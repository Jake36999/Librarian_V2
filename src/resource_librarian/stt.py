"""Speech to text: the per-library service slot for recorded audio.

DeepInfra's documented ASR routes are not OpenAI chat calls.  They accept one
multipart ``audio`` field at their native inference endpoint and return a
transcription object.  Keeping that small protocol here means an agent chat
route can never be accidentally used as a transcription fallback.

This module intentionally exposes only a typed transport and a tiny
connection probe.  Starting a transcription remains an explicit caller
action; the probe is not model qualification and does not claim recognition
quality from a silent synthetic WAV.
"""
from __future__ import annotations

import io
import json
import secrets
import urllib.error
import urllib.request
import wave
from pathlib import Path
from typing import Any, Callable, Mapping

from .providers import PRESETS, ProviderError, _key
from .service_adapters import ServiceBinding, ServiceContractError, require_binding
from .vault import Vault
from . import service_routes


DEFAULT = ""
BASE = "https://api.deepinfra.com/v1/inference"
TIMEOUT_SECONDS = 120
MAX_AUDIO_BYTES = 40_000_000
MAX_RESPONSE_BYTES = 2_000_000
ADAPTER_ID = "deepinfra_inference_stt_v1"


class SttError(RuntimeError):
    """A selected speech-recognition route cannot safely transcribe audio."""


def choice(vault: Vault) -> dict[str, str]:
    """The library's selected speech-to-text route, or no choice."""
    route = service_routes.resolve(vault, "stt")
    return route.choice() if route else {}


def validate_choice(provider: str, model: str) -> ServiceBinding:
    """Resolve the exact reviewed ASR contract before a request is possible."""
    if provider != "deepinfra":
        raise SttError("speech to text runs on DeepInfra's native inference API")
    if not model:
        raise SttError("no speech-to-text model is chosen (Settings -> Connections, slot 7)")
    try:
        selected = require_binding("stt", provider, model)
    except ServiceContractError as exc:
        raise SttError(f"{provider}:{model} has no reviewed speech-to-text adapter contract") from exc
    if selected.descriptor is None or selected.descriptor.id != ADAPTER_ID:
        raise SttError(f"{provider}:{model} has an unsupported speech-to-text adapter")
    return selected


def _safe_filename(filename: str) -> str:
    value = Path(str(filename or "recording.wav")).name.replace("\r", "").replace("\n", "")
    value = value.replace('"', "")
    return value[:180] or "recording.wav"


def _safe_content_type(value: str) -> str:
    value = str(value or "").split(";", 1)[0].replace("\r", "").replace("\n", "").strip()
    return value[:120] or "application/octet-stream"


def _multipart_audio(audio: bytes, filename: str, content_type: str) -> tuple[bytes, str]:
    """Render exactly the documented one-field DeepInfra ASR request body."""
    boundary = "----LibrarianSTT" + secrets.token_hex(12)
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="audio"; filename="{_safe_filename(filename)}"\r\n'
        f"Content-Type: {_safe_content_type(content_type)}\r\n\r\n"
    ).encode("utf-8")
    return head + audio + f"\r\n--{boundary}--\r\n".encode("ascii"), boundary


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _timed_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for row in value:
        if not isinstance(row, Mapping):
            continue
        item: dict[str, Any] = {"text": str(row.get("text") or "")}
        for key in ("start", "end"):
            number = _number(row.get(key))
            if number is not None:
                item[key] = number
        if isinstance(row.get("id"), int):
            item["id"] = row["id"]
        out.append(item)
    return out


def _normalise(data: Any) -> dict[str, Any]:
    if not isinstance(data, Mapping) or not isinstance(data.get("text"), str):
        raise SttError("the speech model returned an unexpected transcription response")
    status = data.get("inference_status") if isinstance(data.get("inference_status"), Mapping) else {}
    cost = _number(status.get("cost"))
    runtime = _number(status.get("runtime_ms"))
    duration = _number(data.get("duration"))
    out: dict[str, Any] = {
        "text": data["text"],
        "segments": _timed_rows(data.get("segments")),
        "words": _timed_rows(data.get("words")),
        "language": str(data.get("language") or "")[:64],
        "request_id": str(data.get("request_id") or "")[:200],
    }
    if duration is not None:
        out["duration"] = duration
    if cost is not None:
        out["cost_usd"] = cost
    if runtime is not None:
        out["runtime_ms"] = runtime
    return out


def _post(url: str, audio: bytes, filename: str, content_type: str, key: str) -> dict[str, Any]:
    body, boundary = _multipart_audio(audio, filename, content_type)
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SttError("the speech model returned an unexpectedly large transcription response")
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise SttError(f"HTTP {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise SttError(f"the speech model is not reachable: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SttError("the speech model returned invalid JSON") from exc


Post = Callable[[str, bytes, str, str, str], Mapping[str, Any]]


def transcribe(vault: Vault, audio: bytes, *, filename: str = "recording.wav",
               content_type: str = "audio/wav", post: Post | None = None) -> dict[str, Any]:
    """Transcribe one caller-provided audio file using its selected typed route."""
    if not isinstance(audio, bytes) or not audio:
        raise SttError("audio must be a non-empty byte string")
    if len(audio) > MAX_AUDIO_BYTES:
        raise SttError(f"audio is larger than the {MAX_AUDIO_BYTES // 1_000_000} MB speech limit")
    chosen = choice(vault)
    if not chosen:
        raise SttError("no speech-to-text model is chosen (Settings -> Connections, slot 7)")
    selected = validate_choice(chosen["provider"], chosen["model"])
    provider = selected.provider
    try:
        route = service_routes.resolve(vault, "stt", validate=True)
        if route is None or route.model != selected.model_id:
            raise service_routes.ServiceRouteError("speech assignment changed; restart the operation")
        key = _key(route.key_env)
        data = service_routes.run(vault, route, lambda: (post or _post)(
            f"{route.native_base()}/{selected.model_id}", audio, _safe_filename(filename),
            _safe_content_type(content_type), key))
    except (service_routes.ServiceRouteError, ProviderError) as exc:
        raise SttError(str(exc)) from exc
    out = _normalise(data)
    out["model"] = f"{selected.provider}:{selected.model_id}"
    out["adapter"] = selected.adapter_id
    out["expectation_id"] = selected.expectation.id if selected.expectation else ""
    return out


def sample_wav() -> bytes:
    """A valid, tiny silent WAV for a connection/response-shape probe.

    It deliberately does not pretend to be a known spoken phrase.  Recognition
    quality is evaluated separately with licensed golden audio, while this UI
    action only verifies the selected account, route and response contract.
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16_000)
        writer.writeframes(b"\x00\x00" * 1_600)  # 100 ms
    return buffer.getvalue()


def probe(vault: Vault, post: Post | None = None) -> dict[str, Any]:
    """Run the explicit, low-cost route/response-shape check used by Slot 7."""
    out = transcribe(vault, sample_wav(), filename="librarian-stt-probe.wav",
                     content_type="audio/wav", post=post)
    heard = out["text"].strip()
    return {
        "ok": True,
        "read": heard[:300] or "(no speech detected, as expected for the connection probe)",
        "summary": "Works: the route returned a valid transcription response.",
        **out,
    }
