"""Explicit operator commands for a resumable, local research workflow."""

import argparse
import json
from pathlib import Path
import sys

from .config import load_config
from .storage import project_lock, read_json
from .workflow import Workflow, initialize_project, PHASES


def read_status(project):
    """Inspect saved progress without initializing or validating a new research run."""
    project = project.resolve()
    active = project / "active_run.json"
    if not active.exists():
        return {"project": str(project), "status": "not_started", "reason": "No active run"}
    run_id = read_json(active).get("run_id")
    legacy_message = (
        "Old run format cannot resume in 0.2; use research --new. Existing artifacts are preserved."
    )
    if not run_id or Path(run_id).name != run_id:
        raise ValueError(legacy_message)
    run_dir = project / "runs" / run_id
    state_path = run_dir / "state" / "research.json"
    if not state_path.is_file():
        raise ValueError(legacy_message)
    state = read_json(state_path)
    if state.get("schema_version") != 2:
        raise ValueError("Unsupported run format; use research --new. Existing artifacts are preserved.")
    return {k: state[k] for k in ("run_id", "status", "phase", "outer_round", "cycle", "reason", "usage")} | {
        "run_dir": str(run_dir),
        "claims": len(state["claims"]),
        "runs": len(state["runs"]),
        "tasks_completed": sum(t["status"] == "completed" for t in state["tasks"].values()),
        "pending": [
            t["task_id"] for t in state["tasks"].values() if t["status"] not in {"completed", "superseded"}
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(prog="paperagents")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("project", type=Path)
    brief = init.add_mutually_exclusive_group(required=True)
    brief.add_argument("--question")
    brief.add_argument("--brief-file", type=Path)
    for name in ("run", "research", "status", "retry", "submit", "approve", "revise", "web", "plan"):
        p = commands.add_parser(name)
        p.add_argument("project", type=Path)
        if name in ("run", "research"):
            p.add_argument("--new", action="store_true")
            p.add_argument(
                "--execute",
                action="store_true",
                help="Authorize the coordinator to execute reviewed experiments",
            )
            p.add_argument("--until", choices=PHASES)
        elif name in ("retry", "submit"):
            p.add_argument("task_id")
            if name == "submit":
                p.add_argument("response", type=Path)
        elif name == "approve":
            p.add_argument("checkpoint", choices=("testbed", "final_method", "submission"))
        elif name == "revise":
            p.add_argument("--from", dest="phase", required=True, choices=("knowledge", "testbed", "evolve"))
            p.add_argument("--reason", required=True)
        elif name == "web":
            p.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize_project(args.project, args.question or "", brief_file=args.brief_file)
            result = {
                "project": str(args.project.resolve()),
                "next": "Review paperagents.toml, then paperagents research PROJECT",
            }
        elif args.command == "web":
            from .web import serve

            serve(args.project.resolve(), port=args.port)
            return 0
        elif args.command == "status":
            result = read_status(args.project)
        elif args.command == "plan":
            config = load_config(args.project)
            result = {
                "phases": PHASES,
                "resources": config["resources"],
                "loops": config["loops"],
                "execution": "Without --execute, pause before running any evaluation; GLM workers may still be called.",
            }
        else:
            if args.command not in ("run", "research") and not (args.project / "active_run.json").is_file():
                raise ValueError("No active run; start one with paperagents research PROJECT")
            with project_lock(args.project):
                w = Workflow(args.project, new=getattr(args, "new", False))
                if args.command in ("run", "research"):
                    result = w.run(execute=args.execute, until=args.until)
                elif args.command == "retry":
                    w.retry(args.task_id)
                    result = w.summary()
                elif args.command == "submit":
                    w.submit(args.task_id, args.response)
                    result = w.summary()
                elif args.command == "approve":
                    w.approve(args.checkpoint)
                    result = w.summary()
                elif args.command == "revise":
                    w.revise(args.phase, args.reason)
                    result = w.summary()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError) as exc:
        print(f"paperagents: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
