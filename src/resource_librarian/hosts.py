"""Personal model-host configuration and observed qualification evidence.

Host records intentionally contain no secret.  They are stored in the
person's Librarian configuration directory so a vault can reference an agent
profile without leaking an endpoint or key to collaborators.  Qualification is
separate from provider catalogue claims: a route is useful only when its own
versioned evidence says so.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, TypeVar

from .coordination import atomic_write_text
from .keys import config_dir
from .providers import PRESETS
from .providers import Provider, ProviderCancelledError, ProviderError, Reply, ToolDef
from .vault import now_iso
from urllib.parse import urlparse

HOST_PROTOCOLS = ("openai", "anthropic")
QUALIFICATION_STATES = ("unavailable", "experimental", "screened", "verified_local",
                        "verified_release")
EVALUATION_LEVELS = ("L0", "L1", "L2", "L3")
L2_REQUIRED_RUNS = 3
L3_REQUIRED_RUNS = 5
FRESHNESS_DAYS = 90
EVALUATION_JOB_STATES = ("queued", "running", "paused", "cancelled", "completed", "stale")
# These are deliberately independent of package SemVer.  A release lead may
# be reused across a patch release only while the tool/prompt contract it was
# evaluated against remains compatible.  Bump the relevant value when its
# contract changes, then release CI supplies fresh L3 evidence.
# L1 used to accept a matching tool name alone.  Version 3 covers the strict
# one-call/arguments/model-identity probe below, so a release record made
# against the old weaker contract cannot be mistaken for current evidence.
RELEASE_TOOL_CONTRACT_VERSION = "3"
RELEASE_PROMPT_CONTRACT_VERSION = "2"
RELEASE_LEAD_SCHEMA_VERSION = 2
RELEASE_LEAD_MANIFEST_STABLE_STATUS = "stable"
# This is deliberately distinct from the release manifest version: custom and
# local routes also need an unambiguous record of what their paid L1 proved.
L1_PROBE_CONTRACT_VERSION = "3"   # 3: the tool continuation step (ADAPT-07)
T = TypeVar("T")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str)


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24]


def _as_time(value: Any) -> datetime | None:
    """Parse an ISO timestamp as an aware UTC time without trusting locale."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _semver(value: str) -> tuple[int, int, int] | None:
    # Core development builds use PEP 440's ``.devN`` suffix while release
    # manifests use SemVer-like comparison ranges.  Treat a recognised
    # prerelease suffix as the same compatibility tuple, but reject arbitrary
    # trailing text rather than accidentally accepting an unrelated version.
    match = re.fullmatch(
        r"v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:(?:[-+].*)|(?:\.(?:dev|post|rc)\d*))?",
        value.strip(),
    )
    if match is None:
        return None
    return tuple(int(part or 0) for part in match.groups())  # type: ignore[return-value]


def _in_version_range(current: str, requirement: str) -> bool:
    """Small, intentionally conservative SemVer-range evaluator.

    Release records use comma-separated comparison clauses (for example
    ``>=2.1.0,<2.2.0``).  Unknown syntax fails closed rather than treating a
    new Core as compatible with evidence it has not actually run.
    """
    version = _semver(current)
    if version is None or not isinstance(requirement, str) or not requirement.strip():
        return False
    for clause in requirement.split(","):
        match = re.fullmatch(r"\s*(>=|<=|==|=|>|<)?\s*(v?\d+(?:\.\d+){0,2}(?:[-+].*)?)\s*", clause)
        if match is None:
            return False
        operator, wanted_text = match.groups()
        wanted = _semver(wanted_text)
        if wanted is None:
            return False
        operator = operator or "="
        if not {"=": version == wanted, "==": version == wanted,
                ">": version > wanted, ">=": version >= wanted,
                "<": version < wanted, "<=": version <= wanted}[operator]:
            return False
    return True


@dataclass
class Host:
    id: str
    display_name: str
    protocol: str
    base_url: str = ""
    auth_ref: str = ""
    enabled: bool = True
    timeout: int = 120
    concurrency_limit: int = 1
    rate_limit: int = 0
    discovery_at: str = ""
    endpoint_fingerprint: str = ""
    health: dict[str, Any] = field(default_factory=dict)
    health_history: list[dict[str, Any]] = field(default_factory=list)
    seeded: bool = False

    @property
    def local(self) -> bool:
        """Whether this host's endpoint runs on this machine.

        A local endpoint (LM Studio, Ollama...) shares CPU/IO with the Core
        itself, so background work must yield to interactive turns; a remote
        provider has no such contention.  Never raise: a malformed URL just
        means "not local", which keeps routing decisions total.
        """
        try:
            host = (urlparse(self.base_url).hostname or "").strip("[]").lower()
        except ValueError:
            return False
        return (host in ("localhost", "127.0.0.1", "::1")
                or host.endswith(".localhost")
                or host.endswith(".local"))

    def normalise(self) -> "Host":
        self.id = self.id.strip().lower().replace(" ", "-")[:80]
        self.display_name = self.display_name.strip()[:120] or self.id
        self.protocol = self.protocol.strip().lower()
        self.base_url = self.base_url.strip().rstrip("/")
        self.auth_ref = self.auth_ref.strip()[:120]
        self.timeout = max(1, min(int(self.timeout or 120), 3600))
        self.concurrency_limit = max(1, min(int(self.concurrency_limit or 1), 32))
        self.rate_limit = max(0, min(int(self.rate_limit or 0), 100_000))
        if not isinstance(self.health, dict):
            self.health = {}
        history = self.health_history if isinstance(self.health_history, list) else []
        self.health_history = [{
            "status": str(row.get("status") or "unknown")[:40],
            "detail": str(row.get("detail") or "")[:300],
            "model": str(row.get("model") or "")[:200],
            "checked_at": str(row.get("checked_at") or "")[:64],
        } for row in history if isinstance(row, dict)][-20:]
        if self.protocol not in HOST_PROTOCOLS:
            raise ValueError(f"host protocol is one of {HOST_PROTOCOLS}")
        if not self.id:
            raise ValueError("host id is required")
        if self.protocol == "openai" and not self.base_url:
            raise ValueError("an OpenAI-compatible host needs a base URL")
        self.endpoint_fingerprint = endpoint_fingerprint(self)
        return self

    def public(self) -> dict[str, Any]:
        row = asdict(self)
        # ``auth_ref`` is the name/alias of a credential source, never a
        # credential value.  It must remain visible so a person can bind a
        # custom host without a vault ever storing the key itself.
        row["needs_key"] = bool(self.auth_ref)
        return row


class HostFullRecordError(ValueError):
    """A caller used the full-upsert endpoint as if it were PATCH.

    The browser has always sent a complete public Host object.  Giving this
    case its own error lets adapters move small controls to the dedicated
    endpoint without surfacing a dataclass ``TypeError`` or HTTP 500.
    """

    def __init__(self, missing_fields: list[str]) -> None:
        self.missing_fields = list(missing_fields)
        super().__init__("host_requires_full_record: missing " + ", ".join(self.missing_fields))


def endpoint_fingerprint(host: Host | dict[str, Any]) -> str:
    row = asdict(host) if isinstance(host, Host) else host
    return digest({"protocol": row.get("protocol", ""),
                   "base_url": str(row.get("base_url", "")).rstrip("/"),
                   "auth_ref": row.get("auth_ref", "")})


def seeded_hosts() -> list[Host]:
    out: list[Host] = []
    for provider, preset in PRESETS.items():
        protocol = str(preset.get("protocol") or "openai")
        if protocol not in HOST_PROTOCOLS:
            continue
        base = str(preset.get("base_url") or "")
        # OpenAI's official endpoint is implied by the provider adapter.
        if provider == "openai" and not base:
            base = "https://api.openai.com/v1"
        out.append(Host(id=f"preset-{provider}", display_name=provider.capitalize(),
                        protocol=protocol, base_url=base,
                        auth_ref=str(preset.get("key_env") or ""), seeded=True).normalise())
    return out


