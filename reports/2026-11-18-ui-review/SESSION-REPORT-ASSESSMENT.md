# Assessment of the Antigravity session's bug reports (2026-11-18)

Two reports came from an Antigravity session that used the `Uni` library (Core on port 61744).
That Core was not touched. Every claim was re-checked against the source, and the ones that could
be reproduced were run live through the UI and Chat on a **scratch library**
(`scratchpad/uitest-vault`, its own Core, `$0.50` ceiling, stopped afterwards). It inherited the
same shared chat defaults the other session used (Lead MiMo-V2.6-Flash, Notes DeepSeek-V4-Flash-Vision-Exp,
Small tasks Qwen3-32B). The whole live session cost **$0.006**. ACCEPT-02 and its research session were not used.

Verdicts: **Reproduced** (seen live) · **Confirmed in code** (cause read, or measured by script) ·
**Partly** · **Not reproduced**.

## Blockers

| Claim | Verdict | Evidence |
|---|---|---|
| A. Map phase deadlock: `update_plan` is missing from the Map tool bundle | **Reproduced**, and worse than reported | Sent the same question in Chat. Frame → Map, three empty searches, then the model called `advance` **15 times in a row** ("stayed: the phase is not finished") until I pressed Stop. The "10 calls left" counter never moved, because refused advances cost no phase budget, so only the 80-step turn cap (effort 8) bounds the spend. The plan pane says "Still needed: …update_plan(map=...)" but the model is not offered the tool. Probe of `bundle_selection`: Map, Search, Judge, Synthesise and Check-out offer no `update_plan` at either tier. |
| A, extent | **Wider than the report says** | `session.py` gates 14 phases on a `update_plan(...)` call (map, check_out for `apply`, find, inventory, plan, seed, goal, focus, baseline, assess, candidate, practice, ingest, check_in; regex scan of the gate text, so approximate). None of them offers `update_plan` in its bundle. Only Map was reproduced live; the rest is the same mechanism and is code-level only. |
| A, side effect | **New** | Same run: `record_assumptions` failed twice with "'tool' is not a tool this session called successfully", so the model also filled the argument with the literal word `tool`. A model-side slip, but a refusal message that names the accepted values would recover it. |
| B. The Small-tasks (Clerk) model is rejected and the work is silently queued | **Reproduced; cause found** | The picker shows `Qwen/Qwen3-32B` as Small tasks, but `/api/routes/readiness` reports its clerk qualification as `experimental / missing`. `_require_profile_qualification` (`app.py:2405`) refuses any non-lead role below the profile floor (`screened` by default), and the refusal turns into `UnavailableEndpoint` → "queued". Staging then shows "Waiting on a clerk model… Choose a tier 3 model" and Draft says "Queued: no clerk model is available". The real reason (needs a qualification run) is lost at two places: `tools/staging.py:146` (`except clerk.ClerkUnavailable:` drops the message) and the hard-coded string at `ui/src/views.ts:615`. The same gate applies to Notes (scribe) and the research helper, which are also "experimental / missing". |
| B, follow-on: stale revision after a queued Redraft | **Reproduced** | After "Draft with the clerk" returned "Queued", "Accept as captured" hit a write-conflict checkpoint. "Reload item" cleared it (the next refusal was the legitimate "no reviewed draft" rule). `views.ts:615` skips `this.show(id)` when the draft is queued, so the page keeps the old revision. The checkpoint card then blames "an edit made outside this call", which is wrong: the edit was the app's own. |
| C. Chat intake stuck in a `macro_expansion` checkpoint loop | **Confirmed in code and by test** | `CheckpointStore.ensure` deliberately mints a **new** card once a checkpoint is resolved (`checkpoints.py:72`, test: pending retry reuses the card; after approve the same scope returns a different id). `run_macro` only continues when the model passes the approved `checkpoint_id` (`agent_runtime.py:885`). The card's own text says "Resolving this card records your decision only; it does not retry the blocked write". Approving in the UI therefore orphans the approval unless the model happens to re-send the id. Not run end to end (that needs a model turn that reaches a write-capable macro). |
| C, details | **Confirmed** | `macro_plan('inspect-map-source')` raises "no macro" (ids use underscores, phases use hyphens; the error does list the valid ids). The model also tried `macro_plan('update_plan')` to get the tool, which fits claim A. The Checkpoints card renders raw JSON including a `staged_revision` token and **no checkpoint id** (checked live). The header badge updated promptly in my run, so "stale badge" is **not reproduced**. |

## UI and accessibility claims

