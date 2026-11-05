# Checking the memory/context review against its literature (2026-11-05)

**What was checked.** Every claim in the 2026-11-03 memory, context and knowledge
review (`reports/2026-11-03-memory-context-review/`) that cites a source: 67 sources,
126 claims, taken from 10 documents. The question for each was: does the cited source
say what the review attributes to it? Each claim's design inferences for Librarian are
judged separately below; they are not literature findings.

## Verdict

**The review's core memory research holds up.** Every one of the 20 cited arXiv papers
exists. Each paper's title or text matches the name the review uses, including
MemoryArena, Memora, TokenWorth and MemDev-Bench (2026 papers that cannot be checked
from training data). The claims those design choices rest on are supported, with the
quotes found in the papers:
- LongMemEval;
- Zep;
- A-Mem;
- Lost in the Middle;
- RULER;
- MemoryAgentBench;
- LifelongAgentBench;
- Evo-Memory;
- MemoryArena;
- Memora;
- LIMBO;
- TokenWorth;
- MemDev-Bench;
- MAST;
- MINJA;
- Agent Workflow Memory;
- Dynamic Cheatsheet;
- ACE;
- GraphRAG;
- Anthropic's context-engineering note.

**The weaker material is the "formal solutions" and "tool decisions" layer.** There the
review often cites a source for a design rule of its own, which the source does not
state. None of those overreaches is a fabricated source, and none changes the
recommended direction. They do mean several design rules are the review's judgement,
not established findings.

| Verdict | Claims | Share |
|---|---|---|
| supported | 98 | 78% |
| partly (core right, a detail overstated or mis-scoped) | 19 | 15% |
| unsupported (the source does not say it) | 4 | 3% |
| not judgeable from this source (another cited source in the same claim covers it, or only an abstract was available) | 5 | 4% |

By document, the research documents are the strongest:
- **REVIEW.md:** 14 of 16 supported.
- **EVOLVING-KNOWLEDGE-REVIEW.md:** 14 of 15 supported.
- **EVOLVING-KNOWLEDGE-BENCHMARK.md:** 4 of 4 supported.
- **TOOL-DECISIONS.md:** the weakest, at 6 of 13 supported.

## Method (re-runnable)

1. **Extract** (M): a script took every unit (paragraph, table row or bullet) that
   cites a URL or a local extract. It yielded 127 occurrences and 126 distinct claims.
2. **Fetch** (M): each outside source was fetched as text.
   - arXiv HTML and abstracts, specification pages, PDFs via pypdf, and READMEs at the
     pinned commits via raw.githubusercontent.com.
   - PubMed blocks scripted pages, so its two abstracts came from NCBI E-utilities.
   - 54 of 54 outside sources fetched. The 13 local extracts were read from the
     repository; three had NUL bytes, which were stripped.
3. **Read** (M): one `XiaomiMiMo/MiMo-V2.6-Pro` call per source, through
   `scripts/delegate_deepinfra.py` (claude pool, task `lit-check-2026-11-05`).
   - Each call returned a verdict, one or two verbatim quotes, a location and a note.
   - Cost: $0.513 for 66 calls. Three packets were refused before any call for NUL
     bytes, then cleaned and sent.
4. **Quote check** (M): every quote was matched against the source text, strictly and
   leniently (letters and digits only).
   - **239 of 241 quotes found**, 229 of them strictly.
   - No supported, partly or unsupported verdict rests on unfound quotes alone.
5. **Spot check** (M): I read eight supported verdicts drawn at random (fixed seed
   20261105) against their quotes, and agreed with all eight. A found quote proves only
   that the text exists. This sample is the check that the verdicts are sound, and
   eight is a small sample.

Data: `data/literature-check.json` (every verdict, quote, location and note).
Scripts: `scripts/fetch_sources.py`, `scripts/run_check.py`, `scripts/instruction.md`.

## What the review got wrong or overstated

Each row gives the claim's location, what is wrong, and what it changes.

