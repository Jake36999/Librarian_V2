# Librarian: research-informed UI/UX assessment

4 November 2026. Repository: `D:/Librarian_V2`. Inspected HEAD: `40ec923f5d7cb5612939b9fc456963b88e0af4a3`. Research basis and complete source inventory: [research synthesis](research-synthesis.md).

## Assessment

Librarian has a coherent visual foundation and useful mechanisms for deliberate research work: a chat/document workspace, staged acceptance, model-readiness information and explicit recovery paths. Its strongest observed weaknesses are readability at narrow widths, discoverability of configuration, and the effort required to understand model assignment. Its research-specific strengths deserve user validation, particularly whether people can distinguish evidence, drafts, accepted notes and unfinished work.

This is a **research-informed inspection with browser evidence**, not a completed usability experiment, ISO compliance assessment or release verdict. A passing scripted workflow establishes functional coverage under that fixture; it does not establish human effectiveness, efficiency, satisfaction or adoption. No overall percentage score is justified.

## Evidence and boundaries

The browser walkthrough earlier in this chat used installed Edge through Playwright with a disposable, seeded demo Core and scripted providers. Screenshots were inspected at 1440 × 1000 and 390 × 844 CSS pixels. The existing `node run-smoke.mjs` suite passed in that fixture. Its checks exercised chat/model selection, approvals, notes, tasks, attachments, settings, MCP, search, staging, sessions and failure recovery. The later focused walkthrough captured no page errors and measured document width equal to viewport width at 390 pixels. Neither finding proves visual usability or accessibility.

The live app on port 8765 was checked at the library picker. Its existing research libraries were not used for invasive tests. The user's CDP-enabled in-app browser was not reached; the review used a separate Edge instance. Source inspection in this turn corroborated pane persistence, model selection alternatives, Settings representation and Search markup. These are the same working-copy observations, not a new production deployment test. Existing untracked repository documents were left untouched.

| Evidence | What it supports | Boundary |
|---|---|---|
| E1: [desktop chat](ux-chat.png) | Initial two-pane composition and toolbar arrangement | Screenshot captured early during initialization; blank model/mode controls in this image are not treated as persistent defects. |
| E2: [desktop model picker](ux-models.png) | Ordered model assignment, terminology and readiness presentation after loading | Seeded model catalogue, not actual provider capability. |
| E3: [desktop settings](ux-settings.png) | Connections hierarchy and scrolling surface | Demo credential/key-storage state, not a security finding about the user's installation. |
| E4: [desktop search](ux-search.png) | Narrow controls within the split workspace | Initial empty state, not relevance-quality evidence. |
| E5: [desktop staging](ux-staging.png) | Review categories, source list and review prompt | Does not prove a participant understands acceptance. |
| E6: [mobile pane](ux-mobile.png) | An open pane covers the workspace after narrowing the desktop viewport | Conditional on pane state, not the fresh-mobile default. |
| E7: [mobile chat after closing pane](ux-mobile-chat.png) | Chat and composer are available again | Does not prove one-handed touch usability or behavior with a virtual keyboard. |
| E8: [mobile search](ux-mobile-search.png) | Query and selected filter values visibly clipped | No horizontal overflow is needed for this defect to occur. |
| E9: [mobile settings](ux-mobile-settings.png) | Dialog fits the width and wraps tabs; content requires vertical scrolling | Focus trapping, screen-reader order and zoom were not tested. |
| E10: source inspection | `main.ts:117`, Settings plus icon; `main.ts:218,252`, pane initialization/persistence; `panels.ts:429–491`, model interactions; `views.ts:834–852`, Search controls; `style.css:60–62`, mobile pane overlay | Implementation evidence supports interpretation; it does not replace user testing. |

## Applying the papers' approach

R2 supplies the organizing method: map features to attributes and heuristics, specify checks, inspect, then validate and refine. Its ISO discussion makes the context of use essential. The working context here is an individual researcher using a local library, on a desktop or narrow browser, with mixed familiarity with model configuration. This is an assessment assumption, not a user-research finding.

R1 informs how to record interaction context; R5 informs hypotheses about proximity, grouping and attention; R6 separates usefulness from ease and intention from actual usage; R9 informs task decomposition and the need to test different levels of experience. Their experimental results are not directly portable to Librarian. All R-number citations below refer to the synthesis and its PDF page locators.

### Provisional Librarian criteria

