"""The core's local API, over a real loopback server: the boundary, the chat
through the loop, permissions decided live, keys that never come back, and the
person's own calls."""
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from resource_librarian import keys, providers
from resource_librarian.app import App, build
from resource_librarian.keys import KeyStore
from resource_librarian.providers import Reply, ToolCall

from conftest import add_source
from test_sessions import OSQUERY_LINE


class Client:
    def __init__(self, server, token):
        self.base = f"http://127.0.0.1:{server.server_address[1]}"
        self.token = token

    def request(self, method, path, body=None, headers=None, token=True):
        head = {"Content-Type": "application/json", **(headers or {})}
        if token:
            head["X-Librarian-Token"] = self.token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=head)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                kind = response.headers.get("Content-Type", "")
                return response.status, (json.loads(raw) if "json" in kind else raw.decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body or {}, **kw)

    def upload(self, path, data: bytes, token=True):
        """The composer's paperclip sends raw bytes, not a JSON body."""
        head = {"X-Librarian-Token": self.token} if token else {}
        req = urllib.request.Request(self.base + path, data=data, method="POST", headers=head)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")


class Model:
    """A scripted chat model whose replies are set per test."""

    def __init__(self):
        self.replies = []
        self.provider = providers.Scripted(lambda s, m, t: self.replies.pop(0))


@pytest.fixture
def served(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    for name in ("OPENAI_API_KEY", "DEEPINFRA_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    add_source(vault.root, "osquery", OSQUERY_LINE, "Query operating system state.")
    model = Model()
    app = App(vault, token="test-token", keys=KeyStore(use_keyring=False),
              provider_for=lambda choice: model.provider, broker_timeout=5)
    server = build(app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield app, Client(server, "test-token"), model
    server.shutdown()
    server.server_close()
    if app.mcp is not None:
        app.mcp.stop()


def wait_for(app, kind, timeout=5.0, after=0):
    end = time.time() + timeout
    while time.time() < end:
        for event in app.hub.since(after):
            if event["type"] == kind:
                return event
        time.sleep(0.02)
    raise AssertionError(f"no {kind} event; saw {[e['type'] for e in app.hub.since(after)]}")


def test_the_boundary(served):
    app, client, _ = served
    assert client.get("/api/state", token=False)[0] == 403
    assert client.get("/api/state")[0] == 200
    evil = client.post("/api/mode", {"mode": "auto"}, headers={"Origin": "https://evil.example"})
    assert evil[0] == 403 and "another origin" in evil[1]["error"]
    assert client.post("/api/mode", {"mode": "auto"},
                       headers={"Origin": "app://obsidian.md"})[0] == 200
    rebound = client.get("/api/state", headers={"Host": "evil.example:8323"})
    assert rebound[0] == 403
    status, page = client.get("/", token=False)                  # the page carries the token
    assert status == 200 and 'content="test-token"' in page and "__LIBRARIAN_TOKEN__" not in page
    req = urllib.request.Request(client.base + "/app.js")
    with urllib.request.urlopen(req) as response:
        assert response.status == 200 and "javascript" in response.headers["Content-Type"]
        assert "default-src 'self'" in response.headers["Content-Security-Policy"]
    assert client.get("/../keys.py", token=False)[0] == 404


def test_a_chat_turn_runs_the_loop_and_streams_events(served):
    app, client, model = served
    assert client.post("/api/chat", {"text": "hi"})[0] == 409     # no model chosen yet
    # R10: a lead M0 has not qualified needs a person's recorded override
    status, body = client.post("/api/tiers", {"tiers": [{"provider": "deepinfra",
                                                          "model": "m1"}]})
    assert status == 409 and body["needs_override"] and body["lead"] == "deepinfra/m1"
    assert client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}],
                                      "override": "trying it out"})[0] == 200
    assert client.get("/api/state")[1]["lead"]["reason"] == "trying it out"
    model.replies = [Reply(tool_calls=[ToolCall("1", "open_session", {"purpose": "explore",
                                                                       "question": "hosts"})]),
                     Reply(text="Opened a thread on hosts.")]
    assert client.post("/api/chat", {"text": "explore hosts"})[1] == {"accepted": True}
    done = wait_for(app, "turn_done")
    assert done["reply"] == "Opened a thread on hosts."
    assert done["session"]["phase"] == "frame" and done["session"]["purpose"] == "explore"
    kinds = [e["type"] for e in app.hub.since(0)]
    assert kinds.index("user") < kinds.index("tool_call") < kinds.index("tool_result") \
        < kinds.index("turn_done")
    assert client.get("/api/state")[1]["session"]["purpose"] == "explore"
    # Busy is cleared before turn_done is announced, so sending the moment
    # it arrives is accepted rather than refused as "still answering".
    model.replies = [Reply(text="Again.")]
    assert client.post("/api/chat", {"text": "again"})[0] == 200
    wait_for(app, "turn_done", after=done["seq"])


