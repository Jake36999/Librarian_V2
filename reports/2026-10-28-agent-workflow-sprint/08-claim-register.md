# Claim register for outside tools and companies (deliverable 8, revision 2)

Date: 2026-10-28 (revised the same evening). Source: the Gemini review (`workflow discussion and review - gemini.md`, 549 lines, five separate responses). A model extracted every factual assertion with a verbatim quote (3 calls, 178 anchored claims, 99% of quotes found at the cited line); duplicates were merged to 174 claims. Revision 2 replaces the first pass's regular-expression tagging, which operated on claim fragments, with a hand-written disposition for each examined claim (`data/claim_dispositions.csv`), each with its source, retrieval date and who checked it. A second-pass review corrected several first-pass verdicts; the ones marked below as read in this review were re-read from the primary source here, not taken on trust.

**Tags.** *verified*: supported as stated by a primary source read in this sprint, or observed directly. *plausible*: partly supported, or consistent with secondary reports or local data. *unverified*: no supporting source read. The `qualifier` column records scope corrections (a true number attached to the wrong scope), partial support, general risks and design hypotheses. Result for the 32 claims about outside companies, tools and services: **8 verified, 16 plausible, 8 unverified**. A further 35 claims concern our own sessions, data or design heuristics and are listed separately; 107 are opinions or local facts this sprint did not examine (all in `data/claim_register.csv`). A verified tag means 'supported by the retrieved source', not independently replicated, and it says nothing about the claim's usefulness to the Librarian.

**Rule applied.** No design in `06-design-proposals.md` depends on a plausible or unverified claim. The outside facts the designs rest on are: DeepInfra's live model and price listing, DeepInfra's data-privacy documentation (relayed by the fetch tool), vLLM's documentation of constrained output (verified for vLLM only: it says nothing about any DeepInfra route, so each route must be qualified separately), and fields in Claude Code and Codex logs (measured locally). The OpenAI figures are used only to evaluate Gemini's review.

