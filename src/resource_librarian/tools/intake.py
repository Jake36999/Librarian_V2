"""Intake: from a reference to a staged, described source."""
from __future__ import annotations

from .. import intake
from ..registry import Card, Context, tool
from ..session import SessionStore
from .library import engine_for
from .staging import clerk_endpoint


def _fetcher(ctx: Context) -> intake.Fetcher:
    return ctx.extras.get("fetcher") or intake.Fetcher()


@tool("ingest", tier="contribute", effect="write", open_world=True, idempotent=True,
      returns=("status", "item", "name", "detail", "screen", "ref"),
      card=Card("Fetch a source (GitHub repo, arXiv id, DOI, web page, or a file in Inbox/), "
                "record what came back as evidence, describe it and stage it",
                "you have found something worth cataloguing",
                "Inside a session, give the brief to screen it against that brief's need; "
                "the screen's verdict is recorded on the candidate, never on the source"))
def ingest(ctx: Context, ref: str, brief: str = "") -> dict:
    need, disqualifiers, found_by = "", [], {}
    if ctx.session:
        session = SessionStore(ctx.vault).load(ctx.session)
        found_by = {"session": session.id}
        if brief:
            if brief not in session.briefs:
                raise TypeError(f"no brief {brief!r}; briefs: {sorted(session.briefs)}")
            need = session.briefs[brief].need
            disqualifiers = session.briefs[brief].disqualifiers
            found_by["brief"] = brief
    result = intake.ingest(ctx.vault, engine_for(ctx), ref, endpoint=clerk_endpoint(ctx),
                           fetcher=_fetcher(ctx), need=need, disqualifiers=disqualifiers,
                           found_by=found_by)
    if ctx.session and result.name and result.status in ("staged", "already_held",
                                                         "screened_out"):
        store = SessionStore(ctx.vault)
        store.append(ctx.session, {"type": "candidate", "source": result.name, "brief": brief,
                                   "staged": result.item, "via": result.status})
        if result.status in ("staged", "already_held"):
            store.append(ctx.session, {"type": "library_item",
                "id": result.item or f"existing:{result.name}", "source": result.name,
                "status": result.status,
                "path": result.detail if result.status == "already_held" else "",
                "brief": brief})
        if result.status == "screened_out":
            store.append(ctx.session, {"type": "decision", "source": result.name,
                                       "disposition": "reject",
                                       "reason": f"screen: {result.screen.get('reason', '')} "
                                                 f"{result.screen.get('contradicts', '')}",
                                       "role": ""})
    return result.to_dict()


@tool("queue_source", tier="consult", effect="write",
      returns=("queued", "waiting"),
      card=Card("Log a reference for intake later, with why it matters",
                "you came across something worth cataloguing but are busy with other work"))
def queue_source(ctx: Context, ref: str, note: str = "") -> dict:
    return {"queued": intake.enqueue(ctx.vault, ref, note, ctx.session or ctx.tier),
            "waiting": len(intake.pending(ctx.vault))}


@tool("intake_run", tier="contribute", effect="write", open_world=True,
      returns=("processed", "results", "still_waiting"),
      card=Card("Ingest what is waiting in the queue", "the queue has items",
                "Bounded by `limit`; each outcome is reported"))
def intake_run(ctx: Context, limit: int = 10) -> dict:
    engine = engine_for(ctx)
    results = []
    for entry in intake.pending(ctx.vault)[:limit]:
        result = intake.ingest(ctx.vault, engine, entry["ref"], endpoint=clerk_endpoint(ctx),
                               fetcher=_fetcher(ctx))
        intake.mark_done(ctx.vault, entry["ref"], result.status)
        results.append(result.to_dict())
    return {"processed": len(results), "results": results,
            "still_waiting": len(intake.pending(ctx.vault))}
