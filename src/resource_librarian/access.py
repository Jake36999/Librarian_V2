"""Central authorship/result boundary and session-scoped publication provenance."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .rules import Refusal

AUTHORSHIP = frozenset({'owner_created', 'generated', 'third_party'})
PURPOSE_AUTHORSHIP = {'own-current': 'owner_created', 'own-legacy': 'owner_created',
                     'own-docs': 'owner_created', 'research-docs': 'third_party',
                     'third-party': 'third_party'}


def person(ctx):
    return ctx.extras.get('caller_kind') == 'person'


def session_sources(ctx):
    if not ctx.session or ctx.vault is None or person(ctx):
        return []
    from .session import SessionStore
    return sorted(SessionStore(ctx.vault).load(ctx.session).taint_sources)


def canonical(spec):
    from .closure import _PROMOTE, _PUBLISH
    return spec.name != 'record_application' and (spec.effect == 'vault_write'
        or spec.name in _PROMOTE | _PUBLISH | {'project_edit'})


def publication_guard(spec, arguments, ctx):
    """Return sources for a mandatory person ask, or refuse before any mutation."""
    sources = session_sources(ctx)
    if not sources or not canonical(spec):
        return []
    if ctx.extras.get('broker') is not None:
        return sources
    raise Refusal('COMPOSITION_REFUSED',
        f'{spec.name}: canonical publication after untrusted input from {sources}. '
        'Use stage_artifact / staging for person review; further reads and work state remain allowed.',
        {'taint_sources': sources, 'staging_route': 'stage_artifact'})


def application_provenance(ctx):
    return {'authorship': 'generated', 'taint_sources': session_sources(ctx)}


def label_generated_write(spec, result, ctx):
    """Within the writer operation, before revision issuance: agent notes are generated."""
    if (person(ctx) or spec.name not in {'create_project', 'update_project', 'write_note', 'edit_note'}
            or not isinstance(result, dict) or ctx.vault is None):
        return
    from . import notes
    from .coordination import atomic_write_text
    for key in ['path', 'written', 'created']:
        rel = result.get(key)
        if not isinstance(rel, str):
            continue
        from .credentials import credential_path
        p = (ctx.vault.root / rel).resolve()
        if credential_path(rel) or not p.is_relative_to(ctx.vault.root.resolve()) or p.suffix != '.md' or not p.is_file():
            continue
        note = notes.load(p)
        note.frontmatter.update(application_provenance(ctx))
        atomic_write_text(p, notes.render(note.frontmatter, note.body))
        break


def _geo_sources(value):
    """Only called for an operator-accepted, digest-bound Geo connector."""
    out = []
    if isinstance(value, dict):
        authorship = value.get('authorship', value.get('provenance'))
        handle = value.get('cite_as') or value.get('graph_id') or value.get('snapshot_id')
        if handle and ((isinstance(authorship, str) and authorship in AUTHORSHIP)
                       or ('authorship' in value and authorship is None)):
            out.append({'handle': str(handle), 'authorship': authorship})
        for child in value.values():
            out.extend(_geo_sources(child))
    elif isinstance(value, list):
        for child in value:
            out.extend(_geo_sources(child))
    elif isinstance(value, str) and value.lstrip().startswith(('{', '[')):
        import json
        try:
            out.extend(_geo_sources(json.loads(value)))
        except (ValueError, RecursionError):
            pass
    return out


def _native_authorship(ctx, value):
    """Resolve source handles from accepted folders/explicit note frontmatter."""
    if ctx.vault is None or not isinstance(value, str):
        return None
    from .credentials import credential_path
    from .folder_review import decision_for
    from . import notes
    if credential_path(value):
        return None
    path = Path(value)
    path = path if path.is_absolute() else ctx.vault.root / path
    decision = decision_for(ctx.vault, path)
    if decision:
        resolved = decision.get('authorship') or PURPOSE_AUTHORSHIP.get(decision.get('purpose'))
        if resolved in AUTHORSHIP:
            return resolved
        return None  # a child purpose overrides its parent, even when unclassified
    from .content_roots import load
    manifest = load(ctx.vault.root) or {}
    declared = []
    for root in manifest.get('roots', []):
        base = Path(root['path'])
        base = base if base.is_absolute() else ctx.vault.root / base
        if path.resolve().is_relative_to(base.resolve()):
            declared.append((len(base.parts), root.get('authorship')))
    if declared:
        resolved = max(declared, key=lambda item: item[0])[1]
        if resolved in AUTHORSHIP:
            return resolved
    if path.is_file() and path.suffix.lower() == '.md' and path.resolve().is_relative_to(ctx.vault.root.resolve()):
        resolved = notes.load(path).frontmatter.get('authorship')
        if resolved in AUTHORSHIP:
            return resolved
    return None


def result_access(spec, arguments, result, ctx):
    if not spec.external and 'error' in result:
        # Do not open a denied/refused source merely to decorate its error.
        return {'sources': [{'handle': 'native:' + spec.name, 'authorship': 'generated'}], 'taint_sources': []}
    if not spec.external and spec.name == 'read_source_file':
        # A generated/owner-curated catalogue note is not proof that the
        # external repository bytes it names are ours. Use the graph's typed
        # provenance for trusted own-code reads; legacy aliases stay explicit.
        handle = 'source:' + str(arguments.get('source', '')) + '/' + str(arguments.get('path', ''))
        return {'sources': [{'handle': handle, 'authorship': None,
                             'authorship_resolution': 'unclassified'}], 'taint_sources': [handle]}
    if not spec.external and spec.name in {'pdf_to_markdown', 'ocr_pdf'} and arguments.get('file'):
        handle = str(arguments['file'])
        authorship = _native_authorship(ctx, handle)
        return {'sources': [{'handle': handle, 'authorship': authorship,
            **({'authorship_resolution': 'unclassified'} if authorship is None else {})}],
            'taint_sources': [handle] if authorship not in {'owner_created', 'generated'} else []}
    if not spec.external and spec.name == 'read_evidence' and ctx.vault and arguments.get('evidence_id'):
        from .evidence import EvidenceStore
        store = EvidenceStore(ctx.vault)
        record = store.get(str(arguments['evidence_id']))
        if record and store.intact(record) and record.authorship in AUTHORSHIP:
            handle = 'evidence:' + record.id
            return {'sources': [{'handle': handle, 'authorship': record.authorship}],
                    'taint_sources': [handle] if record.authorship == 'third_party' else []}
    if spec.external:
        sources = _geo_sources(result) if spec.provenance_authority == 'geographer' else []
        if not sources:
            import hashlib
            import json
            identity = hashlib.sha256(json.dumps(arguments, sort_keys=True, default=str).encode()).hexdigest()[:16]
            sources = [{'handle': 'external:' + spec.name + ':' + identity, 'authorship': 'third_party'}]
    elif spec.open_world:
        handle = next((str(arguments[k]) for k in ['url', 'source', 'path', 'evidence_id']
                       if arguments.get(k)), spec.name)
        sources = [{'handle': handle, 'authorship': 'third_party'}]
    else:
        sources = []
        def visit(value):
            if isinstance(value, dict):
                for key in ['path', 'source', 'source_path', 'note', 'name', 'project']:
                    handle = value.get(key)
                    if isinstance(handle, str):
                        authorship = _native_authorship(ctx, handle)
                        if authorship is None and key in {'name', 'note', 'source', 'project'} and ctx.vault:
                            from . import notes
                            matches = [p for p in notes.iter_paths(ctx.vault.root)
                                       if p.stem.casefold() == handle.casefold()]
                            if len(matches) == 1:
                                authorship = _native_authorship(ctx, str(matches[0]))
                        if authorship:
                            sources.append({'handle': handle, 'authorship': authorship})
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        visit(arguments)
        visit(result)
        if spec.name == 'read_project' and ctx.session and ctx.vault:
            from .session import SessionStore
            from .tools.sessions import _project_root
            project = SessionStore(ctx.vault).load(ctx.session).project
            try:
                root = _project_root(ctx, project)
                handle = str(root / arguments.get('path', ''))
                authorship = _native_authorship(ctx, handle)
                if authorship:
                    sources.append({'handle': handle, 'authorship': authorship})
            except (Refusal, ValueError, TypeError):
                pass
        if not sources:
            # A native work/control result is generated. Source readers without a
            # resolvable author are conservatively untrusted, never declared own.
            reader = spec.name in {'read_file', 'read_source_file', 'read_evidence',
                                  'read_source_section', 'verify_source_pages',
                                  'get_note', 'deep_read', 'deep_read_note', 'read_project',
                                  'search', 'search_work', 'read_result', 'web_search'}
            if result.get('found') is False or (spec.name in {'search', 'search_work'} and result.get('results') == []):
                reader = False
            handle = next((str(arguments[k]) for k in ['path', 'source', 'evidence_id', 'name']
                           if isinstance(arguments.get(k), str) and arguments[k]), 'native:' + spec.name)
            sources = [{'handle': handle,
                        'authorship': None if reader else 'generated'}]
    sources = sorted({(s['handle'], s['authorship']) for s in sources}, key=lambda s: (s[0], s[1] or ''))
    rows = [{'handle': h, 'authorship': a, **({'authorship_resolution': 'unclassified'} if a is None else {})}
            for h, a in sources]
    return {'sources': rows, 'taint_sources': sorted({h for h, a in sources if a not in {'owner_created', 'generated'}})}


def finalize_result(spec, arguments, result, ctx):
    from .access_classes import READ_PERMISSION_CONTROLS
    if not spec.external and spec.name in READ_PERMISSION_CONTROLS:
        return result  # Permission metadata does not itself read the named source.
    access = result_access(spec, arguments, result, ctx)
    publication_session = ctx.session or ctx.extras.get('_publication_session')
    if ('error' not in result or spec.external) and access['taint_sources'] and not person(ctx) and publication_session and ctx.vault:
        from .session import SessionStore
        SessionStore(ctx.vault).append(publication_session, {'type': 'taint',
            'sources': access['taint_sources'], 'tool': spec.name})
    # Person-only/control calls are class C, outside the model-content
    # conformance denominator. Preserve their existing receipt shape.
    from .access_classes import CONTROL_TOOLS
    if person(ctx) or spec.tier == 'curate' or (not spec.external and spec.name in CONTROL_TOOLS):
        return result
    return {**result, 'access': access}


def clear_taint(ctx, checkpoint_id):
    from .session import SessionStore
    from .checkpoints import CheckpointStore
    if not person(ctx) or ctx.tier != 'curate' or not ctx.session:
        raise Refusal('PERMISSION_DENIED', 'Only a person can clear session provenance through a scoped checkpoint')
    store = SessionStore(ctx.vault)
    sources = sorted(store.load(ctx.session).taint_sources)
    cp = CheckpointStore(ctx.vault).get(checkpoint_id)
    used = any(e.get('type') == 'taint_clear' and e.get('checkpoint') == checkpoint_id
               for e in store.events(ctx.session))
    if (cp['type'] != 'publication_taint' or cp['scope'] != ctx.session or cp.get('expired')
            or cp['resolution'] != 'approve' or cp['evidence'].get('session') != ctx.session
            or sorted(cp['evidence'].get('sources', [])) != sources or used):
        raise Refusal('PERMISSION_DENIED', 'Approve a fresh checkpoint listing this session and its exact taint sources')
    store.append(ctx.session, {'type': 'taint_clear', 'sources': sources,
                               'checkpoint': checkpoint_id, 'by': 'person'})
    return {'cleared_sources': sources, 'session_id': ctx.session}
