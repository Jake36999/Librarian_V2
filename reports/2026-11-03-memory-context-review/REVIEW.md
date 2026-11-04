# Memory, retrieval, knowledge graphs, and multiagent context review

Date: 3 November 2026. Reviewed Librarian V2 at `40ec923f5d7cb5612939b9fc456963b88e0af4a3` and the available Resource-Library source tree. Recommendations for the main development workflow; no runtime implementation, migration, provider calls, or release-gate changes were performed.

**Recommendation:** retain V2's retrieval engine, evidence model, and Core-owned Session history. The next memory investment should connect those pieces into bounded model inputs and durable, evidence-bearing worker handoffs. A new graph database or general-purpose autonomous memory framework is a lower priority.

## Scope and evidence limits

The attached conversation is historical evidence, not a continuation instruction. Its final recorded checkpoint agrees with the checkout: Obsidian layout fixes are committed, and the real Browser + Obsidian + Claude/Cowork mixed-traffic acceptance run remains. This review does not replace that run or reopen unrelated implementation work.

`D:/Librarian research/` is empty, and `D:/Librarian_V2/papers/` does not exist. The usable compiled corpus is under `reports/2026-10-29-long-horizon-harness-research/data/paper_text/` and `reports/2026-10-30-runtime-tooling-literature/data/paper_text/`. There are **59 original extraction files** across those two sets. Earlier manifests describe 59 PDFs, with one exact duplicate pair in the original 51; file count is not independent-study count. Original manifest PDF paths point to `E:/Librarian research/`, which was not used for this review.

I inventoried and hashed all 59 available extracts, screened filenames and memory/context/graph/communication vocabulary, and reread targeted passages in the relevant papers below. This is a focused research round, not a new exhaustive review of every experiment. The original PDFs were unavailable at the requested locations, so page citations below refer to physical-page markers preserved in the extracted text; figures and extraction fidelity were not independently checked against PDFs.

The Graphify compiled-graphs skill found only four worked examples under `F:/Downloads/graphify-8/graphify-8/worked/`. None is a Resource-Library or Librarian V2 graph. Resource-Library's `.obsidian/graph.json` is an Obsidian graph-settings file, not evidence of an extracted knowledge graph. No graph artifacts were rebuilt or modified. `F:/uv-data/` contains environment/cache/tool directories; it was not treated as a research corpus or imported into the application.

Verification: **84 tests passed in 30.39 s**, covering projections, result handles, search, embeddings, audited sessions, and research rounds. This is focused regression evidence, not a fresh full-suite, live-provider, or Claude MCP acceptance result. Reproducible inventory and a synthetic context-size probe are in [review-evidence.json](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/data/review-evidence.json); see also the [extract inventory](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/data/local-extract-inventory.json).

## What Resource-Library actually provided, and what carried over

“Memory” covers several mechanisms here. Library retrieval recalls sources; Session state recalls work and authority; the Desk recalls a pursuit's working set; graph analysis discovers connections. Their persistence and authority differ.

