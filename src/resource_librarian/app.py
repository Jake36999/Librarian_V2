"""The core's local API: what the interface talks to, in the website and in the
Obsidian view alike.

`resource-librarian app` serves the interface and a JSON API on loopback. One
process holds everything the interface must not: the keys, the permission
broker, the agent loop and the vault. The interface holds none of it and asks.

**The boundary.** V1's chat found that the `Host` check stops DNS rebinding
but not a page on another site posting to `127.0.0.1` from the person's own
browser. So every `/api/` request needs:
- a loopback `Host`;
- the per-process page token (header `X-Librarian-Token`, or `?token=` for the
  event stream, which a browser cannot give headers), which only a same-origin
  page (it is in the served page) or the host that started the core (it
  passed it in) can know;
- for a write, an `Origin`, when the browser sends one, that is this server
  or an allowed host (`app://obsidian.md`).

**Who is calling.** The interface's own buttons are the person: they call
tools at `curate` through the registry (`/api/tool/<name>`), since a click is
the person's decision. The chat's model runs at `contribute` through the loop,
and every action it takes is decided by the broker in the current mode. Queued
actions are pipelines the person starts; their steps go through the broker too.

**Events.** One stream (`/api/events`, server-sent events): the loop's steps,
permission requests and decisions, mode changes, action progress. Each has a
sequence number, so a page that reconnects misses nothing recent.
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import re
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any, Callable, Iterator
from urllib.parse import parse_qs, urlparse

from . import ADAPTER_PROTOCOL_RANGE, PROTOCOL_VERSION, __version__, batch, doctor, notes, workflows
from . import tools  # noqa: F401  (registers the tools)
from .agent_runtime import (ProfileCapacityError, ProfileRunGate, ProfiledEndpoint,
                            route_permitted)
from .broker import ANSWERS, MODES, Broker
from .checkpoints import CheckpointStore
from . import connection
from .coordination import (DocumentLeases, LeaseHeldError, StaleLeaseError,
                           VaultCoordinator, VaultWatcher, VaultWriter, atomic_write_bytes, atomic_write_text,
                           fingerprint)
from .hosts import (EVALUATION_LEVELS, RELEASE_PROMPT_CONTRACT_VERSION,
                    RELEASE_TOOL_CONTRACT_VERSION, L1_PROBE_CONTRACT_VERSION,
                    EvaluationJobStore, Host, HostFullRecordError, HostLimiter, HostRegistry,
                    LimitedProvider, QualificationStore, endpoint_fingerprint, fingerprints,
                    release_lead_for_route, release_leads, validate_l1_probe,
                    validate_l1_continuation, continuation_messages)
from .index import IndexService
from .file_access import read_text
from .keys import KeyStore, config_dir
from .loop import LENGTHS, STANCES, Loop, ProviderEndpoint
from .model_invocation import (InvocationPayload, InvocationRuntime,
                               InvocationScope, ModelIdentityMismatchError,
                               TaskContract)
from .providers import DASHBOARDS, PRESETS, Provider, ProviderError, ToolDef, from_settings
from .registry import REGISTRY, TIERS, Context
from .role_routes import CHAT_ROLES, RoleRouteBinding, RoleRouteStore
from .rules import Refusal
from .staging import StagingStore
from .session import SessionStore, attach_core_writer, detach_core_writer
from .tools.sessions import Waiters
from .vault import DEFAULT_CONFIG, Vault, now_iso

LOOPBACK = {"127.0.0.1", "localhost", "::1", "[::1]"}
HOST_ORIGINS = {"app://obsidian.md"}
MAX_BODY = 1_000_000
MAX_UPLOAD = 40_000_000
QUEUED = ("clear-enrichment-backlog", "deep-read-staged", "review-conversation", "review-due",
          "weekly-review")
PROVIDER_LABELS = {"deepinfra": "DeepInfra", "openai": "OpenAI", "anthropic": "Anthropic",
                   "local": "Local server"}
SCRIPT_SUFFIXES = {".py": "python", ".sh": "shell"}      # what the pane may run (sandbox.py)
DEFAULTS = {"working_context": "", "reply_length": "long", "stance": "answer", "tiers": [],
            "mode": "ask", "base_urls": {}, "effort": 4, "agent_profile": "lead"}


class ApiError(Exception):
    def __init__(self, status: int, message: str, **extra: Any):
        super().__init__(message)
        self.status = status
        self.body = {"error": message, **extra}


def mutation_entry(what: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Guard a direct, mutating App entry point for the Core lifetime.

    HTTP writes have a single outer guard, but adapters and tests may invoke
    App methods directly.  Keeping this small decorator at those alternate
    entry points prevents a shutdown race from becoming an API-shape
    distinction.
    """
    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def guarded(self: "App", *args: Any, **kwargs: Any) -> Any:
            with self._counted_mutation(what):
                return fn(self, *args, **kwargs)
        return guarded
    return decorate


# ------------------------------------------------------------------- events

