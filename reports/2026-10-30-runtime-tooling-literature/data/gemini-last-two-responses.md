*User prompt: okay, not looking at the mcp tooling, we're looking at the mid-walk tooling, workflows, roles ect currently implemented. please review the harness design and build against the litterature provided, what does the harness do well that can be identified as translations of the information held in the documents, what does the harness not include that may be essential, could assist with reliability, performance, or user experience?*

Response: Evaluating the mid-walk runtime, role architecture, workflow engine, and AuditedEngagement harness (src/resource\_librarian/agent\_runtime.py, loop.py, session.py, audit\_events.py, audit\_projection.py, closure.py, research\_grains.py, profiles.py, role\_routes.py, effort.py, workflows.py, and tools/audited.py) at commit a9be71b against the 51-paper research corpus and design specifications reveals a disciplined architectural foundation alongside several unbuilt or over-simplified mechanisms.

### **1\. What the Harness Does Well (Direct Translations from the Literature)**

| Implemented Mechanism | Codebase Modules | Literature & Design Source | How It Translates the Research |
| :---- | :---- | :---- | :---- |
| **Externalized State & Manage–Preflight–Execute–Audit–Reduce Loop** | session.py, audit\_events.py, closure.py, tools/audited.py | *LongHorizon-Harness* (MEA loop); *Thought Management System* (TMS, Bidochko, 2026\) | Replaces an ever-growing conversational transcript with an append-only, hash-chained Session event store (requirement, artifact, fact, question, contract, verifier\_result, reduction, external\_edit). Crucially, the build adopts TMS's persistent goal/validator separation while explicitly rejecting its autonomous self-expanding goal generation, keeping root goals user-controlled. |
| **Deterministic Tier-A Closure Over Self-Critique or Peer Consensus** | research\_grains.py, target\_audit.py, closure\_audit.py | *ReflectiChain* (Luo et al., 2026); *LLM-Assisted Combinatorial Optimization* (llm\_co); *Mutual Influence* (Oujezsky et al., 2025\) | Represents hard constraints explicitly and gates requirement closure on zero-token deterministic verifiers (quote.located, target.diff\_clean, schema validation, and a9be71b person-bound source\_id checks). This avoids *ReflectiChain*'s negative transfer from heavy reflection prompts on smaller models (40% vs. 95% on CodeSim) and prevents the premature groupthink consensus warned against in *Mutual Influence*. |
| **Non-Monotonic Context Control & Task-Sized Tool Bundles** | audit\_projection.py, agent\_runtime.py, result\_handles.py, loop.py | *Knowledge-Driven Reasoning for Mobile Agentic AI* (Liu et al., 2026); *STAGE* (R13, mathematics-14-01568-v2.pdf) | Directly translates the finding that context exposure is non-monotonic (excess context causes distraction and hallucination, while procedural lookup prunes branching). audit\_projection.py feeds the Manager a bounded state projection rather than raw executor trajectories; agent\_runtime.py narrows the 130-tool registry into phase- and role-scoped ToolBundles (5–12 tools per turn); and result\_handles.py (ADAPT-11) swaps oversized tool outputs for bounded previews and retrievable handles. |
| **Canonical Role-to-Route Isolation & Decoupled Effort Controls** | profiles.py, role\_routes.py, model\_invocation.py, effort.py, clerk.py, scribe.py | *AI Agents vs. Agentic AI* (Sapkota et al., 2026); *SOA Service Coordination* (R07 / bus choreography); *DIK Hierarchy* | Separates control flow from role execution across Lead (Manager/planner), Scribe (scoped writer), Clerk (read-only background worker/auditor), and Helper (read-only sub-agent). effort.py and model\_invocation.py cleanly decouple universal orchestration WorkBudget (turns, tool calls, dollar caps) from route-specific native ModelBehaviour (such as reasoning\_effort or chat\_template\_kwargs). |
| **Provisional Staging,DIK Promotion, & Conservative Filtering** | staging.py, promote.py, dik.py, desk.py, agenda.py | *Knowledge-Worker Study* (Plaito); *CoACL* (R04, Appendix A.3); *Data Annotation Review* (R07) | Honors the workplace study finding that collaborative work relies on provisional, inspectable coordination artefacts (staging queues, desk, agenda) before promotion into persistent knowledge (dik.py, promote.py), and applies *CoACL*'s conservative filtering by quarantining uncertain or unverified outputs rather than auto-promoting them. |

