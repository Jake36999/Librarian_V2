from test_core_batch import core, _ctx


def test_folder_batch_derived_writes_use_core_writer(core, tmp_path, monkeypatch):
    from resource_librarian import batch, clerk, dik
    from resource_librarian.coordination import on_writer_thread
    from resource_librarian.folder_review import FolderReview
    root = tmp_path / 'code'; root.mkdir(); (root / 'test.py').write_text('VALUE = 2')
    def planner(found):
        return dict(shared_survey_fingerprint=found.fingerprint, partitions=[dict(
            key='all', subtrees=[], file_counts={'.py':1}, bytes=9,
            suggestion=dict(purpose='own-current', reasons=['fixture']))])
    review = FolderReview(core.vault, planner=planner)
    card = core.writer.submit(lambda: review.survey(root)['cards'][0], caller='test-survey')
    core.writer.submit(lambda: review.approve_batch([card['id']], person=True), caller='test-approve')
    observed = []
    original = dik.save
    def checked(*args):
        observed.append(on_writer_thread()); return original(*args)
    monkeypatch.setattr(dik, 'save', checked)
    endpoint = clerk.Scripted(lambda p: {'description':'Source content not examined.'}
        if p['task']=='folder_brief' else {'sensitivity':'normal','reason':'metadata only'})
    result = batch.start(_ctx(core, clerk=endpoint), 'person')
    assert result['status']=='finished'
    assert observed and all(observed)
    assert review.store.load(card['id'])['status']=='enriched'
