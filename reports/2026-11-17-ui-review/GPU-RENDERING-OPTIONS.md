# Moving Geo-Grapher's display to the GPU: what the measurements say

2026-11-17. Machine: GTX 1080 (8 GB, idle) and Radeon RX 5500 XT (drives the display and runs the
browser's WebGL), Node 24, Python 3.11 in the pinned Geo runtime. "Measured" means I ran it in a throwaway
process or in the browser pane; "read" means I read the code; "estimated" and "not verified" are marked.
Scripts are in the session scratchpad (`frame_variants.py`, `frame_time.py`, `first_frame.py`,
`load_profile.py`, `curves_bench.mjs`, `catalog_sizes.py`).

## Short answer

Rendering is not the slow part, and the graph is not "pre-computed" in the sense that matters. Moving the
display to VRAM would change a path that costs about 2 ms a frame. The costs sit in three other places, and
each has a cheaper fix than a new language or a new GPU path. One part of the display is a genuine GPU
candidate: the curve maths.

## Two premises to correct

1. **"We already pre-compute the graphs."** What is stored is the full graph, and it is large: the Nonlinear
   Field Lab graph stores are 8.3 GB, 3.0 GB and 18.5 GB; Resource-Library's docs graph is 13 GB (file sizes,
   measured). Every view first loads a whole graph into Python objects (59,085 entities: 3 s warm and
   731 MB; 296,905 entities: 34 s warm, 101 s cold, 4.2 GB). Then the server computes a frame. The browser
   only ever receives a budgeted frame (`node_budget=120`, `curve_budget=200` per graph, read from
   `graph_composition.py:66`).
2. **"The curve maths is native to NVIDIA displays."** The curves are B-splines evaluated **on the CPU in
   JavaScript** (`frontend/src/curves.ts`, de Boor), then drawn as plain line segments. WebGL has no spline
   primitive. The nodes are already GPU-instanced (`InstancedMesh`, `Scene.tsx:784`).

## Where the time goes (measured)

| Stage | Cost | Notes |
|---|---|---|
| Load a graph into the server (`store.graph`) | 3.1–3.6 s for 59k entities; 34 s for 297k; 12–14 KB RAM per entity | 2.2 s is inside one function reading rows, 0.8 s is JSON decoding 105,671 blobs |
| First frame after load | 1.5 s warm (5.7 s on a cold disk cache) | one-time tokenizer load, base64 decoding of 199,998 records |
| **Every frame, server** | **33 ms** (median, 59k-entity graph) | **25 ms is the JSON-schema pass**; pydantic only gives 8.3 ms; no validation gives 6.5 ms (the layout and packing itself) |
| Rebuild curves in the browser | 8 ms (1 graph), 22 ms (3), **42–53 ms (6)** | the CPU spline evaluation; runs on data change, the beta slider and the hover lens |
| Draw, browser GPU | **about 2 ms** for a synthetic full budget (6 graphs, 553k triangles, 57,600 line segments); 7.7 ms with three-times-larger overlapping shells | plus about 1 ms to re-upload the line vertices (1.4 MB) every frame |
| A real frame in the pane | 30 nodes, 0 curves, 2 draw calls, 60 fps | `?debug` metrics on the AMD card |

Caveats: the GPU figure is a simplified shader, not the app's own scene, so treat it as an order of
magnitude. Caching the JSON-schema validator made no difference (32.7 ms against 33.0 ms), so the walk
itself is the cost, not its construction. The profile of the load path is for one graph.

## Options, ranked by what they buy

| # | Change | Buys | Cost / risk | Evidence |
|---|---|---|---|---|
| 1 | **Skip the JSON-schema pass on the hot path** (`wire.py:84`); keep strict pydantic; run jsonschema in tests and on a sample of calls | server frame 33 → about 8 ms (4×); six-graph refresh about 200 → about 50 ms | one-line change plus a test; loses one validation layer at runtime | measured |
| 2 | **Compact view index built at ingest**, so a view loads the tree, labels and aggregated relationships, not every entity, evidence and analysis row; cap loaded graphs at 3 with eviction | removes the 10–100 s waits and most of the 5.4 GB; fixes your item-5 RAM problem | the biggest piece of work; needs a format (Arrow, numpy memmap or sqlite) and lazy detail loads | cause measured; gain estimated |
| 3 | **Evaluate the B-splines in the vertex shader** (TypeScript and GLSL, same three.js stack): control points in a texture, `t` per vertex, beta and lens as uniforms | rebuild cost 8–53 ms → about 0; slider and hover lens become free; no line re-uploads | picking and the selected-edge line read the CPU positions today (`edgePoints`, `segmentIds`), so hover needs CPU evaluation for one curve or GPU picking; medium effort | the CPU cost measured; the shader design not built or tested |
| 4 | numba `@njit` on the layout | little: the layout is about 6.5 ms already | low value | measured |
| 5 | GPU compute (CuPy or numba-CUDA on the GTX 1080) | nothing today; a good fit later for the new "open a folder and it becomes the vector space" layout when it must place thousands of children | needs the numbers first; CuPy and numba-CUDA run on Windows and the 1080 (compute 6.1), not verified here | estimated |
| 6 | Rust (PyO3) for the loader, validator or layout | real gains on the load path (JSON decode plus object build) | large; defer until 1 and 2 are measured | estimated |

## Options that do not fit

- **Render on the NVIDIA card.** Windows can assign Claude or Chrome to the 1080 in Graphics settings, but
  the AMD card already draws a full-budget frame in about 2 ms, and a render card that is not the display
  card adds a copy. No gain to chase.
- **JAX.** Official GPU wheels are Linux and WSL2 only, so the 1080 would need WSL2 (not verified), and
  nothing here is a numeric kernel at scale.
- **Plotly.** It cannot express the instanced shells, the fading directional threads, the dashed and
  pulsing statuses, or the per-edge fade that `Scene.tsx` does in its shaders. It would lose features.
- **Tauri and Rust as a shell.** Tauri hosts the same WebView2 WebGL the browser uses, so it does not change
  draw speed. It could help packaging and the footprint of the app window; that is a separate decision.

## Suggested order

1. Option 1, then re-measure the six-graph refresh (small, safe, measured).
2. Option 2, with the graph cap, because this is what the owner waits for and what fills RAM.
3. Option 3 when the hover lens or the beta slider feels slow at three or more graphs.
4. Keep the GTX 1080 for option 5 once the folder-as-vector-space layout exists and has a measured cost.
