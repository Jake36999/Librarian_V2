"""Reopening a library whose Core is still running (A1).

Closing the tab leaves the Core running. Opening the library again opens that
Core instead of building a second one; a stale lease is put to the person on a
page; a live process that does not answer is refused by name.
"""
from __future__ import annotations

import io
import json
import os
import socket
import threading
import urllib.error
import urllib.request

import pytest

from resource_librarian import app as app_module, connection, library_picker, process_identity, reopen
from resource_librarian.coordination import LeaseHeldError, StaleLeaseError


@pytest.fixture
def config(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("LIBRARIAN_HOST_MANAGED", raising=False)
    monkeypatch.delenv("LIBRARIAN_VAULT_TAKEOVER", raising=False)
    monkeypatch.delenv("LIBRARIAN_VAULT", raising=False)


@pytest.fixture
def said(monkeypatch):
    lines: list[dict] = []
    monkeypatch.setattr(app_module, "_announce", lines.append)
    return lines


def _closed_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def _publish(vault, url: str) -> None:
    assert connection.publish(vault.root, url=url, token="page-secret", pid=os.getpid(),
                              protocol_version=app_module.PROTOCOL_VERSION,
                              secret_source="desktop",
                              process_start=process_identity.process_start(os.getpid()))


def _no_second_core(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("a second Core was built for a library that is already open")
    monkeypatch.setattr(app_module, "App", refuse)


def test_reopening_a_running_library_opens_its_core(vault, config, said, monkeypatch):
    core = app_module.App(vault, coordinate=True)
    server = app_module.build(core, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        connection.publish(vault.root, url=url, token=core.token, pid=os.getpid(),
                           protocol_version=app_module.PROTOCOL_VERSION,
                           secret_source=core.secret_source,
                           process_start=process_identity.process_start(os.getpid()))
        opened: list[str] = []
        monkeypatch.setattr("webbrowser.open", opened.append)
        _no_second_core(monkeypatch)

        assert app_module.serve(str(vault.root), port=0, open_browser=True) == 0
        assert said == [{"attached": url + "/", "vault": str(vault.root)}]
        assert opened == [url + "/"]
        assert core.token not in repr(said)
    finally:
        server.shutdown()
        server.server_close()
        core.close_runtime()


def test_a_live_process_that_does_not_answer_is_refused_by_name(vault, config, said, monkeypatch):
    _publish(vault, f"http://127.0.0.1:{_closed_port()}")
    _no_second_core(monkeypatch)

    assert app_module.serve(str(vault.root), port=0) == 2
    assert said[0]["error"] == "vault_in_use"
    assert f"Librarian process {os.getpid()}" in said[0]["detail"]
    assert "page-secret" not in repr(said)


def test_a_record_of_a_dead_core_is_not_attached_to(vault, config, monkeypatch):
    connection.publish(vault.root, url="http://127.0.0.1:9", token="t", pid=os.getpid(),
                       protocol_version="2", secret_source="desktop",
                       process_start="not-this-process")
    assert reopen.running_core(vault.root) is None


class _StaleThenFine:
    """Stands in for App: the lease is stale until the person takes it over."""

    def __init__(self):
        self.calls: list[bool] = []

    def __call__(self, _vault, **kwargs):
        self.calls.append(bool(kwargs.get("takeover")))
        if not kwargs.get("takeover"):
            raise StaleLeaseError("a prior Librarian Core appears to have stopped (pid 4242, "
                                  "started 2026-11-08)")
        raise LeaseHeldError("stop here: the takeover was attempted")


def _serve_in_background(vault, **kwargs):
    result: dict = {}
    worker = threading.Thread(target=lambda: result.setdefault(
        "code", app_module.serve(str(vault.root), port=0, **kwargs)), daemon=True)
    worker.start()
    return worker, result


def _wait_for_page(said, worker):
    for _ in range(200):
        if said or not worker.is_alive():
            break
        worker.join(.05)
    assert said and said[0].get("takeover_page"), said
    return said[0]["takeover_page"]


def _decide(page: str, choice: str, token: str | None = None) -> int:
    if token is None:
        with urllib.request.urlopen(page, timeout=5) as response:
            html = response.read().decode()
        token = html.split('var token = "', 1)[1].split('"', 1)[0]
    request = urllib.request.Request(page + "decide", method="POST",
                                     data=json.dumps({"choice": choice}).encode(),
                                     headers={"Content-Type": "application/json",
                                              "X-Takeover-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def test_a_stale_lease_asks_the_person_and_takes_over_only_on_their_answer(
        vault, config, said, monkeypatch):
    fake = _StaleThenFine()
    monkeypatch.setattr(app_module, "App", fake)
    worker, result = _serve_in_background(vault)
    page = _wait_for_page(said, worker)

    with urllib.request.urlopen(page, timeout=5) as response:
        html = response.read().decode()
    assert "pid 4242" in html and "Take over and open" in html
    assert _decide(page, "takeover", token="wrong") == 403     # only its own page decides
    assert fake.calls == [False]

    assert _decide(page, "takeover") == 200
    worker.join(10)
    assert fake.calls == [False, True]
    assert result["code"] == 2                                 # the stand-in refused, as told


def test_leaving_a_stale_library_closed_never_takes_it_over(vault, config, said, monkeypatch):
    fake = _StaleThenFine()
    monkeypatch.setattr(app_module, "App", fake)
    worker, result = _serve_in_background(vault)
    page = _wait_for_page(said, worker)

    assert _decide(page, "leave") == 200
    worker.join(10)
    assert fake.calls == [False]
    assert result["code"] == 2
    assert said[-1]["decision"] == "leave"


def test_a_host_managed_core_reports_a_stale_lease_without_a_page(
        vault, config, said, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_HOST_MANAGED", "1")
    fake = _StaleThenFine()
    monkeypatch.setattr(app_module, "App", fake)

    assert app_module.serve(str(vault.root), port=0) == 2
    assert said == [{"error": "stale_vault_lease", "detail": said[0]["detail"],
                     "takeover": said[0]["takeover"]}]
    assert fake.calls == [False]


# -- the library picker ---------------------------------------------------------

def _no_child(monkeypatch):
    def refuse(*_a, **_k):
        raise AssertionError("the picker started a second app for an open library")
    monkeypatch.setattr(library_picker.subprocess, "Popen", refuse)


def test_the_picker_opens_a_running_library_where_it_runs(vault, config, monkeypatch):
    _publish(vault, "http://127.0.0.1:9123")
    monkeypatch.setattr(reopen.urllib.request, "urlopen", _FakeMeta())
    _no_child(monkeypatch)

    out = library_picker.launch(str(vault.root))
    assert out == {"url": "http://127.0.0.1:9123/", "path": str(vault.root.resolve()),
                   "attached": True}


def test_the_picker_refuses_a_live_process_that_does_not_answer(vault, config, monkeypatch):
    _publish(vault, f"http://127.0.0.1:{_closed_port()}")
    _no_child(monkeypatch)

    with pytest.raises(library_picker.PickerError, match=f"Librarian process {os.getpid()}"):
        library_picker.launch(str(vault.root))


def test_the_picker_sends_the_person_to_the_takeover_page(vault, config, monkeypatch):
    line = json.dumps({"stale_vault_lease": True, "takeover_page": "http://127.0.0.1:7001/",
                       "vault": str(vault.root), "detail": "pid 4242"}) + "\n"

    class Child:
        stdout = io.StringIO(line)

        def poll(self):
            return None
    monkeypatch.setattr(library_picker.subprocess, "Popen", lambda *a, **k: Child())

    out = library_picker.launch(str(vault.root))
    assert out["url"] == "http://127.0.0.1:7001/" and out["stale_lease"] is True


class _FakeMeta:
    def __call__(self, request, timeout=None):
        assert request.full_url.endswith("/api/meta")
        assert request.get_header("X-librarian-token") == "page-secret"
        return io.BytesIO(b'{"protocol_version": "2"}')
