"""Ordered mixed acceptance replans only inside its reviewed file footprint."""
import json
import queue
import threading

import pytest

from resource_librarian import notes, promote as promotion, staging, taxonomy
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.index import Index
from resource_librarian.keys import KeyStore
from resource_librarian.tools import library

from test_core_source_promotion import core, _copies, _originals, _source, _store  # noqa: F401


def _topic(core, item_id="topic-a", name="Alpha Studies", members=None):
    core.writer.submit(lambda: _store(core).add({"id": item_id, "kind": "topic", "name": name,
        "what_belongs": f"Evidence for {name}", "members": ["other-0"] if members is None else members}))
    return item_id


def _import(core, item_id="import-a", target="Notes/Imported.md", fm=None, body="# Imported\n\nOriginal prose."):
    core.writer.submit(lambda: _store(core).add({"id": item_id, "kind": "import", "name": "Imported",
        "target": target, "frontmatter": fm or {"type": "note"}, "body": body, "evidence": []}))
    return item_id


def _accept(core, ids, **kwargs):
    return core.person_call("staging_decide", {"item_ids": ids, "decision": "accept", **kwargs})


def _topic_of(core, name):
    return notes.load(core.vault.root / f"Sources/repository/{name}.md").frontmatter["primary_topic"]


def test_two_topics_keep_both_rows_and_use_core_sql_and_writer_effects(core, monkeypatch):
    a, b = _topic(core), _topic(core, "topic-b", "Beta Studies", ["other-1"])
    original, atomic, sql = Index.upsert, promotion.atomic_write_text, []
    def upsert(self, path, **kw):
        sql.append(threading.current_thread())
        return original(self, path, **kw)
    def write(path, text):
        assert on_writer_thread()
        return atomic(path, text)
    def forbidden(*a, **kw):
        raise AssertionError("mixed acceptance constructed a second SQLite index")
    monkeypatch.setattr(Index, "upsert", upsert)
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    monkeypatch.setattr(library, "Index", forbidden)
    out = _accept(core, [a, b])
    assert out.get("accepted") == 2, json.dumps(out, indent=2)
    assert set(sql) == {core.index_service._thread}
    assert {"Alpha Studies", "Beta Studies"} <= set(core.vault.topics())
    assert _topic_of(core, "other-0") == "Alpha Studies"
    assert _topic_of(core, "other-1") == "Beta Studies"
    events = [json.loads(s) for s in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    event = next(e for e in reversed(events) if "Sources/repository/other-1.md" in e["targets"])
    assert "Sources/repository/other-0.md" in event["targets"]
    assert all(f".librarian/staging/topic/{i}.json" in event["targets"] for i in (a, b))


def test_two_topics_refiling_same_source_preserve_prose_and_order(core):
    a, b = _topic(core), _topic(core, "topic-b", "Beta Studies", ["other-0"])
    out = _accept(core, [a, b])
    assert out.get("accepted") == 2, json.dumps(out, indent=2)
    assert _topic_of(core, "other-0") == "Beta Studies"
    assert "An unrelated topic 0" in (core.vault.root / "Sources/repository/other-0.md").read_text(encoding="utf-8")
    assert "[[other-0]]" not in (core.vault.root / "Indexes/Topic - Alpha Studies.md").read_text(encoding="utf-8")
    assert "[[other-0]]" in (core.vault.root / "Indexes/Topic - Beta Studies.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("topic_first", [False, True])
def test_source_and_topic_use_explicit_order_with_original_inputs_retained(core, topic_first):
    a = _topic(core, members=["New Widget"])
    if topic_first:
        core.writer.submit(lambda: _store(core).save({**_store(core).load("new-widget"), "topic": "Alpha Studies"}))
    originals = [p.read_bytes() for p in _originals(core)]
    out = _accept(core, [a, "new-widget"] if topic_first else ["new-widget", a])
    assert out.get("accepted") == 2, json.dumps(out, indent=2)
    assert notes.load(_source(core)).frontmatter["primary_topic"] == "Alpha Studies"
    assert [p.read_bytes() for p in _originals(core)] == originals
    assert len(_copies(core)) == 2
    topic_result = out["results"][0 if topic_first else 1]
    assert bool(topic_result["refiled"][0].get("error")) == topic_first


def test_imported_source_can_be_refiled_later_in_same_reviewed_batch(core):
    i = _import(core, target="Sources/repository/Imported.md", fm={"type": "source", "kind": "repository", "primary_topic": "Unfiled"})
    a = _topic(core, members=["Imported"])
    out = _accept(core, [i, a])
    assert out.get("accepted") == 2, out
    assert _topic_of(core, "Imported") == "Alpha Studies"
    assert "Original prose." in (core.vault.root / "Sources/repository/Imported.md").read_text(encoding="utf-8")


def test_imported_concept_backlinks_are_within_explicitly_approved_scope(core):
    i = _import(core, target="Concepts/Fault Recovery.md", fm={"type": "concept", "status": "active"},
                body="# Fault Recovery\n\n## Definition\nMy explicit imported definition.\n")
    def wording():
        item = _store(core).load("new-widget")
        item["review"]["draft"]["bottom_line"] = "Widget field study explains Fault Recovery."
        _store(core).save(item)
    core.writer.submit(wording)
    out = _accept(core, [i, "new-widget"])
    assert out.get("accepted") == 2, out
    concept = (core.vault.root / "Concepts/Fault Recovery.md").read_text(encoding="utf-8")
    assert "My explicit imported definition" in concept and "[[New Widget]]" in concept


@pytest.mark.parametrize("dependency_only", [False, True])
def test_replanning_cannot_expand_approved_targets_or_dependencies(core, monkeypatch, dependency_only):
    a = _topic(core)
    original, calls = staging.prepare_source, []
    def prepare(*args, **kwargs):
        plan = original(*args, **kwargs)
        calls.append(True)
        if len(calls) > 1:
            plan["observed"].append(("Notes/Not Approved.md", "missing"))
            if not dependency_only:
                plan["targets"].append("Notes/Not Approved.md")
        return plan
    monkeypatch.setattr(staging, "prepare_source", prepare)
    out = _accept(core, [a, "new-widget"])
    assert out.get("refused") == "DOCUMENT_ACTIVE", out
    assert out["completed_results"][0]["status"] == "accepted"
    assert out["checkpoint"]["type"] == "write_conflict"
    assert not _copies(core) and not _source(core).exists()


def test_revision_then_topic_preserves_new_claims_during_refiling(core):
    core.writer.submit(lambda: _store(core).add({"id": "rev-a", "kind": "source", "name": "other-0",
        "revision_of": "Sources/repository/other-0.md", "sections": {"Claims": "A newly reviewed claim."}}))
    a = _topic(core)
    out = _accept(core, ["rev-a", a])
    assert out.get("accepted") == 2, out
    note = notes.load(core.vault.root / "Sources/repository/other-0.md")
    assert "newly reviewed claim" in note.sections()["Claims"]
    assert note.frontmatter["primary_topic"] == "Alpha Studies"


def test_agent_does_not_gain_taxonomy_authority_from_mixed_batch(core):
    a = _topic(core)
    core.vault.set_setting("promotion", "mode", "agent")
    out = core.mcp_call("staging_decide", {"item_ids": [a, "new-widget"], "decision": "accept"}, tier="contribute")["result"]
    assert out.get("accepted") == 1, out
    assert out["results"][0]["refused"] == "PERSON_CONFIRMS"
    assert "Alpha Studies" not in core.vault.topics()


def test_agent_revisions_still_require_individual_review_tokens(core):
    core.writer.submit(lambda: _store(core).add({"id": "rev-a", "kind": "source", "name": "other-0",
        "revision_of": "Sources/repository/other-0.md", "sections": {"Claims": "A newly reviewed claim."}}))
    a = _topic(core)
    out = core.mcp_call("staging_decide", {"item_ids": ["rev-a", a], "decision": "accept"}, tier="contribute")["result"]
    assert out.get("refused") == "REVISION_REQUIRED", out
    assert "Alpha Studies" not in core.vault.topics()


@pytest.mark.parametrize("change", ["attachment", "staged", "policy"])
def test_permission_wait_cannot_retarget_mixed_source_and_import(core, change):
    i = _import(core)
    core.vault.set_setting("promotion", "mode", "agent")
    core.set_mode("ask")
    events, results = queue.Queue(), []
    core.broker.subscribe(lambda e: events.put(e) if e.get("type") == "permission_request" else None)
    t = threading.Thread(target=lambda: results.append(core.mcp_call("staging_decide", {
        "item_ids": ["new-widget", i], "decision": "accept"}, tier="contribute")["result"]))
    t.start()
    try:
        request = events.get(timeout=5)
        if change == "attachment":
            _originals(core)[0].write_bytes(b"The human's newer source input")
        elif change == "staged":
            core.writer.submit(lambda: _store(core).save({**_store(core).load(i), "target": "Notes/Unreviewed.md"}))
        else:
            core.vault.set_setting("promotion", "mode", "person")
        core.broker.answer(request["id"], "allow_once")
        t.join(5)
        assert not t.is_alive()
        assert results[0].get("refused") == "DOCUMENT_ACTIVE", results
        assert not _copies(core) and not (core.vault.root / "Notes/Imported.md").exists()
    finally:
        core.broker.close("test cleanup")
        t.join(5)


def test_topic_partial_progress_is_item_local_and_resumes_after_restart(core, monkeypatch):
    a, b = _topic(core), _topic(core, "topic-b", "Beta Studies", ["other-1"])
    original, failures = Index.upsert, []
    def upsert(self, path, **kw):
        result = original(self, path, **kw)
        if (path == core.vault.root / "About/Topics.md" and not failures
                and "| Alpha Studies |" in path.read_text(encoding="utf-8")):
            failures.append(True)
            raise OSError("private failure details")
        return result
    with monkeypatch.context() as m:
        m.setattr(Index, "upsert", upsert)
        out = _accept(core, [a, b])
    assert out.get("accepted") == 1 and out["results"][1]["status"] == "accepted", out
    progress = _store(core).load(a)["acceptance_progress"]
    assert progress["completed_paths"] == ["About/Topics.md"]
    assert "private failure details" not in str(out)
    core.close_runtime()
    restarted = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        assert _accept(restarted, [a]).get("accepted") == 1
        text = (core.vault.root / "About/Topics.md").read_text(encoding="utf-8")
        assert text.count("| Alpha Studies |") == text.count("| Beta Studies |") == 1
        assert _topic_of(core, "other-0") == "Alpha Studies"
    finally:
        restarted.close_runtime()


def test_mixed_preview_is_read_only_and_discloses_ordered_replanning(core):
    a = _topic(core, members=["New Widget"])
    before = (core.vault.root / "About/Topics.md").read_bytes()
    out = _accept(core, ["new-widget", a], dry_run=True)
    assert out.get("would_accept") == 2 and out["ordered_replanning"], out
    assert "Sources/document/New Widget.md" in out["targets"]
    source = out["results"][0]
    assert source["coverage"] == "captured" and source["sections"] == ["Claims"]
    assert source["file"] == "Sources/document/files/paper.pdf" and len(source["copies"]) == 2
    assert (core.vault.root / "About/Topics.md").read_bytes() == before
    assert not _copies(core) and not _source(core).exists()


def test_same_topic_twice_never_overwrites_first_row(core):
    a, b = _topic(core), _topic(core, "topic-b", "Alpha Studies", ["other-1"])
    out = _accept(core, [a, b])
    assert out.get("accepted") == 1 and out["results"][1].get("error"), out
    assert (core.vault.root / "About/Topics.md").read_text(encoding="utf-8").count("| Alpha Studies |") == 1
    assert _topic_of(core, "other-0") == "Alpha Studies"
    assert _topic_of(core, "other-1") == "Unfiled"


@pytest.mark.parametrize("import_first", [False, True])
def test_import_source_collision_never_replaces_earlier_work_or_moves_inputs(core, import_first):
    i = _import(core, target="Sources/document/New Widget.md", fm={"type": "source", "kind": "document"})
    out = _accept(core, [i, "new-widget"] if import_first else ["new-widget", i])
    assert out.get("accepted") == 1, out
    assert all(p.exists() for p in _originals(core))
    assert len(_copies(core)) == (0 if import_first else 2)
    assert ("Original prose." in _source(core).read_text(encoding="utf-8")) == import_first


def test_later_member_lease_blocks_before_any_topic_row_is_added(core):
    a, b = _topic(core), _topic(core, "topic-b", "Beta Studies", ["other-1"])
    core.document_leases.heartbeat("Sources/repository/other-1.md", editor="Obsidian", dirty=True)
    before = (core.vault.root / "About/Topics.md").read_bytes()
    out = _accept(core, [a, b])
    assert out.get("refused") == "DOCUMENT_ACTIVE", out
    assert (core.vault.root / "About/Topics.md").read_bytes() == before


def test_failed_source_is_not_refiled_by_a_later_topic_before_person_review(core, monkeypatch):
    a = _topic(core, members=["New Widget"])
    original = Index.upsert
    def upsert(self, path, **kw):
        result = original(self, path, **kw)
        if path == _source(core):
            raise OSError("source index failure")
        return result
    with monkeypatch.context() as m:
        m.setattr(Index, "upsert", upsert)
        out = _accept(core, ["new-widget", a])
    assert out.get("accepted") == 0, json.dumps(out, indent=2)
    assert "interrupted work" in out["results"][1]["error"]
    assert "Alpha Studies" not in core.vault.topics()
    assert _accept(core, ["new-widget"]).get("accepted") == 1
    assert _accept(core, [a]).get("accepted") == 1


def test_separate_lens_store_and_import_keep_normal_mixed_decision_contract(core):
    i = _import(core)
    core.writer.submit(lambda: _store(core).add({"id": "lens-a", "kind": "lens", "name": "Interface first",
        "source": "A source", "source_quote": "program to an interface", "attends_to": ["interfaces"]}))
    out = _accept(core, [i, "lens-a"])
    assert out.get("accepted") == 2, json.dumps(out, indent=2)
    assert out["results"][1]["lens"]


def test_combined_mixed_inventory_is_bounded_before_any_write(core, monkeypatch):
    a = _topic(core)
    original = taxonomy.prepare_accept
    def large(*args, **kwargs):
        plan = original(*args, **kwargs)
        plan["observed"].extend((f"Notes/dependency-{n}.md", "missing") for n in range(200))
        return plan
    monkeypatch.setattr(taxonomy, "prepare_accept", large)
    out = _accept(core, [a, "new-widget"])
    assert out.get("error") == "invalid_arguments" and "200-file" in out["detail"], out
    assert not _copies(core) and "Alpha Studies" not in core.vault.topics()


def test_failed_topic_does_not_overwrite_an_outside_edit_to_its_staged_record(core, monkeypatch):
    a, b = _topic(core), _topic(core, "topic-b", "Beta Studies", ["other-1"])
    original, human = Index.upsert, []
    def upsert(self, path, **kw):
        result = original(self, path, **kw)
        if path == core.vault.root / "About/Topics.md" and "| Alpha Studies |" in path.read_text(encoding="utf-8"):
            item = _store(core).load(a)
            item["what_belongs"] = "A newer human decision."
            _store(core).save(item)  # An outside editor, deliberately not Core's writer.
            human.append(_store(core).path(a).read_bytes())
            raise OSError("failed after a human edit")
        return result
    monkeypatch.setattr(Index, "upsert", upsert)
    out = _accept(core, [a, b])
    assert out.get("refused") == "DOCUMENT_ACTIVE", json.dumps(out, indent=2)
    assert _store(core).path(a).read_bytes() == human[-1]
    assert "acceptance_progress" not in _store(core).load(a)
    assert "Beta Studies" not in core.vault.topics()


def test_later_topic_cannot_reuse_an_earlier_topics_generated_filename(core):
    a = _topic(core, name="Alpha/Studies")
    b = _topic(core, "topic-b", "AlphaStudies", ["other-1"])
    out = _accept(core, [a, b])
    assert out.get("accepted") == 1, json.dumps(out, indent=2)
    assert "filenames collide" in out["results"][1]["error"]
    assert "AlphaStudies" not in core.vault.topics()
    text = (core.vault.root / "Indexes/Topic - AlphaStudies.md").read_text(encoding="utf-8")
    assert "[[other-0]]" in text and "[[other-1]]" not in text


def test_progress_recording_cannot_bypass_guards_for_policy_files(core):
    from resource_librarian.coordination import fingerprint
    rel = ".librarian/config.toml"
    before = core.vault.config_path.read_bytes()
    guard = promotion.PromotionGuard(core.vault, {"targets": [rel], "observed": [(rel, fingerprint(core.vault.config_path))]})
    with pytest.raises(TypeError, match="declared staging record"):
        guard.record_progress(rel, "not policy")
    assert core.vault.config_path.read_bytes() == before


def test_stopped_index_between_topics_preserves_first_result_and_stops_later_work(core, monkeypatch):
    a, b = _topic(core), _topic(core, "topic-b", "Beta Studies", ["other-1"])
    i = _import(core)
    original = promotion.atomic_write_text
    def write(path, text):
        result = original(path, text)
        if path == _store(core).path(a) and '"status": "accepted"' in text:
            core.index_service.close()
        return result
    monkeypatch.setattr(promotion, "atomic_write_text", write)
    out = _accept(core, [a, b, i])
    assert out.get("accepted") == 1, json.dumps(out, indent=2)
    assert out["results"][2]["error"].startswith("not run")
    assert "Alpha Studies" in core.vault.topics() and "Beta Studies" not in core.vault.topics()
    assert not (core.vault.root / "Notes/Imported.md").exists()
