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

The cap holds across threads and across every Core of this person (MF-019).
Under one cross-process lock, a chunk *reserves* its estimate before it is
sent, and nothing that would pass the cap, counting other in-flight
reservations, is admitted. Afterwards the reservation settles exactly once:
- at the cost the call reported;
- released, when the request certainly was not charged (refused before it was
  sent, a 4xx, the model busy after its retries);
- kept as a liability, when the outcome is unknown (a timeout, a dropped
  connection, a 5xx, a result that arrived after the route changed).

Asking again after an unknown outcome is a new reservation, so a retry is
charged too. Speech to text has no reviewed prices, so it has no cap here.
"""
from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import re
import secrets
import threading
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


class TtsNotSent(TtsError):
    """The request certainly was not charged: refused before or by the provider."""


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

LOCK_SECONDS = 10.0


def ledger_path() -> Path:
    from .keys import config_dir
    return config_dir() / "tts-spend.jsonl"


def _entries() -> list[dict[str, Any]]:
    path = ledger_path()
    if not path.is_file():
        return []
    return [json.loads(line) for line in jsonl_lines(path.read_text(encoding="utf-8"))
            if line.strip()]


def committed(entries: list[dict[str, Any]]) -> float:
    """What counts against the cap: every charge, plus every reservation not yet
    settled or released. A reservation whose outcome is unknown keeps counting."""
    total, reserved, settled, released = 0.0, {}, {}, set()
    for entry in entries:
        kind = entry.get("type", "charge")              # a line from before MF-019
        rid = str(entry.get("id") or "")
        if kind == "charge":
            total += float(entry.get("cost_usd") or 0.0)
        elif kind == "reserve":
            reserved[rid] = float(entry.get("amount") or 0.0)
        elif kind == "settle" and rid not in settled and rid not in released:
            settled[rid] = float(entry.get("cost_usd") or 0.0)
        elif kind == "release" and rid not in settled:
            released.add(rid)
    open_ = sum(amount for rid, amount in reserved.items()
                if rid not in settled and rid not in released)
    return total + sum(settled.values()) + open_


def spent() -> float:
    return committed(_entries())


def _append(entry: dict[str, Any]) -> None:
    path = ledger_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"t": now_iso(), **entry}) + "\n")
        handle.flush()
        with contextlib.suppress(OSError):
            os.fsync(handle.fileno())


@contextlib.contextmanager
def _ledger() -> Any:
    from .coordination import FileLockTimeout, exclusive_file_lock
    try:
        with exclusive_file_lock(ledger_path().with_suffix(".lock"), timeout=LOCK_SECONDS):
            yield
    except FileLockTimeout as exc:
        raise TtsNotSent("the speech spend ledger is busy in another window or library; "
                         "try again in a moment") from exc


def reserve(amount: float, chars: int, model: str, mode: str) -> tuple[str, float]:
    """Hold `amount` against the cap before sending; refused if it would not fit."""
    with _ledger():
        so_far = committed(_entries())
        if so_far + amount > CAP_USD:
            raise TtsNotSent(f"text to speech has spent ${so_far:.2f} of its ${CAP_USD:.2f} "
                             f"cap; this part would cost ${amount:.4f}")
        rid = secrets.token_hex(8)
        _append({"type": "reserve", "id": rid, "amount": amount, "chars": chars,
                 "model": model, "mode": mode})
    return rid, so_far


def _close(rid: str, entry: dict[str, Any]) -> bool:
    """Settle or release a reservation, once; a second close changes nothing."""
    with _ledger():
        for row in _entries():
            if row.get("id") == rid and row.get("type") in ("settle", "release"):
                return False
        _append({**entry, "id": rid})
    return True


def settle(rid: str, cost: float, outcome: str = "charged") -> bool:
    return _close(rid, {"type": "settle", "cost_usd": cost, "outcome": outcome})


def release(rid: str, why: str) -> bool:
    return _close(rid, {"type": "release", "why": why[:200]})


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
                raise TtsNotSent(f"the speech model is busy at DeepInfra (HTTP {exc.code}, "
                                 f"tried {len(BUSY_RETRIES) + 1} times): try again in a minute, "
                                 f"or choose another speech model in Settings -> Connections, "
                                 f"slot 5") from exc
            # A 4xx is a refusal of the request; a 5xx may have done the work.
            error = TtsNotSent if exc.code < 500 else TtsError
            raise error(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            import socket
            # Refused or unresolved: nothing reached the model. Anything else
            # (a reset, a timeout) may have, so its outcome is unknown.
            error = TtsNotSent if isinstance(exc.reason, (ConnectionRefusedError, socket.gaierror)) \
                else TtsError
            raise error(f"the speech model is not reachable: {exc}") from exc
        except (TimeoutError, ConnectionError) as exc:
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
    # One chunk asked for twice at once (a replay while it is still being
    # spoken) is sent once: the second waits, then plays the cached audio.
    with _chunk_lock(f"{folder}|{digest}"):
        cached = _cached(folder, digest)
        if cached is not None:
            return cached
        return _speak_once(vault, text, mode, model, body, folder, digest, post)


_chunk_locks: dict[str, threading.Lock] = {}
_chunk_locks_guard = threading.Lock()


@contextlib.contextmanager
def _chunk_lock(key: str) -> Any:
    with _chunk_locks_guard:
        lock = _chunk_locks.setdefault(key, threading.Lock())
    with lock:
        yield


def _cached(folder: Path, digest: str) -> dict[str, Any] | None:
    for ext, mime in (("mp3", "audio/mp3"), ("wav", "audio/wav"), ("ogg", "audio/ogg"),
                      ("flac", "audio/flac"), ("opus", "audio/opus")):
        cache = folder / f"{digest}.{ext}"
        if cache.is_file():
            return {"audio": _data_uri(mime, cache.read_bytes()), "cost_usd": 0.0,
                    "cached": True, "spent_usd": round(spent(), 6), "cap_usd": CAP_USD}
    return None


def _speak_once(vault: Vault, text: str, mode: str, model: str, body: dict[str, Any],
                folder: Path, digest: str, post: Callable[..., dict[str, Any]] | None
                ) -> dict[str, Any]:
    cost = estimate(text, model)
    rid, so_far = reserve(cost, len(text), model, mode)
    sent = False
    try:
        route = service_routes.resolve(vault, "tts", validate=True)
        if route is None or route.model != model:
            raise service_routes.ServiceRouteError("speech assignment changed; restart the operation")
        key = os.environ.get(route.key_env, "")
        if not key:
            raise TtsNotSent(f"{route.key_env} is not set (Settings -> Connections)")

        def send() -> dict[str, Any]:
            nonlocal sent
            sent = True
            return (post or _post)(f"{route.native_base()}/{model}", body, key)

        out = service_routes.run(vault, route, send)
    except BaseException as exc:
        # Released only when the request certainly cost nothing; otherwise the
        # reservation stays as a liability (a timeout, a reset, a late result).
        if isinstance(exc, TtsNotSent) or not sent:
            release(rid, f"{type(exc).__name__}: {exc}")
        else:
            settle(rid, cost, outcome="unknown")
        if isinstance(exc, (service_routes.ServiceRouteError, ProviderError)):
            raise TtsError(str(exc)) from exc
        raise
    # A result came back, so the work was done: its cost is owed from here on,
    # whatever the audio turns out to be.
    actual = float((out.get("inference_status") or {}).get("cost") or cost)
    settle(rid, actual)
    audio = str(out.get("audio") or "")
    if not audio.startswith("data:audio"):
        raise TtsError(f"the model returned no audio ({str(out)[:200]})")
    mime, raw = _playable(audio)
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
