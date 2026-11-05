"""Worker driver: run one isolated task with Claude Code as the agent and Zhipu GLM as its only model.

Invoked by the command backend as ``python -m paperagents.glm_worker <prompt.md>`` inside the
task's attempt directory. Claude Code's stream-json transcript goes to stdout, which the
coordinator stores as ``driver.log``; the web view renders it as the agent's step-by-step trace.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .config import ROOT, load_config


def main(argv: list[str]) -> int:
    prompt = Path(argv[0]).resolve()
    project = next((p for p in prompt.parents if (p / "paperagents.toml").is_file()), None)
    if project is None:
        print("glm_worker: cannot find the project's paperagents.toml", file=sys.stderr)
        return 2
    glm = load_config(project)["glm"]
    key = os.environ.get(glm["api_key_env"], "").strip()
    private_config = ROOT / ".env.glm.json"
    if not key and private_config.is_file():
        key = json.loads(private_config.read_text(encoding="utf-8"))["api_key"]
    if not key:
        print(f"glm_worker: set {glm['api_key_env']} to a Zhipu API key", file=sys.stderr)
        return 2
    env = {name: value for name, value in os.environ.items() if not name.startswith("ANTHROPIC_")}
    for name in ("CLAUDE_CODE_OAUTH_TOKEN", "CLAUDECODE", "CLAUDE_CODE_USE_BEDROCK",
                 "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY"):
        env.pop(name, None)
    env.update(ANTHROPIC_BASE_URL=glm["base_url"], ANTHROPIC_AUTH_TOKEN=key, ANTHROPIC_MODEL=glm["model"],
               ANTHROPIC_DEFAULT_OPUS_MODEL=glm["model"], ANTHROPIC_DEFAULT_SONNET_MODEL=glm["model"],
               ANTHROPIC_DEFAULT_HAIKU_MODEL=glm["fast_model"], ANTHROPIC_SMALL_FAST_MODEL=glm["fast_model"],
               CLAUDE_CODE_SUBAGENT_MODEL=glm["model"], CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1",
               API_TIMEOUT_MS="600000")
    env[glm["api_key_env"]] = key
    env["PAPERAGENTS_GLM_MCP_KEY"] = key
    # Literature search uses Zhipu's own search tool; the built-in WebSearch would need Anthropic.
    search = {"mcpServers": {"web-search-prime": {"type": "http", "url": glm["search_mcp_url"],
                              "headers": {"Authorization": "Bearer ${PAPERAGENTS_GLM_MCP_KEY}"}}}}
    instructions = (prompt.read_text(encoding="utf-8") + "\nAll generative model API calls must use "
                    + glm["model"] + " at the official BigModel endpoint. Never print credentials or copy "
                    f"them into artifacts, source code, commands or logs. {glm['model']} is text-only; record "
                    "visual evidence that cannot be verified from extracted text, tables or captions. "
                    "Follow this task's execution limits; research experiments are run separately by "
                    "the coordinator. If an experiment needs model API credentials, declare this "
                    "resource requirement without embedding the key in its workspace.\n")
    tools = "Read,Write,Edit,Glob,Grep,Bash,WebFetch"
    command = [glm["agent_command"], "-p", instructions,
               "--output-format", "stream-json", "--verbose", "--model", glm["model"],
               "--effort", "max", "--setting-sources", "", "--no-session-persistence",
               "--add-dir", str(project), str(ROOT), "--mcp-config", json.dumps(search),
               "--strict-mcp-config", "--permission-mode", "dontAsk", "--tools", tools,
               "--allowedTools", tools + ",mcp__web-search-prime__web_search_prime"]
    os.execvpe(command[0], command, env)
    return 0  # not reached


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