### **2\. What the Harness Does Not Include (Gaps in Reliability, Performance, and UX)**

#### **A. Reliability & Epistemic Integrity Gaps**

> * **Missing Admissible Contract Skeletons & Pre-Submission Auto-Repair (tools/audited.py, audit\_projection.py)**:  
  * **Literature Basis**: R06 (*From LLM narratives to parameterized cooperation policies*, frai-9-1820827.pdf) demonstrates that a structured policy compiler with mechanical compliance checking and deterministic repair/fallback rules yields much higher reliability than unconstrained natural-language generation. The Phase 3 plan (ADAPT-11) likewise specified canonical-ID injection and deterministic argument repair prior to submission.  
  * **Current Deficit**: In the G5 live runs, models repeatedly hit Refusal during preflight because audit\_projection.py does not pre-populate an admissible contract skeleton (enumerating valid verifier\_id options and canonical target paths for each open requirement), forcing the LLM to burn full turns guessing exact predicate strings.  
> * **No Deterministic "Soft Sensor" Loop Breaker for Rephrased Questions (tools/sessions.py, loop.py, quality.py)**:  
  * **Literature Basis**: Boskabadi et al. (*Sense–Infer–Control*, 2025\) use lightweight surrogate "soft sensors" to track unobservable Quality Indicator Variables (QIVs), which the research sprint translated into zero-token deterministic runtime counters for action-loop and question-loop stalls.  
  * **Current Deficit**: ask\_user in tools/sessions.py only checks near-exact string equality, which allowed MiMo-V2.6-Flash to spin in a 115-question loop on t5-lab-sheet because each slightly rephrased question received a fixed answer. The harness needs a deterministic per-requirement no-progress breaker that parks the blocked requirement as unresolved and moves to independent work—without instructing the agent to fabricate an unauthorized assumption.  
> * **Coarse Session-Wide Epoch Bumping & Broken Historical Replay (audit\_events.py)**:  
  * **Literature Basis**: R14 (*Deductive Verification of Process-Oriented Programs*, S0146411625700361.pdf) and the SOA trace model (R07) emphasize scoped temporal invariants where only state variables intersecting a mutation are invalidated.  
  * **Current Deficit**: To patch cross-contract draft overwrites, a9be71b bumps a single global session epoch whenever an existing artifact path is recorded with modified content, which globally invalidates unrelated passing verifications in the same session. In addition, a9be71b requires contract fields on verified reductions without a schema-version fallback, causing pre-a9be71b audited session histories to replay as invalid.  
> * **Vulnerability to Semantic Relationship Inversion (research\_grains.py, HARNESS-08)**:  
  * **Literature Basis**: R02 (*LLM-S2KG*, applsci-16-04720.pdf) proves that even when document and paragraph provenance are preserved, LLM extractions suffer from relationship inversion (e.g., turning *"inhibit"* into *"promote"*), and *Mask-Guided Rationales* shows that quote existence does not prove claim support.  
  * **Current Deficit**: Tier-A quote.located only verifies that a substring exists inside the bound source\_id. It cannot detect relationship inversion or verify multi-source numeric agreement, and the optional read-only Tier-B auditor (HARNESS-08) has not yet been evaluated or wired into high-consequence synthesis gates.

#### **B. Performance, Latency & Cost Efficiency Gaps**

> * **Lack of an Adaptive Complexity Gate to Bypass Multi-Turn Ceremony on Small Tasks (agent\_runtime.py, tools/audited.py)**:  
  * **Literature Basis**: The local E2' Stage A0 experiment proved that managed orchestration (2.51x lead effort) and one-shot delegation (1.46x lead effort) lose to direct inline execution on small tasks due to contract and handoff overhead. *HPR-GenRM* (Chen & Liu, 2026\) and *FA-HRL* (Chen et al., 2026\) similarly support dynamically scaling supervisory depth by task uncertainty and horizon.  
  * **Current Deficit**: Inside an audited session, every grain requires multi-turn contract proposal, preflight admission, execution, and verification calls. Adding an adaptive complexity gate—or batching multiple homogeneous grains into a single preflighted macro contract—would cut the high refusal and turn overhead observed in the DeepSeek and MiMo G5 runs.  
