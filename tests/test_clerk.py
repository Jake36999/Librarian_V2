import inspect
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from resource_librarian import clerk
from resource_librarian.evidence import FRAMING_KEYS

README = ("osquery exposes the operating system as a relational database. You write SQL "
          "queries against tables such as processes and listening_ports. It runs as a "
          "daemon on Linux, macOS and Windows.")


def test_no_constructor_can_accept_framing():
    """M4 acceptance: no clerk task payload can contain a project, brief or session."""
    forbidden = FRAMING_KEYS - {"need", "disqualifiers", "topic"} | {"project", "brief",
                                                                      "session", "context"}
    for name, build in clerk.CONSTRUCTORS.items():
        params = set(inspect.signature(build).parameters)
        assert not params & forbidden, (name, params & forbidden)
    framed_allowed = {"screen": {"need", "disqualifiers"}, "fit": {"need", "disqualifiers"},
                      "relevance": {"topic"}, "queries": {"need"}}
    for name, build in clerk.CONSTRUCTORS.items():
        params = set(inspect.signature(build).parameters)
        assert params & {"need", "disqualifiers", "topic"} <= framed_allowed.get(name, set())


def test_payload_is_exactly_the_task():
    task = clerk.mechanics(README)
    payload = task.payload()
    assert set(payload) == clerk.PAYLOAD_KEYS
    assert README in payload["user"]
    text = json.dumps(payload).lower()
    for framing in ("catalogue", "library", "session", "brief", "vault", "our", "we"):
        assert not re.search(rf"\b{framing}\b", text), framing


def scripted(reply):
    return clerk.Scripted(lambda payload: reply)


def test_bullets_are_grounded_and_ungrounded_dropped():
    result = clerk.run_one(clerk.mechanics(README), scripted({"bullets": [
        "Exposes the operating system as relational tables queried with SQL",
        "Uses a quantum annealer to accelerate blockchain consensus"]}))
    assert result.ok and len(result.value["bullets"]) == 1
    assert "quantum" in result.dropped[0]


def test_screen_reject_without_real_quote_becomes_unclear():
    task = clerk.screen(README, "host inventory", ["requires a GPU"])
    result = clerk.run_one(task, scripted({"verdict": "reject", "reason": "needs GPU",
                                           "contradicts": ["requires an NVIDIA GPU"]}))
    assert result.value["verdict"] == "unclear"
    real = clerk.run_one(task, scripted({"verdict": "reject", "reason": "Windows",
                                         "contradicts": ["runs as a daemon on Linux"]}))
    assert real.value["verdict"] == "reject"


def test_fit_with_unverifiable_quote_becomes_uncertain():
    task = clerk.fit(README, "query host state", [])
    result = clerk.run_one(task, scripted({"recommendation": "fits", "reason": "r",
                                           "evidence_quote": "a query engine for hosts"}))
    assert result.value["recommendation"] == "uncertain"


def test_not_confident_is_dropped():
    result = clerk.run_one(clerk.axis("maturity", ["Active", "Abandoned"], README),
                           scripted({"value": "Active", "confident": False}))
    assert result.status == "not_confident"


def test_repair_then_refuse():
    replies = iter(['{"bullets": "not a list"}', '{"bullets": ["runs as a daemon"]}'])
    result = clerk.run_one(clerk.uses(README), clerk.Scripted(lambda p: next(replies)))
    assert result.ok and result.attempts == 2
    bad = clerk.run_one(clerk.uses(README), scripted("I think it is a database tool"))
    assert bad.status == "refused" and "no JSON" in bad.problems


def test_terms_must_appear_in_their_sentence():
    result = clerk.run_one(clerk.terms(README), scripted({"terms": [
        {"term": "relational database", "sentence": "osquery exposes the operating system "
                                                    "as a relational database."},
        {"term": "eBPF", "sentence": "It uses eBPF probes."}]}))
    assert [t["term"] for t in result.value["terms"]] == ["relational database"]


def test_no_endpoint_queues_and_never_falls_back(tmp_path):
    results = clerk.run([clerk.uses(README)], None, tmp_path / "q")
    assert results[0].status == "queued" and len(list((tmp_path / "q").iterdir())) == 1
    queued = json.loads(next((tmp_path / "q").iterdir()).read_text())
    assert set(queued) == clerk.PAYLOAD_KEYS


def test_concurrency_preserves_order():
    endpoint = clerk.Scripted(lambda p: {"bullets": []}, concurrency=4)
    tasks = [clerk.uses(f"text {i}") for i in range(10)]
    results = clerk.run(tasks, endpoint)
    assert [r.task_id for r in results] == [t.id for t in tasks]


class _Fake(BaseHTTPRequestHandler):
    seen: list = []

    def do_POST(self):                                      # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _Fake.seen.append({"auth": self.headers.get("Authorization"), "body": body})
        if "response_format" in body:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"error": "response_format json_schema is not supported"}')
            return
        reply = {"model": body["model"], "choices": [{"message": {
            "content": json.dumps({"bullets": ["runs as a daemon on Linux"]})}}]}
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(reply).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_server():
    server = HTTPServer(("127.0.0.1", 0), _Fake)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _Fake.seen = []
    yield f"http://127.0.0.1:{server.server_address[1]}/v1"
    server.shutdown()


def test_openai_compatible_endpoint(fake_server, monkeypatch):
    monkeypatch.setenv("TEST_KEY", "secret")
    endpoint = clerk.from_config({"provider": "custom", "base_url": fake_server,
                                  "key_env": "TEST_KEY", "model": "m1", "model_uses": "m2",
                                  "min_tokens": 1800})
    result = clerk.run_one(clerk.uses(README), endpoint)
    assert result.ok and result.model == "m2"
    first, second = _Fake.seen
    assert first["auth"] == "Bearer secret" and first["body"]["max_tokens"] == 1800
    assert "response_format" in first["body"] and "response_format" not in second["body"]


def test_missing_key_queues(fake_server, monkeypatch, tmp_path):
    monkeypatch.delenv("TEST_KEY", raising=False)
    endpoint = clerk.from_config({"provider": "custom", "base_url": fake_server,
                                  "key_env": "TEST_KEY", "model": "m"})
    result = clerk.run([clerk.uses(README)], endpoint, tmp_path / "q")[0]
    assert result.status == "queued" and "TEST_KEY" in result.problems


def test_unreachable_endpoint_queues(tmp_path):
    endpoint = clerk.OpenAICompatible("http://127.0.0.1:9/v1", "m", timeout=2)
    assert clerk.run([clerk.uses(README)], endpoint, tmp_path)[0].status == "queued"
