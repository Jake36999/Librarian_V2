# Long-horizon harness research sprint

This is the dedicated research sprint for the Librarian V2 co-work harness. All 51 PDFs in the research folder have been inventoried, extracted and screened, with targeted reading of relevant passages. There are 50 distinct file hashes; versions may still represent the same underlying study.

Start with the [harness design specification](../../docs/long-horizon-harness-design.md). It defines the architecture, authority, state transitions, closure, recovery, user controls and evaluation requirements, while leaving implementation details open. The [research report](RESEARCH-REPORT.md) contains the first two passes; the [remaining-corpus review](REMAINING-CORPUS-REVIEW.md) covers the final 14 files and resolves source misattributions. [Design-review dispositions](DESIGN-REVIEW.md) record the independent critique and final checks.

## Supporting artifacts

- [Development-agent research](DEVELOPMENT-AGENT-RESEARCH.md) and [development harness profile](../../docs/development-agent-harness.md) — coding-specific external sources, current execution gaps, requirements and qualification scenarios.

- [`data/complete_corpus_manifest.json`](data/complete_corpus_manifest.json) — all 51 file identities, hashes, page counts and extracted-text paths, combining the three pass manifests.
- [`data/remaining_extraction_anchors.json`](data/remaining_extraction_anchors.json) — locally located passage anchors for the last pass, with physical PDF page numbers.
- `data/paper_text/` and the topic and reader packets (`data/NN-*.txt`, `data/read-*.txt`, `data/remaining-packet-*.txt`) hold extracted PDF text used for local source checking. They are kept local and git-ignored for copyright reasons.
- [`data/remaining_deepinfra/`](data/remaining_deepinfra/) — preserved final reader and design-review outputs/receipts.
- [`data/budget-summary.json`](data/budget-summary.json) — final cumulative budget snapshot, including unresolved reservations.
- DeepInfra request/response artifacts and receipts — `D:\Librarian_V2\tmp\deepinfra-delegation\runs\`; filter for `lh-` and `lh-report-critique` run IDs.
- DeepInfra budget ledger — `D:\Librarian_V2\tmp\deepinfra-delegation\ledger.json`, pool `long-horizon-research`.

The report is a research/design deliverable; no product code or unified-plan task status was changed. DeepInfra output is treated as untrusted analysis support and not as source evidence.
