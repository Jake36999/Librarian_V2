"""A folder's ingestion as one pipeline, with its counts reconciled (implementation plan M5).

As-is W-ING-01: nothing reconciled what was surveyed, queued, staged, read and accepted. W-FOL-04:
accepting a folder did not lead on to its intake. W-ING-02: a queue nobody drained said nothing.
"""
from __future__ import annotations

import pytest

from resource_librarian import tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context

from test_folder_tools import library, person  # noqa: F401  (fixture)


def surveyed_and_docs_accepted(vault, source, service):
    REGISTRY.call("folder_survey", {"path": str(source)}, person(vault, service))
    card = next(c for c in REGISTRY.call("folder_overview", {}, person(vault, service))["cards"]
                if c["path"] == "docs")
    REGISTRY.call("folder_accept", {"id": card["id"], "folder_fingerprint": card["folder_fingerprint"],
                                    "purpose": "own-docs", "graph": "library-docs"}, person(vault, service))


def test_the_ledger_reconciles_a_folders_counts(library):
    vault, source, service, _ = library
    surveyed_and_docs_accepted(vault, source, service)
    ledger = REGISTRY.call("ingestion_ledger", {"root": str(source)}, person(vault, service))
    assert ledger["folders"] == {"surveyed": 4, "accepted": 1, "waiting": 3}
    assert ledger["documents"]["in_accepted_reference_folders"] == 1      # the PDF in docs/
    assert ledger["documents"]["not_yet_queued"] == 1
    assert "folder card(s) wait for a decision" in ledger["next"]


def test_accepted_reference_folders_are_queued_in_one_call(library):
    vault, source, service, _ = library
    surveyed_and_docs_accepted(vault, source, service)
    out = REGISTRY.call("folder_queue_accepted", {"root": str(source)}, person(vault, service))
    assert out["queued"] == 1 and out["folders"][0]["folder"].endswith("docs")
    ledger = REGISTRY.call("ingestion_ledger", {"root": str(source)}, person(vault, service))
    assert ledger["documents"]["not_yet_queued"] == 0
    assert ledger["sources"].get("queued") == 1


def test_the_ingest_folder_pipeline_runs_to_the_persons_decisions(library):
    vault, source, service, _ = library
    ctx = person(vault, service)
    out = REGISTRY.call("run_pipeline", {"name": "ingest-folder", "inputs": {"path": str(source)}}, ctx)
    assert out["status"] == "finished", out
    # Person mode: policy acceptance is refused and the run goes on; the folders wait for the person.
    assert out["outputs"]["folders"]["surveyed"] == 4
    assert "wait for a decision" in out["outputs"]["next"]



def test_a_folders_ingestion_captures_only_its_own_documents(library):
    # The Resource-Library supervised run (27 November): `run-queue` drained the whole shared queue,
    # oldest first, other folders' and briefs' references included. Now the pipeline captures only the
    # folder's own documents, and every other queued reference is left byte for byte as it was.
    from resource_librarian import intake
    from resource_librarian.staging import StagingStore
    vault, source, service, _ = library
    surveyed_and_docs_accepted(vault, source, service)
    elsewhere = intake.enqueue(vault, "https://example.invalid/a-brief-reference")
    path = StagingStore(vault).path(elsewhere["id"])
    before = path.read_bytes()
    out = REGISTRY.call("run_pipeline", {"name": "ingest-folder", "inputs": {"path": str(source)}},
                        person(vault, service))
    assert out["status"] == "finished", out
    capture = out["steps"]["capture"]
    assert capture["processed"] == 1 and capture["still_waiting_here"] == 0
    assert [i["id"] for i in intake.pending(vault)] == [elsewhere["id"]]
    assert path.read_bytes() == before
    # Without a folder, intake_run drains the queue as before.
    plain = REGISTRY.call("intake_run", {"limit": 5}, person(vault, service))
    assert "still_waiting_here" not in plain

def test_an_undrained_capture_queue_shows_on_the_agenda(library):
    vault, source, service, _ = library
    surveyed_and_docs_accepted(vault, source, service)
    REGISTRY.call("folder_queue_accepted", {"root": str(source)}, person(vault, service))
    agenda = REGISTRY.call("agenda", {}, Context(tier="consult", vault=vault, extras={"caller_kind": "mcp"}))
    assert agenda["queued_for_capture"]["count"] == 1 and agenda["queued_for_capture"]["owner"] == "lead"


def test_the_ingest_folder_pipeline_runs_in_a_core_with_a_vault_writer(library):
    # M5 acceptance (2026-11-27): in the Core, a pipeline's runner sat inside one writer operation,
    # so its orchestrating steps (folder_survey first) were refused ORCHESTRATION_CONTEXT. The test
    # above has no writer, so it passed.
    from resource_librarian.coordination import VaultWriter
    vault, source, service, _ = library
    writer = VaultWriter(vault)
    try:
        ctx = Context(tier="curate", vault=vault, extras={"caller_kind": "person", "folder_service": service,
                                                          "vault_writer": writer})
        out = REGISTRY.call("run_pipeline", {"name": "ingest-folder", "inputs": {"path": str(source)}}, ctx)
    finally:
        writer.close()
    assert out["status"] == "finished", out
    assert out["outputs"]["folders"]["surveyed"] == 4


def test_a_captured_source_is_accounted_for_by_its_file(library):
    # M5 acceptance (2026-11-27): capture keeps the document as `file`, not the queued `ref`, so
    # every accepted source of the run was listed as unaccounted and `sources` was empty.
    from resource_librarian.staging import StagingStore
    vault, source, service, _ = library
    surveyed_and_docs_accepted(vault, source, service)
    REGISTRY.call("folder_queue_accepted", {"root": str(source)}, person(vault, service))
    store = StagingStore(vault)
    [queued] = [i for i in store.items("source") if i.get("status") == "queued"]
    captured = {k: v for k, v in queued.items() if k != "ref"}
    captured.update(status="accepted", file=str(source / "docs" / "paper.pdf").replace("\\", "/"))
    store.save(captured)
    ledger = REGISTRY.call("ingestion_ledger", {"root": str(source)}, person(vault, service))
    assert ledger["sources"] == {"accepted": 1}
    assert ledger["unaccounted_count"] == 0
