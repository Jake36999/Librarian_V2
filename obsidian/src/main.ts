// Librarian V2 in Obsidian: a desktop-only plugin that starts the local core
// for this vault and mounts the interface in a view. It contains no research
// logic; the core does, the same core the website and the MCP server use.

import { App, ItemView, Notice, Plugin, PluginSettingTab, SecretComponent, Setting, TFile, MarkdownView,
         WorkspaceLeaf, FileSystemAdapter } from "obsidian";
import { mount, type Mounted } from "../../ui/src/main";
import { CoreNotFound, KEY_ENV, start, type Running } from "./core";

const VIEW = "librarian-view";
const PROVIDER_LABEL: Record<string, string> = { deepinfra: "DeepInfra", openai: "OpenAI", anthropic: "Anthropic" };

interface Settings {
  corePath: string;
  secrets: Record<string, string>;     // provider -> secret id in Obsidian's secret storage
}

const DEFAULTS: Settings = { corePath: "", secrets: {} };

export default class LibrarianPlugin extends Plugin {
  settings: Settings = { ...DEFAULTS };
  core: Running | null = null;
  private starting: Promise<Running> | null = null;
  private lastMarkdownPath = "";
  private dirtyAt = new Map<string, number>();

  async onload(): Promise<void> {
    this.settings = { ...DEFAULTS, ...(await this.loadData()) };
    this.registerView(VIEW, (leaf) => new LibrarianView(leaf, this));
    this.addRibbonIcon("library", "Open the librarian", () => this.activate());
    this.addCommand({ id: "open", name: "Open the librarian", callback: () => this.activate() });
    this.addCommand({
      id: "ask-about-note", name: "Ask about this note",
      checkCallback: (checking) => {
        const file = this.app.workspace.getActiveFile();
        if (!file || file.extension !== "md") return false;
        if (!checking) void this.askAbout(file);
        return true;
      },
    });
    // Obsidian saves while a person types.  Remember recent changes rather
    // than treating every focused note as dirty forever: the Core receives a
    // short note-level heartbeat only while a real edit is actively settling.
    this.registerEvent(this.app.vault.on("modify", (file) => {
      if (file instanceof TFile && file.extension === "md") {
        this.lastMarkdownPath = file.path;
        this.dirtyAt.set(file.path, Date.now());
      }
    }));
    this.registerEvent(this.app.workspace.on("active-leaf-change", () => {
      const file = this.app.workspace.getActiveFile();
      if (file?.extension === "md") this.lastMarkdownPath = file.path;
    }));
    this.addSettingTab(new LibrarianSettings(this.app, this));
  }

  onunload(): void {
    // Closing a view or unloading Obsidian never acts as an implicit Host
    // stop.  The Core flushes/ends only through the explicit Librarian Host
    // controls, so long Clerk work and a paused checkpoint remain resumable.
    this.core = null;
  }

  vaultPath(): string {
    const adapter = this.app.vault.adapter;
    if (!(adapter instanceof FileSystemAdapter)) throw new Error("the librarian needs a vault on disk");
    return adapter.getBasePath();
  }

