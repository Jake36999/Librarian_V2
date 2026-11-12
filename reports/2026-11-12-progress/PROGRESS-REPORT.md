# Librarian V2: where it stands, and what is planned where (2026-11-12)

The yardstick is the finalization plan of 2026-11-04
(`reports/2026-11-04-master-finalization/`: the plan, the requirements and
`execution-queue.json` with MF-001…MF-051). Each packet's evidence is its §19
entry in `docs/unified-implementation-plan.md`.

The second half is for anyone integrating Geo-Grapher. It maps which planned
packets already cover the same files and ideas, so that work is done once, in
the right place.

Labels:
- **M**: measured here by a re-runnable command or a hosted CI run;
- **R**: reported elsewhere and not re-measured.

## 1. Summary

- **Done since 2026-11-04 (M):**
  - all of Wave 1A (MF-005…010) and Wave 1B (MF-011…020);
  - the Core side of MF-027 (a–c);
  - build and release hardening MF-043a–e;
  - Codex's two backend requests (ticked staging triage, macro recovery
    handles).
- **Current master:** `8bbf281`. Full suite on a clean clone: 2,130 passed,
  2 skipped (`reports/2026-11-07-evidence/suite-replace-py311.json`). Hosted CI
  is green on every job: core and wheel-smoke on 3.11.9, 3.12.10 and 3.13.17,
  plus adapters.
- **Not releasable yet.** What remains is owner decisions, real-host runs, the UI
  wave and the final release engineering (section 3).
- **Uncommitted right now in `D:\Librarian_V2`:** another session's Geo-Grapher
  integration work.
  - It touches `mcp_client.py`, `loop.py`, `agent_runtime.py`, two standard
    profiles, `ui/src/settings.ts` and tests. In `mcp_client.py`, an oversized
    *structured* MCP result is now withheld whole instead of character-clipped.
  - It sits on `master`, not on the `geo-grapher-wave4` branch the Geo-Grapher
    plan names, and has not been suite-tested here.
  - Commit it on a branch before other work lands on those files.

## 2. Delivered, with evidence

| Area | Packets | What it means for users and agents | Evidence |
|---|---|---|---|
| UI truth and isolation | MF-005…010 | The composer is kept on refusal; Stop is separate; mutation feedback is truthful; CSS and DOM are namespaced; legacy and stale states are shown; stop reasons are durable | §19; commits `6b73fd6`…`fd9586c` (M) |
| Context bound | MF-011 | Every provider request fits its route's window; trimming is measured and reported | `5167969` (M) |
| Durable evidence | MF-012 | `ref:` references reopen exact note and file evidence after a helper exits or the app restarts | `bc30910` (M) |
| Ingestion identity | MF-013, 014, 020 | Deep reads, renamed documents and V1 import or batch reuse never silently reuse stale bytes | `896369d`, `1bbbf6c`, `5713330` (M) |
| Sandbox safety | MF-015, 016 | Uncapped container output is its own always-asked permission. Every container is stopped, shown stopped and removed before a checked, all-or-nothing export | `5e3a6b4`, `7a7bcb6`; real-Docker qualification in `reports/2026-11-05-evidence/` (M) |
| Workflows | MF-017, 018 | Pinned workflow closure; a step whose outcome is unknown waits for a person and is never blindly repeated | `306bc4e`, `d190969` (M) |
| Spend | MF-019 | TTS spend is reserved across processes. STT has no price, so it has no cap | `d40ea08` (M) |
| Review and preview | MF-027a–c (Core) | Each reply review is bound to its reply and its exact note. `staging_show` returns the byte-exact preview an accept writes. Claim Run checks Docker first | `294d15b` (M) |
| Triage and recovery | Codex asks | Several sources can be ticked and approved or deferred, each refused if it changed since it was listed. Paused macros can be resolved by handle after a reconnect | `3b3de57` (M) |
| Build and release | MF-043a–e | Exact toolchains; hash-locked installs; workflow security; retained test evidence; SBOM and provenance attestation (not yet run) | `40eaf7d`, `9dbf575` (M) |
| CI reliability | — | Saving a file waits out a brief Windows lock, the cause of the "promotion interrupted" intermittent | `8bbf281` (M) |

The UI wave (Codex): Settings workspace, navigation, search layout, keyboard and
health. Evidence is in `reports/2026-11-05-ui-wave/STATUS.md` and
`HOST-QUALIFICATION.md` (R for this report).

## 3. Pending, by kind

