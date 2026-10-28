"""Single-source acceptance uses copied plans, the Core index and guarded files."""
import json
import queue
import threading

import pytest

from resource_librarian import embed, notes, promote as promotion, staging
from resource_librarian.app import App
from resource_librarian.coordination import fingerprint, fingerprint_bytes, on_writer_thread
from resource_librarian.index import Index
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.tools import library

from conftest import add_source, write_note


@pytest.fixture
def core(vault):
    write_note(vault.root, "Concepts/Widget.md", "type: concept\nstatus: active",
               "# Widget\n\n## Definition\nA person's own definition.\n")
    for n in range(4):
        add_source(vault.root, f"other-{n}", f"An unrelated topic {n}.")
    raw = vault.root / "Project/docs/paper.pdf"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"%PDF-1.4\r\n\x00Original project artifact\xff")
    clean = vault.work("staging") / "files/paper.md"
    clean.parent.mkdir(parents=True, exist_ok=True)
    clean.write_bytes(b"# Widget paper\r\n\r\nClean text remains unchanged.\n")
    staging.StagingStore(vault).add({"id": "new-widget", "kind": "source", "name": "New Widget",
        "source_kind": "document", "title": "Widget field study", "canonical_url": "https://example.org/paper",
        "file": "Project/docs/paper.pdf", "clean_file": ".librarian/staging/files/paper.md",
        "review": {"draft": {"status": "ok", "bottom_line": "Widget field study measures practical effects.",
                              "what_it_solves": "Evidence for evaluating Widget.", "model": "fixture-clerk"}},
        "sections": {"Claims": "Source-stated claims, not an endorsement."}, "evidence": []})
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    try:
        yield app
    finally:
        app.close_runtime()


def _store(core):
    return staging.StagingStore(core.vault)


def _accept(core, **kwargs):
    return core.person_call("staging_decide", {"item_ids": ["new-widget"], "decision": "accept", **kwargs})


def _change(core, fn):
    def change():
        store = _store(core)
        item = store.load("new-widget")
        fn(item)
        store.save(item)
    core.writer.submit(change)


def _source(core):
    return core.vault.root / "Sources/document/New Widget.md"


def _copies(core):
    return list((core.vault.root / "Sources/document/files").glob("*"))


def _originals(core):
    return [core.vault.root / "Project/docs/paper.pdf", core.vault.work("staging") / "files/paper.md"]


