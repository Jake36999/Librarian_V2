"""Search the library's work, not only its notes (P5's deferral, built 2026-10-01): what
waits in staging, the research threads, and what was used or written in them.

The library search answers "what does the library hold?". This answers "where did I see
that?" - a staged source not yet accepted, the session that asked about it, the note it
wrote. Every query word must appear (accents and case folded, as in the library search);
results come back newest first, each saying where it matched."""
from __future__ import annotations

from typing import Any, Literal

from ..index import fold
from ..registry import Card, Context, tool
from ..search import terms_from
from ..session import SessionStore
from ..staging import StagingStore


def _hit(blob: str, words: list[str]) -> bool:
    text = fold(blob)
    return all(w in text for w in words)


def _staging(ctx: Context, words: list[str], limit: int) -> list[dict[str, Any]]:
    out = []
    for item in StagingStore(ctx.vault).items():
        draft = ((item.get("review") or {}).get("draft") or {})
        blob = " ".join(str(x) for x in (
            item.get("name"), item.get("title"), item.get("ref"), item.get("note"),
            item.get("topic"), item.get("what_belongs"), draft.get("bottom_line"),
            (item.get("fields") or {}).get("description"), item.get("canonical_url")) if x)
        if _hit(blob, words):
            out.append({"kind": item["kind"], "id": item["id"], "name": item.get("name", ""),
                        "status": item["status"],
                        "when": item.get("captured_at") or item.get("queued_at") or
                        item.get("created_at", "")})
    return sorted(out, key=lambda r: str(r["when"]), reverse=True)[:limit]


def _sessions(ctx: Context, words: list[str], limit: int) -> list[dict[str, Any]]:
    store = SessionStore(ctx.vault)
    out = []
    for row in store.list():
        s = store.load(row["id"])
        blob = " ".join([s.question, s.project, s.purpose, s.summary, s.gaps,
                         *(b.need for b in s.briefs.values()),
                         *(str(t) for t in s.topics()),
                         *(m["text"] for m in s.messages)])
        if _hit(blob, words):
            out.append({"session": s.id, "purpose": s.purpose, "status": s.status,
                        "phase": s.phase, "question": s.question or s.project,
                        "when": s.opened_at})
    return sorted(out, key=lambda r: str(r["when"]), reverse=True)[:limit]


def _activity(ctx: Context, words: list[str], limit: int) -> list[dict[str, Any]]:
    store = SessionStore(ctx.vault)
    out = []
    for row in store.list():
        s = store.load(row["id"])
        events = [("used", u.get("source", ""), u.get("used_for", ""), u.get("t", ""))
                  for u in s.uses]
        events += [("wrote", w.get("path", ""), w.get("tool", ""), w.get("t", ""))
                   for w in s.writes]
        events += [(f"library {i.get('status', '')}", i.get("path") or i.get("source", ""),
                    i.get("source", ""), "") for i in s.library_items.values()]
        for what, target, detail, when in events:
            if target and _hit(f"{target} {detail}", words):
                out.append({"what": what, "target": target, "detail": detail,
                            "session": s.id, "when": when or s.opened_at})
    return sorted(out, key=lambda r: str(r["when"]), reverse=True)[:limit]


@tool("search_work", tier="consult", effect="read", returns=("scope", "results"),
      card=Card("Search what waits in staging, the research threads, or what was used and "
                "written in them", "you remember seeing something but not where: a staged "
                "source, a session that asked about it, a note it wrote",
                "Every word must match (accents and case aside); newest first"))
def search_work(ctx: Context, query: str,
                scope: Literal["staging", "sessions", "activity"] = "staging",
                limit: int = 20) -> dict:
    words = [fold(t) for t in terms_from(query)]
    if not words:
        raise TypeError("give at least one word to look for")
    finder = {"staging": _staging, "sessions": _sessions, "activity": _activity}[scope]
    results = finder(ctx, words, max(1, min(int(limit), 100)))
    return {"scope": scope, "query": query, "results": results}