class HostRegistry:
    """Global, non-secret host data with immutable seeded defaults."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_dir() / "hosts.json"
        self._hosts = self._load()

    def _load(self) -> dict[str, Host]:
        rows: list[dict[str, Any]] = []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            rows = payload.get("hosts", []) if isinstance(payload, dict) else []
        except (OSError, ValueError):
            pass
        out = {h.id: h for h in seeded_hosts()}
        for row in rows:
            if not isinstance(row, dict):
                continue
            try:
                host = Host(**{k: v for k, v in row.items() if k in Host.__dataclass_fields__}).normalise()
            except (TypeError, ValueError):
                continue
            # A saved record may configure a seed, but cannot change identity/type.
            if host.id in out and out[host.id].seeded:
                base = out[host.id]
                base.enabled = host.enabled
                base.timeout = host.timeout
                base.concurrency_limit = host.concurrency_limit
                base.rate_limit = host.rate_limit
                base.health = host.health
                base.health_history = host.health_history
            else:
                out[host.id] = host
        return out

    def _save(self) -> None:
        rows = [asdict(h) for h in self._hosts.values() if not h.seeded or h.health or h.health_history or not h.enabled or
                h.timeout != 120 or h.concurrency_limit != 1 or h.rate_limit != 0]
        atomic_write_text(self.path, json.dumps({"schema_version": 1, "hosts": rows}, indent=2,
                                                 ensure_ascii=False) + "\n")

    def all(self) -> list[dict[str, Any]]:
        return [h.public() for h in sorted(self._hosts.values(), key=lambda x: (not x.seeded, x.id))]

    def get(self, host_id: str) -> Host:
        try:
            return self._hosts[host_id]
        except KeyError as exc:
            raise KeyError(f"no host {host_id!r}") from exc

    def upsert(self, row: dict[str, Any]) -> dict[str, Any]:
        """Replace a Host record; small control changes use ``update_controls``.

        Keep this as a full-upsert operation for the existing browser and
        2.x callers.  Validate identity fields *before* constructing the
        dataclass so a PATCH-shaped body produces a stable, actionable error.
        """
        if not isinstance(row, dict):
            raise TypeError("host is an object")
        required = ("id", "display_name", "protocol")
        missing = [key for key in required
                   if not isinstance(row.get(key), str) or not str(row.get(key) or "").strip()]
        if missing:
            raise HostFullRecordError(missing)
        candidate = Host(**{k: v for k, v in row.items() if k in Host.__dataclass_fields__})
        candidate.id = candidate.id.strip().lower().replace(" ", "-")[:80]
        previous = self._hosts.get(candidate.id)
        if previous is not None and previous.seeded:
            # The browser receives a public host record.  An omitted
            # credential reference must not look like an attempt to erase the
            # seed's binding, while an explicit different value still needs a
            # cloned custom host.
            for key in ("protocol", "base_url", "auth_ref"):
                supplied = row.get(key)
                current = getattr(previous, key)
                if supplied not in (None, "") and str(supplied).strip().rstrip("/") != str(current).rstrip("/"):
                    raise ValueError("a seeded host's endpoint and secret reference cannot be changed; clone it")
            host = Host(id=previous.id,
                        display_name=str(row.get("display_name") or previous.display_name),
                        protocol=previous.protocol, base_url=previous.base_url, auth_ref=previous.auth_ref,
                        enabled=row.get("enabled", previous.enabled),
                        timeout=row.get("timeout", previous.timeout),
                        concurrency_limit=row.get("concurrency_limit", previous.concurrency_limit),
                        rate_limit=row.get("rate_limit", previous.rate_limit),
                        discovery_at=previous.discovery_at,
                        endpoint_fingerprint=previous.endpoint_fingerprint,
                        health=previous.health, health_history=previous.health_history,
                        seeded=True).normalise()
        else:
            host = candidate.normalise()
        self._hosts[host.id] = host
        self._save()
        return host.public()

    def update_controls(self, row: dict[str, Any]) -> dict[str, Any]:
        """Update only safe runtime controls without replacing host identity.

        This endpoint deliberately cannot change endpoint, protocol, or the
        key reference.  It is suitable for a future quick-control in the
        model tile and removes the temptation to send a partial full upsert.
        """
        if not isinstance(row, dict):
            raise TypeError("host controls are an object")
        allowed = {"host_id", "enabled", "timeout", "concurrency_limit", "rate_limit"}
        unsupported = sorted(str(key) for key in row if key not in allowed)
        if unsupported:
            raise ValueError("host_controls_only_accept: " + ", ".join(unsupported))
        host_id = row.get("host_id")
        if not isinstance(host_id, str) or not host_id.strip():
            raise ValueError("host_id is required")
        supplied = [key for key in ("enabled", "timeout", "concurrency_limit", "rate_limit")
                    if key in row]
        if not supplied:
            raise ValueError("supply at least one host control")
        if "enabled" in row and not isinstance(row["enabled"], bool):
            raise ValueError("enabled is a boolean")
        for key in ("timeout", "concurrency_limit", "rate_limit"):
            if key in row and (isinstance(row[key], bool) or not isinstance(row[key], (int, float))):
                raise ValueError(f"{key} is a number")

        host = self.get(host_id.strip().lower().replace(" ", "-")[:80])
        identity = (host.protocol, host.base_url, host.auth_ref, host.endpoint_fingerprint)
        for key in supplied:
            setattr(host, key, row[key])
        host.normalise()
        if (host.protocol, host.base_url, host.auth_ref, host.endpoint_fingerprint) != identity:
            # Defensive: controls must never be a backdoor to a different
            # endpoint, even if Host.normalise changes in the future.
            raise AssertionError("host controls changed immutable identity")
        self._save()
        return host.public()

    def remove(self, host_id: str) -> None:
        host = self.get(host_id)
        if host.seeded:
            raise ValueError("a seeded host cannot be removed; disable it instead")
        del self._hosts[host_id]
        self._save()

    def mark_health(self, host_id: str, *, ok: bool, detail: str = "", model: str = "") -> dict[str, Any]:
        host = self.get(host_id)
        host.health = {"status": "ready" if ok else "error", "detail": detail[:300],
                       "model": model[:200], "checked_at": now_iso()}
        host.health_history = [*host.health_history, dict(host.health)][-20:]
        host.discovery_at = now_iso()
        self._save()
        return host.public()


@dataclass
class _HostLimit:
    concurrency: int
    semaphore: threading.BoundedSemaphore
    calls: list[float] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)
    transient_failures: int = 0
    circuit_open_until: float = 0.0
    # Interactive turns (a Lead chat) outrank background sync on the same
    # machine; `idle` is a separate gate from `lock` because a dataclass
    # default_factory cannot bind to a sibling field.
    interactive: int = 0
    idle: threading.Condition = field(default_factory=lambda: threading.Condition(threading.Lock()))


def transient_provider_error(error: ProviderError) -> bool:
    """Classify retryable provider failures without treating auth as transient.

    Provider adapters already retry their own HTTP requests where they have
    status-code detail.  This narrow, text-level fallback covers custom
    OpenAI-compatible adapters and makes the host circuit breaker useful
    without retrying a bad key, model identifier, or malformed request.
    """
    detail = str(error).casefold()
    if any(token in detail for token in ("api_key", "api key", "authentication", "unauthorized",
                                         "forbidden", "not configured", "no model chosen",
                                         "invalid request", "bad request", "404")):
        return False
    return any(token in detail for token in (
        "429", "500", "502", "503", "504", "timeout", "timed out", "slow", "busy",
        "temporar", "connection reset", "connection aborted", "service unavailable",
        "rate limit", "overloaded",
    ))


class HostLimiter:
    """Per-Core enforcement for a personal host's declared limits.

    Limits are intentionally local rather than a promise about a provider's
    account-wide quota.  They prevent the Core's Lead/Clerk concurrency from
    stampeding a custom endpoint and make an overload an explicit
    ``ProviderError`` instead of a silent reroute.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._limits: dict[str, _HostLimit] = {}

    def _limit(self, host: Host) -> _HostLimit:
        with self._lock:
            state = self._limits.get(host.id)
            # If a person lowers a limit, future calls receive a fresh gate.
            # In-flight calls keep their original semaphore safely.
            if state is None or state.concurrency != host.concurrency_limit:
                state = _HostLimit(host.concurrency_limit, threading.BoundedSemaphore(host.concurrency_limit))
                self._limits[host.id] = state
            return state

    def run(self, host: Host, call: Callable[[], T], *, background: bool = False,
            cancel: threading.Event | None = None) -> T:
        state = self._limit(host)
        wait = float(min(max(host.timeout, 1), 120))

        def check_cancelled() -> None:
            if cancel is not None and cancel.is_set():
                raise ProviderCancelledError()

        check_cancelled()
        if background and host.local:
            # A local endpoint shares this machine's CPU with the person
            # chatting, so a background sync yields until the interactive
            # turn drains -- before queueing on the host's semaphore, so an
            # interactive call never waits behind embedding work.
            deadline = time.monotonic() + wait
            with state.idle:
                while state.interactive > 0:
                    check_cancelled()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ProviderError(f"host {host.display_name!r} is busy with an interactive turn; "
                                            "the background call yielded")
                    state.idle.wait(min(remaining, 0.05) if cancel is not None else remaining)
        if not background:
            with state.idle:
                state.interactive += 1
        try:
            deadline = time.monotonic() + wait
            while True:
                check_cancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderError(f"host {host.display_name!r} reached its concurrency limit "
                                        f"({host.concurrency_limit}); no failover was attempted")
                if state.semaphore.acquire(timeout=min(remaining, 0.05)
                                           if cancel is not None else remaining):
                    break
            try:
                check_cancelled()
                if host.rate_limit:
                    with state.lock:
                        now = time.monotonic()
                        if state.circuit_open_until > now:
                            remaining = max(1, round(state.circuit_open_until - now))
                            raise ProviderError(f"host {host.display_name!r} circuit is open after repeated "
                                                f"transient failures; retry in about {remaining}s. "
                                                "No failover was attempted")
                        state.calls[:] = [at for at in state.calls if now - at < 60.0]
                        if len(state.calls) >= host.rate_limit:
                            raise ProviderError(f"host {host.display_name!r} reached its configured rate limit "
                                                f"({host.rate_limit}/minute); no failover was attempted")
                        state.calls.append(now)
                else:
                    with state.lock:
                        now = time.monotonic()
                        if state.circuit_open_until > now:
                            remaining = max(1, round(state.circuit_open_until - now))
                            raise ProviderError(f"host {host.display_name!r} circuit is open after repeated "
                                                f"transient failures; retry in about {remaining}s. "
                                                "No failover was attempted")
                result = call()
                with state.lock:
                    state.transient_failures = 0
                    state.circuit_open_until = 0.0
                return result
            except ProviderError as exc:
                if transient_provider_error(exc):
                    with state.lock:
                        state.transient_failures += 1
                        # Three consecutive host-level failures is enough to stop
                        # a Clerk/Lead stampede, but short enough for a personal
                        # local endpoint to recover without manual reset.
                        if state.transient_failures >= 3:
                            state.circuit_open_until = time.monotonic() + 30.0
                raise
            finally:
                state.semaphore.release()
        finally:
            if not background:
                with state.idle:
                    state.interactive -= 1
                    state.idle.notify_all()


