"""HARNESS-06: research rounds with closure per grain, staged synthesis, the person's
checkpoint controls, the no-suitable-tool outcome and the Tier A share measure."""
from __future__ import annotations

import json

import pytest

from resource_librarian import dik, research_grains
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.claim_run import RunnableStore
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.tools.audited import staging_folder

QUOTE = "rounds are bounded by an admitted contract"


class Lead:
    def __init__(self, vault, session=""):
        self.ctx = Context(tier="contribute", vault=vault, session=session)

    def __call__(self, tool, **args):
        return REGISTRY.call(tool, args, self.ctx)

    def ok(self, tool, **args):
        result = self(tool, **args)
        assert "error" not in result and "refused" not in result, result
        return result

    def person(self, tool, **args):
        person = Context(tier="curate", vault=self.ctx.vault, session=self.ctx.session)
        result = REGISTRY.call(tool, args, person)
        assert "error" not in result and "refused" not in result, result
        return result

    def audit(self):
        return SessionStore(self.ctx.vault).load(self.ctx.session).audit

    def summary(self):
        from resource_librarian import audit_events
        return audit_events.summary(self.audit())


@pytest.fixture
def evidence(vault):
    return EvidenceStore(vault).put("page", "https://example.org/harness", {
        "title": "Harness", "text": f"In this design {QUOTE}, and each is audited."}).id


@pytest.fixture
def lead(vault):
    lead = Lead(vault)
    lead.ok("open_session", purpose="audited", question="how are rounds bounded?")
    return lead


def requirements(lead):
    lead.person("set_requirement", requirement_id="R1", text="The key quote is located.",
                predicates=["quote present", "staged draft unchanged"])
    lead.person("set_requirement", requirement_id="R2", text="A synthesis the person accepts.",
                closure="human_judgment")


def round_to_reduce(lead, evidence):
    """One research round through the registry, up to and including reduction."""
    requirements(lead)
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1", "R2"],
                                               "step": "locate the quote; draft a synthesis"}})
    assert lead.ok("advance")["moved"] == "preflight"
    lead.ok("admit_contract", contract_id="C1", requirements=["R1", "R2"],
            write=[staging_folder(lead.ctx, lead.ctx.session)], operations=["read", "stage"],
            verifiers={"R1: quote present": "quote.located",
                       "R1: staged draft unchanged": "target.diff_clean"})
    assert lead.ok("advance")["moved"] == "execute"
    staged = lead.ok("stage_artifact", name="synthesis",
                     text="# Synthesis\n\nRounds are bounded by their contract.\n")
    assert lead.ok("advance")["moved"] == "audit"
    quote = lead.ok("verify_grain", requirement="R1", predicate="quote present",
                    params={"evidence": evidence, "quote": QUOTE})
    clean = lead.ok("verify_grain", requirement="R1", predicate="staged draft unchanged")
    assert lead.ok("advance")["moved"] == "reduce"
    reduced = lead.ok("reduce_round")
    return staged, quote, clean, reduced


# --- the round, end to end ---------------------------------------------------------

def test_a_round_closes_verified_grains_with_exact_statements(lead, evidence):
    staged, quote, clean, reduced = round_to_reduce(lead, evidence)
    assert quote["outcome"] == "pass" and quote["strength"] == "exact"
    assert quote["statement"] == (f"the quote is present in evidence `{evidence}` at offset 15 "
                                  "of field `text`")
    assert clean["statement"].startswith("the 1 artifact(s) of contract C1 are unchanged")
    assert reduced["reduced"]["R1"] == {"status": "verified"}
    summary = lead.summary()
    assert summary["requirements"]["R1"]["established"] == [quote["statement"],
                                                            clean["statement"]]


