# Eight newly added papers: verified reading list

Reviewed 2026-10-30 against local PDFs, with physical PDF page numbers below. The folder now contains 59 PDFs: the original 51 plus eight new hashes. Gemini discussed seven; the additional staged-fact-scoring paper is also covered here. Sources, extraction hashes and normalization are in [the manifest](data/new-source-manifest.json). Evidence strength is graded for transfer to Librarian's own runtime, not solely by venue.

## 1. Retry safety — highest immediate engineering value

**WASABI: If At First You Don't Succeed, Try, Try, Again...?** Stoica et al., SOSP 2024. [Local PDF](E:/Librarian%20research/3694715.3695971.pdf); [author copy](https://bastoica.github.io/files/papers/2024_sosp_wasabi.pdf).

The study analyzes 70 retry issues and distinguishes IF, WHEN and HOW failures. Its 45% non-loop figure concerns sampled **issues**, not all retries in production (pp.2–5). The tool reports 109 previously unknown bugs: 42 from testing plus 87 static findings, with 20 overlapping (p.2); findings still required manual adjudication. K=1 probes post-retry cleanup, while K=100 probes caps/delays in its Java systems (pp.7–8). Neither 100 attempts nor a 15-minute oracle timeout is an appropriate universal Librarian default.

Transfer: inventory retries across provider transport, Clerk jobs, workflow resume and round transitions; test one transient failure, repeated failure, cancellation, non-retryable refusal, partial effects and stale worker identity. Use virtual time and configured limits. The paper does not prove any present Librarian bug; it supplies a testing method. Code analysis should use bounded functions plus call-graph context: its large-file miss rates are not an optimal prompt-size threshold.

## 2. Runtime privilege mediation — useful bounded model, limited security evidence

**MCP-Secure: A Runtime Access Control Layer for Privilege-Aware LLM Agent Tooling.** Singh and Madisetti, IEEE OJCS 2026. [Local PDF](E:/Librarian%20research/A%20Runtime%20Access%20Control%20Layer%20for%20Privilege-Aware%20LLM%20Agent%20Tooling.pdf), DOI 10.1109/OJCS.2026.3664314.

The host-side wrapper checks scope and effects before calls; approval allows temporary elevation (pp.3–5). This mechanism can inform Librarian's Registry/broker even though the paper uses MCP. It does **not** require changing Claude/Codex's tools. The paper supplies no universal elevation duration or grain-completion revocation rule.

The 1,080 executions cover two repository tasks, three models, three attack simulations, four enforcement levels and 15 repeats (p.6). Its approver is an internal probabilistic policy; this does not measure human approval friction. Static metadata, single-agent isolation and limited adversarial testing are explicit limitations (p.9). Do not transfer the block rate as a Librarian security guarantee.

Useful metrics: required steps completed / required steps total (p.7), and allowed benign calls / all attempted calls (p.8). Predeclare required steps and benign labels independently; report refusals and useful outcomes alongside them. For dynamic research plans use predicate-level progress rather than a model-invented step denominator. Denied writes must be visibly denied, not silently converted to apparent successful no-ops.

## 3. Tool schemas and correction — near-term interface value

**eidos: A modular approach to external function integration in LLMs.** Aldana-Martín et al., SoftwareX 2025, DOI 10.1016/j.softx.2025.102290. [Local PDF](E:/Librarian%20research/A%20modular%20approach%20to%20external%20function%20integration%20in%20LLMs.pdf).

The architecture separates validation from execution, with declarative types/options/regex and soft coercion followed by structured rejection (pp.2–3). Figure 2 on physical p.4 **does show a function/argument card with Give permission and Cancel**. The wording differs from Gemini's Continue/Cancel, but its broad confirmation-card observation is supported visually. An extraction-only reader incorrectly denied this feature; that suggestion was rejected after rendering the page.

This is a software/illustration paper, not a controlled security or performance comparison. Librarian already implements coercion, enum normalization, reference resolution, explicit unknown-argument rejection and write-intent checks. Incremental transfer: structured error fields, stable predicate IDs, deterministic skeletons and round-trip validation tests. Formatting repair must not reinterpret a path, choose a new source, override a conflict or widen authority. No need to replace Registry with a second validation framework.

## 4. Semantic conflict detection — experimental Tier B, never a truth oracle

**DEMUC: Detecting Misinformation by Uncovering Commonsense Conflicts With LLM Workflows.** Wang et al., IEEE TKDE 2026. [Local PDF](E:/Librarian%20research/Detecting%20Misinformation%20by%20Uncovering%20Commonsense%20Conflicts%20With%20LLM%20Workflows.pdf).

The quoted 58%/51% conflict-identification and 78%/73% extraction results appear on pp.3–4. They concern selected models and a specific commonsense/news setting; the extraction analysis uses 200 manually judged samples. They do not prove all small models fail at verification or that decomposition solves Librarian synthesis correctness.

The method extracts triples, generates an expected object from a subject/relation without the full article, and uses conflict expressions to augment a trained misinformation classifier (pp.5–9). Its “golden” object is generated knowledge, not independently verified truth. Source-isolated verification against Librarian evidence would be a **new adaptation**, not the evaluated method. Six relations per prompt and epsilon 0.8 are experimental settings, not portable limits; full scoring also needs suitable likelihood/log-probability support.

