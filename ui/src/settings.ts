// + Settings: Connections, Working context, MCP servers, Library.
// A key goes to the core once and never comes back: only whether one is saved
// and its last four characters.

import type { Api } from "./api";
import { ApiError } from "./api";
import { clear, h } from "./dom";
import { PROVIDERS } from "./panels";

const PAGES = [["connections", "Connections"], ["context", "Working context"],
               ["mcp", "MCP servers"], ["library", "Library"]] as const;

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
              private refresh: () => Promise<void>, private manageKeys?: () => void) {
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
                   mcp: () => this.mcp(), library: () => this.library() }[this.page];
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
        h("p", { class: "note" }, "After changing a key, the plugin restarts the core so it takes effect."));
    }
    const select = h("select", { id: "lib-provider" },
      Object.entries(PROVIDERS).map(([id, label]) => h("option", { value: id }, label))) as HTMLSelectElement;
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
      input.disabled = false; save.hidden = false; checkUsage.hidden = false;
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
      `Remove the saved ${PROVIDERS[select.value]} key? It can't be recovered from here.`,
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
      h("div", { class: "row2" }, checkUsage), usageBox);
    show();
    return page;
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
    this.api.get("/api/library").then((lib) => {
      const promo = h("select", { id: "lib-promo" },
        [["person", "person (default): a person accepts every promotion"], ["agent", "agent: the librarian may promote, except sensitive material"]]
          .map(([v, label]) => h("option", { value: v, selected: lib.promotion?.mode === v }, label))) as HTMLSelectElement;
      const status = h("span", { class: "note inline", role: "status" });
      promo.onchange = async () => {
        try { await this.api.post("/api/library", { promotion_mode: promo.value }); status.textContent = "Saved to the vault's config."; }
        catch (e) { status.textContent = (e as Error).message; }
      };
      clear(host,
        h("label", { class: "f", for: "lib-promo" }, "Promotion"), h("div", { class: "row2 tight" }, promo, status),
        h("label", { class: "f" }, "Distribution posture"),
        h("p", {}, String(lib.usage?.distribution_posture ?? "private"), h("span", { class: "dim" }, " · set in the vault's config")),
        h("label", { class: "f" }, "Clerk route"),
        h("p", {}, lib.clerk?.provider ? `configured: ${lib.clerk.provider}` : "tier 3 model, else queued"),
        h("label", { class: "f" }, "Capabilities on this install"),
        (lib.doctor ?? []).map((c: any) => h("div", { class: "srv" },
          h("span", { class: `dot ${c.ok ? "" : c.required ? "off" : "nokey"}` }),
          h("span", {}, h("strong", {}, c.name), ` · ${c.detail ?? ""}`))),
        profile,
        h("label", { class: "f" }, "Lens packs"),
        packs,
        h("label", { class: "f" }, "Model catalogues"),
        catalogs);
      void this.paintPacks(packs);
      void this.paintModelCatalogs(catalogs);
      void this.paintProfile(profile);
    }).catch((e) => clear(host, h("p", { class: "error" }, (e as Error).message)));
    return host;
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
