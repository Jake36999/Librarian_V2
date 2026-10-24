"""The MCP server: generated from the registry, one thread per connection, every
call run by the vault's active Core (CORE-04A), and the M5 acceptance: a
scripted session run through MCP produces the same artefacts as the same
session run straight through the registry (the path the CLI and the agent loop
take)."""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time

import anyio
import anyio.from_thread
import anyio.to_thread
import pytest

mcp = pytest.importorskip("mcp")
from mcp import Client  # noqa: E402

from resource_librarian import clerk, connection, intake, notes, process_identity  # noqa: E402
from resource_librarian.app import PROTOCOL_VERSION, App, build  # noqa: E402
from resource_librarian.mcp_server import LibrarianServer  # noqa: E402
from resource_librarian.registry import REGISTRY, Context  # noqa: E402

from test_intake import RESPONSES, clerk_answers  # noqa: E402
from walks import add_project_walk, artefacts, library  # noqa: E402
from test_workflows import backlog  # noqa: E402

MODES = ["legacy", "auto"]          # the handshake era and the 2026-07-28 era


def run(server, script, mode="legacy", **client):
    """Drive `script(call)` against the server through a real MCP client; the
    script is ordinary synchronous code, as a model's turn would be."""
    out = {}

    async def main():
        async with Client(server.server, mode=mode, **client) as c:
            def call(_tool, **arguments):
                result = anyio.from_thread.run(c.call_tool, _tool, arguments)
                payload = result.structured_content or json.loads(result.content[0].text)
                assert result.is_error == ("error" in payload)
                return payload
            out["value"] = await anyio.to_thread.run_sync(script, call)
    anyio.run(main)
    return out["value"]


def _publish(root, url, pid, token="t"):
    assert connection.publish(root, url=url, token=token, pid=pid, protocol_version=PROTOCOL_VERSION,
                              secret_source="desktop",
                              process_start=process_identity.process_start(pid))


