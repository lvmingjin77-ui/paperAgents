"""Synthetic counterexamples for explicit, versioned scientific admission gates."""

from copy import deepcopy

import pytest

from paperagents.contracts import (
    EXPERT_REVIEW_CRITERIA,
    REVIEW_DIMENSIONS,
    artifact_schema,
    validate_artifact,
)
from tests.paperagents.test_contracts import artifacts
from tests.paperagents.test_review_score_contracts import review_v2


def strict_validate(stage, data):
    validate_artifact(stage, data)


def ready_synthesis():
    data = artifacts()["synthesis"]
    candidate = artifacts()["hypothesis"]["candidates"][0]
    data["candidate_ref"] = {"idea_id": candidate["idea_id"], "candidate_hash": "a" * 64}
    data["proposal"].update({key: deepcopy(candidate[key])
                             for key in ("mechanism", "assumptions", "falsification")})
    return data


def searched_novelty(*, count=1):
    data = artifacts()["novelty"]
    item = data["reviews"][0]
    item["status"] = "distinct"
    item["search_log"] = [{
        "provider": "SYNTHETIC_TEST_FIXTURE", "query": "fixture mechanism",
        "searched_at": "2026-11-04T00:00:00Z",
        "scope": {"years": [2024, 2026], "venue": "FixtureConf"},
        "results_count": count,
        "result_refs": ["SYNTHETIC_TEST_FIXTURE#result-1"] if count else [],
        "limitations": [],
    }]
    return data


def criterion_checks(stage):
    criteria = REVIEW_DIMENSIONS if stage == "proposal_review" else EXPERT_REVIEW_CRITERIA
    return [{"criterion": criterion, "check": "SYNTHETIC_TEST_FIXTURE: criterion review",
             "verdict": "pass", "evidence": ["SYNTHETIC_TEST_FIXTURE#evidence"]}
            for criterion in criteria]


@pytest.mark.parametrize("field", ["candidate_ref", "mechanism", "assumptions", "falsification"])
def test_ready_synthesis_requires_version_identity_and_scientific_core(field):
    data = ready_synthesis()
    strict_validate("synthesis", data)
    del (data if field == "candidate_ref" else data["proposal"])[field]
    with pytest.raises(ValueError, match=field):
        strict_validate("synthesis", data)


@pytest.mark.parametrize("fingerprint", ["a" * 63, "A" * 64, "a" * 64 + "\n", None])
def test_candidate_reference_requires_exact_hash(fingerprint):
    data = ready_synthesis()
    data["candidate_ref"]["candidate_hash"] = fingerprint
    with pytest.raises(ValueError, match="candidate_hash"):
        strict_validate("synthesis", data)


@pytest.mark.parametrize("decision", ["needs_evidence", "no_viable_idea"])
def test_nonready_synthesis_need_not_invent_a_candidate_or_mechanism(decision):
    data = {"decision": decision, "selected_idea_id": None, "proposal": {}, "next_action": "stop",
            "alternatives": [], "unresolved_questions": ["Fixture evidence gap"]}
    strict_validate("synthesis", data)


@pytest.mark.parametrize("search_log", [[], ["No matching paper found"]])
def test_distinct_requires_structured_search_receipts(search_log):
    data = searched_novelty()
    data["reviews"][0]["search_log"] = search_log
    with pytest.raises(ValueError, match="search_log"):
        strict_validate("novelty", data)


@pytest.mark.parametrize("field", ["provider", "query", "searched_at", "scope", "results_count",
                                   "result_refs", "limitations"])
def test_search_receipt_must_expose_query_scope_results_and_gaps(field):
    data = searched_novelty()
    del data["reviews"][0]["search_log"][0][field]
    with pytest.raises(ValueError, match=field):
        strict_validate("novelty", data)


@pytest.mark.parametrize("count", [-1, True, 1.5, None])
def test_result_count_is_a_nonnegative_integer(count):
    data = searched_novelty()
    data["reviews"][0]["search_log"][0]["results_count"] = count
    with pytest.raises(ValueError, match="results_count"):
        strict_validate("novelty", data)


