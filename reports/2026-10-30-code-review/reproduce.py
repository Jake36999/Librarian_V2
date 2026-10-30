"""Read-only product review: reproduce defects in disposable fixture vaults.
Run from checkout: $env:PYTHONPATH='src'; python reports/2026-10-30-code-review/reproduce.py
Assertions describe observed defects, not desired regression-test expectations.
"""
import json
import os
import tempfile
from pathlib import Path

from resource_librarian import tools, closure_audit, audit_events
from resource_librarian.init import init
from resource_librarian.vault import Vault
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import SessionStore
from resource_librarian.content_roots import plan_adopt, apply_adopt, iter_documents


def call(ctx, tool_name, **args):
    result = REGISTRY.call(tool_name, args, ctx)
    assert 'error' not in result and 'refused' not in result, (tool_name, result)
    return result


with tempfile.TemporaryDirectory(prefix='librarian-review-') as temporary:
    root = Path(temporary)
    os.environ['LIBRARIAN_CONFIG_DIR'] = str(root / 'config')
    init(root / 'vault', name='Review fixture')
    vault = Vault(root / 'vault')
    evidence = EvidenceStore(vault)
    source_a = evidence.put('page', 'https://example.org/source-a', {'text': 'Source A has no expected quotation.'})
    source_b = evidence.put('page', 'https://example.org/source-b', {'text': 'A completely unrelated quotation in source B.'})
    lead = Context(tier='contribute', vault=vault)
    call(lead, 'open_session', purpose='audited', question='Quote source A')
    person = Context(tier='curate', vault=vault, session=lead.session)
    predicate = 'the requested quotation is located in source A'
    call(person, 'set_requirement', requirement_id='R1', text='Quote source A only',
         predicates=[predicate], verifiers={predicate: 'quote.located'})
    call(lead, 'update_plan', fields={'proposal': {'requirements': ['R1'], 'step': 'quote source A'}})
    call(lead, 'advance')
    call(lead, 'admit_contract', contract_id='C1', requirements=['R1'], operations=['read'],
         read=[], write=[], verifiers={f'R1: {predicate}': 'quote.located'})
    call(lead, 'advance')
    ordinary = next(p for p in vault.root.rglob('*.md') if not any(x.startswith('.') for x in p.relative_to(vault.root).parts))
    read_outside = call(lead, 'get_note', name=ordinary.stem)
    assert read_outside.get('found') is True
    engine = lead.extras.pop('engine', None)
    if engine is not None:
        engine.index.close()
    print(json.dumps({'finding': 'registry_get_note_outside_scope', 'read_targets': [], 'read_succeeded': True}))
    call(lead, 'advance')
    result = call(lead, 'verify_grain', requirement='R1', predicate=predicate,
                  params={'evidence': source_b.id, 'quote': 'A completely unrelated quotation'})
    call(lead, 'advance')
    reduction = call(lead, 'reduce_round')
    session = SessionStore(vault).load(lead.session)
    recheck = closure_audit.audit(vault, session)
    assert result['outcome'] == 'pass'
    assert reduction['reduced']['R1']['status'] == 'verified'
    assert not recheck['false_closures']
    print(json.dumps({'finding': 'wrong_source_closure', 'status': 'verified',
                      'audit_verdict': recheck['rows'][0]['verdict']}))

    # A new contract can reuse prior reductions/results at the same epoch.
    call(lead, 'advance')
    call(lead, 'advance')
    call(lead, 'admit_contract', contract_id='C2', requirements=['R1'], operations=['read'],
         read=[], write=[], verifiers={f'R1: {predicate}': 'quote.located'})
    call(lead, 'advance')
    call(lead, 'advance')
    session = SessionStore(vault).load(lead.session)
    assert audit_events.unchecked_predicates(session.audit, 'C2') == []
    assert audit_events.unreduced_requirements(session.audit, 'C2') == []
    print(json.dumps({'finding': 'cross_contract_reuse', 'epoch': session.audit.epoch,
                      'current_contract': 'C2', 'result_contract': session.audit.results['V1']['contract']}))

    from resource_librarian.tools.audited import staging_folder
    editor = Context(tier='contribute', vault=vault)
    call(editor, 'open_session', purpose='audited', question='Keep draft unchanged')
    owner = Context(tier='curate', vault=vault, session=editor.session)
    call(owner, 'set_requirement', requirement_id='R1', text='Draft is unchanged',
         predicates=['draft unchanged'], verifiers={'draft unchanged': 'target.diff_clean'})
    call(editor, 'update_plan', fields={'proposal': {'requirements': ['R1'], 'step': 'stage draft'}})
    for cid, content in [('C1', 'original draft'), ('C2', 'replacement draft')]:
        call(editor, 'advance')
        call(editor, 'admit_contract', contract_id=cid, requirements=['R1'],
             write=[staging_folder(editor, editor.session)], operations=['read', 'stage'],
             verifiers={'R1: draft unchanged': 'target.diff_clean'})
        call(editor, 'advance')
        call(editor, 'stage_artifact', name='same-draft', text=content)
        call(editor, 'advance')
        if cid == 'C1': call(editor, 'verify_grain', requirement='R1', predicate='draft unchanged')
        call(editor, 'audit_targets')
        moved = call(editor, 'advance')
        assert moved['moved'] == 'reduce', moved
        call(editor, 'reduce_round')
        if cid == 'C1': call(editor, 'advance')
    changed = SessionStore(vault).load(editor.session)
    assert changed.audit.requirement_status('R1') == 'verified'
    assert closure_audit.audit(vault, changed)['false_closures']
    print(json.dumps({'finding': 'changed_draft_stays_verified', 'status': 'verified',
                      'closure_recheck': 'fails', 'current_contract': 'C2'}))

    # Authorizer uses parameter-name heuristics, missing get_note's name argument.
    from types import SimpleNamespace
    from resource_librarian import closure
    spec = SimpleNamespace(name='get_note', effect='read', open_world=False)
    executing = SimpleNamespace(purpose='audited', phase='execute', audit=session.audit, contract_calls={})
    approved = closure.authorize(executing, spec, {'name': 'Outside the empty read scope'}, None, vault)
    assert approved['class'] == 'read'
    print(json.dumps({'finding': 'get_note_read_scope_bypass', 'read_targets': [], 'authorized': True}))

    # Explicitly excluded files and hidden Markdown files still enter the walker.
    adopted = root / 'adopted'; adopted.mkdir()
    (adopted / 'visible.md').write_text('visible', encoding='utf-8')
    (adopted / 'private.md').write_text('excluded', encoding='utf-8')
    (adopted / '.secret.md').write_text('hidden', encoding='utf-8')
    plan = plan_adopt(adopted, excludes=['private.md'])
    apply_adopt(adopted, plan['survey_fingerprint'], excludes=['private.md'])
    found = [p.name for p in iter_documents(adopted)]
    assert 'private.md' in found and '.secret.md' in found
    print(json.dumps({'finding': 'adopted_file_exclusions_ignored', 'indexed_candidates': found}))

    if os.name == 'nt':
        import subprocess
        external = root / 'external'; external.mkdir()
        (external / 'outside.md').write_text('outside approved root', encoding='utf-8')
        junction = adopted / 'linked'
        made = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)], capture_output=True, text=True)
        assert made.returncode == 0, made.stderr
        leaked = [p.relative_to(adopted).as_posix() for p in iter_documents(adopted)]
        assert 'linked/outside.md' in leaked
        print(json.dumps({'finding': 'junction_followed', 'outside_root_file': 'linked/outside.md'}))
