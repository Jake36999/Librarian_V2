# V1 to Librarian capability matrix

**Status:** reconciled against passing acceptance evidence on 2026-10-30
(ACCEPT-03). Each row names the evidence it rests on. The plan's
[acceptance matrix](../tests/test_acceptance_matrix.py) checks each of eight
workflows for success, refusal, recovery and no mutation on failure. A row
that leans on anything less says so.

“Internal pack” means a first-party module behind the `InternalPack` boundary,
not a third-party plugin marketplace.

## Status vocabulary

| Status | Meaning |
| --- | --- |
| ported | The V1 user-visible capability is kept. Acceptance evidence covers it. |
| changed | The outcome is kept, but an unsafe or impractical mechanism is deliberately replaced. Acceptance evidence covers it. |
| internal pack | A narrower, first-party module. Its evidence is stated per row and may be partial. |
| local evidence only | It works in in-process and packaged fixtures on the owner's Windows host. The real host applications have not been accepted yet (ACCEPT-02). |
| partial | Part of the stated capability exists. The missing part is named. |
| excluded | Deliberately left out for now, with a named reason and a named way back. |
| dropped | Not carried forward. A named replacement or workaround exists. |
| deferred | Planned for later work (V3, or a later V2 task) and not shipped. |
| retired | A V1 mechanism removed on purpose. |
| not adopted | Proposed in a design document. The owner has not adopted it. |

## Research capabilities carried from V1

| Capability | Status | V2 treatment | Evidence |
| --- | --- | --- | --- |
| Markdown source catalogue, evidence and concepts | ported | Native vault formats and evidence-first source notes are retained; evidence is content-addressed. | Acceptance: evidence, staging and promotion. `test_evidence.py`, `test_concepts.py`. |
| Search, source intake and local index | ported | The Core-owned `IndexService` is the only SQLite owner; clients call Core APIs. | Acceptance: research intake. `test_search.py`, `test_sqlite_ownership.py`. |
| Sessions, staged writing and approval gates | ported | Existing phase and approval semantics remain the control plane. | Acceptance: evidence, staging and promotion; profiles, bundles, macros and checkpoints. `test_sessions.py`. |
| V1 source continuity | changed | A guided, one-way import previews and stages selected records ([migration guide](migration.md)). It never edits V1 or auto-promotes content. | Acceptance: V1 import. |
| Model tiers | changed | Versioned vault-scoped profiles, host records, role/slot bindings, compact tool bundles and per-role qualifications replace positional routing. G2 and G4 are closed. | Acceptance: profiles, bundles, macros and checkpoints; service slots. `test_route_picker_snapshot.py`. |
| Common research walks | changed | The audited `inspect_map_source`, `search_and_judge`, `intake_to_stage`, `evidence_to_claim_check` and `review_staged_candidate` macros make their expanded plan and stops visible. | Acceptance: profiles, bundles, macros and checkpoints. `test_workflows.py`. |
| Ranking learning (V1 use signals) | internal pack | Offline candidates and a manual Current/Candidate/Compare selector replace percentage traffic canaries. A candidate can be selected only after its offline benchmark is recorded. | Acceptance: manual ranking. |
| Source-bound workbench | changed | Engagements require catalogued sources and pinned revisions. Docker is the only mode called isolated, and every run records its isolation label. | Acceptance: Workbench execution labelling. A real Docker run is ACCEPT-02. |
| Community/graph advice | internal pack (partial evidence) | Deterministic, disposable-index reports use wikilinks and declared topic/concept links; they never rewrite Markdown or ranking. | Tools `community_rebuild`, `community_reports` and `community_disagreements` are registered. Tests cover only that the rebuild uses the Core's index service (`test_core_index_service.py`). **No test checks the communities it reports.** Not in the acceptance matrix. |
| Repository capability extraction | internal pack (partial evidence) | A revision-pinned, bounded plan/materialisation path that executes no code. It selects files by suffix (`.py`, `.ts`, `.tsx`, `.js`, `.jsx`); it does not parse those languages. | `test_extract_pinning.py` covers revision pinning, the reviewed-plan check, and a materialised excerpt from a Python file. **No test uses a TypeScript or JavaScript file.** Not in the acceptance matrix. |

## Clients and services

