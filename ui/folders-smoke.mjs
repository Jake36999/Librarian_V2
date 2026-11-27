// Real native UI/Core and installed Geo wheel; no model calls or real libraries.
import { chromium } from 'playwright-core';
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve, sep } from 'node:path';

const [url, artifacts, source] = process.argv.slice(2);
mkdirSync(artifacts, {recursive: true});
const browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe'});
const context = await browser.newContext({viewport: {width: 1380, height: 1000}});
const page = await context.newPage();
const errors = []; page.on('pageerror', e => errors.push(String(e)));
await context.tracing.start({screenshots:true, snapshots:true});
try {
  await page.goto(url);
  await page.getByRole('tab', {name:'Staging', exact:true}).click();
  await page.getByRole('button', {name:/^Folders/}).click({timeout:8000});
  await page.getByRole('heading', {name:'Folder purposes'}).waitFor();
  assert.ok(await page.getByText('credential-like', {exact:false}).count());
  const card = page.getByRole('article', {name:'third_party_alpha'});
  await card.getByText('Draft — not accepted', {exact:true}).waitFor();
  assert.equal(await card.getByLabel('Purpose').inputValue(), 'third-party');
  assert.equal(await card.getByLabel('Graph').inputValue(), 'Test Vault-third-party');
  await page.screenshot({path: `${artifacts}/folders-staged.png`, fullPage:true});
  await card.getByRole('button', {name:'Accept folder decision', exact:true}).click();
  // A decided card leaves the waiting list, as a decided source does, and moves to Accepted.
  await page.getByText(/^Accepted third_party_alpha\./).waitFor({timeout:30000});
  assert.equal(await page.getByRole('article', {name:'third_party_alpha'}).count(), 0);
  await page.reload();
  await page.getByRole('tab', {name:'Staging',exact:true}).click();
  await page.getByRole('button', {name:/^Folders/}).click();
  await page.getByLabel('Which folders').selectOption('accepted');
  await page.getByRole('article', {name:'third_party_alpha'}).getByText('Decided and applied by a person', {exact:true}).waitFor();
  await page.screenshot({path:`${artifacts}/folders-accepted.png`, fullPage:true});
  await page.getByLabel('Which folders').selectOption('waiting');
  if (source) {
    assert.ok([resolve('G:/Libraries/_qa'), resolve('G:/Librarian-work/tmp')].some((base) =>
      resolve(source).toLowerCase().startsWith(base.toLowerCase() + sep)));
    await page.getByRole('article', {name:'third_party_beta', exact:true}).waitFor();
    writeFileSync(resolve(source, 'src/processor.py'), 'def process(value):\n    return value + 2\n');
    const inherited = page.locator('details.lib-inherited-folders:not([open]) > summary');
    if (await inherited.count()) await inherited.click();
    const stale = page.getByRole('article', {name:'src', exact:true});
    await stale.getByRole('button', {name:'Accept folder decision', exact:true}).click();
    await stale.getByText(/FOLDER_STALE/).waitFor();
    await stale.scrollIntoViewIfNeeded();
    await page.screenshot({path:`${artifacts}/folders-stale.png`, fullPage:true});
    await page.getByLabel('Folder to survey').fill(source);
    await Promise.all([
      page.waitForResponse((r) => r.url().includes('/api/folders/survey') && r.status() === 200),
      page.getByRole('button', {name:'Survey folders', exact:true}).click(),
    ]);
    await page.getByLabel('Which folders').selectOption('accepted');
    await page.getByRole('article', {name:'third_party_alpha'}).getByText('Decided and applied by a person', {exact:true}).waitFor();
    await page.getByLabel('Which folders').selectOption('waiting');
    await page.getByRole('article', {name:'third_party_beta', exact:true}).waitFor();
    if (await inherited.count()) await inherited.click();
    await page.getByRole('article', {name:'src', exact:true}).getByText('Waiting for a decision', {exact:true}).waitFor();
  }
  assert.deepEqual(errors, []);
  console.log('PASS: visible draft, metadata, suggested group, person acceptance, persistence, stale refusal and re-survey; zero models');
} finally {
  await context.tracing.stop({path:`${artifacts}/trace.zip`});
  await browser.close();
}
