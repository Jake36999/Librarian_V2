"""Roadmap §4 B3 (2026-09-28): how many accepted lenses each source gave, and a
doctor line when one source gives more than half of them."""
from resource_librarian import doctor, tools  # noqa: F401  (registers tools)
from resource_librarian.lenses import LensStore
from resource_librarian.registry import REGISTRY, Context


def add(store, n, source, origin=""):
    for i in range(n):
        store.accept({"name": f"{source} stance {i}", "source": source,
                      "source_quote": "a quoted passage"}, "person", origin=origin)


def line(vault):
    return next((c for c in doctor.checks(vault) if c.name == "lens concentration"), None)


def test_no_line_without_lenses_and_too_few_to_judge(vault):
    assert line(vault) is None
    add(LensStore(vault), 3, "Clean Architecture")
    check = line(vault)
    assert check.ok and "too few to judge" in check.detail


def test_one_source_giving_most_lenses_is_flagged(vault):
    store = LensStore(vault)
    add(store, 5, "Clean Architecture")
    add(store, 2, "Systems Analysis")
    add(store, 9, "Pack Source", origin="pack:source-assessment")    # chosen as a set
    spread = store.concentration()
    assert spread["drawn"] == 7 and spread["from_packs"] == 9 and spread["sources"] == 2
    assert spread["by_source"][0] == {"source": "Clean Architecture", "lenses": 5}
    assert spread["concentrated"] and spread["top_share"] == 0.71
    check = line(vault)
    assert not check.ok and "Clean Architecture (5, 71%)" in check.detail
    listed = REGISTRY.call("lens_list", {}, Context(tier="consult", vault=vault))
    assert listed["concentration"]["concentrated"]


def test_an_even_spread_is_fine(vault):
    store = LensStore(vault)
    for source in ("A", "B", "C"):
        add(store, 2, source)
    assert not store.concentration()["concentrated"] and line(vault).ok
