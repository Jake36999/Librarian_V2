# Prioritized UI implementation packets

2026-11-04 · specifications only; no packet has been implemented by this review. See [gap matrix](UI-REVIEW.md) and [designs](UI-DESIGNS.md). Sizes S/M are bounded implementation estimates, not measured effort. Keep vanilla DOM/CSS and current payloads/person tools. IDs here are UI-01..13, distinct from NAT backend packets.

## Execution and test conventions

Implement from `ui/src`, then run `npm run check` and build both distributions through their existing scripts; never hand-edit `src/resource_librarian/ui/*`. Existing esbuild outputs currently match. Preserve current smoke's injected `.popover/.grid/.card` collision checks and revision/refusal tests. Keep `ui/packaged-smoke.mjs` an installed-Core boundary: no PYTHONPATH/demo launch or real-library mutations. Use a temporary installed test vault supplied by its harness. Mocked GET/POST faults below test rendering/interaction, not provider/OS truth; restore routes with `page.unroute()` after each case. Re-run the unmocked read-only packaged Search afterward.

The current scripts import `playwright-core`, not `@playwright/test`. Use their existing boolean `expect(cond, label)` in smoke; add the same small helper (or equivalent throws) to packaged smoke. The following helpers/assertions are **literal proposed additions**, not claims that current code passes them. Proposed data-testid values are new DOM hooks introduced by the corresponding packet and carry no business state.

```js
const check = async (condition, label) => {
  if (!(await condition)) throw new Error(label);
};
const within = async (child, parent) => {
  const [a, b] = await Promise.all([child.boundingBox(), parent.boundingBox()]);
  return !!a && !!b && a.x >= b.x - 1 && a.y >= b.y - 1
    && a.x + a.width <= b.x + b.width + 1;
};
const focused = (locator) => locator.evaluate(el => el === document.activeElement);
// Hook names describe views, not API/schema additions.
const root = page.locator('.librarian-root');
```

All waits must observe a request, DOM state, or bounded assertion; no fixed sleep to hide races. Add reusable fixtures to `tests/ui_demo_core.py` as necessary using real session/staging tools; do not replace backend closure semantics with fake frontend state. Prefer precise role/test-id selectors over toolbar nth-child positions. Fixtures must name session and requirement IDs and use existing schema fields only.

| Packet | Size / priority | Depends on | Done only when |
|---|---|---|---|
| UI-01 Composer admission and Stop | S / P1 | none | Rejected draft/attachment references survive, explicit Stop is separate from Enter, pending admission prevents duplicate POST, later typed text is not cleared. Transport ambiguity prompts state inspection, no automatic resend. |
| UI-02 Action truth and feedback | M / P1/P2 | UI-01 for shared mutation pattern | Radios/effort reconcile on errors, Forget errors visible, clear-all scope explicit, cancellation pending reflected, checkpoint resolution never replays effects, meta mount-failure retry available. |
| UI-03 CSS isolation | M / P1 | none | All requested selectors/classes inventoried and owned tokens migrated across emitters, all dialog rules rooted, foreign dialog unchanged, existing model-host collision test retained, generated CSS parity checked. |
| UI-04 Root-width layout | M / P1 | UI-03 | Layout reacts to leaf width independent of window, saved split clamped, root-contained header/popovers/dialogs, composer and Search usable at narrow widths. Observer/timers disposed. |
| UI-05 Overlay focus and host keys | M / P2 | UI-03/04 | Async content gets usable focus, Escape is owned and restores focus, native dialog trap retained, two mounts do not share IDs/radio groups, pane listeners removed. Real Obsidian hotkeys checked separately. |
| UI-06 Tabs, splitter and touch ergonomics | S / P3 | UI-04/05 | Tab semantics implemented, keyboard split resizing bounded, long press cancels on movement/touchcancel and cannot clear then click-reselect, reduced motion and touch action discoverability covered. |
| UI-07 Legacy and stale oversight | M / P2 | UI-05 | Empty legacy histories show read-only banner, new audited session path works, recorded edit paths and stale requirements displayed without invented causal mappings. |
| UI-08 Blocked requirements and diagnostics | M / P2 | UI-07 | Inline revision preserves predicates/verifiers, refreshes real session state, shows genuine reason or unavailable; structured refusal details and on-demand contract skeleton accessible without flooding normal chat. |
| UI-09 Operations and derived failures | M / P2 | UI-02/05 | Health/dirty leases separate from SSE; accepted-with-embedding-warning visible. Unknown index progress/quarantine/paid-call status explicitly unavailable; no fake progress bars or charges. |
| UI-10 Evidence comparison and reply/execution review | M / P2 | UI-07/09 | Existing bytes/proposed sections compared with honest limitations; advisory challenges open note context, late unbound reviews never attached to a guessed reply; Docker availability visible, no host fallback in Claim Run. NAT-dependent receipt features remain explicitly open. |
| UI-11 Model-role selection | M / P2 | UI-02/05 | Role-first DOM controls submit current tiers contract, preserve role/fallback semantics, retain server override gate, explicit service clear; no new routing authority. |
| UI-12 Research navigation and disclosure | M / P3 | UI-04/08 | Labelled Settings, Desk/This week links and separate Work actions use existing methods; return from Settings preserves staging selection/edits unless user chooses destructive reload. |
| UI-13 Installed and adapter evidence | S / P1 assurance | UI-01..12 slices | Source tests and in-memory parity pass; installed-wheel browser and adapter runtime checks run with artifact/host identity. Real Obsidian mixed-host/Docker checks remain a separate ACCEPT-02 record. |

