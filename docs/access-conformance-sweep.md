# C0 content-tool conformance sweep

Review baseline: native Wave L `54f17b5`, Geo Wave L `495d689`/`4e773a2`. This is a pre-fix census against the newly approved Part A0 contract. It does not apply S1–S6b or R.

The census includes all 180 native registrations, even metadata/control tools, plus every Geo MCP surface (canonical, graph-scoped, standalone paper and opt-in annotations). A materialised content path, arbitrary nested tool result, draft, plan or source text counts conservatively as potential content. Pure control receipts/counts are n/a. Unknown authorship is not silently interpreted as owner_created.

**Full-contract conformance: 0/98 native potential-content tools and 0/38 Geo potential-content operations.** This is not a claim that the existing permission boundaries fail: the new authorship contract is absent, so no mixed-content tool earns full conformance merely from its tier or Wave L provenance label. Metadata/control rows do not improve this score. Surface duplicates are counted separately because wrappers can change exposure; canonical 1.0/1.1 share one implementation and one row per operation.

Actors are possible entry points, not unconditional authority. The native registry's consult/contribute/curate tiers are distinct from model role tiers 1/2/3. MCP agents are capped at contribute; a lead is further bundle/profile-gated; helpers have the explicit HELPER_TOOLS allow-list; a task worker sees only its queue payload. Scribe models receive no registry tools. Live runtime MCP installations are not enumerated: no connected Core was used. Their generic adapter is reviewed separately below, not asserted compliant.

## Native registry — 180 tools

