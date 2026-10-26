"""Core-owned index boundaries for adapter/agent request contexts."""
from __future__ import annotations

import json
import threading

import pytest

from resource_librarian import clerk, communities, extract, intake, ranking, scout, tools  # noqa: F401
from resource_librarian.index import IndexService
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.tools import library

from conftest import add_source


def _no_direct_index(*_args, **_kwargs):
    raise AssertionError("an App-backed request opened a second SQLite index")


def test_library_reads_use_the_core_index_worker(vault, monkeypatch):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    service = IndexService(vault)
    ctx = Context(tier="curate", vault=vault, extras={"index_service": service})
    try:
        # Construct the service first, then prove a request path does not
        # instantiate library.Index in the calling/adaptor thread.
        monkeypatch.setattr(library, "Index", _no_direct_index)
        found = library.search_tool(ctx, "operating system SQL")
        status = library.index_status(ctx)
    finally:
        service.close()
    assert found["results"][0]["name"] == "osquery"
    assert status["notes"] >= 1


def test_first_party_packs_accept_the_core_index_service(vault, monkeypatch):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    service = IndexService(vault)
    try:
        monkeypatch.setattr(communities, "Index", _no_direct_index)
        built = communities.rebuild(vault, index_service=service)
        monkeypatch.setattr(extract, "Index", _no_direct_index)
        with pytest.raises(TypeError, match="catalogued repository"):
            extract.plan(vault, "missing", index_service=service)
    finally:
        service.close()
    assert built["advisory"] is True


def test_index_service_closes_after_accepted_work_and_rejects_new_work(vault):
    service = IndexService(vault)
    assert service.stats()["notes"] == 0
    service.close()

    with pytest.raises(RuntimeError, match="closed"):
        service.stats()


def test_gateway_returns_copied_data_and_rejects_worker_objects(vault, monkeypatch):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    service = IndexService(vault)
    ctx = Context(tier="consult", vault=vault, extras={"index_service": service})
    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        gateway = library.IndexGateway(ctx)
        row = gateway.run(lambda engine: engine.index.note_row("osquery"))

        assert isinstance(row, dict) and row["name"] == "osquery"
        with pytest.raises(TypeError, match="copied plain data"):
            gateway.run(lambda engine: engine)
        with pytest.raises(TypeError, match="copied plain data"):
            gateway.run(lambda engine: engine.index.conn)
    finally:
        service.close()


def test_callback_intake_fails_before_fetch_when_the_index_service_is_closed(vault):
    """A Core ownership failure must precede network/evidence side effects."""
    service = IndexService(vault)
    ctx = Context(tier="contribute", vault=vault, extras={"index_service": service})

    class MustNotFetch:
        def get(self, *_args, **_kwargs):
            raise AssertionError("intake fetched before Core index admission")

    service.close()
    with pytest.raises(RuntimeError, match="closed"):
        intake.ingest(vault, None, "acme/rowstream", endpoint=None, fetcher=MustNotFetch(),
                      index_call=library.IndexGateway(ctx).run)


def test_core_backed_intake_releases_index_worker_before_clerk_io(vault, monkeypatch):
    """The callback boundary must not pin SQLite while a Clerk is slow."""
    from test_intake import RESPONSES, clerk_answers

    entered, release = threading.Event(), threading.Event()
    errors: list[BaseException] = []
    thread: threading.Thread | None = None

    def answers(payload):
        entered.set()
        assert release.wait(3), "test did not release the scripted Clerk"
        return clerk_answers(payload)

    service = IndexService(vault)
    ctx = Context(tier="curate", vault=vault, extras={
        "index_service": service,
        "clerk": clerk.Scripted(answers),
        "fetcher": intake.Replay(RESPONSES),
    })
    try:
        # The service already owns its Index. Any attempt by the request
        # thread to create another one would make this test fail immediately.
        monkeypatch.setattr(library, "Index", _no_direct_index)

        def run() -> None:
            try:
                REGISTRY.call("ingest", {"ref": "acme/rowstream"}, ctx)
            except BaseException as exc:  # report thread failures in the test thread
                errors.append(exc)

        thread = threading.Thread(target=run)
        thread.start()
        assert entered.wait(3), "intake never reached its Clerk phase"
        # This would time out if the external Clerk call still held the
        # IndexService worker. It also proves an ordinary Core lookup remains
        # available while intake waits.
        assert library.index_status(ctx)["notes"] >= 1
        release.set()
        thread.join(5)
        assert not thread.is_alive()
        assert not errors
    finally:
        release.set()
        if thread is not None:
            thread.join(5)
        service.close()


