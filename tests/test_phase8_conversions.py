"""S2 RED preparation; fake cleanup, no PDF parser/model/network required."""
import pytest

from resource_librarian import pdf_markdown, text, tools
from resource_librarian.init import init
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault
import json


@pytest.fixture
def conversion(tmp_path, monkeypatch):
    monkeypatch.setenv('LIBRARIAN_CONFIG_DIR', str(tmp_path / 'config'))
    init(tmp_path / 'library', name='Fixture')
    vault = Vault(tmp_path / 'library')
    pdf = vault.root / 'Inbox/book.pdf'
    pdf.parent.mkdir(exist_ok=True)
    pdf.write_bytes(b'fixture PDF bytes; extraction is mocked')
    sibling = pdf.with_suffix('.md')
    sibling.write_text('Owner-created sibling; never overwrite.', encoding='utf-8')
    monkeypatch.setattr(text, 'extract', lambda *args: text.Extraction(pages=['First page.', 'Second page.']))
    calls = []
    def clean(pages, *args, **kwargs):
        calls.append(list(pages))
        return '\n\n'.join(pages), 1
    monkeypatch.setattr(pdf_markdown, 'clean_document', clean)
    return vault, sibling, calls


def test_conversion_is_hidden_content_addressed_and_preserves_both_originals(conversion):
    vault, sibling, calls = conversion
    out = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, Context(tier='contribute', vault=vault))
    assert 'error' not in out, out
    assert out['path'].startswith('.librarian/conversions/')
    assert out['path'].endswith('.md')
    assert out['authorship'] == 'generated'
    assert len(out['evidence_id']) == 32
    assert sibling.read_text(encoding='utf-8') == 'Owner-created sibling; never overwrite.'
    assert (vault.root / 'Inbox/book.pdf').read_bytes() == b'fixture PDF bytes; extraction is mocked'


def test_identical_source_reuses_a_verified_conversion_without_another_cleanup_call(conversion):
    vault, _, calls = conversion
    ctx = Context(tier='contribute', vault=vault)
    first = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, ctx)
    second = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, ctx)
    assert first['path'] == second['path']
    assert second['cached'] is True
    assert len(calls) == 1


def test_changed_conversion_is_refused_without_spending_again(conversion):
    vault, _, calls = conversion
    ctx = Context(tier='contribute', vault=vault)
    first = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, ctx)
    (vault.root / first['path']).write_text('changed', encoding='utf-8')
    out = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, ctx)
    assert out['refused'] == 'EVIDENCE_IS_NEVER_EDITED'
    assert len(calls) == 1


def test_conversion_index_cannot_rebind_valid_text_to_another_original(conversion):
    vault, _, calls = conversion
    ctx = Context(tier='contribute', vault=vault)
    REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, ctx)
    path = vault.librarian / 'conversions/index.json'
    index = json.loads(path.read_text(encoding='utf-8'))
    next(iter(index['items'].values()))['original_sha256'] = 'wrong-original'
    path.write_text(json.dumps(index), encoding='utf-8')
    out = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, ctx)
    assert out['refused'] == 'EVIDENCE_IS_NEVER_EDITED'
    assert len(calls) == 1


def test_source_acceptance_does_not_expose_a_conversion_or_move_originals(conversion):
    from resource_librarian import staging
    vault, _, _ = conversion
    out = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, Context(tier='contribute', vault=vault))
    item = {'file': 'Inbox/book.pdf', 'clean_file': out['path']}
    assert staging._attachment_path(vault, out['path']) == vault.root / out['path']
    folder = vault.root / 'Sources/document/files'
    original_copy = staging._move_file(vault, item, folder)
    assert (vault.root / original_copy).is_file()
    assert (vault.root / 'Inbox/book.pdf').is_file()
    assert item['clean_file'] == out['path']
    assert (vault.root / out['path']).is_file()
    assert not list(folder.glob('*.md'))


def test_legacy_migration_is_explicit_manifested_and_never_guesses_a_sibling(conversion):
    from resource_librarian.conversions import migrate_confirmed
    vault, sibling, calls = conversion
    clean = vault.root / 'Inbox/confirmed-clean.md'
    clean.write_bytes(b'Previously generated conversion.\r\nSecond line.\n')
    dry = migrate_confirmed(vault, 'Inbox/book.pdf', 'Inbox/confirmed-clean.md')
    assert dry['dry_run'] is True
    assert not (vault.librarian / 'conversions/index.json').exists()
    applied = migrate_confirmed(vault, 'Inbox/book.pdf', 'Inbox/confirmed-clean.md', apply=True)
    assert applied['path'].startswith('.librarian/conversions/')
    assert (vault.root / applied['path']).read_bytes() == clean.read_bytes()
    assert sibling.read_text(encoding='utf-8') == 'Owner-created sibling; never overwrite.'
    assert clean.is_file() and (vault.root / 'Inbox/book.pdf').is_file()
    assert not calls
    manifest = json.loads((vault.librarian / 'conversions/migrations.json').read_text(encoding='utf-8'))
    assert manifest[0]['sha256'] == applied['sha256']
    assert manifest[0]['old_path'] == 'Inbox/confirmed-clean.md'
    assert manifest[0]['original_retained'] and manifest[0]['legacy_retained']


def test_legacy_clean_text_cannot_be_copied_to_visible_sources(conversion):
    from resource_librarian import staging
    vault, sibling, _ = conversion
    item = {'file': 'Inbox/book.pdf', 'clean_file': 'Inbox/book.md'}
    folder = vault.root / 'Sources/document/files'
    staging._move_file(vault, item, folder)
    assert item['clean_file'].startswith('.librarian/conversions/')
    assert sibling.is_file()
    assert not list(folder.glob('*.md'))


def test_survey_only_reports_explicit_conversion_references_and_apply_updates_them(conversion):
    from resource_librarian.conversions import survey_legacy, migrate_inventory
    from resource_librarian import notes
    vault, sibling, _ = conversion
    card = vault.root / 'Sources/document/Book.md'
    card.parent.mkdir(parents=True, exist_ok=True)
    card.write_text(notes.render({'type': 'source', 'file': 'Inbox/book.pdf',
                                 'file_markdown': 'Inbox/book.md'}, '# Book\n'), encoding='utf-8')
    # This association, rather than adjacency, is what confirms generated text.
    rows = survey_legacy(vault)
    assert len(rows) == 1 and rows[0]['reference'] == 'Sources/document/Book.md'
    assert migrate_inventory(vault)['dry_run'] is True
    assert notes.load(card).frontmatter['file_markdown'] == 'Inbox/book.md'
    out = migrate_inventory(vault, apply=True)
    assert len(out['results']) == 1
    assert notes.load(card).frontmatter['file_markdown'].startswith('.librarian/conversions/')
    assert sibling.is_file()
    assert survey_legacy(vault) == []


def test_conversion_cannot_be_indexed_as_a_note_even_by_direct_upsert(conversion):
    from resource_librarian.index import Index
    vault, _, _ = conversion
    result = REGISTRY.call('pdf_to_markdown', {'file': 'Inbox/book.pdf'}, Context(tier='contribute', vault=vault))
    index = Index(vault)
    try:
        assert index.upsert(vault.root / result['path']) is False
        assert not index.conn.execute('SELECT 1 FROM note WHERE path=?', (result['path'],)).fetchone()
    finally:
        index.close()