## Assertions by packet

### UI-01 — Admission failure, input preservation, explicit stop

Add to `ui/smoke.mjs`, before selecting any model; fault only admission and count requests. Existing fixture `/api/state.busy` can be mocked for the busy case, or use its deterministic scripted turn barrier.

```js
let chatPosts = 0, cancelPosts = 0;
await page.route('**/api/chat', route => {
  chatPosts++;
  return route.fulfill({status:409,contentType:'application/json',
    body:JSON.stringify({error:'forced admission rejection'})});
});
await page.getByRole('textbox',{name:'Message',exact:true}).fill('keep this draft');
await page.getByRole('textbox',{name:'Message',exact:true}).press('Enter');
await page.getByRole('alert').filter({hasText:'forced admission rejection'}).waitFor();
await check(page.locator('#lib-msg').inputValue().then(v=>v==='keep this draft'),'draft survives 409');
await check(chatPosts===1,'one admission attempt');
await page.unroute('**/api/chat');
```

Add fixture case: route existing `/api/state` response through `route.fetch/json`, change only `busy:true`, reload; intercept cancel with a deferred response and listen to requests. Fill `next question`, press Enter, assert cancelPosts remains 0, composer remains unchanged, then click `getByRole('button',{name:'Stop reply',exact:true})`, wait for cancel request, assert count 1 and `Stopping reply…` status. Release response, emit deterministic turn_done, assert Send returns and draft remains. Add delayed-success case: type a newer draft while POST is pending, then fulfil; assert newer text survives. Attach a fixture file first and assert `getByTestId('lib-attachment-reference')` still exists after 409. An uploaded file remains on disk; don't assert deletion.

`packaged-smoke.mjs`: run the 409 test against a routed response and verify no real `/api/chat` reaches installed Core, then unroute and run normal read-only Search. Do not incur a model call.

### UI-02 — Reconcile failures and preserve ACCEPT-02 fixes

In `smoke.mjs` mock `/api/effort` to 409 after saving the prior slider value; set range to another value and dispatch change. Assert restored `inputValue()` equals prior value and alert shows the refusal. Repeat for `/api/mode`, asserting the previously confirmed radio remains checked. Forget request rejection must leave the row and visible error.

```js
const decisions = page.getByTestId('lib-checkpoint-write-conflict');
await check(decisions.getByRole('button',{name:'Mark reviewed; retry manually',exact:true}).count().then(n=>n===1),'truthful review label');
const resolve = page.waitForRequest(r=>new URL(r.url()).pathname==='/api/checkpoints/resolve');
await decisions.getByRole('button',{name:'Mark reviewed; retry manually',exact:true}).click();
await check(resolve.then(r=>r.postDataJSON().choice==='retry_after_review'),'records original decision enum');
await page.getByRole('alert').filter({hasText:'not retried'}).waitFor();
await check(blockedWriteRequests===0,'resolution never replays write');
```

`blockedWriteRequests` must count the fixture's actual blocked operation endpoint after initial refusal, not all tool traffic. In packaged smoke, inject a checkpoint in a routed state response, intercept resolve, apply the same assertions and prove no write tool invoked. Restore routes. In adapter runtime fixture test ordinary retry calls start with takeover false; typed StaleCoreLease retry sets true; protocol-handshake retry calls ensureCore again without true. Mock start/meta, not OS takeover.

