"""Owner T1–T4: source-set taint, persistence and person-scoped publication."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from resource_librarian.registry import Context, REGISTRY, Card, ToolSpec
from resource_librarian.session import SessionStore
from resource_librarian.rules import Refusal
from test_closure import Lead, executing, InjectingFetcher


def tainted(vault, purpose='explore'):
    lead = (executing(vault, operations=['read', 'untrusted', 'stage', 'write'],
                      write=['Notes/out.md', '.librarian/staging/'],
                      fetcher=InjectingFetcher()) if purpose == 'audited'
            else Lead(vault, fetcher=InjectingFetcher()))
    if purpose != 'audited':
        assert 'error' not in lead('open_session', purpose=purpose, question='q')
    assert 'error' not in lead('read_url', url='https://example.org/page')
    return lead


@pytest.mark.parametrize('purpose', ['explore', 'audited'])
def test_staging_and_work_state_remain_allowed(vault, purpose):
    from resource_librarian.access import publication_guard
    lead = tainted(vault, purpose)
    for name in ['stage_artifact', 'log_use', 'decide', 'add_candidate',
                 'record_synthesis', 'checkpoint', 'queue_source']:
        spec = REGISTRY.get(name)
        assert publication_guard(spec, {}, lead.ctx) == []
    for name in ['write_note', 'promote_offering', 'project_edit', 'vault_push']:
        with pytest.raises(Refusal, match='COMPOSITION_REFUSED') as exc:
            publication_guard(REGISTRY.get(name), {}, lead.ctx)
        assert 'https://example.org/page' in exc.value.detail
        assert 'stag' in exc.value.detail


def test_session_taint_survives_park_resume_branch_but_rewind_removes_it(vault):
    lead = Lead(vault, fetcher=InjectingFetcher())
    lead('open_session', purpose='explore', question='q')
    store = SessionStore(vault)
    store.append(lead.ctx.session, {'type': 'message', 'role': 'user', 'text': 'before'})
    lead('read_url', url='https://example.org/page')
    store.append(lead.ctx.session, {'type': 'message', 'role': 'assistant', 'text': 'after'})
    sources = store.load(lead.ctx.session).taint_sources
    assert sources and 'https://example.org/page' in str(sources)
    assert 'error' not in lead('park_session')
    restarted = Lead(vault)
    assert 'error' not in restarted('resume_session', session_id=lead.ctx.session)
    assert store.load(restarted.ctx.session).taint_sources == sources
    child = store.copy_through(lead.ctx.session, 0)
    assert store.load(child).taint_sources == sources  # branch cannot launder context
    # Park/resume are pre-existing write barriers for rewind. Exercise a
    # legal rewind on a fresh thread without bypassing those barriers.
    rewindable = Lead(vault, fetcher=InjectingFetcher())
    rewindable('open_session', purpose='explore', question='rewind fixture')
    store.append(rewindable.ctx.session, {'type': 'message', 'role': 'user', 'text': 'before'})
    rewindable('read_url', url='https://example.org/page')
    person = replace(rewindable.ctx, tier='curate', extras={'caller_kind': 'person'})
    assert 'error' not in REGISTRY.call('rewind_session', {'to_index': 0}, person)
    assert not store.load(rewindable.ctx.session).taint_sources
    assert not store.new('explore').taint_sources


def test_person_scoped_checkpoint_clear_requires_exact_current_sources(vault):
    from resource_librarian.access import clear_taint
    from resource_librarian.checkpoints import CheckpointStore
    lead = tainted(vault)
    person = replace(lead.ctx, tier='curate', extras={'caller_kind': 'person'})
    sources = SessionStore(vault).load(lead.ctx.session).taint_sources
    checkpoints = CheckpointStore(vault)
    cp = checkpoints.create('publication_taint', lead.ctx.session,
                            evidence={'session': lead.ctx.session, 'sources': sources},
                            choices=['decline', 'approve'], default='decline')
    with pytest.raises(Refusal):
        clear_taint(lead.ctx, cp['id'])
    with pytest.raises(Refusal):
        clear_taint(person, cp['id'])
    checkpoints.resolve(cp['id'], 'approve')
    assert clear_taint(person, cp['id'])['cleared_sources'] == sources
    assert not SessionStore(vault).load(lead.ctx.session).taint_sources
    lead('read_url', url='https://example.org/another')
    with pytest.raises(Refusal):
        clear_taint(person, cp['id'])


def test_mixed_geo_provenance_is_explicit_unknown_server_cannot_self_promote(vault):
    from resource_librarian.access import result_access
    ctx = Context(vault=vault)
    spec = ToolSpec('fixture', lambda ctx: {}, 'consult', 'read', Card('fixture'),
                    external=True, provenance_authority='geographer')
    payload = {'items': [
        {'graph_id': 'own', 'authorship': 'owner_created', 'cite_as': 'own/entity:1'},
        {'graph_id': 'ref', 'authorship': 'third_party', 'cite_as': 'ref/doc:2'},
        {'graph_id': 'work', 'authorship': 'generated', 'cite_as': 'work/root'}]}
    access = result_access(spec, {}, payload, ctx)
    assert {s['authorship'] for s in access['sources']} == {
        'owner_created', 'generated', 'third_party'}
    assert access['taint_sources'] == ['ref/doc:2']
    unknown = result_access(replace(spec, provenance_authority=''), {}, payload, ctx)
    assert unknown['taint_sources']
    assert not any(s['authorship'] == 'owner_created' for s in unknown['sources'])


def test_person_reader_does_not_taint_session(vault):
    lead = Lead(vault, fetcher=InjectingFetcher())
    lead('open_session', purpose='explore', question='q')
    person = replace(lead.ctx, tier='curate', extras={
        'caller_kind': 'person', 'fetcher': InjectingFetcher()})
    out = REGISTRY.call('read_url', {'url': 'https://example.org/page'}, person)
    assert 'error' not in out
    assert not SessionStore(vault).load(lead.ctx.session).taint_sources
    assert 'error' not in REGISTRY.call('write_note', {
        'folder': 'Notes', 'name': 'out', 'body': 'Person reviewed.', 'mode': 'create'}, person)


def test_project_review_forces_ask_and_preserves_licence_warning_even_in_auto(vault):
    from resource_librarian.access import publication_guard
    from resource_librarian.broker import Broker
    lead = tainted(vault)
    broker = Broker('auto', {'project_edit': 'allow'}, timeout=0)
    lead.ctx.extras['broker'] = broker
    sources = publication_guard(REGISTRY.get('project_edit'), {}, lead.ctx)
    heard = []

    def review(event):
        heard.append(event)
        if event['type'] == 'permission_request':
            broker.set_mode('auto')  # must not release a mandatory person review
            assert broker.pending()
            broker.answer(event['id'], 'allow_once')

    broker.subscribe(review)
    review_ctx = replace(lead.ctx, extras={**lead.ctx.extras, '_publication_review': sources})
    permission = broker.check(REGISTRY.get('project_edit'), {'path': 'src/a.py'}, review_ctx)
    assert permission.startswith('asked:')
    assert 'derived from third-party (unlicensed) material: do not copy it into this repository' in str(heard)
    assert 'https://example.org/page' in str(heard)


def test_record_application_is_generated_use_log_not_blocked_publication(vault):
    from resource_librarian.access import publication_guard, application_provenance
    lead = tainted(vault)
    assert publication_guard(REGISTRY.get('record_application'), {}, lead.ctx) == []
    metadata = application_provenance(lead.ctx)
    assert metadata['authorship'] == 'generated'
    assert 'https://example.org/page' in str(metadata['taint_sources'])


def test_person_checkpoint_ui_resolution_clears_the_scoped_session(vault):
    from resource_librarian.app import App
    from resource_librarian.checkpoints import CheckpointStore
    lead = tainted(vault)
    sources = SessionStore(vault).load(lead.ctx.session).taint_sources
    cp = CheckpointStore(vault).create('publication_taint', lead.ctx.session,
        evidence={'session': lead.ctx.session, 'sources': sources},
        choices=['decline', 'approve'], default='decline')
    app = App(vault, token='fixture', provider_for=lambda _: None)
    try:
        app.checkpoint_resolve(cp['id'], 'approve')
        assert not SessionStore(vault).load(lead.ctx.session).taint_sources
    finally:
        app.close_runtime()


def test_unknown_external_error_payload_does_not_bypass_session_taint(vault, monkeypatch):
    lead = Lead(vault)
    lead('open_session', purpose='explore', question='q')
    monkeypatch.setattr(REGISTRY, '_tools', dict(REGISTRY._tools))
    REGISTRY.register(ToolSpec('external_error_fixture',
        lambda ctx: {'error': 'provider_error', 'content': 'Untrusted provider text'},
        'consult', 'read', Card('Fixture error'), external=True, needs_vault=False))
    lead('external_error_fixture')
    assert SessionStore(vault).load(lead.ctx.session).taint_sources


def test_sessionless_helper_source_attaches_only_to_its_publication_session(vault, monkeypatch):
    store = SessionStore(vault)
    parent = store.new('explore')
    unrelated = store.new('explore')
    monkeypatch.setattr(REGISTRY, '_tools', dict(REGISTRY._tools))
    REGISTRY.register(ToolSpec('helper_external_fixture', lambda ctx: {'content': 'source'},
        'consult', 'read', Card('Fixture'), external=True, needs_vault=False))
    ctx = Context(vault=vault, extras={'_publication_session': parent.id})
    REGISTRY.call('helper_external_fixture', {}, ctx)
    assert store.load(parent.id).taint_sources
    assert not store.load(unrelated.id).taint_sources
    assert ctx.session is None  # no parent-session tools/context exposed to helper


def test_empty_native_search_is_metadata_not_a_third_party_read():
    from resource_librarian.access import result_access
    spec = ToolSpec('search', lambda ctx: {}, 'consult', 'read', Card('Search'))
    access = result_access(spec, {}, {'results': [], 'considered': 0}, Context())
    assert access['taint_sources'] == []


def test_unknown_internal_source_is_flagged_and_tainted_without_fabricating_authorship():
    from resource_librarian.access import result_access
    spec = ToolSpec('get_note', lambda ctx: {}, 'consult', 'read', Card('Read'))
    access = result_access(spec, {'name': 'unclassified'}, {'body': 'fixture'}, Context())
    assert access['sources'][0]['authorship'] is None
    assert access['sources'][0]['authorship_resolution'] == 'unclassified'
    assert access['taint_sources'] == ['unclassified']


def test_mixed_geo_unknown_graph_cannot_hide_behind_an_owned_graph():
    from resource_librarian.access import result_access
    spec = ToolSpec('geo', lambda ctx: {}, 'consult', 'read', Card('Geo'), external=True,
                    provenance_authority='geographer')
    access = result_access(spec, {}, {'graphs': [
        {'graph_id': 'own', 'authorship': 'owner_created'},
        {'graph_id': 'unknown', 'authorship': None, 'authorship_resolution': 'unclassified'}]}, Context())
    assert access['taint_sources'] == ['unknown']


def test_legacy_documentary_provenance_object_is_not_an_authorship_declaration():
    from resource_librarian.access import result_access
    spec = ToolSpec('geo', lambda ctx: {}, 'consult', 'read', Card('Geo'), external=True,
                    provenance_authority='geographer')
    access = result_access(spec, {}, {'cite_as': 'ref/doc:1',
        'provenance': {'coverage': 'legacy_unverified', 'source_path': 'fixture.md'}}, Context())
    assert access['taint_sources']


def test_real_application_record_stores_generated_text_and_sources_while_tainted(vault):
    from conftest import add_source
    from resource_librarian import notes
    add_source(vault.root, 'fixture', 'Synthetic fixture.', 'Synthetic use.')
    store = SessionStore(vault)
    session = store.new('apply', question='Fixture application')
    store.append(session.id, {'type': 'phase', 'to': 'check_out'})
    store.append(session.id, {'type': 'taint', 'sources': ['fixture-third-party']})
    ctx = Context(tier='contribute', vault=vault, session=session.id)
    out = REGISTRY.call('record_application', {'title': 'Fixture use', 'stage': 'tested',
        'outcome': 'recorded', 'sources_used': ['fixture'], 'needed': 'A fixture',
        'found_and_taken': 'A described use, not copied source code.', 'replaced': 'Nothing',
        'should_learn': 'Test provenance'}, ctx)
    assert 'error' not in out, out
    fm = notes.load(vault.root / out['recorded']).frontmatter
    assert fm['authorship'] == 'generated'
    assert fm['taint_sources'] == ['fixture-third-party']
    assert 'access' not in out  # use-log receipt is class C, not a content read


@pytest.mark.parametrize('tool,descriptor', [('read_url', {}), ('mcp__legacy__read', {}),
    ('read_url', {'contract_call': {'contract': 'C1', 'class': 'untrusted', 'untrusted': True, 'key': 'fixture'}})])
def test_resume_of_pre_s1_untrusted_calls_does_not_silently_drop_protection(vault, tool, descriptor):
    store = SessionStore(vault)
    session = store.new('explore')
    store.append(session.id, {'type': 'call', 'tool': tool, 'ok': True, 'effect': 'read',
                              'charged': False, 'args': {'url': 'fixture'}, **descriptor})
    assert store.load(session.id).taint_sources


def test_legacy_person_calls_remain_untainted(vault):
    store = SessionStore(vault)
    session = store.new('explore')
    store.append(session.id, {'type': 'call', 'tool': 'read_url', 'tier': 'curate',
                             'effect': 'read', 'ok': True, 'charged': False})
    assert not store.load(session.id).taint_sources
