"""Research Pipeline §6; plan P6: optional project access.

Off by default and refused at the core, not only hidden; folders a person chose, never a
path the model names; a librarian-app/ sidecar created without overwriting anything; scans
that write maps, not copies, and a log of every read; an Application that keeps the project
work - files, proposed versus applied changes - apart, with a pointer from the project."""
import json
import threading
import time

import pytest

from resource_librarian import projects, tools  # noqa: F401  (registers tools)
from resource_librarian.broker import Broker
from resource_librarian.loop import narrowed
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore

from conftest import add_source
from test_app import served  # noqa: F401  (fixture)

PROJECT_TOOLS = {"read_project", "project_scan", "project_map", "project_edit"}


@pytest.fixture
def codebase(tmp_path):
    root = tmp_path / "hostwatch"
    (root / "hostwatch").mkdir(parents=True)
    (root / "hostwatch" / "__init__.py").write_text("")
    (root / "hostwatch" / "core.py").write_text("from . import util\nimport requests\n\n"
                                                "def collect():\n    return util.hosts()\n")
    (root / "hostwatch" / "util.py").write_text("def hosts():\n    return []\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_core.py").write_text("from hostwatch import core\n")
    (root / ".git" / "refs" / "heads").mkdir(parents=True)
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (root / ".git" / "refs" / "heads" / "main").write_text("0123456789abcdef0123456789abcdef01234567\n")
    return root


def session(vault, codebase, purpose="suggest"):
    add_source(vault.root, "osquery", "Exposes the operating system as SQL tables.")
    c = Context(tier="contribute", vault=vault)
    REGISTRY.call("create_project", {"name": "HostWatch", "stage": "active", "summary": "s",
                                     "repository": str(codebase)}, c)
    REGISTRY.call("open_session", {"purpose": purpose, "project": "HostWatch",
                                   **({"question": "q"} if purpose == "apply" else {})}, c)
    return c


def test_off_by_default_refused_at_the_core_and_hidden_from_the_model(vault, codebase):
    c = session(vault, codebase)
    for name in PROJECT_TOOLS:
        assert REGISTRY.call(name, {}, c)["refused"] == "PROJECT_ACCESS_OFF", name
    assert not PROJECT_TOOLS & {s.name for s in narrowed("contribute", projects_on=False)}
    assert PROJECT_TOOLS <= {s.name for s in narrowed("contribute", projects_on=True)}


def test_only_a_folder_a_person_added_is_read_even_when_access_is_on(vault, codebase, tmp_path):
    c = session(vault, codebase)
    projects.set_enabled(vault, True)
    assert REGISTRY.call("read_project", {}, c)["refused"] == "PROJECT_ACCESS_OFF"  # not added
    other = tmp_path / "elsewhere"
    other.mkdir()
    projects.add_root(vault, str(other), project="Something Else")
    assert REGISTRY.call("read_project", {}, c)["refused"] == "PROJECT_ACCESS_OFF"
    projects.add_root(vault, str(codebase), project="HostWatch")
    listing = REGISTRY.call("read_project", {}, c)
    assert "hostwatch/core.py" in listing["files"]
    assert not any(f.startswith("librarian-app") for f in listing["files"])
    projects.set_enabled(vault, False)                  # the same session, still open
    assert REGISTRY.call("read_project", {}, c)["refused"] == "PROJECT_ACCESS_OFF"


@pytest.mark.parametrize("bad", ["relative/path", "C:\\\\", "~"])
def test_a_folder_must_be_a_real_project_folder(vault, bad):
    with pytest.raises(TypeError):
        projects.add_root(vault, bad)


def test_the_library_itself_is_never_a_project_folder(vault):
    with pytest.raises(TypeError):
        projects.add_root(vault, str(vault.root))
    with pytest.raises(TypeError):
        projects.add_root(vault, str(vault.root / "Notes"))


