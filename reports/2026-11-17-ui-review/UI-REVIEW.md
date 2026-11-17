# UI review, 2026-11-17

The owner reported five UI issues while the three libraries were being ingested. Items 1–4 are
fixed in this session; item 5 is scoped below. The last section is a prompt for a fresh session
that runs UI/UX review rounds with Claude in Chrome.

## Items 1–4: what changed

| # | Owner's issue | Change | Where |
|---|---|---|---|
| 1 | No clean way to close Geo-Grapher or the Librarian | Librarian header **Close ▾**: "Close Geo-Grapher" or "Start Geo-Grapher", and "Close this library", a graceful Core stop that lists active work first and only forces after a second confirmed choice. Geo-Grapher gained its own **Close** button; its server exits with code 0 and the Core reports it as closed, not failed. "Geo-Grapher ↗" restarts a closed service. | Librarian `ui/src/main.ts`, `geo_service.py`, `app.py` (`/api/geographer/stop`, `/start`); Geo `LibraryLink.tsx`, `graph_server.py` (`/api/workspace/close`), `cli.py` |
| 2 | Relationships leaving their folder should be slightly faded, and shown only when the connecting graph is displayed | A relationship between two repositories (graphs or reviewed member folders) is drawn at 40% (`CROSSING_FADE`). One whose other end is not displayed is not drawn. Bridges between graphs are drawn only while both graphs are shown, and faded. | Geo `nodeStyle.ts` (`edgeFade`), `Scene.tsx` (shader `aFade`) |
| 3 | Node colour by content in file, function and atomic views | Files by type (code, docs, data, config, notebook, media), tests and generated/vendor apart, symbols by kind (class, function/method, constant, external, atom). Containers stay neutral. A legend sits under the scene. File shells are filled in proportion to their colour so the colour is visible. | Geo `nodeStyle.ts`, `Scene.tsx`, `App.tsx` |
| 4 | Node names misaligned (owner suspected unfinished enrichment) | It was mostly a naming bug, not enrichment. Every graph label began with the library name, so six graphs read "Nonlinear Field Lab-quantule_map…". A reviewed folder's repository showed its internal id `g_…:c695…`. Composed nodes carried "graph label · " into their labels. Now labels drop the library name and shorten in the middle, members of one graph are named by folder, ids are never shown, and a node with no name yet shows no label rather than a hash. | Geo `names.ts`, `api.ts` (`shortName`), `useGraphComposition.ts`, `graph_router.py` (`repo_roots`) |

**Checked in a browser** on a source-tree Geo server over Nonlinear Field Lab's catalog:
- labels read "quantule_mapper", "solver", "third-party-papers · external_valida…" and
  "quantule_mapper-docs · cl_tg_r_ro…";
- Python files show steel-blue;
- Close shows the closed page and the server exits with code 0.

**Not yet live** in the libraries' own Geo views: they run the pinned wheel in
`G:\Libraries\_geo-runtime\env`. To deploy:
1. Rebuild the wheel: `uv build --wheel --out-dir G:/Libraries/_geo-runtime/dist`, with
   `UV_CACHE_DIR=G:/Libraries/_geo-runtime/uv-cache UV_LINK_MODE=copy`.
2. Reinstall it: `uv pip install --python G:/Libraries/_geo-runtime/env/Scripts/python.exe --reinstall-package geo-grapher <wheel>`.
3. Restart each library's Geo service. The new Close ▾ menu does this once the Cores run the
   new Librarian code; a Core restart does it too.

## Item 5 (scope): Staging shows "0 waiting" and browsing shows the bare minimum

**What happens.**
- The Staging page lists Sources through a status filter, "Which sources", whose default is
  "Captured, to review" (`status=staged`).
- In agent mode, every captured source is approved as soon as it is captured, so that bucket is
  always empty.
- The items are in the other buckets. Measured 2026-11-16:
  - Nonlinear Field Lab: 88 enriched, 69 partial, 23 processing.
  - Resource-Library: 124 accepted, 40 partial.
- The filter offers neither "Accepted" nor "Processing" (`ui/src/views.ts:119`), so accepted
  Sources cannot be listed there at all.
- The counter on the Sources tab sums the waiting states, but the list under it shows only
  the chosen state.

**Browse** lists the vault's own folders (`/api/files`, `ui/src/pane.ts:283`):
- Ingested material stays in Staging until it is accepted. Accepting runs the six-step
  promotion into `Sources/`, and no library has done it for this run. So `Sources/` is nearly
  empty and the reading results (points, limits, terms, lenses) are visible only from Staging.
