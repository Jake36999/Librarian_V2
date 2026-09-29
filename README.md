# Librarian V2 (under construction)

A second, standalone version of the Resource Library, built to be downloaded and deployed into a
**new** vault, and to scale with that vault as it grows. It is more general than V1 and does not
take in V1's data: every V2 vault starts empty and is filled through V2's own intake. The plan is `../PLAN - Librarian V2.md`.

This folder is dot-prefixed on purpose while V2 is built beside V1: V1's index and Obsidian skip
dot-folders, so V1 keeps working unchanged. At cutover (milestone M6) this becomes the repository
root and V1 is retired from this branch.

## Install

```bash
pip install -e ".[dev]"
```

If a command below dies with an OpenBLAS "memory allocation still failed after 10 retries"
error, numpy's backend is fighting the machine for threads; set `OPENBLAS_NUM_THREADS=1` and
`OMP_NUM_THREADS=1` before running it and it clears up.

```bash
resource-librarian init ~/MyResearch          # a new vault
resource-librarian --vault ~/MyResearch doctor

cd ~/MyResearch
resource-librarian index                                   # changed notes only
resource-librarian search --query "parse SQL lineage" --constraints '{"license_class": "Permissive"}'
resource-librarian search --query "workflow patterns" --intent in_text
resource-librarian get_note --name "apache - airflow"
resource-librarian evaluate                                # .librarian/eval/ questions and scenarios

pytest                 # fast suite
pytest -m slow -s      # scale: synthetic 1,000 and 5,000-source vaults
```

Every command above except `init` and `mcp` is a registered tool, so the MCP server and
the chat (M5) offer exactly the same set.

## PDF cleanup

`pypdf`'s extraction (V1 used PyMuPDF, AGPL, which can't ship here) is mechanical: broken
line-wraps, running headers/footers, page numbers, no heading structure - readable by search,
not by a person. `pdf_to_markdown` (`pdf_markdown.py`, ported from
`.utility/scripts/pdf_to_markdown.py`, which converted the books under `06-Papers/PDF's/`)
reformats it into clean markdown, written beside the PDF as its own `.md` file - reflowing,
stripping the noise, adding headings, never summarising or adding anything not in the source:

```bash
resource-librarian --vault ~/MyResearch pdf_to_markdown --file "Inbox/some-book.pdf"
```

The model is fixed on purpose, not a `[clerk]` setting: always `deepseek-ai/DeepSeek-V4-Flash-0731`
on DeepInfra, whatever this vault's own clerk route is (which may be a local model) - it already
proved itself on the original conversion.

## Model catalogues

Profiling a chat model (the model picker's "Profile this model", or `ingest("model:<provider>:<id>")`)
fetches its listing page and drafts a Source note from it - real work, paid for again by every
vault that wants the same provider's models. A **standard catalogue**
(`standard/model_catalog/<provider>.json`) is that work done once and shipped with the package;
any vault adopts it for free, no network call, the same relationship a lens pack has to its
lenses:

```bash
resource-librarian --vault ~/MyResearch model_catalog_status          # what's bundled, what's held
resource-librarian --vault ~/MyResearch model_catalog_adopt --provider deepinfra
```

Also reachable from the app: Settings → Library → **Model catalogues**. Adopting writes each
model straight in as an accepted source (already reviewed once - see `model_catalog.py`), and
adopting again only fills in what's missing, never duplicates. To refresh a catalogue after
profiling more models in some vault, `scripts/export_model_catalog.py --vault <path> --provider
<name>` re-bundles it from that vault's own accepted `Sources/model/` notes.

## The app

```bash
resource-librarian --vault ~/MyResearch app --open   # the interface, on 127.0.0.1:8323
```

The interface (`ui/`, TypeScript with no framework) is built into the package, so an install
needs no Node. To change it: `cd ui && npm install && npm run build`. `ui/smoke.mjs` drives it
in a real browser against `tests/ui_demo_core.py` (a seeded vault and a scripted model).

For a vault scoped to whatever project you're standing in rather than a named research
folder, `scripts/new-vault.ps1` wraps `init` and `app --open` into one step: run it with no
arguments from that project's own directory and it creates (or, on a later run, reopens)
`.\.librarian-app` there, titled after the folder, then launches it. `-Name`, `-Port` and
`-NoLaunch` (set up without launching) cover the rest — see the script's own header.

## The MCP server and the Cowork plugin

```bash
pip install -e ".[mcp]"
resource-librarian --vault ~/MyResearch mcp                    # a Reader, at consult tier
resource-librarian --vault ~/MyResearch mcp --tier contribute  # the Librarian
```

The server is generated from the same registry: one research thread per connection, each
result carrying the session envelope. `plugin/` is the Cowork plugin (skills, commands and the
`clerk` agent) that launches it; see `plugin/README.md`.