def test_honest_zero_result_search_does_not_require_an_invented_nearest_paper():
    data = searched_novelty(count=0)
    data["reviews"][0]["nearest_work"] = []
    strict_validate("novelty", data)
    data["reviews"][0]["search_log"][0]["result_refs"] = ["Conflicting result count"]
    with pytest.raises(ValueError, match="result_refs"):
        strict_validate("novelty", data)


def test_returned_results_need_locators_or_a_disclosed_retrieval_limit():
    data = searched_novelty()
    record = data["reviews"][0]["search_log"][0]
    record["result_refs"] = []
    with pytest.raises(ValueError, match="search_log"):
        strict_validate("novelty", data)
    record["limitations"] = ["Fixture service reported a count without retrievable identifiers."]
    strict_validate("novelty", data)


def test_irrelevant_returned_results_do_not_require_fabricated_nearest_work():
    data = searched_novelty()
    data["reviews"][0].update(nearest_work=[], reason="Fixture results address a different problem.")
    strict_validate("novelty", data)


@pytest.mark.parametrize("status", ["overlap", "uncertain"])
def test_non_distinct_status_can_disclose_partial_or_missing_search(status):
    data = searched_novelty()
    data["reviews"][0].update(status=status, search_log=["Fixture missing retrieval access"])
    strict_validate("novelty", data)


@pytest.mark.parametrize("stage", ["expert_review", "proposal_review"])
def test_accepted_review_must_cover_every_named_criterion_once(stage):
    data = artifacts()[stage]
    data["checks"] = criterion_checks(stage)
    strict_validate(stage, data)
    data["checks"].pop()
    with pytest.raises(ValueError, match="checks"):
        strict_validate(stage, data)
    data["checks"].append(deepcopy(data["checks"][0]))
    with pytest.raises(ValueError, match="checks"):
        strict_validate(stage, data)


@pytest.mark.parametrize("stage", ["expert_review", "proposal_review"])
def test_rejected_review_can_be_partial_but_cannot_repeat_a_criterion(stage):
    data = artifacts()[stage]
    data.update(accepted=False, checks=criterion_checks(stage)[:1])
    data["checks"][0]["verdict"] = "unknown"
    strict_validate(stage, data)
    data["checks"].append(deepcopy(data["checks"][0]))
    with pytest.raises(ValueError, match="duplicate criterion"):
        strict_validate(stage, data)


@pytest.mark.parametrize("stage", ["expert_review", "proposal_review"])
def test_format_only_check_cannot_replace_scientific_criteria(stage):
    data = artifacts()[stage]
    del data["checks"][0]["criterion"]
    with pytest.raises(ValueError, match="criterion"):
        strict_validate(stage, data)
    data["checks"] = criterion_checks(stage)
    data["checks"][0]["criterion"] = "title_exists"
    with pytest.raises(ValueError, match="criterion"):
        strict_validate(stage, data)


def test_capability_review_can_accept_evidenced_knowledge_only_scope():
    data = artifacts()["expert_review"]
    data["checks"] = criterion_checks("expert_review")
    data["checks"][-1].update(
        check="Fixture paper supplies theory only; accepted capability is source-grounded explanation.",
        evidence=["SYNTHETIC_TEST_FIXTURE#declared-scope-and-limitations"],
    )
    data["limitations"] = ["No runnable method or claimed reproduction."]
    strict_validate("expert_review", data)


def test_unknown_experimental_effect_is_not_itself_a_failed_admission_condition():
    data = review_v2()
    data["checks"] = criterion_checks("proposal_review")
    data["checks"][2]["check"] = "Fixture effect is unknown; mechanism is coherent and falsifiable."
    strict_validate("proposal_review", data)
    data["checks"].pop()
    with pytest.raises(ValueError, match="checks"):
        strict_validate("proposal_review", data)

