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
