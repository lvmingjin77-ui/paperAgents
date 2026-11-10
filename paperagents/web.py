"""Read-only research observatory. All data stays inside the selected project."""

from __future__ import annotations

import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PAGE = Path(__file__).with_name("web.html")
_SECRET = re.compile(r"(?i)(?:api[_-]?key|access[_-]?token|authorization|password|secret)")
_TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|[a-f0-9]{32}\.[A-Za-z0-9]{12,})\b"
)
_ASSIGNMENT = re.compile(
    r"""(?i)(\b(?:api[_-]?key|access[_-]?token|authorization|password|secret)["']?\s*[:=]\s*["']?)([^\s,"'\]}]+)"""
)


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if _SECRET.fullmatch(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _ASSIGNMENT.sub(
            r"\1[REDACTED]",
            re.sub(r"(?i)Bearer\s+[A-Za-z0-9_.-]+", "Bearer [REDACTED]", _TOKEN.sub("[REDACTED]", value)),
        )
    return value


def _json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text())


def _lines(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    lines = []
    for index, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        try:
            event = json.loads(line)
        except ValueError:
            event = {"type": "text", "text": line}
        if not isinstance(event, dict):
            event = {"type": "text", "text": str(event)}
        # Streaming token counters are telemetry, not actions or scientific output.
        if (
            event.get("type") == "thinking_tokens"
            or event.get("subtype") == "thinking_tokens"
            or (event.get("type") == "text" and line.strip() == "thinking_tokens")
        ):
            continue
        if event.get("type") == "stream_event":
            delta = event.get("event", {}).get("delta", {})
            if delta.get("type") in {"thinking_delta", "signature_delta"}:
                continue
        event["log_line"] = index
        lines.append(redact(event))
    return lines


class View:
    def __init__(self, project: Path):
        self.project = project.resolve()
        self._transcripts = {}

    def _safe(self, value: str | Path) -> Path:
        path = Path(value)
        path = (path if path.is_absolute() else self.project / path).resolve()
        if not path.is_relative_to(self.project) or any(
            p.startswith(".") or p.lower() in {"credentials", "secrets", "auth.json"}
            for p in path.relative_to(self.project).parts
        ):
            raise ValueError("File is outside public project artifacts")
        return path

    def _run(self, run_id: str | None = None) -> Path:
        if not run_id:
            run_id = (_json(self.project / "active_run.json", {}) or {}).get("run_id")
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("No selected research run")
        path = self._safe(self.project / "runs" / run_id)
        if not (path / "state" / "research.json").is_file():
            raise ValueError("Run does not use the current research state format")
        return path

    def runs(self) -> dict:
        runs = []
        for path in sorted((self.project / "runs").glob("*/state/research.json"), reverse=True):
            data = _json(self._safe(path), {})
            runs.append(
                {
                    "run_id": path.parents[1].name,
                    "status": data.get("status"),
                    "phase": data.get("phase"),
                    "cycle": data.get("cycle"),
                }
            )
        return {"active": (_json(self.project / "active_run.json", {}) or {}).get("run_id"), "runs": runs}

    def state(self, run_id: str | None = None) -> dict:
        return redact(_json(self._run(run_id) / "state" / "research.json", {}))

    def events(self, run_id: str | None = None) -> list:
        return _lines(self._run(run_id) / "events.jsonl")

    def _transcript(self, path: Path) -> list:
        if not path.is_file():
            return []
        stat = path.stat()
        signature = (stat.st_size, stat.st_mtime_ns)
        cached = self._transcripts.get(path)
        if cached is None or cached[0] != signature:
            cached = (signature, _lines(path))
            self._transcripts[path] = cached
        return cached[1]

    def task(self, task_id: str, run_id: str | None = None) -> dict:
        state = self.state(run_id)
        task = state.get("tasks", {}).get(task_id)
        if task is None:
            raise ValueError("Unknown task")
        request = self._safe(task["request_path"])
        response = self._safe(task["response_path"])
        attempts = []
        directory = request.parent
        logs = sorted(directory.parent.glob("attempt-*/driver.log"))
        for path in logs:
            safe = self._safe(path)
            attempts.append(
                {
                    "name": path.parent.name,
                    "path": str(path),
                    "transcript": self._transcript(safe),
                    "feedback": _json(path.parent / "validation_feedback.json"),
                }
            )
        return redact(
            {"task": task, "request": _json(request), "response": _json(response), "attempts": attempts}
        )

    def pool(self, run_id: str | None = None) -> list:
        state = self.state(run_id)
        stages = {
            "propose",
            "exchange",
            "revise",
            "triage",
            "merge",
            "assess",
            "select",
            "judge",
            "explain",
            "evolve",
            "novelty",
            "ablation_plan",
            "peer_review",
            "meta_review",
            "freeze",
            "testbed_plan",
            "argument",
            "write_section",
            "rebuttal",
            "final_judgment",
            "method_spec",
            "reassess",
            "faithfulness",
        }
        pool = []
        for task_id, task in state.get("tasks", {}).items():
            if task.get("stage") in stages and task.get("status") == "completed":
                pool.append(
                    {
                        "task_id": task_id,
                        "stage": task["stage"],
                        "subject": task.get("subject"),
                        "role": task.get("role"),
                        "timestamp": task.get("completed_at"),
                        "output": _json(self._safe(task["response_path"]), {}),
                    }
                )
        return redact(pool)

    def errors(self, run_id: str | None = None) -> list:
        errors = []
        for task_id, task in self.state(run_id).get("tasks", {}).items():
            if task.get("status") in {"failed", "rejected", "interrupted"} or task.get("error"):
                errors.append(
                    {"task_id": task_id, "kind": "task", "error": task.get("error", task["status"])}
                )
            if not task.get("request_path"):
                continue
            for attempt in self.task(task_id, run_id)["attempts"]:
                calls = {}
                for event in attempt["transcript"]:
                    for block in (
                        event.get("message", {}).get("content", [])
                        if isinstance(event.get("message", {}).get("content"), list)
                        else []
                    ):
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "tool_use":
                            calls[block.get("id")] = block.get("name")
                        elif block.get("type") == "tool_result" and block.get("is_error"):
                            errors.append(
                                {
                                    "task_id": task_id,
                                    "kind": "tool",
                                    "attempt": attempt["name"],
                                    "tool": calls.get(block.get("tool_use_id"), "tool"),
                                    "line": event["log_line"],
                                    "error": block.get("content"),
                                }
                            )
                    if event.get("type") == "result" and event.get("is_error"):
                        errors.append(
                            {"task_id": task_id, "kind": "worker", "error": event.get("result", event)}
                        )
        for run_id, run in self.state(run_id).get("runs", {}).items():
            if run.get("outcome") not in {"completed", None}:
                errors.append(
                    {"run_id": run_id, "kind": "experiment", "error": run.get("reason", run.get("outcome"))}
                )
        return redact(errors)

    def file(self, path: str) -> dict:
        target = self._safe(path)
        if not target.is_file():
            raise ValueError("Missing artifact")
        if target.stat().st_size > 5_000_000:
            return {"text": "文件超过 5 MB，请从本地路径打开。", "path": str(target)}
        return {"text": redact(target.read_text(errors="replace")), "path": str(target)}


def serve(project: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    view = View(project)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            return

        def do_GET(self):
            url = urlparse(self.path)
            query = {key: values[0] for key, values in parse_qs(url.query).items()}
            routes = {
                "/api/runs": lambda: view.runs(),
                "/api/state": lambda: view.state(query.get("run")),
                "/api/events": lambda: view.events(query.get("run")),
                "/api/task": lambda: view.task(query["id"], query.get("run")),
                "/api/pool": lambda: view.pool(query.get("run")),
                "/api/errors": lambda: view.errors(query.get("run")),
                "/api/file": lambda: view.file(query["path"]),
            }
            code, kind = 200, "application/json; charset=utf-8"
            try:
                if url.path == "/":
                    body, kind = PAGE.read_bytes(), "text/html; charset=utf-8"
                elif url.path in routes:
                    body = json.dumps(routes[url.path](), ensure_ascii=False).encode()
                else:
                    code, body = 404, b'{"error":"not found"}'
            except (ValueError, KeyError, OSError) as exc:
                code, body = 404, json.dumps({"error": str(exc)}, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"PaperAgents http://{host}:{port}（只读）")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
