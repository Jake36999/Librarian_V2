"""The open web as a place to look (websearch.py). A result is a candidate:
`ingest(url)` is what keeps one."""
from __future__ import annotations

from typing import Literal

from .. import websearch
from ..intake import FetchError
from ..registry import Card, Context, tool
from .intake import _fetcher


@tool("web_search", tier="consult", effect="read", open_world=True,
      returns=("backend", "results", "note"),
      card=Card("Search the open web (or scholarly works, or an encyclopedia) for sources the "
                "library does not hold yet",
                "the vault holds nothing, or too little, on what is needed: course pages, "
                "product documentation, tutorials, papers, reference articles",
                "Results are candidates, not evidence: titles, links and the engine's own "
                "snippets. ingest(url) what is worth keeping - it is fetched and recorded then. "
                "kind: web (Brave, Tavily or SearXNG when set up, else Wikipedia), scholarly "
                "(OpenAlex), encyclopedia (Wikipedia)"))
def web_search(ctx: Context, query: str, kind: Literal["web", "scholarly", "encyclopedia"] = "web",
               limit: int = 8) -> dict:
    try:
        return websearch.search(query, kind, limit, vault=ctx.vault, fetcher=_fetcher(ctx))
    except FetchError as exc:
        return {"backend": websearch.backend(ctx.vault) if kind == "web" else kind,
                "results": [], "note": f"the search could not be reached: {exc}"}
