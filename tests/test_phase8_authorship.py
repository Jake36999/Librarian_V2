import json
from types import SimpleNamespace

import pytest

from resource_librarian.registry import Context, ToolSpec, Card
from test_folder_review import library, fake_planner


@pytest.mark.parametrize('purpose,expected', [('own-current', 'owner_created'),
    ('own-legacy', 'owner_created'), ('own-docs', 'owner_created'),
    ('research-docs', 'third_party'), ('third-party', 'third_party')])
def test_folder_decision_derives_authorship_and_publishes_to_manifest(library, purpose, expected):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.content_roots import load
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'src')
    accepted = review.accept(card['id'], card['folder_fingerprint'], purpose=purpose,
                            graph='fixture', person=True)
    assert accepted['decision']['authorship'] == expected
    assert next(r for r in load(vault.root)['roots'] if r.get('folder_decision') == card['id'])['authorship'] == expected


@pytest.mark.parametrize('purpose', ['data', 'logs/transcripts'])
def test_ambiguous_folder_requires_explicit_authorship(library, purpose):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'src')
    with pytest.raises(ValueError, match='AUTHORSHIP'):
        review.accept(card['id'], card['folder_fingerprint'], purpose=purpose, graph='fixture', person=True)
    accepted = review.accept(card['id'], card['folder_fingerprint'], purpose=purpose,
                            graph='fixture', person=True, authorship='third_party')
    assert accepted['decision']['authorship'] == 'third_party'


def test_search_snippet_resolves_note_authorship_and_trusted_geo_json_wrapper(vault):
    from resource_librarian.access import result_access
    p = vault.root / 'Sources/ref.md'
    p.parent.mkdir(exist_ok=True)
    p.write_text('---\nauthorship: third_party\n---\n\n# Ref\nText.', encoding='utf-8')
    spec = ToolSpec('search', lambda ctx: {}, 'consult', 'read', Card('Search'))
    out = result_access(spec, {}, {'results': [{'name': 'ref', 'fields': {}}]}, Context(vault=vault))
    assert out['taint_sources']
    geo = ToolSpec('geo', lambda ctx: {}, 'consult', 'read', Card('Geo'), external=True,
                   provenance_authority='geographer')
    result = {'content': json.dumps({'graph_id': 'g', 'cite_as': 'own/root',
                                     'authorship': 'owner_created'})}
    out = result_access(geo, {}, result, Context(vault=vault))
    assert out['sources'] == [{'handle': 'own/root', 'authorship': 'owner_created'}]
    assert out['taint_sources'] == []


def test_connector_trust_is_acceptance_bound_and_unknown_server_is_open_world(tmp_path):
    from resource_librarian.mcp_client import McpManager, digest
    from resource_librarian.registry import REGISTRY
    definition = {'command': 'fixture', 'args': []}
    assert digest(definition) != digest({**definition, 'provenance_authority': 'geographer'})


def test_native_generated_note_keeps_its_authorship_when_read_back(vault):
    from test_closure import Lead
    from resource_librarian.session import SessionStore
    from resource_librarian import notes
    lead = Lead(vault)
    lead('open_session', purpose='add_project', question='q')
    made = lead('create_project', name='Fixture project', stage='planning', summary='Synthetic own work.')
    assert notes.load(vault.root / made['created']).frontmatter['authorship'] == 'generated'
    read = lead('get_note', name='Fixture project')
    assert not read['access']['taint_sources']
    assert not SessionStore(vault).load(lead.ctx.session).taint_sources


def test_only_operator_bound_geo_connector_can_project_transport_provenance():
    from resource_librarian.mcp_client import project_result_metadata
    result = SimpleNamespace(meta={'access': {'authorship': 'owner_created', 'cite_as': 'own/root'}})
    assert project_result_metadata({}, result) == {}
    assert project_result_metadata({'provenance_authority': 'geographer'}, result) == {
        'provenance_metadata': result.meta['access']}


def test_third_party_data_root_stays_read_only_even_inside_the_vault(vault):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.content_roots import load
    root = vault.root / 'data'
    root.mkdir()
    review = FolderReview(vault)
    review._root_access({'source_root': str(vault.root), 'path': 'data', 'id': 'fixture',
        'survey_fingerprint': 'fixture', 'decision': {'purpose': 'data', 'authorship': 'third_party'}})
    assert next(r for r in load(vault.root)['roots'] if r['path'] == 'data')['access'] == 'read_only'


def test_unclassified_child_purpose_never_inherits_parent_ownership(vault, monkeypatch):
    from resource_librarian import content_roots, folder_review
    from resource_librarian.access import _native_authorship
    content_roots._write_json(content_roots.manifest_path(vault.root), {'version': 1,
        'roots': [{'path': '.', 'access': 'read_write', 'authorship': 'owner_created'}]})
    monkeypatch.setattr(folder_review, 'decision_for', lambda *args: {'purpose': 'data'})
    assert _native_authorship(SimpleNamespace(vault=vault), 'data/file.txt') is None


def test_staged_folder_metadata_distinguishes_unclassified_source_from_generated_description(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'src')
    assert card['authorship'] is None
    assert card['authorship_resolution'] == 'unclassified'
    assert card['description']['authorship'] == 'generated'
    accepted = review.accept(card['id'], card['folder_fingerprint'], purpose='own-current',
                            graph='fixture', person=True)
    assert accepted['authorship'] == 'owner_created'
    assert accepted['description']['authorship'] == 'generated'


def test_legacy_folder_metadata_is_projected_without_silently_classifying_data(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = review.survey(source)['cards'][0]
    card.pop('authorship', None)
    card.pop('authorship_resolution', None)
    card['decision'] = {'purpose': 'own-current', 'accepted_by': 'person'}
    review.store.save(card)
    projected = next(c for c in review.overview()['cards'] if c['id'] == card['id'])
    assert projected['authorship'] == 'owner_created'
    card['decision'] = {'purpose': 'data', 'accepted_by': 'person'}
    review.store.save(card)
    projected = next(c for c in review.overview()['cards'] if c['id'] == card['id'])
    assert projected['authorship'] is None
    assert projected['authorship_resolution'] == 'unclassified'


def test_native_refusal_does_not_open_source_text_for_metadata(vault, monkeypatch):
    from resource_librarian import notes
    from resource_librarian.access import result_access
    p = vault.root / 'Notes/blocked.md'
    p.parent.mkdir(exist_ok=True)
    p.write_text('---\nauthorship: owner_created\n---\n\n# Fixture', encoding='utf-8')
    def denied_read(*args):
        raise AssertionError('Source read after refusal')
    monkeypatch.setattr(notes, 'load', denied_read)
    spec = ToolSpec('get_note', lambda ctx: {}, 'consult', 'read', Card('Read'))
    out = result_access(spec, {'name': 'blocked'}, {'error': 'refused'}, Context(vault=vault))
    assert out['taint_sources'] == []
