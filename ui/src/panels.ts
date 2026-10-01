// The toolbar's popovers: Modes (permission mode and queued actions), the Model
// tile (chat models by click order), and Sessions.

import type { Api, ApiError } from "./api";
import { clear, h, when } from "./dom";

export const MODES = [
  ["plan", "Plan", "Reads and searches. Writes are refused: the librarian proposes instead."],
  ["ask", "Ask permission", "Every write pauses for you, with Allow once, Allow for this session, or Deny."],
  ["auto", "Auto", "Writes within the phase gate and the vault's settings. Sensitive material still waits for you."],
] as const;

const ACTIONS: Record<string, [string, string]> = {
  "clear-enrichment-backlog": ["Clear enrichment backlog", "Fetch, describe and stage everything queued. Background, cancellable."],
  "deep-read-staged": ["Deep-read staged sources", "Read each staged source's whole text: claims and limits with pages, and lenses to review. Background, cancellable."],
  "review-conversation": ["Review this conversation for sources", "A bounded snapshot of recent turns → suggested sources. Writes nothing."],
  "weekly-review": ["Weekly review of a pursuit", "Its tasks, what was read and written, its desk → a drafted reflection for you to read. Writes nothing until you accept it."],
};

export const PROVIDERS: Record<string, string> = {
  deepinfra: "DeepInfra", openai: "OpenAI", anthropic: "Anthropic", local: "Local server",
};

const ROLES = ["leads the session", "writes notes", "small tasks"];

function profileMeta(m: any): string {
  if (m.profiling === "queued") return "profiling: awaiting your review in Staging";
  const p = m.profile;
  if (!p) return "unprofiled";
  const parts: string[] = [];
  if (p.suggested_tier) parts.push(String(p.suggested_tier).replace(/_/g, " "));
  const bestFor = (p.best_for ?? []) as string[];
  if (bestFor.length) parts.push(bestFor.map((t: string) => String(t).replace(/_/g, " ")).join(", "));
  if (p.context_length) parts.push(`${Math.round(p.context_length / 1000)}k ctx`);
  if (p.price_input_per_1m || p.price_output_per_1m) {
    parts.push(`$${p.price_input_per_1m ?? 0} / $${p.price_output_per_1m ?? 0} per 1M`);
  }
  parts.push(p.tool_calling ? "tool calling" : "no tool calling");
  return parts.filter(Boolean).join(" · ");
}

export class Popover {
  readonly el: HTMLElement;
  constructor(id: string, label: string, readonly button: HTMLElement) {
    this.el = h("div", { class: "popover", id, hidden: true, role: "dialog", "aria-label": label });
    button.setAttribute("aria-haspopup", "true");
    button.setAttribute("aria-expanded", "false");
  }
  get open(): boolean { return !this.el.hidden; }
  show(on: boolean): void {
    this.el.hidden = !on;
    this.button.setAttribute("aria-expanded", String(on));
    if (on) (this.el.querySelector("input, button") as HTMLElement | null)?.focus();
  }
}

// -- Modes ---------------------------------------------------------------------

