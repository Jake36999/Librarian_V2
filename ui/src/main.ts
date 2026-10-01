// The Librarian interface: one bundle, mounted by the website (it finds
// #librarian-root and the page token in the page) and by the Obsidian plugin
// (it calls Librarian.mount with its own options).

import { reader } from "./speech";
import { Api, type Event, type Options } from "./api";
export type { Options } from "./api";
import { AttachPanel } from "./attach";
import { Chat, type Session } from "./chat";
import { $, clear, h } from "./dom";
import { MODES, ModelTile, Popover, PROVIDERS, renderLibraries, renderModes, renderSessions, type Tier } from "./panels";
import { Settings } from "./settings";
import { DocPane } from "./pane";
import { link } from "./markdown";
import { Search, Staging } from "./views";

type View = "chat" | "staging" | "search";

/** After a rename, links to the old name already in the chat log point at
 *  nothing; each click target is captured when rendered, so replace them. */
function relinkChat(log: HTMLElement, oldName: string, newName: string,
                    open: (target: string) => void): void {
  log.querySelectorAll<HTMLAnchorElement>("a.wl").forEach((a) => {
    const target = a.title;
    const parts = target.split("/");
    if (parts[parts.length - 1].replace(/\.md$/i, "").toLowerCase() !== oldName.toLowerCase()) return;
    parts[parts.length - 1] = newName;
    const label = a.textContent === oldName ? newName : a.textContent ?? newName;
    a.replaceWith(link(parts.join("/"), label, open));
  });
}

class App {
  private api: Api;
  private state: Record<string, any> = {};
  // Bumped whenever this tab learns newer tiers than a fetch in flight could
  // hold (its own pick, or a `tiers_changed` event): a `/api/state` answer
  // requested before that must not put the older tiers back.
  private tiersEpoch = 0;
  private effects = new Map<string, string>();
  private pipelines: string[] = [];
  private session: Session = null;
  private view: View = "chat";

  private chat: Chat;
  private staging: Staging;
  private search: Search;
  private pane: DocPane;
  private body: HTMLElement;
  private paneButton: HTMLButtonElement;
  private settings: Settings;
  private modes: Popover;
  private models: Popover;
  private sessions: Popover;
  private libraries: Popover;
  private libraryButton = h("button", { class: "ghost lib-switch", title: "Switch library" }, "Library ▾");
  private attachPop: Popover;
  private attachPanel: AttachPanel;
  private tile: ModelTile;

  private title = h("span", { class: "title" }, "Librarian");
  private crumb = h("span", { class: "crumb" });
  private live = h("span", { class: "live", role: "status", title: "Connection to the core" });
  private chips = h("div", { class: "chips", "aria-label": "Queued actions" });
  private input = h("textarea", {
    id: "lib-msg", "aria-label": "Message",
    placeholder: "Ask the librarian. Enter sends, Shift+Enter adds a line.",
  }) as HTMLTextAreaElement;
  private attachments: { label: string; raw: string }[] = [];
  private attachRow = h("div", { class: "attach-row", hidden: true });
  private msgBox = h("div", { class: "msg-box" });
  private modeButton = h("button", { class: "tb" });
  private modelButton = h("button", { class: "tb" });
  // The effort slider (owner, 2026-10-01): how much work the person expects - helpers,
  // steps and time per reply, call budgets, how much is reviewed (effort.py).
  private effortValue = h("span", { class: "effort-value" }, "4");
  private effortInput = h("input", { type: "range", min: "1", max: "10", step: "1", value: "4",
    "aria-label": "Effort" }) as HTMLInputElement;
  private effortControl = h("label", { class: "effort tb" }, "Effort ", this.effortInput, this.effortValue);
  private sendButton: HTMLButtonElement;
  private views: Record<View, HTMLElement>;
  private nav: Record<View, HTMLButtonElement>;
  private notice = h("div", { class: "notice", role: "alert", hidden: true });

