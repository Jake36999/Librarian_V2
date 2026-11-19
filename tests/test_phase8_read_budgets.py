"""S4 route budgets: token units, actual windows, visible/reasoning reserves."""
import pytest

from resource_librarian.registry import Context, REGISTRY
from resource_librarian import access, text, tools  # noqa: F401


def test_comparison_is_clamped_to_actual_route_not_owner_intent():
    from resource_librarian.read_access import allocate
    out = allocate({'model': 'fixture-qwen', 'context_tokens': 262144,
        'prompt_tokens': 10000, 'visible_output_tokens': 1800, 'reasoning_reserve_tokens': 1024},
        requested_tokens=400000, sources=2)
    assert out['unit'] == 'tokens'
    assert out['effective_tokens'] == 249320
    assert out['per_source_tokens'] == [124660, 124660]
    assert out['clamped'] is True


def test_tier3_output_is_a_separate_binding_limit():
    from resource_librarian.read_access import allocate
    from resource_librarian.rules import Refusal
    with pytest.raises(Refusal, match='TASK_OUTPUT_TOO_LARGE'):
        allocate({'model': 'fixture-clerk', 'context_tokens': 262144,
                  'prompt_tokens': 1000, 'visible_output_tokens': 1800,
                  'reasoning_reserve_tokens': 1024}, requested_tokens=200000,
                 expected_output_tokens=1801, tier=3)


def test_unknown_actual_route_cannot_claim_a_large_read_budget():
    from resource_librarian.read_access import allocate
    from resource_librarian.rules import Refusal
    with pytest.raises(Refusal, match='READ_ROUTE_REQUIRED'):
        allocate({}, requested_tokens=200000)


def test_measured_byte_bound_does_not_assume_unicode_has_four_characters_per_token():
    from resource_librarian.read_access import measure
    assert measure('漢字') >= 6


@pytest.mark.parametrize('person,authorship', [(True, 'third_party'), (False, 'third_party'), (False, 'owner_created')])
def test_person_and_own_raw_access_remain_allowed(vault, monkeypatch, person, authorship):
    path = vault.root / 'Inbox/document.pdf'
    path.write_bytes(b'fixture')
    monkeypatch.setattr(access, '_native_authorship', lambda *args: authorship)
    monkeypatch.setattr(text, 'extract', lambda *args: text.Extraction(pages=['Original text.']))
    out = REGISTRY.call('read_file', {'path': 'Inbox/document.pdf'},
        Context(vault=vault, extras={'caller_kind': 'person'} if person else {}))
    assert out['text'] == 'Original text.'


def test_page_verification_reads_only_named_original_pages_without_ocr(vault, monkeypatch):
    from conftest import pdf_bytes
    path = vault.root / 'Inbox/study.pdf'
    path.write_bytes(pdf_bytes([['Page one unrelated.'], ['A claim on page two.'], ['Page three unrelated.']]))
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    ctx = Context(vault=vault, extras={'read_route': {'model': 'fixture-route',
        'context_tokens': 8192, 'prompt_tokens': 1000, 'visible_output_tokens': 1800,
        'reasoning_reserve_tokens': 1024}})
    out = REGISTRY.call('verify_source_pages', {'source': 'Inbox/study.pdf', 'pages': [2],
                                              'claim': 'A claim on page two.'}, ctx)
    assert 'error' not in out, out
    assert [p['page'] for p in out['pages']] == [2]
    assert out['pages'][0]['text'].strip() == 'A claim on page two.'
    assert out['claim_verification'] == 'not_performed'
    assert out['original_pages_read'] is True
    assert out['allocation']['effective_tokens'] <= 4368
    assert out['authorship'] == 'third_party'


