"""CORE-07: SSE cursors are epoch-bound, never a replayed action log."""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

import pytest

from resource_librarian.app import App, Hub, build
from resource_librarian.keys import KeyStore


def test_hub_replay_requires_the_current_epoch_and_never_publishes_resync():
    hub = Hub(keep=2)
    first = hub.publish({"type": "first", "seq": 999, "at": -1, "epoch": "forged"})
    cursor = hub.cursor()
    second = hub.publish({"type": "second"})

    assert first["seq"] == 1 and first["epoch"] == cursor["epoch"]
    assert second["seq"] == 2 and second["epoch"] == cursor["epoch"]
    replay, resync = hub.resume(1, cursor["epoch"])
    assert resync is None and [event["type"] for event in replay] == ["second"]

    before = hub.last()
    for since, epoch, reason in [
        (1, "prior-core", "epoch_changed"),
        (1, "", "epoch_required"),
        (99, cursor["epoch"], "cursor_ahead"),
    ]:
        replay, resync = hub.resume(since, epoch)
        assert replay == []
        assert resync == {"type": "resync_required", "seq": before,
                          "epoch": cursor["epoch"], "reason": reason,
                          "state_url": "/api/state", "instruction": "refresh_state"}
        assert hub.last() == before


def test_hub_detects_when_the_bounded_replay_window_has_expired():
    hub = Hub(keep=2)
    epoch = hub.cursor()["epoch"]
    for number in range(3):
        hub.publish({"type": f"event-{number}"})

    replay, resync = hub.resume(0, epoch)

    assert replay == []
    assert resync and resync["reason"] == "history_expired"
    assert resync["seq"] == 3 and resync["epoch"] == epoch


def test_hub_with_no_retention_never_silently_drops_a_gap():
    hub = Hub(keep=0)
    epoch = hub.cursor()["epoch"]
    hub.publish({"type": "discarded"})

    replay, resync = hub.resume(0, epoch)

    assert replay == []
    assert resync and resync["reason"] == "history_expired"


@pytest.fixture
def served_resync(vault, tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    app = App(vault, token="event-test-token", keys=KeyStore(use_keyring=False))
    server = build(app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield app, server
    finally:
        server.shutdown()
        server.server_close()
        if app.mcp is not None:
            app.mcp.stop()


def _first_sse_event(server, token: str, query: str) -> dict:
    url = f"http://127.0.0.1:{server.server_address[1]}/api/events?token={token}&{query}"
    with urllib.request.urlopen(url, timeout=5) as response:
        fields: dict[str, str] = {}
        while True:
            line = response.readline().decode("utf-8")
            if line == "\n":
                break
            key, value = line.rstrip("\n").split(": ", 1)
            fields[key] = value
        assert fields["event"] == "resync_required"
        return json.loads(fields["data"])


def test_http_resync_is_synthetic_and_state_exposes_the_cursor(served_resync):
    app, server = served_resync
    app.hub.publish({"type": "ordinary"})
    state = app.state()
    cursor = state["event_stream"]
    before = app.hub.last()

    event = _first_sse_event(server, "event-test-token",
                             "since=1&epoch=previous-core")

    assert event["reason"] == "epoch_changed"
    assert event["epoch"] == cursor["epoch"]
    assert event["seq"] == before == cursor["last_seq"]
    assert event["state_url"] == "/api/state" and event["instruction"] == "refresh_state"
    assert app.hub.last() == before


@pytest.mark.parametrize("since", ["not-a-number", "-1"])
def test_events_reject_a_malformed_or_negative_cursor(served_resync, since):
    _app, server = served_resync
    url = f"http://127.0.0.1:{server.server_address[1]}/api/events?token=event-test-token&since={since}"

    with pytest.raises(urllib.error.HTTPError) as raised:
        urllib.request.urlopen(url, timeout=5)

    assert raised.value.code == 400
    assert "non-negative integer" in raised.value.read().decode("utf-8")
