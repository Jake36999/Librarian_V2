// Real native UI/Core M1a smoke check and screenshot capture (zero model calls).
//   node m1a-smoke.mjs <url> <artifacts-dir> [source-dir]
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';

const [url, artifacts, source] = process.argv.slice(2);
assert.ok(url, 'usage: node m1a-smoke.mjs <url> <artifacts-dir> [source-dir]');
assert.ok(artifacts, 'artifacts directory is required');
mkdirSync(artifacts, { recursive: true });

const TOKEN = 'synthetic-qa-token';
const apiPost = async (path, body = {}) => {
  const res = await fetch(new URL(path, url), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Librarian-Token': TOKEN,
    },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  return { status: res.status, data };
};

const browser = await chromium.launch({ executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe' });
const context = await browser.newContext({ viewport: { width: 1380, height: 1000 } });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(`pageerror: ${String(e)}`));
page.on('console', (m) => {
  // Stale-revision check intentionally provokes one expected HTTP 409 response.
  if (m.type() === 'error' && !/status of 409/.test(m.text())) {
    errors.push(`console.error: ${m.text()}`);
  }
});

await context.tracing.start({ screenshots: true, snapshots: true });
try {
  await page.goto(url);
  await page.waitForSelector('header nav');

  // 1. Finished run chip has Details button that opens its run_status record.
  const started = await apiPost('/api/actions', { name: 'gather-agenda', inputs: {} });
  assert.equal(started.status, 200, `expected 200 starting gather-agenda, got ${started.status}`);
  const chip = page.locator('.lib-chip.lib-action-finished', { hasText: 'gather-agenda' });
  await chip.waitFor({ timeout: 20000 });
  const detailsBtn = chip.getByRole('button', { name: 'Details of gather-agenda', exact: true });
  await detailsBtn.waitFor();
  await detailsBtn.click();
  const dialog = page.locator('dialog[open]');
  await dialog.waitFor({ timeout: 10000 });
  const headingText = await dialog.locator('h3').innerText();
  assert.match(headingText, /gather-agenda · finished/);
  const bodyText = await dialog.locator('.lib-run-record-body').innerText();
  const parsedRun = JSON.parse(bodyText);
  assert.equal(parsedRun.name, 'gather-agenda');
  assert.equal(parsedRun.status, 'finished');
  await page.screenshot({ path: `${artifacts}/m1a-run-details.png`, fullPage: true });
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  await dialog.waitFor({ state: 'hidden' });
  console.log('✓ M1a Check 1: finished run chip Details button opens run_status record');

  // 2. Stale-revision conflict -> "Reload item, keeping your edits" keeps edited Bottom Line.
  const attachRes = await fetch(new URL('/api/attach?dir=Inbox&name=m1a-fixture.txt', url), {
    method: 'POST',
    headers: { 'X-Librarian-Token': TOKEN },
    body: 'M1a Fixture Source\n\nSynthetic text source for M1a stale-revision and Which-sources verification.\n',
  });
  assert.equal(attachRes.status, 200, `expected 200 from /api/attach, got ${attachRes.status}`);
  const attached = await attachRes.json();
  const ingested = await apiPost('/api/tool/ingest', { arguments: { ref: attached.path }, session: '' });
  assert.equal(ingested.status, 200);
  const itemId = ingested.data.id || ingested.data.item;
  assert.equal(ingested.data.status, 'staged', `expected staged item, got ${JSON.stringify(ingested.data)}`);
  assert.ok(itemId, `expected staged item id from ingest, got ${JSON.stringify(ingested.data)}`);

  await page.getByRole('tab', { name: 'Staging', exact: true }).click();
  const statusSelect = page.getByLabel('Which sources');
  await statusSelect.waitFor();
  await statusSelect.selectOption('staged');

  const itemRow = page.locator(`[data-item="${itemId}"]`);
  await itemRow.waitFor({ timeout: 10000 });
  await itemRow.click();

  const bottomLine = page.locator('#lib-bl');
  await bottomLine.waitFor({ timeout: 10000 });
  const editedBottomLine = 'Kept edited Bottom Line across stale-revision reload (M1a)';
  await bottomLine.fill(editedBottomLine);

  // Bump item revision externally (flag sensitive, then clear) while item stays status=staged.
  const flag1 = await apiPost('/api/tool/staging_flag', {
    arguments: { item_id: itemId, sensitive: true, reason: 'M1a conflict probe' },
    session: '',
  });
  assert.equal(flag1.status, 200);
  const flag2 = await apiPost('/api/tool/staging_flag', {
    arguments: { item_id: itemId, sensitive: false, reason: 'cleared before reload' },
    session: '',
  });
  assert.equal(flag2.status, 200);

  await page.getByRole('button', { name: 'Accept as captured', exact: true }).click();
  const reloadKeepingBtn = page.getByRole('button', { name: 'Reload item, keeping your edits', exact: true });
  await reloadKeepingBtn.waitFor({ timeout: 10000 });
  await reloadKeepingBtn.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${artifacts}/m1a-stale-conflict.png`, fullPage: true });

  await reloadKeepingBtn.click();
  const keptNotice = page.getByText('Your edits were kept over the reloaded item', { exact: false });
  await keptNotice.waitFor({ timeout: 10000 });
  assert.equal(await page.locator('#lib-bl').inputValue(), editedBottomLine);
  await page.locator('#lib-bl').scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${artifacts}/m1a-stale-reloaded-kept.png`, fullPage: true });
  console.log('✓ M1a Check 2: Reload item, keeping your edits preserves Bottom Line');

  // 3. "Which sources" lists processing ("Being ingested") and accepted ("Accepted into the library").
  await page.getByRole('button', { name: 'Accept as captured', exact: true }).click();
  await page.getByText('Accepted into the library and catalogued', { exact: false }).waitFor({ timeout: 15000 });

  const options = await statusSelect.locator('option').evaluateAll((els) =>
    els.map((el) => ({ value: el.getAttribute('value'), label: el.textContent?.trim() }))
  );
  assert.deepEqual(
    options.find((o) => o.value === 'processing'),
    { value: 'processing', label: 'Being ingested' },
    'Which sources must include processing ("Being ingested")'
  );
  assert.deepEqual(
    options.find((o) => o.value === 'accepted'),
    { value: 'accepted', label: 'Accepted into the library' },
    'Which sources must include accepted ("Accepted into the library")'
  );

  // Exercise processing filter first to confirm it queries without error.
  await statusSelect.selectOption('processing');
  await page.waitForTimeout(300);
  assert.equal(await statusSelect.inputValue(), 'processing');

  // Then select accepted and confirm the newly accepted item is listed.
  await statusSelect.selectOption('accepted');
  const acceptedRow = page.locator(`[data-item="${itemId}"]`);
  await acceptedRow.waitFor({ timeout: 10000 });
  await acceptedRow.click();
  await page.screenshot({ path: `${artifacts}/m1a-which-sources.png`, fullPage: true });
  console.log('✓ M1a Check 3: Which sources lists processing and accepted items');

  // 4. Folder cards distinguish "Selected for the description batch; not decided yet"
  //    from "Decided and applied by a person".
  await page.getByRole('button', { name: /^Folders/ }).click({ timeout: 8000 });
  await page.getByRole('heading', { name: 'Folder purposes' }).waitFor();

  await page.getByLabel('Select third_party_beta for the description batch', { exact: true }).check();
  await page.getByRole('button', { name: 'Select for the description batch', exact: true }).click();
  await page.getByText('Selected for the description batch: start it in Staging', { exact: false }).waitFor({ timeout: 10000 });

  // Reload to confirm the persisted Core state label renders directly on the folder card.
  await page.reload();
  await page.getByRole('tab', { name: 'Staging', exact: true }).click();
  await page.getByRole('button', { name: /^Folders/ }).click({ timeout: 8000 });
  const selectedCard = page.getByRole('article', { name: 'third_party_beta', exact: true });
  await selectedCard.getByText('Selected for the description batch; not decided yet', { exact: true }).waitFor({ timeout: 10000 });
  await selectedCard.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${artifacts}/m1a-folder-selected-batch.png`, fullPage: true });

  const alphaCard = page.getByRole('article', { name: 'third_party_alpha', exact: true });
  await alphaCard.getByRole('button', { name: 'Accept folder decision', exact: true }).click();
  await page.getByText(/^Accepted third_party_alpha\./).waitFor({ timeout: 30000 });
  await page.getByLabel('Which folders', { exact: true }).selectOption('accepted');
  const decidedCard = page.getByRole('article', { name: 'third_party_alpha', exact: true });
  await decidedCard.getByText('Decided and applied by a person', { exact: true }).waitFor({ timeout: 10000 });
  await decidedCard.scrollIntoViewIfNeeded();
  await page.screenshot({ path: `${artifacts}/m1a-folder-decided-person.png`, fullPage: true });
  console.log('✓ M1a Check 4: folder cards show distinct batch-selected and person-decided labels');

  assert.deepEqual(errors, [], `unexpected browser errors: ${errors.join(' | ')}`);
  console.log('PASS: all 4 M1a browser checks verified against live demo Core; zero models');
} finally {
  await context.tracing.stop({ path: `${artifacts}/m1a-trace.zip` });
  await browser.close();
}
