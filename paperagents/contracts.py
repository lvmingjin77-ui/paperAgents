"""JSON artifact contracts for the PaperAgents research workflow.

Validation is structural, not a scientific assessment. A source reference is not
proof that its locator exists or supports a claim; independent review must check
those facts. This module has no dependencies outside the Python standard library.
"""

from __future__ import annotations

from copy import deepcopy
import json
import math
import re
from typing import Any


REVIEW_DIMENSIONS = {
    "problem_value": "问题价值",
    "novelty": "新颖性与研究增量",
    "mechanism_soundness": "机制与逻辑合理性",
    "evidence_quality": "已有依据的可靠性",
    "experimental_discriminability": "实验判别力",
    "feasibility": "实施可行性",
}


EXPERT_REVIEW_CRITERIA = {
    "source_fidelity": "来源忠实性",
    "scientific_understanding": "科学理解",
    "reasoning_transfer": "论证与迁移",
    "capability_evidence": "能力证据",
}


def _text() -> dict:
    return {"type": "string", "minLength": 1}


def _sha256() -> dict:
    return {"type": "string", "minLength": 64, "maxLength": 64,
            "pattern": "^[a-f0-9]{64}$"}


def _array(items: dict, *, minimum: int = 0) -> dict:
    return {"type": "array", "items": items, "minItems": minimum}


def _object(properties: dict, *, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": True,
    }


def _reference() -> dict:
    return {
        "anyOf": [_text(), {"type": "object", "minProperties": 1}],
        "description": "A source locator, evidence identifier, or structured evidence record.",
    }


def _references(*, minimum: int = 0) -> dict:
    return _array(_reference(), minimum=minimum)


def _knowledge() -> dict:
    return {"type": "object", "minProperties": 1}


def _when(field: str, value: Any, then: dict) -> dict:
    return {
        "if": {"properties": {field: {"const": value}}, "required": [field]},
        "then": then,
    }


def _trace() -> dict:
    schema = _object({
        "step": {"anyOf": [_text(), {"type": "integer", "minimum": 1}]},
        "statement": _text(),
        "basis": {"enum": ["author_stated", "reconstructed", "unknown"]},
        "source_refs": _references(),
    })
    schema["allOf"] = [{
        "if": {"properties": {"basis": {"enum": ["author_stated", "reconstructed"]}},
               "required": ["basis"]},
        "then": {"properties": {"source_refs": {"minItems": 1}}},
    }]
    schema["description"] = (
        "author_stated records reasoning stated by the authors; reconstructed is an "
        "explicit system reconstruction, not an author intention; unknown permits no citation."
    )
    return schema


def _code_tool() -> dict:
    schema = _object({
        "name": _text(),
        "status": {"enum": ["documented", "wrapped", "tested", "reproduced"]},
        "verification_evidence": _references(),
    })
    schema["allOf"] = [{
        "if": {"properties": {"status": {"enum": ["tested", "reproduced"]}},
               "required": ["status"]},
        "then": {"properties": {"verification_evidence": {"minItems": 1}}},
    }]
    return schema


def _check() -> dict:
    return _object({
        "check": _text(),
        "evidence": _references(),
        "verdict": {"enum": ["pass", "fail", "unknown"]},
    })


def _review(*, proposal: bool = False) -> dict:
    properties = {"accepted": {"type": "boolean"}, "checks": _array(_check())}
    if proposal:
        properties["blocking_issues"] = _references()
    else:
        properties.update({"expert_id": _text(), "limitations": _references()})
    schema = _object(properties)
    accepted_properties = {
        "checks": {"minItems": 1, "items": {"properties": {
            "verdict": {"const": "pass"}, "evidence": {"minItems": 1},
        }}}
    }
    if proposal:
        accepted_properties["blocking_issues"] = {"maxItems": 0}
    schema["allOf"] = [_when("accepted", True, {"properties": accepted_properties})]
    return schema


def _review_dimensions() -> dict:
    dimension = _object({
        "status": {"enum": ["scored", "unknown"]},
        "score": {"type": ["integer", "null"]},
        "rationale": dict(_text(), pattern=r"\S"),
        "evidence": _references(),
    })
    dimension["allOf"] = [
        _when("status", "scored", {"properties": {
            "score": {"type": "integer", "enum": [1, 2, 3, 4, 5]},
            "evidence": {"minItems": 1},
        }}),
        _when("status", "unknown", {"properties": {"score": {"const": None}}}),
    ]
    dimensions = _object({name: deepcopy(dimension) for name in REVIEW_DIMENSIONS})
    dimensions["additionalProperties"] = False
    dimensions["description"] = (
        "Six separate ordinal judgments, each with a rationale and evidence. Unknown "
        "uses a null score and explains the missing basis. No aggregate or threshold "
        "determines acceptance; checks and blocking_issues remain independent."
    )
    return dimensions


