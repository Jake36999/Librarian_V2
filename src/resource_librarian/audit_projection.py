"""The Manager's bounded view of an audited session (HARNESS-04).

The Manager proposes the next step from this projection, never from the whole
transcript. Two kinds of content go into it:

- **Essential**, never trimmed: where the session stands, every active
  requirement in full with each predicate's own current outcome, the current
  contract, open questions, the budget and the capability manifest. If the
  essential part does not fit, the projection says so (`fits: False`) instead
  of cutting a constraint: the work must be split or narrowed.
- **Optional**, filled in priority order while there is room: the latest
  result details, aggregate counts, older reports as ids only, and as many
  recent events as fit.

Every projection says what it included, trimmed and omitted, and carries a
digest. Nothing in it depends on the clock, so the same log always gives the
same projection.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from . import audit_events


DEFAULT_TOKEN_BUDGET = 6000
RECENT_EVENTS = 12
MAX_REFERENCES = 20
TEXT_CLIP = 300

# Tier A verifiers the harness can name in a contract (HARNESS-05 to HARNESS-07
# implement them). Each id says exactly what a pass means, never more.
TIER_A_VERIFIERS = {
    "evidence.integrity": "the evidence object passes its integrity and ingestion checks",
    "coverage.status": "these named sources or parts have this recorded examination status",
    "quote.located": "the quote is present in the named evidence at the stated offset",
    "arithmetic.reproduces": "the calculation reproduces from its operands and assumptions",
    "claim_run.passed": "the declared claim-run passed in the recorded environment and scope",
    "index.findable": "the artifact resolves through the declared lookup",
    "target.diff_clean": "only the contract's write targets changed, as declared",
}

_EVENT_KEYS = ("id", "requirement", "contract", "predicate", "status", "outcome", "strength",
               "to", "path", "role", "revision", "epoch", "kind", "tool", "ok")


def estimate_tokens(value: Any) -> int:
    """The runner's estimate (3.5 characters per token) over canonical JSON."""
    return math.ceil(len(_canonical(value)) / 3.5)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str,
                      separators=(",", ":"))


def _clip(value: Any, limit: int = TEXT_CLIP) -> Any:
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [{len(value) - limit} more characters]"
    return value


def capability_manifest(*, tier: str, profile: Any = None, roots: list[str] | None = None,
                        routes: dict[str, dict[str, Any]] | None = None,
                        projects_on: bool = True) -> dict[str, Any]:
    """What the Core could admit: bundles, verifiers, roots and route availability.

    Bundles are those the caller's tier and profile allow, by the same policy as
    `select_bundle`. Roots default to the whole vault until DEPLOY adds content
    roots. Routes the caller does not report are marked unknown, never available.
    """
    from .agent_runtime import BUNDLES, effective_tier
    from .loop import narrowed
    allowed = {s.name for s in narrowed(effective_tier(tier, profile), "", projects_on, False)}
    permitted = getattr(profile, "allowed_bundles", None) or None
    bundles = [{"id": b.id, "purpose": b.purpose}
               for b in sorted(BUNDLES.values(), key=lambda b: b.id)
               if (permitted is None or b.id in permitted) and allowed.intersection(b.names)]
    reported = routes or {}
    roles = ("lead", "scribe", "clerk", "research_helper")
    return {
        "bundles": bundles,
        "verifiers": [{"id": k, "predicate": v} for k, v in sorted(TIER_A_VERIFIERS.items())],
        "roots": sorted(roots or ["."]),
        "routes": {role: reported.get(role, {"available": "unknown",
                                             "reason": "not reported by the Core"})
                   for role in sorted(set(roles) | set(reported))},
    }


def _compact_event(event: dict[str, Any]) -> dict[str, Any]:
    if event.get("type") == "message":
        # Conversation text is not copied in: a projection is not a transcript.
        return {"type": "message", "role": event.get("role"),
                "chars": len(str(event.get("text", ""))), "t": event.get("t")}
    out = {"type": event.get("type"), "t": event.get("t")}
    out.update({k: _clip(event[k], 120) for k in _EVENT_KEYS if k in event})
    return out


