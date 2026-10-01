// The conversation and the plan beside it. Tool activity reads as one rail of
// past-tense lines; writes are marked; a permission request is a card in the
// conversation, answered in place; a failure says what failed.

import type { Api, Event } from "./api";
import { clear, h } from "./dom";
import { link, render } from "./markdown";
import { reader, speakerIcon } from "./speech";

export type Session = Record<string, any> | null;

export interface ChatHooks {
  openNote(name: string): void;
  effectOf(tool: string): string;
  onSession(session: Session): void;
  resend(text: string): void;
  rewind(index: number): void;
  branch(index: number): void;
  continueSession(): void;
  /** Staging -> Offerings, opened at one staged draft. */
  openOffering?(id: string): void;
}

/** The staged offering a promotion question is about, from the path the question
 *  names (`promote_offering` asks "Promote the offering ... (path)?"). */
function offeringAsked(q: Record<string, any>): string {
  if (q.kind !== "confirm") return "";
  const named = /staging\/offerings\/([^\s()]+)\.md/.exec(String(q.question ?? ""));
  return named ? named[1] : "";
}

/** Small line icons, drawn rather than emoji, so they match the theme. */
function icon(paths: readonly (readonly [string, Record<string, string>])[]): SVGElement {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "13");
  svg.setAttribute("height", "13");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of paths) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", "currentColor");
    el.setAttribute("stroke-width", "1.3");
    svg.append(el);
  }
  return svg;
}
const copyIcon = (): SVGElement => icon([
  ["rect", { x: "3", y: "4.5", width: "8", height: "9.5", rx: "1.3" }],
  ["path", { d: "M6 4.5V3a1.3 1.3 0 0 1 1.3-1.3H12A1.3 1.3 0 0 1 13.3 3v8A1.3 1.3 0 0 1 12 12.3h-1" }]]);
const retryIcon = (): SVGElement => icon([
  ["path", { d: "M3 8a5 5 0 1 1 1.7 3.75" }], ["path", { d: "M3 11.8V8.1h3.7" }]]);
const rewindIcon = (): SVGElement => icon([
  ["path", { d: "M8.5 3 3.3 8l5.2 5" }], ["path", { d: "M13 3v10" }]]);
const branchIcon = (): SVGElement => icon([
  ["circle", { cx: "3.6", cy: "3.6", r: "1.5" }], ["circle", { cx: "3.6", cy: "12.4", r: "1.5" }],
  ["circle", { cx: "12.4", cy: "8", r: "1.5" }],
  ["path", { d: "M5 4.3 10.8 7.5" }], ["path", { d: "M5 11.7 10.8 8.5" }]]);

const PHASE_LABEL: Record<string, string> = {
  frame: "Frame", ingest: "Ingest", map: "Map", need: "Need", search: "Search",
  judge: "Judge", synthesise: "Synthesise", check_out: "Check out", check_in: "Check in",
  find: "Find",
};

export class Chat {
  readonly log = h("div", { class: "log", "aria-live": "polite", role: "log" });
  readonly plan = h("aside", { class: "plan", "aria-label": "Plan" });
  private rail = new Map<string, HTMLElement[]>();     // tool -> lines waiting for a result
  private cards = new Map<string, HTMLElement>();      // permission request id -> card
  private working: HTMLElement | null = null;
  private outcomeCard: HTMLElement | null = null;
  private lastUserText = "";                           // for Retry, after a failed turn

  constructor(private api: Api, private hooks: ChatHooks) {
    this.empty();
  }

  private empty(): void {
    clear(this.log, h("div", { class: "hint" },
      "Ask the librarian. It opens a session for anything longer than one search, and the plan ",
      "on the right shows where the thread is."));
  }

  private scroll(): void {
    this.log.scrollTop = this.log.scrollHeight;
  }

  private append(el: HTMLElement): void {
    this.log.querySelector(".hint")?.remove();
    if (this.working) this.log.insertBefore(el, this.working);
    else this.log.append(el);
    this.scroll();
  }

