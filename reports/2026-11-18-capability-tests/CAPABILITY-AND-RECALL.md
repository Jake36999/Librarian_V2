# Capability and recall tests after the large-sample acceptance (2026-11-18)

**Owner's request (in chat):** "accept a large sample to the catalogue ... afterwards, proceed to run search and workflow capability tests and benchmarks ect, try and cover as many services as you can". This follows the earlier question of whether the cleaned data gives a Librarian agent what it needs to navigate and understand the libraries it works in.

All numbers below were measured through the running Cores, or through Geo-Grapher's own Python API. Nothing was estimated. No paid model calls were made, except the small Clerk calls that `open_brief` makes to draft queries.

## Bottom line

1. **Accepting the sample is what made the libraries navigable.**
   - On the same 40 sampled records per library, catalogue search now finds the right source in the top 5 for 90–95% of fact questions. Before acceptance it was 20–62%.
   - Name lookup is 93–95%, against 8–72% before.
   - In-text search went from 0% to 83–95%.
   - Every one of these hits is the accepted Source note, not the raw file.
   - The library's own `evaluate` tool, now seeded with these questions, scores hit@5 of 1.00 (Parallax), 0.97 (NFL) and 0.99 (RL).
2. **The workflow works end to end**: open, frame, map, need, search, judge, synthesise, then a drafted offering whose quote comes from past the note's card. It ran on all three libraries. Two gaps limit it in practice (finding W1 and finding W2 below).
3. **A regression of mine was found and fixed: Resource-Library searches took about 100 s.**
   - The cause was a path check that ef5f595 added on every index refresh.
   - The fix is 0244f56. Searches now take 13–17 s including the refresh.
   - The fix is pushed, hosted CI passed, and the Cores run on it.
4. **Geo-Grapher finds the right code in our own repositories.**
   - Parallax's internal graph is dominated by vendored third-party code, which is the planned graph move.
   - Federated search silently drops every third-party graph, so the "open both graphs" workflow does not work yet.
   - Resource-Library's research-paper corpus holds 12 documents with 0 claims.

## 1. Acceptance

| Library | Eligible | Chosen | Accepted | Model calls | Not accepted |
|---|---|---|---|---|---|
| Parallax | 44 | 44 | 44 | 0 | 0 |
| Nonlinear Field Lab | 731 | 250 | 240 | 0 | 10: name collisions |
| Resource-Library | 280 | 150 | 143 | 0 | 6 name collisions, 1 excluded path |

- **Eligible** means enriched, normal sensitivity, fully read, and the Clerk's draft is `ok`. The 40 records the recall benchmark samples were accepted first.
- **Name collisions.** Ten NFL items were refused with `UNIQUE_NOTE_NAMES`, for example "'report' already exists at Sources/document/report.md". Their titles are bare file stems such as `report`, `safety_checkpoint` and `evidence_index`, which many run folders share. They wait on the titles decision (C6).
- **Excluded path.** One RL item, `research-synthesis-dba09f`, points into a folder that was excluded after it was staged. The refusal is correct; the staged record is stale.
- **The reason recorded on every accepted item** cites your chat instruction. Accepted notes carry `attested_by: person` (open item, unchanged).
- **Acceptance slowed as the catalogue grew.** RL batches of 10 went from 21 s to 205 s. One dry-run accept took 100 s whether it covered 1 item or 5, so the cost was fixed per call, not per item: the regression in §4.

## 2. Recall: can an agent find what the library holds?

**Method.**
- The sample is the same 40 records per library as the earlier baseline (seed 7).
- **Fact probe:** the six rarest words of one of the source's own read claims.
- **Name probe:** the document's title.
- A hit means the source's document or its accepted Source note is in the top k.
- Script: `recall_bench2.py`, deterministic, with no model calls.

**hit@5 before acceptance → after:**

| Probe (intent) | Parallax | NFL | RL |
|---|---|---|---|
| fact (`all`) | 0.62 → **0.95** | 0.53 → **0.90** | 0.20 → **0.93** |
| fact (`donor`) | – → **0.93** | – → **0.90** | – → **0.93** |
| fact (`orient`) | – → 0.93 | – → 0.90 | – → 0.93 |
| fact (`technique`) | – → 0.90 | – → 0.88 | – → 0.93 |
| fact (`in_text`) | 0.00 → **0.93** | 0.00 → **0.83** | 0.00 → **0.95** |
| fact (`workspace`) | 0.93 → 0.93 | 0.65 → 0.65 | 0.95 → 0.95 |
| name (`all`) | 0.72 → **0.93** | 0.40 → **0.95** | 0.08 → **0.95** |
| name (`donor`) | – → 0.93 | – → 0.95 | – → 0.95 |
| staged reading (`search_work`, top 20) | 0.00 → 0.00 | 0.05 → 0.05 | 0.10 → 0.10 |

