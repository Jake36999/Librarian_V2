"""HARNESS-03: the audited Session purpose - phases, rounds, questions, budgets,
resume, and the writer-only append path."""
from __future__ import annotations

import json

import pytest

from resource_librarian import session as session_module
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal
from resource_librarian.session import SessionStore, attach_core_writer, detach_core_writer


class Lead:
    """The model, through the registry, as a surface would call it."""

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

    @property
    def store(self):
        return SessionStore(self.ctx.vault)

    def state(self):
        return self.store.load(self.ctx.session)


class Core:
    """What preflight, the executor, Tier A and reduction append (HARNESS-04..07 will)."""

    def __init__(self, lead):
        self.lead = lead

    def append(self, event):
        self.lead.store.append_audit(self.lead.ctx.session, event)

    @property
    def epoch(self):
        return self.lead.state().audit.epoch

    def admit(self, cid="C1", revision=1):
        self.append({"type": "contract", "id": cid, "revision": revision, "requirements": ["R1"],
                     "role": "lead", "epoch": self.epoch,
                     "targets": {"read": [], "write": ["notes/out.md"]}})

    def produce(self, aid="A1"):
        self.append({"type": "artifact", "id": aid, "path": "notes/out.md",
                     "fingerprint": "a" * 20, "contract": "C1"})

    def check(self, rid="V1", outcome="pass", aid="A1"):
        contract = self.lead.state().audit.contracts["C1"]
        self.append({"type": "verifier_result", "id": rid, "requirement": "R1",
                     "contract": "C1", "contract_revision": contract["revision"],
                     "predicate": "the note exists", "verifier": "tier_a.exists@1",
                     "strength": "exact", "outcome": outcome, "artifacts": [aid],
                     "epoch": self.epoch})

    def reduce(self, status, results=("V1",)):
        self.append({"type": "reduction", "requirement": "R1", "status": status,
                     "results": list(results), "by": "core", "epoch": self.epoch})


@pytest.fixture
def lead(vault):
    lead = Lead(vault)
    lead.ok("open_session", purpose="audited", question="write the summary note")
    return lead


def set_r1(lead):
    lead.person("set_requirement", requirement_id="R1", text="A summary note exists.",
                predicates=["the note exists"])


def propose(lead):
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"],
                                               "step": "draft notes/out.md"}})


def walk_to(lead, core, phase):
    """Walk round 1 to `phase` through tools and Core events."""
    set_r1(lead)
    propose(lead)
    order = ["preflight", "execute", "audit", "reduce"]
    for step in order[:order.index(phase) + 1]:
        if step == "execute":
            core.admit()
        elif step == "audit":
            core.produce()
        elif step == "reduce":
            core.check()
        assert lead.ok("advance")["moved"] == step


# --- the purpose and its phases ----------------------------------------------------

def test_a_full_round_verifies_and_closes(lead):
    core = Core(lead)
    walk_to(lead, core, "reduce")
    core.reduce("verified")
    session = lead.state()
    assert session.completion()["complete"] is True
    assert "close_session" in session.next_step(lead.ctx.vault)
    result = lead.ok("close_session", summary="The note exists and was checked.", gaps="none")
    assert result["completion"]["outcome"] == "complete_verified"


@pytest.mark.parametrize("setup,missing", [
    (lambda lead, core: None, "no requirements yet"),
    (lambda lead, core: set_r1(lead), "propose one bounded step"),
    (lambda lead, core: (set_r1(lead), lead.ok(
        "update_plan", fields={"proposal": {"requirements": ["R9"]}})), "unknown requirement"),
])
def test_manage_exits_only_with_requirements_and_a_proposal(lead, setup, missing):
    setup(lead, Core(lead))
    refused = lead.ok("advance")
    assert refused["moved"] is False and missing in refused["missing"][0]


def test_preflight_needs_an_admitted_contract_at_the_current_epoch(lead):
    set_r1(lead)
    propose(lead)
    lead.ok("advance")
    assert "no contract has been admitted" in lead.ok("advance")["missing"][0]
    core = Core(lead)
    core.admit()
    core.append({"type": "external_edit", "path": "notes/out.md", "fingerprint": "b" * 20,
                 "source": "watcher"})
    assert "admit it again" in lead.ok("advance")["missing"][0]
    core.admit(revision=2)
    assert lead.ok("advance")["moved"] == "execute"


def test_audit_and_reduce_wait_for_every_predicate_and_requirement(lead):
    core = Core(lead)
    walk_to(lead, core, "audit")
    assert "no result yet at this epoch for R1: the note exists" in lead.ok("advance")["missing"]
    core.check(outcome="fail")  # a failed check also completes the audit phase
    assert lead.ok("advance")["moved"] == "reduce"
    assert "requirement R1 has no reduction" in lead.ok("advance")["missing"][0]
    core.reduce("failed", results=())
    moved = lead.ok("advance")
    assert (moved["moved"], moved["round"]) == ("manage", 2)


def test_closing_names_what_is_unresolved(lead):
    core = Core(lead)
    walk_to(lead, core, "reduce")
    core.reduce("partial")
    refused = lead("close_session", summary="Drafted.", gaps="none")
    assert "name these gaps: R1 (partial)" in json.dumps(refused)
    done = lead.ok("close_session", summary="Drafted; not verified.", gaps="R1 is partial")
    assert done["completion"]["outcome"] == "in_progress"


