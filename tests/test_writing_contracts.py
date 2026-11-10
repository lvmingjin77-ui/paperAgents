"""Writing provenance checks on synthetic records and files; no workers or experiments."""

from pathlib import Path

import pytest

from paperagents import contracts as C
from paperagents.workflow import Workflow


@pytest.fixture
def workflow(tmp_path):
    w = Workflow.__new__(Workflow)
    w.run_dir = tmp_path / "run"
    w.run_dir.mkdir()
    w.state = {
        "claims": {
            "idea@1": {"ref": "idea@1", "active": False, "verdict": "supported"},
            "idea@2": {"ref": "idea@2", "active": True, "verdict": "refuted"},
            "analysis@1": {"ref": "analysis@1", "active": True, "verdict": "inconclusive"},
        },
        "evidence": {
            "old": {"claim_ref": "idea@1"},
            "current": {"claim_ref": "idea@2"},
            "analysis": {"claim_ref": "analysis@1"},
            "baseline": {"claim_ref": None},
        },
        "draft": {},
    }
    w.config = {"loops": {"reviewers": 1}}
    w.context = lambda: {}
    w.transition = lambda phase: None
    return w


def argument(refs, evidence):
    return {
        "question": "What did the fixture establish?",
        "answer": "The proposed effect did not hold.",
        "contributions": [{"statement": "A negative finding", "claim_refs": refs, "evidence_ids": evidence}],
        "analyses": [],
        "negative_results": ["The proposed effect did not hold."],
        "limits": [],
    }


@pytest.mark.parametrize("refs,evidence", [
    ([], ["baseline"]),
    (["missing@1"], ["baseline"]),
    (["idea@2"], ["baseline"]),
    (["idea@2", "analysis@1"], ["current"]),
    (["idea@2"], ["old"]),
    (["idea@2"], ["missing"]),
])
def test_argument_rejects_unknown_or_unbound_claims(workflow, refs, evidence):
    with pytest.raises(ValueError):
        workflow._check_argument(argument(refs, evidence))


def test_argument_schema_requires_claim_versions():
    with pytest.raises(ValueError):
        C.validate(argument([], ["baseline"]), C.ARGUMENT)


def test_argument_keeps_negative_and_analysis_results_with_baseline_context(workflow):
    data = argument(["idea@2", "analysis@1"], ["current", "analysis", "baseline"])
    data["analyses"] = [{"question": "What changed?", "finding": "The old result did not transfer.",
                         "claim_refs": ["idea@1", "idea@2"], "evidence_ids": ["old", "current"]}]
    C.validate(data, C.ARGUMENT)
    workflow._check_argument(data)


def review(workflow, path, ref="idea@2"):
    data = dict(
        decision="accept", reason="Synthetic inspection",
        dimensions={k: dict(score=3, reason="Synthetic", evidence_ids=[]) for k in C.REVIEW_DIMENSIONS},
        inspected=[dict(path=str(path), claim_ref=ref, finding="Checked the fixture")],
        required_experiments=[], claim_refs=[ref],
    )

    def tasks(specs):
        C.validate(data, specs[0][4])
        specs[0][-1](data)
        return [data]

    workflow.tasks = tasks
    workflow._peer_review()


@pytest.mark.parametrize("absolute", [False, True])
def test_inspection_accepts_shared_run_file_for_active_claim(workflow, absolute):
    path = workflow.run_dir / "evaluator.py"
    path.write_text("# synthetic shared evaluator\n")
    review(workflow, path if absolute else path.name)
    assert workflow.state["reviews"][0]["inspected"][0]["claim_ref"] == "idea@2"


@pytest.mark.parametrize("case", ["directory", "missing", "absolute_outside", "relative_outside", "file_link", "dir_link"])
def test_inspection_rejects_nonfiles_and_paths_outside_run(workflow, case):
    outside = workflow.run_dir.parent / "outside.py"
    outside.write_text("# outside this run\n")
    if case == "directory":
        path = workflow.run_dir / "workspace"
        path.mkdir()
    elif case == "missing":
        path = Path("missing.py")
    elif case == "absolute_outside":
        path = outside
    elif case == "relative_outside":
        path = Path("../outside.py")
    elif case == "file_link":
        path = workflow.run_dir / "linked.py"
        path.symlink_to(outside)
    else:
        link = workflow.run_dir / "linked-directory"
        link.symlink_to(workflow.run_dir.parent, target_is_directory=True)
        path = link / "outside.py"
    with pytest.raises(ValueError):
        review(workflow, path)


def test_inspection_rejects_unknown_claim(workflow):
    path = workflow.run_dir / "evaluator.py"
    path.write_text("# synthetic shared evaluator\n")
    with pytest.raises(ValueError):
        review(workflow, path, "missing@1")


def test_inspection_accepts_internal_symlink_and_historical_claim(workflow):
    target = workflow.run_dir / "old-program.py"
    target.write_text("# historical implementation\n")
    path = workflow.run_dir / "linked.py"
    path.symlink_to(target)
    review(workflow, path, "idea@1")
