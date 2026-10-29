# Sprint state (resume capsule; read this first, not the conversation)

Updated: 2026-10-28 evening. Plan of record: `C:\Users\jakem\.claude\plans\c-users-jakem-downloads-workflow-discus-ethereal-turtle.md`. Start with `00-summary.md`.

## Rules in force
Evidence tags M (measured by script), R (reported), U (outside claim: verified / plausible / unverified). Delegated claims need a verbatim anchor, checked locally. No product code changes. No commits in either repository. Session logs are parsed for metadata only and never sent off the machine.

## State
- **Done:** deliverables 00 to 08 in this folder; 26 scripts in `scripts/`; data in `data/`; 87 DeepInfra calls (85 extraction, 2 critic; 2.72M input tokens, $2.45 live, 0 failed); independent critic pass done and adjudicated (`data/critic_adjudication.csv`; 13 defects fixed, 14 traceability gaps closed in `data/supporting_totals.json`, 5 false positives; Codex duplicate token events removed (308) and the reconciliation in `data/determinism_check.json` now passes for 203 of 205 threads).
- **Vault write-back (D:\Resource-Library), uncommitted:** 11 new draft notes in `06-Papers/` (status draft), 1 new `09-Applications/Application - Librarian V2 Agent Delegation Review 2026-10.md`, and small edits to `06-Papers/Paper Index.md` (new batch, paper_count 43) and `09-Applications/Application Index.md` (one row, record_count 19). No existing note was edited otherwise. HDDLGym (reading-list #11) has no first-page identifier, so no note was written.
- **Repo `D:\Librarian_V2`:** HEAD unchanged (`11bdd5b`); untracked `reports/2026-10-28-agent-workflow-sprint/` and `tmp/`.
- **Spend:** `claude-ledger.json` committed about 2.6 of 8 USD (the runner's stale cards understate GLM-5.3 and DeepSeek-V4.1-Flash; live-price cost is in `tmp/sprint/lanes/results.jsonl`).

## Remaining
1. (done) Critic findings adjudicated and fixed.
2. (done in part) Claim-register spot-check: the verified rows and the broadest rules were re-read; CL-025 (OpenAI manuscript count) went from verified to plausible, so the register now reads 3 verified, 22 plausible, 33 unverified. The 33 default-unverified rows were not re-read one by one.
3. Owner decisions listed in `00-summary.md`.

## Re-running
Deterministic scripts: `git_metrics.py`, `receipt_metrics.py`, `codex_log_metrics.py`, `plan_log_metrics.py`, `vast_queue_metrics.py`, `benchmark_digest.py`, `analyze_baseline.py`; `claude_log_metrics.py D--Librarian-V2 librarian_v2` (live log: sprint session excluded from the baseline). Model lanes: `prep_corpus.py`, `build_lanes.py`, `sprint_dispatch.py`, then `verify_anchors.py` with the repo venv python. `receipt_metrics.py` now tags each call `development` or `sprint`.

## Known issues
1. `claim_register.csv` tags come from hand-written regex rules (verified rows and broad rules spot-checked; default-unverified rows not).
2. Rate cards for DeepSeek-V4.1-Flash(-1017) and GLM-5.3 are stale in `scripts/delegate_deepinfra.py` (GLM-5.3 is 2x); the ledger understates them.
3. `G:\vast\cloud_queue.log` line 4 holds a plaintext instance API key: tell the user to rotate it; never copy it.
4. Codex "observed idle" after a limit includes time the user was away: an upper bound.
5. The corpus has 50 distinct papers (two PDFs are byte-identical); four files have no first-page identifier.
6. Past packets were not stored, so packet-contract conformance (M9) cannot be measured for past calls.
