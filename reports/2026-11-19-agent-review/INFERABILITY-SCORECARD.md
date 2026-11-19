# Label-Only Inferability Scorecard (`A2`)

**Builds Reviewed:**
- **Librarian V2:** branch `feat/geo-per-library-service`, commit `d1a08bb` (`Fix the stress-test findings; show the library's own Geo-Grapher as a service, not a failed server`), live sandbox ACCEPT-02 (`http://127.0.0.1:65414/`)
- **Geo-Grapher:** branch `feat/per-library-service`, commit `42a4474` (`Build operators: role override, keep only/remove with counts, compare, declared links, graph colours`, bundle `index-D0AQRNRL.js`), tested on ACCEPT-02 Geo (`http://127.0.0.1:65417/`), `Resource-Library` Geo (`http://127.0.0.1:62518/`, read-only), and disposable standalone Geo (`http://127.0.0.1:64181/`)

## Methodology
During the Phase 2 blind pass (`B0` / `A1` / `A2` via browser subagent `9fa50400-0770-4909-9357-ecae5785e2b9`, before reading design docs or source internals), each visible control's purpose was predicted solely from its label, icon, location, and adjacent text with confidence `1–3`, then exercised to verify whether actual behavior matched (`match`), only partly matched or failed (`partial`), or contradicted (`mismatch`). Disabled controls were audited separately for whether an accessible reason (`title` or visible adjacent hint) was provided.
*(Note: The Phase 2 blind pass scored **85** distinct controls across both products — **44** in Librarian V2 and **41** in Geo-Grapher. Additional standalone `Build` controls unreachable on ACCEPT-02 `:65417` were exercised later in Phase 4 on `:64181` and are summarized below the main table.)*

---

## Summary Statistics (Blind Pass: 85 Controls)

### By Product
| Product | Controls Scored | Match | Partial | Mismatch | Match Rate |
| :--- | ---: | ---: | ---: | ---: | ---: |
| Librarian V2 | 44 | 41 | 3 | 0 | 93.2% (`41/44`) |
| Geo-Grapher | 41 | 40 | 1 | 0 | 97.6% (`40/41`) |
| **Combined** | **85** | **81** | **4** | **0** | **95.3% (`81/85`)** |

### By Control Type
*(Types taken verbatim from Phase 2 blind pass classification; one control was logged as `tab / disabled` and kept in its own row plus noted in Disabled Reason totals.)*

| Control Type | Total | Match | Partial | Mismatch | Match Rate |
| :--- | ---: | ---: | ---: | ---: | ---: |
| `menu` | 17 | 17 | 0 | 0 | 100.0% |
| `toggle` | 5 | 5 | 0 | 0 | 100.0% |
| `slider` | 5 | 5 | 0 | 0 | 100.0% |
| `disabled` | 5 | 5 | 0 | 0 | 100.0% |
| `tab / disabled` | 1 | 1 | 0 | 0 | 100.0% |
| `text` | 28 | 26 | 2 | 0 | 92.9% |
| `icon-only` | 14 | 13 | 1 | 0 | 92.9% |
| `tab` | 10 | 9 | 1 | 0 | 90.0% |
| **Total** | **85** | **81** | **4** | **0** | **95.3%** |

### Disabled-Control Reason Availability (12 Controls Logged with Disabled States)
- **Yes (clear reason in `title` or adjacent visible text):** `6` (`Librarian`: Item `Tick`, `Approve ticked`/`Defer ticked`/`Clear`; `Geo`: `←` Navigate back, `Runtime overlay unavailable`, AST/WL diagnostics, `Keep only or remove`)
- **Partial (ambiguous tooltip or tooltip-only without adjacent hint):** `3` (`Geo`: `Abstraction -> Conceptual Components` disabled `<option>` has `title=null` while rest of `<select>` works; `QI` tooltip only; `Centre`/`Active` in `Graphs` where `Centre` has `title=null` and `Active` says `"Shared scene members (at most 3)"` rather than `"Already active"`)
- **No (no `title` and no explanation when disabled):** `3` (`Librarian`: `Note` tab `title=null`; `Geo`: `Validate and activate rules` `title=null`, `Link graphs` `Use the selected item`/`Declare link` `title=null` — though `Why this link` placeholder reads `Required`)

