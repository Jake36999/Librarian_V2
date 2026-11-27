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



# A held folder card is a ticket with an owner (M5 planted cases; plan M5 item 2: "unmet items are held
# with their tickets, and the rest go on"). Policy acceptance used to return its held cards once, to
# whoever called it, and nothing kept them. What holds a card decides who owns it: a sensitivity, link
# or authorship question, or content changed where a decision cannot cover it, is the person's reserved
# decision; a card not yet checked, stale or invalid
# is the Lead's to remedy. Deciding the card closes the ticket (the Core's own recheck).
_PERSONS_HOLDS = ("sensitive", "link", "authorship", "changed")       # "changed": Owner, 27 November


def _held_ticket_class(reason: str) -> str:
    return "reserved_decision" if any(word in reason for word in _PERSONS_HOLDS) else "partial_or_unmet"


def _remedy(reason: str) -> str:
    if "not yet checked" in reason:
        return "draft the card (folder_draft) so its sensitivity is checked, then accept by policy again"
    if reason.startswith("stale"):
        return "survey the folder again (folder_survey), then accept by policy again"
    if reason.startswith("validation"):
        return "review the card in Folders; its inventory did not validate"
    return "a person decides this folder in Folders"


def _write_tickets(ctx: Context, fn) -> None:
    """Ticket writes go through the Core's writer when there is one (these tools run beside it)."""
    try:
        writer = ctx.extras.get("vault_writer") if isinstance(ctx.extras, dict) else None
        if writer is not None:
            writer.submit(fn, caller="folder-tickets")
        else:
            fn()
    except Exception:                                    # noqa: BLE001 - a ticket never fails the decision
        pass


def _hold_tickets(ctx: Context, held: list[dict], decided_ids: set[str]) -> None:
    from ..tickets import TicketStore

    def write():
        store = TicketStore(ctx.vault)
        for ticket in store.all(open_only=True):
            if ticket["scope"].removeprefix("folder:") in decided_ids:
                store.close(ticket["id"], "core-recheck", "the folder card was decided")
        for hold in held:
            reason = str(hold.get("reason") or "held")
            store.ensure(_held_ticket_class(reason), f"folder:{hold['id']}", opened_by="folder-policy",
                         summary=f"folder {hold.get('path')} held: {reason}. Next: {_remedy(reason)}",
                         evidence={"card": hold["id"], "path": hold.get("path"), "reason": reason})
    _write_tickets(ctx, write)

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



# A card is drafted when the Clerk has checked its sensitivity (`folder_review.draft`). Until then,
# policy acceptance holds it ("sensitivity not yet checked"), and an excluded or inherited card needs
# no check of its own.
_CHECKED = frozenset({"normal", "review_required"})


def _needs_draft(card: dict) -> bool:
    return (card.get("status") != "accepted" and not card.get("decision") and not card.get("inherited")
            and card.get("suggested_purpose") != "exclude"
            and (card.get("sensitivity") or {}).get("sensitivity") not in _CHECKED)


@tool("folder_draft_pending", tier="contribute", effect="write", scope="library", orchestrates=True,
      open_world=True, returns=("drafted", "held", "failed", "remaining"),
      card=Card("Have the Clerk draft every waiting folder card under a surveyed root that has no draft "
                "yet: its description and its sensitivity check",
                "after a survey, so that policy acceptance can decide the cards (an undrafted card is held "
                "as 'sensitivity not yet checked'); the ingest-folder pipeline's draft step",
                "Spends: pass approve_spend=true for this request (SPEND_APPROVAL_REQUIRED otherwise). Each "
                "card is one folder_draft call with the caller's own authority, so its gates hold "
                "(FOLDER_DRAFT_DISABLED without the owner's approval of the Clerk route). Only folder "
                "metadata reaches the Clerk"))
def folder_draft_pending(ctx: Context, root: str, approve_spend: bool = False, limit: int = 50) -> dict:
    """The draft step of a folder's ingestion (M5; as-is W-BAT-01): `folder_draft`, card by card, for
    the cards that need one, as `folder_queue_accepted` runs `folder_queue_sources`. A card the Clerk
    finds sensitive is reported as held; a failed draft says why, and the others go on."""
    if approve_spend is not True:
        raise Refusal("SPEND_APPROVAL_REQUIRED", "drafting asks the Clerk two questions per folder card; "
                                                 "pass approve_spend=true for this request")
    from ..ingestion import _key
    base = _key(root)
    pending = [c for c in _service(ctx).overview().get("cards", [])
               if c.get("source_root") and _key(c["source_root"]) == base and _needs_draft(c)]
    pending.sort(key=lambda c: (c.get("path") != ".", str(c.get("path"))))
    drafted, held, failed = [], [], []
    for card in pending[:max(0, int(limit))]:
        out = REGISTRY.call("folder_draft", {"id": card["id"], "approve_spend": True}, ctx)
        if "error" in out:
            failed.append({"path": card.get("path"), "refused": out.get("refused") or out.get("error"),
                           "detail": str(out.get("detail") or "")[:300]})
            if out.get("refused") in ("FOLDER_DRAFT_DISABLED", "SPEND_APPROVAL_REQUIRED", "CLERK_UNAVAILABLE"):
                break                                    # the same for every card: say it once
            continue
        sensitivity = (out.get("sensitivity") or {}).get("sensitivity")
        (held if sensitivity == "review_required" else drafted).append(card.get("path"))
    return {"drafted": drafted, "held": held, "failed": failed,
            "remaining": max(0, len(pending) - max(0, int(limit)))}

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
    out = _run(lambda: _service(ctx).accept(id, folder_fingerprint, purpose=purpose, graph=graph or None,
                                            description=description, authorship=authorship, person=True))
    if isinstance(out, dict) and out.get("status") == "accepted":
        _hold_tickets(ctx, [], {id})                     # a card the person decided is no longer held
    return out


