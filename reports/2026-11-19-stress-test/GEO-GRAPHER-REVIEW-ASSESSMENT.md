# Geo-Grapher review: claims checked, suggestions assessed (2026-11-19)

Checked live on Resource-Library's own Geo service at 1440×900, read-only (no graph was edited, copied,
deleted or created; the one-time entry link came from that library's Core). Tags: **verified** = I measured
or reproduced it; **not checked** = I did not open that graph.

## The reviewer's claims

| Claim | Result | What I saw |
|---|---|---|
| The canvas is starved of space | **verified** | Canvas 875×383 = **25.9%** of the window (the review said 23.4%). In the 730px centre column the controls and notes around it take **347px**: heading 110, filter bar 148, scene controls 51, scope note 38. The two side panels take another 31.8% of the window. The top header measured **96px**, not 175px; I would not rely on the 175 |
| Popovers do not close on Escape or outside click | **verified** | Opened Scope & filters, pressed Escape, then clicked outside: still open both times. Cause: they are native `<details>` elements (Graphs, Scope & filters, the merge-review and bridge-review panels), which have no dismiss behaviour of their own |
| Scope & filters opens over its own trigger | **verified** | Its panel (255–535 × 285–846) fully covers the trigger (259–… × 357–389) |
| `Graphs (N)` overflows the right edge, clipping `Delete…` | **not reproduced** | At 1440 its panel ends at x=1165. It may clip at narrower widths; I did not test them |
| `Add folder…` is disabled | **verified, but see below** | The panel says "No folders are browsable." |
| Raw hashes, agent-context JSON and paper diagnostics crowd the Inspector | **partly checked** | The entity id is shown in full under the title; Advanced diagnostics and Architecture rules are already collapsed. I did not open Agent context |
| Overlapping labels on the 20k-entity graph; "Graph detail unavailable" on the 65k-entity graph; aborted requests; duplicate Links rows; the List drawer over the switcher; multi-graph overlay after switching | **not checked** | I did not load those graphs. Loading a 65k-entity graph in the user's real library is not a read-only act in cost terms |

## The suggestions

**Agree, in this order**

1. **Give the canvas the room.** Collapse the filter bar to one row (Relationships, Abstraction, Breadth) with the rest behind a `Layers & filters` popover; move the legend and mouse hints into a corner `?` toggle. Target: chrome of about 150px, not 347px. This is the largest gain and the cheapest.
2. **One dismiss behaviour for every popover.** Escape, outside click and a viewport clamp, in one helper. Anchor Scope & filters below its trigger, not over it. This is a small change; Librarian already does it (its smoke test checks Escape and focus return on every overlay), so the pattern exists to copy.
3. **Progressive disclosure in the Inspector.** Open by default: Summary, Folded source, Links and Evidence. Collapsed: Agent context, diagnostics, rules. Agent context is the product for agents, so keep it, collapsed. Show a short name with a Copy button instead of the full hash.

**Agree with a change**

- **A compact one-row header** is right, but the saving is smaller than claimed (96px now, so about 45px back), so do it after items 1 to 3.
- **"Librarian-style tiles"**: use them for the secondary controls only (QI, bundling, EdgeLens, rules). Abstraction and breadth are the controls people use constantly and should stay in view.

**Disagree**

- **A standalone onboarding walkthrough and a "New graph" flow.** In a library, Geo-Grapher is Librarian's extension, not a separate product. The graphs come from the library's folders (Librarian's Staging → Folders review), so `Add folder…` and `Create a physically merged graph` are controls that cannot apply there. The right fix is to **hide them or explain them** ("Graphs for this library are built from its folders in Librarian"), with a link back, not to build a second way in. A short empty-state hint on a sparse graph ("2 sources: add folders in Librarian to grow this") is the onboarding worth having.
- **Creating a test graph on `E:\`.** No: `E:\DataManagement` is out of bounds for this work, and nothing here needs it.

## For the Librarian side

1. **Open Geo on the graph the person last used** (or the library's own current graph), not the first alphabetically. The review opened on a two-source graph, which is the worst first impression of the tool.
2. **The Geo-Grapher header button should show state.** The Settings row now says running, starting, failed, or not set up; the header button should carry the same, so a library with no Geo runtime does not offer a dead link.
3. **"Open in Geo-Grapher" from a source or folder note**, focused on that entity. This needs support on the Geo side and is the strongest link between the two UIs.
4. **Share one small popover/dismiss spec** between the two UIs, so the two tools behave the same.

## Status

Done in Geo-Grapher (`F:\uv-data\Geo_Grapher`, commit `bb5c708`, branch `feat/per-library-service`, **not pushed**):
canvas space (filter bar 148 → 86px, header 95 → 64px, canvas 26% → 31–33% of the window), one dismiss
behaviour for every floating panel (Escape, outside press, focus back to the trigger), Scope & filters
opening under its trigger, the legend behind a toggle, and the opaque id no longer shown as a name in the
Inspector. The Inspector already had its tabs, so that suggestion needed little.

**Deployed 2026-11-19** to all four libraries with Geo (ACCEPT-02, Nonlinear Field Lab, Parallax,
Resource-Library). The wheel was built from a clean export of `bb5c708` plus the built front end; it differs
from the previously deployed wheel only in line endings and the new bundle. It was reinstalled into
`G:\Libraries\_geo-runtime\env` and each library's Geo was restarted through its Core (4 s each; every Core was
idle, no turn, action or batch running). Each now serves the new bundle. The Cores themselves were not restarted.
Rollback: `uv pip install --python G:/Libraries/_geo-runtime/env/Scripts/python.exe --reinstall-package geo-grapher --no-deps G:/Libraries/_geo-runtime/dist/previous/geo_grapher-0.2.0-before-bb5c708.whl`,
then restart each Geo (Close ▾ → start, or `POST /api/geographer/stop` then `/start`).

**Top bar, rail and zoom slider deployed 2026-11-19** (Geo-Grapher commit `fa33b96`, same four libraries). The
wheel was built from a clean export of `fa33b96` plus the built front end (bundle `index-QS4Fiqmj.js` /
`index-Bdrl7Mc9.css`), reinstalled into `G:\Libraries\_geo-runtime\env`, and each library's Geo was restarted
through its Core (about 2 s each; every Core was idle: not busy, no running action). Each serves the new bundle
and still lists its graphs (2, 6, 7 and 16). On the real Resource-Library, in Edge: at 1200×760 the header is one
row of 51px and the canvas is 54% of the window (it was 26%); at 477×1200 with 3D space on the canvas is 71%.
That width opens in List view by default, as before. No page errors. One install detail: the default uv cache is
on C: and uv cannot move files across drives, so the install needs `UV_CACHE_DIR=G:\Libraries\_geo-runtime\uv-cache`.
Rollback: `uv pip install --python G:/Libraries/_geo-runtime/env/Scripts/python.exe --reinstall-package geo-grapher --no-deps G:/Libraries/_geo-runtime/dist/previous/geo_grapher-0.2.0-before-fa33b96.whl`
(with the same `UV_CACHE_DIR`), then restart each Geo.

Still open: the Inspector's
member list still shows an id-looking entry for a repository root; the 20k and 65k-entity graph claims were
not checked; the pre-existing failing test "search hides stale matches while a newer query is pending".
