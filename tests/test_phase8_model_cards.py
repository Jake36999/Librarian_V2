"""S6b owner metadata beats generated drafts, without silently applying a tier map."""
import hashlib

import pytest

from conftest import add_source, write_note
from resource_librarian import notes
from test_app import served  # noqa: F401


def test_profile_precedence_is_per_field_and_preserves_explicit_unknown():
    from resource_librarian.model_cards import merge_profiles
    key = ('deepinfra', 'example/model')
    out = merge_profiles({key: {'context_length': 100, 'tool_calling': True, 'recommendation_rank': 3}},
        {key: {'authorship': 'generated', 'context_length': 200, 'price_input_per_1m': 0.1}},
        {key: {'authorship': 'owner_created', 'context_length': 150, 'tool_calling': None, 'task_class': 'Sub_Agent'}})[key]
    assert out['context_length'] == 150
    assert out['tool_calling'] is None
    assert out['price_input_per_1m'] == 0.1
    assert out['recommendation_rank'] == 3
    assert out['_field_authorship']['context_length'] == 'owner_created'
    assert out['_field_authorship']['price_input_per_1m'] == 'generated'
    assert 'suggested_tier' not in out  # owner has not approved task_class → tier


def test_generated_fields_cannot_override_owner_fields_from_a_previous_layer():
    from resource_librarian.model_cards import merge_profiles
    key = ('deepinfra', 'example/model')
    out = merge_profiles({}, {key: {'authorship': 'owner_created', 'context_length': 150}},
                          {key: {'authorship': 'generated', 'context_length': 300, 'tool_calling': True}})[key]
    assert out['context_length'] == 150 and out['tool_calling'] is True


@pytest.fixture
def owner_model(vault, tmp_path):
    root = tmp_path / 'v1'
    path = write_note(root, '10-Models/Owner model.md',
        'type: ai_model\nprovider: DeepInfra\nmodel_id: example/model\ncanonical_url: https://example.org/model\n'
        'context_length: 131072\ntask_class: Sub_Agent\nstatus: active',
        '# Owner model\n\n## Model Card\nDistributor quotation fixture.\n\n## Reading Notes\nMy test observations.\n')
    write_note(vault.root, 'Sources/model/Machine model.md',
        'type: source\nkind: model\ntitle: Machine model\ncanonical_url: https://example.org/model\n'
        'provider: deepinfra\nmodel_id: example/model\ncontext_length: 262144\n'
        'suggested_tier: Tier_1\nauthorship: generated', '## Bottom Line\nGenerated model description.\n')
    return root, path


def test_existing_model_card_is_staged_as_a_revision_not_silently_skipped(vault, owner_model):
    from resource_librarian import v1_export
    from resource_librarian.staging import StagingStore
    root, _ = owner_model
    plan = v1_export.plan(root, vault)
    row = next(r for r in plan['rows'] if r['v1_path'] == '10-Models/Owner model.md')
    assert row['action'] == 'stage' and row['revision_of'].endswith('Machine model.md')
    result = v1_export.stage(root, vault)
    assert result['staged'] == 1
    item = StagingStore(vault).load(result['items'][0])
    assert item['revision_of'].endswith('Machine model.md')
    assert item['fields']['context_length'] == 131072
    assert item['fields']['authorship'] == 'owner_created'
    assert item['fields']['section_authorship']['Model Card'] == 'third_party'
    assert item['fields']['section_authorship']['Reading Notes'] == 'owner_created'
    assert item['fields'].get('suggested_tier') is None
    assert v1_export.stage(root, vault)['staged'] == 0
    held = notes.load(vault.root / 'Sources/model/Machine model.md')
    assert held.frontmatter['context_length'] == 262144  # no write before person review


def test_model_refresh_composition_updates_owner_fields_but_preserves_unset_generated_fields(vault, owner_model):
    from resource_librarian import v1_export
    from resource_librarian.staging import StagingStore, compose_revision
    root, _ = owner_model
    result = v1_export.stage(root, vault)
    assert result['items'], result
    store = StagingStore(vault); item = store.load(result['items'][0])
    composed = compose_revision(store, item)
    fm, _, _ = notes.parse(composed['composed'])
    assert fm['context_length'] == 131072
    assert fm['suggested_tier'] == 'Tier_1'  # no implicit mapping; show pending disagreement
    assert fm['field_authorship']['suggested_tier'] == 'generated'
    assert fm['field_authorship']['task_class'] == 'owner_created'


def test_model_refresh_refuses_when_target_changed_after_staging(vault, owner_model):
    from resource_librarian import v1_export
    from resource_librarian.staging import StagingStore, compose_revision
    root, _ = owner_model
    result = v1_export.stage(root, vault)
    assert result['items'], result
    store = StagingStore(vault); item = store.load(result['items'][0])
    target = vault.root / item['revision_of']
    target.write_text(target.read_text(encoding='utf-8') + '\nPerson edited this meanwhile.\n', encoding='utf-8')
    with pytest.raises(Exception, match='DOCUMENT_ACTIVE|STALE'):
        compose_revision(store, item)


