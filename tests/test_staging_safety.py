"""Selected staging writes share the Core's revision/lease/index boundaries."""
from dataclasses import replace
import json
import queue
import threading

import pytest

from resource_librarian import revisions, staging
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY
from resource_librarian.registry import Context
from resource_librarian.rules import Refusal
from resource_librarian.tools import library

from conftest import add_source


@pytest.fixture
def core(vault):
    add_source(vault.root, "Original", "An existing accepted source with durable evidence.")
    staging.StagingStore(vault).add({"id": "revision-original", "kind": "source", "name": "Original",
        "source_kind": "repository", "revision_of": "Sources/repository/Original.md",
        "sections": {"Claims": "New source-stated claims with citations."}, "evidence": []})
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    try:
        yield app
    finally:
        app.close_runtime()


def show(core):
    return core.person_call("staging_show", {"item_id": "revision-original"})


def accept(core, reviewed=None):
    args = {"item_ids": ["revision-original"], "decision": "accept"}
    if reviewed:
        args.update(revision=reviewed["revision"], staged_revision=reviewed["staged_revision"])
    return core.person_call("staging_decide", args)


def test_a_note_edited_since_review_is_not_merged(core):
    reviewed = show(core)
    path = core.vault.root / reviewed["revision_of"]
    path.write_text(path.read_text(encoding="utf-8") + "\nA human's own annotation.\n", encoding="utf-8")
    before = path.read_bytes()
    out = accept(core, reviewed)
    assert out["refused"] == "DOCUMENT_ACTIVE" and out["checkpoint"]["type"] == "write_conflict"
    assert path.read_bytes() == before
    assert staging.StagingStore(core.vault).load("revision-original")["status"] == "staged"


def test_changed_staged_content_invalidates_the_review_even_when_note_is_unchanged(core):
    reviewed = show(core)
    store = staging.StagingStore(core.vault)
    def change():
        item = store.load("revision-original")
        item["sections"]["Claims"] = "A different proposed claim."
        store.save(item)
    core._serialized("change-staged-content", change)
    out = accept(core, reviewed)
    assert out["refused"] == "DOCUMENT_ACTIVE"
    assert "New source-stated" not in (core.vault.root / reviewed["revision_of"]).read_text(encoding="utf-8")
    fresh = accept(core, show(core))
    assert fresh["accepted"] == 1
    assert "A different proposed claim." in (core.vault.root / reviewed["revision_of"]).read_text(encoding="utf-8")


def test_an_agent_needs_its_own_note_revision_but_an_explicit_person_action_remains_compatible(core):
    args = {"item_ids": ["revision-original"], "decision": "accept"}
    assert core.mcp_call("staging_decide", args, tier="contribute")["result"]["refused"] == "REVISION_REQUIRED"
    reviewed = show(core)
    wrong_holder = core.mcp_call("staging_decide", {**args, "revision": reviewed["revision"]}, tier="contribute")["result"]
    assert wrong_holder["refused"] == "REVISION_REFUSED"
    assert accept(core)["accepted"] == 1  # Existing person-owned API compatibility.


def test_an_active_document_lease_blocks_the_merge(core):
    reviewed = show(core)
    core.document_leases.heartbeat(reviewed["revision_of"], editor="Obsidian", dirty=True)
    out = accept(core, reviewed)
    assert out["refused"] == "DOCUMENT_ACTIVE"
    assert staging.StagingStore(core.vault).load("revision-original")["status"] == "staged"


def test_sensitive_revision_cannot_bypass_the_source_sensitivity_gate(core):
    core.vault.set_setting("promotion", "mode", "agent")
    store = staging.StagingStore(core.vault)
    def sensitive():
        item = store.load("revision-original")
        item["sensitivity"] = "review"
        store.save(item)
    core._serialized("mark-sensitive", sensitive)
    reviewed = core.mcp_call("staging_show", {"item_id": "revision-original"}, tier="contribute")["result"]
    result = core.mcp_call("staging_decide", {"item_ids": ["revision-original"], "decision": "accept",
        "revision": reviewed["revision"], "staged_revision": reviewed["staged_revision"]}, tier="contribute")["result"]
    assert result["results"][0]["refused"] == "SENSITIVITY_REVIEW"
    assert store.load("revision-original")["status"] == "staged"


