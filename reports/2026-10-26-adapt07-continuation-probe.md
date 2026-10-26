# ADAPT-07 continuation probe: the two reviewed DeepInfra routes

**Date:** 2026-10-26. **Contract:** L1 probe contract version 3 (tool proposal → tool result → final answer).
**Run by:** Claude, with the owner's approval of a small budgeted run.

The probe sends one prompt and a single strict tool, `librarian_probe`. If the model proposes exactly one valid call, the probe replays that reply exactly as the agent loop does (`Reply.message()`, including any `reasoning_content`) with a tool result carrying a one-off token. It then requires a plain-text final answer containing that token, with no further tool call, unique non-empty tool-call IDs and the exact requested model in every reply. A route that only manages the proposal is not screened.

Each route made 2 calls with `temperature=0`: up to 64 output tokens for step 1 and 256 for step 2. It ran in a throwaway vault and config folder, through the product's own `App.run_qualification`.

| Route | Outcome | Duration | Observed model | `reasoning_content` in a tool loop | Replayed | Status |
| --- | --- | --- | --- | --- | --- | --- |
| `XiaomiMiMo/MiMo-V2.6-Flash` | pass | 12.1 s | exact match | **returned** | yes | screened |
| `deepseek-ai/DeepSeek-V4.1-Flash` | pass | 2.5 s | exact match | not returned | not applicable | screened |

**What this means for ADAPT-08:** MiMo-V2.6-Flash sends a reasoning continuation with its tool proposal, and the probe confirms it accepts that continuation replayed on the next turn. Its `native_reasoning` capability is `unknown` in its expectation record; this is evidence for the "reasoning replay policy" value ADAPT-08 introduces. DeepSeek-V4.1-Flash needs no replay. Neither expectation record was changed by this run: both routes keep provider-default behaviour until ADAPT-08's reviewed records permit a change.
