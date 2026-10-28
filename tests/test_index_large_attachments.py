"""INDEX-05: large managed attachments remain streamed under real promotion.

This is a work-shape characterization, not a latency or RSS benchmark. It
keeps the current repeated-fingerprint cost visible while pinning the safety
boundary: every attachment read is explicitly bounded, unrelated Core reads
stay live, and the accepted copies exactly match their retained originals.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

from resource_librarian import notes, staging

from test_core_source_promotion import core  # noqa: F401  (shared real-Core fixture)


MIB = 1 << 20
RAW_SIZE = 64 * MIB
CLEAN_SIZE = 16 * MIB


def _stream_create(path: Path, size: int, byte: int) -> str:
    """Create and hash a deterministic non-sparse file in 1 MiB blocks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    block = bytes([byte]) * MIB
    digest = hashlib.sha256()
    remaining = size
    with path.open("wb") as handle:
        while remaining:
            part = block[:min(len(block), remaining)]
            handle.write(part)
            digest.update(part)
            remaining -= len(part)
    return digest.hexdigest()


def _stream_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(MIB), b""):
            size += len(block)
            digest.update(block)
    return size, digest.hexdigest()


class _TrackedReader:
    def __init__(self, handle, path: Path, reads: dict[str, object]):
        self._handle = handle
        self._path = path
        self._reads = reads

    def read(self, size: int = -1):
        assert 0 < size <= MIB, f"unbounded attachment read for {self._path}: {size}"
        first = self._reads["first"]
        allow = self._reads["allow"]
        assert isinstance(first, threading.Event) and isinstance(allow, threading.Event)
        if not first.is_set():
            first.set()
            assert allow.wait(20), "concurrent read probe did not release attachment scan"
        block = self._handle.read(size)
        self._reads["bytes"] = int(self._reads["bytes"]) + len(block)
        self._reads["calls"] = int(self._reads["calls"]) + 1
        self._reads["peak"] = max(int(self._reads["peak"]), len(block))
        by_path = self._reads["by_path"]
        assert isinstance(by_path, dict)
        key = self._path.as_posix()
        by_path[key] = int(by_path.get(key, 0)) + len(block)
        return block

    def __enter__(self):
        self._handle.__enter__()
        return self

    def __exit__(self, *args):
        return self._handle.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self._handle, name)


@pytest.mark.slow
def test_large_source_attachments_stream_and_leave_unrelated_reads_live(core, monkeypatch):
    raw = core.vault.root / "Project/docs/paper.pdf"
    clean = core.vault.work("staging") / "files/paper.md"
    raw_hash = _stream_create(raw, RAW_SIZE, 0x17)
    clean_hash = _stream_create(clean, CLEAN_SIZE, 0x61)

    destination = core.vault.root / "Sources/document/files"
    raw_copy = destination / "paper.pdf"
    clean_copy = destination / "paper (clean text).md"
    watched = {path.resolve() for path in (raw, clean, raw_copy, clean_copy)}
    reads: dict[str, object] = {
        "bytes": 0,
        "calls": 0,
        "peak": 0,
        "by_path": {},
        "first": threading.Event(),
        "allow": threading.Event(),
    }
    active = True
    path_type = type(raw)
    original_open = path_type.open

    def tracked_open(path, mode="r", *args, **kwargs):
        handle = original_open(path, mode, *args, **kwargs)
        if active and "r" in mode and "b" in mode and path.resolve() in watched:
            return _TrackedReader(handle, path.resolve(), reads)
        return handle

    monkeypatch.setattr(path_type, "open", tracked_open)

    outcome: list[dict | BaseException] = []

    def accept() -> None:
        try:
            outcome.append(core.person_call("staging_decide", {
                "item_ids": ["new-widget"], "decision": "accept",
            }))
        except BaseException as exc:  # make background failures assertable
            outcome.append(exc)

    started = time.monotonic()
    worker = threading.Thread(target=accept, daemon=True, name="large-attachment-accept")
    worker.start()
    first = reads["first"]
    allow = reads["allow"]
    assert isinstance(first, threading.Event) and isinstance(allow, threading.Event)
    try:
        assert first.wait(20), "promotion never began reading a managed attachment"
        concurrent_started = time.monotonic()
        browser = core.person_call("get_note", {"name": "other-0"})
        cowork = core.mcp_call("vault_status", {}, tier="contribute")["result"]
        concurrent_seconds = time.monotonic() - concurrent_started
        assert concurrent_seconds < 5.0
        assert browser["found"] is True
        assert "error" not in cowork and cowork["vault"] == str(core.vault.root)
    finally:
        allow.set()

    worker.join(180)
    assert not worker.is_alive(), "large-attachment acceptance did not finish in three minutes"
    active = False
    assert len(outcome) == 1 and not isinstance(outcome[0], BaseException), outcome
    result = outcome[0]
    assert isinstance(result, dict) and result["accepted"] == 1, result
    promoted = result["results"][0]
    assert promoted["promotion"]["catalogued"] is True
    assert set(promoted["originals_retained"]) == {
        "Project/docs/paper.pdf", ".librarian/staging/files/paper.md",
    }

    assert _stream_digest(raw) == (RAW_SIZE, raw_hash)
    assert _stream_digest(clean) == (CLEAN_SIZE, clean_hash)
    assert _stream_digest(raw_copy) == (RAW_SIZE, raw_hash)
    assert _stream_digest(clean_copy) == (CLEAN_SIZE, clean_hash)
    assert not list(destination.glob(".*.tmp"))

    source = core.vault.root / promoted["promotion"]["path"]
    accepted = notes.load(source)
    assert accepted.frontmatter["file"] == "Sources/document/files/paper.pdf"
    assert accepted.frontmatter["file_markdown"] == \
        "Sources/document/files/paper (clean text).md"
    assert staging.StagingStore(core.vault).load("new-widget")["status"] == "accepted"
    indexed = core.index_service.run(lambda index: dict(index.note_row("New Widget")))
    assert indexed["path"] == source.relative_to(core.vault.root).as_posix()
    assert core.index_service.run(
        lambda index: index.conn.execute("PRAGMA integrity_check").fetchone()[0]
    ) == "ok"

    assert core.writer.flush(10)
    core.index_service.run(lambda index: None)
    assert core.writer._queue.unfinished_tasks == 0
    assert core.index_service._queue.unfinished_tasks == 0

    elapsed = time.monotonic() - started
    logical_bytes = RAW_SIZE + CLEAN_SIZE
    scanned = int(reads["bytes"])
    metrics = {
        "logical_attachment_bytes": logical_bytes,
        "attachment_read_bytes": scanned,
        "scan_amplification": round(scanned / logical_bytes, 2),
        "read_calls": int(reads["calls"]),
        "peak_read_bytes": int(reads["peak"]),
        "concurrent_read_seconds": round(concurrent_seconds, 3),
        "elapsed_seconds": round(elapsed, 3),
        "by_path": {
            Path(path).resolve().relative_to(core.vault.root.resolve()).as_posix(): size
            for path, size in dict(reads["by_path"]).items()
        },
    }
    print("INDEX05_LARGE_ATTACHMENT " + json.dumps(metrics, sort_keys=True))
    assert metrics["peak_read_bytes"] <= MIB
    assert scanned >= logical_bytes * 2  # at least fingerprint plus streamed copy
    assert scanned <= logical_bytes * 8  # two final source/destination checks remain

    writer = core.writer
    index_service = core.index_service
    assert core.close_runtime() is True
    assert not writer.alive
    assert index_service._closed.is_set() and not index_service._thread.is_alive()
