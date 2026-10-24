"""Single-Core coordination for a mutable Librarian vault.

The vault deliberately remains ordinary Markdown, so Obsidian and a person may
edit it directly.  Librarian-originated writes, however, must not race each
other.  This module provides the small local authority used by the app/loop:

* :class:`VaultCoordinator` holds one inter-process lease for a vault;
* :class:`VaultWriter` serialises Librarian mutations and records operations;
* :class:`DocumentLeases` gives an Obsidian editor a short, note-level write
  reservation without locking the whole vault.

It does not attempt to lock a person's editor.  A current human lease causes a
Librarian write to pause before it replaces that specific note, which is safer
than overwriting an unsaved or continuously saved Obsidian buffer.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import queue
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

from . import __version__, process_identity
from .rules import Refusal
from .vault import Vault, now_iso

try:  # Windows is the supported desktop target; POSIX keeps tests portable.
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover - POSIX only
    msvcrt = None
try:  # pragma: no cover - Windows has no fcntl
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows only
    fcntl = None

T = TypeVar("T")
LEASE_SECONDS = 10.0
DEBOUNCE_SECONDS = 1.0


class LeaseHeldError(RuntimeError):
    """Another Core currently owns the mutable vault lease."""


class StaleLeaseError(LeaseHeldError):
    """A dead Core left diagnostic metadata that needs an explicit takeover."""


class DocumentBusyError(Refusal):
    """A human is actively editing a note a Librarian action wants to replace."""

    def __init__(self, path: str, editor: str = "a person") -> None:
        super().__init__("DOCUMENT_ACTIVE",
                         f"{path} is being edited by {editor}; wait for the edit to settle or "
                         "resolve the document checkpoint before writing it")


class PreconditionChangedError(DocumentBusyError):
    """A note changed after the caller captured the revision it intended to edit.

    This deliberately remains a ``DOCUMENT_ACTIVE`` refusal.  The browser and
    Obsidian already know how to turn that refusal into a document-conflict
    checkpoint, and a changed revision needs the same person-facing recovery
    path as an actively dirty editor.
    """

    def __init__(self, path: str) -> None:
        super().__init__(path, "a document that changed after this operation was queued")


def fingerprint(path: Path) -> str:
    """A cheap content fingerprint used as a write precondition."""
    if not path.is_file():
        return "missing"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:20]


@dataclass(frozen=True)
class LeaseInfo:
    instance_id: str
    pid: int
    started_at: str
    protocol_version: str
    core_version: str
    vault: str
    # Creation time of the lease holder, so a later takeover check cannot
    # mistake a recycled PID for the original Core.
    process_started: float | None = None


class VaultCoordinator:
    """An exclusive advisory lease held for an app process's vault lifetime."""

    # `flock` is process-scoped on POSIX, so two test/server objects in the
    # same process would otherwise appear to acquire the same vault.  The
    # operating-system lock remains the cross-process authority; this small
    # guard makes the single-Core invariant true inside one process too.
    _process_guard = threading.RLock()
    _process_paths: set[str] = set()

    def __init__(self, vault: Vault, *, protocol_version: str = "1") -> None:
        self.vault = vault
        self.protocol_version = protocol_version
        self.runtime = vault.librarian / "runtime"
        self.path = self.runtime / "vault.lock"
        self.info_path = self.runtime / "vault.lease.json"
        self._file: Any = None
        self.info = LeaseInfo(secrets.token_hex(12), os.getpid(), now_iso(), protocol_version,
                              __version__, str(vault.root),
                              process_identity.process_started_at(os.getpid()))

    def acquire(self, *, takeover: bool = False) -> LeaseInfo:
        if self._file is not None:
            return self.info
        self.runtime.mkdir(parents=True, exist_ok=True)
        canonical = str(self.path.resolve()).casefold()
        with self._process_guard:
            if canonical in self._process_paths:
                raise LeaseHeldError("another Librarian Core in this process owns this vault")
        handle = open(self.path, "a+b")
        claimed_process = False
        try:
            # Lock a stable byte.  Windows requires a byte to exist first.
            handle.seek(0)
            if not handle.read(1):
                handle.seek(0)
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            if msvcrt is not None:
                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError as exc:
                    raise LeaseHeldError(self._held_message()) from exc
            elif fcntl is not None:  # pragma: no cover - POSIX CI support
                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError as exc:
                    raise LeaseHeldError(self._held_message()) from exc
            else:  # pragma: no cover - exotic platform safeguard
                raise LeaseHeldError("this platform has no supported file-lock primitive")
            # A lock sidecar is diagnostic rather than authoritative.  If a
            # crashed Core left it behind, do not silently overwrite the only
            # useful clue for the person: require a conscious takeover.
            previous = self.status()
            if previous and previous.get("instance_id") != self.info.instance_id:
                pid = int(previous.get("pid") or 0)
                # The process-local guard above proves that a diagnostic row
                # with our own PID cannot belong to a still-held Core.  This
                # happens after a normal in-process switch if the prior
                # sidecar could not be deleted (for example a transient AV
                # lock), and it is safe to replace once the OS lock is ours.
                # Our PID alone is not enough: a crashed Core whose PID was
                # recycled to us is a stale lease, which needs a takeover.
                same_process_recovery = pid == os.getpid() and \
                    self._pid_alive(pid, previous.get("process_started"))
                if self._pid_alive(pid, previous.get("process_started")) and not same_process_recovery:
                    raise LeaseHeldError(self._held_message())
                if not same_process_recovery and not takeover:
                    raise StaleLeaseError("a prior Librarian Core appears to have stopped "
                                          f"(pid {pid or '?'}, started "
                                          f"{previous.get('started_at', '?')}); rerun with an "
                                          "explicit vault takeover after checking it is not active")
            self._file = handle
            with self._process_guard:
                self._process_paths.add(canonical)
                claimed_process = True
            self._write_info()
            return self.info
        except Exception:
            self._file = None
            if claimed_process:
                with self._process_guard:
                    self._process_paths.discard(canonical)
            handle.close()
            raise

    @staticmethod
    def _pid_alive(pid: int, started: float | None = None) -> bool:
        # The shared platform-aware check: on Windows `os.kill(pid, 0)` reports
        # an exited process as alive while any handle to it is open.  An
        # inaccessible process still counts as alive, so takeover stays explicit.
        return process_identity.is_alive(pid, started)

    def _held_message(self) -> str:
        current = self.status()
        if current:
            return ("another Librarian Core owns this vault "
                    f"(pid {current.get('pid', '?')}, started {current.get('started_at', '?')})")
        return "another Librarian Core owns this vault"

    def _write_info(self) -> None:
        payload = json.dumps(asdict(self.info), indent=2, sort_keys=True) + "\n"
        atomic_write_text(self.info_path, payload)

    def status(self) -> dict[str, Any]:
        try:
            data = json.loads(self.info_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    @property
    def held(self) -> bool:
        return self._file is not None

    def release(self) -> None:
        handle, self._file = self._file, None
        if handle is None:
            return
        try:
            # Remove our diagnostic row while the OS lock is still held.  If
            # this happened after unlocking, a new Core could write its row
            # between the identity check and unlink, losing useful evidence.
            status = self.status()
            if status.get("instance_id") == self.info.instance_id:
                with contextlib.suppress(OSError):
                    self.info_path.unlink()
            handle.seek(0)
            if msvcrt is not None:
                with contextlib.suppress(OSError):
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            elif fcntl is not None:  # pragma: no cover - POSIX CI support
                with contextlib.suppress(OSError):
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()
            with self._process_guard:
                self._process_paths.discard(str(self.path.resolve()).casefold())

    def __enter__(self) -> "VaultCoordinator":
        self.acquire()
        return self

    def __exit__(self, *_: Any) -> None:
        self.release()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Atomically replace a text file in its own directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        with temp.open("w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        with contextlib.suppress(OSError):
            temp.unlink()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Atomically replace binary attachment/output bytes in their own directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        with contextlib.suppress(OSError):
            temp.unlink()


@dataclass
class DocumentLease:
    path: str
    editor: str
    baseline: str
    dirty: bool
    touched: float

    @property
    def expires_at(self) -> float:
        return self.touched + LEASE_SECONDS


class DocumentLeases:
    """In-memory note-level editing leases sent by an adapter/editor."""

    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self._leases: dict[str, DocumentLease] = {}
        self._changed: dict[str, float] = {}
        self._suppress_until: dict[str, float] = {}
        # A time-only suppression can expire while a laptop is asleep between
        # an atomic Core write and the watcher's next poll.  Remember the
        # content fingerprint as well, so that delayed observation of that
        # exact Core replacement is never mistaken for a human edit.
        self._core_fingerprints: dict[str, tuple[str, float]] = {}
        self._lock = threading.RLock()

    def heartbeat(self, path: str, *, editor: str = "Obsidian", dirty: bool = True,
                  baseline: str = "") -> dict[str, Any]:
        target = self.vault.safe_relative(path)
        rel = target.relative_to(self.vault.root).as_posix()
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            self._leases[rel] = DocumentLease(rel, editor[:80] or "Obsidian",
                                               baseline or fingerprint(target), bool(dirty), now)
        return self.view(rel)

    def release(self, path: str, *, editor: str = "") -> None:
        target = self.vault.safe_relative(path)
        rel = target.relative_to(self.vault.root).as_posix()
        with self._lock:
            lease = self._leases.get(rel)
            if lease is not None and (not editor or lease.editor == editor):
                self._leases.pop(rel, None)

    def observe_change(self, path: str) -> None:
        target = self.vault.safe_relative(path)
        rel = target.relative_to(self.vault.root).as_posix()
        with self._lock:
            now = time.monotonic()
            known = self._core_fingerprints.get(rel)
            if known is not None and known[0] == fingerprint(target):
                self._core_fingerprints.pop(rel, None)
                self._changed.pop(rel, None)
                return
            if now < self._suppress_until.get(rel, 0.0):
                return
            self._changed[rel] = now

    def note_core_write(self, paths: list[str] | tuple[str, ...]) -> None:
        """Avoid treating the Core's own atomic replacement as a human edit."""
        with self._lock:
            until = time.monotonic() + DEBOUNCE_SECONDS * 2
            for path in paths:
                try:
                    target = self.vault.safe_relative(path)
                    rel = target.relative_to(self.vault.root).as_posix()
                except (OSError, ValueError, Refusal):
                    continue
                self._suppress_until[rel] = until
                self._core_fingerprints[rel] = (fingerprint(target), time.monotonic() + 60.0)
                self._changed.pop(rel, None)

    def quiet(self, path: str) -> bool:
        target = self.vault.safe_relative(path)
        rel = target.relative_to(self.vault.root).as_posix()
        with self._lock:
            return time.monotonic() - self._changed.get(rel, 0.0) >= DEBOUNCE_SECONDS

    def assert_writable(self, paths: list[str] | tuple[str, ...]) -> None:
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            for path in paths:
                target = self.vault.safe_relative(path)
                rel = target.relative_to(self.vault.root).as_posix()
                changed = self._changed.get(rel, 0.0)
                if changed and now - changed < DEBOUNCE_SECONDS:
                    raise DocumentBusyError(rel, "an editor saving this note")
                lease = self._leases.get(rel)
                # An adapter sends a lease only for the short period in which
                # it considers this document actively edited.  Even a clean
                # heartbeat is a current editor/read lease: replacing the
                # note beneath that editor is still surprising, and it is
                # inexpensive to pause only this document for its ten-second
                # expiry.
                if lease is not None:
                    raise DocumentBusyError(rel, lease.editor)

    def view(self, path: str = "") -> dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            leases = [l for l in self._leases.values() if not path or l.path == path]
            return {"leases": [{"path": l.path, "editor": l.editor, "dirty": l.dirty,
                                 "expires_in": max(0, round(l.expires_at - now, 1)),
                                 "baseline": l.baseline}
                                for l in sorted(leases, key=lambda x: x.path)]}

    def _expire(self, now: float) -> None:
        self._leases = {p: l for p, l in self._leases.items() if l.expires_at > now}
        self._changed = {p: t for p, t in self._changed.items() if now - t < 60.0}
        self._suppress_until = {p: t for p, t in self._suppress_until.items() if t > now}
        self._core_fingerprints = {p: row for p, row in self._core_fingerprints.items()
                                   if row[1] > now}


class VaultWatcher:
    """Small polling watcher for direct Markdown edits outside Librarian.

    Polling avoids adding a native watcher dependency to a Windows-local Core
    and coalesces Obsidian's rapid temp/save sequence through DocumentLeases'
    one-second quiet window.  It watches visible Markdown only, never SQLite
    or internal state.
    """

    def __init__(self, vault: Vault, leases: DocumentLeases, interval: float = 0.35) -> None:
        self.vault, self.leases, self.interval = vault, leases, max(0.1, interval)
        self._known: dict[str, tuple[int, int]] = {}
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"librarian-watch-{vault.root.name}")

    def start(self) -> None:
        self._known = self._snapshot()
        self._thread.start()

    def close(self, timeout: float = 2.0) -> None:
        self._closed.set()
        self._thread.join(timeout)

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        rows: dict[str, tuple[int, int]] = {}
        try:
            paths = self.vault.root.rglob("*.md")
            for path in paths:
                try:
                    rel = path.relative_to(self.vault.root)
                    if any(part.startswith(".") for part in rel.parts):
                        continue
                    stat = path.stat()
                    rows[rel.as_posix()] = (stat.st_mtime_ns, stat.st_size)
                except OSError:
                    continue
        except OSError:
            pass
        return rows

    def _run(self) -> None:
        while not self._closed.wait(self.interval):
            self.scan_once()

    def scan_once(self) -> None:
        """Observe one coalesced Markdown snapshot.

        A deletion is an edit too.  Without the second loop a Core write
        could silently recreate a note a person had just removed in Obsidian.
        Keeping this method small and public-ish also makes the deletion race
        deterministic to exercise without a timing-sensitive watcher test.
        """
        latest = self._snapshot()
        for rel, stamp in latest.items():
            if self._known.get(rel) != stamp:
                self.leases.observe_change(rel)
        for rel in set(self._known) - set(latest):
            self.leases.observe_change(rel)
        self._known = latest


@dataclass
class Operation:
    id: str
    caller: str
    targets: list[str]
    started_at: str
    # Captured by the actor immediately before it invokes the mutation, not
    # when a caller happened to enqueue it. This makes the audit record useful
    # when several agents were queued against the same note.
    precondition_fingerprints: dict[str, str] = field(default_factory=dict)
    # The actual revision seen by the actor immediately before it invoked the
    # mutation.  Keeping this separate from a caller's expected revision
    # makes a conflict auditable rather than silently replacing the expected
    # value with the newer one.
    observed_fingerprints: dict[str, str] = field(default_factory=dict)
    # Never persist arbitrary tool output here: output can contain source text
    # or an accidental credential. The durable event records a compact,
    # inspectable outcome shape and digest instead.
    result: dict[str, Any] = field(default_factory=dict)
    finished_at: str = ""
    status: str = "queued"
    detail: str = ""


# Writer threads, so a wait for a person on one keeps serving its queue.
_WRITER_THREADS: dict[threading.Thread, "VaultWriter"] = {}
_WRITER_THREADS_GUARD = threading.Lock()


def wait_for_person(event: threading.Event, timeout: float | None) -> bool:
    """Wait for a person's answer; on a vault writer's thread, keep serving it.

    Before this, a question asked inside a writer operation held the writer,
    so the person's answer - also a write - waited behind it until the
    question timed out, and the thread was parked unanswered.
    """
    with _WRITER_THREADS_GUARD:
        writer = _WRITER_THREADS.get(threading.current_thread())
    return writer.serve_until(event, timeout) if writer is not None else event.wait(timeout)


class VaultWriter:
    """One serial worker for Librarian-originated mutations in a vault."""

    def __init__(self, vault: Vault, leases: DocumentLeases | None = None) -> None:
        self.vault = vault
        self.leases = leases or DocumentLeases(vault)
        self._queue: queue.Queue[tuple[Operation, Callable[[], Any], threading.Event, list[Any]]] = queue.Queue()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"librarian-writer-{vault.root.name}")
        self._thread.start()
        with _WRITER_THREADS_GUARD:
            _WRITER_THREADS[self._thread] = self

    @property
    def log_path(self) -> Path:
        return self.vault.librarian / "runtime" / "operations.jsonl"

    def submit(self, fn: Callable[[], T], *, caller: str = "core",
               targets: list[str] | tuple[str, ...] = (),
               preconditions: dict[str, str] | None = None,
               timeout: float | None = None) -> T:
        # A macro is itself a writer operation and invokes ordinary registry
        # tools.  Re-queueing from the sole worker would deadlock; nested calls
        # are already serial because this worker owns the operation.
        if threading.current_thread() is self._thread:
            # A macro may call ordinary registered tools while the outer macro
            # already owns this actor.  Run the nested operation inline rather
            # than re-queueing and deadlocking, but still produce its own
            # durable operation trail and enforce its own target revision.
            op = Operation(secrets.token_hex(8), caller[:80], list(targets), now_iso(),
                           precondition_fingerprints=dict(preconditions or {}))
            try:
                return self._invoke(op, fn)
            except Exception as exc:
                op.status = "failed"
                op.detail = f"{type(exc).__name__}: {str(exc)[:300]}"
                op.result = _operation_error(exc)
                raise
            finally:
                op.finished_at = now_iso()
                # Avoid masking the domain error with a best-effort final
                # audit append.  A failure to write the initial event occurs
                # before the mutation in _invoke and is still propagated.
                with contextlib.suppress(Exception):
                    self._record(op)
        if self._closed.is_set():
            raise RuntimeError("vault writer is closed")
        op = Operation(secrets.token_hex(8), caller[:80], list(targets), now_iso(),
                       precondition_fingerprints=dict(preconditions or {}))
        done, box = threading.Event(), []
        self._queue.put((op, fn, done, box))
        if not done.wait(timeout):
            raise TimeoutError(f"vault operation {op.id} did not finish")
        kind, value = box[0]
        if kind == "error":
            raise value
        return value

    def _run(self) -> None:
        while not self._closed.is_set() or not self._queue.empty():
            try:
                item = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self._serve(item)

    def _serve(self, item: tuple[Operation, Callable[[], Any], threading.Event, list[Any]]) -> None:
        op, fn, done, box = item
        try:
            value = self._invoke(op, fn)
            box.append(("ok", value))
        except Exception as exc:  # preserve the exact domain refusal for callers
            op.status = "failed"
            op.detail = f"{type(exc).__name__}: {str(exc)[:300]}"
            op.result = _operation_error(exc)
            box.append(("error", exc))
        finally:
            op.finished_at = now_iso()
            try:
                self._record(op)
            except Exception as audit_error:  # never strand a waiting caller
                # A completed mutation with a failed final audit write is
                # not safe to report as a normal success.  The first
                # record is deliberately written before the mutation, so
                # this rare case remains diagnosable without hanging the
                # UI or killing the actor thread.
                if not box or box[-1][0] == "ok":
                    box[:] = [("error", RuntimeError(
                        f"vault operation {op.id} completed but its audit event could not be written: "
                        f"{type(audit_error).__name__}"))]
            finally:
                done.set()
                self._queue.task_done()

    def serve_until(self, event: threading.Event, timeout: float | None) -> bool:
        """Wait for `event` on the writer thread while still serving the queue.

        An operation that asks a person (ask_user, a promotion confirmation)
        runs here, and the person's answer is itself a write: blocking this
        thread would queue the answer behind the question until it timed out.
        Queued operations run one at a time on this same thread, so writes stay
        serial and ordered while the asking operation waits at its question.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        while not event.is_set():
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return False
            try:
                item = self._queue.get(timeout=0.05 if remaining is None else min(0.05, remaining))
            except queue.Empty:
                continue
            self._serve(item)
        return True

    def _invoke(self, op: Operation, fn: Callable[[], T]) -> T:
        """Run one serialized mutation with revision and audit protection."""
        op.status = "running"
        # Do this inside the actor after all preceding operations have
        # committed, then enforce document leases before the write.  A
        # supplied fingerprint is an actual compare-and-swap precondition;
        # actor-generated values document the revision seen for operations
        # that did not originate from a read-modify-write workflow.
        for path in op.targets:
            try:
                observed = fingerprint(self.vault.safe_relative(path))
            except (OSError, ValueError, Refusal):
                observed = "unreadable"
            op.observed_fingerprints[path] = observed
            expected = op.precondition_fingerprints.get(path)
            if expected is not None and expected != observed:
                raise PreconditionChangedError(path)
            op.precondition_fingerprints.setdefault(path, observed)
        # Do not mutate a vault if its durable operation-start event cannot be
        # recorded.  This also makes disk-full/permission failures explicit.
        self._record(op)
        self.leases.assert_writable(op.targets)
        value = fn()
        self.leases.note_core_write(op.targets)
        op.status = "done"
        op.result = _operation_result(value)
        return value

    def _record(self, op: Operation) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(op), ensure_ascii=False) + "\n"
        # The writer is the only local producer, so append is serial and no
        # separate file lock is needed inside this process.
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())

    def flush(self, timeout: float | None = None) -> bool:
        start = time.monotonic()
        while self._queue.unfinished_tasks:
            if timeout is not None and time.monotonic() - start >= timeout:
                return False
            time.sleep(0.02)
        return True

    def close(self, timeout: float = 5.0) -> None:
        self.flush(timeout)
        self._closed.set()
        self._thread.join(timeout)
        with _WRITER_THREADS_GUARD:
            _WRITER_THREADS.pop(self._thread, None)


def _operation_result(value: Any) -> dict[str, Any]:
    """Compact a tool result for durable operation auditing without copying it.

    The full tool/session trace remains in its purpose-specific store. The
    writer log needs to answer "what did this operation report?" while never
    becoming another unbounded or secret-bearing content archive.
    """
    if isinstance(value, dict):
        summary: dict[str, Any] = {"outcome": "ok", "type": "object",
                                   "keys": sorted(str(key)[:80] for key in value)[:40]}
        for key in ("status", "outcome", "error", "refused", "id"):
            if key in value and isinstance(value[key], (str, int, float, bool)):
                summary[key] = str(value[key])[:240]
        try:
            digest_source = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
        except (TypeError, ValueError):
            # A result can contain a circular/debug object.  It must not make
            # an already-completed write appear to have failed merely because
            # the compact audit digest could not serialise that object.
            digest_source = repr(value)
    elif isinstance(value, (str, int, float, bool)) or value is None:
        summary = {"outcome": "ok", "type": type(value).__name__}
        digest_source = repr(value)
    else:
        summary = {"outcome": "ok", "type": type(value).__name__}
        digest_source = repr(value)
    summary["digest"] = hashlib.sha256(digest_source.encode("utf-8", "replace")).hexdigest()[:20]
    return summary


def _operation_error(exc: Exception) -> dict[str, Any]:
    return {"outcome": "error", "type": type(exc).__name__,
            "digest": hashlib.sha256(str(exc).encode("utf-8", "replace")).hexdigest()[:20]}
