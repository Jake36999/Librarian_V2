"""Taxonomy writes keep prepared bytes, target leases and Core SQL ownership."""
from dataclasses import replace
import json
import queue
import threading

import pytest

from resource_librarian import clerk, notes, staging, taxonomy
from resource_librarian.app import App
from resource_librarian.coordination import on_writer_thread
from resource_librarian.index import Index
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.tools import library

from conftest import add_source


@pytest.fixture
def core(vault):
    (vault.root / "About/Topics.md").write_text(
        "# Topics\n\n| Topic | What belongs here |\n| --- | --- |\n"
        "| Unfiled | waiting |\n| Data | data tools |\n| Systems | host tools |\n", encoding="utf-8")
    add_source(vault.root, "alpha", "A query planner with SQL joins.")
    add_source(vault.root, "beta", "A host telemetry collector.")
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode("auto")
    try:
        yield app
    finally:
        app.close_runtime()


def _note(core, name):
    return core.vault.root / f"Sources/repository/{name}.md"


def _ops(core):
    return [json.loads(line) for line in core.writer.log_path.read_text(encoding="utf-8").splitlines()]


def _pending(core, tool, args, mutate):
    core.set_mode("ask")
    requests, results = queue.Queue(), []
    core.broker.subscribe(lambda event: requests.put(event) if event.get("type") == "permission_request" else None)
    thread = threading.Thread(target=lambda: results.append(core.mcp_call(tool, args, tier="contribute")["result"]))
    thread.start()
    try:
        try:
            event = requests.get(timeout=3)
        except queue.Empty:
            raise AssertionError(f"no approval request; returned results: {results}") from None
        mutate()
        core.broker.answer(event["id"], "allow_once")
        thread.join(5)
        assert not thread.is_alive()
        return results[0]
    finally:
        core.broker.close("test cleanup")
        thread.join(3)


def test_refile_and_views_keep_sql_and_files_on_their_owners(core, monkeypatch):
    sql, files, rendering = [], [], []
    original_write, original_upsert = taxonomy.atomic_write_text, Index.upsert
    original_topic, original_master = taxonomy.topic_index_text, taxonomy.master_index_text
    def no_direct(*args, **kwargs):
        raise AssertionError("a Core-backed taxonomy call opened a second index")
    def write(path, text):
        assert on_writer_thread()
        files.append(path.relative_to(core.vault.root).as_posix())
        return original_write(path, text)
    def upsert(index, *args, **kwargs):
        sql.append(threading.current_thread())
        return original_upsert(index, *args, **kwargs)
    def topic(*args, **kwargs):
        rendering.append(threading.current_thread())
        return original_topic(*args, **kwargs)
    def master(*args, **kwargs):
        rendering.append(threading.current_thread())
        return original_master(*args, **kwargs)
    monkeypatch.setattr(library, "Index", no_direct)
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    monkeypatch.setattr(Index, "upsert", upsert)
    monkeypatch.setattr(taxonomy, "topic_index_text", topic)
    monkeypatch.setattr(taxonomy, "master_index_text", master)
    out = core.person_call("refile_source", {"sources": ["alpha", "beta"], "topic": "Data"})
    assert [row["source"] for row in out["results"]] == ["alpha", "beta"], out
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == "Data"
    assert notes.load(_note(core, "beta")).frontmatter["primary_topic"] == "Data"
    assert "[[alpha]]" in (core.vault.root / "Indexes/Topic - Data.md").read_text(encoding="utf-8")
    assert "[[beta]]" in (core.vault.root / "Indexes/Topic - Data.md").read_text(encoding="utf-8")
    out = core.person_call("views_refresh", {})
    assert out.get("not_accepted") == [] and "Indexes/Master Index.md" in out["written"], out
    assert files and sql and rendering
    assert set(sql + rendering) == {core.index_service._thread}
    operations = [op for op in _ops(core) if op["status"] == "done" and "Sources/repository/alpha.md" in op["targets"]]
    assert set(operations[-1]["targets"]) == {"Sources/repository/alpha.md", "Sources/repository/beta.md",
        "Indexes/Topic - Unfiled.md", "Indexes/Topic - Data.md", "Indexes/Master Index.md"}
    assert "About/Topics.md" in operations[-1]["precondition_fingerprints"]
    assert "About/Topics.md" not in operations[-1]["targets"]