> * **Character-Heuristic Budget Guards & Orphaned Ledger Reservations (scripts/g5\_measure.py, scripts/delegate\_ledger.py)**:  
  * **Literature Basis**: *Knowledge-Driven Reasoning for Mobile Agentic AI* models reasoning as a strict cost-bearing trajectory across token generation, memory retention, and branching.  
  * **Current Deficit**: While a9be71b added a pre-call budget check to g5\_measure.py, it relies on a character-based worst-case estimate rather than actual provider token serialization, does not enforce a hard cross-session cap inside Loop itself, and delegate\_ledger.py still leaves orphaned reservations (\$0.0136 unresolved\_reserved\_usd) when a request fails before receiving a provider receipt.  
> * **Incomplete Mid-Flight Cancellation & Ambiguous-Effect Reconciliation (providers.py, loop.py, ADAPT-04B)**:  
  * **Literature Basis**: *Piccialli et al.* (AgentAI survey, 2025\) and R14 (S0146411625700361.pdf) highlight Behaviour-Tree-style node interruptibility and mandatory reconciliation before retrying an interrupted action whose side effect is uncertain.  
  * **Current Deficit**: Turn-level shutdown checkpointing (CORE-02) is in place, but in-flight provider stream cancellation (ADAPT-04B) and explicit pre-retry reconciliation for interrupted tool calls remain incomplete.

#### **C. User Experience (UX) & Human-Agent Interaction Gaps**

> * **Missing Interactive Mid-Walk Status Ledger & Contestable Grain Inspector (ui/app.js, obsidian/src/main.ts)**:  
  * **Literature Basis**: The *Knowledge-Worker Study* (Plaito), *Homo agenticus*, and *Pedagogy-First* papers emphasize that users must be able to see why the system is blocked, inspect per-requirement evidence provenance, contest assumptions, and remix intermediate outputs without reading raw logs.  
  * **Current Deficit**: While backend events track requirements and verifier outcomes, the browser UI (ui/app.js) and Obsidian plugin (obsidian/src/main.ts) do not yet render a live **Audited Engagement Status Ledger** showing per-predicate pass/fail/stale badges, cost burn by role, and one-click actions to edit a rejected contract or override an assumption mid-walk.  
> * **Read-Only Single-Shot Workbench Instead of an Iterative Coding Workspace (workbench.py, sandbox.py)**:  
  * **Literature Basis**: *SWE-agent* (arXiv:2405.15793v3) and *CaMeL* (arXiv:2503.18813v2) show that agentic coding requires an iterative, stateful Agent-Computer Interface (ACI) with capability-enforced isolation across edit–build–test cycles.  
  * **Current Deficit**: workbench.py only supports single person-triggered commands over a read-only pinned snapshot, lacks a persistent writable candidate worktree for multi-step agentic repair, and checks output size limits in \_archive\_outputs only *after* copying files from the container.

Would you like to focus next on designing the **admissible contract skeleton \+ auto-repair layer** in audit\_projection.py/tools/audited.py to stop preflight refusals, or the **zero-token stall/question-loop breaker** in tools/sessions.py?

---

*User prompt: okay, i just found these academic papers, do they provide insights? if so please give me a quick overview / reading list grouped by what they contribute towards*

Response: **Six of the seven uploaded papers provide actionable architectural insights** for Librarian V2’s mid-walk runtime, verification workflows, retry resilience, and human checkpoints, while **one paper (InfraMLForge) exhibits severe methodological red flags and should be excluded**.

### **1\. At-a-Glance Screening Matrix**

