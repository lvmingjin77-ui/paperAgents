"""Content-addressed source and expert snapshots; no overwrite of prior versions."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
import re
import shutil
from pathlib import Path

from .storage import digest, read_json, write_json


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _asset_name(asset_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", asset_id)[:50] + "-" + digest(asset_id)[:8]


def find_expert_assets(project: Path, expert_id: str) -> list[str]:
    """Discover local versions by identity only; this is not a reuse approval."""
    root = project / "library" / "experts" / _asset_name(expert_id)
    return [
        str(path)
        for path in sorted(root.glob("*/asset.json"))
        if path.is_file()
        and not path.is_symlink()
        and not any(parent.is_symlink() for parent in path.parents)
    ]


def _write_immutable_text(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content:
        raise ValueError("Immutable asset derived contents changed")
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def _knowledge_views(folder: Path, record: dict) -> list[dict]:
    """Render navigable views of submitted evidence; do not invent paper content."""
    knowledge = record.get("knowledge", {})
    views = {}
    if "paper_understanding" in knowledge:
        views["paper-understanding.json"] = knowledge["paper_understanding"]
    if "idea_trace" in record:
        views["idea-trace.json"] = record["idea_trace"]
    if "reasoning_patterns" in knowledge:
        views["reasoning-patterns.json"] = knowledge["reasoning_patterns"]
    for field, filename in (
        ("communication_analysis", "communication-analysis.json"),
        ("reuse_assessment", "reuse-assessment.json"),
    ):
        if field in knowledge:
            views[filename] = knowledge[field]
    if not views:
        return []
    directory = folder / "knowledge"
    directory.mkdir(exist_ok=True)
    for name, data in views.items():
        path = directory / name
        if path.exists() and json.loads(path.read_text(encoding="utf-8")) != data:
            raise ValueError("Immutable asset derived contents changed")
        if not path.exists():
            write_json(path, data)
    lines = [
        f"# {record['expert_id']} knowledge index",
        "",
        "Generated from the submitted asset. Reading coverage, understanding and actual tool "
        "execution are separate claims; consult the independent review for acceptance.",
        "",
        "## Views",
        "",
    ]
    lines.extend(f"- [{name}]({name})" for name in views)
    understanding = knowledge.get("paper_understanding", {})
    if understanding:
        lines.extend(["", "## Sources", ""])
        for source in understanding.get("sources", []):
            path = Path(source["path"]) if source.get("path") else None
            target = (
                ("../" + path.relative_to(folder).as_posix())
                if path and path.is_relative_to(folder)
                else None
            )
            location = f"[frozen source]({target})" if target else "unavailable"
            lines.append(f"- {source['source_id']}: {source['kind']}, {source['status']}; {location}")
        lines.extend(["", "## Reading anchors", ""])
        for anchor in understanding.get("navigation", []):
            lines.append(
                f"- {anchor['anchor_id']} | {anchor['source_id']} | {anchor['kind']} | "
                f"{anchor['locator']} | {anchor['summary']}"
            )
    patterns = knowledge.get("reasoning_patterns", [])
    if patterns:
        lines.extend(["", "## Reasoning patterns", ""])
        for pattern in patterns:
            lines.append(f"- {pattern['pattern_id']}: {pattern.get('name', pattern.get('label', ''))}")
    _write_immutable_text(directory / "index.md", "\n".join(lines) + "\n")
    return [
        {"path": path.relative_to(folder).as_posix(), "sha256": file_hash(path)}
        for path in sorted(directory / name for name in [*views, "index.md"])
    ]


def freeze_asset(
    project: Path, kind: str, record: dict, asset_id: str, sources: list[str], *, structured: bool = False
) -> dict:
    if "_asset" in record:
        raise ValueError("_asset is coordinator-owned; workers provide original source_paths instead")
    source_files = []
    roots = []
    origin_map = {}
    for number, supplied in enumerate(sources):
        source = Path(supplied)
        source = source if source.is_absolute() else project / source
        if source.is_symlink() or not source.exists():
            raise ValueError(f"Asset source is missing or a symlink: {source}")
        source = source.resolve()
        if (project / "library").resolve().is_relative_to(source):
            raise ValueError("Asset source cannot contain the destination library")
        target = Path("sources") / f"{number:03d}-{source.name}"
        roots.append(target.as_posix())
        origin_map[str(source)] = target.as_posix()
        entries = sorted(source.rglob("*")) if source.is_dir() else [source]
        for entry in entries:
            if entry.is_symlink():
                raise ValueError(f"Asset source contains a symlink: {entry}")
            relative = target / entry.relative_to(source) if source.is_dir() else target
            origin_map[str(entry)] = relative.as_posix()
            if entry.is_dir():
                continue
            if not entry.is_file():
                raise ValueError(f"Unsupported asset entry: {entry}")
            source_files.append((entry, relative, file_hash(entry)))
    manifest = [{"path": relative.as_posix(), "sha256": hash_} for _, relative, hash_ in source_files]
    version_input = {
        "record": record,
        "sources": manifest,
        "origin_map": origin_map,
        "asset_format": 3,
        "structured": structured,
    }
    version = digest(version_input)[:24]
    name = _asset_name(asset_id)
    folder = project / "library" / kind / name / version
    if folder.is_symlink():
        raise ValueError("Immutable asset directory is a symlink")
    if (folder / "asset.json").exists() or (folder / "asset.json").is_symlink():
        if (folder / "asset.json").is_symlink():
            raise ValueError("Immutable asset metadata is a symlink")
        verify_asset(read_json(folder / "asset.json"))
    folder.mkdir(parents=True, exist_ok=True)
    for source, relative, hash_ in source_files:
        destination = folder / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if file_hash(destination) != hash_:
                raise ValueError("Immutable asset contents changed")
        else:
            shutil.copy2(source, destination)
            if file_hash(destination) != hash_:
                raise ValueError("Source changed while snapshotting")
    output = deepcopy(record)
    output["_asset"] = {
        "path": str(folder.resolve()),
        "version": version,
        "files": manifest,
        "origin_map": origin_map,
    }
    if kind == "papers" and roots:
        output["full_text_path"] = str((folder / roots[0]).resolve())
    elif roots:
        output["source_paths"] = [str((folder / root).resolve()) for root in roots]
    if kind == "experts":
        understanding = output.get("knowledge", {}).get("paper_understanding", {}) if structured else {}
        for source in understanding.get("sources", []):
            if source.get("path"):
                original = Path(source["path"])
                original = original if original.is_absolute() else project / original
                relative = origin_map.get(str(original.resolve()))
                if relative is None:
                    raise ValueError("Paper understanding source was not included in the frozen asset")
                source["path"] = str((folder / relative).resolve())
                if file_hash(Path(source["path"])) != source["sha256"].lower():
                    raise ValueError("Paper understanding source changed while snapshotting")
        output["_asset"]["derived_files"] = _knowledge_views(folder, output) if structured else []
    if kind == "experts":
        skill_name = "expert-" + re.sub(r"[^a-z0-9-]", "-", asset_id.lower())[:40] + "-" + version[:8]
        _write_immutable_text(
            folder / "SKILL.md",
            f"---\nname: {skill_name}\ndescription: Consult this versioned expert knowledge asset.\n---\n\n"
            + (
                "Start with [the knowledge index](knowledge/index.md); use it to select the relevant "
                "understanding, idea-trace or reasoning-pattern view and frozen source. Read the full "
                "relevant source passage and its figure/table context before answering. The views are "
                "derived from asset.json, which holds the full record.\n\n"
                if output["_asset"]["derived_files"]
                else "Read asset.json and the relevant source references. "
            )
            + "Distinguish author-stated reasoning, "
            "reconstruction and unknown history. Tool use requires the recorded verification state. "
            "Load the current work skill separately. Independent expert_review is required; storage "
            "does not certify expertise or scientific correctness.\n",
        )
        output["_asset"]["derived_files"].append(
            {"path": "SKILL.md", "sha256": file_hash(folder / "SKILL.md")}
        )
    asset_file = folder / "asset.json"
    if asset_file.exists() and read_json(asset_file) != output:
        raise ValueError("Immutable asset metadata changed")
    write_json(asset_file, output)
    verify_asset(output)
    return output


def verify_asset(record: dict) -> None:
    asset = record.get("_asset")
    if not asset:
        return
    supplied_root = Path(asset["path"])
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise ValueError("Immutable asset directory is missing or a symlink")
    root = supplied_root.resolve()
    expected = {"asset.json": None}
    for item in asset["files"] + asset.get("derived_files", []):
        name = item["path"]
        relative = Path(name)
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() != name
            or name in expected
            or name in {"", "."}
        ):
            raise ValueError("Immutable asset manifest contains an invalid or duplicate path")
        expected[name] = item["sha256"]
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError("Immutable asset contains a symlink or unsupported entry")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    if actual != set(expected):
        raise ValueError("Immutable asset file set changed (missing or unregistered files)")
    if read_json(root / "asset.json") != record:
        raise ValueError("Immutable asset metadata changed")
    for name, expected_hash in expected.items():
        if expected_hash is not None and file_hash(root / name) != expected_hash:
            raise ValueError("Immutable asset source changed")
