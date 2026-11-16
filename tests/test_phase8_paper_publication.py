from test_phase8_paper_graph import paper


def _accepted(monkeypatch, pdf, accepted_by='person'):
    from resource_librarian import folder_review
    monkeypatch.setattr(folder_review, 'configuration', lambda _: {'enabled': True})
    decision = dict(purpose='research-docs', authorship='third_party', graph='papers', accepted_by=accepted_by)
    card = dict(id='folder-fixture', status='accepted', source_root=str(pdf.parent), path='.', decision=decision)
    monkeypatch.setattr(folder_review.FolderReview, 'list', lambda _: [card])
    monkeypatch.setattr(folder_review.FolderReview, 'validate', lambda *_: None)
    calls = []
    monkeypatch.setattr(folder_review, 'cli', lambda config, operation, payload:
                        calls.append((operation, payload)) or {'geographer_version':'0.2.0', 'published':True})
    return calls


READ = {'read': {'0': {'locator': 'p. 1', 'points': ['Opening evidence is stated.'], 'limits': []},
                 '1': {'locator': 'pp. 2-3', 'points': ['A method with a late detail.'],
                       'limits': ['Closing evidence is bounded.']}}}


def test_parse_only_prepares_the_projection_and_publish_runs_after_reading(paper, monkeypatch):
    """2026-11-16: publishing at parse sent empty claims and made two generations per paper."""
    import json
    from resource_librarian.batch import _parse, _publish
    from resource_librarian.registry import Context
    vault, pdf, converted = paper
    calls = _accepted(monkeypatch, pdf)
    item = {'name':'Study', 'file':'Inbox/original.pdf', 'clean_file':converted['path'], 'source_kind':'paper'}
    out = _parse(Context(tier='contribute', vault=vault), item)
    assert 'publication' not in out['paper_graph'] and calls == []
    done = _publish(Context(tier='contribute', vault=vault), {**item, 'deep_read': READ})
    assert done['status'] == 'complete' and calls[0][0][0] == 'import-library-paper'
    assert calls[0][1]['graph_label'] == 'papers'
    artifact = json.loads((vault.root / done['paper_graph']['path']).read_text(encoding='utf-8'))
    claims = [(c['text'], c['claim_type']) for s in artifact['sections'] for c in s['claims']]
    assert ('Opening evidence is stated.', 'reading_point') in claims
    assert ('Closing evidence is bounded.', 'reading_limit') in claims
    assert any('unverified' in x for x in artifact['coverage']['limitations'])


def test_agent_policy_decisions_publish_only_in_an_agent_mode_library(paper, monkeypatch):
    from resource_librarian import paper_graph
    vault, pdf, converted = paper
    calls = _accepted(monkeypatch, pdf, accepted_by='agent-policy')
    item = {'name':'Study', 'file':'Inbox/original.pdf', 'clean_file':converted['path']}
    artifact = paper_graph.write_artifact(vault, item)
    assert paper_graph.publish_artifact(vault, item, artifact)['status'] == 'awaiting_accepted_folder'
    vault.set_setting('promotion', 'mode', 'agent')
    assert paper_graph.publish_artifact(vault, item, artifact)['published'] is True and len(calls) == 1


def test_a_complete_text_layer_gets_a_free_page_anchored_conversion(paper, monkeypatch):
    from resource_librarian import paper_graph, text
    from resource_librarian.conversions import ConversionStore
    vault, pdf, _ = paper
    monkeypatch.setattr(text, 'extract', lambda *a: text.Extraction(pages=['First page text.', 'Second page text.']))
    data = paper_graph.export_document(vault, {'name': 'Usable', 'file': 'Inbox/original.pdf'}, text_layer=True)
    assert data['coverage']['status'] == 'full_conversion' and data['page_count'] == 2
    rel = paper_graph.text_layer_conversion(vault, pdf)                    # cached, not re-made
    assert ConversionStore(vault).page_units(rel) == [(1, 'First page text.'), (2, 'Second page text.')]
    monkeypatch.setattr(text, 'extract', lambda *a: text.Extraction(pages=['Text.', '   ']))
    other = vault.root / 'Inbox/scan.pdf'; other.write_bytes(b'another fixture')
    assert paper_graph.text_layer_conversion(vault, other) is None          # a page without text: none
    assert paper_graph.export_document(vault, {'name': 'Plain', 'file': 'Inbox/original.pdf'})['coverage']['status']         == 'catalogue_only'                                                # only the publish stage asks for it


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


def test_an_enriched_source_reruns_only_a_stage_added_after_it_was_read(vault, monkeypatch):
    """2026-11-16: papers read before the publish stage existed get it without a paid re-read."""
    from resource_librarian import batch, staging
    from resource_librarian.registry import Context
    store = staging.StagingStore(vault)
    store.add({"id": "s1", "kind": "source", "status": "staged", "name": "S", "sensitivity": "normal",
               "sections": {}, "history": []})
    ran = []
    stages = [(name, (lambda n: lambda ctx, item: ran.append(n) or {"status": "complete"})(name))
              for name, _ in batch.STAGES]
    monkeypatch.setattr(batch, "STAGES", stages[:-1])
    ctx = Context(tier="curate", vault=vault)
    approve = lambda: store.save({**store.load("s1"), "status": "approved"})
    approve()
    batch.start(ctx, requested_by="person")
    assert store.load("s1")["status"] == "enriched" and ran[-1] == "review"
    assert "enriched" in staging.DECIDABLE["approve"]
    ran.clear()
    monkeypatch.setattr(batch, "STAGES", stages)
    approve()
    batch.start(ctx, requested_by="person")
    assert ran == ["publish"]


def test_a_cleanup_that_lost_page_anchors_is_kept_unused_and_the_text_layer_is_read(paper, monkeypatch):
    """2026-11-16: 9 of 31 cleaned conversions merged or dropped a page marker, so their Sources
    were read without page locators and could never reach a paper graph."""
    from resource_librarian import batch
    from resource_librarian.conversions import ConversionStore
    from resource_librarian.registry import Context
    vault, pdf, mapped = paper
    store = ConversionStore(vault)
    unmapped = store.save(store.request(pdf, 'pdf_markdown:page-anchors-v2:fixture'),
                          '[page 1]\nOne.\n\n[page 3]\nThree, page two merged away.', pages=3)
    real_call = batch.REGISTRY.call
    def call(name, args, ctx):
        if name == 'pdf_to_markdown':
            return {'path': unmapped['path']}
        return real_call(name, args, ctx)
    monkeypatch.setattr(batch.REGISTRY, 'call', call)
    ctx = Context(tier='contribute', vault=vault)
    seen = []
    monkeypatch.setattr(batch, '_update_item', lambda ctx, item_id, fn: seen.append(item_id))
    out = batch._parse(ctx, {'id': 'x', 'name': 'Study', 'file': 'Inbox/original.pdf',
                             'intake': {'quality': {'verdict': 'cleanup'}}})
    assert seen == [] and 'lost its page anchors' in out['cleanup']
    assert batch._page_mapped(ctx, mapped['path']) and not batch._page_mapped(ctx, unmapped['path'])