  /** A message plus its actions - hover-revealed, so the log itself stays
   *  quiet to read. Copy always works; retry only on a message a failed turn
   *  left dangling; rewind and branch only once a message's place in the
   *  resumable log is known (a replayed thread), rewind only where nothing
   *  after it has written to the vault. */
  private bubble(role: "user" | "assistant", text: string,
                 opts: { canRetry?: boolean; index?: number; minRewind?: number } = {}
                ): HTMLElement {
    const body = role === "user" ? h("div", { class: "msg user" }, text)
      : h("div", { class: "msg" }, render(text, this.hooks.openNote, { breaks: true }));
    const actions = [h("button", {
      class: "icon-btn", title: "Copy", "aria-label": "Copy message",
      onclick: () => { void navigator.clipboard.writeText(text).catch(() => undefined); },
    }, copyIcon())];
    if (role === "assistant") {
      // Text to speech, mode A: read this reply aloud (slot 5); again to stop.
      const speak: HTMLElement = h("button", {
        class: "icon-btn speak", title: "Read aloud", "aria-label": "Read aloud",
        onclick: () => void reader.toggle({ text }, speak),
      }, speakerIcon());
      actions.push(speak);
    }
    if (opts.canRetry) {
      actions.push(h("button", {
        class: "icon-btn", title: "Retry: send this again", "aria-label": "Retry",
        onclick: () => this.hooks.resend(text),
      }, retryIcon()));
    }
    if (opts.index !== undefined) {
      const canRewind = opts.index >= (opts.minRewind ?? 0);
      actions.push(h("button", {
        class: "icon-btn", disabled: !canRewind,
        title: canRewind ? "Rewind to here: removes this message and everything after it"
          : "Can't rewind here: something after this message already wrote to the library",
        "aria-label": "Rewind to here",
        onclick: () => {
          if (canRewind && confirm("Remove this message and everything after it? "
            + "This can't be undone.")) this.hooks.rewind(opts.index!);
        },
      }, rewindIcon()));
      actions.push(h("button", {
        class: "icon-btn", title: "Branch: start a new thread from here",
        "aria-label": "Branch from here", onclick: () => this.hooks.branch(opts.index!),
      }, branchIcon()));
    }
    return h("div", { class: `msg-wrap${role === "user" ? " user" : ""}` }, body,
      h("div", { class: "msg-actions" }, actions));
  }

  /** After a successful rewind: the thread stays the same one, just shorter. */
  applyRewind(messages: { role: string; text: string }[], minRewind: number): void {
    this.replay(messages, minRewind);
  }

  /** Reopening a thread: render what was actually said, in order, before the
   *  live stream picks up - the log itself, not the `handle()` event path
   *  (that path also flips `working`/rail state meant for a turn in progress). */
  private replay(messages: { role: string; text: string }[], minRewind = 0): void {
    clear(this.log);
    messages.forEach((m, i) => {
      const dangling = m.role === "user" && i === messages.length - 1;   // never answered
      this.log.append(this.bubble(m.role === "user" ? "user" : "assistant", String(m.text ?? ""),
        { canRetry: dangling, index: i, minRewind }));
      if (dangling) this.lastUserText = String(m.text ?? "");
    });
    if (!messages.length) this.empty();
    this.scroll();
  }

  setWorking(on: boolean): void {
    if (on && !this.working) {
      this.working = h("div", { class: "working" }, "The librarian is working…");
      this.log.append(this.working);
      this.scroll();
    } else if (!on && this.working) {
      this.working.remove();
      this.working = null;
    }
  }

