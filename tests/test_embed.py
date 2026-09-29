from resource_librarian.embed import VectorSearch
from resource_librarian.index import Index
from resource_librarian.search import Engine, search

from conftest import add_source


def test_cache_is_by_content(vault):
    path = add_source(vault.root, "Alpha", "parses SQL lineage")
    add_source(vault.root, "Beta", "draws pictures")
    with Index(vault) as ix:
        ix.refresh()
        vs = VectorSearch.from_spec(ix, "hash:64")
        first = vs.sync()
        assert first > 0 and vs.sync() == 0
        path.rename(path.with_name("Alpha Renamed.md"))
        ix.refresh()
        assert vs.sync() == 0                    # same text, same vectors
        names, why = vs.search("SQL lineage")
        assert why == "" and names[0] == "Alpha Renamed"


def test_unavailable_is_loud(vault):
    add_source(vault.root, "Alpha", "x")
    with Index(vault) as ix:
        ix.refresh()
        vs = VectorSearch.from_spec(ix, "nonsense:model")
        engine = Engine(ix, vault.config()["heuristics"], vs)
        r = search(engine, "x")
        assert r.partial and "vectors unavailable" in r.notes[0]


def test_vectors_join_the_fusion(vault):
    add_source(vault.root, "Alpha", "lineage of warehouse tables")
    with Index(vault) as ix:
        ix.refresh()
        engine = Engine(ix, vault.config()["heuristics"], VectorSearch.from_spec(ix, "hash:64"))
        r = search(engine, "lineage")
        assert r.results and not r.partial
