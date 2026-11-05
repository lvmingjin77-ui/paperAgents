"""Skill routing and history integrity, using only synthetic research fixtures."""

from pathlib import Path

import pytest

from paperagents.storage import digest, read_json, write_json
from paperagents.workflow import Workflow, initialize_project
from tests.paperagents.test_workflow import advance, answer


@pytest.fixture
def workflow(tmp_path):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    return Workflow(project)


def requests(workflow):
    return [read_json(workflow.run_dir / "requests" / task["task_id"] / "request.json")
            for task in workflow.summary()["pending"]]


def test_reuse_discovery_is_identity_scoped_and_does_not_skip_review(workflow):
    advance(workflow, stop="domain")
    first = requests(workflow)[0]
    assert first["context"]["reuse_candidates"] == []
    assert "reuse-and-update-expert" not in {skill["id"] for skill in first["skills"]}
    advance(workflow, stop="hypothesis")
    old_paths = {expert["expert_id"]: str(Path(expert["_asset"]["path"]) / "asset.json")
                 for expert in workflow.experts()}
    workflow.revise("domain", "Reassess existing fixture knowledge")
    workflow.run()
    domain = requests(workflow)[0]
    assert domain["context"]["reuse_candidates"] == [old_paths["domain"]]
    assert domain["skills"][0]["id"] == "reuse-and-update-expert"
    advance(workflow, stop="paper")
    for request in requests(workflow):
        if request["stage"] != "paper":
            continue
        assert request["context"]["reuse_candidates"] == [old_paths[request["subject_id"]]]
        assert request["skills"][0]["id"] == "reuse-and-update-expert"
        assert "analyze-paper-communication" not in {skill["id"] for skill in request["skills"]}
    assert advance(workflow, stop="expert_review")["status"] == "awaiting_workers"


def test_revision_receipts_are_real_filtered_and_changed_ideas_need_new_ids(workflow):
    advance(workflow)
    workflow.revise("hypothesis", "Reconsider the fixture mechanism")
    workflow.run()
    for request in requests(workflow):
        context = request["context"]
        assert "candidates" not in context  # No peer proposals are injected.
        revision = context["revision_context"]
        previous = revision["previous_hypotheses"]
        assert all(record["data"]["expert_id"] == request["subject_id"] for record in previous)
        own_ids = {item["idea_id"] for record in previous for item in record["data"]["candidates"]}
        for record in previous + revision["challenges"] + revision["novelty"]:
            assert digest(read_json(Path(record["artifact_path"]))) == record["artifact_hash"]
        for record in revision["challenges"] + revision["novelty"]:
            assert {item["idea_id"] for item in record["reviews"]} <= own_ids
        assert "revise-hypotheses" in {skill["id"] for skill in request["skills"]}

    request = requests(workflow)[0]
    data = answer(request, workflow.project)
    data["candidates"][0]["mechanism"] = "Changed fixture mechanism"
    response = Path(request["output_path"])
    write_json(response, data)
    with pytest.raises(ValueError, match="new idea_id"):
        workflow.submit(request["task_id"], response)
    data["candidates"][0]["idea_id"] += "-r2"
    write_json(response, data)
    workflow.submit(request["task_id"], response)

    next_request = requests(workflow)[0]
    data = answer(next_request, workflow.project)
    data["candidates"][0]["idea_id"] = request["subject_id"] + "-idea"
    response = Path(next_request["output_path"])
    write_json(response, data)
    with pytest.raises(ValueError, match="another expert's historical idea_id"):
        workflow.submit(next_request["task_id"], response)


def test_restarting_unsubmitted_hypotheses_does_not_invent_revision_inputs(workflow):
    advance(workflow, stop="hypothesis")
    workflow.revise("hypothesis", "Restart pending work")
    workflow.run()
    for request in requests(workflow):
        assert "revision_context" not in request["context"]
        assert "revise-hypotheses" not in {skill["id"] for skill in request["skills"]}


def test_communication_and_reuse_views_are_frozen_without_inventing_content(workflow):
    advance(workflow, stop="paper")
    request = next(item for item in requests(workflow) if item["stage"] == "paper")
    data = answer(request, workflow.project)
    data["knowledge"]["communication_analysis"] = {
        "status": "unknown", "writing_structure": [], "display_patterns": [], "transfer_recipes": [],
        "limitations": ["Synthetic fixture contains no substantive paper content"],
    }
    data["knowledge"]["reuse_assessment"] = {
        "assessment_version": 1, "decision": "no_candidate", "reason": "Synthetic fresh project",
    }
    response = Path(request["output_path"])
    write_json(response, data)
    workflow.submit(request["task_id"], response)
    accepted = workflow._artifact(workflow.state["tasks"][request["task_id"]])
    folder = Path(accepted["_asset"]["path"]) / "knowledge"
    for field, name in (("communication_analysis", "communication-analysis.json"),
                        ("reuse_assessment", "reuse-assessment.json")):
        assert read_json(folder / name) == data["knowledge"][field]
        assert name in (folder / "index.md").read_text()
    Workflow(workflow.project)
    write_json(folder / "communication-analysis.json", {"tampered": True})
    with pytest.raises(ValueError, match="Immutable asset source changed"):
        Workflow(workflow.project)