  keys(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const provider of Object.keys(KEY_ENV)) {
      const id = this.settings.secrets[provider];
      const value = id ? this.app.secretStorage.getSecret(id) : null;
      if (value) out[provider] = value;
    }
    return out;
  }

  ensureCore(): Promise<Running> {
    if (this.core) return Promise.resolve(this.core);
    if (!this.starting) {
      this.starting = start(this.settings.corePath, this.vaultPath(), this.keys())
        .then((running) => {
          this.core = running;
          running.process?.on("exit", () => { if (this.core === running) this.core = null; });
          return running;
        })
        .finally(() => { this.starting = null; });
    }
    return this.starting;
  }

  async stopCore(): Promise<void> {
    // We never terminate a Core discovered from the Librarian Host or another
    // adapter.  An Obsidian-owned child is stopped only for an explicit key
    // rotation/restart from this plugin.  Ask it to drain through the same
    // authenticated lifecycle contract the Host uses; do not turn a key
    // change into an unlogged process kill or a silent loss of Clerk work.
    const core = this.core;
    if (!core?.process) {
      this.core = null;
      return;
    }
    const child = core.process;
    let detail: any = {};
    try {
      const response = await fetch(`${core.url}/api/host/stop`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token,
                   "Origin": "app://obsidian.md" },
        body: JSON.stringify({ force: false }),
      });
      try { detail = await response.json(); } catch { detail = {}; }
      if (!response.ok) {
        const active = detail.active ? " Resolve or explicitly close the active work in Librarian first." : "";
        throw new Error(`${String(detail.error || "the Core refused to stop cleanly")}.${active}`);
      }
    } catch (e) {
      // Retain the running child for retry instead of falling back to kill().
      throw new Error(`Librarian Core was not restarted: ${(e as Error).message}`);
    }
    await new Promise<void>((resolve, reject) => {
      if (child.exitCode !== null) { resolve(); return; }
      const timer = window.setTimeout(() => reject(new Error("the Core is still draining work")), 15_000);
      child.once("exit", () => { window.clearTimeout(timer); resolve(); });
      child.once("error", (e) => { window.clearTimeout(timer); reject(e); });
    });
    if (this.core === core) this.core = null;
  }

  forgetCore(core?: Running): void {
    if (!core || this.core === core) this.core = null;
  }

  /** Keys reach the core only when it starts, so a changed key restarts it. */
  async restartCore(): Promise<void> {
    if (this.core && !this.core.owned) {
      throw new Error("Librarian is attached to an existing Host Core. Restart it from the Librarian Host before changing Obsidian-managed keys.");
    }
    await this.stopCore();
    for (const leaf of this.app.workspace.getLeavesOfType(VIEW)) {
      const view = leaf.view;
      if (view instanceof LibrarianView) await view.render();
    }
  }

  async activate(): Promise<LibrarianView | null> {
    let leaf = this.app.workspace.getLeavesOfType(VIEW)[0];
    if (!leaf) {
      leaf = this.app.workspace.getRightLeaf(false) ?? this.app.workspace.getLeaf(true);
      await leaf.setViewState({ type: VIEW, active: true });
    }
    await this.app.workspace.revealLeaf(leaf);
    return leaf.view instanceof LibrarianView ? leaf.view : null;
  }

  activeMarkdownPath(): string {
    const active = this.app.workspace.getActiveViewOfType(MarkdownView)?.file
      ?? this.app.workspace.getActiveFile();
    if (active?.extension === "md") this.lastMarkdownPath = active.path;
    return this.lastMarkdownPath;
  }

  documentIsDirty(path: string): boolean {
    const touched = this.dirtyAt.get(path) ?? 0;
    // The Core's heartbeat expires after ten seconds.  Retaining the same
    // interval here avoids a permanent reservation from a note merely viewed
    // before the Librarian pane was opened.
    if (Date.now() - touched > 10_000) {
      this.dirtyAt.delete(path);
      return false;
    }
    return true;
  }

  private async askAbout(file: TFile): Promise<void> {
    const view = await this.activate();
    view?.insert(`[[${file.basename}]] `);
  }
}

class LibrarianView extends ItemView {
  private mounted: Mounted | null = null;
  private heartbeatTimer: number | null = null;
  private heartbeatPath = "";

  constructor(leaf: WorkspaceLeaf, private plugin: LibrarianPlugin) {
    super(leaf);
  }

  getViewType(): string { return VIEW; }
  getDisplayText(): string { return "Librarian"; }
  getIcon(): string { return "library"; }

  async onOpen(): Promise<void> {
    await this.render();
  }

  async render(): Promise<void> {
    this.mounted?.dispose();
    this.mounted = null;
    this.stopHeartbeat(this.plugin.core ?? undefined);
    const root = this.contentEl;
    root.empty();
    root.addClass("librarian-view");
    root.createEl("p", { text: "Starting the librarian…" });
    let core: Running;
    try {
      core = await this.plugin.ensureCore();
    } catch (e) {
      root.empty();
      const box = root.createDiv({ cls: "librarian-missing" });
      if (e instanceof CoreNotFound) {
        box.createEl("p", { text: "The Librarian core is not installed, or Obsidian can't find it." });
        box.createEl("p", { text: "Install it with: pip install 'resource-librarian[mcp]' — then set its path in this plugin's settings if Obsidian doesn't find it on its own (apps started from the dock often don't see your shell's PATH)." });
      } else {
        box.createEl("p", { text: `The core did not start: ${(e as Error).message}` });
      }
      new Setting(box).addButton((b) => b.setButtonText("Try again").onClick(() => this.render()));
      return;
    }
    try {
      const response = await fetch(`${core.url}/api/meta`, {
        headers: { "X-Librarian-Token": core.token },
      });
      const meta = await response.json();
      if (!response.ok || String(meta.protocol_version) !== "2") {
        throw new Error(`Core protocol ${String(meta.protocol_version ?? "unknown")} is not compatible with this adapter.`);
      }
    } catch (e) {
      this.plugin.forgetCore(core);
      root.empty();
      root.createEl("p", { text: `The Librarian Core cannot mount safely: ${(e as Error).message}` });
      return;
    }
    root.empty();
    const host = root.createDiv({ cls: "librarian-host" });
    this.mounted = mount(host, {
      base: core.url, token: core.token, host: "obsidian",
      openNote: (_name, notePath) => { void this.app.workspace.openLinkText(notePath, "", false); },
      openElsewhere: () => { window.open(`${core.url}/`); },
      manageKeys: () => {
        const setting = (this.app as any).setting;
        setting?.open?.();
        setting?.openTabById?.(this.plugin.manifest.id);
      },
    });
    this.startHeartbeat(core);
  }

