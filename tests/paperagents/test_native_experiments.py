"""Real tiny CPU subprocesses test the bridge; fixtures are not research evidence."""

import sys
from pathlib import Path

import pytest

from paperagents.experiments import REVIEW_CRITERIA, run_experiment
from paperagents.storage import read_json, write_json
from paperagents.workflow import Workflow, initialize_project
from src.investigation.program_spec import render_default_program_spec_toml
from tests.paperagents.test_workflow import advance


@pytest.fixture
def workflow(tmp_path):
    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE: recover y=2*x using local test data")
    workflow = Workflow(project)
    assert advance(workflow)["status"] == "completed"
    return workflow


EVALUATOR = '''import argparse, json, subprocess, sys
from pathlib import Path
parser = argparse.ArgumentParser()
parser.add_argument('--program_path')
parser.add_argument('--results_dir')
args = parser.parse_args()
rows = json.loads(Path('data.json').read_text())
errors = []
for row in rows:
    result = subprocess.run([sys.executable, args.program_path, str(row['x'])],
                            check=True, stdout=subprocess.PIPE, text=True)
    errors.append(abs(float(result.stdout.strip()) - row['y']))
out = Path(args.results_dir)
(out / 'metrics.json').write_text(json.dumps({'combined_score': -sum(errors)/len(errors), 'samples': len(rows)}))
(out / 'correct.json').write_text(json.dumps({'correct': True}))
'''


def build_response(summary, *, evaluator=EVALUATOR, candidate="print(float(__import__('sys').argv[1])*2)\n"):
    pending = summary["pending"][0]
    request = read_json(Path(pending["request_path"]))
    workspace = Path(request["context"]["workspace"])
    (workspace / "evaluate.py").write_text(evaluator)
    write_json(workspace / "data.json", [{"x": 1, "y": 2}, {"x": 2, "y": 4}])
    for name, program in (("program_0", "print(float(__import__('sys').argv[1]))\n"), ("program_1", candidate)):
        directory = workspace / name
        (directory / "src").mkdir(parents=True, exist_ok=True)
        (directory / "program_spec.toml").write_text(render_default_program_spec_toml())
        (directory / "src" / "program.py").write_text(program)
    data = {"proposal_hash": request["context"]["proposal_hash"], "evaluation_split": "search",
            "evaluator": "evaluate.py", "baseline": "program_0", "candidate": "program_1",
            "python_executable": sys.executable,
            "protocol": {"data_description": "SYNTHETIC TEST ONLY: two deterministic arithmetic inputs in data.json",
                         "configuration": {"seed": 0, "samples": 2, "dependencies": "Python standard library"},
                         "metrics": {"combined_score": "Negative mean absolute error; larger is better"},
                         "controls": ["Identical input rows and evaluator for both programs"],
                         "decision_rules": ["Inspect whether candidate reduces arithmetic error"]},
            "limitations": ["Synthetic test only, not scientific validation"]}
    write_json(Path(pending["response_path"]), data)
    return workspace


def review_response(summary, *, accepted=True):
    pending = summary["pending"][0]
    request = read_json(Path(pending["request_path"]))
    data = {"proposal_hash": request["context"]["proposal_hash"],
            "build_hash": request["context"]["build_hash"], "accepted": accepted,
            "checks": [{"criterion": name, "evidence": ["SYNTHETIC TEST FIXTURE: inspected evaluate.py and data.json"],
                        "verdict": "pass" if accepted else "unknown"} for name in REVIEW_CRITERIA],
            "blocking_issues": [] if accepted else ["Synthetic missing protocol evidence"]}
    write_json(Path(pending["response_path"]), data)


def prepare(workflow, **kwargs):
    first = run_experiment(workflow)
    assert first["phase"] == "experiment_build"
    workspace = build_response(first, **kwargs)
    second = run_experiment(workflow)
    assert second["phase"] == "experiment_review"
    review_response(second)
    ready = run_experiment(workflow)
    assert ready["status"] == "ready_for_experiment"
    return workspace, Path(ready["experiment_dir"])


