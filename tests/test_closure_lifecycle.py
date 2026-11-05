"""REMED-03, closure lifecycle qualification (Codex review R2, C1).

A closure or acceptance holds only on the state it was made on, whichever
route changed that state: an edit the watcher sees, a Core write it does not,
an edit made while the app was closed, or a later contract. A predicate no
check the person named establishes stays partial. A history written before
contract-scoped reductions reads as legacy, never as corrupt and never as
current evidence."""
from __future__ import annotations

import json

from test_research_round import (QUOTE, Lead, evidence, lead,  # noqa: F401  (fixtures)
                                 requirements, round_to_reduce, staging_folder)

from resource_librarian import audit_events
from resource_librarian.coordination import atomic_write_text
from resource_librarian.evidence import EvidenceStore
from resource_librarian.rules import Refusal
from resource_librarian.session import (SessionStore, reconcile, reconcile_open,
                                        record_external_edit)


def to_audit(lead, evidence):
    """Round 1 with both of R1's predicates checked, stopped before reduction."""
    requirements(lead, evidence)
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1", "R2"], "step": "s"}})
    lead.ok("advance")
    lead.ok("admit_contract", contract_id="C1", requirements=["R1", "R2"],
            write=[staging_folder(lead.ctx, lead.ctx.session)], operations=["read", "stage"],
            verifiers={"R1: quote present": "quote.located",
                       "R1: staged draft unchanged": "target.diff_clean"})
    lead.ok("advance")
    staged = lead.ok("stage_artifact", name="synthesis", text="# Synthesis\n\nbounded.\n")
    lead.ok("advance")
    lead.ok("verify_grain", requirement="R1", predicate="quote present",
            params={"evidence": evidence, "quote": QUOTE})
    lead.ok("verify_grain", requirement="R1", predicate="staged draft unchanged")
    lead.ok("audit_targets")
    lead.ok("advance")
    return staged


def edits(lead, source="core_check"):
    return [e["path"] for e in lead.audit().external_edits if e["source"] == source]


def evidence_file(vault, ident):
    return next(vault.evidence.glob(f"*/{ident}.json"))


# --- new histories: a result records what it read ---------------------------------------

def test_a_result_records_the_files_it_read_by_fingerprint(lead, evidence, vault):
    to_audit(lead, evidence)
    quote = next(r for r in lead.audit().results.values() if r["verifier"] == "quote.located")
    path = evidence_file(vault, evidence).relative_to(vault.root).as_posix()
    assert list(quote["inputs"]) == [path]


def test_an_unchanged_round_reconciles_to_nothing_and_verifies(lead, evidence, vault):
    to_audit(lead, evidence)
    assert reconcile(vault, lead.ctx.session) == []
    assert lead.ok("reduce_round")["reduced"]["R1"] == {"status": "verified"}
    assert lead.audit().external_edits == []


# --- every mutation route stales ----------------------------------------------------------

def test_a_core_write_the_watcher_never_sees_stops_verification(lead, evidence, vault):
    staged = to_audit(lead, evidence)
    # Another session's Core write: the watcher suppresses the Core's own writes.
    atomic_write_text(vault.root / staged["path"], "# Synthesis\n\nrewritten elsewhere.\n")
    reduced = lead.ok("reduce_round")["reduced"]["R1"]
    assert reduced["status"] != "verified"
    assert edits(lead) == [staged["path"]]
    assert lead.audit().requirement_status("R1") != "verified"


def test_a_changed_evidence_record_stales_the_quote_check(lead, evidence, vault):
    to_audit(lead, evidence)
    record = evidence_file(vault, evidence)
    data = json.loads(record.read_text(encoding="utf-8"))
    data["payload"] = {**data.get("payload", {}), "text": "a different text now"}
    record.write_text(json.dumps(data), encoding="utf-8")
    assert lead.ok("reduce_round")["reduced"]["R1"]["status"] != "verified"
    assert edits(lead) == [record.relative_to(vault.root).as_posix()]


