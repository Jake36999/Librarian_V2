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
from .closure import VERIFIERS


DEFAULT_TOKEN_BUDGET = 6000
RECENT_EVENTS = 12
MAX_REFERENCES = 20
TEXT_CLIP = 300


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


def capability_manifest(*, tier: str, profile: Any = None, roots: list[Any] | None = None,
                        routes: dict[str, dict[str, Any]] | None = None,
                        projects_on: bool = True) -> dict[str, Any]:
    """What the Core could admit: bundles, verifiers, roots and route availability.

    Bundles are those the caller's tier and profile allow, by the same policy as
    `select_bundle`. Roots default to the whole vault until DEPLOY adds content
    roots. Routes the caller does not report are marked unknown, never available.
    """
    from .agent_runtime import BUNDLES, bundle_selection
    audited_phases = ("manage", "preflight", "execute", "audit", "reduce")
    permitted = getattr(profile, "allowed_bundles", None) if profile is not None else None
    candidate_ids = set(BUNDLES) if not permitted else set(permitted)
    # ``research`` is the runtime's phase-specific wildcard. Expand only to
    # the actual audited phases, not unrelated role bundles such as Clerk or
    # Draft, and let the shared selector derive each surface below.
    if permitted and "research" in permitted:
        candidate_ids.update(audited_phases)
    bundles = []
    for bundle in sorted((BUNDLES[name] for name in candidate_ids), key=lambda b: b.id):
        selected = bundle_selection(tier, bundle.id, projects_on=projects_on,
                                    profile=profile)
        if selected.allowed and selected.offered:
            # Keep the essential Manager projection compact. The detailed
            # reachability rows below are only the five audited phases.
            bundles.append({"id": bundle.id, "purpose": bundle.purpose})
    audited = {}
    for phase in audited_phases:
        selected = bundle_selection(tier, phase, projects_on=projects_on, working=True,
                                    profile=profile, purpose="audited")
        audited[phase] = {
            "bundle": selected.bundle_id, "allowed": selected.allowed,
            "registered": list(selected.registered),
            "offered": [spec.name for spec in selected.offered],
            "admission": "checked_at_call_time",
            **({"fallback": selected.fallback} if selected.fallback else {}),
        }
    raw_roots = roots if roots is not None else [
        {"path": ".", "access": "read_write", "attached": False}]
    root_access = []
    for raw in raw_roots:
        if isinstance(raw, dict):
            path = str(raw.get("path") or "").strip()
            if path:
                root_access.append({"path": path,
                                    "access": str(raw.get("access") or "unknown"),
                                    "attached": bool(raw.get("attached"))})
        elif str(raw).strip():
            root_access.append({"path": str(raw).strip(), "access": "unknown",
                                "attached": False})
    root_access.sort(key=lambda row: row["path"])
    reported = routes or {}
    roles = ("lead", "scribe", "clerk", "research_helper")
    return {
        "bundles": bundles,
        "audited_bundles": audited,
        # HARNESS-06 telemetry: how many bundles the tier and profile filter left.
        "bundle_counts": {"registered": len(BUNDLES), "after_filter": len(bundles)},
        # One registry (closure.py): each id says exactly what a pass means.
        "verifiers": [{"id": k, "kind": v.kind, "max_strength": v.max_strength,
                       "predicate": v.predicate} for k, v in sorted(VERIFIERS.items())],
        "roots": [row["path"] for row in root_access],
        "root_access": root_access,
        "profile": ({key: getattr(profile, key) for key in (
            "id", "role", "revision", "permission_ceiling", "required_qualification",
            "allowed_bundles") if hasattr(profile, key)} if profile is not None else
                    {"status": "not_reported"}),
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
                           for p in req["predicates"]},
            # REMED-06: each predicate's stable id, for plans and checks.
            "ids": {f"{rid}.{req['ids'][p]}": p for p in req["predicates"]
                    if p in (req.get("ids") or {})},
            # The verifier the person named for a predicate: the plan must use it.
            **({"verifiers": dict(req["verifiers"])} if req.get("verifiers") else {}),
            # MF-010: why a blocked or failed requirement stopped, and who stopped it.
            **({"stop": stop} if (stop := audit_events.stop_reason(audit, rid)) else {})}
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
                    **({"invalid_history": audit.invalid} if audit.invalid else {}),
                    **({"legacy_history": audit.legacy} if audit.legacy else {})},
        "requirements": active,
        "closed_requirements": closed,
        "contract": contract,
        "open_questions": [{"id": q["id"], "question": _clip(q["question"])}
                           for q in session.open_questions()],
        **({"contract_skeleton": skeleton}
           if (skeleton := contract_skeleton(session, vault)) is not None else {}),
        **({"stall": dict(session.stall)} if any(session.stall.values()) else {}),
        "budget": {"phase_calls_left": session.budget_left(),
                   **({"rounds_left": max(0, limit - session.audit_round),
                       "round_limit": limit} if limit is not None else {})},
        "manifest": manifest,
    }


