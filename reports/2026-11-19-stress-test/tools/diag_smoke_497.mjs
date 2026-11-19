// Diagnoses the EXACT geometry failure of ui/smoke.mjs:264 at 497x450 on baseline da7bf8a
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire('D:/Librarian_V2/ui/package.json');
const { chromium } = require('playwright-core');

const BASE_DIR = 'C:/Users/jakem/.gemini/antigravity/brain/3960e172-6f69-4375-a20c-32da8ab417ab/scratch/librarian-stress-20261119/base';
const PY = 'D:/Librarian_V2/.venv/Scripts/python.exe';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const core = spawn(PY, [join(BASE_DIR, 'tests/ui_demo_core.py')], {
  cwd: BASE_DIR,
  env: { ...process.env, PYTHONPATH: join(BASE_DIR, 'src') },
  stdio: ['ignore', 'pipe', 'pipe'],
});

let url = '';
core.stderr.on('data', () => {});
await new Promise((resolve, reject) => {
  let buf = '';
  const timer = setTimeout(() => reject(new Error('timeout')), 20000);
  core.stdout.on('data', chunk => {
    buf += chunk.toString();
    const m = buf.match(/http:\/\/127\.0\.0\.1:\d+\/?/);
    if (m) { url = m[0]; clearTimeout(timer); resolve(); }
  });
});

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 820 } });
  await page.goto(url);
  await page.waitForSelector('#lib-msg');
  // Reproduce the state smoke.mjs leaves before line 244: a live conversation + session strip!
  await page.click("button[aria-label='Settings']");
  await page.click("dialog button:has-text('Models')");
  await page.click("dialog button:has-text('DeepInfra')");
  await page.locator("dialog .lib-model-row button:has-text('Use as Lead')").first().click();
  await page.keyboard.press('Escape');
  await page.fill('#lib-msg', 'hello');
  await page.click('button[type=submit]');
  await page.waitForSelector('.lib-perm', { timeout: 10000 });
  await page.click('.lib-perm button:has-text("Allow once")');
  await page.waitForFunction(() => !document.querySelector('#lib-send').textContent.includes('Stop'), { timeout: 15000 });

  const longListing = Array.from({ length: 120 }, (_, i) => ({
    kind: 'file', name: `Scroll fixture ${i + 1}`, path: `Scroll fixture ${i + 1}.md`,
  }));
  await page.route('**/api/files?dir=', route => route.fulfill({ json: { dir: '', entries: longListing } }));
  await page.setViewportSize({ width: 497, height: 450 });
  if (await page.getByRole('button', { name: 'Close the pane' }).isVisible()) {
    await page.getByRole('button', { name: 'Close the pane' }).click();
  }
  await page.getByRole('button', { name: 'Attach', exact: true }).click();
  const tile = page.getByRole('dialog', { name: 'Attach', exact: true });
  await tile.getByRole('menuitem', { name: 'Scroll fixture 120', exact: true }).waitFor({ state: 'attached' });
  const diag = await tile.evaluate(el => {
    const box = el.getBoundingClientRect();
    const area = el.parentElement.getBoundingClientRect();
    const kids = [...el.parentElement.children].map(c => ({
      cls: c.className, tag: c.tagName, hidden: c.hidden,
      rect: { top: Math.round(c.getBoundingClientRect().top), bottom: Math.round(c.getBoundingClientRect().bottom), height: Math.round(c.getBoundingClientRect().height) }
    }));
    const header = document.querySelector('header')?.getBoundingClientRect();
    const main = document.querySelector('main')?.getBoundingClientRect();
    const compose = document.querySelector('.lib-compose')?.getBoundingClientRect();
    return {
      fits: box.top >= area.top && box.bottom <= area.bottom && box.left >= area.left && box.right <= area.right,
      scrollable: el.scrollHeight > el.clientHeight,
      box: { top: box.top, bottom: box.bottom, left: box.left, right: box.right, w: box.width, h: box.height },
      area: { top: area.top, bottom: area.bottom, left: area.left, right: area.right, w: area.width, h: area.height },
      header: header ? { h: header.height } : null,
      main: main ? { top: main.top, bottom: main.bottom, h: main.height } : null,
      compose: compose ? { top: compose.top, bottom: compose.bottom, h: compose.height } : null,
      cs: { maxHeight: getComputedStyle(el).maxHeight, bottom: getComputedStyle(el).bottom, top: getComputedStyle(el).top, minHeight: getComputedStyle(el).minHeight },
      kids,
    };
  });
  console.log(JSON.stringify(diag, null, 2));
} finally {
  await browser.close();
  core.kill();
}
