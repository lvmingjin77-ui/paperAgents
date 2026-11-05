"""Regression checks for mutation guards, repair history and worker cleanup."""

from copy import deepcopy
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from paperagents import providers
from paperagents.storage import digest, read_json, write_json
from paperagents.workflow import Workflow, initialize_project
from tests.paperagents.test_workflow import advance, answer


def snapshot(directory):
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


@pytest.fixture
def workflow(tmp_path):
    project = tmp_path / "research"
    initialize_project(project, "SYNTHETIC_TEST_FIXTURE")
    return Workflow(project)


@pytest.mark.parametrize("operation", ["submit", "revise", "feedback", "run"])
@pytest.mark.parametrize("changed", ["brief", "research_config", "frozen_brief", "frozen_config"])
def test_changed_research_cannot_partially_mutate_run(workflow, operation, changed):
    workflow.run()
    task = workflow.summary()["pending"][0]
    request = read_json(workflow.run_dir / "requests" / task["task_id"] / "request.json")
    response = workflow.project / "response.json"
    write_json(response, answer(request, workflow.project))
    feedback = workflow.project / "feedback.json"
    write_json(feedback, {"evaluation_split": "search", "run_id": "fixture",
                          "code_version": "fixture", "data_description": "fixture",
                          "configuration": {"fixture": True}, "findings": ["fixture"],
                          "artifact_refs": ["fixture"]})
    if changed == "brief":
        (workflow.project / "research.md").write_text("A changed question")
    elif changed == "research_config":
        path = workflow.project / "paperagents.toml"
        path.write_text(path.read_text().replace("lookback_years = 3", "lookback_years = 4"))
    elif changed == "frozen_brief":
        (workflow.run_dir / "research.md").write_text("A changed snapshot")
    else:
        path = workflow.run_dir / "config.json"
        data = read_json(path)
        data["research"]["lookback_years"] = 99
        write_json(path, data)
    before = snapshot(workflow.run_dir)
    state = deepcopy(workflow.state)
    with pytest.raises(ValueError, match="research input changed|Research input changed"):
        if operation == "submit":
            workflow.submit(task["task_id"], response)
        elif operation == "revise":
            workflow.revise("scope", "Test rejected mutation")
        elif operation == "feedback":
            workflow.add_feedback(feedback)
        else:
            workflow.run()
    assert workflow.state == state
    assert snapshot(workflow.run_dir) == before


def test_backend_changes_do_not_change_the_research_contract(workflow):
    workflow.run()
    task = workflow.summary()["pending"][0]
    request = read_json(workflow.run_dir / "requests" / task["task_id"] / "request.json")
    path = workflow.project / "paperagents.toml"
    path.write_text(path.read_text().replace("timeout_seconds = 1800", "timeout_seconds = 2400"))
    workflow.config["execution"]["max_parallel"] = 2
    response = workflow.project / "response.json"
    write_json(response, answer(request, workflow.project))
    workflow.submit(task["task_id"], response)
    assert workflow.state["tasks"][task["task_id"]]["status"] == "completed"


def test_explicit_new_run_preserves_damaged_history(workflow):
    advance(workflow, stop="corpus")
    old_run = workflow.run_dir
    task = next(task for task in workflow.state["tasks"].values() if task["stage"] == "scope")
    path = old_run / "artifacts" / f"{task['task_id']}.json"
    write_json(path, {"tampered": True})
    before = snapshot(old_run)
    with pytest.raises(ValueError, match="Accepted artifact changed.*--new"):
        Workflow(workflow.project)
    fresh = Workflow(workflow.project, new=True)
    assert fresh.state == {}
    assert fresh.run(new=True)["status"] == "awaiting_workers"
    assert fresh.run_dir != old_run
    assert snapshot(old_run) == before
    assert read_json(workflow.project / "active_run.json")["run_id"] == fresh.state["run_id"]


