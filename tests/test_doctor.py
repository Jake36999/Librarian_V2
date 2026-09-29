"""doctor's per-server MCP checks (Co-work Roadmap §3, Phase 2): configured,
accepted, and - only when a live McpManager is passed - actually connected.
A throwaway manager (no live manager given) never starts a connection; it
only ever reads mcp.json/mcp_accepted.json, same as the settings page's
status view."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from resource_librarian import doctor  # noqa: E402
from resource_librarian.mcp_client import McpManager  # noqa: E402

FAKE_SERVER = str(Path(__file__).parent / "fixtures" / "fake_mcp_server.py")


def _names(checks):
    return [c.name for c in checks]


def test_no_configured_servers_gives_no_mcp_server_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path))
    names = _names(doctor.checks(None))
    assert not any(n.startswith("mcp: ") for n in names)


def test_configured_but_not_accepted_is_reported_without_a_live_manager(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path))
    McpManager(tmp_path).set_server("fake", {"command": sys.executable, "args": [FAKE_SERVER]})
    checks = {c.name: c for c in doctor.checks(None)}
    assert checks["mcp: fake"].ok is True
    assert "not accepted" in checks["mcp: fake"].detail


def test_a_disabled_server_is_reported_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path))
    manager = McpManager(tmp_path)
    manager.set_server("fake", {"command": sys.executable, "args": [FAKE_SERVER], "enabled": False})
    checks = {c.name: c for c in doctor.checks(None)}
    assert checks["mcp: fake"] == doctor.Check("mcp: fake", True, "disabled")


def test_accepted_but_no_live_manager_says_it_was_not_checked_here(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path))
    manager = McpManager(tmp_path)
    manager.set_server("fake", {"command": sys.executable, "args": [FAKE_SERVER]})
    manager.accept("fake")
    checks = {c.name: c for c in doctor.checks(None)}
    assert checks["mcp: fake"].ok is True
    assert "not running here" in checks["mcp: fake"].detail


def test_a_live_manager_reports_a_real_connection_and_tool_count(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path))
    manager = McpManager(tmp_path)
    manager.set_server("fake", {"command": sys.executable, "args": [FAKE_SERVER]})
    manager.accept("fake")
    manager.sync()
    try:
        checks = {c.name: c for c in doctor.checks(None, manager)}
        assert checks["mcp: fake"] == doctor.Check("mcp: fake", True, "2 tool(s), connected")
    finally:
        manager.stop()


def test_a_live_manager_reports_a_connection_error_as_not_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path))
    manager = McpManager(tmp_path)
    manager.set_server("broken", {"command": "no-such-executable-anywhere"})
    manager.accept("broken")
    manager.sync()
    try:
        checks = {c.name: c for c in doctor.checks(None, manager)}
        assert checks["mcp: broken"].ok is False
        assert checks["mcp: broken"].detail
    finally:
        manager.stop()


# -- recommended Obsidian plugins (Co-work Roadmap §2, "How delegation works") -
# Each test isolates LIBRARIAN_CONFIG_DIR too: these exercise the Obsidian-
# plugin check, not the MCP one, and a plain `doctor.checks(vault)` call
# would otherwise read whatever mcp.json a real machine happens to have.

def test_no_obsidian_folder_gives_no_plugin_check(vault, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(vault.root.parent / "config"))
    names = _names(doctor.checks(vault))
    assert "obsidian plugins" not in names


def test_an_empty_enabled_list_gives_no_plugin_check(vault, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(vault.root.parent / "config"))
    obsidian = vault.root / ".obsidian"
    obsidian.mkdir()
    (obsidian / "community-plugins.json").write_text("[]")
    names = _names(doctor.checks(vault))
    assert "obsidian plugins" not in names


def test_recommended_plugins_enabled_are_named_by_their_display_name(vault, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(vault.root.parent / "config"))
    obsidian = vault.root / ".obsidian"
    obsidian.mkdir()
    (obsidian / "community-plugins.json").write_text(
        '["dataview", "obsidian-tasks-plugin", "some-unrelated-plugin"]')
    checks = {c.name: c for c in doctor.checks(vault)}
    assert checks["obsidian plugins"] == doctor.Check(
        "obsidian plugins", True, "Dataview, Tasks")


def test_a_malformed_community_plugins_file_is_never_a_crash(vault, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(vault.root.parent / "config"))
    obsidian = vault.root / ".obsidian"
    obsidian.mkdir()
    (obsidian / "community-plugins.json").write_text("not json")
    names = _names(doctor.checks(vault))
    assert "obsidian plugins" not in names
