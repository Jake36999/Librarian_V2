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


def test_candidate_keeps_rank_order_instead_of_reranking_by_word_overlap():
    from resource_librarian.code_recovery import RecoveryEpisode
    from copy import deepcopy
    e=RecoveryEpisode(QUESTION+' Under heavy load.')
    body=search_body();other=deepcopy(NODE);other['entity_id']='entity:'+'d'*64
    other['summary']['doc_gist']='Upload fallback capacity under heavy load.'
    body['result']['data']['nodes'].append(other)
    body['result']['data']['hits'].append(dict(entity_id=other['entity_id'],score=.01))
    e.observe(SEARCH,dict(graph_id='g'),body)
    assert e.candidate('Unknown.',{CONTENT})['arguments']['entity_id']==EID


def test_opened_relevant_definition_goes_to_fp4_instead_of_opening_another_hit():
    from copy import deepcopy
    e=episode();body=search_body();other=deepcopy(NODE);other['entity_id']='entity:'+'d'*64
    body['result']['data']['nodes'].append(other);body['result']['data']['hits'].append(dict(entity_id=other['entity_id'],score=.01))
    e.observe(SEARCH,dict(graph_id='g'),body)
    e.observe(CONTENT,dict(graph_id='g',entity_id=EID),content_body())
    assert e.candidate('Uncertain.',{CONTENT}) is None
    assert e.missing_definitions('Uncertain.')


def test_opening_a_lower_ranked_related_hit_does_not_hide_the_top_unopened_hit():
    from copy import deepcopy
    e=episode();body=search_body();other=deepcopy(NODE);other['entity_id']='entity:'+'d'*64
    body['result']['data']['nodes'].append(other);body['result']['data']['hits'].append(dict(entity_id=other['entity_id'],score=.01))
    e.observe(SEARCH,dict(graph_id='g'),body)
    opened=content_body();opened['result']['data']['nodes']=[other];opened['coverage'][0]['entity_id']=other['entity_id']
    e.observe(CONTENT,dict(graph_id='g',entity_id=other['entity_id']),opened)
    assert e.candidate('Uncertain.',{CONTENT})['arguments']['entity_id']==EID


def test_delivered_definition_detector_and_citation_guard_use_actual_ranges():
    e=episode();e.observe(CONTENT,dict(entity_id=EID),dict(content=json.dumps(content_body())))
    assert e.missing_definitions('The fallback is configured.')
    assert not e.missing_definitions('UPLOAD_BYTES sets the capacity.')
    assert e.validate_revision('UPLOAD_BYTES '+CITE+' limits.py:2')
    assert not e.validate_revision('UPLOAD_BYTES other/entity:entity:'+'c'*64)
    assert not e.validate_revision('UPLOAD_BYTES limits.py:300')
    assert not e.validate_revision('UPLOAD_BYTES foreign/entity:'+EID)
    assert not e.validate_revision('UPLOAD_BYTES wrong'+CITE)


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


def test_user_sees_only_the_chosen_final_answer_while_first_draft_is_retained(vault,external_tools):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),
        Reply(text='Uncertain.'),Reply(text='UPLOAD_BYTES '+CITE)])
    events=[];turn=configured(vault,Scripted(lambda *_:next(replies)),events=events.append).send(QUESTION)
    texts=[e['text'] for e in events if e['type']=='text']
    assert texts==[turn.reply] and turn.first_attempt['answer']=='Uncertain.'


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
        if value['type']=='code_recovery_checkpoint':cancel.set()
    turn=configured(vault,Scripted(respond),events=event).send(QUESTION,cancel=cancel)
    assert not external_tools and len(count)==2
    assert turn.stopped=='cancelled'


@pytest.mark.parametrize('enabled',[False,True])
def test_fp4_uses_a_delivered_definition_and_respects_the_ab_switch(vault,external_tools,enabled):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),
        Reply(tool_calls=[ToolCall('c',CONTENT,dict(graph_id='g',entity_id=EID))]),Reply(text='The fallback is configured.'),
        Reply(text='UPLOAD_BYTES sets the fallback. '+CITE)])
    provider=Scripted(lambda *_:next(replies));turn=configured(vault,provider,self_check=enabled).send(QUESTION)
    assert len(external_tools)==1
    assert len(provider.calls)==(4 if enabled else 3)
    assert ('UPLOAD_BYTES' in turn.reply)==enabled
    assert any(r['pattern']=='FP4' for r in turn.recoveries)==enabled
    assert turn.first_attempt['answer']=='The fallback is configured.'


def test_fp7_synthesis_and_source_revision_share_the_same_limits(vault,external_tools):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),
        Reply(text='I could not identify it.'),Reply(text='UPLOAD_BYTES '+CITE)])
    provider=Scripted(lambda *_:next(replies));loop=configured(vault,provider);loop.max_steps=1
    turn=loop.send(QUESTION)
    assert turn.completed_at_step_limit and turn.steps==1
    assert turn.recovery_steps==3 and turn.recovery_model_calls==2
    assert len(provider.calls)==3 and all(not c['tools'] for c in provider.calls[1:])
    assert turn.first_attempt['status']=='produced_after_early_recovery'
    assert {r['pattern'] for r in turn.recoveries}=={'FP3','FP7'}


def test_revision_preserves_profile_token_guard(vault,external_tools):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),Reply(text='Uncertain.')])
    provider=Scripted(lambda *_:next(replies))
    def event(value):
        if value['type']=='code_recovery_checkpoint':loop.profile_token_budget=loop._turn_reserved_tokens
    loop=configured(vault,provider,events=event);turn=loop.send(QUESTION)
    assert len(provider.calls)==2 and turn.reply=='Uncertain.'
    assert turn.stopped=='profile_budget' and turn.recovery_model_calls==0