def _score_schema(stage: str, schema: dict) -> None:
    if stage != "proposal_review":
        return
    schema["properties"].update({
        "candidate_scores": _array(_object({
            "idea_id": _text(), "candidate_hash": _sha256(),
            "dimensions": _review_dimensions(),
        }), minimum=1),
        "proposal_score": _object({
            "proposal_hash": _sha256(), "dimensions": _review_dimensions(),
        }),
    })
    schema["required"].extend(["candidate_scores", "proposal_score"])


def _novelty_search_record() -> dict:
    record = _object({
        "provider": _text(), "query": _text(), "searched_at": _text(),
        "scope": _reference(), "results_count": {"type": "integer", "minimum": 0},
        "result_refs": _references(), "limitations": _references(),
    })
    record["allOf"] = [
        _when("results_count", 0, {"properties": {"result_refs": {"maxItems": 0}}}),
        {"if": {"properties": {"results_count": {"type": "integer", "minimum": 1}}},
         "then": {"anyOf": [
             {"properties": {"result_refs": {"minItems": 1}}},
             {"properties": {"limitations": {"minItems": 1}}},
         ]}},
    ]
    record["description"] = (
        "Record an actual query, its scope, time and returned count. Positive counts "
        "need result references or an explicit retrieval limitation. A zero result is "
        "not proof of universal novelty. The schema cannot establish that a search occurred."
    )
    return record


def _decision_schema(stage: str, schema: dict) -> None:
    if stage == "synthesis":
        schema["properties"]["candidate_ref"] = _object({
            "idea_id": _text(), "candidate_hash": _sha256(),
        })
        proposal_core = _object({
            "mechanism": _text(), "assumptions": _references(), "falsification": _reference(),
        })
        schema["allOf"].append(_when("decision", "ready", {
            "required": ["candidate_ref"], "properties": {"proposal": proposal_core},
        }))
    elif stage == "novelty":
        item = schema["properties"]["reviews"]["items"]
        item["allOf"] = [_when("status", "distinct", {"properties": {
            "search_log": _array(_novelty_search_record(), minimum=1),
        }})]
    elif stage in {"expert_review", "proposal_review"}:
        criteria = REVIEW_DIMENSIONS if stage == "proposal_review" else EXPERT_REVIEW_CRITERIA
        check = schema["properties"]["checks"]["items"]
        check["properties"]["criterion"] = {"enum": list(criteria)}
        check["required"].append("criterion")
        required_coverage = {
            "minItems": len(criteria), "maxItems": len(criteria),
            "allOf": [{"contains": {"properties": {"criterion": {"const": criterion}},
                                    "required": ["criterion"]}} for criterion in criteria],
        }
        schema["allOf"].append(_when("accepted", True, {"properties": {"checks": required_coverage}}))


def _discussion_schema(stage: str, schema: dict) -> None:
    """Discussion loop: numbered objections, explicit next action, reviewed non-selection."""
    if stage == "selection":
        schema["properties"]["core_paper_ids"].update(minItems=1, maxItems=5)
    elif stage == "challenge":
        item = schema["properties"]["reviews"]["items"]
        item["properties"].update({"candidate_hash": _sha256(), "objections": _array(_objection())})
        item["required"].extend(["candidate_hash", "objections"])
        schema["properties"]["issue_responses"] = _array(_object({"issue_id": _text(), "response": _text()}))
        schema["required"].append("issue_responses")
    elif stage == "reading":
        trace = schema["properties"]["idea_trace"]["items"]
        trace["properties"]["trace_id"] = _text()
        trace["required"].append("trace_id")
        schema["properties"]["card"] = _paper_card()
        schema["required"].append("card")
    elif stage == "domain":
        knowledge = schema["properties"]["knowledge"]
        knowledge["properties"]["landscape"] = _landscape()
        knowledge["required"].append("landscape")
    elif stage == "synthesis":
        schema["properties"]["next_action"] = {
            "enum": ["proceed", "revise_candidates", "gather_materials", "stop"],
            "description": "proceed only with ready; revise_candidates sends the debate back to the "
                           "authors; gather_materials opens bounded evidence collection; stop waits for the operator.",
        }
        schema["required"].append("next_action")
        schema["properties"]["secondary_ref"] = {
            "anyOf": [{"type": "null"}, _object({"idea_id": _text(), "candidate_hash": _sha256()})],
            "description": "Optional: one further active candidate with a different mechanism, run against "
                           "the same baseline and evaluator as program_2. It must meet the same admission "
                           "conditions as the selected candidate.",
        }
        schema["allOf"].append(_when("decision", "ready", {"properties": {"next_action": {"const": "proceed"}}}))
        schema["allOf"].append({"if": {"properties": {"decision": {"enum": ["needs_evidence", "no_viable_idea"]}},
                                       "required": ["decision"]},
                                "then": {"properties": {"next_action": {"not": {"const": "proceed"}}}}})
    elif stage == "proposal_review":
        schema["properties"]["decision_assessment"] = _object({
            "synthesis_decision": {"enum": ["ready", "needs_evidence", "no_viable_idea"]},
            "agree": {"type": "boolean"}, "reason": _text(),
        })
        schema["required"].append("decision_assessment")
        schema["properties"]["experiment_requirements"] = _array(_object({
            "requirement_id": _text(), "kind": {"enum": ["effect", "validity_gate"]},
            "question": _text(), "decision_rule": _text(), "on_fail": _text()}))
        schema["required"].append("experiment_requirements")
        if "candidate_scores" in schema["properties"]:
            schema["properties"]["candidate_scores"]["minItems"] = 0  # every candidate may have been withdrawn


