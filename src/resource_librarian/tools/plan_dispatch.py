"""Core-owned, read-only task DAG execution over snapshot packets."""
from __future__ import annotations
import json
from dataclasses import replace
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from .. import clerk, effort
from ..packet_checks import content_sha256, verify_citations
from ..registry import Card, Context, REGISTRY, tool

PROFILES = {1:'tier1_lead', 2:'tier2_forager', 3:'tier3_leaf'}
CAPS = {1:'lead_agents', 2:'tier2_agents', 3:'tier3_agents'}


def _call_external(ctx, server, name, arguments):
    tool_name = f'mcp__{server}__{name}'
    if name not in {'compile_task_packet','list_graphs'}:
        raise ValueError('PLAN_EXTERNAL_TOOL_REFUSED')
    # A narrowly named Core expansion, like durable-reference rehydration.
    # Profile/phase/Broker checks still execute in Registry.call.
    child = replace(ctx, extras={**ctx.extras, 'plan_packet_fetch':tool_name})
    out = REGISTRY.call(tool_name, arguments, child)
    if not isinstance(out, dict) or out.get('error') or out.get('is_error') or out.get('structured_result_withheld'):
        raise ValueError('EXTERNAL_CALL_FAILED: ' + str(out)[:400])
    if 'content' in out:
        out = json.loads(out['content'])
    if not isinstance(out, dict) or out.get('error'):
        raise ValueError('EXTERNAL_CALL_FAILED: ' + str(out)[:400])
    return out


def _run_task(ctx, tier, packet):
    if tier == 3:
        from .staging import clerk_endpoint
        endpoint = clerk_endpoint(ctx)
        if endpoint is None:
            raise ValueError('CLERK_UNAVAILABLE')
        result = clerk.run([clerk.code_block_contract(packet)], endpoint)[0]
        if not result.ok:
            raise ValueError('CLERK_FAILED: ' + result.problems)
        return result.value, {k:v for k,v in result.to_dict().items() if k != 'value'}
    from .delegate import delegate
    brief = packet['instruction'] + '\n```json\n' + json.dumps(packet, ensure_ascii=False) + '\n```\nReturn JSON matching: ' + json.dumps(clerk.code_contract_schema())
    out = delegate(ctx, questions=[brief], tier=tier)
    if out.get('error') or not out.get('results'):
        raise ValueError('HELPER_FAILED: ' + str(out)[:400])
    result = out['results'][0]
    if result.get('error') or result.get('stopped'):
        raise ValueError('HELPER_FAILED: ' + str(result.get('error') or result.get('stopped')))
    text = result.get('answer', '').strip()
    if text.startswith('```') and text.endswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    return json.loads(text), {k:result[k] for k in ('model','tools','steps') if k in result}


def _validate(ctx, plan):
    def text(v): return isinstance(v, str) and bool(v.strip())
    if not isinstance(plan, dict) or set(plan) != {'plan_id','server','tasks'} or not all(text(plan[k]) for k in ('plan_id','server')):
        raise ValueError('PLAN_SHAPE')
    rows = plan['tasks']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 32: raise ValueError('PLAN_SHAPE')
    tasks = {}
    for t in rows:
        if not isinstance(t, dict) or set(t) != {'task_id','tier','graph_id','anchors','instruction','depends_on'}: raise ValueError('PLAN_SHAPE')
        if not all(text(t[k]) for k in ('task_id','graph_id','instruction')) or t['task_id'] in tasks or type(t['tier']) is not int or t['tier'] not in PROFILES: raise ValueError('PLAN_SHAPE')
        if not isinstance(t['anchors'], list) or not 1 <= len(t['anchors']) <= 8 or not all(text(a) for a in t['anchors']): raise ValueError('PLAN_SHAPE')
        deps = t['depends_on']
        if not isinstance(deps, list) or not all(text(d) for d in deps) or len(deps) != len(set(deps)): raise ValueError('PLAN_SHAPE')
        tasks[t['task_id']] = t
    if any(d not in tasks for t in rows for d in t['depends_on']): raise ValueError('PLAN_UNKNOWN_DEPENDENCY')
    waves, done = [], set()
    while len(done) < len(tasks):
        wave = sorted(k for k,t in tasks.items() if k not in done and set(t['depends_on']) <= done)
        if not wave: raise ValueError('PLAN_CYCLE')
        counts = Counter(tasks[k]['tier'] for k in wave)
        if any(n > effort.of(ctx)[CAPS[tier]] for tier,n in counts.items()): raise ValueError('PLAN_TOO_LARGE_FOR_EFFORT')
        waves.append(wave); done.update(wave)
    mcp = ctx.extras.get('mcp'); server = plan['server']
    if mcp is None: raise ValueError('PLAN_SERVER_UNAVAILABLE')
    status = mcp.status().get(server, {})
    if not all(status.get(k) for k in ('enabled','accepted','connected')) or status.get('library_enabled') is False: raise ValueError('PLAN_SERVER_UNAVAILABLE')
    names = mcp.tool_names(server)
    if any(f'mcp__{server}__{name}' not in names for name in ('compile_task_packet','list_graphs')): raise ValueError('PLAN_SERVER_UNAVAILABLE')
    return tasks, waves