Accepted records only, hit@5 for catalogue fact and name: Parallax 1.00 and 1.00; NFL 0.95 and 1.00; RL 0.97 and 1.00.

**What this means for an agent:**
- **Accepted Sources are found by their facts and their names**, with MRR 0.82–0.95. A Source is found as the Source note, so an agent gets the bottom line, sections and provenance, not a raw file.
- **The workspace view is unchanged.** It still loses to giant log and data notes in NFL: 7 of 12 misses are "crowded".
- **Staged reading is effectively unsearchable.** `search_work` with three rare words returns nothing for 38 of 40 NFL records, 39 of 40 Parallax records and 36 of 40 RL records, because it requires every word (AND). Anything not yet accepted is reachable only by name or ID. There are 491 NFL items left in that state.
- **Caveats:**
  - All three indexes have 0 embeddings, so every result is lexical. The fact probes use the source's own words, so they overstate recall for paraphrased questions.
  - `pattern`, `precedent`, `data` and `made` return nothing in every library, because no notes of those kinds exist yet. That is accurate, not a fault.
  - Topics are only `Unfiled`, there are no lenses, and community reports have never been built. So `orient` and `lens_suggest` have little to orient by.

**The libraries' own evaluation harness** (`evaluate`, k=5):
- I seeded `.librarian/eval/questions.json` with 2 questions per accepted benchmark record (fact and name, intent `donor`, expecting the Source note): Parallax 74, NFL 76, RL 76.
- Results: Parallax hit 1.00 (MRR 0.98); NFL hit 0.97 (MRR 0.93, 2 fact misses); RL hit 0.99 (MRR 0.97, 1 fact miss).
- `vectors_contributed` was 0.
- **Learned ranking can't be tested yet.** `ranking_candidate_generate` needs at least 30 search-feedback events over 10 queries, and every library has 0.

## 3. Workflow: a research session as an agent runs it

**Method.** Script: `session_flow.py`, one or more sessions per library. The steps:
- `open_session` (explore), then `update_plan` (map) and `open_brief` with disqualifiers;
- two `research_round` + `checkpoint` cycles when the search phase is entered;
- in judge: `add_candidate` for the brief's `already_held` when search was skipped, then `decide` keep and reject with reasons;
- `record_assumptions`, `record_synthesis`;
- `draft_offering` with a verbatim quote taken three-quarters of the way into the kept Source's original, well past its card;
- `park_session`. The test offerings stay staged and were not promoted into your vaults.

| Library, need | Steps ok | Search phase | Candidates | Workspace leads | Late quote accepted |
|---|---|---|---|---|---|
| Parallax, control hub operator auth | 26/28 (`close_session` needs the offering promoted first: W4) | skipped (covered) | 3 | – | yes |
| NFL, solver validation | 21/21 | skipped (covered) | 3 | – | yes |
| NFL, GPU memory limits | 21/21 | skipped (covered) | 3 | – | yes |
| NFL, "lattice QCD MILC benchmark comparison" | 34/34 | entered, 2 rounds | 15 | 5 | yes |
| RL, stale vault lease takeover | 21/21 | skipped (covered) | 3 | – | yes |

**Findings:**
- **W1. The coverage verdict is too generous for sentence-length needs, so the search phase is usually skipped.**
  - Example need: "sources comparing this solver's results or runtime against published lattice QCD or MILC codes". It scores `covered` because it matches 4 of its 10 "distinctive" terms (solver, results, runtime, against) with 5 sources agreeing. The actual subject (lattice, QCD, MILC) matches nothing.
  - The same subject in five words scores `thin`. Unrelated needs (cookery, Brazilian tax law) are correctly `uncovered`.
  - Because `advance` skips search when every brief is `covered`, a full-sentence need almost never reaches `research_round` or its workspace leads.
  - Fix direction: weight terms by how rare they are in the library, and require the rarest terms of the need to be matched before calling it covered.
- **W2. When search is skipped, nothing carries the brief's hits into judge.**
  - `open_brief` returns `already_held`, but the candidates list stays empty, and the judge envelope's `next` does not mention `add_candidate`.
  - An agent following `next` ends with `record_synthesis(outcome='nothing')`. It worked here only because my script calls `add_candidate` for the held sources.
  - Fix direction: when search is skipped, seed the held sources as candidates, or name `add_candidate` in `next`.
