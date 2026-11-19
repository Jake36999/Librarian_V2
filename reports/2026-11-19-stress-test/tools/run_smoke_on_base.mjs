// Runs the full D:\Librarian_V2\ui\smoke.mjs against baseline da7bf8a to reproduce line 264!
import { spawn } from 'node:child_process';
import { join } from 'node:path';

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

console.log('Base core URL:', url);
const smoke = spawn('node', ['D:/Librarian_V2/ui/smoke.mjs', url, CHROME], {
  cwd: 'D:/Librarian_V2/ui',
  stdio: 'inherit',
});
const code = await new Promise(res => smoke.on('exit', res));
core.kill();
process.exit(code ?? 1);
