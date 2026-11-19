The following is a <SYSTEM_MESSAGE> not actually sent by the user. It is provided by the system as important information to pay attention to.

<SYSTEM_MESSAGE>
[Message] timestamp=2026-11-19T14:10:01Z sender=9fa50400-0770-4909-9357-ecae5785e2b9 priority=MESSAGE_PRIORITY_HIGH content=COMPLETED / TASK_COMPLETED

### 1. Part 1 — B0 Blind Cold Start & A1 First-Impression Audit

#### A1 First-Impression Audit — Librarian V2 (`http://127.0.0.1:65414/` at `1440×900`)
- **30-second impression**: Immediately recognizable as an AI-assisted knowledge/vault workspace ("Ask the librarian. It opens a session for anything longer than one search, and the plan on the right shows where the thread is.") with top-bar navigation (`Chat`, `Staging`, `Search`), `Settings`, `Models`, `Geo-Grapher ↗`, a document-pane toggle, power `⏻`, and a bottom chat composer.
- **Initial/empty-state friction & bugs**:
  - **Pre-hydration blank controls**: On first paint before JS hydration completes, the library button reads generic `"Library ▾"` (missing `ACCEPT-02 Testing Library`), and two pill buttons next to `📎` render completely blank (later hydrating to `Modes: Ask ▾` and `1 lead-m · preset-deepinfra ▾`).
  - **Misleading empty-state copy**: Main canvas claims *"the plan on the right shows where the thread is"*, yet the right Document Pane is closed by default (`Plan` is invisible until manually toggled).
  - **Header crowding**: Once hydrated (`ACCEPT-02 Testing Library ▾`), the top bar wraps awkwardly onto two lines at `1440×900`.
  - **Console/HTTP error on boot**: Initial load logs `GET /api/file?path=About%20the%20Librarian%20and%20how%20to%20use%20it.md -> HTTP 404` (and clicking `Read this document` later triggers `POST /api/tts/chunk -> HTTP 400 Bad Request`).
  - **First click instinct**: `Show the document pane` (to find the referenced "plan on the right") and `Library ▾` / `Staging` / `Search` to discover what the library actually holds.

#### B0 Cold-Start Goals Log (Librarian V2 & Geo-Grapher)
- **(a) What does this library contain?**
  - **Path & clicks**: Click 1: `Show the document pane` → opens on `Plan` ("No thread yet"). Click 2: `Pane view` dropdown → `Browse` → reveals vault root `/` containing **19 folders** (`About/`, `ACCEPT-02 Test/`, `Computer systems and security/`, `Design Theory/`, `Excalidraw/`, `Game-Concepts/`, `gemini-Transcripts/`, `Indexes/`, `module 1/`, `Networking/`, `Notes/`, `owl animation_files/`, `Programming/`, `Projects/`, `quest app design spec/`, `research/`, `Sources/`, `Systems analysis and database design/`, `The riddle app/`) and **27 root notes** (`Welcome`, `Introduction to Networking`, `Quest app - Design Document first draft`, etc.). Click 3: `Staging` tab → shows **5 Sources**, **29 Folders**, **9 Lenses**, **0 Concepts/Topics/Offerings/From V1**. Also `Settings → Topics & organisation` shows **10 topic buckets** (all `0` filed) + `Unfiled (5)`.
  - **Dead ends / friction**: No library summary/dashboard on `Chat`; `This week` pane view stayed stuck on `"Loading…"`; `Note` tab is disabled with no tooltip until a note is picked from `Browse`; clicking `Open skill registry` links (`About the Librarian...`, `Tool Reference`, `Rules`) have `href="#"` and `About the Librarian and how to use it.md` 404s.