def test_distributor_section_taints_but_owner_reading_notes_do_not(vault):
    from resource_librarian.registry import Context, REGISTRY
    from resource_librarian.session import SessionStore
    import resource_librarian.tools  # noqa: F401
    write_note(vault.root, 'Sources/model/Mixed card.md',
        'type: source\nkind: model\nauthorship: owner_created\nsection_authorship:\n'
        '  Model Card: third_party\n  Reading Notes: owner_created',
        '## Model Card\nDistributor quotation fixture.\n\n## Reading Notes\nOwner observations.\n')
    sid = SessionStore(vault).new('explore', question='Read a model card').id
    ctx = Context(tier='contribute', vault=vault, session=sid)
    out = REGISTRY.call('get_note', {'name': 'Mixed card', 'sections': ['Reading Notes']}, ctx)
    assert out['found'] and not SessionStore(vault).load(sid).taint_sources
    out = REGISTRY.call('get_note', {'name': 'Mixed card', 'sections': ['Model Card']}, ctx)
    assert out['found'] and SessionStore(vault).load(sid).taint_sources
    assert any('Model Card' in source for source in SessionStore(vault).load(sid).taint_sources)


def test_generated_card_cannot_claim_owner_field_authority():
    from resource_librarian.model_cards import merge_profiles
    key = ('deepinfra', 'example/model')
    out = merge_profiles({}, {key: {'authorship': 'owner_created', 'context_length': 100}},
        {key: {'authorship': 'generated', 'field_authorship': {'context_length': 'owner_created'}, 'context_length': 1000}})[key]
    assert out['context_length'] == 100


def test_picker_merges_accepted_model_sources_per_field_and_shows_owner_class(served, monkeypatch):
    import resource_librarian.app as app_module
    app, _, model = served
    monkeypatch.setattr(model.provider, 'models', lambda: ['example/model'])
    monkeypatch.setattr(app_module, '_shipped_profiles', lambda: {('deepinfra', 'example/model'):
        {'context_length': 100, 'tool_calling': True}})
    write_note(app.vault.root, 'Sources/model/Draft.md',
        'type: source\nkind: model\nprovider: deepinfra\nmodel_id: example/model\nauthorship: generated\n'
        'context_length: 262144\nprice_input_per_1m: 0.25\nsuggested_tier: Tier_1', '## Bottom Line\nDraft.\n')
    write_note(app.vault.root, 'Sources/model/Owner.md',
        'type: source\nkind: model\nprovider: deepinfra\nmodel_id: example/model\nauthorship: owner_created\n'
        'context_length: 131072\ntask_class: Sub_Agent', '## Reading Notes\nOwner observations.\n')
    app.index_service.refresh()
    profile = app.models('deepinfra')['models'][0]['profile']
    assert profile['context_length'] == 131072
    assert profile['price_input_per_1m'] == 0.25
    assert profile['tool_calling'] is True
    assert profile['task_class'] == 'Sub_Agent'
    assert profile['suggested_tier'] == 'Tier_1'  # mapping still awaits owner
    assert profile['field_authorship']['context_length'] == 'owner_created'
    route_profile = app._route_catalogue_entry({'provider': 'deepinfra', 'model': 'example/model'})
    assert route_profile['tool_calling'] is True  # same fieldwise fallback on the actual route path
    assert not model.provider.calls  # metadata listing dispatched no chat/probe


def test_person_accepts_refresh_and_later_v1_edits_create_a_new_revision(vault, owner_model):
    from resource_librarian import v1_export, staging
    from resource_librarian.index import Index
    from resource_librarian.search import Engine
    root, card = owner_model
    first = v1_export.stage(root, vault)
    store = staging.StagingStore(vault)
    with Index(vault) as index:
        index.refresh()
        result = staging.decide(store, Engine(index), first['items'], 'accept', decided_by='person')
        assert result[0]['status'] == 'accepted'
    assert notes.load(vault.root / 'Sources/model/Machine model.md').frontmatter['context_length'] == 131072
    assert v1_export.stage(root, vault)['staged'] == 0
    card.write_text(card.read_text(encoding='utf-8').replace('131072', '65536'), encoding='utf-8')
    second = v1_export.stage(root, vault)
    assert second['staged'] == 1
    assert second['items'] != first['items']
    assert notes.load(vault.root / 'Sources/model/Machine model.md').frontmatter['context_length'] == 131072


def test_model_refresh_never_uses_agent_promotion_mode_to_skip_person_review(vault, owner_model):
    from resource_librarian import v1_export, staging
    from resource_librarian.index import Index
    from resource_librarian.search import Engine
    root, _ = owner_model
    first = v1_export.stage(root, vault)
    item = staging.StagingStore(vault).load(first['items'][0])
    target = vault.root / item['revision_of']; before = target.read_bytes()
    with Index(vault) as index:
        index.refresh()
        with pytest.raises(Exception, match='PERSON_CONFIRMS'):
            staging._decide_revision(staging.StagingStore(vault), Engine(index), item,
                                    'accept', {}, 'agent', 'agent')
    assert target.read_bytes() == before