def _paper_card() -> dict:
    """ORKG-style research contribution: problem, method and results with their conditions."""
    result = _object({"benchmark": _text(), "metric": _text(), "value": _text(), "condition": _text()})
    card = _object({
        "problem": _text(),
        "contributions": _array(_object({
            "method": _text(), "mechanism": _text(), "assumptions": _array(_text()),
            "results": _array(result),
        }), minimum=1),
        "relations": _array(_object({
            "paper_id": _text(),
            "relation": {"enum": ["extends", "contrasts", "uses", "compares_against", "other"]},
            "note": _text(),
        })),
    })
    card["description"] = ("Structured contribution of this paper. Names are free text; the coordinator merges "
                           "equal names case-insensitively into the domain graph. Results keep their conditions.")
    return card


def _landscape() -> dict:
    """The domain expert's structured view; every paper_id must resolve to a read corpus paper."""
    ids = lambda minimum=0: _array(_text(), minimum=minimum)  # noqa: E731
    gap = _object({"gap_id": _text(), "problem": _text(), "condition": _text(),
                   "status": {"enum": ["untested", "failed", "inconclusive"]},
                   "evidence_paper_ids": ids(), "note": _text()})
    gap["allOf"] = [{"if": {"properties": {"status": {"enum": ["failed", "inconclusive"]}}},
                     "then": {"properties": {"evidence_paper_ids": {"minItems": 1}}}}]
    question = _object({"question": _text(), "paper_ids": ids(), "known": _text(), "unknowns": ids(),
                        "observations": ids(), "corpus_gaps": ids()})
    question["description"] = ("One research question from the brief: existing methods and evidence, what is still "
                               "unknown, observations that would tell competing explanations apart, and missing sources. "
                               "It need not contain a gap or an answer.")
    return _object({
        "questions": _array(question, minimum=1),
        "set_aside": _array(_object({"paper_id": _text(), "reason": _text()})),
        "evolution_chains": _array(_object({"chain_id": _text(), "paper_ids": ids(2), "steps": ids(1)})),
        "contested": _array(_object({"claim": _text(), "supporting": ids(1), "opposing": ids(1), "note": _text()})),
        "gaps": _array(gap),
        "protocols": _array(_object({"protocol": _text(), "used_by": ids(1), "blind_spot": _text()})),
    })


def _temporary_expert() -> dict:
    schema = _object({
        "expert_id": _text(),
        "specialty": _text(),
        "reason": _text(),
        "source_paper_ids": _array(_text()),
        "material_gaps": _references(),
    }, required=["expert_id", "specialty", "reason", "source_paper_ids"])
    schema["allOf"] = [_when("source_paper_ids", [], {
        "required": ["material_gaps"],
        "properties": {"material_gaps": {"minItems": 1}},
    })]
    return schema


def _proposal() -> dict:
    return _object({
        "title": _text(),
        "problem": _text(),
        "hypothesis": _text(),
        "implementation_plan": _array(_text(), minimum=1),
        "evaluation": _knowledge(),
        "source_refs": _references(minimum=1),
    })


def _candidate() -> dict:
    return _object({
        "idea_id": _text(), "title": _text(),
        "kind": {"enum": ["mechanism", "diagnostic", "baseline"],
                 "description": "mechanism: a new or transferred intervention; diagnostic: locates a bottleneck "
                                "or tests a competing explanation; baseline: a configured existing method."},
        "problem": _text(), "hypothesis": _text(), "mechanism": _text(),
        "assumptions": _references(), "nearest_work": _references(),
        "falsification": _reference(), "experiment_plan": _reference(),
        "source_refs": _references(minimum=1),
    })


def _objection() -> dict:
    schema = _object({
        "objection_id": _text(), "claim": _text(), "objection": _text(),
        "evidence": _references(), "blocking": {"type": "boolean"},
        "resolution_test": _text(),
    })
    schema["description"] = (
        "One numbered objection against one candidate version. objection_id must be unique "
        "across the run. resolution_test states what evidence, revision or experiment would "
        "resolve it. blocking=true means the candidate must not be admitted while it stays open."
    )
    return schema