| Capability | Resource-Library / V1 | Librarian V2 | Carry-over and value |
|---|---|---|---|
| Lexical RAG retrieval | SQLite/FTS catalogue, named intents, constraints, evidence excerpts, rank fusion and explicit coverage | `index.py`, `search.py`: FTS5 chunks, names/text/coverage, RRF, constraints, explanatory result envelopes, configurable content model | **Strong functional carry-over. Keep.** V2 explicitly identifies `consult` as its predecessor. Retrieval rules generalize beyond the original catalogue. |
| Semantic retrieval | Optional LM Studio embeddings; float32 cosine scan, unavailable-vector degradation | `embed.py`: local and hosted encoders, model/representation namespaces, query/document encoding contracts, explicit embedding start and intent-specific vector participation | **Carried over and extended. Keep optional.** Rebuild embeddings for the selected V2 representation; old vector bytes are not automatically interchangeable. |
| Source and claim memory | Notes, provenance, capability/component evidence and catalogue metadata | EvidenceStore, intake/deep reading, quote checks, provenance, claim runs, staging and promotion | **Substantial retained purpose, richer V2 contracts. Keep.** A matched quote establishes presence, not that the surrounding claim is true. |
| Note-link graph | `graph.py` exports catalogue links, invokes Graphify clustering, excludes structural hubs from centrality and retains graph build-state metadata | SQLite `link` rows plus `communities.py` deterministic label propagation over note links and declared relations | **Purpose carried over; algorithm and representation changed.** This is an advisory library graph, not a full temporal semantic memory graph. |
| Cross-topic community summaries in retrieval | `graph.report()` builds deterministic fact-based summaries; `consult._communities_touching()` adds relevant cross-topic communities to orientation results | Communities have members/degree and separate report tools; `search.py` has no community-retrieval lane | **Partial carry-over.** Useful discovery integration was lost. Evaluate restoring it behind an experiment. |
| Graph disagreement reporting | V1 compares community membership with topic assignments and reports the spread | V2 `disagreements()` surfaces connected central members as advisory candidates | **Simplified.** The shared name does not imply the original topic/community comparison survives. Restore only if users need that question answered. |
| Capability-sized code context | V1 `importgraph.py` and `digest.py`: seed → transitive imports → SCC/topological packing → budgeted digest/build plan | DIK has repository data and typed structural/inferred relations; source reading exists, but no equivalent seed-to-budgeted-digest path was found in V2 runtime | **Partially retained structure, missing end-to-end context feature.** Worth selectively porting for repository research; code-development execution remains separate scope. |
| Conversational continuity | V1 `chat.py` saves/reloads conversations and clips tool results | V2 Session event history, transcript restore, phase/budget state, audit events, deterministic replay and projection | **Reworked and substantially stronger.** Keep the V2 Session as authority; do not import old chat histories as current requirements. |
| Pursuit working set | Catalogue use/provenance signals and branch/application context | `desk.py`: persistent user pins and recency/frequency signals from existing Session use/write events | **Useful V2 working memory.** Desk titles cue retrieval; they do not inject whole notes or establish truth. |
| Long-horizon task memory | V1 digests and saved chats help bounded work; no equivalent audited Session reducer was identified | Requirements, contracts, evidence/check outcomes, epochs, questions, reductions, replay and a bounded Manager projection | **Major V2 addition.** Foundation exists; actual request assembly still needs the work below. |
| Worker memory | No equivalent structured shared-memory workflow established by the reviewed V1 paths | Read-only `delegate` helpers share access to the Core index and return answers/tool names/stop information | **Read access exists; durable coordination memory is incomplete.** Shared access to sources is different from shared task state. |

Source anchors: [V1 consult](/D:/Resource-Library/.utility/librarian/consult.py:1214), [V1 graph report](/D:/Resource-Library/.utility/librarian/graph.py:448), [V1 digest](/D:/Resource-Library/.utility/librarian/digest.py:115), [V1 import graph](/D:/Resource-Library/.utility/librarian/importgraph.py:109), [V2 search](/D:/Librarian_V2/src/resource_librarian/search.py:1), [V2 community graph](/D:/Librarian_V2/src/resource_librarian/communities.py:20), [V2 DIK](/D:/Librarian_V2/src/resource_librarian/dik.py:1), [Desk](/D:/Librarian_V2/src/resource_librarian/desk.py:1).

### Implementation carry-over is different from data migration

V2's migration intentionally stages selected active/published sources, concepts, applications and offerings. Drafts, canvases, generated hubs/queues/indexes, workflows, untyped notes and derived caches are excluded by default. Original notes are retained as evidence, and promotion remains separate. See [migration contract](/D:/Librarian_V2/docs/migration.md:1) and [import implementation](/D:/Librarian_V2/src/resource_librarian/v1_export.py:184).

This means neither V1 graph caches nor vectors nor conversation histories should be assumed to have migrated because the search code was ported. I did not certify any particular target vault's import completeness. A percentage of “memory migrated” would be misleading without a source/target manifest and explicit categories. The useful answer is: retrieval and evidence principles are strongly retained; graph discovery is partly simplified; the audited task-memory foundation is new; reusable cross-session and worker memory still need a deliberate lifecycle.

## Current gaps that matter most

### 1. The bounded projection is not the complete bounded request

