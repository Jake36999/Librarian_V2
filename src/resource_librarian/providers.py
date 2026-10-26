"""The provider layer: two protocols behind one interface.

The standalone agent loop talks to a model through a `Provider`: a list of
messages and a list of tools in, a `Reply` (text and tool calls) out. Two
protocols cover every provider V2 supports:

- **OpenAI-compatible** `/chat/completions`: OpenAI, DeepInfra, and a local
  server (LM Studio or any compatible URL, no key needed);
- **Anthropic's Messages API**.

Messages are kept in one neutral shape and translated at the edge, so the loop
never knows which protocol it is speaking. Keys are read from the environment
of the core process, by name, and never returned: `check()` reports whether a
key is present and what the provider's live model listing says, which is also
where model ids come from (never a hard-coded list). Standard library only.

The neutral message shape:
- `{"role": "user", "content": str}`
- `{"role": "assistant", "content": str, "tool_calls": [{"id", "name", "arguments": dict}]}`
- `{"role": "tool", "tool_call_id": str, "name": str, "content": str}`
"""
from __future__ import annotations

import http.client
import json
import os
import re
import secrets
import select
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable

PRESETS: dict[str, dict[str, str]] = {
    "openai": {"protocol": "openai", "base_url": "https://api.openai.com/v1",
               "key_env": "OPENAI_API_KEY"},
    "deepinfra": {"protocol": "openai", "base_url": "https://api.deepinfra.com/v1/openai",
                  "key_env": "DEEPINFRA_API_KEY"},
    "local": {"protocol": "openai", "base_url": "http://127.0.0.1:1234/v1", "key_env": ""},
    "anthropic": {"protocol": "anthropic", "base_url": "https://api.anthropic.com/v1",
                  "key_env": "ANTHROPIC_API_KEY"},
}
ANTHROPIC_VERSION = "2023-06-01"

# Where a person is sent to see billing directly: confirmed dashboard roots,
# not a guessed sub-page. Local has none - there is no account to bill.
DASHBOARDS: dict[str, str] = {"deepinfra": "https://deepinfra.com/dash",
                             "openai": "https://platform.openai.com/usage",
                             "anthropic": "https://console.anthropic.com/settings/billing"}

# A balance endpoint outside DeepInfra's OpenAI-compatible surface, found by
# reading a community project's code rather than in DeepInfra's own published
# API reference: unofficial, and may change or disappear without notice.
# `usage()` treats it that way - one best-effort read, never load-bearing.
_DEEPINFRA_BALANCE = "https://api.deepinfra.com/payment/checklist?compute_owed=true"


PROVIDER_FAILURE_CATEGORIES = (
    "local_environment",
    "credentials",
    "route_configuration",
    "provider_rate_limited",
    "provider_transient",
    "provider_transport",
    "provider_rejected",
    "output_budget",
    "model_identity_mismatch",
    "cancelled",
    "unknown",
)


class ProviderError(RuntimeError):
    """A selected route could not answer, with an optional typed cause.

    The message remains safe, concise, and useful to a person.  ``category``
    is deliberately separate from the message so a Windows socket policy or a
    missing key cannot be reported as evidence that a model is unreliable.
    Older/custom adapters may still construct this with only a message; the
    classifier below gives those errors a conservative category at the Core
    boundary.
    """

    def __init__(self, message: str, *, category: str = "") -> None:
        super().__init__(message)
        self.category = category if category in PROVIDER_FAILURE_CATEGORIES else ""


class ProviderCancelledError(ProviderError):
    """The caller cancelled an in-flight provider operation."""

    def __init__(self) -> None:
        super().__init__("the provider request was cancelled", category="cancelled")


