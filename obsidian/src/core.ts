// Starting the local core: the plugin can't install Python packages (Obsidian's
// developer policies), so it finds an installed core, starts it on loopback with
// a fresh page token, and hands it the keys from Obsidian's secret storage as
// environment variables: in memory only, never written anywhere.

import { spawn, type ChildProcess } from "node:child_process";
import { randomBytes } from "node:crypto";
import * as path from "node:path";

export const KEY_ENV: Record<string, string> = {
  deepinfra: "DEEPINFRA_API_KEY", openai: "OPENAI_API_KEY", anthropic: "ANTHROPIC_API_KEY",
};

export interface Running { url: string; token: string; process: ChildProcess }

export class CoreNotFound extends Error {}

/** `resource-librarian`, or a Python interpreter that has the package. */
function command(corePath: string): [string, string[]] {
  const exe = corePath.trim() || "resource-librarian";
  return /^python[\d.]*(\.exe)?$/i.test(path.basename(exe)) ? [exe, ["-m", "resource_librarian"]] : [exe, []];
}

export function start(corePath: string, vaultPath: string, keys: Record<string, string>,
                      timeoutMs = 20000): Promise<Running> {
  const token = randomBytes(24).toString("base64url");
  const [exe, prefix] = command(corePath);
  // The core exits when this pipe closes, so it never outlives Obsidian.
  const env: Record<string, string | undefined> = { ...process.env, LIBRARIAN_TOKEN: token,
                                                    LIBRARIAN_EXIT_WITH_STDIN: "1" };
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
        const url = String(JSON.parse(line).listening).replace(/\/$/, "");
        resolve({ url, token, process: child });
      } catch (e) {
        reject(e);
      }
    });
  });
}
