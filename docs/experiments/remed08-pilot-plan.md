# REMED-08 pilot plan: wasted effort after REMED-06

Status: **approved and in progress.** The canary and DeepSeek control are
complete. MiMo tasks t1--t3 were attempted; two unknown outcomes retained
their full reservations. On 2026-10-31 the owner chose the session-only stop
policy below before t4--t8 resume.

## Why

REMED-06 is not done until "a bounded pilot shows less wasted effort with
admission unchanged". REMED-08 is the targeted G5 re-measurement within the
existing $8 ledger, kept beside the 32/74 and 25/74 runs as separate evidence.
This one paid run serves both.

It is also the first real use of three changes that so far have only been
tested locally:
- the per-dispatch ledger reservation (REMED-05);
- reconciliation before a closure (REMED-03);
- the stall limit (REMED-06).

## What is compared

The **baseline** is the re-run at `a9be71b`: same 8 tasks, same two routes,
results in `tmp/g5/rerun-*`.

| Route | Tier A | Refused calls | Sessions at `max_turns` | Model calls | Spend |
| --- | --- | --- | --- | --- | --- |
| DeepSeek-V4.1-Flash | 19/37 (0.514) | 41 | 0 of 8 | 327 | $0.69 |
| MiMo-V2.6-Flash | 6/37 (0.162) | 881 | 5 of 8 | 434 | $1.09 |

MiMo's waste was refused admission: 530 refused calls on t1 alone. It
omitted the `verifiers` argument 597 times across its sessions. DeepSeek's
was small.

The **candidate** is the current master, recorded by exact commit at run time
(`4742baa` or later). Since the baseline, these changes landed:
- `c0f7736`: admission fills an omitted plan entry from the person's binding;
- REMED-01: validation of adopted libraries;
- REMED-02: grouped search;
- REMED-03: drift reconciliation, and verified only through the person's
  named verifier;
- REMED-04: Workbench limits;
- REMED-05: per-dispatch reservations;
- REMED-06: predicate ids, the contract skeleton, refusal details and stall
  parking.

**Confound, stated in advance.** The candidate differs from the baseline by
all of those, not by REMED-06 alone. `c0f7736` in particular targets the same
MiMo failure. A difference can be credited to "the current build", not to
any one change. An ablation that isolates REMED-06 (the same build with
`audited_stall_limit` set out of reach) would need a second MiMo run of about
$1.10. It is not proposed; the owner may add it.

## The slices

| Step | Slice | Why | Expected spend |
| --- | --- | --- | --- |
| 0. Canary | DeepSeek, t1-design-patterns only | First real dispatch through the REMED-05 gate. Check the ledger entries settle `completed`, with metered usage, before any larger spend. | about $0.07 |
| 1. Primary | MiMo, all 8 tasks | Where the waste was. | about $1.10 or less |
| 2. Control | DeepSeek, all 8 tasks | The no-regression check on the route that worked. | about $0.70 |

Everything else is held to the baseline:
- the task file `docs/experiments/g5-tasks.json`, unchanged;
- `--max-turns 12`, a restart after turn 2, and the fixed answer;
- the stall limit at its default of 8.

If the canary shows any `uncertain` or `started` entry, or a charge far from
its metered usage, stop and report; steps 1 and 2 do not run.

## Measures (declared before the run)

**Wasted effort (the primary measures).** Per route, candidate against
baseline:
1. refused calls, in total and per session (median);
2. model calls per Tier A closure;
3. dollars per Tier A closure;
4. sessions ending at `max_turns`.

**Reported alongside:**
- questions asked;
- stall parks, and which requirements they parked;
- refusal kinds, from REMED-06's `details`;
- Tier A share with its interval;
- the ledger's reservation and settlement counts per status.

**Admission unchanged (the guard).** These are the original G5 conditions:
- histories valid, 16 of 16 (legacy is not valid here: every history is new);
- 0 false closures in the closure audit, each closure stating whether it was
  independently re-checked or re-run;