def _safe_token_count(value: Any) -> int | None:
    """Accept only non-negative integral token counts from a provider reply."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    if isinstance(value, float) and value >= 0 and value.is_integer():
        return int(value)
    return None


def _safe_usage(value: Any) -> dict[str, int]:
    """Normalize the small non-secret usage subset shared by supported APIs.

    Provider payloads often grow product-specific nested accounting fields. A
    runtime trace needs only the response's input/output/total token counts;
    keeping the whole object would make it an accidental raw-provider-payload
    store. Invalid, negative, boolean, and unknown values are ignored.
    """
    if not isinstance(value, Mapping):
        return {}

    def first(*names: str) -> int | None:
        for name in names:
            token_count = _safe_token_count(value.get(name))
            if token_count is not None:
                return token_count
        return None

    usage: dict[str, int] = {}
    input_tokens = first("input_tokens", "prompt_tokens")
    output_tokens = first("output_tokens", "completion_tokens")
    total_tokens = first("total_tokens")
    if input_tokens is not None:
        usage["input_tokens"] = input_tokens
    if output_tokens is not None:
        usage["output_tokens"] = output_tokens
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    if total_tokens is not None:
        usage["total_tokens"] = total_tokens
    return usage


_SAFE_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,199}")


def _safe_request_id(value: Any) -> str:
    """Return a bounded diagnostic request ID, never an arbitrary header value."""
    if not isinstance(value, str):
        return ""
    candidate = value.strip()
    return candidate if _SAFE_REQUEST_ID.fullmatch(candidate) else ""


def _response_request_id(headers: Any) -> str:
    """Extract an explicitly named provider request header, if one is safe.

    The response JSON's ``id`` is a completion identifier, not an HTTP request
    ID; it deliberately never flows into this diagnostic field.
    """
    try:
        items = headers.items()
    except (AttributeError, TypeError):
        return ""
    for name, value in items:
        if str(name).casefold() in {"x-request-id", "request-id", "anthropic-request-id"}:
            request_id = _safe_request_id(value)
            if request_id:
                return request_id
    return ""


class _ResponsePayload(dict):
    """A normal decoded response object with optional safe HTTP metadata.

    Keeping this a ``dict`` subclass preserves every existing monkeypatch and
    caller that expects the historical decoded-body return shape from
    :func:`_request`.
    """

    __slots__ = ("request_id",)

    def __init__(self, body: dict[str, Any], request_id: str = "") -> None:
        super().__init__(body)
        self.request_id = _safe_request_id(request_id)


class OutputBudgetError(ProviderError):
    """A response ended for length before it yielded text or a tool proposal."""

    def __init__(self, *, observed_model: Any = "", stop_reason: Any = "",
                 usage: Any = None, request_id: Any = "") -> None:
        super().__init__(
            "the model reached its output budget before returning text or a tool call",
            category="output_budget",
        )
        self.observed_model = str(observed_model or "")[:300]
        self.stop_reason = str(stop_reason or "")[:160]
        self.usage = _safe_usage(usage)
        self.request_id = _safe_request_id(request_id)


def provider_failure_category(error: BaseException | str) -> str:
    """Return a stable, user-facing category for a route failure.

    This is intentionally a small taxonomy: it distinguishes failures a
    person can repair locally from provider behaviour without claiming that a
    generic network error says anything about model quality.  Explicit adapter
    categories win; the text fallback preserves compatibility for custom and
    historical adapters that raised the old message-only ``ProviderError``.
    """
    explicit = str(getattr(error, "category", ""))
    if explicit in PROVIDER_FAILURE_CATEGORIES:
        return explicit

    # A real OS exception is useful evidence.  Do not infer the same result
    # from the bare words "permission denied": provider responses and custom
    # adapters can use that wording for an account or policy rejection.
    if isinstance(error, PermissionError) or getattr(error, "winerror", None) == 10013:
        return "local_environment"

    detail = str(error).casefold()
    # Setup/identity precedes local-permission matching: an HTTP 403 whose
    # provider happens to say "permission denied" is a provider credential
    # problem, not a Windows socket-policy failure.
    if any(token in detail for token in (
        "no model chosen", "no anthropic model chosen", "not configured",
        "unknown provider", "host is disabled", "model not found", "http 404",
    )):
        return "route_configuration"
    if any(token in detail for token in (
        "api_key", "api key", "is not set", "authentication", "unauthorized",
        "invalid key", "http 401", "http 403",
    )):
        return "credentials"
    if any(token in detail for token in (
        "winerror 10013", "socket in a way forbidden", "network access is disabled",
        "blocked by local policy", "socket access forbidden",
    )):
        return "local_environment"
    if any(token in detail for token in ("http 429", "rate limit", "rate-limited")):
        return "provider_rate_limited"
    if any(token in detail for token in (
        "http 500", "http 502", "http 503", "http 504", "timed out",
        "timeout", "provider is slow", "provider busy", "service unavailable",
        "overloaded", "connection reset", "connection aborted",
    )):
        return "provider_transient"
    if any(token in detail for token in (
        "is not reachable", "connection refused", "name or service not known",
        "temporary failure in name resolution", "dns", "network is unreachable",
    )):
        return "provider_transport"
    if "http " in detail:
        return "provider_rejected"
    return "unknown"


def _http_failure_category(status: int) -> str:
    if status in (401, 403):
        return "credentials"
    if status == 404:
        return "route_configuration"
    if status == 429:
        return "provider_rate_limited"
    if status in (500, 502, 503, 504):
        return "provider_transient"
    return "provider_rejected"


def _transport_failure_category(reason: Any) -> str:
    """Classify an OS transport error without treating it as model evidence."""
    seen: set[int] = set()
    current = reason
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, PermissionError) or getattr(current, "winerror", None) == 10013:
            return "local_environment"
        detail = str(current).casefold()
        if any(token in detail for token in (
            "winerror 10013", "socket in a way forbidden", "network access is disabled",
            "blocked by local policy", "operation not permitted",
        )):
            return "local_environment"
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return "provider_transport"


def synthetic_call_id() -> str:
    """An id for a tool call the server returned without one.

    A positional ``call_{i}`` repeats on every turn, so a walk's history held
    several calls named ``call_0`` and a tool result could pair with the wrong
    proposal.  A random id is unique within any walk; it is alphanumeric
    after the prefix, which the stricter tool-call id formats accept.
    """
    return "call_" + secrets.token_hex(8)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name, "arguments": self.arguments}


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    model: str = ""
    stop: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    request_id: str = ""
    reasoning_content: str = ""

    def message(self) -> dict[str, Any]:
        out: dict[str, Any] = {"role": "assistant", "content": self.text}
        if self.tool_calls:
            out["tool_calls"] = [c.to_dict() for c in self.tool_calls]
            # Some thinking-capable OpenAI-compatible routes require their
            # reasoning continuation to accompany a later tool-result turn.
            # It is deliberately held only in this in-memory model history:
            # Session persistence records person-visible text, never it.
            if self.reasoning_content:
                out["reasoning_content"] = self.reasoning_content
        return out


@dataclass(frozen=True)
class ToolDef:
    """A tool as a model is shown it: the registry's name, description and schema."""
    name: str
    description: str
    parameters: dict[str, Any]


