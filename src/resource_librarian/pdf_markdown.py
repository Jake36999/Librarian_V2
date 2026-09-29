"""A PDF's mechanically-extracted text, reformatted into clean markdown by one
fixed model - ported from `.utility/scripts/pdf_to_markdown.py` (V1), which
already did this job well converting the books under `06-Papers/PDF's/`.

The model is deliberately not configurable, on the person's own instruction:
always DeepInfra's `deepseek-ai/DeepSeek-V4-Flash-0731`, regardless of what a
vault's own `[clerk]` route is set to (which may be a local model) - a vault
whose ingestion otherwise runs locally still gets this one step from
DeepInfra, the same model that proved itself on the original conversion.

Mechanical extraction itself stays on `pypdf` (BSD) rather than V1's PyMuPDF
(AGPL, cannot ship in this package - see `text.py`); only the reformatting
step is carried over, unchanged in what it is told to do:
reflow line-wraps, drop running headers/footers/page numbers, add heading
levels, never summarise or add anything not in the source.
"""
from __future__ import annotations

from .providers import OpenAICompatible, PRESETS

MODEL = "deepseek-ai/DeepSeek-V4-Flash-0731"
BATCH_CHARS = 6000
REASONING_FLOOR = 1800

CLEANUP_SYSTEM = (
    "You reformat raw PDF-extracted text into clean markdown. You do not "
    "summarize, shorten, paraphrase, or add anything not in the source. "
    "Fix only: broken line-wraps, running headers/footers and page numbers "
    "(remove them), heading levels (## for section headings you can "
    "identify from capitalization/numbering), paragraph breaks, and obvious "
    "table structure. If a sentence is cut off at the very start or end of "
    "the batch because of the page boundary, leave it as-is rather than "
    "guessing the missing words. Output only the cleaned markdown, no "
    "commentary."
)


def endpoint() -> OpenAICompatible:
    """Always this one model, on DeepInfra - never the vault's own [clerk]
    route, which may be a local model unsuited to this (or any) task."""
    preset = PRESETS["deepinfra"]
    return OpenAICompatible(preset["base_url"], MODEL, preset["key_env"], name="deepinfra")


def batch_pages(pages: list[str], batch_chars: int = BATCH_CHARS) -> list[str]:
    """Consecutive pages grouped under `batch_chars`, so a sentence split
    across a page boundary lands in the same call as its other half."""
    batches: list[str] = []
    current: list[str] = []
    size = 0
    for page in pages:
        current.append(page)
        size += len(page)
        if size >= batch_chars:
            batches.append("\n\n".join(current))
            current, size = [], 0
    if current:
        batches.append("\n\n".join(current))
    return batches


def clean_text(raw: str, ep: OpenAICompatible | None = None) -> str:
    """One blob of raw extracted text, reformatted. Raises `ProviderError`
    (no key, unreachable, the model's own error) - never silently degrades,
    since the whole point of calling this is the cleaner text."""
    ep = ep or endpoint()
    reply = ep.chat(CLEANUP_SYSTEM, [{"role": "user", "content": raw}], [],
                    max_tokens=REASONING_FLOOR + max(2000, int(len(raw) * 0.6)))
    return reply.text.strip()


def clean_document(pages: list[str], ep: OpenAICompatible | None = None) -> tuple[str, int]:
    """Every page, batched and cleaned, joined into one markdown document -
    for a person or the model to read whole, the way V1's script wrote a
    `.md` sibling next to a PDF. Returns (markdown, batches billed)."""
    ep = ep or endpoint()
    batches = batch_pages(pages)
    cleaned = [clean_text(batch, ep) for batch in batches]
    return "\n\n".join(cleaned), len(batches)