def _make_schemas() -> dict[str, dict]:
    entry = _object({
        "paper_id": _text(), "title": _text(), "venue_id": _text(),
        "year": {"type": "integer", "minimum": 1},
        "pub_date": {"anyOf": [{"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"}, {"type": "null"}],
                     "description": "Date of the collected version, not of another version."},
        "source_url": _text(), "full_text_path": {"type": ["string", "null"]},
        "relevance": {"enum": ["core", "transferable"]}, "background": {"type": "boolean"},
        "reason": _text(),
    })
    entry["properties"].update(doi=_text(), arxiv_id=_text(), same_as=_array(_text()),
                               related_to=_array(_text()), read={"type": "boolean"})
    entry["description"] = ("Screening record only; reading happens in per-paper tasks. Optional: doi, arxiv_id "
                            "with version, same_as / related_to as paper_id lists, read=true with a reason for a "
                            "background paper that must still be read.")
    corpus = _object({
        "papers": _array(entry),
        "coverage": _object({"status": {"enum": ["complete", "partial", "insufficient"]}}),
        "search_log": _references(),
        "missing_sources": _references(),
    })
    corpus["allOf"] = [{"if": {"properties": {"coverage": {"properties": {"status": {"const": "complete"}}}}},
                        "then": {"properties": {"papers": {"minItems": 1}, "search_log": {"minItems": 1},
                                                "missing_sources": {"maxItems": 0}}}}]
    paper = _object({
        "expert_id": _text(), "paper_id": _text(), "knowledge": _knowledge(),
        "idea_trace": _array(_trace(), minimum=1), "code_tools": _array(_code_tool()),
        "limitations": _references(),
    })
    paper["properties"]["source_paths"] = _array(_text())
    paper["allOf"] = [
        _when("code_tools", [], {"properties": {"limitations": {"minItems": 1}}}),
        {
            "if": {"properties": {"code_tools": {"contains": {
                "properties": {"status": {"enum": ["wrapped", "tested", "reproduced"]}},
                "required": ["status"],
            }}}, "required": ["code_tools"]},
            "then": {"required": ["source_paths"],
                     "properties": {"source_paths": {"minItems": 1}}},
        },
    ]
    selection = _object({
        "core_paper_ids": {"type": "array", "items": _text(), "minItems": 3,
                           "maxItems": 3, "uniqueItems": True},
        "selection_reasons": _knowledge(),
        "temporary_experts": _array(_temporary_expert()),
        "coverage": _array(_object({"question": _text(), "route": _text(),
                                    "expert_ids": _array(_text(), minimum=1)}), minimum=1),
        # Teams compared and not chosen: the record of the comparison, not a semantic gate.
        "team_alternatives": _array(_object({"core_paper_ids": _array(_text(), minimum=1),
                                             "temporary_expert_ids": _array(_text()), "covers": _text(),
                                             "misses": _text(), "reason": _text()}), minimum=1),
    })
    hypothesis = _object({"expert_id": _text(), "candidates": _array(_candidate())})
    reading = _object({
        "paper_id": _text(), "idea_trace": _array(_trace()),
        "coverage": _object({"status": {"enum": ["complete", "partial", "insufficient"]},
                             "unread": _references()}),
        "limitations": _references(),
    })
    reading["allOf"] = [{
        "if": {"properties": {"coverage": {"properties": {"status": {"const": "complete"}},
                                           "required": ["status"]}}, "required": ["coverage"]},
        "then": {"properties": {"idea_trace": {"minItems": 1},
                                "coverage": {"properties": {"unread": {"maxItems": 0}}}}},
    }]
    response = _object({
        "objection_id": _text(),
        "action": {"enum": ["rebut", "revise", "withdraw", "experiment", "accept_limitation"]},
        "argument": _text(), "evidence": _references(),
        "revised_idea_id": {"anyOf": [_text(), {"type": "null"}]},
    })
    response["allOf"] = [_when("action", "revise", {"properties": {"revised_idea_id": _text()}})]
    revised = _candidate()
    revised["properties"].update({"parent_ids": _array(_text(), minimum=1), "change_summary": _text()})
    revised["required"].extend(["parent_ids", "change_summary"])
    rebuttal = _object({
        "expert_id": _text(), "responses": _array(response),
        "revised_candidates": _array(revised), "withdrawn_idea_ids": _array(_text()),
    })
    rebuttal["description"] = (
        "The author's own answer to each assigned objection. A revision that changes the "
        "scientific core is a new candidate with parent_ids; it is challenged again. A merge "
        "may name another expert's candidate as a parent but must include one of the author's own."
    )
    recheck = _object({
        "expert_id": _text(),
        "verdicts": _array(_object({
            "objection_id": _text(), "status": {"enum": ["resolved", "unresolved", "experiment"]},
            "reason": _text(), "evidence": _references(),
        })),
        "new_reviews": _array(_object({
            "idea_id": _text(), "candidate_hash": _sha256(), "objections": _array(_objection()),
        })),
    })
    recheck["description"] = (
        "The original challenger judges only its own objections against the author's actual "
        "response; experiment means the disagreement becomes a discriminating experiment. "
        "new_reviews challenge candidates created in this round."
    )
    synthesis = _object({
        "decision": {"enum": ["ready", "needs_evidence", "no_viable_idea"]},
        "selected_idea_id": {"anyOf": [_text(), {"type": "null"}]},
        "proposal": {"type": "object"},
        "alternatives": _references(), "unresolved_questions": _references(),
    })
    synthesis["allOf"] = [_when("decision", "ready", {"properties": {
        "selected_idea_id": _text(), "proposal": _proposal(),
        "unresolved_questions": {"not": {"contains": {
            "type": "object", "properties": {"blocking": {"const": True}},
            "required": ["blocking"],
        }}},
    }})]
    return {
        "scope": _object({
            "direction": _text(),
            "venues": _array(_object({"venue_id": _text(), "note": _text()}), minimum=1),
            "queries": _array(_text(), minimum=1),
            "inclusion_criteria": _array(_text(), minimum=1),
        }),
        "corpus": corpus,
        "domain": _object({
            "expert_id": {"const": "domain"}, "knowledge": _knowledge(),
            "source_paper_ids": _array(_text(), minimum=1), "limitations": _references(),
        }),
        "selection": selection,
        "paper": paper,
        "consultant": _object({
            "expert_id": _text(), "specialty": _text(), "knowledge": _knowledge(),
            "source_refs": _references(), "limitations": _references(),
        }),
        "expert_review": _review(),
        "hypothesis": hypothesis,
        "challenge": _object({
            "expert_id": _text(), "reviews": _array(_object({
                "idea_id": _text(), "claims": _references(), "required_evidence": _references(),
            })),
        }),
        "novelty": _object({"reviews": _array(_object({
            "idea_id": _text(), "status": {"enum": ["distinct", "overlap", "uncertain"]},
            "nearest_work": _references(), "search_log": _references(), "reason": _text(),
        }))}),
        "synthesis": synthesis,
        "proposal_review": _review(proposal=True),
        "evidence": _object({
            "issue_id": _text(),
            "affected_idea_ids": _array(_text(), minimum=1),
            "outcome": {"enum": ["resolved", "premise_fails", "needs_experiment", "needs_human", "unresolved"]},
            "changes": _array({"enum": ["assumption", "mechanism", "data", "statistical_guarantee"]}),
            "finding": _text(),
            "evidence": _references(minimum=1),
            "limitations": _references(),
            "next_step": _text(),
        }),
        "reading": reading,
        "triage": _object({"reviews": _array(_object({
            "idea_id": _text(), "candidate_hash": _sha256(),
            "overlap_risk": {"enum": ["low", "medium", "high", "unknown"]},
            "near_matches": _references(), "search_log": _references(), "note": _text(),
        })),
            "groups": _array(_object({
                "group_id": _text(), "relation": {"enum": ["duplicate", "partial", "shared"]},
                "idea_ids": _array(_text(), minimum=2), "representative": _text(), "reason": _text(),
            })),
        }),
        "agenda": _object({
            "issues": _array(_object({
                "issue_id": _text(),
                "kind": {"enum": ["mechanism_conflict", "merge_opportunity", "value_question",
                                  "evidence_gap", "shared_prerequisite", "feasibility", "other"]},
                "idea_ids": _array(_text(), minimum=1), "question": _text(),
                "assigned_expert_ids": _array(_text(), minimum=1),
            })),
            "notes": _references(),
        }),
        "rebuttal": rebuttal,
        "merge": deepcopy(rebuttal),  # authors answer triage duplicate notices with the rebuttal contract
        "recheck": recheck,
    }