class Hub:
    """Fan-out of epoch-bound events to every open stream, with short memory.

    Sequence numbers are process-local. A fresh Core can begin again at one,
    so an event-stream cursor is meaningful only with this Hub's random epoch.
    Session logs remain the durable source for session state; this class never
    attempts to reconstruct actions from its bounded in-memory event list.
    """

    def __init__(self, keep: int = 500):
        self._lock = threading.Lock()
        self._epoch = secrets.token_urlsafe(12)
        self._seq = 0
        self._recent: deque[dict[str, Any]] = deque(maxlen=keep)
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._seq += 1
            # The Core owns stream identity. A tool/event producer cannot
            # forge a sequence, timestamp, or epoch through its payload.
            stamped = {**event, "seq": self._seq, "at": round(time.time(), 3),
                       "epoch": self._epoch}
            self._recent.append(stamped)
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(stamped)
            except Exception:                               # noqa: BLE001
                pass
        return stamped

    def last(self) -> int:
        with self._lock:
            return self._seq

    def cursor(self) -> dict[str, Any]:
        """The only cursor a client may use to reconnect to this Core."""
        with self._lock:
            return {"epoch": self._epoch, "last_seq": self._seq}

    def since(self, seq: int) -> list[dict[str, Any]]:
        with self._lock:
            return [e for e in self._recent if e["seq"] > seq]

    def resume(self, since: int, epoch: str = "") -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        """Return replayable events or one synthetic instruction to refresh.

        The instruction is deliberately not published: it must not advance the
        shared sequence or look like a durable action. The browser fetches
        ``/api/state`` after it, preserving the distinction between Hub events
        and canonical Core/session state.
        """
        with self._lock:
            current = {"epoch": self._epoch, "last_seq": self._seq}
            reason = ""
            if epoch and epoch != self._epoch:
                reason = "epoch_changed"
            elif since > 0 and not epoch:
                reason = "epoch_required"
            elif since > self._seq:
                reason = "cursor_ahead"
            # A zero-sized retention window is useful in constrained hosts;
            # it must also report a gap rather than silently pretending that
            # an event it discarded never happened.
            elif since < self._seq and (not self._recent or since < self._recent[0]["seq"] - 1):
                reason = "history_expired"
            if reason:
                return [], {
                    "type": "resync_required", "seq": current["last_seq"],
                    "epoch": current["epoch"], "reason": reason,
                    "state_url": "/api/state", "instruction": "refresh_state",
                }
            return [dict(event) for event in self._recent if event["seq"] > since], None

    def subscribe(self, listener: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(listener)

        def stop() -> None:
            with self._lock:
                if listener in self._listeners:
                    self._listeners.remove(listener)
        return stop


# ---------------------------------------------------------------- settings

class Settings:
    """The interface's own settings, in `.librarian/app.json`: the working
    context, reply length, model tiers and mode. Never a key.

    The model choices (`SHARED`) are the person's, not one library's (owner, 2026-10-03:
    a new library had no models, so its ingest queued everything for a clerk that was
    never chosen). Each change is also kept in the user's config directory, and a library
    that has not chosen its own starts from them."""

    SHARED = ("tiers", "lead_overrides", "effort")

    def __init__(self, vault: Vault, writer: VaultWriter | None = None):
        self.path = vault.librarian / "app.json"
        self.writer = writer
        self.serialize: Callable[[str, Callable[[], Any]], Any] | None = None
        self.data = dict(DEFAULTS)
        own: dict[str, Any] = {}
        if self.path.is_file():
            try:
                own = json.loads(self.path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                own = {}
        shared = self._shared()
        self.data.update({k: v for k, v in shared.items() if k in self.SHARED and k not in own})
        self.data.update(own)
        self.inherited = sorted(k for k in shared if k in self.SHARED and k not in own)

    @staticmethod
    def _shared_path() -> Path:
        from .keys import config_dir
        return config_dir() / "app-defaults.json"

    def _shared(self) -> dict[str, Any]:
        try:
            data = json.loads(self._shared_path().read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def update_in_operation(self, **changes: Any) -> None:
        """Persist inside an already serialized App operation."""
        updated = {**self.data, **changes}
        atomic_write_text(self.path, json.dumps(updated, indent=1, ensure_ascii=False) + "\n")
        self.data.update(changes)
        mine = {k: v for k, v in changes.items() if k in self.SHARED}
        if mine:
            try:
                path = self._shared_path()
                atomic_write_text(path, json.dumps({**self._shared(), **mine}, indent=1,
                                                   ensure_ascii=False) + "\n")
            except OSError:
                pass                # a read-only config dir never stops a choice

    def update(self, **changes: Any) -> None:
        def persist() -> None:
            self.update_in_operation(**changes)
        if self.serialize is not None:
            self.serialize("settings", persist)
        elif self.writer is not None:
            # Document leases protect human-editable Markdown only.  Internal
            # state is still serialised by the writer but has no Obsidian path.
            self.writer.submit(persist, caller="settings")
        else:
            persist()


@dataclass
class Action:
    id: str
    name: str
    status: str = "running"
    steps: int = 0
    run: str = ""
    result: dict[str, Any] = field(default_factory=dict)
    cancel: threading.Event = field(default_factory=threading.Event)

    def public(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "status": self.status,
                "steps": self.steps, "run": self.run,
                **({"at": self.result.get("at"), "reason": self.result.get("reason")}
                   if self.status == "paused" else {})}


PROFILE_FIELDS = ("modality", "best_for", "license_class", "suggested_tier", "context_length",
                  "price_input_per_1m", "price_output_per_1m", "tool_calling", "reasoning")


def _tri_state(value: Any) -> bool | None:
    """True, False, or None for "not yet assessed" - never a guessed False."""
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold() if value is not None else ""
    return True if text == "true" else False if text == "false" else None


def _shipped_profiles() -> dict[tuple[str, str], dict[str, Any]]:
    """The model catalogues shipped with the package (standard/model_catalog/*.json)."""
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for path in sorted((Path(__file__).parent / "standard" / "model_catalog").glob("*.json")):
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in rows if isinstance(rows, list) else []:
            fields = (row or {}).get("fields") or {}
            key = (str(fields.get("provider") or "").lower(), str(fields.get("model_id") or "").lower())
            if key[1]:
                out[key] = {k: fields.get(k) for k in PROFILE_FIELDS}
    return out


def _profiles_path() -> Path:
    from .keys import config_dir
    return config_dir() / "model-profiles.json"


def _remembered_profiles() -> dict[tuple[str, str], dict[str, Any]]:
    try:
        data = json.loads(_profiles_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {tuple(k.split("|", 1)): v for k, v in data.items()
            if isinstance(v, dict) and "|" in k}


def _remember_profiles(own: dict[tuple[str, str], dict[str, Any]]) -> None:
    """Keep this library's model profiles where every library can see them."""
    if not own:
        return
    known = {f"{p}|{m}": v for (p, m), v in _remembered_profiles().items()}
    fresh = {f"{p}|{m}": {k: v.get(k) for k in PROFILE_FIELDS} for (p, m), v in own.items()}
    if all(known.get(k) == v for k, v in fresh.items()):
        return
    try:
        path = _profiles_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps({**known, **fresh}, indent=0, default=str))
    except OSError:
        pass


def ELIGIBLE_LEADS() -> list[dict[str, Any]]:            # noqa: N802 - a read-only table
    """The leads M0 found to complete research tasks (standard/eligible_leads.json)."""
    path = Path(__file__).parent / "standard" / "eligible_leads.json"
    try:
        return list(json.loads(path.read_text(encoding="utf-8")).get("eligible") or [])
    except (OSError, json.JSONDecodeError):
        return []


# --------------------------------------------------------------------- app

class App:
    def __init__(self, vault: Vault, token: str = "", keys: KeyStore | None = None,
                 provider_for: Callable[[dict[str, Any]], Provider | None] | None = None,
                 allowed_origins: set[str] | None = None, broker_timeout: float = 600.0,
                 mcp: Any = None, *, coordinate: bool = False, takeover: bool = False,
                 secret_source: str = "desktop", host_managed: bool = False):
        self.vault = vault
        self.broker_timeout = broker_timeout
        self.token = token or secrets.token_urlsafe(24)
        self.coordinated = bool(coordinate)
        self.secret_source = secret_source if secret_source in ("desktop", "obsidian") else "desktop"
        # Only a trusted local lifecycle owner (the per-user Host or an
        # adapter-owned Core performing an explicit SecretStorage rotation)
        # asks a Core to stop over loopback.  A regular browser cannot
        # accidentally acquire a lifecycle control surface merely by knowing
        # the page token.
        self.host_managed = bool(host_managed)
        self.coordinator: VaultCoordinator | None = None
        self.document_leases = DocumentLeases(vault)
        self.watcher: VaultWatcher | None = None
        self.writer: VaultWriter | None = None
        # This lock is created before migrations: settings migrations use the
        # same serialization boundary as ordinary App mutations.
        self._lock = threading.RLock()
        self._shutdown_lock = threading.Lock()
        self._closed = False
        self._shutdown_started = False
        self._shutdown_pending: dict[str, Any] = {}
        # Shutdown is observable (CORE-02A): new work is refused once it
        # begins, and each phase is recorded for the Host and the tray.
        self._admitting = True
        self.shutdown_phases: list[dict[str, Any]] = []
        # Synchronous calls running here - a person's own and an MCP client's
        # (CORE-04A) - so a stop waits for them rather than closing under them.
        self._calls = {"person": 0, "mcp": 0}
        # Direct app/HTTP mutations which are neither chat turns nor registry
        # calls.  Admission and this count are changed under ``_lock`` so a
        # stop either refuses a new mutation or waits for its writer work.
        self._mutations = 0
        self._offline_lock = threading.RLock()
        self._offline_lease: VaultCoordinator | None = None
        if not coordinate and (VaultCoordinator.held_here(vault) or VaultCoordinator.held_elsewhere(vault)):
            raise ApiError(409, "CORE_REQUIRED: a Core already owns this library; connect through its API")
        if coordinate:
            self.coordinator = VaultCoordinator(vault, protocol_version=PROTOCOL_VERSION)
            self.coordinator.acquire(takeover=takeover)
            self.writer = VaultWriter(vault, self.document_leases)
            self.writer.retain_lifecycle_owner(self.coordinator)
            # Session events from any module go through this writer (CORE-03).
            attach_core_writer(vault, self.writer)
        # Recovery must precede *any* App-owned write (including settings
        # migration): otherwise a truncated final JSONL line could be joined
        # to that first append and turn a recoverable crash tail into a new
        # corrupt record.  Checkpoints and Hub need no settings/broker state.
        self.checkpoints = CheckpointStore(vault)
        self.hub = Hub()
        try:
            self.operation_recoveries = self._reconcile_interrupted_operations()
        except Exception:
            # A failed startup must not strand the process-local session sink
            # or vault lease. In particular, an unreadable operation log is a
            # fail-closed condition rather than permission to mutate blindly.
            if self.writer is not None:
                detach_core_writer(vault, self.writer)
                if self.writer.close() and self.coordinator is not None:
                    self.coordinator.release()
                    self.writer.release_lifecycle_owner()
                    self.coordinator = None
            raise
        self.keys = keys or KeyStore(obsidian_managed=self.secret_source == "obsidian")
        self.settings = Settings(vault, self.writer)
        self.settings.serialize = self._serialized
        self.index_service = IndexService(vault)
        self.hosts = HostRegistry()
        self.host_limiter = HostLimiter()
        for row in self.hosts.all():
            # Public rows deliberately omit auth_ref; seed and custom entries
            # are registered below through their private record only.
            try:
                auth_ref = self.hosts.get(str(row["id"])).auth_ref
                if auth_ref:
                    self.keys.register_ref(auth_ref)
            except (KeyError, AttributeError):
                continue
        self.role_routes = RoleRouteStore(vault)
        try:
            self._migrate_legacy_host_routes()
            self._migrate_legacy_role_routes()
            self._migrate_service_routes()
        except Exception:
            self.index_service.close()
            if self.writer is not None:
                detach_core_writer(vault, self.writer)
                if self.writer.close() and self.coordinator is not None:
                    self.coordinator.release()
                    self.writer.release_lifecycle_owner()
                    self.coordinator = None
            raise
        self.qualifications = QualificationStore()
        self.evaluation_jobs = EvaluationJobStore()
        from .agent_runtime import ProfileStore
        self.profiles = ProfileStore(vault)
        self.profile_gate = ProfileRunGate()
        # A start-only writer record means a prior process may have mutated
        # some, all, or none of its targets.  It has already been surfaced
        # before App-owned writes and before the watcher begins; recovery
        # never replays or repairs it.
        if self.writer is not None:
            self.watcher = VaultWatcher(vault, self.document_leases)
            self.watcher.start()
        # Redacted invocation diagnostics live only in process memory for the
        # first adapter slice.  Do not turn model prompts or responses into a
        # new vault artefact merely by adding a protocol translation seam.
        self.invocation_runtime = InvocationRuntime()
        self.broker = Broker(mode=self.settings.data.get("mode", "ask"),
                             timeout=broker_timeout)
        self.broker.subscribe(self.hub.publish)
        self.waiters = Waiters(timeout=broker_timeout)
        self.waiters.subscribe(self.hub.publish)
        self.allowed_origins = set(HOST_ORIGINS | (allowed_origins or set()))
        self._provider_for = provider_for or self._configured_provider
        self.busy = False
        self._turn_cancel: threading.Event | None = None
        self.loop: Loop | None = None
        self._tts_plans: dict[str, tuple[str, list[str]]] = {}   # slot 5's readings
        self.actions: dict[str, Action] = {}
        from .service_routes import ServiceRuntime
        self.service_runtime = ServiceRuntime(vault, self.hosts, self.host_limiter)
        self.service_runtime.attach()
        if mcp is not None:
            # Switching library: outside servers are configured per person, not
            # per library (mcp.json), and their tools are registered once,
            # globally - so the running manager carries over, and only the new
            # library's own broker is seeded with their default (Ask).
            self.mcp = mcp
            mcp.owner = self                       # the retiring library no longer stops it
            mcp.attach_broker(self.broker)
            mcp.use_library(vault.librarian)       # this library's own choices
            threading.Thread(target=mcp.sync, daemon=True, name="mcp-sync").start()
            return
        try:
            from .mcp_client import McpManager
        except ImportError:
            self.mcp = None                  # needs `pip install resource-librarian[mcp]`
        else:
            self.mcp = McpManager(config_dir(), broker=self.broker)
            self.mcp.owner = self
            self.mcp.use_library(vault.librarian)
            threading.Thread(target=self.mcp.sync, daemon=True, name="mcp-sync").start()

    # -- switching library ---------------------------------------------------
    def running(self) -> dict[str, Any]:
        """What would still be working here if this library were switched away
        from: a chat turn, workflows mid-run, questions waiting on a person."""
        actions = [a.public() for a in self.actions.values() if a.status == "running"]
        return {k: v for k, v in {"turn": self.busy, "actions": actions,
                                  "batch": batch.live(self.vault),
                                  "mcp_calls": self._calls["mcp"],
                                  "person_calls": self._calls["person"],
                                  "service_calls": self.service_runtime.active_calls,
                                  "waiting_on_person": len(self.broker.pending())}.items() if v}

    def retire(self, patience: float = 3600.0, poll: float = 2.0) -> None:
        """Close this library gracefully once it is no longer the open one: let
        a chat turn and running workflows finish (they write to this library's
        own sessions, which stay resumable), and let questions waiting on a
        person time out - an unanswered permission parks its session, since
        silence is never approval. Then drop the conversation. Outside servers
        are shared with the library that replaced this one, so they stay up."""
        deadline = time.monotonic() + patience
        while (self.busy or batch.live(self.vault) or any(a.status == "running" for a in self.actions.values())) \
                and time.monotonic() < deadline:
            time.sleep(poll)
        self.hub.publish({"type": "library_closed", "vault": self.vault.root.name})
        if self.loop is not None:
            self.loop.messages.clear()
            self.loop.ctx.session = None
        self.close_runtime()

    #: How long shutdown waits for a cancelled chat turn or action to stop.
    #: First-party provider transports abort their active socket (ADAPT-04B);
    #: legacy third-party providers retain their synchronous ABI, so this is
    #: still a fail-closed bound rather than a universal stop-latency promise.
    STOP_GRACE_SECONDS = 5.0
    #: A writer has already closed admission when this wait begins.  If an
    #: operation still has not returned at the deadline, the Core remains a
    #: retained, visibly pending owner rather than releasing the vault beneath
    #: that operation.
    WRITER_STOP_SECONDS = 10.0

    def _admit(self, what: str) -> None:
        if not self._admitting:
            raise ApiError(503, f"the Core is stopping; {what} was not started")

    @contextlib.contextmanager
    def _counted_call(self, kind: str, what: str) -> Iterator[None]:
        """Admit one synchronous call under the lock admission closes under,
        and count it until it returns: close_runtime either sees it and waits
        for it within its grace, or refuses it."""
        with self._lock:
            self._admit(what)
            self._calls[kind] += 1
        try:
            yield
        finally:
            with self._lock:
                self._calls[kind] -= 1

    def _begin_mutation(self, what: str) -> None:
        """Atomically admit one mutation and retain the Core until it ends.

        App-owned configuration/checkpoint writes are synchronous, but cannot
        simply check ``_admitting`` before submitting to the writer: shutdown
        could close in that gap.  The count is held until the operation (and
        therefore its writer work) returns, so a stop sees either a refusal or
        work it must drain before it can release the vault.

        Background work uses this paired with ``_end_mutation``: it must be
        counted before its thread is started, not when that thread eventually
        gets CPU time.  That makes the admission boundary apply equally to
        synchronous and asynchronous Core-owned writes.
        """
        with self._lock:
            self._admit(what)
            self._mutations += 1

    def _end_mutation(self) -> None:
        """Release one mutation slot acquired by ``_begin_mutation``."""
        with self._lock:
            self._mutations -= 1

    @contextlib.contextmanager
    def _counted_mutation(self, what: str) -> Iterator[None]:
        """Context-manager form of the Core mutation lifetime boundary."""
        self._begin_mutation(what)
        try:
            yield
        finally:
            self._end_mutation()

    def _shutdown_health(self) -> dict[str, Any]:
        """Non-secret lifecycle state for a Core that may be draining."""
        with self._lock:
            if self._closed:
                state = "closed"
            elif self._shutdown_started:
                state = "pending"
            else:
                state = "ready"
            pending = dict(self._shutdown_pending)
            mutations = self._mutations
        return {"state": state, "pending": pending, "active_mutations": mutations}

    def _persist_shutdown_phases(self) -> None:
        """Best-effort per-user telemetry for complete *or pending* stops.

        A Host-managed process exits after its one bounded shutdown attempt.
        If admitted work or the writer is still active, the vault lease and
        index correctly remain unreleased until process exit; retaining the
        truthful ``shutdown_pending`` phase lets the successor and tray
        distinguish that path from a clean drain without inventing later
        ``index_closed`` or ``lease_released`` phases.
        """
        if self.coordinator is None:
            return
        try:
            atomic_write_text(connection.shutdown_path(self.vault.root),
                              json.dumps({"phases": self.shutdown_phases}, indent=2) + "\n")
        except Exception:                                  # noqa: BLE001
            pass                         # diagnostics never block a stop

    def close_runtime(self) -> bool:
        """Flush mutable state and release this vault's process lease once.

        A tray/adapter calls this only for an explicit stop or after a switch
        has allowed work to finish.  It deliberately does not implement an
        idle timer or browser-client reference counting.  The phases are
        recorded in order (CORE-02A) in ``.librarian/runtime/shutdown.json``.

        ``False`` is a deliberately fail-closed result: admission is closed,
        but admitted work or the vault writer still exists, so the Core keeps
        its index and vault lease.  A later call retries the final drain.
        """
        with self._shutdown_lock:
            if self._closed:
                return True
            phases = self.shutdown_phases

            def phase(name: str, **detail: Any) -> None:
                phases.append({"phase": name, "at": now_iso(), **detail})

            first_stop = not self._shutdown_started
            if first_stop:
                self._shutdown_started = True
                # Admission closes under the same lock chat(), synchronous
                # calls, and direct mutations admit under.  A request is thus
                # either already counted below or refused before it submits.
                with self._lock:
                    self._admitting = False
                    turn = self._turn_cancel
                self.service_runtime.close()
                phase("admission_closed")
                if turn is not None:
                    turn.set()
                # A question or permission request waiting for a person would
                # otherwise hold a call (and sometimes the writer) until its
                # normal timeout.  These terminal closes make it return now.
                released = self.waiters.release_all() + self.broker.close("the Core is stopping")
            else:
                with self._lock:
                    turn = self._turn_cancel
                released = 0

            cancelled: dict[str, Action] = {}
            deadline = time.monotonic() + self.STOP_GRACE_SECONDS
            while True:
                # A person-started background batch outlives its HTTP request.
                # Include it in explicit-stop draining, including a reservation
                # made just before admission closed.
                batch.cancel(self.vault)
                # Re-scan each pass: an action registered just before admission
                # closed may only now be visible as running.
                for action in list(self.actions.values()):
                    if action.status == "running":
                        action.cancel.set()
                        cancelled[action.id] = action
                with self._lock:
                    calls = sum(self._calls.values()) + self.service_runtime.active_calls
                    mutations = self._mutations
                    busy = self.busy
                active_actions = any(action.status == "running" for action in cancelled.values())
                if not (busy or calls or mutations or batch.live(self.vault) or active_actions) \
                        or time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
            with self._lock:
                calls_left = {kind: n for kind, n in self._calls.items() if n}
                mutations_left = self._mutations
                busy = self.busy
            if self.service_runtime.active_calls:
                calls_left["service"] = self.service_runtime.active_calls
            actions_left = {action.id: action.status for action in cancelled.values()
                            if action.status == "running"}
            batch_left = batch.live(self.vault)
            if first_stop:
                phase("work_cancelled",
                      turn="none" if turn is None else "still_running" if busy else "stopped",
                      actions={action.id: action.status for action in cancelled.values()},
                      batch_still_running=batch_left,
                      released_waits=released, calls_still_running=calls_left,
                      mutations_still_running=mutations_left)
                # A thread whose turn this stop cut off is parked, durably and
                # through the writer that is still open, so it reopens as
                # interrupted with committed work intact (CORE-02B).
                session_id = getattr(getattr(self.loop, "ctx", None), "session", None) \
                    if turn is not None else None
                if session_id:
                    try:
                        store = SessionStore(self.vault)
                        if store.load(session_id).status == "open":
                            store.append(session_id, {
                                "type": "status", "status": "parked",
                                "note": "interrupted: the Core stopped while a turn was running; "
                                        "resume this thread to continue"})
                            phase("session_parked", session=session_id)
                            self.hub.publish({"type": "session_interrupted", "session": session_id})
                    except Exception:                       # noqa: BLE001
                        pass          # a missing/unreadable log never blocks a stop
                # Stop observing before draining writes so a final Core
                # replacement is never reclassified as a direct human edit.
                if self.watcher is not None:
                    self.watcher.close()

            # Once grace expires, stop *new* writer submissions even when an
            # admitted turn/action has not returned.  This preserves the
            # existing guarantee that a late batch result cannot commit after
            # a stop.  Crucially, a timeout here does not release the index or
            # lease: an already-running writer operation still owns both.
            if busy or calls_left or mutations_left or batch_left or actions_left:
                writer_drained: bool | None = None
                if self.writer is not None:
                    writer_drained = self.writer.close(timeout=self.WRITER_STOP_SECONDS)
                    phase("writer_drained", drained=bool(writer_drained),
                          writer_alive=self.writer.alive)
                detail = {"reason": "admitted_work_still_running",
                          "turn": bool(busy), "calls": calls_left,
                          "mutations": mutations_left, "batch": batch_left,
                          "actions": actions_left,
                          "writer_drained": writer_drained}
                if writer_drained is False:
                    detail["reason"] = "writer_still_running"
                self._shutdown_pending = detail
                phase("shutdown_pending", **detail)
                self._persist_shutdown_phases()
                return False

            if self.writer is not None:
                drained = self.writer.close(timeout=self.WRITER_STOP_SECONDS)
                phase("writer_drained", drained=bool(drained), writer_alive=self.writer.alive)
                if not drained:
                    detail = {"reason": "writer_still_running", "writer_alive": self.writer.alive}
                    self._shutdown_pending = detail
                    phase("shutdown_pending", **detail)
                    self._persist_shutdown_phases()
                    return False

            try:
                self.index_service.close()
            except Exception as exc:                         # noqa: BLE001
                detail = {"reason": "index_close_failed", "error": type(exc).__name__}
                self._shutdown_pending = detail
                phase("shutdown_pending", **detail)
                self._persist_shutdown_phases()
                return False
            phase("index_closed")
            if self.coordinator is not None:
                self.coordinator.release()
                phase("lease_released")
            if self.writer is not None:
                # Detached only after the lease is safely gone: a late
                # session append continues to meet a closed writer rather
                # than falling through to an uncoordinated write.
                detach_core_writer(self.vault, self.writer)
                self.writer.release_lifecycle_owner()
            # This App created (or took over) the outside-server manager:
            # stop its background portal too, or it outlives the library.
            if self.mcp is not None and getattr(self.mcp, "owner", None) is self:
                try:
                    self.mcp.stop()
                except Exception:                            # noqa: BLE001
                    pass
            self._persist_shutdown_phases()
            self._shutdown_pending = {}
            self._closed = True
            return True

    def request_host_stop(self, *, force: bool = False) -> dict[str, Any]:
        """Validate an explicit Host stop before its server is shut down.

        There is intentionally no idle/client-count path here.  If useful
        work is active the Host must show it and ask the person to resolve or
        stop it; a background Core is never silently killed because a tab
        closed.  ``force`` is retained for an explicit tray confirmation and
        is recorded in the response for a caller to surface.
        """
        if not self.host_managed:
            raise ApiError(404, "this Core is not managed by Librarian Host")
        active = self.running()
        if active and not force:
            raise ApiError(409, "Core has active work; resolve it or explicitly force Quit",
                           active=active, checkpoint="forced_engagement_close")
        return {"stopping": True, "forced": bool(force), "active": active}

    def _serialized(self, caller: str, fn: Callable[[], Any]) -> Any:
        """Run an App-owned mutation through the Core lifetime boundary.

        The admission count deliberately spans ``writer.submit`` itself, not
        only the check before it.  That makes configuration and checkpoint
        writes indistinguishable from HTTP mutations to shutdown: either they
        are refused under the admission lock or shutdown waits for them.
        """
        with self._counted_mutation(f"the {caller} mutation"):
            if self.writer is not None:
                return self.writer.submit(fn, caller=caller)
            # Offline compatibility Apps have no lifetime writer. They still
            # acquire the actual interprocess lease for each mutation, so a
            # Core starting between discovery and migration cannot race those
            # writes.
            with self._offline_lock:
                if self._offline_lease is not None:
                    return fn()
                lease = VaultCoordinator(self.vault, protocol_version=PROTOCOL_VERSION)
                try:
                    lease.acquire()
                except (LeaseHeldError, StaleLeaseError) as exc:
                    raise ApiError(409, f"CORE_REQUIRED: {exc}") from exc
                self._offline_lease = lease
                try:
                    return fn()
                finally:
                    self._offline_lease = None
                    lease.release()

    def _reconcile_interrupted_operations(self) -> list[dict[str, Any]]:
        """Turn ambiguous pre-crash writes into one durable review card each.

        This intentionally runs only for the mutable, coordinated Core.  An
        offline App owns neither the lease nor the writer and must not inspect
        or mutate another Core's recovery state.  The writer log is evidence,
        not an instruction queue: we make no repair or replay here.
        """
        if self.writer is None:
            return []
        interrupted = self.writer.interrupted_operations()
        if not interrupted:
            return []

        def reconcile() -> list[dict[str, Any]]:
            recovered: list[dict[str, Any]] = []
            for record in interrupted:
                current: dict[str, str] = {}
                for target in record["targets"]:
                    try:
                        current[target] = fingerprint(self.vault.safe_relative(target))
                    except (OSError, ValueError, Refusal):
                        current[target] = "unreadable"
                identity = json.dumps({
                    "operation_id": record["operation_id"],
                    "caller": record["caller"],
                    "targets": record["targets"],
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                scope = "operation-recovery:" + record["operation_id"][:100] + ":" + \
                    hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
                evidence = {
                    "operation_id": record["operation_id"],
                    "caller": record["caller"],
                    "started_at": record["started_at"],
                    "targets": list(record["targets"]),
                    "precondition_fingerprints": dict(record["precondition_fingerprints"]),
                    "observed_fingerprints": dict(record["observed_fingerprints"]),
                    "current_fingerprints": current,
                    "consequence": ("The operation may have partially applied. "
                                    "Librarian made no repair or replay."),
                }
                if record.get("integrity_error"):
                    evidence["integrity_error"] = str(record["integrity_error"])
                recovered.append(self.checkpoints.ensure_historical(
                    "operation_recovery", scope, evidence=evidence,
                    choices=["acknowledge"], default="acknowledge",
                    requester="operation-recovery"))
            return recovered

        return self.writer.submit(reconcile, caller="operation-recovery")

    # -- models -----------------------------------------------------------
    def _migrate_legacy_host_routes(self) -> None:
        """Move pre-registry tier choices onto explicit Host records once.

        Older 2.x settings used ``provider`` plus a global ``base_urls`` map.
        Keep accepting that shape at API boundaries, but migrate existing
        persisted choices into a seeded host (or a deterministic custom host)
        at Core start.  A host record contains no key value, and preserving the
        old base URL means this is an identity-preserving upgrade rather than
        a quiet route substitution.
        """
        try:
            marker = int(self.settings.data.get("host_route_migration") or 0)
        except (TypeError, ValueError):
            marker = 0
        if marker >= 1:
            return
        raw_tiers = self.settings.data.get("tiers")
        if not isinstance(raw_tiers, list):
            self.settings.update(host_route_migration=1)
            return
        base_urls = self.settings.data.get("base_urls") or {}
        base_urls = base_urls if isinstance(base_urls, dict) else {}
        converted: list[Any] = []
        changed = False
        for raw in raw_tiers:
            if not isinstance(raw, dict) or raw.get("host_id") or not raw.get("model"):
                converted.append(raw)
                continue
            provider = str(raw.get("provider") or "").strip().casefold()
            preset = PRESETS.get(provider)
            if preset is None:
                converted.append(raw)
                continue
            seeded_id = f"preset-{provider}"
            try:
                seeded = self.hosts.get(seeded_id)
            except KeyError:
                # A malformed local host registry should not make an existing
                # legacy route disappear. Leave that row for the normal 2.x
                # compatibility path and retry after the registry is repaired.
                converted.append(raw)
                continue
            requested_base = str(base_urls.get(provider) or raw.get("base_url") or "").strip().rstrip("/")
            host_id = seeded.id
            if requested_base and requested_base != seeded.base_url.rstrip("/"):
                suffix = hashlib.sha256(f"{provider}\n{requested_base}".encode("utf-8")).hexdigest()[:12]
                host_id = f"legacy-{provider}-{suffix}"
                try:
                    self.hosts.get(host_id)
                except KeyError:
                    try:
                        self.hosts.upsert({
                            "id": host_id,
                            "display_name": f"Migrated {provider} route",
                            "protocol": str(preset.get("protocol") or seeded.protocol),
                            "base_url": requested_base,
                            "auth_ref": str(preset.get("key_env") or seeded.auth_ref),
                        })
                    except (OSError, TypeError, ValueError):
                        # Keep the original route intact when personal host
                        # storage is unavailable; this migration must never
                        # turn a recoverable settings upgrade into data loss.
                        converted.append(raw)
                        continue
            retained = {key: value for key, value in raw.items()
                        if key not in {"provider", "host_id", "base_url"}}
            converted.append({"host_id": host_id, "provider": host_id, **retained})
            changed = True
        self.settings.update(tiers=converted if changed else raw_tiers,
                             host_route_migration=1)

    def _binding_for_route(self, role: str, route: dict[str, Any], *,
                           source: str = "explicit") -> RoleRouteBinding:
        host_id = str(route.get("host_id") or route.get("provider") or "")
        if host_id in PRESETS and not route.get("host_id"):
            provider = host_id
            host_id = "preset-" + provider
            bases = self.settings.data.get("base_urls") or {}
            requested_base = str(bases.get(provider) or route.get("base_url") or "").strip().rstrip("/") \
                if isinstance(bases, dict) else ""
            if role in CHAT_ROLES and not route.get("host_id") and requested_base and \
                    requested_base != str(PRESETS[provider].get("base_url") or "").rstrip("/"):
                suffix = hashlib.sha256(f"{provider}\n{requested_base}".encode("utf-8")).hexdigest()[:12]
                host_id = f"legacy-{provider}-{suffix}"
        try:
            host = self.hosts.get(host_id)
        except KeyError:
            # Keep the unavailable identity visible; execution refuses it.
            host = None
        protocol = host.protocol if host is not None else ""
        return RoleRouteBinding(
            role=role, host_id=host_id, model_id=str(route.get("model") or ""),
            protocol=protocol,
            endpoint_fingerprint=host.endpoint_fingerprint if host is not None else "",
            adapter_id=("legacy_anthropic_messages" if protocol == "anthropic" else
                        "legacy_openai_chat") if role in CHAT_ROLES else "",
            evidence_kind="chat_qualification" if role in CHAT_ROLES else "service_contract",
            source=source, updated_at=now_iso())

    def _legacy_chat_bindings(self, tiers: Any) -> dict[str, RoleRouteBinding]:
        rows: dict[str, RoleRouteBinding] = {}
        for position, role in enumerate(("lead", "scribe", "clerk")):
            route = tiers[position] if isinstance(tiers, list) and position < len(tiers) else None
            if isinstance(route, dict) and route.get("model"):
                rows[role] = self._binding_for_route(role, route, source="legacy_tier")
            elif position and (parent := ("lead", "scribe")[position - 1]) in rows:
                rows[role] = RoleRouteBinding(role=role, inherits_from=parent,
                                             source="inherited", updated_at=now_iso())
        if "scribe" in rows:
            rows["research_helper"] = RoleRouteBinding(
                role="research_helper", inherits_from="scribe", source="inherited", updated_at=now_iso())
        return rows

    def _service_binding(self, slot: str, provider: str, model: str, *, host_id: str = "") -> RoleRouteBinding:
        from .embed import LOCAL_KINDS
        if not model:
            return RoleRouteBinding(role=slot, source="unconfigured", updated_at=now_iso())
        if slot == "embeddings" and provider in LOCAL_KINDS and not host_id:
            return RoleRouteBinding(role=slot, host_id=f"local-{provider}", model_id=model,
                                     protocol="local", evidence_kind="local_service",
                                     source="legacy_service", updated_at=now_iso())
        return self._binding_for_route(slot, {"provider": provider, "model": model, "host_id": host_id},
                                       source="legacy_service")

    def _migrate_legacy_role_routes(self) -> None:
        def migrate() -> None:
            if self.role_routes.exists():
                rows = self.role_routes.raw()  # Invalid state is never silently regenerated.
                projected = self._tiers_projection(rows, self.settings.data.get("tiers") or [])
                if projected != self.settings.data.get("tiers"):
                    self.settings.update_in_operation(tiers=projected)
                return
            rows = self._legacy_chat_bindings(self.settings.data.get("tiers"))
            for slot in ("ocr", "tts", "stt", "embeddings"):
                value = str(self.vault.setting("services", slot) or "")
                if slot == "embeddings" and value.startswith("api:"):
                    value = value[4:]
                provider, _, model = value.partition(":")
                rows[slot] = self._service_binding(slot, provider, model)
            self.role_routes.initialize_if_absent(rows)
        self._serialized("role-route-migration", migrate)

    def _migrate_service_routes(self) -> None:
        """Promote the earlier metadata mirrors once, preserving legacy vectors."""
        def migrate() -> None:
            if self.settings.data.get("service_route_migration") == 1:
                for slot in ("ocr", "tts", "stt", "embeddings"):
                    binding = self.role_routes.resolve(slot)
                    value = ""
                    if binding is not None and binding.model_id:
                        provider = binding.host_id
                        if binding.protocol == "local":
                            provider = provider.removeprefix("local-")
                        elif provider.startswith("preset-") and provider[7:] in PRESETS:
                            try:
                                host = self.hosts.get(provider)
                                if host.base_url.rstrip("/") == PRESETS[provider[7:]]["base_url"].rstrip("/"):
                                    provider = provider[7:]
                            except KeyError:
                                pass
                        value = f"{provider}:{binding.model_id}"
                    if value != str(self.vault.setting("services", slot) or ""):
                        self.vault.set_setting("services", slot, value)
                return
            rows = self.role_routes.raw()
            for slot in ("ocr", "tts", "stt", "embeddings"):
                value = str(self.vault.setting("services", slot) or "")
                if slot == "embeddings":
                    value = value or str(self.vault.setting("search", "vectors") or "")
                    if value.startswith("api:"):
                        value = value[4:]
                provider, _, model = value.partition(":")
                rows[slot] = self._service_binding(slot, provider, model)
            self.role_routes.save(rows)
            self.settings.update_in_operation(service_route_migration=1)
        self._serialized("service-route-migration", migrate)

    def _chat_bindings_for_tiers(self, tiers: list[dict[str, Any]]) -> dict[str, RoleRouteBinding]:
        rows = self.role_routes.raw()
        previous = dict(rows)
        for role in CHAT_ROLES:
            rows.pop(role, None)
        for role, binding in self._legacy_chat_bindings(tiers).items():
            rows[role] = self._revised_binding(previous.get(role), binding)
        helper = previous.get("research_helper")
        if helper is not None and not helper.inherits_from:
            rows["research_helper"] = helper
        return rows

    def _tiers_projection(self, rows: dict[str, RoleRouteBinding],
                          hints: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rebuild the old picker from authoritative bindings after a crash."""
        roles = ("lead", "scribe", "clerk")
        positions = [i for i, role in enumerate(roles)
                     if role in rows and rows[role].model_id and not rows[role].inherits_from]
        if not positions or self.role_routes.resolve("lead", rows) is None:
            return []
        projected = []
        for i in range(max(positions) + 1):
            binding = self.role_routes.resolve(roles[i], rows)
            if binding is None:
                raise ValueError(f"no route for picker position {i + 1}")
            hint = hints[i] if i < len(hints) and isinstance(hints[i], dict) else {}
            identity = str(hint.get("host_id") or hint.get("provider") or "")
            identity = "preset-" + identity if identity in PRESETS and not hint.get("host_id") else identity
            projected.append(dict(hint) if identity == binding.host_id and hint.get("model") == binding.model_id
                             else {"host_id": binding.host_id, "provider": binding.host_id,
                                   "model": binding.model_id})
        return projected

    @staticmethod
    def _revised_binding(previous: RoleRouteBinding | None,
                         binding: RoleRouteBinding) -> RoleRouteBinding:
        from dataclasses import replace
        return replace(binding, revision=previous.revision + 1 if previous else 1,
                       updated_at=now_iso())

    def _save_service_binding(self, slot: str, provider: str, model: str, *, host_id: str = "") -> None:
        rows = self.role_routes.raw()
        rows[slot] = self._revised_binding(rows.get(slot), self._service_binding(slot, provider, model, host_id=host_id))
        self.role_routes.save(rows)

    def _configured_provider(self, choice: dict[str, Any]) -> Provider | None:
        settings = dict(choice)
        host_id = str(settings.get("host_id") or "")
        configured_host: Host | None = None
        if host_id:
            try:
                host = self.hosts.get(host_id)
            except KeyError as exc:
                raise ProviderError(str(exc)) from exc
            if not host.enabled:
                raise ProviderError(f"host {host.display_name!r} is disabled")
            settings = {**settings, "provider": host.id, "protocol": host.protocol,
                        "base_url": host.base_url, "key_env": host.auth_ref,
                        "timeout": host.timeout}
            configured_host = host
        base = self.settings.data.get("base_urls", {}).get(choice.get("provider", ""))
        if base and not settings.get("base_url"):
            settings["base_url"] = base
        provider = from_settings(settings)
        return LimitedProvider(provider, configured_host, self.host_limiter) \
            if provider is not None and configured_host is not None else provider

    def meta(self) -> dict[str, Any]:
        """Non-secret Core/adapter handshake and operational health contract."""
        lease = self.coordinator.status() if self.coordinator is not None else {}
        shutdown = self._shutdown_health()
        if self.writer is None:
            writer_state = "not_coordinated"
        elif self.writer.alive:
            writer_state = "draining" if shutdown["state"] == "pending" else "ready"
        else:
            writer_state = "closed"
        return {
            "core_version": __version__, "protocol_version": PROTOCOL_VERSION,
            "ui_build_id": "development" if __version__.endswith(".dev0") else __version__,
            "compatible_adapter_range": ADAPTER_PROTOCOL_RANGE,
            "enabled_features": ["vault_coordinator", "vault_writer", "document_leases",
                                 "host_registry", "qualification", "agent_profiles",
                                 "tool_bundles", "audited_macros", "checkpoints",
                                 "v1_migration", "internal_packs"],
            "non_secret_health": {
                "vault_lease": "held" if self.coordinator is not None and self.coordinator.held
                else "not_coordinated",
                "lease": lease,
                "writer": writer_state,
                "index": "retained_pending_shutdown" if shutdown["state"] == "pending" else "ready",
                "shutdown": shutdown,
                "watcher": self.watcher.health() if self.watcher is not None else {"status": "not_coordinated"},
                "secret_source": "obsidian_managed" if self.secret_source == "obsidian" else self.keys.backend,
            },
        }

    # -- document-aware coordination -------------------------------------
    @mutation_entry("the document heartbeat")
    def document_heartbeat(self, path: str, *, editor: str = "Obsidian", dirty: bool = True,
                           baseline: str = "") -> dict[str, Any]:
        try:
            return self.document_leases.heartbeat(path, editor=editor, dirty=dirty,
                                                  baseline=baseline)
        except (ValueError, OSError) as exc:
            raise ApiError(400, str(exc)) from exc

    @mutation_entry("the document release")
    def document_release(self, path: str, *, editor: str = "") -> dict[str, Any]:
        try:
            self.document_leases.release(path, editor=editor)
            return self.document_leases.view(path)
        except (ValueError, OSError) as exc:
            raise ApiError(400, str(exc)) from exc

    @mutation_entry("the document change notification")
    def document_changed(self, path: str) -> dict[str, Any]:
        try:
            self.document_leases.observe_change(path)
            return {"observed": path, "debounce_seconds": 1}
        except (ValueError, OSError) as exc:
            raise ApiError(400, str(exc)) from exc

    def documents(self) -> dict[str, Any]:
        return self.document_leases.view()

    # -- personal host registry -------------------------------------------
    def host_list(self) -> dict[str, Any]:
        return {"hosts": self.hosts.all()}

    def _workflow_readiness(self, profile_id: str) -> tuple[str, str]:
        """Check the compact surface a selected interactive profile can use.

        The generic L0 contract proves that the registry, macros, and default
        compact bundles agree.  The Model Tile must also expose when the
        *selected* profile intentionally narrows that surface too far to lead
        a normal project walk; otherwise the UI says ``walk ready`` and the
        first provider request discovers the mismatch.

        This is diagnostic only: it never broadens a profile, changes a
        session, or writes qualification evidence.  Non-lead profiles remain
        valid for their delegated roles, but are not interactive Lead
        surfaces.
        """
        outcome, detail = self._l0_contract_check()
        try:
            profile = self.profiles.get(profile_id)
        except (KeyError, ValueError):
            return "blocked", (f"selected agent profile {profile_id!r} is unavailable; "
                               "choose a Lead profile before starting a walk")
        if profile.role != "lead":
            return "blocked", (f"profile {profile.id!r} has role {profile.role!r}; "
                               "choose a Lead profile for an interactive research walk")
        from .agent_runtime import PROJECT_BOOTSTRAP_PURPOSES, required_bundle_actions, select_bundle
        for purpose in sorted(PROJECT_BOOTSTRAP_PURPOSES):
            required = required_bundle_actions("frame", purpose=purpose,
                                               project="", project_exists=False)
            offered = {spec.name for spec in select_bundle(
                "contribute", "frame", purpose=purpose, project="", project_exists=False,
                profile=profile)}
            missing = [name for name in required if name not in offered]
            if missing:
                return "blocked", (f"profile {profile.id!r} hides required Frame action "
                                   f"{missing[0]!r}; repair its allowed bundles or permission "
                                   "ceiling before starting a project walk")
        return outcome, detail

    def _passive_qualification(self, host_id: str, model: str, role: str) -> dict[str, Any]:
        """Inspect evidence without invalidating it or queuing paid work."""
        current = self._qualification_fingerprints(host_id, model, role)
        existing = self.qualifications.get(host_id, model, role)
        change = self.qualifications.route_change_kind(
            host_id=host_id, model_id=model, role=role,
            compatibility_fingerprint=current["compatibility"],
            behavior_fingerprint=current["behavior"])
        if existing is None:
            return {"role": role, "status": "experimental", "freshness": "missing", "fresh": False,
                    "invalidation": ""}
        freshness = "current" if existing.fresh() else "expired_or_missing"
        status, invalidation = existing.status, existing.invalidation
        if change == "hard":
            status, freshness = "stale", "hard_incompatible"
            invalidation = "hard compatibility fingerprint changed; run L0 then requalify"
        elif change == "soft":
            freshness = "advisory_stale"
            invalidation = "advisory stale behavior fingerprint; review before release use"
        return {"host_id": existing.host_id, "model_id": existing.model_id,
                "role": existing.role, "status": status,
                "updated_at": existing.updated_at, "expires_at": existing.expires_at,
                "invalidation": invalidation, "evidence_runs": existing.evidence_runs,
                "fresh": existing.fresh() and change != "hard", "freshness": freshness}

    def route_readiness(self, profile_id: str = "", session_id: str = "") -> dict[str, Any]:
        """Return compact, non-secret route evidence for the existing picker.

        This endpoint deliberately does not discover models or run probes: a
        tile opening must not make an endpoint request or a paid call.  It
        reflects only routes already selected, previously qualified, or
        shipped as release-lead candidates.  Model listing remains the host
        card's existing explicit action.
        """
        # Readiness enriches the existing picker; it must never make model
        # selection disappear because an internal diagnostic itself is
        # temporarily unavailable.  Qualification still fails closed through
        # the explicit L0 path, while the picker can show an honest warning
        # and let the person inspect or choose a different already-known
        # route.
        selected_profile = profile_id or str(self.settings.data.get("agent_profile") or "lead")
        try:
            outcome, detail = self._workflow_readiness(selected_profile)
        except Exception:  # noqa: BLE001 - diagnostic boundary, not execution
            outcome, detail = (
                "error",
                "Core workflow self-check is unavailable; route selection remains available.",
            )
        core = {"ok": outcome == "pass", "status": outcome, "detail": detail,
                "profile": selected_profile,
                "session": session_id}
        # Qualification evidence is role-specific at the runtime boundary
        # (``_require_profile_qualification`` uses ``profile.role``), not
        # keyed to a person-created profile id.  Keep readiness aligned with
        # that same lookup so a custom Lead profile does not incorrectly show
        # its already-qualified Lead route as experimental.
        try:
            qualification_role = self.profiles.get(selected_profile).role
        except (KeyError, ValueError):
            qualification_role = selected_profile
        candidates: dict[tuple[str, str], dict[str, str]] = {}

        def add_route(host_id: Any, model: Any, provider: Any = "") -> None:
            wanted_host, wanted_model = str(host_id or "").strip(), str(model or "").strip()
            if not wanted_host or not wanted_model:
                return
            candidates[(wanted_host, wanted_model)] = {
                "host_id": wanted_host, "model": wanted_model,
                "provider": str(provider or wanted_host),
            }

        stored_bindings = self.role_routes.raw()
        bindings = {role: self.role_routes.resolve(role, stored_bindings) for role in CHAT_ROLES}
        try:
            task_slot = self._profile_binding_role(self.profiles.get(selected_profile))
        except (KeyError, ValueError, ApiError):
            task_slot = ""
        task_binding = bindings.get(task_slot)
        for binding in bindings.values():
            if binding is not None and binding.source != "unconfigured":
                add_route(binding.host_id, binding.model_id)
        for route in self.settings.data.get("tiers") or []:
            if isinstance(route, dict):
                add_route(route.get("host_id") or route.get("provider"), route.get("model"),
                          route.get("provider") or route.get("host_id"))
        for row in self.qualifications.runs.values():
            add_route(row.host_id, row.model_id, row.host_id)
        for raw in release_leads().get("leads", []):
            if isinstance(raw, dict):
                add_route(raw.get("host_id") or raw.get("provider"), raw.get("model"), raw.get("provider"))

        routes: list[dict[str, Any]] = []
        for host_id, model in sorted(candidates):
            try:
                host = self.hosts.get(host_id)
                health = dict(host.health) if isinstance(host.health, dict) else {}
            except KeyError:
                host = None
                health = {"status": "unknown", "detail": "Host record is unavailable"}
            # A picker opening is a read, not a qualification operation.  In
            # particular, do not call ``qualification_status`` here: that
            # method intentionally refreshes stale evidence, runs L0, and
            # may queue L2/L3 work.  Surface a prospective stale state
            # instead; the normal explicit qualification action remains the
            # only path which mutates evidence or creates paid-work plans.
            by_role = {role: self._passive_qualification(host_id, model, role)
                       for role in dict.fromkeys((*CHAT_ROLES, qualification_role))}
            qualification = by_role[qualification_role]
            assigned = [binding for binding in bindings.values() if binding is not None and
                        binding.host_id == host_id and binding.model_id == model]
            binding_errors = {}
            for binding in assigned:
                if host is None:
                    binding_errors[binding.role] = "host unavailable"
                elif not host.enabled:
                    binding_errors[binding.role] = "host disabled"
                elif binding.protocol != host.protocol or binding.endpoint_fingerprint != host.endpoint_fingerprint:
                    binding_errors[binding.role] = "endpoint changed; review and select the route again"
            route_detail = str(qualification.get("invalidation") or health.get("detail") or "")
            row = {
                "host_id": host_id, "provider": host_id, "model": model,
                "role": qualification_role,
                "qualification": qualification,
                "qualification_by_role": by_role,
                "active_task": bool(task_binding and task_binding.host_id == host_id and
                                    task_binding.model_id == model),
                "task_profile": selected_profile,
                "bound_roles": [binding.role for binding in assigned],
                "binding_errors": binding_errors,
                "host_enabled": host.enabled if host is not None else False,
                "freshness": qualification.get("freshness", "missing"),
                "host_health": health or {"status": "unknown", "detail": "Host has not been tested"},
                "core_workflow": {"ok": core["ok"], "status": core["status"], "detail": core["detail"]},
                # The live fixture preflight is intentionally owned by the
                # evaluator.  Never claim it passed merely because the model
                # picker opened; the UI renders this honestly as unchecked.
                "fixture_preflight": {"ok": None, "status": "not_run",
                                        "detail": "Run an evaluation fixture preflight before paid walks."},
                "detail": route_detail,
            }
            routes.append(row)
            # The chat picker retains legacy provider keys while settings and
            # stored tiers use the seeded Host id.  Include an alias row so
            # existing cards receive readiness without changing selection.
            if host_id.startswith("preset-"):
                routes.append({**row, "host_id": host_id[len("preset-"):],
                               "provider": host_id[len("preset-"):]})
        # A pack that failed to load leaves every route ``unknown``; say why
        # here rather than letting reviewed routes quietly look unreviewed.
        return {"core": core, "routes": routes,
                "bindings": {role: binding.public() if binding is not None else None
                             for role, binding in bindings.items()},
                "expectation_pack": self.invocation_runtime.expectations.status()}

    def _release_contract(self, host_id: str) -> dict[str, Any]:
        """The public route facts a bundled L3 result is allowed to cover.

        Secret source and a user's key are intentionally not part of this
        release comparison.  Their account is tested separately by L1; the
        release record instead proves an exact provider endpoint/model and
        Core/tool/prompt contract.
        """
        try:
            host = self.hosts.get(host_id)
            endpoint = {"protocol": host.protocol, "base_url": host.base_url,
                        "auth_ref": host.auth_ref}
            fingerprint = host.endpoint_fingerprint
        except KeyError:
            preset = PRESETS.get(host_id, {})
            endpoint = {"protocol": str(preset.get("protocol") or ""),
                        "base_url": str(preset.get("base_url") or ""),
                        "auth_ref": str(preset.get("key_env") or "")}
            fingerprint = endpoint_fingerprint(endpoint)
        return {"core_version": __version__, "protocol_version": PROTOCOL_VERSION,
                "tool_contract_version": RELEASE_TOOL_CONTRACT_VERSION,
                "prompt_contract_version": RELEASE_PROMPT_CONTRACT_VERSION,
                "endpoint": endpoint, "endpoint_fingerprint": fingerprint}

    def release_lead_options(self) -> dict[str, Any]:
        """First-run choices and their next safe action, never provider keys.

        Stable releases return two `verified_release` candidates.  A source
        checkout can honestly show pending candidates too, but labels them
        unavailable rather than implying a fictional qualification.
        """
        manifest = release_leads()
        options: list[dict[str, Any]] = []
        for raw in manifest.get("leads", []):
            if not isinstance(raw, dict):
                continue
            host_id = str(raw.get("host_id") or raw.get("provider") or "")
            model = str(raw.get("model") or "")
            contract = self._release_contract(host_id)
            lead, reason = release_lead_for_route(host_id, model, contract=contract,
                                                   role="lead", manifest=manifest)
            probe = None
            if lead is not None:
                current = self._qualification_fingerprints(host_id, model, "lead")
                self._refresh_qualification_route(host_id, model, "lead", current)
                probe = self.qualifications.matching_l1_probe(
                    host_id=host_id, model_id=model, role="lead",
                    compatibility_fingerprint=current["compatibility"],
                    observed_model=str(lead.get("model_version") or ""),
                )
            try:
                key = self.host_key_status(host_id)
            except ApiError:
                key = {"needed": True, "saved": False}
            try:
                l1_plan = self.qualification_plan(host_id, model, "lead", "L1") \
                    if host_id and model else None
            except ApiError:
                l1_plan = None
            options.append({"id": raw.get("id", ""), "provider": raw.get("provider", ""),
                            "host_id": host_id, "model": model,
                            "qualification": "verified_release" if lead is not None and probe is not None
                            else ("release_probe_required" if lead is not None
                                  else str(raw.get("qualification") or "pending_release_ci")),
                            "release_qualified": lead is not None,
                            "available": lead is not None,
                            "account_probe": None if probe is None else {
                                "id": probe.id, "at": probe.at, "observed_model": probe.observed_model},
                            "reason": reason or ("run the account L1 probe after entering your key"
                                                  if probe is None and lead is not None
                                                  else "account L1 probe passed" if lead is not None else ""),
                            "key": key,
                            "l1_plan": l1_plan})
        return {"integrity_valid": bool(manifest.get("integrity_valid")),
                "setup_required": not bool(self.settings.data.get("tiers")) and bool(options),
                "choices": options}

    @mutation_entry("the release-lead selection")
    def select_release_lead(self, lead_id: str, *, key: str = "", overwrite: bool = False,
                            checkpoint_id: str = "") -> dict[str, Any]:
        """Complete the explicit first-run hosted-lead path.

        The bundled L3 record is only a release claim; it does not grant a
        person's account access.  This method therefore verifies the exact
        signed row before saving an optional personal key, creates/reuses the
        visible L1-spend checkpoint, and selects the route only after that
        account's tool-call probe observes the expected exact model.  Pending
        development candidates cannot pass this path.
        """
        wanted = str(lead_id or "").strip()
        manifest = release_leads()
        raw = next((row for row in manifest.get("leads", [])
                    if isinstance(row, dict) and str(row.get("id") or "") == wanted), None)
        if raw is None:
            raise ApiError(404, "no bundled release lead has that id")
        host_id = str(raw.get("host_id") or raw.get("provider") or "")
        model = str(raw.get("model") or "")
        if not host_id or not model:
            raise ApiError(409, "bundled release lead has no usable route")
        contract = self._release_contract(host_id)
        lead, reason = release_lead_for_route(host_id, model, contract=contract,
                                               role="lead", manifest=manifest)
        if lead is None or str(lead.get("id") or "") != wanted:
            raise ApiError(409, "bundled lead is not currently verified release evidence",
                           reason=reason or "release lead is unavailable")
        try:
            host = self.hosts.get(host_id)
        except KeyError as exc:
            raise ApiError(409, f"bundled lead refers to an unavailable host: {host_id}") from exc
        if key.strip():
            self.host_save_key(host_id, key, overwrite=overwrite)
        elif self.host_key_status(host_id).get("needed") and not self.host_key_status(host_id).get("saved"):
            raise ApiError(409, f"enter a key for {host.display_name} before the account probe")

        # L1 is deliberately not auto-approved: first-run selection shows
        # its cost/endpoint consequence in a real checkpoint.  The browser
        # resolves that row and repeats this id with its checkpoint id.
        probe = self.run_qualification(host_id, model, "lead", "L1", False,
                                       scenario=f"release:{wanted}", checkpoint_id=checkpoint_id)
        if probe.get("run", {}).get("outcome") != "pass":
            return {"selected": False, "lead": wanted, "probe": probe,
                    "reason": "the account L1 tool-call probe did not pass; no route was selected"}
        status = self.lead_status([{"host_id": host_id, "model": model}])
        if status.get("status") != "eligible":
            return {"selected": False, "lead": wanted, "probe": probe, "lead_status": status,
                    "reason": "the account probe did not match current release evidence"}
        selected = self.set_lead({"host_id": host_id, "model": model})
        self.hub.publish({"type": "release_lead_selected", "lead": wanted,
                          "host_id": host_id, "model": model})
        return {"selected": True, "lead": wanted, "probe": probe, "tiers": selected["tiers"],
                "lead_status": selected["lead"]}

    @mutation_entry("the host update")
    def host_upsert(self, row: Any) -> dict[str, Any]:
        if not isinstance(row, dict):
            raise ApiError(400, "host is a JSON object")
        try:
            saved = self.hosts.upsert(row)
            auth_ref = self.hosts.get(str(saved["id"])).auth_ref
            if auth_ref:
                self.keys.register_ref(auth_ref)
            return saved
        except HostFullRecordError as exc:
            raise ApiError(400, "host_requires_full_record", missing_fields=exc.missing_fields,
                           detail=str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise ApiError(400, str(exc)) from exc

    @mutation_entry("the host controls update")
    def host_update_controls(self, row: Any) -> dict[str, Any]:
        """Apply the small, non-identity host control surface.

        ``POST /api/hosts`` remains a complete-record replacement for
        compatibility.  This separate route is intentionally the only place
        a popup/control can send a partial host row.
        """
        if not isinstance(row, dict):
            raise ApiError(400, "host controls are a JSON object")
        try:
            return self.hosts.update_controls(row)
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise ApiError(400, str(exc)) from exc

    @mutation_entry("the host removal")
    def host_remove(self, host_id: str) -> dict[str, Any]:
        try:
            self.hosts.remove(host_id)
            return {"removed": host_id}
        except (KeyError, ValueError) as exc:
            raise ApiError(400, str(exc)) from exc

    def host_key_status(self, host_id: str) -> dict[str, Any]:
        try:
            host = self.hosts.get(host_id)
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        return self.keys.status_ref(host.auth_ref, label=host.display_name)

    @mutation_entry("the host key update")
    def host_save_key(self, host_id: str, key: str, overwrite: bool = False) -> dict[str, Any]:
        try:
            host = self.hosts.get(host_id)
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        if not host.auth_ref:
            raise ApiError(400, "this host does not require a key")
        before = self.keys.status_ref(host.auth_ref, label=host.display_name)
        if before.get("saved") and not overwrite:
            raise ApiError(409, "a key is already saved", confirm=(
                f"Replace the saved key for {host.display_name}?"))
        try:
            return self.keys.save_ref(host.auth_ref, key, label=host.display_name)
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        except PermissionError as exc:
            raise ApiError(409, str(exc), managed_by="obsidian") from exc
        except OSError as exc:
            raise ApiError(503, f"could not save the key: {exc}") from exc

    @mutation_entry("the host test")
    def host_test(self, host_id: str, model: str = "") -> dict[str, Any]:
        try:
            host = self.hosts.get(host_id)
            provider = self._configured_provider({"host_id": host_id, "model": model})
            if provider is None:
                raise ProviderError("not configured")
            checked = provider.check()
            health = self.hosts.mark_health(host_id, ok=bool(checked.get("ok")),
                                            detail=str(checked.get("error") or checked.get("status") or ""),
                                            model=model)
            self.hub.publish({"type": "route_health_changed", "host_id": host_id,
                              "model": model, "health": health.get("health", {})})
            return {"host": host.public(), "check": checked}
        except (KeyError, ProviderError) as exc:
            try:
                self.hosts.mark_health(host_id, ok=False, detail=str(exc), model=model)
            except (KeyError, OSError):
                pass
            raise ApiError(400, str(exc)) from exc

    # -- tiered qualification ----------------------------------------------
    def _qualification_fingerprints(self, host_id: str, model: str, role: str) -> dict[str, str]:
        """Dependency evidence for a route, split into hard and soft inputs."""
        from .agent_runtime import BUNDLES, MACROS
        try:
            host = self.hosts.get(host_id)
            endpoint = {"protocol": host.protocol, "fingerprint": host.endpoint_fingerprint}
        except KeyError:
            # Legacy provider routes remain supported through 2.x; their
            # preset is a stable endpoint dependency too.
            preset = PRESETS.get(host_id, {})
            endpoint = {"protocol": preset.get("protocol", ""), "base_url": preset.get("base_url", "")}
        try:
            profile = self.profiles.get(role).public()
        except (KeyError, ValueError):
            profile = {"id": role}
        schemas = [{"name": spec.name, "tier": spec.tier, "effect": spec.effect,
                    "schema": spec.json_schema()}
                   for spec in sorted(REGISTRY.for_tier("curate"), key=lambda x: x.name)]
        # The adapter and the exact model expectation are part of the wire /
        # parser contract, not presentation metadata.  A changed adapter ABI,
        # protocol renderer, endpoint identity, or exact capability record
        # therefore produces a hard qualification fingerprint.  Do this
        # passively: constructing a configured provider reads no secret and
        # does not discover models or make a paid probe.
        adapter_contract: dict[str, Any] = {
            "id": "unresolved", "version": "", "abi": 0, "protocol": "",
            "expectation_id": "", "expectation_fingerprint": "", "expectation_status": "unreviewed",
        }
        try:
            provider = self._configured_provider({"host_id": host_id, "model": model})
            if provider is not None:
                summary = self.invocation_runtime.adapter_summary(provider, model_id=model)
                expected = summary.get("expectation") if isinstance(summary.get("expectation"), dict) else {}
                adapter_contract = {
                    "id": str(summary.get("id") or ""),
                    "version": str(summary.get("version") or ""),
                    "abi": int(summary.get("abi") or 0),
                    "protocol": str(summary.get("protocol") or ""),
                    "expectation_id": str(expected.get("id") or ""),
                    "expectation_fingerprint": str(expected.get("fingerprint") or ""),
                    "expectation_status": str(expected.get("status") or "unreviewed"),
                }
        except (KeyError, ProviderError, ValueError):
            # Legacy/malformed routes are still fingerprinted from their
            # endpoint/model below.  Their unresolved adapter state cannot
            # masquerade as compatible evidence.
            pass
        return fingerprints(
            protocol=PROTOCOL_VERSION, tool_schema=schemas,
            response_contract={
                "tool_call_id": "string", "arguments": "object",
                "adapter_contract": adapter_contract,
                "l1_probe": {
                    "version": L1_PROBE_CONTRACT_VERSION,
                    "calls": "exactly_one:librarian_probe",
                    "arguments": {"ok": True},
                    "returned_model": "exact_requested_model",
                },
            },
            endpoint=endpoint, model=model,
            security_policy={"registry": "closed", "no_silent_failover": True,
                             "secret_source": self.secret_source},
            prompt_bundle={"loop_base": "v2", "reply_length": self.settings.data.get("reply_length", "")},
            profile=profile,
            bundle={name: list(row.names) for name, row in BUNDLES.items()},
            macros={name: {"version": row.version, "steps": [step.tool for step in row.steps]}
                    for name, row in MACROS.items()})

    @staticmethod
    def _l0_contract_check() -> tuple[str, str]:
        """Run the deterministic side of qualification without a model call."""
        from .agent_runtime import (MACROS, PROJECT_BOOTSTRAP_PURPOSES,
                                    required_bundle_actions, select_bundle)
        failures = [spec.name for spec in REGISTRY.for_tier("curate")
                    if spec.json_schema().get("type") != "object"]
        failures += [f"macro:{macro.id}:{step.tool}" for macro in MACROS.values()
                     for step in macro.steps if step.tool not in REGISTRY]
        # Exercise the same state-aware overlay that a serial model turn sees.
        # The static bundle table alone is not enough: ``open_session`` moves
        # an add-project walk into Frame before its next model request.
        for purpose in sorted(PROJECT_BOOTSTRAP_PURPOSES):
            required = required_bundle_actions("frame", purpose=purpose,
                                               project="", project_exists=False)
            offered = {spec.name for spec in select_bundle(
                "contribute", "frame", purpose=purpose, project="", project_exists=False)}
            failures += [f"bundle:{purpose}:frame:{name}" for name in required if name not in offered]
        return (("pass", "deterministic registry and macro contract checks passed")
                if not failures else ("fail", ", ".join(failures)))

    def _record_l0(self, host_id: str, model: str, role: str, fingerprints_row: dict[str, str],
                   *, scenario: str = "default") -> dict[str, Any]:
        """Persist one deterministic run for a specific dependency fingerprint."""
        if self.qualifications.has_run(
                host_id=host_id, model_id=model, role=role, level="L0",
                compatibility_fingerprint=fingerprints_row["compatibility"],
                behavior_fingerprint=fingerprints_row["behavior"], scenario=scenario):
            rows = [row for row in self.qualifications.runs.values()
                    if (row.host_id, row.model_id, row.role, row.level, row.scenario,
                        row.compatibility_fingerprint, row.behavior_fingerprint) ==
                    (host_id, model, role, "L0", scenario,
                     fingerprints_row["compatibility"], fingerprints_row["behavior"])]
            return max(rows, key=lambda row: row.at).__dict__
        outcome, detail = self._l0_contract_check()
        run = self.qualifications.record(
            host_id=host_id, model_id=model, role=role, level="L0", outcome=outcome,
            compatibility_fingerprint=fingerprints_row["compatibility"],
            behavior_fingerprint=fingerprints_row["behavior"], detail=detail, scenario=scenario)
        return run.__dict__

    def _refresh_qualification_route(self, host_id: str, model: str, role: str,
                                     fingerprints_row: dict[str, str] | None = None) -> tuple[Any, dict[str, Any] | None]:
        """Invalidate a route and make the resulting requalification actionable.

        Hard protocol/schema/endpoint/model/security changes immediately
        remove verified selection, run L0, and create dormant L2/L3 plans.
        Soft prompt/macro/profile changes retain selectability with an
        advisory marker, run L0, and queue the cheaper L2 review.  Queuing is
        not execution: paid work still requires the UI spend checkpoint and
        an artifact-bearing evaluator result.
        """
        current = fingerprints_row or self._qualification_fingerprints(host_id, model, role)
        kind = self.qualifications.route_change_kind(
            host_id=host_id, model_id=model, role=role,
            compatibility_fingerprint=current["compatibility"],
            behavior_fingerprint=current["behavior"])
        q = self.qualifications.invalidate_route(
            host_id=host_id, model_id=model, role=role,
            compatibility_fingerprint=current["compatibility"],
            behavior_fingerprint=current["behavior"])
        self.evaluation_jobs.invalidate_route(
            host_id=host_id, model_id=model, role=role,
            compatibility_fingerprint=current["compatibility"],
            behavior_fingerprint=current["behavior"])
        if not kind or q is None:
            return q, None

        scenario = f"invalidation:{kind}:{current['compatibility'][:10]}:{current['behavior'][:10]}"
        l0 = self._record_l0(host_id, model, role, current, scenario=scenario)
        levels = ("L1", "L2", "L3") if kind == "hard" else ("L2",)
        queued: list[dict[str, Any]] = []
        for level in levels:
            if level == "L1":
                # An L1 is a provider call, so it remains an explicit
                # checkpointed action rather than a background cost.
                continue
            plan = self.qualification_plan(host_id, model, role, level)
            existing = self.evaluation_jobs.pending_for(
                host_id=host_id, model_id=model, role=role, level=level,
                compatibility_fingerprint=current["compatibility"],
                behavior_fingerprint=current["behavior"], scenario=scenario)
            job = existing or self.evaluation_jobs.create(plan, scenario=scenario)
            if existing is None:
                job = self.evaluation_jobs.mark_automatic(job, kind=kind)
            queued.append(job.public())

        # ``record`` derives a new Qualification row from the L0 result.  Put
        # the reason back on that current row so every adapter sees the
        # actionable distinction rather than a mysterious status downgrade.
        refreshed = self.qualifications.get(host_id, model, role)
        if refreshed is not None:
            q = self.qualifications.annotate_route(
                host_id=host_id, model_id=model, role=role, invalidation=(
                f"{'hard compatibility' if kind == 'hard' else 'advisory_stale: behavior'} "
                f"fingerprint changed; L0 {l0.get('outcome')}; "
                f"{'L1–L3' if kind == 'hard' else 'L2'} requalification queued"))
        event = {"kind": kind, "l0": l0, "required_levels": list(levels),
                 "queued_jobs": queued,
                 "paid_work": "not started; approve a spend checkpoint before evaluation"}
        self.hub.publish({"type": "qualification_requalification_queued", "host_id": host_id,
                          "model": model, "role": role, **event})
        return q, event

    def qualification_plan(self, host_id: str, model: str, role: str = "lead",
                           level: str = "L1") -> dict[str, Any]:
        if level not in EVALUATION_LEVELS:
            raise ApiError(400, f"level is one of {EVALUATION_LEVELS}")
        try:
            host = self.hosts.get(host_id)
        except KeyError as exc:
            # Legacy tiers still name provider presets directly through 2.x.
            # They are not editable HostRegistry records, but their stable
            # endpoint is sufficient for a transparent qualification plan.
            preset = PRESETS.get(host_id)
            if preset is None:
                raise ApiError(404, str(exc)) from exc
            try:
                host = Host(id=host_id, display_name=host_id.capitalize(),
                            protocol=str(preset.get("protocol") or "openai"),
                            base_url=str(preset.get("base_url") or "https://api.openai.com/v1"),
                            auth_ref=str(preset.get("key_env") or ""), seeded=True).normalise()
            except ValueError as host_error:
                raise ApiError(400, str(host_error)) from host_error
        if not model.strip():
            raise ApiError(400, "model is required")
        counts = {"L0": 1, "L1": 1, "L2": 3, "L3": 5}
        # This is deliberately an estimate, not invented pricing.  Providers
        # differ and can change pricing; a host may later supply a rate card.
        return {"host_id": host_id, "model": model, "role": role, "level": level,
                "runs": counts[level], "estimated_minutes": {"L0": 0, "L1": 1,
                                                                 "L2": 8, "L3": 90}[level],
                "estimated_cost_usd": None,
                "requires_spend_confirmation": level != "L0",
                "resumable": level in ("L2", "L3"),
                "host": host.public(), "fingerprints": self._qualification_fingerprints(host_id, model, role)}

    def qualification_status(self, host_id: str, model: str, role: str = "lead") -> dict[str, Any]:
        current = self._qualification_fingerprints(host_id, model, role)
        q, requalification = self._refresh_qualification_route(host_id, model, role, current)
        rows = [r for r in self.qualifications.runs.values()
                if (r.host_id, r.model_id, r.role) == (host_id, model, role)]
        return {"qualification": None if q is None else {
                    "host_id": q.host_id, "model_id": q.model_id, "role": q.role,
                    "status": q.status, "updated_at": q.updated_at,
                    "expires_at": q.expires_at, "invalidation": q.invalidation,
                    "evidence_runs": q.evidence_runs,
                    "fresh": q.fresh(),
                    "freshness": "current" if q.fresh() else "expired_or_missing"},
                "runs": [r.__dict__ for r in sorted(rows, key=lambda r: r.at, reverse=True)],
                "jobs": self.evaluation_jobs.list(host_id=host_id, model_id=model, role=role),
                "requalification": requalification,
                "fingerprints": current}

    def _evaluation_spend_checkpoint(self, plan: dict[str, Any], *, confirm_spend: bool,
                                     checkpoint_id: str = "") -> None:
        """Turn paid-evaluation consent into a durable UI decision.

        The old ``confirm_spend`` bool remains a 2.x compatibility shim for
        scripts and older adapters. It now writes the same approved checkpoint
        that Browser/Obsidian UI resolves explicitly, rather than leaving a
        policy sentence for a model or caller to infer.
        """
        fingerprint = str((plan.get("fingerprints") or {}).get("compatibility") or "")
        scope = "evaluation:" + hashlib.sha256(json.dumps({
            "host": plan.get("host_id"), "model": plan.get("model"), "role": plan.get("role"),
            "level": plan.get("level"), "compatibility": fingerprint,
        }, sort_keys=True).encode("utf-8")).hexdigest()[:20]
        approved = False
        if checkpoint_id:
            try:
                row = self.checkpoints.get(checkpoint_id)
                approved = row.get("type") == "evaluation_spend" and row.get("scope") == scope and \
                    row.get("resolution") == "approve" and not row.get("expired")
            except (KeyError, ValueError):
                approved = False
        if approved:
            return
        create = lambda: self.checkpoints.ensure(
            "evaluation_spend", scope,
            evidence={"plan": {key: value for key, value in plan.items() if key != "host"},
                      "consequence": "This may make paid provider calls; the run remains resumable."},
            choices=["approve", "cancel"], default="cancel", requester="person")
        row = self._serialized("evaluation-spend", create)
        if confirm_spend:
            # A legacy explicit confirmation is a person action too. Persist
            # it as an ordinary resolution so audit/UI tools see the decision.
            if not row.get("resolution"):
                row = self._serialized("evaluation-spend",
                                       lambda: self.checkpoints.resolve(row["id"], "approve"))
            self.hub.publish({"type": "checkpoint_resolved", "checkpoint": row})
            return
        self.hub.publish({"type": "checkpoint_created", "checkpoint": row})
        raise ApiError(409, "confirm evaluation spend", plan=plan,
                       checkpoint="evaluation_spend", checkpoint_record=row)

    @mutation_entry("the qualification run")
    def run_qualification(self, host_id: str, model: str, role: str = "lead",
                          level: str = "L0", confirm_spend: bool = False,
                          scenario: str = "default", checkpoint_id: str = "") -> dict[str, Any]:
        """Run the low-cost qualification tiers synchronously.

        L0 is deterministic and suitable for every CI change.  L1 is one real
        endpoint/tool probe and needs an explicit spend choice.  L2/L3 create
        a durable, budget-confirmed plan rather than hiding a long paid walk
        behind an HTTP request.  A local evaluator or release CI advances the
        plan only by submitting an artifact-backed observed result.
        """
        plan = self.qualification_plan(host_id, model, role, level)
        if level in ("L2", "L3"):
            self._evaluation_spend_checkpoint(plan, confirm_spend=confirm_spend,
                                              checkpoint_id=checkpoint_id)
            try:
                job = self.evaluation_jobs.create(plan, scenario=scenario)
            except ValueError as exc:
                raise ApiError(400, str(exc)) from exc
            result = {"queued": True, "status": "queued", "plan": plan, "job": job.public(),
                      "detail": "No model call has started. Submit each artifact-backed evaluator "
                                "result to advance this resumable job."}
            self.hub.publish({"type": "qualification_job_queued", "job": job.public()})
            return result
        if level != "L0":
            self._evaluation_spend_checkpoint(plan, confirm_spend=confirm_spend,
                                              checkpoint_id=checkpoint_id)
        fps = plan["fingerprints"]
        if level == "L0":
            run = self._record_l0(host_id, model, role, fps)
            return {"run": run, "status": self.qualification_status(host_id, model, role)}
        started = time.monotonic()
        observed_model = ""
        probe_validation: dict[str, Any] = {
            "contract_version": L1_PROBE_CONTRACT_VERSION,
            "passed": False,
            "checks": {},
            "failure_codes": ["not_run"],
            "requested_model": model,
            "observed_model": "",
        }
        try:
            provider = self._configured_provider({"host_id": host_id, "model": model})
            if provider is None:
                raise ProviderError("host is not configured")
            probe_tools = [ToolDef("librarian_probe", "Return a small probe object.",
                                   {"type": "object", "properties": {"ok": {"type": "boolean"}},
                                    "required": ["ok"], "additionalProperties": False})]
            # One prompt for both steps; the second replays the first exactly
            # as the agent loop does (ADAPT-07).
            probe_prompt = [{"role": "user", "content": (
                'Call librarian_probe with {"ok": true}. When you receive its result, '
                "reply in plain text with the token it returns.")}]
            probe_payload = InvocationPayload.from_legacy(
                "You are a qualification probe.", probe_prompt, probe_tools,
                max_tokens=64, temperature=0)
            probe_scope = InvocationScope(
                role=role,
                task=TaskContract(id="l1-tool-probe", kind="qualification",
                                  interaction="qualification_probe",
                                  required_capabilities=frozenset({"tool_use"})),
                behavior_mode="provider_default")
            reply = self.invocation_runtime.invoke(provider, probe_payload, scope=probe_scope)
            observed_model = str(reply.model or "")
            probe_validation = validate_l1_probe(reply, model)
            if probe_validation["passed"]:
                # A one-shot proposal is not enough for tool work: send the
                # tool result back and require a final answer that uses it.
                continuation_payload = InvocationPayload.from_legacy(
                    "You are a qualification probe.", continuation_messages(probe_prompt, reply),
                    probe_tools, max_tokens=256, temperature=0)
                continuation_scope = InvocationScope(
                    role=role,
                    task=TaskContract(id="l1-tool-continuation", kind="qualification",
                                      interaction="qualification_probe",
                                      required_capabilities=frozenset({"tool_use"})),
                    behavior_mode="provider_default")
                final_reply = self.invocation_runtime.invoke(provider, continuation_payload,
                                                             scope=continuation_scope)
                continuation = validate_l1_continuation(reply, final_reply, model)
                probe_validation["continuation"] = continuation
                probe_validation["passed"] = bool(probe_validation["passed"] and continuation["passed"])
                probe_validation["failure_codes"] = list(probe_validation["failure_codes"]) + [
                    f"continuation_{code}" for code in continuation["failure_codes"]]
            else:
                probe_validation["continuation"] = {"passed": False, "failure_codes": ["not_run"],
                                                    "checks": {}}
            good = bool(probe_validation["passed"])
            outcome = "pass" if good else "fail"
            detail = ("strict tool continuation probe passed" if good else
                      "strict tool continuation probe failed: " +
                      ", ".join(probe_validation["failure_codes"]))
            health = self.hosts.mark_health(host_id, ok=good, detail=detail, model=model)
            self.hub.publish({"type": "route_health_changed", "host_id": host_id,
                              "model": model, "health": health.get("health", {})})
        except ModelIdentityMismatchError as exc:
            # The invocation runtime has already blocked this reply from any
            # Loop/tool surface.  L1 is the one controlled observer allowed
            # to inspect the live normalized reply so it can retain exact
            # requested/observed evidence rather than reducing a route drift
            # to an unhelpful generic transport failure.
            observed_model = exc.result.observed_model
            if exc.reply is not None:
                probe_validation = validate_l1_probe(exc.reply, model)
            else:
                probe_validation = {
                    "contract_version": L1_PROBE_CONTRACT_VERSION,
                    "passed": False,
                    "checks": {"returned_model": False},
                    "failure_codes": ["returned_model_mismatch"],
                    "requested_model": model,
                    "observed_model": observed_model,
                }
            outcome = "fail"
            detail = "strict tool-call probe failed: " + ", ".join(
                probe_validation["failure_codes"])
            try:
                health = self.hosts.mark_health(host_id, ok=False, detail=detail, model=model)
                self.hub.publish({"type": "route_health_changed", "host_id": host_id,
                                  "model": model, "health": health.get("health", {})})
            except (KeyError, OSError):
                pass
        except ProviderError as exc:
            outcome, detail = "unavailable", str(exc)[:500]
            probe_validation = {
                "contract_version": L1_PROBE_CONTRACT_VERSION,
                "passed": False,
                "checks": {},
                "failure_codes": ["provider_unavailable"],
                "requested_model": model,
                "observed_model": observed_model,
            }
            try:
                health = self.hosts.mark_health(host_id, ok=False, detail=detail, model=model)
                self.hub.publish({"type": "route_health_changed", "host_id": host_id,
                                  "model": model, "health": health.get("health", {})})
            except (KeyError, OSError):
                pass
        run = self.qualifications.record(host_id=host_id, model_id=model, role=role, level="L1",
                                         outcome=outcome, compatibility_fingerprint=fps["compatibility"],
                                         behavior_fingerprint=fps["behavior"],
                                         duration_ms=round((time.monotonic() - started) * 1000),
                                         detail=detail, observed_model=observed_model,
                                         probe_validation=probe_validation, scenario=scenario)
        return {"run": run.__dict__, "status": self.qualification_status(host_id, model, role)}

    def qualification_jobs(self, host_id: str = "", model: str = "", role: str = "") -> dict[str, Any]:
        return {"jobs": self.evaluation_jobs.list(host_id=host_id, model_id=model, role=role)}

    def _qualification_job_current(self, job_id: str) -> tuple[Any, dict[str, str]]:
        """Load a job and reject it if the current hard contract changed."""
        try:
            job = self.evaluation_jobs.get(job_id)
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        current = self._qualification_fingerprints(job.host_id, job.model_id, job.role)
        self._refresh_qualification_route(job.host_id, job.model_id, job.role, current)
        return job, current

    @mutation_entry("the qualification pause")
    def pause_qualification_job(self, job_id: str, reason: str = "") -> dict[str, Any]:
        self._qualification_job_current(job_id)
        try:
            job = self.evaluation_jobs.pause(job_id, reason or "paused by person")
        except ValueError as exc:
            raise ApiError(409, str(exc)) from exc
        self.hub.publish({"type": "qualification_job_paused", "job": job.public()})
        return {"job": job.public()}

    @mutation_entry("the qualification resume")
    def resume_qualification_job(self, job_id: str) -> dict[str, Any]:
        self._qualification_job_current(job_id)
        try:
            job = self.evaluation_jobs.resume(job_id)
        except ValueError as exc:
            raise ApiError(409, str(exc)) from exc
        self.hub.publish({"type": "qualification_job_resumed", "job": job.public()})
        return {"job": job.public()}

    @mutation_entry("the qualification cancellation")
    def cancel_qualification_job(self, job_id: str, reason: str = "") -> dict[str, Any]:
        try:
            job = self.evaluation_jobs.cancel(job_id, reason or "cancelled by person")
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        except ValueError as exc:
            raise ApiError(409, str(exc)) from exc
        self.hub.publish({"type": "qualification_job_cancelled", "job": job.public()})
        return {"job": job.public()}

    @mutation_entry("the qualification result")
    def record_qualification_job_result(self, job_id: str, *, outcome: str, artifact: str,
                                         detail: str = "", duration_ms: int = 0,
                                         cost_usd: float = 0.0) -> dict[str, Any]:
        """Attach one real L2/L3 evaluator outcome to a queued job.

        This endpoint does not execute or simulate a golden walk.  It is the
        hand-off from a local evaluator/CI harness after it has produced a
        durable artifact.  Passing and failing results need an artifact so a
        future qualification review can inspect the observed work.
        """
        if outcome not in ("pass", "fail", "unavailable", "cancelled"):
            raise ApiError(400, "outcome is pass, fail, unavailable or cancelled")
        if outcome in ("pass", "fail") and not str(artifact).strip():
            raise ApiError(400, "pass/fail evaluator results require an artifact reference")
        job, current = self._qualification_job_current(job_id)
        try:
            job = self.evaluation_jobs.begin_result(
                job_id, compatibility_fingerprint=current["compatibility"])
        except ValueError as exc:
            raise ApiError(409, str(exc)) from exc
        try:
            run = self.qualifications.record(
                host_id=job.host_id, model_id=job.model_id, role=job.role, level=job.level,
                outcome=outcome, compatibility_fingerprint=job.compatibility_fingerprint,
                behavior_fingerprint=job.behavior_fingerprint, scenario=job.scenario,
                duration_ms=duration_ms, cost_usd=cost_usd, detail=detail, artifact=artifact)
            job = self.evaluation_jobs.finish_result(job_id, run.id, outcome=outcome,
                                                      detail=detail or f"{outcome} result recorded")
        except (OSError, ValueError) as exc:
            # The result slot is intentionally made resumable after a local
            # persistence error instead of looking as though it completed.
            try:
                self.evaluation_jobs.pause(job_id, f"could not persist evaluator result: {exc}")
            except (KeyError, ValueError):
                pass
            raise ApiError(503, f"could not persist evaluator result: {exc}") from exc
        status = self.qualification_status(job.host_id, job.model_id, job.role)
        self.hub.publish({"type": "qualification_job_result", "job": job.public(),
                          "run": run.__dict__})
        return {"job": job.public(), "run": run.__dict__, "status": status}

    # -- profiles and UI checkpoints --------------------------------------
    def _active_agent_profile(self) -> Any:
        """Return the vault's selected agent profile or fail closed.

        Settings can be edited outside the browser, so a missing/deleted
        profile is not silently replaced with the broader legacy behaviour.
        A person can pick ``lead`` explicitly to recover it through the
        ordinary settings endpoint.
        """
        profile_id = str(self.settings.data.get("agent_profile") or "lead")
        try:
            return self.profiles.get(profile_id)
        except (KeyError, ValueError) as exc:
            raise ApiError(409, f"selected agent profile {profile_id!r} is unavailable; choose a profile",
                           agent_profile=profile_id) from exc

    def _tier_choice(self, n: int) -> dict[str, Any] | None:
        """2.x projection of the canonical Lead/Scribe/Clerk bindings."""
        if n not in (1, 2, 3):
            return None
        return self._role_choice(("lead", "scribe", "clerk")[n - 1])

    @staticmethod
    def _profile_binding_role(profile: Any) -> str:
        role = str(profile.route_policy.get("binding_role") or profile.role)
        if role not in CHAT_ROLES:
            raise ApiError(409, f"profile {profile.id!r} needs a route slot; choose one in Profiles",
                           profile=profile.public())
        return role

    def _role_choice(self, role: str, *, validate_host: bool = True) -> dict[str, Any] | None:
        binding = self.role_routes.resolve(role)
        if binding is None or binding.source == "unconfigured":
            return None
        route = {"host_id": binding.host_id, "provider": binding.host_id, "model": binding.model_id}
        if not binding.host_id or not binding.model_id:
            raise ApiError(409, f"{role} has an incomplete route; select its model again", role=role)
        if validate_host:
            try:
                host = self.hosts.get(binding.host_id)
            except KeyError as exc:
                raise ApiError(409, f"{role}'s host is unavailable; select its route again", role=role) from exc
            if not host.enabled:
                raise ApiError(409, f"{role}'s host is disabled", role=role)
            if binding.protocol != host.protocol or binding.endpoint_fingerprint != host.endpoint_fingerprint:
                raise ApiError(409, f"{role}'s host endpoint changed; review and select its route again",
                               role=role, route=route)
        return route

    def role_provider(self, role: str) -> Provider | None:
        route = self._role_choice(role)
        return self._provider_for(route) if route is not None else None

    def _helper_provider(self, tier: int) -> Provider | None:
        return self.role_provider("lead") if tier == 1 else self._provider_for_profile("research_helper")

    def _provider_for_profile(self, profile_id: str) -> Provider | None:
        profile = self.profiles.get(profile_id)
        return self.role_provider(self._profile_binding_role(profile))

    def _route_rate_card(self, route: dict[str, Any] | None, profile: Any) -> dict[str, Any] | None:
        """Find an auditable price card for conservative profile cost caps.

        A profile-supplied card is intentional for a personal/custom endpoint.
        For a known preset, reuse a catalogued model profile only when both
        input and output prices are present.  Unknown prices never become a
        guessed zero: a non-zero cost budget then stops before the call.
        """
        policy = getattr(profile, "route_policy", {}) or {}
        direct = policy.get("rate_card") if isinstance(policy, dict) else None
        if isinstance(direct, dict):
            return direct
        if not route:
            return None
        provider = str(route.get("provider") or "").casefold()
        model = str(route.get("model") or "").casefold()
        if not provider or not model:
            return None
        if route.get("host_id") and not str(route["host_id"]).startswith("preset-"):
            return None  # custom endpoint pricing must be explicitly supplied by the profile
        if provider.startswith("preset-") and provider[7:] in PRESETS:
            family = provider[7:]
            host = self.hosts.get(provider)
            preset = PRESETS[family]
            if host.base_url.rstrip("/") == str(preset.get("base_url") or "").rstrip("/") and \
                    host.protocol == preset.get("protocol"):
                provider = family
        catalogues = {**_shipped_profiles(), **_remembered_profiles(), **self._model_sources()}
        known = catalogues.get((provider, model)) or {}
        incoming, outgoing = known.get("price_input_per_1m"), known.get("price_output_per_1m")
        if incoming is None or outgoing is None:
            return None
        return {"price_input_per_1m": incoming, "price_output_per_1m": outgoing}

    def _background_endpoint_route(self, endpoint: Any,
                                   fallback_route: dict[str, Any] | None = None) -> dict[str, Any]:
        """Recover the actual non-secret route used by a Clerk/Scribe task.

        ``ProviderEndpoint`` wraps the modern host-registry provider, while a
        2.x ``[clerk]`` route is a plain Clerk endpoint.  Both can be matched
        to a registered host by its public endpoint identity.  A route that
        cannot be identified is deliberately not treated as qualified: the
        person can add the host record and keep using the same model rather
        than allowing an invisible configuration escape hatch.
        """
        carrier = getattr(endpoint, "provider", None)
        host = getattr(carrier, "host", None) if carrier is not None else None
        provider = getattr(carrier, "provider", carrier) if carrier is not None else endpoint
        model = str(getattr(provider, "model", "") or getattr(endpoint, "model", "") or "")
        if host is not None:
            return {"host_id": str(host.id), "provider": str(host.id), "model": model}
        if isinstance(endpoint, ProviderEndpoint) and fallback_route:
            return dict(fallback_route)
        base_url = str(getattr(provider, "base_url", "") or
                       getattr(endpoint, "base_url", "") or "").rstrip("/")
        matches = [row for row in self.hosts.all()
                   if base_url and str(row.get("base_url") or "").rstrip("/") == base_url]
        if len(matches) == 1:
            return {"host_id": str(matches[0]["id"]), "provider": str(matches[0]["id"]),
                    "model": model}
        return {"provider": "", "model": model, "base_url": base_url}

    def _background_profile_guard(self, profile: Any, endpoint: Any,
                                  fallback_route: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Apply the Clerk/Scribe profile before each single-shot model call."""
        route = self._background_endpoint_route(endpoint, fallback_route)
        if not str(route.get("host_id") or route.get("provider") or "") or not route.get("model"):
            raise ValueError("bind this legacy Clerk/Scribe endpoint to a Host Registry record before "
                             "using a screened or verified profile")
        permitted, reason = route_permitted(profile, route)
        if not permitted:
            raise ValueError(reason)
        # A host-backed ProviderEndpoint retains its bounded retry/circuit
        # behaviour, but its policy comes from the role profile rather than
        # the selected lead profile.
        provider = getattr(endpoint, "provider", None)
        if isinstance(provider, LimitedProvider):
            provider.retry_policy = str(getattr(profile, "retry_policy", "bounded"))
        lead = self.lead_status([route]) if profile.role == "lead" else {}
        self._require_profile_qualification(profile, route, lead)
        return self._route_rate_card(route, profile)

    def _background_profile_endpoint(self, role: str, endpoint: Any, tier: int) -> Any:
        """Wrap one configured background endpoint in its fixed role profile.

        The ``tier`` argument is a compatibility bridge for a ProviderEndpoint
        with a legacy preset route; it is never a privilege selector.  Profile
        role, route allow-list and qualification remain the authority.
        """
        from .clerk import UnavailableEndpoint
        if isinstance(endpoint, (ProfiledEndpoint, UnavailableEndpoint)):
            return endpoint
        try:
            profile = self.profiles.get(role)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"the vault's {role} profile is unavailable") from exc
        binding_role = self._profile_binding_role(profile)
        fallback_route = self._role_choice(binding_role)

        def guard(current: Any, target: Any) -> dict[str, Any] | None:
            if isinstance(target, ProviderEndpoint) and fallback_route is not None:
                # Recheck before each call in a Clerk task pool. An already
                # constructed endpoint cannot continue after its host or
                # assignment changes and borrow evidence for a different one.
                if self._role_choice(binding_role) != fallback_route:
                    raise ValueError(f"{role} route changed; restart this task on its selected route")
            return self._background_profile_guard(current, target, fallback_route)

        return ProfiledEndpoint(
            endpoint, profile, gate=self.profile_gate,
            route_guard=guard,
            rate_card=self._route_rate_card(fallback_route, profile),
        )

    def _helper_profile_guard(self, profile: Any, tier: int) -> dict[str, Any] | None:
        """Check the fixed read-only helper profile against its actual route.

        Delegation chooses tier 2 when available and falls back to tier 1, so
        the guard receives the *resolved* tier rather than trusting the model's
        requested label.  It keeps helper runs under the same route allow-list,
        role-qualification and cost-card policy as an interactive agent turn.
        """
        route = self._role_choice("lead" if tier == 1 else self._profile_binding_role(profile))
        if route is None:
            raise ValueError(f"no route is configured for helper tier {tier}")
        permitted, reason = route_permitted(profile, route)
        if not permitted:
            raise ValueError(reason)
        lead = self.lead_status([route]) if str(getattr(profile, "role", "")) == "lead" else {}
        self._require_profile_qualification(profile, route, lead)
        return self._route_rate_card(route, profile)

    @staticmethod
    def _qualification_rank(status: str) -> int:
        return {"experimental": 0, "unavailable": 0, "screened": 1,
                "verified_local": 2, "verified_release": 2}.get(status, 0)

    def _require_profile_qualification(self, profile: Any, route: dict[str, Any],
                                       lead: dict[str, Any]) -> None:
        """Enforce an AgentProfile's qualification floor at the call boundary.

        The profile file is vault-scoped policy, so merely displaying its
        ``required_qualification`` in Settings is insufficient.  This check
        runs immediately before a model can receive a prompt.  Lead routes
        retain their stricter release/M0 policy; other roles use their own
        role-specific evidence so a screened lead cannot accidentally stand
        in for an untested Clerk or Scribe walk.

        A 2.x legacy lead override remains a deliberate person decision.  It
        is recorded by ``set_tiers`` and is never mistaken for qualification
        evidence, but preserves the established compatibility escape hatch.
        """
        required = str(getattr(profile, "required_qualification", "screened") or "screened")
        if self._qualification_rank(required) == 0:
            return
        role = str(getattr(profile, "role", "lead") or "lead")
        if role == "lead":
            if lead.get("status") == "override":
                return
            observed = str(lead.get("result") or "")
            # Older M0 eligible-lead records predate L0–L3 labels.  They are
            # still a stronger lead screen than no evidence, but they cannot
            # meet a profile that explicitly requires L3-level evidence.
            if lead.get("status") == "eligible" and not self._qualification_rank(observed):
                observed = "screened"
            if lead.get("status") == "eligible" and \
                    self._qualification_rank(observed) >= self._qualification_rank(required):
                return
            host_id = str(route.get("host_id") or route.get("provider") or "")
            model = str(route.get("model") or "")
            plan: dict[str, Any] | None = None
            if host_id and model:
                try:
                    level = "L1" if self._qualification_rank(required) <= 1 else "L3"
                    plan = self.qualification_plan(host_id, model, "lead", level)
                except ApiError:
                    pass
            raise ApiError(409,
                           f"agent profile {getattr(profile, 'id', role)!r} requires {required} "
                           f"lead qualification; this route is {observed or 'experimental'}",
                           profile=profile.public(), qualification=lead, plan=plan)

        host_id = str(route.get("host_id") or route.get("provider") or "")
        model = str(route.get("model") or "")
        if not host_id or not model:
            raise ApiError(409, "the selected route has no host/model qualification identity",
                           profile=profile.public(), route=route)
        status = self.qualification_status(host_id, model, role)
        row = status.get("qualification") or {}
        observed = str(row.get("status") or "experimental")
        fresh = bool(row.get("fresh"))
        if fresh and self._qualification_rank(observed) >= self._qualification_rank(required):
            return
        try:
            level = "L1" if self._qualification_rank(required) <= 1 else "L3"
            plan = self.qualification_plan(host_id, model, role, level)
        except ApiError:
            plan = None
        freshness = "expired" if row and not fresh else "missing"
        raise ApiError(409,
                       f"agent profile {getattr(profile, 'id', role)!r} requires {required} "
                       f"qualification for role {role!r}; this route is {observed} ({freshness})",
                       profile=profile.public(), qualification=status, plan=plan)

    @mutation_entry("the agent-profile selection")
    def set_agent_profile(self, profile_id: str) -> dict[str, Any]:
        """Select the agent policy used for subsequent chat turns.

        Switching an active run would make its trace ambiguous, so it is a
        short, explicit idle-time choice.  It remains vault-scoped and never
        changes a host, credential, or person-initiated tool permission.
        """
        wanted = str(profile_id or "").strip()
        if not wanted:
            raise ApiError(400, "agent profile id is required")
        try:
            profile = self.profiles.get(wanted)
        except (KeyError, ValueError) as exc:
            raise ApiError(404, f"no agent profile {wanted!r}") from exc
        if self.busy:
            raise ApiError(409, "wait for the active agent turn before changing its profile")
        binding_role = self._profile_binding_role(profile)
        route = self._role_choice(binding_role)
        self.settings.update(agent_profile=profile.id)
        if self.loop is not None:
            self.loop.ctx.extras["agent_profile"] = profile.id
            self.loop.configure_profile(profile, rate_card=self._route_rate_card(route, profile))
            level = self.loop.ctx.extras.get("effort") or {}
            self.loop.turn_seconds = self.loop.cap_turn_seconds(level.get("turn_seconds"))
        self.hub.publish({"type": "agent_profile_changed", "profile": profile.public()})
        return {"agent_profile": profile.public()}

    def profile_list(self) -> dict[str, Any]:
        selected = str(self.settings.data.get("agent_profile") or "lead")
        return {"profiles": self.profiles.all(), "selected": selected,
                "active": self.profile_gate.status()}

    def profile_history(self, profile_id: str) -> dict[str, Any]:
        wanted = str(profile_id or "").strip()
        if not wanted:
            raise ApiError(400, "agent profile id is required")
        try:
            # Do not expose a history for an arbitrary misspelled file key.
            self.profiles.get(wanted)
        except (KeyError, ValueError) as exc:
            raise ApiError(404, f"no agent profile {wanted!r}") from exc
        return {"id": wanted, "history": self.profiles.history(wanted)}

    def packs(self) -> dict[str, Any]:
        from .packs import all_packs, compatible
        from .packs import PACKS
        return {"packs": [{**row, "compatible": compatible(PACKS[row["id"]])}
                          for row in all_packs()]}

    @mutation_entry("the profile update")
    def profile_save(self, row: Any) -> dict[str, Any]:
        from .agent_runtime import AgentProfile
        if not isinstance(row, dict):
            raise ApiError(400, "profile is a JSON object")
        try:
            allowed = {key: value for key, value in row.items()
                       if key in AgentProfile.__dataclass_fields__}
            if "id" not in allowed or "role" not in allowed:
                raise ValueError("profile needs id and role")
            profile = AgentProfile(**allowed)
            save = lambda: self.profiles.save(profile)
            return self._serialized("profile-settings", save)
        except (TypeError, ValueError) as exc:
            raise ApiError(400, str(exc)) from exc

    def checkpoint_list(self, pending_only: bool = False) -> dict[str, Any]:
        return {"checkpoints": self.checkpoints.all(pending_only=pending_only)}

    @mutation_entry("the checkpoint creation")
    def checkpoint_create(self, type: str, scope: str, evidence: Any = None,
                          choices: Any = None, requester: str = "person") -> dict[str, Any]:
        if not type or not scope:
            raise ApiError(400, "checkpoint type and scope are required")
        if evidence is not None and not isinstance(evidence, dict):
            raise ApiError(400, "checkpoint evidence is an object")
        if choices is not None and (not isinstance(choices, list) or
                                    not all(isinstance(choice, str) for choice in choices)):
            raise ApiError(400, "checkpoint choices is a list of strings")
        create = lambda: self.checkpoints.create(type, scope, evidence=evidence or {},
                                                  choices=choices or [], requester=requester)
        row = self._serialized("checkpoint", create)
        self.hub.publish({"type": "checkpoint_created", "checkpoint": row})
        return row

    @mutation_entry("the checkpoint resolution")
    def checkpoint_resolve(self, checkpoint_id: str, choice: str) -> dict[str, Any]:
        try:
            resolve = lambda: self.checkpoints.resolve(checkpoint_id, choice)
            row = self._serialized("checkpoint", resolve)
            self.hub.publish({"type": "checkpoint_resolved", "checkpoint": row})
            return row
        except KeyError as exc:
            raise ApiError(404, str(exc)) from exc
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc

    def tier(self, n: int) -> Provider | None:
        """Legacy position API; inheritance is resolved by the role store."""
        route = self._tier_choice(n)
        return self._provider_for(route) if route is not None else None

    def _extras(self) -> dict[str, Any]:
        from . import effort
        level = effort.profile(self.settings.data.get("effort"))
        # Preserve a corrupt hand-edited setting for the explicit runtime
        # error in ``_active_agent_profile``.  Non-agent screens still need
        # to render enough state for the person to repair it.
        profile_id = str(self.settings.data.get("agent_profile") or "lead")
        extras: dict[str, Any] = {"broker": self.broker, "waiters": self.waiters,
                                  "mcp": self.mcp,
                                  # the person's effort setting, and the tiers a delegate runs on
                                  # (a ceiling: the lead may choose less with set_effort)
                                  "effort": level, "effort_ceiling": level,
                                  "agent_provider": self.tier,
                                  "helper_provider": self._helper_provider,
                                  "caller": "core",
                                  "document_leases": self.document_leases,
                                  # The registry uses this narrow executor for
                                  # every non-orchestrating tool call.  It is
                                  # the only route by which an app-backed
                                  # browser/Obsidian/Cowork request can touch
                                  # the derived SQLite index.
                                  "index_service": self.index_service,
                                  "index_access": "core",
                                  "checkpoints": self.checkpoints,
                                  "profile_store": self.profiles,
                                  "agent_profile": profile_id,
                                  "profile_gate": self.profile_gate,
                                  "helper_profile_guard": self._helper_profile_guard,
                                   "background_profile_endpoint": self._background_profile_endpoint,
                                  "invocation_runtime": self.invocation_runtime,
                                  "use_tool_bundles": True}
        if self.writer is not None:
            extras["vault_writer"] = self.writer
        from .clerk import UnavailableEndpoint
        try:
            clerk = self._provider_for_profile("clerk")
        except (ApiError, ProviderError, KeyError, ValueError) as exc:
            clerk = None
            extras["clerk"] = UnavailableEndpoint(str(exc))
        if clerk is not None:
            # A registered route is the person's current Clerk assignment. It
            # takes precedence over a retained 2.x ``[clerk]`` block, whose
            # syntax is still used when no Host Registry route is assigned.
            extras["clerk"] = ProviderEndpoint(clerk, invocation_runtime=self.invocation_runtime,
                                                role="clerk")
        try:
            scribe = self._provider_for_profile("scribe")
        except (ApiError, ProviderError, KeyError, ValueError) as exc:
            scribe = None
            extras["scribe"] = UnavailableEndpoint(str(exc))
        if scribe is not None:
            extras["scribe"] = ProviderEndpoint(scribe, invocation_runtime=self.invocation_runtime,
                                                 role="scribe")
        lead = self.lead_status()
        if lead["status"] != "none":           # carried into every call's trace (R10)
            extras["lead_status"] = lead["status"] + (f": {lead.get('reason', '')}"
                                                      if lead["status"] == "override" else "")
        return extras

    def _loop(self) -> Loop:
        profile = self._active_agent_profile()
        role = self._profile_binding_role(profile)
        route = self._role_choice(role)
        if route is not None:
            permitted, reason = route_permitted(profile, route)
            if not permitted:
                raise ApiError(409, reason, profile=profile.public(), route=route)
        provider = self.role_provider(role)
        if provider is None:
            raise ApiError(409, "choose a chat model first (Model: tier 1)")
        lead = self.lead_status([route]) if profile.role == "lead" else {}
        if lead.get("status") == "release_probe_required":
            raise ApiError(409, "run the selected route's L1 connectivity/tool probe before starting a lead session",
                           lead=lead.get("model"), qualification=lead)
        self._require_profile_qualification(profile, route or {}, lead)
        data = self.settings.data
        if self.loop is None:
            self.loop = Loop(self.vault, provider, working_context=data["working_context"],
                             reply_length=data["reply_length"], stance=data["stance"],
                             extras=self._extras(), on_event=self.hub.publish)
        else:
            self.loop.provider = provider
            self.loop.working_context = data["working_context"]
            self.loop.reply_length = data["reply_length"]
            self.loop.stance = data["stance"]
            self.loop.ctx.extras.update(self._extras())
        level = self.loop.ctx.extras["effort"]
        self.loop.configure_profile(profile, rate_card=self._route_rate_card(route, profile))
        # The provider layer itself never silently swaps models.  A bounded
        # retry policy is carried only by the host wrapper, if this route has
        # one; an unwrapped legacy provider retains its established behaviour.
        if isinstance(provider, LimitedProvider):
            provider.retry_policy = profile.retry_policy
        self.loop.max_steps = level["turn_steps"]
        self.loop.turn_seconds = self.loop.cap_turn_seconds(level["turn_seconds"])
        return self.loop

    @mutation_entry("the effort setting")
    def set_effort(self, level: Any) -> dict[str, Any]:
        """The effort slider: kept with the app's settings, applied from the next step, and
        written into an open session so its budgets follow (and the trace shows why)."""
        from . import effort
        from .session import SessionStore
        chosen = effort.profile(level)
        self.settings.update(effort=chosen["level"])
        if self.loop is not None:
            self.loop.ctx.extras["effort"] = chosen
            self.loop.max_steps, self.loop.turn_seconds = (chosen["turn_steps"],
                                                           self.loop.cap_turn_seconds(chosen["turn_seconds"]))
            if self.loop.ctx.session:
                try:
                    SessionStore(self.vault).append(self.loop.ctx.session, {
                        "type": "effort", "level": chosen["level"],
                        "budget_scale": chosen["budget_scale"]})
                except Exception:                           # noqa: BLE001
                    pass                                    # a closed or missing session
        return chosen

    # -- chat -------------------------------------------------------------
    def chat(self, text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise ApiError(400, "an empty message")
        with self._lock:
            self._admit("this message")
            if self.busy:
                raise ApiError(409, "the librarian is still answering; wait, or cancel")
            loop = self._loop()
            try:
                profile = self._active_agent_profile()
                release_profile_slot = self.profile_gate.acquire(profile)
            except ProfileCapacityError as exc:
                raise ApiError(409, str(exc), profile=profile.public()) from exc
            self.busy = True
            cancel = threading.Event()
            self._turn_cancel = cancel

        def turn() -> None:
            try:
                result = loop.send(text, cancel=cancel)
                self._touch_desk(text)
                event = {"type": "turn_done", **result.to_dict(), "session": self.session_view()}
            except Exception as exc:                        # noqa: BLE001
                event = {"type": "error", "error": f"{type(exc).__name__}: {exc}"}
            finally:
                # Free before announcing: a person who sends the moment the
                # reply lands must not be told the librarian is still
                # answering.  The profile gate is released on every error or
                # cancellation path too, so a failed provider never strands
                # a profile's only concurrency slot.
                release_profile_slot()
                with self._lock:
                    self.busy = False
                    self._turn_cancel = None
            self.hub.publish(event)
            if event["type"] == "turn_done" and event.get("reply"):
                self._review_reply(loop, str(event["reply"]))
        threading.Thread(target=turn, daemon=True, name="librarian-turn").start()
        return {"accepted": True}

    def cancel_turn(self) -> dict[str, Any]:
        with self._lock:
            if not self.busy or self._turn_cancel is None:
                return {"cancelling": False}
            self._turn_cancel.set()
        return {"cancelling": True}

    WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")

    def _review_reply(self, loop: Loop, reply: str) -> None:
        """§4 G3 on chat replies (`reply_review`): after the reply, never
        before it; the verdict is its own event, and a challenge waits for the
        lead model's next prompt."""
        from . import effort, reply_review
        level = effort.profile(self.settings.data.get("effort"))
        if not (reply_review.enabled(self.vault) or level["review_replies"]):
            return
        # The turn has already made the reply visible and cleared ``busy``.
        # A review can queue Clerk work or add a runnable challenge, so it
        # needs its own lifetime slot rather than letting shutdown mistake the
        # completed turn for all completed work.  Claim the slot before the
        # thread exists: a stop either refuses this review or retains the
        # vault until its direct filesystem writes are done.
        try:
            self._begin_mutation("the reply review")
        except ApiError:
            return
        try:
            from .tools.staging import clerk_endpoint
            ctx = Context(tier="contribute", vault=self.vault, extras=self._extras())

            def run() -> None:
                try:
                    try:
                        out = reply_review.review_reply(self.vault, reply, clerk_endpoint(ctx),
                                                        max_claims=max(1, level["review_claims"]))
                    except Exception as exc:                # noqa: BLE001
                        out = {"status": f"error: {type(exc).__name__}", "held": 0,
                               "unchecked": 0, "challenged": []}
                    if out is None:
                        return
                    loop.challenges = list(out.get("challenged") or [])
                    self.hub.publish({"type": "reply_reviewed", **out})
                finally:
                    self._end_mutation()
            threading.Thread(target=run, daemon=True, name="librarian-reply-review").start()
        except Exception:
            self._end_mutation()
            raise

    def _touch_desk(self, text: str) -> None:
        """Notes a person linked in a message (the paperclip inserts `[[...]]`)
        go on the desk of the thread's pursuit (roadmap §2 B, deferred; §4 D3),
        as opening one in the pane already does. Only notes that exist, and
        only when the thread has a pursuit; never an error for the turn."""
        if self.loop is None or not self.loop.ctx.session:
            return
        try:
            project = SessionStore(self.vault).load(self.loop.ctx.session).project
            if not project:
                return
            from .desk import DeskStore
            wanted = {m.strip().rsplit("/", 1)[-1].removesuffix(".md").casefold()
                      for m in self.WIKILINK.findall(text)}
            if not wanted:
                return
            store = DeskStore(self.vault)
            opened = [path.stem for path in notes.iter_paths(self.vault.root)
                      if path.stem.casefold() in wanted and path.stem != project]
            if opened:
                self._serialized("desk-touch", lambda: [store.touch(project, note) for note in opened])
        except Exception:                                   # noqa: BLE001
            pass                                            # the desk is a convenience

    def reset(self) -> dict[str, Any]:
        if self.busy:
            raise ApiError(409, "the librarian is still answering")
        if self.loop is not None:
            self.loop.messages.clear()
            self.loop.ctx.session = None
        self.hub.publish({"type": "conversation_reset"})
        return {"reset": True}

    def attach(self, session_id: str) -> dict[str, Any]:
        """Continue a thread in the chat: the person picked it from Sessions."""
        loop = self._loop()
        result = self.person_call("resume_session", {"session_id": session_id})
        if "error" in result:
            raise ApiError(400, result.get("detail") or result["error"], result=result)
        loop.ctx.session = session_id
        # Otherwise the person sees the old conversation replayed while the
        # model itself remembers none of it - it would greet them as a
        # stranger on the very next turn.
        loop.restore(result.get("messages") or [])
        self.hub.publish({"type": "session_attached", "session": self.session_view()})
        return {"attached": session_id, "session": self.session_view()}

    def session_view(self) -> dict[str, Any] | None:
        session = self.loop.ctx.session if self.loop is not None else None
        if not session:
            return None
        try:
            return SessionStore(self.vault).load(session).to_dict(self.vault)
        except Exception:                                   # noqa: BLE001
            return None

    # -- the person's own calls ---------------------------------------------
    def person_call(self, name: str, arguments: dict[str, Any], session: str = ""
                    ) -> dict[str, Any]:
        with self._counted_call("person", f"the call {name!r}"):
            return self._person_call(name, arguments, session)

    def _person_call(self, name: str, arguments: dict[str, Any], session: str
                     ) -> dict[str, Any]:
        extras = {k: v for k, v in self._extras().items() if k != "broker"}
        # A profile can only narrow an *agent*.  A person's explicit UI/CLI
        # action remains their curate-tier authority, never accidentally
        # inherited from the lead profile used by the chat loop.
        extras.pop("agent_profile", None)
        extras.pop("profile_store", None)
        extras["caller_kind"] = "person"
        ctx = Context(tier="curate", vault=self.vault, session=session or None, extras=extras)
        result = self._surface_checkpoint(REGISTRY.call(name, arguments, ctx), name, arguments,
                                          requester="person")
        if name in ("answer", "staging_decide", "promote_offering") and "error" not in result:
            self.hub.publish({"type": "person_acted", "tool": name})
        if name == "rewind_session" and "error" not in result and self.loop is not None \
                and self.loop.ctx.session == ctx.session:
            # The tool truncated the log itself; the running loop's own
            # in-memory context still has to forget the same messages, or the
            # very next turn would answer as if nothing had been discarded.
            self.loop.rewind_to(result["rewound_to"])
        return result

    def _surface_checkpoint(self, result: dict[str, Any], name: str, arguments: dict[str, Any],
                            *, requester: str) -> dict[str, Any]:
        """A refused write to a note being edited becomes a visible conflict
        checkpoint, and any checkpoint a call made reaches the UI at once."""
        if result.get("refused") == "DOCUMENT_ACTIVE" and "checkpoint" not in result:
            checkpoint = self._serialized("document-conflict-checkpoint", lambda: self.checkpoints.create(
                "write_conflict", str(result.get("detail") or name),
                evidence={"tool": name, "arguments": arguments,
                          "leases": self.document_leases.view().get("leases", [])},
                choices=["wait", "retry_after_review", "cancel"], requester=requester))
            result = {**result, "checkpoint": checkpoint}
            self.hub.publish({"type": "checkpoint_created", "checkpoint": checkpoint})
        elif isinstance(result.get("checkpoint"), dict):
            # Registry-owned refusals and audited macros can make an explicit
            # UI checkpoint too.  Surface it immediately rather than relying
            # on a later page refresh.
            self.hub.publish({"type": "checkpoint_created", "checkpoint": result["checkpoint"]})
        return result

    #: An MCP client is an agent, never a person: it may hold consult or
    #: contribute.  `curate` is a person's own authority (person_call).
    MCP_TIER_CEILING = "contribute"

    def mcp_call(self, name: str, arguments: Any, session: str = "",
                 tier: str = "consult") -> dict[str, Any]:
        """One tool call from an MCP connection (CORE-04A).

        The MCP process holds no vault state: it forwards each call here, and
        the Core runs it as an agent - the connection's tier capped at
        contribute, the permission broker attached, and the same writer,
        index service, document leases and checkpoints as every Core call.
        Returns the tool's result and the session the call left attached.
        """
        if tier not in TIERS:
            raise ApiError(400, f"tier is one of {list(TIERS)}")
        if not isinstance(arguments, dict):
            raise ApiError(400, "arguments is a JSON object")
        granted = TIERS[min(TIERS.index(tier), TIERS.index(self.MCP_TIER_CEILING))]
        with self._counted_call("mcp", f"the MCP call {name!r}"):
            extras = {**self._extras(), "caller_kind": "mcp", "caller": "mcp"}
            # A question for the person does not block an MCP call: it returns
            # the question (needs_person, question_id) as MCP always has; the
            # person answers in Librarian and the client calls again.
            extras.pop("waiters", None)
            ctx = Context(tier=granted, vault=self.vault, session=session or None, extras=extras)
            result = self._surface_checkpoint(REGISTRY.call(name, arguments, ctx), name, arguments,
                                              requester="mcp")
        return {"result": result, "session": ctx.session or "", "tier": granted}

    @mutation_entry("the offering decision")
    def decide_offering(self, offering: str, decision: str) -> dict[str, Any]:
        from .tools.sessions import decide_offering
        ctx = Context(tier="curate", vault=self.vault,
                      extras={k: v for k, v in self._extras().items() if k != "broker"})
        try:
            action = lambda: decide_offering(ctx, offering, decision)
            result = self._serialized("browser-promotion", action)
        except TypeError as exc:
            return {"error": "invalid_arguments", "detail": str(exc)}
        self.hub.publish({"type": "person_acted", "tool": "promote_offering"})
        return result

    # -- queued actions -----------------------------------------------------
    @mutation_entry("the action start")
    def start_action(self, name: str, inputs: dict[str, Any] | None = None) -> dict[str, Any]:
        from .tools.workflows import _library, _router
        action = Action(secrets.token_hex(4), name)
        extras = {**self._extras(), "cancel": action.cancel}

        def progress(event: dict[str, Any]) -> None:
            action.steps += 1
            action.run = event["run"]
            self.hub.publish({"type": "action_progress", **action.public()})
        extras["progress"] = progress
        ctx = Context(tier="contribute", vault=self.vault, extras=extras)
        library = _library(ctx)
        library.get(name)                                   # unknown names fail now, loudly
        # Admit and register together, under the lock close_runtime closes
        # admission under: it either sees this action or refuses it.
        with self._lock:
            self._admit(f"the action {name!r}")
            self.actions[action.id] = action

        def run() -> None:
            try:
                runner = workflows.Runner(library, ctx, _router(ctx))
                action.result = runner.start(name, inputs or {})
                action.run = action.result.get("run", action.run)
                action.status = action.result.get("status", "finished")
            except (Refusal, workflows.DefinitionError, KeyError) as exc:
                action.status = "failed"
                action.result = {"error": str(exc)}
            except Exception as exc:                        # noqa: BLE001
                action.status = "failed"
                action.result = {"error": f"{type(exc).__name__}: {exc}"}
            self.hub.publish({"type": "action_done", **action.public(),
                              "result": action.result})
        self.hub.publish({"type": "action_started", **action.public()})
        threading.Thread(target=run, daemon=True, name=f"action-{name}").start()
        return action.public()

    def cancel_action(self, action_id: str) -> dict[str, Any]:
        action = self.actions.get(action_id)
        if action is None:
            raise ApiError(404, f"no action {action_id!r}")
        action.cancel.set()
        return {"cancelling": action_id}

    # -- MCP servers (Co-work Roadmap §3, Phase 1) ---------------------------
    def _mcp(self) -> Any:
        if self.mcp is None:
            raise ApiError(409, "outside MCP servers need the `mcp` extra: "
                                "pip install resource-librarian[mcp]")
        return self.mcp

    def mcp_status(self) -> dict[str, Any]:
        mcp = self._mcp()
        from .mcp_client import redacted_args
        status = mcp.status()
        servers = mcp.servers()
        return {"servers": {name: {**status.get(name, {}), "command": d.get("command", ""),
                                   "args": redacted_args(d.get("args") or []),
                                   "env": sorted((d.get("env") or {}).keys()),
                                   "tool_names": mcp.tool_names(name)}
                            for name, d in servers.items()},
                "config_dir": str(mcp.config_dir),
                "tool_settings": dict(self.broker.settings)}

    @mutation_entry("the MCP configuration update")
    def mcp_save_config(self, servers: Any) -> dict[str, Any]:
        mcp = self._mcp()
        if not isinstance(servers, dict):
            raise ApiError(400, "mcpServers is a JSON object")
        mcp.save_config({"mcpServers": servers})
        mcp.sync()
        return self.mcp_status()

    @mutation_entry("the MCP server acceptance")
    def mcp_accept(self, name: str) -> dict[str, Any]:
        mcp = self._mcp()
        try:
            mcp.accept(name)
        except ValueError as exc:
            raise ApiError(404, str(exc)) from exc
        mcp.sync()
        return self.mcp_status()

    @mutation_entry("the MCP server update")
    def mcp_add_server(self, name: str, definition: Any) -> dict[str, Any]:
        """One server, added or replaced - a skills-registry install, or a
        person's own hand-configured entry. Saving it here *is* the accept
        gesture: the person just supplied these connection details themselves,
        so there is nothing left to confirm."""
        mcp = self._mcp()
        if not name:
            raise ApiError(400, "name is required")
        if not isinstance(definition, dict):
            raise ApiError(400, "server is a JSON object")
        mcp.set_server(name, definition)
        mcp.accept(name)
        # Installed from inside this library, so it is on here - and only here:
        # every other library still decides for itself (off until it does).
        mcp.set_library_enabled(name, True)
        mcp.sync()
        return self.mcp_status()

    @mutation_entry("the library MCP setting")
    def mcp_set_library_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        mcp = self._mcp()
        try:
            mcp.set_library_enabled(name, bool(enabled))
        except KeyError:
            raise ApiError(404, f"no server {name!r}") from None
        mcp.sync()
        return self.mcp_status()

    @mutation_entry("the MCP server setting")
    def mcp_set_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        mcp = self._mcp()
        servers = mcp.servers()
        if name not in servers:
            raise ApiError(404, f"no server {name!r}")
        mcp.set_server(name, {**servers[name], "enabled": bool(enabled)})
        mcp.sync()
        return self.mcp_status()

    @mutation_entry("the MCP server removal")
    def mcp_remove_server(self, name: str) -> dict[str, Any]:
        mcp = self._mcp()
        mcp.remove_server(name)
        mcp.sync()
        return self.mcp_status()

    def mcp_registry_search(self, query: str) -> dict[str, Any]:
        return self._mcp().search_registry(query)

    # -- settings pages ------------------------------------------------------
    @mutation_entry("the key update")
    def save_key(self, provider: str, key: str, overwrite: bool = False) -> dict[str, Any]:
        from .keys import SEARCH_KEYS
        if provider not in PRESETS and provider not in SEARCH_KEYS:
            raise ApiError(400, f"unknown provider {provider!r}")
        before = self.keys.status(provider)
        if before.get("saved") and not overwrite:
            label = PROVIDER_LABELS.get(provider, provider.capitalize())
            raise ApiError(409, "a key is already saved", confirm=(
                f"Replace the saved {label} key? The old key is removed and can't be "
                f"recovered from here."))
        try:
            status = self.keys.save(provider, key)
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        except PermissionError as exc:
            raise ApiError(409, str(exc), managed_by="obsidian") from exc
        except OSError as exc:
            raise ApiError(503, f"could not save the key: {exc}") from exc
        return {**status, "check": self.check(provider)}

    @mutation_entry("the key migration")
    def migrate_keys_to_keychain(self, *, confirm: bool = False) -> dict[str, Any]:
        """Perform the person's explicit fallback-key migration request."""
        if not confirm:
            raise ApiError(409, "confirm keychain migration", confirm=(
                "Move all saved fallback-file credentials into this Windows user's credential store? "
                "No credential values will be shown or sent to the browser."))
        try:
            return self.keys.migrate_to_keychain()
        except PermissionError as exc:
            raise ApiError(409, str(exc), managed_by="obsidian") from exc
        except OSError as exc:
            raise ApiError(503, f"could not migrate credentials to the operating-system keychain: {exc}") from exc

    def usage(self, provider: str) -> dict[str, Any]:
        """One best-effort read of account balance/usage, and the provider's
        own dashboard either way. Never raises: a failure here is answered,
        not surfaced as a 500, since it is expected for most providers."""
        dashboard = DASHBOARDS.get(provider, "")
        try:
            made = self._provider_for({"provider": provider})
        except ProviderError as exc:
            return {"ok": False, "error": str(exc), "dashboard": dashboard}
        if made is None:
            return {"ok": False, "error": f"{provider} is not configured", "dashboard": dashboard}
        try:
            data = made.usage()
        except ProviderError as exc:
            return {"ok": False, "error": str(exc), "dashboard": dashboard}
        out: dict[str, Any] = {"ok": True, "dashboard": dashboard, "unofficial": True}
        if provider == "deepinfra" and isinstance(data, dict) and "stripe_balance" in data:
            out.update(balance=data.get("stripe_balance"), currency="USD",
                      suspended=bool(data.get("suspended")),
                      billing_type=str(data.get("billing_type") or ""))
        return out

    def check(self, provider: str) -> dict[str, Any]:
        from .keys import SEARCH_KEYS
        if provider == "github":
            return {"ok": True, "status": "Saved. Repository intake now reads GitHub's API "
                                          "with it (a much higher rate limit)"}
        if provider in SEARCH_KEYS:
            # Not called out to: a test search would spend one of the key's searches.
            from . import websearch
            used = websearch.backend(self.vault)
            return {"ok": True, "status": f"Saved. Web search now uses {used.capitalize()}"
                                          + ("" if used == provider else
                                             " (Brave is used first when both are set)")}
        try:
            made = self._provider_for({"provider": provider})
        except ProviderError as exc:
            return {"ok": False, "error": str(exc)}
        if made is None:
            return {"ok": False, "error": "not configured"}
        return made.check()

    def _model_sources(self) -> dict[tuple[str, str], dict[str, Any]]:
        """Every catalogued model Source, keyed by (provider, model_id), both
        lowercased so a live listing's id matches regardless of case."""
        try:
            rows = self.index_service.run(lambda index: list(index.conn.execute(
                "SELECT path, frontmatter FROM note WHERE shape = 'source' AND kind = 'model'")))
        except Exception:                                   # noqa: BLE001 - no index yet
            return {}
        out: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            fm = json.loads(row["frontmatter"])
            key = (str(fm.get("provider") or "").lower(), str(fm.get("model_id") or "").lower())
            if key[1]:
                out[key] = {**fm, "_path": row["path"]}
        return out

    def _pending_models(self) -> set[tuple[str, str]]:
        """Model ids already queued for a person's review in staging, so the
        tile can say so instead of offering to profile them again."""
        try:
            items = StagingStore(self.vault).items("source")
        except Exception:                                   # noqa: BLE001
            return set()
        return {(str(i.get("fields", {}).get("provider") or "").lower(),
                str(i.get("fields", {}).get("model_id") or "").lower())
                for i in items if i.get("source_kind") == "model" and
                i["status"] in ("staged", "deferred")}

    def models(self, provider: str) -> dict[str, Any]:
        try:
            # A custom host is addressed by its registry id.  Legacy callers
            # still pass a provider preset, so this remains source-compatible
            # with the existing model tile while allowing Settings to discover
            # any OpenAI-compatible personal host.
            try:
                self.hosts.get(provider)
                choice = {"host_id": provider}
            except KeyError:
                choice = {"provider": provider}
            made = self._provider_for(choice)
            listed = made.models() if made is not None else []
        except ProviderError as exc:
            status = "offline" if provider == "local" else \
                "no key" if "is not set" in str(exc) else "error"
            return {"provider": provider, "status": status, "error": str(exc)[:300],
                    "models": []}
        chosen = {(t or {}).get("model"): i + 1
                  for i, t in enumerate(self.settings.data.get("tiers") or [])
                  if (t or {}).get("provider") == provider}
        own = self._model_sources()
        # A profile is knowledge about a model, not about a library (owner, 2026-10-03):
        # this library's own notes, else what any library has profiled (kept in the user's
        # config directory), else the catalogue shipped with the package.
        _remember_profiles(own)
        profiles = {**_shipped_profiles(), **_remembered_profiles(), **own}
        pending = self._pending_models()
        out = []
        for m in listed:
            entry: dict[str, Any] = {"id": m, "tier": chosen.get(m)}
            # Passive adapter evidence for the existing model picker.  This
            # does not run discovery/probes or change a selected model; the
            # current UI may ignore it until its compact status row lands.
            entry["adapter"] = self.invocation_runtime.adapter_summary(made, model_id=m)
            profile = profiles.get((provider, m.lower()))
            if profile:
                entry["profile"] = {
                    "path": profile.get("_path", ""), "modality": profile.get("modality"),
                    "shared": not profile.get("_path"),
                    "best_for": profile.get("best_for") or [],
                    "license_class": profile.get("license_class"),
                    "suggested_tier": profile.get("suggested_tier"),
                    "context_length": profile.get("context_length"),
                    "price_input_per_1m": profile.get("price_input_per_1m"),
                    "price_output_per_1m": profile.get("price_output_per_1m"),
                    # Tri-state (ROUTE-02): an unassessed capability is None, not
                    # False - only an explicit "no" may block a lead placement.
                    "tool_calling": _tri_state(profile.get("tool_calling")),
                    "reasoning": _tri_state(profile.get("reasoning"))}
            elif (provider, m.lower()) in pending:
                entry["profiling"] = "queued"
            out.append(entry)
        return {"provider": provider, "status": "ready", "models": out}

    @staticmethod
    def _host_model_override_scope(tiers: list[dict[str, Any]]) -> str:
        """Bind a route-override choice to these exact normalized routes."""
        canonical = json.dumps(tiers, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return "host-model-override:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]

    def _host_model_override_checkpoint(self, tiers: list[dict[str, Any]], lead: dict[str, Any],
                                        *, checkpoint_id: str = "", reason: str = "") -> dict[str, Any]:
        """Require a durable UI decision before selecting an experimental lead.

        ``override`` was a free-text compatibility parameter in early 2.x.
        Keep it as a direct, person-originated approval path, but record the
        same structured checkpoint as Browser and Obsidian.  An agent cannot
        supply either route selection or a checkpoint id through this method.
        """
        scope = self._host_model_override_scope(tiers)
        if checkpoint_id:
            try:
                row = self.checkpoints.get(checkpoint_id)
            except KeyError as exc:
                raise ApiError(404, str(exc)) from exc
            if row.get("type") == "host_model_override" and row.get("scope") == scope and \
                    row.get("resolution") == "approve" and not row.get("expired"):
                return row
            raise ApiError(409, "approve the matching host/model override checkpoint before selecting this route",
                           checkpoint_record=row, checkpoint="host_model_override")

        create = lambda: self.checkpoints.ensure(
            "host_model_override", scope,
            evidence={"tiers": tiers, "lead": lead,
                      "consequence": "This route is experimental or no longer has current lead evidence. "
                                     "It will not be labelled verified."},
            choices=["approve", "cancel"], default="cancel", requester="person")
        row = self._serialized("host-model-override", create)
        self.hub.publish({"type": "checkpoint_created", "checkpoint": row})
        if reason.strip():
            # A compatibility caller has already made the explicit choice in
            # its own UI/CLI.  Persist that choice as a normal resolution so
            # it is auditable and never a magic bypass.
            if not row.get("resolution"):
                row = self._serialized("host-model-override",
                                       lambda: self.checkpoints.resolve(row["id"], "approve"))
                self.hub.publish({"type": "checkpoint_resolved", "checkpoint": row})
            if row.get("resolution") == "approve":
                return row
        if row.get("resolution") == "approve":
            return row
        raise ApiError(409,
                       f"{lead.get('model') or 'this route'} has not completed the lead qualification suite, "
                       "so it is not known to finish research tasks. Review the route consequences and choose "
                       "Approve only to use it experimentally.",
                       needs_override=True, lead=lead.get("model", ""), checkpoint="host_model_override",
                       checkpoint_record=row)

    def _clean_tiers(self, tiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not isinstance(tiers, list) or len(tiers) > 3:
            raise ApiError(400, "tiers is a list of up to three {provider|host_id, model}")
        clean = []
        for t in tiers:
            if not isinstance(t, dict) or not t.get("model"):
                raise ApiError(400, "each tier needs a provider or host id and a model id")
            host_id = str(t.get("host_id") or "")
            if host_id:
                try:
                    host = self.hosts.get(host_id)
                except KeyError as exc:
                    raise ApiError(400, str(exc)) from exc
                if not host.enabled:
                    raise ApiError(400, f"host {host.display_name!r} is disabled")
                clean.append({"host_id": host.id, "provider": host.id,
                              "model": str(t["model"])})
            elif t.get("provider") in PRESETS:
                provider = str(t["provider"])
                binding = self._binding_for_route("lead", t)
                if binding.host_id != "preset-" + provider:
                    # Discovery still accepts the 2.x provider spelling and
                    # base_urls map. Pin that same endpoint when the person
                    # selects a model; never switch a local listing to the
                    # preset URL merely because canonical bindings now exist.
                    bases = self.settings.data.get("base_urls") or {}
                    base = str(bases.get(provider) or t.get("base_url") or "").strip().rstrip("/")
                    try:
                        host = self.hosts.get(binding.host_id)
                        if not host.enabled:
                            raise ApiError(400, f"host {host.display_name!r} is disabled")
                        if host.base_url.rstrip("/") != base or host.protocol != PRESETS[provider]["protocol"]:
                            raise ApiError(409, "the migrated host endpoint changed; select the explicit host route")
                    except KeyError:
                        self._serialized("legacy-host-selection", lambda: self.hosts.upsert({
                            "id": binding.host_id, "display_name": f"Migrated {provider} route",
                            "protocol": PRESETS[provider]["protocol"], "base_url": base,
                            "auth_ref": PRESETS[provider].get("key_env", "")}))
                    clean.append({"host_id": binding.host_id, "provider": binding.host_id,
                                  "model": str(t["model"])})
                else:
                    clean.append({"provider": provider, "model": str(t["model"])})
            else:
                raise ApiError(400, "each tier needs a known provider or enabled host id and a model id")
        return clean

    @mutation_entry("the tier selection")
    def set_tiers(self, tiers: list[dict[str, Any]], override: str = "",
                  checkpoint_id: str = "") -> dict[str, Any]:
        return self._select_tiers(self._clean_tiers(tiers), override, checkpoint_id)

    def _select_tiers(self, clean: list[dict[str, Any]], override: str,
                      checkpoint_id: str, *, lead_only: bool = False) -> dict[str, Any]:
        # Requirements Addendum R10: benchmark tiers screen; completing tasks (M0) qualifies.
        # A lead that has not is taken only on a person's recorded override.
        lead = self.lead_status(clean)
        changes: dict[str, Any] = {"tiers": clean}
        if lead["status"] == "ineligible":
            self._host_model_override_checkpoint(clean, lead, checkpoint_id=checkpoint_id,
                                                 reason=override)
            overrides = dict(self.settings.data.get("lead_overrides") or {})
            overrides[lead["model"]] = {"reason": (override.strip() or
                                                  "approved via host/model override checkpoint")[:300],
                                       "at": now_iso()}
            changes["lead_overrides"] = overrides

        def persist() -> None:
            if lead_only:
                rows = self.role_routes.raw()
                rows["lead"] = self._revised_binding(
                    rows.get("lead"), self._binding_for_route("lead", clean[0]))
                # A fresh Lead selection also creates the normal inherited
                # defaults if this vault previously had no chat selection.
                for role, binding in self._legacy_chat_bindings(clean[:1]).items():
                    rows.setdefault(role, binding)
            else:
                rows = self._chat_bindings_for_tiers(clean)
            changes["tiers"] = self._tiers_projection(rows, clean)
            self.role_routes.save(rows)
            self.settings.update_in_operation(**changes)

        self._serialized("role-route-settings", persist)
        self.hub.publish({"type": "tiers_changed", "tiers": changes["tiers"]})
        return {"tiers": changes["tiers"], "lead": self.lead_status(changes["tiers"])}

    @mutation_entry("the lead selection")
    def set_lead(self, route: Any, override: str = "", checkpoint_id: str = "") -> dict[str, Any]:
        """Assign position 1 only (ROUTE-01).

        "Use as lead" and the release-lead selection used to send a one-item
        tier list, which silently removed the Scribe and Clerk positions.  The
        stored positions 2-3 pass through the same validation unchanged.
        """
        if not isinstance(route, dict):
            raise ApiError(400, "lead is one {provider|host_id, model}")
        kept = [dict(t) for t in (self.settings.data.get("tiers") or [])[1:3] if isinstance(t, dict)]
        # Validate through the same API boundary, then patch only the Lead
        # binding. Inherited roles retain their references rather than being
        # frozen into copies of the prior route.
        clean = self._clean_tiers([route])[0]
        return self._select_tiers([clean, *kept], override, checkpoint_id, lead_only=True)

    def lead_status(self, tiers: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if tiers is None:
            bound = self._role_choice("lead", validate_host=False)
            if bound is None:
                return {"status": "none"}
            # Retain the compatibility display spelling when it identifies
            # the same bound route; unrelated edits to app.json cannot
            # change what execution or qualification uses.
            selected = (self.settings.data.get("tiers") or [bound])[0]
            same = (self._binding_for_route("lead", selected).host_id == bound["host_id"] and
                    selected.get("model") == bound["model"])
            tiers = [selected if same else bound]
        if not tiers:
            return {"status": "none"}
        route = tiers[0]
        display_host = str(route.get("host_id") or route.get("provider") or "")
        host_id = "preset-" + display_host if display_host in PRESETS and not route.get("host_id") else display_host
        key = f"{display_host}/{route['model']}"
        overrides = self.settings.data.get("lead_overrides") or {}
        override = overrides.get(f"{host_id}/{route['model']}") or overrides.get(key)
        if not override and host_id.startswith("preset-"):
            override = overrides.get(f"{host_id[len('preset-'):]}/{route['model']}")
        model = str(route["model"])
        current = self._qualification_fingerprints(host_id, model, "lead")
        qualification, _ = self._refresh_qualification_route(host_id, model, "lead", current)
        # Local L3 remains valid independently of a bundled release record.
        # A persisted ``verified_release`` marker cannot bypass the manifest
        # and account-probe checks below.
        if qualification is not None and qualification.status == "verified_local" and qualification.fresh():
            return {"status": "eligible", "model": key, "result": qualification.status,
                    "evidence": qualification.evidence_runs,
                    "advisory": qualification.invalidation}
        # Release L3 evidence only applies if this Core/endpoint contract is
        # still compatible and this person's account has a fresh matching L1
        # probe.  A development template, expiry or integrity failure is not
        # a convincing-looking default lead.
        contract = self._release_contract(host_id)
        release_lead, release_reason = release_lead_for_route(host_id, model, contract=contract)
        if release_lead is not None:
            probe = self.qualifications.matching_l1_probe(
                host_id=host_id, model_id=model, role="lead",
                compatibility_fingerprint=current["compatibility"],
                observed_model=str(release_lead.get("model_version") or ""),
            )
            if probe is not None:
                return {"status": "eligible", "model": key, "result": "verified_release",
                        "release_lead": release_lead.get("id"),
                        "evidence": release_lead.get("qualification_artifacts", []),
                        "account_probe": probe.id,
                        "advisory": qualification.invalidation if qualification is not None else ""}
            return {"status": "release_probe_required", "model": key,
                    "result": "verified_release", "release_lead": release_lead.get("id"),
                    "reason": "bundled release evidence is valid; run the matching account L1 probe",
                    "l1_plan": self.qualification_plan(host_id, model, "lead", "L1")}
        if release_reason:
            if override:
                return {"status": "override", "model": key, "release_reason": release_reason, **override}
            return {"status": "ineligible", "model": key, "reason": release_reason,
                    "result": qualification.status if qualification is not None else "experimental",
                    "evidence": qualification.evidence_runs if qualification is not None else []}
        if qualification is not None and qualification.status in ("verified_local", "verified_release"):
            return {"status": "ineligible", "model": key,
                    "reason": "qualification evidence is expired or missing its freshness date",
                    "result": qualification.status, "evidence": qualification.evidence_runs,
                    "advisory": qualification.invalidation}
        listed = {f"{e.get('provider')}/{e.get('model')}": e for e in ELIGIBLE_LEADS()}
        if key in listed:
            return {"status": "eligible", "model": key, "result": listed[key].get("result", "")}
        if override:
            return {"status": "override", "model": key, **override}
        return {"status": "ineligible", "model": key}

    @mutation_entry("the context setting")
    def set_context(self, working_context: str | None = None,
                    reply_length: str | None = None, stance: str | None = None
                    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if working_context is not None:
            changes["working_context"] = str(working_context)[:8000]
        if reply_length is not None:
            if reply_length not in LENGTHS and len(reply_length) > 300:
                raise ApiError(400, "a custom reply length is a short instruction")
            changes["reply_length"] = reply_length
        if stance is not None:
            if stance not in STANCES:
                raise ApiError(400, f"stance is one of {sorted(STANCES)}")
            changes["stance"] = stance
        self.settings.update(**changes)
        return {k: self.settings.data[k] for k in ("working_context", "reply_length", "stance")}

    @mutation_entry("the permission mode")
    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in MODES:
            raise ApiError(400, f"mode is one of {MODES}")
        self.settings.update(mode=mode)
        return self.broker.set_mode(mode)

    def library(self) -> dict[str, Any]:
        config = self.vault.config()
        return {"promotion": config.get("promotion", {}), "usage": config.get("usage", {}),
                "clerk": {k: v for k, v in config.get("clerk", {}).items()
                          if "key" not in k.lower()},
                "search": config.get("search", {}),
                "doctor": [c.to_dict() for c in doctor.checks(self.vault, self.mcp)]}

    # -- service models (Requirements Addendum R17): slots 4-7, kept per library ----
    SERVICE_SLOTS = (("ocr", 4, "OCR", "reads PDF pages that have no text layer"),
                     ("tts", 5, "Text to speech", "reads a note or a reply aloud"),
                     ("embeddings", 6, "Embeddings", "the vectors search uses"),
                     ("stt", 7, "Speech to text", "turns an audio recording into text"))

    def services(self) -> dict[str, Any]:
        from . import ocr
        from .service_adapters import binding as service_binding
        import tomllib
        own: dict[str, Any] = {}
        if self.vault.config_path.is_file():
            with self.vault.config_path.open("rb") as handle:
                own = tomllib.load(handle).get("services") or {}
        chosen = ocr.choice(self.vault)
        slots = []
        for name, number, label, job in self.SERVICE_SLOTS:
            row: dict[str, Any] = {"slot": name, "number": number, "label": label, "job": job}
            if name == "ocr":
                # `default`: still the value a new library starts with (init writes it)
                row.update(chosen or {"provider": "", "model": ""}, built=True,
                           default=own.get("ocr", DEFAULT_CONFIG["services"]["ocr"]) ==
                           DEFAULT_CONFIG["services"]["ocr"])
            elif name == "embeddings":
                row.update(self._embeddings_status(), built=True)
            elif name == "tts":
                from . import tts
                row.update(tts.choice(self.vault) or {"provider": "", "model": ""}, built=True,
                           default=own.get("tts", tts.DEFAULT) == tts.DEFAULT,
                           spent_usd=round(tts.spent(), 4), cap_usd=tts.CAP_USD)
            elif name == "stt":
                from . import stt
                row.update(stt.choice(self.vault) or {"provider": "", "model": ""}, built=True,
                           default=False)
            else:
                row.update(provider="", model="", built=False)       # planned (P4b)
            # Service contracts are independent of agent-chat expectations.
            # This is passive selection evidence only: it never probes,
            # changes a configured model, or upgrades qualification.
            if row.get("model"):
                if name == "embeddings":
                    from . import embed
                    row["adapter"] = embed.adapter_summary(str(row.get("spec") or ""), vault=self.vault)
                else:
                    from .service_routes import resolve as service_route
                    selected = service_route(self.vault, name)
                    row["adapter"] = service_binding(name, selected.contract_provider if selected else "",
                                                     str(row.get("model") or "")).summary()
            binding = self.role_routes.resolve(name)
            row["binding"] = binding.public() if binding is not None else None
            try:
                from .service_routes import resolve as service_route, ServiceRouteError
                selected = service_route(self.vault, name, validate=True)
                row["route_status"] = "selected" if selected else "unconfigured"
            except ServiceRouteError as exc:
                row["route_status"], row["route_error"] = "unavailable", str(exc)
            slots.append(row)
        return {"slots": slots}

    def _embeddings_status(self) -> dict[str, Any]:
        """Slot 6: the model, how much of the library it has embedded, what the rest would
        take, which intents use it, and the last lexical-vs-hybrid measurement."""
        from . import embed
        spec = embed.spec_for(self.vault)
        out: dict[str, Any] = {"provider": "", "model": "", "spec": spec,
                               "vector_intents": self.vault.setting("search", "vector_intents")}
        if not spec:
            return out
        kind, _, rest = spec.partition(":")
        provider, model = (rest.split(":", 1) if kind == "api" else (kind, rest))
        out.update(provider=provider, model=model,
                   legacy=not self.vault.setting("services", "embeddings"))
        name = embed.storage_model(spec)       # as VectorSearch stores it
        price = None
        if kind == "api":
            profile = self._model_sources().get((provider, model.lower())) or {}
            price = profile.get("price_input_per_1m")
        def measure(index: Any) -> dict[str, Any]:
            index.refresh()                               # count what is there now
            representation_ok = embed.representation_current(index, spec)
            return {"chunks": int(index.conn.execute(
                        "SELECT COUNT(DISTINCT hash) FROM chunk WHERE role != 'document'").fetchone()[0]),
                    "embedded": int(index.conn.execute(
                        "SELECT COUNT(*) FROM embedding WHERE model = ?", (name,)).fetchone()[0])
                    if representation_ok else 0,
                    "representation_stale": not representation_ok,
                    "estimate": embed.estimate(index, name, price)}
        out.update(self.index_service.run(measure))
        out["hosted"] = kind == "api"
        compared = self.vault.work("eval") / "vectors.json"
        if compared.is_file():
            try:
                out["comparison"] = json.loads(compared.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return out

    @mutation_entry("the service setting")
    def set_service(self, slot: str, provider: str, model: str, host_id: str = "") -> dict[str, Any]:
        from . import embed
        if slot not in ("ocr", "tts", "stt", "embeddings"):
            raise ApiError(400, f"slot {slot!r} is not built yet")
        host = None
        local_encoder = slot == "embeddings" and provider in embed.LOCAL_KINDS and not host_id
        if model and not local_encoder:
            wanted = host_id or ("preset-" + provider if provider in PRESETS else provider)
            try:
                host = self.hosts.get(wanted)
            except KeyError as exc:
                raise ApiError(400, str(exc)) from exc
            if not host.enabled or host.protocol != "openai":
                raise ApiError(400, "services require an enabled OpenAI-compatible host")
            if slot in ("tts", "stt"):
                if host.id != "preset-deepinfra" or host.base_url.rstrip("/") != PRESETS["deepinfra"]["base_url"]:
                    raise ApiError(400, "native speech services require the reviewed DeepInfra endpoint")
                provider = "deepinfra"
            elif host_id:
                provider = host.id
        selected_host = host.id if host is not None else ""
        if slot == "embeddings":
            # a new model starts with no intents using it: a person turns them on after
            # measuring (SM-8), and nothing is embedded until they start it (R17)
            def set_embeddings() -> dict[str, Any]:
                self._save_service_binding(slot, provider, model, host_id=selected_host)
                self.vault.set_setting("services", "embeddings", f"{provider}:{model}" if model else "")
                self.vault.set_setting("search", "vector_intents", [])
                return self.services()
            return self._serialized("service-settings", set_embeddings)
        if slot == "tts":
            from . import tts
            if model and (provider != "deepinfra" or model not in tts.PRICES):
                raise ApiError(400, f"text to speech runs on DeepInfra with a model whose price "
                                    f"is known, so its ${tts.CAP_USD:.2f} cap holds: "
                                    f"{', '.join(sorted(tts.PRICES))}")
            return self._serialized("service-settings", lambda: (
                self._save_service_binding(slot, provider, model, host_id=selected_host),
                self.vault.set_setting("services", "tts", f"{provider}:{model}" if model else ""),
                self.services())[-1])
        if slot == "stt":
            from . import stt
            if model:
                try:
                    stt.validate_choice(provider, model)
                except stt.SttError as exc:
                    raise ApiError(400, str(exc)) from exc
            return self._serialized("service-settings", lambda: (
                self._save_service_binding(slot, provider, model, host_id=selected_host),
                self.vault.set_setting("services", "stt", f"{provider}:{model}" if model else ""),
                self.services())[-1])
        if slot != "ocr":
            raise ApiError(400, f"slot {slot!r} is not built yet")
        return self._serialized("service-settings", lambda: (
            self._save_service_binding(slot, provider, model, host_id=selected_host),
            self.vault.set_setting("services", "ocr", f"{provider}:{model}" if model else ""),
            self.services())[-1])

    @mutation_entry("the vector-intent setting")
    def set_vector_intents(self, intents: list[str]) -> dict[str, Any]:
        from .search import INTENTS
        unknown = [i for i in intents if i not in INTENTS]
        if unknown:
            raise ApiError(400, f"not search intents: {unknown}")
        return self._serialized("service-settings", lambda: (
            self.vault.set_setting("search", "vector_intents", list(dict.fromkeys(intents))),
            self.services())[1])

    @mutation_entry("the service test")
    def test_service(self, slot: str) -> dict[str, Any]:
        """One small, real call: the OCR model reads a sample line (R17's Test action)."""
        from . import ocr
        if slot == "embeddings":
            return self._test_embeddings()
        if slot == "tts":
            from . import tts
            try:
                out = tts.speak(self.vault, "Testing the read-aloud voice.", "test")
            except tts.TtsError as exc:
                return {"ok": False, "error": str(exc)[:300]}
            return {"ok": True, "read": "Testing the read-aloud voice.", "audio": out["audio"],
                    "cost_usd": out["cost_usd"]}
        if slot == "stt":
            from . import stt
            try:
                return stt.probe(self.vault)
            except stt.SttError as exc:
                return {"ok": False, "error": str(exc)[:300]}
        if slot != "ocr":
            raise ApiError(400, f"slot {slot!r} is not built yet")
        try:
            reader = ocr.endpoint(self.vault)
            if reader is None:
                return {"ok": False, "error": "no OCR model is chosen"}
            got = reader.page_text(ocr.sample_png())
        except (ocr.OcrError, ProviderError) as exc:
            return {"ok": False, "error": str(exc)[:300]}
        return {"ok": "librarian reads this page" in got.lower(), "read": got[:300],
                "model": getattr(reader, "name", "")}

    # -- text to speech (slot 5): a reply (mode A) or the open document (mode B) ------
    @mutation_entry("the read-aloud plan")
    def tts_plan(self, text: str = "", path: str = "") -> dict[str, Any]:
        """Cut a reply, or the note at `path`, into the chunks it will be read in; nothing
        is spoken (or spent) until a chunk is asked for."""
        from . import tts
        if path:
            text, mode = self.read_file(path)["text"], "document"
        else:
            mode = "message"
        if not text.strip():
            raise ApiError(400, "nothing to read")
        chosen = tts.choice(self.vault)
        planned = tts.plan(text, chosen.get("model", ""))
        if not planned["chunks"]:
            raise ApiError(400, "nothing speakable in it")
        plan_id = hashlib.sha256(("\n".join(planned["chunks"]) + mode).encode()
                                 ).hexdigest()[:16]
        self._tts_plans[plan_id] = (mode, planned["chunks"])
        while len(self._tts_plans) > 20:
            self._tts_plans.pop(next(iter(self._tts_plans)))
        return {"plan": plan_id, "mode": mode, "count": len(planned["chunks"]),
                **{k: planned[k] for k in ("chars", "estimate_usd", "spent_usd", "cap_usd")}}

    @mutation_entry("the read-aloud request")
    def tts_chunk(self, plan_id: str, index: int) -> dict[str, Any]:
        from . import tts
        if plan_id not in self._tts_plans:
            raise ApiError(404, "that reading has expired: start it again")
        mode, parts = self._tts_plans[plan_id]
        if not 0 <= index < len(parts):
            raise ApiError(400, f"chunk {index} is not one of 0-{len(parts) - 1}")
        try:
            out = tts.speak(self.vault, parts[index], mode)
        except tts.TtsError as exc:
            raise ApiError(402 if "cap" in str(exc) else 400, str(exc)) from exc
        return {"index": index, "count": len(parts), **out}

    def _test_embeddings(self) -> dict[str, Any]:
        """Slot 6's Test: two close sentences and a far one, embedded - the dimension, and
        whether the close pair is closer than the far one."""
        from . import embed
        spec = embed.spec_for(self.vault)
        if not spec:
            return {"ok": False, "error": "no embedding model is chosen"}
        try:
            import numpy as np
            _, encode, _query_encode, _contract = embed.load_embedding_encoders(spec, vault=self.vault)
            vectors = np.asarray(encode(["a cat sat on the mat", "a kitten sat on a mat",
                                         "quarterly tax filing deadlines"]), dtype="float32")
        except Exception as exc:                            # noqa: BLE001 - key, network, lib
            return {"ok": False, "error": str(exc)[:300]}
        unit = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9)
        near, far = float(unit[0] @ unit[1]), float(unit[0] @ unit[2])
        return {"ok": near > far, "dimension": int(vectors.shape[1]),
                "read": f"close pair {near:.2f}, far pair {far:.2f}", "model": spec}

    # -- project access (Research Pipeline §6): a person's controls, never the model's --
    def projects(self) -> dict[str, Any]:
        from . import projects
        data = projects.state(self.vault)
        for r in data["roots"]:
            r["exists"] = Path(r["path"]).is_dir()
        return data

    @mutation_entry("the project setting")
    def set_projects_enabled(self, on: bool) -> dict[str, Any]:
        from . import projects
        return self._serialized("project-settings", lambda: (
            projects.set_enabled(self.vault, on), self.projects())[1])

    @mutation_entry("the project root update")
    def add_project_root(self, path: str, project: str) -> dict[str, Any]:
        from . import projects
        try:
            return self._serialized("project-settings", lambda: (
                projects.add_root(self.vault, path, project), self.projects())[1])
        except TypeError as exc:
            raise ApiError(400, str(exc)) from exc

    @mutation_entry("the project write setting")
    def set_project_writes(self, root_id: str, allowed: bool) -> dict[str, Any]:
        from . import projects
        try:
            return self._serialized("project-settings", lambda: (
                projects.set_writes(self.vault, root_id, allowed), self.projects())[1])
        except TypeError as exc:
            raise ApiError(404, str(exc)) from exc

    @mutation_entry("the project root removal")
    def remove_project_root(self, root_id: str) -> dict[str, Any]:
        from . import projects
        return self._serialized("project-settings", lambda: (
            projects.remove_root(self.vault, root_id), self.projects())[1])

    @mutation_entry("the project scan")
    def scan_project_root(self, root_id: str) -> dict[str, Any]:
        from . import projects
        entry = next((r for r in projects.state(self.vault)["roots"] if r["id"] == root_id), None)
        if entry is None:
            raise ApiError(404, f"no project root {root_id!r}")
        if not Path(entry["path"]).is_dir():
            raise ApiError(409, f"{entry['path']} has moved or gone: add it again")
        def scan() -> dict[str, Any]:
            out = projects.scan(self.vault, Path(entry["path"]), entry.get("project") or "")
            return {**self.projects(), "scanned": out}
        return self._serialized("project-scan", scan)

    @mutation_entry("the library setting")
    def set_library(self, promotion_mode: str = "",
                    review: dict[str, bool] | None = None) -> dict[str, Any]:
        """Settings -> Library: the promotion mode, and the review gate (§4 G3) on replies
        and on drafted offerings - `review_replies` / `review_offerings` under [clerk]."""
        def apply() -> dict[str, Any]:
            if promotion_mode:
                self.vault.set_setting("promotion", "mode", promotion_mode)
            for key, on in (review or {}).items():
                self.vault.set_setting("clerk", key, bool(on))
            return self.library()
        if promotion_mode:
            if promotion_mode not in ("person", "agent"):
                raise ApiError(400, "promotion mode is 'person' or 'agent'")
        for key, on in (review or {}).items():
            if key not in ("review_replies", "review_offerings"):
                raise ApiError(400, f"no review setting {key!r}")
        return self._serialized("library-settings", apply)

    # -- the document pane: the vault's own notes, read-only ---------------
    def _visible(self, rel: str) -> Path:
        try:
            return self.vault.safe_relative(rel)
        except Refusal as exc:
            raise ApiError(403, exc.detail) from exc

    def list_files(self, rel: str = "") -> dict[str, Any]:
        folder = self._visible(rel)
        if not folder.is_dir():
            raise ApiError(404, f"no folder {rel!r}")
        root = self.vault.root.resolve()
        entries = []
        for child in sorted(folder.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
            if child.name.startswith("."):
                continue
            if child.is_dir():
                entries.append({"name": child.name, "kind": "dir",
                                "path": child.resolve().relative_to(root).as_posix()})
            elif child.suffix.lower() == ".md":
                entries.append({"name": child.stem, "kind": "file",
                                "path": child.resolve().relative_to(root).as_posix()})
            elif child.suffix.lower() in SCRIPT_SUFFIXES:     # opened as code; runnable
                entries.append({"name": child.name, "kind": "file", "script": True,
                                "path": child.resolve().relative_to(root).as_posix()})
        here = folder.relative_to(root).as_posix()
        return {"dir": "" if here == "." else here, "entries": entries}

    def read_file(self, rel: str) -> dict[str, Any]:
        """A note by vault path (with or without `.md`), or by bare name when
        the name is unique enough to find: what a [[link]] in the chat holds."""
        rel = (rel or "").strip()
        if Path(rel).suffix.lower() in SCRIPT_SUFFIXES:
            # A script is shown as code, never rendered - and only a script can be run
            # (the pane's Run button, EXECUTION_SANDBOX_ONLY).
            target = self._visible(rel)
            if not target.is_file():
                raise ApiError(404, f"no file {rel!r}")
            if target.stat().st_size > 2_000_000:
                raise ApiError(413, "that file is too large to show here")
            root = self.vault.root.resolve()
            return {"path": target.resolve().relative_to(root).as_posix(), "name": target.name,
                    "text": read_text(target, encoding="utf-8", errors="replace"),
                    "script": SCRIPT_SUFFIXES[target.suffix.lower()],
                    "modified": round(target.stat().st_mtime)}
        candidates = [rel if rel.lower().endswith(".md") else f"{rel}.md"]
        path = None
        for candidate in candidates:
            target = self._visible(candidate)
            if target.is_file():
                path = target
                break
        if path is None and "/" not in rel:
            wanted = f"{rel}.md".lower() if not rel.lower().endswith(".md") else rel.lower()
            for found in sorted(self.vault.root.rglob("*.md")):
                relative = found.relative_to(self.vault.root)
                if found.name.lower() == wanted and \
                        not any(p.startswith(".") for p in relative.parts):
                    path = found
                    break
        if path is None:
            raise ApiError(404, f"no note {rel!r}")
        if path.stat().st_size > 2_000_000:
            raise ApiError(413, "that note is too large to show here")
        root = self.vault.root.resolve()
        return {"path": path.resolve().relative_to(root).as_posix(), "name": path.stem,
                "text": read_text(path, encoding="utf-8", errors="replace"),
                "modified": round(path.stat().st_mtime)}

    @mutation_entry("the file upload")
    def upload_file(self, dir_rel: str, filename: str, data: bytes) -> dict[str, Any]:
        """The composer's paperclip: a file the person had on their own machine,
        saved into the vault (Inbox/ unless they chose to browse elsewhere) so
        `ingest` can reach it by the same vault-relative path a person dropping
        it in by hand would use."""
        def persist() -> dict[str, Any]:
            folder = self._visible(dir_rel or "Inbox")
            folder.mkdir(parents=True, exist_ok=True)
            name = notes.safe_name(filename) or "attachment"
            target = folder / name
            stem, suffix = target.stem, target.suffix
            n = 1
            while target.exists():
                target = folder / f"{stem} ({n}){suffix}"
                n += 1
            atomic_write_bytes(target, data)
            root = self.vault.root.resolve()
            return {"path": target.resolve().relative_to(root).as_posix(), "name": target.name}
        # Folder paths are visible vault paths, so an active note lease can
        # only block a same-name replacement (we choose a new name).
        return self._serialized("browser-upload", persist)

    def state(self) -> dict[str, Any]:
        data = self.settings.data
        selected_profile: Any | None = None
        try:
            selected_profile = self._active_agent_profile()
        except ApiError:
            # A manually removed selected profile must leave the browser able
            # to repair settings; chat itself still fails closed.
            pass
        return {"version": __version__, "vault": self.vault.root.name,
                "vault_name": self.vault.title, "vault_path": str(self.vault.root),
                "mode": self.broker.mode, "pending": self.broker.pending(),
                "tool_settings": dict(self.broker.settings),
                "busy": self.busy, "tiers": data.get("tiers") or [],
                "role_routes": {role: binding.public() for role, binding in self.role_routes.raw().items()},
                "lead": self.lead_status(),
                "release_leads": self.release_lead_options(),
                "working_context": data["working_context"],
                "reply_length": data["reply_length"], "stance": data["stance"],
                "effort": self._effort_view(),
                "keys": self.keys.all(), "key_backend": self.keys.backend,
                "key_migration_pending": self.keys.migration_pending,
                "secret_source": "obsidian_managed" if self.secret_source == "obsidian" else self.keys.backend,
                "vault_lease": self.coordinator.status() if self.coordinator is not None else {},
                "shutdown": self._shutdown_health(),
                "profiles": self.profiles.all(),
                "agent_profile": str(data.get("agent_profile") or "lead"),
                 "agent_profile_role": getattr(selected_profile, "role", ""),
                 "agent_profile_required_qualification": getattr(
                     selected_profile, "required_qualification", ""),
                "active_profile_runs": self.profile_gate.status(),
                "pending_checkpoints": self.checkpoints.all(pending_only=True),
                "session": self.session_view(),
                "actions": [a.public() for a in self.actions.values()],
                "queued_actions": list(QUEUED), "queued_inputs": self.queued_inputs(),
                "last_event": self.hub.last(), "event_stream": self.hub.cursor()}

    def _effort_view(self) -> dict[str, Any]:
        from . import effort
        return effort.profile(self.settings.data.get("effort"))

    def queued_inputs(self) -> dict[str, dict[str, Any]]:
        """For each one-click action, the inputs a person must give before it
        can start (roadmap §4 D1) - a required input with no default, like
        weekly-review's `project`. The queue popover asks for these first."""
        library = workflows.Library(self.vault)
        out: dict[str, dict[str, Any]] = {}
        for name in QUEUED:
            try:
                inputs = library.get(name).data.get("inputs") or {}
            except workflows.DefinitionError:
                continue
            needed = {key: {"type": (spec or {}).get("type", "string")}
                      for key, spec in inputs.items()
                      if not isinstance(spec, dict) or "default" not in spec}
            if needed:
                out[name] = needed
        return out


# -------------------------------------------------------------------- HTTP

def _asset(name: str) -> bytes | None:
    try:
        path = resources.files("resource_librarian").joinpath("ui", name)
        return path.read_bytes() if path.is_file() else None
    except (FileNotFoundError, ModuleNotFoundError):
        return None


TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "librarian"
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:     # quiet: no request logs
            return

        # -- the boundary ----------------------------------------------------
        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in LOOPBACK

        def _origin_ok(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            own = {f"http://{self.headers.get('Host')}"}
            return origin in own or origin in app.allowed_origins

        def _token_ok(self, query: dict[str, list[str]]) -> bool:
            given = self.headers.get("X-Librarian-Token") or (query.get("token") or [""])[0]
            return secrets.compare_digest(given, app.token)

        def _send(self, status: int, body: bytes, kind: str, extra: dict[str, str] | None = None
                  ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in {**self._cors(), **(extra or {})}.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _cors(self) -> dict[str, str]:
            """Only a host origin (the Obsidian view) is let read across origins;
            a page on any other site gets no CORS headers, so its browser
            refuses it the response."""
            origin = self.headers.get("Origin") or ""
            if origin in app.allowed_origins:
                return {"Access-Control-Allow-Origin": origin, "Vary": "Origin"}
            return {}

        def do_OPTIONS(self) -> None:                       # noqa: N802
            if not self._host_ok() or not self._cors():
                return self._json(403, {"error": "refused"})
            self._send(204, b"", "text/plain", {
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Content-Type, X-Librarian-Token",
                "Access-Control-Max-Age": "600"})

        def _json(self, status: int, payload: Any) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False, default=str)
                       .encode("utf-8"), "application/json; charset=utf-8")

        def _body(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                raise ApiError(413, "request too large")
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError as exc:
                raise ApiError(400, f"invalid JSON: {exc}") from exc
            if not isinstance(data, dict):
                raise ApiError(400, "the body is a JSON object")
            return data

        # -- routes ----------------------------------------------------------
        def do_GET(self) -> None:                           # noqa: N802
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if not self._host_ok():
                return self._json(403, {"error": "refused: not a loopback host"})
            if not url.path.startswith("/api/"):
                return self._static(url.path)
            if not self._token_ok(query):
                return self._json(403, {"error": "refused: missing or stale page token; "
                                                 "reload the page"})
            try:
                if url.path == "/api/events":
                    raw_since = (query.get("since") or ["0"])[0]
                    try:
                        since = int(raw_since or 0)
                    except (TypeError, ValueError) as exc:
                        raise ApiError(400, "since is a non-negative integer") from exc
                    if since < 0:
                        raise ApiError(400, "since is a non-negative integer")
                    return self._events(since, str((query.get("epoch") or [""])[0] or ""))
                if url.path == "/api/meta":
                    return self._json(200, app.meta())
                if url.path == "/api/state":
                    return self._json(200, app.state())
                if url.path == "/api/tools":
                    return self._json(200, {"tools": [
                        {"name": s.name, "purpose": s.card.purpose, "effect": s.effect,
                         "tier": s.tier, "schema": s.json_schema()}
                        for s in sorted(REGISTRY.for_tier("curate"), key=lambda s: s.name)]})
                if url.path == "/api/models":
                    return self._json(200, app.models((query.get("provider") or [""])[0]))
                if url.path == "/api/hosts":
                    return self._json(200, app.host_list())
                if url.path == "/api/routes/readiness":
                    return self._json(200, app.route_readiness(
                        (query.get("profile") or [""])[0], (query.get("session") or [""])[0]))
                if url.path == "/api/hosts/key":
                    return self._json(200, app.host_key_status((query.get("host_id") or [""])[0]))
                if url.path == "/api/qualification":
                    return self._json(200, app.qualification_status(
                        (query.get("host_id") or [""])[0], (query.get("model") or [""])[0],
                        (query.get("role") or ["lead"])[0]))
                if url.path == "/api/qualification/plan":
                    return self._json(200, app.qualification_plan(
                        (query.get("host_id") or [""])[0], (query.get("model") or [""])[0],
                        (query.get("role") or ["lead"])[0], (query.get("level") or ["L1"])[0]))
                if url.path == "/api/qualification/jobs":
                    return self._json(200, app.qualification_jobs(
                        (query.get("host_id") or [""])[0], (query.get("model") or [""])[0],
                        (query.get("role") or [""])[0]))
                if url.path == "/api/release-leads":
                    return self._json(200, app.release_lead_options())
                if url.path == "/api/profiles":
                    return self._json(200, app.profile_list())
                if url.path == "/api/profiles/history":
                    return self._json(200, app.profile_history((query.get("id") or [""])[0]))
                if url.path == "/api/packs":
                    return self._json(200, app.packs())
                if url.path == "/api/checkpoints":
                    return self._json(200, app.checkpoint_list(
                        bool((query.get("pending") or [""])[0])))
                if url.path == "/api/documents":
                    return self._json(200, app.documents())
                if url.path == "/api/library":
                    return self._json(200, app.library())
                if url.path == "/api/services":
                    return self._json(200, app.services())
                if url.path == "/api/projects":
                    return self._json(200, app.projects())
                if url.path == "/api/offerings/staged":
                    from .tools.sessions import staged_offering, staged_offerings
                    wanted = (query.get("id") or [""])[0]
                    if wanted:
                        try:
                            return self._json(200, staged_offering(app.vault, wanted))
                        except TypeError as exc:
                            raise ApiError(404, str(exc)) from exc
                    return self._json(200, {"offerings": staged_offerings(app.vault)})
                if url.path == "/api/claims/runs":
                    from . import claim_run
                    return self._json(200, {"runs": claim_run.RunnableStore(app.vault).list(),
                                            "docker": claim_run.docker_status()[1]})
                if url.path == "/api/libraries":
                    from . import libraries
                    return self._json(200, {"libraries": libraries.known(app.vault),
                                            "current": str(app.vault.root)})
                if url.path == "/api/files":
                    return self._json(200, app.list_files((query.get("dir") or [""])[0]))
                if url.path == "/api/file":
                    return self._json(200, app.read_file((query.get("path") or [""])[0]))
                if url.path == "/api/usage":
                    return self._json(200, app.usage((query.get("provider") or [""])[0]))
                if url.path == "/api/keys":
                    return self._json(200, {"keys": app.keys.all(),
                                            "backend": app.keys.backend})
                if url.path == "/api/mcp":
                    return self._json(200, app.mcp_status())
                if url.path == "/api/mcp/registry":
                    return self._json(200, app.mcp_registry_search(
                        (query.get("q") or [""])[0]))
                return self._json(404, {"error": f"no route {url.path}"})
            except ApiError as exc:
                return self._json(exc.status, exc.body)

        def do_POST(self) -> None:                          # noqa: N802
            url = urlparse(self.path)
            if not self._host_ok():
                return self._json(403, {"error": "refused: not a loopback host"})
            if not self._origin_ok():
                return self._json(403, {"error": "refused: a page on another origin"})
            if not self._token_ok(parse_qs(url.query)):
                return self._json(403, {"error": "refused: missing or stale page token; "
                                                 "reload the page"})
            try:
                if url.path == "/api/attach":
                    with app._counted_mutation(f"the HTTP mutation {url.path!r}"):
                        return self._attach(parse_qs(url.query))
                body = self._body()
                # Every HTTP POST is a potentially state-changing control
                # surface.  This outer admission/count closes the gaps left
                # by legacy handlers which mutate broker/key/MCP state
                # directly rather than through an App helper.
                with app._counted_mutation(f"the HTTP mutation {url.path!r}"):
                    return self._json(200, self._post(url.path, body))
            except ApiError as exc:
                return self._json(exc.status, exc.body)
            except Exception as exc:                        # noqa: BLE001
                return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

        def _attach(self, query: dict[str, list[str]]) -> None:
            """Raw bytes, not JSON: a file from the composer's paperclip is too
            large, and the wrong shape, for `_body()`'s JSON cap."""
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0:
                raise ApiError(400, "no file was sent")
            if length > MAX_UPLOAD:
                raise ApiError(413, f"that file is over the attachment limit "
                                    f"({MAX_UPLOAD // 1_000_000}MB); place it in the vault's "
                                    f"Inbox/ folder directly instead")
            data = self.rfile.read(length)
            name = (query.get("name") or [""])[0]
            if not name:
                raise ApiError(400, "name is required")
            folder = (query.get("dir") or ["Inbox"])[0]
            return self._json(200, app.upload_file(folder, name, data))

        def _post(self, path: str, body: dict[str, Any]) -> Any:
            if path == "/api/host/stop":
                out = app.request_host_stop(force=bool(body.get("force")))
                # Send the confirmation before stopping the serving thread;
                # HostManager then waits for the process to disappear instead
                # of relying on client reference counts or a console window.
                threading.Thread(target=self.server.shutdown, daemon=True,
                                 name="librarian-host-stop").start()
                return out
            if path == "/api/chat":
                return app.chat(str(body.get("text") or ""))
            if path == "/api/chat/cancel":
                return app.cancel_turn()
            if path == "/api/chat/reset":
                return app.reset()
            if path == "/api/chat/attach":
                return app.attach(str(body.get("session_id") or ""))
            if path.startswith("/api/tool/"):
                name = path[len("/api/tool/"):]
                arguments = body.get("arguments") or {}
                if not isinstance(arguments, dict):
                    raise ApiError(400, "arguments is a JSON object")
                return app.person_call(name, arguments, str(body.get("session") or ""))
            if path == "/api/mode":
                return app.set_mode(str(body.get("mode") or ""))
            if path == "/api/permission":
                answer = str(body.get("answer") or "")
                if answer not in ANSWERS:
                    raise ApiError(400, f"answer is one of {ANSWERS}")
                try:
                    return app.broker.answer(str(body.get("id") or ""), answer)
                except LookupError as exc:
                    raise ApiError(404, str(exc)) from exc
            if path == "/api/tool-setting":
                try:
                    app.broker.set_tool(str(body.get("tool") or ""),
                                        str(body.get("setting") or ""))
                except ValueError as exc:
                    raise ApiError(400, str(exc)) from exc
                return {"tool_settings": dict(app.broker.settings)}
            if path == "/api/keys":
                return app.save_key(str(body.get("provider") or ""), str(body.get("key") or ""),
                                    bool(body.get("overwrite")))
            if path == "/api/keys/remove":
                if not body.get("confirm"):
                    raise ApiError(409, "confirm removal", confirm=(
                        "Remove the saved key? It can't be recovered from here."))
                try:
                    return app.keys.remove(str(body.get("provider") or ""))
                except PermissionError as exc:
                    raise ApiError(409, str(exc), managed_by="obsidian") from exc
                except OSError as exc:
                    raise ApiError(503, f"could not update key storage: {exc}") from exc
            if path == "/api/keys/migrate":
                return app.migrate_keys_to_keychain(confirm=bool(body.get("confirm")))
            if path == "/api/keys/check":
                return app.check(str(body.get("provider") or ""))
            if path == "/api/hosts":
                return app.host_upsert(body.get("host"))
            if path == "/api/hosts/controls":
                return app.host_update_controls(body)
            if path == "/api/hosts/remove":
                return app.host_remove(str(body.get("host_id") or ""))
            if path == "/api/hosts/key":
                return app.host_save_key(str(body.get("host_id") or ""), str(body.get("key") or ""),
                                         bool(body.get("overwrite")))
            if path == "/api/hosts/test":
                return app.host_test(str(body.get("host_id") or ""), str(body.get("model") or ""))
            if path == "/api/release-leads/select":
                return app.select_release_lead(str(body.get("id") or ""), key=str(body.get("key") or ""),
                                               overwrite=bool(body.get("overwrite")),
                                               checkpoint_id=str(body.get("checkpoint_id") or ""))
            if path == "/api/qualification/run":
                return app.run_qualification(str(body.get("host_id") or ""), str(body.get("model") or ""),
                                             str(body.get("role") or "lead"), str(body.get("level") or "L0"),
                                             bool(body.get("confirm_spend")),
                                             str(body.get("scenario") or "default"),
                                             str(body.get("checkpoint_id") or ""))
            if path == "/api/qualification/jobs/pause":
                return app.pause_qualification_job(str(body.get("id") or ""),
                                                   str(body.get("reason") or ""))
            if path == "/api/qualification/jobs/resume":
                return app.resume_qualification_job(str(body.get("id") or ""))
            if path == "/api/qualification/jobs/cancel":
                return app.cancel_qualification_job(str(body.get("id") or ""),
                                                    str(body.get("reason") or ""))
            if path == "/api/qualification/jobs/result":
                try:
                    duration_ms = int(body.get("duration_ms") or 0)
                    cost_usd = float(body.get("cost_usd") or 0.0)
                except (TypeError, ValueError) as exc:
                    raise ApiError(400, "duration_ms and cost_usd must be numbers") from exc
                return app.record_qualification_job_result(
                    str(body.get("id") or ""), outcome=str(body.get("outcome") or ""),
                    artifact=str(body.get("artifact") or ""), detail=str(body.get("detail") or ""),
                    duration_ms=duration_ms, cost_usd=cost_usd)
            if path == "/api/profiles":
                return app.profile_save(body.get("profile"))
            if path == "/api/agent-profile":
                return app.set_agent_profile(str(body.get("id") or ""))
            if path == "/api/checkpoints":
                return app.checkpoint_create(str(body.get("type") or ""), str(body.get("scope") or ""),
                                             body.get("evidence"), body.get("choices"),
                                             str(body.get("requester") or "person"))
            if path == "/api/checkpoints/resolve":
                return app.checkpoint_resolve(str(body.get("id") or ""), str(body.get("choice") or ""))
            if path == "/api/documents/heartbeat":
                return app.document_heartbeat(str(body.get("path") or ""),
                                              editor=str(body.get("editor") or "Obsidian"),
                                              dirty=bool(body.get("dirty", True)),
                                              baseline=str(body.get("baseline") or ""))
            if path == "/api/documents/release":
                return app.document_release(str(body.get("path") or ""),
                                            editor=str(body.get("editor") or ""))
            if path == "/api/documents/changed":
                return app.document_changed(str(body.get("path") or ""))
            if path == "/api/mcp/config":
                return app.mcp_save_config(body.get("mcpServers"))
            if path == "/api/mcp/accept":
                return app.mcp_accept(str(body.get("name") or ""))
            if path == "/api/mcp/server":
                return app.mcp_add_server(str(body.get("name") or ""), body.get("server"))
            if path == "/api/mcp/library":
                return app.mcp_set_library_enabled(str(body.get("name") or ""),
                                                   bool(body.get("enabled")))
            if path == "/api/mcp/enable":
                return app.mcp_set_enabled(str(body.get("name") or ""), bool(body.get("enabled")))
            if path == "/api/mcp/remove":
                return app.mcp_remove_server(str(body.get("name") or ""))
            if path == "/api/tiers":
                return app.set_tiers(body.get("tiers") or [], str(body.get("override") or ""),
                                     str(body.get("checkpoint_id") or ""))
            if path == "/api/mcp/call":
                # The MCP server's only way into this vault (CORE-04A).  It
                # authenticates with the owner-only connection record's token.
                return app.mcp_call(str(body.get("tool") or ""), body.get("arguments") or {},
                                    str(body.get("session") or ""), str(body.get("tier") or "consult"))
            if path == "/api/lead":
                return app.set_lead(body.get("route"), str(body.get("override") or ""),
                                    str(body.get("checkpoint_id") or ""))
            if path == "/api/sandbox/run_file":
                # A person's "Run this script" (EXECUTION_SANDBOX_ONLY): their own call
                return app.person_call("sandbox_run_file", {"path": str(body.get("path") or "")})
            if path == "/api/tts/plan":
                return app.tts_plan(str(body.get("text") or ""), str(body.get("path") or ""))
            if path == "/api/tts/chunk":
                return app.tts_chunk(str(body.get("plan") or ""), int(body.get("index") or 0))
            if path == "/api/effort":
                return app.set_effort(body.get("level"))
            if path == "/api/context":
                return app.set_context(body.get("working_context"), body.get("reply_length"),
                                       body.get("stance"))
            if path == "/api/library":
                review = body.get("review")
                return app.set_library(str(body.get("promotion_mode") or ""),
                                       review if isinstance(review, dict) else None)
            if path == "/api/services":
                return app.set_service(str(body.get("slot") or ""), str(body.get("provider") or ""),
                                       str(body.get("model") or ""), str(body.get("host_id") or ""))
            if path == "/api/services/test":
                return app.test_service(str(body.get("slot") or ""))
            if path == "/api/projects/enable":
                return app.set_projects_enabled(bool(body.get("enabled")))
            if path == "/api/projects/add":
                return app.add_project_root(str(body.get("path") or ""),
                                            str(body.get("project") or ""))
            if path == "/api/offerings/decide":
                # The person's Promote / Decline on a staged offering (Staging -> Offerings)
                return app.decide_offering(str(body.get("id") or ""),
                                           str(body.get("decision") or ""))
            if path == "/api/claims/run":
                # A person's "Run it" (EXECUTION_SANDBOX_ONLY): the curate-tier tool, through
                # the person's own call - never the model's
                return app.person_call("run_claim_input", {"run_id": str(body.get("id") or "")})
            if path == "/api/projects/writes":
                return app.set_project_writes(str(body.get("id") or ""), bool(body.get("allowed")))
            if path == "/api/projects/remove":
                return app.remove_project_root(str(body.get("id") or ""))
            if path == "/api/projects/scan":
                return app.scan_project_root(str(body.get("id") or ""))
            if path == "/api/services/vector_intents":
                return app.set_vector_intents([str(i) for i in body.get("intents") or []])
            if path == "/api/library/switch":
                return self.server.board.switch(str(body.get("path") or ""),  # type: ignore[attr-defined]
                                                force=bool(body.get("force")))
            if path == "/api/libraries/forget":
                from . import libraries
                return {"forgotten": libraries.forget(str(body.get("path") or ""))}
            if path == "/api/actions":
                try:
                    return app.start_action(str(body.get("name") or ""), body.get("inputs"))
                except workflows.DefinitionError as exc:
                    raise ApiError(404, str(exc)) from exc
            if path.startswith("/api/actions/") and path.endswith("/cancel"):
                return app.cancel_action(path.split("/")[3])
            raise ApiError(404, f"no route {path}")

        def _static(self, path: str) -> None:
            name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
            if "/" in name or name.startswith("."):
                return self._json(404, {"error": "not found"})
            data = _asset(name)
            if data is None:
                if name == "index.html":
                    data = (b"<!doctype html><title>Librarian</title><p>The interface is not "
                            b"built in this install. The API is running.</p>")
                else:
                    return self._json(404, {"error": "not found"})
            if name == "index.html":
                data = data.replace(b"__LIBRARIAN_TOKEN__", app.token.encode())
            kind = TYPES.get(Path(name).suffix, "application/octet-stream")
            self._send(200, data, kind, {
                # media-src: read-aloud audio arrives as data: URIs; without it the policy
                # fell back to 'self' and every clip was refused unplayed (2026-10-03)
                "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; "
                                           "media-src 'self' data: blob:; "
                                           "style-src 'self' 'unsafe-inline'; "
                                           "frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer"})

        def _events(self, since: int, epoch: str = "") -> None:
            waiting: deque[dict[str, Any]] = deque()
            ready = threading.Event()

            def listener(event: dict[str, Any]) -> None:
                waiting.append(event)
                ready.set()
            # Subscribe before taking the replay snapshot. A concurrent event
            # can appear in both queues, but the sequence-aware browser safely
            # de-duplicates it; taking the snapshot first could lose it.
            stop = app.hub.subscribe(listener)
            replay, resync = app.hub.resume(since, epoch)
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            for k, v in self._cors().items():
                self.send_header(k, v)
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            try:
                if resync is not None:
                    self._event(resync)
                for event in replay:
                    self._event(event)
                while not self.server.closing:                  # type: ignore[attr-defined]
                    if not ready.wait(15):
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                        continue
                    ready.clear()
                    while waiting:
                        self._event(waiting.popleft())
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                stop()
                self.close_connection = True

        def _event(self, event: dict[str, Any]) -> None:
            data = json.dumps(event, ensure_ascii=False, default=str)
            self.wfile.write(f"id: {event['seq']}\nevent: {event['type']}\n"
                             f"data: {data}\n\n".encode("utf-8"))
            self.wfile.flush()

    return Handler


class Switchboard:
    """Which library the running server serves, and switching it in place -
    the same port and token, like switching vaults in Obsidian. The new
    library is loaded first, then swapped in atomically; the one it replaces
    retires in the background (`App.retire`) rather than being cut off."""

    def __init__(self, app: App):
        self.app = app
        self._lock = threading.Lock()
        self.retiring: list[App] = []

    def switch(self, path: str, force: bool = False) -> dict[str, Any]:
        from . import libraries
        try:
            vault = libraries.resolve(path)
        except ValueError as exc:
            raise ApiError(400, str(exc)) from exc
        with self._lock:
            old = self.app
            if vault.root == old.vault.root:
                return {"switched": False, "vault": vault.title, "reason": "already open"}
            running = old.running()
            if running and not force:
                raise ApiError(409, f"{old.vault.title} still has work in progress; "
                                    f"switch anyway and let it finish in the background?",
                               running=running)
            own = getattr(old._provider_for, "__self__", None) is old
            new = App(vault, token=old.token, keys=old.keys,
                      provider_for=None if own else old._provider_for,
                      allowed_origins=old.allowed_origins,
                      broker_timeout=old.broker_timeout, mcp=old.mcp,
                      coordinate=old.coordinated, secret_source=old.secret_source)
            self.app = new
        libraries.remember(old.vault)          # so it can always be switched back to
        libraries.remember(vault)
        old.hub.publish({"type": "library_switched", "to": vault.title})
        self.retiring.append(old)

        def retire() -> None:
            old.retire()
            self.retiring.remove(old)
        threading.Thread(target=retire, daemon=True, name="library-retire").start()
        return {"switched": True, "vault": vault.title, "from": old.vault.title,
                "finishing_in_background": running}


class _Current:
    """The handler's view of `App`: every attribute read goes to whichever
    library the switchboard holds right now."""

    def __init__(self, board: Switchboard):
        object.__setattr__(self, "_board", board)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._board.app, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._board.app, name, value)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    closing = False
    board: Switchboard

    def shutdown(self) -> None:
        self.closing = True
        super().shutdown()


def build(app: App, port: int = 0) -> Server:
    board = Switchboard(app)
    server = Server(("127.0.0.1", port), make_handler(_Current(board)))  # type: ignore[arg-type]
    server.board = board
    return server


def serve(vault_path: str | None, port: int = 8323, token: str = "",
          open_browser: bool = False, *, takeover: bool = False) -> int:
    import os
    try:
        vault = Vault.find(vault_path or os.environ.get("LIBRARIAN_VAULT") or None)
    except Refusal:
        from .library_picker import serve_picker
        return serve_picker(port, open_browser)
    try:
        app = App(vault, token=token or os.environ.get("LIBRARIAN_TOKEN", ""), coordinate=True,
                  takeover=takeover or os.environ.get("LIBRARIAN_VAULT_TAKEOVER") == "1",
                  secret_source="obsidian" if os.environ.get("LIBRARIAN_SECRET_SOURCE") == "obsidian"
                  else "desktop",
                  host_managed=os.environ.get("LIBRARIAN_HOST_MANAGED") == "1")
    except StaleLeaseError as exc:
        print(json.dumps({"error": "stale_vault_lease", "detail": str(exc),
                          "takeover": "rerun Librarian app with --takeover after checking the old Core"}),
              flush=True)
        return 2
    except LeaseHeldError as exc:
        print(json.dumps({"error": "vault_in_use", "detail": str(exc)}), flush=True)
        return 2
    from . import libraries
    try:
        libraries.remember(vault)
    except OSError:
        pass                                  # a read-only config dir never stops the app
    server = build(app, port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    # This is separate from the vault lease: the lease remains diagnostic
    # metadata only.  The owner-only record lets Obsidian/Cowork attach to an
    # already-running Core instead of attempting a second mutable Core for
    # the same vault.  If private storage is unavailable, normal startup is
    # still safe; adapters simply get the ordinary lease-held response.
    from . import process_identity
    connection.publish(vault.root, url=url, token=app.token, pid=os.getpid(),
                       process_start=process_identity.process_start(os.getpid()),
                       protocol_version=PROTOCOL_VERSION, secret_source=app.secret_source)
    # The host that started the core reads this line to find the port.
    started = {"listening": url, "vault": str(vault.root)}
    print(json.dumps(started), flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.closing = True
        server.server_close()
        if server.board.app.mcp is not None:
            server.board.app.mcp.stop()
        for closing_app in [server.board.app, *server.board.retiring]:
            closing_app.close_runtime()
        connection.remove(vault.root, pid=os.getpid(), token=app.token)
    return 0