| Paper / System | Study Type & Venue | Core Mechanism | Evidence Grade | Target Librarian V2 Area |
| :---- | :---- | :---- | :---- | :---- |
| **MCP-Secure** *(Singh & Madisetti, 2026\)* | Empirical evaluation (1,080 runs across GPT-5, Claude Sonnet 4, Grok-4), *IEEE OJCS* | Session-level security state machine (L0–L3) with scoped visibility, read-only defaults, and time-boxed privilege elevation that auto-reverts. | **High** — Direct runtime & metric transfer. | closure.py, registry.py, agent\_runtime.py, g5\_measure.py |
| **WASABI** *(Stoica et al., 2024\)* | Empirical bug study (70 incidents) \+ static/dynamic fault-injection tool (109 bugs found), *ACM SOSP '24* | Taxonomy of IF, WHEN, and HOW retry bugs across loops, queues, and state machines; *K*\=1 and *K*\=100 fault injection with 3 retry oracles. | **High** — Essential for loop/queue recovery & testing. | loop.py, providers.py, clerk.py, audit\_events.py, test\_accept\_failures.py |
| **DEMUC** *(Wang et al., 2026\)* | Empirical workflow study \+ CoMis benchmark, *IEEE TKDE* | Proves 7B–8B LLMs fail at direct veracity/conflict judging (51%–67%) but succeed at triplet extraction (73%–78%); decomposes verification into extraction → isolated golden-object query → conflict scoring. | **High** — Solves context-persuasion in Tier-B auditing. | research\_grains.py, clerk.py, lenses.py, HARNESS-08 |
| **eidos** *(Aldana-Martín et al., 2025\)* | Software architecture paper, *SoftwareX* | Intermediary validation/execution split with declarative regex/option schemas, **soft validation** (type coercion), and structured fail-safe error traces. | **Moderate** — Useful pattern for preflight argument repair. | tools/audited.py, registry.py, ADAPT-11 |
| **Delphi-LLM Screening** *(Pournik et al., 2026\)* | Clinical systematic review workflow (14,858 records), *Stud. Health Technol. Inform.* | Pass 1 thematic clustering surfaces exclusion clues → single-round human consensus locks rules → Pass 2 INCLUDE / EXCLUDE / MAYBE triage (*κ*\=0.91, 70% time saved). | **Moderate-High** — Strong UX pattern for bulk intake/adoption. | scout.py, intake.py, deploy\_survey.py, staging.py |
| **APE** *(Qian et al., 2024\)* | System demonstration (Apple), *ACL HITL Workshop* | Query-by-Committee (QBC) active learning across temperature sweeps (*t*∈{0,0.5,1.0}); ranks candidates by label-distribution entropy *H*(*p*) for human annotation. | **Moderate** — Bounded transfer for dedupe & few-shot selection. | document\_identity.py (DEPLOY-04), lens\_gold.py |
| **InfraMLForge** *(Zhang, 2025\)* | Unreviewed preprint, *Research Square* | High-level equations for training, dataset versioning *V*(*di*​), and DAG deployment under resource caps *C*(*θ*)≤*C*max​. | **Exclude / Low** — Severe benchmark & citation anomalies. | None (already covered by stronger sources) |

### **2\. Grouped Reading List & Actionable Insights for Librarian V2**

#### **Group A: Mid-Walk Access Control, Contract Admission & Tool Validation**

**1\. MCP-Secure: A Runtime Access Control Layer for Privilege-Aware LLM Agent Tooling (Singh & Madisetti, 2026\)**

> * **What it contributes:** Demonstrates a host-side mediation pipeline (Scope Check \-\> Guardrails \-\> Effect Check \-\> Decision) governed by a session-level state machine across four levels: L0 (baseline), L1 (task-scoped tools), L2 (read-only default where mutations become safe no-ops), and L3 (approval-gated elevation).  
> * **Key empirical findings to extract:**  
  * **Behavioral Shaping:** Tightening tool scope and read-only defaults does not merely block bad calls after the fact; it alters upstream model planning, dropping average unsafe attempts per run from 2.89 (L0) to 1.80 (L2).  
  * **Auto-Reverting Privilege Windows (L3-Elevated → L2):** When an agent receives approval for a mutating action, privileges elevate only for a time-boxed window before automatically reverting to read-only (L2), preventing privilege drift over long horizons.  
  * **Partial-Progress Telemetry (ProgressBeforeBlock & Benign %):** Instead of binary pass/fail, utility is measured by ProgressBeforeBlock=Total required stepsRequired steps executed​ alongside Benign %=Total calls attemptedAllowed benign calls​×100.  
  * **Metadata Limitation Warning:** Section VII-C explicitly notes that static endpoint-level read/write tags over- or under-approximate safety, requiring argument-level validation and dynamic taint tracking.  
> * **Direct application to Librarian V2:** Add ProgressBeforeBlock and Benign % to scripts/g5\_measure.py so tasks that stall on contract admission still report how far the walk progressed, and ensure contract write permissions in closure.py auto-revert immediately upon grain completion or timeout.

**2\. eidos: A modular approach to external function integration in LLMs (Aldana-Martín et al., 2025\)**

> * **What it contributes:** Separates declarative tool **validation** from **execution** using JSON schemas that specify parameter types, allowed options enums, regex patterns, and expected response structures.  
> * **Key mechanism to extract:** Uses a **multi-tiered validation fallback** where minor formatting/type mismatches undergo deterministic **soft validation** (e.g., safely coercing "42" to 42\) before resorting to fail-safe rejection with a structured error trace, paired with a UI confirmation card showing the exact function and arguments (Continue / Cancel).  
> * **Direct application to Librarian V2:** Directly supports fixing the G5 contract-refusal bottleneck in tools/audited.py—apply semantics-preserving soft coercion (normalizing path slashes, stripping whitespace, matching unambiguous bare predicate keys) before returning a preflight Refusal.

