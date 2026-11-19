"""Each library's Geo-Grapher is run by that library's Core (owner, 2026-11-15).

The Core starts `serve-graphs` for the library's own catalog when it starts the
library, on a port the service chooses, with a per-library token passed through
the environment, and stops it when the library closes. A fake command stands in
for the pinned wheel, so no real Geo-Grapher is needed here.
"""
import json
import os
import sys
import time
from pathlib import Path

import pytest

from resource_librarian.init import init
from resource_librarian.vault import Vault

FAKE = r'''
import json, os, sys, time, argparse
p = argparse.ArgumentParser(); p.add_argument("op")
for flag in ("--catalog", "--transport", "--port", "--ready-file", "--librarian-url", "--library-name"):
    p.add_argument(flag)
p.add_argument("--create-catalog", action="store_true")
a, _ = p.parse_known_args()
mode = os.environ.get("FAKE_GEO_MODE", "ok")
record = dict(argv=sys.argv[1:], token_seen=bool(os.environ.get("GEOGRAPHER_ACCESS_TOKEN")), pid=os.getpid())
open(os.environ["FAKE_GEO_RECORD"], "w").write(json.dumps(record))
if mode == "old_wheel":
    sys.stderr.write("serve-graphs: error: unrecognized arguments: --ready-file\n"); sys.exit(2)
if mode in ("ok", "closes", "crashes"):
    open(a.ready_file, "w").write(json.dumps(dict(url="http://127.0.0.1:59999/", port=59999, pid=os.getpid())))
if mode == "split":                      # a launcher that outlives its listener, as a Windows venv launcher can
    import subprocess
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    open(os.environ["FAKE_GEO_RECORD"] + ".child", "w").write(str(child.pid))
    open(a.ready_file, "w").write(json.dumps(dict(url="http://127.0.0.1:59999/", port=59999, pid=child.pid)))
if mode in ("closes", "crashes"):        # closed from its own window, or ended on its own
    time.sleep(0.6); sys.exit(0 if mode == "closes" else 3)
while True:
    time.sleep(0.2)
'''


@pytest.fixture
def library(tmp_path, monkeypatch):
    root = tmp_path / "Parallax"
    init(root, name="Parallax")
    vault = Vault(root)
    fake = tmp_path / "fake_geo.py"
    fake.write_text(FAKE, encoding="utf-8")
    record = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_GEO_RECORD", str(record))
    (vault.librarian / "geographer.json").write_text(json.dumps(
        dict(enabled=True, command=[sys.executable, str(fake)], wheel_version="0.2.0")), encoding="utf-8")
    return vault, record


def _wait(service, states, seconds=20):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if service.status()["state"] in states:
            return service.status()
        time.sleep(0.05)
    return service.status()


def test_a_library_start_runs_its_own_geo_grapher_with_a_hidden_token(library):
    from resource_librarian.geo_service import GeoService
    vault, record = library
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    try:
        status = _wait(service, {"running", "failed"})
        assert status["state"] == "running", status
        assert status["url"] == "http://127.0.0.1:59999/"
        seen = json.loads(record.read_text())
        assert seen["token_seen"] is True
        assert service.token and service.token not in " ".join(seen["argv"])   # never in argv
        assert "--create-catalog" in seen["argv"] and "--port" in seen["argv"]
        catalog = seen["argv"][seen["argv"].index("--catalog") + 1]
        assert Path(catalog) == vault.librarian / "geographer" / "catalog.sqlite"
        assert seen["argv"][seen["argv"].index("--librarian-url") + 1] == "http://127.0.0.1:52206/"
        assert seen["argv"][seen["argv"].index("--library-name") + 1] == vault.title == "Parallax"
        assert status["library"] == vault.title
        assert service.open_url() == f"http://127.0.0.1:59999/?geo_token={service.token}"
        assert service.token not in json.dumps(status)                         # status never leaks it
    finally:
        service.stop()
    assert service.status()["state"] == "stopped"
    pid = json.loads(record.read_text())["pid"]
    assert not _alive(pid)


def test_disabled_libraries_start_nothing(library):
    from resource_librarian.geo_service import GeoService
    vault, record = library
    (vault.librarian / "geographer.json").write_text(json.dumps(dict(enabled=False)), encoding="utf-8")
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    assert service.status()["state"] == "disabled" and not record.exists()
    assert service.open_url() is None