def test_staged_record_retargeted_while_permission_waits_is_refused(core):
    add_source(core.vault.root, "Other", "A separate accepted source which must not be changed.")
    core.vault.set_setting("promotion", "mode", "agent")
    reviewed = core.mcp_call("staging_show", {"item_id": "revision-original"}, tier="contribute")["result"]
    core.set_mode("ask")
    requests = queue.Queue()
    core.broker.subscribe(lambda event: requests.put(event) if event.get("type") == "permission_request" else None)
    result = []
    thread = threading.Thread(target=lambda: result.append(core.mcp_call("staging_decide", {
        "item_ids": ["revision-original"], "decision": "accept", "revision": reviewed["revision"],
        "staged_revision": reviewed["staged_revision"]}, tier="contribute")["result"]))
    thread.start()
    try:
        event = requests.get(timeout=3)
        def retarget():
            store = staging.StagingStore(core.vault)
            item = store.load("revision-original")
            item["revision_of"] = "Sources/repository/Other.md"
            store.save(item)
        core._serialized("retarget-staged-item", retarget)
        core.broker.answer(event["id"], "allow_once")
        thread.join(3)
        assert not thread.is_alive()
        assert result[0]["refused"] == "DOCUMENT_ACTIVE"
        assert "New source-stated" not in (core.vault.root / "Sources/repository/Other.md").read_text(encoding="utf-8")
    finally:
        core.broker.close("test cleanup")
        thread.join(3)


