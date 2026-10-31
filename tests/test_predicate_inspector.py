"""UX-01 backend: compact per-predicate inspection from folded audit state."""
from __future__ import annotations

import copy

from resource_librarian import audit_events, tools  # noqa: F401
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.session import SessionStore


def apply(state, event):
    audit_events.check_and_apply(state, event)


def requirement(state, *, rid="R1", closure="authoritative", bound=True):
    verifier = ({"verifier": "quote.located", "params": {"evidence": "E1"}}
                if bound else "quote.located")
    apply(state, {"type": "requirement", "id": rid, "revision": 1,
                  "text": "The quote is present.", "closure": closure,
                  "predicates": ["quote present"],
                  "verifiers": {"quote present": verifier}, "by": "person"})


def contract(state, rid="R1"):
    apply(state, {"type": "contract", "id": "C1", "revision": 1,
                  "requirements": [rid], "role": "lead", "epoch": state.epoch,
                  "targets": {"read": [], "write": []}, "operations": ["read"],
                  "verifiers": {f"{rid}: quote present": "quote.located"}})


def result(state, outcome="pass", *, rid="R1", evidence="E1"):
    apply(state, {"type": "verifier_result", "id": "V1", "requirement": rid,
                  "contract": "C1", "contract_revision": 1,
                  "predicate": "quote present", "verifier": "quote.located",
                  "strength": "exact", "outcome": outcome, "artifacts": [],
                  "epoch": state.epoch, "statement": f"checked: {outcome}",
                  "params": {"evidence": evidence}})


def test_inspector_covers_unchecked_pass_unbound_and_fail_without_mutation():
    unchecked = audit_events.AuditState()
    requirement(unchecked)
    before = copy.deepcopy(unchecked)
    [req] = audit_events.predicate_inspector(unchecked)["requirements"]
    [row] = req["predicates"]
    assert row["id"] == "R1.p1" and row["result"] is None
    assert row["outcome"] == "not_checked"
    assert row["subject"] == {"evidence": "E1"} and row["missing_subject_keys"] == []
    assert unchecked == before

    passed = audit_events.AuditState()
    requirement(passed)
    contract(passed)
    result(passed)
    [row] = audit_events.predicate_inspector(passed)["requirements"][0]["predicates"]
    assert row["result"] == {"id": "V1", "outcome": "pass", "strength": "exact",
                             "verifier": "quote.located", "contract": "C1", "revision": 1,
                             "contract_integrity": "not_required", "epoch": 0, "stale": False,
                             "artifacts": [], "statement": "checked: pass"}
    assert row["verifier"] == {"id": "quote.located", "named_by_person": True,
                               "kind": "deterministic", "max_strength": "exact",
                               "params": {"evidence": "E1"}}
    assert row["decision_path"] == "core_verification" and row["outcome"] == "pass"

    mismatched = audit_events.AuditState()
    requirement(mismatched)
    contract(mismatched)
    result(mismatched, evidence="E2")
    [row] = audit_events.predicate_inspector(mismatched)["requirements"][0]["predicates"]
    assert row["subject"] == {"evidence": "E1"}
    assert row["subject_mismatches"] == ["evidence"]

    unbound = audit_events.AuditState()
    requirement(unbound, bound=False)
    [row] = audit_events.predicate_inspector(unbound)["requirements"][0]["predicates"]
    assert row["subject"] == {} and row["missing_subject_keys"] == ["evidence"]

    failed = audit_events.AuditState()
    requirement(failed)
    contract(failed)
    result(failed, "fail")
    assert audit_events.predicate_inspector(failed)["requirements"][0]["predicates"][0] \
        ["result"]["outcome"] == "fail"


def test_historical_result_and_person_acceptance_show_staleness_and_artifact_details():
    state = audit_events.AuditState()
    requirement(state)
    contract(state)
    apply(state, {"type": "artifact", "id": "A1", "path": "draft.md",
                  "fingerprint": "abc", "contract": "C1"})
    result(state)
    apply(state, {"type": "reduction", "requirement": "R1", "status": "human_accepted",
                  "results": [], "by": "person", "epoch": 0, "contract": "C1",
                  "artifact": "A1"})
    apply(state, {"type": "external_edit", "path": "draft.md", "fingerprint": "changed",
                  "source": "watcher"})

    [req] = audit_events.predicate_inspector(state)["requirements"]
    [row] = req["predicates"]
    assert req["status"] == "stale" and row["stale"] is True and row["result"]["stale"] is True
    accepted = row["decision"]["person"]
    assert accepted["status"] == "human_accepted" and accepted["stale"] is True
    assert accepted["artifact"] == {"id": "A1", "path": "draft.md",
                                    "contract": "C1", "epoch": 0}
    # The historical artifact explains the old acceptance, but is not exposed
    # as a fresh accept/reject action after the epoch changed.
    assert req["artifacts"] == []


def test_invalid_and_legacy_histories_are_visible_but_not_actionable():
    invalid = audit_events.AuditState(invalid="bad event")
    legacy = audit_events.AuditState(legacy="old reduction")
    assert audit_events.predicate_inspector(invalid) == {
        "actionable": False, "invalid": "bad event", "scope": audit_events.SCOPE,
        "requirements": []}
    assert audit_events.predicate_inspector(legacy) == {
        "actionable": False, "invalid": "", "legacy": "old reduction",
        "scope": audit_events.SCOPE, "requirements": []}


def test_audited_session_status_exposes_a_deterministic_inspector(vault):
    ctx = Context(tier="contribute", vault=vault)
    REGISTRY.call("open_session", {"purpose": "audited", "question": "q"}, ctx)
    person = Context(tier="curate", vault=vault, session=ctx.session)
    REGISTRY.call("set_requirement", {
        "requirement_id": "R1", "text": "The quote is present.",
        "predicates": ["quote present"],
        "verifiers": {"quote present": {"verifier": "quote.located",
                                           "params": {"evidence": "E1"}}}}, person)

    first = REGISTRY.call("session_status", {}, ctx)
    second = REGISTRY.call("session_status", {}, ctx)
    assert first["predicate_inspector"] == second["predicate_inspector"]
    assert first["predicate_inspector"]["actionable"] is True
    assert first["predicate_inspector"]["requirements"][0]["predicates"][0]["id"] == "R1.p1"
    assert SessionStore(vault).load(ctx.session).to_dict(vault)["predicate_inspector"] == \
        first["predicate_inspector"]
