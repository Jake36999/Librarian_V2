"""Read-only evidence validation plus reproducible packaging of this review.

No network or paid calls. Does not run or alter the product or earlier reports.
"""
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
WORK = REPO / 'tmp/overseer-workflow'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def readjson(path):
    return json.loads(path.read_text(encoding='utf-8'))


def absolute_links(path):
    # Our prose links have no nested brackets; spaces/parentheses use <targets>.
    pattern = r'\[([^\]\n]+)\]\((<[^>\n]+>|[^)\n]+)\)'
    def replace(match):
        label, target = match.groups()
        target = target.strip('<>')
        if re.match(r'^[a-z]+://', target):
            return match.group(0)
        suffix = re.search(r':\d+$', target)
        line = suffix.group(0) if suffix else ''
        bare = target[:-len(line)] if line else target
        p = Path(bare)
        if not p.is_absolute():
            p = (path.parent / p).resolve()
        assert p.exists(), (path.name, target)
        result = p.as_posix() + line
        if ' ' in result or '(' in result:
            result = '<' + result + '>'
        return f'[{label}]({result})'
    old = path.read_text(encoding='utf-8')
    new = re.sub(pattern, replace, old)
    if new != old:
        path.write_text(new, encoding='utf-8')
    return len(re.findall(pattern, new))