_SCHEMAS = _make_schemas()
STAGES = tuple(_SCHEMAS)


def _ids(*, minimum: int = 0) -> dict:
    return dict(_array(_text(), minimum=minimum), uniqueItems=True)


def _anchor_ref() -> dict:
    return _object({"source_id": _text(), "anchor_id": _text()})


def _analysis_item() -> dict:
    schema = _object({
        "status": {"enum": ["analyzed", "not_applicable", "unknown"]},
        "summary": _text(), "source_refs": _array(_anchor_ref()), "reason": _text(),
    }, required=["status", "summary", "source_refs"])
    schema["allOf"] = [
        _when("status", "analyzed", {"properties": {"source_refs": {"minItems": 1}}}),
        _when("status", "not_applicable", {"required": ["reason"]}),
        _when("status", "unknown", {"required": ["reason"]}),
    ]
    return schema


def _paper_understanding() -> dict:
    source = _object({
        "source_id": _text(),
        "kind": {"enum": ["full_text", "supplement", "code", "data", "other"]},
        "version": _text(), "status": {"enum": ["read", "partial", "unavailable"]},
        "required": {"type": "boolean"},
        "path": {"type": ["string", "null"]},
        "sha256": {"type": ["string", "null"]},
    })
    source["allOf"] = [
        {"if": {"properties": {"status": {"enum": ["read", "partial"]}}},
         "then": {"properties": {"path": _text(), "sha256": {
             "type": "string", "pattern": "^[a-fA-F0-9]{64}$"}}}},
        _when("status", "unavailable", {"properties": {
            "path": {"const": None}, "sha256": {"const": None}}}),
    ]
    coverage = _object({
        "status": {"enum": ["complete", "partial", "insufficient"]},
        "read_anchor_ids": _ids(), "unread_anchor_ids": _ids(),
    })
    coverage["allOf"] = [_when("status", "complete", {"properties": {
        "read_anchor_ids": {"minItems": 1}, "unread_anchor_ids": {"maxItems": 0}}})]
    schema = _object({
        "paper_type": _text(), "sources": _array(source, minimum=1), "coverage": coverage,
        "navigation": _array(_object({
            "anchor_id": _text(), "source_id": _text(),
            "kind": {"enum": ["section", "equation", "figure", "table", "appendix", "other"]},
            "locator": _text(), "summary": _text(),
        }), minimum=1),
        "analysis": _object({name: _analysis_item() for name in (
            "problem", "method", "formalism", "figures_tables", "evidence", "assumptions", "limitations")}),
        "limitations": _array(_text()),
    })
    schema["description"] = (
        "IDs must be unique. Read/unread anchor IDs must partition navigation. Every reference "
        "must resolve to its source and a read anchor. Complete requires a read full_text and "
        "all required sources read; it describes declared coverage, not scientific correctness. "
        "Actual paths, hashes, locators and reading claims require separate verification."
    )
    return schema


