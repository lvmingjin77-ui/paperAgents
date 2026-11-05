"""Version-bound review scores and a readable report; no aggregate or ranking."""

from __future__ import annotations

import html
import json

from .contracts import REVIEW_DIMENSIONS
from .storage import digest


def review_targets(candidates: list[dict], synthesis: dict) -> dict:
    return {"candidates": [{"idea_id": candidate["idea_id"], "candidate_hash": digest(candidate)}
                           for candidate in candidates],
            "proposal_hash": digest(synthesis["proposal"]),
            "selected_idea_id": synthesis["selected_idea_id"]}


def validate_score_targets(review: dict, targets: dict) -> None:
    expected = {item["idea_id"]: item["candidate_hash"] for item in targets["candidates"]}
    scores = review["candidate_scores"]
    ids = [item["idea_id"] for item in scores]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        raise ValueError("Review scores must cover every candidate exactly once")
    for score in scores:
        if score["candidate_hash"] != expected[score["idea_id"]]:
            raise ValueError(f"Review score refers to a different candidate version: {score['idea_id']}")
    if review["proposal_score"]["proposal_hash"] != targets["proposal_hash"]:
        raise ValueError("Review score refers to a different proposal version")


def score_summary(review: dict) -> dict:
    summary = {"accepted": review["accepted"], "blocking_issues": review["blocking_issues"]}

    def compact(record: dict) -> dict:
        return {key: value for key, value in record.items() if key != "dimensions"} | {
            "dimensions": {key: record["dimensions"][key]["score"] for key in REVIEW_DIMENSIONS}}

    return dict(summary, scoring_status="available",
                candidate_scores=[compact(item) for item in review["candidate_scores"]],
                proposal_score=compact(review["proposal_score"]))


def _inline(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    text = html.escape(text, quote=False).replace("\\", "\\\\")
    for character in ("`", "*", "_", "[", "]", "|", "#"):
        text = text.replace(character, "\\" + character)
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _score(item: dict) -> str:
    return "未知" if item["status"] == "unknown" else f"{item['score']}/5"


def _evidence(items: list) -> str:
    return "；".join(_inline(item) for item in items) if items else "未提供；见缺口说明"


def _details(title: str, record: dict, version_key: str) -> list[str]:
    lines = [f"### {title}", "", f"版本：`{record[version_key]}`", ""]
    for key, label in REVIEW_DIMENSIONS.items():
        item = record["dimensions"][key]
        lines.extend([f"- **{label}：{_score(item)}**。{_inline(item['rationale'])}",
                      f"  证据：{_evidence(item['evidence'])}"])
    lines.append("")
    return lines


def render_review(review: dict, context: dict, artifact_path: str) -> str:
    decision = "通过，可交给实验阶段" if review["accepted"] else "未通过，需处理评审意见"
    lines = ["# Idea 六维评审", "", f"本轮裁决：**{decision}**。", "",
             f"完整评审记录：`{artifact_path}`", ""]
    lines.extend(["分数为评审者基于所列证据的 1–5 级判断；未知不计作 0 分。"
                  "不计算加权总分，不按分数自动选优或放行。", "",
                  "## 最终提案", "",
                  (f"{_inline(context['synthesis']['proposal'].get('title', '（未选择提案）'))}"
                   f"（综合决定：{_inline(context['synthesis']['decision'])}；"
                   f"所选候选：{_inline(context['synthesis']['selected_idea_id'])}）"), "",
                  "| 维度 | 评分 |", "| --- | --- |"])
    for key, label in REVIEW_DIMENSIONS.items():
        lines.append(f"| {label} | {_score(review['proposal_score']['dimensions'][key])} |")
    lines.extend(["", "## 候选对照", "",
                  "按候选原有顺序展示。候选与综合后的最终提案分别评分，避免混用两个版本。", "",
                  "| 候选 | " + " | ".join(REVIEW_DIMENSIONS.values()) + " |",
                  "| --- | " + " | ".join("---" for _ in REVIEW_DIMENSIONS) + " |"])
    scores = {item["idea_id"]: item for item in review["candidate_scores"]}
    for candidate in context["candidates"]:
        item = scores[candidate["idea_id"]]
        label = f"{candidate['idea_id']}：{candidate['title']}"
        cells = " | ".join(_score(item["dimensions"][key]) for key in REVIEW_DIMENSIONS)
        lines.append(f"| {_inline(label)} | {cells} |")
    lines.extend(["", "## 评分理由与证据", ""])
    lines.extend(_details("最终提案", review["proposal_score"], "proposal_hash"))
    for candidate in context["candidates"]:
        lines.extend(_details(_inline(candidate["idea_id"]), scores[candidate["idea_id"]], "candidate_hash"))
    assessment = review["decision_assessment"]
    lines.extend(["## 对综合决定的复核", "",
                  f"综合决定：`{_inline(assessment['synthesis_decision'])}`；评审"
                  f"{'同意' if assessment['agree'] else '不同意'}。{_inline(assessment['reason'])}", ""])
    lines.extend(["## 准入检查", "", "| 检查 | 结论 | 证据 |", "| --- | --- | --- |"])
    for check in review["checks"]:
        lines.append(f"| {_inline(check['check'])} | {check['verdict']} | {_evidence(check['evidence'])} |")
    if not review["checks"]:
        lines.append("| 尚无检查记录 | unknown | 未提供 |")
    lines.extend(["", "## 阻塞项", ""])
    lines.extend(f"- {_inline(issue)}" for issue in review["blocking_issues"])
    if not review["blocking_issues"]:
        lines.append("无已记录阻塞项；裁决以准入检查和独立评审意见为准。")
    return "\n".join(lines) + "\n"
