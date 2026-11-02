"""REMED-07: exact wire size of long audited-session model requests.

The Manager projection is bounded, but it does not replace the conversation
history sent to a model.  These fixtures exercise both first-party chat
adapters through the real HTTP serializer, without an external or paid call.
"""
from __future__ import annotations

import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from resource_librarian.loop import Loop
from resource_librarian.providers import (Anthropic, DispatchGate, OpenAICompatible,
                                          set_dispatch_gate)
from resource_librarian.session import SessionStore


FIRST = "REMED07-FIRST-HISTORY-MARKER"
FINAL = "REMED07-FINAL-REQUEST-MARKER"


class _CaptureGate(DispatchGate):
    """Keep qualification metadata only; never retain a model request body."""

    def __init__(self, first: str, last: str) -> None:
        self.first, self.last = first, last
        self.rows: list[dict] = []

    def before(self, method, url, body, sent_bytes):
        encoded = json.dumps(body).encode("utf-8")
        assert sent_bytes == len(encoded)
        rendered = encoded.decode("utf-8")
        self.rows.append({
            "method": method,
            "endpoint": url.rsplit("/", 1)[-1],
            "sent_bytes": sent_bytes,
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "messages": len(body.get("messages") or []),
            "first_retained": self.first in rendered,
            "last_retained": self.last in rendered,
            "final_retained": FINAL in rendered,
        })
        return len(self.rows) - 1


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.receipts: list[dict] = []


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:  # noqa: N802
        server: _Server = self.server  # type: ignore[assignment]
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        server.receipts.append({
            "sent_bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        })
        if self.path.endswith("/messages"):
            reply = {"model": "qualification-model", "stop_reason": "end_turn",
                     "content": [{"type": "text", "text": "ok"}],
                     "usage": {"input_tokens": 1, "output_tokens": 1}}
        else:
            reply = {"model": "qualification-model", "choices": [{
                "finish_reason": "stop", "message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
        encoded = json.dumps(reply).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


@pytest.fixture(scope="module")
def provider_server():
    server = _Server()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


def _audited_history(vault, rounds: int) -> tuple[str, list[dict[str, str]], str]:
    store = SessionStore(vault)
    sid = store.new("audited", question="Qualify the real long-session model view").id
    last = ""
    for number in range(1, rounds + 1):
        user = FIRST if number == 1 else f"REMED07-USER-{number:02d}"
        last = f"REMED07-LAST-{number:02d}"
        store.append(sid, {"type": "message", "role": "user",
                           "text": user + " " + ("u" * 96)})
        store.append(sid, {"type": "message", "role": "assistant",
                           "text": last + " " + ("a" * 96)})
    return sid, store.load(sid).messages, last


def _measure(vault, server: _Server, protocol: str, rounds: int) -> dict:
    sid, history, last = _audited_history(vault, rounds)
    base = f"http://127.0.0.1:{server.server_address[1]}/v1"
    provider = (OpenAICompatible(base, model="qualification-model")
                if protocol == "openai" else
                Anthropic(model="qualification-model", key_env="", base_url=base))
    loop = Loop(vault, provider, extras={"agent_profile": "lead"}, max_steps=1)
    loop.ctx.session = sid
    loop.restore(history)
    gate = _CaptureGate(FIRST, last)
    receipt_at = len(server.receipts)
    previous = set_dispatch_gate(gate)
    try:
        turn = loop.send(FINAL)
    finally:
        set_dispatch_gate(previous)

    assert turn.reply == "ok" and not turn.error
    assert len(gate.rows) == 1 and len(server.receipts) == receipt_at + 1
    measured, received = gate.rows[0], server.receipts[-1]
    assert measured["sent_bytes"] == received["sent_bytes"]
    assert measured["sha256"] == received["sha256"]
    assert measured["first_retained"] and measured["last_retained"]
    assert measured["final_retained"]

    # Invocation evidence is deliberately redacted: request content and the
    # body digest above are measurement-local, not a new prompt log.
    trace = json.dumps(loop._private_runtime.recent(), default=str)
    assert FIRST not in trace and last not in trace and FINAL not in trace
    assert measured["sha256"] not in trace
    return {"protocol": protocol, "rounds": rounds,
            "sent_bytes": measured["sent_bytes"], "messages": measured["messages"]}


def test_exact_request_size_over_long_audited_histories(vault, provider_server):
    rows = [_measure(vault, provider_server, protocol, rounds)
            for protocol in ("openai", "anthropic") for rounds in (1, 10, 50)]

    for protocol in ("openai", "anthropic"):
        sizes = [row["sent_bytes"] for row in rows if row["protocol"] == protocol]
        assert sizes[0] < sizes[1] < sizes[2]

    # `pytest -s` makes this deterministic evidence table visible for the
    # qualification report; ordinary suite runs retain their normal capture.
    print(json.dumps(rows, indent=2))
