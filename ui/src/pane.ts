// The document pane beside the chat: the session's plan, or a vault note
// rendered as Markdown. The ⋮ menu switches to the plan, reopens a recent
// note, browses the vault's folders, or renames/moves the open note. Links
// inside a note open here too.

import type { Api } from "./api";
import { clear, h } from "./dom";
import { render } from "./markdown";

const RECENT = 8;

export class DocPane {
  readonly el = h("aside", { class: "lib-pane", "aria-label": "Document" });
  private crumbs = h("div", { class: "pane-crumbs" });
  private menuButton = h("button", { class: "icon-btn", title: "Plan, recent notes and folders",
    "aria-label": "Documents menu", "aria-haspopup": "true", "aria-expanded": "false" }, "⋮");
  private menu = h("div", { class: "pane-menu", hidden: true, role: "menu" });
  private body = h("div", { class: "pane-body" });
  private recent: { path: string; name: string }[] = [];
  private current: { kind: "plan" } | { kind: "agenda" } | { kind: "doc"; path: string; name: string } = { kind: "plan" };
  private browsing = "";

  /** `onMoved`: a note was renamed, so links to it elsewhere (the chat) can follow.
   *  `currentProject`: the open session's pursuit, if any - drives the ⋮ menu's Desk
   *  section and which pursuit a note opened here is touched against. */
  constructor(private api: Api, private plan: HTMLElement, private vaultName: () => string,
              private onClose: () => void,
              private onMoved: (oldName: string, newName: string) => void = () => undefined,
              private currentProject: () => string = () => "",
              private currentSession: () => string = () => "") {
    this.menuButton.onclick = () => this.toggleMenu();
    this.el.append(
      h("div", { class: "pane-head" }, this.crumbs,
        h("div", { class: "pane-actions" }, this.menuButton,
          h("button", { class: "icon-btn", title: "Close the pane", "aria-label": "Close the pane",
            onclick: () => this.onClose() }, "✕")),
        this.menu),
      this.body);
    document.addEventListener("click", (e) => {
      if (!this.menu.hidden && !e.composedPath().includes(this.menu) && !e.composedPath().includes(this.menuButton)) {
        this.showMenu(false);
      }
    });
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") this.showMenu(false); });
    this.showPlan();
  }

  get showingPlan(): boolean { return this.current.kind === "plan"; }

  showPlan(): void {
    this.current = { kind: "plan" };
    clear(this.crumbs, h("span", { class: "crumb-here" }, "Plan"),
      h("span", { class: "dim" }, " · the session this chat is working in"));
    clear(this.body, this.plan);
    this.body.scrollTop = 0;
  }