Transfer: evaluate a read-only checker that records draft proposition, independently retrieved source passage, relation/polarity/time/units, possible contradiction and uncertainty. Include support, contradiction and insufficient-evidence labels. Preserve negatives, model cost and latency. Never upgrade `quote.located` to semantic entailment or let an LLM reviewer grant authoritative closure.

## 5. Human-approved corpus screening — useful workflow with narrow validation

**A Hybrid Delphi-Inspired Expert–LLM Workflow for Efficient Evidence Screening in Systematic Reviews.** Pournik et al., 2026. [Local PDF](E:/Librarian%20research/Expert-LLM%20Workflow%20for%20Efficient%20Evidence%20Screening%20in%20Systematic%20Reviews.pdf).

The workflow proposes exclusion clues, obtains expert consensus, locks rules and labels INCLUDE/EXCLUDE/MAYBE with explanations (pp.2–3). It processed 14,858 thyroid-related records. The 96% agreement and kappa 0.91 derive from **100 randomly sampled records**, independently reviewed by two people—not all 14,858. The reported one false exclusion is in that sample. The paper reports 13,890 exclusions and 1.7 hours, and about 70% manual-time reduction, with a single-domain/generalization caveat (pp.3–5). Rendering p.3 confirmed values obscured by text-font encoding.

Transfer: model-assisted intake screening can propose rules for a person to approve, then retain reversible labels, reasons and an uncertainty queue. Audit exclusions, including a random control sample to detect confident systematic mistakes. Do not let inferred exclusion clues alter filesystem access policy or delete sources. Keep the deterministic directory survey read-only; attach model proposals as a separate optional screening stage.

## 6. Active selection for human review — useful experiment, not deduplication proof

**APE: Active Learning-based Tooling for Finding Informative Few-shot Examples for LLM-based Entity Matching.** Qian et al., DaSH/ACL 2024. [Official paper](https://aclanthology.org/2024.dash-1.1/); [local PDF](E:/Librarian%20research/Examples%20for%20LLM-based%20Entity%20Matching.pdf).

This three-page demo uses repeated predictions, temperature variation and binary-label entropy to select ambiguous matching pairs for annotation (p.3). The three temperatures 0/0.5/1 are example/demo settings; quantitative evaluation is deferred. One model sampled repeatedly is not an independent committee and disagreement is not calibrated error probability.

Transfer: prioritize ambiguous lens/golden-example or possible-duplicate candidates for human review while retaining random sampling. Measure labeling efficiency against a baseline. The paper supplies neither an LSH implementation nor authority to merge notes; Gemini's “DEPLOY-04 Layer 5” is a proposed extension, not a current implemented dedupe layer. Keep identity and merge decisions independent of label entropy.

## 7. Staged triple scoring — additional paper Gemini did not cover

**LLMs in Staging: An Orchestrated LLM Workflow for Structured Augmentation with Fact Scoring.** Trimigno et al., Future Internet 2025, 17, 535. [Local PDF](E:/Librarian%20research/An%20Orchestrated%20LLM%20Workflow%20for%20Structured%20Augmentation%20with%20Fact%20Scoring.pdf), DOI 10.3390/fi17120535.

The pipeline combines extraction, attention-based scoring and downstream performance tasks (pp.5–13). DeBERTa-v3 attention is a relevance/salience proxy; the authors explicitly distinguish it from formal factual grounding (p.16). Some model/task combinations regress (p.13). Despite its title, it does not validate factual truth or demonstrate a replacement for Librarian's staging/promotion rules.

Transfer: structured intermediate records and stage-specific evaluation are useful. The attention scorer requires access to encoder internals, unavailable through ordinary hosted chat APIs. Consider it only as an optional local salience experiment with measured benefit over retrieval/baselines. It is not a necessary runtime subsystem or zero-cost verification method.

## 8. InfraMLForge — retain in inventory; do not use as empirical design authority

**InfraMLForge: Developer Tooling for Rapid LLM Development and Scalable Deployment.** Zhang, Research Square preprint v1, June 2025. [Local PDF](E:/Librarian%20research/Developer%20Tooling%20for%20Rapid%20LLM%20Development%20and%20Scalable%20Deployment.pdf), DOI 10.21203/rs.3.rs-6793970/v1.

Table I and methodology compare NLP tasks with tool/robotics baselines without a reproducible adapter/evaluation account, and model naming is inconsistent between the setup and table (p.4). Figures 1–3 do not supply the missing protocol (pp.3,5). Those concerns suffice for low evidential weight. A reader's claimed arithmetic anomalies were ordinary rounding, and were rejected. Gemini's accusation that the diagram is an unattributed reproduction was **not verified**; this review makes no misconduct claim.

Generic dataset versioning/resource limits are already supported by stronger sources and repository contracts. No necessary new harness requirement depends on this paper.

## Reading order and adoption boundary

Read WASABI and eidos first for engineering tests/interfaces; MCP-Secure for mediation and utility metrics with its limitations; DEMUC for a carefully bounded Tier-B experiment. Delphi and APE inform optional human-review workflows. The staging paper is optional local-model research. InfraMLForge remains catalogued but does not justify implementation.

All transfers above are proposals requiring Librarian-specific acceptance tests. The papers do not establish that adding more agents, always-on self-reflection, fixed confidence cutoffs, or a taint graph improves this product.
