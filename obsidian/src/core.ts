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

/** Use an alive, local Core when the user already has one for this vault.
 * The Core still proves compatibility through /api/meta before the view
 * mounts. A missing/stale/unreadable private record is intentionally benign. */
export async function discover(vaultPath: string): Promise<Running | null> {
  try {
    const row = JSON.parse(await readFile(discoveryPath(vaultPath), "utf8")) as DiscoveryRecord;
    if (!row || typeof row.url !== "string" || typeof row.token !== "string"
        || typeof row.pid !== "number" || String(row.protocol_version) !== "2") return null;
    let sameVault = path.resolve(String(row.vault || ""));
    let wanted = path.resolve(vaultPath);
    if (process.platform === "win32") { sameVault = sameVault.toLowerCase(); wanted = wanted.toLowerCase(); }
    if (sameVault !== wanted) return null;
    const url = loopbackUrl(row.url);
    if (!url) return null;
    try { process.kill(row.pid, 0); } catch { return null; }
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
  const active = await discover(vaultPath);
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