  handle(event: Event): void {
    switch (event.type) {
      case "user":
        this.lastUserText = String(event.text ?? "");
        this.append(this.bubble("user", this.lastUserText));
        this.setWorking(true);
        break;
      case "text":
        this.append(this.bubble("assistant", String(event.text ?? "")));
        break;
      case "tool_call": {
        const tool = String(event.tool);
        const write = this.hooks.effectOf(tool) !== "read";
        const line = h("div", { class: `tool${write ? " write" : ""}` },
          h("code", {}, tool), " · ", h("span", { class: "dim" }, "running"));
        this.rail.set(tool, [...(this.rail.get(tool) ?? []), line]);
        this.append(line);
        break;
      }
      case "tool_result": {
        const tool = String(event.tool);
        const waiting = this.rail.get(tool) ?? [];
        const line = waiting.shift() ?? h("div", { class: "tool" }, h("code", {}, tool));
        const result = (event.result ?? {}) as Record<string, any>;
        clear(line, h("code", {}, tool), " · ", summarise(tool, result, this.hooks.openNote));
        if (result.error) line.classList.add("refused");
        if (!line.isConnected) this.append(line);
        if (result.session) this.hooks.onSession(result.session);
        // G3: a review's challenge that carries a failing input - only a person runs it.
        const runnable = (result.runnable ?? []) as { run_id: string; claim: string; input: string }[];
        if (runnable.length) this.append(h("div", { class: "note reviewed runnable" },
          "A review challenged these claims with a call that would show them wrong. Nothing has run.",
          h("ul", {}, runnable.map((r) => h("li", {}, `“${r.claim}” — `, h("code", {}, r.input), " ",
            this.runButton(r.run_id))))));
        break;
      }
      case "permission_request":
        this.permission(event);
        break;
      case "permission_decided": {
        const card = this.cards.get(String(event.id));
        if (card) {
          card.classList.add("done");
          const row = card.querySelector(".row");
          if (row) clear(row as HTMLElement, h("em", {}, sentence(String(event.reason ?? event.outcome))));
        }
        break;
      }
      case "reply_reviewed": {
        // §4 G3: the verdict on the last reply's note-backed claims, beside it, not in it.
        const challenged = (event.challenged ?? []) as { claim: string; note: string; counter_quote: string; reason: string }[];
        const held = Number(event.held ?? 0), unchecked = Number(event.unchecked ?? 0);
        const silent = (event.not_extracted ?? []) as string[];
        const over = Number(event.over_limit ?? 0);
        if (!held && !challenged.length && !unchecked && !event.status) break;
        this.append(h("div", { class: "note reviewed" },
          event.status ? `The review could not run (${event.status}).`
            : `Checked against the notes it cites: ${held} held${unchecked ? `, ${unchecked} unchecked` : ""}${challenged.length ? `, ${challenged.length} challenged` : ""}.`,
          challenged.length ? h("ul", {}, challenged.map((c: any) => h("li", {}, `⚑ “${c.claim}” — `,
            h("span", { class: "dim" }, c.counter_quote ? `${c.reason} [[${c.note}]] says: “${c.counter_quote}”`
              : `not found in [[${c.note}]]. ${c.reason}`),
            c.run_id ? h("div", {}, "Failing input: ", h("code", {}, String(c.input ?? "")), " ",
              this.runButton(String(c.run_id))) : null))) : null,
          silent.length ? h("div", { class: "dim small" }, `Nothing it says about ${silent.map((n) => `[[${n}]]`).join(", ")} was picked out to check.`) : null,
          over ? h("div", { class: "dim small" }, `${over} more claim${over === 1 ? " was" : "s were"} past the review limit (the effort setting) and not checked.`) : null,
          challenged.length ? h("div", { class: "dim small" }, "The librarian sees these challenges in its next reply.") : null));
        break;
      }
      case "turn_done":
        this.setWorking(false);
        if (event.stopped === "cancelled") {
          this.append(h("div", { class: "tool" }, "Reply stopped."));
        } else if (event.stopped === "max_steps") {
          this.append(h("div", { class: "error" }, "Stopped after the step limit for one turn. ",
            "Say “continue” to carry on, or ask for a summary of where it got to."));
        } else if (event.stopped === "provider_error") {
          this.append(h("div", { class: "error" }, `The model could not answer: ${event.error}. `,
            "Check the key and the model under + → Connections, then retry.", " ",
            h("button", { class: "icon-btn", title: "Retry: send this again",
              "aria-label": "Retry", onclick: () => this.hooks.resend(this.lastUserText) },
              retryIcon())));
        }
        this.sessionOutcome((event.session as Session) ?? null);
        this.hooks.onSession((event.session as Session) ?? null);
        break;
      case "error":
        this.setWorking(false);
        this.append(h("div", { class: "error" }, String(event.error)));
        break;
      case "conversation_reset":
        this.rail.clear();
        this.setWorking(false);
        this.empty();
        this.hooks.onSession(null);
        break;
      case "session_attached": {
        const session = (event.session as any) ?? null;
        this.replay((session?.messages ?? []) as { role: string; text: string }[],
          Number(session?.min_rewind_index ?? 0));
        this.append(h("div", { class: "tool" }, "continuing the thread ",
          h("code", {}, String(session?.session ?? ""))));
        // A question from before this thread was reopened has no live turn
        // still waiting on it (that call, if any, ended with the process
        // that was running it) - answering it now only records the answer;
        // it takes a fresh message to actually carry the thread on. Still
        // worth surfacing: an unanswered question is exactly what silently
        // stalled a resumed thread before.
        for (const q of (session?.questions ?? []) as any[]) {
          if (q.answer === null || q.answer === undefined) {
            this.questionCard({ type: "question_asked", question_id: q.id, question: q.question,
              kind: q.kind, options: q.options, session: session?.session } as unknown as Event);
          }
        }
        this.hooks.onSession(session as Session);
        break;
      }
      case "question_asked":
        this.questionCard(event);
        break;
      case "question_answered": {
        // A question now really blocks the turn until answered (see
        // Waiters in tools/sessions.py), so the plan must show it - and
        // clear it once answered - without waiting for the (now-delayed)
        // tool result or the next turn_done. Answered from elsewhere (the
        // Plan panel, another tab): this card still needs marking done.
        const card = this.cards.get(`q:${String(event.question_id ?? "")}`);
        if (card && !card.classList.contains("done")) {
          card.classList.add("done");
          const row = card.querySelector(".row");
          if (row) clear(row as HTMLElement, h("em", {}, event.answered ? "Answered elsewhere." : "Timed out unanswered."));
        }
        const sessionId = String(event.session ?? "");
        if (sessionId) {
          this.api.tool("session_status", {}, sessionId)
            .then((out) => { if (!out.error) this.hooks.onSession(out as Session); })
            .catch(() => undefined);
        }
        break;
      }
    }
  }

