"""Batch state uses the writer; retrieval uses Core, not a second SQLite owner."""
import json
import threading

import pytest

from resource_librarian import batch, dik
from resource_librarian.app import ApiError, App
from resource_librarian.coordination import on_writer_thread, PreconditionChangedError
from resource_librarian.index import Index
from resource_librarian.evidence import EvidenceStore
from resource_librarian.keys import KeyStore
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.staging import StagingStore
from resource_librarian.tools import library
from resource_librarian.workflows import RunStore

from conftest import add_source, pdf_bytes


@pytest.fixture
def core(vault):
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        yield app
    finally:
        app.close_runtime()


def _ctx(core, **extras):
    return Context(tier="curate", vault=core.vault, extras={
        "vault_writer": core.writer, "index_service": core.index_service,
        "caller_kind": "person", **extras})


def _item(core, name="new-model", **values):
    item = {"id": name, "kind": "source", "name": name, "source_kind": "model",
            "status": "approved", "fields": {}, "evidence": [{"id": "fixture"}], **values}
    core.writer.submit(lambda: StagingStore(core.vault).add(item), caller="test-seed")
    return item


def _fail_index(*args, **kwargs):
    raise AssertionError("batch opened a second SQLite connection")


def _thread(fn):
    results, errors = [], []
    def call():
        try:
            results.append(fn())
        except BaseException as exc:
            errors.append(exc)
    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    return thread, results, errors


def test_batch_lookups_use_core_worker_without_refresh(core, monkeypatch):
    add_source(core.vault.root, "held", "A source already in the library.")
    core.index_service.refresh()
    item = _item(core)
    sql = []
    original = Index.note_row
    def row(self, name):
        sql.append(threading.current_thread())
        return original(self, name)
    monkeypatch.setattr(Index, "note_row", row)
    monkeypatch.setattr(library, "Index", _fail_index)
    monkeypatch.setattr(Index, "refresh", _fail_index)
    assert batch._validate(_ctx(core), {**item, "name": "held"})["status"] == "failed"
    assert batch._validate(_ctx(core), item)["status"] == "complete"
    assert batch._validate(_ctx(core), {**item, "evidence": []})["status"] == "failed"
    assert set(sql) == {core.index_service._thread}


def test_metadata_uses_latest_fields_and_preserves_other_proposals(core, monkeypatch):
    from resource_librarian import intake
    item = _item(core, fields={"language": "Python"})
    record = {"source": item["name"], "data": [{"kind": "language", "name": "Rust"}]}
    core.writer.submit(lambda: dik.save(core.vault, record))
    batch._update_item(_ctx(core), item["id"], lambda fresh: fresh.update(
        fields={"language": "Go"}, metadata_proposals={"license": "person's review"}))
    sql = []
    original = intake.readiness
    def readiness(engine, kind, fields):
        sql.append(threading.current_thread())
        return original(engine, kind, fields)
    monkeypatch.setattr(intake, "readiness", readiness)
    monkeypatch.setattr(library, "Index", _fail_index)
    out = batch._metadata(_ctx(core), item)
    fresh = StagingStore(core.vault).load(item["id"])
    assert "proposed" not in out
    assert fresh["fields"]["language"] == "Go"
    assert fresh["metadata_proposals"] == {"license": "person's review"}
    assert sql == [core.index_service._thread]


def test_metadata_proposals_save_on_writer_and_keep_other_fields(core, monkeypatch):
    item = _item(core, metadata_proposals={"license": "existing proposal"})
    core.writer.submit(lambda: dik.save(core.vault, {
        "source": item["name"], "data": [{"kind": "language", "name": "Rust"}]}))
    original, saves = StagingStore.save, []
    def save(self, value):
        assert on_writer_thread()
        saves.append(value["id"])
        return original(self, value)
    monkeypatch.setattr(StagingStore, "save", save)
    assert batch._metadata(_ctx(core), item)["proposed"] == {"language": "Rust"}
    fresh = StagingStore(core.vault).load(item["id"])
    assert fresh["metadata_proposals"] == {"license": "existing proposal", "language": "from the Data records"}
    assert saves == [item["id"]]


