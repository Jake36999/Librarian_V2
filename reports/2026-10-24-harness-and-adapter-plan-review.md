# Librarian V2 review: system state, AuditedEngagement plan, and adapter-layer completion

**Review date:** 2026-10-24
**Scope:** the working tree at `df71ada` plus uncommitted changes; the
[AuditedEngagement specification](../docs/audited-engagement-harness.md); the
[system attention review](2026-10-23-system-attention-deployment-and-runtime-review.md);
the [model invocation architecture](../docs/model-invocation-architecture.md),
[adapter requirements](../docs/model-adapter-requirements.md), and
[adapter cohort record](../docs/model-adapter-cohort-2026-10-23.md); the local
research corpus (`E:\Librarian research`, 15 PDFs) and the relevant
Resource-Library paper notes (20 notes).

This review changes no product behaviour. It records findings, reproductions, and
a recommended order of work.

## 1. Bottom line

1. **The system's direction is sound, but none of the six P0 items from the
   2026-10-23 review has closed.** The Host graceful-stop test still fails
   (reproduced today). The SQLite single-owner rule is partly enforced: 17 call
   sites route through IndexService and 43 direct `engine_for` calls remain in
   tool paths. Route binding, per-role readiness, the unknown-tool-support
   coercion, and the lead-selection tier wipe are unchanged. STT has landed.
2. **The AuditedEngagement plan is careful and faithful to its source paper**,
   and its research citations are mostly accurate (section 4). Its main risk is
   architectural. It specifies a new event store, state machine, and reducer
   beside `session.py`, which already is an append-only, hash-chained,
   phase-gated, budgeted harness whose state is a fold over events. Building
   AuditedEngagement as a session purpose would remove most of Phases A–B.
3. **The plan's authoritative-closure path covers only a narrow part of what
   Librarian actually does.** By the spec's own rules, research synthesis is
   `partial` or `human_judgment`. The first shippable slice should be the
   spec's own "externalized state only" variant, plus Tier A integrity over
   staging writes.
4. **The adapter layer is a good observability seam and a fail-closed
   compatibility check. It does not adapt anything yet.** Every request is
   still rendered by `providers.py`. No request differs by model, so the stated
   goal (give each model input in the form it expects) is not started. The
   foundation is the right one to build on.
5. **I found seven concrete defects in the adapter foundation** (section 5.2).
   The most consequential: any edit to the expectation pack changes every
   record's fingerprint, which is a hard qualification dependency. Adding one
   draft record therefore invalidates every route's qualification evidence at
   once. `reasoning_content` and `usage` are discarded on every
   OpenAI-compatible response, yet DeepSeek's thinking mode documents that
   `reasoning_content` must be passed back after a tool call.
6. **Four sequencing documents disagree.** The release queue says the V2
   implementation is complete. The attention review lists release-blocking P0s.
   The harness has Phases A–F and the invocation architecture has Phases A–E.
   Section 7 proposes one merged order.

## 2. Method and evidence

- Read the four specification documents in full, plus `model_invocation.py`,
  `providers.py` (rendering), the uncommitted `loop.py` and `app.py` changes,
  and the relevant parts of `session.py`, `agent_runtime.py`, `tools/library.py`,
  `hosts.py`, and `clerk.py`.
- Ran the adapter, service, STT, embedding, TTS, vectors-slot, Clerk,
  qualification-job, and Host-lifecycle suites with `PYTHONPATH=src`:
  **66 passed, 1 failed** (`test_host_lifecycle.py::test_host_managed_core_starts_and_stops_cleanly`).
  The full suite was not run.
- Reproduced the pack-fingerprint and pack-validation defects with a short
  script against the shipped `core.json` (section 5.2).
- **Second reader.** A DeepInfra-hosted model (`XiaomiMiMo/MiMo-V2.6-Pro`, with
  `zai-org/GLM-5.3` for the cross-document consistency pass) read every PDF in
  the research corpus and the 20 Resource-Library notes. It checked each
  against the spec's sections 3 and 23. That came to 17 calls, about 459k
  prompt and 88k completion tokens, roughly USD 0.29 at catalogue prices. I
  checked four of its quotes against the PDFs (ReflectiChain p. 2 and pp. 7/15;
  KDRAR p. 22); all four matched, with the same page numbers. Its other page
  references were not checked individually.