| Where | Claim, as attributed | What the source actually supports | Consequence |
|---|---|---|---|
| `consolidated/02-DESIGN-DIRECTION.md:47` | Knowledge graphs need not be acyclic; define cycle handling; conjunctive premises, disjunctive alternative supports; conservative invalidation. Cited to the 1987 AAAI assumption-maintenance paper and to PROV-DM | The AAAI paper supports conjunctive explanations and alternative minimal supports only. **PROV-DM supports none of it**: it "does not attempt to specify the conditions under which derivations exist" | The acyclicity and conservative-invalidation rules stand as the review's own design decisions. Keep them, labelled as such |
| `formal-solutions/FORMAL-CONTRACTS.md:41` | "SQLite isolation and Temporal's retry discussion establish" that an SQLite transaction cannot make filesystem/remote changes atomic | SQLite isolation covers visibility between connections and journal rollback only. Temporal supports that retried activities can repeat or partly repeat | True as engineering, but not established by these sources. MF-018's at-most-once design does not depend on the citation |
| `formal-solutions/RESEARCH-FINDINGS.md:38`, `TOOL-DECISIONS.md:27` | PROV says provenance is "not whether it is true"; PROV is "not an authorization or truth engine" | PROV-DM says provenance *helps* users "make trust judgements". It never limits itself that way | A sound design stance, but not PROV's. Reword as Librarian's rule |
| `REQUIREMENTS-RESEARCH.md:34` | Three local extracts (LLM-S2KG, CoACL, STAGE) jointly corroborate provenance-bearing retrieval and explicit unresolved links | LLM-S2KG supports source/paragraph provenance and original-text retrieval. **CoACL (A.3) only excludes low-confidence edges** from the refined graph. STAGE supports only the original-text fallback. None describes explicit unresolved links | "Keep inferred links unresolved until supported" is an inference from CoACL's conservative filtering, not something it proposes |
| `REVIEW.md:97` | ReflectiChain tests "scope narrowing, exceptions, temporal relaxation and priority inversion" | The paper's taxonomy is **goal drift, exception injection, temporal relaxation**. Scope narrowing and priority inversion are not its categories | Use the paper's three categories when building drift test cases |
| `REVIEW.md:98` | WASABI: interrupted memory writes, duplicate merge/retry; "use configured local limits, not the paper's probe constants" | WASABI's example is interrupted **HDFS file** writes, with nothing on duplicate merge. Its probe constants deliberately *exceed* configured thresholds | The transfer to memory writes is an inference. The advice on constants inverts the paper's reason for them |
| `consolidated/03-RESEARCH-OBJECTIVES.md:35`, `04-…:83` | ReasoningBank as a source for episodic/semantic/procedural memory; "poor reflection can produce harmful context" | ReasoningBank says it "did not extensively compare with other memory architectures such as episodic or hierarchical memory". The harmful-context warning is ACE's, not ReasoningBank's | Attribute the reflection warning to ACE only |
| `formal-solutions/RESEARCH-FINDINGS.md:94` | Hypothesis stateful testing "checks invariants against a reference model" and is "not exhaustive" | Invariants are user functions run after every step; a reference model is one usage pattern. "Not exhaustive" is not stated | Minor |
| `formal-solutions/RESEARCH-FINDINGS.md:56` | Case-based reasoning treats adaptation as essential | Aamodt and Plaza list Copy as a reuse subtask, trivial reuse in simple classification | Minor; evaluation inside the cycle is supported |
| `EVOLVING-KNOWLEDGE-REVIEW.md:116` | Karpicke and Blunt 2011 supports spacing | That study compares retrieval practice with concept mapping; spacing is the other cited study (Karpicke and Bauernschmidt 2011) | Minor citation slip |
| `formal-solutions/TOOL-DECISIONS.md:10,13,14,16,17` | License and capability facts cited to pinned READMEs | The READMEs don't state most of them. **Checked in the real files, the facts are true**: Inspect `LICENSE` is MIT and its `pyproject.toml` requires `>=3.11`; cwltool `LICENSE.txt` is Apache-2.0; Hypothesis `LICENSE.txt` is MPL-2.0. LangGraph's README covers durable execution and memory, not "checkpoint/store abstractions"; GraphRAG's README says "maintenance mode" but not "global sensemaking" (the GraphRAG paper does) | Facts verified; fix the citations to point at LICENSE and pyproject files |

Five "not judgeable" results:
- **Four are covered by the other URL in the same claim:** Inspect's agent bridge,
  the Build Systems PDF, and Workflow Run RO-Crate, which covers both of the two
  RO-Crate citations.