@pytest.mark.parametrize("closed", ["index", "writer"])
def test_stopped_core_cannot_change_metadata_or_fall_back(core, monkeypatch, closed):
    item = _item(core)
    core.writer.submit(lambda: dik.save(core.vault, {
        "source": item["name"], "data": [{"kind": "language", "name": "Rust"}]}))
    path = StagingStore(core.vault).path(item["id"])
    before = path.read_bytes()
    monkeypatch.setattr(library, "Index", _fail_index)
    (core.index_service if closed == "index" else core.writer).close()
    with pytest.raises(RuntimeError, match="closed"):
        batch._metadata(_ctx(core), item)
    assert path.read_bytes() == before


@pytest.mark.parametrize("background", [False, True])
def test_batch_releases_writer_between_stages_and_serializes_state(core, monkeypatch, background):
    item = _item(core)
    entered, release = threading.Event(), threading.Event()
    saves, logs = [], []
    original_save, original_append = StagingStore.save, RunStore.append
    def save(self, value):
        assert on_writer_thread()
        saves.append(value["id"])
        return original_save(self, value)
    def append(self, run_id, event):
        assert on_writer_thread()
        logs.append(event["type"])
        return original_append(self, run_id, event)
    def slow(ctx, source):
        assert not on_writer_thread()
        entered.set()
        assert release.wait(5)
        return {"status": "complete"}
    monkeypatch.setattr(StagingStore, "save", save)
    monkeypatch.setattr(RunStore, "append", append)
    monkeypatch.setattr(batch, "STAGES", [("validate", batch._validate), ("read", slow)])
    monkeypatch.setattr(library, "Index", _fail_index)
    thread, results, errors = _thread(lambda: core.person_call("process_approved", {"background": background}))
    worker = None
    try:
        assert entered.wait(3)
        worker = batch._LIVE[str(core.vault.root)][1]
        assert core.running()["batch"]
        repeated = core.person_call("process_approved", {"background": True})
        assert repeated["started"] is False and repeated["already_running"]
        batch._update_item(_ctx(core), item["id"], lambda fresh: fresh.update(title="person's title"))
        assert library.index_status(_ctx(core))["notes"] >= 0
        late = _item(core, "next-batch")
        release.set()
        thread.join(5)
        if worker:
            worker.join(5)
        assert not thread.is_alive() and not errors and results, errors
        assert not batch.live(core.vault)
        fresh = StagingStore(core.vault).load(item["id"])
        assert fresh["title"] == "person's title" and fresh["status"] == "enriched"
        assert StagingStore(core.vault).load(late["id"])["status"] == "approved"
        assert "finished" in logs and len(saves) >= 3
        events = RunStore(core.vault).events(batch.latest(core.vault))
        assert [e["stage"] for e in events if e["type"] == "done"] == ["validate", "read"]
    finally:
        release.set()
        thread.join(5)
        if worker:
            worker.join(5)


def test_cancelled_last_stage_is_resumable_without_repeating_it(core, monkeypatch):
    item = _item(core)
    calls = []
    def step(ctx, source):
        calls.append(source["id"])
        ctx.extras["cancel"].set()
        return {"status": "complete"}
    monkeypatch.setattr(batch, "STAGES", [("read", step)])
    out = core.person_call("process_approved", {})
    assert out["status"] == "cancelled"
    assert StagingStore(core.vault).load(item["id"])["status"] == "processing"
    resumed = core.person_call("process_approved", {"resume": out["run"]})
    assert resumed["status"] == "finished" and calls == [item["id"]]
    assert StagingStore(core.vault).load(item["id"])["status"] == "enriched"


def test_person_decision_during_stage_is_not_overwritten(core, monkeypatch):
    item = _item(core)
    def step(ctx, source):
        batch._update_item(ctx, source["id"], lambda fresh: fresh.update(status="deferred"))
        return {"status": "complete"}
    monkeypatch.setattr(batch, "STAGES", [("read", step)])
    out = core.person_call("process_approved", {})
    assert out["status"] == "failed"
    assert StagingStore(core.vault).load(item["id"])["status"] == "deferred"


def test_derived_record_changed_during_clerk_call_is_not_replaced(core, monkeypatch):
    item = _item(core, source_kind="document")
    record = {"source": item["name"], "kind": "document", "data": [
        {"id": "a", "kind": "chapter"}, {"id": "b", "kind": "chapter"}], "information": []}
    core.writer.submit(lambda: dik.save(core.vault, record))
    def relate(value, endpoint, queue, **kwargs):
        assert not on_writer_thread()
        assert library.index_status(_ctx(core))["notes"] >= 0
        core.writer.submit(lambda: dik.save(core.vault, {**record, "person": "new revision"}))
        value["information"] = [{"type": "stale model output"}]
        return {"added": 1}
    monkeypatch.setattr(dik, "relate_chapters", relate)
    with pytest.raises(PreconditionChangedError):
        batch._relate(_ctx(core), item)
    assert dik.load(core.vault, item["name"])["person"] == "new revision"
    assert dik.load(core.vault, item["name"])["information"] == []


