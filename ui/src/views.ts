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
  private status = "staged";                  // sources only: which part of their lifecycle
  private selected = "";
  // Research Pipeline §4.2: shown on every kind while approved sources wait, and while a
  // batch runs; polled only while one runs.
  private banner = h("div", { class: "batch-banner", role: "status" });
  private poll = 0;
  private wasRunning = false;
  // True right after a decision's outcome message is shown, until the person
  // opens something else or explicitly refreshes: an automatic reload (the
  // SSE echo of this same decision, or someone else's) must not wipe it.
  private detailLocked = false;
  private paintKinds: () => void = () => {};
  private pending = "";                      // an offering to open once the list loads

  constructor(private api: Api, private openNote: (name: string) => void,
              private currentSession: () => string = () => "",
              private onSessionUpdate: (session: Record<string, any>) => void = () => {}) {
    const kinds = h("div", { class: "seg", role: "group", "aria-label": "Kind" });
    const statuses = h("select", { "aria-label": "Which sources", onchange: () => {
      this.status = statuses.value; this.selected = ""; void this.load(true);
    } }, [["staged", "Captured, to review"], ["approved", "Approved, awaiting ingestion"],
          ["enriched", "Ingested, ready to accept"], ["partial", "Ingested with gaps"],
          ["queued", "Queued for capture"],
          ["failed", "Failed"], ["deferred", "Deferred"]]
      .map(([v, label]) => h("option", { value: v }, label))) as HTMLSelectElement;
    const paint = () => {
      clear(kinds, [["source", "Sources"], ["lens", "Lenses"], ["concept", "Concepts"], ["topic", "Topics"], ["offering", "Offerings"], ["import", "From V1"]].map(([v, label]) =>
        h("button", { "aria-pressed": String(this.kind === v), onclick: () => { this.kind = v; paint(); void this.load(true); } }, label)));
      scan.style.display = this.kind === "concept" ? "" : "none";
      propose.style.display = this.kind === "topic" ? "" : "none";
      statuses.style.display = this.kind === "source" ? "" : "none";
    };
    const propose = h("button", { class: "ghost", title: "Group the library's sources into topics, staged here for you to accept",
      onclick: async () => {
        clear(this.list, h("p", { class: "dim" }, "Asking the clerk to group the sources…"));
        try {
          const out = await this.api.tool("topic_propose", {});
          if (out.error) throw new Error(String(out.detail ?? out.error));
          await this.load(true);
          const n = (out.proposed ?? []).length;
          this.list.prepend(h("p", { class: "note" }, out.detail ? String(out.detail)
            : `${n} topic${n === 1 ? "" : "s"} proposed from ${out.considered} sources.` +
              ((out.refile ?? []).length ? ` ${out.refile.length} source(s) fit a topic you already have.` : "")));
        } catch (e) {
          clear(this.list, h("p", { class: "error" }, (e as Error).message));
        }
      } }, "Propose topics");
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
    this.paintKinds = paint;
    this.el.append(h("div", { class: "view-head" }, h("strong", {}, "Staging review"), kinds, statuses,
      h("button", { class: "ghost", onclick: () => void this.load(true) }, "Refresh"), scan, propose),
      this.banner,
      h("div", { class: "split" }, this.list, this.detail));
  }

  /** `reset`: an explicit visit (opening the view, Refresh, switching kind) —
   * always shows the placeholder when nothing is selected. Left false, an
   * automatic reload (another surface's decision arriving over the event
   * stream) refreshes the list without wiping a just-shown outcome message. */
  async load(reset = false): Promise<void> {
    if (reset) this.detailLocked = false;
    clear(this.list, h("p", { class: "dim" }, "Loading…"));
    if (this.kind === "offering") return this.loadOfferings();
    try {
      const status = this.kind === "source" ? this.status : "staged";
      const out = await this.api.tool("staging_list", { kind: this.kind, status, limit: 50 });
      const items = (out.items ?? []) as any[];
      clear(this.list,
        h("p", { class: "dim" }, `${out.total ?? items.length} ${status === "staged" ? "waiting" : status}`),
        items.length ? items.map((item) => h("button", {
          class: `item${item.id === this.selected ? " sel" : ""}`, role: "option",
          "aria-selected": String(item.id === this.selected), onclick: () => this.show(item.id),
        }, item.sensitivity === "review" ? h("span", { class: "flag", title: "sensitive: a person decides" }, "⚑ ") : null,
          item.name || item.id,
          h("small", {}, (item.kind === "lens"
            ? [item.source ? `from ${item.source}` : "", item.locator]
            : item.kind === "concept"
            ? [`${item.sources ?? 0} source${item.sources === 1 ? "" : "s"}`, `${item.usages ?? 0} usage${item.usages === 1 ? "" : "s"}`]
            : item.kind === "topic"
            ? [`${item.coverage?.sources ?? 0} of ${item.coverage?.of ?? 0} sources`, item.duplicate_of ? `close to ${item.duplicate_of}` : ""]
            : item.ref
            ? [item.failure ? `failed: ${item.failure.stage}` : "not yet fetched", item.note]
            : item.status === "enriched" || item.status === "partial"
            ? [item.topic, `coverage ${item.processing?.coverage ?? "?"}`]
            : item.status === "failed"
            ? [`failed at ${item.failure?.stage ?? "?"}`]
            : [item.topic, item.drafted ? "drafted" : item.reviewed ? "draft queued" : "no draft yet",
               item.deep_read ? `read ${item.deep_read}` : "", item.fit]).filter(Boolean).join(" · "))))
          : h("p", { class: "dim" }, "Nothing here."));
      if (!this.selected && !this.detailLocked) {
        clear(this.detail, h("p", { class: "dim" }, "Choose an item to see its draft beside its evidence."));
      }
    } catch (e) {
      clear(this.list, h("p", { class: "error" }, (e as Error).message));
    }
    void this.paintBanner();
  }

  /** Open one staged offering here (the chat's "Read the draft" on a promotion question). */
  focusOffering(id: string): void {
    this.kind = "offering";
    this.selected = id;
    this.pending = id;
    this.paintKinds();
  }

  /** Offering drafts wait in staging/offerings/ until promoted: listed here so a person
   * reads one before answering "promote it?" (Test Report A2 b). Not staging items -
   * each belongs to the session that drafted it, and its decision is recorded there. */
  private async loadOfferings(): Promise<void> {
    try {
      const out = await this.api.get("/api/offerings/staged");
      const rows = (out.offerings ?? []) as any[];
      const waiting = rows.filter((r) => r.status !== "declined").length;
      clear(this.list,
        h("p", { class: "dim" }, `${waiting} waiting${rows.length > waiting ? ` · ${rows.length - waiting} declined` : ""}`),
        rows.length ? rows.map((r) => h("button", {
          class: `item${r.offering === this.selected ? " sel" : ""}`, role: "option",
          "aria-selected": String(r.offering === this.selected), onclick: () => void this.showOffering(r.offering),
        }, r.challenged ? h("span", { class: "flag", title: "a claim the review challenged was kept: yours to weigh" }, "⚑ ") : null,
          r.title,
          h("small", {}, [r.project || "Insights", `${r.claims} claim${r.claims === 1 ? "" : "s"}`,
            r.question ? "asked: promote?" : r.status === "declined" ? "declined" : "",
            r.session_status === "closed" ? "session closed" : ""].filter(Boolean).join(" · "))))
          : h("p", { class: "dim" }, "No offering waits to be promoted."));
      if (this.pending) {
        const id = this.pending;
        this.pending = "";
        return this.showOffering(id);
      }
      if (!this.selected && !this.detailLocked) {
        clear(this.detail, h("p", { class: "dim" }, "Choose an offering to read it before deciding."));
      }
    } catch (e) {
      clear(this.list, h("p", { class: "error" }, (e as Error).message));
    }
    void this.paintBanner();
  }

  private async showOffering(id: string): Promise<void> {
    this.selected = id;
    this.detailLocked = false;
    this.list.querySelectorAll(".item").forEach((b) => b.classList.remove("sel"));
    clear(this.detail, h("p", { class: "dim" }, "Loading…"));
    let r: any;
    try {
      r = await this.api.get(`/api/offerings/staged?id=${encodeURIComponent(id)}`);
    } catch (e) {
      clear(this.detail, h("p", { class: "error" }, (e as Error).message));
      return;
    }
    const status = h("div", { role: "status" });
    const decide = (d: string) => async () => {
      try {
        const out = await this.api.post("/api/offerings/decide", { id, decision: d });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" },
          out.resumed ? `${r.title}: answered - the session carries on and ${d === "promote" ? "promotes" : "declines"} it.`
            : out.promoted ? [`${r.title}: promoted to `, h("a", { href: "#", onclick: (e: Event) => {
                e.preventDefault(); this.openNote(String(out.promoted));
              } }, String(out.promoted)), out.findable === false ? " (not yet found by search)" : "", "."]
            : `${r.title}: declined. It stays here, and can still be promoted.`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const review = r.review ?? {};
    const reviewed = ["holds", "unchecked", "queued"].filter((k) => review[k]).map((k) => `${review[k]} ${k}`);
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, r.title)),
      h("p", { class: "dim" }, [r.kind.replace(/_/g, " "), r.created, `for ${r.project || "Insights"}`,
        `${r.claims} claim${r.claims === 1 ? "" : "s"}, each quote found in its source`,
        reviewed.length ? `review: ${reviewed.join(", ")}${review.by ? ` (${review.by})` : ""}` : "",
        `session ${r.session} (${r.session_status})`].filter(Boolean).join(" · ")),
      r.challenged ? h("p", { class: "warn" }, `⚑ ${r.challenged} claim${r.challenged === 1 ? "" : "s"} the review challenged ${r.challenged === 1 ? "was" : "were"} kept by the agent, with its reason - read ${r.challenged === 1 ? "it" : "them"} before promoting.`) : null,
      h("p", { class: "note" }, r.question ? "The session has asked you to promote this. Your choice here answers it."
        : r.status === "declined" ? "You declined this. It stays in staging; promoting it now still moves it into the library."
        : "The session has not asked yet. Promoting moves it into the library now."),
      h("div", { class: "offering-body" }, render(String(r.text ?? ""), this.openNote, { frontmatter: true })),
      h("div", { class: "row2 tight" },
        h("button", { class: "primary", onclick: decide("promote") }, "Promote into the library"),
        r.status === "declined" ? null : h("button", { class: "ghost", onclick: decide("decline") }, "Decline")),
      status);
  }

  /** Approving a source only queues it: a person begins the batch here, and nothing
   * else starts it (Research Pipeline §4.2). The count is the approved set not yet
   * started; while a batch runs, later approvals are counted apart, for the next run. */
  private async paintBanner(): Promise<void> {
    let b: any;
    try {
      b = await this.api.tool("batch_status", {});
    } catch {
      clear(this.banner);
      return;
    }
    const waiting = Number(b.waiting ?? 0);
    const running = b.status === "running";
    const start = (label: string, args: Record<string, unknown>, cls = "primary") =>
      h("button", { class: cls, onclick: async (e: Event) => {
        (e.currentTarget as HTMLButtonElement).disabled = true;
        try {
          const out = await this.api.tool("process_approved", { ...args, background: true });
          if (out.error || out.refused) throw new Error(String(out.detail ?? out.refused ?? out.error));
        } catch (err) {
          this.banner.append(h("p", { class: "error" }, (err as Error).message));
          return;
        }
        void this.paintBanner();
      } }, label);
    const rows: HTMLElement[] = [];
    if (running) {
      const cur = b.current ?? {};
      rows.push(h("div", { class: "row2 tight" },
        h("span", {}, h("strong", {}, `Processing ${b.processed ?? 0} of ${b.total ?? 0}`),
          cur.item ? ` · ${cur.item}: ${cur.stage}${cur.detail ? ` - ${cur.detail}` : ""}` : ""),
        h("button", { class: "ghost", onclick: async () => {
          await this.api.tool("batch_cancel", {});
          void this.paintBanner();
        } }, "Stop after this stage")));
      if (waiting) rows.push(h("p", { class: "note inline" }, `${waiting} more approved, waiting for the next run.`));
    } else {
      const unfinished = (b.items ?? []).some((i: any) => i.status === "processing");
      if (unfinished && (b.status === "interrupted" || b.status === "cancelled")) {
        rows.push(h("div", { class: "row2 tight" },
          h("span", {}, `The last batch stopped${b.detail ? ` (${b.detail})` : ""} with sources unfinished.`),
          start("Resume it", { resume: b.run }, "ghost")));
      }
      if (waiting) {
        rows.push(h("div", { class: "row2 tight" },
          h("strong", {}, waiting === 1 ? "1 source approved and awaiting ingestion."
            : `${waiting} sources approved and awaiting ingestion.`),
          start("Click here to begin", {})));
      }
    }
    clear(this.banner, rows.length ? h("div", { class: "warn" }, rows) : null);
    window.clearTimeout(this.poll);
    if (running) this.poll = window.setTimeout(() => void this.paintBanner(), 2000);
    else if (this.wasRunning && this.kind === "source") void this.load();   // it just finished
    this.wasRunning = running;
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
    if (item.kind === "topic") return this.showTopic(item);
    if (item.kind === "import") return this.showImport(item);
    if (item.ref && (item.status === "queued" || item.status === "failed")) return this.showQueued(item);
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
          ? (r.merged_into ? `Merged ${(r.sections ?? []).join(", ") || "its sections"} into ${r.merged_into}; the previous text is kept on this item.`
            : r.promotion && !r.promotion.catalogued ? `Accepted: ${r.promotion.status}.` : `Accepted into the library and catalogued (coverage: ${r.coverage ?? "unknown"}).`) +
            (r.handoff ? " It joins your session as an undecided candidate." : "")
          : decision === "approve" ? "Approved for ingestion: it waits for the batch above. Nothing is in the library yet."
          : decision === "reject" ? "Rejected." : "Deferred.";
        this.selected = "";
        if (r.session && r.session.session === this.currentSession()) this.onSessionUpdate(r.session);
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
    // Two approvals, never one "Accept" for both (Research Pipeline §4.2): approving spends
    // processing on it; accepting publishes it. "Accept as captured" is the deliberate
    // quick path: nothing further is read, and the note records `coverage: captured`.
    const st = String(item.status ?? "staged");
    const btn = (label: string, d: string, cls = "ghost", title = "") =>
      h("button", { class: cls, onclick: decide(d), ...(title ? { title } : {}) }, label);
    const proc = item.processing ?? {};
    const buttons = item.revision_of
      ? [btn("Accept", "accept", "primary"), btn("Reject", "reject"), btn("Defer", "defer")]
      : st === "enriched"
      ? [btn("Accept into library", "accept", "primary"), btn("Reject", "reject"), btn("Defer", "defer")]
      : st === "partial"
      ? [btn("Approve for ingestion again", "approve", "primary", "Runs only the unfinished stages; finished ones are kept"),
         btn("Accept with partial coverage", "accept", "ghost", "The note records its coverage and what was not examined"),
         btn("Reject", "reject"), btn("Defer", "defer")]
      : st === "approved"
      ? [btn("Reject", "reject"), btn("Defer", "defer", "ghost", "Take it out of the waiting batch")]
      : st === "processing"
      ? []
      : st === "failed"
      ? [btn("Approve for ingestion again", "approve", "primary"), btn("Reject", "reject")]
      : [btn("Approve for ingestion", "approve", "primary", "Read it in full and review it in the next batch, then accept it"),
         btn("Reject", "reject"), btn("Defer", "defer"),
         btn("Accept as captured", "accept", "ghost", "Catalogue it now from what capture read, without ingesting it; the note records coverage: captured")];
    const stage = st === "approved"
      ? h("p", { class: "note" }, "Approved for ingestion: it waits for the batch (the banner above). Nothing is in the library yet.")
      : st === "processing" ? h("p", { class: "note" }, `Being ingested in ${item.batch ?? "a batch"}.`)
      : st === "enriched" || st === "partial" ? h("div", {},
          h("p", { class: "note" }, st === "enriched"
            ? `Ingested in ${proc.run ?? "a batch"}: every stage complete, coverage ${proc.coverage ?? "unknown"}.`
            : `Ingested in ${proc.run ?? "a batch"} with gaps: coverage ${proc.coverage ?? "unknown"}. Approve it again to run only what is unfinished, or accept it as it is - its note will say what was not examined.`),
          (proc.not_examined ?? []).length ? h("p", { class: "warn" }, `Not examined: ${(proc.not_examined as string[]).join("; ")}.`) : null)
      : st === "staged" || st === "deferred" ? h("p", { class: "note" }, "Captured: only what intake fetched has been read.")
      : st === "failed" && item.failure ? h("p", { class: "warn" }, `Ingestion failed at ${item.failure.stage}: ${item.failure.reason}`)
      : null;
    // The stage ledger and what capture found (R12): each stage's outcome, the quality
    // verdict with its next step, a possible duplicate, and the fit screen kept apart
    // from the neutral description.
    const intakeInfo = item.intake ?? {};
    const q = intakeInfo.quality ?? {};
    const ledger = (stages: Record<string, string>) =>
      Object.entries(stages ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ");
    const capture = h("div", {},
      Object.keys(intakeInfo.stages ?? {}).length ? h("p", { class: "dim" }, `Capture — ${ledger(intakeInfo.stages)}`) : null,
      Object.keys(proc.stages ?? {}).length ? h("p", { class: "dim" }, `Batch — ${ledger(proc.stages)}`) : null,
      q.verdict && q.verdict !== "usable" ? h("p", { class: "warn" }, `${q.reason}. Next: ${q.next}.`) : null,
      item.possible_duplicate_of ? h("p", { class: "warn" }, `Possibly the same work as ${item.possible_duplicate_of}.`) : null,
      item.fit_screen ? h("p", { class: "note" }, `Screened against ${item.found_for?.brief ?? "its brief"}: `,
        h("strong", {}, String(item.fit_screen.verdict ?? item.fit_screen.status ?? "")),
        item.fit_screen.reason ? ` — ${item.fit_screen.reason}` : "", " (a fit judgement, kept apart from the description)") : null);
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name),
        item.canonical_url ? h("a", { href: item.canonical_url, target: "_blank", rel: "noreferrer noopener" }, "source ↗") : null),
      item.sensitivity === "review" ? h("p", { class: "warn" }, "⚑ Marked sensitive: only a person accepts it, and only a person clears the mark.") : null,
      stage,
      capture,
      item.revision_of ? h("p", { class: "note" }, "A revision of an accepted note, ",
        h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); this.openNote(item.revision_of); } }, item.revision_of),
        item.revision_kind === "dik"
          ? `: its Data and Information records rebuilt. Accepting adds ${Object.keys(item.sections ?? {}).join(", ")} to that note, each labelled with where its claims come from; the note's own prose is untouched (the previous text is kept on this item). Rejecting leaves the note as it is.`
          : ": its whole text read. Accepting merges its Claims and Evidence & Limits into that note (the previous text is kept on this item); rejecting leaves the note as it is.") : null,
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
          h("div", { class: "row2" }, buttons,
            st === "processing" ? null
              : h("button", { class: "ghost push", onclick: draftIt }, draft.bottom_line ? "Redraft" : "Draft with the clerk")),
          h("div", { class: "row2" },
            h("span", { class: "note inline" }, readLine),
            st !== "processing" && (!dr || readCount < dr.chunks)
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
    const imported = item.imported as { definition?: string; concept_kind?: string; aliases?: string[]; related?: string[] } | undefined;
    const aliases = h("input", { type: "text", placeholder: "Aliases, comma-separated (optional)",
      "aria-label": "Aliases" }) as HTMLInputElement;
    const related = h("input", { type: "text", placeholder: "Related concepts, comma-separated (optional)",
      "aria-label": "Related" }) as HTMLInputElement;
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    const split = (v: string) => v.split(",").map((s) => s.trim()).filter(Boolean);
    if (imported) {
      // From V1: its own definition, offered to keep or reword - accepting is still a person's.
      definition.value = imported.definition ?? "";
      kindSel.value = imported.concept_kind ?? "term";
      aliases.value = (imported.aliases ?? []).join(", ");
      related.value = (imported.related ?? []).join(", ");
    }
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

  /** A proposed topic, as the library's own sources suggest it (R8). It is reviewed here;
   * accepting, renaming or merging it into the taxonomy is done in Settings → Library. */
  /** V1's Applications and branch offerings: the note as V1 wrote it, into its V2 folder. */
  private showImport(item: any): void {
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    const decide = (d: string) => async () => {
      try {
        const out = await this.api.tool("staging_decide", { item_ids: [item.id], decision: d, reason: reason.value });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" },
          `${item.name}: ${d === "accept" ? `written to ${item.target}` : d === "reject" ? "rejected" : "deferred"}.`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name ?? item.id)),
      h("p", { class: "dim" }, `From V1 ${item.imported_from?.path ?? ""} - accepting writes it to ${item.target}, as V1 wrote it. V1's whole note is also kept as evidence.`),
      h("pre", { class: "import-body" }, String(item.body ?? "").slice(0, 4000)),
      reason,
      h("div", { class: "row2 tight" },
        h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer"),
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject")),
      status);
  }

  private showTopic(item: any): void {
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    const decide = (d: string) => async () => {
      try {
        const out = await this.api.tool("staging_decide", { item_ids: [item.id], decision: d, reason: reason.value });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.error ?? out.detail ?? out.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" }, `${item.name}: ${d === "reject" ? "rejected" : "deferred"}.`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const members = (item.members ?? []) as string[];
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name)),
      h("p", {}, item.what_belongs ?? ""),
      item.duplicate_of ? h("p", { class: "warn" }, `Close to a topic you already have: ${item.duplicate_of}. Merge rather than add?`) : null,
      h("p", { class: "dim" }, `${item.coverage?.sources ?? members.length} of the ${item.coverage?.of ?? "?"} sources considered · proposed by ${item.proposed_by ?? "the clerk"}`),
      (item.aliases ?? []).length ? h("p", {}, h("strong", {}, "Also called: "), (item.aliases as string[]).join(", ")) : null,
      h("h4", {}, "Sources it would hold"),
      h("p", {}, members.flatMap((s, i) => [i ? ", " : "", h("a", { class: "wl", href: "#",
        onclick: (e: Event) => { e.preventDefault(); this.openNote(s); } }, s)])),
      h("p", { class: "note" }, "A proposal only: the topic list changes when you accept, rename or merge it in Settings → Library."),
      reason,
      h("div", { class: "row2" },
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer")),
      status);
  }

  /** A reference in the intake queue, not yet fetched, or whose capture failed (R7). */
  private showQueued(item: any): void {
    const reason = h("input", { type: "text", placeholder: "Why remove it", "aria-label": "Reason" }) as HTMLInputElement;
    const status = h("div", { role: "status" });
    const act = (tool: string, args: Record<string, unknown>, done: string) => async () => {
      try {
        const out = await this.api.tool(tool, args);
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error) throw new Error(String(r.error ?? out.detail ?? out.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" }, `${item.ref}: ${done}`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, (e as Error).message));
      }
    };
    const remove = () => reason.value.trim()
      ? act("queue_remove", { item_ids: [item.id], reason: reason.value }, "removed; kept in quarantine with your reason.")()
      : clear(status, h("p", { class: "error" }, "Say why it is removed."));
    const f = item.found_for ?? {};
    clear(this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.ref)),
      h("p", {}, item.status === "failed" ? "Its capture failed: nothing was fetched." : "Queued for capture: not yet fetched."),
      item.failure ? h("p", { class: "warn" }, `${item.failure.stage}: ${item.failure.reason}`) : null,
      item.note ? h("p", {}, h("strong", {}, "Why: "), item.note) : null,
      h("p", { class: "dim" }, [item.requested_by ? `asked by ${item.requested_by}` : "",
        f.session ? `for ${f.session}${f.brief ? ` / ${f.brief}` : ""}` : "",
        item.queued_at ? `queued ${String(item.queued_at).slice(0, 10)}` : ""].filter(Boolean).join(" · ")),
      reason,
      h("div", { class: "row2" },
        item.status === "failed"
          ? h("button", { class: "primary", onclick: act("queue_retry", { item_ids: [item.id] }, "queued again.") }, "Retry capture")
          : null,
        h("button", { class: "ghost", onclick: remove }, "Remove from queue")),
      status);
  }
}

