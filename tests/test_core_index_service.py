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