def test_source_accept_owns_sql_and_files_and_copies_without_relocating_inputs(core, monkeypatch):
    sql, files = [], []
    upsert, atomic = Index.upsert, promotion.atomic_write_text
    def indexed(self, path, **kw):
        sql.append(threading.current_thread())
        return upsert(self, path, **kw)
    def write(path, text):
        assert on_writer_thread()
        files.append(path)
        return atomic(path, text)
    def forbidden(*a, **kw):
        raise AssertionError("a serving source promotion opened another Index")
    monkeypatch.setattr(Index, "upsert", indexed)
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    monkeypatch.setattr(library, "Index", forbidden)
    originals = [p.read_bytes() for p in _originals(core)]
    out = _accept(core)
    assert out["accepted"] == 1, out
    assert files and set(sql) == {core.index_service._thread}
    assert [p.read_bytes() for p in _originals(core)] == originals
    note = notes.load(_source(core))
    assert note.frontmatter["file"] == "Sources/document/files/paper.pdf"
    assert note.frontmatter["file_markdown"] == "Sources/document/files/paper (clean text).md"
    assert "needs_attention" not in note.frontmatter
    assert "Source-stated claims, not an endorsement." in note.body
    assert [p.read_bytes() for p in sorted(_copies(core), key=lambda p: p.suffix, reverse=True)] == originals
    assert _store(core).load("new-widget")["sections"]["Claims"].startswith("Source-stated")
    concept = (core.vault.root / "Concepts/Widget.md").read_text(encoding="utf-8")
    assert "A person's own definition" in concept and "[[New Widget]]" in concept
    operations = [json.loads(s) for s in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    done = next(o for o in reversed(operations) if o["status"] == "done" and
                "Sources/document/New Widget.md" in o["targets"])
    assert ".librarian/staging/source/new-widget.json" in done["targets"]
    assert set(out["results"][0]["originals_retained"]) == {
        "Project/docs/paper.pdf", ".librarian/staging/files/paper.md"}
    assert all(p in done["precondition_fingerprints"] for p in out["results"][0]["originals_retained"])


def test_source_encoder_releases_writer_and_reconciles_public_result(core, monkeypatch):
    np = pytest.importorskip("numpy")
    core.set_service("embeddings", "hash", "16")
    entered, release, unrelated = threading.Event(), threading.Event(), threading.Event()

    def encode(texts):
        assert not on_writer_thread()
        entered.set()
        assert release.wait(5)
        return np.ones((len(texts), 16), dtype="float32")

    monkeypatch.setattr(embed, "load_embedding_encoders",
                        lambda spec, **kw: ("hash:16", encode, encode, {}))
    accepted = []
    worker = threading.Thread(target=lambda: accepted.append(_accept(core)), daemon=True)
    worker.start()
    assert entered.wait(5)
    assert notes.load(_source(core)).frontmatter["needs_attention"] == promotion.EMBEDDING_PENDING
    other = threading.Thread(target=lambda: core.writer.submit(
        lambda: unrelated.set(), caller="unrelated-during-embedding"), daemon=True)
    other.start()
    try:
        assert unrelated.wait(1), "encoder IO still occupied the sole vault writer"
    finally:
        release.set()
        worker.join(10)
        other.join(10)
    assert not worker.is_alive() and accepted[0]["accepted"] == 1
    report = accepted[0]["results"][0]["promotion"]
    assert report["steps"]["index"]["detail"]["vectors"].endswith("chunk(s) embedded")
    assert "needs_attention" not in notes.load(_source(core)).frontmatter
    assert _store(core).load("new-widget")["promotion"] == report
    operations = [json.loads(row) for row in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    assert all("_post_write" not in op.get("result", {}).get("keys", []) for op in operations)


def test_source_embedding_failure_is_nonfatal_truthful_and_persisted(core, monkeypatch):
    pytest.importorskip("numpy")
    core.set_service("embeddings", "hash", "16")

    def fail(_texts):
        raise RuntimeError("private-provider-detail")

    monkeypatch.setattr(embed, "load_embedding_encoders",
                        lambda spec, **kw: ("hash:16", fail, fail, {}))
    out = _accept(core)
    assert out["accepted"] == 1 and out["not_findable"] == ["new-widget"]
    report = out["results"][0]["promotion"]
    assert not report["catalogued"]
    assert "embedding update failed (RuntimeError)" in report["steps"]["index"]["detail"]["vectors"]
    assert "embedding update failed" in notes.load(_source(core)).frontmatter["needs_attention"]
    assert _store(core).load("new-widget")["promotion"] == report
    assert "private-provider-detail" not in json.dumps(out)


def test_embedding_failure_does_not_overwrite_edit_after_publication(core, monkeypatch):
    pytest.importorskip("numpy")
    core.set_service("embeddings", "hash", "16")
    entered, release = threading.Event(), threading.Event()

    def fail(_texts):
        assert not on_writer_thread()
        entered.set()
        assert release.wait(5)
        raise RuntimeError("late failure")

    monkeypatch.setattr(embed, "load_embedding_encoders",
                        lambda spec, **kw: ("hash:16", fail, fail, {}))
    accepted = []
    worker = threading.Thread(target=lambda: accepted.append(_accept(core)), daemon=True)
    worker.start()
    assert entered.wait(5) and _source(core).is_file()
    human = _source(core).read_text(encoding="utf-8") + "\n\nHuman edit after publication.\n"
    _source(core).write_text(human, encoding="utf-8")
    release.set()
    worker.join(10)
    assert not worker.is_alive()
    assert _source(core).read_text(encoding="utf-8") == human
    result = accepted[0]["results"][0]
    assert result["promotion"]["catalogued"] is False
    assert any(w["stage"] == "source_attention" for w in result["embedding_warnings"])
    assert _store(core).load("new-widget")["promotion"] == result["promotion"]


def test_nested_post_write_tool_is_refused_before_source_mutation(core):
    ctx = Context(tier="curate", vault=core.vault,
                  extras={**core._extras(), "caller_kind": "person"})
    out = core.writer.submit(lambda: REGISTRY.call("staging_decide", {
        "item_ids": ["new-widget"], "decision": "accept"}, ctx), caller="nested-test")
    assert out["refused"] == "POST_WRITE_CONTEXT"
    assert not _source(core).exists() and _store(core).load("new-widget")["status"] == "staged"


def test_post_write_crash_window_leaves_authoritative_pending_marker(core, monkeypatch):
    core.set_service("embeddings", "hash", "16")
    from resource_librarian.tools import staging as staging_tools

    def crash(_self, _aggregate):
        raise RuntimeError("continuation fixture")

    monkeypatch.setattr(staging_tools._StagingEmbeddingContinuation, "finish", crash)
    out = _accept(core)
    assert out["accepted"] == 1 and out["post_write_warning"]["error"] == "RuntimeError"
    assert notes.load(_source(core)).frontmatter["needs_attention"] == promotion.EMBEDDING_PENDING
    saved = _store(core).load("new-widget")["promotion"]
    assert saved["steps"]["index"]["detail"]["vectors"] == "pending writer release"


def test_dry_run_predicts_copies_without_changing_files_or_staged_json(core):
    before = _store(core).path("new-widget").read_bytes()
    out = _accept(core, dry_run=True)
    assert out["would_accept"] == 1, out
    assert out["results"][0]["file"] == "Sources/document/files/paper.pdf"
    assert out["results"][0]["sections"] == ["Claims"]
    assert not _copies(core) and not _source(core).exists()
    assert _store(core).path("new-widget").read_bytes() == before


@pytest.mark.parametrize("fault", ["duplicate", "kind", "draft", "field", "missing"])
def test_preflight_failure_never_copies_an_attachment(core, fault):
    if fault == "duplicate":
        add_source(core.vault.root, "New Widget", "A different source with the same name.")
    elif fault == "kind":
        _change(core, lambda i: i.update(source_kind="../../outside"))
    elif fault == "draft":
        _change(core, lambda i: i.update(review={}))
    elif fault == "missing":
        _change(core, lambda i: i.update(file="Project/docs/missing.pdf"))
    out = _accept(core, **({"fields": {"not_a_real_field": True}} if fault == "field" else {}))
    assert out["accepted"] == 0 and not _copies(core), out
    assert all(p.exists() for p in _originals(core))
    assert _store(core).load("new-widget")["status"] == "staged"


def test_existing_attachment_destination_is_not_replaced(core):
    dest = core.vault.root / "Sources/document/files/paper.pdf"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"Another source's attachment")
    assert _accept(core)["accepted"] == 1
    assert dest.read_bytes() == b"Another source's attachment"
    assert notes.load(_source(core)).frontmatter["file"].endswith("paper (2).pdf")


@pytest.mark.parametrize("target", ["Concepts/Widget.md", "Indexes/Master Index.md", "Sources/document/New Widget.md"])
def test_human_target_lease_blocks_before_any_copy(core, target):
    core.document_leases.heartbeat(target, editor="Obsidian", dirty=True)
    out = _accept(core)
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert out["checkpoint"]["type"] == "write_conflict"
    assert not _copies(core) and not _source(core).exists()


def test_unrelated_note_stays_editable_during_acceptance(core):
    core.document_leases.heartbeat("Project/docs/working.md", editor="Obsidian", dirty=True)
    assert _accept(core)["accepted"] == 1


@pytest.mark.parametrize("rel", [".librarian/config.toml", ".git/config", "../outside.pdf"])
def test_hidden_state_and_outside_paths_cannot_be_attachment_inputs(core, rel):
    _change(core, lambda i: i.update(file=rel))
    out = _accept(core)
    assert out.get("error") or out.get("accepted") == 0, out
    assert not _copies(core) and not _source(core).exists()


@pytest.mark.parametrize("change", ["attachment", "staged", "dik", "destination"])
def test_preconditions_survive_permission_wait(core, change):
    core.vault.set_setting("promotion", "mode", "agent")
    core.set_mode("ask")
    events, results = queue.Queue(), []
    core.broker.subscribe(lambda e: events.put(e) if e.get("type") == "permission_request" else None)
    thread = threading.Thread(target=lambda: results.append(core.mcp_call("staging_decide", {
        "item_ids": ["new-widget"], "decision": "accept"}, tier="contribute")["result"]))
    thread.start()
    try:
        event = events.get(timeout=5)
        if change == "attachment":
            _originals(core)[0].write_bytes(b"A newer project artifact")
        elif change == "staged":
            _change(core, lambda i: i.update(name="Other source"))
        elif change == "dik":
            from resource_librarian import dik
            path = dik.path_for(core.vault, "New Widget")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}", encoding="utf-8")
        else:
            path = core.vault.root / "Sources/document/files/paper.pdf"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"A person's new artifact")
        core.broker.answer(event["id"], "allow_once")
        thread.join(5)
        assert not thread.is_alive()
        assert results[0]["refused"] == "DOCUMENT_ACTIVE", results
        assert not _source(core).exists()
        assert len(_copies(core)) == (1 if change == "destination" else 0)
    finally:
        core.broker.close("test cleanup")
        thread.join(5)


