"""P3 of the 2026-09-30 plan: state and orchestration.

Every write says where in the method it may run (Deeper Audit, "phase routing is only
explicit for a subset of writes"), and every purpose can reach the tools its own exit
conditions ask for (Requirements Addendum R5)."""
import re

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, SCOPES, Context
from resource_librarian.session import PURPOSES, WRITES, Session

from test_sessions import Model, library  # noqa: F401  (fixture)


def test_every_write_declares_where_it_may_run():
    unclassified = [s.name for s in map(REGISTRY.get, REGISTRY.names())
                    if s.effect != "read" and not s.external and not s.sessionless
                    and s.scope not in SCOPES]
    assert unclassified == []
    every_phase = {p for phases in PURPOSES.values() for p in phases}
    for name, phases in WRITES.items():
        assert phases and phases <= every_phase, (name, phases - every_phase)


def test_each_phase_can_call_what_its_own_exit_condition_asks_for(vault):
    names = set(REGISTRY.names())
    for purpose, phases in PURPOSES.items():
        for phase in phases:
            session = Session(id="S", purpose=purpose, project="P", question="q", phase=phase)
            asked = {w for line in session.missing(vault)
                     for w in re.findall(r"\b[a-z]+(?:_[a-z]+)*\b", line) if w in names}
            for name in asked:
                gate = WRITES.get(name)
                assert gate is None or phase in gate, f"{purpose}/{phase} asks for {name}"


def test_learn_and_apply_can_create_the_project_they_are_for(library):
    for purpose, extra in (("learn", {"question": "agile"}), ("apply", {"question": "q"})):
        m = Model(library)
        m.ok("open_session", purpose=purpose, **extra)
        out = m.ok("create_project", name=f"P {purpose}", stage="planning", summary="s",
                   pursuit_kind="learning")
        assert "error" not in out


def test_staged_sources_can_be_decided_where_they_are_staged():
    for phase in ("ingest", "seed", "assess", "judge"):
        assert phase in WRITES["staging_decide"], phase
    assert "ingest" not in WRITES                      # R12: capture in any phase


def test_scouting_is_a_search_step(library):
    m = Model(library)
    m.ok("open_session", purpose="explore", question="host monitoring")
    out = m("scout_discover")
    assert out["refused"] == "PHASE_GATE" and "search" in out["detail"]


def test_capability_cards_say_where_a_write_runs(vault):
    cards = {c["name"]: c for c in REGISTRY.call("capabilities", {}, Context(
        tier="contribute", vault=vault))["tools"]}
    assert cards["decide"]["phases"] == ["judge"] and cards["decide"]["scope"] == "phase"
    assert cards["write_note"]["scope"] == "session" and "phases" not in cards["write_note"]
    assert "scope" not in cards["search"]
