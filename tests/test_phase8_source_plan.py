"""S4 source verification: reusable audited reads and a no-model dispatch path."""
import json

import jsonschema
import pytest

from resource_librarian import access, effort, tools  # noqa: F401
from resource_librarian.conversions import ConversionStore, file_sha256
from resource_librarian.registry import Context


def parameters():
    return dict(server='geo', graph_id='g-papers', document='doc:1', section_id=7,
                corpus_revision='corpus-1', source='Inbox/study.pdf', pages=[2],
                claim='Original target claim.')


def test_template_is_two_tier2_reads_or_one_tier1_read():
    from resource_librarian.source_verification import make_plan
    from resource_librarian.tools.plan_dispatch import _shape_problems, _plan_schema
    two = make_plan(**parameters(), tier=2)
    assert [t['tier'] for t in two['tasks']] == [2, 2]
    assert two['tasks'][1]['depends_on'] == [two['tasks'][0]['task_id']]
    assert two['source_verification']['macro'] == 'source_pages_to_claim_check'
    assert _shape_problems(two)[0] == []
    jsonschema.validate({'plan': two, 'dry_run': True}, _plan_schema())
    one = make_plan(**parameters(), tier=1)
    assert len(one['tasks']) == 1 and one['tasks'][0]['tier'] == 1


def test_tier3_and_unbounded_source_templates_are_refused():
    from resource_librarian.source_verification import make_plan
    with pytest.raises(ValueError, match='PLAN_SCOPE'):
        make_plan(**parameters(), tier=3)
    args = {**parameters(), 'pages': list(range(1, 10))}
    with pytest.raises(Exception, match='THIRD_PARTY_ROUTE_REQUIRED'):
        make_plan(**args, tier=2)


def test_page_macro_reuses_the_audited_evidence_to_claim_engine():
    from resource_librarian.agent_runtime import MACROS, _expanded_plan
    macro = MACROS['source_pages_to_claim_check']
    assert macro.write_capable is False
    plan = _expanded_plan(macro, {'source': 'Inbox/study.pdf', 'pages': [2], 'claim': 'Claim'})
    assert [s['tool'] for s in plan['steps']] == ['read_source_section', 'verify_source_pages']
    assert plan['steps'][1]['arguments']['pages'] == [2]


def test_profile_read_bundle_exposes_the_bounded_read_route():
    from resource_librarian.agent_runtime import DEFAULT_PROFILES, bundle_selection
    selection = bundle_selection('consult', 'frame', profile=DEFAULT_PROFILES['research_helper'])
    names = {s.name for s in selection.offered}
    assert {'read_source_section', 'verify_source_pages'} <= names


@pytest.mark.parametrize('phase', ['map', 'execute'])
def test_lead_can_prepare_a_source_plan_and_request_person_review(phase):
    from resource_librarian.agent_runtime import MAX_BUNDLE_TOOLS, bundle_selection
    names = {s.name for s in bundle_selection('contribute', phase).offered}
    assert {'source_verification_plan', 'request_raw_source_access', 'dispatch_plan', 'read_result', 'macro_run'} <= names
    assert len(names) <= MAX_BUNDLE_TOOLS


@pytest.fixture
def source_world(vault, monkeypatch):
    from conftest import pdf_bytes
    from resource_librarian.tools import plan_dispatch as pd
    pdf = vault.root / 'Inbox/study.pdf'
    pdf.write_bytes(pdf_bytes([['Page one must not be sent.'], ['Original target claim.'], ['Page three must not be sent.']]))
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    store = ConversionStore(vault)
    store.save(store.request(pdf, 'scripted-anchored'),
        '[page 1]\nPage one must not be sent.\n\n[page 2]\nOriginal target claim.\n\n[page 3]\nPage three must not be sent.', pages=3)
    class Mcp:
        def status(self):return {'geo': {'enabled': True, 'accepted': True, 'connected': True}}
        def tool_names(self, server):return ['mcp__geo__list_graphs', 'mcp__geo__paper_get_section']
    route = {'model': 'scripted-helper', 'context_tokens': 262144, 'prompt_tokens': 1000,
             'visible_output_tokens': 4096, 'reasoning_reserve_tokens': 0}
    ctx = Context(tier='contribute', vault=vault, extras={'mcp': Mcp(), 'effort': effort.profile(1),
        'read_route': route, 'helper_read_route': lambda tier: dict(route)})
    state = {'source_sha256': file_sha256(pdf), 'revision': 'corpus-1'}
    external, dispatched = [], []
    def call(ctx, server, tool, args):
        external.append((tool, args))
        if tool == 'list_graphs':
            return {'graphs': [{'graph_id': 'g-papers', 'snapshot_id': 'code-head-1', 'provenance': 'third_party'}]}
        assert tool == 'paper_get_section'
        return {'graph_id': 'g-papers', 'result': {'section_id': 7, 'text': 'Original target claim.',
            'context': {'corpus_revision': state['revision']},
            'provenance': {'source_path': str(pdf.resolve()), 'source_sha256': state['source_sha256'],
                           'location': {'page_start': 2, 'page_end': 2}}}}
    monkeypatch.setattr(pd, '_call_external', call)
    def run(ctx, tier, packet):
        dispatched.append(packet)
        encoded = json.dumps(packet)
        assert 'Page one must not be sent.' not in encoded
        assert 'Page three must not be sent.' not in encoded
        return {'inputs': [], 'outputs': [], 'calls': [],
            'claims': [{'text': 'External reference: original target claim.', 'cite': packet['handles'][0]}],
            'not_determinable': []}, {'model': 'scripted-helper', 'steps': 0}
    monkeypatch.setattr(pd, '_run_task', run)
    return pd, ctx, state, external, dispatched


