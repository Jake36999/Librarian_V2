"""G5 readiness: a model can drive an audited round through the real App and Loop.

R1: each audited phase offers its round's tools, and the person's controls are
in no model bundle. R2: a scripted Lead runs one full round using only the
tools it is offered on each step - no registry shortcut, no paid call.
"""
from __future__ import annotations

import json

import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.agent_runtime import BUNDLES, DEFAULT_PROFILES, select_bundle
from resource_librarian.app import App
from resource_librarian.evidence import EvidenceStore
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, Scripted, ToolCall
from resource_librarian.session import SessionStore

PERSON_ONLY = {"set_requirement", "accept_artifact", "reject_artifact", "request_evidence"}
ROUND = {"manage": {"audit_projection", "update_plan"}, "preflight": {"admit_contract"},
         "execute": {"stage_artifact"}, "audit": {"verify_grain", "audit_targets"},
         "reduce": {"reduce_round"}}
QUOTE = "rounds are bounded by an admitted contract"


# --- R1: the bundles ---------------------------------------------------------------

@pytest.mark.parametrize("phase", list(ROUND))
def test_each_audited_phase_offers_its_round_tools(phase):
    offered = {s.name for s in select_bundle("contribute", phase, profile=DEFAULT_PROFILES["lead"],
                                             purpose="audited")}
    assert ROUND[phase] <= offered and "advance" in offered


@pytest.mark.parametrize("tier", ["consult", "contribute", "curate"])
def test_the_persons_controls_are_in_no_model_bundle(tier):
    assert not PERSON_ONLY & {n for b in BUNDLES.values() for n in b.names}
    for phase in (*ROUND, "frame", "search", ""):
        offered = {s.name for s in select_bundle(tier, phase, profile=DEFAULT_PROFILES["lead"])}
        assert not PERSON_ONLY & offered, (tier, phase)


# --- R2: a scripted Lead drives one round ------------------------------------------

class RoundLead:
    """A scripted Lead. Each step it may call only a tool it was just offered;
    anything else is recorded as a violation instead of being called."""

    def __init__(self, evidence):
        self.evidence = evidence
        self.violations: list[tuple[str, list[str]]] = []
        self.offered: list[set[str]] = []
        self.staged_in = ""
        self.plan = None
        self.n = 0

    def _last_result(self, messages):
        for message in reversed(messages):
            if message.get("role") == "tool":
                try:
                    return json.loads(message.get("content") or "{}")
                except ValueError:
                    return {}
        return {}

    def _steps(self):
        yield "open_session", {"purpose": "audited", "question": "How are rounds bounded?"}
        yield None                                      # turn 1 ends; the person sets requirements
        yield "audit_projection", {}
        yield "update_plan", {"fields": {"proposal": {
            "requirements": ["R1", "R2"], "step": "locate the quote and stage a synthesis"}}}
        yield "advance", {}
        yield "admit_contract", {
            "contract_id": "C1", "requirements": ["R1", "R2"], "write": [self.staged_in],
            "operations": ["read", "stage"],
            "verifiers": {"R1: quote present": "quote.located",
                          "R1: staged draft unchanged": "target.diff_clean"}}
        yield "advance", {}
        yield "stage_artifact", {"name": "synthesis",
                                 "text": "# Synthesis\n\nRounds are bounded by their contract.\n"}
        yield "advance", {}
        yield "verify_grain", {"requirement": "R1", "predicate": "quote present",
                               "params": {"evidence": self.evidence, "quote": QUOTE}}
        yield "verify_grain", {"requirement": "R1", "predicate": "staged draft unchanged"}
        yield "audit_targets", {}
        yield "advance", {}
        yield "reduce_round", {}
        yield None

    def __call__(self, system, messages, tools):
        names = {t.name for t in tools}
        self.offered.append(names)
        last = self._last_result(messages)
        if "staged_in" in last:
            self.staged_in = last["staged_in"]
        if self.plan is None:
            self.plan = self._steps()
        step = next(self.plan, None)
        if step is None:
            return Reply(text="Done for now.")
        tool, args = step
        if tool not in names:
            self.violations.append((tool, sorted(names)))
            return Reply(text=f"{tool} was not offered.")
        self.n += 1
        return Reply(tool_calls=[ToolCall(f"c{self.n}", tool, args)])


@pytest.fixture
def evidence(vault):
    return EvidenceStore(vault).put("page", "https://example.org/harness", {
        "text": f"In this design {QUOTE}, and each is audited."}).id


