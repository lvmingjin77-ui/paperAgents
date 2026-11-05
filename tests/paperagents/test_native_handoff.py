"""Native expert research cannot silently enter the old ideation loop."""

import json
from pathlib import Path
import shutil

import pytest

from paperagents import v3


@pytest.fixture
def research_materials(tmp_path):
    sources = tmp_path / "expert-sources"
    sources.mkdir()
    (sources / "notes.md").write_text("SYNTHETIC_FIXTURE: known mechanism and limitations.\n")
    proposal = {"title": "Synthetic native proposal", "problem": "Fixture research question",
                "hypothesis": "Fixture hypothesis", "mechanism": "Canonical fixture mechanism",
                "assumptions": ["Fixture assumption"], "falsification": "Fixture negative prediction",
                "implementation_plan": ["Implement exactly the reviewed fixture mechanism"],
                "evaluation": {"controls": "Matched fixture control"}}
    expert = {"expert_id": "domain", "knowledge": {"scope": "Synthetic fixture only"},
              "source_paths": [str(sources)], "limitations": ["No real scientific result"]}
    return proposal, expert, sources


def test_native_export_does_not_read_legacy_template_and_retains_reviewed_core(tmp_path, research_materials, monkeypatch):
    proposal, expert, _ = research_materials
    original = Path.read_text
    legacy_template = v3.REPO_ROOT / "src/prompts/idea.md"

    def read_without_legacy(path, *args, **kwargs):
        if path.resolve() == legacy_template.resolve():
            raise AssertionError("Native export must not load the legacy ideation template")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_without_legacy)
    task = v3.export_task(tmp_path / "native", proposal, [expert], mode="native")
    context = json.loads((task / v3.CONTEXT_FILE).read_text())
    assert context["investigation_expert_mode"] == "native_expert_loop"
    assert context["proposal"] == proposal
    prompt = (task / v3.IDEA_PROMPT).read_text()
    assert "Only the PaperAgents expert workflow may generate or revise" in prompt
    assert "experiment_build" in prompt and "experiment_review" in prompt
    assert "create-idea" not in prompt
    assert "idea_bundle" not in prompt
    assert "one agent assisted" not in prompt
    brief = (task / "task.md").read_text()
    assert proposal["mechanism"] in brief
    assert proposal["falsification"] in brief
    assert "upstream task drafting" not in brief
    assert "Return search feedback" in brief
    v3.verify_export(task, v3.export_receipt(task))


@pytest.mark.parametrize("entry", ["build", "dry_run", "execute", "idea_hook"])
def test_native_task_is_rejected_by_all_legacy_entrypoints(tmp_path, research_materials, monkeypatch, entry):
    proposal, expert, _ = research_materials
    task = v3.export_task(tmp_path / "native", proposal, [expert], mode="native")

    def forbidden(*args, **kwargs):
        raise AssertionError("Legacy execution must not start for a native task")

    monkeypatch.setattr(v3.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="paperagents experiment or paperagents research"):
        if entry == "build":
            v3.build_command(task)
        elif entry == "dry_run":
            v3.run_v3(task)
        elif entry == "execute":
            v3.run_v3(task, dry_run=False, expected_receipt=v3.export_receipt(task))
        else:
            v3.idea_instruction_path(task, tmp_path / "legacy-default.md")


def test_original_investigation_hook_cannot_reenter_single_agent_ideation(tmp_path, research_materials, monkeypatch):
    from src.investigation import cli, script_runners

    proposal, expert, _ = research_materials
    task = v3.export_task(tmp_path / "native", proposal, [expert], mode="native")

    def forbidden(**kwargs):
        raise AssertionError("Original idea shell runner must not be invoked")

    monkeypatch.setattr(script_runners, "run_idea_generation", forbidden)
    with pytest.raises(ValueError, match="legacy single-agent ideation runner is disabled"):
        cli.run_idea_generation(
            agent="codex", agent_model="fixture", task_dir=task, results_dir=tmp_path / "results",
            cycle_index=1, output_dir=tmp_path / "idea", instruct_path=Path("unused.md"),
            timeout_seconds=30, harness_evaluated_attempts=True, containerize=True,
            validation_feedback="",
        )
    assert not (tmp_path / "idea").exists()


def test_native_assets_and_receipt_remain_portable(tmp_path, research_materials):
    proposal, expert, sources = research_materials
    task = v3.export_task(tmp_path / "native", proposal, [expert], mode="native")
    receipt = v3.export_receipt(task)
    copied = tmp_path / "portable-task"
    shutil.copytree(task, copied)
    original_notes = str(sources / "notes.md")
    shutil.rmtree(sources)
    shutil.rmtree(task)
    v3.verify_export(copied, receipt)
    context = json.loads((copied / v3.CONTEXT_FILE).read_text())
    record = json.loads((copied / context["experts"][0]["record_path"]).read_text())
    assert record["knowledge"] == expert["knowledge"]
    assert (copied / record["source_path_map"][original_notes]).read_text().startswith("SYNTHETIC_FIXTURE")
    assert (copied / context["source_path_map"][original_notes]).is_file()


def test_legacy_exports_keep_the_original_template_and_default_behavior(tmp_path, research_materials):
    proposal, expert, _ = research_materials
    default = v3.export_task(tmp_path / "default", proposal, [expert])
    explicit = v3.export_task(tmp_path / "legacy", proposal, [expert], mode="legacy")
    assert v3.export_receipt(default) == v3.export_receipt(explicit)
    context = json.loads((explicit / v3.CONTEXT_FILE).read_text())
    assert context["investigation_expert_mode"] == "materials_assisted_single_agent"
    template = v3.idea_instruction_path(explicit, tmp_path / "unused.md")
    assert template.read_text().startswith((v3.REPO_ROOT / "src/prompts/idea.md").read_text().rstrip())
    assert "upstream task drafting" in (explicit / "task.md").read_text()
    assert v3.build_command(explicit)[-1] == "--dry-run"


def test_export_modes_are_explicit_and_cannot_overwrite_each_other(tmp_path, research_materials):
    proposal, expert, _ = research_materials
    root = tmp_path / "native"
    task = v3.export_task(root, proposal, [expert], mode="native")
    receipt = v3.export_receipt(task)
    assert v3.export_task(root, proposal, [expert], mode="native") == task
    with pytest.raises(FileExistsError, match="differs"):
        v3.export_task(root, proposal, [expert], mode="legacy")
    v3.verify_export(task, receipt)
    with pytest.raises(ValueError, match="Export mode"):
        v3.export_task(tmp_path / "invalid", proposal, [], mode="silently-fallback")
    assert not (tmp_path / "invalid").exists()