def test_synthesis_is_staged_for_the_person_and_closes_nothing(lead, evidence, vault):
    staged, _, _, reduced = round_to_reduce(lead, evidence)
    assert staged["path"].startswith(".librarian/staging/audited/")
    assert (vault.root / staged["path"]).is_file()
    assert reduced["reduced"]["R2"]["status"] == "open"
    assert "awaiting the person" in reduced["reduced"]["R2"]["reason"]
    assert reduced["outcome"] == "in_progress"


def test_the_round_never_declares_semantic_completion(lead, evidence):
    _, _, _, reduced = round_to_reduce(lead, evidence)
    lead.person("accept_artifact", requirement="R2", artifact="A1")
    summary = lead.summary()
    assert summary["outcome"] == "complete_with_human_acceptance"
    assert "nothing here asserts that a claim is true" in summary["scope"]
    text = json.dumps(summary).lower()
    for phrase in ("claim is true", "research is complete.", "answer is correct"):
        assert phrase not in text.replace("asserts that a claim is true", "")


def test_a_round_resumes_from_its_log(lead, evidence, vault):
    requirements(lead)
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1", "R2"], "step": "s"}})
    lead.ok("advance")
    lead.ok("admit_contract", contract_id="C1", requirements=["R1", "R2"],
            write=[staging_folder(lead.ctx, lead.ctx.session)], operations=["read", "stage"],
            verifiers={"R1: quote present": "quote.located",
                       "R1: staged draft unchanged": "target.diff_clean"})
    lead.ok("advance")
    lead.ok("stage_artifact", name="synthesis", text="draft")
    lead.ok("advance")
    lead.ok("verify_grain", requirement="R1", predicate="quote present",
            params={"evidence": evidence, "quote": QUOTE})
    # A new process: nothing carried over but the session id.
    resumed = Lead(vault)
    resumed.ok("resume_session", session_id=lead.ctx.session)
    assert SessionStore(vault).load(resumed.ctx.session).phase == "audit"
    still = resumed.ok("advance")
    assert still["moved"] is False and "staged draft unchanged" in still["missing"][0]
    resumed.ok("verify_grain", requirement="R1", predicate="staged draft unchanged")
    assert resumed.ok("advance")["moved"] == "reduce"
    assert resumed.ok("reduce_round")["reduced"]["R1"]["status"] == "verified"


def test_a_staged_draft_edited_after_staging_fails_the_integrity_grain(lead, evidence, vault):
    requirements(lead)
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "s"}})
    lead.ok("advance")
    lead.ok("admit_contract", contract_id="C1", requirements=["R1"],
            write=[staging_folder(lead.ctx, lead.ctx.session)], operations=["read", "stage"],
            verifiers={"R1: quote present": "quote.located",
                       "R1: staged draft unchanged": "target.diff_clean"})
    lead.ok("advance")
    staged = lead.ok("stage_artifact", name="synthesis", text="draft")
    (vault.root / staged["path"]).write_text("edited behind the audit", encoding="utf-8")
    lead.ok("advance")
    clean = lead.ok("verify_grain", requirement="R1", predicate="staged draft unchanged")
    assert clean["outcome"] == "fail" and "changed after it was recorded" in clean["statement"]


def test_staging_outside_the_contracts_targets_is_refused(lead, evidence):
    requirements(lead)
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "s"}})
    lead.ok("advance")
    lead.ok("admit_contract", contract_id="C1", requirements=["R1"],
            write=[".librarian/staging/elsewhere/"], operations=["read", "stage"],
            verifiers={"R1: quote present": "quote.located",
                       "R1: staged draft unchanged": "target.diff_clean"})
    lead.ok("advance")
    out = lead("stage_artifact", name="synthesis", text="draft")
    assert out["refused"] == "CONTRACT_SCOPE" and "outside contract C1" in out["detail"]


# --- the no-suitable-tool outcome --------------------------------------------------

