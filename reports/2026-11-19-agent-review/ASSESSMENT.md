# Assessment of the agent review (2026-11-19)

This checks the review in this folder (`SUMMARY.md`, `REVIEW-UI-UX.md`, `INFERABILITY-SCORECARD.md`,
`LIVE-TEST.md`) against the code and the running products, and records what was fixed. Method: I read the code
behind each finding, reproduced the ones I could cheaply, and fixed the ones that are plainly defects in
Geo-Grapher or in the Librarian's Geo launcher. A finding I could not check is marked **not checked**, not assumed.

## Where the review is right, and where it needs a correction

| Finding | Verdict | Notes |
|---|---|---|
| F-01 empty-catalog deadlock | **Confirmed, fixed** | `Workspace.tsx` treated "no graphs" as "still loading". An empty catalogue now shows an explanation and Add folder. Spec: `build-mode.spec.cjs`. |
| F-02 `lead-m` 404 | **Confirmed, but narrower than stated** | The placeholder is in ACCEPT-02's own `.librarian/app.json` (`tiers[0].model = "lead-m"`). Your global defaults (`app-defaults.json`) name real models, and no code default says `lead-m`. So this is the sandbox's configuration, not a default every library gets. The product gap stands: nothing warns when a configured model id does not exist. **Not changed** (the review was not allowed to touch Models, and neither will I without you). |
| F-03 Ask-mode approval is invisible outside Chat | **Plausible, not checked** | Consistent with how the broker is wired. A header badge for pending approvals is a Librarian UI change (`ui/src`, which another agent has worked in). Needs your decision on the MCP side (open question 3). |
| F-04 Geo MCP `content: []` | **Confirmed, but deliberate** | `server.py:80` says the empty `content` is on purpose ("prevents the SDK duplicating the JSON in text"). Fixed as an opt-in, not a default: `serve-graphs --text-content` (or `GEOGRAPHER_MCP_TEXT_CONTENT=1`) also returns the JSON as text. **Your Antigravity config needs that flag** (see below). |
| F-05 `Add folder…` always fails in a library's Geo | **Confirmed, fixed** | `geo_service.py` passed no `--browse-root`. It now passes the project folders attached to the library (only while project access is on). Geo's page now says how to attach one instead of naming a command-line flag. Tests in `tests/test_geo_service.py`. **Choice for you:** project folders were the nearest existing, person-approved allowlist; say if you want another set (open question 4). |
| F-06 MCP descriptions name arguments that error | **Confirmed, fixed in part** | The hub reused the single-graph guidance, which names `content_kind` and `direction`; the flat tools take neither. Descriptions are now rewritten for the flat form, with a test that no description names an argument its schema refuses. **Not fixed:** `search_entities` hits omit `rel_path`/`kind`; `compile_task_packet` rejects ids both ways; `federated_search` ordering and shape. |
| F-07 cold first search 71 s | **Not checked** | Plausible for a 65k-entity graph. Not touched. |
| F-08 declared links cannot be traversed | **Partly fixed** | Declared links now say "declared by a person, not checked against the code" where they are listed (the review's "in force" read as verified). Clicking the arc to jump to its target is **not built**. |
| F-09 Staging write-conflict | **Not checked** | Librarian UI. |
| F-10 no intake button in Staging | **Not checked** | Librarian UI. |
| F-11 no Desk in the UI | **Probably wrong as stated** | `ui/src/pane.ts` builds a "Desk" section in the note pane's ⋮ menu, but only when a session is open on a project (`currentProject`). The reviewer could not run a project session (F-02), so it never appeared. The real finding is discoverability: the feature is invisible without a project session. **Not checked in the browser.** |
| F-12 Search filters blank, "thin", unmatched noise | **Plausible, not checked** | The Filters element exists (`views.ts:1099`); I did not reproduce it being empty. |
| F-13 Reveal button overlaps canvas help | **Confirmed, fixed** | Reproduced before the fix at 1440, 768 and 375 px (overlap), none after. The button now sits above the camera tools instead of widening them. |
| F-14 Inspect overflow, clipped tab | **Confirmed, fixed** | Long ids now wrap, and the five Inspect tabs fit or scroll instead of clipping "Investigate". Rules and Hierarchy drawers covering the left rail: **not checked**. |
| F-15 scissors only after Box select | **Confirmed, improved** | The Build tab now names the Box select tool, and a file or folder selected in the hierarchy can start a cut with "Use the selected file or folder". The scissors themselves still need Box select. |
| F-16 Compare enabled with no fingerprints; list not refreshing | **Half right** | Compare does fail with a plain message (not a bare 400), but is not pre-disabled: **not fixed**. The "list did not refresh" is a misreading: `Graphs (N)` counts *checked* graphs, and new graphs arrive unchecked. The panel now says so after an ingest ("added 3 graphs… check one to show it"). |
| F-17, F-18, F-21, F-24 | **Not checked** | Librarian UI polish and accessibility. |
| F-19 "0 curves" with bundled arcs on screen | **Fixed, not visually checked** | Documentary links are now counted as curves. |
| F-20 Legend ignores Escape; Matrix headers; Light contrast | **Legend fixed; the rest not** | Escape now closes the Legend (spec added). Matrix headers and Light-theme contrast are untouched. |
| F-22 harness configs disagree | **Confirmed** | `~/.claude.json` points `librarian` at `F:/uv-data/Geo_Grapher`, a code repository the agent guide says never to use as a library. Not changed (your settings). |
| F-23 raw ids, stale Active, Compare items not clickable, stretched × | **× fixed; rest not** | The sheet's close button no longer stretches. The other three are untouched. |
| F-25 | **Not checked** | |

**One scoring caution.** The inferability scorecard reports 95.3% match across 85 controls. The review also lists
several controls with no explanation when disabled and an invisible Desk, so the high match rate comes from controls
that were *visible*. The ones that fail are mostly the hidden ones, which a label-only test cannot see. Read the
figure as "labels are good when you can find the control", not "the interface is 95% clear".

## What changed

Geo-Grapher (`F:\uv-data\Geo_Grapher`): empty-catalogue shell; library-aware folder-picker message; Reveal button
layout; Inspect wrapping and tabs; sheet close button; Legend closes with Escape; curve count includes documentary
links; unverified wording on declared links; Keep only/Remove hint and "use the selected file or folder"; ingest
result says where the graphs went; MCP `--text-content` and corrected tool descriptions. Librarian
(`D:\Librarian_V2`): `geo_service.py` passes `--browse-root` for attached project folders.

## What I need from you

1. **Antigravity config.** To make Geo MCP tools readable there, add `--text-content` to the arguments in
   `C:\Users\jakem\.gemini\config\plugins\geo-grapher\mcp_config.json`. I have not edited it.
2. **`~/.claude.json`.** The `librarian` entry should name a real library, not `F:/uv-data/Geo_Grapher`.
3. **Browse roots for a library's Geo** (review open question 4): is "project folders attached to the library, with
   project access on" the right set?
4. **ACCEPT-02's `lead-m`.** Set `tiers[0].model` to a real model (or tell me to), so the Chat route works there.
5. **The approval badge (F-03) and Staging intake (F-10).** These are Librarian UI changes; say if you want them
   done and by whom, since `ui/src` is shared.

## Not done, in the order I would do it

F-08 traversal (select a declared link, jump to its end); Compare pre-disable; `search_entities` hit fields and the
`compile_task_packet` id handling (F-06); Matrix header wrapping and Light-theme contrast (F-20); Search facets and
"thin" (F-12); the first-search latency (F-07).
