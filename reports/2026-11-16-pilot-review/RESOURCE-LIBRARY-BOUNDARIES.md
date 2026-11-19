# Resource-Library ingestion: project boundaries and data controls (proposal, 2026-11-16)

**Owner's request (2026-11-16):** use the rest of the $30 for Resource-Library, covering these folders:
- `E:\Librarian research`
- `D:\Librarian_V2`
- `D:\Resource-Library`
- `D:\Aletheia_project\DEV_TOOLS\ToolSet`
- `F:\knowledge_compiler_engine (DAG Engine)`

Boundaries between projects must not blur, making full use of Geo-Grapher and the data controls.

**Status: proposal.** Nothing has been surveyed, accepted or spent in Resource-Library. Its promotion mode is `person`, so a person accepts its folders and starts its paid work. Its ceiling is set to $0 until then.

## 1. How the boundaries are kept

- **One graph per project and stratum.** Geo-Grapher keeps one stratum per graph. Code, docs, data and logs of each project go to `Resource-Library-<project>`, `-docs`, `-data` and `-logs`.
- **Third-party material per project.** New library setting `[folders] third_party_graph = "project"`, already set for Resource-Library. Each project's vendored code goes to `Resource-Library-<project>-third-party` and its papers to `…-third-party-papers`. Without it, ToolSet's vendored tools and the Librarian's papers would share one graph. The default (`library`) is unchanged, so Nonlinear Field Lab keeps its labels.
- **Authorship travels with each folder decision.** It is `owner_created` for the projects and `third_party` for vendored code and papers, and every Source inherits it. Third-party folders are read-only and untrusted for canonical publication.
- **Cross-project questions** go through the cross-graph analysis (`analyze_cross_graphs`, `list_bridges`). No graph is merged.
- **One copy per paper.** 28 PDFs in `D:\Resource-Library\06-Papers\PDF's` are byte-identical to Nonlinear Field Lab's research PDFs (the physics papers). They belong to that library and are being read there. They are skipped here and listed in the run log. `E:\Librarian research` overlaps neither.

## 2. Data controls checked

| Finding | Control |
|---|---|
| `E:\Librarian research\Geo_Grapher-wave4-QA-archive` (4.9 GB): Geo catalogs plus 15 `*.cursor-secret` files | **The credential rule missed `*.cursor-secret`.** Fixed: secret-store names (`*.secret`, `*-secret`, `secrets.json`, `credentials.json`, `.netrc` and others) are now refused before any read. The folder is excluded outright. |
| `D:\Librarian_V2\tmp` (31,052 files): worktrees, QA workspaces and the delegation ledger, plus 427 cursor secrets | Exclude: duplicate code and scratch |
| `D:\Resource-Library\.librarian-app` (the library itself), `.v2` (an old code copy), `.Data`, `.utility` | Hidden folders are never surveyed. `.v2` is also the stale code the old Resource-Library Core was running; that Core was replaced by one on current code. |
| `.env` (ToolSet), `.env.txt` and `config/docker.env` (knowledge_compiler_engine), `.env.example` | Already refused by the credential rule |
| `graphify-out`, `build`, `.venv`, caches | Excluded as generated or dependency folders |

## 3. Proposed folder decisions

Purposes:
- **Sources** are read by the Clerk. That's paid, and it's what the budget buys.
- **Indexed** means the folder goes into its Geo graph only, which is free.

| Project | Folder | Purpose | Graph | Read as Sources |
|---|---|---|---|---|
| Librarian_V2 | `src`, `tests`, `scripts`, `ui`, `obsidian`, `plugin`, `spikes` | own-current | `Resource-Library-Librarian_V2` | no (indexed) |
| | `docs` | own-docs | `…-Librarian_V2-docs` | 40 md |
| | `reports` | own-docs | `…-Librarian_V2-docs` | 142 md (Markdown only, not the evidence JSON/CSV) |
| | `tmp` | exclude | — | — |
| Resource-Library (the V1 vault) | `00-Indexes`, `01-Resources`, `02-Glossary`, `03-Patterns`, `04-Reviews`, `08-Workflows`, `09-Applications`, `10-Models`, `branch offerings`, `internal docs`, top-level notes | own-docs | `…-Resource-Library-docs` | about 590 md |
| | `06-Papers` (notes) | own-docs | `…-Resource-Library-docs` | 88 md |
| | `06-Papers/PDF's` | research-docs | `…-Resource-Library-third-party-papers` | 106 PDFs (134 less the 28 duplicates) |
| | `05-Canvases`, `design` | exclude | — | — |
| ToolSet | `aletheia_toolchain`, `local_tool_assist_mcp`, top-level scripts | own-current | `…-ToolSet` | no |
| | `docs` | own-docs | `…-ToolSet-docs` | 9 md |
| | `3rd-party-tools` | third-party | `…-ToolSet-third-party` | PDFs only (1); its 976 vendored md stay indexed, unread |
| | `local_tool_assist_outputs` | data (owner_created) | `…-ToolSet-data` | no |
| | `ToolSet_bundle_20260502_234111` | exclude (a snapshot) | — | — |
| knowledge_compiler_engine | `src`, `tests`, `scripts`, `frontend`, `colab_deployment`, `config` | own-current | `…-knowledge_compiler_engine (DAG Engine)` | no |
| | `docs`, top-level md | own-docs | `…-docs` | 4 md |
| | `output` (2,497 JSON, 45 `.pt` weights), top-level `dataset*.jsonl` | data (owner_created) | `…-data` | no |
| | `runs` | logs/transcripts (owner_created) | `…-logs` | no |
| | `unsloth_compiled_cache` | exclude | — | — |
| Librarian research | the 114 top-level PDFs | research-docs | `…-Librarian research-third-party-papers` | 114 PDFs, several of them textbooks |
| | `Geo_Grapher-wave4-QA-archive` | exclude | — | — |

**Order and budget.**
- Sources run newest first. Own docs go first (the main architecture), then papers.
- The ceiling is the $30 total less what Nonlinear Field Lab has spent. A small supervisor keeps both libraries' combined spend under $30.
- At the measured rates ($0.004 per Markdown doc, about $0.0008 per text-layer PDF page), about 870 docs and 220 PDFs should come to roughly $8–15. Textbooks dominate the PDF cost.

## 4. What a person decides

1. Accept or change the decisions above. This can be done in Resource-Library's Folders view, or by letting an agent apply them under `promotion.mode = agent`. An agent may not switch that setting itself.
2. Approve the folder checks: `[folders] production_drafting = true`. These are small paid Clerk calls that check each folder's sensitivity. Policy acceptance holds any folder marked sensitive for a person.
3. Approve the paid run by raising the ceiling from $0.
