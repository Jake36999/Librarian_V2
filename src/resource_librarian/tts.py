"""Text to speech: service slot 5 (R17), with the owner's two modes and a $2 cap (2026-10-01).

One pipeline, two ways in:

- **Mode A, a message.** The speaker button under a reply reads that reply aloud.
- **Mode B, a document.** The speaker button beside the pane's ⋮ ("Read this document")
  reads the open note or file.

Either way the text is made speakable (frontmatter, code blocks, link and table syntax and
Markdown markers dropped), cut into chunks of whole sentences up to CHUNK_CHARS - the size
the model reads quickly, so the first words play while the rest is still to come - and each
chunk is spoken only when it is about to be played. Stopping costs nothing further.

The model is `[services] tts` (default Kokoro-82M on DeepInfra; `PRICES` is a compatibility
view of the evidence-backed service register). Each chunk's audio is kept by a digest of
model, voice and text, so reading a thing again costs nothing. Spend is kept in the app's
own `tts-spend.jsonl` - across libraries - and a chunk that would take it past `CAP_USD`
($2.00, the owner's limit) is refused before anything is sent; the actual cost each call
reports is what is recorded.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .service_adapters import (ServiceContractError, binding as service_binding,
                               registry as service_registry, tts_request)
from .vault import Vault, jsonl_lines, now_iso
from . import service_routes
from .providers import ProviderError

DEFAULT = "deepinfra:hexgrad/Kokoro-82M"
VOICE = "af_bella"
CAP_USD = 2.00
CHUNK_CHARS = 1200
# $ per million characters.  Keep these public compatibility constants for the
# settings picker, but derive their values from the reviewed service pack.  The
# runtime additionally requires a current price-evidence expiry before it makes
# a paid request, so this static view alone can never bypass the spend cap.
PRICES = {
    row.model_id: float(row.price_per_million)
    for row in service_registry().records
    if row.service == "tts" and row.provider == "deepinfra" and row.price_per_million is not None
}
BASE = "https://api.deepinfra.com/v1/inference"
# Retained for compatibility with integrations that inspect this public map.
# Request rendering itself is now owned by the typed service adapter.
INPUT_FIELD = {
    row.model_id: row.input_field
    for row in service_registry().records
    if row.service == "tts" and row.provider == "deepinfra" and row.input_field != "text"
}
AUDIO_EXT = {"audio/mp3": "mp3", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav",
             "audio/ogg": "ogg", "audio/flac": "flac", "audio/opus": "opus"}


class TtsError(RuntimeError):
    """Said to the person as it is: no model, an unknown price, the cap, or the call failed."""


def choice(vault: Vault) -> dict[str, str]:
    route = service_routes.resolve(vault, "tts")
    return route.choice() if route else {}


# ------------------------------------------------------------------ the text

def speakable(text: str) -> str:
    """What is worth hearing: no frontmatter, code, tables or Markdown markers."""
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
    text = re.sub(r"```.*?```", " (a code block, not read aloud) ", text, flags=re.S)
    text = re.sub(r"^\|.*\|\s*$", "", text, flags=re.M)               # table rows
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)       # [[note|label]]
    text = re.sub(r"\[\[([^\]#|]+)(#[^\]]*)?\]\]", lambda m: m.group(1).rsplit("/", 1)[-1], text)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)           # [text](url), images
    text = re.sub(r"https?://\S+", " a link ", text)
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)        # headings
    text = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", text, flags=re.M)     # list markers
    text = re.sub(r"^\s*>\s?", "", text, flags=re.M)                 # quotes
    text = re.sub(r"[*_`~]{1,3}", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{2,}", "\n\n", text).strip()


def chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    """Whole sentences packed up to `size`; a longer sentence is cut at a space."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n{2,}", text) if s.strip()]
    out: list[str] = []
    current = ""
    for sentence in sentences:
        while len(sentence) > size:
            cut = sentence.rfind(" ", 0, size)
            cut = cut if cut > size // 2 else size
            if current:
                out.append(current)
                current = ""
            out.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if current and len(current) + 1 + len(sentence) > size:
            out.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        out.append(current)
    return out


# ------------------------------------------------------------------ the money

def ledger_path() -> Path:
    from .keys import config_dir
    return config_dir() / "tts-spend.jsonl"


def spent() -> float:
    path = ledger_path()
    if not path.is_file():
        return 0.0
    return sum(json.loads(line).get("cost_usd", 0.0)
               for line in jsonl_lines(path.read_text(encoding="utf-8")) if line.strip())


def _record(cost: float, chars: int, model: str, mode: str) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"t": now_iso(), "cost_usd": cost, "chars": chars,
                                 "model": model, "mode": mode}) + "\n")


def estimate(text: str, model: str) -> float:
    try:
        selected = service_binding("tts", "deepinfra", model)
    except ServiceContractError as exc:
        raise TtsError(str(exc)) from exc
    contract = selected.expectation
    if contract is None or contract.price_per_million is None:
        raise TtsError(f"no price is known for {model!r}, so the ${CAP_USD:.2f} cap could not "
                       f"hold: choose a model listed in tts.PRICES")
    if not contract.price_is_current():
        raise TtsError(f"price evidence for {model!r} is stale, so the ${CAP_USD:.2f} cap "
                       "cannot safely hold: refresh the service expectation pack")
    return len(text) * float(contract.price_per_million) / 1_000_000


# ------------------------------------------------------------------ the audio