@pytest.mark.parametrize('invalid', ['unsupported_author', 'null', '[owner_created]', '{label: owner_created}'])
def test_invalid_section_authorship_is_unclassified_not_owner_trust(vault, invalid):
    from resource_librarian.registry import Context, REGISTRY
    from resource_librarian.session import SessionStore
    import resource_librarian.tools  # noqa: F401
    write_note(vault.root, 'Sources/model/Invalid card.md',
        'type: source\nkind: model\nauthorship: owner_created\nsection_authorship:\n  Model Card: ' + invalid,
        '## Model Card\nA source excerpt with invalid provenance.\n')
    sid = SessionStore(vault).new('explore', question='Read a card').id
    out = REGISTRY.call('get_note', {'name': 'Invalid card'}, Context(vault=vault, session=sid))
    assert out['found']
    assert SessionStore(vault).load(sid).taint_sources
    assert any(s.get('authorship_resolution') == 'unclassified' for s in out['access']['sources'])


def test_v1_card_scan_refuses_credential_like_paths_before_read(vault, tmp_path, monkeypatch):
    from resource_librarian import v1_export
    from resource_librarian.credentials import credential_path
    root = tmp_path / 'v1'
    write_note(root, '10-Models/certs/fixture.md', 'type: ai_model', 'Fixture name only; not a credential.')
    real = notes.load
    refused_reads = []
    def load(path):
        if credential_path(path):refused_reads.append(str(path))
        assert not credential_path(path), 'Credential-like path reached the note reader'
        return real(path)
    monkeypatch.setattr(notes, 'load', load)
    rows = v1_export.candidates(root)
    assert refused_reads == []
    assert len(rows) == 1 and rows[0]['action'] == 'left out'
    assert 'credential' in rows[0]['why'].lower()


def test_shared_native_note_walk_does_not_offer_credential_or_generated_notes(vault):
    for rel in ['certs/model.md', 'graphify-out/summary.md', 'build/generated.md']:
        write_note(vault.root, rel, 'type: source', 'Fixture path only.')
    offered = {p.relative_to(vault.root).as_posix() for p in notes.iter_paths(vault.root)}
    assert not {'certs/model.md', 'graphify-out/summary.md', 'build/generated.md'} & offered


def test_v1_generated_model_draft_is_not_relabelled_as_owner_metadata():
    from resource_librarian.model_cards import import_fields
    fields = import_fields({'authorship': 'generated', 'drafted_by': 'scripted-model', 'context_length': 100},
                           {'Reading Notes': 'Machine observations.', 'Model Card': 'Distributor text.'}, 'a' * 64)
    assert fields['authorship'] == 'generated'
    assert fields['field_authorship']['context_length'] == 'generated'
    assert fields['section_authorship']['Reading Notes'] == 'generated'
    assert fields['section_authorship']['Model Card'] == 'third_party'


def test_model_card_distributor_quotes_remain_bounded_at_the_result_boundary(vault):
    import json
    from resource_librarian.registry import Context, REGISTRY
    from resource_librarian.mcp_client import external_result_limit
    import resource_librarian.tools  # noqa: F401
    write_note(vault.root, 'Sources/model/Large card.md',
        'type: source\nkind: model\nauthorship: owner_created\nsection_authorship:\n  Model Card: third_party',
        '## Model Card\n' + 'A long distributor quotation. ' * 5000)
    out = REGISTRY.call('get_note', {'name': 'Large card'}, Context(vault=vault))
    assert out['found']
    assert len(json.dumps(out, ensure_ascii=True)) <= external_result_limit(None)
    assert out['truncated'] and out['omissions']
    assert any(s['authorship'] == 'third_party' for s in out['access']['sources'])


def test_owner_explicit_unknown_field_survives_the_v1_refresh_path(vault, owner_model):
    from resource_librarian import v1_export, staging
    root, card = owner_model
    card.write_text(card.read_text(encoding='utf-8').replace('context_length: 131072', 'context_length: null'), encoding='utf-8')
    result = v1_export.stage(root, vault)
    store = staging.StagingStore(vault)
    item = store.load(result['items'][0])
    composed = staging.compose_revision(store, item)
    fm, _, _ = notes.parse(composed['composed'])
    assert 'context_length' in fm and fm['context_length'] is None
    assert fm['field_authorship']['context_length'] == 'owner_created'


@pytest.mark.parametrize('author', [None, 'unexpected', {'label': 'owner_created'}])
def test_explicit_unclassified_v1_authorship_cannot_be_promoted_by_folder_name(author):
    from resource_librarian.model_cards import import_fields
    with pytest.raises(TypeError, match='MODEL_CARD_AUTHORSHIP_UNCLASSIFIED'):
        import_fields({'authorship': author}, {}, 'a' * 64)
