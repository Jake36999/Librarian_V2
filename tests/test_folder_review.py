import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from resource_librarian.vault import Vault


@pytest.fixture
def library(tmp_path):
    root = tmp_path / 'library'; root.mkdir()
    vault = Vault(root)
    source = tmp_path / 'source'; source.mkdir()
    for name in ['src/a.py', 'third_party_alpha/a.py', 'third_party_beta/b.py', 'docs/note.md']:
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('synthetic fixture\n')
    return vault, source


def fake_planner(surveyed):
    return {'plan_version': 'workspace-init-v1', 'geographer_version': '0.2.0',
        'shared_survey_fingerprint': surveyed.fingerprint, 'root': surveyed.canonical_root,
        'partitions': [dict(key=name, subtrees=[name], file_counts={'.py': 1}, bytes=18,
                           suggestion=dict(purpose='third-party' if name.startswith('third_party') else 'own-current',
                                           reasons=['synthetic metadata signal']))
                       for name in ['src', 'third_party_alpha', 'third_party_beta', 'docs']],
        'excluded': [], 'credential_refusals': {'count': 0, 'paths': []}}


def test_stages_folder_cards_with_shared_fingerprint_and_group_suggestion(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner)
    cards = review.survey(source)['cards']
    assert len(cards) == 4
    assert all(c['status'] == 'staged' and c['description']['state'] == 'awaiting_model_draft' for c in cards)
    third = [c for c in cards if c['suggested_purpose'] == 'third-party']
    assert len({c['suggested_graph'] for c in third}) == 1
    assert third[0]['suggested_graph'] == 'library-third-party'


def test_accept_is_person_only_and_attached_roots_stay_readonly(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {'graphs': []})
    cards = review.survey(source)['cards']; card = next(c for c in cards if c['path'] == 'src')
    with pytest.raises(ValueError, match='PERSON_CONFIRMS'):
        review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='library-code', person=False)
    result = review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='library-code', person=True)
    assert result['status'] == 'accepted' and applied
    manifest = json.loads((vault.librarian / 'content-roots.json').read_text())
    row = next(r for r in manifest['roots'] if r['path'] == str(source / 'src'))
    assert row['access'] == 'read_only' and row['attached']


def test_unchanged_acceptance_survives_resurvey_but_changed_folder_reasks(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    cards = review.survey(source)['cards']; card = next(c for c in cards if c['path'] == 'src')
    review.accept(card['id'], card['folder_fingerprint'], purpose='own-current', graph='library-code', person=True)
    (source / 'docs/note.md').write_text('an unrelated edit')
    assert next(c for c in review.survey(source)['cards'] if c['path'] == 'src')['status'] == 'accepted'
    (source / 'src/a.py').write_text('a changed source')
    assert next(c for c in review.survey(source)['cards'] if c['path'] == 'src')['status'] == 'staged'


def test_excluded_folder_never_reaches_ingest(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {})
    card = review.survey(source)['cards'][0]
    review.accept(card['id'], card['folder_fingerprint'], purpose='exclude', graph='', person=True)
    assert not applied


def test_third_party_folder_disables_project_writes(library):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian import projects
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    card = next(c for c in review.survey(source)['cards'] if c['path'] == 'third_party_alpha')
    review.accept(card['id'], card['folder_fingerprint'], purpose='third-party', graph='library-third-party', person=True)
    projects._save(vault, {'enabled': True, 'roots': [{'id': 'test', 'path': str(source), 'writes': True}]})
    from resource_librarian.rules import Refusal
    with pytest.raises(Refusal) as refused:
        projects.edit(vault, source, 'third_party_alpha/a.py', 'replace', 'new', 'synthetic fixture')
    assert refused.value.code == 'FOLDER_READ_ONLY'


def test_accepted_child_overrides_parent_and_every_folder_is_reviewable(library):
    from resource_librarian.folder_review import FolderReview, decision_for
    vault, source = library
    nested = source / 'third_party_alpha/own-analysis'; nested.mkdir(); (nested / 'report.md').write_text('synthetic')
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {})
    cards = review.survey(source)['cards']
    parent = next(c for c in cards if c['path'] == 'third_party_alpha')
    child = next(c for c in cards if c['path'] == 'third_party_alpha/own-analysis')
    review.accept(parent['id'], parent['folder_fingerprint'], purpose='third-party', graph='references', person=True)
    assert decision_for(vault, nested / 'report.md')['purpose'] == 'third-party'
    review.accept(child['id'], child['folder_fingerprint'], purpose='own-docs', graph='analysis', person=True)
    assert decision_for(vault, nested / 'report.md')['purpose'] == 'own-docs'


