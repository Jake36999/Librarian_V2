"""Standard model catalogues: a provider's models, already profiled once, that
any vault can adopt without paying to profile them again.

Profiling a model (`ingest("model:<provider>:<id>")`) fetches its public
listing page and asks a clerk to describe it - real, if small, cost, repeated
for every vault that wants the same provider's models. A catalogue is that
work done once and shipped with the package (`standard/model_catalog/`, one
JSON array per provider), the same relationship a lens pack has to the
lenses it ships (`lens_packs.py`): nothing reaches a vault until a person
adopts it, adopting again after the bundle changes replaces rather than
duplicates, and each entry still carries the evidence it was drafted from -
adopting is accepting a bundle of already-reviewed sources, not asserting new
facts.

A `model` source is machine-drafted (`describe()`'s `model_specs` task) and
staged for review like any other on first ingest; a catalogue entry has
already been through that once, so adopting it writes the Source note
directly, the same way accepting a lens pack writes lenses directly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

from .evidence import EvidenceStore
from .promote import Draft, promote
from .search import Engine
from .vault import Vault, now_iso

KIND = "model"


@dataclass
class CatalogEntry:
    name: str
    title: str
    canonical_url: str
    fields: dict[str, Any]
    bottom_line: str
    what_it_solves: str
    sections: dict[str, str]
    evidence: dict[str, Any]
    captured_at: str = ""


def _load(node: Any) -> list[CatalogEntry]:
    data = json.loads(node.read_text(encoding="utf-8"))
    return [CatalogEntry(e["name"], e["title"], e["canonical_url"], e["fields"],
                         e["bottom_line"], e["what_it_solves"], e["sections"],
                         e["evidence"], e.get("captured_at", "")) for e in data]


def providers() -> list[str]:
    """Every provider a standard catalogue ships for."""
    node = resources.files("resource_librarian") / "standard" / "model_catalog"
    if not node.is_dir():
        return []
    return sorted(c.stem for c in node.iterdir() if c.name.endswith(".json"))


def catalogue(provider: str) -> list[CatalogEntry]:
    node = resources.files("resource_librarian") / "standard" / "model_catalog" / \
        f"{provider}.json"
    if not node.is_file():
        raise ValueError(f"no standard catalogue for {provider!r}; have {providers()}")
    return _load(node)


def status(vault: Vault, engine: Engine) -> list[dict[str, Any]]:
    """Every standard catalogue, and how much of it this vault already holds -
    by canonical_url, the same identity `ingest` already checks against."""
    out = []
    for provider in providers():
        entries = catalogue(provider)
        held = sum(1 for e in entries
                   if engine.index.note_row(e.name) is not None)
        out.append({"provider": provider, "models": len(entries), "held": held})
    return out


def adopt(vault: Vault, engine: Engine, provider: str, accepted_by: str = "person"
         ) -> dict[str, Any]:
    """Write every not-yet-held entry as an accepted Source note, the same
    `promote` step `staging_decide` uses - this bundle has already been
    reviewed once; adopting it is a person's decision to reuse that review,
    not a fresh, unreviewed draft reaching the vault on its own."""
    store = EvidenceStore(vault)
    written, already_held, failed = [], [], []
    for entry in catalogue(provider):
        if engine.index.note_row(entry.name) is not None:
            already_held.append(entry.name)
            continue
        ev = entry.evidence
        record = store.put(ev["kind"], ev["source"], ev["payload"], ev.get("fetched_at"))
        try:
            report = promote(vault, engine, Draft(
                name=entry.name, kind=KIND, title=entry.title,
                canonical_url=entry.canonical_url, bottom_line=entry.bottom_line,
                what_it_solves=entry.what_it_solves, fields=dict(entry.fields),
                sections=dict(entry.sections),
                evidence=[{"id": record.id, "kind": record.kind, "source": record.source,
                          "fetched_at": record.fetched_at}],
                captured_at=entry.captured_at or now_iso()[:10], attested_by=accepted_by))
        except Exception as exc:                             # noqa: BLE001
            failed.append({"name": entry.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        written.append({"name": entry.name, "path": report.path,
                        "catalogued": report.catalogued})
    return {"provider": provider, "written": len(written), "already_held": len(already_held),
            "failed": failed}
