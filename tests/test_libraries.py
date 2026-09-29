"""Switching library in place (Co-work Roadmap §4, 2026-09-28): the same
server and token load another library, and the one it replaces retires in the
background - letting its work finish rather than cutting it off."""
import threading
import time

from resource_librarian import libraries
from resource_librarian.init import init
from resource_librarian.vault import Vault

from test_app import Client, served  # noqa: F401  (fixture)


def _second(tmp_path) -> Vault:
    init(tmp_path / "History", name="History")
    return Vault(tmp_path / "History")


def test_switching_serves_the_other_library_from_the_same_server(served, tmp_path):
    app, client, server = served
    other = _second(tmp_path)
    status, out = client.post("/api/library/switch", {"path": str(other.root)})
    assert status == 200 and out["switched"] and out["vault"] == "History"
    assert client.get("/api/state")[1]["vault"] == "History"      # same port, same token
    listed = {e["name"]: e for e in client.get("/api/libraries")[1]["libraries"]}
    assert listed["History"]["current"]
    original = str(app.vault.config()["vault"]["name"])
    assert original in listed and not listed[original]["current"]   # can go back
    assert any(e["type"] == "library_switched" for e in app.hub.since(0))   # the old page reloads


def test_a_busy_library_asks_first_then_finishes_in_the_background(served, tmp_path):
    app, client, server = served
    other = _second(tmp_path)
    app.busy = True                                   # a chat turn still answering
    status, out = client.post("/api/library/switch", {"path": str(other.root)})
    assert status == 409 and out["running"]["turn"]
    assert client.get("/api/state")[1]["vault"] != "History"      # nothing changed
    status, out = client.post("/api/library/switch", {"path": str(other.root), "force": True})
    assert status == 200 and out["finishing_in_background"]["turn"]
    closed = threading.Event()
    app.hub.subscribe(lambda e: e["type"] == "library_closed" and closed.set())
    assert not closed.wait(0.5)                       # still answering: not closed yet
    app.busy = False                                  # the turn finishes on its own
    assert closed.wait(10)                            # then the old library retires


def test_only_a_real_library_can_be_opened(served, tmp_path):
    app, client, server = served
    (tmp_path / "plain").mkdir()
    status, out = client.post("/api/library/switch", {"path": str(tmp_path / "plain")})
    assert status == 400 and "not a library" in out["error"]
    status, out = client.post("/api/library/switch", {"path": str(app.vault.root)})
    assert status == 200 and out["switched"] is False              # already open


def test_the_list_marks_a_library_whose_folder_is_gone(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    gone = _second(tmp_path)
    libraries.remember(gone)
    for p in sorted(gone.root.rglob("*"), reverse=True):
        p.unlink() if p.is_file() else p.rmdir()
    gone.root.rmdir()
    assert libraries.known()[0]["missing"]
    assert libraries.forget(str(gone.root)) and libraries.known() == []


def test_two_libraries_sharing_a_folder_name_are_told_apart(tmp_path, monkeypatch):
    """`new-vault.ps1` always names a project's vault folder `.librarian-app`, so
    the switcher must tell libraries apart by their own configured title, not
    that shared folder name."""
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    init(tmp_path / "ProjectA" / ".librarian-app", name="ProjectA")
    init(tmp_path / "ProjectB" / ".librarian-app", name="ProjectB")
    libraries.remember(Vault(tmp_path / "ProjectA" / ".librarian-app"))
    libraries.remember(Vault(tmp_path / "ProjectB" / ".librarian-app"))
    assert {e["name"] for e in libraries.known()} == {"ProjectA", "ProjectB"}