def test_model_draft_is_explicitly_approved_metadata_only_and_never_accepted(library, monkeypatch):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian import clerk
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    with pytest.raises(ValueError, match='SPEND_APPROVAL_REQUIRED'):
        review.draft(card['id'], object())
    def run(tasks, endpoint):
        assert 'synthetic fixture' not in tasks[0].chunk
        assert tasks[1].kind.name == 'sensitivity'
        return [SimpleNamespace(ok=True, value={'description': 'A synthetic folder inventory.'}),
                SimpleNamespace(ok=True, value={'sensitivity': 'normal', 'reason': 'metadata only'})]
    monkeypatch.setattr(clerk, 'run', run)
    result = review.draft(card['id'], clerk.Scripted(lambda _: {}), approved=True)
    assert result['status'] == 'staged' and result['description']['draft']
    assert result['description']['state'] == 'model_draft'


def test_folder_review_is_woven_into_native_attach_without_a_second_survey(library, monkeypatch):
    from resource_librarian import content_roots, folder_review
    vault, source = library
    monkeypatch.setattr(type(vault), 'exists', lambda self: True)
    monkeypatch.setattr(folder_review, 'configuration', lambda _: {'enabled': True})
    calls = []
    def planner(config, operation, payload):
        calls.append(payload['fingerprint'])
        return fake_planner(SimpleNamespace(fingerprint=payload['fingerprint'], canonical_root=payload['root']))
    monkeypatch.setattr(folder_review, 'cli', planner)
    plan = content_roots.plan_attach(vault, source)
    assert plan['geo_grapher']['shared_survey_fingerprint'] == plan['survey_fingerprint']
    result = content_roots.apply_attach(vault, source, plan['survey_fingerprint'])
    assert result['folders']['cards']
    assert len(calls) == 2, 'one shared survey/plan per native planning and compare-and-apply operation'


def test_writer_cannot_modify_a_readonly_folder_even_with_a_declared_target(library):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.coordination import VaultWriter
    vault, _ = library; source = vault.root / 'third_party_alpha'; source.mkdir()
    target = source / 'a.py'; target.write_text('synthetic')
    def planner(found):
        p = fake_planner(found); p['partitions'] = [dict(key='residual', subtrees=[], file_counts={'.py':1},
            bytes=9, suggestion=dict(purpose='third-party', reasons=['synthetic']))]; return p
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    card = review.survey(source)['cards'][0]
    review.accept(card['id'], card['folder_fingerprint'], purpose='third-party', graph='references', person=True)
    writer = VaultWriter(vault)
    try:
        with pytest.raises(Exception, match='READ_ONLY|read.only'):
            writer.submit(lambda: target.write_text('changed'), targets=['third_party_alpha/a.py'])
    finally:
        writer.close()
    assert target.read_text() == 'synthetic'


def test_enabled_project_attachment_keeps_sidecar_in_library_and_cannot_enable_writes(library):
    from resource_librarian import projects
    vault, source = library
    vault.librarian.mkdir(exist_ok=True)
    (vault.librarian / 'geographer.json').write_text(json.dumps({'enabled': True}))
    result = projects.add_root(vault, str(source))
    assert not (source / 'librarian-app').exists()
    assert result['access'] == 'read_only'
    with pytest.raises(Exception, match='READ_ONLY|read.only'):
        projects.set_writes(vault, result['id'], True)


