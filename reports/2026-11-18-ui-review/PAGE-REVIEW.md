# Librarian UI page review (2026-11-18)

Walked every page against the live ACCEPT-02 Core (`127.0.0.1:59480`) in Chrome, read-only: no
Accept, Approve, Queue, Choose or Close clicks, no model or paid calls. The built-in browser was
used once, only for the 375px width check. Each finding is tagged:

- **verified in source**: I read the code that causes it.
- **observed**: seen in the live page, cause not read.
- **judgement**: a design or usability opinion.

Pages covered: header and its menus (Library, Sessions, Checkpoints, Close), Chat and composer
(Modes, Model picker, Attach), the document pane (Plan, Browse, This week), Staging (Sources with
every status filter, Folders, Lenses, Concepts, Topics, Offerings, From V1), Search (every scope
and intent), Settings (all 12 sections), Models, and a 375px width pass.

No console errors or unhandled rejections on any page. A `<img onerror>` search string did not
execute (no XSS). Accessible names were present on every visible control.

## Bugs

| # | Where | Finding | Status |
|---|---|---|---|
| B1 | Header, Close menu (⏻) | Does not close on Escape or an outside click; every other popover does. `closeMenu` is missing from `popovers()` and from the list in `onDocumentClick` (`ui/src/main.ts:301`, `:307`). The menu holds "Close this library", so a stray open menu stays armed. | verified in source |
| B2 | Staging, Sources, "Queued for capture" | Header says "93 queued" but only 50 rows render, with no "showing 50 of 93" and no pager. `staging_list` is called with `limit: 50` (`ui/src/views.ts:267`). The rest of the queue cannot be seen or reached. | verified in source |
| B3 | Staging, source detail | The yellow banner "the extracted text is mechanical… Next: the approved batch cleans it into markdown" still shows after the stage ledger above it says every stage, including parse and cleanup, is complete. It is the capture-time verdict (`quality.py:45`) printed unconditionally when it is not "usable" (`views.ts:698`). The advice is stale once cleanup has run. | verified in source |
| B4 | Document pane, Plan, "Written" | The same note appears twice ("DataManagement Step 3 Grouping Proposal", one file). `session.writes` is rendered without de-duplication (`ui/src/chat.ts:931`). | verified in source |
| B5 | Chat model picker (Lead / Notes / Small tasks) | Lists all 177 DeepInfra models, including image, video, embedding and speech models (Bria/remove_background, Pixverse T2V, Lightricks LTX, BAAI/bge-*, Qwen3-ASR). The modality filter exists only for service slots (`ui/src/panels.ts:540`, `SLOT_KIND`); chat roles get none. Picking one as Lead would assign a model that cannot chat. | verified in source |
| B6 | Plan pane vs Staging | The pane lists the three sources as "approved"; Staging lists the same three as "Ingested, ready to accept". Two vocabularies for one state, and the pane copy is the session's recorded status, not the live one. The pane also lists only the last 12 sources (`slice(-12)`) while the heading shows the full count. | observed; list cap verified in source |
| B7 | Settings, Health vs other places | Health says "mcp: geo-grapher · installed; not enabled in this library". Review and promotion says "Enabled external servers: geo-grapher (connected)", and the header menu says Geo-Grapher is "Running for this library". Three statements about one thing, one of which contradicts the others. | observed |
| B8 | Search | An empty query is sent and returns "Nothing held matches / uncovered" instead of being refused or prompting for a query. | observed |
| B9 | Staging at phone width (375px) | The kind tabs (Sources … From V1) are 650px wide and do not wrap; the whole Staging view becomes horizontally scrollable, so the list and detail slide off-screen when you reach "Offerings" or "From V1". Matches your narrow screenshot. | observed |

## Inconsistencies

