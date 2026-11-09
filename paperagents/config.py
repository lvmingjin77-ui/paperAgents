"""Scientific questions live in Markdown; execution choices live in TOML."""

from copy import deepcopy
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {
    "research": {"lookback_years": 3, "core_papers": 2, "allow_temporary_experts": True},
    "backend": {"kind": "manual", "timeout_seconds": 1800},
    "glm": {
        "model": "glm-5.2",
        "fast_model": "glm-5.2",
        "base_url": "https://open.bigmodel.cn/api/anthropic",
        "api_key_env": "ZHIPU_API_KEY",
        "search_mcp_url": "https://open.bigmodel.cn/api/mcp/web_search_prime/mcp",
        "agent_command": "claude",
    },
    "execution": {
        "max_worker_attempts": 2,
        "experiment_timeout_seconds": 3600,
        "sandbox": "auto",
        "max_parallel": 4,
    },
    "resources": {
        "device": "local",
        "memory_gb": 16,
        "gpu": "",
        "wall_clock_days": 3,
        "max_worker_calls": 600,
        "python_executable": sys.executable,
    },
    "data": {
        "allowed_sources": [],
        "download": True,
        "license_notes": "Use permitted sources; record provenance.",
    },
    "loops": {
        "screen_top_n": 2,
        "exploratory_slots": 1,
        "evolve_rounds": 2,
        "target_good": 2,
        "engineering_budget": 2,
        "seeds": [11, 29],
        "confirm_seeds": [101, 211],
        "test_seeds": [503],
        "max_candidates_per_expert": 2,
        "outer_rounds": 2,
        "literature_rounds": 2,
        "review_rounds": 2,
        "reviewers": 2,
    },
    "output": {"venue": "unspecified", "template": "article", "page_limit": 9, "anonymous": True},
    "checkpoints": {"testbed": False, "final_method": False, "submission": False},
}


def toml_template():
    import json

    lines = ["# wall_clock_days counts running time only; pauses and approvals are not charged."]
    for section, fields in DEFAULTS.items():
        lines += ["", f"[{section}]"]
        for key, value in fields.items():
            lines.append(f"{key} = {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines) + "\n"


TEMPLATE = toml_template()


def load_config(project):
    config = deepcopy(DEFAULTS)
    path = Path(project) / "paperagents.toml"
    if path.exists():
        for section, fields in tomllib.loads(path.read_text()).items():
            if section not in config or not isinstance(fields, dict):
                raise ValueError(f"Unknown configuration section: {section}")
            for key, value in fields.items():
                if key not in config[section]:
                    raise ValueError(
                        f"Unknown configuration key: {section}.{key}; new runs use the 0.2 template"
                    )
                expected = type(config[section][key])
                if not (expected is float and type(value) in (int, float)) and type(value) is not expected:
                    raise ValueError(f"{section}.{key} must be {expected.__name__}")
                config[section][key] = value
    if config["backend"]["kind"] not in {"manual", "glm"} or config["execution"]["sandbox"] not in {"auto", "none"}:
        raise ValueError("backend.kind is manual or glm; execution.sandbox is auto or none")
    loops = config["loops"]
    if set(loops["seeds"]) & set(loops["confirm_seeds"]):
        raise ValueError("Confirmation uses new seeds, distinct from screening seeds")
    return config
