"""Standard model catalogues: a provider's models, already profiled once, that
any vault can adopt without paying to profile them again.

Profiling a model (`ingest("model:<provider>:<id>")`) fetches its public
listing page and asks a clerk to describe it - real, if small, cost, repeated
for every vault that wants the same provider's models. A catalogue is that
work done once and shipped with the package (`standard/model_catalog/`, one
JSON array per provider), the same relationship a lens pack has to the
lenses it ships (`lens_packs.py`): nothing reaches a vault until a person
adopts it. Adopting again skips already-held names rather than updating a
person's accepted note. Each entry carries the evidence it was drafted from -
adopting is accepting a bundle of already-reviewed sources, not asserting new
facts.

A `model` source is machine-drafted (`describe()`'s `model_specs` task) and
staged for review like any other on first ingest; a catalogue entry has
already been through that once, so adopting it writes the Source note
directly, the same way accepting a lens pack writes lenses directly.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any, Callable

from .evidence import EvidenceStore
from .promote import Draft, promote
from . import promote as promotion
from .coordination import MISSING, fingerprint, operation_path
from .rules import Refusal
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
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", provider) or provider not in providers():
        raise ValueError(f"no standard catalogue for {provider!r}; have {providers()}")
    node = resources.files("resource_librarian") / "standard" / "model_catalog" / \
        f"{provider}.json"
    if not node.is_file():
        raise ValueError(f"no standard catalogue for {provider!r}; have {providers()}")
    return _load(node)


def status(vault: Vault, engine: Engine) -> list[dict[str, Any]]:
    """Every standard catalogue, and how much of it this vault already holds -
    by exact accepted note name (not qualification or a measured capability)."""
    out = []
    for provider in providers():
        entries = catalogue(provider)
        rows = [row for e in entries if (row := engine.index.note_row(e.name)) is not None]
        attention = [row["name"] for row in rows if json.loads(row["frontmatter"]).get("needs_attention")]
        out.append({"provider": provider, "models": len(entries), "held": len(rows),
                    **({"needs_attention": attention} if attention else {})})
    return out


def adopt(vault: Vault, engine: Engine | None, provider: str, accepted_by: str = "person", *,
          index_call: Callable | None = None, write_call: Callable | None = None, leases=None,
          cancelled: Callable[[], bool] | None = None
         ) -> dict[str, Any]:
    """Write every not-yet-held entry as an accepted Source note, the same
    `promote` step `staging_decide` uses - this bundle has already been
    reviewed once; adopting it is a person's decision to reuse that review,
    not a fresh, unreviewed draft reaching the vault on its own."""
    if index_call is not None:
        if write_call is None:
            raise TypeError("Core catalogue adoption requires its writer callback")
        return _adopt_via(vault, provider, accepted_by, index_call, write_call, leases, cancelled)
    if engine is None:
        raise TypeError("catalogue adoption requires an Engine or Core callbacks")
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


def _adopt_via(vault, provider, accepted_by, index_call, write_call, leases, cancelled):
    """One reviewed bundle action, bounded per-entry writer plans (not one giant lease)."""
    index_call(lambda engine: None)  # Admission before evidence or catalogue processing.
    store = EvidenceStore(vault)
    written, held, failed, attention = [], [], [], []
    for entry in catalogue(provider):
        if cancelled is not None and cancelled():
            return {"provider": provider, "written": len(written), "already_held": len(held),
                    "failed": failed, "cancelled": True, "not_findable": attention}
        try:
            if index_call(lambda engine: engine.index.note_row(entry.name)) is not None:
                held.append(entry.name)
                continue
            ev = entry.evidence
            record = store.prepare(ev["kind"], ev["source"], ev["payload"], ev.get("fetched_at"))
            draft = Draft(name=entry.name, kind=KIND, title=entry.title,
                canonical_url=entry.canonical_url, bottom_line=entry.bottom_line,
                what_it_solves=entry.what_it_solves, fields=dict(entry.fields), sections=dict(entry.sections),
                evidence=[{k: getattr(record, k) for k in ("id", "kind", "source", "fetched_at")}],
                captured_at=entry.captured_at or now_iso()[:10], attested_by=accepted_by)
            plan = promotion.prepare(vault, draft, index_call)
            path = store._path(record.kind, record.id)
            rel = path.relative_to(vault.root).as_posix()
            # Do not create evidence through a hidden-root junction either.
            if operation_path(vault, rel) != path:
                raise TypeError("evidence path redirects outside its owned root")
            stamp = fingerprint(path)
            if stamp != MISSING and json.loads(path.read_bytes()) != record.to_dict():
                raise Refusal("EVIDENCE_IS_NEVER_EDITED", "existing evidence does not match its content address")
            plan["observed"].append((rel, stamp))
            plan["targets"].append(rel)
            def commit():
                if index_call(lambda engine: engine.index.note_row(plan["name"])) is not None:
                    raise Refusal("UNIQUE_NOTE_NAMES", "the model was catalogued while adoption waited")
                guard = promotion.PromotionGuard(vault, plan, leases)
                try:
                    if stamp == MISSING:
                        guard.write(rel, json.dumps(record.to_dict(), ensure_ascii=False, indent=1))
                    return promotion.apply(vault, draft, plan, index_call, leases=leases, guard=guard)
                except Refusal as exc:
                    exc.extra["completed_paths"] = list(dict.fromkeys(guard.completed))
                    raise
                except Exception as exc:
                    raise promotion.PromotionInterruptedError(exc, guard.completed) from exc
            report = write_call(commit, plan)
            written.append(entry.name)
            if not report.catalogued:
                attention.append(entry.name)
        except Exception as exc:
            completed = exc.extra.get("completed_paths", []) if isinstance(exc, Refusal) else \
                getattr(exc, "completed_paths", [])
            failed.append({"name": entry.name,
                           "error": str(exc) if isinstance(exc, (Refusal, promotion.PromotionInterruptedError)) else
                                    f"{type(exc).__name__}: adoption failed; inspect and retry explicitly",
                           **({"refused": exc.code} if isinstance(exc, Refusal) else {}),
                           "completed_paths": list(completed)})
    return {"provider": provider, "written": len(written), "already_held": len(held), "failed": failed,
            **({"not_findable": attention} if attention else {})}