def test_an_edit_made_while_closed_stales_a_verified_requirement_on_resume(lead, evidence,
                                                                          vault):
    staged = to_audit(lead, evidence)
    lead.ok("reduce_round")
    assert lead.audit().requirement_status("R1") == "verified"
    lead.ok("park_session", note="closing the app")
    (vault.root / staged["path"]).write_text("edited with the app closed", encoding="utf-8")
    resumed = Lead(vault)                                     # a new process
    resumed.ok("resume_session", session_id=lead.ctx.session)
    audit = SessionStore(vault).load(lead.ctx.session).audit
    assert audit.requirement_status("R1") == "stale"
    assert audit_events.session_outcome(audit) == "stale"


def test_startup_records_what_changed_while_the_app_was_not_running(lead, evidence, vault):
    staged = to_audit(lead, evidence)
    lead.ok("reduce_round")
    (vault.root / staged["path"]).unlink()                    # deleted while closed
    found = reconcile_open(vault)
    assert found == {lead.ctx.session: [staged["path"]]}
    edit = lead.audit().external_edits[-1]
    assert edit["fingerprint"] == audit_events.MISSING and edit["source"] == "core_check"
    assert lead.audit().requirement_status("R1") == "stale"
    assert reconcile_open(vault) == {}                        # recorded once, not again


def test_a_watcher_edit_is_not_recorded_twice(lead, evidence, vault):
    staged = to_audit(lead, evidence)
    (vault.root / staged["path"]).write_text("edited in Obsidian", encoding="utf-8")
    assert record_external_edit(vault, staged["path"]) == [lead.ctx.session]
    assert reconcile(vault, lead.ctx.session) == []
    assert edits(lead, "watcher") == [staged["path"]] and edits(lead) == []


def test_a_human_acceptance_goes_stale_when_its_artifact_changes(lead, evidence, vault):
    staged = to_audit(lead, evidence)
    lead.ok("reduce_round")
    lead.person("accept_artifact", requirement="R2", artifact=staged["artifact"])
    assert lead.audit().requirement_status("R2") == "human_accepted"
    atomic_write_text(vault.root / staged["path"], "changed after acceptance")
    Lead(vault).ok("resume_session", session_id=lead.ctx.session)
    assert lead.audit().requirement_status("R2") == "stale"


def test_an_acceptance_is_refused_on_a_moved_state(lead, evidence, vault):
    staged = to_audit(lead, evidence)
    atomic_write_text(vault.root / staged["path"], "changed before the person accepted")
    person = Lead(vault, session=lead.ctx.session)
    person.ctx.tier = "curate"
    out = person("accept_artifact", requirement="R2", artifact=staged["artifact"])
    assert "changed since it was staged" in json.dumps(out)
    assert edits(lead) == [staged["path"]]                    # and the change is on record


# --- a predicate no check the person named establishes stays partial -------------------

def unnamed_round(lead):
    lead.person("set_requirement", requirement_id="R1", text="The figure matches the source.",
                predicates=["the figure matches the source"])
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "s"}})
    lead.ok("advance")
    lead.ok("admit_contract", contract_id="C1", requirements=["R1"],
            write=[staging_folder(lead.ctx, lead.ctx.session)], operations=["read", "stage"],
            verifiers={"R1: the figure matches the source": "target.diff_clean"})
    lead.ok("advance")
    lead.ok("stage_artifact", name="figure", text="40%")
    lead.ok("advance")
    lead.ok("verify_grain", requirement="R1", predicate="the figure matches the source")
    lead.ok("audit_targets")
    lead.ok("advance")


def test_a_model_chosen_check_cannot_verify_a_semantic_predicate(lead):
    unnamed_round(lead)
    reduced = lead.ok("reduce_round")["reduced"]["R1"]
    assert reduced["status"] == "partial"
    assert "no verifier the person named" in reduced["reason"]


def test_the_rules_refuse_verified_without_the_persons_verifier(lead):
    unnamed_round(lead)
    audit = lead.audit()
    result = next(iter(audit.results))
    try:
        SessionStore(lead.ctx.vault).append_audit(lead.ctx.session, {
            "type": "reduction", "requirement": "R1", "status": "verified",
            "results": [result], "by": "core", "epoch": audit.epoch, "contract": "C1"})
    except Refusal as exc:
        assert "no verifier the person named" in str(exc)
    else:
        raise AssertionError("verified was recorded without the person's verifier")


# --- legacy, invalid and interrupted histories -------------------------------------------

