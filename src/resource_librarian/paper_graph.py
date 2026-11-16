"""Free paper graph artifacts from verified persistent conversions, never summaries."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from . import dik
from .conversions import ConversionStore, file_sha256, is_conversion
from .coordination import atomic_write_text, operation_path
from .vault import now_iso


TEXT_LAYER_METHOD = 'text-layer:v1'


def text_layer_conversion(vault, original):
    """A free, page-anchored conversion of a PDF whose own text layer is complete (2026-11-16).

    With `optical_all_pages` off, a clean PDF is read straight from its text layer and never
    gets a persistent conversion, so it could never reach its paper graph. This records that
    same text, page by page, as a generated conversion bound to the original's bytes. A PDF
    with any page lacking text gets none: its paper stays catalogue-only.
    """
    from . import text
    store = ConversionStore(vault)
    request = store.request(original, TEXT_LAYER_METHOD)
    held = store.find(request)
    if held is not None:
        return held['path']
    extracted = text.extract(original, vault.derived / 'text')
    pages = list(extracted.pages or [])
    if extracted.error or not pages or not all(p.strip() for p in pages):
        return None
    markdown = '\n\n'.join(f'[page {n}]\n{page.strip()}' for n, page in enumerate(pages, 1))
    return store.save(request, markdown, pages=len(pages), needed=len(pages), read=len(pages))['path']


def reading_claims(item, start, end):
    """The read points and limits located on pages start-end: generated and unverified, each
    kept with its locator. A point spanning sections belongs to the one holding its first page."""
    claims = []
    for chunk in ((item.get('deep_read') or {}).get('read') or {}).values():
        found = re.match(r'pp?\.\s*(\d+)', str(chunk.get('locator') or ''))
        if not found or not start <= int(found.group(1)) <= end:
            continue
        for kind, key in (('reading_point', 'points'), ('reading_limit', 'limits')):
            for text_ in chunk.get(key) or []:
                if isinstance(text_, str) and text_.strip():
                    claims.append({'text': text_.strip(), 'claim_type': kind})
    return claims


def export_document(vault, item, *, text_layer=False):
    from .catalogue_navigation import use_rollup
    from .staging import _attachment_path
    original = None
    if item.get('file'):
        candidate = Path(item['file'])
        if candidate.is_absolute() and not candidate.resolve().is_relative_to(vault.root):
            from .read_access import source_path
            from .registry import Context
            original = source_path(Context(vault=vault), str(candidate))
        else:
            original = _attachment_path(vault, item['file'])
    data = {'file_path': original.resolve().as_posix() if original else 'catalogue:' + str(item['name']),
            'metadata': {'title': item.get('title') or item['name'], 'authors': item.get('authors', [])},
            'sections': [], 'source': 'librarian_conversion', 'producer': 'librarian-paper-conversion-v1',
            'source_extractor_version': 'librarian-conversion-v1', 'extracted_at': now_iso(),
            'usage': {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0},
            'coverage': {'status': 'catalogue_only', 'page_verification': False, 'limitations': []},
            'catalogue': {'authorship': 'generated', 'captured_at': now_iso(),
                          'use_rollup': use_rollup(vault, item['name'])}}
    def unavailable(reason):
        data['coverage']['limitations'].append(reason)
        return data
    if original is None or not original.is_file():
        return unavailable('Original PDF is not available; catalogue only, no page verification')
    rel = item.get('clean_file') or item.get('file_markdown')
    if not rel and text_layer:
        rel = text_layer_conversion(vault, original)
    if not rel or not is_conversion(vault, rel):
        return unavailable('No verified persistent full conversion; catalogue summary is not source text')
    store = ConversionStore(vault)
    entry = store.entry(rel)
    if entry.get('errors') or entry.get('read', 0) < entry.get('needed', 0):
        return unavailable('Conversion has unread or failed OCR pages; full source coverage is unavailable')
    if file_sha256(original) != entry['original_sha256']:
        return unavailable('Original bytes no longer match the conversion')
    units = store.page_units(rel)
    if not units:
        return unavailable('Conversion page mapping is missing or unverified')
    request = store.request(original, entry['method'])
    resolved = store.find(request)
    if not resolved or resolved['path'] != rel:
        return unavailable('Conversion cache binding is inconsistent')
    if resolved['source_authorship'] is None:
        return unavailable('Original authorship is unclassified')
    pages = [text for _, text in units]
    data.update(page_count=len(pages), source_sha256=entry['original_sha256'],
                original={'path': original.resolve().as_posix(), 'sha256': entry['original_sha256'],
                          'authorship': resolved['source_authorship'],
                          'evidence_id': resolved['original_evidence_id']},
                conversion={'path': str((vault.root / rel).resolve()), 'sha256': entry['sha256'],
                            'authorship': 'generated', 'evidence_id': entry['evidence_id']})
    for position, chapter in enumerate(dik.chapters(pages)):
        start, end = chapter['first_page'], chapter['last_page']
        body = '\n\n'.join(pages[start - 1:end])
        data['sections'].append({'heading': chapter['title'], 'position': position,
            'section_type': 'other', 'text': body, 'word_count': len(body.split()),
            'page_start': start, 'page_end': end, 'claims': reading_claims(item, start, end),
            'concepts': []})
    limitations = ['Generated text and chapter detection require checking original pages; no claim verification performed']
    if any(s['claims'] for s in data['sections']):
        limitations.append('Claims are the Librarian reading\'s generated points and limits, located by page; '
                           'unverified against the original')
    data['coverage'] = {'status': 'full_conversion', 'page_verification': False, 'limitations': limitations}
    return data


def write_artifact(vault, item, *, text_layer=False):
    data = export_document(vault, item, text_layer=text_layer)
    # Paid conversion is persistent; this free graph projection is rebuildable.
    key = hashlib.sha256(data['file_path'].encode()).hexdigest()[:32]
    path = operation_path(vault, '.librarian/derived/paper-graph/' + key + '.nodes.json')
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
    return {'path': path.relative_to(vault.root).as_posix(), 'coverage': data['coverage'],
            'sha256': file_sha256(path), 'source': data['file_path'], 'authorship': 'generated'}


def publish_artifact(vault, item, artifact):
    """Publish only within the person's accepted, current folder assignment."""
    from . import folder_review
    config = folder_review.configuration(vault)
    if not config.get('enabled'):
        return dict(status='disabled')
    if artifact['coverage']['status'] != 'full_conversion':
        return dict(status='catalogue_only', published=False)
    source = Path(artifact['source']).resolve()
    review = folder_review.FolderReview(vault)
    candidates = []
    for card in review.list():
        root = Path(card['source_root']) / card['path']
        if source.is_relative_to(root.resolve()):
            candidates.append((len(root.parts), card))
    card = max(candidates, key=lambda r:r[0])[1] if candidates else None
    # A person's acceptance, or the library's agent policy when the person set promotion.mode =
    # agent (owner, 2026-11-15/16): policy decisions never publish in a person-mode library.
    accepted_by = (card or {}).get('decision', {}).get('accepted_by')
    trusted = accepted_by == 'person' or (accepted_by == 'agent-policy'
                                          and str(vault.setting('promotion', 'mode') or 'person') == 'agent')
    if (not card or card['status'] != 'accepted' or card.get('pending_decision') or not trusted
            or card['decision']['purpose'] == 'exclude'):
        return dict(status='awaiting_accepted_folder', published=False)
    review.validate(card)
    path = vault.root / artifact['path']
    if file_sha256(path) != artifact['sha256']:
        raise ValueError('PAPER_ARTIFACT_STALE: rebuild the free projection')
    return folder_review.cli(config, ['import-library-paper', '--catalog',
        str(vault.librarian / 'geographer/catalog.sqlite')], dict(library=str(vault.root),
        graph_label=card['decision']['graph'], artifact=str(path), artifact_sha256=artifact['sha256']))
