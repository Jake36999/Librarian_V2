"""Owner-reviewed model metadata and staged V1 refreshes; no tier mapping or probes."""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import notes
from .credentials import refuse_credentials
from .rules import Refusal

AUTHOR_RANK = {'third_party': 0, 'generated': 1, 'owner_created': 2}
OWNER_SECTIONS = {'reading notes', 'personal notes', 'owner notes', 'test notes', 'live test notes', 'my observations'}


def identity(fm):
    provider = str(fm.get('provider') or '').casefold()
    provider = {'lmstudio_local': 'local', 'lmstudio': 'local'}.get(provider, provider)
    return provider, str(fm.get('model_id') or '').casefold()


def card_authorship(fields):
    explicit = fields.get('authorship')
    if 'authorship' in fields:return explicit if isinstance(explicit, str) and explicit in AUTHOR_RANK else None
    return 'generated' if fields.get('drafted_by') else 'owner_created'


def merge_profiles(*layers):
    out, ranks = {}, {}
    for layer, records in enumerate(layers):
        for key, fields in records.items():
            result = out.setdefault(key, {'_field_authorship': {}, '_field_sources': {}})
            default = fields.get('authorship', 'generated')
            default = default if default in AUTHOR_RANK else 'generated'
            authors = fields.get('field_authorship', fields.get('_field_authorship', {}))
            for field, value in fields.items():
                if field in {'field_authorship', '_field_authorship', '_field_sources'}:continue
                if field == 'recommendation_rank' and (type(value) is not int or value < 1):continue
                author = authors.get(field, default) if isinstance(authors, dict) else default
                author = author if author in AUTHOR_RANK else default
                if AUTHOR_RANK[author] > AUTHOR_RANK[default]:author = default
                rank = (AUTHOR_RANK[author], layer)
                if rank >= ranks.get((key, field), (-1, -1)):
                    result[field] = value; ranks[key, field] = rank
                    result['_field_authorship'][field] = author
                    origins = fields.get('_field_sources') or {}
                    previous = origins.get(field, {}) if isinstance(origins, dict) else {}
                    result['_field_sources'][field] = {'authorship': author,
                        'path': previous.get('path') or fields.get('_path', ''), 'layer': layer}
    return out


def refresh_plan(v1_root, vault, row, fm):
    """Only model cards have a refresh path; ordinary V1 import behavior is retained."""
    if row.get('shape') != 'source' or row.get('kind') != 'model' or row.get('v1_type') != 'ai_model':return None
    author = card_authorship(fm)
    if author is None:return {**row, 'action': 'left out', 'why': 'Model-card authorship is unclassified; choose the closed vocabulary before import'}
    if author != 'owner_created':return None  # Not the owner-card refresh exception to ordinary V1 imports.
    key = identity(fm)
    if not all(key):return None
    candidates = [notes.load(p) for p in notes.iter_paths(vault.root)]
    matches = [n for n in candidates if n.frontmatter.get('type') == 'source'
               and n.frontmatter.get('kind') == 'model' and identity(n.frontmatter) == key]
    if len(matches) > 1:
        return {**row, 'action': 'left out', 'why': 'Ambiguous model identity; a person must choose the target',
                'candidates': [str(n.path.relative_to(vault.root)) for n in matches]}
    if not matches:return None
    source = v1_root / row['v1_path']; refuse_credentials(source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = matches[0]; relative = target.path.relative_to(vault.root).as_posix()
    details = dict(model_card_sha256=digest, revision_of=relative,
                   model_target_sha256=hashlib.sha256(target.path.read_bytes()).hexdigest())
    from .staging import StagingStore
    pending = [i for i in StagingStore(vault).items('source')
        if i.get('revision_kind') == 'model_card' and i.get('revision_of') == relative
        and i.get('fields', {}).get('owner_card_sha256') == digest
        and i.get('status') in {'staged', 'deferred', 'approved', 'processing', 'enriched', 'partial'}]
    if pending:return {**row, **details, 'action': 'already staged'}
    if target.frontmatter.get('owner_card_sha256') == digest:
        return {**row, **details, 'action': 'already held'}
    return {**row, **details, 'action': 'stage', 'why': 'Changed owner model metadata needs person review'}


def import_fields(fields, sections, digest):
    fields = dict(fields)
    author = card_authorship(fields)
    if author is None:raise TypeError('MODEL_CARD_AUTHORSHIP_UNCLASSIFIED')
    if fields.get('provider'):fields['provider'] = identity(fields)[0]
    fields.update(authorship=author, **({'owner_card_sha256': digest} if author == 'owner_created' else {'imported_card_sha256': digest}))
    fields['field_authorship'] = {name: author for name in fields if name != 'field_authorship'}
    fields['section_authorship'] = {name: author if name.casefold() in OWNER_SECTIONS else 'third_party'
                                   for name in sections}
    return fields


def compose_refresh(store, item, note, raw):
    from .v1_export import _bound_root
    source_root = _bound_root(store.vault)
    rel = item.get('imported_from', {}).get('path', '')
    source = (source_root / rel).resolve() if source_root else None
    if source is None or not source.is_relative_to(source_root.resolve()):
        raise Refusal('DOCUMENT_ACTIVE', 'STALE model-card import binding; stage it again')
    refuse_credentials(source)
    if (hashlib.sha256(raw).hexdigest() != item.get('model_target_sha256')
            or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != item.get('fields', {}).get('owner_card_sha256')):
        raise Refusal('DOCUMENT_ACTIVE', 'STALE model card or target changed after staging; stage it again')
    incoming = item['fields']
    if identity(incoming) != identity(note.frontmatter):raise TypeError('MODEL_CARD_IDENTITY_MISMATCH')
    key = identity(incoming)
    merged = merge_profiles({key: note.frontmatter}, {key: incoming})[key]
    authors = merged.pop('_field_authorship'); merged.pop('_field_sources', None)
    merged['field_authorship'] = authors
    section_authors = {h: note.frontmatter.get('section_authorship', {}).get(h, note.frontmatter.get('authorship', 'generated'))
                       for h in note.sections()}
    section_authors.update(incoming.get('section_authorship', {}))
    merged['section_authorship'] = section_authors
    body = note.body; previous = {}
    for heading, text in (item.get('sections') or {}).items():
        previous[heading] = note.sections().get(heading, '')
        author = section_authors.get(heading, 'third_party')
        body = notes.with_section(body, heading, f'*Authorship: {author}.*\n\n{text}')
    return merged, body, previous
