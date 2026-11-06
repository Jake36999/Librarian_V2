"""Approving or deferring several staged items, each as the person saw it (Codex UI ask 1;
MF-034b bulk triage).

Each row of a staging list carries the revision it shows. A person ticks items and sends
each one on its own with its revision. An item whose record changed since it was listed is
refused (`DOCUMENT_ACTIVE`, with a write-conflict checkpoint) and left untouched; the
others are decided.
"""
from __future__ import annotations

import pytest

from resource_librarian import staging
from resource_librarian.app import App
from resource_librarian.keys import KeyStore

NAMES = ("one", "two", "three")


@pytest.fixture
def core(vault):
    store = staging.StagingStore(vault)
    for name in NAMES:
        store.add({"id": f"src-{name}", "kind": "source", "name": f"Source {name}",
                   "source_kind": "paper", "evidence": [], "sections": {}})
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    try:
        yield app
    finally:
        app.close_runtime()


def listed(core):
    out = core.person_call("staging_list", {"kind": "source", "status": "staged"})
    return {row["id"]: row for row in out["items"]}


def decide(core, item_id, decision, revision="", reason=""):
    return core.person_call("staging_decide", {
        "item_ids": [item_id], "decision": decision, "reason": reason,
        **({"staged_revision": revision} if revision else {})})


def status(core, item_id):
    return staging.StagingStore(core.vault).load(item_id)["status"]


def edit_elsewhere(core, item_id):
    def change():
        store = staging.StagingStore(core.vault)
        item = store.load(item_id)
        item["note"] = "changed in another tab"
        store.save(item)
    core._serialized("edit-elsewhere", change)


def test_each_listed_row_carries_the_revision_it_shows(core):
    rows = listed(core)
    assert sorted(rows) == [f"src-{name}" for name in sorted(NAMES)]
    assert all(row["staged_revision"].startswith("rev1.") for row in rows.values())
    out = decide(core, "src-one", "approve", rows["src-one"]["staged_revision"])
    assert out["results"][0]["status"] == "approved" and status(core, "src-one") == "approved"


def test_a_changed_item_is_refused_and_untouched_while_the_others_are_decided(core):
    rows = listed(core)
    edit_elsewhere(core, "src-two")
    before = staging.StagingStore(core.vault).path("src-two").read_bytes()
    outcomes = {item_id: decide(core, item_id, "approve", rows[item_id]["staged_revision"])
                for item_id in rows}
    assert outcomes["src-two"]["refused"] == "DOCUMENT_ACTIVE"
    assert outcomes["src-two"]["checkpoint"]["type"] == "write_conflict"
    assert staging.StagingStore(core.vault).path("src-two").read_bytes() == before
    assert status(core, "src-two") == "staged"
    assert status(core, "src-one") == "approved" and status(core, "src-three") == "approved"


def test_a_defer_is_checked_the_same_way(core):
    rows = listed(core)
    edit_elsewhere(core, "src-three")
    assert decide(core, "src-three", "defer", rows["src-three"]["staged_revision"],
                  reason="later")["refused"] == "DOCUMENT_ACTIVE"
    assert status(core, "src-three") == "staged"
    out = decide(core, "src-one", "defer", rows["src-one"]["staged_revision"], reason="later")
    assert out["results"][0]["status"] == "deferred"


def test_a_revision_belongs_to_one_item(core):
    rows = listed(core)
    stray = decide(core, "src-two", "approve", rows["src-one"]["staged_revision"])
    assert stray["refused"] == "REVISION_REFUSED" and status(core, "src-two") == "staged"
    several = core.person_call("staging_decide", {
        "item_ids": ["src-one", "src-two"], "decision": "approve",
        "staged_revision": rows["src-one"]["staged_revision"]})
    assert several["refused"] == "REVISION_REQUIRED"
    assert status(core, "src-one") == "staged" and status(core, "src-two") == "staged"


def test_a_decision_without_a_revision_still_works(core):
    out = core.person_call("staging_decide", {"item_ids": ["src-one", "src-two"],
                                              "decision": "approve"})
    assert [r["status"] for r in out["results"]] == ["approved", "approved"]