@pytest.fixture
def live_core():
    """Start the vault's Core in this process, serving HTTP on loopback and
    published as the vault's active Core - what Librarian.bat or the tray Host
    does. Auto mode unless a test says otherwise; `extras` reach every call."""
    started = []

    def start(vault, mode="auto", **extras):
        app = App(vault, coordinate=True)
        app.broker.set_mode(mode)
        if extras:
            plain = app._extras
            app._extras = lambda: {**plain(), **extras}
        server = build(app, 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _publish(vault.root, f"http://127.0.0.1:{server.server_address[1]}", os.getpid(), app.token)
        started.append((vault, app, server))
        return app
    yield start
    for vault, app, server in started:
        server.shutdown()
        server.server_close()
        app.close_runtime()
        connection.remove(vault.root, pid=os.getpid(), token=app.token)


def _ops(vault):
    path = vault.librarian / "runtime" / "operations.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()] if path.exists() else []


def test_tools_come_from_the_registry_and_respect_the_tier(vault, live_core):
    async def listed(tier):
        async with Client(LibrarianServer(vault, tier).server, mode="legacy") as c:
            return {t.name: t for t in (await c.list_tools()).tools}
    reader = anyio.run(listed, "consult")
    librarian = anyio.run(listed, "contribute")
    assert set(reader) == {s.name for s in REGISTRY.for_tier("consult")}
    assert set(librarian) == {s.name for s in REGISTRY.for_tier("contribute")}
    assert "staging_decide" in librarian and "staging_decide" not in reader
    assert "accept_workflow" not in librarian                  # a person's tool
    spec = REGISTRY.get("search")
    assert reader["search"].input_schema == spec.json_schema()
    assert reader["search"].description == spec.description()
    assert reader["search"].annotations.read_only_hint is True
    assert librarian["staging_decide"].annotations.read_only_hint is False
    assert reader["search"].meta["librarian/group"] == "search"
    assert librarian["open_session"].meta["librarian/group"] == "session"

    live_core(vault)
    refused = run(LibrarianServer(vault, "consult"),
                  lambda call: call("staging_decide", item_ids=["x"], decision="accept"))
    assert refused["refused"] == "TIER_REFUSED"


def test_a_curate_connection_is_an_agent_at_contribute(vault, live_core):
    """CORE-04A: curate is a person's authority. The server lists contribute
    tools only, and the Core refuses a curate-only tool even if asked."""
    capped = LibrarianServer(vault, "curate")
    assert capped.tier == "contribute"
    assert {t.name for t in capped.tools()} == {s.name for s in REGISTRY.for_tier("contribute")}
    contribute = {s.name for s in REGISTRY.for_tier("contribute")}
    curate_only = sorted(s.name for s in REGISTRY.for_tier("curate") if s.name not in contribute)
    assert curate_only
    core = live_core(vault)
    assert capped.call(curate_only[0], {}, {})["refused"] == "TIER_REFUSED"
    # The Core caps the tier itself, whatever a client claims.
    assert core.mcp_call(curate_only[0], {}, tier="curate")["result"]["refused"] == "TIER_REFUSED"


@pytest.mark.parametrize("mode", MODES)
def test_a_connection_carries_its_session(vault, live_core, mode):
    live_core(vault)
    server = LibrarianServer(vault, "contribute")

    def script(call):
        assert call("session_status")["refused"] == "SESSION_REQUIRED"
        opened = call("open_session", purpose="explore", question="host monitoring")
        status = call("session_status")
        gated = call("draft_offering", title="x", summary="x", claims=[])
        call("park_session", note="later")
        parked = call("write_note", folder="Notes", name="x", body="y")
        resumed = call("resume_session", session_id=opened["opened"])
        return opened, status, gated, parked, resumed
    opened, status, gated, parked, resumed = run(server, script, mode)
    assert status["session"]["session"] == opened["opened"]
    assert status["session"]["phase"] == "frame"
    assert gated["refused"] == "PHASE_GATE"
    assert gated["session"]["session"] == opened["opened"]        # the envelope on refusals
    assert parked["refused"] == "SESSION_REQUIRED"            # a parked thread writes nothing
    assert resumed["status"] == "open"


def test_connections_do_not_share_a_session(vault, live_core):
    live_core(vault)
    server = LibrarianServer(vault, "contribute")
    first = run(server, lambda call: call("open_session", purpose="explore")["opened"])
    second = run(server, lambda call: call("session_status"))
    assert first and second["refused"] == "SESSION_REQUIRED"


def test_routing_without_a_core_clerk_pauses(vault, live_core):
    """The clerk is the Core's: with no routing model the pipeline pauses
    rather than borrowing the connection's model in-line."""
    backlog(vault)
    live_core(vault, clerk=clerk.Scripted(clerk_answers), fetcher=intake.Replay(RESPONSES))
    out = run(LibrarianServer(vault, "contribute"),
              lambda call: call("run_pipeline", name="clear-enrichment-backlog"))
    assert out["status"] == "paused" and "no routing model" in out["reason"]


# -- CORE-04A: every call is the Core's, or refused --------------------------

def test_without_a_core_every_call_is_refused_and_nothing_is_written(vault):
    server = LibrarianServer(vault, "contribute")
    before = sorted(p.relative_to(vault.root) for p in vault.root.rglob("*"))
    for name, arguments in (("open_session", {"purpose": "explore"}), ("search", {"query": "x"}),
                            ("session_status", {})):
        assert server.call(name, arguments, {})["refused"] == "CORE_REQUIRED"
    assert sorted(p.relative_to(vault.root) for p in vault.root.rglob("*")) == before


def test_a_recorded_core_that_stopped_is_refused(vault):
    child = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-c", "pass"])
    child.wait()
    _publish(vault.root, "http://127.0.0.1:9", child.pid)
    refused = LibrarianServer(vault, "contribute").call("open_session", {"purpose": "explore"}, {})
    assert refused["refused"] == "CORE_REQUIRED" and "no longer running" in refused["detail"]


def test_an_unreachable_or_foreign_core_is_refused_without_a_fallback(vault):
    with socket.socket() as probe:                   # a loopback port nobody serves
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    _publish(vault.root, f"http://127.0.0.1:{port}", os.getpid())
    server = LibrarianServer(vault, "contribute")
    refused = server.call("open_session", {"purpose": "explore"}, {})
    assert refused["refused"] == "CORE_REQUIRED" and "no direct vault access" in refused["detail"]
    assert not list((vault.librarian / "sessions").glob("*.jsonl"))
    _publish(vault.root, "http://example.com:80", os.getpid())
    assert server.call("session_status", {}, {})["refused"] == "CORE_REQUIRED"


def test_mcp_writes_go_through_the_core_writer_as_mcp(vault, live_core):
    live_core(vault)
    state = {}
    server = LibrarianServer(vault, "contribute")
    server.call("open_session", {"purpose": "add_project"}, state)
    made = server.call("create_project", {"name": "Host Watch", "stage": "planning",
                                          "summary": "Watch our hosts."}, state)
    assert "error" not in made, made
    callers = {op["caller"] for op in _ops(vault)}
    assert "mcp" in callers                          # the tool's own write
    assert "session-event" in callers                # and its session events


def test_an_mcp_write_to_a_note_being_edited_becomes_a_conflict_checkpoint(vault, live_core):
    core = live_core(vault)
    state = {}
    server = LibrarianServer(vault, "contribute")
    server.call("open_session", {"purpose": "add_project"}, state)
    made = server.call("create_project", {"name": "Host Watch", "stage": "planning",
                                          "summary": "Watch our hosts."}, state)
    core.document_heartbeat(made["created"], editor="Obsidian", dirty=True)
    refused = server.call("update_project", {"name": "Host Watch", "summary": "Changed."}, state)
    assert refused["refused"] == "DOCUMENT_ACTIVE"
    assert refused["checkpoint"]["requester"] == "mcp"
    assert "Watch our hosts." in (vault.root / made["created"]).read_text(encoding="utf-8")


def test_in_ask_mode_an_mcp_write_waits_for_a_person(vault, live_core):
    """The broker is kept: the Core's Modes setting governs an MCP agent too."""
    core = live_core(vault, mode="ask")
    state = {}
    server = LibrarianServer(vault, "contribute")
    server.call("open_session", {"purpose": "add_project"}, state)
    asked = []

    def person():
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            for request in core.broker.pending():
                asked.append(request["tool"])
                core.broker.answer(request["id"], "allow_once")
                return
            time.sleep(0.05)
    helper = threading.Thread(target=person, daemon=True)
    helper.start()
    made = server.call("create_project", {"name": "Host Watch", "stage": "planning",
                                          "summary": "Watch our hosts."}, state)
    helper.join(25)
    assert asked == ["create_project"] and "error" not in made, made


def test_the_core_endpoint_needs_the_token_a_loopback_host_and_its_own_origin(vault, live_core):
    """Reviewer question (DeepSeek-V4-Pro, CORE-04A): the endpoint is covered by
    do_POST's host, origin and token checks before any routing."""
    import urllib.error
    import urllib.request
    core = live_core(vault)
    url = connection.load(vault.root)["url"]
    body = json.dumps({"tool": "session_status", "arguments": {}, "tier": "contribute"}).encode()

    def post(headers):
        request = urllib.request.Request(url + "/api/mcp/call", data=body, method="POST",
                                         headers={"Content-Type": "application/json", **headers})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status
        except urllib.error.HTTPError as exc:
            return exc.code
    assert post({"X-Librarian-Token": core.token, "Origin": url}) == 200
    assert post({"X-Librarian-Token": "wrong", "Origin": url}) == 403
    assert post({"Origin": url}) == 403
    assert post({"X-Librarian-Token": core.token, "Origin": "https://evil.example"}) == 403
    assert post({"X-Librarian-Token": core.token, "Origin": url, "Host": "evil.example"}) == 403


def test_a_stopping_core_refuses_new_mcp_calls(vault, live_core):
    core = live_core(vault)
    core._admitting = False
    refused = LibrarianServer(vault, "contribute").call("session_status", {}, {})
    assert refused["refused"] == "CORE_REQUIRED" and "503" in refused["detail"]


# -- acceptance: the same scripted session, two surfaces ---------------------

def test_the_same_session_through_mcp_and_the_core_leaves_the_same_artefacts(tmp_path, live_core):
    """MCP is a transport: the walk through MCP leaves exactly what the same
    calls leave when made in an identical Core directly (its broker, writer,
    clerk queue and review - with questions returned, not awaited, as MCP's are)."""
    direct = library(tmp_path / "direct")
    direct_core = live_core(direct)
    extras = {k: v for k, v in direct_core._extras().items() if k != "waiters"}
    ctx = Context(tier="contribute", vault=direct, extras={**extras, "caller_kind": "mcp", "caller": "mcp"})
    direct_session = add_project_walk(direct, lambda _tool, **a: REGISTRY.call(_tool, a, ctx))
    direct_core.close_runtime()

    served = library(tmp_path / "served")
    core = live_core(served)
    served_session = run(LibrarianServer(served, "contribute"),
                         lambda call: add_project_walk(served, call))
    core.close_runtime()                  # release the lease before reading every file

    # Each Core's runtime state (lease, operation log) is its own.
    core_only = (".librarian/runtime/",)
    left = {k: v for k, v in artefacts(direct, direct_session).items() if not k.startswith(core_only)}
    right = {k: v for k, v in artefacts(served, served_session).items() if not k.startswith(core_only)}
    assert sorted(left) == sorted(right)
    for rel in left:
        assert left[rel] == right[rel], rel
    offering = notes.load(served.root / "Offerings/Host Watch/Host Watch Starter.md")
    assert offering.frontmatter["session"] == served_session


def test_the_clerk_agent_answers_waiting_tasks_outside_the_thread(vault, live_core):
    """The clerk route with no endpoint: a review queues its tasks; a clerk
    agent on the same connection takes each one, which carries nothing of the
    thread; the review's next run uses the answers."""
    live_core(vault, fetcher=intake.Replay(RESPONSES))
    server = LibrarianServer(vault, "contribute")

    def answer_all(call):
        seen, bad = [], None
        while (task := call("clerk_next"))["waiting"]:
            assert "session" not in task and "SECRET-FRAMING" not in json.dumps(task)
            payload = {"task": task["task"], "user": task["user"], "schema": task["schema"]}
            if bad is None:
                bad = call("clerk_submit", key=task["key"], answer={"nonsense": 1})
            seen.append(task["task"])
            submitted = call("clerk_submit", key=task["key"], answer=clerk_answers(payload))
            assert submitted["accepted"], submitted
        return seen, bad

    def script(call):
        staged = call("ingest", ref="acme/rowstream")
        assert staged["detail"]["draft"] == "queued"
        first = call("staging_review", item_id=staged["item"])
        assert first["draft"]["status"] == "queued"
        call("open_session", purpose="explore", question="SECRET-FRAMING streaming storage")
        seen, bad = answer_all(call)
        call("park_session")
        return staged["item"], seen, bad
    item, seen, bad = run(server, script)
    assert bad["accepted"] is False and bad["problems"]
    assert {"bottom_line", "sensitivity"} <= set(seen)
    assert not list((vault.work("queue") / "clerk").glob("*.json"))

    reviewed = run(LibrarianServer(vault, "contribute"),
                   lambda call: call("staging_review", item_id=item))
    assert reviewed["draft"]["status"] == "ok", reviewed
    assert reviewed["draft"]["model"] == "clerk-agent"
    assert not list((vault.work("queue") / "clerk").glob("*.json"))    # nothing re-queued


# -- the Cowork plugin ---------------------------------------------------------

PLUGIN = __import__("pathlib").Path(__file__).resolve().parents[1] / "plugin"


def test_the_plugin_launches_this_server_at_contribute():
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "librarian"
    server = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["librarian"]
    assert server["command"] == "resource-librarian"
    assert server["args"][:3] == ["mcp", "--tier", "contribute"]
    from resource_librarian.cli import build_parser
    args = build_parser().parse_args(server["args"])
    assert args.command == "mcp" and args.mcp_tier == "contribute"


def test_the_plugin_names_only_tools_that_exist():
    """A skill that names a tool the server does not list would send Claude
    after nothing; so would a clerk agent granted a tool that is not there."""
    granted = {s.name for s in REGISTRY.for_tier("contribute")}
    words = {"add_project", "nothing_found"}              # a purpose and a plan field
    for path in PLUGIN.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        for name in re.findall(r"`([a-z]+(?:_[a-z]+)+)`", text):
            assert name in granted or name in words, (path.name, name)
        for name in re.findall(r"mcp__plugin_librarian_librarian__(\w+)", text):
            assert REGISTRY.get(name).sessionless, name     # the clerk sees no thread
        assert re.match(r"---\n(name|description): ", text) or path.name == "README.md", path


def test_the_stdio_server_runs_as_the_plugin_launches_it(vault, live_core):
    from mcp import StdioServerParameters
    live_core(vault)                      # the plugin's server needs the vault's Core
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "resource_librarian", "mcp", "--tier", "contribute"],
        env={**os.environ, "LIBRARIAN_VAULT": str(vault.root)})

    async def main():
        async with Client(params) as c:
            names = {t.name for t in (await c.list_tools()).tools}
            opened = await c.call_tool("open_session", {"purpose": "explore"})
            status = await c.call_tool("session_status", {})
            return names, opened.structured_content, status.structured_content
    names, opened, status = anyio.run(main)
    assert names == {s.name for s in REGISTRY.for_tier("contribute")}
    assert status["session"]["session"] == opened["opened"]
    assert (vault.root / ".librarian" / "sessions" / f"{opened['opened']}.jsonl").is_file()