def test_core_backed_taxonomy_and_ranking_use_callback_index_access(vault, monkeypatch):
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    add_source(vault.root, "falco", "Inspect operating system activity with rules.")
    service = IndexService(vault)

    def answers(payload):
        assert payload["task"] == "topics"
        return {"topics": [{"name": "Host monitoring", "what_belongs": "host activity",
                            "members": ["osquery", "falco"], "aliases": []}]}

    ctx = Context(tier="contribute", vault=vault, extras={
        "index_service": service, "clerk": clerk.Scripted(answers)})
    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        proposed = REGISTRY.call("topic_propose", {}, ctx)
        ranking._save(vault, {"schema_version": 1, "active": "current", "history": [],
                              "candidates": [{"id": "candidate", "heuristics": {}}]})
        compared = REGISTRY.call("ranking_compare", {
            "query": "operating system", "candidate_id": "candidate"}, ctx)
    finally:
        service.close()

    assert proposed["proposed"] == [{"id": "topic-host-monitoring", "name": "Host monitoring",
                                      "sources": 2}]
    assert compared["candidate"] == "candidate"


def test_core_backed_ranking_benchmark_persists_after_index_work(vault, monkeypatch):
    """The benchmark's retrieval is serialized; its durable report is not."""
    add_source(vault.root, "osquery", "Query operating system state with SQL.")
    evaluation = vault.work("eval")
    evaluation.mkdir(parents=True, exist_ok=True)
    (evaluation / "questions.json").write_text(json.dumps({"questions": [{
        "id": "q-osquery", "question": "operating system SQL", "intent": "donor",
        "expects": ["osquery"],
    }]}), encoding="utf-8")
    (evaluation / "scenarios.json").write_text(json.dumps({"scenarios": []}), encoding="utf-8")
    ranking._save(vault, {"schema_version": 1, "active": "current", "history": [],
                          "candidates": [{"id": "candidate", "heuristics": {
                              "coverage_weight": 1.05,
                          }}]})

    service = IndexService(vault)
    ctx = Context(tier="contribute", vault=vault, extras={"index_service": service})
    persisted_on: list[threading.Thread] = []
    original_record = ranking.record_benchmark

    def record(*args, **kwargs):
        persisted_on.append(threading.current_thread())
        return original_record(*args, **kwargs)

    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        monkeypatch.setattr(ranking, "record_benchmark", record)
        report = REGISTRY.call("ranking_benchmark", {"candidate_id": "candidate"}, ctx)
    finally:
        service.close()

    assert report["candidate"] == "candidate"
    assert persisted_on == [threading.current_thread()]
    saved = ranking.status(vault)["candidates"][0]
    assert saved["benchmark"]["candidate"] == "candidate"


def test_core_backed_sweep_uses_callback_index_access(vault, monkeypatch):
    """The migrated multi-item sweep retains Core-owned index access."""
    from test_intake import RESPONSES, clerk_answers

    scout.CandidateStore(vault).add(
        "acme/rowstream", "https://github.com/acme/rowstream", "CDC repository", "test",
        github={"archived": False, "stars": 1200, "license_spdx": "MIT",
                "pushed_at": "2026-09-01T00:00:00Z", "topics": ["cdc"], "size_kb": 900},
    )
    frozen = scout.freeze_cohort(vault)
    scout.mark_reviewed(vault, frozen["cohort"], "person")
    evaluation = vault.work("eval")
    evaluation.mkdir(parents=True, exist_ok=True)
    (evaluation / "last.json").write_text(json.dumps({"total": 6, "hit": 1.0}), encoding="utf-8")

    service = IndexService(vault)
    ctx = Context(tier="contribute", vault=vault, extras={
        "index_service": service, "clerk": clerk.Scripted(clerk_answers),
        "fetcher": intake.Replay(RESPONSES),
    })
    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        result = REGISTRY.call("sweep", {"limit": 1}, ctx)
    finally:
        service.close()

    assert result["staged"] == 1
    assert result["results"][0]["name"] == "acme - rowstream"


