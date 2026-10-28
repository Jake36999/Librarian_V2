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
from .file_access import file_access
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
        Refusal.__init__(self, "DOCUMENT_ACTIVE",
                         f"{path} changed after it was read (an edit made outside this call), "
                         "so it was not overwritten: read it again and reapply the change, or "
                         "resolve the write-conflict checkpoint")


class OperationLogUnreadableError(RuntimeError):
    """The Core cannot safely admit mutation without reading its audit log."""


MISSING = "missing"                      # the fingerprint of a file that does not exist


def operation_path(vault: Vault, rel: str) -> Path:
    """Internal operation dependencies may include owned operational state.

    Public file APIs still use Vault.safe_relative and cannot read dot-folders.
    No operation dependency may reach another hidden root or escape by a link.
    """
    parts = str(rel).replace("\\", "/").split("/")
    if parts and parts[0] in {".librarian", ".evidence"}:
        if len(parts) < 2 or any(part in ("", ".", "..") or ":" in part for part in parts):
            raise Refusal("VAULT_REQUIRED", "invalid operational state dependency")
        target = vault.root.joinpath(*parts).resolve()
        state_root = vault.root.resolve() / parts[0]
        if state_root not in target.parents:
            raise Refusal("VAULT_REQUIRED", "operational state dependency escapes its state root")
        return target
    return vault.safe_relative(rel)


def fingerprint_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:20]


def fingerprint(path: Path) -> str:
    """A cheap content fingerprint used as a write precondition."""
    with file_access(path):
        if not path.is_file():
            return MISSING
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                digest.update(block)
        return digest.hexdigest()[:20]