### UI-03 — Both CSS directions and namespace inventory

`smoke.mjs`: retain lines 27–58's model-card hostile styles. Add a foreign native dialog containing input/button/.tabs/.page before mounting a second isolated UI; capture computed properties before and after loading shipped stylesheet. Assert unchanged foreign styles. Add host stress rules for old generic names and check owned controls still wrap and fit.

```js
await page.addStyleTag({content:`
  .row,.row2,.list,.item,.badge,.header,.body,.tabs,.page,.slot {height:9px!important;overflow:hidden!important}
  .popover,.card,.grid {display:flex!important;flex-direction:row!important}
  button {height:32px;white-space:nowrap}
`});
const model = page.getByTestId('lib-model-card').first();
await check(model.evaluate(el=>el.clientHeight>=el.scrollHeight),'model card not clipped by host height');
await check(model.evaluate(el=>getComputedStyle(el).whiteSpace==='normal'),'model card wraps');
await check(page.getByTestId('lib-model-grid').evaluate(el=>getComputedStyle(el).display==='grid'),'owned grid survives');
await check(JSON.stringify(foreignAfter)===JSON.stringify(foreignBefore),'foreign dialog unchanged');
```

`foreignBefore/After` are captured for the same dialog with the same host CSS; compare boxSizing/font/padding/colour/display/height. Do not count native-dialog UA differences as CSS regressions. Run matching checks with the installed CSS in packaged smoke. Community plugins using `!important` against **new lib-prefixed names** are outside the promise.

Add exact structural checks to `tests/test_obsidian_adapter_contract.py` alongside its browser evidence, without replacing the runtime test:

```python
def test_shared_css_has_no_global_dialog_branches():
    import re
    css = (ROOT / 'ui/src/style.css').read_text(encoding='utf-8')
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    headers = re.findall(r'([^{}]+)\{', css)
    for header in headers:
        if header.strip().startswith('@'):
            continue
        for selector in header.split(','):
            selector = selector.strip()
            assert not re.match(r'^(dialog|button|input|select|textarea|\*)(?=[\s.:#\[]|$)', selector), selector
    assert (ROOT/'ui/src/style.css').read_bytes() == (ROOT/'src/resource_librarian/ui/app.css').read_bytes()
```

This checks outgoing branches/parity, not incoming theme immunity; runtime checks remain mandatory. Update the existing obsolete literal-class expectations when owned names change rather than deleting their intent.

### UI-04 — Split-pane layout independent of viewport

Add identical root-width assertions to both browser scripts; packaged script uses installed CSS. At a wide window, resize only the mounted root. Then resize viewport separately and test saved oversized preference on reload.

```js
await page.setViewportSize({width:1440,height:1000});
await root.evaluate(el=>{el.style.width='420px';});
await page.waitForFunction(()=>document.querySelector('.librarian-root')?.dataset.libLayout==='narrow');
await check(root.evaluate(el=>el.scrollWidth<=el.clientWidth+1),'leaf has no horizontal overflow');
await check(page.getByTestId('lib-header').evaluate(el=>el.scrollWidth<=el.clientWidth+1),'header fits narrow leaf');
await page.getByRole('tab',{name:'Search',exact:true}).click();
const query = page.getByRole('searchbox',{name:'Search query',exact:true});
await check(query.boundingBox().then(b=>!!b && b.width>=280),'query retains useful width in 420px leaf');
await check(within(query,root),'search fits root');
```

The >=280px value is this design's acceptance target, not a published universal standard. Open each header popover and Settings; assert within(root), and for dialog assert bottom <= root bottom/viewport available bound. At 420px, selecting Document must provide Back to chat and restore draft. At wide root, oversized saved pane width must leave main >=360px; test 320/420/760/1100 root widths, including a tall window/short leaf to exercise vertical scroll. Restore root style after test.

### UI-05 — Escape and focus ownership

In both browser scripts delay model GET response, open picker, release listing, then assert focus inside the loaded picker. Verify ordinary native dialog Tab cycle stays within dialog; Escape closes only that dialog, returning to Settings trigger. Test two mounted roots using exported Librarian.mount and a mocked base; keep all fixture IDs/radio names unique.

