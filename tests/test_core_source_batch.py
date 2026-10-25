"""Bulk source acceptance composes only its own guarded writes."""
import json
import queue
import threading

import pytest

from resource_librarian import notes, promote as promotion, staging
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.index import Index
from resource_librarian.keys import KeyStore
from resource_librarian.tools import library

from test_core_source_promotion import core, _copies, _originals, _source, _store  # noqa: F401


def _second(core, *, item_id="second", name="Second Widget", kind="document"):
    path = core.vault.root / f"Project/{item_id}/paper.pdf"
    path.parent.mkdir(parents=True)
    path.write_bytes(f"An original artifact for {name}".encode())
    core.writer.submit(lambda: _store(core).add({"id": item_id, "kind": "source", "name": name,
        "title": name, "source_kind": kind, "file": path.relative_to(core.vault.root).as_posix(),
        "review": {"draft": {"status": "ok", "bottom_line": f"{name} studies Widget failure recovery.",
                              "what_it_solves": f"Practical Widget data from {name}.", "model": "fixture-clerk"}},
        "sections": {"Claims": f"Evidence for {name}."}}))
    return path


def _accept(core, ids=None, **kwargs):
    return core.person_call("staging_decide", {"item_ids": ids or ["new-widget", "second"],
                                             "decision": "accept", **kwargs})


def _fail_at(core, monkeypatch, name):
    original = Index.upsert
    def upsert(self, path, **kw):
        result = original(self, path, **kw)
        if path == core.vault.root / f"Sources/document/{name}.md":
            raise OSError("a provider secret must not appear in an error")
        return result
    monkeypatch.setattr(Index, "upsert", upsert)


