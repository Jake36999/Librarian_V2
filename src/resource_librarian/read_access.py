"""Central read policy and route-clamped token allocations (S4)."""
from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path
from dataclasses import replace

from .rules import Refusal

ROUTE = ['catalogue', 'graph', 'section', 'verify_source_pages']
PLANNING_CHARACTERS_PER_TOKEN = 4
MEASUREMENT = 'UTF-8 bytes of serialized content: conservative token upper bound, not a model tokenizer'


def measure(value):
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(',', ':'), default=str)
    return len(text.encode('utf-8'))


def allocate(route, *, requested_tokens=200000, sources=1, expected_output_tokens=0, tier=2):
    values = [route.get(k) for k in ('context_tokens', 'prompt_tokens', 'visible_output_tokens', 'reasoning_reserve_tokens')]
    if (not route.get('model') or any(type(v) is not int or v < 0 for v in values)
            or values[0] < 1 or values[2] < 1):
        raise Refusal('READ_ROUTE_REQUIRED', 'The actual bound route must declare its window, measured prompt, visible output and reasoning reserve')
    if type(sources) is not int or not 1 <= sources <= 100 or type(requested_tokens) is not int or requested_tokens < 0:
        raise TypeError('Use 1–100 sources and a nonnegative token request')
    window, prompt, visible, reasoning = values
    if type(expected_output_tokens) is not int or expected_output_tokens < 0:
        raise TypeError('Expected visible output is a nonnegative token count')
    if expected_output_tokens > visible:
        raise Refusal('TASK_OUTPUT_TOO_LARGE', 'Split the task before dispatch: its expected visible output exceeds this route',
                      {'expected_output_tokens': expected_output_tokens, 'visible_output_tokens': visible, 'tier': tier})
    available = max(0, window - prompt - visible - reasoning)
    effective = min(requested_tokens, available)
    quotient, remainder = divmod(effective, sources)
    return {**route, 'unit': 'tokens', 'requested_tokens': requested_tokens,
            'effective_tokens': effective, 'per_source_tokens': [quotient + (i < remainder) for i in range(sources)],
            'clamped': effective != requested_tokens, 'tier': tier,
            'expected_output_tokens': expected_output_tokens,
            'measurement': route.get('measurement', MEASUREMENT),
            'planning_characters_per_token': PLANNING_CHARACTERS_PER_TOKEN}


def raw_target(spec, arguments, ctx):
    from .access import _native_authorship
    if spec.name == 'read_project':
        if not arguments.get('path'):
            return None, None
        target = _project_file(ctx, arguments['path'])
        return str(target), _native_authorship(ctx, str(target))
    if spec.name == 'get_note':
        from .tools.library import IndexGateway
        row = IndexGateway(ctx, include_vectors=False).run(lambda engine: engine.index.note_row(arguments['name']))
        if row is not None and row['shape'] != 'source':
            author = _native_authorship(ctx, row['path'])
            if author == 'third_party':
                return row['path'], author
        return None, None  # A catalogue entry is the intended first access point.
    if spec.name == 'read_file':
        path = str(arguments.get('path') or '')
        from .tools.browse import _inside
        target = _inside(ctx, path)  # Validate before licence routing; no file is opened.
        return (path, _native_authorship(ctx, str(target))) if target.is_file() else (None, None)
    if spec.name == 'read_source_file':
        return 'repository:' + str(arguments.get('source')) + ':' + str(arguments.get('path')), None
    if spec.name == 'read_evidence':
        from .evidence import EvidenceStore
        record = EvidenceStore(ctx.vault).get(str(arguments.get('evidence_id') or ''))
        if record is not None:
            return 'evidence:' + record.id, record.authorship
    if spec.name in {'deep_read', 'deep_read_note'}:
        if spec.name == 'deep_read':
            from .staging import StagingStore
            item = StagingStore(ctx.vault).load(arguments['item_id'])
        else:
            from .tools.library import IndexGateway
            from . import notes
            row = IndexGateway(ctx, include_vectors=False).run(lambda engine: engine.index.note_row(arguments['note']))
            if row is None:
                return None, None
            item = notes.load(ctx.vault.root / row['path']).frontmatter
        target = item.get('file')
        return (str(target), _native_authorship(ctx, str(target))) if target else ('source:' + str(item.get('name', arguments)), None)
    return None, None


