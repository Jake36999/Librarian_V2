"""Read-only index inputs from accepted roots; original bytes stay in place."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from . import content_roots, notes, text
from .coordination import atomic_write_text, operation_path
from .credentials import credential_path, generated_path
from .deploy_survey import EXCLUDE_NAMES, is_link

PLAIN = {'.md', '.markdown', '.txt', '.rst', '.py', '.pyi', '.js', '.jsx', '.ts', '.tsx',
         '.css', '.scss', '.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.sql',
         '.rs', '.c', '.h', '.cpp', '.hpp', '.sh', '.ps1', '.go', '.java', '.rb'}
SUPPORTED = PLAIN | set(text.SUPPORTED)


def roots(vault):
    out = []
    for row in (content_roots.load(vault.root) or {}).get('roots', []):
        base = Path(row['path']); base = base if base.is_absolute() else vault.root / base
        out.append({**row, 'base': base.resolve()})
    return out


def classification(vault, path, *, declared=None):
    path = Path(path).resolve()
    matches = [r for r in (roots(vault) if declared is None else declared) if path.is_relative_to(r['base'])]
    return max(matches, key=lambda r: len(r['base'].parts)) if matches else None


def key(vault, path):
    path = Path(path)
    return path.relative_to(vault.root).as_posix() if path.is_relative_to(vault.root) else path.resolve().as_posix()


def is_projection(vault, path):
    return Path(path).resolve().is_relative_to((vault.derived / 'folder-catalogue').resolve())


def _catalogue(vault, row):
    base = row['base']; digest = hashlib.sha256(str(base).encode()).hexdigest()[:16]
    path = operation_path(vault, '.librarian/derived/folder-catalogue/' + digest + '.md')
    fm = dict(type='source', kind='document', catalogue_of='folder', title=base.name, authorship='generated',
        original_authorship=row.get('authorship'), root=str(base), catalogue_only=True,
        _index_read_only=True, status='active', survey_fingerprint=row.get('survey_fingerprint'),
        folder_decision=row.get('folder_decision'), graph_label=row.get('graph_label'),
        evidence=row.get('evidence', []))
    body = (f'# Attached folder - {base.name} - {digest}\n\n## Description\n'
        f"Accepted purpose: {row.get('purpose') or 'not recorded'}. "
        f"Original authorship: {row.get('authorship') or 'unclassified'}.\n\n"
        'This is folder metadata, not source text or evidence of examination.\n\n'
        f"{row.get('description') or 'Description not recorded.'}\n\n"
        f"## Graph\n{row.get('graph_label') or 'Graph not recorded.'}\n\n"
        f'## Original folder\n{base}\n')
    rendered = notes.render(fm, body)
    if not path.is_file() or path.read_text(encoding='utf-8') != rendered:
        atomic_write_text(path, rendered)
    return path


def index_paths(vault):
    declared = roots(vault)
    paths = set()
    for path in notes.iter_paths(vault.root):
        choice = classification(vault, path, declared=declared)
        if not choice or choice.get('authorship') != 'third_party':paths.add(path)
    excludes = (content_roots.load(vault.root) or {}).get('excludes', [])
    for row in declared:
        base = row['base']
        if not row.get('attached') and row.get('access') != 'read_only':continue
        if row.get('purpose') == 'exclude' or not base.is_dir() or is_link(base):continue
        paths.add(_catalogue(vault, row))
        if row.get('authorship') != 'owner_created':continue
        for here, directories, files in os.walk(base):
            parent = Path(here)
            def allowed(path):
                rel = path.relative_to(base).as_posix()
                choice = classification(vault, path, declared=declared)
                return (choice is not None and choice.get('authorship') == 'owner_created'
                    and choice.get('purpose') != 'exclude' and not is_link(path)
                    and not any(p.startswith('.') or p in EXCLUDE_NAMES or p == 'graphify-out' for p in path.relative_to(base).parts)
                    and not credential_path(rel) and not generated_path(rel)
                    and not any(rel == e or rel.startswith(str(e).rstrip('/') + '/') or str(path) == e for e in excludes))
            directories[:] = [d for d in directories if allowed(parent / d)]
            for filename in files:
                path = parent / filename
                if path.suffix.lower() in SUPPORTED and allowed(path):paths.add(path)
    return sorted(paths)


def document(vault, path, snapshot):
    """Return an index representation; recheck accepted authorship before reading."""
    path = Path(path); row = classification(vault, path)
    if (row is None or row.get('authorship') != 'owner_created' or row.get('purpose') == 'exclude'
            or credential_path(path) or generated_path(path) or is_link(path)):
        raise ValueError('Workspace document is outside an accepted owner-created root')
    extraction_error = ''
    if path.suffix.lower() in PLAIN:
        value = snapshot.data.decode('utf-8', errors='replace').replace('\r\n','\n').replace('\r','\n')
    else:
        extracted = text.extract(path, vault.derived / 'text')
        extraction_error = extracted.error
        if not extraction_error and not any(page.strip() for page in extracted.pages):
            extraction_error = 'No extractable text; original pages were not OCRed'
        value = '' if extraction_error else '\n\n'.join(f'[page {n}]\n{page}' for n, page in enumerate(extracted.pages, 1))
        from .file_access import read_bytes_snapshot, FileChangedError
        if read_bytes_snapshot(path).data != snapshot.data:raise FileChangedError('Source changed during extraction')
    fm, body, error = notes.parse(value)
    digest = hashlib.sha256(str(row['base']).encode()).hexdigest()[:8]
    name = f"workspace:{row['base'].name}-{digest}/{path.relative_to(row['base']).as_posix()}"
    fm.update(authorship='owner_created', _index_read_only=True, _workspace_source=str(path),
              source_sha256=hashlib.sha256(snapshot.data).hexdigest())
    return name, fm, body, error or extraction_error