def test_an_old_wheel_is_reported_with_the_fix(library, monkeypatch):
    from resource_librarian.geo_service import GeoService
    vault, _ = library
    monkeypatch.setenv("FAKE_GEO_MODE", "old_wheel")
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    status = _wait(service, {"failed"})
    assert status["state"] == "failed" and "rebuild" in status["error"].lower()


def test_a_service_that_never_reports_ready_is_stopped(library, monkeypatch):
    from resource_librarian.geo_service import GeoService
    vault, record = library
    monkeypatch.setenv("FAKE_GEO_MODE", "silent")
    service = GeoService(vault, ready_timeout=1.0)
    service.start("http://127.0.0.1:52206/")
    status = _wait(service, {"failed"})
    assert status["state"] == "failed" and "ready" in status["error"].lower()
    time.sleep(0.5)
    assert not _alive(json.loads(record.read_text())["pid"])


def _alive(pid):
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259                                          # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def test_an_app_never_starts_geo_by_itself_and_closing_the_library_stops_it(library):
    """Hundreds of tests build Apps: only serve()/switch() start the service."""
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    vault, record = library
    app = App(vault, token="t", keys=KeyStore(use_keyring=False))
    try:
        assert app.geo.status()["state"] == "stopped" and not record.exists()
        app.geo.start("http://127.0.0.1:52206/")
        assert _wait(app.geo, {"running", "failed"})["state"] == "running"
        pid = json.loads(record.read_text())["pid"]
    finally:
        app.close_runtime()
    assert app.geo.status()["state"] == "stopped" and not _alive(pid)


def test_stop_never_ends_a_process_a_stale_ready_file_names(library):
    """A ready file left by an earlier run must not point stop() at a reused pid."""
    import subprocess
    from resource_librarian.geo_service import GeoService
    vault, _ = library
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        runtime = vault.librarian / "runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "geographer-ready.json").write_text(
            json.dumps(dict(url="http://127.0.0.1:1/", port=1, pid=bystander.pid)), encoding="utf-8")
        service = GeoService(vault)          # this session never started a service
        service.stop()
        time.sleep(0.5)
        assert bystander.poll() is None and _alive(bystander.pid)
    finally:
        bystander.kill()


def test_stop_ends_only_the_listener_it_recorded(library):
    """If the recorded listener's pid now belongs to another process, leave it alone."""
    import subprocess
    from resource_librarian.geo_service import GeoService
    vault, _ = library
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    bystander = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert _wait(service, {"running", "failed"})["state"] == "running"
        service._info = {**service._info, "pid": bystander.pid}      # as if the pid were reused
        service.stop()
        time.sleep(0.5)
        assert bystander.poll() is None
    finally:
        bystander.kill()


def test_the_service_is_told_which_process_owns_it(library):
    from resource_librarian.geo_service import GeoService
    vault, record = library
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    try:
        assert _wait(service, {"running", "failed"})["state"] == "running"
        argv = json.loads(record.read_text())["argv"]
        assert argv[argv.index("--parent-pid") + 1] == str(os.getpid())
    finally:
        service.stop()


@pytest.mark.parametrize("mode, state", [("closes", "stopped"), ("crashes", "failed")])
def test_a_service_that_exits_is_not_reported_running_and_can_start_again(library, monkeypatch, mode, state):
    """2026-11-17: Geo-Grapher gained a Close button; the Core must not keep offering its address."""
    from resource_librarian.geo_service import GeoService
    vault, record = library
    monkeypatch.setenv("FAKE_GEO_MODE", mode)
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    try:
        assert _wait(service, {"running", "failed"})["state"] == "running"
        status = _wait(service, {"stopped", "failed"})
        assert status["state"] == state
        assert (status["error"] == "") == (mode == "closes")
        assert service.open_url() is None
        assert not (vault.librarian / "runtime" / "geographer-ready.json").exists()
        monkeypatch.setenv("FAKE_GEO_MODE", "ok")
        service.start("http://127.0.0.1:52206/")
        assert _wait(service, {"running", "failed"})["state"] == "running"
    finally:
        service.stop()


