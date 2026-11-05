"""Synthetic fixtures test orchestration, never stand in for scientific evidence."""

import sys
from pathlib import Path

import pytest

from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow, initialize_project
from paperagents.assets import file_hash
from paperagents.contracts import REVIEW_DIMENSIONS, EXPERT_REVIEW_CRITERIA
from tests.paperagents.test_paper_knowledge import domain_v2, paper_v2


def answer(request, project):
    stage, context = request["stage"], request["context"]
    source = ["SYNTHETIC_TEST_FIXTURE: section 1"]
    trace = [{"step": "motivation", "statement": "Fixture hypothesis", "basis": "author_stated", "source_refs": source}]
    if stage == "scope":
        return {"direction": "Fixture direction", "venues": [{"venue_id": "FixtureConf", "note": "SYNTHETIC_TEST_FIXTURE"}], "queries": ["fixture"], "inclusion_criteria": ["fixture only"]}
    if stage == "corpus":
        papers = []
        for i in range(3):
            path = project / f"fixture-{i}.txt"
            path.write_text("SYNTHETIC_TEST_FIXTURE, not a real paper")
            papers.append({"paper_id": f"p{i}", "title": f"Fixture {i}", "year": 2026, "venue_id": "FixtureConf",
                           "pub_date": None, "source_url": "https://example.invalid/fixture", "full_text_path": str(path),
                           "relevance": "core", "background": False, "reason": "SYNTHETIC_TEST_FIXTURE"})
        return {"papers": papers, "coverage": {"status": "complete"}, "search_log": source, "missing_sources": []}
    if stage == "reading":
        pid = context["expected_paper_id"]
        return {"paper_id": pid, "coverage": {"status": "complete", "unread": []}, "limitations": [],
                "idea_trace": [dict(item, trace_id=f"{pid}-t{i}") for i, item in enumerate(trace)],
                "card": {"problem": "Fixture problem", "relations": [],
                         "contributions": [{"method": f"Fixture method {pid}", "mechanism": "Fixture mechanism",
                                            "assumptions": ["Fixture assumption"],
                                            "results": [{"benchmark": "FixtureBench", "metric": "score", "value": "1",
                                                         "condition": "SYNTHETIC_TEST_FIXTURE"}]}]}}
    if stage == "triage":
        return {"reviews": [dict(item, overlap_risk="unknown", near_matches=[], search_log=[],
                                 note="SYNTHETIC_TEST_FIXTURE: no real search") for item in context["candidate_targets"]], "groups": []}
    if stage == "rebuttal":
        return {"expert_id": context["expected_expert_id"], "revised_candidates": [], "withdrawn_idea_ids": [],
                "responses": [{"objection_id": item["objection_id"], "action": "rebut", "argument": "Fixture rebuttal",
                               "evidence": source, "revised_idea_id": None} for item in context["objections"]]}
    if stage == "recheck":
        return {"expert_id": context["expected_expert_id"],
                "verdicts": [{"objection_id": item["objection_id"], "status": "resolved", "reason": "Fixture",
                              "evidence": source} for item in context["objections_to_judge"]],
                "new_reviews": [dict(item, objections=[]) for item in context["new_targets"]]}
    if stage == "agenda":
        return {"issues": [], "notes": ["SYNTHETIC_TEST_FIXTURE: no issues raised"]}
    if stage == "domain":
        data = domain_v2(["p0", "p1", "p2"])
        data["knowledge"]["problem_map"] = "fixture"
        return data
    if stage == "selection":
        return {"coverage": [{"question": "fixture", "route": "fixture", "expert_ids": ["domain", "paper:p0"]}],
                "team_alternatives": [{"core_paper_ids": ["p0"], "temporary_expert_ids": [], "covers": "fixture",
                                       "misses": "fixture", "reason": "SYNTHETIC_TEST_FIXTURE"}],
                "core_paper_ids": ["p0", "p1", "p2"], "selection_reasons": {"p0": "baseline", "p1": "mechanism", "p2": "counterexample"},
                "temporary_experts": [{"expert_id": "statistics", "specialty": "statistics", "reason": "fixture", "source_paper_ids": ["p0"]}]}
    if stage == "paper":
        path = context["paper"]["full_text_path"]
        return paper_v2(context["paper"]["paper_id"], path, file_hash(Path(path)))
    if stage == "consultant":
        return {"expert_id": context["expected_expert_id"], "specialty": "statistics", "knowledge": {"controls": "fixture"}, "source_refs": source, "limitations": []}
    if stage in {"expert_review", "proposal_review"}:
        criteria = REVIEW_DIMENSIONS if stage == "proposal_review" else EXPERT_REVIEW_CRITERIA
        data = {"accepted": True, "checks": [{"criterion": criterion, "check": "Synthetic criterion only",
                                              "evidence": source, "verdict": "pass"} for criterion in criteria]}
        data.update({"blocking_issues": [], "experiment_requirements": []} if stage == "proposal_review" else {"expert_id": context["expected_expert_id"], "limitations": []})
        if stage == "proposal_review":
            data["decision_assessment"] = {"synthesis_decision": context["synthesis"]["decision"],
                                           "agree": True, "reason": "SYNTHETIC_TEST_FIXTURE"}
            if context["synthesis"]["decision"] != "ready":
                data["accepted"] = False

            def dimensions():
                return {key: {"status": "scored", "score": 3, "rationale": "SYNTHETIC_TEST_FIXTURE only",
                              "evidence": source} for key in REVIEW_DIMENSIONS}
            targets = context["review_targets"]
            data["candidate_scores"] = [dict(item, dimensions=dimensions()) for item in targets["candidates"]]
            data["proposal_score"] = {"proposal_hash": targets["proposal_hash"], "dimensions": dimensions()}
        return data
    if stage == "hypothesis":
        return {"expert_id": context["expected_expert_id"], "candidates": [{"idea_id": context["expected_expert_id"] + "-idea",
                "title": "Fixture idea", "kind": "mechanism", "problem": "Fixture problem", "hypothesis": "Fixture hypothesis", "mechanism": "Fixture mechanism",
                "assumptions": ["Fixture assumption"], "nearest_work": source, "falsification": "Fixture falsifier",
                "experiment_plan": "Fixture controls", "source_refs": source}]}
    if stage == "challenge":
        reviews = [{"idea_id": item["idea_id"], "candidate_hash": item["candidate_hash"], "claims": source,
                    "required_evidence": [], "objections": []} for item in context["candidate_targets"]]
        return {"expert_id": context["expected_expert_id"], "reviews": reviews,
                "issue_responses": [{"issue_id": issue, "response": "Fixture response"}
                                    for issue in context.get("assigned_issue_ids", [])]}
    if stage == "novelty":
        logs = [{"provider": "synthetic_fixture", "query": "fixture", "searched_at": "2026-11-04T00:00:00Z",
                 "scope": "SYNTHETIC_TEST_FIXTURE only", "results_count": 1,
                 "result_refs": source, "limitations": ["Not a real search"]}]
        return {"reviews": [{"idea_id": item["idea_id"], "status": "distinct", "nearest_work": source, "search_log": logs, "reason": "Fixture only"} for item in context["candidates"]]}
    if stage == "synthesis":
        if not context["candidates"]:
            return {"decision": "no_viable_idea", "selected_idea_id": None, "proposal": {}, "alternatives": [],
                    "unresolved_questions": [], "next_action": "stop"}
        data = {"decision": "ready", "selected_idea_id": context["candidates"][0]["idea_id"], "proposal": {
                "title": "Fixture proposal", "problem": "Fixture problem", "hypothesis": "Fixture hypothesis",
                "implementation_plan": ["Fixture implementation"], "evaluation": {"controls": "fixture"}, "source_refs": source},
                "alternatives": [], "unresolved_questions": [], "next_action": "proceed",
                "candidate_ref": dict(context["candidate_targets"][0])}
        for field in ("problem", "hypothesis", "mechanism", "assumptions", "falsification"):
            data["proposal"][field] = context["candidates"][0][field]
        return data
    raise AssertionError(stage)


