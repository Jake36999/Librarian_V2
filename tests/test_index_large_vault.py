"""INDEX-05 deterministic large-vault refresh characterization.

The assertions are correctness and work-shape bounds, not latency budgets.
Durations and artifact sizes are recorded as diagnostics so later packaged
and Python-matrix runs can compare like with like without turning one machine's
speed into a release contract.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

import resource_librarian.index as index_module
from resource_librarian.index import Index, IndexService
from resource_librarian.notes import iter_paths


NOTE_COUNT = 5_000
PAYLOAD_BYTES = 4_800
MODIFIED = 50
RENAMED = 25
DELETED = 25


def _large_note(number: int) -> str:
    marker = f"large-vault-{number:04d}"
    repeated = (f"{marker} evidence remains deterministic. " * 160)
    payload = repeated[:PAYLOAD_BYTES]
    return f"# Scale Note {number:04d}\n\n## Evidence\n\n{payload}\n"


def _metadata(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    return stat.st_mtime_ns, stat.st_size, \
        f"{stat.st_dev}:{stat.st_ino}:{stat.st_ctime_ns}"


def _assert_exact_tree(index: Index) -> None:
    expected = {
        path.relative_to(index.vault.root).as_posix(): _metadata(path)
        for path in iter_paths(index.vault.root)
    }
    actual = {
        row["path"]: (row["mtime_ns"], row["size"], row["file_identity"])
        for row in index.conn.execute(
            "SELECT path, mtime_ns, size, file_identity FROM note")
    }
    assert actual == expected
    assert index.conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not index.conn.in_transaction
    for table in ("chunk", "facet", "link", "component"):
        assert index.conn.execute(
            f"SELECT COUNT(*) FROM {table} AS child LEFT JOIN note "
            "ON note.path = child.path WHERE note.path IS NULL"
        ).fetchone()[0] == 0


@pytest.mark.slow
def test_large_vault_refresh_is_incremental_and_convergent(vault, monkeypatch):
    folder = vault.root / "Scale"
    folder.mkdir()
    paths = []
    for number in range(NOTE_COUNT):
        path = folder / f"Scale Note {number:04d}.md"
        path.write_text(_large_note(number), encoding="utf-8")
        paths.append(path)

    fixture_bytes = sum(path.stat().st_size for path in paths)
    assert 20 * 1024 * 1024 <= fixture_bytes <= 30 * 1024 * 1024
    metrics = {"fixture_notes": NOTE_COUNT, "fixture_bytes": fixture_bytes}

    snapshots: list[str] = []
    snapshot_bytes: list[int] = []
    original_snapshot = index_module.read_bytes_snapshot
    largest_note_bytes = max(path.stat().st_size for path in iter_paths(vault.root)) + 64

    def observed_snapshot(path):
        snapshot = original_snapshot(path)
        snapshots.append(Path(path).relative_to(vault.root).as_posix())
        snapshot_bytes.append(len(snapshot.data))
        # Characterize the per-file payload passed into upsert. This is an IO
        # work-shape bound, not a claim about process RSS or object retention.
        assert len(snapshot.data) <= largest_note_bytes
        return snapshot

    monkeypatch.setattr(index_module, "read_bytes_snapshot", observed_snapshot)
    service = IndexService(vault)
    callback_threads: list[threading.Thread] = []
    index_instances: set[int] = set()

    def verify_on_service(index):
        callback_threads.append(threading.current_thread())
        index_instances.add(id(index))
        _assert_exact_tree(index)

    try:
        all_initial_paths = {
            path.relative_to(vault.root).as_posix() for path in iter_paths(vault.root)
        }
        started = time.perf_counter()
        initial = service.refresh()
        metrics["initial_refresh_seconds"] = round(time.perf_counter() - started, 3)

        assert initial.rebuilt is True
        assert set(initial.upserted) == all_initial_paths
        assert snapshots == sorted(all_initial_paths)
        metrics["initial_snapshot_bytes"] = sum(snapshot_bytes)
        metrics["initial_peak_snapshot_bytes"] = max(snapshot_bytes)
        assert service.stats()["notes"] == len(all_initial_paths)
        service.run(verify_on_service)

        snapshots.clear()
        snapshot_bytes.clear()
        started = time.perf_counter()
        stable = service.refresh()
        metrics["stable_refresh_seconds"] = round(time.perf_counter() - started, 3)
        assert stable.upserted == []
        assert stable.removed == []
        assert stable.reason == ""
        assert stable.unchanged == len(all_initial_paths)
        assert snapshots == []
        assert snapshot_bytes == []

        modified = paths[:MODIFIED]
        renamed = paths[MODIFIED:MODIFIED + RENAMED]
        deleted = paths[MODIFIED + RENAMED:MODIFIED + RENAMED + DELETED]
        for path in modified:
            path.write_text(path.read_text(encoding="utf-8") + "\nmodified once\n",
                            encoding="utf-8")
        rename_pairs = []
        for path in renamed:
            target = path.with_name(f"{path.stem} Renamed.md")
            path.rename(target)
            rename_pairs.append((path, target))
        for path in deleted:
            path.unlink()

        expected_upserts = {
            path.relative_to(vault.root).as_posix() for path in modified
        } | {
            target.relative_to(vault.root).as_posix() for _source, target in rename_pairs
        }
        expected_removed = {
            path.relative_to(vault.root).as_posix() for path in deleted
        } | {
            source.relative_to(vault.root).as_posix() for source, _target in rename_pairs
        }

        snapshots.clear()
        snapshot_bytes.clear()
        started = time.perf_counter()
        changed = service.refresh()
        metrics["incremental_refresh_seconds"] = round(time.perf_counter() - started, 3)
        assert set(changed.upserted) == expected_upserts
        assert set(changed.removed) == expected_removed
        assert changed.reason == ""
        # Modified and rename destinations are the only paths whose bytes are
        # snapshotted; deletions and every unchanged note require metadata only.
        assert snapshots == sorted(expected_upserts)
        metrics["incremental_snapshot_bytes"] = sum(snapshot_bytes)
        metrics["incremental_peak_snapshot_bytes"] = max(snapshot_bytes)

        final_paths = {
            path.relative_to(vault.root).as_posix() for path in iter_paths(vault.root)
        }
        assert final_paths == (all_initial_paths - expected_removed) | expected_upserts
        assert changed.unchanged == len(final_paths) - len(expected_upserts)
        assert service.stats()["notes"] == len(final_paths)
        service.run(verify_on_service)
        for path in [*modified, *(target for _source, target in rename_pairs)]:
            rel = path.relative_to(vault.root).as_posix()
            expected_hash = hashlib.sha256(
                path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()[:24]
            assert service.run(lambda index, rel=rel: index.conn.execute(
                "SELECT hash FROM note WHERE path = ?", (rel,)).fetchone()[0]) == expected_hash

        snapshots.clear()
        snapshot_bytes.clear()
        second_stable = service.refresh()
        assert second_stable.upserted == []
        assert second_stable.removed == []
        assert second_stable.reason == ""
        assert second_stable.unchanged == len(final_paths)
        assert snapshots == []
        assert snapshot_bytes == []
        service.checkpoint()
        service._queue.join()
        assert callback_threads == [service._thread, service._thread]
        assert index_instances == {id(service._index)}
        assert service._queue.unfinished_tasks == 0
        metrics["index_bytes"] = service._index.path.stat().st_size
        print(f"\nlarge-vault metrics: {json.dumps(metrics, sort_keys=True)}")
    finally:
        service.close()
    assert not service._thread.is_alive()
    assert service._index._all == []
