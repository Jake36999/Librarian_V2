"""A paper graph's citation handle as research evidence (owner, 2026-11-20).

A paper in this library's Geo-Grapher paper graph is cited as `<graph-label>/doc:N`. That is its
`cite_as`, and the paper itself stays labelled third_party where it is. The same paper is also a
Source note in the library: the generated card the intake pipeline wrote from it, with the same
name as the graph's document title. A handle can therefore be put forward as a session candidate,
kept in Judge, and cited by an offering's claim. A claim's quote is verified against that Source
note with the ordinary checks: the card, its evidence, its document chunks and its full
conversion. Nothing about verification changes; the handle only says where in the graph the paper
lives.

The handle is resolved by one read of the graph (`paper_get_document`), made by the Core on its
own library's graph service. It is never a model call.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .rules import Refusal

HANDLE = re.compile(r"^(?P<graph>[A-Za-z0-9][\w.\-]{0,119})/(?P<doc>doc:\d+)$")
GET_DOCUMENT = "mcp__geo-grapher__paper_get_document"


def is_handle(value: Any) -> bool:
    return isinstance(value, str) and HANDLE.match(value.strip()) is not None


def resolve(ctx: Any, handle: str) -> dict[str, Any]:
    """`{handle, graph, doc, title, provenance, note}`: the graph's own document for a handle and the
    library's Source note of the same name (`note` is empty when the paper has none)."""
    from .registry import REGISTRY
    match = HANDLE.match(handle.strip())
    if match is None:
        raise TypeError(f"{handle!r} is not a graph citation; one reads '<graph-label>/doc:N'")
    if GET_DOCUMENT not in REGISTRY:
        raise Refusal("GRAPH_UNAVAILABLE", f"{handle}: this library's Geo-Grapher is not "
                      "connected, so the citation cannot be resolved")
    out = REGISTRY.get(GET_DOCUMENT).fn(ctx, graph_id=match["graph"],
                                         request={"title": match["doc"], "detail": "card"})
    body = out.get("content") if isinstance(out, dict) else None
    try:
        data = json.loads(body) if isinstance(body, str) else (out or {})
    except ValueError:
        data = {}
    doc = data.get("result") if isinstance(data.get("result"), dict) else {}
    if out.get("error") or out.get("is_error") or doc.get("error") or doc.get("id") != match["doc"]:
        raise TypeError(f"{handle!r} names no document in graph {match['graph']!r}: copy cite_as "
                        "exactly from a paper search or document result")
    title = str(doc.get("title") or "")
    from .tools.library import IndexGateway
    row = IndexGateway(ctx).run(lambda engine: engine.index.note_row(title)) if title else None
    return {"handle": f"{match['graph']}/{match['doc']}", "graph": match["graph"],
            "doc": match["doc"], "title": title,
            "provenance": str(doc.get("provenance") or data.get("provenance") or ""),
            "note": row["name"] if row is not None else ""}


def note_for(ctx: Any, handle: str) -> str:
    """The library's Source note for a handle, or a refusal that says why there is none."""
    found = resolve(ctx, handle)
    if not found["note"]:
        raise TypeError(f"{handle} ({found['title']!r}) has no Source note in this library yet, so "
                        "its text cannot be quoted: cite a paper that has one, or a person "
                        "accepts it from staging first")
    return found["note"]