```js
const trigger = page.getByRole('button',{name:'Choose models',exact:true});
await trigger.click();
await page.getByTestId('lib-model-card').first().waitFor();
await check(page.getByTestId('lib-model-popover').evaluate(el=>el.contains(document.activeElement)),'loaded picker owns focus');
await page.keyboard.press('Escape');
await check(focused(trigger),'Escape returns focus');
await check(hostEscapeEvents===0,'handled Escape does not bubble to host');
await page.locator('#host-outside-input').focus();
await page.keyboard.press('Escape');
await check(hostEscapeEvents===1,'unowned Escape remains available to host');
```

Fixture adds `host-outside-input` and a bubble listener counting Escape, before mounting. This checks bubble ownership only; record that actual Obsidian capture handlers remain a manual gate. Mount, dispose, remount twice and count handler effects; no leaked pane listener should close or refocus another view.

### UI-06 — Semantics and touch

```js
await page.getByRole('tab',{name:'Chat',exact:true}).focus();
await page.keyboard.press('ArrowRight');
await check(focused(page.getByRole('tab',{name:'Staging',exact:true})),'roving tab focus');
const split = page.getByRole('separator',{name:'Resize document pane',exact:true});
const old = Number(await split.getAttribute('aria-valuenow'));
await split.focus(); await page.keyboard.press('ArrowLeft');
await check(split.getAttribute('aria-valuenow').then(v=>Number(v)!==old),'keyboard resizes pane');
```

Use the same semantics assertions in packaged smoke. For model clearing, touchstart then touchcancel the selected card, advance a controlled page clock >600ms, assert `/api/tiers` clear count 0. Long-press completed must clear once without subsequent pick POST. Check reduced-motion computed transitionDuration is `0s` after `page.emulateMedia({reducedMotion:'reduce'})`. No real time sleeps.

### UI-07 — Legacy and stale histories

Create/mount fixtures using existing legacy session loader fixtures where possible; a routed state response with `predicate_inspector:{requirements:[],invalid:'',legacy:'legacy history',actionable:false}` specifically tests the early-return defect. Repeat with nonempty requirements and `invalid:''` to catch the nullish-coalescing defect too. For stale state use actual audit fixture and external edit + resume, then assert:

```js
await check(page.getByRole('status').filter({hasText:'Read-only audit history'}).isVisible(),'empty legacy banner');
await check(page.getByRole('button',{name:'Start new audited session',exact:true}).isVisible(),'new session path');
await check(page.getByRole('button',{name:'Accept artifact',exact:true}).count().then(n=>n===0),'no legacy acceptance');
await check(page.getByTestId('lib-session-edits').getByText('Sources/changed.md',{exact:true}).isVisible(),'changed file is named');
await check(page.getByTestId('lib-requirement-R1').getByText('stale',{exact:true}).first().isVisible(),'stale requirement visible');
await check(page.getByText('Changes recorded for this session',{exact:true}).isVisible(),'no false per-file dependency claim');
```

Use separate loaded fixtures for legacy and stale assertions. New-session button must POST open_session with purpose audited then attach returned ID; assert old session did not receive a mutation. Packaged smoke can use routed GET/state history for display tests only; do not create real sessions in an arbitrary installed library. Unmocked fixture/real tool transitions belong to smoke's disposable vault.

### UI-08 — Revision preserves binding and diagnostics disclose bounds

Fixture R1 has existing text, `predicates:['the quote is present']`, verifier `quote.located` with `{evidence:'E1'}`, and blocked status. Deliver the reason through a real live tool_result with result.stalled, not session.history (which contains phase names). Use the UI revision form and inspect request, not merely new text.

```js
await page.getByRole('button',{name:'Revise and reopen R1',exact:true}).click();
await page.getByRole('textbox',{name:'Requirement text',exact:true}).fill('Revised research requirement');
const saved = page.waitForRequest(r=>new URL(r.url()).pathname==='/api/tool/set_requirement');
await page.getByRole('button',{name:'Save requirement revision',exact:true}).click();
const body = (await saved).postDataJSON();
await check(body.arguments.requirement_id==='R1','correct requirement');
await check(JSON.stringify(body.arguments.predicates)===JSON.stringify(['the quote is present']),'preserves predicates');
await check(body.arguments.verifiers['the quote is present'].params.evidence==='E1','preserves verifier subject');
await page.getByTestId('lib-requirement-R1').getByText('revision 2',{exact:true}).waitFor();
```