#### **Group B: Mid-Walk Retry Resilience, Cancellation Safety & Fault-Injection Testing**

**3\. If At First You Don't Succeed, Try, Try, Again...? (WASABI) (Stoica et al., SOSP '24)**

> * **What it contributes:** An empirical root-cause analysis of 70 production retry bugs in distributed systems and an automated fault-injection \+ LLM/static analyzer (WASABI) that uncovered 109 new bugs.  
> * **Critical failure modes that map directly to Librarian's runtime:**  
  * **45% of Retries Are Non-Loop (Queues & State Machines):** 25% of retry bugs occur in asynchronous task re-enqueuing and 20% in state-machine re-transitions (like Clerk jobs and AuditedEngagement rounds), where state and error handling are dispersed across files.  
  * **IF Bugs (36%) — Retrying Cancelled Tasks & Wrapped Permission Errors:** Highlights bugs where a task processor catches a generic exception and re-enqueues a task *even after the user or shutdown sequence set isShutdown \= true* (HIVE-23894, ElasticSearch-53687), or retries non-recoverable permission failures (AccessControlException) because a lower layer wrapped them inside a generic exception (HADOOP-16683).  
  * **WHEN Bugs (33%) — Missing Backoff in State Machines & Broken Caps:** State-machine procedures that re-enter the same state on failure without an explicit backoff congest the executor and survive restarts because state is persisted (HBASE-20492). Counter double-increment bugs (YARN-8362) or negative config values (HDFS-15439) either halve or disable retry caps.  
  * **HOW Bugs (31%) — Uncleaned Partial State & Zombie Task ID Collisions:** Retried stages that share the same ID as a timed-out "zombie" stage corrupt shared status maps (SPARK-27630), and retried file-creation steps fail permanently if partial files from the failed attempt aren't cleaned up first (HBASE-20616).  
  * **LLM Context-Size Degradation on Code Analysis:** GPT-4 missed 100 retry loops in files whose token count averaged 10,539 tokens (median 9,304), nearly double the size of files where it succeeded.  
> * **Direct application to Librarian V2:**  
  1. In loop.py, clerk.py, and tools/audited.py, verify that explicit user cancellation/shutdown flags (stop\_event) are checked inside every except block before any retry or queue re-submission.  
  2. Ensure Refusal and scope-authorization errors are never wrapped in generic provider/tool exceptions that trigger automatic retry.  
  3. Adopt WASABI's ***K*****\=1 vs. *K*\=100 fault-injection pattern** in tests/test\_accept\_failures.py: inject *K*\=1 transient failure at each state-transition/tool site to test partial-state cleanup (HOW bugs), and *K*\=100 failures to verify that every loop and state-machine transition enforces both backoff and a hard cap (WHEN bugs).

#### **Group C: Epistemic Verification & Claim-Conflict Decomposition**

**4\. Detecting Misinformation by Uncovering Commonsense Conflicts With LLM Workflows (DEMUC) (Wang et al., 2026\)**

> * **What it contributes:** Explains *why* single-pass LLM verification fails and provides a 3-step decomposed workflow (DEMUC) that outperforms direct prompting.  
> * **Key empirical findings to extract:**  
  * **LLMs Are Bad Direct Conflict Judges Due to Context Persuasion, But Good Extractors:** On the CoMis dataset, Qwen3-8B and DeepSeek-7B achieved only 58% and 51% accuracy when asked directly whether an article contained a conflict (frequently accepting false claims because they were persuaded by the surrounding text), yet achieved **78% and 73% accuracy at extracting structured (subject, relation, object) triplets**.  
  * **Decomposed Verification Isolates the Oracle from Context Persuasion:** Instead of asking the model *"Does draft X contradict source Y?"*, DEMUC (1) extracts (s, r, o) triplets from the text using 3–5 in-context examples (batching ≈6 relations per call, which was empirically optimal before extraction quality degraded) and filters out high-perplexity extractions (*ϵ*\=0.8); (2) queries the knowledge model for the expected object *o*^ given only (s, r) *without the persuasive article context*; and (3) scores the conflict between *o* and *o*^ to emit an explicit contrastive statement ("However, s is r ô instead of o").  