This twelve-item set adapts general heuristics to the app's research domain. It has not been independently validated. Priority is the importance of the criterion (3 critical, 2 important, 1 useful), **not** measured defect severity. Status means observed concern, partial support, or unverified; it does not imply a formal pass/fail.

| ID / priority | Feature and rule | Attribute / source | Operational check and current assessment |
|---|---|---|---|
| L01 / 2 | Settings and primary actions use recognizable labels. | Learnability, consistency; R2 p.2 H2/H4/H6. | Ask a new user to find model setup without hints. **Concern:** Settings is visually “+”; accessible name and tooltip help but do not resolve visual ambiguity (E3/E10). |
| L02 / 3 | Search retains readable query and scope at supported widths. | Effectiveness, efficiency; R2 H6/H7; R9 pp.3–5. | At 390 px, read all selected values and enter a query. **Observed concern:** five controls compete in one row (E8). |
| L03 / 2 | A pane can be opened, closed and resized without losing the primary task. | Control/freedom; R2 H3/H7; context measurement from R1 pp.9–11. | Narrow an open desktop workspace, recover chat, and return to the same task. **Concern:** pane covers the chat; close restores it (E6/E7). |
| L04 / 2 | Users can assign, inspect and change model roles explicitly. | Recognition, error prevention; R2 H5/H6; task decomposition R9. | Choose a lead and writer, replace the writer, clear the assignment. **Partial:** roles are described, but click order creates state-dependent meaning; alternatives to right-click exist (E2/E10). |
| L05 / 3 | Model selection, capability and verified readiness are distinguishable. | Status, credible interpretation; adapted R2 H1/H5 to research domain. | Ask what “unprofiled”, selected and qualified each imply. **Partial support:** readiness/qualification labels and override checks exist; human comprehension unverified (E2 and smoke). |
| L06 / 3 | Every reviewed claim can be related to its evidence. | Effectiveness, credibility; domain adaptation of R2; cautious proximity application R5 pp.2–5. | Locate the evidence supporting a staged claim, explain a limitation, then accept/reject. **Partial support:** grounding/review workflows passed scripted checks; actual comprehension unverified. |
| L07 / 3 | Captured, queued, processed and accepted sources remain distinguishable. | Status and error prevention; adapted R2 H1/H5. | Identify what is already in the library and what acceptance will change. **Partial support:** categories and statuses visible (E5); smoke covers queue/start/accept; novice interpretation unverified. |
| L08 / 3 | Interrupted work retains context and offers an explicit recovery step. | Recovery and control; R2 H3/H9. | Trigger the fixture's interrupted acceptance and stale review; recover without silently dropping edits. **Partial support:** existing smoke checks passed; recovery clarity with users unverified. |
| L09 / 3 | Permissions make a write's scope and consequence understandable. | Error prevention, control; domain adaptation of R2 H3/H5. | In Ask mode, explain an approval before choosing it; inspect folder edit permissions. **Partial support:** approvals and default-off folder edits passed scripted checks; informed consent unverified. |
| L10 / 2 | Initial screens offer a useful next step without teaching the whole system. | Learnability, help, perceived usefulness; R2 H8/H10; R6 pp.2–3/8. | Start one research task from a new thread with no coaching. **Concern:** empty states describe mechanics but supply few direct starter actions (E1/E4). |
| L11 / 2 | Related controls and explanations are grouped by user task. | Efficiency, findability; R2 H8; cautious R5 proximity transfer. | Connect a provider without reviewing advanced host/agent settings. **Concern:** Connections mixes routine setup and deep configuration (E3/E9). |
| L12 / 3 | Meaningful outcomes and user effort are measured separately. | Effectiveness, efficiency, satisfaction, usefulness; R2 p.2; R6 p.8; R9 pp.3–5. | Collect success/error/time plus ease/usefulness and actual return behavior. **Unverified:** browser logs establish functional actions, not a UX outcome dataset. |

Example interpretation for L02: a wide, labelled query field with readable selected scope complies with the intended check; clipped fragments violate it. Expected benefit is less ambiguity and less corrective interaction. Misunderstanding to avoid: no horizontal page overflow does not imply readable controls. Similarly, L06 concerns checking evidence, not merely displaying two panels.

## Findings and proposed changes

Priority below is a local product recommendation: **P1** obstructs a core task's usability in an observed state; **P2** is meaningful friction; **P3** is a lower-urgency hypothesis. Frequency and human impact magnitude were not measured. No security or release blocker is inferred from this scale.

