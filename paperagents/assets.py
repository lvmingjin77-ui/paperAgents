"""Versioned library records: reading cards and expert knowledge reused across runs."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shutil

from .storage import digest, write_json


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _name(asset_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", asset_id)[:50] + "-" + digest(asset_id)[:8]


def find_expert_assets(project: Path, expert_id: str) -> list[str]:
    """Earlier versions of an expert; candidates for reuse, not approval."""
    return [str(p) for p in sorted((project / "library" / "experts" / _name(expert_id)).glob("*/asset.json"))]


def save_asset(project: Path, kind: str, record: dict, asset_id: str, sources=()) -> dict:
    """Store a record with copies of its local source files under a content-derived version."""
    sources = [Path(s) if Path(s).is_absolute() else project / s for s in sources]
    version = digest({"record": record, "sources": [str(s) for s in sources]})[:24]
    folder = project / "library" / kind / _name(asset_id) / version
    copies = []
    for number, source in enumerate(sources):
        target = folder / "sources" / f"{number:03d}-{source.name}"
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True)
        else:
            shutil.copy2(source, target)
        copies.append(str(target))
    output = dict(record, _asset={"path": str(folder), "version": version})
    if copies:
        output["source_paths"] = copies
    write_json(folder / "asset.json", output)
    return output
