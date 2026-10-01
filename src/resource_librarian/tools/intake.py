"""Intake: from a reference to a staged, described source."""
from __future__ import annotations

from .. import intake
from ..registry import Card, Context, tool
from ..session import SessionStore
from .library import engine_for
from .staging import clerk_endpoint


def _fetcher(ctx: Context) -> intake.Fetcher:
    return ctx.extras.get("fetcher") or intake.Fetcher()


def _attach(ctx: Context, session_id: str, brief: str, result: intake.IntakeResult) -> None:
    """A capture made for a session joins that session as an undecided candidate (and a
    library item): found for it, not yet judged by it."""
    if not (result.name and result.status in ("staged", "already_held", "screened_out")):
        return
    store = SessionStore(ctx.vault)
    store.append(session_id, {"type": "candidate", "source": result.name, "brief": brief,
                              "staged": result.item, "via": result.status})
    if result.status == "screened_out":
        store.append(session_id, {"type": "decision", "source": result.name,
                                  "disposition": "reject",
                                  "reason": f"screen: {result.screen.get('reason', '')} "
                                            f"{result.screen.get('contradicts', '')}",
                                  "role": ""})
    else:
        store.append(session_id, {"type": "library_item",
            "id": result.item or f"existing:{result.name}", "source": result.name,
            "status": result.status,
            "path": result.detail if result.status == "already_held" else "",
            "brief": brief})


# Addendum R12: capture is allowed in any phase - only a fit claim needs a framed need, and
# that comes from the brief, when one is given. `defer` queues instead of fetching now.
@tool("ingest", tier="contribute", effect="write", scope="session", open_world=True,
      idempotent=True, resolve={"brief": "brief"},
      returns=("status", "state", "next", "item", "name", "detail", "screen", "quality"),
      card=Card("Fetch a source (GitHub repo, arXiv id, DOI, dataset or web page, or a file "
                "in Inbox/), record what came back as evidence, check what was really read, "
                "describe it and stage it", "you have found something worth cataloguing",
                "Any phase, and no brief is needed to capture: leave `brief` out unless one is "
                "open. `brief` is its ID as open_brief returned it - brief='B1' - never its "
                "sentence; with it, the find is screened against that brief's need (the "
                "verdict kept apart from the description). defer=true only queues it. The "
                "result says the state it reached and what comes next"))
def ingest(ctx: Context, ref: str, brief: str = "", defer: bool = False,
           note: str = "") -> dict:
    if defer:
        return _queue(ctx, ref, note, brief)
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
    if ctx.session:
        _attach(ctx, ctx.session, brief, result)
    out = result.to_dict()
    if result.status in ("quarantined", "error"):
        # one lifecycle (R7): a capture that failed is visible and can be retried
        queued = intake.enqueue(ctx.vault, ref, "", ctx.session or ctx.tier,
                                session=ctx.session or "", brief=brief)
        out["queue"] = intake.settle(ctx.vault, queued["id"], result)
        out["item"] = queued["id"]
    return out


def _queue(ctx: Context, ref: str, note: str, brief: str) -> dict:
    if brief:
        if not ctx.session:
            raise TypeError("a brief belongs to a session: queue without one outside a session")
        if brief not in SessionStore(ctx.vault).load(ctx.session).briefs:
            raise TypeError(f"no brief {brief!r} in this session")
    queued = intake.enqueue(ctx.vault, ref, note, ctx.session or ctx.tier,
                            session=ctx.session or "", brief=brief)
    return {"status": "queued", "state": "queued", "item": queued["id"],
            "next": "intake_run captures it (the run-queue action)", "queued": queued,
            "waiting": len(intake.pending(ctx.vault))}


@tool("queue_source", tier="consult", effect="write", scope="session",
      resolve={"brief": "brief"}, returns=("queued", "waiting"),
      card=Card("Log a reference for intake later, with why it matters (the same as "
                "ingest with defer=true, for a reader)",
                "you came across something worth cataloguing but are busy with other work",
                "Inside a session the session (and the brief, if given) is kept with it, so "
                "intake_run screens it against that brief and adds it to the session"))
def queue_source(ctx: Context, ref: str, note: str = "", brief: str = "") -> dict:
    return _queue(ctx, ref, note, brief)


