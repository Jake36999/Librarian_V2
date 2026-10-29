"""Research rounds in an audited session (HARNESS-06).

Each phase of a round has its tool here, and the person has theirs:

| Phase | Tool | What it records |
| --- | --- | --- |
| preflight | admit_contract | the contract, if the Core's rules admit it |
| execute | stage_artifact | a draft in staging and its fingerprint (an artifact) |
| audit | verify_grain | one Tier A check of one predicate, with its exact statement |
| reduce | reduce_round | each requirement's status, from the results alone |
| any (person) | accept_artifact, reject_artifact, request_evidence, set_requirement | the person's decision |

Nothing here declares the research complete. Grains with a deterministic
check close through it (`research_grains.py`); synthesis and interpretation
are staged and stay open until the person accepts the exact artifact.
"""
from __future__ import annotations

import re
from typing import Any

from .. import audit_events, research_grains
from ..coordination import atomic_write_text, fingerprint
from ..registry import Card, Context, tool
from ..revisions import WriteIntent
from ..rules import Refusal
from .library import IndexGateway
from .sessions import _session, _store


def _audited(ctx: Context):
    session = _session(ctx)
    if session.purpose != "audited":
        raise TypeError("this belongs to an audited session: open_session(purpose='audited')")
    return session


def _next_id(table: Any, prefix: str) -> str:
    return f"{prefix}{len(table) + 1}"


def staging_folder(ctx: Context, session_id: str) -> str:
    """Where a session's drafts are staged, vault-relative, ending in '/'."""
    folder = ctx.vault.work("staging") / "audited" / session_id
    return folder.relative_to(ctx.vault.root).as_posix() + "/"