def _project_file(ctx, path):
    from .credentials import refuse_credentials
    from .session import SessionStore
    from .tools.sessions import _project_root
    refuse_credentials(path)
    session = SessionStore(ctx.vault).load(ctx.session)
    root = _project_root(ctx, session.project).resolve()
    target = (root / path).resolve()
    refuse_credentials(target)
    if root not in target.parents or not target.is_file():
        raise TypeError('Name a file inside the person-approved project')
    return target


def guard(spec, arguments, ctx, *, consume=False):
    from .access import person
    if person(ctx) or ctx.vault is None:
        return
    if spec.name == 'deep_read' and ctx.extras.get('_batch_run'):
        from .staging import StagingStore
        item = StagingStore(ctx.vault).load(arguments['item_id'])
        if item.get('status') == 'processing' and item.get('batch') == ctx.extras['_batch_run']:
            # Core-only capability from the curate-tier approved-batch runner.
            # Its Clerk receives bounded chunks; no whole document is returned.
            return
    handle, authorship = raw_target(spec, arguments, ctx)
    if handle is None or authorship in {'owner_created', 'generated'}:
        return
    if _raw_grant(spec, arguments, ctx, consume=consume):
        return
    raise Refusal('THIRD_PARTY_ROUTE_REQUIRED',
        'Locate this source through catalogue → graph → section, then verify_source_pages. '
        'A scoped person checkpoint can grant one raw read to tiers 1–2.',
        {'source': handle, 'authorship': authorship, 'route': ROUTE,
         **({'raw_request_example': {'tool': 'request_raw_source_access',
              'arguments': {'tool_name': 'read_file', 'arguments': {'path': handle}}}}
            if spec.name == 'get_note' else {})})


def _binding(spec, arguments, ctx):
    from .conversions import file_sha256
    from .credentials import refuse_credentials
    effective = dict(arguments)
    for key, value in spec.json_schema().get('properties', {}).items():
        if key not in effective and 'default' in value:
            effective[key] = value['default']
    handle, _ = raw_target(spec, effective, ctx)
    if spec.name == 'read_file':
        refuse_credentials(effective['path'])
        sha = file_sha256(source_path(ctx, effective['path']))
    elif spec.name == 'read_evidence':
        from .evidence import EvidenceStore
        store = EvidenceStore(ctx.vault)
        record = store.get(effective['evidence_id'])
        if not record or not store.intact(record):
            raise Refusal('EVIDENCE_IS_NEVER_EDITED', 'A raw grant needs intact source evidence')
        sha = hashlib.sha256(json.dumps(record.to_dict(), sort_keys=True).encode()).hexdigest()
    elif spec.name == 'read_source_file':
        from .tools.library import IndexGateway
        row = IndexGateway(ctx, include_vectors=False).run(lambda engine: engine.index.note_row(effective['source']))
        if row is None:
            raise TypeError('A raw repository grant requires its exact catalogue note')
        sha = file_sha256(ctx.vault.root / row['path'])
    elif spec.name == 'read_project':
        sha = file_sha256(_project_file(ctx, effective['path']))
    else:
        raise TypeError('Only read_file, read_source_file, read_evidence and read_project accept a raw grant')
    body = {'tool': spec.name, 'arguments': effective, 'source_sha256': sha,
            'model': ctx.extras.get('read_route', {}).get('model'), 'tier': ctx.extras.get('agent_tier', 1)}
    return {'source': handle, 'binding': hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest(), **body}


def request_raw(ctx, tool_name, arguments, recipient_tier=0):
    from .registry import REGISTRY, coerce
    from .checkpoints import CheckpointStore
    if not ctx.session or ctx.extras.get('agent_tier', 1) not in {1, 2}:
        raise Refusal('THIRD_PARTY_ROUTE_REQUIRED', 'One-off raw grants require a session and a tier-1 or tier-2 caller', {'route': ROUTE})
    allocate(ctx.extras.get('read_route', {}))
    recipient = recipient_tier or ctx.extras.get('agent_tier', 1)
    if recipient not in {1, 2}:
        raise Refusal('THIRD_PARTY_ROUTE_REQUIRED', 'Only tiers 1–2 can receive raw grants', {'route': ROUTE})
    target = ctx
    if recipient != ctx.extras.get('agent_tier', 1):
        route_for = ctx.extras.get('helper_read_route')
        route = route_for(recipient) if callable(route_for) else {}
        if not route.get('model'):
            raise Refusal('READ_ROUTE_REQUIRED', 'The actual recipient route must be bound before person review')
        target = replace(ctx, extras={**ctx.extras, 'agent_tier': recipient, 'read_route': route})
    spec = REGISTRY.check(tool_name, ctx.tier)
    args, _ = coerce(spec, arguments)
    evidence = {**_binding(spec, args, target), 'session': ctx.session, 'one_call': True,
                'allocation_at_read': 'pending measured recipient prompt',
                'warning': 'Third-party material remains untrusted for canonical publication; this grants reading only'}
    checkpoint = CheckpointStore(ctx.vault).create('raw_source_access', ctx.session,
        evidence=evidence, choices=['approve', 'decline'], default='decline', requester='agent')
    return {'checkpoint': checkpoint, 'route': ROUTE}


