"""REMED-05, durable per-call accounting for paid evaluation (Codex review F6).

Every HTTP attempt to a paid provider, retries included, holds a reservation
on the shared delegation ledger before it is sent, and is settled from what
came back. A crash, a retry, a timeout or a reply without usage leaves the
ledger correct and spends nothing further. Driven through the real
`providers._request` against a local server."""
from __future__ import annotations

import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from resource_librarian import providers

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("g5_measure", SCRIPTS / "g5_measure.py")
g5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g5)

CARD = {"input_per_1m": 1.0, "output_per_1m": 1.0}
BODY = {"model": "m", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 100}
USAGE = {"prompt_tokens": 10, "completion_tokens": 5}


class Server:
    """Answers each POST with the next scripted (status, body, delay)."""

    def __init__(self, script):
        self.script, self.hits = list(script), 0
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):          # noqa: N802
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                server.hits += 1
                status, body, delay = server.script.pop(0)
                time.sleep(delay)
                data = json.dumps(body).encode()
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except OSError:
                    pass                # the client gave up (a timeout test)

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}/v1/chat/completions"
        threading.Thread(target=self.http.serve_forever, daemon=True).start()

    def close(self):
        self.http.shutdown()
        self.http.server_close()


@pytest.fixture
def serve():
    servers = []

    def make(*script):
        servers.append(Server(script))
        return servers[-1]

    yield make
    for server in servers:
        server.close()


@pytest.fixture
def gate(tmp_path):
    gates = []

    def make(cap=8.0, run="run-1", run_budget=None, call_cap=0.25):
        made = g5.PaidDispatch(tmp_path / "ledger.json", cap, CARD, model="m", run=run,
                               task="t", run_budget=run_budget, call_cap=call_cap,
                               host="127.0.0.1")
        gates.append(made)
        providers.set_dispatch_gate(made)
        return made

    yield make
    providers.set_dispatch_gate(None)


def calls(tmp_path):
    path = tmp_path / "ledger.json"
    return json.loads(path.read_text(encoding="utf-8"))["calls"] if path.exists() else []


def send(server, body=BODY, timeout=5.0, retries=()):
    return providers._request("POST", server.url, {}, body, timeout=timeout, retries=retries,
                              sleep=lambda _: None)


def reserve_for(body=BODY):
    sent = len(json.dumps(body).encode("utf-8"))
    return (sent * CARD["input_per_1m"] + body["max_tokens"] * CARD["output_per_1m"]) / 1e6


# --- a call is reserved before it is sent and settled from its usage ----------------

def test_a_metered_call_is_reserved_then_charged_its_usage(tmp_path, serve, gate):
    server = serve((200, {"choices": [], "usage": USAGE}, 0))
    gate()
    send(server)
    [entry] = calls(tmp_path)
    assert entry["status"] == "completed" and entry["cost_basis"] == "metered_estimate"
    assert entry["charged_usd"] == pytest.approx(15 / 1e6)
    assert entry["reserve_usd"] == pytest.approx(reserve_for())
    assert entry["request_sha256"] and entry["pool"] == "g5"


def test_each_retry_is_its_own_reservation(tmp_path, serve, gate):
    server = serve((503, {"error": "busy"}, 0), (200, {"usage": USAGE}, 0))
    gate()
    send(server, retries=(0.0,))
    first, second = calls(tmp_path)
    assert server.hits == 2
    # The 503 was answered without processing: the delegation rule charges nothing.
    assert (first["status"], first["charged_usd"]) == ("failed", 0.0)
    assert second["status"] == "completed"


# --- unknown cost keeps its reservation and stops spending ----------------------------

def test_a_timeout_keeps_its_reservation_and_sends_nothing_more(tmp_path, serve, gate):
    server = serve((200, {"usage": USAGE}, 1.5), (200, {"usage": USAGE}, 0))
    paid = gate()
    with pytest.raises(providers.ProviderError, match="G5 budget"):
        send(server, timeout=0.3, retries=(0.0,))          # the retry is refused unsent
    [entry] = calls(tmp_path)
    assert server.hits == 1
    assert entry["status"] == "uncertain" and entry["charged_usd"] == pytest.approx(reserve_for())
    assert "outcome is unknown" in paid.blocked


def test_a_reply_without_usage_is_charged_its_reservation_and_stops_the_run(tmp_path, serve,
                                                                            gate):
    server = serve((200, {"choices": []}, 0), (200, {"usage": USAGE}, 0))
    paid = gate()
    send(server)
    with pytest.raises(providers.ProviderError, match="no usage"):
        send(server)
    [entry] = calls(tmp_path)
    assert server.hits == 1 and entry["status"] == "uncertain"
    assert entry["charged_usd"] == pytest.approx(reserve_for())
    assert "no usage" in paid.blocked


