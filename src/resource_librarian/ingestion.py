"""A folder's ingestion, reconciled (implementation plan M5; as-is W-ING-01).

On 19-20 November nothing reconciled a folder's counts: what was surveyed, queued, staged, read and
accepted had to be pieced together by tier 0, call by call. `ledger(vault, root)` reads the stores that
already hold each step - the folder cards, the folder-to-Source queue ledger, the staging store - and
says, for one surveyed root, how many documents sit at each step and which are unaccounted for. It reads
only; nothing here decides or moves anything.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# The order a document goes through, as staging names its statuses.
STEPS = ("queued", "staged", "approved", "processing", "enriched", "partial", "accepted", "failed",
         "deferred", "rejected")


def _key(path: Any) -> str:
    return os.path.normcase(str(Path(str(path)).resolve()))


def _under(path: str, root: str) -> bool:
    key = _key(path)
    return key == root or key.startswith(root.rstrip("\\/") + os.sep)


def ledger(vault: Any, root: str) -> dict[str, Any]:
    from .folder_review import FolderReview
    from .folder_sources import SOURCE_PURPOSES, documents
    from .staging import StagingStore
    base = _key(root)
    cards = [c for c in FolderReview(vault).list(include_provenance=False)
             if c.get("source_root") and _key(c["source_root"]) == base]
    folders = {"surveyed": len(cards),
               "accepted": sum(1 for c in cards if c.get("status") == "accepted"),
               "waiting": sum(1 for c in cards if c.get("status") != "accepted")}
    reference = []
    for card in cards:
        purpose = (card.get("decision") or {}).get("purpose")
        if card.get("status") == "accepted" and purpose in SOURCE_PURPOSES:
            reference.append(str(card["source_root"]) if card.get("path") in (".", "") else
                             str(Path(card["source_root"]) / card["path"]))
    in_folders: set[str] = set()
    for folder in reference:
        try:
            in_folders |= {_key(p) for p in documents(vault, folder)}
        except ValueError:
            continue                                   # a folder decided after the list was read
    path = vault.librarian / "folder-sources.json"
    queued_ledger = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    queued = {_key(k) for k in queued_ledger if _under(k, base)}
    statuses: dict[str, int] = {}
    seen: set[str] = set()
    for item in StagingStore(vault).items("source"):
        # A queued item keeps its document as `ref`; capture moves it to `file` (M5 acceptance,
        # 2026-11-27: read on the queued shape only, every captured source showed as unaccounted).
        ref = str(item.get("ref") or item.get("file_original") or item.get("file") or "")
        if not ref or ref.startswith(("http:", "https:")) or not _under(ref, base):
            continue
        seen.add(_key(ref))
        statuses[item.get("status", "staged")] = statuses.get(item.get("status", "staged"), 0) + 1
    documents_count = len(in_folders)
    return {
        "root": str(Path(root).resolve()),
        "folders": folders,
        "documents": {"in_accepted_reference_folders": documents_count,
                      "queued_from_folders": len(queued & in_folders) if in_folders else len(queued),
                      "not_yet_queued": len(in_folders - queued)},
        "sources": {step: statuses[step] for step in STEPS if statuses.get(step)},
        # Queued by folder review but never captured into staging: lost between two steps.
        "unaccounted": sorted(queued - seen)[:20],
        "unaccounted_count": len(queued - seen),
        "next": _next(folders, documents_count, len(in_folders - queued), statuses),
    }


def _next(folders: dict[str, int], documents: int, not_queued: int, statuses: dict[str, int]) -> str:
    if folders["waiting"]:
        return f"{folders['waiting']} folder card(s) wait for a decision (Folders, or folder_accept_policy)"
    if not_queued:
        return f"{not_queued} document(s) of accepted reference folders are not queued (folder_queue_accepted)"
    if statuses.get("queued"):
        return f"{statuses['queued']} queued document(s) are not captured yet (run-queue / intake_run)"
    if statuses.get("staged"):
        return f"{statuses['staged']} staged source(s) wait for approval into the batch"
    if statuses.get("approved"):
        return f"{statuses['approved']} approved source(s) wait for the batch to start (a person's)"
    if statuses.get("enriched") or statuses.get("partial"):
        return f"{statuses.get('enriched', 0) + statuses.get('partial', 0)} read source(s) wait for acceptance"
    return "nothing waits" if documents or folders["surveyed"] else "survey the folder first"
