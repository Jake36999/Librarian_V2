## Verdict

Gemini's DEMUC summary is **substantially accurate on the numbers and the workflow shape**, but it **overstates what was trained/classified and blurs three distinct things**: (a) factual truth, (b) attention salience, (c) commonsense-model beliefs. It also imports DEMUC's `ε=0.8` and "≈6 relations" as if they were transferable defaults; the paper presents them as dataset-tuned hyperparameters.

## DEMUC (new-05.txt) — claim-by-claim

**58%/51% and 78%/73% — confirmed, with scope caveats.**
- Direct conflict identification: Qwen 58%, DeepSeek 51% (p.3, §II-B). Direct veracity: 67%/52% (p.3, §II-A).
- Element extraction: Qwen 78%, DeepSeek 73% (p.4, §II-C, Fig. 2).
- **Scope limits Gemini omits:** all four numbers are on **CoMis only** (1,580 Chinese articles, ~50 words, fake:real 1.3:1; p.8, Table V). Extraction figures come from **200 hand-scored samples** (100 real / 100 fake) with **manual** success criteria (p.3–4). These are not held-out benchmark accuracies and not English-generalizable.

**"Source-isolated entailment checks" — mislabeled.** DEMUC does **not** do entailment. It does: extract `(s,r,o)` from the article → query a commonsense generator `GΠ(s,r)` **without the article** → compare `o` vs `ô` via a BARTScore-style token log-likelihood conflict score `c` (p.5, Eq. 6; p.7, Eq. 7). The "isolation" is real (the oracle sees only `(s,r)`), but the comparison is a **generative likelihood gap against a commonsense KB**, not NLI/entailment. Calling it "entailment" would let a downstream harness claim a stronger guarantee than the paper supports.

**Six-relation batch — confirmed but conditional.** "Simultaneous inference for approximately six relations" is stated as empirically optimal *for DEMUC-LLM*; more relations "may lead the LLM to extract inaccurate or meaningless triplets" (p.7, fn. 1). It is a **prompt-batching heuristic for one 7B model on one dataset**, not a universal cap.

**ε = 0.8 — confirmed, but it is a perplexity filter, not a conflict threshold.** `ε` filters extracted triplets by mean token NLL (p.7, §III-C); sensitivity peaks at 0.8 on GossipCop (p.11, Fig. 4). The **conflict** threshold is a separate `μ = 0.6` (p.9, §V-A). Gemini conflates the two roles and presents 0.8 as if portable.

**Effectiveness — confirmed but bounded.** Plug-in gains across five MD backbones, five runs, p<0.05 (p.9–10, Tables VIII–IX); e.g. +1.91 macro-F1 on Weibo over CED. **But:** (i) the ablation shows the *conjunction word* ("However") is the strongest single cue — "MD systems can efficiently identify patterns linking conjunctions with veracity labels" (p.9, §V-C). That is a **label-leakage-shaped shortcut**, not commonsense reasoning. (ii) `ô` is treated as "ground-truth knowledge" by assumption (p.7, §III-D) — COMET/LLM outputs are **commonsense model beliefs**, not verified facts. (iii) CoMis is Chinese; English transfer is untested.

## LLMs in Staging (new-04.txt) — what is actually trained/classified

- **Extractor:** Stanza constituency parse + deterministic tree-walker; no grammar checks, no training (p.5–6, §3.1).
- **Scorer:** **DeBERTa-v3, frozen, training-free**; score = max-pooled self-attention over `(s,p,o)` spans, layer/head max, log-length normalization, six pairwise directions collapsed to two max terms (p.8–9, Eqs. 4–8). This is **attention salience**, explicitly *not* factual truth: "attention weights do not directly measure causality… an approximation rather than a formal measure of factual grounding" (p.16, §6.1).
- **Performer:** the only component trained (encoder/encoder-decoder fine-tuned) or zero-shot (Qwen2.5) (p.10, §3.3; p.13, Table 3).
- **What is classified:** downstream MCQA/QA/summarization labels — **not** factuality. Gains are metric deltas (accuracy, BLEURT, ROUGE), with **regressions** for Qwen2.5-7B on RACE (−1.87%), MCTest (−0.32%), QuALITY (−3.82%) (p.13, Table 4). Gemini's earlier "High" evidence grade for DEMUC and its silence on these regressions are both over-generous.

## What requires local attention access

Only the Staging scorer. It needs **raw self-attention tensors** from a bidirectional encoder (p.8, §3.2.1–3.2.2). Any Tier-B experiment that reuses this scoring must run the encoder locally and expose per-layer/head attention; a hosted chat API cannot supply it. DEMUC's workflow, by contrast, needs only text-in/text-out plus token log-probabilities (for `ε` and `c`) — cheaper, but still requires logprob access for the perplexity filter.

## Three things to keep separate

1. **Factual truth** — neither paper establishes it. Staging measures task metrics; DEMUC measures conflict against a KB.
2. **Attention salience** — Staging's `σ(t)`; a relevance proxy, author-acknowledged as non-causal.
3. **Commonsense model beliefs** — DEMUC's `ô` from COMET/Qwen; assumed golden, unverified.

## Bounded read-only Librarian Tier B experiments (suggested)

All read-only, no authoritative LLM closure, no universal thresholds:

- **B1 (DEMUC-shape, no entailment claim):** on a fixed 50-doc sample, extract `(s,r,o)`, query oracle on `(s,r)` only, record `o` vs `ô` and `c`. Report agreement with human labels; do **not** gate closure on it.
- **B2 (batch-size sweep):** vary relations-per-prompt ∈ {1,3,6,12}; measure extraction precision on the same sample. Treat 6 as a hypothesis, not a default.
- **B3 (ε/μ sweep):** sweep `ε` and `μ` independently; report precision/recall curves. Do not fix 0.8/0.6 globally.
- **B4 (conjunction ablation):** strip "However"/"And" from expressions and re-measure any downstream classifier — this directly tests the shortcut Gemini missed.
- **B5 (Staging salience, local only):** if a local DeBERTa is available, compute `σ(t)` and correlate with human salience ratings; report as salience, never as truth.
- **B6 (regression watch):** any adoption must log per-model deltas including negatives (Qwen-7B pattern).

## Risks

- Gemini's "High — solves context-persuasion in Tier-B auditing" overclaims: DEMUC's own ablation suggests the gain may be a lexical cue.
- "Entailment" framing would license closure claims the evidence cannot bear.
- Porting `ε=0.8`/six-relation batching as defaults risks silent quality loss on other corpora/languages.

**Assumptions:** Gemini's quoted figures refer to new-05.txt §II; "source-isolated entailment" is my reading of its phrasing, not a paper term. **Not run:** no commands or tests executed.