Add exact assertions for collapsed `details` refusal JSON until user expands, then rule-specific detail visible; skeleton absent until a user opens “Proposed contract”, then `/api/tool/audit_projection` called once. A `fits:false` fixture shows narrowing guidance, never an actionable admit. Resume without a live result shows “Detailed stop reason is not exposed here”; do not fake a reason inside history or recent_events. Read-only rendering/route assertions can be duplicated in packaged smoke; mutation uses disposable real fixture only.

### UI-09 — Operations are not connectivity

Use real `/api/meta` response shape through route.fetch, setting writer closed and watcher status error; `/api/documents` returns one valid lease. Keep SSE connected. The warning must remain visible in Search and Staging too.

```js
await page.getByRole('button',{name:'Operations details',exact:true}).click();
await check(page.getByTestId('lib-core-health').getByText('closed',{exact:true}).isVisible(),'writer failure visible despite connected stream');
await check(page.getByTestId('lib-document-leases').getByText('Sources/edited.md',{exact:true}).isVisible(),'dirty note named');
await check(page.getByTestId('lib-index-snapshot').getByRole('progressbar').count().then(n=>n===0),'no invented percent progress');
await check(page.getByTestId('lib-index-snapshot').getByText('Rebuild progress is not exposed',{exact:true}).isVisible(),'progress limitation explicit');
```

For acceptance fixture return real embedding_warnings after derived encoder failure and assert “Source accepted; embedding update failed” plus returned next action; accepted note remains in library. In packaged smoke mock health/read-only documents only; assert unauthenticated/failed health updates show unavailable, never healthy fallback. A missing jobs/paid ledger/quarantine list cannot be “tested” by inventing such endpoints. Freeze/advance page clock to check no overlapping polls and no polling after dispose.

### UI-10 — Provenance and execution without fabricated receipts

```js
await page.getByRole('button',{name:'Compare current note and proposed sections',exact:true}).click();
await check(page.getByTestId('lib-current-note-bytes').textContent().then(t=>t===fixtureCurrentText),'current bytes preserved');
await check(page.getByText('Proposed sections; final merged Markdown preview unavailable',{exact:true}).isVisible(),'comparison scope truthful');
await check(page.getByTestId('lib-reply-review').getByRole('link',{name:'Open cited note',exact:true}).count().then(n=>n>0),'challenge evidence openable');
await check(page.getByTestId('lib-reply-review').getByText('Advisory review',{exact:true}).isVisible(),'no verification claim');
await check(page.getByRole('button',{name:'Run claim input in Docker',exact:true}).isDisabled(),'Docker unavailable disables execution');
await check(page.getByText('Docker Desktop is not running',{exact:true}).isVisible(),'Docker reason visible without hover');
```

Fixtures must use the existing `/api/claims/runs.docker` reason string (set that exact string for the unavailable case) and actual verdict shape for post-run rendering. Supply a delayed unbound reply_reviewed event after another assistant reply, assert review is in the unassociated region and is not inside either message bubble. In the Workbench form select `non_isolated_host_exec`, assert visible “network isolation is not enforced”, and assert zero engagement_start requests before explicit person confirmation. Claim Run must make zero host execution requests in all unavailable cases. Timeout result with no cleanup field must show “Cleanup status not reported”, never “quarantined safely”. NAT-04/05/10 receipts cannot be an exit claim until implemented upstream; mark those follow-on checks blocked, not passed. Packaged smoke limits execution tests to routed responses and zero real execution assertions.

### UI-11 — Role selection fidelity

```js
await page.getByRole('button',{name:'Choose Notes model',exact:true}).click();
const tiersRequest = page.waitForRequest(r=>new URL(r.url()).pathname==='/api/tiers');
await page.getByTestId('lib-model-card').filter({hasText:'scripted-demo'}).click();
const tiers = (await tiersRequest).postDataJSON().tiers;
await check(tiers[0].model===originalLead,'writer change preserves lead');
await check(tiers[1].model==='scripted-demo','writer role explicit');
await check(page.getByRole('button',{name:'Clear all chat model roles',exact:true}).isVisible(),'clear scope visible');
```

