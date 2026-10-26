"""ADAPT-04B transport and host-limiter cancellation boundaries."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from resource_librarian.hosts import Host, HostLimiter, LimitedProvider
from resource_librarian.loop import Loop
from resource_librarian.model_invocation import InvocationPayload, InvocationRuntime
from resource_librarian.providers import (
    Anthropic,
    OpenAICompatible,
    Provider,
    ProviderCancelledError,
    ProviderError,
    Reply,
)


class _ProviderServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.requests = 0


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        server: _ProviderServer = self.server  # type: ignore[assignment]
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        server.requests += 1
        server.entered.set()
        if self.path.startswith("/slow/"):
            server.release.wait(5)
        if self.path.endswith("/messages"):
            body = {"model": "m", "stop_reason": "end_turn",
                    "content": [{"type": "text", "text": "ok"}]}
        else:
            body = {"model": "m", "choices": [{"finish_reason": "stop",
                                                  "message": {"content": "ok"}}]}
        encoded = json.dumps(body).encode("utf-8")
        try:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


@pytest.fixture
def provider_server():
    server = _ProviderServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        thread.join(5)


def _base(server: _ProviderServer, prefix: str = "") -> str:
    return f"http://127.0.0.1:{server.server_address[1]}{prefix}"


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
def test_first_party_transport_aborts_a_slow_request(kind, provider_server) -> None:
    provider = (OpenAICompatible(_base(provider_server, "/slow/v1"), model="m")
                if kind == "openai" else
                Anthropic(model="m", key_env="", base_url=_base(provider_server, "/slow/v1")))
    cancel = threading.Event()
    failures: list[BaseException] = []

    def call() -> None:
        try:
            provider.chat_cancellable("system", [{"role": "user", "content": "hello"}], [],
                                      cancel=cancel)
        except BaseException as exc:
            failures.append(exc)

    worker = threading.Thread(target=call)
    worker.start()
    assert provider_server.entered.wait(3)
    started = time.monotonic()
    cancel.set()
    worker.join(1)

    assert not worker.is_alive()
    assert time.monotonic() - started < 1
    assert len(failures) == 1
    assert isinstance(failures[0], ProviderCancelledError)
    assert failures[0].category == "cancelled"
    assert not [t for t in threading.enumerate()
                if t.name == "librarian-provider-cancel" and t.is_alive()]


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
def test_uncancelled_first_party_transport_keeps_normal_reply_semantics(kind, provider_server) -> None:
    provider = (OpenAICompatible(_base(provider_server, "/v1"), model="m")
                if kind == "openai" else
                Anthropic(model="m", key_env="", base_url=_base(provider_server, "/v1")))

    reply = provider.chat_cancellable(
        "system", [{"role": "user", "content": "hello"}], [], cancel=threading.Event())

    assert reply.text == "ok" and reply.model == "m"
    assert provider_server.requests == 1


def test_an_already_cancelled_transport_never_contacts_the_server(provider_server) -> None:
    cancel = threading.Event()
    cancel.set()
    provider = OpenAICompatible(_base(provider_server, "/v1"), model="m")

    with pytest.raises(ProviderCancelledError):
        provider.chat_cancellable("system", [], [], cancel=cancel)

    assert provider_server.requests == 0


def _host() -> Host:
    return Host("cancel-host", "Cancel host", "openai", "https://example.invalid/v1",
                timeout=2, concurrency_limit=1).normalise()


def test_cancel_while_waiting_for_host_capacity_does_not_leak_a_slot() -> None:
    limiter, host = HostLimiter(), _host()
    occupied, release = threading.Event(), threading.Event()

    def hold() -> str:
        occupied.set()
        release.wait(5)
        return "first"

    first = threading.Thread(target=limiter.run, args=(host, hold))
    first.start()
    assert occupied.wait(3)
    cancel = threading.Event()
    threading.Timer(0.1, cancel.set).start()

    with pytest.raises(ProviderCancelledError):
        limiter.run(host, lambda: "must not run", cancel=cancel)

    release.set()
    first.join(3)
    assert not first.is_alive()
    assert limiter.run(host, lambda: "next") == "next"
    assert limiter._limit(host).interactive == 0


class _TransientProvider(Provider):
    name = model = "transient"

    def __init__(self) -> None:
        self.calls = 0
        self.called = threading.Event()

    def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
        self.calls += 1
        self.called.set()
        raise ProviderError("HTTP 503: busy", category="provider_transient")


def test_cancel_interrupts_limited_provider_retry_backoff() -> None:
    provider = _TransientProvider()
    limited = LimitedProvider(provider, _host(), HostLimiter())
    cancel = threading.Event()
    threading.Timer(0.1, cancel.set).start()

    with pytest.raises(ProviderCancelledError):
        limited.chat_cancellable("system", [], [], cancel=cancel)

    assert provider.calls == 1
    state = limited.limiter._limit(limited.host)
    assert state.interactive == 0
    assert state.transient_failures == 1


class _FourArgumentProvider(Provider):
    name = model = "legacy"

    def chat(self, system, messages, tools, max_tokens=4096):
        return Reply(text="legacy", model=self.model)


def test_default_cancellable_entry_point_preserves_four_argument_providers() -> None:
    reply = _FourArgumentProvider().chat_cancellable(
        "system", [], [], cancel=threading.Event())
    assert reply.text == "legacy"


def test_invocation_runtime_records_a_typed_nonretryable_cancellation() -> None:
    cancel = threading.Event()
    cancel.set()
    runtime = InvocationRuntime(id_factory=lambda: "cancel-plan")

    with pytest.raises(ProviderCancelledError):
        runtime.invoke(_FourArgumentProvider(),
                       InvocationPayload.from_legacy("system", [], []), cancel=cancel)

    result = runtime.recent()[-1]["result"]
    assert result["outcome"] == "cancelled"
    assert result["failure"] == {
        "category": "cancelled", "retryable": False,
        "message": "the provider request was cancelled"}


def test_loop_maps_provider_cancellation_to_a_stop_not_an_error(vault) -> None:
    entered = threading.Event()

    class WaitingProvider(Provider):
        name = model = "waiting"

        def chat(self, system, messages, tools, max_tokens=4096, temperature=None):
            raise AssertionError("the runtime must use the cancellable entry point")

        def chat_cancellable(self, system, messages, tools, max_tokens=4096,
                             temperature=None, cancel=None):
            entered.set()
            assert cancel is not None
            assert cancel.wait(3)
            raise ProviderCancelledError()

    cancel = threading.Event()
    events = []
    loop = Loop(vault, WaitingProvider(), on_event=events.append)
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    try:
        turn = loop.send("hello", cancel=cancel)
    finally:
        timer.cancel()

    assert entered.is_set()
    assert turn.stopped == "cancelled" and not turn.error and not turn.reply
    assert events[-1] == {"type": "stopped", "reason": "cancelled"}
    assert not [event for event in events if event["type"] == "error"]
    assert loop.messages == [{"role": "user", "content": "hello"}]