def test_bounded_source_section_uses_cached_conversion_not_another_extraction(vault, monkeypatch):
    from resource_librarian.conversions import ConversionStore
    path = vault.root / 'Inbox/study.pdf'
    path.write_bytes(b'fixture original')
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    store = ConversionStore(vault)
    store.save(store.request(path, 'scripted'), '[page 1]\nFirst.\n\n[page 2]\nSelected.', pages=2)
    monkeypatch.setattr(text, 'extract', lambda *args: pytest.fail('No per-access extraction or OCR'))
    ctx = Context(vault=vault, extras={'read_route': {'model': 'fixture-route',
        'context_tokens': 8192, 'prompt_tokens': 1000, 'visible_output_tokens': 1800,
        'reasoning_reserve_tokens': 1024}, 'agent_tier': 3})
    out = REGISTRY.call('read_source_section', {'source': 'Inbox/study.pdf', 'pages': [2]}, ctx)
    assert 'error' not in out, out
    assert out['pages'] == [{'page': 2, 'text': 'Selected.', 'truncated': False}]
    assert out['authorship'] == 'generated'
    assert out['source_authorship'] == 'third_party'
    assert out['primary_source'] is False


def test_no_whole_document_or_oversized_page_targets(vault):
    out = REGISTRY.call('verify_source_pages', {'source': 'Inbox/study.pdf',
        'pages': list(range(1, 10)), 'claim': 'Claim'}, Context(vault=vault))
    assert out.get('refused') == 'THIRD_PARTY_ROUTE_REQUIRED', out


@pytest.fixture
def raw_grant(vault, monkeypatch):
    from resource_librarian.session import SessionStore
    from resource_librarian.checkpoints import CheckpointStore
    path = vault.root / 'Inbox/external.txt'
    path.write_text('Third-party source.', encoding='utf-8')
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    sid = SessionStore(vault).new('explore', question='Read a reference').id
    ctx = Context(tier='contribute', vault=vault, session=sid, extras={'agent_tier': 2,
        'read_route': {'model': 'fixture-helper', 'context_tokens': 262144,
                       'prompt_tokens': 1000, 'visible_output_tokens': 4096, 'reasoning_reserve_tokens': 0}})
    request = REGISTRY.call('request_raw_source_access', {'tool_name': 'read_file',
        'arguments': {'path': 'Inbox/external.txt'}}, ctx)
    assert 'error' not in request, request
    return ctx, request['checkpoint'], CheckpointStore(vault)


def test_person_approved_raw_grant_is_one_call_and_does_not_clear_taint(raw_grant):
    from resource_librarian.session import SessionStore
    ctx, checkpoint, store = raw_grant
    denied = REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, ctx)
    assert denied['refused'] == 'THIRD_PARTY_ROUTE_REQUIRED'
    store.resolve(checkpoint['id'], 'approve')  # scripted person action, no model/network
    out = REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, ctx)
    assert out['text'] == 'Third-party source.', out
    again = REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, ctx)
    assert again['refused'] == 'THIRD_PARTY_ROUTE_REQUIRED'
    assert SessionStore(ctx.vault).load(ctx.session).taint_sources


def test_raw_grant_is_bound_to_source_bytes_and_actual_route(raw_grant):
    ctx, checkpoint, store = raw_grant
    store.resolve(checkpoint['id'], 'approve')
    ctx.extras['read_route']['model'] = 'different-model'
    assert REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, ctx)['refused'] == 'THIRD_PARTY_ROUTE_REQUIRED'
    ctx.extras['read_route']['model'] = 'fixture-helper'
    (ctx.vault.root / 'Inbox/external.txt').write_text('Changed source.', encoding='utf-8')
    assert REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, ctx)['refused'] == 'THIRD_PARTY_ROUTE_REQUIRED'


def test_tier3_cannot_request_a_raw_grant(raw_grant):
    ctx, _, _ = raw_grant
    ctx.extras['agent_tier'] = 3
    out = REGISTRY.call('request_raw_source_access', {'tool_name': 'read_file',
        'arguments': {'path': 'Inbox/external.txt'}}, ctx)
    assert out['refused'] == 'THIRD_PARTY_ROUTE_REQUIRED'


def test_requesting_permission_does_not_itself_read_or_taint(raw_grant):
    from resource_librarian.session import SessionStore
    ctx, _, _ = raw_grant
    assert not SessionStore(ctx.vault).load(ctx.session).taint_sources


def test_one_raw_grant_cannot_be_spent_twice_by_concurrent_calls(raw_grant):
    from concurrent.futures import ThreadPoolExecutor
    ctx, checkpoint, store = raw_grant
    store.resolve(checkpoint['id'], 'approve')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, ctx), range(2)))
    assert sum(r.get('text') == 'Third-party source.' for r in results) == 1, results
    assert sum(r.get('refused') == 'THIRD_PARTY_ROUTE_REQUIRED' for r in results) == 1, results


