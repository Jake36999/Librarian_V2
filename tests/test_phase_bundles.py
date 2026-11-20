"""Every phase's exit gate must be satisfiable with the tools its bundle offers.

The in-app lead is offered only the phase's compact bundle, and the registry refuses anything
else (TOOL_BUNDLE_REFUSED). A gate that asks for a tool its bundle omits can never be met: a model
refused `advance` 15 times in Map (2026-11-18), and the same gap was found in Need, Search, Judge,
Synthesise, Check-out and every phase of the other purposes. `scripts/phase_walk.py` finds them;
this test keeps them found.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import phase_walk  # noqa: E402

from resource_librarian.agent_runtime import MAX_BUNDLE_TOOLS, bundle_selection  # noqa: E402
from resource_librarian.session import PURPOSES  # noqa: E402


def _blocked(summary):
    return [f"{purpose}/{phase}: {', '.join(tools)}"
            for purpose, phases in summary.items() for phase, tools in phases.items()]


def test_no_gate_asks_for_a_tool_its_phase_does_not_offer():
    rows = phase_walk.check_gates(list(PURPOSES), "contribute")
    assert not [r for r in rows if r["status"] == "could_not_open"], rows
    assert _blocked(phase_walk.summarise({"gates": rows})) == []


def test_a_scripted_agent_can_walk_the_text_purposes_on_the_enforced_surface():
    walk = phase_walk.check_walk(list(phase_walk.TEXT_PURPOSES_FOR_WALK), "contribute")
    summary = phase_walk.summarise({"walk": walk})
    assert _blocked(summary) == []
    stuck = [(purpose, s["phase"], s.get("detail")) for purpose, steps in walk.items()
             for s in steps if s["status"] in ("STUCK", "FAIL")]
    assert stuck == []


def test_gate_hints_use_the_syntax_update_plan_accepts():
    """update_plan takes `fields={...}`; a hint that teaches `update_plan(map=...)` fails."""
    import inspect

    from resource_librarian.session import Session
    source = inspect.getsource(Session) + inspect.getsource(Session.missing)
    assert not re.findall(r"update_plan\((?!fields=)[a-z_]+=", source)


@pytest.mark.parametrize("purpose", sorted(PURPOSES))
def test_a_phase_bundle_is_never_clipped_by_the_tool_cap(purpose):
    """Gate tools, required actions and the tail tools (read_result, macro_run, macro_plan) must
    all fit: the cap clips from the end, so an overflow silently drops a tail tool."""
    from resource_librarian.agent_runtime import BUNDLES
    from resource_librarian.registry import REGISTRY
    for phase in PURPOSES[purpose]:
        bundle_id = phase.replace("_", "-")
        names = [n for n in (BUNDLES[bundle_id].names if bundle_id in BUNDLES else ())
                 if n in REGISTRY]
        tail = [n for n in ("read_result", "macro_run", "macro_plan") if n not in names]
        # plus the at-most-two session-aware required actions (create_project, read_project)
        assert len(names) + len(tail) + 2 <= MAX_BUNDLE_TOOLS, (purpose, phase, len(names))
        offered = {s.name for s in bundle_selection("contribute", phase.replace("_", "-"),
                                                   purpose=purpose).offered}
        assert set(tail) <= offered, (purpose, phase, set(tail) - offered)


def test_an_audited_session_can_be_closed_and_every_phase_can_park():
    """Stress F-06 / F-12: the audited round's next-step text ends in close_session, and a spent
    budget tells the model to park_session, so both must be on the surface that says so."""
    offered = {s.name for s in bundle_selection("contribute", "reduce", purpose="audited").offered}
    assert "close_session" in offered         # the registry allows it in reduce, not in manage
    for purpose, phases in PURPOSES.items():
        for phase in phases:
            offered = {s.name for s in bundle_selection("contribute", phase, purpose=purpose).offered}
            assert "park_session" in offered, (purpose, phase)


def test_a_terminal_phase_can_go_back(vault):
    """Stress ST-F12: `advance` (which also moves back) was not offered in check-out or in
    learn's next, so a model could not return to redo a phase."""
    from resource_librarian.agent_runtime import BUNDLES
    assert "advance" in BUNDLES["check-out"].names and "advance" in BUNDLES["next"].names


def test_research_phases_offer_the_librarys_graphs_read_only():
    """2026-11-20: agents researching a 96-paper corpus never reached its knowledge graphs; no
    phase bundle offered Geo-Grapher. The paper graph is the access route for third-party papers."""
    from resource_librarian.agent_runtime import BUNDLES, GRAPH_CHECK, GRAPH_FIND, GRAPH_READ, MAX_BUNDLE_TOOLS
    assert set(GRAPH_FIND) <= set(BUNDLES["need"].names)
    assert set(GRAPH_FIND + GRAPH_READ) <= set(BUNDLES["search"].names)
    assert set(GRAPH_CHECK) <= set(BUNDLES["judge"].names) and set(GRAPH_CHECK) <= set(BUNDLES["synthesise"].names)
    assert all(name.startswith("mcp__geo-grapher__") for name in GRAPH_FIND + GRAPH_READ + GRAPH_CHECK)
    # The tail tools still fit after the largest research bundle.
    assert len(BUNDLES["search"].names) + 4 <= MAX_BUNDLE_TOOLS


def test_an_unknown_macro_is_refused_before_anyone_is_asked(vault):
    """2026-11-20: macro_run('resume_session') waited 600 s for an approval, then parked the thread."""
    from resource_librarian.broker import Broker
    from resource_librarian.registry import REGISTRY, Context
    broker = Broker(mode="auto", timeout=30)
    out = REGISTRY.call("macro_run", {"macro": "resume_session", "inputs": {}},
                        Context(tier="contribute", vault=vault, extras={"broker": broker}))
    assert out.get("error") and "no macro" in str(out.get("detail")), out
    assert not broker.pending()