- **Long-horizon paper.** I first read pp. 3–5 from the page images in
  `tmp/pdfs/`. The full PDF was later found at
  `C:\Users\jakem\Downloads\Long horizon harness paper.pdf` and checked by the
  second reader. The spec's claims on cost inversion (Table 4), token shares
  (Fig. 5), negative transfer (Tables 9 and 11), and stale evidence after user
  input (§B.2.2) are accurate. Two caveats:
  - The paper ran Manager, Executor, and Auditor on the **same backbone** (§3.1,
    p. 6) and reports no mixed pairings.
  - The "3.6×" figure is OSWorld **output** tokens only (p. 10).

  Details are in the companion [transcript review](2026-10-24-chatgpt-transcript-review.md).

## 3. System state against the 2026-10-23 attention review

| Item (10-23 priority) | Status today | Evidence |
| --- | --- | --- |
| Host graceful stop (P0) | **Still failing** | Real-child lifecycle test fails at `stopped["stopped"] is True` (`tests/test_host_lifecycle.py:95`). |
| Core-only SQLite ownership (P0) | **Partial** | `with_engine` and `with_index` run on `IndexService` when the Core installs one (`tools/library.py:83-104`): 17 call sites. `engine_for(ctx)` still builds a direct `Index` (`tools/library.py:22-46`), and 43 tool call sites use it. No static guard exists yet. |
| Existing-doc adoption (P0) | **Not started** | No adopt plan or apply flow, no `DocumentRoot`, no `workspace_document`. |
| Profiles choose routes (P0) | **Unchanged** | `route_policy` is still an allow-list (`agent_runtime.py:221-316`). Release-lead selection calls `set_tiers([lead])` (`app.py:853`), which replaces the whole tier list and drops Scribe and Clerk (`app.py:2306`). |
| Readiness per role (P0) | **Unchanged** | `route_readiness` applies one `qualification_role` to every tier (`app.py:609-680`). |
| Migrated preset host identity (P0) | **Papered over** | `model_invocation.py` adds two alias maps (`_host_matches`, `legacy_structured_output_policy`) instead of converging on one canonical host ID. Each new consumer must remember the alias. |
| Unknown `tool_calling` shown as false (P1) | **Unchanged** | `app.py:2245` `bool(profile.get("tool_calling"))`. |
| STT service slot (P1) | **Done** | Slot 7, `stt.py`, `deepinfra_inference_stt_v1`, with tests. |
| Durable runtime evidence (P1) | **Partial** | A redacted in-memory trace (200 records) exists; nothing is persisted, and usage and request ID are reported as `unavailable`. |
| Work budget vs native reasoning (P1) | **Correct in code** | No native control is sent (`behavior_mode` is always `provider_default`). I did not check the UI copy. |

**Planning conflict.** [`release-implementation-queue.md`](../docs/release-implementation-queue.md)
states "the V2 implementation and its deterministic validation are complete"
and plans R0–R5 from that premise. It does not mention the attention review's
release-blocking P0s, the harness, or the adapter phases. That premise is not
true while the Host stop test fails.

## 4. AuditedEngagement plan

### 4.1 What the plan gets right

- **Faithful to the Manage–Execute–Audit design, with two safer changes.** pp. 3–5
  of the source paper match the spec: Manager without environment access,
  fresh-context budget-bounded Executor, read-only Auditor that never sees the
  Executor's trajectory, termination only on `complete AND clean`. The spec's
  changes are both stricter. A deterministic reducer replaces the paper's
  Manager-applied state update, and a deterministic Tier A audit runs before
  the paper's LLM audit.
- **The Auditable Closure Gate is well supported.** ReflectiChain states its own
  scope condition: "If constraints can be verified by a rule engine, SED is not
  the primary risk" (p. 2). It also loses to ReAct in unfamiliar domains (CCR
  40% vs 95%, Table 9 p. 18), and costs 68% more tokens than ReAct (p. 15).
  Both findings support keeping the mode opt-in and gated.
- **Research hygiene is good.** The numbers checked out: KDRAR's top five (p. 22),
  STAGE's 512-token budget (p. 13), and the dual-graph paper's Table 4 vs.
  14.6-point prose discrepancy (Table 4 deltas are 1.53 and 2.82 points,
  p. 23). The "Important limit" column is accurate and, in several rows,
  understated (section 4.4).
- **Integrity and correctness are kept apart**, Tier B is never treated as
  certification, and the plan refuses to copy paper thresholds.
- **Release gates are tied to the existing P0 list** rather than being
  re-invented.

### 4.2 Issues, ranked

**1. It builds a second harness beside the existing one.**
`session.py` already provides most of what spec sections 7, 8, 13, and 19
propose to build new:

