import io
import json
import urllib.request

import pytest

from resource_librarian import embed
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


def test_reviewed_hosted_embedding_contract_uses_distinct_document_and_query_forms(monkeypatch):
    """EmbeddingGemma's card distinguishes corpus text from a query.

    This is a deterministic transport fixture, not a provider call.  It
    protects the adapter rule that query prefixes never leak into indexed
    passages (and vice versa).
    """
    seen: list[dict] = []

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def urlopen(request, timeout=0):
        payload = json.loads(request.data)
        seen.append(payload)
        vectors = [[0.25] * 768 for _ in payload["input"]]
        return Reply(json.dumps({"data": [
            {"index": i, "embedding": vector} for i, vector in enumerate(vectors)]}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")
    document = embed._api_encoder("deepinfra", "google/embeddinggemma-300m",
                                  representation_kind="document")
    query = embed._api_encoder("deepinfra", "google/embeddinggemma-300m",
                               representation_kind="query")
    assert len(document(["A source passage"])[0]) == 768
    assert len(query(["find a source"])[0]) == 768
    assert [row["input"] for row in seen] == [["title: none | text: A source passage"],
                                                ["task: search result | query: find a source"]]
    assert [row["encoding_format"] for row in seen] == ["float", "float"]


def test_representation_change_requires_a_fresh_embedding_pass(vault):
    """Old raw vectors cannot be treated as prefixed model-card vectors."""
    pytest.importorskip("numpy")
    import numpy as np

    add_source(vault.root, "Alpha", "parses SQL lineage")
    with Index(vault) as ix:
        ix.refresh()

        def encode(texts):
            return np.ones((len(texts), 4), dtype="float32")

        spec = "api:deepinfra:BAAI/bge-m3"
        old = VectorSearch(ix, spec, encode, representation_namespace=f"{spec}#repr-old")
        assert old.sync() > 0 and old.embedded() > 0
        namespace, _ = embed.embedding_namespace(spec, "deepinfra", "BAAI/bge-m3")
        changed = VectorSearch(ix, spec, encode, representation_namespace=namespace)
        assert changed.embedded() == 0
        # The passive service tile uses the same metadata check, rather than
        # loading an encoder merely to count vectors.
        assert not embed.representation_current(ix, spec)
        assert changed.sync() > 0 and changed.embedded() > 0
        assert embed.representation_current(ix, spec)
        marker = ix.conn.execute("SELECT value FROM meta WHERE key = ?",
                                 ("embedding-representation:api:deepinfra:BAAI/bge-m3",)).fetchone()
        assert marker[0] == namespace
