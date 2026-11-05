"""Regressions for the closed discussion loop and the structured domain expert (synthetic fixtures only)."""

from pathlib import Path

import pytest

from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow
from tests.paperagents.test_discussion_loop import SOURCE, drive, objection, requests_for, revised
from tests.paperagents.test_workflow import answer, project  # noqa: F401  (fixture)


def challenge_on(target, oid_suffix="1", blocking=True, by="domain"):
    def respond(request, data):
        context = request["context"]
        if request["stage"] == "challenge" and context["expected_expert_id"] == by:
            for review in data["reviews"]:
                if review["idea_id"] == target:
                    review["objections"] = [objection(f"{by}/{oid_suffix}", blocking)]
        return data
    return respond


def submit_pending(workflow, subject, data):
    task = next(t for t in workflow.summary()["pending"] if t["subject_id"] == subject)
    directory = workflow.run_dir / "requests" / task["task_id"]
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    return read_json(directory / "request.json")


def test_a_candidate_cannot_fork_into_two_successors(project):
    workflow = Workflow(project)
    drive(workflow, challenge_on("paper:p0-idea"), stop="rebuttal")
    request = read_json(workflow.run_dir / "requests" / workflow.summary()["pending"][0]["task_id"] / "request.json")
    base = request["context"]["own_candidates"][0]
    data = {"expert_id": "paper:p0", "withdrawn_idea_ids": [],
            "responses": [{"objection_id": "domain/1", "action": "revise", "argument": "x", "evidence": SOURCE,
                           "revised_idea_id": "paper:p0-a"}],
            "revised_candidates": [revised("paper:p0-a", ["paper:p0-idea"], base),
                                   revised("paper:p0-b", ["paper:p0-idea"], base)]}
    with pytest.raises(ValueError, match="only one successor"):
        submit_pending(workflow, "paper:p0", data)


def test_merge_is_checked_against_dispatched_versions_not_submission_order(project):
    def respond(request, data):
        data = challenge_on("paper:p1-idea")(request, data)
        if request["stage"] == "agenda":
            data["issues"] = [{"issue_id": "m1", "kind": "merge_opportunity", "question": "Combine?",
                               "idea_ids": ["paper:p1-idea", "paper:p2-idea"], "assigned_expert_ids": ["paper:p2"]}]
        return data

    workflow = Workflow(project)
    drive(workflow, respond, stop="rebuttal")
    p1 = read_json(workflow.run_dir / "requests" / next(t for t in workflow.summary()["pending"]
                                                         if t["subject_id"] == "paper:p1")["task_id"] / "request.json")
    base = p1["context"]["own_candidates"][0]
    submit_pending(workflow, "paper:p1", {
        "expert_id": "paper:p1", "withdrawn_idea_ids": [],
        "responses": [{"objection_id": "domain/1", "action": "revise", "argument": "x", "evidence": SOURCE,
                       "revised_idea_id": "paper:p1-v2"}],
        "revised_candidates": [revised("paper:p1-v2", ["paper:p1-idea"], base)]})
    p2 = read_json(workflow.run_dir / "requests" / next(t for t in workflow.summary()["pending"]
                                                         if t["subject_id"] == "paper:p2")["task_id"] / "request.json")
    # paper:p1-idea is no longer active, but it was the version dispatched to paper:p2.
    submit_pending(workflow, "paper:p2", {
        "expert_id": "paper:p2", "responses": [], "withdrawn_idea_ids": [],
        "revised_candidates": [revised("paper:p2-merge", ["paper:p2-idea", "paper:p1-idea"],
                                       p2["context"]["own_candidates"][0])]})
    active = {item["idea_id"] for item in workflow.candidates()}
    assert {"paper:p1-v2", "paper:p2-merge"} <= active and "paper:p1-idea" not in active


