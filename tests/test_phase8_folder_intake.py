import json
from pathlib import Path

import pytest

from test_folder_review import library, fake_planner


def test_folder_capture_does_not_grant_external_read(library):
    from resource_librarian import intake
    vault, source = library
    assert intake.capture('folder:' + str(source)).kind == 'folder'
    result = intake.ingest(vault, None, 'folder:' + str(source), endpoint=None)
    assert result.status == 'quarantined'
    assert 'PERSON_FOLDER_ADAPTER' in result.detail


def test_survey_is_native_intake_with_evidence_dik_and_stable_ids(library, monkeypatch):
    from resource_librarian import intake, dik
    from resource_librarian.evidence import EvidenceStore
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    called = []
    original = intake.ingest
    def wrapped(*args, **kwargs):
        called.append(args[2]); return original(*args, **kwargs)
    monkeypatch.setattr(intake, 'ingest', wrapped)
    review = FolderReview(vault, planner=fake_planner)
    result = review.survey(source)
    assert called == ['folder:' + str(source)]
    assert EvidenceStore(vault).get(result['inventory_evidence']).kind == 'survey'
    for card in result['cards']:
        assert card['intake']['stages'] == ['capture', 'evidence', 'facts', 'describe', 'stage']
        assert EvidenceStore(vault).get(card['evidence'][0]['id'])
        record = dik.load(vault, card['id'])
        assert record['data'][0]['status'] == 'not examined'
        assert record['data'][0]['evidence'] == card['evidence'][0]['id']
        assert card['provenance']['checked'] is True
    again = review.survey(source)
    assert again['inventory_evidence'] == result['inventory_evidence']
    assert [c['evidence'] for c in again['cards']] == [c['evidence'] for c in result['cards']]


def test_failed_planner_is_quarantined_by_native_intake(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    def broken(found):
        plan = fake_planner(found); plan['shared_survey_fingerprint'] = 'wrong'; return plan
    with pytest.raises(ValueError, match='SHARED_SURVEY_MISMATCH'):
        FolderReview(vault, planner=broken).survey(source)
    rows = list((vault.work('quarantine') / 'intake').glob('*.json'))
    assert len(rows) == 1
    assert json.loads(rows[0].read_text())['stage'] == 'facts'


def test_unapproved_real_clerk_is_blocked_before_dispatch(library, monkeypatch):
    from resource_librarian import clerk
    from resource_librarian.folder_review import FolderReview
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    calls = []
    monkeypatch.setattr(clerk, 'run', lambda *a: calls.append(a))
    with pytest.raises(ValueError, match='FOLDER_DRAFT_DISABLED'):
        review.draft(card['id'], object(), approved=True)
    assert not calls


def test_folder_draft_checks_provenance_and_runs_sensitivity(library):
    from resource_librarian import clerk
    from resource_librarian.folder_review import FolderReview
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    bad = clerk.Scripted(lambda p: {'folder_brief': {'description': 'This folder has 999 files.'},
                          'sensitivity': {'sensitivity': 'normal', 'reason': 'metadata only'}}[p['task']])
    with pytest.raises(ValueError, match='FOLDER_PROVENANCE'):
        review.draft(card['id'], bad, approved=True)
    assert review.store.load(card['id'])['description']['text'] == ''
    good = clerk.Scripted(lambda p: {'folder_brief': {'description': 'This folder has 1 files.'},
                           'sensitivity': {'sensitivity': 'review_required', 'reason': 'dual use'}}[p['task']])
    drafted = review.draft(card['id'], good, approved=True)
    assert drafted['sensitivity']['sensitivity'] == 'review_required'
    assert drafted['description']['provenance'][0]['outcome'] == 'supported'


def test_accepted_card_has_immutable_evidence_and_authored_dik(library):
    from resource_librarian import dik
    from resource_librarian.evidence import EvidenceStore
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'src')
    accepted = review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='code', person=True)
    record = EvidenceStore(vault).get(accepted['accepted_evidence'])
    assert record.authorship == 'owner_created'
    assert dik.load(vault, card['id'])['authorship'] == 'owner_created'
    assert record.payload['inventory_evidence'] == card['evidence'][0]['id']


def test_description_is_checked_again_before_display(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    card['description']['text'] = 'This folder contains 900 files.'
    review.store.save(card)
    displayed = next(c for c in review.list() if c['id'] == card['id'])
    assert displayed['description']['text'] == ''
    assert displayed['description']['state'] == 'provenance_refused'


def test_changed_evidence_refuses_acceptance_even_if_native_fingerprint_matches(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda x: applied.append(x) or {})
    card = review.survey(source)['cards'][0]
    card['evidence'][0]['id'] = '0' * 32
    review.store.save(card)
    with pytest.raises(ValueError, match='FOLDER_EVIDENCE_STALE'):
        review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='code', person=True)
    assert not applied


