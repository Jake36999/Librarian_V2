"""Recompute selected quantities from frozen sprint CSVs without changing them."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
from bisect import bisect_left
import csv
import json
import statistics

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / '2026-10-28-agent-workflow-sprint'
def read(name):
    with (SOURCE / 'data' / name).open(encoding='utf-8') as f:
        return list(csv.DictReader(f))
def ts(s):
    return datetime.fromisoformat(s.replace('Z', '+00:00'))
def summ(xs):
    return {'n': len(xs), 'median': statistics.median(xs) if xs else None, 'total': sum(xs)}

def main():
    baseline = json.loads((SOURCE / 'data/baseline_metrics.json').read_text(encoding='utf-8'))
    w = baseline['claude_opus_price_fit']
    changes = sorted([r for r in read('m1_changes.csv') if r['family'] == 'claude'], key=lambda r: r['commit_time'])
    ends = [ts(r['commit_time']) for r in changes]
    cache_create = Counter()
    for r in read('claude_librarian_v2_messages.csv'):
        if r['is_api_error'] == 'True' or r['is_sidechain'] == 'True' or r['session'] in {'61d3eaf3-e0bc-4aa9-aa45-2de25ffb574b', '23197395-4e2e-4e3c-ad90-9cbe3af61a81'}:
            continue
        i = bisect_left(ends, ts(r['ts']))
        if i < len(changes):
            cache_create[i] += int(r['cache_creation_tokens'])
    prices = []
    for i, r in enumerate(changes):
        old = (int(r['fresh_tokens']) * w['usd_per_mtok_input'] + int(r['output_tokens']) * w['usd_per_mtok_output'] + int(r['cache_read_tokens']) * w['usd_per_mtok_cache_read']) / 1e6
        extra = cache_create[i] * (w['usd_per_mtok_cache_creation'] - w['usd_per_mtok_input']) / 1e6
        prices.append({'commit': r['hash'], 'cache_creation_tokens': cache_create[i], 'reported_formula_usd': old, 'four_component_formula_usd': old + extra})
    p = ROOT / 'data/shadow_price_sensitivity.csv'
    with p.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(prices[0]))
        writer.writeheader(); writer.writerows(prices)
    # Mature follow-up is assessed at an explicit cutoff, rather than today's changing HEAD.
    cutoff = ts('2026-10-28T21:00:00Z')
    code = [r for r in read('commits.csv') if r['on_master'] == 'True' and r['code_commit'] == 'True' and r['bookkeeping_only'] != 'True' and r['n_parents'] == '1']
    mature = {f'at_least_{h}h_followup': sum((cutoff-ts(r['commit_time'])).total_seconds() >= 3600*h for r in code) for h in (24,72)}
    # Completed receipt vs. shell-result times used as result arrivals.
    delegates = read('codex_delegates.csv')
    timing = []
    for r in read('delegations.csv'):
        if r.get('population') != 'development' or r.get('role') in ('canary','other') or not r.get('completed_at'):
            continue
        candidates = [d for d in delegates if d['task'] == r['task']]
        for d in candidates:
            timing.append({'task': r['task'], 'receipt_status': r['status_receipt'],
                'tool_result': d['ts_result'], 'receipt_completion': r['completed_at'],
                'result_precedes_completion_seconds': round((ts(r['completed_at'])-ts(d['ts_result'])).total_seconds(),3)})
    with (ROOT/'data/delegate_result_timing.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(timing[0])); writer.writeheader(); writer.writerows(timing)
    result = {'shadow_price_original_formula': summ([r['reported_formula_usd'] for r in prices]),
        'shadow_price_four_component_formula': summ([r['four_component_formula_usd'] for r in prices]),
        'followup_censoring': {'cutoff': cutoff.isoformat(), 'code_commits': len(code), **mature},
        'codex_named_delegate_tool_results': len(timing),
        'tool_result_before_actual_receipt_completion': sum(r['result_precedes_completion_seconds'] > 0 for r in timing),
        'causal_status': 'Sensitivity checks only; retain original attribution and fitted rates, not a replacement baseline.'}
    (ROOT/'data/metric_sensitivity.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
