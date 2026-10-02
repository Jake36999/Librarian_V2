// + Settings: Connections, Working context, MCP servers, Library.
// A key goes to the core once and never comes back: only whether one is saved
// and its last four characters.

import type { Api } from "./api";
import { ApiError } from "./api";
import { clear, h } from "./dom";
import { PROVIDERS } from "./panels";

const PAGES = [["connections", "Connections"], ["context", "Working context"],
               ["mcp", "MCP servers"], ["library", "Library"], ["projects", "Projects"]] as const;

// Curated MCP servers, evaluated for fit with a research vault (Co-work
// Roadmap §3): stdio, no separate install step (uvx/npx -y fetch on first
// run), and no API key required to start. `env` values of the shape
// "${NAME}" are resolved from that environment variable at connect time,
// never stored here - the picker never needs a secret to enable one.
const CURATED_SKILLS = [
  { id: "semantic-scholar", name: "Semantic Scholar",
    description: "Search papers, citations and authors - fills the literature gap.",
    command: "uvx", args: ["s2-mcp-server==1.7.4"],   // pinned: see mcp_client.unpinned
    env: { SEMANTIC_SCHOLAR_API_KEY: "${SEMANTIC_SCHOLAR_API_KEY}" } },
  { id: "playwright", name: "Playwright browser",
    description: "Open and read web pages in a real, headless browser - for pages a plain fetch can't read.",
    command: "npx", args: ["-y", "@playwright/mcp@0.0.82", "--headless", "--isolated"], env: {} },
  { id: "apify", name: "Apify (web search and scrapers)",
    description: "Search the web and fetch pages (RAG web browser), plus ready-made scrapers. Needs APIFY_TOKEN.",
    command: "npx", args: ["-y", "@apify/actors-mcp-server@0.16.0"],
    env: { APIFY_TOKEN: "${APIFY_TOKEN}" } },
] as const;

export class Settings {
  readonly dialog = h("dialog", { class: "settings", "aria-label": "Settings" }) as HTMLDialogElement;
  private page: string = "connections";
  private body = h("section", { class: "page" });
  private tabs = h("div", { class: "tabs", role: "tablist" });

  constructor(private api: Api, private state: () => Record<string, any>,
              private refresh: () => Promise<void>, private manageKeys?: () => void,
              private chooseService?: (slot: string, label: string,
                                       current?: { provider: string; model: string }) => void) {
    this.dialog.append(
      h("div", { class: "dlg-head" }, h("strong", {}, "Settings"),
        h("button", { class: "ghost push", onclick: () => this.dialog.close() }, "Close")),
      this.tabs, this.body);
  }

  open(page = this.page): void {
    this.page = page;
    this.render();
    if (!this.dialog.open) this.dialog.showModal();
  }

  render(): void {
    clear(this.tabs, PAGES.map(([id, label]) => h("button", {
      role: "tab", "aria-selected": String(id === this.page),
      onclick: () => { this.page = id; this.render(); },
    }, label)));
    const page = { connections: () => this.connections(), context: () => this.context(),
                   mcp: () => this.mcp(), library: () => this.library(),
                   projects: () => this.projectsPage() }[this.page];
    clear(this.body, page ? page() : null);
  }

