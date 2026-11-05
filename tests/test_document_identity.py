"""DEPLOY-04: document identity across moves and renames, and duplicates explained
by layer - never merged, moved or deleted."""
from __future__ import annotations

import os

import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.document_identity import external_identity, normalised_text
from resource_librarian.index import Index
from resource_librarian.registry import REGISTRY, Context


def put(vault, rel, text, newline="\n"):
    path = vault.root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline=newline) as handle:
        handle.write(text)
    return path


@pytest.fixture
def index(vault):
    put(vault, "Notes/Plan.md", "# Plan\n\nShip the adapter first.\n")
    with Index(vault) as idx:
        idx.refresh()
        yield idx


def doc_id(index, rel):
    found = index.document(rel)
    return found["doc_id"] if found else None


# --- identity ------------------------------------------------------------------------

def test_an_obsidian_style_rename_keeps_the_document(vault, index):
    before = doc_id(index, "Notes/Plan.md")
    os.rename(vault.root / "Notes/Plan.md", vault.root / "Notes/Roadmap.md")
    report = index.refresh()
    assert doc_id(index, "Notes/Roadmap.md") == before
    assert index.document("Notes/Plan.md") is None
    assert report.moved == [{"doc_id": before, "from": "Notes/Plan.md",
                             "to": "Notes/Roadmap.md", "matched_by": "file identity"}]


def test_a_move_to_another_folder_keeps_it_even_when_edited_in_the_same_breath(vault, index):
    before = doc_id(index, "Notes/Plan.md")
    (vault.root / "Inbox").mkdir(exist_ok=True)
    os.rename(vault.root / "Notes/Plan.md", vault.root / "Inbox/Plan.md")
    put(vault, "Inbox/Plan.md", "# Plan\n\nShip the adapter first, then the docs.\n")
    index.refresh()
    assert doc_id(index, "Inbox/Plan.md") == before


def test_a_move_that_rewrote_the_file_is_recognised_by_its_bytes(vault, index):
    before = doc_id(index, "Notes/Plan.md")
    data = (vault.root / "Notes/Plan.md").read_bytes()
    (vault.root / "Notes/Plan.md").unlink()
    (vault.root / "Inbox").mkdir(exist_ok=True)
    (vault.root / "Inbox/Plan copy.md").write_bytes(data)     # a new file, the same bytes
    report = index.refresh()
    assert doc_id(index, "Inbox/Plan copy.md") == before
    assert report.moved[0]["matched_by"] == "byte hash"


def test_an_ambiguous_move_is_never_guessed(vault, index):
    put(vault, "Notes/Twin.md", "# Plan\n\nShip the adapter first.\n")   # Plan's bytes
    index.refresh()
    old = {doc_id(index, "Notes/Plan.md"), doc_id(index, "Notes/Twin.md")}
    data = (vault.root / "Notes/Plan.md").read_bytes()
    for rel in ("Notes/Plan.md", "Notes/Twin.md"):
        (vault.root / rel).unlink()
    for rel in ("Inbox/A.md", "Inbox/B.md"):
        (vault.root / rel).parent.mkdir(exist_ok=True)
        (vault.root / rel).write_bytes(data)
    report = index.refresh()
    assert report.moved == []
    assert not {doc_id(index, "Inbox/A.md"), doc_id(index, "Inbox/B.md")} & old


def test_a_deleted_document_is_forgotten_and_a_new_one_is_new(vault, index):
    before = doc_id(index, "Notes/Plan.md")
    (vault.root / "Notes/Plan.md").unlink()
    index.refresh()
    put(vault, "Notes/Plan.md", "# Plan\n\nA different plan entirely.\n")
    index.refresh()
    assert doc_id(index, "Notes/Plan.md") not in (None, before)


def test_identity_survives_a_rebuild(vault, index):
    before = doc_id(index, "Notes/Plan.md")
    index.rebuild()
    assert doc_id(index, "Notes/Plan.md") == before


# --- duplicates, explained -----------------------------------------------------------

def layers(index):
    from resource_librarian.document_identity import duplicates
    return {g["layer"]: sorted(d["path"] for d in g["documents"])
            for g in duplicates(index.conn)["groups"]}


def test_exact_and_formatting_only_duplicates_are_explained(vault, index):
    put(vault, "Inbox/Plan (copy).md", "# Plan\n\nShip the adapter first.\n")
    put(vault, "Inbox/Plan crlf.md", "# Plan  \r\n\r\n\r\nShip the  adapter first.\r\n",
        newline="")
    index.refresh()
    found = layers(index)
    assert found["byte hash"] == ["Inbox/Plan (copy).md", "Notes/Plan.md"]
    assert found["normalised text"] == ["Inbox/Plan (copy).md", "Inbox/Plan crlf.md",
                                        "Notes/Plan.md"]