@pytest.mark.parametrize('parent_purpose', ['exclude', 'third-party'])
def test_accepted_internal_child_override_controls_index_scope_and_write_access(library, parent_purpose):
    from resource_librarian.folder_review import FolderReview, refuse_write
    from resource_librarian.content_roots import iter_documents
    vault, _ = library
    parent = vault.root / 'mixed'; child = parent / 'own-analysis'; child.mkdir(parents=True)
    target = child / 'report.md'; target.write_text('synthetic own document')
    def planner(found):
        return dict(plan_version='workspace-init-v1', shared_survey_fingerprint=found.fingerprint,
            partitions=[dict(key='residual', subtrees=[], file_counts={'.md':1}, bytes=22,
                suggestion=dict(purpose='third-party', reasons=['synthetic']))])
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    cards = review.survey(parent)['cards']; root = next(c for c in cards if c['path'] == '.')
    nested = next(c for c in cards if c['path'] == 'own-analysis')
    review.accept(root['id'], root['folder_fingerprint'], purpose=parent_purpose, graph='' if parent_purpose=='exclude' else 'references', person=True)
    review.accept(nested['id'], nested['folder_fingerprint'], purpose='own-docs', graph='own-analysis', person=True)
    assert target in iter_documents(vault.root)
    refuse_write(vault, target)


def test_accepting_another_card_cannot_silently_reingest_a_changed_accepted_folder(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library; applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {})
    cards = review.survey(source)['cards']
    first = next(c for c in cards if c['path'] == 'src')
    second = next(c for c in cards if c['path'] == 'third_party_alpha')
    review.accept(first['id'], first['folder_fingerprint'], purpose='own-current', graph='own', person=True)
    (source / 'src/a.py').write_text('changed since acceptance')
    with pytest.raises(ValueError, match='FOLDER_STALE'):
        review.accept(second['id'], second['folder_fingerprint'], purpose='third-party', graph='references', person=True)
    assert len(applied) == 1


# --- Large-repository review (owner, 2026-11-15): 1,583 cards / ~1,100 graphs on quantule_mapper ---

