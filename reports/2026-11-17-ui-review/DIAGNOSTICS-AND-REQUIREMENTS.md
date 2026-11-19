# Diagnostics and proposed development requirements, 2026-11-17

Measured on this machine today. "Measured" means I ran it; "read" means I read the code and did not
run it; "not checked" is stated where it applies. Scripts are in the session scratchpad
(`probe_staging.py`, `staging_size.py`, `geo_mem.py`, `geoprocs.ps1`, `cpu.ps1`).

## Diagnostics

### D1. Staging never loads (blocks a task)

| Fact | How known |
|---|---|
| `staging_list` timed out at 60 s on every Core; `batch_status` took 30.8 s; plain endpoints took under 2 s. | measured |
| `staging_list` calls `store.counts()`, which parses **every staging file of every kind**, including the `folder` kind (`staging.py:164`, `tools/staging.py:178`). | read |
| Folder cards: Resource-Library 12,722 files / 63.5 MB; Nonlinear Field Lab 1,584 / 10.4 MB; Parallax 15,543 files / **213 MB**, the largest single card 25 MB. One full scan takes 2.6 s, 0.5 s and 3.7 s warm, in a separate process. | measured |
| The Cores are also busy with live ingestion: Resource-Library 1.7 cores, Parallax 1.2, Nonlinear 0.2 sustained, with **no UI open**. Detached scripts from the two earlier sessions are still running (`run_phases.py both`, `run_parallax.py`, `budget_supervisor.py`, `watchdog.py`). No session shows as running. | measured |
| The UI issues several `staging_list` calls at once (`commands.ts:64-66`, `views.ts:267`); each repeats the full scan. | read |

**Cause (likely, not proven end to end):** an O(all files) scan on every call, repeated by parallel calls,
on a Core whose single process is also doing ingestion. I measured a single scan, not the multiplied
case. My own timing probes added some load while I measured; the 60 s result held across three Cores.

### D2. Geo-Grapher memory and the stuck "Loading selected graphs…" (slows)

| Graph (Nonlinear Field Lab) | Entities | Load time | RAM added |
|---|---|---|---|
| quantule_mapper (graph 1) | 59,085 | 3.7 s | 731 MB |
| quantule_mapper (graph 2) | 25,901 | 2.2 s | 362 MB |
| quantule_mapper (graph 3) | **296,905** | **34 s warm, 101 s cold** | **4,237 MB** |
| three small graphs | 37, 2,161, 3 | under 0.3 s | 41 MB |
| **All six** | | | **5,410 MB** |

- About **12–14 KB of Python memory per entity**, from entities, evidence and analyses held as objects, plus
  source bytes (`service.py:76`). Measured.
- `compose_frame` accepts 1–19 graphs (`graph_composition.py:41`); the active-set endpoint accepts 1–4
  (`graph_server.py:371`); the UI showed "6 graph(s) displayed". There is no consistent cap. Read.
- Each service keeps up to 4 snapshots (`service.py:80`), but `router.services` has no size cap and
  services close only when a newer generation retires them (`graph_router.py:163`). Loaded graphs stay in
  RAM until the process exits. Read.
- What the browser draws is small: 120 nodes and 200 curves per graph (`graph_composition.py:66`). Read.
  So the memory is the server's graph model, not the picture.

**Cause:** the server loads a whole graph into Python objects for any view of it, loads all selected graphs
before replying, and never evicts. The stuck pill is the sequential load of up to 5.4 GB.

### D3. Process sprawl (slows)

Ten Geo servers and about eight Librarian MCP servers were running, each owned by an idle Claude Code
session left open from 11-14 to 11-17. Cores started before the close-route change return 404 on
`/api/geographer/stop`, so the UI could not close their Geo service (measured: two Cores returned 404).
RAM was 75% before cleanup, 68% after stopping seven Geo servers. The Cores themselves run code from another
session's temporary folder (`…/scratchpad/core-ea6bda2`), seen in a traceback.

### D4. Disk (blocks a task, needs the owner)

G: has 5.0 GB free. Ingest is refused with `DISK_RESERVE` (geographer CLI log, 10:58).

### D5. Not yet checked

- Whether the new faint inter-globe threads draw correctly (needs a Geo server; held off to avoid reloading
  5 GB).
- Keyboard order, contrast in both themes, Search and Settings, empty states on a scratch library.

## GPU question

Moving the graph to VRAM does not fit what D2 measured. The cost is Python objects in system RAM, not
geometry. Rendering already runs on a GPU (whichever the browser uses) and draws only a few hundred
elements. The GTX 1080 has 8 GB and 0 MiB used, but VRAM cannot hold Python objects; it would need the
graph rebuilt as flat numeric arrays, and GPU graph libraries I know of (RAPIDS) require a newer GPU
generation than the 1080 (**not verified**). The cheaper win is to stop holding 12–14 KB per entity (R3, R4).
The GPU is a fair candidate later for the new "open folder becomes the vector space" layout, once measured.

## Proposed requirements for the development workflow

Numbers are starting points for the owner to set.

**R1. Staging reads cost O(page), not O(vault).** Keep counts in an index updated on write, or exclude
`folder` from list calls unless asked. Gate: on a fixture of 15,000 folder cards, `staging_list` p95 under
1 s while a batch runs.

**R2. Every loading state has a timeout, a cause and a retry.** After 15 s, a region says what it waits
on and offers Retry. Gate: a UI test that stalls the API and expects the message.

**R3. A memory budget is a test.** Geo loads at most 3 graphs; the least recently used is evicted; the
active-set and compose endpoints enforce the same cap and the UI says which graph was dropped. Gate: a test
that opens 6 graphs and asserts resident size and the cap.

**R4. Load by need.** Index the tree and labels first; read evidence, analyses and source bytes only when
a witness or file is opened. Target under 1 KB per entity for the first frame, measured in CI with the
per-entity figure from D2 as the baseline.

**R5. One owner per process.** One Geo service per library, owned by its Core; `host status` and
`host doctor` list orphans and offer to stop them; MCP servers exit when their session goes idle or ends;
the stop route exists in every Core version; Cores run from an installed copy, not a scratch folder.

**R6. A finding needs a number.** Each review round commits its probe script and records the measurement
with the finding, as above.

**R7. Disk reserve is visible.** The UI shows free space and the reserve before ingest is refused.

**R8. Geo-Grapher UI design spec (to write next).**
- A. One central controls panel scoped to Geo's tasks.
- B. A visual toolkit with sliders for node and thread spacing; with a globe selected, its corner resizes it,
  while its edge or centre moves it.
- C. Hot keys, starting with Enter to enter the selected globe, so the open directory becomes the vector
  space for its children (the structure you described).
- D. Fewer simultaneous legends: colour, thread and direction legends on demand, not one paragraph.

**R9. Librarian UI consistency.** One layout and one set of patterns across the paperclip menu, Settings,
Staging and Search; file navigation centralised in Search and the right panel; the paperclip menu split into
workflows, tools, add file and add folder; power buttons bottom right and in Settings.