- Attached project folders (the content roots) are not browsable from the pane.

So the UI is not failing to render documents. It shows the one state that agent mode empties,
and it has no view of attached roots or of accepted-only lists.

**Proposed fixes** (not done):
1. Default the filter to the first non-empty state, and show a count beside each option.
2. Add "Accepted" and "Processing" to the filter, read-only where no decision applies.
3. When the chosen state is empty but others are not, say which states hold items. Never show
   a bare "Nothing here".
4. Browse: add the library's content roots (read-only, per their folder decision), and a
   "Staged material" entry that opens an enriched item's reading.
5. Decide, as the owner, whether agent mode should accept enriched Sources into `Sources/`.
   Until then, a library's notes do not include its ingestion.

## Prompt for a fresh session: UI/UX review rounds with Claude in Chrome

> Run UI/UX review rounds on the Librarian and Geo-Grapher, using the Claude in Chrome skill
> (`anthropic-skills:chrome-browser`; load the tools in one ToolSearch call). Work in
> `D:\Librarian_V2` (Librarian) and `F:\uv-data\Geo_Grapher` (Geo-Grapher).
>
> **Start here.** Read `reports/2026-11-17-ui-review/UI-REVIEW.md`, which covers what changed
> today and the Staging/Browse scope. Then read the owner's standing rules in
> `C:\Users\jakem\.claude\projects\D--Librarian-V2\memory\MEMORY.md`.
>
> **Don't disturb ingestion.** Another session may be ingesting into Nonlinear Field Lab,
> Resource-Library and Parallax. Check with `mcp__ccd_session_mgmt__list_sessions` and ask it
> (`SendMessage`) before restarting a Core.
> - Agents manage Cores (`python -m resource_librarian host start|restart|status --vault <path>`),
>   but a restart mid-batch interrupts its work.
> - Never print a token. Open the Librarian UI with the Host's connection record. Get
>   Geo-Grapher's one-time link from `GET /api/geographer` (`open_url`) and keep it out of
>   logs and messages.
> - Prefer a disposable library for anything that writes, for example `init` a scratch vault
>   in the scratchpad.
>
> **Each round:**
> 1. Pick 3–5 real tasks a person does. For example:
>    - find what a library knows about a topic;
>    - review and decide staged sources, including partial ones;
>    - read one enriched paper's points and limits against its PDF;
>    - open the library's graphs, find a file, follow a relationship across graphs;
>    - close Geo-Grapher, then the library, and start them again.
> 2. Walk each task in Chrome at desktop width and at 1024 px. Screenshot every step that
>    confuses, misleads, hides state or is slow.
> 3. Check the empty, loading, error and partial states on purpose. Agent mode leaves "Captured,
>    to review" empty, and enrichment is unfinished in all three libraries.
> 4. Check keyboard-only use and focus order for the task, plus colour contrast in both themes.
>    The Geo node colours are new; check that they stay distinguishable.
> 5. Write findings to `reports/2026-11-17-ui-review/ROUND-<n>.md`. Give each one a severity
>    (blocks a task / misleads / slows / polish), evidence (screenshot path, steps, expected vs
>    actual) and the file and function responsible.
> 6. Fix what is small and clearly right, one finding per commit. Before each commit:
>    - run `npm run check` and `npm run build` in `ui/`, or `npm run typecheck`,
>      `npm run test:unit` and `npm run build` in Geo-Grapher;
>    - run the relevant pytest files, and the full suite in a clean clone;
>    - add a §19 entry in `docs/unified-implementation-plan.md`.
>
>    Commit explicit paths only, never another session's files. Leave larger or debatable
>    changes as proposals for the owner.
> 7. Re-walk the fixed tasks to confirm, then start the next round with tasks the last round
>    did not cover.
>
> **Stop after three rounds,** or earlier when a round finds nothing above "polish". Then
> summarise in `reports/2026-11-17-ui-review/SUMMARY.md`: what was fixed (commits), what is
> proposed, and what needs the owner's decision. That includes item 5's last point, whether
> agent mode should accept enriched Sources.
>
> **Deploying Geo-Grapher front-end fixes:** rebuild and reinstall the pinned wheel as described
> in UI-REVIEW.md, then restart the Geo service (Close ▾ → Close, then Geo-Grapher ↗), not the
> Core.
