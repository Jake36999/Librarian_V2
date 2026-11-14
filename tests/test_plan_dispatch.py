import json
from types import SimpleNamespace
import pytest
from resource_librarian.registry import Context
from resource_librarian import effort


def plan(tasks=None):
    return dict(plan_id='p1',server='geo',tasks=tasks or [task('t1')])


def task(tid, deps=(), tier=3):
    return dict(task_id=tid,tier=tier,graph_id='g1',anchors=['entity:f'],instruction='Describe.',depends_on=list(deps))


class FakeMcp:
    def status(self):
        return {'geo':dict(enabled=True,accepted=True,connected=True)}
    def tool_names(self, server):
        return ['mcp__geo__compile_task_packet','mcp__geo__list_graphs']


@pytest.fixture
def world(monkeypatch):
    import resource_librarian.tools.plan_dispatch as pd
    fetched=[]
    def call(ctx, server, tool, arguments):
        if tool=='list_graphs':
            return {'graphs':[dict(graph_id='g1',snapshot_id='s1')]}
        fetched.append(arguments)
        return dict(packet_version='task-packet-v1',graph_id='g1',snapshot_id='s1',instruction='Describe.',
            anchors=[dict(ref='entity:f',cite_as='g/entity:f',text='def f(x): return x')],boundary=[],
            upstream=arguments['upstream'],handles=['g/entity:f'])
    monkeypatch.setattr(pd, '_call_external',call)
    def run(ctx, tier, packet):
        return dict(inputs=[dict(name='x',cite='g/entity:f'),dict(name='ghost',cite='bad')],
                    outputs=[dict(name='y',cite='g/entity:f')],calls=[],claims=[dict(text='do not forward',cite='g/entity:f')],not_determinable=[]), {'model':'fake','attempts':1}
    monkeypatch.setattr(pd, '_run_task',run)
    return pd, Context(tier='contribute',extras={'mcp':FakeMcp(),'effort':effort.profile(1)}), fetched


@pytest.mark.parametrize('tasks,code', [([task('t1',['t2']),task('t2',['t1'])],'PLAN_CYCLE'),
    ([task('t1',['missing'])],'PLAN_UNKNOWN_DEPENDENCY'),
    ([task('t'+str(i),tier=1) for i in range(6)],'PLAN_TOO_LARGE_FOR_EFFORT'),
    ([task('t1'),task('t1')],'PLAN_SHAPE'),([task('t1',tier=True)],'PLAN_SHAPE')])
def test_preflight_has_zero_external_calls(world,tasks,code):
    pd,ctx,calls=world
    with pytest.raises(ValueError,match='^'+code): pd.dispatch_plan(ctx,plan(tasks))
    assert calls==[]


def test_dependency_ports_only_and_receipts(world):
    pd,ctx,calls=world
    out=pd.dispatch_plan(ctx,plan([task('t3',['t2'],1),task('t2',['t1'],2),task('t1')]))
    assert out['waves']==[['t1'],['t2'],['t3']]
    assert out['results']['t1']['verification']['closure_strength']=='none'
    up=calls[1]['upstream']
    assert up==[dict(task_id='t1',ref='entity:f',cite='g/entity:f',inputs=[dict(name='x',cite='g/entity:f')],outputs=[dict(name='y',cite='g/entity:f')])]
    assert 'do not forward' not in json.dumps(up)
    assert out['results']['t1']['receipt']['task_id']=='t1'
    assert out['stale']==[]


def test_packet_failure_skips_transitive_dependants(world,monkeypatch):
    pd,ctx,calls=world
    original = pd._call_external
    monkeypatch.setattr(pd,'_call_external',lambda c,s,t,a: original(c,s,t,a) if t=='list_graphs' else {'error':'broken'})
    out=pd.dispatch_plan(ctx,plan([task('t1'),task('t2',['t1']),task('t3',['t2'])]))
    assert [out['results'][t]['state'] for t in ('t1','t2','t3')]==['failed','skipped','skipped']


def test_stale_snapshot_is_explicit(world,monkeypatch):
    pd,ctx,calls=world
    orig=pd._call_external
    monkeypatch.setattr(pd,'_call_external',lambda c,s,t,a: {'graphs':[dict(graph_id='g1',snapshot_id='s2')]} if t=='list_graphs' else orig(c,s,t,a))
    out=pd.dispatch_plan(ctx,plan())
    assert out['stale']==['t1'] and out['results']['t1']['scope_error']=='STALE_SCOPE'


def test_bundle_caps():
    from resource_librarian.agent_runtime import BUNDLES,MAX_BUNDLE_TOOLS
    for name in ('map','execute'):
        assert 'dispatch_plan' in BUNDLES[name].names
        assert len(BUNDLES[name].names)<=MAX_BUNDLE_TOOLS


def test_cap_is_per_wave_and_not_total(world):
    pd,ctx,calls=world
    out=pd.dispatch_plan(ctx,plan([task('t1',tier=1),task('t2',['t1'],1)]))
    assert out['waves']==[['t1'],['t2']]


