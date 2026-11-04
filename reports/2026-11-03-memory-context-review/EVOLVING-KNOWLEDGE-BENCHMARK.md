# Benchmark design: evolving project knowledge

**Draft, 3 November 2026. Not executed.** Companion to the [design assessment](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/EVOLVING-KNOWLEDGE-REVIEW.md). The [ten scenario seeds](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/data/evolving-knowledge-scenarios.json) use invented facts and abstract event names. They are test specifications, not valid Librarian API calls or a runnable evaluation suite.

## Questions to answer

1. Does preserving project experience improve later **unseen** work?
2. Does the agent stop applying invalid guidance after a relevant change?
3. Does it preserve unaffected knowledge and historical rationale?
4. Can it recover a working method through a versioned replication recipe?
5. Can the same mechanisms survive worker handoff, restart and scope changes?
6. Are benefits worth acquisition, curation, verification, retrieval and execution costs?

These questions adapt the sequential-transfer emphasis of [LifelongAgentBench](https://arxiv.org/html/2505.11942v1), the evolving-memory framing of [Evo-Memory](https://arxiv.org/html/2511.20857v1), and the interdependent-action emphasis of [MemoryArena](https://arxiv.org/html/2602.16313v1). They add controlled goal/perspective/requirements changes specific to Librarian. None is a claim of reproducing those benchmarks.

## Evaluation layers

| Layer | Execution | What it can establish |
|---|---|---|
| 0 — State and integrity | Local deterministic fixtures over a future adapter to Session/evidence/workflow interfaces | Current-versus-historical eligibility, revision/fingerprint checks, dependency handling, duplicate merge, retrieval scoping and budget invariants |
| 1 — Agent behavior | Fixed qualified route on invented but realistic project streams; no external mutable sources | Whether the agent uses the correct state/evidence and produces the expected answer/action under shifts |
| 2 — Local real work | Curated research/pursuit tasks and bounded mechanical recipes with versioned source captures | Useful transfer, supported synthesis, reproducibility within policy, human correction and actual total cost |
| 3 — Broader transfer | Held-out projects, domains and separately qualified routes | Whether effects survive beyond the development tasks; not justified by a small pilot alone |

Do not run arbitrary benchmark code or open execution scope just to match a paper. Use existing permitted tools, deterministic fixtures and the established execution boundary. Source content and generated worker instructions remain data.

## Treatment arms

All arms retain current user requirements, policy, current-state evidence, safety and the ordinary task capability. “No reusable memory” removes only optional earlier-task experience. Every arm receives the same authorized source access and the same current task.

| Arm | Memory treatment | Purpose |
|---|---|---|
| A | No optional previous-task memory | Cold baseline |
| B | Scoped retrieval of original application episodes | Test experience reuse without learned abstractions |
| C | B plus lifecycle tiers and bounded working-set selection | Isolate what tiering/attention adds |
| D | B plus staged, versioned lessons with applicability and corrections | Test qualified knowledge evolution; compare directly with B and C |
| E | D plus parameterized replication recipes with version-bound checks | Test procedural memory and repeatability |
| F | E plus agent probes and bounded event-triggered revalidation | Test whether monitoring prevents stale/harmful transfer at acceptable cost |

Start with A/B/C/D; add E/F only after simpler arms run correctly. A full combinatorial study is unnecessary initially. Adding an LLM curator, extra samples or different executor routes changes the treatment and must be accounted for. Include acquisition/curation tokens in cost even if performed before the evaluated task.

For agent comparisons, allocate the same total run budget and separately report a practical operating comparison at matched accepted quality. When allocations differ, report the difference rather than presenting a raw success gain as an architecture-only effect.

## Stream design and leakage controls

Each stream contains acquisition, related use, a controlled change, adaptation, unrelated work, and delayed return. Use explicit event/revision boundaries rather than wall-clock waiting. Replay the same boundary into each treatment's cloned initial state. Keep future task facts and expected answers outside accessible memory.

Use chronological acquisition/evaluation splits and disjoint project families for development versus final assessment. Reusable procedures may be induced only from previously observed episodes. If benchmark feedback is given after a task, define its strength and reveal it identically across arms. Distinguish execution/environment feedback from a gold answer. Repeated trials start from independent cloned memory, not the previous trial's improved state.

Freeze route/model configuration, prompt/tool versions, source captures, budgets, randomization, task order and scoring before comparisons. Models cannot generally be made deterministic; repeat streams and report paired differences and uncertainty at the **stream** level. Similar questions within one stream are correlated, not independent sample units. Counterbalance equivalent orders where valid, without destroying causal task dependencies.

The ten seeds are suitable for adapter development, not a representative performance sample. Extend them with separately authored unseen variants and real work before making a release claim. Preregister pilot size and stopping criteria against the actual available budget; no paid agent runs are authorized or launched by this document.

## Required scenario coverage

| Seed | Controlled change | Required behavior |
|---|---|---|
| EKP-01 | Cloud-friendly goal becomes offline-only | Former recommendation becomes inapplicable; original measurement and decision history remain accessible |
| EKP-02 | Source revision withdraws support for one premise | Affected dependent claim requires recheck; unrelated verified result remains usable |
| EKP-03 | One of two independently sufficient support sets fails | Dependent conclusion remains usable under its remaining qualified support; cause is explainable |
| EKP-04 | Explore an alternative lens without adopting it | Operative requirements unchanged; later explicit adoption changes them at its own revision |
| EKP-05 | A failed workaround becomes viable after environment fix | Old failure retained as conditional history; current evidence permits requalification |
| EKP-06 | Cross-project similarity plus unavailable scoped retrieval | No unrestricted fallback; explain scope/availability gap |
| EKP-07 | Replication environment changes after a successful run | Old receipt stays historical; current recipe qualification requires affected checks to rerun |
| EKP-08 | A card's evidence is revised | Old agent probe is retired; human understanding and agent assessment remain distinct; hidden rubric stays hidden |
| EKP-09 | Parent changes requirements while workers run | Stale results cannot close current work; duplicate result has a single merge |
| EKP-10 | Archive, delayed return and incomplete source access | Recover retained rationale under current access; missing essential support prevents unqualified reuse |

Add adversarial variants: late caveat past a preview boundary, source instruction laundered through a lesson, cycle in an execution recipe, false paraphrase contradiction, and a completely unrelated memory with high lexical similarity.

## Metrics and denominators

| Metric | Definition / interpretation |
|---|---|
| Task success and partial progress | Named acceptance predicates passed / required predicates; synthesis adjudicated separately from mechanical closure |
| Forward transfer | Difference between warm-memory and cold matched performance on held-out related variants; report uncertainty, not a single lucky example |
| Preservation | Performance on still-valid earlier knowledge after new learning and distractors; do not count keeping obsolete advice as successful retention |
| Current-state error | Decisions using known inapplicable/superseded/withdrawn material / decisions with an adjudicated opportunity to make that distinction |
| Historical recall | Correct version/rationale answers / explicitly historical questions; historical accuracy cannot excuse current-state misuse |
| Adaptation lag | Number of evaluated decisions after a controlled change until the preregistered recovery condition; unrecovered streams remain censored/failures, not zero lag |
| Correct retirement and over-invalidation | Separately score affected items correctly blocked and unaffected eligible items incorrectly blocked, against authored dependency ground truth |
| Applicability calibration | Correct apply/reject/unknown judgments / labeled procedure-context pairs; report false rejection and harmful reuse separately |
| Replication | Current-version recipes passing all named output/verifier obligations / attempted recipes; include unavailable and interrupted runs as explicit outcomes |
| Probe utility | Consequential stale-use failures detected and prevented versus unnecessary invalidations/rechecks; card-answer accuracy alone is insufficient |
| Benefit and harm | Paired tasks helped and paired tasks harmed compared with A/B, with repeat-run uncertainty; avoid attributing all variance to memory |
| Coverage and access | Supported required items found / known required items; cross-scope leakage and missing-source disclosures reported independently |
| Cost and effort | All role input/output/cache tokens, known/estimated/unknown charges, retrieval/curation/check overhead, latency, memory storage, and human corrections |

If nothing is accepted, cost per accepted task has no finite success denominator: report total cost and zero accepted outcomes. Model-judged scores cannot certify source truth or replace required executable checks. Keep scoring artifacts and outcome labels outside the agent's ordinary context.

For human cards, run a separate consented learning assessment if desired: delayed recall/application under a defined schedule. Do not mix a human learning effect with an agent-memory outcome. Human retrieval-practice findings motivate this separate feature, not an agent cache-expiry rule. [Primary study](https://pubmed.ncbi.nlm.nih.gov/21252317/).

## Failure attribution and review

Record whether a failure came from acquisition, consolidation, indexing, retrieval, context assembly, applicability judgment, execution, merge, or scoring. Save redacted IDs/hashes/versioned references rather than unrestricted prompts. Inspect memory-induced failures and false refusals, including cases where a good answer was available but omitted by scope or size rules.

State invariants should be deterministic: no current closure from a stale requirement; no cross-scope material; no duplicate accepted merge; no irreversible loss of canonical constraints during cache eviction. Behavioral benefits need held-out task evidence. Set a go/no-go threshold before running E/F; do not choose a threshold after observing a desired result.

A useful result is allowed to be negative: tiering may help attention but not correctness; recipes may improve repeatability while making transfer brittle; agent probes may cost more than they prevent. Retain the simpler design when the added mechanism does not improve the agreed quality/cost trade-off.
