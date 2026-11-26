# What the checks prove, and what they do not

26 November 2026. Every to-be flow in these packs is `PROPOSED_UNACCEPTED`. None of it is implemented. Passing the pack checks, or hosted CI, is evidence about the **diagram model and the repository's existing code**, never that runtime behaviour has changed.

## The model checks (`render_pack.py`)

These run on the specs alone. They prove that the model is well formed and internally consistent:

| Check | What a pass means |
|---|---|
| Structure | One start; every node reachable; every non-end node has a way out; a decision's ways out all have guards; forks match joins |
| Scenarios | Every extension has a path; each is numbered by the step it leaves; exactly one path reaches success |
| References | Each reference calls a spec in its pack and handles exactly that spec's outcomes |
| Status | As-is specs are `IMPLEMENTED_*`, to-be specs `PROPOSED_*`, and no pack spec carries `superseded_by` |
| Actors | Every lane is an actor of `docs/terminology.md` |
| Size | At most 40 nodes per diagram, notes excluded |
| Boundaries | Every decision on a real quantity lists values below, at and above its limit, or is recorded as reviewed with no threshold |
| Weaknesses | Every as-is weakness sits at a real node, in exactly one root cause, and is either handled by a named to-be node or open with a reason |
| Tables | Every `spec:node` a table cites exists, in its pack or the counterpart |
| Syntax | No unquoted YAML boolean or comma that would silently change a guard |
| Freshness (`--check`) | Every view was generated from its spec as it is now |

**What they cannot prove.** That a flow is the right design. That the as-is specs match the running code beyond what their evidence cites. That a to-be flow, once built, would behave as drawn. Tier-0 turn counts and path counts are properties of the diagrams.

## Hosted CI

CI runs the repository's test suite on the commits it names. These packs change no code, so a pass shows only that the existing code still passes its tests. It is not evidence for any to-be behaviour. A pass also covers only the commit it ran on, not later edits in the working tree.

## What would need runtime work, or acceptance testing

| Claim in the to-be | Evidence needed before it counts |
|---|---|
| Tier 0 commissions once; at most 2 tier-0 turns per ingestion | A real commissioned ingestion, with turns counted from its run log |
| No permission prompt inside the envelope | The envelope implemented (W1b item 5), and a run whose broker log shows 0 asks for granted tools |
| The Oracle on a distinct route; verdicts re-checked | The Oracle implemented (P6–P7), and a run whose receipts show distinct routes and a passing recheck |
| Every failure opens a ticket, routed as the routing table says | The ticket service implemented, and injected failures of each class landing with their owners |
| A folder decision rebuilds only its group | The incremental application implemented in Geo-Grapher, with groups touched counted per accept |
| One active paper database; nothing left behind | The import changed, and the safety cases in `geo-grapher/to-be/incremental-safety` passing as tests |
| The replay invariant of the data contract | A rebuild of the Data records and the index from Bronze, diffed against the live records |
| The performance targets | Each row of the performance tables measured before and after, with its metric |
