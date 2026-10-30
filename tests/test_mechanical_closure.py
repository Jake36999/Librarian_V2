"""HARNESS-07: mechanical authoritative closure - a bounded write completes only
after an exact verifier pass and a clean protected-target audit."""
from __future__ import annotations

import pytest

from resource_librarian import audit_events, research_grains
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.coordination import MISSING
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal
from resource_librarian.session import SessionStore

PLAN = {"R1: the note meets the content model": "schema.valid",
        "R1: the note's citations resolve": "citation.resolves"}


class Lead:
    def __init__(self, vault):
        self.ctx = Context(tier="contribute", vault=vault)

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


@pytest.fixture
def source(vault):
    path = vault.root / "Sources" / "s.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    (vault.root / "Notes").mkdir(exist_ok=True)
    path.write_text("---\ntype: note\ntitle: S\n---\n# S\n\nThe source.\n", encoding="utf-8")
    return EvidenceStore(vault).put("page", "https://example.org/s", {"text": "the source"}).id


def to_execute(vault, *, operations=None):
    lead = Lead(vault)
    lead.ok("open_session", purpose="audited", question="write the summary note")
    lead.person("set_requirement", requirement_id="R1", text="A cited summary note.",
                predicates=["the note meets the content model", "the note's citations resolve"],
                verifiers={predicate.split(": ", 1)[1]: {"verifier": verifier,
                                                         "params": {"note": "Notes/out.md"}}
                           for predicate, verifier in PLAN.items()})
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "write it"}})
    lead.ok("advance")
    admitted = lead.ok("admit_contract", contract_id="C1", requirements=["R1"],
                       write=["Notes/out.md"], read=["Sources/s.md"], verifiers=PLAN,
                       **({"operations": operations} if operations else {}))
    lead.ok("advance")
    return lead, admitted


def write(lead, evidence):
    lead.ok("write_note", folder="Notes", name="out", body="# Out\n\nFrom [[s]].\n",
            frontmatter={"title": "Out", "evidence": [evidence]})


def finish(lead):
    """Audit the targets, run both planned verifiers, reduce."""
    lead.ok("advance")
    audited = lead.ok("audit_targets")
    for predicate in ("the note meets the content model", "the note's citations resolve"):
        lead.ok("verify_grain", requirement="R1", predicate=predicate,
                params={"note": "Notes/out.md"})
    lead.ok("advance")
    return audited, lead.ok("reduce_round")


def test_the_snapshot_is_taken_at_admission_before_anything_writes(vault, source):
    lead, admitted = to_execute(vault)
    assert admitted["snapshot"] == {"id": "S1", "protected": 2}
    snap = lead.audit().snapshots["S1"]["targets"]
    assert snap["Notes/out.md"] == MISSING and snap["Sources/s.md"] != MISSING


def test_a_bounded_write_completes_after_its_verifiers_and_a_clean_audit(vault, source):
    lead, _ = to_execute(vault)
    write(lead, source)
    audited, reduced = finish(lead)
    assert audited["integrity"] == "clean" and audited["changed"] == ["Notes/out.md"]
    assert reduced["reduced"]["R1"] == {"status": "verified"}
    assert reduced["outcome"] == "complete_verified"
    summary = audit_events.summary(lead.audit())
    assert summary["contracts"]["C1"]["integrity"] == "clean"
    assert summary["requirements"]["R1"]["established"] == [
        "`Notes/out.md` parses and meets the content model for shape `note` (fields, "
        "sections, axis values)",
        "the 1 evidence id(s) and 1 wiki link(s) `Notes/out.md` cites all resolve"]


def test_the_audit_phase_waits_for_the_target_audit(vault, source):
    lead, _ = to_execute(vault)
    write(lead, source)
    lead.ok("advance")
    for predicate in PLAN:
        lead.ok("verify_grain", requirement="R1", predicate=predicate.split(": ", 1)[1],
                params={"note": "Notes/out.md"})
    waiting = lead.ok("advance")
    assert waiting["moved"] is False
    assert "protected targets are not audited yet" in waiting["missing"][0]


def test_verified_is_refused_without_a_clean_audit_even_by_a_direct_append(vault, source):
    lead, _ = to_execute(vault)
    write(lead, source)
    lead.ok("advance")
    for predicate in PLAN:
        lead.ok("verify_grain", requirement="R1", predicate=predicate.split(": ", 1)[1],
                params={"note": "Notes/out.md"})
    store = SessionStore(vault)
    with pytest.raises(Refusal, match="protected-target audit is not_audited"):
        store.append_audit(lead.ctx.session, {"type": "reduction", "requirement": "R1",
                                              "status": "verified", "results": ["V1", "V2"],
                                              "by": "core", "epoch": 0, "contract": "C1"})


