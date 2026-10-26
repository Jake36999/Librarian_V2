"""Bounded, revision-aware repository capability extraction.

This is deliberately an evidence reader, never an executor or unrestricted
clone facility.  The initial planner uses the repository components already
captured by Librarian; unsupported/dynamic imports are reported rather than
invented as a dependency closure.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .coordination import atomic_write_text
from .evidence import EvidenceStore
from .index import Index, run_index
from .rules import Refusal
from .vault import now_iso

SUPPORTED = (".py", ".ts", ".tsx", ".js", ".jsx")


def _source(index: Index, source: str) -> Any:
    row = index.note_row(source, "source")
    if row is None or row["kind"] != "repository":
        raise TypeError("source is a catalogued repository")
    return row


def _with_index(vault: Any, index_service: Any, operation: Any, *, offline: bool = False) -> Any:
    """Keep Core-backed extraction on its single SQLite owner.

    A standalone script must explicitly choose offline mode. Serving callers
    supply their Core service; its absence is never permission to open SQLite.
    """
    return run_index(vault, operation, index_service=index_service, offline=offline)


def _survey_revision(vault: Any, frontmatter: str) -> str:
    """Return the repository tree recorded by survey evidence, never a timestamp.

    Component rows also cover structure and access-point evidence.  Their historical
    ``revision`` value may therefore be an evidence-fetch or component timestamp; it is
    useful search metadata, but cannot pin a reproducible extraction.
    """
    fm = json.loads(frontmatter)
    store = EvidenceStore(vault)
    revisions = {str(record.payload["tree_sha"])
                 for evidence in fm.get("evidence") or []
                 if (record := store.get(str(evidence))) is not None
                 and record.kind == "survey" and record.payload.get("tree_sha")}
    if len(revisions) > 1:
        raise Refusal("PINNED_REVISION_REQUIRED",
                      "the repository cites multiple distinct surveyed tree SHAs")
    return next(iter(revisions), "")


def _plan_token(data: dict[str, Any]) -> str:
    """Content-address the exact reviewed extraction contract, excluding timestamps."""
    contract = {key: value for key, value in data.items() if key not in ("at", "plan_token")}
    digest = hashlib.sha256(json.dumps(
        contract, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    return f"extract-plan-v1:{digest}"


def plan(vault: Any, source: str, seed: str = "", include_tests: bool = False,
         max_files: int = 20, max_chars: int = 80_000, *, index_service: Any = None,
         offline: bool = False) -> dict[str, Any]:
    max_files = max(1, min(int(max_files), 50))
    max_chars = max(1_000, min(int(max_chars), 200_000))
    def collect(index: Index) -> dict[str, Any]:
        index.refresh()
        row = _source(index, source)
        return {"frontmatter": str(row["frontmatter"]),
                "components": [dict(r) for r in index.conn.execute(
                    "SELECT address, revision, evidence FROM component "
                    "WHERE path = ? ORDER BY address", (row["path"],))]}
    collected = _with_index(vault, index_service, collect, offline=offline)
    components = collected["components"]
    revision = _survey_revision(vault, collected["frontmatter"])
    if not revision:
        raise Refusal("PINNED_REVISION_REQUIRED",
                      "the repository has no survey evidence with a pinned tree SHA")
    candidates = []
    for component in components:
        address = str(component.get("address") or "")
        suffix = Path(address).suffix.lower()
        if suffix not in SUPPORTED:
            continue
        if not include_tests and any(part in address.lower() for part in ("/test", "\\test", "_test.")):
            continue
        if seed and seed.lower() not in address.lower():
            continue
        candidates.append(component)
    if seed and not candidates:
        # Be transparent: a seed may name a capability rather than a path.
        candidates = [c for c in components if Path(str(c.get("address") or "")).suffix.lower() in SUPPORTED]
    selected = candidates[:max_files]
    files = [{"path": str(c["address"]), "revision": revision,
              "evidence": str(c.get("evidence") or "")} for c in selected]
    out = {"source": source, "seed": seed, "revision": revision, "files": files,
           "include_tests": include_tests, "max_files": max_files, "max_chars": max_chars,
           "estimated_chars": min(max_chars, len(files) * 4_000),
           "unresolved": ["dynamic and external imports are reported, not resolved in v1"],
           "closure": "survey-bounded", "at": now_iso()}
    return {**out, "plan_token": _plan_token(out)}


def materialize(vault: Any, source: str, *, seed: str = "", include_tests: bool = False,
                max_files: int = 20, max_chars: int = 80_000, fetcher: Any = None,
                revision: str | None = None, plan_token: str | None = None,
                index_service: Any = None,
                offline: bool = False) -> dict[str, Any]:
    from . import upkeep
    from .intake import Fetcher
    data = plan(vault, source, seed, include_tests, max_files, max_chars,
                index_service=index_service, offline=offline)
    # Omitting both review fields retains the direct Python API's compatibility while
    # still pinning its single plan-and-fetch operation to the plan just observed.  Any
    # caller presenting review data must present the complete pair.
    internal_plan = revision is None and plan_token is None
    if internal_plan:
        revision = data["revision"]
        plan_token = data["plan_token"]
    if not revision:
        raise Refusal("PINNED_REVISION_REQUIRED",
                      "provide the pinned revision returned by extract_plan")
    if revision != data["revision"]:
        raise Refusal("PINNED_REVISION_REQUIRED",
                      "the reviewed extract plan no longer matches the surveyed tree SHA")
    if not plan_token:
        raise Refusal("PINNED_REVISION_REQUIRED",
                      "provide the plan token returned by extract_plan")
    if plan_token != data["plan_token"]:
        raise Refusal("PINNED_REVISION_REQUIRED",
                      "the reviewed extract plan no longer matches these extraction options")
    used = 0
    excerpts = []
    for item in data["files"]:
        remaining = max(0, max_chars - used)
        if remaining <= 0:
            break
        # Only copy metadata on the worker. Evidence/cache reads and the
        # actual repository fetch must not occupy the sole SQLite owner.
        from types import SimpleNamespace
        def index_call(operation: Any) -> Any:
            def lookup(index: Index) -> Any:
                row = operation(SimpleNamespace(index=index))
                return dict(row) if row is not None else None
            return _with_index(vault, index_service, lookup, offline=offline)
        file = upkeep.source_file(vault, None, fetcher or Fetcher(), source,
                                  item["path"], min(20_000, remaining), index_call=index_call,
                                  pinned_revision=revision)
        text = str(file.get("text") or "")
        used += len(text)
        excerpts.append({"path": item["path"], "revision": file.get("version", ""),
                         "text": text, "truncated": bool(file.get("truncated"))})
    key = hashlib.sha256(json.dumps({"source": source, "revision": data["revision"],
                                     "files": [x["path"] for x in excerpts]}, sort_keys=True).encode()).hexdigest()[:20]
    target = vault.derived / "extract" / f"{key}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    out = {**data, "materialized": len(excerpts), "chars": used, "excerpts": excerpts,
           "cache": str(target.relative_to(vault.root)), "at": now_iso()}
    atomic_write_text(target, json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    return out
