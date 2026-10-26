// Start the demo core (tests/ui_demo_core.py), run smoke.mjs against it, stop it.
//   node run-smoke.mjs [browser-path]
// With no path, an installed Chrome or Edge is used (no Chromium download needed).
import { spawn, execFileSync } from "child_process";
import { existsSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const here = dirname(fileURLToPath(import.meta.url));
const candidates = [
  process.argv[2],
  process.env.LIBRARIAN_SMOKE_BROWSER,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome", "/usr/bin/chromium", "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
].filter(Boolean);
const browser = candidates.find((p) => existsSync(p));
if (!browser) { console.error("no Chrome, Edge or Chromium found: pass its path"); process.exit(2); }

const repo = join(here, "..");
const venvPython = join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const python = process.env.LIBRARIAN_SMOKE_PYTHON ||
  (existsSync(venvPython) ? venvPython : process.platform === "win32" ? "python" : "python3");
const env = { ...process.env, PYTHONPATH: join(repo, "src"), LIBRARIAN_SMOKE_PYTHON: python };
const core = spawn(python, ["tests/ui_demo_core.py"],
  { cwd: repo, env, windowsHide: true, stdio: ["ignore", "pipe", "inherit"] });
const url = await new Promise((resolve, reject) => {
  let buffer = "";
  core.stdout.on("data", (chunk) => {
    buffer += chunk;
    const line = buffer.split("\n").find((l) => l.startsWith("{"));
    if (line) resolve(JSON.parse(line).url);
  });
  core.on("exit", (code) => reject(new Error(`the demo core exited (${code})`)));
});
const smoke = spawn(process.execPath, [join(here, "smoke.mjs"), url, browser], { env, windowsHide: true, stdio: "inherit" });
const code = await new Promise((resolve) => smoke.on("exit", resolve));
if (process.platform === "win32" && core.exitCode === null && core.pid) {
  // The venv redirector owns a separate interpreter child. Stop only this
  // demo's process tree so a failed smoke run cannot leave a Core behind.
  try { execFileSync("taskkill", ["/pid", String(core.pid), "/t", "/f"], { stdio: "ignore", windowsHide: true }); }
  catch { core.kill(); }
} else core.kill();
process.exit(code ?? 1);
