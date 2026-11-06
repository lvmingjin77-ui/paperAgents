"""Synthetic coordination fixtures, never literature searches or research runs."""

from copy import deepcopy
from pathlib import Path

import pytest

from paperagents.knowledge import (
    KnowledgeBlocked,
    REVIEW_CRITERIA,
    advance_knowledge,
    knowledge_view,
    request_literature,
)
from paperagents.skills import STAGE_SKILLS, resolve_skills


def paper(pid):
    return {
        "paper_id": pid,
        "title": f"Synthetic method {pid}",
        "year": 2026,
        "venue": "Fixture",
        "doi": "",
        "arxiv_id": "",
        "url": f"https://example.invalid/{pid}",
        "full_text_path": "",
        "code_url": "",
        "relevance": "core",
        "reason": "Fixture route",
        "source_refs": [],
    }


def knowledge():
    return {
        "understanding": "Synthetic source understanding",
        "mechanism": "Fixture mechanism",
        "assumptions": [],
        "failures": [],
        "coverage": [],
        "source_refs": [],
        "idea_trace": [],
        "reasoning_patterns": [],
        "code_map": [],
        "communication": [],
        "gaps": [],
    }


class FakeWorkflow:
    def __init__(self, project):
        self.project = project
        self.project.mkdir(parents=True, exist_ok=True)
        (self.project / "research.md").write_text("Synthetic research problem; no real science.")
        self.run_dir = self.project / "runs" / "fixture"
        self.config = {"research": {"core_papers": 2, "allow_temporary_experts": True}}
        self.state = {"outer_round": 1}
        self.calls = []
        self.contexts = {}
        self.responses = {}
        self.papers = [paper("p1"), paper("p2")]
        self.reject = False
        self.materials_missing = False
        self.crash_after = None
        self.transform_response = None
        self.events = []

    def event(self, kind, **payload):
        self.events.append((kind, payload))

    def save(self):
        pass

    def task(self, stage, subject, role, context, schema, key=None, validator=None):
        if key in self.responses:
            return deepcopy(self.responses[key])
        self.calls.append((stage, subject))
        self.contexts[(stage, subject)] = deepcopy(context)
        if self.crash_after == stage:
            raise InterruptedError("synthetic interruption")
        if stage == "scope":
            response = {
                k: []
                for k in ("questions", "venues", "inclusion", "exclusions", "search_plan", "stop_conditions")
            }
            response["window"] = "2024–2026"
        elif stage == "corpus":
            response = {
                "papers": self.papers,
                "queries": [],
                "coverage_gaps": [],
                "excluded": [],
                "stop_reason": "fixture",
            }
        elif stage == "reading":
            response = {
                "paper_id": subject,
                "card": {
                    "problem": "Fixture problem",
                    "contributions": [],
                    "relations": [],
                    "relevance": "Relevant method",
                    "limitations": [],
                    "coverage": [
                        {"section": "appendix", "status": "unavailable", "notes": "not needed for selection"}
                    ],
                    "source_refs": [],
                },
            }
        elif stage == "domain":
            response = {
                "overview": "Synthetic competing routes",
                "routes": [],
                "knowledge_gaps": [],
                "evidence_limits": [],
                "source_paper_ids": [p["paper_id"] for p in self.papers],
            }
        elif stage == "selection":
            response = {
                "core_papers": [
                    {
                        "expert_id": f"expert-{p['paper_id']}",
                        "paper_id": p["paper_id"],
                        "method_contribution": "Fixture method",
                        "responsibility": "Fixture question",
                    }
                    for p in self.papers[:2]
                ],
                "temporary_experts": [],
                "coverage": [],
                "alternatives": [],
                "rationale": "Fixture selection",
            }
        elif stage in {"paper", "consultant"}:
            response = {
                "expert_id": subject,
                "role": context["role"],
                "status": "needs_materials" if self.materials_missing else "ready",
                "source_paper_ids": context["source_paper_ids"],
                "source_paths": [],
                "knowledge": knowledge(),
                "reuse_assessment": "Fixture reuse check",
                "missing_materials": ["Core mechanism source unavailable"] if self.materials_missing else [],
            }
        elif stage == "expert_review":
            response = {
                "accepted": not self.reject,
                "checks": [
                    {
                        "criterion": c,
                        "verdict": "fail" if self.reject else "pass",
                        "evidence": ["SYNTHETIC_FIXTURE_ONLY"],
                    }
                    for c in REVIEW_CRITERIA
                ],
                "blocking_issues": ["Unsupported mechanism"] if self.reject else [],
                "permitted_uses": ["Fixture only"],
                "limitations": [],
            }
        else:
            raise AssertionError(stage)
        # Exercise the exact response contract sent to real workers.
        if self.transform_response:
            response = self.transform_response(stage, response)
        from jsonschema import validate

        validate(response, schema)
        if validator:
            validator(response)
        self.responses[key] = deepcopy(response)
        return response