class Provider:
    name = "provider"
    model = ""

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        raise NotImplementedError

    def chat_cancellable(self, system: str, messages: list[dict[str, Any]],
                         tools: list[ToolDef], max_tokens: int = 4096,
                         temperature: float | None = None,
                         cancel: threading.Event | None = None) -> Reply:
        """Compatibility entry point which preserves the historical chat ABI.

        Third-party providers get checks around their legacy call. First-party
        transports override this method and abort their active socket.
        """
        if cancel is not None and cancel.is_set():
            raise ProviderCancelledError()
        kwargs: dict[str, Any] = {"max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        reply = self.chat(system, messages, tools, **kwargs)
        if cancel is not None and cancel.is_set():
            raise ProviderCancelledError()
        return reply

    def models(self) -> list[str]:
        raise NotImplementedError

    def usage(self) -> dict[str, Any]:
        """Best-effort account usage or credit balance, read live, never
        cached or trusted for anything the vault does. Most providers have
        no such call on their inference API; those raise, and the settings
        page falls back to a link to the provider's own dashboard."""
        raise ProviderError(f"{self.name} has no usage endpoint")

    def check(self) -> dict[str, Any]:
        """For the Connections page: whether a key is saved, and what the
        listing says. Never the key."""
        key_env = getattr(self, "key_env", "")
        out: dict[str, Any] = {"provider": self.name,
                               "key": ("not needed" if not key_env else
                                       "present" if os.environ.get(key_env) else "missing")}
        try:
            listed = self.models()
        except ProviderError as exc:
            return {**out, "ok": False, "error": str(exc)[:300],
                    "failure_category": provider_failure_category(exc)}
        return {**out, "ok": True, "models": len(listed),
                "status": f"Connected: {len(listed)} models available"}


# ------------------------------------------------------------------- HTTP

# A model call that times out, cannot connect, or is told the model is busy is tried
# again after these pauses before the turn gives up (2026-10-02: one read timeout on
# DeepInfra ended the owner's turn, and the next call answered in under two seconds).
TRANSIENT_RETRIES = (3.0, 10.0)
TRANSIENT_HTTP = (429, 500, 502, 503, 504)   # 500: "Response payload is not completed"


class _CancellationHandle:
    """Abort one synchronous urllib call without moving it to a worker."""

    def __init__(self, cancel: threading.Event) -> None:
        self.cancel = cancel
        self.done = threading.Event()
        self._lock = threading.Lock()
        self._connection: http.client.HTTPConnection | None = None
        self._response: Any = None
        self._watcher = threading.Thread(
            target=self._watch, daemon=True, name="librarian-provider-cancel")

    def start(self) -> None:
        if self.cancel.is_set():
            raise ProviderCancelledError()
        self._watcher.start()

    def attach_connection(self, connection: http.client.HTTPConnection) -> None:
        with self._lock:
            if self.cancel.is_set():
                raise ProviderCancelledError()
            self._connection = connection

    def attach_response(self, response: Any) -> None:
        with self._lock:
            self._response = response
        if self.cancel.is_set():
            self._abort()
            raise ProviderCancelledError()

    def wait_readable(self, sock: Any, timeout: float | None) -> None:
        """Wait for socket input in bounded slices before a blocking read."""
        deadline = time.monotonic() + float(timeout or 120)
        while True:
            if self.cancel.is_set():
                raise ProviderCancelledError()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("timed out")
            try:
                readable, _, _ = select.select([sock], [], [], min(remaining, 0.05))
            except (OSError, ValueError):
                if self.cancel.is_set():
                    raise ProviderCancelledError()
                raise
            if readable:
                return

    @staticmethod
    def _shutdown(sock: Any) -> None:
        if sock is None:
            return
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except (AttributeError, OSError):
            pass
        try:
            sock.close()
        except (AttributeError, OSError):
            pass

    def _abort(self) -> None:
        with self._lock:
            connection, response = self._connection, self._response
        self._shutdown(getattr(connection, "sock", None))
        fp = getattr(response, "fp", None)
        raw = getattr(fp, "raw", None)
        self._shutdown(getattr(raw, "_sock", None))
        try:
            if response is not None:
                response.close()
        except (OSError, ValueError):
            pass
        try:
            if connection is not None:
                connection.close()
        except OSError:
            pass

    def _watch(self) -> None:
        while not self.done.wait(0.05):
            if self.cancel.is_set():
                self._abort()
                return

    def finish(self) -> None:
        self.done.set()
        if self._watcher.is_alive():
            self._watcher.join()
        with self._lock:
            self._connection = None
            self._response = None


class _CancellableHTTPConnection(http.client.HTTPConnection):
    def __init__(self, host: str, handle: _CancellationHandle, **kwargs: Any) -> None:
        self._cancel_handle = handle
        super().__init__(host, **kwargs)

    def getresponse(self) -> http.client.HTTPResponse:
        if self.sock is not None:
            self._cancel_handle.wait_readable(self.sock, self.timeout)
        return super().getresponse()


class _CancellableHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, handle: _CancellationHandle, **kwargs: Any) -> None:
        self._cancel_handle = handle
        super().__init__(host, **kwargs)

    def getresponse(self) -> http.client.HTTPResponse:
        if self.sock is not None:
            self._cancel_handle.wait_readable(self.sock, self.timeout)
        return super().getresponse()


