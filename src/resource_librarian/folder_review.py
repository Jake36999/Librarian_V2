"""Folder decisions in the existing staging airlock; source trees are never written."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from . import content_roots, deploy_survey
from .coordination import atomic_write_text
from .credentials import credential_path, generated_path
from .staging import StagingStore
from .vault import now_iso

PURPOSES = ('own-current', 'own-legacy', 'own-docs', 'research-docs', 'third-party',
            'data', 'logs/transcripts', 'exclude')
READ_ONLY = {'research-docs', 'third-party', 'data'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def configuration(vault):
    path = vault.librarian / 'geographer.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'enabled': False}


def inventory(found):
    return dict(version='folder-inventory-v1', root=found.canonical_root,
                fingerprint=found.fingerprint, entries=found.entries, partial=found.partial,
                unreadable=found.unreadable, credential_refusals=found.credential_refusals)


def cli(config, operation, payload):
    command = config.get('command')
    if (not config.get('enabled') or not isinstance(command, list) or not command
            or not all(isinstance(s, str) and s for s in command)
            or config.get('wheel_version') != '0.2.0'):
        raise ValueError('GEOGRAPHER_CONFIGURATION: enable a pinned 0.2.0 installed-wheel command')
    done = subprocess.run([*command, *operation], input=json.dumps(payload).encode('utf-8'),
                          capture_output=True, timeout=120)
    if done.returncode:
        # Do not reflect raw subprocess output (it may contain source data) into the UI.
        raise ValueError('GEOGRAPHER_CALL_FAILED: inspect the local diagnostic log')
    result = json.loads(done.stdout)
    if result.get('geographer_version') != config['wheel_version']:
        raise ValueError('GEOGRAPHER_VERSION_MISMATCH: install the pinned wheel')
    return result


class FolderReview:
    def __init__(self, vault, *, planner=None, applier=None):
        self.vault = vault; self.store = StagingStore(vault)
        self.config = configuration(vault); self.planner = planner; self.applier = applier

    def list(self):
        folder = self.store.folder('folder')
        rows = [self.store.load(path.stem) for path in sorted(folder.glob('*.json'))] if folder.is_dir() else []
        from .access import PURPOSE_AUTHORSHIP
        for card in rows:
            decision = card.get('pending_decision') or card.get('decision') or {}
            authorship = decision.get('authorship') or PURPOSE_AUTHORSHIP.get(decision.get('purpose'))
            card.update(authorship=authorship, authorship_resolution='declared' if authorship else
                        'excluded' if decision.get('purpose') == 'exclude' else 'unclassified')
            card['description'].setdefault('authorship', 'generated')
            from . import provenance
            claims = provenance.check_sections(self.vault, {'Description': card['description']['text']},
                {'evidence': [e['id'] for e in card.get('evidence', [])]})
            if any(r['outcome'] == 'contradicted' for r in claims):
                card['description'] = dict(state='provenance_refused', text='', draft=True,
                    authorship='generated', provenance=claims)
        return rows

    def overview(self):
        path = self.vault.librarian / 'folder-surveys.json'
        surveys = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        paths = sorted({name for report in surveys.values() for name in report['credential_refusals']['paths']})
        return dict(authorship='generated', enabled=self.config.get('enabled', False),
                    drafting_available=False, cards=self.list(), purposes=PURPOSES,
                    credential_refusals=dict(count=len(paths), paths=paths))

    def survey(self, root, *, surveyed=None):
        from . import intake
        result = intake.ingest(self.vault, None, 'folder:' + str(root), endpoint=None,
                               _folder_review=self, _surveyed=surveyed)
        if result.status == 'quarantined':
            raise ValueError(result.detail)
        return result.detail

    def _stage_inventory(self, found, record):
        from . import folder_intake
        plan = self.planner(found) if self.planner else (getattr(found, 'geo_grapher', {}) or {}).get('plan') or cli(self.config,
            ['init-workspace', '--root', found.canonical_root, '--catalog',
             str(self.vault.librarian / 'geographer/catalog.sqlite'), '--survey-in', '-'], inventory(found))
        if plan.get('shared_survey_fingerprint') != found.fingerprint:
            raise ValueError('SHARED_SURVEY_MISMATCH: both consumers must use the same survey')
        path = self.vault.librarian / 'folder-surveys.json'
        surveys = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        surveys[found.canonical_root] = dict(fingerprint=found.fingerprint,
            inventory_evidence=record.id, credential_refusals=found.credential_refusals)
        atomic_write_text(path, json.dumps(surveys, indent=1))
        root = Path(found.canonical_root); existing = {c['id']: c for c in self.list()}; cards = []
        proposals = [*plan['partitions'], *[dict(key='exclude:' + e['rel'], subtrees=[e['rel']],
            file_counts={}, bytes=0, suggestion=dict(purpose='exclude', reasons=[e['reason']]))
            for e in plan.get('excluded', []) if not credential_path(e['rel'])]]
        proposed = {(p.get('subtrees') or ['.'])[0] or '.' for p in proposals}
        for name, size, _ in found.entries:
            rel = name.rstrip('/')
            if not name.endswith('/') or size < 0 or rel in proposed or credential_path(rel): continue
            parents = [p for p in proposals if any(rel.startswith(s + '/') for s in p.get('subtrees', []))]
            inherited = max(parents, key=lambda p: len(p['subtrees'][0]), default=None)
            children = [r for r in folder_intake.eligible(found.entries)
                        if r[0].startswith(rel + '/') and r[1] >= 0 and not r[0].endswith('/')]
            counts = {}
            for child in children:
                suffix = Path(child[0]).suffix.lower() or '(no extension)'
                counts[suffix] = counts.get(suffix, 0) + 1
            proposals.append(dict(key=rel, subtrees=[rel], file_counts=counts, bytes=sum(r[1] for r in children),
                suggestion=dict(purpose=inherited['suggestion']['purpose'] if inherited else 'own-current',
                                reasons=['inherited folder suggestion; a person may override it'])))
        for part in proposals:
            rel = (part.get('subtrees') or ['.'])[0] or '.'
            if credential_path(rel) or generated_path(rel): continue
            selected = [r for r in found.entries if rel == '.' or r[0].rstrip('/') == rel or r[0].startswith(rel + '/')]
            fp = digest(selected); item_id = 'folder-' + digest([str(root), rel])[:24]
            old = existing.get(item_id)
            if old and old['folder_fingerprint'] == fp:
                old['survey_fingerprint'] = found.fingerprint
                folder_intake.prepare_card(self.vault, old, selected, old)
                self.store.save(old); cards.append(old); continue
            purpose = part['suggestion']['purpose']
            graph = self.vault.root.name + ('-third-party' if purpose in {'third-party', 'research-docs'}
                                           else '-' + (root.name if rel == '.' else rel.replace('/', '-')))
            card = dict(id=item_id, kind='folder', status='staged', name=rel, path=rel,
                source_root=str(root), folder_fingerprint=fp, survey_fingerprint=found.fingerprint,
                file_counts=part['file_counts'], bytes=part['bytes'], suggested_purpose=purpose,
                suggested_graph=graph, reasons=part['suggestion']['reasons'], partition=part,
                authorship=None, authorship_resolution='unclassified',
                description=dict(state='awaiting_model_draft', text='', draft=True, authorship='generated'),
                previous_decision=old.get('decision') if old else None)
            folder_intake.prepare_card(self.vault, card, selected, old)
            self.store.add(card); cards.append(card)
        # A vanished folder must not leave an accepted, invisible stale decision.
        live = {c['id'] for c in cards}
        for old in existing.values():
            if old['source_root'] == str(root) and old['id'] not in live:
                old.update(status='deferred', stale_reason='folder no longer present'); self.store.save(old)
        return dict(enabled=True, cards=cards, duplicates=folder_intake.duplicates(cards),
                    survey_fingerprint=found.fingerprint,
                    credential_refusals=found.credential_refusals)

    def approve_batch(self, item_ids, *, person=False):
        """Queue one bounded exact set; the existing batch processes, not accepts."""
        if not person:
            raise ValueError('PERSON_CONFIRMS: a person starts folder processing')
        if not isinstance(item_ids, list) or not 1 <= len(item_ids) <= 100 or len(set(item_ids)) != len(item_ids):
            raise ValueError('FOLDER_BATCH: choose 1-100 distinct cards')
        cards = [self.store.load(key) for key in item_ids]
        for card in cards:
            if card['kind'] != 'folder' or card['status'] not in {'staged', 'deferred', 'partial', 'failed'}:
                raise ValueError('FOLDER_BATCH: only waiting folder cards can be approved')
            if (card.get('sensitivity') or {}).get('sensitivity') == 'review_required':
                raise ValueError('SENSITIVITY_REVIEW: review this card individually as a person')
            if card.get('suggested_purpose') not in {'own-current', 'own-legacy', 'own-docs',
                                                    'research-docs', 'third-party', 'exclude'}:
                raise ValueError('FOLDER_BATCH: ambiguous classification needs individual review')
            self.validate(card)
        for card in cards:
            card.update(status='approved')
            self.store.save(card)
        return dict(approved=item_ids, next='Start process_approved; acceptance remains separate')

    def validate(self, card):
        from .folder_intake import validate_card
        found = deploy_survey.survey(card['source_root'], geographer={'enabled': False})
        rel = card['path']
        rows = [r for r in found.entries if rel == '.' or r[0].rstrip('/') == rel or r[0].startswith(rel + '/')]
        if found.partial or found.unreadable or found.stops or digest(rows) != card['folder_fingerprint']:
            raise ValueError('FOLDER_STALE: survey and review this card again')
        validate_card(self.vault, card, rows)

    def draft(self, item_id, endpoint, *, approved=False, persist=True):
        if not approved: raise ValueError('SPEND_APPROVAL_REQUIRED')
        if endpoint is None: raise ValueError('CLERK_UNAVAILABLE')
        from . import clerk
        if not isinstance(endpoint, clerk.Scripted):
            raise ValueError('FOLDER_DRAFT_DISABLED: owner approval of a qualified Clerk route is required')
        card = self.store.load(item_id)
        # Only metadata reaches the Clerk, including for third-party folders. No graph/source bodies.
        payload = dict(path=card['path'], file_counts=card['file_counts'], bytes=card['bytes'])
        kind = clerk.Kind('folder_brief', 'describe folder inventory metadata without inferring source behaviour',
            {'type': 'object', 'required': ['description'], 'properties': {
                'description': {'type': 'string', 'maxLength': 400}}}, max_tokens=320)
        results = clerk.run([clerk.Task(kind, json.dumps(payload), 'Describe this inventory in one sentence.'),
                             clerk.sensitivity(json.dumps(payload))], endpoint)
        result = results[0]
        if not result.ok: raise ValueError('FOLDER_DRAFT_FAILED')
        from . import provenance
        claims = provenance.check_sections(self.vault, {'Description': result.value['description']},
            {'evidence': [e['id'] for e in card.get('evidence', [])]})
        if any(r['outcome'] == 'contradicted' for r in claims):
            raise ValueError('FOLDER_PROVENANCE: description contradicts its inventory')
        if len(results) < 2 or not results[1].ok:
            raise ValueError('FOLDER_SENSITIVITY: review is incomplete')
        card['sensitivity'] = results[1].value
        card['description'] = dict(state='model_draft', text=result.value['description'], draft=True,
                                   authorship='generated', provenance=claims)
        if persist:
            self.store.save(card)
        return card

    def accept(self, item_id, fingerprint, *, purpose, graph, person=False, description=None, authorship=None):
        if not person: raise ValueError('PERSON_CONFIRMS: only the folder review UI can accept a folder')
        if purpose not in PURPOSES: raise ValueError('FOLDER_PURPOSE: choose a listed purpose')
        from .access import AUTHORSHIP, PURPOSE_AUTHORSHIP
        derived = PURPOSE_AUTHORSHIP.get(purpose)
        if purpose == 'exclude':
            authorship = None
        elif derived:
            if authorship is not None and authorship != derived:
                raise ValueError('FOLDER_AUTHORSHIP: this purpose determines its authorship')
            authorship = derived
        elif authorship not in AUTHORSHIP:
            raise ValueError('FOLDER_AUTHORSHIP: data and logs/transcripts require an explicit authorship choice')
        if purpose != 'exclude' and (not isinstance(graph, str) or not graph.strip() or len(graph) > 120):
            raise ValueError('FOLDER_GRAPH: choose a graph label')
        card = self.store.load(item_id)
        if card['kind'] != 'folder' or fingerprint != card['folder_fingerprint']:
            raise ValueError('FOLDER_STALE: review this card again')
        found = deploy_survey.survey(card['source_root'], geographer={'enabled': False})
        rel = card['path']; rows = [r for r in found.entries if rel == '.' or r[0].rstrip('/') == rel or r[0].startswith(rel + '/')]
        if found.partial or found.unreadable or digest(rows) != fingerprint:
            raise ValueError('FOLDER_STALE: the folder changed; survey again')
        from .folder_intake import validate_card
        validate_card(self.vault, card, rows)
        description = description if description is not None else card['description']['text']
        if description is not None:
            from . import provenance
            if not isinstance(description, str) or len(description) > 400:
                raise ValueError('FOLDER_DESCRIPTION: limit the description to 400 characters')
            claims = provenance.check_sections(self.vault, {'Description': description},
                {'evidence': [e['id'] for e in card['evidence']]})
            if any(r['outcome'] == 'contradicted' for r in claims):
                raise ValueError('FOLDER_PROVENANCE: description contradicts its inventory')
        candidate = dict(card, decision=dict(purpose=purpose, authorship=authorship, graph=graph.strip(),
                         description=description if description is not None else card['description']['text'],
                         accepted_by='person', accepted_at=now_iso()), status='accepted')
        candidate.update(authorship=authorship, authorship_resolution='declared' if authorship else 'excluded')
        all_cards = [c for c in self.list() if c['id'] != item_id] + [candidate]
        selected = [c for c in all_cards if c['status'] == 'accepted' and c.get('decision')]
        surveys = {found.canonical_root: found}
        for member in selected:
            source_root = member['source_root']
            if source_root not in surveys:
                surveys[source_root] = deploy_survey.survey(source_root, geographer={'enabled': False})
            checked = surveys[source_root]; relative = member['path']
            entries = [r for r in checked.entries if relative == '.' or r[0].rstrip('/') == relative or r[0].startswith(relative + '/')]
            if checked.partial or checked.unreadable or checked.stops or digest(entries) != member['folder_fingerprint']:
                raise ValueError(f'FOLDER_STALE: accepted folder {relative} changed; survey again before applying any group')
            validate_card(self.vault, member, entries)
        # Persist the read barrier before ingestion; a failed graph build cannot enable writes.
        self._root_access(candidate)
        request = dict(library=str(self.vault.root), decisions=selected, inventory=inventory(found))
        card.update(status='processing', pending_decision=candidate['decision']); self.store.save(card)
        try:
            result = ((self.applier(request) if self.applier else cli(self.config,
                ['apply-folder-review', '--catalog', str(self.vault.librarian / 'geographer/catalog.sqlite')], request))
                if purpose != 'exclude' or card.get('application') or any(c['decision']['purpose'] != 'exclude' for c in selected) else {})
        except Exception:
            card.update(status='failed', failure='graph application failed; read-only barrier retained')
            self.store.save(card); raise
        candidate['application'] = result; candidate.pop('pending_decision', None)
        from .folder_intake import accepted_record
        accepted_record(self.vault, candidate)
        self._root_access(candidate)
        self.store.save(candidate); return candidate

    def _root_access(self, card):
        root = Path(card['source_root']); target = root if card['path'] == '.' else root / card['path']
        attached = not target.resolve().is_relative_to(self.vault.root.resolve())
        purpose = card['decision']['purpose']
        access = 'read_only' if attached or purpose in READ_ONLY or card['decision'].get('authorship') == 'third_party' else 'read_write'
        data = content_roots.load(self.vault.root) or dict(version=1, mode='create',
            roots=[dict(path='.', access='read_write')], excludes=[])
        path = str(target) if attached else target.relative_to(self.vault.root).as_posix()
        data['roots'] = [r for r in data['roots'] if r['path'] != path]
        if purpose != 'exclude':
            data['roots'].append(dict(path=path, access=access, attached=attached,
                purpose=purpose, authorship=card['decision']['authorship'],
                folder_decision=card['id'], survey_fingerprint=card['survey_fingerprint'],
                description=card['decision'].get('description', ''), graph_label=card['decision']['graph'],
                evidence=[e['id'] for e in card.get('evidence', [])] +
                         ([card['accepted_evidence']] if card.get('accepted_evidence') else [])))
        else:
            data['excludes'] = sorted(set(data.get('excludes', [])) | {path})
        content_roots._write_json(content_roots.manifest_path(self.vault.root), data)


def decision_for(vault, path):
    """Deepest accepted folder decision wins. Stale/failed read barriers stay conservative."""
    path = Path(path).resolve(); candidates = []
    for card in FolderReview(vault).list():
        decision = card.get('pending_decision') or card.get('decision')
        if not decision: continue
        root = Path(card['source_root']); root = root if card['path'] == '.' else root / card['path']
        if path.is_relative_to(root.resolve()): candidates.append((len(root.parts), decision))
    return max(candidates, key=lambda c: c[0])[1] if candidates else None


def refuse_write(vault, path):
    from .rules import Refusal
    decision = decision_for(vault, path)
    if decision and (decision['purpose'] in READ_ONLY | {'exclude'} or decision.get('authorship') == 'third_party'):
        raise Refusal('FOLDER_READ_ONLY', f'{path}: accepted folder is read-only or excluded')
    manifest = content_roots.load(vault.root) or {}
    matches = []
    for root in manifest.get('roots', []):
        folder = Path(root['path']); folder = folder if folder.is_absolute() else vault.root / folder
        if Path(path).resolve().is_relative_to(folder.resolve()): matches.append((len(folder.parts), root))
    if matches and max(matches, key=lambda item:item[0])[1].get('access') == 'read_only':
        raise Refusal('FOLDER_READ_ONLY', f'{path}: attached or read-only content root')