def _wav(pcm: bytes, rate: int, channels: int = 1, width: int = 2) -> bytes:
    """Raw little-endian PCM wrapped in a WAV header, so a browser can play it."""
    import struct
    size = len(pcm)
    return (b"RIFF" + struct.pack("<I", 36 + size) + b"WAVEfmt " +
            struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * channels * width,
                        channels * width, width * 8) + b"data" + struct.pack("<I", size) + pcm)


def _playable(audio: str) -> tuple[str, bytes]:
    """A model's `data:audio/...;base64,...` as (mime type, bytes) a browser plays."""
    head, _, data = audio.partition(",")
    raw = base64.b64decode(data)
    params = head[len("data:"):].split(";")
    mime = params[0].lower()
    if mime in ("audio/pcm", "audio/l16", "audio/raw"):
        rate = next((int(p.split("=", 1)[1]) for p in params[1:] if p.startswith("rate=")),
                    24000)
        return "audio/wav", _wav(raw, rate)
    return mime, raw


def _data_uri(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode()


# ------------------------------------------------------------------ the call

# DeepInfra answers 429 "Model busy, retry later" when a shared model is saturated (seen on
# Kokoro, 2026-10-01): retried after these pauses before the person is told.
BUSY_RETRIES = (2.0, 5.0, 10.0)


def _post(url: str, body: dict[str, Any], key: str,
          sleep: Callable[[float], None] | None = None) -> dict[str, Any]:
    import time
    pauses = list(BUSY_RETRIES)
    while True:
        request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                         method="POST",
                                         headers={"Authorization": f"Bearer {key}",
                                                  "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (429, 503):
                if pauses:
                    (sleep or time.sleep)(pauses.pop(0))
                    continue
                raise TtsError(f"the speech model is busy at DeepInfra (HTTP {exc.code}, tried "
                               f"{len(BUSY_RETRIES) + 1} times): try again in a minute, or "
                               f"choose another speech model in Settings -> Connections, "
                               f"slot 5") from exc
            raise TtsError(f"HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise TtsError(f"the speech model is not reachable: {exc}") from exc


def speak(vault: Vault, text: str, mode: str = "message",
          post: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None
          ) -> dict[str, Any]:
    """One chunk, spoken: its audio as a data URI, what it cost, and the spend so far."""
    chosen = choice(vault)
    if not chosen:
        raise TtsError("no text-to-speech model is chosen (Settings -> Connections, slot 5)")
    if chosen["provider"] != "deepinfra":
        raise TtsError("text to speech runs on DeepInfra's inference API")
    model = chosen["model"]
    try:
        body, _selected = tts_request(chosen["provider"], model, text)
    except ServiceContractError as exc:
        if "no reviewed tts adapter contract" in str(exc):
            raise TtsError(f"no price is known for {model!r}, and it has no reviewed TTS "
                           "adapter contract") from exc
        raise TtsError(str(exc)) from exc
    voice = str(body.get("preset_voice") or "")
    digest = hashlib.sha256(f"{model}|{voice}|{text}".encode("utf-8")).hexdigest()[:24]
    folder = vault.derived / "tts"
    for ext, mime in (("mp3", "audio/mp3"), ("wav", "audio/wav"), ("ogg", "audio/ogg"),
                      ("flac", "audio/flac"), ("opus", "audio/opus")):
        cache = folder / f"{digest}.{ext}"
        if cache.is_file():
            return {"audio": _data_uri(mime, cache.read_bytes()), "cost_usd": 0.0,
                    "cached": True, "spent_usd": round(spent(), 6), "cap_usd": CAP_USD}
    cost = estimate(text, model)
    so_far = spent()
    if so_far + cost > CAP_USD:
        raise TtsError(f"text to speech has spent ${so_far:.2f} of its ${CAP_USD:.2f} cap; this "
                       f"part would cost ${cost:.4f}")
    try:
        route = service_routes.resolve(vault, "tts", validate=True)
        if route is None or route.model != model:
            raise service_routes.ServiceRouteError("speech assignment changed; restart the operation")
        key = os.environ.get(route.key_env, "")
        if not key:
            raise TtsError(f"{route.key_env} is not set (Settings -> Connections)")
        out = service_routes.run(vault, route, lambda: (post or _post)(
            f"{route.native_base()}/{model}", body, key))
    except (service_routes.ServiceRouteError, ProviderError) as exc:
        raise TtsError(str(exc)) from exc
    audio = str(out.get("audio") or "")
    if not audio.startswith("data:audio"):
        raise TtsError(f"the model returned no audio ({str(out)[:200]})")
    mime, raw = _playable(audio)
    # Only Kokoro reports its cost; for the rest the register's price is what is recorded.
    actual = float((out.get("inference_status") or {}).get("cost") or cost)
    _record(actual, len(text), model, mode)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{digest}.{AUDIO_EXT.get(mime, 'bin')}").write_bytes(raw)
    return {"audio": _data_uri(mime, raw), "cost_usd": actual, "cached": False,
            "spent_usd": round(so_far + actual, 6), "cap_usd": CAP_USD}


def plan(text: str, model: str = "") -> dict[str, Any]:
    """What reading `text` would take: its chunks, characters and the most it could cost."""
    parts = chunks(speakable(text))
    chars = sum(len(p) for p in parts)
    price = PRICES.get(model or DEFAULT.split(":", 1)[1])
    return {"chunks": parts, "chars": chars,
            "estimate_usd": round(chars * price / 1_000_000, 6) if price is not None else None,
            "spent_usd": round(spent(), 6), "cap_usd": CAP_USD}