def _interrupt(core, monkeypatch, phase="source", **kwargs):
    if phase == "copy":
        original = promotion.PromotionGuard.copy
        def copy(self, source, destination):
            original(self, source, destination)
            raise OSError("private failure details should not escape")
        monkeypatch.setattr(promotion.PromotionGuard, "copy", copy)
    else:
        original = Index.upsert
        def upsert(self, path, **kw):
            result = original(self, path, **kw)
            if path == _source(core):
                raise OSError("private failure details should not escape")
            return result
        monkeypatch.setattr(Index, "upsert", upsert)
    out = _accept(core, **kwargs)
    assert not out["accepted"] and "private failure" not in str(out), out
    assert _store(core).load("new-widget")["promotion_progress"]["completed_paths"]
    return out


@pytest.mark.parametrize("phase", ["copy", "source"])
@pytest.mark.parametrize("prose", ["reviewed", "person"])
def test_interrupted_acceptance_can_be_explicitly_finished_after_restart(core, monkeypatch, phase, prose):
    if prose == "person":
        # A person-authored approval must not acquire a fictitious clerk author
        # when the UI presents its saved text on the next attempt.
        _change(core, lambda i: i.update(review={}))
    with monkeypatch.context() as m:
        _interrupt(core, m, phase, **({"bottom_line": "My own reading.",
                                     "what_it_solves": "My own use case."} if prose == "person" else {}))
    before = {p.name: p.read_bytes() for p in _copies(core)}
    if phase == "source":
        assert "promotion incomplete" in notes.load(_source(core)).frontmatter["needs_attention"]
    core.close_runtime()
    replacement = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        reviewed = replacement.person_call("staging_show", {"item_id": "new-widget"})
        out = _accept(replacement, staged_revision=reviewed["staged_revision"],
                      bottom_line=reviewed["review"]["draft"]["bottom_line"],
                      what_it_solves=reviewed["review"]["draft"]["what_it_solves"],
                      **({"revision": reviewed["revision"]} if reviewed.get("revision") else {}))
        assert out.get("accepted") == 1, out
        assert len(_copies(core)) == 2
        assert all((core.vault.root / "Sources/document/files" / name).read_bytes() == data
                   for name, data in before.items())
        assert all(p.exists() for p in _originals(core))
        assert _store(core).load("new-widget")["promotion_progress"]["completed_at"]
        assert "needs_attention" not in notes.load(_source(core)).frontmatter
        if prose == "person":
            assert "drafted_by" not in notes.load(_source(core)).frontmatter
    finally:
        replacement.close_runtime()


