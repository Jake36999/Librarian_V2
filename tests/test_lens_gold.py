"""A2A-5: the lens gold set a person labels - per-chunk labels that cannot silently drift,
the old phrase rule as a fallback, and proposals from lenses a person already accepted."""
import pytest

from resource_librarian import deep_read, lens_gold
from resource_librarian.lenses import LensStore

from conftest import add_source

STANCE = "Name the failure before the fix: say which structure broke first, then repair it."


def book(n: int = 4) -> str:
    paras = []
    for i in range(n):
        body = STANCE if i == 2 else f"Chapter {i} describes the parts of the machine. " * 40
        paras.append(f"Section {i}.\n\n{body}\n\n" + "Filler sentence about bolts. " * 180)
    return "\n\n".join(paras)


@pytest.fixture
def gold(tmp_path):
    (tmp_path / "book.md").write_text(book(), encoding="utf-8")
    data = lens_gold.load(tmp_path / "gold.json")
    lens_gold.add_source(data, "repairs", "Failure before fix", "find what broke first",
                         file="book.md")
    return tmp_path, data


def test_labels_are_per_chunk_and_a_changed_text_makes_them_stale(gold):
    root, data = gold
    entry = data["sources"]["repairs"]
    cl = lens_gold.chunks(entry, root)
    at = next(c.index for c in cl if STANCE in c.text)
    lens_gold.mark(data, "repairs", at, "gold", cl)
    lens_gold.mark(data, "repairs", 0, "none", cl)
    lens_gold.save(root / "gold.json", data)
    data = lens_gold.load(root / "gold.json")
    entry = data["sources"]["repairs"]
    assert lens_gold.judged(entry, cl) == {at: True, 0: False}
    assert lens_gold.rule_of(entry) == "labels"
    # the text changes under the labelled chunk: its label is stale, never moved
    (root / "book.md").write_text(book().replace("Name the failure", "Name the fault"),
                                  encoding="utf-8")
    row = lens_gold.status(data, root)[0]
    assert row["stale"] == [at] and row["gold"] == 0 and row["none"] == 1
    lens_gold.mark(data, "repairs", 0, "skip", cl)
    assert "0" not in data["sources"]["repairs"]["labels"]


def test_a_source_with_no_labels_falls_back_to_its_phrase_rule(gold):
    root, data = gold
    lens_gold.add_source(data, "repairs", "Failure before fix", "find what broke first",
                         file="book.md", phrases=r"structure broke first")
    entry = data["sources"]["repairs"]
    cl = lens_gold.chunks(entry, root)
    judged = lens_gold.judged(entry, cl)
    assert len(judged) == len(cl) and sum(judged.values()) == 1
    assert lens_gold.rule_of(entry) == "phrases"


@pytest.mark.parametrize("bad", [dict(key="Bad Key", file="book.md"),
                                 dict(key="ok"),
                                 dict(key="ok", file="book.md", vault="v", note="n")])
def test_a_source_needs_a_plain_key_and_exactly_one_text(gold, bad):
    _, data = gold
    key = bad.pop("key")
    with pytest.raises(ValueError):
        lens_gold.add_source(data, key, "n", "e", **bad)


def test_accepted_lenses_are_proposed_and_adopted_as_unconfirmed_gold(vault, gold):
    _, data = gold
    files = vault.root / "Sources" / "document" / "files"
    files.mkdir(parents=True)
    (files / "Repair Manual.md").write_text(book(), encoding="utf-8")
    add_source(vault.root, "Repair Manual", "A manual.", kind_folder="document",
               extra_fm="file: Sources/document/files/Repair Manual.md")
    store = LensStore(vault)
    store.accept({"name": "Failure before fix", "source": "Repair Manual",
                  "source_quote": "say which structure broke first",
                  "perspective": "find what broke first"}, accepted_by="person")
    store.accept({"name": "Checklist habit", "source": "Repair Manual"}, accepted_by="person",
                 origin="pack:habits")
    store.accept({"name": "Unfound", "source": "Repair Manual",
                  "source_quote": "a sentence the manual never says"}, accepted_by="person")
    proposals = {p["name"]: p for p in lens_gold.propose(vault, data)}
    assert "Checklist habit" not in proposals                     # a pack lens has no passage
    assert "not in the source" in proposals["Unfound"]["problem"]
    found = proposals["Failure before fix"]
    cl = deep_read.chunk(deep_read.source_units(vault, {"file": "Sources/document/files/Repair Manual.md"}))
    assert found["chunks"] == [c.index for c in cl if STANCE in c.text]
    entry = lens_gold.adopt(data, found, vault, "failure-before-fix")
    assert {lab["by"] for lab in entry["labels"].values()} == {"accepted-lens"}
    row = next(r for r in lens_gold.status(data, vault.root) if r["key"] == "failure-before-fix")
    assert row["gold"] == 1 and row["proposed"] == 1
    assert "Failure before fix" not in {p["name"] for p in lens_gold.propose(vault, data)}