def test_a_predicate_no_check_can_establish_is_no_suitable_tool(lead):
    lead.person("set_requirement", requirement_id="R1", text="An interpretation.",
                closure="partial", predicates=["the reading is fair"])
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "s"}})
    lead.ok("advance")
    lead.ok("admit_contract", contract_id="C1", requirements=["R1"],
            write=[staging_folder(lead.ctx, lead.ctx.session)], verifiers={})
    lead.ok("advance")
    lead.ok("advance")                                       # nothing to wait for
    out = lead.ok("verify_grain", requirement="R1", predicate="the reading is fair")
    assert out["outcome"] == "no_suitable_tool"
    assert lead.summary()["requirements"]["R1"]["predicates"] == {
        "the reading is fair": "no_suitable_tool"}
    assert lead.ok("advance")["moved"] == "reduce"           # not waited for
    reduced = lead.ok("reduce_round")["reduced"]["R1"]
    assert reduced["status"] == "open" and "no_suitable_tool" in reduced["reason"]


# --- the person's checkpoint controls each change state ----------------------------

@pytest.mark.parametrize("control", ["set_requirement", "request_evidence", "accept_artifact",
                                     "reject_artifact"])
def test_every_checkpoint_control_changes_state(lead, evidence, control):
    round_to_reduce(lead, evidence)
    before = lead.summary()
    args = {"set_requirement": dict(requirement_id="R3", text="Cite a second source.",
                                    predicates=["a second source is quoted"]),
            "request_evidence": dict(requirement="R1", what="the contract's admission rule"),
            "accept_artifact": dict(requirement="R2", artifact="A1"),
            "reject_artifact": dict(requirement="R2", artifact="A1",
                                    reason="it omits the epoch rule")}[control]
    lead.person(control, **args)
    after = lead.summary()
    assert after != before
    if control == "set_requirement":
        assert after["requirements"]["R3"]["status"] == "open"
    elif control == "request_evidence":
        assert after["requirements"]["R1"]["revision"] == 2
        assert after["requirements"]["R1"]["status"] == "open"           # reopened
        assert after["requirements"]["R1"]["predicates"][
            "evidence is located for: the contract's admission rule"] == "not_checked"
    elif control == "accept_artifact":
        assert after["requirements"]["R2"]["status"] == "human_accepted"
    else:
        assert after["requirements"]["R2"]["person"][-1] == {
            "status": "open", "rejected": "A1", "reason": "it omits the epoch rule"}


def test_the_model_cannot_use_the_persons_controls(lead, evidence):
    round_to_reduce(lead, evidence)
    out = lead("accept_artifact", requirement="R2", artifact="A1")
    assert "refused" in out or "error" in out
    assert lead.summary()["requirements"]["R2"]["status"] == "open"


def test_accepting_an_artifact_edited_since_staging_is_refused(lead, evidence, vault):
    staged, *_ = round_to_reduce(lead, evidence)
    (vault.root / staged["path"]).write_text("changed", encoding="utf-8")
    person = Context(tier="curate", vault=vault, session=lead.ctx.session)
    out = REGISTRY.call("accept_artifact", {"requirement": "R2", "artifact": "A1"}, person)
    assert out["refused"] == "AUDIT_EVENT_INVALID" and "changed since it was staged" in out["detail"]


# --- the grain checks, one by one --------------------------------------------------

