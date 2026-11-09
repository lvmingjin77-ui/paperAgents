"""External agent transport. No synthetic scientific results or implicit model calls."""

from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import time
from pathlib import Path


_PROCESS_GROUP_GRACE_SECONDS = 5.0


def _stop_process_group(process: subprocess.Popen) -> bool:
    """Stop this worker's session even when its leader exits before its children."""

    def signal_group(signum: int) -> bool:
        try:
            os.killpg(process.pid, signum)
            return True
        except ProcessLookupError:
            return False

    if signal_group(signal.SIGTERM):
        deadline = time.monotonic() + _PROCESS_GROUP_GRACE_SECONDS
        while time.monotonic() < deadline:
            process.poll()
            if not signal_group(0):
                break
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        else:
            # Waiting for the leader alone misses children that ignore SIGTERM.
            signal_group(signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        return False
    return True


def _worker_boundary(config: dict, request_dir: Path, argv: list[str]) -> tuple[list[str], dict, dict]:
    """Protect sealed inputs while allowing the model transport to reach its API.

    Driver HOME/cache/temp are private to this attempt, so we need not grant writes to
    the user's real home or Claude settings. This is independent of experiment network
    isolation: research workers need network access for models and literature retrieval.
    """
    denied = [Path(value).resolve() for value in config.get("deny_read_paths", [])]
    writable = [request_dir, *[Path(value).resolve() for value in config.get("write_paths", [])]]
    for supplied in config.get("deny_read_paths", []) + config.get("write_paths", []):
        if not Path(supplied).is_absolute():
            raise ValueError("Worker boundary paths must be absolute")
    mode = config.get("sandbox", "auto")
    if mode not in {"auto", "none"}:
        raise ValueError("sandbox must be auto or none")
    env = os.environ.copy()
    private = request_dir / ".runtime"
    for name in ("home", "tmp", "cache", "claude"):
        (private / name).mkdir(parents=True, exist_ok=True)
    env.update(
        HOME=str(private / "home"),
        TMPDIR=str(private / "tmp"),
        # zsh uses TMPPREFIX independently for heredoc temporary files.
        TMPPREFIX=str(private / "tmp" / "zsh"),
        # Claude's Bash tool defaults to /tmp even when TMPDIR is set.
        CLAUDE_CODE_TMPDIR=str(private / "tmp"),
        XDG_CACHE_HOME=str(private / "cache"),
        CLAUDE_CONFIG_DIR=str(private / "claude"),
    )
    metadata = {
        "mode": mode,
        "deny_read_paths": [str(p) for p in denied],
        "write_paths": [str(p) for p in writable],
        "network": "allowed for agent API/tools",
    }
    if mode == "none":
        metadata.update(
            enforcement="none", warning="Explicitly unconfined worker; sealed data is not OS-protected"
        )
        return argv, env, metadata
    for path in denied:
        if not path.exists():
            raise ValueError(f"Sealed worker path does not exist: {path}")
    for path in writable:
        if not path.is_dir():
            raise ValueError(f"Worker write directory does not exist: {path}")
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        rules = ["(version 1)", "(allow default)", "(deny file-write*)"]
        for path in writable:
            rules.append("(allow file-write* (subpath " + json.dumps(str(path)) + "))")
        rules.append('(allow file-write* (literal "/dev/null"))')
        for path in denied:
            selector = "subpath" if path.is_dir() else "literal"
            rule = "(" + selector + " " + json.dumps(str(path)) + ")"
            rules += ["(deny file-read* " + rule + ")", "(deny file-write* " + rule + ")"]
            # A writable ancestor must not be renamed to move the sealed path outside
            # the deny rule. Creating siblings remains permitted.
            for parent in path.parents:
                if any(parent == root or parent.is_relative_to(root) for root in writable):
                    rules.append("(deny file-write-unlink (literal " + json.dumps(str(parent)) + "))")
        profile = request_dir / "worker.sb"
        profile.write_text("\n".join(rules) + "\n")
        metadata["enforcement"] = "macos-seatbelt"
        return [shutil.which("sandbox-exec"), "-f", str(profile), *argv], env, metadata
    if platform.system() == "Linux" and shutil.which("bwrap"):
        command = [
            shutil.which("bwrap"),
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
            "--ro-bind",
            "/",
            "/",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
        ]
        for path in writable:
            command += ["--bind", str(path), str(path)]
        for path in denied:
            if path.is_dir():
                command += ["--tmpfs", str(path), "--remount-ro", str(path)]
            else:
                command += ["--ro-bind", "/dev/null", str(path)]
        metadata["enforcement"] = "linux-bubblewrap"
        return [*command, "--chdir", str(request_dir), *argv], env, metadata
    raise ValueError(
        "No worker sandbox available; install bubblewrap on Linux or explicitly choose sandbox=none"
    )


def execute_command(config: dict, request_dir: Path, cancel=None) -> tuple[bool, str]:
    """Run one independent driver, protecting sealed files and coordinator writes.

    The driver reads request.json/prompt.md and writes response.json. Model credentials
    stay in its inherited environment; only the separately isolated experiment runner
    removes credentials and disables networking. Boundary configuration never embeds keys.
    ``cancel`` (a threading.Event) stops a driver running in a worker thread, which does not
    receive KeyboardInterrupt itself.
    """
    request_dir = Path(request_dir).resolve()
    paths = {
        name: str(request_dir / filename)
        for name, filename in {
            "request": "request.json",
            "response": "response.json",
            "prompt": "prompt.md",
        }.items()
    }
    argv = []
    for argument in config["command"]:
        for key, value in paths.items():
            argument = argument.replace("{" + key + "}", value)
        argv.append(argument)
    try:
        command, env, boundary = _worker_boundary(config, request_dir, argv)
    except (OSError, ValueError) as exc:
        (request_dir / "boundary.json").write_text(
            json.dumps({"enforcement": "unavailable", "reason": str(exc)}, indent=2)
        )
        return False, "worker_boundary_unavailable: " + str(exc)
    (request_dir / "boundary.json").write_text(json.dumps(boundary, indent=2))
    with (request_dir / "driver.log").open("ab") as log:
        try:
            process = subprocess.Popen(
                command, cwd=request_dir, env=env, stdout=log, stderr=log, start_new_session=True
            )
        except OSError as exc:
            return False, "driver_launch_failed: " + str(exc)
        try:
            deadline = time.monotonic() + config["timeout_seconds"]
            while True:
                try:
                    code = process.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if cancel is not None and cancel.is_set():
                        _stop_process_group(process)
                        return False, "driver_interrupted"
                    if time.monotonic() > deadline:
                        raise
        except subprocess.TimeoutExpired:
            if not _stop_process_group(process):
                return False, "driver_timeout_cleanup_incomplete"
            return False, "driver_timeout"
        except KeyboardInterrupt:
            _stop_process_group(process)
            raise
    if code != 0:
        return False, f"driver_exit_{code}"
    if not (request_dir / "response.json").is_file():
        return False, "driver_missing_response"
    return True, ""