def test_breadth_cards_can_select_experts_before_complete_reading(tmp_path):
    w = FakeWorkflow(tmp_path)
    advance_knowledge(w)
    assert len(w.state["experts"]) == 3
    assert w.calls.index(("selection", "team")) < w.calls.index(("paper", "expert-p1"))
    assert w.state["knowledge"]["readings"]["p1"]["card"]["coverage"][0]["status"] == "unavailable"
    assert all(e["review"]["accepted"] for e in w.state["experts"])
    assert Path(w.state["experts"][0]["_asset"]["path"], "SKILL.md").is_file()
    before = len(w.calls)
    advance_knowledge(w)
    assert len(w.calls) == before


def test_outer_gap_search_reuses_prior_cards_and_reviews_experts(tmp_path):
    w = FakeWorkflow(tmp_path)
    advance_knowledge(w)
    request_literature(w, ["Missing verifier mechanism"])
    w.state["outer_round"] = 2
    w.papers.append(paper("p3"))
    advance_knowledge(w)
    assert w.calls.count(("reading", "p1")) == 1
    assert w.calls.count(("reading", "p3")) == 1
    assert w.calls.count(("expert_review", "expert-p1")) == 2
    assert w.contexts[("paper", "expert-p1")]["reuse_candidates"]
    assert w.contexts[("corpus", "corpus")]["questions_to_add"] == ["Missing verifier mechanism"]


def test_independent_review_rejection_preserves_knowledge_and_stops(tmp_path):
    w = FakeWorkflow(tmp_path)
    w.reject = True
    with pytest.raises(KnowledgeBlocked, match="Unsupported mechanism"):
        advance_knowledge(w)
    assert w.state["status"] == "needs_materials"
    assert len(w.state["knowledge"]["readings"]) == 2
    assert not w.state.get("experts")


def test_missing_core_material_is_not_claimed_as_ready(tmp_path):
    w = FakeWorkflow(tmp_path)
    w.materials_missing = True
    with pytest.raises(KnowledgeBlocked, match="Core mechanism"):
        advance_knowledge(w)
    assert not any(stage == "expert_review" for stage, _ in w.calls)


def test_interrupted_pipeline_does_not_repeat_completed_reading(tmp_path):
    w = FakeWorkflow(tmp_path)
    w.crash_after = "selection"
    with pytest.raises(InterruptedError):
        advance_knowledge(w)
    w.crash_after = None
    advance_knowledge(w)
    assert w.calls.count(("reading", "p1")) == 1
    assert len(w.state["experts"]) == 3


def test_domain_revision_reuses_sources_and_preserves_prior_tasks(tmp_path, monkeypatch):
    from paperagents.storage import read_json, write_json
    from paperagents.workflow import Workflow, initialize_project

    fixture = FakeWorkflow(tmp_path / "fixture")
    project = tmp_path / "project"
    initialize_project(project, "Synthetic domain revision; no scientific work.")
    w = Workflow(project)
    w.config["research"]["core_papers"] = 2
    w.config["backend"]["kind"] = "glm"
    w.config["loops"]["outer_rounds"] = 1

    def execute(driver, directory):
        req = read_json(directory / "request.json")
        response = fixture.task(
            req["stage"], req["subject"], req["role"], req["context"], req["output_schema"], req["task_id"]
        )
        write_json(directory / "response.json", response)
        return True, ""

    monkeypatch.setattr("paperagents.workflow.execute_command", execute)
    advance_knowledge(w)
    completed = deepcopy(w.state["tasks"])
    artifacts = {
        Path(t[field]): Path(t[field]).read_bytes()
        for t in completed.values()
        for field in ("request_path", "response_path")
    }
    readings = deepcopy(w.state["knowledge"]["readings"])
    calls = len(fixture.calls)
    w.state["tasks"]["k1-consultant-unfinished"] = dict(
        task_id="k1-consultant-unfinished", stage="consultant", status="interrupted"
    )

    w.revise("domain", "Recheck the decision-relevant source conflict")
    assert w.state["outer_round"] == 1
    assert not w.state["experts"]
    assert "selection" not in w.state["knowledge"]
    assert "complete_outer_round" not in w.state["knowledge"]
    assert w.state["tasks"]["k1-consultant-unfinished"]["status"] == "superseded"
    assert all(w.state["tasks"][key] == task for key, task in completed.items())

    advance_knowledge(w)
    assert set(stage for stage, _ in fixture.calls[calls:]) == {
        "domain", "selection", "consultant", "paper", "expert_review"
    }
    context = fixture.contexts[("domain", "domain")]
    assert context["previous_domain_path"] == completed["k1-domain-domain"]["response_path"]
    assert context["questions_to_add"] == ["Recheck the decision-relevant source conflict"]
    assert w.state["knowledge"]["readings"] == readings
    assert all(path.read_bytes() == content for path, content in artifacts.items())
    assert w.state["tasks"]["k1-d1-domain-domain"]["status"] == "completed"
    assert len(w.state["experts"]) == 3
    calls = len(fixture.calls)
    advance_knowledge(w)
    assert len(fixture.calls) == calls