def test_two_queued_acceptances_cannot_reapply_one_revision(core, monkeypatch):
    spec = REGISTRY.get("staging_decide")
    barrier = threading.Barrier(2)
    def intent(ctx, kwargs):
        value = spec.intent(ctx, kwargs)
        barrier.wait(timeout=3)
        return value
    monkeypatch.setitem(REGISTRY._tools, "staging_decide", replace(spec, intent=intent))
    results = []
    threads = [threading.Thread(target=lambda: results.append(accept(core))) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive()
    assert sum(out.get("accepted", 0) for out in results) == 1
    assert sum(out.get("refused") == "DOCUMENT_ACTIVE" for out in results) == 1


def test_revision_sqlite_stays_on_core_and_file_write_stays_on_writer(core, monkeypatch):
    from resource_librarian.index import Index
    calls = []
    original_write = staging.atomic_write_text
    original_upsert = Index.upsert
    def no_direct(*args, **kwargs):
        pytest.fail("opened a second index")
    def write(*args, **kwargs):
        assert on_writer_thread()
        return original_write(*args, **kwargs)
    def upsert(index, *args, **kwargs):
        calls.append(threading.current_thread())
        return original_upsert(index, *args, **kwargs)
    monkeypatch.setattr(library, "Index", no_direct)
    monkeypatch.setattr(staging, "atomic_write_text", write)
    monkeypatch.setattr(Index, "upsert", upsert)
    reviewed = show(core)
    dry = core.person_call("staging_decide", {"item_ids": ["revision-original"], "decision": "accept", "dry_run": True})
    assert dry["would_accept"] == 1 and dry["results"][0]["would"] == "merge"
    assert accept(core, reviewed)["accepted"] == 1
    assert calls and set(calls) == {core.index_service._thread}


def test_closed_index_refuses_before_a_revision_mutates_markdown(core):
    reviewed = show(core)
    path = core.vault.root / reviewed["revision_of"]
    before = path.read_bytes()
    core.index_service.close()
    result = accept(core, reviewed)
    assert result["error"] == "failed" and "closed" in result["detail"]
    assert path.read_bytes() == before
    assert staging.StagingStore(core.vault).load("revision-original")["status"] == "staged"


@pytest.mark.parametrize("item_id", ["../outside", "x/../../outside", "C:\\outside", ".hidden"])
def test_staged_ids_cannot_read_or_write_other_paths(core, item_id):
    store = staging.StagingStore(core.vault)
    with pytest.raises(TypeError, match="plain filename"):
        store.load(item_id)
    with pytest.raises(TypeError, match="plain filename"):
        store.add({"id": item_id, "kind": "source", "name": "Bad"})


def test_corrupt_item_identity_cannot_redirect_an_accept(core):
    store = staging.StagingStore(core.vault)
    path = store.path("revision-original")
    item = store.load("revision-original")
    item["id"] = "another-item"
    path.write_text(json.dumps(item), encoding="utf-8")
    with pytest.raises(TypeError, match="identity"):
        store.load("revision-original")
    assert "error" in core.person_call("staging_show", {"item_id": "revision-original"})


@pytest.mark.parametrize("kind,target", [("concept", "Concepts/New term.md"),
                                         ("import", "Notes/Imported.md")])
def test_new_note_created_during_permission_wait_is_not_overwritten(core, kind, target):
    core.vault.set_setting("promotion", "mode", "agent")
    item = {"id": "new-item", "kind": kind, "name": "New term", "target": target,
            "frontmatter": {"type": "note"}, "body": "Imported text", "evidence": []}
    core._serialized("stage-test", lambda: staging.StagingStore(core.vault).add(item))
    core.set_mode("ask")
    requests, results = queue.Queue(), []
    core.broker.subscribe(lambda event: requests.put(event) if event.get("type") == "permission_request" else None)
    thread = threading.Thread(target=lambda: results.append(core.mcp_call("staging_decide", {
        "item_ids": ["new-item"], "decision": "accept",
        **({"fields": {"definition": "A person's definition."}} if kind == "concept" else {})},
        tier="contribute")["result"]))
    thread.start()
    try:
        event = requests.get(timeout=3)
        path = core.vault.root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("A newly created human note.\n", encoding="utf-8")
        core.broker.answer(event["id"], "allow_once")
        thread.join(3)
        assert not thread.is_alive()
        assert results[0]["refused"] == "DOCUMENT_ACTIVE"
        assert path.read_text(encoding="utf-8") == "A newly created human note.\n"
        assert staging.StagingStore(core.vault).load("new-item")["status"] == "staged"
    finally:
        core.broker.close("test cleanup")
        thread.join(3)


def test_attachment_changed_during_rejection_permission_wait_is_not_quarantined(core):
    source = core.vault.root / "Inbox" / "changing.pdf"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"reviewed bytes")
    item = {"id": "reject-changing", "kind": "source", "source_kind": "document",
            "name": "changing", "file": "Inbox/changing.pdf", "evidence": []}
    core._serialized("stage-test", lambda: staging.StagingStore(core.vault).add(item))
    core.set_mode("ask")
    requests, results = queue.Queue(), []
    core.broker.subscribe(lambda event: requests.put(event)
                          if event.get("type") == "permission_request" else None)
    thread = threading.Thread(target=lambda: results.append(core.mcp_call("staging_decide", {
        "item_ids": ["reject-changing"], "decision": "reject", "reason": "not relevant",
    }, tier="contribute")["result"]))
    thread.start()
    try:
        event = requests.get(timeout=3)
        source.write_bytes(b"changed after review")
        core.broker.answer(event["id"], "allow_once")
        thread.join(3)
        assert not thread.is_alive()
        assert results[0]["refused"] == "DOCUMENT_ACTIVE"
        assert source.read_bytes() == b"changed after review"
        assert staging.StagingStore(core.vault).load("reject-changing")["status"] == "staged"
        assert not (core.vault.work("quarantine") / "staging" / "reject-changing.json").exists()
    finally:
        core.broker.close("test cleanup")
        thread.join(3)