def test_native_cpu_execution_feedback_and_idempotent_resume(workflow, monkeypatch):
    import paperagents.v3
    def no_legacy(*args, **kwargs):
        raise AssertionError("Legacy ideation/investigation must not run")
    monkeypatch.setattr(paperagents.v3, "run_v3", no_legacy)
    workspace, cycle = prepare(workflow)
    assert not (cycle / "executions").exists()
    result = run_experiment(workflow, execute=True)
    assert result["status"] == "awaiting_workers"
    assert result["experiment_status"] == "completed"
    assert result["ideation"]["phase"] == "hypothesis"
    assert result["ideation"]["status"] == "awaiting_workers"
    baseline = read_json(cycle / "results" / "baseline.json")
    candidate = read_json(cycle / "results" / "candidate.json")
    assert baseline["metrics"]["combined_score"] == -1.5
    assert candidate["metrics"]["combined_score"] == 0.0
    assert candidate["evaluation_manifest"]["producer"] == "isolated_evaluator"
    assert not (workspace / "program_0" / "metrics.json").exists()
    feedback = read_json(Path(result["feedback_path"]))
    assert feedback["findings"]["comparison_valid"] is True
    assert feedback["candidate_ref"] == result["candidate_ref"]
    hypothesis_task = result["ideation"]["pending"][0]
    request = read_json(workflow.run_dir / "requests" / hypothesis_task["task_id"] / "request.json")
    assert request["context"]["search_feedback"][0] == feedback
    assert "revise-hypotheses" in {item["id"] for item in request["skills"]}
    before = (cycle / "results" / "baseline.json").stat().st_mtime_ns
    resumed = Workflow(workflow.project)
    again = run_experiment(resumed, execute=True)
    assert again["feedback_path"] == result["feedback_path"]
    assert len(resumed.state["feedback"]) == 1
    assert resumed.state["iteration"] == 2
    assert before == (cycle / "results" / "baseline.json").stat().st_mtime_ns


def test_no_execution_without_explicit_execute(workflow):
    _, cycle = prepare(workflow)
    for _ in range(2):
        assert run_experiment(Workflow(workflow.project))["status"] == "ready_for_experiment"
    assert not (cycle / "executions").exists()
    assert workflow.state["feedback"] == []


def test_independent_reviewer_rejection_blocks_execution(workflow):
    build_response(run_experiment(workflow))
    pending = run_experiment(workflow)
    review_response(pending, accepted=False)
    result = run_experiment(workflow, execute=True)
    assert result["status"] == "needs_evidence"
    assert result["phase"] == "review_rejected"
    assert not (Path(result["experiment_dir"]) / "executions").exists()


@pytest.mark.parametrize("target", ["workspace", "request", "response", "export"])
def test_frozen_inputs_cannot_change_after_review(workflow, target):
    workspace, cycle = prepare(workflow)
    if target == "workspace":
        (workspace / "data.json").write_text("[]")
    elif target == "request":
        path = cycle / "requests" / "experiment_review" / "request.json"
        data = read_json(path)
        data["context"]["proposal_hash"] = "changed"
        write_json(path, data)
    elif target == "response":
        path = cycle / "requests" / "experiment_build" / "response.json"
        data = read_json(path)
        data["limitations"].append("changed")
        write_json(path, data)
    else:
        (Path(workflow.state["task_dir"]) / "task.md").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        run_experiment(workflow, execute=True)
    assert not (cycle / "executions").exists()


def test_missing_results_are_inconclusive_and_not_zero(workflow):
    _, cycle = prepare(workflow, evaluator="print('test evaluator deliberately omits results')\n")
    result = run_experiment(workflow, execute=True)
    feedback = read_json(Path(result["feedback_path"]))
    records = feedback["findings"]["results"]
    assert records["baseline"]["status"] == "inconclusive"
    assert "metrics" not in records["baseline"]
    assert "candidate" not in records
    assert feedback["findings"]["comparison_valid"] is False
    assert not (cycle / "executions" / "candidate").exists()


def test_candidate_execution_failure_returns_real_feedback(workflow):
    prepare(workflow, candidate="raise RuntimeError('fixture candidate failure')\n")
    result = run_experiment(workflow, execute=True)
    feedback = read_json(Path(result["feedback_path"]))
    results = feedback["findings"]["results"]
    assert results["baseline"]["status"] == "completed"
    assert results["candidate"]["status"] == "inconclusive"
    assert results["candidate"]["returncode"] != 0
    assert "metrics" not in results["candidate"]
    log = Path(results["candidate"]["log_path"])
    assert "fixture candidate failure" in log.read_text()
    assert "fixture candidate failure" in results["candidate"]["log_tail"]
    assert str(log) in results["candidate"]["artifact_hashes"]
    assert str(log) in feedback["artifact_refs"]
    assert not feedback["findings"]["comparison_valid"]


