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
- **Obsidian** reads and writes the same vault: the notes are plain Markdown with YAML frontmatter, so the whole vault opens natively in Obsidian with bi-directional compatibility.

---

## Install

Requires Python 3.11+.

```bash
pip install -e ".[dev]"          # full install including test suite
pip install -e ".[mcp]"          # add MCP server support
pip install -e ".[embed]"        # add semantic embedding for richer search
pip install -e ".[pdf]"          # add PDF extraction
```

Create a new vault and open the app:

```bash
resource-librarian init ~/MyResearch
resource-librarian --vault ~/MyResearch app --open
```

On Windows, `scripts/new-vault.ps1` does both steps in one from a project directory:

```powershell
.\scripts\new-vault.ps1          # creates .librarian-app here, opens in browser
```

`Librarian.bat` in this directory is a shortcut that opens the app (or the vault-selection page if no vault is configured yet).

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

## Models

Librarian runs three model tiers, each independently configurable:

| Tier | Role | Recommended |
|------|------|-------------|
| Tier 1 (lead) | Runs research sessions, chat | Any capable chat model |
| Tier 2 (scribe) | Writes source notes and drafts | Mid-size, instruction-following |
| Tier 3 (clerk) | Small background tasks | Fast and cheap |

Supported providers: **DeepInfra**, **OpenAI**, **Anthropic**, **local** (any OpenAI-compatible server such as LM Studio).

A standard model catalogue for DeepInfra ships with the package — adopt it without making any API calls:

```bash
resource-librarian --vault ~/MyResearch model_catalog_adopt --provider deepinfra
```

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
