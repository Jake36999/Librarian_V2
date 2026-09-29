"""Outside MCP servers are installed once, for the person, and enabled per
library, default off (Co-work Roadmap §4 F1): one library per domain means a
scholarly-search server belongs in a history library and not a software one."""
from resource_librarian.init import init
from resource_librarian.mcp_client import McpManager
from resource_librarian.vault import Vault

from test_mcp_client import fake_definition


def _libraries(tmp_path):
    for name in ("Software", "History"):
        init(tmp_path / name, name=name)
    return Vault(tmp_path / "Software"), Vault(tmp_path / "History")


def test_an_installed_server_is_off_in_every_library_until_that_library_turns_it_on(tmp_path):
    software, history = _libraries(tmp_path)
    manager = McpManager(tmp_path / "config")
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    try:
        manager.use_library(history.librarian)
        assert manager.sync()["fake"]["connected"] is False          # installed, not enabled
        manager.set_library_enabled("fake", True)
        status = manager.sync()["fake"]
        assert status["connected"] and status["library_enabled"]
        manager.use_library(software.librarian)                      # a library switch
        status = manager.sync()["fake"]
        assert status["connected"] is False and status["library_enabled"] is False
        manager.use_library(history.librarian)
        assert manager.sync()["fake"]["connected"]                   # its own choice kept
    finally:
        manager.stop()


def test_a_redefined_server_stays_on_but_says_it_changed(tmp_path):
    _, history = _libraries(tmp_path)
    manager = McpManager(tmp_path / "config")
    manager.use_library(history.librarian)
    manager.set_server("fake", fake_definition())
    manager.accept("fake")
    manager.set_library_enabled("fake", True)
    manager.set_server("fake", {**fake_definition(), "args": [*fake_definition()["args"], "--x"]})
    manager.accept("fake")
    status = manager.status()["fake"]
    assert status["library_enabled"] and status["changed_since_enabled"]


def test_the_global_installed_switch_still_stops_it_everywhere(tmp_path):
    _, history = _libraries(tmp_path)
    manager = McpManager(tmp_path / "config")
    manager.use_library(history.librarian)
    manager.set_server("fake", fake_definition(enabled=False))
    manager.accept("fake")
    manager.set_library_enabled("fake", True)
    try:
        assert manager.sync()["fake"]["connected"] is False
    finally:
        manager.stop()


def test_without_a_library_nothing_is_filtered(tmp_path):
    """The CLI and a bare manager are not scoped to a library."""
    assert McpManager(tmp_path / "config").enabled_here("anything")
