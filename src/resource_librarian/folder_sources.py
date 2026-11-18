"""Accepted third-party folders become Sources (owner, 2026-11-15).

Folder review classifies folders; it never reads their contents. A folder accepted
as `third-party` or `research-docs` is reference material, so each of its documents
enters the normal source pipeline: intake (capture -> evidence -> facts -> describe
-> stage) and then the approved batch (parse -> read -> lenses -> data -> relate ->
metadata -> review). Own code, data and logs (`owner_created`) are indexed whole instead
and never turned into Sources. Own documentation (`own-docs`) is both (owner, 2026-11-16):
read as Sources, and still indexed in its own graph, reasoned over separately and joined
by the cross-graph analysis.

Queuing is deferred (`ingest defer=true`): no model call happens here, so a whole
folder can be queued for free and processed in measured batches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from . import content_roots
from .credentials import credential_path, generated_path

SOURCE_PURPOSES = frozenset({"third-party", "research-docs", "own-docs"})
ORDERS = ("name", "newest")
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


def blocked_folders(vault: Any) -> set[str]:
    """Normcased absolute folders no folder source may come from: the manifest's excludes (an
    `exclude` decision or survey hygiene) and folders still withheld for a decision."""
    import os
    from .workspace_documents import roots, undecided_folders
    manifest = content_roots.load(vault.root) or {}
    out = set(undecided_folders(vault, roots(vault)))
    for value in manifest.get("excludes", []):
        path = Path(value)
        out.add(os.path.normcase(str((path if path.is_absolute() else vault.root / path).resolve())))
    return out


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
        raise ValueError("FOLDER_SOURCES: only an accepted third-party, research-docs or own-docs folder "
                         "becomes Sources; other own content is indexed whole")
    import os
    from .workspace_documents import _inside
    blocked = blocked_folders(vault)
    # The deepest attached root owning a path, by its parents: one manifest read, not one per file.
    bases = {os.path.normcase(str(Path(r["path"]).resolve())) for r in
             (content_roots.load(vault.root) or {}).get("roots", []) if r.get("attached")}
    mine = os.path.normcase(str(base))

    def owned_here(path: Path) -> bool:
        for parent in path.parents:
            key = os.path.normcase(str(parent))
            if key in bases:
                return key == mine                     # a deeper accepted card decides otherwise
        return False

    def skipped(part: str) -> bool:
        # Hidden folders too, as the survey treats them (2026-11-16: pytest scratch PDFs inside a
        # hidden temp folder were queued as the "newest" research papers).
        return part in SKIP_DIRS or part.lower().endswith("cache") or part.startswith(".")

    out = []
    # Skipped folders are pruned before they are entered (2026-11-18: rglob walked whole .git and
    # .venv trees only to drop every file found there).
    for here, directories, files in os.walk(base):
        directories[:] = [d for d in directories if not skipped(d)]
        parent = Path(here)
        for name in files:
            path = parent / name
            suffix = path.suffix.lower()
            if suffix not in DOCUMENT_SUFFIXES or (wanted is not None and suffix not in wanted):
                continue
            rel = path.relative_to(base)
            if credential_path(rel.as_posix()) or generated_path(rel.as_posix()):
                continue
            if not owned_here(path) or _inside(path.parent, blocked):
                continue                               # a deeper decision, an exclusion or a hold
            out.append(path)
    return sorted(out)


def _ledger(vault: Any) -> Path:
    return vault.librarian / "folder-sources.json"


def queue(vault: Any, folder: str, *, ingest: Callable[[str, str], dict[str, Any]],
          limit: int = 50, scope: Any = None, order: str = "name") -> dict[str, Any]:
    """Defer up to ``limit`` not-yet-queued documents of one folder through ``ingest``.
    ``order="newest"`` queues the most recently modified first (intake runs in queue order)."""
    if not isinstance(limit, int) or not 1 <= limit <= 500:
        raise ValueError("FOLDER_SOURCES: limit is 1-500 documents per call")
    if order not in ORDERS:
        raise ValueError(f"FOLDER_SOURCES: order is one of {list(ORDERS)}")
    chosen = _scope(scope)
    docs = documents(vault, folder, chosen)
    if order == "newest":
        docs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
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
    from .coordination import atomic_write_text
    atomic_write_text(path, json.dumps(done, indent=1))        # never a half-written ledger
    keys = {d.resolve().as_posix() for d in docs}
    return dict(folder=str(Path(folder).resolve()), scope=list(chosen), order=order, not_in_scope=dict(sorted(left_out.items())),
                documents=len(docs), queued=queued,
                already_queued=sum(1 for k in keys if k in done) - queued,
                remaining=sum(1 for k in keys if k not in done), failures=failures)
