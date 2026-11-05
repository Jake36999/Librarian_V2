"""Text to speech (slot 5; owner 2026-10-01): two modes on one pipeline, speakable chunks,
audio kept so a second reading is free, and a $2 cap checked before anything is sent."""
import base64
import json

import pytest

from resource_librarian import tts

from conftest import write_note
from test_app import served  # noqa: F401  (fixture)

MP3 = "data:audio/mp3;base64," + base64.b64encode(b"ID3fake-audio").decode()


def fake_post(log):
    def post(url, body, key):
        log.append((url, body))
        return {"audio": MP3, "inference_status": {"cost": len(body["text"]) * 0.99 / 1e6}}
    return post


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    monkeypatch.setenv("LIBRARIAN_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    return tmp_path / "config" / "tts-spend.jsonl"


def test_what_is_read_is_the_prose_in_whole_sentences():
    text = ("---\ntype: note\n---\n# Week Plan\n\nRead the [[Sources/page/Scrum Guide|guide]] "
            "first. See https://example.org now!\n\n```python\nprint(1)\n```\n"
            "| a | b |\n|---|---|\n- **Day 1**: roles.\n")
    said = tts.speakable(text)
    assert "type: note" not in said and "print(1)" not in said and "|" not in said
    assert "Read the guide first." in said and "a link" in said and "Day 1: roles." in said
    parts = tts.chunks(" ".join(["This is one sentence of the plan."] * 100), size=200)
    assert all(len(p) <= 200 for p in parts) and all(p.endswith(".") for p in parts)


def test_a_chunk_is_spoken_once_kept_and_its_real_cost_recorded(vault, ledger):
    log = []
    first = tts.speak(vault, "Hello, reader.", "message", post=fake_post(log))
    again = tts.speak(vault, "Hello, reader.", "message", post=fake_post(log))
    assert first["audio"] == MP3 and not first["cached"] and again["cached"]
    assert len(log) == 1 and log[0][0].endswith("/hexgrad/Kokoro-82M")
    assert log[0][1] == {"text": "Hello, reader.", "output_format": "mp3",
                         "preset_voice": "af_bella"}
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    # MF-019: a reservation before the call, settled once with the real cost.
    assert [r["type"] for r in rows] == ["reserve", "settle"]
    assert rows[0]["id"] == rows[1]["id"] and rows[1]["outcome"] == "charged"
    assert rows[1]["cost_usd"] == pytest.approx(14 * 0.99 / 1e6)
    assert tts.spent() == pytest.approx(14 * 0.99 / 1e6)


def cost_of(text):
    return len(text) * 0.99 / 1e6


def test_concurrent_callers_cannot_spend_past_the_cap_together(vault, ledger):
    """MF-019: both used to read the same spend, pass the check and send."""
    import threading
    first, second = "The first part to read.", "Another part to read."
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"cost_usd": tts.CAP_USD - 1.5 * cost_of(first)}) + "\n")
    go, outcomes, log = threading.Event(), [], []

    def slow_post(url, body, key):
        log.append(body["text"])
        go.wait(2)                                  # both would be in flight at once
        return {"audio": MP3, "inference_status": {"cost": cost_of(body["text"])}}

    def speak(text):
        try:
            outcomes.append(("ok", tts.speak(vault, text, "message", post=slow_post)))
        except tts.TtsError as exc:
            outcomes.append(("refused", str(exc)))

    threads = [threading.Thread(target=speak, args=(t,)) for t in (first, second)]
    for thread in threads:
        thread.start()
    threading.Event().wait(0.5)
    go.set()
    for thread in threads:
        thread.join(5)

    assert sorted(kind for kind, _ in outcomes) == ["ok", "refused"], outcomes
    assert len(log) == 1 and tts.spent() <= tts.CAP_USD
    assert any("cap" in str(detail) for kind, detail in outcomes if kind == "refused")


def test_another_cores_open_reservation_and_lock_hold_across_processes(vault, ledger):
    import os
    import subprocess
    import sys
    import time
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "src"
    child = subprocess.Popen(
        [sys.executable, "-c",
         "import time\n"
         "from resource_librarian import tts\n"
         "from resource_librarian.coordination import exclusive_file_lock\n"
         f"tts.reserve({tts.CAP_USD - 0.000001}, 10, 'm', 'message')\n"
         "with exclusive_file_lock(tts.ledger_path().with_suffix('.lock')):\n"
         "    print('locked', flush=True)\n"
         "    time.sleep(1.5)\n"],
        stdout=subprocess.PIPE, text=True,
        env={**os.environ, "PYTHONPATH": str(src)})
    try:
        assert child.stdout.readline().strip() == "locked"
        started = time.monotonic()
        with pytest.raises(tts.TtsError, match="cap"):
            tts.reserve(cost_of("Hello."), 6, "m", "message")
        waited = time.monotonic() - started
    finally:
        child.wait(10)
    assert waited >= 0.8                      # it queued behind the other process's lock
    assert child.returncode == 0


