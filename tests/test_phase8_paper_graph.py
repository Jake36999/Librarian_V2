"""S3: full generated conversion, original identity and honest page mapping."""
import json

import pytest

from resource_librarian import access, deep_read, tools  # noqa: F401 - register tools
from resource_librarian.conversions import ConversionStore
from resource_librarian.init import init
from resource_librarian.vault import Vault


@pytest.fixture
def paper(tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARIAN_CONFIG_DIR', str(tmp_path / 'config'))
    init(tmp_path / 'library', name='Paper fixture')
    vault = Vault(tmp_path / 'library')
    pdf = vault.root / 'Inbox/original.pdf'
    pdf.write_bytes(b'PDF fixture; no model or parser needed')
    monkeypatch.setattr(access, '_native_authorship', lambda *args: 'third_party')
    store = ConversionStore(vault)
    request = store.request(pdf, 'scripted-page-conversion:v1')
    out = store.save(request,
        '[page 1]\n# Introduction\nOpening evidence.\n\n'
        '[page 2]\n# Method\nA method with a late detail.\n\n'
        '[page 3]\nClosing evidence beyond the catalogue summary.', pages=3)
    return vault, pdf, out


def test_deep_read_keeps_original_page_numbers_from_generated_conversion(paper):
    vault, pdf, converted = paper
    representation, units = deep_read.source(vault, {'file': 'Inbox/original.pdf', 'clean_file': converted['path']})
    assert representation == 'clean_file'
    assert [n for n, _ in units] == [1, 2, 3]
    assert units[-1][1].endswith('Closing evidence beyond the catalogue summary.')


def test_paper_export_uses_full_conversion_and_dik_chapters(paper):
    from resource_librarian.paper_graph import export_document
    vault, pdf, converted = paper
    data = export_document(vault, {'name': 'Study', 'title': 'Study title',
        'file': 'Inbox/original.pdf', 'clean_file': converted['path'],
        'sections': {'Bottom Line': 'A tiny catalogue summary.'}})
    assert data['coverage']['status'] == 'full_conversion'
    assert data['file_path'] == pdf.resolve().as_posix()
    assert data['original']['authorship'] == 'third_party'
    assert data['conversion']['authorship'] == 'generated'
    assert data['conversion']['evidence_id'] == converted['evidence_id']
    assert [(s['page_start'], s['page_end']) for s in data['sections']] == [(1, 1), (2, 3)]
    assert 'Closing evidence beyond' in data['sections'][-1]['text']
    assert all('tiny catalogue' not in s['text'] for s in data['sections'])
    assert data['usage']['cost_usd'] == 0


def test_missing_original_is_catalogue_only_without_invented_page_verification(paper):
    from resource_librarian.paper_graph import export_document
    vault, _, converted = paper
    data = export_document(vault, {'name': 'Study', 'file': 'Inbox/not-present.pdf',
                                'clean_file': converted['path']})
    assert data['coverage']['status'] == 'catalogue_only'
    assert data['sections'] == []
    assert data['coverage']['page_verification'] is False


def test_legacy_unmapped_conversion_cannot_claim_pdf_page_coordinates(paper):
    from resource_librarian.paper_graph import export_document
    vault, pdf, _ = paper
    store = ConversionStore(vault)
    out = store.save(store.request(pdf, 'unmapped-legacy'), '# Method\nUnmapped prose.', pages=3)
    data = export_document(vault, {'name': 'Legacy', 'file': 'Inbox/original.pdf', 'clean_file': out['path']})
    assert data['coverage']['status'] == 'catalogue_only'
    assert data['sections'] == []
    assert 'page' in ' '.join(data['coverage']['limitations']).lower()


def test_native_batch_prepares_free_graph_artifact_from_existing_conversion(paper):
    from resource_librarian.batch import _parse
    from resource_librarian.registry import Context
    vault, _, converted = paper
    out = _parse(Context(tier='contribute', vault=vault), {'name': 'Study',
        'file': 'Inbox/original.pdf', 'clean_file': converted['path'], 'source_kind': 'paper'})
    assert out['paper_graph']['coverage']['status'] == 'full_conversion'
    artifact = json.loads((vault.root / out['paper_graph']['path']).read_text(encoding='utf-8'))
    assert artifact['sections'][-1]['page_end'] == 3


def test_pdf_cleanup_sends_page_boundaries_and_records_verified_mapping(paper, monkeypatch):
    from resource_librarian import pdf_markdown, text
    from resource_librarian.registry import REGISTRY, Context
    vault, _, _ = paper
    monkeypatch.setattr(text, 'extract', lambda *args: text.Extraction(pages=['First.', 'Second.']))
    seen = []
    def scripted(pages, *args, **kwargs):
        seen.extend(pages)
        return '\n\n'.join(pages), 1
    monkeypatch.setattr(pdf_markdown, 'clean_document', scripted)
    out = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/original.pdf'}, Context(tier='contribute', vault=vault))
    assert 'error' not in out, out
    assert seen == ['[page 1]\nFirst.', '[page 2]\nSecond.']
    assert ConversionStore(vault).page_units(out['path']) == [(1, 'First.'), (2, 'Second.')]


def test_previous_paid_cleanup_is_retained_without_automatic_reconversion(paper, monkeypatch):
    from resource_librarian import pdf_markdown
    from resource_librarian.registry import REGISTRY, Context
    vault, pdf, _ = paper
    store = ConversionStore(vault)
    old = store.save(store.request(pdf, 'pdf_markdown:v1:' + pdf_markdown.MODEL), 'Legacy paid text.', pages=3)
    def forbidden(*args, **kwargs):
        pytest.fail('Existing paid conversion must not be silently replaced')
    monkeypatch.setattr(pdf_markdown, 'clean_document', forbidden)
    out = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/original.pdf'}, Context(tier='contribute', vault=vault))
    assert out['cached'] is True and out['path'] == old['path']
    assert out['page_mapping'] == 'unverified'


def test_incomplete_ocr_never_claims_a_full_conversion(paper):
    from resource_librarian.paper_graph import export_document
    vault, pdf, _ = paper
    store = ConversionStore(vault)
    converted = store.save(store.request(pdf, 'incomplete-ocr:v1'),
        '[page 1]\nRead content.\n\n[page 2]\n', pages=2,
        errors=[{'page': 2, 'error': 'scripted unavailable'}], needed=2, read=1)
    data = export_document(vault, {'name': 'Partial', 'file': 'Inbox/original.pdf', 'clean_file': converted['path']})
    assert data['coverage']['status'] == 'catalogue_only'
    assert data['sections'] == []


def test_ocr_coverage_metadata_is_bound_to_conversion_evidence(paper):
    from resource_librarian.rules import Refusal
    vault, pdf, _ = paper
    store = ConversionStore(vault)
    converted = store.save(store.request(pdf, 'ocr-binding'), '[page 1]\nText.', pages=1,
                           errors=[{'page': 1, 'error': 'not read'}], needed=1, read=0)
    index = json.loads(store.index_path.read_text(encoding='utf-8'))
    entry = next(e for e in index['items'].values() if e['path'] == converted['path'])
    entry['errors'] = []; entry['read'] = 1
    store.index_path.write_text(json.dumps(index), encoding='utf-8')
    with pytest.raises(Refusal, match='EVIDENCE_IS_NEVER_EDITED'):
        store.page_units(converted['path'])


def test_read_chunk_covering_a_whole_middle_chapter_counts_its_actual_coverage(paper):
    from resource_librarian import dik
    vault, _, _ = paper
    data = dik.document(vault, 'Study', ['# Introduction\nA.', '# Method\nB.', '# Results\nC.'],
        {'0': {'points': ['Scripted source point.']}}, [(1, 3)], 'fixture-revision')
    assert data['coverage'] == 'full'
    assert all(row['coverage'] == 'full' for row in data['data'])


def test_native_dik_keeps_original_page_numbers_when_an_earlier_page_has_no_text(paper, monkeypatch):
    from resource_librarian import batch, dik
    from resource_librarian.staging import StagingStore
    from resource_librarian.registry import Context
    vault, pdf, _ = paper
    store = ConversionStore(vault)
    converted = store.save(store.request(pdf, 'blank-first-page'),
        '[page 1]\n\n[page 2]\n# Method\nMethod text.\n\n[page 3]\n# Results\nResult text.', pages=3)
    item = StagingStore(vault).add({'id': 's-study', 'kind': 'source', 'name': 'Study',
        'source_kind': 'paper', 'file': 'Inbox/original.pdf', 'clean_file': converted['path']})
    monkeypatch.setattr(deep_read, 'read_parts', lambda *args: {'0': {'points': ['Scripted point.']}})
    batch._data(Context(vault=vault), item)
    locators = [row['locator'] for row in dik.load(vault, 'Study')['data']]
    assert 'pp. 3-3' in locators, locators
