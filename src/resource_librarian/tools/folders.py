"""Folder review as tools (implementation plan M1a; as-is W-ACT-01).

A folder the person connected, or routed an agent to, is open to that library's agents through these
same actions (policy: "A connected folder is the person's decision"). The Web UI's `/api/folders/*`
routes call these tools too, so every surface passes the same checks and gets the same refusal codes.

Who decides is unchanged: accepting one folder and approving a folder batch are the person's (curate
tier, and refused for a declared agent); an agent accepts folders only by policy, under promotion mode
agent, which only the owner sets.
"""
from __future__ import annotations

from typing import Any

from ..folder_service import FolderService, refusal_of
from ..registry import Card, Context, REGISTRY, tool
from ..rules import Refusal


def _service(ctx: Context) -> FolderService:
    service = ctx.extras.get("folder_service")
    return service if service is not None else FolderService(ctx.vault)


def _is_person(ctx: Context) -> bool:
    return ctx.extras.get("caller_kind") == "person" and not ctx.extras.get("actor")


def _run(fn):
    try:
        return fn()
    except ValueError as exc:
        refusal = refusal_of(exc)
        if refusal is not None:
            raise refusal from exc
        raise TypeError(str(exc)) from exc       # a plain argument problem, with its message


@tool("folder_overview", tier="consult", effect="read",
      returns=("cards", "purposes", "enabled", "credential_refusals"),
      card=Card("The library's connected folders: each surveyed folder's card, its suggested and "
                "accepted purpose, and whether its documents can be queued as Sources",
                "before surveying, deciding or queueing a folder",
                "Folder cards describe folders; their documents' content is not returned"))
def folder_overview(ctx: Context) -> dict:
    return _service(ctx).overview()


@tool("folder_survey", tier="contribute", effect="write", scope="library", orchestrates=True,
      returns=(),
      card=Card("Survey a folder the person connected or routed you to: inventory its subfolders "
                "into folder cards with suggested purposes, reading metadata only",
                "a person asked for a folder to be brought into the library",
                "No document is read and no model is called. Survey again after the folder "
                "changes; a stale card refuses its decision (FOLDER_STALE)"))
def folder_survey(ctx: Context, path: str) -> dict:
    return _run(lambda: _service(ctx).survey(path))


@tool("folder_draft", tier="contribute", effect="write", scope="library", orchestrates=True,
      open_world=True, returns=("id", "description"),
      card=Card("Have the Clerk draft one folder card's description and sensitivity review from "
                "its inventory",
                "a folder card has no description yet",
                "Spends: pass approve_spend=true for this request. Needs the owner's approval of a "
                "qualified Clerk assignment (FOLDER_DRAFT_DISABLED otherwise)"))
def folder_draft(ctx: Context, id: str = "", approve_spend: bool = False) -> dict:
    from .staging import clerk_endpoint
    return _run(lambda: _service(ctx).draft(id, clerk_endpoint(ctx), approve_spend=approve_spend))


@tool("folder_accept", tier="curate", effect="write", scope="library", orchestrates=True,
      returns=("id", "status", "decision"),
      card=Card("Accept one folder card with its purpose, authorship and graph, and apply its group",
                "the person decides a folder in Folders",
                "The person's decision: refused for an agent (PERSON_CONFIRMS); an agent uses "
                "folder_accept_policy under promotion mode agent"))
def folder_accept(ctx: Context, id: str = "", folder_fingerprint: str = "", purpose: str = "", graph: str = "",
                  description: str | None = None, authorship: str | None = None) -> dict:
    if not _is_person(ctx):
        raise Refusal("PERSON_CONFIRMS", "a person accepts a single folder; an agent uses "
                                         "folder_accept_policy under promotion mode agent")
    return _run(lambda: _service(ctx).accept(id, folder_fingerprint, purpose=purpose, graph=graph or None,
                                             description=description, authorship=authorship, person=True))


@tool("folder_accept_policy", tier="contribute", effect="write", scope="library", orchestrates=True,
      returns=("accepted", "held", "covered"),
      card=Card("Accept a surveyed root's unambiguous, non-sensitive folder cards as suggested, and "
                "apply their groups",
                "promotion mode is agent and a surveyed root's cards wait for a decision",
                "Needs promotion.mode = agent, which only the owner sets (PROMOTION_MODE). "
                "Ambiguous and sensitive cards are held for the person"))