class _CancellableHTTPHandler(urllib.request.HTTPHandler):
    def __init__(self, handle: _CancellationHandle) -> None:
        super().__init__()
        self.handle = handle

    def http_open(self, req: Any) -> Any:
        def factory(host: str, **kwargs: Any) -> http.client.HTTPConnection:
            connection = _CancellableHTTPConnection(host, self.handle, **kwargs)
            self.handle.attach_connection(connection)
            return connection
        return self.do_open(factory, req)


class _CancellableHTTPSHandler(urllib.request.HTTPSHandler):
    def __init__(self, handle: _CancellationHandle) -> None:
        super().__init__()
        self.handle = handle

    def https_open(self, req: Any) -> Any:
        def factory(host: str, **kwargs: Any) -> http.client.HTTPSConnection:
            connection = _CancellableHTTPSConnection(host, self.handle, **kwargs)
            self.handle.attach_connection(connection)
            return connection
        return self.do_open(factory, req, context=self._context,
                            check_hostname=self._check_hostname)


def _open_cancellable(request: urllib.request.Request, timeout: float,
                      cancel: threading.Event) -> tuple[Any, _CancellationHandle]:
    handle = _CancellationHandle(cancel)
    handle.start()
    try:
        opener = urllib.request.build_opener(
            _CancellableHTTPHandler(handle), _CancellableHTTPSHandler(handle))
        response = opener.open(request, timeout=timeout)
        handle.attach_response(response)
        return response, handle
    except urllib.error.HTTPError as error:
        # HTTPError is also the response object. Keep its body read
        # cancellable while the caller classifies the status and extracts the
        # bounded diagnostic detail.
        try:
            handle.attach_response(error)
        except BaseException:
            handle.finish()
            raise
        setattr(error, "_librarian_cancel_handle", handle)
        raise
    except BaseException:
        handle.finish()
        if cancel.is_set():
            raise ProviderCancelledError()
        raise