| Claim | Verdict | Evidence |
|---|---|---|
| `Open original` unreadable | **Confirmed (measured)** | Unclassed button at `catalogue.ts:15`; `.lib-app button` only sets `color: inherit`. In the dark theme: text rgb(236,234,240) on the browser face rgb(240,240,240) = **1.05:1** (report said ~1.1:1). |
| White search inputs in the dark Settings dialog | **Confirmed (measured)** | `style.css:266-267` lists `input[type=text]` for `dialog.lib-dialog` but not `search`. Dark theme: dialog text inputs rgb(30,29,35); both search inputs rgb(255,255,255). Readable (black on white) but inconsistent. |
| ⏻ menu ignores Escape and outside click | **Confirmed** | Same bug as B1 in `PAGE-REVIEW.md` (`closeMenu` missing from `popovers()` and `onDocumentClick`). Two independent finders. |
| Five placeholder-only inputs in Tools & integrations | **Confirmed**, low severity | No `<label>` or `aria-label` on any of them (checked live). A placeholder still gives an accessible name in most browsers, but it vanishes while typing. |
| Search `sessions` and `staging` tiles are dead ends | **Reproduced** | Plain `div` tiles, no button or link, `tabindex=-1`, `cursor: auto`; clicking a session tile did nothing. |
| No `<main>` on Staging or Search, no h1/h2 | **Confirmed** | Chat is a `<main>`; Staging and Search are not inside one; zero `h1`/`h2` in the app. (The report's exact heading levels differ from what I counted; the gap is real.) |
| `Geo-Grapher ↗` is enabled when Geo-Grapher is off | **Reproduced** | Scratch library has no Geo-Grapher: the button is enabled, clicking it shows "Geo-Grapher is not enabled for this library", while the ⏻ menu shows "Not enabled" with the Start button disabled. |
| Settings and Models open the same page | **Reproduced** | Both open "Models & services". |
| "Settings → Library" does not exist | **Confirmed** | Also found independently in `PAGE-REVIEW.md`. |
| `(Choose models)` is plain text | **Confirmed in code** | `views.ts:508` builds it as a string; compare the working button elsewhere. |
| `Modes → Suggest sources` has a field labelled "text" and Start is silent | **Reproduced**, with a twist | The only field is labelled and placeholdered "text". With text entered, Start closes the popover and nothing else happens. The earlier "Fill in every field first." notice (from an empty Start) **stays on screen** after the successful start, which reads as if it still applied. |
| Branch and Rewind only appear after a replay | **Confirmed in code** | `chat.ts:167` renders them only when `opts.index` is set (replay path). |
| `Sources 11` badge vs an empty default list | **Confirmed** | Also found independently as the badge/"0 waiting" mismatch. |
| Stale `quality` banner after cleanup | **Confirmed** | Also found independently (`views.ts:698`). |
| Plan pane repeats the same instruction in NEXT and OPEN | **Reproduced** | Visible in my Chat run; the chat card repeats it a third time. |
| Chat empty state points to a closed pane | **Reproduced** | "the plan on the right…" with the pane closed by default. |
| Mid-word `Accept` wrapping in Methods & lenses | **Not reproduced at 375px** | Buttons are 61×32 (one line). `white-space: normal` is set, so a narrower row could split them. |

## Not checked

Truncated claims ("otherris", "makingass"), duplicated concept usages, casing/plural concept duplicates,
the activity-search date quirk, stray `</function>` text in streamed output, and the closed-session
contradiction on the `UCLan` thread. They depend on the other session's library content or on a
particular model's output; I did not see them in the scratch run. The `</function>` claim is plausible:
`code_recovery.py:30` strips a complete `<tool_call>…</function>` block but nothing handles a lone closing tag.

## Findings that change what to do

1. **Claim A is the most expensive defect.** A refused `advance` costs tokens but not phase budget, so a looping model burns the full turn cap. Two fixes are needed: offer `update_plan` in every phase whose gate asks for it (a registry-level check that every gate hint names a tool the bundle offers would have caught this), and make repeated identical refusals end the turn.
2. **Assigning a model is not enough.** Notes, Small tasks and the research helper are all "experimental / missing" until a qualification run, and every background action silently queues. The UI should say "qualification needed" with the real reason and a path to run it.
3. **Shared defaults do leak.** The scratch library inherited the other session's three chat models without being asked. This confirms the untested risk in `PAGE-REVIEW.md` (potential problem 3).
4. The two reports and `PAGE-REVIEW.md` agree on five items (⏻ menu, Staging counts, stale banner, `Settings → Library`, tiny targets), which raises confidence in those.

## Suggested order

1. Map/phase-gate `update_plan` gap plus the repeated-refusal turn stop.
2. Surface the Clerk refusal reason; reload the item after a queued draft; correct the write-conflict wording.
3. Checkpoint approval resumes (or hands the id back to) the pending macro; show the checkpoint id and a readable summary instead of raw JSON.
4. The small certain items: ⏻ dismissal, `Open original` class, dialog search styling, Geo-Grapher ↗ state, the "text" form, queue cap and duplicate "Written" entries from `PAGE-REVIEW.md`.
