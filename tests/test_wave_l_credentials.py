"""Only synthetic credential names/content are used here."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from resource_librarian.deploy_survey import survey
from resource_librarian import intake


def test_survey_refuses_secret_names_without_opening_them(tmp_path, monkeypatch):
    names = ['Frank.env', '.env', '.env.local', 'certs/readme.md',
             'wazuh_config/certs/server.pem', 'id_private.md', 'private.key']
    for name in [*names, 'docs/safe.md']:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic fixture only', encoding='utf-8')
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path.relative_to(tmp_path).as_posix() not in names
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', guarded)
    result = survey(tmp_path).to_dict()
    assert result['credential_refusals']['count'] >= 5
    assert 'Frank.env' in result['credential_refusals']['paths']
    assert result['markdown_files'] == 1
    assert result['content_candidates'] == [{'path': 'docs', 'markdown_files': 1}]


def test_direct_file_intake_refuses_before_read_or_evidence(tmp_path):
    path = tmp_path / 'id_private.md'
    path.write_text('synthetic fixture only', encoding='utf-8')
    vault = SimpleNamespace(root=tmp_path)
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        intake.fetch_file('id_private.md', vault, None)


def test_static_project_survey_never_reads_refused_names(tmp_path, monkeypatch):
    from resource_librarian import structure
    for name in ['id_private.py', '.env.example', 'certs/public.txt', 'safe.py']:
        path = tmp_path / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('SYNTHETIC_VALUE = 1\n')
    original = Path.read_text
    def guarded(path, *args, **kwargs):
        assert path.name == 'safe.py', 'refused content was opened'
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded)
    structure.survey(tmp_path)


def test_project_read_refuses_credential_before_any_content_read(tmp_path, monkeypatch):
    from resource_librarian.tools import sessions
    from resource_librarian import projects
    from resource_librarian.registry import Context
    (tmp_path / 'id_private.md').write_text('synthetic')
    monkeypatch.setattr(sessions, '_session', lambda _: SimpleNamespace(project='fixture', id='session'))
    monkeypatch.setattr(sessions, '_project_root', lambda *a: tmp_path)
    monkeypatch.setattr(projects, 'log', lambda *a, **k: pytest.fail('must refuse before side effects'))
    with pytest.raises(ValueError, match='CREDENTIAL_REFUSED'):
        sessions.read_project(Context(), 'id_private.md')


def test_public_vault_path_refuses_credential_even_for_direct_api_reads(tmp_path):
    from resource_librarian.vault import Vault
    from resource_librarian.rules import Refusal
    with pytest.raises((ValueError, Refusal), match='CREDENTIAL_REFUSED'):
        Vault(tmp_path).safe_relative('certs/public.txt')


def test_surveying_credential_directory_itself_offers_no_content(tmp_path):
    root = tmp_path / 'certs'; root.mkdir(); (root / 'public.md').write_text('synthetic')
    result = survey(root).to_dict()
    assert result['credential_refusals']['count'] == 1
    assert result['markdown_files'] == 0 and result['content_candidates'] == []
    assert any('CREDENTIAL_REFUSED' in stop for stop in result['stops'])