def _artifact_rel(ctx: Context, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")[:60]
    if not slug:
        raise TypeError("name the draft: letters or digits")
    return f"{staging_folder(ctx, ctx.session)}{slug}.md"


def _stage_intent(ctx: Context, kwargs: dict[str, Any]) -> WriteIntent:
    rel = _artifact_rel(ctx, str(kwargs.get("name", "")))
    return WriteIntent((rel,), absent=() if (ctx.vault.root / rel).exists() else (rel,))


@tool("admit_contract", tier="contribute", effect="write", phases=("preflight",),
      card=Card("Ask the Core to admit this round's contract",
                "the proposal is settled and the round needs its bounded contract",
                "Names the requirements it addresses, what it may read and write, the operations "
                "it may use and, for each predicate, the verifier that will check it. The Core "
                "refuses a plan that could not close an authoritative requirement. Drafts go "
                "under the session's staging folder (staged_in)"))
def admit_contract(ctx: Context, contract_id: str, requirements: list[str],
                   write: list[str] | None = None, read: list[str] | None = None,
                   verifiers: dict | None = None, operations: list[str] | None = None) -> dict:
    session = _audited(ctx)
    existing = session.audit.contracts.get(contract_id)
    event = {"type": "contract", "id": contract_id,
             "revision": existing["revision"] + 1 if existing else 1,
             "requirements": list(requirements), "role": "lead", "epoch": session.audit.epoch,
             "targets": {"read": list(read or []), "write": list(write or [])},
             "verifiers": dict(verifiers or {})}
    if operations:
        event["operations"] = list(operations)
    _store(ctx).append_audit(session.id, event)
    admitted = _store(ctx).load(session.id).audit.contracts[contract_id]
    return {"contract": contract_id, "revision": admitted["revision"],
            "verifiers": admitted["verifiers"], "operations": admitted["operations"],
            "staged_in": staging_folder(ctx, session.id)}


@tool("stage_artifact", tier="contribute", effect="write", phases=("execute",),
      intent=_stage_intent,
      card=Card("Stage a draft (a synthesis, an interpretation) for the person",
                "the contract's work produced text a person must judge",
                "Written to the session's staging folder, never to the library, and recorded with "
                "its fingerprint so the audit can check it is unchanged. Synthesis is the "
                "person's to accept: staging it closes nothing"))
def stage_artifact(ctx: Context, name: str, text: str) -> dict:
    session = _audited(ctx)
    contract = session.audit.current_contract
    if not contract:
        raise Refusal("CONTRACT_SCOPE", "no admitted contract is executing; preflight first")
    rel = _artifact_rel(ctx, name)
    path = ctx.vault.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    ident = _next_id(session.audit.artifacts, "A")
    _store(ctx).append_audit(session.id, {"type": "artifact", "id": ident, "path": rel,
                                          "fingerprint": fingerprint(path),
                                          "contract": contract})
    return {"artifact": ident, "path": rel, "contract": contract,
            "next": "the audit checks it is unchanged (target.diff_clean); the person accepts "
                    "or rejects it (accept_artifact / reject_artifact)"}


@tool("verify_grain", tier="contribute", effect="write", phases=("audit",),
      card=Card("Run the planned Tier A check for one predicate",
                "auditing a contract: each planned predicate needs its result",
                "Runs the verifier the contract planned for 'requirement: predicate' and records "
                "its result with the exact statement it established (an offset, a hash, a count), "
                "never more. params by verifier - evidence.integrity: evidence, item; "
                "coverage.status: source, parts, status; quote.located: evidence, quote; "
                "arithmetic.reproduces: note (path); claim_run.passed: run; index.findable: "
                "note (name); target.diff_clean: none. A predicate no verifier can check "
                "returns no_suitable_tool and goes to the person"))
def verify_grain(ctx: Context, requirement: str, predicate: str,
                 params: dict | None = None) -> dict:
    session = _audited(ctx)
    audit = session.audit
    contract = audit.current_contract
    if not contract:
        raise Refusal("CONTRACT_SCOPE", "no admitted contract to audit")
    planned = audit.contracts[contract]["verifiers"].get(f"{requirement}: {predicate}")
    if planned not in research_grains.CHECKS:
        # No registered check can establish it: say so, close nothing.
        return {"outcome": research_grains.NO_SUITABLE_TOOL, "requirement": requirement,
                "predicate": predicate, "planned": planned or "",
                "detail": "no Tier A check establishes this predicate; it stays with the person"}
    context: dict[str, Any] = {"session": session}
    if planned == "index.findable":
        context["index_run"] = IndexGateway(ctx).run
    check = research_grains.run(planned, ctx.vault, dict(params or {}), **context)
    ident = _next_id(audit.results, "V")
    mine = [a for a, v in audit.artifacts.items() if v["contract"] == contract]
    _store(ctx).append_audit(session.id, {
        "type": "verifier_result", "id": ident, "requirement": requirement,
        "contract": contract, "contract_revision": audit.contracts[contract]["revision"],
        "predicate": predicate, "verifier": planned, "strength": check.strength,
        "outcome": check.outcome, "epoch": audit.epoch, "statement": check.statement,
        "artifacts": mine if planned == "target.diff_clean" else []})
    return {"result": ident, "outcome": check.outcome, "strength": check.strength,
            "statement": check.statement, "verifier": planned,
            **({"detail": check.detail} if check.detail else {}),
            **({"evidence": list(check.evidence)} if check.evidence else {})}


def _core_status(audit: Any, rid: str) -> tuple[str, list[str], str]:
    """A requirement's status from its latest results alone, with the results cited."""
    req = audit.requirements[rid]
    latest = {p: audit_events._latest_result(audit, rid, p) for p in req["predicates"]}
    cited = [hit[0] for hit in latest.values() if hit]
    outcomes = {p: hit[1]["outcome"] if hit else "" for p, hit in latest.items()}
    if req["closure"] == "human_judgment":
        return "open", cited, "awaiting the person's acceptance of a staged artifact"
    if any(o == "fail" for o in outcomes.values()):
        return "failed", cited, "a predicate's latest result is fail"
    unplanned = [p for p in req["predicates"] if audit_events._unplanned(audit, rid, p)]
    if req["closure"] == "authoritative":
        if all(hit and hit[1]["outcome"] == "pass" and hit[1]["strength"] in ("exact", "bounded")
               for hit in latest.values()):
            return "verified", cited, ""
        if any(o == "unavailable" for o in outcomes.values()):
            return "blocked", cited, "a check could not run"
        return "open", cited, "not every predicate has an exact or bounded pass"
    if unplanned and not any(o == "pass" for o in outcomes.values()):
        return "open", cited, f"{research_grains.NO_SUITABLE_TOOL}: " + "; ".join(unplanned)
    if any(o == "pass" for o in outcomes.values()):
        return "partial", cited, ""
    return "open", cited, "no predicate passed"


@tool("reduce_round", tier="contribute", effect="write", phases=("reduce",),
      card=Card("Reduce this round's results to requirement statuses",
                "every planned predicate has a result and the round is ending",
                "The Core's reduction: verified only when every predicate of an authoritative "
                "requirement has an exact or bounded pass; human-judgment requirements stay open "
                "until the person accepts. Requirements the person already settled this epoch "
                "are left as they are"))
def reduce_round(ctx: Context) -> dict:
    session = _audited(ctx)
    audit = session.audit
    contract = audit.current_contract
    if not contract:
        raise Refusal("CONTRACT_SCOPE", "no admitted contract to reduce")
    out = {}
    for rid in audit_events.unreduced_requirements(audit, contract):
        status, cited, reason = _core_status(audit, rid)
        _store(ctx).append_audit(session.id, {"type": "reduction", "requirement": rid,
                                              "status": status, "results": cited, "by": "core",
                                              "epoch": audit.epoch,
                                              **({"reason": reason} if reason else {})})
        out[rid] = {"status": status, **({"reason": reason} if reason else {})}
    summary = audit_events.summary(_store(ctx).load(session.id).audit)
    return {"reduced": out, "outcome": summary["outcome"], "scope": summary["scope"]}


# ---------------------------------------------------- the person's checkpoint controls

def _artifact(session: Any, ctx: Context, artifact: str) -> dict:
    found = session.audit.artifacts.get(artifact)
    if found is None:
        raise TypeError(f"no artifact {artifact!r} in this session")
    return found


@tool("accept_artifact", tier="curate", effect="write", scope="session",
      card=Card("Accept a staged artifact as meeting a requirement",
                "the person has read the exact draft and judges it meets the requirement",
                "The person's decision alone. It names the exact artifact; if the file changed "
                "since it was staged, accept the new version only after it is staged again"))
def accept_artifact(ctx: Context, requirement: str, artifact: str) -> dict:
    session = _audited(ctx)
    found = _artifact(session, ctx, artifact)
    path = ctx.vault.root / found["path"]
    if not path.is_file() or fingerprint(path) != found["fingerprint"]:
        raise Refusal("AUDIT_EVENT_INVALID", f"{artifact} ({found['path']}) changed since it was "
                                             "staged: the accepted text must be the staged text")
    _store(ctx).append_audit(session.id, {"type": "reduction", "requirement": requirement,
                                          "status": "human_accepted", "results": [],
                                          "by": "person", "artifact": artifact,
                                          "epoch": session.audit.epoch})
    return {"requirement": requirement, "status": "human_accepted", "artifact": artifact}


@tool("reject_artifact", tier="curate", effect="write", scope="session",
      card=Card("Send a staged artifact back",
                "the person judges a draft does not meet the requirement",
                "The requirement stays open with the person's reason recorded, so the next round "
                "starts from it"))
def reject_artifact(ctx: Context, requirement: str, artifact: str, reason: str) -> dict:
    session = _audited(ctx)
    _artifact(session, ctx, artifact)
    _store(ctx).append_audit(session.id, {"type": "reduction", "requirement": requirement,
                                          "status": "open", "results": [], "by": "person",
                                          "rejected": artifact, "reason": reason,
                                          "epoch": session.audit.epoch})
    return {"requirement": requirement, "status": "open", "rejected": artifact}


@tool("request_evidence", tier="curate", effect="write", scope="session",
      card=Card("Ask for evidence a requirement must have",
                "the person wants something located or checked before accepting",
                "Adds a predicate to the requirement, which revises it: earlier closures go "
                "stale and the next contract must plan a check for the new predicate"))
def request_evidence(ctx: Context, requirement: str, what: str) -> dict:
    session = _audited(ctx)
    req = session.audit.requirements.get(requirement)
    if req is None:
        raise TypeError(f"no requirement {requirement!r}; set_requirement creates one")
    predicate = f"evidence is located for: {what.strip()}"
    if predicate in req["predicates"]:
        return {"requirement": requirement, "predicate": predicate, "already": True}
    _store(ctx).append_audit(session.id, {
        "type": "requirement", "id": requirement, "revision": req["revision"] + 1,
        "text": req["text"], "closure": req["closure"],
        "predicates": req["predicates"] + [predicate], "by": "person"})
    return {"requirement": requirement, "revision": req["revision"] + 1, "predicate": predicate}
