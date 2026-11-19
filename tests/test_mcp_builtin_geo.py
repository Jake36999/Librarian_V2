"""A library's own Geo-Grapher reaches its agents as a library-owned MCP server (owner,
2026-11-18: "Built-in service"): the Core's running service over loopback HTTP, with its
per-library token as a header kept in memory, shadowing the person's mcp.json entry of the
same name. Tested against a real HTTP server that refuses a request without the token."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from resource_librarian.broker import Broker  # noqa: E402
from resource_librarian.mcp_client import McpManager  # noqa: E402
from resource_librarian.registry import REGISTRY  # noqa: E402

FAKE_HTTP = str(Path(__file__).parent / "fixtures" / "fake_mcp_http_server.py")
FAKE_STDIO = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def service():
    port, token = _free_port(), "t0ken-for-test"
    proc = subprocess.Popen([sys.executable, FAKE_HTTP, str(port)],
                            env={**os.environ, "FAKE_GEO_TOKEN": token},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.time() + 20
    while time.time() < deadline:
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/mcp", token
    proc.terminate(); proc.wait(timeout=10)


@pytest.fixture
def manager(tmp_path):
    m = McpManager(tmp_path, broker=Broker())
    yield m
    m.stop()


def test_the_library_owned_service_shadows_the_mcp_json_entry_and_answers(manager, service):
    url, token = service
    # The person's old entry: accepted, but it is not what this library's agents should reach.
    manager.set_server("geo-grapher", {"command": sys.executable, "args": [FAKE_STDIO]})
    manager.accept("geo-grapher")
    manager.set_builtin("geo-grapher", {"url": url, "headers": {"X-Geo-Token": token},
                                         "provenance_authority": "geographer"})
    status = manager.sync()["geo-grapher"]
    assert status["connected"] and status["library_owned"] and status["error"] == ""
    assert REGISTRY.external_names() == ["mcp__geo-grapher__echo"]     # not the stdio fake's two
    spec = REGISTRY.get("mcp__geo-grapher__echo")
    assert spec.provenance_authority == "geographer" and not spec.open_world
    out = manager.call_tool("geo-grapher", "echo", {"text": "hello"})
    assert out["untrusted"] is True and '"hello"' in out["content"]
    assert "X-Geo-Token" not in (manager.servers().get("geo-grapher") or {}).get("headers", {})
    assert token not in (Path(manager.config_path).read_text(encoding="utf-8"))


def test_a_wrong_token_does_not_connect_and_a_cleared_service_is_removed(manager, service):
    url, token = service
    manager.set_builtin("geo-grapher", {"url": url, "headers": {"X-Geo-Token": "wrong"}})
    status = manager.sync()["geo-grapher"]
    assert not status["connected"] and status["error"]
    manager.set_builtin("geo-grapher", {"url": url, "headers": {"X-Geo-Token": token}})
    assert manager.sync()["geo-grapher"]["connected"]                 # a new definition reconnects
    manager.clear_builtin("geo-grapher")
    assert "geo-grapher" not in manager.sync()
    assert REGISTRY.external_names() == []


def test_a_call_after_the_service_changed_is_withheld(manager, service):
    url, token = service
    manager.set_builtin("geo-grapher", {"url": url, "headers": {"X-Geo-Token": token}})
    manager.sync()
    manager.set_builtin("geo-grapher", {"url": url, "headers": {"X-Geo-Token": "rotated"}})
    assert manager.call_tool("geo-grapher", "echo", {"text": "x"})["error"] == "access_changed"


def test_only_a_loopback_http_endpoint_can_be_library_owned(manager):
    with pytest.raises(ValueError):
        manager.set_builtin("geo-grapher", {"url": "https://example.org/mcp"})
    with pytest.raises(ValueError):
        manager.set_builtin("geo-grapher", {"command": "python"})


def test_a_reserved_name_is_never_launched_from_mcp_json(manager):
    """A person-level stdio "geo-grapher" entry (the wheel is not on PyPI, so it only ever ended
    in "Connection closed") is not launched while the Core's own service is not running: the
    name is reported as library-owned and not connected, with no error of its own."""
    manager.set_server("geo-grapher", {"command": sys.executable, "args": [FAKE_STDIO]})
    manager.accept("geo-grapher")
    manager.reserve("geo-grapher")
    status = manager.sync()["geo-grapher"]
    assert status["library_owned"] and not status["connected"] and status["error"] == ""
    assert status["tools"] == 0 and REGISTRY.external_names() == []
    assert manager._clients == {}                      # nothing was started


def test_a_reserved_name_still_connects_once_the_service_runs(manager, service):
    url, token = service
    manager.reserve("geo-grapher")
    manager.set_builtin("geo-grapher", {"url": url, "headers": {"X-Geo-Token": token}})
    assert manager.sync()["geo-grapher"]["connected"]
    manager.clear_builtin("geo-grapher")
    status = manager.sync()["geo-grapher"]             # the service ended: reported, not vanished
    assert status["library_owned"] and not status["connected"]


def test_the_geo_service_hands_its_running_endpoint_to_listeners(tmp_path):
    from types import SimpleNamespace
    from resource_librarian.geo_service import GeoService
    vault = SimpleNamespace(librarian=tmp_path / ".librarian", root=tmp_path, title="t")
    geo = GeoService(vault)
    seen = []
    geo.on_change.append(seen.append)
    assert geo.mcp_definition() is None
    with geo._lock:
        geo._state, geo._info, geo.token = "running", {"port": 5123, "url": "http://127.0.0.1:5123/"}, "tok"
    geo._notify()
    assert seen[-1]["url"] == "http://127.0.0.1:5123/mcp" and seen[-1]["headers"] == {"X-Geo-Token": "tok"}
    geo.stop()
    assert seen[-1] is None and geo.mcp_definition() is None