def test_an_unknown_outcome_keeps_its_reservation_a_refusal_releases_it(vault, ledger):
    text = "A sentence to read."

    def timed_out(url, body, key):
        raise tts.TtsError("the speech model is not reachable: timed out")

    def refused(url, body, key):
        raise tts.TtsNotSent("HTTP 400: bad request")

    with pytest.raises(tts.TtsError, match="timed out"):
        tts.speak(vault, text, "message", post=timed_out)
    assert tts.spent() == pytest.approx(cost_of(text))          # it may have been charged

    with pytest.raises(tts.TtsNotSent, match="HTTP 400"):
        tts.speak(vault, "Something else to read.", "message", post=refused)
    assert tts.spent() == pytest.approx(cost_of(text))          # released: nothing owed

    out = tts.speak(vault, text, "message", post=fake_post([]))  # asked again: a new charge
    assert not out["cached"]
    assert tts.spent() == pytest.approx(2 * cost_of(text))
    outcomes = [json.loads(line).get("outcome") for line in ledger.read_text().splitlines()]
    assert outcomes.count("unknown") == 1 and outcomes.count("charged") == 1


def test_a_result_that_arrives_after_the_route_changed_is_still_owed(vault, ledger,
                                                                      monkeypatch):
    from resource_librarian import service_routes

    def late(vault_, route, call):
        call()
        raise service_routes.ServiceRouteError("tts assignment changed; restart the operation")

    monkeypatch.setattr(service_routes, "run", late)
    log = []
    with pytest.raises(tts.TtsError, match="assignment changed"):
        tts.speak(vault, "Late words.", "message", post=fake_post(log))
    assert len(log) == 1 and tts.spent() == pytest.approx(cost_of("Late words."))


def test_a_reservation_settles_once_and_a_replay_is_sent_once(vault, ledger):
    import threading
    rid, _ = tts.reserve(0.01, 5, "m", "message")
    assert tts.settle(rid, 0.004) is True and tts.release(rid, "late") is False
    assert tts.settle(rid, 0.5) is False and tts.spent() == pytest.approx(0.004)

    log, gate = [], threading.Event()

    def slow(url, body, key):
        log.append(body["text"])
        gate.wait(2)
        return {"audio": MP3, "inference_status": {"cost": cost_of(body["text"])}}

    results = []
    threads = [threading.Thread(target=lambda: results.append(
        tts.speak(vault, "Read me twice.", "message", post=slow))) for _ in range(2)]
    for thread in threads:
        thread.start()
    threading.Event().wait(0.3)
    gate.set()
    for thread in threads:
        thread.join(5)
    assert len(log) == 1 and sorted(r["cached"] for r in results) == [False, True]


def test_the_cap_refuses_before_anything_is_sent(vault, ledger):
    ledger.parent.mkdir(parents=True)
    ledger.write_text(json.dumps({"cost_usd": tts.CAP_USD - 0.000001}) + "\n")
    log = []
    with pytest.raises(tts.TtsError, match="cap"):
        tts.speak(vault, "One more sentence to read.", "message", post=fake_post(log))
    assert log == []


def test_a_model_with_no_known_price_is_refused(vault, ledger):
    vault.set_setting("services", "tts", "deepinfra:someone/unpriced-tts")
    with pytest.raises(tts.TtsError, match="no price"):
        tts.speak(vault, "Hello.", "message", post=fake_post([]))


def test_both_modes_through_the_app(served, ledger, monkeypatch):
    app, client, _ = served
    log = []
    monkeypatch.setattr(tts, "_post", fake_post(log))
    # mode A: a reply
    plan = client.post("/api/tts/plan", {"text": "First sentence. Second sentence."})[1]
    assert plan["mode"] == "message" and plan["count"] == 1 and plan["cap_usd"] == 2.0
    chunk = client.post("/api/tts/chunk", {"plan": plan["plan"], "index": 0})[1]
    assert chunk["audio"] == MP3 and chunk["count"] == 1
    # mode B: the open document
    write_note(app.vault.root, "Notes/Plan.md", "type: note",
               "# Plan\n\n" + " ".join(["Day one is for reading the guide."] * 60))
    plan = client.post("/api/tts/plan", {"path": "Notes/Plan.md"})[1]
    assert plan["mode"] == "document" and plan["count"] > 1
    assert log[-1][1]["text"] == "First sentence. Second sentence."     # nothing more yet
    client.post("/api/tts/chunk", {"plan": plan["plan"], "index": 1})
    assert len(log) == 2                                                # one chunk, on demand
    assert client.post("/api/tts/chunk", {"plan": "gone", "index": 0})[0] == 404