def test_host_stop_sees_and_cancels_background_batch_before_closing_writer(core, monkeypatch):
    _item(core)
    entered = threading.Event()
    def step(ctx, item):
        entered.set()
        assert ctx.extras["cancel"].wait(4)
        return {"status": "partial", "reason": "cancelled"}
    monkeypatch.setattr(batch, "STAGES", [("read", step)])
    out = core.person_call("process_approved", {"background": True})
    assert entered.wait(3)
    core.host_managed = True
    with pytest.raises(ApiError) as held:
        core.request_host_stop()
    assert held.value.status == 409
    assert core.request_host_stop(force=True)["active"]["batch"] == out["run"]
    core.close_runtime()
    assert not batch.live(core.vault)
    assert batch.status(core.vault, out["run"])["status"] == "cancelled"
    phase = next(p for p in core.shutdown_phases if p["phase"] == "work_cancelled")
    assert phase["batch_still_running"] == ""
    assert core.writer.interrupted_operations() == []


def test_tier_gate_and_closed_writer_refuse_before_start(core):
    item = _item(core)
    ctx = _ctx(core)
    ctx.tier = "contribute"
    assert REGISTRY.call("process_approved", {}, ctx)["refused"] == "TIER_REFUSED"
    core.writer.close()
    with pytest.raises(RuntimeError, match="closed"):
        batch.start(_ctx(core), "person")
    assert not batch.live(core.vault)
    assert StagingStore(core.vault).load(item["id"])["status"] == "approved"


def test_pdf_fetch_keeps_io_off_writer_and_refuses_stale_item(core):
    item = _item(core, source_kind="paper")
    class Fetcher:
        def get(self, url, accept):
            assert not on_writer_thread()
            batch._update_item(_ctx(core), item["id"], lambda fresh: fresh.update(title="new title"))
            return pdf_bytes([["Fetched paper text with enough words to read."]])
    with pytest.raises(PreconditionChangedError):
        batch._fetch_full_text(_ctx(core, fetcher=Fetcher()), item, "https://example.org/paper.pdf")
    assert not (core.vault.work("staging") / "files" / f"{item['id']}.pdf").exists()
    assert StagingStore(core.vault).load(item["id"])["title"] == "new title"