  // -- page 1 --------------------------------------------------------------
  private connections(): HTMLElement {
    const keys: any[] = this.state().keys ?? [];
    if (this.manageKeys) {
      // In Obsidian, keys live in Obsidian's secret storage and reach the core
      // in memory when the plugin starts it; this page only shows what it has.
      return h("div", {},
        h("p", {}, "Keys are kept in Obsidian's secret storage, never in the vault or the plugin's data."),
        keys.filter((k) => k.needed).map((k) => h("div", { class: "srv" },
          h("span", { class: `dot ${k.saved ? "" : "nokey"}` }),
          `${PROVIDERS[k.provider] ?? k.provider}: `, k.saved ? `•••• ${k.last4}` : "no key")),
        h("div", { class: "row2" }, h("button", { class: "primary", onclick: () => { this.dialog.close(); this.manageKeys?.(); } },
          "Choose keys in the plugin's settings")),
        h("p", { class: "note" }, "After changing a key, the plugin restarts the core so it takes effect."),
        this.serviceModels());
    }
    // Model providers, then the web search backends (keys.SEARCH_KEYS): web_search uses
    // Brave, else Tavily, else a SearXNG instance, else Wikipedia only.
    const LABELS: Record<string, string> = { ...PROVIDERS, tavily: "Tavily (web search)",
      brave: "Brave Search (web search)", github: "GitHub (repository intake)" };
    const select = h("select", { id: "lib-provider" },
      Object.entries(LABELS).map(([id, label]) => h("option", { value: id }, label))) as HTMLSelectElement;
    const input = h("input", { type: "password", id: "lib-key", autocomplete: "off", placeholder: "Paste a key" }) as HTMLInputElement;
    const status = h("span", { class: "note inline", role: "status" });
    const confirmBox = h("div");
    const save = h("button", { class: "primary" }, "Save key") as HTMLButtonElement;
    const remove = h("button", { class: "ghost" }, "Remove key") as HTMLButtonElement;
    const usageBox = h("div", { class: "usage" });
    const checkUsage = h("button", { class: "ghost", onclick: async () => {
      clear(usageBox, h("p", { class: "dim" }, "Checking…"));
      let out: any;
      try {
        out = await this.api.get(`/api/usage?provider=${select.value}`);
      } catch (e) {
        out = { ok: false, error: (e as Error).message };
      }
      const link = out.dashboard ? h("a", { href: out.dashboard, target: "_blank", rel: "noreferrer noopener" },
        out.ok && out.balance !== undefined ? "Full billing details ↗" : "View on the provider's site ↗") : null;
      if (out.ok && out.balance !== undefined) {
        clear(usageBox, h("p", {},
          `Balance: $${out.balance}${out.currency ? ` ${out.currency}` : ""}`,
          out.suspended ? h("strong", {}, " · account suspended") : null,
          out.billing_type ? h("span", { class: "dim" }, ` · ${out.billing_type}`) : null),
          h("p", { class: "note" }, "Unofficial: read from an undocumented endpoint, not DeepInfra's published API. ", link));
      } else {
        clear(usageBox, h("p", { class: "dim" }, out.error || "Usage isn't available here for this provider."), link);
      }
    } }, "Check usage") as HTMLButtonElement;
    const show = () => {
      const k = keys.find((x) => x.provider === select.value) ?? {};
      clear(confirmBox);
      clear(usageBox);
      if (!k.needed) {
        input.disabled = true; save.hidden = true; remove.hidden = true; checkUsage.hidden = true;
        status.textContent = "No key needed. The local server must be running.";
        return;
      }
      input.disabled = false; save.hidden = false;
      checkUsage.hidden = ["tavily", "brave", "github"].includes(select.value);
      remove.hidden = !k.saved;
      save.textContent = k.saved ? "Overwrite key" : "Save key";
      input.placeholder = k.saved ? `•••• ${k.last4} · ${k.source === "host" ? "from Obsidian" : "saved"}` : "Paste a key";
      status.textContent = "";
    };
    const submit = async (overwrite: boolean) => {
      status.textContent = "Saving and testing…";
      try {
        const out = await this.api.post("/api/keys", { provider: select.value, key: input.value, overwrite });
        input.value = "";
        status.textContent = out.check?.ok ? out.check.status : `Saved, but the provider said: ${out.check?.error ?? "no answer"}`;
        status.className = `note inline ${out.check?.ok ? "ok" : "err"}`;
        await this.refresh();
        keys.splice(0, keys.length, ...(this.state().keys ?? []));
        const msg = status.textContent;
        show();
        status.textContent = msg;
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && e.body.confirm) {
          clear(confirmBox, h("div", { class: "confirm" }, String(e.body.confirm),
            h("div", { class: "row2" },
              h("button", { class: "ghost", onclick: () => clear(confirmBox) }, "Cancel"),
              h("button", { class: "primary", onclick: () => submit(true) }, "Overwrite"))));
          status.textContent = "";
        } else {
          status.textContent = (e as Error).message;
          status.className = "note inline err";
        }
      }
    };
    save.onclick = () => submit(false);
    remove.onclick = () => clear(confirmBox, h("div", { class: "confirm" },
      `Remove the saved ${LABELS[select.value]} key? It can't be recovered from here.`,
      h("div", { class: "row2" },
        h("button", { class: "ghost", onclick: () => clear(confirmBox) }, "Cancel"),
        h("button", { class: "primary", onclick: async () => {
          await this.api.post("/api/keys/remove", { provider: select.value, confirm: true });
          await this.refresh();
          keys.splice(0, keys.length, ...(this.state().keys ?? []));
          show();
        } }, "Remove"))));
    select.onchange = show;
    input.onkeydown = (e) => { if (e.key === "Enter") submit(false); };
    const page = h("div", {},
      h("label", { class: "f", for: "lib-provider" }, "Provider"), select,
      h("label", { class: "f", for: "lib-key" }, "Connect API key"), input,
      h("div", { class: "row2" }, save, remove, status), confirmBox,
      h("p", { class: "note" }, `Keys are kept by the core (${this.state().key_backend ?? "securely"}), never in the vault. `,
        "They never come back to this page: only whether one is saved, and its last four characters."),
      h("label", { class: "f" }, "Usage & billing"),
      h("div", { class: "row2" }, checkUsage), usageBox,
      this.serviceModels());
    show();
    return page;
  }

  /** Research Pipeline §6.1: project access - off by default, folders a person chooses, each
   *  with its librarian-app/ sidecar. The core refuses project tools while it is off; this
   *  page is where a person turns it on, never the model. */
  private projectsPage(): HTMLElement {
    const host = h("div", {}, h("p", { class: "dim" }, "Loading…"));
    const status = h("span", { class: "note inline", role: "status" });
    const paint = (data: any) => {
      const toggle = h("input", { type: "checkbox", id: "lib-projects-on", checked: !!data.enabled,
        onchange: async (e: globalThis.Event) => {
          try { paint(await this.api.post("/api/projects/enable", { enabled: (e.target as HTMLInputElement).checked })); }
          catch (err) { status.textContent = (err as Error).message; }
        } }) as HTMLInputElement;
      const path = h("input", { type: "text", class: "f", id: "lib-project-path",
        placeholder: "Full path to the project folder, e.g. D:\\code\\my-app" }) as HTMLInputElement;
      const project = h("input", { type: "text", "aria-label": "Project note",
        placeholder: "Its Project note's name (optional)" }) as HTMLInputElement;
      const act = (url: string, body: Record<string, unknown>, done = "") => async () => {
        status.textContent = "";
        try {
          const out = await this.api.post(url, body);
          paint(out);
          if (done) status.textContent = done;
        } catch (err) { status.textContent = (err as Error).message; }
      };
      clear(host,
        h("label", { class: "opt" }, toggle, h("span", {}, h("strong", {}, "Enable project access"),
          h("small", {}, "Off by default. While off, no project folder is read and the librarian's project tools are unavailable - checked by the core, not only this page."))),
        h("label", { class: "f" }, "Project folders"),
        (data.roots ?? []).length ? (data.roots as any[]).map((r) => h("div", { class: "srv project-root" },
          h("span", { class: `dot ${r.exists ? "" : "off"}` }),
          h("span", {}, h("code", {}, r.path),
            h("span", { class: "dim" }, [r.project ? ` · ${r.project}` : " · no Project note linked",
              ` · librarian-app/ ${r.scaffold?.state ?? "?"}`,
              r.last_scan ? ` · scanned ${String(r.last_scan.at).slice(0, 10)} at ${String(r.last_scan.revision).slice(0, 10)} (${r.last_scan.components} components)` : " · not scanned",
              r.exists ? "" : " · moved or gone: add it again"].join(""))),
          data.enabled && r.exists ? h("button", { class: "ghost", onclick: act("/api/projects/scan", { id: r.id }, "Scanned.") }, "Scan") : null,
          h("label", { class: "inline project-writes", title: "Separate from reading: the librarian may then propose one change at a time (a snippet replaced or a new file), shown as a diff; you approve each one, and each is logged with a backup in librarian-app/logs/." },
            h("input", { type: "checkbox", checked: !!r.writes, "aria-label": `Allow edits in ${r.path}`,
              onchange: (e: globalThis.Event) => act("/api/projects/writes",
                { id: r.id, allowed: (e.target as HTMLInputElement).checked },
                (e.target as HTMLInputElement).checked ? "Edits allowed: each one is still asked." : "Edits withdrawn.")() }),
            " Allow edits"),
          h("button", { class: "ghost", onclick: act("/api/projects/remove", { id: r.id }) }, "Remove this project")))
          : h("p", { class: "dim" }, "No project folders yet."),
        h("label", { class: "f", for: "lib-project-path" }, "Add a project folder"), path,
        h("div", { class: "row2 tight" }, project,
          h("button", { class: "primary", onclick: () => act("/api/projects/add",
            { path: path.value.trim(), project: project.value.trim() }, "Added: its librarian-app/ is ready.")() }, "Add"),
          status),
        h("p", { class: "note" }, "Adding a folder creates librarian-app/ inside it (manifest, README, data, information, sessions, applications, index, logs), never overwriting a file already there, and never touching the project's own .gitignore. The librarian reads the project. It changes a project file only in a folder where you ticked Allow edits, and asks you before every change, whatever the permission mode; each change is logged with a backup in librarian-app/logs/ so it can be undone."));
    };
    this.api.get("/api/projects").then(paint)
      .catch((e) => clear(host, h("p", { class: "error" }, (e as Error).message)));
    return host;
  }

  /** Slot 6 (R17, SM-8): what embedding the library takes before anything is sent, a
   *  person's own start, the lexical-vs-hybrid measurement, and the intents a person turns
   *  vectors on for after reading it. */
  private embeddingsBlock(s: any, reload: () => void): HTMLElement {
    const status = h("span", { class: "note inline", role: "status" });
    const confirm = h("div");
    const est = s.estimate ?? {};
    const local = h("button", { class: "ghost", title: "A small static model on this machine: no key, no cost",
      onclick: async () => {
        await this.api.post("/api/services", { slot: "embeddings", provider: "model2vec", model: "minishlab/potion-base-8M" });
        reload();
      } }, "Use a local model");
    const embedAll = h("button", { class: "primary", onclick: () => clear(confirm, h("div", { class: "confirm" },
      `This embeds ${est.chunks} text chunks (about ${est.tokens_est} tokens) with ${s.spec}` +
        (s.hosted ? (est.cost_est_usd !== undefined ? `, about $${est.cost_est_usd}.` : ". Its price is unknown here: see the provider's page.")
          : ", on this machine."),
      h("div", { class: "row2" },
        h("button", { class: "ghost", onclick: () => clear(confirm) }, "Cancel"),
        h("button", { class: "primary", onclick: async () => {
          clear(confirm);
          status.textContent = "Embedding…";
          try {
            const out = await this.api.tool("embed_index", {});
            if (out.error) throw new Error(String(out.detail ?? out.error));
            reload();
          } catch (e) { status.textContent = (e as Error).message; }
        } }, "Embed")))) }, "Embed the library");
    const measure = h("button", { class: "ghost", onclick: async () => {
      status.textContent = "Measuring lexical against hybrid on this library's questions…";
      try {
        const out = await this.api.tool("evaluate", { compare_vectors: true });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        reload();
      } catch (e) { status.textContent = (e as Error).message; }
    } }, "Measure (lexical vs hybrid)");
    const using = new Set<string>((s.vector_intents ?? []) as string[]);
    const rows = Object.entries((s.comparison?.by_intent ?? {}) as Record<string, any>);
    const table = rows.length ? h("table", { class: "compare" },
      h("tr", {}, ["intent", "questions", "lexical hit", "hybrid hit", "Δ", "use vectors"].map((t) => h("th", {}, t))),
      rows.map(([intent, r]) => h("tr", {}, h("td", {}, intent), h("td", {}, String(r.n)),
        h("td", {}, String(r.lexical_hit)), h("td", {}, String(r.hybrid_hit)),
        h("td", { class: r.delta_hit > 0 ? "ok" : r.delta_hit < 0 ? "err" : "" }, String(r.delta_hit)),
        h("td", {}, h("input", { type: "checkbox", checked: using.has(intent), "aria-label": `use vectors for ${intent}`,
          onchange: (e: globalThis.Event) => { if ((e.target as HTMLInputElement).checked) using.add(intent); else using.delete(intent); } }))))) : null;
    const save = rows.length ? h("button", { class: "ghost", onclick: async () => {
      await this.api.post("/api/services/vector_intents", { intents: [...using] });
      reload();
    } }, "Save intents") : null;
    return h("div", { class: "embeddings" },
      s.model ? h("p", { class: "dim" }, `${s.embedded ?? 0} of ${s.chunks ?? 0} text chunks embedded` +
        (s.vector_intents?.length ? ` · vectors used for: ${s.vector_intents.join(", ")}` : " · vectors used for no intent yet")) : null,
      h("div", { class: "row2 tight" }, local, s.model && est.chunks ? embedAll : null, s.model ? measure : null, status),
      confirm, table, save,
      s.comparison ? h("p", { class: "note" }, `Measured ${String(s.comparison.at ?? "").slice(0, 10)} on ${s.comparison.questions} questions; vectors joined ${s.comparison.vectors_contributed} answers. Turn them on only where they help.`) : null);
  }

  /** Requirements Addendum R17: service models, slots 4-6 - each one kind of job with its
   *  own request format, chosen with the same tile as the chat models and kept with this
   *  library. Test makes one small real call. */
  private serviceModels(): HTMLElement {
    const host = h("div", { class: "services" }, h("p", { class: "dim" }, "Loading…"));
    void (async () => {
      let out: any;
      try {
        out = await this.api.get("/api/services");
      } catch (e) {
        clear(host, h("p", { class: "error" }, (e as Error).message));
        return;
      }
      clear(host, h("label", { class: "f" }, "Service models"),
        (out.slots ?? []).map((s: any) => {
          const status = h("span", { class: "note inline", role: "status" });
          const current = s.model
            ? `${s.model} · ${PROVIDERS[s.provider] ?? s.provider}${s.default ? " (default)" : ""}`
            : s.built ? "none chosen" : "planned";
          const test = async () => {
            status.className = "note inline";
            status.textContent = "Testing: one small call…";
            try {
              const t = await this.api.post("/api/services/test", { slot: s.slot });
              status.textContent = t.ok ? `Works: it read “${t.read}”.`
                : `Not working: ${t.error ?? `it read “${t.read}”`}`;
              if (t.ok && t.audio) void new Audio(t.audio).play().catch(() => undefined);
              status.className = `note inline ${t.ok ? "ok" : "err"}`;
            } catch (e) {
              status.textContent = (e as Error).message;
            }
          };
          return h("div", { class: `srv service slot-${s.slot}`,
            title: s.built && s.model ? "Right-click to empty this slot" : "",
            oncontextmenu: async (e: Event) => {
              if (!s.built || !s.model) return;
              e.preventDefault();
              try {
                await this.api.post("/api/services", { slot: s.slot, provider: "", model: "" });
                this.render();
              } catch (err) { status.textContent = (err as Error).message; }
            } },
            h("span", { class: "badge" }, String(s.number)),
            h("span", {}, h("strong", {}, s.label), ` · ${current}`, h("span", { class: "dim" }, ` · ${s.job}`),
              s.cap_usd !== undefined ? h("span", { class: "dim" }, ` · spent $${Number(s.spent_usd ?? 0).toFixed(2)} of its $${Number(s.cap_usd).toFixed(2)} cap`) : null),
            s.built && this.chooseService ? h("button", { class: "ghost", onclick: () => {
              this.dialog.close();
              this.chooseService!(s.slot, s.label, { provider: s.provider, model: s.model });
            } }, "Choose…") : null,
            s.built && s.model ? h("button", { class: "ghost", onclick: test }, "Test") : null,
            status,
            s.slot === "embeddings" ? this.embeddingsBlock(s, () => this.render()) : null);
        }),
        h("p", { class: "note" }, "Each does one kind of job with its own request format, and is kept with this library. An empty slot is never filled by a chat model."));
    })();
    return host;
  }

  // -- page 2 --------------------------------------------------------------
  private context(): HTMLElement {
    const s = this.state();
    const text = h("textarea", { class: "f", id: "lib-sys", placeholder: "What will you be working on?" }) as HTMLTextAreaElement;
    text.value = s.working_context ?? "";
    let length: string = s.reply_length ?? "long";
    const custom = h("input", { type: "text", placeholder: "custom", "aria-label": "Custom reply length",
      value: ["long", "short"].includes(length) ? "" : length }) as HTMLInputElement;
    const seg = h("div", { class: "seg", role: "group", "aria-label": "In-chat responses" });
    const paint = () => clear(seg, ["long", "short"].map((v) => h("button", {
      "aria-pressed": String(length === v), onclick: () => { length = v; custom.value = ""; paint(); },
    }, v[0].toUpperCase() + v.slice(1))));
    paint();
    let stance: string = s.stance ?? "answer";
    const stanceSeg = h("div", { class: "seg", role: "group", "aria-label": "Stance" });
    const paintStance = () => clear(stanceSeg, ["answer", "coach"].map((v) => h("button", {
      "aria-pressed": String(stance === v), onclick: () => { stance = v; paintStance(); },
    }, v[0].toUpperCase() + v.slice(1))));
    paintStance();
    const status = h("span", { class: "note inline", role: "status" });
    return h("div", {},
      h("label", { class: "f", for: "lib-sys" }, "System prompt"), text,
      h("label", { class: "f" }, "In-chat responses"),
      h("div", { class: "row2 tight" }, seg, custom),
      h("label", { class: "f" }, "Stance"),
      h("div", { class: "row2 tight" }, stanceSeg),
      h("p", { class: "note" }, "Answer replies directly. Coach asks before telling and gives a hint before an answer - a `learn` session always uses Coach, whatever this is set to."),
      h("div", { class: "row2" }, h("button", { class: "primary", onclick: async () => {
        try {
          await this.api.post("/api/context", { working_context: text.value,
            reply_length: custom.value.trim() || length, stance });
          await this.refresh();
          status.textContent = "Saved.";
        } catch (e) { status.textContent = (e as Error).message; }
      } }, "Save"), status),
      h("p", { class: "note" }, "This shapes chat replies only. Notes, concepts and offerings are written by the tier 2 model without it, so how you like replies never changes how the catalogue is written."));
  }

  // -- page 3 --------------------------------------------------------------
  // A skills registry: curated servers toggle on in one step (install +
  // accept), plus a hand-add form for anything else, status per server, and
  // per-tool Allow/Ask/Deny. Outside tools stay outside the rules - their
  // results are marked untrusted, and none can write to the vault - so this
  // page only ever asks "which server, which tool", never "trust it fully".
  private mcp(): HTMLElement {
    const host = h("div", {}, h("p", { class: "dim" }, "Loading…"));
    const load = () => this.api.get("/api/mcp")
      .then((data) => clear(host, this.mcpBody(data, load)))
      .catch((e) => clear(host, h("p", { class: "error" }, (e as Error).message)));
    load();
    return host;
  }

  private mcpBody(data: any, reload: () => void): HTMLElement {
    const servers: Record<string, any> = data.servers ?? {};
    const toolSettings: Record<string, string> = data.tool_settings ?? {};
    const status = h("span", { class: "note inline", role: "status" });
    const busy = (label: string) => { status.textContent = label; status.className = "note inline"; };
    const fail = (e: unknown) => { status.textContent = (e as Error).message; status.className = "note inline err"; };

    const curatedCard = (skill: typeof CURATED_SKILLS[number]) => {
      const installed = servers[skill.id];
      // "On" means on in *this* library (§4 F1): installed once for the
      // person, each library enables it for itself.
      const on = !!installed?.enabled && installed?.library_enabled !== false;
      const toggle = h("button", { class: on ? "ghost" : "primary", onclick: async () => {
        busy(on ? "Disabling in this library…" : installed ? "Enabling in this library…" : "Installing and enabling…");
        try {
          if (installed) {
            if (!on && !installed.enabled) await this.api.post("/api/mcp/enable", { name: skill.id, enabled: true });
            await this.api.post("/api/mcp/library", { name: skill.id, enabled: !on });
          } else {
            await this.api.post("/api/mcp/server", { name: skill.id,
              server: { command: skill.command, args: skill.args, env: skill.env ?? {}, enabled: true } });
          }
          status.textContent = ""; reload();
        } catch (e) { fail(e); }
      } }, on ? "Disable here" : installed ? "Enable here" : "Install") as HTMLButtonElement;
      return h("div", { class: "srv" },
        h("span", { class: `dot ${on ? "" : "off"}` }),
        h("span", {}, h("strong", {}, skill.name), h("span", { class: "dim" }, ` · ${skill.description}`)),
        toggle);
    };

    const nameInput = h("input", { type: "text", placeholder: "server name" }) as HTMLInputElement;
    const cmdInput = h("input", { type: "text", placeholder: "command, e.g. npx" }) as HTMLInputElement;
    const argsInput = h("input", { type: "text", placeholder: "args, space-separated" }) as HTMLInputElement;
    const envInput = h("input", { type: "text", placeholder: "env as KEY=value, comma-separated (optional)" }) as HTMLInputElement;

    // Browsing is read-only and never connects anything by itself: a result
    // only ever pre-fills the hand-add form below, the same way a curated
    // card's own definition would, and the person still has to look at it
    // and click Add and accept themselves - an extra look, on top of the
    // curated list's one click, since these are unvetted by anyone here.
    const searchInput = h("input", { type: "search",
      placeholder: "search the MCP registry, e.g. calendar" }) as HTMLInputElement;
    const browseResults = h("div", { class: "browse-results" });
    const fillHandAdd = (name: string, server: { command: string; args: string[]; env: Record<string, string> }) => {
      nameInput.value = name;
      cmdInput.value = server.command;
      argsInput.value = server.args.join(" ");
      envInput.value = Object.entries(server.env).map(([k, v]) => `${k}=${v}`).join(", ");
      nameInput.scrollIntoView({ block: "center" });
      nameInput.focus();
    };
    const runSearch = async () => {
      clear(browseResults, h("p", { class: "dim" }, "Searching…"));
      let out: any;
      try {
        out = await this.api.get(`/api/mcp/registry?q=${encodeURIComponent(searchInput.value.trim())}`);
      } catch (e) { clear(browseResults, h("p", { class: "error" }, (e as Error).message)); return; }
      if (out.error) { clear(browseResults, h("p", { class: "note err" }, out.error)); return; }
      const entries: any[] = out.servers ?? [];
      if (!entries.length) { clear(browseResults, h("p", { class: "dim" }, "No results.")); return; }
      clear(browseResults, entries.map((entry) => h("div", { class: "srv" },
        h("span", { class: `dot ${entry.resolvable ? "" : "nokey"}` }),
        h("span", {}, h("strong", {}, entry.title || entry.name),
          h("span", { class: "dim" }, ` · ${entry.description}`),
          entry.repository
            ? h("a", { href: entry.repository, target: "_blank", rel: "noreferrer noopener" }, " repo ↗") : null,
          !entry.resolvable ? h("div", { class: "note" }, entry.reason) : null),
        entry.resolvable
          ? h("button", { class: "ghost",
              onclick: () => fillHandAdd(String(entry.name).split("/").pop() || entry.name, entry.server) },
              "Fill in below")
          : null)));
    };
    searchInput.onkeydown = (e) => { if (e.key === "Enter") runSearch(); };

    const addServer = async () => {
      const name = nameInput.value.trim();
      if (!name || !cmdInput.value.trim()) { fail(new Error("name and command are required")); return; }
      const env: Record<string, string> = {};
      for (const pair of envInput.value.split(",").map((s) => s.trim()).filter(Boolean)) {
        const [key, ...rest] = pair.split("=");
        if (key) env[key.trim()] = rest.join("=").trim();
      }
      busy("Adding and accepting…");
      try {
        await this.api.post("/api/mcp/server", { name, server: {
          command: cmdInput.value.trim(),
          args: argsInput.value.split(/\s+/).filter(Boolean), env, enabled: true } });
        nameInput.value = cmdInput.value = argsInput.value = envInput.value = "";
        status.textContent = ""; reload();
      } catch (e) { fail(e); }
    };

    const toolRow = (tool: string) => {
      let setting = toolSettings[tool] ?? "ask";
      const seg = h("div", { class: "seg", role: "group", "aria-label": `${tool} permission` });
      const paint = () => clear(seg, ["allow", "ask", "deny"].map((v) => h("button", {
        "aria-pressed": String(setting === v),
        onclick: async () => {
          try {
            await this.api.post("/api/tool-setting", { tool, setting: v });
            setting = v; toolSettings[tool] = v; paint();
          } catch (e) { fail(e); }
        },
      }, v[0].toUpperCase() + v.slice(1))));
      paint();
      return h("div", { class: "row2 tight" }, h("span", { class: "dim" }, tool.replace(/^mcp__/, "")), seg);
    };

    const serverRows = Object.entries(servers).map(([name, s]) => h("div", { class: "srv-block" },
      h("div", { class: "srv" },
        h("span", { class: `dot ${s.connected ? "" : s.error ? "off" : "nokey"}` }),
        h("span", {}, h("strong", {}, name),
          h("span", { class: "dim" }, ` · ${s.command}${(s.args ?? []).length ? " " + s.args.join(" ") : ""}`),
          (s.env ?? []).length ? h("span", { class: "dim" }, ` · env: ${s.env.join(", ")}`) : null,
          h("span", { class: "dim" }, ` · ${s.tools ?? 0} tool${s.tools === 1 ? "" : "s"}`)),
        s.library_enabled === undefined ? null : h("button", { class: s.library_enabled ? "ghost" : "primary",
          title: "Whether this library uses it; every library decides for itself", onclick: async () => {
          busy(s.library_enabled ? "Disabling in this library…" : "Enabling in this library…");
          try { await this.api.post("/api/mcp/library", { name, enabled: !s.library_enabled }); status.textContent = ""; reload(); }
          catch (e) { fail(e); }
        } }, s.library_enabled ? "Disable here" : "Enable here"),
        h("button", { class: "ghost", title: "Installed for you: pausing stops it in every library", onclick: async () => {
          busy(s.enabled ? "Pausing everywhere…" : "Resuming…");
          try { await this.api.post("/api/mcp/enable", { name, enabled: !s.enabled }); status.textContent = ""; reload(); }
          catch (e) { fail(e); }
        } }, s.enabled ? "Pause all" : "Resume all"),
        h("button", { class: "ghost", onclick: async () => {
          busy("Removing…");
          try { await this.api.post("/api/mcp/remove", { name }); status.textContent = ""; reload(); }
          catch (e) { fail(e); }
        } }, "Remove")),
      s.error ? h("p", { class: "note err" }, s.error) : null,
      s.unpinned ? h("p", { class: "note err" }, `Not pinned: ${s.unpinned}`) : null,
      s.changed_since_enabled ? h("p", { class: "note" }, "Its definition changed after this library turned it on - still on here; worth a look.") : null,
      (s.tool_names ?? []).length
        ? h("div", { class: "tool-perms" }, (s.tool_names as string[]).map(toolRow))
        : null));

    return h("div", {},
      h("label", { class: "f" }, "Skills registry"),
      h("p", { class: "note" }, "Installed once for you, then enabled per library, off until you turn it on: a history library and a software library each choose their own tools."),
      CURATED_SKILLS.map(curatedCard),
      h("label", { class: "f" }, "Browse the MCP Registry"),
      h("div", { class: "row2 tight" }, searchInput,
        h("button", { class: "ghost", onclick: runSearch }, "Search")),
      browseResults,
      h("label", { class: "f" }, "Add a server by hand"),
      h("div", { class: "row2 tight" }, nameInput, cmdInput),
      h("div", { class: "row2 tight" }, argsInput, envInput),
      h("div", { class: "row2" }, h("button", { class: "primary", onclick: addServer }, "Add and accept"), status),
      h("label", { class: "f" }, "Servers"),
      serverRows.length ? serverRows : h("p", { class: "dim" }, "None configured yet."),
      h("p", { class: "note" }, "Outside tools stay outside the rules: their results are marked untrusted, clerk tasks ",
        "never call them, and none can write to the vault. Each tool defaults to Ask until set otherwise. Meanwhile, ",
        "the librarian itself is an MCP server: `resource-librarian mcp` (see the Cowork plugin)."));
  }

  // -- page 4 --------------------------------------------------------------
  private library(): HTMLElement {
    const host = h("div", {}, h("p", { class: "dim" }, "Loading…"));
    const packs = h("div", { class: "lens-packs" }, h("p", { class: "dim" }, "Loading…"));
    const catalogs = h("div", { class: "model-catalogs" }, h("p", { class: "dim" }, "Loading…"));
    const profile = h("div", { class: "library-profile" });
    const topics = h("div", { class: "topics" }, h("p", { class: "dim" }, "Loading…"));
    this.api.get("/api/library").then((lib) => {
      const promo = h("select", { id: "lib-promo" },
        [["person", "person (default): a person accepts every promotion"], ["agent", "agent: the librarian may promote, except sensitive material"]]
          .map(([v, label]) => h("option", { value: v, selected: lib.promotion?.mode === v }, label))) as HTMLSelectElement;
      const status = h("span", { class: "note inline", role: "status" });
      promo.onchange = async () => {
        try { await this.api.post("/api/library", { promotion_mode: promo.value }); status.textContent = "Saved to the vault's config."; }
        catch (e) { status.textContent = (e as Error).message; }
      };
      // A key row in the list below opens a box under the list to set that key in place
      // (owner, 2026-10-02): the same key store as Settings -> Connections.
      const keyBox = h("div", { class: "key-entry" });
      let opened: HTMLElement | null = null;
      const keyEntry = (c: any, row: HTMLElement) => {
        opened?.setAttribute("aria-expanded", "false");
        if (opened === row) { opened = null; clear(keyBox); return; }
        opened = row;
        row.setAttribute("aria-expanded", "true");
        const label = String(c.name).replace(/^key: /, "");
        const input = h("input", { type: "password", autocomplete: "off", "aria-label": `${label} key`,
          placeholder: c.ok ? `Replace the key (${c.detail})` : `Paste the ${label} key` }) as HTMLInputElement;
        const said = h("span", { class: "note inline", role: "status" });
        const save = async () => {
          if (!input.value.trim()) return;
          said.textContent = "Saving…";
          try {
            const out = await this.api.post("/api/keys", { provider: c.key, key: input.value.trim(), overwrite: true });
            input.value = "";
            said.textContent = out.check?.ok ? out.check.status : `Saved, but the provider said: ${out.check?.error ?? "no answer"}`;
            said.className = `note inline ${out.check?.ok ? "ok" : "err"}`;
            await this.refresh();
            // The row says so at once: its dot goes green and its detail names the store.
            const line = row.closest(".srv");
            line?.querySelector(".dot")?.setAttribute("class", "dot");
            const detail = line?.querySelector(".key-detail");
            if (detail) detail.textContent = " · saved in this computer's key store";
          } catch (e) {
            said.textContent = (e as Error).message;
            said.className = "note inline err";
          }
        };
        input.onkeydown = (e) => { if (e.key === "Enter") void save(); };
        clear(keyBox, h("div", { class: "confirm" },
          h("label", { class: "f" }, `${label} key`),
          h("div", { class: "row2 tight" }, input,
            h("button", { class: "primary", onclick: () => void save() }, "Save key"),
            h("button", { class: "ghost", onclick: () => keyEntry(c, row) }, "Cancel")),
          said,
          h("small", { class: "dim" }, "Kept in this computer's key store, never in a library. Settings -> Connections lists every key.")));
        input.focus();
      };
      // §4 G3: a second model checks claims against the notes they cite (O4, O5).
      const reviewStatus = h("span", { class: "note inline", role: "status" });
      const reviewBox = (key: string, label: string, hint: string) => {
        const box = h("input", { type: "checkbox", id: `lib-${key}` }) as HTMLInputElement;
        box.checked = !!lib.clerk?.[key];
        box.onchange = async () => {
          try {
            await this.api.post("/api/library", { review: { [key]: box.checked } });
            reviewStatus.textContent = "Saved to the library's config.";
          } catch (e) {
            box.checked = !box.checked;
            reviewStatus.textContent = (e as Error).message;
          }
        };
        return h("div", { class: "srv" }, box, h("label", { for: `lib-${key}` }, h("strong", {}, label), h("span", { class: "dim" }, ` · ${hint}`)));
      };
      clear(host,
        h("label", { class: "f", for: "lib-promo" }, "Promotion"), h("div", { class: "row2 tight" }, promo, status),
        h("label", { class: "f" }, "Review"),
        reviewBox("review_replies", "Check replies",
          "the claims a reply makes about the notes it links are checked against those notes; the verdict shows under the reply"),
        reviewBox("review_offerings", "Check drafted offerings",
          "each claim is checked before the draft is staged; a challenged claim kept by the librarian needs you to promote it"),
        h("p", { class: "note" }, "Run by the small-tasks model (tier 3), or `route_review` under [clerk]. A high effort setting also turns these on for its turns. ", reviewStatus),
        h("label", { class: "f" }, "Distribution posture"),
        h("p", {}, String(lib.usage?.distribution_posture ?? "private"), h("span", { class: "dim" }, " · set in the vault's config")),
        h("label", { class: "f" }, "Clerk route"),
        h("p", {}, lib.clerk?.provider ? `configured: ${lib.clerk.provider}` : "tier 3 model, else queued"),
        h("label", { class: "f" }, "Capabilities on this install"),
        (lib.doctor ?? []).map((c: any) => h("div", { class: "srv" },
          h("span", { class: `dot ${c.ok ? "" : c.required ? "off" : "nokey"}` }),
          h("span", {}, c.key
            ? h("button", { class: "link", title: `${c.ok ? "Replace" : "Add"} this key`,
                "aria-expanded": "false", onclick: (e: Event) => keyEntry(c, e.currentTarget as HTMLElement) },
                h("strong", {}, c.name))
            : h("strong", {}, c.name), h("span", { class: "key-detail" }, ` · ${c.detail ?? ""}`)))),
        keyBox,
        profile,
        h("label", { class: "f" }, "Topics"),
        topics,
        h("label", { class: "f" }, "Lens packs"),
        packs,
        h("label", { class: "f" }, "Model catalogues"),
        catalogs);
      void this.paintTopics(topics);
      void this.paintPacks(packs);
      void this.paintModelCatalogs(catalogs);
      void this.paintProfile(profile);
    }).catch((e) => clear(host, h("p", { class: "error" }, (e as Error).message)));
    return host;
  }

  /** The closed topic list (About/Topics.md) and the topics proposed for it (R8): only
   *  here does a proposal join the list - accepted as proposed, renamed, or rejected. */
  private async paintTopics(host: HTMLElement): Promise<void> {
    const status = h("span", { class: "note inline", role: "status" });
    const reload = () => void this.paintTopics(host);
    let out: any;
    try {
      out = await this.api.tool("topics_list", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
    } catch (e) {
      clear(host, h("p", { class: "error" }, (e as Error).message));
      return;
    }
    const propose = h("button", { class: "ghost", onclick: async () => {
      status.textContent = "Asking the clerk to group the sources…";
      try {
        const r = await this.api.tool("topic_propose", { only_unfiled: false });
        if (r.error) throw new Error(String(r.detail ?? r.error));
        status.textContent = r.detail ? String(r.detail) : `${(r.proposed ?? []).length} proposed.`;
        reload();
      } catch (e) { status.textContent = (e as Error).message; }
    } }, "Propose topics");
    const refresh = h("button", { class: "ghost", title: "Rewrite the topic indexes and the Master Index from the notes",
      onclick: async () => {
        try { await this.api.tool("views_refresh", {}); status.textContent = "Indexes rewritten."; }
        catch (e) { status.textContent = (e as Error).message; }
      } }, "Rewrite indexes");
    const proposal = (p: any) => {
      const name = h("input", { type: "text", value: p.name, "aria-label": "Topic name" }) as HTMLInputElement;
      const file = h("input", { type: "checkbox", checked: true }) as HTMLInputElement;
      const accept = h("button", { class: "primary", onclick: async () => {
        try {
          const r = await this.api.tool("staging_decide", { item_ids: [p.id], decision: "accept",
            fields: { name: name.value, refile: file.checked } });
          const one = (r.results ?? [])[0] ?? r;
          if (r.error || one.error || one.refused) throw new Error(String(one.detail ?? one.error ?? r.detail ?? r.error));
          status.textContent = `${one.topic} added; ${(one.refiled ?? []).filter((x: any) => x.topic && !x.unchanged).length} source(s) filed under it.`;
          reload();
        } catch (e) { status.textContent = (e as Error).message; }
      } }, "Accept");
      return h("div", { class: "srv" }, name,
        h("label", { class: "note inline" }, file, ` file its ${p.sources} source${p.sources === 1 ? "" : "s"} under it`),
        p.duplicate_of ? h("span", { class: "warn" }, `close to ${p.duplicate_of}`) : null, accept);
    };
    clear(host,
      h("p", {}, (out.topics ?? []).map((t: any) => `${t.topic} (${t.sources})`).join(" · ")),
      out.unfiled ? h("p", { class: "note" }, `${out.unfiled} source${out.unfiled === 1 ? "" : "s"} Unfiled.`) : null,
      (out.not_accepted ?? []).length ? h("p", { class: "warn" }, `Filed under topics not in the list: ${(out.not_accepted as string[]).join(", ")}.`) : null,
      (out.proposed ?? []).length ? h("p", { class: "note" }, "Proposed from the library's own sources (details in Staging → Topics):") : null,
      (out.proposed ?? []).map(proposal),
      h("div", { class: "row2 tight" }, propose, refresh, status));
  }

  /** The domain profile this library was created with (profiles.py): what it
   *  suggests and where each item stands. Suggestions only - each is taken up
   *  through its own gate (a pack's Accept below, a server's Enable here on
   *  the MCP servers page). */
  private async paintProfile(host: HTMLElement): Promise<void> {
    try {
      const out = await this.api.tool("library_profile", {});
      if (!out.profile) { clear(host); return; }
      const done = (state: string) => state === "accepted" || state === "enabled here" || state === "available";
      const item = (kind: string, name: string, state: string) => h("div", { class: "srv" },
        h("span", { class: `dot ${done(state) ? "" : "nokey"}` }),
        h("span", {}, h("strong", {}, name), h("span", { class: "dim" }, ` · ${kind} · ${state}`)));
      clear(host,
        h("label", { class: "f" }, `Set up for its domain: the ${out.profile} profile`),
        (out.content_model_added ?? []).length
          ? h("p", { class: "note" }, `Added at creation: ${(out.content_model_added as string[]).join("; ")}.`) : null,
        (out.lens_packs ?? []).map((p: any) => item("lens pack - accept it below", p.name, p.state)),
        (out.mcp_servers ?? []).map((m: any) => item("outside server - MCP servers page", m.name, m.state)),
        (out.workflows ?? []).map((w: any) => item("workflow", w.name, w.state)),
        h("p", { class: "note" }, "Suggestions only: nothing here is accepted, installed or turned on until you do it."));
    } catch {
      clear(host);
    }
  }

  /** Lens packs (lens_packs.py): a plugin's or domain pack's hand-written
   *  lenses. Nothing is installed until a person accepts a pack's exact text;
   *  a pack whose file changed since shows as changed and needs accepting again. */
  private async paintPacks(host: HTMLElement, message = ""): Promise<void> {
    try {
      const out = await this.api.tool("lens_packs", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const packs = (out.packs ?? []) as { name: string; origin: string; state: string; description: string;
        lenses: string[]; problems: string[] }[];
      const status = h("span", { class: "note inline", role: "status" }, message);
      clear(host,
        h("p", { class: "note" }, "A pack's lenses are instructions someone else wrote for the model. Read them before accepting; nothing is used until a person adopts a lens in a thread."),
        packs.length ? packs.map((p) => h("div", { class: "srv" },
          h("span", { class: `dot ${p.state === "accepted" ? "" : p.state === "invalid" ? "off" : "nokey"}` }),
          h("span", {}, h("strong", {}, p.name), ` · ${p.origin} · ${p.state} · ${p.lenses.length} lens${p.lenses.length === 1 ? "" : "es"}`,
            p.description ? h("small", { class: "dim" }, ` — ${p.description}`) : null,
            h("details", {}, h("summary", {}, "Lenses"), h("ul", {}, p.lenses.map((n) => h("li", {}, n)))),
            p.problems.length ? h("p", { class: "note err" }, p.problems.slice(0, 5).join("; ")) : null),
          p.state === "not accepted" || p.state === "changed"
            ? h("button", { class: "ghost", onclick: async () => {
                try {
                  const r = await this.api.tool("lens_pack_accept", { name: p.name });
                  if (r.error) throw new Error(String(r.detail ?? r.error));
                  void this.paintPacks(host, `${p.name}: ${r.lenses.length} lens(es) installed${r.replaced ? `, ${r.replaced} replaced` : ""}.`);
                } catch (e) { status.textContent = (e as Error).message; }
              } }, p.state === "changed" ? "Accept the new version" : "Accept")
            : null))
          : h("p", { class: "dim" }, "No lens packs. A plugin or domain pack adds one to .librarian/lens_packs/."),
        status);
    } catch (e) {
      clear(host, h("p", { class: "error" }, (e as Error).message));
    }
  }

  /** Standard model catalogues (model_catalog.py): a provider's models,
   *  already profiled once and shipped with the package. Adopting one writes
   *  its Source notes straight in - each was reviewed once already, so this
   *  is reusing that review, not asking the vault to trust a fresh draft. */
  private async paintModelCatalogs(host: HTMLElement, message = ""): Promise<void> {
    try {
      const out = await this.api.tool("model_catalog_status", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const catalogs = (out.catalogues ?? []) as { provider: string; models: number; held: number }[];
      const status = h("span", { class: "note inline", role: "status" }, message);
      clear(host,
        h("p", { class: "note" }, "Each model here was already profiled once from its provider's own listing page - adopting a catalogue reuses that, instead of profiling every model again in this vault."),
        catalogs.length ? catalogs.map((c) => h("div", { class: "srv" },
          h("span", { class: `dot ${c.held === c.models ? "" : "nokey"}` }),
          h("span", {}, h("strong", {}, c.provider), ` · ${c.held}/${c.models} models held`),
          c.held < c.models
            ? h("button", { class: "ghost", onclick: async () => {
                try {
                  const r = await this.api.tool("model_catalog_adopt", { provider: c.provider });
                  if (r.error) throw new Error(String(r.detail ?? r.error));
                  void this.paintModelCatalogs(host, `${c.provider}: ${r.written} model(s) added${r.already_held ? `, ${r.already_held} already held` : ""}${r.failed.length ? `, ${r.failed.length} failed` : ""}.`);
                } catch (e) { status.textContent = (e as Error).message; }
              } }, c.held ? "Adopt the rest" : "Adopt")
            : null))
          : h("p", { class: "dim" }, "No standard model catalogues are bundled with this install."),
        status);
    } catch (e) {
      clear(host, h("p", { class: "error" }, (e as Error).message));
    }
  }
}
