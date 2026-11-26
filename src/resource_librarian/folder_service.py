"""Folder review as one service, used by every surface (implementation plan M1a, 2026-11-26).

Policy (agent-roles-and-authority, "A connected folder is the person's decision"): a folder the person
connected, or routed an agent to, is open to that library's agents through the same actions the Web UI
uses. Before this, folder review was reachable only through the Core API's `/api/folders/*` routes, so
no workflow or MCP caller could use it (as-is W-ACT-01).

The service owns how each operation runs beside the Core, as the routes did:
- a survey walks the folder before the writer is asked for anything (2026-11-17: an 8-minute walk inside
  the writer starved the whole Core);
- an acceptance's long project walk and Geo-Grapher build run beside the single writer, and only its
  writes go to the writer;
- folder operations run one after another.

Errors stay `ValueError("CODE: detail")`, as FolderReview raises them; `refusal_of` names the rule.
Who may decide stays where it was: a person accepts one folder and approves a batch; an agent accepts by
policy only under promotion mode agent, which only the owner sets.
"""
from __future__ import annotations

import contextlib
import threading
from typing import Any, Callable

from .rules import RULES, Refusal


def refusal_of(exc: Exception) -> Refusal | None:
    """The named rule behind a folder ValueError ("CODE: detail" or "CODE"), if it names one."""
    text = str(exc)
    code, _, detail = text.partition(":")
    code = code.strip()
    return Refusal(code, detail.strip()) if code in RULES else None


def state_label(card: dict[str, Any]) -> str:
    """One meaning per folder-card state (as-is W-FOL-05): a card selected for the description batch is
    not decided, and only an accepted card has been applied."""
    status = card.get("status")
    if status == "accepted":
        by = (card.get("decision") or {}).get("accepted_by")
        return "Decided and applied" + (" by the agent policy" if by == "agent-policy" else " by a person" if by else "")
    if status == "approved":
        return "Selected for the description batch; not decided yet"
    if status == "processing":
        return "Being described in a batch; not decided yet"
    if status == "partial":
        return "Described with gaps; waiting for a decision"
    if status == "failed":
        return "Application failed; review and retry"
    return "Waiting for a decision"


class FolderService:
    def __init__(self, vault: Any, *, writer: Any = None, lock: Any = None,
                 serialized: Callable[[str, Callable[[], Any]], Any] | None = None,
                 counted: Callable[[str], Any] | None = None, planner: Any = None, applier: Any = None):
        self.vault = vault
        self.planner, self.applier = planner, applier      # Geo-Grapher's, unless a test supplies them
        self.writer = writer
        self.lock = lock if lock is not None else threading.RLock()
        self._serialized = serialized or (lambda caller, fn: fn())
        self._counted = counted or (lambda what: contextlib.nullcontext())

    def _review(self, commit: Callable[[Callable[[], Any]], Any] | None = None):
        from .folder_review import FolderReview
        return FolderReview(self.vault, commit=commit, planner=self.planner, applier=self.applier)

    def _beside_writer(self, caller: str, fn: Callable[[Any], Any]) -> Any:
        if self.writer is None:
            return self._serialized(caller, lambda: fn(self._review()))
        with self.lock, self._counted(f"the {caller} mutation"):
            return fn(self._review(commit=lambda write: self.writer.submit(write, caller=caller)))

    # -- reads ----------------------------------------------------------------
    def overview(self) -> dict[str, Any]:
        from .folder_sources import SOURCE_PURPOSES
        data = self._review().overview()
        for card in data.get("cards", []):
            # One eligibility rule on every surface: the UI shows "Queue documents as Sources"
            # exactly where `queue` accepts the folder (own-docs included).
            purpose = (card.get("decision") or {}).get("purpose")
            card["queueable"] = card.get("status") == "accepted" and purpose in SOURCE_PURPOSES
            card["state_label"] = state_label(card)
        return data

    # -- operations -----------------------------------------------------------
    def survey(self, path: str) -> dict[str, Any]:
        from . import deploy_survey
        if not str(path or "").strip():
            raise ValueError("FOLDER_REFERENCE: name a folder")
        with self.lock:
            found = deploy_survey.survey(path, geographer={"enabled": False}) if self.writer is not None else None
            return self._serialized("folder-survey", lambda: self._review().survey(path, surveyed=found))

    def draft(self, item_id: str, endpoint: Any, *, approve_spend: bool) -> dict[str, Any]:
        commit = (lambda write: self.writer.submit(write, caller="folder-draft")) if self.writer is not None else None
        with self.lock:
            return self._review(commit=commit).draft(item_id, endpoint, approved=approve_spend is True)

    def accept(self, item_id: str, fingerprint: str, *, purpose: Any, graph: Any, description: Any = None,
               authorship: Any = None, person: bool) -> dict[str, Any]:
        return self._beside_writer("folder-accept", lambda review: review.accept(
            item_id, fingerprint, purpose=purpose, graph=graph, person=person,
            description=description, authorship=authorship))

    def accept_by_policy(self, root: str) -> dict[str, Any]:
        if not str(root or "").strip():
            raise ValueError("FOLDER_REFERENCE: name the surveyed source root")
        return self._beside_writer("folder-accept", lambda review: review.accept_by_policy(root))

    def approve_batch(self, items: Any, *, person: bool) -> dict[str, Any]:
        return self._serialized("folder-batch-approve", lambda: self._review().approve_batch(items, person=person))

    def queue_sources(self, folder: str, *, limit: int, scope: Any, order: str,
                      ingest: Callable[[str, str], Any]) -> dict[str, Any]:
        from .folder_sources import queue
        with self.lock:                           # one ledger writer at a time (2026-11-17)
            return queue(self.vault, folder, limit=limit, scope=scope, order=order, ingest=ingest)