def test_a_listener_ended_from_outside_is_not_reported_running(library, monkeypatch):
    """2026-11-17: a Geo-Grapher ended from outside (not by the Core) left its Core offering the address
    of a server that no longer existed, so the Geo-Grapher button opened a dead page and could not start
    a new one. The listener's own liveness decides, not only the launcher's."""
    import signal
    from resource_librarian.geo_service import GeoService
    vault, record = library
    monkeypatch.setenv("FAKE_GEO_MODE", "split")
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    try:
        assert _wait(service, {"running", "failed"})["state"] == "running"
        assert service.open_url() is not None
        child = int(Path(str(record) + ".child").read_text())
        launcher = json.loads(record.read_text())["pid"]
        os.kill(child, signal.SIGTERM)                       # the real server goes; its launcher stays
        status = _wait(service, {"stopped", "failed"})
        assert status["state"] == "failed" and "GEOGRAPHER_EXITED" in status["error"], status
        assert service.open_url() is None and status["url"] is None
        assert not _alive(launcher)                          # the leftover launcher is ended too
        monkeypatch.setenv("FAKE_GEO_MODE", "ok")
        service.start("http://127.0.0.1:52206/")             # and the button can start it again
        assert _wait(service, {"running", "failed"})["state"] == "running"
    finally:
        service.stop()


def test_the_person_ui_can_close_and_reopen_this_librarys_geo_grapher(vault, tmp_path, monkeypatch):
    """2026-11-17: a close control per Core. Closing Geo-Grapher leaves the Core running."""
    import threading
    from resource_librarian.app import App, build
    from resource_librarian.keys import KeyStore
    from test_app import Client
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    calls = []

    class Geo:
        state = "running"
        def stop(self): calls.append("stop"); Geo.state = "stopped"
        def start(self, url): calls.append(("start", url)); Geo.state = "running"
        def status(self): return {"state": Geo.state, "error": "", "url": None, "library": "x"}
        def open_url(self): return "http://127.0.0.1:1/?geo_token=t" if Geo.state == "running" else None

    app = App(vault, token="test-token", keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.geo = Geo()
    server = build(app)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        client = Client(server, "test-token")
        assert client.post("/api/geographer/stop", token=False)[0] == 403       # person UI only
        code, out = client.post("/api/geographer/stop")
        assert code == 200 and out["state"] == "stopped" and out["open_url"] is None
        assert client.post("/api/geographer/start")[0] == 409                    # no address yet
        server.board.url = "http://127.0.0.1:5555/"
        code, out = client.post("/api/geographer/start")
        assert code == 200 and out["state"] == "running" and out["open_url"]
        assert calls == ["stop", ("start", "http://127.0.0.1:5555/")]
    finally:
        server.shutdown(); server.server_close()


def _argv_of(vault, record):
    from resource_librarian.geo_service import GeoService
    service = GeoService(vault)
    service.start("http://127.0.0.1:52206/")
    try:
        assert _wait(service, {"running", "failed"})["state"] == "running"
        return json.loads(record.read_text())["argv"]
    finally:
        service.stop()


def _attach(vault, *folders):
    (vault.librarian / "projects.json").write_text(json.dumps(
        {"enabled": True, "roots": [{"id": f"r{i}", "path": str(f)} for i, f in enumerate(folders)]}), encoding="utf-8")


def test_a_librarys_geo_may_browse_the_project_folders_its_person_attached(library, tmp_path):
    """F-05 (agent review 2026-11-19): with no browse roots, "Add folder" in a library's Geo always failed."""
    vault, record = library
    attached, gone = tmp_path / "attached-project", tmp_path / "moved-away"
    attached.mkdir()
    _attach(vault, attached, attached, gone)               # a duplicate and a folder that no longer exists
    argv = _argv_of(vault, record)
    roots = [argv[i + 1] for i, a in enumerate(argv) if a == "--browse-root"]
    assert roots == [str(attached)]


def test_geo_browses_nothing_until_project_access_is_on_and_a_folder_is_attached(library, tmp_path):
    vault, record = library
    assert "--browse-root" not in _argv_of(vault, record)                      # nothing attached
    folder = tmp_path / "attached-project"
    folder.mkdir()
    (vault.librarian / "projects.json").write_text(json.dumps(
        {"enabled": False, "roots": [{"id": "r0", "path": str(folder)}]}), encoding="utf-8")
    assert "--browse-root" not in _argv_of(vault, record)                      # attached, but project access is off
