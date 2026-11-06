"""Synthetic research lifecycle fixtures. No model API or scientific experiment is invoked."""

import json
from pathlib import Path
import pytest
from paperagents.workflow import Pending, Workflow, initialize_project
from paperagents.storage import write_json, digest
from paperagents import contracts as C
from paperagents.state import add_claim, add_evidence, set_verdict


def candidate(identity="fixture", parents=None):
    return dict(
        claim_id=identity,
        kind="mechanism",
        text="SYNTHETIC fixture hypothesis",
        mechanism="Fixture increment",
        prediction="Fixture score increases",
        falsification="No increase",
        parents=parents or [],
        exploratory=True,
        sources=[],
    )


def scores():
    return {
        k: dict(score=3, reason="SYNTHETIC fixture assessment", evidence_ids=[]) for k in C.REVIEW_DIMENSIONS
    }


@pytest.fixture
def workflow(tmp_path):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC engineering fixture; not scientific evidence")
    w = Workflow(project)
    w.config["execution"]["sandbox"] = "none"
    w.config["loops"].update(
        seeds=[1, 2], confirm_seeds=[3, 4], test_seeds=[5], evolve_rounds=2, target_good=2
    )
    return w


def test_request_preserves_large_context_without_embedding_it_in_prompt(workflow):
    context = {"evidence": "SYNTHETIC_EVIDENCE_ONLY\n" * 100_000}
    with pytest.raises(Pending):
        workflow.task("scope", "large-request", "expert", context, {"type": "object"})
    task = workflow.state["tasks"][workflow.key("scope", "large-request")]
    request_path = Path(task["request_path"])
    request = json.loads(request_path.read_text())
    prompt = (request_path.parent / "prompt.md").read_text()
    assert request["context"] == context
    assert str(request_path) in prompt
    assert "SYNTHETIC_EVIDENCE_ONLY" not in prompt
    assert len(prompt.encode()) < 20_000


def test_shared_expert_index_preserves_identity_and_links_full_assets(workflow):
    expert = dict(
        expert_id="paper-fixture",
        role="paper",
        source_paper_ids=["fixture"],
        knowledge={"mechanism": "SYNTHETIC_FULL_METHOD"},
        _asset={"path": str(workflow.project / "library/experts/fixture")},
    )
    workflow.state["experts"] = [expert, {"expert_id": "domain", "role": "domain"}]
    context = workflow.context()
    assert context["experts"][0] == dict(
        expert_id="paper-fixture",
        role="paper",
        source_paper_ids=["fixture"],
        asset_path=str(Path(expert["_asset"]["path"]) / "asset.json"),
        skill_path=str(Path(expert["_asset"]["path"]) / "SKILL.md"),
    )
    assert context["experts"][1] == {"expert_id": "domain", "role": "domain"}
    assert workflow.state["experts"][0]["knowledge"] == expert["knowledge"]


