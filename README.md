# Librarian

A personal research library you can actually talk to.

Librarian is a tool for people who read seriously. You give it sources — papers, repositories, books, articles — and it indexes them into a structured vault. You can then search, consult, and build on what you've read through a chat interface backed by whatever language model you choose. It does not summarise the web or hallucinate citations; it works from what you have actually read and ingested.

---

## What it does

- **Vaults** hold your sources as structured notes — one note per source, with evidence, concepts, patterns and your own assessments of them.
- **Search** finds sources by meaning, intent, or constraint (license, language, domain).
- **Chat** lets you ask questions, run research sessions and build new outputs (reports, project plans, offering notes) from what the vault holds.
- **Sessions** give the model a structured walk: open a thread with a purpose, move through phases (frame → search → synthesise), write a staged draft, promote it to the vault. Every step is gated so the model can only write what the current phase allows.
- **Intake** ingests new sources from the web, from files in your Inbox, or from PDFs you drop in.
- **Lenses** let the vault teach the model how to reason — see below.
- **Obsidian** reads and writes the same vault: the notes are plain Markdown with YAML frontmatter, so the whole vault opens natively in Obsidian with bi-directional compatibility.

---

## Install

Requires Python 3.11+.

### Windows: Setup.bat

Double-click **`Setup.bat`** in this folder. It sets up this copy in one go:

- a Python environment of its own (`.venv` here), so this copy runs its own code;
- the Librarian, with the MCP server, PDF text and semantic search;
- a check that it starts;
- a desktop shortcut, **Librarian**, that opens the library picker.

It is safe to run again, for example after updating. The options pass through:

```bat
Setup.bat -Extras "mcp,pdf,embed,dev"    REM also the test suite
Setup.bat -NoShortcut                    REM no desktop shortcut
Setup.bat -BuildUI                       REM rebuild the interface from ui\src (needs Node.js)
```

### The library picker

The shortcut opens a page before any library, like Obsidian's vault picker. From it
you can:

- open a library you have opened before;
- **create a new library**, by name and place, optionally with a domain profile
  (software systems, a course, history);
- **open a folder as a library**. A folder inside a library opens that library. Any
  other folder becomes a library only if you agree, and only what is missing is
  added: nothing already in it changes;
- forget a library from the list. The folder itself is left alone.

`Librarian.bat --pick` opens the same page. `Librarian.bat` on its own opens the library
at or above the folder it runs in, or the picker if there is none. Its window is the
Librarian's server: closing it stops the Librarian.

### By hand (any platform)

```bash
pip install -e ".[dev]"          # full install including test suite
pip install -e ".[mcp]"          # add MCP server support
pip install -e ".[embed]"        # add semantic embedding for richer search
pip install -e ".[pdf]"          # add PDF extraction
```

Create a library and open the app, or start at the picker:

```bash
resource-librarian init ~/MyResearch --profile software-systems
resource-librarian --vault ~/MyResearch app --open
resource-librarian app --pick --open
```

On Windows, `scripts/new-vault.ps1` opens or creates a domain library from inside a
project folder, and registers the project in it:

```powershell
.\scripts\new-vault.ps1 -Domain Software -Profile software-systems
.\scripts\new-vault.ps1          # a one-off library at .\.librarian-app
```

---

## Services

### Web app

The main interface: a chat panel, a staging panel (review and accept drafted sources), and a search panel. Served locally on `127.0.0.1`.

```bash
resource-librarian --vault ~/MyResearch app --open
```

No Node or build step needed — the front end ships pre-built inside the package. Source is in `ui/` (TypeScript, no framework) if you want to modify it.

**Vault selection:** If you run `resource-librarian app` without specifying a vault, a library-picker page opens in the browser listing your previously opened vaults.

### CLI

Every registered tool is also a CLI subcommand. Output is JSON by default (`--text` gives a human summary where available).

```bash
resource-librarian --vault ~/MyResearch search --query "parse SQL lineage"
resource-librarian --vault ~/MyResearch get_note --name "apache - airflow"
resource-librarian --vault ~/MyResearch ingest --url "https://github.com/..."
resource-librarian --vault ~/MyResearch doctor   # vault health check
```

### MCP server

Exposes the same tool registry over the Model Context Protocol (stdio), so any MCP-compatible host (Claude Code, Cursor, etc.) can use it as a research tool.

```bash
resource-librarian --vault ~/MyResearch mcp                    # consult tier (read-only)
resource-librarian --vault ~/MyResearch mcp --tier contribute  # contribute tier (sessions + writes)
```

### Obsidian plugin

`obsidian/` contains a plugin that embeds the Librarian chat panel directly inside Obsidian. The plugin starts the core process and communicates with it over a local port, so the vault you have open in Obsidian is the one the chat uses.

Build: `cd obsidian && npm install && npm run build`, then copy `dist/` to your vault's `.obsidian/plugins/librarian/`.

### Claude Code cowork plugin

`plugin/` is a Cowork plugin (skills and commands) for Claude Code. It gives Claude Code a set of slash commands (`/research`, `/new-project`, `/resume`, etc.) and a `clerk` agent that runs inside a research session, handling description tasks (note writing, synthesis drafts) independently of the main chat model.

---

## Models and providers

Librarian uses the OpenAI-compatible chat API, so the same code path works across every provider that speaks it. Three model tiers are independently configurable:

