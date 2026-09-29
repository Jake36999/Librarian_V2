// Librarian V2 in Obsidian: a desktop-only plugin that starts the local core
// for this vault and mounts the interface in a view. It contains no research
// logic; the core does, the same core the website and the MCP server use.

import { App, ItemView, Notice, Plugin, PluginSettingTab, SecretComponent, Setting, TFile,
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
    this.addSettingTab(new LibrarianSettings(this.app, this));
  }

  onunload(): void {
    this.stopCore();
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
          running.process.on("exit", () => { if (this.core === running) this.core = null; });
          return running;
        })
        .finally(() => { this.starting = null; });
    }
    return this.starting;
  }

  stopCore(): void {
    this.core?.process.kill();
    this.core = null;
  }

  /** Keys reach the core only when it starts, so a changed key restarts it. */
  async restartCore(): Promise<void> {
    this.stopCore();
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

  private async askAbout(file: TFile): Promise<void> {
    const view = await this.activate();
    view?.insert(`[[${file.basename}]] `);
  }
}

class LibrarianView extends ItemView {
  private mounted: Mounted | null = null;

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
  }

  insert(text: string): void {
    this.mounted?.insert(text);
  }

  async onClose(): Promise<void> {
    this.mounted = null;
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
            await this.plugin.restartCore();
            new Notice(`Librarian: ${label} key updated; the core restarted.`);
          }));
    }
    new Setting(containerEl)
      .setName("Restart the core")
      .setDesc(this.plugin.core ? `Running at ${this.plugin.core.url}` : "Not running.")
      .addButton((b) => b.setButtonText("Restart").onClick(async () => { await this.plugin.restartCore(); this.display(); }));
  }
}
