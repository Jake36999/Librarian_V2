"""Check the review's coverage, verified anchors, links and input fingerprints."""
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'2026-10-28-agent-workflow-sprint'

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    coverage=list(csv.DictReader((ROOT/'data/literature_coverage.csv').open(encoding='utf-8')))
    claims=list(csv.DictReader((ROOT/'data/claim_review.csv').open(encoding='utf-8')))
    anchors=json.loads((ROOT/'data/supplement_methods.json').read_text(encoding='utf-8'))
    assert len(coverage)==50 and len({r['file'] for r in coverage})==50
    assert len(claims)==58 and len({r['id'] for r in claims})==58
    assert len(anchors)==25 and all(r['exact_page_verified'] for r in anchors)
    assert all(r['second_pass_status'] and r['reason'] for r in claims)
    broken=[]
    for md in ROOT.glob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',md.read_text(encoding='utf-8')):
            if not target.startswith(('https://','http://')) and not (md.parent/target.split('#')[0]).exists():
                broken.append({'file':md.name,'target':target})
    assert not broken,broken
    files=sorted(p for p in SOURCE.rglob('*') if p.is_file() and '__pycache__' not in str(p))
    manifest={str(p.relative_to(SOURCE)).replace('\\','/'):digest(p) for p in files}
    dest=ROOT/'data/reviewed_input_hashes.json'
    if dest.exists():
        assert json.loads(dest.read_text(encoding='utf-8'))==manifest,'Original sprint artifacts changed during verification'
    dest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    result={'pdf_coverage':len(coverage),'outside_claim_dispositions':len(claims),
        'new_exact_page_anchors':len(anchors),'broken_local_links':len(broken),'original_artifacts_fingerprinted':len(files)}
    (ROOT/'data/validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
