"""ROUTE-05: one golden snapshot of what the three-position picker and the service
slots show, and a cross-check that every readiness label names the route that
actually executes for its role.

The snapshot is the API payload behind the picker (`/api/routes/readiness`) and
the service slots (`/api/services`), with volatile fields (fingerprints, times,
revisions, spend) removed. Regenerate it only after reviewing the change:

    LIBRARIAN_UPDATE_GOLDEN=1 pytest tests/test_route_picker_snapshot.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from resource_librarian.app import App
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, Scripted

GOLDEN = Path(__file__).parent / "golden" / "route_picker.json"
CHAT_ROLES = ("lead", "scribe", "clerk", "research_helper")


def route(model):
    return {"provider": "deepinfra", "model": model}


@pytest.fixture
def app(vault):
    app = App(vault, keys=KeyStore(use_keyring=False), coordinate=True,
              provider_for=lambda choice: Scripted(lambda *_: Reply(choice["model"])))
    try:
        # The three picker positions, each a different model.
        app.set_tiers([route("lead-m"), route("notes-m"), route("intake-m")], override="test")
        # One service slot chosen away from its default.
        app.set_service("ocr", "deepinfra", "vision-m")
        # Evidence for Clerk only: it must label Clerk, and nothing else.
        prints = app._qualification_fingerprints("preset-deepinfra", "intake-m", "clerk")
        app.qualifications.record(host_id="preset-deepinfra", model_id="intake-m", role="clerk",
                                  level="L1", outcome="pass",
                                  compatibility_fingerprint=prints["compatibility"],
                                  behavior_fingerprint=prints["behavior"],
                                  probe_validation={"contract_version": "3", "passed": True})
        yield app
    finally:
        app.close_runtime()


def _binding(row):
    if row is None:
        return None
    return {k: row[k] for k in ("host_id", "model_id", "protocol", "adapter_id", "evidence_kind",
                                "source", "inherits_from")}


def snapshot(app) -> dict:
    """The picker and service-slot payloads, as the API serialises them, minus noise."""
    readiness = json.loads(json.dumps(app.route_readiness(), default=str))
    services = json.loads(json.dumps(app.services(), default=str))
    routes = [{"host_id": r["host_id"], "model": r["model"], "bound_roles": r["bound_roles"],
               "active_task": r["active_task"], "binding_errors": r["binding_errors"],
               "host_enabled": r["host_enabled"],
               "qualification_by_role": {role: q["status"]
                                         for role, q in r["qualification_by_role"].items()}}
              for r in readiness["routes"] if r["bound_roles"] or r["active_task"]]
    slots = [{"slot": s["slot"], "number": s["number"], "label": s["label"],
              "provider": s.get("provider", ""), "model": s.get("model", ""),
              "built": s.get("built"), "default": s.get("default"),
              "route_status": s.get("route_status"),
              "adapter_status": (s.get("adapter") or {}).get("status"),
              "binding": _binding(s.get("binding"))}
             for s in services["slots"]]
    return {"picker_positions": app.settings.data["tiers"],
            "bindings": {role: _binding(b) for role, b in readiness["bindings"].items()},
            "routes": sorted(routes, key=lambda r: (r["host_id"], r["model"])),
            "service_slots": slots}


def test_the_picker_and_service_slots_match_the_golden_snapshot(app):
    current = snapshot(app)
    if os.environ.get("LIBRARIAN_UPDATE_GOLDEN"):
        GOLDEN.parent.mkdir(exist_ok=True)
        GOLDEN.write_text(json.dumps(current, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    assert current == json.loads(GOLDEN.read_text(encoding="utf-8"))


def test_every_readiness_label_names_the_route_that_executes(app):
    """Label truth equals runtime truth, role by role."""
    readiness = app.route_readiness()
    labelled = {role: [(r["host_id"], r["model"]) for r in readiness["routes"]
                       if role in r["bound_roles"] and r["host_id"].startswith("preset-")]
                for role in CHAT_ROLES}
    extras = app._extras()
    executed = {"lead": app._loop().send("hello").reply,
                "scribe": extras["scribe"].provider.chat("", [], []).text,
                "clerk": extras["clerk"].provider.chat("", [], []).text,
                "research_helper": extras["helper_provider"](2).chat("", [], []).text}
    for role in CHAT_ROLES:
        assert labelled[role] == [("preset-deepinfra", executed[role])], role
        assert readiness["bindings"][role]["model_id"] == executed[role], role


def test_qualification_labels_are_per_role(app):
    row = next(r for r in app.route_readiness()["routes"]
               if r["host_id"] == "preset-deepinfra" and r["model"] == "intake-m")
    by_role = {role: q["status"] for role, q in row["qualification_by_role"].items()}
    assert by_role["clerk"] == "screened"
    assert {by_role[r] for r in ("lead", "scribe", "research_helper")} == {"experimental"}


def test_changing_one_slot_changes_only_that_slot(app):
    before = snapshot(app)
    app.set_service("ocr", "deepinfra", "vision-other")
    after = snapshot(app)
    changed = [s["slot"] for s, t in zip(before["service_slots"], after["service_slots"]) if s != t]
    assert changed == ["ocr"]
    assert {k: v for k, v in after.items() if k != "service_slots"} == \
        {k: v for k, v in before.items() if k != "service_slots"}