def test_ask_mode_waits_for_the_person_and_a_mode_switch_releases_it(served):
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    client.post("/api/mode", {"mode": "ask"})
    model.replies = [Reply(tool_calls=[ToolCall("1", "create_project", {
        "name": "Host Watch", "stage": "idea", "summary": "Watch hosts."})]),
        Reply(text="Created.")]
    client.post("/api/chat", {"text": "make the project"})
    request = wait_for(app, "permission_request")
    assert request["tool"] == "create_project"
    assert client.get("/api/state")[1]["pending"][0]["id"] == request["id"]
    assert client.post("/api/mode", {"mode": "auto"})[1]["released"] == [request["id"]]
    assert wait_for(app, "turn_done")["reply"] == "Created."
    assert (app.vault.root / "Projects" / "Host Watch.md").is_file()


def test_a_denied_request_reaches_the_model_as_a_refusal(served):
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [Reply(tool_calls=[ToolCall("1", "create_project", {
        "name": "Nope", "stage": "idea", "summary": "x"})]), Reply(text="Understood.")]
    client.post("/api/chat", {"text": "make it"})
    request = wait_for(app, "permission_request")
    assert client.post("/api/permission", {"id": request["id"], "answer": "deny"})[0] == 200
    wait_for(app, "turn_done")
    result = [e for e in app.hub.since(0) if e["type"] == "tool_result"][0]["result"]
    assert result["refused"] == "PERMISSION_DENIED"
    assert not (app.vault.root / "Projects" / "Nope.md").exists()


def test_answering_a_question_wakes_the_waiting_turn(served):
    """The gate bug: answering a question the model asked used to be inert -
    nothing fed it back to the loop, or resumed the turn. `ask_user` now
    really blocks the turn's own thread (Waiters, tools/sessions.py), the
    same handshake a permission gate already uses, so the model sees the
    real answer and finishes the SAME turn - no second message needed."""
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "m1"}], "override": "test"})
    model.replies = [
        Reply(tool_calls=[ToolCall("1", "open_session", {"purpose": "explore",
                                                          "question": "hosts"})]),
        Reply(tool_calls=[ToolCall("2", "ask_user", {"question": "Which host?"})]),
        Reply(text="Noted: Prod-01."),
    ]
    client.post("/api/chat", {"text": "explore hosts"})
    asked = wait_for(app, "question_asked")
    assert asked["question"] == "Which host?"
    answered = client.post("/api/tool/answer", {
        "arguments": {"question_id": asked["question_id"], "answer": "Prod-01"},
        "session": asked["session"]})
    assert answered[0] == 200 and answered[1]["resumed"] is True
    wait_for(app, "question_answered")
    done = wait_for(app, "turn_done")
    assert done["reply"] == "Noted: Prod-01."
    tool_results = [e["result"] for e in app.hub.since(0)
                    if e["type"] == "tool_result" and e["tool"] == "ask_user"]
    assert tool_results[-1]["answer"] == "Prod-01"
    assert "needs_person" not in tool_results[-1]


