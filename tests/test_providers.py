"""No API calls: tiny local worker fixtures exercise the OS boundary."""

import json
import platform
import shutil
import sys

import pytest

from paperagents.providers import execute_command


@pytest.fixture
def worker(tmp_path):
    request = tmp_path / "attempt"
    workspace = tmp_path / "workspace"
    request.mkdir()
    workspace.mkdir()
    (request / "request.json").write_text("{}")
    (request / "prompt.md").write_text("synthetic worker only")
    sealed = workspace / "data" / "sealed.txt"
    sealed.parent.mkdir()
    sealed.write_text("synthetic-sealed-marker")
    (workspace / "public.txt").write_text("public-marker")
    config = {
        "command": [sys.executable, str(request / "worker.py")],
        "timeout_seconds": 5,
        "sandbox": "auto",
        "deny_read_paths": [str(sealed)],
        "write_paths": [str(workspace)],
    }
    return request, workspace, sealed, config


def run_source(request, config, source):
    (request / "worker.py").write_text(source)
    return execute_command(config, request)


MAC = pytest.mark.skipif(
    platform.system() != "Darwin" or not shutil.which("sandbox-exec"), reason="macOS sandbox test"
)


@MAC
def test_worker_reads_public_writes_response_and_workspace(worker):
    request, workspace, sealed, config = worker
    ok, error = run_source(
        request,
        config,
        f"""from pathlib import Path
import os
assert Path({str(workspace / "public.txt")!r}).read_text() == 'public-marker'
Path({str(workspace / "method.py")!r}).write_text('print("fixture")')
Path(os.environ['HOME'], 'claude-cache').write_text('cache')
Path('response.json').write_text('{{"ok":true}}')
""",
    )
    assert ok, error + (request / "driver.log").read_text()
    assert json.loads((request / "boundary.json").read_text())["enforcement"] == "macos-seatbelt"


@MAC
@pytest.mark.parametrize("action", ["read", "write", "unlink", "rename_parent", "hardlink", "outside_write"])
def test_worker_cannot_access_sealed_or_move_it_outside_boundary(worker, action):
    request, workspace, sealed, config = worker
    target = repr(str(sealed))
    actions = {
        "read": f"Path({target}).read_text()",
        "write": f'Path({target}).write_text("changed")',
        "unlink": f"Path({target}).unlink()",
        "rename_parent": f"Path({str(sealed.parent)!r}).rename({str(workspace / 'renamed')!r})",
        "hardlink": f"os.link({target}, {str(workspace / 'alias')!r})",
        "outside_write": f'Path({str(workspace.parent / "coordinator.json")!r}).write_text("changed")',
    }
    ok, error = run_source(
        request,
        config,
        "from pathlib import Path\nimport os\n"
        + actions[action]
        + '\nPath("response.json").write_text("{}")',
    )
    assert not ok
    assert error.startswith("driver_exit_")
    assert sealed.read_text() == "synthetic-sealed-marker"
    assert not (workspace / "alias").exists()


@MAC
def test_sealed_directory_is_protected_recursively(worker):
    request, workspace, sealed, config = worker
    config["deny_read_paths"] = [str(sealed.parent)]
    ok, _ = run_source(
        request,
        config,
        f'from pathlib import Path\nPath({str(sealed)!r}).read_text()\nPath("response.json").write_text("{{}}")',
    )
    assert not ok


def test_missing_sandbox_requires_explicit_choice(worker, monkeypatch):
    request, workspace, sealed, config = worker
    monkeypatch.setattr(shutil, "which", lambda _: None)
    ok, error = run_source(
        request, config, 'from pathlib import Path\nPath("response.json").write_text("{}")'
    )
    assert not ok and error.startswith("worker_boundary_unavailable:")
    assert not (request / "response.json").exists()
    config["sandbox"] = "none"
    ok, error = execute_command(config, request)
    assert ok, error
    assert json.loads((request / "boundary.json").read_text())["enforcement"] == "none"


def test_relative_boundary_paths_are_rejected(worker):
    request, workspace, sealed, config = worker
    config["deny_read_paths"] = ["relative-secret"]
    ok, error = run_source(request, config, "")
    assert not ok and "absolute" in error
