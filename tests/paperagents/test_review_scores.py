"""Score visibility and provenance using synthetic reviews, not scientific results."""

from copy import deepcopy
from pathlib import Path

import pytest

from paperagents.cli import main
from paperagents.contracts import REVIEW_DIMENSIONS
from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow, initialize_project
from tests.paperagents.test_workflow import advance, answer


@pytest.fixture
def review_run(tmp_path):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    workflow = Workflow(project)
    summary = advance(workflow, stop="proposal_review")
    task_id = summary["pending"][0]["task_id"]
    directory = workflow.run_dir / "requests" / task_id
    request = read_json(directory / "request.json")
    return workflow, task_id, directory, request, answer(request, project)


def submit_review(workflow, task_id, directory, data):
    write_json(directory / "response.json", data)
    workflow.submit(task_id, directory / "response.json")


def test_scores_visible_in_status_and_cli_without_choosing_by_score(review_run, capsys):
    workflow, task_id, directory, request, data = review_run
    for item in data["candidate_scores"][0]["dimensions"].values():
        item["score"] = 1
    for item in data["candidate_scores"][1]["dimensions"].values():
        item["score"] = 5
    data["proposal_score"]["dimensions"]["feasibility"] = {
        "status": "unknown", "score": None,
        "rationale": "Synthetic nonblocking uncertainty; planned experiment will measure it.",
        "evidence": [],
    }
    submit_review(workflow, task_id, directory, data)
    summary = workflow.run()
    assert summary["status"] == "completed"
    assert workflow.one("synthesis")["selected_idea_id"] == data["candidate_scores"][0]["idea_id"]
    assert summary["review_summary"]["proposal_score"]["dimensions"]["feasibility"] is None
    assert read_json(Path(summary["review_artifact"])) == data
    assert main(["review", str(workflow.project)]) == 0
    report = capsys.readouterr().out
    assert "本轮裁决：**通过" in report
    assert "未知" in report
    assert data["proposal_score"]["dimensions"]["feasibility"]["rationale"] in report
    assert "SYNTHETIC_TEST_FIXTURE: section 1" in report.replace("\\_", "_")
    for label in REVIEW_DIMENSIONS.values():
        assert label in report
    assert report.index("domain-idea：") < report.index("paper:p0-idea：")
    assert main(["status", str(workflow.project)]) == 0
    assert '"scoring_status": "available"' in capsys.readouterr().out


@pytest.mark.parametrize("change,match", [
    ("missing", "every candidate"),
    ("unknown", "every candidate"),
    ("candidate_version", "different candidate version"),
    ("proposal_version", "different proposal version"),
])
def test_missing_or_stale_scores_cannot_be_committed(review_run, change, match):
    workflow, task_id, directory, _, data = review_run
    if change == "missing":
        data["candidate_scores"].pop()
    elif change == "unknown":
        data["candidate_scores"][0]["idea_id"] = "not-a-candidate"
    elif change == "candidate_version":
        data["candidate_scores"][0]["candidate_hash"] = "0" * 64
    else:
        data["proposal_score"]["proposal_hash"] = "0" * 64
    with pytest.raises(ValueError, match=match):
        submit_review(workflow, task_id, directory, data)
    assert workflow.state["tasks"][task_id]["status"] == "pending"
    assert not (workflow.run_dir / "artifacts" / f"{task_id}.json").exists()


def test_high_scores_do_not_bypass_rejection_and_revision_hides_old_scores(review_run, capsys):
    workflow, task_id, directory, _, data = review_run
    for record in [*data["candidate_scores"], data["proposal_score"]]:
        for item in record["dimensions"].values():
            item["score"] = 5
    data["accepted"] = False
    data.setdefault("decision_assessment", {})["agree"] = False
    data["checks"][0]["verdict"] = "fail"
    data["blocking_issues"] = ["Synthetic fatal protocol mismatch"]
    submit_review(workflow, task_id, directory, data)
    summary = workflow.run()
    assert summary["status"] == "needs_evidence"
    assert summary["review_summary"]["accepted"] is False
    assert "5/5" in workflow.review_report()
    assert "Synthetic fatal protocol mismatch" in workflow.review_report()
    assert main(["v3", str(workflow.project), "--execute"]) == 1
    assert "reviewed, exported proposal" in capsys.readouterr().err
    old_artifact = read_json(Path(summary["review_artifact"]))
    workflow.revise("hypothesis", "Synthetic new evidence")
    assert "review_summary" not in workflow.summary()
    assert "尚未产生" in workflow.review_report()
    assert read_json(Path(summary["review_artifact"])) == old_artifact


def test_pending_review_and_cli_schema_match_the_dispatched_request(review_run, capsys):
    workflow, _, _, request, data = review_run
    assert main(["review", str(workflow.project)]) == 0
    assert "尚未产生" in capsys.readouterr().out
    assert main(["schema", "proposal_review"]) == 0
    import json
    schema = json.loads(capsys.readouterr().out)
    assert schema == request["output_schema"]
    invalid = deepcopy(data)
    del invalid["proposal_score"]
    path = workflow.project / "invalid-review.json"
    write_json(path, invalid)
    assert main(["validate", "proposal_review", str(path)]) == 1
    assert "proposal_score" in capsys.readouterr().err
