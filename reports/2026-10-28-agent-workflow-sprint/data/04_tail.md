## I. Reader audit (five measures, kept apart)

| Reader | Papers read | Completed / truncated | Parse (as is / repaired / salvaged) | Anchored items | Quote on the cited page | Adjacent page | Elsewhere in paper | Not found |
|---|---:|---|---|---:|---:|---:|---:|---:|
@@READER_ROWS@@

- **Call completion and parse** are separate from quote location: a salvaged answer keeps the complete array items before a defect and drops the rest, so **salvage never proves the reading is complete**.
- **Quote location (exact page)** is stricter than the first pass's one-page tolerance. Re-checking with the strict rule: @@STRICT_RECHECK@@
- **The strict rule is a floor.** It misses quotes that the PDF breaks across lines at a hyphen ("VLM- related"). A follow-up that compares letters and digits only (`scripts/hyphen_recheck.py`, `data/hyphen_recheck.json`, added 2026-10-29) recovers 104 of the 145 misses: 97.7% of the 1,771 anchored items sit on the exact cited page or run onto the next (MiMo-V2.6-Pro 98.1%, GLM-5.3 98.3%, GLM-5.3-Flash 94.4%), and 30 quotes (1.7%) are found nowhere in the paper. Read the strict rates above as a floor and these as a ceiling. The coverage count below is a floor for the same reason.
- **Semantic support** (does the page support the claim?): @@SUPPORT_SUMMARY@@
- **Where the numbers in result texts come from.** @@RESULT_NUMBERS@@
- **Coverage against an independent checklist.** The second-pass reviewer chose 25 passages that the first pass had missed. @@COVERAGE@@ This is a small, selective checklist, so it bounds recall for those passages only; it is not a recall estimate for the papers.
- **Reader overlap.** On the @@OVERLAP_PAPERS@@ papers read twice, @@OVERLAP@@ Overlap between two readers is an exploratory sign of coverage, not a measure of it: independence, equal detectability and the definition of an item are not established. Where the two readers disagree on applicability level: @@LEVEL_AGREE@@
- **Judges.** The applicability opinion (`03-reading-list.md`) and the support audit use Qwen3.5-397B, a third model family, so no judge shares a family with a reader. GLM-5.3 was tried first for the applicability opinion and returned its reasoning instead of JSON until the output cap (a failure the first pass also saw twice), so it was not used as a judge; that call's $0.05 is counted in the spend.
- **What the first pass missed, found again here without being told.** @@MISSED_FOUND@@

## What this literature does not supply
No paper in the folder measures delegation economics, orchestrator quota, resume cost or review hold-up on software work. The closest are the drift papers (#01, #12; both report negative transfer outside their home domain), the task-tree validator (#02), the verify-before-act and false-refusal measures (#08), the role-level cost accounting for verification (#07) and the fixed-rule baseline lesson (#14). Verification costs are reported in a few robotics, reward-modelling and agent-system papers; none transfers to text API delegation without measurement (experiments E9, E12, E13 in `07-open-questions-experiments.md`).