export function renderModes(pop: Popover, api: Api, mode: string, queued: string[],
                            pipelines: string[], report: (msg: string) => void,
                            needs: Record<string, Record<string, { type: string }>> = {}): void {
  const group = h("div", { role: "radiogroup", "aria-label": "Permission mode" },
    MODES.map(([value, label, help]) => h("label", { class: "opt" },
      h("input", {
        type: "radio", name: "librarian-mode", value, checked: value === mode,
        onchange: async () => {
          try { await api.post("/api/mode", { mode: value }); } catch (e) { report((e as Error).message); }
        },
      }),
      h("span", {}, label, h("small", {}, help)))));
  const extra = pipelines.filter((p) => !queued.includes(p) && !p.startsWith("review-item"));
  const run = async (name: string, inputs: Record<string, string> = {}) => {
    pop.show(false);
    try { await api.post("/api/actions", { name, inputs }); } catch (e) { report((e as Error).message); }
  };
  // D1: an action with required inputs (weekly-review's pursuit) asks for
  // them here first; a `project` input is chosen from the library's pursuits.
  const start = (name: string) => async () => {
    const wanted = needs[name];
    if (!wanted || !Object.keys(wanted).length) { await run(name); return; }
    const fields: Record<string, HTMLInputElement | HTMLSelectElement> = {};
    const rows = await Promise.all(Object.keys(wanted).map(async (key) => {
      let el: HTMLInputElement | HTMLSelectElement;
      if (key === "project") {
        let names: string[] = [];
        try {
          const listing = await api.get("/api/files?dir=Projects");
          names = ((listing.entries ?? []) as any[]).filter((e) => e.kind !== "dir")
            .map((e) => String(e.name).replace(/\.md$/, ""));
        } catch { /* fall back to typing it */ }
        el = names.length
          ? h("select", { class: "f" }, names.map((n) => h("option", { value: n }, n))) as HTMLSelectElement
          : h("input", { type: "text", class: "f", placeholder: "the pursuit's name" }) as HTMLInputElement;
      } else {
        el = h("input", { type: "text", class: "f", placeholder: key }) as HTMLInputElement;
      }
      el.id = `queue-${name}-${key}`;
      fields[key] = el;
      return h("div", {}, h("label", { class: "f", for: el.id }, key === "project" ? "Pursuit" : key), el);
    }));
    clear(pop.el, h("h4", {}, (ACTIONS[name] ?? [name])[0]), rows,
      h("div", { class: "row2" },
        h("button", { class: "primary", onclick: () => {
          const inputs = Object.fromEntries(Object.entries(fields).map(([k, el]) => [k, el.value.trim()]));
          if (Object.values(inputs).some((v) => !v)) { report("Fill in every field first."); return; }
          void run(name, inputs);
        } }, "Start"),
        h("button", { class: "ghost", onclick: () => renderModes(pop, api, mode, queued, pipelines, report, needs) }, "Back")));
  };
  clear(pop.el,
    h("h4", {}, "Permission mode"), group,
    h("h4", { class: "gap" }, "Queue an action"),
    queued.map((name) => h("button", { class: "menuitem", onclick: start(name) },
      (ACTIONS[name] ?? [name])[0], h("small", {}, (ACTIONS[name] ?? ["", "A pipeline."])[1]))),
    extra.length ? h("h4", { class: "gap" }, "This vault's pipelines") : null,
    extra.map((name) => h("button", { class: "menuitem", onclick: start(name) }, name)));
}

// -- the Model tile --------------------------------------------------------------

export interface Tier { provider: string; model: string }

// Vision-capable by name, for models not yet profiled (a profile's modality wins).
const VISION = /(-vl\b|vl-|vision|ocr|gemma-[34]|qwen3\.[5-9]|llama-4|pixtral|llava|inkling|glimmer)/i;
// Embedding models by name (the catalogue profiles none yet).
const EMBED = /(bge|embed|e5-|gte-|nomic|minilm|mpnet|potion|jina|arctic)/i;
const SLOT_KIND: Record<string, { label: string; fits: (m: any) => boolean }> = {
  ocr: { label: "Vision models", fits: (m) => m.profile?.modality === "Image_To_Text" || VISION.test(String(m.id)) },
  embeddings: { label: "Embedding models", fits: (m) => m.profile?.modality === "Embeddings" || EMBED.test(String(m.id)) },
  tts: { label: "Speech models", fits: (m) => m.profile?.modality === "Text_To_Speech" || /tts|kokoro|chatterbox|orpheus|speech|higgs/i.test(String(m.id)) },
};

export class ModelTile {
  private listings = new Map<string, any>();
  private filter = "";
  private toast = "";
  private press: number | undefined;
  // R10: a lead the completion suite (M0) has not qualified waits here for the person's
  // recorded "use it anyway", instead of being taken silently.
  private pendingLead: { tiers: Tier[]; lead: string } | null = null;
  // R17: the same tile, choosing one service model (slot 4 OCR, ...) instead of the tiers.
  private slot: { name: string; label: string; done: () => void; current?: Tier } | null = null;
  private showAll = false;

