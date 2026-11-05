"""Discussion loop (workflow contract v3) with synthetic fixtures only; no scientific evidence."""

from copy import deepcopy

import pytest

from paperagents.cli import main
from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow
from tests.paperagents.test_workflow import answer, project  # noqa: F401  (fixture)

SOURCE = ["SYNTHETIC_TEST_FIXTURE: section 1"]


def objection(oid, blocking=True):
    return {"objection_id": oid, "claim": "Fixture claim", "objection": f"Fixture objection {oid}",
            "evidence": SOURCE, "blocking": blocking, "resolution_test": "Fixture control"}


def revised(idea_id, parents, base):
    item = deepcopy(base)
    for key in ("proposed_by", "introduced_round"):
        item.pop(key, None)
    item.update(idea_id=idea_id, parent_ids=parents, change_summary="Fixture revision",
                mechanism=f"Revised mechanism for {idea_id}")
    return item


def drive(workflow, respond=None, *, stop=None, limit=200):
    """Answer every pending request; respond(request, default) may replace the default answer."""
    for _ in range(limit):
        summary = workflow.run()
        if summary["status"] != "awaiting_workers" or summary["phase"] == stop:
            return summary
        for task in summary["pending"]:
            directory = workflow.run_dir / "requests" / task["task_id"]
            request = read_json(directory / "request.json")
            data = answer(request, workflow.project)
            if respond:
                data = respond(request, data)
            write_json(directory / "response.json", data)
            workflow.submit(task["task_id"], directory / "response.json")
    raise AssertionError("workflow did not settle")


def requests_for(workflow, stage):
    return [read_json(path) for path in sorted((workflow.run_dir / "requests").glob(f"*/request.json"))
            if read_json(path)["stage"] == stage]


def test_revision_answers_objection_and_superseded_version_leaves_the_shortlist(project):
    def respond(request, data):
        stage, context = request["stage"], request["context"]
        if stage == "challenge" and context["expected_expert_id"] == "domain":
            review = next(r for r in data["reviews"] if r["idea_id"] == "paper:p0-idea")
            review["objections"] = [objection("domain/1")]
        if stage == "rebuttal":
            assert [o["objection_id"] for o in context["objections"]] == ["domain/1"]
            base = context["own_candidates"][0]
            data = {"expert_id": "paper:p0", "responses": [{
                "objection_id": "domain/1", "action": "revise", "argument": "Added the missing control",
                "evidence": SOURCE, "revised_idea_id": "paper:p0-idea-v2"}],
                "revised_candidates": [revised("paper:p0-idea-v2", ["paper:p0-idea"], base)],
                "withdrawn_idea_ids": []}
        if stage == "recheck":
            judged = [o["objection_id"] for o in context["objections_to_judge"]]
            data = {"expert_id": context["expected_expert_id"],
                    "verdicts": [{"objection_id": oid, "status": "resolved", "reason": "Control added",
                                  "evidence": SOURCE} for oid in judged],
                    "new_reviews": [dict(t, objections=[]) for t in context["new_targets"]]}
        if stage == "synthesis":
            assert "paper:p0-idea" not in {c["idea_id"] for c in context["candidates"]}
        return data

    workflow = Workflow(project)
    summary = drive(workflow, respond)
    assert summary["status"] == "completed"
    rebuttals = requests_for(workflow, "rebuttal")
    assert [r["subject_id"] for r in rebuttals] == ["paper:p0"]  # only the author with objections answers
    rechecks = {r["subject_id"]: r["context"] for r in requests_for(workflow, "recheck")}
    assert [o["objection_id"] for o in rechecks["domain"]["objections_to_judge"]] == ["domain/1"]
    assert "paper:p0" not in rechecks  # authors do not review their own revision
    assert rechecks["paper:p1"]["objections_to_judge"] == []
    novelty = requests_for(workflow, "novelty")[0]["context"]
    ids = {c["idea_id"] for c in novelty["candidates"]}
    assert "paper:p0-idea-v2" in ids and "paper:p0-idea" not in ids
    ledger = read_json(workflow.run_dir / "debate" / "ledger.json")
    assert ledger["objections"][0]["status"] == "resolved"
    assert ledger["objections"][0]["current_idea_id"] == "paper:p0-idea-v2"
    assert (workflow.run_dir / "debate" / "ledger.md").read_text().count("`domain/1`") == 1


