import type { Api } from "./api";
import { h, clear } from "./dom";
import { preference, remember } from "./commands";

interface Setup {
  name: string;
  context: string;
  length: string;
  stance: string;
  tiers: {provider: string; model: string; host_id?: string}[];
}

export function researchSetups(api: Api, state: () => Record<string, any>, refresh: () => Promise<void>): HTMLElement {
  const root = h("details", {}, h("summary", {}, "Named research presets"));
  const list = h("div"), preview = h("div"), status = h("p", {role:"status"});
  const name = h("input",{type:"text","aria-label":"New preset name",placeholder:"Preset name"}) as HTMLInputElement;
  const read = (): Setup[] => JSON.parse(preference("research-setups","[]"));
  const snapshot = (title: string): Setup => {
    const s = state();
    return {name:title, context:s.working_context ?? "", length:s.reply_length ?? "long", stance:s.stance ?? "answer",
      tiers:(s.tiers ?? []).map((t: Setup["tiers"][number]) => ({provider:t.provider,model:t.model,...(t.host_id ? {host_id:t.host_id} : {})}))};
  };
  function inspect(setup: Setup) {
    const now = snapshot(""), library = String(state().vault_path ?? state().vault);
    const roleNames = ["Lead","Notes","Small tasks"];
    const format = (s: Setup) => s.tiers.map((r,i) => roleNames[i] + ": " + (r.host_id ?? r.provider) + " / " + r.model).join("; ") || "No explicit roles";
    const apply = (roles: boolean) => async (e: Event) => {
      const button = e.currentTarget as HTMLButtonElement;
      button.disabled = true;
      try {
        if (library !== String(state().vault_path ?? state().vault)) throw Error("Library changed. Preview the preset again.");
        if (roles) await api.post("/api/tiers",{tiers:setup.tiers});
        else await api.post("/api/context",{working_context:setup.context,reply_length:setup.length,stance:setup.stance});
        await refresh();
        status.textContent = (roles ? "Model roles" : "Chat preferences") + " applied to " + (state().vault_name || state().vault) + ".";
        inspect(setup);
      } catch (err) { status.textContent = (err as Error).message; button.disabled = false; }
    };
    clear(preview,h("h4",{},setup.name + " → " + (state().vault_name || state().vault)),
      h("p",{}, "Saved chat instructions: ",now.context || "(empty)"," → ",setup.context || "(empty)"),
      h("p",{},now.length+" / "+now.stance+" → "+setup.length+" / "+setup.stance),
      h("button",{class:"ghost",onclick:apply(false)},"Apply chat preferences"),
      h("p",{},format(now)+" → "+format(setup)),h("small",{},"Role changes also update defaults for libraries without their own choices."),
      h("button",{class:"ghost",onclick:apply(true)},"Apply model roles"));
  }
  function paint() {
    try {
      clear(list,read().map(setup => h("div",{class:"row2"},h("strong",{},setup.name),
        h("button",{class:"ghost",onclick:()=>inspect(setup)},"Preview"),
        h("button",{class:"ghost",onclick:()=>{remember("research-setups",JSON.stringify(read().filter(row=>row.name!==setup.name)));clear(preview);paint();}},"Remove preset"))));
    } catch {status.textContent = "Saved presets could not be read.";}
  }
  root.append(h("p",{},"Save this library’s current chat instructions, length, stance and model roles in this browser. Preview changes before applying them to another library at this address."),
    name,h("button",{class:"ghost",onclick:()=>{
      try {
        const rows=read(), title=name.value.trim();
        if(!title || rows.some(r=>r.name===title)) {status.textContent="Enter a unique preset name.";return;}
        remember("research-setups",JSON.stringify([...rows,snapshot(title)]));name.value="";status.textContent="Preset saved.";paint();
      } catch {status.textContent="Could not save the preset in this browser.";}
    }},"Save current settings as preset"),list,preview,status);
  paint();return root;
}
