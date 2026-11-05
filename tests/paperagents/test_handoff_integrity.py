"""Reviewed snapshots stay bound to trusted receipts; no real experiments run."""

from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from paperagents.assets import freeze_asset, verify_asset
from paperagents import v3


@pytest.fixture
def frozen(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    source = project / "notes.md"
    source.write_text("SYNTHETIC_TEST_FIXTURE; no scientific result.\n")
    expert = freeze_asset(project, "experts", {
        "expert_id": "domain", "knowledge": {"reasoning_patterns": []},
        "source_paths": [str(source)], "limitations": ["Synthetic fixture"],
    }, "domain", [str(source)], structured=True)
    return project, expert


def export_frozen(project, expert):
    proposal = {"title": "Synthetic proposal", "problem": "Fixture problem",
                "hypothesis": "Fixture hypothesis", "implementation_plan": ["Fixture implementation"],
                "evaluation": {"controls": "Fixture controls"}}
    # The controller exports the whole frozen expert, including its generated views.
    return v3.export_task(project / "export", proposal,
                          [dict(expert, source_paths=[expert["_asset"]["path"]])])


def test_frozen_views_are_preserved_and_benchmark_additions_remain_allowed(frozen):
    project, expert = frozen
    verify_asset(expert)
    task = export_frozen(project, expert)
    receipt = v3.export_receipt(task)
    assert v3.EXPORT_MANIFEST in receipt["files"]
    for name in ("asset.json", "SKILL.md", "knowledge/index.md", "knowledge/reasoning-patterns.json"):
        assert any(path.endswith("/" + name) for path in receipt["files"])
    (task / "program_0").mkdir()
    (task / "program_0" / "candidate.py").write_text("# legitimate later benchmark code\n")
    (task / "task_contract.json").write_text('{"synthetic": true}\n')
    v3.verify_export(task, receipt)


@pytest.mark.parametrize("name", ["unreviewed.py", "knowledge/extra.json", "sources/extra.txt"])
def test_unregistered_frozen_files_cannot_be_verified_reused_or_exported(frozen, name):
    project, expert = frozen
    root = Path(expert["_asset"]["path"])
    extra = root / name
    extra.parent.mkdir(parents=True, exist_ok=True)
    extra.write_text("Unreviewed content")
    with pytest.raises(ValueError, match="file set changed"):
        verify_asset(expert)
    with pytest.raises(ValueError, match="file set changed"):
        export_frozen(project, expert)
    assert not (project / "export" / "task").exists()
    source = project / "notes.md"
    with pytest.raises(ValueError, match="file set changed"):
        freeze_asset(project, "experts", {
            "expert_id": "domain", "knowledge": {"reasoning_patterns": []},
            "source_paths": [str(source)], "limitations": ["Synthetic fixture"],
        }, "domain", [str(source)], structured=True)


@pytest.mark.parametrize("kind", ["file", "directory", "metadata"])
def test_frozen_symlinks_are_rejected_even_if_contents_match(frozen, kind):
    project, expert = frozen
    root = Path(expert["_asset"]["path"])
    if kind == "directory":
        source = root / "knowledge"
        target = project / "moved-knowledge"
    elif kind == "metadata":
        source, target = root / "asset.json", project / "metadata.json"
    else:
        source, target = root / "SKILL.md", project / "skill.md"
    source.rename(target)
    source.symlink_to(target, target_is_directory=kind == "directory")
    with pytest.raises(ValueError, match="symlink"):
        verify_asset(expert)


@pytest.mark.parametrize("target", ["task", "context", "prompt", "expert", "source"])
def test_reviewed_export_tampering_is_rejected_even_with_rewritten_local_manifest(frozen, target, monkeypatch):
    project, expert = frozen
    task = export_frozen(project, expert)
    receipt = v3.export_receipt(task)
    names = {"task": "task.md", "context": v3.CONTEXT_FILE, "prompt": v3.IDEA_PROMPT,
             "expert": next(name for name in receipt["files"] if name.endswith("/expert.json")),
             "source": next(name for name in receipt["files"] if name.endswith("/000-notes.md"))}
    changed = names[target]
    (task / changed).write_text("Unreviewed replacement")
    manifest_path = task / v3.EXPORT_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest[changed] = v3._hash(task / changed)
    manifest_path.write_text(json.dumps(manifest))

    def forbidden(*args, **kwargs):
        raise AssertionError("Damaged export must not launch a subprocess")

    monkeypatch.setattr(v3.subprocess, "run", forbidden)
    with pytest.raises(ValueError, match="changed"):
        v3.run_v3(task, dry_run=False, expected_receipt=receipt)


@pytest.mark.parametrize("kind", ["missing", "file_link", "directory_link", "extra"])
def test_export_missing_symlink_and_extra_expert_files_are_rejected(frozen, kind):
    project, expert = frozen
    task = export_frozen(project, expert)
    receipt = v3.export_receipt(task)
    prompt = task / v3.IDEA_PROMPT
    if kind == "missing":
        prompt.unlink()
    elif kind == "file_link":
        target = project / "prompt-copy.md"
        prompt.rename(target)
        prompt.symlink_to(target)
    elif kind == "directory_link":
        source = task / v3.ASSETS_DIR / "experts"
        target = project / "expert-copy"
        source.rename(target)
        source.symlink_to(target, target_is_directory=True)
    else:
        (task / v3.ASSETS_DIR / "unreviewed.py").write_text("# unreviewed\n")
    with pytest.raises(ValueError):
        v3.verify_export(task, receipt)


@pytest.mark.parametrize("path", ["../escape", "/absolute", "paperagents_assets/../task.md", "./task.md"])
def test_export_receipt_paths_cannot_escape_or_alias(frozen, path):
    project, expert = frozen
    task = export_frozen(project, expert)
    receipt = v3.export_receipt(task)
    receipt["files"][path] = "0" * 64
    with pytest.raises(ValueError, match="unsafe path"):
        v3.verify_export(task, receipt)


def test_execution_requires_trusted_receipt_and_does_not_forward_it_to_subprocess(frozen, monkeypatch):
    project, expert = frozen
    task = export_frozen(project, expert)
    receipt = v3.export_receipt(task)
    original = deepcopy(receipt)
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(v3.subprocess, "run", fake_run)
    with pytest.raises(ValueError, match="trusted export receipt"):
        v3.run_v3(task, dry_run=False)
    assert not calls
    assert v3.run_v3(task, dry_run=False, expected_receipt=receipt).returncode == 0
    assert "--dry-run" not in calls[-1][0]
    assert "expected_receipt" not in calls[-1][1]
    assert receipt == original
    assert v3.run_v3(task).returncode == 0
    assert calls[-1][0][-1] == "--dry-run"
    # Receipts describe portable bytes, not the original machine's path.
    copied = project / "portable-task"
    shutil.copytree(task, copied)
    v3.verify_export(copied, receipt)