def test_the_same_outside_thing_is_explained_even_when_the_texts_differ(vault, index):
    put(vault, "Sources/page/a.md", "---\ntype: source\ncanonical_url: https://www.Example.org/"
                                    "guide/\n---\n# A\n\nOne summary.\n")
    put(vault, "Sources/page/b.md", "---\ntype: source\ncanonical_url: https://example.org/"
                                    "guide\n---\n# B\n\nAnother summary.\n")
    index.refresh()
    from resource_librarian.document_identity import duplicates
    group = next(g for g in duplicates(index.conn)["groups"]
                 if g["layer"] == "external identity")
    assert group["why"] == "each declares url:example.org/guide; their texts differ"


def test_a_hard_link_is_one_file_under_two_paths(vault, index):
    try:
        os.link(vault.root / "Notes/Plan.md", vault.root / "Notes/Plan link.md")
    except OSError:
        pytest.skip("hard links are not available here")
    index.refresh()
    assert layers(index)["file identity"] == ["Notes/Plan link.md", "Notes/Plan.md"]


def test_the_report_changes_nothing(vault, index):
    put(vault, "Inbox/Plan (copy).md", "# Plan\n\nShip the adapter first.\n")
    index.refresh()
    before = sorted(p.relative_to(vault.root).as_posix() for p in vault.root.rglob("*.md"))
    out = REGISTRY.call("document_duplicates", {}, Context(tier="consult", vault=vault))
    assert "error" not in out and out["groups"], out
    assert "nothing was merged, moved or deleted" in out["note"]
    assert sorted(p.relative_to(vault.root).as_posix()
                  for p in vault.root.rglob("*.md")) == before


# --- the layer keys ------------------------------------------------------------------

def test_normalisation_removes_formatting_only():
    assert normalised_text("﻿A  b\r\n\r\n\tc \n") == normalised_text("A b\nc")
    assert normalised_text("A b") != normalised_text("a b")      # case is content


@pytest.mark.parametrize("fm,expected", [
    ({"repo_key": "Owner/Repo"}, "repository:owner/repo"),
    ({"identifier_kind": "doi", "identifier": "10.1000/XYZ"}, "doi:10.1000/xyz"),
    ({"canonical_url": "https://www.github.com/a/b.git"}, "url:github.com/a/b"),
    ({"title": "no outside identity"}, ""),
])
def test_external_identity(fm, expected):
    assert external_identity(fm) == expected


# --- MF-014: a Source's document text follows its identity ------------------------

MANUAL = "The calibration procedure uses a reference thermistor at 25 degrees. " * 5
ATTACHED = "Sources/document/files/manual.txt"


@pytest.fixture
def attached(vault):
    """A Source note whose attached manual's text is indexed."""
    from resource_librarian.text import sync_documents
    from conftest import add_source
    doc = vault.root / ATTACHED
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text(MANUAL, encoding="utf-8")
    note = add_source(vault.root, "Manual", "A device manual.", kind_folder="document",
                      extra_fm=f"file: {ATTACHED}")
    with Index(vault) as idx:
        idx.refresh()
        assert sync_documents(idx)["indexed"][0]["chunks"] == 1
        yield idx, note


def text_rows(index):
    return [tuple(r) for r in index.conn.execute(
        "SELECT id, path, note, hash FROM chunk WHERE role = 'document' ORDER BY id")]


def found_in_text(index, query="thermistor calibration"):
    from resource_librarian.search import Engine, search
    engine = Engine(index, index.vault.config()["heuristics"])
    return [hit.fields["note"] for hit in search(engine, query, "in_text").results]


def test_a_renamed_source_keeps_its_document_text_ids_and_all(vault, attached):
    from resource_librarian.text import sync_documents
    index, note = attached
    before = text_rows(index)
    fts = [r[0] for r in index.conn.execute(
        "SELECT rowid FROM chunk_fts WHERE chunk_fts MATCH 'thermistor'")]
    os.rename(note, note.with_name("Field Manual.md"))

    report = index.refresh()

    after = text_rows(index)
    assert [(i, h) for i, _, _, h in after] == [(i, h) for i, _, _, h in before]
    assert {(p, n) for _, p, n, _ in after} == {("Sources/document/Field Manual.md",
                                                 "Field Manual")}
    assert report.document_text["carried"][0]["to"] == "Sources/document/Field Manual.md"
    assert [r[0] for r in index.conn.execute(
        "SELECT rowid FROM chunk_fts WHERE chunk_fts MATCH 'thermistor'")] == fts
    assert found_in_text(index) == ["Field Manual"]
    synced = sync_documents(index)
    assert synced["indexed"] == [] and synced["unchanged"] == 1   # not read again