def test_withdrawing_every_candidate_still_reaches_a_reviewed_decision(project):
    def respond(request, data):
        stage, context = request["stage"], request["context"]
        if stage == "challenge":
            prefix = context["objection_id_prefix"]
            for review in data["reviews"]:
                review["objections"] = [objection(f"{prefix}{review['idea_id']}")]
        if stage == "rebuttal":
            data = {"expert_id": context["expected_expert_id"], "revised_candidates": [],
                    "withdrawn_idea_ids": [c["idea_id"] for c in context["own_candidates"]],
                    "responses": [{"objection_id": o["objection_id"], "action": "withdraw", "argument": "fatal",
                                   "evidence": SOURCE, "revised_idea_id": None} for o in context["objections"]]}
        if stage == "synthesis":
            assert context["candidates"] == []
            data = {"decision": "no_viable_idea", "selected_idea_id": None, "proposal": {}, "alternatives": [],
                    "unresolved_questions": [], "next_action": "stop"}
        if stage == "proposal_review":
            assert data["candidate_scores"] == []
        return data

    summary = drive(Workflow(project), respond)
    assert summary["status"] == "needs_evidence" and "confirmed by independent review" in summary["reason"]


def test_ready_review_cannot_accept_while_disagreeing(project):
    workflow = Workflow(project)
    drive(workflow, stop="proposal_review")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["decision_assessment"]["agree"] = False
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="must agree"):
        workflow.submit(task["task_id"], directory / "response.json")


def test_revising_from_recheck_restarts_the_whole_discussion(project):
    workflow = Workflow(project)
    drive(workflow, challenge_on("paper:p0-idea"))
    assert any(key.startswith("rebuttal.") for key in workflow.state["batches"])
    workflow.revise("recheck", "Recheck evidence was wrong")
    assert not any(key.startswith(("rebuttal.", "recheck.")) for key in workflow.state["batches"])
    assert workflow.state["debate_round"] == 0
    assert workflow.run()["phase"] == "rebuttal"


def test_revised_ids_from_earlier_rounds_cannot_be_reused_with_new_content(project):
    def respond(request, data):
        data = challenge_on("paper:p0-idea")(request, data)
        context = request["context"]
        if request["stage"] == "rebuttal":
            base = context["own_candidates"][0]
            data = {"expert_id": "paper:p0", "withdrawn_idea_ids": [],
                    "responses": [{"objection_id": "domain/1", "action": "revise", "argument": "x",
                                   "evidence": SOURCE, "revised_idea_id": "paper:p0-v2"}],
                    "revised_candidates": [revised("paper:p0-v2", ["paper:p0-idea"], base)]}
        return data

    workflow = Workflow(project)
    drive(workflow, respond)
    workflow.revise("hypothesis", "Start over")
    drive(workflow, stop="hypothesis")
    task = next(t for t in workflow.summary()["pending"] if t["subject_id"] == "paper:p0")
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["candidates"][0].update(idea_id="paper:p0-v2", mechanism="Something else entirely")
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="new idea_id"):
        workflow.submit(task["task_id"], directory / "response.json")


def test_notes_stay_private_and_agenda_issues_must_be_answered(project):
    def respond(request, data):
        stage = request["stage"]
        if stage == "agenda":
            data["notebook"] = ["PRIVATE_MODERATOR_NOTE"]
            data["issues"] = [{"issue_id": "q1", "kind": "value_question", "idea_ids": ["paper:p0-idea"],
                               "question": "Is this worth doing?", "assigned_expert_ids": ["paper:p1"]}]
        return data

    workflow = Workflow(project)
    drive(workflow, respond, stop="challenge")
    challenge = next(r for r in requests_for(workflow, "challenge") if r["subject_id"] == "paper:p1")
    assert "PRIVATE_MODERATOR_NOTE" not in str(challenge["context"])
    agenda_task = next(t for t in workflow.state["tasks"].values() if t["stage"] == "agenda")
    assert "notebook" not in workflow._artifact(agenda_task)
    assert "PRIVATE_MODERATOR_NOTE" in Path(workflow._notebook("domain")["path"]).read_text()
    assert challenge["context"]["assigned_issue_ids"] == ["q1"]
    data = answer(challenge, project)
    data["issue_responses"] = []
    with pytest.raises(ValueError, match="agenda issues"):
        submit_pending(workflow, "paper:p1", data)


