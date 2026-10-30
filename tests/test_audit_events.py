"""HARNESS-02: the audited-session event vocabulary, its transitions and outcomes."""
from __future__ import annotations

import itertools
import json

import pytest

from resource_librarian import audit_events
from resource_librarian.coordination import DocumentLeases
from resource_librarian.rules import Refusal
from resource_librarian.session import (SessionStore, _append_lock, _write_event_locked,
                                        record_external_edit, sessions_watching)


@pytest.fixture
def store(vault):
    return SessionStore(vault)


@pytest.fixture
def sid(store):
    return store.new("explore", question="does the source support the claim?").id


def lines(store, sid):
    return [json.loads(l) for l in store.path(sid).read_text(encoding="utf-8").splitlines() if l]


VERIFIER_FOR = {"quote present": "quote.located", "arithmetic reproduces": "arithmetic.reproduces"}
# The subject the person binds to each predicate (Codex review, 2026-10-30).
SUBJECT_FOR = {"quote present": {"evidence": "E1"}, "arithmetic reproduces": {"note": "notes/a.md"}}


def requirement(rid="R1", *, revision=1, closure="authoritative", predicates=("quote present",),
                by="person"):
    return {"type": "requirement", "id": rid, "revision": revision, "closure": closure,
            "predicates": list(predicates), "text": "Quote the source exactly.", "by": by,
            "verifiers": {p: {"verifier": VERIFIER_FOR[p], "params": SUBJECT_FOR[p]}
                          for p in predicates if p in VERIFIER_FOR}}


def contract(cid="C1", *, revision=1, requirements=("R1",), epoch=0, write=("notes/a.md",),
             predicates=("quote present",)):
    return {"type": "contract", "id": cid, "revision": revision,
            "requirements": list(requirements), "role": "lead", "epoch": epoch,
            "targets": {"read": ["sources/s.md"], "write": list(write)},
            # HARNESS-05: an authoritative requirement needs its verifier plan up front
            "verifiers": {f"{r}: {p}": VERIFIER_FOR[p] for r in requirements for p in predicates}}


def result(rid_="V1", *, outcome="pass", strength="exact", epoch=0, predicate="quote present",
           contract_revision=1, artifacts=("A1",)):
    return {"type": "verifier_result", "id": rid_, "requirement": "R1", "contract": "C1",
            "contract_revision": contract_revision, "predicate": predicate,
            "verifier": f"{VERIFIER_FOR.get(predicate, 'quote.located')}@1", "strength": strength,
            "outcome": outcome, "artifacts": list(artifacts), "epoch": epoch,
            "params": dict(SUBJECT_FOR.get(predicate, {}))}


def artifact(aid="A1", path="notes/a.md", fp="f" * 20):
    return {"type": "artifact", "id": aid, "path": path, "fingerprint": fp, "contract": "C1"}


def verify(results=("V1",), epoch=0, status="verified", by="core", contract="C1"):
    return {"type": "reduction", "requirement": "R1", "status": status, "results": list(results),
            "by": by, "epoch": epoch, "contract": contract}


def snapshot(sid_="S1", *, contract_revision=1, epoch=0):
    # HARNESS-07: a contract that writes is snapshotted before it runs...
    return {"type": "snapshot", "id": sid_, "contract": "C1",
            "contract_revision": contract_revision, "epoch": epoch,
            "targets": {"notes/a.md": "f" * 20, "sources/s.md": "e" * 20}}


def clean(tid="T1", *, snapshot_="S1", contract_revision=1, epoch=0):
    # ...and audited clean before its results can verify anything.
    return {"type": "target_audit", "id": tid, "contract": "C1", "snapshot": snapshot_,
            "contract_revision": contract_revision, "epoch": epoch, "integrity": "clean",
            "changed": ["notes/a.md"], "findings": []}


def seed(store, sid):
    for event in (requirement(), contract(), snapshot(), artifact(), result(), clean()):
        store.append_audit(sid, event)


# --- valid histories ----------------------------------------------------------------

def test_a_valid_history_verifies_and_replays_to_the_same_state(store, sid):
    seed(store, sid)
    store.append_audit(sid, verify())
    first = audit_events.summary(store.load(sid).audit)
    assert first["requirements"]["R1"]["status"] == "verified"
    assert first["outcome"] == "complete_verified"
    assert audit_events.summary(store.load(sid).audit) == first  # deterministic replay
    assert store.load(sid).to_dict(store.vault)["audit"] == first


def test_a_session_without_audit_events_is_unchanged(store, sid):
    assert "audit" not in store.load(sid).to_dict(store.vault)


# --- invalid transitions are refused and nothing is written -----------------------------

def refused(store, sid, event, match):
    before = len(lines(store, sid))
    with pytest.raises(Refusal, match=match):
        store.append_audit(sid, event)
    assert len(lines(store, sid)) == before


