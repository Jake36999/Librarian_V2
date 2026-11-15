"""Free catalogue projections; recorded use is history, never proof of truth."""
from __future__ import annotations

import re
import json
from pathlib import Path

from . import dik, notes
from .session import SessionStore


def _name(value):
    return re.sub(r'^\[\[|\]\]$', '', str(value)).split('|', 1)[0].casefold()


def all_use_rollups(vault, *, application_rows=None):
    uses, applications, limitations = {}, {}, []
    store = SessionStore(vault)
    for path in sorted(store.folder.glob('*.jsonl')):
        try:
            for event in store.events(path.stem):
                if event.get('type') == 'use' and event.get('source'):
                    uses.setdefault(_name(event['source']), []).append({'session': path.stem,
                        'used_for': str(event.get('used_for', ''))[:300], 'authorship': 'generated'})
        except (OSError, ValueError):
            limitations.append('Unreadable use history: ' + path.stem)
    if application_rows is None:
        application_rows = []
        for path in notes.iter_paths(vault.root):
            note = notes.load(path)
            if note.frontmatter.get('type') == 'application':
                application_rows.append({'name': note.name, 'path': path.relative_to(vault.root).as_posix(),
                                         'frontmatter': note.frontmatter})
    for row in application_rows:
        fm = row['frontmatter']
        fm = json.loads(fm) if isinstance(fm, str) else fm
        sources = fm.get('sources_used', [])
        for source in set(_name(s) for s in sources) if isinstance(sources, list) else []:
            applications.setdefault(source, []).append({'name': row['name'], 'path': row['path'],
                'outcome': str(fm.get('outcome', ''))[:200], 'authorship': fm.get('authorship'),
                'taint_sources': fm.get('taint_sources', [])[:8]})
    return {source: _rollup(uses.get(source, []), applications.get(source, []), limitations)
            for source in set(uses) | set(applications)}


def _rollup(uses=(), applications=(), limitations=()):
    return {'authorship': 'generated', 'basis': 'recorded log_use events and Application notes; not efficacy evidence',
            'log_use_count': len(uses), 'application_count': len(applications),
            'recent_uses': list(uses[-3:]), 'applications': list(applications[-3:]),
            'truncated': len(uses) > 3 or len(applications) > 3, 'limitations': list(limitations[:3])}


def use_rollup(vault, source, *, rollups=None):
    rows = all_use_rollups(vault) if rollups is None else rollups
    return rows.get(_name(source), _rollup())


def navigation(vault, note, *, chapter_limit=8):
    from .read_access import source_path
    from .registry import Context
    from .rules import Refusal
    original = {'available': False, 'reason': 'Original is missing or outside accepted source roots'}
    if note.frontmatter.get('file'):
        try:
            declared = Path(str(note.frontmatter['file']))
            declared = declared if declared.is_absolute() else vault.root / declared
            if not declared.is_file():
                raise FileNotFoundError('Original attachment is missing')
            path = source_path(Context(vault=vault), str(declared))
            original = {'available': True, 'path': str(path), 'name': path.name,
                        'download_source': note.name, 'representation': 'original'}
        except (OSError, TypeError, ValueError, Refusal):
            pass
    chapters = []
    record = dik.load(vault, note.name)
    all_chapters = [d for d in record.get('data', []) if d.get('kind') == 'chapter']
    for row in all_chapters[:chapter_limit]:
        claims = row.get('claims', []) if row.get('status') != 'not examined' else []
        text = [str(c.get('text', c.get('claim', ''))) if isinstance(c, dict) else str(c) for c in claims]
        chapters.append({'title': str(row.get('name', ''))[:200], 'locator': row.get('locator'),
            'status': row.get('status'), 'coverage': row.get('coverage'),
            'summary': [t[:240] for t in text[:2] if t],
            'summary_truncated': len(text)>2 or any(len(t)>240 for t in text[:2]), 'authorship': 'generated',
            'basis': 'deep_read chapter claims; source-stated, not independently verified'})
    sections = {h.casefold(): t for h, t in note.sections().items()}
    relevance = note.frontmatter.get('when_relevant') or sections.get("when it's relevant") or sections.get('when to use') or ''
    return {'authorship': 'generated', 'when_relevant': str(relevance)[:600],
            'relevance_status': 'recorded' if relevance else 'not recorded',
            'use_rollup': use_rollup(vault, note.name), 'chapters': chapters,
            'chapters_total': len(all_chapters), 'chapters_truncated': len(all_chapters) > len(chapters),
            'original': original}