@dataclass(frozen=True)
class LeaseInfo:
    instance_id: str
    pid: int
    started_at: str
    protocol_version: str
    core_version: str
    vault: str
    # Exact start identity of the lease holder, so a later takeover check
    # cannot mistake a recycled PID for the original Core.
    process_start: str | None = None


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
                              process_identity.process_start(os.getpid()))

    def acquire(self, *, takeover: bool = False) -> LeaseInfo:
        if self._file is not None:
            return self.info
        self.runtime.mkdir(parents=True, exist_ok=True)
        canonical = str(self.path.resolve()).casefold()
        with self._process_guard:
            if canonical in self._process_paths:
                raise LeaseHeldError("another Librarian Core in this process owns this vault")
        try:
            handle = open(self.path, "a+b")
        except PermissionError as exc:
            # A live Windows owner can deny even opening the byte-range lock
            # file through a second CRT handle. That is the same ownership
            # outcome as LK_NBLCK failing below. Preserve unrelated ACL,
            # read-only-volume and security-software failures when no exact
            # live foreign owner is recorded.
            if self._live_foreign_owner():
                raise LeaseHeldError(self._held_message()) from exc
            raise
        claimed_process = False
        try:
            # Lock a stable byte.  Windows requires a byte to exist first.
            handle.seek(0)
            try:
                present = handle.read(1)
            except PermissionError as exc:
                if self._live_foreign_owner():
                    raise LeaseHeldError(self._held_message()) from exc
                raise
            if not present:
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
                    self._pid_alive(pid, previous.get("process_start"))
                if self._pid_alive(pid, previous.get("process_start")) and not same_process_recovery:
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

    @classmethod
    def held_here(cls, vault: Vault) -> bool:
        """Whether a coordinator in this process holds this vault's lease."""
        canonical = str((vault.librarian / "runtime" / "vault.lock").resolve()).casefold()
        with cls._process_guard:
            return canonical in cls._process_paths

    @classmethod
    def held_elsewhere(cls, vault: Vault) -> bool:
        """Whether another live process holds this vault's lease, read from its
        diagnostic row (pinned to that process's identity, so a stale row or a
        recycled PID is not mistaken for a running Core).  It never touches
        the lock itself: probing it could make a starting Core fail to acquire."""
        try:
            data = json.loads((vault.librarian / "runtime" / "vault.lease.json")
                              .read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        pid = int(data.get("pid") or 0) if isinstance(data, dict) else 0
        if pid <= 0 or pid == os.getpid():
            return False
        return cls._pid_alive(pid, data.get("process_start"))

    @staticmethod
    def _pid_alive(pid: int, start: str | None = None) -> bool:
        # The shared platform-aware check: on Windows `os.kill(pid, 0)` reports
        # an exited process as alive while any handle to it is open.  An
        # inaccessible process still counts as alive, so takeover stays explicit.
        return process_identity.is_alive(pid, start)

    def _held_message(self) -> str:
        current = self.status()
        if current:
            return ("another Librarian Core owns this vault "
                    f"(pid {current.get('pid', '?')}, started {current.get('started_at', '?')})")
        return "another Librarian Core owns this vault"

    def _live_foreign_owner(self) -> bool:
        """Whether the diagnostic sidecar names one exact live other process.

        This is deliberately only supporting evidence for a Windows
        ``PermissionError`` while probing the authoritative OS lock. A stale,
        absent or unreadable sidecar must not turn an ordinary filesystem
        fault into a misleading ownership refusal.
        """
        if msvcrt is None:
            return False
        current = self.status()
        try:
            pid = int(current.get("pid") or 0)
        except (AttributeError, TypeError, ValueError):
            return False
        process_start = current.get("process_start")
        return pid > 0 and pid != os.getpid() and bool(process_start) and \
            self._pid_alive(pid, process_start)

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
        with file_access(path):
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
        with file_access(path):
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
        self._unreadable: set[str] = set()
        self._lock = threading.RLock()

    def heartbeat(self, path: str, *, editor: str = "Obsidian", dirty: bool = True,
                  baseline: str = "") -> dict[str, Any]:
        target = self.vault.safe_relative(path)
        rel = target.relative_to(self.vault.root).as_posix()
        now = time.monotonic()
        with self._lock:
            self._expire(now)
            try:
                observed = baseline or fingerprint(target)
            except OSError:
                observed = "unreadable"
                self._unreadable.add(rel)
            self._leases[rel] = DocumentLease(rel, editor[:80] or "Obsidian",
                                               observed, bool(dirty), now)
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
            recovering = rel in self._unreadable
            if recovering:
                try:
                    target.stat()
                except FileNotFoundError:
                    pass  # A confirmed deletion can resolve a pending read.
            observed = fingerprint(target) if known is not None or recovering else None
            self._unreadable.discard(rel)  # Only after a required read succeeds.
            if known is not None and known[0] == observed:
                self._core_fingerprints.pop(rel, None)
                self._suppress_until.pop(rel, None)
                self._changed.pop(rel, None)
                return
            if known is None and not recovering and now < self._suppress_until.get(rel, 0.0):
                return
            self._changed[rel] = now

    def unreadable(self, path: str) -> None:
        """Pause only this document until the watcher can confirm a read."""
        target = self.vault.safe_relative(path)
        with self._lock:
            self._unreadable.add(target.relative_to(self.vault.root).as_posix())

    def pending_reads(self) -> list[str]:
        with self._lock:
            return sorted(self._unreadable)

    def note_core_write(self, paths: list[str] | tuple[str, ...], *,
                        fingerprints: dict[str, str] | None = None) -> None:
        """Avoid treating the Core's own atomic replacement as a human edit.

        A caller that computed the exact fingerprint over the bytes it
        atomically published may supply it. This keeps the watcher proof while
        avoiding an immediate second read of a large streamed attachment.
        """
        supplied = fingerprints or {}
        with self._lock:
            until = time.monotonic() + DEBOUNCE_SECONDS * 2
            for path in paths:
                try:
                    target = self.vault.safe_relative(path)
                    rel = target.relative_to(self.vault.root).as_posix()
                except (OSError, ValueError, Refusal):
                    continue
                self._suppress_until[rel] = until
                observed = supplied.get(rel)
                if observed is None:
                    try:
                        observed = fingerprint(target)
                    except OSError:
                        self._unreadable.add(rel)
                        self._core_fingerprints.pop(rel, None)
                        continue
                self._core_fingerprints[rel] = (observed, time.monotonic() + 60.0)
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
                if rel in self._unreadable:
                    raise DocumentBusyError(rel, "an unreadable note awaiting a filesystem rescan")
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
        self._errors: dict[str, str] = {}
        self._error_lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"librarian-watch-{vault.root.name}")

    def start(self) -> None:
        self._known = self._snapshot()
        self._thread.start()

    def close(self, timeout: float = 2.0) -> None:
        self._closed.set()
        if self._thread.ident is not None:
            self._thread.join(timeout)

    def _error(self, rel: str, exc: Exception) -> None:
        with self._error_lock:
            self._errors[rel] = type(exc).__name__
            while len(self._errors) > 50:
                self._errors.pop(next(iter(self._errors)))

    def health(self) -> dict[str, Any]:
        with self._error_lock:
            errors = [{"path": path, "error": error} for path, error in sorted(self._errors.items())][:20]
        pending = self.leases.pending_reads()
        status = ("stopped" if self._closed.is_set() else "not_started" if self._thread.ident is None
                  else "failed" if not self._thread.is_alive() else "degraded" if errors or pending else "ready")
        return {"status": status, "pending_reads": pending[:20], "pending_count": len(pending), "errors": errors}

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
                except FileNotFoundError:
                    continue
                except OSError as exc:
                    name = rel.as_posix()
                    self._error(name, exc)
                    try:
                        self.leases.unreadable(name)
                    except (OSError, Refusal):
                        pass
                    if name in self._known:
                        rows[name] = self._known[name]
        except OSError as exc:
            self._error("<snapshot>", exc)
            # A partial directory walk is not evidence that missing entries
            # were deleted. Keep them until a subsequent successful scan.
            for rel, stamp in self._known.items():
                rows.setdefault(rel, stamp)
        else:
            with self._error_lock:
                self._errors.pop("<snapshot>", None)
        return rows

    def _run(self) -> None:
        while not self._closed.wait(self.interval):
            try:
                self.scan_once()
            except OSError as exc:
                self._error("<scan>", exc)  # Filesystem failure, not a swallowed programming error.

    def scan_once(self) -> None:
        """Observe one coalesced Markdown snapshot.

        A deletion is an edit too.  Without the second loop a Core write
        could silently recreate a note a person had just removed in Obsidian.
        Keeping this method small and public-ish also makes the deletion race
        deterministic to exercise without a timing-sensitive watcher test.
        """
        latest = self._snapshot()
        changed = {rel for rel, stamp in latest.items() if self._known.get(rel) != stamp}
        changed.update(set(self._known) - set(latest))
        changed.update(self.leases.pending_reads())
        with self._error_lock:
            self._errors.pop("<scan>", None)
        for rel in sorted(changed):
            try:
                self.leases.observe_change(rel)
                with self._error_lock:
                    self._errors.pop(rel, None)
            except OSError as exc:
                self._error(rel, exc)
                try:
                    self.leases.unreadable(rel)
                except (OSError, Refusal):
                    pass
                # Do not consume the failed event. Retry even when the next
                # snapshot is identical or the path remains absent.
                if rel in self._known:
                    latest[rel] = self._known[rel]
                else:
                    latest.pop(rel, None)
            except Refusal as exc:
                self._error(rel, exc)
                latest.pop(rel, None)  # Invalid/out-of-vault aliases are never followed.
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