---

## Top 10 Most Misleading / High-Friction Controls (Blind Pass + Live Exercise)

1. **`Build -> Compare graphs -> Compare` (`Geo`, `text` -> `partial`):** Remains enabled when two paper-only ACCEPT-02 graphs are checked; clicking fires `POST /api/graphs/compare -> HTTP 400` with alert `"These graphs have no code fingerprints yet"` instead of pre-disabling with a reason.
2. **Pre-hydration blank pills & `"Library ▾"` / `"Effort 4"` (`Librarian`, composer/header):** On first paint before hydration, the two pills next to `📎` render completely empty ovals and `Effort` defaults to `4` (later snapping to `Modes: Ask ▾`, `1 lead-m · preset-deepinfra ▾`, `Effort 8`).
3. **`Models` (`Librarian` header, `text` -> `partial`):** Sits beside `Settings` as an equal top-bar button, yet opens the exact same `Settings` modal scrolled/switched to `"Models & services"`, crowding the header onto two rows.
4. **Chat empty-state copy vs `Show the document pane` (`Librarian`):** Empty canvas instructs `"the plan on the right shows where the thread is"`, even though the right Document Pane starts closed on cold load.
5. **`Note` tab (`Librarian` Document Pane, `tab / disabled`):** Disabled before a note is opened with `title=null`, `aria-label=null`, and `aria-disabled=null`, giving a newcomer no hint that picking a note from `Browse` or `Search` unlocks it.
6. **Scissors (`Keep only or remove selection…`, `Geo` canvas rail):** Invisible unless the user already knows to click `Box select` and drag a marquee over bubbles on canvas; searching or framing `src/helper.py` in `Inspect` does not unlock Scissors.
7. **`Read this document` (`Librarian` Document Pane, `icon-only` -> `partial`):** In Phase 2 blind pass on `:65414`, clicking fired `POST /api/tts/chunk -> HTTP 400 Bad Request` (in Phase 4 on revised state it returned HTTP 200 OK via Kokoro-82M at ~$0.002–$0.009 per play, still without pre-click cost confirmation).
8. **`This week` (`Librarian` Document Pane, `tab` -> `partial`):** Hung indefinitely on `"Loading…"` during Phase 2 cold-start `B0` pass (succeeded in Phase 4 live pass with `No date (48)` undated items after `POST /api/tool/agenda` returned 200 OK).
9. **`Graphs -> Centre` / `Active` buttons (`Geo` right panel, `partial` disabled reason):** On the already-active graph, disabled `Centre` has `title=null` and disabled `Active` carries `title="Shared scene members (at most 3)"`, which fails to state `"This graph is already active"`.
10. **`Build -> Link graphs -> Declared links` (`reference · in force`) (`Geo`):** After declaring a manual bridge, `Declared links` displays `reference · in force` and truncated raw IDs (`entity:entity:74277f…`) without displaying the `"unverified operator assertion"` warning documented in Geo-Grapher's docs/MCP instructions, nor does clicking the gold bridge arc jump to the target node.