class LimitedProvider(Provider):
    """A transparent Provider facade guarded by :class:`HostLimiter`."""

    def __init__(self, provider: Provider, host: Host, limiter: HostLimiter,
                 retry_policy: str = "bounded") -> None:
        self.provider, self.host, self.limiter = provider, host, limiter
        self.name, self.model = provider.name, provider.model
        self.retry_policy = retry_policy if retry_policy in ("none", "bounded") else "bounded"

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        return self.chat_cancellable(system, messages, tools, max_tokens=max_tokens,
                                     temperature=temperature)

    def chat_cancellable(self, system: str, messages: list[dict[str, Any]],
                         tools: list[ToolDef], max_tokens: int = 4096,
                         temperature: float | None = None,
                         cancel: threading.Event | None = None) -> Reply:
        # Providers with a native HTTP adapter generally retried before this
        # point.  A single, bounded facade retry covers custom endpoints while
        # preserving the selected route; it never silently changes models.
        attempts = 2 if self.retry_policy == "bounded" else 1
        for attempt in range(attempts):
            try:
                return self.limiter.run(self.host, lambda: self.provider.chat_cancellable(
                    system, messages, tools, max_tokens=max_tokens, temperature=temperature,
                    cancel=cancel), cancel=cancel)
            except ProviderError as exc:
                if attempt + 1 >= attempts or not transient_provider_error(exc):
                    raise
                delay = 0.25 * (2 ** attempt)
                if cancel is not None:
                    if cancel.wait(delay):
                        raise ProviderCancelledError()
                else:
                    time.sleep(delay)
        raise AssertionError("bounded provider retry loop unexpectedly ended")

    def models(self) -> list[str]:
        return self.limiter.run(self.host, self.provider.models)

    def usage(self) -> dict[str, Any]:
        return self.limiter.run(self.host, self.provider.usage)

    def check(self) -> dict[str, Any]:
        return self.limiter.run(self.host, self.provider.check)


def validate_l1_probe(reply: Reply, requested_model: str) -> dict[str, Any]:
    """Validate the complete low-cost route/tool contract.

    A provider can be reachable while a selected model still produces a
    malformed tool call.  Keep those facts separate, expose each check to the
    UI, and fail closed rather than treating a matching function name as
    sufficient qualification evidence.
    """
    calls = list(reply.tool_calls) if isinstance(getattr(reply, "tool_calls", None), list) else []
    exact_one = len(calls) == 1
    call = calls[0] if exact_one else None
    tool_name = str(getattr(call, "name", "") or "")
    correct_name = bool(call is not None and tool_name == "librarian_probe")
    arguments = getattr(call, "arguments", None) if call is not None else None
    arguments_exact = (
        isinstance(arguments, dict)
        and set(arguments) == {"ok"}
        and type(arguments.get("ok")) is bool
        and arguments.get("ok") is True
    )
    requested = str(requested_model or "").strip()
    observed = str(getattr(reply, "model", "") or "").strip()
    returned_model = bool(observed and requested and observed == requested)

    failures: list[str] = []
    if not exact_one:
        failures.append("tool_call_count")
    elif not correct_name:
        failures.append("tool_name")
    elif not arguments_exact:
        failures.append("unparseable_arguments" if isinstance(arguments, dict) and "_unparsed" in arguments
                        else "tool_arguments")
    if not observed:
        failures.append("returned_model_missing")
    elif not returned_model:
        failures.append("returned_model_mismatch")

    checks = {
        "exactly_one_call": exact_one,
        "tool_name": correct_name,
        "arguments": arguments_exact,
        "returned_model": returned_model,
    }
    return {
        "contract_version": L1_PROBE_CONTRACT_VERSION,
        "passed": not failures,
        "checks": checks,
        "failure_codes": failures,
        "requested_model": requested,
        "observed_model": observed,
    }