def test_a_crash_between_reserve_and_settle_keeps_the_charge(tmp_path, serve, gate):
    sent = len(json.dumps(BODY).encode("utf-8"))
    gate().before("POST", "http://127.0.0.1/x", BODY, sent)       # then the process dies
    server = serve((200, {"usage": USAGE}, 0))
    gate()                                                         # a new process
    with pytest.raises(providers.ProviderError, match="still in flight|reconcile"):
        send(server)                                              # the same request again
    [entry] = calls(tmp_path)
    assert server.hits == 0
    assert entry["status"] == "started" and entry["charged_usd"] == pytest.approx(reserve_for())
    assert g5.committed(tmp_path / "ledger.json", 8.0) == pytest.approx(reserve_for())


# --- the caps refuse before anything is sent -------------------------------------------

def test_the_pool_cap_refuses_a_call_unsent(tmp_path, serve, gate):
    server = serve((200, {"usage": USAGE}, 0))
    gate(cap=reserve_for() / 2)
    with pytest.raises(providers.ProviderError, match="refused the reservation"):
        send(server)
    assert server.hits == 0 and calls(tmp_path) == []


def test_a_runs_budget_is_a_cap_of_its_own(tmp_path, serve, gate):
    server = serve((200, {"usage": USAGE}, 0))
    gate(run_budget=reserve_for() / 2)
    with pytest.raises(providers.ProviderError, match="task budget"):
        send(server)
    assert server.hits == 0


def test_two_runs_share_one_pool(tmp_path, serve, gate):
    server = serve((200, {"usage": USAGE}, 0))
    sent = len(json.dumps(BODY).encode("utf-8"))
    gate(cap=reserve_for() * 1.5, run="run-a").before("POST", server.url, BODY, sent)
    gate(cap=reserve_for() * 1.5, run="run-b")       # another run, concurrently
    with pytest.raises(providers.ProviderError, match="exceed total budget"):
        send(server, body={**BODY, "messages": [{"role": "user", "content": "other"}]})
    assert server.hits == 0


def test_a_model_request_without_max_tokens_is_refused(tmp_path, serve, gate):
    server = serve((200, {"usage": USAGE}, 0))
    gate()
    with pytest.raises(providers.ProviderError, match="max_tokens"):
        send(server, body={"model": "m", "messages": []})
    assert server.hits == 0


def test_a_request_to_another_endpoint_is_refused(tmp_path, gate):
    paid = gate()
    with pytest.raises(providers.ProviderError, match="no rate card"):
        paid.before("POST", "https://api.other.example/v1/chat", BODY, 10)


def test_a_request_without_a_body_is_not_a_model_call(tmp_path, gate):
    assert gate().before("GET", "http://127.0.0.1/models", None, 0) is None
    assert calls(tmp_path) == []


# --- one ledger policy: the first G5 ledger moves onto the shared one ------------------

def test_the_first_g5_ledger_is_adopted_with_its_spend(tmp_path):
    old = tmp_path / "ledger.json"
    old.write_text(json.dumps({"cap_usd": 8.0, "spent_usd": 0.75, "entries": [
        {"label": "pilot", "usd": 0.25}, {"label": "full", "usd": 0.5}]}), encoding="utf-8")
    kept = old.read_bytes()
    g5.adopt_ledger(old, 8.0)
    assert g5.committed(old, 8.0) == pytest.approx(0.75)
    assert (tmp_path / "ledger.g5v1.json").read_bytes() == kept
    assert json.loads(old.read_text(encoding="utf-8"))["schema"] == 2
    g5.adopt_ledger(old, 8.0)                                     # already adopted: no change
    assert g5.committed(old, 8.0) == pytest.approx(0.75)


def test_adoption_refuses_a_different_cap_or_a_bad_sum(tmp_path):
    old = tmp_path / "ledger.json"
    old.write_text(json.dumps({"cap_usd": 8.0, "spent_usd": 1.0, "entries": [
        {"label": "a", "usd": 0.25}]}), encoding="utf-8")
    with pytest.raises(SystemExit, match="cap"):
        g5.adopt_ledger(old, 9.0)
    with pytest.raises(SystemExit, match="do not add up"):
        g5.adopt_ledger(old, 8.0)
    assert "cap_usd" in json.loads(old.read_text(encoding="utf-8"))   # left as it was
