"""Core-owned, read-only task DAG execution over snapshot packets."""
from __future__ import annotations
import json
from dataclasses import replace
import dataclasses
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


PLAN_KEYS = ('plan_id', 'server', 'tasks')
TASK_KEYS = ('task_id', 'tier', 'graph_id', 'anchors', 'instruction', 'depends_on')
# Exact decimal spellings a lead may send for a tier (observed live, 2026-11-14).
# Nothing else is coerced: no whitespace, floats, leading zeros or booleans.
TIER_SPELLINGS = {'1': 1, '2': 2, '3': 3}


def _shape_problems(plan):
    """Every shape problem, bounded, plus the normalised copy and its notes.

    A bare ``PLAN_SHAPE`` gave a lead nothing to repair; naming each field does.
    """
    def text(v): return isinstance(v, str) and bool(v.strip())
    problems, notes = [], []
    if not isinstance(plan, dict):
        return ['plan must be an object'], None, notes
    problems += [f'missing {k}' for k in PLAN_KEYS if k not in plan]
    problems += [f'unexpected {k}' for k in sorted(set(plan) - set(PLAN_KEYS), key=str)]
    problems += [f'{k} must be a non-empty string' for k in ('plan_id', 'server') if k in plan and not text(plan[k])]
    rows = plan.get('tasks')
    if 'tasks' in plan and (not isinstance(rows, list) or not 1 <= len(rows) <= 32):
        problems.append('tasks must be a list of 1 to 32 task objects')
        rows = None
    clean, seen = [], set()
    for i, t in enumerate(rows or []):
        where = f'tasks[{i}]'
        if not isinstance(t, dict):
            problems.append(f'{where}: must be an object'); continue
        problems += [f'{where}: missing {k}' for k in TASK_KEYS if k not in t]
        problems += [f'{where}: unexpected {k}' for k in sorted(set(t) - set(TASK_KEYS), key=str)]
        t = dict(t)
        for k in ('task_id', 'graph_id', 'instruction'):
            if k in t and not text(t[k]): problems.append(f'{where}: {k} must be a non-empty string')
        if text(t.get('task_id')):
            if t['task_id'] in seen: problems.append(f'{where}: duplicate task_id {t["task_id"][:40]!r}')
            seen.add(t['task_id'])
        if 'tier' in t:
            tier = t['tier']
            if type(tier) is str and tier in TIER_SPELLINGS:
                t['tier'] = TIER_SPELLINGS[tier]; notes.append(f'{where}.tier')
            elif type(tier) is not int or tier not in PROFILES:
                problems.append(f'{where}: tier must be the integer 1, 2 or 3')
        if 'anchors' in t:
            a = t['anchors']
            if not isinstance(a, list) or not 1 <= len(a) <= 8 or not all(text(x) for x in a):
                problems.append(f'{where}: anchors must be a list of 1 to 8 entity references')
        if 'depends_on' in t:
            d = t['depends_on']
            if not isinstance(d, list) or not all(text(x) for x in d) or len(d) != len(set(d)):
                problems.append(f'{where}: depends_on must be a list of distinct task_id strings')
        clean.append(t)
    return problems, (None if problems else {**plan, 'tasks': clean}), notes


def _shape_error(problems):
    """One bounded message; a problem every task shares is named once, with its indexes."""
    grouped, order = {}, []
    for problem in problems:
        where, sep, what = problem.partition(': ')
        if sep and where.startswith('tasks['):
            if what not in grouped: grouped[what] = []; order.append(what)
            grouped[what].append(where[6:-1])
        else:
            order.append(problem); grouped[problem] = None
    items = [what if grouped[what] is None else f"tasks[{','.join(grouped[what])}]: {what}" for what in order]
    message, shown = 'PLAN_SHAPE: ', 0
    for item in items:
        if len(message) + len(item) + 2 > 560: break
        message += ('; ' if shown else '') + item; shown += 1
    if shown < len(items): message += f'; and {len(items) - shown} more'
    return ValueError(message)


def _validate(ctx, plan, notes=None):
    problems, plan, normalised = _shape_problems(plan)
    if problems: raise _shape_error(problems)
    if notes is not None: notes.extend(normalised)
    rows = plan['tasks']
    tasks = {t['task_id']: t for t in rows}
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
    normalised = []
    tasks, waves = _validate(ctx, plan, normalised)
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
    return dict(plan_id=plan['plan_id'], waves=waves, results={k:results[k] for k in sorted(results)}, stale=stale,
                normalised=normalised)


def _plan_schema() -> dict:
    """The full nested contract a lead is shown (live pilot finding P2, 2026-11-14).

    It mirrors ``_shape_problems`` exactly; a test holds the two together.
    """
    ref = {'type': 'string', 'minLength': 1}
    task = {'type': 'object', 'additionalProperties': False, 'required': list(TASK_KEYS), 'properties': {
        'task_id': {**ref, 'description': 'unique within this plan'},
        'tier': {'type': 'integer', 'enum': [1, 2, 3],
                 'description': 'integer, not a string: 3 = Clerk code-block contract, '
                                '2 = synthesis over upstream contracts, 1 = lead-model review'},
        'graph_id': {**ref, 'description': 'a graph_id from list_graphs on this server'},
        'anchors': {'type': 'array', 'minItems': 1, 'maxItems': 8, 'items': ref,
                    'description': 'canonical entity references exactly as search returned them'},
        'instruction': {**ref, 'description': 'what this task should describe; no conversation framing'},
        'depends_on': {'type': 'array', 'uniqueItems': True, 'items': ref,
                       'description': 'task_ids whose results this task receives; [] for none'}}}
    example = {'plan_id': 'config-contracts', 'server': '<connected geo-grapher server>', 'tasks': [
        {'task_id': 'contract-1', 'tier': 3, 'graph_id': '<graph_id>', 'anchors': ['entity:<id>'],
         'instruction': 'Describe the inputs, outputs and calls of this code block.', 'depends_on': []},
        {'task_id': 'synthesis-1', 'tier': 2, 'graph_id': '<graph_id>', 'anchors': ['entity:<id>'],
         'instruction': 'Combine the upstream contracts into one cited account.', 'depends_on': ['contract-1']}]}
    plan = {'type': 'object', 'additionalProperties': False, 'required': list(PLAN_KEYS),
            'properties': {'plan_id': ref, 'server': {**ref, 'description': 'the connected MCP server name'},
                           'tasks': {'type': 'array', 'minItems': 1, 'maxItems': 32, 'items': task}},
            'examples': [example]}
    return {'type': 'object', 'additionalProperties': False, 'required': ['plan'], 'properties': {'plan': plan}}


REGISTRY._tools['dispatch_plan'] = dataclasses.replace(REGISTRY.get('dispatch_plan'), schema=_plan_schema())