- **(b) How do you search it?**
  - **Path & clicks**: Click 1: `Search` tab (`Chat | Staging | Search`). Type query and click `Search` (2 more actions).
  - **Scopes/filters observed**: `Search in` (`the library`, `staging`, `sessions`, `activity`), `Intent` (`all · everything, grouped` + 8 intents: `donor`, `orient`, `pattern`, `technique`, `data`, `precedent`, `made`, `in_text`), `Source date` (`any date`, `within a year`, `within 3 years`), plus a `"Filters"` container (`"Filters appear here from what the search returns."`).
  - **Query results & quality**:
    - `"networking"` (`the library`, `all`): `Sources · 2` (includes an unrelated European yield-curve ANN paper labeled `"listed without a term match"` + `Unfiled` topic), `Patterns · 0`, `What this library made · 4` (3 labeled `"listed without a term match"`, 1 matched `'networking'` in heading), `workspace · 5` (top match `Introduction to Networking`; clicking it opened the full note in Document Pane).
    - `"quest"` (`the library`, `all`): `workspace · 16` (relevant hits like `quest app design sketchup`, `Quest app - Design Document first draft`).
    - `"networking"` (`staging`): `10-Domain-Diverse-Baseline-Controls/cybersecurity-networking · folder · staged`.
  - **Dead ends / friction**: The `"Filters"` region remained completely empty (`""`) even after results loaded (no clickable scope tiles appeared for `sources`/`concepts`/`notes`/`projects`/`sessions`/`staging`). Searching `"networking"` returned unrequested `"listed without a term match"` items in `Sources` and `What this library made`.
- **(c) How do you open its Geo view & return?**
  - **Path & clicks**: Click 1: `Geo-Grapher ↗` in Librarian top bar. Opens a **new popup tab** at `http://127.0.0.1:65417/` (`<REDACTED_TOKEN>` stripped; title `Geo Grapher · Architecture workspace`; `<meta name="geographer-workspace" content="integrated">`; modulepreload chunks `rolldown-runtime-WkwZ5CU-.js`, `react-DCTAcUCH.js`, `three-DvFRLbwu.js`, CSS `index-m16ZCzl7.css`; executable `<script>` tags are stripped by the browser sandbox).
  - **Return**: Clicking `← Librarian · ACCEPT-02 Testing Library` in Geo-Grapher's top-left navigates cleanly back to `http://127.0.0.1:65414/` (1 click).
- **(d) What graphs exist in Geo-Grapher and what do they cover? (Geo-Grapher A1)**
  - **A1 first impression (`1440×900`)**: Dark 3D workspace showing 2 isolated spherical repository bubbles (`DataManagement-baseline` in magenta, `DataManagement-external` in teal) with **0 curves** and **2 entities** (`4 groups · 0 curves · 2 entities · working-tree`). Top bar provides navigation, search, `Hierarchy`, and `Settings`; right panel shows `Inspect | Graphs | Build`.
  - **Graphs present (`Graphs` tab)**:
    1. `ACCEPT-02 Testing Library-DataManagement-baseline` (Magenta, Active & Checked; root `g_1b2d94d0a79987dfa563eb9e:4ae57baa08cb`, `1 repository represented leaf owners`, `working tree cf1cbb66 · d21469`).
    2. `ACCEPT-02 Testing Library-DataManagement-external` (Teal, Checked; root `g_8daf20e7826dde6eb4072258:258113bf376e`, `1 repository represented leaf owners`).
  - **Dead ends / confusion**: Both graphs contain only 1 repository enclosure each with no child files/folders (`"No children in this hierarchy filter"` regardless of `External references` / `Documentation` toggles, `0 exact · 0 candidate · 0 unresolved relationships`), so drill-down (`Enter / frame`), `Compare` (`HTTP 400: "These graphs have no code fingerprints yet"`), `Add folder…` (`"No folders are browsable. Start the server with --browse-root DIR."`), and leaf selection/scissors tools cannot reveal code structure in this dataset. Also at `1080×800` and `1440×900`, the long hash entity ID overflows the right inspector horizontally.

---

### 2. Part 2 — A2 Label-Only Inferability Scorecard (84 Controls)