Fixture seeds two distinct existing models and appropriate qualifications; never bypass an actual needs_override response. Assert ordinary card click cannot silently set override; explicit Use as lead anyway remains required and role-specific chips refresh after save. Packaged test reads routing readiness and uses mocked tier POST only. Service picker clearing tests assert `/api/services.slot` and no `/api/tiers` request.

### UI-12 — Navigation and staged-work continuity

```js
await page.getByRole('button',{name:'Settings',exact:true}).click();
await page.getByRole('button',{name:'Close',exact:true}).click();
await check(page.getByRole('textbox',{name:'Bottom Line',exact:true}).inputValue().then(v=>v===editedBottomLine),'settings roundtrip retains draft');
await page.getByRole('button',{name:'This week',exact:true}).click();
await check(page.getByRole('heading',{name:'This week',exact:true}).isVisible(),'agenda reachable directly');
await page.getByRole('button',{name:'Work actions',exact:true}).click();
await check(page.getByRole('button',{name:'Process enrichment backlog',exact:true}).isVisible(),'processing label not delete');
await check(page.getByRole('radiogroup',{name:'Permission mode',exact:true}).isVisible().then(v=>!v),'work actions separate from permission selection');
```

Add these after a fixture staging item has been opened and Bottom Line edited. New heading/labels are packet DOM requirements. Packaged navigation test uses a read-only agenda with existing tool, not mutation. Preserve explicit destructive Reload topics text and require it before dropping local taxonomy edits.

### UI-13 — Adapter and packaged boundary

`tests/test_obsidian_adapter_contract.py` currently has six static source tests. Keep its discovery identity, drain margin, tab-placement and typed-takeover protections. Add a Node/esbuild-backed adapter runtime fixture (`tests/fixtures/obsidian_ui_runtime.mjs`, new) exposing a minimal fake Obsidian workspace/ItemView/Setting and injected Core/fetch. Run the actual bundled adapter through scripted interactions; JSON evidence returned by the fixture is asserted in Python:

```python
def test_obsidian_retry_and_view_lifecycle_runtime():
    import json, subprocess
    run = subprocess.run(['node', str(ROOT/'tests/fixtures/obsidian_ui_runtime.mjs')],
                         cwd=ROOT, check=True, capture_output=True, text=True, timeout=60)
    result = json.loads(run.stdout)
    assert result['ordinary_retry_takeover'] is False
    assert result['typed_stale_retry_takeover'] is True
    assert result['handshake_retry_takeover'] is False
    assert result['discovered_core_stop_requests'] == 0
    assert result['owned_core_stop_force'] is False
    assert result['heartbeat_after_close'] == 0
    assert result['keydown_listeners_after_dispose'] == 0
    assert result['active_leaf_root'] == 'main'
```

The fixture must obtain those values from requests/events generated by source, never return constant expected booleans. This does not emulate Obsidian CSS/hotkeys accurately; installed browser containment tests and manual Obsidian evidence supplement it. If Node modules are absent, mark runtime prerequisite explicitly; do not silently skip and count acceptance complete.

`packaged-smoke.mjs`: before ready-file write retain existing token identity and successful API/Search checks; run UI-03/04/05 boundary cases against the **installed** JS/CSS. Record browser version, viewport/root width, loaded asset hashes, ui_build_id/core protocol and mock-vs-real evidence. After release-file appears, repeat authenticated meta and an unmocked Search to prove ongoing two-adapter usability. Never record page tokens or keys in report evidence. This is installed-fixture coverage, not real Claude/Cowork or Obsidian acceptance by itself.

## Backend-dependent work explicitly not authorized as UI packets

- Real schema-v5 rebuild percentage/ETA and a persistent active EMBEDDING_PENDING queue: current APIs do not expose progress events or job identity. UI-09 may only show snapshots/known warnings and the limitation.
- General quarantined-artifact history: current tools expose some immediate outcomes, not an authorized quarantine listing contract.
- G5 uncertain paid-call task settlement: an offline measurement gate is not current UI runtime accounting. No paid calls or automatic retry.
- Exact final promotion/taxonomy byte diff: server prepared plans are not published; UI-10 is a labelled semantic comparison only.
- NAT-04/05 hard output quotas, teardown verification and quarantine receipts; NAT-10 reply/revision identity and coverage. Show existing errors truthfully and leave stronger claims blocked until actual upstream payloads exist.

No new endpoint/state-store proposal is hidden in those dependencies. A follow-up backend decision is separate from completing the bounded UI improvements above.
