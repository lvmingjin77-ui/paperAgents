"""Research routing with fake workers; never runs a model or an evaluator."""

from types import SimpleNamespace
from unittest.mock import Mock

from paperagents import experiments
from paperagents.storage import write_json


def workflow_at(tmp_path, status="completed"):
    workflow = SimpleNamespace(run_dir=tmp_path, state={"status": status}, start=Mock())
    workflow.run = Mock(return_value={"status": status, "phase": "export", "pending": []})
    return workflow


def cycle(workflow, number, status):
    name = f"r{number:03d}"
    write_json(workflow.run_dir / "experiments" / "active.json", {"cycle": name})
    write_json(workflow.run_dir / "experiments" / name / "state.json", {"status": status})


def test_experiment_budget_survives_repeated_invocations(tmp_path, monkeypatch):
    workflow = workflow_at(tmp_path)
    cycle(workflow, 1, "completed")
    execute = Mock(side_effect=AssertionError("Must not start another experiment"))
    monkeypatch.setattr(experiments, "run_experiment", execute)
    for _ in range(2):
        result = experiments.run_research(workflow, execute=True)
        assert result["research_status"] == "experiment_limit_reached"
        assert result["experiments_completed"] == 1
    assert workflow.run.call_count == 2  # Finish feedback-driven ideation even at the limit.
    execute.assert_not_called()


def test_interrupted_feedback_is_committed_before_resuming_ideation(tmp_path, monkeypatch):
    workflow = workflow_at(tmp_path)
    cycle(workflow, 1, "feedback_pending")

    def resume(workflow, *, execute):
        workflow.run.assert_not_called()
        assert execute is True
        cycle(workflow, 1, "completed")
        return {"status": "completed", "experiment_status": "completed"}

    monkeypatch.setattr(experiments, "run_experiment", resume)
    assert experiments.run_research(workflow, execute=True)["experiments_completed"] == 1
    workflow.run.assert_called_once()


def test_explicit_two_cycle_budget_continues_then_stops(tmp_path, monkeypatch):
    workflow = workflow_at(tmp_path)
    calls = []

    def execute_cycle(workflow, *, execute):
        assert execute
        calls.append(len(calls) + 1)
        cycle(workflow, calls[-1], "completed")
        return {"status": "completed", "experiment_status": "completed"}

    monkeypatch.setattr(experiments, "run_experiment", execute_cycle)
    result = experiments.run_research(workflow, execute=True, max_experiments=2)
    assert calls == [1, 2]
    assert result["research_status"] == "experiment_limit_reached"


def test_review_rejection_or_missing_resources_does_not_spin(tmp_path, monkeypatch):
    workflow = workflow_at(tmp_path)
    blocked = {"status": "needs_evidence", "phase": "experiment_build", "reason": "Missing data"}
    execute = Mock(return_value=blocked)
    monkeypatch.setattr(experiments, "run_experiment", execute)
    assert experiments.run_research(workflow, execute=True)["reason"] == "Missing data"
    execute.assert_called_once()


def test_without_execute_stops_at_reviewed_experiment(tmp_path, monkeypatch):
    workflow = workflow_at(tmp_path)
    execute = Mock(return_value={"status": "ready_for_experiment", "phase": "ready"})
    monkeypatch.setattr(experiments, "run_experiment", execute)
    assert experiments.run_research(workflow)["status"] == "ready_for_experiment"
    execute.assert_called_once_with(workflow, execute=False)