`audit_projection.project()` preserves active requirement text, predicate outcomes, the current contract, open questions, budget and capabilities; optional results/events fit around them. When essential content cannot fit, it returns `fits=False`. The 50-round projection fixtures pass. This is good behavior and should be preserved.

However, [`audit_projection` is exposed as a tool](/D:/Librarian_V2/src/resource_librarian/tools/sessions.py:598). The [active invocation path](/D:/Librarian_V2/src/resource_librarian/loop.py:932) still sends `system_prompt()`, `view()`, and tools. [`view()`](/D:/Librarian_V2/src/resource_librarian/loop.py:812) retains all user/assistant messages and a compacted entry for every old tool result. Six recent tool results remain whole; older results are clipped to 700 characters. This reduces growth but does not bound it. A model requesting a projection is not evidence that it received only that projection.

The synthetic probe calls the real `view()` with fixed-size messages: 10 rounds produce 140,495 serialized characters; 50 produce 336,775; 200 produce 1,072,925. These are **size observations**, not measured provider tokens or model accuracy. The important result is continued growth even though old tool results are compacted. System text and tool schemas would add further request content.

Existing [profile budget reservation](/D:/Librarian_V2/src/resource_librarian/loop.py:497) helps refuse excessive per-turn token/cost reservations; it is not a context assembler. Its approximate character count is not a guaranteed upper bound across tokenizers, Unicode, code, JSON and different routes. Projection accounting also estimates payload pieces rather than measuring the final complete request including every envelope.

### 2. Rehydratable evidence is only partially implemented

[`ResultHandleStore`](/D:/Librarian_V2/src/resource_librarian/result_handles.py:1) gives exact content-addressed reads for oversized `read_source_file`, `get_note`, and `search` results. The existing tests establish bounded previews and Loop isolation. These are useful privacy and context controls.

Handles are intentionally in-memory and Loop-local. A helper's handle cannot resolve in the parent Loop; restarting loses it. Other tools still reach the final 16,000-character clipping path, and older history uses prefix clipping rather than task-specific evidence selection. [`restore()`](/D:/Librarian_V2/src/resource_librarian/loop.py:886) reconstructs user/assistant text, not the original tool evidence. Resume therefore needs stable source/evidence references, not an assumption that old result handles or narrative recollections remain actionable.

### 3. Worker handoffs are prose-heavy and disconnected from Session revisions

[`delegate`](/D:/Librarian_V2/src/resource_librarian/tools/delegate.py:37) has valuable restrictions: fixed read tools, versioned helper profiles, concurrency limits and Core index access. Preserve them.

The current request is a question string and brief. The returned answer is sliced to 4,000 characters and accompanied by tool names, steps, stop reason and errors. There is no structured requirement/predicate identity, parent epoch, evidence-location list, contradiction list, source-version set or resumable worker checkpoint in that envelope. The parent also does not pass a general snapshot of its active constraints; such details must currently be written into each question. A useful late caveat or citation can fall beyond the answer slice without a dedicated truncation flag.

This is not evidence that every delegation is wrong. It is an interface limitation that makes omission, stale merge and restart hard to detect mechanically. Per-helper profile budgeting exists; the reviewed handoff path does not establish one parent-reserved aggregate budget or complete durable child receipts. Verify that accounting explicitly before claiming it.

### 4. Searchable notes are not yet a complete reusable-memory lifecycle

Session history, Desk signals, evidence, notes, workflows and staging cover much of the required storage. What is missing is a unified way to retrieve reusable decisions, validated procedures, failed attempts and relevant prior-session episodes with explicit scope, freshness and supersession. `facts.py` contains deterministic catalogue-field derivation; it is not a general conversational fact-memory service.

Do not solve this by embedding every transcript and calling the results authoritative. Historical statements may have been corrected, inferred, rejected, session-specific or obsolete. Persistent constraints and decisions need precedence; retrieval scores cannot decide permission.

### 5. Three graphs have different jobs

The library graph connects notes/concepts; a source graph describes static document/code structure; a requirement/evidence dependency graph tracks what conclusions rely on which versions. V2 has pieces of the first two and conservative Session epoch invalidation for the third. Combining all of them into an untyped graph would lose important distinctions.

