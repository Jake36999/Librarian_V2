"""Standard model catalogues: the bundled data loads, and adopting it writes
accepted sources once, never twice (model_catalog.py)."""
from __future__ import annotations

from resource_librarian import model_catalog
from resource_librarian.index import Index
from resource_librarian.search import Engine


def test_the_bundled_deepinfra_catalog_loads():
    assert "deepinfra" in model_catalog.providers()
    entries = model_catalog.catalogue("deepinfra")
    assert len(entries) > 50
    one = entries[0]
    assert one.canonical_url.startswith("https://deepinfra.com/")
    assert one.fields["provider"] == "deepinfra"
    assert one.bottom_line and one.evidence["payload"]["text"]


FAKE = [
    model_catalog.CatalogEntry(
        name="widget-a - testprovider", title="test/widget-a",
        canonical_url="https://example.test/test/widget-a",
        fields={"provider": "testprovider", "model_id": "test/widget-a",
               "modality": "Text_Generation", "license_class": "Permissive",
               "context_length": 8192, "price_input_per_1m": 0.1,
               "price_output_per_1m": 0.2, "tool_calling": True, "reasoning": False,
               "best_for": ["Small_Coding_Tasks"], "suggested_tier": "Tier_2"},
        bottom_line="Widget A is a small test model.",
        what_it_solves="It solves testing this module without real network calls.",
        sections={"Specs": "- **Provider**: testprovider (`test/widget-a`)"},
        evidence={"id": "", "kind": "model_listing", "source": "https://example.test/test/widget-a",
                 "fetched_at": "2026-09-28T00:00:00+00:00",
                 "payload": {"provider": "testprovider", "model_id": "test/widget-a",
                            "text": "Widget A: a small model for testing."}},
        captured_at="2026-09-28"),
    model_catalog.CatalogEntry(
        name="widget-b - testprovider", title="test/widget-b",
        canonical_url="https://example.test/test/widget-b",
        fields={"provider": "testprovider", "model_id": "test/widget-b",
               "modality": "Text_Generation", "license_class": "Permissive",
               "context_length": 4096, "price_input_per_1m": 0.05,
               "price_output_per_1m": 0.1, "tool_calling": False, "reasoning": False,
               "best_for": ["Small_Coding_Tasks"], "suggested_tier": "Tier_3"},
        bottom_line="Widget B is another small test model.",
        what_it_solves="It solves testing adopt() over more than one entry.",
        sections={"Specs": "- **Provider**: testprovider (`test/widget-b`)"},
        evidence={"id": "", "kind": "model_listing", "source": "https://example.test/test/widget-b",
                 "fetched_at": "2026-09-28T00:00:00+00:00",
                 "payload": {"provider": "testprovider", "model_id": "test/widget-b",
                            "text": "Widget B: another small model for testing."}},
        captured_at="2026-09-28"),
]


def test_adopt_writes_accepted_sources_once_not_twice(vault, monkeypatch):
    monkeypatch.setattr(model_catalog, "providers", lambda: ["testprovider"])
    monkeypatch.setattr(model_catalog, "catalogue", lambda provider: FAKE)
    engine = Engine(Index(vault))

    first = model_catalog.adopt(vault, engine, "testprovider")
    assert first == {"provider": "testprovider", "written": 2, "already_held": 0, "failed": []}
    assert (vault.root / "Sources" / "model" / "widget-a - testprovider.md").is_file()
    note = (vault.root / "Sources" / "model" / "widget-a - testprovider.md").read_text()
    assert "Widget A is a small test model." in note
    assert "attested_by: person" in note

    before = model_catalog.status(vault, engine)
    assert before == [{"provider": "testprovider", "models": 2, "held": 2}]

    again = model_catalog.adopt(vault, engine, "testprovider")
    assert again == {"provider": "testprovider", "written": 0, "already_held": 2, "failed": []}