def test_unresolved_blocking_objection_loops_then_blocks_ready_and_auto_revises(project):
    state = {"rounds": []}

    def respond(request, data):
        stage, context = request["stage"], request["context"]
        if stage == "challenge" and context["expected_expert_id"] in {"domain", "paper:p1"}:
            prefix = context["objection_id_prefix"]
            for review in data["reviews"]:
                if review["idea_id"] == "paper:p0-idea":
                    review["objections"] = [objection(prefix + "1")]
        if stage == "rebuttal":
            state["rounds"].append(context["debate_round"])
            data = {"expert_id": context["expected_expert_id"], "responses": [
                {"objection_id": o["objection_id"], "action": "rebut", "argument": "Fixture rebuttal",
                 "evidence": SOURCE, "revised_idea_id": None} for o in context["objections"]],
                "revised_candidates": [], "withdrawn_idea_ids": []}
        if stage == "recheck":
            own = [o["objection_id"] for o in context["objections_to_judge"]]
            assert all(oid.startswith(context["expected_expert_id"] + "/") for oid in own)
            data = {"expert_id": context["expected_expert_id"],
                    "verdicts": [{"objection_id": oid, "status": "unresolved", "reason": "Still missing",
                                  "evidence": SOURCE} for oid in own], "new_reviews": []}
        if stage == "synthesis" and request["context"]["debate_ledger"]["open_blocking"]:
            data = {"decision": "needs_evidence", "selected_idea_id": None, "proposal": {},
                    "alternatives": [], "next_action": "revise_candidates",
                    "unresolved_questions": [{"question": "domain/1 unresolved", "blocking": True}]}
        return data

    workflow = Workflow(project)
    # A ready selection of the objected candidate is rejected by the coordinator.
    drive(workflow, respond, stop="synthesis")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    request = read_json(directory / "request.json")
    assert {o["idea_id"] for o in request["context"]["debate_ledger"]["open_blocking"]} == {"paper:p0-idea"}
    bad = answer(request, project)
    bad.update(selected_idea_id="paper:p0-idea", candidate_ref=next(
        t for t in request["context"]["candidate_targets"] if t["idea_id"] == "paper:p0-idea"))
    for field in ("problem", "hypothesis", "mechanism", "assumptions", "falsification"):
        bad["proposal"][field] = next(c for c in request["context"]["candidates"]
                                      if c["idea_id"] == "paper:p0-idea")[field]
    write_json(directory / "response.json", bad)
    with pytest.raises(ValueError, match="open blocking objections"):
        workflow.submit(task["task_id"], directory / "response.json")
    (directory / "response.json").rename(directory / "rejected.json")

    summary = drive(workflow, respond)
    assert state["rounds"][:2] == [1, 2]  # second round, then stopped at max_rounds=2
    assert workflow.state["auto_revisions"] == 1
    assert workflow.state["iteration"] == 2
    revision = workflow.state["revisions"][-1]
    assert revision["from_phase"] == "hypothesis" and "independent review agreed" in revision["reason"]
    second = [r for r in requests_for(workflow, "hypothesis") if r["task_id"].startswith("r002")
              and r["subject_id"] == "paper:p0"][0]
    discussion = second["context"]["revision_context"]["discussion"]
    assert {o["objection_id"] for o in discussion["objections"]} == {"domain/1", "paper:p1/1"}
    # Second iteration raised the same objections; the auto-revision budget is spent, so it stops.
    assert summary["status"] == "needs_evidence"
    assert "confirmed by independent review" in summary["reason"]


def test_reviewer_can_dispute_a_no_selection_decision(project):
    def respond(request, data):
        if request["stage"] == "synthesis":
            return {"decision": "no_viable_idea", "selected_idea_id": None, "proposal": {},
                    "alternatives": [], "unresolved_questions": [], "next_action": "stop"}
        if request["stage"] == "proposal_review":
            data["accepted"] = False
            data.setdefault("decision_assessment", {})["agree"] = False
            data["decision_assessment"] = {"synthesis_decision": "no_viable_idea", "agree": False,
                                           "reason": "paper:p2-idea was dismissed without evidence"}
        return data

    workflow = Workflow(project)
    summary = drive(workflow, respond)
    assert summary["status"] == "needs_evidence"
    assert "disputes the synthesis decision" in summary["reason"]
    assert "proposal_review" in workflow.state["batches"]  # non-selection was reviewed, not skipped
    report = workflow.review_report()
    assert "不同意" in report and "未选择提案" in report