def _raw_grant(spec, arguments, ctx, *, consume):
    from .checkpoints import CheckpointStore
    from .session import SessionStore
    from .coordination import exclusive_file_lock, operation_path
    if spec.name not in {'read_file', 'read_source_file', 'read_evidence', 'read_project'}:
        return False
    session = ctx.session or ctx.extras.get('_publication_session')
    if not session or ctx.extras.get('agent_tier', 1) not in {1, 2}:
        return False
    candidates = [cp for cp in CheckpointStore(ctx.vault).all()
        if cp['type'] == 'raw_source_access' and cp['scope'] == session
        and cp['resolution'] == 'approve' and not cp.get('expired')]
    if not candidates:
        return False
    binding = _binding(spec, arguments, ctx)
    store = SessionStore(ctx.vault)
    for cp in candidates:
        if cp['evidence'].get('binding') != binding['binding'] or cp['evidence'].get('session') != session:
            continue
        allocate(ctx.extras.get('read_route', {}))
        if not re.fullmatch('[0-9a-f]{16}', cp['id']):
            return False
        # Resolve the state directory, not a filename another thread may have
        # byte-locked (Windows can fail final-path resolution on that handle).
        lock_path = operation_path(ctx.vault, '.librarian/raw-access') / (cp['id'] + '.lock')
        if lock_path.is_symlink():
            raise Refusal('VAULT_REQUIRED', 'A grant lock cannot redirect outside its state directory')
        def check():
            with exclusive_file_lock(lock_path):
                if any(e.get('type') == 'raw_source_grant_used' and e.get('checkpoint') == cp['id'] for e in store.events(session)):
                    return False
                if consume:
                    store.append(session, {'type': 'raw_source_grant_used', 'checkpoint': cp['id'],
                                               'source': binding['source'], 'binding': binding['binding']})
                return True
        # Core writer before lock: no reader can hold this lock while waiting on the writer.
        if store._through_core(check, 'raw-source-grant'):
            return True
    return False


def bounded_pages(pages):
    if (not isinstance(pages, list) or not 1 <= len(pages) <= 8
            or any(type(p) is not int or p < 1 for p in pages) or len(set(pages)) != len(pages)):
        raise Refusal('THIRD_PARTY_ROUTE_REQUIRED', 'Name 1–8 distinct positive original pages, located through the graph; never request an entire document', {'route': ROUTE})
    return sorted(pages)


def source_path(ctx, source):
    from .credentials import refuse_credentials
    from .content_roots import load
    from . import notes
    refuse_credentials(source)
    path = Path(source)
    path = path if path.is_absolute() else ctx.vault.root / path
    if not path.is_file():
        from .tools.library import IndexGateway
        row = IndexGateway(ctx, include_vectors=False).run(lambda engine: engine.index.note_row(source))
        if row is None:
            raise Refusal('THIRD_PARTY_ROUTE_REQUIRED', 'Catalogue only: original is missing; no original-page verification is available', {'route': ROUTE})
        card = notes.load(ctx.vault.root / row['path'])
        target = card.frontmatter.get('file')
        if not target:
            raise Refusal('THIRD_PARTY_ROUTE_REQUIRED', 'Catalogue only: no original file is recorded', {'route': ROUTE})
        path = Path(target)
        path = path if path.is_absolute() else ctx.vault.root / path
    refuse_credentials(path); refuse_credentials(path.resolve())
    roots = [ctx.vault.root.resolve()]
    for root in (load(ctx.vault.root) or {}).get('roots', []):
        base = Path(root['path'])
        roots.append((base if base.is_absolute() else ctx.vault.root / base).resolve())
    resolved = path.resolve()
    if not any(resolved.is_relative_to(root) for root in roots) or not resolved.is_file():
        raise Refusal('VAULT_REQUIRED', 'Original must exist in this library or an accepted attached root')
    # In-vault hidden state is never accepted as an original.
    if resolved.is_relative_to(ctx.vault.root.resolve()):
        ctx.vault.safe_relative(resolved.relative_to(ctx.vault.root.resolve()).as_posix())
    return resolved


