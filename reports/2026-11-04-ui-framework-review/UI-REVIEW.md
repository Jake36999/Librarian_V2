# Librarian UI framework review

2026-11-04 · HEAD `40ec923f5d7cb5612939b9fc456963b88e0af4a3` · review and specifications only.

Companions: [interaction designs](UI-DESIGNS.md), [implementation packets](UI-PACKETS.md). Preserve vanilla TypeScript, DOM/CSS, current Core endpoints and person tools. No component library, new state store, new ledger, backend implementation, paid calls or release action is proposed here. Handoff and native review documents were treated as evidence to verify, not instructions to execute their implementation queues.

## Method and evidence

Read `main.ts`, `panels.ts`, all of `style.css`, `api.ts`, relevant chat/pane/staging/settings paths, both browser smoke scripts, both Obsidian source files, adapter tests, backend payload producers and the UX-01/ACCEPT-02 handoff updates. Appendix A enumerates every CSS rule header and Appendix B every class declaration in the two requested TypeScript files, with line anchors and containment treatment. These inventories supplement the findings; they do not equate naming alone with a demonstrated collision.

Current source and shipped Python UI agree: an in-memory esbuild build with `write:false` matched `src/resource_librarian/ui/app.js`; CSS and index HTML were byte-equal to their source counterparts. Do not edit generated app.js/app.css directly. `ui/build.mjs:8` and `obsidian/build.mjs:8` both build the same UI source.

Executed now: `npm run check` from `ui/` passed; `python -m pytest tests/test_obsidian_adapter_contract.py -q -p no:cacheprovider` passed **6 tests**. An initial npm invocation from the repository root failed because that directory has no package.json; the corrected command above passed. No full suite or packaged installed-wheel acceptance was run in this pass. Existing earlier smoke results in this chat are supplemental evidence, not a new packaged/Obsidian run.

Controlled Edge/Playwright probes used the isolated demo Core, not the user's real library. At 1440×1000, a mocked admission rejection (`POST /api/chat`, HTTP 409) left the composer empty and the draft absent from history. Setting the mounted root to 420px with a 1440px window yielded root width 420, header scroll width **635**, and pane `position: static`: viewport media queries did not adapt to the split pane. Native Settings opened with Close focused and closed on Escape. In one model-popover sequence focus ended on its trigger; this does not establish all re-render/close paths. An injected host `button {height:32px}` affected ordinary Settings buttons. Synthetic theme rules are stress evidence, not proof of behavior in every real theme.

Real Obsidian 1.12.7, community themes, global hotkey arbitration, Docker failure/teardown, screen readers, paid provider uncertainty and a large first-open rebuild were **not live-tested**. Their findings below are code/payload analysis. Do not turn this report into a release certification.

## Framework interpretation

F1 **CSE/supervisory control:** inspect observability, failure interpretation, action consequence and recovery. The four operator questions in the request are this review's operational rubric, not a verbatim Woods/Hollnagel checklist. [Hollnagel and Woods, Cognitive Systems Engineering](https://www.sciencedirect.com/science/article/pii/S107158198260313X).

