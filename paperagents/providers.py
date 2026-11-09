"""Worker transport: run one agent driver per task attempt, hiding the sealed test set."""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import time


def _stop(process: subprocess.Popen) -> None:
    """Stop the driver's whole session, including children that outlive the leader."""
    for signum in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, signum)
        except ProcessLookupError:
            break
        try:
            process.wait(timeout=5)
            break
        except subprocess.TimeoutExpired:
            continue


def _boundary(argv: list[str], request_dir: Path, sealed: list[Path], mode: str) -> list[str]:
    """Workers may read and write freely (they need network and tools) but never read sealed paths."""
    sealed = [p for p in sealed if p.exists()]
    if not sealed or mode == "none":
        return argv
    if platform.system() == "Darwin" and shutil.which("sandbox-exec"):
        rules = ["(version 1)", "(allow default)"]
        for path in sealed:
            rule = f"({'subpath' if path.is_dir() else 'literal'} {json.dumps(str(path))})"
            rules += [f"(deny file-read* {rule})", f"(deny file-write* {rule})"]
        profile = request_dir / "worker.sb"
        profile.write_text("\n".join(rules) + "\n")
        return [shutil.which("sandbox-exec"), "-f", str(profile), *argv]
    if platform.system() == "Linux" and shutil.which("bwrap"):
        command = [shutil.which("bwrap"), "--bind", "/", "/", "--dev", "/dev", "--proc", "/proc"]
        for path in sealed:
            command += ["--tmpfs", str(path)] if path.is_dir() else ["--ro-bind", "/dev/null", str(path)]
        return [*command, *argv]
    raise ValueError('No worker sandbox to hide the sealed test set; set execution.sandbox = "none" explicitly')


def execute_command(config: dict, request_dir: Path, cancel=None) -> tuple[bool, str]:
    """Run one driver that reads prompt.md and writes response.json in its attempt directory.

    ``cancel`` (a threading.Event) stops a driver running in a worker thread, which does not
    receive KeyboardInterrupt itself.
    """
    request_dir = Path(request_dir).resolve()
    argv = [a.replace("{prompt}", str(request_dir / "prompt.md")) for a in config["command"]]
    private = request_dir / ".runtime"
    env = dict(os.environ)
    # Private home, temp and agent configuration per attempt; the user's own settings stay untouched.
    for name, variable in (("home", "HOME"), ("tmp", "TMPDIR"), ("cache", "XDG_CACHE_HOME"), ("claude", "CLAUDE_CONFIG_DIR")):
        (private / name).mkdir(parents=True, exist_ok=True)
        env[variable] = str(private / name)
    env.update(TMPPREFIX=str(private / "tmp" / "zsh"), CLAUDE_CODE_TMPDIR=str(private / "tmp"))
    try:
        command = _boundary(argv, request_dir, [Path(p) for p in config["deny_read_paths"]], config["sandbox"])
    except ValueError as exc:
        return False, str(exc)
    with (request_dir / "driver.log").open("ab") as log:
        try:
            process = subprocess.Popen(command, cwd=request_dir, env=env, stdout=log, stderr=log, start_new_session=True)
        except OSError as exc:
            return False, f"driver_launch_failed: {exc}"
        deadline = time.monotonic() + config["timeout_seconds"]
        try:
            while True:
                try:
                    code = process.wait(timeout=1)
                    break
                except subprocess.TimeoutExpired:
                    if cancel is not None and cancel.is_set():
                        _stop(process)
                        return False, "driver_interrupted"
                    if time.monotonic() > deadline:
                        _stop(process)
                        return False, "driver_timeout"
        except KeyboardInterrupt:
            _stop(process)
            raise
    if code != 0:
        return False, f"driver_exit_{code}"
    if not (request_dir / "response.json").is_file():
        return False, "driver_missing_response"
    return True, ""
