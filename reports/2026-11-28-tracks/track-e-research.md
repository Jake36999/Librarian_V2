# Track E: research fitted to a brief (M7)

**Why:** research sessions are where the library is used for the Owner's own work. The plan's M7 fixes how a brief is researched:
- candidates come from the corpus only;
- one budget per brief, from the manifest;
- one synthesis per question;
- code placements are verified claims;
- a redraft limit per claim.

**Repository:** Librarian.
**Depends on:**
- B3, so unreviewed papers can be cited;
- the oracle (M4, done), for review apart from the work.

**Read:** the implementation plan's M7. The spec audit's M7 rows (`reports/2026-11-27-spec-vs-pack/README.md` §1.3) list where the Research Pipeline requirements are more precise than the pack:
- Addendum R11 (an explicit "extend budget" offer);
- R13 (per-brief verdicts: covered, partial or gap);
- R15 (search fields, reject before open).

## Sprint E1: the inventory and the Owner's decision D6

- Map M7's items to `session.py`, `closure.py`, `graph_evidence.py` and `tools/sessions.py`, as the spec audit began.
- Take the Owner's decision D6 before building: today claim review is opt-in, falls back to the Clerk, and stages held-claim offerings. Should it be always on, with no fallback?

**Done when:** the map is written and D6 is decided.

## Sprint E2: candidates and budget

- Candidates come from the corpus only (W-RES-01).
- Read but unaccepted papers are candidates and can be quoted (W-RES-05, W-CIT-02). The spec audit marks this as diverging from 30 September §4.1, so the Owner confirms it first.
- The budget comes from the manifest, not from each phase visit (W-RES-02).

**Done when:** a five-question brief needs no budget extension, and decides no candidate from outside the corpus.

## Sprint E3: synthesis, placements and redrafts

- One synthesis per question (W-RES-03).
- A quote taken from a paper's card alone is caught (W-RES-06).
- A code placement is a claim citing a code entity (W-RES-04).
- A redraft limit per claim, then a stated gap.
- Comparing projects uses federated search over accepted bridges, which needs G6.

**Done when:** each report has its own synthesis, and every code placement is verified or stated as a gap. The measured run needs the Owner's approval of its spend.