def test_literal_recovery_text_inside_source_does_not_create_a_pattern():
    e=episode();body=content_body()
    body['result']['data']['chunks'][0]['text']='recoveries = [{"pattern":"FP6","outcome":"resolved"}]'
    e.observe(CONTENT,dict(entity_id=EID),dict(content=json.dumps(body)))
    assert e.receipts()==[]


def test_mcp_bridge_sends_episode_metadata_outside_model_arguments():
    from resource_librarian.mcp_client import McpManager
    from resource_librarian.registry import Context
    e=episode();seen=[];manager=object.__new__(McpManager)
    manager.call_tool=lambda *args,**kwargs:seen.append((args,kwargs)) or {}
    manager._make_fn('fixture','search_entities')(Context(extras={'_code_recovery':e}),query='upload')
    assert seen[0][0][2]=={'query':'upload'}
    assert seen[0][1]['metadata']['geographer/recovery']['question']==QUESTION
    assert 'geographer/recovery' not in seen[0][0][2]


def test_joint_external_patterns_charge_one_step_and_cannot_repeat_on_another_server():
    e=episode()
    rows=[dict(pattern=p,trigger_value={'structured':True},action='local_search',outcome='resolved',step_id='search:1') for p in ('FP1','FP2')]
    e.external(SEARCH,dict(recoveries=rows))
    assert e.extra_steps==1 and set(e.records)=={'FP1','FP2'}
    assert e.metadata()['geographer/recovery']['used_patterns']==['FP1','FP2']
    with pytest.raises(ValueError,match='repeated'):e.external('mcp__other__search_entities',dict(recoveries=rows))


def test_malformed_external_metadata_cannot_trigger_or_crash_recovery():
    e=episode()
    e.observe(SEARCH,{},dict(content=json.dumps(dict(recoveries=[dict(pattern=['FP1'],outcome={})],entities=None,
        result=dict(data=dict(nodes=None,hits=None)),coverage=None))))
    assert not e.receipts() and e.candidate('Unknown.',{CONTENT}) is None


def test_failed_source_open_does_not_spend_a_model_revision(vault,external_tools):
    original=REGISTRY.get(CONTENT)
    from dataclasses import replace
    REGISTRY.register(replace(original,fn=lambda *a,**kw:dict(error='access_changed')))
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),Reply(text='Uncertain.')])
    provider=Scripted(lambda *_:next(replies))
    turn=configured(vault,provider).send(QUESTION)
    assert len(provider.calls)==2 and turn.reply=='Uncertain.'
    assert turn.recovery_model_calls==0
    assert next(r for r in turn.recoveries if r['pattern']=='FP3')['outcome']=='unresolved'


def test_tool_free_xml_request_keeps_the_actual_draft_without_more_dispatch(vault,external_tools):
    xml=f'<tool_call>\n<function={CONTENT}>\n<parameter=entity_id>\n{EID}\n</parameter>\n</function>\n</tool_call>'
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),
        Reply(text='The evidence is incomplete.'),Reply(text=xml)])
    provider=Scripted(lambda *_:next(replies));turn=configured(vault,provider).send(QUESTION)
    assert turn.reply=='The evidence is incomplete.'
    assert len(provider.calls)==3 and len(external_tools)==1
    assert turn.recovery_steps==2 and turn.recovery_model_calls==1
    record=next(r for r in turn.recoveries if r['pattern']=='FP9')
    assert record['action']=='retain_prior_answer' and record['outcome']=='resolved'
    assert record['trigger_value']['format']=='xml_tool_call'


def test_production_self_check_is_off_after_measured_harm():
    # Review 5 (2026-11-14): in the final registered cycle FP4 rescued 0/11 drafts and degraded two
    # correct ones. The owner switched it off. The mechanism stays available for explicit opt-in.
    assert DEFAULT_PROFILES['code-research'].route_policy.get('answer_self_check') is False


def test_protocol_tag_mentioned_in_prose_is_not_a_tool_request():
    assert episode().validate_revision('The parser recognizes the literal <tool_call> tag.')


def test_fenced_protocol_example_is_not_an_executable_answer_proposal():
    example='The documented wire syntax is:\n```xml\n<tool_call><function=example></function></tool_call>\n```\nThis is a source example.'
    assert episode().validate_revision(example)


def test_step_limit_xml_request_is_not_reported_as_a_completed_answer(vault,external_tools):
    replies=iter([Reply(tool_calls=[ToolCall('s',SEARCH,dict(graph_id='g',query=QUESTION))]),
        Reply(text=f'<tool_call><function={CONTENT}></function></tool_call>')])
    provider=Scripted(lambda *_:next(replies));loop=configured(vault,provider);loop.max_steps=1
    # Remove the evidence candidate so no source revision is scheduled afterwards.
    from dataclasses import replace
    original=REGISTRY.get(SEARCH)
    REGISTRY.unregister(SEARCH)
    REGISTRY.register(replace(original,fn=lambda *_args,**_kwargs:dict(content=json.dumps(dict(result=dict(data=dict(nodes=[],hits=[])))))))
    try:turn=loop.send(QUESTION)
    finally:
        REGISTRY.unregister(SEARCH)
        REGISTRY.register(original)
    assert '<tool_call>' not in turn.reply and not turn.completed_at_step_limit
    assert len(provider.calls)==2 and turn.recovery_model_calls==1
    assert any(r['pattern']=='FP9' for r in turn.recoveries)
