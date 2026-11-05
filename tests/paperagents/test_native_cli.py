"""Exercise public native entrypoints with manual workers and real CPU execution."""

import json
from pathlib import Path

from paperagents.cli import main
from paperagents.workflow import Workflow, initialize_project
from tests.paperagents.test_native_experiments import build_response, review_response
from tests.paperagents.test_workflow import advance


def invoke(capsys, *arguments):
    assert main(list(arguments)) == 0
    return json.loads(capsys.readouterr().out)


def test_research_starts_with_question_and_experiment_requires_review(tmp_path, capsys):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC TEST QUESTION")
    assert main(["experiment", str(project)]) == 1
    assert "Start a run first" in capsys.readouterr().err
    result = invoke(capsys, "research", str(project), "--execute")
    assert result["status"] == "awaiting_workers"
    assert result["phase"] == "scope"
    assert not (Workflow(project).run_dir / "experiments").exists()
    assert main(["experiment", str(project), "--execute"]) == 1
    assert "review ideation" in capsys.readouterr().err


def test_cli_runs_local_experiment_then_resumes_expert_revision(tmp_path, capsys):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC TEST QUESTION")
    advance(Workflow(project))
    build = invoke(capsys, "research", str(project))
    assert build["phase"] == "experiment_build"
    build_response(build)
    review = invoke(capsys, "experiment", str(project))
    assert review["phase"] == "experiment_review"
    review_response(review)
    ready = invoke(capsys, "research", str(project))
    assert ready["status"] == "ready_for_experiment"
    cycle = Path(ready["experiment_dir"])
    assert not (cycle / "executions").exists()
    completed = invoke(capsys, "experiment", str(project), "--execute")
    assert completed["experiment_status"] == "completed"
    assert completed["status"] == "awaiting_workers"
    assert completed["phase"] == "hypothesis"
    assert completed["pending"]
    resumed = invoke(capsys, "experiment", str(project))
    assert resumed["feedback_path"] == completed["feedback_path"]
    assert len(Workflow(project).state["feedback"]) == 1


def test_cli_rebuild_preserves_rejected_experiment(tmp_path, capsys):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC TEST QUESTION")
    advance(Workflow(project))
    build = invoke(capsys, "experiment", str(project))
    build_response(build)
    review = invoke(capsys, "experiment", str(project))
    review_response(review, accepted=False)
    rejected = invoke(capsys, "experiment", str(project), "--execute")
    assert rejected["phase"] == "review_rejected"
    old_review = Path(review["pending"][0]["response_path"])
    old_bytes = old_review.read_bytes()
    rebuilt = invoke(capsys, "experiment", str(project), "--rebuild")
    assert rebuilt["phase"] == "experiment_build"
    assert rebuilt["experiment_dir"] != rejected["experiment_dir"]
    assert old_review.read_bytes() == old_bytes


def test_new_project_cannot_reenter_legacy_ideation(tmp_path, capsys):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC TEST QUESTION")
    advance(Workflow(project))
    assert main(["v3", str(project)]) == 1
    assert "native" in capsys.readouterr().err.lower()
