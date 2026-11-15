"""S6: full own documents, metadata-only external references, no source writes."""
import hashlib
import json

import pytest

from resource_librarian import content_roots, tools  # noqa: F401
from resource_librarian.index import Index
from resource_librarian.registry import Context, REGISTRY
from resource_librarian.search import Engine, search
from test_app import served  # noqa: F401


def attach(vault, *roots):
    content_roots._write_json(content_roots.manifest_path(vault.root), {
        'version': 1, 'mode': 'create', 'roots': [{'path': '.', 'access': 'read_write'},
            *[dict(path=str(path), access='read_only', attached=True, authorship=author,
                   purpose='own-docs' if author == 'owner_created' else 'research-docs') for path, author in roots]],
        'excludes': []})


def test_attached_own_documents_are_fully_searchable_and_never_rewritten(vault, tmp_path):
    root = tmp_path / 'own-docs'; root.mkdir()
    original = root / 'Guide.md'
    original.write_text('# Operations\n\n' + ('Introductory content.\n\n' * 200) + 'Ultravioletflux procedure at the end.', encoding='utf-8')
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    attach(vault, (root, 'owner_created'))
    with Index(vault) as index:
        index.refresh()
        hits = search(Engine(index), 'Ultravioletflux', 'workspace').to_dict()['results']
        assert len(hits) == 1
        row = index.note_row(hits[0]['name'])
        assert row['shape'] == 'workspace_document'
        assert json.loads(row['frontmatter'])['authorship'] == 'owner_created'
        assert row['path'] == original.as_posix()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob('*')) == ['Guide.md']


def test_attached_workspace_keeps_short_tail_and_repeated_headings(vault, tmp_path):
    root = tmp_path / 'own-complete'; root.mkdir()
    (root / 'Long.md').write_text('# Operations\n\n'+('Opening material.\n'*250)+
        '\nUltravioletflux procedure at the end.',encoding='utf-8')
    (root / 'Repeated.md').write_text('## Evidence\nAmberwitness first occurrence.\n\n'
        '## Evidence\nJadewitness second occurrence.',encoding='utf-8')
    attach(vault,(root,'owner_created'))
    with Index(vault) as index:
        index.refresh()
        for query in ('Ultravioletflux','Amberwitness','Jadewitness'):
            assert search(Engine(index),query,'workspace').results,query


def test_person_can_open_workspace_search_path_without_general_external_read(served, tmp_path):
    from urllib.parse import quote
    app, client, _ = served
    own=tmp_path/'click-owned';own.mkdir();path=own/'Guide.md';path.write_text('Ownedclicksentinel source.')
    outside=tmp_path/'not-attached.md';outside.write_text('Must not be shown.')
    attach(app.vault,(own,'owner_created'))
    app.index_service.refresh()
    status,out=client.get('/api/file?path='+quote(path.as_posix()))
    assert status==200,out
    assert out['read_only'] and 'Ownedclicksentinel' in out['text']
    assert client.get('/api/file?path='+quote(outside.as_posix()))[0] != 200


def test_person_vault_absolute_paths_keep_existing_read_behavior(served):
    from urllib.parse import quote
    app,client,_=served
    path=app.vault.root/'Notes/Local.md';path.parent.mkdir(exist_ok=True);path.write_text('# Local\n\nLocalnote sentinel.')
    status,out=client.get('/api/file?path='+quote(path.as_posix()))
    assert status==200,out
    assert 'Localnote sentinel' in out['text']


def test_third_party_root_is_catalogue_only_without_opening_its_documents(vault, tmp_path, monkeypatch):
    import resource_librarian.index as indexing
    root = tmp_path / 'research'; root.mkdir()
    (root / 'External.md').write_text('Prohibitedrawsentinel original reference text.', encoding='utf-8')
    attach(vault, (root, 'third_party'))
    real = indexing.read_bytes_snapshot
    def snapshot(path):
        assert not path.resolve().is_relative_to(root.resolve()), 'Third-party source bytes reached the native index'
        return real(path)
    monkeypatch.setattr(indexing, 'read_bytes_snapshot', snapshot)
    with Index(vault) as index:
        index.refresh()
        assert not search(Engine(index), 'Prohibitedrawsentinel', 'all').results
        rows = index.conn.execute("SELECT frontmatter FROM note WHERE shape='source'").fetchall()
        assert any(json.loads(r[0]).get('original_authorship') == 'third_party' for r in rows)


