"""Generic code-research recovery: bounded actions, actual evidence, no goldens."""
import json
import threading
import pytest
from resource_librarian.agent_runtime import AgentProfile,DEFAULT_PROFILES,ProfileStore
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply,Scripted,ToolCall
from resource_librarian.registry import REGISTRY,Card,ToolSpec

SEARCH='mcp__fixture__search_entities'
CONTENT='mcp__fixture__get_entity_content'
EID='entity:'+'a'*64
CITE='fixture/entity:'+EID
QUESTION='Which constant sets the upload fallback capacity?'
SOURCE=dict(repo_id='r',revision='fixed',rel_path='limits.py',start_line=2,end_line=2)
NODE=dict(entity_id=EID,cite_as=CITE,qualified_name='limits.py.UPLOAD_BYTES',kind='constant',source=SOURCE,
    summary=dict(doc_gist='Upload fallback capacity.',signature='UPLOAD_BYTES = 4096',why='comment: upload fallback capacity'))


def episode():
    from resource_librarian.code_recovery import RecoveryEpisode
    return RecoveryEpisode(QUESTION,self_check=True)


def search_body():return dict(graph_id='g',entities=[{k:NODE[k] for k in ('entity_id','cite_as','qualified_name')}],
    result=dict(data=dict(nodes=[NODE],hits=[dict(entity_id=EID,score=1.)])))


def content_body():return dict(graph_id='g',result=dict(data=dict(entity_id=EID,nodes=[NODE],
    chunks=[dict(entity_id=EID,source=SOURCE,text='UPLOAD_BYTES = 4096\n')])),
    coverage=[dict(entity_id=EID,start_line=2,end_line=2,source=SOURCE,truncated=False,sha256='b'*64)])


def test_one_pattern_workflow_and_three_shared_extra_steps():
    e=episode()
    assert e.begin('FP1',{'score':0},'verbatim_search')
    assert not e.begin('FP1',{'score':0},'verbatim_search')
    assert e.begin('FP2',{'disagree':True},'semantic_fusion')
    assert e.claim('search',patterns=['FP1','FP2'])
    assert e.begin('FP3',{'unopened':EID},'open_and_revise')
    assert e.claim('source',patterns=['FP3'])
    assert e.begin('FP4',{'missing_definition':EID},'shared_revision')
    assert e.claim('revision',patterns=['FP3','FP4'],model=True)
    assert e.extra_steps==3 and not e.claim('another',patterns=['FP4'],model=True)


def test_at_most_two_additional_model_invocations_even_with_a_step_left():
    e=episode()
    for pattern in ('FP7','FP4','FP5'):assert e.begin(pattern,{'structured':True},'test_action')
    assert e.claim('synthesis',patterns=['FP7'],model=True)
    assert e.claim('revision',patterns=['FP4'],model=True)
    assert not e.claim('third_model',patterns=['FP5'],model=True)
    assert e.extra_steps==2 and e.extra_model_calls==2


def test_retrieved_candidate_uses_same_server_and_real_scoped_id():
    e=episode();e.observe(SEARCH,dict(graph_id='g',query=QUESTION),dict(content=json.dumps(search_body())))
    candidate=e.candidate('I could not identify it.',{SEARCH,CONTENT})
    assert candidate['tool']==CONTENT and candidate['arguments']==dict(graph_id='g',entity_id=EID)
    assert e.candidate('I could not identify it.',{SEARCH}) is None
    assert e.candidate('UPLOAD_BYTES '+CITE,{SEARCH,CONTENT}) is None


def test_delivered_definition_detector_and_citation_guard_use_actual_ranges():
    e=episode();e.observe(CONTENT,dict(entity_id=EID),dict(content=json.dumps(content_body())))
    assert e.missing_definitions('The fallback is configured.')
    assert not e.missing_definitions('UPLOAD_BYTES sets the capacity.')
    assert e.validate_revision('UPLOAD_BYTES '+CITE+' limits.py:2')
    assert not e.validate_revision('UPLOAD_BYTES other/entity:entity:'+'c'*64)
    assert not e.validate_revision('UPLOAD_BYTES limits.py:300')


@pytest.fixture
def external_tools():
    opened=[]
    def search(ctx,**kwargs):return dict(content=json.dumps(search_body()))
    def content(ctx,**kwargs):opened.append(kwargs);return dict(content=json.dumps(content_body()))
    for name,fn in ((SEARCH,search),(CONTENT,content)):
        REGISTRY.register(ToolSpec(name,fn,'consult','read',Card('Read fixture evidence'),needs_vault=False,external=True,
            schema=dict(type='object',properties=dict(graph_id=dict(type='string'),query=dict(type='string'),entity_id=dict(type='string')),additionalProperties=False)))
    try:yield opened
    finally:
        for name in (SEARCH,CONTENT):REGISTRY.unregister(name)


def configured(vault,provider,*,self_check=False,events=None):
    loop=Loop(vault,provider,scribe=None,max_steps=12,extras={'use_tool_bundles':False},on_event=events)
    values=DEFAULT_PROFILES['code-research'].public();values['route_policy']={**values['route_policy'],'answer_self_check':self_check}
    loop.configure_profile(AgentProfile(**values).validate())
    loop.ctx.extras.update(agent_profile='code-research',profile_store=ProfileStore(vault))
    loop.only=frozenset({SEARCH,CONTENT})
    return loop


def test_loop_opens_skipped_source_then_one_guarded_revision_and_keeps_first(vault,external_tools):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),
        Reply(text='I could not identify it.'),Reply(text='UPLOAD_BYTES sets the capacity. '+CITE)])
    provider=Scripted(lambda *_:next(replies))
    turn=configured(vault,provider).send(QUESTION)
    assert 'UPLOAD_BYTES' in turn.reply
    assert turn.first_attempt['answer']=='I could not identify it.'
    assert turn.first_attempt['status']=='unrecovered_draft'
    assert len(external_tools)==1 and len(provider.calls)==3 and provider.calls[-1]['tools']==[]
    assert turn.recovery_steps==2 and turn.recovery_model_calls==1
    assert next(r for r in turn.recoveries if r['pattern']=='FP3')['outcome']=='resolved'


def test_revision_cannot_execute_tools_or_replace_answer_with_an_invented_citation(vault,external_tools):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),Reply(text='Uncertain.'),
        Reply(text='UPLOAD_BYTES other/entity:entity:'+'c'*64,tool_calls=[ToolCall('bad',CONTENT,dict(entity_id=EID))])])
    provider=Scripted(lambda *_:next(replies));turn=configured(vault,provider).send(QUESTION)
    assert turn.reply=='Uncertain.' and len(external_tools)==1 and len(provider.calls)==3
    assert next(r for r in turn.recoveries if r['pattern']=='FP3')['outcome']=='unresolved'


def test_cancel_after_first_draft_blocks_every_recovery_action(vault,external_tools):
    cancel=threading.Event();count=[]
    def respond(*_):
        count.append(1)
        return Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]) if len(count)==1 else Reply(text='Uncertain.')
    def event(value):
        if value['type']=='text':cancel.set()
    turn=configured(vault,Scripted(respond),events=event).send(QUESTION,cancel=cancel)
    assert not external_tools and len(count)==2
    assert turn.stopped=='cancelled'