def test_a_moved_note_whose_attachment_changed_does_not_take_the_old_text(vault, attached):
    from resource_librarian.text import sync_documents
    index, note = attached
    os.rename(note, note.with_name("Field Manual.md"))
    (vault.root / ATTACHED).write_text("A different manual about torque wrenches. " * 5,
                                       encoding="utf-8")

    report = index.refresh()

    assert "attachment is not the one" in report.document_text["purged"][0]["reason"]
    assert text_rows(index) == [] and found_in_text(index) == []
    assert sync_documents(index)["indexed"][0]["note"] == "Field Manual"
    assert found_in_text(index, "torque wrenches") == ["Field Manual"]


def test_copies_never_share_the_text_until_exactly_one_remains(vault, attached):
    index, note = attached
    before = text_rows(index)
    data = note.read_bytes()
    for copy in ("Manual A.md", "Manual B.md"):
        (note.parent / copy).write_bytes(data)
    note.unlink()

    report = index.refresh()

    assert "2 notes hold the same attachment" in report.document_text["kept"][0]["reason"]
    assert found_in_text(index) == []                            # kept, but unsearchable
    stats = index.stats()
    assert stats["document_chunks"] == 0 and stats["orphaned_document_chunks"] == len(before)

    (note.parent / "Manual B.md").unlink()
    report = index.refresh()

    assert report.document_text["carried"][0]["to"] == "Sources/document/Manual A.md"
    assert [r[0] for r in text_rows(index)] == [r[0] for r in before]
    assert found_in_text(index) == ["Manual A"]


def test_a_failure_while_settling_rolls_the_whole_move_back(vault, attached, monkeypatch):
    index, note = attached
    before = text_rows(index)
    old_id = doc_id(index, "Sources/document/Manual.md")
    original = Index._carry_document_text

    def fails_half_way(self, orphan, to):
        original(self, orphan, to)
        raise RuntimeError("injected crash")

    monkeypatch.setattr(Index, "_carry_document_text", fails_half_way)
    os.rename(note, note.with_name("Field Manual.md"))
    with pytest.raises(RuntimeError, match="injected"):
        index.refresh()
    assert text_rows(index) == before                            # the chunk move was undone
    assert doc_id(index, "Sources/document/Manual.md") == old_id  # and so was the identity's

    monkeypatch.undo()
    index.refresh()
    assert doc_id(index, "Sources/document/Field Manual.md") == old_id
    assert [r[0] for r in text_rows(index)] == [r[0] for r in before]


def test_text_waits_unsearchable_while_the_tree_is_still_changing(vault, attached,
                                                                  monkeypatch):
    index, note = attached
    note.unlink()
    monkeypatch.setattr(index, "_filesystem_metadata", lambda: {"still": (0, 0, "")})

    report = index.refresh()

    assert report.reason and "still changing" in report.document_text["kept"][0]["reason"]
    assert index.stats()["orphaned_document_chunks"] == 1 and found_in_text(index) == []

    monkeypatch.undo()
    report = index.refresh()
    assert report.document_text["purged"][0]["reason"] == "its note is gone"
    assert index.stats()["orphaned_document_chunks"] == 0


def test_text_indexed_before_mf014_moves_only_while_its_stamp_still_matches(vault, attached):
    index, note = attached
    index.conn.execute("DELETE FROM document_text")              # an index from before MF-014
    index.conn.commit()
    os.rename(note, note.with_name("Field Manual.md"))
    assert index.refresh().document_text["carried"]
    assert found_in_text(index) == ["Field Manual"]

    index.conn.execute("DELETE FROM document_text")
    index.conn.commit()
    os.utime(vault.root / ATTACHED, (1_000_000, 1_000_000))     # touched since it was read
    os.rename(note.with_name("Field Manual.md"), note)
    assert index.refresh().document_text["purged"]
    assert text_rows(index) == []


def test_a_rebuild_leaves_document_text_where_it_is(vault, attached):
    index, note = attached
    put(vault, "Notes/Manual.md", "# Manual\n\nA plain note that shares the name.\n")
    index.refresh()
    before = text_rows(index)

    index.rebuild()

    # Re-attaching by name once handed the text to whichever "Manual" came first.
    assert text_rows(index) == before
    assert {p for _, p, _, _ in before} == {"Sources/document/Manual.md"}


def test_the_rename_tool_keeps_the_text_searchable(vault, attached):
    index, note = attached
    before = [r[0] for r in text_rows(index)]
    ctx = Context(tier="contribute", vault=vault)
    moved = REGISTRY.call("note_move", {"name": "Manual", "new_name": "Field Manual"}, ctx)
    assert "error" not in moved, moved

    out = REGISTRY.call("search", {"query": "thermistor calibration", "intent": "in_text"},
                        Context(tier="consult", vault=vault))
    assert [r["fields"]["note"] for r in out["results"]] == ["Field Manual"]
    # The same chunks, carried: searching syncs documents, and before MF-014 that
    # read the attachment again into new chunks.
    assert [r[0] for r in text_rows(index)] == before