def install_fake_workers(w, monkeypatch):
    import paperagents.knowledge
    import paperagents.writing

    def knowledge(workflow):
        workflow.state["experts"] = [
            dict(expert_id="domain", role="domain", knowledge={}, source_paper_ids=[])
        ]
        workflow.state["knowledge"] = {"corpus": {"papers": []}}
        workflow.save()

    monkeypatch.setattr(paperagents.knowledge, "advance_knowledge", knowledge)
    monkeypatch.setattr(
        paperagents.writing,
        "compile_draft",
        lambda path: dict(status="compiled", audit={"passed": True}, pdf=str(path / "main.pdf")),
    )
    answers = {}

    def task(stage, subject, role, context, schema, key=None, validator=None):
        task_id = key or w.key(stage, subject)
        if task_id in answers:
            return json.loads(json.dumps(answers[task_id]))
        if stage == "testbed_plan":
            data = dict(
                design="SYNTHETIC fixture",
                baselines=["baseline"],
                validity_checks=["fixture"],
                diagnostics=[],
                unresolved=[],
            )
        elif stage == "build_testbed":
            workspace = Path(context["workspace"])
            (workspace / "baseline.json").write_text("1")
            for split in ("screen", "confirm", "test"):
                (workspace / f"{split}.json").write_text("{}")
            (workspace / "evaluate.py").write_text("""import argparse,json,pathlib
p=argparse.ArgumentParser()
for name in ('program','data','seed','output'):p.add_argument('--'+name)
a=p.parse_args(); out=pathlib.Path(a.output);out.mkdir(exist_ok=True,parents=True)
value=float(pathlib.Path(a.program).read_text())
(out/'metrics.json').write_text(json.dumps({'quality':value}))
(out/'correct.json').write_text(json.dumps({'correct':True}))
""")
            data = dict(
                status="ready",
                reason="Fixture protocol",
                protocol=dict(
                    evaluator="evaluate.py",
                    programs={"baseline": "baseline.json"},
                    splits={s: f"{s}.json" for s in ("screen", "confirm", "test")},
                    metrics={"quality": {"direction": "max", "description": "Fixture metric"}},
                    data_provenance=["Synthetic fixture"],
                    validity_rules=["Engineering only"],
                    diagnostic_observations=[],
                    unknowns=[],
                    assets=[],
                ),
            )
        elif stage in ("protocol_review", "implementation_review", "ablation_review"):
            data = dict(accepted=True, reason="SYNTHETIC review fixture", issues=[])
        elif stage == "propose":
            assert any(e["kind"] == "run" and e["claim_ref"] is None for e in context["evidence"].values())
            assert any(
                e["kind"] == "diagnosis" and e["claim_ref"] is None for e in context["evidence"].values()
            )
            data = dict(claims=[candidate()], reason="Initial fixture")
        elif stage == "exchange":
            data = {"comments": []}
        elif stage == "revise":
            data = dict(claims=[], reason="Retain fixture")
        elif stage == "triage":
            data = dict(groups=[], overlap_notes=[])
        elif stage == "merge":
            data = dict(withdraw=[], claims=[], reason="Distinct fixture")
        elif stage == "assess":
            data = dict(decision="admit", reason="Fixture", dimensions=scores(), required_tests=[])
        elif stage == "select":
            data = dict(claim_refs=[context["eligible"][0]["ref"]], reason="Fixture exploration")
        elif stage == "build":
            filename = "program-" + digest(subject)[:12] + ".json"
            (Path(context["workspace"]) / filename).write_text("1" if "ablation" in subject else "2")
            data = dict(
                program=filename,
                changes="Synthetic fixture",
                protocol_changes=False,
                reason="No protocol changes",
            )
        elif stage == "judge":
            data = dict(
                decision="promising", reason="Fixture only", evidence_ids=context["available_evidence_ids"]
            )
        elif stage == "explain":
            data = dict(
                findings=["Fixture evidence"],
                competing_explanations=[],
                next_tests=[],
                reframe=False,
                literature_gaps=[],
            )
        elif stage == "novelty":
            data = dict(decision="distinct", reason="SYNTHETIC only", references=[])
        elif stage == "ablation_plan":
            data = {
                "variants": [dict(id="remove", change="Synthetic ablation", prediction="Fixture decreases")]
            }
        elif stage == "evolve":
            latest = max(w.state["claims"].values(), key=lambda c: c["version"])
            data = dict(claims=[candidate(parents=[latest["ref"]])], reason="Fixture revision")
        elif stage == "final_judgment":
            data = {
                "verdicts": [
                    dict(claim_ref=r, verdict="supported", reason="Fixture final review")
                    for r in w.state["final_claims"]
                ]
            }
        elif stage == "write_section":
            data = dict(sections=[], references=[])
        elif stage == "rebuttal":
            data = dict(response="Synthetic fixture response", evidence_ids=[], required_experiments=[])
        elif stage in ("write", "finalize"):
            refs = w.state.get("final_claims") or [
                c["ref"] for c in w.state["claims"].values() if c["active"]
            ]
            data = dict(
                title="SYNTHETIC engineering fixture",
                sections=[
                    dict(
                        name="Results",
                        claim_refs=refs,
                        tex="Synthetic fixture only. " + context["metrics"][-1]["macro"],
                    )
                ],
                references=[],
                figures=[
                    {k: f[k] for k in ("path", "claim_refs", "caption", "run_ids")}
                    for f in context["figures"]
                    if set(f["claim_refs"]) <= set(refs)
                ],
            )
        elif stage == "peer_review":
            data = dict(
                decision="accept",
                reason="Synthetic reviewer",
                dimensions=scores(),
                required_experiments=[],
                claim_refs=w.state["confirmed"],
            )
        elif stage == "meta_review":
            data = dict(
                decision="accept",
                reason="Synthetic meta review",
                required_experiments=[],
                claim_refs=[c["ref"] for c in w.state["claims"].values() if c["active"]],
            )
        else:
            raise AssertionError(stage)
        C.validate(data, schema)
        if validator:
            validator(data)
        folder = w.run_dir / "tasks" / task_id / "attempt-001"
        folder.mkdir(parents=True, exist_ok=True)
        write_json(folder / "response.json", data)
        w.state["tasks"][task_id] = dict(
            task_id=task_id,
            stage=stage,
            subject=subject,
            role=role,
            status="completed",
            response_path=str(folder / "response.json"),
            request_path=str(folder / "request.json"),
            attempt=1,
        )
        answers[task_id] = data
        w.save()
        return json.loads(json.dumps(data))

    monkeypatch.setattr(w, "task", task)
    return answers


