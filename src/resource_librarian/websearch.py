"""Searching the open web, so the librarian is not limited to what it already
holds (2026-09-28: a course library could find nothing on Thunkable or Agile,
because its only outside search was GitHub and arXiv).

Backends, tried in this order for `kind="web"`:

- **Brave Search** with `BRAVE_API_KEY`, or **Tavily** with `TAVILY_API_KEY`
  (both have free tiers), or a **SearXNG** instance the person runs, named by
  `searxng_url` under `[search]` in the library's config;
- with none of those, **Wikipedia**, keyless - enough to get started, and
  every result says which backend it came from.

`kind="scholarly"` asks **OpenAlex** (keyless, papers and books across fields);
`kind="encyclopedia"` asks Wikipedia.

A result is a candidate, never evidence: a title, a link and the snippet the
search engine chose. Keeping one means `ingest(url)`, which fetches the page
itself and records it as evidence like any other source. Nothing here is
framed by a need or session (DATA_IS_UNFRAMED): only the query goes out.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .intake import USER_AGENT, FetchError, Fetcher
from .vault import Vault

KINDS = ("web", "scholarly", "encyclopedia")
TIMEOUT = 20


def _clean(text: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", str(text or "")).split())[:400]


def _post_json(url: str, payload: dict[str, Any]) -> Any:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise FetchError(f"{url}: {exc}") from exc


def _get_json(fetcher: Fetcher, url: str, headers: dict[str, str] | None = None) -> Any:
    if headers:                                  # a keyed API: its own header, not the Fetcher's
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                       "Accept": "application/json", **headers})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise FetchError(f"{url.split('?')[0]}: {exc}") from exc
    return json.loads(fetcher.get(url, "application/json"))


def _brave(query: str, limit: int, fetcher: Fetcher) -> list[dict[str, str]]:
    url = "https://api.search.brave.com/res/v1/web/search?" + urllib.parse.urlencode(
        {"q": query, "count": limit})
    data = _get_json(fetcher, url, {"X-Subscription-Token": os.environ["BRAVE_API_KEY"]})
    return [{"url": r.get("url", ""), "title": _clean(r.get("title")),
             "snippet": _clean(r.get("description"))}
            for r in (data.get("web") or {}).get("results", [])]


def _tavily(query: str, limit: int, fetcher: Fetcher) -> list[dict[str, str]]:
    data = _post_json("https://api.tavily.com/search", {
        "api_key": os.environ["TAVILY_API_KEY"], "query": query, "max_results": limit})
    return [{"url": r.get("url", ""), "title": _clean(r.get("title")),
             "snippet": _clean(r.get("content"))} for r in data.get("results", [])]


def _searxng(base: str, query: str, limit: int, fetcher: Fetcher) -> list[dict[str, str]]:
    url = base.rstrip("/") + "/search?" + urllib.parse.urlencode({"q": query, "format": "json"})
    data = _get_json(fetcher, url)
    return [{"url": r.get("url", ""), "title": _clean(r.get("title")),
             "snippet": _clean(r.get("content"))} for r in data.get("results", [])[:limit]]


def _wikipedia(query: str, limit: int, fetcher: Fetcher) -> list[dict[str, str]]:
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "list": "search", "srsearch": query, "srlimit": limit,
        "format": "json"})
    data = _get_json(fetcher, url)
    return [{"url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(
                r["title"].replace(" ", "_")),
             "title": r["title"], "snippet": _clean(r.get("snippet"))}
            for r in (data.get("query") or {}).get("search", [])]


def _openalex(query: str, limit: int, fetcher: Fetcher) -> list[dict[str, str]]:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
        "search": query, "per-page": limit})
    data = _get_json(fetcher, url)
    out = []
    for w in data.get("results", []):
        doi = str(w.get("doi") or "")
        location = (w.get("primary_location") or {}).get("landing_page_url") or ""
        year = w.get("publication_year") or ""
        venue = ((w.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
        out.append({"url": doi or location or str(w.get("id") or ""),
                    "title": _clean(w.get("display_name")),
                    "snippet": _clean(f"{year} {venue} - cited by {w.get('cited_by_count', 0)}")})
    return out


def backend(vault: Vault | None) -> str:
    """Which web backend a `kind="web"` search uses here."""
    if os.environ.get("BRAVE_API_KEY"):
        return "brave"
    if os.environ.get("TAVILY_API_KEY"):
        return "tavily"
    if vault is not None and str((vault.config().get("search") or {}).get("searxng_url") or ""):
        return "searxng"
    return "wikipedia"


def search(query: str, kind: str = "web", limit: int = 8, *, vault: Vault | None = None,
           fetcher: Fetcher | None = None) -> dict[str, Any]:
    """`{"backend", "results": [{url, title, snippet}], "note"?}`. Raises
    FetchError when the backend cannot be reached."""
    if kind not in KINDS:
        raise ValueError(f"kind is one of {', '.join(KINDS)}")
    query = " ".join(str(query or "").split())[:300]
    if not query:
        raise ValueError("an empty query")
    fetcher = fetcher or Fetcher()
    limit = max(1, min(int(limit), 20))
    if kind == "scholarly":
        name, results = "openalex", _openalex(query, limit, fetcher)
    elif kind == "encyclopedia":
        name, results = "wikipedia", _wikipedia(query, limit, fetcher)
    else:
        name = backend(vault)
        if name == "brave":
            results = _brave(query, limit, fetcher)
        elif name == "tavily":
            results = _tavily(query, limit, fetcher)
        elif name == "searxng":
            results = _searxng(str(vault.config()["search"]["searxng_url"]), query, limit, fetcher)
        else:
            results = _wikipedia(query, limit, fetcher)
    out: dict[str, Any] = {"backend": name,
                           "results": [r for r in results if r["url"]][:limit]}
    if kind == "web" and name == "wikipedia":
        out["note"] = ("no web search backend is set up, so this searched Wikipedia only: set "
                       "BRAVE_API_KEY or TAVILY_API_KEY, or searxng_url under [search], for the "
                       "open web")
    return out