@tool("folder_accept_policy", tier="contribute", effect="write", scope="library", orchestrates=True,
      returns=("accepted", "held", "covered"),
      card=Card("Accept a surveyed root's unambiguous, non-sensitive folder cards as suggested, and "
                "apply their groups",
                "promotion mode is agent and a surveyed root's cards wait for a decision",
                "Needs promotion.mode = agent, which only the owner sets (PROMOTION_MODE). "
                "Ambiguous and sensitive cards are held for the person"))
def folder_accept_policy(ctx: Context, root: str) -> dict:
    out = _run(lambda: _service(ctx).accept_by_policy(root))
    if isinstance(out, dict) and "held" in out:
        from ..ingestion import _key
        base = _key(root)
        decided = {c["id"] for c in _service(ctx).overview().get("cards", [])
                   if c.get("status") == "accepted" and c.get("source_root") and _key(c["source_root"]) == base}
        _hold_tickets(ctx, list(out.get("held") or []), decided)
    return out


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



@tool("ingestion_begin", tier="contribute", effect="write", scope="library", orchestrates=True,
      open_world=True, returns=("approved", "started", "held", "sensitive", "run"),
      card=Card("Approve a surveyed folder's staged sources into the batch and start it, as the person; for "
                "any other caller, hold that decision on the person's agenda",
                "the ingest-folder pipeline's last decision, once its documents are captured",
                "High risk: approving and starting commit spend (Research Pipeline §4.2). The person's own "
                "call does both, through staging_decide and process_approved; another caller's call holds "
                "them on the person's agenda as one reserved decision and changes nothing else. A source "
                "marked sensitive is never approved here: a person reviews it on its own"))
def ingestion_begin(ctx: Context, root: str, reason: str = "") -> dict:
    """The batch from the pipeline (M5; plan M5 item 1). Starting the batch stays the person's, as it
    always was (`process_approved` is curate tier). Until the commission (M2) lets tier 0 decide it, an
    agent's run holds it for the person (policy: "High risk when no tier 0 oversees"), and the rest of
    its run goes on."""
    from ..ingestion import _key, staged_under
    from ..tickets import TicketStore
    staged = staged_under(ctx.vault, root)
    sensitive = sorted(i["id"] for i in staged if i.get("sensitivity") == "review")
    ready = sorted(i["id"] for i in staged if i.get("sensitivity") != "review")
    scope = f"ingestion:{_key(root)}"[:300]
    if not ready:
        return {"approved": 0, "started": False, "held": False, "sensitive": sensitive,
                "detail": "nothing staged from this folder waits to be approved"}
    if not (_is_person(ctx) and ctx.tier == "curate"):
        held = {}

        def hold():
            held.update(TicketStore(ctx.vault).ensure(
                "reserved_decision", scope, opened_by="ingestion",
                summary=f"{len(ready)} staged source(s) from {root} wait to be approved into the batch and "
                        f"the batch started: a high-risk decision, the person's (Staging: approve, then "
                        f"begin)" + (f"; {len(sensitive)} marked sensitive wait for review on their own"
                                     if sensitive else ""),
                evidence={"root": root, "items": ready[:200], "sensitive": sensitive[:200]}))
        _write_tickets(ctx, hold)
        return {"approved": 0, "started": False, "held": True, "sensitive": sensitive,
                "ticket": held.get("id", "")}
    approved: list[str] = []
    refused: list[dict] = []
    for start in range(0, len(ready), 100):
        out = REGISTRY.call("staging_decide", {"item_ids": ready[start:start + 100], "decision": "approve",
                                               "reason": reason or f"ingest-folder: {root}"}, ctx)
        if "error" in out:
            return {"approved": len(approved), "started": False, "held": False, "sensitive": sensitive,
                    "refused": out.get("refused") or out.get("error"), "detail": str(out.get("detail") or "")[:300]}
        for row in out.get("results") or []:
            (refused.append({"id": row.get("id"), "why": str(row.get("refused") or row.get("error"))[:200]})
             if ("refused" in row or "error" in row) else approved.append(row.get("id")))
    begun = REGISTRY.call("process_approved", {"background": True}, ctx) if approved else {}

    def recheck():
        store = TicketStore(ctx.vault)
        for ticket in store.all(open_only=True):
            if ticket["scope"] == scope:
                store.close(ticket["id"], "core-recheck", "the person approved the sources and began the batch")
    if approved:
        _write_tickets(ctx, recheck)
    return {"approved": len(approved), "started": bool(begun.get("started")), "held": False,
            "sensitive": sensitive, "run": begun.get("run", ""), **({"refused": refused} if refused else {}),
            **({"detail": begun.get("detail")} if begun.get("detail") else {})}

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
