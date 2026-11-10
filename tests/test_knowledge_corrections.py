"""Exercise knowledge correction and reselection with synthetic workers, without model calls."""

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

import pytest

from paperagents import contracts as C
from paperagents import knowledge as K
from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow, initialize_project


OLD = "Test-gallery composition causes false acceptance"
CORRECTED = "Training negative augmentation improves ranking; no-match behavior is untested"
SOURCE = dict(source="SYNTHETIC paper", locator="Table 6", observation=CORRECTED, basis="observed")


def selection(owner):
    return dict(
        core_papers=[dict(expert_id=owner, paper_id="p1", method_contribution=OLD, responsibility=OLD)],
        temporary_experts=[dict(expert_id="temp", specialty="diagnosis", reason=OLD, source_paper_ids=["p2"])],
        coverage=[dict(question="composition", expert_ids=[owner, "temp"], method_owner=owner, uncovered=OLD)],
        alternatives=[dict(core_paper_ids=["p2"], temporary_specialties=[], strengths=[OLD], gaps=[OLD])],
        rationale=OLD,
    )


def expert(identity, role, sources):
    return dict(
        expert_id=identity, role=role, status="ready", source_paper_ids=sources, source_paths=[],
        knowledge=dict(understanding="SYNTHETIC", mechanism="SYNTHETIC", assumptions=[], failures=[],
                       coverage=[], source_refs=[SOURCE], idea_trace=[], reasoning_patterns=[], code_map=[],
                       communication=[], gaps=[]),
        reuse_assessment="SYNTHETIC", missing_materials=[],
    )


def review(accepted=True):
    return dict(
        accepted=accepted,
        checks=[dict(criterion=c, verdict="pass" if accepted else "fail", evidence=["SYNTHETIC"])
                for c in K.REVIEW_CRITERIA],
        blocking_issues=[],
        errors=[] if accepted else [dict(statement=OLD, correction=CORRECTED, source_refs=[SOURCE])],
        permitted_uses=["SYNTHETIC"], limitations=[],
    )


@pytest.fixture
def knowledge_run(tmp_path, monkeypatch):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC; not scientific evidence")
    w = Workflow(project)
    w.config["research"]["core_papers"] = 1
    w.config["backend"]["kind"] = "manual"
    w.state["phase"] = "knowledge"
    controls = dict(invalid_teams=0, reject_domain_once=False)
    calls = []
    domain = dict(overview=OLD, routes=[], knowledge_gaps=[], evidence_limits=[], source_paper_ids=["p1", "p2"])

    def answer(stage, subject, context):
        revision = w.state["knowledge"].get("domain_revision", 0)
        if stage == "scope":
            return dict(questions=["composition"], window="SYNTHETIC", venues=[], inclusion=[], exclusions=[],
                        search_plan=[], stop_conditions=[])
        if stage == "corpus":
            papers = [dict(paper_id=p, title=p, year=2026, venue="SYNTHETIC", doi="", arxiv_id="",
                           url=f"https://example.invalid/{p}", full_text_path="", code_url="",
                           relevance="core", reason="SYNTHETIC", source_refs=[SOURCE]) for p in ("p1", "p2")]
            return dict(papers=papers, queries=[], coverage_gaps=[], excluded=[], stop_reason="SYNTHETIC")
        if stage == "reading":
            return dict(paper_id=subject, card=dict(problem="composition", contributions=[], relations=[],
                        relevance="SYNTHETIC", limitations=[], coverage=[], source_refs=[SOURCE]))
        if stage == "domain":
            return deepcopy(domain)
        if stage == "selection":
            return selection(f"method{revision}")
        if stage in ("paper", "consultant"):
            item = expert(context["expert_id"], context["role"], context["source_paper_ids"])
            if context["role"] == "domain":
                item.update(
                    domain={**domain, "overview": CORRECTED},
                    selection=json.loads(json.dumps(context["selection"]).replace(OLD, CORRECTED)),
                    responses=[dict(correction_id=c["correction_id"], decision="applied",
                                    change=CORRECTED, reason="Table 6") for c in context["corrections"]],
                    team_valid=revision >= controls["invalid_teams"],
                )
            else:
                item["upstream_corrections"] = (
                    [dict(target="selection", statement=OLD, correction=CORRECTED, source_refs=[SOURCE])]
                    if context["role"] == "paper" else []
                )
            return item
        if stage == "expert_review":
            return review(not (controls["reject_domain_once"] and subject == "domain"))
        raise AssertionError(stage)

    def task(stage, subject, role, context, schema, key=None, validator=None):
        task_id = key or w.key(stage, subject)
        if task_id in w.state["tasks"]:
            return read_json(Path(w.state["tasks"][task_id]["response_path"]))
        calls.append(dict(stage=stage, subject=subject, context=deepcopy(context)))
        data = answer(stage, subject, context)
        C.validate(data, schema)
        if validator:
            validator(data)
        path = w.run_dir / "tasks" / task_id / "response.json"
        write_json(path, data)
        w.state["tasks"][task_id] = dict(task_id=task_id, stage=stage, status="completed", response_path=str(path))
        return data

    monkeypatch.setattr(w, "task", task)
    return w, controls, calls