def test_cancellation_prevents_all_fetches_and_helpers(world):
    import threading
    pd,ctx,calls=world
    ctx.extras['cancel']=threading.Event();ctx.extras['cancel'].set()
    out=pd.dispatch_plan(ctx,plan())
    assert out['results']['t1']['state']=='failed' and calls==[]


def test_non_geo_server_names_are_supported(world):
    pd,ctx,calls=world
    ctx.extras['mcp'].status=lambda: {'selected':dict(enabled=True,accepted=True,connected=True)}
    ctx.extras['mcp'].tool_names=lambda s:['mcp__selected__compile_task_packet','mcp__selected__list_graphs']
    p=plan();p['server']='selected'
    assert pd.dispatch_plan(ctx,p)['results']['t1']['state']=='ok'


def test_missing_anchor_fails_instead_of_running_empty_context(world,monkeypatch):
    pd,ctx,calls=world;orig=pd._call_external
    def call(*a):
        out=orig(*a)
        if a[2]=='compile_task_packet':out['anchors']=[]
        return out
    monkeypatch.setattr(pd,'_call_external',call)
    out=pd.dispatch_plan(ctx,plan())
    assert out['results']['t1']['state']=='failed'
    assert out['results']['t1']['error']=='ANCHOR_OMITTED'


def test_real_clerk_path_preserves_payload_and_receipt(monkeypatch):
    from resource_librarian.tools import plan_dispatch as pd,staging
    from resource_librarian import clerk
    class Endpoint:
        concurrency=1
        read_route={'model':'fixture','context_tokens':32768,
                    'visible_output_tokens':1800,'reasoning_reserve_tokens':0}
        def complete(self,payload,repair):
            assert payload['task']=='code_block_contract'
            return json.dumps(dict(inputs=[],outputs=[],calls=[],claims=[],not_determinable=[])),'fixture'
    monkeypatch.setattr(staging,'clerk_endpoint',lambda ctx:Endpoint())
    packet=dict(packet_version='task-packet-v1',instruction='Describe.',anchors=[],boundary=[],upstream=[],handles=[])
    answer,receipt=pd._run_task(Context(),3,packet)
    assert receipt['model']=='fixture' and receipt['attempts']==1
    assert answer['inputs']==[] and 'value' not in receipt


def test_external_path_uses_registry_and_checks_decoded_errors(monkeypatch):
    from resource_librarian.tools import plan_dispatch as pd
    calls=[]
    def call(name,args,ctx):
        calls.append(name)
        return dict(content=json.dumps({'error':{'code':'refused'}}))
    monkeypatch.setattr(pd.REGISTRY,'call',call)
    with pytest.raises(ValueError,match='EXTERNAL_CALL_FAILED'):
        pd._call_external(Context(),'selected','compile_task_packet',{})
    assert calls==['mcp__selected__compile_task_packet']


def test_core_expansion_keeps_broker_and_read_only_checks():
    from resource_librarian.tools import plan_dispatch as pd
    from resource_librarian.registry import REGISTRY,ToolSpec,Card
    name='mcp__fixture__compile_task_packet';calls=[]
    class Broker:
        def check(self,spec,args,ctx,preview=None):
            calls.append('broker'); return 'allowed'
    ctx=Context(tier='contribute',extras=dict(enforce_active_bundle=True,active_bundle=['dispatch_plan'],broker=Broker()))
    def fn(ctx,**args):calls.append('server');return dict(content='{"ok":true}')
    spec=ToolSpec(name=name,fn=fn,tier='contribute',effect='read',card=Card('fixture'),external=True,needs_vault=False,schema={'type':'object'})
    REGISTRY.register(spec)
    try:
        assert pd._call_external(ctx,'fixture','compile_task_packet',{})=={'ok':True}
        assert calls==['broker','server']
        REGISTRY.unregister(name)
        from dataclasses import replace
        REGISTRY.register(replace(spec,effect='write'));calls.clear()
        with pytest.raises(ValueError,match='EXTERNAL_CALL_FAILED'):
            pd._call_external(ctx,'fixture','compile_task_packet',{})
        assert not calls
    finally:REGISTRY.unregister(name)


def test_real_helper_path_keeps_helper_allowlist(tmp_path):
    from resource_librarian.tools import plan_dispatch as pd
    from resource_librarian.tools.delegate import HELPER_TOOLS
    from resource_librarian.providers import Provider,Reply
    from resource_librarian.init import init
    from resource_librarian.vault import Vault
    class Fixture(Provider):
        def chat(self,system,messages,tools,**kwargs):
            assert {t.name for t in tools}<=HELPER_TOOLS
            assert all(not t.name.startswith('mcp__') for t in tools)
            return Reply(text=json.dumps(dict(inputs=[],outputs=[],calls=[],claims=[],not_determinable=[])))
    init(tmp_path/'vault');ctx=Context(tier='contribute',vault=Vault(tmp_path/'vault'),extras={'helper_provider':lambda tier:Fixture()})
    packet=dict(packet_version='task-packet-v1',instruction='Describe.',anchors=[],boundary=[],upstream=[],handles=[])
    answer,receipt=pd._run_task(ctx,2,packet)
    assert answer['inputs']==[] and receipt['steps']==1
