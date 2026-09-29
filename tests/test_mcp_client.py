"""The MCP client (Co-work Roadmap §3, Phase 1): mcp.json, digest-based
acceptance, dynamic tool registration, and the untrusted-wrapped bridge -
against a real stdio subprocess (`tests/fixtures/fake_mcp_server.py`), not
just an in-process fake, since the whole point is a real anyio connection
held open across separate sync calls."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from resource_librarian.broker import Broker  # noqa: E402
from resource_librarian.mcp_client import McpManager, digest  # noqa: E402
from resource_librarian.registry import REGISTRY, Context  # noqa: E402

FAKE_SERVER = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


@pytest.fixture
def manager(tmp_path):
    m = McpManager(tmp_path, broker=Broker())
    yield m
    m.stop()


def fake_definition(**overrides):
    return {"command": sys.executable, "args": [FAKE_SERVER], **overrides}


def test_config_round_trips(manager):
    assert manager.servers() == {}
    manager.set_server("fake", fake_definition())
    assert manager.servers()["fake"]["command"] == sys.executable
    manager.remove_server("fake")
    assert manager.servers() == {}


def test_acceptance_ignores_the_enabled_flag_but_not_the_command(manager):
    manager.set_server("fake", fake_definition())
    definition = manager.servers()["fake"]
    manager.accept("fake")
    assert manager.is_accepted("fake", definition)
    # Toggling enabled alone never invalidates acceptance.
    manager.set_server("fake", {**definition, "enabled": False})
    assert manager.is_accepted("fake", manager.servers()["fake"])
    # A changed command does.
    manager.set_server("fake", {**definition, "args": [FAKE_SERVER, "--extra"]})
    assert not manager.is_accepted("fake", manager.servers()["fake"])


def test_accept_refuses_an_unknown_server(manager):
    with pytest.raises(ValueError):
        manager.accept("nope")


def test_sync_never_connects_an_unaccepted_or_disabled_server(manager):
    manager.set_server("fake", fake_definition())
    status = manager.sync()                                    # not accepted yet
    assert status["fake"] == {"enabled": True, "accepted": False, "connected": False,
                              "tools": 0, "error": "", "unpinned": ""}
    manager.accept("fake")
    manager.set_server("fake", {**manager.servers()["fake"], "enabled": False})
    status = manager.sync()
    assert status["fake"]["connected"] is False
    assert REGISTRY.external_names() == []


def test_sync_connects_an_accepted_enabled_server_and_registers_its_tools(manager):
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    status = manager.sync()
    assert status["fake"] == {"enabled": True, "accepted": True, "connected": True,
                              "tools": 2, "error": "", "unpinned": ""}
    assert REGISTRY.external_names() == ["mcp__fake__boom", "mcp__fake__echo"]
    assert sorted(manager.tool_names("fake")) == ["mcp__fake__boom", "mcp__fake__echo"]
    spec = REGISTRY.get("mcp__fake__echo")
    assert spec.external and spec.tier == "contribute" and spec.needs_vault is False
    assert spec.effect == "read"                                 # readOnlyHint on the fake tool
    assert REGISTRY.get("mcp__fake__boom").effect == "write"     # no hint: the cautious default


def test_broker_is_seeded_ask_but_a_persons_own_setting_is_kept(manager):
    manager.broker.set_tool("mcp__fake__echo", "allow")          # a person's own choice, first
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.sync()
    assert manager.broker.settings["mcp__fake__echo"] == "allow"    # not clobbered
    assert manager.broker.settings["mcp__fake__boom"] == "ask"       # the seeded default


def test_call_tool_wraps_the_result_as_untrusted(manager):
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.sync()
    ctx = Context(tier="contribute")
    out = REGISTRY.call("mcp__fake__echo", {"text": "hello"}, ctx)
    assert out == {"server": "fake", "tool": "echo", "untrusted": True,
                   "is_error": False, "content": '{"text": "hello"}'}


def test_call_tool_surfaces_a_server_side_error_without_raising(manager):
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.sync()
    out = REGISTRY.call("mcp__fake__boom", {}, Context(tier="contribute"))
    assert out["untrusted"] is True and out["is_error"] is True and out["content"] == "kaput"


def test_a_lower_tier_cannot_call_an_external_tool(manager):
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.sync()
    out = REGISTRY.call("mcp__fake__echo", {"text": "x"}, Context(tier="consult"))
    assert out["refused"] == "TIER_REFUSED"


def test_disabling_a_server_unregisters_its_tools(manager):
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.sync()
    assert REGISTRY.external_names()
    manager.set_server("fake", {**manager.servers()["fake"], "enabled": False})
    manager.sync()
    assert REGISTRY.external_names() == []
    out = REGISTRY.call("mcp__fake__echo", {"text": "x"}, Context(tier="contribute"))
    assert out["refused"] == "CLOSED_ACTION_REGISTRY"


def test_stop_unregisters_everything_and_is_idempotent(manager):
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.sync()
    manager.stop()
    assert REGISTRY.external_names() == []
    manager.stop()                                      # a second stop is a no-op, not an error


def test_calling_a_disconnected_server_fails_loudly_not_silently(manager):
    out = manager.call_tool("nope", "echo", {})
    assert out["error"] == "unavailable"


def test_digest_is_stable_regardless_of_key_order():
    a = digest({"command": "x", "args": ["1", "2"], "env": {"A": "1", "B": "2"}})
    b = digest({"env": {"B": "2", "A": "1"}, "args": ["1", "2"], "command": "x"})
    assert a == b


# -- registry browsing (Co-work Roadmap §3, Phase 2) -------------------------
# Against a real local HTTP server (matching test_clerk.py's precedent) built
# from the actual shape registry.modelcontextprotocol.io/v0/servers returns
# (confirmed live on 2026-09-27), not the real network: this suite must pass
# with no internet, and a fixed fixture pins the parsing to a known shape.

import json as _json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import resource_librarian.mcp_client as mcp_client

REGISTRY_PAGE = {"servers": [
    {"server": {"name": "io.github.smaniches/semantic-scholar-mcp",
               "title": "Semantic Scholar MCP Server",
               "description": "Search 200M+ papers, citations, authors.",
               "repository": {"url": "https://github.com/smaniches/semantic-scholar-mcp"},
               "packages": [{"registryType": "pypi", "identifier": "s2-mcp-server",
                            "runtimeHint": "uvx", "transport": {"type": "stdio"},
                            "environmentVariables": [
                                {"name": "SEMANTIC_SCHOLAR_API_KEY",
                                 "description": "higher rate limits", "isSecret": True}]}]}},
    {"server": {"name": "io.github.example/npm-tool",
               "description": "An npm-packaged stdio server.",
               "packages": [{"registryType": "npm", "identifier": "example-mcp-tool",
                            "transport": {"type": "stdio"}}]}},
    {"server": {"name": "ai.example/remote-only",
               "description": "A hosted server, no local package.",
               "remotes": [{"type": "streamable-http", "url": "https://example.com/mcp"}]}},
    {"server": {"name": "io.github.example/docker-tool",
               "description": "Needs Docker and its own runtime arguments.",
               "packages": [{"registryType": "oci", "identifier": "example/tool",
                            "transport": {"type": "stdio"},
                            "runtimeArguments": [{"type": "positional", "value": "--rm"}]}]}},
]}


class _FakeRegistry(BaseHTTPRequestHandler):
    def do_GET(self):                                       # noqa: N802
        _FakeRegistry.seen.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(_json.dumps(REGISTRY_PAGE).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake_registry(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _FakeRegistry)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _FakeRegistry.seen = []
    monkeypatch.setattr(mcp_client, "REGISTRY_SEARCH_URL",
                        f"http://127.0.0.1:{server.server_address[1]}/v0/servers")
    yield _FakeRegistry
    server.shutdown()


def test_search_registry_sends_the_query_and_a_limit(fake_registry, manager):
    manager.search_registry("semantic scholar", limit=5)
    assert len(fake_registry.seen) == 1
    assert "search=semantic" in fake_registry.seen[0] and "limit=5" in fake_registry.seen[0]


def test_search_registry_resolves_a_pypi_stdio_package_via_uvx(fake_registry, manager):
    out = manager.search_registry("semantic")
    entry = next(s for s in out["servers"] if s["name"].endswith("semantic-scholar-mcp"))
    assert entry["resolvable"] is True
    assert entry["server"] == {"command": "uvx", "args": ["s2-mcp-server"],
                              "env": {"SEMANTIC_SCHOLAR_API_KEY": "${SEMANTIC_SCHOLAR_API_KEY}"}}
    assert entry["env"] == [{"name": "SEMANTIC_SCHOLAR_API_KEY", "required": False, "secret": True}]


def test_search_registry_resolves_an_npm_stdio_package_via_npx(fake_registry, manager):
    out = manager.search_registry("")
    entry = next(s for s in out["servers"] if s["name"].endswith("npm-tool"))
    assert entry["resolvable"] is True
    assert entry["server"] == {"command": "npx", "args": ["-y", "example-mcp-tool"], "env": {}}


def test_search_registry_marks_a_remote_only_server_unresolvable_with_a_reason(fake_registry, manager):
    out = manager.search_registry("")
    entry = next(s for s in out["servers"] if s["name"].endswith("remote-only"))
    assert entry["resolvable"] is False and "server" not in entry
    assert "OAuth" in entry["reason"] or "bearer" in entry["reason"]


def test_search_registry_marks_a_docker_package_unresolvable_with_a_reason(fake_registry, manager):
    out = manager.search_registry("")
    entry = next(s for s in out["servers"] if s["name"].endswith("docker-tool"))
    assert entry["resolvable"] is False and "server" not in entry


def test_search_registry_never_raises_when_the_registry_is_unreachable(manager, monkeypatch):
    monkeypatch.setattr(mcp_client, "REGISTRY_SEARCH_URL", "http://127.0.0.1:1/v0/servers")
    out = manager.search_registry("anything")
    assert out["servers"] == [] and "error" in out