def _reasoning_pattern(*, domain: bool) -> dict:
    refs = (_object({"paper_id": _text(), "locator": _text()}) if domain else _anchor_ref())
    schema = _object({
        "pattern_id": _text(), "name": _text(), "problem_type": _text(),
        "reasoning_move": _text(), "preconditions": _array(_text(), minimum=1),
        "failure_modes": _array(_text(), minimum=1),
        "source_refs": _array(refs, minimum=1),
        "trace_refs": _array(_object({"paper_id": _text(), "trace_id": _text()}),
                             minimum=0 if domain else 1),
        "evidence_status": {"enum": ["source_supported", "source_inferred"]},
        "transfer_status": {"const": "unvalidated"}, "test_plan": _text(),
    })
    if domain:
        schema["properties"]["trace_link_limitations"] = _text()
        schema["allOf"] = [_when("trace_refs", [], {"required": ["trace_link_limitations"]})]
    schema["description"] = (
        "A source-grounded strategy, not a certified target-domain result. Domain references "
        "name source_paper_ids explicitly and require cross-artifact resolution. Paper trace "
        "references must name this paper and an existing local trace_id."
    )
    return schema


def _expert_schema(stage: str, schema: dict) -> None:
    if stage not in {"paper", "domain"}:
        return
    knowledge = _object({
        "reasoning_patterns": _array(_reasoning_pattern(domain=stage == "domain")),
        "reasoning_patterns_reason": _text(),
    }, required=["reasoning_patterns"])
    knowledge["allOf"] = [_when("reasoning_patterns", [], {
        "required": ["reasoning_patterns_reason"]})]
    if stage == "paper":
        knowledge["properties"]["paper_understanding"] = _paper_understanding()
        knowledge["required"].append("paper_understanding")
        trace = _trace()
        trace["properties"].update({
            "trace_id": _text(), "depends_on": _ids(), "source_refs": _array(_anchor_ref()),
            "reasoning_operation": _text(), "assumptions": _array(_text()),
            "alternatives": _array(_text()), "testable_implication": _text(),
        })
        trace["required"].extend(["trace_id", "depends_on", "reasoning_operation", "assumptions",
                                  "alternatives", "testable_implication"])
        trace["description"] += " Trace IDs must be unique and depends_on must form an acyclic local graph."
        schema["properties"]["idea_trace"] = _array(trace, minimum=1)
    schema["properties"]["knowledge"] = knowledge


def artifact_schema(stage: str) -> dict:
    """Return an independent JSON Schema (draft 2020-12) for a workflow stage."""
    if not isinstance(stage, str) or stage not in _SCHEMAS:
        raise ValueError(f"Unknown artifact stage: {stage!r}; expected one of {', '.join(STAGES)}")
    schema = deepcopy(_SCHEMAS[stage])
    for extend in (_expert_schema, _score_schema, _decision_schema, _discussion_schema):
        extend(stage, schema)
    schema["properties"]["notebook"] = dict(_array(_text()), description="Optional private working notes; "
                                            "returned only to you, never shown to other experts.")
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["title"] = f"PaperAgents {stage} artifact"
    return schema


def _is_type(value: Any, kind: str) -> bool:
    return {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "integer": type(value) is int,
        "boolean": type(value) is bool, "null": value is None,
    }[kind]


def _fits(value: Any, schema: dict, path: str) -> bool:
    try:
        _validate(value, schema, path)
    except ValueError:
        return False
    return True


