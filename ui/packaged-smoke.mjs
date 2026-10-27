// Browser acceptance for an already-running *installed* Librarian Core.
//
// This deliberately does not launch Python, set PYTHONPATH, or refer to the
// checkout's demo Core.  A packaging harness supplies the private loopback URL
// and token published by the installed Core.  The token is environment-only
// so it never appears in a process command line:
//
//   LIBRARIAN_PACKAGED_TOKEN=SECRET node packaged-smoke.mjs --url http://127.0.0.1:1234
//
// For simultaneous adapter evidence, --ready-file is written atomically once
// the real browser has rendered and completed a read-only search.  The browser
// then remains connected until --release-file appears (or the bounded timeout
// expires).
import { chromium } from "playwright-core";
import {
  existsSync, mkdirSync, renameSync, rmSync, writeFileSync,
} from "fs";
import { dirname, join } from "path";

function argumentsOf(argv) {
  const values = new Map();
  for (let index = 0; index < argv.length; index += 1) {
    const name = argv[index];
    if (!name.startsWith("--") || index + 1 >= argv.length) {
      throw new Error(`expected --name value, got ${name}`);
    }
    values.set(name.slice(2), argv[index + 1]);
    index += 1;
  }
  return values;
}

function firstExisting(paths) {
  return [...new Set(paths.filter(Boolean))].find((path) => existsSync(path));
}

function browserCandidates(explicit) {
  const local = process.env.LOCALAPPDATA ?? "";
  if (process.platform === "win32") {
    return [
      explicit,
      process.env.LIBRARIAN_SMOKE_BROWSER,
      "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
      "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
      local && join(local, "Microsoft/Edge/Application/msedge.exe"),
      "C:/Program Files/Google/Chrome/Application/chrome.exe",
      "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
      local && join(local, "Google/Chrome/Application/chrome.exe"),
    ];
  }
  return [
    explicit,
    process.env.LIBRARIAN_SMOKE_BROWSER,
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/microsoft-edge", "/usr/bin/google-chrome", "/usr/bin/chromium",
  ];
}

function loopbackUrl(raw) {
  let parsed;
  try { parsed = new URL(raw); } catch { throw new Error(`invalid Core URL: ${raw}`); }
  if (parsed.protocol !== "http:" ||
      !["127.0.0.1", "localhost", "[::1]"].includes(parsed.hostname)) {
    throw new Error(`Core URL must be loopback HTTP, got ${raw}`);
  }
  parsed.pathname = "/";
  parsed.search = "";
  parsed.hash = "";
  return parsed.toString().replace(/\/$/, "");
}

function atomicJson(path, value) {
  if (existsSync(path)) throw new Error(`ready file already exists: ${path}`);
  mkdirSync(dirname(path), { recursive: true });
  const temporary = `${path}.${process.pid}.tmp`;
  try {
    writeFileSync(temporary, `${JSON.stringify(value)}\n`, { encoding: "utf8", flag: "wx" });
    renameSync(temporary, path);
  } finally {
    rmSync(temporary, { force: true });
  }
}

const delay = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

async function waitForRelease(path, timeoutSeconds) {
  const deadline = Date.now() + timeoutSeconds * 1000;
  while (!existsSync(path)) {
    if (Date.now() >= deadline) {
      throw new Error(`release file did not appear within ${timeoutSeconds}s: ${path}`);
    }
    await delay(200);
  }
}

const args = argumentsOf(process.argv.slice(2));
const rawUrl = args.get("url") ?? process.env.LIBRARIAN_PACKAGED_URL ?? "";
if (args.has("token")) {
  throw new Error("the Core token must use LIBRARIAN_PACKAGED_TOKEN, not a process argument");
}
const token = process.env.LIBRARIAN_PACKAGED_TOKEN ?? "";
// Capture the secret for authenticated assertions, then remove it before
// Playwright launches Edge/Chrome so the browser process cannot inherit it.
delete process.env.LIBRARIAN_PACKAGED_TOKEN;
const readyFile = args.get("ready-file") ?? process.env.LIBRARIAN_BROWSER_READY_FILE ?? "";
const releaseFile = args.get("release-file") ?? process.env.LIBRARIAN_BROWSER_RELEASE_FILE ?? "";
const holdTimeout = Number(args.get("hold-timeout") ??
  process.env.LIBRARIAN_BROWSER_HOLD_TIMEOUT ?? "120");

