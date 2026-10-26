"""Reviewed authoring for strict declarative model-expectation records.

Card-derived claims wait in the ordinary staging airlock. Only a person can
activate one, and activation writes a non-secret personal pack after the
complete candidate pack validates. Raw source prose and executable/template
fields never enter either the proposal or the active pack.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .coordination import atomic_write_text
from .evidence import EvidenceStore
from .keys import config_dir
from .model_invocation import (EXPECTATION_PACK_SCHEMA_VERSION, ExpectationPackError,
                               ExpectationRegistry, _check_record_fields, digest)
from .staging import StagingStore
from .vault import now_iso


PACK_ID = "librarian-personal-model-expectations"
PACK_FILE = "model-expectations.json"


def pack_path(path: Path | None = None) -> Path:
    return path or config_dir() / PACK_FILE


def _empty_pack() -> dict[str, Any]:
    return {"schema_version": EXPECTATION_PACK_SCHEMA_VERSION,
            "pack_id": PACK_ID, "records": []}


def _personal_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return _empty_pack()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExpectationPackError(
            f"personal expectation pack is unreadable: {type(exc).__name__}") from exc
    registry = ExpectationRegistry.from_payload(payload)
    if registry.pack_id != PACK_ID:
        raise ExpectationPackError(f"personal expectation pack id is {PACK_ID!r}")
    if any(record.status != "reviewed" for record in registry.records):
        raise ExpectationPackError("personal expectation pack contains a non-reviewed record")
    return payload


def _route_key(record: Any) -> tuple[str, int, str, str, str, str]:
    return (record.adapter_id, record.adapter_abi, record.protocol, record.model_id.casefold(),
            record.host_id_or_family.casefold(), record.endpoint_fingerprint)


def _source(store: StagingStore, source_item_id: str) -> tuple[dict[str, Any], str]:
    item = store.load(source_item_id)
    if item.get("kind") != "source" or item.get("source_kind") != "model":
        raise TypeError("an expectation proposal needs a staged source/model card")
    evidence_ids = [str(row.get("id") or "") for row in item.get("evidence") or []
                    if isinstance(row, Mapping) and row.get("id")]
    if not evidence_ids:
        raise TypeError("the source/model card needs content-addressed evidence")
    evidence_id = evidence_ids[0]
    evidence = EvidenceStore(store.vault).get(evidence_id)
    if evidence is None:
        raise TypeError("the source/model card evidence is missing")
    canonical_url = str(item.get("canonical_url") or "").strip()
    if not canonical_url or evidence.source != canonical_url:
        raise TypeError("the model-card URL does not match its evidence source")
    return item, evidence_id


def propose(store: StagingStore, source_item_id: str,
            proposed: Mapping[str, Any]) -> dict[str, Any]:
    """Create a reviewable draft from one evidenced staged model source."""
    if not isinstance(proposed, Mapping):
        raise TypeError("proposed expectation record is an object")
    source, evidence_id = _source(store, source_item_id)
    row = copy.deepcopy(dict(proposed))
    _check_record_fields(row)
    if not str(row.get("id") or "").strip():
        raise TypeError("a proposed expectation needs an explicit id")
    # Status and provenance are controlled by the airlock, not the proposer.
    if row.get("status") not in (None, "draft"):
        raise TypeError("a proposed expectation enters staging as draft")
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    source_revision = str(row.get("source_revision") or
                          provenance.get("source_revision") or "").strip()
    if not source_revision:
        raise TypeError("a proposed expectation must pin source_revision")
    canonical_url = str(source.get("canonical_url") or "").strip()
    supplied_url = str(row.get("source_url") or provenance.get("source_url") or "").strip()
    if supplied_url and supplied_url != canonical_url:
        raise TypeError("expectation provenance must use the staged model-card URL")
    for controlled in ("source_url", "source_revision", "source_kind", "source_evidence_id"):
        row.pop(controlled, None)
    row.pop("provenance", None)
    row["status"] = "draft"
    row["provenance"] = {"source_url": canonical_url, "source_revision": source_revision,
                         "source_kind": "model_card", "source_evidence_id": evidence_id}
    # Validate the exact strict schema before creating any staging state.
    checked = ExpectationRegistry.from_payload({"schema_version": EXPECTATION_PACK_SCHEMA_VERSION,
                                                "pack_id": "proposal-check", "records": [row]})
    record = checked.records[0]
    row["id"] = record.id
    if record.model_id == "*" or record.host_id_or_family == "*":
        raise TypeError("a card-derived expectation must name an exact model and host family")
    if record.dialect:
        raise TypeError("a card alone cannot enable a non-default runtime dialect; "
                        "add qualification evidence first")
    item_id = f"expectation-{row['id']}-{digest(row, 10)}"
    try:
        existing = store.load(item_id)
    except TypeError:
        existing = None
    if existing is not None:
        return {"item": item_id, "status": existing["status"], "record_id": row["id"],
                "source_item_id": source_item_id, "source_evidence_id": evidence_id}
    item = store.add({"id": item_id, "kind": "model_expectation",
                      "name": str(row["id"]), "source_item_id": source_item_id,
                      "source_evidence_id": evidence_id, "record": row})
    return {"item": item_id, "status": item["status"], "record_id": row["id"],
            "source_item_id": source_item_id, "source_evidence_id": evidence_id}


def review(store: StagingStore, item_id: str) -> dict[str, Any]:
    item = store.load(item_id)
    if item.get("kind") != "model_expectation":
        raise TypeError(f"{item_id} is not a model expectation proposal")
    row = copy.deepcopy(item.get("record"))
    if not isinstance(row, dict):
        raise TypeError("the staged expectation record is malformed")
    _source_item, current_evidence_id = _source(
        store, str(item.get("source_item_id") or ""))
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    if current_evidence_id != item.get("source_evidence_id") or \
            current_evidence_id != provenance.get("source_evidence_id"):
        raise TypeError("the staged expectation provenance changed; propose and review it again")
    ExpectationRegistry.from_payload({"schema_version": EXPECTATION_PACK_SCHEMA_VERSION,
                                      "pack_id": "proposal-review", "records": [row]})
    return {"id": item_id, "kind": item["kind"], "status": item["status"],
            "record": row, "source_item_id": item.get("source_item_id", ""),
            "source_evidence_id": item.get("source_evidence_id", ""),
            "notice": "Card claims are declarations only; qualification remains separate."}


def decide(store: StagingStore, item_id: str, decision: str, reason: str = "", *,
           decided_by: str, path: Path | None = None) -> dict[str, Any]:
    if decided_by != "person":
        raise TypeError("only a person can accept or reject an expectation proposal")
    if decision not in {"accept", "reject"}:
        raise TypeError("decision is accept or reject")
    if decision == "reject" and not reason.strip():
        raise TypeError("a rejection needs its reason")
    item = store.load(item_id)
    if item.get("kind") != "model_expectation" or item.get("status") != "staged":
        raise TypeError("the model expectation is not awaiting review")
    if decision == "reject":
        item["status"] = "rejected"
        item["history"].append({"decision": "reject", "by": "person",
                                "at": now_iso(), "reason": reason})
        store.quarantine(item, reason)
        return {"id": item_id, "status": "rejected", "quarantined": True}

    row = copy.deepcopy(item.get("record"))
    if not isinstance(row, dict):
        raise TypeError("the staged expectation record is malformed")
    _source_item, current_evidence_id = _source(
        store, str(item.get("source_item_id") or ""))
    provenance = row.get("provenance") if isinstance(row.get("provenance"), Mapping) else {}
    if current_evidence_id != item.get("source_evidence_id") or \
            current_evidence_id != provenance.get("source_evidence_id"):
        raise TypeError("the staged expectation provenance changed; propose and review it again")
    row["status"] = "reviewed"
    target = pack_path(path)
    payload = _personal_payload(target)
    records = [record for record in payload["records"] if record.get("id") != row.get("id")]
    records.append(row)
    candidate = {**payload, "records": records}
    personal = ExpectationRegistry.from_payload(candidate)
    baseline = ExpectationRegistry.bundled()
    baseline_ids = {record.id for record in baseline.records}
    if row.get("id") in baseline_ids:
        raise ExpectationPackError("a personal expectation may not replace a bundled record")
    accepted = next(record for record in personal.records if record.id == row["id"])
    exact_collisions = [record.id for record in (*baseline.records, *personal.records)
                        if record.id != accepted.id and record.model_id != "*" and
                        record.status != "deprecated" and _route_key(record) == _route_key(accepted)]
    if exact_collisions:
        raise ExpectationPackError(
            "an exact route already has expectation record " + ", ".join(exact_collisions))
    if any(record.status != "reviewed" for record in personal.records):
        raise ExpectationPackError("only reviewed records may enter the active pack")
    # Leave a durable recovery marker before the cross-scope config write.
    # A failed activation therefore remains visibly staged and retryable; a
    # failure saving the final state can be reconciled from the pack hash.
    item["acceptance_progress"] = {
        "version": 1, "record_id": row["id"],
        "record_fingerprint": accepted.fingerprint,
        "candidate_pack_fingerprint": personal.pack_fingerprint,
        "started_at": now_iso(),
    }
    store.save(item)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, json.dumps(candidate, indent=2, ensure_ascii=False) + "\n")
    item["status"] = "accepted"
    item["accepted_to"] = f"personal:{PACK_FILE}#{row['id']}"
    item["acceptance_progress"]["completed_at"] = now_iso()
    item["history"].append({"decision": "accept", "by": "person", "at": now_iso(),
                            "pack_fingerprint": personal.pack_fingerprint})
    store.save(item)
    return {"id": item_id, "status": "accepted", "record_id": row["id"],
            "pack_id": personal.pack_id, "pack_fingerprint": personal.pack_fingerprint}