def folder_accept_policy(ctx: Context, root: str) -> dict:
    return _run(lambda: _service(ctx).accept_by_policy(root))


@tool("folder_approve_batch", tier="curate", effect="write", scope="library", orchestrates=True,
      returns=("approved",),
      card=Card("Approve 1-100 waiting folder cards for the next batch",
                "the person approves folder cards in Folders",
                "The person's decision: refused for an agent (PERSON_CONFIRMS). Approved is not "
                "accepted: the batch describes the folders, then each is decided"))
def folder_approve_batch(ctx: Context, items: list[str] | None = None) -> dict:
    return _run(lambda: _service(ctx).approve_batch(items, person=_is_person(ctx)))


@tool("folder_queue_sources", tier="contribute", effect="write", scope="library", orchestrates=True,
      returns=("queued", "documents", "remaining", "not_in_scope"),
      card=Card("Queue an accepted reference folder's documents for intake as Sources",
                "a third-party, research-docs or own-docs folder is accepted and its documents "
                "should become Sources",
                "No model call here: each document is deferred (ingest defer=true) and captured "
                "when the queue runs. PDFs by default; pass scope to widen it, with the counts in "
                "view"))
def folder_queue_sources(ctx: Context, folder: str, limit: int = 50, scope: list[str] | None = None,
                         order: str = "name") -> dict:
    def ingest(ref: str, note: str) -> Any:
        # Each document is queued with the caller's own authority, not a person's.
        return REGISTRY.call("ingest", {"ref": ref, "defer": True, "note": note}, ctx)
    return _run(lambda: _service(ctx).queue_sources(folder, limit=limit, scope=scope, order=order,
                                                    ingest=ingest))


@tool("folder_queue_accepted", tier="contribute", effect="write", scope="library", orchestrates=True,
      returns=("folders", "queued", "remaining"),
      card=Card("Queue the documents of every accepted reference folder under a surveyed root",
                "after a root's folders are accepted, so accepting a folder can lead straight on to "
                "intake (as-is W-FOL-04)",
                "The same queueing as folder_queue_sources, folder by folder, up to `limit` documents "
                "in all; each document is deferred (no model call) with the caller's own authority"))
def folder_queue_accepted(ctx: Context, root: str, limit: int = 50, scope: list[str] | None = None) -> dict:
    from pathlib import Path
    from ..ingestion import _key
    service = _service(ctx)
    base = _key(root)
    folders = [c for c in service.overview().get("cards", [])
               if c.get("queueable") and c.get("source_root") and _key(c["source_root"]) == base]
    out, queued, remaining = [], 0, 0
    for card in folders:
        folder = str(card["source_root"]) if card.get("path") in (".", "") else str(Path(card["source_root"]) / card["path"])
        left = max(0, limit - queued)
        if not left:
            out.append({"folder": folder, "queued": 0, "skipped": "the limit was reached"})
            continue
        result = REGISTRY.call("folder_queue_sources", {"folder": folder, "limit": min(500, left),
                                                        **({"scope": scope} if scope else {})}, ctx)
        if "error" in result:
            out.append({"folder": folder, "error": result.get("refused") or result.get("error"),
                        "detail": str(result.get("detail") or "")[:300]})
            continue
        queued += int(result.get("queued") or 0)
        remaining += int(result.get("remaining") or 0)
        out.append({"folder": folder, "queued": result.get("queued"), "remaining": result.get("remaining")})
    return {"folders": out, "queued": queued, "remaining": remaining}


@tool("ingestion_ledger", tier="consult", effect="read",
      returns=("root", "folders", "documents", "sources", "unaccounted", "next"),
      card=Card("One surveyed folder's ingestion, reconciled: folders surveyed and accepted, documents "
                "queued, and sources staged, read and accepted, with what is unaccounted for and what "
                "waits next",
                "checking an ingestion's progress without piecing it together call by call",
                "Reads the folder cards, the folder-to-Source queue and the staging store; changes nothing"))
def ingestion_ledger(ctx: Context, root: str) -> dict:
    from ..ingestion import ledger
    return ledger(ctx.vault, root)
