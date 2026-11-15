"""The project-file entry point shares the central raw-source boundary."""
import json

import pytest

from resource_librarian import access, tools  # noqa: F401
from resource_librarian.read_access import guard, request_raw, bound_raw_result
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.rules import Refusal
from resource_librarian.session import SessionStore


@pytest.fixture
def project_read(vault, tmp_path, monkeypatch):
    from resource_librarian.tools import sessions
    root = tmp_path / 'external-project'
    root.mkdir()
    path = root / 'module.py'
    path.write_text('REFERENCE = 42\n', encoding='utf-8')
    monkeypatch.setattr(sessions, '_project_root', lambda *args: root)
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    sid = SessionStore(vault).new('explore', question='Read project reference').id
    ctx = Context(tier='contribute', vault=vault, session=sid, extras={'agent_tier': 2,
        'read_route': dict(model='scripted-helper', context_tokens=262144, prompt_tokens=1000,
                           visible_output_tokens=4096, reasoning_reserve_tokens=0)})
    return ctx, path


@pytest.mark.parametrize('authorship', ['third_party', None])
def test_project_raw_read_needs_the_same_explicit_route(project_read, monkeypatch, authorship):
    ctx, _ = project_read
    monkeypatch.setattr(access, '_native_authorship', lambda *args: authorship)
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('read_project'), {'path': 'module.py'}, ctx)


def test_project_listing_is_metadata_and_person_access_is_unchanged(project_read):
    ctx, _ = project_read
    assert guard(REGISTRY.get('read_project'), {'path': ''}, ctx) is None
    ctx.extras['caller_kind'] = 'person'
    assert guard(REGISTRY.get('read_project'), {'path': 'module.py'}, ctx) is None


def test_project_grant_is_one_call_and_pins_original_bytes(project_read):
    from resource_librarian.checkpoints import CheckpointStore
    ctx, path = project_read
    args = {'path': 'module.py'}
    request = request_raw(ctx, 'read_project', args)
    CheckpointStore(ctx.vault).resolve(request['checkpoint']['id'], 'approve')
    assert guard(REGISTRY.get('read_project'), args, ctx, consume=True) is None
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('read_project'), args, ctx, consume=True)
    request = request_raw(ctx, 'read_project', args)
    CheckpointStore(ctx.vault).resolve(request['checkpoint']['id'], 'approve')
    path.write_text('REFERENCE = 43\n', encoding='utf-8')
    with pytest.raises(Refusal, match='THIRD_PARTY_ROUTE_REQUIRED'):
        guard(REGISTRY.get('read_project'), args, ctx)


def test_project_result_keeps_the_route_character_cap(project_read):
    from resource_librarian.mcp_client import external_result_limit
    ctx, _ = project_read
    result = bound_raw_result(REGISTRY.get('read_project'), {'text': 'x' * 100000}, ctx, {})
    assert result['truncated']
    assert len(json.dumps(result)) <= external_result_limit(262144)
