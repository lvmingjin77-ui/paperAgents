"""Operator inspection and control commands must not implicitly create research runs."""

import json

import pytest

from paperagents.cli import main
from paperagents.storage import write_json
from paperagents.workflow import Workflow, initialize_project


def files(project):
    return {
        str(p.relative_to(project)): (p.read_bytes(), p.stat().st_mtime_ns)
        for p in project.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "project"
    initialize_project(path, "Synthetic CLI fixture; no scientific work.")
    return path


def test_status_and_plan_do_not_initialize_or_lock_a_run(project, capsys):
    before = files(project)
    assert main(["status", str(project)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "not_started"
    assert main(["plan", str(project)]) == 0
    assert "knowledge" in json.loads(capsys.readouterr().out)["phases"]
    assert files(project) == before
    assert not (project / "runs").exists()
    assert "max_parallel" not in (project / "paperagents.toml").read_text()
    assert "paper_capabilities" not in (project / "paperagents.toml").read_text()


def test_status_reads_saved_run_even_when_scientific_input_changed(project, capsys):
    w = Workflow(project)
    (project / "research.md").write_text("A changed brief must not prevent inspecting existing progress.")
    before = files(project)
    assert main(["status", str(project)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["run_id"] == w.state["run_id"]
    assert result["phase"] == "knowledge"
    assert files(project) == before


@pytest.mark.parametrize(
    "command,arguments",
    [
        ("retry", ["missing-task"]),
        ("submit", ["missing-task", "missing-response.json"]),
        ("approve", ["testbed"]),
        ("revise", ["--from", "evolve", "--reason", "Synthetic revision"]),
    ],
)
def test_control_commands_require_existing_run(project, capsys, command, arguments):
    before = files(project)
    assert main([command, str(project), *arguments]) == 1
    assert "No active run" in capsys.readouterr().err
    assert files(project) == before
    assert not (project / "runs").exists()


def test_legacy_status_does_not_migrate_or_create_state(project, capsys):
    write_json(project / "active_run.json", {"run_id": "legacy"})
    write_json(project / "runs" / "legacy" / "state.json", {"status": "paused"})
    before = files(project)
    assert main(["status", str(project)]) == 1
    assert "Old run format" in capsys.readouterr().err
    assert files(project) == before