def project_pages(ctx, units, **metadata):
    """Keep selected page numbers and explicit omissions under the measured route cap."""
    from .access import person
    if person(ctx):
        allocation = {'unit': 'tokens', 'effective_tokens': 32000, 'scope': 'person, no model allocation'}
        cap = 32000
    else:
        allocation = allocate(ctx.extras.get('read_route', {}), tier=ctx.extras.get('agent_tier', 1),
                              requested_tokens=ctx.extras.get('_source_read_tokens', 200000))
        from .mcp_client import external_result_limit
        cap = external_result_limit(allocation['context_tokens'])
    # A separate fixed allowance covers source identity, page flags and receipts.
    serialized_size = lambda value: len(json.dumps(value, ensure_ascii=True).encode('utf-8'))
    remaining = max(0, min(cap, allocation['effective_tokens']) - serialized_size(metadata) - serialized_size(allocation) - 1024)
    pages = []
    for number, content in units:
        low, high = 0, len(content)
        while low < high:
            middle = (low + high + 1) // 2
            if serialized_size(content[:middle]) <= remaining:
                low = middle
            else:
                high = middle - 1
        selected = content[:low]
        remaining = max(0, remaining - serialized_size(selected) - 64)
        pages.append({'page': number, 'text': selected, 'truncated': selected != content})
    return {**metadata, 'pages': pages, 'allocation': allocation,
            'truncated': any(p['truncated'] for p in pages),
            'omissions': ['Selected page text cut to fit the actual route allocation'] if any(p['truncated'] for p in pages) else []}


def bound_raw_result(spec, result, ctx, arguments):
    """A person grant changes reading permission, never the result-size cap."""
    from .access import person
    frontmatter = result.get('frontmatter')
    section_authors = frontmatter.get('section_authorship', {}) if spec.name == 'get_note' and isinstance(frontmatter, dict) else {}
    quoted_catalogue = (spec.name == 'get_note' and isinstance(section_authors, dict)
        and any(not isinstance(a, str) or a not in {'owner_created', 'generated'} for a in section_authors.values()))
    if person(ctx) or (spec.name not in {'read_file', 'read_source_file', 'read_evidence', 'read_project'} and not quoted_catalogue) or 'error' in result:
        return result
    from copy import deepcopy
    from .mcp_client import external_result_limit
    route = ctx.extras.get('read_route', {})
    cap = external_result_limit(route.get('context_tokens'))
    allocation = allocate(route, tier=ctx.extras.get('agent_tier', 1)) if route.get('context_tokens') else None
    out = deepcopy(result)
    fields = []
    def visit(value):
        if isinstance(value, dict):
            if isinstance(value.get('text'), str):
                fields.append((value, 'text', value['text']))
                value['text'] = ''
            if quoted_catalogue and isinstance(value.get('sections'), dict):
                for heading, content in value['sections'].items():
                    if isinstance(content, str):
                        fields.append((value['sections'], heading, content))
                        value['sections'][heading] = ''
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:visit(child)
    visit(out)
    size = lambda value: len(json.dumps(value, ensure_ascii=True).encode('utf-8'))
    if allocation is not None:
        out['read_allocation'] = allocation
    remaining = max(0, min(cap, allocation['effective_tokens'] if allocation else cap) - size(out) - 2048)
    clipped = False
    for field, key, content in fields:
        low, high = 0, len(content)
        while low < high:
            middle = (low + high + 1) // 2
            if size(content[:middle]) <= remaining:low = middle
            else:high = middle - 1
        field[key] = content[:low]
        remaining = max(0, remaining - size(field[key]))
        if low != len(content):
            clipped = True
            if key == 'text' and field is not out:
                field['next_offset'] = max(0, int(arguments.get('offset', 0))) + low
                field['truncated'] = True
    if clipped:
        out.update(truncated=True, omissions=['Text cut to the actual route allocation and existing character cap; use located sections/pages for the remainder'])
    return out
