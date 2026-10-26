"""INDEX-05: a moving Markdown tree reconciles to coherent index rows."""
from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
from pathlib import Path

import pytest

from resource_librarian.coordination import atomic_write_text
from resource_librarian.file_access import FileChangedError, read_bytes_snapshot
from resource_librarian.index import Index, IndexService

from conftest import add_source


def _assert_note_snapshot(index: Index, path: Path) -> None:
    rel = path.relative_to(index.vault.root).as_posix()
    row = index.conn.execute("SELECT * FROM note WHERE path = ?", (rel,)).fetchone()
    assert row is not None
    text = path.read_text(encoding="utf-8", errors="replace")
    stat = path.stat()
    assert row["hash"] == hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
    assert (row["mtime"], row["size"]) == (stat.st_mtime, stat.st_size)
    assert row["mtime_ns"] == stat.st_mtime_ns
    assert row["file_identity"] == f"{stat.st_dev}:{stat.st_ino}:{stat.st_ctime_ns}"


def _assert_no_orphan_metadata(index: Index) -> None:
    for table in ("chunk", "facet", "link", "component"):
        count = index.conn.execute(
            f"SELECT COUNT(*) FROM {table} AS child "
            "LEFT JOIN note ON note.path = child.path WHERE note.path IS NULL"
        ).fetchone()[0]
        assert count == 0, f"{table} contains metadata for a missing note"


def test_refresh_reconciles_a_rename_between_scan_and_upsert(vault, monkeypatch):
    source = add_source(vault.root, "Alpha", "first revision")
    target = source.with_name("Alpha Renamed.md")
    with Index(vault) as index:
        index.refresh()
        atomic_write_text(source, source.read_text(encoding="utf-8") + "\nchanged\n")
        original = index.upsert
        raced = False

        def upsert(path, *args, **kwargs):
            nonlocal raced
            if Path(path) == source and not raced:
                raced = True
                source.rename(target)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(index, "upsert", upsert)
        report = index.refresh()

        assert raced
        assert report.removed == ["Sources/repository/Alpha.md"]
        assert report.upserted == ["Sources/repository/Alpha Renamed.md"]
        assert index.note_row("Alpha") is None
        assert index.note_row("Alpha Renamed")["path"] == \
            "Sources/repository/Alpha Renamed.md"
        _assert_note_snapshot(index, target)
        _assert_no_orphan_metadata(index)


def test_initial_rebuild_reconciles_a_rename_during_its_walk(vault, monkeypatch):
    source = add_source(vault.root, "Alpha", "first revision")
    target = source.with_name("Alpha Renamed.md")
    with Index(vault) as index:
        original = index.upsert
        raced = False

        def upsert(path, *args, **kwargs):
            nonlocal raced
            if Path(path) == source and not raced:
                raced = True
                source.rename(target)
            return original(path, *args, **kwargs)

        monkeypatch.setattr(index, "upsert", upsert)
        report = index.refresh()

        assert raced and report.rebuilt
        assert "Sources/repository/Alpha Renamed.md" in report.upserted
        assert index.note_row("Alpha") is None
        assert index.note_row("Alpha Renamed")["path"] == \
            "Sources/repository/Alpha Renamed.md"
        _assert_note_snapshot(index, target)
        _assert_no_orphan_metadata(index)


def test_refresh_reconciles_a_delete_between_scan_and_upsert(vault, monkeypatch):
    source = add_source(vault.root, "Alpha", "first revision")
    with Index(vault) as index:
        index.refresh()
        atomic_write_text(source, source.read_text(encoding="utf-8") + "\nchanged\n")
        original = index.upsert
        raced = False

        def upsert(path, *args, **kwargs):
            nonlocal raced
            if Path(path) == source and not raced:
                raced = True
                source.unlink()
            return original(path, *args, **kwargs)

        monkeypatch.setattr(index, "upsert", upsert)
        report = index.refresh()

        assert raced
        assert report.removed == ["Sources/repository/Alpha.md"]
        assert report.upserted == []
        assert index.note_row("Alpha") is None
        _assert_no_orphan_metadata(index)


def test_refresh_rechecks_metadata_changed_after_an_upsert(vault, monkeypatch):
    source = add_source(vault.root, "Alpha", "first revision")
    with Index(vault) as index:
        index.refresh()
        atomic_write_text(source, source.read_text(encoding="utf-8") + "\nsecond revision\n")
        original = index.upsert
        raced = False

        def upsert(path, *args, **kwargs):
            nonlocal raced
            changed = original(path, *args, **kwargs)
            if Path(path) == source and not raced:
                raced = True
                atomic_write_text(source, source.read_text(encoding="utf-8") +
                                  "\nthird and longer revision\n")
            return changed

        monkeypatch.setattr(index, "upsert", upsert)
        report = index.refresh()

        assert raced
        assert report.upserted == ["Sources/repository/Alpha.md"]
        _assert_note_snapshot(index, source)
        _assert_no_orphan_metadata(index)