### F01 — P1: Mobile Search hides meaning through compression

**Observed:** E8 shows a narrow query input and clipped scope/intent/date values at 390 × 844. The page itself fits the viewport. E4 shows lesser truncation even on desktop when the document pane is open. Search markup keeps query, three selectors and the action together (E10).

**Research link:** L02; R2 recognition and efficiency; R9's task-selection framing. **Inference:** people may struggle to verify the active search context, but no participant error rate has been collected.

**Proposed change:** give the query a full-width row and a visible label; put scope and optional filters below or in an expandable Filters area. Preserve readable selected values rather than shrinking every control. **Verification target:** at both tested widths, complete a source search with a date/intent change and explain the chosen context. Test additional widths and text zoom before claiming responsive coverage. This layout target is a proposal, not a numerical threshold from the papers.

### F02 — P2: Pane persistence becomes an unexpected mobile takeover

**Observed:** resizing a desktop layout with its pane open produces a full-workspace Plan panel (E6). Closing it restores chat (E7). Source initializes a fresh pane as closed below 1000 px unless a saved preference overrides it; mobile CSS changes an open pane into an overlay.

**Research link:** L03; R2 control/freedom and R1 interaction context. **Correction to earlier review:** this is conditional persisted/open state, not the default fresh-mobile layout.

**Proposed change:** distinguish desktop split-pane preference from mobile overlay state. Close or explicitly transition the overlay when narrowing, preserving the selected document and offering a labelled return-to-chat action. **Verification target:** desktop-to-mobile resize, narrow reload with saved open state, open note on mobile, then return to chat with draft intact. Decide deliberately whether a note-reading workflow should stay open; blanket auto-close could itself interrupt users.

### F03 — P2: The Settings symbol suggests adding content

**Observed:** “+” opens Settings (E3/E10); its accessible name and title are Settings. **Research link:** L01; R2 real-world match/consistency/recognition. **Inference:** visual discoverability is weaker than the programmatic name; this is not a missing-accessible-name finding.

**Proposed change:** use a gear with a label where space permits. **Verification target:** first-time users can find provider configuration unprompted; record wrong turns and time to locate. Do not treat a scripted click by accessible name as proof of visual discoverability.

### F04 — P2: Ordered model assignment exposes internal sequencing

**Observed:** choosing model cards in order fills lead, note-writing and small-task tiers. The picker explains this, but one card's effect depends on the previously filled slots (E2/E10).

**Research link:** L04/L05; R2 recognition/error prevention; R9 task/decision decomposition. **Correction:** the app already supplies a visible Clear selection button after selection, Delete support and a touch long-press alternative. Right-click is not the only recovery path. My earlier recommendation to add a Clear action overstated that gap.

**Proposed change:** select the role first, then its model, with visible Replace/Clear per role. Keep capability and qualification information close to the chosen role. **Verification target:** select lead and writer, change just the writer, and explain the fallback/qualification state. Compare decisions and resets; do not promise a time saving without a study.

### F05 — P2: Connections front-loads advanced configuration

**Observed:** provider credentials, service-model assignments and deeper agent/host settings share a long scrolling dialog (E3/E9). Wrapped mobile tabs keep the modal within the viewport but do not remove the information burden.

**Research link:** L11; R2 minimalist design and R6 ease versus usefulness. **Inference:** novice setup may feel more complex than the underlying research task requires.

**Proposed change:** use task sections such as Connect provider, Choose chat model, Optional services and Advanced configuration. Preserve visible status and repair actions. **Verification target:** users can make one successful connection and identify whether it was tested without entering unrelated host settings. Real provider tests remain a separate gate.

### F06 — P3: Empty screens reserve space without directing progress

**Observed:** an empty Plan occupies about half the desktop workspace; Search begins mostly blank, and Chat explains session mechanics (E1/E4/E5). The split layout is valuable when evidence or a note is open; the problem is its empty state, not the split-view concept.

**Research link:** L10/L11; R2 minimalist design/help; R6 perceived usefulness. **Proposed change:** collapse an empty Plan until needed, or show a compact contextual prompt. Offer a few real research starters, such as finding a source, reviewing an intake item or resuming a session. **Verification target:** test first meaningful task completion and usefulness judgments; choose starter tasks based on intended users rather than decorative sample prompts.

## Strengths to preserve and validate