def test_merge_issue_invites_author_and_keeps_other_parent_active(project):
    def respond(request, data):
        stage, context = request["stage"], request["context"]
        if stage == "agenda":
            data["issues"] = [{"issue_id": "m1", "kind": "merge_opportunity",
                               "idea_ids": ["paper:p1-idea", "paper:p2-idea"], "question": "Combine?",
                               "assigned_expert_ids": ["paper:p1"]}]
        if stage == "rebuttal":
            assert context["merge_issues"][0]["issue_id"] == "m1"
            base = context["own_candidates"][0]
            data = {"expert_id": "paper:p1", "responses": [], "withdrawn_idea_ids": [],
                    "revised_candidates": [revised("paper:p1-merge", ["paper:p1-idea", "paper:p2-idea"], base)]}
        if stage == "recheck":
            data = {"expert_id": context["expected_expert_id"], "verdicts": [],
                    "new_reviews": [dict(t, objections=[]) for t in context["new_targets"]]}
        return data

    workflow = Workflow(project)
    assert drive(workflow, respond)["status"] == "completed"
    novelty = requests_for(workflow, "novelty")[0]["context"]
    ids = {c["idea_id"] for c in novelty["candidates"]}
    assert {"paper:p1-merge", "paper:p2-idea"} <= ids and "paper:p1-idea" not in ids
    assert {r["subject_id"] for r in requests_for(workflow, "recheck")} == {
        "domain", "paper:p0", "paper:p2", "statistics"}


@pytest.mark.parametrize("mutation,message", [
    ("missing_response", "rebuttal responses"),
    ("revise_without_candidate", "submitted revision"),
    ("withdraw_other", "your own active candidates"),
])
def test_rebuttal_relationships_are_enforced(project, mutation, message):
    def respond(request, data):
        if request["stage"] == "challenge" and request["context"]["expected_expert_id"] == "domain":
            for review in data["reviews"]:
                if review["idea_id"] == "paper:p0-idea":
                    review["objections"] = [objection("domain/1"), objection("domain/2", blocking=False)]
        return data

    workflow = Workflow(project)
    drive(workflow, respond, stop="rebuttal")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    responses = [{"objection_id": oid, "action": "rebut", "argument": "x", "evidence": SOURCE,
                  "revised_idea_id": None} for oid in ("domain/1", "domain/2")]
    data = {"expert_id": "paper:p0", "responses": responses, "revised_candidates": [], "withdrawn_idea_ids": []}
    if mutation == "missing_response":
        data["responses"] = responses[:1]
    elif mutation == "revise_without_candidate":
        responses[0].update(action="revise", revised_idea_id="paper:p0-new")
    else:
        responses[0]["action"] = "withdraw"
        data["withdrawn_idea_ids"] = ["paper:p1-idea"]
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match=message):
        workflow.submit(task["task_id"], directory / "response.json")


def test_objection_ids_need_the_challenger_prefix(project):
    workflow = Workflow(project)
    drive(workflow, stop="challenge")
    task = next(t for t in workflow.summary()["pending"] if t["subject_id"] == "domain")
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["reviews"][0]["objections"] = [objection("someone-else/1")]
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="start with the challenger"):
        workflow.submit(task["task_id"], directory / "response.json")


def test_notebook_carries_an_experts_own_notes_across_stages(project):
    def respond(request, data):
        if request["stage"] == "hypothesis" and request["context"]["expected_expert_id"] == "paper:p0":
            data["notebook"] = ["Considered a second mechanism; dropped for lack of a control."]
        return data

    workflow = Workflow(project)
    drive(workflow, respond, stop="challenge")
    challenge = next(r for r in requests_for(workflow, "challenge") if r["subject_id"] == "paper:p0")
    notebook = challenge["context"]["expert_notebook"]
    assert notebook["exists"]
    assert "second mechanism" in open(notebook["path"], encoding="utf-8").read()
    other = next(r for r in requests_for(workflow, "challenge") if r["subject_id"] == "paper:p1")
    assert not other["context"]["expert_notebook"]["exists"]


def test_core_paper_count_and_discussion_limits_are_configurable(project):
    config = project / "paperagents.toml"
    config.write_text(config.read_text().replace("max_rounds = 2", "max_rounds = 9"))
    with pytest.raises(ValueError, match="max_rounds"):
        Workflow(project)
    config.write_text(config.read_text().replace("max_rounds = 9", "max_rounds = 1")
                      .replace("core_papers = 3", "core_papers = 2"))
    workflow = Workflow(project)
    with pytest.raises(ValueError, match="exactly 2 core papers"):  # the fixture selects three papers
        drive(workflow)
    assert workflow.summary()["phase"] == "selection"
    assert main(["plan", str(project)]) == 0