def main():
    manifest = readjson(ROOT / 'data/source_manifest.json')
    for source in manifest:
        assert digest(Path(source['path'])) == source['sha256'], source['id']
        lines = Path(source['prepared']).read_text(encoding='utf-8').splitlines()
        assert len(lines) == source['lines']
        assert all(line.startswith(f'L{i:05d}| ') for i, line in enumerate(lines, 1))

    plan = readjson(WORK / 'calls.json')
    expected = {c['id'] for c in plan if c['phase'] in ('extract', 'public-critic')}
    receipts = [readjson(p) for p in sorted((WORK / 'runs').glob('*.receipt.json'))]
    assert len(receipts) == len(expected) == 14
    assert {r['task'] for r in receipts} == expected
    assert all(r['status'] == 'completed' and r['finish_reason'] == 'stop' for r in receipts)
    ledger = readjson(ROOT / 'data/deepinfra-ledger.json')
    assert all(r['status'] == 'completed' for r in ledger['calls'])
    total = sum(r['estimated_cost_usd'] for r in receipts)
    assert abs(total - ledger['committed_usd']) < 0.0000001
    assert 0 < total < 5.0
    archive = ROOT / 'data/calls'
    archive.mkdir(exist_ok=True)
    index = []
    request_ids = []
    for r in receipts:
        src = next(p for p in (WORK / 'runs').glob('*.receipt.json') if readjson(p)['task'] == r['task'])
        receipt_path = archive / f"{r['task']}.receipt.json"
        output_path = archive / f"{r['task']}.output.txt"
        shutil.copyfile(src, receipt_path)
        shutil.copyfile(Path(r['output_path']), output_path)
        request_id = r.get('request_id') or r.get('provider_request_id')
        assert request_id, r['task']
        request_ids.append(request_id)
        index.append({'task': r['task'], 'receipt': str(receipt_path),
                      'output': str(output_path), 'receipt_sha256': digest(receipt_path),
                      'output_sha256': digest(output_path), 'original_receipt': str(src)})
    assert len(set(request_ids)) == len(receipts)
    save(ROOT / 'data/call_archive.json', index)
    save(ROOT / 'data/call_plan.json', plan)
    shutil.copyfile(WORK / 'dispatch.jsonl', ROOT / 'data/dispatch.jsonl')

    observed = [REPO / p for p in ['scripts/delegate_deepinfra.py',
                'docs/unified-implementation-plan.md', 'tests/test_openai_chat_adapter.py',
                'tests/test_anthropic_messages_adapter.py',
                'reports/2026-10-28-index05-attachment-scan-reduction.md']]
    save(ROOT / 'data/inspected_file_hashes.json', [
        {'path': str(p), 'sha256': digest(p)} for p in observed])

    # These are locally adjudicated case anchors. They are intentionally separate
    # from the remote reader's labels, which remain UNADJUDICATED.
    cases = [
        ('E2', 'claude', 985, '0.009', 'pasted call result', 'A cheap draft returned; acceptance and integration were separate.'),
        ('E2', 'claude', 1077, 'IndexError: list index out of range', 'pasted tool failure', 'Application failed after implementation write and before test creation.'),
        ('E3', 'codex2', 3186, 'retried it three times', 'lead report', 'Historical hidden retries; current runner inspected and now disables retries.'),
        ('E4', 'codex2', 2452, 'not delegating to DeepInfra', 'lead correction', 'Native Codex workers are not external DeepInfra evidence.'),
        ('E4', 'codex2', 760, 'switched the checkout', 'lead report', 'Concurrency/ownership evidence; not evidence of DeepInfra performance.'),
        ('E5', 'research', 1806, 'The brief forbids novelty claims', 'pasted correction code', 'Correction exists; no completeness claim about all notes.'),
        ('E5', 'research', 3860, 'Notes are FIRST DRAFTS', 'pasted script text', 'Draft status is explicit; budget comment is not execution proof.'),
        ('E6', 'research', 2768, 'ImportError: numpy.core.multiarray failed to import', 'pasted tool failure', 'Environment failure, not proof of worker reasoning failure.'),
        ('E6', 'research', 973, 'Five errors of my own', 'lead retrospective', 'Motivates independent computations; physics not rederived here.'),
        ('E7', 'research', 430, 'Both agents hit a server overload', 'lead report', 'Does not identify the infrastructure cause.'),
        ('E8', 'gemini', 207, 'unless two sub-agents flag a conflict', 'proposal', 'Disagreement-only lead auditing misses correlated errors.'),
        ('E8', 'gemini', 216, 'Only review flagged discrepancies', 'proposal', 'Need audit of apparently passing cases and coverage.'),
    ]
    curated = []
    for case, sid, number, anchor, kind, judgment in cases:
        line = (ROOT / f'data/sources/{sid}.txt').read_text(encoding='utf-8').splitlines()[number - 1]
        assert anchor in line, (case, sid, number, anchor)
        curated.append({'case': case, 'source': sid, 'line': number, 'anchor': anchor,
                        'kind': kind, 'judgment': judgment, 'status': 'LOCALLY_ADJUDICATED'})
    save(ROOT / 'data/curated_cases.json', curated)
    critic = readjson(ROOT / 'data/critic_findings.json')
    dispositions = readjson(ROOT / 'data/critic_dispositions.json')
    assert len(critic) == len(dispositions) == 7
    assert all(f['report_quote_present'] for f in critic)
    assert {f['id'] for f in critic} == {d['id'] for d in dispositions}
    anchors = readjson(ROOT / 'data/worker_episodes.json')
    rejected = readjson(ROOT / 'data/rejected_outputs.json')
    assert len(anchors) == 100 and len(rejected) == 4
    assert all(r['anchor_valid'] and r['status'] == 'UNADJUDICATED' for r in anchors)

    links = {name: absolute_links(ROOT / name) for name in ['REPORT.md', 'EVIDENCE.md']}
    checks = {
        'finished_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Review and recommendation; no controller implementation or savings benchmark',
        'source_original_hashes_unchanged': len(manifest),
        'source_lines': sum(s['lines'] for s in manifest),
        'completed_paid_calls': len(receipts),
        'reader_calls': 13, 'abstract_critic_calls': 1,
        'api_usage_estimate_usd': round(total, 8),
        'ledger_committed_usd': ledger['committed_usd'], 'budget_usd': 5.0,
        'pending_or_unknown_calls': 0,
        'input_tokens': sum(r['usage']['input_tokens'] for r in receipts),
        'output_tokens': sum(r['usage']['output_tokens'] for r in receipts),
        'anchored_unadjudicated_episodes': len(anchors), 'rejected_anchors': len(rejected),
        'locally_adjudicated_transcript_anchors': len(curated),
        'critic_findings_dispositioned': len(dispositions),
        'private_critic_export_blocked_and_not_executed': True,
        'checked_local_markdown_links_and_external_syntax': links,
        'product_tests_rerun': False,
        'product_files_modified_by_this_review': False,
        'archive': str(ROOT / 'data/call_archive.json'),
        'report_sha256': digest(ROOT / 'REPORT.md'),
        'evidence_sha256': digest(ROOT / 'EVIDENCE.md'),
    }
    save(ROOT / 'data/completion.json', checks)
    print(json.dumps(checks, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()
