"""Slot 7: speech-to-text is a typed DeepInfra multipart service, never chat."""
from __future__ import annotations

import io
import json
import urllib.request
import wave

import pytest

from resource_librarian import stt
from resource_librarian.vault import Vault

from test_app import served  # noqa: F401  (fixture)


def _reply(text: str = "Hello from the recording."):
    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            return json.dumps({
                "text": text,
                "language": "en",
                "duration": 0.5,
                "request_id": "req-stt",
                "segments": [{"id": 0, "start": 0, "end": 0.5, "text": text}],
                "words": [{"start": 0, "end": 0.5, "text": "Hello"}],
                "inference_status": {"runtime_ms": 12, "cost": 0.00001},
            }).encode()
    return Reply()


def test_transcription_uses_the_documented_native_multipart_audio_contract(vault, monkeypatch):
    vault.set_setting("services", "stt", "deepinfra:Qwen/Qwen3-ASR-0.6B")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    sent: dict[str, object] = {}

    def fake_urlopen(request, timeout=0):
        sent["url"] = request.full_url
        sent["auth"] = request.get_header("Authorization")
        sent["content_type"] = request.get_header("Content-type")
        sent["body"] = request.data
        sent["timeout"] = timeout
        return _reply()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    audio = b"RIFF\x04\x00\x00\x00WAVE"
    out = stt.transcribe(vault, audio, filename='recording".wav', content_type="audio/wav")

    assert sent["url"] == "https://api.deepinfra.com/v1/inference/Qwen/Qwen3-ASR-0.6B"
    assert sent["auth"] == "Bearer test-key"
    assert str(sent["content_type"]).startswith("multipart/form-data; boundary=----LibrarianSTT")
    body = sent["body"]
    assert isinstance(body, bytes)
    assert b'name="audio"; filename="recording.wav"' in body
    assert b"Content-Type: audio/wav" in body and audio in body
    assert out == {
        "text": "Hello from the recording.",
        "segments": [{"text": "Hello from the recording.", "start": 0.0, "end": 0.5, "id": 0}],
        "words": [{"text": "Hello", "start": 0.0, "end": 0.5}],
        "language": "en",
        "request_id": "req-stt",
        "duration": 0.5,
        "cost_usd": 0.00001,
        "runtime_ms": 12.0,
        "model": "deepinfra:Qwen/Qwen3-ASR-0.6B",
        "adapter": "deepinfra_inference_stt_v1",
        "expectation_id": "deepinfra-qwen3-asr",
    }


def test_only_a_registered_stt_contract_can_be_selected_or_called(vault):
    assert stt.choice(vault) == {}
    vault.set_setting("services", "stt", "deepinfra:unknown/asr")
    with pytest.raises(stt.SttError, match="adapter contract"):
        stt.transcribe(vault, b"audio")
    with pytest.raises(stt.SttError, match="native inference"):
        stt.validate_choice("openai", "whisper-1")


def test_probe_is_a_valid_silent_wav_connection_check_not_a_quality_claim(vault, monkeypatch):
    vault.set_setting("services", "stt", "deepinfra:openai/whisper-large-v3-turbo")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    sample = stt.sample_wav()
    with wave.open(io.BytesIO(sample), "rb") as reader:
        assert (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) == (1, 2, 16_000)
        assert reader.getnframes() == 1_600
    got = stt.probe(vault, post=lambda *args: {
        "text": "", "segments": [], "words": [], "inference_status": {"runtime_ms": 2},
    })
    assert got["ok"] and "valid transcription response" in got["summary"]
    assert "no speech detected" in got["read"]
    assert got["model"] == "deepinfra:openai/whisper-large-v3-turbo"


def test_transcription_response_size_is_bounded(vault, monkeypatch):
    vault.set_setting("services", "stt", "deepinfra:Qwen/Qwen3-ASR-0.6B")
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")

    class HugeReply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, *args):
            return b"x" * (stt.MAX_RESPONSE_BYTES + 1)

    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: HugeReply())
    with pytest.raises(stt.SttError, match="unexpectedly large"):
        stt.transcribe(vault, b"RIFF")


def test_slot_seven_is_configured_and_tested_through_the_existing_services_api(served, monkeypatch):
    app, client, _ = served
    slots = {slot["slot"]: slot for slot in client.get("/api/services")[1]["slots"]}
    assert slots["stt"] == {
        "slot": "stt", "number": 7, "label": "Speech to text",
        "job": "turns an audio recording into text", "provider": "", "model": "",
        "built": True, "default": False,
    }
    assert client.post("/api/services", {"slot": "stt", "provider": "openai",
                                         "model": "whisper-1"})[0] == 400
    out = client.post("/api/services", {"slot": "stt", "provider": "deepinfra",
                                         "model": "mistralai/Voxtral-Mini-3B-2507"})[1]
    stt_slot = next(slot for slot in out["slots"] if slot["slot"] == "stt")
    assert stt_slot["model"] == "mistralai/Voxtral-Mini-3B-2507"
    assert stt_slot["adapter"]["adapter"]["id"] == "deepinfra_inference_stt_v1"
    assert stt_slot["adapter"]["status"] == "reviewed"
    assert Vault(app.vault.root).setting("services", "stt") == \
        "deepinfra:mistralai/Voxtral-Mini-3B-2507"
    monkeypatch.setattr(stt, "probe", lambda vault: {
        "ok": True, "read": "connection response", "summary": "Works: checked safely.",
    })
    assert client.post("/api/services/test", {"slot": "stt"})[1] == {
        "ok": True, "read": "connection response", "summary": "Works: checked safely.",
    }