def test_intake_integrity_catches_an_edited_record(vault, evidence):
    assert research_grains.integrity(vault, {"evidence": evidence}).outcome == "pass"
    path = next(vault.evidence.glob(f"*/{evidence}.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["payload"]["text"] = "edited"
    path.write_text(json.dumps(data), encoding="utf-8")
    check = research_grains.integrity(vault, {"evidence": evidence})
    assert check.outcome == "fail" and "no longer matches its content hash" in check.statement


def test_coverage_names_what_was_not_examined(vault):
    dik.save(vault, {"source": "Paper", "kind": "document", "data": [
        {"id": "chapter:pp. 1-4", "locator": "pp. 1-4", "status": "observed"},
        {"id": "chapter:pp. 5-9", "locator": "pp. 5-9", "status": "not examined"}]})
    some = research_grains.coverage(vault, {"source": "Paper", "parts": ["pp. 1-4"]})
    assert some.outcome == "pass"
    assert some.statement == ("source `Paper`: 1 named part(s) have recorded status 'observed'; "
                              "not examined: pp. 5-9")
    every = research_grains.coverage(vault, {"source": "Paper"})
    assert every.outcome == "fail" and "not examined: pp. 5-9" in every.statement


def test_arithmetic_reproduces_from_the_evidence(vault):
    survey = EvidenceStore(vault).put("survey", "https://github.com/x/y", {"files": 42})
    note = vault.root / "Sources" / "y.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(f"---\nevidence: [{survey.id}]\n---\n# y\n\n## Summary\n\nIt has 42 files.\n",
                    encoding="utf-8")
    check = research_grains.arithmetic(vault, {"note": "Sources/y.md"})
    assert check.outcome == "pass" and "42 files" in check.statement
    note.write_text(f"---\nevidence: [{survey.id}]\n---\n# y\n\n## Summary\n\nIt has 40 files.\n",
                    encoding="utf-8")
    off = research_grains.arithmetic(vault, {"note": "Sources/y.md"})
    assert off.outcome == "fail" and "contradicted (recorded 42)" in off.statement


def test_claim_run_reports_the_persons_run_and_never_runs_one(vault):
    store = RunnableStore(vault)
    run_id = store.add("parse('') raises", "y", {"call": "m:parse", "args": [""], "kwargs": {},
                                                 "expect": "raises", "value": "ValueError"},
                       origin="test")
    assert research_grains.claim_run(vault, {"run": run_id}).outcome == "unavailable"
    store.record(run_id, {"verdict": "confirmed", "detail": "raised ValueError",
                          "version": "the surveyed version", "commit": "abc123def4567",
                          "evidence": "e1", "by": "person"})
    check = research_grains.claim_run(vault, {"run": run_id})
    assert check.outcome == "pass" and check.strength == "bounded"
    assert "on commit abc123def456 (the surveyed version)" in check.statement


def test_every_registered_tier_a_verifier_has_a_check():
    from resource_librarian import closure
    authoritative = {k for k, v in closure.VERIFIERS.items()
                     if v.kind in closure.AUTHORITATIVE_KINDS}
    assert set(research_grains.CHECKS) == authoritative


# --- telemetry and measurement -----------------------------------------------------

def test_the_manager_view_is_recorded_with_its_digest_and_bundle_count(lead):
    view = lead.ok("audit_projection")
    recorded = SessionStore(lead.ctx.vault).load(lead.ctx.session).manager_views[-1]
    assert recorded["digest"] == view["digest"]
    assert recorded["bundles"]["after_filter"] == len(view["manifest"]["bundles"])
    assert recorded["bundles"]["registered"] >= recorded["bundles"]["after_filter"]


def test_tier_a_share_is_measured_from_the_logs(lead, evidence, vault):
    round_to_reduce(lead, evidence)
    measured = research_grains.tier_a_share(vault)
    # R1's two predicates closed by Tier A; R2 (synthesis) is open.
    assert measured == {"sessions": 1, "grains": 3, "tier_a": 2, "human_accepted": 0,
                        "other": 1, "share": 0.667}
    lead.person("accept_artifact", requirement="R2", artifact="A1")
    assert research_grains.tier_a_share(vault)["human_accepted"] == 1


def test_findability_reports_each_missed_lookup(vault):
    missed = research_grains.findable(vault, {"note": "y"},
                                      index_run=lambda op: (["not in the top 5 for its title"], 5))
    assert missed.outcome == "fail" and "not in the top 5 for its title" in missed.statement
    found = research_grains.findable(vault, {"note": "y"}, index_run=lambda op: ([], 5))
    assert found.outcome == "pass" and found.statement.startswith("note `y` is in the top 5")
