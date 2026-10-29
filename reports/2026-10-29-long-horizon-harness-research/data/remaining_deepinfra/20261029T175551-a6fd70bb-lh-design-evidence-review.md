

1. **Unsupported transfer: R06 fallback policy vs. product safety**
   **File:** `docs/long-horizon-harness-design.md` §10; `reports/.../REMAINING-CORPUS-REVIEW.md` (R06); `data/remaining_extraction_anchors.json` (remaining_06, p.6).
   **Finding:** The design correctly rejects R06's "safe default policy" fallback for invalid output, noting it applies to simulation, not mutation-capable products. However, §5 ("Execute") states invalid output gets a "bounded repair attempt or a visible stop." The source anchor confirms the simulation uses a fallback to preserve continuity. The design lacks explicit evidence for *repair* feasibility in the product context. Full-paper context on R06's specific failure modes is needed to justify "repair" over "stop" for unparseable contracts.
   **Risk:** Assuming repair is safer than stopping without evidence could permit malformed mutations.
   **Test:** Trace event logs for "invalid contract" outcomes; verify no mutation occurs before explicit repair success or stop.

2. **Unsafe authority: Hash chains vs. environmental authentication**
   **File:** `docs/long-horizon-harness-design.md` §4; `reports/.../REMAINING-CORPUS-REVIEW.md` (Corrections #5).
   **Finding:** §4 states hash chains "detect some edits but do not authenticate the entire environment." The review corrections align, noting receipts prove only implemented checks. However, §4 also says "A broken or unsupported history must not silently become authoritative state." The design relies on `VaultWriter` for integrity but admits hash chains don't prove scientific correctness. There is a tension between "authoritative state" and "unauthenticated environment."
   **Risk:** Users may conflate "integrity verified" (hash match) with "content verified" (truth).
   **Test:** Simulate an external edit to a source file during a session; verify the session flags staleness rather than accepting the hash-matched old state.

3. **Recovery contradiction: Cancellation vs. ambiguous timeout**
   **File:** `docs/long-horizon-harness-design.md` §5; `reports/.../REMAINING-CORPUS-REVIEW.md` (Design changes).
   **Finding:** §5 mandates "Check cancellation... before dispatch" and "An ambiguous timeout is not evidence that nothing happened." It requires reconciliation before retry. However, the design admits "Resume must avoid issuing a second effect merely because the first response was lost." If reconciliation is unavailable (per §5), the design says "park for a decision." This contradicts the goal of "Reliability and continuity" (§1) if parking blocks all progress indefinitely without a defined recovery path.
   **Risk:** Session paralysis during transient network failures if reconciliation tools are missing.
   **Test:** Inject a timeout during a tool call; verify the session parks without duplicate effects and offers a manual reconciliation path.

4. **Loss of user agency: Manual parameter specification in verification**
   **File:** `docs/long-horizon-harness-design.md` §10; `data/remaining_extraction_anchors.json` (remaining_14, p.30).
   **Finding:** The design cites R14 for "Reusable temporal requirement/check patterns." Anchor remaining_14 (p.30) states "values of pattern parameters are specified manually." The design §11 leaves "budget defaults; monitoring thresholds" open to implementation. If these thresholds (parameters) are manually specified without user visibility or adjustment, it contradicts §1 Goal: "User agency... revise scope." The design does not explicitly expose these verification parameters to the user.
   **Risk:** Hidden verification thresholds may reject valid user work without explanation.
   **Test:** Review UI spec for checkpoint controls; verify users can view and adjust verification thresholds (e.g., confidence limits) before session start.

5. **Small detail unnecessarily frozen: Context bound enforcement**
   **File:** `docs/long-horizon-harness-design.md` §6; `reports/.../