def test_authoring_and_project_writes_keep_sqlite_on_core_and_markdown_on_writer(vault, monkeypatch):
    from resource_librarian.app import App
    from resource_librarian.coordination import on_writer_thread
    from resource_librarian.index import Index
    from resource_librarian.keys import KeyStore
    from resource_librarian.tools import authoring, sessions

    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    index_threads, write_threads, event_threads = [], [], []
    original_upsert = Index.upsert
    original_atomic = authoring.atomic_write_text
    original_event = sessions._event
    def upsert(index, *args, **kwargs):
        index_threads.append(threading.current_thread())
        return original_upsert(index, *args, **kwargs)
    def write(*args, **kwargs):
        write_threads.append(on_writer_thread())
        return original_atomic(*args, **kwargs)
    def event(*args, **kwargs):
        event_threads.append(on_writer_thread())
        return original_event(*args, **kwargs)
    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        monkeypatch.setattr(Index, "upsert", upsert)
        monkeypatch.setattr(authoring, "atomic_write_text", write)
        monkeypatch.setattr(sessions, "atomic_write_text", write)
        monkeypatch.setattr(sessions, "_event", event)
        sid = app.person_call("open_session", {"purpose": "add_project", "question": "Map notes"})["opened"]
        def call(tool_name, **arguments):
            result = app.person_call(tool_name, arguments, sid)
            assert "error" not in result, result
            return result
        call("create_project", name="Map", summary="A project", pursuit_kind="research", stage="planning")
        call("update_project", name="Map", summary="Updated summary", stage="active")
        call("reflection_accept", project="Map", text="The map is useful.")
        call("write_note", folder="Projects/Map", name="Plan", body="## Tasks\n- [ ] Read first 📅 2026-01-01\n")
        call("edit_note", note="Plan", section="Next", text="Compare alternatives.")
        call("task_route", note="Plan", text="Read first", action="reschedule", new_due="2027-01-01")
        archived = call("archive_note", note="Plan", reason="Replaced by the project summary")
        assert archived["path"] == "Archive/Projects/Map/Plan.md"
        assert app.index_service.run(lambda index: index.note_row("Map")["shape"]) == "project"
        assert index_threads and set(index_threads) == {app.index_service._thread}
        assert write_threads and all(write_threads)
        assert event_threads and all(event_threads)
    finally:
        app.close_runtime()


def test_closed_index_refuses_note_creation_before_markdown_changes(vault):
    from resource_librarian.tools import authoring
    service = IndexService(vault)
    service.close()
    ctx = Context(tier="curate", vault=vault, extras={"index_service": service})
    with pytest.raises(RuntimeError, match="closed"):
        authoring.write_note(ctx, "Notes", "Must not exist", "No write")
    assert not (vault.root / "Notes" / "Must not exist.md").exists()


def test_open_brief_releases_core_index_before_clerk_request(vault, monkeypatch):
    from resource_librarian.session import SessionStore
    from resource_librarian.tools import sessions
    service = IndexService(vault)
    store = SessionStore(vault)
    session = store.new("explore", "", "How do we inspect an operating system?")
    def answer(payload):
        # A call back to the index from this thread would block if the Clerk
        # were accidentally running on the index worker under a parent wait.
        assert threading.current_thread() is not service._thread
        assert service.stats()["notes"] >= 0
        return {"queries": ["operating system monitoring"]}
    ctx = Context(tier="contribute", vault=vault, session=session.id,
                  extras={"index_service": service, "clerk": clerk.Scripted(answer)})
    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        result = sessions.open_brief(ctx, "Monitor a host", ["must not require SaaS"])
        assert result["suggested_queries"] == ["operating system monitoring"]
        assert store.load(session.id).briefs["B1"].need == "Monitor a host"
    finally:
        service.close()


def test_session_offering_walk_uses_core_index_without_holding_it_during_review(vault, monkeypatch):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    from test_review_gate import CLAIM, SUMMARY, to_synthesise
    from test_sessions import OSQUERY_LINE, Model
    add_source(vault.root, "osquery", OSQUERY_LINE,
               "Query operating system state such as processes and open sockets.")
    vault.set_setting("clerk", "review_offerings", True)
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    reviewed = []
    def answer(payload):
        assert threading.current_thread() is not app.index_service._thread
        assert app.index_service.stats()["notes"] >= 1
        if payload["task"] == "review":
            reviewed.append(payload)
            return {"verdict": "holds", "counter_quote": "", "reason": "checked"}
        return {"queries": ["operating system state database"]}
    model = Model(vault)
    model.ctx.extras.update(index_service=app.index_service, vault_writer=app.writer,
                            clerk=clerk.Scripted(answer))
    try:
        monkeypatch.setattr(library, "Index", _no_direct_index)
        to_synthesise(model)
        drafted = model.ok("draft_offering", title="Host Plan", summary=SUMMARY, claims=[CLAIM])
        assert reviewed and OSQUERY_LINE in reviewed[0]["user"]
        asked = model.ok("promote_offering", offering=drafted["offering"])
        model.person(asked["question_id"], "yes")
        promoted = model.ok("promote_offering", offering=drafted["offering"])
        assert promoted["findable"] and (vault.root / promoted["path"]).is_file()
    finally:
        app.close_runtime()


def test_project_validation_refreshes_a_changed_content_model_on_core(vault):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    from resource_librarian.schema import MODEL_PATH
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        app.index_service.refresh()
        path = vault.root / MODEL_PATH
        original = path.read_text(encoding="utf-8")
        changed = original.replace("| stage | idea, planning, active, paused, done, dropped |",
                                   "| stage | idea, planning, active, paused, done, dropped, incubating |")
        assert original != changed
        path.write_text(changed, encoding="utf-8")  # A direct human model edit.
        created = app.person_call("create_project", {"name": "New model", "stage": "incubating",
                                                     "summary": "Validate the updated schema"})
        assert "created" in created, created
    finally:
        app.close_runtime()
