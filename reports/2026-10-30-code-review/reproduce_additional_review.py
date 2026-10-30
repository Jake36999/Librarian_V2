"""Disposable-vault checks for the additional review; no provider/network calls.
Assertions record observed behavior, not desired regression expectations.
"""
import json
import os
import tempfile
from pathlib import Path
from resource_librarian import tools, notes, schema
from resource_librarian.init import init
from resource_librarian.vault import Vault
from resource_librarian.content_roots import apply_adopt, plan_adopt
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.index import Index
from resource_librarian.search import Engine, search

with tempfile.TemporaryDirectory(prefix='librarian-additional-review-') as temporary:
    root = Path(temporary)
    os.environ['LIBRARIAN_CONFIG_DIR'] = str(root / 'config')
    docs = root / 'Docs'
    def write(rel, text):
        path = docs / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return path

    write('README.md', '# Canary rollout\n\nA blue-green canary rollout guide.\n')
    write('guide/link.md', '# Guide\n\n[[Managed]]\n')
    write('site/README.md', '---\ntitle: Site\n---\n# Site\n')
    write('api/README.md', '---\ntitle: API\n---\n# API\n')
    plan = plan_adopt(docs)
    apply_adopt(docs, plan['survey_fingerprint'])
    vault = Vault(docs)
    init(root / 'starter')
    write(str(schema.MODEL_PATH), (root / 'starter' / schema.MODEL_PATH).read_text(encoding='utf-8'))
    write('Concepts/Managed.md', '---\ntype: concept\ntitle: Managed\n---\n# Managed\n')
    plain = write('Sources/PreviouslyManaged.md', '# Missing frontmatter\n')
    result = REGISTRY.call('check_notes', {}, Context(tier='consult', vault=vault))
    assert 'error' not in result, result
    violations = result['violations']
    assert any(v['check'] == 'unique_note_names' and v['note'] == 'README' for v in violations)
    assert any(v['check'] == 'orphan_notes' and v['note'] == 'Managed' for v in violations)
    direct = schema.load(docs).check(notes.load(plain), docs)
    assert direct and not any(v['note'] == 'PreviouslyManaged' for v in violations)
    print(json.dumps({'finding': 'validation_classification_and_links',
                      'frontmattered_README_duplicates_flagged': True,
                      'workspace_link_ignored_causes_orphan': True,
                      'plain_source_folder_document_exempt': True,
                      'classification_note': 'Plain source-folder documents are intentionally workspace documents under current policy.'}))
    with Index(vault) as index:
        index.refresh()
        engine = Engine(index, vault.config()['heuristics'])
        workspace = search(engine, 'blue-green canary rollout', 'workspace')
        everything = search(engine, 'blue-green canary rollout', 'all', source='does-not-exist', max_age_days=1)
        orient = search(engine, 'blue-green canary rollout', 'orient')
        assert workspace.results
        assert any(r.fields.get('intent') == 'workspace' for r in everything.results)
        assert everything.verdict == orient.verdict and everything.considered == orient.considered
        print(json.dumps({'finding': 'all_search_metadata', 'workspace_verdict': workspace.verdict,
                          'all_verdict': everything.verdict, 'all_considered': everything.considered,
                          'all_matched': everything.matched,
                          'workspace_results': len(workspace.results),
                          'nonexistent_source_argument_did_not_restrict_workspace': True,
                          'guidance_omits_workspace': 'workspace' not in everything.next_step}))
