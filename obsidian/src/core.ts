// Starting the local core: the plugin can't install Python packages (Obsidian's
// developer policies), so it finds an installed core, starts it on loopback with
// a fresh page token, and hands it the keys from Obsidian's secret storage as
// environment variables: in memory only, never written anywhere.

import { spawn, type ChildProcess } from "node:child_process";
import { randomBytes, createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import * as os from "node:os";
import * as path from "node:path";

export const KEY_ENV: Record<string, string> = {
  deepinfra: "DEEPINFRA_API_KEY", openai: "OPENAI_API_KEY", anthropic: "ANTHROPIC_API_KEY",
};
export const STOP_EXIT_MS = 25_000;

export interface Running {
  url: string;
  token: string;
  /** Present only when this adapter spawned the Core itself. */
  process?: ChildProcess;
  owned: boolean;
}

export class CoreNotFound extends Error {}

interface DiscoveryRecord {
  vault: string;
  url: string;
  token: string;
  pid: number;
  process_start: string;
  protocol_version: string;
}

/** A page token is an adapter credential, not a general-purpose bearer token.
 * Refuse to attach it to anything except the Core's loopback HTTP surface,
 * even if a damaged private discovery record or a misconfigured launcher
 * presents a syntactically valid URL. */
function loopbackUrl(value: string): string | null {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.toLowerCase();
    if (parsed.protocol !== "http:" || !["127.0.0.1", "localhost", "::1", "[::1]"].includes(host)) return null;
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}

function discoveryPath(vaultPath: string): string {
  // Mirrors resource_librarian.connection.path_for().  It deliberately uses
  // a hash rather than leaking a vault name into a configuration filename.
  let canonical = path.resolve(vaultPath);
  if (process.platform === "win32") canonical = canonical.toLowerCase();
  const key = createHash("sha256").update(canonical, "utf8").digest("hex").slice(0, 24);
  // Python's config_dir() treats LIBRARIAN_CONFIG_DIR as the *complete*
  // Librarian config directory.  XDG_CONFIG_HOME, in contrast, is only a
  // parent.  Keeping that distinction here makes Host discovery work in
  // managed/portable installs as well as the normal ~/.config install.
  const explicit = process.env.LIBRARIAN_CONFIG_DIR;
  const base = explicit || path.join(process.env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config"),
                                     "resource-librarian");
  return path.join(base, "cores", `${key}.json`);
}

function samePath(left: string, right: string): boolean {
  let a = path.resolve(left);
  let b = path.resolve(right);
  if (process.platform === "win32") { a = a.toLowerCase(); b = b.toLowerCase(); }
  return a === b;
}

/** Ask the installed Core code to validate the protected record's exact
 * PID/start identity. Node's PID-only kill(0) cannot distinguish a recycled
 * Windows PID, while resource_librarian.process_identity uses the native
 * creation FILETIME and is also the Host/MCP authority for this decision. */
async function exactCoreIsRunning(corePath: string, vaultPath: string,
                                  expected: DiscoveryRecord, expectedUrl: string): Promise<boolean> {
  const [exe, prefix] = command(corePath);
  return new Promise((resolve) => {
    let child: ChildProcess;
    try {
      child = spawn(exe, [...prefix, "host", "status", "--vault", vaultPath],
        { env: process.env, stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
    } catch {
      resolve(false);
      return;
    }
    let out = "";
    let settled = false;
    const finish = (value: boolean) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(value);
    };
    const timer = setTimeout(() => { child.kill(); finish(false); }, 5_000);
    child.on("error", () => finish(false));
    child.stdout?.on("data", (data) => {
      out += String(data);
      if (out.length > 1_000_000) { child.kill(); finish(false); }
    });
    child.on("exit", (code) => {
      if (code !== 0) { finish(false); return; }
      try {
        const status = JSON.parse(out) as { cores?: Array<Record<string, unknown>> };
        const matched = Array.isArray(status.cores) && status.cores.some((row) =>
          Number(row.pid) === expected.pid
          && row.process_start === expected.process_start
          && typeof row.vault === "string" && samePath(row.vault, vaultPath)
          && typeof row.url === "string" && loopbackUrl(row.url) === expectedUrl);
        finish(Boolean(matched));
      } catch { finish(false); }
    });
  });
}

/** Use an alive, local Core when the user already has one for this vault.
 * The Core still proves compatibility through /api/meta before the view
 * mounts. A missing/stale/unreadable private record is intentionally benign. */
export async function discover(vaultPath: string, corePath = ""): Promise<Running | null> {
  try {
    const row = JSON.parse(await readFile(discoveryPath(vaultPath), "utf8")) as DiscoveryRecord;
    if (!row || typeof row.url !== "string" || typeof row.token !== "string"
        || typeof row.pid !== "number" || typeof row.process_start !== "string"
        || !row.process_start || String(row.protocol_version) !== "2") return null;
    if (!samePath(String(row.vault || ""), vaultPath)) return null;
    const url = loopbackUrl(row.url);
    if (!url) return null;
    // Validate before the private page token leaves this process. A stale or
    // recycled-PID record therefore cannot disclose it to an unrelated local
    // listener merely because that process now owns the old PID.
    if (!await exactCoreIsRunning(corePath, vaultPath, row, url)) return null;
    return { url, token: row.token, owned: false };
  } catch { return null; }
}

/** `resource-librarian`, or a Python interpreter that has the package. */
function command(corePath: string): [string, string[]] {
  const exe = corePath.trim() || "resource-librarian";
  return /^python[\d.]*(\.exe)?$/i.test(path.basename(exe)) ? [exe, ["-m", "resource_librarian"]] : [exe, []];
}

export async function start(corePath: string, vaultPath: string, keys: Record<string, string>,
                            timeoutMs = 20000): Promise<Running> {
  const active = await discover(vaultPath, corePath);
  if (active) return active;
  const token = randomBytes(24).toString("base64url");
  const [exe, prefix] = command(corePath);
  // The Core is a user-controlled Host process.  It deliberately outlives
  // this view (and even an Obsidian crash); explicit Host stop/restart owns
  // its lifetime. Provider keys remain only in this child process memory.
  const env: Record<string, string | undefined> = { ...process.env, LIBRARIAN_TOKEN: token,
                                                    LIBRARIAN_SECRET_SOURCE: "obsidian",
                                                    // This grants the child exactly one authenticated
                                                    // graceful-stop endpoint for an explicit key rotation.
                                                    // It never ties Core lifetime to this view or its stdio.
                                                    LIBRARIAN_HOST_MANAGED: "1" };
  // Do not accidentally inherit an unrelated shell's provider selection.
  // Obsidian's SecretStorage choices are the only model credentials injected
  // into an Obsidian-managed Core.  This is especially important on Windows,
  // where Obsidian often inherits a long-lived Explorer environment.
  for (const name of Object.values(KEY_ENV)) delete env[name];
  for (const [provider, name] of Object.entries(KEY_ENV)) {
    if (keys[provider]) env[name] = keys[provider];
  }
  return new Promise((resolve, reject) => {
    let child: ChildProcess;
    try {
      child = spawn(exe, [...prefix, "--vault", vaultPath, "app", "--port", "0"],
        { env, stdio: ["pipe", "pipe", "pipe"], windowsHide: true });
    } catch (e) {
      reject(new CoreNotFound(String(e)));
      return;
    }
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`the core did not start within ${timeoutMs / 1000}s. ${err.slice(-400)}`));
    }, timeoutMs);
    child.on("error", (e: NodeJS.ErrnoException) => {
      clearTimeout(timer);
      reject(e.code === "ENOENT" ? new CoreNotFound(`${exe} was not found`) : e);
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`the core exited (${code}). ${err.slice(-400) || out.slice(-400)}`));
    });
    child.stderr?.on("data", (d) => { err += String(d); });
    child.stdout?.on("data", (d) => {
      out += String(d);
      const line = out.split("\n").find((l) => l.includes("\"listening\""));
      if (!line) return;
      clearTimeout(timer);
      try {
        const url = loopbackUrl(String(JSON.parse(line).listening));
        if (!url) throw new Error("the Core reported a non-loopback listening URL");
        resolve({ url, token, process: child, owned: true });
      } catch (e) {
        reject(e);
      }
    });
  });
}