@pytest.fixture
def project(tmp_path):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    return project


def advance(workflow, *, stop=None):
    while True:
        summary = workflow.run()
        if summary["status"] != "awaiting_workers" or summary["phase"] == stop:
            return summary
        for task in summary["pending"]:
            directory = workflow.run_dir / "requests" / task["task_id"]
            request = read_json(directory / "request.json")
            response = directory / "response.json"
            write_json(response, answer(request, workflow.project))
            workflow.submit(task["task_id"], response)


def test_complete_handoff_resume_and_independent_round(project):
    workflow = Workflow(project)
    summary = advance(workflow, stop="hypothesis")
    assert len(summary["pending"]) == 5  # domain + 3 core + one invited specialist
    assigned_roles = {}
    for task in summary["pending"]:
        request = read_json(workflow.run_dir / "requests" / task["task_id"] / "request.json")
        assigned_roles[request["subject_id"]] = request["role"]
        assert request["expert_profile"]["id"] == request["role"]
        assert Path(request["expert_profile"]["path"]).is_file()
    assert assigned_roles == {"domain": "domain", "paper:p0": "paper", "paper:p1": "paper",
                              "paper:p2": "paper", "statistics": "consultant"}
    first = summary["pending"][0]
    directory = workflow.run_dir / "requests" / first["task_id"]
    request = read_json(directory / "request.json")
    write_json(directory / "response.json", answer(request, project))
    workflow.submit(first["task_id"], directory / "response.json")
    resumed = Workflow(project)
    for task in summary["pending"][1:]:
        context = read_json(resumed.run_dir / "requests" / task["task_id"] / "request.json")["context"]
        assert "candidates" not in context
        assert "hypotheses" not in context
    result = advance(resumed)
    assert result["status"] == "completed"
    exported = Path(result["task_dir"])
    assert (exported / "task.md").is_file()
    assert (exported / "paperagents_context.json").is_file()
    assert list((exported / "paperagents_assets").rglob("*fixture-0.txt"))
    assert Workflow(project).run()["task_dir"] == str(exported)


