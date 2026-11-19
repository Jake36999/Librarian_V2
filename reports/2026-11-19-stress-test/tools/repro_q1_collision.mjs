// Deterministically reproduces F-05 (ui/src/chat.ts:845 cross-session q1 card drop):
// Seeds two sessions in a scratch vault, each with an open question `q1`.
// Attaches Session A in the UI (shows `q1` card), then attaches Session B:
// because `this.cards` is never cleared on replay() and keys by `q:${id}` without sessionId,
// Session B's `q1` card is silently dropped from Chat!
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';

const require = createRequire('D:/Librarian_V2/ui/package.json');
const { chromium } = require('playwright-core');

const PY = 'D:/Librarian_V2/.venv/Scripts/python.exe';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const VAULT = 'C:/Users/jakem/.gemini/antigravity/brain/3960e172-6f69-4375-a20c-32da8ab417ab/scratch/librarian-stress-20261119/q1_repro_vault';

rmSync(VAULT, { recursive: true, force: true });
mkdirSync(VAULT, { recursive: true });

// Seed vault with 2 open sessions each having an unanswered q1
const seedCode = `
import sys, json
from pathlib import Path
sys.path.insert(0, r'D:\\Librarian_V2\\src')
from resource_librarian.init import init
from resource_librarian.vault import Vault
from resource_librarian.session import SessionStore
from resource_librarian import tools
from resource_librarian.registry import REGISTRY, Context

vroot = Path(r'${VAULT}')
init(vroot, name='Q1 Collision Repro')
v = Vault(vroot)
st = SessionStore(v)
sids = []
for label, qtext in [('Session A', 'Question in Session A?'), ('Session B', 'Promote the offering in Session B?')]:
    out = REGISTRY.call('open_session', {'purpose': 'explore', 'question': label}, Context(tier='curate', vault=v))
    sid = out['opened']
    st.append(sid, {'type': 'question', 'id': 'q1', 'question': qtext, 'kind': 'confirm', 'ref': 'o1', 'options': ['yes', 'no']})
    sids.append(sid)
print(json.dumps(sids))
`;

const seed = spawn(PY, ['-c', seedCode], { stdio: ['ignore', 'pipe', 'pipe'] });
let seedOut = '', seedErr = '';
seed.stdout.on('data', d => { seedOut += d.toString(); });
seed.stderr.on('data', d => { seedErr += d.toString(); });
const rc = await new Promise(r => seed.on('exit', r));
if (rc !== 0) throw new Error('seed failed: ' + seedErr);
const [sidA, sidB] = JSON.parse(seedOut.trim());

const core = spawn(PY, ['-m', 'resource_librarian', '--vault', VAULT, 'app', '--port', '0'], {
  cwd: 'D:/Librarian_V2',
  env: { ...process.env, PYTHONPATH: 'D:/Librarian_V2/src' },
  stdio: ['ignore', 'pipe', 'pipe'],
});
let url = '', stderr = '';
core.stderr.on('data', d => { stderr += d.toString(); });
await new Promise((resolve, reject) => {
  let buf = '';
  const t = setTimeout(() => reject(new Error('timeout: ' + stderr)), 20000);
  core.stdout.on('data', c => {
    buf += c.toString();
    const m = buf.match(/http:\/\/127\.0\.0\.1:\d+\/?/);
    if (m) { url = m[0]; clearTimeout(t); resolve(); }
  });
});

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(url);
  await page.waitForSelector('#lib-msg');
  await page.waitForTimeout(1000);  // wait for SSE /api/events subscription to attach

  const attachByQuestion = async (needle) => {
    await page.locator('button', { hasText: /Sessions/ }).click();
    const pop = page.locator('.lib-popover:not([hidden])');
    await pop.waitFor({ state: 'visible' });
    const btn = pop.locator('button', { hasText: needle }).first();
    await btn.waitFor({ state: 'visible' });
    await btn.click();
    await page.waitForTimeout(500);
  };

  // Attach Session A via Sessions menu
  await attachByQuestion('Session A');
  const afterA = await page.evaluate(() => ({
    chatQuestions: [...document.querySelectorAll('.lib-log [aria-label="Question"]')].map(el => el.textContent?.trim()),
    chatText: document.querySelector('.lib-log')?.textContent?.trim() || '',
  }));

  // Now attach Session B via Sessions menu (WITHOUT reloading page!)
  await attachByQuestion('Session B');
  const afterB = await page.evaluate(() => ({
    chatQuestions: [...document.querySelectorAll('.lib-log [aria-label="Question"]')].map(el => el.textContent?.trim()),
    chatText: document.querySelector('.lib-log')?.textContent?.trim() || '',
  }));

  // Reload page (clearing in-memory this.cards) and attach Session B: now q1 DOES appear!
  await page.reload();
  await page.waitForSelector('#lib-msg');
  await page.waitForTimeout(1000);
  await attachByQuestion('Session B');
  const afterReloadB = await page.evaluate(() => ({
    chatQuestions: [...document.querySelectorAll('.lib-log [aria-label="Question"]')].map(el => el.textContent?.trim()),
    chatText: document.querySelector('.lib-log')?.textContent?.trim() || '',
  }));

  console.log(JSON.stringify({ sidA, sidB, afterA, afterB, afterReloadB, bugReproduced: afterA.chatQuestions.length === 1 && afterB.chatQuestions.length === 0 && afterReloadB.chatQuestions.length === 1 }, null, 2));
} finally {
  await browser.close();
  core.kill();
}
