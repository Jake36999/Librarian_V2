# High-impact memory, context and knowledge improvements, scoped (2026-11-05)

These build on what is already in place:
- MF-011: every request fits its route's window;
- MF-012: durable `ref:` references reopen exact evidence after a helper exits or the
  app restarts;
- MF-013, MF-014, MF-020: ingestion no longer silently reuses stale readings.

Each improvement below cites only literature findings that passed the check in
`LITERATURE-CHECK.md`. What the papers found holds for their benchmarks and models
only; it justifies a design and an experiment here, not a predicted result.
Speculation is kept in the **Hypothesis** lines.

## Ranking

| # | Improvement | Gap closed | Size | Release role |
|---|---|---|---|---|
| W1 | Session working state carried through compaction and restart | MC-02 (not met) | M–L | candidate: fixes a measured loss |
| W2 | Deterministic memory evaluation harness | MC-12 (not met) | M | gate for W5 and W6; outside release |
| W3 | Typed helper result envelope | MC-08 (not met) | M | in MF-021a, if MF-051 selects MF-021 |
| W4 | Effective-context budget and constraint placement | MC-01 refinement | S | small follow-up to MF-011 |
| W5 | Validity time and supersession for facts and notes | MC-05, MC-14 | L | MF-036; outside release |
| W6 | Applicability-scoped lessons | MC-04, MC-13 | L | MF-036/041; only after W2 |

Order: **W1 and W4 first** (both close or tighten a defect in code shipping now), then
**W2** (so W5 and W6 are decided on evidence), then W3 when MF-021 is in scope.

---

## W1. Session working state: what dropped context said, kept itemized

**The gap.** Measured in code:
- When a long thread outgrows the window, `Loop._fit_context` (MF-011) drops whole
  middle rounds. The model is told only *how many* were omitted (`loop.py:569-577`).
- After a restart, `Loop.restore` rebuilds only user and assistant text; tool results
  are not replayed (`loop.py:949-958`).
- So a correction the person gave in round 3 ("no, only peer-reviewed sources"), a
  decision, or the evidence a turn relied on can vanish from what the model sees.
  Audited-session constraints survive through the context header. Ordinary threads
  have no equivalent.

**What the literature supports.**
- LongMemEval separates memory values from retrieval keys, and finds that compressing
  original rounds into facts loses information. That argues against prose summaries
  as the carrier.
- ACE keeps context as itemized entries with ids and applies localized delta updates,
  instead of regenerating the whole context.
- Anthropic's context-engineering note describes compaction and structured note-taking
  as the standard tools.

**Design.**
- **The record:** a per-session `working_state` of itemized entries. Each has
  `{id, kind: constraint | correction | decision | open_question | evidence, text,
  origin: person | core | model, source_event, refs[], status: active | superseded,
  superseded_by}`.
- **What fills it:**
  - **Core, deterministically:** durable references minted (MF-012), notes read or
    written, and sources cited.
  - **The person's own words:** a user message a small clerk task classifies as a
    correction or constraint is stored **verbatim, with its quote verified against
    the message** (the existing `clerk.verify` pattern).
  - **The model:** it may propose entries. They are labelled `origin: model` and are
    never presented as the person's constraints.
- **How it changes:** only by localized deltas (add, supersede), never by a whole
  rewrite. A superseded entry stays, marked, for audit.
- **How it is used:**
  - `_fit_context` reserves a bounded slice for active entries inside the protected
    header whenever rounds are dropped.
  - The omission notice names the categories that were dropped and how to reopen
    them (their `ref:` ids).
  - `restore` replays the working state and the session's references, not just the
    text.

**Files:** `loop.py` (`_fit_context`, `restore`), `session.py` (events), a new
`working_state.py`, `clerk.py` (one grounded classification task); tests in
`tests/test_request_fit.py` and a new `tests/test_working_state.py`.

**Done when:**
- in a 200-round thread with corrections at rounds 3 and 50, both appear verbatim in
  the final request and after a restart;
- a superseded constraint is marked, never deleted;
- a model-proposed entry never reaches the person-constraints slot;
- the slice has a hard ceiling (MC-16), and an overflow says which entries were left
  out;
