"""Research handoff, portable expert assets, and the optional upstream idea seam."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from paperagents import v3


@pytest.fixture
def proposal():
    return {
        "title": "A controlled optimizer experiment",
        "problem": "Can bounded restart allocation improve search?",
        "hypothesis": "State-dependent restarts improve the score under equal compute.",
        "implementation_plan": ["Implement bounded restart allocation.", "Compare equal-budget controls."],
        "evaluation": {"metric": "combined_score", "controls": ["equal compute"],
                       "inconclusive": "too few successful seeds"},
        "source_refs": [{"source_id": "paper:one", "locator": "section 3"}],
        "unresolved_questions": ["Does the mechanism survive the ablation?"],
    }


def _export(tmp_path, proposal):
    skill = tmp_path / "knowledge_skill"
    (skill / "references").mkdir(parents=True)
    (skill / "scripts").mkdir()
    (skill / "SKILL.md").write_text("# Read constraints before planning.\n")
    (skill / "references" / "paper.md").write_text("Evidence anchor: section 3.\n")
    (skill / "scripts" / "check.py").write_text("# Readable tool definition, never executed.\n")
    expert = {"expert_id": "domain/restarts", "kind": "domain",
              "knowledge": {"mechanism": "stagnation-triggered restart"},
              "idea_trace": ["paper:one#section-3"], "code_tools": ["scripts/check.py"],
              "limitations": ["causal mechanism untested"], "source_paths": [skill]}
    task = v3.export_task(tmp_path / "run", proposal, [expert])
    return task, expert, skill


def test_export_preserves_proposal_and_complete_expert_assets_in_upstream_snapshot(tmp_path, proposal):
    from src.investigation.files import ensure_task_copy_in_results, load_instructions

    task, expert, skill = _export(tmp_path, proposal)
    snapshot = ensure_task_copy_in_results(task, tmp_path / "results")
    # The investigation cannot depend on the original host's expert directory.
    shutil.rmtree(skill)
    shutil.rmtree(task)
    context = json.loads((snapshot / v3.CONTEXT_FILE).read_text())
    assert context["proposal"] == proposal
    assert context["investigation_expert_mode"] == "materials_assisted_single_agent"
    record = json.loads((snapshot / context["experts"][0]["record_path"]).read_text())
    assert record["knowledge"] == expert["knowledge"]
    assert record["limitations"] == expert["limitations"]
    copied_skill = snapshot / record["source_paths"][0]
    assert (copied_skill / "SKILL.md").read_text().startswith("# Read constraints")
    assert (copied_skill / "references/paper.md").read_text().startswith("Evidence anchor")
    assert (copied_skill / "scripts/check.py").is_file()
    assert len(record["source_files"]) == 3
    for item in record["source_files"]:
        assert v3._hash(snapshot / item["path"]) == item["sha256"]
    template = v3.idea_instruction_path(snapshot, Path("unused"))
    rendered = load_instructions(template, snapshot, tmp_path / "results")
    assert f"{snapshot}/paperagents_context.json" in rendered
    assert "{{TASK_DIR}}" not in rendered
    assert "Harness Rubric Requirements" in rendered
    assert "Single-directory invariant" in rendered
    assert "does not invoke independent expert agents" in rendered


def test_reexport_is_idempotent_and_conflicts_leave_original_intact(tmp_path, proposal):
    task, expert, _ = _export(tmp_path, proposal)
    before = (task / "task.md").read_bytes()
    assert v3.export_task(task.parent, proposal, [expert]) == task
    changed = dict(proposal, hypothesis="A different, unreviewed hypothesis")
    with pytest.raises(FileExistsError, match="differs"):
        v3.export_task(task.parent, changed, [expert])
    assert (task / "task.md").read_bytes() == before
    assert not list(task.parent.glob(".paperagents-export-*"))
    (task / "task.md").write_text("Changed after export")
    with pytest.raises(FileExistsError):
        v3.export_task(task.parent, proposal, [expert])


def test_host_metadata_paths_resolve_to_copied_files_without_rewriting_scientific_text(tmp_path, proposal):
    from src.investigation.files import ensure_task_copy_in_results

    library = tmp_path / "library"
    paper_dir = library / "papers" / "v001"
    expert_dir = library / "experts" / "v002"
    (paper_dir / "tools").mkdir(parents=True)
    expert_dir.mkdir(parents=True)
    full_text = paper_dir / "full_text.md"
    tool = paper_dir / "tools" / "reproduce.py"
    full_text.write_text("The paper's complete mechanism and evidence.\n")
    tool.write_text("# Tool implementation retained for later execution.\n")
    source_record = {"_asset": {"path": str(paper_dir)},
                     "full_text_path": str(full_text), "code_tools": [str(tool)]}
    (paper_dir / "record.json").write_text(json.dumps(source_record))
    scientific_text = f"An observation originally documented at {full_text}; remains unverified."
    expert = {"expert_id": "paper-expert", "_asset": {"path": str(expert_dir)},
              "knowledge": {"claim": scientific_text}, "paper": source_record,
              "source_paths": [expert_dir, paper_dir]}
    (expert_dir / "record.json").write_text(json.dumps(expert, default=str))
    task = v3.export_task(tmp_path / "run", proposal, [expert])
    snapshot = ensure_task_copy_in_results(task, tmp_path / "results")
    shutil.rmtree(library)
    shutil.rmtree(task)
    context = json.loads((snapshot / v3.CONTEXT_FILE).read_text())
    record = json.loads((snapshot / context["experts"][0]["record_path"]).read_text())
    assert record["paper"] == source_record, "Source metadata is retained as provenance"
    assert record["knowledge"]["claim"] == scientific_text
    for original in (paper_dir, expert_dir, paper_dir / "tools", full_text, tool,
                     paper_dir / "record.json", expert_dir / "record.json"):
        mapped = context["source_path_map"][str(original)]
        assert mapped == record["source_path_map"][str(original)]
        assert not Path(mapped).is_absolute()
        assert (snapshot / mapped).exists()
    copied_paper = snapshot / context["source_path_map"][str(full_text)]
    assert copied_paper.read_text().startswith("The paper's complete mechanism")
    copied_record = snapshot / context["source_path_map"][str(paper_dir / "record.json")]
    assert json.loads(copied_record.read_text()) == source_record
    for item in record["source_files"]:
        assert v3._hash(snapshot / item["path"]) == item["sha256"]
    assert "never fall back to accessing the host path" in (snapshot / v3.IDEA_PROMPT).read_text()


def test_original_tool_paths_compose_through_frozen_asset_origin_maps(tmp_path, proposal):
    library = tmp_path / "library"
    paper = library / "paper-v1"
    expert_dir = library / "expert-v1"
    (paper / "sources").mkdir(parents=True)
    (expert_dir / "sources").mkdir(parents=True)
    (paper / "sources/tool.py").write_text("# actual frozen paper tool\n")
    (expert_dir / "sources/knowledge.md").write_text("Frozen expert knowledge\n")
    original_tool = str(tmp_path / "old-machine" / "tool.py")
    original_notes = str(tmp_path / "old-machine" / "knowledge.md")
    missing = str(tmp_path / "old-machine" / "missing.py")
    escaped = str(tmp_path / "old-machine" / "escape.py")
    frozen = {"_asset": {"path": str(paper), "origin_map": {
        str(tmp_path / "old-machine" / "paper"): ".",
        original_tool: "sources/tool.py", missing: "sources/missing.py",
        escaped: "../expert-v1/sources/knowledge.md"}}}
    (paper / "asset.json").write_text(json.dumps(frozen))
    expert = {"expert_id": "paper-expert", "code_tools": [{"entrypoint": original_tool}],
              "_asset": {"path": str(expert_dir),
                         "origin_map": {original_notes: "sources/knowledge.md"}},
              "source_paths": [expert_dir, paper]}
    task = v3.export_task(tmp_path / "run", proposal, [expert])
    shutil.rmtree(library)
    context = json.loads((task / v3.CONTEXT_FILE).read_text())
    record = json.loads((task / context["experts"][0]["record_path"]).read_text())
    for paths in (context["source_path_map"], record["source_path_map"]):
        assert (task / paths[original_tool]).read_text() == "# actual frozen paper tool\n"
        assert (task / paths[original_notes]).read_text() == "Frozen expert knowledge\n"
        assert paths[original_tool] == paths[str(paper / "sources/tool.py")]
        assert missing not in paths
        assert escaped not in paths
    assert record["code_tools"] == expert["code_tools"]


def test_rejects_nonportable_assets_and_does_not_publish_partial_task(tmp_path, proposal):
    asset = tmp_path / "expert"
    asset.mkdir()
    external = tmp_path / "private.txt"
    external.write_text("Not part of this expert")
    (asset / "escape").symlink_to(external)
    with pytest.raises(ValueError, match="unsupported entry"):
        v3.export_task(tmp_path / "run", proposal,
                       [{"expert_id": "one", "source_paths": [asset]}])
    assert not (tmp_path / "run/task").exists()


@pytest.mark.parametrize("damage", ["missing_prompt", "path_escape", "schema", "symlink_context"])
def test_marked_tasks_cannot_silently_drop_expert_context(tmp_path, proposal, damage):
    task = v3.export_task(tmp_path / "run", proposal, [])
    path = task / v3.CONTEXT_FILE
    context = json.loads(path.read_text())
    if damage == "missing_prompt":
        (task / v3.IDEA_PROMPT).unlink()
    elif damage == "path_escape":
        context["idea_prompt_path"] = "../../untrusted.md"
        path.write_text(json.dumps(context))
    elif damage == "schema":
        context["schema_version"] = 999
        path.write_text(json.dumps(context))
    else:
        path.unlink()
        path.symlink_to(tmp_path / "missing.json")
    with pytest.raises(ValueError):
        v3.idea_instruction_path(task, Path("default.md"))


@pytest.mark.parametrize("exported", [True, False])
def test_investigation_hook_forwards_original_runner_contract(tmp_path, proposal, monkeypatch, exported):
    from src.investigation import cli, script_runners
    from src.investigation.models import IdeaGenerationResult

    if exported:
        task = v3.export_task(tmp_path / "run", proposal, [])
    else:
        task = tmp_path / "plain_task"
        task.mkdir()
    original = tmp_path / "custom.md"
    original.write_text("ordinary custom instruction")
    received = {}
    expected = IdeaGenerationResult(output="not executed", exit_code=0, idea_dir=tmp_path / "idea")

    def fake_runner(**kwargs):
        received.update(kwargs)
        return expected

    monkeypatch.setattr(script_runners, "run_idea_generation", fake_runner)
    arguments = dict(agent="codex", agent_model="test-model", task_dir=task,
                     results_dir=tmp_path / "results", cycle_index=3,
                     output_dir=tmp_path / "idea", instruct_path=original,
                     timeout_seconds=30, harness_evaluated_attempts=True,
                     containerize=True, validation_feedback="repair schema only")
    assert cli.run_idea_generation(**arguments) is expected
    assert received["instruct_path"] == (task / v3.IDEA_PROMPT if exported else original)
    for key, value in arguments.items():
        if key != "instruct_path":
            assert received[key] == value
    assert received["script_path"] == v3.REPO_ROOT / "src/scripts/idea.sh"
    assert not (tmp_path / "idea").exists(), "The original shell must own output directory creation"


def test_build_command_and_run_fix_cwd_preserve_arguments_and_default_to_dry_run(tmp_path, proposal, monkeypatch):
    task = v3.export_task(tmp_path / "space in run", proposal, [])
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="planned")

    monkeypatch.setattr(v3.subprocess, "run", fake_run)
    overrides = ["agent.name=codex", "execution.dry_run=false"]
    result = v3.run_v3(task, overrides, capture_output=True, text=True, check=True)
    assert result.stdout == "planned"
    argv, kwargs = calls[0]
    assert argv[1:5] == ["-m", "src.agsci.main", "run", str(task)]
    assert argv[-1] == "--dry-run"
    assert kwargs["cwd"] == v3.REPO_ROOT
    assert kwargs["check"] is True
    assert overrides == ["agent.name=codex", "execution.dry_run=false"]
    assert "--dry-run" not in v3.build_command(task, dry_run=False)
    with pytest.raises(ValueError, match="task_dir"):
        v3.build_command(task, ["task.dir=other"])
    with pytest.raises(ValueError, match="sequence"):
        v3.build_command(task, "agent.name=codex")
    with pytest.raises(ValueError, match="fixes cwd"):
        v3.run_v3(task, cwd="/tmp")


def test_upstream_dry_run_accepts_exported_brief_without_launching_children(tmp_path, proposal, monkeypatch, capsys):
    from src.pipeline import cli, phases

    task = v3.export_task(tmp_path / "run", proposal, [])

    def forbidden(*args, **kwargs):
        raise AssertionError("dry-run must not launch subprocesses")

    monkeypatch.setattr(phases.subprocess, "run", forbidden)
    # macOS's default /var/folders uses a symlink; upstream requires a real path.
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    # Exercise the actual upstream parser and phase command builders on our brief.
    argv = v3.build_command(task, ["container.env_file=", f"paths.run_dir={tmp_path / 'planned'}"])
    assert cli.main(argv[4:]) == 0
    output = capsys.readouterr()
    assert not (task / "task_contract.json").exists()
    assert "task_drafting" in output.out + output.err


@pytest.mark.parametrize("custom", [True, False])
def test_run_resolves_temp_directory_without_mutating_environment(tmp_path, proposal, monkeypatch, custom):
    task = v3.export_task(tmp_path / "run", proposal, [])
    real_temp = tmp_path / "real_temp"
    real_temp.mkdir()
    alias = tmp_path / "temp_alias"
    alias.symlink_to(real_temp, target_is_directory=True)
    received = {}

    def fake_run(argv, **kwargs):
        received.update(kwargs)
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(v3.subprocess, "run", fake_run)
    environment = {"TMPDIR": str(alias), "PAPERAGENTS_TEST_MARKER": "preserved"}
    if custom:
        v3.run_v3(task, env=environment)
    else:
        monkeypatch.setenv("TMPDIR", str(alias))
        monkeypatch.setenv("PAPERAGENTS_TEST_MARKER", "preserved")
        v3.run_v3(task)
    assert received["env"]["TMPDIR"] == str(real_temp.resolve())
    assert received["env"]["PAPERAGENTS_TEST_MARKER"] == "preserved"
    assert environment["TMPDIR"] == str(alias)
    if custom:
        assert set(received["env"]) == set(environment)
    else:
        assert v3.os.environ["TMPDIR"] == str(alias)
