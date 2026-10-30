"""REMED-06, admission usability and stall handling (Codex review R4, U1, U2).

Stable predicate ids, a contract skeleton built from the person's bindings,
structured refusal details, and no-progress tracking that parks the dependent
requirement. Admission itself is unchanged: every check still runs."""
from __future__ import annotations

import json

import pytest
from test_g5_readiness import g5
from test_research_round import (QUOTE, Lead, evidence, lead,  # noqa: F401  (fixtures)
                                 requirements, staging_folder)

from resource_librarian import session as session_module
from resource_librarian.audit_projection import contract_skeleton
from resource_librarian.providers import Reply, Scripted, ToolCall
from resource_librarian.session import SessionStore


def state(lead):
    return SessionStore(lead.ctx.vault).load(lead.ctx.session)


def to_preflight(lead, evidence, step=("R1", "R2")):
    requirements(lead, evidence)
    lead.ok("update_plan", fields={"proposal": {"requirements": list(step), "step": "s"}})
    lead.ok("advance")


def details(result):
    return result.get("details") or {}


# --- stable predicate ids ---------------------------------------------------------------

def test_predicates_keep_their_ids_across_revisions(lead):
    lead.person("set_requirement", requirement_id="R1", text="t", predicates=["a", "b"])
    lead.person("set_requirement", requirement_id="R1", text="t", predicates=["a", "b", "c"])
    lead.person("set_requirement", requirement_id="R1", text="t", predicates=["c", "a"])
    assert lead.audit().requirements["R1"]["ids"] == {"a": "p1", "b": "p2", "c": "p3"}
    lead.person("set_requirement", requirement_id="R1", text="t", predicates=["a", "d"])
    assert lead.audit().requirements["R1"]["ids"]["d"] == "p4"      # never a reused id


def test_a_plan_and_a_check_can_name_predicates_by_id(lead, evidence):
    to_preflight(lead, evidence)
    admitted = lead.ok("admit_contract", contract_id="C1", requirements=["R1", "R2"],
                       write=[staging_folder(lead.ctx, lead.ctx.session)],
                       operations=["read", "stage"],
                       verifiers={"R1.p1": "quote.located", "R1.p2": "target.diff_clean"})
    assert admitted["verifiers"] == {"R1: quote present": "quote.located",
                                     "R1: staged draft unchanged": "target.diff_clean"}
    lead.ok("advance")
    lead.ok("stage_artifact", name="synthesis", text="draft")
    lead.ok("advance")
    by_id = lead.ok("verify_grain", requirement="R1", predicate="p1",
                    params={"evidence": evidence, "quote": QUOTE})
    dotted = lead.ok("verify_grain", requirement="R1.p2")
    assert by_id["outcome"] == "pass" and dotted["outcome"] == "pass"


# --- the contract skeleton ----------------------------------------------------------------

def test_the_skeleton_is_admissible_as_built_and_the_round_verifies(lead, evidence):
    to_preflight(lead, evidence)
    projected = lead.ok("audit_projection")
    skeleton = projected["essential"]["contract_skeleton"] if "essential" in projected \
        else projected["contract_skeleton"]
    assert skeleton["complete"] is True and "needs" not in skeleton
    args = skeleton["arguments"]
    assert args["verifiers"] == {"R1.p1": "quote.located", "R1.p2": "target.diff_clean"}
    assert args["operations"] == ["read", "untrusted", "stage"]
    assert any(p.endswith(f"{evidence}.json") for p in args["read"])
    lead.ok("admit_contract", **args)                     # admitted unchanged
    lead.ok("advance")
    lead.ok("stage_artifact", name="synthesis", text="draft")
    lead.ok("advance")
    lead.ok("verify_grain", requirement="R1", predicate="p1",
            params={"evidence": evidence, "quote": QUOTE})
    lead.ok("verify_grain", requirement="R1", predicate="p2")
    lead.ok("audit_targets")
    lead.ok("advance")
    assert lead.ok("reduce_round")["reduced"]["R1"] == {"status": "verified"}


def test_the_skeleton_never_guesses_an_unnamed_verifier(lead):
    lead.person("set_requirement", requirement_id="R1", text="The figure matches.",
                predicates=["the figure matches the source"])
    lead.ok("update_plan", fields={"proposal": {"requirements": ["R1"], "step": "s"}})
    lead.ok("advance")
    skeleton = contract_skeleton(state(lead), lead.ctx.vault)
    assert skeleton["complete"] is False and skeleton["arguments"]["verifiers"] == {}
    [need] = skeleton["needs"]
    assert need["predicate"] == "R1.p1" and "quote.located" in need["eligible"]
    assert "review.llm" not in need["eligible"]
    out = lead("admit_contract", **skeleton["arguments"])     # still refused, in detail
    assert details(out)["kind"] == "missing_verifier"
    assert details(out)["predicate_id"] == "R1.p1"


def test_the_skeleton_is_shown_only_while_a_contract_is_prepared(lead, evidence):
    to_preflight(lead, evidence)
    lead.ok("admit_contract", **contract_skeleton(state(lead), lead.ctx.vault)["arguments"])
    lead.ok("advance")                                           # execute
    assert contract_skeleton(state(lead), lead.ctx.vault) is None


# --- structured refusal details ----------------------------------------------------------

