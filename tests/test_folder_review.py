import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from resource_librarian.vault import Vault


@pytest.fixture
def library(tmp_path):
    root = tmp_path / 'library'; root.mkdir()
    vault = Vault(root)
    source = tmp_path / 'source'; source.mkdir()
    for name in ['src/a.py', 'third_party_alpha/a.py', 'third_party_beta/b.py', 'docs/note.md']:
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic fixture\n')
    return vault, source


def fake_planner(surveyed):
    return {'plan_version': 'workspace-init-v1', 'geographer_version': '0.2.0',
        'shared_survey_fingerprint': surveyed.fingerprint, 'root': surveyed.canonical_root,
        'partitions': [dict(key=name, subtrees=[name], file_counts={'.py': 1}, bytes=18,
                           suggestion=dict(purpose='third-party' if name.startswith('third_party') else 'own-current',
                                           reasons=['synthetic metadata signal']))
                       for name in ['src', 'third_party_alpha', 'third_party_beta', 'docs']],
        'excluded': [], 'credential_refusals': {'count': 0, 'paths': []}}


def test_stages_folder_cards_with_shared_fingerprint_and_group_suggestion(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner)
    cards = review.survey(source)['cards']
    assert len(cards) == 4
    assert all(c['status'] == 'staged' and c['description']['state'] == 'awaiting_model_draft' for c in cards)
    third = [c for c in cards if c['suggested_purpose'] == 'third-party']
    assert len({c['suggested_graph'] for c in third}) == 1
    assert third[0]['suggested_graph'] == 'library-third-party'


def test_accept_is_person_only_and_attached_roots_stay_readonly(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {'graphs': []})
    cards = review.survey(source)['cards']; card = next(c for c in cards if c['path'] == 'src')
    with pytest.raises(ValueError, match='PERSON_CONFIRMS'):
        review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='library-code', person=False)
    result = review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='library-code', person=True)
    assert result['status'] == 'accepted' and applied
    manifest = json.loads((vault.librarian / 'content-roots.json').read_text())
    row = next(r for r in manifest['roots'] if r['path'] == str(source / 'src'))
    assert row['access'] == 'read_only' and row['attached']


def test_unchanged_acceptance_survives_resurvey_but_changed_folder_reasks(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    cards = review.survey(source)['cards']; card = next(c for c in cards if c['path'] == 'src')
    review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='library-code', person=True)
    (source / 'docs/note.md').write_text('an unrelated edit')
    assert next(c for c in review.survey(source)['cards'] if c['path'] == 'src')['status'] == 'accepted'
    (source / 'src/a.py').write_text('a changed source')
    assert next(c for c in review.survey(source)['cards'] if c['path'] == 'src')['status'] == 'staged'


def test_excluded_folder_never_reaches_ingest(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {})
    card = review.survey(source)['cards'][0]
    review.accept(card['id'], card['folder_fingerprint'], purpose='exclude', graph='', person=True)
    assert not applied


def test_third_party_folder_disables_project_writes(library):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian import projects
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'third_party_alpha')
    review.accept(card['id'], card['folder_fingerprint'], purpose='third-party', graph='library-third-party', person=True)
    projects._save(vault, {'enabled': True, 'roots': [{'id': 'test', 'path': str(source), 'writes': True}]})
    from resource_librarian.rules import Refusal
    with pytest.raises(Refusal) as refused:
        projects.edit(vault, source, 'third_party_alpha/a.py', 'replace', 'new', 'synthetic fixture')
    assert refused.value.code == 'FOLDER_READ_ONLY'


def test_accepted_child_overrides_parent_and_every_folder_is_reviewable(library):
    from resource_librarian.folder_review import FolderReview, decision_for
    vault, source = library
    nested = source / 'third_party_alpha/own-analysis'; nested.mkdir(); (nested / 'report.md').write_text('synthetic')
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    cards = review.survey(source)['cards']
    parent = next(c for c in cards if c['path'] == 'third_party_alpha')
    child = next(c for c in cards if c['path'] == 'third_party_alpha/own-analysis')
    review.accept(parent['id'], parent['folder_fingerprint'], purpose='third-party', graph='references', person=True)
    assert decision_for(vault, nested / 'report.md')['purpose'] == 'third-party'
    review.accept(child['id'], child['folder_fingerprint'], purpose='own-docs', graph='analysis', person=True)
    assert decision_for(vault, nested / 'report.md')['purpose'] == 'own-docs'