def test_insufficient_corpus_blocks_but_partial_search_continues_with_gaps(project):
    workflow = Workflow(project)
    advance(workflow, stop="corpus")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["coverage"]["status"] = "insufficient"
    data["missing_sources"] = ["most proceedings inaccessible"]
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    assert workflow.run()["status"] == "needs_evidence"
    assert "reading" not in workflow.state["batches"]

    workflow.revise("corpus", "Supplied the inaccessible proceedings")
    task = workflow.run()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["coverage"]["status"] = "partial"
    data["missing_sources"] = ["one inaccessible proceeding"]
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    summary = workflow.run()
    assert summary["phase"] == "reading" and len(summary["pending"]) == 3
    advance(workflow, stop="domain")
    domain = read_json(workflow.run_dir / "requests" / workflow.summary()["pending"][0]["task_id"] / "request.json")
    assert domain["context"]["corpus"]["missing_sources"] == ["one inaccessible proceeding"]
    assert all("idea_trace" not in paper for paper in domain["context"]["corpus"]["papers"])
    assert all(paper["reading"]["artifact_path"] for paper in domain["context"]["corpus"]["papers"])


def test_too_few_usable_readings_requests_evidence_before_domain(project):
    workflow = Workflow(project)
    advance(workflow, stop="reading")
    pending = workflow.summary()["pending"]
    assert [read_json(workflow.run_dir / "requests" / t["task_id"] / "request.json")["skills"][0]["id"]
            for t in pending][:1] == ["understand-paper"]
    for index, task in enumerate(pending):
        directory = workflow.run_dir / "requests" / task["task_id"]
        data = answer(read_json(directory / "request.json"), project)
        if index == 0:
            data["coverage"] = {"status": "insufficient", "unread": ["sections 2-6"]}
        write_json(directory / "response.json", data)
        workflow.submit(task["task_id"], directory / "response.json")
    summary = workflow.run()
    assert summary["status"] == "needs_evidence"
    assert "Fewer than 3 papers" in summary["reason"]
    assert "domain" not in workflow.state["batches"]


