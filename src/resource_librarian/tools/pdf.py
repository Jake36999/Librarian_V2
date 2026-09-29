"""Clean a PDF's mechanically-extracted text into readable markdown
(pdf_markdown.py) - the step V1 ran before a book's text ever reached intake,
ported forward as its own tool rather than folded silently into every PDF's
ingestion (that would change ingestion's cost for every vault without anyone
having decided it should)."""
from __future__ import annotations

from .. import pdf_markdown, text
from ..registry import Card, Context, tool


@tool("pdf_to_markdown", tier="contribute", effect="write", open_world=True,
      returns=("path", "pages", "batches"),
      card=Card("Clean a PDF's mechanically-extracted text into readable markdown, written "
                "beside it as its own .md file",
                "a PDF's raw extraction is full of broken line-wraps, running headers/footers "
                "and page numbers, and a clean copy would help both the person and the model "
                "read it",
                "Reformats only - never summarises, shortens or adds anything not in the "
                "source. Always deepseek-ai/DeepSeek-V4-Flash-0731 on DeepInfra, whatever this "
                "vault's own [clerk] route is set to (which may be a local model)"))
def pdf_to_markdown_tool(ctx: Context, file: str) -> dict:
    path = (ctx.vault.root / file).resolve()
    if ctx.vault.root not in path.parents or not path.is_file():
        raise TypeError(f"{file!r} is not a file inside this vault")
    if path.suffix.lower() != ".pdf":
        raise TypeError(f"{file!r} is not a PDF")
    result = text.extract(path, ctx.vault.derived / "text")
    if result.error:
        raise TypeError(result.error)
    if not any(p.strip() for p in result.pages):
        raise TypeError(f"{file!r} has no extractable text (a scanned PDF needs OCR first)")
    markdown, batches = pdf_markdown.clean_document(result.pages)
    out_path = path.with_suffix(".md")
    out_path.write_text(markdown, encoding="utf-8")
    return {"path": str(out_path.relative_to(ctx.vault.root)).replace("\\", "/"),
            "pages": len(result.pages), "batches": batches}