> * **Direct application to Librarian V2:** This directly addresses the **R02 relationship-inversion blindspot** (e.g., *"inhibit"* vs. *"promote"*) in research\_grains.py and HARNESS-08. When designing the Tier-B read-only auditor (clerk.py) or strengthening quote.located, decompose verification: extract (subject, relation, object) from the staged synthesis draft, query the source passage for (subject, relation) \-\> ? in isolation, and compare the extracted object against the source object. Also keep multi-predicate batching capped around ≤6 relations per prompt.

#### **Group D: Corpus Triage, Deduplication & Active Human Checkpoints**

**5\. A Hybrid Delphi-Inspired Expert-LLM Workflow for Efficient Evidence Screening in Systematic Reviews (Pournik et al., 2026\)**

> * **What it contributes:** A two-stage human-LLM screening protocol tested on 14,858 clinical abstracts.  
> * **Key mechanism to extract:**  
  1. **Exploratory Thematic Clustering & Exclusion-Clue Mining:** An initial pass groups records into broad categories and surfaces recurring textual phrases from irrelevant clusters (e.g., "rat model", "cell line") as candidate exclusion rules.  
  2. **Single-Round Consensus Checkpoint:** Humans review and approve the candidate exclusion rules *once* before bulk execution, checking for false-exclusion risk.  
  3. **Three-Valued Triage (INCLUDE / EXCLUDE / MAYBE) with Short Justifications:** Locked rules are embedded into structured prompts that output a 3-state label plus a brief justification for auditability, achieving 96% agreement (*κ*\=0.91), 93% automated exclusion (13,890 / 14,858 records in 1.7 hours), and a 70% reduction in human screening time.  
> * **Direct application to Librarian V2:** Ideal workflow upgrade for deploy\_survey.py (DEPLOY-01), scout.py, and intake.py: when adopting a large directory or screening a batch of papers, have the survey pass propose candidate exclusion patterns from the sampled files, present them at a single user approval checkpoint, and classify borderline items as MAYBE (routed to staging) rather than forcing binary inclusion.

**6\. APE: Active Learning-based Tooling for Finding Informative Few-shot Examples for LLM-based Entity Matching (Qian et al., 2024\)**

> * **What it contributes:** Applies **Query-by-Committee (QBC)** active learning to select the most ambiguous entity-matching pairs ⟨*e*1​,*e*2​⟩ for human annotation and few-shot prompt injection.  
> * **Key mechanism to extract:** Evaluates candidate pairs *m*\=3 times across a temperature sweep (*t*∈{0,0.5,1.0}), computes the binary label distribution entropy *H*(*p*)=−*R*\+(*p*)log*R*\+(*p*)−(1−*R*\+(*p*))log(1−*R*\+(*p*)), and surfaces only the top-*k* highest-entropy (highest disagreement) pairs to the human user for labeling and rationale capture.  
> * **Direct application to Librarian V2:** Useful for lens\_gold.py (ADAPT-10 expectation/lens authoring) and document\_identity.py (DEPLOY-04 Layer 5 near-duplicate LSH candidates): when building golden test sets or resolving ambiguous near-duplicate notes, prioritize human review on the highest-entropy/borderline pairs rather than random sampling.

#### **Group E: Excluded / Low-Trust Source**

**7\. InfraMLForge: Developer Tooling for Rapid LLM Development and Scalable Deployment (Zhang, 2025\)**

> * **Why to exclude from design authority:** This is an unreviewed *Research Square* preprint with major validity issues: its architecture diagram (Fig. 1\) is an unattributed reproduction of a multimodal conversational API-platform diagram, and its evaluation table (Table I) benchmarks unrelated methods—including *"Non-Prehensile Tool Manipulation"*, which is a robotics object-manipulation paper—against NLP datasets (EPIE idioms, CLIMATE-FEVER, SkillSpan, NLPeer) without explaining how a robotics controller or Llama-3-13b was evaluated on them.  
> * **Disposition:** Record in the corpus manifest for completeness, but **do not cite InfraMLForge as empirical support** for Librarian V2’s architecture.

Would you like to fold the **WASABI retry/cancellation guards**, **MCP-Secure auto-reverting write windows \+ ProgressBeforeBlock metric**, and **DEMUC isolated triplet-verification workflow** into docs/long-horizon-harness-design.md (or directly into the runtime modules)?

---
