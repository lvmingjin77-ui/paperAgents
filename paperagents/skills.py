"""Resolve only the skills relevant to each worker assignment."""

from __future__ import annotations

from pathlib import Path

from .config import ROOT
from .storage import read_json

STAGE_SKILLS = {
    "scope": ["build-literature-corpus"],
    "corpus": ["build-literature-corpus", "understand-paper", "trace-paper-ideas"],
    "domain": ["build-domain-expert", "distill-reasoning-patterns"],
    "selection": ["select-paper-team"],
    "paper": ["build-paper-expert", "understand-paper", "trace-paper-ideas",
              "distill-reasoning-patterns", "map-paper-code"],
    "consultant": ["build-domain-expert"],
    "expert_review": ["verify-expert"],
    "hypothesis": ["generate-hypotheses"],
    "challenge": ["challenge-claims"],
    "novelty": ["audit-novelty"],
    "synthesis": ["design-discriminating-experiments", "synthesize-proposal"],
    "proposal_review": ["review-research"],
    "evidence": ["review-research"],
    "reading": ["understand-paper", "trace-paper-ideas"],
    "triage": ["audit-novelty"],
    "agenda": ["moderate-discussion"],
    "merge": ["revise-hypotheses"],
    "rebuttal": ["revise-hypotheses", "design-discriminating-experiments"],
    "recheck": ["challenge-claims"],
    "experiment_build": ["design-discriminating-experiments", "build-method-tools"],
    "experiment_review": ["verify-method-tools", "review-research"],
}

PAPER_CAPABILITY_SKILLS = {
    "communication": ["analyze-paper-communication"],
    "method_tools": ["build-method-tools", "verify-method-tools"],
}


def resolve_skills(stage: str, root: Path | None = None, *, context: dict | None = None) -> list[dict]:
    root = (root or ROOT / "skills").resolve()
    registry = read_json(root / "registry.json")["skills"]
    names = list(STAGE_SKILLS[stage])
    context = context or {}
    if stage == "corpus" and context.get("per_paper_reading"):
        # v3 assigns reading to separate per-paper tasks.
        names = ["build-literature-corpus"]
    if stage == "paper":
        capabilities = context.get("paper_capabilities", [])
        if not isinstance(capabilities, list) or any(
                not isinstance(item, str) or item not in PAPER_CAPABILITY_SKILLS
                for item in capabilities):
            raise ValueError("paper_capabilities must be a list containing only communication or method_tools")
        for capability, skill_ids in PAPER_CAPABILITY_SKILLS.items():
            if capability in capabilities:
                names.extend(skill_ids)
    if stage in {"domain", "paper"} and context.get("reuse_candidates"):
        names.insert(0, "reuse-and-update-expert")
    if stage == "hypothesis" and context.get("revision_context"):
        names.append("revise-hypotheses")
    result = []
    for name in names:
        path = (root / registry[name]["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"Invalid skill path for {name}")
        result.append({"id": name, "path": str(path), "instructions": path.read_text(encoding="utf-8")})
    return result


def resolve_expert_profile(role: str, root: Path | None = None) -> dict | None:
    """Profiles define how an expert uses skills; they are not additional skills."""
    root = (root or ROOT / "skills").resolve()
    profiles = read_json(root / "registry.json").get("expert_profiles", {})
    if role not in profiles:
        return None
    path = (root / profiles[role]["path"]).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Invalid expert profile path for {role}")
    return {"id": role, "path": str(path), "instructions": path.read_text(encoding="utf-8")}
