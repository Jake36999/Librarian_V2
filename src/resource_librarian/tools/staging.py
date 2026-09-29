"""Staging review: the airlock, and the lens store the app reads."""
from __future__ import annotations

import re
from typing import Literal

from .. import clerk, concepts, notes, staging
from .. import deep_read as reading
from ..lenses import LensStore
from ..registry import Card, Context, tool
from ..vault import now_iso
from .library import engine_for


def _store(ctx: Context) -> staging.StagingStore:
    return staging.StagingStore(ctx.vault)


def clerk_endpoint(ctx: Context) -> clerk.Endpoint | None:
    """The surface's endpoint, else the vault's configured one, else the
    surface's fallback (MCP sampling), else None and the tasks queue."""
    endpoint = ctx.extras.get("clerk")
    if endpoint is None:
        endpoint = clerk.from_config(ctx.vault.config().get("clerk") or {})
    if endpoint is None:
        endpoint = ctx.extras.get("clerk_fallback")
    return endpoint


def scribe_endpoint(ctx: Context) -> clerk.Endpoint | None:
    """Tier 2: the surface's scribe, else `[scribe]` in config, else the
    surface's fallback (the loop's own model in a fresh call, or MCP sampling)."""
    endpoint = ctx.extras.get("scribe")
    if endpoint is None:
        try:
            endpoint = clerk.from_config(ctx.vault.config().get("scribe") or {})
        except clerk.ClerkUnavailable:
            endpoint = None
    if endpoint is None:
        endpoint = ctx.extras.get("scribe_fallback") or ctx.extras.get("clerk_fallback")
    return endpoint


@tool("staging_list", tier="consult", effect="read",
      returns=("counts", "total", "items"),
      card=Card("What waits in staging: counts, and a page of items",
                "reviewing the airlock", "Sensitive items are marked"))
def staging_list(ctx: Context, kind: Literal["", "source", "lens", "concept"] = "",
                 status: Literal["", "staged", "deferred", "accepted"] = "staged",
                 limit: int = 25, offset: int = 0) -> dict:
    store = _store(ctx)
    rows = [staging.summary(i) for i in store.items(kind, status)]
    return {"counts": store.counts(), "total": len(rows),
            "items": rows[offset:offset + limit]}


@tool("staging_show", tier="consult", effect="read",
      card=Card("One staged item in full, with its evidence and any review",
                "deciding an item"))
def staging_show(ctx: Context, item_id: str) -> dict:
    return staging.show(_store(ctx).load(item_id))


@tool("staging_review", tier="contribute", effect="write", open_world=True,
      returns=("id", "draft", "reviewed_at"),
      card=Card("Assisted review: an unframed Bottom Line draft from the evidence alone, "
                "a sensitivity check, and (given a need) a framed fit judgement with its "
                "quote shown in context", "before deciding a source",
                "Runs on the clerk channel; with no clerk configured the tasks are queued"))
def staging_review(ctx: Context, item_id: str, need: str = "",
                   disqualifiers: list[str] | None = None) -> dict:
    return staging.review(_store(ctx), item_id, clerk_endpoint(ctx), need, disqualifiers)


@tool("deep_read", tier="contribute", effect="write", open_world=True,
      returns=("chunks", "read", "remaining", "lenses_staged"),
      card=Card("Read a staged source's whole text chunk by chunk: its claims and limits with "
                "the pages they came from, its terms, and any reasoning stance it teaches "
                "(staged as a lens)",
                "a staged document, paper or page is worth more than its opening window; "
                "before accepting it",
                "Bounded by max_chunks per call and resumable: call again to carry on. Runs on "
                "the clerk channel; with no clerk configured the tasks are queued"))
def deep_read_tool(ctx: Context, item_id: str, max_chunks: int = reading.MAX_CHUNKS,
                   lenses: bool = True) -> dict:
    kind = _store(ctx).load(item_id).get("source_kind", "")
    sections = dict(engine_for(ctx, refresh=False).index.model.sections_for("source", kind))
    return reading.deep_read(ctx.vault, item_id, clerk_endpoint(ctx), max_chunks=max_chunks,
                             lenses=lenses, sections_of=sections)


@tool("deep_read_note", tier="contribute", effect="write", open_world=True,
      returns=("revision", "chunks", "read", "remaining", "lenses_staged"),
      card=Card("Deep-read a source that is already accepted: its whole text, staged as a "
                "revision of its note",
                "an accepted source was only skimmed at intake, or its text is worth reading "
                "in full now",
                "Never rewrites the note: the claims and limits it finds, with pages, wait in "
                "Staging as a revision a person merges; lenses are staged as usual. Resumable"))
