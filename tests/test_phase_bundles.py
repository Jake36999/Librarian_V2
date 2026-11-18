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