def test_reading_cards_compile_into_a_graph_and_the_landscape_must_cite_read_papers(project):
    workflow = Workflow(project)
    drive(workflow, stop="domain")
    request = read_json(workflow.run_dir / "requests" / workflow.summary()["pending"][0]["task_id"] / "request.json")
    graph = read_json(Path(request["context"]["domain_graph"]["graph"]))
    assert set(graph["papers"]) == {"p0", "p1", "p2"}
    assert graph["problems"]["fixture problem"]["paper_ids"] == ["p0", "p1", "p2"]
    assert len(list(Path(request["context"]["domain_graph"]["problems_dir"]).glob("*.md"))) == 1
    assert list((project / "library" / "readings").glob("*/*/asset.json"))
    data = answer(request, project)
    data["knowledge"]["landscape"]["contested"] = [{"claim": "x", "supporting": ["p0"], "opposing": ["p9"],
                                                    "note": "unread paper"}]
    with pytest.raises(ValueError, match="without a reading record"):
        submit_pending(workflow, "domain", data)
    reading = next(t for t in workflow.state["tasks"].values() if t["stage"] == "reading")
    assert all("trace_id" in item for item in workflow._artifact(reading)["idea_trace"])


def test_reading_requires_unique_trace_ids(project):
    workflow = Workflow(project)
    drive(workflow, stop="reading")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["idea_trace"] = data["idea_trace"] * 2
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="duplicate trace_id"):
        workflow.submit(task["task_id"], directory / "response.json")


def test_corpus_screening_reports_every_problem_and_links_versions(project):
    workflow = Workflow(project)
    drive(workflow, stop="corpus")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    start = workflow.state["search_window"]["start"]
    data["papers"][0]["venue_id"] = "OtherConf"
    data["papers"][1]["pub_date"] = f"{int(start[:4]) - 1}-01-01"
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError) as error:
        workflow.submit(task["task_id"], directory / "response.json")
    assert "p0: venue_id 'OtherConf'" in str(error.value) and "p1:" in str(error.value)
    data = answer(read_json(directory / "request.json"), project)
    extra = dict(data["papers"][2], paper_id="p2-v2", arxiv_id="2401.00001v2")
    data["papers"][2]["arxiv_id"] = "2401.00001v1"
    data["papers"].append(extra)
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    assert {p["paper_id"] for p in workflow._to_read()} == {"p0", "p1", "p2"}
    view = {p["paper_id"]: p for p in workflow.corpus_view()["papers"]}
    assert view["p2-v2"]["version_of"] == "p2" and view["p2-v2"]["full_text_path"]


def test_recheck_lists_only_assigned_candidates_names_extras_and_can_be_retried(project):
    def respond(request, data):
        data = challenge_on("paper:p0-idea")(request, data)
        if request["stage"] == "rebuttal":
            base = request["context"]["own_candidates"][0]
            data = {"expert_id": "paper:p0", "withdrawn_idea_ids": [],
                    "responses": [{"objection_id": "domain/1", "action": "revise", "argument": "x",
                                   "evidence": SOURCE, "revised_idea_id": "paper:p0-v2"}],
                    "revised_candidates": [revised("paper:p0-v2", ["paper:p0-idea"], base)]}
        return data

    workflow = Workflow(project)
    drive(workflow, respond, stop="recheck")
    task = next(t for t in workflow.summary()["pending"] if t["subject_id"] == "paper:p1")
    directory = workflow.run_dir / "requests" / task["task_id"]
    request = read_json(directory / "request.json")
    assert [c["idea_id"] for c in request["context"]["candidates"]] == ["paper:p0-v2"]
    assert request["context"]["candidate_targets"] == request["context"]["new_targets"]
    data = answer(request, project)
    data["new_reviews"].append({"idea_id": "paper:p1-idea", "candidate_hash": "a" * 64, "objections": []})
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match=r"remove \['paper:p1-idea'\]"):
        workflow.submit(task["task_id"], directory / "response.json")
    (directory / "response.json").rename(directory / "failed-response-1.json")
    workflow.state["tasks"][task["task_id"]].update(status="invalid", attempts=2,
                                                    last_response=str(directory / "failed-response-1.json"))
    workflow._save()
    workflow.retry(task["task_id"])
    retried = workflow.state["tasks"][task["task_id"]]
    assert retried["attempts"] == 0 and "remove ['paper:p1-idea']" in retried["error"]