  startSlot(name: string, label: string, done: () => void, current?: Tier): void {
    this.slot = { name, label, done, current };
    this.showAll = false;
    this.filter = "";
    this.toast = "";
  }

  endSlot(): void { this.slot = null; }

  /** Right-click on the slot's own model: the slot is emptied (never filled by a chat
   *  model - R17). */
  private async clearSlot(): Promise<void> {
    const slot = this.slot!;
    try {
      await this.api.post("/api/services", { slot: slot.name, provider: "", model: "" });
      this.slot = null;
      slot.done();
    } catch (e) {
      this.toast = (e as Error).message;
      this.render();
    }
  }

  private async pickSlot(provider: string, model: string): Promise<void> {
    const slot = this.slot!;
    try {
      await this.api.post("/api/services", { slot: slot.name, provider, model });
      this.slot = null;
      slot.done();
    } catch (e) {
      this.toast = (e as Error).message;
      this.render();
    }
  }

  constructor(private pop: Popover, private api: Api, private tiers: () => Tier[],
              private keysSaved: () => Record<string, boolean>,
              private setTiers: (tiers: Tier[]) => void = () => {}) {}

  async refresh(): Promise<void> {
    const saved = this.keysSaved();
    await Promise.all(Object.keys(PROVIDERS).map(async (p) => {
      if (p !== "local" && !saved[p]) {
        this.listings.set(p, { status: "no key", models: [] });
        return;
      }
      try { this.listings.set(p, await this.api.get(`/api/models?provider=${p}`)); }
      catch (e) { this.listings.set(p, { status: "error", error: (e as Error).message, models: [] }); }
    }));
    this.render();
  }

  private async save(tiers: Tier[], override = ""): Promise<void> {
    try {
      await this.api.post("/api/tiers", { tiers, ...(override ? { override } : {}) });
      this.pendingLead = null;
      // Update local state immediately rather than waiting on the
      // `tiers_changed` broadcast to echo back: that event exists to sync
      // *other* tabs, and this tab's own render must not depend on a round
      // trip through the event stream landing before the caller's own
      // `render()` runs, or a picked model can briefly (or, under load,
      // not-so-briefly) look unpicked to this same click's own next step.
      this.setTiers(tiers);
    } catch (e) {
      const body = ((e as ApiError).body ?? {}) as Record<string, unknown>;
      if (body.needs_override) this.pendingLead = { tiers, lead: String(body.lead ?? "") };
      this.toast = (e as Error).message;
    }
  }

  private overridePrompt(): HTMLElement | null {
    const pending = this.pendingLead;
    if (!pending) return null;
    const reason = h("input", { type: "text", "aria-label": "Why use it anyway",
      value: "chosen before the completion suite had run" }) as HTMLInputElement;
    return h("div", { class: "warn", role: "alert" },
      h("p", {}, this.toast),
      h("div", { class: "row2 tight" }, reason,
        h("button", { class: "primary", onclick: async () => {
          this.toast = "";
          await this.save(pending.tiers, reason.value.trim() || "chosen by the person");
          this.render();
        } }, "Use it as lead anyway"),
        h("button", { class: "ghost", onclick: () => {
          this.pendingLead = null;
          this.toast = "";
          this.render();
        } }, "Choose another")));
  }

  private async clearAll(): Promise<void> {
    this.toast = "Selection cleared. Click models in order again.";
    await this.save([]);
    this.render();
  }

  private async pick(provider: string, model: string): Promise<void> {
    if (this.slot) return this.pickSlot(provider, model);
    const tiers = this.tiers();
    const at = tiers.findIndex((t) => t.provider === provider && t.model === model);
    const entry = ((this.listings.get(provider)?.models ?? []) as any[]).find((m) => m.id === model);
    if (at >= 0) {
      this.toast = `${model} is tier ${at + 1}. Right-click it, press Delete, or use Clear selection to start again.`;
    } else if (tiers.length >= 3) {
      this.toast = "All three tiers are chosen. Clear the selection to start again.";
    } else if (tiers.length === 0 && entry?.profile && entry.profile.tool_calling === false) {
      // Only a profiled "no" blocks leading; an unprofiled model is given the benefit of the doubt.
      this.toast = `${model} can't lead a session: it is profiled as not supporting tool calling. It can still be chosen as tier 2 or 3.`;
    } else {
      const next = [...tiers, { provider, model }];
      this.toast = next.length === 1
        ? "Only tier 1 is chosen, so it also writes notes and runs small tasks. A small tier 3 is usually more reliable on closed questions."
        : "";
      await this.save(next);
    }
    this.render();
  }