SKELETON_PHASES = ("manage", "preflight")
_STAGING_VERIFIERS = frozenset({"target.diff_clean", "boundary.staged"})


def _bound_reads(vault: Any, params: dict[str, Any]) -> set[str]:
    """The vault paths a bound subject names: what the contract must let it read."""
    from .closure import _note_paths
    out: set[str] = set()
    if vault is None:
        return out
    for key in ("note", "source"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            value = value.strip().replace("\\", "/")
            out.update([value] if value.endswith(".md") and (vault.root / value).is_file()
                       else _note_paths(vault, value))
    ident = params.get("evidence")
    if isinstance(ident, str):
        from .evidence import EvidenceStore
        located = EvidenceStore(vault).locate(ident.strip())
        if located is not None:
            out.add(located.relative_to(vault.root).as_posix())
    return out


def contract_skeleton(session: Any, vault: Any) -> dict[str, Any] | None:
    """`admit_contract`'s arguments, built from the person's bindings alone
    (REMED-06, U2): the requirements the proposal names (or every open one),
    each predicate keyed by its stable id with the verifier the person named,
    the operations those checks need, and the paths their subjects name. A
    predicate the person named no verifier for is not guessed: it is listed
    under `needs`, with the verifiers that could close it. Shown while a
    contract is being prepared; it depends on the log and the library only."""
    from .closure import OPERATIONS, authoritative_verifiers
    audit = session.audit
    if session.purpose != "audited" or audit.halted or session.phase not in SKELETON_PHASES:
        return None
    proposal = session.plan.get("proposal")
    named = proposal.get("requirements") if isinstance(proposal, dict) else None
    closed = ("verified", "human_accepted")
    rids = [r for r in (named if isinstance(named, list) else []) if r in audit.requirements] \
        or [r for r in sorted(audit.requirements) if audit.requirement_status(r) not in closed]
    if not rids:
        return None
    verifiers: dict[str, str] = {}
    needs: list[dict[str, Any]] = []
    operations, reads, stage = {"read"}, set(), False
    for rid in rids:
        req = audit.requirements[rid]
        stage = stage or req["closure"] == "human_judgment"
        for predicate in req["predicates"]:
            pid = f"{rid}.{(req.get('ids') or {}).get(predicate, '')}"
            bound = (req.get("verifiers") or {}).get(predicate)
            if bound:
                verifiers[pid] = bound["verifier"]
                stage = stage or bound["verifier"] in _STAGING_VERIFIERS
                if bound["verifier"] == "quote.located":
                    operations.add("untrusted")     # the evidence text is read to quote it
                reads |= _bound_reads(vault, bound.get("params") or {})
            elif req["closure"] == "authoritative":
                needs.append({"predicate": pid, "text": predicate,
                              "why": "the person named no verifier for it: plan one that "
                                     "establishes it, or ask the person to name one",
                              "eligible": authoritative_verifiers()})
    write = []
    if stage:
        operations.add("stage")
        if vault is not None:
            folder = vault.work("staging") / "audited" / session.id
            write = [folder.relative_to(vault.root).as_posix() + "/"]
    return {"tool": "admit_contract",
            "arguments": {"contract_id": f"C{len(audit.contracts) + 1}", "requirements": rids,
                          "verifiers": verifiers,
                          "operations": [o for o in OPERATIONS if o in operations],
                          "read": sorted(reads), "write": write},
            "complete": not needs, **({"needs": needs} if needs else {}),
            "from": "the person's bindings and the library; nothing in it is guessed"}


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
