# Phase 6–7 F3 security preparation

Scope: owner-authorised, controlled local-server review on feature branches, 2026-11-13. This is release preparation, not a remote penetration test or an assertion that F3/F4 exit criteria are complete. No third-party systems or live user stores were probed.

## Environment and boundaries

The installed wheel served a disposable copy of real ToolSet, librarian-v2, librarian-survey and paper stores at `127.0.0.1:8788`. The copy is under `D:/Librarian_V2/tmp/geo-grapher-qa-workspaces/security/20261113-final-a3`, with a separate approved browse root. All test writes, temporary folders, junctions, proposals and jobs belonged to that copy. Playwright exercised real HTTP and a browser, with one worker. Original gate stores, frozen wheels and benchmark inputs were not modified.

The threat model is an untrusted browser origin or untrusted path/request reaching a local, single-user service. Native local API clients without Origin remain supported. This is not an authenticated remote multi-user service, nor a sandbox against hostile local processes that already control its files. The SDK's loopback-origin policy and browser CORS behavior are separate boundaries.

Controls reviewed: Host/Origin validation, JSON mutation routes, body-size admission, picker containment/reparse points, preview/execution boundaries, pruning as derivation, proposal validation and replay, and safe error/metadata retention. Source mapping covered `graph_server.py`, `workspace_init.py`, `graph_catalog.py`, the transport guard and QA cleanup. No generic claim of exhaustive authentication, denial-of-service or OS-race assurance is made.

## Findings and repairs

| Finding | First observed behavior | Impact / priority | Repair |
|---|---|---|---|
| S1: same-root junction accepted | Picker returned 200 for a junction whose target was also inside the allowed browse root | P2 policy bypass: contradicts the promised no-reparse rule; no outside-root disclosure demonstrated | Check lexical path components before resolving; reject traversal/reparse components and check final containment |
| S2: preview-root change not revalidated | After a preview root became an outside-root junction, execute returned 200 and created a job; later stale-plan checking failed it | P2 boundary gap before the filesystem rescan; no outside-source publication demonstrated | Revalidate the root before job creation and again in the worker before applying the plan |

Both were reproduced against the installed baseline wheel, not inferred only from a read-through. Two unit oracles then failed on the same inputs before the fix. Existing stale-plan checking prevented successful ingestion in the observed S2 attempt; this report does not claim an exfiltration or original-store write.

## Executed evidence

| Attempt | Result | Evidence |
|---|---|---|
| Real-store browser baseline on final wave-4 wheel | 5/5 PASS | `output/qa-real/results-f3-security-baseline.json` |
| First live HTTP/browser security pass | 4/6 PASS, S1/S2 FAIL | `output/qa-real/results-f3-security-first.json` and retained traces |
| Unit regressions before guard fixes | 2 FAIL, 15 PASS | `output/w4-f3-security-unit-red.log` |
| Focused guards/catalog after fixes | 47 PASS | `output/w4-f3-security-unit-green.log` |
| Corrected live HTTP/browser security pass | **6/6 PASS** | `output/qa-real/results-f3-security-final.json` |
| Hardened-wheel real-store browser | **5/5 PASS** | `output/qa-real/results-f3-browser-final.json` |
| Hardened-wheel preset smoke | **28/28 PASS**, complete results ≤7,500 characters | `output/phase67-gates/wave4/preset-smoke-f3-security-final.json` |
| Full Geo verification after fixes | **690 backend, 16 frontend unit, 17 browser PASS**, typecheck/build PASS | `output/w4-f3-verify-final.log` |

The six live scenarios cover:

1. Foreign, opaque/null and deceptive loopback-prefix Origins rejected on mutation routes; hostile Host refused; graph heads unchanged.
2. Allowed picker control and outside, traversal, UNC, outside-target junction, same-root junction and URL-like inputs refused for picker/preview.
3. Preview root replaced by an actual Windows junction refused before job creation, with the fixture restored afterwards.
4. Invalid plan/job IDs, traversal pruning paths, malformed JSON and >4 MiB request bodies rejected without source graph mutation.
5. A real related-code proposal: invalid kinds/limits and blank rationale refused; a justified rejection succeeds; replay returns conflict. No synthetic candidate or accepted bridge was inserted.
6. An opaque-origin browser page cannot submit the JSON mutation. The browser result is recorded alongside direct Origin-header HTTP tests; it is not used to attribute every browser block solely to the server guard.

The guarded server wheel is `output/phase67-gates/wave4/f3-security-dist/geo_grapher-0.1.1-py3-none-any.whl`, SHA256 `77b647c92a3261467a1bc89434af91a2146fb99c207cf81246a9a90abb2f170f`. It adds the HTTP guard fixes after the sealed final model-cycle wheel (`a390f2…`). No model cycle was repeated for this patch: wave-4 code evaluation remains closed. The MCP/agent implementation and Librarian runtime were not changed by the HTTP repairs.

The final exact-wheel real-store browser, preset and cleanup audits are recorded with gate §17/§18. This controlled server uses the repository's QA-only cleanup route; that route is not added to the production package by this work.

## Privacy, retention and remaining release work

No credentials were inspected, printed or copied into evidence. Approved model wrappers read their configured key internally for the separate final code cycle; the security tests made no model/provider calls. New delivery diagnostics retain bounded IDs, ranges and hashes, not full tool source text; answers, browser screenshots and traces can still contain private code and local paths, so evidence remains local and has not been pushed. Test-owned proposals/derived graphs are removed after each run and original graph heads are compared with the preparation manifest.

QA cleanup was run before each browser/security cycle. Its managed-root tests cover stale/forged plans, frozen wheels, protected gate paths, actual junctions, timestamp ordering and a target replaced between deletions. Unmarked or questionable copies are retained. Harness-owned fixture links are removed only as link entries during teardown; other reparse content remains protected.

The live Resource-Library pilot, owner hands-on acceptance, W3-5 decision, F2 merges, reviewed migration/backup exercise and 0.2.0 build/sign-off remain outside this security pass. The future C14 rule is still only a proposal; the existing wave-4 samples are not rescored. No remaining confirmed S1/S2 defect is accepted merely by documentation: both have passing regressions and live-server checks.