def test_folder_duplicates_use_document_identity_and_are_metadata_candidates(library, monkeypatch):
    from resource_librarian import document_identity
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    # Equal relative inventories, intentionally different folder names and content.
    (source / 'third_party_beta/b.py').rename(source / 'third_party_beta/a.py')
    calls = []
    remember = document_identity.remember
    def spy(*args, **kwargs):
        calls.append(args[1]); return remember(*args, **kwargs)
    monkeypatch.setattr(document_identity, 'remember', spy)
    review = FolderReview(vault, planner=fake_planner)
    result = review.survey(source)
    assert calls
    groups = result['duplicates']['groups']
    assert groups and all(g['scope'] == 'folder_inventory_metadata' and g['candidate_only'] for g in groups)
    assert all('content not examined' in g['why'] for g in groups)


def test_credential_and_bundle_metadata_never_appear_as_folder_content(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    for name in ['src/Frank.env', 'src/a.bundle.js', 'src/graphify-out/output.json']:
        path = source / name; path.parent.mkdir(exist_ok=True); path.write_text('do not read')
    review = FolderReview(vault, planner=fake_planner)
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'src')
    assert [r['path'] for r in card['inventory_metadata']] == ['src/a.py']
    assert card['file_counts'] == {'.py': 1}


def test_folder_cards_use_existing_person_started_approved_batch(library):
    from resource_librarian import batch, clerk
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.registry import Context
    from resource_librarian.workflows import RunStore
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    cards = review.survey(source)['cards']
    selected = [c['id'] for c in cards[:2]]
    with pytest.raises(ValueError, match='PERSON_CONFIRMS'):
        review.approve_batch(selected, person=False)
    review.approve_batch(selected, person=True)
    endpoint = clerk.Scripted(lambda p: {'description': 'Folder inventory; content not examined.'}
        if p['task'] == 'folder_brief' else {'sensitivity': 'normal', 'reason': 'metadata only'})
    ctx = Context(tier='curate', vault=vault, extras={'caller_kind': 'person', 'clerk': endpoint})
    result = batch.start(ctx, 'person')
    assert result['total'] == 2 and result['status'] == 'finished'
    for key in selected:
        item = review.store.load(key)
        assert item['status'] == 'enriched'  # Processing is NOT canonical acceptance.
        assert item['processing']['coverage'] == 'metadata only; content not examined'
    assert cards[2]['id'] not in result['items'][0].values()
    assert set(RunStore(vault).events(result['run'])[0]['items']) == set(selected)
    assert not list(vault.root.glob('Sources/**/*.md'))


def test_folder_batch_is_partial_when_production_drafting_is_disabled(library):
    from resource_librarian import batch
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.registry import Context
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    review.approve_batch([card['id']], person=True)
    result = batch.start(Context(tier='curate', vault=vault, extras={'caller_kind': 'person'}), 'person')
    assert result['status'] == 'finished'
    item = review.store.load(card['id'])
    assert item['status'] == 'partial'
    assert item['processing']['stages']['folder_describe'] == 'queued'
    assert 'content not examined' in item['processing']['coverage']


def test_review_required_card_stays_outside_unambiguous_batch(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    card['sensitivity'] = {'sensitivity': 'review_required', 'reason': 'dual use'}
    review.store.save(card)
    with pytest.raises(ValueError, match='SENSITIVITY_REVIEW'):
        review.approve_batch([card['id']], person=True)
    assert review.store.load(card['id'])['status'] == 'staged'


def test_folder_batch_stage_key_is_bound_to_route(library):
    from resource_librarian.batch import _stage_key
    identity = {'kind':'folder', 'inventory_evidence':'a' * 32}
    assert _stage_key(identity, 'folder_describe', 'route-a') != _stage_key(identity, 'folder_describe', 'route-b')


def test_stored_unchecked_description_cannot_be_accepted(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda x: applied.append(x) or {})
    card = review.survey(source)['cards'][0]
    card['description']['text'] = 'This folder has 450 files.'; review.store.save(card)
    with pytest.raises(ValueError, match='FOLDER_PROVENANCE'):
        review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='code', person=True)
    assert not applied


def test_stale_clerk_result_cannot_replace_person_edit(library):
    from resource_librarian import batch, clerk
    from resource_librarian.registry import Context
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.coordination import PreconditionChangedError
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    def answer(payload):
        fresh = review.store.load(card['id'])
        fresh['description']['text'] = 'Person revised this draft.'; review.store.save(fresh)
        return {'description':'Original inventory.'} if payload['task']=='folder_brief' else {'sensitivity':'normal','reason':'metadata'}
    ctx = Context(tier='curate',vault=vault,extras={'clerk':clerk.Scripted(answer)})
    with pytest.raises(PreconditionChangedError):
        batch._folder_describe(ctx, card)
    assert review.store.load(card['id'])['description']['text'] == 'Person revised this draft.'