V2's community report is explicitly advisory. Its cached report records a timestamp, but it is not bound to a source snapshot in the way V1's `built_at_index` intended. Snapshot identity and stale indicators should precede wider retrieval use. Existing HARNESS-09 already reserves targeted dependency invalidation; this review proposes evaluation inputs, not immediate replacement of conservative invalidation.

## Research round: methods worth transferring

The following are **design inferences for Librarian**, with the source's actual domain and limitations kept separate.

| Local source and checked passage | Useful mechanism | Transfer and boundary |
|---|---|---|
| TMS, `tms.txt`, pp.2–6, especially p.6 continuity/resume discussion | Persistent goal/task structure plus execution feedback | Reuse the Session requirement tree, replay and explicit next work. The prototype does not establish a generally optimal scheduler, recursive planning policy or autonomous root-goal creation. |
| Knowledge-Driven Reasoning for Mobile Agentic AI, `mobile_kdr.txt`, pp.2–3 and knowledge-exposure experiment | Separate episode information, bounded task context and reusable knowledge; selective activation | Index prior episodes and validated procedures, activate only relevant records. Its UAV/mobile setting does not establish Librarian token savings or a universal optimal context size. |
| LLM-S2KG, `remaining_02.txt`, p.10 provenance, pp.11–12 representation, pp.24–25 limits | Document/paragraph provenance and structural context alongside semantic associations | Use evidence spans and section parents in retrieval. The paper explicitly acknowledges relationship inversions and uses symmetric/undirected semantic labels in its representation; do not copy that representation for directed dependencies or causal assertions. Presence of a graph or quote does not validate a claim. |
| CoACL, `remaining_04.txt`, p.19 Appendix A.3 | Conservative handling of ambiguous candidate edges | Keep inferred links proposed/unresolved until supported. Apply this to advisory links, never silently drop mandatory user requirements. This is graph-learning research, not a validated agent-memory policy. |
| STAGE, `remaining_13.txt`, p.6 and pp.9–10,16 | Original-text fallback and bounded structural context | Preserve source text if enrichment fails; evaluate bounded graph-neighbor expansion. Its learned token selector and GNN training are not needed for a hosted API implementation. |
| Communication-efficient multiagent cooperation, `comm_efficient.txt`, pp.1–4 | Goal-oriented, interpretable messages under a communication budget | Use a minimal worker packet and structured result, then retrieve supporting detail on demand. The experiment is robot navigation; it does not validate LLM software-agent performance or a fixed packet size. |
| Mutual Influence, `mutual_influence.txt`, p.7 | Distinguish agreement from outcome validity | Retain independent evidence and disagreements when merging workers. The paper finds agreement effects but no statistically significant approval-rate change in that comparison. Consensus should not become a verifier. |
| CoKV, `kv_management.txt`, pp.1–3 | Attention-head-level KV allocation | Defer. It concerns inference internals, not durable memory, worker state or source retrieval. Hosted API clients cannot assume access to these controls. |
| ReflectiChain, `sed.txt` and `reflectichain_full.txt`, taxonomy/results | Test scope narrowing, exceptions, temporal relaxation and priority inversion | Add memory-compaction and handoff drift cases. Versions are not independent replications, and results do not justify always-on reflection. |
| WASABI, new corpus `new-01.txt`, pp.2–8 | Retry lifecycle and cleanup testing | Test interrupted memory writes, uncertain worker completion and duplicate merge/retry. Use configured local limits, not the paper's probe constants. |
| MCP-Secure, new corpus `new-03.txt`, pp.3–5,9 | Host mediation and scoped tool effects | Recheck current permission whenever memory is rehydrated or passed to a worker. The source's restricted evaluation and static metadata are not comprehensive multiagent security evidence. |

Local links: [original compiled extracts](/D:/Librarian_V2/reports/2026-10-29-long-horizon-harness-research/data/paper_text), [new extracts](/D:/Librarian_V2/reports/2026-10-30-runtime-tooling-literature/data/paper_text), [original manifest](/D:/Librarian_V2/reports/2026-10-29-long-horizon-harness-research/data/complete_corpus_manifest.json), [new manifest](/D:/Librarian_V2/reports/2026-10-30-runtime-tooling-literature/data/new-source-manifest.json). Earlier reports remain useful context, but the recommendations above were checked against local source passages rather than adopted from reader-agent commentary.

