"""Read-only live view of a PaperAgents project; standard library only, bound to localhost.

It reads the run directory (state, requests, artifacts, ledger, events, worker transcripts)
and never writes, so observing a run cannot change it.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .workflow import PHASES, key

PAGE = Path(__file__).with_name("web.html")
STAGE_PHASE = {"consultant": "paper"}


def _json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _lines(path: Path) -> list:
    """JSON lines where possible, raw text otherwise (worker transcripts and the event log)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"type": "raw", "text": line})
    return out


class View:
    def __init__(self, project: Path):
        self.project = project.resolve()
        self._tool_error_cache = {}

    def tool_errors(self, run_id: str) -> list:
        folder = self._run(run_id)
        errors = []
        for path in sorted((folder / "requests").glob("*/attempts/*/driver.log")):
            stat = path.stat()
            signature = (stat.st_mtime_ns, stat.st_size)
            cached = self._tool_error_cache.get(path)
            if cached is None or cached[0] != signature:
                calls, found = {}, []
                for line, event in enumerate(_lines(path), 1):
                    blocks = event.get("message", {}).get("content", [])
                    if not isinstance(blocks, list):
                        continue
                    for block in blocks:
                        if block.get("type") == "tool_use":
                            calls[block["id"]] = block.get("name", "未知工具")
                        elif block.get("type") == "tool_result" and block.get("is_error"):
                            content = block.get("content", "")
                            found.append({"task_id": path.parents[2].name,
                                          "attempt": path.parent.name,
                                          "tool": calls.get(block.get("tool_use_id"), "未知工具"),
                                          "line": line,
                                          "error": content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)})
                cached = (signature, found)
                self._tool_error_cache[path] = cached
            errors.extend(cached[1])
        return errors

    def _run(self, run_id: str) -> Path:
        path = (self.project / "runs" / run_id).resolve()
        if path.parent != (self.project / "runs").resolve() or not path.is_dir():
            raise KeyError(run_id)
        return path

    def runs(self) -> dict:
        active = (_json(self.project / "active_run.json") or {}).get("run_id")
        runs = []
        for folder in sorted((self.project / "runs").glob("*"), reverse=True):
            state = _json(folder / "state.json") or {}
            runs.append({"run_id": folder.name, "status": state.get("status"), "iteration": state.get("iteration")})
        return {"project": str(self.project), "active": active, "runs": runs}

    def run(self, run_id: str) -> dict:
        folder = self._run(run_id)
        state = _json(folder / "state.json") or {}
        tasks = [dict(task, phase=STAGE_PHASE.get(task["stage"], task["stage"])) for task in state.get("tasks", {}).values()]
        experiments = [dict(_json(path) or {}, cycle=path.parent.name)
                       for path in sorted((folder / "experiments").glob("*/state.json"))]
        for item in experiments:
            item["results"] = {p.stem: _json(p) for p in (folder / "experiments" / item["cycle"] / "results").glob("*.json")}
        brief = folder / "research.md"
        return {"run_id": run_id, "phases": list(PHASES) + (["evidence"] if state.get("evidence_round") else []), "tasks": tasks, "events": _lines(folder / "events.jsonl"),
                "state": {k: v for k, v in state.items() if k not in {"tasks", "batches"}},
                "phase_index": state.get("phase_index", 0),
                "current_phase": "evidence" if state.get("evidence_active") else (
                    PHASES[state.get("phase_index", 0)] if state.get("phase_index", 0) < len(PHASES) else "export"), "ledger": _json(folder / "debate" / "ledger.json"),
                "experiments": experiments, "brief": brief.read_text(encoding="utf-8") if brief.is_file() else "",
                "graph": _json(folder / "domain_graph" / "graph.json") and str(folder / "domain_graph")}

    def task(self, run_id: str, task_id: str) -> dict:
        folder = self._run(run_id)
        directory = folder / "requests" / task_id
        if directory.parent != folder / "requests" or not directory.is_dir():
            raise KeyError(task_id)
        attempts = []
        for attempt in sorted((directory / "attempts").glob("*")):
            attempts.append({"name": attempt.name, "feedback": _json(attempt / "validation_feedback.json"),
                             "receipt": _json(attempt / "driver_receipt.json"),
                             "failed": {p.name: _json(p) for p in attempt.glob("failed-response-*.json")},
                             "transcript": _lines(attempt / "driver.log")})
        rejected = {p.name: _json(p) for p in directory.glob("*-response-*.json")}
        return {"request": _json(directory / "request.json"), "artifact": _json(folder / "artifacts" / f"{task_id}.json"),
                "response": _json(directory / "response.json"), "rejected": rejected, "attempts": attempts}

    def experts(self, run_id: str) -> list:
        folder = self._run(run_id)
        state = _json(folder / "state.json") or {}
        reviews = {}
        experts = []
        for task in state.get("tasks", {}).values():
            if task["status"] != "completed":
                continue
            data = _json(folder / "artifacts" / f"{task['task_id']}.json") or {}
            if task["stage"] == "expert_review":
                reviews[task["subject_id"]] = data
            elif task["stage"] in {"domain", "paper", "consultant"}:
                experts.append({"expert_id": data.get("expert_id"), "stage": task["stage"], "task_id": task["task_id"],
                                "asset": (data.get("_asset") or {}).get("path"), "limitations": data.get("limitations"),
                                "knowledge_keys": sorted((data.get("knowledge") or {}).keys())})
        for expert in experts:
            expert["review"] = reviews.get(expert["expert_id"])
            expert["notebook"] = _lines(folder / "notebooks" / f"{key(expert['expert_id'] or '')}.jsonl")
        return experts

    def pool(self, run_id: str) -> list:
        """Every expert utterance of the discussion, in acceptance order."""
        folder = self._run(run_id)
        state = _json(folder / "state.json") or {}
        order = {e.get("task"): i for i, e in enumerate(_lines(folder / "events.jsonl")) if e.get("kind") == "accepted"}
        tasks = sorted((t for t in state.get("tasks", {}).values() if t["status"] == "completed"),
                       key=lambda t: order.get(t["task_id"], len(order)))
        messages = []
        for task in tasks:
            stage, data = task["stage"], _json(folder / "artifacts" / f"{task['task_id']}.json") or {}
            who = data.get("expert_id") or {"agenda": "domain（主持）", "synthesis": "domain（综合）", "triage": "初筛核查",
                                            "novelty": "查新核查", "proposal_review": "独立评审", "evidence": "补证据核查"}.get(stage)
            if who is None:
                continue
            base = {"task": task["task_id"], "stage": stage, "round": task.get("round"),
                    "iteration": task["task_id"][1:4], "speaker": who}

            def say(kind, text, target="", **extra):
                messages.append(dict(base, kind=kind, text=text, target=target, **extra))

            if stage == "hypothesis":
                for c in data.get("candidates", []):
                    say("提案", f"{c['title']}\n假设：{c['hypothesis']}\n机制：{c['mechanism']}\n反证：{c['falsification']}", c["idea_id"])
            elif stage == "triage":
                for r in data.get("reviews", []):
                    say(f"初筛：{r['overlap_risk']}", r["note"], r["idea_id"])
                for g in data.get("groups", []):
                    say(f"归组：{g['relation']}", f"{g['reason']}\n代表：{g['representative']}", ", ".join(g["idea_ids"]), id=g["group_id"])
            elif stage == "agenda":
                for i in data.get("issues", []):
                    say(f"议题：{i['kind']}", f"{i['question']}\n指派：{', '.join(i['assigned_expert_ids'])}",
                        ", ".join(i["idea_ids"]), id=i["issue_id"])
            elif stage in {"challenge", "recheck"}:
                for r in data.get("reviews", []) + data.get("new_reviews", []):
                    for o in r.get("objections", []):
                        say("异议（阻塞）" if o["blocking"] else "异议",
                            f"{o['claim']}\n→ {o['objection']}\n解除条件：{o['resolution_test']}", r["idea_id"], id=o["objection_id"])
                for i in data.get("issue_responses", []):
                    say("议题回应", i["response"], i["issue_id"])
                for v in data.get("verdicts", []):
                    say(f"复核：{v['status']}", v["reason"], v["objection_id"])
            elif stage in {"merge", "rebuttal"}:
                for r in data.get("responses", []):
                    say(f"{'合并确认' if stage == 'merge' else '答辩'}：{r['action']}", r["argument"] + (f"\n新版本：{r['revised_idea_id']}" if r.get("revised_idea_id") else ""),
                        r["objection_id"])
                for c in data.get("revised_candidates", []):
                    say("修订 / 组合", f"{c['title']}\n来源：{', '.join(c['parent_ids'])}\n{c['change_summary']}", c["idea_id"])
                for idea in data.get("withdrawn_idea_ids", []):
                    say("撤回", "作者撤回该候选", idea)
            elif stage == "novelty":
                for r in data.get("reviews", []):
                    say(f"查新：{r['status']}", r["reason"], r["idea_id"])
            elif stage == "evidence":
                say(f"补证据：{data['outcome']}",
                    f"{data['finding']}\n下一步：{data['next_step']}\n证据："
                    + json.dumps(data["evidence"], ensure_ascii=False), data["issue_id"])
            elif stage == "synthesis":
                say(f"综合：{data.get('decision')}",
                    f"选择：{data.get('selected_idea_id')}；下一步：{data.get('next_action')}\n"
                    + json.dumps(data.get("unresolved_questions", []), ensure_ascii=False), data.get("selected_idea_id") or "")
            elif stage == "proposal_review":
                a = data.get("decision_assessment", {})
                say("评审：" + ("通过" if data.get("accepted") else "未通过"),
                    f"{'同意' if a.get('agree') else '不同意'}综合决定：{a.get('reason', '')}\n阻塞：{data.get('blocking_issues')}")
        return messages

    def file(self, path: str) -> str:
        target = Path(path).resolve()
        if not target.is_relative_to(self.project) or not target.is_file():
            raise KeyError(path)
        return target.read_text(encoding="utf-8", errors="replace")[:500_000]


def serve(project: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    view = View(project)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep the terminal quiet
            return

        def send(self, code: int, body: bytes, kind: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            routes = {"/api/runs": lambda: view.runs(), "/api/run": lambda: view.run(q["run"]),
                      "/api/tool-errors": lambda: view.tool_errors(q["run"]),
                      "/api/task": lambda: view.task(q["run"], q["task"]), "/api/pool": lambda: view.pool(q["run"]),
                      "/api/experts": lambda: view.experts(q["run"]), "/api/file": lambda: {"text": view.file(q["path"])}}
            if url.path == "/":
                return self.send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            if url.path not in routes:
                return self.send(404, b"not found", "text/plain")
            try:
                body = json.dumps(routes[url.path](), ensure_ascii=False).encode()
            except (KeyError, ValueError) as exc:
                return self.send(404, json.dumps({"error": str(exc)}).encode(), "application/json")
            self.send(200, body, "application/json; charset=utf-8")

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"PaperAgents web: http://{host}:{port}  (read-only, Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