  /** The coverage ledger (R13): each asked topic, its brief and verdict, and what was
   *  kept for it - context finds counted apart, since they do not answer it. */
  private coverage(session: Session): HTMLElement | null {
    const ledger = ((session?.completion?.ledger ?? session?.coverage) ?? []) as any[];
    if (!ledger.length) return null;
    const mark: Record<string, string> = { covered: "✓ covered", partial: "◐ partial", gap: "✗ gap",
      open: "○ open", "no brief": "○ no brief yet" };
    return h("div", { class: "coverage" }, h("h3", {}, "Coverage"),
      h("ul", {}, ledger.map((r) => h("li", {}, h("strong", {}, String(r.topic)),
        ` · ${r.brief || "no brief"} · ${mark[r.verdict] ?? r.verdict}`,
        (r.kept ?? []).length ? h("span", { class: "dim" }, ` · ${r.kept.length} kept`) : null,
        (r.context ?? []).length ? h("span", { class: "dim" }, ` · ${r.context.length} context only`) : null))));
  }

  /** R11: a spent budget with the phase unfinished is the person's to extend. */
  private extendBudget(session: Session): HTMLElement | null {
    if (!session?.budget_spent || session.status !== "open") return null;
    return h("button", { class: "ghost", title: "Give this phase ten more calls",
      onclick: async (e: globalThis.Event) => {
        (e.currentTarget as HTMLButtonElement).disabled = true;
        try {
          const out = await this.api.tool("extend_budget", { add: 10 }, String(session.session ?? ""));
          if (out.error) throw new Error(String(out.detail ?? out.error));
          if (out.session) this.hooks.onSession(out.session as Session);
        } catch (err) {
          this.append(h("div", { class: "error" }, `Could not extend the budget: ${(err as Error).message}`));
        }
      } }, "Extend budget (+10 calls)");
  }

