"""Process manifests and mandates in the Core (implementation plan M1b; W1b items 1-3).

A parent process is checked against a component's manifest alone, and a manifest goes stale when any
action it reaches changes, so an old manifest never authorises a changed action.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import jsonschema
import pytest

from resource_librarian import manifests, tools, workflows  # noqa: F401
from resource_librarian.registry import REGISTRY, Context

ROOT = Path(__file__).resolve().parents[1]
MANDATES = ROOT / "reports" / "2026-11-20-workflow-map" / "examples" / "manifests"
SCHEMA = json.loads((ROOT / "src" / "resource_librarian" / "standard" / "manifest.schema.json").read_text(encoding="utf-8"))
STANDARD = ROOT / "src" / "resource_librarian" / "standard"


def shipped():
    return sorted(p.stem for kind in ("workflows", "pipelines") for p in (STANDARD / kind).glob("*.yaml"))


@pytest.mark.parametrize("name", shipped())
def test_every_shipped_process_has_a_valid_fresh_manifest(name):
    library = workflows.Library(None)
    manifest = manifests.compile_process(name, library)
    jsonschema.validate(manifest, SCHEMA)
    assert manifests.problems_in(manifest) == []
    assert manifests.is_fresh(manifest, library)
    assert manifest["rollup"]["undeclared"] == []


def test_the_prototypes_two_mandate_checks_run_in_the_core():
    manifest = manifests.compile_process("clear-enrichment-backlog", workflows.Library(None))
    read_only = json.loads((MANDATES / "read-only-parent.mandate.json").read_text(encoding="utf-8"))
    ingestion = json.loads((MANDATES / "ingestion-sprint.mandate.json").read_text(encoding="utf-8"))
    assert manifests.check(manifest, read_only)          # refused for a read-only parent
    assert manifests.check(manifest, ingestion) == []    # suitable for an ingestion sprint


def test_a_mandate_can_limit_the_state_a_process_changes():
    manifest = manifests.compile_process("clear-enrichment-backlog", workflows.Library(None))
    problems = manifests.check(manifest, {"changes": ["staging"]})
    assert any("changes" in p and "outside" in p for p in problems)


def test_a_changed_action_makes_the_manifest_stale(monkeypatch):
    library = workflows.Library(None)
    manifest = manifests.compile_process("clear-enrichment-backlog", library)
    spec = REGISTRY.get("staging_review")
    monkeypatch.setitem(REGISTRY._tools, "staging_review", replace(spec, tier="curate"))
    assert not manifests.is_fresh(manifest, library)


def test_state_classes_are_declared_or_derived_and_always_known():
    for name in REGISTRY.names():
        classes, how = manifests.changes_of(name)
        assert set(classes) <= set(manifests.STATE_CLASSES), name
        assert how in ("declared", "derived")
    assert manifests.changes_of("staging_decide") == (("staging", "notes", "indexes"), "declared")
    assert manifests.changes_of("search")[0] == ()
    declared = manifests._declared_changes()
    assert set(declared) <= set(REGISTRY.names())         # only registered actions are declared


def test_the_same_layer_is_allowed_and_a_later_one_refused():
    manifest = manifests.compile_process("clear-enrichment-backlog", workflows.Library(None))
    assert manifest["layer"] == 2
    assert not any("layer rule" in p for p in manifests.check(manifest, {"parent_layer": 2}))
    assert any("layer rule" in p for p in manifests.check(manifest, {"parent_layer": 1}))


def test_process_manifest_tool_answers_from_the_manifest(vault):
    ctx = Context(tier="consult", vault=vault, extras={"caller_kind": "mcp"})
    out = REGISTRY.call("process_manifest", {"name": "clear-enrichment-backlog",
                                             "mandate": {"effects": ["read"], "open_world": False}}, ctx)
    assert out["valid"] is True and out["suitable"] is False and out["unsuitable"]
