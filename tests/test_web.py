import json

import pytest

from paperagents.storage import write_json
from paperagents.web import View, redact


@pytest.fixture
def project(tmp_path):
    run = tmp_path / "runs" / "run1"
    request = run / "tasks" / "t1" / "attempt-001" / "request.json"
    request.parent.mkdir(parents=True)
    write_json(request, {"context": {"api_key": "sensitive-value"}, "instruction": "test"})
    write_json(request.parent / "response.json", {"message": "observed result"})
    write_json(
        run / "state/research.json",
        {
            "phase": "exchange",
            "status": "ready",
            "tasks": {
                "t1": {
                    "stage": "exchange",
                    "subject": "paper1",
                    "role": "expert",
                    "status": "completed",
                    "request_path": str(request),
                    "response_path": str(request.parent / "response.json"),
                }
            },
            "runs": {"r1": {"outcome": "impl_failed", "reason": "ImportError"}},
        },
    )
    write_json(tmp_path / "active_run.json", {"run_id": "run1"})
    (request.parent / "driver.log").write_text(
        "\n".join(
            json.dumps(e)
            for e in [
                {"type": "thinking_tokens"},
                {"type": "system", "subtype": "thinking_tokens"},
                {
                    "type": "assistant",
                    "message": {"content": [{"type": "tool_use", "id": "x", "name": "Read"}]},
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": "x",
                                "is_error": True,
                                "content": "File missing",
                            }
                        ]
                    },
                },
            ]
        )
    )
    return tmp_path


def test_new_state_and_pool(project):
    view = View(project)
    assert view.runs()["active"] == "run1"
    assert view.state()["phase"] == "exchange"
    assert view.pool()[0]["output"]["message"] == "observed result"
    assert view.task("t1")["request"]["context"]["api_key"] == "[REDACTED]"


def test_noise_filtered_tool_errors_retained(project):
    view = View(project)
    task = view.task("t1")
    assert len(task["attempts"][0]["transcript"]) == 2
    errors = view.errors()
    assert any(e.get("tool") == "Read" and e["error"] == "File missing" for e in errors)
    assert any(e.get("run_id") == "r1" for e in errors)


def test_file_boundary_and_private_files(project):
    view = View(project)
    (project / ".env").write_text("private")
    for name in [".env", "../outside", "/etc/passwd"]:
        with pytest.raises(ValueError):
            view.file(name)
    (project / "link").symlink_to("/etc/passwd")
    with pytest.raises(ValueError):
        view.file("link")


def test_no_old_run_format(project):
    write_json(project / "runs/old/state.json", {"status": "completed"})
    assert len(View(project).runs()["runs"]) == 1
    with pytest.raises(ValueError):
        View(project).state("old")


def test_redaction():
    value = redact({"api_key": "private", "text": "password=private"})
    assert "private" not in json.dumps(value)


@pytest.mark.parametrize("stage", ["testbed_plan", "write_section", "rebuttal", "final_judgment"])
def test_new_research_outputs_remain_in_pool(project, stage):
    view = View(project)
    state = view.state()
    state["tasks"]["t1"]["stage"] = stage
    write_json(project / "runs/run1/state/research.json", state)
    assert view.pool()[0]["stage"] == stage