- **W3. A missing argument blocks for 10 minutes.** `open_brief` without disqualifiers asks a person, and with nobody present it waits 600 s, then parks the session. It is correct when a person is attached. For an unattended agent, an immediate refusal naming the argument would be better.
- **W4. A drafted offering must be promoted before the session can close.** That is right for real work. A test or abandoned offering can only be parked, so test sessions accumulate. I parked 7 of my test sessions in Parallax and NFL.
- **Quote checking works past the card.** A quote taken three-quarters of the way into the original was accepted in every library (ef5f595's change).
- **Relevance is not measured by this flow.** It keeps the first two held sources. The RL lease question kept `regression-manifest` and `audited-engagement-harness`, which are plausible at best.

## 4. Speed

| Call | Parallax | NFL | RL before fix | RL after fix |
|---|---|---|---|---|
| search, refresh included | p50 1–4 s (p95 15–24 s) | p50 1.3–3 s (p95 27–29 s) | **~100 s every call** | p50 2–5 s (p95 15–19 s) |
| `doctor` | 141 s | 227 s | 149 s | – |
| `capabilities` | 19 s | 13 s | 29 s | – |
| `topics_list` | 18 s | 27 s | 99 s | – |
| `evaluate` (74–76 questions) | 46 s | 40 s | 98 s (empty) | 14 s |
| accept, batch of 10 | 28–37 s | 15–47 s | 21 s → 205 s | – |

**The RL regression.** A profile of one refresh on RL took 113.7 s:
- 101.5 s was in `sync_documents`;
- that was 95.4 s in 143 calls to `content_roots.resolve_read_path`, 0.67 s each;
- the time went to 277,351 `Path.resolve` calls, because each call resolved all 53 attached roots and all 1,779 manifest exclusions again.

ef5f595 put that check on every refresh. Since each RL call took longer than the 30-second refresh window, every call paid it.

The fix (0244f56) caches the resolved scope per manifest content: 144 files now resolve in 1.9 s. A test proves an exclusion written after a read still refuses the next read. The full suite passed in a clean clone (2,663 passed, 2 skipped). It is pushed, hosted Core CI passed, and the three Cores run on it (`G:\Libraries\_core-runtime\0244f56\src`).

**Still slow:**
- RL's own index refresh is about 12 s (`Index.refresh` 11.7 s, `_index_paths` 7.4 s).
- `doctor` takes 2–4 minutes.
- Write paths (`staging_decide`) always refresh fully. They do not use the search refresh window, by design, since writes need a fresh index for the uniqueness checks.

## 5. Capability sweep (51 read and inspect calls per library)

| Library | ok | Refusals |
|---|---|---|
| Parallax | 48/51 → 49 after fixing two of my arguments | `project_map`: project access is off (Settings → Projects) |
| NFL | 49/51 | `read_source_section` on a non-PDF (by design: page-anchored conversions only); `project_map` needs a project session |
| RL | 49/51 | the same two |

- Every search intent, the staging tools, evidence reading, provenance, the duplicate reports, sessions, workflows, runs, the queue, the agenda, ranking and catalogue status, and the V1 import status all answered.
- `document_duplicates` finds 50 groups in Parallax and NFL and 34 in RL. These are the same files under several names, which feeds the titles decision.

## 6. Geo-Grapher (the agent path, through `agent_requests.call_code`)

| Graph, query | First call | Repeat | Top hit |
|---|---|---|---|
| RL Librarian_V2, "vault coordinator lease takeover" | 20 s | 2.9 s | `coordination.py.VaultCoordinator.acquire`, correct |
| RL Librarian_V2, "folder review accept policy" | 3.4 s | – | `FolderReview.accept_by_policy`, correct |
| RL ToolSet, "manifest doctor" | 5.8 s | 0.8 s | `manifest_doctor.py`, correct |
| NFL quantule_mapper, "mediator storage" | 4 s | – | `orchestrator/storage`, correct |
| NFL quantule_mapper, "BSSN solver step" | 24 s | 4.2 s | `ETDRK4Solver.step`, the nearest real code |
| Parallax network_management, "control hub allowlist operator token" | **355 s** | 7.9 s | mitmproxy and csitool code, **third-party** |
| Parallax network_management, "csi capture pipeline" | 8.3 s | – | hackthelan and mitmproxy, **third-party** |

**Findings:**
- **G1. Parallax's internal graph is mostly vendored code.** `Additional Services/mitmproxy-main`, `Network Reconnaissance & Penetration Testing/hackthelan-main` and `linux-80211n-csitool-master` sit inside `network_management` and outrank our own code. A `Parallax-third-party` graph already exists, but these folders are not in it. This is the graph move in PARALLAX-GRAPH-PLAN.md.
- **G2. Federated search drops every third-party graph.**
  - `federated_search([internal, third-party])` returns the internal graph only.
  - The third-party one is omitted with `GRAPH_UNAVAILABLE`: "Select repo_ids explicitly in a multi-project snapshot". This happens for NFL and Parallax.
  - The open-both-graphs relationship view you described depends on this working, so it needs fixing before the graph rebuild.
- **G3. One paper corpus is empty.**
  - NFL third-party papers: 63 documents, 6,134 claims, and search works ("Q-ball stability" finds the Q-ball stress-stability paper).
  - RL's `Librarian research-third-party-papers` holds 12 documents and **0 claims**, so every search returns nothing.
  - Three graphs named `-papers` have no paper database attached at all: Parallax third-party-papers, RL Resource-Library-third-party-papers, and the DAG Engine third-party-papers.
- **G4. Expanding a search hit can fail.** `get_architecture_context` on a hit from a test file failed with "Filter excludes the focus entity". Every context answer was degraded to radius 0, and one answer was 95 KB.
- **G5. Code search has noise.** "Q-ball soliton solver" ranks `self._q.put` first, matching on the single letter `q`.
- **G6. Cold starts are slow.** The first query on a large graph took 20–355 s. Repeats took 1–8 s.
- **G7. The agent-side Geo MCP entry is broken** (found earlier, unchanged).
  - The global `~/.config/resource-librarian/mcp.json` "geo-grapher" entry runs `uvx --from geo-grapher==0.1.1 ... --transport stdio` with no `GEOGRAPHER_CATALOG` set.
  - NFL and RL enable it, so a Librarian agent's Geo tools there talk to a published 0.1.1 with no catalogue, not the per-library service.
  - The benchmark above bypassed MCP for that reason.

## 7. Decisions for you, and what I'd do next

**Yours to decide:**
1. Titles and topics (C6–C9). They block 16 acceptances and give `orient` and `lens_suggest` nothing to work with.
2. Whether agent-accepted notes keep `attested_by: person`.
3. The Parallax graph rebuild per PARALLAX-GRAPH-PLAN.md: vendored folders to the third-party graph, legacy notebook graphs, OpenClaw excluded. G2 should be fixed first.

**For me, if you agree:**
- an immediate refusal for an unattended missing argument (W3);
- the Geo federated `repo_ids` default (G2);
- the RL papers corpus (G3);
- the Geo MCP entry (G7).

## 8. Fixed afterwards (5c5aa3a, on your "Yes, fix them")

| Gap | Change | Measured on the live libraries after the change |
|---|---|---|
| W1, coverage verdict | Each distinctive term counts by its rarity in the library (`coverage_weighting = rarity`; `count` keeps V1's rule). | The lattice-QCD sentence went from `covered` to `thin` (account 0.24). The solver-validation sentence went from `covered` to `thin`. The CuPy GPU-memory need stays `covered`, since the library does hold it. Cookery stays `uncovered`. The NFL session on the lattice-QCD sentence now enters search: 34/34 steps, 15 candidates, 5 workspace leads. |
| W2, empty judge | `open_brief` records what its search held. When `advance` skips search, those sources become candidates (`candidates_from_briefs`). | The Parallax session with a covered brief: 19/19 steps, judge seeded with the 5 held sources, no `add_candidate` calls. |
| Staged search | `search_work` searches a staged source's reading (points, limits, sections, draft). It needs two thirds of the words (all of a one- or two-word query) and ranks fuller matches first. | Staged reading found in the top 20 on the same probes: NFL 39/40, Parallax 40/40, RL 40/40. Before: 2/40, 0/40, 4/40. No empty results. 1.3–5 s per call. |

- Full suite in a clean clone: 2,666 passed, 2 skipped.
- Access fingerprints for `advance`, `open_brief` and `search_work` were refreshed after review.
- Pushed; the three Cores run on `G:\Libraries\_core-runtime\5c5aa3a\src`.
- **Not re-measured:** the `evaluate` scores and the fact and name recall tables in §2 predate this change. The change touches only the verdict, not the ranking, so the results lists are the same.

## 9. Geo gaps (on your "Yes, Geo gaps")

**G2, fixed (Geo-Grapher 7b4f3b3).**
- **Cause:** agent search and federated search sent an empty repository scope. The engine refuses that for a snapshot with several repositories, and every reviewed folder group is such a snapshot. So every third-party graph was dropped (`GRAPH_UNAVAILABLE`), and agent search on those graphs failed.
- **Fix:** a graph is now searched whole. Similarity search keeps the engine's rule and stays inside the focus entity's repository.
- **Evidence:** a new test with a two-folder third-party graph. The Geo suite passed (885 passed, 1 skipped). Pushed; the wheel is rebuilt and installed in `G:\Libraries\_geo-runtime`, and the Cores were restarted.
- **Measured afterwards:** both graphs now answer in every library. Parallax "CSI capture" returns the third-party `WiGr` CSI model code next to our graph's hits; NFL and RL return their third-party graphs too.
- Any remaining omission is `size_limit` (budget fitting), not unavailability.

**G3, cause found; the fix needs paid reading (your call).**
- RL's `Librarian research-third-party-papers` corpus has 12 documents and 0 claims because its 40 research PDFs were converted and published to Geo but never deep-read: 0 of 1,444 chunks.
- A paper's claims are its reading's points and limits, so there is nothing to search. NFL's paper corpus was read and has 6,134 claims.
- Reading them is a paid DeepInfra run of 1,444 chunks. Ingestion is paused, and the shared $30 shows $7.71 spent.
- Separately, Geo publishes a new paper database on every import and keeps every earlier one by design: 13 generations for this graph.

**G7, built (0fa91f4, on your "Built-in service").**
- Each Core now registers its own running Geo service as the `geo-grapher` server for its agents: loopback HTTP `/mcp`, with the token in an in-memory header. It stands in for the `mcp.json` entry, and tool names and Ask permissions are unchanged.
- Measured through the Cores: all three connect (NFL 22 tools, RL 22, Parallax 12). `list_graphs` returns RL's own catalogue in 0.5 s. `search_entities` finds `VaultCoordinator.acquire` in Librarian_V2 (15 s, cold), and third-party CSI code in `Parallax-third-party` (1.9 s), the multi-repository graph G2 fixed.
- A call is withheld if the service, its token or the library changed since the connection was made.
- The MCP status page shows the built-in's endpoint and header names, never the token.

The design note from before the decision:
- The agent-side "geo-grapher" entry in your global `mcp.json` starts a published `geo-grapher==0.1.1` over stdio with `GEOGRAPHER_CATALOG` unset. The Librarian's MCP client is stdio-only.
- The better fix is to stop using that entry: each Core registers its own library's running Geo service (`/mcp` over HTTP, which takes `X-Geo-Token`) as a built-in server. The token stays in Core memory, there's no second Geo process loading the same multi-GB graphs, and the agent sees exactly this library's catalogue.
- That changes how an outside tool is granted. Today a person accepts each `mcp.json` entry by digest; a library-owned built-in would skip that acceptance, though each tool still starts at Ask in the permission broker. So it is your decision.
- The alternative keeps the stdio entry but points it at the pinned local runtime with this library's catalogue. You would re-accept it, since its digest changes. It costs a second Geo process per library.

**Checked against the review you pasted:**
- **#1 is confirmed, and larger than reported.** The three libraries' graphs total **73 GB**. Most graphs keep 2–9 snapshots, and nothing prunes or compacts them. Examples:
  - RL `Resource-Library-docs`: 13.1 GB and 9 snapshots, with 26k live of 646k stored entities (4%).
  - NFL `quantule_mapper-docs`: 20.5 GB, half of it older snapshots.
  - Parallax `third-party-docs`: 10.4 GB, half old.
  - Cold first queries of 20–355 s (G6) fit this.
  - Pruning to the live snapshot (plus one) and compacting would delete data permanently. It needs your yes and a Geo command that does not exist yet.
- **#2 is partly right.** The live snapshot of `Librarian research-third-party-papers` (2 entities) is the correct pointer, since that folder holds papers, not code. The older 119k-entity snapshot was built from a temporary folder, `.gg-w4-final-temp`, and is 1.9 GB of junk. That belongs to #1; the pointer is fine.
- **#3–#5 I have not verified**: unused clusters, discovery cards and bridges; no flow from Geo back into DIK; an empty top of the pyramid. They match what I saw: 0 Concepts, topics only `Unfiled`, communities never built, 0 embeddings, and 0 rows in the bridge tables. The counts they give for staging and the clerk queue I did not check.

## Files

- Scripts, in the scratchpad: `accept_sample.py`, `capability_smoke.py`, `session_flow.py`, `recall_bench2.py`, `seed_eval.py`, `geo_bench.py`, `geo_bench2.py`, `profile_rl.py`.
- Raw results, in the same folder: `accept-*.out`, `cap-*.json`, `session-*.json`, `recall-accepted-*.json`, `geo-bench2.out`.
- Seeded questions, in each library: `.librarian/eval/questions.json`.