- **The fifth** (`04-THEORY…:67`, the build-systems analogy) cites only the
  publication page, whose abstract does not contain it. The paper itself, cited
  elsewhere in the review, was judged supported for the related claim.

## The memory research that holds, in one place

These are the supported findings the improvement plan
(`MEMORY-IMPROVEMENTS.md`) relies on. Each is quoted from the source, and the quote
was found by script.

| Source | Supported finding | Verified quote (abridged) |
|---|---|---|
| LongMemEval (2410.10813v2) | Long-term memory has distinct control points (indexing, retrieval, reading). Storing compressed facts instead of original rounds loses information in most tested settings | "We identify four crucial control points for long-term memory of chat assistants" |
| Lost in the Middle (2307.03172) | Using evidence is position-sensitive | "performance can degrade significantly when changing the position of relevant information" |
| RULER (2404.06654v3) | Advertised and useful context length differ | "RULER expands upon the vanilla NIAH test to encompass variations with diverse types and quantities of needles" |
| Zep (2501.13956v1) | Bi-temporal records (event time and ingestion time); episodic data kept alongside derived semantics | "Zep implements a bi-temporal model" |
| A-Mem (2502.12110v1) | Structured notes with links and evolving descriptions | "we construct structured memory notes that capture both explicit information and LLM-generated contextual understanding" |
| ACE (2510.04618v1) | Itemized bullets with ids and helpful/harmful counters; localized delta updates instead of full rewrites | "Rather than regenerating contexts in full, ACE incrementally produces compact delta contexts" |
| ReasoningBank (2509.25140v1) | Strategies and pitfalls from successes and failures; LLM-judge labels can be noisy | "it may introduce noise when tasks are ambiguous or when the judge model itself errs" |
| LifelongAgentBench (2505.11942v1) | Benefit from prior experience depends on the model; for strong models it can be small or negative | "the performance gain from adding prior experience is small or even negative" |
| MemoryAgentBench (2507.05257v3) | Four competencies, including selective forgetting | "accurate retrieval, test-time learning, long-range understanding, and selective forgetting" |
| MemoryArena (2602.16313v1) | Interdependent multi-session tasks; all methods decay with dependency depth | "all evaluated methods exhibit a decay" |
| Memora (2604.20006v1) | Distinguishes incomplete retrieval from continued use of invalid memories | "Questions are organized into three tasks: Remembering, Reasoning, and Recommending." |
| MemDev-Bench (2610.27524v1) | Historical guidance fails by compatibility mismatch and misapplied transfer | "Agents adopt memory whose assumptions do not fit the current task" |
| LIMBO (2609.14138v1), TokenWorth (2610.26453v1) | Replay value is task-dependent, so fixed replay policies waste budget. TokenWorth claims results only at one budget | "we do not claim robustness across a range of budget levels" |
| MAST (2503.13657v3) | Multi-agent failures include coordination failures and acting on wrong assumptions | "proceeding with wrong assumptions instead of seeking clarification (FM-2.2, 6.80%)" |
| MINJA (2503.03704v1) | Malicious memory records can be injected through ordinary queries | "injection of malicious records into the memory bank by only interacting with the agent via queries" |
| GraphRAG (2404.16130v2) | Advantage shown for global sensemaking, not exact lookup | "global approaches significantly outperformed conventional vector RAG (SS) in both comprehensiveness and diversity" |
| Anthropic, context engineering | Compaction, structured note-taking, condensed sub-agent handoffs | "Compaction is the practice of taking a conversation nearing the context window limit, summarizing its contents…" |

**Scope of these findings.** They come from the papers' own benchmarks, models and
domains (U for Librarian). They justify experiments and design choices that can be
tested here. They do not predict Librarian's results.

## Suggested corrections to the 2026-11-03 documents

1. Label the acyclicity, conservative-invalidation, SQLite-atomicity and "PROV is not
   a truth engine" statements as Librarian design decisions, and drop the citations
   that don't carry them.
2. Replace ReflectiChain's categories with goal drift, exception injection and
   temporal relaxation.
3. Point license facts at LICENSE and pyproject files at the pinned commits.
4. Attribute the reflection warning to ACE; attribute spacing to Karpicke and
   Bauernschmidt.

These are edits to a historical review. They can wait for MF-042 (doc
reconciliation) rather than being made now.
