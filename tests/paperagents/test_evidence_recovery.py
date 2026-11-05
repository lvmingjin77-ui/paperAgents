"""Offline checkpoint regression tests; no model, network or experiments."""

import pytest

from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow
from tests.paperagents.test_workflow import project
from tests.paperagents.test_discussion_loop import drive


def stopped_review(project):
    workflow = Workflow(project)
    # Reproduce a checkpoint created before evidence continuation was supported.
    workflow.config["discussion"]["max_evidence_rounds"] = 0

    def request_materials(request, data):
        if request["stage"] == "synthesis":
            data.update(decision="needs_evidence", next_action="gather_materials",
                        unresolved_questions=["Check annotations", "Check sample independence"])
        return data

    assert drive(workflow, request_materials)["status"] == "needs_evidence"
    return workflow


def submit_evidence(workflow, task, *, outcome="resolved", changes=()):
    folder = workflow.run_dir / "requests" / task["task_id"]
    request = read_json(folder / "request.json")
    response = folder / "response.json"
    write_json(response, {
        "issue_id": request["context"]["issue"]["issue_id"],
        "affected_idea_ids": [request["context"]["candidates"][0]["idea_id"]],
        "outcome": outcome, "changes": list(changes), "finding": "SYNTHETIC_TEST_FIXTURE",
        "evidence": ["Synthetic evidence, not a scientific result"], "limitations": [],
        "next_step": "Independently verify the fixture report",
    })
    workflow.submit(task["task_id"], response)


def test_old_checkpoint_and_partial_evidence_resume_without_repeating_prior_tasks(project):
    old = stopped_review(project)
    accepted = {tid: task["artifact_hash"] for tid, task in old.state["tasks"].items()}
    workflow = Workflow(project)
    first = workflow.run()
    assert first["phase"] == "evidence"
    assert len(first["pending"]) == 2
    submit_evidence(workflow, first["pending"][0])

    resumed = Workflow(project)
    remaining = resumed.run()
    assert [t["task_id"] for t in remaining["pending"]] == [first["pending"][1]["task_id"]]
    submit_evidence(resumed, remaining["pending"][0])
    result = resumed.run()
    assert result["phase"] == "synthesis"
    for tid, expected in accepted.items():
        assert resumed.state["tasks"][tid]["artifact_hash"] == expected
    request = read_json(resumed.run_dir / "requests" / result["pending"][0]["task_id"] / "request.json")
    assert len(request["context"]["evidence_reports"]) == 2
    assert request["context"]["revision_context"]["proposal_reviews"]


@pytest.mark.parametrize("outcome,changes,phase", [
    ("premise_fails", [], "hypothesis"),
    ("resolved", ["data"], "hypothesis"),
    ("needs_human", [], "synthesis"),  # A local resource gap is not a global veto.
    ("needs_experiment", [], "synthesis"),  # Must still pass independent review.
])
def test_reports_return_to_authors_or_review_not_directly_to_experiments(project, outcome, changes, phase):
    stopped_review(project)
    workflow = Workflow(project)
    for task in workflow.run()["pending"]:
        submit_evidence(workflow, task, outcome=outcome, changes=changes)
    summary = workflow.run()
    assert summary["phase"] == phase
    assert summary["status"] == "awaiting_workers"
    assert not (workflow.run_dir / "experiments").exists()
    assert len(workflow.state["batches"]["reading"]) > 0


def test_zero_evidence_budget_leaves_checkpoint_stopped(project):
    workflow = stopped_review(project)
    assert workflow.run()["status"] == "needs_evidence"
    assert not any(t["stage"] == "evidence" for t in workflow.state["tasks"].values())