  constructor(root: HTMLElement, opts: Options) {
    this.api = new Api(opts);
    const openNote = (target: string) => void this.openDoc(target);
    reader.init(this.api, (message) => this.warn(message));
    this.chat = new Chat(this.api, {
      openNote,
      effectOf: (tool) => this.effects.get(tool) ?? "write",
      onSession: (s) => this.setSession(s),
      resend: (text) => void this.sendText(text),
      continueSession: () => void this.sendText("Continue the current research session from its next step. Read session_status first, complete the open work, and report any information you cannot verify as a gap. Do not claim the session or requested work is complete while session_status still shows open items."),
      rewind: (index) => void this.rewindMessage(index),
      branch: (index) => void this.branchMessage(index),
      openOffering: (id) => { this.staging.focusOffering(id); this.show("staging"); },
    });
    this.staging = new Staging(this.api, openNote, () => this.session?.session ?? "",
      (session) => this.setSession(session));
    this.search = new Search(this.api, openNote);
    this.pane = new DocPane(this.api, this.chat.plan, () => String(this.state.vault ?? ""),
      () => this.showPane(false),
      (oldName, newName) => relinkChat(this.chat.log, oldName, newName, openNote),
      () => this.session?.project ?? "",
      () => this.session?.session ?? "");
    this.opts = opts;
    this.settings = new Settings(this.api, () => this.state, () => this.refresh(), opts.manageKeys,
      (slot, label) => void this.chooseService(slot, label));

    const plus = h("button", { class: "tb icon", title: "Settings", "aria-label": "Settings",
      onclick: () => this.settings.open() }, "+");
    this.modes = new Popover("lib-modes", "Modes", this.modeButton);
    this.models = new Popover("lib-models", "Model", this.modelButton);
    const sessionsButton = h("button", { class: "ghost" }, "Sessions ▾");
    this.sessions = new Popover("lib-sessions", "Sessions", sessionsButton);
    this.libraries = new Popover("lib-libraries", "Libraries", this.libraryButton);
    this.libraryButton.onclick = () => {
      this.toggle(this.libraries);
      if (this.libraries.open) void renderLibraries(this.libraries, this.api, this.libraryName());
    };
    this.tile = new ModelTile(this.models, this.api, () => (this.state.tiers ?? []) as Tier[],
      () => Object.fromEntries(((this.state.keys ?? []) as any[]).map((k) => [k.provider, !!k.saved])),
      (tiers) => { this.state.tiers = tiers; this.tiersEpoch++; });
    const attachButton = h("button", { class: "tb icon", title: "Attach a file, or link a note or folder",
      "aria-label": "Attach" }, "📎");
    this.attachPop = new Popover("lib-attach", "Attach", attachButton);
    this.attachPanel = new AttachPanel(this.attachPop, this.api, (text) => this.insertIntoComposer(text),
      (file, raw) => this.addAttachment(file.name, raw));
    attachButton.onclick = () => { this.toggle(this.attachPop); if (this.attachPop.open) this.attachPanel.render(); };

    this.modeButton.onclick = () => this.toggle(this.modes);
    this.modelButton.onclick = async () => {
      this.tile.endSlot();                          // the toolbar's own button: the chat tiers
      this.toggle(this.models);
      if (this.models.open) {
        // The state a fast click can race (key status, chosen tiers) must be
        // fresh before the tile reads it, not whatever start() last fetched.
        await this.refresh();
        await this.tile.refresh();
      }
    };
    sessionsButton.onclick = () => {
      this.toggle(this.sessions);
      if (this.sessions.open) void renderSessions(this.sessions, this.api, (id) => this.attach(id), () => this.reset(),
        this.libraryName(), String(this.state.vault_path ?? ""));
    };
    // The website hands over to Obsidian by its URL scheme; the plugin passes its own.
    const elsewhere = h("button", {
      class: "tb", title: opts.host === "obsidian" ? "Continue in the website" : "Open this vault in Obsidian",
      onclick: opts.openElsewhere ?? (() => {
        window.location.href = `obsidian://open?vault=${encodeURIComponent(String(this.state.vault ?? ""))}`;
      }),
    }, opts.host === "obsidian" ? "↗ Open in browser" : "↗ Open in Obsidian");
    this.sendButton = h("button", { class: "send", onclick: () => this.send() }, "Send") as HTMLButtonElement;
    this.effortInput.oninput = () => { this.effortValue.textContent = this.effortInput.value; };
    this.effortInput.onchange = async () => {
      try {
        const chosen = await this.api.post("/api/effort", { level: Number(this.effortInput.value) });
        this.state.effort = chosen;
        this.paintEffort();
      } catch (e) { this.warn((e as Error).message); }
    };
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); void this.send(); }
    });

    const chatView = h("main", { class: "chatview" }, this.chat.log);
    this.views = { chat: chatView, staging: this.staging.el, search: this.search.el };
    const navButton = (v: View, label: string) => h("button", {
      role: "tab", onclick: () => this.show(v) }, label) as HTMLButtonElement;
    this.nav = { chat: navButton("chat", "Chat"), staging: navButton("staging", "Staging"),
                 search: navButton("search", "Search") };

    clear(this.msgBox, this.attachRow, this.input);
    const composer = h("div", { class: "composer" }, this.chips, this.msgBox,
      h("div", { class: "toolbar" }, plus, attachButton, this.modeButton, this.modelButton, this.effortControl, elsewhere, this.sendButton),
      this.modes.el, this.models.el, this.attachPop.el);

    this.paneButton = h("button", { class: "icon-btn", title: "Plan and notes beside the chat",
      "aria-label": "Show the document pane", onclick: () => this.showPane(!this.paneOpen) }, paneIcon()) as HTMLButtonElement;
    const resizer = h("div", { class: "lib-resizer", role: "separator", "aria-orientation": "vertical",
      title: "Drag to resize" });
    resizer.addEventListener("pointerdown", (e) => this.resize(e as PointerEvent, resizer));
    this.body = h("div", { class: "lib-body" },
      h("div", { class: "lib-main" }, this.notice, chatView, this.staging.el, this.search.el, composer),
      resizer, this.pane.el);
    clear(root,
      h("div", { class: `lib-app host-${opts.host}` },
        h("header", {}, h("div", { class: "anchor" }, this.libraryButton, this.libraries.el),
          h("div", { class: "anchor" }, sessionsButton, this.sessions.el),
          this.title, this.crumb,
          h("nav", { role: "tablist", "aria-label": "Views" }, Object.values(this.nav)), this.live,
          this.paneButton),
        this.body),
      this.settings.dialog);
    this.composer = composer;

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") [this.modes, this.models, this.sessions, this.libraries, this.attachPop].forEach((p) => p.show(false));
    });
    document.addEventListener("click", (e) => {
      // The dispatch path, not `contains`: a click that re-renders the popover
      // detaches its own target, which is still inside.
      const path = e.composedPath();
      for (const p of [this.modes, this.models, this.sessions, this.libraries, this.attachPop]) {
        if (p.open && !path.includes(p.el) && !path.includes(p.button)) p.show(false);
      }
    });
    this.show("chat");
    const width = recall("pane-w");
    if (width) this.body.style.setProperty("--pane-w", width);
    // Open by default where there is room for both; the choice is remembered.
    const saved = recall("pane");
    this.showPane(saved ? saved === "open" : (root.clientWidth || window.innerWidth) >= 1000);
  }

  private composer: HTMLElement;
  private opts: Options;
  private paneOpen = true;

  // -- the document pane -------------------------------------------------------
  /** A [[link]]: in Obsidian the real note opens; elsewhere it opens beside the chat. */
  private async openDoc(target: string): Promise<void> {
    if (this.opts.openNote) {
      try {
        const doc = await this.api.get(`/api/file?path=${encodeURIComponent(target)}`);
        this.opts.openNote(doc.name, doc.path);
        return;
      } catch { /* not a file the core can see: show why in the pane */ }
    }
    this.showPane(true);
    await this.pane.open(target);
  }

  private showPane(on: boolean): void {
    this.paneOpen = on;
    this.body.classList.toggle("pane-open", on);
    this.body.classList.toggle("pane-closed", !on);
    this.paneButton.setAttribute("aria-pressed", String(on));
    remember("pane", on ? "open" : "closed");
  }

  private resize(start: PointerEvent, handle: HTMLElement): void {
    start.preventDefault();
    handle.setPointerCapture(start.pointerId);
    const rect = this.body.getBoundingClientRect();
    const move = (e: PointerEvent) => {
      const width = Math.min(Math.max(rect.right - e.clientX, 300), rect.width - 360);
      this.body.style.setProperty("--pane-w", `${Math.round(width)}px`);
    };
    const up = () => {
      handle.removeEventListener("pointermove", move as EventListener);
      remember("pane-w", this.body.style.getPropertyValue("--pane-w"));
    };
    handle.addEventListener("pointermove", move as EventListener);
    handle.addEventListener("pointerup", up, { once: true });
  }

  async start(): Promise<void> {
    try {
      const tools = await this.api.get("/api/tools");
      for (const t of tools.tools ?? []) this.effects.set(t.name, t.effect);
      const listed = await this.api.tool("list_workflows").catch(() => ({ definitions: [] }));
      this.pipelines = ((listed.definitions ?? []) as any[]).filter((d) => d.kind === "pipeline").map((d) => d.name);
      await this.refresh();
    } catch (e) {
      this.warn(`The core did not answer: ${(e as Error).message}. Is \`resource-librarian app\` running?`);
      return;
    }
    this.api.events((event) => this.onEvent(event), (live) => {
      this.live.className = `live ${live ? "on" : "off"}`;
      this.live.textContent = live ? "●" : "○ reconnecting";
      if (live) void this.refresh();
    });
    this.input.focus();
  }

  private async refresh(): Promise<void> {
    const epoch = this.tiersEpoch;
    const fresh = await this.api.get("/api/state");
    if (this.tiersEpoch !== epoch) fresh.tiers = this.state.tiers;     // newer than this answer
    this.state = fresh;
    this.paintSendButton();
    this.libraryButton.textContent = `${this.libraryName()} ▾`;
    this.libraryButton.title = `Switch library - this is ${this.libraryName()} (${String(this.state.vault_path ?? "")})`;
    document.title = `${this.libraryName()} - Librarian`;
    this.setSession(this.state.session ?? null);
    this.paintToolbar();
    this.paintChips();
    if (this.state.busy) this.chat.setWorking(true);
    for (const request of this.state.pending ?? []) this.chat.handle({ seq: 0, type: "permission_request", ...request });
  }

  private onEvent(event: Event): void {
    this.chat.handle(event);
    switch (event.type) {
      case "mode_changed":
        this.state.mode = event.to;
        this.paintToolbar();
        break;
      case "tiers_changed":
        this.state.tiers = event.tiers;
        this.tiersEpoch++;
        this.paintToolbar();
        if (this.models.open) this.tile.render();
        break;
      case "turn_done": case "error":
        this.state.busy = false;
        this.paintSendButton();
        break;
      case "action_started": case "action_progress": case "action_done": {
        const actions = (this.state.actions ?? []) as any[];
        const at = actions.findIndex((a) => a.id === event.id);
        const row = { id: event.id, name: event.name, status: event.status, steps: event.steps, reason: event.reason };
        if (at >= 0) actions[at] = row; else actions.push(row);
        this.state.actions = actions;
        this.paintChips();
        if (event.type === "action_done" && this.view === "staging") void this.staging.load();
        break;
      }
      case "person_acted":
        if (event.session) this.setSession(event.session);
        if (this.view === "staging") void this.staging.load();
        break;
      case "library_switched":
        // Another tab (or this one) switched library: this page belongs to
        // the one that was left, so load the new one.
        window.location.reload();
        break;
    }
  }

  // -- painting ------------------------------------------------------------
  private paintEffort(): void {
    const e = this.state.effort;
    if (!e) return;
    this.effortInput.value = String(e.level);
    this.effortValue.textContent = String(e.level);
    this.effortControl.title = `Effort ${e.level} of 10 - how much work you expect. `
      + `Helpers at once: ${e.lead_agents} on the lead model, ${e.tier2_agents} on the notes model; `
      + `small-task calls at once: ${e.tier3_agents}. Up to ${e.turn_steps} steps and `
      + `${Math.round(e.turn_seconds / 60)} min per reply; call budgets x${e.budget_scale}. `
      + `Review: ${e.review_replies ? `offerings and up to ${e.review_claims} claims per reply`
        : e.review_offerings ? "offerings' claims" : "nothing automatic"}.`;
  }

  private paintToolbar(): void {
    this.paintEffort();
    const mode = MODES.find(([v]) => v === this.state.mode);
    clear(this.modeButton, "Modes: ", h("strong", {}, mode ? mode[1].split(" ")[0] : "?"), " ▾");
    const tier = ((this.state.tiers ?? []) as Tier[])[0];
    clear(this.modelButton, tier
      ? [h("span", { class: "badge" }, "1"), ` ${tier.model} · ${PROVIDERS[tier.provider] ?? tier.provider}`]
      : "Choose models", " ▾");
    renderModes(this.modes, this.api, this.state.mode, this.state.queued_actions ?? [], this.pipelines,
      (msg) => this.warn(msg), this.state.queued_inputs ?? {});
  }

  private paintChips(): void {
    const running = ((this.state.actions ?? []) as any[]).filter((a) => a.status === "running" || a.status === "paused");
    clear(this.chips, running.map((a) => h("span", { class: "chip" },
      `${a.name} · ${a.status === "paused" ? `paused${a.reason ? `: ${a.reason}` : ""}` : `${a.steps} steps`}`,
      a.status === "running" ? h("button", { "aria-label": `Cancel ${a.name}`, onclick: async () => {
        try { await this.api.post(`/api/actions/${a.id}/cancel`); } catch (e) { this.warn((e as Error).message); }
      } }, "✕") : null)));
  }

  private setSession(session: Session): void {
    // A tool result's envelope is partial; a full view has `phases`.
    if (session && this.session && session.session === this.session.session)
      session = { ...this.session, ...session };
    this.session = session;
    this.chat.renderPlan(session);
    if (!session) {
      this.title.textContent = this.libraryName();
      this.crumb.textContent = "no thread";
      return;
    }
    this.title.textContent = session.project || session.question || this.libraryName();
    this.crumb.textContent = `${session.purpose ?? ""} · phase: ${session.phase ?? ""}${session.status && session.status !== "open" ? ` · ${session.status}` : ""}`;
  }

  /** The open library by its own name: two libraries made by new-vault.ps1 share the
   *  folder name `.librarian-app`, so the folder cannot say which one this is. */
  private libraryName(): string {
    return String(this.state.vault_name ?? this.state.vault ?? "Librarian");
  }

  private show(view: View): void {
    this.view = view;
    for (const [v, el] of Object.entries(this.views)) el.hidden = v !== view;
    for (const [v, b] of Object.entries(this.nav)) b.setAttribute("aria-selected", String(v === view));
    this.composer.hidden = view !== "chat";
    if (view === "staging") void this.staging.load(true);
    if (view === "search") this.search.focus();
  }

  /** R17: Settings' "Choose…" for a service slot opens the model tile to pick one model
   *  for it; picking (or Cancel) returns to Settings. */
  private async chooseService(slot: string, label: string,
                              current?: { provider: string; model: string }): Promise<void> {
    // After the click that asked for it has finished: that click is still on its way up
    // to the document, whose click-outside handler would close a popover opened now.
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    this.tile.startSlot(slot, label, () => {
      if (this.models.open) this.toggle(this.models);
      this.settings.open("connections");
    }, current?.model ? current : undefined);
    if (!this.models.open) this.toggle(this.models);
    await this.refresh();
    await this.tile.refresh();
  }

  private toggle(pop: Popover): void {
    const open = !pop.open;
    [this.modes, this.models, this.sessions, this.attachPop].forEach((p) => p.show(false));
    pop.show(open);
  }

  /** A file just attached: a chip above the composer, its icon standing for
   *  it, splitting the box in two - the reference itself already sits in the
   *  message text (`insertIntoComposer` put it there); removing the chip
   *  takes that same text back out. */
  private addAttachment(label: string, raw: string): void {
    this.attachments.push({ label, raw });
    this.renderAttachments();
  }

  private removeAttachment(i: number): void {
    const [gone] = this.attachments.splice(i, 1);
    if (gone) this.input.value = this.input.value.replace(`${gone.raw} `, "").replace(gone.raw, "");
    this.renderAttachments();
  }

  private renderAttachments(): void {
    const has = this.attachments.length > 0;
    this.attachRow.hidden = !has;
    this.msgBox.classList.toggle("has-attachments", has);
    clear(this.attachRow, this.attachments.map((a, i) => h("span", { class: "attach-chip" },
      fileIcon(), h("span", { class: "attach-name" }, a.label),
      h("button", { class: "attach-remove", "aria-label": `Remove ${a.label}`,
        onclick: () => this.removeAttachment(i) }, "×"))));
  }

  private insertIntoComposer(text: string): void {
    const el = this.input;
    const start = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, start);
    const insertion = `${before && !/\s$/.test(before) ? " " : ""}${text} `;
    el.value = before + insertion + el.value.slice(end);
    const caret = start + insertion.length;
    el.focus();
    el.setSelectionRange(caret, caret);
  }

  private warn(message: string): void {
    this.notice.hidden = false;
    clear(this.notice, message, h("button", { class: "ghost push", "aria-label": "Dismiss",
      onclick: () => { this.notice.hidden = true; } }, "✕"));
  }

  // -- actions ---------------------------------------------------------------
  private async send(): Promise<void> {
    if (this.state.busy) {
      try { await this.api.post("/api/chat/cancel", {}); }
      catch (e) { this.warn((e as Error).message); }
      return;
    }
    const text = this.input.value.trim();
    if (!text) return;
    this.input.value = "";
    this.attachments = [];
    this.renderAttachments();
    await this.sendText(text);
  }

  /** The send path itself, shared by the composer and a message's Retry
   *  button - which resends the same text without touching the composer. */
  private async sendText(text: string): Promise<void> {
    if (!text) return;
    try {
      await this.api.post("/api/chat", { text });
      this.state.busy = true;
      this.paintSendButton();
    } catch (e) {
      const message = (e as Error).message;
      this.warn(message.includes("tier 1") ? "Choose a chat model first: click Model, then a model (it becomes tier 1)." : message);
    }
  }

  private paintSendButton(): void {
    const busy = !!this.state.busy;
    this.sendButton.textContent = busy ? "Stop" : "Send";
    this.sendButton.setAttribute("aria-label", busy ? "Stop reply" : "Send message");
    this.sendButton.title = busy ? "Stop the current reply" : "Send message";
  }

  private async attach(id: string): Promise<void> {
    try { await this.api.post("/api/chat/attach", { session_id: id }); this.show("chat"); }
    catch (e) { this.warn((e as Error).message); }
  }

  private async rewindMessage(index: number): Promise<void> {
    const sessionId = this.session?.session;
    if (!sessionId) return;
    try {
      const out = await this.api.tool("rewind_session", { to_index: index }, sessionId);
      if (out.error) { this.warn(String(out.detail ?? out.error)); return; }
      this.chat.applyRewind(out.messages ?? [], Number(out.min_rewind_index ?? 0));
    } catch (e) { this.warn((e as Error).message); }
  }

  /** Branching switches to the new thread straight away, the same way
   *  picking a thread from Sessions does - there is nothing else to show
   *  until it's the one open. */
  private async branchMessage(index: number): Promise<void> {
    const sessionId = this.session?.session;
    if (!sessionId) return;
    try {
      const out = await this.api.tool("branch_session", { to_index: index }, sessionId);
      if (out.error) { this.warn(String(out.detail ?? out.error)); return; }
      await this.attach(String(out.branched));
    } catch (e) { this.warn((e as Error).message); }
  }

  /** Put text into the message box (Obsidian: "Ask about this note"). */
  insert(text: string): void {
    this.show("chat");
    const gap = this.input.value && !this.input.value.endsWith(" ") ? " " : "";
    this.input.value += gap + text;
    this.input.focus();
  }

  private async reset(): Promise<void> {
    try { await this.api.post("/api/chat/reset"); } catch (e) { this.warn((e as Error).message); }
  }
}