def _equal(left: Any, right: Any) -> bool:
    # JSON true and 1 differ, unlike Python's equality relation.
    return json.dumps(left, sort_keys=True) == json.dumps(right, sort_keys=True)


def _validate(value: Any, schema: dict, path: str) -> None:
    """Validate the small JSON Schema vocabulary emitted by this module."""
    if "type" in schema:
        kinds = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, kind) for kind in kinds):
            raise ValueError(f"{path}: expected {' or '.join(kinds)}")
    if "const" in schema and not _equal(value, schema["const"]):
        raise ValueError(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and not any(_equal(value, item) for item in schema["enum"]):
        raise ValueError(f"{path}: expected one of {schema['enum']!r}")
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        raise ValueError(f"{path}: must not be empty")
    if isinstance(value, str) and "maxLength" in schema and len(value) > schema["maxLength"]:
        raise ValueError(f"{path}: permits at most {schema['maxLength']} character(s)")
    if isinstance(value, str) and "pattern" in schema and re.search(schema["pattern"], value) is None:
        raise ValueError(f"{path}: does not match the required format")
    if type(value) is int and "minimum" in schema and value < schema["minimum"]:
        raise ValueError(f"{path}: must be at least {schema['minimum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                raise ValueError(f"{path}.{key}: required field is missing")
        if len(value) < schema.get("minProperties", 0):
            raise ValueError(f"{path}: must not be an empty object")
        if schema.get("additionalProperties") is False:
            unexpected = set(value) - schema.get("properties", {}).keys()
            if unexpected:
                raise ValueError(f"{path}: unexpected fields {', '.join(sorted(unexpected))}")
        for key, child in schema.get("properties", {}).items():
            if key in value:
                _validate(value[key], child, f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValueError(f"{path}: requires at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValueError(f"{path}: permits at most {schema['maxItems']} item(s)")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True) for item in value]
            if len(set(encoded)) != len(encoded):
                raise ValueError(f"{path}: items must be unique")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(item, schema["items"], f"{path}[{index}]")
        if "contains" in schema and not any(_fits(item, schema["contains"], path) for item in value):
            raise ValueError(f"{path}: required matching item is absent")
    if "anyOf" in schema and not any(_fits(value, option, path) for option in schema["anyOf"]):
        raise ValueError(f"{path}: does not match an allowed shape")
    for child in schema.get("allOf", []):
        _validate(value, child, path)
    if "if" in schema and _fits(value, schema["if"], path):
        _validate(value, schema.get("then", {}), path)
    if "not" in schema and _fits(value, schema["not"], path):
        raise ValueError(f"{path}: contains a prohibited value or unresolved blocking issue")


def _check_json(value: Any, path: str) -> None:
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{path}: non-finite numbers are not JSON values")
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path}: object keys must be strings")
            _check_json(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _check_json(child, f"{path}[{index}]")
        return
    raise ValueError(f"{path}: {type(value).__name__} is not a JSON value")


def _unique_index(items: list[dict], field: str, path: str) -> dict[str, dict]:
    result = {}
    for item in items:
        if item[field] in result:
            raise ValueError(f"{path}: duplicate {field} {item[field]!r}")
        result[item[field]] = item
    return result


def _check_expert_links(stage: str, data: dict) -> None:
    """Resolve local IDs only; external sources and scientific claims are not checked."""
    knowledge = data["knowledge"]
    patterns = knowledge["reasoning_patterns"]
    _unique_index(patterns, "pattern_id", f"{stage}.knowledge.reasoning_patterns")
    if stage == "domain":
        known = set(data["source_paper_ids"])
        for pattern in patterns:
            for field in ("source_refs", "trace_refs"):
                for ref in pattern[field]:
                    if ref["paper_id"] not in known:
                        raise ValueError(f"domain.reasoning_patterns.{field}: unknown source paper_id")
        return

    understanding = knowledge["paper_understanding"]
    sources = _unique_index(understanding["sources"], "source_id", "paper_understanding.sources")
    anchors = _unique_index(understanding["navigation"], "anchor_id", "paper_understanding.navigation")
    coverage = understanding["coverage"]
    read = set(coverage["read_anchor_ids"])
    unread = set(coverage["unread_anchor_ids"])
    if read & unread or read | unread != set(anchors):
        raise ValueError("paper_understanding.coverage: read/unread anchors must partition navigation")
    for anchor_id, anchor in anchors.items():
        source = sources.get(anchor["source_id"])
        if source is None:
            raise ValueError("paper_understanding.navigation: unknown source_id")
        if anchor_id in read and source["status"] == "unavailable":
            raise ValueError("paper_understanding.coverage: unavailable source has a read anchor")
        if anchor_id in unread and source["status"] == "read":
            raise ValueError("paper_understanding.coverage: fully read source has an unread anchor")
    if coverage["status"] == "complete":
        if not any(source["kind"] == "full_text" and source["status"] == "read"
                   for source in sources.values()):
            raise ValueError("paper_understanding.coverage: complete requires a read full_text")
        if any(source["required"] and source["status"] != "read" for source in sources.values()):
            raise ValueError("paper_understanding.coverage: complete requires all required sources read")

    def check_refs(refs: list[dict], path: str) -> None:
        for ref in refs:
            anchor = anchors.get(ref["anchor_id"])
            if anchor is None or anchor["source_id"] != ref["source_id"]:
                raise ValueError(f"{path}: source_id/anchor_id does not resolve")
            if ref["anchor_id"] not in read:
                raise ValueError(f"{path}: reference points to an unread anchor")
            if "paper_id" in ref and ref["paper_id"] != data["paper_id"]:
                raise ValueError(f"{path}: reference names a different paper")

    for name, analysis in understanding["analysis"].items():
        if name in {"problem", "method", "formalism", "figures_tables", "evidence", "assumptions", "limitations"}:
            check_refs(analysis["source_refs"], f"paper_understanding.analysis.{name}.source_refs")
    traces = _unique_index(data["idea_trace"], "trace_id", "paper.idea_trace")
    remaining = {trace_id: set(trace["depends_on"]) for trace_id, trace in traces.items()}
    dependents = {trace_id: [] for trace_id in traces}
    for trace_id, trace in traces.items():
        check_refs(trace["source_refs"], f"paper.idea_trace.{trace_id}.source_refs")
        for dependency in trace["depends_on"]:
            if dependency not in traces:
                raise ValueError(f"paper.idea_trace.{trace_id}.depends_on: unknown trace_id")
            dependents[dependency].append(trace_id)
    ready = [trace_id for trace_id, dependencies in remaining.items() if not dependencies]
    visited = 0
    while ready:
        trace_id = ready.pop()
        visited += 1
        for child in dependents[trace_id]:
            remaining[child].remove(trace_id)
            if not remaining[child]:
                ready.append(child)
    if visited != len(traces):
        raise ValueError("paper.idea_trace.depends_on: cycle detected")
    for pattern in patterns:
        check_refs(pattern["source_refs"], "paper.reasoning_patterns.source_refs")
        for ref in pattern["trace_refs"]:
            if ref["paper_id"] != data["paper_id"] or ref["trace_id"] not in traces:
                raise ValueError("paper.reasoning_patterns.trace_refs: unknown local paper/trace reference")


def validate_artifact(stage: str, data: dict) -> None:
    """Raise ``ValueError`` for invalid structure; otherwise return ``None``.

    This intentionally does not inspect files, resolve cross-artifact IDs, verify
    citations, infer novelty, or judge scientific truth. Those are separate gates.
    """
    schema = artifact_schema(stage)
    _check_json(data, stage)
    _validate(data, schema, stage)
    if stage in {"paper", "domain"}:
        _check_expert_links(stage, data)
    if stage == "proposal_review":
        _unique_index(data["candidate_scores"], "idea_id", "proposal_review.candidate_scores")
    if stage in {"expert_review", "proposal_review"}:
        _unique_index(data["checks"], "criterion", f"{stage}.checks")
    _check_local_ids(stage, data)


def _check_local_ids(stage: str, data: dict) -> None:
    """Local uniqueness only; cross-artifact links are resolved by the coordinator."""
    if stage == "challenge":
        _unique_index(data["reviews"], "idea_id", "challenge.reviews")
        _unique_index([item for review in data["reviews"] for item in review["objections"]],
                      "objection_id", "challenge.objections")
    elif stage == "recheck":
        _unique_index(data["verdicts"], "objection_id", "recheck.verdicts")
        _unique_index(data["new_reviews"], "idea_id", "recheck.new_reviews")
        _unique_index([item for review in data["new_reviews"] for item in review["objections"]],
                      "objection_id", "recheck.objections")
    elif stage in {"rebuttal", "merge"}:
        _unique_index(data["responses"], "objection_id", "rebuttal.responses")
        _unique_index(data["revised_candidates"], "idea_id", "rebuttal.revised_candidates")
        if len(set(data["withdrawn_idea_ids"])) != len(data["withdrawn_idea_ids"]):
            raise ValueError("rebuttal.withdrawn_idea_ids: duplicate idea id")
    elif stage == "agenda":
        _unique_index(data["issues"], "issue_id", "agenda.issues")
    elif stage == "reading":
        _unique_index(data["idea_trace"], "trace_id", "reading.idea_trace")
    elif stage == "domain" and isinstance(data.get("knowledge", {}).get("landscape"), dict):
        landscape = data["knowledge"]["landscape"]
        _unique_index(landscape["evolution_chains"], "chain_id", "domain.landscape.evolution_chains")
        _unique_index(landscape["gaps"], "gap_id", "domain.landscape.gaps")
    elif stage == "triage":
        _unique_index(data["reviews"], "idea_id", "triage.reviews")
        _unique_index(data["groups"], "group_id", "triage.groups")
