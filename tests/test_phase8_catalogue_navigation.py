"""S5 catalogue navigation is free, located, and separate from originals."""
import json

import pytest

from conftest import add_source, write_note
from resource_librarian import dik, tools  # noqa: F401 -- register tools in isolated runs
from resource_librarian.index import Index
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.session import SessionStore
from resource_librarian.search import Engine, search
from test_app import served  # noqa: F401


@pytest.fixture
def catalogue(vault):
    original = vault.root / 'Inbox/reference.pdf'
    original.write_bytes(b'%PDF-fixture-original')
    add_source(vault.root, 'Target paper', 'Locates target evidence.',
               extra_fm='file: Inbox/reference.pdf\nwhen_relevant: Compare target mechanisms.\nauthorship: generated')
    sid = SessionStore(vault).new('explore', question='Target').id
    SessionStore(vault).append(sid, {'type': 'use', 'source': 'Target paper', 'used_for': 'Compare a mechanism.'})
    write_note(vault.root, 'Applications/Application - Target.md',
        'type: application\nauthorship: generated\nsources_used: ["[[Target paper]]"]\noutcome: worked',
        '## What Was Found And Taken\nUsed a located comparison, not copied prose.\n')
    dik.save(vault, {'source': 'Target paper', 'kind': 'document', 'revision': 'fixture',
        'data': [{'kind': 'chapter', 'name': 'Method', 'locator': 'pp. 2-3', 'status': 'observed',
                  'coverage': 'full', 'claims': ['Located method summary.']},
                 {'kind': 'chapter', 'name': 'Appendix', 'locator': 'pp. 4-5',
                  'status': 'not examined', 'coverage': 'not opened', 'claims': []}], 'information': []})
    return vault, original


def test_catalogue_note_exposes_relevance_use_rollup_and_chapter_coverage(catalogue):
    vault, _ = catalogue
    out = REGISTRY.call('get_note', {'name': 'Target paper'}, Context(vault=vault))
    navigation = out['catalogue']
    assert navigation['when_relevant'] == 'Compare target mechanisms.'
    assert navigation['use_rollup']['log_use_count'] == 1
    assert navigation['use_rollup']['application_count'] == 1
    assert navigation['chapters'][0]['summary'] == ['Located method summary.']
    assert navigation['chapters'][1]['status'] == 'not examined'
    assert navigation['chapters'][1]['summary'] == []
    assert navigation['original']['available'] is True
    assert 'conversion' not in navigation['original']['path']


def test_every_source_search_intent_carries_recorded_use_not_just_precedent(catalogue):
    vault, _ = catalogue
    with Index(vault) as index:
        index.refresh()
        for intent in ['donor', 'orient', 'all']:
            out = search(Engine(index), 'Target paper', intent).to_dict()
            target = next(r for r in out['results'] if r['name'] == 'Target paper')
            assert target['fields']['use_rollup']['log_use_count'] == 1
            assert target['fields']['use_rollup']['application_count'] == 1


def test_missing_original_and_hidden_conversion_never_become_original_links(catalogue, monkeypatch):
    from resource_librarian.catalogue_navigation import navigation
    from resource_librarian import notes
    vault, original = catalogue
    original.unlink()
    from resource_librarian.tools.library import IndexGateway
    monkeypatch.setattr(IndexGateway, 'run', lambda *args: pytest.fail('A missing attachment must not trigger index refresh/extraction'))
    note = notes.load(vault.root / 'Sources/repository/Target paper.md')
    assert navigation(vault, note)['original']['available'] is False
    note.frontmatter['file'] = '.librarian/conversions/fake.md'
    assert navigation(vault, note)['original']['available'] is False


def test_paper_graph_projection_carries_the_same_use_rollup(catalogue):
    from resource_librarian.paper_graph import export_document
    vault, _ = catalogue
    out = export_document(vault, {'name': 'Target paper', 'file': 'Inbox/reference.pdf'})
    assert out['catalogue']['use_rollup']['log_use_count'] == 1
    assert out['catalogue']['use_rollup']['application_count'] == 1
    assert out['catalogue']['authorship'] == 'generated'


def test_search_reads_each_use_log_once_and_next_search_sees_new_uses(catalogue, monkeypatch):
    vault, _ = catalogue
    for number in range(4):
        add_source(vault.root, f'Target paper {number}', 'Target evidence comparison.')
    calls = []
    real = SessionStore.events
    def events(store, sid):
        calls.append(sid)
        return real(store, sid)
    monkeypatch.setattr(SessionStore, 'events', events)
    with Index(vault) as index:
        index.refresh()
        engine = Engine(index)
        search(engine, 'Target paper', 'donor')
        assert len(calls) == 1
        SessionStore(vault).append(calls[0], {'type': 'use', 'source': 'Target paper', 'used_for': 'Second use.'})
        out = search(engine, 'Target paper', 'donor').to_dict()
        target = next(r for r in out['results'] if r['name'] == 'Target paper')
        assert target['fields']['use_rollup']['log_use_count'] == 2


def test_person_file_view_adds_catalogue_and_original_download_requires_token(served, monkeypatch):
    import urllib.request
    app, client, _ = served
    original = app.vault.root / 'Inbox/original.pdf'
    original.write_bytes(b'%PDF-original-download')
    add_source(app.vault.root, 'Download', 'An original source.', extra_fm='file: Inbox/original.pdf')
    from resource_librarian import text
    monkeypatch.setattr(text, 'extract', lambda *args, **kwargs: pytest.fail('Download must not extract/index the original'))
    status, document = client.get('/api/file?path=Download')
    assert status == 200 and document['catalogue']['original']['available']
    assert client.get('/api/source-original?source=Download', token=False)[0] == 403
    request = urllib.request.Request(client.base + '/api/source-original?source=Download',
                                     headers={'X-Librarian-Token': client.token})
    with urllib.request.urlopen(request) as response:
        assert response.read() == original.read_bytes()
        assert 'attachment' in response.headers['Content-Disposition']
        assert response.headers['X-Content-Type-Options'] == 'nosniff'


def test_original_endpoint_never_serves_conversion_or_credential_paths(served):
    app, client, _ = served
    for name, target in [('Conversion', '.librarian/conversions/fake.md'), ('Secret', 'Inbox/private.key')]:
        path = app.vault.root / target
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('must not be served', encoding='utf-8')
        add_source(app.vault.root, name, 'Catalogue only.', extra_fm='file: ' + target)
        assert client.get('/api/source-original?source=' + name)[0] in {400, 403, 404}


def test_person_view_keeps_all_chapters_while_agent_navigation_stays_bounded(served):
    app, client, _ = served
    add_source(app.vault.root, 'Long paper', 'Many chapters.')
    dik.save(app.vault, {'source': 'Long paper', 'data': [dict(kind='chapter', name=f'Chapter {n}',
        locator=f'pp. {n}-{n}', status='observed', coverage='full', claims=['Summary.']) for n in range(1, 12)]})
    _, document = client.get('/api/file?path=Long%20paper')
    assert len(document['catalogue']['chapters']) == 11
    assert document['catalogue']['chapters_truncated'] is False
    from resource_librarian import notes
    from resource_librarian.catalogue_navigation import navigation
    note = notes.load(app.vault.root / 'Sources/repository/Long paper.md')
    assert len(navigation(app.vault, note)['chapters']) == 8
    assert navigation(app.vault, note)['chapters_truncated'] is True