  /** "This week": every open, dated task across the vault, computed fresh -
   *  no daemon, nothing kept in sync (Co-work Roadmap 2C). */
  async showAgenda(): Promise<void> {
    this.current = { kind: "agenda" };
    clear(this.crumbs, h("span", { class: "crumb-here" }, "This week"),
      h("span", { class: "dim" }, " · open, dated tasks across the vault"));
    clear(this.body, h("p", { class: "dim pad" }, "Loading…"));
    try {
      const out = await this.api.tool("agenda", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const groups: [string, string][] = [["overdue", "Overdue"], ["today", "Today"],
        ["this_week", "This week"], ["later", "Later"], ["undated", "No date"]];
      const rows = (tasks: { note: string; path: string; text: string; due: string | null }[]) =>
        h("ul", {}, tasks.map((t) => h("li", {},
          h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); void this.open(t.path); } }, t.note),
          ": ", t.text, t.due ? h("small", {}, ` 📅 ${t.due}`) : null)));
      const sections = groups.map(([key, label]) => {
        const tasks = (out[key] ?? []) as { note: string; path: string; text: string; due: string | null }[];
        return tasks.length ? h("section", {}, h("h4", {}, `${label} (${tasks.length})`), rows(tasks)) : null;
      });
      const empty = groups.every(([key]) => !(out[key] ?? []).length);
      clear(this.body, h("div", { class: "pad agenda" },
        empty ? h("p", { class: "dim" }, "Nothing open with a checkbox anywhere in the vault.") : sections));
    } catch (e) {
      clear(this.body, h("div", { class: "pad" }, h("p", { class: "error" }, (e as Error).message)));
    }
    this.body.scrollTop = 0;
  }

  /** A vault path (with or without .md) or a bare note name. */
  async open(target: string): Promise<void> {
    clear(this.body, h("p", { class: "dim pad" }, `Opening ${target}…`));
    let doc: any;
    try {
      doc = await this.api.get(`/api/file?path=${encodeURIComponent(target)}`);
    } catch (e) {
      clear(this.crumbs, h("span", { class: "crumb-here" }, target));
      clear(this.body, h("div", { class: "pad" }, h("p", { class: "error" }, (e as Error).message),
        h("p", { class: "dim" }, "Names are exact. Browse with ⋮, or ask the librarian for the path.")));
      return;
    }
    this.current = { kind: "doc", path: doc.path, name: doc.name };
    this.recent = [{ path: doc.path, name: doc.name }, ...this.recent.filter((r) => r.path !== doc.path)].slice(0, RECENT);
    const project = this.currentProject();
    if (project) this.api.tool("desk_touch", { project, note: doc.name }).catch(() => undefined);
    this.paintCrumbs(doc.path);
    const rendered = render(doc.text, (t) => void this.open(t), { frontmatter: true });
    // A note that opens with its own title heading keeps it as the title.
    const own = Array.from(rendered.children).find((el) => !el.matches("table.props"));
    const titled = own?.tagName === "H2" && own.textContent?.trim().toLowerCase() === String(doc.name).toLowerCase();
    if (titled) own!.remove();
    clear(this.body, h("article", { class: "doc" }, h("h1", { class: "doc-title" }, doc.name), rendered));
    this.body.scrollTop = 0;
  }

  private paintCrumbs(path: string): void {
    const parts = path.split("/");
    const out: (Node | string)[] = [];
    parts.forEach((part, i) => {
      out.push(h("span", { class: "sep" }, "/"));
      if (i === parts.length - 1) {
        out.push(h("span", { class: "crumb-here" }, part));
      } else {
        const dir = parts.slice(0, i + 1).join("/");
        out.push(h("button", { class: "crumb-dir", title: `Browse ${dir}`,
          onclick: () => { this.browsing = dir; this.showMenu(true); } }, part));
      }
    });
    clear(this.crumbs, out);
  }

  // -- the ⋮ menu ------------------------------------------------------------
  private toggleMenu(): void {
    if (this.menu.hidden && this.current.kind === "doc") {
      this.browsing = this.current.path.split("/").slice(0, -1).join("/");
    }
    this.showMenu(this.menu.hidden !== false);
  }

  private showMenu(on: boolean): void {
    this.menu.hidden = !on;
    this.menuButton.setAttribute("aria-expanded", String(on));
    if (on) void this.paintMenu();
  }

  private async paintMenu(): Promise<void> {
    const item = (label: string, small: string, action: () => void, cls = "") => h("button", {
      class: `menuitem ${cls}`, role: "menuitem", onclick: action }, label, small ? h("small", {}, small) : null);
    const folder = h("div", { class: "pane-folder" }, h("p", { class: "dim" }, "Loading…"));
    const vault = this.vaultName();
    const obsidian = this.current.kind === "doc" && vault
      ? `obsidian://open?vault=${encodeURIComponent(vault)}&file=${encodeURIComponent(this.current.path)}` : "";
    const doc = this.current.kind === "doc" ? this.current : null;
    const project = this.currentProject();
    const desk = h("div", { class: "pane-desk" }, h("p", { class: "dim" }, "Loading…"));
    const session = this.currentSession();
    const lenses = h("div", { class: "pane-lenses" }, h("p", { class: "dim" }, "Loading…"));
    clear(this.menu,
      item("Plan", "the session this chat is working in", () => { this.showMenu(false); this.showPlan(); }),
      item("This week", "open, dated tasks across the vault", () => { this.showMenu(false); void this.showAgenda(); }),
      obsidian ? h("a", { class: "menuitem", href: obsidian, role: "menuitem" }, "Open this note in Obsidian") : null,
      doc ? item("Rename or move…", "links to it across the vault follow", () => this.paintMove(doc), "move") : null,
      project ? h("h4", {}, `Desk — ${project}`) : null,
      project ? desk : null,
      session ? h("h4", {}, "Lenses — this thread") : null,
      session ? lenses : null,
      this.recent.length ? h("h4", {}, "Recent") : null,
      this.recent.map((r) => item(r.name, r.path, () => { this.showMenu(false); void this.open(r.path); })),
      h("h4", {}, "Browse"), folder);
    (this.menu.querySelector("button") as HTMLElement | null)?.focus();
    try {
      const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(this.browsing)}`);
      const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
      clear(folder,
        h("div", { class: "folder-path" }, `/${listing.dir}`),
        up !== null ? item(`↑ ${up ? up.split("/").pop() : "the vault"}`, "", () => { this.browsing = up; void this.paintMenu(); }, "dir up") : null,
        (listing.entries as any[]).map((e) => e.kind === "dir"
          ? item(`${e.name}/`, "", () => { this.browsing = e.path; void this.paintMenu(); }, "dir")
          : item(e.name, "", () => { this.showMenu(false); void this.open(e.path); }, "file")),
        listing.entries.length ? null : h("p", { class: "dim" }, "No notes here."));
    } catch (e) {
      this.browsing = "";
      clear(folder, h("p", { class: "error" }, (e as Error).message));
    }
    if (project) void this.paintDesk(desk, project, item, doc);
    if (session) void this.paintLenses(lenses, session);
  }

  /** Accepted lenses for this thread: the adopted ones (each an instruction
   *  in the model's prompt until dropped), then the rest with what each
   *  catches and when not to use it. Adopting is the person's choice - this
   *  pane calls as the person - and a thread holds at most three. */
  private async paintLenses(host: HTMLElement, session: string): Promise<void> {
    try {
      const [status, out] = await Promise.all([
        this.api.tool("session_status", {}, session),
        this.api.tool("lens_suggest", { limit: 12 }, session)]);
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const adopted = new Set<string>((status.lenses ?? []) as string[]);
      const all = (out.lenses ?? []) as { id: string; name: string; source: string; catches: string; not_when: string }[];
      const toggle = (id: string) => async () => {
        try {
          const r = await this.api.tool(adopted.has(id) ? "lens_drop" : "lens_adopt", { lens_id: id }, session);
          if (r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? r.error));
        } catch (e) { clear(host, h("p", { class: "error" }, (e as Error).message)); return; }
        void this.paintLenses(host, session);
      };
      clear(host, all.length
        ? all.sort((a, b) => Number(adopted.has(b.id)) - Number(adopted.has(a.id))).map((l) =>
            h("div", { class: "menuitem desk-row", title: [l.catches && `Catches: ${l.catches}`, l.not_when && `Not when: ${l.not_when}`].filter(Boolean).join("\n") },
              h("span", { class: "lens-name" }, l.name, h("small", { title: l.source },
                ` · ${l.source.length > 36 ? `${l.source.slice(0, 35)}…` : l.source}`)),
              h("button", { class: "icon-btn pin-toggle", title: adopted.has(l.id) ? "Drop from this thread" : "Adopt for this thread",
                "aria-label": adopted.has(l.id) ? `Drop ${l.name}` : `Adopt ${l.name}`, onclick: () => void toggle(l.id)() },
                adopted.has(l.id) ? "✓" : "+")))
        : h("p", { class: "dim" }, "No accepted lenses yet - accept one in Staging, or a lens pack in Settings → Library."));
    } catch (e) {
      clear(host, h("p", { class: "error" }, (e as Error).message));
    }
  }

  private async paintDesk(desk: HTMLElement, project: string,
                          item: (label: string, small: string, action: () => void, cls?: string) => HTMLElement,
                          doc: { path: string; name: string } | null): Promise<void> {
    try {
      const out = await this.api.tool("desk_show", { project });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const working = (out.working_set ?? []) as { note: string; pinned: boolean; why: string }[];
      const pinned = new Set(working.filter((r) => r.pinned).map((r) => r.note));
      const togglePin = (name: string) => async () => {
        try {
          await this.api.tool(pinned.has(name) ? "desk_unpin" : "desk_pin", { project, note: name });
        } catch { /* best-effort */ }
        void this.paintDesk(desk, project, item, doc);
      };
      clear(desk,
        doc ? item(pinned.has(doc.name) ? `📌 Unpin "${doc.name}"` : `📌 Pin "${doc.name}" to the desk`,
          "", () => void togglePin(doc.name)(), "pin") : null,
        working.length ? working.map((r) => h("div", { class: "menuitem desk-row" },
          h("button", { class: "wl", onclick: () => { this.showMenu(false); void this.open(r.note); } }, r.note),
          h("small", {}, r.why),
          h("button", { class: "icon-btn pin-toggle", title: r.pinned ? "Unpin" : "Pin",
            "aria-label": r.pinned ? `Unpin ${r.note}` : `Pin ${r.note}`, onclick: () => void togglePin(r.note)() },
            r.pinned ? "📌" : "📍")))
          : h("p", { class: "dim" }, "Nothing on the desk yet - open or pin a note."));
    } catch (e) {
      clear(desk, h("p", { class: "error" }, (e as Error).message));
    }
  }

  // -- rename or move ----------------------------------------------------------
  private paintMove(doc: { path: string; name: string }): void {
    const here = doc.path.split("/").slice(0, -1).join("/");
    const name = h("input", { type: "text", id: "lib-mv-name", value: doc.name,
      "aria-label": "New name" }) as HTMLInputElement;
    const folder = h("input", { type: "text", id: "lib-mv-folder", value: here,
      "aria-label": "Folder", placeholder: "the vault's top level" }) as HTMLInputElement;
    const picker = h("div", { class: "picker" });
    const status = h("div", { role: "status" });
    let picking = here;

    const paintPicker = async (): Promise<void> => {
      clear(picker, h("p", { class: "dim" }, "Loading…"));
      try {
        const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(picking)}`);
        const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
        const go = (dir: string) => () => { picking = dir; folder.value = dir; void paintPicker(); };
        clear(picker,
          h("div", { class: "folder-path" }, `/${listing.dir}`),
          up !== null ? h("button", { class: "menuitem dir up", type: "button", onclick: go(up) },
            `↑ ${up ? up.split("/").pop() : "the vault"}`) : null,
          (listing.entries as any[]).filter((e) => e.kind === "dir").map((e) =>
            h("button", { class: "menuitem dir", type: "button", onclick: go(e.path) }, `${e.name}/`)));
      } catch (e) {
        clear(picker, h("p", { class: "error" }, (e as Error).message));
      }
    };

    const submit = async (): Promise<void> => {
      const newName = name.value.trim();
      const newFolder = folder.value.trim().replace(/^\/+|\/+$/g, "");
      const args: Record<string, string> = { name: doc.name };
      if (newName && newName !== doc.name) args.new_name = newName;
      if (newFolder !== here) args.new_folder = newFolder;
      if (!args.new_name && args.new_folder === undefined) {
        clear(status, h("p", { class: "error" }, "Nothing changed: give a new name or a different folder."));
        return;
      }
      clear(status, h("p", { class: "dim" }, "Moving…"));
      try {
        const out = await this.api.tool("note_move", args);
        if (out.error) throw new Error(String(out.detail ?? out.error));
        const moved = String(out.path);
        const movedName = moved.split("/").pop()!.replace(/\.md$/, "");
        const updated = (out.updated_links ?? []) as string[];
        this.recent = this.recent.filter((r) => r.path !== doc.path);
        this.showMenu(false);
        if (movedName !== doc.name) this.onMoved(doc.name, movedName);
        await this.open(moved);
        this.body.querySelector("article.doc")?.prepend(h("div", { class: "note moved", role: "status" },
          `Moved from ${doc.path}. `,
          updated.length ? h("details", {}, h("summary", {},
            `Updated links in ${updated.length} note${updated.length === 1 ? "" : "s"}.`),
            h("ul", {}, updated.map((p) => h("li", {}, p))))
            : "No other note linked to it."));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const onEnter = (e: Event) => { if ((e as KeyboardEvent).key === "Enter") void submit(); };
    name.addEventListener("keydown", onEnter);
    folder.addEventListener("keydown", onEnter);

    clear(this.menu, h("div", { class: "move-form" },
      h("h4", {}, "Rename or move"),
      h("label", { class: "f", for: "lib-mv-name" }, "Name"), name,
      h("label", { class: "f", for: "lib-mv-folder" }, "Folder"), folder,
      picker,
      h("div", { class: "row2" },
        h("button", { class: "primary", type: "button", onclick: () => void submit() }, "Move"),
        h("button", { class: "ghost", type: "button", onclick: () => void this.paintMenu() }, "Cancel")),
      status,
      h("p", { class: "note" }, "Every [[link]] to this note by its name is updated to match.")));
    name.focus();
    name.select();
    void paintPicker();
  }
}
