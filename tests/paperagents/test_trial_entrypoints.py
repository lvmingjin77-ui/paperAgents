"""A local Markdown brief enters the research-only path without launching models."""

import subprocess
from pathlib import Path

import pytest

from paperagents import v3
from paperagents.cli import main
from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow, initialize_project
from tests.paperagents.test_workflow import advance, answer


def test_markdown_input_is_preserved_and_invalid_input_does_not_create_project(tmp_path, capsys):
    brief = tmp_path / "研究问题.md"
    content = "# Research question\n\nSYNTHETIC_TEST_FIXTURE\n\n## Constraints\n\nKeep these details.\n"
    brief.write_text(content)
    project = tmp_path / "project"
    assert main(["init", str(project), "--brief-file", str(brief)]) == 0
    assert (project / "research.md").read_text() == content
    brief.write_text("# No question\n\n## Still only headings\n")
    invalid = tmp_path / "invalid"
    assert main(["init", str(invalid), "--brief-file", str(brief)]) == 1
    assert not invalid.exists()
    capsys.readouterr()


@pytest.fixture
def completed_project(tmp_path):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    workflow = Workflow(project)
    assert advance(workflow)["status"] == "completed"
    return project


def test_cli_defaults_to_drafting_and_investigation_and_preserves_explicit_override(completed_project, monkeypatch):
    calls = []

    def capture(task, overrides, **options):
        calls.append((task, overrides, options))
        return subprocess.CompletedProcess([], 0)

    monkeypatch.setattr(v3, "run_v3", capture)
    assert main(["v3", str(completed_project)]) == 0
    _, overrides, options = calls[-1]
    assert "execution.phases=task_drafting,investigation" in overrides
    assert options["dry_run"] is True
    assert options["expected_receipt"] == Workflow(completed_project).state["export_receipt"]
    assert main(["v3", str(completed_project), "--override", "execution.phases=investigation"]) == 0
    assert calls[-1][1] == ["execution.phases=investigation"]


def test_changed_reviewed_export_cannot_reach_execution(completed_project, monkeypatch, capsys):
    workflow = Workflow(completed_project)
    task = Path(workflow.state["task_dir"])
    (task / "task.md").write_text("Different, unreviewed research")

    def forbidden(*args, **kwargs):
        raise AssertionError("An altered research export must never launch an experiment")

    monkeypatch.setattr(v3.subprocess, "run", forbidden)
    assert main(["v3", str(completed_project), "--execute"]) == 1
    assert "task.md" in capsys.readouterr().err


@pytest.mark.parametrize("mutation", ["hash", "idea_id", "problem", "hypothesis", "mechanism", "assumptions", "falsification"])
def test_synthesis_cannot_change_reviewed_scientific_core(tmp_path, mutation):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    workflow = Workflow(project)
    summary = advance(workflow, stop="synthesis")
    task_id = summary["pending"][0]["task_id"]
    directory = workflow.run_dir / "requests" / task_id
    request = read_json(directory / "request.json")
    data = answer(request, project)
    if mutation == "hash":
        data["candidate_ref"]["candidate_hash"] = "0" * 64
    elif mutation == "idea_id":
        data["candidate_ref"]["idea_id"] = "different-idea"
    else:
        data["proposal"][mutation] = ["changed"] if mutation == "assumptions" else "Different scientific content"
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="candidate|scientific"):
        workflow.submit(task_id, directory / "response.json")
    assert workflow.state["tasks"][task_id]["status"] == "pending"
    assert not (workflow.run_dir / "artifacts" / f"{task_id}.json").exists()


def test_retired_workflow_contract_is_refused_but_a_new_run_can_start(tmp_path):
    project = tmp_path / "legacy"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    workflow = Workflow(project)
    workflow.start()
    old_run = workflow.run_dir
    for version in (None, 2):
        if version is None:
            workflow.state.pop("workflow_contract_version", None)
        else:
            workflow.state["workflow_contract_version"] = version
        workflow._save()
        with pytest.raises(ValueError, match="retired workflow contract"):
            Workflow(project)
    fresh = Workflow(project, new=True)
    assert advance(fresh)["status"] == "completed"
    assert fresh.run_dir != old_run and (old_run / "state.json").is_file()


def test_repeated_author_revision_keeps_actual_prior_rejection(completed_project):
    workflow = Workflow(completed_project)
    workflow.revise("proposal_review", "Synthetic reviewer correction")
    summary = advance(workflow, stop="proposal_review")
    task_id = summary["pending"][0]["task_id"]
    directory = workflow.run_dir / "requests" / task_id
    data = answer(read_json(directory / "request.json"), completed_project)
    data["accepted"] = False
    data.setdefault("decision_assessment", {})["agree"] = False
    data["blocking_issues"] = ["SYNTHETIC_REJECTION_REQUIRING_RESPONSE"]
    write_json(directory / "response.json", data)
    workflow.submit(task_id, directory / "response.json")
    workflow.run()
    workflow.revise("hypothesis", "First author response")
    advance(workflow, stop="challenge")
    workflow.revise("hypothesis", "Correct the author response before a new review")
    summary = advance(workflow, stop="hypothesis")
    request = read_json(workflow.run_dir / "requests" / summary["pending"][0]["task_id"] / "request.json")
    reviews = request["context"]["revision_context"]["proposal_reviews"]
    assert reviews[0]["task_id"] == task_id
    assert reviews[0]["data"]["blocking_issues"] == data["blocking_issues"]
