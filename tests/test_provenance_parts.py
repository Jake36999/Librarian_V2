"""A folder brief's per-type file counts are parts, not the folder's total (2026-11-17).

The Clerk wrote "The folder 'specs' contains 7 files ..., consisting of 5 files with a '.json'
extension and 2 files with no extension" - all true - and provenance called both parts a
contradiction of the 7-file total, so the folder check failed on every attempt. The same held
Parallax's 55 folder checks.
"""
from resource_librarian import provenance
from resource_librarian.evidence import EvidenceStore


def _survey(vault, entries):
    record = EvidenceStore(vault).put("survey", "folder:test", {
        "scope": "folder_inventory_metadata", "entries": entries,
        "files": sum(1 for e in entries if not e[0].endswith("/")), "bytes": 0},
        authorship="generated")
    return {"evidence": [record.id]}


ENTRIES = [["specs/", 0, 0], ["specs/a.json", 1, 0], ["specs/b.json", 1, 0], ["specs/c.json", 1, 0],
           ["specs/d.json", 1, 0], ["specs/e.json", 1, 0], ["specs/.gitkeep", 0, 0], ["specs/README", 1, 0]]


def outcomes(vault, text):
    return [(r["stated"], r["outcome"]) for r in
            provenance.check_sections(vault, {"Description": text}, _survey(vault, ENTRIES))]


def test_per_type_counts_are_parts_and_match_the_inventory(vault):
    text = ("The folder 'specs' contains 7 files totaling 9860 bytes, consisting of 5 files with a "
            "'.json' extension and 2 files with no extension.")
    assert outcomes(vault, text) == [(7, "supported"), (5, "supported"), (2, "supported")]


def test_a_wrong_total_is_still_a_contradiction_and_an_unknown_part_is_only_unsupported(vault):
    assert outcomes(vault, "The folder holds 9 files.") == [(9, "contradicted")]
    assert outcomes(vault, "It has 4 files with a '.py' extension.") == [(4, "unsupported")]