# Writer threads, so code that must never block one (a wait for a person) can
# tell it is running on one.
_WRITER_THREADS: dict[threading.Thread, "VaultWriter"] = {}
_WRITER_THREADS_GUARD = threading.Lock()


def on_writer_thread() -> bool:
    """True inside a vault-writer operation.

    An operation is linear: its revision checks, its mutation and its audit
    record happen with nothing else in between.  Waiting for a person there
    would either hold every other write for as long as they take or, if the
    queue were served meanwhile, let unrelated writes land inside an
    operation that had already checked its revisions.  So a question is
    recorded inside the operation and waited on after it (registry).
    """
    with _WRITER_THREADS_GUARD:
        return threading.current_thread() in _WRITER_THREADS


class VaultWriter:
    """One serial worker for Librarian-originated mutations in a vault."""

    def __init__(self, vault: Vault, leases: DocumentLeases | None = None) -> None:
        self.vault = vault
        self.leases = leases or DocumentLeases(vault)
        self._queue: queue.Queue[tuple[Operation, Callable[[], Any], threading.Event, list[Any]]] = queue.Queue()
        self._closed = threading.Event()
        # ``submit`` and ``close`` share this boundary.  A shutdown must not
        # observe an empty queue, then let a concurrent caller enqueue one
        # more operation before it closes admission to the actor.
        self._admission = threading.Lock()
        # The App keeps its coordinator alive through the writer's lifetime.
        # This matters when a timed shutdown returns while the daemon worker
        # is still inside a mutation: dropping the App object must not let a
        # file-handle finalizer release the vault lease underneath that worker.
        self._lifecycle_owner: Any | None = None
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"librarian-writer-{vault.root.name}")
        self._thread.start()
        with _WRITER_THREADS_GUARD:
            _WRITER_THREADS[self._thread] = self

    @property
    def log_path(self) -> Path:
        return self.vault.librarian / "runtime" / "operations.jsonl"

    @property
    def alive(self) -> bool:
        """Whether the serial worker can still execute a vault operation."""
        return self._thread.is_alive()

    @property
    def accepting(self) -> bool:
        """Whether a new external operation can enter the writer."""
        return not self._closed.is_set()

    def retain_lifecycle_owner(self, owner: Any) -> None:
        """Keep a lease owner alive until this writer has stopped.

        The owner is deliberately opaque: ``VaultWriter`` stays usable in
        offline tests, while the coordinated App supplies its
        :class:`VaultCoordinator`.  The App explicitly releases the lease and
        then drops this reference after a confirmed drain.
        """
        self._lifecycle_owner = owner

    def release_lifecycle_owner(self) -> None:
        """Drop the retention established by :meth:`retain_lifecycle_owner`."""
        self._lifecycle_owner = None

    def interrupted_operations(self) -> list[dict[str, Any]]:
        """Return safe diagnostics for operations without a durable outcome.

        The writer records ``running`` before a mutation and a second, terminal
        record after it.  A process crash or final-audit failure can leave only
        the former.  Startup recovery must surface that ambiguity without
        replaying, repairing, or exposing an operation's result/detail (either
        can contain document text).  The caller turns these rows into durable
        human checkpoints.

        A truncated final JSONL record is the normal crash artefact and is
        ignored.  A malformed complete record is instead returned as a
        minimal integrity diagnostic, so corruption cannot disappear silently.
        """
        try:
            raw = self.log_path.read_bytes()
        except FileNotFoundError:
            return []
        except OSError as exc:
            # Treating an unreadable operation log as an empty one would let
            # the Core overwrite state without first surfacing a possibly
            # interrupted mutation. The caller releases its lease and refuses
            # startup rather than admitting writes on unknown evidence.
            raise OperationLogUnreadableError(
                "the vault operation log cannot be read; mutation admission is refused") from exc
        lines = raw.splitlines(keepends=True)
        latest: dict[str, dict[str, Any]] = {}
        diagnostics: list[dict[str, Any]] = []
        for index, raw_line in enumerate(lines):
            terminated = raw_line.endswith((b"\n", b"\r"))
            line = raw_line.rstrip(b"\r\n")
            if not line.strip():
                continue
            try:
                decoded = line.decode("utf-8")
                row = json.loads(decoded)
            except (UnicodeDecodeError, json.JSONDecodeError):
                if index == len(lines) - 1 and not terminated:
                    # The final append may have been cut off between write and
                    # flush.  The preceding durable record still tells us the
                    # real state, if any.
                    continue
                diagnostics.append(_operation_integrity_diagnostic(
                    index + 1, line, "invalid UTF-8 or JSON record"))
                continue
            record, error = _operation_recovery_record(row)
            if error:
                diagnostics.append(_operation_integrity_diagnostic(index + 1, line, error))
                continue
            assert record is not None  # narrows for type checkers and readers
            latest[record["operation_id"]] = record

        interrupted = [record for record in latest.values()
                       if record["caller"] != "operation-recovery"
                       and record["status"] in {"queued", "running"}
                       and not record["finished_at"]]
        return sorted([*diagnostics, *interrupted],
                      key=lambda record: (str(record.get("started_at") or ""),
                                          str(record.get("operation_id") or "")))

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
        op = Operation(secrets.token_hex(8), caller[:80], list(targets), now_iso(),
                       precondition_fingerprints=dict(preconditions or {}))
        done, box = threading.Event(), []
        # Admission and shutdown are one atomic decision.  In particular, do
        # not let ``close`` return from a successful drain while a submitter
        # which checked ``_closed`` just before it enqueues is still racing.
        with self._admission:
            if self._closed.is_set():
                raise RuntimeError("vault writer is closed")
            self._queue.put((op, fn, done, box))
        if not done.wait(timeout):
            raise TimeoutError(f"vault operation {op.id} did not finish")
        kind, value = box[0]
        if kind == "error":
            raise value
        return value

    def _run(self) -> None:
        try:
            while not self._closed.is_set() or not self._queue.empty():
                try:
                    item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                self._serve(item)
        finally:
            # Do not claim this is a writer thread after it has stopped.  A
            # timed close used to remove this entry *while it was still
            # running*, which also hid a useful lifecycle fact from callers.
            with _WRITER_THREADS_GUARD:
                _WRITER_THREADS.pop(self._thread, None)

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

    def _invoke(self, op: Operation, fn: Callable[[], T]) -> T:
        """Run one serialized mutation with revision and audit protection."""
        op.status = "running"
        # Core operations also name their owned state files (staging, runs,
        # derived records). Validate those through the internal resolver but
        # never offer them as editable Obsidian documents. Public path APIs
        # and heartbeat validation still reject hidden files.
        document_targets = []
        for path in op.targets:
            target = operation_path(self.vault, path)
            rel = target.relative_to(self.vault.root).as_posix()
            if rel.split("/", 1)[0] not in {".librarian", ".evidence"}:
                document_targets.append(rel)
        # Do this inside the actor after all preceding operations have
        # committed, then enforce document leases before the write.  A
        # supplied fingerprint is an actual compare-and-swap precondition;
        # actor-generated values document the revision seen for operations
        # that did not originate from a read-modify-write workflow.
        for path in dict.fromkeys([*op.targets, *op.precondition_fingerprints]):
            try:
                observed = fingerprint(operation_path(self.vault, path))
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
        self.leases.assert_writable(document_targets)
        value = fn()
        self.leases.note_core_write(document_targets)
        op.status = "done"
        op.result = _operation_result(value)
        return value

    def _record(self, op: Operation) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(asdict(op), ensure_ascii=False) + "\n").encode("utf-8")
        # The writer is the only local producer, so append is serial and no
        # separate file lock is needed inside this process.
        with self.log_path.open("a+b") as handle:
            # A previous process can die during its final JSONL append.  Do
            # not glue this new record to that partial tail: a later startup
            # would mistake the concatenation for a complete corrupt row.  A
            # complete no-newline JSON object is preserved; an incomplete one
            # was never a durable operation record and is safely discarded.
            handle.seek(0, os.SEEK_END)
            length = handle.tell()
            if length:
                handle.seek(0)
                previous = handle.read()
                if not previous.endswith((b"\n", b"\r")):
                    boundary = max(previous.rfind(b"\n"), previous.rfind(b"\r")) + 1
                    tail = previous[boundary:]
                    try:
                        parsed_tail = json.loads(tail.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        handle.seek(boundary)
                        handle.truncate()
                    else:
                        # JSONL requires a delimiter even if a prior producer
                        # crashed between its complete object and newline.
                        if isinstance(parsed_tail, dict):
                            handle.seek(0, os.SEEK_END)
                            handle.write(b"\n")
                        else:
                            handle.seek(boundary)
                            handle.truncate()
            handle.seek(0, os.SEEK_END)
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

    def close(self, timeout: float = 5.0) -> bool:
        """Close admission and wait for every accepted operation to stop.

        ``False`` means an operation is still executing after ``timeout``.
        It is intentionally not treated as a successful close: callers that
        own a vault lease must retain it (and any dependent resources) until
        a later retry confirms that this worker is no longer alive.
        """
        with self._admission:
            self._closed.set()
        if threading.current_thread() is self._thread:
            return False
        self._thread.join(timeout)
        stopped = not self._thread.is_alive()
        if stopped:
            with _WRITER_THREADS_GUARD:
                _WRITER_THREADS.pop(self._thread, None)
        return stopped


def _operation_recovery_record(row: Any) -> tuple[dict[str, Any] | None, str]:
    """Reduce one audit-log row to the non-secret state recovery may show."""
    if not isinstance(row, dict):
        return None, "record is not an object"
    operation_id = _operation_text(row.get("id"), 160)
    if not operation_id:
        return None, "record has no operation id"
    status = _operation_text(row.get("status"), 40)
    if status not in {"queued", "running", "done", "failed"}:
        return None, "record has an invalid status"
    raw_targets = row.get("targets", [])
    if not isinstance(raw_targets, list) or not all(isinstance(path, str) for path in raw_targets):
        return None, "record has invalid targets"
    preconditions = _operation_fingerprints(row.get("precondition_fingerprints", {}))
    observed = _operation_fingerprints(row.get("observed_fingerprints", {}))
    if preconditions is None or observed is None:
        return None, "record has invalid fingerprints"
    return {
        "operation_id": operation_id,
        "caller": _operation_text(row.get("caller"), 80) or "unknown",
        "started_at": _operation_text(row.get("started_at"), 80),
        "targets": [_operation_text(path, 400) for path in raw_targets[:200]],
        "precondition_fingerprints": preconditions,
        "observed_fingerprints": observed,
        "finished_at": _operation_text(row.get("finished_at"), 80),
        "status": status,
    }, ""


def _operation_text(value: Any, limit: int) -> str:
    """Bound an audit identifier without carrying arbitrary nested payloads."""
    return str(value or "").replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()[:limit]


def _operation_fingerprints(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    if len(value) > 200:
        return None
    out: dict[str, str] = {}
    for path, digest in value.items():
        if not isinstance(path, str) or not isinstance(digest, str):
            return None
        out[_operation_text(path, 400)] = _operation_text(digest, 160)
    return out


def _operation_integrity_diagnostic(line_number: int, raw: str | bytes, reason: str) -> dict[str, Any]:
    """Make a stable, safe recovery item for a malformed complete log row."""
    payload = raw if isinstance(raw, bytes) else raw.encode("utf-8", "replace")
    marker = hashlib.sha256(f"{line_number}:".encode("utf-8") + payload).hexdigest()[:16]
    return {
        "operation_id": f"operation-log-integrity-{marker}",
        "caller": "operation-log",
        "started_at": "",
        "targets": [],
        "precondition_fingerprints": {},
        "observed_fingerprints": {},
        "finished_at": "",
        "status": "running",
        "integrity_error": f"operation log integrity issue at record {line_number}: {reason}",
    }


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
