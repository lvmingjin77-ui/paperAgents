"""Breadth reading, method-team selection and reusable, independently reviewed experts.

The coordinator stores actual worker outputs. It never invents literature or
requires exhaustive reading before a paper can be selected for deeper study.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from .assets import file_hash, find_expert_assets, freeze_asset, verify_asset
from .landscape import compile_graph, write_views
from .storage import digest, read_json, write_json


def obj(**properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def arr(item, minimum=0):
    return {"type": "array", "items": item, "minItems": minimum}


TEXT = {"type": "string"}
TEXTS = arr(TEXT)
SOURCE = obj(
    source=TEXT,
    locator=TEXT,
    observation=TEXT,
    basis={"enum": ["author_stated", "observed", "reconstructed", "unknown"]},
)
SOURCES = arr(SOURCE)
STATUS = {"enum": ["ready", "needs_materials"]}
SCOPE = obj(
    questions=TEXTS,
    window=TEXT,
    venues=TEXTS,
    inclusion=TEXTS,
    exclusions=TEXTS,
    search_plan=TEXTS,
    stop_conditions=TEXTS,
)
PAPER = obj(
    paper_id=TEXT,
    title=TEXT,
    year={"type": "integer"},
    venue=TEXT,
    doi=TEXT,
    arxiv_id=TEXT,
    url=TEXT,
    full_text_path=TEXT,
    code_url=TEXT,
    relevance={"enum": ["core", "transferable", "background"]},
    reason=TEXT,
    source_refs=SOURCES,
)
CORPUS = obj(
    papers=arr(PAPER),
    queries=TEXTS,
    coverage_gaps=TEXTS,
    excluded=arr(obj(title=TEXT, reason=TEXT)),
    stop_reason=TEXT,
)
RESULT = obj(benchmark=TEXT, metric=TEXT, value=TEXT, condition=TEXT, source=TEXT)
CARD = obj(
    problem=TEXT,
    contributions=arr(
        obj(method=TEXT, mechanism=TEXT, assumptions=TEXTS, results=arr(RESULT), source_refs=SOURCES)
    ),
    relations=arr(obj(paper_id=TEXT, relation=TEXT, note=TEXT)),
    relevance=TEXT,
    limitations=TEXTS,
    coverage=arr(obj(section=TEXT, status={"enum": ["read", "partial", "unavailable"]}, notes=TEXT)),
    source_refs=SOURCES,
)
READING = obj(paper_id=TEXT, card=CARD)
ROUTE = obj(
    question=TEXT,
    explanation=TEXT,
    methods=TEXTS,
    paper_ids=TEXTS,
    evidence=SOURCES,
    gaps=TEXTS,
    discriminating_observations=TEXTS,
)
DOMAIN = obj(
    overview=TEXT, routes=arr(ROUTE), knowledge_gaps=TEXTS, evidence_limits=TEXTS, source_paper_ids=TEXTS
)
MEMBER = obj(expert_id=TEXT, paper_id=TEXT, method_contribution=TEXT, responsibility=TEXT)
TEMP = obj(expert_id=TEXT, specialty=TEXT, reason=TEXT, source_paper_ids=TEXTS)
SELECTION = obj(
    core_papers=arr(MEMBER),
    temporary_experts=arr(TEMP),
    coverage=arr(obj(question=TEXT, expert_ids=TEXTS, uncovered=TEXT)),
    alternatives=arr(obj(core_paper_ids=TEXTS, temporary_specialties=TEXTS, strengths=TEXTS, gaps=TEXTS)),
    rationale=TEXT,
)
TRACE = obj(
    trace_id=TEXT,
    before=TEXT,
    operation=TEXT,
    after=TEXT,
    depends_on=TEXTS,
    assumptions=TEXTS,
    alternatives=TEXTS,
    prediction=TEXT,
    source_refs=SOURCES,
)
PATTERN = obj(
    pattern_id=TEXT,
    trigger=TEXT,
    transformation=TEXT,
    invariants=TEXTS,
    preconditions=TEXTS,
    counterexamples=TEXTS,
    transfer_test=TEXT,
    trace_ids=TEXTS,
    source_refs=SOURCES,
)
CODE = obj(
    component=TEXT,
    source=TEXT,
    symbol=TEXT,
    inputs=TEXT,
    outputs=TEXT,
    mechanism=TEXT,
    assumptions=TEXTS,
    dependencies=TEXTS,
    verification={"enum": ["inspected", "tested", "unavailable"]},
    evidence=TEXTS,
)
KNOWLEDGE = obj(
    understanding=TEXT,
    mechanism=TEXT,
    assumptions=TEXTS,
    failures=TEXTS,
    coverage=arr(obj(section=TEXT, status=TEXT, impact=TEXT)),
    source_refs=SOURCES,
    idea_trace=arr(TRACE),
    reasoning_patterns=arr(PATTERN),
    code_map=arr(CODE),
    communication=arr(
        obj(element=TEXT, purpose=TEXT, construction=TEXT, transferable_rule=TEXT, source_refs=SOURCES)
    ),
    gaps=TEXTS,
)
EXPERT = obj(
    expert_id=TEXT,
    role={"enum": ["domain", "paper", "temporary"]},
    status=STATUS,
    source_paper_ids=TEXTS,
    source_paths=TEXTS,
    knowledge=KNOWLEDGE,
    reuse_assessment=TEXT,
    missing_materials=TEXTS,
)
REVIEW_CRITERIA = ["source_fidelity", "method_understanding", "transfer_limits", "implementation_claims"]
EXPERT_REVIEW = obj(
    accepted={"type": "boolean"},
    checks=arr(
        obj(
            criterion={"enum": REVIEW_CRITERIA}, verdict={"enum": ["pass", "fail", "unknown"]}, evidence=TEXTS
        ),
        4,
    ),
    blocking_issues=TEXTS,
    permitted_uses=TEXTS,
    limitations=TEXTS,
)
EXPERT_REVIEW["properties"]["checks"].update(
    maxItems=4,
    allOf=[
        {"contains": {"properties": {"criterion": {"const": criterion}}}} for criterion in REVIEW_CRITERIA
    ],
)
EXPERT_REVIEW["allOf"] = [
    {
        "if": {"properties": {"accepted": {"const": True}}},
        "then": {
            "properties": {
                "blocking_issues": {"maxItems": 0},
                "checks": {
                    "items": {"properties": {"verdict": {"const": "pass"}, "evidence": {"minItems": 1}}}
                },
            }
        },
    }
]


class KnowledgeBlocked(ValueError):
    """Materials or a scientifically usable expert are missing; retain all work."""


def _block(w, reason):
    w.state.update(status="needs_materials", reason=reason)
    w.save()
    raise KnowledgeBlocked(reason)


def _task(w, stage, subject, role, context, schema, validator=None):
    outer = w.state.get("outer_round", 1)
    return w.task(
        stage, subject, role, context, schema, key=f"k{outer}-{stage}-{subject}", validator=validator
    )


def _validate_corpus(corpus):
    identities = [p["paper_id"] for p in corpus["papers"]]
    if len(set(identities)) != len(identities):
        raise ValueError("Corpus paper_id values must be unique")


def _validate_reading(reading, paper_id):
    if reading["paper_id"] != paper_id:
        raise ValueError(f"Reading must refer to {paper_id}")


def _validate_sources(source_ids, papers, label):
    unknown = sorted(set(source_ids) - set(papers))
    if unknown:
        raise ValueError(f"{label} references papers outside the corpus: {unknown}")


def _validate_selection(selection, papers, research):
    core = selection["core_papers"]
    temporary = selection["temporary_experts"]
    if len(core) != research["core_papers"]:
        raise ValueError("Selected core-paper count must equal research.core_papers")
    if len({m["paper_id"] for m in core}) != len(core):
        raise ValueError("Core method experts must have distinct source papers")
    if not research["allow_temporary_experts"] and temporary:
        raise ValueError("Temporary experts are disabled in this project's configuration")
    _validate_sources([m["paper_id"] for m in core], papers, "Selected core experts")
    for member in temporary:
        _validate_sources(member["source_paper_ids"], papers, member["expert_id"])
    identities = ["domain"] + [m["expert_id"] for m in core + temporary]
    if len(set(identities)) != len(identities):
        raise ValueError("Expert IDs must be distinct, with domain reserved for the domain expert")


def _validate_expert(expert, expert_id, role, source_papers):
    if expert["expert_id"] != expert_id:
        raise ValueError(f"Expert identity must be {expert_id}")
    if expert["role"] != role or set(expert["source_paper_ids"]) != set(source_papers):
        raise ValueError(f"Expert {expert_id} must retain its assigned role and source papers")


def _brief(w):
    return (w.project / "research.md").read_text(encoding="utf-8")


def _paper_fingerprint(paper, project):
    # Changed source versions get a new card. Identity alone is not evidence.
    source = {k: paper[k] for k in ("title", "year", "doi", "arxiv_id", "url", "full_text_path")}
    if paper["full_text_path"]:
        path = Path(paper["full_text_path"])
        path = path if path.is_absolute() else project / path
        source["file_hash"] = file_hash(path) if path.is_file() else "unavailable"
    return digest(source)


def _frozen_record(w, kind, record, identity, sources=()):
    return freeze_asset(w.project, kind, record, identity, list(sources))


def _save_expert(w, expert, subject):
    if expert["status"] != "ready":
        _block(w, "; ".join(expert["missing_materials"]) or f"{subject}: missing core method evidence")
    review = _task(
        w,
        "expert_review",
        subject,
        "critic",
        {
            "brief": _brief(w),
            "expert": expert,
            "rule": "Check only decision-relevant understanding. Partial coverage is allowed when "
            "its limits do not invalidate the intended use. Author discovery history must "
            "remain unknown unless directly documented. Verify actual source anchors.",
        },
        EXPERT_REVIEW,
    )
    if not review["accepted"] or review["blocking_issues"]:
        _block(w, f"{subject}: " + "; ".join(review["blocking_issues"] or ["expert review rejected"]))
    record = deepcopy(expert)
    record["review"] = review
    return _frozen_record(w, "experts", record, subject, expert["source_paths"])


def _reuse(w, expert_id):
    candidates = []
    for path in find_expert_assets(w.project, expert_id):
        record = read_json(Path(path))
        verify_asset(record)
        if record.get("review", {}).get("accepted"):
            candidates.append(
                {
                    "path": path,
                    "knowledge": record["knowledge"],
                    "source_paper_ids": record["source_paper_ids"],
                    "review": record["review"],
                }
            )
    return candidates


def request_literature(w, questions):
    """Queue targeted gaps for the next outer round; retain accepted cards/assets."""
    knowledge = w.state.setdefault("knowledge", {})
    knowledge["pending_questions"] = list(
        dict.fromkeys(knowledge.get("pending_questions", []) + list(questions))
    )
    knowledge.pop("complete_outer_round", None)
    w.event("literature_requested", questions=questions)
    w.save()


def advance_knowledge(w):
    """Resume K1. Each task and accepted artifact remains available after interruption."""
    outer = w.state.get("outer_round", 1)
    k = w.state.setdefault("knowledge", {})
    if k.get("complete_outer_round") == outer:
        return
    brief = _brief(w)
    common = {
        "brief": brief,
        "research_config": w.config["research"],
        "as_of_date": datetime.now(timezone.utc).date().isoformat(),
        "inputs_dir": str(w.project / "inputs"),
        "library_dir": str(w.project / "library"),
        "questions_to_add": k.get("pending_questions", []),
    }
    k["scope"] = _task(
        w,
        "scope",
        "scope",
        "expert",
        common
        | {
            "instruction": "Plan retrieval from the current research question and open questions. "
            "Use a rolling lookback_years window ending on as_of_date. "
            "Existing library assets are source clues, not approved conclusions or a fixed shortlist. "
            "Cover competing method routes before deciding which explains the bottleneck. "
            "A method need not report our exact target metric to offer a relevant transferable mechanism. "
            "Do not select experts, extract reasoning patterns or audit every existing asset in scope; "
            "those responsibilities belong to later stages.",
        },
        SCOPE,
    )
    w.save()
    corpus = _task(
        w,
        "corpus",
        "corpus",
        "expert",
        {
            **common,
            "scope": k["scope"],
            "previous_corpus": k.get("corpus", {}),
            "instruction": "Keep useful prior entries; search gaps and changed sources only. "
            "Do not deep-read every paper or require every PDF locally. Provide "
            "verified public source URLs and honest access limits.",
        },
        CORPUS,
        validator=_validate_corpus,
    )
    papers = {p["paper_id"]: p for p in corpus["papers"]}
    k["corpus"] = corpus
    w.save()
    if not papers:
        _block(w, "No verified papers found. " + "; ".join(corpus["coverage_gaps"]))

    readings = k.setdefault("readings", {})
    fingerprints = k.setdefault("reading_fingerprints", {})
    for paper_id, paper in papers.items():
        fingerprint = _paper_fingerprint(paper, w.project)
        if paper_id in readings and fingerprints.get(paper_id) == fingerprint:
            continue
        # Reuse only the exact source metadata cache; a new task gets fresh selection context.
        cache_root = w.project / "library" / "reading_cache"
        cache = cache_root / f"{fingerprint}.json"
        if cache.is_file():
            record = read_json(cache)
            verify_asset(record)
            record = deepcopy(record)
            record["paper_id"] = paper_id
        else:
            record = _task(
                w,
                "reading",
                paper_id,
                "expert",
                {
                    **common,
                    "paper": paper,
                    "depth": "breadth card: contribution, mechanism outline, assumptions, "
                    "reported evidence and gaps; no exhaustive appendix/code reading "
                    "or mandatory full reasoning trace",
                },
                READING,
                validator=lambda data: _validate_reading(data, paper_id),
            )
            source = Path(paper["full_text_path"]) if paper["full_text_path"] else None
            if source and not source.is_absolute():
                source = w.project / source
            sources = [str(source)] if source and source.is_file() else []
            record = _frozen_record(w, "readings", record, fingerprint, sources)
            write_json(cache, record)
        readings[paper_id] = record
        fingerprints[paper_id] = fingerprint
        w.save()
    active_cards = {p: readings[p]["card"] for p in papers}
    graph = compile_graph(active_cards, {p: v["title"] for p, v in papers.items()})
    k["graph"] = graph
    k["graph_paths"] = write_views(w.run_dir / "knowledge" / "landscape", graph, active_cards)
    k["domain"] = _task(
        w,
        "domain",
        "domain",
        "expert",
        {
            **common,
            "scope": k["scope"],
            "cards": active_cards,
            "graph": graph,
            "instruction": "Compare explanations for each open question; "
            "do not assign a bottleneck before discriminating evidence. Distinguish "
            "a corpus gap from a field-wide gap. Request targeted reading for material gaps.",
        },
        DOMAIN,
        validator=lambda data: _validate_sources(data["source_paper_ids"], papers, "Domain"),
    )
    w.save()
    selection = _task(
        w,
        "selection",
        "team",
        "expert",
        {
            **common,
            "domain": k["domain"],
            "papers": corpus["papers"],
            "cards": active_cards,
            "selection_rule": "Choose method contributions "
            "covering competing solution routes; breadth reading need not be complete. "
            "Prefer recent relevant advances but explain older foundational choices. "
            "Compare complete teams with equal core seat counts including temporary expertise.",
        },
        SELECTION,
        validator=lambda data: _validate_selection(data, papers, w.config["research"]),
    )
    core = selection["core_papers"]
    k["selection"] = selection
    w.save()
    specs = [
        (
            "domain",
            "domain",
            "consultant",
            k["domain"]["source_paper_ids"],
            {"domain": k["domain"], "cards": active_cards},
        )
    ]
    specs += [
        (
            m["expert_id"],
            "paper",
            "paper",
            [m["paper_id"]],
            {
                "paper": papers[m["paper_id"]],
                "reading": readings[m["paper_id"]],
                "responsibility": m["responsibility"],
            },
        )
        for m in core
    ]
    specs += [
        (
            m["expert_id"],
            "temporary",
            "consultant",
            m["source_paper_ids"],
            {
                "specialty": m["specialty"],
                "reason": m["reason"],
                "papers": [papers[p] for p in m["source_paper_ids"] if p in papers],
            },
        )
        for m in selection["temporary_experts"]
    ]
    experts = []
    for expert_id, role, stage, source_papers, context in specs:
        response = _task(
            w,
            stage,
            expert_id,
            "expert",
            {
                **common,
                **context,
                "expert_id": expert_id,
                "role": role,
                "source_paper_ids": source_papers,
                "selection": selection,
                "reuse_candidates": _reuse(w, expert_id),
            },
            EXPERT,
            validator=lambda data: _validate_expert(data, expert_id, role, source_papers),
        )
        experts.append(_save_expert(w, response, expert_id))
        w.state["experts"] = experts
        w.save()
    k["complete_outer_round"] = outer
    k["pending_questions"] = []
    w.event("knowledge_completed", outer_round=outer, papers=len(papers), experts=len(experts))
    w.save()