| Spec proposes | Already in the codebase |
| --- | --- |
| Durable event store, replay, state reducer (§7, §8, §13.1) | `session.py`: an append-only JSONL event log whose state is a fold over its events. Resume is replay. `chain_hash`/`verify_chain` make the log hash-chained. |
| Phase-gated execution and budgets (§8, §9.2) | Per-purpose phases with exit conditions; writes gated by phase (`PHASE_GATE`); per-phase call budgets (`BUDGET_SPENT`); `before_call`/`after_call` hooks. |
| Checkpoints as durable decisions (§17.2) | Questions are events; an unanswered question blocks `advance`. |
| Tier A deterministic verifiers (§12.1) | `claim_run.py` (runs a claim's failing input, with fixed runner text), `provenance.py` (checks note arithmetic against survey evidence), `quality.py` (per-source capture verdicts), the L0 contract check. |
| Partial-closure carrier (§5.2) | `staging.py`: the airlock between machine output and the vault. |
| Typed composite actions (§11.1 macros) | `workflows.py` (declarative actions, workflows, pipelines) and `agent_runtime.MACROS`. |

Section 19's module map does not mention `session.py` or `claim_run.py`. It
also assigns typed dependency edges and invalidation events to `provenance.py`,
which is an arithmetic checker, not a provenance graph.

*Recommendation.* Implement AuditedEngagement as a session purpose whose phases
are `manage → preflight → execute → audit → reduce`. Make engagement records
typed session events. Register the existing checkers as Tier A verifiers behind
one small `Verifier` interface. Replay, budgets, phase gating, and question
checkpoints come with it. The genuinely new pieces are then the contract
compiler, the protected-target snapshot and diff, and the reducer's transition
table.

**2. Manager, Executor, and Auditor are not mapped onto the existing roles.**
The spec adds three roles. The route-binding model has Lead, Scribe, Clerk, and
Research Helper, and the release gate requires canonical role routing for all
of them. Leaving the mapping open widens the gate.

*Recommendation.*

- Manager is the Lead binding, run with an inference-only `TaskContract`
  (`interaction=single_turn`, no tools).
- Executor is the Lead binding for tool contracts, or the Scribe binding for
  drafting contracts.
- The Tier B Auditor is the Clerk binding. Clerk already has `consult`
  authority and a read bundle.
- Same-route audit is then mechanical to detect: the Clerk binding equals the
  Executor binding.

This reuses `RolePolicy` and per-role qualification instead of adding three
roles.

**3. Nothing keeps the Manager's input bounded across rounds.** In the paper the
Manager re-reads every report V₁…Vᵢ (Fig. 2, "External State Memory – O(rounds)
growth"). The spec says "compact persisted state" and "redacted audit
summaries" but gives no rule for producing them.

*Recommendation.* Define a deterministic Manager projection:

- active constraints;
- open, partial, stale, and blocked requirements;
- the latest AuditReport per open requirement;
- the last N engagement events;
- counts of everything else;
- older reports by reference only;
- a hard token budget, with tests at 50+ rounds.

**4. The Manager cannot see what is feasible.** Section 9.1 gives the Manager
requirement summaries, the epoch, audit outcomes, route availability, budget,
and checkpoints, but no catalogue of eligible tool bundles, verifiers, or write
roots. The compiler will therefore reject infeasible proposals one round at a
time. The Thought Management System paper gates node creation on available
capabilities (Algorithm 2, p. 6).

*Recommendation.* Give the Manager a compact capability manifest: eligible
bundle IDs per target class, the available verifiers, and the approved write
roots.

**5. No table says which verifier can produce which closure class.** The schema
allows contradictory combinations such as `closure_class=authoritative`,
`verifier=llm_assessment`, `verification_strength=advisory`. The combinatorial
optimisation survey is explicit: LLM judges complement solver signals but are
not verifiers (p. 7).

*Recommendation.* Add a validity table to the Closure Gate:

- `authoritative` requires a `deterministic`, `test_or_solver`, or
  `evidence_check` verifier with `exact` or `bounded` strength.
- `llm_assessment` alone caps a requirement at `partial`.

**6. The first slice targets the narrowest workload.** Spec section 5.2 already
says a staged research summary is normally `partial` or `human_judgment`, and
that is most of Librarian's work. The authoritative path pays off first for
mechanical work: vault/index operations, citation existence, `claim_run`
results, and schema-validated records.

*Recommendation.* Ship the "externalized state only" variant (§21.3) first, for
research rounds with partial closure, with Tier A integrity over staging
writes. Start authoritative closure with mechanical operations. Set a kill
criterion in advance. If "state + Tier A/B" does not beat "externalized state
only" by a preset margin on Librarian's own fixtures, do not ship Tier B as a
default. The papers show these loops can raise cost without raising results:
ReflectiChain +68% tokens; Thought Management System, higher AI cost (Tables
6–7); CoT below standard prompting on two backbones (Table 1).

**7. The action-tool cap needs a floor as well as a ceiling.** Current phase
bundles already offer about 4–6 action tools plus controls (`frame`, `map`,
`search`, and `judge` hold 8 tools each, including `advance`/`ask_user`), so
the cap of five mostly describes current practice. KDRAR shows "a significant
drop when the candidate list contains only three APIs" (p. 22). Its training
also never sees a missing correct item (p. 9), so a filtered-out tool produces
confident wrong action rather than a refusal.

*Recommendation.* Record the post-filter candidate count. Add a "no suitable
tool" terminal report. Track the bundle-expansion rate.

**8. Constraints in the prompt are not enough.** In the semantic-drift paper,
restating rules in the prompt raises constraint fidelity only to 58.2% RCS
(p. 4). Removing either the forward feasibility check or the retrospective
audit loses most of the effect (Table III). The spec already re-anchors on
state (preflight, then Tier A), which is the right answer. Tier B's rubric
should name the drift signatures the papers observed: exception injection,
temporal relaxation, scope narrowing, priority inversion (ReflectiChain
pp. 16–17).

**9. Per-call authorization should be named explicitly.** The spec's
effective-authority intersection (§6.2) includes contract read and write
targets, so it already goes beyond "which tools exist". Mellafe Zuvic (2026)
shows that frameworks default to capability gating without argument-value
authorization. That is the confused-deputy gap.

*Recommendation.*

- State that the broker checks each call's argument values: target path
  within `write_targets`, operation class, size, and idempotency key.
- Add Muruaga's composition closure: individually permitted calls must not
  combine into a prohibited outcome within one contract.

**10. Checkpoints should let the person initiate, not only approve.**
Homo agenticus reports that who initiates a decision matters more to felt
agency than who executes it (pp. 4–5). It also reports that people feel agency
over controls that do nothing (p. 3). Every checkpoint control must therefore
have a real causal effect. Offer "propose a constraint" and "request evidence"
before "approve", and test that every control changes state.

**11. The spec is far ahead of its prerequisites.** It runs to 1,468 lines, nine
record types, and a 14-state machine, while every prerequisite gate is still
red.

*Recommendation.* Freeze the scope of Phases A–B. Treat sections 13 (selective
invalidation engine), 15 (trust-zone propagation), and 16 (structural graph)
as design notes until the Phase B exit is met. The cross-document consistency
findings are in section 6.

### 4.3 An existing trust-zone gap in prompt assembly

`Loop.system_prompt()` (`loop.py:492-545`) puts vault-derived text into the
system message, the highest-priority channel: note titles on the desk, adopted
lenses (stances drawn from source passages), and `counter_quote` text from
cited notes. Wallace et al. (2024) show models trained to rank
system > user > third-party content. Greshake et al. (2023) show that text
planted in retrieved content acts as instructions.

The lens text has passed through staging review, but a counter-quote or a
Source note title has not. Before trust zones are enforced at the broker
(Phase D), render vault-derived text in a lower-priority, delimited position
instead: a tool result, or a quoted block in the user turn. This is also an
adapter concern (section 5.3).

### 4.4 Citation check

| Spec source | Verdict | Note |
| --- | --- | --- |
| Long-horizon harness (full PDF) | Accurate | Loop, roles, termination rule, cost inversion (Table 4: Qwen 10.7M→34.3M, Opus 16.5M→11.1M tokens per task), and negative transfer (Tables 9 and 11) all match. All roles share one backbone in the paper, so the spec's independent-auditor route is untested there. |
| ReflectiChain (expanded, *Electronics* 2026) | Accurate; limits understated | Its world model *is* learned and is the second-most-valuable component, so "do not substitute a learned world model" is Librarian's choice, not a finding. Its tables disagree with each other (Table 7 vs Table 4), so do not quote its numbers. |
| Semantic-execution drift (short paper) | Mostly accurate | It has no cognitive-load measurement; that observation comes from the expanded paper. Its "world model" is analytic and hand-specified, not learned. |
| STAGE | Accurate | 512-token global budget (p. 13). Random token retention (80.32) beat head truncation (79.66) (Table 4), which cautions against a naive fixed-priority truncation in the capsule assembler. |
| KDRAR | Accurate; "compatibility" mildly overstated | Its compatibility matrix is co-usage frequency, by the authors' own account (p. 20). |
| Dual-graph (LLM-S2KG) | Accurate | Table 4 vs prose discrepancy confirmed (p. 23). |
| Combinatorial optimisation survey | Accurate; limit understated | Even with a solver, an omitted constraint passes executability checks (p. 7). |
| Thought Management System | Accurate | Its validator is an LLM with a soft score, not a deterministic gate; its thesis argues against human checkpoints. |
| AgentAI survey | Direction accurate, mechanism overstated | It supports graceful shutdown in general (p. 7), not "durable operation boundaries". |
| Agentic-AI surveys (taxonomy, age of reasoning, cybersecurity) | Direction accurate | Broker-placed trust zones are Librarian's design. The cybersecurity paper supports separating trusted from untrusted zones (p. 8). |
| Homo agenticus | Mostly accurate | "Interrogation" refers to radiologists' professional practice (p. 9). The paper reports no study of its own. |
| Pedagogy-first | Overstated for "interrogation cards" | Supports machine-in-the-loop control (P5, p. 3). Nothing card-shaped. |
| Industrial agentic AI | Analogy accurate | No thresholds or validated quantities at all. |

The pattern is consistent. Numeric claims are accurate. Several mechanisms
(durable-boundary interruption, broker-enforced zones, interrogation cards) are
Librarian design choices that the cited surveys only point towards. Section 3
of the spec should label them "Librarian design", as section 23 already does
for trust zones.

## 5. Adapter layer: state and completion plan

### 5.1 What exists

`model_invocation.py` provides:

- immutable `TaskContract`, `InvocationScope`, `ExactRoute`, and
  `InvocationPlan`;
- a tri-state `ModelExpectation` with a read-only registry;
- three trusted descriptors (`legacy_openai_chat`, `legacy_anthropic_messages`,
  `legacy_provider_chat`);
- a `LegacyProviderAdapter` that calls `Provider.chat` unchanged;
- an `InvocationRuntime` with a bounded, redacted in-memory trace;
- walk-level binding pinning in `Loop.send` (`loop.py:805`).

It fails closed on behaviour modes that have not been reviewed and on
capabilities marked explicitly false. Unknown is not treated as false.
`service_adapters.py` gives OCR, TTS, STT, and embeddings their own typed
contracts. Embedding representation hashes stop vector spaces mixing. The
adapter contract now feeds the hard qualification fingerprint.

Against the architecture's own phases:

| Phase | State |
| --- | --- |
| A – data and observability | Types and in-memory trace done. Persistence, usage, request ID, and queue timing not done. |
| B – canonical role bindings | Not started. This is also an attention-review P0. |
| C – adapter ABI and packs | Descriptors and a 13-record pack done. `render`, `parse`, `normalise_usage`, and `conformance_cases` are not implemented. The registry holds descriptors only; the runtime always creates `LegacyProviderAdapter`. |
| D – native behaviour | Correctly gated; nothing is sent. |
| E – collaboration and services | Service adapters done early. Collaboration plans not started. |

### 5.2 Defects found

**Update (2026-10-24, later the same day).** Defects 1, 2, 3, and 5 are fixed
in the working tree, with L0 tests in `tests/test_model_invocation.py`:

- per-record content hashing;
- strict pack fields and a recursive forbidden-key scan;
- `ExpectationRegistry.status()`, surfaced in `doctor`, `route_readiness`, the
  tile summary, and plan warnings;
- `providers.synthetic_call_id()`.

The full suite gives 891 passed, 1 skipped, and 1 failed. The failure is the
Host-stop test, which was already failing. Defects 4, 6, and 7 remain open.

1. **Pack-wide fingerprint invalidates all qualification evidence.**
   `ModelExpectation.fingerprint` hashes `pack_fingerprint`, which is a digest
   of the whole pack (`model_invocation.py:290-299`, `365`). App puts that
   fingerprint into `response_contract.adapter_contract`
   (`app.py:969-996`), which is part of the hard `compatibility` fingerprint
   (`hosts.py:612-618`).
   *Reproduced.* Appending an unrelated draft record changes MiMo V2.6 Flash's
   fingerprint from `6aac31…` to `106ea85c…`. Every route's L1 evidence would
   become stale on any pack edit.
   *Fix.* Hash each record's own content. Keep the pack ID and version as
   provenance, outside the record hash. This matches the architecture's
   `records/<sha256>` design.
2. **Pack validation is lenient.** The forbidden-key check covers top-level
   keys only. A nested `prompt_contract.template` is accepted, and unknown
   fields are ignored silently (reproduced). The requirements say packs "cannot
   contain" templates, and the harness requires "unknown field rejection".
   *Fix.* Use a strict JSON Schema with `additionalProperties: false` and a
   recursive forbidden-key scan.
3. **A malformed shipped pack fails silently.** On a parse error,
   `ExpectationRegistry.bundled()` returns an empty registry
   (`model_invocation.py:387-398`). Every route then reads as `unknown` and
   nothing reports why.
   *Fix.* Keep the conservative fallback, and surface the load error in
   `doctor` and `route_readiness`.
4. **Reasoning and usage are discarded.**
   - `OpenAICompatible.chat` keeps only `content`, `tool_calls`, `model`, and
     `finish_reason` (`providers.py:333-362`).
   - The response's `usage` object is dropped, even though the trace reports
     usage as "unavailable".
   - `reasoning_content` is dropped, and `Reply.message()` never replays it.
     For DeepSeek thinking mode with tools, the provider documents that it
     must be replayed (section 5.3).
   - A reasoning model that spends its `max_tokens` on reasoning returns an
     empty reply with `finish_reason=length`. That is indistinguishable from a
     model that chose to say nothing.
5. **Synthetic tool-call IDs repeat.** When a server omits call IDs, the
   provider assigns `call_{i}` (`providers.py:356`), so every turn reuses
   `call_0`. The conversation history then holds duplicate IDs.
   *Fix.* Generate IDs that are unique within the walk.
6. **Several model calls bypass the plan.**
   - Clerk has its own `/chat/completions` client with its own
     `response_format` retry (`clerk.py:1211-1282`).
   - OCR and the PDF-cleanup helper use their own transports.
   - `Loop` keeps a `runtime is None` path.

   The architecture's acceptance criterion "every provider request originates
   from a valid immutable InvocationPlan" is not yet true.
7. **Observed-model mismatch is recorded, not evaluated.** `InvocationResult`
   stores `observed_model`, but there is no per-call identity verdict (the
   architecture's `conformance.model_identity`). Only the L1 probe compares
   requested and returned model.

### 5.3 The gap against the goal

The stated goal is to give each model its prompt and information in the form
it expects, or at least one it is familiar with from training. Nothing yet does
this.

For hosted OpenAI-compatible routes, which are most of the cohort, the server
applies the token-level chat template. The levers the client actually controls
are therefore message-level. Each can be expressed as a small enum in the
expectation record and interpreted by first-party adapter code. That keeps the
"no templates or prompts in packs" rule intact.

| Lever (proposed field) | Why it matters | Today |
| --- | --- | --- |
| `reasoning_field` / `reasoning_replay`: `drop`, `after_tool_calls`, `always` | Reasoning models in tool loops have model-specific replay rules. DeepSeek's [thinking-mode guide](https://api-docs.deepseek.com/guides/thinking_mode/) says that once a tool call has happened, `reasoning_content` must be passed back on every later request. Without tool calls it is ignored. Community reports show HTTP 400 "reasoning_content … must be passed back" when clients drop it. MiniMax asks for thinking content to be kept in history, including tool-call turns ([NVIDIA model card](https://docs.api.nvidia.com/nim/reference/minimaxai-minimax-m2), [MiniMax blog](https://huggingface.co/blog/MiniMax-AI/aligning-to-what)). I could not confirm Kimi K2 Thinking's rule from its docs. | Always dropped. This is a live risk for the DeepSeek V4.x records. The passing 10-23 walks suggest DeepInfra's default for that route does not enable thinking, or tolerates omission. That is exactly the fact an expectation record should pin, with a probe. |
| `reasoning_counts_toward_max_tokens`, `output_headroom` | Reasoning tokens can use up the output budget, giving an empty reply. Resource-Library's DeepInfra adapter already notes reasoning-tagged models need "real headroom". | Not modelled. The Loop sends the profile output budget (default 4096). |
| `content_tool_call_dialect`: `none`, `hermes_xml`, `json_block` | When an endpoint's tool parser fails, open-weight models emit tool calls as text. The Loop then treats that as a final answer. Detect it and return a typed failure first; parse it only after fixtures and review. | Read as a final answer. |
| `tool_schema_dialect` | Endpoints accept different JSON Schema subsets. Normalise schemas, or reject before spending. | Sent raw. |
| `tool_call_id_format`, `tool_result_shape` | Some templates constrain ID formats or render tool results by name. | Fixed shape; `name` dropped from tool messages. |
| `system_role`: `native`, `fold_into_first_user` | Not every template has a system role. | Always a system message. |
| `sampling_profile` per behaviour mode (cited ranges) | Model cards publish recommended sampling. Hosted servers may or may not apply it by default. | Provider default. Temperature is not sent in walks. |
| `context_layout`: `document_framing` (`xml_tags`, `markdown`), `query_position` | Vendors' prompting guides differ on document framing and on whether instructions go first or last in long contexts. These are first-party prompt-assembler options selected by enum, never pack text. | One layout for every model. |
| `cache_strategy`: `stable_prefix`, `anthropic_cache_control` | The system prompt is rebuilt every step with volatile state (budget hints, refusal notes, review corrections; `loop.py:492-545`). Any change breaks the shared prefix and so defeats prompt caching. The 10-23 validation runs were prompt-heavy (71,773 prompt vs 2,020 completion tokens). Order prompt parts from stable to volatile, and move per-step state into a trailing message. | Volatile state sits at the top of the prompt. |
| Trust-zone placement | Untrusted text belongs in the lowest-priority, delimited channel for each model (section 4.3). | Vault-derived text goes into the system prompt. |

Two further gaps in the plan:

- **The L1 probe tests one tool call only.** Most format failures appear on the
  *continuation*: tool-call ID mismatch, rejected reasoning replay, role
  ordering. L1 should be a two-step probe: tool call, then tool result, then
  final answer.
- **No authoring path for expectation records.** Librarian's own staging
  airlock fits this. A model card is a source, a model drafts the record, the
  draft waits in staging, and a person's accept turns it into a reviewed
  record. This dogfoods the product and uses the same second-reader pattern
  used in this review.

### 5.4 Recommended completion order

Each step leaves today's request bodies unchanged unless it says otherwise.

1. **Fix defects 1, 2, 3, and 5.**
   *Exit:* L0 tests for per-record hash stability across unrelated pack edits,
   strict pack rejection (nested and unknown keys), visible load failure, and
   unique synthetic IDs.
2. **Make route evidence durable.** Carry `usage`, request ID, and
   `finish_reason` into `Reply` metadata. Append plan and result traces to the
   session log as `model_request`/`model_response` events.
   *Exit:* this meets the harness's "Route evidence" release gate for Loop
   walks.
3. **Consolidate chat transports.** Route Clerk's and OCR's chat calls through
   the runtime (OCR already has a typed request builder), and remove the
   `runtime is None` path.
   *Exit:* a static test that no module outside the adapter or transport layer
   builds a `/chat/completions` URL.
4. **Canonical role bindings.** This is shared with the attention-review P0.
   Expectation-to-qualification evidence is role-specific, so this must come
   before the cohort grows.
5. **Move rendering and parsing into the adapters.** `OpenAIChatAdapter` and
   `AnthropicMessagesAdapter` take `render(plan, payload)` and `parse(response)`;
   `Provider` keeps only transport and authentication.
   *Exit:* golden-body fixtures show byte-identical requests to today for
   every existing fixture.
6. **Dialect vocabulary v1:** reasoning replay and headroom, detection of tool
   calls in content (typed failure), schema dialect, and sampling profile. Add
   the two-step L1 probe. Apply this first to the two reviewed records and the
   two long-horizon draft records.
7. **Context-layout and cache-order options in prompt assembly.** Evaluate per
   route on Librarian's own fixtures before enabling any of them.
8. **Expectation authoring through staging.** Defer signing and the pack update
   channel until there is a distribution need. The pack currently ships inside
   the signed Core.

## 6. Cross-document consistency

A second reader (GLM-5.3) read the harness spec (AEH), the invocation
architecture (MIA), the adapter requirements (MAR), and the expectations
registry (MER) together. I checked the items marked ✓ against the text. The
rest are its findings, listed for the documents' owners to confirm.

**The documents say different things are implemented**

- ✓ MIA §8.3 says "the Core records ordered, append-only walk events". MAR says
  diagnostics are "not persisted yet". MAR is right.
- ✓ MIA §7.1 says "V2 initially supports" five adapter families, including
  Responses, Transformers, and vLLM/SGLang. MAR lists those same families as
  "deliberately not enabled yet".
- ✓ MER calls itself "the proposed evidence layer". MAR describes the shipped
  registry and pack.
- ✓ MIA §10.6 still says STT is "Not available yet". STT is now slot 7.
- MIA §10.1 says "all save, migration, and runtime paths use canonical role
  bindings" in the present tense. Its own Phase B, and the AEH §4 gate, treat
  this as future work.

**Vocabularies disagree**

- ✓ Model-behaviour states. MIA §10.4 uses Provider default / Declared /
  Adapter-tested / Qualified. MER uses Unsupported / Declared / Adapter-tested /
  Qualified, and a third enum, `adapter_mapping_status`.
- Work budget is defined three slightly different ways (MIA §10.4, MER,
  AEH §11.2).
- ✓ AEH §5.1 has four modes; the `mode` field in §7.1 allows two
  (`plan_only | audited`).
- AEH says "Helper" where MIA says `research_helper`.
- The route header has different required fields in MIA and MER.

**Terms used but never defined**

- `consult | contribute | curate` authority (MIA §5.2).
- The "screened" qualification level, against MER's L0–L3.
- "Session phase" inside the authority intersection.
- Policy effects for the `sensitive`, `adopted_workspace`, and `user_authored`
  zones (only `untrusted_external` has rules).
- `REQUIRE_HUMAN_CLOSURE`'s downstream state.
- Round vs. walk.
- Operation class, precondition, and acceptance-predicate formats.
- The checkpoint type list.

**Requirements that cannot be tested yet**

- The Closure Gate must verify acceptance predicates "without invoking a
  model", but no predicate language exists.
- Tier A "always runs after a mutation-capable contract", which leaves
  read-only rounds without a defined audit.
- The context assembler has six reservation tiers and the capsule has only
  four budget fields.
- Tier B must report "unsupported claims and contradictory evidence", but the
  AuditReport has no field for them.

**Missing pieces** (these match sections 4.2.2, 4.2.3, and 4.2.5 above)

- The role mapping.
- A Manager context assembler, since ContextCapsule covers only the Executor
  and Auditor.
- The verifier × strength × closure-class matrix.
- Three outcome enums with no mapping between them: ExecutionReport `outcome`,
  WalkResult `status`, InvocationResult `outcome`.
- Budget-reservation hold and release across rounds.

**Over-specified for a first delivery**

- RuntimeQualitySignal and PolicyCorrection schemas (§7.7–7.8).
- The structural-graph taxonomy and dedupe layers 4–5 (§16.2–16.3).
- The full metric catalogue (§18.2).
- Ranked tool selection with compatibility evidence (§10.2). A static,
  policy-filtered bundle is enough at first.
- CollaborationPlan's five modes (MIA §5.3).
- The sharded, compressed pack format for a 13-record pack (MIA §11).

*Recommendation.* Before Phase A code, do one editing pass:

- Mark each MIA and MER section as implemented, partial, or planned.
- Pick one vocabulary for behaviour states, work budget, and role names.
- Add the three missing tables: role mapping, closure validity, outcome mapping.

## 7. One merged order of work

*Amended by the [blind-spot verification](2026-10-24-architecture-blindspot-verification.md),
which adds four items to step 1 and later steps: MCP proxy-or-lease, cancelling
the turn at shutdown, read-fingerprint preconditions, and service transports
through the host limiter.*

1. **Release blockers (attention review P0).**
   - Host stop with phase telemetry.
   - IndexService-only SQLite, with a static guard.
   - Canonical role bindings and per-role readiness.
   - Tri-state capability display.
   - Lead selection that preserves the other tiers.
2. **Adapter steps 1–3** (section 5.4). These are small, independent of the
   above, and give route evidence that both the release (R2) and the harness
   need.
3. **Release queue R0–R5** on the corrected premise.
4. **Adoption planner and content roots.** Required before adopted folders feed
   any harness context.
5. **Adapter steps 5–7.** This is where model-familiar formatting begins.
6. **AuditedEngagement as a session purpose.** Plan-only, then "externalized
   state + Tier A" for research rounds with partial closure, then
   authoritative closure for mechanical operations. Tier B comes only after the
   comparative evaluation in spec §21.3 clears its preset margin.
7. **Trust-zone broker enforcement and invalidation (harness Phase D).** The
   prompt-placement fix in section 4.3 can land earlier, alongside step 5.

## 8. Research basis used in this review

Local PDFs (`E:\Librarian research`): the long-horizon harness paper (pp. 3–5
images); ReflectiChain (*Electronics* 15, 3452); LLM Planning against
Semantic-Execution Drift; STAGE (*Mathematics* 14, 1568); LLM-S2KG (*Applied
Sciences* 16, 4720); KDRAR; Advances in LLM-Assisted Combinatorial
Optimization; Thought Management System; AgentAI survey; Agentic AI: the age of
reasoning; AI Agents vs Agentic AI taxonomy; Transforming cybersecurity with
agentic AI; Industrial agentic AI; Homo agenticus; knowledge workers and an
embedded LLM agent; Pedagogy-first LLM integration.

Resource-Library notes (`D:\Resource-Library\06-Papers`): Mellafe Zuvic 2026
(capability gates are not authorization); Muruaga 2026 (bounded delegation);
Greshake 2023 (indirect prompt injection); Wallace 2024 (instruction
hierarchy); Wang 2026 (AgentSpec runtime enforcement); Yao 2022 (ReAct); Shinn
2023 (Reflexion); Parasuraman, Sheridan & Wickens 2000; Save 2014; BEA 2005
(flight data recorder passivity); Aalst 2003 (workflow patterns); and others
with no material bearing.

The second-reader reports are kept outside the repository. Re-run them, or ask
for them to be checked in under `reports/`, if they are needed as evidence.