def test_partial_rejection_checks_and_reports_retained_original_attachments(core):
    source = core.vault.root / "Inbox" / "partial.pdf"
    clean = core.vault.work("staging") / "files" / "partial.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    clean.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"reviewed source")
    clean.write_text("reviewed text", encoding="utf-8")
    item = {"id": "reject-partial", "kind": "source", "source_kind": "document",
            "name": "partial", "status": "partial", "file": "Inbox/partial.pdf",
            "clean_file": ".librarian/staging/files/partial.md", "evidence": [],
            "promotion_progress": {"version": 1, "completed_paths": ["Sources/document/partial.md"]}}
    core._serialized("stage-test", lambda: staging.StagingStore(core.vault).add(item))
    core.set_mode("ask")
    requests, results = queue.Queue(), []
    core.broker.subscribe(lambda event: requests.put(event)
                          if event.get("type") == "permission_request" else None)
    thread = threading.Thread(target=lambda: results.append(core.mcp_call("staging_decide", {
        "item_ids": ["reject-partial"], "decision": "reject", "reason": "stop here",
    }, tier="contribute")["result"]))
    thread.start()
    try:
        event = requests.get(timeout=3)
        clean.write_text("changed after review", encoding="utf-8")
        core.broker.answer(event["id"], "allow_once")
        thread.join(3)
        assert not thread.is_alive()
        assert results[0]["refused"] == "DOCUMENT_ACTIVE"
        assert staging.StagingStore(core.vault).load("reject-partial")["status"] == "partial"

        core.set_mode("auto")
        rejected = core.person_call("staging_decide", {
            "item_ids": ["reject-partial"], "decision": "reject", "reason": "stop here",
        })["results"][0]
        assert rejected["originals_retained"] == [
            "Inbox/partial.pdf", ".librarian/staging/files/partial.md"]
        assert source.read_bytes() == b"reviewed source"
        assert clean.read_text(encoding="utf-8") == "changed after review"
    finally:
        core.broker.close("test cleanup")
        thread.join(3)


def test_internal_dependencies_do_not_open_public_hidden_file_access(core):
    from resource_librarian.coordination import operation_path, fingerprint, PreconditionChangedError
    state = ".librarian/staging/source/revision-original.json"
    path = operation_path(core.vault, state)
    assert path.is_file()
    with pytest.raises(Refusal):
        core.vault.safe_relative(state)
    for escape in (".git/config", ".librarian/../Notes/secret.md", ".librarian/C:/file",
                   ".librarian//file", ".librarian"):
        with pytest.raises(Refusal):
            operation_path(core.vault, escape)
    ctx = Context(vault=core.vault)
    expected = revisions.preconditions(ctx, revisions.WriteIntent((), observed=((state, fingerprint(path)),)), "")
    revisions.check_now(ctx, expected)
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(PreconditionChangedError):
        revisions.check_now(ctx, expected)


def test_staged_revision_token_cannot_authorize_a_note_write(core):
    reviewed = show(core)
    assert core.person_call("write_note", {"folder": "Notes", "name": "Own note", "body": "Original text"})["created"]
    result = core.person_call("edit_note", {"note": "Own note", "section": "Claims", "text": "Wrong token",
                                          "revision": reviewed["staged_revision"]})
    assert result["refused"] == "REVISION_REFUSED"


def test_staging_dependency_operation_log_remains_readable_after_restart(core):
    assert accept(core, show(core))["accepted"] == 1
    core.close_runtime()
    restarted = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        assert restarted.operation_recoveries == []
        assert restarted.person_call("write_note", {"folder": "Notes", "name": "After restart",
                                                    "body": "No spurious recovery block."})["created"]
    finally:
        restarted.close_runtime()
