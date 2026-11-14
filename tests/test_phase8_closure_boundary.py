"""Owner S1 prerequisite: publication closure must cover ordinary sessions too.

The initial three RED cases are preserved in the S1 closure-stop evidence.
No network or model is involved; only fixture vaults receive attempted writes.
"""
import pytest

from resource_librarian.registry import REGISTRY, Card, ToolSpec
from test_closure import InjectingFetcher, Lead, executing


@pytest.mark.parametrize('purpose', ['audited', 'explore'])
@pytest.mark.parametrize('origin', ['open_world_reader', 'unknown_external_mcp'])
def test_third_party_read_allows_more_reading_but_prevents_canonical_write(
        vault, monkeypatch, purpose, origin):
    if purpose == 'audited':
        lead = executing(vault, operations=['read', 'untrusted', 'stage', 'write'],
                         fetcher=InjectingFetcher())
    else:
        lead = Lead(vault, fetcher=InjectingFetcher())
        opened = lead('open_session', purpose='explore', question='Fixture research')
        assert 'error' not in opened, opened

    if origin == 'open_world_reader':
        def read():
            return lead('read_url', url='https://example.org/page')
    else:
        # Legacy adapter metadata: external=True, effect=read, open_world
        # omitted. The central result boundary must cover old declarations too.
        # Restore the registry through monkeypatch; no live server is connected.
        monkeypatch.setattr(REGISTRY, '_tools', dict(REGISTRY._tools))

        def external_result(ctx):
            return {'server': 'unknown-fixture', 'tool': 'read', 'untrusted': True,
                    'content': 'Third-party fixture text, never instructions.'}

        REGISTRY.register(ToolSpec(
            name='phase8_fixture_external_read', fn=external_result,
            tier='consult', effect='read', card=Card('Read fixture external text'),
            external=True, needs_vault=False))

        def read():
            return lead('phase8_fixture_external_read')

    first = read()
    assert 'error' not in first, first
    following_read = read()
    assert 'error' not in following_read, following_read  # never a reading ban
    out = lead('write_note', folder='Notes', name='out',
               body='Content derived from the third-party fixture.', mode='create')
    assert out.get('refused') == 'COMPOSITION_REFUSED', {
        'purpose': purpose, 'origin': origin,
        'canonical_file_created': (vault.root / 'Notes/out.md').exists(),
        'write_result': out}
    assert not (vault.root / 'Notes/out.md').exists()