def test_an_out_of_scope_change_is_a_violation_and_cannot_complete(vault, source):
    """The executor changes a protected read target behind the writer's back."""
    lead, _ = to_execute(vault)
    write(lead, source)
    (vault.root / "Sources" / "s.md").write_text("rewritten", encoding="utf-8")
    audited, reduced = finish(lead)
    assert audited["integrity"] == "violation"
    assert audited["findings"] == ["Sources/s.md changed but is not a write target"]
    assert reduced["reduced"]["R1"]["status"] == "blocked"
    assert reduced["outcome"] == "integrity_violation"


def test_an_unaccounted_change_to_a_write_target_is_suspect(vault, source):
    """The target changed, but no writer call of the contract wrote it."""
    lead, _ = to_execute(vault)
    note = vault.root / "Notes" / "out.md"
    note.write_text(f"---\ntitle: Out\nevidence: [{source}]\n---\n# Out\n\nFrom [[s]].\n",
                    encoding="utf-8")
    audited, reduced = finish(lead)
    assert audited["integrity"] == "suspect"
    assert "with no writer call of contract C1" in audited["findings"][0]
    assert reduced["reduced"]["R1"] == {"status": "blocked",
                                        "reason": "protected-target audit is suspect"}
    assert reduced["outcome"] == "needs_person"


def test_an_out_of_scope_tool_write_is_refused_and_leaves_the_audit_clean(vault, source):
    lead, _ = to_execute(vault)
    out = lead("write_note", folder="Notes", name="other", body="x")
    assert out["refused"] == "CONTRACT_SCOPE"
    write(lead, source)
    audited, reduced = finish(lead)
    assert audited["integrity"] == "clean" and reduced["reduced"]["R1"]["status"] == "verified"
    assert not (vault.root / "Notes" / "other.md").exists()


def test_unrelated_edits_elsewhere_do_not_touch_the_audit(vault, source):
    lead, _ = to_execute(vault)
    write(lead, source)
    (vault.root / "Notes" / "unrelated.md").write_text("someone else's note", encoding="utf-8")
    audited, _ = finish(lead)
    assert audited["integrity"] == "clean"


def test_a_contract_cannot_protect_the_whole_vault(vault, source):
    lead = Lead(vault)
    lead.ok("open_session", purpose="audited", question="q")
    lead.person("set_requirement", requirement_id="R1", text="t", predicates=["p"])
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "s"}})
    lead.ok("advance")
    out = lead("admit_contract", contract_id="C1", requirements=["R1"], write=["Notes/out.md"],
               read=["."], verifiers={"R1: p": "schema.valid"})
    assert out["refused"] == "CONTRACT_SCOPE" and "not the whole vault" in out["detail"]


def test_a_read_only_contract_needs_no_target_audit(vault, source):
    lead, admitted = to_execute(vault, operations=["read"])
    assert "snapshot" not in admitted
    (vault.root / "Notes" / "out.md").write_text(
        f"---\ntitle: Out\nevidence: [{source}]\n---\n# Out\n\nFrom [[s]].\n", encoding="utf-8")
    lead.ok("advance")
    for predicate in PLAN:
        lead.ok("verify_grain", requirement="R1", predicate=predicate.split(": ", 1)[1],
                params={"note": "Notes/out.md"})
    assert lead.ok("advance")["moved"] == "reduce"
    assert lead.ok("reduce_round")["reduced"]["R1"]["status"] == "verified"


# --- the added verifiers -----------------------------------------------------------

def test_schema_valid_names_each_violation(vault):
    bad = vault.root / "Notes" / "bad.md"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.write_text("---\ntype: source\n---\n# B\n", encoding="utf-8")
    check = research_grains.schema_valid(vault, {"note": "Notes/bad.md"})
    assert check.outcome == "fail" and "source requires `kind`" in check.statement


def test_citation_resolves_names_what_does_not(vault):
    note = vault.root / "Notes" / "c.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text("---\ntitle: C\nevidence: [deadbeef]\n---\n# C\n\nSee [[nowhere]].\n",
                    encoding="utf-8")
    check = research_grains.citation_resolves(vault, {"note": "Notes/c.md"})
    assert check.outcome == "fail"
    assert "evidence deadbeef is not stored" in check.statement
    assert "[[nowhere]] names no note" in check.statement


def test_boundary_staged_passes_a_staging_round_and_fails_a_direct_write(vault, source):
    lead, _ = to_execute(vault)
    write(lead, source)
    session = SessionStore(vault).load(lead.ctx.session)
    check = research_grains.boundary_staged(vault, {}, session=session)
    assert check.outcome == "fail" and "write_note (write)" in check.statement
