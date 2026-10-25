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
        this.serviceModels(), this.releaseLeadSetup(), this.agentProfiles(), this.hostRegistry());
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
    const keyMigration = h("div");
    if (this.state().key_backend === "config file" || this.state().key_migration_pending) {
      const migrationStatus = h("span", { class: "note inline", role: "status" });
      const migrate = h("button", { class: "ghost", onclick: () => clear(keyMigration,
        h("div", { class: "confirm" },
          "Move the saved fallback-file credentials into this computer's operating-system keychain? No key value is displayed or sent back to this page.",
          h("div", { class: "row2" },
            h("button", { class: "ghost", onclick: () => { this.render(); } }, "Cancel"),
            h("button", { class: "primary", onclick: async () => {
              migrationStatus.textContent = "Migrating…";
              try {
                const out = await this.api.post("/api/keys/migrate", { confirm: true });
                await this.refresh();
                if (out.available === false) {
                  migrationStatus.textContent = String(out.detail ?? "No operating-system keychain is available yet.");
                  migrationStatus.className = "note inline err";
                } else if (out.fallback_retained) {
                  migrationStatus.textContent = String(out.detail ?? "Migrated, but the old fallback file remains.");
                  migrationStatus.className = "note inline err";
                } else {
                  migrationStatus.textContent = out.already_secure ? "Keys are already in the operating-system keychain." : "Saved keys moved to the operating-system keychain.";
                  migrationStatus.className = "note inline ok";
                }
              } catch (e) {
                migrationStatus.textContent = (e as Error).message;
                migrationStatus.className = "note inline err";
              }
            } }, "Migrate")))) }, "Move fallback keys to keychain") as HTMLButtonElement;
      clear(keyMigration, h("p", { class: "note" },
        this.state().key_migration_pending
          ? "A protected fallback key file from an earlier installation still needs explicit migration into this computer's keychain."
          : "This installation is using the protected file fallback. Once the operating-system keychain is available, move saved keys explicitly."),
      h("div", { class: "row2" }, migrate, migrationStatus));
    }
    const page = h("div", {},
      h("label", { class: "f", for: "lib-provider" }, "Provider"), select,
      h("label", { class: "f", for: "lib-key" }, "Connect API key"), input,
      h("div", { class: "row2" }, save, remove, status), confirmBox,
      h("p", { class: "note" }, `Keys are kept by the core (${this.state().key_backend ?? "securely"}), never in the vault. `,
        "They never come back to this page: only whether one is saved, and its last four characters."),
      keyMigration,
      h("label", { class: "f" }, "Usage & billing"),
      h("div", { class: "row2" }, checkUsage), usageBox,
      this.serviceModels(), this.releaseLeadSetup(), this.agentProfiles(), this.hostRegistry());
    show();
    return page;
  }

  /** The chosen profile narrows an agent; it cannot expand a person's tools
   * or silently change its route.  Keeping the selector beside hosts makes
   * the connection between a model choice and its policy visible. */
  private agentProfiles(): HTMLElement {
    const root = h("section", { class: "agent-profiles" }, h("p", { class: "dim" }, "Loading agent profiles…"));
    const reload = async () => {
      try {
        const out = await this.api.get("/api/profiles");
        const profiles = (out.profiles ?? []) as any[];
        const selected = String(out.selected ?? this.state().agent_profile ?? "lead");
        const status = h("span", { class: "note inline", role: "status" });
        const select = h("select", { "aria-label": "Agent profile" }, profiles.map((profile) =>
          h("option", { value: String(profile.id), selected: String(profile.id) === selected },
            `${profile.id} r${profile.revision ?? 1} · ${profile.role} · ${profile.permission_ceiling}`))) as HTMLSelectElement;
        select.onchange = async () => {
          status.textContent = "Applying profile…";
          try {
            await this.api.post("/api/agent-profile", { id: select.value });
            await this.refresh();
            status.textContent = "Applied to subsequent agent turns.";
            status.className = "note inline ok";
          } catch (e) {
            select.value = selected;
            status.textContent = (e as Error).message;
            status.className = "note inline err";
          }
        };
        const active = out.active ?? {};
        const editor = h("div", { class: "profile-editor" });
        const split = (value: string) => value.split(",").map((part) => part.trim()).filter(Boolean);
        const showEditor = (base: any, creating = false) => {
          const route = base.route_policy ?? {};
          const rates = route.rate_card ?? {};
          const id = h("input", { type: "text", value: creating ? "" : String(base.id ?? ""),
            placeholder: "profile id", "aria-label": "Profile id" }) as HTMLInputElement;
          const role = h("input", { type: "text", value: String(base.role ?? "lead"),
            "aria-label": "Profile role" }) as HTMLInputElement;
          const routeSlots = ["lead", "scribe", "clerk", "research_helper"];
          const bindingRole = h("select", { "aria-label": "Model route slot" },
            routeSlots.map((value) => h("option", { value,
              selected: value === String(route.binding_role ?? (routeSlots.includes(base.role) ? base.role : "lead")) },
              value.replace(/_/g, " ")))) as HTMLSelectElement;
          const ceiling = h("select", { "aria-label": "Permission ceiling" },
            ["consult", "contribute", "curate"].map((value) => h("option", { value,
              selected: value === String(base.permission_ceiling ?? "contribute") }, value))) as HTMLSelectElement;
          const qualification = h("select", { "aria-label": "Required qualification" },
            ["experimental", "screened", "verified_local", "verified_release"].map((value) => h("option", { value,
              selected: value === String(base.required_qualification ?? "screened") }, value))) as HTMLSelectElement;
          const bundles = h("input", { type: "text", value: (base.allowed_bundles ?? []).join(", "),
            placeholder: "session, research", "aria-label": "Allowed tool bundles" }) as HTMLInputElement;
          const hosts = h("input", { type: "text", value: (route.host_ids ?? []).join(", "),
            placeholder: "optional host ids", "aria-label": "Allowed host ids" }) as HTMLInputElement;
           const providers = h("input", { type: "text", value: (route.providers ?? []).join(", "),
             placeholder: "optional legacy providers", "aria-label": "Allowed legacy providers" }) as HTMLInputElement;
          const models = h("input", { type: "text", value: (route.model_ids ?? []).join(", "),
            placeholder: "optional model ids", "aria-label": "Allowed model ids" }) as HTMLInputElement;
           const validation = h("input", { type: "text", value: (base.validation_rules ?? []).join(", "),
             placeholder: "grounded, cite evidence", "aria-label": "Validation focus rules" }) as HTMLInputElement;
          const token = h("input", { type: "number", min: 0, value: String(base.token_budget ?? 0),
            "aria-label": "Token budget per agent turn" }) as HTMLInputElement;
          const output = h("input", { type: "number", min: 1, value: String(base.output_budget ?? 4096),
            "aria-label": "Maximum output tokens" }) as HTMLInputElement;
          const cost = h("input", { type: "number", min: 0, step: "0.01", value: String(base.cost_budget_usd ?? 0),
            "aria-label": "Cost budget USD per agent turn" }) as HTMLInputElement;
          const seconds = h("input", { type: "number", min: 0, value: String(base.time_budget_seconds ?? 0),
            "aria-label": "Time budget seconds" }) as HTMLInputElement;
          const concurrent = h("input", { type: "number", min: 1, max: 32, value: String(base.concurrency_limit ?? 1),
            "aria-label": "Concurrent runs" }) as HTMLInputElement;
          const inputRate = h("input", { type: "number", min: 0, step: "0.001",
            value: String(rates.input_per_1m ?? rates.price_input_per_1m ?? ""),
            placeholder: "input $/1M", "aria-label": "Input USD per million tokens" }) as HTMLInputElement;
          const outputRate = h("input", { type: "number", min: 0, step: "0.001",
            value: String(rates.output_per_1m ?? rates.price_output_per_1m ?? ""),
            placeholder: "output $/1M", "aria-label": "Output USD per million tokens" }) as HTMLInputElement;
          const retry = h("select", { "aria-label": "Retry policy" }, ["bounded", "none"].map((value) =>
            h("option", { value, selected: value === String(base.retry_policy ?? "bounded") }, value))) as HTMLSelectElement;
          const failover = h("select", { "aria-label": "Failover policy" }, ["ask", "never"].map((value) =>
            h("option", { value, selected: value === String(base.failover_policy ?? "ask") }, value))) as HTMLSelectElement;
          const editorStatus = h("span", { class: "note inline", role: "status" });
          const save = async () => {
            const rateCard: Record<string, number> = {};
            if (inputRate.value.trim() || outputRate.value.trim()) {
              rateCard.input_per_1m = Number(inputRate.value || 0);
              rateCard.output_per_1m = Number(outputRate.value || 0);
            }
            const profile = { ...base, id: id.value.trim(), role: role.value.trim(),
              permission_ceiling: ceiling.value, required_qualification: qualification.value,
              allowed_bundles: split(bundles.value), token_budget: Number(token.value || 0),
              output_budget: Number(output.value || 4096), cost_budget_usd: Number(cost.value || 0),
              time_budget_seconds: Number(seconds.value || 0), concurrency_limit: Number(concurrent.value || 1),
              retry_policy: retry.value, failover_policy: failover.value,
               validation_rules: split(validation.value),
              route_policy: { ...route, host_ids: split(hosts.value), model_ids: split(models.value),
                 binding_role: bindingRole.value,
                 providers: split(providers.value),
                ...(Object.keys(rateCard).length ? { rate_card: rateCard } : {}) } };
            editorStatus.textContent = "Saving profile…";
            try {
              await this.api.post("/api/profiles", { profile });
              editorStatus.textContent = "Saved as a new profile revision.";
              editorStatus.className = "note inline ok";
              await reload();
            } catch (e) {
              editorStatus.textContent = (e as Error).message;
              editorStatus.className = "note inline err";
            }
          };
          clear(editor,
            h("div", { class: "confirm" },
              h("strong", {}, creating ? "New agent profile" : `Edit ${base.id}`),
              h("div", { class: "row2 tight" }, id, role, ceiling, qualification),
              h("label", { class: "f" }, "Use the model assigned to this route slot"), bindingRole,
              h("label", { class: "f" }, "Tool bundles (comma-separated)"), bundles,
              h("label", { class: "f" }, "Route allow-lists (blank means unrestricted)"),
               h("div", { class: "row2 tight" }, hosts, providers, models),
               h("label", { class: "f" }, "Validation focus (comma-separated, guidance only; platform gates still apply)"), validation,
              h("label", { class: "f" }, "Turn budgets"),
              h("div", { class: "row2 tight" }, token, output, cost, seconds, concurrent),
              h("p", { class: "note" }, "A non-zero cost cap needs both rate fields; otherwise Core refuses before a paid provider call."),
              h("div", { class: "row2 tight" }, inputRate, outputRate, retry, failover),
              h("div", { class: "row2" }, h("button", { class: "ghost", onclick: () => clear(editor) }, "Cancel"),
                h("button", { class: "primary", onclick: () => void save() }, "Save profile"), editorStatus)));
        };
        const chosen = profiles.find((profile) => String(profile.id) === selected) ?? profiles[0] ?? {};
         const history = h("div", { class: "profile-history" });
         const showHistory = async () => {
           try {
             const out = await this.api.get(`/api/profiles/history?id=${encodeURIComponent(String(chosen.id ?? ""))}`);
             const rows = (out.history ?? []) as any[];
             clear(history, rows.length ? h("div", { class: "confirm" }, h("strong", {}, "Saved profile revisions"),
               rows.slice(0, 12).map((row) => h("p", { class: "note" },
                 `r${row.revision ?? row.profile?.revision ?? "?"} · ${String(row.at ?? "").replace("T", " ").slice(0, 19)} · ` +
                 `${row.profile?.role ?? ""}, ${row.profile?.permission_ceiling ?? ""}, output ${row.profile?.output_budget ?? ""}`)),
               h("button", { class: "ghost", onclick: () => clear(history) }, "Hide history"))
               : h("p", { class: "note" }, "No vault-specific revisions yet. Editing a shipped default creates revision 2."));
           } catch (e) { clear(history, h("p", { class: "error" }, (e as Error).message)); }
         };
        clear(root,
          h("label", { class: "f" }, "Agent profile"),
          h("div", { class: "row2 tight" }, select,
            h("button", { class: "ghost", onclick: () => showEditor(chosen) }, "Edit…"),
            h("button", { class: "ghost", onclick: () => showEditor({ id: "", role: "research_helper",
              permission_ceiling: "consult", required_qualification: "screened", allowed_bundles: ["read"],
              route_policy: {}, output_budget: 1024, retry_policy: "bounded", failover_policy: "ask",
               concurrency_limit: 1 }, true) }, "New…"),
             h("button", { class: "ghost", onclick: () => void showHistory() }, "History…"), status),
          h("p", { class: "note" }, "Profiles set tool bundles, permission ceilings, route allow-lists, budgets and concurrency. " +
            "They narrow the selected agent only; they never grant it a new host or bypass a checkpoint."),
          Object.keys(active).length ? h("p", { class: "note" }, `Active profile runs: ${Object.entries(active).map(([id, n]) => `${id} (${n})`).join(", ")}.`) : null,
           editor, history);
      } catch (e) {
        clear(root, h("p", { class: "error" }, (e as Error).message));
      }
    };
    void reload();
    return root;
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
      s.representation_stale ? h("p", { class: "note locked" }, "Embedding representation changed; existing vectors are not used. Choose Embed all to build the reviewed representation.") : null,
      h("div", { class: "row2 tight" }, local, s.model && est.chunks ? embedAll : null, s.model ? measure : null, status),
      confirm, table, save,
      s.comparison ? h("p", { class: "note" }, `Measured ${String(s.comparison.at ?? "").slice(0, 10)} on ${s.comparison.questions} questions; vectors joined ${s.comparison.vectors_contributed} answers. Turn them on only where they help.`) : null);
  }

  /** Requirements Addendum R17: service models, slots 4-7 - each one kind of job with its
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
          const contract = s.adapter && typeof s.adapter === "object" ? s.adapter : {};
          const contractLabel = !s.model ? "" : contract.adapter?.id
            ? ` · ${String(contract.adapter.id).replace(/_/g, " ")} · ${contract.status ?? "unreviewed"}`
            : " · no reviewed service contract";
          const test = async () => {
            status.className = "note inline";
            status.textContent = "Testing: one small call…";
            try {
              const t = await this.api.post("/api/services/test", { slot: s.slot });
              status.textContent = t.summary ?? (t.ok ? `Works: it read “${t.read}”.`
                : `Not working: ${t.error ?? `it read “${t.read}”`}`);
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
              contractLabel ? h("span", { class: "dim" }, contractLabel) : null,
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

  /** Personal endpoints are configuration, not vault data.  This deliberately
   * keeps endpoint/key binding, discovery, health probes and local limits in
   * the same visible place rather than making a model infer policy from a URL. */
  private hostRegistry(): HTMLElement {
    const root = h("section", { class: "host-registry" }, h("p", { class: "dim" }, "Loading personal hosts…"));
    const reload = async () => {
      try {
        const data = await this.api.get("/api/hosts");
        const hosts = (data.hosts ?? []) as any[];
        clear(root,
          h("label", { class: "f" }, "Personal model hosts"),
          h("p", { class: "note" }, "Hosts contain endpoints and rate limits, never credentials. " +
            "A custom endpoint is OpenAI-compatible in V2; test it before assigning it to an agent profile."),
          hosts.map((row) => this.hostCard(row, reload)),
          this.newHostCard(reload));
      } catch (e) {
        clear(root, h("p", { class: "error" }, (e as Error).message));
      }
    };
    void reload();
    return root;
  }

  private hostCard(row: any, reload: () => Promise<void>): HTMLElement {
    const title = h("strong", {}, String(row.display_name ?? row.id));
    const status = h("span", { class: "note inline", role: "status" });
    const detail = row.health?.detail ? ` · ${row.health.detail}` : "";
    const health = h("span", { class: `note inline ${row.health?.status === "ready" ? "ok" : row.health?.status === "error" ? "err" : ""}` },
      row.health?.status ? `${row.health.status}${detail}` : "not tested");
    const model = h("input", { type: "text", placeholder: "Model id for test or lead selection", "aria-label": `Model on ${row.display_name ?? row.id}` }) as HTMLInputElement;
    // An unavailable/deleted selected profile is represented as an empty role
    // by Core.  Treat that as absent here so an L1 probe never submits an
    // invalid blank role; the Core will still enforce the chosen profile when
    // a real agent turn starts.
    const probeRole = String(this.state().agent_profile_role || this.state().agent_profile || "lead");
    const discovered = h("div", { class: "row2 tight" });
    const enabled = h("input", { type: "checkbox", checked: !!row.enabled, "aria-label": `Enable ${row.display_name ?? row.id}` }) as HTMLInputElement;
    const name = h("input", { type: "text", value: String(row.display_name ?? ""), "aria-label": "Host display name" }) as HTMLInputElement;
    const protocol = h("select", { "aria-label": "Host protocol", disabled: !!row.seeded },
      h("option", { value: "openai", selected: row.protocol === "openai" }, "OpenAI-compatible"),
      h("option", { value: "anthropic", selected: row.protocol === "anthropic" }, "Anthropic")) as HTMLSelectElement;
    const base = h("input", { type: "text", value: String(row.base_url ?? ""), "aria-label": "Base URL", disabled: !!row.seeded }) as HTMLInputElement;
    const authRef = h("input", { type: "text", value: String(row.auth_ref ?? ""), "aria-label": "Credential reference", disabled: !!row.seeded }) as HTMLInputElement;
    const timeout = h("input", { type: "number", value: String(row.timeout ?? 120), min: 1, max: 3600, "aria-label": "Timeout seconds" }) as HTMLInputElement;
    const concurrency = h("input", { type: "number", value: String(row.concurrency_limit ?? 1), min: 1, max: 32, "aria-label": "Concurrent calls" }) as HTMLInputElement;
    const rate = h("input", { type: "number", value: String(row.rate_limit ?? 0), min: 0, "aria-label": "Calls per minute" }) as HTMLInputElement;
    const key = h("input", { type: "password", autocomplete: "off", placeholder: row.needs_key ? "Paste key for this host" : "No key configured", disabled: !row.needs_key,
      "aria-label": `Key for ${row.display_name ?? row.id}` }) as HTMLInputElement;
    const confirm = h("div");

    const save = async () => {
      status.textContent = "Saving host…";
      try {
        await this.api.post("/api/hosts", { host: {
          id: row.id, display_name: name.value.trim(), protocol: protocol.value,
          base_url: base.value.trim(), auth_ref: authRef.value.trim(), enabled: enabled.checked,
          timeout: Number(timeout.value || 120), concurrency_limit: Number(concurrency.value || 1),
          rate_limit: Number(rate.value || 0),
        } });
        status.textContent = "Saved.";
        await reload();
      } catch (e) { status.textContent = (e as Error).message; status.className = "note inline err"; }
    };
    const setKey = async (overwrite = false) => {
      try {
        const out = await this.api.post("/api/hosts/key", { host_id: row.id, key: key.value, overwrite });
        key.value = "";
        status.textContent = out.saved ? "Key saved." : "Key status updated.";
        clear(confirm);
      } catch (e) {
        const body = ((e as ApiError).body ?? {}) as Record<string, unknown>;
        if (body.confirm) {
          clear(confirm, h("div", { class: "confirm" }, String(body.confirm), h("div", { class: "row2" },
            h("button", { class: "ghost", onclick: () => clear(confirm) }, "Cancel"),
            h("button", { class: "primary", onclick: () => void setKey(true) }, "Replace key"))));
        } else status.textContent = (e as Error).message;
      }
    };
    const discover = async () => {
      status.textContent = "Discovering models…";
      try {
        const out = await this.api.get(`/api/models?provider=${encodeURIComponent(String(row.id))}`);
        const models = (out.models ?? []) as any[];
        clear(discovered, models.length ? models.slice(0, 40).map((entry) => h("button", { class: "ghost", onclick: () => { model.value = String(entry.id); } }, String(entry.id)))
          : h("span", { class: "note inline" }, out.error ?? "No models returned."));
        status.textContent = models.length ? `${models.length} models discovered.` : "No models returned.";
      } catch (e) { status.textContent = (e as Error).message; status.className = "note inline err"; }
    };
    const test = async () => {
      status.textContent = "Testing host…";
      try {
        const out = await this.api.post("/api/hosts/test", { host_id: row.id, model: model.value.trim() });
        const check = out.check ?? {};
        const category = String(check.failure_category ?? "");
        status.textContent = check.ok ? "Connection and model listing work."
          : category === "local_environment"
            ? "Local network policy blocked the Core — this is not a model result."
            : String(check.error ?? "Host test failed.");
        status.className = `note inline ${check.ok ? "ok" : "err"}`;
        await reload();
      } catch (e) { status.textContent = (e as Error).message; status.className = "note inline err"; }
    };
    const probe = async (checkpointId = "") => {
      if (!model.value.trim()) { status.textContent = "Enter or discover a model id first."; return; }
      status.textContent = "Preparing a one-call tool probe…";
      try {
        const out = await this.api.post("/api/qualification/run", {
          host_id: row.id, model: model.value.trim(), role: probeRole, level: "L1", checkpoint_id: checkpointId,
        });
        const run = out.run ?? {};
        status.textContent = run.outcome === "pass" ? `L1 tool-call probe passed for ${probeRole} (Screened).`
          : `L1 probe: ${run.detail ?? run.outcome ?? "did not pass"}`;
        status.className = `note inline ${run.outcome === "pass" ? "ok" : "err"}`;
        clear(confirm);
        await reload();
      } catch (e) {
        const body = ((e as ApiError).body ?? {}) as Record<string, any>;
        const checkpoint = body.checkpoint_record;
        if (checkpoint?.id) {
          status.textContent = "Approve this small paid account probe to run it.";
          clear(confirm, h("div", { class: "confirm" }, "This L1 probe makes one real tool-call request to this host.",
            h("div", { class: "row2" }, h("button", { class: "ghost", onclick: () => clear(confirm) }, "Cancel"),
              h("button", { class: "primary", onclick: async () => {
                await this.api.post("/api/checkpoints/resolve", { id: checkpoint.id, choice: "approve" });
                await probe(checkpoint.id);
              } }, "Approve probe"))));
        } else { status.textContent = (e as Error).message; status.className = "note inline err"; }
      }
    };
    const chooseLead = async (checkpointId = "", override = "") => {
      if (!model.value.trim()) { status.textContent = "Enter or discover a model id first."; return; }
      try {
        // Position 1 only: the Scribe and Clerk positions are kept (ROUTE-01).
        await this.api.post("/api/lead", { route: { host_id: row.id, model: model.value.trim() },
          ...(checkpointId ? { checkpoint_id: checkpointId } : {}), ...(override ? { override } : {}) });
        status.textContent = `${model.value} is the selected lead route.`;
        clear(confirm);
        await this.refresh();
      } catch (e) {
        const body = ((e as ApiError).body ?? {}) as Record<string, any>;
        const checkpoint = body.checkpoint_record;
        if (checkpoint?.id) {
          clear(confirm, h("div", { class: "confirm" }, (e as Error).message,
            h("p", { class: "note" }, "This route remains experimental. Approving records your route choice; it does not mark the model verified."),
            h("div", { class: "row2" }, h("button", { class: "ghost", onclick: () => clear(confirm) }, "Cancel"),
              h("button", { class: "primary", onclick: async () => {
                await this.api.post("/api/checkpoints/resolve", { id: checkpoint.id, choice: "approve" });
                await chooseLead(checkpoint.id);
              } }, "Use experimental lead"))));
        } else if (body.needs_override) {
          // Compatibility for a Core older than the checkpointed route API.
          const reason = h("input", { type: "text", value: "chosen by the person for this host", "aria-label": "Why use this unqualified lead" }) as HTMLInputElement;
          clear(confirm, h("div", { class: "confirm" }, (e as Error).message,
            h("p", { class: "note" }, "This records an explicit experimental-route choice; it does not mark the model verified."),
            reason, h("div", { class: "row2" }, h("button", { class: "ghost", onclick: () => clear(confirm) }, "Cancel"),
              h("button", { class: "primary", onclick: () => void chooseLead("", reason.value.trim() || "chosen by the person") }, "Use experimental lead"))));
        } else status.textContent = (e as Error).message;
      }
    };
    const remove = async () => {
      try { await this.api.post("/api/hosts/remove", { host_id: row.id }); await reload(); }
      catch (e) { status.textContent = (e as Error).message; }
    };
    return h("div", { class: "host-card" },
      h("div", { class: "row2 tight" }, h("span", { class: `dot ${row.enabled ? "" : "off"}` }), title,
        h("code", {}, String(row.id)), row.seeded ? h("span", { class: "dim" }, "preset") : null, health),
      h("div", { class: "host-grid" },
        h("label", { class: "f" }, "Display name", name), h("label", { class: "f" }, "Protocol", protocol),
        h("label", { class: "f" }, "Base URL", base), h("label", { class: "f" }, "Credential reference", authRef),
        h("label", { class: "f" }, "Timeout (s)", timeout), h("label", { class: "f" }, "Concurrent calls", concurrency),
        h("label", { class: "f" }, "Calls/minute (0 = no local cap)", rate)),
      h("label", { class: "opt" }, enabled, h("span", {}, "Enable this host")),
      h("div", { class: "row2" }, h("button", { class: "ghost", onclick: () => void save() }, "Save host"),
        !row.seeded ? h("button", { class: "ghost", onclick: () => void remove() }, "Remove") : null, status),
      row.needs_key ? h("div", { class: "row2" }, key, h("button", { class: "ghost", onclick: () => void setKey() }, "Save key")) : null,
      confirm,
      h("div", { class: "row2" }, model, h("button", { class: "ghost", onclick: () => void discover() }, "Discover models"),
        h("button", { class: "ghost", onclick: () => void test() }, "Test"),
         h("button", { class: "ghost", onclick: () => void probe() }, `L1 probe (${probeRole})`),
        h("button", { class: "primary", onclick: () => void chooseLead() }, "Use as lead")), discovered);
  }

  private newHostCard(reload: () => Promise<void>): HTMLElement {
    const id = h("input", { type: "text", placeholder: "e.g. studio-lan", "aria-label": "New host id" }) as HTMLInputElement;
    const label = h("input", { type: "text", placeholder: "Display name", "aria-label": "New host display name" }) as HTMLInputElement;
    const base = h("input", { type: "text", placeholder: "http://127.0.0.1:1234/v1", "aria-label": "New host base URL" }) as HTMLInputElement;
    const auth = h("input", { type: "text", placeholder: "Optional env/key reference", "aria-label": "New host credential reference" }) as HTMLInputElement;
    const status = h("span", { class: "note inline", role: "status" });
    const add = async () => {
      try {
        await this.api.post("/api/hosts", { host: { id: id.value.trim(), display_name: label.value.trim(),
          protocol: "openai", base_url: base.value.trim(), auth_ref: auth.value.trim(), enabled: true,
          timeout: 120, concurrency_limit: 1, rate_limit: 0 } });
        await reload();
      } catch (e) { status.textContent = (e as Error).message; status.className = "note inline err"; }
    };
    return h("div", { class: "host-card new-host" }, h("strong", {}, "Add OpenAI-compatible host"),
      h("div", { class: "host-grid" }, h("label", { class: "f" }, "Id", id), h("label", { class: "f" }, "Name", label),
        h("label", { class: "f" }, "Base URL", base), h("label", { class: "f" }, "Credential reference", auth)),
      h("div", { class: "row2" }, h("button", { class: "primary", onclick: () => void add() }, "Add host"), status));
  }

  /** A stable release can ship two L3-qualified candidates, but an account
   * tool probe and its spend decision still belong to the person. */
  private releaseLeadSetup(): HTMLElement {
    const root = h("section", { class: "release-leads" });
    void this.api.get("/api/release-leads").then((data) => {
      const choices = (data.choices ?? []) as any[];
      if (!choices.length) { clear(root); return; }
      clear(root, h("label", { class: "f" }, "First-run verified leads"),
        choices.map((choice) => {
          const key = h("input", { type: "password", autocomplete: "off", placeholder: choice.key?.saved ? "Key already available" : "Provider key", disabled: !choice.available || !!choice.key?.saved,
            "aria-label": `Key for ${choice.model}` }) as HTMLInputElement;
          const status = h("span", { class: "note inline", role: "status" });
          let keySaved = !!choice.key?.saved;
          const pick = async (checkpointId = "") => {
            try {
              const out = await this.api.post("/api/release-leads/select", { id: choice.id,
                key: keySaved ? "" : key.value, checkpoint_id: checkpointId });
              keySaved = true;
              status.textContent = out.selected ? `${choice.model} is ready as lead.` : String(out.reason ?? "Probe did not pass.");
              if (out.selected) await this.refresh();
            } catch (e) {
              const body = ((e as ApiError).body ?? {}) as Record<string, any>;
              const checkpoint = body.checkpoint_record;
              if (checkpoint?.id) {
                status.textContent = "Approve the small account probe to continue.";
                clear(actions, h("button", { class: "primary", onclick: async () => {
                  await this.api.post("/api/checkpoints/resolve", { id: checkpoint.id, choice: "approve" });
                  await pick(checkpoint.id);
                } }, "Approve account probe"));
              } else status.textContent = (e as Error).message;
            }
          };
          const actions = h("div", { class: "row2" });
          const label = choice.available ? "Connect and probe" : "Awaiting release qualification";
          clear(actions, choice.available ? h("button", { class: "primary", onclick: () => void pick() }, label) : null);
          return h("div", { class: "host-card release-lead" }, h("strong", {}, `${choice.provider} · ${choice.model}`),
            h("p", { class: "note" }, choice.available ? (choice.reason ?? "") : `Unavailable: ${choice.reason ?? choice.qualification}`),
            choice.available && !keySaved ? key : null, actions, status);
        }));
    }).catch((e) => clear(root, h("p", { class: "error" }, (e as Error).message)));
    return root;
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