*(Wait: note that standalone Geo's empty-catalog deadlock at `Workspace.tsx:181-190` — `"Opening project graphs…"` forever when `GET /api/graphs` returns `[]` — precedes any control even rendering!)*

---

## Top 10 Clearest & Most Inferable Controls

1. **`Geo-Grapher ↗` ↔ `← Librarian · <library>` (`Librarian` ↔ `Geo` headers):** Explicit external-launch icon and back-link breadcrumb reliably open Geo in a popup tab and return to Librarian in 1 click.
2. **`📎` Attach / Workflows paperclip menu (`Librarian` composer):** Every option (`Attach a file from this computer`, `Link a note or folder from the library`, `Open skill registry`, plus 5 workflows) pairs a clear verb with an exact `Result:` explanation before running.
3. **`Staging -> Approve ticked` / `Defer ticked` (`Librarian`):** Pre-disabled with clear adjacent helper text (`"Tick sources to decide several at once"`) and dynamically updates its label to exact count (`"Approve 1 ticked"`).
4. **`Modes: Ask ▾` (`Librarian` composer):** Immediately clarifies current broker posture and lists three unambiguous choices (`Plan`, `Ask permission`, `Auto`).
5. **`Staging -> Which sources` (`Librarian`):** Status-oriented plain-English filter labels (`Captured, to review`, `Approved, awaiting ingestion`, `Ingested, ready to accept`, `Ingested with gaps`).
6. **`Legend` (`Geo` canvas top-left):** Concise visual decoding table covering enclosures, 10 node categories, 7 edge colors (`orange call/data`, `gold bridge`, `red violation`, etc.), direction fade, and dashed/dotted patterns.
7. **`Dark` / `Light` theme toggle (`Geo` Settings):** Immediately switches both chrome and the WebGL/3D canvas theme with unmistakable visual feedback.
8. **`Keep only or remove` live cut preview (`Geo` Build / Scissors):** Reports exact file count, item count, and cross-cut dropped relationship count (`"Keeps 1 of 5 files and 9 of 27 items. Relationships across the cut would be dropped: 15."`) before creating a new graph.
9. **`Combine graphs -> Review merge plan` (`Geo` Build):** Forces explicit plan inspection (naming source snapshots and confirmation checkbox) before creating an immutable merged graph.
10. **`Inspect -> Agent context` (`Geo` right panel):** Displays explicit token budget (`868/8192`) and one-click `Copy context JSON` action with unambiguous meaning.

---

## Complete Blind-Pass Scorecard Table (85 Controls)

| # | Product | Screen / Region | Control | Type | Prediction | Conf | Actual | Score | Disabled reason? |
|---:|:---|:---|:---|:---|---:|:---:|:---|---:|:---|
| 1 | Librarian | Header | `Library ▾` (`ACCEPT-02 Testing Library ▾`) | `menu` | Opens library switcher dropdown | 3 | Opens list of ~18 libraries + Open another library | `match` | — |
| 2 | Librarian | Header | `Sessions ▾` | `menu` | Opens conversation threads list | 3 | Opens `Sessions` dialog (New conversation, sort, 2 threads) | `match` | — |
| 3 | Librarian | Header | `Checkpoints ▾` | `menu` | Lists pending human-approval checkpoints | 3 | Opens `Decisions waiting for you` ("No decisions are waiting") | `match` | — |
| 4 | Librarian | Header | `Chat` | `tab` | Switches main view to Chat | 3 | Activates Chat tab & composer | `match` | — |
| 5 | Librarian | Header | `Staging` | `tab` | Switches main view to Staging review | 3 | Switches main view to Staging review | `match` | — |
| 6 | Librarian | Header | `Search` | `tab` | Switches main view to Search | 3 | Switches main view to Search | `match` | — |
| 7 | Librarian | Header | `Settings` | `text` | Opens library & app Settings modal | 3 | Opens Settings modal on `Models & services` | `match` | — |
| 8 | Librarian | Header | `Models` | `text` | Opens model configuration view | 2 | Opens exact same Settings modal on `Models & services` (redundant with `Settings`) | `partial` | — |
| 9 | Librarian | Header | `Geo-Grapher ↗` | `text` | Launches Geo-Grapher in new tab | 3 | Opens new popup tab on `:65417/` | `match` | — |
| 10 | Librarian | Header | `Show the document pane` (split-pane icon) | `icon-only` | Toggles right-hand Document Pane | 3 | Toggles right-hand Document Pane open/closed | `match` | — |
| 11 | Librarian | Header | `⏻` (`Close Geo-Grapher or this library`) | `icon-only` | Shuts down server or offers power options | 2 | Opens dialog with `Close Geo-Grapher` & `Close this library` (barely visible in screenshot overlap) | `match` | — |
| 12 | Librarian | Composer | `#lib-msg` (`Ask the librarian...`) | `text` | Message input for chat | 3 | Accepts typed text; Enter sends | `match` | — |
| 13 | Librarian | Composer | `📎` (`Attach`) | `icon-only` | Opens attachment / workflow menu | 3 | Opens dialog with attach, link, skill registry, and 5 workflows | `match` | — |
| 14 | Librarian | Paperclip menu | `📎 Attach a file from this computer` | `menu` | Opens OS file picker into Inbox | 3 | File input trigger (`Copies it into this library's Inbox`) | `match` | — |
| 15 | Librarian | Paperclip menu | `🔗 Link a note or folder from the library` | `menu` | Opens vault picker to attach note/folder | 3 | Opens Document Pane Browse in `"Pick a file to add to the chat"` mode | `match` | — |
| 16 | Librarian | Paperclip menu | `Open skill registry` | `menu` | Displays available skills/commands | 3 | Opens `Skill registry` article in right Document Pane | `match` | — |
| 17 | Librarian | Paperclip menu | `Run a workflow` (5 buttons) | `text` | Starts predefined workflow (e.g. `Process enrichment backlog`) | 3 | 5 workflow buttons with clear Result descriptions (not executed to preserve state) | `match` | — |
| 18 | Librarian | Composer | `Modes: Ask ▾` (blank before hydration) | `menu` | Selects agent permission mode | 3 | Opens Permission mode menu (`Plan`, `Ask permission`, `Auto`) | `match` | — |
| 19 | Librarian | Composer | `1 lead-m · preset-deepinfra ▾` (blank before hydration) | `menu` | Selects lead/notes/small-task chat models | 3 | Opens Chat models 1-2-3 role picker + `Filter models` | `match` | — |
| 20 | Librarian | Composer | `Effort` (`4`/`8`) | `slider` | Adjusts reasoning effort level | 3 | Range slider controlling effort (`8` in hydrated view) | `match` | — |
| 21 | Librarian | Composer | `↗ Open in Obsidian` | `text` | Opens current library/vault in Obsidian | 3 | External `obsidian://` action button | `match` | — |
| 22 | Librarian | Composer | `Send` | `text` | Sends message; disabled/no-op if empty | 3 | No-op when input empty (stays enabled visually) | `match` | — |
| 23 | Librarian | Doc Pane | `Note` | `tab / disabled` | Shows open note content | 3 | Disabled until a note is opened; active & renders markdown once opened | `match` | No (`title=null`, no adjacent reason when disabled) |
| 24 | Librarian | Doc Pane | `Browse` | `tab` | Lists vault folders and root notes | 3 | Shows `/` with 19 folders & 27 notes | `match` | — |
| 25 | Librarian | Doc Pane | `Plan` | `tab` | Shows active thread plan | 3 | Shows `"No thread yet."` | `match` | — |
| 26 | Librarian | Doc Pane | `This week` | `tab` | Shows tasks due this week | 2 | Stuck on `"Loading…"` after wait | `partial` | — |
| 27 | Librarian | Doc Pane | `Read this document` (speaker icon) | `icon-only` | Reads open note aloud via TTS | 3 | Toggles aria-label to `Stop reading aloud`; fires `POST /api/tts/chunk` (HTTP 400) | `partial` | — |
| 28 | Librarian | Doc Pane | `⋮` (`Note actions`) | `icon-only` | Opens note context menu | 3 | Opens `Open this note in Obsidian`, `Rename or move…`, `Copy path` | `match` | — |
| 29 | Librarian | Doc Pane | `✕` (`Close the pane`) | `icon-only` | Closes Document Pane | 3 | Closes Document Pane | `match` | — |
| 30 | Librarian | Doc Pane | `Document pane width` resizer | `slider` | Dragging widens/narrows pane | 3 | Dragging left widened pane and switched `Pane view` `<select>` into 4 tab buttons | `match` | — |
| 31 | Librarian | Staging | Kind tabs (`Sources 5`, `Folders 29`, `Lenses 9`, `Concepts 0`, `Topics 0`, `Offerings 0`, `From V1 0`) | `tab` | Switches staged item category | 3 | Switches category (`Sources`, `Folders`, `Lenses` populated; `Offerings` empty) | `match` | — |
| 32 | Librarian | Staging | `Which sources` dropdown | `menu` | Filters sources by pipeline status | 3 | Filters between `Captured, to review`, `Approved...`, `Ingested...`, etc. | `match` | — |
| 33 | Librarian | Staging | `Review evidence layout` dropdown | `menu` | Changes draft vs evidence pane layout | 3 | Switches `Evidence beside draft` / `Evidence on demand` | `match` | — |
| 34 | Librarian | Staging | `Refresh` | `text` | Reloads staging queue | 3 | Reloads staging items | `match` | — |
| 35 | Librarian | Staging | Item `Tick` checkbox | `toggle` | Selects item for batch `Approve ticked` / `Defer ticked` / `Clear` | 3 | Ticking enables `Approve ticked`, `Defer ticked`, `Clear`; `Clear` unticks | `match` | Yes (adjacent text `"Tick sources to decide several at once"`; `title=null`) |
| 36 | Librarian | Staging | `Approve ticked` / `Defer ticked` / `Clear` | `disabled` | Batch-act on ticked items (disabled until ticked) | 3 | Disabled until ≥1 item ticked; enabled immediately on tick | `match` | Yes (adjacent text) |
| 37 | Librarian | Staging | Item detail actions (`Approve for ingestion`, `Reject`, `Defer`, `Accept as captured`, `Redraft`, `Deep read`, `View source evidence`) | `text` | Single-item review actions | 3 | Visible in item detail panel below draft/evidence (long titles overflow horizontally) | `match` | — |
| 38 | Librarian | Staging Folders | `Survey folders` / `Approve selected...` / `Accept unambiguous...` | `text` | Batch folder classification actions | 3 | Appears in `Folders (29)` tab alongside per-folder Purpose chips | `match` | — |
| 39 | Librarian | Search | `Search query` + `Search` button | `text` | Runs search across selected scope | 3 | Returns grouped results (`Sources`, `Patterns`, `What this library made`, `workspace`) | `match` | — |
| 40 | Librarian | Search | `Search in` dropdown | `menu` | Scopes search to library/staging/sessions/activity | 3 | Changes results (e.g. `staging` finds staged folder) | `match` | — |
| 41 | Librarian | Search | `Intent` dropdown | `menu` | Filters by 8 query intents or `all` | 3 | Single-intent query (`in_text`) switches to flat source-passage list | `match` | — |
| 42 | Librarian | Search | `Source date` dropdown | `menu` | Filters results by recency | 3 | Re-runs query filtered by date (`any date`, `within a year`, `within 3 years`) | `match` | — |
| 43 | Librarian | Search | Result link + `Not relevant` | `text` | Opens note / marks result irrelevant | 3 | Result link opens note in Document Pane (`Filters` box stays empty — no scope tiles) | `match` | — |
| 44 | Librarian | Settings | `Find a setting` + Left nav sections | `text` | Filters settings and switches section | 3 | Switches sections (`Chat behaviour`, `Topics & organisation`, etc.); no Dark/Light theme toggle exists | `match` | — |
| 45 | Geo | Top bar | `Geo Grapher home` logo | `icon-only` | Navigates to Geo-Grapher root | 3 | Links to `:65417/` | `match` | — |
| 46 | Geo | Top bar | `← Librarian · ACCEPT-02 Testing Library` | `text` | Returns to Librarian tab/URL | 3 | Navigates back to `http://127.0.0.1:65414/` | `match` | — |
| 47 | Geo | Top bar | `Close` | `text` | Closes Geo-Grapher for this library | 3 | Title: `"Close Geo-Grapher for ACCEPT-02 Testing Library"` | `match` | — |
| 48 | Geo | Top bar | `←` (`Navigate back`) | `disabled` | Goes back in workspace history | 3 | Disabled at initial state | `match` | Yes (greyed out at root; `title="Back"`) |
| 49 | Geo | Top bar | `↑` (`Enter parent container`) | `icon-only` | Moves up one containment level | 3 | Stays at current level when already at top graph container | `match` | — |
| 50 | Geo | Top bar | `Home` (house icon) | `icon-only` | Resets to top Workspace view | 3 | Restores Workspace overview displaying all checked graphs | `match` | — |
| 51 | Geo | Top bar | `Workspace` / `DataManagement-baseline` breadcrumb | `text` | Jumps to clicked ancestor level | 3 | Breadcrumb buttons for containment navigation | `match` | — |
| 52 | Geo | Top bar | `Search files, classes, functions…` + `Search intent` | `menu` | Searches entities/docs by mode | 3 | Typing triggers `"Searching…"` in banner; intent has 3 modes | `match` | — |
| 53 | Geo | Top bar | `Hierarchy` | `icon-only` | Toggles left Repository hierarchy drawer | 3 | Opens/closes left Hierarchy drawer (`Close hierarchy` inside) | `match` | — |
| 54 | Geo | Top bar | `Settings` (gear icon) | `icon-only` | Opens Geo-Grapher preferences | 3 | Opens popover with `Dark`/`Light` theme + `Hierarchy width` & `Inspector width` sliders | `match` | — |
| 55 | Geo | Settings | `Dark` / `Light` theme buttons | `toggle` | Switches UI and canvas theme | 3 | Immediately switches full UI + 3D canvas between Dark and Light modes | `match` | — |
| 56 | Geo | Settings | `Hierarchy panel width` / `Inspector panel width` | `slider` | Resizes left and right sidebars | 3 | Range sliders (`235`, `330`) | `match` | — |
| 57 | Geo | Hierarchy | `External references` / `Documentation` / `−` collapse / `Close hierarchy` | `toggle` | Filters tree nodes & collapses drawer | 3 | Checkboxes toggle, `−` collapses root (`aria-expanded="false"`), `Close hierarchy` closes drawer; tree shows `"No children in this hierarchy filter"` | `match` | — |
| 58 | Geo | Main bar | `3D space` / `List` / `Matrix` | `tab` | Switches architecture visualization mode | 3 | Switches smoothly between 3D canvas, table List, and Dependency Matrix | `match` | — |
| 59 | Geo | Main bar | `Relationships` dropdown | `menu` | Changes edge visibility preset | 3 | Switches `Exact`, `Internal exact + candidates`, `All uncertainty` | `match` | — |
| 60 | Geo | Main bar | `Abstraction` dropdown | `menu` | Changes node grouping granularity | 3 | Switches `Interactive Mixed`, `Repository`, `Directories`, `Files`, `Classes`, `Atomic` (`Conceptual Components` disabled) | `match` | Partial (`Conceptual Components` disabled with no explanation) |
| 61 | Geo | Main bar | `Path` / `Nearby` / `Wider` | `toggle` | Adjusts neighborhood breadth | 3 | Toggles pressed breadth level | `match` | — |
| 62 | Geo | Main bar | `Scope & filters` | `text` | Expands dependency filter & QI popover | 3 | Opens `Dependency scope` popover | `match` | — |
| 63 | Geo | Scope & filters | `Static` / `Runtime overlay` [disabled] / `Runtime overlay unavailable` | `disabled` | Toggles static vs runtime edges | 3 | `Static` checked; runtime controls disabled | `match` | Yes (`Runtime overlay unavailable` + title `"No measured runtime collection is attached to this snapshot"`) |
| 64 | Geo | Scope & filters | Subtypes (`calls`, `imports`, `imports_from`, `inherits`) & `tests`/`generated`/`vendor`/`external`/`Include uncertain` | `toggle` | Filters edge & node categories | 3 | Checkboxes toggle filter state (tight label-to-checkbox spacing visually) | `match` | — |
| 65 | Geo | Scope & filters | `Collapse nearby detail` / `Collapse to focused scope` / `Reset filters` | `text` | Collapses expansion or resets scope | 3 | Scope-reset action buttons | `match` | — |
| 66 | Geo | Scope & filters | `QI` (`QI algorithm`: `Off` / `Helper balls` / `Directed`) | `disabled` | Controls QI grouping layout | 2 | Disabled in `Interactive Mixed`; **enabled** when `Abstraction = Atomic` | `match` | Partial (tooltip `title="Requires atomic grouping and exact static relationships."` only; no visible adjacent text) |
| 67 | Geo | Scope & filters | `Configure rules` (+ `Validate and activate rules` [disabled]) | `text` | Opens YAML rules configuration | 3 | Expands `Rules configuration` (model, YAML textarea, file upload, disabled Validate) overlapping Legend | `match` | No (`Validate` `title=null`, empty YAML implies why) |
| 68 | Geo | Main bar | `Pin selection` (pin icon) | `icon-only` | Pins selected entity in scene | 3 | Toggles `aria-pressed="true"` | `match` | — |
| 69 | Geo | Canvas rail | `Box select` | `icon-only` | Enables shift-drag rectangular selection | 3 | Toggles `aria-pressed="true"` | `match` | — |
| 70 | Geo | Canvas rail | `Reset layout` | `icon-only` | Resets moved/resized bubbles | 3 | Resets manual bubble placement | `match` | — |
| 71 | Geo | Canvas | `Legend` | `text` | Toggles color/edge/depth legend | 3 | Opens detailed legend (`○ enclosure`, node/edge colors, direction, pattern, size/depth/angle) | `match` | — |
| 72 | Geo | Canvas | `Zoom out` (`-`), `Zoom` slider, `Zoom in` (`+`), `Fit displayed graphs` | `slider` | Adjusts camera zoom & frames scene | 3 | `Zoom in` `0`→`0.3`, `Zoom out` `0.3`→`0`, `Fit` resets framing (note `Reveal nearby detail` pill overlaps canvas hint text when centered) | `match` | — |
| 73 | Geo | Canvas bottom | `Bundling` slider & `Local EdgeLens` checkbox | `slider` | Adjusts edge bundling (`0.80`) & cursor EdgeLens | 3 | Checkbox toggles; slider reads `0.8` | `match` | — |
| 74 | Geo | Canvas bottom | `Coverage` | `text` | Shows extraction coverage & unresolved counts | 3 | Opens `Extraction coverage` popover (`0 exact · 0 candidate · 0 unresolved · 0 parse failures`) | `match` | — |
| 75 | Geo | Right panel | `Inspect` / `Graphs` / `Build` | `tab` | Switches right panel mode | 3 | Switches cleanly between Inspect, Graphs, and Build | `match` | — |
| 76 | Geo | Inspect | `Overview` / `Links` / `Evidence` / `Agent context` / `Investigate` | `tab` | Switches entity inspector sub-views | 3 | All 5 tabs switch and show grounded content (Agent context shows token budget `868/8192` + `Copy context JSON`) | `match` | — |
| 77 | Geo | Inspect → Overview | `Enter / frame`, `Copy ID`, `Pin entity`, `Impact direction`, `Find dependants`, `Advanced diagnostics`, `Find identical normal forms` [disabled], `Find WL candidates` [disabled], `Architecture rules` | `text` | Inspects/frames/queries selected entity | 3 | `Pin entity` toggles to `Unpin entity`; `Find dependants` returns `0 dependants`; `Advanced diagnostics` & `Architecture rules` expand; AST/WL buttons disabled | `match` | Yes (adjacent `"Normalised AST Not available"`, `"3-hop WL Not available"`; `title=null`) |
| 78 | Geo | Graphs tab | `Active graph` dropdown + `Graphs ( 2 )` toggle | `menu` | Selects active graph & expands graph list | 3 | Switches active graph; `Graphs ( 2 )` toggles graph cards | `match` | — |
| 79 | Geo | Graphs tab | Per-graph checkbox, `Centre` [disabled on active], `Active` [disabled on active], `Colour` dropdown, `Copy…`, `Delete…` | `text` | Displays, centers, activates, colors, copies, or deletes graph | 2 | Checkbox hides/shows graph; `Centre` on external isolates view to 1 graph; `Copy…` opens inline form; `Delete…` opens inline `"Type the graph label to confirm"` (cancelled) | `match` | Partial (disabled `Centre` has `title=null`; disabled `Active` has `title="Shared scene members (at most 3)"` which doesn't state "already active") |
| 80 | Geo | Graphs tab | `Show declared bridges`, `Repository snapshot`, `Save view`, `Saved views` | `text` | Toggles bridges, snapshot, saves/loads view | 3 | `Show declared bridges` toggles; `Save view` opens `"Save this workspace"` modal (cancelled) | `match` | — |
| 81 | Geo | Build tab | `Add folder…` | `text` | Opens folder browser/splitter | 3 | Shows inline `"No folders are browsable. Start the server with --browse-root DIR."` | `match` | — |
| 82 | Geo | Build tab | `Keep only or remove` (scissors workflow) | `disabled` | Keeps/removes canvas-selected files/folders | 3 | Shows `"Select files or folders on the canvas, then press the scissors... Nothing is selected for this yet."` (scissors icon not rendered at repo-only level) | `match` | Yes (adjacent text explains why inactive) |
| 83 | Geo | Build tab | `Combine graphs` → `Create a physically merged graph` | `text` | Opens merge plan form | 3 | Expands `New graph name` + `Review merge plan` | `match` | — |
| 84 | Geo | Build tab | `Compare graphs` (`First`, `Second`, `Compare`) | `text` | Diffs two checked graphs | 2 | Fires `POST /api/graphs/compare -> HTTP 400`, inline alert `"These graphs have no code fingerprints yet, so they cannot be compared"` | `partial` | — |
| 85 | Geo | Build tab | `Link graphs` (`Whole graph`, `Use the selected item` [disabled on To], `Declare link` [disabled], `Review bridge candidates` → `Find candidates`) | `text` | Declares cross-graph links or reviews candidates | 3 | `Whole graph` fills `root`; `Find candidates` shows `"No pending candidates listed."` | `match` | No (disabled `Use the selected item` and `Declare link` lack `title` tooltips, though `Why` placeholder says `Required`) |

---

## Post-Blind Build Controls Observed Live (`http://127.0.0.1:64181/`)
When unblocked with a seeded code graph + `--browse-root` in Phase 4, the following additional controls appeared and were scored qualitatively:
- **`Keep only or remove selection…` (Scissors rail icon):** Hidden until `Box select` is used on canvas; preview wording (`Keep only these` vs `Remove these`) is highly clear with exact dropped-edge counts.
- **`How this folder was read` (`Add folder…` -> `Read this folder` modal):** Clear Role dropdown (`8` options), clear `licence file present` vs `no licence file` badges, and clear `"you chose X; the scan suggested Y"` confirmation; however multi-part `Ingest 3 selected parts` did not auto-refresh `Graphs` without reload.
- **`Compare` diff listitems (`app_repo -> app_repo_v2`):** Clear counts (`1 Identical`, `2 Same contract, rewritten`, `2 Same name, changed`, `3 Only in ...`), but list rows are static text (non-clickable).
- **`Take back` (`Declared links`):** Clear inline confirmation (`Take it back` / `Keep it`); however `Declared links` renders truncated hashes (`entity:entity:74277f…`) + `reference · in force` without surfacing `"unverified"`, and clicking the gold bridge arc provides no jump/traversal.