def test_the_scaffold_is_created_and_never_overwritten(vault, codebase):
    first = projects.add_root(vault, str(codebase), project="HostWatch")
    app = codebase / "librarian-app"
    assert first["scaffold"]["state"] == "created"
    assert {p.name for p in app.iterdir()} == {"manifest.json", "README.md", ".gitignore",
                                               "data", "information", "sessions",
                                               "applications", "index", "logs"}
    manifest = json.loads((app / "manifest.json").read_text())
    assert manifest["root"] == str(codebase.resolve()) and manifest["schema_version"] == 1
    (app / "README.md").write_text("my own notes about this folder")
    again = projects.add_root(vault, str(codebase), project="HostWatch")
    assert again["scaffold"]["state"] == "present"
    assert (app / "README.md").read_text() == "my own notes about this folder"
    assert not (codebase / ".gitignore").exists()       # the project's own is never touched


def test_a_scan_writes_maps_not_copies_and_is_logged(vault, codebase):
    c = session(vault, codebase)
    projects.set_enabled(vault, True)
    projects.add_root(vault, str(codebase), project="HostWatch")
    out = REGISTRY.call("project_scan", {}, c)
    assert out["revision"] == "0123456789abcdef0123456789abcdef01234567"
    mapped = REGISTRY.call("project_map", {"kind": "module"}, c)
    assert {d["locator"] for d in mapped["components"]} >= {"hostwatch/core.py",
                                                            "hostwatch/util.py"}
    edges = {(e["type"], e["from"], e["to"]) for e in mapped["relations"]}
    assert ("imports", "module:hostwatch/core.py", "module:hostwatch/util.py") in edges
    assert ("depends_on", "module:hostwatch/core.py", "dependency:requests") in edges
    sidecar = [p.relative_to(codebase / "librarian-app").as_posix()
               for p in (codebase / "librarian-app").rglob("*") if p.is_file()]
    assert not [p for p in sidecar if p.endswith(".py")]           # no copies of the code
    log = (codebase / "librarian-app" / "logs" / "access.jsonl").read_text()
    assert '"event": "scan"' in log


def test_an_application_keeps_project_work_apart_with_a_pointer_from_the_project(vault, codebase):
    c = session(vault, codebase, purpose="apply")
    projects.set_enabled(vault, True)
    projects.add_root(vault, str(codebase), project="HostWatch")
    REGISTRY.call("advance", {}, c)
    REGISTRY.call("log_use", {"source": "osquery", "used_for": "host tables"}, c)
    REGISTRY.call("advance", {}, c)
    base = dict(title="Host Inventory", stage="prototype", outcome="worked",
                sources_used=["osquery"], needed="n", found_and_taken="f", replaced="r",
                should_learn="s", project_files=["hostwatch/core.py"])
    bad = REGISTRY.call("record_application", {**base, "changes": [{"change": "x",
                                                                     "status": "done"}]}, c)
    assert bad["error"] == "invalid_arguments"
    out = REGISTRY.call("record_application", {**base, "changes": [
        {"change": "query hosts through osquery", "status": "applied", "outcome": "works"},
        {"change": "drop the cron script", "status": "proposed"}]}, c)
    body = (vault.root / out["recorded"]).read_text(encoding="utf-8")
    assert "**applied**: query hosts through osquery - outcome: works" in body
    assert "**proposed**: drop the cron script" in body and "`hostwatch/core.py`" in body
    pointer = json.loads((codebase / out["project_reference"]).read_text())
    assert pointer["application"] == out["recorded"]


def test_the_projects_page_controls(served, codebase):
    app, client, _ = served
    assert client.get("/api/projects")[1] == {"enabled": False, "roots": []}
    client.post("/api/projects/enable", {"enabled": True})
    added = client.post("/api/projects/add", {"path": str(codebase), "project": "HostWatch"})[1]
    root = added["roots"][0]
    assert root["exists"] and root["scaffold"]["state"] == "created"
    assert client.post("/api/projects/add", {"path": "nowhere"})[0] == 400
    scanned = client.post("/api/projects/scan", {"id": root["id"]})[1]
    assert scanned["scanned"]["components"] > 0 and scanned["roots"][0]["last_scan"]
    assert client.post("/api/projects/remove", {"id": root["id"]})[1]["roots"] == []