def test_batch_clerk_queue_commits_and_cleanup_use_writer(core, monkeypatch):
    from resource_librarian import clerk
    from resource_librarian.tools import staging as staging_tools
    item = _item(core, source_kind="document")
    record = {"source": item["name"], "kind": "document", "data": [
        {"id": c, "name": c, "kind": "chapter", "coverage": "full", "claims": ["A claim."]}
        for c in ("a", "b")], "information": []}
    core.writer.submit(lambda: dik.save(core.vault, record))
    monkeypatch.setattr(staging_tools, "clerk_endpoint", lambda ctx: None)
    assert batch._relate(_ctx(core), item)["status"] == "queued"
    queue = core.vault.work("queue") / "clerk"
    queued = clerk.next_task(queue)
    assert queued
    target = (queue / f"{queued['key']}.json").relative_to(core.vault.root).as_posix()
    events = [json.loads(line) for line in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    assert any(e["status"] == "done" and e["targets"] == [target] for e in events)
    core.writer.submit(lambda: clerk.submit(queue, queued["key"], {"relations": []}, by="test"))
    # Replay a stale pending file beside its stored answer, as after a crash.
    core.writer.submit(lambda: (queue / f"{queued['key']}.json").write_text("{}", encoding="utf-8"))
    assert batch._relate(_ctx(core), item)["status"] == "complete"
    assert not (queue / f"{queued['key']}.json").exists()
    assert clerk.next_task(queue) is None


def test_owned_state_targets_are_audited_but_hidden_paths_stay_private(core):
    path = core.vault.librarian / "derived" / "test.json"
    core.writer.submit(lambda: (path.parent.mkdir(parents=True, exist_ok=True),
        path.write_text("{}", encoding="utf-8")), caller="test", targets=[".librarian/derived/test.json"])
    events = [json.loads(line) for line in core.writer.log_path.read_text(encoding="utf-8").splitlines()]
    assert events[-1]["targets"] == [".librarian/derived/test.json"]
    assert events[-1]["observed_fingerprints"] == {".librarian/derived/test.json": "missing"}
    for rel in (".librarian/derived/test.json", ".obsidian/settings.json"):
        with pytest.raises(Exception, match="VAULT_REQUIRED"):
            core.vault.safe_relative(rel)
        with pytest.raises(Exception, match="VAULT_REQUIRED"):
            core.document_leases.heartbeat(rel, editor="Obsidian", dirty=True)
    executed = []
    for rel in (".librarian/../outside.json", ".obsidian/settings.json"):
        with pytest.raises(Exception, match="VAULT_REQUIRED"):
            core.writer.submit(lambda: executed.append(True), targets=[rel])
    assert executed == []


def test_other_workflow_cannot_be_resumed_as_an_approved_batch(core):
    runs = RunStore(core.vault)
    core.writer.submit(lambda: runs.append("workflow-fixture", {
        "type": "started", "name": "another-workflow", "kind": "workflow", "items": []}))
    before = runs.path("workflow-fixture").read_bytes()
    out = core.person_call("process_approved", {"resume": "workflow-fixture"})
    assert out["error"] == "invalid_arguments"
    assert runs.path("workflow-fixture").read_bytes() == before


def test_late_batch_results_cannot_write_after_core_stop(core, monkeypatch):
    item = _item(core)
    entered, release = threading.Event(), threading.Event()
    def step(ctx, value):
        entered.set()
        assert release.wait(5)
        batch._update_item(ctx, value["id"], lambda fresh: fresh.update(late=True))
        return {"status": "complete"}
    monkeypatch.setattr(batch, "STAGES", [("read", step)])
    monkeypatch.setattr(core, "STOP_GRACE_SECONDS", 0.05)
    out = core.person_call("process_approved", {"background": True})
    worker = batch._LIVE[str(core.vault.root)][1]
    try:
        assert entered.wait(3)
        core.close_runtime()
        stage_path = StagingStore(core.vault).path(item["id"])
        log_path = RunStore(core.vault).path(out["run"])
        stage_before, log_before = stage_path.read_bytes(), log_path.read_bytes()
        release.set()
        worker.join(5)
        assert not worker.is_alive()
        assert stage_path.read_bytes() == stage_before
        assert log_path.read_bytes() == log_before
        assert batch.status(core.vault, out["run"])["status"] == "interrupted"
    finally:
        release.set()
        worker.join(5)


def test_all_real_batch_stages_work_in_a_coordinated_core_without_paid_calls(core, monkeypatch):
    evidence = core.writer.submit(lambda: EvidenceStore(core.vault).put(
        "model_listing", "https://example.org/model", {"text":
            "This model generates text. Its context window is bounded and tools require testing."}))
    item = _item(core, evidence=[{"id": evidence.id}], fields={
        "provider": "fixture", "model_id": "test-model", "context_length": 4096})
    monkeypatch.setattr(library, "Index", _fail_index)
    out = REGISTRY.call("process_approved", {}, _ctx(core))
    assert out["status"] == "finished", out
    assert set(out["items"][0]["stages"]) == {stage for stage, _ in batch.STAGES}
    assert "failed" not in out["items"][0]["stages"].values(), out
    # With no endpoint the read/review wait in the existing queue; no silent
    # fallback model, promotion, or claim of full reading is introduced.
    fresh = StagingStore(core.vault).load(item["id"])
    assert fresh["status"] == "partial"
    assert fresh["processing"]["coverage"].startswith("partial")
    assert not (core.vault.root / "Sources/model/new-model.md").exists()


def test_start_audit_failure_does_not_leave_a_phantom_live_batch(core, monkeypatch):
    _item(core)
    original = core.writer._record
    def record(op):
        if op.caller == "batch" and not op.targets and op.status == "done":
            raise OSError("simulated final audit failure")
        return original(op)
    monkeypatch.setattr(core.writer, "_record", record)
    out = core.person_call("process_approved", {})
    assert out["error"] == "failed"
    assert not batch.live(core.vault)
    assert batch.status(core.vault)["status"] == "interrupted"
    assert core.writer.interrupted_operations()
