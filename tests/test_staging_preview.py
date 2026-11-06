"""MF-027b (spec U-B3): staging_show composes the exact preview of what accepting an item
writes, by the same code the accept runs, with no writes; the revision tokens stay the
only authority."""
from __future__ import annotations

import re

import pytest

from resource_librarian import staging
from resource_librarian.app import App
from resource_librarian.coordination import fingerprint
from resource_librarian.keys import KeyStore

from conftest import add_source, write_note


@pytest.fixture
def core(vault):
    write_note(vault.root, "Concepts/Widget.md", "type: concept\nstatus: active",
               "# Widget\n\n## Definition\nA person's own definition.\n")
    add_source(vault.root, "Original", "An existing accepted source with durable evidence.")
    store = staging.StagingStore(vault)
    store.add({"id": "new-widget", "kind": "source", "name": "New Widget",
               "source_kind": "document", "title": "Widget field study",
               "canonical_url": "https://example.org/paper",
               "review": {"draft": {"status": "ok", "bottom_line": "Widget field study measures practical effects.",
                                    "what_it_solves": "Evidence for evaluating Widget.", "model": "fixture-clerk"}},
               "sections": {"Claims": "Source-stated claims, not an endorsement."}, "evidence": []})
    store.add({"id": "revision-original", "kind": "source", "name": "Original",
               "source_kind": "repository", "revision_of": "Sources/repository/Original.md",
               "sections": {"Claims": "New source-stated claims with citations."}, "evidence": []})
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    try:
        yield app
    finally:
        app.close_runtime()


def library_files(vault):
    """Every file outside the app's own work folders, by fingerprint."""
    return {p.relative_to(vault.root).as_posix(): fingerprint(p) for p in vault.root.rglob("*")
            if p.is_file() and ".librarian" not in p.parts}


def without(text, field):
    return re.sub(rf"^{field}:.*\n", "", text, flags=re.M)


def test_a_revision_preview_is_exactly_what_accepting_it_writes(core):
    before = library_files(core.vault)
    shown = core.person_call("staging_show", {"item_id": "revision-original"})
    preview = shown["preview"]
    assert library_files(core.vault) == before                       # a preview writes nothing
    target = core.vault.root / "Sources/repository/Original.md"
    assert preview["status"] == "exact" and preview["kind"] == "revision"
    assert preview["current_markdown"].encode("utf-8") == target.read_bytes()
    assert preview["sections"] == ["Claims"] and preview["authorizes"] is False
    assert preview["source_revision"].startswith("rev1.")
    out = core.person_call("staging_decide", {"item_ids": ["revision-original"], "decision": "accept",
                                              "revision": shown["revision"],
                                              "staged_revision": shown["staged_revision"]})
    assert out["accepted"] == 1, out
    assert target.read_bytes() == preview["composed_markdown"].encode("utf-8")   # byte for byte


def test_a_new_source_preview_is_what_accepting_it_writes_but_its_stamp(core):
    shown = core.person_call("staging_show", {"item_id": "new-widget"})
    preview = shown["preview"]
    assert preview["status"] == "exact" and preview["kind"] == "new_source", preview
    assert preview["current_markdown"] == "" and preview["set_on_accept"] == ["catalogued_at"]
    assert preview["path"] == "Sources/document/New Widget.md"
    assert "Indexes/Master Index.md" in preview["dependencies"] and preview["dependency_digest"]
    draft = shown["review"]["draft"]
    out = core.person_call("staging_decide", {"item_ids": ["new-widget"], "decision": "accept",
                                              "bottom_line": draft["bottom_line"],
                                              "what_it_solves": draft["what_it_solves"],
                                              "staged_revision": shown["staged_revision"]})
    assert out["accepted"] == 1, out
    written = (core.vault.root / preview["path"]).read_text(encoding="utf-8")
    assert without(written, "catalogued_at") == without(preview["composed_markdown"], "catalogued_at")


def test_an_edit_needs_a_fresh_preview_and_a_stale_token_is_still_refused(core):
    shown = core.person_call("staging_show", {"item_id": "new-widget"})
    edited = core.person_call("staging_preview", {"item_id": "new-widget",
                                                  "bottom_line": "A different, person-written line.",
                                                  "what_it_solves": "Something else."})
    assert "A different, person-written line." in edited["preview"]["composed_markdown"]
    assert edited["preview"]["preview_digest"] != shown["preview"]["preview_digest"]

    def change():
        store = staging.StagingStore(core.vault)
        item = store.load("new-widget")
        item["title"] = "Changed in another tab"
        store.save(item)
    core._serialized("edit-elsewhere", change)
    again = core.person_call("staging_show", {"item_id": "new-widget"})
    assert again["preview"]["preview_digest"] != shown["preview"]["preview_digest"]
    stale = core.person_call("staging_decide", {"item_ids": ["new-widget"], "decision": "accept",
                                                "staged_revision": shown["staged_revision"]})
    assert stale.get("refused") == "DOCUMENT_ACTIVE"
    assert not (core.vault.root / "Sources/document/New Widget.md").exists()


def test_an_agent_sees_that_a_person_must_accept_not_a_preview_it_cannot_use(core):
    from resource_librarian.registry import REGISTRY, Context
    ctx = Context(tier="contribute", vault=core.vault, extras=core._extras())
    shown = REGISTRY.call("staging_show", {"item_id": "new-widget"}, ctx)
    assert shown["preview"]["status"] == "needs_person"
    assert shown["preview"]["refused"] == "PERSON_CONFIRMS" and "composed_markdown" not in shown["preview"]
