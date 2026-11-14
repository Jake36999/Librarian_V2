"""Read located conversion sections and original pages; no model/OCR per access."""
from __future__ import annotations
import hashlib
from typing import Literal

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


@tool('source_verification_plan', tier='consult', effect='read',
      card=Card('Prepare two tier-2 tasks or one tier-1 task to compare a located conversion section with original PDF pages',
                'after a paper graph section supplies its original SHA, page range and corpus revision',
                'Run dispatch_plan(plan, dry_run=True) first. The plan rechecks section, original bytes and revision; it never requests a whole document.'))
def source_verification_plan(ctx: Context, source: str, claim: str, graph_id: str,
                             document: str, section_id: int, tier: Literal[1, 2] = 2,
                             server: str = '') -> dict:
    from ..source_verification import make_plan
    from .plan_dispatch import _call_external
    mcp = ctx.extras.get('mcp')
    candidates = []
    if mcp:
        for name, state in mcp.status().items():
            if (all(state.get(k) for k in ('enabled', 'accepted', 'connected'))
                    and state.get('library_enabled') is not False
                    and f'mcp__{name}__paper_get_section' in mcp.tool_names(name)):
                candidates.append(name)
    if not server and len(candidates) == 1:
        server = candidates[0]
    if server not in candidates:
        raise ValueError('PLAN_SERVER_UNAVAILABLE: name one accepted server with paper_get_section')
    result = _call_external(ctx, server, 'paper_get_section', {'graph_id': graph_id,
        'request': {'title': document, 'section_id': section_id, 'max_chars': 500}})
    body = result.get('result', result)
    provenance = body.get('provenance', {})
    location = provenance.get('location', {}) if isinstance(provenance, dict) else {}
    start, end = location.get('page_start'), location.get('page_end')
    revision = body.get('context', {}).get('corpus_revision')
    if (body.get('section_id') != section_id or not revision
            or type(start) is not int or type(end) is not int or not 1 <= start <= end <= start + 7):
        raise ValueError('PLAN_SOURCE_SCOPE: select a graph section with 1–8 original pages and a corpus revision')
    original = source_path(ctx, source)
    if file_sha256(original) != provenance.get('source_sha256'):
        raise ValueError('PLAN_SOURCE_SCOPE: original bytes differ from the graph source')
    return {'plan': make_plan(server=server, graph_id=graph_id, document=document,
        section_id=section_id, corpus_revision=revision, source=source,
        pages=list(range(start, end + 1)), claim=claim, tier=tier), 'based_on': 'evidence_to_claim_check',
        'next': 'dispatch_plan with dry_run=true; model dispatch requires its normal route and qualification gates'}


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
