"""Small versioned research graph. Progress never substitutes for scientific evidence."""

from datetime import datetime, timezone
from .storage import digest


def now():
    return datetime.now(timezone.utc).isoformat()


def new_state(run_id, inputs):
    return dict(
        schema_version=2,
        run_id=run_id,
        input_hash=inputs,
        created_at=now(),
        status="ready",
        phase="knowledge",
        outer_round=1,
        cycle=0,
        claims={},
        evidence={},
        runs={},
        tasks={},
        knowledge={},
        experts=[],
        protocol={},
        draft={},
        frozen={},
        selected=[],
        confirmed=[],
        approvals=[],
        history=[],
        usage={"worker_calls": 0, "active_seconds": 0.0},
        reason="",
    )


def add_claim(state, data, owner, key):
    found = next((c for c in state["claims"].values() if c["creation_key"] == key), None)
    if found:
        return found["ref"]
    identity = data["claim_id"]
    prior = [c for c in state["claims"].values() if c["claim_id"] == identity]
    if prior and any(c["owner"] != owner for c in prior):
        raise ValueError("Only the author may revise a claim; use a new ID with parents for combinations")
    for parent in data.get("parents", []):
        if parent not in state["claims"]:
            raise ValueError(f"Unknown parent claim version: {parent}")
    version = max((c["version"] for c in prior), default=0) + 1
    ref = f"{identity}@{version}"
    for c in prior:
        c["active"] = False
    state["claims"][ref] = dict(
        data,
        ref=ref,
        version=version,
        owner=owner,
        creation_key=key,
        active=True,
        verdict="untested",
        stage="proposed",
        evidence_ids=[],
    )
    return ref


def add_evidence(state, kind, claim_ref, source, content):
    if claim_ref and claim_ref not in state["claims"]:
        raise ValueError(f"Unknown evidence target: {claim_ref}")
    record = dict(kind=kind, claim_ref=claim_ref, source=source, hash=digest(content), content=content)
    eid = "e-" + digest(record)[:16]
    state["evidence"][eid] = dict(record, evidence_id=eid)
    if claim_ref and eid not in state["claims"][claim_ref]["evidence_ids"]:
        state["claims"][claim_ref]["evidence_ids"].append(eid)
    return eid


def set_verdict(state, ref, verdict, evidence_ids, reason):
    if verdict not in {"supported", "refuted", "inconclusive", "unverifiable_with_resources"}:
        raise ValueError("Invalid scientific verdict")
    records = [state["evidence"][eid] for eid in evidence_ids]
    if any(e["claim_ref"] != ref for e in records):
        raise ValueError("Evidence must bind to this claim version")
    if verdict in {"supported", "refuted"} and not any(
        e["kind"] == "literature" or (e["kind"] == "run" and e["content"]["outcome"] == "completed")
        for e in records
    ):
        raise ValueError("An assessment or review alone cannot establish an empirical claim")
    state["claims"][ref].update(verdict=verdict, verdict_reason=reason)


def active_claims(state):
    return [c for c in state["claims"].values() if c["active"]]
