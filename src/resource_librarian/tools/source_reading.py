"""Read located conversion sections and original pages; no model/OCR per access."""
from __future__ import annotations
import hashlib

from .. import access
from ..conversions import ConversionStore, file_sha256
from ..read_access import bounded_pages, project_pages, source_path, ROUTE
from ..registry import Card, Context, tool
from ..rules import Refusal


@tool('request_raw_source_access', tier='contribute', effect='write', scope='session',
      card=Card('Ask a person for one raw source read by this session and bound route',
                'a tier-1 or tier-2 task needs raw access instead of the located section route',
                'No read occurs until approved. Bound to bytes, arguments, route and tier; never clears publication taint.'))
def request_raw_source_access(ctx: Context, tool_name: str, arguments: dict, recipient_tier: int = 0) -> dict:
    from ..read_access import request_raw
    return request_raw(ctx, tool_name, arguments, recipient_tier)


@tool('verify_source_pages', tier='consult', effect='read',
      returns=('pages', 'source', 'claim_verification', 'allocation'),
      card=Card('Read 1–8 located pages of the original PDF to check a claim',
                'after catalogue → graph → conversion section',
                'No OCR or model call. Reports the original pages and literal quote presence; does not verify a scientific claim.'))
def verify_source_pages(ctx: Context, source: str, pages: list[int], claim: str) -> dict:
    pages = bounded_pages(pages)
    path = source_path(ctx, source)
    if path.suffix.lower() != '.pdf':
        raise TypeError('Original-page verification requires a PDF; do not invent pages for other formats')
    from pypdf import PdfReader
    with path.open('rb') as handle:
        reader = PdfReader(handle)
        if any(p > len(reader.pages) for p in pages):
            raise TypeError('A selected page is outside the original PDF')
        units = [(n, reader.pages[n - 1].extract_text() or '') for n in pages]
    authorship = access._native_authorship(ctx, str(path))
    return project_pages(ctx, units, source=str(path), original_sha256=file_sha256(path),
        authorship=authorship, original_pages_read=True, claim_excerpt=claim[:200],
        claim_sha256=hashlib.sha256(claim.encode()).hexdigest(),
        claim_verification='not_performed',
        literal_quote_present=bool(claim.strip()) and claim.strip() in '\n\n'.join(t for _, t in units),
        text_origin='original PDF text layer; no OCR', primary_source=True)


@tool('read_source_section', tier='consult', effect='read',
      returns=('pages', 'source', 'allocation'),
      card=Card('Read a located, bounded set of original-page sections from a cached full conversion',
                'after catalogue and graph lookup',
                'Generated text is not an original source. Next check the original with verify_source_pages.'))
def read_source_section(ctx: Context, source: str, pages: list[int]) -> dict:
    pages = bounded_pages(pages)
    path = source_path(ctx, source)
    store = ConversionStore(ctx.vault)
    sha = file_sha256(path)
    for entry in store._index()['items'].values():
        if entry.get('original_sha256') != sha:
            continue
        units = dict(store.page_units(entry['path']))
        if not units or any(p not in units for p in pages):
            continue
        if entry.get('errors') or entry.get('read', 0) < entry.get('needed', 0):
            continue
        return project_pages(ctx, [(p, units[p]) for p in pages], source=str(path),
            original_sha256=sha, authorship='generated', source_authorship=access._native_authorship(ctx, str(path)),
            conversion_evidence_id=entry['evidence_id'], primary_source=False,
            next='verify_source_pages', claim_verification='not_performed')
    raise Refusal('THIRD_PARTY_ROUTE_REQUIRED', 'Catalogue only: no complete page-anchored conversion matches this original; no OCR was run', {'route': ROUTE})