def test_large_reading_evidence_stays_available_through_domain_and_team_indexes(tmp_path):
    import json

    w = FakeWorkflow(tmp_path)
    evidence = "SYNTHETIC_LONG_SOURCE_EVIDENCE " * 5000

    def add_evidence(stage, response):
        if stage == "reading":
            response["card"]["limitations"] = [evidence]
        return response

    w.transform_response = add_evidence
    advance_knowledge(w)
    views = [
        w.contexts[("domain", "domain")],
        w.contexts[("selection", "team")],
        w.contexts[("consultant", "domain")],
        knowledge_view(w.state["knowledge"]),
    ]
    for view in views:
        assert len(json.dumps(view)) < len(evidence) // 10
        for item in view["reading_index"].values():
            record = json.loads(Path(item["card_path"]).read_text())
            assert record["card"]["limitations"] == [evidence]


def test_local_source_changes_invalidate_card_cache(tmp_path):
    w = FakeWorkflow(tmp_path)
    source = tmp_path / "source.txt"
    source.write_text("source version one")
    w.papers[0]["full_text_path"] = str(source)
    advance_knowledge(w)
    source.write_text("source version two")
    w.state["outer_round"] = 2
    advance_knowledge(w)
    assert w.calls.count(("reading", "p1")) == 2
    assert w.calls.count(("reading", "p2")) == 1


@pytest.mark.parametrize(
    "stage,change,error",
    [
        ("corpus", lambda data: data["papers"].append(deepcopy(data["papers"][0])), "unique"),
        ("reading", lambda data: data.update(paper_id="other-paper"), "Reading must refer"),
        ("domain", lambda data: data["source_paper_ids"].append("unknown"), "outside the corpus"),
        ("selection", lambda data: data["core_papers"].pop(), "core-paper count"),
        ("selection", lambda data: data["core_papers"][0].update(expert_id="domain"), "distinct"),
        ("paper", lambda data: data.update(expert_id="wrong-author"), "Expert identity"),
        ("paper", lambda data: data.update(role="domain"), "assigned role"),
    ],
)
def test_semantically_invalid_response_is_not_cached_and_can_be_corrected(tmp_path, stage, change, error):
    w = FakeWorkflow(tmp_path)

    def corrupt(current_stage, response):
        result = deepcopy(response)
        if current_stage == stage:
            change(result)
        return result

    w.transform_response = corrupt
    with pytest.raises(ValueError, match=error):
        advance_knowledge(w)
    rejected_subject = next(subject for current_stage, subject in reversed(w.calls) if current_stage == stage)
    assert f"k1-{stage}-{rejected_subject}" not in w.responses
    w.transform_response = None
    advance_knowledge(w)
    assert len(w.state["experts"]) == 3
    assert w.calls.count((stage, rejected_subject)) == 2


def test_all_new_stages_have_real_skills_and_reading_is_light():
    for stage in STAGE_SKILLS:
        skills = resolve_skills(stage)
        assert skills
        assert all(Path(s["path"]).is_file() and "request.output_schema" in s["instructions"] for s in skills)
    assert [s["id"] for s in resolve_skills("reading")] == ["read-paper-card"]
    assert "trace-paper-ideas" in [s["id"] for s in resolve_skills("paper")]
    assert "map-paper-code" in [s["id"] for s in resolve_skills("paper")]