  private async profile(provider: string, model: string): Promise<void> {
    this.toast = `Profiling ${model}…`;
    this.render();
    try {
      const out = await this.api.tool("ingest", { ref: `model:${provider}:${model}` });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      this.toast = out.status === "already_held"
        ? `${model} is already catalogued.`
        : `${model} is staged for review — accept it under Staging to finish profiling it.`;
    } catch (e) {
      this.toast = `Could not profile ${model}: ${(e as Error).message}`;
    }
    await this.refresh();
  }

  render(): void {
    const tiers = this.tiers();
    const slots = [0, 1, 2].map((i) => {
      const t = tiers[i];
      const fallback = !t && i > 0 && tiers.length ? `uses tier ${Math.min(i, tiers.length)}` : "not chosen";
      return h("span", { class: "slot", title: t ? "Right-click to clear the chosen models" : "",
        oncontextmenu: (e: Event) => { if (tiers.length) { e.preventDefault(); void this.clearAll(); } } },
        h("span", { class: "badge" }, String(i + 1)),
        t ? `${t.model} · ${PROVIDERS[t.provider] ?? t.provider}` : h("span", { class: "dim" }, fallback),
        h("span", { class: "dim" }, ` · ${ROLES[i]}`));
    });
    const filter = h("input", {
      type: "search", placeholder: "Filter models", "aria-label": "Filter models", value: this.filter,
      oninput: (e: Event) => { this.filter = (e.target as HTMLInputElement).value; this.renderGrids(grids); },
    });
    const grids = h("div", {});
    if (this.slot) {
      const slot = this.slot;
      clear(this.pop.el,
        h("div", { class: "tierbar" }, h("strong", {}, `Choose the ${slot.label} model`),
          h("span", { class: "dim" }, this.showAll ? "Every model is listed. Click one."
            : `${SLOT_KIND[slot.name]?.label ?? "Matching models"} are listed (by profile, or by name). Click one.`),
          h("button", { class: "ghost", onclick: () => { this.showAll = !this.showAll; this.render(); } },
            this.showAll ? `${SLOT_KIND[slot.name]?.label ?? "Matching models"} only` : "Show all"),
          h("button", { class: "ghost", onclick: () => { this.slot = null; slot.done(); } }, "Cancel")),
        slot.current?.model ? h("p", { class: "dim" }, `Now: ${slot.current.model}. Right-click it to empty the slot.`) : null,
        this.toast ? h("div", { class: "toast", role: "status" }, this.toast) : null,
        filter, grids);
      this.renderGrids(grids);
      return;
    }
    clear(this.pop.el,
      h("div", { class: "tierbar" }, h("strong", {}, "Chat models"),
        h("span", { class: "dim" }, "Click in order: 1 leads, 2 writes notes, 3 does small tasks. Right-click a chosen model, or a tier, to clear all.")),
      h("div", { class: "tierbar" }, slots,
        tiers.length ? h("button", { class: "ghost", onclick: () => this.clearAll() }, "Clear selection") : null),
      this.pendingLead ? this.overridePrompt()
        : this.toast ? h("div", { class: "toast", role: "status" }, this.toast) : null,
      filter, grids,
      h("h4", {}, "OCR · Text to speech · Embeddings"),
      h("p", { class: "note locked" }, "These have their own slots (4 OCR, 5 Text to speech, 6 Embeddings) in Settings → Connections, each chosen with this same tile and kept with the library."),
      h("p", { class: "note" }, "Models come from each provider's live listing. A profiled model (a Source of kind model) shows its suggested tier and best-for tags (a first guess to confirm or correct), plus context, price and tool calling; an unprofiled one can be profiled, which stages it for your review like any other source."));
    this.renderGrids(grids);
  }