**Added 2026-10-29.** Outside claims introduced by the overseer-workflow review (Agentless, MAST, the scaling-agent-systems paper, Anthropic's multi-agent research article, DeepInfra prices) are tagged in `10-final-report.md`, appendix A. They are not counted in the totals above, which concern the Gemini review.

## Primary sources read

| Source | Used for | Read |
|---|---|---|
| `https://openai.com/index/navier-stokes-solution/` | agent counts, durations, message and token totals, Codex consolidation, the Lean phase | 2026-10-28 with the built-in browser. The fetch tool gets HTTP 403, which is why the first pass could not read it |
| `https://github.com/openai/math` (README) and `history.md` | 721 manuscripts in 373 families, about 4,000 problems, three manuscripts withdrawn on 7 October, two added on 26 October | 2026-10-28 |
| `https://docs.vllm.ai/en/latest/features/structured_outputs/` | constrained output types and backends | 2026-10-28 (fetch tool) |
| `https://docs.deepinfra.com/account/data-privacy` | 'Input data is not stored to disk'; 'We do not log the content of your requests'; bulk APIs may store data encrypted for a short, unstated period; Google and Anthropic models follow those companies' policies; metadata logged (request ID, cost, sampling parameters) | 2026-10-28 (fetch tool summary) |
| `https://deepinfra.com/privacy` | the general policy statement | 2026-10-28 (first pass, fetch tool) |
| `https://api.deepinfra.com/v1/openai/models` | rate cards, context lengths, model availability | 2026-10-28T17:05Z |

## Outside claims

| ID | Line | Claim (verbatim) | Tag | Qualifier | Basis |
|---|---:|---|---|---|---|
| CL-001 | 7 | You will actually be disappointed if you open the **166-page paper** itself looking for system architecture. | plausible | secondary_only | The announcement links the paper but gives no page count; the 166 figure rests on secondary reports. Source: https://openai.com/index/navier-stokes-solution/ (no page count); secondary news reports (. |
| CL-002 | 7 | It contains zero systems engineering diagrams or orchestration code. | unverified |  | A zero-content claim about the proof document needs a full inspection of it; not done. |
| CL-003 | 9 | technical disclosures from OpenAI researchers like Sébastien Bubeck. | unverified |  | No specific staff disclosure was identified and read. |
| CL-004 | 13 | separated mathematical discovery, context consolidation, and formal verification into distinct phases | plausible | partly_supported | Discovery by agent groups, Codex consolidation and a later Lean verification phase are described; calling them distinct automated phases is the commentator's interpretation. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-005 | 15 | OpenAI spun up multiple isolated groups of concurrent agents powered by an unreleased internal frontier model | plausible | partly_supported | Groups of agents powered by an unnamed internal model are described, with monitoring and isolation safeguards; the strength of isolation between groups is not stated (groups communicated internally). Source: https://openai.com/index/navier-stokes-solution/. |
| CL-006 | 15 | different agent groups were assigned variants of the Millennium Prize problems | verified |  | Different groups were prompted with different variants of the problem statement. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-007 | 15 | some swarms attempting to prove smoothness, others attempting to construct a singularity | verified |  | Versions A and B (proof) and C and D (disproof) were given to separate groups. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-008 | 16 | scaled to roughly **10,000 concurrent agents** | verified |  | The group that produced the Navier-Stokes resolution involved on the order of 10,000 concurrent agents. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-009 | 16 | Over an **88-hour run**, the Navier–Stokes swarm exchanged approximately **2.7 million internal messages** | verified |  | Resolution about 88 hours after the first agents launched; 2.7 million messages and about 130 billion output tokens in resolving Navier-Stokes. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-010 | 16 | the total hit **4.9 million messages** and \~300 billion tokens | verified | scope_correction | 4.9 million messages and about 300 billion output tokens are the totals across ALL attempted problems, not the Navier-Stokes run. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-011 | 17 | OpenAI periodically paused or sampled the swarms and used **Codex** as a consolidation engine. | plausible | partly_supported | Codex was used to consolidate the most useful insights from each agent group; periodic pausing or sampling of the swarms is not stated. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-012 | 17 | Codex ingested the raw intermediate mathematical findings from separate agent groups | plausible | partly_supported | Follow-up prompts drew on the agents' own intermediate results; the ingestion mechanism is not described. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-013 | 18 | Once the unannounced internal model produced the natural-language analytical proof (the 166-page construction) | plausible | partly_supported | The solving model is an unnamed internal model; the proof page count is not on the announcement page. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-014 | 18 | which spent an additional **17 hours** auto-formalizing and compiling the proof into **Lean** | verified |  | Lean formalization and verification took an additional 17 hours via GPT-6 Astra. The first pass wrongly said no source stated this. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-015 | 18 | auto-formalization can subtly alter hypothesis semantics during translation | plausible | general_risk | A general specification-translation risk; no specific demonstrated case was audited here. |
| CL-016 | 22 | OpenAI has **not** open-sourced or published UI screenshots of their internal orchestration dashboard | unverified |  | The announcement does not address dashboards or UI; absence elsewhere cannot be inferred from one page. |
| CL-017 | 24 | the "central dashboard" wasn't just a passive telemetry viewer—it functioned as a **stateful MapReduce / DAG c | unverified |  | A MapReduce or DAG controller is not disclosed by the retrieved sources. |
| CL-018 | 26 | the 10,000 agents were executed inside strict network-isolated sandboxes | unverified | partly_supported | The page states strict safeguards including monitoring and isolation, and that agents could read a cached copy of the internet; strict network-isolated sandboxes are not stated. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-019 | 27 | Their control plane relied on an automated **Reduction/Consolidation node (Codex)** | plausible | partly_supported | Codex consolidation is stated; an automated control-plane node is not. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-020 | 28 | By wiring the **Lean theorem prover** into the downstream pipeline | verified |  | A Lean formalization and verification of the proof is described and linked. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-021 | 36 | Pure PDE math, self-similar vortex profile equations, and asymptotic bounds. | unverified |  | Exact proof contents were not reviewed. |
| CL-022 | 37 | High-level metrics (10k agents, 4.9M messages, 88h runtime) | plausible | scope_correction | Mixes scopes: 10,000 agents and 88 hours belong to the Navier-Stokes group and run; 4.9 million messages is the all-problems total (2.7 million for Navier-Stokes). Source: https://openai.com/index/navier-stokes-solution/. |
| CL-023 | 38 | The formal theorem definitions, dependency graph of lemmas, and tactic scripts generated by GPT-6 Astra. | plausible | partly_supported | The Lean work is attributed to GPT-6 Astra (the first pass wrongly called this contradicted, by comparing with a different document); the breakdown into definitions, lemma graph and tactic scripts is not stated. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-024 | 39 | A critical teardown of how AI auto-formalization into Lean can introduce semantic drift | unverified |  | No specific critical teardown was identified and read. |
| CL-025 | 74 | the subsequent October 2026 release of 722 mathematical manuscripts | plausible | version_and_denominator | README: 721 manuscripts in 373 families now. history.md records three manuscripts withdrawn on 7 October and two added on 26 October; no initial count is stated (its 300/719 figure counts top-line results, not manuscripts). The fi Source: https://github.com/openai/math (README); https://github.com/openai/math/blob/main/history.. |
| CL-026 | 84 | OpenAI used **Codex as a periodic consolidation bottleneck** between agent waves. | plausible | partly_supported | Cross-pollination by Codex is stated; calling it a periodic bottleneck is not. Source: https://openai.com/index/navier-stokes-solution/. |
| CL-027 | 94 | even with Lean 4, LLMs will try to subtly alter definitions to make the code compile | plausible | general_risk | Possible semantic mismatch in autoformalisation is widely discussed; intentional model behaviour is not shown. |
| CL-028 | 103 | 2.7 million messages in OpenAI's run did not mean 2.7 million casual Slack-style messages. | unverified |  | Message contents and schema were not described. |
| CL-029 | 106 | via guided decoding / JSON schema enforcement in vLLM or Outlines | verified | vllm_only | vLLM documents JSON-schema, regex, choice and grammar constrained output (backends xgrammar and guidance; outlines appears only in regex notes). Says nothing about any DeepInfra route. Source: https://docs.vllm.ai/en/latest/features/structured_outputs/. |
| CL-085 | 323 | Provisioning overhead on Vast.ai (\~5–8 minutes to pull container image and weights) | plausible | local_partly_supported | Measured rent-to-runner time was 4.6, 5.6 and 5.5 minutes on three rentals; this does not isolate image pull and weight load. Source: data/vast_summary.json. |
| CL-095 | 344 | call DeepSeek-V3 / Qwen-Coder on DeepInfra to write and debug the Python script | plausible | partly_supported | The live listing shows these models are available; it does not show that they can write and debug such a script. Source: https://api.deepinfra.com/v1/openai/models. |
| CL-096 | 348 | it uses the Vast.ai CLI/API to spin up a pre-configured Docker image (containing your JAX/CuPy environment \+  | plausible | partly_supported | A local controller and the Vast CLI and API rented boxes for 31 jobs; the exact image contents (JAX, CuPy, vLLM) are not established. Source: data/vast_summary.json. |

## Claims about our own sessions, data and design heuristics

These were filed as outside claims by the extractor but describe what happened in our sessions, what our data show, or a proposed heuristic. They are not tagged verified, plausible or unverified. `local_supported` means a measurement or repository record supports it; `local_reported` means only a transcript says so.

| ID | Line | Claim (verbatim) | Status | Basis |
|---|---:|---|---|---|
| CL-032 | 148 | using DeepInfra like a glorified PDF summary tool ($0.59–$1.03 per batch for 32–37 literature notes) | partly | '$1.03' appears once in research-session tool output; '$0.59' and the per-batch framing were not found. |
| CL-039 | 160 | its entire cumulative conversation history (often 50k–100k+ tokens) is re-processed. | local_measured_proxy | Cache reads are 99% of Claude input tokens, so history is re-sent every turn, but mostly at the cache-read price; an every-turn full re-processing cost is not established. |
| CL-040 | 161 | Spending \$1.03 out of a \$5.00 DeepInfra budget sounds thrifty | partly | Same check as CL-032. |
| CL-054 | 240 | Because those sub-agents shared the same platform API/classifier pool, they immediately hit server overloads a | unverified | A shared platform-pool explanation for tool blocks is not demonstrated by local error counts. |
| CL-056 | 241 | bumped ThreadPoolExecutor(max\_workers=8), enforced a \$4.50 hard stop in cost\_log.jsonl | not_checked | A hard cap value in research batch scripts that are not in the provided data. |
| CL-078 | 307 | Embarrassingly parallel, **single-pass or low-iteration** tasks where total tokens are predictable and wall-cl | design_hypothesis | A workload-selection heuristic, not a measured fact. |
| CL-079 | 308 | High-iteration **attempt-bounded** loops (e.g., 100+ trial solver continuations, massive parameter sweeps | design_hypothesis | An attempt-bounded compute heuristic that needs task-specific benchmarking. |
| CL-082 | 321 | 37 notes=\$1.03 on DeepInfra | partly | Same check as CL-032. |
| CL-083 | 321 | one shot per paper; 37 notes=\$1.03 on DeepInfra | partly | Same check as CL-032. |
| CL-086 | 329 | Costs $0.59–$1.03 per batch and finishes in 90 seconds via ThreadPoolExecutor(max\_workers=8) | partly | Same check as CL-032. |
| CL-089 | 330 | Offloading the coding loop from Claude to DeepInfra saves Claude's context limit while costing \<\$0.15 in API | unverified | Savings and the dollar cap need paired task measurement. |
| CL-090 | 331 | You rent a node for e.g. 4 hours ($4–$8 total), run vLLM \+ JAX side-by-side | unverified | An illustrative rental price and stack. |
| CL-093 | 332 | Zero LLM tokens during run; 100% JAX FFT/ETDRK4 GPU compute (2–12 GPU-hours) | unverified | Zero-model-token runtime and GPU-hours depend on the exact workload. |
| CL-094 | 340 | librarian lit-batch \--brief RESEARCH\_BRIEF\_B5.md \--budget 4.50 | design_hypothesis | An illustrative command, not evidence that the tool exists. |
| CL-098 | 360 | Claude immediately abandons the tool and writes raw inline Python/Bash to do the job inside its own context wi | local_reported | A behavioural generalisation from historical sessions. |
| CL-099 | 366 | In every session, Claude refuses to generate or fetch anything until it builds a structural map of the workspa | local_reported | An every-session universal claim not supported by a sampled transcript. |
| CL-105 | 373 | In the first session, Claude used the librarian CLI and resource-library MCP tools directly. | local_reported | A historical tooling assertion; the quote is not execution proof. |
| CL-106 | 375 | Claude needed every DeepInfra worker (deepseek-ai/DeepSeek-V4-Pro-0813) to evaluate papers against | local_reported | A historical exact-model claim; the model suffix was not checked against the research-side script. |
| CL-107 | 375 | run ThreadPoolExecutor(max\_workers=8) with a hardcoded BUDGET \= 4.5 | not_checked | Same as CL-056. |
| CL-108 | 376 | and *immediately* using the wall-clock wait time to write session memories or start the A0 code inventory (job | local_reported | Needs task timestamps to check the overlap. |
| CL-109 | 380 | model labels are leads, never findings; verify against the text with pages, or label UNVERIFIED | local_reported | An evidence-handling policy statement, not a model capability. |
| CL-110 | 382 | Claude **does not trust the DeepSeek-V4-Pro drafts** | local_reported | An interpretation of historical review behaviour. |
| CL-123 | 403 | hypotheses C1–C14 under a \$5 budget | local_reported | A historical experiment and budget claim without per-task reconciliation. |
| CL-127 | 413 | ThreadPoolExecutor \+ custom CONTEXT prompt \+ \$4.50 cap \+ cost\_log.jsonl | not_checked | Same as CL-056. |
| CL-132 | 428 | Claude knows that LLMs hallucinate page numbers (like the p. 8 vs p. 9 Bekenstein error Claude caught in stamp | local_reported | A specific earlier page-number error anecdote, not adjudicated. |
| CL-133 | 428 | invent author names from memory (like the "Cassandro" vs Galvagno & Giribet error Claude caught on itself) | local_reported | A specific earlier author-name error anecdote, not adjudicated. |
| CL-139 | 442 | Estimated cost ≈\$0.80−\$1.20, deterministic 1-shot completion. | unverified | A budget estimate and deterministic-completion claim without a defined workload. |
| CL-142 | 457 | ChatGPT caught that /api/tool runs as person\_call with curate authority and no broker | local_reported | A historical code-review finding that must be bound to its revision. |
| CL-144 | 458 | .venv\\Scripts\\python.exe on Windows acts as a redirector process (spawning a child PID different from the pa | local_supported | The venv python launcher spawns a base-interpreter child with a different PID (documented in the plan); not a vendor capability claim. |
| CL-145 | 458 | os.kill(pid, 0\) reports exited Windows processes as alive while a handle is held | local_supported | Repository fix and test documents the behaviour in that Windows setup. |
| CL-147 | 459 | live DeepInfra validation showed both MiMo-V2.6-Flash and DeepSeek-V4.1-Flash failing the add\_project walk | local_reported | Earlier route-walk failures were not rerun; do not generalise from model names. |
| CL-149 | 459 | Fixing the state-aware bundle brought live validation to **8/8 passing** at **\$0.01** total cost. | confirmed | 8 of 8 cases passed, 0 provider failures, estimated cost $0.0105. |
| CL-152 | 464 | forcing ChatGPT to recover work from git reflog | local_reported | A historical reflog-recovery assertion not replayed. |
| CL-153 | 465 | ChatGPT's safety gate refused to upload loop.py to DeepInfra without explicit per-file export approval. | local_reported | A specific historical approval refusal, not a platform policy. |
| CL-155 | 466 | Both Claude and ChatGPT repeatedly hit rate/usage limits mid-suite | local_supported | Structured limit events support repeated hits by both agents; mid-suite attribution not checked. |

## Changes from the first pass

| ID | First pass | Now | Why |
|---|---|---|---|
| CL-004 | unverified | plausible (partly_supported) | Discovery by agent groups, Codex consolidation and a later Lean verification phase are described; calling them distinct automated phases is the commentator's interpretati |
| CL-006 | plausible | verified | Different groups were prompted with different variants of the problem statement. |
| CL-007 | plausible | verified | Versions A and B (proof) and C and D (disproof) were given to separate groups. |
| CL-008 | plausible | verified | The group that produced the Navier-Stokes resolution involved on the order of 10,000 concurrent agents. |
| CL-009 | plausible | verified | Resolution about 88 hours after the first agents launched; 2.7 million messages and about 130 billion output tokens in resolving Navier-Stokes. |
| CL-010 | unverified | verified (scope_correction) | 4.9 million messages and about 300 billion output tokens are the totals across ALL attempted problems, not the Navier-Stokes run. |
| CL-014 | unverified | verified | Lean formalization and verification took an additional 17 hours via GPT-6 Astra. The first pass wrongly said no source stated this. |
| CL-016 | plausible | unverified | The announcement does not address dashboards or UI; absence elsewhere cannot be inferred from one page. |
| CL-020 | plausible | verified | A Lean formalization and verification of the proof is described and linked. |
| CL-022 | unverified | plausible (scope_correction) | Mixes scopes: 10,000 agents and 88 hours belong to the Navier-Stokes group and run; 4.9 million messages is the all-problems total (2.7 million for Navier-Stokes). |
| CL-023 | unverified | plausible (partly_supported) | The Lean work is attributed to GPT-6 Astra (the first pass wrongly called this contradicted, by comparing with a different document); the breakdown into definitions, lemm |
| CL-024 | plausible | unverified | No specific critical teardown was identified and read. |
| CL-028 | plausible | unverified | Message contents and schema were not described. |
| CL-029 | plausible | verified (vllm_only) | vLLM documents JSON-schema, regex, choice and grammar constrained output (backends xgrammar and guidance; outlines appears only in regex notes). Says nothing about any De |
| CL-095 | verified | plausible (partly_supported) | The live listing shows these models are available; it does not show that they can write and debug such a script. |
| CL-096 | verified | plausible (partly_supported) | A local controller and the Vast CLI and API rented boxes for 31 jobs; the exact image contents (JAX, CuPy, vLLM) are not established. |
| CL-039 | plausible | reclassified as local (local_measured_proxy) | Cache reads are 99% of Claude input tokens, so history is re-sent every turn, but mostly at the cache-read price; an every-turn full re-processing cost is not established |
| CL-078 | unverified | reclassified as local (design_hypothesis) | A workload-selection heuristic, not a measured fact. |
| CL-079 | unverified | reclassified as local (design_hypothesis) | An attempt-bounded compute heuristic that needs task-specific benchmarking. |
| CL-094 | unverified | reclassified as local (design_hypothesis) | An illustrative command, not evidence that the tool exists. |
| CL-109 | unverified | reclassified as local (local_reported) | An evidence-handling policy statement, not a model capability. |
| CL-144 | verified | reclassified as local (local_supported) | The venv python launcher spawns a base-interpreter child with a different PID (documented in the plan); not a vendor capability claim. |
| CL-145 | plausible | reclassified as local (local_supported) | Repository fix and test documents the behaviour in that Windows setup. |
| CL-155 | unverified | reclassified as local (local_supported) | Structured limit events support repeated hits by both agents; mid-suite attribution not checked. |
