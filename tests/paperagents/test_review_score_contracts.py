"""Synthetic scorecards exercise structure, never scientific scoring quality."""

from copy import deepcopy
import json

import pytest

from paperagents.contracts import REVIEW_DIMENSIONS, artifact_schema, validate_artifact


def review_v2():
    dimensions = {
        name: {"status": "scored", "score": 5,
               "rationale": "SYNTHETIC_TEST_FIXTURE: rubric justification",
               "evidence": ["SYNTHETIC_TEST_FIXTURE#source"]}
        for name in REVIEW_DIMENSIONS
    }
    return {
        "accepted": True,
        "decision_assessment": {"synthesis_decision": "ready", "agree": True, "reason": "SYNTHETIC_TEST_FIXTURE"},
        "checks": [{"criterion": name, "check": "Fixture admission condition", "verdict": "pass",
                    "evidence": ["SYNTHETIC_TEST_FIXTURE#condition"]} for name in REVIEW_DIMENSIONS],
        "blocking_issues": [],
        "experiment_requirements": [],
        "candidate_scores": [{"idea_id": "fixture-idea", "candidate_hash": "a" * 64,
                              "dimensions": deepcopy(dimensions)}],
        "proposal_score": {"proposal_hash": "b" * 64, "dimensions": dimensions},
    }


def validate(data):
    validate_artifact("proposal_review", data)


@pytest.mark.parametrize("target", ["candidate", "proposal"])
def test_requires_all_and_only_the_six_dimensions(target):
    data = review_v2()
    dimensions = (data["candidate_scores"][0] if target == "candidate"
                  else data["proposal_score"])["dimensions"]
    del dimensions["evidence_quality"]
    with pytest.raises(ValueError, match="evidence_quality"):
        validate(data)
    dimensions["evidence_quality"] = deepcopy(dimensions["problem_value"])
    dimensions["weighted_total"] = 5
    with pytest.raises(ValueError, match="weighted_total"):
        validate(data)


@pytest.mark.parametrize("score", [0, 6, -1, True, False, 3.0, "3", None])
def test_scored_dimension_requires_integer_one_to_five(score):
    data = review_v2()
    data["candidate_scores"][0]["dimensions"]["problem_value"]["score"] = score
    with pytest.raises(ValueError, match="score"):
        validate(data)


@pytest.mark.parametrize("score", [1, 2, 3, 4, 5])
def test_score_magnitude_is_not_an_admission_threshold(score):
    data = review_v2()
    for record in [*data["candidate_scores"], data["proposal_score"]]:
        for dimension in record["dimensions"].values():
            dimension["score"] = score
    validate(data)


@pytest.mark.parametrize("field", ["status", "score", "rationale", "evidence"])
def test_every_dimension_has_an_explicit_basis(field):
    data = review_v2()
    del data["proposal_score"]["dimensions"]["novelty"][field]
    with pytest.raises(ValueError, match=field):
        validate(data)


@pytest.mark.parametrize("change", [{"rationale": ""}, {"rationale": " \n "},
                                    {"evidence": []}, {"evidence": [""]}])
def test_numeric_rating_requires_actual_rationale_and_evidence_fields(change):
    data = review_v2()
    data["proposal_score"]["dimensions"]["novelty"].update(change)
    with pytest.raises(ValueError):
        validate(data)


def test_unknown_is_explicit_and_not_a_fabricated_numeric_rating():
    data = review_v2()
    dimension = data["proposal_score"]["dimensions"]["evidence_quality"]
    dimension.update(status="unknown", score=None, evidence=[],
                     rationale="Required source has not been retrieved in this fixture.")
    validate(data)
    dimension["score"] = 1
    with pytest.raises(ValueError, match="score"):
        validate(data)


@pytest.mark.parametrize("change", ["blocking_issue", "failed_check", "unknown_check"])
def test_perfect_scores_cannot_bypass_admission_conditions(change):
    data = review_v2()
    if change == "blocking_issue":
        data["blocking_issues"] = ["Fixture required dataset is unavailable."]
    else:
        data["checks"][0]["verdict"] = "fail" if change == "failed_check" else "unknown"
    with pytest.raises(ValueError):
        validate(data)
    data["accepted"] = False
    data.setdefault("decision_assessment", {})["agree"] = False
    validate(data)


@pytest.mark.parametrize("fingerprint", ["a" * 63, "a" * 65, "A" * 64,
                                         "g" * 64, "a" * 64 + "\n", None])
def test_scorecards_require_exact_lowercase_sha256_identity(fingerprint):
    for target, field in (("candidate_scores", "candidate_hash"),
                          ("proposal_score", "proposal_hash")):
        data = review_v2()
        record = data[target][0] if target == "candidate_scores" else data[target]
        record[field] = fingerprint
        with pytest.raises(ValueError, match=field):
            validate(data)


def test_duplicate_or_absent_candidate_scorecards_are_invalid():
    data = review_v2()
    data["candidate_scores"].append(deepcopy(data["candidate_scores"][0]))
    with pytest.raises(ValueError, match="duplicate idea_id"):
        validate(data)  # coverage of exactly the reviewed candidates is checked against review_targets


def test_score_schema_is_serializable_and_independently_mutable():
    schema = artifact_schema("proposal_review")
    assert json.loads(json.dumps(schema)) == schema
    candidate_dimensions = schema["properties"]["candidate_scores"]["items"]["properties"]["dimensions"]
    candidate_dimensions["properties"]["problem_value"]["properties"].clear()
    assert candidate_dimensions["properties"]["novelty"]["properties"]
    assert schema["properties"]["proposal_score"]["properties"]["dimensions"]["properties"]["problem_value"]["properties"]
    validate(review_v2())
