// Beside the chat: staging review (each draft beside its evidence), search, and
// a note reader. Every button here is the person's own decision, sent as a tool
// call at their tier.

import type { Api } from "./api";
import { clear, h } from "./dom";
import { render } from "./markdown";

// A model's `best_for`/`suggested_tier` are a clerk's first guess, not a
// measurement (see Note Content Model.md) - a person edits them here the
// same way they edit a drafted Bottom Line.
const BEST_FOR_TAGS = ["Talking_Fast", "Long_Conversations", "Small_Coding_Tasks",
  "Large_Coding_Tasks", "Long_Horizon_Tasks"];
const TIERS = ["Tier_1", "Tier_2", "Tier_3"];
const untag = (s: string) => s.replace(/_/g, " ");

// -- staging review ------------------------------------------------------------

export class Staging {
  readonly el = h("div", { class: "view staging" });
  private list = h("div", { class: "items", role: "listbox", "aria-label": "Staged items" });
  private detail = h("div", { class: "detail" });
  private kind = "source";
  private selected = "";
  // True right after a decision's outcome message is shown, until the person
  // opens something else or explicitly refreshes: an automatic reload (the
  // SSE echo of this same decision, or someone else's) must not wipe it.
  private detailLocked = false;

  constructor(private api: Api, private openNote: (name: string) => void) {
    const kinds = h("div", { class: "seg", role: "group", "aria-label": "Kind" });
    const paint = () => {
      clear(kinds, [["source", "Sources"], ["lens", "Lenses"], ["concept", "Concepts"]].map(([v, label]) =>
        h("button", { "aria-pressed": String(this.kind === v), onclick: () => { this.kind = v; paint(); void this.load(true); } }, label)));
      scan.style.display = this.kind === "concept" ? "" : "none";
    };
    const scan = h("button", { class: "ghost", title: "Scan recorded term usages for a term seen across several sources",
      onclick: async () => {
        clear(this.list, h("p", { class: "dim" }, "Scanning term usages…"));
        try {
          const out = await this.api.tool("concept_candidates", {});
          await this.load(true);
          const n = (out.staged ?? []).length;
          this.list.prepend(h("p", { class: "note" }, n ? `${n} new concept${n === 1 ? "" : "s"} staged.` : "Nothing new to stage."));
        } catch (e) {
          clear(this.list, h("p", { class: "error" }, (e as Error).message));
        }
      } }, "Scan for concepts");
    paint();
    this.el.append(h("div", { class: "view-head" }, h("strong", {}, "Staging review"), kinds,
      h("button", { class: "ghost", onclick: () => void this.load(true) }, "Refresh"), scan),
      h("div", { class: "split" }, this.list, this.detail));
  }

  /** `reset`: an explicit visit (opening the view, Refresh, switching kind) —
   * always shows the placeholder when nothing is selected. Left false, an
   * automatic reload (another surface's decision arriving over the event
   * stream) refreshes the list without wiping a just-shown outcome message. */
  async load(reset = false): Promise<void> {
    if (reset) this.detailLocked = false;
    clear(this.list, h("p", { class: "dim" }, "Loading…"));
    try {
      const out = await this.api.tool("staging_list", { kind: this.kind, status: "staged", limit: 50 });
      const items = (out.items ?? []) as any[];
      clear(this.list,
        h("p", { class: "dim" }, `${out.total ?? items.length} waiting`),
        items.length ? items.map((item) => h("button", {
          class: `item${item.id === this.selected ? " sel" : ""}`, role: "option",
          "aria-selected": String(item.id === this.selected), onclick: () => this.show(item.id),
        }, item.sensitivity === "review" ? h("span", { class: "flag", title: "sensitive: a person decides" }, "⚑ ") : null,
          item.name || item.id,
          h("small", {}, (item.kind === "lens"
            ? [item.source ? `from ${item.source}` : "", item.locator]
            : item.kind === "concept"
            ? [`${item.sources ?? 0} source${item.sources === 1 ? "" : "s"}`, `${item.usages ?? 0} usage${item.usages === 1 ? "" : "s"}`]
            : [item.topic, item.drafted ? "drafted" : item.reviewed ? "draft queued" : "no draft yet",
               item.deep_read ? `read ${item.deep_read}` : "", item.fit]).filter(Boolean).join(" · "))))
          : h("p", { class: "dim" }, "Nothing waiting."));
      if (!this.selected && !this.detailLocked) {
        clear(this.detail, h("p", { class: "dim" }, "Choose an item to see its draft beside its evidence."));
      }
    } catch (e) {
      clear(this.list, h("p", { class: "error" }, (e as Error).message));
    }
  }