def _retry_pause(seconds: float, sleep: Any,
                 cancel: threading.Event | None) -> None:
    if cancel is None:
        if sleep is None:
            time.sleep(seconds)
        else:
            sleep(seconds)
        return
    if sleep is not None:
        sleep(seconds)
        if cancel.is_set():
            raise ProviderCancelledError()
    elif cancel.wait(seconds):
        raise ProviderCancelledError()


def _read_cancellable(response: Any, handle: _CancellationHandle,
                      timeout: float) -> bytes:
    """Read a response in readiness-bounded chunks without a reader worker."""
    chunks: list[bytes] = []
    while True:
        fp = getattr(response, "fp", None)
        raw = getattr(fp, "raw", None)
        sock = getattr(raw, "_sock", None)
        if sock is not None:
            handle.wait_readable(sock, timeout)
        if handle.cancel.is_set():
            raise ProviderCancelledError()
        chunk = response.read1(64 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _request(method: str, url: str, headers: dict[str, str], body: Any = None,
             timeout: float = 120, sleep: Any = None,
             retries: tuple[float, ...] | None = None,
             cancel: threading.Event | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    # A caller with its own recovery (Clerk's schema fallback) passes ().
    pauses = list(TRANSIENT_RETRIES if retries is None else retries)
    while True:
        request = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": "application/json",
                                                  **headers})
        handle: _CancellationHandle | None = None
        try:
            if cancel is not None:
                response, handle = _open_cancellable(request, timeout, cancel)
            else:
                response = urllib.request.urlopen(request, timeout=timeout)
            with response:
                raw_body = (_read_cancellable(response, handle, timeout)
                            if handle is not None else response.read())
                decoded = json.loads(raw_body.decode("utf-8"))
                if cancel is not None and cancel.is_set():
                    raise ProviderCancelledError()
                if isinstance(decoded, dict):
                    return _ResponsePayload(decoded, _response_request_id(
                        getattr(response, "headers", None)))
                return decoded
        except ProviderCancelledError:
            raise
        except urllib.error.HTTPError as exc:
            if handle is None:
                handle = getattr(exc, "_librarian_cancel_handle", None)
            error_body = (_read_cancellable(exc, handle, timeout)
                          if isinstance(handle, _CancellationHandle) else exc.read())
            detail = error_body.decode("utf-8", "replace")[:400]
            if exc.code in TRANSIENT_HTTP and pauses:
                _retry_pause(pauses.pop(0), sleep, cancel)
                continue
            raise ProviderError(f"HTTP {exc.code} from {url}: {detail}",
                                category=_http_failure_category(exc.code)) from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            # A refused connection is a server that is not running (a local model): asking
            # again only waits. A timeout or a dropped connection is worth another try.
            reason = getattr(exc, "reason", exc)
            if pauses and isinstance(reason, (TimeoutError, ConnectionResetError,
                                              ConnectionAbortedError)):
                _retry_pause(pauses.pop(0), sleep, cancel)
                continue
            if isinstance(reason, TimeoutError):
                # Reached, but slow (2026-10-02): "not reachable" sent the person to check
                # their key when the model was simply busy.
                raise ProviderError(f"the model did not answer within {int(timeout)} seconds "
                                    f"({len(TRANSIENT_RETRIES) + 1} tries): the provider is slow "
                                    f"or busy right now - try again shortly, or choose another "
                                    f"model", category="provider_transient") from exc
            raise ProviderError(f"{url} is not reachable: {exc}",
                                category=_transport_failure_category(reason)) from exc
        finally:
            if handle is not None:
                handle.finish()