def test_batch_uses_core_and_writer_and_keeps_both_generated_links(core, monkeypatch):
    second = _second(core)
    sql = []
    original = Index.upsert
    def upsert(self, path, **kw):
        sql.append(threading.current_thread())
        return original(self, path, **kw)
    atomic = promotion.atomic_write_text
    def write(path, text):
        assert on_writer_thread()
        return atomic(path, text)
    def forbidden(*a, **kw):
        raise AssertionError("source batch created a direct SQLite engine")
    monkeypatch.setattr(Index, "upsert", upsert)
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    monkeypatch.setattr(library, "engine_for", forbidden)
    monkeypatch.setattr(library, "Index", forbidden)
    before = [p.read_bytes() for p in [*_originals(core), second]]
    out = _accept(core)
    assert out["accepted"] == 2, out
    assert set(sql) == {core.index_service._thread}
    assert [p.read_bytes() for p in [*_originals(core), second]] == before
    assert notes.load(_source(core)).frontmatter["file"].endswith("/paper.pdf")
    other = notes.load(core.vault.root / "Sources/document/Second Widget.md")
    assert other.frontmatter["file"].endswith("/paper (2).pdf")
    assert (core.vault.root / other.frontmatter["file"]).read_bytes() == second.read_bytes()
    assert len(_copies(core)) == 3
    for rel in ("Concepts/Widget.md", "Indexes/Topic - Unfiled.md"):
        text = (core.vault.root / rel).read_text(encoding="utf-8")
        assert "[[New Widget]]" in text and "[[Second Widget]]" in text
    assert "A person's own definition" in (core.vault.root / "Concepts/Widget.md").read_text(encoding="utf-8")
    events = [json.loads(s) for s in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    event = next(e for e in reversed(events) if "Sources/document/Second Widget.md" in e["targets"])
    assert "Sources/document/New Widget.md" in event["targets"]
    assert all(f".librarian/staging/source/{i}.json" in event["targets"] for i in ("new-widget", "second"))


def test_batch_preview_reserves_the_same_destinations_as_accept(core):
    _second(core)
    state = {i: _store(core).path(i).read_bytes() for i in ("new-widget", "second")}
    preview = _accept(core, dry_run=True)
    assert preview["would_accept"] == 2
    paths = [r["copies"][0]["destination"] for r in preview["results"]]
    assert paths == ["Sources/document/files/paper.pdf", "Sources/document/files/paper (2).pdf"]
    assert not _copies(core)
    assert all(_store(core).path(i).read_bytes() == raw for i, raw in state.items())
    out = _accept(core)
    assert out["accepted"] == 2, out
    assert [notes.load(core.vault.root / r["promotion"]["path"]).frontmatter["file"] for r in out["results"]] == paths


@pytest.mark.parametrize("kind", ["document", "repository"])
def test_duplicate_proposed_name_is_refused_before_its_attachment_copy(core, kind):
    _second(core, name="New Widget", kind=kind)
    out = _accept(core)
    assert out["accepted"] == 1 and out["results"][1]["refused"] == "UNIQUE_NOTE_NAMES", out
    assert len(_copies(core)) == 2  # Only the first source's raw and clean input.
    assert _store(core).load("second")["status"] == "staged"
    assert not (core.vault.root / "Sources/repository/files/paper.pdf").exists()


def test_bad_item_does_not_hide_a_valid_item_or_mutate_its_inputs(core):
    _second(core)
    core.writer.submit(lambda: _store(core).save({**_store(core).load("second"), "review": {}}))
    out = _accept(core, ["no-such-item", "second", "new-widget"])
    assert out["accepted"] == 1 and "error" in out["results"][0] and "error" in out["results"][1], out
    assert out["results"][2]["status"] == "accepted" and len(_copies(core)) == 2


@pytest.mark.parametrize("kind", ["prose", "fields"])
def test_batch_cannot_share_one_items_prose_or_fields(core, kind):
    _second(core)
    extra = {"bottom_line": "The same opinion."} if kind == "prose" else {"fields": {"coverage": "full"}}
    for dry_run in (True, False):
        out = _accept(core, dry_run=dry_run, **extra)
        assert out["error"] == "invalid_arguments", out
    assert not _copies(core)


def test_later_target_lease_blocks_before_first_source_is_written(core):
    _second(core)
    core.document_leases.heartbeat("Sources/document/Second Widget.md", editor="Obsidian", dirty=True)
    out = _accept(core)
    assert out["refused"] == "DOCUMENT_ACTIVE" and out["checkpoint"]["type"] == "write_conflict", out
    assert not _copies(core) and not _source(core).exists()


def test_edit_after_first_accept_reports_its_result_and_aborts_remaining_items(core, monkeypatch):
    second = _second(core)
    _second(core, item_id="third", name="Third Widget")
    original = promotion.atomic_write_text
    def write(path, text):
        result = original(path, text)
        if path == _store(core).path("new-widget") and '"status": "accepted"' in text:
            second.write_bytes(b"A human's newer second artifact")
        return result
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    out = _accept(core, ["new-widget", "second", "third"])
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert out["completed_results"][0]["status"] == "accepted"
    assert "Sources/document/New Widget.md" in out["completed_paths"]
    assert not (core.vault.root / "Sources/document/Second Widget.md").exists()
    assert not (core.vault.root / "Sources/document/Third Widget.md").exists()
    assert second.read_bytes() == b"A human's newer second artifact"
    assert _store(core).load("new-widget")["status"] == "accepted"
    assert len(_copies(core)) == 2


@pytest.mark.parametrize("failed", ["New Widget", "Second Widget"])
def test_caught_io_failure_retains_only_that_items_progress_and_other_items_can_finish(core, monkeypatch, failed):
    _second(core)
    with monkeypatch.context() as m:
        _fail_at(core, m, failed)
        out = _accept(core)
    assert out["accepted"] == 1, out
    failed_id, other = ("new-widget", "Second Widget") if failed == "New Widget" else ("second", "New Widget")
    progress = _store(core).load(failed_id)["promotion_progress"]
    assert f"Sources/document/{failed}.md" in progress["completed_paths"]
    assert f"Sources/document/{other}.md" not in progress["completed_paths"]
    assert "provider secret" not in str(out)
    core.close_runtime()
    restarted = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        out = _accept(restarted, [failed_id])
        assert out["accepted"] == 1, out
        assert len(_copies(restarted)) == 3
    finally:
        restarted.close_runtime()


def test_original_session_is_kept_per_source_not_shared_across_batch(core):
    from resource_librarian.session import SessionStore
    _second(core)
    session_ids = []
    def origins():
        for item_id in ("new-widget", "second"):
            origin = SessionStore(core.vault).new("explore").id
            session_ids.append(origin)
            item = _store(core).load(item_id)
            item["found_for"] = {"session": origin}
            _store(core).save(item)
    core.writer.submit(origins)
    out = _accept(core)
    assert out.get("accepted") == 2, out
    assert [notes.load(core.vault.root / r["promotion"]["path"]).frontmatter["session"] for r in out["results"]] == session_ids


@pytest.mark.parametrize("changed", ["attachment", "staged", "config"])
def test_one_permission_request_covers_only_unchanged_batch_inputs(core, changed):
    second = _second(core)
    core.vault.set_setting("promotion", "mode", "agent")
    core.set_mode("ask")
    events, results = queue.Queue(), []
    core.broker.subscribe(lambda e: events.put(e) if e.get("type") == "permission_request" else None)
    thread = threading.Thread(target=lambda: results.append(core.mcp_call("staging_decide", {
        "item_ids": ["new-widget", "second"], "decision": "accept"}, tier="contribute")["result"]))
    thread.start()
    try:
        request = events.get(timeout=5)
        if changed == "attachment":
            second.write_bytes(b"A different input")
        elif changed == "staged":
            core.writer.submit(lambda: _store(core).save({**_store(core).load("second"), "name": "A different proposed source"}))
        else:
            core.vault.set_setting("promotion", "mode", "person")
        core.broker.answer(request["id"], "allow_once")
        thread.join(5)
        assert not thread.is_alive()
        assert results[0]["refused"] == "DOCUMENT_ACTIVE", results
        assert events.empty() and not _copies(core) and not _source(core).exists()
    finally:
        core.broker.close("test cleanup")
        thread.join(5)


def test_unrelated_edit_does_not_block_bulk_source_acceptance(core):
    _second(core)
    core.document_leases.heartbeat("Project/docs/working.md", editor="Obsidian", dirty=True)
    assert _accept(core)["accepted"] == 2


def test_oversized_combined_plan_refuses_before_mutation(core, monkeypatch):
    _second(core)
    original = staging.prepare_source
    def oversized(*a, **kw):
        plan = original(*a, **kw)
        plan["observed"].extend((f"Project/extra-{plan['item_id']}-{n}.md", "missing") for n in range(100))
        return plan
    monkeypatch.setattr(staging, "prepare_source", oversized)
    out = _accept(core)
    assert out["error"] == "invalid_arguments" and "200-file" in out["detail"], out
    assert not _copies(core)


def test_change_to_shared_dependency_during_preparation_is_not_rebased(core, monkeypatch):
    _second(core)
    original = staging.prepare_source
    changed = []
    def prepare(*a, **kw):
        plan = original(*a, **kw)
        if not changed:
            path = core.vault.root / "Concepts/Widget.md"
            path.write_text(path.read_text(encoding="utf-8") + "\nA newer human definition.\n", encoding="utf-8")
            changed.append(path)
        return plan
    monkeypatch.setattr(staging, "prepare_source", prepare)
    out = _accept(core)
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert not _copies(core)
    assert "newer human definition" in changed[0].read_text(encoding="utf-8")


def test_two_queued_batches_cannot_reapply_the_same_items(core, monkeypatch):
    from dataclasses import replace
    from resource_librarian.registry import REGISTRY
    _second(core)
    spec = REGISTRY.get("staging_decide")
    barrier = threading.Barrier(2)
    def intent(ctx, args):
        plan = spec.intent(ctx, args)
        barrier.wait(timeout=5)
        return plan
    monkeypatch.setitem(REGISTRY._tools, "staging_decide", replace(spec, intent=intent))
    results = []
    threads = [threading.Thread(target=lambda: results.append(_accept(core))) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(8)
    assert all(not thread.is_alive() for thread in threads)
    assert sorted(r.get("accepted", 0) for r in results) == [0, 2], results
    assert sum(r.get("refused") == "DOCUMENT_ACTIVE" for r in results) == 1
    assert len(_copies(core)) == 3


def test_duplicate_item_ids_report_second_decision_without_recopying(core):
    preview = _accept(core, ["new-widget", "new-widget"], dry_run=True)
    assert preview["would_accept"] == 1 and not preview["results"][1]["ok"], preview
    out = _accept(core, ["new-widget", "new-widget"])
    assert out["accepted"] == 1 and out["results"][1].get("error"), out
    assert len(_copies(core)) == 2


def test_missing_origin_does_not_invent_a_session_or_hide_accepted_results(core):
    from resource_librarian.session import SessionStore
    _second(core)
    core.writer.submit(lambda: _store(core).save({**_store(core).load("new-widget"),
                                               "found_for": {"session": "missing-origin"}}))
    out = _accept(core)
    assert out["accepted"] == 2, out
    assert out["results"][0]["handoff_warning"]["error"] == "SESSION_REQUIRED"
    assert not SessionStore(core.vault).path("missing-origin").exists()
    assert notes.load(_source(core)).frontmatter["session"] == "missing-origin"


def test_stopped_index_between_items_retains_results_and_never_copies_later_inputs(core, monkeypatch):
    _second(core)
    _second(core, item_id="third", name="Third Widget")
    original = promotion.atomic_write_text
    def write(path, text):
        result = original(path, text)
        if path == _store(core).path("new-widget") and '"status": "accepted"' in text:
            core.index_service.close()
        return result
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    out = _accept(core, ["new-widget", "second", "third"])
    assert out["accepted"] == 1, out
    assert "RuntimeError" in out["results"][1]["error"]
    assert out["results"][2]["error"].startswith("not run")
    assert len(_copies(core)) == 2
    assert not (core.vault.root / "Sources/document/Second Widget.md").exists()
