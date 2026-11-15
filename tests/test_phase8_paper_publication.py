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