def test_profile_cannot_inflate_the_actual_routes_declared_window():
    from resource_librarian.app import App
    from types import SimpleNamespace
    app = SimpleNamespace(_route_catalogue_entry=lambda route: {'context_length': 262144})
    profile = SimpleNamespace(route_policy={'context_tokens': 1048576})
    assert App._route_context_limit(app, {'model': 'fixture-helper'}, profile) == 262144


def test_loop_records_the_actual_prompt_and_both_output_reserves(vault):
    from resource_librarian.loop import Loop
    from types import SimpleNamespace
    provider = SimpleNamespace(name='fixture-provider', model='fixture-model')
    loop = Loop(vault, provider, tier='consult')
    loop.context_limit = 262144
    loop.profile_output_budget = 1800
    runtime = SimpleNamespace(output_headroom_tokens=lambda p: 1024)
    loop._capture_read_route(provider, runtime, 'System', [{'role': 'user', 'content': '漢字'}], [])
    route = loop.ctx.extras['read_route']
    assert route['model'] == 'fixture-model'
    assert route['context_tokens'] == 262144
    assert route['prompt_tokens'] >= 6
    assert route['visible_output_tokens'] == 1800
    assert route['reasoning_reserve_tokens'] == 1024


def test_helper_loop_uses_its_own_resolved_route_window(vault, monkeypatch):
    from test_agent_runtime_profiles import CaptureProvider
    from resource_librarian.loop import Loop
    from resource_librarian import effort
    limits = []
    original = Loop._capture_read_route
    def captured(self, *args):
        original(self, *args)
        limits.append((self.ctx.extras.get('agent_tier'), self.ctx.extras['read_route']['context_tokens']))
    monkeypatch.setattr(Loop, '_capture_read_route', captured)
    ctx = Context(tier='contribute', vault=vault, extras={'effort': effort.profile(1),
        'agent_provider': lambda tier: CaptureProvider(),
        'helper_read_route': lambda tier: {'context_tokens': 32768, 'model': 'fixture-helper'}})
    result = REGISTRY.call('delegate', {'questions': ['Read a catalogue card'], 'tier': 2}, ctx)
    assert result['results'][0]['answer'] == 'bounded reply', result
    assert limits == [(2, 32768)]


def test_unclassified_original_page_read_taints_publication(vault, monkeypatch):
    from conftest import pdf_bytes
    from resource_librarian.session import SessionStore
    path = vault.root / 'Inbox/unknown.pdf'
    path.write_bytes(pdf_bytes([['Unknown original.']]))
    monkeypatch.setattr(access, '_native_authorship', lambda *args: None)
    sid = SessionStore(vault).new('explore', question='Read reference').id
    ctx = Context(vault=vault, session=sid, extras={'read_route': {'model': 'fixture',
        'context_tokens': 8192, 'prompt_tokens': 500, 'visible_output_tokens': 1800, 'reasoning_reserve_tokens': 0}})
    out = REGISTRY.call('verify_source_pages', {'source': 'Inbox/unknown.pdf', 'pages': [1], 'claim': 'Unknown'}, ctx)
    assert 'error' not in out, out
    assert out['access']['taint_sources']
    assert SessionStore(vault).load(sid).taint_sources


def test_sessionless_helper_can_consume_its_parent_scoped_read_grant(raw_grant):
    from dataclasses import replace
    ctx, checkpoint, store = raw_grant
    store.resolve(checkpoint['id'], 'approve')
    helper = replace(ctx, tier='consult', session=None,
                     extras={**ctx.extras, '_publication_session': ctx.session, 'caller': 'research_helper'})
    out = REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, helper)
    assert out.get('text') == 'Third-party source.', out
    assert REGISTRY.call('read_file', {'path': 'Inbox/external.txt'}, helper)['refused'] == 'THIRD_PARTY_ROUTE_REQUIRED'