| Product | Screen / Region | Control | Type | Prediction | Confidence | Actual | Score | Disabled reason? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| Librarian | Header | `Library ▾` (`ACCEPT-02 Testing Library ▾`) | menu | Opens library switcher dropdown | 3 | Opens list of ~18 libraries + Open another library | match | — |
| Librarian | Header | `Sessions ▾` | menu | Opens conversation threads list | 3 | Opens `Sessions` dialog (New conversation, sort, 2 threads) | match | — |
| Librarian | Header | `Checkpoints ▾` | menu | Lists pending human-approval checkpoints | 3 | Opens `Decisions waiting for you` ("No decisions are waiting") | match | — |
| Librarian | Header | `Chat` | tab | Switches main view to Chat | 3 | Activates Chat tab & composer | match | — |
| Librarian | Header | `Staging` | tab | Switches main view to Staging review | 3 | Switches main view to Staging review | match | — |
| Librarian | Header | `Search` | tab | Switches main view to Search | 3 | Switches main view to Search | match | — |
| Librarian | Header | `Settings` | text | Opens library & app Settings modal | 3 | Opens Settings modal on `Models & services` | match | — |
| Librarian | Header | `Models` | text | Opens model configuration view | 2 | Opens exact same Settings modal on `Models & services` (redundant with `Settings`) | partial | — |
| Librarian | Header | `Geo-Grapher ↗` | text | Launches Geo-Grapher in new tab | 3 | Opens new popup tab on `:65417/` | match | — |
| Librarian | Header | `Show the document pane` (split-pane icon) | icon-only | Toggles right-hand Document Pane | 3 | Toggles right-hand Document Pane open/closed | match | — |
| Librarian | Header | `⏻` (`Close Geo-Grapher or this library`) | icon-only | Shuts down server or offers power options | 2 | Opens dialog with `Close Geo-Grapher` & `Close this library` (barely visible in screenshot overlap) | match | — |
| Librarian | Composer | `#lib-msg` (`Ask the librarian...`) | text | Message input for chat | 3 | Accepts typed text; Enter sends | match | — |
| Librarian | Composer | `📎` (`Attach`) | icon-only | Opens attachment / workflow menu | 3 | Opens dialog with attach, link, skill registry, and 5 workflows | match | — |
| Librarian | Paperclip menu | `📎 Attach a file from this computer` | menu | Opens OS file picker into Inbox | 3 | File input trigger (`Copies it into this library's Inbox`) | match | — |
| Librarian | Paperclip menu | `🔗 Link a note or folder from the library` | menu | Opens vault picker to attach note/folder | 3 | Opens Document Pane Browse in `"Pick a file to add to the chat"` mode | match | — |
| Librarian | Paperclip menu | `Open skill registry` | menu | Displays available skills/commands | 3 | Opens `Skill registry` article in right Document Pane | match | — |
| Librarian | Paperclip menu | `Run a workflow` (5 buttons) | text | Starts predefined workflow (e.g. `Process enrichment backlog`) | 3 | 5 workflow buttons with clear Result descriptions (not executed to preserve state) | match | — |
| Librarian | Composer | `Modes: Ask ▾` (blank before hydration) | menu | Selects agent permission mode | 3 | Opens Permission mode menu (`Plan`, `Ask permission`, `Auto`) | match | — |
| Librarian | Composer | `1 lead-m · preset-deepinfra ▾` (blank before hydration) | menu | Selects lead/notes/small-task chat models | 3 | Opens Chat models 1-2-3 role picker + `Filter models` | match | — |
| Librarian | Composer | `Effort` (`4`/`8`) | slider | Adjusts reasoning effort level | 3 | Range slider controlling effort (`8` in hydrated view) | match | — |
| Librarian | Composer | `↗ Open in Obsidian` | text | Opens current library/vault in Obsidian | 3 | External `obsidian://` action button | match | — |
| Librarian | Composer | `Send` | text | Sends message; disabled/no-op if empty | 3 | No-op when input empty (stays enabled visually) | match | — |
| Librarian | Doc Pane | `Note` | tab / disabled | Shows open note content | 3 | Disabled until a note is opened; active & renders markdown once opened | match | No (`title=null`, no adjacent reason when disabled) |
| Librarian | Doc Pane | `Browse` | tab | Lists vault folders and root notes | 3 | Shows `/` with 19 folders & 27 notes | match | — |
| Librarian | Doc Pane | `Plan` | tab | Shows active thread plan | 3 | Shows `"No thread yet."` | match | — |
| Librarian | Doc Pane | `This week` | tab | Shows tasks due this week | 2 | Stuck on `"Loading…"` after wait | partial | — |
| Librarian | Doc Pane | `Read this document` (speaker icon) | icon-only | Reads open note aloud via TTS | 3 | Toggles aria-label to `Stop reading aloud`; fires `POST /api/tts/chunk` (HTTP 400) | partial | — |
| Librarian | Doc Pane | `⋮` (`Note actions`) | icon-only | Opens note context menu | 3 | Opens `Open this note in Obsidian`, `Rename or move…`, `Copy path` | match | — |
| Librarian | Doc Pane | `✕` (`Close the pane`) | icon-only | Closes Document Pane | 3 | Closes Document Pane | match | — |
| Librarian | Doc Pane | `Document pane width` resizer | slider | Dragging widens/narrows pane | 3 | Dragging left widened pane and switched `Pane view` `<select>` into 4 tab buttons | match | — |
| Librarian | Staging | Kind tabs (`Sources 5`, `Folders 29`, `Lenses 9`, `Concepts 0`, `Topics 0`, `Offerings 0`, `From V1 0`) | tab | Switches staged item category | 3 | Switches category (`Sources`, `Folders`, `Lenses` populated; `Offerings` empty) | match | — |
| Librarian | Staging | `Which sources` dropdown | menu | Filters sources by pipeline status | 3 | Filters between `Captured, to review`, `Approved...`, `Ingested...`, etc. | match | — |
| Librarian | Staging | `Review evidence layout` dropdown | menu | Changes draft vs evidence pane layout | 3 | Switches `Evidence beside draft` / `Evidence on demand` | match | — |
| Librarian | Staging | `Refresh` | text | Reloads staging queue | 3 | Reloads staging items | match | — |
| Librarian | Staging | Item `Tick` checkbox | toggle | Selects item for batch `Approve ticked` / `Defer ticked` / `Clear` | 3 | Ticking enables `Approve ticked`, `Defer ticked`, `Clear`; `Clear` unticks | match | Yes (adjacent text `"Tick sources to decide several at once"`; `title=null`) |
| Librarian | Staging | `Approve ticked` / `Defer ticked` / `Clear` | disabled | Batch-act on ticked items (disabled until ticked) | 3 | Disabled until ≥1 item ticked; enabled immediately on tick | match | Yes (adjacent text) |
| Librarian | Staging | Item detail actions (`Approve for ingestion`, `Reject`, `Defer`, `Accept as captured`, `Redraft`, `Deep read`, `View source evidence`) | text | Single-item review actions | 3 | Visible in item detail panel below draft/evidence (long titles overflow horizontally) | match | — |
| Librarian | Staging Folders | `Survey folders` / `Approve selected...` / `Accept unambiguous...` | text | Batch folder classification actions | 3 | Appears in `Folders (29)` tab alongside per-folder Purpose chips | match | — |
| Librarian | Search | `Search query` + `Search` button | text | Runs search across selected scope | 3 | Returns grouped results (`Sources`, `Patterns`, `What this library made`, `workspace`) | match | — |
| Librarian | Search | `Search in` dropdown | menu | Scopes search to library/staging/sessions/activity | 3 | Changes results (e.g. `staging` finds staged folder) | match | — |
| Librarian | Search | `Intent` dropdown | menu | Filters by 8 query intents or `all` | 3 | Single-intent query (`in_text`) switches to flat source-passage list | match | — |
| Librarian | Search | `Source date` dropdown | menu | Filters results by recency | 3 | Re-runs query filtered by date (`any date`, `within a year`, `within 3 years`) | match | — |
| Librarian | Search | Result link + `Not relevant` | text | Opens note / marks result irrelevant | 3 | Result link opens note in Document Pane (`Filters` box stays empty — no scope tiles) | match | — |
| Librarian | Settings | `Find a setting` + Left nav sections | text | Filters settings and switches section | 3 | Switches sections (`Chat behaviour`, `Topics & organisation`, etc.); no Dark/Light theme toggle exists | match | — |
| Geo | Top bar | `Geo Grapher home` logo | icon-only | Navigates to Geo-Grapher root | 3 | Links to `:65417/` | match | — |
| Geo | Top bar | `← Librarian · ACCEPT-02 Testing Library` | text | Returns to Librarian tab/URL | 3 | Navigates back to `http://127.0.0.1:65414/` | match | — |
| Geo | Top bar | `Close` | text | Closes Geo-Grapher for this library | 3 | Title: `"Close Geo-Grapher for ACCEPT-02 Testing Library"` | match | — |
| Geo | Top bar | `←` (`Navigate back`) | disabled | Goes back in workspace history | 3 | Disabled at initial state | match | Yes (greyed out at root; `title="Back"`) |
| Geo | Top bar | `↑` (`Enter parent container`) | icon-only | Moves up one containment level | 3 | Stays at current level when already at top graph container | match | — |
| Geo | Top bar | `Home` (house icon) | icon-only | Resets to top Workspace view | 3 | Restores Workspace overview displaying all checked graphs | match | — |
| Geo | Top bar | `Workspace` / `DataManagement-baseline` breadcrumb | text | Jumps to clicked ancestor level | 3 | Breadcrumb buttons for containment navigation | match | — |
| Geo | Top bar | `Search files, classes, functions…` + `Search intent` | menu | Searches entities/docs by mode | 3 | Typing triggers `"Searching…"` in banner; intent has 3 modes | match | — |
| Geo | Top bar | `Hierarchy` | icon-only | Toggles left Repository hierarchy drawer | 3 | Opens/closes left Hierarchy drawer (`Close hierarchy` inside) | match | — |
| Geo | Top bar | `Settings` (gear icon) | icon-only | Opens Geo-Grapher preferences | 3 | Opens popover with `Dark`/`Light` theme + `Hierarchy width` & `Inspector width` sliders | match | — |
| Geo | Settings | `Dark` / `Light` theme buttons | toggle | Switches UI and canvas theme | 3 | Immediately switches full UI + 3D canvas between Dark and Light modes | match | — |
| Geo | Settings | `Hierarchy panel width` / `Inspector panel width` | slider | Resizes left and right sidebars | 3 | Range sliders (`235`, `330`) | match | — |
| Geo | Hierarchy | `External references` / `Documentation` / `−` collapse / `Close hierarchy` | toggle | Filters tree nodes & collapses drawer | 3 | Checkboxes toggle, `−` collapses root (`aria-expanded="false"`), `Close hierarchy` closes drawer; tree shows `"No children in this hierarchy filter"` | match | — |
| Geo | Main bar | `3D space` / `List` / `Matrix` | tab | Switches architecture visualization mode | 3 | Switches smoothly between 3D canvas, table List, and Dependency Matrix | match | — |
| Geo | Main bar | `Relationships` dropdown | menu | Changes edge visibility preset | 3 | Switches `Exact`, `Internal exact + candidates`, `All uncertainty` | match | — |
| Geo | Main bar | `Abstraction` dropdown | menu | Changes node grouping granularity | 3 | Switches `Interactive Mixed`, `Repository`, `Directories`, `Files`, `Classes`, `Atomic` (`Conceptual Components` disabled) | match | Partial (`Conceptual Components` disabled with no explanation) |
| Geo | Main bar | `Path` / `Nearby` / `Wider` | toggle | Adjusts neighborhood breadth | 3 | Toggles pressed breadth level | match | — |
| Geo | Main bar | `Scope & filters` | text | Expands dependency filter & QI popover | 3 | Opens `Dependency scope` popover | match | — |
| Geo | Scope & filters | `Static` / `Runtime overlay` [disabled] / `Runtime overlay unavailable` | disabled | Toggles static vs runtime edges | 3 | `Static` checked; runtime controls disabled | match | Yes (`Runtime overlay unavailable` + title `"No measured runtime collection is attached to this snapshot"`) |
| Geo | Scope & filters | Subtypes (`calls`, `imports`, `imports_from`, `inherits`) & `tests`/`generated`/`vendor`/`external`/`Include uncertain` | toggle | Filters edge & node categories | 3 | Checkboxes toggle filter state (tight label-to-checkbox spacing visually) | match | — |
| Geo | Scope & filters | `Collapse nearby detail` / `Collapse to focused scope` / `Reset filters` | text | Collapses expansion or resets scope | 3 | Scope-reset action buttons | match | — |
| Geo | Scope & filters | `QI` (`QI algorithm`: `Off` / `Helper balls` / `Directed`) | disabled | Controls QI grouping layout | 2 | Disabled in `Interactive Mixed`; **enabled** when `Abstraction = Atomic` | match | Partial (tooltip `title="Requires atomic grouping and exact static relationships."` only; no visible adjacent text) |
| Geo | Scope & filters | `Configure rules` (+ `Validate and activate rules` [disabled]) | text | Opens YAML rules configuration | 3 | Expands `Rules configuration` (model, YAML textarea, file upload, disabled Validate) overlapping Legend | match | No (`Validate` `title=null`, empty YAML implies why) |
| Geo | Main bar | `Pin selection` (pin icon) | icon-only | Pins selected entity in scene | 3 | Toggles `aria-pressed="true"` | match | — |
| Geo | Canvas rail | `Box select` | icon-only | Enables shift-drag rectangular selection | 3 | Toggles `aria-pressed="true"` | match | — |
| Geo | Canvas rail | `Reset layout` | icon-only | Resets moved/resized bubbles | 3 | Resets manual bubble placement | match | — |
| Geo | Canvas | `Legend` | text | Toggles color/edge/depth legend | 3 | Opens detailed legend (`○ enclosure`, node/edge colors, direction, pattern, size/depth/angle) | match | — |
| Geo | Canvas | `Zoom out` (`-`), `Zoom` slider, `Zoom in` (`+`), `Fit displayed graphs` | slider | Adjusts camera zoom & frames scene | 3 | `Zoom in` `0`→`0.3`, `Zoom out` `0.3`→`0`, `Fit` resets framing (note `Reveal nearby detail` pill overlaps canvas hint text when centered) | match | — |
| Geo | Canvas bottom | `Bundling` slider & `Local EdgeLens` checkbox | slider | Adjusts edge bundling (`0.80`) & cursor EdgeLens | 3 | Checkbox toggles; slider reads `0.8` | match | — |
| Geo | Canvas bottom | `Coverage` | text | Shows extraction coverage & unresolved counts | 3 | Opens `Extraction coverage` popover (`0 exact · 0 candidate · 0 unresolved · 0 parse failures`) | match | — |
| Geo | Right panel | `Inspect` / `Graphs` / `Build` | tab | Switches right panel mode | 3 | Switches cleanly between Inspect, Graphs, and Build | match | — |
| Geo | Inspect | `Overview` / `Links` / `Evidence` / `Agent context` / `Investigate` | tab | Switches entity inspector sub-views | 3 | All 5 tabs switch and show grounded content (Agent context shows token budget `868/8192` + `Copy context JSON`) | match | — |
| Geo | Inspect → Overview | `Enter / frame`, `Copy ID`, `Pin entity`, `Impact direction`, `Find dependants`, `Advanced diagnostics`, `Find identical normal forms` [disabled], `Find WL candidates` [disabled], `Architecture rules` | text | Inspects/frames/queries selected entity | 3 | `Pin entity` toggles to `Unpin entity`; `Find dependants` returns `0 dependants`; `Advanced diagnostics` & `Architecture rules` expand; AST/WL buttons disabled | match | Yes (adjacent `"Normalised AST Not available"`, `"3-hop WL Not available"`; `title=null`) |
| Geo | Graphs tab | `Active graph` dropdown + `Graphs ( 2 )` toggle | menu | Selects active graph & expands graph list | 3 | Switches active graph; `Graphs ( 2 )` toggles graph cards | match | — |
| Geo | Graphs tab | Per-graph checkbox, `Centre` [disabled on active], `Active` [disabled on active], `Colour` dropdown, `Copy…`, `Delete…` | text | Displays, centers, activates, colors, copies, or deletes graph | 2 | Checkbox hides/shows graph; `Centre` on external isolates view to 1 graph; `Copy…` opens inline form; `Delete…` opens inline `"Type the graph label to confirm"` (cancelled) | match | Partial (disabled `Centre` has `title=null`; disabled `Active` has `title="Shared scene members (at most 3)"` which doesn't state "already active") |
| Geo | Graphs tab | `Show declared bridges`, `Repository snapshot`, `Save view`, `Saved views` | text | Toggles bridges, snapshot, saves/loads view | 3 | `Show declared bridges` toggles; `Save view` opens `"Save this workspace"` modal (cancelled) | match | — |
| Geo | Build tab | `Add folder…` | text | Opens folder browser/splitter | 3 | Shows inline `"No folders are browsable. Start the server with --browse-root DIR."` | match | — |
| Geo | Build tab | `Keep only or remove` (scissors workflow) | disabled | Keeps/removes canvas-selected files/folders | 3 | Shows `"Select files or folders on the canvas, then press the scissors... Nothing is selected for this yet."` (scissors icon not rendered at repo-only level) | match | Yes (adjacent text explains why inactive) |
| Geo | Build tab | `Combine graphs` → `Create a physically merged graph` | text | Opens merge plan form | 3 | Expands `New graph name` + `Review merge plan` | match | — |
| Geo | Build tab | `Compare graphs` (`First`, `Second`, `Compare`) | text | Diffs two checked graphs | 2 | Fires `POST /api/graphs/compare -> HTTP 400`, inline alert `"These graphs have no code fingerprints yet, so they cannot be compared"` | partial | — |
| Geo | Build tab | `Link graphs` (`Whole graph`, `Use the selected item` [disabled on To], `Declare link` [disabled], `Review bridge candidates` → `Find candidates`) | text | Declares cross-graph links or reviews candidates | 3 | `Whole graph` fills `root`; `Find candidates` shows `"No pending candidates listed."` | match | No (disabled `Use the selected item` and `Declare link` lack `title` tooltips, though `Why` placeholder says `Required`) |

---

### 3. Light vs Dark Contrast & Console/HTTP Errors Observed
- **Theme behavior**:
  - **Librarian V2**: Dark-only UI (no Light/Dark toggle in `Settings` or header). Contrast is readable overall, though pre-hydration blank pills and overlapping `⏻` menu / overflowed long underscore filenames in Staging (`EXT_O1_2406.04797_Multi_Labe...`) clip or crowd.
  - **Geo-Grapher (`:65417`)**: Supports both **Dark** (default) and **Light** modes via `Settings → Theme`. Both themes have clean text/surface contrast on toolbars and sidebars; however, in **Light mode**, when a single bubble is centered/focused, it renders as a pale cream sphere with modest contrast against the `#E5E7EB` light grey canvas (whereas unselected/multi-graph magenta & teal spheres have good contrast). Also in Geo-Grapher, **`Reveal nearby detail` overlaps canvas bottom hint text**, **`Rules configuration` occludes `Legend`**, **`Entity ID` overflows horizontally** at both `1080×800` and `1440×900`, and `Dependency scope` checkbox labels (`StaticRuntime Observations`, `CallsImports`) sit overly tight.
- **HTTP Errors Observed**:
  1. Librarian: `GET http://127.0.0.1:65414/api/file?path=About%20the%20Librarian%20and%20how%20to%20use%20it.md` → `HTTP 404` on initial load.
  2. Librarian: `POST http://127.0.0.1:65414/api/tts/chunk` → `HTTP 400 Bad Request` on `Read this document`.
  3. Geo-Grapher: `POST http://127.0.0.1:65417/api/graphs/compare` → `HTTP 400 Bad Request` on `Compare` (`"These graphs have no code fingerprints yet, so they cannot be compared"`).
</SYSTEM_MESSAGE>