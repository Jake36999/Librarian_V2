// Reproduces ui/smoke.mjs:264 ("paperclip fits and scrolls at 497x450") on baseline da7bf8a
// using the extracted base snapshot, and captures exact DOM geometry & computed styles.
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
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
let stderr = '';
core.stderr.on('data', d => { stderr += d.toString(); });
await new Promise((resolve, reject) => {
  let buf = '';
  const timer = setTimeout(() => reject(new Error('timeout starting base demo core: ' + stderr)), 20000);
  core.stdout.on('data', chunk => {
    buf += chunk.toString();
    const m = buf.match(/http:\/\/127\.0\.0\.1:\d+\/?/);
    if (m) { url = m[0]; clearTimeout(timer); resolve(); }
  });
  core.on('exit', code => { clearTimeout(timer); reject(new Error('core exited ' + code + ': ' + stderr)); });
});

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1200, height: 820 } });
  await page.goto(url);
  await page.waitForSelector('#lib-msg');
  const longListing = Array.from({ length: 120 }, (_, i) => ({
    kind: 'file', name: `Scroll fixture ${i + 1}`, path: `Scroll fixture ${i + 1}.md`,
  }));
  await page.route('**/api/files?dir=', route => route.fulfill({ json: { dir: '', entries: longListing } }));
  for (const size of [{ width: 1200, height: 820 }, { width: 497, height: 450 }]) {
    await page.setViewportSize(size);
    if (size.width === 497 && await page.getByRole('button', { name: 'Close the pane' }).isVisible()) {
      await page.getByRole('button', { name: 'Close the pane' }).click();
    }
    const trigger = page.getByRole('button', { name: 'Attach', exact: true });
    await trigger.click();
    const tile = page.getByRole('dialog', { name: 'Attach', exact: true });
    await tile.getByRole('menuitem', { name: 'Scroll fixture 120', exact: true }).waitFor({ state: 'attached' });
    const diag = await tile.evaluate(el => {
      const box = el.getBoundingClientRect();
      const area = el.parentElement.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const areaCs = getComputedStyle(el.parentElement);
      const form = el.parentElement.querySelector('.lib-compose');
      const formBox = form ? form.getBoundingClientRect() : null;
      const head = document.querySelector('header');
      const headBox = head ? head.getBoundingClientRect() : null;
      return {
        fits: box.top >= area.top && box.bottom <= area.bottom && box.left >= area.left && box.right <= area.right,
        scrollable: el.scrollHeight > el.clientHeight,
        box: { top: box.top, bottom: box.bottom, left: box.left, right: box.right, width: box.width, height: box.height },
        area: { top: area.top, bottom: area.bottom, left: area.left, right: area.right, width: area.width, height: area.height },
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
        computed: { position: cs.position, top: cs.top, bottom: cs.bottom, maxHeight: cs.maxHeight, overflowY: cs.overflowY },
        parentClass: el.parentElement.className,
        parentPos: areaCs.position,
        formBox: formBox ? { top: formBox.top, bottom: formBox.bottom, height: formBox.height } : null,
        headBox: headBox ? { top: headBox.top, bottom: headBox.bottom, height: headBox.height } : null,
      };
    });
    console.log(JSON.stringify({ size, diag }, null, 2));
    await page.keyboard.press('Escape');
  }
} finally {
  await browser.close();
  core.kill();
}
