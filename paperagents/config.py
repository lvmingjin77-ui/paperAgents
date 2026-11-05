"""Project configuration; the scientific brief stays in research.md."""

from __future__ import annotations

import copy
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "research": {"lookback_years": 3, "core_papers": 3, "allow_temporary_experts": True},
    "discussion": {"max_rounds": 2, "max_auto_revisions": 1, "max_evidence_rounds": 2,
                   "max_candidates_per_expert": 2},
    "backend": {"kind": "manual", "command": [], "timeout_seconds": 1800},
    "glm": {"model": "glm-5.2", "fast_model": "glm-5.2",
            "base_url": "https://open.bigmodel.cn/api/anthropic", "api_key_env": "ZHIPU_API_KEY",
            "search_mcp_url": "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp", "agent_command": "claude"},
    "execution": {"max_parallel": 4, "max_worker_attempts": 2,
                  "experiment_timeout_seconds": 21600, "paper_capabilities": []},
}
DEFAULT_TOML = '''# Scientific goals and constraints belong in research.md.
[research]
lookback_years = 3
# Number of core paper experts (2-5); the domain expert is always added.
core_papers = 3
allow_temporary_experts = true

[discussion]
# Author rebuttal + original-challenger recheck rounds before the novelty audit.
max_rounds = 2
# Automatic returns to the authors when synthesis and independent review both ask for revision.
max_auto_revisions = 1
# Bounded evidence collection; never executes candidate experiments.
max_evidence_rounds = 2
# Short, distinct proposals per expert; details live in referenced files.
max_candidates_per_expert = 2

[backend]
# manual: emit isolated worker requests; command: invoke an external agent driver;
# glm: every worker is Claude Code driven by Zhipu GLM (see [glm]); no other model API is called.
kind = "manual"
# An argv array, never a shell string. Placeholders: {request}, {response}, {prompt}.
command = []
timeout_seconds = 1800

[glm]
# Workers run the Claude Code CLI against Zhipu's Anthropic-compatible endpoint.
# The API key comes from this environment variable or the private .env.glm.json file.
model = "glm-5.2"
fast_model = "glm-5.2"
base_url = "https://open.bigmodel.cn/api/anthropic"
api_key_env = "ZHIPU_API_KEY"
search_mcp_url = "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp"
agent_command = "claude"

[execution]
max_parallel = 4
max_worker_attempts = 2
experiment_timeout_seconds = 21600
# Optional paper learning: "communication", "method_tools". Core understanding
# and source-code mapping are always loaded; these abilities remain available.
paper_capabilities = []
'''


def load_config(project: Path) -> dict:
    config = copy.deepcopy(DEFAULTS)
    path = project / "paperagents.toml"
    if path.exists():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        for section, settings in raw.items():
            if section not in config or not isinstance(settings, dict):
                raise ValueError(f"Unknown or invalid configuration section: {section}")
            for key, value in settings.items():
                if key not in config[section]:
                    raise ValueError(f"Unknown configuration key: {section}.{key}")
                config[section][key] = value
    for section, key in [("research", "lookback_years"), ("execution", "max_parallel"),
                         ("execution", "max_worker_attempts"), ("backend", "timeout_seconds"),
                         ("execution", "experiment_timeout_seconds")]:
        value = config[section][key]
        if type(value) is not int or value <= 0:
            raise ValueError(f"{section}.{key} must be a positive integer")
    core = config["research"]["core_papers"]
    if type(core) is not int or not 2 <= core <= 5:
        raise ValueError("research.core_papers must be an integer from 2 to 5")
    discussion = config["discussion"]
    for name, low, high in (("max_rounds", 1, 5), ("max_auto_revisions", 0, 3),
                            ("max_evidence_rounds", 0, 5), ("max_candidates_per_expert", 1, 5)):
        if type(discussion[name]) is not int or not low <= discussion[name] <= high:
            raise ValueError(f"discussion.{name} must be an integer from {low} to {high}")
    if type(config["research"]["allow_temporary_experts"]) is not bool:
        raise ValueError("research.allow_temporary_experts must be a boolean")
    capabilities = config["execution"]["paper_capabilities"]
    if not isinstance(capabilities, list) or any(
        not isinstance(item, str) or item not in {"communication", "method_tools"} for item in capabilities
    ):
        raise ValueError("execution.paper_capabilities accepts communication and method_tools only")
    backend = config["backend"]
    if backend["kind"] not in {"manual", "command", "glm"}:
        raise ValueError("backend.kind must be manual, command or glm")
    if backend["kind"] == "glm":  # a preset of the command backend
        backend.update(kind="command", driver="glm",
                       command=[sys.executable, "-m", "paperagents.glm_worker", "{prompt}"])
    if not isinstance(backend["command"], list) or not all(
        isinstance(arg, str) and arg for arg in backend["command"]
    ):
        raise ValueError("backend.command must be an argv array")
    if backend["kind"] == "command" and not backend["command"]:
        raise ValueError("command backend requires backend.command")
    return config
