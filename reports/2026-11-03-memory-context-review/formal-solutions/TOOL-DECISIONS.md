# Tool decision register

3 November 2026. Source-screened candidates, not installed or deployment-qualified products. “Use/prototype” below is a research recommendation, not a change to Librarian's dependency set.

## Shortlist

| Tool | Observed license indication | Recommendation | Fit and limitation | Inspected snapshot |
|---|---|---|---|---|
| TLA+/TLC | MIT | **Use for a focused design model** | CLI requires Java 11+; keep outside runtime. Inspected README says Eclipse Toolbox is unmaintained; prefer CLI/editor integration. | [dc6a944429fe](https://github.com/tlaplus/tlaplus/blob/dc6a944429fe3e26104d38f9ff792d2d5d83f307/README.md) |
| Hypothesis | MPL-2.0, with exceptions | **Prototype as a development test dependency** | Stateful rules can exercise actual Python interfaces against a simpler model. Generated tests do not constitute an exhaustive proof. | [30f73af87f58](https://github.com/HypothesisWorks/hypothesis/blob/30f73af87f587b6911042552e24f1dea2577988a/LICENSE.txt) |
| XTDB | MPL-2.0-or-later per README | **Borrow semantics; defer migration** | Separate database deployment and data model. Temporal query support does not supply domain truth, access policy or withdrawal propagation automatically. | [cf9ad735af92](https://github.com/xtdb/xtdb/blob/cf9ad735af92d8440441deb1fd39b6842c247ace/README.adoc) |
| Temporal server | MIT | **Defer runtime replacement** | Adds a durable orchestration service. Useful if distributed scheduling/recovery becomes an unmet requirement; external effects still need idempotency and reconciliation. | [8ac42361480c](https://github.com/temporalio/temporal/blob/8ac42361480ce7df37aec4adab8d4358e8e1f278/README.md) |
| LangGraph | MIT | **Reference patterns; defer runtime replacement** | Checkpoint/store abstractions overlap current Session/workflow responsibilities. A migration would need policy, replay and revision equivalence tests. | [3c916d750575](https://github.com/langchain-ai/langgraph/blob/3c916d750575b22c464790e9774494d810ccd322/README.md) |
| cwltool | Apache-2.0 | **Evaluate optional interchange/validation** | CWL reference runner; inspected Windows guidance uses WSL2/Docker. Keep existing registered-tool runtime as the default execution boundary. | [959ce27ea0ea](https://github.com/common-workflow-language/cwltool/blob/959ce27ea0ea0d9b1d083fb34a47d46a22954852/README.rst) |
| Anki | AGPL-3.0-or-later, with exceptions | **Optional human-review integration** | Use for the person's review history, with versioned source links. Do not conflate card success with agent execution competence or copy its scheduling into agent expiry. | [100390631376](https://github.com/ankitects/anki/blob/1003906313766ef73f949d48fdeb074fe2a1f3b2/LICENSE) |
| Microsoft GraphRAG | MIT | **Defer central adoption; narrow retrieval experiment only** | Pinned README explicitly describes maintenance mode. Published evidence concerns global sensemaking, not general temporal memory correctness. | [34b2b67ae460](https://github.com/microsoft/graphrag/blob/34b2b67ae4601ad0b47bcd179fbe3f2a23aa0857/README.md) |
| Inspect | MIT | **Prototype in an isolated evaluation environment** | Python >=3.11 fits V2's declared range, but dependency compatibility was not resolved. Adapter must preserve route/tool behavior and include every worker's cost. | [de4b309791b2](https://github.com/UKGovernmentBEIS/inspect_ai/blob/de4b309791b2d4d49d3064f3c2760f37ba86cc92/README.md) |

Full commit IDs, repository dates and metadata are in [tool-snapshots.json](/D:/Librarian_V2/reports/2026-11-03-memory-context-review/formal-solutions/tool-snapshots.json). Pins identify the reviewed source, not recommended release versions. Repository metadata reported all nine as non-archived, but that did not establish active feature development: GraphRAG's own README is more informative. No popularity measure was used as proof of quality.

License entries are screening observations from repository metadata and the linked files. Hypothesis and Anki had ambiguous metadata labels, resolved by reading their license files; this is not a full dependency/distribution license audit.

## Standards to reuse without adopting a platform

| Standard/method | Concrete use | Qualification |
|---|---|---|
| [PROV-DM, 2013 Recommendation](https://www.w3.org/TR/2013/REC-prov-dm-20130430/) | Source/derivation/revision identity and optional provenance interchange | A vocabulary, not an authorization or truth engine |
| [CWL v1.2.1](https://www.commonwl.org/v1.2/Workflow.html) | Typed inputs/outputs and explicit dependency contract for replication recipes | Do not claim CWL conformance for an incomplete custom subset |
| [RO-Crate 1.1](https://www.researchobject.org/ro-crate/specification/1.1/) and [Workflow Run RO-Crate](https://www.researchobject.org/workflow-run-crate/) | Export run artifacts and their execution context | Interchange packaging does not itself reproduce a result; 1.1 is the inspected version, not a claim it is newest |
| Bitemporal projection | Separate when information applied from when it became known | Can be modeled in current storage; exact schema and correction semantics still need tests |
| Case-based reasoning | Retrieve, adapt, test and retain scoped experience | Similarity alone cannot qualify transfer |
| Support groups and dependency fingerprints | Preserve alternative evidence and target rechecks | Full dependency completeness is not established by an inferred graph |

## Why not replace the current stack now?

The preceding code reviews found existing application logs, Session history, a workflow registry, claim checks, hybrid retrieval and source indexes. A replacement must demonstrate more than overlapping features. The immediate gaps concern contracts across these boundaries: current applicability, full request size, stable evidence, parent acceptance and qualification of reusable lessons.

A separate temporal database or workflow service also introduces backup, schema evolution, access control, retention and failure reconciliation responsibilities. Those costs may be justified later, but no deployment or workload measurement in this pass establishes that they are justified now. This is a fit assessment, not a claim that those products are unsuitable in general.

## Adapter qualification checks

For any selected prototype, freeze a release and dependency lock before running comparisons. Use synthetic or captured permitted data first. Check:

1. **State ownership:** one durable authority; secondary indexes and checkpoints have explicit rebuild/rollback behavior.
2. **Scope:** enforce current access on lookup, graph expansion, fallback, rehydration and worker merge. A namespace alone is not proof of access isolation.
3. **Withdrawal:** revoke current eligibility and account for cached excerpts, vectors, summaries and exported artifacts; separate retention policy from retrieval policy.
4. **Continuity:** replay/restart with version-bound evidence; reject incompatible code/schema/input revisions visibly.
5. **Route fidelity:** an evaluation adapter must not silently alter model settings, tools, compaction or accepted feedback.
6. **Resources:** include curation, indexing, worker, model and verification costs; confirm offline requirements and Windows deployment behavior empirically.
7. **Exit:** export canonical records, source references and receipts in a documented format; demonstrate reconstruction without the candidate service.

These are proposed qualification criteria. This pass checked public documentation, selected source files, metadata and local manifests; it did not validate telemetry defaults, every transitive license, Windows installation, native exports, deletion behavior, or production performance of these candidates.

## Recommended first experiment

Use the current runtime with a small external evaluation adapter and stateful tests. Compare no optional prior experience, original episode retrieval, episode retrieval plus tiers, and qualified lessons. Add a temporal/source-revision fixture before any learned curation. Advance recipes or selective dependency indexing only when the baseline exposes a measurable problem they can solve.

That experiment can determine whether the proposed changes improve Librarian. The available papers and product documentation cannot substitute for it.