@pytest.mark.parametrize("change", ["note", "draft", "attachment", "copy"])
def test_interrupted_work_never_overwrites_later_edits(core, monkeypatch, change):
    with monkeypatch.context() as m:
        _interrupt(core, m)
    if change == "note":
        _source(core).write_text(_source(core).read_text(encoding="utf-8") + "\nHuman annotation.\n", encoding="utf-8")
    elif change == "attachment":
        _originals(core)[0].write_bytes(b"Changed input")
    elif change == "copy":
        _copies(core)[0].write_bytes(b"Changed retained copy")
    note_before = _source(core).read_bytes()
    copies_before = {p.name: p.read_bytes() for p in _copies(core)}
    out = _accept(core, **({"bottom_line": "A new interpretation."} if change == "draft" else {}))
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert _source(core).read_bytes() == note_before
    assert {p.name: p.read_bytes() for p in _copies(core)} == copies_before


@pytest.mark.parametrize("decision", ["reject", "defer"])
def test_reject_or_defer_does_not_undo_partial_copies_or_move_originals(core, monkeypatch, decision):
    with monkeypatch.context() as m:
        _interrupt(core, m)
    note_before = _source(core).read_bytes()
    copies_before = {p.name: p.read_bytes() for p in _copies(core)}
    out = core.person_call("staging_decide", {"item_ids": ["new-widget"], "decision": decision,
                                            "reason": "Needs independent review."})
    assert out["results"][0]["status"] == ("rejected" if decision == "reject" else "deferred"), out
    assert _source(core).read_bytes() == note_before
    assert {p.name: p.read_bytes() for p in _copies(core)} == copies_before
    assert all(p.exists() for p in _originals(core))


