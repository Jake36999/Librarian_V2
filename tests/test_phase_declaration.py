"""W1 (owner, 2026-11-20): session purposes and phases are declared once, in
standard/phases.yaml, and the code reads them from there."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import phase_walk  # noqa: E402  (registers every tool, offline)
from resource_librarian import phases  # noqa: E402
from resource_librarian.agent_runtime import BUNDLES, required_bundle_actions  # noqa: E402
from resource_librarian.session import GATES, PURPOSES  # noqa: E402


def test_every_purposes_phase_is_declared_with_a_gate_whose_checks_exist():
    decl = phases.DECLARATION
    for purpose, sequence in PURPOSES.items():
        assert sequence == decl.purposes[purpose]
        for name in sequence:
            assert decl.phases[name].gate, name
            for g in decl.phases[name].gate:
                assert g.check in GATES, (name, g.check)


def test_a_bundle_is_the_phases_declared_tools():
    for name, ph in phases.DECLARATION.phases.items():
        assert BUNDLES[ph.bundle_id].names == ph.tools
    assert required_bundle_actions("map", purpose="suggest") == ("open_brief", "read_project")
    assert required_bundle_actions("frame", purpose="add_project") == ("create_project",)
    assert required_bundle_actions("frame", purpose="add_project", project="P",
                                   project_exists=True) == ()


def test_a_tool_a_gate_names_is_declared_as_its_remedy():
    """The drift guard: a check that starts telling a model to use a tool declares it, so the
    offer check (phase_walk) and the workflow map see it."""
    declared = phase_walk.gate_tools()
    for name, named in phase_walk.named_in_checks().items():
        assert named <= declared[name], (name, sorted(named - declared[name]))


def test_every_phase_offers_what_its_gate_and_any_refusal_name():
    rows = phase_walk.check_gates(list(PURPOSES), "contribute")
    blocked = [(r["purpose"], r["phase"], r["not_offered"]) for r in rows if r["status"] != "ok"]
    assert blocked == []


BASE = """
version: 1
tool_groups: {g: [a]}
tail: []
purposes: {p: {mode: librarian, phases: [one]}}
phases:
  one:
    ask: "?"
    bundle: {purpose: x, tools: [b, "@g"]}
    gate: [{check: c, remedies: [b]}]
"""


def test_a_declaration_expands_groups_and_refuses_what_it_cannot_mean():
    decl = phases.parse(BASE)
    assert decl.phases["one"].tools == ("b", "a")
    for broken, why in [
        (BASE.replace('"@g"', '"@nope"'), "no tool group"),
        (BASE.replace("phases: [one]", "phases: [one, two]"), "undeclared phase"),
        (BASE.replace("gate: [{check: c, remedies: [b]}]", "gate: []"), "declares its gate"),
        (BASE.replace("remedies: [b]", "remedies: [{tool: b, when: x}]"), "unknown remedy key"),
        (BASE.replace("version: 1", "version: 2"), "version 1"),
        (BASE.replace("mode: librarian", "mode: wizard"), "mode"),
    ]:
        with pytest.raises(phases.PhaseDefinitionError, match=why):
            phases.parse(broken)


def test_an_unregistered_check_is_refused():
    with pytest.raises(phases.PhaseDefinitionError, match="unregistered gate check"):
        phases.validate_checks(set(GATES) - {"judge"})