def deep_read_note(ctx: Context, note: str, max_chunks: int = reading.MAX_CHUNKS,
                   lenses: bool = True) -> dict:
    engine = engine_for(ctx)
    row = engine.index.note_row(note)
    if row is None or row["shape"] != "source":
        raise TypeError(f"no accepted source named {note!r}; names are exact")
    loaded = notes.load(ctx.vault.root / row["path"])
    fm = loaded.frontmatter
    store = _store(ctx)
    open_revision = next((i for i in store.items(kind="source")
                          if i.get("revision_of") == row["path"]
                          and i.get("status") in ("staged", "deferred")), None)
    if open_revision is None:
        slug = re.sub(r"[^a-z0-9]+", "-", row["name"].lower()).strip("-")[:50] or "source"
        open_revision = store.add({
            "id": f"revision-{slug}-{now_iso()[:10]}", "kind": "source",
            "name": row["name"], "title": fm.get("title", row["name"]),
            "source_kind": fm.get("kind", "document"), "revision_of": row["path"],
            "canonical_url": fm.get("canonical_url", ""),
            **({"file": fm["file"]} if fm.get("file") else {}),
            "evidence": [{"id": e} for e in fm.get("evidence") or [] if isinstance(e, str)],
            "sensitivity": str(fm.get("sensitivity") or "normal"), "sections": {}})
    kind = open_revision.get("source_kind", "")
    sections = dict(engine.index.model.sections_for("source", kind))
    out = reading.deep_read(ctx.vault, open_revision["id"], clerk_endpoint(ctx),
                            max_chunks=max_chunks, lenses=lenses, sections_of=sections)
    return {"revision": open_revision["id"], "of": row["path"], **out}


@tool("staging_decide", tier="contribute", effect="vault_write",
      returns=("results", "accepted", "not_findable", "refused"),
      card=Card("Accept, reject or defer staged items, one or a batch",
                "an item has been reviewed",
                "Accepting a source runs the six-step promotion and reports whether it is "
                "findable. Under promotion.mode 'person', and for anything sensitive, only a "
                "person accepts. Rejections go to quarantine with their reason"))
def staging_decide(ctx: Context, item_ids: list[str],
                   decision: Literal["accept", "reject", "defer"], reason: str = "",
                   bottom_line: str = "", what_it_solves: str = "",
                   fields: dict | None = None) -> dict:
    results = staging.decide(_store(ctx), engine_for(ctx), item_ids, decision, reason,
                             bottom_line, what_it_solves,
                             decided_by="person" if ctx.tier == "curate" else "agent",
                             session=ctx.session or "", fields=fields)
    return {"results": results,
            "accepted": sum(1 for r in results if r.get("status") == "accepted"),
            "not_findable": [r["id"] for r in results if r.get("promotion")
                             and not r["promotion"]["catalogued"]],
            "refused": sum(1 for r in results if "refused" in r or "error" in r)}


@tool("staging_flag", tier="contribute", effect="write",
      returns=("id", "sensitivity"),
      card=Card("Mark a staged item sensitive (or clear the mark, as a person)",
                "an item is dual-use: offensive security, surveillance"))
def staging_flag(ctx: Context, item_id: str, sensitive: bool = True, reason: str = "") -> dict:
    store = _store(ctx)
    item = store.load(item_id)
    if not sensitive and ctx.tier != "curate":
        raise TypeError("only a person clears a sensitivity mark")
    item["sensitivity"] = "review" if sensitive else "normal"
    item.setdefault("history", []).append({"flag": item["sensitivity"], "reason": reason,
                                           "by": ctx.tier})
    store.save(item)
    return {"id": item_id, "sensitivity": item["sensitivity"]}


@tool("lens_list", tier="consult", effect="read",
      card=Card("Accepted lenses: reasoning stances drawn from sources",
                "you want a way of looking at a problem that a source teaches"))
def lens_list(ctx: Context, query: str = "", limit: int = 25) -> dict:
    store = LensStore(ctx.vault)
    return {"total": store.count(), "lenses": store.list(query, limit),
            "concentration": store.concentration()}


@tool("lens_show", tier="consult", effect="read",
      card=Card("One accepted lens in full, with the passage it was drawn from",
                "adopting a lens"))
def lens_show(ctx: Context, lens_id: str) -> dict:
    lens = LensStore(ctx.vault).get(lens_id)
    return lens or {"found": False, "lens_id": lens_id}


@tool("concept_candidates", tier="contribute", effect="write",
      returns=("scanned", "staged"),
      card=Card("Scan recorded term usages and stage a concept candidate for each term "
                "seen across several sources",
                "building the glossary; re-running never restages a decided term",
                "Nothing is drafted from thin air: only the term's own quoted usages are "
                "staged. A person's own words become the Definition on accept"))
def concept_candidates(ctx: Context, min_sources: int = concepts.MIN_SOURCES) -> dict:
    return concepts.candidates(ctx.vault, min_sources)


# -- the clerk agent route -----------------------------------------------------

@tool("clerk_next", tier="contribute", effect="read", sessionless=True,
      returns=("waiting",),
      card=Card("The next waiting clerk task: one question, one text, one answer shape",
                "you are the clerk agent, and only then",
                "Never call this from a research conversation: a clerk answer must not "
                "see the thread's framing. It runs outside any session"))
def clerk_next(ctx: Context) -> dict:
    task = clerk.next_task(ctx.vault.work("queue") / "clerk")
    return task or {"waiting": 0}


@tool("clerk_submit", tier="contribute", effect="write", sessionless=True,
      returns=("accepted",),
      card=Card("Submit the clerk agent's answer to one waiting task",
                "you are the clerk agent and have answered the task from its text alone",
                "The answer is checked for shape now, and for grounding when the owning "
                "review next runs"))
def clerk_submit(ctx: Context, key: str, answer: dict) -> dict:
    return clerk.submit(ctx.vault.work("queue") / "clerk", key, answer, by="clerk-agent")
