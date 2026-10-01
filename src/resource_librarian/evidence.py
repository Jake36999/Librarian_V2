"""The data layer: what a fetch returned, kept exactly as returned.

Evidence is **content-addressed**: a record's id is the hash of its canonical
content, so the same fetch stored twice is one record, a changed fetch is a new
record, and nothing is ever rewritten (`EVIDENCE_IS_NEVER_EDITED`). A note
cites the ids it rests on; a rename cannot break that link, because the id is
the content.

Evidence is **unframed** (`DATA_IS_UNFRAMED`): a record may not carry a
project, a brief, a session or a need. What was fetched, from where, when, and
nothing about why. The check is structural, in `put`, rather than a convention.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from .rules import Refusal
from .vault import Vault, now_iso

# A screen *verdict* is not here on purpose: "keep, against this need" is a
# judgement framed by the need, so it lives on the Candidate in its session.
# What the screen read (the abstract, the README) is evidence.
KINDS = ("survey", "metadata", "readme", "abstract", "pdf_text", "page",
         "term_usage", "access_point", "external_link", "model_listing",
         "code_structure", "access_check", "execution", "v1_note")

# Keys that would carry framing into the data layer.
FRAMING_KEYS = frozenset({"project", "brief", "brief_id", "session", "session_id",
                          "need", "disqualifiers", "purpose", "why", "topic", "framing"})


@dataclass(frozen=True)
class Record:
    id: str
    kind: str
    source: str
    fetched_at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "source": self.source,
                "fetched_at": self.fetched_at, "payload": self.payload}


def _canonical(kind: str, source: str, fetched_at: str, payload: dict[str, Any]) -> bytes:
    return json.dumps({"kind": kind, "source": source, "fetched_at": fetched_at,
                       "payload": payload}, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _framing_keys(value: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            here = f"{path}.{key}" if path else str(key)
            if str(key).lower() in FRAMING_KEYS:
                found.append(here)
            found += _framing_keys(inner, here)
    elif isinstance(value, list):
        for i, inner in enumerate(value):
            found += _framing_keys(inner, f"{path}[{i}]")
    return found


class EvidenceStore:
    def __init__(self, vault: Vault):
        self.vault = vault

    def _path(self, kind: str, record_id: str) -> Path:
        return self.vault.evidence / kind / f"{record_id}.json"

    def put(self, kind: str, source: str, payload: dict[str, Any],
            fetched_at: str | None = None) -> Record:
        if kind not in KINDS:
            raise ValueError(f"evidence kind {kind!r} is not one of {KINDS}")
        if not str(source).strip():
            raise Refusal("EVIDENCE_REQUIRED", "evidence must name where it came from")
        framed = _framing_keys(payload)
        if framed:
            raise Refusal("DATA_IS_UNFRAMED",
                          f"evidence may not carry framing; remove {framed[:5]}. What was "
                          f"fetched belongs here; why it was fetched belongs in the session.")
        fetched_at = fetched_at or now_iso()
        record_id = hashlib.sha256(_canonical(kind, source, fetched_at, payload)).hexdigest()[:32]
        path = self._path(kind, record_id)
        record = Record(record_id, kind, source, fetched_at, payload)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            tmp.replace(path)
        return record

    def get(self, record_id: str) -> Record | None:
        for path in self.vault.evidence.glob(f"*/{record_id}.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            return Record(data["id"], data["kind"], data["source"], data["fetched_at"],
                          data["payload"])
        return None

    def iter(self, kind: str | None = None) -> Iterator[Record]:
        pattern = f"{kind}/*.json" if kind else "*/*.json"
        for path in sorted(self.vault.evidence.glob(pattern)):
            data = json.loads(path.read_text(encoding="utf-8"))
            yield Record(data["id"], data["kind"], data["source"], data["fetched_at"],
                         data["payload"])

    def verify(self) -> list[str]:
        """Records whose content no longer matches their id: evidence that was
        edited after it was stored. Empty is the only acceptable answer."""
        bad = []
        for record in self.iter():
            expected = hashlib.sha256(_canonical(record.kind, record.source,
                                                 record.fetched_at, record.payload)).hexdigest()[:32]
            if expected != record.id:
                bad.append(record.id)
        return bad
