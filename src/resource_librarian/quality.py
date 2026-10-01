"""What capture actually got, per source kind (Requirements Addendum R12: "each source kind
has a declared subflow with a quality branch").

Deterministic, and cheap enough to run on every capture. Each check returns a verdict, the
reason in a sentence, and the next action; the verdict decides what the approved batch does
with the item (`batch.py`) and what the accepted note says was not examined.

| Kind | Verdicts |
| --- | --- |
| document | usable · cleanup (broken wraps, running headers, page numbers) · needs_ocr |
| page | usable · js_shell (the text is built by scripts, not in the HTML) |
| repository | usable · partial (no README, or the file tree was truncated) |
| paper | metadata_only (the abstract; the batch fetches the open-access PDF if one is known) |
| dataset | usable (access points found) · no_access_point |
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

OCR_SHARE = 0.3            # this share of pages without text: the file needs OCR
SHELL_TEXT = 400           # a page with less text than this and several scripts is a shell
SHELL_SCRIPTS = 3


def verdict(name: str, reason: str, next_action: str, **detail: Any) -> dict[str, Any]:
    return {"verdict": name, "reason": reason, "next": next_action, **detail}


def document(pages: list[str], empty_pages: int, is_pdf: bool = True) -> dict[str, Any]:
    n = max(1, len(pages))
    if empty_pages >= n or not any(p.strip() for p in pages):
        return verdict("needs_ocr", "no page has a text layer: it is scanned or image-only",
                       "OCR it outside the librarian, then ingest the OCR'd file",
                       pages=len(pages), empty_pages=empty_pages)
    if empty_pages / n >= OCR_SHARE:
        return verdict("needs_ocr", f"{empty_pages} of {len(pages)} pages have no text layer",
                       "OCR the file for the missing pages; the rest can be read as it is",
                       pages=len(pages), empty_pages=empty_pages)
    if not is_pdf:
        return verdict("usable", "text extracted", "nothing", pages=len(pages))
    noise = _noise(pages)
    if noise["score"] >= 1:
        return verdict("cleanup", "the extracted text is mechanical: " + ", ".join(
            noise["signs"]), "the approved batch cleans it into markdown (pdf_to_markdown) "
            "before reading it", pages=len(pages), empty_pages=empty_pages, signs=noise["signs"])
    return verdict("usable", "text extracted cleanly", "nothing", pages=len(pages),
                   empty_pages=empty_pages)


def _noise(pages: list[str]) -> dict[str, Any]:
    """Signs of raw PDF extraction a reader stumbles over: words hyphenated across lines,
    the same header or footer on most pages, bare page numbers."""
    lines = [ln.strip() for p in pages for ln in p.splitlines() if ln.strip()]
    if not lines:
        return {"score": 0, "signs": []}
    signs, score = [], 0.0
    breaks = sum(1 for a, b in zip(lines, lines[1:]) if a.endswith("-") and b[:1].islower())
    if breaks / len(lines) > 0.03:
        signs.append(f"{breaks} words broken across lines")
        score += 1
    if len(pages) >= 3:
        per_page = Counter(ln for p in pages for ln in {x.strip() for x in p.splitlines()
                                                        if x.strip()})
        repeated = [ln for ln, c in per_page.items() if c >= max(3, len(pages) * 0.6)
                    and len(ln) < 80]
        if repeated:
            signs.append(f"{len(repeated)} running header/footer line(s)")
            score += 1
    numbers = sum(1 for ln in lines if re.fullmatch(r"(page\s+)?\d{1,4}(\s+of\s+\d+)?", ln, re.I))
    if len(pages) >= 3 and numbers >= len(pages) * 0.6:
        signs.append("bare page numbers")
        score += 0.5
    return {"score": score, "signs": signs}


def page(text: str, scripts: int) -> dict[str, Any]:
    if len(text.strip()) < SHELL_TEXT and scripts >= SHELL_SCRIPTS:
        return verdict("js_shell", f"only {len(text.strip())} characters of text beside "
                       f"{scripts} scripts: the page builds its content in the browser",
                       "render it with the Playwright MCP server (Settings → MCP servers) "
                       "and ingest what it shows, or find a static copy",
                       text_chars=len(text.strip()), scripts=scripts)
    return verdict("usable", "text read from the HTML", "nothing",
                   text_chars=len(text.strip()))


def repository(readme: str, truncated: bool) -> dict[str, Any]:
    missing = ([] if readme.strip() else ["no README"]) + (
        ["the file tree was truncated by the host"] if truncated else [])
    if missing:
        return verdict("partial", "; ".join(missing), "read the repository's own docs or "
                       "tree in the batch; the description rests on what was fetched")
    return verdict("usable", "README and file tree read", "nothing")


def paper(abstract: str, full_text_url: str) -> dict[str, Any]:
    base = "the abstract and metadata" if abstract.strip() else "the metadata only (no abstract)"
    if full_text_url:
        return verdict("metadata_only", f"{base} read; the whole paper was not",
                       "the approved batch fetches the open-access PDF and reads it",
                       full_text_url=full_text_url)
    return verdict("metadata_only", f"{base} read; no open-access PDF is known",
                   "find an open-access copy (a preprint, the author's page) and ingest it")


def dataset(access_points: list[dict[str, str]]) -> dict[str, Any]:
    if access_points:
        return verdict("usable", f"{len(access_points)} access point(s) found", "nothing",
                       access_points=len(access_points))
    return verdict("no_access_point", "no downloadable file or API link on the page",
                   "find the dataset's download or API page and ingest that")
