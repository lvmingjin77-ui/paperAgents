"""Public PaperAgents CLI; downstream agsci remains available unchanged."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import ROOT
from .contracts import STAGES, artifact_schema, validate_artifact
from .storage import project_lock, read_json
from .workflow import PHASES, Workflow, initialize_project


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paperagents", description="Expert ideation and native search experiments")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="Create a project from a research question or Markdown brief")
    init.add_argument("project", type=Path)
    brief = init.add_mutually_exclusive_group(required=True)
    brief.add_argument("--direction", help="Research question/task text (legacy option name)")
    brief.add_argument("--brief-file", type=Path, help="Copy this Markdown research brief without rewriting it")
    for command in ("run", "research", "experiment", "status", "review", "plan", "submit", "revise", "retry", "feedback", "v3"):
        sub = commands.add_parser(command)
        sub.add_argument("project", type=Path)
        if command == "run":
            sub.add_argument("--new", action="store_true", help="Create a fresh run; preserve prior runs and library")
        if command in {"research", "experiment"}:
            sub.add_argument("--execute", action="store_true", help="Run the reviewed local experiment and feed results back to the experts")
        if command == "research":
            sub.add_argument("--max-experiments", type=int, default=1,
                             help="Total experiment cycles in this run (default: 1); resuming does not reset the limit")
        if command == "experiment":
            sub.add_argument("--rebuild", action="store_true", help="Rebuild a rejected experiment while preserving its review and files")
        if command in {"submit", "retry"}:
            sub.add_argument("task_id")
            sub.add_argument("response", type=Path)
        if command == "revise":
            sub.add_argument("--from", dest="phase", choices=PHASES, required=True)
            sub.add_argument("--reason", required=True)
        if command == "feedback":
            sub.add_argument("file", type=Path)
        if command == "v3":
            sub.add_argument("--execute", action="store_true", help="Execute the reviewed task; default only previews upstream commands")
            sub.add_argument("--override", action="append", default=[], help="A v3 Hydra key=value override; repeatable")
    schema = commands.add_parser("schema", help="Print the artifact schema for a worker stage")
    schema.add_argument("stage", choices=STAGES)
    validate = commands.add_parser("validate")
    validate.add_argument("stage", choices=STAGES)
    validate.add_argument("file", type=Path)
    commands.add_parser("skills", help="List registered research skills")
    web = commands.add_parser("web", help="Read-only live web view of a project's runs")
    web.add_argument("project", type=Path)
    web.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize_project(args.project, args.direction or "", brief_file=args.brief_file)
            result = {"project": str(args.project.resolve()), "next": "paperagents run <project>"}
        elif args.command == "schema":
            result = artifact_schema(args.stage)
        elif args.command == "validate":
            validate_artifact(args.stage, read_json(args.file))
            result = {"valid_structure": True, "scientific_validity": "requires independent review"}
        elif args.command == "web":
            from .web import serve
            serve(args.project, port=args.port)  # read-only; never takes the coordinator lock
            return 0
        elif args.command == "skills":
            result = read_json(ROOT / "skills" / "registry.json")
        else:
            if not args.project.is_dir():
                raise ValueError("Project directory does not exist; use init first")
            with project_lock(args.project):
                workflow = Workflow(args.project, new=args.command == "run" and args.new)
                if args.command == "status":
                    result = workflow.summary()
                elif args.command == "review":
                    print(workflow.review_report())
                    return 0
                elif args.command == "plan":
                    result = {"phases": list(PHASES),
                              "core_experts": 1 + workflow.config["research"]["core_papers"],
                              "discussion": dict(workflow.config["discussion"],
                                                 loop="challenge → rebuttal ⇄ recheck until no open blocking objection"),
                              "temporary_experts": workflow.config["research"]["allow_temporary_experts"],
                              "backend": workflow.config["backend"]["kind"],
                              "experiment": "native build → independent review → baseline/candidate evaluation → expert revision",
                              "execution": "local Python; no legacy create-idea or Docker requirement"}
                elif args.command == "run":
                    result = workflow.run(new=args.new)
                elif args.command == "research":
                    from .experiments import run_research
                    result = run_research(workflow, execute=args.execute, max_experiments=args.max_experiments)
                elif args.command == "experiment":
                    from .experiments import run_experiment
                    result = run_experiment(workflow, execute=args.execute, rebuild=args.rebuild)
                elif args.command == "submit":
                    workflow.submit(args.task_id, args.response)
                    result = workflow.run()
                elif args.command == "retry":
                    workflow.retry(args.task_id)  # registers only; `run` dispatches it
                    result = dict(workflow.summary(), next="paperagents run <project>")
                elif args.command == "revise":
                    workflow.revise(args.phase, args.reason)  # registers only; `research` continues the run
                    result = dict(workflow.summary(), next="paperagents research <project> [--execute]")
                elif args.command == "feedback":
                    workflow.add_feedback(args.file)
                    result = workflow.summary()
                else:
                    if workflow.state.get("status") != "completed":
                        raise ValueError("A reviewed, exported proposal is required before invoking v3")
                    workflow.start()  # Reject a changed research brief before starting execution.
                    from .v3 import run_v3
                    overrides = list(args.override)
                    if not any(item.lstrip("+").startswith("execution.phases=") for item in overrides):
                        overrides.insert(0, "execution.phases=task_drafting,investigation")
                    process = run_v3(Path(workflow.state["task_dir"]), overrides, dry_run=not args.execute,
                                     expected_receipt=workflow.state.get("export_receipt"))
                    return process.returncode
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError) as exc:
        print(f"paperagents: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
