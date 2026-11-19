// Area E Playwright verification script (zero model spend; uses tests/ui_demo_core.py on HEAD).
// Tests:
// 1. Light mode (prefers-color-scheme: light) contrast & dark-dialog inputs
// 2. Reduced motion (prefers-reduced-motion: reduce)
// 3. Modes popover clipping above viewport at 640x450 (200% zoom equivalent) and 497x450
// 4. 768x1024 open Document Pane covering Staging tab
// 5. Guide first-visit localStorage (librarian:guide-seen) across cleared storage, saved-closed pane, and pre-guide library
// 6. Live DOM rendering of adversarial /api/skills payload through markdown.ts (XSS vs Markdown table/heading/link injection)
// 7. Chat this.cards cross-session collision: q1 in session A causes q1 in session B to be silently dropped!
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire('D:/Librarian_V2/ui/package.json');
const { chromium } = require('playwright-core');

const PY = 'D:/Librarian_V2/.venv/Scripts/python.exe';
const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';

const core = spawn(PY, ['D:/Librarian_V2/tests/ui_demo_core.py'], {
  cwd: 'D:/Librarian_V2',
  env: { ...process.env, PYTHONPATH: 'D:/Librarian_V2/src' },
  stdio: ['ignore', 'pipe', 'pipe'],
});

let url = '';
let stderr = '';
core.stderr.on('data', d => { stderr += d.toString(); });
await new Promise((resolve, reject) => {
  let buf = '';
  const t = setTimeout(() => reject(new Error('timeout starting demo core: ' + stderr)), 20000);
  core.stdout.on('data', c => {
    buf += c.toString();
    const m = buf.match(/http:\/\/127\.0\.0\.1:\d+\/?/);
    if (m) { url = m[0]; clearTimeout(t); resolve(); }
  });
});

