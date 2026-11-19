# View-index spike: how small can a graph's loaded form be?

> **Built, same day: Geo-Grapher `a3dd77d`.** The spike's open question (parity) is closed. Evidence,
> analyses and fingerprints became lazy tables (`lazygraph.LazyTable`) that behave exactly as the dicts they
> replace, so whatever needs the whole table still gets it; projection reads only an evidence count per
> relationship; the entity form drops the binary-lifting table. **Parity:** nine frames per graph on the real
> 59k and 297k-entity Nonlinear graphs (radius 1 and 2, child focuses, atomic and kind/file grouping) are
> byte-identical to the full load, with no lazy table filled; the whole Geo suite passes with it on (868
> passed, 1 skipped) plus 9 new tests. **Measured, quiet machine:** 59k entities, after load 750 → 182 MB, load
> 14.8 → 1.5 s; 297k entities, after load 4,278 → 1,105 MB, load 20.5 → 9.5 s, after the frames 4,785 → 1,665 MB.
> Frame time is unchanged. **Live:** one Nonlinear graph in the running Geo: 869 → 375 MB. The lazy-parent-walk
> concern in finding 3 below did not materialise (11 ms frames on the 297k graph). Still open: 1.1 GB for 297k
> entities after load is about 3.7 KB each; a columnar form is the next step if that is too much; the frame
> machinery adds about 250–560 MB on top (partition and layout caches), not yet examined.
>
> The numbers below are the spike's, kept as written.

2026-11-17. Throwaway code only; nothing in Geo-Grapher changed for this. Scripts: `spike/view_spike.py`
(full, lean and compact loaders plus frame digests), `spike/where_memory.py`, `spike/evict_rss.py`.
Real Nonlinear Field Lab graphs, read-only, a catalog copy, one fresh process per measurement.

## Result

| Graph | Loader | RAM added | Load | Median frame | Frames identical to full |
|---|---|---|---|---|---|
| 59,085 entities | full (today) | 662 MB | 3.3 s | 39.5 ms | (baseline) |
| | lean: no evidence, fingerprints or bulk analyses | 430 MB | 1.9 s | 37.2 ms | 5 of 6 |
| | **compact**: also fewer entity columns, shared strings, no binary-lifting table | **121 MB** | **1.3 s** | 36.3 ms | 5 of 6 |
| 296,905 entities | full (today) | 4,172 MB | 37.8 s | 17.8 ms | (baseline) |
| | **compact** | **1,649 MB** | **12.8 s** | 21.2 ms | **4 of 6** |

Six requests per graph: root at context radius 1 and 2, three child focuses, and the atomic-grouping
frame. Identical means the same SHA-256 of the whole response. Frame time does not change; the gain is
memory and load time.

## What it says

1. **Skipping evidence and analyses is not enough.** Lean saves about a third. The weight is in the entity
   and relationship objects: 19 fields per entity, including `ancestors_binary_lifting_json` (up to 1,185
   characters each), two 64-character hashes and repeated repository ids that are separate string objects.
   Dropping unused columns, sharing the id strings and not building `TreeIndex.up` (a Python list table for
   every entity) took the 59k graph from 430 to 121 MB.
2. **The compact form is not yet exact.** On the 59k graph the atomic-grouping frame differs; on the 297k graph
   a child frame at radius 2 differs as well. The atomic path reads evidence details and `declaration:`
   analyses: keeping declarations changed its digest without matching it, and trimmed evidence made the
   request fail. I did not find the full set. So a real index needs a **parity test against the full load** as
   its acceptance gate, not just a memory number.
3. **Parent-pointer ancestor lookup was a guess I did not settle.** I replaced the binary-lifting table with a
   parent walk. One run of the 297k graph showed 2.5 s frames and three errors; a rerun showed 21 ms and none.
   The first run overlapped with ingestion, a live Geo server and my other probes, so I treat it as
   contaminated, but I did not establish the cause. A production version should keep a compact array table
   rather than rely on walking parents.
4. **1.6 GB for 297k entities is still about 5.5 KB each.** The remaining weight (qualified names, paths,
   relationship objects) was not measured. A columnar store is the next step if that is too much.

## Proposed shape of the real thing

- **Two tiers.** A *view context* held per loaded graph: entities (only the columns a frame reads), the tree
  with array-based ancestors, relationships, incidences and the `text:` analyses. A *detail context*
  (evidence, fingerprints, the rest of the analyses) loaded when a request needs it (atomic grouping, witness
  inspection, clone search) and dropped under the loaded-graph cap.
- **Built at ingest or first open and cached on disk**, so reopening does not rescan the 8–18 GB stores.
- **Parity gate in CI:** for fixture graphs, every viewport request type must give a byte-identical response
  from the view context and from the full load, or declare which tier it needs.
- **Memory gate in CI:** bytes per entity for the view context, with today's 12–14 KB as the baseline and a
  target the owner sets (the compact spike reached about 2 KB on the 59k graph).

## Not done, and not verified

- The atomic and radius-2 differences are unexplained.
- Only Nonlinear graphs were measured; Resource-Library's and Parallax's largest stores were not.
- RAM figures are the process working set after load, not a controlled allocation count.