def test_lead_can_request_person_review_for_the_actual_helper_route(raw_grant):
    ctx, _, store = raw_grant
    ctx.extras['agent_tier'] = 1
    ctx.extras['read_route']['model'] = 'fixture-lead'
    ctx.extras['helper_read_route'] = lambda tier: {'model': 'fixture-helper', 'context_tokens': 262144}
    out = REGISTRY.call('request_raw_source_access', {'tool_name': 'read_file',
        'arguments': {'path': 'Inbox/external.txt'}, 'recipient_tier': 2}, ctx)
    assert 'error' not in out, out
    evidence = out['checkpoint']['evidence']
    assert evidence['tier'] == 2 and evidence['model'] == 'fixture-helper'
    assert evidence['allocation_at_read'] == 'pending measured recipient prompt'


def code_packet(anchors):
    return {'packet_version': 'task-packet-v1', 'instruction': 'Describe bounded inputs and outputs.',
            'anchors': [{'ref': 'entity:' + str(i), 'cite_as': 'g/entity:' + str(i), 'text': 'def f(x): return x'}
                        for i in range(anchors)], 'boundary': [], 'upstream': []}


def test_clerk_packet_is_sized_by_output_before_any_dispatch(monkeypatch):
    from resource_librarian.tools.plan_dispatch import _run_task
    from resource_librarian.tools import staging
    from resource_librarian import clerk
    from resource_librarian.rules import Refusal
    from types import SimpleNamespace
    endpoint = SimpleNamespace(read_route={'model': 'fixture-clerk', 'context_tokens': 262144,
        'visible_output_tokens': 1800, 'reasoning_reserve_tokens': 1024})
    monkeypatch.setattr(staging, 'clerk_endpoint', lambda ctx: endpoint)
    monkeypatch.setattr(clerk, 'run', lambda *args: pytest.fail('Oversized output must stop before a model call'))
    with pytest.raises(Refusal, match='TASK_OUTPUT_TOO_LARGE'):
        _run_task(Context(), 3, code_packet(8))


def test_clerk_packet_reports_actual_effective_allocations(monkeypatch):
    from resource_librarian.tools.plan_dispatch import _run_task
    from resource_librarian.tools import staging
    from resource_librarian import clerk
    from types import SimpleNamespace
    endpoint = SimpleNamespace(read_route={'model': 'fixture-clerk', 'context_tokens': 262144,
        'visible_output_tokens': 1800, 'reasoning_reserve_tokens': 1024})
    monkeypatch.setattr(staging, 'clerk_endpoint', lambda ctx: endpoint)
    result = SimpleNamespace(ok=True, value={}, to_dict=lambda: {'model': 'fixture-clerk', 'value': {}})
    monkeypatch.setattr(clerk, 'run', lambda *args: [result])
    _, receipt = _run_task(Context(), 3, code_packet(1))
    budget = receipt['read_allocation']
    assert budget['visible_output_tokens'] == 1800
    assert budget['reasoning_reserve_tokens'] == 1024
    assert budget['prompt_tokens'] > 0
    assert budget['expected_output_tokens'] <= 1800


def test_deep_read_cannot_bypass_the_located_section_route(vault, monkeypatch):
    from resource_librarian.staging import StagingStore
    from resource_librarian.read_access import guard
    from resource_librarian.rules import Refusal
    StagingStore(vault).add({'id': 'external-study', 'kind': 'source', 'name': 'Study',
        'source_kind': 'paper', 'file': 'Inbox/study.pdf'})
    (vault.root / 'Inbox/study.pdf').write_bytes(b'fixture')
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('deep_read'), {'item_id': 'external-study'}, Context(vault=vault))


def test_bounded_pages_also_keep_the_existing_per_call_character_cap(vault):
    from resource_librarian.read_access import project_pages
    from resource_librarian.mcp_client import external_result_limit
    import json
    ctx = Context(vault=vault, extras={'read_route': {'model': 'fixture',
        'context_tokens': 262144, 'prompt_tokens': 1000,
        'visible_output_tokens': 1800, 'reasoning_reserve_tokens': 1024}})
    out = project_pages(ctx, [(1, 'x' * 100000)], source='fixture.pdf')
    assert out['truncated'] is True
    assert out['omissions']
    assert len(json.dumps(out)) <= external_result_limit(262144)