  private renderGrids(host: HTMLElement): void {
    const tiers = this.tiers();
    const needle = this.filter.toLowerCase();
    clear(host, Object.entries(PROVIDERS).map(([p, label]) => {
      const listing = this.listings.get(p) ?? { status: "…", models: [] };
      const models = (listing.models as any[]).filter((m) => !needle || String(m.id).toLowerCase().includes(needle))
        .filter((m) => !this.slot || this.showAll || (SLOT_KIND[this.slot.name]?.fits(m) ?? true));
      const status = listing.status === "ready" ? `${listing.models.length} model${listing.models.length === 1 ? "" : "s"}`
        : listing.status === "no key" ? "no key saved (+ → Connections)"
        : listing.status === "offline" ? "offline: the local server is not running"
        : listing.error ? `error: ${listing.error}` : listing.status;
      return h("section", { class: "provider" },
        h("h4", {}, h("span", { class: `dot ${listing.status === "ready" ? "" : listing.status === "no key" ? "nokey" : "off"}` }), `${label} · ${status}`),
        models.length ? h("div", { class: "grid" }, models.slice(0, 60).map((m) => {
          // In a service slot, "chosen" is the slot's own model; otherwise its tier.
          const inSlot = this.slot?.current?.provider === p && this.slot?.current?.model === m.id;
          const at = this.slot ? (inSlot ? 0 : -1)
            : tiers.findIndex((t) => t.provider === p && t.model === m.id);
          const clear = () => (this.slot ? this.clearSlot() : this.clearAll());
          const card = h("button", {
            class: `card${at >= 0 ? " sel" : ""}`, "aria-pressed": at >= 0 ? "true" : "false",
            title: at >= 0 ? (this.slot ? "Right-click (or Delete) to empty this slot"
              : "Right-click (or Delete) to clear the chosen models")
              : m.profile && m.profile.tool_calling === false
              ? "Profiled as not supporting tool calling: can still lead as tier 2 or 3" : "",
            onclick: () => this.pick(p, m.id),
            oncontextmenu: (e: Event) => { if (at >= 0) { e.preventDefault(); void clear(); } },
            onkeydown: (e: Event) => { if (at >= 0 && (e as KeyboardEvent).key === "Delete") void clear(); },
            ontouchstart: () => { if (at >= 0) this.press = window.setTimeout(() => void clear(), 600); },
            ontouchend: () => window.clearTimeout(this.press),
          },
          at >= 0 && !this.slot ? h("span", { class: "badge" }, String(at + 1)) : null,
          h("div", { class: "name" }, m.id), h("div", { class: "meta" }, profileMeta(m)));
          return h("div", { class: "card-wrap" }, card,
            // "local" has no public listing page to profile from (see MODEL_PAGES
            // server-side); offering the action there would only fail loudly.
            p !== "local" && !m.profile && m.profiling !== "queued"
              ? h("button", { class: "profile-link",
                  onclick: () => void this.profile(p, m.id) }, "Profile this model")
              : null);
        })) : null,
        models.length > 60 ? h("p", { class: "note" }, `${models.length - 60} more: type to filter.`) : null);
    }));
  }
}

// -- Sessions --------------------------------------------------------------------

// -- Libraries -----------------------------------------------------------------

/** Switch library in place, like switching vaults in Obsidian: the same app
 *  loads another library, and the one it leaves retires in the background.
 *  If the open library still has work running, ask before switching - that
 *  work then finishes where it started, and its threads stay resumable. */