def test_index_service_detects_same_size_replacement_with_restored_mtime(vault):
    source = add_source(vault.root, "Alpha", "first revision")
    service = IndexService(vault)
    callbacks = []
    try:
        service.refresh()
        before = source.stat()
        replacement = source.read_bytes().replace(b"first revision", b"other revision")
        temporary = source.with_suffix(".replacement")
        temporary.write_bytes(replacement)
        os.utime(temporary, ns=(before.st_atime_ns, before.st_mtime_ns))
        os.replace(temporary, source)
        after = source.stat()
        assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)

        report = service.refresh()
        service.run(lambda index: (callbacks.append(threading.current_thread()),
                                   _assert_note_snapshot(index, source)))

        assert report.upserted == ["Sources/repository/Alpha.md"]
        assert callbacks == [service._thread]
    finally:
        service.close()


def test_read_bytes_snapshot_refuses_active_same_size_mutation(tmp_path, monkeypatch):
    path = tmp_path / "active.md"
    path.write_bytes(b"first bytes")
    original_open = Path.open
    original_stat = path.stat()

    class MutatingReader:
        def __init__(self):
            self.handle = original_open(path, "r+b")
            self.mutated = False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.handle.close()

        def fileno(self):
            return self.handle.fileno()

        def seek(self, *args):
            return self.handle.seek(*args)

        def read(self, *args):
            data = self.handle.read(*args)
            if not self.mutated:
                self.mutated = True
                self.handle.seek(0)
                self.handle.write(b"other bytes")
                self.handle.flush()
                os.fsync(self.handle.fileno())
                os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            return data

    def open_path(target, *args, **kwargs):
        if target == path and args == ("rb",):
            return MutatingReader()
        return original_open(target, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)
    with pytest.raises(FileChangedError):
        read_bytes_snapshot(path)


def test_index_service_rebuild_removes_stale_component_rows(vault):
    add_source(vault.root, "Alpha", "first revision")
    service = IndexService(vault)
    try:
        service.refresh()

        def add_orphan(index):
            index.conn.execute(
                "INSERT INTO component(path, note, address, revision, evidence) VALUES (?, ?, ?, ?, ?)",
                ("Sources/repository/Gone.md", "Gone", "gone.py", "old", "stale"))
            index.conn.commit()

        service.run(add_orphan)
        assert service.run(lambda index: index.conn.execute(
            "SELECT COUNT(*) FROM component WHERE note = 'Gone'").fetchone()[0]) == 1
        service.refresh(rebuild=True)
        assert service.run(lambda index: index.conn.execute(
            "SELECT COUNT(*) FROM component WHERE note = 'Gone'").fetchone()[0]) == 0
    finally:
        service.close()


def test_rebuild_preserves_non_convergence_reason(vault, monkeypatch):
    add_source(vault.root, "Alpha", "first revision")
    service = IndexService(vault)
    try:
        monkeypatch.setattr(service._index, "_filesystem_metadata",
                            lambda: {"moving.md": (1, 1, "moving")})
        report = service.refresh()
        assert "index has never been built" in report.reason
        assert "Markdown tree remained active" in report.reason
    finally:
        service.close()


def test_schema_v2_index_migrates_then_rebuilds_without_orphans(vault):
    source = add_source(vault.root, "Alpha", "current source truth")
    database = vault.derived / "index.sqlite"
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            CREATE TABLE note (
              path TEXT PRIMARY KEY, name TEXT NOT NULL, name_lower TEXT NOT NULL,
              shape TEXT NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL,
              aliases TEXT NOT NULL, topic TEXT NOT NULL, bottom_line TEXT NOT NULL,
              frontmatter TEXT NOT NULL, hash TEXT NOT NULL, mtime REAL NOT NULL,
              size INTEGER NOT NULL, parse_error TEXT NOT NULL, indexed_at TEXT NOT NULL
            );
            CREATE TABLE component (
              path TEXT NOT NULL, note TEXT NOT NULL, address TEXT NOT NULL,
              revision TEXT NOT NULL, evidence TEXT NOT NULL
            );
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)
        stat = source.stat()
        connection.execute(
            "INSERT INTO note VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Sources/repository/Alpha.md", "Alpha", "alpha", "source", "repository",
             "Legacy Alpha", "", "", "legacy bottom line", "{}", "legacy-hash",
             stat.st_mtime, stat.st_size, "", "2026-10-25T00:00:00Z"))
        connection.execute("INSERT INTO component VALUES (?, ?, ?, ?, ?)",
                           ("Sources/repository/Gone.md", "Gone", "gone.py", "old", "stale"))
        connection.execute("INSERT INTO meta VALUES ('model_hash', 'schema-v2-hash')")

    service = IndexService(vault)
    try:
        before = service.run(lambda index: {
            "columns": {row[1] for row in index.conn.execute("PRAGMA table_info(note)")},
            "title": index.note_row("Alpha")["title"],
            "stale": index.stale_reason(),
        })
        assert {"mtime_ns", "file_identity"} <= before["columns"]
        assert before["title"] == "Legacy Alpha"  # ALTER did not discard the old row.
        assert before["stale"] == "the content model or the index format changed"

        report = service.refresh()
        assert report.rebuilt
        assert report.reason == "the content model or the index format changed"

        def verify(index):
            row = index.note_row("Alpha")
            assert row is not None and row["title"] == "Alpha"
            assert row["mtime_ns"] == source.stat().st_mtime_ns
            assert row["file_identity"]
            assert index.conn.execute(
                "SELECT COUNT(*) FROM component AS child LEFT JOIN note "
                "ON note.path = child.path WHERE note.path IS NULL").fetchone()[0] == 0
            _assert_note_snapshot(index, source)

        service.run(verify)
    finally:
        service.close()
