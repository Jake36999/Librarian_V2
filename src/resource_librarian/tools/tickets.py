"""Tickets as tools (implementation plan M3; tickets.py).

A failure or misalignment is a ticket with an owner and a review date, not a code in one call's result
(as-is W-DOC-02). Agents read tickets and record what they tried or hand one on; closing a ticket is the
person's, or a recheck's, never the worker's own.
"""
from __future__ import annotations

from ..registry import Card, Context, tool
from ..tickets import OWNERS, TicketStore


def _who(ctx: Context) -> str:
    actor = ctx.extras.get("actor") if isinstance(ctx.extras.get("actor"), dict) else {}
    if actor.get("name"):
        return f"agent:{actor['name']}"
    return "person" if ctx.tier == "curate" and ctx.extras.get("caller_kind") == "person" else \
        str(ctx.extras.get("caller") or "agent")


@tool("tickets", tier="consult", effect="read", returns=("tickets",),
      card=Card("Open tickets: failures and misalignments, each with its class, owner, review date "
                "and history; past its review date a ticket shows under its next owner",
                "before repairing, or to see what is owed and by whom",
                "`all=true` includes closed tickets; `ticket_class` narrows to one class"))
def tickets(ctx: Context, all: bool = False, ticket_class: str = "") -> dict:
    rows = TicketStore(ctx.vault).all(open_only=not all)
    if ticket_class:
        rows = [r for r in rows if r["class"] == ticket_class]
    return {"tickets": rows}


@tool("ticket_note", tier="contribute", effect="write", scope="library",
      returns=("id", "owner", "history"),
      card=Card("Record what was tried or found on an open ticket, or hand it to its next owner",
                "after a repair attempt, a finding, or when the ticket belongs to someone else",
                f"handover_to is one of {', '.join(OWNERS)}; the handover is recorded on the ticket"))
def ticket_note(ctx: Context, ticket_id: str, text: str, handover_to: str = "") -> dict:
    try:
        return TicketStore(ctx.vault).note(ticket_id, _who(ctx), text, handover_to=handover_to)
    except (KeyError, ValueError) as exc:
        raise TypeError(str(exc).strip("'\"")) from exc


@tool("ticket_close", tier="curate", effect="write", scope="library",
      returns=("id", "status", "resolution"),
      card=Card("Close a ticket with its resolution",
                "the person has seen the repair or decided the ticket",
                "The person's: a worker never closes its own ticket (a recheck closes it in M4)"))
def ticket_close(ctx: Context, ticket_id: str, resolution: str) -> dict:
    try:
        return TicketStore(ctx.vault).close(ticket_id, "person", resolution)
    except (KeyError, ValueError) as exc:
        raise TypeError(str(exc).strip("'\"")) from exc