def test_revision_preserves_old_export_and_receipts(project):
    workflow = Workflow(project)
    first = advance(workflow)
    old = Path(first["task_dir"])
    old_text = (old / "task.md").read_text()
    workflow.revise("hypothesis", "New public search evidence")
    second = advance(workflow)
    assert second["task_dir"] != first["task_dir"]
    assert (old / "task.md").read_text() == old_text
    task = next(item for item in workflow.state["tasks"].values() if item["stage"] == "scope")
    write_json(workflow.run_dir / "artifacts" / f"{task['task_id']}.json", {"tampered": True})
    with pytest.raises(ValueError, match="Accepted artifact changed"):
        Workflow(project)


def test_final_feedback_rejected(project, tmp_path):
    workflow = Workflow(project)
    workflow.start()
    path = tmp_path / "feedback.json"
    write_json(path, {"evaluation_split": "final"})
    with pytest.raises(ValueError, match="final evaluation is excluded"):
        workflow.add_feedback(path)


def test_failed_driver_cannot_promote_valid_output(project, tmp_path):
    driver = tmp_path / "driver.py"
    driver.write_text("import json,sys\njson.dump({'direction':'fixture','venues':['fixture'],'queries':['fixture'],'inclusion_criteria':['fixture']},open(sys.argv[1],'w'))\nsys.exit(7)\n")
    workflow = Workflow(project)
    workflow.config["backend"].update(kind="command", command=[sys.executable, str(driver), "{response}"])
    result = workflow.run()
    assert result["status"] == "awaiting_workers"
    assert result["phase"] == "scope"
    assert result["pending"][0]["attempts"] == 2
    assert not workflow.results("scope")


def test_unknown_core_paper_and_fabricated_file_are_rejected(project):
    workflow = Workflow(project)
    advance(workflow, stop="corpus")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["papers"][0]["full_text_path"] = "nonexistent.pdf"
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="Full text does not exist"):
        workflow.submit(task["task_id"], directory / "response.json")


def test_interrupted_request_preparation_is_resumable(project):
    workflow = Workflow(project)
    workflow.start()
    workflow._prepare_batch("scope")
    # Simulate a crash after directory creation, before batch registration.
    workflow.state["batches"].clear()
    workflow.state["tasks"].clear()
    workflow._save()
    assert Workflow(project).run()["status"] == "awaiting_workers"


def test_source_contents_are_frozen_and_new_versions_preserved(project):
    workflow = Workflow(project)
    advance(workflow, stop="domain")
    old = workflow.one("corpus")["papers"][0]
    frozen = Path(old["full_text_path"])
    original = project / "fixture-0.txt"
    original.write_text("changed outside the run")
    assert frozen.read_text().startswith("SYNTHETIC")
    assert Workflow(project).one("corpus")["papers"][0] == old
    from paperagents.assets import freeze_asset
    new = dict(old)
    new.pop("_asset")
    new["full_text_path"] = str(original)
    changed = freeze_asset(project, "papers", new, new["paper_id"], [str(original)])
    assert changed["_asset"]["version"] != old["_asset"]["version"]
    assert frozen.read_text().startswith("SYNTHETIC")
    frozen.write_text("tampered frozen evidence")
    with pytest.raises(ValueError, match="Immutable asset source changed"):
        Workflow(project)


