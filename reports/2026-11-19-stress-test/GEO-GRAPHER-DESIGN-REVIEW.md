# Design Review: Geo-Grapher workspace (2026-11-19)

**Maturity level:** L0 (Greenfield): no `DESIGN.md` or `.ds-context.md` in `F:\uv-data\Geo_Grapher`, so there is no design system to check against.
**Sub-agents run:** Visual Quality Inspector, UX Critic, A11y Auditor, Motion Reviewer. DS Compliance Checker skipped (no DS).
**Artifact:** the live workspace (Resource-Library's Geo service), measured at 1440×900 and 477×1200, the owner's four screenshots, and the code in `frontend/src`.
**Total findings:** 19 (P0: 0, P1: 6, P2: 10, P3: 3)

Measured, not estimated: control sizes, contrast of 40 sampled text elements, chrome heights, the presence of `prefers-reduced-motion`, skip link, landmarks and `lang`. Where a finding rests on reading code, the file is named. The ingestion examples are **illustrations, not output from your libraries**.

---

## The owner's direction, one by one

| # | Direction | Verdict | Why, and the change I'd make |
|---|---|---|---|
| 1 | Two jobs: explore a graph, and build / use tools | **Agree** | This is the right organising idea. It gives the right-hand panel three modes instead of one: *Inspect* (the selected thing), *Graphs* (which graphs and views), *Build* (create and change). See F3 |
| 2 | Zoom +/− become a slider with clickable ends | **Agree** | Use a native range input so keyboard and screen readers work, log-scaled, kept in sync with wheel zoom, with Fit kept beside it. See F8 |
| 3 | Top buttons become icons only, in smaller tiles, moved left | **Agree for canvas tools, not for everything** | The eight layout tools (box select, prune, size ±, move, reset) suit a **vertical icon rail on the canvas's left edge**. Mode and state controls (Path / Nearby / Wider, the two selects, Scope & filters) should keep text: a label is how a person sees which mode is on. See F6, F9 |
| 4 | Back, up and path move into the top bar; search resizes to fit | **Agree strongly** | Two bars become one (about 40px saved, and it removes the narrow-width wrap). Back, up and breadcrumb on the left, search takes the rest, the middle of the path collapses with an ellipsis. See F1 |
| 5 | "Active graph" and "Save view" move into the Inspector | **Agree, with one change** | They describe the *workspace*, not the selected entity. Put them in a **Graphs** mode of the right panel, not in the entity tabs, or the panel mixes two scopes. See F2, F3 |
| 6 | Dark / Light moves to settings | **Agree** | Geo has no settings surface yet, so one is needed (a gear popover: theme, panel widths, legend default). The button currently shows the *target* theme, not the current one. See F7 |
| 7 | A Control panel: new graphs, colours, connections, relational operators, directory ingestion with an ASCII file map | **Agree in principle; change the shape** | The data for the file map already exists, and several operators already exist under other names. The design risks are in what the operators *mean* on a graph, and in not breaking the evidence-first model. See F4, F5, F13 to F15, F18 |

### The relational operators, mapped onto what Geo already has

| Operator | What it would mean on a graph | Already in Geo | Recommendation |
|---|---|---|---|
| **select** (keep rows) | Keep the entities and relationships that match a condition | Prune (box select, then "Create pruned graph"), filters | Offer as **"Keep only…"**; result is a new derived graph |
| **project** | A narrower view of the same entities | `analysis.project` (contracts relationships onto a grouping) | This is a *view*, not a new graph: Abstraction and grouping already do it. Don't add a second control |
| **union** | One graph holding both | Merge (reviewed plan, then "physically merged graph") | Offer as **"Combine…"** (exists) |
| **difference**, **intersection** | What is in A but not B; what is in both | `cross_graph.diff_graphs`: matches entities by fingerprint in four passes (exact code, same contract, same role, same name), not a plain set | Offer as **"Compare…"**, and show the **match kind** instead of pretending identity is binary. The user must see *what counts as the same* |
| **join** | Rows related through a key | Bridges: declared links between graphs, with a rationale and review | Offer as **"Link…"**. A join key has to be chosen and shown |
| **product** (every row with every row) | All pairs of A and B | none | **Don't add it.** On graphs it yields N×M pairs with no meaning. The useful form is *candidate generation* for bridges, which "Find candidates" already does with scoring |

The database-system parts in your list (**data dictionary, schema manager, database engine, query system, forms generator**) mostly exist under other names: the wire schema and relationship families are the dictionary, the rules YAML ("Configure rules") is the schema manager, the snapshot store and catalogue are the engine, and search, find-dependants and task packets are the query system. **A forms generator has no counterpart and I'd leave it out.** The aim is a graph tool that borrows the operators' *clarity*, not a SQL console.

---

## What's working

1. **The Inspector tab strip is a correct tab pattern**: `role="tablist"`, roving tabindex, Arrow / Home / End (`Inspector.tsx:538-573`). Reuse it for any new tab and don't invent another.
2. **The evidence-first model is visible in the controls**: declared bridges need a rationale and a review, graph deletion needs the graph's label typed, and ingestion is a *preview with per-partition opt-out* before anything is written. These are the right safeguards (Error Prevention, Tolerance for Error) and the new Control panel must not weaken them.
3. **Accessibility basics are in place and measured**: `lang`, a descriptive title, a skip link, `main` / `nav` / `header` landmarks, and a `prefers-reduced-motion` rule. Of 40 sampled text elements none failed 4.5:1.
4. **The layout tools already carry explicit accessible names** (for example "Size +: enlarge selected nodes"), so they can become icons without losing their names.
5. **List and Matrix views are real non-spatial alternatives** to the 3D scene, which is what a canvas-first tool needs for people who can't use drag and wheel.
6. **No horizontal scroll at 477px**, and the popover dismissal fixed earlier today (Escape, outside press) is the right base for new panels.

---

## P0: Blockers

| # | Category | Sub-agent | Location | Issue | Effort | Fix |
|---|---|---|---|---|---|---|
| | | | | None | | |

## P1: Major

| # | Category | Sub-agent | Location | Issue | Effort | Fix |
|---|---|---|---|---|---|---|
| F1 | Layout `[cross-dim]` | Visual, UX | Top of the page, narrow width | At 477×1200 the controls around the canvas take **627px of 1200 (52%)**: app header 175px over 3 rows, navigation bar 39px, the Hierarchy / Inspector toggle row 43px, heading 117px, filter bar 127px. The canvas is 48% of the window. At 1440 the same pieces take 347px of a 731px column | M | One top bar: logo, back, up, breadcrumb, search (flex), then a few icons. Fold the Hierarchy / Inspector toggles into that bar's icons at narrow width. This is your direction 4 |
| F2 | Consistency | UX | Header: "Active graph", "Graphs (N)", the third select | **Three look-alike selectors for one idea.** "Active graph" (a select), "Graphs (N)" (a checklist with "Active" and "Centre" buttons), and a third select that is the *snapshot* picker with **no visible label** (only a screen-reader label). A person can't tell them apart (H4, H6) | M | One **Graphs** mode in the right panel: the list of graphs with the active one marked, the checked set, and the snapshot as a labelled "Revision" row. Your direction 5 |
| F3 | Structure | UX | Right panel | Dropping "Active graph", "Save view" and a Control panel into the existing **five** entity tabs makes seven tabs at 330px and mixes two scopes: what is selected, and what the workspace is. Hick's Law and H4 | M | Two levels. Top: **Inspect \| Graphs \| Build**. Inside Inspect, the current five tabs. Widen the panel's default to about 360px |
| F4 | Meaning | UX | Control panel: operators | The operators need a **definition of "the same entity"**. Without it, intersection and difference are guesses. Geo's own diff has four match kinds, not a yes / no. Product has no useful graph meaning (see the table above) | L | Task-language buttons (Keep only, Combine, Compare, Link). Always show a **preview with counts** before running, name the match kind, and produce a **new derived graph** (never change the source). Drop "product" |
| F5 | Honesty | UX | Control panel: add / remove connections | Letting a person add or delete relationships *inside* a graph breaks "evidence-backed": extracted relationships are facts with evidence. Mixing hand-made ones in would make the graph look more certain than it is | M | Hand-made connections are **declared links** (the existing bridge: gold, needs a rationale, reviewable, removable) and are drawn and counted separately. "Remove" means remove a declared link, or **hide** an extracted one with a filter. Never delete an extracted relationship |
| F6 | Accessible names | A11y | The toolbars, after the icon change | Moving to icons only is a 4.1.2 risk if done carelessly. Several current controls use plain unicode glyphs (← → ↑ ↓) and a few labels are ambiguous as pictures (Prune, Box select, Pin) | M | One icon set with one stroke weight; every icon button gets an `aria-label`, a visible focus ring and a tooltip that also opens on focus (`title` alone does not work on touch). Keep text on ambiguous or stateful controls |

## P2: Minor

| # | Category | Sub-agent | Location | Issue | Effort | Fix |
|---|---|---|---|---|---|---|
| F7 | Consistency | UX, A11y | Theme button | The button shows the **target** ("Light" while the UI is dark), so it reads as a status. The default theme is fixed to dark (`App.tsx:101`) instead of following `prefers-color-scheme` | S | Move to a new settings popover as a Dark / Light / System choice that shows the current one. Settings also takes panel widths (now hidden inside the Coverage popover) and the legend default |
| F8 | Zoom | UX, A11y | Camera controls | A bare slider is a worse target than a button for a small precise step, and zoom is not linear | S | A native `<input type="range">`, log-scaled, with `aria-valuetext` ("zoom 2.4×"), ± ends of at least 32px, in sync with wheel zoom, with **Fit** kept |
| F9 | Visual | Visual | Layout tools row | Six of ten tools are **disabled** when nothing is selected, so the row is mostly inert controls | S | In the icon rail, show the selection group only when something is selected; keep Box select and Reset layout always |
| F10 | Target size `[systemic]` | A11y | Whole page | **All 163 interactive controls are under 44px** (typical 32 to 37px; the smallest is a 15×16 checkbox). This passes WCAG 2.2 AA's 24px minimum but not the 44px touch standard, and the icon tiles you want would make it worse | M | One fix, not 163: a minimum hit area of 32px on desktop and 44px at narrow widths via padding, not by enlarging the glyph |
| F11 | Empty state | UX | Canvas on a sparse graph | A graph of two sources renders **one huge blank sphere** with no hint of what to do next (H1, H10). It is the first thing a new user sees | S | A short in-canvas message: "2 sources. Enter a container to see what is inside it", with the action |
| F12 | Language | UX | Toolbar and filter bar | Internal terms: **QI**, **EdgeLens**, **Bundling 0.80**, "Production · exact dependencies", "Interactive Mixed", "Impact direction" (H2). The QI sentence was already moved to a tooltip | M | Plain names with the term in the tooltip; group the technical ones under an "Advanced" disclosure |
| F13 | Ingest review | UX, Visual | Control panel: directory ingestion | The current review is a four-column table. An ASCII file map needs about **60 monospace columns**; the right panel holds about 44. It will wrap and become unreadable. ASCII is also poor for screen readers | M | Open the review as a **wide sheet** over the canvas (the panel only holds the entry point and status). Render an interactive **tree** (`role="tree"`) with a **Copy as ASCII** button, so the text form is for pasting and the tree is for using |
| F14 | Ingest review | UX | Ingestion preview | A person can include or exclude a partition but **cannot change its role**. Every classification is a suggestion (`accepted: False`), so a wrong guess can only be dropped, not corrected | M | Per-folder role control (internal, external / third-party, data, logs, withhold) that records the person's choice and the reason |
| F15 | Policy | UX | Classification | Your example has an **"unlicensed"** group. Today's policy flags a folder because a licence file is **present** ("review upstream ownership"), a nested Git repository whose ownership is unconfirmed, a vendor-style name, PDF-dominant or bulk-data content. **A nested repository with no licence at all is not a signal.** This needs an owner decision, not a guess | M | Decide the rule (for example: a nested repository with no licence file is treated as external and withheld until reviewed), then show it in the map with its reason |
| F16 | Colour | UX, A11y | Control panel: colouring graphs | Colour already carries meaning here: node colour is *content type*, edge colour is *relationship family*, and the legend explains both. A free colour choice adds a third channel and can clash with those hues (1.4.1) | S | Colour is a per-graph **accent** (outline, label chip) from a small reserved set that avoids the semantic hues, with a text or pattern cue as well; never recolour nodes or edges |

## P3: Cosmetic

| # | Category | Sub-agent | Location | Issue | Effort | Fix |
|---|---|---|---|---|---|---|
| F17 | Tokens | Visual | Whole page | Border radii of 5px, 6px and 0 mix; font sizes of 10, 11, 11.9, 12 and 14px (11.9px is an off-scale near-duplicate of 12). There is no token file to check against (L0) | S | Define a small type and radius scale, and a `DESIGN.md` so the next review has something to conform to |
| F18 | Legibility | Visual, A11y | Legend, scope note | 10px text in the legend and the coverage note | S | 11px minimum, 12px for the legend |
| F19 | Motion | Motion | Camera, observed edges | The camera move is 320ms (matches the 300ms panel standard) and `prefers-reduced-motion` is read in `Scene.tsx:433`. Observed edges **pulse indefinitely**; I did not confirm the pulse itself stops under reduced motion | S | Confirm the pulse stops under reduced motion and offer a user pause (WCAG 2.2.2) |

**Contrast failures:** 0 of 40 sampled. **Keyboard issues:** none found in the tab strip and popovers; the 3D scene's keyboard tools (arrows, zoom) must survive the redesign. **Motion a11y:** `prefers-reduced-motion` addressed; the pulse unconfirmed.

---

## Target layout (a sketch, not a mock-up)

```
┌ top bar ──────────────────────────────────────────────────────────────────────────────┐
│ ◉ Geo  ‹ ↑  Home / Workspace / Librarian rese…papers   [ search (grows to fit)    ] ⚙ │
├────────────┬───────────────────────────────────────────────┬──────────────────────────┤
│ Hierarchy  │ ┌─┐                                           │ [Inspect] Graphs  Build  │
│            │ │▢│  Relationships ▾  Abstraction ▾  Path│Nearby│Wider                  │
│ ▸ Alpha    │ │✎│                                           │  Overview Links Evidence │
│   app.py   │ │＋│            canvas                         │  Agent Investigate       │
│            │ │－│                                           │                          │
│            │ │⟲│                              ─●────  Fit  │                          │
│            │ └─┘  vertical icon rail                       │                          │
└────────────┴───────────────────────────────────────────────┴──────────────────────────┘
```

## Ingestion map (illustration only: not output from any of your libraries)

```
sample-project/                               [internal] code · 214 files
├─ src/                                       internal   code
├─ docs/                                      internal   docs
├─ legacy/                                    internal   legacy        name signal
├─ papers/                                    external   research docs  PDF-dominant
├─ vendor/zlib/                               external   third-party   name signal · licence file present
├─ tools/forked-lib/                          external   third-party   nested Git repository · ownership unconfirmed
├─ data/runs/                                 data       bulk data files
├─ node_modules/                              excluded   hygiene
└─ secrets/                                   refused    credential folder

 internal 3 · external 3 · data 1 · excluded 1 · refused 1      [Copy as ASCII]
```
The roles and reasons shown are the ones the ingestion plan already produces (`workspace_init.py`: current, legacy, docs, third_party, external_reference, research_docs, data, transcripts; reasons such as "nested Git repository; ownership unconfirmed" and "licence file; review upstream ownership").

---

## Summary

The new direction is sound: two jobs (explore, build), one top bar, tools on a rail, and a right panel with modes. The two things that most need care are **what the operators mean on a graph** (identity and a preview, new graphs only, no product) and **keeping hand-made connections apart from extracted facts**. The ingestion file map is the easiest high-value piece: the data is already produced by the preview, and it needs a wide sheet, a role override and one policy decision about "unlicensed".

**Suggested order:** (1) one top bar, vertical icon rail, zoom slider, settings popover: F1, F6 to F10, F17, F18, mostly CSS and layout; (2) the right-panel modes and the Graphs mode: F2, F3; (3) Build: the ingest file map first (F13 to F15), then Compare / Combine / Keep only on the existing operations (F4), then declared links (F5), then accent colours (F16).
