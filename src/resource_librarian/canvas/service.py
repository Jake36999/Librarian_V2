"""Safe canvas writes: preview a change, then commit it only if nothing moved underneath.

The flow (adopted from the owner's MARK XLVIII safe canvas service, W2 2026-11-20):

1. **Preview.** Read the canvas without loss (`document.load_document`). A malformed one is
   reported and never replaced. Merge the generated nodes into it (`merge_managed`): a node
   whose id does not start with the managed prefix is a person's and is kept as it is, and a
   managed node keeps the position it already has. Lay it out (`layout.layout_document`),
   which never moves a pinned node or one a person moved since the last layout. Return the
   result with the file's current revision and the proposal's hash.
2. **Commit.** Refuse if the file's revision changed since the preview (a conflict: preview
   again) or the proposal does not hash to what was previewed. Otherwise back up the current
   file, then replace it atomically.

A canvas that holds no managed node at all was drawn by a person (or by something other than
this service), so `preview` refuses to merge into it unless the caller says it may.
"""
from __future__ import annotations

import copy
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..coordination import atomic_write_text
from .document import (CanvasValidationError, canonical_bytes, content_revision, load_document,
                       merge_managed, proposal_hash)
from .layout import layout_document

MANAGED_PREFIX = "librarian-"


class CanvasConflict(RuntimeError):
    """The canvas changed since it was previewed, or the proposal is not the one previewed."""


def _ids(payload: dict[str, Any]) -> set[str]:
    return {str(n.get("id")) for n in payload.get("nodes", []) if isinstance(n, dict)}


def preview(path: str | Path, generated: dict[str, Any], *, profile: str | None = "dependency",
            managed_prefix: str = MANAGED_PREFIX, adopt: bool = False) -> dict[str, Any]:
    """What writing `generated` into the canvas at `path` would produce. Writes nothing."""
    target = Path(path)
    for node in generated.get("nodes", []):
        if not str(node.get("id") or "").startswith(managed_prefix):
            raise ValueError(f"generated node {node.get('id')!r} must carry the managed prefix "
                             f"{managed_prefix!r}, so a person's own nodes are never taken for it")
    existing = load_document(target)                 # raises CanvasValidationError, never repairs
    managed_before = {i for i in _ids(existing) if i.startswith(managed_prefix)}
    if target.exists() and existing.get("nodes") and not managed_before and not adopt:
        raise CanvasConflict(f"{target.name} holds no node this service wrote: it is a person's "
                             f"canvas, so nothing is merged into it (write a new canvas, or pass "
                             f"adopt=True to add beside its own nodes)")
    merged = merge_managed(existing, generated, managed_prefix=managed_prefix)
    if profile is None:
        # The generator placed its own nodes; a kept node still keeps where it already is.
        proposal, metrics = merged, {"pinned_count": 0, "profile": None}
    else:
        proposal, metrics = layout_document(merged, profile=profile, managed_prefix=managed_prefix)
    generated_ids = _ids(generated)
    return {
        "path": str(target),
        "base_revision": content_revision(target),
        "proposal_hash": proposal_hash(proposal),
        "proposal": proposal,
        "metrics": metrics,
        "changes": {
            "added": sorted(generated_ids - managed_before),
            "removed": sorted(managed_before - generated_ids),
            "kept": sorted(managed_before & generated_ids),
            "persons_nodes_kept": len(_ids(existing) - managed_before),
            "pinned": metrics.get("pinned_count", 0),
        },
    }


def commit(path: str | Path, previewed: dict[str, Any]) -> dict[str, Any]:
    """Write a previewed proposal, if the canvas is still the one previewed."""
    target = Path(path)
    if str(target) != previewed.get("path"):
        raise CanvasConflict("this preview is for another canvas")
    if content_revision(target) != previewed.get("base_revision"):
        raise CanvasConflict(f"{target.name} changed since it was previewed: preview again")
    proposal = previewed.get("proposal")
    if not isinstance(proposal, dict) or proposal_hash(proposal) != previewed.get("proposal_hash"):
        raise CanvasConflict("the proposal is not the one previewed")
    backup = ""
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        # `.bak`, not `.canvas`, so Obsidian does not list the backup as a second canvas.
        copy_to = target.with_name(f"{target.name}.{stamp}.bak")
        shutil.copy2(target, copy_to)
        backup = str(copy_to)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, canonical_bytes(copy.deepcopy(proposal)).decode("utf-8"))
    return {"written": str(target), "revision": content_revision(target), "backup": backup,
            "changes": previewed.get("changes", {})}


def write(path: str | Path, generated: dict[str, Any], **options: Any) -> dict[str, Any]:
    """Preview and commit in one call, for a caller that has already decided (a person running
    a generator). The same checks apply; nothing a person drew is touched."""
    return commit(path, preview(path, generated, **options))


__all__ = ["CanvasConflict", "CanvasValidationError", "MANAGED_PREFIX", "commit", "preview",
           "write"]