@pytest.mark.parametrize("changed", ["source", "taxonomy", "view"])
def test_permission_wait_cannot_adopt_changed_targets_or_taxonomy(core, changed):
    assert "written" in core.person_call("views_refresh", {})
    before_beta = _note(core, "beta").read_bytes()
    def mutate():
        path = (_note(core, "alpha") if changed == "source" else
                core.vault.root / ("About/Topics.md" if changed == "taxonomy" else "Indexes/Master Index.md"))
        path.write_bytes(path.read_bytes() + b"\nHuman annotation during approval.\n")
    out = _pending(core, "refile_source", {"sources": ["alpha", "beta"], "topic": "Data"}, mutate)
    assert out["refused"] == "DOCUMENT_ACTIVE" and out["checkpoint"]["type"] == "write_conflict", out
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == "Unfiled"
    assert _note(core, "beta").read_bytes() == before_beta


@pytest.mark.parametrize("active", ["Sources/repository/beta.md", "Indexes/Master Index.md"])
def test_active_target_lease_blocks_before_any_source_changes(core, active):
    core.document_leases.heartbeat(active, editor="Obsidian", dirty=True)
    out = core.person_call("refile_source", {"sources": ["alpha", "beta"], "topic": "Data"})
    assert out["refused"] == "DOCUMENT_ACTIVE"
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == "Unfiled"


@pytest.mark.parametrize("interruption", ["lease", "edit"])
def test_edit_starting_mid_refile_stops_next_write_and_keeps_completed_work(core, monkeypatch, interruption):
    before_beta = _note(core, "beta").read_bytes()
    master = core.vault.root / "Indexes/Master Index.md"
    before_master = master.read_bytes()
    original_write = taxonomy.atomic_write_text
    def write(path, text):
        original_write(path, text)
        if path == _note(core, "alpha"):
            if interruption == "lease":
                core.document_leases.heartbeat("Sources/repository/beta.md", editor="Obsidian", dirty=True)
            else:
                _note(core, "beta").write_bytes(before_beta + b"\nNew human prose.\n")
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    out = core.person_call("refile_source", {"sources": ["alpha", "beta"], "topic": "Data"})
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert out["completed_paths"] == ["Sources/repository/alpha.md"]
    assert "Earlier writes remain" in out["checkpoint"]["scope"]
    assert out["checkpoint"]["evidence"]["completed_paths"] == ["Sources/repository/alpha.md"]
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == "Data"
    assert notes.load(_note(core, "beta")).frontmatter["primary_topic"] == "Unfiled"
    assert _note(core, "beta").read_bytes() == before_beta + (b"\nNew human prose.\n" if interruption == "edit" else b"")
    assert master.read_bytes() == before_master
    row = core.index_service.run(lambda index: dict(index.note_row("alpha")))
    assert json.loads(row["frontmatter"])["primary_topic"] == "Data"


def test_unrelated_note_lease_does_not_block_refiling(core):
    core.document_leases.heartbeat("Notes/Unrelated.md", editor="Obsidian", dirty=True)
    out = core.person_call("refile_source", {"sources": ["alpha"], "topic": "Data"})
    assert out["results"][0]["topic"] == "Data", out


def test_view_plan_inventory_change_while_waiting_requires_replan(core):
    master = core.vault.root / "Indexes/Master Index.md"
    before_master = master.read_bytes()
    def mutate():
        add_source(core.vault.root, "newcomer", "New source.", topic="New external topic")
    out = _pending(core, "views_refresh", {}, mutate)
    assert out["refused"] == "DOCUMENT_ACTIVE" and "source topics changed" in out["detail"], out
    assert master.read_bytes() == before_master


