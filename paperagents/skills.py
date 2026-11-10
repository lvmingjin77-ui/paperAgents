"""Task-scoped research capabilities; expert knowledge lives in reusable assets."""

from __future__ import annotations

from pathlib import Path

from .config import ROOT
from .storage import read_json


STAGE_SKILLS = {
    "final_judgment": ["review-paper"],
    "scope": ["build-literature-corpus"],
    "corpus": ["build-literature-corpus"],
    "reading": ["read-paper-card"],
    "domain": ["build-domain-expert"],
    "selection": ["select-paper-team"],
    "paper": [
        "build-paper-expert",
        "understand-paper",
        "trace-paper-ideas",
        "distill-reasoning-patterns",
        "map-paper-code",
        "analyze-paper-communication",
    ],
    "consultant": ["build-domain-expert", "trace-paper-ideas", "distill-reasoning-patterns"],
    "expert_review": ["verify-expert"],
    "propose": ["generate-hypotheses"],
    "exchange": ["exchange-ideas"],
    "revise": ["exchange-ideas", "explain-and-evolve"],
    "triage": ["exchange-ideas", "audit-novelty"],
    "merge": ["exchange-ideas"],
    "assess": ["challenge-claims"],
    "select": ["challenge-claims"],
    "build_testbed": ["build-testbed", "build-method-tools"],
    "protocol_review": ["build-testbed", "verify-method-tools"],
    "build": ["build-method-tools"],
    "implementation_review": ["verify-method-tools"],
    "judge": ["screen-and-diagnose"],
    "reassess": ["screen-and-diagnose"],
    "method_spec": ["build-method-tools"],
    "faithfulness": ["review-paper"],
    "explain": ["screen-and-diagnose", "explain-and-evolve"],
    "evolve": ["explain-and-evolve", "generate-hypotheses"],
    "novelty": ["audit-novelty"],
    "ablation_plan": ["plan-ablation"],
    "ablation_review": ["plan-ablation", "screen-and-diagnose"],
    "freeze": ["screen-and-diagnose", "verify-method-tools"],
    "argument": ["write-section"],
    "write_section": ["write-section"],
    "rebuttal": ["review-paper", "write-section"],
    "testbed_plan": ["build-testbed"],
    "write": ["write-section"],
    "peer_review": ["review-paper"],
    "meta_review": ["review-paper"],
    "finalize": ["write-section", "review-paper"],
}


def resolve_skills(stage: str, root: Path | None = None, *, context: dict | None = None) -> list[dict]:
    root = (root or ROOT / "skills").resolve()
    registry = read_json(root / "registry.json")["skills"]
    names = list(STAGE_SKILLS[stage])
    if (context or {}).get("reuse_candidates"):
        names.insert(0, "reuse-and-update-expert")
    result = []
    for name in dict.fromkeys(names):
        path = (root / registry[name]["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Invalid skill path for {name}")
        result.append({"id": name, "path": str(path), "instructions": path.read_text(encoding="utf-8")})
    return result


def resolve_expert_profile(role: str, root: Path | None = None) -> dict | None:
    root = (root or ROOT / "skills").resolve()
    profiles = read_json(root / "registry.json")["expert_profiles"]
    if role not in profiles:
        return None
    path = (root / profiles[role]["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Invalid expert profile for {role}")
    return {"id": role, "path": str(path), "instructions": path.read_text(encoding="utf-8")}