def test_interrupted_driver_response_is_not_accepted(project):
    workflow = Workflow(project)
    workflow.run()
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    write_json(directory / "response.json", answer(read_json(directory / "request.json"), project))
    workflow.state["tasks"][task["task_id"]].update(status="running", attempts=1)
    workflow._save()
    resumed = Workflow(project)
    assert resumed.run()["status"] == "awaiting_workers"
    assert not resumed.results("scope")
    assert list(directory.glob("interrupted-response-*.json"))


def test_tool_sources_persist_and_are_exported(project):
    workflow = Workflow(project)
    advance(workflow, stop="paper")
    task = next(task for task in workflow.summary()["pending"] if task["stage"] == "paper")
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    tool = project / "method.py"
    tool.write_text("def method(x):\n    return x + 1\n")
    data["source_paths"] = [str(tool)]
    data["code_tools"] = [{"name": "fixture_method", "status": "wrapped",
                           "entrypoint": str(tool), "verification_evidence": []}]
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    tool.unlink()
    result = advance(workflow)
    exported = Path(result["task_dir"])
    context = read_json(exported / "paperagents_context.json")
    snapshot = exported / context["source_path_map"][str(tool)]
    assert snapshot.read_text() == "def method(x):\n    return x + 1\n"


def test_paper_sources_are_hash_checked_and_knowledge_views_frozen(project):
    workflow = Workflow(project)
    advance(workflow, stop="paper")
    task = next(item for item in workflow.summary()["pending"] if item["stage"] == "paper")
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    source = data["knowledge"]["paper_understanding"]["sources"][0]
    original_hash = source["sha256"]
    source["sha256"] = "0" * 64
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="hash mismatch"):
        workflow.submit(task["task_id"], directory / "response.json")
    source["sha256"] = original_hash
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    accepted = workflow._artifact(workflow.state["tasks"][task["task_id"]])
    asset = Path(accepted["_asset"]["path"])
    frozen_source = Path(accepted["knowledge"]["paper_understanding"]["sources"][0]["path"])
    assert frozen_source.is_relative_to(asset)
    assert file_hash(frozen_source) == original_hash
    assert (asset / "knowledge/index.md").is_file()
    assert (asset / "knowledge/idea-trace.json").is_file()
    assert (asset / "knowledge/reasoning-patterns.json").is_file()
    Workflow(project)  # The frozen views and source records are consistent on resume.
    (asset / "knowledge/idea-trace.json").write_text("[]")
    with pytest.raises(ValueError, match="Immutable asset source changed"):
        Workflow(project)


def test_missing_supplement_blocks_paper_promotion(project):
    workflow = Workflow(project)
    advance(workflow, stop="paper")
    task = next(item for item in workflow.summary()["pending"] if item["stage"] == "paper")
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    understanding = data["knowledge"]["paper_understanding"]
    understanding["sources"].append({"source_id": "supp", "kind": "supplement", "version": "unknown",
        "status": "unavailable", "required": True, "path": None, "sha256": None})
    understanding["coverage"]["status"] = "partial"
    understanding["limitations"].append("Required supplement not retrieved")
    write_json(directory / "response.json", data)
    workflow.submit(task["task_id"], directory / "response.json")
    assert advance(workflow)["status"] == "needs_evidence"
    assert "expert_review" not in workflow.state["batches"]


def test_domain_pattern_cannot_invent_a_corpus_trace(project):
    workflow = Workflow(project)
    advance(workflow, stop="domain")
    task = workflow.summary()["pending"][0]
    directory = workflow.run_dir / "requests" / task["task_id"]
    data = answer(read_json(directory / "request.json"), project)
    data["knowledge"]["reasoning_patterns"][0]["trace_refs"] = [{"paper_id": "p0", "trace_id": "invented"}]
    write_json(directory / "response.json", data)
    with pytest.raises(ValueError, match="unknown corpus trace"):
        workflow.submit(task["task_id"], directory / "response.json")