  private sessionOutcome(session: Session): void {
    if (!session) return;
    this.outcomeCard?.remove();
    if (session.status === "closed") {
      this.outcomeCard = h("div", { class: "session-outcome closed", role: "status" },
        h("strong", {}, "Thread closed"),
        session.summary ? h("div", {}, String(session.summary)) : null,
        session.gaps ? h("div", { class: "dim" }, `Gaps: ${session.gaps}`) : null,
        this.coverage(session));
      this.append(this.outcomeCard);
      return;
    }
    const openItems = (session.open_items ?? []) as string[];
    const parked = session.status === "parked";
    this.outcomeCard = h("div", { class: "session-outcome open", role: "status" },
      h("strong", {}, `${parked ? "Thread parked" : "Thread still open"} · ${String(session.phase ?? "work in progress")}`),
      openItems.length ? h("ul", {}, openItems.slice(0, 5).map((item) => h("li", {}, item))) : null,
      session.next ? h("p", {}, String(session.next)) : null,
      this.coverage(session),
      this.extendBudget(session),
      parked ? h("p", { class: "dim" }, "Reopen this thread from Sessions to continue.")
        : h("button", { class: "ghost", onclick: () => this.hooks.continueSession() }, "Continue from next step"));
    this.append(this.outcomeCard);
  }

  /** G3: a person's "Run it" - one function call in a Docker sandbox with no network. The
   *  verdict (confirmed / not confirmed / could not run) replaces the button. */
  private runButton(runId: string): HTMLElement {
    const out = h("span", { class: "run-claim" });
    const button = h("button", { class: "ghost", title: "Runs this one call in a Docker container with no network and the repository read-only. Needs Docker Desktop running.",
      onclick: async () => {
        (button as HTMLButtonElement).disabled = true;
        clear(out, h("span", { class: "dim" }, "running in the sandbox…"));
        try {
          const r = await this.api.post("/api/claims/run", { id: runId });
          if (r.error) clear(out, h("span", { class: "error" }, String(r.detail ?? r.error)));
          else clear(out, h("strong", {}, String(r.verdict).replace(/_/g, " ")), ` — ${r.detail} (${r.version})`);
        } catch (e) {
          clear(out, h("span", { class: "error" }, (e as Error).message));
        }
      } }, "Run it");
    clear(out, button);
    return out;
  }

  private permission(event: Event): void {
    const args = (event.arguments ?? {}) as Record<string, string>;
    const preview = (event.preview ?? null) as Record<string, string> | null;
    // A previewed change (project_edit) shows its diff, not its raw arguments.
    const detail = preview ? `${preview.path ?? ""}` :
      Object.entries(args).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(" · ");
    const diff = preview?.diff ? h("pre", { class: "diff" }, String(preview.diff).split("\n").map((line) =>
      h("span", { class: line.startsWith("+") && !line.startsWith("+++") ? "add"
        : line.startsWith("-") && !line.startsWith("---") ? "del" : "" }, line + "\n"))) : null;
    const answer = (value: string) => async () => {
      try {
        await this.api.post("/api/permission", { id: event.id, answer: value });
      } catch (e) {
        this.append(h("div", { class: "error" }, `Could not answer: ${(e as Error).message}`));
      }
    };
    const card = h("div", { class: "perm", role: "group", "aria-label": "Permission needed" },
      h("strong", {}, "Permission needed"), " · ", h("code", {}, String(event.tool)),
      ` wants to ${event.effect === "read" ? "run" : "write"}`,
      detail ? h("div", { class: "dim" }, detail) : null,
      diff,
      event.always_ask ? h("div", { class: "dim" }, "Asked before every change: allowing it applies this one only.") : null,
      h("div", { class: "row" },
        h("button", { onclick: answer("allow_once") }, event.always_ask ? "Apply this change" : "Allow once"),
        event.always_ask ? null : h("button", { onclick: answer("allow_session") }, "Allow for this session"),
        h("button", { onclick: answer("deny") }, "Deny")));
    this.cards.set(String(event.id), card);
    this.append(card);
    (card.querySelector("button") as HTMLButtonElement | null)?.focus();
  }

