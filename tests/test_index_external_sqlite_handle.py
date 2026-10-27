"""INDEX-05: fail-safe behavior beside an unsupported foreign SQLite reader.

Adapters never open the derived index directly.  This fixture deliberately
does so to characterize a third-party process that pins a WAL snapshot: Core
work must remain live, a passive checkpoint must report its retained backlog,
and an explicit checkpoint after the reader leaves must converge.
"""
from __future__ import annotations

import os
import sqlite3
import time

import pytest

from resource_librarian.index import IndexService

from conftest import add_source


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="INDEX-05 external-handle characterization is Windows-specific"
)


def test_foreign_reader_pins_wal_without_blocking_core_progress(vault) -> None:
    add_source(vault.root, "Initial", "Initial checkpoint anchor.")
    service = IndexService(vault)
    foreign: sqlite3.Connection | None = None
    worker = service._thread
    try:
        service.refresh()
        baseline_notes = service.stats()["notes"]
        # Start from an empty WAL so the foreign reader's end mark and every
        # subsequently retained frame are deterministic.
        truncated = service.run(
            lambda index: tuple(index.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone())
        )
        assert truncated[0] == 0

        foreign = sqlite3.connect(service.vault.derived / "index.sqlite", timeout=0.1,
                                  isolation_level=None)
        foreign.execute("PRAGMA query_only=ON")
        foreign.execute("BEGIN")
        assert foreign.execute("SELECT COUNT(*) FROM note").fetchone()[0] == baseline_notes

        # Each refresh is coordinated through the sole IndexService worker.
        # The unsupported reader must not prevent writes or ordinary reads.
        for number in range(6):
            add_source(vault.root, f"Foreign{number}", f"Written with reader held: {number}.")
            report = service.refresh()
            assert len(report.upserted) == 1
            assert service.stats()["notes"] == baseline_notes + number + 1
        assert service.run(lambda index: dict(index.note_row("Foreign5")))["name"] == "Foreign5"
        assert service.run(
            lambda index: index.conn.execute("PRAGMA integrity_check").fetchone()[0]
        ) == "ok"
        assert service.run(lambda index: len(index._all)) == 1

        started = time.monotonic()
        pinned = service.checkpoint()
        assert time.monotonic() - started < 2.0
        assert pinned["busy"] is False
        assert pinned["log_frames"] > pinned["checkpointed_frames"] >= 0
        assert pinned["complete"] is False

        # Recovery is explicit: releasing the foreign transaction alone does
        # not claim completion; the next Core checkpoint reports it.
        foreign.rollback()
        foreign.close()
        foreign = None
        recovered = service.checkpoint()
        assert recovered["busy"] is False
        assert recovered["log_frames"] == recovered["checkpointed_frames"]
        assert recovered["complete"] is True
        assert service.stats()["notes"] == baseline_notes + 6
        assert service.run(
            lambda index: index.conn.execute("PRAGMA integrity_check").fetchone()[0]
        ) == "ok"
    finally:
        if foreign is not None:
            foreign.close()
        service.close()

    assert not worker.is_alive()
