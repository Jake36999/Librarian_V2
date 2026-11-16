# Ingestion contract audit â€” 2026-11-15

Status: incomplete pipeline; not verified enrichment. No additional paid evaluation authorized by this audit.

## Evidence

- `docs/access-model.md` specifies catalogue â†’ graph â†’ section â†’ original verification; two tier-2 comparisons or one tier-1 comparison. `source_verification_plan` plus a free dispatch dry run implements planning separately from ingestion.
- `content_roots.py` implements versioned owner-approved connected roots and compare-and-apply fingerprints. Attached roots are read-only. This is the existing configuration foundation, not a reason to rewrite each tool per project.
- `batch.py` runs validate, parse, read, lenses, data, relate, metadata, review. Its final review checks Bottom Line draft status, not independent source equivalence. No verification stage is enforced in this batch.
- Parse only converts PDFs marked cleanup or needs_ocr; usable PDFs can bypass persistent Markdown conversion. `paper_graph.py` correctly marks these catalogue_only and unpublished.
- The first pilot intake captured all ten PDFs through mechanical extraction. Five descriptions were initially complete and five queued. They were opening-text captures, not full-source enrichment.
- At audit time, first two batch items were partial with 0/12 and 0/4 reading coverage. Neither had clean_file. Third item had begun reading. No semantic verification of all ten exists.
- Resume reuses matching logged stage keys regardless of completion status; queued/partial work may be skipped. This remains a blocker.
- Clerk unavailable errors become queued results; a directory of task JSON is not an automatic worker. Exact underlying provider failure has not yet been established.
- Acceptance prepares attachment copies inside Sources/<kind>/files; this differs from an exclusively external-reference catalogue. Original files are retained. The new connected-path fix does not settle that product policy.

## Fixes already made, scope and limitations

Shared connected-read resolver used by ordinary file reads and PDF/OCR tools; accepted external attachment resolution; common code/data suffixes supported by text extraction. Four new read/conversion cases failed before the change. Focused suites: 70 + 55 passed. Live person read returned 9 PDF pages and bounded text. These checks establish file access, not conversion fidelity or semantic recall. No full-suite result or merge is claimed.

## Required orchestration contract

Extend the existing configuration/contract framework, rather than adding per-project source edits. Versioned, owner-approved scope must name library and connected roots, exclusions, read/analyse/edit capabilities, actor bindings, expiry/revocation, source revision, ingestion stages, required coverage, actual model routes, token/output and spending bounds, verification requirements and derivative destinations. Tier-0 is an owner-delegation concept, not a self-asserted model trust flag. A scoped owner approval supplies authority; DeepInfra defaults receive none. UI and tools must resolve and display the same effective contract and any narrowing refusal.

Read permission, authority to modify a project, authorship and canonical publication are distinct. Granting project access does not reclassify third-party material as owner-created or establish semantic verification. Generated work belongs in library operational storage unless the owner explicitly authorizes another destination.

## Required closure before scaling

1. Confirm cancellation; preserve first outcomes and spend records.
2. Fix and test retry semantics; expose structured Clerk queue reasons and diagnose actual route failure.
3. Ensure full persistent conversion where paper graph/page verification requires it, preserving original SHA and page anchors.
4. Gate verified completion on coverage, source identity and actual independent comparison; separate draft success from verified status.
5. Run free end-to-end connected-project fixtures, source-mutation checks, recall and verification dry runs before more paid work.
6. Re-estimate using measured routes, including the distinct fixed PDF conversion model. Existing ~$6 estimate is provisional and cannot establish cost of this corrected pipeline.


## Owner clarification and corrective guardrails (2026-11-15)

Markdown is the persistent machine-reading surface and the Obsidian-compatible format; direct extraction/conversion is hidden under `.librarian/`, while the catalogue summary is visible. Originals remain available for person reading and bounded validation. Do not use catalogue prose as a surrogate for source text when building a paper graph.

Audit of this session found the new resolver incorrectly required a purpose classification after attachment and omitted configured excludes. Both were demonstrated RED and corrected. Read-path authority now lives in content_roots.resolve_read_path and is reused for original verification. It honours existing attach configuration (including unclassified attachments), explicit deeper exclusions, configured excludes and the existing enabled project-root switch. There is no new tier-0 trust flag, permission store, model binding, or project-write grant.

Session operating contract:
- Before changing access policy, identify the existing owner setting, manifest, registry guard and scoped contract that own it. Add regression coverage showing those settings change effective behaviour.
- Separate path authority, actor permission, authorship/publication and representation verification. A person endpoint access check is not an agent-route acceptance test.
- Inspect full stage results, coverage and omissions before reporting completion; HTTP 200, a produced summary or a graph artifact are insufficient.
- Do not restart or resume paid processing based only on a path smoke test. Require a no-model end-to-end rehearsal for the actual staged inputs, retry semantics and graph/verification dependencies, then account for remaining budget.
- Preserve first results. Never count cached partial/queued stages as completed work. Never substitute model self-report for the verifier evidence.

Cancellation has now been confirmed in the preserved run log, after the third paper's queued read. No further paid processing is dispatched by this correction. Resume, conversion-completeness and mandatory independent-verification gaps remain tracked; this access correction does not claim to close them.