def test_keys_are_saved_confirmed_and_never_returned(served, tmp_path, monkeypatch):
    app, client, _ = served
    secret = "sk-test-SECRET-7f3a"
    saved = client.post("/api/keys", {"provider": "deepinfra", "key": secret})
    assert saved[0] == 200 and saved[1]["last4"] == "7f3a" and saved[1]["saved"]
    again = client.post("/api/keys", {"provider": "deepinfra", "key": "sk-other-key-1111"})
    assert again[0] == 409 and "Replace the saved DeepInfra key?" in again[1]["confirm"]
    everything = json.dumps([client.get("/api/state")[1], client.get("/api/keys")[1],
                             app.hub.since(0)])
    assert secret not in everything and "SECRET" not in everything
    stored = tmp_path / "config" / ".env"
    assert stored.is_file() and keys.owner_only(stored)      # 0600, or its Windows ACL
    assert not list(app.vault.root.rglob(".env"))                 # never inside the vault
    assert client.post("/api/keys/remove", {"provider": "deepinfra"})[0] == 409
    removed = client.post("/api/keys/remove", {"provider": "deepinfra", "confirm": True})
    assert removed[1]["saved"] is False


def test_the_persons_own_calls_and_settings(served):
    app, client, _ = served
    status, found = client.post("/api/tool/search", {"arguments": {"query": "operating system"}})
    assert status == 200 and found["results"][0]["name"] == "osquery"
    tools = client.get("/api/tools")[1]["tools"]
    assert "accept_workflow" in {t["name"] for t in tools}          # the person is curate
    context = client.post("/api/context", {"working_context": "a thesis on hosts",
                                           "reply_length": "short"})[1]
    assert context == {"working_context": "a thesis on hosts", "reply_length": "short",
                       "stance": "answer"}
    assert json.loads((app.vault.librarian / "app.json").read_text())["reply_length"] == "short"
    assert client.post("/api/context", {"stance": "coach"})[1]["stance"] == "coach"
    assert client.post("/api/context", {"stance": "nope"})[0] == 400
    library = client.post("/api/library", {"promotion_mode": "agent"})[1]
    assert library["promotion"]["mode"] == "agent" and library["doctor"]
    assert client.post("/api/tiers", {"tiers": [{"provider": "nope", "model": "x"}]})[0] == 400


def test_tiers_fall_back_upward(served):
    app, client, model = served
    client.post("/api/tiers", {"tiers": [{"provider": "deepinfra", "model": "big"}], "override": "test"})
    assert app.tier(3) is model.provider                           # tier 3 -> 2 -> 1
    client.post("/api/tiers", {"tiers": []})                       # clear selection
    assert app.tier(1) is None


def test_a_queued_action_asks_in_ask_mode_and_can_be_cancelled(served):
    app, client, _ = served
    status, action = client.post("/api/actions", {"name": "run-queue"})
    assert status == 200 and action["status"] == "running"
    request = wait_for(app, "permission_request")                # its write waits, in Ask
    assert request["tool"] == "intake_run"
    assert client.post(f"/api/actions/{action['id']}/cancel")[1] == {"cancelling": action["id"]}
    client.post("/api/permission", {"id": request["id"], "answer": "allow_once"})
    done = wait_for(app, "action_done")
    assert done["id"] == action["id"] and done["status"] == "finished"

    client.post("/api/mode", {"mode": "auto"})
    after = app.hub.last()
    second = client.post("/api/actions", {"name": "run-queue"})[1]
    done = wait_for(app, "action_done", after=after)
    assert done["id"] == second["id"] and done["status"] == "finished"
    assert not [e for e in app.hub.since(after) if e["type"] == "permission_request"]
    assert client.post("/api/actions", {"name": "no-such-pipeline"})[0] == 404
    assert client.post("/api/actions/zzz/cancel")[0] == 404


def test_a_cancelled_run_pauses_before_its_next_step(vault):
    from resource_librarian import workflows
    from resource_librarian.registry import Context
    from resource_librarian.tools.workflows import _library
    cancel = threading.Event()
    cancel.set()
    ctx = Context(tier="contribute", vault=vault, extras={"cancel": cancel})
    out = workflows.Runner(_library(ctx), ctx).start("run-queue")
    assert out["status"] == "paused" and out["reason"] == "cancelled by a person"
    cancel.clear()
    resumed = workflows.Runner(_library(ctx), ctx).resume(out["run"])
    assert resumed["status"] == "finished"