def test_a_scripted_lead_drives_a_full_round_using_only_offered_tools(vault, evidence):
    lead = RoundLead(evidence)
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: Scripted(lead))
    try:
        app.set_tiers([{"provider": "deepinfra", "model": "scripted-lead"}], override="test")
        app.set_mode("auto")
        loop = app._loop()
        loop.send("Open an audited session on how rounds are bounded.")
        sid = loop.ctx.session
        assert sid, "the Lead opened no session"
        app.person_call("set_requirement", {
            "requirement_id": "R1", "text": "The key quote is located.",
            "predicates": ["quote present", "staged draft unchanged"]}, session=sid)
        app.person_call("set_requirement", {
            "requirement_id": "R2", "text": "A synthesis the person accepts.",
            "closure": "human_judgment"}, session=sid)
        turn = loop.send("Work the round.")
    finally:
        app.close_runtime()
    assert lead.violations == [], lead.violations
    assert turn.stopped == "", turn.stopped
    session = SessionStore(vault).load(sid)
    from resource_librarian import audit_events, research_grains
    summary = audit_events.summary(session.audit)
    assert summary["requirements"]["R1"]["status"] == "verified"
    assert summary["requirements"]["R2"]["status"] == "open"            # the person's to accept
    assert summary["contracts"]["C1"]["integrity"] == "clean"
    assert research_grains.grain_counts(session.audit) == {
        "grains": 3, "tier_a": 2, "human_accepted": 0, "other": 1}


# --- R3: the runner, dry-run with the scripted Lead ---------------------------------

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("g5_measure", SCRIPTS / "g5_measure.py")
g5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g5)

TASK = {"id": "t1", "question": "How are rounds bounded?", "requirements": [
    {"requirement_id": "R1", "text": "The key quote is located.",
     "predicates": ["quote present", "staged draft unchanged"]},
    {"requirement_id": "R2", "text": "A synthesis the person accepts.",
     "closure": "human_judgment"}]}


def dry_run(vault, evidence, tmp_path):
    lead = RoundLead(evidence)
    row = g5.run_task(TASK, library=vault.root, run_dir=tmp_path / "run",
                      route={"provider": "deepinfra", "model": "scripted-lead"},
                      provider_for=lambda choice: Scripted(lead), max_turns=6)
    return lead, row


def test_the_runner_measures_a_scripted_session_on_a_scratch_copy(vault, evidence, tmp_path):
    before = sorted(p.relative_to(vault.root).as_posix() for p in vault.root.rglob("*"))
    lead, row = dry_run(vault, evidence, tmp_path)
    assert lead.violations == []
    assert row["stopped"] == "idle", row
    assert row["grains"] == {"grains": 3, "tier_a": 2, "human_accepted": 0, "other": 1}
    assert row["restart"] == {"after_turn": 2, "state_hash_equal": True}
    assert row["invalid_history"] is False and row["integrity"] == {"C1": "clean"}
    assert row["closure_audit"]["checked"] == 2 and row["closure_audit"]["false_closures"] == []
    assert {r["method"] for r in row["closure_audit"]["rows"]} == {"independent"}
    # The real library was only read.
    assert sorted(p.relative_to(vault.root).as_posix() for p in vault.root.rglob("*")) == before
    summed = g5.totals([row])["pooled"]
    assert summed["share"] == 0.667 and summed["interval_95"] == g5.wilson(2, 3)
    assert summed["false_closures"] == 0 and summed["restart_failures"] == 0


def test_a_paid_run_must_be_confirmed_and_priced(tmp_path, capsys):
    base = ["--library", str(tmp_path), "--tasks", "x.json", "--run-dir", str(tmp_path / "r"),
            "--budget-usd", "1"]
    assert g5.main(base + ["--route", "deepinfra:deepseek-ai/DeepSeek-V4.1-Flash"]) == 2
    assert "--confirm-paid" in capsys.readouterr().err
    assert g5.main(base + ["--route", "deepinfra:unpriced/model", "--confirm-paid"]) == 2
    assert "no checked rate card" in capsys.readouterr().err


def test_spend_fails_closed_without_usage():
    events = [{"type": "model_response", "usage": "unavailable"}]
    assert g5.spend(events, {"input_per_1m": 1, "output_per_1m": 1})["without_usage"] == 1


# --- R4: the closure audit ---------------------------------------------------------

def test_the_closure_audit_catches_a_closure_that_no_longer_holds(vault, evidence, tmp_path):
    from resource_librarian import closure_audit
    from resource_librarian.vault import Vault
    _, row = dry_run(vault, evidence, tmp_path)
    copy = Vault(tmp_path / "run" / "t1" / "vault")
    path = next(copy.evidence.glob(f"*/{evidence}.json"))
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["text"] = "rewritten without the passage"
    path.write_text(json.dumps(record), encoding="utf-8")
    found = closure_audit.audit(copy, SessionStore(copy).load(row["session"]))
    assert [r["verifier"] for r in found["false_closures"]] == ["quote.located"]
    assert "not in the evidence text" in found["false_closures"][0]["why"]