def test_only_the_person_sets_requirements(lead):
    refused = lead("set_requirement", requirement_id="R1", text="x", predicates=["p"])
    assert refused.get("refused") == "TIER_REFUSED"
    set_r1(lead)
    events = [json.loads(l) for l in lead.store.path(lead.ctx.session).read_text(
        encoding="utf-8").splitlines() if l]
    assert [e["by"] for e in events if e["type"] == "requirement"] == ["person"]


def test_a_requirement_needs_an_audited_session(vault):
    other = Lead(vault)
    other.ok("open_session", purpose="explore", question="q")
    person = Context(tier="curate", vault=vault, session=other.ctx.session)
    result = REGISTRY.call("set_requirement", {"requirement_id": "R1", "text": "x",
                                               "predicates": ["p"]}, person)
    assert "audited session" in json.dumps(result)


# --- questions and budgets -----------------------------------------------------------

def test_an_unanswered_question_blocks_every_phase(lead):
    set_r1(lead)
    propose(lead)
    asked = lead.ok("ask_user", question="Which folder should the note go in?")
    refused = lead.ok("advance")
    assert refused["moved"] is False and "unanswered question" in refused["missing"][0]
    lead.person("answer", question_id=asked["question_id"], answer="notes/")
    assert lead.ok("advance")["moved"] == "preflight"


def test_a_new_round_restores_full_budgets_but_a_redo_halves_them(lead):
    core = Core(lead)
    walk_to(lead, core, "reduce")
    full = lead.state().budget_left()
    lead.ok("advance", target="audit")          # going back within the round
    lead.ok("advance")                           # audit is still complete
    assert lead.state().budget_left() < full    # the second visit to reduce is halved
    core.reduce("failed", results=())
    lead.ok("advance")                           # round 2 begins at manage
    session = lead.state()
    assert (session.phase, session.audit_round) == ("manage", 2)
    assert session.budget_left() == session.budgets["manage"]
    assert lead.ok("session_status")["round"] == 2


def test_the_round_limit_is_enforced(lead):
    (lead.ctx.vault.root / ".librarian" / "config.toml").write_text(
        "[session]\naudited_max_rounds = 1\n", encoding="utf-8")
    core = Core(lead)
    walk_to(lead, core, "reduce")
    core.reduce("failed", results=())
    refused = lead.ok("advance")
    assert refused["moved"] is False and "round limit reached (1)" in refused["missing"][0]


# --- resume (HARNESS-03 done-when) --------------------------------------------------

def test_a_paused_audited_session_resumes_with_the_same_state_hash(lead, vault):
    core = Core(lead)
    walk_to(lead, core, "execute")
    core.produce()
    before = lead.state().state_hash()
    lead.ok("park_session", note="stopping for now")
    assert lead.state().status == "parked"

    restarted = Lead(vault)                     # a new process: nothing held in memory
    restarted.ok("resume_session", session_id=lead.ctx.session)
    after = SessionStore(vault).load(lead.ctx.session)
    assert after.status == "open"
    assert after.state_hash() == before
    assert (after.phase, after.audit_round, after.audit.epoch) == ("execute", 1, 0)
    assert restarted.ok("advance")["moved"] == "audit"   # and the walk carries on


def test_the_state_hash_notices_a_real_change(lead):
    core = Core(lead)
    walk_to(lead, core, "execute")
    before = lead.state().state_hash()
    core.produce()
    assert lead.state().state_hash() != before


# --- the writer-only append path (HARNESS-03 done-when) ----------------------------

class RecordingWriter:
    def __init__(self):
        self.callers = []

    def submit(self, fn, caller=""):
        self.callers.append(caller)
        return fn()


def test_every_session_append_goes_through_the_core_writer(vault):
    writer = RecordingWriter()
    attach_core_writer(vault, writer)
    try:
        lead = Lead(vault)
        lead.ok("open_session", purpose="audited", question="q")
        core = Core(lead)
        walk_to(lead, core, "reduce")
        core.reduce("verified")
        lead.ok("close_session", summary="Done.", gaps="none")
        lines = [l for l in lead.store.path(lead.ctx.session).read_text(
            encoding="utf-8").splitlines() if l]
        session_writes = [c for c in writer.callers if c.startswith("session-")]
        assert len(lines) == len(session_writes)   # no line was written around the writer
        assert "session-audit-event" in session_writes
    finally:
        detach_core_writer(vault, writer)
        session_module._STOPPED_CORES.discard(session_module._vault_key(vault))


def test_after_the_core_stops_an_audit_event_is_refused_not_written_directly(vault):
    lead = Lead(vault)
    lead.ok("open_session", purpose="audited", question="q")
    path = lead.store.path(lead.ctx.session)
    writer = RecordingWriter()
    attach_core_writer(vault, writer)
    detach_core_writer(vault, writer)          # this process's Core stopped
    try:
        before = path.read_text(encoding="utf-8")
        with pytest.raises(Refusal, match="CORE_REQUIRED"):
            lead.store.append_audit(lead.ctx.session, {
                "type": "requirement", "id": "R1", "revision": 1, "text": "x",
                "closure": "authoritative", "predicates": ["p"], "by": "person"})
        assert path.read_text(encoding="utf-8") == before
    finally:
        session_module._STOPPED_CORES.discard(session_module._vault_key(vault))