def test_only_a_host_origin_may_read_across_origins(served):
    app, client, _ = served
    status, _ = client.request("OPTIONS", "/api/state", token=False,
                               headers={"Origin": "app://obsidian.md"})
    assert status == 204
    assert client.request("OPTIONS", "/api/state", token=False,
                          headers={"Origin": "https://evil.example"})[0] == 403
    req = urllib.request.Request(client.base + "/api/state", headers={
        "X-Librarian-Token": client.token, "Origin": "app://obsidian.md"})
    with urllib.request.urlopen(req) as response:
        assert response.headers["Access-Control-Allow-Origin"] == "app://obsidian.md"
    req = urllib.request.Request(client.base + "/api/state", headers={
        "X-Librarian-Token": client.token, "Origin": "https://evil.example"})
    with urllib.request.urlopen(req) as response:
        assert response.headers["Access-Control-Allow-Origin"] is None


def test_the_pane_reads_the_vaults_notes_and_nothing_else(served):
    app, client, _ = served
    status, top = client.get("/api/files")
    names = {e["name"]: e for e in top["entries"]}
    assert status == 200 and names["Sources"]["kind"] == "dir"
    assert not [n for n in names if n.startswith(".")]            # .librarian, .obsidian...
    assert top["entries"][0]["kind"] == "dir"                       # folders first
    inner = client.get("/api/files?dir=Sources/repository")[1]
    assert {"name": "osquery", "kind": "file", "path": "Sources/repository/osquery.md"} in inner["entries"]

    by_path = client.get("/api/file?path=Sources/repository/osquery")[1]
    assert by_path["name"] == "osquery" and by_path["text"].startswith("---\n")
    by_name = client.get("/api/file?path=osquery")[1]              # what a bare [[link]] holds
    assert by_name["path"] == "Sources/repository/osquery.md"
    assert client.get("/api/file?path=Sources/repository/osquery.md")[1]["path"] == by_name["path"]

    assert client.get("/api/file?path=.librarian/config.toml")[0] == 403
    assert client.get("/api/file?path=.librarian/app")[0] == 403
    assert client.get("/api/files?dir=../..")[0] == 403
    assert client.get("/api/file?path=../../etc/passwd")[0] == 403
    assert client.get("/api/file?path=nothing-by-this-name")[0] == 404
    assert client.get("/api/files", token=False)[0] == 403


def test_attach_saves_a_file_a_person_can_then_ingest(served, monkeypatch):
    """The composer's paperclip: a file lands in Inbox/, a name collision
    doesn't clobber the first one, and the path it hands back is exactly what
    `ingest` already knows how to take (see test_intake's file capture)."""
    app, client, _ = served
    status, out = client.upload("/api/attach?name=paper.pdf", b"%PDF-1.4 not a real pdf")
    assert status == 200, out
    assert out == {"path": "Inbox/paper.pdf", "name": "paper.pdf"}
    assert (app.vault.root / "Inbox" / "paper.pdf").read_bytes() == b"%PDF-1.4 not a real pdf"

    status2, out2 = client.upload("/api/attach?name=paper.pdf", b"a second, different file")
    assert status2 == 200 and out2["path"] == "Inbox/paper (1).pdf"
    assert (app.vault.root / "Inbox" / "paper.pdf").read_bytes() == b"%PDF-1.4 not a real pdf"

    assert client.upload("/api/attach?name=x.txt", b"x", token=False)[0] == 403
    assert client.upload("/api/attach?dir=..&name=x.txt", b"x")[0] == 403

    import resource_librarian.app as app_module
    monkeypatch.setattr(app_module, "MAX_UPLOAD", 4)
    status3, out3 = client.upload("/api/attach?name=big.bin", b"too many bytes")
    assert status3 == 413, out3