| Tool | Minimum tier | Possible actors, subject to gates | Possible authorship | Status | Fix | Source evidence |
|---|---|---|---|---|---|---|
| accept_artifact | curate | person | n/a | n/a | — | src/resource_librarian/tools/audited.py:394 |
| accept_workflow | curate | person | n/a | n/a | — | src/resource_librarian/tools/workflows.py:66 |
| activity | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:1943 |
| add_candidate | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1301 |
| admit_contract | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/audited.py:62 |
| advance | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:501 |
| agenda | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/library.py:517 |
| answer | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:478 |
| archive_note | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/authoring.py:323 |
| ask_user | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:440 |
| audit_projection | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:598 |
| audit_targets | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/audited.py:259 |
| batch_cancel | curate | person | n/a | n/a | — | src/resource_librarian/tools/batch.py:33 |
| batch_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/batch.py:24 |
| branch_session | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:337 |
| capabilities | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/core.py:10 |
| capability_candidates | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/capabilities.py:48 |
| capability_install | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/capabilities.py:110 |
| capability_propose | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/capabilities.py:87 |
| check_notes | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/core.py:69 |
| checkpoint | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1264 |
| claim_run_preflight | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/upkeep.py:86 |
| clerk_next | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped); task worker (sessionless protocol only) | owner_created, generated, third_party | diverges | S1, S4 | src/resource_librarian/tools/staging.py:752 |
| clerk_submit | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped); task worker (sessionless protocol only) | n/a | n/a | — | src/resource_librarian/tools/staging.py:763 |
| close_brief | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1053 |
| close_session | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:543 |
| cohort_freeze | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/scout.py:40 |
| cohort_reviewed | curate | person | n/a | n/a | — | src/resource_librarian/tools/scout.py:47 |
| community_disagreements | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/communities.py:27 |
| community_rebuild | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/communities.py:9 |
| community_reports | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/communities.py:19 |
| concept_candidates | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/staging.py:739 |
| create_project | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:713 |
| decide | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1326 |
| deep_read | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:281 |
| deep_read_note | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:298 |
| delegate | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/delegate.py:31 |
| desk_pin | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/desk.py:38 |
| desk_show | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/desk.py:24 |
| desk_touch | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/desk.py:61 |
| desk_unpin | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/desk.py:50 |
| dik_rebuild | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:105 |
| dispatch_plan | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/plan_dispatch.py:158 |
| doctor | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/core.py:23 |
| document_duplicates | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:32 |
| draft_offering | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/sessions.py:1495 |
| duplicate_report | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:22 |
| edit_note | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/authoring.py:230 |
| embed_index | curate | person | n/a | n/a | — | src/resource_librarian/tools/library.py:334 |
| engagement_close | curate | person | n/a | n/a | — | src/resource_librarian/tools/workbench.py:103 |
| engagement_list | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workbench.py:125 |
| engagement_plan | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workbench.py:52 |
| engagement_propose | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/workbench.py:62 |
| engagement_start | curate | person | n/a | n/a | — | src/resource_librarian/tools/workbench.py:72 |
| evaluate | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/library.py:533 |
| extend_budget | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:682 |
| extract_materialize | curate | person | owner_created, generated, third_party | diverges | S1, S4 | src/resource_librarian/tools/extract.py:20 |
| extract_plan | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/extract.py:9 |
| filters | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:374 |
| freshness_check | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:9 |
| get_note | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4, S5, S6 | src/resource_librarian/tools/library.py:382 |
| gitignore_ensure | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/vault.py:36 |
| index | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:207 |
| index_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:229 |
| ingest | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/intake.py:39 |
| intake_run | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/intake.py:126 |
| lens_adopt | curate | person | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/lenses.py:34 |
| lens_drop | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/lenses.py:55 |
| lens_list | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/staging.py:722 |
| lens_pack_accept | curate | person | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/lenses.py:88 |
| lens_packs | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/lenses.py:79 |
| lens_show | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/staging.py:731 |
| lens_suggest | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/lenses.py:21 |
| library_profile | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/lenses.py:67 |
| list_claim_runs | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:95 |
| list_files | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | n/a | n/a | — | src/resource_librarian/tools/browse.py:90 |
| list_sessions | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:280 |
| list_workflows | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:26 |
| log_use | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1313 |
| macro_plan | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/macros.py:10 |
| macro_resolve | curate | person | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/macros.py:53 |
| macro_run | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/macros.py:26 |
| macro_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/macros.py:39 |
| model_catalog_adopt | curate | person | owner_created, generated, third_party | diverges | S1, S6b | src/resource_librarian/tools/model_catalog.py:20 |
| model_catalog_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/model_catalog.py:10 |
| model_expectation_propose | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/model_expectations.py:9 |
| note_move | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:412 |
| ocr_pdf | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S2, S3, S4 | src/resource_librarian/tools/pdf.py:51 |
| open_brief | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:974 |
| open_session | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:227 |
| park_session | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:310 |
| pdf_to_markdown | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S2, S3, S4 | src/resource_librarian/tools/pdf.py:13 |
| process_approved | curate | person | n/a | n/a | — | src/resource_librarian/tools/batch.py:9 |
| project_edit | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:922 |
| project_map | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S6 | src/resource_librarian/tools/sessions.py:950 |
| project_scan | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S6 | src/resource_librarian/tools/sessions.py:908 |
| promote_offering | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1685 |
| provenance_check | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:46 |
| queue_list | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/intake.py:148 |
| queue_remove | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/intake.py:159 |
| queue_retry | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/intake.py:177 |
| queue_source | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/intake.py:92 |
| ranking_benchmark | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/ranking.py:32 |
| ranking_candidate_generate | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/ranking.py:23 |
| ranking_compare | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/ranking.py:44 |
| ranking_restore | curate | person | n/a | n/a | — | src/resource_librarian/tools/ranking.py:64 |
| ranking_select | curate | person | n/a | n/a | — | src/resource_librarian/tools/ranking.py:54 |
| ranking_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/ranking.py:15 |
| read_evidence | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S4 | src/resource_librarian/tools/audited.py:224 |
| read_file | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4 | src/resource_librarian/tools/browse.py:67 |
| read_project | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S4, S6 | src/resource_librarian/tools/sessions.py:769 |
| read_result | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4 | src/resource_librarian/tools/results.py:9 |
| read_source_file | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4 | src/resource_librarian/tools/upkeep.py:57 |
| read_url | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/browse.py:38 |
| record_application | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1823 |
| record_assumptions | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:371 |
| record_synthesis | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1351 |
| record_trace | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/scout.py:66 |
| reduce_round | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/audited.py:360 |
| refile_source | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/taxonomy.py:67 |
| reflection_accept | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:1999 |
| reflection_draft | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/sessions.py:1969 |
| reject_artifact | curate | person | n/a | n/a | — | src/resource_librarian/tools/audited.py:414 |
| request_budget | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:666 |
| request_evidence | curate | person | n/a | n/a | — | src/resource_librarian/tools/audited.py:430 |
| research_round | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/sessions.py:1077 |
| resume_session | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:287 |
| review_due_open | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:856 |
| rewind_session | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:317 |
| rules | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/core.py:33 |
| run_claim_input | curate | person | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/upkeep.py:74 |
| run_list | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/browse.py:108 |
| run_pipeline | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:95 |
| run_resume | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:112 |
| run_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:105 |
| run_workflow | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:86 |
| sandbox_read | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sandbox.py:26 |
| sandbox_run | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sandbox.py:9 |
| sandbox_run_file | curate | person | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sandbox.py:36 |
| save_workflow | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:57 |
| scout_discover | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/scout.py:11 |
| scout_expand | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/scout.py:20 |
| scout_rank | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/scout.py:27 |
| search | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4, S5, S6 | src/resource_librarian/tools/library.py:236 |
| search_feedback | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:257 |
| search_work | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/work_search.py:74 |
| session_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:303 |
| set_effort | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/pace.py:17 |
| set_requirement | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:572 |
| show_workflow | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/workflows.py:41 |
| stage_artifact | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/audited.py:116 |
| staging_decide | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:500 |
| staging_flag | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/staging.py:706 |
| staging_list | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:156 |
| staging_preview | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:257 |
| staging_review | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:270 |
| staging_show | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/staging.py:236 |
| sweep | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/scout.py:55 |
| task_add | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/library.py:465 |
| task_done | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:496 |
| task_route | curate | person | n/a | n/a | — | src/resource_librarian/tools/sessions.py:2020 |
| topic_propose | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/taxonomy.py:41 |
| topics_list | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/taxonomy.py:13 |
| understanding_due | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/sessions.py:833 |
| understanding_record | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:802 |
| update_plan | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/sessions.py:351 |
| update_project | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/authoring.py:273 |
| v1_import_plan | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); task worker (sessionless protocol only) | owner_created, generated, third_party | diverges | R, S1, S6b | src/resource_librarian/tools/v1_migration.py:19 |
| v1_import_stage | curate | person; task worker (sessionless protocol only) | owner_created, generated, third_party | diverges | R, S1, S6b | src/resource_librarian/tools/v1_migration.py:28 |
| v1_import_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); task worker (sessionless protocol only) | owner_created, generated, third_party | diverges | R, S1 | src/resource_librarian/tools/v1_migration.py:42 |
| validate_workflow | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/workflows.py:50 |
| vault_commit | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/vault.py:54 |
| vault_push | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/vault.py:77 |
| vault_status | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/core.py:46 |
| verify_access | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/library.py:352 |
| verify_grain | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/audited.py:141 |
| views_refresh | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | n/a | n/a | — | src/resource_librarian/tools/taxonomy.py:78 |
| web_search | consult | person; lead (bundle/profile-gated); external agent (MCP tier-capped); research helper (read-only allow-list) | owner_created, generated, third_party | diverges | S1, S4, S5 | src/resource_librarian/tools/web.py:13 |
| withdraw_reference | curate | person | n/a | n/a | — | src/resource_librarian/tools/results.py:34 |
| write_note | contribute | person; lead (bundle/profile-gated); external agent (MCP tier-capped) | owner_created, generated, third_party | diverges | S1 | src/resource_librarian/tools/authoring.py:158 |

