## Assessment of Gemini’s final response (correctness lens)

**Scope and evidence limits.** I assessed only the four exported papers and Gemini’s two responses. I did not inspect the harness code, commit `a9be71b`, or the other 47 corpus papers. Claims about code behavior are therefore unverified here. The eidos packet is export-redacted: one credential-like example line was removed, so I cannot assess that listing. The Delphi text is partly garbled by encoding, so some values are uncertain.

### eidos (Aldana-Martín et al., 2025)

**Gemini is broadly right, with one overreach.** The paper does describe a validation/execution split (p.2, §2.1), declarative JSON metadata with `type`, `options`, and `regex` (p.2, Listing 2), and a multi-tiered fallback: soft validation/coercion, then retries/correction, then fail-safe rejection with a structured error trace (p.3, §2.2). Inputs and outputs are validated after execution (p.3, §3).

**Overreach:** Gemini says eidos has a “UI confirmation card showing the exact function and arguments (Continue / Cancel).” The paper does not describe that. Fig. 2 (p.4) shows a chatbot debug view of function calls and parameters, not a confirmation dialog. Treat the Continue/Cancel card as Gemini’s inference, not a paper claim.

**Evidence limits:** This is a software-architecture paper. It reports no controlled evaluation, no accuracy or latency metrics, and no comparison against baselines beyond Table 1’s feature checklist (p.2). “Guarantees” (p.3) is the authors’ design claim, not measured evidence. The GIS example is illustrative (pp.3–4).

### APE (Qian et al., 2024)

**Gemini’s QBC description is accurate.** For each entity pair, the same prompt runs *m* times, with *m*=3 in the demo, at temperatures 0, 0.5, and 1.0 (p.3). It computes label-distribution entropy H(p) = −R₊logR₊ − (1−R₊)log(1−R₊), where R₊ is the positive-label ratio, and selects the top-*k* highest-entropy pairs for annotation (p.3). Temperature is zero during evaluation (p.3). Incremental and fixed sampling modes are both offered (p.3).

**Unsupported:** Gemini’s application to “document_identity.py (DEPLOY-04 Layer 5 near-duplicate LSH candidates)” is not supported by APE. The paper covers entity matching on DBLP-Scholar (p.2) and mentions no LSH, near-duplicate detection, or merging. That transfer is Gemini’s own design idea and should be labeled as such.

**Evidence limits:** This is a demo paper. It reports no quantitative results and defers evaluation to future work (p.3, §3). The temperatures and *m*=3 are demo settings, not validated defaults.

### Delphi (Pournik et al., 2026)

**Sample size:** Validation used 100 randomly selected records, independently screened by two blinded human reviewers (p.3, §2). The 14,858 records are the full screening corpus, not the validation sample.

**Uncertain values:** The abstract and results render as “96% concordance” and “κ = 0.91” (pp.1, 3, 4), but the κ glyph is garbled in the packet. Treat κ=0.91 as probable but unconfirmed. The 70% time reduction (p.1) and 93% exclusion, 13,890/14,858, in 1.7 hours (p.3) are legible.

**False-exclusion wording:** Gemini’s “only one false exclusion” is consistent with the paper: one abstract (1%) was wrongly excluded, and that study had been labeled “maybe” by a human and judged borderline (p.3). However, the paper also says two “include”-labeled records were later excluded at full-text screening (p.3). Gemini omits that. The paper’s “near-perfect agreement” and “safely automate” language (pp.3–4) is stronger than a 100-record, single-domain validation supports.

**Domain limits:** The authors state the approach was tested in a single clinical domain with one model version and needs cross-topic and cross-model validation (p.4, §4; p.5). Gemini’s “Moderate-High” grade is defensible only if those limits are stated.

### InfraMLForge (Zhang, 2025)

**Internally verifiable anomalies:**
- Table I (p.4) scores “Non-Prehensile Tool Manipulation” and “Budget-Constrained Tool Learning” on EPIE, CLIMATE-FEVER, SkillSpan, and NLPeer. These are NLP datasets, and the cited works are robotics/tool-planning papers (refs [23], [24], p.6). The paper gives no method for how those systems were run on these datasets.
- Table I lists “InfraMLForge GPT-4o” and “Llama-3-13b” as if they were methods, while §IV-C says GPT-4 (`gpt-4-turbo-2024-04-09`) was used (p.4). The model naming is inconsistent.
- The “Overall Avg.” column is not the arithmetic mean of the four dataset columns for several rows. For example, GPT-4o’s four values average 85.45, not 85.5; PLATO’s average 82.525, not 82.5. These are minor, but the column is undefined.
- §V-B reports PLATO training at 4.8 h and deployment at 1.2 min (p.5), while §V-C reports auto-scaling training at 6.5 h and deployment at 1.5 h (p.6). The units and baselines differ, and the paper does not reconcile them.
- The equations (1)–(6) are generic notation with no implementation or results tied to them (pp.3–4).

**Do not allege plagiarism or misconduct.** Gemini’s claim that Fig. 1 is an “unattributed reproduction” cannot be verified from the packet; the figure is only referenced (p.3). The benchmark anomalies justify excluding the paper as design authority, not accusing the author of misconduct. Gemini’s “Exclude / Low” disposition is reasonable; its plagiarism framing is not supported by the exported text.

### Bounded transfers for Librarian’s own workflow

- **Intake/triage (Delphi):** Use a three-valued INCLUDE/EXCLUDE/MAYBE pass with short justifications, route MAYBE to staging, and require one human approval of exclusion rules before bulk runs. Validate on a random sample with two blinded reviewers, and report the sample size and κ alongside raw counts. Do not adopt 96%/κ=0.91/70% as defaults.
- **Test authoring (APE):** For ambiguous pairs, run the same prompt at 0/0.5/1.0, compute binary entropy, and send top-*k* to human labeling. Keep temperature at 0 for evaluation. Treat *m*=3 and the temperature sweep as demo settings to re-tune.
- **Tool validation (eidos):** Adopt declarative schemas plus soft coercion before rejection, and return structured error traces. Do not claim a confirmation UI from this paper.
- **InfraMLForge:** Use only as a cautionary example of benchmark hygiene: check that baselines are applicable to the datasets, that model names are consistent, and that aggregate columns are defined.

**Deterministic tests for the integrator:**
1. Recompute Table I row means and flag mismatches.
2. Assert that every baseline cited in Table I has a stated evaluation protocol on each dataset.
3. Check that Delphi’s reported κ and concordance are reproduced from the 100-record sample, not the 14,858 corpus.
4. Verify that any APE-derived selector uses temperature 0 at evaluation and logs *m* and *t* values.
5. Confirm that eidos-derived validation tests cover coercion, retry, and structured rejection paths.