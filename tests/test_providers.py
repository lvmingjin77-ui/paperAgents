"""No API calls: tiny local worker fixtures exercise the OS boundary."""

import json
import os
import platform
import select
import shutil
import subprocess
import sys
import time

import pytest

from paperagents.providers import _stop_process_group, _worker_boundary, execute_command


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
@pytest.mark.skipif(not shutil.which("claude"), reason="Claude Code CLI integration test")
def test_claude_bash_uses_private_temp_without_model_calls(worker):
    """Exercise the installed Bash tool through MCP, with no credentials or network."""
    request, _, _, config = worker
    request = request.resolve()
    command, env, _ = _worker_boundary(config, request, [shutil.which("claude"), "mcp", "serve"])
    env = {
        key: value
        for key, value in env.items()
        if key
        in {
            "PATH",
            "LANG",
            "LC_ALL",
            "SHELL",
            "HOME",
            "TMPDIR",
            "TMPPREFIX",
            "CLAUDE_CODE_TMPDIR",
            "CLAUDE_CONFIG_DIR",
            "XDG_CACHE_HOME",
        }
    }
    env.update(SHELL="/bin/zsh", DISABLE_AUTOUPDATER="1", CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1")
    with (request / "worker.sb").open("a") as profile:
        profile.write("(deny network*)\n")
    with (request / "mcp.log").open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=request,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            start_new_session=True,
        )

        def send(message):
            process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
            process.stdin.flush()

        def receive(message_id):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                remaining = max(0, deadline - time.monotonic())
                assert select.select([process.stdout], [], [], remaining)[0], "MCP response timed out"
                line = process.stdout.readline()
                assert line, (request / "mcp.log").read_text()
                response = json.loads(line)
                if response.get("id") == message_id:
                    assert "error" not in response, response
                    return response["result"]
            pytest.fail("MCP response timed out")

        try:
            send(
                {
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "paperagents-boundary-test", "version": "1"},
                    },
                }
            )
            receive(1)
            send({"method": "notifications/initialized"})
            send(
                {
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "Bash",
                        "arguments": {
                            "command": "cat <<'EOF'\npaperagents-bash-ok\nEOF",
                            "timeout": 5000,
                        },
                    },
                }
            )
            result = receive(2)
            assert not result.get("isError"), result
            output = "\n".join(item.get("text", "") for item in result["content"])
            assert "paperagents-bash-ok" in output, output
            # This directory is created by Claude itself before Bash can execute.
            assert (request / ".runtime" / "tmp" / f"claude-{os.getuid()}").is_dir()
        finally:
            _stop_process_group(process)
            process.stdin.close()
            process.stdout.close()


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
