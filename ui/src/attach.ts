// The composer's paperclip: one menu for everything a person brings to the librarian.
//   - attach a file from this computer (it lands in Inbox/, where a person would otherwise drop
//     it by hand; its path goes into the message),
//   - link a note or folder already in the library (the library opens in the pane beside the
//     chat, with a hint, and a click on a file adds it to the message: there is one place to
//     navigate, not two),
//   - open the skill registry (skills, "/" commands and the docs of installed plugins),
//   - run a workflow (the fixed jobs a person starts: starting one is the permission for its steps).
// A reference lands in the message so the librarian knows what it is for: a plain path in
// backticks for a folder or a fresh attachment, a [[wikilink]] for a note that exists.

import type { Api } from "./api";
import type { Popover } from "./panels";
import { clear, h } from "./dom";

export interface AttachHooks {
  /** Open the library in the pane to pick one file for the chat. */
  pickFile(): void;
  /** Open the skill registry in the pane. */
  openRegistry(): void;
  /** The workflow section, built from the Core's current list; `rerender` returns to this menu. */
  workflows(rerender: () => void): HTMLElement[];
}

export class AttachPanel {
  private status = h("p", { class: "dim" });
  private fileInput = h("input", { type: "file", hidden: true,
    "aria-label": "Choose a file to attach" }) as HTMLInputElement;

  constructor(private pop: Popover, private api: Api, private insert: (text: string) => void,
              private onFileAttached: (file: { name: string }, raw: string) => void = () => {},
              private hooks: AttachHooks = { pickFile() {}, openRegistry() {}, workflows: () => [] }) {
    this.fileInput.addEventListener("change", () => void this.chosen());
    document.body.append(this.fileInput);
  }

  /** MF-008: the hidden picker lives on <body>; a remount must not leave it. */
  dispose(): void { this.fileInput.remove(); }

  /** Called each time the popover opens. */
  render(): void { this.paint(); }

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

  private item(label: string, hint: string, action: () => void): HTMLElement {
    return h("button", { class: "menuitem", role: "menuitem", onclick: action },
      label, hint ? h("small", {}, hint) : null);
  }

  private paint(): void {
    clear(this.pop.el,
      this.item("📎 Attach a file from this computer", "Copies it into this library's Inbox and adds its path to your message.",
        () => { this.pop.show(false); this.fileInput.click(); }),
      this.item("🔗 Link a note or folder from the library", "Opens the library beside the chat: pick a file to add to the chat.",
        () => { this.pop.show(false); this.hooks.pickFile(); }),
      this.status,
      this.item("Open skill registry", "Skills, “/” commands and where to read about installed plugins.",
        () => { this.pop.show(false); this.hooks.openRegistry(); }),
      ...this.hooks.workflows(() => this.paint()));
  }
}
