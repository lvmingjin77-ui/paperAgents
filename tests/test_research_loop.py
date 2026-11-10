"""The whole research loop on synthetic workers and a synthetic evaluator: no model API, no real science."""

import json
from pathlib import Path

import pytest

from paperagents import contracts as C
from paperagents.storage import digest, write_json
from paperagents.workflow import Workflow, initialize_project

EVALUATOR = """import argparse, json, pathlib
p = argparse.ArgumentParser()
for name in ('program', 'data', 'seed', 'output'): p.add_argument('--' + name)
a = p.parse_args(); out = pathlib.Path(a.output)
value = float(pathlib.Path(a.program).read_text())
units = json.loads(pathlib.Path(a.data).read_text())['units']
rows = {u: {'quality': [value + (i - 0.5) * value / 10, 1]} for i, u in enumerate(units)}
(out / 'metrics.json').write_text(json.dumps({'quality': sum(r['quality'][0] for r in rows.values()) / len(rows)}))
(out / 'units.json').write_text(json.dumps(rows))
(out / 'correct.json').write_text(json.dumps({'correct': True}))
"""


def claim(identity="idea", parents=()):
    return dict(claim_id=identity, kind="mechanism", text="SYNTHETIC hypothesis", mechanism="Fixture",
                prediction="Quality increases", falsification="No increase", parents=list(parents),
                exploratory=True, sources=[])


def answer(w, stage, subject, context):
    """A synthetic worker for every stage; it reads only what a real worker would receive."""
    scores = {k: dict(score=3, reason="SYNTHETIC", evidence_ids=[]) for k in C.REVIEW_DIMENSIONS}
    claims = [c["ref"] for c in w.state["claims"].values() if c["active"]]
    if stage == "testbed_plan":
        return dict(design="SYNTHETIC", baselines=["baseline"], validity_checks=[], diagnostics=[], unresolved=[])
    if stage == "build_testbed":
        ws = Path(context["workspace"])
        units = {s: [f"{s}-a", f"{s}-b"] for s in ("screen", "confirm", "test")}
        for split, names in units.items():
            (ws / f"{split}.json").write_text(json.dumps({"units": names}))
        (ws / "manifest.json").write_text(json.dumps(units))
        (ws / "audit.json").write_text(json.dumps([{"unit": "screen-a", "label": "SYNTHETIC", "evidence": "fixture"}]))
        (ws / "baseline.txt").write_text("1")
        (ws / "evaluate.py").write_text(EVALUATOR)
        protocol = dict(
            evaluator="evaluate.py", programs={"baseline": "baseline.txt"},
            baselines=[dict(name="baseline", source="SYNTHETIC", version="0", supervision="none", compute="none")],
            splits={s: f"{s}.json" for s in units}, statistical_unit="SYNTHETIC unit", split_manifest="manifest.json",
            audit_sample="audit.json", metrics={"quality": {"direction": "max", "description": "SYNTHETIC"}},
            comparison_rules=[], scope="Engineering fixture", data_provenance=[], validity_rules=[],
            diagnostic_observations=[], unknowns=[], assets=[],
        )
        return dict(status="ready", reason="SYNTHETIC", protocol=protocol)
    if stage in ("protocol_review", "implementation_review", "ablation_review", "faithfulness"):
        return dict(accepted=True, reason="SYNTHETIC", issues=[])
    if stage == "explain":
        return dict(findings=["SYNTHETIC"], competing_explanations=[], next_tests=[], reframe=False,
                    literature_gaps=[], claim_refs=context.get("explain_claims", []))
    if stage == "propose":
        return dict(claims=[claim()], reason="SYNTHETIC")
    if stage == "evolve":
        latest = max(w.state["claims"].values(), key=lambda c: c["version"])
        return dict(claims=[claim(parents=[latest["ref"]])], reason="SYNTHETIC revision")
    if stage == "exchange":
        return {"comments": []}
    if stage == "revise":
        return dict(claims=[], reason="SYNTHETIC")
    if stage == "triage":
        return dict(groups=[], overlap_notes=[])
    if stage == "merge":
        return dict(withdraw=[], claims=[], reason="SYNTHETIC")
    if stage == "assess":
        return dict(decision="admit", reason="SYNTHETIC", dimensions=scores, required_tests=[])
    if stage == "select":
        return dict(claim_refs=[context["eligible"][0]["ref"]], reason="SYNTHETIC")
    if stage == "method_spec":
        return dict(inputs="x", outputs="y", components=[], procedure="SYNTHETIC", parameters=[],
                    difference_from_baselines="SYNTHETIC")
    if stage == "build":
        name = "program-" + digest(subject)[:12] + ".txt"
        (Path(context["workspace"]) / name).write_text("1" if "ablation" in subject else "2")
        return dict(program=name, changes="SYNTHETIC", protocol_changes=False, reason="none")
    if stage == "judge":
        runs = {r["run_id"] for r in context["runs"]}
        cited = [e for e, item in w.state["evidence"].items() if item["kind"] == "run" and item["content"]["run_id"] in runs]
        verdict = "inconclusive" if subject.endswith("-screen") else "supported"
        return dict(gate="advance", verdict=verdict, prediction_tested="Quality increases", reason="SYNTHETIC",
                    evidence_ids=cited)
    if stage == "novelty":
        return dict(decision="distinct", reason="SYNTHETIC", references=[])
    if stage == "ablation_plan":
        return {"variants": [dict(id="remove", change="SYNTHETIC", rules_out="SYNTHETIC", prediction="Quality decreases")]}
    if stage == "reassess":
        own = [e for e, item in w.state["evidence"].items() if item["claim_ref"] == subject]
        return dict(verdict="unchanged", prediction_tested="Quality increases", reason="SYNTHETIC", evidence_ids=own)
    if stage == "argument":
        bound = [(e, item["claim_ref"]) for e, item in w.state["evidence"].items() if item["claim_ref"] in claims]
        eid, ref = bound[-1]
        item = dict(statement="SYNTHETIC", claim_refs=[ref], evidence_ids=[eid])
        return dict(question="SYNTHETIC", answer="SYNTHETIC", contributions=[item], analyses=[],
                    negative_results=[], limits=[])
    if stage == "write_section":
        return dict(sections=[], references=[])
    if stage in ("write", "finalize"):
        refs = w.state.get("final_claims") or claims
        macro = next(m["macro"] for m in reversed(context["metrics"]) if m["claim_ref"] in refs)
        return dict(title="SYNTHETIC", sections=[dict(name="Results", claim_refs=refs, tex="SYNTHETIC " + macro)],
                    references=[], figures=[])
    if stage == "peer_review":
        return dict(decision="accept", reason="SYNTHETIC", dimensions=scores, required_experiments=[], claim_refs=[],
                    inspected=[dict(path="workspace/evaluate.py", claim_ref=claims[0], finding="SYNTHETIC")])
    if stage == "rebuttal":
        return dict(response="SYNTHETIC", evidence_ids=[], required_experiments=[])
    if stage == "meta_review":
        return dict(decision="accept", reason="SYNTHETIC", claim_refs=claims, required_experiments=[])
    if stage == "final_judgment":
        return {"verdicts": [dict(claim_ref=r, verdict="supported", reason="SYNTHETIC") for r in w.state["final_claims"]]}
    raise AssertionError(stage)


