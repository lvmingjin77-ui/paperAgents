"""Candidate lineage and the numbered objection ledger of the expert discussion loop.

Pure functions over accepted artifacts. The ledger records what experts actually
submitted: objections, author responses and the original challenger's verdicts.
It never infers a response, a verdict or a consensus that no artifact contains.
"""

from __future__ import annotations

from .storage import digest

CLOSED = {"resolved", "experiment", "withdrawn_target"}


def candidate_archive(hypotheses: list[dict], rebuttals: list[tuple[int, dict]], absorbed: dict | None = None) -> dict:
    """All candidate versions with owners, lineage, withdrawals, same-author successors and consented merges."""
    candidates: dict[str, dict] = {}
    for result in hypotheses:
        for item in result["candidates"]:
            candidates[item["idea_id"]] = dict(item, proposed_by=result["expert_id"], introduced_round=0)
    withdrawn: set[str] = set()
    successor: dict[str, str] = {}
    for round_number, result in rebuttals:
        for item in result.get("revised_candidates", []):
            candidates[item["idea_id"]] = dict(item, proposed_by=result["expert_id"],
                                               introduced_round=round_number)
            for parent in item["parent_ids"]:
                if parent in candidates and candidates[parent]["proposed_by"] == result["expert_id"]:
                    successor[parent] = item["idea_id"]
        withdrawn.update(result.get("withdrawn_idea_ids", []))
    for parent, child in (absorbed or {}).items():
        successor.setdefault(parent, child)
    active = [idea_id for idea_id in candidates if idea_id not in withdrawn and idea_id not in successor]
    return {"candidates": candidates, "withdrawn": withdrawn, "successor": successor, "active": active}


def current_target(idea_id: str, archive: dict) -> str | None:
    """Follow the author's own revisions; a withdrawn line has no current target."""
    seen = set()
    while idea_id in archive["successor"] and idea_id not in seen:
        seen.add(idea_id)
        idea_id = archive["successor"][idea_id]
    if idea_id in archive["withdrawn"] or idea_id not in archive["candidates"]:
        return None
    return idea_id


def candidate_hash(item: dict) -> str:
    """Hash of the candidate record exactly as the coordinator hands it to workers."""
    return digest(item)


def build_ledger(challenges: list[dict], rebuttals: list[tuple[int, dict]],
                 rechecks: list[tuple[int, dict]], archive: dict) -> dict[str, dict]:
    ledger: dict[str, dict] = {}

    def add(objection: dict, review: dict, raised_by: str, round_number: int) -> None:
        ledger[objection["objection_id"]] = dict(
            objection, idea_id=review["idea_id"], candidate_hash=review["candidate_hash"],
            raised_by=raised_by, raised_round=round_number, responses=[], verdicts=[])

    for result in challenges:
        for review in result["reviews"]:
            for objection in review.get("objections", []):
                add(objection, review, result["expert_id"], 0)
    events = sorted([(r, 0, "response", a) for r, a in rebuttals]
                    + [(r, 1, "verdict", a) for r, a in rechecks], key=lambda item: (item[0], item[1]))
    for round_number, _, kind, result in events:
        if kind == "response":
            for response in result["responses"]:
                if response["objection_id"] in ledger:
                    ledger[response["objection_id"]]["responses"].append(
                        dict(response, round=round_number, by=result["expert_id"]))
        else:
            for verdict in result["verdicts"]:
                if verdict["objection_id"] in ledger:
                    ledger[verdict["objection_id"]]["verdicts"].append(
                        dict(verdict, round=round_number, by=result["expert_id"]))
            for review in result.get("new_reviews", []):
                for objection in review["objections"]:
                    add(objection, review, result["expert_id"], round_number)
    for record in ledger.values():
        record["current_idea_id"] = current_target(record["idea_id"], archive)
        current = archive["candidates"].get(record["current_idea_id"] or "", {})
        record["current_round"] = current.get("introduced_round", 0)
        record["status"] = status(record)
    return ledger


def status(record: dict) -> str:
    if record["current_idea_id"] is None:
        return "withdrawn_target"
    last_response = record["responses"][-1]["round"] if record["responses"] else None
    if record["verdicts"] and (last_response is None or record["verdicts"][-1]["round"] >= last_response):
        if record["current_round"] > record["verdicts"][-1]["round"]:
            return "reopened"  # the author changed the candidate after this verdict
        return record["verdicts"][-1]["status"]
    return "responded" if record["responses"] else "open"


def needs_response(record: dict) -> bool:
    return record["status"] in {"open", "unresolved"}


def needs_verdict(record: dict, round_number: int) -> bool:
    return ((record["status"] == "responded" and record["responses"][-1]["round"] == round_number)
            or (record["status"] == "reopened" and record["current_round"] == round_number))


def open_blocking(ledger: dict[str, dict], idea_id: str | None = None) -> list[dict]:
    return [record for record in ledger.values()
            if record["blocking"] and record["status"] not in CLOSED
            and (idea_id is None or record["current_idea_id"] == idea_id)]


def render_ledger(ledger: dict[str, dict], archive: dict) -> str:
    """A readable discussion table built only from submitted records."""
    lines = ["# 讨论议题表", "",
             "仅包含已提交的异议、作者答辩和原质疑者复核；不代表共识或科学结论。", "",
             "| 异议 | 针对候选（当前版本） | 提出者 | 阻塞 | 作者处理 | 复核 | 状态 |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for record in ledger.values():
        actions = "；".join(f"R{item['round']}:{item['action']}" for item in record["responses"]) or "—"
        verdicts = "；".join(f"R{item['round']}:{item['status']}" for item in record["verdicts"]) or "—"
        target = f"{record['idea_id']} → {record['current_idea_id'] or '已撤回'}"
        cell = record["objection"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{record['objection_id']}` {cell} | {target} | {record['raised_by']} | "
                     f"{'是' if record['blocking'] else '否'} | {actions} | {verdicts} | {record['status']} |")
    if not ledger:
        lines.append("| 尚无异议 | — | — | — | — | — | — |")
    lines.extend(["", "## 候选谱系", ""])
    for idea_id, item in archive["candidates"].items():
        state = "撤回" if idea_id in archive["withdrawn"] else (
            f"被 {archive['successor'][idea_id]} 取代" if idea_id in archive["successor"] else "有效")
        parents = ", ".join(item.get("parent_ids", [])) or "初始提案"
        lines.append(f"- `{idea_id}`（{item['proposed_by']}，来源：{parents}）：{state}")
    return "\n".join(lines) + "\n"
