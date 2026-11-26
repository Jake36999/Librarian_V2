// The Librarian interface: one bundle, mounted by the website (it finds
// #librarian-root and the page token in the page) and by the Obsidian plugin
// (it calls Librarian.mount with its own options).

import { COMMANDS, preference } from "./commands";
import { reader } from "./speech";
import { Api, ApiError, type Event, type Options } from "./api";
export type { Options } from "./api";
import { AttachPanel } from "./attach";
import { Chat, type Session } from "./chat";
import { $, claimInstance, clear, h, cls, sel } from "./dom";
import { MODES, ModelTile, Popover, PROVIDERS, renderLibraries, renderModes, renderSessions, renderWorkflows, type Tier } from "./panels";
import { Settings } from "./settings";
import { DocPane } from "./pane";
import { link } from "./markdown";
import { Search, Staging } from "./views";

type View = "chat" | "staging" | "search";

/** A finished run's outputs in one line: " · read 0, failed 5". Lists show their size. */
export function actionOutputs(outputs: unknown): string {
  if (!outputs || typeof outputs !== "object") return "";
  const parts = Object.entries(outputs as Record<string, unknown>)
    .filter(([k, v]) => k !== "errors" && v !== null && v !== undefined && v !== "")
    .slice(0, 6)
    .map(([k, v]) => `${k} ${Array.isArray(v) ? v.length
      : typeof v === "object" ? Object.keys(v as object).length
      : String(v).length > 40 ? `${String(v).slice(0, 39)}…` : String(v)}`);
  return parts.length ? ` · ${parts.join(", ")}` : "";
}

/** After a rename, links to the old name already in the chat log point at
 *  nothing; each click target is captured when rendered, so replace them. */
function relinkChat(log: HTMLElement, oldName: string, newName: string,
                    open: (target: string) => void): void {
  log.querySelectorAll<HTMLAnchorElement>(sel("a.wl")).forEach((a) => {
    const target = a.title;
    const parts = target.split("/");
    if (parts[parts.length - 1].replace(/\.md$/i, "").toLowerCase() !== oldName.toLowerCase()) return;
    parts[parts.length - 1] = newName;
    const label = a.textContent === oldName ? newName : a.textContent ?? newName;
    a.replaceWith(link(parts.join("/"), label, open));
  });
}

class App {
  private readonly ids = claimInstance();     // mount-unique IDs (MF-008); first so fields can use it
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
  private checkpoints: Popover;
  private libraryButton = h("button", { class: "ghost lib-switch", title: "Switch library" }, "Library ▾");
  // This library's own Geo-Grapher, run by this Core (one library, one Geo service).
  private geoButton = h("button", { class: "ghost geo-open", title: "Open this library's graphs in Geo-Grapher",
    onclick: () => void this.openGeo() }, "Geo-Grapher ↗");
  private checkpointButton = h("button", { class: "ghost", title: "Decisions waiting for you" }, "Checkpoints ▾");
  // AR-F03: permission requests waiting for an answer, shown on the Chat tab from any view.
  private waiting = new Set<string>();
  // Close controls (owner, 2026-11-17): this library's Geo-Grapher, or the whole library
  // (its Core, which stops Geo-Grapher with it), each closed gracefully.
  // An icon so the header does not wrap on narrow hosts (the smoke run's 497 px pane).
  private closeButton = h("button", { class: "ghost lib-close", title: "Close Geo-Grapher or this library",
    "aria-label": "Close Geo-Grapher or this library" }, "⏻");
  private closeMenu!: Popover;
  private attachPop: Popover;
  private attachPanel: AttachPanel;
  private tile: ModelTile;

  private title = h("span", { class: "title" }, "Librarian");
  private crumb = h("span", { class: "crumb" });
  private live = h("span", { class: "live", role: "status", title: "Connection to the core" });
  private chips = h("div", { class: "chips", "aria-label": "Queued actions" });
  // A run's full record, opened from its chip (M1a, W-WFR-01): the chip shows a summary, and dismissing
  // it no longer loses what the run did, what failed and why.
  private runDialog = h("dialog", { class: "lib-dialog run-record", "aria-label": "Run record" }) as HTMLDialogElement;
  private input = h("textarea", {
    id: this.ids.id("lib-msg"), class: "composer-text", "aria-label": "Message",
    placeholder: "Ask the librarian. Enter sends, Shift+Enter adds a line.",
  }) as HTMLTextAreaElement;
  private attachments: { label: string; raw: string }[] = [];
  private sending = false;      // a chat POST is in flight (MF-005)
  private cancelling = new Set<string>();   // workflow runs with a cancel requested (MF-006)
  private savedPaneWidth = 0;                // the person's split preference, px (MF-008)
  private bodyObserver: ResizeObserver | null = null;
  private stopping = false;     // Stop was pressed; waiting for the Core's outcome
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
  private batchNotice = h("div", {class:"notice", role:"status", hidden:true});
  private notice = h("div", { class: "notice", role: "alert", hidden: true });

