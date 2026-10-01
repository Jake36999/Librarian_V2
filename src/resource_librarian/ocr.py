"""OCR: text for PDF pages that have no text layer (Requirements Addendum R17, slot 4).

P3b's quality check flags a scanned PDF `needs_ocr`; this reads those pages. Each page with
no extractable text is rendered to an image (pypdfium2 - BSD/Apache; PyMuPDF is AGPL and
cannot ship here) and sent to the library's chosen OCR model; pages that already have text
keep it. The result is one markdown text, page by page, kept with the staged item.

The model is the library's own choice, saved in `.librarian/config.toml`:

    [services]
    ocr = "deepinfra:Qwen/Qwen3.5-397B-A17B"
    ocr_format = "vision_chat"

`vision_chat` is an OpenAI-compatible chat call with the page as an `image_url`. An empty
`ocr` means no OCR: the page stays a stated gap - it never falls back to a chat model.
Cleaning up text that already exists is a different job, `pdf_markdown.py`'s.
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import text
from .providers import PRESETS, ProviderError, _key
from .vault import Vault

FORMATS = ("vision_chat",)
MAX_PAGES = 200            # a batch reads at most this many image-only pages per document
SCALE = 2.0                # ~144 dpi: small print stays legible
PROMPT = ("Transcribe all of the text on this page image, exactly as written, as Markdown. "
          "Keep headings, lists and tables; write mathematics in LaTeX. Do not summarise, "
          "translate, correct or add anything. If the page has no text, reply with nothing.")


class OcrError(RuntimeError):
    pass


def choice(vault: Vault) -> dict[str, str]:
    """The library's OCR model, or {} when none is chosen."""
    raw = str(vault.setting("services", "ocr") or "").strip()
    provider, _, model = raw.partition(":")
    if not (provider and model):
        return {}
    return {"provider": provider, "model": model,
            "format": str(vault.setting("services", "ocr_format") or "vision_chat")}


class VisionChat:
    """An OpenAI-compatible chat endpoint that takes an image in the message."""

    def __init__(self, provider: str, model: str, timeout: float = 180):
        if provider not in PRESETS or PRESETS[provider].get("protocol") != "openai":
            raise OcrError(f"{provider!r} is not an OpenAI-compatible provider")
        self.url = PRESETS[provider]["base_url"].rstrip("/") + "/chat/completions"
        self.key_env, self.model, self.timeout = PRESETS[provider]["key_env"], model, timeout
        self.name = f"{provider}:{model}"

    def page_text(self, png: bytes) -> str:
        key = _key(self.key_env)                           # ProviderError when no key is set
        image = "data:image/png;base64," + base64.b64encode(png).decode()
        body = {"model": self.model, "temperature": 0, "max_tokens": 4000,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": image}}]}]}
        request = urllib.request.Request(
            self.url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json",
                     **({"Authorization": f"Bearer {key}"} if key else {})})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise OcrError(f"{self.name}: HTTP {exc.code} {exc.read()[:200]!r}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise OcrError(f"{self.name}: {exc}") from exc
        try:
            return str(data["choices"][0]["message"]["content"] or "").strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise OcrError(f"{self.name}: an unexpected reply {str(data)[:200]}") from exc


def endpoint(vault: Vault, extras: dict[str, Any] | None = None) -> Any | None:
    """The OCR endpoint in use: one injected by a test or caller, else the library's choice."""
    given = (extras or {}).get("ocr_endpoint")
    if given is not None:
        return given
    chosen = choice(vault)
    if not chosen:
        return None
    if chosen["format"] not in FORMATS:
        raise OcrError(f"OCR format {chosen['format']!r} is not one of {FORMATS}")
    return VisionChat(chosen["provider"], chosen["model"])


def render_page(path: Path, index: int, scale: float = SCALE) -> bytes:
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(str(path))
    try:
        image = document[index].render(scale=scale).to_pil()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    finally:
        document.close()


def read_pdf(vault: Vault, path: Path, ocr: Any, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """Every page's text: its own text layer where it has one, OCR where it has none."""
    extracted = text.extract(path, vault.derived / "text")
    if extracted.error:
        raise OcrError(extracted.error)
    pages = list(extracted.pages)
    needed = [i for i, page in enumerate(pages) if not page.strip()]
    done, errors = 0, []
    for i in needed[:max(0, max_pages)]:
        try:
            pages[i] = ocr.page_text(render_page(path, i))
            done += 1
        except ProviderError as exc:                      # no key: every page would fail alike
            errors.append({"page": i + 1, "error": str(exc)[:200]})
            break
        except OcrError as exc:
            errors.append({"page": i + 1, "error": str(exc)[:200]})
    markdown = "\n\n".join(f"[page {n}]\n{page.strip()}" for n, page in enumerate(pages, 1)
                           if page.strip())
    return {"markdown": markdown, "pages": len(pages), "needed": len(needed), "read": done,
            "errors": errors, "model": getattr(ocr, "name", "")}


def sample_png(line: str = "The librarian reads this page.") -> bytes:
    """A small page image with a known sentence, for the slot's Test action."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (900, 220), "white")
    try:
        font = ImageFont.load_default(size=40)
    except TypeError:                                    # Pillow before 10.1
        font = ImageFont.load_default()
    ImageDraw.Draw(image).text((40, 80), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