def test_selection_corrections_replace_all_downstream_fields(knowledge_run):
    w, _, calls = knowledge_run
    K.advance_knowledge(w)

    view = K.knowledge_view(w.state["knowledge"])
    assert OLD not in json.dumps(view["selection"])
    assert view["selection"]["temporary_experts"][0]["reason"] == CORRECTED
    assert view["selection"]["coverage"][0]["uncovered"] == CORRECTED
    assert view["selection"]["alternatives"][0]["gaps"] == [CORRECTED]
    assert view["corrections"]["responses"][0]["decision"] == "applied"
    count = len(calls)
    K.advance_knowledge(w)
    assert len(calls) == count  # Resuming completed knowledge does not rebuild it.


@pytest.mark.parametrize("member", ["core_papers", "temporary_experts"])
def test_domain_cannot_silently_replace_a_built_expert(knowledge_run, member):
    w, _, _ = knowledge_run
    K.advance_knowledge(w)
    domain = deepcopy(w.state["experts"][0])
    domain["selection"][member][0]["expert_id"] = "unbuilt"
    domain["selection"]["coverage"] = []
    papers = {p["paper_id"]: p for p in w.state["knowledge"]["corpus"]["papers"]}
    with pytest.raises(ValueError, match="existing team's selection"):
        K._validate_domain_expert(domain, ["p1", "p2"], w.state["knowledge"]["corrections"]["items"],
                                  papers, selection("method0"), w.config["research"])


def test_literature_update_reselects_without_discarding_experiments(knowledge_run):
    w, controls, calls = knowledge_run
    w.state.update(phase="knowledge_update", literature_round=1,
                   protocol={"evaluator": "approved.py"}, claims={"existing": {"owner": "old", "active": True}})
    original = deepcopy((w.state["protocol"], w.state["claims"]))
    controls["invalid_teams"] = 1
    K.advance_knowledge(w)

    assert (w.state["protocol"], w.state["claims"]) == original
    assert w.state["phase"] == "knowledge_update"
    assert w.state["knowledge"]["selection"]["core_papers"][0]["expert_id"] == "method1"
    assert w.state["knowledge"]["complete_outer_round"] == 1
    counts = Counter(c["stage"] for c in calls)
    assert counts["domain"] == counts["selection"] == 2
    assert counts["scope"] == counts["corpus"] == 1
    assert counts["reading"] == 2  # The same two cards are reused after reselection.
    with pytest.raises(ValueError, match="only available before protocol approval"):
        K.revise_domain(w, "Manual domain revision must remain unavailable after testbed")


def test_manual_domain_revision_from_paused_testbed_keeps_materials(knowledge_run):
    w, _, calls = knowledge_run
    K.advance_knowledge(w)
    preserved = deepcopy({key: w.state["knowledge"][key] for key in ("corpus", "readings", "reading_fingerprints")})
    source = w.project / "inputs" / "source.txt"
    source.write_text("SYNTHETIC source material")
    w.state.update(phase="testbed", status="needs_materials", protocol={}, testbed_revision=3,
                   testbed_feedback={"reason": "old plan failed"})
    stages = {"testbed_plan": "completed", "build_testbed": "failed", "protocol_review": "pending"}
    old_tasks = {}
    for stage, status in stages.items():
        task_id = w.key(stage, "old-testbed")
        task = dict(task_id=task_id, stage=stage, status=status, attempt=3)
        w.state["tasks"][task_id] = task
        old_tasks[stage] = task

    w.revise("domain", "Correct the evidence used by the testbed plan")

    assert w.state["phase"] == "knowledge"
    assert w.state["status"] == "ready"
    assert w.state["testbed_revision"] == 0
    assert w.state["testbed_feedback"] == {}
    assert w.state["experts"] == []
    assert w.state["knowledge"]["domain_revision"] == 1
    assert "domain" not in w.state["knowledge"]
    assert {key: w.state["knowledge"][key] for key in preserved} == preserved
    assert source.read_text() == "SYNTHETIC source material"
    assert old_tasks["testbed_plan"]["status"] == "completed"
    assert old_tasks["build_testbed"]["status"] == old_tasks["protocol_review"]["status"] == "superseded"

    K.advance_knowledge(w)
    counts = Counter(c["stage"] for c in calls)
    assert counts["scope"] == counts["corpus"] == 1
    assert counts["reading"] == 2
    assert counts["domain"] == counts["selection"] == 2


def test_second_invalid_team_stops_with_existing_experiments_intact(knowledge_run):
    w, controls, calls = knowledge_run
    controls["invalid_teams"] = 2
    w.state.update(phase="knowledge_update", protocol={"approved": True}, claims={"existing": {"active": True}})
    with pytest.raises(K.KnowledgeBlocked, match="still invalidate the team"):
        K.advance_knowledge(w)
    assert w.state["protocol"] == {"approved": True}
    assert w.state["claims"] == {"existing": {"active": True}}
    assert sum(c["stage"] == "selection" for c in calls) == 2
    assert "complete_outer_round" not in w.state["knowledge"]


def test_domain_rereview_receives_original_corrections_and_sources(knowledge_run):
    w, controls, calls = knowledge_run
    controls["reject_domain_once"] = True
    K.advance_knowledge(w)
    reviews = [c for c in calls if c["stage"] == "expert_review" and c["subject"].startswith("domain")]
    assert [c["subject"] for c in reviews] == ["domain", "domain-revision"]
    expected = w.state["knowledge"]["corrections"]["items"]
    assert expected[0]["source_refs"] == [SOURCE]
    assert all(c["context"]["corrections"] == expected for c in reviews)
    revision = next(c for c in calls if c["stage"] == "consultant" and c["subject"] == "domain-revision")
    assert revision["context"]["corrections"] == expected
    assert revision["context"]["review"]["errors"][0]["source_refs"] == [SOURCE]
