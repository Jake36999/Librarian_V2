import json

import pytest

from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.evidence import EvidenceStore
from resource_librarian.registry import REGISTRY, Context
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


def test_an_id_is_never_a_pattern_or_a_path(vault):
    """MF-012: `*` once matched whichever record a glob found first, so a quote
    check or a contract's read scope could be judged against the wrong one."""
    from resource_librarian import closure, closure_audit
    store = EvidenceStore(vault)
    record = store.put("page", "https://x", {"text": "the cited words"})
    (vault.root / "secret.json").write_text(json.dumps({
        "id": "x", "kind": "page", "source": "s", "fetched_at": "t", "payload": {}}))

    for forged in ("*", record.id[:8] + "*", "../../secret", record.id.upper(), ""):
        assert store.locate(forged) is None and store.get(forged) is None
        assert closure_audit._evidence(vault, forged) is None
        assert closure._evidence_readable(vault, forged, [".evidence/"]) is False
    assert store.get(record.id).payload == {"text": "the cited words"}
    assert closure._evidence_readable(vault, record.id, [".evidence/"]) is True


def test_an_edited_record_is_not_served_as_the_cited_text(vault):
    store = EvidenceStore(vault)
    record = store.put("page", "https://x", {"text": "original words"})
    ctx = Context(tier="consult", vault=vault)
    assert REGISTRY.call("read_evidence", {"evidence_id": record.id},
                         ctx)["fields"]["text"]["text"] == "original words"

    path = vault.evidence / "page" / f"{record.id}.json"
    data = json.loads(path.read_text())
    data["payload"]["text"] = "words put in its mouth"
    path.write_text(json.dumps(data))
    out = REGISTRY.call("read_evidence", {"evidence_id": record.id}, ctx)

    assert out["refused"] == "EVIDENCE_IS_NEVER_EDITED" and out["status"] == "changed"
    assert "put in its mouth" not in json.dumps(out)