def test_person_granted_raw_read_still_obeys_the_actual_per_call_cap(raw_grant):
    import json
    from resource_librarian.mcp_client import external_result_limit
    ctx, _, store = raw_grant
    (ctx.vault.root / 'Inbox/external.txt').write_text('x' * 100000, encoding='utf-8')
    args = {'path': 'Inbox/external.txt', 'max_chars': 60000}
    request = REGISTRY.call('request_raw_source_access', {'tool_name': 'read_file', 'arguments': args}, ctx)
    store.resolve(request['checkpoint']['id'], 'approve')
    result = REGISTRY.call('read_file', args, ctx)
    assert 'error' not in result, result
    assert result['truncated']
    assert len(json.dumps(result)) <= external_result_limit(262144)


def test_person_started_ingestion_can_process_its_bound_item_but_not_other_items(vault, monkeypatch):
    from resource_librarian.staging import StagingStore
    from resource_librarian.read_access import guard
    from resource_librarian.rules import Refusal
    store = StagingStore(vault)
    store.add({'id': 'approved-study', 'kind': 'source', 'name': 'Study',
               'source_kind': 'paper', 'file': 'Inbox/study.pdf',
               'status': 'processing', 'batch': 'person-started-batch'})
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    ctx = Context(vault=vault, extras={'_batch_run': 'person-started-batch'})
    assert guard(REGISTRY.get('deep_read'), {'item_id': 'approved-study'}, ctx) is None
    ctx.extras['_batch_run'] = 'different-batch'
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('deep_read'), {'item_id': 'approved-study'}, ctx)


def test_get_note_cannot_turn_a_third_party_original_into_a_catalogue_entry(vault):
    from conftest import write_note
    write_note(vault.root, 'Notes/External.md', 'type: note\nauthorship: third_party',
               '# External\n\n## Body\nOriginal third-party prose.\n')
    out = REGISTRY.call('get_note', {'name': 'External'}, Context(vault=vault))
    assert out.get('refused') == 'THIRD_PARTY_ROUTE_REQUIRED', out


def test_get_note_keeps_the_third_party_catalogue_entry_available(vault):
    from conftest import add_source
    add_source(vault.root, 'External catalogue', 'Generated catalogue summary.',
               extra_fm='authorship: third_party')
    out = REGISTRY.call('get_note', {'name': 'External catalogue'}, Context(vault=vault))
    assert out.get('found') is True, out


def test_agent_can_read_exact_person_referenced_pdf_outside_roots(vault, tmp_path, monkeypatch):
    external = tmp_path / "person sample.pdf"
    external.write_bytes(b"fixture")
    ctx = Context(vault=vault, extras={"_person_pdf_messages": [f'Read "{external}".']})
    monkeypatch.setattr(text, "extract", lambda *args: text.Extraction(pages=["Referenced text"]))
    result = REGISTRY.call("read_file", {"path": str(external)}, ctx)
    assert result.get("text") == "Referenced text", result
    ctx.extras["_person_pdf_messages"] = [f'Read "{external}.bak".']
    assert "error" in REGISTRY.call("read_file", {"path": str(external)}, ctx)


def test_a_person_started_shipped_read_workflow_may_deep_read(vault, monkeypatch):
    """WF-D3: deep-read-staged started from the paperclip was refused on every third-party
    source. The Core's workflow grant for a person's start is that person's route; a context
    without it (an agent's own call) is still refused."""
    from resource_librarian.staging import StagingStore
    from resource_librarian.read_access import guard
    from resource_librarian.rules import Refusal
    StagingStore(vault).add({'id': 'staged-study', 'kind': 'source', 'name': 'Study',
                             'source_kind': 'paper', 'file': 'Inbox/study.pdf', 'status': 'staged'})
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    granted = Context(tier='contribute', vault=vault, extras={
        'workflow_grant': {'label': 'deep-read-staged workflow', 'tools': frozenset({'deep_read'})}})
    assert guard(REGISTRY.get('deep_read'), {'item_id': 'staged-study'}, granted) is None
    other = Context(tier='contribute', vault=vault, extras={
        'workflow_grant': {'label': 'review-due workflow', 'tools': frozenset({'review_due_open'})}})
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('deep_read'), {'item_id': 'staged-study'}, other)
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('deep_read'), {'item_id': 'staged-study'},
              Context(tier='contribute', vault=vault))