def test_feedback_commit_resume_does_not_duplicate(workflow, monkeypatch):
    prepare(workflow)
    original = workflow.revise
    def interrupted(*args, **kwargs):
        raise RuntimeError("synthetic interruption after feedback persistence")
    monkeypatch.setattr(workflow, "revise", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        run_experiment(workflow, execute=True)
    assert len(workflow.state["feedback"]) == 1
    assert workflow.state["iteration"] == 1
    monkeypatch.setattr(workflow, "revise", original)
    resumed = Workflow(workflow.project)
    result = run_experiment(resumed)
    assert result["experiment_status"] == "completed"
    assert len(resumed.state["feedback"]) == 1
    assert resumed.state["iteration"] == 2


def test_missing_resources_can_be_supplied_later(workflow):
    pending = run_experiment(workflow)
    request = read_json(Path(pending["pending"][0]["request_path"]))
    response = Path(pending["pending"][0]["response_path"])
    write_json(response, {"status": "needs_evidence", "proposal_hash": request["context"]["proposal_hash"],
                          "missing_resources": ["Actual dataset unavailable"], "limitations": []})
    assert run_experiment(workflow)["status"] == "needs_evidence"
    build_response(pending)
    assert run_experiment(workflow)["phase"] == "experiment_review"


def test_build_rejects_symlinks_and_fabricated_result_files(workflow, tmp_path):
    pending = run_experiment(workflow)
    workspace = build_response(pending)
    outside = tmp_path / "external.json"
    outside.write_text("{}")
    (workspace / "external.json").symlink_to(outside)
    with pytest.raises(ValueError, match="Symlink"):
        run_experiment(workflow)
    (workspace / "external.json").unlink()
    write_json(workspace / "program_0" / "metrics.json", {"combined_score": 1})
    with pytest.raises(ValueError, match="must not provide evaluation results"):
        run_experiment(workflow)


def test_changed_research_cannot_start_execution(workflow):
    _, cycle = prepare(workflow)
    (workflow.project / "research.md").write_text("different task")
    with pytest.raises(ValueError, match="Research input changed"):
        run_experiment(workflow, execute=True)
    assert not (cycle / "executions").exists()


def test_review_requires_five_evidenced_unique_checks(workflow):
    build_response(run_experiment(workflow))
    pending = run_experiment(workflow)
    review_response(pending)
    response = Path(pending["pending"][0]["response_path"])
    review = read_json(response)
    review["checks"][0]["evidence"] = []
    write_json(response, review)
    with pytest.raises(ValueError, match="evidence"):
        run_experiment(workflow, execute=True)


def test_failed_command_cannot_promote_its_response(workflow, tmp_path):
    driver = tmp_path / "failed_driver.py"
    driver.write_text("import json,sys\njson.dump({'status':'needs_evidence'},open(sys.argv[1],'w'))\nsys.exit(7)\n")
    workflow.config["backend"].update(kind="command", command=[sys.executable, str(driver), "{response}"])
    result = run_experiment(workflow)
    assert result["status"] == "awaiting_workers"
    assert result["pending"][0]["attempts"] == 2
    assert result["pending"][0]["error"] == "driver_exit_7"
    assert not Path(result["pending"][0]["response_path"]).exists()


def test_command_backend_does_not_accept_unreceipted_response(workflow, tmp_path):
    pending = run_experiment(workflow)
    build_response(pending)
    driver = tmp_path / "failed.py"
    driver.write_text("raise SystemExit(7)\n")
    workflow.config["backend"].update(kind="command", command=[sys.executable, str(driver)])
    result = run_experiment(workflow)
    assert result["status"] == "awaiting_workers"
    assert result["phase"] == "experiment_build"
    assert result["pending"][0]["attempts"] == 2


def test_review_rebuild_preserves_rejected_evidence(workflow):
    build_response(run_experiment(workflow))
    pending = run_experiment(workflow)
    review_response(pending, accepted=False)
    rejection = run_experiment(workflow)
    original = Path(rejection["experiment_dir"])
    result = run_experiment(workflow, rebuild=True)
    assert Path(result["experiment_dir"]).name == "r001-build002"
    assert read_json(original / "state.json")["phase"] == "review_rejected"
    request = read_json(Path(result["pending"][0]["request_path"]))
    assert request["context"]["previous_rejected_build"]["review"]["accepted"] is False


def test_next_approved_iteration_starts_a_fresh_cycle(workflow):
    prepare(workflow)
    run_experiment(workflow, execute=True)
    assert advance(workflow)["status"] == "completed"
    result = run_experiment(workflow)
    assert result["phase"] == "experiment_build"
    assert Path(result["experiment_dir"]).name == "r002"
    request = read_json(Path(result["pending"][0]["request_path"]))
    assert request["context"]["previous_experiment"]["feedback"]["ideation_iteration"] == 1


def test_legacy_export_is_not_a_native_experiment(workflow):
    from paperagents.v3 import export_task, export_receipt
    task = export_task(workflow.project / "legacy", workflow.one("synthesis")["proposal"], [], mode="legacy")
    workflow.state.update(task_dir=str(task), export_receipt=export_receipt(task))
    workflow._save()
    with pytest.raises(ValueError, match="native expert-loop export"):
        run_experiment(workflow)


@pytest.mark.parametrize("stage", ["experiment_build", "experiment_review"])
@pytest.mark.parametrize("invalid", ["{", '{"status":"invalid"}'])
def test_invalid_command_outputs_are_archived_and_retried(workflow, tmp_path, stage, invalid):
    pending = run_experiment(workflow)
    if stage == "experiment_review":
        build_response(pending)
        pending = run_experiment(workflow)
        review_response(pending)
        valid = read_json(Path(pending["pending"][0]["response_path"]))
        Path(pending["pending"][0]["response_path"]).unlink()
    else:
        valid = {"status": "needs_evidence", "proposal_hash": pending["proposal_hash"],
                 "missing_resources": ["Actual dataset unavailable"], "limitations": []}
    template = tmp_path / "valid.json"
    write_json(template, valid)
    driver = tmp_path / "retry.py"
    driver.write_text("import pathlib,sys\n"
                      "response=pathlib.Path(sys.argv[1]); counter=pathlib.Path('calls.txt')\n"
                      "calls=int(counter.read_text())+1 if counter.exists() else 1\n"
                      "counter.write_text(str(calls))\n"
                      "response.write_text(sys.argv[3] if calls==1 else pathlib.Path(sys.argv[2]).read_text())\n")
    workflow.config["backend"].update(kind="command", command=[sys.executable, str(driver), "{response}", str(template), invalid])
    result = run_experiment(workflow)
    assert result["status"] == ("needs_evidence" if stage == "experiment_build" else "ready_for_experiment")
    directory = Path(pending["pending"][0]["request_path"]).parent
    assert (directory / "calls.txt").read_text() == "2"
    assert (directory / "validation_feedback.json").is_file()
    assert list(directory.glob("response.rejected-*.json"))
    state = read_json(Path(result["experiment_dir"]) / "state.json")
    assert state["requests"][stage]["driver_success_response_hash"]


def test_registration_interruption_recovers_frozen_cycle(workflow):
    first = run_experiment(workflow)
    active = workflow.run_dir / "experiments" / "active.json"
    active.unlink()
    resumed = run_experiment(Workflow(workflow.project))
    assert resumed["experiment_dir"] == first["experiment_dir"]
    assert resumed["pending"][0]["request_path"] == first["pending"][0]["request_path"]


def test_resume_after_expert_revision_before_experiment_commit(workflow, monkeypatch):
    import paperagents.experiments as experiments
    prepare(workflow)
    save = experiments._save
    def interrupted(workflow, cycle, state):
        if state["phase"] == "complete":
            raise RuntimeError("synthetic interruption after revision")
        return save(workflow, cycle, state)
    monkeypatch.setattr(experiments, "_save", interrupted)
    with pytest.raises(RuntimeError, match="synthetic interruption"):
        run_experiment(workflow, execute=True)
    assert workflow.state["iteration"] == 2
    monkeypatch.setattr(experiments, "_save", save)
    resumed = Workflow(workflow.project)
    result = run_experiment(resumed)
    assert result["experiment_status"] == "completed"
    assert len(resumed.state["feedback"]) == 1
    assert resumed.state["iteration"] == 2


def test_reviewed_secondary_candidate_runs_as_program_2_under_the_same_evaluator(tmp_path):
    from tests.paperagents.test_discussion_loop import drive

    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE: recover y=2*x using local test data")
    workflow = Workflow(project)

    def respond(request, data):
        context = request["context"]
        if request["stage"] == "hypothesis":
            data["candidates"][0]["mechanism"] = f"Fixture mechanism of {context['expected_expert_id']}"
        if request["stage"] == "synthesis":
            data["secondary_ref"] = dict(context["candidate_targets"][1])
        return data

    assert drive(workflow, respond)["status"] == "completed"
    secondary_id = workflow.one("synthesis")["secondary_ref"]["idea_id"]
    first = run_experiment(workflow)
    request = read_json(Path(first["pending"][0]["request_path"]))
    assert request["context"]["secondary_candidate"]["idea_id"] == secondary_id
    assert "secondary" in request["output_schema"]["oneOf"][0]["required"]
    workspace = build_response(first)
    response = Path(first["pending"][0]["response_path"])
    data = read_json(response)
    with pytest.raises(ValueError, match="secondary"):
        run_experiment(workflow)  # build without program_2 / secondary field is rejected
    directory = workspace / "program_2"
    (directory / "src").mkdir(parents=True)
    (directory / "program_spec.toml").write_text(render_default_program_spec_toml())
    (directory / "src" / "program.py").write_text("print(float(__import__('sys').argv[1])*2 + 1)\n")
    data["secondary"] = "program_2"
    write_json(response, data)
    second = run_experiment(workflow)
    assert second["phase"] == "experiment_review"
    review_response(second)
    assert run_experiment(workflow)["status"] == "ready_for_experiment"
    result = run_experiment(workflow, execute=True)
    cycle = Path(result["experiment_dir"])
    assert read_json(cycle / "results" / "secondary.json")["metrics"]["combined_score"] == -1.0
    feedback = read_json(Path(result["feedback_path"]))
    assert feedback["secondary_ref"]["idea_id"] == secondary_id
    assert feedback["findings"]["comparison_valid"] is True


def test_objections_settled_by_experiment_become_required_tests(tmp_path):
    from tests.paperagents.test_discussion_loop import SOURCE, drive, objection

    project = tmp_path / "project"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE: recover y=2*x using local test data")
    workflow = Workflow(project)

    def respond(request, data):
        stage, context = request["stage"], request["context"]
        if stage == "challenge" and context["expected_expert_id"] == "paper:p0":
            for review in data["reviews"]:
                if review["idea_id"] == "domain-idea":
                    review["objections"] = [objection("paper:p0/1")]
        if stage == "rebuttal":
            data["responses"] = [dict(r, action="experiment", argument="Ablate the shared feature")
                                 for r in data["responses"]]
        if stage == "recheck":
            data["verdicts"] = [dict(v, status="experiment") for v in data["verdicts"]]
        if stage == "proposal_review":
            assert [t["objection_id"] for t in context["required_tests"]] == ["paper:p0/1"]
        return data

    assert drive(workflow, respond)["status"] == "completed"
    first = run_experiment(workflow)
    request = read_json(Path(first["pending"][0]["request_path"]))
    assert request["context"]["required_tests"][0]["author_plan"] == "Ablate the shared feature"
    build_response(first)
    response = Path(first["pending"][0]["response_path"])
    with pytest.raises(ValueError, match="objection_tests|protocol requires"):
        run_experiment(workflow)
    data = read_json(response)
    data["protocol"]["objection_tests"] = [{"objection_id": "paper:p0/1", "design": "Run the ablation arm"}]
    write_json(response, data)
    second = run_experiment(workflow)
    review_response(second)
    run_experiment(workflow)
    workflow.state["auto_revisions"] = 1  # budget spent in this ideation cycle
    workflow._save()
    result = run_experiment(workflow, execute=True)
    feedback = read_json(Path(result["feedback_path"]))
    assert feedback["required_tests"][0]["design"] == "Run the ablation arm"
    assert workflow.state["auto_revisions"] == 0  # fresh budget for the next ideation cycle