@pytest.mark.parametrize("event,match", [
    (requirement(by="model"), "only by the person"),
    (requirement(predicates=()), "at least one acceptance predicate"),
    (requirement(revision=2), "revision must be 1"),
    (contract(requirements=("R9",)), "unknown requirement"),
    ({"type": "fact", "id": "F1", "assertion": "x", "basis": "guess"}, "basis must be one of"),
    ({"type": "artifact", "id": "A9", "path": "../outside.md", "fingerprint": "x"},
     "vault-relative"),
    ({"type": "message", "role": "user", "text": "hi"}, "not an audit event"),
])
def test_malformed_events_are_refused_before_any_write(store, sid, event, match):
    refused(store, sid, event, match)


@pytest.mark.parametrize("event,match", [
    (result(predicate="claim is true"), "not one of requirement R1's"),
    (result(epoch=5), "was made at epoch 5"),
    (result(contract_revision=2), "not its current one"),
    (verify(status="verified", by="person"), "reached by Core reduction"),
    (verify(results=()), "must cite"),
    ({**verify(status="human_accepted", by="person"), "artifact": "A9"},
     "exact artifact revision"),
])
def test_invalid_transitions_are_refused(store, sid, event, match):
    for e in (requirement(), contract(), artifact()):
        store.append_audit(sid, e)
    if event["type"] == "reduction":
        store.append_audit(sid, result())
    refused(store, sid, event, match)


def test_only_an_exact_or_bounded_pass_verifies(store, sid):
    for e in (requirement(), contract(), artifact(), result(strength="advisory")):
        store.append_audit(sid, e)
    refused(store, sid, verify(), "verified needs an exact or bounded pass")


def test_an_older_pass_cannot_hide_a_newer_failure(store, sid):
    seed(store, sid)
    store.append_audit(sid, result("V2", outcome="fail"))
    refused(store, sid, verify(results=("V1", "V2")), "latest result is fail")
    summary = audit_events.summary(store.load(sid).audit)
    assert summary["requirements"]["R1"]["predicates"] == {"quote present": "fail"}


def test_every_predicate_needs_its_own_pass(store, sid):
    both = ("quote present", "arithmetic reproduces")
    for e in (requirement(predicates=both), contract(predicates=both), artifact(), result()):
        store.append_audit(sid, e)
    refused(store, sid, verify(), "'arithmetic reproduces' has no result")


def test_human_judgment_closure_is_never_verified(store, sid):
    for e in (requirement(closure="human_judgment"), contract(), artifact(), result()):
        store.append_audit(sid, e)
    refused(store, sid, verify(), "only an authoritative requirement can be verified")
    store.append_audit(sid, {**verify(status="human_accepted", by="person"), "artifact": "A1"})
    audit = store.load(sid).audit
    assert audit.requirement_status("R1") == "human_accepted"
    assert audit_events.session_outcome(audit) == "complete_with_human_acceptance"


# --- freshness: requirement and contract revisions and outside edits ------------------

@pytest.mark.parametrize("change", [
    contract(revision=2, epoch=0),
    {"type": "external_edit", "path": "notes/a.md", "fingerprint": "g" * 20,
     "source": "watcher"},
])
def test_a_contract_revision_or_outside_edit_makes_closure_stale(store, sid, change):
    seed(store, sid)
    store.append_audit(sid, verify())
    store.append_audit(sid, change)
    audit = store.load(sid).audit
    assert audit.epoch == 1
    assert audit.requirement_status("R1") == "stale"
    assert audit_events.session_outcome(audit) == "stale"
    # The old pass no longer counts: re-verification needs a result at the new epoch.
    refused(store, sid, verify(epoch=1), "no result at the current epoch")


def test_a_requirement_revision_reopens_it_and_stales_the_others(store, sid):
    store.append_audit(sid, requirement("R2"))
    seed(store, sid)
    store.append_audit(sid, contract("C2", requirements=("R2",)))
    store.append_audit(sid, {**result("V2"), "requirement": "R2", "contract": "C2"})
    store.append_audit(sid, {**snapshot("S2"), "contract": "C2"})
    store.append_audit(sid, {**clean("T2", snapshot_="S2"), "contract": "C2"})
    store.append_audit(sid, verify())
    store.append_audit(sid, {**verify(results=("V2",), contract="C2"), "requirement": "R2"})

    store.append_audit(sid, requirement(revision=2))  # the person changes R1

    audit = store.load(sid).audit
    assert audit.epoch == 1
    assert audit.requirement_status("R1") == "open"   # a revised requirement starts again
    assert audit.requirement_status("R2") == "stale"  # whole-session invalidation until HARNESS-09
    assert audit_events.session_outcome(audit) == "stale"


def test_a_model_cannot_revise_a_requirement(store, sid):
    seed(store, sid)
    refused(store, sid, requirement(revision=2, by="model"), "only by the person")


# --- an invalid stored history is reported, never trusted --------------------------

def test_an_invalid_stored_history_is_marked_and_refuses_more(store, sid):
    seed(store, sid)
    path = store.path(sid)
    with _append_lock(path):  # bypass the check, as a hand edit or a bug would
        _write_event_locked(path, verify(results=(), status="verified"))
    audit = store.load(sid).audit
    assert audit.invalid and "must cite" in audit.invalid
    assert audit_events.session_outcome(audit) == "invalid_history"
    assert audit.requirement_status("R1") == "open"  # the bad closure was not applied
    refused(store, sid, result("V2"), "audit history is invalid")


