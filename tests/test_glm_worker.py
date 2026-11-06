"""Exercise real driver launch with a local fixture executable, never a model API."""

import json
import os
import subprocess
import sys

import pytest

from paperagents.config import ROOT


@pytest.mark.skipif(os.name != "posix", reason="Executable fixture uses a POSIX shebang")
def test_large_task_is_read_from_file_instead_of_command_arguments(tmp_path):
    agent = tmp_path / "local-agent"
    agent.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "from pathlib import Path\n"
        "prompt = Path(os.environ['PAPERAGENTS_PROBE_PROMPT'])\n"
        "print(json.dumps({'launcher': sys.argv[sys.argv.index('-p') + 1], "
        "'argv_bytes': sum(len(x.encode()) for x in sys.argv), "
        "'prompt_bytes': prompt.stat().st_size}))\n"
    )
    agent.chmod(0o755)
    (tmp_path / "paperagents.toml").write_text(
        f'[glm]\nagent_command = {json.dumps(str(agent))}\napi_key_env = "PAPERAGENTS_PROBE_KEY"\n'
    )
    prompt = tmp_path / "prompt.md"
    prompt.write_text("SYNTHETIC_EVIDENCE_ONLY\n" * 100_000)
    result = subprocess.run(
        [sys.executable, "-m", "paperagents.glm_worker", str(prompt)],
        cwd=tmp_path,
        env={
            "PATH": os.defpath,
            "PYTHONPATH": str(ROOT),
            "PAPERAGENTS_PROBE_KEY": "NOT_A_CREDENTIAL",
            "PAPERAGENTS_PROBE_PROMPT": str(prompt),
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    received = json.loads(result.stdout)
    assert received["prompt_bytes"] == prompt.stat().st_size > 2_000_000
    assert received["argv_bytes"] < 10_000
    assert str(prompt) in received["launcher"]
    assert "SYNTHETIC_EVIDENCE_ONLY" not in received["launcher"]
