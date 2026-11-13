"""The tool-step budget ends with one guarded, tool-free synthesis request."""
import threading

from resource_librarian.loop import Loop
from resource_librarian.providers import ProviderError, Reply, Scripted, ToolCall


def test_step_limit_answers_from_existing_evidence_without_more_tools(vault):
    seen = []
    events = []
    def respond(system, messages, tools):
        seen.append((system, list(messages), list(tools)))
        if tools:
            return Reply(tool_calls=[ToolCall(str(len(seen)), 'vault_status', {})])
        assert any(m['role'] == 'tool' for m in messages)
        assert 'evidence' in system.lower() and 'missing' in system.lower()
        return Reply(text='The gathered status is available; supporting sources are missing.')
    loop = Loop(vault, Scripted(respond), max_steps=2, scribe=None,
                extras={'use_tool_bundles': False}, on_event=events.append)
    turn = loop.send('Summarise what can be established.')
    assert turn.reply and turn.completed_at_step_limit is True
    assert turn.steps == 2 and len(turn.calls) == 2
    assert len(seen) == 3 and seen[-1][2] == []
    assert turn.to_dict()['completed_at_step_limit'] is True
    assert sum(e['type'] == 'tool_call' for e in events) == 2


def test_final_call_cannot_execute_another_tool(vault):
    seen = []
    def respond(system, messages, tools):
        seen.append(list(tools))
        return Reply(tool_calls=[ToolCall(str(len(seen)), 'vault_status', {})])
    loop = Loop(vault, Scripted(respond), max_steps=1, scribe=None,
                extras={'use_tool_bundles': False})
    turn = loop.send('Read status.')
    assert len(seen) == 2 and seen[-1] == []
    assert len(turn.calls) == 1 and turn.steps == 1
    assert turn.stopped == 'max_steps' and not turn.completed_at_step_limit
    assert loop.messages[-1]['role'] == 'tool'
    assert not any(c.get('id') == '2' for m in loop.messages for c in m.get('tool_calls', []))


def test_cancelled_after_last_tool_does_not_dispatch_synthesis(vault):
    cancel = threading.Event()
    count = []
    def respond(*args):
        count.append(1)
        return Reply(tool_calls=[ToolCall('one', 'vault_status', {})])
    def event(value):
        if value['type'] == 'tool_result':
            cancel.set()
    loop = Loop(vault, Scripted(respond), max_steps=1, scribe=None,
                extras={'use_tool_bundles': False}, on_event=event)
    turn = loop.send('Read status.', cancel=cancel)
    assert turn.stopped == 'cancelled' and len(count) == 1


def test_final_synthesis_failure_is_not_marked_completed(vault):
    count = []
    def respond(system, messages, tools):
        count.append(1)
        if not tools:
            raise ProviderError('offline')
        return Reply(tool_calls=[ToolCall('one', 'vault_status', {})])
    loop = Loop(vault, Scripted(respond), max_steps=1, scribe=None,
                extras={'use_tool_bundles': False})
    turn = loop.send('Read status.')
    assert turn.stopped == 'provider_error' and not turn.completed_at_step_limit
    assert len(count) == 2


def test_final_call_keeps_profile_budget_guard(vault):
    count = []
    def respond(*args):
        count.append(1)
        return Reply(tool_calls=[ToolCall('one', 'vault_status', {})])
    def event(value):
        if value['type'] == 'tool_result':
            loop.profile_token_budget = loop._turn_reserved_tokens
    loop = Loop(vault, Scripted(respond), max_steps=1, scribe=None,
                extras={'use_tool_bundles': False}, on_event=event)
    turn = loop.send('Read status.')
    assert turn.stopped == 'profile_budget' and len(count) == 1
    assert not turn.completed_at_step_limit


def test_effort_reducing_limit_below_current_step_still_gets_one_answer(vault):
    count = []
    def respond(system, messages, tools):
        count.append(1)
        return Reply(tool_calls=[ToolCall(str(len(count)), 'vault_status', {})]) if tools else Reply(text='Partial evidence only.')
    def event(value):
        if value['type'] == 'tool_result' and len(count) == 2:
            loop.max_steps = 1
    loop = Loop(vault, Scripted(respond), max_steps=3, scribe=None,
                extras={'use_tool_bundles': False}, on_event=event)
    turn = loop.send('Read status.')
    assert turn.completed_at_step_limit and turn.reply == 'Partial evidence only.'
    assert turn.steps == 2 and len(turn.calls) == 2 and len(count) == 3


def test_blank_synthesis_is_not_a_completed_answer(vault):
    provider = Scripted(lambda system, messages, tools:
        Reply(tool_calls=[ToolCall('one', 'vault_status', {})]) if tools else Reply(text='  \n'))
    turn = Loop(vault, provider, max_steps=1, scribe=None,
                extras={'use_tool_bundles': False}).send('Read status.')
    assert not turn.completed_at_step_limit
