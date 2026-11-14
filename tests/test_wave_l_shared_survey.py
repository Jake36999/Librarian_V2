import json
from types import SimpleNamespace

from resource_librarian import deploy_survey


def test_enabled_passes_same_inventory_to_pinned_cli(tmp_path, monkeypatch):
    (tmp_path / 'a.md').write_text('synthetic')
    monkeypatch.setenv('GEOGRAPHER_INIT', 'pinned-geographer')
    def run(argv, **kwargs):
        assert '--survey-in' in argv
        inventory = json.loads(kwargs['input'])
        assert inventory['entries'][0][0] == 'a.md'
        assert inventory['version'] == 'folder-inventory-v1'
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            'plan_version': 'workspace-init-v1', 'shared_survey_fingerprint': inventory['fingerprint'],
            'geographer_version': '0.2.0', 'partitions': []}).encode())
    monkeypatch.setattr(deploy_survey.subprocess, 'run', run)
    result = deploy_survey.survey(tmp_path)
    assert result.geo_grapher['plan']['shared_survey_fingerprint'] == result.fingerprint


def test_disabled_does_not_launch_geo(tmp_path, monkeypatch):
    monkeypatch.delenv('GEOGRAPHER_INIT', raising=False)
    monkeypatch.setattr(deploy_survey.subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(AssertionError('Geo disabled')))
    assert 'geo_grapher' not in deploy_survey.survey(tmp_path).to_dict()