def rewrite(vault, session_id, change):
    """Rewrite one session log's events, as an older build or a fault would have."""
    path = SessionStore(vault).path(session_id)
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    path.write_text("".join(json.dumps(change(e)) + "\n" for e in lines), encoding="utf-8")
    return path


def without_contract(event):
    if event.get("type") == "reduction" and event.get("status") == "verified":
        event = {k: v for k, v in event.items() if k != "contract"}
    return event


def test_a_pre_cutover_history_reads_as_legacy_not_as_corrupt(lead, evidence, vault):
    to_audit(lead, evidence)
    lead.ok("reduce_round")
    path = rewrite(vault, lead.ctx.session, without_contract)
    kept = path.read_bytes()
    session = SessionStore(vault).load(lead.ctx.session)
    audit = session.audit
    assert audit.legacy and not audit.invalid
    assert "a9be71b" in audit.legacy and "not current evidence" in audit.legacy
    assert audit_events.session_outcome(audit) == "legacy_history"
    assert audit.requirement_status("R1") != "verified"     # never trusted as verified
    assert audit_events.summary(audit)["legacy"] == audit.legacy
    assert "legacy" in session._audited_missing()[0]
    assert not session.completion()["complete"]
    assert path.read_bytes() == kept                           # preserved as written


def test_a_legacy_history_accepts_no_further_audit_event(lead, evidence, vault):
    to_audit(lead, evidence)
    lead.ok("reduce_round")
    rewrite(vault, lead.ctx.session, without_contract)
    out = lead("set_requirement", requirement_id="R3", text="more", closure="partial")
    assert "legacy" in json.dumps(out)
    assert reconcile(vault, lead.ctx.session) == []            # nothing appended to it


def test_an_invalid_history_is_still_invalid_not_legacy(lead, evidence, vault):
    to_audit(lead, evidence)
    lead.ok("reduce_round")

    def wrong_contract(event):
        if event.get("type") == "reduction" and event.get("status") == "verified":
            event = {**event, "contract": "C9"}
        return event

    rewrite(vault, lead.ctx.session, wrong_contract)
    audit = SessionStore(vault).load(lead.ctx.session).audit
    assert audit.invalid and not audit.legacy
    assert audit_events.session_outcome(audit) == "invalid_history"


def test_an_interrupted_append_is_skipped_and_the_round_continues(lead, evidence, vault):
    to_audit(lead, evidence)
    before = SessionStore(vault).load(lead.ctx.session).state_hash()
    path = SessionStore(vault).path(lead.ctx.session)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"type": "reduction", "requirement": "R1", "sta')   # torn mid-write
    resumed = Lead(vault)
    resumed.ok("resume_session", session_id=lead.ctx.session)
    after = SessionStore(vault).load(lead.ctx.session)
    assert not after.audit.halted and after.state_hash() == before
    assert after.audit.external_edits == []


def test_a_round_interrupted_before_reduction_resumes_and_verifies(lead, evidence, vault):
    to_audit(lead, evidence)
    resumed = Lead(vault)                                      # crash, then a new process
    resumed.ok("resume_session", session_id=lead.ctx.session)
    assert resumed.ok("reduce_round")["reduced"]["R1"] == {"status": "verified"}


def test_a_stale_result_is_never_cited_after_a_change(lead, evidence, vault):
    staged = to_audit(lead, evidence)
    old = set(lead.audit().results)
    atomic_write_text(vault.root / staged["path"], "moved")
    lead.ok("reduce_round")
    for reduction in lead.audit().reductions:
        assert not set(reduction["results"]) & old


def test_a_legacy_history_is_named_read_only_in_listings_and_the_inspector(lead, evidence, vault):
    """MF-009: the projection the UI reads, from a real session log. The
    inspector always carries `invalid` ('' when sound), so the UI must read
    `legacy` past an empty `invalid`; the listing names the history read-only."""
    to_audit(lead, evidence)
    lead.ok("reduce_round")
    rewrite(vault, lead.ctx.session, without_contract)
    store = SessionStore(vault)
    view = store.load(lead.ctx.session).to_dict(vault)["predicate_inspector"]
    assert view["invalid"] == "" and view["legacy"] and view["actionable"] is False
    row = next(r for r in store.list() if r["id"] == lead.ctx.session)
    assert row["audit_history"] == "legacy"
    assert all("audit_history" not in r for r in store.list() if r["id"] != lead.ctx.session)