| Kind | Packets | Blocker |
|---|---|---|
| **Owner decisions** | MF-051 release scope; MF-002 ledger liabilities; MF-043f licence, ownership and support (`reports/2026-11-06-mf043/GOVERNANCE-DECISIONS.md`); whether to dispatch the first release candidate (it publishes attestations to the public Sigstore log) | the owner |
| **Real-host runs** | MF-001 mixed-client acceptance with a real Claude client; MF-045 the final-candidate repeat; MF-035 native Obsidian hotkeys | the owner in Obsidian and Claude |
| **Core, optional (Wave 2)** | MF-021a–c structured worker hand-off, shared budget, restart-safe merge; MF-022 encoder recovery; MF-023 pinned claim recipes; MF-024 Clerk/Scribe/Scout receipts; MF-028 common envelopes for PDF, OCR and search; MF-029 V1 identity reconciliation; MF-030 MCP restart and library-switch qualification | MF-051 decides which ship |
| **UI (Codex lane)** | MF-025, 026, 031–034 remainders; the MF-027 before/after preview display; the background-chip view of paused runs | in progress |
| **Release engineering** | MF-044 acceptance and capability refresh (the capability matrix predates every MF packet); MF-046/047 freeze, routes, signing, publication | MF-035, 042, 051 |
| **Research (outside the release)** | MF-036–041: temporal revisions and lessons, selective invalidation, parent/section retrieval, community orientation, the DIK code digest, the evolving-knowledge benchmark; memory improvements W1–W6 (`reports/2026-11-05-review-pass/MEMORY-IMPROVEMENTS.md`) | after the release |
| **Known defects** | Reopening a library whose Core is still running refuses (`vault_in_use`) instead of reopening it (`app.py:4641`). No sweep for containers left by a crashed Core (MF-016 limit). Disk writes inside the sandbox are sampled, not capped (MF-015 decision) | the first is scoped in `LIBRARY-ACCESS-API-SCOPE.md` |
| **Housekeeping** | Rotate the DeepInfra key exposed in a local log on 2026-11-05 | the owner |

## 4. Geo-Grapher: what it is to the Librarian

**What it is (R, from its README and plans).** A deterministic, local, read-only
knowledge-graph builder for code and documents:
- It parses, and never executes, a repository into immutable per-snapshot SQLite
  stores.
- It condenses structure: SCC condensation, helper-tree contraction, and from
  wave 3 directed convex contraction that provably preserves reachability.
- It answers through token-exact MCP envelopes: `search_entities`,
  `get_architecture_context`, `get_entity_content`, `find_dependants` and
  others, plus paper tools.
- A 3D nested-sphere workspace shows several graphs. Since wave 1 it has an
  affinity layout, display labels, role badges and coloured directional edges.
- A catalog keeps several graphs apart, with declared bridges between them.

Phase 6–7 wave 1 is merged (`c153765`). Waves 2–4 are planned:
- **wave 2:** fingerprints and drift, notebooks, `init-workspace`, cross-graph
  diff;
- **wave 3:** directed contraction, typed bridges, lineage and staleness,
  `analyze_cross_graphs`, the directory picker;
- **wave 4:** task packets, `dispatch_plan` on Librarian helpers, route-aware
  result limits.

**Why it fits better than V1's graphify.** V1's graph nodes held abstract content
with no context saving, and V1 drew several graphs on one 2D canvas.
Geo-Grapher's answers are bounded, counted, citable envelopes:
- every node has a source span;
- every claim cites a handle (`cite_as`);
- federation keeps each graph's ranking separate, instead of inventing a global
  one.

That suits the Librarian's evidence rules (MF-012 references, closure verifiers,
`DATA_IS_UNFRAMED` clerks).

**What it adds to the Librarian.**
1. **A code and document substrate for sessions.** Today the Librarian reads a
   project by files (`project_map`, `read_project`). Graph envelopes give a lead
   model architecture context at a fraction of the tokens, with citations a
   verifier can check.
2. **Work packets for helpers (wave 4).** The Core fetches packets itself, so
   helpers stay tool-free. Tier-3 clerks answer closed-shape questions over one
   packet, and citations are checked deterministically. This is the Librarian's
   own discipline extended to code.
3. **Staleness the Librarian lacks.** Geo-Grapher's lineage (G5) and drift tiers
   (G3) give exactly the "this evidence changed since you relied on it" signal
   that MC-05, MC-14 and MF-036/037 call for, for code-backed claims.
