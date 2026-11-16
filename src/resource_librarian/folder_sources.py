"""Accepted third-party folders become Sources (owner, 2026-11-15).

Folder review classifies folders; it never reads their contents. A folder accepted
as `third-party` or `research-docs` is reference material, so each of its documents
enters the normal source pipeline: intake (capture -> evidence -> facts -> describe
-> stage) and then the approved batch (parse -> read -> lenses -> data -> relate ->
metadata -> review). Own content (`owner_created`) is indexed whole instead and is
never turned into Sources.

Queuing is deferred (`ingest defer=true`): no model call happens here, so a whole
folder can be queued for free and processed in measured batches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import content_roots
from .credentials import credential_path, generated_path

SOURCE_PURPOSES = frozenset({"third-party", "research-docs"})
DOCUMENT_SUFFIXES = frozenset({".pdf", ".md", ".txt", ".rst", ".tex", ".html", ".htm", ".docx"})
# What becomes a Source by default. A vendored repository holds thousands of .txt/.rst/.md files (Parallax's
# third-party folders: 9,359 documents, 17 of them PDFs); each Source costs about fifteen Clerk tasks plus its
# reading, so wider scopes are chosen per call, with the counts in view (see `queue`'s not_in_scope).
DEFAULT_SCOPE = (".pdf",)
SKIP_DIRS = frozenset({".git", "node_modules", "venv", ".venv", "__pycache__", "build", "dist", "output",
                       "tmp", "graphify-out", ".librarian", "librarian-app"})


def attached_root(vault: Any, path: Path) -> dict[str, Any] | None:
    """The deepest accepted attached root containing ``path``, or None."""
    manifest = content_roots.load(vault.root) or {}
    target = path.resolve()
    best = None
    for root in manifest.get("roots", []):
        if not root.get("attached"):
            continue
        base = Path(root["path"]).resolve()
        if (target == base or base in target.parents) and (best is None or len(base.parts) > len(Path(best["path"]).resolve().parts)):
            best = root
    return best


def _scope(scope: Any) -> tuple[str, ...]:
    chosen = tuple(str(x).lower() for x in (scope if scope else DEFAULT_SCOPE))
    if not chosen or any(x not in DOCUMENT_SUFFIXES for x in chosen):
        raise ValueError(f"FOLDER_SOURCES: scope is a non-empty subset of {sorted(DOCUMENT_SUFFIXES)}")
    return chosen


def documents(vault: Any, folder: str, scope: Any = None, *, _all: bool = False) -> list[Path]:
    """This accepted reference folder's own documents of the chosen scope, sorted; nothing a deeper decision owns."""
    if scope is not None and not scope and not _all:
        raise ValueError("FOLDER_SOURCES: scope is a non-empty subset of " + str(sorted(DOCUMENT_SUFFIXES)))
    wanted = None if _all else _scope(scope)
    base = Path(folder).resolve()
    decision = attached_root(vault, base)
    if decision is None or Path(decision["path"]).resolve() != base or decision.get("purpose") not in SOURCE_PURPOSES:
        raise ValueError("FOLDER_SOURCES: only an accepted third-party or research-docs folder becomes Sources; "
                         "own content is indexed whole")
    out = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in DOCUMENT_SUFFIXES:
            continue
        if wanted is not None and path.suffix.lower() not in wanted:
            continue
        rel = path.relative_to(base)
        if any(part in SKIP_DIRS or part.lower().endswith("cache") for part in rel.parts[:-1]):
            continue
        if credential_path(rel.as_posix()) or generated_path(rel.as_posix()):
            continue
        owner = attached_root(vault, path)
        if owner is None or Path(owner["path"]).resolve() != base:
            continue                                   # a deeper accepted card decides this one
        out.append(path)
    return out


def _ledger(vault: Any) -> Path:
    return vault.librarian / "folder-sources.json"


def queue(vault: Any, folder: str, *, ingest: Callable[[str, str], dict[str, Any]],
          limit: int = 50, scope: Any = None) -> dict[str, Any]:
    """Defer up to ``limit`` not-yet-queued documents of one folder through ``ingest``."""
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("FOLDER_SOURCES: limit is 1-500 documents per call")
    chosen = _scope(scope)
    docs = documents(vault, folder, chosen)
    left_out: dict[str, int] = {}
    for other in documents(vault, folder, _all=True):
        if other.suffix.lower() not in chosen:
            left_out[other.suffix.lower()] = left_out.get(other.suffix.lower(), 0) + 1
    path = _ledger(vault)
    done = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    queued, failures = 0, []
    for doc in docs:
        key = doc.resolve().as_posix()
        if key in done:
            continue
        if queued >= limit:
            break
        try:
            result = ingest(key, f"folder source: {Path(folder).name}")
        except Exception as exc:                       # one bad document never stops the folder
            failures.append(dict(path=key, error=str(exc)[:200]))
            continue
        done[key] = result.get("status", "queued")
        queued += 1
    path.write_text(json.dumps(done, indent=1), encoding="utf-8")
    keys = {d.resolve().as_posix() for d in docs}
    return dict(folder=str(Path(folder).resolve()), scope=list(chosen), not_in_scope=dict(sorted(left_out.items())),
                documents=len(docs), queued=queued,
                already_queued=sum(1 for k in keys if k in done) - queued,
                remaining=sum(1 for k in keys if k not in done), failures=failures)