def test_model_draft_is_explicitly_approved_metadata_only_and_never_accepted(library, monkeypatch):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian import clerk
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    with pytest.raises(ValueError, match='SPEND_APPROVAL_REQUIRED'):
        review.draft(card['id'], object())
    def run(tasks, endpoint):
        assert 'synthetic fixture' not in tasks[0].chunk
        return [SimpleNamespace(ok=True, value={'description': 'A synthetic folder inventory.'})]
    monkeypatch.setattr(clerk, 'run', run)
    result = review.draft(card['id'], object(), approved=True)
    assert result['status'] == 'staged' and result['description']['draft']
    assert result['description']['state'] == 'model_draft'


def test_folder_review_is_woven_into_native_attach_without_a_second_survey(library, monkeypatch):
    from resource_librarian import content_roots, folder_review
    vault, source = library
    monkeypatch.setattr(type(vault), 'exists', lambda self: True)
    monkeypatch.setattr(folder_review, 'configuration', lambda _: {'enabled': True})
    calls = []
    def planner(config, operation, payload):
        calls.append(payload['fingerprint'])
        return fake_planner(SimpleNamespace(fingerprint=payload['fingerprint'], canonical_root=payload['root']))
    monkeypatch.setattr(folder_review, 'cli', planner)
    plan = content_roots.plan_attach(vault, source)
    assert plan['geo_grapher']['shared_survey_fingerprint'] == plan['survey_fingerprint']
    result = content_roots.apply_attach(vault, source, plan['survey_fingerprint'])
    assert result['folders']['cards']
    assert len(calls) == 2, 'one shared survey/plan per native planning and compare-and-apply operation'


def test_writer_cannot_modify_a_readonly_folder_even_with_a_declared_target(library):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.coordination import VaultWriter
    vault, _ = library; source = vault.root / 'third_party_alpha'; source.mkdir()
    target = source / 'a.py'; target.write_text('synthetic')
    def planner(found):
        p = fake_planner(found); p['partitions'] = [dict(key='residual', subtrees=[], file_counts={'.py':1},
            bytes=9, suggestion=dict(purpose='third-party', reasons=['synthetic']))]; return p
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    card = review.survey(source)['cards'][0]
    review.accept(card['id'], card['folder_fingerprint'], purpose='third-party', graph='references', person=True)
    writer = VaultWriter(vault)
    try:
        with pytest.raises(Exception, match='READ_ONLY|read.only'):
            writer.submit(lambda: target.write_text('changed'), targets=['third_party_alpha/a.py'])
    finally:
        writer.close()
    assert target.read_text() == 'synthetic'


def test_enabled_project_attachment_keeps_sidecar_in_library_and_cannot_enable_writes(library):
    from resource_librarian import projects
    vault, source = library
    vault.librarian.mkdir(exist_ok=True)
    (vault.librarian / 'geographer.json').write_text(json.dumps({'enabled': True}))
    result = projects.add_root(vault, str(source))
    assert not (source / 'librarian-app').exists()
    assert result['access'] == 'read_only'
    with pytest.raises(Exception, match='READ_ONLY|read.only'):
        projects.set_writes(vault, result['id'], True)


@pytest.mark.parametrize('parent_purpose', ['exclude', 'third-party'])
def test_accepted_internal_child_override_controls_index_scope_and_write_access(library, parent_purpose):
    from resource_librarian.folder_review import FolderReview, refuse_write
    from resource_librarian.content_roots import iter_documents
    vault, _ = library
    parent = vault.root / 'mixed'; child = parent / 'own-analysis'; child.mkdir(parents=True)
    target = child / 'report.md'; target.write_text('synthetic own document')
    def planner(found):
        return dict(plan_version='workspace-init-v1', shared_survey_fingerprint=found.fingerprint,
            partitions=[dict(key='residual', subtrees=[], file_counts={'.md':1}, bytes=22,
                suggestion=dict(purpose='third-party', reasons=['synthetic']))])
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    cards = review.survey(parent)['cards']; root = next(c for c in cards if c['path'] == '.')
    nested = next(c for c in cards if c['path'] == 'own-analysis')
    review.accept(root['id'], root['folder_fingerprint'], purpose=parent_purpose, graph='' if parent_purpose=='exclude' else 'references', person=True)
    review.accept(nested['id'], nested['folder_fingerprint'], purpose='own-docs', graph='own-analysis', person=True)
    assert target in iter_documents(vault.root)
    refuse_write(vault, target)


def test_accepting_another_card_cannot_silently_reingest_a_changed_accepted_folder(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {})
    cards = review.survey(source)['cards']
    first = next(c for c in cards if c['path'] == 'src')
    second = next(c for c in cards if c['path'] == 'third_party_alpha')
    review.accept(first['id'], first['folder_fingerprint'], purpose='own-current', graph='own', person=True)
    (source / 'src/a.py').write_text('changed since acceptance')
    with pytest.raises(ValueError, match='FOLDER_STALE'):
        review.accept(second['id'], second['folder_fingerprint'], purpose='third-party', graph='references', person=True)
    assert len(applied) == 1
