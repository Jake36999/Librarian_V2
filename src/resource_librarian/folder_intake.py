"""Folder-kind intake facts and DIK projections; never source-body extraction."""
from pathlib import Path

from . import dik, provenance
from .credentials import credential_path, generated_path
from .evidence import EvidenceStore


def eligible(entries):
    return [r for r in entries if not credential_path(r[0]) and not generated_path(r[0])]


def _record(vault, source, payload, previous=''):
    import json
    payload = json.loads(json.dumps(payload))
    store = EvidenceStore(vault)
    old = store.get(previous) if previous else None
    if old and not store.intact(old):
        raise ValueError('FOLDER_EVIDENCE_STALE: evidence integrity check failed')
    if old and old.kind == 'survey' and old.source == source and old.payload == payload:
        return old
    return store.put('survey', source, payload, authorship='generated')


def inventory_record(vault, found):
    import json
    path = vault.librarian / 'folder-surveys.json'
    prior = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
    rows = eligible(found.entries)
    payload = dict(scope='folder_inventory_metadata', root=found.canonical_root,
        fingerprint=found.fingerprint, entries=rows,
        files=sum(r[1] >= 0 and not r[0].endswith('/') for r in rows),
        content_status='not examined', partial=False)
    record = _record(vault, found.canonical_root, payload,
                     prior.get(found.canonical_root, {}).get('inventory_evidence', ''))
    dik.save(vault, dict(source='folder-inventory-' + record.id, authorship='generated',
        evidence=[record.id], data=[dict(id='inventory', kind='folder',
            locator=found.canonical_root, source=found.canonical_root, revision=record.id,
            evidence=record.id, method='native folder survey; metadata only', origin='observed',
            status='not examined', metadata_observed=True)], information=[]))
    return record


def prepare_card(vault, card, selected, previous=None):
    rows = eligible(selected)
    files = [r for r in rows if r[1] >= 0 and not r[0].endswith('/')]
    old = (previous or {}).get('evidence') or []
    record = _record(vault, str(Path(card['source_root']) / card['path']),
        dict(scope='folder_inventory_metadata', entries=rows, files=len(files),
             bytes=sum(r[1] for r in files), content_status='not examined', partial=False),
        old[0]['id'] if old else '')
    card.update(evidence=[dict(id=record.id, kind='survey')], inventory_evidence=record.id,
        intake=dict(kind='folder', stages=['capture', 'evidence', 'facts', 'describe', 'stage'],
                    description='awaiting approved qualified Clerk; no model called'),
        sensitivity=card.get('sensitivity') or dict(sensitivity='not examined', reason='Clerk not run'))
    card['provenance'] = dict(checked=True, claims=provenance.check_sections(
        vault, {'Description': card['description']['text']}, {'evidence': [record.id]}),
        limitation='arithmetic only; source content not examined')
    card['inventory_metadata'] = [dict(path=r[0], bytes=r[1]) for r in files]
    card['file_counts'] = {}
    for row in files:
        suffix = Path(row[0]).suffix.lower() or '(no extension)'
        card['file_counts'][suffix] = card['file_counts'].get(suffix, 0) + 1
    card['bytes'] = sum(r[1] for r in files)
    save_dik(vault, card)
    return card


def save_dik(vault, card):
    ref = card['evidence'][0]['id']
    dik.save(vault, dict(source=card['id'], authorship=card.get('authorship'),
        evidence=[ref, *([card['accepted_evidence']] if card.get('accepted_evidence') else [])],
        data=[dict(id='folder:' + card['id'], kind='folder', name=card['path'],
            locator=card['source_root'] + '/' + card['path'], revision=ref, evidence=ref,
            method='native inventory; no source bodies read', origin='observed',
            status='not examined', metadata_observed=True)], information=[]))


def accepted_record(vault, card):
    record = EvidenceStore(vault).put('access_check', card['id'],
        dict(authorship_classification=card['decision']['authorship'],
             graph_label=card['decision']['graph'], accepted_by='person',
             inventory_evidence=card['evidence'][0]['id'], content_status='not examined'),
        authorship='owner_created')
    card['accepted_evidence'] = record.id
    save_dik(vault, card)


def validate_card(vault, card, selected):
    import json
    refs = card.get('evidence') or []
    store = EvidenceStore(vault)
    record = store.get(refs[0].get('id', '')) if refs else None
    if (record is None or not store.intact(record) or record.kind != 'survey'
            or record.id != card.get('inventory_evidence')
            or record.payload.get('entries') != json.loads(json.dumps(eligible(selected)))):
        raise ValueError('FOLDER_EVIDENCE_STALE: inventory evidence changed; survey and review again')


def duplicates(cards):
    import json
    from .document_identity import folder_inventory_duplicates
    inventories = []
    for card in cards:
        prefix = '' if card['path'] == '.' else card['path'].rstrip('/') + '/'
        rows = [dict(path=r['path'].removeprefix(prefix), bytes=r['bytes'])
                for r in card.get('inventory_metadata', [])]
        # Empty folders provide no evidence that two sources are duplicates.
        if rows:
            inventories.append((card['id'], json.dumps(rows, sort_keys=True).encode('utf-8')))
    return folder_inventory_duplicates(inventories)