// -- search ----------------------------------------------------------------------

const INTENTS = [["all", "everything, grouped"], ["donor", "something to reuse"],
  ["orient", "where the catalogue holds a topic"], ["pattern", "a design pattern"],
  ["technique", "a technique"], ["data", "a dataset"], ["precedent", "prior work"],
  ["made", "what this library made"], ["in_text", "text inside documents"]];
// Constraints apply to the source-shaped intents only (the engine's own rule).
const FILTERED = new Set(["all", "donor", "orient", "data"]);
const GROUP_LABEL: Record<string, string> = { orient: "Sources", pattern: "Patterns",
  made: "What this library made" };

/** The person's catalogue page (Search Methods SM-1): result-derived facets with counts on
 *  the left, summarised tiles on the right, the note beside it on a click. No ranking lives
 *  here - it calls the same `search` the agent does, with the same constraints. */
export class Search {
  readonly el = h("div", { class: "view search" });
  private facets = h("div", { class: "facets", "aria-label": "Filters" });
  private results = h("div", { class: "results", "aria-live": "polite" });
  private chosen: Record<string, string[]> = {};
  private last = { query: "", intent: "all", age: 0 };
  // The library, or the library's work: staging, the threads, what was used and written
  private scope = "library";

  constructor(private api: Api, private openNote: (name: string) => void) {
    const query = h("input", { type: "search", placeholder: "What are you looking for?", "aria-label": "Search query" }) as HTMLInputElement;
    const intent = h("select", { "aria-label": "Intent" },
      INTENTS.map(([v, label]) => h("option", { value: v }, `${v} · ${label}`))) as HTMLSelectElement;
    const age = h("select", { "aria-label": "Source date" },
      [["0", "any date"], ["365", "within a year"], ["1095", "within 3 years"]]
        .map(([v, label]) => h("option", { value: v }, label))) as HTMLSelectElement;
    const scope = h("select", { "aria-label": "Search in", onchange: () => {
      this.scope = scope.value;
      intent.style.display = age.style.display = this.scope === "library" ? "" : "none";
    } }, [["library", "the library"], ["staging", "staging"], ["sessions", "sessions"],
          ["activity", "activity"]].map(([v, label]) => h("option", { value: v }, label))) as HTMLSelectElement;
    const run = () => this.scope === "library"
      ? this.run(query.value, intent.value, Number(age.value)) : this.runWork(query.value);
    query.onkeydown = (e) => { if (e.key === "Enter") run(); };
    this.el.append(h("div", { class: "view-head" }, h("strong", {}, "Search")),
      h("div", { class: "row2 tight" }, query, scope, intent, age, h("button", { class: "primary", onclick: run }, "Search")),
      h("div", { class: "split" }, this.facets, this.results));
  }

