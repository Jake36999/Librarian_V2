# Executive Review Summary — Librarian V2 & Geo-Grapher

**Builds Tested:** Librarian V2 `feat/geo-per-library-service` @ `d1a08bb` | Geo-Grapher `feat/per-library-service` @ `42a4474` (`index-D0AQRNRL.js`)  
**Total Model Spend:** **`$0.043281`** (`+$0.004896` above pre-existing `$0.038385`, `$10.00` vault ceiling; `~$0.019931` TTS spent/held on `$2.00` Kokoro cap — well under `$3.00` budget)  
**Detailed Reports:** [REVIEW-UI-UX.md](file:///D:/Librarian_V2/reports/2026-11-19-agent-review/REVIEW-UI-UX.md) · [INFERABILITY-SCORECARD.md](file:///D:/Librarian_V2/reports/2026-11-19-agent-review/INFERABILITY-SCORECARD.md) (`95.3%` blind match across `85` controls) · [LIVE-TEST.md](file:///D:/Librarian_V2/reports/2026-11-19-agent-review/LIVE-TEST.md)

---

## Top 10 Highest-Impact Findings (In Priority Order)

1. **`F-01` (Blocker) — Standalone Geo empty-catalog deadlock:** Opening a fresh standalone Geo server (`GET /api/graphs -> []`) permanently freezes on `"Opening project graphs…"` with zero UI controls ([Workspace.tsx#L181-L190](file:///F:/uv-data/Geo_Grapher/frontend/src/Workspace.tsx#L181-L190)).
2. **`F-02` (Blocker) — Broken default Librarian routes out of the box:** ACCEPT-02's configured `Lead` model (`lead-m`) returns `HTTP 404 model_not_found`, zero of 177 DeepInfra models are `qualified`, and Clerk (`DeepSeek-V4-Flash-0731`) stalls batch ingestion silently at `partial 0/16` (`experimental (missing)`).
3. **`F-03` (High) — Silent `Modes: Ask` MCP approval trap:** Write MCP calls (`ingest`, `open_brief`, `create_project`) block up to `600s` (timing out MCP at `180s`) while showing `"Permission needed"` only inside the Web UI `Chat` tab with zero badge on `Staging` or `Search`.
4. **`F-04` (High) — Geo MCP returns empty `content: []`:** `geographer serve-graphs` emits JSON solely in `structuredContent`, causing Antigravity `call_mcp_tool` to return empty strings on all 22 tools.
5. **`F-05` (High) — Librarian-launched Geo `Add folder…` always fails:** `geo_service.py:90-93` omits `--browse-root`, immediately dead-ending `Add folder…` inside integrated Geo.
6. **`F-06` + `F-07` (High) — Geo MCP latency & schema drift:** Cold first `search_entities` took **`70.96s`** (`1.17 GB` RAM); schemas advertise unsupported `content_kind`/`direction` args that error at runtime, hide `rel_path` on duplicate `GeoService` test hits, and reject `compile_task_packet` IDs either way.
7. **`F-08` (High) — Declared cross-graph bridges cannot be traversed in Geo UI:** Clicking the gold bridge arc or inspecting `Inspect -> Links` offers no jump to target and hides `"unverified"` status under `"reference · in force"`.
8. **`F-09` + `F-10` (High) — Librarian Staging self-conflict & missing intake UI:** Batching creates an optimistic-lock write-conflict checkpoint (`Checkpoints (1)`) on stale UI state, reloading erases drafted fields, and Staging has no `"Add source"` button independent of Chat.
9. **`F-12` (High) — Librarian Search `Filters` blank + `"thin"` + unmatched noise:** UI leaves `"Filters appear here..."` empty despite MCP returning `facets`, leaks raw verdict `"thin"`, and injects `"listed without a term match"` items.
10. **`F-11` + `F-13` + `F-14` (High/Med) — Missing UI Desk & Canvas/Inspector collisions:** Zero `Desk`/`Pin` controls exist in Librarian UI; Geo `Reveal nearby detail` collides with `.scene-edit-help` at `375px`/`768px`/`1440px`, `Rules` buries `Legend`, and `Inspect` clips `"Investigate"` and overflows IDs.

---

## 3 Strongest & 3 Weakest Design Choices

| 3 Strongest Design Choices | 3 Weakest Design Choices |
| :--- | :--- |
| **1. Non-destructive Build operators (`Geo`):** `Add folder` (licence warnings + role overrides), Scissors live drop counts, snapshot-pinned `Combine`, & `Take back` protect source graphs cleanly. | **1. Early loading return before workspace shell (`Geo`):** Treating `graphs.length === 0` identically to `"loading"` locks out every standalone Build operator (`F-01`). |
| **2. Actionable Paperclip workflows (`Librarian`):** Clear `Result:` descriptions preview exact workflow scope before execution (`F-03` aside). | **2. Chat-only broker approval & missing UI fallbacks (`Librarian`):** Routing MCP `Ask` cards only to `Chat` and tying Staging intake to Chat creates deadlocks when users switch tabs or Chat LLMs 404 (`F-02`, `F-03`, `F-10`). |
| **3. Explicit trust/provenance separation & responsiveness:** Clean `Geo-Grapher ↗` ↔ `← Librarian` links, `Checkpoints`, `Agent context` token meters (`868/8192`), `0` root overflow across `375–1440px`, and `0` reduced-motion violations. | **3. Schema/UI mismatches across surfaces:** Geo MCP omitting `content` and documenting non-existent parameters (`content_kind`, `direction`); Librarian `Search` hiding returned `facets`; Geo hiding Scissors until `Box select`. |

---

## 3 Places a Newcomer Is Most Likely to Give Up

1. **Opening standalone Geo-Grapher on a new folder:** Sees `"Opening project graphs…"` forever (`F-01`) with zero buttons to add their folder.
2. **Sending their first Librarian Chat message or ingesting via Staging on default models:** Hits `HTTP 404` on `lead-m` (`F-02`), stalls silently at `partial 0/16` (`experimental`), and finds no `"Add source"` button in Staging (`F-10`).
3. **Connecting an MCP agent while viewing `Staging`/`Search` or querying `geo-grapher`:** Librarian write tools hang 180s without visible notification (`F-03`), while Geo MCP tools print empty strings (`F-04`) or stall >70s cold (`F-07`).

---

## What to Do First
1. Patch Geo `Workspace.tsx` to render `Build -> Add folder…` when `graphs` is empty, pass `--browse-root` from Librarian `geo_service.py`, and pre-validate Librarian's `Lead`/`Clerk` models on boot.
2. Emit text `content` alongside `structuredContent` in `geographer serve-graphs`, remove phantom `content_kind`/`direction` doc references, and expose global `Ask` approval indicators in Librarian's header.
3. Make Geo Scissors available from Hierarchy/Search selection, make declared Gold bridges clickable/traversable (`Inspect -> Links`), and wire `facets` into Librarian's `Search` Filters bar.

---

## What Could Not Be Tested & Why
- **Live multi-turn Librarian UI Chat replies (`B1.1`, `B1.3`) & Chat paperclip workflows (`Suggest sources`):** Blocked by inherited `lead-m` `HTTP 404` (`F-02`) combined with the strict constraint forbidding edits to `Settings -> Models & services`. Substituted MCP session walks, MCP `search`/`get_note`, and verbatim disk source verification (`7` claims).
- **Librarian UI Desk (`Pin`/`Unpin`, `B1.4`):** Unattainable in UI because zero `Desk` or `Pin` controls exist in the DOM (`F-11`); MCP `desk_show` worked while `desk_pin`/`unpin` are write-gated under `Ask`.
- **Cold standalone Geo `Build` onboarding from `0` graphs (`B2.1`):** Blocked at `"Opening project graphs…"` (`F-01`); worked around by seeding 1 tiny CLI bootstrap graph (`seed_boot`) before exercising all 7 Build operators cleanly on `:64181`.

---

## Open Questions for the Owner
1. Why is `preset-deepinfra/lead-m` configured globally across vaults when `lead-m` is absent from DeepInfra's 177-model list and 0 models carry `qualified` status? Should first-run preset selection block non-existent IDs?
2. Should `Resource-Library` (`G:\Libraries\...`) and `ACCEPT-02` share a unified MCP target rule, and should `.claude.json`'s `--vault F:/uv-data/Geo_Grapher` entry be corrected?
3. When MCP clients trigger `Broker` `"ask"` while no person is watching `Chat`, should MCP tools return a structured `"pending_person_approval"` status instead of blocking synchronously for `600s`?
4. When Librarian launches Geo-Grapher (`geo_service.py`), which directories (approved folder-review roots vs vault root) should populate `--browse-root`?
