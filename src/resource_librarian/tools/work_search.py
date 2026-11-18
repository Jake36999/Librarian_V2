"""Search the library's work, not only its notes (P5's deferral, built 2026-10-01): what
waits in staging, the research threads, and what was used or written in them.

The library search answers "what does the library hold?". This answers "where did I see
that?" - a staged source not yet accepted, the session that asked about it, the note it
wrote. Accents and case are folded, as in the library search. A result matches at least two
thirds of the query's words (all of a one- or two-word query); more matched words come first,
then newest; each says how many it matched. A staged source is searched through its reading
too: the points and limits its deep read recorded, its sections and its draft (2026-11-18:
three rare words from a read claim found 0-10% of staged sources, because only titles and
the bottom line were searched and every word had to match)."""
from __future__ import annotations

from typing import Any, Literal

from ..index import fold
from ..registry import Card, Context, tool
from ..search import terms_from
from ..session import SessionStore
from ..staging import StagingStore


def _matched(blob: str, words: list[str]) -> int:
    """How many of the words the text holds, or 0 below the two-thirds floor."""
    text = fold(blob)
    found = sum(1 for w in words if w in text)
    return found if found >= max(1, -(-2 * len(words) // 3)) else 0


def _reading(item: dict[str, Any]) -> list[str]:
    """The text a staged source's reading recorded: points and limits per read part, and
    the drafted sections."""
    out: list[str] = []
    for part in ((item.get("deep_read") or {}).get("read") or {}).values():
        for key in ("points", "limits"):
            out += [str(x) for x in (part.get(key) or []) if isinstance(x, str)]
    for body in (item.get("sections") or {}).values():
        out += [str(x) for x in body] if isinstance(body, list) else [str(body)]
    return out


def _ranked(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    rows = sorted(rows, key=lambda r: str(r["when"]), reverse=True)
    return sorted(rows, key=lambda r: -r["matched"])[:limit]


def _staging(ctx: Context, words: list[str], limit: int) -> list[dict[str, Any]]:
    out = []
    for item in StagingStore(ctx.vault).items():
        draft = ((item.get("review") or {}).get("draft") or {})
        blob = " ".join(str(x) for x in (
            item.get("name"), item.get("title"), item.get("ref"), item.get("note"),
            item.get("topic"), item.get("what_belongs"), draft.get("bottom_line"),
            (item.get("fields") or {}).get("description"), item.get("canonical_url"),
            draft.get("what_it_solves"), *_reading(item)) if x)
        matched = _matched(blob, words)
        if matched:
            out.append({"kind": item["kind"], "id": item["id"], "name": item.get("name", ""),
                        "status": item["status"], "matched": matched, "of": len(words),
                        "when": item.get("captured_at") or item.get("queued_at") or
                        item.get("created_at", "")})
    return _ranked(out, limit)


def _sessions(ctx: Context, words: list[str], limit: int) -> list[dict[str, Any]]:
    store = SessionStore(ctx.vault)
    out = []
    for row in store.list():
        s = store.load(row["id"])
        blob = " ".join([s.question, s.project, s.purpose, s.summary, s.gaps,
                         *(b.need for b in s.briefs.values()),
                         *(str(t) for t in s.topics()),
                         *(m["text"] for m in s.messages)])
        matched = _matched(blob, words)
        if matched:
            out.append({"session": s.id, "purpose": s.purpose, "status": s.status,
                        "phase": s.phase, "question": s.question or s.project,
                        "matched": matched, "of": len(words), "when": s.opened_at})
    return _ranked(out, limit)


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
            matched = _matched(f"{target} {detail}", words) if target else 0
            if matched:
                out.append({"what": what, "target": target, "detail": detail,
                            "session": s.id, "matched": matched, "of": len(words),
                            "when": when or s.opened_at})
    return _ranked(out, limit)


@tool("search_work", tier="consult", effect="read", returns=("scope", "results"),
      card=Card("Search what waits in staging, the research threads, or what was used and "
                "written in them", "you remember seeing something but not where: a staged "
                "source, a session that asked about it, a note it wrote",
                "At least two thirds of the words must match (all of one or two); most "
                "matched first, then newest; a staged source is searched through its reading"))
def search_work(ctx: Context, query: str,
                scope: Literal["staging", "sessions", "activity"] = "staging",
                limit: int = 20) -> dict:
    words = [fold(t) for t in terms_from(query)]
    if not words:
        raise TypeError("give at least one word to look for")
    finder = {"staging": _staging, "sessions": _sessions, "activity": _activity}[scope]
    results = finder(ctx, words, max(1, min(int(limit), 100)))
    return {"scope": scope, "query": query, "results": results}