def _key(key_env: str) -> str:
    if not key_env:
        return ""
    key = os.environ.get(key_env, "")
    if not key:
        raise ProviderError(f"{key_env} is not set", category="credentials")
    return key


# ----------------------------------------------------------- OpenAI-compatible

class OpenAICompatible(Provider):
    def __init__(self, base_url: str, model: str = "", key_env: str = "", name: str = "",
                 timeout: float = 120):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.key_env = key_env
        self.name = name or self.base_url
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        key = _key(self.key_env)
        return {"Authorization": f"Bearer {key}"} if key else {}

    def models(self) -> list[str]:
        listing = _request("GET", f"{self.base_url}/models", self._headers(),
                           timeout=self.timeout)
        return sorted(str(m.get("id")) for m in listing.get("data") or [] if m.get("id"))

    def usage(self) -> dict[str, Any]:
        if self.name != "deepinfra":
            raise ProviderError(f"no usage endpoint is known for {self.name}")
        return _request("GET", _DEEPINFRA_BALANCE, self._headers(), timeout=self.timeout)

    @staticmethod
    def wire_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Thin delegation kept so existing callers (OpenAICompatible.wire_messages)
        # continue to work without importing the adapter directly.
        from .adapters.openai_chat import OpenAIChatAdapter
        return OpenAIChatAdapter.wire_messages(system, messages)

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        return self.chat_cancellable(system, messages, tools, max_tokens=max_tokens,
                                     temperature=temperature)

    def chat_cancellable(self, system: str, messages: list[dict[str, Any]],
                         tools: list[ToolDef], max_tokens: int = 4096,
                         temperature: float | None = None,
                         cancel: threading.Event | None = None) -> Reply:
        if not self.model:
            raise ProviderError(f"no model chosen for {self.name}", category="route_configuration")
        # Import inside the method to avoid a circular import at module level.
        from .adapters.openai_chat import OpenAIChatAdapter
        body = OpenAIChatAdapter.render(self.model, system, messages, tools,
                                        max_tokens=max_tokens, temperature=temperature)
        from .adapters.openai_chat import chat_url
        if cancel is None:
            reply = _request("POST", chat_url(self.base_url), self._headers(), body, self.timeout)
        else:
            reply = _request("POST", chat_url(self.base_url), self._headers(), body,
                             self.timeout, cancel=cancel)
        return OpenAIChatAdapter.parse(reply)