export async function renderLibraries(pop: Popover, api: Api, current: string): Promise<void> {
  clear(pop.el, h("p", { class: "dim" }, "Loading libraries…"));
  const status = h("p", { class: "note", role: "status" });
  const go = async (path: string, force = false): Promise<void> => {
    clear(status, `Opening ${path}…`);
    try {
      await api.post("/api/library/switch", { path, force });
      window.location.reload();                       // the whole page belongs to the new library
    } catch (e) {
      const err = e as ApiError;
      const running = err.body?.running as Record<string, unknown> | undefined;
      if (err.status === 409 && running) {
        const parts = [running.turn ? "a reply in progress" : "",
          Array.isArray(running.actions) && running.actions.length ? `${running.actions.length} workflow(s) running` : "",
          running.waiting_on_person ? `${running.waiting_on_person} question(s) waiting for you` : ""].filter(Boolean);
        clear(status, `${current} still has ${parts.join(", ")}. `,
          h("button", { class: "ghost", onclick: () => void go(path, true) }, "Switch anyway - let it finish in the background"),
          h("small", {}, " Unanswered questions time out and park their thread, so it can be resumed later."));
      } else {
        clear(status, h("span", { class: "error" }, err.message));
      }
    }
  };
  try {
    const out = await api.get("/api/libraries");
    const rows = (out.libraries ?? []) as { path: string; name: string; last_opened: string; current: boolean; missing: boolean }[];
    const path = h("input", { type: "text", class: "f", placeholder: "A library's folder, e.g. D:\\Libraries\\History",
      "aria-label": "Library folder path" }) as HTMLInputElement;
    path.addEventListener("keydown", (e) => { if (e.key === "Enter" && path.value.trim()) void go(path.value.trim()); });
    clear(pop.el,
      h("h4", {}, "Libraries"),
      rows.length ? rows.map((l) => h("div", { class: "menuitem desk-row" },
        h("button", { class: "wl", disabled: l.current || l.missing, title: l.path,
          onclick: () => void go(l.path) },
          `${l.current ? "✓ " : ""}${l.name}`, h("small", {}, l.missing ? " · folder missing" : ` · opened ${when(l.last_opened)}`)),
        l.current ? null : h("button", { class: "icon-btn", title: "Remove from this list (the library itself is untouched)",
          "aria-label": `Forget ${l.name}`, onclick: async () => {
            await api.post("/api/libraries/forget", { path: l.path }).catch(() => undefined);
            void renderLibraries(pop, api, current);
          } }, "✕")))
        : h("p", { class: "dim" }, "Only this library so far."),
      h("h4", { class: "gap" }, "Open another library"),
      h("div", { class: "row2 tight" }, path,
        h("button", { class: "ghost", onclick: () => path.value.trim() && void go(path.value.trim()) }, "Open")),
      h("small", { class: "dim" }, "One library per domain; projects live inside it as pursuits."),
      status);
  } catch (e) {
    clear(pop.el, h("p", { class: "error" }, `Could not list libraries: ${(e as Error).message}`));
  }
}

/** The open library's threads. Each library keeps its own (`.librarian/sessions` in its
 *  folder), so the heading names the library: another library's threads are opened by
 *  switching to it. */
export async function renderSessions(pop: Popover, api: Api, attach: (id: string) => void,
                                     reset: () => void, library = "this library",
                                     libraryPath = ""): Promise<void> {
  clear(pop.el, h("p", { class: "dim" }, "Loading threads…"));
  try {
    const out = await api.tool("list_sessions");
    const rows = (out.sessions ?? []) as any[];
    clear(pop.el,
      h("button", { class: "menuitem", onclick: () => { pop.show(false); reset(); } },
        "New conversation", h("small", {}, "The librarian opens a thread when it needs one.")),
      h("h4", { class: "gap", title: libraryPath ? `Kept in ${libraryPath}` : "" }, `Threads in ${library}`),
      rows.length ? rows.map((s) => h("button", {
        class: "menuitem", onclick: () => { pop.show(false); attach(s.id); },
      }, `${s.project || s.question || s.purpose}`,
        h("small", {}, `${s.purpose} · ${s.status} · ${s.phase} · ${when(s.opened_at)}`)))
        : h("p", { class: "dim" }, "No threads in this library yet."),
      h("small", { class: "dim" }, "Another library's threads are under that library: switch to it from the library menu."));
  } catch (e) {
    clear(pop.el, h("p", { class: "error" }, `Could not list threads: ${(e as Error).message}`));
  }
}