@pytest.mark.parametrize("phase", ["hypothesis", "synthesis"])
def test_rejected_review_and_synthesis_return_as_actual_revision_evidence(workflow, phase):
    summary = advance(workflow, stop="proposal_review")
    task_id = summary["pending"][0]["task_id"]
    directory = workflow.run_dir / "requests" / task_id
    request = read_json(directory / "request.json")
    response = answer(request, workflow.project)
    response["accepted"] = False
    response["decision_assessment"]["agree"] = False
    response["checks"][0]["verdict"] = "fail"
    response["blocking_issues"] = ["UNIQUE_FIXTURE_REVIEW_BLOCK: missing matched control"]
    write_json(directory / "response.json", response)
    workflow.submit(task_id, directory / "response.json")
    assert workflow.run()["status"] == "needs_evidence"
    workflow.revise(phase, "Resolve the actual review")
    summary = workflow.run()
    for pending in summary["pending"]:
        revised = read_json(workflow.run_dir / "requests" / pending["task_id"] / "request.json")
        context = revised["context"]["revision_context"]
        assert context["previous_synthesis"]
        assert context["proposal_reviews"][0]["data"]["blocking_issues"] == response["blocking_issues"]
        assert context["proposal_reviews"][0]["data"]["accepted"] is False
        for record in context["previous_synthesis"] + context["proposal_reviews"]:
            assert read_json(Path(record["artifact_path"])) == record["data"]
            assert digest(record["data"]) == record["artifact_hash"]
        if phase == "hypothesis":
            assert "candidates" not in revised["context"]
            assert all(record["data"]["expert_id"] == revised["subject_id"]
                       for record in context["previous_hypotheses"])


def test_worker_prompt_references_one_frozen_request_without_repeating_it(workflow):
    summary = workflow.run()
    task_id = summary["pending"][0]["task_id"]
    directory = workflow.run_dir / "requests" / task_id
    request = read_json(directory / "request.json")
    prompt = (directory / "prompt.md").read_text()
    assert "Read request.json" in prompt
    assert request["output_path"] in prompt
    assert request["context"]["research_brief"] not in prompt
    for skill in request["skills"]:
        assert skill["instructions"]
        assert skill["instructions"] not in prompt
    assert len(prompt) < 2000


def test_markdown_brief_is_copied_exactly_before_any_workflow_is_started(tmp_path):
    source = tmp_path / "input.md"
    content = "# 明确的研究问题\r\n\r\n验证机制 A。\r\n\r\n## 约束\r\n保留划分。\r\n".encode("utf-8")
    source.write_bytes(content)
    project = tmp_path / "new-project"
    initialize_project(project, brief_file=source)
    assert (project / "research.md").read_bytes() == content
    assert not (project / "active_run.json").exists()
    assert Workflow(project).summary()["status"] == "not_started"


@pytest.mark.parametrize("content", [b"# Heading\n", b"\n\n", b"\xff"])
def test_invalid_markdown_does_not_leave_a_partial_project(tmp_path, content):
    source = tmp_path / "input.md"
    source.write_bytes(content)
    project = tmp_path / "new-project"
    with pytest.raises(ValueError):
        initialize_project(project, brief_file=source)
    assert not project.exists()


@pytest.mark.skipif(os.name != "posix", reason="The command backend owns POSIX process groups")
def test_timeout_kills_child_even_when_leader_exits_on_sigterm(tmp_path, monkeypatch):
    monkeypatch.setattr(providers, "_PROCESS_GROUP_GRACE_SECONDS", 0.2)
    child = tmp_path / "child.py"
    child.write_text("import os,signal,time\nfrom pathlib import Path\n"
                     "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                     "Path('child.pid').write_text(str(os.getpid()))\n"
                     "while True: time.sleep(0.1)\n")
    driver = tmp_path / "driver.py"
    driver.write_text("import os,subprocess,sys,time\nfrom pathlib import Path\n"
                      "Path('driver.pid').write_text(str(os.getpid()))\n"
                      "subprocess.Popen([sys.executable,'child.py'])\n"
                      "while True: time.sleep(0.1)\n")
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        ok, reason = providers.execute_command({"command": [sys.executable, str(driver)], "timeout_seconds": 0.7}, tmp_path)
        assert not ok and reason == "driver_timeout_or_interruption"
        assert unrelated.poll() is None
        pid = int((tmp_path / "child.pid").read_text())
        deadline = time.monotonic() + 2
        while True:
            status = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
            if not status or status.startswith("Z"):
                break
            assert time.monotonic() < deadline, f"Worker child survived timeout: {pid} ({status})"
            time.sleep(0.02)
    finally:
        if (tmp_path / "driver.pid").exists():
            try:
                os.killpg(int((tmp_path / "driver.pid").read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
        unrelated.terminate()
        unrelated.wait(timeout=5)
