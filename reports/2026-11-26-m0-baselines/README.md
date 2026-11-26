# M0: baselines and room to work

26 November 2026. This is the first milestone of [the implementation plan](../../docs/proposals/implementation-plan-2026-11.md), which the Owner accepted on 26 November. It records what tier 0 and the in-app models cost today, so each later milestone can be measured against it. It also says what M0 changed so that the cost can be counted from now on.

Provenance: **M** measured here, by the script or query named; **R** reported in an earlier record; **model** a figure from the systems-analysis packs' diagrams, not from a run.

## What M0 changed

| Change | Where | Checked by |
|---|---|---|
| **The Core records every outside call into it**: surface (MCP, person, declared agent), tool, session, outcome or refusal code, time, and result size. It records no arguments or content. Before this, the Core kept a log of its own model calls (`usage-*.jsonl`) and of its writes (`operations.jsonl`), but not of the calls made to it | `src/resource_librarian/call_log.py`; `.librarian/runtime/calls-YYYYMMDD.jsonl`; hooked into `App.mcp_call` and `App.person_call` | `tests/test_call_log.py` |
| **The pack check is a test** (CI pathway 1), with no workflow-file change. A planted stale view fails it | `tests/test_packs.py` | the suite |
| **The pack check works in a fresh checkout.** Specs were hashed with their line endings, so every view failed `--check` in a clean clone | `render_pack.py` `sha` | `tests/test_packs.py` |
| **Every shipped workflow and pipeline must load and validate** (CI pathway 8). The test now covers all 21 files, the two pipelines included | `tests/test_workflows.py` `test_standard_set_is_valid` | the suite |
| **Room to work.** Clean clones and scratch work go to `G:\Librarian-work` (106 GB free; Owner, 26 November). D: has 4.8 GB free and C: 2.9 GB | — | — |

## Tier 0: what the 19–20 November ingestion cost

| Measure | Figure | Provenance |
|---|---|---|
| Tier-0 turns on the main path, and on the worst | 8 and 10 | model: the as-is ingestion over the observed trace (performance table) |
| Write operations tier 0 made through MCP | 246 on 18 November, 36 on 19 November | M: the test vault's writer log (`E:\Librarian ACCEPT-02 Vault\.librarian\runtime\operations.jsonl`, `caller = mcp`) |
| Folder-acceptance writes | 128 on 19 November | M: the same log, `caller = folder-accept` |
| Batch writes | 224 on 18 November, 3,404 on 19 November | M: the same log, `caller = batch` |
| Refused calls in one burst | 92 in 6 seconds, then accepts reported that had not happened | R: policy, agent-roles-and-authority ("A tier-0 agent finishes its own work too") |

**What could not be measured, and why.** The tier-0 transcript of the 19–20 November run is not among the local transcripts.
- Codex reached the Librarian through the Core API and the CLI.
- Claude Code reached it through MCP and Bash.
- Neither transcript separates calls made inside one script: on 19 November one command sent 92 calls.
- So turns per run stay a model figure until the call log counts a real run.

Two runs that can be counted from transcripts, for scale (M: the scripts below, over local transcripts; aggregates only):

| Run | Calls to the Core | Owner messages | What came back to tier 0 | Refusal codes seen | Most-called |
|---|---|---|---|---|---|
| Codex session, 14–15 November (batch work) | 92 (27 and 59 by day) | 62 | about 43,000 tokens | 4 | `process_approved` 14, `batch_cancel` 9, `deep_read` 7, `batch_status` 6 |
| Claude Code, 15–26 November (11 sessions, mostly development, this one included) | 431 | — | about 90,000 tokens | 9 | — |

## In-app models: what the same run spent

M: the test vault's usage logs (`usage-20261118.jsonl` to `usage-20261120.jsonl`).

| Day | Model calls | By role | Tokens in / out | Reported cost | Calls that failed |
|---|---|---|---|---|---|
| 18 November | 278 | Clerk 252, cleanup 17, Lead 5, Scribe 2, research helper 2 | 398,328 / 83,698 | $0.038 | 3 |
| 19 November | 4,147 | Clerk 3,832, cleanup 305, Scribe 4, research helper 4, Lead 2 | 6,458,455 / 1,419,232 | $0.622 | 44 |
| 20 November | 7 | — | 1,167 / 113 | $0.000 | 1 |

The Clerk (tier 3) did 92% of the model calls on 19 November: the bounded reading tasks.

## The other baselines, already recorded

The [Librarian performance table](../2026-11-25-systems-analysis-finalisation/librarian/to-be/performance.md) and the [Geo-Grapher one](../2026-11-25-systems-analysis-finalisation/geo-grapher/to-be/performance.md) hold the rest, each with its provenance:
- 150 s per MCP ask and 600 s in the app;
- four budget extensions in the 20 November research run;
- 82 out-of-corpus candidates;
- 0 of 12 folder descriptions;
- 77.2 GB of disk for 30 graphs.

No figure there was measured against a running Librarian; each milestone's acceptance run measures its own rows.

## The fixed test folder for M5

M5's acceptance run needs the same input each time. Proposed:
- **The folder:** `E:\DataManagement\03-Retrieval-Routing-and-Graph-Query-Systems`, which holds 8 PDFs.
- **The vault:** a fresh library made for each run under `G:\Librarian-work`, never the existing test vault. That vault already holds these papers, so a re-run would only find duplicates.

The Owner may name another folder.

## Room on D: and C: (the Owner's decision)

Parallel sessions with their own worktrees still need space on D:, where the repository is. A session's worktree needed 5.4 GB on 26 November. Candidates, none removed:
- the uv cache, 834 MB on C:;
- the pip cache, 141 MB on C:;
- two worktree records whose folders are gone (`git worktree prune`);
- two old phase-6/7 worktrees under `D:\Librarian_V2\tmp\phase67-release-20261114` (not measured);
- `D:\LaptopShare.vhdx`, 10 GB.

## How to re-run

The transcript counts came from three read-only scripts in the session's scratchpad: `tier0_baseline.py`, `codex_baseline.py` and `claude_baseline.py`. They print aggregates only, and their outputs are in `G:\Librarian-work`. From now on, the Core's own call log replaces them:

```powershell
.venv\Scripts\python.exe -c "from resource_librarian.vault import Vault; from resource_librarian.call_log import CallLog; import json; print(json.dumps(CallLog(Vault(r'E:\Librarian ACCEPT-02 Vault')).summary(), indent=1))"
```
