"""Independent, read-only checks of Claude's sprint inputs; writes only this review.

Run with .venv/Scripts/python.exe -I <this file>. No API calls or raw log exports.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import re
import sys
import fitz

REPO = Path(r'D:\Librarian_V2')
ORIGINAL = REPO / 'reports/2026-10-28-agent-workflow-sprint'
OUT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from resource_librarian.clerk import quoted

def rows(name):
    with (ORIGINAL / 'data' / name).open(encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save(name, value):
    p = OUT / 'data' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

def csvsave(name, values):
    p = OUT / 'data' / name
    p.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for v in values for k in v))
    with p.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(values)

def main():
    paper_rows = rows('reading_list_ranked.csv')
    inventory = {r['file']: r for r in rows('papers_inventory.csv')}
    papers = {}
    pdf_checks = []
    for r in paper_rows:
        path = Path(r'E:\Librarian research') / r['file']
        content = path.read_bytes()
        doc = fitz.open(path)
        pages = [p.get_text() for p in doc]
        papers[r['slug']] = pages
        p = OUT / 'data' / 'paper_text' / f"rank-{int(r['rank']):02d}.txt"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('\n'.join(f'[[PAGE {i}]]\n{t}' for i, t in enumerate(pages, 1)), encoding='utf-8')
        pdf_checks.append({'rank': int(r['rank']), 'file': r['file'], 'slug': r['slug'],
            'pages': len(pages), 'sha256': hashlib.sha256(content).hexdigest(),
            'matches_original_hash': hashlib.sha256(content).hexdigest() == inventory[r['file']]['sha256']})
    save('pdf_identity.json', pdf_checks)
    cards = [json.loads(s) for s in (ORIGINAL / 'data/method_cards.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    checks = []
    for c in cards:
        rank = re.search(r'P2-r(\d+)-', c.get('call', ''))
        canonical = next((r['slug'] for r in paper_rows if rank and int(r['rank']) == int(rank[1])), c['paper'])
        ps = papers.get(canonical, [])
        p = int(c.get('page') or 0)
        exact = [i for i, s in enumerate(ps, 1) if quoted(str(c.get('quote') or ''), s)]
        checks.append({'call': c.get('call'), 'paper': canonical, 'name': c.get('name'),
            'claimed_page': p, 'original_status': c.get('verified'), 'exact_page_match': p in exact,
            'actual_matching_pages': ';'.join(map(str, exact)),
            'within_one_page': any(abs(i-p) <= 1 for i in exact)})
    csvsave('exact_page_checks.csv', checks)
    save('card_coverage.json', {'counts': dict(Counter(c['paper'] for c in cards)),
        'verified_exact_page': sum(c['original_status'] == 'verified' and c['exact_page_match'] for c in checks),
        'verified_wrong_page': [c for c in checks if c['original_status'] == 'verified' and not c['exact_page_match']]})

    # Reconcile saved per-request sums against saved cumulative counters.
    reqs = rows('codex_requests.csv')
    sums = Counter()
    for r in reqs:
        sums[r['thread']] += int(r['total_tokens'])
    thread_groups = defaultdict(list)
    for r in rows('codex_threads.csv'):
        if int(r['requests']):
            thread_groups[r['thread']].append(r)
    reconciled = [{'thread': tid, 'kind': rs[0]['kind'], 'rollout_files': len(rs), 'sum_last_total': sums[tid],
        'final_cumulative': max(int(r['cumulative_total_max']) for r in rs),
        'difference': sums[tid] - max(int(r['cumulative_total_max']) for r in rs)}
        for tid, rs in thread_groups.items()]
    csvsave('codex_counter_reconciliation.csv', reconciled)

    # Original delegate parser uses a substring test, which also matches reads/edits.
    wanted = {(r['thread'], r['ts_call']) for r in rows('codex_delegates.csv')}
    found = []
    cmd_pattern = re.compile(r'\bcmd[\"\x27]?\s*:\s*("(?:[^"\\]|\\.)*"|\x27(?:[^\x27\\]|\\.)*\x27|`(?:[^`\\]|\\.)*`)')
    for path in (Path.home() / '.codex/sessions/2026').glob('*/*/rollout-*.jsonl'):
        with path.open(encoding='utf-8') as f:
            try:
                meta = json.loads(next(f))['payload']
            except (ValueError, StopIteration, KeyError):
                continue
            tid = meta.get('id')
            if tid not in {x[0] for x in wanted}:
                continue
            for raw in f:
                o = json.loads(raw)
                if (tid, o.get('timestamp')) not in wanted:
                    continue
                p = o.get('payload', {})
                if p.get('type') not in ('function_call', 'custom_tool_call'):
                    continue
                body = str(p.get('input') or p.get('arguments') or '')
                cmds = []
                for s in cmd_pattern.findall(body):
                    try:
                        cmds.append(json.loads(s) if s[0] == '"' else s[1:-1])
                    except ValueError:
                        cmds.append(s[1:-1])
                cmd = '\n'.join(cmds) if cmds else body
                # Actual dispatch needs an interpreter invocation, script path and task/model flags.
                launch = bool(re.search(r'(?:python(?:\.exe)?|python3|py|\.venv[^\r\n]{0,50}python\.exe)[^\r\n;&|]{0,130}delegate_deepinfra\.py\s+[^\r\n]*--(?:task|model)\b', cmd, re.I))
                help_only = bool(re.search(r'delegate_deepinfra\.py\s+(?:--help|-h)\b', cmd))
                inspection = bool(re.search(r'\b(?:Get-Content|rg|Select-String|git\s+(?:show|diff))\b', cmd, re.I))
                found.append({'thread': tid, 'ts_call': o['timestamp'], 'tool': p.get('name'),
                    'actual_launch_signature': launch, 'help_only': help_only,
                    'inspection_signature': inspection, 'command_sha256': hashlib.sha256(cmd.encode()).hexdigest(),
                    'has_task_flag': '--task' in cmd, 'has_model_flag': '--model' in cmd})
    csvsave('delegate_classification_audit.csv', found)

    # Raw fields are totals only; no transcript content is saved.
    summary = {'pdfs_checked': len(pdf_checks), 'pdf_hashes_match': all(r['matches_original_hash'] for r in pdf_checks),
        'method_cards': len(cards), 'originally_verified_cards': sum(c['original_status'] == 'verified' for c in checks),
        'verified_wrong_page': sum(c['original_status'] == 'verified' and not c['exact_page_match'] for c in checks),
        'codex_threads_reconciled': len(reconciled), 'codex_counter_mismatches': sum(r['difference'] != 0 for r in reconciled),
        'codex_original_delegate_rows': len(wanted), 'codex_rows_located': len(found),
        'codex_launch_signatures': sum(r['actual_launch_signature'] for r in found),
        'codex_inspection_signatures': sum(r['inspection_signature'] for r in found),
        'codex_rows_with_task_and_model': sum(r['has_task_flag'] and r['has_model_flag'] for r in found)}
    save('independent_checks.json', summary)
    print(json.dumps(summary, indent=2))

if __name__ == '__main__':
    main()