def test_authorship_change_removes_previously_indexed_original_text(vault, tmp_path):
    root = tmp_path / 'changed'; root.mkdir()
    (root / 'Guide.md').write_text('# A guide\n\nAmberprocedures original text.', encoding='utf-8')
    attach(vault, (root, 'owner_created'))
    with Index(vault) as index:
        index.refresh()
        assert search(Engine(index), 'Amberprocedures', 'workspace').results
        attach(vault, (root, 'third_party'))
        index.refresh()
        assert not search(Engine(index), 'Amberprocedures', 'all').results


def test_external_document_names_do_not_collide_and_model_reads_are_read_only(vault, tmp_path):
    roots = [tmp_path / 'one', tmp_path / 'two']
    for number, root in enumerate(roots):
        root.mkdir(); (root / 'README.md').write_text(f'# Sharedtopic\n\nOwned document {number}.', encoding='utf-8')
    attach(vault, *((root, 'owner_created') for root in roots))
    with Index(vault) as index:
        index.refresh()
        hits = search(Engine(index), 'Sharedtopic', 'workspace').results
        assert len(hits) == 2 and len({h.name for h in hits}) == 2
        name = hits[0].name
    out = REGISTRY.call('get_note', {'name': name}, Context(vault=vault))
    assert 'Owned document' in json.dumps(out['sections'])
    assert out['read_only'] is True
    edited = REGISTRY.call('edit_note', {'note': name, 'section': 'Changed', 'text': 'must not land'},
                           Context(tier='contribute', vault=vault))
    assert 'refused' in edited or 'error' in edited


def test_hygiene_and_nested_third_party_overrides_precede_source_open(vault, tmp_path, monkeypatch):
    import resource_librarian.index as indexing
    root = tmp_path / 'own'; root.mkdir()
    nested = root / 'reference'; nested.mkdir()
    (nested / 'No.md').write_text('Nestedforbidden sentinel.')
    (root / '.env').write_text('fixture name only')
    bundle = root / 'src/resource_librarian/ui'; bundle.mkdir(parents=True)
    (bundle / 'app.js').write_text('Generatedbundlesentinel')
    source = root / 'ui/src'; source.mkdir(parents=True)
    (source / 'main.ts').write_text('export const Sourceuivocabulary = true;')
    attach(vault, (root, 'owner_created'), (nested, 'third_party'))
    real = indexing.read_bytes_snapshot
    def snapshot(path):
        assert not path.resolve().is_relative_to(nested.resolve())
        assert path.name not in {'.env', 'app.js'}
        return real(path)
    monkeypatch.setattr(indexing, 'read_bytes_snapshot', snapshot)
    with Index(vault) as index:
        index.refresh()
        assert search(Engine(index), 'Sourceuivocabulary', 'workspace').results
        assert not search(Engine(index), 'Nestedforbidden', 'all').results


def test_owned_text_code_and_original_pdf_all_use_free_native_extraction(vault, tmp_path):
    from conftest import pdf_bytes
    root = tmp_path / 'formats'; root.mkdir()
    (root / 'notes.txt').write_text('Textformatvocabulary instructions.')
    (root / 'code.py').write_text('VALUE = "Codeformatvocabulary"\n')
    (root / 'study.pdf').write_bytes(pdf_bytes([['Pdffirstpagevocabulary'], ['Pdflastpagevocabulary']]))
    attach(vault, (root, 'owner_created'))
    with Index(vault) as index:
        index.refresh()
        for word in ['Textformatvocabulary', 'Codeformatvocabulary', 'Pdffirstpagevocabulary', 'Pdflastpagevocabulary']:
            hits = search(Engine(index), word, 'workspace').results
            assert hits, word
            out = REGISTRY.call('get_note', {'name': hits[0].name}, Context(vault=vault))
            assert word in json.dumps(out['sections']), out


def test_unreadable_owned_document_is_reported_without_losing_good_documents(vault, tmp_path):
    root = tmp_path / 'broken'; root.mkdir()
    (root / 'bad.pdf').write_bytes(b'not a pdf')
    (root / 'good.md').write_text('# A guide\n\nGooddocumentvocabulary text.')
    attach(vault, (root, 'owner_created'))
    with Index(vault) as index:
        index.refresh()
        assert search(Engine(index), 'Gooddocumentvocabulary', 'workspace').results
        assert index.stats()['unparsed'] >= 1