def _essential(session: Any, manifest: dict[str, Any], vault: Any) -> dict[str, Any]:
    audit = session.audit
    active, closed = {}, {}
    for rid, req in sorted(audit.requirements.items()):
        status = audit.requirement_status(rid)
        if status in ("verified", "human_accepted"):
            closed[rid] = status
            continue
        active[rid] = {
            "text": req["text"], "closure": req["closure"], "revision": req["revision"],
            "status": status,
            # One outcome per predicate: a passing quote check cannot hide a
            # failing arithmetic check on the same requirement.
            "predicates": {p: audit_events._predicate_outcome(audit, rid, p)
                           for p in req["predicates"]}}
    contract = None
    if audit.current_contract:
        c = audit.contracts[audit.current_contract]
        contract = {"id": audit.current_contract, "revision": c["revision"],
                    "requirements": c["requirements"], "read": c["read"], "write": c["write"],
                    "role": c["role"], "admitted_epoch": c["admitted_epoch"]}
    limit = session.audited_round_limit(vault) if vault is not None else None
    return {
        "session": {"id": session.id, "purpose": session.purpose,
                    "question": _clip(session.question), "status": session.status,
                    "phase": session.phase, "round": session.audit_round,
                    "epoch": audit.epoch, "outcome": audit_events.session_outcome(audit),
                    **({"invalid_history": audit.invalid} if audit.invalid else {})},
        "requirements": active,
        "closed_requirements": closed,
        "contract": contract,
        "open_questions": [{"id": q["id"], "question": _clip(q["question"])}
                           for q in session.open_questions()],
        "budget": {"phase_calls_left": session.budget_left(),
                   **({"rounds_left": max(0, limit - session.audit_round),
                       "round_limit": limit} if limit is not None else {})},
        "manifest": manifest,
    }


def _latest_results(audit: Any) -> tuple[dict[str, Any], set[str]]:
    latest: dict[str, Any] = {}
    for rid, req in audit.requirements.items():
        for predicate in req["predicates"]:
            found = audit_events._latest_result(audit, rid, predicate)
            if found:
                ident, result = found
                latest[f"{rid}: {predicate}"] = {"id": ident, **{
                    k: result[k] for k in ("verifier", "strength", "outcome", "artifacts",
                                           "epoch")}}
    return latest, {v["id"] for v in latest.values()}


def _counts(events: list[dict[str, Any]], audit: Any) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    for event in events:
        by_type[event.get("type", "?")] = by_type.get(event.get("type", "?"), 0) + 1
    outcomes: dict[str, int] = {}
    for result in audit.results.values():
        outcomes[result["outcome"]] = outcomes.get(result["outcome"], 0) + 1
    return {"events": dict(sorted(by_type.items())), "results_by_outcome":
            dict(sorted(outcomes.items())), "external_edits": len(audit.external_edits),
            "reductions": len(audit.reductions)}


def _references(audit: Any, current: set[str]) -> dict[str, Any]:
    """Older reports by id only, newest first, capped; the rest are counted."""
    older = [ident for ident in reversed(list(audit.results)) if ident not in current]
    contracts = [f"{cid}@r{c['revision']}" for cid, c in sorted(audit.contracts.items())
                 if cid != audit.current_contract]
    return {"older_results": older[:MAX_REFERENCES],
            "older_results_not_listed": max(0, len(older) - MAX_REFERENCES),
            "other_contracts": contracts[:MAX_REFERENCES],
            "other_contracts_not_listed": max(0, len(contracts) - MAX_REFERENCES),
            "where": "the session log holds every report in full"}


def project(session: Any, events: list[dict[str, Any]], *, manifest: dict[str, Any],
            vault: Any = None, token_budget: int = DEFAULT_TOKEN_BUDGET,
            recent: int = RECENT_EVENTS) -> dict[str, Any]:
    """Build the Manager projection for `session`, within `token_budget` tokens."""
    essential = _essential(session, manifest, vault)
    used = estimate_tokens(essential)
    accounting: dict[str, Any] = {"budget": token_budget, "included": ["essential"],
                                  "trimmed": {}, "omitted": {}}
    if used > token_budget:
        out = {"fits": False,
               "reason": (f"the active requirements, contract and manifest need about {used} "
                          f"tokens, over the {token_budget}-token budget. No constraint is "
                          "cut to fit: split the work or narrow the requirements"),
               "session": essential["session"], "accounting": {**accounting, "tokens": used}}
        out["digest"] = _digest(out)
        return out

    projection: dict[str, Any] = {"fits": True, **essential}
    latest, current_ids = _latest_results(session.audit)
    optional = (("latest_results", latest),
                ("counts", _counts(events, session.audit)),
                ("references", _references(session.audit, current_ids)))
    for name, value in optional:
        cost = estimate_tokens({name: value})
        if used + cost <= token_budget:
            projection[name] = value
            used += cost
            accounting["included"].append(name)
        else:
            accounting["omitted"][name] = "no room within the budget"

    # Recent events last: as many of the newest as fit, oldest dropped first.
    tail = [_compact_event(e) for e in events[-recent:]]
    while tail and used + estimate_tokens({"recent_events": tail}) > token_budget:
        tail.pop(0)
    if tail:
        projection["recent_events"] = tail
        used += estimate_tokens({"recent_events": tail})
        accounting["included"].append("recent_events")
    accounting["trimmed"]["recent_events"] = min(recent, len(events)) - len(tail)
    accounting["omitted"]["earlier_events"] = max(0, len(events) - min(recent, len(events)))
    accounting["tokens"] = used
    projection["accounting"] = accounting
    projection["digest"] = _digest(projection)
    return projection


def _digest(value: dict[str, Any]) -> str:
    body = {k: v for k, v in value.items() if k != "digest"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()[:24]
