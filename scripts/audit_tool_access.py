"""C0 review inventory/CI guard. This does not enforce the future S1/S4 access policy."""
import argparse
import hashlib
import inspect
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTHORSHIP = ('owner_created', 'generated', 'third_party')


def fingerprint(spec):
    source = inspect.getsource(spec.fn).replace('\r\n', '\n')
    schema = json.dumps(spec.json_schema(), sort_keys=True, separators=(',', ':'))
    return dict(source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                schema_sha256=hashlib.sha256(schema.encode()).hexdigest(), effect=spec.effect,
                open_world=spec.open_world, external=spec.external, sessionless=spec.sessionless)


def declaration(spec, *, content, status, fixes):
    from resource_librarian.tools.delegate import HELPER_TOOLS
    actors = ['person']
    if spec.tier != 'curate': actors += ['lead (bundle/profile-gated)', 'external agent (MCP tier-capped)']
    if spec.name in HELPER_TOOLS: actors.append('research helper (read-only allow-list)')
    if spec.sessionless: actors.append('task worker (sessionless protocol only)')
    path = Path(inspect.getsourcefile(spec.fn)).resolve().relative_to(ROOT)
    return dict(tool=spec.name, minimum_tier=spec.tier, actors=actors, returns_content=content,
        authorship_may_return=list(AUTHORSHIP) if content else [], authorship_explicit=False if content else None,
        status=status, fixes=fixes, evidence=dict(path=path.as_posix(), line=inspect.getsourcelines(spec.fn)[1],
        symbol=spec.fn.__name__), fingerprint=fingerprint(spec))


def validate(rows, specs):
    indexed = {row['tool']: row for row in rows}; problems = []
    if len(indexed) != len(rows): problems.append('DUPLICATE_ACCESS_DECLARATION')
    specs = list(specs)
    for spec in specs:
        row = indexed.get(spec.name)
        if row is None:
            problems.append('UNDECLARED_ACCESS: ' + spec.name); continue
        if row.get('minimum_tier') != spec.tier or row.get('fingerprint') != fingerprint(spec):
            problems.append('STALE_ACCESS: ' + spec.name)
        if type(row.get('returns_content')) is not bool or not row.get('actors'):
            problems.append('INVALID_ACCESS: ' + spec.name)
        if row.get('returns_content'):
            if row.get('status') not in {'conforms','diverges'} or not row.get('authorship_may_return'):
                problems.append('INVALID_CONTENT_ACCESS: ' + spec.name)
            if not set(row.get('authorship_may_return', [])) <= set(AUTHORSHIP):
                problems.append('INVALID_AUTHORSHIP: ' + spec.name)
            if row.get('status') == 'diverges' and not row.get('fixes'):
                problems.append('MISSING_REMEDY: ' + spec.name)
        elif row.get('status') != 'n/a': problems.append('INVALID_METADATA_ACCESS: ' + spec.name)
    for extra in sorted(set(indexed) - {spec.name for spec in specs}):
        problems.append('ORPHANED_ACCESS: ' + extra)
    return problems


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--declarations', type=Path,
        default=ROOT / 'docs/tool-access-declarations.json'); args = parser.parse_args()
    import resource_librarian.tools  # noqa: F401
    from resource_librarian.registry import REGISTRY
    review = json.loads(args.declarations.read_text(encoding='utf-8'))
    problems = validate(review['tools'], REGISTRY._tools.values())
    rows = [row for row in review['tools'] if row['returns_content']]
    print(json.dumps(dict(registered=len(review['tools']), content=len(rows),
        conforms=sum(row['status']=='conforms' for row in rows), problems=problems), indent=2))
    raise SystemExit(bool(problems))


if __name__ == '__main__': main()