| Tier | Role | Recommended |
|------|------|-------------|
| Tier 1 (lead) | Runs research sessions, chat | Any capable chat model |
| Tier 2 (scribe) | Writes source notes and drafts | Mid-size, instruction-following |
| Tier 3 (clerk) | Small background tasks, lens extraction | Fast and cheap |

**Supported providers:**

| Provider | Protocol | Key env var |
|----------|----------|-------------|
| [DeepInfra](https://deepinfra.com) | OpenAI-compatible | `DEEPINFRA_API_KEY` |
| [OpenAI](https://platform.openai.com) | OpenAI | `OPENAI_API_KEY` |
| [Anthropic](https://anthropic.com) | Anthropic Messages API | `ANTHROPIC_API_KEY` |
| [LM Studio](https://lmstudio.ai) | OpenAI-compatible (local) | none |
| Any OpenAI-compatible server | OpenAI-compatible | configurable |

Any local server that exposes an OpenAI-compatible `/chat/completions` endpoint — LM Studio, Ollama with the OpenAI adapter, vLLM, llama.cpp server — works without changes to the code. Set the base URL in Settings → Connections → Local server.

A standard model catalogue for DeepInfra ships with the package — adopt it without any API calls:

```bash
resource-librarian --vault ~/MyResearch model_catalog_adopt --provider deepinfra
```

---

## Web search and external capabilities

The `web_search` tool reaches the open web during research sessions without leaving the app. Backends are tried in order:

| Backend | Key env var | Notes |
|---------|-------------|-------|
| [Tavily](https://tavily.com) | `TAVILY_API_KEY` | Best results; free tier available |
| [Brave Search](https://brave.com/search/api/) | `BRAVE_API_KEY` | Alternative; free tier available |
| [SearXNG](https://searxng.github.io/) | none (self-hosted) | Set `searxng_url` in vault config |
| Wikipedia | none | Keyless fallback; always available |

Scholarly search uses **OpenAlex** (keyless, papers and books). Set at least one key to unlock the full web; Wikipedia alone is enough to get started.

Additional capabilities are available by connecting MCP servers in Settings → MCP servers. Curated options that work out of the box:

- **Semantic Scholar** — search papers, citations and authors
- **Playwright browser** — open and read pages a plain fetch cannot reach
- **Apify** — web scrapers and the RAG web browser (requires `APIFY_TOKEN`)

---

## Lenses

Lenses are the vault's specialisation mechanism. A lens is a named reasoning stance — a way of reading a particular kind of material — that the vault extracts from your sources and makes available to the model.

**Where they come from.** When you deep-read a source, the pipeline proposes lenses it finds in the text: a stance the passage teaches, with the sentence that grounds it, the conditions it applies in, and questions to probe with. You review each one in the Staging panel — edit, accept or discard. Accepted lenses are stored in the vault, indexed and searchable.

**How they're used.** In a chat session you can adopt a lens for that thread:

```
/research   →   lens_suggest(material="paper", task="assess")
             →   [shows matching lenses]
             →   lens_adopt("lens-id")
```

Adopting a lens adds its instruction to the session's system prompt. The model then reasons through that stance for the rest of the thread — without you having to explain it. You can adopt multiple lenses and drop any of them mid-session.

**Lens packs.** A domain pack or plugin can ship a set of pre-accepted lenses as a YAML file (a *lens pack*), the same way standard workflows ship with the package. The two that ship in the core:

- `source-assessment` — how to evaluate a source's evidence quality, limits and transferability
- `tool-choice` — how to choose among tools, avoid unnecessary writes, and read refusal messages

**Adaptive learning.** As you work, the lenses your vault holds grow to reflect what you have actually read. A source on distributed systems contributes stances about distributed systems; one on pedagogy contributes stances about teaching. The vault gradually accumulates a reasoning vocabulary that is specific to your domain — without any fine-tuning or configuration.

---

## Tiers and permission modes

Tools are organised into three tiers controlling what a model can do:

- **consult** — reads and searches only. Safe for MCP connections to untrusted hosts.
- **contribute** — adds sessions, staging, and research writes. The normal interactive tier.
- **curate** — full access including vault maintenance. For the person at their own terminal.

The web app adds a permission mode on top: **Plan** (reads only, model proposes), **Ask** (every write pauses for approval), **Auto** (writes within phase and vault settings).

---

## Vault layout

A vault is any folder with a `.librarian/config.toml` inside it. `resource-librarian init` creates the structure; everything else builds from there.

```
MyResearch/
├── .librarian/
│   ├── config.toml      # vault name, clerk route, session settings
│   ├── sessions/        # append-only research thread logs
│   └── staging/         # drafted sources awaiting review
├── Sources/             # one note per ingested source
├── Concepts/            # concepts extracted from sources
├── Offerings/           # finished outputs (reports, analyses)
├── Projects/            # active research threads
├── Indexes/             # topic indexes
└── Inbox/              # drop files here for intake
```

Notes are plain Markdown with YAML frontmatter. The vault opens as-is in Obsidian.

---

## PDF support

```bash
resource-librarian --vault ~/MyResearch pdf_to_markdown --file "Inbox/some-paper.pdf"
```

Extracts and reformats a PDF into clean Markdown beside the original — reflowing paragraphs, stripping headers and footers, adding heading structure. Never summarises or adds content not in the source.

---

## Tests

```bash
pytest                   # fast suite (~40 test files)
pytest -m slow -s        # scale tests on synthetic 1,000 and 5,000-source vaults
```