def test_a_closed_session_accepts_no_audit_event(store, sid):
    store.append(sid, {"type": "closed", "summary": "done"})
    with pytest.raises(Refusal, match="is closed"):
        store.append_audit(sid, requirement())


# --- outcome mapping: every combination maps to exactly one visible outcome ----------

def test_every_layer_combination_maps_to_one_visible_outcome():
    for inv, exe, aud in itertools.product(audit_events.INVOCATION, audit_events.EXECUTION,
                                           audit_events.AUDIT):
        assert audit_events.visible_outcome(inv, exe, aud) in audit_events.VISIBLE


@pytest.mark.parametrize("layers,expected", [
    (("ok", "completed", "violation"), "integrity_violation"),
    (("uncertain", "not_run", "not_run"), "uncertain_effect"),
    (("ok", "completed", "suspect"), "needs_person"),
    (("truncated", "not_run", "not_run"), "failed"),
    (("ok", "refused", "not_run"), "refused"),
    (("cancelled", "cancelled", "not_run"), "cancelled"),
    (("ok", "interrupted", "not_run"), "interrupted"),
    (("ok", "completed", "stale"), "stale"),
    (("ok", "partial", "clean"), "partial"),
    (("ok", "completed", "clean"), "checked"),
    (("ok", "completed", "not_run"), "unchecked"),  # a tool success is not a checked result
    (("not_run", "not_run", "not_run"), "no_change"),
])
def test_the_most_important_layer_wins(layers, expected):
    assert audit_events.visible_outcome(*layers) == expected


def test_unknown_layer_values_are_refused():
    with pytest.raises(ValueError):
        audit_events.visible_outcome("ok", "done", "clean")


# --- external edits appear in the session's log (HARNESS-02 done-when) -------------

def watched(store, sid):
    for e in (requirement(), contract()):
        store.append_audit(sid, e)


def test_an_outside_edit_to_a_target_is_appended_to_the_session(vault, store, sid):
    watched(store, sid)
    note = vault.root / "notes" / "a.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("edited in Obsidian\n", encoding="utf-8")
    leases = DocumentLeases(vault)
    leases.on_external_change(lambda rel: record_external_edit(vault, rel))

    leases.observe_change("notes/a.md")

    edits = [e for e in lines(store, sid) if e["type"] == "external_edit"]
    assert len(edits) == 1 and edits[0]["path"] == "notes/a.md"
    assert edits[0]["source"] == "watcher" and edits[0]["fingerprint"]
    assert store.load(sid).audit.epoch == 1


def test_read_targets_and_deletions_are_watched_too(vault, store, sid):
    watched(store, sid)
    assert record_external_edit(vault, "sources/s.md") == [sid]  # a read target; absent file
    edit = [e for e in lines(store, sid) if e["type"] == "external_edit"][0]
    assert edit["fingerprint"]  # the missing-file marker, not an empty string


def test_the_cores_own_write_unrelated_paths_and_closed_sessions_are_not_recorded(
        vault, store, sid):
    watched(store, sid)
    other = store.new("explore").id
    for e in (requirement(), contract()):
        store.append_audit(other, e)
    store.append(other, {"type": "closed", "summary": "done"})
    note = vault.root / "notes" / "a.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("written by the Core\n", encoding="utf-8")
    leases = DocumentLeases(vault)
    calls = []
    leases.on_external_change(calls.append)

    leases.note_core_write(["notes/a.md"])
    leases.observe_change("notes/a.md")
    assert calls == []  # the Core's own write is not an outside edit

    assert sessions_watching(vault, "notes/unrelated.md") == []
    assert sessions_watching(vault, "notes/a.md") == [sid]  # the closed session is excluded


def test_the_apps_document_change_route_records_the_edit(vault, store, sid, tmp_path,
                                                          monkeypatch):
    """End to end: an editor adapter reports a change through the App, as Obsidian does."""
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    from resource_librarian.providers import Scripted
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    watched(store, sid)
    note = vault.root / "notes" / "a.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("edited outside\n", encoding="utf-8")
    app = App(vault, token="t", keys=KeyStore(use_keyring=False),
              provider_for=lambda choice: Scripted(lambda s, m, t: None), broker_timeout=5)
    try:
        app.document_changed("notes/a.md")
    finally:
        if app.mcp is not None:
            app.mcp.stop()
    assert [e["path"] for e in lines(store, sid) if e["type"] == "external_edit"] == ["notes/a.md"]


def test_a_failing_listener_never_breaks_the_watcher(vault):
    leases = DocumentLeases(vault)

    def broken(rel):
        raise RuntimeError("listener failed")

    leases.on_external_change(broken)
    leases.observe_change("notes/x.md")  # does not raise
    assert leases.listener_errors()[0]["path"] == "notes/x.md"
