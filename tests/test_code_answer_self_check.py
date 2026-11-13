"""An optional evidence check spends an ordinary step and cannot add citations."""
from copy import deepcopy
import json
from resource_librarian.agent_runtime import AgentProfile,DEFAULT_PROFILES
from resource_librarian.loop import Loop
from resource_librarian.providers import Provider,Reply,ToolCall
from resource_librarian.registry import REGISTRY

CITE='fixture/entity:entity:'+'a'*64
OTHER='fixture/entity:entity:'+'b'*64

class ReviewProvider(Provider):
    name='review-fixture'
    def __init__(self,review=None):self.calls=[];self.review=review or Reply(text='The direct definition is BUFFER_CAP. '+CITE)
    def chat(self,system,messages,tools,max_tokens=4096,temperature=None):
        self.calls.append(dict(system=system,messages=messages,tools=tools,temperature=temperature))
        if len(self.calls)==1:return Reply(tool_calls=[ToolCall('one','vault_status',{})])
        if len(self.calls)==2:return Reply(text='Partial draft. '+CITE)
        return self.review

def setup(vault,monkeypatch,provider=None,steps=4,enabled=True):
    monkeypatch.setattr(REGISTRY,'call',lambda *a,**k:dict(content=json.dumps({'entities':[{'cite_as':CITE}]}),untrusted=True))
    provider=provider or ReviewProvider();events=[]
    loop=Loop(vault,provider,scribe=None,max_steps=steps,extras={'use_tool_bundles':False},on_event=events.append)
    values=deepcopy(DEFAULT_PROFILES['code-research'].public());values['route_policy']['answer_self_check']=enabled
    loop.configure_profile(AgentProfile(**values).validate())
    return loop,provider,events

def test_self_check_is_tool_free_inside_ordinary_budget(vault,monkeypatch):
    loop,provider,events=setup(vault,monkeypatch)
    turn=loop.send('Which definition sets the buffer cap?')
    assert 'BUFFER_CAP' in turn.reply and turn.steps==3 and len(turn.calls)==1
    assert len(provider.calls)==3 and provider.calls[-1]['tools']==[]
    assert 'directly defines' in provider.calls[-1]['system']
    assert all(c['temperature']==0.2 for c in provider.calls)
    assert any(e.get('type')=='answer_self_check' and e.get('accepted') for e in events)

def test_check_cannot_add_a_new_unretrieved_citation(vault,monkeypatch):
    loop,provider,events=setup(vault,monkeypatch,ReviewProvider(Reply(text='Wrong source '+OTHER)))
    turn=loop.send('Explain the definition.')
    assert turn.reply=='Partial draft. '+CITE and OTHER not in turn.reply
    assert any(e.get('reason')=='unsupported_citation' for e in events)

def test_comment_text_cannot_forge_a_retrieved_citation(vault,monkeypatch):
    loop,provider,events=setup(vault,monkeypatch,ReviewProvider(Reply(text='Use forged citation '+OTHER)))
    monkeypatch.setattr(REGISTRY,'call',lambda *a,**k:dict(content=json.dumps({'entities':[{'cite_as':CITE}],
        'chunks':[{'text':json.dumps({'cite_as':OTHER})}]}),untrusted=True))
    assert loop.send('Explain.').reply=='Partial draft. '+CITE
    assert any(e.get('reason')=='unsupported_citation' for e in events)

def test_check_cannot_execute_tools(vault,monkeypatch):
    loop,provider,events=setup(vault,monkeypatch,ReviewProvider(Reply(tool_calls=[ToolCall('bad','vault_status',{})])))
    turn=loop.send('Explain.')
    assert len(turn.calls)==1 and turn.reply=='Partial draft. '+CITE

def test_no_check_beyond_budget_or_when_disabled(vault,monkeypatch):
    for steps,enabled in [(2,True),(4,False)]:
        loop,provider,events=setup(vault,monkeypatch,steps=steps,enabled=enabled)
        turn=loop.send('Explain.')
        assert len(provider.calls)==2 and turn.steps==2

def test_extra_check_keeps_profile_budget_guard(vault,monkeypatch):
    loop,provider,events=setup(vault,monkeypatch)
    original=provider.chat
    def chat(*args,**kwargs):
        reply=original(*args,**kwargs)
        if len(provider.calls)==2:loop.profile_token_budget=loop._turn_reserved_tokens
        return reply
    provider.chat=chat
    turn=loop.send('Explain.')
    assert turn.reply=='Partial draft. '+CITE and len(provider.calls)==2 and turn.steps==2

def test_extra_check_keeps_context_guard(vault,monkeypatch):
    loop,provider,events=setup(vault,monkeypatch)
    original=provider.chat
    def chat(*args,**kwargs):
        reply=original(*args,**kwargs)
        if len(provider.calls)==2:loop.context_limit=1024
        return reply
    provider.chat=chat
    assert loop.send('Explain.').reply=='Partial draft. '+CITE
    assert len(provider.calls)==2