def test_models_shows_profiled_queued_and_unprofiled(served, monkeypatch):
    """The Model tile's whole point: a catalogued model Source shows its real
    specs, a staged one says it is awaiting review, and only a genuinely
    unprofiled one is unprofiled."""
    from resource_librarian import clerk, intake
    from resource_librarian.registry import Context
    from test_intake import MODEL_PAGE, model_answers

    app, client, model = served
    model.provider.models = lambda: ["openai/gpt-oss-20b", "acme/still-unprofiled",
                                     "acme/queued-model"]

    c = Context(tier="curate", vault=app.vault, extras={
        "clerk": clerk.Scripted(model_answers),
        "fetcher": intake.Replay({"https://deepinfra.com/openai/gpt-oss-20b": MODEL_PAGE})})
    profiled = REGISTRY_CALL(c, "ingest", ref="model:deepinfra:openai/gpt-oss-20b")
    REGISTRY_CALL(c, "staging_decide", item_ids=[profiled["item"]], decision="accept")
    # queued: staged, no draft, left waiting (as a real "no clerk endpoint" run would)
    queued_ctx = Context(tier="curate", vault=app.vault, extras={
        "fetcher": intake.Replay({"https://deepinfra.com/acme/queued-model": MODEL_PAGE})})
    REGISTRY_CALL(queued_ctx, "ingest", ref="model:deepinfra:acme/queued-model")

    listing = client.get("/api/models?provider=deepinfra")[1]
    by_id = {m["id"]: m for m in listing["models"]}
    done = by_id["openai/gpt-oss-20b"]
    assert done["profile"]["tool_calling"] is True and done["profile"]["suggested_tier"] == "Tier_3"
    assert done["profile"]["best_for"] == ["Small_Coding_Tasks"]
    assert done["profile"]["context_length"] == 131072
    assert done["profile"]["path"].startswith("Sources/model/")
    assert by_id["acme/queued-model"].get("profiling") == "queued"
    assert "profile" not in by_id["acme/still-unprofiled"] and \
        "profiling" not in by_id["acme/still-unprofiled"]


def REGISTRY_CALL(ctx, name, **arguments):
    from resource_librarian.registry import REGISTRY
    result = REGISTRY.call(name, arguments, ctx)
    assert "error" not in result, result
    return result


def test_api_usage_falls_back_to_the_dashboard_link(served):
    """The scripted provider (like most real providers) has no usage endpoint:
    the settings page must still get a dashboard link, never a 500."""
    _, client, _ = served
    out = client.get("/api/usage?provider=deepinfra")[1]
    assert out["ok"] is False and out["dashboard"] == "https://deepinfra.com/dash"
    assert "usage endpoint" in out["error"]
    unknown = client.get("/api/usage?provider=nope")[1]
    assert unknown["ok"] is False and unknown["dashboard"] == ""


def test_api_usage_reports_a_working_deepinfra_balance(served, monkeypatch):
    app, client, model = served
    model.provider.usage = lambda: {"stripe_balance": 4.2, "suspended": False,
                                    "billing_type": "prepaid"}
    out = client.get("/api/usage?provider=deepinfra")[1]
    assert out == {"ok": True, "dashboard": "https://deepinfra.com/dash", "unofficial": True,
                  "balance": 4.2, "currency": "USD", "suspended": False,
                  "billing_type": "prepaid"}


# -- MCP servers (Co-work Roadmap §3, Phase 1) -----------------------------------

pytest.importorskip("mcp")
FAKE_MCP_SERVER = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


def test_api_mcp_status_is_empty_with_no_servers_configured(served):
    _, client, _ = served
    status, out = client.get("/api/mcp")
    assert status == 200 and out["servers"] == {}


def test_api_mcp_save_a_server_needs_acceptance_before_it_connects(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/config", {
        "mcpServers": {"fake": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}}})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is False
    assert out["servers"]["fake"]["connected"] is False
    assert out["servers"]["fake"]["command"] == sys.executable
    assert "env" not in out["servers"]["fake"] or out["servers"]["fake"]["env"] == []


def test_api_mcp_accept_connects_and_registers_its_tools(served):
    import sys
    from resource_librarian.registry import REGISTRY
    app, client, _ = served
    client.post("/api/mcp/config", {
        "mcpServers": {"fake": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}}})
    status, out = client.post("/api/mcp/accept", {"name": "fake"})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is True
    # Accepted for the person, but each library decides for itself (§4 F1):
    # not running here until this library turns it on.
    assert out["servers"]["fake"]["connected"] is False
    assert out["servers"]["fake"]["library_enabled"] is False
    status, out = client.post("/api/mcp/library", {"name": "fake", "enabled": True})
    assert status == 200 and out["servers"]["fake"]["library_enabled"] is True
    assert out["servers"]["fake"]["connected"] is True
    assert out["servers"]["fake"]["tools"] == 2
    assert sorted(out["servers"]["fake"]["tool_names"]) == ["mcp__fake__boom", "mcp__fake__echo"]
    assert out["tool_settings"]["mcp__fake__echo"] == "ask"
    assert "mcp__fake__echo" in REGISTRY.external_names()
    assert app.broker.settings["mcp__fake__echo"] == "ask"


