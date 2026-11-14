import pytest
from test_plan_dispatch import world, plan, task


def test_third_party_clerk_task_refused_before_any_packet_or_model(world, monkeypatch):
    pd, ctx, calls = world
    original = pd._call_external
    def external(ctx, server, name, arguments):
        if name == 'list_graphs':
            return {'graphs': [{'graph_id': 'g1', 'stratum': {'role': 'third_party'}}]}
        return original(ctx, server, name, arguments)
    monkeypatch.setattr(pd, '_call_external', external)
    monkeypatch.setattr(pd, '_run_task', lambda *a: pytest.fail('model called'))
    with pytest.raises(ValueError, match='PLAN_SCOPE.*t1'):
        pd.dispatch_plan(ctx, plan())
    assert calls == []


def test_current_system_claim_from_external_reference_is_flagged():
    from resource_librarian.packet_checks import verify_citations
    packet = {'provenance': 'third_party', 'handles': ['upstream/entity:x']}
    answer = dict(inputs=[], outputs=[], calls=[], not_determinable=[],
                  claims=[{'text': 'Our current system uses this implementation.', 'cite': 'upstream/entity:x'}])
    checked = verify_citations(answer, packet)
    assert checked['closure_strength'] == 'none'
    assert checked['provenance_errors'] == ['claims[0]: THIRD_PARTY_AS_CURRENT_SYSTEM']


def test_final_loop_answer_flags_external_current_system_claim_without_model_retry(vault, monkeypatch):
    from resource_librarian.loop import Loop
    from resource_librarian.providers import Scripted, Reply, ToolCall
    calls = []; events = []
    def respond(*args):
        calls.append(1)
        return Reply(tool_calls=[ToolCall('one', 'vault_status', {})]) if len(calls) == 1 else Reply(
            text='Our current system uses this implementation [upstream/entity:x].')
    loop = Loop(vault, Scripted(respond), scribe=None, extras={'use_tool_bundles': False}, on_event=events.append)
    monkeypatch.setattr(loop, 'call', lambda *a: {'provenance': 'third_party', 'cite_as': 'upstream/entity:x'})
    result = loop.send('Describe our system.')
    assert 'Source scope warning' in result.reply
    assert any(e['type'] == 'source_scope_warning' for e in events)
    assert len(calls) == 2