if (!rawUrl || !token) {
  throw new Error("a URL and LIBRARIAN_PACKAGED_TOKEN are required");
}
if (Boolean(readyFile) !== Boolean(releaseFile)) {
  throw new Error("--ready-file and --release-file must be supplied together");
}
if (!Number.isFinite(holdTimeout) || holdTimeout <= 0 || holdTimeout > 600) {
  throw new Error("--hold-timeout must be between 1 and 600 seconds");
}

const url = loopbackUrl(rawUrl);
const executablePath = firstExisting(browserCandidates(args.get("browser")));
if (!executablePath) {
  throw new Error("no installed Edge or Chrome found; pass --browser or LIBRARIAN_SMOKE_BROWSER");
}

let browser;
try {
  browser = await chromium.launch({ executablePath, headless: true });
  const page = await browser.newPage({ viewport: { width: 1200, height: 820 } });
  const errors = [];
  const successfulApi = new Set();
  page.on("pageerror", (error) => errors.push(`page: ${String(error)}`));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("response", (response) => {
    const responseUrl = new URL(response.url());
    if (responseUrl.origin === new URL(url).origin && responseUrl.pathname.startsWith("/api/") && response.ok()) {
      successfulApi.add(responseUrl.pathname);
    }
  });

  const index = await page.goto(`${url}/`, { waitUntil: "domcontentloaded" });
  if (!index?.ok()) throw new Error(`packaged UI returned HTTP ${index?.status() ?? "no response"}`);
  await page.waitForSelector("header nav[aria-label='Views']");
  await page.waitForFunction(() => document.title.endsWith(" - Librarian"));
  await page.waitForFunction(() => {
    const button = document.querySelector("button.lib-switch");
    return button && button.textContent && button.textContent.trim() !== "Library ▾";
  });

  const pageToken = await page.locator("meta[name='librarian-token']").getAttribute("content");
  if (pageToken !== token) throw new Error("served page token does not match the private discovery record");
  for (const required of ["/api/tools", "/api/state"]) {
    if (!successfulApi.has(required)) throw new Error(`packaged UI did not complete ${required}`);
  }

  await page.getByRole("tab", { name: "Search" }).click();
  const query = page.getByRole("searchbox", { name: "Search query" });
  await query.fill("packaged-browser-smoke-no-match");
  const [searchResponse] = await Promise.all([
    page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/tool/search" && response.request().method() === "POST"),
    query.press("Enter"),
  ]);
  if (!searchResponse.ok()) throw new Error(`read-only search returned HTTP ${searchResponse.status()}`);
  const searchBody = await searchResponse.json();
  if (searchBody.error) throw new Error(`read-only search failed: ${searchBody.error}`);
  await page.waitForFunction(() => {
    const results = document.querySelector(".view.search .results");
    return results && !results.textContent?.includes("Searching…");
  });
  if (errors.length) throw new Error(`browser errors:\n${errors.join("\n")}`);

  const evidence = {
    url,
    browser: executablePath,
    title: await page.title(),
    api: [...successfulApi].sort(),
    search_results: Array.isArray(searchBody.results) ? searchBody.results.length : null,
  };
  if (readyFile) {
    atomicJson(readyFile, evidence);
    await waitForRelease(releaseFile, holdTimeout);
    // The integration harness creates the release marker only after the
    // packaged MCP process has completed.  Recheck through this same browser
    // page so the evidence proves the two adapters overlapped in time and the
    // browser remained usable afterwards.
    evidence.post_release_api = await page.evaluate(async (pageToken) => {
      const response = await fetch("/api/meta", {
        headers: { "X-Librarian-Token": pageToken },
      });
      const body = await response.json();
      if (!response.ok) throw new Error(`post-release /api/meta returned HTTP ${response.status}`);
      return { core_version: body.core_version, protocol_version: body.protocol_version };
    }, token);
    if (errors.length) throw new Error(`browser errors during adapter overlap:\n${errors.join("\n")}`);
  }
  console.log(JSON.stringify(evidence));
} finally {
  await browser?.close();
}
