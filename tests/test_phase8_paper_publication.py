from test_phase8_paper_graph import paper


def test_native_parse_publishes_conversion_only_through_accepted_folder(paper, monkeypatch):
    from resource_librarian import folder_review
    from resource_librarian.batch import _parse
    from resource_librarian.registry import Context
    vault, pdf, converted = paper
    monkeypatch.setattr(folder_review, 'configuration', lambda _: {'enabled': True})
    decision = dict(purpose='research-docs', authorship='third_party', graph='papers', accepted_by='person')
    card = dict(id='folder-fixture', status='accepted', source_root=str(pdf.parent), path='.', decision=decision)
    monkeypatch.setattr(folder_review.FolderReview, 'list', lambda _: [card])
    monkeypatch.setattr(folder_review.FolderReview, 'validate', lambda *_: None)
    calls = []
    monkeypatch.setattr(folder_review, 'cli', lambda config, operation, payload:
                        calls.append((operation, payload)) or {'geographer_version':'0.2.0', 'published':True})
    out = _parse(Context(tier='contribute', vault=vault), {'name':'Study', 'file':'Inbox/original.pdf',
        'clean_file':converted['path'], 'source_kind':'paper'})
    assert out['paper_graph']['publication']['published'] is True
    assert calls[0][0][0] == 'import-library-paper'
    assert calls[0][1]['graph_label'] == 'papers'
    assert calls[0][1]['artifact_sha256'] == out['paper_graph']['sha256']


def test_publication_never_uses_failed_or_unreviewed_folder(paper, monkeypatch):
    from resource_librarian import folder_review, paper_graph
    vault, _, converted = paper
    monkeypatch.setattr(folder_review, 'configuration', lambda _: {'enabled':True})
    monkeypatch.setattr(folder_review.FolderReview, 'list', lambda _: [])
    monkeypatch.setattr(folder_review, 'cli', lambda *a: (_ for _ in ()).throw(AssertionError('must not publish')))
    item = {'name':'Study', 'file':'Inbox/original.pdf', 'clean_file':converted['path']}
    artifact = paper_graph.write_artifact(vault, item)
    assert paper_graph.publish_artifact(vault, item, artifact)['status'] == 'awaiting_accepted_folder'


def test_paper_export_can_use_an_accepted_external_original(paper, monkeypatch, tmp_path):
    from resource_librarian import content_roots, paper_graph
    from resource_librarian.conversions import ConversionStore
    vault, pdf, _ = paper
    external = tmp_path / 'attached'; external.mkdir()
    original = external / 'original.pdf'; original.write_bytes(pdf.read_bytes())
    content_roots._write_json(content_roots.manifest_path(vault.root), dict(version=1, mode='create',
        roots=[dict(path='.',access='read_write'), dict(path=str(external), access='read_only', attached=True,
            authorship='third_party', purpose='research-docs')], excludes=[]))
    store=ConversionStore(vault)
    converted=store.save(store.request(original,'free-external'), '[page 1]\nLocated original text.', pages=1)
    data=paper_graph.export_document(vault, dict(name='External study',file=str(original),clean_file=converted['path']))
    assert data['coverage']['status']=='full_conversion'
    assert data['original']['path']==original.as_posix()


def test_paper_export_refuses_an_unattached_external_original(paper, tmp_path):
    import pytest
    from resource_librarian.paper_graph import export_document
    vault,pdf,_=paper
    original=tmp_path/'outside.pdf';original.write_bytes(pdf.read_bytes())
    with pytest.raises(Exception,match='accepted|library|vault|Vault'):
        export_document(vault,dict(name='Unapproved',file=str(original)))