def test_slot_five_keeps_to_priced_deepinfra_models(served):
    app, client, _ = served
    slots = {s["slot"]: s for s in client.get("/api/services")[1]["slots"]}
    assert slots["tts"]["built"] and slots["tts"]["model"] == "hexgrad/Kokoro-82M"
    assert client.post("/api/services", {"slot": "tts", "provider": "openai",
                                         "model": "tts-1"})[0] == 400
    out = client.post("/api/services", {"slot": "tts", "provider": "deepinfra",
                                        "model": "ResembleAI/chatterbox-turbo"})[1]
    assert {s["slot"]: s for s in out["slots"]}["tts"]["model"] == "ResembleAI/chatterbox-turbo"


def test_a_busy_model_is_retried_then_said_plainly(monkeypatch):
    """DeepInfra's 'HTTP 429: Model busy, retry later' (owner's TTS check, 2026-10-01)."""
    import io
    import urllib.error
    calls, pauses = [], []

    def busy_then(ok_after):
        def urlopen(request, timeout):
            calls.append(1)
            if len(calls) <= ok_after:
                raise urllib.error.HTTPError(request.full_url, 429, "busy", {},
                                             io.BytesIO(b'{"detail":"Model busy, retry later"}'))
            return io.BytesIO(b'{"audio": "data:audio/mp3;base64,AA=="}')
        return urlopen
    monkeypatch.setattr(tts.urllib.request, "urlopen", busy_then(2))
    assert tts._post("https://example.invalid/u", {}, "k", sleep=pauses.append)["audio"].startswith("data:audio")
    assert pauses == [2.0, 5.0]
    calls.clear()
    pauses.clear()
    monkeypatch.setattr(tts.urllib.request, "urlopen", busy_then(99))
    with pytest.raises(tts.TtsError, match="busy at DeepInfra"):
        tts._post("https://example.invalid/u", {}, "k", sleep=pauses.append)
    assert len(calls) == 4 and pauses == list(tts.BUSY_RETRIES)


def test_each_model_is_sent_its_own_field_and_raw_pcm_becomes_wav(vault, ledger, monkeypatch):
    """2026-10-03: Qwen3-TTS answered 422 'input: Field required', and HiggsAudio returns raw
    PCM a browser cannot play."""
    # Payload/decoding behavior must not start failing merely because the
    # separate, correctly fail-closed price evidence expires. Pricing freshness
    # has its own contract tests; this call never reaches a provider.
    monkeypatch.setattr(tts, "estimate", lambda text, model: 0.0)
    import struct
    pcm = struct.pack("<4h", 0, 1000, -1000, 0)
    sent = []

    def higgs(url, body, key):
        sent.append(dict(body))
        return {"audio": "data:audio/pcm;rate=24000;base64," + base64.b64encode(pcm).decode()}
    vault.set_setting("services", "tts", "deepinfra:bosonai/HiggsAudioV2.5")
    out = tts.speak(vault, "Hello.", "message", post=higgs)
    assert sent[0]["input"] == "Hello." and "text" not in sent[0]
    head, _, data = out["audio"].partition(",")
    raw = base64.b64decode(data)
    assert head == "data:audio/wav;base64" and raw[:4] == b"RIFF" and raw.endswith(pcm)
    assert struct.unpack("<I", raw[24:28])[0] == 24000
    assert tts.speak(vault, "Hello.", "message", post=higgs)["cached"]      # kept as .wav


def test_a_model_that_rejects_its_reviewed_field_is_not_retried_with_a_guess(vault, ledger,
                                                                            monkeypatch):
    # Isolate the reviewed request-field behavior from time-varying price
    # evidence. Production still refuses stale pricing before a paid call.
    monkeypatch.setattr(tts, "estimate", lambda text, model: 0.0)
    calls = []

    def wants_input(url, body, key):
        calls.append(dict(body))
        if "input" not in body:
            raise tts.TtsError('HTTP 422: {"detail":[{"type":"missing","loc":["input"]}]}')
        return {"audio": "data:audio/wav;base64," + base64.b64encode(b"RIFFxxxx").decode()}
    vault.set_setting("services", "tts", "deepinfra:ResembleAI/chatterbox-turbo")
    with pytest.raises(tts.TtsError, match="HTTP 422"):
        tts.speak(vault, "Hi there.", "message", post=wants_input)
    assert [sorted(c) for c in calls] == [["output_format", "text"]]
