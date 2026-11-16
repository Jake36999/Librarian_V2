# Ten-PDF pilot recovery â€” 2026-11-15

Status: active recovery; not complete, not verified, not approved for full-corpus dispatch.

## Evidence and fixes

- Original attempts retained in the vault run logs. All ten sources initially remained partial; no claim that a terminal batch receipt meant successful ingestion.
- OCR completion now requires every required page. Partial conversions are retried. Successful pages have independent immutable conversion receipts and are reused.
- OCR requests use the selected route; bounded parallel IO follows its host concurrency setting. Rendering and persistent conversion writes remain on the caller thread. Per-thread response metadata prevents mixing page costs. Truncated responses are incomplete.
- Visual descriptions are requested separately from transcription. New recipe `ocr:v3-visual` distinguishes these outputs from earlier transcription-only conversions.
- Clerk task unavailability no longer discards successful sibling results. Failed essential extraction tasks no longer count as read chunks. Deep-read returns individual task failure reasons.
- A reproduced terms-schema contradiction required complete sentences but limited them to 300 characters. The prompt now requests bounded verbatim excerpts. Oversized returned sentences are reduced to contiguous excerpts containing the term, then schema and source-grounding checks still run; reductions are recorded.
- Batch cancellation signals its in-memory event without waiting behind writer work. Network work still holds the writer in several older tools; that architectural limitation remains.

## Live routes and measurements

- Original OCR Qwen3.5-397B: recurring timeouts and incomplete conversion.
- Gemma OCR comparison: 27.17 seconds, provider-reported $0.00051701; rejected for material equation transcription errors on the inspected source page.
- Qwen3-VL-30B comparison: 60-second timeout, retained.
- Qwen3.5-27B comparison: 21.86 seconds, provider-reported $0.00416442. Equations substantially better; a figure annotation error remains a verification finding. Selected through the normal service configuration endpoint.
- Qwen3.5-27B completed the current 22-page paper in approximately two minutes at concurrency four. Its graph artifact correctly says full conversion, page verification false, publication awaiting accepted folder.
- Gemma Clerk passed native L0 and L1 qualification (L1 run 9515126995c3b471f371, 1.828 seconds). Selected through the normal tier configuration endpoint. Earlier GPT-OSS Clerk attempts and the timed-out qualification client request are retained.
- The pilot comprises 198 PDF pages. Cost and fidelity assessment remains pending; successful-page costs alone exclude earlier failed/cancelled calls and Clerk work. No full-library run is authorized by this report.

## Validation

Full suite before the latest optical concurrency and term-evidence changes: 2524 passed, 1 skipped, 5 deselected (637.40 seconds). Subsequent focused suite: 80 passed. Earlier failing regressions and logs retained under G:/Libraries/_qa/. Final full-suite verification remains due after fixes settle.

## Remaining work

Finish ten sources with actual full coverage; retry the first two partial terminal items; inspect summaries/extractions against originals; run source-grounded recall and graph checks; reconcile cost including unknown billing; assess full-run scope and budget before dispatching either complete library. No merge or push performed.

## Continued recovery (through 2026-11-16)

- The 22-page paper reached 13/13 read chunks (59 claims, 39 evidence/limit entries); the 8-page paper reached 8/8 (35 claims, 18 evidence/limit entries). Native source verification is still distinct from full read coverage.
- The 34-page and phase-field papers reached enriched/full batch receipts.
- Actual remaining failures included unescaped LaTeX in JSON and oversized bullet fields. Invalid backslash escapes are repaired deterministically and logged, followed by schema/source checks. Oversized bullet items are discarded whole with recorded omissions while valid siblings survive; claims are never truncated mid-statement.
- Authorship lookup was rebuilding display provenance for all 1,583 folder cards for each evidence write. Policy lookup now reads validated decision metadata only. URI evidence handles never inherit filesystem-path authorship. Regression and taint tests retained.
- OCR is a reviewed orchestrator: network work runs outside the writer, persistent cache writes remain serialized, and changed originals are refused. Bounded pending writes allow optical capture to continue when another task temporarily occupies the writer.
- A dense page hit 4,000 output tokens. One bounded token-growth retry now uses measured prompt tokens and the selected route's declared window, with an 8,000 default configurable ceiling (services.ocr_max_output_tokens); both attempts' usage is retained. Unknown windows do not authorize growth.
- DeepInfra host concurrency was adjusted through the existing control endpoint to eight to share capacity between independent OCR and Clerk operations. Role profile ceilings continue to apply.
- Full-suite run 4: 2535 passed, 1 skipped, 5 deselected. Full-suite run 5: 2538 passed, 1 skipped, 5 deselected. Further final-source tests are required after the most recent changes; first failures are retained.
- Source hashes for all ten originals are in G:/Libraries/_qa/pilot-source-hashes-recovery.json. Live graph discovery succeeded through the authenticated native Geo service; paper artifact publication is still awaiting folder acceptance.