def test_person_can_open_returned_workspace_identifier_and_read_only_catalogue(served, tmp_path):
    import urllib.parse
    app, client, _ = served
    root = tmp_path / 'person-docs'; root.mkdir()
    (root / 'Guide.md').write_text('# A guide\n\nPersondocumentvocabulary text.')
    attach(app.vault, (root, 'owner_created'))
    app.index_service.refresh()
    rows = app.index_service.run(lambda index: [dict(r) for r in index.conn.execute(
        "SELECT name,shape FROM note WHERE shape='workspace_document' OR json_extract(frontmatter,'$.catalogue_of')='folder'")])
    assert {r['shape'] for r in rows} == {'workspace_document', 'source'}
    for row in rows:
        status, doc = client.get('/api/file?path=' + urllib.parse.quote(row['name']))
        assert status == 200, doc
        assert doc['read_only'] is True
        if row['shape'] == 'workspace_document':assert 'Persondocumentvocabulary' in doc['text']


def test_explicit_third_party_upsert_cannot_bypass_the_index_walk(vault, tmp_path, monkeypatch):
    import resource_librarian.index as indexing
    root = tmp_path / 'outside'; root.mkdir()
    original = root / 'No.md'; original.write_text('Never opened.')
    attach(vault, (root, 'third_party'))
    monkeypatch.setattr(indexing, 'read_bytes_snapshot', lambda *args: pytest.fail('Refuse before open'))
    with Index(vault) as index:
        assert index.upsert(original) is False


def test_third_party_attachment_text_is_removed_from_native_document_index(vault, monkeypatch):
    from conftest import add_source
    from resource_librarian import text
    source = vault.root / 'Inbox/research'; source.mkdir()
    original = source / 'study.pdf'; original.write_bytes(b'never extracted')
    add_source(vault.root, 'External paper', 'Catalogue description only.',
               extra_fm='file: Inbox/research/study.pdf\nauthorship: generated')
    attach(vault, (source, 'third_party'))
    with Index(vault) as index:
        index.refresh()
        index.add_document_text('External paper', ['Oldthirdpartyindexsentinel prose.'])
        monkeypatch.setattr(text, 'extract', lambda *args: pytest.fail('Original third-party text must not be extracted into native search'))
        report = text.sync_documents(index)
        assert not search(Engine(index), 'Oldthirdpartyindexsentinel', 'in_text').results
        assert any(p.get('code') == 'THIRD_PARTY_CATALOGUE_ONLY' for p in report['problems'])


@pytest.mark.parametrize('relative', ['private.key', '.env', 'src/resource_librarian/ui/app.js', 'graphify-out/graph.md'])
def test_direct_upsert_applies_path_hygiene_before_open(vault, tmp_path, monkeypatch, relative):
    import resource_librarian.index as indexing
    root = tmp_path / 'own-direct'; root.mkdir()
    path = root / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture only')
    attach(vault, (root, 'owner_created'))
    monkeypatch.setattr(indexing, 'read_bytes_snapshot', lambda *args: pytest.fail('Rejected path reached a content open'))
    with Index(vault) as index:
        assert index.upsert(path) is False


def test_attached_workspace_source_never_reaches_a_hosted_embedding_encoder(vault, tmp_path):
    import numpy as np
    from resource_librarian.embed import VectorSearch
    root = tmp_path / 'private-source'; root.mkdir()
    original = root / 'private.py'
    original.write_text('def Privatecodebodysentinel():\n    return 42\n')
    attach(vault, (root, 'owner_created'))
    sent = []
    def hosted_encode(values):
        sent.extend(values)
        return np.ones((len(values), 8), dtype='float32')
    with Index(vault) as index:
        index.refresh()
        hosted = VectorSearch(index, 'api:scripted:embedding', hosted_encode)
        hosted.sync()
        assert not any('Privatecodebodysentinel' in value for value in sent)
        assert search(Engine(index), 'Privatecodebodysentinel', 'workspace').results
        local = VectorSearch.from_spec(index, 'hash:64')
        assert local.sync() > 0
        assert index.conn.execute('SELECT count(*) FROM chunk c JOIN embedding e ON e.hash=c.hash '
                                  'WHERE c.path=? AND e.model=?', (original.as_posix(), local.model)).fetchone()[0] > 0


def test_folder_catalogues_use_existing_content_model_kinds(vault, tmp_path):
    root = tmp_path / 'reference-catalogue'; root.mkdir()
    attach(vault, (root, 'third_party'))
    with Index(vault) as index:
        index.refresh()
        rows = index.conn.execute("SELECT kind,frontmatter FROM note WHERE shape='source'").fetchall()
        catalogues = [row for row in rows if json.loads(row['frontmatter']).get('catalogue_only')]
        assert catalogues
        assert all(row['kind'] in index.model.kinds for row in catalogues)