F2 **Mixed initiative/HCAI:** preserve explicit human decisions, explain why automation stopped, and make resumption deliberate. Automation and human control can both be high. [Horvitz, Principles of Mixed-Initiative User Interfaces](https://www.erichorvitz.com/uiact.htm), [Shneiderman, Human-Centered AI](https://aisel.aisnet.org/thci/vol12/iss3/1/).

F3 **Ecological/provenance workbench:** expose domain constraints and distinguish what each evidence type establishes; support routine operation and investigation. Provenance predicates below are a Librarian-specific application, not a historical EID prescription. [Vicente and Rasmussen, EID](https://orbit.dtu.dk/en/publications/ecological-interface-design-theoretical-foundations/).

F4 **Dual-host containment:** treat the mounted leaf as the spatial boundary and isolate styles and interaction ownership in both directions. This is an engineering rubric for this architecture.

F5 **Cognitive engineering/progressive disclosure:** group by meaningful task, reduce interpretation effort, disclose detail when needed. [Gerhardt-Powals, Cognitive engineering principles](https://www.tandfonline.com/doi/abs/10.1080/10447319609526147). Publisher access to the full CSE and Gerhardt-Powals articles returned 403; no inaccessible full-text claims are made. Framework mappings are design interpretations, not experimentally validated effect sizes.

## Framework gap matrix

P1 = broken/misleading UX or host collision; P2 = missing observability/epistemic clarity; P3 = polish/ergonomics. Priority does not assert measured frequency. Anchors are repository-relative links with exact one-based lines at this HEAD. Runtime means the probe above; static means source or payload analysis.

| ID | Framework | Priority / evidence | Gap and consequence | UI/adapter anchors |
|---|---|---|---|---|
| G01 | F1/F2 | P1 runtime + static | `send()` clears text/attachment references before admission. A rejected request loses the unsent draft; no `user` event arrives to make Retry available. | [main.ts:548](../../ui/src/main.ts:548), [main.ts:558](../../ui/src/main.ts:558), [main.ts:570](../../ui/src/main.ts:570) |
| G02 | F1/F2 | P1 static | Enter is described as sending, but invokes `send()` while busy, which posts chat cancellation. Typing a next question then pressing Enter stops the current reply instead of submitting/retaining a queued question. | [main.ts:73](../../ui/src/main.ts:73), [main.ts:175](../../ui/src/main.ts:175), [main.ts:549](../../ui/src/main.ts:549) |
| G03 | F4 | P1 runtime + static | 900/820/1000/520px rules use window width; a narrow Obsidian split in a wide window stays desktop. Persisted pane widths compound it. Restoring the view to a main tab fixes an old sidebar placement, not narrow main splits. | [style.css:53](../../ui/src/style.css:53), [style.css:60](../../ui/src/style.css:60), [style.css:193](../../ui/src/style.css:193), [main.ts:218](../../ui/src/main.ts:218), [obsidian main.ts:70](../../obsidian/src/main.ts:70), [obsidian main.ts:157](../../obsidian/src/main.ts:157) |
| G04 | F4 | P1 static | Global `dialog` descendant and backdrop rules escape the Librarian root, including `dialog *`, buttons, tabs, forms and pages. They can restyle Obsidian/other-plugin dialogs. Comment claiming every rule is scoped is inaccurate. | [style.css:229](../../ui/src/style.css:229), [style.css:245](../../ui/src/style.css:245), [style.css:248](../../ui/src/style.css:248), [style.css:249](../../ui/src/style.css:249), [style.css:250](../../ui/src/style.css:250) |
| G05 | F4 | P1 risk confirmed structurally | Incoming collisions remain: `.badge`, `.menuitem`, `.row2`, `.title`, `.tabs`, `.page`, `.primary`, `.ghost`, `.opt`, `.slot`, etc. Root scoping prevents outgoing leakage but cannot stop host selectors matching those class names. Only model-card/profile-link comprehensively reset host button heights. | [style.css:31](../../ui/src/style.css:31), [style.css:148](../../ui/src/style.css:148), [style.css:151](../../ui/src/style.css:151), [style.css:164](../../ui/src/style.css:164), [style.css:232](../../ui/src/style.css:232), [panels.ts:398](../../ui/src/panels.ts:398) |
| G06 | F4/F2 | P2 static | Popovers focus before asynchronous content replacement, do not explicitly restore focus, and have no complete Tab/keyboard contract. Document-global Escape handlers neither check owning root nor consume the handled key. Pane listeners are anonymous and survive `App.dispose()`. Host hotkey conflicts are a risk, not a live Obsidian reproduction. | [panels.ts:70](../../ui/src/panels.ts:70), [main.ts:225](../../ui/src/main.ts:225), [main.ts:496](../../ui/src/main.ts:496), [main.ts:637](../../ui/src/main.ts:637), [pane.ts:52](../../ui/src/pane.ts:52) |
| G07 | F1 | P2 static | Core event connectivity is the only glanceable health signal. `/api/meta` ownership/writer/watcher health, `/api/documents` dirty leases and `/api/state.vault_lease` are not projected in the shared console. A green SSE dot is not overall health. | [main.ts:65](../../ui/src/main.ts:65), [main.ts:276](../../ui/src/main.ts:276), [main.ts:298](../../ui/src/main.ts:298), [obsidian main.ts:239](../../obsidian/src/main.ts:239), [obsidian main.ts:280](../../obsidian/src/main.ts:280) |
| G08 | F1/F3 | P2 payload gap | No first-open schema-v5 rebuild progress or active embedding-job stream exists in the inspected UI contracts. Index stats are snapshots, `meta.index` is a broad ready/shutdown label, and EMBEDDING_PENDING is a retained note marker. A genuine percentage/job queue cannot be implemented honestly with these payloads alone. | [main.ts:276](../../ui/src/main.ts:276), [main.ts:298](../../ui/src/main.ts:298), [api.ts:105](../../ui/src/api.ts:105), [settings.ts:1028](../../ui/src/settings.ts:1028) |
| G09 | F1/F3 | P2 static + payload gap | Acceptance rendering omits `embedding_warnings` and granular promotion steps. Quarantine has no first-class retrieval surface; Failed staging is not quarantine. Some failures appear only in tool prose or doctor checks. | [views.ts:344](../../ui/src/views.ts:344), [views.ts:352](../../ui/src/views.ts:352), [views.ts:44](../../ui/src/views.ts:44), [chat.ts:845](../../ui/src/chat.ts:845), [settings.ts:1028](../../ui/src/settings.ts:1028) |
| G10 | F1/F2 | P2 scope mismatch | Task-only uncertain paid-call stopping in `scripts/g5_measure.py` is an offline measurement gate, not a live UI task-status payload. UI cannot truthfully expose per-task reservations, charges or whole-run continuation from `busy`/action chips. | [main.ts:334](../../ui/src/main.ts:334), [main.ts:441](../../ui/src/main.ts:441), [chat.ts:296](../../ui/src/chat.ts:296) |
| G11 | F2 | P2 static | Legacy warning is suppressed by `view.invalid ?? view.legacy` when the actual payload has `invalid:''`; empty requirements also return before any banner. Sessions listing has no audit-history field and offers attach for every row. No dedicated start-new action at halted history. Existing Branch is not proven safe for legacy audit histories. | [panels.ts:570](../../ui/src/panels.ts:570), [chat.ts:435](../../ui/src/chat.ts:435), [chat.ts:440](../../ui/src/chat.ts:440), [chat.ts:442](../../ui/src/chat.ts:442) |
| G12 | F2/F3 | P2 static | Stale predicate status and old result are shown, but causal file edits from `session.audit.external_edits` are omitted. UI does not distinguish the path that changed from requirements globally invalidated by the epoch advance. | [chat.ts:473](../../ui/src/chat.ts:473), [chat.ts:520](../../ui/src/chat.ts:520), [chat.ts:679](../../ui/src/chat.ts:679) |
| G13 | F2 | P2 static + payload bound | Blocked requirements have a status badge, but no inline revise/reopen form. Generic parked text refers to reopening a thread; stall parking settles requirements while independent work can continue. Stall reason/counters are not all in `session_status`; bounded audit projection can supply recent events/counters, not guaranteed complete historical reasons. | [chat.ts:416](../../ui/src/chat.ts:416), [chat.ts:457](../../ui/src/chat.ts:457), [chat.ts:525](../../ui/src/chat.ts:525), [panels.ts:581](../../ui/src/panels.ts:581) |
| G14 | F2/F5 | P2 static | Structured refusal `details` discarded by `summarise()`; contract skeleton is absent from UI even though `audit_projection` is callable. Inspector opens every non-pass predicate and rebuilds DOM on state updates, increasing noise and losing disclosure/focus state. | [chat.ts:845](../../ui/src/chat.ts:845), [chat.ts:495](../../ui/src/chat.ts:495), [chat.ts:695](../../ui/src/chat.ts:695), [main.ts:455](../../ui/src/main.ts:455) |
| G15 | F3 | P2 static + payload bound | Source revisions show new sections plus a link to the current note, not a byte-exact before/after promotion diff. Taxonomy edits are accepted in Settings after review in Staging; prepared write plans remain server-side. Current preview is not an exact rendered final Markdown mutation. CAS protects correctness but does not explain the change. | [views.ts:474](../../ui/src/views.ts:474), [views.ts:503](../../ui/src/views.ts:503), [views.ts:699](../../ui/src/views.ts:699), [settings.ts:1171](../../ui/src/settings.ts:1171) |
| G16 | F3/F2 | P2 static | Reply review appends below the current log, not bound to a reply identity; note references are literal strings, not openable evidence links. NAT-10's revision/turn identity and checked-span fields are not implemented; UI must not imply complete-note verification. | [chat.ts:264](../../ui/src/chat.ts:264), [chat.ts:274](../../ui/src/chat.ts:274), [api.ts:102](../../ui/src/api.ts:102) |
| G17 | F3/F1 | P2 static | Claim Run presents “Run it” with Docker warning only in tooltip, ignores `/api/claims/runs.docker` preflight, then compresses results to verdict/detail/version. No dedicated Workbench view consumes engagement state. Raw execution checkpoints do not constitute a Workbench console. | [chat.ts:589](../../ui/src/chat.ts:589), [chat.ts:593](../../ui/src/chat.ts:593), [main.ts:405](../../ui/src/main.ts:405), [pane.ts:23](../../ui/src/pane.ts:23) |
| G18 | F3 | P2 backend dependency | NAT-04/05 enforced output limits/quarantine/verified cleanup are proposed backend work, not states that the current UI can reliably discover. Timeout text must not imply verified containment/cleanup. Claim Run is Docker-only; host fallback is an explicitly different Workbench choice. | [chat.ts:593](../../ui/src/chat.ts:593), [pane.ts:153](../../ui/src/pane.ts:153), [main.ts:405](../../ui/src/main.ts:405) |
| G19 | F1/F5 | P1/P2 static | Error fidelity gaps: force-switch copy promises background completion but outcomes can fail; library Forget swallows rejection; effort slider remains on unsaved value after a failed POST; disabled run cancellation has no pending/completed feedback. Raw control state can imply more than the server confirmed. | [panels.ts:531](../../ui/src/panels.ts:531), [panels.ts:551](../../ui/src/panels.ts:551), [main.ts:168](../../ui/src/main.ts:168), [main.ts:445](../../ui/src/main.ts:445) |
| G20 | F5/F4 | P3 / existing visual concern | Search control row cannot wrap; Desk/Agenda are hidden behind document menu, which is itself behind a pane toggle when closed; topic decisions span Staging and Settings. Settings “+” conflicts with add/create conventions. | [views.ts:851](../../ui/src/views.ts:851), [style.css:237](../../ui/src/style.css:237), [pane.ts:210](../../ui/src/pane.ts:210), [main.ts:117](../../ui/src/main.ts:117) |
| G21 | F4/F5 | P3 static | Tabs lack arrow/Home/End/roving focus semantics; splitter is pointer-only despite separator role; view switch resets staged selection via load(true). No reduced-motion rule for action fade; touch message actions rely on hover/focus discovery. | [main.ts:181](../../ui/src/main.ts:181), [main.ts:193](../../ui/src/main.ts:193), [main.ts:471](../../ui/src/main.ts:471), [style.css:69](../../ui/src/style.css:69), [settings.ts:58](../../ui/src/settings.ts:58) |

## Handoff verification: UX-01 and ACCEPT-02

| Requested verification | Current result | Evidence / remaining gap |
|---|---|---|
| Legacy histories badged with new/fork path | Incomplete; ordinary Sessions menu is not history-aware | UX-01 read-only warning is defeated by the actual empty-invalid/nonempty-legacy payload and also by empty predicates. Start a new audited session is safer than claiming Branch preserves legacy authority. G11. |
| External edits identify file and invalidated closure | Partial | Predicate inspector shows stale status, authority, bound subject and historical result. `audit.external_edits` carries path/source/epoch but is not rendered; do not fabricate a per-file dependency graph. G12. |
| Eight unproductive interactions explain stop and offer revision | Partial | Default is 8, configurable through `audited_stall_limit`; requirements become blocked, not necessarily the entire session parked. Existing UI has evidence/accept/reject actions, no requirement revision form. G13. |
| Refusal details, skeleton, predicate inspection are scannable | Inspector implemented; other two incomplete | Structured details flattened; skeleton available only through explicit `audit_projection`; all unresolved predicates expanded. G14. |
| “Retry after review” actually reviews/retries | Fixed by honest semantics | Now “Mark reviewed; retry manually”, with explanation before/after decision. It records a decision only, correctly. `main.ts:412–434`, adapter contract test at `tests/test_obsidian_adapter_contract.py:57`. Keep this fix. |
| “Try again” recovers startup | Fixed for start errors; handshake path incomplete | `obsidian/src/main.ts:234` reruns render/ensureCore; typed stale error alone enables takeover. `/api/meta` mount failure clears cached Core but returns with no retry control (`main.ts:249`). Add retry there without automatic takeover. |
| Old sidebar restore crushes editor | Placement migration implemented; container adaptation incomplete | Main-workspace leaf activation is present. G03 remains for a narrow main split or root-width change. |

## Provenance surface audit

**Staging:** preserves important distinctions between approve-for-ingestion, accept-as-captured and accept-with-partial-coverage (`views.ts:405`). Lens review shows field origin and inline grounding (`views.ts:524`), and interrupted acceptance explains completed paths/original retention (`views.ts:465`). Revision tokens and explicit stale reload are strengths; preview fidelity is G15, not a claim of unguarded writes.

**Search:** shows coverage depth, score reasons, facets and advisories (`views.ts:898–980`). This supports source selection but not epistemic authority: accepted/captured/full depth are not truth predicates. Current file identity can be opened; a chain from source evidence revision through a particular checked claim is not uniformly exposed.

**Desk/Agenda:** agenda task links open notes (`pane.ts:81`); Desk records touched/pinned notes (`pane.ts:278`). These are work-context and recency signals, not verification. In Obsidian, `main.ts:240` delegates normal note opening to the host and returns before `DocPane.open()`; shared-pane automatic Desk touching must not be assumed to happen identically there.

**Chat:** separate tool result, advisory reply review and person permission surfaces are valuable. The existing predicate inspector explicitly distinguishes person acceptance from Core verification. Keep “quote located”, arithmetic result, source assertion, environmental replication and accepted artifact as separate lines, never one green trust score. G16/G17 concern locating and interpreting the evidence, not replacing backend verification.

## Operational payload limits

| Need | Existing source | What is safe now / unavailable |
|---|---|---|
| Ownership and watcher/writer health | `app.py:1150` `/api/meta.non_secret_health`; `app.py:3908` `/api/state.vault_lease`, shutdown, actions, active_profile_runs | Render existing health separately from SSE status; no assertion that a network response proves the OS lease healthy. |
| Dirty documents | `coordination.py:543` `/api/documents.leases[]` with path/editor/dirty/expires_in/baseline | Show current lease list and advisory expiry; next fetch is authority. |
| Schema-v5 rebuild | `index.py:43,514,563`, person tool `index_status` (`tools/library.py:229`) | Snapshot counts/stale/built_at only. No phase/percent; stats request can wait on the same worker. |
| Embedding continuation/errors | `tools/staging.py:26,34`, `promote.py:44,603` | Show returned `embedding_warnings`, `promotion.steps` and note `needs_attention` when fetched; not a live job queue. |
| Quarantine | `staging.py:180`, intake quarantine files | Immediate rejection/capture response may carry reason/location; no general quarantine listing API. Do not invent a Quarantine tab backed by hidden-file browsing. |
| Audited detail | `/api/tool/session_status`, `/api/tool/audit_projection` (`tools/sessions.py:306,604`) | Inspector, external edits and bounded recent events; omitted events stay omitted. Skeleton fetched on demand, no new store. |
| Paid-call task block | `scripts/g5_measure.py:358–438` | Offline gate; no runtime session reservation projection. Report unavailable; no automatic retry of uncertain paid effects. |
| Claim runs | `/api/claims/runs` (`app.py:4131`), `/api/claims/run` (`app.py:4369`) | Docker reason string and existing verdict/evidence/version. Not Workbench host fallback and not future NAT cleanup receipt. |
| Exact promotion/taxonomy diff | `tools/staging.py:173`, `/api/file` and `topic_map`; prepared plans in `tools/staging.py:255` | Existing bytes and proposed fields can be compared; exact composed bytes/plan are not published. Label semantic comparison and keep revision refusals. |

## Control/action-label inventory

Every event-bearing control declaration in main.ts and panels.ts was traced. Repeated controls generated from arrays share the same handler; this is a family inventory, not only a search for particular labels.

| Control family and anchor | Actual action and fidelity disposition |
|---|---|
| Settings “+” (`main:117`) | Opens native modal; behavior works, visible symbol mismatched. UI-12. |
| Library / Sessions / Checkpoints triggers (`main:125,150,155`) | Toggle popover and fetch data; fetch failure needs inline status. Modal ownership/focus UI-05. |
| Attach (`main:137`) | Opens file/note attach panel; remove chip (`main:524`) removes inserted reference, not the saved Inbox file. Make retention explicit. |
| Modes / model triggers (`main:139–148`) | Mode toggles permission/action menu; model awaits state/listing refresh. Modes contains actions unrelated to permission choice; split task navigation UI-12. |
| Open in browser/Obsidian (`main:160`) | Host link opens vault, not equivalent session, selected note or unsent draft; avoid “Continue” guarantees in tooltip. |
| Effort slider (`main:168`) | POSTS level, repaint on success, no rollback on failure; UI-02. No authority increase promised. |
| Send / Stop / Enter (`main:166,175,548`) | POST chat/cancel according to busy. G01/G02; UI-01. |
| Chat/Staging/Search tabs (`main:181,471`) | Switch local views; Staging reloads/reset selection, composer hidden outside chat. UI-06/UI-12. |
| Pane toggle / drag separator (`main:192,260`) | Toggle saved pane state, resize on pointer drag; label always “Show” even open, no keyboard resize. UI-04/UI-06. |
| Checkpoint choices (`main:417,433`) | Resolve only. Correct manual retry copy; dynamic choices must name decision, not execution. UI-02. |
| Cancel action (`main:445`) | Requests cancellation, does not prove instantaneous stop. Show “Stopping…” until authoritative completion; UI-02. |
| Notice dismiss (`main:542`) | Hides notice; does not resolve failure. Correct, but critical state must remain in Operations. |
| Continue/Retry hooks (`main:99,100,570`) | Send a new instruction/repeat text, not replay last failed tool effect. Label scoped accordingly; UI-01/UI-08. |
| Rewind/Branch (`main:599,615`) | Calls tool then applies/attaches result. Rewind discards messages, not already-applied writes; server min index protects it. Legacy branch correctness not established. |
| Permission radios (`panels:96`) | POST mode; native radio visually changes before response with no rollback. UI-02; two mounts also share radio name. |
| Queue action and Start/Back (`panels:108,133,138,143,146`) | Start gathers required inputs then POSTS actions. “Clear enrichment backlog” processes it rather than deleting; label “Process enrichment backlog”. Back restores menu; no API undo. |
| Use as lead anyway / Choose another (`panels:340,345`) | Explicit override save / dismiss pending choice. Default reason is prefilled, so records are not evidence of user-authored rationale. Preserve override boundary, improve wording, UI-11. |
| Model card click (`panels:483`) | Add next tier; clicking selected explains, does not deselect. All-three-selected requires clear/rebuild. UI-11. |
| Clear selection / tier context menu / Delete / long press (`panels:354,401,431,484–487`) | Clear ALL chat roles, or current service slot in slot mode. Existing Clear action is present; long press lacks touchcancel and may still click afterward. UI-02/UI-11. |
| Show all/matching / Cancel slot (`panels:418,420`) | Filter visible catalogue / return to settings; Cancel does not undo previously saved assignment. Accurate scope; keyboard/focus UI-05. |
| Profile this model (`panels:499`) | Ingests a model source into Staging, not a qualification test or immediate usable profile. Toast distinguishes this; label “Stage model profile for review”. |
| Library row/Open/force-switch (`panels:519,531,548,558`) | Switch locator and reload page; force leaves work on old Core, no guarantee it completes. Say “Leave work running”, disclose waiting questions timeout. |
| Forget library (`panels:551`) | Removes locator only; errors swallowed then list reloaded. UI-02. |
| New conversation / session row (`panels:577,581`) | Reset chat / attach history. Does not necessarily create/fork an audited session. UI-07. |

## Suggested sequence

Close draft-loss and misleading input behavior first (UI-01), then honest action feedback (UI-02) and CSS/container containment (UI-03/04). Scope focus handling before expanding the console (UI-05/06). Add lifecycle oversight and provenance surfaces (UI-07–10), then routing and navigation refinements (UI-11/12). UI-13 validates generated/installed artifacts. The design specs explicitly fence unsupported backend fields; missing progress, exact diff and NAT receipts cannot be solved by speculative UI state.


## Appendix A — Complete stylesheet rule-header audit

Every rule header in `ui/src/style.css` is listed, including media rules and comma-separated branches. Root scoping describes outgoing containment only. Generic descendants remain incoming-name exposure until namespaced; resets are still needed for host element selectors. No rule is omitted because its name looks specific.

| Line | Selector or at-rule | Disposition |
|---:|---|---|
| [4](../../ui/src/style.css:4) | `.librarian-root, #librarian-root` | owned root/theme variables |
| [12](../../ui/src/style.css:12) | `@media (prefers-color-scheme: dark)` | system preference; keep with owned selectors |
| [13](../../ui/src/style.css:13) | `#librarian-root` | owned root/theme variables |
| [21](../../ui/src/style.css:21) | `.host-obsidian` | owned root/theme variables |
| [27](../../ui/src/style.css:27) | `.lib-app *` | root-scoped outgoing; prefix local tokens against incoming rules |
| [28](../../ui/src/style.css:28) | `.lib-app` | root-scoped outgoing; prefix local tokens against incoming rules |
| [30](../../ui/src/style.css:30) | `.host-obsidian.lib-app` | owned root/theme variables |
| [31](../../ui/src/style.css:31) | `.lib-app button` | root-scoped outgoing; prefix local tokens against incoming rules |
| [32](../../ui/src/style.css:32) | `.lib-app a` | root-scoped outgoing; prefix local tokens against incoming rules |
| [33](../../ui/src/style.css:33) | `.lib-app :focus-visible` | root-scoped outgoing; prefix local tokens against incoming rules |
| [34](../../ui/src/style.css:34) | `.lib-app [hidden]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [35](../../ui/src/style.css:35) | `.lib-app header` | root-scoped outgoing; prefix local tokens against incoming rules |
| [36](../../ui/src/style.css:36) | `.lib-app header .title` | root-scoped outgoing; prefix local tokens against incoming rules |
| [37](../../ui/src/style.css:37) | `.lib-app header .crumb` | root-scoped outgoing; prefix local tokens against incoming rules |
| [38](../../ui/src/style.css:38) | `.lib-app header nav` | root-scoped outgoing; prefix local tokens against incoming rules |
| [39](../../ui/src/style.css:39) | `.lib-app header nav button` | root-scoped outgoing; prefix local tokens against incoming rules |
| [40](../../ui/src/style.css:40) | `.lib-app header nav button[aria-selected="true"]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [41](../../ui/src/style.css:41) | `.lib-app .live` | root-scoped outgoing; prefix local tokens against incoming rules |
| [42](../../ui/src/style.css:42) | `.lib-app .live.on` | root-scoped outgoing; prefix local tokens against incoming rules |
| [43](../../ui/src/style.css:43) | `.lib-app .anchor` | root-scoped outgoing; prefix local tokens against incoming rules |
| [44](../../ui/src/style.css:44) | `.lib-app .ghost` | root-scoped outgoing; prefix local tokens against incoming rules |
| [45](../../ui/src/style.css:45) | `.lib-app .push` | root-scoped outgoing; prefix local tokens against incoming rules |
| [46](../../ui/src/style.css:46) | `.lib-app .dim` | root-scoped outgoing; prefix local tokens against incoming rules |
| [47](../../ui/src/style.css:47) | `.lib-app .notice` | root-scoped outgoing; prefix local tokens against incoming rules |
| [51](../../ui/src/style.css:51) | `.lib-app header` | root-scoped outgoing; prefix local tokens against incoming rules |
| [52](../../ui/src/style.css:52) | `.lib-app .lib-body` | root-scoped outgoing; prefix local tokens against incoming rules |
| [53](../../ui/src/style.css:53) | `.lib-app .lib-main` | root-scoped outgoing; prefix local tokens against incoming rules |
| [54](../../ui/src/style.css:54) | `.lib-app main.chatview, .lib-app .view` | root-scoped outgoing; prefix local tokens against incoming rules |
| [55](../../ui/src/style.css:55) | `.lib-app main.chatview` | root-scoped outgoing; prefix local tokens against incoming rules |
| [56](../../ui/src/style.css:56) | `.lib-app .lib-resizer` | root-scoped outgoing; prefix local tokens against incoming rules |
| [57](../../ui/src/style.css:57) | `.lib-app .lib-resizer:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [58](../../ui/src/style.css:58) | `.lib-app .lib-pane` | root-scoped outgoing; prefix local tokens against incoming rules |
| [59](../../ui/src/style.css:59) | `.lib-app .lib-body.pane-closed .lib-pane, .lib-app .lib-body.pane-closed .lib-resizer` | root-scoped outgoing; prefix local tokens against incoming rules |
| [60](../../ui/src/style.css:60) | `@media (max-width: 900px)` | window-width/media rule; migrate layout conditions to root sizing |
| [61](../../ui/src/style.css:61) | `.lib-app .lib-resizer` | root-scoped outgoing; prefix local tokens against incoming rules |
| [62](../../ui/src/style.css:62) | `.lib-app .lib-pane` | root-scoped outgoing; prefix local tokens against incoming rules |
| [63](../../ui/src/style.css:63) | `.lib-app header .crumb` | root-scoped outgoing; prefix local tokens against incoming rules |
| [65](../../ui/src/style.css:65) | `.lib-app .log` | root-scoped outgoing; prefix local tokens against incoming rules |
| [66](../../ui/src/style.css:66) | `.lib-app .hint` | root-scoped outgoing; prefix local tokens against incoming rules |
| [67](../../ui/src/style.css:67) | `.lib-app .msg-wrap` | root-scoped outgoing; prefix local tokens against incoming rules |
| [68](../../ui/src/style.css:68) | `.lib-app .msg-wrap.user` | root-scoped outgoing; prefix local tokens against incoming rules |
| [69](../../ui/src/style.css:69) | `.lib-app .msg-actions` | root-scoped outgoing; prefix local tokens against incoming rules |
| [70](../../ui/src/style.css:70) | `.lib-app .msg-wrap:hover .msg-actions, .lib-app .msg-actions:focus-within` | root-scoped outgoing; prefix local tokens against incoming rules |
| [71](../../ui/src/style.css:71) | `.lib-app .msg-actions .icon-btn` | root-scoped outgoing; prefix local tokens against incoming rules |
| [72](../../ui/src/style.css:72) | `.lib-app .msg-actions .icon-btn[disabled]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [73](../../ui/src/style.css:73) | `.lib-app .msg-actions .icon-btn[disabled]:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [74](../../ui/src/style.css:74) | `.lib-app .msg` | root-scoped outgoing; prefix local tokens against incoming rules |
| [75](../../ui/src/style.css:75) | `.lib-app .msg p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [76](../../ui/src/style.css:76) | `.lib-app .msg pre` | root-scoped outgoing; prefix local tokens against incoming rules |
| [77](../../ui/src/style.css:77) | `.lib-app .msg.user` | root-scoped outgoing; prefix local tokens against incoming rules |
| [78](../../ui/src/style.css:78) | `.lib-app .tool` | root-scoped outgoing; prefix local tokens against incoming rules |
| [79](../../ui/src/style.css:79) | `.lib-app .tool code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [80](../../ui/src/style.css:80) | `.lib-app .tool.write` | root-scoped outgoing; prefix local tokens against incoming rules |
| [81](../../ui/src/style.css:81) | `.lib-app .tool.refused` | root-scoped outgoing; prefix local tokens against incoming rules |
| [82](../../ui/src/style.css:82) | `.lib-app .working` | root-scoped outgoing; prefix local tokens against incoming rules |
| [83](../../ui/src/style.css:83) | `.lib-app .error` | root-scoped outgoing; prefix local tokens against incoming rules |
| [84](../../ui/src/style.css:84) | `.lib-app .session-outcome` | root-scoped outgoing; prefix local tokens against incoming rules |
| [85](../../ui/src/style.css:85) | `.lib-app .session-outcome.closed` | root-scoped outgoing; prefix local tokens against incoming rules |
| [86](../../ui/src/style.css:86) | `.lib-app .session-outcome ul` | root-scoped outgoing; prefix local tokens against incoming rules |
| [87](../../ui/src/style.css:87) | `.lib-app .session-outcome p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [88](../../ui/src/style.css:88) | `.lib-app .ok` | root-scoped outgoing; prefix local tokens against incoming rules |
| [88](../../ui/src/style.css:88) | `.lib-app .err` | root-scoped outgoing; prefix local tokens against incoming rules |
| [89](../../ui/src/style.css:89) | `.lib-app .warn` | root-scoped outgoing; prefix local tokens against incoming rules |
| [90](../../ui/src/style.css:90) | `.lib-app .wl` | root-scoped outgoing; prefix local tokens against incoming rules |
| [91](../../ui/src/style.css:91) | `.lib-app .perm` | root-scoped outgoing; prefix local tokens against incoming rules |
| [92](../../ui/src/style.css:92) | `.lib-app .perm .row, .lib-app .question .row` | root-scoped outgoing; prefix local tokens against incoming rules |
| [93](../../ui/src/style.css:93) | `.lib-app .perm button, .lib-app .question button` | root-scoped outgoing; prefix local tokens against incoming rules |
| [94](../../ui/src/style.css:94) | `.lib-app .perm.done` | root-scoped outgoing; prefix local tokens against incoming rules |
| [95](../../ui/src/style.css:95) | `.lib-app .perm pre.diff` | root-scoped outgoing; prefix local tokens against incoming rules |
| [96](../../ui/src/style.css:96) | `.lib-app .perm pre.diff .add` | root-scoped outgoing; prefix local tokens against incoming rules |
| [97](../../ui/src/style.css:97) | `.lib-app .perm pre.diff .del` | root-scoped outgoing; prefix local tokens against incoming rules |
| [98](../../ui/src/style.css:98) | `.lib-app .plan` | root-scoped outgoing; prefix local tokens against incoming rules |
| [99](../../ui/src/style.css:99) | `.lib-app .plan h3` | root-scoped outgoing; prefix local tokens against incoming rules |
| [100](../../ui/src/style.css:100) | `.lib-app .plan ul` | root-scoped outgoing; prefix local tokens against incoming rules |
| [101](../../ui/src/style.css:101) | `.lib-app .plan li` | root-scoped outgoing; prefix local tokens against incoming rules |
| [102](../../ui/src/style.css:102) | `.lib-app .plan p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [103](../../ui/src/style.css:103) | `.lib-app .question` | root-scoped outgoing; prefix local tokens against incoming rules |
| [104](../../ui/src/style.css:104) | `.lib-app .question p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [105](../../ui/src/style.css:105) | `.lib-app .question input` | root-scoped outgoing; prefix local tokens against incoming rules |
| [106](../../ui/src/style.css:106) | `.lib-app .predicate-inspector` | root-scoped outgoing; prefix local tokens against incoming rules |
| [107](../../ui/src/style.css:107) | `.lib-app .predicate-inspector .inspector-scope` | root-scoped outgoing; prefix local tokens against incoming rules |
| [108](../../ui/src/style.css:108) | `.lib-app .requirement-card` | root-scoped outgoing; prefix local tokens against incoming rules |
| [109](../../ui/src/style.css:109) | `.lib-app .requirement-heading` | root-scoped outgoing; prefix local tokens against incoming rules |
| [110](../../ui/src/style.css:110) | `.lib-app .inspector-meta` | root-scoped outgoing; prefix local tokens against incoming rules |
| [111](../../ui/src/style.css:111) | `.lib-app .inspector-state` | root-scoped outgoing; prefix local tokens against incoming rules |
| [112](../../ui/src/style.css:112) | `.lib-app .state-pass, .lib-app .state-verified, .lib-app .state-human_accepted` | root-scoped outgoing; prefix local tokens against incoming rules |
| [113](../../ui/src/style.css:113) | `.lib-app .state-fail, .lib-app .state-failed, .lib-app .state-stale` | root-scoped outgoing; prefix local tokens against incoming rules |
| [114](../../ui/src/style.css:114) | `.lib-app .predicate-row` | root-scoped outgoing; prefix local tokens against incoming rules |
| [115](../../ui/src/style.css:115) | `.lib-app .predicate-row summary` | root-scoped outgoing; prefix local tokens against incoming rules |
| [116](../../ui/src/style.css:116) | `.lib-app .predicate-row summary code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [117](../../ui/src/style.css:117) | `.lib-app .predicate-detail` | root-scoped outgoing; prefix local tokens against incoming rules |
| [118](../../ui/src/style.css:118) | `.lib-app .predicate-detail p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [119](../../ui/src/style.css:119) | `.lib-app .warn-text` | root-scoped outgoing; prefix local tokens against incoming rules |
| [120](../../ui/src/style.css:120) | `.lib-app .inspector-actions` | root-scoped outgoing; prefix local tokens against incoming rules |
| [121](../../ui/src/style.css:121) | `.lib-app .inspector-action-row` | root-scoped outgoing; prefix local tokens against incoming rules |
| [122](../../ui/src/style.css:122) | `.lib-app .inspector-action-row input` | root-scoped outgoing; prefix local tokens against incoming rules |
| [123](../../ui/src/style.css:123) | `.lib-app .inspector-artifact` | root-scoped outgoing; prefix local tokens against incoming rules |
| [124](../../ui/src/style.css:124) | `.lib-app .inspector-artifact p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [125](../../ui/src/style.css:125) | `.lib-app .inspector-action-status` | root-scoped outgoing; prefix local tokens against incoming rules |
| [127](../../ui/src/style.css:127) | `.lib-app .composer` | root-scoped outgoing; prefix local tokens against incoming rules |
| [128](../../ui/src/style.css:128) | `.lib-app .chips` | root-scoped outgoing; prefix local tokens against incoming rules |
| [129](../../ui/src/style.css:129) | `.lib-app .chip` | root-scoped outgoing; prefix local tokens against incoming rules |
| [130](../../ui/src/style.css:130) | `.lib-app .chip button` | root-scoped outgoing; prefix local tokens against incoming rules |
| [131](../../ui/src/style.css:131) | `.lib-app textarea#lib-msg` | root-scoped outgoing; prefix local tokens against incoming rules |
| [132](../../ui/src/style.css:132) | `.lib-app .msg-box.has-attachments textarea#lib-msg` | root-scoped outgoing; prefix local tokens against incoming rules |
| [133](../../ui/src/style.css:133) | `.lib-app .attach-row` | root-scoped outgoing; prefix local tokens against incoming rules |
| [134](../../ui/src/style.css:134) | `.lib-app .attach-chip` | root-scoped outgoing; prefix local tokens against incoming rules |
| [135](../../ui/src/style.css:135) | `.lib-app .attach-chip .attach-name` | root-scoped outgoing; prefix local tokens against incoming rules |
| [136](../../ui/src/style.css:136) | `.lib-app .attach-remove` | root-scoped outgoing; prefix local tokens against incoming rules |
| [137](../../ui/src/style.css:137) | `.lib-app .attach-remove:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [138](../../ui/src/style.css:138) | `.lib-app .toolbar` | root-scoped outgoing; prefix local tokens against incoming rules |
| [139](../../ui/src/style.css:139) | `.lib-app pre.import-body` | root-scoped outgoing; prefix local tokens against incoming rules |
| [140](../../ui/src/style.css:140) | `.lib-app .lib-pane pre.code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [141](../../ui/src/style.css:141) | `.lib-app .lib-pane pre.code.err` | root-scoped outgoing; prefix local tokens against incoming rules |
| [142](../../ui/src/style.css:142) | `.lib-app .lib-pane .run-output h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [143](../../ui/src/style.css:143) | `.lib-app .toolbar .effort` | root-scoped outgoing; prefix local tokens against incoming rules |
| [144](../../ui/src/style.css:144) | `.lib-app .toolbar .effort input[type=range]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [145](../../ui/src/style.css:145) | `.lib-app .toolbar .effort .effort-value` | root-scoped outgoing; prefix local tokens against incoming rules |
| [146](../../ui/src/style.css:146) | `.lib-app .tb` | root-scoped outgoing; prefix local tokens against incoming rules |
| [147](../../ui/src/style.css:147) | `.lib-app .tb.icon` | root-scoped outgoing; prefix local tokens against incoming rules |
| [148](../../ui/src/style.css:148) | `.lib-app .tb[aria-expanded="true"]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [149](../../ui/src/style.css:149) | `.lib-app .send` | root-scoped outgoing; prefix local tokens against incoming rules |
| [150](../../ui/src/style.css:150) | `.lib-app .badge` | root-scoped outgoing; prefix local tokens against incoming rules |
| [152](../../ui/src/style.css:152) | `.lib-app .lib-popover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [153](../../ui/src/style.css:153) | `.lib-app header .lib-popover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [154](../../ui/src/style.css:154) | `.lib-app .lib-popover h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [155](../../ui/src/style.css:155) | `.lib-app .lib-popover h4.gap` | root-scoped outgoing; prefix local tokens against incoming rules |
| [156](../../ui/src/style.css:156) | `.lib-app #lib-modes` | root-scoped outgoing; prefix local tokens against incoming rules |
| [157](../../ui/src/style.css:157) | `.lib-app .opt` | root-scoped outgoing; prefix local tokens against incoming rules |
| [158](../../ui/src/style.css:158) | `.lib-app .opt:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [159](../../ui/src/style.css:159) | `.lib-app .opt small, .lib-app .menuitem small` | root-scoped outgoing; prefix local tokens against incoming rules |
| [160](../../ui/src/style.css:160) | `.lib-app .menuitem` | root-scoped outgoing; prefix local tokens against incoming rules |
| [161](../../ui/src/style.css:161) | `.lib-app .menuitem:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [162](../../ui/src/style.css:162) | `.lib-app #lib-models` | root-scoped outgoing; prefix local tokens against incoming rules |
| [163](../../ui/src/style.css:163) | `.lib-app #lib-models input[type=search]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [164](../../ui/src/style.css:164) | `.lib-app .tierbar` | root-scoped outgoing; prefix local tokens against incoming rules |
| [165](../../ui/src/style.css:165) | `.lib-app .tierbar .slot` | root-scoped outgoing; prefix local tokens against incoming rules |
| [166](../../ui/src/style.css:166) | `.lib-app .model-grid` | root-scoped outgoing; prefix local tokens against incoming rules |
| [167](../../ui/src/style.css:167) | `.lib-app .model-card-wrap` | root-scoped outgoing; prefix local tokens against incoming rules |
| [168](../../ui/src/style.css:168) | `.lib-app .profile-link` | root-scoped outgoing; prefix local tokens against incoming rules |
| [169](../../ui/src/style.css:169) | `.lib-app .model-card` | root-scoped outgoing; prefix local tokens against incoming rules |
| [170](../../ui/src/style.css:170) | `.lib-app .model-card:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [171](../../ui/src/style.css:171) | `.lib-app .model-card.sel` | root-scoped outgoing; prefix local tokens against incoming rules |
| [172](../../ui/src/style.css:172) | `.lib-app .model-card .model-name` | root-scoped outgoing; prefix local tokens against incoming rules |
| [173](../../ui/src/style.css:173) | `.lib-app .model-card .model-meta` | root-scoped outgoing; prefix local tokens against incoming rules |
| [174](../../ui/src/style.css:174) | `.lib-app .model-card .badge` | root-scoped outgoing; prefix local tokens against incoming rules |
| [175](../../ui/src/style.css:175) | `.lib-app .readiness` | root-scoped outgoing; prefix local tokens against incoming rules |
| [176](../../ui/src/style.css:176) | `.lib-app .readiness-chip` | root-scoped outgoing; prefix local tokens against incoming rules |
| [177](../../ui/src/style.css:177) | `.lib-app .readiness-chip.warn` | root-scoped outgoing; prefix local tokens against incoming rules |
| [178](../../ui/src/style.css:178) | `.lib-app .route-summary` | root-scoped outgoing; prefix local tokens against incoming rules |
| [179](../../ui/src/style.css:179) | `.lib-app .route-summary.warn` | root-scoped outgoing; prefix local tokens against incoming rules |
| [180](../../ui/src/style.css:180) | `.lib-app .dot, dialog .dot` | OUTGOING: unowned dialog branch |
| [181](../../ui/src/style.css:181) | `.lib-app .dot.nokey, dialog .dot.nokey` | OUTGOING: unowned dialog branch |
| [181](../../ui/src/style.css:181) | `.lib-app .dot.off, dialog .dot.off` | OUTGOING: unowned dialog branch |
| [182](../../ui/src/style.css:182) | `.lib-app .toast` | root-scoped outgoing; prefix local tokens against incoming rules |
| [183](../../ui/src/style.css:183) | `.lib-app .checkpoint` | root-scoped outgoing; prefix local tokens against incoming rules |
| [184](../../ui/src/style.css:184) | `.lib-app .checkpoint:first-of-type` | root-scoped outgoing; prefix local tokens against incoming rules |
| [185](../../ui/src/style.css:185) | `.lib-app .checkpoint p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [186](../../ui/src/style.css:186) | `.lib-app .checkpoint-evidence` | root-scoped outgoing; prefix local tokens against incoming rules |
| [187](../../ui/src/style.css:187) | `.lib-app .locked, dialog .locked` | OUTGOING: unowned dialog branch |
| [190](../../ui/src/style.css:190) | `.lib-app .view` | root-scoped outgoing; prefix local tokens against incoming rules |
| [191](../../ui/src/style.css:191) | `.lib-app .view-head` | root-scoped outgoing; prefix local tokens against incoming rules |
| [192](../../ui/src/style.css:192) | `.lib-app .split` | root-scoped outgoing; prefix local tokens against incoming rules |
| [193](../../ui/src/style.css:193) | `@media (max-width: 820px)` | window-width/media rule; migrate layout conditions to root sizing |
| [193](../../ui/src/style.css:193) | `.lib-app .split` | root-scoped outgoing; prefix local tokens against incoming rules |
| [194](../../ui/src/style.css:194) | `.lib-app .items` | root-scoped outgoing; prefix local tokens against incoming rules |
| [195](../../ui/src/style.css:195) | `.lib-app .item` | root-scoped outgoing; prefix local tokens against incoming rules |
| [196](../../ui/src/style.css:196) | `.lib-app .item.sel` | root-scoped outgoing; prefix local tokens against incoming rules |
| [197](../../ui/src/style.css:197) | `.lib-app .item small` | root-scoped outgoing; prefix local tokens against incoming rules |
| [198](../../ui/src/style.css:198) | `.lib-app .flag` | root-scoped outgoing; prefix local tokens against incoming rules |
| [199](../../ui/src/style.css:199) | `.lib-app .columns` | root-scoped outgoing; prefix local tokens against incoming rules |
| [200](../../ui/src/style.css:200) | `@media (max-width: 1000px)` | window-width/media rule; migrate layout conditions to root sizing |
| [200](../../ui/src/style.css:200) | `.lib-app .columns` | root-scoped outgoing; prefix local tokens against incoming rules |
| [201](../../ui/src/style.css:201) | `.lib-app .evidence` | root-scoped outgoing; prefix local tokens against incoming rules |
| [202](../../ui/src/style.css:202) | `.lib-app .staging .sections` | root-scoped outgoing; prefix local tokens against incoming rules |
| [203](../../ui/src/style.css:203) | `.lib-app .staging .sections h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [204](../../ui/src/style.css:204) | `.lib-app .staging .sections ul` | root-scoped outgoing; prefix local tokens against incoming rules |
| [205](../../ui/src/style.css:205) | `.lib-app .staging blockquote.lens-quote, .lib-app .staging blockquote.lens-instruction` | root-scoped outgoing; prefix local tokens against incoming rules |
| [206](../../ui/src/style.css:206) | `.lib-app .staging blockquote.lens-quote cite` | root-scoped outgoing; prefix local tokens against incoming rules |
| [207](../../ui/src/style.css:207) | `.lib-app .staging blockquote.lens-quote.small` | root-scoped outgoing; prefix local tokens against incoming rules |
| [208](../../ui/src/style.css:208) | `.lib-app .staging .sections li blockquote.lens-quote.small` | root-scoped outgoing; prefix local tokens against incoming rules |
| [209](../../ui/src/style.css:209) | `.lib-app .staging .detail h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [210](../../ui/src/style.css:210) | `.lib-app .result` | root-scoped outgoing; prefix local tokens against incoming rules |
| [211](../../ui/src/style.css:211) | `.lib-app .result p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [213](../../ui/src/style.css:213) | `.lib-app .search .facets` | root-scoped outgoing; prefix local tokens against incoming rules |
| [214](../../ui/src/style.css:214) | `.lib-app .search .facet h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [215](../../ui/src/style.css:215) | `.lib-app .search .facet` | root-scoped outgoing; prefix local tokens against incoming rules |
| [216](../../ui/src/style.css:216) | `.lib-app .search .facet h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [217](../../ui/src/style.css:217) | `.lib-app .search .chip` | root-scoped outgoing; prefix local tokens against incoming rules |
| [218](../../ui/src/style.css:218) | `.lib-app .search .chip[aria-pressed="true"]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [219](../../ui/src/style.css:219) | `.lib-app .search .tile` | root-scoped outgoing; prefix local tokens against incoming rules |
| [220](../../ui/src/style.css:220) | `.lib-app .search .tile.dismissed` | root-scoped outgoing; prefix local tokens against incoming rules |
| [221](../../ui/src/style.css:221) | `.lib-app .search .tile p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [222](../../ui/src/style.css:222) | `.lib-app .search .tile-head` | root-scoped outgoing; prefix local tokens against incoming rules |
| [223](../../ui/src/style.css:223) | `.lib-app .search .depth` | root-scoped outgoing; prefix local tokens against incoming rules |
| [224](../../ui/src/style.css:224) | `.lib-app .search .depth.full` | root-scoped outgoing; prefix local tokens against incoming rules |
| [225](../../ui/src/style.css:225) | `.lib-app .search .depth.partial, .lib-app .search .depth.captured` | root-scoped outgoing; prefix local tokens against incoming rules |
| [226](../../ui/src/style.css:226) | `.lib-app .search .group h3` | root-scoped outgoing; prefix local tokens against incoming rules |
| [227](../../ui/src/style.css:227) | `.lib-app .verdict` | root-scoped outgoing; prefix local tokens against incoming rules |
| [230](../../ui/src/style.css:230) | `.lib-app input[type=text], .lib-app input[type=search], .lib-app input[type=password], .lib-app select, .lib-app textarea.f, dialog input[type=text], dialog input[type=password], dialog select, dialog textarea.f` | OUTGOING: unowned dialog branch |
| [233](../../ui/src/style.css:233) | `.lib-app textarea.f, dialog textarea.f` | OUTGOING: unowned dialog branch |
| [234](../../ui/src/style.css:234) | `.lib-app textarea.f.short` | root-scoped outgoing; prefix local tokens against incoming rules |
| [235](../../ui/src/style.css:235) | `.lib-app label.f, dialog label.f` | OUTGOING: unowned dialog branch |
| [236](../../ui/src/style.css:236) | `.lib-app .primary, dialog .primary` | OUTGOING: unowned dialog branch |
| [237](../../ui/src/style.css:237) | `.lib-app .row2, dialog .row2` | OUTGOING: unowned dialog branch |
| [238](../../ui/src/style.css:238) | `.lib-app .row2.tight, dialog .row2.tight` | OUTGOING: unowned dialog branch |
| [239](../../ui/src/style.css:239) | `.lib-app .seg, dialog .seg` | OUTGOING: unowned dialog branch |
| [240](../../ui/src/style.css:240) | `.lib-app .seg button, dialog .seg button` | OUTGOING: unowned dialog branch |
| [241](../../ui/src/style.css:241) | `.lib-app .seg button[aria-pressed="true"], dialog .seg button[aria-pressed="true"]` | OUTGOING: unowned dialog branch |
| [242](../../ui/src/style.css:242) | `.lib-app .note, dialog .note` | OUTGOING: unowned dialog branch |
| [243](../../ui/src/style.css:243) | `.lib-app .note.inline, dialog .note.inline` | OUTGOING: unowned dialog branch |
| [245](../../ui/src/style.css:245) | `dialog.settings, dialog.reader` | OUTGOING: unowned dialog branch |
| [248](../../ui/src/style.css:248) | `dialog *` | OUTGOING: unowned dialog branch |
| [249](../../ui/src/style.css:249) | `dialog button` | OUTGOING: unowned dialog branch |
| [250](../../ui/src/style.css:250) | `dialog::backdrop` | OUTGOING: unowned dialog branch |
| [251](../../ui/src/style.css:251) | `dialog .dlg-head` | OUTGOING: unowned dialog branch |
| [252](../../ui/src/style.css:252) | `dialog .ghost` | OUTGOING: unowned dialog branch |
| [253](../../ui/src/style.css:253) | `dialog .push` | OUTGOING: unowned dialog branch |
| [254](../../ui/src/style.css:254) | `dialog .tabs` | OUTGOING: unowned dialog branch |
| [255](../../ui/src/style.css:255) | `dialog .tabs button` | OUTGOING: unowned dialog branch |
| [256](../../ui/src/style.css:256) | `dialog .tabs button[aria-selected="true"]` | OUTGOING: unowned dialog branch |
| [257](../../ui/src/style.css:257) | `dialog .page` | OUTGOING: unowned dialog branch |
| [258](../../ui/src/style.css:258) | `dialog .page .pre` | OUTGOING: unowned dialog branch |
| [259](../../ui/src/style.css:259) | `dialog .ok` | OUTGOING: unowned dialog branch |
| [259](../../ui/src/style.css:259) | `dialog .err, dialog .error` | OUTGOING: unowned dialog branch |
| [260](../../ui/src/style.css:260) | `dialog .srv` | OUTGOING: unowned dialog branch |
| [261](../../ui/src/style.css:261) | `dialog .confirm` | OUTGOING: unowned dialog branch |
| [262](../../ui/src/style.css:262) | `dialog .host-card` | OUTGOING: unowned dialog branch |
| [263](../../ui/src/style.css:263) | `dialog .host-card.new-host` | OUTGOING: unowned dialog branch |
| [264](../../ui/src/style.css:264) | `dialog .host-grid` | OUTGOING: unowned dialog branch |
| [265](../../ui/src/style.css:265) | `dialog .host-card input[type=number]` | OUTGOING: unowned dialog branch |
| [266](../../ui/src/style.css:266) | `dialog .host-card code` | OUTGOING: unowned dialog branch |
| [267](../../ui/src/style.css:267) | `@media (max-width: 540px)` | window-width/media rule; migrate layout conditions to root sizing |
| [267](../../ui/src/style.css:267) | `dialog .host-grid` | OUTGOING: unowned dialog branch |
| [268](../../ui/src/style.css:268) | `.lib-app .msg code, .lib-app .plan code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [269](../../ui/src/style.css:269) | `.lib-app .msg pre code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [270](../../ui/src/style.css:270) | `.lib-app header .ghost` | root-scoped outgoing; prefix local tokens against incoming rules |
| [271](../../ui/src/style.css:271) | `.lib-app header .title` | root-scoped outgoing; prefix local tokens against incoming rules |
| [272](../../ui/src/style.css:272) | `@media (max-width: 520px)` | window-width/media rule; migrate layout conditions to root sizing |
| [272](../../ui/src/style.css:272) | `.lib-app header` | root-scoped outgoing; prefix local tokens against incoming rules |
| [272](../../ui/src/style.css:272) | `.lib-app header nav button` | root-scoped outgoing; prefix local tokens against incoming rules |
| [275](../../ui/src/style.css:275) | `@media (max-width: 520px)` | window-width/media rule; migrate layout conditions to root sizing |
| [276](../../ui/src/style.css:276) | `.lib-app header` | root-scoped outgoing; prefix local tokens against incoming rules |
| [277](../../ui/src/style.css:277) | `.lib-app header .title` | root-scoped outgoing; prefix local tokens against incoming rules |
| [278](../../ui/src/style.css:278) | `.lib-app header .ghost` | root-scoped outgoing; prefix local tokens against incoming rules |
| [281](../../ui/src/style.css:281) | `.librarian-view.view-content` | owned integration boundary |
| [282](../../ui/src/style.css:282) | `.librarian-view .librarian-host` | owned integration boundary |
| [283](../../ui/src/style.css:283) | `.librarian-view .librarian-missing` | owned integration boundary |
| [286](../../ui/src/style.css:286) | `.lib-app .icon-btn` | root-scoped outgoing; prefix local tokens against incoming rules |
| [287](../../ui/src/style.css:287) | `.lib-app .icon-btn:hover, .lib-app .icon-btn[aria-expanded="true"], .lib-app .icon-btn[aria-pressed="true"]` | root-scoped outgoing; prefix local tokens against incoming rules |
| [288](../../ui/src/style.css:288) | `.lib-app .pane-head` | root-scoped outgoing; prefix local tokens against incoming rules |
| [289](../../ui/src/style.css:289) | `.lib-app .pane-crumbs` | root-scoped outgoing; prefix local tokens against incoming rules |
| [290](../../ui/src/style.css:290) | `.lib-app .pane-crumbs .sep` | root-scoped outgoing; prefix local tokens against incoming rules |
| [291](../../ui/src/style.css:291) | `.lib-app .pane-crumbs .crumb-here` | root-scoped outgoing; prefix local tokens against incoming rules |
| [292](../../ui/src/style.css:292) | `.lib-app .pane-crumbs .crumb-dir` | root-scoped outgoing; prefix local tokens against incoming rules |
| [293](../../ui/src/style.css:293) | `.lib-app .pane-crumbs .crumb-dir:hover` | root-scoped outgoing; prefix local tokens against incoming rules |
| [294](../../ui/src/style.css:294) | `.lib-app .pane-actions` | root-scoped outgoing; prefix local tokens against incoming rules |
| [295](../../ui/src/style.css:295) | `.lib-app .pane-menu` | root-scoped outgoing; prefix local tokens against incoming rules |
| [297](../../ui/src/style.css:297) | `.lib-app .pane-menu h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [298](../../ui/src/style.css:298) | `.lib-app .pane-menu .menuitem` | root-scoped outgoing; prefix local tokens against incoming rules |
| [299](../../ui/src/style.css:299) | `.lib-app .pane-menu .menuitem.dir` | root-scoped outgoing; prefix local tokens against incoming rules |
| [300](../../ui/src/style.css:300) | `.lib-app .pane-menu .folder-path` | root-scoped outgoing; prefix local tokens against incoming rules |
| [301](../../ui/src/style.css:301) | `.lib-app .pane-menu .move-form` | root-scoped outgoing; prefix local tokens against incoming rules |
| [302](../../ui/src/style.css:302) | `.lib-app .pane-menu .move-form h4` | root-scoped outgoing; prefix local tokens against incoming rules |
| [303](../../ui/src/style.css:303) | `.lib-app .pane-menu .picker` | root-scoped outgoing; prefix local tokens against incoming rules |
| [304](../../ui/src/style.css:304) | `.lib-app .doc .moved` | root-scoped outgoing; prefix local tokens against incoming rules |
| [305](../../ui/src/style.css:305) | `.lib-app .pane-body` | root-scoped outgoing; prefix local tokens against incoming rules |
| [306](../../ui/src/style.css:306) | `.lib-app .pad` | root-scoped outgoing; prefix local tokens against incoming rules |
| [309](../../ui/src/style.css:309) | `.lib-app .doc` | root-scoped outgoing; prefix local tokens against incoming rules |
| [310](../../ui/src/style.css:310) | `.lib-app .doc .doc-title` | root-scoped outgoing; prefix local tokens against incoming rules |
| [311](../../ui/src/style.css:311) | `.lib-app .doc h2` | root-scoped outgoing; prefix local tokens against incoming rules |
| [312](../../ui/src/style.css:312) | `.lib-app .doc h3` | root-scoped outgoing; prefix local tokens against incoming rules |
| [313](../../ui/src/style.css:313) | `.lib-app .doc h4, .lib-app .doc h5, .lib-app .doc h6` | root-scoped outgoing; prefix local tokens against incoming rules |
| [314](../../ui/src/style.css:314) | `.lib-app .doc p` | root-scoped outgoing; prefix local tokens against incoming rules |
| [315](../../ui/src/style.css:315) | `.lib-app .doc ul, .lib-app .doc ol, .lib-app .msg ul, .lib-app .msg ol` | root-scoped outgoing; prefix local tokens against incoming rules |
| [316](../../ui/src/style.css:316) | `.lib-app .doc li.task, .lib-app .msg li.task` | root-scoped outgoing; prefix local tokens against incoming rules |
| [317](../../ui/src/style.css:317) | `.lib-app .doc hr` | root-scoped outgoing; prefix local tokens against incoming rules |
| [318](../../ui/src/style.css:318) | `.lib-app .doc code, .lib-app .msg code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [319](../../ui/src/style.css:319) | `.lib-app .doc pre, .lib-app .msg pre` | root-scoped outgoing; prefix local tokens against incoming rules |
| [320](../../ui/src/style.css:320) | `.lib-app .doc pre code, .lib-app .msg pre code` | root-scoped outgoing; prefix local tokens against incoming rules |
| [321](../../ui/src/style.css:321) | `.lib-app .doc blockquote, .lib-app .msg blockquote` | root-scoped outgoing; prefix local tokens against incoming rules |
| [322](../../ui/src/style.css:322) | `.lib-app .callout` | root-scoped outgoing; prefix local tokens against incoming rules |
| [323](../../ui/src/style.css:323) | `.lib-app .callout-title` | root-scoped outgoing; prefix local tokens against incoming rules |
| [324](../../ui/src/style.css:324) | `.lib-app .callout-warning, .lib-app .callout-caution` | root-scoped outgoing; prefix local tokens against incoming rules |
| [325](../../ui/src/style.css:325) | `.lib-app .table-wrap` | root-scoped outgoing; prefix local tokens against incoming rules |
| [326](../../ui/src/style.css:326) | `.lib-app .doc table, .lib-app .msg table` | root-scoped outgoing; prefix local tokens against incoming rules |
| [327](../../ui/src/style.css:327) | `.lib-app .doc th, .lib-app .doc td, .lib-app .msg th, .lib-app .msg td` | root-scoped outgoing; prefix local tokens against incoming rules |
| [328](../../ui/src/style.css:328) | `.lib-app .doc thead th, .lib-app .msg thead th` | root-scoped outgoing; prefix local tokens against incoming rules |
| [329](../../ui/src/style.css:329) | `.lib-app .doc table.props` | root-scoped outgoing; prefix local tokens against incoming rules |
| [330](../../ui/src/style.css:330) | `.lib-app .doc table.props th, .lib-app .doc table.props td` | root-scoped outgoing; prefix local tokens against incoming rules |
| [331](../../ui/src/style.css:331) | `.lib-app .doc table.props th` | root-scoped outgoing; prefix local tokens against incoming rules |
| [332](../../ui/src/style.css:332) | `.lib-app .doc table.props tr` | root-scoped outgoing; prefix local tokens against incoming rules |
| [333](../../ui/src/style.css:333) | `.lib-app .usage, dialog .usage` | OUTGOING: unowned dialog branch |
| [334](../../ui/src/style.css:334) | `.lib-app .usage p, dialog .usage p` | OUTGOING: unowned dialog branch |
| [335](../../ui/src/style.css:335) | `.lib-app .usage a, dialog .usage a` | OUTGOING: unowned dialog branch |
| [338](../../ui/src/style.css:338) | `.lib-app .pane-lenses .desk-row` | root-scoped outgoing; prefix local tokens against incoming rules |
| [339](../../ui/src/style.css:339) | `.lib-app .pane-lenses .lens-name` | root-scoped outgoing; prefix local tokens against incoming rules |
| [340](../../ui/src/style.css:340) | `.lib-app .pane-lenses .lens-name small` | root-scoped outgoing; prefix local tokens against incoming rules |
| [343](../../ui/src/style.css:343) | `.lib-app .origin` | root-scoped outgoing; prefix local tokens against incoming rules |
| [344](../../ui/src/style.css:344) | `.lib-app .origin-source` | root-scoped outgoing; prefix local tokens against incoming rules |
| [345](../../ui/src/style.css:345) | `.lib-app .origin-person` | root-scoped outgoing; prefix local tokens against incoming rules |
| [346](../../ui/src/style.css:346) | `.lib-app .lens-quote .quote-context` | root-scoped outgoing; prefix local tokens against incoming rules |
| [347](../../ui/src/style.css:347) | `.lib-app .lens-quote mark` | root-scoped outgoing; prefix local tokens against incoming rules |
| [350](../../ui/src/style.css:350) | `.lib-app .offering-body` | root-scoped outgoing; prefix local tokens against incoming rules |
| [353](../../ui/src/style.css:353) | `.lib-app button.link, dialog button.link` | OUTGOING: unowned dialog branch |
| [354](../../ui/src/style.css:354) | `.lib-app button.link:hover, dialog button.link:hover, dialog button.link[aria-expanded="true"]` | OUTGOING: unowned dialog branch |
| [355](../../ui/src/style.css:355) | `dialog .key-entry .confirm` | OUTGOING: unowned dialog branch |
| [358](../../ui/src/style.css:358) | `.lib-app .model-card.rec` | root-scoped outgoing; prefix local tokens against incoming rules |
| [359](../../ui/src/style.css:359) | `.lib-app .model-card .rec-label` | root-scoped outgoing; prefix local tokens against incoming rules |

## Appendix B — Complete class-declaration audit in main.ts and panels.ts

Every literal/template `class:` declaration and direct className assignment in the requested two modules is included below. Expressions are retained so conditional modifiers are visible; dynamic names must be namespaced at emission as well as in CSS. This inventory does not assert that every generic token already causes a collision. Other emitters must migrate with their corresponding CSS rules (D5).

| Source | Declaration | Treatment |
|---|---|---|
| [ui/src/main.ts:57](../../ui/src/main.ts:57) | `"ghost lib-switch"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:58](../../ui/src/main.ts:58) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:63](../../ui/src/main.ts:63) | `"title"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:64](../../ui/src/main.ts:64) | `"crumb"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:65](../../ui/src/main.ts:65) | `"live"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:66](../../ui/src/main.ts:66) | `"chips"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:72](../../ui/src/main.ts:72) | `"attach-row"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:73](../../ui/src/main.ts:73) | `"msg-box"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:74](../../ui/src/main.ts:74) | `"tb"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:75](../../ui/src/main.ts:75) | `"tb"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:78](../../ui/src/main.ts:78) | `"effort-value"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:81](../../ui/src/main.ts:81) | `"effort tb"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:85](../../ui/src/main.ts:85) | `"notice"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:117](../../ui/src/main.ts:117) | `"tb icon"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:121](../../ui/src/main.ts:121) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:132](../../ui/src/main.ts:132) | `"tb icon"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:161](../../ui/src/main.ts:161) | `"tb"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:166](../../ui/src/main.ts:166) | `"send"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:179](../../ui/src/main.ts:179) | `"chatview"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:187](../../ui/src/main.ts:187) | `"composer"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:188](../../ui/src/main.ts:188) | `"toolbar"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:191](../../ui/src/main.ts:191) | `"icon-btn"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:193](../../ui/src/main.ts:193) | `"lib-resizer"` | Keep owned lib token; namespace any suffix/conditional tokens |
| [ui/src/main.ts:196](../../ui/src/main.ts:196) | `"lib-body"` | Keep owned lib token; namespace any suffix/conditional tokens |
| [ui/src/main.ts:197](../../ui/src/main.ts:197) | `"lib-main"` | Keep owned lib token; namespace any suffix/conditional tokens |
| [ui/src/main.ts:200](../../ui/src/main.ts:200) | `&#96;lib-app host-${opts.host}&#96;` | Keep owned lib token; namespace any suffix/conditional tokens |
| [ui/src/main.ts:201](../../ui/src/main.ts:201) | `"anchor"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:202](../../ui/src/main.ts:202) | `"anchor"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:203](../../ui/src/main.ts:203) | `"anchor"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:288](../../ui/src/main.ts:288) | `&#96;live ${live ? "on" : "off"}&#96;` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:388](../../ui/src/main.ts:388) | `"badge"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:413](../../ui/src/main.ts:413) | `"checkpoint-evidence"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:415](../../ui/src/main.ts:415) | `"checkpoint-help"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:426](../../ui/src/main.ts:426) | `"checkpoint"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:430](../../ui/src/main.ts:430) | `"row2"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:438](../../ui/src/main.ts:438) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:443](../../ui/src/main.ts:443) | `"chip"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:522](../../ui/src/main.ts:522) | `"attach-chip"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:523](../../ui/src/main.ts:523) | `"attach-name"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:524](../../ui/src/main.ts:524) | `"attach-remove"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/main.ts:542](../../ui/src/main.ts:542) | `"ghost push"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:75](../../ui/src/panels.ts:75) | `"lib-popover"` | Keep owned lib token; namespace any suffix/conditional tokens |
| [ui/src/panels.ts:93](../../ui/src/panels.ts:93) | `"opt"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:122](../../ui/src/panels.ts:122) | `"f"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:123](../../ui/src/panels.ts:123) | `"f"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:125](../../ui/src/panels.ts:125) | `"f"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:129](../../ui/src/panels.ts:129) | `"f"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:132](../../ui/src/panels.ts:132) | `"row2"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:133](../../ui/src/panels.ts:133) | `"primary"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:138](../../ui/src/panels.ts:138) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:142](../../ui/src/panels.ts:142) | `"gap"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:143](../../ui/src/panels.ts:143) | `"menuitem"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:145](../../ui/src/panels.ts:145) | `"gap"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:146](../../ui/src/panels.ts:146) | `"menuitem"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:296](../../ui/src/panels.ts:296) | `"readiness"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:298](../../ui/src/panels.ts:298) | `&#96;readiness-chip ${/blocked&#124;issue&#124;experimental&#124;unavailable&#124;stale/i.test(value) ? "warn" : ""}&#96;` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:309](../../ui/src/panels.ts:309) | `&#96;route-summary${good ? "" : " warn"}&#96;` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:310](../../ui/src/panels.ts:310) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:337](../../ui/src/panels.ts:337) | `"warn"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:339](../../ui/src/panels.ts:339) | `"row2 tight"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:340](../../ui/src/panels.ts:340) | `"primary"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:345](../../ui/src/panels.ts:345) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:400](../../ui/src/panels.ts:400) | `"slot"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:402](../../ui/src/panels.ts:402) | `"badge"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:403](../../ui/src/panels.ts:403) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:404](../../ui/src/panels.ts:404) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:415](../../ui/src/panels.ts:415) | `"tierbar"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:416](../../ui/src/panels.ts:416) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:418](../../ui/src/panels.ts:418) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:420](../../ui/src/panels.ts:420) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:421](../../ui/src/panels.ts:421) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:422](../../ui/src/panels.ts:422) | `"toast"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:428](../../ui/src/panels.ts:428) | `"tierbar"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:429](../../ui/src/panels.ts:429) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:430](../../ui/src/panels.ts:430) | `"tierbar"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:431](../../ui/src/panels.ts:431) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:433](../../ui/src/panels.ts:433) | `"note"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:436](../../ui/src/panels.ts:436) | `"toast"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:439](../../ui/src/panels.ts:439) | `"note locked"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:440](../../ui/src/panels.ts:440) | `"note"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:467](../../ui/src/panels.ts:467) | `"model-provider"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:468](../../ui/src/panels.ts:468) | `&#96;dot ${listing.status === "ready" ? "" : listing.status === "no key" ? "nokey" : "off"}&#96;` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:469](../../ui/src/panels.ts:469) | `"model-grid"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:478](../../ui/src/panels.ts:478) | `&#96;model-card${at >= 0 ? " sel" : ""}${rec ? " rec" : ""}&#96;` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:489](../../ui/src/panels.ts:489) | `"badge"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:490](../../ui/src/panels.ts:490) | `"model-name"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:490](../../ui/src/panels.ts:490) | `"model-meta"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:491](../../ui/src/panels.ts:491) | `"model-meta"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:493](../../ui/src/panels.ts:493) | `"rec-label"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:494](../../ui/src/panels.ts:494) | `"model-card-wrap"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:498](../../ui/src/panels.ts:498) | `"profile-link"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:502](../../ui/src/panels.ts:502) | `"note"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:516](../../ui/src/panels.ts:516) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:517](../../ui/src/panels.ts:517) | `"note"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:531](../../ui/src/panels.ts:531) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:534](../../ui/src/panels.ts:534) | `"error"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:541](../../ui/src/panels.ts:541) | `"f"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:546](../../ui/src/panels.ts:546) | `"menuitem desk-row"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:547](../../ui/src/panels.ts:547) | `"wl"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:550](../../ui/src/panels.ts:550) | `"icon-btn"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:555](../../ui/src/panels.ts:555) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:556](../../ui/src/panels.ts:556) | `"gap"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:557](../../ui/src/panels.ts:557) | `"row2 tight"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:558](../../ui/src/panels.ts:558) | `"ghost"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:559](../../ui/src/panels.ts:559) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:562](../../ui/src/panels.ts:562) | `"error"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:572](../../ui/src/panels.ts:572) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:577](../../ui/src/panels.ts:577) | `"menuitem"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:579](../../ui/src/panels.ts:579) | `"gap"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:581](../../ui/src/panels.ts:581) | `"menuitem"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:584](../../ui/src/panels.ts:584) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:585](../../ui/src/panels.ts:585) | `"dim"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
| [ui/src/panels.ts:587](../../ui/src/panels.ts:587) | `"error"` | Rename owned tokens/modifiers to lib-*; preserve host integration tokens only |