def test_partial_work_cannot_be_reapproved_redrafted_or_accepted_as_a_batch(core, monkeypatch):
    with monkeypatch.context() as m:
        _interrupt(core, m)
    assert core.person_call("staging_decide", {"item_ids": ["new-widget"], "decision": "approve"})["accepted"] == 0
    assert core.person_call("staging_review", {"item_id": "new-widget"})["error"] == "invalid_arguments"
    core.writer.submit(lambda: _store(core).add({"id": "other", "kind": "source", "name": "Another",
        "source_kind": "document", "review": {"draft": {"status": "ok", "bottom_line": "Another."}}}))
    out = core.person_call("staging_decide", {"item_ids": ["new-widget", "other"], "decision": "accept"})
    assert out["results"][0].get("error"), out


def test_agent_cannot_resume_interrupted_person_promotion_even_in_agent_mode(core, monkeypatch):
    with monkeypatch.context() as m:
        _interrupt(core, m)
    core.vault.set_setting("promotion", "mode", "agent")
    out = core.mcp_call("staging_decide", {"item_ids": ["new-widget"], "decision": "accept"},
                        tier="contribute")["result"]
    assert out["results"][0]["refused"] == "PERSON_CONFIRMS", out


@pytest.mark.parametrize("closed", ["writer", "index"])
def test_closed_core_does_not_fallback_to_direct_acceptance(core, closed):
    (core.writer if closed == "writer" else core.index_service).close()
    ctx = Context(tier="curate", vault=core.vault, extras={"index_service": core.index_service,
        "vault_writer": core.writer, "caller_kind": "person"})
    out = REGISTRY.call("staging_decide", {"item_ids": ["new-widget"], "decision": "accept"}, ctx)
    assert out.get("error"), out
    assert not _copies(core) and not _source(core).exists()


def test_streaming_fingerprint_matches_existing_contract(tmp_path, monkeypatch):
    data = b"\x00\xff\r\n" * (1 << 20)
    path = tmp_path / "artifact.bin"
    path.write_bytes(data)
    def forbidden(*a, **kw):
        raise AssertionError("fingerprint loaded a whole attachment")
    monkeypatch.setattr(type(path), "read_bytes", forbidden)
    assert fingerprint(path) == fingerprint_bytes(data)


