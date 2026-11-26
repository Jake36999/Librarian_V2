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


def test_an_undrained_capture_queue_shows_on_the_agenda(library):
    vault, source, service, _ = library
    surveyed_and_docs_accepted(vault, source, service)
    REGISTRY.call("folder_queue_accepted", {"root": str(source)}, person(vault, service))
    agenda = REGISTRY.call("agenda", {}, Context(tier="consult", vault=vault, extras={"caller_kind": "mcp"}))
    assert agenda["queued_for_capture"]["count"] == 1 and agenda["queued_for_capture"]["owner"] == "lead"