  constructor(private root: HTMLElement, opts: Options) {
    this.api = new Api(opts);
    const openNote = (target: string) => void this.openDoc(target);
    reader.init(this.api, (message) => this.warn(message));
    this.chat = new Chat(this.api, {
      openNote,
      effectOf: (tool) => this.effects.get(tool) ?? "write",
      onSession: (s) => this.setSession(s),
      resend: (text) => void this.sendText(text),
      newThread: () => void this.reset(),
      continueSession: () => void this.sendText("Continue the current research session from its next step. Read session_status first, complete the open work, and report any information you cannot verify as a gap. Do not claim the session or requested work is complete while session_status still shows open items."),
      openModelPicker: () => {
        this.toggle(this.models);
        if (this.models.open) void this.tile.refresh();
      },
      rewind: (index) => void this.rewindMessage(index),
      branch: (index) => void this.branchMessage(index),
      openOffering: (id) => { this.staging.focusOffering(id); this.show("staging"); },
    });
    this.staging = new Staging(this.api, openNote, () => this.session?.session ?? "",
      (session) => this.setSession(session), () => this.settings.open("models"), event => {
        if (event === "start" && preference("job-start") === "activity") { this.show("search"); this.search.activity(); }
        if (event === "finish" && preference("batch-notice") === "on") {
          this.batchNotice.hidden = false;
          clear(this.batchNotice, this.libraryName() + ": ingestion batch finished. ",
            h("button", {class:"ghost",onclick:()=>{this.batchNotice.hidden=true;this.show("staging");}}, "View batch"),
            h("button", {class:"ghost",onclick:()=>{this.batchNotice.hidden=true;}}, "Dismiss"));
        }
      }, () => {
        const tiers = this.state.tiers ?? [], route = tiers[2] ?? tiers[1] ?? tiers[0];
        return "Library: " + this.libraryName() + ". " + (route ? "Chat small-task selection: " + route.provider + " / " + route.model + ". Individual steps can use other routes." : "No chat model selected.");
      }, () => String(this.state.vault_path || this.state.vault || ""));
    this.search = new Search(this.api, openNote);
    this.pane = new DocPane(this.api, this.chat.plan, () => String(this.state.vault ?? ""),
      () => this.showPane(false),
      (oldName, newName) => relinkChat(this.chat.log, oldName, newName, openNote),
      () => this.session?.project ?? "",
      () => this.session?.session ?? "");
    this.opts = opts;
    this.settings = new Settings(this.api, () => this.state, () => this.refresh(), opts.manageKeys,
      (slot, label, current, role) => void this.chooseService(slot, label, current, role), opts.host === "obsidian", id => this.command(id), base => this.ids.id(base));

    const settingsButton = h("button", { class: "ghost", title: "Settings", "aria-label": "Settings",
      onclick: () => this.settings.open() }, "Settings");
    this.modes = new Popover(this.ids.id("lib-modes"), "Modes", this.modeButton, "lib-modes");
    this.models = new Popover(this.ids.id("lib-models"), "Model", this.modelButton, "lib-models");
    const sessionsButton = h("button", { class: "ghost" }, "Sessions ▾");
    this.sessions = new Popover(this.ids.id("lib-sessions"), "Sessions", sessionsButton, "lib-sessions");
    this.libraries = new Popover(this.ids.id("lib-libraries"), "Libraries", this.libraryButton, "lib-libraries");
    this.checkpoints = new Popover(this.ids.id("lib-checkpoints"), "Checkpoints", this.checkpointButton, "lib-checkpoints");
    this.closeMenu = new Popover(this.ids.id("lib-close"), "Close", this.closeButton, "lib-close-menu");
    this.closeButton.onclick = () => { this.toggle(this.closeMenu); if (this.closeMenu.open) void this.renderClose(); };
    this.libraryButton.onclick = () => {
      this.toggle(this.libraries);
      if (this.libraries.open) void renderLibraries(this.libraries, this.api, this.libraryName());
    };
    this.tile = new ModelTile(this.models, this.api, () => (this.state.tiers ?? []) as Tier[],
      () => Object.fromEntries(((this.state.keys ?? []) as any[]).map((k) => [k.provider, !!k.saved])),
      (tiers) => { this.state.tiers = tiers; this.tiersEpoch++; });
    const attachButton = h("button", { class: "tb icon", title: "Attach a file, or link a note or folder",
      "aria-label": "Attach" }, "📎");
    this.attachPop = new Popover(this.ids.id("lib-attach"), "Attach", attachButton, "lib-attach");
    this.attachPanel = new AttachPanel(this.attachPop, this.api, (text) => this.insertIntoComposer(text),
      (file, raw) => this.addAttachment(file.name, raw), {
        // The pane is the one place to navigate to a file: it opens on Browse with a hint.
        pickFile: () => { this.showPane(true); this.pane.pickFile("Pick a file to add to the chat",
          (reference) => this.insertIntoComposer(reference)); },
        openRegistry: () => void this.openSkillRegistry(),
        workflows: (rerender) => renderWorkflows(this.attachPop, this.api, this.state.queued_actions ?? [],
          this.pipelines, (msg) => this.warn(msg), this.state.queued_inputs ?? {},
          this.ids.id("librarian-workflow"),
          this.libraryName() + " · " + (this.session?.session ?? "no active conversation"), rerender),
      });
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
    this.checkpointButton.onclick = () => {
      this.toggle(this.checkpoints);
      if (this.checkpoints.open) void this.refreshCheckpoints();
    };
    // The website hands over to Obsidian by its URL scheme; the plugin passes its own.
    const elsewhere = h("button", {
      class: "tb", title: opts.host === "obsidian" ? "Continue in the website" : "Open this vault in Obsidian",
      onclick: opts.openElsewhere ?? (() => {
        window.location.href = `obsidian://open?vault=${encodeURIComponent(String(this.state.vault ?? ""))}`;
      }),
    }, opts.host === "obsidian" ? "↗ Open in browser" : "↗ Open in Obsidian");
    this.sendButton = h("button", { class: "send", onclick: () => (this.state.busy ? this.stop() : this.send()) }, "Send") as HTMLButtonElement;
    this.effortInput.oninput = () => { this.effortValue.textContent = this.effortInput.value; };
    this.effortInput.onchange = async () => {
      try {
        const chosen = await this.api.post("/api/effort", { level: Number(this.effortInput.value) });
        this.state.effort = chosen;
        this.paintEffort();
      } catch (e) {
        // MF-006: the slider returns to the level the Core confirmed.
        this.paintEffort();
        this.warn(`Effort not changed: ${(e as Error).message}`);
      }
    };
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.altKey && !e.isComposing && (e.ctrlKey || e.metaKey) === (preference("send") === "modified")) { e.preventDefault(); if (!this.state.busy) void this.send(); }
    });

    const chatView = h("main", { class: "chatview" }, this.chat.log, this.attachPop.el);
    this.views = { chat: chatView, staging: this.staging.el, search: this.search.el };
    const navButton = (v: View, label: string) => h("button", {
      role: "tab", onkeydown: (event: globalThis.Event) => {
        const e = event as KeyboardEvent;
        const names = Object.keys(this.nav) as View[], index = names.indexOf(v);
        const next = e.key === "Home" ? 0 : e.key === "End" ? names.length-1 :
          e.key === "ArrowRight" ? (index+1)%names.length : e.key === "ArrowLeft" ? (index+names.length-1)%names.length : -1;
        if (next >= 0) { e.preventDefault(); this.show(names[next]); this.nav[names[next]].focus(); }
      }, onclick: () => this.show(v) }, label) as HTMLButtonElement;
    this.nav = { chat: navButton("chat", "Chat"), staging: navButton("staging", "Staging"),
                 search: navButton("search", "Search") };

    clear(this.msgBox, this.attachRow, this.input);
    const composer = h("div", { class: "composer" }, this.chips, this.msgBox,
      h("div", { class: "toolbar" }, attachButton, this.modeButton, this.modelButton, this.effortControl, elsewhere, this.sendButton),
      this.modes.el, this.models.el);

    this.paneButton = h("button", { class: "icon-btn", title: "Plan and notes beside the chat",
      "aria-label": "Show the document pane", onclick: () => this.showPane(!this.paneOpen) }, paneIcon()) as HTMLButtonElement;
    const resizer = h("div", { class: "lib-resizer", role: "separator", "aria-orientation": "vertical",
      tabindex: "0", "aria-label": "Document pane width", title: "Drag or use arrow keys to resize" });
    resizer.addEventListener("keydown", (e) => {
      const room = this.body.clientWidth - resizer.offsetWidth;
      const now = this.pane.el.getBoundingClientRect().width;
      const widths: Record<string,number> = {Home:300, End:room-360, ArrowLeft:now+24, ArrowRight:now-24};
      if (!(e.key in widths)) return;
      e.preventDefault(); this.savedPaneWidth = widths[e.key]; this.savedPaneWidth = this.applyPaneWidth();
      remember("pane-w",String(this.savedPaneWidth)+"px");
    });
    resizer.addEventListener("pointerdown", (e) => this.resize(e as PointerEvent, resizer));
    this.body = h("div", { class: "lib-body" },
      h("div", { class: "lib-main" }, this.notice, this.batchNotice, chatView, this.staging.el, this.search.el, composer),
      resizer, this.pane.el);
    clear(root,
      h("div", { class: `lib-app host-${opts.host}` },
        h("header", {}, h("div", { class: "anchor" }, this.libraryButton, this.libraries.el),
          h("div", { class: "anchor" }, sessionsButton, this.sessions.el),
          h("div", { class: "anchor" }, this.checkpointButton, this.checkpoints.el),
          this.title, this.crumb,
          h("nav", { role: "tablist", "aria-label": "Views" }, Object.values(this.nav)), settingsButton, h("button",{class:"ghost",onclick:()=>this.settings.open("models")},"Models"), this.live,
          this.geoButton, this.paneButton,
          h("div", { class: "anchor" }, this.closeButton, this.closeMenu.el)),
        this.body),
      this.settings.dialog, this.runDialog);
    this.composer = composer;

    document.addEventListener("keydown", this.onDocumentKey);
    document.addEventListener("click", this.onDocumentClick);
    this.show("chat");
    // MF-008: the saved split is a preference; what is applied is clamped to
    // the room this root has now (pane >= 300px, chat >= 360px), and follows
    // the root as it resizes. The preference itself is kept for wider roots.
    this.savedPaneWidth = parseInt(recall("pane-w"), 10) || 0;
    this.applyPaneWidth();
    if (typeof ResizeObserver !== "undefined") {
      this.bodyObserver = new ResizeObserver(() => this.applyPaneWidth());
      this.bodyObserver.observe(this.body);
    }
    // Open by default where there is room for both; the choice is remembered.
    const saved = recall("pane");
    this.showPane(saved === "open");
    void this.openGuideOnFirstVisit(saved);
  }

  /** A new library carries "About the Librarian and how to use it" at its root. The first time
   *  this browser opens the library (and the pane has not been opened or closed on purpose), the
   *  pane opens on it, so the way in is on screen. Its links lead to the formal notes beside it.
   *  An older library has no such note: nothing opens. Obsidian shows notes itself, so it is left alone. */
  private async openGuideOnFirstVisit(savedPane: string): Promise<void> {
    if (this.opts.openNote || savedPane || recall("guide-seen")) return;
    try { await this.api.get(`/api/file?path=${encodeURIComponent(GUIDE_NOTE + ".md")}`); }
    catch { return; }
    remember("guide-seen", "1");
    this.showPane(true);
    await this.pane.open(GUIDE_NOTE);
  }

  private composer: HTMLElement;
  private opts: Options;
  private paneOpen = true;
  private stopEvents: (() => void) | null = null;
  private readonly onDocumentKey = (e: KeyboardEvent) => {
    // MF-008: Escape closes this mount's open popovers and is consumed. With
    // none open it passes by, so the host and other views keep their keys.
    if (this.opts.host === "website" && e.altKey && e.shiftKey && !e.ctrlKey && !e.metaKey && !e.repeat &&
        !e.isComposing && !e.defaultPrevented && !this.settings.dialog.open && e.target instanceof Element &&
        (this.root.contains(e.target) || (e.target === document.body && document.querySelectorAll(".librarian-root").length === 1)) &&
        !e.target.closest("input, textarea, select, [contenteditable], [role=textbox], dialog, [role=dialog]")) {
      const key = e.code.replace(/^(Key|Digit)/, "");
      const id = key && Object.keys(COMMANDS).find(id => preference("key." + id) === key);
      if (id) { e.preventDefault(); this.command(id); return; }
    }
    if (e.key !== "Escape") return;
    const open = this.popovers().filter((p) => p.open);
    if (!open.length) return;
    open.forEach((p) => { if (p !== this.models || !this.tile.cancelSlot()) p.show(false); });
    e.preventDefault();
    e.stopPropagation();
  };
  private popovers(): Popover[] {
    return [this.modes, this.models, this.sessions, this.libraries, this.checkpoints, this.attachPop, this.closeMenu];
  }
  private readonly onDocumentClick = (e: MouseEvent) => {
    // The dispatch path, not `contains`: a click that re-renders the popover
    // detaches its own target, which is still inside.
    const path = e.composedPath();
    for (const p of this.popovers()) {
      if (p.open && !path.includes(p.el) && !path.includes(p.button)) {
        if (p !== this.models || !this.tile.cancelSlot()) p.show(false);
      }
    }
  };

  // -- the document pane -------------------------------------------------------
  /** A [[link]]: in Obsidian the real note opens; elsewhere it opens beside the chat. */
  /** The skill registry: built by the Core on request, shown in the pane like a note. */
  private async openSkillRegistry(): Promise<void> {
    try {
      const page = await this.api.get("/api/skills");
      this.showPane(true);
      this.pane.showPage(String(page.title ?? "Skill registry"), String(page.markdown ?? ""));
    } catch (e) { this.warn(`The skill registry did not open: ${(e as Error).message}`); }
  }

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
    if (!on) this.pane.cancelPick();                  // closing the pane ends a file pick
    this.paneOpen = on;
    this.body.classList.toggle(cls("pane-open"), on);
    this.body.classList.toggle(cls("pane-closed"), !on);
    this.paneButton.setAttribute("aria-pressed", String(on));
    remember("pane", on ? "open" : "closed");
  }

  /** Apply the saved split clamped to the current room; returns the width
   *  applied (0 when none is saved and the stylesheet's default applies). */
  private applyPaneWidth(): number {
    const separator = this.body.querySelector<HTMLElement>(".lib-resizer");
    separator?.setAttribute("aria-valuemin","300");
    separator?.setAttribute("aria-valuemax",String(Math.max(300,this.body.clientWidth-(separator.offsetWidth||5)-360)));
    if (!this.savedPaneWidth) { separator?.setAttribute("aria-valuenow", String(Math.round(this.pane.el.getBoundingClientRect().width))); return 0; }
    const handle = this.body.querySelector<HTMLElement>(".lib-resizer")?.offsetWidth ?? 0;
    const room = this.body.clientWidth - handle;
    const width = room > 0 ? Math.max(300, Math.min(this.savedPaneWidth, room - 360)) : this.savedPaneWidth;
    this.body.style.setProperty("--pane-w", `${Math.round(width)}px`);
    separator?.setAttribute("aria-valuenow",String(Math.round(width)));
    return Math.round(width);
  }

  private resize(start: PointerEvent, handle: HTMLElement): void {
    start.preventDefault();
    handle.setPointerCapture(start.pointerId);
    const rect = this.body.getBoundingClientRect();
    const move = (e: PointerEvent) => {
      this.savedPaneWidth = Math.round(rect.right - e.clientX);
      this.applyPaneWidth();
    };
    const up = () => {
      handle.removeEventListener("pointermove", move as EventListener);
      this.savedPaneWidth = this.applyPaneWidth();     // a drag saves what it shows
      remember("pane-w", `${this.savedPaneWidth}px`);
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
    this.stopEvents = this.api.events(this.state.event_stream, (event) => this.onEvent(event), (live) => {
      this.live.className = cls(`live ${live ? "on" : "off"}`);
      this.live.setAttribute("aria-label", live ? "Event stream connected" : "Event stream reconnecting");
      this.live.title = live ? "Event stream connected" : "Event stream reconnecting";
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
    if (this.settings.dialog.open) this.settings.syncState();
    this.paintSendButton();
    this.libraryButton.textContent = `${this.libraryName()} ▾`;
    this.libraryButton.title = `Switch library - this is ${this.libraryName()} (${String(this.state.vault_path ?? "")})`;
    document.title = `${this.libraryName()} - Librarian`;
    this.setSession(this.state.session ?? null);
    this.paintToolbar();
    this.paintChips();
    if (this.state.busy) this.chat.setWorking(true);
    for (const request of this.state.pending ?? []) this.chat.handle({ seq: 0, type: "permission_request", ...request });
    this.waiting = new Set(((this.state.pending ?? []) as any[]).map((r) => String(r.id)));
    this.paintWaiting();
  }

  /** The Chat tab says when a request waits for a person, so a call blocked in Chat is seen
   *  from Staging or Search (AR-F03). */
  private paintWaiting(): void {
    const n = this.waiting.size, tab = this.nav.chat;
    clear(tab, "Chat", n ? h("span", { class: "badge waiting", "aria-hidden": "true" }, String(n)) : null);
    tab.setAttribute("aria-label", n ? `Chat, ${n} permission request${n === 1 ? "" : "s"} waiting` : "Chat");
    tab.title = n ? `${n} permission request${n === 1 ? " is" : "s are"} waiting for you in Chat` : "";
  }

  private onEvent(event: Event): void {
    if (event.type === "resync_required") {
      // The stream is intentionally not an action log. A Core restart or a
      // dropped retained window means the only safe recovery is to fetch the
      // current canonical state; never replay a tool or chat action here.
      void this.refresh().catch((error) => this.warn((error as Error).message));
      return;
    }
    this.chat.handle(event);
    switch (event.type) {
      case "permission_request":
        this.waiting.add(String(event.id));
        this.paintWaiting();
        break;
      case "permission_decided":
        this.waiting.delete(String(event.id));
        this.paintWaiting();
        break;
      case "mode_changed":
        this.state.mode = event.to;
        this.paintToolbar();
        break;
      case "tiers_changed":
        this.state.tiers = event.tiers;
        if (this.settings.dialog.open) this.settings.syncState();
        this.tiersEpoch++;
        this.paintToolbar();
        if (this.models.open) this.tile.render();
        break;
      case "turn_done": case "error":
        this.state.busy = false;
        this.stopping = false;
        this.paintSendButton();
        break;
      case "action_started": case "action_progress": case "action_done": {
        const actions = (this.state.actions ?? []) as any[];
        const at = actions.findIndex((a) => a.id === event.id);
        // Keep what the Core reports about the run (outputs, error, a paused route's question
        // and options), not only its name and status: WF-D1, a finished run's result was lost.
        const { type: _type, result: _result, at: _at, ...row } = event as any;
        if (at >= 0) actions[at] = row; else actions.push(row);
        this.state.actions = actions;
        this.paintChips();
        if (event.type === "action_done" && this.view === "staging") void this.staging.load();
        break;
      }
      case "action_dismissed":
        this.state.actions = ((this.state.actions ?? []) as any[]).filter((a) => a.id !== (event as any).id);
        this.paintChips();
        break;
      case "person_acted":
        if (event.session) this.setSession(event.session);
        if (this.view === "staging") void this.staging.load();
        break;
      case "checkpoint_created": case "checkpoint_resolved":
        void this.refreshCheckpoints();
        break;
      case "route_health_changed": case "workflow_preflight":
        // Route evidence is deliberately refreshed only when the picker is
        // visible.  This keeps normal chat turns free of incidental route
        // requests while ensuring an open Model Tile never presents stale
        // safety state.
        if (this.models.open) void this.tile.refresh();
        if (event.type === "route_health_changed") {
          const lead = ((this.state.tiers ?? []) as any[])[0];
          const ev = event as any;
          if (lead && [lead.host_id, lead.provider, `preset-${lead.provider}`].includes(ev.host_id)) {
            this.state.lead_route_health = { host_id: ev.host_id, ...(ev.health ?? {}) };
            this.paintToolbar();
          }
        }
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
    this.effortControl.title = `Effort up to ${e.level} of 10 - the most work you allow. The librarian `
      + `chooses less for a small request (one link, one file, a quick answer). At ${e.level}: `
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
    // AR-F02: a Lead whose model the provider does not know says so here, before the next turn.
    const health = (this.state.lead_route_health ?? {}) as any;
    const broken = !!tier && health.status === "error" && (!health.model || health.model === tier.model);
    clear(this.modelButton, tier
      ? [h("span", { class: "badge" }, "1"), broken ? h("span", { class: "route-warning", "aria-label": "route problem" }, " ⚠") : null,
         ` ${tier.model} · ${PROVIDERS[tier.provider] ?? tier.provider}`]
      : "Choose models", " ▾");
    this.modelButton.title = broken ? `This model's route failed: ${health.detail ?? ""}` : "";
    renderModes(this.modes, this.api, this.state.mode, (msg) => this.warn(msg), this.ids.id("librarian-mode"));
    const pending = ((this.state.pending_checkpoints ?? []) as any[]).length;
    this.checkpointButton.textContent = pending ? `Checkpoints (${pending}) ▾` : "Checkpoints ▾";
    if (this.checkpoints.open) this.renderCheckpoints();
  }

  /** Policy choices live here, not in a prose prompt.  A blocked operation
   * leaves its evidence and available, explicit choices in this small panel;
   * resolving one does not silently unblock unrelated work. */
  private async refreshCheckpoints(): Promise<void> {
    try {
      const out = await this.api.get("/api/checkpoints?pending=1");
      this.state.pending_checkpoints = out.checkpoints ?? [];
      this.renderCheckpoints();
      this.paintToolbar();
    } catch (e) { this.warn((e as Error).message); }
  }

  private renderCheckpoints(): void {
    const rows = (this.state.pending_checkpoints ?? []) as any[];
    const card = (row: any) => {
      // The raw record is for checking, not reading first: folded under "Details".
      const evidence = row.evidence && Object.keys(row.evidence).length
        ? h("details", { class: "checkpoint-details" }, h("summary", {}, "Details"),
            h("pre", { class: "checkpoint-evidence" }, JSON.stringify(row.evidence, null, 2))) : null;
      const writeConflictHelp = row.type === "write_conflict"
        ? h("p", { class: "checkpoint-help" },
            "Review the named note in its editor. Resolving this card records your decision only; it does not retry the blocked write. Repeat the original action after the editor is quiet.")
        : null;
      // MF-006: one resolution per press. The card's choices stay disabled
      // while the Core records it, and come back only if it was refused.
      const buttons: HTMLButtonElement[] = [];
      const resolve = async (choice: string) => {
        if (buttons.some((b) => b.disabled)) return;
        buttons.forEach((b) => { b.disabled = true; });
        try {
          await this.api.post("/api/checkpoints/resolve", { id: row.id, choice });
        } catch (e) {
          buttons.forEach((b) => { b.disabled = false; });
          this.warn(`Decision not recorded: ${(e as Error).message}`);
          return;
        }
        if (choice === "retry_after_review") this.warn(
          "Review recorded. The blocked write was not retried; repeat the original action after the editor is quiet.");
        await this.refreshCheckpoints();
      };
      return h("section", { class: "checkpoint" },
        h("strong", {}, String(row.type ?? "Decision").replace(/_/g, " ")),
        // Every card names itself, so an agent and a person can be talking about the same one.
        h("small", { class: "dim" }, ` · ${String(row.id ?? "")}`),
        h("p", {}, String(row.scope ?? "")),
        evidence, writeConflictHelp,
        h("div", { class: "row2" }, ...(Array.isArray(row.choices) ? row.choices : []).map((choice: string) =>
          // The Core declares the safe default.  Array order is presentation
          // history, not an instruction to make an approval action primary.
          buttons[buttons.push(h("button", { class: choice === row.default ? "primary" : "ghost",
            onclick: () => void resolve(choice) },
            choice === "retry_after_review" ? "Mark reviewed; retry manually" : choice.replace(/_/g, " ")) as HTMLButtonElement) - 1])));
    };
    clear(this.checkpoints.el,
      h("h4", {}, "Decisions waiting for you"),
      rows.length ? rows.map(card) : h("p", { class: "dim" }, "No decisions are waiting. Agents can continue work on other notes."));
  }

  private paintChips(): void {
    const actions = ((this.state.actions ?? []) as any[]).filter((a) =>
      ["running", "paused", "finished", "failed"].includes(a.status));
    // MF-006: a requested cancel stays visibly pending until the Core reports
    // the run stopped (its chip goes) or refuses the request.
    for (const id of [...this.cancelling]) {
      if (!actions.some((a) => a.id === id && a.status === "running")) this.cancelling.delete(id);
    }
    const post = async (a: any, verb: string, body?: unknown) => {
      try { await this.api.post(`/api/actions/${a.id}/${verb}`, body); } catch (e) {
        this.warn(`${a.name}: ${(e as Error).message}`);
      }
    };
    const dismiss = (a: any) => h("button", { "aria-label": `Dismiss ${a.name}`, title: "Dismiss",
      onclick: () => void post(a, "dismiss") }, "✕");
    // A finished run says what it left behind and a failed one why (WF-D1); a paused routing
    // step offers its options and a resume (WF-D4). The full result stays in the run log.
    clear(this.chips, actions.map((a) => {
      if (a.status === "running") return h("span", { class: "chip" }, `${a.name} · ${a.steps} steps`,
        this.cancelling.has(a.id)
          ? h("button", { "aria-label": `Cancelling ${a.name}`, "aria-busy": "true", disabled: true }, "Cancelling…")
          : h("button", { "aria-label": `Cancel ${a.name}`, onclick: async () => {
              this.cancelling.add(a.id);
              this.paintChips();
              try { await this.api.post(`/api/actions/${a.id}/cancel`); } catch (e) {
                this.cancelling.delete(a.id);
                this.paintChips();
                this.warn(`${a.name} was not cancelled: ${(e as Error).message}`);
              }
            } }, "✕"));
      if (a.status === "paused") {
        const options: string[] = Array.isArray(a.options) ? a.options : [];
        return h("span", { class: "chip action-paused", role: "group", "aria-label": `${a.name} is paused` },
          `${a.name} · paused${a.reason ? `: ${a.reason}` : ""}`,
          a.question && options.length ? h("span", { class: "dim" }, ` ${a.question}`) : null,
          ...options.map((option) => h("button", { class: "action-choice",
            title: `Continue with "${option}" for this step`,
            onclick: () => void post(a, "resume", { choices: { [a.paused_step]: option } }) }, option)),
          h("button", { class: "action-choice", title: "Continue: a routing model set since then decides",
            onclick: () => void post(a, "resume") }, "Resume"),
          dismiss(a));
      }
      const summary = a.status === "failed" ? `failed${a.error ? `: ${a.error}` : ""}` : `finished${actionOutputs(a.outputs)}`;
      const errors: string[] = Array.isArray(a.outputs?.errors) ? a.outputs.errors : [];
      const details = a.run ? h("button", { class: "action-choice", "aria-label": `Details of ${a.name}`,
        title: "Open this run's full record: each step, what it returned and why it stopped",
        onclick: () => void this.openRun(a) }, "Details") : null;
      return h("span", { class: `chip action-${a.status}`, role: "status",
          title: [summary, ...errors.map((e) => `• ${e}`)].join("\n") },
        `${a.name} · ${summary}`, details, dismiss(a));
    }));
  }

  /** The run's record as the Core keeps it (run_status), bounded for the page. */
  private async openRun(a: any): Promise<void> {
    let record: unknown;
    try { record = await this.api.tool("run_status", { run_id: a.run }); } catch (e) {
      this.warn(`${a.name}: the run record could not be read: ${(e as Error).message}`);
      return;
    }
    const text = JSON.stringify(record, null, 2);
    clear(this.runDialog,
      h("h3", {}, `${a.name} · ${a.status}`),
      h("pre", { class: "run-record-body" }, text.length > 20000 ? `${text.slice(0, 20000)}\n…` : text),
      h("button", { type: "button", onclick: () => this.runDialog.close() }, "Close"));
    if (!this.runDialog.open) this.runDialog.showModal();
  }

  private setSession(session: Session): void {
    // A tool result's envelope is partial; a full view has `phases`.
    if (session && this.session && session.session === this.session.session)
      session = { ...this.session, ...session };
    this.session = session;
    this.chat.renderPlan(session);
    if (!session) {
      this.title.textContent = "";
      this.crumb.textContent = "no thread";
      return;
    }
    this.title.textContent = session.project || session.question || "";
    this.crumb.textContent = `${session.purpose ?? ""} · phase: ${session.phase ?? ""}${session.status && session.status !== "open" ? ` · ${session.status}` : ""}`;
  }

  /** The open library by its own name: two libraries made by new-vault.ps1 share the
   *  folder name `.librarian-app`, so the folder cannot say which one this is. */
  private libraryName(): string {
    return String(this.state.vault_name ?? this.state.vault ?? "Librarian");
  }

  command(id: string): void {
    if (!(id in COMMANDS)) return;
    if (id === "settings") { this.settings.open(); return; }
    this.settings.dialog.close();
    if (id === "search") { this.show("search"); return; }
    if (id === "sessions" || id === "checkpoints") {
      const pop = id === "sessions" ? this.sessions : this.checkpoints;
      if (!pop.open) pop.button.click();
      return;
    }
    if (["staging","approved","resume","retry","stop"].includes(id)) {
      this.show("staging");
      if (id === "staging") this.staging.el.querySelector("button")?.focus();
      else void this.staging.focusBatch(id);
      return;
    }
    this.show("chat");
    if (id === "intake") {
      this.attachPop.button.click();
      this.warn("Attach a source file for this library, then ask the librarian to capture it for review in Staging.");
      return;
    }
    // Workflows live in the paperclip menu: open it and focus the one asked for.
    if (!this.attachPop.open) { this.toggle(this.attachPop); this.attachPanel.render(); }
    const button = this.attachPop.el.querySelector<HTMLButtonElement>(`[data-command="${id}"]`);
    if (button) { button.focus(); button.scrollIntoView({block:"nearest"}); }
    else this.warn("This workflow is unavailable in " + this.libraryName() + ".");
  }

  private show(view: View, refresh = true): void {
    this.view = view;
    for (const [v, el] of Object.entries(this.views)) el.hidden = v !== view;
    for (const [v, b] of Object.entries(this.nav)) { b.setAttribute("aria-selected", String(v === view)); b.tabIndex = v === view ? 0 : -1; }
    this.composer.hidden = view !== "chat";
    if (view === "staging" && refresh) void this.staging.load(true);
    if (view === "search") this.search.focus();
  }

  /** R17: Settings' "Choose…" for a service slot opens the model tile to pick one model
   *  for it; picking (or Cancel) returns to Settings. */
  private async chooseService(slot: string, label: string,
                              current?: { provider: string; model: string }, role?: number): Promise<void> {
    // After the click that asked for it has finished: that click is still on its way up
    // to the document, whose click-outside handler would close a popover opened now.
    await new Promise((resolve) => window.setTimeout(resolve, 0));
    const origin = this.view;
    this.show("chat");
    this.tile.startSlot(slot, label, () => {
      if (this.models.open) this.toggle(this.models);
      this.show(origin, false);
      this.settings.open("models");
    }, current?.model ? current : undefined, role);
    if (!this.models.open) this.toggle(this.models);
    await this.refresh();
    await this.tile.refresh();
  }

  private toggle(pop: Popover): void {
    const open = !pop.open;
    [this.modes, this.models, this.sessions, this.libraries, this.checkpoints, this.attachPop, this.closeMenu]
      .forEach((p) => p.show(false));
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
    this.msgBox.classList.toggle(cls("has-attachments"), has);
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

  /** The Close menu: this library's Geo-Grapher, then the library itself. */
  private async renderClose(): Promise<void> {
    const pop = this.closeMenu;
    const status = h("p", { class: "dim", role: "status" }, "");
    let geo: any = {};
    try { geo = await this.api.get("/api/geographer"); } catch { geo = { state: "unknown" }; }
    const running = geo.state === "running" || geo.state === "starting";
    const geoButton = h("button", {
      class: "ghost", disabled: geo.state === "disabled" || geo.state === "unknown",
      onclick: async () => {
        status.textContent = running ? "Closing Geo-Grapher…" : "Starting Geo-Grapher…";
        try {
          await this.api.post(running ? "/api/geographer/stop" : "/api/geographer/start");
          status.textContent = running ? "Geo-Grapher is closed. The library keeps running." : "Geo-Grapher is starting.";
          window.setTimeout(() => { if (pop.open) void this.renderClose(); }, 1200);
        } catch (e) { status.textContent = `Not done: ${(e as Error).message}`; }
      } }, running ? "Close Geo-Grapher" : "Start Geo-Grapher");
    const libraryButton = h("button", { class: "ghost danger", onclick: () => void this.closeLibrary(false, status, body) },
      "Close this library");
    const body = h("div", { class: "close-body" });
    clear(pop.el,
      h("h4", {}, "Geo-Grapher"),
      h("p", { class: "dim" }, geo.state === "disabled" ? "Not enabled for this library."
        : running ? "Running for this library." : geo.state === "failed" ? `Stopped with an error${geo.error ? `: ${geo.error}` : "."}`
        : "Closed."),
      geoButton,
      h("h4", {}, "This library"),
      h("p", { class: "dim" }, "Stops its Core gracefully: no new work is admitted, current work finishes or is "
        + "listed for you first, then its Geo-Grapher and the vault lease are released."),
      libraryButton, body, status);
  }

  /** Ask this library's Core to stop. Active work is shown first; only an explicit
   * second choice forces the stop (the Core records it as a forced engagement close). */
  private async closeLibrary(force: boolean, status: HTMLElement, body: HTMLElement): Promise<void> {
    status.textContent = force ? "Stopping after the current step…" : "Asking the library to stop…";
    try {
      await this.api.post("/api/host/stop", { force });
      this.stopping = true;
      clear(this.root, h("div", { class: "lib-closed", role: "status" },
        h("h2", {}, `${this.libraryName()} is closed`),
        h("p", {}, "Its Core and Geo-Grapher have stopped and the vault is released. You can close this tab, "
          + "or start the library again from the Librarian Host.")));
    } catch (e) {
      const err = e as ApiError;
      if (err.status === 409) {
        const active = (err.body?.active ?? {}) as Record<string, unknown>;
        const rows = Object.entries(active).filter(([, v]) => v && (!Array.isArray(v) || v.length));
        status.textContent = "";
        clear(body,
          h("p", { class: "warn" }, "This library has work in progress:"),
          h("ul", {}, rows.length ? rows.map(([k, v]) => h("li", {}, `${k.replace(/_/g, " ")}: ${
            Array.isArray(v) ? v.length : typeof v === "object" ? Object.keys(v as object).length : String(v)}`))
            : h("li", {}, "a running action")),
          h("button", { class: "ghost danger", onclick: () => {
            if (window.confirm("Stop the library now? Work in progress is cancelled at its next safe point."))
              void this.closeLibrary(true, status, body);
          } }, "Stop anyway"),
          h("button", { class: "ghost", onclick: () => { clear(body); this.closeMenu.show(false); } }, "Keep it running"));
      } else if (err.status === 404) {
        status.textContent = "This Core was not started by the Librarian Host; stop it where it was started.";
      } else {
        status.textContent = `Not stopped: ${err.message}`;
      }
    }
  }

  private async openGeo(): Promise<void> {
    try {
      let geo = await this.api.get("/api/geographer");
      if (geo.state === "stopped" || geo.state === "failed") {
        // Closed earlier from the Close menu or from Geo-Grapher itself: start it again.
        geo = await this.api.post("/api/geographer/start");
        for (let i = 0; i < 40 && !geo.open_url && geo.state === "starting"; i++) {
          await new Promise(r => window.setTimeout(r, 500));
          geo = await this.api.get("/api/geographer");
        }
      }
      if (geo.open_url) { window.open(geo.open_url, "_blank", "noopener"); return; }
      this.warn(geo.state === "disabled"
        ? "Geo-Grapher is not enabled for this library."
        : geo.state === "starting" ? "Geo-Grapher is still starting for this library; try again in a moment."
        : `Geo-Grapher is not running for this library${geo.error ? `: ${geo.error}` : "."}`);
    } catch (error) {
      this.warn(`Could not reach this library's Geo-Grapher: ${String(error)}`);
    }
  }

  private warn(message: string): void {
    this.notice.hidden = false;
    clear(this.notice, message, h("button", { class: "ghost push", "aria-label": "Dismiss",
      onclick: () => { this.notice.hidden = true; } }, "✕"));
  }

  // -- actions ---------------------------------------------------------------
  /** Send the composer's text. The draft stays until the server accepts it:
   *  a refusal or a lost connection keeps text and attachments. Success
   *  clears only what was sent, so anything typed while it was pending
   *  survives (MF-005, G01). */
  private async send(): Promise<void> {
    if (this.state.busy || this.sending) return;
    const raw = this.input.value;
    const text = raw.trim();
    if (!text) return;
    const sent = [...this.attachments];
    if (!(await this.sendText(text))) return;
    if (this.input.value === raw) this.input.value = "";
    this.attachments = this.attachments.filter((a) => !sent.includes(a));
    this.renderAttachments();
  }

  /** The send path itself, shared by the composer and a message's Retry
   *  button - which resends the same text without touching the composer.
   *  One request at a time: a second press while one is pending sends
   *  nothing. True when the server accepted it. */
  private async sendText(text: string): Promise<boolean> {
    if (!text || this.sending) return false;
    this.sending = true;
    this.paintSendButton();
    try {
      await this.api.post("/api/chat", { text });
      this.state.busy = true;
      return true;
    } catch (e) {
      const message = (e as Error).message;
      this.warn(message.includes("tier 1") ? "Choose a chat model first: click Model, then a model (it becomes tier 1)." : message);
      return false;
    } finally {
      this.sending = false;
      this.paintSendButton();
    }
  }

  /** Stop the current reply. Only this button stops one; the reply is
   *  stopped when the Core says so (turn_done or error), not when the
   *  request is sent. */
  private async stop(): Promise<void> {
    if (!this.state.busy || this.stopping) return;
    this.stopping = true;
    this.paintSendButton();
    try { await this.api.post("/api/chat/cancel", {}); }
    catch (e) {
      this.stopping = false;
      this.paintSendButton();
      this.warn((e as Error).message);
    }
  }

  private paintSendButton(): void {
    const busy = !!this.state.busy;
    this.sendButton.disabled = this.sending || this.stopping;
    this.sendButton.setAttribute("aria-busy", String(this.sending || this.stopping));
    this.sendButton.textContent = this.stopping ? "Stopping…" : busy ? "Stop" : "Send";
    this.sendButton.setAttribute("aria-label", this.stopping ? "Stopping reply" : busy ? "Stop reply" : "Send message");
    this.sendButton.title = this.stopping ? "Stopping the current reply" : busy ? "Stop the current reply" : "Send message";
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

  dispose(): void {
    this.stopEvents?.();
    this.stopEvents = null;
    this.bodyObserver?.disconnect();
    this.bodyObserver = null;
    // MF-008: nothing this mount registered outlives it.
    this.settings.stopHealth();
    this.staging.dispose();
    this.pane.dispose();
    this.attachPanel.dispose();
    this.tile.dispose();
    this.popovers().forEach((p) => p.dispose());
    this.ids.release();
    document.removeEventListener("keydown", this.onDocumentKey);
    document.removeEventListener("click", this.onDocumentClick);
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

/** The note every new library starts with (starter/About the Librarian and how to use it.md). */
const GUIDE_NOTE = "About the Librarian and how to use it";

function recall(key: string): string {
  try { return localStorage.getItem(`librarian:${key}`) ?? ""; } catch { return ""; }
}

export interface Mounted { command(id: string): void; insert(text: string): void; dispose(): void }

export function mount(root: HTMLElement, opts: Options): Mounted {
  root.classList.add(cls("librarian-root"), cls(`host-${opts.host}`));
  const app = new App(root, opts);
  void app.start();
  return { command: id => app.command(id), insert: (text) => app.insert(text), dispose: () => app.dispose() };
}

// The website: the core serves the page with its token in a meta tag.
const auto = typeof document !== "undefined" ? document.getElementById("librarian-root") : null;
if (auto) {
  const token = $<HTMLMetaElement>(document, "meta[name=librarian-token]")?.content ?? "";
  mount(auto, { base: "", token, host: "website" });
}