  private async show(id: string): Promise<void> {
    this.selected = id;
    this.detailLocked = false;
    this.list.querySelectorAll(".item").forEach((b) => b.classList.remove("sel"));
    clear(this.detail, h("p", { class: "dim" }, "Loading…"));
    let item: any;
    try {
      item = await this.api.tool("staging_show", { item_id: id });
      if (item.error) throw new Error(String(item.detail ?? item.error));
    } catch (e) {
      clear(this.detail, h("p", { class: "error" }, (e as Error).message));
      return;
    }
    if (item.kind === "lens") return this.showLens(item);
    if (item.kind === "concept") return this.showConcept(item);
    const draft = item.review?.draft ?? {};
    const bottom = h("textarea", { class: "f", id: "lib-bl", placeholder: "One or two sentences: what this is, from the evidence." }) as HTMLTextAreaElement;
    bottom.value = draft.bottom_line ?? "";
    const solves = h("textarea", { class: "f short", id: "lib-solves", placeholder: "What problem it solves, for whom." }) as HTMLTextAreaElement;
    solves.value = draft.what_it_solves ?? "";
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)", "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    const isModel = item.source_kind === "model";
    const bestFor = new Set<string>((item.fields?.best_for ?? []) as string[]);
    let suggestedTier = (item.fields?.suggested_tier ?? "") as string;
    const bestForButtons = BEST_FOR_TAGS.map((tag) => {
      const btn = h("button", { type: "button", "aria-pressed": String(bestFor.has(tag)),
        onclick: () => {
          if (bestFor.has(tag)) bestFor.delete(tag); else bestFor.add(tag);
          btn.setAttribute("aria-pressed", String(bestFor.has(tag)));
        } }, untag(tag)) as HTMLButtonElement;
      return btn;
    });
    const tierButtons: HTMLButtonElement[] = TIERS.map((t) => h("button", {
      type: "button", "aria-pressed": String(suggestedTier === t),
      onclick: () => {
        suggestedTier = t;
        tierButtons.forEach((b, i) => b.setAttribute("aria-pressed", String(TIERS[i] === t)));
      } }, untag(t)) as HTMLButtonElement);
    const decide = (decision: string) => async () => {
      try {
        const out = await this.api.tool("staging_decide", { item_ids: [id], decision, reason: reason.value,
          bottom_line: bottom.value, what_it_solves: solves.value,
          ...(isModel ? { fields: { best_for: Array.from(bestFor), ...(suggestedTier ? { suggested_tier: suggestedTier } : {}) } } : {}) });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        const outcome = decision === "accept"
          ? (r.promotion && !r.promotion.catalogued ? `Accepted: ${r.promotion.status}.` : "Accepted and catalogued.")
          : decision === "reject" ? "Rejected." : "Deferred.";
        this.selected = "";
        await this.load();                                   // the list, without it
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" }, `${item.name}: ${outcome}`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const draftIt = async () => {
      clear(status, h("p", { class: "dim" }, "Asking the clerk for an unframed draft…"));
      try {
        const out = await this.api.tool("staging_review", { item_id: id });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        if (out.draft?.status === "queued") clear(status, h("p", { class: "dim" }, "Queued: no clerk model is available. Choose a tier 3 model, or run the clerk agent."));
        else await this.show(id);
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const readIt = async () => {
      clear(status, h("p", { class: "dim" }, "Reading the whole text, part by part…"));
      try {
        const out = await this.api.tool("deep_read", { item_id: id });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        await this.show(id);
        const lensNote = out.lenses_staged?.length
          ? ` ${out.lenses_staged.length} lens${out.lenses_staged.length === 1 ? "" : "es"} staged for review under Lenses.` : "";
        const waitNote = out.waiting_on_clerk
          ? ` ${out.waiting_on_clerk} part${out.waiting_on_clerk === 1 ? "" : "s"} waiting on a clerk model.` : "";
        this.detail.querySelector("[role=status]")?.replaceChildren(h("p", { class: "ok" },
          `Read ${out.read} of ${out.chunks} parts.${lensNote}${waitNote}`));
        void this.load();
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const dr = item.deep_read;
    const readCount = dr ? Object.keys(dr.read ?? {}).length : 0;
    const readLine = dr
      ? `Deep read: ${readCount} of ${dr.chunks} parts read${dr.lenses?.length ? `, ${dr.lenses.length} lens${dr.lenses.length === 1 ? "" : "es"} staged` : ""}.`
      : "Only the opening of this source has been read.";
    const sections = Object.entries((item.sections ?? {}) as Record<string, string>).filter(([, t]) => t);
    const queued = (item.review?.queued ?? []) as string[];
    const missing = (item.readiness ?? []) as string[];
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name),
        item.canonical_url ? h("a", { href: item.canonical_url, target: "_blank", rel: "noreferrer noopener" }, "source ↗") : null),
      item.sensitivity === "review" ? h("p", { class: "warn" }, "⚑ Marked sensitive: only a person accepts it, and only a person clears the mark.") : null,
      item.revision_of ? h("p", { class: "note" }, "A revision of an accepted note, ",
        h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); this.openNote(item.revision_of); } }, item.revision_of),
        ": its whole text read. Accepting merges its Claims and Evidence & Limits into that note (the previous text is kept on this item); rejecting leaves the note as it is.") : null,
      queued.length ? h("p", { class: "warn" },
        `⏳ Waiting on a clerk model for: ${queued.join(", ")}. Choose a tier 3 model under Model, `,
        "set [clerk] in the vault's config, or run the clerk agent, then “Redraft” below.") : null,
      (item.intake_notes ?? []).length ? h("p", { class: "note" }, `Intake could not read everything: ${(item.intake_notes as string[]).join("; ")}.`) : null,
      missing.length ? h("p", { class: "warn" }, `Still missing before this is catalogued fully: ${missing.join(", ")}.`) : null,
      h("div", { class: "columns" },
        h("div", {},
          h("label", { class: "f", for: "lib-bl" }, draft.bottom_line ? `Bottom Line (drafted by ${draft.model || "the clerk"}; edit it)` : "Bottom Line"),
          bottom,
          h("label", { class: "f", for: "lib-solves" }, "What it solves"), solves,
          isModel ? h("div", {},
            h("label", { class: "f" }, "Best for (a clerk's first guess; confirm or correct it)"),
            h("div", { class: "seg", role: "group", "aria-label": "Best for" }, bestForButtons),
            h("label", { class: "f" }, "Suggested tier (a first guess)"),
            h("div", { class: "seg", role: "group", "aria-label": "Suggested tier" }, tierButtons)) : null,
          (draft.dropped ?? []).length ? h("p", { class: "note" }, `Dropped from the draft as ungrounded: ${(draft.dropped as string[]).join("; ")}`) : null,
          reason,
          h("div", { class: "row2" },
            h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
            h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
            h("button", { class: "ghost", onclick: decide("defer") }, "Defer"),
            h("button", { class: "ghost push", onclick: draftIt }, draft.bottom_line ? "Redraft" : "Draft with the clerk")),
          h("div", { class: "row2" },
            h("span", { class: "note inline" }, readLine),
            !dr || readCount < dr.chunks
              ? h("button", { class: "ghost", onclick: readIt, title: "Claims and limits from every part, with pages; terms; and any reasoning stance the text teaches, staged as a lens" },
                  dr ? "Continue deep read" : "Deep read")
              : null),
          status),
        h("div", {},
          sections.length ? h("label", { class: "f" }, "What was read") : null,
          sections.length ? h("div", { class: "sections" }, sections.map(([heading, body]) =>
            h("section", {}, h("h4", {}, heading), render(body, this.openNote)))) : null,
          h("label", { class: "f" }, "Evidence"),
          h("pre", { class: "evidence" }, String(item.evidence_text ?? "")))));
  }

  private showLens(item: any): void {
    const p = { ...(item.proposal ?? {}), ...item };
    // B1: every field says where it came from - the source's own words, or
    // drafted (by the extraction model or a pack's author), or reworded by
    // you - so a drafted probe is never read as something the source said.
    const origin: Record<string, string> = p.provenance ?? {};
    const ORIGIN_LABEL: Record<string, string> = {
      source: "from the source", model: "drafted by the model", pack: "written by the pack's author",
      person: "edited by you", "model+source": "drafted by the model, each with a source quote",
      "pack+source": "written by the pack's author, each with a source quote" };
    const head = (label: string, field: string) => h("h4", {}, label,
      origin[field] ? h("span", { class: `origin origin-${origin[field].replace("+", "-")}` }, ORIGIN_LABEL[origin[field]] ?? origin[field]) : null);
    const list = (label: string, items: unknown, field = "") => (items as string[] | undefined)?.length
      ? h("div", {}, head(label, field), h("ul", {}, (items as string[]).map((t) => h("li", {}, t)))) : null;
    // attends_to and probes carry their own grounding quote (E2) - shown
    // beside the claim, not behind a link (E9), so accepting means seeing
    // the evidence, not trusting the label.
    // C4: a probe another part of the text answers says so, with that claim.
    const groundedList = (label: string, items: { what?: string; question?: string; because?: string;
                                                  confirmed_by?: { claim: string; locator?: string } }[] | undefined, field = "") =>
      items?.length
        ? h("div", {}, head(label, field), h("ul", {}, items.map((it) =>
            h("li", {}, it.what ?? it.question ?? "", it.because ? h("blockquote", { class: "lens-quote small" }, it.because) : null,
              it.confirmed_by ? h("p", { class: "note" }, "Answered elsewhere in the text: ", it.confirmed_by.claim,
                it.confirmed_by.locator ? ` (${it.confirmed_by.locator})` : "") : null))))
        : null;
    const quotes: { quote: string; locator?: string; before?: string; after?: string }[] = p.quotes?.length ? p.quotes
      : (p.source_quote ? [{ quote: p.source_quote, locator: p.locator }] : []);
    // B2: each quote inside the passage it came from, so the stance is checked
    // against its context rather than a lifted sentence.
    const inContext = (q: { quote: string; locator?: string; before?: string; after?: string }) =>
      h("blockquote", { class: "lens-quote" },
        q.before ? h("span", { class: "quote-context" }, `…${q.before}`) : null,
        h("mark", {}, q.quote),
        q.after ? h("span", { class: "quote-context" }, `${q.after}…`) : null,
        q.locator ? h("cite", {}, ` — ${q.locator}`) : null);
    const trace = Object.entries((p.trace ?? {}) as Record<string, string>);
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    // A person may reword the stance and say when it applies before accepting
    // (lenses.EDITABLE); the quotes are the source's, so they are not editable.
    // Only a changed field is sent, and the store keeps the original beside it.
    const editable: [string, string, boolean][] = [["name", "Name", false], ["catches", "The failure it catches", true],
      ["applies_when", "Applies when", true], ["not_when", "Not when", true],
      ["prompt_fragment", "The instruction a model would adopt", true],
      ["materials", "Material tags (comma-separated: paper, repository…)", false],
      ["tasks", "Task tags (comma-separated: assess, design, debug…)", false]];
    const initial = (key: string) => Array.isArray(p[key]) ? (p[key] as string[]).join(", ") : String(p[key] ?? "");
    const inputs = editable.map(([key, label, long]) => {
      const el = (long ? h("textarea", { class: "f", rows: key === "prompt_fragment" ? 4 : 2 })
        : h("input", { type: "text", class: "f" })) as HTMLInputElement | HTMLTextAreaElement;
      el.value = initial(key);
      el.id = `lens-edit-${key}`;
      return { key, el, row: h("div", {}, h("label", { class: "f", for: el.id }, label), el) };
    });
    const edits = () => Object.fromEntries(inputs.filter((i) => i.el.value.trim() !== initial(i.key).trim())
      .map((i) => [i.key, i.el.value.trim()]));
    const decide = (d: string) => async () => {
      try {
        const changed = d === "accept" ? edits() : {};
        const out = await this.api.tool("staging_decide", { item_ids: [item.id], decision: d, reason: reason.value,
          ...(Object.keys(changed).length ? { fields: changed } : {}) });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" },
          `${p.name}: ${d === "accept" ? "accepted into the lens store" : d === "reject" ? "rejected" : "deferred"}.`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const source = p.source
      ? h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); this.openNote(p.source); } }, p.source)
      : "an unknown source";
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, p.name ?? item.id)),
      h("p", {}, "A reasoning stance drawn from ", source,
        quotes.length > 1 ? ` (${quotes.length} passages)` : (p.locator ? ` (${p.locator})` : ""), "."),
      p.level === "document" ? h("div", { class: "note" },
        h("p", {}, "Drawn from the whole text, not one passage: it rests on these claims from different parts."),
        h("ul", {}, ((p.rests_on ?? []) as string[]).map((r) => h("li", {}, r)))) : null,
      origin.quotes ? h("p", { class: "dim small" }, "The passage(s) - ", h("span", { class: "origin origin-source" }, "from the source"),
        "; highlighted within the text around them.") : null,
      ...quotes.map(inContext),
      p.topic_warning ? h("p", { class: "note err" }, "No situation outside the source's own subject survived as a transfer: this may be a topic rather than a reusable stance.") : null,
      p.challenge?.verdict ? h("p", { class: "note" }, `Challenge: ${p.challenge.verdict}${p.challenge.reason ? ` — ${p.challenge.reason}` : ""}`) : null,
      p.resembles ? h("p", { class: "note" }, `Resembles a lens you already accepted: ${p.resembles.name}. Reject this one if it adds nothing.`) : null,
      p.perspective ? h("div", {}, head("The stance", "perspective"), h("p", {}, p.perspective)) : null,
      groundedList("Weighs", p.attends_to, "attends_to"),
      list("Lets fade", p.deprioritizes, "deprioritizes"),
      p.role_purpose ? h("div", {}, head("As a role", "role_purpose"), h("p", {}, p.role_purpose)) : null,
      list("Brings", p.role_capabilities, "role_capabilities"),
      list("Expected of it", p.role_expectations, "role_expectations"),
      list("Also fits", p.transfers_to, "transfers_to"),
      groundedList("Ask this of a similar artifact", p.probes, "probes"),
      p.catches ? h("div", {}, head("The failure this catches", "catches"), h("p", {}, p.catches)) : null,
      (p.applies_when || p.not_when) ? h("div", {}, head("When to reach for it", p.applies_when ? "applies_when" : "not_when"),
        p.applies_when ? h("p", {}, "Applies when: ", p.applies_when) : null,
        p.not_when ? h("p", {}, "Not when: ", p.not_when) : null) : null,
      p.prompt_fragment ? h("div", {}, head("The instruction a model would adopt", "prompt_fragment"),
        h("blockquote", { class: "lens-instruction" }, p.prompt_fragment)) : null,
      trace.length ? h("details", {}, h("summary", {}, "How this was drafted"),
        h("ul", {}, trace.map(([step, model]) => h("li", {}, `${step}: `, h("code", {}, model || "unknown model"))))) : null,
      h("p", { class: "note" }, "Check the stance is really in the quoted passage(s) before accepting it."),
      h("details", {}, h("summary", {}, "Edit before accepting"), inputs.map((i) => i.row)),
      reason,
      h("div", { class: "row2" },
        h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer")),
      status,
      h("details", {}, h("summary", {}, "The raw proposal"),
        h("pre", { class: "evidence" }, JSON.stringify(item.proposal ?? item, null, 1))));
  }

  private showConcept(item: any): void {
    const usages = (item.usages ?? []) as { source: string; sentence: string }[];
    const sources = (item.sources ?? []) as string[];
    const definition = h("textarea", { class: "f", id: "lib-def",
      placeholder: "In your own words: what this term or pattern means. Never drafted for you." }) as HTMLTextAreaElement;
    const kindSel = h("select", { "aria-label": "Concept kind" },
      h("option", { value: "term" }, "term"), h("option", { value: "pattern" }, "pattern")) as HTMLSelectElement;
    const aliases = h("input", { type: "text", placeholder: "Aliases, comma-separated (optional)",
      "aria-label": "Aliases" }) as HTMLInputElement;
    const related = h("input", { type: "text", placeholder: "Related concepts, comma-separated (optional)",
      "aria-label": "Related" }) as HTMLInputElement;
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    const split = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
    const decide = (d: string) => async () => {
      if (d === "accept" && !definition.value.trim()) {
        clear(status, h("p", { class: "error" }, "A Definition, in your own words, is needed to accept a concept."));
        return;
      }
      try {
        const out = await this.api.tool("staging_decide", { item_ids: [item.id], decision: d, reason: reason.value,
          ...(d === "accept" ? { fields: { definition: definition.value, concept_kind: kindSel.value,
            aliases: split(aliases.value), related: split(related.value) } } : {}) });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" },
          `${item.name}: ${d === "accept" ? "accepted as a Concept note" : d === "reject" ? "rejected" : "deferred"}.`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name ?? item.id)),
      h("p", {}, `Seen across ${sources.length} source${sources.length === 1 ? "" : "s"}: `,
        sources.flatMap((s, i) => [i ? ", " : "", h("a", { class: "wl", href: "#",
          onclick: (e: Event) => { e.preventDefault(); this.openNote(s); } }, s)])),
      h("h4", {}, "Usages"),
      h("ul", {}, usages.map((u) => h("li", {}, h("blockquote", { class: "lens-quote small" }, u.sentence),
        h("cite", {}, ` — ${u.source}`)))),
      h("p", { class: "note" }, "Nothing above is drafted: the Definition below is your own words, "
        + "the one part of a concept note this catalogue never writes for you."),
      h("label", { class: "f", for: "lib-def" }, "Definition"), definition,
      h("label", { class: "f" }, "Kind"), kindSel,
      aliases, related, reason,
      h("div", { class: "row2" },
        h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer")),
      status);
  }
}