### Targeted primary-source supplements

The local collection is stronger on harnesses, graph learning and tool mediation than on conversational-memory evaluation. Four external primary sources help close that gap:

- **LongMemEval** evaluates recall, cross-session reasoning, temporal reasoning, updates and abstention. Its experiments distinguish storing original interaction rounds from compressing everything into isolated facts: compression can lose information, while expanded retrieval keys can still help. Proposed transfer: retain original episodes as values and test enriched keys as a derived index, alongside temporal filters. These results concern its benchmark and models, not a guaranteed Librarian improvement. [Paper, §§3–5](https://arxiv.org/html/2410.10813v2).
- **Lost in the Middle** demonstrates position-sensitive retrieval/use of evidence in long contexts. Proposed transfer: measure constraint survival with relevant evidence at the beginning, middle and end, and vary distractors. Its tested models do not establish how current qualified Librarian routes behave. [Paper](https://arxiv.org/abs/2307.03172).
- **Zep** describes episodic/semantic layers and temporal fact invalidation. Proposed transfer: distinguish when something was recorded from when it applies, preserve superseded assertions and support “as of” retrieval. The architecture and vendor-authored benchmark do not establish a need to adopt its service or graph database. [Paper, §§2–3](https://arxiv.org/html/2501.13956v1).
- **A-Mem** proposes structured memory notes, semantic links and evolving descriptions. Proposed transfer: experiment with suggested links and derived retrieval metadata. Keep originals and versions intact; do not let automatic evolution rewrite user requirements or accepted facts. Its findings do not establish safe autonomous memory rewriting in this product. [Paper, §3](https://arxiv.org/html/2502.12110v1).

## Proposed implementation queue

These are suggested packets, not additions silently applied to the unified plan. Sizes are relative engineering slices, not time estimates. Foundation packets should reuse Session/Writer/index ownership and existing profile/route contracts.

| Order / packet | Size | Concrete change and likely integration | Acceptance evidence |
|---|---|---|---|
| **1 — MEM-01: measure actual context** | Small | Instrument final request assembly in `Loop.send`/invocation runtime: system, schemas, required state, recent dialogue, retrieved items, output reserve, estimated/actual token usage. Log IDs/digests/counts, not raw prompts. Add memory challenge fixtures before tuning. | A long conversation reports every request component; aggregate includes worker/retry calls; unknown usage is explicit; diagnostics contain no source text or credentials. |
| **2 — MEM-02: enforce a complete request budget** | Medium | Add one context assembler at dispatch. For audited work, always supply a current Session projection plus a bounded dialogue/evidence tail instead of accumulating the full history. Reserve output/schema overhead using route-aware counting or a tested conservative margin. Preserve provider continuation/tool-call grouping. | At 50 and 200 rounds the final serialized request stays within the configured route budget; required constraints survive; essential overflow splits/parks visibly; `fits=False` cannot be bypassed by proceeding with a clipped projection. |
| **3 — MEM-03: durable evidence references** | Small–medium | Keep Loop handles as ephemeral previews. Add stable references to existing evidence/source artifacts with version/hash, locator, representation and read scope. Rehydrate through the normal broker/index boundary; do not introduce arbitrary handle-based file access. | Parent can reopen a child's cited evidence after child exit and Core restart; changed/missing/unauthorized sources are reported stale/unavailable; an expired Loop handle is not falsely presented as durable. |
| **4 — MEM-04: typed worker handoffs** | Medium | Extend `delegate` input/output with parent Session/requirement IDs, epoch, scoped constraints, source refs, budgets, findings, unresolved questions, disagreements, actual usage and explicit truncation/partial status. A child returns proposals; Core-owned merge records them. | Parallel workers remain read-only; oversized answers retain structured evidence/caveats; a parent correction during work causes stale rejection/reconciliation; duplicates merge once; malformed results cannot close requirements. |
| **5 — MEM-05: cross-session episode retrieval** | Medium | Build a disposable index over approved/scoped Session episodes: decisions, evidence-backed findings, failed attempts and unresolved work. Store event-range pointers as values. Use lexical retrieval first, optional existing vectors, and project/time/status filters. | A reopened pursuit retrieves a past decision with its original event range and correction history; an obsolete decision cannot override a current user correction; unrelated pursuits do not leak into results. |
| **6 — MEM-06: consolidation and correction lifecycle** | Medium | At useful checkpoints, propose reusable decision/procedure records with source events, scope, validity, verification limits and supersession. Reuse staging/promotion for durable knowledge. Separate evidence-backed procedure from tentative model reflection. | A repeated failure is recalled with its conditions; later success/correction supersedes without erasing history; inferred preference is never silently promoted into a global instruction; withdrawn records disappear from retrieval. |
| **7 — MEM-07: aggregate delegation budgets and recovery** | Small–medium | Reserve worker allowances in parent scope before dispatch; reconcile actual/estimated/unknown charges and completion status through durable receipts. Add child IDs and idempotent merge keys. Keep execution and acceptance separate. | N helpers cannot each consume the parent's full allocation; interruption retains uncertain reservations; restart does not relaunch or reaccept unresolved child results; all model calls appear in total cost. |
| **8 — MEM-08: parent/section-aware RAG experiment** | Small | Return exact hit spans plus bounded section parents, source versions and conflicting passages. Compare lexical, hybrid and bounded structural expansion on the same questions using existing evaluation tooling. | Report retrieval recall and answer support separately; test negation/caveats, similar names, duplicates and stale captures; retain the baseline if quality/cost does not improve. |
| **9 — MEM-09: restore useful graph discovery experimentally** | Small–medium | Bind community reports to an index/source snapshot, mark stale state, add deterministic cross-topic fact summaries and an optional `orient` lane. Recreate topic/community disagreement only if useful. | Cross-topic questions improve at matched context/cost; structural hubs cannot dominate; edits invalidate reports; no generative model is introduced on ordinary reads. |
| **10 — MEM-10: selective dependency invalidation** | Medium, later | Under HARNESS-09, project typed `depends_on`, `supports`, `contradicts`, `supersedes` links from Session/evidence records. Begin with declared dependencies; keep inferred links advisory. | An edit invalidates known dependents; missing/inferred dependencies fall back to conservative invalidation; accuracy/rework savings justify the extra graph machinery. |
| **11 — MEM-11: capability-context digest pilot** | Medium, optional | Adapt V1's import closure and topological packing for bounded repository reading. Keep unresolved imports, dynamic behavior and oversized SCCs explicit. Reuse DIK evidence and content-root permissions; no persistent full source graph is required. | Compare against file-by-file and broad directory context; verify versions and declared static import coverage; never label regex import closure as full semantic/runtime dependency closure. |
| **12 — MEM-12: memory retention and removal** | Small–medium, alongside MEM-03/05 | Define scope/retention for ephemeral results, evidence, episodes and promoted knowledge. Make withdrawal/tombstones invalidate indexes/caches; define separately what physical source deletion means for audit retention. | A removed record cannot be retrieved from stale vectors, summaries or graph reports; privacy scope survives handoffs; the interface distinguishes retrieval withdrawal from physical removal. |

Suggested sequencing: MEM-01 → MEM-02/03 → MEM-04 → MEM-05/06/07. Bring retention rules into the design before durable cross-session indexing ships. Then compare MEM-08/09; defer MEM-10 until conservative invalidation has a measured cost. MEM-11 is a separate repository-research pilot. Keep the existing mixed-host MCP acceptance run independently scheduled; these suggestions do not claim to complete it.

### Minimal memory and handoff contract

This describes logical fields, not a requirement for a second database or authoritative log:

```text
Memory reference / projected record:
  stable identity; kind; user/library/project/session scope
  original Session event range or evidence identity + source version + locator
  origin (person / observed / source-stated / inferred); verification scope
  recorded time; explicit applicability interval if known; supersedes/conflicts
  current status (proposed / usable / disputed / stale / withdrawn)
  content/ref payload; retrieval keys; retention/access policy

Worker request:
  child/parent IDs; parent epoch + requirement revision; bounded question
  required constraints; allowed source scope; evidence refs; allocated resources

Worker result:
  child identity + input snapshot; findings with evidence refs
  unresolved/conflicting items; failed attempts; usage; stop/truncation status
  proposed updates and idempotent merge identity
```

Current user intent and Core policy govern authority. Verified results remain bound to their exact checked source/version and predicate. Recency and semantic similarity only rank eligible records. Do not resolve conflicting scientific sources with “newest wins,” or turn a worker's confidence/consensus into permission or truth. Child-private context stays private unless deliberately included in the bounded handoff; useful shared records enter through the Core-owned merge path.

## Evaluation pack for the main workflow and Claude MCP round

Start with deterministic fixtures, then a bounded set of real tasks on the same qualified routes. The current 84 tests establish relevant existing behavior; they do not cover the proposed new packets. Compare current execution, complete bounded context, bounded context plus episode retrieval, and only then graph expansion/semantic enrichment. Hold tasks, routes, output limits and total budgets comparable; report failure cases and denominators.

| Fixture | Required observation |
|---|---|
| Constraint introduced early; 50/200 rounds; distractors placed before/after it | Exact required constraint survives compaction and restart; actual request stays bounded. |
| User corrects a preference/decision; asks current and historical questions | Current answers use the correction; “as of” answers retain historical provenance; unknown dates stay unknown. |
| Two similar projects or users, same vocabulary | Retrieval and handoffs obey scope and current access; no cross-project memory contamination. |
| Worker returns after parent requirement/source change | Result is stale for dependent closure; useful unaffected material can be re-evaluated explicitly. |
| Two workers repeat one source and disagree in interpretation | Source duplication is counted once; disagreement remains visible; agreement does not verify the claim. |
| Worker result exceeds preview, with key caveat at the end | Truncation is explicit; complete structured evidence/caveat can be rehydrated. |
| Restart after read, before merge, and during uncertain provider completion | Stable evidence resolves; ephemeral handles fail clearly; child results merge once; unknown cost/effect stays unresolved. |
| Old workaround or failed approach is retrieved | Preconditions/version are checked; outdated advice does not override current validation. |
| Source says “inhibits,” neighboring text says “promotes,” quote exists in both | Relation direction and semantic support are checked separately from quote presence. |
| Hostile instructions inside a retrieved note or remembered episode | Content remains data after retrieval, consolidation and delegation; cannot enlarge scope. |
| Withdrawal/deletion of remembered material | Lexical/vector/summary/graph caches no longer surface withdrawn content. |
| Browser + Obsidian + real Claude/Cowork use the same pursuit | The same durable state and revision are observed; cross-client corrections do not permit stale closure. This is an additional memory scenario, not a substitute for ACCEPT-02's existing checks. |

Measure critical-constraint retention, retrieval recall, temporal/update correctness, supported-answer rate, abstention, stale merges, duplicate effects, restart recovery, total input/output/cached tokens and cost across all roles, latency, and human correction effort. Include “nothing accepted” runs in costs. Predeclare acceptance conditions; do not copy another paper's score or confidence threshold. For policy and mandatory-constraint fixtures, any unauthorized scope expansion or dropped required constraint fails that fixture.

## Keep, recover selectively, defer

**Keep:** current lexical/optional-hybrid retrieval, explanations and constraint filtering; original-source evidence and staging; Core/Writer ownership; Session replay/epoch semantics; bounded projection overflow refusal; Desk pins; read-only helper policy; local result-handle isolation.

**Recover selectively:** cross-topic community summaries in orientation retrieval, graph snapshot identity, and V1's capability-sized import context. Port the useful behavior with V2 ownership and evaluation; do not restore obsolete catalogue assumptions or old derived caches wholesale. V1's `queryunderstanding.py` even records that attempted ask/context/exclusion reweighting degraded its scenario results; preserve that negative lesson rather than copying the segmenter as an assumed improvement.

**Defer:** adopting a graph service/database by default, automatic semantic fact rewriting, full-transcript embedding as the sole memory, learned graph-token selectors, always-on reflection/reviewer swarms, inference-level KV manipulation, and agent consensus/trust scores as closure signals. None solves the identified dispatch, handoff and rehydration gaps by itself.

The first concrete development packet should be **MEM-01 + MEM-02**, with **MEM-03 + MEM-04** immediately after. That makes the new harness's recorded memory reliably usable at the model and worker boundaries before adding more knowledge to retrieve.
