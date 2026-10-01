"""Text to speech: service slot 5 (R17), with the owner's two modes and a $2 cap (2026-10-01).

One pipeline, two ways in:

- **Mode A, a message.** The speaker button under a reply reads that reply aloud.
- **Mode B, a document.** The speaker button beside the pane's ⋮ ("Read this document")
  reads the open note or file.

Either way the text is made speakable (frontmatter, code blocks, link and table syntax and
Markdown markers dropped), cut into chunks of whole sentences up to CHUNK_CHARS - the size
the model reads quickly, so the first words play while the rest is still to come - and each
chunk is spoken only when it is about to be played. Stopping costs nothing further.

The model is `[services] tts` (default Kokoro-82M on DeepInfra, $0.62 per million
characters; `PRICES` holds the register's rates). Each chunk's audio is kept by a digest of
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

from .vault import Vault, jsonl_lines, now_iso

DEFAULT = "deepinfra:hexgrad/Kokoro-82M"
VOICE = "af_bella"
CAP_USD = 2.00
CHUNK_CHARS = 1200
# $ per million characters (DeepInfra register, 2026-09-27); a model not here is refused, so
# the cap cannot be crossed by a price nobody knows.
PRICES = {"hexgrad/Kokoro-82M": 0.62, "ResembleAI/chatterbox-turbo": 1.00,
          "ResembleAI/chatterbox-multilingual": 1.00, "Audio8/Audio8-TTS-Preview-0.6b": 5.00,
          "Qwen/Qwen3-TTS": 20.00, "bosonai/HiggsAudioV2.5": 20.00}
BASE = "https://api.deepinfra.com/v1/inference"


class TtsError(RuntimeError):
    """Said to the person as it is: no model, an unknown price, the cap, or the call failed."""


def choice(vault: Vault) -> dict[str, str]:
    value = vault.setting("services", "tts")
    value = DEFAULT if value is None else str(value)
    provider, _, model = value.partition(":")
    return {"provider": provider, "model": model} if model else {}


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
    if model not in PRICES:
        raise TtsError(f"no price is known for {model!r}, so the ${CAP_USD:.2f} cap could not "
                       f"hold: choose a model listed in tts.PRICES")
    return len(text) * PRICES[model] / 1_000_000


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
    voice = VOICE if model == "hexgrad/Kokoro-82M" else ""
    digest = hashlib.sha256(f"{model}|{voice}|{text}".encode("utf-8")).hexdigest()[:24]
    cache = vault.derived / "tts" / f"{digest}.mp3"
    if cache.is_file():
        return {"audio": "data:audio/mp3;base64," + base64.b64encode(cache.read_bytes()).decode(),
                "cost_usd": 0.0, "cached": True, "spent_usd": round(spent(), 6), "cap_usd": CAP_USD}
    cost = estimate(text, model)
    so_far = spent()
    if so_far + cost > CAP_USD:
        raise TtsError(f"text to speech has spent ${so_far:.2f} of its ${CAP_USD:.2f} cap; this "
                       f"part would cost ${cost:.4f}")
    key = os.environ.get("DEEPINFRA_API_KEY", "")
    if not key:
        raise TtsError("DEEPINFRA_API_KEY is not set (Settings -> Connections)")
    body: dict[str, Any] = {"text": text, "output_format": "mp3"}
    if voice:
        body["preset_voice"] = voice
    out = (post or _post)(f"{BASE}/{model}", body, key)
    audio = str(out.get("audio") or "")
    if not audio.startswith("data:audio"):
        raise TtsError(f"the model returned no audio ({str(out)[:200]})")
    actual = float((out.get("inference_status") or {}).get("cost") or cost)
    _record(actual, len(text), model, mode)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(base64.b64decode(audio.split(",", 1)[1]))
    return {"audio": audio, "cost_usd": actual, "cached": False,
            "spent_usd": round(so_far + actual, 6), "cap_usd": CAP_USD}


def plan(text: str, model: str = "") -> dict[str, Any]:
    """What reading `text` would take: its chunks, characters and the most it could cost."""
    parts = chunks(speakable(text))
    chars = sum(len(p) for p in parts)
    price = PRICES.get(model or DEFAULT.split(":", 1)[1])
    return {"chunks": parts, "chars": chars,
            "estimate_usd": round(chars * price / 1_000_000, 6) if price is not None else None,
            "spent_usd": round(spent(), 6), "cap_usd": CAP_USD}
