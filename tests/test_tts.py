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
        return {"audio": MP3, "inference_status": {"cost": len(body["text"]) * 0.62 / 1e6}}
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
    assert len(rows) == 1 and rows[0]["cost_usd"] == pytest.approx(14 * 0.62 / 1e6)


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
