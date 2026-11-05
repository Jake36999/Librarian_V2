import type { Api } from "./api";
import { clear, h } from "./dom";

export const COMMANDS: Record<string, string> = {
  settings: "Open Settings", search: "Focus Search", staging: "Open Staging",
  sessions: "Open Sessions", checkpoints: "Open Checkpoints", intake: "Set up sources for this library",
  "clear-enrichment-backlog": "Process enrichment backlog", "deep-read-staged": "Deep-read staged sources",
  "review-conversation": "Suggest sources from this conversation", "review-due": "Review due concepts",
  "weekly-review": "Draft weekly pursuit review", approved: "Process approved sources",
  retry: "Retry steps waiting for a model", resume: "Resume interrupted batch", stop: "Stop after current stage",
};

export function preference(key: string, fallback = ""): string {
  try { return localStorage.getItem("librarian.ui." + key) ?? fallback; } catch { return fallback; }
}
export function remember(key: string, value: string): void {
  localStorage.setItem("librarian.ui." + key, value);
}

export function shortcutPage(native: boolean, open: (id: string) => void, api: Api, state: Record<string, any>): HTMLElement {
  const panel = h("div"), status = h("p", {role:"status"});
  const options = Array.from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789");
  const controls = new Map<string,{hint:HTMLElement;button:HTMLButtonElement}>();
  const explain = (id: string, text: string, available = true) => {
    const control = controls.get(id)!;
    control.hint.textContent = text; control.button.disabled = !available;
  };
  const row = (id: string, label: string) => {
    const binding = h("select", {"aria-label": "Shortcut for " + label},
      h("option", {value:""}, "Unassigned"), options.map(key => h("option", {value:key}, "Alt + Shift + " + key))) as HTMLSelectElement;
    binding.value = preference("key." + id);
    binding.onchange = () => {
      const conflict = binding.value && Object.keys(COMMANDS).find(other => other !== id && preference("key." + other) === binding.value);
      if (conflict) { status.textContent = "Already assigned to " + COMMANDS[conflict]; binding.value = preference("key." + id); return; }
      try { remember("key." + id, binding.value); status.textContent = "Shortcut saved."; }
      catch { status.textContent = "Could not save this browser preference."; binding.value = preference("key." + id); }
    };
    const hint = h("small"), button = h("button", {class:"ghost", onclick:(e: Event) => {
      e.stopPropagation(); open(id);
    }}, "Open") as HTMLButtonElement;
    controls.set(id,{hint,button});
    return h("div", {class:"settings-role"}, h("div",{},h("strong", {}, label),hint), native ? null : binding,button);
  };
  clear(panel, h("p", {}, native ? "Assign keys in Obsidian Settings → Hotkeys. Search for Librarian."
    : "Shortcuts apply to this browser address. Select Unassigned to clear a binding. Workflow shortcuts open the action for review."),
    status, Object.entries(COMMANDS).map(([id,label]) => row(id,label)));
  const batchKeys = ["approved","retry","resume","stop"];
  batchKeys.forEach(id=>explain(id,"Checking this library’s queue…",false));
  void api.tool("batch_status",{}).then(b => {
    if (b.error) throw Error();
    const running = b.status === "running";
    explain("approved", `${b.waiting ?? 0} approved sources waiting.`, !running && b.waiting > 0);
    explain("retry", `${b.waiting_on_model ?? 0} sources waiting for a model.`, !running && b.waiting_on_model > 0);
    const resume = ["failed","cancelled","interrupted"].includes(b.status) && b.items?.some((i:any)=>i.status==="processing");
    explain("resume",resume ? "Unfinished run: " + b.run : "No interrupted batch to resume.",!!resume);
    explain("stop",running ? "Active batch: " + b.run : "No batch running.",running);
  }).catch(()=>batchKeys.forEach(id=>explain(id,"Queue status unavailable.",false)));
  explain("review-conversation",state.session?.session ? "Conversation: " + state.session.session : "Start a conversation first.",!!state.session?.session);
  explain("weekly-review","Choose the pursuit in the action panel before starting.");
  void api.tool("understanding_due",{}).then(out=>{
    if (Array.isArray(out.due)) explain("review-due",`${out.due.length} due review tasks. Opens up to five parked sessions and skips existing reviews.`,out.due.length > 0);
  }).catch(()=>explain("review-due","Due count unavailable."));
  for (const [id,status] of [["deep-read-staged","staged"],["clear-enrichment-backlog","queued"]]) {
    void api.tool("staging_list",{kind:"source",status,limit:1}).then(out=>{
      if (typeof out.total === "number") explain(id,`${out.total} sources in the ${status} queue. Review the action before starting.`);
    }).catch(()=>explain(id,"Queue count unavailable."));
  }
  return panel;
}
