# INDEX-05 attachment scan reduction and DeepInfra delegation evidence

**Date:** 2026-10-28

**Status:** Implemented and locally verified; INDEX-05/G1 remains partial.

**Implementation:** `fd8a0ca`

**Delegation runner:** `6e1a355`

## Outcome

The real single-source promotion characterization now reads **603,979,776
bytes** for **83,886,080 logical attachment bytes**, or **7.2x**. The preceding
characterization read 2,332,033,024 bytes, or 27.8x. Peak individual reads
remain bounded to 1 MiB, byte-exact retained originals and published copies
still match, and concurrent Browser/Cowork reads remain responsive.

The change gives a single-source promotion an explicit copy inventory. Its
streamed copy, post-EOF source check, destination compare-and-swap, text/config
checks and final full source/destination check remain. Intermediate text and
embedding work no longer rehashes the attachment inventory. The exact digest
computed while streaming is also supplied to `DocumentLeases` after atomic
publication, avoiding an immediate duplicate destination read without
weakening watcher comparison: a later watcher observation still fingerprints
the file and treats any mismatch as an outside edit.

Batch/direct guards retain their conservative full-footprint behavior.

## External delegation record

The owner explicitly authorized review export of files under
`D:\Librarian_V2`. `scripts/delegate_deepinfra.py` confines exports to that
repository, denies credential paths, scans text for common secrets, hashes
every exported file and packet, reserves budget before dispatch, disables
implicit transport retries, and writes an atomic receipt containing the
provider request ID and usage. The approved total ceiling is **$12**.

| Task | Model | Request | Input | Output | Estimated cost | Result |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Canary | DeepSeek V4.1 Flash 1017 | `Rtgsx48Y00ER5jlCWG9cckZR` | 147 | 4 | $0.00001558 | Exact `CANARY_OK`. |
| Correctness map retry | DeepSeek V4.1 Flash 1017 | `Re4mqgF2pwGYRXOmGG4IisCW` | 33,184 | 4,000 | $0.00442803 | Found the main repeated-check boundary; output hit its cap and included false positives. |
| Patch draft | Qwen3 Coder 480B | `RS0dQJSBM9RtLARPhwhIH8X0` | 27,818 | 2,242 | $0.01058740 | Rejected locally: initialization order, legacy semantics and test patch were defective. |
| Adversarial critic | GLM 5.3 Flash | `RpuHC6fIm7nN8NoJKrKEWPoC` | 29,917 | 4,161 | $0.00656805 | Correctly rejected the Qwen draft and narrowed the safe boundary; retained one false positive. |
| 8x diagnosis | DeepSeek V4.1 Flash 1017 | `RBlRoP1ylJukzO6jRoTDm3qo` | 108,463 | 4,000 | $0.01180537 | Prompted the stack-attributed local measurement; its own attribution became circular and was not trusted. |
| Final reducer review | DeepSeek V4.1 Flash 1017 | `RfRqi8SIhLOf5OhkGVp0ub0k` | 45,621 | 3,289 | $0.00543782 | Ship verdict; no blocking finding survived local inspection. |

One earlier mapper process was interrupted after dispatch and produced no
provider receipt. Its full **$0.00589009** preflight reserve remains charged in
the local ledger rather than being silently reclaimed. Total committed budget,
including that uncertain reserve, is **$0.04473234**.

Model observations from this packet:

- DeepSeek was useful for broad control-flow mapping, but long answers reached
  the output cap and speculative attribution required local measurement.
- Qwen produced concise patch-shaped output but missed an initialization-order
  failure and broke established invariants; its patch was not applied.
- GLM was the strongest adversarial critic in this node, catching Qwen's
  concrete defects, though its retained-copy diagnosis still missed an
  existing top-of-copy full check.
- Agreement was never treated as proof. Stack-attributed I/O measurement and
  deterministic tests selected the final implementation.

## Verification

- Delegation runner and watcher focus: **22 passed**.
- Watcher/promotion/mixed/staging group: **102 passed in 49.26s**.
- Explicit slow large-attachment characterization: **1 passed in 1.95s**;
  7.2x amplification, 1 MiB maximum read, 0.047s concurrent read sample.
- Frozen default suite: **1,471 passed, 2 skipped, 4 deselected in 510.94s
  (8m30s)**.

The default suite excludes the explicit slow characterization, which is
reported separately above. No branch was pushed and no release/signing claim
is made.

## Remaining boundary

INDEX-05/G1 remains partial. The next local packet is encoder work currently
held inside an enclosing writer operation. Hosted Python matrix/signing and
execution in the real external host applications remain separate evidence.