def test_one_graph_per_project_and_inherited_subfolders_join_their_parents_graph(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    deep = source / 'src/pkg/sub'; deep.mkdir(parents=True); (deep / 'm.py').write_text('synthetic')
    cards = {c['path']: c for c in FolderReview(vault, planner=fake_planner).survey(source)['cards']}
    project = f'{vault.title}-{source.name}'
    # one stratum per graph (Geo-Grapher invariant): docs get the project's -docs graph
    assert cards['src']['suggested_graph'] == project
    assert cards['docs']['suggested_graph'] == project or cards['docs']['suggested_purpose'] == 'own-current'
    assert cards['src/pkg']['suggested_graph'] == cards['src/pkg/sub']['suggested_graph'] == project
    assert cards['src/pkg']['inherited'] is True and cards['src/pkg']['inherited_from'] == 'src'
    assert cards['src']['inherited'] is False
    assert {cards['third_party_alpha']['suggested_graph'], cards['third_party_beta']['suggested_graph']} == \
        {f'{vault.title}-third-party'}
    own_graphs = {c['suggested_graph'] for c in cards.values() if c['suggested_purpose'] != 'third-party'}
    assert own_graphs <= {project, project + '-docs', project + '-data', project + '-logs', project + '-legacy'}


def test_content_signals_suggest_data_logs_and_objects_instead_of_inheriting_code(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    for folder, ext, n in (('src/sweep_runs', '.json', 12), ('src/GIFS', '.gif', 9), ('src/runtime_logs', '.log', 6),
                           ('src/mixed', '.py', 3)):
        path = source / folder; path.mkdir(parents=True)
        for i in range(n):
            (path / f'f{i}{ext}').write_text('synthetic')
    (source / 'src/mixed/table.csv').write_text('a,b')
    cards = {c['path']: c for c in FolderReview(vault, planner=fake_planner).survey(source)['cards']}
    assert cards['src/sweep_runs']['suggested_purpose'] == 'data'
    assert cards['src/GIFS']['suggested_purpose'] == 'exclude'
    assert cards['src/runtime_logs']['suggested_purpose'] == 'logs/transcripts'
    assert cards['src/mixed']['suggested_purpose'] == 'own-current' and cards['src/mixed']['inherited'] is True
    for path in ('src/sweep_runs', 'src/GIFS', 'src/runtime_logs'):
        assert cards[path]['inherited'] is False and 'content' in cards[path]['reasons'][0]


def test_resurvey_refreshes_undecided_suggestions_but_keeps_decisions(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    first = {c['path']: c for c in review.survey(source)['cards']}
    for card in first.values():                                  # simulate cards staged by older code
        card['suggested_graph'] = 'stale-per-folder-graph'; review.store.save(card)
    review.accept(first['docs']['id'], first['docs']['folder_fingerprint'], purpose='own-docs',
                  graph='kept-by-person', person=True)
    again = {c['path']: c for c in review.survey(source)['cards']}
    assert again['src']['suggested_graph'] == f'{vault.title}-{source.name}'      # refreshed
    assert again['docs']['status'] == 'accepted' and again['docs']['decision']['graph'] == 'kept-by-person'


# --- Agent-mode orchestration (owner, 2026-11-15): only sensitive or un-inferable items wait for a person ---

def _agent_mode(vault):
    vault.set_setting("promotion", "mode", "agent")


def _checked(review):
    """Simulate the metadata-only Clerk check having run on every card."""
    for card in review.list():
        card['sensitivity'] = dict(sensitivity='normal', reason='checked'); review.store.save(card)


def test_policy_accept_needs_agent_mode(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    review.survey(source)
    with pytest.raises(ValueError, match='PROMOTION_MODE'):
        review.accept_by_policy(source)


def test_policy_accept_takes_unambiguous_suggestions_in_one_application_and_holds_the_rest(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    runs = source / 'src/sweep_runs'; runs.mkdir(parents=True)
    for i in range(5):
        (runs / f'r{i}.csv').write_text('a,b')
    _agent_mode(vault)
    applied = []
    review = FolderReview(vault, planner=fake_planner, applier=lambda request: applied.append(request) or {'graphs': []})
    cards = {c['path']: c for c in review.survey(source)['cards']}
    _checked(review); cards = {c['path']: c for c in review.list()}
    sensitive = cards['third_party_beta']; sensitive['sensitivity'] = dict(sensitivity='review_required', reason='dual-use')
    review.store.save(sensitive)
    out = review.accept_by_policy(source)
    assert len(applied) == 1                                          # one graph application for the set
    after = {c['path']: c for c in review.list()}
    assert after['src']['status'] == 'accepted' and after['src']['decision']['accepted_by'] == 'agent-policy'
    assert after['src']['decision']['graph'] == cards['src']['suggested_graph']
    assert after['third_party_alpha']['decision']['authorship'] == 'third_party'
    held = {h['path']: h['reason'] for h in out['held']}
    assert 'sensitive' in held['third_party_beta'] and after['third_party_beta']['status'] == 'staged'
    # data inside the project's own code: authorship inferred from the nearest classified ancestor
    assert after['src/sweep_runs']['decision']['authorship'] == 'owner_created'
    assert out['accepted'] == sorted(p for p, c in after.items() if c['status'] == 'accepted')


def test_policy_accept_never_overrides_a_persons_decision(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    _agent_mode(vault)
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    cards = {c['path']: c for c in review.survey(source)['cards']}
    review.accept(cards['docs']['id'], cards['docs']['folder_fingerprint'], purpose='own-docs', graph='mine', person=True)
    _checked(review)
    review.accept_by_policy(source)
    docs = {c['path']: c for c in review.list()}['docs']
    assert docs['decision']['accepted_by'] == 'person' and docs['decision']['graph'] == 'mine'


def test_staging_counts_separate_covered_folder_cards_and_read_folder_sensitivity(library):
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.staging import StagingStore
    vault, source = library
    (source / 'src/pkg').mkdir(); (source / 'src/pkg/m.py').write_text('synthetic')
    FolderReview(vault, planner=fake_planner).survey(source)
    counts = StagingStore(vault).counts()['folder']
    assert counts['covered'] >= 1                     # src/pkg inherits from src
    assert counts['staged'] == 4                       # the four partitions that need a look
    assert counts.get('sensitive_waiting', 0) == 0     # pending clerk checks are not "sensitive"


def test_policy_accept_holds_folders_whose_sensitivity_was_never_checked(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    _agent_mode(vault)
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    review.survey(source)
    out = review.accept_by_policy(source)
    assert out['accepted'] == [] and all('not yet checked' in h['reason'] for h in out['held'])


class _RealishEndpoint:
    """Not clerk.Scripted: stands in for a production (qualified) Clerk route."""
    name = "realish"; concurrency = 1

    def __init__(self):
        self.payloads = []

    def complete(self, payload, repair=""):
        import json as _json
        self.payloads.append(payload)
        if payload["task"] == "sensitivity":
            return _json.dumps({"sensitivity": "normal", "reason": "metadata only"}), "realish"
        return _json.dumps({"description": "A folder of Python source files."}), "realish"


def test_production_folder_check_needs_the_owners_recorded_approval(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    endpoint = _RealishEndpoint()
    with pytest.raises(ValueError, match='FOLDER_DRAFT_DISABLED'):
        review.draft(card['id'], endpoint, approved=True)
    vault.set_setting('folders', 'production_drafting', True)
    drafted = review.draft(card['id'], endpoint, approved=True)
    assert drafted['sensitivity']['sensitivity'] == 'normal'
    assert drafted['description']['state'] == 'model_draft' and drafted['description']['draft'] is True
    sent = ' '.join(str(p['user']) for p in endpoint.payloads)
    assert 'synthetic fixture' not in sent                                # metadata only, never file text


def test_policy_skips_inherited_cards_and_excludes_need_no_sensitivity_check(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    (source / 'src/pkg').mkdir(); (source / 'src/pkg/m.py').write_text('synthetic')
    _agent_mode(vault)
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    cards = {c['path']: c for c in review.survey(source)['cards']}
    docs = cards['docs']; docs['suggested_purpose'] = 'exclude'; review.store.save(docs)   # never ingested
    src = cards['src']; src['sensitivity'] = dict(sensitivity='normal', reason='checked'); review.store.save(src)
    out = review.accept_by_policy(source)
    assert 'src' in out['accepted'] and 'docs' in out['accepted']          # exclude needs no check
    assert 'src/pkg' not in out['accepted'] and out['covered'] >= 1         # inherited: covered by src
    assert not any(h['path'] == 'src/pkg' for h in out['held'])


def test_policy_infers_data_authorship_from_its_nearest_classified_ancestor(library):
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    for folder in ('src/runs', 'third_party_alpha/dump'):
        path = source / folder; path.mkdir(parents=True)
        for i in range(5):
            (path / f'r{i}.csv').write_text('a,b')
    _agent_mode(vault)
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    review.survey(source); _checked(review)
    review.accept_by_policy(source)
    after = {c['path']: c for c in review.list()}
    assert after['src/runs']['decision']['purpose'] == 'data'
    assert after['src/runs']['decision']['authorship'] == 'owner_created'        # inside own project code
    assert after['third_party_alpha/dump'].get('inherited') is True               # stays third-party, covered
    assert 'decision' not in after['third_party_alpha/dump']
    assert 'ancestor' in after['src/runs']['decision']['policy']['rule']


def test_a_failed_geographer_call_writes_the_promised_diagnostic_log(library, tmp_path):
    import sys, json as _json
    from resource_librarian.folder_review import cli
    vault, _ = library
    script = tmp_path / 'boom.py'
    script.write_text("import sys; sys.stderr.write('Traceback: catalog locked\n'); sys.exit(1)")
    config = dict(enabled=True, command=[sys.executable, str(script)], wheel_version='0.2.0', log_dir=str(vault.root / 'logs'))
    with pytest.raises(ValueError, match='GEOGRAPHER_CALL_FAILED') as caught:
        cli(config, ['apply-folder-review'], {'x': 1})
    assert 'catalog locked' not in str(caught.value)            # never reflected into the UI
    log = (vault.root / 'logs' / 'geographer-cli.log').read_text(encoding='utf-8')
    assert 'apply-folder-review' in log and 'catalog locked' in log and 'exit 1' in log


def test_suggested_graphs_keep_one_stratum_per_graph():
    from resource_librarian.folder_review import suggested_graph
    names = {p: suggested_graph('Lab', 'qm', p) for p in
             ('own-current', 'own-docs', 'own-legacy', 'data', 'logs/transcripts', 'third-party', 'research-docs')}
    assert names == {'own-current': 'Lab-qm', 'own-docs': 'Lab-qm-docs', 'own-legacy': 'Lab-qm-legacy',
                     'data': 'Lab-qm-data', 'logs/transcripts': 'Lab-qm-logs',
                     'third-party': 'Lab-third-party', 'research-docs': 'Lab-third-party-papers'}
    assert len(set(names.values())) == len(names)                     # never two strata in one graph


def test_a_library_of_several_projects_can_keep_third_party_material_per_project(library):
    """Owner, 2026-11-16: boundaries between projects must not blur in Resource-Library."""
    from resource_librarian.folder_review import FolderReview, suggested_graph
    vault, source = library
    vault.set_setting('folders', 'third_party_graph', 'project')
    cards = FolderReview(vault, planner=fake_planner).survey(source)['cards']
    third = {c['suggested_graph'] for c in cards if c['suggested_purpose'] == 'third-party'}
    assert third == {f'library-{source.name}-third-party'}
    assert suggested_graph('L', 'p', 'research-docs', 'project') == 'L-p-third-party-papers'
    assert suggested_graph('L', 'p', 'research-docs') == 'L-third-party-papers'      # default unchanged
    with pytest.raises(ValueError, match='third_party_graph'):
        suggested_graph('L', 'p', 'third-party', 'folder')


def test_subtree_index_matches_the_original_scan_exactly():
    """2026-11-16: the per-folder scan was folders x files; the index must give identical rows
    (same order, so the same folder fingerprints)."""
    import random
    from resource_librarian.folder_review import Subtrees
    rnd = random.Random(3)
    names = set()
    for _ in range(400):
        depth = rnd.randint(1, 5)
        parts = [rnd.choice(['a', 'b', 'ab', 'a.b', 'c d']) for _ in range(depth)]
        for d in range(1, depth):
            names.add('/'.join(parts[:d]) + '/')
        names.add('/'.join(parts) + rnd.choice(['', '.md', '.py']))
    entries = sorted((n, rnd.randint(-1, 50), 0) for n in names)
    index = Subtrees(entries)
    for rel in ['.'] + sorted({n.rstrip('/') for n in names}):
        brute = [r for r in entries if rel == '.' or r[0].rstrip('/') == rel or r[0].startswith(rel + '/')]
        assert index.rows(rel) == brute, rel


def test_a_large_tree_surveys_in_linear_time(library):
    import time
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    for i in range(300):
        for j in range(10):
            path = source / 'tmp' / f'w{i}' / f'f{j}.md'; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x')
    started = time.perf_counter()
    cards = FolderReview(vault, planner=fake_planner).survey(source)['cards']
    assert len(cards) >= 300 and time.perf_counter() - started < 120


def test_policy_covers_folders_under_an_excluded_parent_instead_of_holding_them(library):
    """2026-11-16: 1,639 cards under an excluded tmp waited for checks they never needed."""
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    (source / 'docs/scratch').mkdir(); (source / 'docs/scratch/n.md').write_text('synthetic')
    _agent_mode(vault)
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    cards = {c['path']: c for c in review.survey(source)['cards']}
    docs = cards['docs']; docs['suggested_purpose'] = 'exclude'; review.store.save(docs)
    child = cards['docs/scratch']                  # its own suggestion, sensitivity never checked
    child.update(inherited=False, inherited_from=None, suggested_purpose='own-docs'); review.store.save(child)
    out = review.accept_by_policy(source)
    assert 'docs' in out['accepted']
    assert 'docs/scratch' not in out['accepted']
    assert not any(h['path'] == 'docs/scratch' for h in out['held'])          # covered, not held
    assert out['covered'] >= 1


def test_policy_never_follows_a_link_or_junction(library, tmp_path):
    import os, subprocess
    from resource_librarian.folder_review import FolderReview
    vault, source = library
    outside = tmp_path / 'outside'; outside.mkdir(); (outside / 'secret.md').write_text('synthetic')
    (source / 'src/linked').mkdir(); (source / 'src/linked/a.py').write_text('synthetic')
    _agent_mode(vault)
    review = FolderReview(vault, planner=fake_planner, applier=lambda _: {'graphs': []})
    cards = {c['path']: c for c in review.survey(source)['cards']}
    _checked(review)
    card = review.store.load(cards['src/linked']['id']) if hasattr(review.store, 'load') else cards['src/linked']
    card.update(inherited=False, inherited_from=None, suggested_purpose='own-current',
                sensitivity=dict(sensitivity='normal', reason='checked'))
    review.store.save(card)
    target = source / 'src/linked'
    for f in target.iterdir(): f.unlink()
    target.rmdir()
    try:
        if os.name == 'nt':
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(target), str(outside)], check=True, capture_output=True)
        else:
            os.symlink(outside, target, target_is_directory=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip('this machine cannot create a link')
    try:
        out = review.accept_by_policy(source)
    except ValueError as exc:                       # a survey that refuses the link is also safe
        assert 'FOLDER' in str(exc); return
    assert 'src/linked' not in out['accepted']
    assert any(h['path'] == 'src/linked' and h['reason'].startswith('link') for h in out['held'])


def test_the_folder_brief_is_given_the_total_so_the_model_never_sums_counts(library, monkeypatch):
    """2026-11-16: summing extension counts itself, the Clerk wrote 2,211 files for 2,292."""
    import json as _json
    from resource_librarian.folder_review import FolderReview
    from resource_librarian import clerk
    vault, source = library; review = FolderReview(vault, planner=fake_planner)
    card = review.survey(source)['cards'][0]
    seen = {}
    def run(tasks, endpoint):
        seen.update(_json.loads(tasks[0].chunk))
        return [SimpleNamespace(ok=True, value={'description': 'A synthetic folder inventory.'}),
                SimpleNamespace(ok=True, value={'sensitivity': 'normal', 'reason': 'metadata only'})]
    monkeypatch.setattr(clerk, 'run', run)
    review.draft(card['id'], clerk.Scripted(lambda _: {}), approved=True)
    assert seen['files'] == sum(card['file_counts'].values()) and 'file_counts' in seen


def test_third_party_graphs_follow_the_observed_modality_so_one_graph_holds_one_stratum(library):
    """2026-11-17: Parallax's doc-modality repositories shared a label with a code-modality
    graph, and Geo-Grapher refused the whole application (GROUP_STRATUM_CONFLICT)."""
    from resource_librarian.folder_review import FolderReview, suggested_graph
    assert suggested_graph('lib', 'p', 'third-party') == 'lib-third-party'
    assert suggested_graph('lib', 'p', 'third-party', modality='code') == 'lib-third-party'
    assert suggested_graph('lib', 'p', 'third-party', modality='doc') == 'lib-third-party-docs'
    assert suggested_graph('lib', 'p', 'third-party', modality='paper') == \
        suggested_graph('lib', 'p', 'research-docs') == 'lib-third-party-papers'
    vault, source = library

    def planner(surveyed):
        plan = fake_planner(surveyed)
        for part in plan['partitions']:
            if part['key'] == 'third_party_beta':
                part['stratum'] = {'role': 'third_party', 'trust_tier': 'bronze', 'modality': 'doc'}
        return plan
    _agent_mode(vault)
    review = FolderReview(vault, planner=planner, applier=lambda _: {'graphs': []})
    cards = {c['path']: c for c in review.survey(source)['cards']}
    assert cards['third_party_alpha']['suggested_graph'].endswith('-third-party')
    assert cards['third_party_beta']['suggested_graph'].endswith('-third-party-docs')
    _checked(review)
    review.accept_by_policy(source)
    after = {c['path']: c for c in review.list()}
    assert after['third_party_beta']['decision']['graph'].endswith('-third-party-docs')
    assert after['third_party_alpha']['decision']['graph'].endswith('-third-party')