def test_complete_loop_with_versioned_evidence_and_single_holdout(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    result = workflow.run(execute=True)
    assert result["status"] == "completed"
    assert {"fixture@1", "fixture@2"} <= workflow.state["claims"].keys()
    assert not workflow.state["claims"]["fixture@1"]["active"]
    assert workflow.state["claims"]["fixture@2"]["verdict"] == "supported"
    runs = list(workflow.state["runs"].values())
    assert len([r for r in runs if r["split"] == "test"]) == 2
    assert workflow.state["draft"]["audit"]["passed"]
    size = len(runs)
    assert workflow.run(execute=True)["status"] == "completed"
    assert len(workflow.state["runs"]) == size
    with pytest.raises(ValueError, match="Holdout"):
        workflow.revise("evolve", "cannot tune on final results")


def test_explicit_execution_gate_and_resume(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    result = workflow.run()
    assert result["status"] == "ready_for_experiment"
    assert not workflow.state["runs"]
    assert workflow.run(execute=True)["status"] == "completed"


def test_manual_task_schema_feedback_and_retry(workflow):
    result = workflow.run()
    assert result["status"] == "awaiting_workers"
    task = next(iter(workflow.state["tasks"].values()))
    response = Path(task["response_path"])
    response.write_text("{}")
    result = workflow.run()
    assert result["status"] == "awaiting_workers"
    assert task["attempt"] == 2
    assert task.get("error")
    Path(task["response_path"]).write_text("{}")
    assert workflow.run()["status"] == "awaiting_retry"
    workflow.retry(task["task_id"])
    assert workflow.config["execution"]["max_worker_attempts"] == 2
    reloaded = Workflow(workflow.project)
    assert reloaded.run()["status"] == "awaiting_workers"


def test_claim_version_never_inherits_old_evidence(workflow):
    s = workflow.state
    a = add_claim(s, candidate(), "domain", "one")
    eid = add_evidence(s, "run", a, "fixture.json", {"outcome": "completed", "metrics": {"quality": 1}})
    set_verdict(s, a, "supported", [eid], "Fixture")
    b = add_claim(s, candidate(parents=[a]), "domain", "two")
    assert s["claims"][b]["verdict"] == "untested" and not s["claims"][b]["evidence_ids"]
    with pytest.raises(ValueError, match="this claim version"):
        set_verdict(s, b, "supported", [eid], "Invalid reuse")
    assessment = add_evidence(s, "assessment", b, "review.json", {"score": 5})
    with pytest.raises(ValueError, match="alone"):
        set_verdict(s, b, "supported", [assessment], "Model vote is not evidence")


def test_protocol_files_cannot_change_after_review(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    workflow.run(execute=True, until="propose")
    (workflow.run_dir / "workspace" / "baseline.json").write_text("10")
    with pytest.raises(ValueError, match="Approved"):
        workflow._verify_protocol()


def test_checkpoint_requires_operator_approval(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    workflow.config["checkpoints"]["testbed"] = True
    assert workflow.run(execute=True)["status"] == "needs_human"
    assert not workflow.state["runs"]
    workflow.approve("testbed")
    assert workflow.run(execute=True)["status"] == "completed"


def test_input_change_requires_new_run(workflow):
    (workflow.project / "research.md").write_text("Changed question")
    with pytest.raises(ValueError, match="input changed"):
        Workflow(workflow.project)
    assert Workflow(workflow.project, new=True).state["run_id"] != workflow.state["run_id"]


def test_worker_currency_and_call_budgets_stop_before_call(workflow):
    from paperagents.workflow import Pending

    workflow.config["resources"]["api_budget"] = 1
    workflow.config["resources"]["api_cost_per_call"] = 2
    with pytest.raises(Pending):
        workflow._budget()
    assert workflow.state["usage"]["worker_calls"] == 0


def test_semantic_rejection_enters_existing_retry_loop(workflow):
    from paperagents.workflow import Pending

    schema = C.obj({"choice": C.TEXT})

    def validate(data):
        if data["choice"] != "accepted":
            raise ValueError("Choose the assigned option: accepted")

    def invoke():
        return workflow.task("select", "fixture", "critic", {}, schema, validator=validate)

    with pytest.raises(Pending):
        invoke()
    task = workflow.state["tasks"][workflow.key("select", "fixture")]
    write_json(Path(task["response_path"]), {"choice": "wrong"})
    with pytest.raises(Pending):
        invoke()
    assert task["attempt"] == 2 and task["status"] != "completed"
    assert "assigned option" in task["error"]
    write_json(Path(task["response_path"]), {"choice": "accepted"})
    assert invoke() == {"choice": "accepted"}
    assert task["status"] == "completed"


def test_approved_testbed_does_not_refresh_manifest_on_resume(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    workflow.config["checkpoints"]["testbed"] = True
    assert workflow.run()["status"] == "needs_human"
    approved = dict(workflow.state["protocol_manifest"])
    (workflow.run_dir / "workspace" / "baseline.json").write_text("99")
    workflow.approve("testbed")
    with pytest.raises(ValueError, match="Approved"):
        workflow.run(execute=True)
    assert workflow.state["protocol_manifest"] == approved
    assert not workflow.state["runs"]


def test_frozen_test_plan_ignores_later_seed_settings(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    assert workflow.run(execute=True, until="final_test")["phase"] == "final_test"
    workflow.config["loops"]["test_seeds"] = [777]
    assert workflow.run(execute=True)["status"] == "completed"
    assert {r["seed"] for r in workflow.state["runs"].values() if r["split"] == "test"} == {5}


def test_screen_resume_keeps_original_judgment_bound_to_original_program(workflow, monkeypatch):
    from paperagents.workflow import Pending

    install_fake_workers(workflow, monkeypatch)
    workflow.run(execute=True, until="screen")
    second = add_claim(workflow.state, candidate("second"), "domain", "second")
    workflow.state["selected"].append(second)
    base_task = workflow.task
    blocked = [False]

    def task(stage, subject, role, context, schema, **kwargs):
        if stage == "build" and subject.startswith(second) and not blocked[0]:
            blocked[0] = True
            raise Pending("Second candidate worker paused")
        result = base_task(stage, subject, role, context, schema, **kwargs)
        if stage == "judge" and subject == "fixture@1-screen":
            result["decision"] = "engineer"
        return result

    monkeypatch.setattr(workflow, "task", task)
    with pytest.raises(Pending):
        workflow._screen()
    original = workflow.state["programs"]["fixture@1"]
    repair = workflow.state["preferred_programs"]["fixture@1"]
    assert repair != original
    before = [r["run_id"] for r in workflow.state["runs"].values() if r["claim_ref"] == "fixture@1"]
    workflow._screen()
    assert [r["run_id"] for r in workflow.state["runs"].values() if r["claim_ref"] == "fixture@1"] == before
    assert workflow._build("fixture@1") == original


def test_review_budget_resume_reuses_same_meta_decision(workflow, monkeypatch):
    from paperagents.workflow import Pending

    install_fake_workers(workflow, monkeypatch)
    workflow.run(execute=True, until="meta_review")
    base_task = workflow.task
    calls = []

    def task(stage, subject, role, context, schema, **kwargs):
        result = base_task(stage, subject, role, context, schema, **kwargs)
        if stage == "meta_review":
            calls.append(subject)
            result.update(decision="revise", reason="Clarify fixture prose")
        return result

    monkeypatch.setattr(workflow, "task", task)
    workflow.config["loops"]["review_rounds"] = 1
    with pytest.raises(Pending):
        workflow._meta_review()
    assert workflow.state.get("review_round", 0) == 0
    workflow.config["loops"]["review_rounds"] = 2
    workflow._meta_review()
    assert calls == ["meta-0", "meta-0"]
    assert workflow.state["review_round"] == 1 and workflow.state["phase"] == "draft"


def test_deadline_applies_before_first_execution(workflow, monkeypatch):
    from paperagents.workflow import Pending

    install_fake_workers(workflow, monkeypatch)
    workflow.run(until="testbed")
    workflow.state["created_at"] = "2000-01-01T00:00:00+00:00"
    workflow.execute = True
    with pytest.raises(Pending):
        workflow._testbed()
    assert not workflow.state["runs"]
    assert workflow.state["status"] == "budget_exhausted"


def test_real_tex_compile_of_synthetic_manuscript_when_available(workflow, monkeypatch):
    import shutil
    import paperagents.writing

    if not (shutil.which("latexmk") or shutil.which("pdflatex")):
        pytest.skip("Local TeX distribution is optional")
    compile_draft = paperagents.writing.compile_draft
    install_fake_workers(workflow, monkeypatch)
    monkeypatch.setattr(paperagents.writing, "compile_draft", compile_draft)
    result = workflow.run(execute=True)
    assert result["status"] == "completed", workflow.state.get("compilation")
    assert Path(workflow.state["compilation"]["pdf"]).read_bytes().startswith(b"%PDF")
    assert workflow.state["compilation"]["audit"]["passed"]


def test_supplement_explanations_reach_writing_even_for_prior_claim(workflow, monkeypatch):
    install_fake_workers(workflow, monkeypatch)
    workflow.state["experts"] = [{"expert_id": "domain", "role": "domain"}]
    ref = add_claim(workflow.state, candidate(), "domain", "initial")
    workflow.state["claims"][ref]["active"] = False
    workflow.state["selected"] = [ref]
    workflow._explain_supplement()
    assert workflow.state["phase"] == "draft"
    evidence = list(workflow.context()["evidence"].values())
    assert len(evidence) == 1
    assert evidence[0]["claim_ref"] == ref
    assert evidence[0]["content"]["findings"] == ["Fixture evidence"]
