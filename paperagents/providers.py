"""External agent transport. No synthetic scientific results or implicit model calls."""

from __future__ import annotations

import os
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


def execute_command(config: dict, request_dir: Path) -> tuple[bool, str]:
    """A driver reads request.json/prompt.md and writes response.json.

    Each worker gets a separate process and cwd. This is context separation,
    not an OS sandbox: configure the driver/container's actual permissions.
    """
    paths = {name: str(request_dir / filename) for name, filename in {
        "request": "request.json", "response": "response.json", "prompt": "prompt.md"
    }.items()}
    argv = []
    for argument in config["command"]:
        for key, value in paths.items():
            argument = argument.replace("{" + key + "}", value)
        argv.append(argument)
    with (request_dir / "driver.log").open("ab") as log:
        process = subprocess.Popen(argv, cwd=request_dir, stdout=log, stderr=log, start_new_session=True)
        try:
            code = process.wait(timeout=config["timeout_seconds"])
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            if not _stop_process_group(process):
                return False, "driver_timeout_cleanup_incomplete"
            return False, "driver_timeout_or_interruption"
    if code != 0:
        return False, f"driver_exit_{code}"
    if not (request_dir / "response.json").is_file():
        return False, "driver_missing_response"
    return True, ""