def _cancelled(ctx):
    cancel = ctx.extras.get('cancel')
    return cancel is not None and cancel.is_set()


@tool('dispatch_plan', tier='contribute', effect='read', open_world=True,
      card=Card('Run a lead-compiled task DAG with snapshot packets and verified citations',
                'bounded code investigation; outputs remain advisory'))
def dispatch_plan(ctx: Context, plan: dict) -> dict:
    tasks, waves = _validate(ctx, plan)
    results, packets = {}, {}; server = plan['server']
    for wave in waves:
        ready = []
        for tid in wave:
            t = tasks[tid]
            if any(results[d]['state'] != 'ok' for d in t['depends_on']):
                results[tid] = dict(state='skipped', snapshot_id=None, error='DEPENDENCY_FAILED'); continue
            try:
                if _cancelled(ctx): raise ValueError('CANCELLED')
                upstream = []
                for d in sorted(t['depends_on']):
                    dep = results[d]; dp = packets[d]
                    first = next(a for a in dp['anchors'] if a['ref'] == tasks[d]['anchors'][0])
                    rec = dict(task_id=d, ref=first['ref'], cite=first['cite_as'])
                    for port in ('inputs','outputs'):
                        rec[port] = [dict(p) for i,p in enumerate(dep['answer'].get(port, [])) if f'{port}[{i}].cite' in dep['verification']['verified']]
                    upstream.append(rec)
                packet = _call_external(ctx, server, 'compile_task_packet', dict(graph_id=t['graph_id'], anchors=t['anchors'], instruction=t['instruction'], profile=PROFILES[t['tier']], upstream=upstream))
                if packet.get('packet_version') != 'task-packet-v1' or packet.get('graph_id') != t['graph_id'] or not isinstance(packet.get('snapshot_id'), str): raise ValueError('INVALID_TASK_PACKET')
                if not any(a.get('ref') == t['anchors'][0] for a in packet.get('anchors', [])): raise ValueError('ANCHOR_OMITTED')
                packets[tid] = packet; ready.append(tid)
            except Exception as exc:
                results[tid] = dict(state='failed', snapshot_id=None, error=str(exc)[:700])

        def run(tid):
            t = tasks[tid]; packet = packets[tid]
            try:
                if _cancelled(ctx): raise ValueError('CANCELLED')
                answer, receipt = _run_task(ctx, t['tier'], packet)
                verification = verify_citations(answer, packet)
                if not isinstance(answer, dict): raise ValueError('ANSWER_SHAPE')
                return dict(state='ok', snapshot_id=packet['snapshot_id'], answer=answer, verification=verification,
                    receipt={**receipt, 'plan_id':plan['plan_id'], 'task_id':tid, 'tier':t['tier'], 'graph_id':t['graph_id'], 'snapshot_id':packet['snapshot_id'],
                             'packet_sha256':content_sha256(packet), 'answer_sha256':content_sha256(answer)})
            except Exception as exc:
                return dict(state='failed', snapshot_id=packet['snapshot_id'], error=str(exc)[:700])
        for tier in sorted(PROFILES):
            group = [tid for tid in ready if tasks[tid]['tier'] == tier]
            if group:
                with ThreadPoolExecutor(max_workers=min(len(group), effort.of(ctx)[CAPS[tier]])) as pool:
                    for tid, result in zip(group, pool.map(run, group)): results[tid] = result
    stale = []
    if any(r['state'] == 'ok' for r in results.values()):
        try:
            if _cancelled(ctx): raise ValueError('CANCELLED')
            latest = _call_external(ctx, server, 'list_graphs', {})
            snapshots = {g['graph_id']:g['snapshot_id'] for g in latest['graphs']}
        except Exception:
            snapshots = {}
        for tid in sorted(results):
            if results[tid]['state'] == 'ok' and snapshots.get(tasks[tid]['graph_id']) != results[tid]['snapshot_id']:
                stale.append(tid); results[tid]['scope_error'] = 'STALE_SCOPE'
    return dict(plan_id=plan['plan_id'], waves=waves, results={k:results[k] for k in sorted(results)}, stale=stale)