@pytest.fixture
def w(tmp_path, monkeypatch):
    import paperagents.knowledge
    import paperagents.writing

    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC fixture; not scientific evidence")
    w = Workflow(project)
    w.config["execution"]["sandbox"] = "none"
    w.config["loops"].update(seeds=[1], confirm_seeds=[2], test_seeds=[3], evolve_rounds=2, target_good=2)

    def knowledge(workflow):
        workflow.state["experts"] = [dict(expert_id="domain", role="domain", source_paper_ids=[])]
        workflow.state["knowledge"].setdefault("corpus", {"papers": []})

    def task(stage, subject, role, context, schema, key=None, validator=None):
        task_id = key or w.key(stage, subject)
        if task_id in w.state["tasks"]:
            return json.loads(Path(w.state["tasks"][task_id]["response_path"]).read_text())
        data = answer(w, stage, subject, context)
        C.validate(data, schema)
        if validator:
            validator(data)
        path = w.run_dir / "tasks" / task_id / "response.json"
        write_json(path, data)
        w.state["tasks"][task_id] = dict(task_id=task_id, stage=stage, status="completed", response_path=str(path))
        return data

    monkeypatch.setattr(paperagents.knowledge, "advance_knowledge", knowledge)
    monkeypatch.setattr(paperagents.writing, "compile_draft", lambda path, output: {"status": "compiled"})
    monkeypatch.setattr(w, "task", task)
    return w


def test_experiments_wait_for_explicit_execution(w):
    assert w.run()["status"] == "ready_for_experiment"
    assert not w.state["runs"]


def test_domain_revision_replans_an_unapproved_testbed(w, monkeypatch):
    task = w.task

    def pause_before_build(stage, *args, **kwargs):
        if stage == "build_testbed":
            w.pause("awaiting_retry", "Synthetic interrupted testbed construction")
        return task(stage, *args, **kwargs)

    monkeypatch.setattr(w, "task", pause_before_build)
    assert w.run()["status"] == "awaiting_retry"
    old_plan = w.key("testbed_plan", "plan-0")
    assert old_plan in w.state["tasks"]
    assert not w.state["protocol"]

    w.revise("domain", "Correct the evidence used to design the testbed")
    monkeypatch.setattr(w, "task", task)
    assert w.run()["status"] == "ready_for_experiment"
    assert w.key("testbed_plan", "plan-0-domain1") in w.state["tasks"]
    assert w.key("build_testbed", "protocol-0-domain1") in w.state["tasks"]
    assert w.key("protocol_review", "protocol-0-domain1") in w.state["tasks"]
    assert not w.state["runs"]


def test_complete_loop_versions_claims_and_opens_holdout_once(w):
    assert w.run(execute=True)["status"] == "completed"
    first, second = w.state["claims"]["idea@1"], w.state["claims"]["idea@2"]
    assert not first["active"] and second["verdict"] == "supported"
    assert any(g["experiment"] == "screen" and g["gate"] == "advance" for g in second["gates"])
    assert any(e["kind"] == "comparison" for e in w.state["evidence"].values())
    tests = [r for r in w.state["runs"].values() if r["split"] == "test"]
    assert len(tests) == 2  # one baseline and one frozen candidate
    runs = len(w.state["runs"])
    assert w.run(execute=True)["status"] == "completed" and len(w.state["runs"]) == runs
    with pytest.raises(ValueError, match="Holdout"):
        w.revise("evolve", "cannot tune on final results")