def _framing(ctx: Context, entry: dict) -> tuple[str, str, list[str], dict, str]:
    """The session, need and disqualifiers a queued reference was found for, if its
    session and brief are still open; otherwise why it is captured unframed."""
    found_for = entry.get("found_for") or {}
    session_id, brief = found_for.get("session", ""), found_for.get("brief", "")
    if not session_id:
        return "", "", [], {}, "unframed: queued outside a session"
    try:
        session = SessionStore(ctx.vault).load(session_id)
    except (TypeError, OSError, KeyError):
        return "", "", [], {}, f"unframed: session {session_id} no longer exists"
    if session.status == "closed":
        return "", "", [], {}, f"unframed: session {session_id} is closed"
    if not brief:
        return session_id, "", [], {"session": session_id}, f"for session {session_id}"
    b = session.briefs.get(brief)
    if b is None or b.status != "open":
        return session_id, "", [], {"session": session_id}, \
            f"for session {session_id}; brief {brief} is closed, so not screened"
    return session_id, b.need, list(b.disqualifiers), \
        {"session": session_id, "brief": brief}, f"framed by {session_id}/{brief}"


@tool("intake_run", tier="contribute", effect="write", scope="session", open_world=True,
      returns=("processed", "results", "still_waiting"),
      card=Card("Capture what is waiting in the queue", "the queue has items",
                "Bounded by `limit`. Each reference is screened against the brief it was "
                "queued for while that brief is open, and joins its session as an undecided "
                "candidate; each outcome says where the reference went"))
def intake_run(ctx: Context, limit: int = 10) -> dict:
    engine = engine_for(ctx)
    results = []
    for entry in intake.pending(ctx.vault)[:limit]:
        session_id, need, disqualifiers, found_by, framing = _framing(ctx, entry)
        result = intake.ingest(ctx.vault, engine, entry["ref"], endpoint=clerk_endpoint(ctx),
                               fetcher=_fetcher(ctx), need=need, disqualifiers=disqualifiers,
                               found_by=found_by)
        settled = intake.settle(ctx.vault, entry["id"], result)
        if session_id:
            _attach(ctx, session_id, found_by.get("brief", ""), result)
        results.append({**result.to_dict(), "framing": framing, "queue": settled})
    return {"processed": len(results), "results": results,
            "still_waiting": len(intake.pending(ctx.vault))}


@tool("queue_list", tier="consult", effect="read", returns=("queued", "failed"),
      card=Card("What waits in the intake queue, and captures that failed, with who asked "
                "and why", "before intake_run, or to find a failed capture to retry"))
def queue_list(ctx: Context, limit: int = 50) -> dict:
    def row(i: dict) -> dict:
        return {k: i[k] for k in ("id", "ref", "note", "requested_by", "found_for",
                                  "queued_at", "failure") if i.get(k)}
    return {"queued": [row(i) for i in intake.pending(ctx.vault)[:limit]],
            "failed": [row(i) for i in intake.pending(ctx.vault, "failed")[:limit]]}


@tool("queue_remove", tier="contribute", effect="write", scope="session",
      returns=("removed",),
      card=Card("Take references out of the intake queue, with the reason",
                "a queued or failed reference is no longer wanted",
                "Nothing is deleted: it goes to quarantine with the reason"))
def queue_remove(ctx: Context, item_ids: list[str], reason: str) -> dict:
    if not reason.strip():
        raise TypeError("say why it is removed")
    out = []
    for item_id in item_ids:
        try:
            intake.remove(ctx.vault, item_id, reason)
            out.append({"id": item_id, "status": "removed"})
        except TypeError as exc:
            out.append({"id": item_id, "error": str(exc)})
    return {"removed": sum(1 for r in out if r.get("status") == "removed"), "results": out}


@tool("queue_retry", tier="contribute", effect="write", scope="session",
      returns=("requeued",),
      card=Card("Put failed captures back in the intake queue",
                "a capture failed for a reason that has since been fixed (network, a moved "
                "file)"))
def queue_retry(ctx: Context, item_ids: list[str]) -> dict:
    out = []
    for item_id in item_ids:
        try:
            intake.retry(ctx.vault, item_id)
            out.append({"id": item_id, "status": "queued"})
        except TypeError as exc:
            out.append({"id": item_id, "error": str(exc)})
    return {"requeued": sum(1 for r in out if r.get("status") == "queued"), "results": out}
