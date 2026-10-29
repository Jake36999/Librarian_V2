"""The audited-session event vocabulary (HARNESS-02).

An audited session keeps its requirements, contracts, evidence and verifier
results as typed Session events, appended through the Core writer like every
other session event; this module is their rule book, not a second store. Each
event is checked against the state folded from the events before it, so a
history either replays to the same state or is reported invalid - never
silently trusted. Questions reuse the Session's own `question`/`answer`
events.

The epoch is what makes evidence go stale. A person revising a requirement,
a revised contract and an edit made outside the Core each advance it, and a
verifier result or a closure counts only at the epoch it was made in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .rules import Refusal


AUDIT_EVENTS = frozenset({"requirement", "contract", "artifact", "fact", "verifier_result",
                          "reduction", "external_edit"})

CLOSURES = ("authoritative", "partial", "human_judgment")
STRENGTHS = ("exact", "bounded", "advisory")
RESULTS = ("pass", "fail", "unavailable", "inconclusive")
FACT_BASES = ("observed", "inferred", "model", "refuted")
STATUSES = ("open", "partial", "verified", "human_accepted", "blocked", "failed")
EDIT_SOURCES = ("watcher", "core_check")


@dataclass
class AuditState:
    epoch: int = 0
    requirements: dict[str, dict[str, Any]] = field(default_factory=dict)
    contracts: dict[str, dict[str, Any]] = field(default_factory=dict)
    artifacts: dict[str, dict[str, Any]] = field(default_factory=dict)
    facts: dict[str, dict[str, Any]] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    reductions: list[dict[str, Any]] = field(default_factory=list)
    external_edits: list[dict[str, Any]] = field(default_factory=list)
    current_contract: str = ""   # the contract most recently admitted (HARNESS-03 rounds)
    # Set when replay met an event the rules refuse. The history is then
    # reported, never trusted, and no further audit event is accepted.
    invalid: str = ""

    @property
    def used(self) -> bool:
        return bool(self.requirements or self.external_edits or self.invalid)

    def watched_paths(self) -> set[str]:
        """Every vault path this session read or targets: what an outside edit stales."""
        paths = {a["path"] for a in self.artifacts.values()}
        for contract in self.contracts.values():
            paths.update(contract["read"])
            paths.update(contract["write"])
        return paths

    def requirement_status(self, requirement_id: str) -> str:
        """A closure made at an older epoch is `stale`, whatever it was."""
        req = self.requirements[requirement_id]
        if req["status"] in ("verified", "human_accepted") and req["status_epoch"] < self.epoch:
            return "stale"
        return req["status"]


def _refuse(message: str) -> Refusal:
    return Refusal("AUDIT_EVENT_INVALID", message)


def _text(event: dict[str, Any], key: str) -> str:
    value = event.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _refuse(f"{event.get('type')} needs a non-empty {key}")
    return value.strip()


def _choice(event: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str:
    value = event.get(key)
    if value not in allowed:
        raise _refuse(f"{event.get('type')} {key} must be one of {list(allowed)}, not {value!r}")
    return value


def _rel_path(value: Any) -> str:
    """A vault-relative path in POSIX form; never absolute and never climbing out."""
    if not isinstance(value, str) or not value.strip():
        raise _refuse("a path must be a non-empty string")
    path = value.strip().replace("\\", "/")
    if path.startswith("/") or (len(path) > 1 and path[1] == ":") or ".." in path.split("/"):
        raise _refuse(f"path {value!r} must be vault-relative")
    return path


def _id_list(event: dict[str, Any], key: str, known: dict[str, Any], what: str) -> list[str]:
    values = event.get(key) or []
    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
        raise _refuse(f"{event.get('type')} {key} must be a list of ids")
    for value in values:
        if value not in known:
            raise _refuse(f"{event.get('type')} names unknown {what} {value!r}")
    return list(values)


def _epoch(state: AuditState, event: dict[str, Any]) -> int:
    """Results and closures are made against the current state, never an older one."""
    epoch = event.get("epoch")
    if epoch != state.epoch:
        raise _refuse(f"{event.get('type')} was made at epoch {epoch!r}, but the session is at "
                      f"epoch {state.epoch}: recheck against the current state")
    return state.epoch


def _revision(state_table: dict[str, dict[str, Any]], event: dict[str, Any]) -> int:
    ident = _text(event, "id")
    revision = event.get("revision", 1)
    expected = state_table[ident]["revision"] + 1 if ident in state_table else 1
    if revision != expected:
        raise _refuse(f"{event['type']} {ident} revision must be {expected}, not {revision!r}")
    return revision


def _new_id(table: dict[str, Any], event: dict[str, Any]) -> str:
    ident = _text(event, "id")
    if ident in table:
        raise _refuse(f"{event['type']} {ident} already exists; record a new id")
    return ident


# ------------------------------------------------------------------ the rules

def _requirement(state: AuditState, event: dict[str, Any]) -> None:
    revision = _revision(state.requirements, event)
    # A model may suggest a scope; only a person's action makes it operative.
    if event.get("by") != "person":
        raise _refuse("a requirement is set or revised only by the person (by='person')")
    closure = _choice(event, "closure", CLOSURES)
    predicates = event.get("predicates") or []
    if not isinstance(predicates, list) or not all(isinstance(p, str) and p.strip()
                                                   for p in predicates):
        raise _refuse("requirement predicates must be a list of non-empty strings")
    if closure == "authoritative" and not predicates:
        raise _refuse("an authoritative requirement needs at least one acceptance predicate")
    text = _text(event, "text")
    if revision > 1:
        state.epoch += 1
    state.requirements[event["id"]] = {
        "text": text, "closure": closure, "predicates": list(predicates),
        "revision": revision, "status": "open", "status_epoch": state.epoch}


def _contract(state: AuditState, event: dict[str, Any]) -> None:
    revision = _revision(state.contracts, event)
    requirements = _id_list(event, "requirements", state.requirements, "requirement")
    if not requirements:
        raise _refuse("a contract addresses at least one requirement")
    targets = event.get("targets") or {}
    if not isinstance(targets, dict):
        raise _refuse("contract targets must be {'read': [...], 'write': [...]}")
    read = [_rel_path(p) for p in targets.get("read") or []]
    write = [_rel_path(p) for p in targets.get("write") or []]
    role = _text(event, "role")
    _epoch(state, event)
    if revision > 1:
        state.epoch += 1
    state.contracts[event["id"]] = {"requirements": requirements, "read": read, "write": write,
                                    "role": role, "revision": revision,
                                    "admitted_epoch": state.epoch}
    state.current_contract = event["id"]


def _artifact(state: AuditState, event: dict[str, Any]) -> None:
    ident = _new_id(state.artifacts, event)
    contract = event.get("contract", "")
    if contract and contract not in state.contracts:
        raise _refuse(f"artifact names unknown contract {contract!r}")
    state.artifacts[ident] = {"path": _rel_path(event.get("path")),
                              "fingerprint": _text(event, "fingerprint"), "contract": contract,
                              "epoch": state.epoch}


def _fact(state: AuditState, event: dict[str, Any]) -> None:
    ident = _new_id(state.facts, event)
    artifacts = _id_list(event, "artifacts", state.artifacts, "artifact")
    # A model's assertion is recorded as such; it is not an observed fact.
    state.facts[ident] = {"assertion": _text(event, "assertion"),
                          "basis": _choice(event, "basis", FACT_BASES), "artifacts": artifacts}


def _verifier_result(state: AuditState, event: dict[str, Any]) -> None:
    ident = _new_id(state.results, event)
    requirement = _text(event, "requirement")
    if requirement not in state.requirements:
        raise _refuse(f"verifier_result names unknown requirement {requirement!r}")
    contract = _text(event, "contract")
    if contract not in state.contracts:
        raise _refuse(f"verifier_result names unknown contract {contract!r}")
    if requirement not in state.contracts[contract]["requirements"]:
        raise _refuse(f"contract {contract} does not address requirement {requirement}")
    if event.get("contract_revision") != state.contracts[contract]["revision"]:
        raise _refuse(f"verifier_result checked contract {contract} revision "
                      f"{event.get('contract_revision')!r}, not its current one")
    predicate = _text(event, "predicate")
    if predicate not in state.requirements[requirement]["predicates"]:
        raise _refuse(f"predicate {predicate!r} is not one of requirement {requirement}'s")
    state.results[ident] = {
        "requirement": requirement, "contract": contract, "predicate": predicate,
        "verifier": _text(event, "verifier"), "strength": _choice(event, "strength", STRENGTHS),
        "outcome": _choice(event, "outcome", RESULTS),
        "artifacts": _id_list(event, "artifacts", state.artifacts, "artifact"),
        "epoch": _epoch(state, event)}


def _latest_result(state: AuditState, requirement: str, predicate: str) -> tuple[str, dict] | None:
    """The newest result for one predicate at the current epoch; an older pass never
    hides a newer failure."""
    found = None
    for ident, result in state.results.items():  # insertion order is append order
        if (result["requirement"], result["predicate"]) == (requirement, predicate) and \
                result["epoch"] == state.epoch:
            found = (ident, result)
    return found


def _reduction(state: AuditState, event: dict[str, Any]) -> None:
    requirement = _text(event, "requirement")
    if requirement not in state.requirements:
        raise _refuse(f"reduction names unknown requirement {requirement!r}")
    req = state.requirements[requirement]
    status = _choice(event, "status", STATUSES)
    cited = _id_list(event, "results", state.results, "verifier_result")
    if any(state.results[r]["requirement"] != requirement for r in cited):
        raise _refuse("a reduction cites only results for its own requirement")
    by = _choice(event, "by", ("core", "person"))
    epoch = _epoch(state, event)
    if status == "verified":
        if req["closure"] != "authoritative":
            raise _refuse(f"requirement {requirement} has {req['closure']} closure; only an "
                          "authoritative requirement can be verified")
        if by != "core":
            raise _refuse("verified is reached by Core reduction over verifier results, "
                          "not declared by a person or model")
        for predicate in req["predicates"]:
            latest = _latest_result(state, requirement, predicate)
            if latest is None:
                raise _refuse(f"predicate {predicate!r} has no result at the current epoch")
            ident, result = latest
            if result["outcome"] != "pass" or result["strength"] not in ("exact", "bounded"):
                raise _refuse(f"predicate {predicate!r}'s latest result is {result['outcome']} "
                              f"({result['strength']}); verified needs an exact or bounded pass")
            if ident not in cited:
                raise _refuse(f"verified must cite predicate {predicate!r}'s latest result {ident}")
    if status == "human_accepted":
        if by != "person":
            raise _refuse("human_accepted is recorded only from the person's action")
        artifact = event.get("artifact")
        if artifact not in state.artifacts:
            raise _refuse("human_accepted names the exact artifact revision accepted")
    req["status"], req["status_epoch"] = status, epoch
    state.reductions.append({"requirement": requirement, "status": status, "results": cited,
                             "by": by, "epoch": epoch})


def _external_edit(state: AuditState, event: dict[str, Any]) -> None:
    path = _rel_path(event.get("path"))
    source = _choice(event, "source", EDIT_SOURCES)
    fingerprint = event.get("fingerprint", "")
    if not isinstance(fingerprint, str):
        raise _refuse("external_edit fingerprint must be a string ('' for a deletion)")
    state.epoch += 1
    state.external_edits.append({"path": path, "fingerprint": fingerprint, "source": source,
                                 "epoch": state.epoch})


_RULES = {"requirement": _requirement, "contract": _contract, "artifact": _artifact,
          "fact": _fact, "verifier_result": _verifier_result, "reduction": _reduction,
          "external_edit": _external_edit}


def check_and_apply(state: AuditState, event: dict[str, Any]) -> None:
    """Validate one audit event against `state` and fold it in, or raise Refusal.

    The rules mutate a state only after every check for that event has passed,
    except epoch bumps that are part of the event's meaning.
    """
    if state.invalid:
        raise _refuse(f"this session's audit history is invalid ({state.invalid}); "
                      "no further audit event is accepted")
    kind = event.get("type")
    if kind not in _RULES:
        raise _refuse(f"{kind!r} is not an audit event; expected one of {sorted(AUDIT_EVENTS)}")
    _RULES[kind](state, event)


def replay(state: AuditState, event: dict[str, Any]) -> None:
    """Fold a stored event; a refused one marks the whole audit history invalid."""
    if state.invalid:
        return
    trial = _copy(state)
    try:
        check_and_apply(trial, event)
    except Refusal as exc:
        state.invalid = f"{event.get('type')} at epoch {state.epoch}: {exc}"
        return
    state.__dict__.update(trial.__dict__)


def _copy(state: AuditState) -> AuditState:
    import copy
    return copy.deepcopy(state)


# ------------------------------------------------------------- outcome mapping

INVOCATION = ("ok", "refused", "failed", "truncated", "cancelled", "uncertain", "not_run")
EXECUTION = ("completed", "partial", "refused", "failed", "cancelled", "interrupted",
             "needs_person", "uncertain", "not_run")
AUDIT = ("clean", "suspect", "violation", "failed", "stale", "not_run")
VISIBLE = ("integrity_violation", "uncertain_effect", "needs_person", "failed", "refused",
           "cancelled", "interrupted", "stale", "partial", "checked", "unchecked", "no_change")


def visible_outcome(invocation: str, execution: str, audit: str) -> str:
    """One visible outcome for every combination of the three layers.

    The order is the order of what a person most needs to know: a boundary
    violation first, then an effect whose outcome is unknown, then anything
    waiting on them. A provider or tool success never reads as a checked
    result on its own, and an unaudited completion stays `unchecked`.
    """
    for value, allowed, name in ((invocation, INVOCATION, "invocation"),
                                 (execution, EXECUTION, "execution"), (audit, AUDIT, "audit")):
        if value not in allowed:
            raise ValueError(f"{name} outcome {value!r} is not one of {list(allowed)}")
    if audit == "violation":
        return "integrity_violation"
    if "uncertain" in (invocation, execution):
        return "uncertain_effect"
    if execution == "needs_person" or audit == "suspect":
        return "needs_person"
    if invocation in ("failed", "truncated") or execution == "failed" or audit == "failed":
        return "failed"
    if "refused" in (invocation, execution):
        return "refused"
    if "cancelled" in (invocation, execution):
        return "cancelled"
    if execution == "interrupted":
        return "interrupted"
    if audit == "stale":
        return "stale"
    if execution == "partial":
        return "partial"
    if execution == "completed":
        return "checked" if audit == "clean" else "unchecked"
    return "no_change"


def session_outcome(state: AuditState) -> str:
    """The audited session's overall outcome, from its requirements' current statuses."""
    if state.invalid:
        return "invalid_history"
    if not state.requirements:
        return "no_requirements"
    statuses = [state.requirement_status(r) for r in state.requirements]
    for status in ("failed", "blocked", "stale"):
        if status in statuses:
            return status
    if all(s == "verified" for s in statuses):
        return "complete_verified"
    if all(s in ("verified", "human_accepted") for s in statuses):
        return "complete_with_human_acceptance"
    return "in_progress"


def unchecked_predicates(state: AuditState, contract_id: str) -> list[str]:
    """`requirement: predicate` pairs of a contract with no result at the current epoch."""
    contract = state.contracts[contract_id]
    return [f"{r}: {p}" for r in contract["requirements"]
            for p in state.requirements[r]["predicates"]
            if _latest_result(state, r, p) is None]


def unreduced_requirements(state: AuditState, contract_id: str) -> list[str]:
    """A contract's requirements with no reduction at the current epoch."""
    reduced = {r["requirement"] for r in state.reductions if r["epoch"] == state.epoch}
    return [r for r in state.contracts[contract_id]["requirements"] if r not in reduced]


def _predicate_outcome(state: AuditState, requirement: str, predicate: str) -> str:
    latest = _latest_result(state, requirement, predicate)
    return latest[1]["outcome"] if latest else "not_checked"


def summary(state: AuditState) -> dict[str, Any]:
    """What a person and a projection read: no event bodies, just current truth.

    Every predicate shows its own current outcome, so a passing quote check
    cannot hide a failing arithmetic check on the same requirement.
    """
    return {
        "epoch": state.epoch, "outcome": session_outcome(state), "invalid": state.invalid,
        "requirements": {r: {"status": state.requirement_status(r),
                             "closure": state.requirements[r]["closure"],
                             "revision": state.requirements[r]["revision"],
                             "predicates": {p: _predicate_outcome(state, r, p)
                                            for p in state.requirements[r]["predicates"]}}
                         for r in state.requirements},
        "contracts": {c: {"revision": v["revision"], "requirements": v["requirements"]}
                      for c, v in state.contracts.items()},
        "external_edits": state.external_edits[-20:],
    }