- The chat/document split can keep a source beside research work; this is compatible with the proximity hypothesis from R5, but a comprehension benefit is not measured.
- Staging distinguishes review work from ordinary chat, and scripted checks cover evidence presentation and deliberate acceptance. Preserve that separation during simplification (L06/L07).
- Ask-mode approvals, explicit permission controls and readiness warnings can support informed control (L05/L09). Avoid hiding them merely to reduce visual density.
- Failure and stale-review flows have functional checks for preserving work and requiring explicit recovery (L08). The next question is whether users understand and complete recovery.
- Warm surfaces, restrained accent colour and consistent form styling give a coherent reading environment. This is an inspection judgment, not a measured satisfaction result.

## Validation plan derived from the papers

### 1. Validate the instrument

Use R2's stages 7–8 rather than declaring the provisional criteria validated. Ask independent evaluators to inspect the same build/tasks using the proposed criteria and a general heuristic control set under comparable conditions. Compare distinct confirmed findings, duplicate/incorrect associations, research-specific coverage and severity judgments. Ask reviewers about clarity, utility and missing checklist detail. If following the paper's expert-judgment suggestion, recruit at least three suitable experts, including domain knowledge where possible (R2 PDF p.10); no such reviewers have been recruited here.

### 2. Pilot a task-based study

Recruit representative researchers with both new and established experience of research/model tools, and include the input/device/access needs the product intends to support. Run a small formative pilot, revise tasks, then size any comparative study around the desired effect and variability. The papers do not establish a universal participant count for Librarian.

| Task | Observable success | Measures and design question |
|---|---|---|
| Connect and choose a model | User finds setup, selects a suitable lead and identifies readiness | Wrong turns, help requests, completion time, qualification comprehension. |
| Find a relevant source | User selects the intended scope/filters and opens the target note | Success, query/filter corrections, time; prioritize narrow Search. |
| Review a captured source | User locates supporting evidence and correctly distinguishes captured from accepted | Evidence accuracy, interpretation errors, acceptance mistakes, confidence. |
| Change a model role | User replaces only the intended role and explains the result | Decisions, resets, unintended changes; compare role-first prototype. |
| Resume across a layout change | User resumes a draft after pane/viewport changes | Lost input/context, recovery time, help required. |
| Recover interrupted work | User recognizes partial completion and uses the correct recovery action | Safe recovery success, repeated actions, preserved edits, explanation accuracy. |

Use equivalent task variants and counterbalance old/new design order if comparing prototypes; familiarity otherwise biases results. Keep the vault and scripted provider fixture constant for interface comparisons, then test real provider variability separately. This experimental design is a local adaptation, not an experiment already conducted.

### 3. Collect outcomes, not just activity

Measure effectiveness as task success and relevant error/recovery outcomes. Measure efficiency as elapsed and active interaction time, reporting provider waiting separately. Ask exploratory questions about ease, confidence in what changed, and usefulness to the research goal; these questions are not a validated psychometric instrument. Record actual return/resumption behavior if evaluating adoption (R6), with agreed study boundaries.

Adapt R1's contextual record to include task ID, study alias, UI version, viewport/input class, active view, pane state, event, outcome and elapsed time. Do not record research text, keys or inferred demographics. Inspect existing activity/session data before adding instrumentation; no new telemetry has been implemented or verified here.

Optional eye tracking can examine Settings, scope controls, role selection and claim/evidence areas. Specify areas of interest and hypotheses before collection; record calibration losses and pair gaze with task/comprehension results (R5). Do not equate time spent looking with understanding, or infer attention from cursor movement alone.

### 4. Reassess after changes

Fix F01 first, then F02–F05; prototype F06 alongside onboarding. Re-run the existing browser suite for behavioral regressions, inspect affected layouts at desktop/narrow widths and zoom, then conduct the user tasks. Maintain separate records of functional regressions and usability outcomes. Revise the criteria if real research problems are missed or if criteria repeatedly overlap (R2).

## Outstanding evidence

No recruited user study, independent heuristic comparison, eye tracking, validated satisfaction/adoption measurement, screen-reader/keyboard audit, dark-mode evaluation, virtual-keyboard evaluation or cross-browser matrix was completed. Real provider quality, responsiveness under long libraries, Obsidian-specific layout and production behavior are outside this evidence. No ISO/WCAG conformance conclusion follows from these screenshots or papers. No app code, source papers or user research libraries were changed for this assessment.