4. **A native graph view,** the way Obsidian has one: the viewer as a pane, and a
   library's repositories as separate graphs.

## 5. Where Geo-Grapher work meets planned Librarian work

Do these together, so each is done once:

| Geo-Grapher plan item | Librarian files | Planned packet in the same place | Do it like this |
|---|---|---|---|
| Wave 4 Task 2: route-aware external result limit (`mcp_client.py`, `loop.py`) | `mcp_client.py:47, 480-505`; `loop.py` context fit | **MF-011** (done: context bound) and **MF-030** (MCP restart and library switch) | Reuse MF-011's resolved window (`loop.py`), don't add a second one. The uncommitted "withhold structured results whole" change belongs here. Add MF-030's restart and library-switch tests while editing `mcp_client.py`. |
| Wave 4 Task 3: clerk `code_block_contract`, `packet_checks.verify_citations`, a closure verifier | `clerk.py`, `closure.py` | **MF-024** (Clerk receipts and correlation) | Give the new task MF-024's receipt fields (worker attribution, effort log), so it is not retrofitted later. |
| Wave 4 Task 4: `dispatch_plan` over `delegate` and the clerk | `tools/plan_dispatch.py`, `agent_runtime.py` bundles | **MF-021a–c** (structured worker envelope, aggregate budget, restart-safe merge) and **W3** (typed helper result) | Return each task's answer in MF-021a's envelope. Reserve the whole plan's spend through MF-021b's aggregate budget. `dispatch_plan` writes nothing, so MF-021c's merge applies only when the lead stages results. If MF-051 leaves MF-021 out, build the smallest envelope `dispatch_plan` needs and record it as MF-021a's first slice. |
| Wave 4 Task 4: snapshot `STALE_SCOPE` at reduce time | `audit_projection.py`, `closure.py` | **MF-037** (selective invalidation), **MC-05/MC-14** | Name the stale reason the way MF-010's durable stop reasons do, so the UI can show it. |
| Wave 2 Task 4: deploy-survey hook (`deploy_survey.py`) | `deploy_survey.py` | **MF-029** (V1 reconciliation) shares the survey path | Keep the hook read-only, as planned. It must never write into the surveyed folder. |
| Wave 3 lineage and bridges (`external` artifact kind reserved) | none yet | **MF-036** (temporal revisions), **W5** (validity time) | When the Librarian registers notes as Geo-Grapher artifacts (wave 5), use MF-036's revision events as the upstream premises. |
| Graph view as a native pane | `ui/src/pane.ts`, `views.ts` | **MF-034a** (pane navigation), Codex's lane | Add it as a pane view beside Note, Browse, Plan and This week, not as a separate page. |
| Running Geo-Grapher as an outside MCP server | `mcp_client.py` limits (≤ 6 tools per server, ≤ 8 in total, read-only, research phases) | **MF-030** | The `lead`, `cross`, `code` and `papers` presets are 6 tools each. Only one Geo-Grapher preset fits per library within the 8-tool total. |
| Effort caps on plan size | `effort.py` | none (existing limits) | `PLAN_TOO_LARGE_FOR_EFFORT` must read `effort.of(ctx)`, never its own constants. |

**Two cautions from the 2026-11-11 session** (transcript
`F:\uv-data\Geo_Grapher\reports\Transcript\claud-development-transcript 2 - geo grapher.txt`):
1. **The helper qualification gate.** Wave 4's helpers will be refused until the
   person qualifies the `research_helper` and clerk routes in the target library.
   Plan a qualification step into the wave 4 gate.
2. **Don't open a repository as a library.** Opening Geo-Grapher's repository as
   a library wrote `.librarian/`, `About/` and `Indexes/` into it. Attach
   repositories as content roots of a real library instead.

## 6. Recommended order from here

1. **Owner:** MF-051 (scope), MF-043f (licence), the release-candidate dispatch,
   and the DeepInfra key rotation.
2. **Fix the reopen defect,** and add the library access service (scoped in
   `LIBRARY-ACCESS-API-SCOPE.md`). It unblocks every outside agent session,
   Geo-Grapher's included.
3. **Commit the uncommitted Geo-Grapher integration changes on a branch,** run
   the suite, then do wave 4 Tasks 2–4 together with MF-030, MF-024 and MF-021a,
   per section 5.
4. **Real-host acceptance:** MF-001, then MF-035, MF-044 and MF-045.
5. **After the release:** MF-036–041 and W1–W6, with Geo-Grapher's lineage as the
   code-side evidence for MF-036/037.
