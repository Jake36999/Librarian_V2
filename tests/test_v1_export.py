"""Exporting V1's catalogue into a V2 library, staged (owner, 2026-10-01): what V1 ingested
is staged for a person, nothing V1 did not ingest is taken, nothing is lost, V1 is untouched."""
import hashlib
from pathlib import Path

from resource_librarian import notes, staging, v1_export
from resource_librarian.evidence import EvidenceStore
from resource_librarian.index import Index
from resource_librarian.search import Engine

from conftest import add_source

REPO = '''---
uuid: "u-1"
canonical_url: "https://github.com/acme/rowstream"
repo_key: "acme/rowstream"
type: "infrastructure_tool"
primary_topic: "Data"
status: "active"
github_stars: 42
---

# acme - rowstream

## Bottom Line
Streams rows from Postgres.

## What It Solves
Moving rows without a broker.

## Architecture & Mechanics
A logical-replication reader.

## Evidence
- fetched 2026-09-11

## GitHub Snapshot
42 stars.
'''


def v1_tree(root: Path) -> Path:
    def put(rel, text):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    put("01-Resources/acme - rowstream.md", REPO)
    put("01-Resources/acme - draftthing.md", REPO.replace('status: "active"', 'status: "draft"')
        .replace("rowstream", "draftthing"))
    put("01-Resources/Manifest - awesome.md", '---\ntype: "manifest_hub"\n---\n# M\n')
    put("02-Glossary/Glossary - Abstract Syntax Tree.md",
        '---\ntype: "glossary_term"\ncanonical_word: "Abstract Syntax Tree"\naliases: ["AST"]\n'
        'related_terms: ["Parser"]\nstatus: "active"\n---\n# Glossary - Abstract Syntax Tree\n\n'
        '## Definition\nA tree of what a program means.\n\n## Why It Matters\nStatic analysis.\n')
    put("06-Papers/Aalst, 2003 - Workflow Patterns.md",
        '---\ntype: "research_paper"\ntitle: "Workflow Patterns"\ndoi: "10.1/x"\n'
        'canonical_url: "https://doi.org/10.1/x"\nstatus: "published"\n---\n# A\n\n'
        '## Bottom Line\nTwenty patterns.\n')
    put("06-Papers/PDF's/books/Some Book.md", "<!-- extracted -->\nPlain text of a book.\n")
    put("09-Applications/Application - Host Watch.md",
        '---\ntype: "application_record"\nstatus: "active"\n---\n# Application - Host Watch\n\n'
        '## What Was Needed\nHost inventory.\n')
    put("branch offerings/Branch Offerings Index.md", '---\ntype: "branch_offerings_index"\n---\n# I\n')
    put("00-Indexes/All.md", "# all\n")
    return root


def digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            h.update(path.as_posix().encode() + path.read_bytes())
    return h.hexdigest()


def test_only_what_v1_ingested_is_staged_and_v1_is_untouched(vault, tmp_path):
    v1 = v1_tree(tmp_path / "v1")
    before = digest(v1)
    planned = v1_export.plan(v1, vault)
    actions = {r["v1_path"]: (r["action"], r.get("why", "")) for r in planned["rows"]}
    assert actions["01-Resources/acme - rowstream.md"][0] == "stage"
    assert "not ingested" in actions["01-Resources/acme - draftthing.md"][1]
    assert "manifest" in actions["01-Resources/Manifest - awesome.md"][1]
    assert actions["06-Papers/PDF's/books/Some Book.md"][1] == "no type: not catalogued"
    assert actions["00-Indexes/"][0] == "left out"
    out = v1_export.stage(v1, vault)
    assert out["staged"] == 4                               # repo, term, paper, application
    assert v1_export.plan(v1, vault)["counts"].get("already staged") == 4
    assert v1_export.stage(v1, vault)["staged"] == 0         # running again doubles nothing
    assert digest(v1) == before                              # V1 is only read
    drafts = v1_export.plan(v1, vault, with_drafts=True)
    assert any(r["v1_path"].endswith("draftthing.md") and r["action"] == "stage"
               for r in drafts["rows"])


def test_a_note_already_held_is_not_staged_again(vault, tmp_path):
    v1 = v1_tree(tmp_path / "v1")
    add_source(vault.root, "acme - rowstream", "Already here.")
    held = {r["v1_path"]: r["action"] for r in v1_export.plan(v1, vault)["rows"]}
    assert held["01-Resources/acme - rowstream.md"] == "already held"


def test_accepted_notes_keep_everything_v1_had(vault, tmp_path):
    v1 = v1_tree(tmp_path / "v1")
    v1_export.stage(v1, vault)
    store, engine = staging.StagingStore(vault), Engine(Index(vault))
    items = {i["name"]: i for i in store.items()}
    repo = items["acme - rowstream"]
    record = EvidenceStore(vault).get(repo["evidence"][0]["id"])
    assert record.kind == "v1_note" and record.payload["text"] == REPO       # all of it
    done = staging.decide(store, engine, [repo["id"]], "accept", "", "", "",
                          decided_by="person", session="")[0]
    note = notes.load(vault.root / done["promotion"]["path"])
    assert {"Architecture & Mechanics", "GitHub Snapshot", "V1 Evidence"} <= set(note.sections())
    assert note.sections()["V1 Evidence"].strip() == "- fetched 2026-09-11"
    assert note.frontmatter["v1_type"] == "infrastructure_tool"
    assert note.frontmatter["github_stars"] == 42 and note.frontmatter["imported_from"] == "V1"
    term = items["Abstract Syntax Tree"]
    staging.decide(store, engine, [term["id"]], "accept", "", "", "", decided_by="person",
                   session="", fields={"definition": term["imported"]["definition"],
                                       "concept_kind": "term",
                                       "aliases": term["imported"]["aliases"],
                                       "related": term["imported"]["related"]})
    concept = notes.load(vault.root / "Concepts" / "Abstract Syntax Tree.md")
    assert concept.sections()["Definition"].strip() == "A tree of what a program means."
    assert concept.sections()["Why It Matters"].strip() == "Static analysis."
    assert "Glossary - Abstract Syntax Tree" in concept.frontmatter["aliases"]
    application = items["Application - Host Watch"]
    staging.decide(store, engine, [application["id"]], "accept", "", "", "",
                   decided_by="person", session="")
    written = notes.load(vault.root / "Applications" / "Application - Host Watch.md")
    assert written.frontmatter["type"] == "application" and \
        written.frontmatter["v1_type"] == "application_record"
    assert "Host inventory." in written.body