# A token only the probe's tool result carries: echoing it proves the model
# read the tool result rather than answering from the prompt (ADAPT-07).
CONTINUATION_TOKEN = "L1-CONT-7F3A"


def validate_l1_continuation(first: Reply, final: Reply, requested_model: str) -> dict[str, Any]:
    """Validate the second step of the tool-continuation probe.

    The first reply must have proposed a tool call; the final reply must
    contain the continuation token in plain text and *no* further tool calls.
    """
    first_calls = list(first.tool_calls) if isinstance(getattr(first, "tool_calls", None), list) else []
    final_calls = list(final.tool_calls) if isinstance(getattr(final, "tool_calls", None), list) else []

    # Every id must be a non-empty string and globally unique across both replies.
    all_ids = [getattr(c, "id", None) for c in first_calls + final_calls]
    ids_unique = all(isinstance(i, str) and len(i) > 0 for i in all_ids) and len(set(all_ids)) == len(all_ids)

    # Final reply must not propose any tool call.
    final_without_tool_call = len(final_calls) == 0

    # Final reply text must contain the continuation token.
    final_text = str(getattr(final, "text", "") or "")
    final_answer = CONTINUATION_TOKEN in final_text

    # Model identity check (same convention as validate_l1_probe).
    requested = str(requested_model or "").strip()
    observed = str(getattr(final, "model", "") or "").strip()
    returned_model = bool(observed and requested and observed == requested)

    failures: list[str] = []
    if not ids_unique:
        failures.append("tool_call_ids")
    if not final_without_tool_call:
        failures.append("repeated_tool_call")
    if not final_answer:
        failures.append("final_answer_missing")
    if not observed:
        failures.append("returned_model_missing")
    elif not returned_model:
        failures.append("returned_model_mismatch")

    checks = {
        "tool_call_ids_unique": ids_unique,
        "final_without_tool_call": final_without_tool_call,
        "final_answer": final_answer,
        "returned_model": returned_model,
    }
    return {
        "passed": not failures,
        "checks": checks,
        "failure_codes": failures,
        "observed_model": observed,
        "reasoning_content_returned": bool(getattr(first, "reasoning_content", None)),
        "reasoning_replayed": bool(getattr(first, "reasoning_content", None)),
    }


def continuation_messages(prompt_messages: list[dict], first: Reply) -> list[dict]:
    """Build the message list that replays the first turn and appends a tool result."""
    tool_call_id = first.tool_calls[0].id
    return prompt_messages + [
        first.message(),
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps({"ok": True, "token": CONTINUATION_TOKEN}),
        },
    ]


@dataclass
class EvaluationRun:
    id: str
    host_id: str
    model_id: str
    role: str
    level: str
    outcome: str
    compatibility_fingerprint: str
    behavior_fingerprint: str
    at: str
    scenario: str = "default"
    duration_ms: int = 0
    cost_usd: float = 0.0
    detail: str = ""
    artifact: str = ""
    # An L1 account probe records the provider's returned model identifier.
    # It is blank for historical rows and for deterministic L0/L2/L3 records;
    # a release lead deliberately requires a fresh observed identifier.
    observed_model: str = ""
    # Structured proof for strict L1 rows.  Empty is deliberately not treated
    # as a pass, preserving the distinction from historical name-only probes.
    probe_validation: dict[str, Any] = field(default_factory=dict)


def _strict_l1_pass(run: EvaluationRun) -> bool:
    """Whether an L1 record carries successful current-contract evidence."""
    validation = run.probe_validation
    return bool(
        isinstance(validation, dict)
        and validation.get("contract_version") == L1_PROBE_CONTRACT_VERSION
        and validation.get("passed") is True
    )


@dataclass
class Qualification:
    host_id: str
    model_id: str
    role: str
    status: str = "experimental"
    compatibility_fingerprint: str = ""
    behavior_fingerprint: str = ""
    evidence_runs: list[str] = field(default_factory=list)
    updated_at: str = ""
    expires_at: str = ""
    invalidation: str = ""

    @property
    def key(self) -> str:
        return "|".join((self.host_id, self.model_id, self.role))

    def fresh(self, now: datetime | None = None) -> bool:
        """Freshness is deliberately separate from compatibility evidence.

        A route can retain its historical L3 artefacts while becoming too old
        to select without a new probe.  A protocol/schema change is handled
        by ``invalidation`` and immediately removes eligibility instead.
        """
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return False
        now = now or datetime.now(timezone.utc)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return expiry > now


def fingerprints(*, protocol: str, tool_schema: Any, response_contract: Any,
                 endpoint: Any, model: str, security_policy: Any,
                 prompt_bundle: Any, profile: Any, bundle: Any, macros: Any) -> dict[str, str]:
    """Stable hard/soft evidence dependencies used by qualification records."""
    return {
        "compatibility": digest({"protocol": protocol, "tool_schema": tool_schema,
                                  "response_contract": response_contract, "endpoint": endpoint,
                                  "model": model, "security_policy": security_policy}),
        "behavior": digest({"prompt_bundle": prompt_bundle, "profile": profile,
                             "bundle": bundle, "macros": macros}),
    }


