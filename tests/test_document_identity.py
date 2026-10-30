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
