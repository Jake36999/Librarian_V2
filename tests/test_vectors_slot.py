"""Requirements Addendum R17 slot 6 and Search Methods SM-8 / req 10; plan P5.4.

The embedding model is the library's choice; a hosted one embeds nothing until a person
starts it; vectors join only the intents a person turned on after measuring; an answer
says whether vectors really contributed ("hybrid") or not ("lexical")."""
import io
import json
import urllib.request
import zlib

import pytest

from resource_librarian import embed, tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source
from test_app import served  # noqa: F401  (fixture)

pytest.importorskip("numpy")


def call(vault, tool_name, /, tier="contribute", **args):
    return REGISTRY.call(tool_name, args, Context(tier=tier, vault=vault))


def library(vault):
    add_source(vault.root, "osquery", "Exposes the operating system as SQL tables.")
    add_source(vault.root, "painter", "Draws pictures of cats.")
    return vault


def test_the_slot_choice_wins_over_the_older_setting(vault):
    vault.set_setting("search", "vectors", "hash:32")
    assert embed.spec_for(vault) == "hash:32"
    vault.set_setting("services", "embeddings", "hash:64")
    assert embed.spec_for(vault) == "hash:64"
    vault.set_setting("services", "embeddings", "deepinfra:BAAI/bge-m3")
    assert embed.spec_for(vault) == "api:deepinfra:BAAI/bge-m3"


def test_vectors_join_only_the_intents_turned_on(vault):
    library(vault)
    vault.set_setting("services", "embeddings", "hash:64")
    vault.set_setting("search", "vector_intents", ["orient"])
    assert call(vault, "search", query="operating system", intent="donor")["ranking"] == "lexical"
    assert call(vault, "search", query="operating system",
                intent="orient")["ranking"] == "hybrid (hash:64)"


def fake_embeddings(monkeypatch, calls):
    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(request, timeout=0):
        texts = json.loads(request.data)["input"]
        calls.append(len(texts))
        vectors = [[float((zlib.crc32(f"{w}{i}".encode()) % 7) - 3) for i in range(8)]
                   for w in texts]
        return Reply(json.dumps({"data": [{"index": i, "embedding": v}
                                          for i, v in enumerate(vectors)]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setenv("DEEPINFRA_API_KEY", "test-key")


def test_a_hosted_model_embeds_nothing_until_a_person_starts_it(vault, monkeypatch):
    library(vault)
    calls: list[int] = []
    fake_embeddings(monkeypatch, calls)
    vault.set_setting("services", "embeddings", "deepinfra:BAAI/bge-m3")
    vault.set_setting("search", "vector_intents", ["orient"])
    before = call(vault, "search", query="operating system", intent="orient")
    assert before["ranking"] == "lexical" and calls == []           # not a single token spent
    assert any("not embedded yet" in n for n in before["notes"])
    assert call(vault, "embed_index")["refused"] == "TIER_REFUSED"  # a person's action
    done = call(vault, "embed_index", tier="curate")
    assert done["embedded"] > 0 and calls
    after = call(vault, "search", query="operating system", intent="orient")
    assert after["ranking"] == "hybrid (api:deepinfra:BAAI/bge-m3)"


def test_the_estimate_counts_what_is_not_yet_embedded(vault):
    library(vault)
    vault.set_setting("services", "embeddings", "hash:64")
    from resource_librarian.tools.library import engine_for
    engine = engine_for(Context(tier="curate", vault=vault))
    first = embed.estimate(engine.index, "hash:64", price_per_1m=0.01)
    assert first["chunks"] > 0 and first["tokens_est"] > 0 and "cost_est_usd" in first
    engine.vectors.sync()
    assert embed.estimate(engine.index, "hash:64")["chunks"] == 0


def test_evaluate_compares_lexical_and_hybrid_per_intent(vault):
    library(vault)
    vault.set_setting("services", "embeddings", "hash:64")
    folder = vault.work("eval")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "questions.json").write_text(json.dumps({"questions": [
        {"id": "q1", "question": "operating system tables", "intent": "donor",
         "expects": ["osquery"]},
        {"id": "q2", "question": "cat pictures", "intent": "orient", "expects": ["painter"]}]}),
        encoding="utf-8")
    out = call(vault, "evaluate", compare_vectors=True)
    assert set(out["by_intent"]) == {"donor", "orient"}
    row = out["by_intent"]["donor"]
    assert row["n"] == 1 and {"lexical_hit", "hybrid_hit", "delta_hit"} <= set(row)
    assert row["lexical_mrr"] == 1.0                        # osquery first: MRR is read
    assert out["vectors_contributed"] == 2
    assert json.loads((folder / "vectors.json").read_text(encoding="utf-8"))["model"] == "hash:64"
    assert call(vault, "search", query="operating system",
                intent="donor")["ranking"] == "lexical"            # measuring turned nothing on


def test_the_slot_in_the_app(served):
    app, client, _ = served
    out = client.post("/api/services", {"slot": "embeddings", "provider": "hash", "model": "64"})[1]
    slot = next(s for s in out["slots"] if s["slot"] == "embeddings")
    assert slot["spec"] == "hash:64" and slot["embedded"] == 0 and slot["chunks"] > 0
    assert slot["vector_intents"] == []
    assert client.post("/api/services/vector_intents", {"intents": ["orient", "nope"]})[0] == 400
    client.post("/api/services/vector_intents", {"intents": ["orient"]})
    assert app.vault.setting("search", "vector_intents") == ["orient"]
    tested = client.post("/api/services/test", {"slot": "embeddings"})[1]
    assert tested["ok"] and tested["dimension"] == 64


def test_two_ranking_configurations_on_the_same_questions(vault):
    library(vault)
    folder = vault.work("eval")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "questions.json").write_text(json.dumps({"questions": [
        {"id": "q1", "question": "operating system tables", "intent": "donor",
         "expects": ["osquery"]}]}), encoding="utf-8")
    out = call(vault, "evaluate", tier="consult", candidate={"name_weight": 0.5})
    row = out["by_intent"]["donor"]
    assert {"current_hit", "candidate_hit", "delta_mrr"} <= set(row) and row["n"] == 1
    assert "not adopted" in out["note"]
    assert call(vault, "evaluate", tier="consult", candidate={"nope": 1})["error"] == \
        "invalid_arguments"