class QualificationStore:
    """Append-only-ish local evidence store. Release evidence is read separately."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_dir() / "model-evaluations.json"
        self.runs: dict[str, EvaluationRun] = {}
        self.qualifications: dict[str, Qualification] = {}
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for row in data.get("runs", []) if isinstance(data, dict) else []:
            try:
                run = EvaluationRun(**row)
                self.runs[run.id] = run
            except TypeError:
                continue
        for row in data.get("qualifications", []) if isinstance(data, dict) else []:
            try:
                q = Qualification(**row)
                self.qualifications[q.key] = q
            except TypeError:
                continue

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1, "runs": [asdict(r) for r in self.runs.values()],
                   "qualifications": [asdict(q) for q in self.qualifications.values()]}
        atomic_write_text(self.path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def record(self, *, host_id: str, model_id: str, role: str, level: str,
               outcome: str, compatibility_fingerprint: str, behavior_fingerprint: str,
               scenario: str = "default", duration_ms: int = 0, cost_usd: float = 0.0, detail: str = "",
               artifact: str = "", observed_model: str = "",
               probe_validation: dict[str, Any] | None = None) -> EvaluationRun:
        if level not in EVALUATION_LEVELS:
            raise ValueError(f"evaluation level is one of {EVALUATION_LEVELS}")
        if outcome not in ("pass", "fail", "unavailable", "cancelled"):
            raise ValueError("evaluation outcome is pass, fail, unavailable or cancelled")
        validation = dict(probe_validation) if isinstance(probe_validation, dict) else {}
        run = EvaluationRun(
            secrets.token_hex(10), host_id, model_id, role, level, outcome,
            compatibility_fingerprint, behavior_fingerprint, now_iso(),
            str(scenario or "default")[:120], max(0, int(duration_ms)), max(0.0, float(cost_usd)),
            detail[:500], artifact[:500], str(observed_model or "")[:300], validation,
        )
        self.runs[run.id] = run
        self._derive(host_id, model_id, role, compatibility_fingerprint, behavior_fingerprint)
        self._save()
        return run

    def _derive(self, host_id: str, model_id: str, role: str, compatible: str,
                behavior: str) -> Qualification:
        relevant = [r for r in self.runs.values() if (r.host_id, r.model_id, r.role) ==
                    (host_id, model_id, role) and r.compatibility_fingerprint == compatible]
        q = Qualification(host_id, model_id, role, compatibility_fingerprint=compatible,
                          behavior_fingerprint=behavior, updated_at=now_iso(),
                          evidence_runs=[r.id for r in sorted(relevant, key=lambda r: r.at)])
        passed = {level: [r for r in relevant if r.level == level and r.outcome == "pass"]
                  for level in EVALUATION_LEVELS}
        failed = any(r.outcome == "fail" for r in relevant)
        qualifying = [r for r in relevant if r.outcome == "pass" and r.level in ("L1", "L2", "L3")]
        if qualifying:
            latest = max(qualifying, key=lambda r: r.at)
            try:
                then = datetime.fromisoformat(latest.at)
                if then.tzinfo is None:
                    then = then.replace(tzinfo=timezone.utc)
                q.expires_at = (then + timedelta(days=FRESHNESS_DAYS)).isoformat(timespec="seconds")
            except ValueError:
                q.expires_at = ""
        l3_by_scenario: dict[str, list[EvaluationRun]] = {}
        for run in passed["L3"]:
            l3_by_scenario.setdefault(run.scenario or "default", []).append(run)
        l3_complete = bool(l3_by_scenario) and all(len(rows) >= L3_REQUIRED_RUNS
                                                   for rows in l3_by_scenario.values())
        if failed:
            q.status, q.invalidation = "experimental", "a qualification run failed"
        elif l3_complete:
            q.status = "verified_local"
        elif any(_strict_l1_pass(row) for row in passed["L1"]):
            q.status = "screened"
        elif relevant:
            q.status = "experimental"
        self.qualifications[q.key] = q
        return q

    @staticmethod
    def selectable(q: Qualification | None) -> bool:
        """Whether a local qualification can currently be used as evidence."""
        return bool(q and q.status in ("verified_local", "verified_release") and q.fresh())

    def get(self, host_id: str, model_id: str, role: str) -> Qualification | None:
        return self.qualifications.get("|".join((host_id, model_id, role)))

    def route_change_kind(self, *, host_id: str, model_id: str, role: str,
                          compatibility_fingerprint: str,
                          behavior_fingerprint: str) -> str:
        """Return the pending dependency change before mutating its evidence.

        Callers use this to run the zero-cost L0 contract check exactly once
        when an existing qualification becomes hard-invalid or advisory
        stale.  Keeping it separate from ``invalidate_route`` preserves that
        method's simple backwards-compatible return value.
        """
        q = self.get(host_id, model_id, role)
        if q is None:
            return ""
        if q.compatibility_fingerprint != compatibility_fingerprint:
            return "hard"
        if q.behavior_fingerprint != behavior_fingerprint:
            return "soft"
        return ""

    def has_run(self, *, host_id: str, model_id: str, role: str, level: str,
                compatibility_fingerprint: str, behavior_fingerprint: str,
                scenario: str = "") -> bool:
        """Whether this exact contract already has the named observed run."""
        return any(
            (row.host_id, row.model_id, row.role, row.level,
             row.compatibility_fingerprint, row.behavior_fingerprint) ==
            (host_id, model_id, role, level, compatibility_fingerprint, behavior_fingerprint)
            and (not scenario or row.scenario == scenario)
            for row in self.runs.values())

    def annotate_route(self, *, host_id: str, model_id: str, role: str,
                       invalidation: str) -> Qualification | None:
        """Persist the person-visible reason attached to current evidence."""
        q = self.get(host_id, model_id, role)
        if q is not None:
            q.invalidation = str(invalidation)[:500]
            self._save()
        return q

    def matching_l1_probe(self, *, host_id: str, model_id: str, role: str,
                          compatibility_fingerprint: str, observed_model: str,
                          now: datetime | None = None) -> EvaluationRun | None:
        """Return a current, exact account probe for a bundled release route.

        This is intentionally stricter than ``screened``: a release record is
        evidence from CI, whereas this record proves that *this person's*
        account reached the same endpoint, requested route and provider-returned
        model after the current hard contract was established.
        """
        current_time = now or datetime.now(timezone.utc)
        candidates: list[EvaluationRun] = []
        for run in self.runs.values():
            if (run.host_id, run.model_id, run.role, run.level, run.outcome) != \
                    (host_id, model_id, role, "L1", "pass"):
                continue
            if run.compatibility_fingerprint != compatibility_fingerprint:
                continue
            if not _strict_l1_pass(run):
                continue
            if not run.observed_model or run.observed_model != observed_model:
                continue
            at = _as_time(run.at)
            if at is None or at + timedelta(days=FRESHNESS_DAYS) <= current_time:
                continue
            candidates.append(run)
        return max(candidates, key=lambda row: row.at) if candidates else None

    def invalidate(self, *, compatibility_fingerprint: str, behavior_fingerprint: str) -> list[Qualification]:
        changed = []
        for q in self.qualifications.values():
            if q.compatibility_fingerprint != compatibility_fingerprint:
                q.status, q.invalidation = "experimental", "hard compatibility fingerprint changed"
                q.compatibility_fingerprint = compatibility_fingerprint
                q.behavior_fingerprint = behavior_fingerprint
                changed.append(q)
            elif q.behavior_fingerprint != behavior_fingerprint:
                q.invalidation = "advisory_stale: behavior fingerprint changed"
                q.behavior_fingerprint = behavior_fingerprint
                changed.append(q)
        if changed:
            self._save()
        return changed

    def invalidate_route(self, *, host_id: str, model_id: str, role: str,
                         compatibility_fingerprint: str,
                         behavior_fingerprint: str) -> Qualification | None:
        """Refresh one route's dependency evidence without churning others.

        Endpoint fingerprints naturally differ between hosts, so applying a
        route's fingerprint to every qualification would falsely invalidate a
        whole person's model registry on every settings visit.
        """
        q = self.get(host_id, model_id, role)
        if q is None:
            return None
        if q.compatibility_fingerprint != compatibility_fingerprint:
            q.status = "experimental"
            q.invalidation = "hard compatibility fingerprint changed"
            q.compatibility_fingerprint = compatibility_fingerprint
            q.behavior_fingerprint = behavior_fingerprint
            self._save()
        elif q.behavior_fingerprint != behavior_fingerprint:
            q.invalidation = "advisory_stale: behavior fingerprint changed"
            q.behavior_fingerprint = behavior_fingerprint
            self._save()
        return q


@dataclass
class EvaluationJob:
    """A durable plan for paid, multi-turn qualification work.

    The job records *what remains to be evaluated*, not a made-up result.  A
    real evaluator (the local golden-walk runner or release CI) submits one
    artifact-backed result at a time.  This makes an interrupted overnight
    run resumable without allowing the UI to accidentally turn a plan into
    ``verified_local`` evidence.
    """

    id: str
    host_id: str
    model_id: str
    role: str
    level: str
    scenario: str
    total_runs: int
    compatibility_fingerprint: str
    behavior_fingerprint: str
    plan: dict[str, Any]
    created_at: str
    updated_at: str
    state: str = "queued"
    completed_runs: int = 0
    run_ids: list[str] = field(default_factory=list)
    detail: str = ""
    cancellation_reason: str = ""
    advisory_stale: bool = False

    @property
    def key(self) -> str:
        return "|".join((self.host_id, self.model_id, self.role))

    @property
    def terminal(self) -> bool:
        return self.state in ("cancelled", "completed", "stale")

    def public(self) -> dict[str, Any]:
        row = asdict(self)
        row["remaining_runs"] = max(0, self.total_runs - self.completed_runs)
        row["resumable"] = self.state in ("queued", "paused")
        # A queued job is deliberately not proof that any paid work began.
        row["requires_result_artifact"] = True
        return row


class EvaluationJobStore:
    """Small crash-safe queue for L2/L3 evaluation plans.

    The queue is stored alongside the person's host settings rather than in a
    vault.  It therefore cannot leak a provider route into a shared vault,
    while artifact references and resulting qualification evidence remain
    inspectable by the person who initiated the work.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_dir() / "model-evaluation-jobs.json"
        self.jobs: dict[str, EvaluationJob] = {}
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        fields = EvaluationJob.__dataclass_fields__
        for row in data.get("jobs", []) if isinstance(data, dict) else []:
            if not isinstance(row, dict):
                continue
            try:
                job = EvaluationJob(**{key: value for key, value in row.items() if key in fields})
            except (TypeError, ValueError):
                continue
            if job.level not in ("L2", "L3") or job.state not in EVALUATION_JOB_STATES:
                continue
            job.total_runs = max(1, int(job.total_runs))
            job.completed_runs = max(0, min(int(job.completed_runs), job.total_runs))
            self.jobs[job.id] = job

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 1,
                   "jobs": [asdict(job) for job in sorted(self.jobs.values(),
                                                           key=lambda row: row.created_at)]}
        atomic_write_text(self.path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")

    def create(self, plan: dict[str, Any], *, scenario: str = "default") -> EvaluationJob:
        level = str(plan.get("level") or "")
        if level not in ("L2", "L3"):
            raise ValueError("only L2/L3 work uses an evaluation job")
        fingerprints_row = plan.get("fingerprints")
        if not isinstance(fingerprints_row, dict) or not fingerprints_row.get("compatibility"):
            raise ValueError("evaluation plan has no compatibility fingerprint")
        counts = {"L2": L2_REQUIRED_RUNS, "L3": L3_REQUIRED_RUNS}
        stamp = now_iso()
        job = EvaluationJob(
            id=f"eval-{secrets.token_hex(10)}",
            host_id=str(plan.get("host_id") or ""), model_id=str(plan.get("model") or ""),
            role=str(plan.get("role") or "lead"), level=level,
            scenario=str(scenario or "default")[:120], total_runs=counts[level],
            compatibility_fingerprint=str(fingerprints_row["compatibility"]),
            behavior_fingerprint=str(fingerprints_row.get("behavior") or ""),
            plan=dict(plan), created_at=stamp, updated_at=stamp,
            detail="Queued; a local evaluator or release CI must submit artifact-backed results.")
        if not job.host_id or not job.model_id:
            raise ValueError("evaluation plan needs a host and model")
        with self._lock:
            self.jobs[job.id] = job
            self._save()
        return job

    def pending_for(self, *, host_id: str, model_id: str, role: str, level: str,
                    compatibility_fingerprint: str, behavior_fingerprint: str,
                    scenario: str) -> EvaluationJob | None:
        """Find the durable automatic/manual plan for one exact contract."""
        with self._lock:
            rows = [job for job in self.jobs.values()
                    if (job.host_id, job.model_id, job.role, job.level, job.scenario,
                        job.compatibility_fingerprint, job.behavior_fingerprint) ==
                    (host_id, model_id, role, level, scenario,
                     compatibility_fingerprint, behavior_fingerprint)
                    and job.state not in ("cancelled", "stale", "completed")]
            return max(rows, key=lambda job: job.updated_at) if rows else None

    def mark_automatic(self, job: EvaluationJob, *, kind: str) -> EvaluationJob:
        """Explain why a zero-cost invalidation created a paid-work plan.

        Queueing never makes a provider call.  The existing explicit spend
        checkpoint remains the only path that starts an evaluator, so this
        record is safe to create during a fingerprint check.
        """
        with self._lock:
            job.detail = (f"Automatically queued after {kind} qualification dependency change. "
                          "No provider call has started; approve a spend checkpoint before evaluation.")[:500]
            job.updated_at = now_iso()
            self._save()
            return job

    def get(self, job_id: str) -> EvaluationJob:
        with self._lock:
            try:
                return self.jobs[job_id]
            except KeyError as exc:
                raise KeyError(f"no evaluation job {job_id!r}") from exc

    def list(self, *, host_id: str = "", model_id: str = "", role: str = "") -> list[dict[str, Any]]:
        with self._lock:
            rows = [job for job in self.jobs.values()
                    if (not host_id or job.host_id == host_id)
                    and (not model_id or job.model_id == model_id)
                    and (not role or job.role == role)]
            return [job.public() for job in sorted(rows, key=lambda row: row.updated_at, reverse=True)]

    def cancel(self, job_id: str, reason: str = "cancelled by person") -> EvaluationJob:
        with self._lock:
            job = self.get(job_id)
            if job.state == "completed":
                raise ValueError("a completed evaluation cannot be cancelled")
            if job.state == "stale":
                raise ValueError("a stale evaluation cannot be resumed; create a fresh plan")
            job.state = "cancelled"
            job.cancellation_reason = str(reason or "cancelled by person")[:500]
            job.detail = job.cancellation_reason
            job.updated_at = now_iso()
            self._save()
            return job

    def pause(self, job_id: str, reason: str = "paused by person") -> EvaluationJob:
        with self._lock:
            job = self.get(job_id)
            if job.terminal:
                raise ValueError("only an unfinished evaluation can be paused")
            job.state = "paused"
            job.detail = str(reason or "paused by person")[:500]
            job.updated_at = now_iso()
            self._save()
            return job

    def resume(self, job_id: str) -> EvaluationJob:
        with self._lock:
            job = self.get(job_id)
            if job.state == "stale":
                raise ValueError("a stale evaluation cannot be resumed; create a fresh plan")
            if job.state in ("cancelled", "completed"):
                raise ValueError("only a paused evaluation can be resumed")
            job.state = "queued"
            job.detail = "Queued for the next artifact-backed evaluator result."
            job.updated_at = now_iso()
            self._save()
            return job

    def begin_result(self, job_id: str, *, compatibility_fingerprint: str) -> EvaluationJob:
        """Claim the next result slot after checking a hard dependency.

        A behavior-only change is retained as advisory evidence.  A protocol,
        schema, endpoint, model, or security-policy change makes the plan
        stale: an old golden-walk artifact must not be attached to a new
        contract.
        """
        with self._lock:
            job = self.get(job_id)
            if job.compatibility_fingerprint != compatibility_fingerprint:
                job.state = "stale"
                job.detail = "Hard compatibility fingerprint changed; create a fresh evaluation plan."
                job.updated_at = now_iso()
                self._save()
                raise ValueError(job.detail)
            if job.state not in ("queued", "paused", "running"):
                raise ValueError("evaluation job is not ready for another result")
            if job.completed_runs >= job.total_runs:
                job.state = "completed"
                job.updated_at = now_iso()
                self._save()
                raise ValueError("evaluation job already has all planned results")
            job.state = "running"
            job.updated_at = now_iso()
            self._save()
            return job

    def finish_result(self, job_id: str, run_id: str, *, outcome: str, detail: str = "") -> EvaluationJob:
        with self._lock:
            job = self.get(job_id)
            if job.state != "running":
                raise ValueError("evaluation job has no claimed result slot")
            if run_id in job.run_ids:
                raise ValueError("this evaluation result is already attached")
            job.run_ids.append(run_id)
            job.completed_runs = min(job.total_runs, job.completed_runs + 1)
            job.updated_at = now_iso()
            job.detail = str(detail or "result recorded")[:500]
            if job.completed_runs >= job.total_runs:
                job.state = "completed"
            elif outcome in ("fail", "unavailable", "cancelled"):
                # Do not burn a budget after a failure or outage.  A person
                # explicitly resumes once they have reviewed the artifact.
                job.state = "paused"
            else:
                job.state = "queued"
            self._save()
            return job

    def invalidate_route(self, *, host_id: str, model_id: str, role: str,
                         compatibility_fingerprint: str, behavior_fingerprint: str) -> list[EvaluationJob]:
        """Mark unfinished jobs stale/advisory when their evidence changes."""
        changed: list[EvaluationJob] = []
        with self._lock:
            for job in self.jobs.values():
                if (job.host_id, job.model_id, job.role) != (host_id, model_id, role) or job.terminal:
                    continue
                if job.compatibility_fingerprint != compatibility_fingerprint:
                    job.state = "stale"
                    job.detail = "Hard compatibility fingerprint changed; create a fresh evaluation plan."
                    job.updated_at = now_iso()
                    changed.append(job)
                elif job.behavior_fingerprint != behavior_fingerprint:
                    job.advisory_stale = True
                    job.detail = "Advisory stale: behavior fingerprint changed; review before release use."
                    job.updated_at = now_iso()
                    changed.append(job)
            if changed:
                self._save()
        return changed


RELEASE_LEADS_PATH = Path(__file__).parent / "standard" / "release_leads.json"
RELEASE_LEADS_PATH_ENV = "LIBRARIAN_RELEASE_LEADS_PATH"
RELEASE_LEADS_SHA256_ENV = "LIBRARIAN_RELEASE_LEADS_SHA256"


def _installed_release_leads_path() -> tuple[Path | None, str]:
    """Return the release-bundle evidence file only when it is hash-bound.

    Stable installers keep the signed bundle's lead record beside the venv;
    the wheel itself intentionally remains buildable from the same source
    tree.  A bare environment path is not enough to redirect qualification
    evidence: the launcher must also provide the SHA-256 recorded in the
    verified release manifest.  This is defence in depth around the detached
    bundle signature, not a replacement for it.
    """
    raw_path = os.environ.get(RELEASE_LEADS_PATH_ENV, "").strip()
    expected_hash = os.environ.get(RELEASE_LEADS_SHA256_ENV, "").strip().lower()
    if not raw_path and not expected_hash:
        return None, ""
    if not raw_path or not re.fullmatch(r"[0-9a-f]{64}", expected_hash):
        return None, "installed release-lead override is incomplete or has no valid SHA-256"
    candidate = Path(raw_path).expanduser()
    if not candidate.is_absolute():
        return None, "installed release-lead override must be an absolute path"
    try:
        actual_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
    except OSError:
        return None, "installed release-lead override could not be read"
    if not hmac.compare_digest(actual_hash, expected_hash):
        return None, "installed release-lead override does not match the signed bundle hash"
    return candidate, ""


def _integrity_valid(manifest: dict[str, Any]) -> bool:
    """Check the compact content digest shipped with the embedded record."""
    payload = {key: value for key, value in manifest.items()
               if key not in ("integrity", "integrity_valid", "manifest_valid", "manifest_reason")}
    actual = manifest.get("integrity")
    return isinstance(actual, str) and len(actual) == len(digest(payload)) and \
        hmac.compare_digest(actual, digest(payload))


def _verification_record_valid(value: Any) -> bool:
    """Require a real release-pipeline verification reference, not a boolean.

    The Core cannot reimplement the operating system's package-signature
    verifier.  It does require the signed artifact's verification record to
    be named, so a hand-edited ``status: signed`` cannot become runtime model
    evidence by itself.  Installer/release CI verifies the signature itself.
    """
    if isinstance(value, str):
        return bool(value.strip())
    if not isinstance(value, dict):
        return False
    reference = any(isinstance(value.get(key), str) and value[key].strip()
                    for key in ("id", "uri", "artifact", "signature"))
    verified = _as_time(value.get("verified_at")) is not None
    return reference and verified


def validate_release_lead_manifest(manifest: dict[str, Any], *,
                                   now: datetime | None = None) -> tuple[bool, str]:
    """Validate the signed-release envelope before trusting any lead row.

    Development templates deliberately fail this check while retaining their
    candidates for the setup UI.  That distinction means an intact pending
    file is visible but never mistaken for release qualification evidence.
    """
    if not isinstance(manifest, dict):
        return False, "bundled release-lead manifest is not an object"
    if manifest.get("schema_version") != RELEASE_LEAD_SCHEMA_VERSION:
        return False, "bundled release-lead manifest schema is unsupported"
    if not _integrity_valid(manifest):
        return False, "bundled release-lead manifest integrity could not be verified"
    status = str(manifest.get("release_status") or "")
    if status == "development_template":
        return False, "bundled release-lead data is a development template, not release evidence"
    if status != RELEASE_LEAD_MANIFEST_STABLE_STATUS:
        return False, "bundled release-lead manifest is not a stable release"
    version = str(manifest.get("release_version") or manifest.get("version") or "")
    if _semver(version) is None:
        return False, "bundled release-lead manifest has no valid release version"
    signing = manifest.get("signing")
    if not isinstance(signing, dict) or signing.get("status") != "signed" or \
            not _verification_record_valid(signing.get("verification")):
        return False, "bundled release-lead manifest has no signed verification record"
    shared = manifest.get("contract")
    if not isinstance(shared, dict):
        return False, "bundled release-lead manifest has no shared contract"
    for key in ("protocol_version", "tool_contract_version", "prompt_contract_version"):
        if not isinstance(shared.get(key), str) or not shared[key].strip():
            return False, f"bundled release-lead manifest is missing contract {key}"
    if not (isinstance(shared.get("core_version"), str) and shared["core_version"].strip()) and \
            not (isinstance(shared.get("core_version_range"), str) and shared["core_version_range"].strip()):
        return False, "bundled release-lead manifest has no Core compatibility contract"
    if not isinstance(manifest.get("leads"), list):
        return False, "bundled release-lead manifest has no lead list"
    return True, ""


def release_leads(path: Path | None = None) -> dict[str, Any]:
    """Read embedded release-lead data without inventing qualification.

    ``integrity`` catches damaged or locally edited content.  Stable rows are
    additionally gated by a signed release-pipeline verification reference;
    artifact signing itself remains the installer/OS verifier's job, not a
    home-grown PKI inside this single-user Core.
    """
    override_reason = ""
    if path is not None:
        source = path
    else:
        installed_source, override_reason = _installed_release_leads_path()
        # An attempted override must fail closed instead of quietly falling
        # back to a package candidate.  That makes a damaged installed bundle
        # visible rather than silently changing qualification provenance.
        if override_reason:
            return {"schema_version": RELEASE_LEAD_SCHEMA_VERSION, "leads": [], "integrity": "invalid",
                    "integrity_valid": False, "manifest_valid": False,
                    "manifest_reason": override_reason}
        source = installed_source or RELEASE_LEADS_PATH
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"schema_version": RELEASE_LEAD_SCHEMA_VERSION, "leads": [], "integrity": "missing",
                "integrity_valid": False, "manifest_valid": False,
                "manifest_reason": "bundled release-lead manifest could not be read"}
    if not isinstance(data, dict):
        return {"schema_version": RELEASE_LEAD_SCHEMA_VERSION, "leads": [], "integrity": "invalid",
                "integrity_valid": False, "manifest_valid": False,
                "manifest_reason": "bundled release-lead manifest is not an object"}
    integrity_valid = _integrity_valid(data)
    manifest_valid, manifest_reason = validate_release_lead_manifest(data)
    rows = data.get("leads", [])
    return {**data, "integrity_valid": integrity_valid,
            "manifest_valid": manifest_valid, "manifest_reason": manifest_reason,
            # A development template with an intact digest remains visible to
            # first-run setup.  An integrity failure hides rows altogether.
            "leads": rows if integrity_valid and isinstance(rows, list) else []}