  /** A question the session asked (`ask_user` / a phase's own required field,
   *  e.g. BRIEF_REQUIRED) - the same blocking handshake as a permission
   *  request (`Waiters` in tools/sessions.py mirrors `Broker.check()`), so it
   *  gets the same treatment: a card right here, impossible to miss, instead
   *  of a silent wait only the Plan panel showed. Answering it wakes the
   *  turn's own blocked call directly. */
  private questionCard(event: Event): void {
    const id = String(event.question_id ?? "");
    if (!id || this.cards.has(`q:${id}`)) return;   // already shown (a reconnect, say)
    const options = (event.options ?? null) as string[] | null;
    const sessionId = String(event.session ?? "");
    const row = h("div", { class: "row" });
    const send = async (value: string) => {
      if (!value.trim()) return;
      clear(row, h("em", {}, "Answering…"));
      try {
        const out = await this.api.tool("answer", { question_id: id, answer: value }, sessionId);
        if (out.error) throw new Error(String(out.detail ?? out.error));
        clear(row, h("em", {}, out.resumed
          ? `Answered: “${value}”` : `Recorded: “${value}” - send a message to carry the thread on.`));
        card.classList.add("done");
        if (out.session) this.hooks.onSession(out.session);
      } catch (e) {
        clear(row, h("div", { class: "error" }, (e as Error).message),
          h("button", { onclick: () => void send(value) }, "Retry"));
      }
    };
    if (options && options.length) {
      row.append(...options.map((o) => h("button", { onclick: () => void send(o) }, o)));
    } else {
      const input = h("input", { type: "text", "aria-label": String(event.question ?? ""),
        placeholder: "Your answer" }) as HTMLInputElement;
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); void send(input.value); }
      });
      row.append(input, h("button", { onclick: () => void send(input.value) }, "Answer"));
    }
    const offering = offeringAsked(event);
    if (offering && this.hooks.openOffering) {
      row.append(h("button", { class: "ghost", onclick: () => this.hooks.openOffering!(offering) }, "Read the draft"));
    }
    const card = h("div", { class: "perm", role: "group", "aria-label": "Question" },
      h("strong", {}, "The librarian is asking"), " · ",
      h("span", { class: "dim" }, String(event.kind ?? "clarify")),
      h("div", {}, String(event.question ?? "")), row);
    this.cards.set(`q:${id}`, card);
    this.append(card);
    (card.querySelector("input, button") as HTMLElement | null)?.focus();
  }

  // -- the plan -----------------------------------------------------------
  renderPlan(session: Session): void {
    if (!session) {
      clear(this.plan,
        h("p", { class: "dim" }, "No thread yet. Sessions ▾ picks one up; the librarian opens one when it needs to."));
      return;
    }
    const phases: string[] = session.phases ?? [];
    const current = phases.indexOf(session.phase);
    const questions = (session.questions ?? []).filter((q: any) => q.answer === null || q.answer === undefined);
    const libraryItems = (session.library_items ?? []) as any[];
    const libraryCounts = session.library_item_counts ?? libraryItems.reduce((counts: Record<string, number>, item) => {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
      return counts;
    }, {});
    const libraryItemCount = Number(session.library_item_count ?? libraryItems.length);
    clear(this.plan,
      h("h3", {}, "Phases"),
      h("ul", {}, phases.map((p, i) => h("li", { class: i > current ? "dim" : "" },
        `${i < current ? "☑" : i === current ? "◐" : "○"} ${PHASE_LABEL[p] ?? p}`,
        i === current && session.budget_left !== undefined
          ? h("span", { class: "dim" }, ` · ${session.budget_left} calls left`) : null))),
      this.extendBudget(session),
      questions.length ? h("h3", {}, "Waiting for you") : null,
      questions.map((q: any) => this.question(session, q)),
      h("h3", {}, "Next"),
      h("p", {}, String(session.next ?? "")),
      (session.open_items ?? []).length ? h("h3", {}, "Open") : null,
      (session.open_items ?? []).length
        ? h("ul", {}, (session.open_items as string[]).map((t) => h("li", {}, t))) : null,
      this.coverage(session),
      Object.keys(session.briefs ?? {}).length ? h("h3", {}, "Briefs") : null,
      Object.entries(session.briefs ?? {}).map(([id, b]: [string, any]) =>
        h("p", {}, h("strong", {}, id), ` ${b.need ?? ""}`, b.status === "closed" ? h("span", { class: "dim" }, " · closed") : null)),
      libraryItemCount ? h("h3", {}, `Library sources · ${libraryItemCount}`) : null,
      libraryItemCount ? h("p", { class: "dim" }, Object.entries(libraryCounts)
        .map(([status, count]) => `${count} ${status}`).join(" · ")) : null,
      libraryItems.length ? h("ul", {}, libraryItems.slice(-12).map((item) => h("li", {},
        item.path ? link(item.path, String(item.source ?? item.path), this.hooks.openNote)
          : String(item.source ?? item.id), ` · ${item.status}`))) : null,
      (session.checkpoints ?? []).length ? h("h3", {}, `Checkpoint, round ${(session.checkpoints ?? []).length}`) : null,
      (session.checkpoints ?? []).slice(-1).map((c: any) => h("ul", {},
        h("li", {}, `Learned: ${c.learned ?? ""}`),
        (c.subthreads ?? []).length ? h("li", {}, `Open: ${(c.subthreads ?? []).length} sub-threads`) : null,
        (c.next_targets ?? []).length ? h("li", {}, `Next: ${(c.next_targets ?? []).join(", ")}`) : null)),
      (session.writes ?? []).length ? h("h3", {}, "Written") : null,
      (session.writes ?? []).length ? h("ul", {}, (session.writes as any[]).map((w) =>
        h("li", {}, w.path ? link(w.path, pathName(w.path), this.hooks.openNote) : w.tool))) : null);
  }

  private question(session: Session, q: any): HTMLElement {
    const box = h("div", { class: "question" }, h("p", {}, q.question));
    const send = async (answer: string) => {
      try {
        const out = await this.api.tool("answer", { question_id: q.id, answer }, session?.session ?? "");
        if (out.error) throw new Error(String(out.detail ?? out.error));
        this.hooks.onSession(out.session ?? session);
      } catch (e) {
        box.append(h("div", { class: "error" }, (e as Error).message));
      }
    };
    const offering = offeringAsked(q);
    if ((q.options ?? []).length) {
      box.append(h("div", { class: "row" }, (q.options as string[]).map((o) =>
        h("button", { onclick: () => send(o) }, o)),
        offering && this.hooks.openOffering
          ? h("button", { class: "ghost", onclick: () => this.hooks.openOffering!(offering) }, "Read the draft") : null));
    } else {
      const input = h("input", { type: "text", "aria-label": q.question, placeholder: "Your answer" }) as HTMLInputElement;
      box.append(h("div", { class: "row" }, input,
        h("button", { onclick: () => input.value.trim() && send(input.value.trim()) }, "Answer")));
    }
    return box;
  }
}

