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

import threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import base64
import io
import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import text
from .providers import PRESETS, ProviderError, _key
from .service_adapters import ServiceContractError, ocr_request
from . import service_routes
from .vault import Vault

FORMATS = ("vision_chat",)
MAX_PAGES = 200            # a batch reads at most this many image-only pages per document
SCALE = 2.0                # ~144 dpi: small print stays legible
PROMPT = ("Transcribe all of the text on this page image, exactly as written, as Markdown. "
          "Keep headings, lists and tables; write mathematics in LaTeX. Do not summarise, "
          "translate or correct source content. For each visible figure or diagram, add a "
          "separate [Visual description] identifying its labels, axes, legend and depicted "
          "relationships. Label these descriptions as generated interpretation. Mark uncertain "
          "symbols or unreadable regions explicitly; do not invent details. For a blank page, "
          "return [Blank page].")


class OcrError(RuntimeError):
    def __init__(self, message, *, response=None):
        super().__init__(message)
        self.response = response or {}


def choice(vault: Vault) -> dict[str, str]:
    """The library's OCR model, or {} when none is chosen."""
    route = service_routes.resolve(vault, "ocr")
    if route is None:
        return {}
    return {**route.choice(),
            "format": str(vault.setting("services", "ocr_format") or "vision_chat")}


class VisionChat:
    """An OpenAI-compatible chat endpoint that takes an image in the message."""

    def __init__(self, provider: str, model: str, timeout: float = 180, *,
                 route: service_routes.ServiceRoute | None = None, vault: Vault | None = None):
        if route is None and (provider not in PRESETS or PRESETS[provider].get("protocol") != "openai"):
            raise OcrError(f"{provider!r} is not an OpenAI-compatible provider")
        from .adapters.openai_chat import chat_url
        self.url = chat_url(route.base_url if route else PRESETS[provider]["base_url"])
        self.provider = provider
        self.key_env = route.key_env if route else PRESETS[provider]["key_env"]
        self.model, self.timeout, self.route, self.vault = model, timeout, route, vault
        self.name = f"{provider}:{model}"
        self._response_local = threading.local()
        runtime = service_routes.runtime(vault) if vault else None
        self.concurrency = runtime.hosts.get(route.host_id).concurrency_limit if runtime and route else 1

    @property
    def last_response(self):
        return getattr(self._response_local, "value", {})

    @last_response.setter
    def last_response(self, value):
        self._response_local.value = value

    def page_text(self, png: bytes) -> str:
        key = _key(self.key_env)                           # ProviderError when no key is set
        image = "data:image/png;base64," + base64.b64encode(png).decode()
        try:
            body, _binding = ocr_request(self.route.contract_provider if self.route else self.provider,
                                         self.model, PROMPT, image)
        except ServiceContractError as exc:
            raise OcrError(f"{self.name}: {exc}") from exc
        # Build auth headers – _request adds Content-Type itself.
        auth_headers: dict[str, str] = {}
        if key:
            auth_headers["Authorization"] = f"Bearer {key}"
        from .providers import ProviderError, _request
        try:
            def send():
                return _request("POST", self.url, auth_headers, body, self.timeout, retries=())
            data = service_routes.run(self.vault, self.route, send) if self.route and self.vault else send()
        except service_routes.ServiceRouteError as exc:
            raise OcrError(str(exc)) from exc
        except ProviderError as exc:
            # The shared transport already retried transient failures.
            raise OcrError(f"{self.name}: {exc}") from exc
        try:
            self.last_response = {"finish_reason": data["choices"][0].get("finish_reason"),
                                  "usage": data.get("usage", {})}
            if self.last_response["finish_reason"] == "length":
                first = dict(self.last_response)
                prompt_tokens = int(first["usage"].get("prompt_tokens") or 0)
                context = int(getattr(self, "context_tokens", 0) or 0)
                cap = int(getattr(self, "max_output_tokens", 8000) or 8000)
                grown = min(cap, max(0, context - prompt_tokens))
                if prompt_tokens > 0 and grown > body["max_tokens"]:
                    body["max_tokens"] = grown
                    try:
                        data = service_routes.run(self.vault, self.route, send) if self.route and self.vault else send()
                    except (ProviderError, service_routes.ServiceRouteError) as exc:
                        raise OcrError(str(exc), response=first) from exc
                    second = {"finish_reason": data["choices"][0].get("finish_reason"), "usage": data.get("usage", {})}
                    usage = dict(second["usage"])
                    for field in ("prompt_tokens", "completion_tokens", "total_tokens", "estimated_cost"):
                        if field in first["usage"] or field in second["usage"]:
                            usage[field] = (first["usage"].get(field) or 0) + (second["usage"].get(field) or 0)
                    self.last_response = {**second, "usage": usage, "attempts": [first, second],
                        "recovery": {"pattern": "OCR_OUTPUT_LIMIT", "trigger_value": "length",
                                     "action": {"max_tokens": grown}, "outcome": second["finish_reason"]}}
                if self.last_response["finish_reason"] == "length":
                    raise OcrError("OCR response truncated at its output limit; page remains incomplete", response=self.last_response)
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
    try:
        route = service_routes.resolve(vault, "ocr", validate=True)
        if route is None or route.choice() != {key: chosen[key] for key in ("provider", "model")}:
            raise service_routes.ServiceRouteError("OCR assignment changed; restart the operation")
        reader = VisionChat(chosen["provider"], chosen["model"], route=route, vault=vault)
        reader.context_tokens = int((extras or {}).get("ocr_context_tokens") or 0)
        reader.max_output_tokens = int(vault.setting("services", "ocr_max_output_tokens") or 8000)
        return reader
    except service_routes.ServiceRouteError as exc:
        raise OcrError(str(exc)) from exc


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


def read_pdf(vault: Vault, path: Path, ocr: Any, max_pages: int = MAX_PAGES, *, all_pages: bool = False, cached_pages=None, on_page=None, extracted=None) -> dict[str, Any]:
    """Every page's text: its own text layer where it has one, OCR where it has none."""
    extracted = extracted if extracted is not None else text.extract(path, vault.derived / "text")
    if extracted.error:
        raise OcrError(extracted.error)
    pages = list(extracted.pages)
    needed = [i for i, page in enumerate(pages) if all_pages or not page.strip()]
    cached_pages = cached_pages or {}
    done, errors = 0, []
    for i in needed:
        if i in cached_pages:
            pages[i] = cached_pages[i]
            done += 1
    pending = [i for i in needed if i not in cached_pages]
    pending = iter(pending[:max(0, max_pages)])
    concurrency = max(1, min(int(getattr(ocr, "concurrency", 1)), 32))
    def transcribe(png):
        value = ocr.page_text(png)
        return value, getattr(ocr, "last_response", {})
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        active = {}
        def submit_next():
            i = next(pending, None)
            if i is not None:
                # PDFium rendering and all durable writes stay on the caller.
                active[pool.submit(transcribe, render_page(path, i))] = i
        for _ in range(concurrency):
            submit_next()
        while active:
            ready, _ = wait(active, return_when=FIRST_COMPLETED)
            for future in ready:
                i = active.pop(future)
                try:
                    pages[i], metadata = future.result()
                    ocr.last_response = metadata
                    if on_page is not None:
                        on_page(i, pages[i])
                    done += 1
                except (ProviderError, OcrError) as exc:
                    errors.append({"page": i + 1, "error": str(exc)[:200],
                                   **({"response": exc.response} if getattr(exc, "response", None) else {})})
                submit_next()
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
