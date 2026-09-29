---
type: "about"
status: "active"
authority: "the plain-text fallback for Settings → MCP servers' skills-registry picker (ui/src/settings.ts, CURATED_SKILLS). Keep the two in sync by hand: this table is what a person reads before ever opening Settings; the picker is where they actually turn one on"
---

# Recommended MCP Servers

An MCP server gives the librarian's model reach outside the vault, through the permission
broker: every call still defaults to **Ask**, every result comes back marked untrusted, and
none can write to the vault directly (see `Co-work Roadmap.md §3`). Settings → **MCP servers**
turns one on in the open library with a single click - install, accept and enable here - for anything listed here.
Beneath the picker, a search box browses the official MCP Registry for anything not listed, and
a hand-add form covers anything neither one finds.

Installed once, enabled per library: a server's definition lives in this machine's own config,
not the vault, so it is installed once for you - but each library turns it on for itself, off
until it does (a history library and a software library choose their own tools). To add one with
the librarian's help, ask for an **add_capability** session: it reads the server's repository as
a source, proposes a pinned definition, and installs it here only when you say yes.

| Server | What it's for | Command | Notes |
| --- | --- | --- | --- |
| Semantic Scholar | Search papers, citations and authors - the literature gap section 1 names | `uvx s2-mcp-server==1.7.4` | No key needed to start; an optional `SEMANTIC_SCHOLAR_API_KEY` (free, semanticscholar.org/product/api) raises the rate limit |
| Playwright browser (microsoft/playwright-mcp, Apache-2.0) | Open and read web pages in a real headless browser - pages built by scripts that a plain fetch reads as empty | `npx -y @playwright/mcp@0.0.82 --headless --isolated` | No key. Reaches any site; `--isolated` keeps no cookies or logins between runs. What it reads is untrusted page text: keep a page by `ingest`-ing its address |
| Apify (apify/apify-mcp-server, MIT) | Web search and page fetching (`apify--rag-web-browser`, `apify--web-fetch`), plus thousands of ready-made scrapers | `npx -y @apify/actors-mcp-server@0.16.0` | Needs `APIFY_TOKEN` (free tier with monthly credit, apify.com). Scrapers spend that credit: allow `call-actor` per call, not always |

The librarian's own `web_search` tool covers plain search without any server: Brave
(`BRAVE_API_KEY`), Tavily (`TAVILY_API_KEY`) or a SearXNG instance (`searxng_url` under
`[search]`), and keyless OpenAlex and Wikipedia. The two above are for pages that need a real
browser, and for scraping.

Evaluated but not curated here, with why, in `Co-work Roadmap.md §3 · Evaluated servers`:
Orbit (team task management - shelved, needs OAuth this build doesn't have), Topos (code
structure - candidate, not yet added), ScholarMCP and paper-search-mcp-nodejs (scholarly search
alternatives - Semantic Scholar above was the stronger pick). Also evaluated 2026-09-28:
addyosmani/agent-skills (MIT) is not an MCP server but a set of engineering-workflow skills for
coding agents such as Claude Code - worth installing there, not here; LakshmanTurlapati/Review-Gate
is a Cursor-only rule and popup that keeps one request open for more prompts - not a gate on the
model's work, and no use outside Cursor.

Excluded outright, whatever a search turns up: filesystem or shell servers (the vault's own
tools already reach the filesystem, safely, through the broker - a generic one bypasses it) and
memory servers (the vault is the memory; a second one would fork it).
