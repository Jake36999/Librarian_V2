"""Domain packs (Co-work Roadmap §2, F): opt-in Content Model extensions per
discipline. Nothing here is new code - the schema is already entirely
data-driven (`schema.py` parses kinds/fields/sections straight out of a
vault's own `About/Note Content Model.md`, and `promote.py` only ever checks
a kind against that parsed table, never a fixed Python list). This proves it:
a vault opts a domain pack in by editing its own Content Model, same as the
starter `About/Domain Packs.md` walks a person through, and the very next
promotion accepts the new kind and carries its extra fields straight into
frontmatter."""
from resource_librarian.index import Index
from resource_librarian.promote import Draft, promote
from resource_librarian.search import Engine
from resource_librarian import notes


def _add_history_kind(vault):
    path = vault.root / "About" / "Note Content Model.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "| model | Sources/model | a hosted or local inference model |\n",
        "| model | Sources/model | a hosted or local inference model |\n"
        "| history | Sources/history | a primary or secondary historical source |\n")
    text += (
        "\n## Frontmatter — source/history\n\n"
        "| Field | Requirement |\n| --- | --- |\n"
        "| provenance | required |\n| perspective | optional |\n")
    path.write_text(text, encoding="utf-8")


def test_a_new_kind_added_to_the_content_model_promotes_with_no_code_change(vault):
    _add_history_kind(vault)
    with Index(vault) as index:
        index.refresh()
        assert "history" in index.model.kinds
        engine = Engine(index, vault.config()["heuristics"])
        report = promote(vault, engine, Draft(
            name="Treaty of Westphalia", kind="history", title="Treaty of Westphalia",
            canonical_url="u", bottom_line="Ended the Thirty Years' War.",
            what_it_solves="Establishes state sovereignty as a norm.",
            fields={"provenance": "primary: the 1648 treaty text",
                   "perspective": "European state formation"}))
    path = vault.root / report.path
    assert path.parent.name == "history"
    fm = notes.load(path).frontmatter
    assert fm["provenance"] == "primary: the 1648 treaty text"
    assert fm["perspective"] == "European state formation"


def test_a_kind_not_in_the_content_model_is_still_refused(vault):
    with Index(vault) as index:
        index.refresh()
        engine = Engine(index, vault.config()["heuristics"])
        try:
            promote(vault, engine, Draft(
                name="x", kind="not-a-real-kind", title="x", canonical_url="u",
                bottom_line="x", what_it_solves="x"))
            assert False, "expected a TypeError"
        except TypeError as exc:
            assert "not-a-real-kind" in str(exc)