function pathName(path: string): string {
  return path.split("/").pop()!.replace(/\.md$/, "");
}

function sentence(text: string): string {
  const t = text.trim();
  return t ? t[0].toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? "" : ".") : "";
}

/** One past-tense line for a tool result. */
export function summarise(tool: string, r: Record<string, any>, openNote: (name: string) => void): Node {
  if (r.error === "refused") return h("span", {}, `refused (${r.refused}): ${r.detail ?? ""}`);
  if (r.error) return h("span", {}, `failed: ${r.detail ?? r.error}`);
  if (Array.isArray(r.results)) {
    const found = r.results.slice(0, 3).filter((x: any) => x.name);
    const frag = h("span", {}, `${r.results.length} result${r.results.length === 1 ? "" : "s"}`,
      r.verdict ? ` · ${r.verdict}` : "", found.length ? " · " : "");
    found.forEach((x: any, i: number) => {
      if (i) frag.append(", ");
      frag.append(link(x.fields?.path ?? x.name, x.name, openNote));
    });
    return frag;
  }
  if (r.promoted && typeof r.promoted === "string") return h("span", {}, "wrote ", link(r.promoted, pathName(r.promoted), openNote));
  if (r.staged && typeof r.staged === "string") return h("span", {}, `staged ${pathName(r.staged)}`);
  if (r.opened) return h("span", {}, `opened a thread (${(r.phases ?? []).join(" → ")})`);
  if (r.moved) return h("span", {}, `moved to ${PHASE_LABEL[r.moved] ?? r.moved}`);
  if (r.moved === false) return h("span", {}, "stayed: the phase is not finished");
  if (r.question_id && r.answer !== undefined) return h("span", {}, `asked and answered: “${String(r.answer).slice(0, 80)}”`);
  if (r.needs_person || r.question_id) return h("span", {}, "asked you a question (see the plan)");
  if (tool === "get_note" && r.name) return h("span", {}, "read ", link(r.path ?? r.name, r.name, openNote));
  if (r.path && typeof r.path === "string") return h("span", {}, "wrote ", link(r.path, pathName(r.path), openNote));
  return h("span", {}, "done");
}