@pytest.mark.parametrize("sensitive", [False, True])
def test_person_and_sensitivity_gates_apply_before_copies(core, sensitive):
    if sensitive:
        core.vault.set_setting("promotion", "mode", "agent")
        _change(core, lambda i: i.update(sensitivity="review"))
    out = core.mcp_call("staging_decide", {"item_ids": ["new-widget"], "decision": "accept"},
                        tier="contribute")["result"]
    assert out["results"][0]["refused"] == ("SENSITIVITY_REVIEW" if sensitive else "PERSON_CONFIRMS"), out
    assert not _copies(core)


def test_progress_does_not_overwrite_staged_human_edits_on_failure(core, monkeypatch):
    original = Index.upsert
    human = []
    def upsert(self, path, **kw):
        result = original(self, path, **kw)
        if path == _source(core):
            item = _store(core).load("new-widget")
            item["title"] = "A new title entered outside the Core."
            _store(core).save(item)
            human.append(_store(core).path("new-widget").read_bytes())
            raise OSError("failed after a concurrent human edit")
        return result
    monkeypatch.setattr(Index, "upsert", upsert)
    out = _accept(core)
    assert out["results"][0]["completed_paths"]
    assert _store(core).path("new-widget").read_bytes() == human[0]
    assert "promotion_progress" not in _store(core).load("new-widget")


def test_attachment_change_during_streaming_does_not_publish_or_leave_temp_files(core, monkeypatch):
    from resource_librarian.rules import Refusal
    source = _originals(core)[0]
    target = "Sources/document/files/streamed.pdf"
    rel = source.relative_to(core.vault.root).as_posix()
    guard = promotion.PromotionGuard(core.vault, {"targets": [target],
        "observed": [(rel, fingerprint(source)), (target, "missing")]})
    # A mutation between streamed read and publication must reject the whole
    # new copy, leaving an existing input and no published partial file.
    monkeypatch.setattr(promotion.os, "fsync", lambda fd: source.write_bytes(b"New project content"))
    with pytest.raises(Refusal):
        guard.copy(rel, target)
    folder = core.vault.root / "Sources/document/files"
    assert not list(folder.iterdir())
    assert source.read_bytes() == b"New project content"


def test_retained_copy_path_cannot_be_retargeted_to_a_project_document(core, monkeypatch):
    with monkeypatch.context() as m:
        _interrupt(core, m)
    _change(core, lambda i: i["promotion_progress"]["copies"][0].update(destination="Project/docs/paper.pdf"))
    before = _source(core).read_bytes()
    out = _accept(core)
    assert out["accepted"] == 0 and "source kind's files folder" in str(out), out
    assert _source(core).read_bytes() == before


def test_hidden_staging_attachment_redirect_cannot_read_configuration(core, monkeypatch):
    from resource_librarian import coordination
    original = coordination.operation_path
    def redirected(vault, rel):
        if rel == ".librarian/staging/files/redirect.md":
            return vault.config_path
        return original(vault, rel)
    monkeypatch.setattr(coordination, "operation_path", redirected)
    _change(core, lambda i: i.update(clean_file=".librarian/staging/files/redirect.md"))
    out = _accept(core)
    assert out["accepted"] == 0 and "inside staging/files" in str(out), out
    assert not _copies(core)


def test_visible_attachment_alias_cannot_resolve_into_hidden_state(core, monkeypatch):
    from resource_librarian.vault import Vault
    original = Vault.safe_relative
    def redirected(vault, rel):
        if rel == "Project/docs/redirect.pdf":
            return vault.config_path
        return original(vault, rel)
    monkeypatch.setattr(Vault, "safe_relative", redirected)
    _change(core, lambda i: i.update(file="Project/docs/redirect.pdf"))
    out = _accept(core)
    assert out["accepted"] == 0 and "hidden vault state" in str(out), out
    assert not _copies(core)