def test_a_refused_plan_says_what_would_be_admitted(lead, evidence):
    to_preflight(lead, evidence)
    out = lead("admit_contract", contract_id="C1", requirements=["R1"],
               verifiers={"R9.p1": "quote.located"})
    assert details(out)["kind"] == "unknown_predicate_key"
    assert details(out)["valid_ids"] == ["R1.p1", "R1.p2"]
    out = lead("admit_contract", contract_id="C1", requirements=["R1"],
               verifiers={"R1.p1": "index.findable", "R1.p2": "target.diff_clean"})
    assert details(out) == {"kind": "person_named_verifier", "key": "R1: quote present",
                            "expected": "quote.located", "given": "index.findable"}
    out = lead("admit_contract", contract_id="C1", requirements=["R7"], verifiers={})
    assert details(out)["kind"] == "unknown_id" and details(out)["known"] == ["R1", "R2"]


# --- no progress parks the dependent requirement ----------------------------------------

@pytest.fixture
def limit(monkeypatch):
    monkeypatch.setattr(session_module, "AUDITED_STALL_LIMIT", 3)
    return 3


def test_answered_rephrased_questions_park_the_dependent_requirement(lead, evidence, limit):
    to_preflight(lead, evidence, step=("R1",))
    out = None
    for n in range(limit):
        asked = lead.ok("ask_user", question=f"Which source should I use, version {n}?")
        lead.person("answer", question_id=asked["question_id"], answer="Work from the "
                                                                       "requirements.")
        out = asked
    assert out["stalled"]["parked"] == ["R1"]
    assert out["stalled"]["independent"] == ["R2"]               # still open for other work
    assert "3 questions" in out["stalled"]["reason"]
    assert lead.audit().requirement_status("R1") == "blocked"
    assert lead.audit().requirement_status("R2") == "open"
    assert state(lead).stall == {"questions": 0, "refusals": 0}   # parking is recorded progress


def test_repeated_refusals_park_and_progress_resets_the_count(lead, evidence, limit):
    to_preflight(lead, evidence, step=("R1",))
    bad = {"contract_id": "C1", "requirements": ["R1"], "verifiers": {"R1.p1": "review.llm"}}
    lead("admit_contract", **bad)
    lead("admit_contract", **bad)
    assert state(lead).stall["refusals"] == 2
    lead.ok("admit_contract", **contract_skeleton(state(lead), lead.ctx.vault)["arguments"])
    assert state(lead).stall == {"questions": 0, "refusals": 0}  # an admitted contract is progress


def test_the_persons_own_refused_calls_are_not_a_stall(lead, evidence, limit):
    to_preflight(lead, evidence, step=("R1",))
    for _ in range(limit + 1):
        person = Lead(lead.ctx.vault, session=lead.ctx.session)
        person.ctx.tier = "curate"
        person("accept_artifact", requirement="R1", artifact="A9")     # refused each time
    assert lead.audit().requirement_status("R1") == "open"


def test_the_person_reopens_a_parked_requirement_by_revising_it(lead, evidence, limit):
    to_preflight(lead, evidence, step=("R1",))
    for n in range(limit):
        lead.ok("ask_user", question=f"question {n}?")
    assert lead.audit().requirement_status("R1") == "blocked"
    lead.person("set_requirement", requirement_id="R1", text="The key quote is located.",
                predicates=["quote present", "staged draft unchanged"])
    assert lead.audit().requirement_status("R1") == "open"


def test_a_scripted_lead_that_only_asks_ends_predictably(vault, evidence, tmp_path, limit):
    """A Lead that rephrases one question forever, answered with the fixed answer
    each time: the runner stops on the parked requirement, not at max_turns."""
    asked = []

    def model(system, messages, tools):
        asked.append(1)
        return Reply(tool_calls=[ToolCall(f"c{len(asked)}", "ask_user",
                                          {"question": f"Could you clarify scope, take {len(asked)}?"})])

    task = {"id": "loop", "question": "q", "requirements": [
        {"requirement_id": "R1", "text": "A synthesis the person accepts.",
         "closure": "human_judgment"}]}
    row = g5.run_task(task, library=vault.root, run_dir=tmp_path / "run",
                      route={"provider": "deepinfra", "model": "scripted"},
                      provider_for=lambda choice: Scripted(model), max_turns=40,
                      permission_wait=0.5)
    assert row["stopped"] == "settled: blocked", row["stopped"]
    # Each rephrasing was a new question, answered at once: still no progress.
    assert len(row["questions"]) == limit and len(asked) == limit


def test_a_lead_repeating_an_answered_question_ends_its_turn_when_parked(lead, evidence, limit):
    """The reuse guard answers a repeat at once, so a looping Lead never waits:
    it is the stall count that stops it, at the limit, inside one turn."""
    to_preflight(lead, evidence, step=("R1",))
    first = lead.ok("ask_user", question="Which source?")
    lead.person("answer", question_id=first["question_id"], answer="Any.")
    again = [lead.ok("ask_user", question="Which source (again)?") for _ in range(limit - 1)]
    assert all(a.get("answered_earlier") for a in again)
    assert again[-1]["stalled"]["parked"] == ["R1"]


def test_the_stall_count_survives_a_restart(lead, evidence, limit):
    to_preflight(lead, evidence, step=("R1",))
    lead.ok("ask_user", question="first?")
    lead.ok("ask_user", question="second?")
    resumed = Lead(lead.ctx.vault)
    resumed.ok("resume_session", session_id=lead.ctx.session)
    assert state(lead).stall == {"questions": 2, "refusals": 0}
    assert json.dumps(state(lead).stall)