def test_flat_source_plan_fills_revision_and_page_targets_from_graph(source_world):
    from resource_librarian.tools.source_reading import source_verification_plan
    _, ctx, _, external, dispatched = source_world
    out = source_verification_plan(ctx, source='Inbox/study.pdf', claim='Original target claim.',
                                   graph_id='g-papers', document='doc:1', section_id=7)
    assert out['plan']['source_verification']['pages'] == [2]
    assert out['plan']['source_verification']['corpus_revision'] == 'corpus-1'
    assert out['plan']['server'] == 'geo'
    assert not dispatched
    assert [name for name, _ in external] == ['paper_get_section']


def test_source_plan_does_not_guess_between_servers(source_world):
    from resource_librarian.tools.source_reading import source_verification_plan
    _, ctx, _, _, dispatched = source_world
    ctx.extras['mcp'].status = lambda: {s: dict(enabled=True, accepted=True, connected=True) for s in ['geo', 'other']}
    ctx.extras['mcp'].tool_names = lambda s: [f'mcp__{s}__paper_get_section']
    with pytest.raises(ValueError, match='name one accepted server'):
        source_verification_plan(ctx, source='Inbox/study.pdf', claim='Claim',
                                 graph_id='g-papers', document='doc:1', section_id=7)
    assert not dispatched


def test_source_plan_dry_run_has_zero_model_dispatches(source_world):
    from resource_librarian.source_verification import make_plan
    pd, ctx, _, external, dispatched = source_world
    out = pd.dispatch_plan(ctx, make_plan(**parameters(), tier=2), dry_run=True)
    assert out['dry_run'] is True
    assert [r['state'] for r in out['results'].values()] == ['planned', 'planned']
    assert not dispatched
    assert any(name == 'paper_get_section' for name, _ in external)


def test_source_plan_checks_both_representations_with_real_page_targets(source_world):
    from resource_librarian.source_verification import make_plan
    pd, ctx, _, _, dispatched = source_world
    out = pd.dispatch_plan(ctx, make_plan(**parameters(), tier=2))
    assert all(r['state'] == 'ok' for r in out['results'].values()), out
    assert len(dispatched) == 2
    assert {p['source_reading']['representation'] for p in dispatched} == {'conversion', 'original'}
    assert all(p['source_reading']['pages'] == [2] for p in dispatched)
    assert all(r['verification']['closure_strength'] == 'bounded' for r in out['results'].values())


@pytest.mark.parametrize('change', ['source_sha256', 'revision'])
def test_wrong_or_stale_graph_source_stops_before_model_dispatch(source_world, change):
    from resource_librarian.source_verification import make_plan
    pd, ctx, state, _, dispatched = source_world
    state[change] = '0' * 64 if change == 'source_sha256' else 'different-revision'
    out = pd.dispatch_plan(ctx, make_plan(**parameters(), tier=2))
    assert not dispatched
    assert any(r['state'] == 'failed' for r in out['results'].values()), out


def test_comparison_splits_one_route_allocation_between_representations(source_world):
    from resource_librarian.source_verification import make_plan
    pd, ctx, _, _, _ = source_world
    ctx.extras['helper_read_route'] = lambda tier: dict(model='small-route', context_tokens=16000,
        prompt_tokens=1000, visible_output_tokens=1800, reasoning_reserve_tokens=1024)
    out = pd.dispatch_plan(ctx, make_plan(**parameters(), tier=1), dry_run=True)
    reads = out['results']['both']['read_allocation']
    assert sum(r['allocation']['effective_tokens'] for r in reads) <= 16000 - 1800 - 1024 - 1000


def test_text_empty_original_page_is_not_sent_as_verification_evidence(source_world, monkeypatch):
    from resource_librarian.source_verification import make_plan
    from pypdf._page import PageObject
    pd, ctx, _, _, dispatched = source_world
    monkeypatch.setattr(PageObject, 'extract_text', lambda self: '')
    out = pd.dispatch_plan(ctx, make_plan(**parameters(), tier=1))
    assert not dispatched
    assert 'no usable text' in out['results']['both']['error']