// -- search ----------------------------------------------------------------------

const INTENTS = [["donor", "something to reuse"], ["orient", "where the catalogue holds a topic"],
  ["pattern", "a design pattern"], ["technique", "a technique"], ["data", "a dataset"],
  ["precedent", "prior work"], ["in_text", "text inside documents"]];

export class Search {
  readonly el = h("div", { class: "view search" });
  private results = h("div", { class: "results", "aria-live": "polite" });

  constructor(private api: Api, private openNote: (name: string) => void) {
    const query = h("input", { type: "search", placeholder: "What are you looking for?", "aria-label": "Search query" }) as HTMLInputElement;
    const intent = h("select", { "aria-label": "Intent" },
      INTENTS.map(([v, label]) => h("option", { value: v }, `${v} · ${label}`))) as HTMLSelectElement;
    const run = () => this.run(query.value, intent.value);
    query.onkeydown = (e) => { if (e.key === "Enter") run(); };
    this.el.append(h("div", { class: "view-head" }, h("strong", {}, "Search")),
      h("div", { class: "row2 tight" }, query, intent, h("button", { class: "primary", onclick: run }, "Search")),
      this.results);
  }

  focus(): void { (this.el.querySelector("input") as HTMLInputElement | null)?.focus(); }

  private async run(query: string, intent: string): Promise<void> {
    if (!query.trim()) return;
    clear(this.results, h("p", { class: "dim" }, "Searching…"));
    try {
      const out = await this.api.tool("search", { query, intent, limit: 20 });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const rows = (out.results ?? []) as any[];
      clear(this.results,
        h("p", { class: "verdict" }, String(out.coverage?.sentence ?? out.verdict ?? "")),
        rows.length ? rows.map((r) => h("div", { class: "result" },
          h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); this.openNote(r.fields?.path ?? r.name); } }, r.name),
          h("span", { class: "dim" }, ` · ${r.fields?.kind ?? r.kind} · ${r.fields?.topic ?? ""}`),
          r.fields?.bottom_line ? h("p", {}, r.fields.bottom_line) : null,
          h("small", { class: "dim" }, r.why ?? ""))) : h("p", { class: "dim" }, "Nothing held matches."),
        out.next_step ? h("p", { class: "note" }, String(out.next_step)) : null);
    } catch (e) {
      clear(this.results, h("p", { class: "error" }, (e as Error).message));
    }
  }
}
