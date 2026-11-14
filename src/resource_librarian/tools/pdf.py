"""Clean a PDF's mechanically-extracted text into readable markdown
(pdf_markdown.py) - the step V1 ran before a book's text ever reached intake,
ported forward as its own tool rather than folded silently into every PDF's
ingestion (that would change ingestion's cost for every vault without anyone
having decided it should)."""
from __future__ import annotations

from .. import ocr, pdf_markdown, text
from ..registry import Card, Context, tool
from ..conversions import ConversionStore


@tool("pdf_to_markdown", tier="contribute", effect="write", scope="session", open_world=True,
      returns=("path", "pages", "batches"),
      card=Card("Clean a PDF's mechanically-extracted text into readable markdown, written "
                "as generated library work under .librarian/conversions/",
                "a PDF's raw extraction is full of broken line-wraps, running headers/footers "
                "and page numbers, and a clean copy would help both the person and the model "
                "read it",
                "Reformats only - never summarises, shortens or adds anything not in the "
                "source. Always deepseek-ai/DeepSeek-V4-Flash-0731 on DeepInfra, whatever this "
                "vault's own [clerk] route is set to (which may be a local model)"))
def pdf_to_markdown_tool(ctx: Context, file: str, staged_item: str = "") -> dict:
    """Generated text remains hidden and reusable even after source acceptance.

    `staged_item` is retained for existing approved batch callers.
    """
    path = (ctx.vault.root / file).resolve()
    if ctx.vault.root not in path.parents or not path.is_file():
        raise TypeError(f"{file!r} is not a file inside this vault")
    if path.suffix.lower() != ".pdf":
        raise TypeError(f"{file!r} is not a PDF")
    store = ConversionStore(ctx.vault)
    request = store.request(path, 'pdf_markdown:v1:' + pdf_markdown.MODEL)
    cached = store.find(request)
    if cached is not None:
        return cached
    result = text.extract(path, ctx.vault.derived / "text")
    if result.error:
        raise TypeError(result.error)
    if not any(p.strip() for p in result.pages):
        raise TypeError(f"{file!r} has no extractable text (a scanned PDF needs OCR first)")
    markdown, batches = pdf_markdown.clean_document(result.pages,
                                                   ctx.extras.get("pdf_endpoint"),
                                                   progress=ctx.extras.get("progress"))
    return store.save(request, markdown, pages=len(result.pages), batches=batches)


@tool("ocr_pdf", tier="contribute", effect="write", scope="session", open_world=True,
      returns=("path", "pages", "needed", "read", "errors", "model"),
      card=Card("Read a PDF's pages that have no text layer (a scan) with the library's OCR "
                "model, into one markdown text", "a PDF was flagged needs_ocr",
                "Pages with text keep their own; only image-only pages are sent, each as one "
                "call to the OCR model chosen in Settings -> Connections (slot 4). With none "
                "chosen it refuses rather than use a chat model"))
def ocr_pdf_tool(ctx: Context, file: str, staged_item: str = "",
                 max_pages: int = ocr.MAX_PAGES) -> dict:
    path = (ctx.vault.root / file).resolve()
    if ctx.vault.root.resolve() not in path.parents or not path.is_file():
        raise TypeError(f"{file!r} is not a file inside this vault")
    if path.suffix.lower() != ".pdf":
        raise TypeError(f"{file!r} is not a PDF")
    reader = ocr.endpoint(ctx.vault, ctx.extras)
    if reader is None:
        raise TypeError("no OCR model is chosen for this library: Settings -> Connections, "
                        "slot 4")
    store = ConversionStore(ctx.vault)
    request = store.request(path, 'ocr:v1:' + str(getattr(reader, 'name', '')) + ':' + str(max_pages))
    cached = store.find(request)
    if cached is not None:
        return cached
    got = ocr.read_pdf(ctx.vault, path, reader, max_pages)
    markdown = got.pop('markdown')
    pages = got.pop('pages')
    return store.save(request, markdown, pages=pages, **got)