  insert(text: string): void {
    this.mounted?.insert(text);
  }

  async onClose(): Promise<void> {
    this.mounted?.dispose();
    this.mounted = null;
    this.stopHeartbeat(this.plugin.core ?? undefined);
  }

  private startHeartbeat(core: Running): void {
    const send = async () => {
      const path = this.plugin.activeMarkdownPath();
      if (this.heartbeatPath && this.heartbeatPath !== path) {
        await fetch(`${core.url}/api/documents/release`, {
          method: "POST", headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token },
          body: JSON.stringify({ path: this.heartbeatPath, editor: "Obsidian" }),
        }).catch(() => undefined);
      }
      this.heartbeatPath = path;
      if (!path || !this.plugin.documentIsDirty(path)) return;
      // Obsidian writes continuously while a Markdown editor is active.  The
      // Core uses a short expiry and debounce, so this reserves only this
      // document and never blocks work on the rest of the vault.
      await fetch(`${core.url}/api/documents/heartbeat`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token },
        body: JSON.stringify({ path, editor: "Obsidian", dirty: true }),
      }).catch(() => undefined);
    };
    void send();
    this.heartbeatTimer = window.setInterval(() => { void send(); }, 2_000);
  }

  private stopHeartbeat(core?: Running): void {
    if (this.heartbeatTimer !== null) window.clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
    const path = this.heartbeatPath;
    this.heartbeatPath = "";
    if (path && core) {
      void fetch(`${core.url}/api/documents/release`, {
        method: "POST", headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token },
        body: JSON.stringify({ path, editor: "Obsidian" }),
      }).catch(() => undefined);
    }
  }
}

class LibrarianSettings extends PluginSettingTab {
  constructor(app: App, private plugin: LibrarianPlugin) {
    super(app, plugin);
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    new Setting(containerEl)
      .setName("Core")
      .setDesc("The installed core: `resource-librarian`, or a Python that has the package. Leave empty to find it on the path.")
      .addText((t) => t.setPlaceholder("resource-librarian").setValue(this.plugin.settings.corePath)
        .onChange(async (value) => { this.plugin.settings.corePath = value; await this.plugin.saveData(this.plugin.settings); }));
    new Setting(containerEl).setHeading().setName("Keys");
    containerEl.createEl("p", { cls: "setting-item-description",
      text: "Choose a secret from Obsidian's secret storage for each provider. The key stays there; the core receives it in memory when it starts, and it never reaches a note, a log or the page." });
    for (const [provider, label] of Object.entries(PROVIDER_LABEL)) {
      new Setting(containerEl)
        .setName(label)
        .addComponent((el) => new SecretComponent(this.app, el)
          .setValue(this.plugin.settings.secrets[provider] ?? "")
          .onChange(async (id) => {
            this.plugin.settings.secrets[provider] = id;
            await this.plugin.saveData(this.plugin.settings);
            try {
              await this.plugin.restartCore();
              new Notice(`Librarian: ${label} key updated; the core restarted.`);
            } catch (e) {
              new Notice((e as Error).message);
            }
          }));
    }
    new Setting(containerEl)
      .setName("Restart the core")
      .setDesc(this.plugin.core ? `Running at ${this.plugin.core.url}` : "Not running.")
      .addButton((b) => b.setButtonText("Restart").onClick(async () => {
        try {
          await this.plugin.restartCore();
        } catch (e) {
          new Notice((e as Error).message);
        }
        this.display();
      }));
  }
}
