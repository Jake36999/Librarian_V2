"""Clean a PDF's mechanically-extracted text into readable markdown
(pdf_markdown.py) - the step V1 ran before a book's text ever reached intake,
ported forward as its own tool rather than folded silently into every PDF's
ingestion (that would change ingestion's cost for every vault without anyone
having decided it should)."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .. import ocr, pdf_markdown, text, usage_log
from ..registry import Card, Context, tool
from ..conversions import ConversionStore
from ..file_access import connected_read_path


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
    path = connected_read_path(ctx.vault, file)
    if not path.is_file():
        raise TypeError(f"{file!r} is not a file inside this vault")
    if path.suffix.lower() != ".pdf":
        raise TypeError(f"{file!r} is not a PDF")
    store = ConversionStore(ctx.vault)
    request = store.request(path, 'pdf_markdown:page-anchors-v2:' + pdf_markdown.MODEL)
    cached = store.find(request)
    if cached is not None:
        return cached
    legacy = store.find(store.request(path, 'pdf_markdown:v1:' + pdf_markdown.MODEL))
    if legacy is not None:
        return {**legacy, 'page_mapping': 'unverified'}
    result = text.extract(path, ctx.vault.derived / "text")
    if result.error:
        raise TypeError(result.error)
    if not any(p.strip() for p in result.pages):
        raise TypeError(f"{file!r} has no extractable text (a scanned PDF needs OCR first)")
    anchored = [f'[page {n}]\n{page}' for n, page in enumerate(result.pages, 1)]
    if usage_log.budget(ctx.vault)["over"]:
        raise TypeError("the library's budget ceiling was reached; no cleanup was run")

    def spent(usage):
        usage_log.record_call(ctx.vault, role="cleanup", task="pdf_to_markdown", model=pdf_markdown.MODEL,
                              host="deepinfra", tokens_in=usage.get("input_tokens"),
                              tokens_out=usage.get("output_tokens"))
    markdown, batches = pdf_markdown.clean_document(anchored,
                                                   ctx.extras.get("pdf_endpoint"),
                                                   progress=ctx.extras.get("progress"),
                                                   on_usage=spent)
    return store.save(request, markdown, pages=len(result.pages), batches=batches)


@tool("ocr_pdf", tier="contribute", effect="write", scope="session", open_world=True, orchestrates=True,
      returns=("path", "pages", "needed", "read", "errors", "model"),
      card=Card("Read a PDF's pages that have no text layer (a scan) with the library's OCR "
                "model, into one markdown text", "a PDF was flagged needs_ocr",
                "Pages with text keep their own; only image-only pages are sent, each as one "
                "call to the OCR model chosen in Settings -> Connections (slot 4). With none "
                "chosen it refuses rather than use a chat model"))
def ocr_pdf_tool(ctx: Context, file: str, staged_item: str = "",
                 max_pages: int = ocr.MAX_PAGES, all_pages: bool = False) -> dict:
    path = connected_read_path(ctx.vault, file)
    if not path.is_file():
        raise TypeError(f"{file!r} is not a file inside this vault")
    if path.suffix.lower() != ".pdf":
        raise TypeError(f"{file!r} is not a PDF")
    reader = ocr.endpoint(ctx.vault, ctx.extras)
    if reader is None:
        raise TypeError("no OCR model is chosen for this library: Settings -> Connections, "
                        "slot 4")
    store = ConversionStore(ctx.vault)
    request = store.request(path, 'ocr:v3-visual:' + str(all_pages) + ':' + str(getattr(reader, 'name', '')) + ':' + str(max_pages))
    def commit(fn):
        from ..conversions import file_sha256
        from ..rules import Refusal
        def checked():
            if file_sha256(path) != request.original_sha256:
                raise Refusal("EVIDENCE_IS_NEVER_EDITED", "Original PDF changed during OCR; retry from its current bytes")
            return fn()
        writer = ctx.extras.get("vault_writer")
        return writer.submit(checked, caller="ocr-conversion") if writer is not None else checked()
    cached = commit(lambda: store.find(request))
    if cached is not None and cached.get("read", 0) >= cached.get("needed", 0) and not cached.get("errors"):
        return cached
    page_requests = {}
    cached_pages = {}
    extracted = commit(lambda: text.extract(path, ctx.vault.derived / "text"))
    for i in range(len(extracted.pages)):
        page_request = store.request(path, request.method + ':page:' + str(i))
        page_requests[i] = page_request
        held = commit(lambda: store.find(page_request))
        if held is not None:
            cached_pages[i] = (ctx.vault.root / held['path']).read_text(encoding='utf-8')
    pending_writes = []
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-page-commit") as persistence:
        def save_page(i, value):
            metadata = getattr(reader, 'last_response', {})
            usage = (metadata or {}).get('usage') or {}
            usage_log.record_call(ctx.vault, role='ocr', task='page', model=getattr(reader, 'name', ''),
                                  tokens_in=usage.get('prompt_tokens'), tokens_out=usage.get('completion_tokens'),
                                  usd=usage.get('estimated_cost'))
            pending_writes.append(persistence.submit(commit, lambda: store.save(
                page_requests[i], value, pages=1, page_number=i + 1,
                model=getattr(reader, 'name', ''), response=metadata)))
            # Bound buffered page text while allowing capture to overlap a busy writer.
            if len(pending_writes) >= max(4, 4 * int(getattr(reader, "concurrency", 1))):
                pending_writes.pop(0).result()
        got = ocr.read_pdf(ctx.vault, path, reader, max_pages, all_pages=all_pages,
                           cached_pages=cached_pages, on_page=save_page, extracted=extracted,
                           keep_going=lambda: not usage_log.budget(ctx.vault)['over'])
        for future in pending_writes:
            future.result()
    markdown = got.pop('markdown')
    pages = got.pop('pages')
    return commit(lambda: store.save(request, markdown, pages=pages, **got))