const results = { url };
const browser = await chromium.launch({ executablePath: CHROME, headless: true });
try {
  // --- Test 1: Light mode + Reduced motion + Guide first-visit + saved-closed ---
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, colorScheme: 'light', reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e)));

  await page.goto(url);
  await page.waitForSelector('#lib-msg');
  await page.waitForTimeout(400);
  const firstVisit = await page.evaluate(() => ({
    guideSeen: localStorage.getItem('librarian:guide-seen'),
    paneClosed: document.querySelector('.lib-body')?.classList.contains('lib-pane-closed'),
    paneTitle: document.querySelector('.lib-pane .lib-doc-title')?.textContent?.trim() || '',
    bg: getComputedStyle(document.body).backgroundColor,
    ink: getComputedStyle(document.body).color,
    reducedMotionMatch: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  }));

  // Open Settings in light mode & check search input colors
  await page.click("button[aria-label='Settings']");
  await page.waitForSelector('dialog[open]');
  const lightSettings = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const inp = dlg?.querySelector('input[type=search]');
    return {
      dlgBg: dlg ? getComputedStyle(dlg).backgroundColor : null,
      inpBg: inp ? getComputedStyle(inp).backgroundColor : null,
      inpColor: inp ? getComputedStyle(inp).color : null,
    };
  });
  await page.keyboard.press('Escape');

  // Also test dark mode Settings input colors
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.click("button[aria-label='Settings']");
  await page.waitForSelector('dialog[open]');
  const darkSettings = await page.evaluate(() => {
    const dlg = document.querySelector('dialog[open]');
    const inp = dlg?.querySelector('input[type=search]');
    return {
      dlgBg: dlg ? getComputedStyle(dlg).backgroundColor : null,
      inpBg: inp ? getComputedStyle(inp).backgroundColor : null,
      inpColor: inp ? getComputedStyle(inp).color : null,
    };
  });
  await page.keyboard.press('Escape');

  // Test pre-guide library (simulate 404 on About the Librarian and how to use it.md with fresh localStorage)
  await page.route('**/api/file?*About*', route => route.fulfill({ status: 404, json: { error: 'no note' } }));
  await page.evaluate(() => { localStorage.clear(); });
  await page.reload();
  await page.waitForSelector('#lib-msg');
  await page.waitForTimeout(400);
  const preGuideLib = await page.evaluate(() => ({
    guideSeen: localStorage.getItem('librarian:guide-seen'),
    paneClosed: document.querySelector('.lib-body')?.classList.contains('lib-pane-closed'),
  }));
  await page.unroute('**/api/file?*About*');

  // Test saved-closed pane (`librarian:pane = "closed"`) + cleared guide-seen
  await page.evaluate(() => {
    localStorage.clear();
    localStorage.setItem('librarian:pane', 'closed');
  });
  await page.reload();
  await page.waitForSelector('#lib-msg');
  await page.waitForTimeout(400);
  const savedClosedWithFreshGuide = await page.evaluate(() => ({
    guideSeen: localStorage.getItem('librarian:guide-seen'),
    paneClosed: document.querySelector('.lib-body')?.classList.contains('lib-pane-closed'),
    paneTitle: document.querySelector('.lib-pane .lib-doc-title')?.textContent?.trim() || '',
    lsKeys: Object.keys(localStorage),
  }));

  results.light_reduced_guide = { firstVisit, lightSettings, darkSettings, preGuideLib, savedClosedWithFreshGuide };

  // --- Test 2: Modes popover clipping at 640x450 & 497x450 (2nd reproduction!) ---
  const modesClip = {};
  for (const vp of [{ width: 640, height: 450 }, { width: 497, height: 450 }]) {
    await page.setViewportSize(vp);
    if (await page.getByRole('button', { name: 'Close the pane' }).isVisible()) {
      await page.getByRole('button', { name: 'Close the pane' }).click();
    }
    await page.locator('button', { hasText: /^Modes:/ }).click();
    await page.waitForSelector('.lib-popover.lib-modes');
    modesClip[`${vp.width}x${vp.height}`] = await page.locator('.lib-popover.lib-modes').evaluate(el => {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      return {
        top: Math.round(r.top * 10) / 10, bottom: Math.round(r.bottom * 10) / 10,
        height: Math.round(r.height * 10) / 10, clippedTop: r.top < 0,
        maxHeight: cs.maxHeight, overflowY: cs.overflowY,
      };
    });
    await page.keyboard.press('Escape');
  }
  results.modes_popover_clip = modesClip;

  // --- Test 3: 768x1024 open Document Pane covers Staging tab (2nd reproduction!) ---
  await page.setViewportSize({ width: 768, height: 1024 });
  if (await page.getByRole('button', { name: 'Show the document pane' }).isVisible()) {
    await page.getByRole('button', { name: 'Show the document pane' }).click();
  }
  await page.getByRole('tab', { name: 'Staging', exact: true }).click();
  await page.waitForTimeout(200);
  results.pane_768_covers_staging = await page.evaluate(() => {
    const pane = document.querySelector('.lib-pane')?.getBoundingClientRect();
    const view = document.querySelector('.lib-view')?.getBoundingClientRect();
    const elAtCenter = document.elementFromPoint(384, 500);
    return {
      paneRect: pane ? { x: pane.x, y: pane.y, w: pane.width, h: pane.height } : null,
      viewRect: view ? { x: view.x, y: view.y, w: view.width, h: view.height } : null,
      centerElementInsidePane: Boolean(elAtCenter && elAtCenter.closest('.lib-pane')),
      paneClosed: document.querySelector('.lib-body')?.classList.contains('lib-pane-closed'),
    };
  });
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.getByRole('tab', { name: 'Chat', exact: true }).click();

  // --- Test 4: Adversarial /api/skills live DOM rendering through markdown.ts ---
  const advMarkdown = [
    '# Skill registry',
    '',
    '## Installed servers and plugins',
    '',
    '| Name | In this library | Tools | Documentation |',
    '| --- | --- | --- | --- |',
    '| `evil` | on | 99 | <img src=x onerror="window.__xss=1">` | on | 1 | <javascript:alert(1)> |',
    '| `data-srv` | on | 1 | <data:text/html,<script>window.__xss=2</script>> |',
    '| `md-inject` | on | 0 | <https://ok.example> [CLICK ME](https://phish.example) | [[About/Rules]]',
    '',
    '## Injected Heading> |',
  ].join('\n');
  await page.route('**/api/skills', route => route.fulfill({
    json: { title: 'Skill registry', markdown: advMarkdown },
  }));
  await page.getByRole('button', { name: 'Attach', exact: true }).click();
  await page.getByRole('menuitem', { name: /Open skill registry/i }).click();
  await page.waitForTimeout(400);
  results.adversarial_skills_dom = await page.evaluate(() => {
    const doc = document.querySelector('.lib-pane .lib-doc');
    const imgs = doc ? [...doc.querySelectorAll('img')].length : 0;
    const scripts = doc ? [...doc.querySelectorAll('script')].length : 0;
    const links = doc ? [...doc.querySelectorAll('a')].map(a => ({ text: a.textContent, href: a.getAttribute('href') })) : [];
    const wikilinks = doc ? [...doc.querySelectorAll('button.lib-wl, .lib-wl')].map(el => el.textContent) : [];
    const h2s = doc ? [...doc.querySelectorAll('h2')].map(h => h.textContent) : [];
    const rows = doc ? [...doc.querySelectorAll('tbody tr')].map(tr => [...tr.querySelectorAll('td')].map(td => td.textContent)) : [];
    return {
      xssExecuted: Boolean(window.__xss),
      imgTags: imgs,
      scriptTags: scripts,
      links,
      wikilinks,
      h2s,
      rowCellCounts: rows.map(r => r.length),
      rows,
    };
  });
  await page.unroute('**/api/skills');

  // --- Test 5: 2nd reproduction of chat.ts:845 cross-session q1 drop! ---
  // Intercept /api/chat/attach or create two sessions with open q1 via API and switch between them!
  const token = await page.evaluate(() => {
    const m = document.querySelector('meta[name=librarian-token]');
    return m ? m.getAttribute('content') : '';
  });
  // Actually call /api/tool/open_session + ask_user on two sessions via page fetch with page's own auth!
  // Let's check if /api/chat/attach works by opening two sessions via /api/tool/open_session!
  const q1Collision = await page.evaluate(async () => {
    // Find token from window or meta or just trigger via SSE mock? Wait: the page itself knows its token,
    // let's check if the UI has Sessions or if we can use the Sessions menu!
    // Even simpler: inspect how main.ts fetches /api/meta (token is in meta tag or script)
    const metaTok = document.querySelector('meta[name=librarian-token]')?.getAttribute('content')
      || (document.documentElement.innerHTML.match(/token["']?\s*[:=]\s*["']([A-Za-z0-9_-]{20,})["']/) || [])[1] || '';
    return { hasToken: Boolean(metaTok), tokenLen: metaTok.length };
  });
  results.q1_token_probe = q1Collision;
  results.pageErrors = pageErrors;
  console.log(JSON.stringify(results, null, 2));
} finally {
  await browser.close();
  core.kill();
}
