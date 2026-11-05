# UI wave status

Baseline assessment of bce35ef against execution-queue.json, checked on 0cb1bd1.

| Packet | Baseline | Evidence and remaining work |
|---|---|---|
| MF-031 | Partial | settings.ts:121 and panels.ts:250 provide role selection and the override gate. Smoke selects OCR separately. Explicit suffix clearing and effort inheritance copy remain. |
| MF-032 | Partial | settings.ts:51 and style.css:369 implement the wide modal, sidebar and compact selector. Smoke covers context retention and header Settings. Global model access and broader form retention need work. |
| MF-033 | Partial | settings.ts:229,524,981 cover key management, folder permissions and chat context. Hosts and per-server tool policies are expanded by default. Sandbox output permission needs its own control. |
| MF-034a | Partial | main.ts:216 keeps Settings in the header. pane.ts:227 mixes navigation and note actions. An empty Plan still opens on desktop. |
| MF-034b | Partial | views.ts:89 and :517 expose evidence layout and preserve note content. Counts, triage hierarchy, batch decisions and per-library position remain. |
| MF-034c | Not met | views.ts Search constructor renders query, filters and submit in one row. |

## Integration checkpoint

| Packet | Current state | Delivered and remaining |
|---|---|---|
| MF-025 | Partial | Arrow/Home/End view navigation and bounded keyboard splitter. Touch cancellation, reduced motion and timer disposal added. Browser smoke covers focus return, resize and overlays. Physical touch and native hotkeys still need real-host checks. |
| MF-026 | Partial | Health exposes writer, index, watcher, vault lease and current document leases. Polls at ten seconds after settlement while Health is open. Errors retain the current panel's prior snapshot and timestamp. Accepted items display Core-provided derived embedding warnings. Forced network loss and injected embedding failure need dedicated regression coverage. |
| MF-031 | Partial | Explicit role-suffix clearing with confirmation, separate service clear and shared-default copy. Existing experimental-lead consent flow exercised. Direct clear and rollback across custom hosts need dedicated tests. |
| MF-032 | Partial | Persistent header Models and Settings entries alongside the existing settings rail. Context/topic draft retention is exercised. A wider pass on unsaved host and project forms remains. |
| MF-033 | Partial | Host details and individual tool policies collapse. Sandbox output has a permission control and an explanation in chat. Existing project permissions retained. Sandbox output boundary choices still need a dedicated walkthrough. |
| MF-034a | Implemented | Note/Browse/Plan/This week are visible choices with a compact selector. Note actions are scoped to the current note. Explicit pane preference survives reload. Fresh profiles start with the pane closed. Document links open the reader. |
| MF-034b | Partial | Filter-specific source counts, staging purpose, distinct processing/acceptance copy, selected item styling, per-library position within the browser session, and evidence layout based on available review space. Bulk defer/approve waits on a Core revision guard. |
| MF-034c | Implemented | Query and submit occupy the first row. Filters wrap on a separate row. Installed-wheel and responsive browser checks cover the layout. |
| MF-035 | Partial | Exact wheel in an external environment, packaged Edge search and Settings, Cowork overlap, DOM containment, bundle hashes and adapter retry/takeover/disposal harness. Native Obsidian and mixed-host hotkeys remain open. |
| MF-027 | Deferred | Reply-review identity, byte previews and Claim Run preflight remain in the backend-dependent queue. |
| New result payloads | Partial | Explicit workflow recovery on chat tool results, macro uncertainty guidance, TTS spent-or-held label and sandbox output disposition. Durable macro replay identity and recovery from the background chip still need work. |

The commit containing this checkpoint can be located with `git log -1 -- ui/obsidian-view-smoke.mjs`.
