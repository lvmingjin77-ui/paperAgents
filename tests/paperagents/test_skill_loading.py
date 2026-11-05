"""Only relevant capabilities enter each worker; all registered skills remain usable."""

from pathlib import Path

import pytest

from paperagents.skills import resolve_skills


CORE_PAPER = ["build-paper-expert", "understand-paper", "trace-paper-ideas",
              "distill-reasoning-patterns", "map-paper-code"]


def names(stage, context=None):
    return [item["id"] for item in resolve_skills(stage, context=context)]


def test_paper_core_keeps_reading_reasoning_transfer_and_code_mapping():
    assert names("paper") == CORE_PAPER
    assert names("paper", {"paper_capabilities": []}) == CORE_PAPER


@pytest.mark.parametrize("capabilities,extra", [
    (["communication"], ["analyze-paper-communication"]),
    (["method_tools"], ["build-method-tools", "verify-method-tools"]),
    (["method_tools", "communication"],
     ["analyze-paper-communication", "build-method-tools", "verify-method-tools"]),
    (["communication", "communication"], ["analyze-paper-communication"]),
])
def test_requested_paper_capabilities_load_without_duplicates(capabilities, extra):
    skills = resolve_skills("paper", context={"paper_capabilities": capabilities})
    assert [item["id"] for item in skills] == CORE_PAPER + extra
    for skill in skills:
        assert Path(skill["path"]).is_file()
        assert skill["instructions"]


@pytest.mark.parametrize("capabilities", [None, "communication", {"communication": True},
                                          ["unknown"], ["method_tool"], [True], [None]])
def test_invalid_paper_capabilities_are_not_silently_ignored(capabilities):
    with pytest.raises(ValueError, match="paper_capabilities"):
        resolve_skills("paper", context={"paper_capabilities": capabilities})


def test_reuse_and_revision_still_require_actual_context():
    assert "reuse-and-update-expert" not in names("domain")
    assert names("domain", {"reuse_candidates": ["existing.json"]})[0] == "reuse-and-update-expert"
    paper = names("paper", {"reuse_candidates": ["existing.json"], "paper_capabilities": ["method_tools"]})
    assert paper == ["reuse-and-update-expert", *CORE_PAPER, "build-method-tools", "verify-method-tools"]
    assert names("hypothesis") == ["generate-hypotheses"]
    assert names("hypothesis", {"revision_context": {"previous_iteration": 1}}) == [
        "generate-hypotheses", "revise-hypotheses"]


def test_native_experiment_stages_reuse_existing_operational_skills():
    assert names("experiment_build") == ["design-discriminating-experiments", "build-method-tools"]
    assert names("experiment_review") == ["verify-method-tools", "review-research"]