/** A window split in two, drawn rather than an emoji, so it matches the theme. */
function paneIcon(): SVGElement {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of [["rect", { x: "1.5", y: "2.5", width: "13", height: "11", rx: "2" }],
                              ["line", { x1: "9", y1: "2.5", x2: "9", y2: "13.5" }]] as const) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", "currentColor");
    el.setAttribute("stroke-width", "1.3");
    svg.append(el);
  }
  return svg;
}

/** A dog-eared page, for an attached file's chip. */
function fileIcon(): SVGElement {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "13");
  svg.setAttribute("height", "13");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of [
    ["path", { d: "M3.5 1.8h6l3 3v8.7a.7.7 0 0 1-.7.7h-8.3a.7.7 0 0 1-.7-.7V2.5a.7.7 0 0 1 .7-.7Z" }],
    ["path", { d: "M9.5 1.8v2.6a.7.7 0 0 0 .7.7h2.3" }],
  ] as const) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", "currentColor");
    el.setAttribute("stroke-width", "1.2");
    el.setAttribute("stroke-linejoin", "round");
    svg.append(el);
  }
  return svg;
}

// Per-viewer conveniences only; the page works the same without them.
function remember(key: string, value: string): void {
  try { localStorage.setItem(`librarian:${key}`, value); } catch { /* private window */ }
}

function recall(key: string): string {
  try { return localStorage.getItem(`librarian:${key}`) ?? ""; } catch { return ""; }
}

export interface Mounted { insert(text: string): void }

export function mount(root: HTMLElement, opts: Options): Mounted {
  root.classList.add("librarian-root", `host-${opts.host}`);
  const app = new App(root, opts);
  void app.start();
  return { insert: (text) => app.insert(text) };
}

// The website: the core serves the page with its token in a meta tag.
const auto = typeof document !== "undefined" ? document.getElementById("librarian-root") : null;
if (auto) {
  const token = $<HTMLMetaElement>(document, "meta[name=librarian-token]")?.content ?? "";
  mount(auto, { base: "", token, host: "website" });
}
