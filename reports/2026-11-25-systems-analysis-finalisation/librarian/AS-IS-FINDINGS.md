# The Librarian as it is: where it goes wrong

25 November 2026. Step 2 of the approach in [PLAN.md](../PLAN.md): map it as it is, find where it goes wrong, then design the preferred version.

The [as-is pack](as-is/INDEX.md) draws 18 use cases from the code at `d9435e1` and the runs of 19–21 November, and records 54 weaknesses with their evidence in [the register](as-is/weaknesses.yaml):
- 24 gaps, 10 faults, 8 costs, 7 risks, 3 unverified claims and 2 drifts;
- grouped into ten root causes (below).

Each root cause ends with the rule the to-be pack must meet. The to-be answers individual weaknesses by id, and the index counts what is still unhandled.

## What already works, and stays

- **The Core's gates hold.** Refusals name their rule; nothing is written past a gate the caller does not hold; a stale folder or a stale revision is refused rather than overwritten.
- **Every item keeps its receipts.** A batch records each stage's status, coverage and what was not examined, so partial work is never credited as read.
- **Definitions are checked before they run.** Workflows are validated when saved, pinned by digest when they run, and refuse to resume after a change. Steps declare their dependencies, effects, acceptance and undo.
- **There is a real judge, in one place.** The audited session admits a contract, runs Tier A checks on the actual artifacts, records a missing check rather than skipping it, and re-checks its closures.
- **Phases are data.** Since W1, a test proves each phase offers every tool its gate or a refusal names.

## Root causes

### T1. No parent process (7 weaknesses)
Ingesting a folder crosses five surfaces: folder review, a separate queue click, intake, the batch and acceptance. Six activation surfaces enter the Core with different tiers, and none reaches a common parent. Nothing reconciles a folder's counts (surveyed, queued, staged, enriched, accepted). On 19–20 November control came back to tier 0 eight times on the main path. The person or tier 0 *is* the parent process.

**To-be rule.** Every unit of work runs under a parent process that owns the whole chain:
- it reconciles its own counts;
- it starts each child itself;
- it ends with one result.
A surface only starts or watches that parent.

### T2. Authority does not fit the work (5)
Over MCP, tier 0 is capped at contribute: it has no folder tools and cannot approve or start a batch. A Broker Ask waits 150 s; the in-app Lead asks tool by tool and waits 600 s. Delegated work stops at gates it cannot pass, or at asks nobody answers.

**To-be rule.** Authority is granted once, before the run:
- a permission envelope sized from the process's manifest;
- the person's reserved decisions are named in advance, as decisions, not as per-call asks.
Nothing inside the envelope asks again.

### T3. Work is counted, not judged (8)
- A completed model call counts as a stage done.
- Read completion follows the part counts.
- Claim review is off by default; an incomplete review stages the claim as unchecked.
- A broken disqualifier went uncaught.
- Acceptance is a person reading a summary.
- Whether a repair worked is judged by the agent that made it.

The audited session's checks exist, but only there.

**To-be rule.** An Oracle, separate from every worker, judges each process's output against its specification before the parent moves on. Tier A (deterministic) checks run first; its verdict is a claim with evidence; a missing check is a failure, not a skip.

### T4. Failures have no ticket and no repair loop (6)
A failure is a refusal code inside a call's result. Nobody owns it and nothing records it:
- folder descriptions failed in all 12 audited attempts, unnoticed;
- a quarantined capture waits for someone to notice;
- every repair on 19–20 November was tier 0 by hand;
- R1's repair re-applied every group in the library, because nothing checks a repair's reach first.

**To-be rule.** Every failure opens a ticket at its mapped extension. A Doctor repairs it with a catalogued remedy, after a blast-radius check, and hands back to the Oracle. A failure no remedy covers goes to tier 0 with its diagnosis attached.

### T5. Decisions wait with no owner (4)
- A finished batch leaves its Source and lens decisions unassigned; W7 counts them but does not route them.
- Enriched and partial items wait with no deadline.
- Folder purposes are decided with no draft, because drafting is off by default.
- Titles stay as file names.

**To-be rule.** Every decision a process leaves has a named owner, a draft to decide from and a place on the agenda. One consolidated decision set goes to the Owner, never one item at a time.

### T6. Results do not reach the person (4)
- The Web UI drops a workflow's result (`app.js:8472`).
- `deep-read-staged` leaves no trace on the items it read.
- A stale-revision reload wipes the person's edits.
- An unfindable note needs a manual re-index.

**To-be rule.** A run's result is a record the person can open: what was done, what failed and why, and what is left. It is written by the Core, not held in the UI.

### T7. One decision reaches too far (2)
One folder's acceptance re-applies every accepted group in the library, and a stale root anywhere blocks it.

**To-be rule.** A decision's reach is its own scope. A change rebuilds only what depends on it, and the Core checks that reach before running it (Geo-Grapher's part is in the Geo-Grapher pack).

### T8. Links between records are derived or missing (6)
- A graph paper is linked to its Source note by title.
- A read but unaccepted paper cannot be quoted.
- Publication waits on folder review, so a URL source is never published.
- An Applications/ note pins nothing it used.
- A provisional paper projection outlives a failed reading.

**To-be rule.** Every cross-record link is stored at the moment both ends exist, with the identity of each end, and is checked when it is used.

### T9. The research session does not fit a brief (4)
- The candidate pool is the whole library: 82 of its own notes had to be decided.
- Budgets halve on every return to a phase: the run needed four extensions.
- One synthesis serves every question.
- Code placement is unchecked prose.

**To-be rule.** A brief over a corpus is scoped to that corpus, and has a synthesis per question. Its budget comes from the manifest and the envelope, not per phase visit. A code placement is a claim like any other.

### T10. Integrity and naming (8)
- A TypeError where a refusal belongs.
- The Web UI's Add source bypasses the Broker.
- "Approved" and "accepted" mean different things for folder cards.
- 96 notes record the wrong attester.
- Accept-as-captured lets an unread source in.
- `doctor` already names the install check.
- There is no semantic metadata step, and leftover paper databases are never cleaned.

**To-be rule.**
- Every error is a named refusal.
- Every surface passes the same gates.
- A state or a name means one thing.
- Records say who did what.

## What this means for the to-be pack

The ten rules are the to-be pack's design constraints. Each to-be use case lists the weaknesses it handles (`handles:`). The as-is index then shows, theme by theme, how many are handled. The to-be is finished when every weakness is handled, or marked deferred with a reason.
