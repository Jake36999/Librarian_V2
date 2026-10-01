"""Search Methods req 7-8, SM-6, SM-9; plan P5.5: evaluation reported per tagged slice,
with its own sample size - including the grains beneath a source (a repository address, a
dataset access point) and exclusions, which the engine does not segment and so are
measured, not corrected."""
import json

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source
from test_search_grains import dataset, library as repositories


def evaluate(vault, questions):
    folder = vault.work("eval")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "questions.json").write_text(json.dumps({"questions": questions}),
                                           encoding="utf-8")
    return REGISTRY.call("evaluate", {}, Context(tier="consult", vault=vault))["questions"]


def test_every_tagged_slice_is_reported_with_its_own_n(vault):
    repositories(vault)
    dataset(vault)
    add_source(vault.root, "Café Tools", "Outils pour le café: une bibliothèque de requêtes.")
    out = evaluate(vault, [
        {"id": "c1", "question": "join order planner", "intent": "donor", "slice": "components",
         "expects_address": "src/planner/join_order.py"},
        {"id": "d1", "question": "row change traces", "intent": "data",
         "slice": ["dataset_access"], "expects_access": "https://zenodo.org/api/records/7"},
        {"id": "n1", "question": "café bibliothèque", "intent": "donor",
         "slice": ["non_english"], "expects": ["Café Tools"]},
        {"id": "x1", "question": "query planner but not copyplan", "intent": "donor",
         "slice": ["exclusions"], "expects": ["joinplan"], "excludes": ["copyplan"]},
    ])
    slices = out["by_slice"]
    assert set(slices) == {"components", "dataset_access", "non_english", "exclusions"}
    assert all(s["n"] == 1 for s in slices.values()) and out["total"] == 4
    assert slices["components"]["hit"] == 1.0                     # scored on the address
    assert slices["dataset_access"]["hit"] == 1.0                 # scored on the access point
    # SM-9: measured as a miss (the ASCII-only tokenizer cut "café" to "caf"), then fixed
    # with a before/after measurement (test_tokenizer.py)
    assert slices["non_english"]["hit"] == 1.0
    # no segmentation: "but not copyplan" is just more terms, and copyplan comes back
    assert slices["exclusions"]["excluded_returned"] == 1
    assert slices["exclusions"]["excluded_of"] == 1


def test_an_address_the_search_does_not_reach_is_a_miss(vault):
    repositories(vault)
    out = evaluate(vault, [{"id": "c2", "question": "cost model", "intent": "donor",
                            "slice": "components", "expects_address": "src/nowhere.py"}])
    assert out["by_slice"]["components"]["hit"] == 0.0 and out["misses"][0]["id"] == "c2"