def test_closed_index_refuses_without_markdown_changes(core):
    before = _note(core, "alpha").read_bytes()
    master = core.vault.root / "Indexes/Master Index.md"
    before_master = master.read_bytes()
    core.index_service.close()
    out = core.person_call("refile_source", {"sources": ["alpha"], "topic": "Data"})
    assert out["error"] == "failed" and "closed" in out["detail"], out
    assert _note(core, "alpha").read_bytes() == before
    assert master.read_bytes() == before_master


def test_preparation_is_invocation_local_and_not_persisted(core):
    ctx = Context(tier="curate", vault=core.vault, extras={**core._extras(), "caller_kind": "person"})
    out = REGISTRY.call("refile_source", {"sources": ["alpha"], "topic": "Data"}, ctx)
    assert out["results"][0]["topic"] == "Data", out
    assert "_prepared_write" not in ctx.extras
    log = core.writer.log_path.read_text(encoding="utf-8")
    assert "A query planner with SQL joins." not in log and "_prepared_write" not in log
    core.close_runtime()
    restarted = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        assert restarted.operation_recoveries == []
    finally:
        restarted.close_runtime()


def test_simultaneous_refiles_do_not_exchange_prepared_contents(core, monkeypatch):
    spec = REGISTRY.get("refile_source")
    barrier = threading.Barrier(2)
    def intent(ctx, kwargs):
        plan = spec.intent(ctx, kwargs)
        barrier.wait(timeout=5)
        return plan
    monkeypatch.setitem(REGISTRY._tools, "refile_source", replace(spec, intent=intent))
    results = []
    def run(topic):
        results.append(core.person_call("refile_source", {"sources": ["alpha"], "topic": topic}))
    threads = [threading.Thread(target=run, args=(topic,)) for topic in ("Data", "Systems")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(8)
        assert not thread.is_alive()
    assert sum("results" in out for out in results) == 1, results
    assert sum(out.get("refused") == "DOCUMENT_ACTIVE" for out in results) == 1, results
    accepted = next(out["results"][0]["topic"] for out in results if "results" in out)
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == accepted


def _stage_topic(core):
    core._serialized("seed-topic", lambda: staging.StagingStore(core.vault).add({
        "id": "topic-research", "kind": "topic", "name": "Research", "what_belongs": "research tooling",
        "members": ["alpha", "beta"], "aliases": ["Research tools"]}))


def _topic_accept(core, **extra):
    proposal = next(item for item in core.person_call("topics_list", {})["proposed"] if item["id"] == "topic-research")
    return core.person_call("staging_decide", {"item_ids": [proposal["id"]], "decision": "accept",
        "staged_revision": proposal["staged_revision"], **extra})


@pytest.mark.parametrize("refile", [True, False])
def test_single_topic_acceptance_preserves_person_flow_and_sql_ownership(core, monkeypatch, refile):
    _stage_topic(core)
    master = core.vault.root / "Indexes/Master Index.md"
    before_master = master.read_bytes()
    threads = []
    original_write, original_upsert = taxonomy.atomic_write_text, Index.upsert
    def write(path, text):
        assert on_writer_thread()
        return original_write(path, text)
    def upsert(index, *args, **kwargs):
        threads.append(threading.current_thread())
        return original_upsert(index, *args, **kwargs)
    monkeypatch.setattr(library, "Index", lambda *a, **k: pytest.fail("second index during topic acceptance"))
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    monkeypatch.setattr(Index, "upsert", upsert)
    out = _topic_accept(core, fields={"name": "Research Tools", "refile": refile})
    assert out["accepted"] == 1 and out["results"][0]["topic"] == "Research Tools", out
    assert core.vault.topics().count("Research Tools") == 1
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == ("Research Tools" if refile else "Unfiled")
    assert threads and set(threads) == {core.index_service._thread}
    if not refile:
        assert master.read_bytes() == before_master
    accepted = [op for op in _ops(core) if op["status"] == "done" and "About/Topics.md" in op["targets"]][-1]
    assert "_prepared_write" not in json.dumps(accepted)
    assert "Research tools" not in core.writer.log_path.read_text(encoding="utf-8")


def test_agent_promotion_setting_does_not_allow_topic_acceptance(core):
    _stage_topic(core)
    core.vault.set_setting("promotion", "mode", "agent")
    proposal = core.mcp_call("topics_list", {}, tier="contribute")["result"]["proposed"][0]
    out = core.mcp_call("staging_decide", {"item_ids": ["topic-research"], "decision": "accept",
        "staged_revision": proposal["staged_revision"]}, tier="contribute")["result"]
    assert out["results"][0]["refused"] == "PERSON_CONFIRMS", out
    assert "Research" not in core.vault.topics()


def test_stale_topic_proposal_token_does_not_accept_unreviewed_members(core):
    _stage_topic(core)
    proposal = core.person_call("topics_list", {})["proposed"][0]
    def change():
        store = staging.StagingStore(core.vault)
        item = store.load("topic-research")
        item["members"] = ["beta"]
        store.save(item)
    core._serialized("change-proposal", change)
    out = core.person_call("staging_decide", {"item_ids": [proposal["id"]], "decision": "accept",
        "staged_revision": proposal["staged_revision"]})
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert "Research" not in core.vault.topics()


def test_dirty_source_blocks_topic_row_addition_before_any_writes(core):
    _stage_topic(core)
    core.document_leases.heartbeat("Sources/repository/beta.md", editor="Obsidian", dirty=True)
    out = _topic_accept(core)
    assert out["refused"] == "DOCUMENT_ACTIVE", out
    assert "Research" not in core.vault.topics()


def test_partial_topic_acceptance_is_reviewable_and_resumable_after_restart(core, monkeypatch):
    _stage_topic(core)
    original_write = taxonomy.atomic_write_text
    def write(path, text):
        original_write(path, text)
        if path == _note(core, "alpha"):
            core.document_leases.heartbeat("Sources/repository/beta.md", editor="Obsidian", dirty=True)
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    out = _topic_accept(core, fields={"name": "Research Tools", "refile": True})
    assert out["refused"] == "DOCUMENT_ACTIVE" and "checkpoint" in out, out
    store = staging.StagingStore(core.vault)
    item = store.load("topic-research")
    assert item["status"] == "staged" and item["acceptance_progress"]["version"] == 1
    assert item["acceptance_progress"]["completed_paths"] == ["About/Topics.md", "Sources/repository/alpha.md"]
    assert core.vault.topics().count("Research Tools") == 1
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == "Research Tools"
    assert notes.load(_note(core, "beta")).frontmatter["primary_topic"] == "Unfiled"
    core.close_runtime()
    monkeypatch.setattr(taxonomy, "atomic_write_text", original_write)
    restarted = App(core.vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        about = restarted.vault.root / "About/Topics.md"
        about.write_text(about.read_text(encoding="utf-8") + "| Another topic | unrelated human addition |\n", encoding="utf-8")
        proposal = restarted.person_call("topics_list", {})["proposed"][0]
        assert proposal["name"] == "Research Tools" and proposal["acceptance_progress"]["refile"] is True
        result = _topic_accept(restarted, fields={"name": "Research Tools", "refile": True})
        assert result["accepted"] == 1, result
        assert restarted.vault.topics().count("Research Tools") == 1
        assert notes.load(_note(restarted, "beta")).frontmatter["primary_topic"] == "Research Tools"
        assert store.load("topic-research")["acceptance_progress"]["completed_at"]
    finally:
        restarted.close_runtime()


def test_changed_partial_topic_row_cannot_be_silently_trusted(core, monkeypatch):
    _stage_topic(core)
    original_write = taxonomy.atomic_write_text
    def write(path, text):
        original_write(path, text)
        if path == core.vault.root / "About/Topics.md":
            core.document_leases.heartbeat("Sources/repository/alpha.md", editor="Obsidian", dirty=True)
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    out = _topic_accept(core)
    assert out["refused"] == "DOCUMENT_ACTIVE"
    path = core.vault.root / "About/Topics.md"
    path.write_text(path.read_text(encoding="utf-8").replace("research tooling", "changed scope"), encoding="utf-8")
    monkeypatch.setattr(taxonomy, "atomic_write_text", original_write)
    core.document_leases.release("Sources/repository/alpha.md", editor="Obsidian")
    out = _topic_accept(core)
    assert out["refused"] == "DOCUMENT_ACTIVE" and "approved taxonomy row changed" in out["detail"], out
    assert notes.load(_note(core, "alpha")).frontmatter["primary_topic"] == "Unfiled"


def test_partial_topic_io_failure_keeps_resume_metadata(core, monkeypatch):
    _stage_topic(core)
    original_write = taxonomy.atomic_write_text
    def write(path, text):
        if path == _note(core, "beta"):
            raise OSError("simulated disk write failure")
        original_write(path, text)
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    out = _topic_accept(core)
    assert out["error"] == "failed" and "simulated disk write failure" in out["detail"], out
    assert staging.StagingStore(core.vault).load("topic-research")["acceptance_progress"]["topic"] == "Research"
    monkeypatch.setattr(taxonomy, "atomic_write_text", original_write)
    assert _topic_accept(core)["accepted"] == 1


def test_generated_topic_filename_collisions_refuse_before_mutation(core):
    about = core.vault.root / "About/Topics.md"
    about.write_text(about.read_text(encoding="utf-8") + "| Data/Store | one |\n| DataStore | two |\n", encoding="utf-8")
    master = core.vault.root / "Indexes/Master Index.md"
    before = master.read_bytes()
    out = core.person_call("views_refresh", {})
    assert out["error"] == "invalid_arguments" and "collide" in out["detail"], out
    assert master.read_bytes() == before


def test_topic_aliases_cannot_inject_taxonomy_rows(core):
    _stage_topic(core)
    out = _topic_accept(core, fields={"refile": False, "aliases": ["also\n| Injected Topic | surprise |"]})
    assert out["accepted"] == 1, out
    assert core.vault.topics() == ["Unfiled", "Data", "Systems", "Research"]


def test_reproposing_topics_does_not_replace_partially_applied_person_changes(core, monkeypatch):
    _stage_topic(core)
    original_write = taxonomy.atomic_write_text
    def write(path, text):
        original_write(path, text)
        if path == core.vault.root / "About/Topics.md":
            core.document_leases.heartbeat("Sources/repository/alpha.md", editor="Obsidian", dirty=True)
    monkeypatch.setattr(taxonomy, "atomic_write_text", write)
    assert _topic_accept(core, fields={"name": "Research Tools"})["refused"] == "DOCUMENT_ACTIVE"
    store = staging.StagingStore(core.vault)
    before = store.path("topic-research").read_bytes()
    endpoint = clerk.Scripted(lambda payload: {"topics": [{"name": "Research", "what_belongs": "new framing",
        "members": ["alpha", "beta"]}]})
    ctx = Context(tier="curate", vault=core.vault, extras={"index_service": core.index_service,
        "vault_writer": core.writer, "clerk": endpoint})
    out = REGISTRY.call("topic_propose", {"only_unfiled": False}, ctx)
    assert out["proposed"] == [], out
    assert endpoint.payloads and not out.get("detail"), out
    assert store.path("topic-research").read_bytes() == before
