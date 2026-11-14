"""Free paper graph artifacts from verified persistent conversions, never summaries."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import dik
from .conversions import ConversionStore, file_sha256, is_conversion
from .coordination import atomic_write_text, operation_path
from .vault import now_iso


def export_document(vault, item):
    from .staging import _attachment_path
    original = _attachment_path(vault, item['file']) if item.get('file') else None
    data = {'file_path': original.resolve().as_posix() if original else 'catalogue:' + str(item['name']),
            'metadata': {'title': item.get('title') or item['name'], 'authors': item.get('authors', [])},
            'sections': [], 'source': 'librarian_conversion', 'producer': 'librarian-paper-conversion-v1',
            'source_extractor_version': 'librarian-conversion-v1', 'extracted_at': now_iso(),
            'usage': {'input_tokens': 0, 'output_tokens': 0, 'cost_usd': 0.0},
            'coverage': {'status': 'catalogue_only', 'page_verification': False, 'limitations': []}}
    def unavailable(reason):
        data['coverage']['limitations'].append(reason)
        return data
    if original is None or not original.is_file():
        return unavailable('Original PDF is not available; catalogue only, no page verification')
    rel = item.get('clean_file') or item.get('file_markdown')
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
            'page_start': start, 'page_end': end, 'claims': [], 'concepts': []})
    data['coverage'] = {'status': 'full_conversion', 'page_verification': False,
        'limitations': ['Generated text and chapter detection require checking original pages; no claim verification performed']}
    return data


def write_artifact(vault, item):
    data = export_document(vault, item)
    # Paid conversion is persistent; this free graph projection is rebuildable.
    key = hashlib.sha256(data['file_path'].encode()).hexdigest()[:32]
    path = operation_path(vault, '.librarian/derived/paper-graph/' + key + '.nodes.json')
    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False))
    return {'path': path.relative_to(vault.root).as_posix(), 'coverage': data['coverage'],
            'sha256': file_sha256(path), 'source': data['file_path'], 'authorship': 'generated'}
