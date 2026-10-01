"""Search Methods SM-9 (2026-09-30): accented and non-English words.

The query tokenizer was ASCII-only: "café" became "caf" and "Zürich" became "rich", so an
accented query found nothing - and "rich" could match inside a name that merely contains
it. Measured before the change on a 17-question set (French, German, accented English,
code identifiers, plain English): 13 of 17, the four misses all accented queries. After:
17 of 17, with the English and code questions returning exactly what they returned before.
The full-text index already folded accents (unicode61); the Python side now does too."""
import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.index import fold
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.search import terms_from

from conftest import add_source

NOTES = [("Café Tools", "Outils pour le café: une bibliothèque de requêtes."),
         ("Müller Planner", "Ein Planer für Abfragen und Übersetzungen."),
         ("joinlib", "Implements join_order and cost_model in C++ with std::vector."),
         ("Resume Parser", "Parses a résumé (a CV) into structured fields."),
         ("Naive Bayes Kit", "A naïve Bayes classifier for short texts."),
         ("Zürich Transit Data", "Timetables for trams in Zürich."),
         ("osquery", "Exposes the operating system as SQL tables."),
         ("painter", "Draws pictures of cats.")]


def search(vault, query):
    out = REGISTRY.call("search", {"query": query, "intent": "donor", "limit": 5},
                        Context(tier="consult", vault=vault))
    return [r["name"] for r in out["results"]]


@pytest.fixture
def library(vault):
    for name, bottom in NOTES:
        add_source(vault.root, name, bottom)
    return vault


def test_terms_keep_their_letters():
    assert terms_from("café bibliothèque") == ["café", "bibliothèque"]
    assert terms_from("Zürich") == ["Zürich"]
    assert terms_from("join_order std::vector") == ["join_order", "std", "vector"]   # as before
    assert fold("Zürich Übersetzungen naïve") == "zurich ubersetzungen naive"


@pytest.mark.parametrize("query,expect", [
    ("café bibliothèque", "Café Tools"), ("cafe bibliotheque", "Café Tools"),
    ("Übersetzungen", "Müller Planner"), ("muller planner", "Müller Planner"),
    ("naïve", "Naive Bayes Kit"), ("résumé", "Resume Parser"), ("Zürich", "Zürich Transit Data"),
    ("zurich trams", "Zürich Transit Data"), ("join_order cost_model", "joinlib"),
    ("operating system tables", "osquery")])
def test_accented_or_not_the_note_is_found(library, query, expect):
    assert search(library, query)[:1] == [expect]


def test_a_fragment_no_longer_matches_inside_an_accented_name(library):
    assert "Zürich Transit Data" not in search(library, "rich")
