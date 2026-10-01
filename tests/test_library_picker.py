"""The library picker (Test Directive, "After the report"): the desktop shortcut's first
page. It lists, opens, creates (with a domain profile), opens a folder as a library, and
forgets - and nothing but its own page can drive it."""
import json
import threading
import urllib.error
import urllib.request

import pytest

from resource_librarian import cli, libraries, library_picker
from resource_librarian.init import init
from resource_librarian.vault import Vault


@pytest.fixture
def picker(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("LIBRARIAN_LIBRARIES", str(tmp_path / "Libraries"))
    launched = []

    def launch(path):                                 # never a real app process here
        launched.append(path)
        return {"url": "http://127.0.0.1:1/", "path": path}
    monkeypatch.setattr(library_picker, "launch", launch)
    monkeypatch.setattr(library_picker, "ask_folder", lambda start="": str(tmp_path / "Picked"))
    server = library_picker._PickerServer(("127.0.0.1", 0), close_after_open=False)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    def call(path, body=None, token=server.token, origin=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Picker-Token"] = token
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(server.origin + path, method="GET" if body is None else "POST",
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                raw = response.read()
                return response.status, (json.loads(raw) if path != "/" else raw.decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")
    call.server, call.launched = server, launched
    yield call
    server.shutdown()
    server.server_close()


def test_only_its_own_page_can_drive_it(picker):
    status, page = picker("/")
    assert status == 200 and f'content="{picker.server.token}"' in page
    assert picker("/api/state", token="")[0] == 403
    assert picker("/api/create", {"name": "X"}, token="wrong")[0] == 403
    assert picker("/api/create", {"name": "X"}, origin="https://evil.example")[0] == 403
    assert picker.launched == []


def test_the_state_lists_libraries_and_the_standard_profiles(picker, tmp_path):
    init(tmp_path / "Uni", "Uni")
    libraries.remember(Vault(tmp_path / "Uni"))
    status, out = picker("/api/state")
    assert status == 200 and [e["name"] for e in out["libraries"]] == ["Uni"]
    assert {"software-systems", "course", "history"} <= {p["name"] for p in out["profiles"]}
    assert out["default_parent"] == str(tmp_path / "Libraries")


def test_create_makes_a_library_with_its_profile_and_opens_it(picker, tmp_path):
    status, out = picker("/api/create", {"name": "Software", "parent": str(tmp_path / "Libraries"),
                                         "profile": "software-systems"})
    made = tmp_path / "Libraries" / "Software"
    assert status == 200 and out["url"] and out["created"] == str(made)
    assert Vault(made).exists() and (made / ".librarian" / "profile.json").is_file()
    assert picker.launched == [str(made)]
    again = picker("/api/create", {"name": "Software", "parent": str(tmp_path / "Libraries")})[1]
    assert "already a library" in again["error"]


def test_create_refuses_a_bad_name_and_a_folder_with_things_in_it(picker, tmp_path):
    for name in ("a/b", "what?", "con", "trailing.", "  "):
        assert "can't be a folder name" in picker("/api/create", {"name": name})[1]["error"]
    (tmp_path / "Libraries" / "Notes").mkdir(parents=True)
    (tmp_path / "Libraries" / "Notes" / "mine.md").write_text("mine", encoding="utf-8")
    out = picker("/api/create", {"name": "Notes", "parent": str(tmp_path / "Libraries")})[1]
    assert "already has things in it" in out["error"]
    assert picker.launched == []


def test_a_folder_is_made_a_library_only_when_asked_and_keeps_what_it_holds(picker, tmp_path):
    folder = tmp_path / "Thesis"
    folder.mkdir()
    (folder / "README.md").write_text("my own readme", encoding="utf-8")
    (folder / "draft.md").write_text("chapter one", encoding="utf-8")
    seen = picker("/api/inspect", {"path": str(folder)})[1]
    assert seen == {"path": str(folder), "exists": True, "library": "", "entries": 2}
    assert "is not a library" in picker("/api/open", {"path": str(folder)})[1]["error"]
    status, out = picker("/api/create", {"folder": str(folder), "adopt": True,
                                         "profile": "course"})
    assert status == 200 and out["created"] == str(folder) and Vault(folder).exists()
    assert (folder / "README.md").read_text(encoding="utf-8") == "my own readme"
    assert (folder / "draft.md").read_text(encoding="utf-8") == "chapter one"


def test_a_folder_inside_a_library_opens_that_library_and_is_never_nested(picker, tmp_path):
    init(tmp_path / "Uni", "Uni")
    inner = tmp_path / "Uni" / "Projects"
    assert picker("/api/inspect", {"path": str(inner)})[1]["library"] == str(tmp_path / "Uni")
    out = picker("/api/create", {"folder": str(inner), "adopt": True})[1]
    assert "is inside the library" in out["error"]
    assert picker("/api/open", {"path": str(inner)})[1]["url"]
    assert picker.launched == [str(tmp_path / "Uni")]
    missing = picker("/api/inspect", {"path": str(tmp_path / "Nowhere")})[1]
    assert missing["exists"] is False
    assert "give the folder's full path" in picker("/api/inspect", {"path": "relative"})[1]["error"]


def test_forget_takes_it_off_the_list_and_leaves_the_folder(picker, tmp_path):
    init(tmp_path / "Uni", "Uni")
    libraries.remember(Vault(tmp_path / "Uni"))
    assert picker("/api/forget", {"path": str(tmp_path / "Uni")})[1]["forgotten"] is True
    assert picker("/api/state")[1]["libraries"] == []
    assert Vault(tmp_path / "Uni").exists()


def test_browse_returns_the_folder_chosen(picker, tmp_path):
    assert picker("/api/browse", {})[1] == {"path": str(tmp_path / "Picked")}


def test_app_pick_starts_at_the_picker(monkeypatch):
    seen = {}
    monkeypatch.setattr(library_picker, "serve_picker",
                        lambda port, open_browser: seen.update(port=port, open=open_browser) or 0)
    assert cli.main(["app", "--pick", "--port", "0", "--open"]) == 0
    assert seen == {"port": 0, "open": True}


def test_a_library_is_named_by_its_title_not_its_folder(tmp_path, monkeypatch):
    """Two new-vault.ps1 libraries both live in folders named `.librarian-app`: the app,
    the switcher and the threads list name them by their own titles."""
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    init(tmp_path / "Uni" / ".librarian-app", "Librarian-Uni")
    vault = Vault(tmp_path / "Uni" / ".librarian-app")
    assert vault.title == "Librarian-Uni" and vault.root.name == ".librarian-app"
    libraries.remember(vault)
    assert libraries.known()[0]["name"] == "Librarian-Uni"
    state = App(vault, token="t", keys=KeyStore(use_keyring=False)).state()
    assert state["vault_name"] == "Librarian-Uni" and state["vault"] == ".librarian-app"
