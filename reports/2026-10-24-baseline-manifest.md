# BASE-01 baseline manifest

**Date:** 2026-10-24
**Task:** BASE-01 of the [unified implementation plan](../docs/unified-implementation-plan.md)
**Branch:** `v2-unified-plan` (from `master` at `df71ada`)

This lists every uncommitted file in the working tree at the start of
implementation, the feature it belongs to, where it came from, and the tests
that cover it. All of it is **baseline**: work done before the unified plan,
now recorded so later tasks build on committed state. `tmp/` (page renders of
a third-party paper) is deliberately left out of version control.

## Commit 1 — model and service adapter foundation

| File | Feature | Origin | Covered by |
| --- | --- | --- | --- |
| `src/resource_librarian/model_invocation.py` (new) | Invocation plans, tri-state expectation records, adapter descriptors, legacy bridge, redacted trace; per-record fingerprints, strict pack validation, visible load status | ChatGPT turns 21–22; hardening by Claude 2026-10-24 | `tests/test_model_invocation.py` |
| `src/resource_librarian/standard/model_expectations/core.json` (new) | Protocol baseline plus the 10-model role cohort | ChatGPT turn 22 | `tests/test_model_invocation.py` |
| `src/resource_librarian/service_adapters.py` (new) | OCR, TTS, STT, and embedding service contracts | ChatGPT turn 22 | `tests/test_service_adapters.py` |
| `src/resource_librarian/standard/service_expectations/core.json` (new) | Service expectation pack | ChatGPT turn 22 | `tests/test_service_adapters.py` |
| `src/resource_librarian/stt.py` (new) | Speech-to-text slot 7 | ChatGPT turn 22 | `tests/test_stt.py` |
| `src/resource_librarian/app.py` | Invocation runtime wiring, adapter qualification fingerprint, STT slot, service adapter summaries, expectation-pack status in readiness | ChatGPT turns 21–22; Claude 2026-10-24 | `tests/test_app.py`, `tests/test_qualification_jobs.py` |
| `src/resource_librarian/loop.py` | Walk-pinned invocation binding; Clerk/Scribe through the runtime | ChatGPT turn 21 | `tests/test_model_invocation.py`, `tests/test_loop.py` |
| `src/resource_librarian/clerk.py` | Evidence-backed structured-output policy | ChatGPT turn 22 | `tests/test_clerk.py` |
| `src/resource_librarian/embed.py` | Embedding representations and namespaces | ChatGPT turn 22 | `tests/test_embed.py`, `tests/test_vectors_slot.py` |
| `src/resource_librarian/ocr.py`, `tts.py`, `vault.py` | Service contract use | ChatGPT turn 22 | `tests/test_tts.py`, `tests/test_ocr.py` |
| `src/resource_librarian/providers.py` | Walk-unique synthetic tool-call IDs | Claude 2026-10-24 | `tests/test_model_invocation.py` |
| `src/resource_librarian/doctor.py` | "model expectations" check | Claude 2026-10-24 | `tests/test_model_invocation.py` |
| `src/resource_librarian/ui/app.js` | Adapter tile line, STT slot, service contract label, stale-representation note | ChatGPT turns 21–22 (edited in the built bundle only) | Rebuilt from `ui/src` — byte-identical |
| `ui/src/panels.ts`, `ui/src/settings.ts` | The same UI changes ported to source | Claude 2026-10-24 | `npm run check`; the rebuild equals the shipped bundle |
| `tests/test_model_invocation.py`, `test_service_adapters.py`, `test_stt.py` (new); `test_app.py`, `test_clerk.py`, `test_embed.py`, `test_qualification_jobs.py`, `test_tts.py`, `test_vectors_slot.py` | Tests for the above | ChatGPT; Claude | Repository venv |

**Found while inventorying.** ChatGPT's UI changes existed only in the built
bundle, not in `ui/src`. The next `npm run build`, including the release build
and the Obsidian plugin built from the same entry point, would have dropped
them silently. They are now in the TypeScript sources.

## Commit 2 — design documents

`docs/model-invocation-architecture.md`, `docs/model-adapter-requirements.md`,
`docs/model-adapter-cohort-2026-10-23.md`, `docs/model-expectations-registry.md`
(cross-links), `docs/audited-engagement-harness.md`,
`docs/unified-implementation-plan.md`. These are specifications. Their
implementation status is reconciled by BASE-03.

## Commit 3 — reviews

`reports/2026-10-24-harness-and-adapter-plan-review.md`,
`reports/2026-10-24-chatgpt-transcript-review.md`,
`reports/2026-10-24-architecture-blindspot-verification.md`, and this manifest.

## Regression baseline

Recorded under the repository venv (`.venv\Scripts\python.exe -m pytest tests`)
before commit 1. See the commit message of commit 1 for the counts. In this
interpreter the real-child Host test is skipped by the venv-redirector guard
that CORE-02A replaces.
