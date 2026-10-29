# Reading list (deliverable 3, part 1, revision 2)

Date: 2026-10-28 (revised the same evening after a second-pass review; the first-pass list is in `revision-1/`). Corpus: `E:\Librarian research` (51 files, 50 distinct: two PDFs are byte-identical) plus 26 agent-related notes already in the Resource-Library vault. Paper numbers (#n) are the first-pass ranks, kept as identifiers.

**What changed.** The first pass triaged each paper from its first two pages, last page and headings, scored it 0 to 3 in four categories, and extracted at most six method cards from 18 papers. That screening mislabelled adjacent work as irrelevant, and one total ranking mixed domain match, evidence quality and immediate applicability. Revision 2 reads **all 50 distinct papers in full** (MiMo-V2.6-Pro, one paper per call), repeats 17 decision-relevant papers with an independent reader (GLM-5.3 for 8, GLM-5.3-Flash for 9), and fills a fixed checklist: problem, evidence type, unit, comparators, methods (A metrics, B schemas, C drift and memory, D communication efficiency, E verification and checking), reported costs, negative results, limitations and reproducibility. Every item carries a page and a quote that a script found on that page (`data/lit2_items.csv`); that proves the quote exists, not that it supports the claim (see the support audit in `04-extraction-table.md`).

**Applicability, three ways, none of them decisive.** Levels: *direct candidate* = the same class of control, verification or coordination problem as an LLM lead delegating to other models; *bounded analogy* = a named mechanism, schema or metric that could transfer to such work with a stated adaptation; *out of scope* = no concrete transfer. The primary reader gave a level while reading; a judge from another model family (Qwen3.5-397B) classified each paper again from its reading record on a stricter written rubric (`scripts/build_applicability.py`). They agree on 48 of 50 papers, and **both call 46 of 50 at least a bounded analogy**, so the scale barely discriminates: models find an analogy almost everywhere. Where two readers read the same paper they gave the same level for 13 of 17. I therefore also give a **reading priority** (high, medium, low) based on titles, the readers' reasons, the judge's named mechanism and the verified item counts; it is my judgement from those records, not from reading all 50 papers, and it is meant to be argued with.

Reading priority: **14 high, 16 medium, 20 low.** Low means a different learning setup, a physical system or a keyword match (for example drift in class-incremental learning, verification of weather forecasts): not unexamined, but unlikely to repay a close reading for this project.

## Read in four tracks

Papers with at least one anchor-verified method in the track's categories, most methods first. 'Costs' and 'Neg.' count verified cost items and negative results the paper reports.

### Metrics and orchestration

| Paper | Priority | Methods here | Costs | Neg. | Why |
|---|---|---:|---:|---:|---|
| #14 From LLM narratives to parameterized cooperation policies in multi-age | high | 7 | 4 | 5 | Fixed-rule baseline matched the compiler; critic stress test |
| #18 Industrial Agentic AI and generative modeling in complex systems | medium | 7 | 4 | 4 | Industrial agentic AI survey: ensembles and closed-loop control |
| #04 Transforming Data Annotation with AI Agents: A Review of Architectures | medium | 5 | 5 | 5 | Survey of annotation agents; its cost savings are cited, not experiments |
| #11 HDDLGym: A Tool for Studying Multi-Agent Hierarchical Problems Defined | high | 5 | 5 | 2 | Explicit task effects; success falls as agents are added |
| #21 Transforming cybersecurity with agentic AI to combat emerging cyber th | medium | 5 | 4 | 3 | Agent security: least privilege, isolation, guardrails (survey) |
| #32 A knowledge-based approach for guided development of Infrastructure as | medium | 5 | 5 | 4 | Ontology-backed validation of configuration code |
| #42 Mask-guided rationales meet LLMs: Hybrid encoder–LLM question answerin | high | 5 | 5 | 3 | Evidence sufficiency and faithfulness tests for rationales |
| #01 ReflectiChain: Mitigating Semantic-Execution Drift in Long-Horizon LLM | high | 4 | 5 | 4 | Drift metrics with explicit costs; negative transfer to code outside its home domain |
| #03 KNOWLEDGE-DRIVEN REASONING FOR MOBILE AGENTIC AI: CONCEPTS, APPROACHES | high | 4 | 4 | 5 | Reusable knowledge packs with token costs; context utility not monotonic |
| #06 Mutual Influence AI: Trust-Based Cooperation Mechanisms for LLM Multi- | medium | 4 | 5 | 4 | Trust-weighted cooperation and rounds-to-approval; effects not significant |
| #08 Confidence-Aware Tree-of-Thoughts: A Federated Safety Net for VLM Agen | high | 4 | 5 | 4 | False-execution and false-refusal measures with a risk frontier |
| #19 Exploring How Knowledge Workers Situate an Organisationally Embedded L | medium | 4 | 5 | 5 | Human review and coordination effort in one organisation |

### Continuity, drift and memory

| Paper | Priority | Methods here | Costs | Neg. | Why |
|---|---|---:|---:|---:|---|
| #03 KNOWLEDGE-DRIVEN REASONING FOR MOBILE AGENTIC AI: CONCEPTS, APPROACHES | high | 3 | 4 | 5 | Reusable knowledge packs with token costs; context utility not monotonic |
| #12 ReflectiChain: Grounding Long-Horizon LLM Planning against Semantic-Ex | high | 3 | 3 | 5 | Second ReflectiChain paper, same lineage as #01 |
| #01 ReflectiChain: Mitigating Semantic-Execution Drift in Long-Horizon LLM | high | 2 | 5 | 4 | Drift metrics with explicit costs; negative transfer to code outside its home domain |
| #02 Thought Management System for long-horizon, goal-driven LLM agents | high | 2 | 5 | 2 | Task tree with a result validator; code placeholder and definitional inconsistencies |
| #07 Embodied Tree of Thoughts: Deliberate Manipulation Planning With Embod | high | 2 | 5 | 5 | Verifier overhead, parallel rollout and replanning, measured |
| #13 AI Agents vs. Agentic AI: A Conceptual taxonomy, applications and chal | medium | 2 | 4 | 4 | Taxonomy survey with multi-agent failure modes |
| #25 Advances in LLM-Assisted Combinatorial Optimization | high | 2 | 5 | 5 | Verification-guided synthesis loops and a verification ladder |
| #43 STAGE: LLM-Driven Semantic and Topological Augmented Graph Embedding f | medium | 2 | 5 | 5 | Bounded structural context under a fixed token budget |
| #05 Towards Communication Efficient Multi-Agent Cooperations: Reinforcemen | medium | 1 | 5 | 4 | Message-size cut in a robot simulation; a budget idea only |
| #09 Hierarchical process-level generative reward modeling with adaptive lo | high | 1 | 5 | 5 | Multi-verifier robustness bound and its correlation caveat; offline cost |
| #10 Agentic AI: The age of reasoning—A review | medium | 1 | 5 | 4 | Review of agentic AI patterns, memory and a four-stage framework |
| #11 HDDLGym: A Tool for Studying Multi-Agent Hierarchical Problems Defined | high | 1 | 5 | 2 | Explicit task effects; success falls as agents are added |

### Verification, grounding and checking

| Paper | Priority | Methods here | Costs | Neg. | Why |
|---|---|---:|---:|---:|---|
| #45 Pattern-Based Approach to the Automation of Deductive Verification of  | high | 7 | 1 | 3 | Requirement patterns with supporting invariants |
| #09 Hierarchical process-level generative reward modeling with adaptive lo | high | 6 | 5 | 5 | Multi-verifier robustness bound and its correlation caveat; offline cost |
| #04 Transforming Data Annotation with AI Agents: A Review of Architectures | medium | 3 | 5 | 5 | Survey of annotation agents; its cost savings are cited, not experiments |
| #13 AI Agents vs. Agentic AI: A Conceptual taxonomy, applications and chal | medium | 3 | 4 | 4 | Taxonomy survey with multi-agent failure modes |
| #25 Advances in LLM-Assisted Combinatorial Optimization | high | 3 | 5 | 5 | Verification-guided synthesis loops and a verification ladder |
| #26 A Formal Perspective for Service Coordination Framework in Service Ori | high | 3 | 2 | 0 | Trace invariants and refinement checks for coordination |
| #37 CoACL: Coupled Augmentation for Contrastive Learning on Text-Attribute | medium | 3 | 5 | 4 | Deterministic LLM inference settings for reproducible checks |
| #42 Mask-guided rationales meet LLMs: Hybrid encoder–LLM question answerin | high | 3 | 5 | 3 | Evidence sufficiency and faithfulness tests for rationales |
| #01 ReflectiChain: Mitigating Semantic-Execution Drift in Long-Horizon LLM | high | 2 | 5 | 4 | Drift metrics with explicit costs; negative transfer to code outside its home domain |
| #02 Thought Management System for long-horizon, goal-driven LLM agents | high | 2 | 5 | 2 | Task tree with a result validator; code placeholder and definitional inconsistencies |
| #05 Towards Communication Efficient Multi-Agent Cooperations: Reinforcemen | medium | 2 | 5 | 4 | Message-size cut in a robot simulation; a budget idea only |
| #07 Embodied Tree of Thoughts: Deliberate Manipulation Planning With Embod | high | 2 | 5 | 5 | Verifier overhead, parallel rollout and replanning, measured |

### Communication and evidence efficiency

| Paper | Priority | Methods here | Costs | Neg. | Why |
|---|---|---:|---:|---:|---|
| #06 Mutual Influence AI: Trust-Based Cooperation Mechanisms for LLM Multi- | medium | 3 | 5 | 4 | Trust-weighted cooperation and rounds-to-approval; effects not significant |
| #05 Towards Communication Efficient Multi-Agent Cooperations: Reinforcemen | medium | 2 | 5 | 4 | Message-size cut in a robot simulation; a budget idea only |
| #02 Thought Management System for long-horizon, goal-driven LLM agents | high | 1 | 5 | 2 | Task tree with a result validator; code placeholder and definitional inconsistencies |
| #08 Confidence-Aware Tree-of-Thoughts: A Federated Safety Net for VLM Agen | high | 1 | 5 | 4 | False-execution and false-refusal measures with a risk frontier |
| #10 Agentic AI: The age of reasoning—A review | medium | 1 | 5 | 4 | Review of agentic AI patterns, memory and a four-stage framework |
| #11 HDDLGym: A Tool for Studying Multi-Agent Hierarchical Problems Defined | high | 1 | 5 | 2 | Explicit task effects; success falls as agents are added |
| #13 AI Agents vs. Agentic AI: A Conceptual taxonomy, applications and chal | medium | 1 | 4 | 4 | Taxonomy survey with multi-agent failure modes |
| #16 AgentAI: A comprehensive survey on autonomous agents in distributed AI | medium | 1 | 3 | 2 | Survey of autonomous agents and their lifecycle |
| #19 Exploring How Knowledge Workers Situate an Organisationally Embedded L | medium | 1 | 5 | 5 | Human review and coordination effort in one organisation |
| #21 Transforming cybersecurity with agentic AI to combat emerging cyber th | medium | 1 | 4 | 3 | Agent security: least privilege, isolation, guardrails (survey) |
| #23 Q-RTS: a real-time swarm intelligence based on multi-agent Q-learning | low | 3 | 2 | 2 | Swarm Q-learning: a training method |
| #22 Improving multi-target cooperative tracking guidance for UAV swarms us | low | 2 | 3 | 2 | UAV tracking guidance: a physical system |

## All papers by reading priority

'Level' shows the primary reader and then the judge. Methods are anchor-verified items by category A/B/C/D/E.

### High priority

| # | Paper | Evidence | Level (reader / judge) | Methods A/B/C/D/E | Costs | Neg. | Why |
|---:|---|---|---|---|---:|---:|---|
| 1 | ReflectiChain: Mitigating Semantic-Execution Drift in Long-Horizon LLM Agen | benchmark | direct cand. / direct cand. | 3/1/2/0/2 | 5 | 4 | Drift metrics with explicit costs; negative transfer to code outside its home domain |
| 2 | Thought Management System for long-horizon, goal-driven LLM agents | benchmark | direct cand. / direct cand. | 1/2/2/1/2 | 5 | 2 | Task tree with a result validator; code placeholder and definitional inconsistencies |
| 3 | KNOWLEDGE-DRIVEN REASONING FOR MOBILE AGENTIC AI: CONCEPTS, APPROACHES, AND | case_study | bounded / bounded | 1/3/3/0/1 | 4 | 5 | Reusable knowledge packs with token costs; context utility not monotonic |
| 7 | Embodied Tree of Thoughts: Deliberate Manipulation Planning With Embodied W | benchmark | bounded / bounded | 0/2/2/0/2 | 5 | 5 | Verifier overhead, parallel rollout and replanning, measured |
| 8 | Confidence-Aware Tree-of-Thoughts: A Federated Safety Net for VLM Agents in | benchmark | direct cand. / direct cand. | 2/2/0/1/2 | 5 | 4 | False-execution and false-refusal measures with a risk frontier |
| 9 | Hierarchical process-level generative reward modeling with adaptive long-ho | benchmark | direct cand. / direct cand. | 0/0/1/0/6 | 5 | 5 | Multi-verifier robustness bound and its correlation caveat; offline cost |
| 11 | HDDLGym: A Tool for Studying Multi-Agent Hierarchical Problems Defined in H | tool_description | bounded / bounded | 1/4/1/1/1 | 5 | 2 | Explicit task effects; success falls as agents are added |
| 12 | ReflectiChain: Grounding Long-Horizon LLM Planning against Semantic-Executi | benchmark | direct cand. / direct cand. | 2/0/3/0/2 | 3 | 5 | Second ReflectiChain paper, same lineage as #01 |
| 14 | From LLM narratives to parameterized cooperation policies in multi-agent sy | simulation | bounded / bounded | 2/5/0/0/1 | 4 | 5 | Fixed-rule baseline matched the compiler; critic stress test |
| 25 | Advances in LLM-Assisted Combinatorial Optimization | survey_review | bounded / bounded | 0/3/2/0/3 | 5 | 5 | Verification-guided synthesis loops and a verification ladder |
| 26 | A Formal Perspective for Service Coordination Framework in Service Oriented | formal_proof | bounded / bounded | 0/3/1/0/3 | 2 | 0 | Trace invariants and refinement checks for coordination |
| 28 | Design of Flexible Static Program Analyzers with PQL | tool_description | bounded / bounded | 0/4/0/0/2 | 5 | 5 | Structural queries over code for automated checks |
| 42 | Mask-guided rationales meet LLMs: Hybrid encoder–LLM question answering fra | benchmark | bounded / bounded | 1/4/0/0/3 | 5 | 3 | Evidence sufficiency and faithfulness tests for rationales |
| 45 | Pattern-Based Approach to the Automation of Deductive Verification of Proce | formal_proof | bounded / bounded | 0/1/0/0/7 | 1 | 3 | Requirement patterns with supporting invariants |

### Medium priority

| # | Paper | Evidence | Level (reader / judge) | Methods A/B/C/D/E | Costs | Neg. | Why |
|---:|---|---|---|---|---:|---:|---|
| 4 | Transforming Data Annotation with AI Agents: A Review of Architectures, Rea | survey_review | bounded / bounded | 1/4/0/0/3 | 5 | 5 | Survey of annotation agents; its cost savings are cited, not experiments |
| 5 | Towards Communication Efficient Multi-Agent Cooperations: Reinforcement Lea | simulation | bounded / bounded | 0/2/1/2/2 | 5 | 4 | Message-size cut in a robot simulation; a budget idea only |
| 6 | Mutual Influence AI: Trust-Based Cooperation Mechanisms for LLM Multi-Agent | simulation | direct cand. / direct cand. | 1/3/0/3/0 | 5 | 4 | Trust-weighted cooperation and rounds-to-approval; effects not significant |
| 10 | Agentic AI: The age of reasoning—A review | survey_review | bounded / bounded | 0/3/1/1/2 | 5 | 4 | Review of agentic AI patterns, memory and a four-stage framework |
| 13 | AI Agents vs. Agentic AI: A Conceptual taxonomy, applications and challenge | survey_review | direct cand. / bounded | 0/0/2/1/3 | 4 | 4 | Taxonomy survey with multi-agent failure modes |
| 16 | AgentAI: A comprehensive survey on autonomous agents in distributed AI for  | survey_review | bounded / bounded | 0/2/0/1/0 | 3 | 2 | Survey of autonomous agents and their lifecycle |
| 18 | Industrial Agentic AI and generative modeling in complex systems | survey_review | bounded / bounded | 0/7/0/0/0 | 4 | 4 | Industrial agentic AI survey: ensembles and closed-loop control |
| 19 | Exploring How Knowledge Workers Situate an Organisationally Embedded LLM Ag | case_study | bounded / bounded | 0/4/1/1/2 | 5 | 5 | Human review and coordination effort in one organisation |
| 20 | Knowledge-Driven Reasoning for Compatible and Interpretable API Recommendat | benchmark | bounded / bounded | 0/1/0/0/2 | 5 | 5 | Human correction share of generated rationales |
| 21 | Transforming cybersecurity with agentic AI to combat emerging cyber threats | survey_review | bounded / bounded | 0/5/0/1/2 | 4 | 3 | Agent security: least privilege, isolation, guardrails (survey) |
| 32 | A knowledge-based approach for guided development of Infrastructure as Code | user_study | bounded / bounded | 0/5/0/0/2 | 5 | 4 | Ontology-backed validation of configuration code |
| 33 | LLM-S2KG: LLM-Based Semantic–Structural Dual Knowledge Graph | benchmark | bounded / bounded | 0/0/0/0/2 | 2 | 3 | Evidence-grounded relation validation (knowledge graphs) |
| 36 | Exploring Information Behavior with Hierarchical Goal Decomposition: The Ca | case_study | bounded / bounded | 0/2/1/0/0 | 3 | 2 | Hierarchical goal decomposition case study |
| 37 | CoACL: Coupled Augmentation for Contrastive Learning on Text-Attributed Gra | benchmark | bounded / bounded | 0/0/0/0/3 | 5 | 4 | Deterministic LLM inference settings for reproducible checks |
| 43 | STAGE: LLM-Driven Semantic and Topological Augmented Graph Embedding for Te | benchmark | bounded / bounded | 0/0/2/0/1 | 5 | 5 | Bounded structural context under a fixed token budget |
| 49 | Homo agenticus in the age of agentic AI: Agency loops, power displacement,  | position | bounded / bounded | 0/1/1/0/1 | 3 | 4 | Agency loops and path dependence (position paper) |

### Low priority

| # | Paper | Evidence | Level (reader / judge) | Methods A/B/C/D/E | Costs | Neg. | Why |
|---:|---|---|---|---|---:|---:|---|
| 15 | Multi-LLM Cooperation-Based Joint Intent-Driven Network Slicing and Resourc | simulation | bounded / bounded | 1/5/0/0/0 | 3 | 3 | Network slicing with LLMs: domain-specific |
| 17 | Efficient Cooperation-Aware Key and Value Management for LLM Inference | benchmark | bounded / bounded | 2/0/3/0/2 | 5 | 4 | Attention-head cache management: needs model internals that API routes do not expose |
| 22 | Improving multi-target cooperative tracking guidance for UAV swarms using m | simulation | bounded / bounded | 2/2/0/2/0 | 3 | 2 | UAV tracking guidance: a physical system |
| 23 | Q-RTS: a real-time swarm intelligence based on multi-agent Q-learning | simulation | bounded / bounded | 0/0/0/3/0 | 2 | 2 | Swarm Q-learning: a training method |
| 24 | Evolutionary Multi-Agent Deep Meta Reinforcement Learning Method for Swarm  | simulation | bounded / bounded | 1/3/0/1/0 | 4 | 5 | Meta reinforcement learning: a training method |
| 27 | Data-And Knowledge-Driven Visual Abductive Reasoning | benchmark | bounded / bounded | 0/0/0/0/0 | 4 | 5 | Visual abductive reasoning: vision models |
| 29 | Integrating Q-Learning with Branch and Bound for the Job Shop Scheduling Pr | benchmark | bounded / bounded | 1/5/1/0/1 | 4 | 1 | Q-learning for job-shop search: an RL method |
| 30 | "Who's Doing the Thinking Here?": A Pedagogy-First Approach to Integrating  | position | bounded / bounded | 0/5/0/0/1 | 0 | 2 | Pedagogy for human learners using LLMs |
| 31 | Leveraging Large Language Models for Node Generation in Few-Shot Learning o | benchmark | bounded / out | 0/3/0/0/0 | 5 | 3 | Few-shot node classification with LLM-generated exemplars |
| 34 | Directed drift: An efficient and stealthy bias injection method using seman | benchmark | out / out | 0/0/0/0/2 | 5 | 4 | Attack on diffusion models: a keyword trap |
| 35 | Double deep Q-network based multi-objective optimization for flexible job s | simulation | bounded / bounded | 1/1/0/0/0 | 5 | 4 | Deep Q-network operator selection: an RL method |
| 38 | G2LoRA: Gradient Orthogonal Low-Rank Adaptation Framework for Graph Continu | benchmark | bounded / bounded | 1/1/3/0/1 | 5 | 5 | Low-rank adaptation training method |
| 39 | Hierarchical goals contextualize local reward decomposition explanations | simulation | bounded / bounded | 0/2/1/0/2 | 1 | 4 | Goal-conditioned reward decomposition for explanations |
| 40 | Hierarchical reinforcement learning for dynamic collision avoidance of auto | simulation | bounded / bounded | 3/2/0/0/0 | 4 | 4 | Hierarchical RL for collision avoidance: a physical system |
| 41 | KLDA-TICNet: Transposition interaction convolutional network for ship traje | benchmark | bounded / bounded | 0/0/0/0/0 | 4 | 3 | Trajectory prediction network |
| 44 | Multiscale Contrastive Learning for Node Clustering Based on Variational Gr | benchmark | out / out | 0/0/0/0/0 | 5 | 4 | Contrastive node clustering: graph ML |
| 46 | Semantic Drift Compensation for Class-Incremental Learning | benchmark | bounded / bounded | 1/0/2/0/0 | 4 | 4 | Semantic drift in class-incremental learning: a keyword trap |
| 47 | Uncertainty-aware cloud resource management via fuzzy-adaptive hierarchical | simulation | bounded / bounded | 1/3/1/0/0 | 5 | 4 | Fuzzy hierarchical cloud resource management |
| 48 | VIKSER: Visual Knowledge-Driven Self-Reinforcing Reasoning Framework | benchmark | bounded / bounded | 0/2/1/0/2 | 5 | 4 | Visual knowledge reasoning framework |
| 50 | Verification and process oriented validation of the MiKlip decadal predicti | survey_review | out / out | 2/0/0/0/3 | 0 | 1 | Meteorological forecast verification: a keyword trap |

## Papers the first pass scored zero that deserve a reading

| # | Paper | First pass | Priority | Mechanism the judge names | Verified methods (A/B/C/D/E) |
|---:|---|---|---|---|---|
| 28 | Design of Flexible Static Program Analyzers with PQL | 0/0/0/0 | high | PQL query language; Abstract PKB interface and generic SPA generation | 0/4/0/0/2 |
| 32 | A knowledge-based approach for guided development of Infrastructure as | 0/0/0/0 | medium | Model validation; Smell detection; Layered SODALITE ontology | 0/5/0/0/2 |
| 33 | LLM-S2KG: LLM-Based Semantic–Structural Dual Knowledge Graph | 0/0/0/0 | medium | Relationship completion and validation; Dual graph fusion | 0/0/0/0/2 |
| 36 | Exploring Information Behavior with Hierarchical Goal Decomposition: T | 0/0/0/0 | medium | Hierarchical Goal Decomposition; Expert-novice model gap analysis | 0/2/1/0/0 |
| 37 | CoACL: Coupled Augmentation for Contrastive Learning on Text-Attribute | 0/0/0/0 | medium | LLM semantic noise correction; Deterministic LLM inference | 0/0/0/0/3 |
| 42 | Mask-guided rationales meet LLMs: Hybrid encoder–LLM question answerin | 0/0/0/0 | high | Selective QA gating and cascaded deployment; Distilled Ex-HateQA-Student deployment | 1/4/0/0/3 |
| 43 | STAGE: LLM-Driven Semantic and Topological Augmented Graph Embedding f | 0/0/0/0 | medium | Graph-conditioned token selection; Bounded-input property | 0/0/2/0/1 |
| 45 | Pattern-Based Approach to the Automation of Deductive Verification of  | 0/0/0/0 | high | Basic and derived requirement patterns; Universal verification-condition proof schemes | 0/1/0/0/7 |
| 49 | Homo agenticus in the age of agentic AI: Agency loops, power displacem | 0/0/0/0 | medium | Agency loop intervention points; Loop memory and path dependence | 0/1/1/0/1 |

## Vault notes on agent topics (adjacent prior art; unchanged from the first pass)

These notes were written on 2026-09-19 from the model's general familiarity with the papers, not from a PDF the vault holds (stated in `Paper Index.md`). They are **secondary sources**: useful for orientation, not citable for section-level claims. The primary Reflexion and Tree of Thoughts papers should be read for the claims that matter; this pass did not retrieve them.

| Rank | Note | A | B | C | D | Score | Why |
|---:|---|:-:|:-:|:-:|:-:|---:|---|
| 1 | shinn-2023-reflexion-language-agents-with-verbal-reinforceme | 2 | 2 | 3 | 0 | 16.0 | Verbal self-reflection stored in episodic memory for retries; pass@1 accuracy reported, no cost or message-efficiency measures. |
| 2 | wang-2023-voyager-an-open-ended-embodied-agent-with | 2 | 3 | 3 | 0 | 15.5 | Lifelong skill library plus curriculum and self-verification; measured item/milestone gains, but no cost or inter-agent communication metrics. |
| 3 | yao-2022-react-synergizing-reasoning-and-acting-in | 1 | 3 | 2 | 0 | 15.0 | Interleaved thought/action loop is a core agent architecture; reports success rates but no cost or reliability metrics. |
| 4 | hayes-roth-1985-a-blackboard-architecture-for-control | 0 | 3 | 1 | 2 | 13.5 | Blackboard architecture: shared workspace plus separate control component for agent coordination; structural alternative to fixed pipelines. |
| 5 | kinny-1996-a-methodology-and-modelling-technique-for | 0 | 3 | 2 | 0 | 12.5 | BDI design methodology specifying agent roles, goals, plans before implementation; relevant to agent schemas and roles. |
| 6 | yao-2023-tree-of-thoughts-deliberate-problem-solving | 2 | 2 | 2 | 0 | 11.5 | Search over reasoning paths with backtracking; reports success rates and a cost-vs-accuracy tradeoff, but single-agent only. |
| 7 | aalst-2003-workflow-patterns | 0 | 3 | 0 | 0 | 10.5 | Catalogue of workflow control-flow patterns; directly relevant to workflow specification schemas for agent tasks. |
| 8 | erol-1995-complexity-decidability-and-undecidability-results | 0 | 1 | 2 | 0 | 8.5 | Complexity results on HTN decomposition depth bounds; tangential to plan-execution limits, no agent orchestration. |
| 9 | kaelbling-1998-planning-and-acting-in-partially-observable | 0 | 1 | 2 | 0 | 8.5 | POMDP formalism for acting under uncertainty; tangential to long-horizon planning, no agent orchestration or metrics. |
| 10 | mellafe-zuvic-2026-capability-gates-are-not-authorization | 1 | 2 | 0 | 0 | 8.5 | Per-call authorization architecture for tool-using agents; reports unauthorized-attempt rates, but no orchestration metrics, planning, or message effi |
| 11 | muruaga-2026-bounded-agents-delegation-security | 1 | 2 | 0 | 0 | 8.5 | Formal delegation-authority model for orchestrator/sub-agent chains; utility and latency numbers, but no planning drift or message-efficiency contribu |
| 12 | nau-2003-shop2-an-htn-planning-system | 0 | 2 | 1 | 0 | 8.5 | HTN planning system for decomposition-then-execution workflows; relevant to workflow specification, not agent metrics. |
| 13 | sutton-1999-between-mdps-and-semi-mdps-a-framework | 0 | 2 | 1 | 0 | 8.5 | Options framework as learned hierarchical decomposition; relevant to task decomposition schemas, not agent orchestration. |
| 14 | wang-2026-agentspec-customizable-runtime-enforcement | 1 | 2 | 0 | 0 | 8.5 | Runtime rule language and enforcement strategies for agent tool calls; overhead measured, but no orchestration metrics, long-horizon planning, or agen |
| 15 | grand-2023-lilo-learning-interpretable-libraries-by-compress | 0 | 1 | 1 | 0 | 5.5 | LLM-guided abstraction library with auto-documentation; adjacent to reusable agent tooling, but no orchestration, cost metrics, or inter-agent communi |
| 16 | ellis-2020-dreamcoder-growing-generalizable-interpretable-kn | 0 | 1 | 1 | 0 | 3.5 | Program-synthesis library learning; reusable primitives resemble tool/abstraction interfaces, but no agent orchestration, metrics, or multi-agent comm |
| 17 | sweller-1988-cognitive-load-during-problem-solving-effects | 0 | 1 | 1 | 0 | 2.0 | Human cognitive load theory; only analogical bearing on task decomposition and context load for agents. |
| 18 | fowler-2011-cqrs | 0 | 1 | 0 | 0 | 1.0 | Architectural pattern essay on read/write model separation; no agent orchestration, metrics, or long-horizon content. |
| 19 | kleppmann-and-beresford-2017-a-conflict-free-replicated-json | 0 | 0 | 0 | 1 | 1.0 | Formal CRDT merge for concurrent replicas; shared-state convergence is adjacent to multi-agent shared state but not about agents. |
| 20 | kleppmann-et-al-2019-local-first-software | 0 | 0 | 0 | 1 | 1.0 | Local-first architecture essay; CRDT collaboration is multi-writer convergence, not agent message or token efficiency. |
| 21 | skelton-pais-2019-team-topologies | 0 | 1 | 0 | 0 | 1.0 | Organisational team-topology practice for human teams; only loose analogy to agent role decomposition, no agent metrics or protocols. |
| 22 | dennis-1966-programming-semantics-for-multiprogrammed-comput | 0 | 0 | 0 | 0 | -3.0 | Capability-based addressing design paper; security abstraction for OS resources, not agent deployment, planning, or communication. |
| 23 | hoare-1969-an-axiomatic-basis-for-computer-programming | 0 | 0 | 0 | 0 | -3.0 | Foundational program-verification logic; unrelated to agent orchestration, metrics, memory, or inter-agent communication. |
| 24 | parasuraman-sheridan-wickens-2000-a-model-for-types-and-leve | 0 | 0 | 0 | 0 | -3.0 | Human-automation interaction framework from aviation; unrelated to agent orchestration, metrics, planning, or multi-agent communication. |
| 25 | save-2014-not-all-or-nothing-not-all-the-same-classifying-au | 0 | 0 | 0 | 0 | -3.0 | EUROCONTROL practitioner piece on aviation automation levels; no bearing on agent orchestration, metrics, planning, or inter-agent communication. |
| 26 | wallace-2024-the-instruction-hierarchy-training-llms-to | 0 | 0 | 0 | 0 | -3.0 | Prompt-injection robustness training; no agent orchestration, planning, memory, or inter-agent communication content. |
