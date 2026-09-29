"""The MCP server: generated from the registry, one thread per connection, the
clerk over sampling, and the M5 acceptance: a scripted session run through MCP
produces the same artefacts as the same session run straight through the
registry (the path the CLI and the agent loop take)."""
import json
import re

import anyio
import anyio.from_thread
import anyio.to_thread
import pytest

mcp = pytest.importorskip("mcp")
import mcp_types as types  # noqa: E402
from mcp import Client  # noqa: E402

from resource_librarian import clerk, intake, notes  # noqa: E402
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


def test_tools_come_from_the_registry_and_respect_the_tier(vault):
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

    refused = run(LibrarianServer(vault, "consult"),
                  lambda call: call("staging_decide", item_ids=["x"], decision="accept"))
    assert refused["refused"] == "TIER_REFUSED"


@pytest.mark.parametrize("mode", MODES)
def test_a_connection_carries_its_session(vault, mode):
    server = LibrarianServer(vault, "contribute")

    def script(call):
        assert call("session_status")["refused"] == "SESSION_REQUIRED"
        opened = call("open_session", purpose="explore", question="host monitoring")
        status = call("session_status")
        gated = call("draft_offering", title="x", summary="x", claims=[])
        call("park_session", note="later")
        parked = call("search", query="anything")
        resumed = call("resume_session", session_id=opened["opened"])
        return opened, status, gated, parked, resumed
    opened, status, gated, parked, resumed = run(server, script, mode)
    assert status["session"]["session"] == opened["opened"]
    assert status["session"]["phase"] == "frame"
    assert gated["refused"] == "PHASE_GATE"
    assert gated["session"]["session"] == opened["opened"]        # the envelope on refusals
    assert parked["refused"] == "SESSION_REQUIRED"
    assert resumed["status"] == "open"


def test_connections_do_not_share_a_session(vault):
    server = LibrarianServer(vault, "contribute")
    first = run(server, lambda call: call("open_session", purpose="explore")["opened"])
    second = run(server, lambda call: call("session_status"))
    assert first and second["refused"] == "SESSION_REQUIRED"


def test_routing_runs_on_the_clients_model_with_no_context(vault):
    backlog(vault)
    asked = []

    async def sample(ctx, params: types.CreateMessageRequestParams):
        asked.append(params)
        text = params.messages[0].content.text
        item = json.loads(text.split("---\n", 1)[1].rsplit("\n---", 1)[0])
        option = "review" if item.get("status") == "staged" else "done"
        return types.CreateMessageResult(role="assistant", model="host-model",
                                         content=types.TextContent(type="text", text=json.dumps(
                                             {"option": option, "reason": "scripted"})))
    server = LibrarianServer(vault, "curate", extras={
        "clerk": clerk.Scripted(clerk_answers), "fetcher": intake.Replay(RESPONSES)})
    out = run(server, lambda call: call("run_pipeline", name="clear-enrichment-backlog"),
              sampling_callback=sample)
    assert out["status"] == "finished", out
    assert out["steps"]["next"]["chosen"] == ["review", "review", "done"]
    assert len(asked) == 3
    for params in asked:
        assert params.include_context == "none"
        assert len(params.messages) == 1 and params.temperature == 0.0
        assert "session" not in (params.system_prompt + params.messages[0].content.text).lower()


def test_without_sampling_the_route_pauses(vault):
    backlog(vault)
    server = LibrarianServer(vault, "curate", extras={
        "clerk": clerk.Scripted(clerk_answers), "fetcher": intake.Replay(RESPONSES)})
    out = run(server, lambda call: call("run_pipeline", name="clear-enrichment-backlog"))
    assert out["status"] == "paused" and "no routing model" in out["reason"]


# -- acceptance: the same scripted session, two surfaces ---------------------

def test_the_same_session_through_mcp_and_the_registry_leaves_the_same_artefacts(tmp_path):
    direct = library(tmp_path / "direct")
    ctx = Context(tier="contribute", vault=direct)
    direct_session = add_project_walk(
        direct, lambda _tool, **a: REGISTRY.call(_tool, a, ctx))

    served = library(tmp_path / "served")
    served_session = run(LibrarianServer(served, "contribute"),
                         lambda call: add_project_walk(served, call))

    left, right = artefacts(direct, direct_session), artefacts(served, served_session)
    assert sorted(left) == sorted(right)
    for rel in left:
        assert left[rel] == right[rel], rel
    offering = notes.load(served.root / "Offerings/Host Watch/Host Watch Starter.md")
    assert offering.frontmatter["session"] == served_session


def test_the_clerk_agent_answers_waiting_tasks_outside_the_thread(vault):
    """The third clerk route: no endpoint, no sampling. A review queues its
    tasks; a clerk agent on the same connection takes each one, which carries
    nothing of the thread; the review's next run uses the answers."""
    server = LibrarianServer(vault, "contribute", extras={"fetcher": intake.Replay(RESPONSES)})

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


def test_the_stdio_server_runs_as_the_plugin_launches_it(vault):
    import os
    import sys
    from mcp import StdioServerParameters
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
