// The composer's paperclip: attach a file from disk into the vault (Inbox/,
// where a person would otherwise drop it by hand), or link a note or folder
// already there. Either way, a reference lands in the message so the
// librarian knows what it's for - a plain path in backticks for a folder or a
// fresh attachment (there's no note to open yet), a [[wikilink]] for a note
// that already exists.

import type { Api } from "./api";
import type { Popover } from "./panels";
import { clear, h } from "./dom";

export class AttachPanel {
  private browsing = "";
  private status = h("p", { class: "dim" });
  private fileInput = h("input", { type: "file", hidden: true,
    "aria-label": "Choose a file to attach" }) as HTMLInputElement;

  constructor(private pop: Popover, private api: Api, private insert: (text: string) => void,
              private onFileAttached: (file: { name: string }, raw: string) => void = () => {}) {
    this.fileInput.addEventListener("change", () => void this.chosen());
    document.body.append(this.fileInput);
  }

  /** Called each time the popover opens: start back at the vault root. */
  render(): void {
    this.browsing = "";
    void this.paint();
  }

  private async chosen(): Promise<void> {
    const file = this.fileInput.files?.[0];
    this.fileInput.value = "";
    if (!file) return;
    clear(this.status, `Attaching ${file.name}…`);
    try {
      const out = await this.api.attach(file);
      const raw = `\`${out.path}\``;
      this.insert(raw);
      this.onFileAttached(file, raw);
      clear(this.status, "");
    } catch (e) {
      clear(this.status, h("span", { class: "error" }, `Could not attach ${file.name}: ${(e as Error).message}`));
    }
  }

  private item(label: string, action: () => void): HTMLElement {
    return h("button", { class: "menuitem", role: "menuitem", onclick: action }, label);
  }

  private async paint(): Promise<void> {
    const folder = h("div", {}, h("p", { class: "dim" }, "Loading…"));
    clear(this.pop.el,
      this.item("📎 Attach a file from this computer", () => { this.pop.show(false); this.fileInput.click(); }),
      this.status,
      h("h4", { class: "gap" }, "Link a note or folder"),
      folder);
    try {
      const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(this.browsing)}`);
      const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
      clear(folder,
        h("div", { class: "folder-path" }, `/${listing.dir}`),
        up !== null ? this.item(`↑ ${up ? up.split("/").pop() : "the vault"}`,
          () => { this.browsing = up; void this.paint(); }) : null,
        listing.dir ? this.item("Link this folder", () => { this.pop.show(false); this.insert(`\`${listing.dir}/\``); }) : null,
        (listing.entries as any[]).map((e: any) => e.kind === "dir"
          ? this.item(`${e.name}/`, () => { this.browsing = e.path; void this.paint(); })
          : this.item(e.name, () => { this.pop.show(false); this.insert(`[[${e.name}]]`); })),
        listing.entries.length ? null : h("p", { class: "dim" }, "No notes here."));
    } catch (e) {
      clear(folder, h("p", { class: "error" }, (e as Error).message));
    }
  }
}