  focus(): void { (this.el.querySelector("input") as HTMLInputElement | null)?.focus(); }

  /** Staging, sessions or activity (search_work): where was that seen? */
  private async runWork(query: string): Promise<void> {
    if (!query.trim()) return;
    clear(this.facets);
    clear(this.results, h("p", { class: "dim" }, "Searching…"));
    try {
      const out = await this.api.tool("search_work", { query, scope: this.scope });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const rows = (out.results ?? []) as any[];
      const when = (w: unknown) => String(w ?? "").slice(0, 10);
      const row = (r: any) => this.scope === "staging"
        ? h("div", { class: "tile" }, h("strong", {}, r.name || r.id),
            h("span", { class: "dim" }, ` · ${r.kind} · ${r.status} · ${when(r.when)}`))
        : this.scope === "sessions"
        ? h("div", { class: "tile" }, h("strong", {}, r.question || r.session),
            h("span", { class: "dim" }, ` · ${r.purpose} · ${r.status} in ${r.phase} · ${when(r.when)} · ${r.session}`))
        : h("div", { class: "tile" }, `${r.what} `,
            h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); this.openNote(r.target); } }, r.target),
            h("span", { class: "dim" }, `${r.detail && r.detail !== r.target ? ` · ${r.detail}` : ""} · ${when(r.when)} · ${r.session}`));
      clear(this.results, rows.length ? rows.map(row) : h("p", { class: "dim" }, `Nothing in ${this.scope} matches.`));
    } catch (e) {
      clear(this.results, h("p", { class: "error" }, (e as Error).message));
    }
  }

  private async run(query: string, intent: string, age = this.last.age): Promise<void> {
    if (!query.trim()) return;
    if (query !== this.last.query || intent !== this.last.intent) this.chosen = {};
    this.last = { query, intent, age };
    clear(this.results, h("p", { class: "dim" }, "Searching…"));
    const constraints = FILTERED.has(intent) ? this.chosen : {};
    try {
      const out = await this.api.tool("search", { query, intent, limit: 20, constraints,
        ...(age ? { max_age_days: age } : {}) });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      this.paintFacets(out, intent);
      this.paintResults(out, query, intent);
    } catch (e) {
      clear(this.results, h("p", { class: "error" }, (e as Error).message));
    }
  }

  private paintFacets(out: any, intent: string): void {
    const axes = Object.entries((out.facets ?? {}) as Record<string, { value: string; count: number }[]>);
    const picked = Object.values(this.chosen).reduce((n, v) => n + v.length, 0);
    const toggle = (axis: string, value: string) => () => {
      const now = new Set(this.chosen[axis] ?? []);
      if (now.has(value)) now.delete(value); else now.add(value);
      this.chosen = { ...this.chosen, [axis]: [...now] };
      if (!now.size) delete this.chosen[axis];
      void this.run(this.last.query, this.last.intent);
    };
    clear(this.facets,
      !FILTERED.has(intent) ? h("p", { class: "dim" }, "Filters apply to sources: choose everything, donor, orient or data.")
        : axes.length || picked ? null : h("p", { class: "dim" }, "Filters appear here from what the search returns."),
      picked ? h("button", { class: "ghost", onclick: () => { this.chosen = {}; void this.run(this.last.query, this.last.intent); } },
        `Clear filters (${picked})`) : null,
      // A chosen value stays listed even when it now matches nothing, so it can be cleared.
      Object.entries(this.chosen).filter(([axis]) => !axes.some(([a]) => a === axis))
        .map(([axis, values]) => h("div", { class: "facet" }, h("h4", {}, axis.replace(/_/g, " ")),
          values.map((v) => h("button", { class: "chip", "aria-pressed": "true", onclick: toggle(axis, v) }, `${v} ✕`)))),
      axes.map(([axis, values]) => h("div", { class: "facet" }, h("h4", {}, axis.replace(/_/g, " ")),
        values.slice(0, 12).map((v) => h("button", {
          class: "chip", "aria-pressed": String((this.chosen[axis] ?? []).includes(v.value)),
          onclick: toggle(axis, v.value),
        }, `${v.value} `, h("span", { class: "dim" }, String(v.count)))))));
  }

  private paintResults(out: any, query: string, intent: string): void {
    const rows = (out.results ?? []) as any[];
    const feedback = (r: any, verdict: string, rank: number) =>
      this.api.tool("search_feedback", { query, note: r.name, verdict, intent: r.fields?.intent ?? intent, rank })
        .catch(() => undefined);
    const tile = (r: any, rank: number) => {
      const f = r.fields ?? {};
      const card: HTMLElement = h("div", { class: "tile" },
        h("div", { class: "tile-head" },
          h("a", { class: "wl", href: "#", onclick: (e: Event) => {
            e.preventDefault();
            void feedback(r, "opened", rank);
            this.openNote(f.path ?? f.note ?? r.name);
          } }, r.name),
          h("span", { class: "dim" }, [r.kind, f.kind && f.kind !== r.kind ? f.kind : "", f.topic].filter(Boolean).join(" · ")),
          f.read_depth ? h("span", { class: `depth ${String(f.read_depth).split(" ")[0]}`,
            title: (f.not_examined ?? []).join("; ") || "how much of the source was read" }, `read: ${f.read_depth}`) : null),
        f.bottom_line ? h("p", {}, f.bottom_line) : f.excerpt ? h("p", {}, f.excerpt) : null,
        h("small", { class: "dim" }, r.why ?? ""),
        // The grains beneath a source (SM-2/3/4): where inside it, how to reach it, what
        // it relates to - shown beside the result, never folded into its rank.
        (f.components ?? []).length ? h("p", { class: "inside" }, "Inside: ",
          (f.components as any[]).map((c, i) => h("span", {}, i ? " · " : "", h("code", {}, c.address),
            h("span", { class: "dim" }, ` (${(c.matched ?? []).join(", ")})`)))) : null,
        (f.access_points ?? []).length ? h("div", { class: "access" },
          (f.access_points as any[]).map((p) => h("div", {}, h("code", {}, p.url), h("span", { class: "dim" },
            p.checked_at === "never" ? " · not checked"
              : ` · ${p.reachable ? "answered" : "did not answer"} (${p.status}) · checked ${String(p.checked_at).slice(0, 10)}`))),
          h("button", { class: "ghost", onclick: async () => {
            await this.api.tool("verify_access", { source: r.name });
            void this.run(this.last.query, this.last.intent);
          } }, "Check access")) : null,
        (f.examples ?? []).length || (f.neighbours ?? []).length ? h("p", { class: "dim" },
          (f.examples ?? []).length ? "Used by: " : "", (f.examples ?? []).flatMap((n: string, i: number) =>
            [i ? ", " : "", h("a", { class: "wl", href: "#", onclick: (e: Event) => { e.preventDefault(); this.openNote(n); } }, n)]),
          (f.neighbours ?? []).length ? `${(f.examples ?? []).length ? " · " : ""}Near: ${(f.neighbours as string[]).join(", ")}` : "") : null,
        h("div", { class: "row2 tight" },
          h("button", { class: "ghost", title: "Logged only: it never changes ranking", onclick: () => {
            void feedback(r, "dismissed", rank);
            card.classList.add("dismissed");
          } }, "Not relevant")));
      return card;
    };
    const groups: [string, any[]][] = intent === "all"
      ? (out.ran ?? []).map((i: string) => [i, rows.filter((r) => r.fields?.intent === i)])
      : [["", rows]];
    const removed = (out.removed_by_filters ?? []) as string[];
    clear(this.results,
      h("p", { class: "verdict" }, String(out.coverage?.sentence ?? out.verdict ?? "")),
      removed.length ? h("p", { class: "warn" }, `Your filters removed these top candidates: ${removed.join(", ")}.`) : null,
      out.ran ? h("p", { class: "dim" }, `Ran: ${(out.ran as string[]).join(", ")} — each answers in its own shape.`) : null,
      rows.length ? groups.map(([i, rs]) => h("section", { class: "group" },
        i ? h("h3", {}, `${GROUP_LABEL[i] ?? i} · ${rs.length}`) : null,
        rs.length ? rs.map((r, n) => tile(r, n + 1)) : h("p", { class: "dim" }, "Nothing here."))) :
        h("p", { class: "dim" }, "Nothing held matches."),
      out.next_step ? h("p", { class: "note" }, String(out.next_step)) : null);
  }
}