def test_api_mcp_accept_refuses_an_unknown_server(served):
    _, client, _ = served
    status, out = client.post("/api/mcp/accept", {"name": "nope"})
    assert status == 404


def test_api_mcp_never_returns_an_env_value(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/config", {
        "mcpServers": {"fake": {"command": sys.executable, "args": [FAKE_MCP_SERVER],
                               "env": {"SOME_TOKEN": "literal-secret-value"}}}})
    assert status == 200
    body = json.dumps(out)
    assert "literal-secret-value" not in body
    assert out["servers"]["fake"]["env"] == ["SOME_TOKEN"]


def test_api_mcp_server_installs_and_accepts_in_one_step(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/server", {
        "name": "fake", "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is True
    assert out["servers"]["fake"]["connected"] is True
    assert out["servers"]["fake"]["tools"] == 2


def test_api_mcp_server_needs_a_name(served):
    import sys
    _, client, _ = served
    status, out = client.post("/api/mcp/server", {
        "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    assert status == 400


def test_api_mcp_enable_toggles_without_losing_acceptance(served):
    import sys
    _, client, _ = served
    client.post("/api/mcp/server", {
        "name": "fake", "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    status, out = client.post("/api/mcp/enable", {"name": "fake", "enabled": False})
    assert status == 200 and out["servers"]["fake"]["connected"] is False
    status, out = client.post("/api/mcp/enable", {"name": "fake", "enabled": True})
    assert status == 200
    assert out["servers"]["fake"]["accepted"] is True      # never had to re-accept
    assert out["servers"]["fake"]["connected"] is True


def test_api_mcp_enable_refuses_an_unknown_server(served):
    _, client, _ = served
    status, out = client.post("/api/mcp/enable", {"name": "nope", "enabled": True})
    assert status == 404


def test_api_mcp_remove_disconnects_and_forgets_the_server(served):
    import sys
    from resource_librarian.registry import REGISTRY
    _, client, _ = served
    client.post("/api/mcp/server", {
        "name": "fake", "server": {"command": sys.executable, "args": [FAKE_MCP_SERVER]}})
    status, out = client.post("/api/mcp/remove", {"name": "fake"})
    assert status == 200 and out["servers"] == {}
    assert REGISTRY.external_names() == []


def test_api_mcp_registry_proxies_the_search_server_side(served, monkeypatch):
    import resource_librarian.mcp_client as mcp_client
    _, client, _ = served
    monkeypatch.setattr(mcp_client, "REGISTRY_SEARCH_URL", "http://127.0.0.1:1/v0/servers")
    status, out = client.get("/api/mcp/registry?q=semantic")
    assert status == 200 and out["servers"] == [] and "error" in out



def test_settings_turn_the_review_gate_on_and_save_a_search_key(served):
    """Owner checks O4/O5 and O3b (2026-10-01): no switch for the review gate, and no
    place for a web search key."""
    app, client, _ = served
    status, lib = client.post("/api/library", {"review": {"review_replies": True,
                                                          "review_offerings": True}})
    assert status == 200 and lib["clerk"]["review_replies"] is True
    assert app.vault.config()["clerk"]["review_offerings"] is True
    assert client.post("/api/library", {"review": {"review_everything": True}})[0] == 400
    assert client.post("/api/library", {"promotion_mode": "agent"})[1]["promotion"]["mode"] == "agent"
    status, out = client.post("/api/keys", {"provider": "tavily", "key": "tvly-test-0123456789"})
    assert status == 200 and out["saved"] and out["check"]["ok"]
    assert "Tavily" in out["check"]["status"]
    keys = {k["provider"]: k for k in client.get("/api/keys")[1]["keys"]}
    assert keys["tavily"]["saved"] and keys["tavily"]["last4"] == "6789"
    assert not keys["brave"]["saved"]