## Geo MCP — 40 operations

| Tool | Minimum tier | Possible actors, subject to gates | Possible authorship | Status | Fix | Source evidence |
|---|---|---|---|---|---|---|
| canonical:check_architecture | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| canonical:find_dependants | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| canonical:find_similar_code | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| canonical:get_architecture_context | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| canonical:get_entity_content | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| canonical:inspect_relationship_witnesses | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| canonical:search_entities | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/server.py |
| paper:annotate_document | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S2 | pipeline/mcp_doc_graph.py |
| paper:find_by_concept | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_annotations | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_claim | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_concept | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_corpus_status | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | n/a | n/a | — | pipeline/mcp_doc_graph.py |
| paper:get_document | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_outline | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_related | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:get_section | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| paper:search_documents | connection-scoped (no native registry tier) | person; connected MCP client (not tier-labelled) | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | pipeline/mcp_doc_graph.py |
| scoped:analyze_cross_graphs | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:check_architecture | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:compile_task_packet | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:federated_search | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:find_dependants | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:find_similar_code | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:get_architecture_context | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:get_entity_content | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:inspect_relationship_witnesses | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:list_bridges | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |
| scoped:list_graphs | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, B2 | src/geographer/graph_server.py |
| scoped:paper_find_by_concept | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_annotations | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_claim | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_concept | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_corpus_status | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | n/a | n/a | — | src/geographer/graph_server.py |
| scoped:paper_get_document | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_outline | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_related | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_get_section | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:paper_search_documents | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S3, S4, S5 | src/geographer/graph_server.py |
| scoped:search_entities | connection-scoped (no native registry tier) | person; lead; research helper; Clerk/Scribe connection principal: own-only; native models have no external registry tools | owner_created, generated, third_party | diverges | S1, S4 | src/geographer/graph_server.py |

