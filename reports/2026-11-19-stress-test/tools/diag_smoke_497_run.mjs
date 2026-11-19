// Captures exact DOM geometry of ui/smoke.mjs:264 at 497x450 on baseline da7bf8a.
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const BASE = 'C:/Users/jakem/.gemini/antigravity/brain/3960e172-6f69-4375-a20c-32da8ab417ab/scratch/librarian-stress-20261119/base';
const SCRATCH = 'C:/Users/jakem/.gemini/antigravity/brain/3960e172-6f69-4375-a20c-32da8ab417ab/scratch/librarian-stress-20261119';
const PY = 'D:/Librarian_V2/.venv/Scripts/python.exe';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

let src = readFileSync('D:/Librarian_V2/ui/smoke.mjs', 'utf8');
src = src.replace('./obsidian-view-smoke.mjs', 'file:///D:/Librarian_V2/ui/obsidian-view-smoke.mjs');
src = src.replace('"playwright-core"', '"file:///D:/Librarian_V2/ui/node_modules/playwright-core/index.mjs"');
src = src.replace("'playwright-core'", "'file:///D:/Librarian_V2/ui/node_modules/playwright-core/index.mjs'");
const inject = `
  const diag497 = await tile.evaluate(el => {
    const box = el.getBoundingClientRect(), area = el.parentElement.getBoundingClientRect();
    const cs = getComputedStyle(el);
    return {
      box: {top:box.top, bottom:box.bottom, left:box.left, right:box.right, w:box.width, h:box.height},
      area: {top:area.top, bottom:area.bottom, left:area.left, right:area.right, w:area.width, h:area.height},
      scrollHeight: el.scrollHeight, clientHeight: el.clientHeight,
      cs: {position:cs.position, top:cs.top, bottom:cs.bottom, maxHeight:cs.maxHeight, minHeight:cs.minHeight, overflowY:cs.overflowY},
      kids: [...el.parentElement.children].map(c => ({cls:c.className, hidden:c.hidden, h:Math.round(c.getBoundingClientRect().height)})),
      headerH: Math.round(document.querySelector('header')?.getBoundingClientRect().height || 0),
    };
  });
  console.log('DIAG497', JSON.stringify(size), JSON.stringify(diag497));
`;
const target = '  await expect(geometry.fits && geometry.scrollable,';
if (!src.includes(target)) throw new Error('target not found');
const diagScript = join(SCRATCH, 'diag-smoke.mjs');
writeFileSync(diagScript, src.replace(target, inject + target), 'utf8');

const core = spawn(PY, [join(BASE, 'tests/ui_demo_core.py')], {
  cwd: BASE,
  env: { ...process.env, PYTHONPATH: join(BASE, 'src') },
  stdio: ['ignore', 'pipe', 'pipe'],
});
let buf = '';
let started = false;
core.stdout.on('data', d => {
  buf += d.toString();
  const m = buf.match(/http:\/\/127\.0\.0\.1:\d+\/?/);
  if (m && !started) {
    started = true;
    const s = spawn('node', [diagScript, m[0], CHROME], { cwd: 'D:/Librarian_V2/ui', stdio: 'inherit' });
    s.on('exit', c => { core.kill(); process.exit(c ?? 0); });
  }
});