- the whole request still fits (MF-011's tests still pass).

**Not claimed.** Presence in the request is measured here. Whether the model *uses*
it is behavioural, so W2 measures it.

**Hypothesis:** keeping verbatim corrections reduces the person having to repeat
themselves in long research threads. W2 can test this offline with a scripted model
for presence, and with approved paid runs for use.

---

## W2. A deterministic memory evaluation harness

**The gap.** Measured: nothing in the repository measures whether memory helps or
harms later decisions (MC-12). The ten evolving-knowledge seeds
(`reports/2026-11-03-memory-context-review/data/evolving-knowledge-scenarios.json`)
are written, but not executable.

**What the literature supports.**
- **LifelongAgentBench:** the gain from prior experience depends on the model, and for
  strong models it is "small or even negative".
- **MemoryAgentBench:** four competencies to test separately, including selective
  forgetting.
- **MemoryArena:** every method decays as dependency depth grows.
- **MemDev-Bench:** historical guidance fails through compatibility mismatch and
  misapplied transfer.
- **MINJA:** memory can be poisoned through ordinary queries.

**Design.**
- **Arms:** memory absent, relevant, noisy, outdated and injected. Each runs against
  the same frozen library state.
- **Tasks:** the ten seeds, plus small fixtures for retrieval, update and selective
  forgetting, interdependent steps, and abstention.
- **Scoring:** deterministic where it can be:
  - required constraints present;
  - superseded facts used or refused;
  - abstention where evidence is missing;
  - references reopened rather than re-fetched.
- **Costs:** tokens, calls and wall time, as denominators.
- **Models:** a scripted model gives the offline tier. Paid behavioural runs go
  through the DeepInfra ledger only with the owner's approval, and are reported
  separately.

**Files:** `scripts/memory_eval.py`, `tests/eval/` fixtures, a results schema;
nothing in the runtime path.

**Done when:**
- the harness runs offline in CI time;
- each arm reports n, a rate and an interval;
- a deliberately harmful memory arm is detected as harmful;
- results are stored as evidence records, like the suite runs.

**Not claimed.** Fixture results say nothing about learning (MF-041's own condition).

---

## W3. A typed helper result envelope

**The gap.** Measured: a `delegate` helper returns its answer truncated to 4,000
characters, plus the tools it used, its stop reason and, since MF-012, the references
it made (`tools/delegate.py`). A caveat or conflict past the truncation is lost. A
missing prerequisite reads the same as an answer.

**What the literature supports.**
- **MAST:** multi-agent failures include coordination failures and acting on wrong
  assumptions (FM-2.2).
- **Anthropic's note:** condensed handoffs from sub-agents.

**Design.**
- **The envelope:** the helper ends with a structured result that Core validates.
  - `findings[]`, each with `evidence[]` (`ref:`, evidence ids, note names, URLs);
  - `caveats[]`, `conflicts[]`, `not_found[]`, `stopped` and `usage`.
- **Merging:** the parent merges the envelope, and keeps the prose as display. A
  finding with no evidence is marked unsupported, not dropped.

**Files:** `tools/delegate.py`, the helper brief and a schema check; tests in
`tests/test_effort.py` and a new `tests/test_worker_continuity.py` (MF-021's planned
file).

**Done when:**
- a late caveat beyond the prose bound is retained structurally;
- a missing prerequisite comes back as `not_found` with no answer;
- a malformed envelope is reported, not silently accepted.

This is MF-021a, so it is in the release only if MF-051 selects MF-021.

---

## W4. Effective-context budget and constraint placement

**The gap.** Measured:
- MF-011 budgets against a route's declared `context_tokens`, else the catalogue's
  `context_length`, else 131,072;
- the context header sits only at the start of the request.

**What the literature supports.**
- **RULER:** advertised and useful context differ.
- **Lost in the Middle:** using evidence is position-sensitive.

**Design.**
- A route can declare a qualified *effective* budget, recorded with its provenance;
  an unqualified catalogue length is used at a stated fraction.
- A short active-constraints reminder (ids and text, from W1) is repeated next to the
  current turn as well as in the header.

**Files:** `loop.py`, `agent_runtime.py` (route policy validation); tests in
`tests/test_request_fit.py`.

**Done when:**
- the effective budget and its source are recorded in `Turn.request`;
- both placements are present, and the request still fits.

**Hypothesis:** the fraction and the repetition help on this product's routes. W2
measures it; until then the fraction is a conservative setting, not a finding.

---

## W5. Validity time and supersession for facts and notes (MF-036 slice)

**The gap.** Measured: notes and evidence carry *recording* times (`captured_at`,
`fetched_at`) but no *validity* time. A corrected fact and the fact it replaces look
equally current to search.

**What the literature supports.**
- **Zep:** bi-temporal records, with raw episodes kept alongside derived semantics.
- **Memora:** distinguishes continued use of invalid memories from incomplete
  retrieval.
- **MemoryAgentBench:** selective forgetting.

**Design.**
- Fact-bearing notes gain `valid_from`, `valid_until` and `superseded_by` in
  frontmatter.
- Search labels a superseded note and ranks it below its successor, unless an "as of"
  date is given.
- A withdrawal suppresses retrieval but keeps the bytes (MC-14). This follows MF-012's
  reference withdrawal, extended to notes, vectors and summaries.

**Files:** `facts.py`, `search.py`, `index.py`, `staging.py`; the planned
`tests/test_knowledge_temporal.py` and `tests/test_memory_withdrawal.py`.

**Done when:** current and as-of answers differ correctly; a correction marks its
dependents for review; withdrawal survives restart and an index rebuild.

This is outside the release by design (MF-036).

---

## W6. Applicability-scoped lessons (only after W2)

**What the literature supports.**
- **ACE:** itemized playbooks with helpful/harmful counters.
- **ReasoningBank:** strategies *and* pitfalls, with noisy judge labels acknowledged.
- **Agent Workflow Memory:** induced reusable routines.
- **MemDev-Bench:** misapplied transfer and compatibility mismatch.
- **MINJA:** injection.

**Design.**
- A lesson is a staged proposal, accepted by a person like any note. It carries:
  - its scope, assumptions and the version it was learned on;
  - the episodes it came from (`ref:` ids);
  - helpful and harmful counts.
- A lesson whose assumptions don't match the current task is offered as tentative,
  never applied silently.
- Model-authored lessons stay quarantined until accepted.

**Done when:** W2 shows a measured benefit on held-out tasks against no-memory and
plain-retrieval arms at matched cost. Without that, keep it out.

---

## Deliberately not recommended

- **Adopting a graph database or GraphRAG as the core store.** GraphRAG's shown
  advantage is for global sensemaking, not exact lookup, and its pinned README says
  the project is "largely in maintenance mode".
- **Replacing original episodes with extracted facts or summaries.** LongMemEval finds
  this loses information. Keep originals and derive keys.
- **"More memory is better".** LifelongAgentBench shows small or negative gains for
  strong models. Treat memory as a treatment to measure.
- **Learned replay or retention policies before deterministic baselines.** LIMBO and
  TokenWorth show task-dependent value; TokenWorth claims results at one budget only.
- **Letting automatic memory evolution rewrite user requirements or accepted facts.**
  A-Mem evolves notes' descriptions. That this is unsafe for requirements is the
  review's design inference, and this plan keeps it.
