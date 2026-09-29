import time

from resource_librarian.index import Index, split_text

from conftest import add_source, write_note


def test_build_roles_facets_links(vault):
    add_source(vault.root, "Alpha", "Alpha parses SQL into lineage graphs.",
               reading="It is not a query engine.", related="[[Beta]]")
    with Index(vault) as ix:
        report = ix.refresh()
        assert report.rebuilt and report.reason == "the index has never been built"
        rows = ix.conn.execute("SELECT heading, role FROM chunk WHERE note = 'Alpha'").fetchall()
        roles = {r["heading"]: r["role"] for r in rows}
        assert roles["Bottom Line"] == "claim" and roles["Reading Notes"] == "caveat"
        assert "Related" not in roles and "Evidence" not in roles
        facets = {(r["axis"], r["value"]) for r in
                  ix.conn.execute("SELECT axis, value FROM facet WHERE note = 'Alpha'")}
        assert ("license_class", "Permissive") in facets and ("kind", "repository") in facets
        assert ix.linked_from("Beta") == ["Alpha"]
        assert ix.note_row("alpha")["shape"] == "source"


def test_refresh_reads_only_changes(vault):
    path = add_source(vault.root, "Alpha", "one")
    add_source(vault.root, "Beta", "two")
    with Index(vault) as ix:
        ix.refresh()
        assert ix.refresh().to_dict()["upserted"] == 0
        time.sleep(0.01)
        path.write_text(path.read_text().replace("one", "uno"))
        report = ix.refresh()
        assert report.upserted == ["Sources/repository/Alpha.md"]
        path.unlink()
        assert ix.refresh().removed == ["Sources/repository/Alpha.md"]
        assert ix.note_row("Alpha") is None
        assert ix.conn.execute("SELECT COUNT(*) FROM chunk_fts").fetchone()[0] == \
            ix.conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]


def test_upsert_is_idempotent(vault):
    path = add_source(vault.root, "Alpha", "one")
    with Index(vault) as ix:
        ix.refresh()
        before = ix.conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0]
        assert ix.upsert(path) is False
        assert ix.upsert(path, force=True) is True
        assert ix.conn.execute("SELECT COUNT(*) FROM chunk").fetchone()[0] == before


def test_content_model_change_forces_rebuild(vault):
    add_source(vault.root, "Alpha", "one")
    with Index(vault) as ix:
        ix.refresh()
        model = vault.root / "About" / "Note Content Model.md"
        model.write_text(model.read_text() + "\n")
        ix._model = None
        assert ix.stale_reason()
        assert ix.refresh().rebuilt


def test_derived_is_disposable(vault):
    add_source(vault.root, "Alpha", "one")
    with Index(vault) as ix:
        ix.refresh()
        first = ix.stats()["chunks"]
    (vault.derived / "index.sqlite").unlink()
    with Index(vault) as ix:
        ix.refresh()
        assert ix.stats()["chunks"] == first


def test_duplicate_names_reported(vault):
    add_source(vault.root, "Alpha", "one")
    write_note(vault.root, "Concepts/Alpha.md", "type: concept", "x")
    with Index(vault) as ix:
        ix.refresh()
        assert ix.duplicate_names() == ["Alpha"]


def test_document_text_survives_rebuild(vault):
    add_source(vault.root, "Alpha", "one")
    with Index(vault) as ix:
        ix.refresh()
        assert ix.add_document_text("Alpha", ["page one text " * 10, "page two text " * 10]) == 2
        ix.rebuild()
        assert ix.stats()["document_chunks"] == 2


def test_split_text_bounds():
    text = "\n\n".join(["word " * 100] * 10)
    pieces = split_text(text, 1200)
    assert len(pieces) > 1 and all(len(p) <= 2400 for p in pieces)
    assert split_text("x" * 5000, 1000)[0] == "x" * 1000