def _merged_release_lead(manifest: dict[str, Any], lead: dict[str, Any]) -> dict[str, Any]:
    """Allow a signed manifest to put shared contract facts at its top level."""
    common = manifest.get("contract")
    merged = {**common, **lead} if isinstance(common, dict) else dict(lead)
    common_endpoint = common.get("endpoint") if isinstance(common, dict) else None
    lead_endpoint = lead.get("endpoint")
    if isinstance(common_endpoint, dict) and isinstance(lead_endpoint, dict):
        merged["endpoint"] = {**common_endpoint, **lead_endpoint}
    return merged


def validate_release_lead(lead: dict[str, Any], *, contract: dict[str, Any] | None = None,
                          now: datetime | None = None) -> tuple[bool, str]:
    """Validate one evidence-bearing release lead, failing closed by detail.

    A pending candidate is deliberately useful to first-run UI, but cannot
    pass this function.  A verified row needs explicit version, endpoint,
    L3-artifact and expiry facts before the Core will combine it with a
    user's L1 probe.
    """
    if not isinstance(lead, dict):
        return False, "release lead is not an object"
    if lead.get("qualification") != "verified_release":
        return False, "bundled release evidence is pending or not verified"
    for key in ("id", "provider", "host_id", "model", "model_version", "model_fingerprint", "role"):
        if not isinstance(lead.get(key), str) or not str(lead[key]).strip():
            return False, f"release lead is missing {key}"
    if str(lead.get("provider")) not in ("openai", "anthropic"):
        return False, "release lead provider is not a supported hosted lead"
    if str(lead.get("role")) != "lead":
        return False, "release lead must be qualified for the lead role"
    expected_model_fingerprint = digest({"provider": lead["provider"], "model": lead["model"],
                                         "model_version": lead["model_version"]})
    if not hmac.compare_digest(str(lead["model_fingerprint"]), expected_model_fingerprint):
        return False, "release lead model fingerprint does not match its exact model version"
    endpoint = lead.get("endpoint")
    if not isinstance(endpoint, dict) or not str(endpoint.get("protocol") or "").strip() or \
            not str(endpoint.get("base_url") or "").strip() or \
            not str(endpoint.get("auth_ref") or "").strip():
        return False, "release lead has no exact endpoint requirement"
    if str(endpoint.get("protocol")) != str(lead.get("provider")):
        return False, "release lead endpoint protocol does not match its provider"
    if not isinstance(lead.get("endpoint_fingerprint"), str) or not lead["endpoint_fingerprint"].strip():
        return False, "release lead has no endpoint fingerprint"
    if not hmac.compare_digest(str(lead["endpoint_fingerprint"]), endpoint_fingerprint(endpoint)):
        return False, "release lead endpoint fingerprint does not match its endpoint requirement"
    if not isinstance(lead.get("protocol_version"), str) or not lead["protocol_version"].strip():
        return False, "release lead has no Core protocol version"
    if not isinstance(lead.get("tool_contract_version"), str) or not lead["tool_contract_version"].strip():
        return False, "release lead has no tool contract version"
    if not isinstance(lead.get("prompt_contract_version"), str) or not lead["prompt_contract_version"].strip():
        return False, "release lead has no prompt contract version"
    if not (isinstance(lead.get("core_version"), str) and lead["core_version"].strip()) and \
            not (isinstance(lead.get("core_version_range"), str) and lead["core_version_range"].strip()):
        return False, "release lead has no Core version compatibility"
    tested = _as_time(lead.get("tested_at"))
    expiry = _as_time(lead.get("expires_at"))
    current_time = now or datetime.now(timezone.utc)
    if tested is None:
        return False, "release lead has no valid evidence date"
    if tested > current_time + timedelta(days=1):
        return False, "release lead evidence date is in the future"
    if expiry is None:
        return False, "release lead has no valid expiry"
    if expiry <= current_time:
        return False, "bundled release evidence has expired"
    if expiry <= tested:
        return False, "release lead expiry must be later than its evidence date"
    try:
        runs = int(lead.get("l3_runs") or 0)
    except (TypeError, ValueError):
        runs = 0
    if runs < L3_REQUIRED_RUNS:
        return False, f"release lead records {runs} L3 runs, not {L3_REQUIRED_RUNS}"
    artifacts = lead.get("qualification_artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        return False, "release lead has no L3 qualification artifacts"
    for item in artifacts:
        if not isinstance(item, dict) or not any(isinstance(item.get(key), str) and item[key].strip()
                                                  for key in ("uri", "path", "id")):
            return False, "release lead has an invalid qualification artifact reference"
        artifact_hash = item.get("sha256")
        if not isinstance(artifact_hash, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", artifact_hash):
            return False, "release lead qualification artifact has no SHA-256 integrity record"
    if contract is None:
        return True, ""
    expected_protocol = str(contract.get("protocol_version") or "")
    if expected_protocol and lead["protocol_version"] != expected_protocol:
        return False, "release lead Core protocol is incompatible"
    expected_tool = str(contract.get("tool_contract_version") or "")
    if expected_tool and lead["tool_contract_version"] != expected_tool:
        return False, "release lead tool contract is incompatible"
    expected_prompt = str(contract.get("prompt_contract_version") or "")
    if expected_prompt and lead["prompt_contract_version"] != expected_prompt:
        return False, "release lead prompt contract is incompatible"
    expected_core = str(contract.get("core_version") or "")
    if expected_core:
        exact = str(lead.get("core_version") or "")
        version_range = str(lead.get("core_version_range") or "")
        if exact and exact != expected_core:
            return False, "release lead Core version is incompatible"
        if not exact and not _in_version_range(expected_core, version_range):
            return False, "release lead Core version range is incompatible"
    expected_fingerprint = str(contract.get("endpoint_fingerprint") or "")
    if expected_fingerprint and lead["endpoint_fingerprint"] != expected_fingerprint:
        return False, "release lead endpoint fingerprint changed"
    expected_endpoint = contract.get("endpoint")
    if isinstance(expected_endpoint, dict):
        if str(endpoint.get("protocol") or "") != str(expected_endpoint.get("protocol") or "") or \
                str(endpoint.get("base_url") or "").rstrip("/") != \
                str(expected_endpoint.get("base_url") or "").rstrip("/") or \
                str(endpoint.get("auth_ref") or "") != str(expected_endpoint.get("auth_ref") or ""):
            return False, "release lead endpoint requirement changed"
    return True, ""


def release_lead_for_route(host_id: str, model_id: str, *, contract: dict[str, Any],
                           role: str = "lead", manifest: dict[str, Any] | None = None
                           ) -> tuple[dict[str, Any] | None, str]:
    """Return a runtime-compatible verified release lead for one exact route."""
    data = manifest if manifest is not None else release_leads()
    matches = []
    for raw in data.get("leads", []):
        if not isinstance(raw, dict):
            continue
        lead = _merged_release_lead(data, raw)
        if (str(lead.get("host_id") or lead.get("provider") or "") == host_id and
                str(lead.get("model") or "") == model_id and str(lead.get("role") or "lead") == role):
            matches.append(lead)
    if not matches:
        return None, ""
    if len(matches) != 1:
        return None, "bundled release evidence is ambiguous for this route"
    valid_manifest, manifest_reason = validate_release_lead_manifest(data)
    if not valid_manifest:
        return None, manifest_reason
    valid, reason = validate_release_lead(matches[0], contract=contract)
    return (matches[0], "") if valid else (None, reason)


def verified_release_leads(*, contract: dict[str, Any] | None = None,
                           manifest: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """List only complete (and optionally runtime-compatible) release evidence."""
    data = manifest if manifest is not None else release_leads()
    valid_manifest, _ = validate_release_lead_manifest(data)
    if not valid_manifest:
        return []
    rows = []
    for raw in data.get("leads", []):
        if not isinstance(raw, dict):
            continue
        row = _merged_release_lead(data, raw)
        valid, _ = validate_release_lead(row, contract=contract)
        if valid:
            rows.append(row)
    return rows
