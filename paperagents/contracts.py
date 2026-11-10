"""Worker boundary contracts; scientific judgments are made by independent reviewers."""

from jsonschema import Draft202012Validator

TEXT = {"type": "string", "minLength": 1}
TEXTS = {"type": "array", "items": TEXT}
NUMBER = {"type": "number"}
BOOL = {"type": "boolean"}
REVIEW_DIMENSIONS = {
    "problem_value": "问题价值",
    "novelty": "新颖性",
    "mechanism_soundness": "机制合理性",
    "evidence_quality": "证据质量",
    "experimental_discriminability": "实验判别力",
    "feasibility": "实施可行性",
}


def obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


def array(items, minimum=0):
    return {"type": "array", "items": items, "minItems": minimum}


def enum(*values):
    return {"enum": list(values)}


def validate(data, schema):
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: str(e.path))
    if errors:
        raise ValueError("; ".join(f"{'.'.join(map(str, e.path)) or '$'}: {e.message}" for e in errors[:20]))


CLAIM = obj(
    {
        "claim_id": TEXT,
        "kind": enum("enhancement", "mechanism", "reformulation", "analysis", "baseline"),
        "text": TEXT,
        "mechanism": TEXT,
        "prediction": TEXT,
        "falsification": TEXT,
        "parents": TEXTS,
        "exploratory": BOOL,
        "sources": TEXTS,
    }
)
PROPOSALS = obj({"claims": array(CLAIM), "reason": TEXT})
REVIEW = obj({"accepted": BOOL, "reason": TEXT, "issues": TEXTS})
SCORES = obj(
    {
        key: obj(
            {
                "score": {"type": ["integer", "null"], "minimum": 1, "maximum": 5},
                "reason": TEXT,
                "evidence_ids": TEXTS,
            }
        )
        for key in REVIEW_DIMENSIONS
    }
)
ASSESSMENT = obj(
    {
        "decision": enum("admit", "revise", "resources"),
        "reason": TEXT,
        "dimensions": SCORES,
        "required_tests": TEXTS,
    }
)
EXCHANGE = obj(
    {
        "comments": array(
            obj(
                {
                    "claim_ref": TEXT,
                    "kind": enum("extend", "combine", "alternative", "objection"),
                    "reason": TEXT,
                    "prediction": TEXT,
                }
            )
        )
    }
)
TRIAGE = obj(
    {"groups": array(obj({"representative": TEXT, "members": TEXTS, "reason": TEXT})), "overlap_notes": TEXTS}
)
MERGE = obj({"withdraw": TEXTS, "claims": array(CLAIM), "reason": TEXT})
SELECTION = obj({"claim_refs": TEXTS, "reason": TEXT})
VERDICT_UPDATE = {
    "verdict": enum("supported", "refuted", "inconclusive", "unchanged"),
    "prediction_tested": TEXT,
    "reason": TEXT,
    "evidence_ids": TEXTS,
}
# Eligibility (gate) and the scientific verdict on the claim's prediction are separate answers.
JUDGMENT = obj({"gate": enum("advance", "stop", "engineer"), **VERDICT_UPDATE})
REASSESSMENT = obj(VERDICT_UPDATE)
METHOD_SPEC = obj(
    {
        "inputs": TEXT,
        "outputs": TEXT,
        "components": TEXTS,
        "procedure": TEXT,
        "parameters": TEXTS,
        "difference_from_baselines": TEXT,
    }
)
EXPLANATION = obj(
    {
        "findings": TEXTS,
        "competing_explanations": TEXTS,
        "next_tests": TEXTS,
        "reframe": BOOL,
        "literature_gaps": TEXTS,
        "claim_refs": TEXTS,
    }
)
NOVELTY = obj({"decision": enum("distinct", "revise", "withdraw"), "reason": TEXT, "references": TEXTS})

SECTION = obj({"name": TEXT, "claim_refs": TEXTS, "tex": TEXT})
SECTION_DRAFT = obj({"sections": array(SECTION), "references": array({"type": "object"})})
FIGURE = obj({"path": TEXT, "claim_refs": TEXTS, "caption": TEXT, "run_ids": TEXTS})
MANUSCRIPT = obj(
    {
        "title": TEXT,
        "sections": array(SECTION, 1),
        "references": array({"type": "object"}),
        "figures": array(FIGURE),
    },
    required=["title", "sections", "references"],
)

TESTBED_PLAN = obj(
    {"design": TEXT, "baselines": TEXTS, "validity_checks": TEXTS, "diagnostics": TEXTS, "unresolved": TEXTS}
)
METRIC = obj({"direction": enum("min", "max"), "description": TEXT})
BASELINE = obj({"name": TEXT, "source": TEXT, "version": TEXT, "supervision": TEXT, "compute": TEXT})
PROTOCOL = obj(
    {
        "evaluator": TEXT,
        "programs": {
            "type": "object",
            "properties": {"baseline": TEXT},
            "required": ["baseline"],
            "additionalProperties": TEXT,
            "propertyNames": {"pattern": "^[A-Za-z0-9_-]+$"},
        },
        "baselines": array(BASELINE, 1),
        "splits": obj({"screen": TEXT, "confirm": TEXT, "test": TEXT}),
        "statistical_unit": TEXT,
        "split_manifest": TEXT,
        "audit_sample": TEXT,
        "metrics": {"type": "object", "minProperties": 1, "additionalProperties": METRIC},
        "comparison_rules": TEXTS,
        "scope": TEXT,
        "data_provenance": TEXTS,
        "validity_rules": TEXTS,
        "diagnostic_observations": TEXTS,
        "unknowns": TEXTS,
        "assets": TEXTS,
    }
)
TESTBED = obj(
    {
        "status": enum("ready", "needs_materials"),
        "reason": TEXT,
        "protocol": {"anyOf": [PROTOCOL, {"type": "null"}]},
    }
)
TESTBED["allOf"] = [{"if": {"properties": {"status": {"const": "ready"}}}, "then": {"properties": {"protocol": PROTOCOL}}}]
BUILD = obj({"program": TEXT, "changes": TEXT, "protocol_changes": BOOL, "reason": TEXT})
ABLATION_PLAN = obj(
    {"variants": array(obj({"id": TEXT, "change": TEXT, "rules_out": TEXT, "prediction": TEXT}), 1)}
)
DECISION = enum("accept", "revise", "experiments", "reframe")
PEER_REVIEW = obj(
    {"decision": DECISION, "reason": TEXT, "dimensions": SCORES, "required_experiments": TEXTS, "claim_refs": TEXTS}
)
META_REVIEW = obj({"decision": DECISION, "reason": TEXT, "claim_refs": TEXTS, "required_experiments": TEXTS})
REBUTTAL = obj({"response": TEXT, "evidence_ids": TEXTS, "required_experiments": TEXTS})
FINAL_JUDGMENT = obj(
    {
        "verdicts": array(
            obj({"claim_ref": TEXT, "verdict": enum("supported", "refuted", "inconclusive"), "reason": TEXT})
        )
    }
)

