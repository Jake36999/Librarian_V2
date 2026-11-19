# UI review, round 1 (interim): first look

Built-in browser pane (800×600), Resource-Library and Nonlinear Field Lab. No fixes made yet.
Nothing was restarted or written. Evidence is from measurement, not screenshots alone.

## Findings

| # | Severity | Finding | Evidence | Where |
|---|---|---|---|---|
| 1 | blocks a task | **Staging never loads.** The page sits on "Loading…" with no timeout, progress or error. Light endpoints answer in under 2 s on all three Cores, but `staging_list` (`kind:"source", limit:1`) timed out at 60 s on Resource-Library, and `batch_status` took 30.8 s. The first tab of the UI showed "Loading…" for more than 5 minutes. | `probe_staging.py` timings, 2026-11-17 ~11:00. The Cores have used ~19,000–28,000 CPU-seconds since 01:33 (about 0.6–0.8 of a core, sustained). The cause is **not diagnosed**; I do not know whether enrichment work or a slow scan is behind it. | `ui/src/views.ts:267` has no timeout or error state; `tools/staging.py:156` is the slow call |
| 2 | blocks a task | **G: has 5.0 GB free (98% full)** and ingest is already being refused: `DISK_RESERVE: estimated ingest would leave less than 5 GiB` at 10:58. `GROUP_STRATUM_CONFLICT: own and external content cannot share a graph` also appears in `apply-folder-review`. | `~/.config/resource-librarian/logs/geographer-cli.log`, `df` | Needs the owner (free space or move libraries); not a UI fix |
| 3 | slows | **Geo-Grapher memory.** The Nonlinear Field Lab Geo server grew from 1.77 GB to 2.38 GB while loading 6 graphs; the two Core processes add 1.1–1.4 GB each. System RAM was 75%. Ten `serve-graphs` processes share the `F:/uv-data/Geo_Grapher/output/named-graphs` catalog and were started 11-14 to 11-17, so some look orphaned. | PIDs 22732, 18780, 11528; process list | Per-library graph cache has no limit |
| 4 | misleads | **Geo-Grapher first screen shows "6 graph(s) displayed" and "0 groups · 0 curves" with a "Loading…" pill for 30 s or more.** Two POSTs (`/api/graphs/frame`, `/viewport/frame`) were still pending. | network log | `Scene`/workspace load path |
| 5 | misleads | **Geo-Grapher controls are cluttered at 800 px.** The header takes three rows; the colour legend and the thread legend run together as one paragraph. | screenshot | Geo `App.tsx` |
| 6 | polish | Staging sub-tabs are truncated at 800 px ("Sources …", "Folders …"), so the counts are hidden. | screenshot | `ui/src/views.ts` |
| 7 | to confirm | The paperclip menu opens at "Loading…" and its text was still in the page after Escape and after switching to Staging. | page text | `ui/src/pane.ts` |
| 8 | risk | The Cores run code from another session's temporary folder (`…/scratchpad/core-ea6bda2/src/…`), seen in a traceback. A temp cleanup would break a running library. | Core log | host start path |

## Not yet done

Keyboard and contrast checks, the Search and Settings walk, the scratch-library empty-state walk, and Geo graph interaction. These wait on finding 1 and on a scratch Core.