- **Folders vs Sources (fixed earlier this session)**: accepted folder cards no longer stay in the waiting list. They now move to an "Accepted" filter, as sources do.
- **Folders and Offerings show the "Evidence beside draft / on demand" selector**, which only applies to Sources and Lenses. Judgement.
- **Lens actions are not in view.** On a lens with long content, Accept / Reject / Defer sit about 700px below the fold and are not sticky; on a source they are visible. The label also differs: Lenses say "Accept", Sources say "Accept into library". Observed.
- **Wording**: the lead model reads `lead-m · preset-deepinfra` while the others read `google/gemma-4-26B-A4B-it · preset-deepinfra`; "lead-m" is an alias that does not say which model. The Modes button reads "Modes: Ask" while its option is "Ask permission". Search group headings mix "Sources · 0" with lower-case "workspace · 11". Judgement.
- **"Settings → Library" does not exist.** The hint appears in `pane.ts:327`, `views.ts:944`, `:1000` and `:1007`. Settings has a "CURRENT LIBRARY" group heading but no page called Library; lens packs are under "Methods & lenses", topics under "Topics & organisation". Verified in source.
- **"This week · open, dated tasks across the vault"** (`pane.ts:123`) shows only "No date (48)", so the heading promises dated tasks and shows undated ones. Observed.
- **Source row names**: queued sources show full file paths as names (`E:\DataManagement\_external\EXT_…pdf`), while ingested ones show the title stem. Observed.
- **Session title and phase badge** are cut off in the header with no `title` tooltip, so the full title cannot be read. The Sessions and Models buttons also have no tooltip. At 375px the title is hidden entirely and the header takes 173px of an 812px screen. Observed.
- **Disabled controls with no stated reason**: the Note tab in the pane, and five "Open" buttons under Commands and shortcuts. Observed.
- **Tabs**: Chat, Staging and Search are `role=tab` with no `tabpanel` or `aria-controls`. Judgement (accessibility).
- **Small targets**: provider enable checkboxes, the Modes checkboxes and the Effort slider are 13–16px, under the 24px WCAG 2.2 minimum. Observed.

## Potential problems

1. **The ACCEPT-02 "test vault" root is the owner's personal Obsidian vault.** It holds networking and university notes, a riddle app, canvases and images. This reaches the research round in three ways:
   - Search's "workspace" group returns those notes for research terms ("routing" returns *Introduction to Networking* and *Leaderboard page*).
   - Attach and Browse list them.
   - "This week" lists 48 tasks from them.
   If the research round should only see the DataManagement corpus, these results contaminate it. The extra reads cost nothing but add noise. Observed (directory listing confirms).
2. **No UI shows or edits the library budget ceiling.** `[budget] ceiling_usd` (now $10.00 here) is config-file only. Settings has no budget field and the settings search for "ceiling", "cost", "spend" and "limit" finds nothing (the `ceiling` matches in `settings.ts` are permission ceilings). The control that stops intake cannot be seen from the page the owner works in. Verified in source.
3. **Chat-model changes also update shared defaults.** The Settings text says: "Chat-model changes also update defaults used by libraries without their own choices." In an isolated test library, assigning a Lead here can change the default for other libraries (for example Resource-Library). Not tested, because I made no changes. The wording says so.
4. **Library list**: "Uni" (`D:\Librarian-Uni`) and "Librarian-Uni" (`D:\Librarian-Uni\.librarian-app`) look like one library registered twice (nested paths). Two entries are marked "folder missing" (Paperclip QA, TTS check) and still listed. Observed.
5. **Staging gives no pointer from Search.** A library-scope search for "routing" returns "Sources · 0" while three matching sources sit in Staging; they only appear under the Staging scope. A hint such as "3 matches in staging" would help. Judgement.
6. **The source fit screen is a weak signal.** For the RouteLLM paper it reports "unclear" because the paper "does not mention … O1-O9, cost caps, … tier-3 dispatch". A third-party paper will never mention the library's internal constraints, so this verdict will come back "unclear" for almost every external source. Judgement; worth checking the screening prompt.
7. **Close this library is one click** (after opening the menu) with no confirmation on the graceful path; it only asks when work is in progress. With B1, the menu can stay open. Judgement.
8. **Providers & keys** shows Anthropic, OpenAI and Local as "enabled" while Health shows their keys "not set", and says a fallback key file "still needs explicit migration" to the keychain. Possibly intended (enabled is not keyed), but the two pages read as a contradiction. Judgement.

## What looked right

Event stream indicator, library switcher (✓ marks the current library), Sessions list with ordering
filters, Checkpoints empty state, Search scopes and error handling, Staging per-status filters,
the evidence panels, Settings navigation and its "Find a setting" box (Enter does not close the
dialog), Escape on the other popovers, no horizontal scroll at 375px on Chat, Search and Settings.

## Suggested order, if you want fixes

1. B1, B2, B4 (small, certain). B5 and B3 next (B5 prevents a bad Lead assignment).
2. Potential problems 1 and 2 matter most for the research round; neither needs code.
3. The wording and accessibility items can batch into one pass.
