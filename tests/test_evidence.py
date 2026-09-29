import json

import pytest

from resource_librarian.evidence import EvidenceStore
from resource_librarian.rules import Refusal


def test_content_addressed_and_idempotent(vault):
    store = EvidenceStore(vault)
    a = store.put("readme", "https://x", {"text": "hi"}, fetched_at="2026-01-01")
    b = store.put("readme", "https://x", {"text": "hi"}, fetched_at="2026-01-01")
    c = store.put("readme", "https://x", {"text": "changed"}, fetched_at="2026-01-01")
    assert a.id == b.id != c.id
    assert len(list(store.iter("readme"))) == 2
    assert store.get(a.id).payload == {"text": "hi"}
    assert store.get("0" * 32) is None


def test_framing_is_refused_at_any_depth(vault):
    store = EvidenceStore(vault)
    with pytest.raises(Refusal) as exc:
        store.put("metadata", "https://x", {"data": [{"Project": "mine"}]})
    assert exc.value.code == "DATA_IS_UNFRAMED" and "data[0].Project" in exc.value.detail


def test_source_required_and_kinds_closed(vault):
    store = EvidenceStore(vault)
    with pytest.raises(Refusal):
        store.put("readme", "  ", {})
    with pytest.raises(ValueError):
        store.put("screen_verdict", "https://x", {})


def test_verify_detects_edits(vault):
    store = EvidenceStore(vault)
    record = store.put("page", "https://x", {"text": "original"})
    assert store.verify() == []
    path = vault.evidence / "page" / f"{record.id}.json"
    data = json.loads(path.read_text())
    data["payload"]["text"] = "edited"
    path.write_text(json.dumps(data))
    assert store.verify() == [record.id]
