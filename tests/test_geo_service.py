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
if mode == "ok":
    open(a.ready_file, "w").write(json.dumps(dict(url="http://127.0.0.1:59999/", port=59999, pid=os.getpid())))
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
        assert seen["argv"][seen["argv"].index("--library-name") + 1] == "Parallax"
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