# -- the project write tool (owner-approved 2026-10-01): a second, per-folder permission,
# root-confined, previewed as a diff, asked before every applied change, logged and backed up.

def editable(vault, codebase, purpose="suggest"):
    c = session(vault, codebase, purpose)
    projects.set_enabled(vault, True)
    entry = projects.add_root(vault, str(codebase), project="HostWatch")
    broker = Broker("auto")
    c.extras["broker"] = broker
    return c, entry, broker


def apply_answered(c, broker, args, answer="allow_once"):
    box = {}
    thread = threading.Thread(target=lambda: box.update(REGISTRY.call("project_edit", args, c)))
    thread.start()
    for _ in range(300):
        if broker.pending():
            break
        time.sleep(0.01)
    request = broker.pending()[0]
    broker.answer(request["id"], answer)
    thread.join(5)
    return request, box


def test_edits_are_a_separate_permission_off_for_every_folder(vault, codebase):
    c, entry, broker = editable(vault, codebase)
    args = {"path": "hostwatch/util.py", "old_text": "return []", "new_text": "return ['a']"}
    assert REGISTRY.call("project_edit", args, c)["refused"] == "PROJECT_WRITES_OFF"
    assert broker.pending() == []                       # nobody is asked about a refused edit
    assert "return []" in (codebase / "hostwatch" / "util.py").read_text()
    projects.set_writes(vault, entry["id"], True)
    projects.set_enabled(vault, False)                  # access off still wins
    assert REGISTRY.call("project_edit", args, c)["refused"] == "PROJECT_ACCESS_OFF"


def test_an_edit_is_previewed_asked_every_time_even_in_auto_and_logged_with_a_backup(vault, codebase):
    c, entry, broker = editable(vault, codebase)
    projects.set_writes(vault, entry["id"], True)
    util = codebase / "hostwatch" / "util.py"
    args = {"path": "hostwatch/util.py", "old_text": "return []", "new_text": "return ['a']"}
    dry = REGISTRY.call("project_edit", {**args, "dry_run": True}, c)
    assert dry["applied"] is False and "+    return ['a']" in dry["diff"]
    assert "return []" in util.read_text() and broker.pending() == []
    request, out = apply_answered(c, broker, args, "allow_session")
    assert request["always_ask"] and "+    return ['a']" in request["preview"]["diff"]
    assert out["applied"] and util.read_text() == "def hosts():\n    return ['a']\n"
    backup = codebase / out["backup"]
    assert backup.read_text() == "def hosts():\n    return []\n"
    assert (backup.parent / ".gitignore").read_text() == "*\n"      # backups stay out of git
    logged = [json.loads(line) for line in
              (codebase / "librarian-app" / "logs" / "access.jsonl").read_text().splitlines()]
    edit = next(e for e in logged if e["event"] == "edit")
    assert edit["revision"] == "0123456789abcdef0123456789abcdef01234567"
    assert edit["before"] and edit["after"] and edit["session"] == c.session
    assert edit["backup"] == out["backup"] and "+    return ['a']" in edit["diff"]
    events = [json.loads(line) for line in
              SessionStore(vault).path(c.session).read_text(encoding="utf-8").splitlines()]
    assert any(e.get("type") == "write" and e.get("path") == "project:hostwatch/util.py"
               for e in events)
    # "Allow for this session" grants nothing for an edit: the next one is asked again.
    again = {"path": "hostwatch/util.py", "old_text": "['a']", "new_text": "['b']"}
    request, out = apply_answered(c, broker, again, "deny")
    assert out["refused"] == "PERMISSION_DENIED" and "['a']" in util.read_text()


def test_plan_mode_previews_but_never_applies(vault, codebase):
    c, entry, _ = editable(vault, codebase)
    projects.set_writes(vault, entry["id"], True)
    c.extras["broker"] = Broker("plan")
    args = {"path": "hostwatch/util.py", "old_text": "return []", "new_text": "return ['a']"}
    assert REGISTRY.call("project_edit", {**args, "dry_run": True}, c)["diff"]
    assert REGISTRY.call("project_edit", args, c)["refused"] == "PERMISSION_DENIED"


