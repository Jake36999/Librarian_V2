# External claims and scope corrections

Checked 28 October 2026. The original register mixes company statements, model capabilities, local observations and proposed workflows. `data/claim_review.csv` gives a row-level second-pass disposition for all **58 entries currently classified as genuinely outside claims**. Historical local workflow assertions are reclassified as local reported evidence where appropriate; they are not turned into verified facts simply because a transcript repeats them.

The statuses below distinguish **verified as stated**, **partly supported**, **scope correction**, **plausible**, and **unverified**. “Verified” means supported by the retrieved source, not independently replicated. The original 3/22/33 tally should not be reused after these corrections.

## OpenAI announcement: source now retrievable

The [primary announcement](https://openai.com/index/navier-stokes-solution/) supports grouped agents, different problem variants, roughly 10,000 concurrent agents in the relevant group, an 88-hour discovery run and Codex consolidation of intermediate insights. It also states an additional 17 hours of Lean formalisation/verification via GPT-6 Astra. Thus **CL-006–009 and CL-014** can be strengthened; **CL-004/005/011–013/019/020/023/026** need their unsupported qualifications removed or separately marked. Pausing schedules, a specific controller node, a bottleneck and particular generated code artifacts are not established by that description.

The same source distinguishes **4.9m messages/300bn output tokens across all problems** from **2.7m/130bn for Navier–Stokes**. CL-010 is not false merely because it uses the larger count: its scope must say all attempted problems. CL-022 mixes scopes. Naming the formalisation model does not identify the discovery model. The register's regex rule treating all GPT-6 Astra references as contradicted by an unnamed discovery model is invalid.

This verifies an account of the workflow; it does not inspect the orchestrator implementation, reproduce the mathematics, prove a particular dashboard architecture, or justify copying its scale into Librarian. No UI-absence or strict network-isolation claim was established here.

## Manuscript counts need version and denominator

The [current primary repository README](https://github.com/openai/math) reports 721 manuscripts in 373 families. Its [history](https://github.com/openai/math/blob/main/history.md) documents withdrawals and later additions. The original statement that the primary material states no withdrawals is incomplete. CL-025's initial-release count needs the initial version, not a current-README comparison. I retain it as plausible rather than infer an initial count from later totals. Manuscripts, result families and formalised top-line results are different denominators.

## Structured output is verifiable; semantic correctness is separate

CL-029 is supported for **vLLM** by its [official structured-output documentation](https://docs.vllm.ai/en/latest/features/structured_outputs/), which describes schema/grammar constraints. This review does not separately verify Outlines. Neither service-level support nor valid JSON establishes that a particular DeepInfra route supports the required schema dialect or that generated claims are true. Keep a local schema/anchor verifier and qualify exact routes.

## DeepInfra privacy needs the linked operational documentation

The [privacy policy](https://deepinfra.com/privacy) provides a general policy statement and links to [operational data-privacy documentation](https://docs.deepinfra.com/account/data-privacy). The latter distinguishes ordinary inference, bulk APIs, model-provider exceptions and metadata logs. Consequently “no retention period stated” is only a description of the page Claude fetched, not a complete account of the published documentation. Apply the policy for the actual API and model used; do not generalize it to every provider or bulk workflow. This review did not send private files to DeepInfra.

## Local facts and suggestions requiring narrower wording

CL-095's model-listing evidence establishes availability at the captured time, not successful autonomous script writing/debugging. CL-096's local Vast controller evidence does not establish its exact image contents. CL-144 and CL-145 concern documented local Windows behavior with existing test provenance; they are not universal vendor capability findings. CL-085's measured rent-to-runner timings do not isolate image-pull and weight-load time.

CL-078/079 are proposed workload-selection heuristics. CL-089/090/093/139 are workload-specific cost/token estimates; they need a measured workload, model/hardware/version, utilization and failure policy. CL-094 is a proposed command, not demonstrated tooling. CL-098/099 and CL-105 onward largely describe specific historical local sessions or the reviewer's interpretation of them. Reclassify them as local assertions and retain their evidence limits rather than tagging them as outside model facts.

The remaining unsupported dashboard internals, staff disclosures, exact proof contents and subjective workflow descriptions remain unverified. Keeping uncertainty here is appropriate; blanket regex matching or an inability to fetch one page should not be presented as substantive refutation.