# ------------------------------------------------------------------ Anthropic

class Anthropic(Provider):
    def __init__(self, model: str = "", key_env: str = "ANTHROPIC_API_KEY",
                 base_url: str = PRESETS["anthropic"]["base_url"], name: str = "anthropic",
                 timeout: float = 120):
        self.model = model
        self.key_env = key_env
        self.base_url = base_url.rstrip("/")
        self.name = name
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": _key(self.key_env), "anthropic-version": ANTHROPIC_VERSION}

    def models(self) -> list[str]:
        listing = _request("GET", f"{self.base_url}/models?limit=1000", self._headers(),
                           timeout=self.timeout)
        return sorted(str(m.get("id")) for m in listing.get("data") or [] if m.get("id"))

    @staticmethod
    def wire_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Kept for existing callers; the adapter owns the wire shape (ADAPT-05).
        from .adapters.anthropic_messages import AnthropicMessagesAdapter
        return AnthropicMessagesAdapter.wire_messages(messages)

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        return self.chat_cancellable(system, messages, tools, max_tokens=max_tokens,
                                     temperature=temperature)

    def chat_cancellable(self, system: str, messages: list[dict[str, Any]],
                         tools: list[ToolDef], max_tokens: int = 4096,
                         temperature: float | None = None,
                         cancel: threading.Event | None = None) -> Reply:
        if not self.model:
            raise ProviderError("no Anthropic model chosen", category="route_configuration")
        from .adapters.anthropic_messages import AnthropicMessagesAdapter
        body = AnthropicMessagesAdapter.render(self.model, system, messages, tools,
                                               max_tokens, temperature)
        if cancel is None:
            reply = _request("POST", f"{self.base_url}/messages", self._headers(), body,
                             self.timeout)
        else:
            reply = _request("POST", f"{self.base_url}/messages", self._headers(), body,
                             self.timeout, cancel=cancel)
        return AnthropicMessagesAdapter.parse(reply)


# ------------------------------------------------------------------ scripted

class Scripted(Provider):
    """A function standing in for a model: `answer(system, messages, tools)`
    returns a `Reply`. Tests and replays."""

    def __init__(self, answer: Callable[[str, list[dict[str, Any]], list[ToolDef]], Reply],
                 name: str = "scripted"):
        self.answer = answer
        self.name = name
        self.model = name
        self.calls: list[dict[str, Any]] = []

    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolDef],
             max_tokens: int = 4096, temperature: float | None = None) -> Reply:
        self.calls.append({"system": system, "messages": [dict(m) for m in messages],
                           "tools": [t.name for t in tools]})
        return self.answer(system, messages, tools)

    def models(self) -> list[str]:
        return [self.name]


def from_settings(settings: dict[str, Any]) -> Provider | None:
    """`{provider: "deepinfra", model: "..."}`, with any preset value
    overridable (`base_url`, `key_env`)."""
    provider = str(settings.get("provider") or "")
    if not provider:
        return None
    if provider not in PRESETS and not settings.get("base_url"):
        raise ProviderError(f"unknown provider {provider!r}; one of {sorted(PRESETS)}, "
                            f"or give a base_url", category="route_configuration")
    base = {**PRESETS.get(provider, {"protocol": "openai"}),
            **{k: v for k, v in settings.items() if k in ("base_url", "key_env", "protocol")}}
    try:
        timeout = max(1.0, min(float(settings.get("timeout") or 120), 3600.0))
    except (TypeError, ValueError):
        timeout = 120.0
    model = str(settings.get("model") or "")
    if base["protocol"] == "anthropic":
        return Anthropic(model, base["key_env"], base["base_url"], provider, timeout=timeout)
    return OpenAICompatible(base["base_url"], model, base["key_env"], provider, timeout=timeout)
