"""Persistent generated conversions, distinct from originals and rebuildable indexes."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from pathlib import Path
from types import SimpleNamespace

from .coordination import atomic_write_text, operation_path
from .credentials import refuse_credentials
from .evidence import EvidenceStore, is_record_id
from .rules import Refusal
from .vault import now_iso


def file_sha256(path):
    path = Path(path)
    refuse_credentials(path)
    refuse_credentials(path.resolve())
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class Request:
    original: Path
    original_sha256: str
    method: str
    cache_key: str
    captured_at: str
    source_authorship: str | None


class ConversionStore:
    def __init__(self, vault):
        self.vault = vault
        self.root = operation_path(vault, '.librarian/conversions')
        self.index_path = self.root / 'index.json'
        self.evidence = EvidenceStore(vault)

    def request(self, original, method):
        from .access import _native_authorship
        original = Path(original).resolve()
        sha = file_sha256(original)
        key = hashlib.sha256((sha + '\n' + method).encode()).hexdigest()
        return Request(original, sha, method, key, now_iso(),
                       _native_authorship(SimpleNamespace(vault=self.vault), str(original)))

    def _index(self):
        if not self.index_path.exists():
            return {'version': 1, 'items': {}, 'origins': {}}
        data = json.loads(self.index_path.read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('items'), dict) or not isinstance(data.get('origins'), dict):
            raise ValueError('Unsupported/corrupt conversion index; retain it and inspect')
        return data

    def _checked(self, entry):
        ident = entry.get('evidence_id')
        if not is_record_id(ident):
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Invalid conversion evidence identity')
        rel = '.librarian/conversions/' + ident + '.md'
        path = operation_path(self.vault, rel)
        record = self.evidence.get(ident)
        detail_keys = set(entry) - {'path', 'evidence_id', 'sha256', 'pages', 'method', 'original_sha256'}
        if (entry.get('path') != rel or not path.is_file() or not record or not self.evidence.intact(record)
                or record.authorship != 'generated' or file_sha256(path) != entry.get('sha256')
                or any(record.payload.get(k) != entry.get(k)
                       for k in ('sha256', 'original_sha256', 'method', 'pages'))):
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Conversion changed or is missing; original and first artifacts were retained')
        if ('conversion_details' in record.payload
                and {key: entry[key] for key in detail_keys} != record.payload['conversion_details']):
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Conversion coverage metadata changed')
        return path

    def checked_path(self, rel):
        entries = [entry for entry in self._index()['items'].values() if entry.get('path') == rel]
        if not entries:
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Unknown generated conversion')
        return self._checked(entries[0])

    def entry(self, rel):
        entries = [entry for entry in self._index()['items'].values() if entry.get('path') == rel]
        if not entries:
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Unknown generated conversion')
        self._checked(entries[0])
        return dict(entries[0])

    def page_units(self, rel):
        entry = self.entry(rel)
        content = self.checked_path(rel).read_text(encoding='utf-8')
        marks = list(re.finditer(r'^\[page ([1-9][0-9]*)\][ \t]*$', content, re.M))
        if ([int(m[1]) for m in marks] != list(range(1, entry['pages'] + 1))
                or not marks or content[:marks[0].start()].strip()):
            return []  # Never reinterpret Markdown's synthetic page 1 as PDF page 1.
        return [(int(mark[1]), content[mark.end():marks[i + 1].start() if i + 1 < len(marks) else len(content)].strip())
                for i, mark in enumerate(marks)]

    def _origin(self, request, index):
        key = hashlib.sha256((str(request.original) + '\n' + request.original_sha256 + '\n'
                              + str(request.source_authorship)).encode()).hexdigest()
        ident = index['origins'].get(key)
        record = self.evidence.get(ident) if ident else None
        if record and (not self.evidence.intact(record)
                       or record.source != str(request.original)
                       or record.payload.get('sha256') != request.original_sha256
                       or record.authorship != request.source_authorship):
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Original-source evidence changed')
        if not record:
            record = self.evidence.put('pdf_text', str(request.original),
                {'sha256': request.original_sha256, 'representation': 'original_file'},
                fetched_at=request.captured_at, authorship=request.source_authorship)
            index['origins'][key] = record.id
        return record

    def find(self, request):
        index = self._index()
        entry = index['items'].get(request.cache_key)
        if entry is None:
            return None
        self._checked(entry)
        if entry['original_sha256'] != request.original_sha256 or entry['method'] != request.method:
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Conversion does not belong to this original and method')
        origin = self._origin(request, index)
        self._save_index(index)
        return self._public(entry, origin, request, cached=True)

    def save(self, request, markdown, *, pages, **details):
        raw = str(markdown).encode('utf-8')
        sha = hashlib.sha256(raw).hexdigest()
        record = self.evidence.put('pdf_text', 'conversion:' + request.cache_key,
            {'sha256': sha, 'original_sha256': request.original_sha256,
             'method': request.method, 'pages': pages, 'representation': 'generated_conversion',
             'conversion_details': details},
            authorship='generated')
        rel = '.librarian/conversions/' + record.id + '.md'
        path = operation_path(self.vault, rel)
        if path.exists() and file_sha256(path) != sha:
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Content-addressed conversion must never be overwritten')
        if not path.exists():
            atomic_write_text(path, str(markdown))
        entry = dict(path=rel, evidence_id=record.id, sha256=sha, pages=pages,
                     method=request.method, original_sha256=request.original_sha256, **details)
        index = self._index()
        origin = self._origin(request, index)
        index['items'][request.cache_key] = entry
        self._save_index(index)
        self._checked(entry)
        return self._public(entry, origin, request, cached=False)

    def _save_index(self, index):
        atomic_write_text(self.index_path, json.dumps(index, indent=2, ensure_ascii=False))

    def _public(self, entry, origin, request, *, cached):
        available = (request.original.is_file() and request.original.resolve() == request.original
                     and file_sha256(request.original) == request.original_sha256)
        return {**entry, 'authorship': 'generated', 'source_authorship': request.source_authorship,
                'original_evidence_id': origin.id, 'original_path': str(request.original),
                'original_available': available, 'original_changed': not available,
                'cached': cached, 'primary_source': False}


def is_conversion(vault, rel):
    try:
        path = operation_path(vault, str(rel))
        root = operation_path(vault, '.librarian/conversions')
        return path.parent == root and path.suffix == '.md' and is_record_id(path.stem)
    except (ValueError, TypeError, Refusal):
        return False


def migrate_confirmed(vault, original, conversion, *, apply=False):
    """Operator migration of a recorded conversion, never a basename heuristic.

    Retain both old files: the durable manifest explains the hidden replacement.
    Legacy conversions have no proven page mapping; S3 must report that omission.
    """
    from .staging import _attachment_path
    source = _attachment_path(vault, original)
    old = _attachment_path(vault, conversion)
    if source.suffix.lower() != '.pdf' or old.suffix.lower() != '.md' or source == old:
        raise TypeError('A confirmed migration requires an original PDF and its recorded Markdown conversion')
    sha = file_sha256(old)
    row = {'old_path': str(conversion), 'original_path': str(original),
           'original_sha256': file_sha256(source), 'sha256': sha,
           'original_retained': True, 'legacy_retained': True,
           'page_mapping': 'unverified', 'dry_run': not apply}
    if not apply:
        return row
    store = ConversionStore(vault)
    request = store.request(source, 'legacy-confirmed:v1:' + sha)
    result = store.find(request)
    if result is None:
        result = store.save(request, old.read_bytes().decode('utf-8'), pages=0,
                            page_mapping='unverified', migrated_from=str(conversion))
    # Preserve the exact byte representation, including legacy line endings.
    if file_sha256(vault.root / result['path']) != sha:
        raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'Legacy conversion encoding differs; retain it for manual review')
    row.update(path=result['path'], evidence_id=result['evidence_id'])
    manifest = store.root / 'migrations.json'
    rows = json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
    if row not in rows:
        atomic_write_text(manifest, json.dumps([*rows, row], indent=2, ensure_ascii=False))
    return {**result, **row}


def survey_legacy(vault):
    """Find explicit catalogue/staging links, never infer authorship by adjacency."""
    from . import notes
    from .staging import _attachment_path
    rows = []
    candidates = [(p, 'note') for p in (vault.root / 'Sources').rglob('*.md')]
    candidates += [(p, 'staging') for p in (vault.librarian / 'staging/source').glob('*.json')]
    for path, kind in sorted(candidates):
        refuse_credentials(path)
        rel = path.relative_to(vault.root).as_posix()
        if kind == 'note':
            path = vault.safe_relative(rel)
        else:
            path = operation_path(vault, rel)
        raw = path.read_bytes()
        value = notes.parse(raw.decode('utf-8'))[0] if kind == 'note' else json.loads(raw)
        key = 'file_markdown' if kind == 'note' else 'clean_file'
        old, original = value.get(key), value.get('file')
        if not old or not original or is_conversion(vault, old):
            continue
        if Path(original).suffix.lower() != '.pdf' or Path(old).suffix.lower() != '.md':
            continue
        source, clean = _attachment_path(vault, original), _attachment_path(vault, old)
        rows.append({'reference': rel, 'reference_kind': kind, 'key': key,
                     'reference_sha256': hashlib.sha256(raw).hexdigest(),
                     'original': original, 'conversion': old,
                     'available': source.is_file() and clean.is_file(),
                     'original_sha256': file_sha256(source) if source.is_file() else None,
                     'sha256': file_sha256(clean) if clean.is_file() else None})
    return rows


def migrate_inventory(vault, *, apply=False):
    """Free operator-only survey/apply. No external roots are walked or changed."""
    from . import notes
    rows = survey_legacy(vault)
    results = []
    for row in rows:
        if not apply or not row['available']:
            results.append(row)
            continue
        reference = operation_path(vault, row['reference'])
        if file_sha256(reference) != row['reference_sha256']:
            raise Refusal('DOCUMENT_ACTIVE', 'Conversion reference changed; survey again')
        from .staging import _attachment_path
        if (file_sha256(_attachment_path(vault, row['original'])) != row['original_sha256']
                or file_sha256(_attachment_path(vault, row['conversion'])) != row['sha256']):
            raise Refusal('DOCUMENT_ACTIVE', 'Conversion or original changed; survey again')
        migrated = migrate_confirmed(vault, row['original'], row['conversion'], apply=True)
        if row['reference_kind'] == 'note':
            fm, body, error = notes.parse(reference.read_text(encoding='utf-8'))
            if error:
                raise ValueError(error)
            fm[row['key']] = migrated['path']
            rendered = notes.render(fm, body)
        else:
            value = json.loads(reference.read_text(encoding='utf-8'))
            value[row['key']] = migrated['path']
            rendered = json.dumps(value, indent=2, ensure_ascii=False)
        atomic_write_text(reference, rendered)
        results.append({**row, 'path': migrated['path'], 'applied': True})
    return {'dry_run': not apply, 'results': results}