| Capability | Status | V2 treatment | Evidence |
| --- | --- | --- | --- |
| Browser chat and local HTTP API | changed; local evidence only | Served by a per-vault Core with a protocol handshake and dynamic ports. | Acceptance: Browser, Obsidian and Cowork lifecycle. `test_app.py`, `test_shutdown.py`. |
| Obsidian two-way Markdown use | changed; local evidence only | Human edits stay direct. Core writes use document leases, debounce and conflict checkpoints. | `test_watcher_recovery.py`, `test_obsidian_adapter_contract.py`. Real Obsidian with SecretStorage is ACCEPT-02. |
| MCP/Cowork access | changed; local evidence only | Uses the same registry and Core safety rules, with legacy tiers mapped to profiles. | `test_mcp.py`, `test_packaged_adapter_smoke.py`. The real Claude/Cowork interface is ACCEPT-02. |
| Service slots (OCR, text to speech, speech to text, embeddings) | changed | Each slot has its own canonical binding and reviewed service contract, and a refused choice changes nothing. | Acceptance: service slots. OCR page rendering needs the optional `pypdfium2`; its test skips without it. |

## Capabilities new in V2

| Capability | Status | Treatment | Evidence |
| --- | --- | --- | --- |
| Create / Adopt / Attach an existing documents folder | changed; local evidence only | Read-only survey, then compare-and-apply adoption: documents stay byte-identical, an unrelated `.librarian` halts it, and the watcher is scoped. G3 closed on 2026-10-30, on local evidence. | `test_deploy_survey.py`, `test_adoption.py`. Running an adopted vault through the full app is ACCEPT-02. |
| Workspace documents in adopted folders | partial | Markdown without frontmatter is searchable as a workspace document and is never rewritten. **Attached read-only roots are not indexed** (excluded below). | `test_workspace_documents.py`. |
| Document identity and duplicate explanation | changed | Ids survive Obsidian renames and moves. Duplicates are explained by layer, and nothing is merged or deleted. | `test_document_identity.py`. |
| Audited long-horizon sessions | partial | Requirements, contracts, Tier A verifiers, research rounds with per-grain closure, and mechanical closure with a protected-target audit. **Missing:** Tier B review (HARNESS-08, needs paid evaluation) and targeted trust propagation (HARNESS-09, deferred). **The share of grains closed by Tier A has not been measured on real sessions**, because none have been run. | `test_audit_events.py`, `test_audited_session.py`, `test_closure.py`, `test_research_round.py`, `test_mechanical_closure.py`. |

## Excluded, dropped, deferred, retired and not adopted

| Item | Status | Reason, and the way back |
| --- | --- | --- |
| V1 normalised surveys, queues, external-link records, staged backlog and lens backlog | dropped | The V1 import carries catalogued notes (kept whole as `v1_note` evidence), not V1 machine state. Re-ingest a source to rebuild its V2 evidence. |
| V1 drafts, canvases, generated hubs/indexes, workflows and untyped notes | excluded | Left out of the default import set. Drafts can be included explicitly (`with_drafts`); the rest are not catalogue records. |
| Indexing attached read-only roots | excluded | The index reads only inside the library's own root. An attached folder is recorded in the manifest and never written into, but it is not searchable yet. |
| Structural heading/block/link index (DEPLOY-05) | deferred | The plan marks it deferred. Its dependencies (DEPLOY-04 and G4) are now met, but an evaluation must prove its value before graph-depth work begins. |
| Tier B LLM audit (HARNESS-08) and trust propagation (HARNESS-09) | deferred | Tier B needs a paid, predeclared evaluation before it can be a default. Trust propagation follows it. |
| Development-agent harness profile (DEV-01 to DEV-14) | not adopted | Proposed in [development-agent-harness.md](development-agent-harness.md); an open owner decision. |
| Public plugin marketplace / arbitrary executable plugins | deferred (V3) | V2 does not ship publisher PKI, a marketplace, a third-party UI runtime or arbitrary plugin execution. |
| Automatic live ranking rollout | retired | A person selects or restores a ranking version. |
| Direct concurrent adapter SQLite access | retired | All adapter reads and writes go through the active Core. |

## How to interpret the matrix

“Ported” and “changed” are used only where the acceptance matrix covers the
workflow. “Local evidence only” means the behaviour passes on the owner's
Windows host in fixtures, including packaged adapters; it is not yet a claim
about the real host applications. That claim waits for ACCEPT-02 and, for a
signed release, RELEASE-03. Where a row says partial, the missing part is
named, and the product does not claim it.