- forced restarts reproduce the state hash, 16 of 16;
- every `verified` predicate passed through the verifier the person named
  (the REMED-03 rule; checked from the logs).

## Proposed decision rule (for the owner to adopt or amend)

REMED-06's exit is met if all of the following hold:

1. **Guard:** all four admission conditions above hold for both routes.
2. **MiMo, less waste:**
   - total refused calls at most half the baseline's (881, so 440 or fewer);
   - model calls per Tier A closure below the baseline's (434 / 6, about 72);
   - fewer sessions end at `max_turns` than the baseline's 5.
3. **DeepSeek, no regression:**
   - the candidate's Tier A share interval overlaps the baseline's
     (0.359–0.666);
   - refused calls are no more than double the baseline's 41.

"Half" and "double" are this plan's proposal, open to amendment, chosen
because the baseline differences are large. They are not figures from the
reviews. If the rule fails, the report says which part, and REMED-06 stays
open.

## Budget

The ledger stands at $4.69723 of $8.00, with $3.30277 left. On the first
paid run it converts to the shared delegation ledger (pool `g5`), and the old
file is kept as `tmp/g5/ledger.g5v1.json`.

| Step | `--budget-usd` (the run's own cap) |
| --- | --- |
| 0. Canary | 0.15 |
| 1. MiMo | 1.40 |
| 2. DeepSeek | 0.90 |
| **Most this pilot can spend** | **2.45** |

That leaves at least $0.85 in the pool. Each request reserves its worst case
before it is sent. An `uncertain` outcome keeps its whole reservation and
stops its current task. Later tasks may use only the genuinely remaining run
and pool caps. Structural failures (including a refused reservation or an
unbounded request) still stop the run. A person may resolve an uncertain entry
with `delegate_ledger.py reconcile`; the two entries already awaiting owner
reconciliation are not changed by the runner-policy update.

## Commands

The same library and task file as the re-run, and a new run folder for each
step:

```
python scripts/g5_measure.py --library D:/Resource-Library/.librarian-app \
  --tasks docs/experiments/g5-tasks.json --run-dir tmp/g5/remed08-canary --only t1-design-patterns \
  --route deepinfra:deepseek-ai/DeepSeek-V4.1-Flash --budget-usd 0.15 --confirm-paid \
  --env-file D:/Resource-Library/.utility/.env

python scripts/g5_measure.py ... --run-dir tmp/g5/remed08-mimo \
  --route deepinfra:XiaomiMiMo/MiMo-V2.6-Flash --budget-usd 1.40 --confirm-paid ...

python scripts/g5_measure.py ... --run-dir tmp/g5/remed08-deepseek \
  --route deepinfra:deepseek-ai/DeepSeek-V4.1-Flash --budget-usd 0.90 --confirm-paid ...
```

## The report

The results go in `reports/2026-10-30-g5-measurement.md`, in a new section
beside the 32/74 and 25/74 runs, which stay as they are. It includes:
- the baseline and candidate tables, and the decision rule's outcome;
- the confound statement;
- the ledger's entries for the pilot;
- the exact commit.

## Risks

- **Parking can lower the Tier A share.** A stall park ends a session
  earlier than `max_turns` would. That is the intended trade: less spend on
  unproductive loops. The share is reported, and the DeepSeek control guards
  against loss on a route that works.
- **An uncertain call stops its task.** A timeout or a reply without usage
  retains its reservation and prevents retries in that task. Continuing with
  a later task spends only within the remaining caps, so correlated provider
  failures can still consume the cap conservatively.
- **The stall limit of 8 is provisional.** This pilot measures it at one
  setting only.
- **Eight tasks per route is a small sample.** The intervals are nominal,
  because grains within a session are correlated.

## Approval record

The owner approved the slices, decision rule and caps before the pilot. On
2026-10-31 the owner additionally approved session-only stopping for unknown
outcomes: keep the complete reservation, stop that task, and let later tasks
continue only against the remaining caps.