def test_with_no_one_to_ask_an_edit_is_only_previewed(vault, codebase):
    c, entry, _ = editable(vault, codebase)
    projects.set_writes(vault, entry["id"], True)
    del c.extras["broker"]
    args = {"path": "hostwatch/util.py", "old_text": "return []", "new_text": "return ['a']"}
    assert REGISTRY.call("project_edit", args, c)["refused"] == "PERMISSION_DENIED"
    assert REGISTRY.call("project_edit", {**args, "dry_run": True}, c)["applied"] is False


@pytest.mark.parametrize("path", ["../outside.py", "librarian-app/manifest.json",
                                  "LIBRARIAN-APP/x.md", ".git/config", "hostwatch/.env",
                                  "C:/Windows/x.txt", ""])
def test_an_edit_stays_inside_the_folder_and_out_of_its_sidecar(vault, codebase, path):
    c, entry, _ = editable(vault, codebase)
    projects.set_writes(vault, entry["id"], True)
    out = REGISTRY.call("project_edit", {"path": path, "new_text": "x", "mode": "create",
                                         "dry_run": True}, c)
    assert out["error"] == "invalid_arguments", out


def test_a_snippet_must_be_unique_and_create_never_overwrites(vault, codebase):
    c, entry, broker = editable(vault, codebase)
    projects.set_writes(vault, entry["id"], True)
    core = {"path": "hostwatch/core.py", "dry_run": True}
    twice = REGISTRY.call("project_edit", {**core, "old_text": "import", "new_text": "x"}, c)
    assert "occurs 2 times" in twice["detail"]
    missing = REGISTRY.call("project_edit", {**core, "old_text": "nowhere", "new_text": "x"}, c)
    assert "occurs 0 times" in missing["detail"]
    exists = REGISTRY.call("project_edit", {**core, "mode": "create", "new_text": "x"}, c)
    assert "exists" in exists["detail"]
    gone = REGISTRY.call("project_edit", {"path": "docs/none.md", "old_text": "a",
                                          "new_text": "b", "dry_run": True}, c)
    assert "does not exist" in gone["detail"]
    (codebase / "logo.png").write_bytes(b"\x89PNG\x00\x00binary")
    binary = REGISTRY.call("project_edit", {"path": "logo.png", "old_text": "PNG",
                                            "new_text": "x", "dry_run": True}, c)
    assert "binary" in binary["detail"]
    _, out = apply_answered(c, broker, {"path": "docs/usage.md", "mode": "create",
                                        "new_text": "# Usage\n"})
    assert out["applied"] and out["backup"] == ""
    assert (codebase / "docs" / "usage.md").read_text() == "# Usage\n"


def test_a_crlf_file_keeps_its_own_line_endings(vault, codebase):
    c, entry, broker = editable(vault, codebase)
    projects.set_writes(vault, entry["id"], True)
    win = codebase / "hostwatch" / "win.py"
    win.write_bytes(b"def a():\r\n    return 1\r\n")
    _, out = apply_answered(c, broker, {"path": "hostwatch/win.py",
                                        "old_text": "def a():\n    return 1",
                                        "new_text": "def a():\n    return 2"})
    assert out["applied"] and win.read_bytes() == b"def a():\r\n    return 2\r\n"


def test_the_edits_switch_on_the_projects_page(served, codebase):
    app, client, _ = served
    client.post("/api/projects/enable", {"enabled": True})
    root = client.post("/api/projects/add", {"path": str(codebase)})[1]["roots"][0]
    assert not root.get("writes")
    on = client.post("/api/projects/writes", {"id": root["id"], "allowed": True})[1]
    assert on["roots"][0]["writes"] is True
    off = client.post("/api/projects/writes", {"id": root["id"], "allowed": False})[1]
    assert off["roots"][0]["writes"] is False
    assert client.post("/api/projects/writes", {"id": "nope", "allowed": True})[0] == 404