## Supplemental Wave L paths and dynamic adapters

| Surface | Actors | Content/authorship today | Status | Follow-up |
|---|---|---|---|---|
| GET /api/folders; POST /api/folders/survey | Person via Core | Inventory, paths and staged suggestions; purpose only, no authorship or DIK inventory record | diverges | S1, R |
| POST /api/folders/draft | Person-approved qualified Clerk, metadata only | Generated staged description; provenance check not yet wired | diverges | S1, R; production drafting remains off pending owner approval |
| POST /api/folders/accept | Person only | Frozen-purpose decision and static graph application; no canonical authorship propagation | diverges | S1, R |
| init-workspace --survey-in | Native ingestion/operator | Shared metadata fingerprint and suggested strata; no evidence/DIK record | diverges | S1, R |
| apply-folder-review | Person-reviewed native caller | Static source graph with immutable snapshot, purpose/stratum, provenance | diverges | S1, R |
| review-mcp-config | Operator | Generated configuration only; never connects or accepts a server | n/a | Existing Wave L own-only Clerk principal is retained |
| Native dynamic MCP adapter (mcp_client._make_fn) | Lead; bounded Core packet-fetch expansion | Arbitrary external content; untrusted=True wrapper but plain read/open_world=False registration | diverges | S1 must test closure outside audited sessions; S4 targets/grants |
| Native writer/registry read-only guard | All native writers | Control; typed FOLDER_READ_ONLY, accepted internal child override, attached sources read-only | n/a | Retain Wave L checks while R changes ingestion |
| dispatch_plan tier-3 preflight | Lead orchestrator | PLAN_SCOPE before packets/models for direct third-party graph anchoring | n/a | Keep L4(a); S4 adds a bounded-target route, not free graph access |
| Bridge creation/proposals | Person/operator | Reference-only, owner decision across own/external boundary | n/a | Retain L4(d) and W3-5 firewall |
| Credential guards | All source readers | Refused names only; credential bodies never inspected | n/a | Retain L5; D6 graphify output hygiene is separate |

The CI guard requires an individual explicit declaration for every shipped registry/MCP operation, including new metadata tools. There is no wildcard approval. Native function/schema fingerprints invalidate stale reviews after implementation changes. These tests only ensure review coverage; **passing them is not a policy-conformance pass**. Runtime dynamic tools need a per-install declaration when S1 wires that surface; the generic adapter does not certify unknown servers.
