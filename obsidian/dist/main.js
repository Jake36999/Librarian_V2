"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/main.ts
var main_exports = {};
__export(main_exports, {
  default: () => LibrarianPlugin
});
module.exports = __toCommonJS(main_exports);
var import_obsidian = require("obsidian");

// ../ui/src/dom.ts
var OWNED_PREFIX = "lib-";
function own(token2) {
  return token2.startsWith(OWNED_PREFIX) || token2.startsWith("librarian-") ? token2 : OWNED_PREFIX + token2;
}
var liveMounts = /* @__PURE__ */ new Set();
function claimInstance() {
  let n = 1;
  while (liveMounts.has(n)) n++;
  liveMounts.add(n);
  return { n, id: (base) => n === 1 ? base : `${base}-${n}`, release: () => {
    liveMounts.delete(n);
  } };
}
function cls(value) {
  return value.split(/\s+/).filter(Boolean).map(own).join(" ");
}
function sel(selector) {
  return selector.replace(/\.(-?[A-Za-z_][\w-]*)/g, (_m, name) => `.${own(name)}`);
}
function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === void 0 || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2), value);
    } else if (key === "class") {
      el.className = cls(String(value));
    } else {
      el.setAttribute(key, value === true ? "" : String(value));
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === void 0 || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return el;
}
var $ = (root, sel2) => root.querySelector(sel2);
function clear(el, ...children) {
  el.replaceChildren();
  for (const child of children.flat()) {
    if (child === null || child === void 0 || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return el;
}
function when(iso) {
  const text = String(iso ?? "");
  return text.slice(0, 16).replace("T", " ");
}

// ../ui/src/commands.ts
var COMMANDS = {
  settings: "Open Settings",
  search: "Focus Search",
  staging: "Open Staging",
  sessions: "Open Sessions",
  checkpoints: "Open Checkpoints",
  intake: "Set up sources for this library",
  "clear-enrichment-backlog": "Process enrichment backlog",
  "deep-read-staged": "Deep-read staged sources",
  "review-conversation": "Suggest sources from this conversation",
  "review-due": "Review due concepts",
  "weekly-review": "Draft weekly pursuit review",
  approved: "Process approved sources",
  retry: "Retry steps waiting for a model",
  resume: "Resume interrupted batch",
  stop: "Stop after current stage"
};
function preference(key, fallback = "") {
  try {
    return localStorage.getItem("librarian.ui." + key) ?? fallback;
  } catch {
    return fallback;
  }
}
function remember(key, value) {
  localStorage.setItem("librarian.ui." + key, value);
}
function shortcutPage(native, open, api, state) {
  const panel = h("div"), status = h("p", { role: "status" });
  const options = Array.from("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789");
  const controls = /* @__PURE__ */ new Map();
  const explain = (id, text, available = true) => {
    const control = controls.get(id);
    control.hint.textContent = text;
    control.button.disabled = !available;
  };
  const row = (id, label) => {
    const binding = h(
      "select",
      { "aria-label": "Shortcut for " + label },
      h("option", { value: "" }, "Unassigned"),
      options.map((key) => h("option", { value: key }, "Alt + Shift + " + key))
    );
    binding.value = preference("key." + id);
    binding.onchange = () => {
      const conflict = binding.value && Object.keys(COMMANDS).find((other) => other !== id && preference("key." + other) === binding.value);
      if (conflict) {
        status.textContent = "Already assigned to " + COMMANDS[conflict];
        binding.value = preference("key." + id);
        return;
      }
      try {
        remember("key." + id, binding.value);
        status.textContent = "Shortcut saved.";
      } catch {
        status.textContent = "Could not save this browser preference.";
        binding.value = preference("key." + id);
      }
    };
    const hint = h("small"), button = h("button", { class: "ghost", onclick: (e) => {
      e.stopPropagation();
      open(id);
    } }, "Open");
    controls.set(id, { hint, button });
    return h("div", { class: "settings-role" }, h("div", {}, h("strong", {}, label), hint), native ? null : binding, button);
  };
  clear(
    panel,
    h("p", {}, native ? "Assign keys in Obsidian Settings \u2192 Hotkeys. Search for Librarian." : "Shortcuts apply to this browser address. Select Unassigned to clear a binding. Workflow shortcuts open the action for review."),
    status,
    Object.entries(COMMANDS).map(([id, label]) => row(id, label))
  );
  const batchKeys = ["approved", "retry", "resume", "stop"];
  batchKeys.forEach((id) => explain(id, "Checking this library\u2019s queue\u2026", false));
  void api.tool("batch_status", {}).then((b) => {
    if (b.error) throw Error();
    const running = b.status === "running";
    explain("approved", `${b.waiting ?? 0} approved sources waiting.`, !running && b.waiting > 0);
    explain("retry", `${b.waiting_on_model ?? 0} sources waiting for a model.`, !running && b.waiting_on_model > 0);
    const resume = ["failed", "cancelled", "interrupted"].includes(b.status) && b.items?.some((i) => i.status === "processing");
    explain("resume", resume ? "Unfinished run: " + b.run : "No interrupted batch to resume.", !!resume);
    explain("stop", running ? "Active batch: " + b.run : "No batch running.", running);
  }).catch(() => batchKeys.forEach((id) => explain(id, "Queue status unavailable.", false)));
  explain("review-conversation", state.session?.session ? "Conversation: " + state.session.session : "Start a conversation first.", !!state.session?.session);
  explain("weekly-review", "Choose the pursuit in the action panel before starting.");
  void api.tool("understanding_due", {}).then((out) => {
    if (Array.isArray(out.due)) explain("review-due", `${out.due.length} due review tasks. Opens up to five parked sessions and skips existing reviews.`, out.due.length > 0);
  }).catch(() => explain("review-due", "Due count unavailable."));
  for (const [id, status2] of [["deep-read-staged", "staged"], ["clear-enrichment-backlog", "queued"]]) {
    void api.tool("staging_list", { kind: "source", status: status2, limit: 1 }).then((out) => {
      if (typeof out.total === "number") explain(id, `${out.total} sources in the ${status2} queue. Review the action before starting.`);
    }).catch(() => explain(id, "Queue count unavailable."));
  }
  return panel;
}

// ../ui/src/speech.ts
var NS = "http://www.w3.org/2000/svg";
function icon(paths, size = 13) {
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of paths) {
    const el = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", "currentColor");
    el.setAttribute("stroke-width", "1.3");
    svg.append(el);
  }
  return svg;
}
var speakerIcon = (size = 13) => icon([
  ["path", { d: "M2.5 6h2.3L8 3.2v9.6L4.8 10H2.5z" }],
  ["path", { d: "M10.4 5.6a3.2 3.2 0 0 1 0 4.8" }],
  ["path", { d: "M12.2 3.8a5.8 5.8 0 0 1 0 8.4" }]
], size);
var stopIcon = (size = 13) => icon([
  ["rect", { x: "4", y: "4", width: "8", height: "8", rx: "1" }]
], size);
var runIcon = (size = 13) => icon([["path", { d: "M5 3.2v9.6L12.6 8z" }]], size);
var Reader = class {
  constructor() {
    this.api = null;
    this.warn = () => void 0;
    this.audio = null;
    this.button = null;
    this.title = "";
    this.run = 0;
  }
  init(api, warn) {
    this.api = api;
    this.warn = warn;
  }
  /** Start reading `source` with `button` showing it; the same button again stops it. */
  async toggle(source, button, size = 13) {
    if (this.button === button) {
      this.stop();
      return;
    }
    this.stop();
    const run = ++this.run;
    this.button = button;
    this.title = button.title;
    button.dataset.readLabel = button.getAttribute("aria-label") ?? this.title;
    button.setAttribute("aria-label", "Stop reading aloud");
    button.setAttribute("aria-pressed", "true");
    button.classList.add(cls("speaking"));
    button.replaceChildren(stopIcon(size));
    try {
      const plan = await this.api.post("/api/tts/plan", source);
      if (run !== this.run) return;
      let next = this.api.post("/api/tts/chunk", { plan: plan.plan, index: 0 });
      for (let i = 0; i < plan.count && run === this.run; i++) {
        const got = await next;
        if (run !== this.run) break;
        if (i + 1 < plan.count) next = this.api.post("/api/tts/chunk", { plan: plan.plan, index: i + 1 });
        button.title = `Reading part ${i + 1} of ${plan.count} - click to stop`;
        await this.play(got.audio, run);
      }
    } catch (e) {
      if (run === this.run) this.warn(`Read aloud: ${e.message}`);
    }
    if (run === this.run) this.reset(size);
  }
  /** Plays one part. A part that cannot play is said, never passed over in silence (a
   *  refused source once made every reading end at once with no sound and no message). */
  play(src, run) {
    return new Promise((resolve2, reject) => {
      if (run !== this.run) {
        resolve2();
        return;
      }
      const audio = new Audio(src);
      this.audio = audio;
      audio.onended = () => resolve2();
      audio.onerror = () => reject(new Error("the audio could not be played in this browser"));
      audio.play().catch((e) => reject(new Error(
        e.name === "NotAllowedError" ? "the browser blocked playback - click the speaker again" : `the audio could not be played (${e.message})`
      )));
    });
  }
  stop() {
    this.run++;
    this.audio?.pause();
    this.audio = null;
    this.reset();
  }
  reset(size = 13) {
    if (this.button) {
      this.button.classList.remove(cls("speaking"));
      this.button.replaceChildren(speakerIcon(size));
      this.button.title = this.title;
      this.button.setAttribute("aria-label", this.button.dataset.readLabel ?? this.title);
      this.button.setAttribute("aria-pressed", "false");
    }
    this.button = null;
  }
};
var reader = new Reader();

// ../ui/src/api.ts
var ApiError = class extends Error {
  constructor(status, body) {
    super(String(body.error ?? `HTTP ${status}`));
    this.status = status;
    this.body = body;
  }
};
var Api = class {
  constructor(opts) {
    this.opts = opts;
  }
  async request(method, path2, body, signal) {
    const response = await fetch(this.opts.base + path2, {
      method,
      signal,
      headers: { "Content-Type": "application/json", "X-Librarian-Token": this.opts.token },
      body: body === void 0 ? void 0 : JSON.stringify(body)
    });
    const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }
  get(path2, signal) {
    return this.request("GET", path2, void 0, signal);
  }
  post(path2, body = {}) {
    return this.request("POST", path2, body);
  }
  /** The composer's paperclip: raw bytes, not JSON - too large and the wrong shape. */
  async attach(file, dir = "Inbox") {
    const qs = `dir=${encodeURIComponent(dir)}&name=${encodeURIComponent(file.name)}`;
    const response = await fetch(`${this.opts.base}/api/attach?${qs}`, {
      method: "POST",
      headers: { "X-Librarian-Token": this.opts.token },
      body: file
    });
    const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }
  /** A person's own tool call, at their tier, through the core's registry. */
  tool(name, args = {}, session = "") {
    return this.post(`/api/tool/${encodeURIComponent(name)}`, { arguments: args, session });
  }
  /** The event stream. Reconnects from an epoch-bound sequence cursor. */
  events(cursor, onEvent, onStatus) {
    let last = Number.isInteger(cursor?.last_seq) && (cursor?.last_seq ?? -1) >= 0 ? Number(cursor?.last_seq) : 0;
    let epoch = typeof cursor?.epoch === "string" ? cursor.epoch : "";
    let source = null;
    let closed = false;
    let reconnect = 0;
    const open = () => {
      const url = `${this.opts.base}/api/events?token=${encodeURIComponent(this.opts.token)}&since=${last}&epoch=${encodeURIComponent(epoch)}`;
      source = new EventSource(url);
      source.onopen = () => onStatus(true);
      source.onmessage = () => void 0;
      source.onerror = () => {
        onStatus(false);
        source?.close();
        if (!closed) reconnect = window.setTimeout(open, 1500);
      };
      const handle = (message) => {
        const event = JSON.parse(message.data);
        if (event.type === "resync_required") {
          if (typeof event.epoch === "string") epoch = event.epoch;
          if (Number.isInteger(event.seq) && event.seq >= 0) last = event.seq;
          onEvent(event);
          return;
        }
        if (event.seq <= last) return;
        if (typeof event.epoch === "string" && event.epoch) epoch = event.epoch;
        last = event.seq;
        onEvent(event);
      };
      for (const type of EVENT_TYPES) source.addEventListener(type, handle);
    };
    open();
    return () => {
      closed = true;
      window.clearTimeout(reconnect);
      source?.close();
    };
  }
};
var EVENT_TYPES = [
  "user",
  "text",
  "tool_call",
  "tool_result",
  "turn_done",
  "error",
  "stopped",
  "permission_request",
  "permission_decided",
  "mode_changed",
  "tiers_changed",
  "session_attached",
  "conversation_reset",
  "person_acted",
  "question_asked",
  "question_answered",
  "action_started",
  "action_progress",
  "action_done",
  "library_switched",
  "reply_reviewed",
  "checkpoint_created",
  "checkpoint_resolved",
  "route_health_changed",
  "workflow_preflight",
  "resync_required"
];

// ../ui/src/attach.ts
var AttachPanel = class {
  constructor(pop, api, insert, onFileAttached = () => {
  }) {
    this.pop = pop;
    this.api = api;
    this.insert = insert;
    this.onFileAttached = onFileAttached;
    this.browsing = "";
    this.status = h("p", { class: "dim" });
    this.fileInput = h("input", {
      type: "file",
      hidden: true,
      "aria-label": "Choose a file to attach"
    });
    this.fileInput.addEventListener("change", () => void this.chosen());
    document.body.append(this.fileInput);
  }
  /** MF-008: the hidden picker lives on <body>; a remount must not leave it. */
  dispose() {
    this.fileInput.remove();
  }
  /** Called each time the popover opens: start back at the vault root. */
  render() {
    this.browsing = "";
    void this.paint();
  }
  async chosen() {
    const file = this.fileInput.files?.[0];
    this.fileInput.value = "";
    if (!file) return;
    clear(this.status, `Attaching ${file.name}\u2026`);
    try {
      const out = await this.api.attach(file);
      const raw = `\`${out.path}\``;
      this.insert(raw);
      this.onFileAttached(file, raw);
      clear(this.status, "");
    } catch (e) {
      clear(this.status, h("span", { class: "error" }, `Could not attach ${file.name}: ${e.message}`));
    }
  }
  item(label, action) {
    return h("button", { class: "menuitem", role: "menuitem", onclick: action }, label);
  }
  async paint() {
    const folder = h("div", {}, h("p", { class: "dim" }, "Loading\u2026"));
    clear(
      this.pop.el,
      this.item("\u{1F4CE} Attach a file from this computer", () => {
        this.pop.show(false);
        this.fileInput.click();
      }),
      this.status,
      h("h4", { class: "gap" }, "Link a note or folder"),
      folder
    );
    try {
      const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(this.browsing)}`);
      const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
      clear(
        folder,
        h("div", { class: "folder-path" }, `/${listing.dir}`),
        up !== null ? this.item(
          `\u2191 ${up ? up.split("/").pop() : "the vault"}`,
          () => {
            this.browsing = up;
            void this.paint();
          }
        ) : null,
        listing.dir ? this.item("Link this folder", () => {
          this.pop.show(false);
          this.insert(`\`${listing.dir}/\``);
        }) : null,
        listing.entries.map((e) => e.kind === "dir" ? this.item(`${e.name}/`, () => {
          this.browsing = e.path;
          void this.paint();
        }) : this.item(e.name, () => {
          this.pop.show(false);
          this.insert(`[[${e.name}]]`);
        })),
        listing.entries.length ? null : h("p", { class: "dim" }, "No notes here.")
      );
    } catch (e) {
      clear(folder, h("p", { class: "error" }, e.message));
    }
  }
};

// ../ui/src/markdown.ts
function wikiTarget(inner) {
  const [ref, alias] = inner.split("|");
  const target = ref.split("#")[0].trim();
  const label = (alias ?? target.split("/").pop() ?? target).trim();
  return { target, label: label || target };
}
function link(target, label, open) {
  return h("a", {
    class: "wl",
    href: "#",
    title: target,
    onclick: ((e) => {
      e.preventDefault();
      open(target);
    })
  }, label);
}
var INLINE = /(`[^`]+`|!?\[\[[^\]]+\]\]|!?\[[^\]]*\]\([^)\s]+\)|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*\s][^*]*\*|(?<![\w])_[^_\s][^_]*_(?![\w])|https?:\/\/[^\s<>)\]]+)/g;
function inline(text, open) {
  const out = document.createDocumentFragment();
  let at = 0;
  for (const match of text.matchAll(INLINE)) {
    const index = match.index ?? 0;
    if (index > at) out.append(text.slice(at, index));
    out.append(token(match[0], open));
    at = index + match[0].length;
  }
  if (at < text.length) out.append(text.slice(at));
  return out;
}
function token(t, open) {
  if (t.startsWith("`")) return h("code", {}, t.slice(1, -1));
  if (t.startsWith("![[") || t.startsWith("[[")) {
    const { target, label } = wikiTarget(t.replace(/^!/, "").slice(2, -2));
    return link(target, label, open);
  }
  if (t.startsWith("![")) {
    const alt = t.slice(2, t.indexOf("]"));
    return h("span", { class: "dim" }, `[image${alt ? `: ${alt}` : ""}]`);
  }
  if (t.startsWith("[")) {
    const close = t.indexOf("](");
    const label = t.slice(1, close);
    const target = t.slice(close + 2, -1);
    if (/^https?:\/\//i.test(target)) {
      return h("a", { href: target, target: "_blank", rel: "noreferrer noopener" }, inline(label, open));
    }
    if (/^[a-z][a-z0-9+.-]*:/i.test(target)) return document.createTextNode(label);
    return link(decodeURIComponent(target).replace(/\.md$/i, ""), label || target, open);
  }
  if (t.startsWith("**") || t.startsWith("__")) return h("strong", {}, inline(t.slice(2, -2), open));
  if (t.startsWith("~~")) return h("s", {}, inline(t.slice(2, -2), open));
  if (t.startsWith("*") || t.startsWith("_")) return h("em", {}, inline(t.slice(1, -1), open));
  if (/^https?:\/\//i.test(t)) return h("a", { href: t, target: "_blank", rel: "noreferrer noopener" }, t);
  return document.createTextNode(t);
}
function splitFrontmatter(text) {
  const normal = text.replace(/\r/g, "");
  if (!normal.startsWith("---\n")) return { props: [], body: normal };
  const end = normal.indexOf("\n---", 4);
  if (end < 0) return { props: [], body: normal };
  const props = [];
  for (const line of normal.slice(4, end).split("\n")) {
    const item = /^\s*-\s+(.*)$/.exec(line);
    if (item && props.length) {
      const last = props[props.length - 1];
      last[1] = last[1] ? `${last[1]}, ${unquote(item[1])}` : unquote(item[1]);
      continue;
    }
    const kv = /^([A-Za-z0-9_ -]+):\s*(.*)$/.exec(line);
    if (kv) props.push([kv[1].trim(), unquote(kv[2]).replace(/^\[(.*)\]$/, "$1")]);
  }
  const rest = normal.slice(end + 4);
  return { props, body: rest.replace(/^[^\n]*\n/, "") };
}
function unquote(v) {
  const t = v.trim();
  return /^(["']).*\1$/.test(t) ? t.slice(1, -1) : t;
}
function render(text, open, opts = {}) {
  const out = document.createDocumentFragment();
  let body = text.replace(/\r/g, "");
  if (opts.frontmatter) {
    const split = splitFrontmatter(body);
    body = split.body;
    if (split.props.length) {
      out.append(h("table", { class: "props" }, h("tbody", {}, split.props.map(([k, v]) => h("tr", {}, h("th", {}, k), h("td", {}, inline(v, open)))))));
    }
  }
  const lines = body.split("\n");
  let i = 0;
  let para = [];
  const flush = () => {
    if (!para.length) return;
    const p = h("p");
    if (opts.breaks) {
      para.forEach((line, n) => {
        if (n) p.append(h("br"));
        p.append(inline(line, open));
      });
    } else {
      p.append(inline(para.join(" "), open));
    }
    out.append(p);
    para = [];
  };
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      flush();
      i++;
      continue;
    }
    const fence = /^\s*(```|~~~)/.exec(line);
    if (fence) {
      flush();
      const code = [];
      i++;
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) code.push(lines[i++]);
      i++;
      out.append(h("pre", {}, h("code", {}, code.join("\n"))));
      continue;
    }
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    if (heading) {
      flush();
      out.append(h(`h${Math.min(heading[1].length + 1, 6)}`, {}, inline(heading[2].replace(/\s#+\s*$/, ""), open)));
      i++;
      continue;
    }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) {
      flush();
      out.append(h("hr"));
      i++;
      continue;
    }
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      flush();
      const rows = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      out.append(table(rows, open));
      continue;
    }
    if (/^\s*>/.test(line)) {
      flush();
      const quoted = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) quoted.push(lines[i++].replace(/^\s*>\s?/, ""));
      const callout = /^\[!(\w+)\][+-]?\s*(.*)$/.exec(quoted[0] ?? "");
      if (callout) {
        out.append(h(
          "div",
          { class: `callout callout-${callout[1].toLowerCase()}` },
          h("div", { class: "callout-title" }, inline(callout[2] || callout[1], open)),
          render(quoted.slice(1).join("\n"), open, { breaks: opts.breaks })
        ));
      } else {
        out.append(h("blockquote", {}, render(quoted.join("\n"), open, { breaks: opts.breaks })));
      }
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      flush();
      const items = [];
      while (i < lines.length && (/^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) || lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length)) items.push(lines[i++]);
      out.append(list(items, open));
      continue;
    }
    para.push(line.trim());
    i++;
  }
  flush();
  return out;
}
function cells(row) {
  return row.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}
function table(rows, open) {
  const [head, , ...body] = rows;
  return h("div", { class: "table-wrap" }, h(
    "table",
    {},
    h("thead", {}, h("tr", {}, cells(head).map((c) => h("th", {}, inline(c, open))))),
    h("tbody", {}, body.map((r) => h("tr", {}, cells(r).map((c) => h("td", {}, inline(c, open))))))
  ));
}
function list(lines, open) {
  const make = (ordered) => h(ordered ? "ol" : "ul");
  const first = /^(\s*)([-*+]|\d+[.)])/.exec(lines[0]);
  const stack = [{ indent: first[1].length, el: make(/\d/.test(first[2])), last: null }];
  for (const line of lines) {
    const m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
    if (!m) {
      stack[stack.length - 1].last?.append(" ", inline(line.trim(), open));
      continue;
    }
    const indent = m[1].replace(/\t/g, "    ").length;
    while (stack.length > 1 && indent < stack[stack.length - 1].indent) stack.pop();
    let top = stack[stack.length - 1];
    if (indent > top.indent && top.last) {
      const nested = { indent, el: make(/\d/.test(m[2])), last: null };
      top.last.append(nested.el);
      stack.push(nested);
      top = nested;
    }
    const task = /^\[([ xX])\]\s+(.*)$/.exec(m[3]);
    const li = task ? h("li", { class: "task" }, h("input", { type: "checkbox", disabled: true, checked: task[1] !== " " }), " ", inline(task[2], open)) : h("li", {}, inline(m[3], open));
    top.el.append(li);
    top.last = li;
  }
  return stack[0].el;
}

// ../ui/src/chat.ts
function offeringAsked(q) {
  if (q.kind !== "confirm") return "";
  const named = /staging\/offerings\/([^\s()]+)\.md/.exec(String(q.question ?? ""));
  return named ? named[1] : "";
}
function icon2(paths) {
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
var copyIcon = () => icon2([
  ["rect", { x: "3", y: "4.5", width: "8", height: "9.5", rx: "1.3" }],
  ["path", { d: "M6 4.5V3a1.3 1.3 0 0 1 1.3-1.3H12A1.3 1.3 0 0 1 13.3 3v8A1.3 1.3 0 0 1 12 12.3h-1" }]
]);
var retryIcon = () => icon2([
  ["path", { d: "M3 8a5 5 0 1 1 1.7 3.75" }],
  ["path", { d: "M3 11.8V8.1h3.7" }]
]);
var rewindIcon = () => icon2([
  ["path", { d: "M8.5 3 3.3 8l5.2 5" }],
  ["path", { d: "M13 3v10" }]
]);
var branchIcon = () => icon2([
  ["circle", { cx: "3.6", cy: "3.6", r: "1.5" }],
  ["circle", { cx: "3.6", cy: "12.4", r: "1.5" }],
  ["circle", { cx: "12.4", cy: "8", r: "1.5" }],
  ["path", { d: "M5 4.3 10.8 7.5" }],
  ["path", { d: "M5 11.7 10.8 8.5" }]
]);
var PHASE_LABEL = {
  frame: "Frame",
  ingest: "Ingest",
  map: "Map",
  need: "Need",
  search: "Search",
  judge: "Judge",
  synthesise: "Synthesise",
  check_out: "Check out",
  check_in: "Check in",
  find: "Find"
};
function providerFailureCopy(event) {
  const category = String(event.failure_category ?? "");
  switch (category) {
    case "local_environment":
      return {
        heading: "The Core could not make its local network connection",
        advice: "This is a Windows or local security-environment issue, not a model-quality result. Check Host status or local network policy, then retry."
      };
    case "credentials":
      return {
        heading: "The selected route rejected its credentials",
        advice: "Check the key and host under Settings \u2192 Providers & keys, then retry."
      };
    case "route_configuration":
      return {
        heading: "The selected route needs attention",
        advice: "Check the host, exact model, and qualification status in the Model Tile, then retry."
      };
    case "provider_rate_limited":
      return {
        heading: "The provider or host is rate limited",
        advice: "Nothing was switched. Retry shortly, or choose another route yourself."
      };
    case "provider_transient":
      return {
        heading: "The provider is temporarily unavailable",
        advice: "Nothing was switched. Retry shortly, or choose another route yourself."
      };
    case "provider_transport":
      return {
        heading: "The Core could not reach the selected host",
        advice: "Check the host URL and network access; this does not assess model quality."
      };
    case "provider_rejected":
      return {
        heading: "The provider rejected this request",
        advice: "Check the selected host and model under Settings \u2192 Providers & keys, then retry."
      };
    default: {
      const slow = /did not answer within|busy|HTTP (429|50[234])/.test(String(event.error));
      return {
        heading: "The selected route could not answer",
        advice: slow ? "Nothing was switched. Retry in a moment, or choose a faster model for slot 1 yourself." : "Check the key and the model under Settings \u2192 Providers & keys, then retry."
      };
    }
  }
}
var Chat = class {
  // for Retry, after a failed turn
  constructor(api, hooks) {
    this.api = api;
    this.hooks = hooks;
    this.log = h("div", { class: "log", "aria-live": "polite", role: "log" });
    this.plan = h("aside", { class: "plan", "aria-label": "Plan" });
    this.rail = /* @__PURE__ */ new Map();
    // tool -> lines waiting for a result
    this.cards = /* @__PURE__ */ new Map();
    // permission request id -> card
    this.working = null;
    this.outcomeCard = null;
    this.lastUserText = "";
    // MF-010: the inspector is rebuilt on every state update, so what the person
    // opened and typed is kept here, by requirement, across rebuilds.
    this.disclosures = /* @__PURE__ */ new Set();
    this.drafts = /* @__PURE__ */ new Map();
    this.empty();
  }
  empty() {
    clear(this.log, h(
      "div",
      { class: "hint" },
      "Ask the librarian. It opens a session for anything longer than one search, and the plan ",
      "on the right shows where the thread is."
    ));
  }
  scroll() {
    this.log.scrollTop = this.log.scrollHeight;
  }
  append(el) {
    this.log.querySelector(sel(".hint"))?.remove();
    if (this.working) this.log.insertBefore(el, this.working);
    else this.log.append(el);
    this.scroll();
  }
  /** A message plus its actions - hover-revealed, so the log itself stays
   *  quiet to read. Copy always works; retry only on a message a failed turn
   *  left dangling; rewind and branch only once a message's place in the
   *  resumable log is known (a replayed thread), rewind only where nothing
   *  after it has written to the vault. */
  bubble(role, text, opts = {}) {
    const body = role === "user" ? h("div", { class: "msg user" }, text) : h("div", { class: "msg" }, render(text, this.hooks.openNote, { breaks: true }));
    const actions = [h("button", {
      class: "icon-btn",
      title: "Copy",
      "aria-label": "Copy message",
      onclick: () => {
        void navigator.clipboard.writeText(text).catch(() => void 0);
      }
    }, copyIcon())];
    if (role === "assistant") {
      const speak = h("button", {
        class: "icon-btn speak",
        title: "Read aloud",
        "aria-label": "Read aloud",
        onclick: () => void reader.toggle({ text }, speak)
      }, speakerIcon());
      actions.push(speak);
    }
    if (opts.canRetry) {
      actions.push(h("button", {
        class: "icon-btn",
        title: "Retry: send this again",
        "aria-label": "Retry",
        onclick: () => this.hooks.resend(text)
      }, retryIcon()));
    }
    if (opts.index !== void 0) {
      const canRewind = opts.index >= (opts.minRewind ?? 0);
      actions.push(h("button", {
        class: "icon-btn",
        disabled: !canRewind,
        title: canRewind ? "Rewind to here: removes this message and everything after it" : "Can't rewind here: something after this message already wrote to the library",
        "aria-label": "Rewind to here",
        onclick: () => {
          if (canRewind && confirm("Remove this message and everything after it? This can't be undone.")) this.hooks.rewind(opts.index);
        }
      }, rewindIcon()));
      actions.push(h("button", {
        class: "icon-btn",
        title: "Branch: start a new thread from here",
        "aria-label": "Branch from here",
        onclick: () => this.hooks.branch(opts.index)
      }, branchIcon()));
    }
    return h(
      "div",
      { class: `msg-wrap${role === "user" ? " user" : ""}` },
      body,
      h("div", { class: "msg-actions" }, actions)
    );
  }
  /** After a successful rewind: the thread stays the same one, just shorter. */
  applyRewind(messages, minRewind) {
    this.replay(messages, minRewind);
  }
  /** Reopening a thread: render what was actually said, in order, before the
   *  live stream picks up - the log itself, not the `handle()` event path
   *  (that path also flips `working`/rail state meant for a turn in progress). */
  replay(messages, minRewind = 0) {
    clear(this.log);
    messages.forEach((m, i) => {
      const dangling = m.role === "user" && i === messages.length - 1;
      this.log.append(this.bubble(
        m.role === "user" ? "user" : "assistant",
        String(m.text ?? ""),
        { canRetry: dangling, index: i, minRewind }
      ));
      if (dangling) this.lastUserText = String(m.text ?? "");
    });
    if (!messages.length) this.empty();
    this.scroll();
  }
  setWorking(on) {
    if (on && !this.working) {
      this.working = h("div", { class: "working" }, "The librarian is working\u2026");
      this.log.append(this.working);
      this.scroll();
    } else if (!on && this.working) {
      this.working.remove();
      this.working = null;
    }
  }
  uncertainRun(run) {
    const paused = run.last ?? run;
    const step = paused.step ?? paused.at;
    if (run.status !== "paused" || paused.reason !== "outcome_unknown" || !run.run || !step) return null;
    const card = h("section", { class: "warn" });
    const actions = h("div", { class: "row2" });
    const status = h("p", { role: "status" });
    const resolve2 = async (choice) => {
      actions.querySelectorAll("button").forEach((button) => {
        button.disabled = true;
      });
      try {
        const current = await this.api.tool("run_status", { run_id: run.run });
        if (current.status !== "paused" || current.last?.step !== step || current.last.reason !== "outcome_unknown" || !current.last.options?.includes(choice)) {
          status.textContent = "The run has changed. Inspect its current status.";
          return;
        }
        const result = await this.api.tool("run_resume", { run_id: run.run, choices: { [step]: choice } });
        if (result.error) throw new Error(String(result.detail ?? result.error));
        status.textContent = `Run ${run.run}: ${result.status}.`;
        const next = this.uncertainRun(result);
        if (next) card.append(next);
      } catch (e) {
        status.textContent = `Check the run status before trying again. ${e.message}`;
      }
    };
    for (const [value, label] of [["applied", "Record step as already applied"], ["retry", "Send this step again"]]) {
      if (paused.options?.includes(value)) actions.append(h("button", { class: "ghost", onclick: () => void resolve2(value) }, label));
    }
    card.append(
      h("strong", {}, "Step outcome unknown"),
      h("p", {}, `Run ${run.run} \xB7 Step ${step}. ${paused.detail}`),
      h("p", {}, "Check the destination before deciding. Sending the step again can repeat its effect."),
      actions,
      status
    );
    return card;
  }
  /** A macro step whose outcome is unknown. A person checks the destination, then
   * answers by the run's recovery handle (its checkpoint and step); Core resumes with
   * the inputs the run's log recorded. The run is looked at again first, so a card that
   * is stale (another tab answered, or a reconnect replayed it) changes nothing. */
  uncertainMacro(result) {
    const action = result.next_action ?? {};
    const handle = result.recovery;
    const card = h(
      "section",
      { class: "warn" },
      h("strong", {}, "Macro step outcome unknown"),
      h("p", {}, `${action.completed_steps ?? 0} steps completed \xB7 ${action.tool ?? handle?.tool ?? ""}`)
    );
    if (!handle?.checkpoint_id) {
      card.append(h("p", {}, String(action.detail ?? "")));
      return card;
    }
    card.append(h("p", {}, "Check the destination before deciding. Sending the step again can repeat its effect."));
    const actions = h("div", { class: "row2" });
    const status = h("p", { role: "status" });
    const buttons = () => Array.from(actions.querySelectorAll("button"));
    const resolve2 = async (choice) => {
      buttons().forEach((button) => {
        button.disabled = true;
      });
      try {
        const current = await this.api.tool("macro_status", { checkpoint_id: handle.checkpoint_id });
        if (current.status !== "outcome_unknown" || current.step !== handle.step || !(current.options ?? []).includes(choice)) {
          status.textContent = current.status === "completed" ? "This macro run has already completed." : "The run has changed. Look at its current status before deciding.";
          return;
        }
        const out = await this.api.tool(
          "macro_resolve",
          { checkpoint_id: handle.checkpoint_id, step: handle.step, choice }
        );
        if (out.error) throw new Error(String(out.detail ?? out.error));
        status.textContent = out.status === "completed" ? "Recorded. The macro run completed." : out.status === "changed" ? "The run has changed. Look at its current status before deciding." : `The macro run is ${out.status}.${out.next_action?.detail ? ` ${out.next_action.detail}` : ""}`;
        if (out.status === "outcome_unknown" && out.recovery) card.append(this.uncertainMacro(out));
      } catch (e) {
        status.textContent = `Look at the run's status before trying again. ${e.message}`;
        buttons().forEach((button) => {
          button.disabled = false;
        });
      }
    };
    for (const [value, label] of [["applied", "Record step as already applied"], ["retry", "Send this step again"]]) {
      if ((handle.options ?? []).includes(value)) actions.append(h("button", { class: "ghost", onclick: () => void resolve2(value) }, label));
    }
    card.append(actions, status);
    return card;
  }
  handle(event) {
    switch (event.type) {
      case "user":
        this.lastUserText = String(event.text ?? "");
        this.append(this.bubble("user", this.lastUserText));
        this.setWorking(true);
        break;
      case "text": {
        const bubble = this.bubble("assistant", String(event.text ?? ""));
        if (event.reply_id) bubble.dataset.replyId = String(event.reply_id);
        this.append(bubble);
        break;
      }
      case "tool_call": {
        const tool = String(event.tool);
        const write = this.hooks.effectOf(tool) !== "read";
        const line = h(
          "div",
          { class: `tool${write ? " write" : ""}` },
          h("code", {}, tool),
          " \xB7 ",
          h("span", { class: "dim" }, "running")
        );
        this.rail.set(tool, [...this.rail.get(tool) ?? [], line]);
        this.append(line);
        break;
      }
      case "tool_result": {
        const tool = String(event.tool);
        const waiting = this.rail.get(tool) ?? [];
        const line = waiting.shift() ?? h("div", { class: "tool" }, h("code", {}, tool));
        const result = event.result ?? {};
        clear(line, h("code", {}, tool), " \xB7 ", summarise(tool, result, this.hooks.openNote));
        if (["run_workflow", "run_pipeline", "run_resume", "run_status"].includes(tool)) {
          const card = this.uncertainRun(result);
          if (card) line.append(card);
        }
        if (result.status === "outcome_unknown" && result.next_action) {
          line.append(this.uncertainMacro(result));
        }
        if (result.error) line.classList.add(cls("refused"));
        if (!line.isConnected) this.append(line);
        if (result.session) this.hooks.onSession(result.session);
        const runnable = result.runnable ?? [];
        if (runnable.length) this.append(h(
          "div",
          { class: "note reviewed runnable" },
          "A review challenged these claims with a call that would show them wrong. Nothing has run.",
          h("ul", {}, runnable.map((r) => h(
            "li",
            {},
            `\u201C${r.claim}\u201D \u2014 `,
            h("code", {}, r.input),
            " ",
            this.runButton(r.run_id)
          )))
        ));
        break;
      }
      case "permission_request":
        this.permission(event);
        break;
      case "permission_decided": {
        const card = this.cards.get(String(event.id));
        if (card) {
          card.classList.add(cls("done"));
          const row = card.querySelector(sel(".row"));
          if (row) clear(row, h("em", {}, sentence(String(event.reason ?? event.outcome))));
        }
        break;
      }
      case "reply_reviewed": {
        const challenged = event.challenged ?? [];
        const held = Number(event.held ?? 0), unchecked = Number(event.unchecked ?? 0);
        const silent = event.not_extracted ?? [];
        const over = Number(event.over_limit ?? 0);
        if (!held && !challenged.length && !unchecked && !event.status) break;
        const ambiguous = event.ambiguous ?? [];
        const partly = event.partly_checked ?? [];
        const target = event.reply_id ? Array.from(this.log.querySelectorAll("[data-reply-id]")).find((el) => el.dataset.replyId === String(event.reply_id)) : void 0;
        const note = h(
          "div",
          { class: "note reviewed", ...event.reply_id ? { "data-review-of": String(event.reply_id) } : {} },
          event.reply_id && !target ? h("div", { class: "dim small" }, "On an earlier reply:") : null,
          event.status ? `The review could not run (${event.status}).` : `Checked against the notes it cites: ${held} held${unchecked ? `, ${unchecked} unchecked` : ""}${challenged.length ? `, ${challenged.length} challenged` : ""}.`,
          challenged.length ? h("ul", {}, challenged.map((c) => h(
            "li",
            {},
            `\u2691 \u201C${c.claim}\u201D \u2014 `,
            h("span", { class: "dim" }, c.counter_quote ? `${c.reason} [[${c.note}]] says: \u201C${c.counter_quote}\u201D` : `not found in [[${c.note}]]. ${c.reason}`),
            c.run_id ? h(
              "div",
              {},
              "Failing input: ",
              h("code", {}, String(c.input ?? "")),
              " ",
              this.runButton(String(c.run_id))
            ) : null
          ))) : null,
          silent.length ? h("div", { class: "dim small" }, `Nothing it says about ${silent.map((n) => `[[${n}]]`).join(", ")} was picked out to check.`) : null,
          over ? h("div", { class: "dim small" }, `${over} more claim${over === 1 ? " was" : "s were"} past the review limit (the effort setting) and not checked.`) : null,
          ambiguous.length ? h("div", { class: "dim small" }, `Not checked: ${ambiguous.map((n) => `[[${n}]]`).join(", ")} matches more than one note. Link it by its folder to have it checked.`) : null,
          partly.length ? h("ul", { class: "dim small" }, partly.map((p) => h("li", {}, `\u201C${p.claim}\u201D \u2014 ${p.note_path}: ${p.reason}.`))) : null,
          challenged.length ? h("div", { class: "dim small" }, event.late ? "This review finished after a newer turn began, so the librarian will not see these challenges. It is advice, not a verdict." : "The librarian sees these challenges in its next reply. It is advice, not a verdict.") : null
        );
        if (target) target.after(note);
        else this.append(note);
        break;
      }
      case "workflow_preflight": {
        const action = String(event.required_next_action ?? "the required task action");
        this.append(h(
          "div",
          { class: "error" },
          "This thread was paused before another model call because the Core cannot currently offer ",
          h("code", {}, action),
          ". No model was blamed or switched. Repair the workflow surface, then retry. ",
          this.hooks.openModelPicker ? h("button", {
            class: "ghost",
            onclick: () => this.hooks.openModelPicker?.()
          }, "Open model status") : null
        ));
        break;
      }
      case "turn_done":
        this.setWorking(false);
        if (event.stopped === "cancelled") {
          this.append(h("div", { class: "tool" }, "Reply stopped."));
        } else if (event.stopped === "max_steps") {
          this.append(h(
            "div",
            { class: "error" },
            "Stopped after the step limit for one turn. ",
            "Say \u201Ccontinue\u201D to carry on, or ask for a summary of where it got to."
          ));
        } else if (event.stopped === "provider_error") {
          const copy = providerFailureCopy(event);
          this.append(h(
            "div",
            { class: "error" },
            `${copy.heading}: ${event.error}. `,
            copy.advice,
            " ",
            h(
              "button",
              {
                class: "icon-btn",
                title: "Retry: send this again",
                "aria-label": "Retry",
                onclick: () => this.hooks.resend(this.lastUserText)
              },
              retryIcon()
            ),
            this.hooks.openModelPicker ? h("button", {
              class: "ghost",
              onclick: () => this.hooks.openModelPicker?.()
            }, "Choose another route") : null
          ));
        }
        this.sessionOutcome(event.session ?? null);
        this.hooks.onSession(event.session ?? null);
        break;
      case "error":
        this.setWorking(false);
        if (event.failure_category === "local_environment") {
          this.append(h(
            "div",
            { class: "error" },
            "Local environment issue (not a model result): ",
            String(event.error)
          ));
        } else {
          this.append(h("div", { class: "error" }, String(event.error)));
        }
        break;
      case "conversation_reset":
        this.rail.clear();
        this.setWorking(false);
        this.empty();
        this.hooks.onSession(null);
        break;
      case "session_attached": {
        const session = event.session ?? null;
        this.replay(
          session?.messages ?? [],
          Number(session?.min_rewind_index ?? 0)
        );
        this.append(h(
          "div",
          { class: "tool" },
          "continuing the thread ",
          h("code", {}, String(session?.session ?? ""))
        ));
        for (const q of session?.questions ?? []) {
          if (q.answer === null || q.answer === void 0) {
            this.questionCard({
              type: "question_asked",
              question_id: q.id,
              question: q.question,
              kind: q.kind,
              options: q.options,
              session: session?.session
            });
          }
        }
        this.hooks.onSession(session);
        break;
      }
      case "question_asked":
        this.questionCard(event);
        break;
      case "question_answered": {
        const card = this.cards.get(`q:${String(event.question_id ?? "")}`);
        if (card && !card.classList.contains(cls("done"))) {
          card.classList.add(cls("done"));
          const row = card.querySelector(sel(".row"));
          if (row) clear(row, h("em", {}, event.answered ? "Answered elsewhere." : "Timed out unanswered."));
        }
        const sessionId = String(event.session ?? "");
        if (sessionId) {
          this.api.tool("session_status", {}, sessionId).then((out) => {
            if (!out.error) this.hooks.onSession(out);
          }).catch(() => void 0);
        }
        break;
      }
    }
  }
  /** The coverage ledger (R13): each asked topic, its brief and verdict, and what was
   *  kept for it - context finds counted apart, since they do not answer it. */
  coverage(session) {
    const ledger = session?.completion?.ledger ?? session?.coverage ?? [];
    if (!ledger.length) return null;
    const mark = {
      covered: "\u2713 covered",
      partial: "\u25D0 partial",
      gap: "\u2717 gap",
      open: "\u25CB open",
      "no brief": "\u25CB no brief yet"
    };
    return h(
      "div",
      { class: "coverage" },
      h("h3", {}, "Coverage"),
      h("ul", {}, ledger.map((r) => h(
        "li",
        {},
        h("strong", {}, String(r.topic)),
        ` \xB7 ${r.brief || "no brief"} \xB7 ${mark[r.verdict] ?? r.verdict}`,
        (r.kept ?? []).length ? h("span", { class: "dim" }, ` \xB7 ${r.kept.length} kept`) : null,
        (r.context ?? []).length ? h("span", { class: "dim" }, ` \xB7 ${r.context.length} context only`) : null
      )))
    );
  }
  /** R11: a spent budget with the phase unfinished is the person's to extend. */
  extendBudget(session) {
    if (!session?.budget_spent || session.status !== "open") return null;
    return h("button", {
      class: "ghost",
      title: "Give this phase ten more calls",
      onclick: async (e) => {
        e.currentTarget.disabled = true;
        try {
          const out = await this.api.tool("extend_budget", { add: 10 }, String(session.session ?? ""));
          if (out.error) throw new Error(String(out.detail ?? out.error));
          if (out.session) this.hooks.onSession(out.session);
        } catch (err) {
          this.append(h("div", { class: "error" }, `Could not extend the budget: ${err.message}`));
        }
      }
    }, "Extend budget (+10 calls)");
  }
  sessionOutcome(session) {
    if (!session) return;
    this.outcomeCard?.remove();
    if (session.status === "closed") {
      this.outcomeCard = h(
        "div",
        { class: "session-outcome closed", role: "status" },
        h("strong", {}, "Thread closed"),
        session.summary ? h("div", {}, String(session.summary)) : null,
        session.gaps ? h("div", { class: "dim" }, `Gaps: ${session.gaps}`) : null,
        this.coverage(session)
      );
      this.append(this.outcomeCard);
      return;
    }
    const openItems = session.open_items ?? [];
    const parked = session.status === "parked";
    this.outcomeCard = h(
      "div",
      { class: "session-outcome open", role: "status" },
      h("strong", {}, `${parked ? "Thread parked" : "Thread still open"} \xB7 ${String(session.phase ?? "work in progress")}`),
      openItems.length ? h("ul", {}, openItems.slice(0, 5).map((item) => h("li", {}, item))) : null,
      session.next ? h("p", {}, String(session.next)) : null,
      this.coverage(session),
      this.extendBudget(session),
      parked ? h("p", { class: "dim" }, "Reopen this thread from Sessions to continue.") : h("button", { class: "ghost", onclick: () => this.hooks.continueSession() }, "Continue from next step")
    );
    this.append(this.outcomeCard);
  }
  /** UX-01: the Core projects this from the audited Session ledger. The UI
   * explains and acts on that projection; it never derives closure state. */
  predicateInspector(session) {
    if (!session) return null;
    const view = session?.predicate_inspector;
    if (!view) return null;
    const requirements = inspectorRequirements(view);
    const invalid = String(view.invalid || "");
    const halted = invalid || String(view.legacy || "");
    if (!requirements.length && !halted) return null;
    const actionable = view.actionable !== false && session.status !== "closed" && !halted;
    const edits = Array.isArray(session.audit?.external_edits) ? session.audit.external_edits : [];
    return h(
      "section",
      { class: "predicate-inspector", "aria-label": "Requirement predicates" },
      h("h3", {}, "Requirements"),
      h(
        "p",
        { class: "dim inspector-scope" },
        "Checks support only the exact predicate shown. Person acceptance is a separate judgment; it is not verification."
      ),
      halted ? h(
        "div",
        { class: "inspector-halted", role: "status" },
        h(
          "p",
          { class: "warn-text" },
          `This audit history is ${invalid ? "invalid" : "legacy"} and is read-only: ${halted}`
        ),
        h("p", { class: "dim" }, "It stays as it is. New audited work starts in a separate thread."),
        this.hooks.newThread ? h("button", { class: "ghost", onclick: () => this.hooks.newThread?.() }, "Start a new thread") : null
      ) : null,
      !requirements.length ? h("p", { class: "dim" }, "This history records no requirements.") : null,
      edits.length ? changedFiles(edits) : null,
      requirements.map((requirement) => {
        const rid = String(requirement.id ?? requirement.requirement_id ?? "Requirement");
        const closure = String(requirement.closure ?? "");
        const status = String(requirement.status ?? "open");
        const predicates = predicateRows(requirement.predicates, rid);
        const artifacts = namedRows(requirement.artifacts, "id");
        const actionStatus = h("div", { class: "inspector-action-status", role: "status" });
        return h(
          "div",
          { class: `requirement-card status-${safeClass(status)}` },
          h(
            "div",
            { class: "requirement-heading" },
            h("strong", {}, rid),
            h("span", { class: `inspector-state state-${safeClass(status)}` }, statusLabel(status))
          ),
          requirement.text ? h("p", {}, String(requirement.text)) : null,
          h(
            "p",
            { class: "dim inspector-meta" },
            closure ? `${closureLabel(closure)} \xB7 ` : "",
            `revision ${String(requirement.revision ?? 1)}`
          ),
          requirement.stop ? stopReasonView(requirement.stop) : null,
          predicates.map((predicate) => this.predicateRow(predicate, rid)),
          actionable && (status === "blocked" || status === "failed") ? this.reviseForm(session, requirement, actionStatus) : null,
          !actionable ? null : this.inspectorActions(session, rid, closure, artifacts, actionStatus),
          actionStatus
        );
      }),
      actionable && session.purpose === "audited" ? this.skeletonView() : null
    );
  }
  disclosure(key, summary, ...body) {
    return h("details", {
      class: "inspector-disclosure",
      open: this.disclosures.has(key),
      ontoggle: (e) => {
        if (e.currentTarget.open) this.disclosures.add(key);
        else this.disclosures.delete(key);
      }
    }, h("summary", {}, summary), ...body);
  }
  /** MF-010: a blocked or failed requirement reopens by revision. Only its
   *  wording changes here: the predicates, the closure and every verifier the
   *  person named, with its parameters, are sent back exactly as projected. */
  reviseForm(session, requirement, status) {
    const rid = String(requirement.id ?? "");
    const original = String(requirement.text ?? "");
    const predicates = Array.isArray(requirement.predicates) ? requirement.predicates : [];
    const verifiers = {};
    for (const p of predicates) {
      if (p?.verifier?.id) verifiers[String(p.text)] = { verifier: String(p.verifier.id), params: { ...p.subject ?? {} } };
    }
    const text = h("textarea", { class: "f short", "aria-label": `Revised wording for ${rid}` });
    text.value = this.drafts.get(rid) ?? original;
    const save = h("button", { class: "ghost" }, "Revise and reopen");
    const sync = () => {
      save.disabled = !text.value.trim() || text.value.trim() === original.trim();
    };
    text.oninput = () => {
      this.drafts.set(rid, text.value);
      sync();
    };
    sync();
    save.onclick = () => {
      this.drafts.delete(rid);
      void this.inspectorAction(session, "set_requirement", {
        requirement_id: rid,
        text: text.value.trim(),
        closure: String(requirement.closure ?? "authoritative"),
        predicates: predicates.map((p) => String(p.text)),
        verifiers
      }, save, status);
    };
    return this.disclosure(
      `revise:${rid}`,
      "Revise the wording and reopen",
      h("p", { class: "dim" }, "Only the wording changes. The predicates and the verifiers you named, with their parameters, are kept exactly. A revision reopens the requirement and makes earlier results stale."),
      text,
      h("div", { class: "inspector-action-row" }, save)
    );
  }
  /** MF-010: the contract skeleton, read only when the person opens it. */
  skeletonView() {
    const body = h("div", { class: "inspector-skeleton" }, h("p", { class: "dim" }, "Loading\u2026"));
    const load = async () => {
      try {
        const out = await this.api.get("/api/session/skeleton");
        clear(body, out.skeleton ? h("pre", { class: "checkpoint-evidence" }, JSON.stringify(out.skeleton, null, 2)) : h("p", { class: "dim" }, `No skeleton: ${String(out.reason ?? "none is being prepared")}.`));
      } catch (e) {
        clear(body, h("p", { class: "error" }, e.message));
      }
    };
    const view = this.disclosure("skeleton", "Contract skeleton", h(
      "p",
      { class: "dim" },
      "admit_contract's arguments built from your bindings alone. A predicate with no verifier you named is listed under needs, never guessed."
    ), body);
    view.addEventListener("toggle", () => {
      if (view.open) void load();
    });
    if (view.open) void load();
    return view;
  }
  predicateRow(predicate, requirementId) {
    const result = predicate.latest_result ?? predicate.result ?? {};
    const id = String(predicate.id ?? predicate.predicate_id ?? `${requirementId}.?`);
    const text = String(predicate.text ?? predicate.predicate ?? predicate.statement ?? "Unnamed predicate");
    const outcome = String(predicate.outcome ?? predicate.status ?? result.outcome ?? "not_checked");
    const stale = Boolean(predicate.stale ?? result.stale);
    const verifier = predicate.verifier ?? predicate.authority ?? {};
    const verifierId = typeof verifier === "string" ? verifier : String(verifier.id ?? verifier.verifier ?? predicate.verifier_id ?? "");
    const verifierKind = typeof verifier === "string" ? String(predicate.verifier_kind ?? "") : String(verifier.kind ?? predicate.verifier_kind ?? "");
    const strength = String(result.strength ?? predicate.strength ?? (typeof verifier === "string" ? "" : verifier.max_strength ?? ""));
    const rawDecision = predicate.decision_path ?? predicate.decision?.path ?? predicate.decision ?? "";
    const decision = typeof rawDecision === "string" ? rawDecision : "";
    const subject = predicate.bound_subject ?? predicate.subject ?? predicate.binding ?? (typeof verifier === "string" ? {} : verifier.params ?? {});
    const missing = predicate.missing_subject_keys ?? predicate.missing_bindings ?? subject.missing ?? [];
    const mismatches = predicate.subject_mismatches;
    const subjectValues = Object.entries(subject).filter(([key, value]) => key !== "missing" && key !== "bound" && value !== void 0 && value !== null && value !== "");
    const exactStatement = String(result.statement ?? predicate.result_statement ?? predicate.established_statement ?? "");
    const artifacts = namedRows(result.artifacts, "id");
    const open = stale || !["pass", "verified", "human_accepted"].includes(outcome);
    return h(
      "details",
      { class: `predicate-row outcome-${safeClass(stale ? "stale" : outcome)}`, open },
      h(
        "summary",
        {},
        h("code", {}, id),
        h("span", {}, text),
        h(
          "span",
          { class: `inspector-state state-${safeClass(stale ? "stale" : outcome)}` },
          stale ? "stale" : statusLabel(outcome)
        )
      ),
      h(
        "div",
        { class: "predicate-detail" },
        h("p", {}, h("strong", {}, "Decision path: "), decisionLabel(decision)),
        verifierId ? h(
          "p",
          {},
          h("strong", {}, "Check: "),
          verifierId,
          verifierKind ? ` \xB7 ${verifierKind}` : "",
          strength ? ` \xB7 ${strength}` : ""
        ) : h("p", { class: "dim" }, "No check has been named for this predicate."),
        subjectValues.length ? h(
          "p",
          {},
          h("strong", {}, "Bound subject: "),
          subjectValues.map(([key, value]) => `${key} = ${displayValue(value)}`).join(" \xB7 ")
        ) : h("p", { class: "dim" }, "No subject is bound."),
        Array.isArray(missing) && missing.length ? h(
          "p",
          { class: "warn-text" },
          `Missing subject binding: ${missing.map(String).join(", ")}. A pass can be partial, but cannot verify this predicate.`
        ) : null,
        Array.isArray(mismatches) && mismatches.length ? h(
          "p",
          { class: "warn-text" },
          `The latest check does not match the bound subject: ${mismatches.map(String).join(", ")}. It cannot verify this predicate.`
        ) : null,
        exactStatement ? h("p", {}, h("strong", {}, "Established statement: "), exactStatement) : h("p", { class: "dim" }, "No current check statement."),
        result.id ? h("p", { class: "dim" }, `Result ${String(result.id)}${result.epoch !== void 0 ? ` \xB7 epoch ${String(result.epoch)}` : ""}${artifacts.length ? ` \xB7 artifacts ${artifacts.map((artifact) => String(artifact.id ?? artifact.artifact ?? "?")).join(", ")}` : ""}`) : null,
        stale ? h("p", { class: "warn-text" }, String(predicate.stale_reason ?? result.stale_reason ?? "This result belongs to an earlier session state and is not current evidence.")) : null
      )
    );
  }
  inspectorActions(session, requirement, closure, artifacts, status) {
    const evidence = h("input", {
      type: "text",
      "aria-label": `Evidence needed for ${requirement}`,
      placeholder: "Evidence or check needed"
    });
    const request = h("button", { class: "ghost", disabled: true }, "Request evidence");
    evidence.oninput = () => {
      request.disabled = !evidence.value.trim();
    };
    request.onclick = () => {
      const what = evidence.value.trim();
      if (what) void this.inspectorAction(session, "request_evidence", { requirement, what }, request, status);
    };
    const rows = [h("div", { class: "inspector-action-row" }, evidence, request)];
    for (const artifact of artifacts) {
      const id = String(artifact.id ?? artifact.artifact ?? "");
      if (!id) continue;
      const reason = h("input", {
        type: "text",
        "aria-label": `Reason for rejecting ${id}`,
        placeholder: "Reason if rejecting"
      });
      const accept = h("button", { class: "ghost" }, "Accept");
      const reject = h("button", { class: "ghost", disabled: true }, "Reject");
      reason.oninput = () => {
        reject.disabled = !reason.value.trim();
      };
      accept.onclick = () => void this.inspectorAction(
        session,
        "accept_artifact",
        { requirement, artifact: id },
        accept,
        status
      );
      reject.onclick = () => {
        const why = reason.value.trim();
        if (why) void this.inspectorAction(
          session,
          "reject_artifact",
          { requirement, artifact: id, reason: why },
          reject,
          status
        );
      };
      rows.push(h(
        "div",
        { class: "inspector-artifact" },
        h(
          "div",
          {},
          h("strong", {}, id),
          artifact.path ? " \xB7 " : "",
          artifact.path ? link(String(artifact.path), pathName(String(artifact.path)), this.hooks.openNote) : null
        ),
        h("p", { class: "dim" }, closure === "human_judgment" ? "Accept records your judgment about this exact artifact; it does not turn it into verified evidence." : "Accept records your judgment separately from Core verification."),
        h("div", { class: "inspector-action-row" }, accept, reason, reject)
      ));
    }
    return h("div", { class: "inspector-actions" }, rows);
  }
  async inspectorAction(session, tool, args, button, status) {
    button.disabled = true;
    clear(status, h("span", { class: "dim" }, "Updating\u2026"));
    try {
      const sessionId = String(session?.session ?? "");
      const out = await this.api.tool(tool, args, sessionId);
      if (out.error || out.refused) {
        button.disabled = false;
        clear(status, refusalView(out));
        return;
      }
      const fresh = await this.api.tool("session_status", {}, sessionId);
      if (fresh.error || fresh.refused) throw new Error(String(fresh.detail ?? fresh.refused ?? fresh.error));
      this.hooks.onSession(fresh);
    } catch (error) {
      button.disabled = false;
      clear(status, h("span", { class: "error" }, error.message));
    }
  }
  /** G3: a person's "Run it" - one function call in a Docker sandbox with no network.
   *  MF-027c: Docker is checked first, and while it is unavailable the button says why and
   *  sends nothing. A verdict replaces the button only when the run left execution evidence. */
  runButton(runId) {
    const out = h("span", { class: "run-claim" });
    const why = h("span", { class: "dim small" });
    const button = h("button", {
      class: "ghost",
      title: "Runs this one call in a Docker container with no network and the repository read-only. Needs Docker Desktop running.",
      onclick: async () => {
        button.disabled = true;
        if (!await ready(true)) return;
        clear(out, h("span", { class: "dim" }, "running in the sandbox\u2026"));
        try {
          const r = await this.api.post("/api/claims/run", { id: runId });
          if (r.error) clear(out, h("span", { class: "error" }, String(r.detail ?? r.error)));
          else if (!r.evidence) clear(out, h("span", { class: "error" }, "The run left no evidence, so there is no verdict to show."));
          else clear(out, h("strong", {}, String(r.verdict).replace(/_/g, " ")), ` \u2014 ${r.detail} (${r.version})`);
        } catch (e) {
          clear(out, h("span", { class: "error" }, e.message));
        }
      }
    }, "Run it");
    const again = h("button", { class: "ghost", hidden: true, onclick: () => void ready(true) }, "Check again");
    const ready = async (fresh) => {
      let check;
      try {
        check = await this.api.get(`/api/claims/preflight${fresh ? "?fresh=1" : ""}`);
      } catch (e) {
        check = { available: false, detail: e.message };
      }
      const ok = check.available === true;
      button.disabled = !ok;
      again.hidden = ok;
      why.textContent = ok ? "" : ` Docker is not available: ${String(check.detail ?? "no answer")}`;
      return ok;
    };
    clear(out, button, why, again);
    void ready(false);
    return out;
  }
  permission(event) {
    const args = event.arguments ?? {};
    const preview = event.preview ?? null;
    const detail = preview ? `${preview.path ?? ""}` : Object.entries(args).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(" \xB7 ");
    const diff = preview?.diff ? h("pre", { class: "diff" }, String(preview.diff).split("\n").map((line) => h("span", { class: line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "del" : "" }, line + "\n"))) : null;
    const answer = (value) => async () => {
      try {
        await this.api.post("/api/permission", { id: event.id, answer: value });
      } catch (e) {
        this.append(h("div", { class: "error" }, `Could not answer: ${e.message}`));
      }
    };
    const card = h(
      "div",
      { class: "perm", role: "group", "aria-label": "Permission needed" },
      h("strong", {}, "Permission needed"),
      " \xB7 ",
      h("code", {}, String(event.tool)),
      ` wants to ${event.effect === "read" ? "run" : "write"}`,
      event.tool === "sandbox_output" ? h(
        "div",
        {},
        h("strong", {}, "Keep the files this run writes?"),
        h("p", {}, "Destination: ", String(args.writes_to ?? "unreported")),
        h("p", {}, "During execution: ", String(args.while_running ?? "unreported")),
        h("p", {}, "After execution: ", String(args.after_the_run ?? "unreported"))
      ) : detail ? h("div", { class: "dim" }, detail) : null,
      diff,
      event.always_ask ? h("div", { class: "dim" }, "Asked before every change: allowing it applies this one only.") : null,
      h(
        "div",
        { class: "row" },
        h("button", { onclick: answer("allow_once") }, event.always_ask ? "Apply this change" : "Allow once"),
        event.always_ask ? null : h("button", { onclick: answer("allow_session") }, "Allow for this session"),
        h("button", { onclick: answer("deny") }, "Deny")
      )
    );
    this.cards.set(String(event.id), card);
    this.append(card);
    card.querySelector("button")?.focus();
  }
  /** A question the session asked (`ask_user` / a phase's own required field,
   *  e.g. BRIEF_REQUIRED) - the same blocking handshake as a permission
   *  request (`Waiters` in tools/sessions.py mirrors `Broker.check()`), so it
   *  gets the same treatment: a card right here, impossible to miss, instead
   *  of a silent wait only the Plan panel showed. Answering it wakes the
   *  turn's own blocked call directly. */
  questionCard(event) {
    const id = String(event.question_id ?? "");
    if (!id || this.cards.has(`q:${id}`)) return;
    const options = event.options ?? null;
    const sessionId = String(event.session ?? "");
    const row = h("div", { class: "row" });
    const send = async (value) => {
      if (!value.trim()) return;
      clear(row, h("em", {}, "Answering\u2026"));
      try {
        const out = await this.api.tool("answer", { question_id: id, answer: value }, sessionId);
        if (out.error) throw new Error(String(out.detail ?? out.error));
        clear(row, h("em", {}, out.resumed ? `Answered: \u201C${value}\u201D` : `Recorded: \u201C${value}\u201D - send a message to carry the thread on.`));
        card.classList.add(cls("done"));
        if (out.session) this.hooks.onSession(out.session);
      } catch (e) {
        clear(
          row,
          h("div", { class: "error" }, e.message),
          h("button", { onclick: () => void send(value) }, "Retry")
        );
      }
    };
    if (options && options.length) {
      row.append(...options.map((o) => h("button", { onclick: () => void send(o) }, o)));
    } else {
      const input = h("input", {
        type: "text",
        "aria-label": String(event.question ?? ""),
        placeholder: "Your answer"
      });
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          void send(input.value);
        }
      });
      row.append(input, h("button", { onclick: () => void send(input.value) }, "Answer"));
    }
    const offering = offeringAsked(event);
    if (offering && this.hooks.openOffering) {
      row.append(h("button", { class: "ghost", onclick: () => this.hooks.openOffering(offering) }, "Read the draft"));
    }
    const card = h(
      "div",
      { class: "perm", role: "group", "aria-label": "Question" },
      h("strong", {}, "The librarian is asking"),
      " \xB7 ",
      h("span", { class: "dim" }, String(event.kind ?? "clarify")),
      h("div", {}, String(event.question ?? "")),
      row
    );
    this.cards.set(`q:${id}`, card);
    this.append(card);
    card.querySelector("input, button")?.focus();
  }
  // -- the plan -----------------------------------------------------------
  renderPlan(session) {
    if (!session) {
      clear(
        this.plan,
        h("p", { class: "dim" }, "No thread yet. Sessions \u25BE picks one up; the librarian opens one when it needs to.")
      );
      return;
    }
    const phases = session.phases ?? [];
    const current = phases.indexOf(session.phase);
    const questions = (session.questions ?? []).filter((q) => q.answer === null || q.answer === void 0);
    const libraryItems = session.library_items ?? [];
    const libraryCounts = session.library_item_counts ?? libraryItems.reduce((counts, item) => {
      counts[item.status] = (counts[item.status] ?? 0) + 1;
      return counts;
    }, {});
    const libraryItemCount = Number(session.library_item_count ?? libraryItems.length);
    clear(
      this.plan,
      h("h3", {}, "Phases"),
      h("ul", {}, phases.map((p, i) => h(
        "li",
        { class: i > current ? "dim" : "" },
        `${i < current ? "\u2611" : i === current ? "\u25D0" : "\u25CB"} ${PHASE_LABEL[p] ?? p}`,
        i === current && session.budget_left !== void 0 ? h("span", { class: "dim" }, ` \xB7 ${session.budget_left} calls left`) : null
      ))),
      this.extendBudget(session),
      questions.length ? h("h3", {}, "Waiting for you") : null,
      questions.map((q) => this.question(session, q)),
      h("h3", {}, "Next"),
      h("p", {}, String(session.next ?? "")),
      (session.open_items ?? []).length ? h("h3", {}, "Open") : null,
      (session.open_items ?? []).length ? h("ul", {}, session.open_items.map((t) => h("li", {}, t))) : null,
      this.predicateInspector(session),
      this.coverage(session),
      Object.keys(session.briefs ?? {}).length ? h("h3", {}, "Briefs") : null,
      Object.entries(session.briefs ?? {}).map(([id, b]) => h("p", {}, h("strong", {}, id), ` ${b.need ?? ""}`, b.status === "closed" ? h("span", { class: "dim" }, " \xB7 closed") : null)),
      libraryItemCount ? h("h3", {}, `Library sources \xB7 ${libraryItemCount}`) : null,
      libraryItemCount ? h("p", { class: "dim" }, Object.entries(libraryCounts).map(([status, count]) => `${count} ${status}`).join(" \xB7 ")) : null,
      libraryItems.length ? h("ul", {}, libraryItems.slice(-12).map((item) => h(
        "li",
        {},
        item.path ? link(item.path, String(item.source ?? item.path), this.hooks.openNote) : String(item.source ?? item.id),
        ` \xB7 ${item.status}`
      ))) : null,
      (session.checkpoints ?? []).length ? h("h3", {}, `Checkpoint, round ${(session.checkpoints ?? []).length}`) : null,
      (session.checkpoints ?? []).slice(-1).map((c) => h(
        "ul",
        {},
        h("li", {}, `Learned: ${c.learned ?? ""}`),
        (c.subthreads ?? []).length ? h("li", {}, `Open: ${(c.subthreads ?? []).length} sub-threads`) : null,
        (c.next_targets ?? []).length ? h("li", {}, `Next: ${(c.next_targets ?? []).join(", ")}`) : null
      )),
      (session.writes ?? []).length ? h("h3", {}, "Written") : null,
      (session.writes ?? []).length ? h("ul", {}, session.writes.map((w) => h("li", {}, w.path ? link(w.path, pathName(w.path), this.hooks.openNote) : w.tool))) : null
    );
  }
  question(session, q) {
    const box = h("div", { class: "question" }, h("p", {}, q.question));
    const send = async (answer) => {
      try {
        const out = await this.api.tool("answer", { question_id: q.id, answer }, session?.session ?? "");
        if (out.error) throw new Error(String(out.detail ?? out.error));
        this.hooks.onSession(out.session ?? session);
      } catch (e) {
        box.append(h("div", { class: "error" }, e.message));
      }
    };
    const offering = offeringAsked(q);
    if ((q.options ?? []).length) {
      box.append(h(
        "div",
        { class: "row" },
        q.options.map((o) => h("button", { onclick: () => send(o) }, o)),
        offering && this.hooks.openOffering ? h("button", { class: "ghost", onclick: () => this.hooks.openOffering(offering) }, "Read the draft") : null
      ));
    } else {
      const input = h("input", { type: "text", "aria-label": q.question, placeholder: "Your answer" });
      box.append(h(
        "div",
        { class: "row" },
        input,
        h("button", { onclick: () => input.value.trim() && send(input.value.trim()) }, "Answer")
      ));
    }
    return box;
  }
};
function inspectorRequirements(view) {
  const direct = namedRows(view.requirements, "id");
  if (direct.length) return direct;
  const grouped = /* @__PURE__ */ new Map();
  for (const row of namedRows(view.predicates, "id")) {
    const requirement = String(row.requirement ?? "Requirement");
    let parent = grouped.get(requirement);
    if (!parent) {
      parent = {
        id: requirement,
        text: row.requirement_text,
        closure: row.closure,
        status: row.status,
        revision: row.revision,
        predicates: []
      };
      grouped.set(requirement, parent);
    }
    parent.predicates.push({
      ...row,
      text: row.predicate ?? row.text,
      outcome: row.outcome ?? row.result?.outcome ?? (row.result?.stale ? "stale" : "not_checked"),
      verifier: row.verifier ?? row.authority,
      decision_path: row.decision_path ?? row.decision?.path,
      missing_subject_keys: row.missing_subject_keys ?? row.missing_bindings
    });
  }
  return [...grouped.values()];
}
function namedRows(value, idKey) {
  if (Array.isArray(value)) return value.flatMap((row) => {
    if (row && typeof row === "object") return [row];
    return row === void 0 || row === null || row === "" ? [] : [{ [idKey]: String(row) }];
  });
  if (!value || typeof value !== "object") return [];
  return Object.entries(value).map(([id, raw]) => {
    if (raw && typeof raw === "object" && !Array.isArray(raw))
      return { [idKey]: id, ...raw };
    return { [idKey]: id, value: raw };
  });
}
function predicateRows(value, requirementId) {
  if (Array.isArray(value)) return value.filter((row) => row && typeof row === "object");
  if (!value || typeof value !== "object") return [];
  return Object.entries(value).map(([text, raw], index) => {
    if (raw && typeof raw === "object" && !Array.isArray(raw))
      return { text, id: `${requirementId}.p${index + 1}`, ...raw };
    return { text, id: `${requirementId}.p${index + 1}`, outcome: raw };
  });
}
function safeClass(value) {
  return value.toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-|-$/g, "") || "unknown";
}
function changedFiles(edits) {
  return h(
    "div",
    { class: "inspector-edits" },
    h("h4", {}, "Files changed after earlier checks"),
    h("p", { class: "dim" }, "Each change advanced the audit epoch, so every requirement checked before it is stale, not only those that read the changed file."),
    h("ul", {}, edits.map((edit) => h(
      "li",
      {},
      h("code", {}, String(edit.path ?? "")),
      ` \xB7 ${String(edit.source ?? "edited")}${edit.fingerprint === "" ? " \xB7 deleted" : ""}${edit.epoch !== void 0 ? ` \xB7 epoch ${String(edit.epoch)}` : ""}`
    )))
  );
}
function statusLabel(value) {
  const labels = {
    not_checked: "not checked",
    no_suitable_tool: "no suitable tool",
    human_accepted: "person accepted",
    inconclusive: "inconclusive"
  };
  return labels[value] ?? value.replace(/_/g, " ");
}
function closureLabel(value) {
  const labels = {
    authoritative: "Core-verifiable requirement",
    partial: "Partial evidence requirement",
    human_judgment: "Person-acceptance requirement"
  };
  return labels[value] ?? value.replace(/_/g, " ");
}
function decisionLabel(value) {
  const labels = {
    core_verification: "Core verification from exact or bounded checks",
    person_acceptance: "Person acceptance of an exact artifact \u2014 not verification",
    partial_only: "Advisory or partial support only",
    partial: "Advisory or partial support only",
    acceptance: "Person acceptance \u2014 not verification"
  };
  return labels[value] ?? (value ? value.replace(/_/g, " ") : "Not established yet");
}
function displayValue(value) {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
function pathName(path2) {
  return path2.split("/").pop().replace(/\.md$/, "");
}
function sentence(text) {
  const t = text.trim();
  return t ? t[0].toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? "" : ".") : "";
}
function refusalView(r) {
  const known = /* @__PURE__ */ new Set(["error", "refused", "rule", "detail", "tool"]);
  const extra = Object.fromEntries(Object.entries(r).filter(([k]) => !known.has(k)));
  return h(
    "span",
    { class: "error" },
    `refused (${String(r.refused ?? r.error)}): ${String(r.detail ?? "")}`,
    Object.keys(extra).length ? h(
      "details",
      { class: "refusal-details" },
      h("summary", {}, "Details"),
      h("pre", {}, JSON.stringify(extra, null, 2))
    ) : null
  );
}
function stopReasonView(stop) {
  const who = stop.by === "person" ? "you" : stop.by === "core" ? "the Core" : String(stop.by ?? "the Core");
  return h(
    "p",
    { class: "inspector-stop" },
    h("strong", {}, `${stop.status === "failed" ? "Failed" : "Stopped"}, by ${who}`),
    stop.reason ? `: ${String(stop.reason)}` : "",
    stop.epoch !== void 0 ? ` (epoch ${String(stop.epoch)})` : ""
  );
}
function summarise(tool, r, openNote) {
  if (r.error === "refused" || r.refused) return refusalView(r);
  if (r.error) return h("span", {}, `failed: ${r.detail ?? r.error}`);
  if (Array.isArray(r.results)) {
    const found = r.results.slice(0, 3).filter((x) => x.name);
    const frag = h(
      "span",
      {},
      `${r.results.length} result${r.results.length === 1 ? "" : "s"}`,
      r.verdict ? ` \xB7 ${r.verdict}` : "",
      found.length ? " \xB7 " : ""
    );
    found.forEach((x, i) => {
      if (i) frag.append(", ");
      frag.append(link(x.fields?.path ?? x.name, x.name, openNote));
    });
    return frag;
  }
  if (r.promoted && typeof r.promoted === "string") return h("span", {}, "wrote ", link(r.promoted, pathName(r.promoted), openNote));
  if (r.staged && typeof r.staged === "string") return h("span", {}, `staged ${pathName(r.staged)}`);
  if (r.opened) return h("span", {}, `opened a thread (${(r.phases ?? []).join(" \u2192 ")})`);
  if (r.moved) return h("span", {}, `moved to ${PHASE_LABEL[r.moved] ?? r.moved}`);
  if (r.moved === false) return h("span", {}, "stayed: the phase is not finished");
  if (r.question_id && r.answer !== void 0) return h("span", {}, `asked and answered: \u201C${String(r.answer).slice(0, 80)}\u201D`);
  if (r.needs_person || r.question_id) return h("span", {}, "asked you a question (see the plan)");
  if (tool === "get_note" && r.name) return h("span", {}, "read ", link(r.path ?? r.name, r.name, openNote));
  if (r.path && typeof r.path === "string") return h("span", {}, "wrote ", link(r.path, pathName(r.path), openNote));
  return h("span", {}, "done");
}

// ../ui/src/panels.ts
var MODES = [
  ["plan", "Plan", "Reads and searches. Writes are refused: the librarian proposes instead."],
  ["ask", "Ask permission", "Every write pauses for you, with Allow once, Allow for this session, or Deny."],
  ["auto", "Auto", "Writes within the phase gate and the vault's settings. Sensitive material still waits for you."]
];
var ACTIONS = {
  "review-due": [COMMANDS["review-due"], "Open parked learning sessions for concepts due for review."],
  "clear-enrichment-backlog": [COMMANDS["clear-enrichment-backlog"], "Fetch, describe and stage everything queued. Background, cancellable."],
  "deep-read-staged": ["Deep-read staged sources", "Read each staged source's whole text: claims and limits with pages, and lenses to review. Background, cancellable."],
  "review-conversation": ["Review this conversation for sources", "A bounded snapshot of recent turns \u2192 suggested sources. Writes nothing."],
  "weekly-review": ["Weekly review of a pursuit", "Its tasks, what was read and written, its desk \u2192 a drafted reflection for you to read. Writes nothing until you accept it."]
};
var PROVIDERS = {
  deepinfra: "DeepInfra",
  openai: "OpenAI",
  anthropic: "Anthropic",
  local: "Local server"
};
var ROLES = ["leads the session", "writes notes", "small tasks"];
function profileMeta(m) {
  if (m.profiling === "queued") return "profiling: awaiting your review in Staging";
  const p = m.profile;
  if (!p) return "unprofiled";
  const parts = p.shared ? ["shared profile"] : [];
  if (p.suggested_tier) parts.push(String(p.suggested_tier).replace(/_/g, " "));
  const bestFor = p.best_for ?? [];
  if (bestFor.length) parts.push(bestFor.map((t) => String(t).replace(/_/g, " ")).join(", "));
  if (p.context_length) parts.push(`${Math.round(p.context_length / 1e3)}k ctx`);
  if (p.price_input_per_1m || p.price_output_per_1m) {
    parts.push(`$${p.price_input_per_1m ?? 0} / $${p.price_output_per_1m ?? 0} per 1M`);
  }
  parts.push(p.tool_calling === true ? "tool calling" : p.tool_calling === false ? "no tool calling" : "tool calling unknown");
  return parts.filter(Boolean).join(" \xB7 ");
}
var SEEDED = /* @__PURE__ */ new Set(["deepinfra", "openai", "anthropic", "local"]);
function sameHost(a, b) {
  const norm = (v) => {
    const s = String(v ?? "");
    return s.startsWith("preset-") && SEEDED.has(s.slice("preset-".length)) ? s.slice("preset-".length) : s;
  };
  return norm(a) === norm(b);
}
function adapterMeta(m) {
  const adapter = m.adapter;
  if (!adapter || typeof adapter !== "object") return "";
  const expectation = adapter.expectation && typeof adapter.expectation === "object" ? adapter.expectation : {};
  const capabilities = adapter.capabilities && typeof adapter.capabilities === "object" ? adapter.capabilities : {};
  const parts = [`adapter: ${String(adapter.id ?? "unknown").replace(/_/g, " ")}`];
  if (!expectation.id) parts.push("no model expectation yet");
  else if (capabilities.tool_use === "unknown") parts.push("tool behaviour unverified");
  else if (capabilities.tool_use === "false") parts.push("tool use unsupported");
  else parts.push(`expectation: ${String(expectation.status ?? "reviewed")}`);
  return parts.join(" \xB7 ");
}
var Popover = class {
  /** `id` is mount-unique; `kind` is the stable class the stylesheet targets. */
  constructor(id, label, button, kind = "") {
    this.button = button;
    this.observer = null;
    this.el = h("div", { class: `lib-popover ${kind}`, id, hidden: true, role: "dialog", "aria-label": label });
    button.setAttribute("aria-haspopup", "true");
    button.setAttribute("aria-expanded", "false");
    button.setAttribute("aria-controls", id);
    if (typeof MutationObserver !== "undefined") {
      this.observer = new MutationObserver(() => {
        if (this.open && !this.el.contains(document.activeElement)) this.focusFirst();
      });
      this.observer.observe(this.el, { childList: true });
    }
  }
  get open() {
    return !this.el.hidden;
  }
  focusFirst() {
    this.el.querySelector("input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])")?.focus();
  }
  show(on) {
    const wasOpen = this.open;
    const focusInside = this.el.contains(document.activeElement);
    this.el.hidden = !on;
    this.button.setAttribute("aria-expanded", String(on));
    if (on) this.focusFirst();
    else if (wasOpen && focusInside) this.button.focus();
  }
  dispose() {
    this.observer?.disconnect();
    this.observer = null;
  }
};
function renderModes(pop, api, mode, queued, pipelines, report, needs = {}, radioName = "librarian-mode", scope = "") {
  let confirmed = mode;
  const group = h(
    "div",
    { role: "radiogroup", "aria-label": "Permission mode" },
    MODES.map(([value, label, help]) => h(
      "label",
      { class: "opt" },
      h("input", {
        type: "radio",
        name: radioName,
        value,
        checked: value === mode,
        onchange: async (event) => {
          try {
            await api.post("/api/mode", { mode: value });
            confirmed = value;
          } catch (e) {
            const radios = event.target.closest("[role=radiogroup]")?.querySelectorAll(`input[name="${radioName}"]`) ?? [];
            radios.forEach((radio) => {
              radio.checked = radio.value === confirmed;
            });
            report(`Mode not changed: ${e.message}`);
          }
        }
      }),
      h("span", {}, label, h("small", {}, help))
    ))
  );
  const extra = pipelines.filter((p) => !queued.includes(p) && !p.startsWith("review-item"));
  const run = async (name, inputs = {}) => {
    pop.show(false);
    try {
      await api.post("/api/actions", { name, inputs });
    } catch (e) {
      report(e.message);
    }
  };
  const start2 = (name) => async () => {
    const wanted = needs[name];
    if (!wanted || !Object.keys(wanted).length) {
      await run(name);
      return;
    }
    const fields = {};
    const rows = await Promise.all(Object.keys(wanted).map(async (key) => {
      let el;
      if (key === "project") {
        let names = [];
        try {
          const listing = await api.get("/api/files?dir=Projects");
          names = (listing.entries ?? []).filter((e) => e.kind !== "dir").map((e) => String(e.name).replace(/\.md$/, ""));
        } catch {
        }
        el = names.length ? h("select", { class: "f" }, names.map((n) => h("option", { value: n }, n))) : h("input", { type: "text", class: "f", placeholder: "the pursuit's name" });
      } else {
        el = h("input", { type: "text", class: "f", placeholder: key });
      }
      el.id = `${radioName}-queue-${name}-${key}`;
      fields[key] = el;
      return h("div", {}, h("label", { class: "f", for: el.id }, key === "project" ? "Pursuit" : key), el);
    }));
    clear(
      pop.el,
      h("h4", {}, (ACTIONS[name] ?? [name])[0]),
      rows,
      h(
        "div",
        { class: "row2" },
        h("button", { class: "primary", onclick: () => {
          const inputs = Object.fromEntries(Object.entries(fields).map(([k, el]) => [k, el.value.trim()]));
          if (Object.values(inputs).some((v) => !v)) {
            report("Fill in every field first.");
            return;
          }
          void run(name, inputs);
        } }, "Start"),
        h("button", { class: "ghost", onclick: () => renderModes(pop, api, mode, queued, pipelines, report, needs, radioName, scope) }, "Back")
      )
    );
  };
  clear(
    pop.el,
    h("h4", {}, "Permission mode"),
    group,
    h("h4", { class: "gap" }, "Queue an action"),
    scope ? h("p", { class: "note" }, scope) : null,
    queued.map((name) => h(
      "button",
      { class: "menuitem", "data-command": name, onclick: start2(name) },
      COMMANDS[name] ?? (ACTIONS[name] ?? [name])[0],
      h("small", {}, (ACTIONS[name] ?? ["", "A pipeline."])[1])
    )),
    extra.length ? h("h4", { class: "gap" }, "This vault's pipelines") : null,
    extra.map((name) => h("button", { class: "menuitem", "data-command": name, onclick: start2(name) }, COMMANDS[name] ?? name))
  );
}
var VISION = /(-vl\b|vl-|vision|ocr|gemma-[34]|qwen3\.[5-9]|llama-4|pixtral|llava|inkling|glimmer)/i;
var EMBED = /(bge|embed|e5-|gte-|nomic|minilm|mpnet|potion|jina|arctic)/i;
var SLOT_KIND = {
  ocr: { label: "Vision models", fits: (m) => m.profile?.modality === "Image_To_Text" || VISION.test(String(m.id)) },
  embeddings: { label: "Embedding models", fits: (m) => m.profile?.modality === "Embeddings" || EMBED.test(String(m.id)) },
  tts: { label: "Speech models", fits: (m) => m.profile?.modality === "Text_To_Speech" || /tts|kokoro|chatterbox|orpheus|speech|higgs/i.test(String(m.id)) },
  stt: { label: "Speech-recognition models", fits: (m) => m.profile?.modality === "Speech_To_Text" || /asr|whisper|voxtral|speech[ _-]?recognition|transcrib/i.test(String(m.id)) }
};
var ModelTile = class {
  constructor(pop, api, tiers, keysSaved, setTiers = () => {
  }) {
    this.pop = pop;
    this.api = api;
    this.tiers = tiers;
    this.keysSaved = keysSaved;
    this.setTiers = setTiers;
    this.listings = /* @__PURE__ */ new Map();
    /**
     * Route evidence is deliberately separate from the provider listings.  A
     * listing says what an endpoint returned; readiness says whether the Core
     * can safely use that exact route for the current profile.  Older Cores do
     * not expose this endpoint, so its absence must not make the picker fail.
     */
    this.readiness = /* @__PURE__ */ new Map();
    this.readinessAvailable = false;
    this.coreReadiness = null;
    this.readinessEpoch = 0;
    this.filter = "";
    this.toast = "";
    // R10: a lead the completion suite (M0) has not qualified waits here for the person's
    // recorded "use it anyway", instead of being taken silently.
    this.pendingLead = null;
    // R17: the same tile, choosing one service model (slot 4 OCR, ...) instead of the tiers.
    this.slot = null;
    this.showAll = false;
  }
  recentKey() {
    return "recent." + (this.slot?.role ?? this.slot?.name ?? "chat");
  }
  recordRecent(provider, model) {
    try {
      const key = this.recentKey(), rows = JSON.parse(preference(key, "[]"));
      remember(key, JSON.stringify([provider + "/" + model, ...rows.filter((x) => x !== provider + "/" + model)].slice(0, 5)));
    } catch {
    }
  }
  startSlot(name, label, done, current, role) {
    this.pendingLead = null;
    this.slot = { name, label, done, current, role };
    this.showAll = false;
    this.filter = "";
    this.toast = "";
  }
  cancelSlot() {
    if (!this.slot) return false;
    const done = this.slot.done;
    this.endSlot();
    done();
    return true;
  }
  dispose() {
    window.clearTimeout(this.press);
    this.endSlot();
  }
  endSlot() {
    this.slot = null;
    this.pendingLead = null;
  }
  /** Right-click on the slot's own model: the slot is emptied (never filled by a chat
   *  model - R17). */
  async clearSlot() {
    const slot = this.slot;
    try {
      await this.api.post("/api/services", { slot: slot.name, provider: "", model: "" });
      this.slot = null;
      slot.done();
    } catch (e) {
      this.toast = e.message;
      this.render();
    }
  }
  async pickSlot(provider, model) {
    const slot = this.slot;
    if (slot.role !== void 0) {
      const tiers = [...this.tiers()];
      const entry = this.listings.get(provider)?.models?.find((m) => m.id === model);
      if (slot.role > tiers.length) this.toast = "Choose the preceding role first.";
      else if (slot.role === 0 && entry?.profile?.tool_calling === false) this.toast = "This model does not support the tools required to lead.";
      else {
        tiers[slot.role] = { provider, model };
        if (await this.save(tiers)) {
          this.recordRecent(provider, model);
          this.endSlot();
          slot.done();
          return;
        }
      }
      this.render();
      return;
    }
    try {
      await this.api.post("/api/services", { slot: slot.name, provider, model });
      this.recordRecent(provider, model);
      this.slot = null;
      slot.done();
    } catch (e) {
      this.toast = e.message;
      this.render();
    }
  }
  async refresh() {
    const saved = this.keysSaved();
    await Promise.all(Object.keys(PROVIDERS).map(async (p) => {
      if (p !== "local" && !saved[p]) {
        this.listings.set(p, { status: "no key", models: [] });
        return;
      }
      try {
        this.listings.set(p, await this.api.get(`/api/models?provider=${p}`));
      } catch (e) {
        this.listings.set(p, { status: "error", error: e.message, models: [] });
      }
    }));
    this.render();
    const epoch = ++this.readinessEpoch;
    void this.refreshReadiness(epoch);
  }
  async refreshReadiness(epoch) {
    const readiness = await this.api.get("/api/routes/readiness").catch(() => null);
    if (epoch !== this.readinessEpoch) return;
    this.readiness.clear();
    this.readinessAvailable = !!readiness;
    this.coreReadiness = readiness?.core ?? readiness?.workflow ?? null;
    const routes = Array.isArray(readiness?.routes) ? readiness.routes : [];
    for (const row of routes) {
      if (!row || typeof row !== "object") continue;
      const provider = String(row.host_id ?? row.provider ?? row.host ?? "");
      const model = String(row.model ?? row.model_id ?? "");
      if (provider && model) this.readiness.set(`${provider}\0${model}`, row);
    }
    if (this.pop.open) this.render();
  }
  routeReadiness(provider, model) {
    return this.readiness.get(`${provider}\0${model}`) ?? null;
  }
  readinessText(value, good, bad, pending) {
    const state = value && typeof value === "object" ? value.ok ?? value.status ?? value.state : value;
    if (state === true || state === "pass" || state === "ready" || state === "passed") return good;
    if (state === false || state === "fail" || state === "blocked" || state === "error") return bad;
    return pending;
  }
  readinessChips(provider, model) {
    if (this.slot && this.slot.role === void 0) return null;
    const row = this.routeReadiness(provider, model);
    if (!row) return null;
    const tiers = this.tiers();
    const selected = tiers.findIndex((t) => sameHost(t.provider, provider) && t.model === model);
    const role = ["lead", "scribe", "clerk"][this.slot?.role ?? (selected >= 0 ? selected : Math.min(tiers.length, 2))];
    const evidence = row.qualification_by_role?.[role] ?? (row.role === role ? row.qualification : null);
    const qualification = evidence?.status ?? "evidence pending";
    const workflow = row.core_workflow ?? row.workflow_ready ?? row.workflow;
    const fixture = row.fixture_preflight ?? row.fixture_ready;
    const health = row.host_health && typeof row.host_health === "object" ? row.host_health.status : row.host_health ?? row.health;
    const labels = [
      `${role}: ${String(qualification).replace(/_/g, " ")}`,
      evidence?.freshness && !["current", "missing"].includes(evidence.freshness) ? `${role}: ${String(evidence.freshness).replace(/_/g, " ")}` : "",
      row.active_task && row.role !== role ? `${row.task_profile} task: ${String(row.qualification?.status ?? "evidence pending").replace(/_/g, " ")}` : "",
      row.binding_errors?.[role] ? `${role}: route unavailable` : "",
      this.readinessText(workflow, "walk ready", "walk blocked", "walk unchecked"),
      this.readinessText(fixture, "fixtures ready", "fixture issue", "fixtures unchecked"),
      this.readinessText(health, "host ready", "host issue", "host unchecked")
    ];
    const detail = String(row.detail ?? row.reason ?? row.advisory ?? "");
    return h(
      "div",
      { class: "readiness", title: detail },
      labels.filter((value, index, all) => value && all.indexOf(value) === index).map((value) => h("span", { class: `readiness-chip ${/blocked|issue|experimental|unavailable|stale/i.test(value) ? "warn" : ""}` }, value))
    );
  }
  readinessSummary() {
    if (!this.readinessAvailable) return null;
    const value = this.coreReadiness;
    const status = value && typeof value === "object" ? value.ok ?? value.status ?? value.state : value;
    const good = status === true || status === "pass" || status === "ready" || status === "passed";
    const label = good ? "Core workflow checks ready" : status ? `Core workflow: ${String(status).replace(/_/g, " ")}` : "Core workflow evidence available";
    const detail = value && typeof value === "object" ? String(value.detail ?? value.reason ?? "") : "";
    return h(
      "p",
      { class: `route-summary${good ? "" : " warn"}`, title: detail },
      label,
      detail ? h("span", { class: "dim" }, ` \xB7 ${detail}`) : null
    );
  }
  async save(tiers, override = "") {
    try {
      const consent = override ? { override } : {};
      const saved = this.slot?.role === 0 ? await this.api.post("/api/lead", { route: tiers[0], ...consent }) : await this.api.post("/api/tiers", { tiers, ...consent });
      this.pendingLead = null;
      this.setTiers(saved.tiers ?? tiers);
      void this.refreshReadiness(++this.readinessEpoch);
      return true;
    } catch (e) {
      const body = e.body ?? {};
      if (body.needs_override) this.pendingLead = { tiers, lead: String(body.lead ?? "") };
      this.toast = e.message;
      return false;
    }
  }
  overridePrompt() {
    const pending = this.pendingLead;
    if (!pending) return null;
    const reason = h("input", {
      type: "text",
      "aria-label": "Why use it anyway",
      value: "chosen before the completion suite had run"
    });
    return h(
      "div",
      { class: "warn", role: "alert" },
      h("p", {}, this.toast),
      h(
        "div",
        { class: "row2 tight" },
        reason,
        h("button", { class: "primary", onclick: async () => {
          this.toast = "";
          if (await this.save(pending.tiers, reason.value.trim() || "chosen by the person") && this.slot?.role !== void 0) {
            const done = this.slot.done;
            this.endSlot();
            done();
            return;
          }
          this.render();
        } }, "Use it as lead anyway"),
        h("button", { class: "ghost", onclick: () => {
          this.pendingLead = null;
          this.toast = "";
          this.render();
        } }, "Choose another")
      )
    );
  }
  async clearAll() {
    if (await this.save([])) this.toast = "Selection cleared. Click models in order again.";
    this.render();
  }
  async pick(provider, model) {
    if (this.slot) return this.pickSlot(provider, model);
    const tiers = this.tiers();
    const at = tiers.findIndex((t) => sameHost(t.provider, provider) && t.model === model);
    const entry = (this.listings.get(provider)?.models ?? []).find((m) => m.id === model);
    if (at >= 0) {
      this.toast = `${model} is tier ${at + 1}. Right-click it, press Delete, or use Clear selection to start again.`;
    } else if (tiers.length >= 3) {
      this.toast = "All three tiers are chosen. Clear the selection to start again.";
    } else if (tiers.length === 0 && entry?.profile && entry.profile.tool_calling === false) {
      this.toast = `${model} can't lead a session: it is profiled as not supporting tool calling. It can still be chosen as tier 2 or 3.`;
    } else {
      const next = [...tiers, { provider, model }];
      this.toast = next.length === 1 ? "Only tier 1 is chosen, so it also writes notes and runs small tasks. A small tier 3 is usually more reliable on closed questions." : "";
      await this.save(next);
    }
    this.render();
  }
  async profile(provider, model) {
    this.toast = `Profiling ${model}\u2026`;
    this.render();
    try {
      const out = await this.api.tool("ingest", { ref: `model:${provider}:${model}` });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      this.toast = out.status === "already_held" ? `${model} is already catalogued.` : `${model} is staged for review \u2014 accept it under Staging to finish profiling it.`;
    } catch (e) {
      this.toast = `Could not profile ${model}: ${e.message}`;
    }
    await this.refresh();
  }
  render() {
    const tiers = this.tiers();
    const slots = [0, 1, 2].map((i) => {
      const t = tiers[i];
      const fallback = !t && i > 0 && tiers.length ? `uses tier ${Math.min(i, tiers.length)}` : "not chosen";
      return h(
        "span",
        {
          class: "slot",
          title: t ? "Right-click to clear the chosen models" : "",
          oncontextmenu: (e) => {
            if (tiers.length) {
              e.preventDefault();
              void this.clearAll();
            }
          }
        },
        h("span", { class: "badge" }, String(i + 1)),
        t ? `${t.model} \xB7 ${PROVIDERS[t.provider] ?? t.provider}` : h("span", { class: "dim" }, fallback),
        h("span", { class: "dim" }, ` \xB7 ${ROLES[i]}`)
      );
    });
    const filter = h("input", {
      type: "search",
      placeholder: "Filter by name or description, e.g. tool calling, long horizon, 1m ctx",
      "aria-label": "Filter models",
      value: this.filter,
      oninput: (e) => {
        this.filter = e.target.value;
        this.renderGrids(grids);
      }
    });
    const grids = h("div", {});
    if (this.slot) {
      const slot = this.slot;
      const quick = preference("model-view") === "quick";
      let recent = [];
      try {
        recent = JSON.parse(preference(this.recentKey(), "[]"));
      } catch {
      }
      const recentOptions = Object.keys(PROVIDERS).flatMap((p) => (this.listings.get(p)?.models ?? []).filter((m) => recent.includes(p + "/" + m.id)).map((m) => h("button", { class: "ghost", onclick: () => this.pick(p, m.id) }, m.id + " \xB7 " + PROVIDERS[p])));
      clear(
        this.pop.el,
        h(
          "div",
          { class: "tierbar" },
          h("strong", {}, `Choose the ${slot.label} model`),
          slot.role !== void 0 ? null : h("span", { class: "dim" }, this.showAll ? "Every model is listed. Click one." : `${SLOT_KIND[slot.name]?.label ?? "Matching models"} are listed (by profile, or by name). Click one.`),
          slot.role !== void 0 ? null : h(
            "button",
            { class: "ghost", onclick: () => {
              this.showAll = !this.showAll;
              this.render();
            } },
            this.showAll ? `${SLOT_KIND[slot.name]?.label ?? "Matching models"} only` : "Show all"
          ),
          h("button", { class: "ghost", onclick: () => {
            this.endSlot();
            slot.done();
          } }, "Cancel")
        ),
        h("button", { class: "ghost", onclick: () => {
          remember("model-view", quick ? "detailed" : "quick");
          this.render();
        } }, quick ? "Compare all models" : "Quick selection"),
        quick ? h("div", {}, h("h4", {}, "Recently assigned to this role"), recentOptions.length ? recentOptions : h("p", {}, "No recent selection is available. Choose Compare all models.")) : null,
        slot.role !== void 0 ? this.overridePrompt() : null,
        slot.role === void 0 && slot.current?.model ? h("p", { class: "dim" }, `Now: ${slot.current.model}. Right-click it to empty the slot.`) : null,
        this.toast ? h("div", { class: "toast", role: "status" }, this.toast) : null,
        quick ? null : filter,
        quick ? null : grids
      );
      if (!quick) this.renderGrids(grids);
      return;
    }
    clear(
      this.pop.el,
      h(
        "div",
        { class: "tierbar" },
        h("strong", {}, "Chat models"),
        h("span", { class: "dim" }, "Click in order: 1 leads, 2 writes notes, 3 does small tasks. Right-click a chosen model, or a tier, to clear all.")
      ),
      h(
        "div",
        { class: "tierbar" },
        slots,
        tiers.length ? h("button", { class: "ghost", onclick: () => this.clearAll() }, "Clear selection") : null
      ),
      this.readinessSummary(),
      tiers.length < 3 ? h("p", { class: "note" }, `Choosing slot ${tiers.length + 1} (${ROLES[tiers.length]}): models whose profile recommends them for it are listed first.`) : null,
      this.pendingLead ? this.overridePrompt() : this.toast ? h("div", { class: "toast", role: "status" }, this.toast) : null,
      filter,
      grids,
      h("h4", {}, "OCR \xB7 Text to speech \xB7 Embeddings \xB7 Speech to text"),
      h("p", { class: "note locked" }, "These have their own assignments in Settings \u2192 Models & services, each chosen with this same tile and kept with the library."),
      h("p", { class: "note" }, "Models come from each provider's live listing. A profiled model (a Source of kind model) shows its suggested tier and best-for tags (a first guess to confirm or correct), plus context, price and tool calling; an unprofiled one can be profiled, which stages it for your review like any other source. The adapter line is protocol evidence, not a reliability verdict: run the route probe before treating an unverified tool path as ready.")
    );
    this.renderGrids(grids);
  }
  renderGrids(host) {
    const tiers = this.tiers();
    const words = this.filter.toLowerCase().split(/\s+/).filter(Boolean);
    const matches = (m) => {
      const text = `${m.id} ${profileMeta(m)} ${adapterMeta(m)}`.toLowerCase().replace(/_/g, " ");
      return words.every((w) => text.includes(w));
    };
    const next = this.slot || tiers.length >= 3 ? 0 : tiers.length + 1;
    const recommended = (m) => next > 0 && String(m.profile?.suggested_tier ?? "") === `Tier_${next}`;
    clear(host, Object.entries(PROVIDERS).map(([p, label]) => {
      const listing = this.listings.get(p) ?? { status: "\u2026", models: [] };
      const models = listing.models.filter(matches).filter((m) => !this.slot || this.showAll || (SLOT_KIND[this.slot.name]?.fits(m) ?? true)).map((m, i) => ({ m, i })).sort((a, b) => Number(recommended(b.m)) - Number(recommended(a.m)) || a.i - b.i).map(({ m }) => m);
      const status = listing.status === "ready" ? `${listing.models.length} model${listing.models.length === 1 ? "" : "s"}` : listing.status === "no key" ? "no key saved (Settings \u2192 Providers & keys)" : listing.status === "offline" ? "offline: the local server is not running" : listing.error ? `error: ${listing.error}` : listing.status;
      return h(
        "section",
        { class: "model-provider" },
        h("h4", {}, h("span", { class: `dot ${listing.status === "ready" ? "" : listing.status === "no key" ? "nokey" : "off"}` }), `${label} \xB7 ${status}`),
        models.length ? h("div", { class: "model-grid" }, models.slice(0, 60).map((m) => {
          const inSlot = sameHost(this.slot?.current?.provider, p) && this.slot?.current?.model === m.id;
          const at = this.slot ? inSlot ? 0 : -1 : tiers.findIndex((t) => sameHost(t.provider, p) && t.model === m.id);
          const clear2 = () => this.slot?.role !== void 0 ? void 0 : this.slot ? this.clearSlot() : this.clearAll();
          const rec = at < 0 && recommended(m);
          const readiness = this.readinessChips(p, String(m.id));
          let dragged = false, held = false;
          const card = h(
            "button",
            {
              class: `model-card${at >= 0 ? " sel" : ""}${rec ? " rec" : ""}`,
              "aria-pressed": at >= 0 ? "true" : "false",
              title: this.slot?.role !== void 0 ? void 0 : at >= 0 ? this.slot ? "Right-click (or Delete) to empty this slot" : "Right-click (or Delete) to clear the chosen models" : m.profile && m.profile.tool_calling === false ? "Profiled as not supporting tool calling: can still lead as tier 2 or 3" : "",
              onclick: (e) => {
                if (held || dragged) {
                  held = dragged = false;
                  e.preventDefault();
                  return;
                }
                void this.pick(p, m.id);
              },
              oncontextmenu: (e) => {
                if (at >= 0) {
                  e.preventDefault();
                  void clear2();
                }
              },
              onkeydown: (e) => {
                if (at >= 0 && e.key === "Delete") void clear2();
              },
              ontouchstart: () => {
                held = dragged = false;
                window.clearTimeout(this.press);
                if (at >= 0) this.press = window.setTimeout(() => {
                  held = true;
                  if (card.isConnected && this.pop.open) void clear2();
                }, 600);
              },
              ontouchmove: () => {
                dragged = true;
                window.clearTimeout(this.press);
              },
              ontouchcancel: () => {
                dragged = true;
                window.clearTimeout(this.press);
              },
              ontouchend: () => window.clearTimeout(this.press)
            },
            at >= 0 && !this.slot ? h("span", { class: "badge" }, String(at + 1)) : null,
            h("div", { class: "model-name" }, m.id),
            h("div", { class: "model-meta" }, profileMeta(m)),
            adapterMeta(m) ? h("div", { class: "model-meta" }, adapterMeta(m)) : null,
            readiness,
            rec ? h("div", { class: "rec-label" }, `Recommended for slot ${next}`) : null
          );
          return h(
            "div",
            { class: "model-card-wrap" },
            card,
            // "local" has no public listing page to profile from (see MODEL_PAGES
            // server-side); offering the action there would only fail loudly.
            p !== "local" && !m.profile && m.profiling !== "queued" ? h("button", {
              class: "profile-link",
              onclick: () => void this.profile(p, m.id)
            }, "Profile this model") : null
          );
        })) : null,
        models.length > 60 ? h("p", { class: "note" }, `${models.length - 60} more: type to filter.`) : null
      );
    }));
  }
};
async function renderLibraries(pop, api, current) {
  clear(pop.el, h("p", { class: "dim" }, "Loading libraries\u2026"));
  const status = h("p", { class: "note", role: "status" });
  const go = async (path2, force = false) => {
    clear(status, `Opening ${path2}\u2026`);
    try {
      await api.post("/api/library/switch", { path: path2, force });
      window.location.reload();
    } catch (e) {
      const err = e;
      const running = err.body?.running;
      if (err.status === 409 && running) {
        const parts = [
          running.turn ? "a reply in progress" : "",
          Array.isArray(running.actions) && running.actions.length ? `${running.actions.length} workflow(s) running` : "",
          running.waiting_on_person ? `${running.waiting_on_person} question(s) waiting for you` : ""
        ].filter(Boolean);
        clear(
          status,
          `${current} still has ${parts.join(", ")}. `,
          h("button", { class: "ghost", onclick: () => void go(path2, true) }, "Switch anyway"),
          // MF-006: the work keeps running, but its outcome is not reported
          // here - it may still fail. Say so rather than promise completion.
          h("small", {}, ` Its running work keeps going in the background, but this window will not show whether it succeeds or fails; switch back to ${current} to check. Unanswered questions time out and park their thread, so it can be resumed later.`)
        );
      } else {
        clear(status, h("span", { class: "error" }, err.message));
      }
    }
  };
  try {
    const out = await api.get("/api/libraries");
    const rows = out.libraries ?? [];
    const path2 = h("input", {
      type: "text",
      class: "f",
      placeholder: "A library's folder, e.g. D:\\Libraries\\History",
      "aria-label": "Library folder path"
    });
    path2.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && path2.value.trim()) void go(path2.value.trim());
    });
    clear(
      pop.el,
      h("h4", {}, "Libraries"),
      rows.length ? rows.map((l) => h(
        "div",
        { class: "menuitem desk-row" },
        h(
          "button",
          {
            class: "wl",
            disabled: l.current || l.missing,
            title: l.path,
            onclick: () => void go(l.path)
          },
          `${l.current ? "\u2713 " : ""}${l.name}`,
          h("small", {}, l.missing ? " \xB7 folder missing" : ` \xB7 opened ${when(l.last_opened)}`)
        ),
        l.current ? null : h("button", {
          class: "icon-btn",
          title: "Remove from this list (the library itself is untouched)",
          "aria-label": `Forget ${l.name}`,
          onclick: async (event) => {
            const button = event.currentTarget;
            button.disabled = true;
            try {
              await api.post("/api/libraries/forget", { path: l.path });
            } catch (e) {
              button.disabled = false;
              clear(status, h("span", { class: "error" }, `${l.name} was not forgotten: ${e.message}`));
              return;
            }
            void renderLibraries(pop, api, current);
          }
        }, "\u2715")
      )) : h("p", { class: "dim" }, "Only this library so far."),
      h("h4", { class: "gap" }, "Open another library"),
      h(
        "div",
        { class: "row2 tight" },
        path2,
        h("button", { class: "ghost", onclick: () => path2.value.trim() && void go(path2.value.trim()) }, "Open")
      ),
      h("small", { class: "dim" }, "One library per domain; projects live inside it as pursuits."),
      status
    );
  } catch (e) {
    clear(pop.el, h("p", { class: "error" }, `Could not list libraries: ${e.message}`));
  }
}
async function renderSessions(pop, api, attach, reset, library = "this library", libraryPath = "") {
  clear(pop.el, h("p", { class: "dim" }, "Loading threads\u2026"));
  try {
    const out = await api.tool("list_sessions");
    const rows = out.sessions ?? [];
    const sort = h("select", { "aria-label": "Sort sessions" }, h("option", { value: "created" }, "Newest created"), h("option", { value: "parked" }, "Parked first"));
    sort.value = preference("session-order", "created");
    const paint = () => {
      rows.sort((a, b) => (sort.value === "parked" ? Number(b.status === "parked") - Number(a.status === "parked") : 0) || String(b.opened_at).localeCompare(String(a.opened_at)));
      clear(
        pop.el,
        h(
          "button",
          { class: "menuitem", onclick: () => {
            pop.show(false);
            reset();
          } },
          "New conversation",
          h("small", {}, "The librarian opens a thread when it needs one.")
        ),
        h("h4", { class: "gap", title: libraryPath ? `Kept in ${libraryPath}` : "" }, `Threads in ${library}`),
        sort,
        rows.length ? rows.map((s) => h(
          "button",
          {
            class: "menuitem",
            onclick: () => {
              pop.show(false);
              attach(s.id);
            }
          },
          `${s.project || s.question || s.purpose}`,
          h("small", {}, `${s.purpose} \xB7 ${s.status} \xB7 ${s.phase} \xB7 ${when(s.opened_at)}`),
          // MF-009: opening a halted audit history views it; it does not resume it.
          s.audit_history ? h(
            "small",
            { class: "warn-text" },
            ` \xB7 read-only ${s.audit_history} audit history`
          ) : null
        )) : h("p", { class: "dim" }, "No threads in this library yet."),
        h("small", { class: "dim" }, "Another library's threads are under that library: switch to it from the library menu.")
      );
    };
    sort.onchange = () => {
      remember("session-order", sort.value);
      paint();
      sort.focus();
    };
    paint();
  } catch (e) {
    clear(pop.el, h("p", { class: "error" }, `Could not list threads: ${e.message}`));
  }
}

// ../ui/src/presets.ts
function researchSetups(api, state, refresh) {
  const root = h("details", {}, h("summary", {}, "Named research presets"));
  const list2 = h("div"), preview = h("div"), status = h("p", { role: "status" });
  const name = h("input", { type: "text", "aria-label": "New preset name", placeholder: "Preset name" });
  const read = () => JSON.parse(preference("research-setups", "[]"));
  const snapshot = (title) => {
    const s = state();
    return {
      name: title,
      context: s.working_context ?? "",
      length: s.reply_length ?? "long",
      stance: s.stance ?? "answer",
      tiers: (s.tiers ?? []).map((t) => ({ provider: t.provider, model: t.model, ...t.host_id ? { host_id: t.host_id } : {} }))
    };
  };
  function inspect(setup) {
    const now = snapshot(""), library = String(state().vault_path ?? state().vault);
    const roleNames = ["Lead", "Notes", "Small tasks"];
    const format = (s) => s.tiers.map((r, i) => roleNames[i] + ": " + (r.host_id ?? r.provider) + " / " + r.model).join("; ") || "No explicit roles";
    const apply = (roles) => async (e) => {
      const button = e.currentTarget;
      button.disabled = true;
      try {
        if (library !== String(state().vault_path ?? state().vault)) throw Error("Library changed. Preview the preset again.");
        if (roles) await api.post("/api/tiers", { tiers: setup.tiers });
        else await api.post("/api/context", { working_context: setup.context, reply_length: setup.length, stance: setup.stance });
        await refresh();
        status.textContent = (roles ? "Model roles" : "Chat preferences") + " applied to " + (state().vault_name || state().vault) + ".";
        inspect(setup);
      } catch (err) {
        status.textContent = err.message;
        button.disabled = false;
      }
    };
    clear(
      preview,
      h("h4", {}, setup.name + " \u2192 " + (state().vault_name || state().vault)),
      h("p", {}, "Saved chat instructions: ", now.context || "(empty)", " \u2192 ", setup.context || "(empty)"),
      h("p", {}, now.length + " / " + now.stance + " \u2192 " + setup.length + " / " + setup.stance),
      h("button", { class: "ghost", onclick: apply(false) }, "Apply chat preferences"),
      h("p", {}, format(now) + " \u2192 " + format(setup)),
      h("small", {}, "Role changes also update defaults for libraries without their own choices."),
      h("button", { class: "ghost", onclick: apply(true) }, "Apply model roles")
    );
  }
  function paint() {
    try {
      clear(list2, read().map((setup) => h(
        "div",
        { class: "row2" },
        h("strong", {}, setup.name),
        h("button", { class: "ghost", onclick: () => inspect(setup) }, "Preview"),
        h("button", { class: "ghost", onclick: () => {
          remember("research-setups", JSON.stringify(read().filter((row) => row.name !== setup.name)));
          clear(preview);
          paint();
        } }, "Remove preset")
      )));
    } catch {
      status.textContent = "Saved presets could not be read.";
    }
  }
  root.append(
    h("p", {}, "Save this library\u2019s current chat instructions, length, stance and model roles in this browser. Preview changes before applying them to another library at this address."),
    name,
    h("button", { class: "ghost", onclick: () => {
      try {
        const rows = read(), title = name.value.trim();
        if (!title || rows.some((r) => r.name === title)) {
          status.textContent = "Enter a unique preset name.";
          return;
        }
        remember("research-setups", JSON.stringify([...rows, snapshot(title)]));
        name.value = "";
        status.textContent = "Preset saved.";
        paint();
      } catch {
        status.textContent = "Could not save the preset in this browser.";
      }
    } }, "Save current settings as preset"),
    list2,
    preview,
    status
  );
  paint();
  return root;
}

// ../ui/src/settings.ts
var GROUPS = [
  ["Environment", [["commands", "Commands & shortcuts"], ["connections", "Providers & keys"], ["mcp", "Tools & integrations"]]],
  ["Current library", [
    ["models", "Models & services"],
    ["context", "Chat behaviour"],
    ["review", "Review & promotion"],
    ["projects", "Project access"],
    ["methods", "Methods & lenses"],
    ["topics", "Topics & organisation"]
  ]],
  ["Advanced", [["profiles", "Agent profiles"], ["health", "Health & diagnostics"]]]
];
var CHAT_ROLES = [
  ["Lead", "Plans and coordinates the research session"],
  ["Notes", "Writes source descriptions and notes"],
  ["Small tasks / reviewer", "Handles bounded tasks and advisory checks"]
];
var SERVICE_NAMES = {
  ocr: "Document reading / OCR",
  tts: "Read aloud",
  stt: "Speech recognition",
  embeddings: "Semantic search"
};
var CURATED_SKILLS = [
  {
    id: "semantic-scholar",
    name: "Semantic Scholar",
    description: "Search papers, citations and authors - fills the literature gap.",
    command: "uvx",
    args: ["s2-mcp-server==1.7.4"],
    // pinned: see mcp_client.unpinned
    env: { SEMANTIC_SCHOLAR_API_KEY: "${SEMANTIC_SCHOLAR_API_KEY}" }
  },
  {
    id: "playwright",
    name: "Playwright browser",
    description: "Open and read web pages in a real, headless browser - for pages a plain fetch can't read.",
    command: "npx",
    args: ["-y", "@playwright/mcp@0.0.82", "--headless", "--isolated"],
    env: {}
  },
  {
    id: "apify",
    name: "Apify (web search and scrapers)",
    description: "Search the web and fetch pages (RAG web browser), plus ready-made scrapers. Needs APIFY_TOKEN.",
    command: "npx",
    args: ["-y", "@apify/actors-mcp-server@0.16.0"],
    env: { APIFY_TOKEN: "${APIFY_TOKEN}" }
  }
];
var Settings = class {
  constructor(api, state, refresh, manageKeys, chooseModel, native = false, runCommand = () => {
  }, fieldId = (base) => base) {
    this.api = api;
    this.state = state;
    this.refresh = refresh;
    this.manageKeys = manageKeys;
    this.chooseModel = chooseModel;
    this.native = native;
    this.runCommand = runCommand;
    this.fieldId = fieldId;
    this.dialog = h("dialog", { class: "lib-dialog settings", "aria-label": "Settings" });
    this.page = "models";
    this.body = h("section", { class: "settings-content" });
    this.libraryName = h("span", { class: "settings-library" });
    this.compact = h("select", { "aria-label": "Settings section" });
    this.links = /* @__PURE__ */ new Map();
    this.drafts = /* @__PURE__ */ new Map();
    this.dirty = false;
    this.draftLibrary = "";
    this.searchResults = h("div", { class: "settings-results", hidden: true });
    this.search = h("input", { type: "search", placeholder: "Find a setting", "aria-label": "Find a setting" });
    this.expandedServices = /* @__PURE__ */ new Set();
    this.healthTimer = 0;
    this.focusService = "";
    this.dialog.addEventListener("close", () => {
      if (!this.dialog.open) this.stopHealth();
    });
    const nav = h("nav", { class: "settings-nav", "aria-label": "Settings sections" });
    for (const [group, pages] of GROUPS) {
      const options = h("optgroup", { label: group });
      nav.append(h("h3", {}, group));
      for (const [id, label] of pages) {
        const link2 = h("button", { type: "button", onclick: () => this.open(id) }, label);
        this.links.set(id, link2);
        nav.append(link2);
        options.append(h("option", { value: id }, label));
      }
      this.compact.append(options);
    }
    this.search.oninput = () => this.findSettings();
    this.body.addEventListener("input", (e) => {
      if ((this.page === "context" || this.page === "topics") && e.target instanceof HTMLElement && e.target.closest("input,textarea,select")) this.dirty = true;
    });
    this.compact.onchange = () => this.open(this.compact.value);
    this.dialog.append(
      h(
        "header",
        { class: "dlg-head" },
        h("strong", {}, "Settings"),
        this.libraryName,
        this.search,
        h("button", { class: "ghost push", onclick: () => this.dialog.close() }, "Close")
      ),
      this.searchResults,
      this.compact,
      h("div", { class: "settings-layout" }, nav, this.body)
    );
  }
  open(page = this.page) {
    this.stopHealth();
    const library = String(this.state().vault_path ?? this.state().vault ?? "");
    if (library !== this.draftLibrary) {
      this.drafts.clear();
      this.dirty = false;
      this.draftLibrary = library;
    }
    if (this.dirty) this.drafts.set(this.page, Array.from(this.body.childNodes));
    this.page = page;
    this.search.value = "";
    this.searchResults.hidden = true;
    const draft = this.drafts.get(page);
    this.dirty = !!draft;
    if (draft) {
      clear(this.body, draft);
      this.updateNav();
    } else this.render();
    if (!this.dialog.open) this.dialog.showModal();
  }
  syncState() {
    const state = this.state(), tiers = state.tiers ?? [];
    const library = state.vault_name || state.vault;
    this.libraryName.textContent = library ? `Library: ${library}` : "Opening library\u2026";
    if (this.page !== "models") return;
    this.body.querySelectorAll(".lib-settings-role").forEach((row, i) => {
      const selected = tiers[i], fallback = tiers[tiers.length - 1];
      const assignment = row.querySelector(".lib-settings-assignment");
      assignment.textContent = selected ? `${selected.model} \xB7 ${PROVIDERS[selected.provider] ?? selected.provider}` : i > tiers.length ? `Choose ${CHAT_ROLES[i - 1][0]} first` + (fallback ? ` \xB7 currently uses ${fallback.model}` : "") : fallback ? `Uses ${fallback.model}` : "No model selected";
      row.querySelector("button").disabled = !library || i > tiers.length;
      const reset = row.querySelector(".lib-clear-role");
      if (reset) reset.hidden = !selected;
    });
  }
  updateNav() {
    for (const [id, link2] of this.links) {
      if (id === this.page) link2.setAttribute("aria-current", "page");
      else link2.removeAttribute("aria-current");
    }
    this.compact.value = this.page;
  }
  stopHealth() {
    window.clearTimeout(this.healthTimer);
    this.healthRequest?.abort();
    this.healthRequest = void 0;
  }
  coreHealth() {
    this.stopHealth();
    const controller = new AbortController();
    this.healthRequest = controller;
    const summary = h("div"), status = h("p", { class: "note", role: "status" }, "Checking Core health\u2026");
    const poll = async () => {
      try {
        const snapshots = await Promise.allSettled([
          this.api.get("/api/meta", controller.signal),
          this.api.get("/api/documents", controller.signal)
        ]);
        if (controller.signal.aborted) return;
        const [meta, documents] = snapshots.map((snapshot) => {
          if (snapshot.status === "rejected") throw snapshot.reason;
          return snapshot.value;
        });
        const health = meta.non_secret_health;
        if (!health || !Array.isArray(documents.leases)) throw new Error("Incomplete health response");
        clear(
          summary,
          h("p", {}, `Writer: ${health.writer} \xB7 Index: ${health.index} \xB7 Watcher: ${health.watcher?.status ?? "unknown"} \xB7 Vault lease: ${health.vault_lease}`),
          h("p", {}, `Active document leases: ${documents.leases.length}`),
          documents.leases.map((lease) => h("div", {}, `${lease.path} \xB7 ${lease.editor} \xB7 ${lease.dirty ? "unsaved edits" : "clean"}`))
        );
        status.textContent = `Last successful check: ${(/* @__PURE__ */ new Date()).toLocaleTimeString()}`;
      } catch (e) {
        if (controller.signal.aborted) return;
        status.textContent = (status.textContent ?? "").split(" \xB7 Refresh failed")[0] + " \xB7 Refresh failed: " + e.message;
      }
      if (!controller.signal.aborted) this.healthTimer = window.setTimeout(poll, 1e4);
    };
    void poll();
    return h("section", {}, h("h3", {}, "Core and active documents"), summary, status);
  }
  controlsPage() {
    const choice = (key, label, options) => h("label", { class: "f" }, label, h(
      "select",
      { onchange: (event) => remember(key, event.target.value) },
      options.map(([value, name]) => h("option", { value, selected: preference(key, options[0][0]) === value }, name))
    ));
    return h(
      "div",
      {},
      choice("job-start", "When an ingestion job starts", [["stay", "Stay on this page"], ["activity", "Open Activity search"]]),
      choice("batch-notice", "When an observed batch finishes", [["quiet", "Keep the result in Staging"], ["on", "Also show an in-app notice"]]),
      shortcutPage(this.native, this.runCommand, this.api, this.state())
    );
  }
  findSettings() {
    const q = this.search.value.trim().toLowerCase();
    const items = [
      ...Array.from(this.links, ([id, link2]) => [id, link2.textContent ?? id]),
      ["models", "Read aloud / text to speech (TTS)", "tts"],
      ["models", "Speech recognition (STT)", "stt"],
      ["models", "Semantic search / embeddings", "embeddings"],
      ["models", "Document reading / OCR", "ocr"],
      ["models", "Clerk / small tasks / reviewer", "role"],
      ["projects", "Folder permissions and editing"],
      ["review", "Who can promote sources?"],
      ["context", "Send shortcut and response length"],
      ["models", "Named research presets", "preset"],
      ["context", "View active context and session lenses", "active"],
      ["connections", "API keys and billing"],
      ...Object.values(COMMANDS).map((name) => ["commands", name])
    ];
    const found = items.filter(([, label]) => label.toLowerCase().includes(q));
    this.searchResults.hidden = !q;
    clear(this.searchResults, found.length ? found.map(([id, label, target]) => h("button", { class: "ghost", onclick: () => {
      const service = target && Object.hasOwnProperty.call(SERVICE_NAMES, target) ? target : "";
      if (service) this.expandedServices.add(service);
      this.open(id);
      if (target === "role") this.body.querySelector('[aria-label="Choose Small tasks / reviewer model"]')?.focus();
      if (id === "commands") Array.from(this.body.querySelectorAll("strong")).find((el) => el.textContent === label)?.closest(".lib-settings-role")?.querySelector("button")?.focus();
      if (service) this.focusService = service;
      if (target === "preset" || target === "active") {
        const detail = Array.from(this.body.querySelectorAll("details")).find((d) => d.querySelector("summary")?.textContent === (target === "preset" ? "Named research presets" : "View active context"));
        if (detail) {
          detail.open = true;
          detail.querySelector("summary")?.focus();
        }
      }
    } }, label)) : h("span", { role: "status" }, "No matching settings."));
  }
  render() {
    this.updateNav();
    const pages = {
      commands: () => this.controlsPage(),
      models: () => this.modelsPage(),
      connections: () => this.connections(),
      mcp: () => this.mcp(),
      context: () => this.context(),
      projects: () => this.projectsPage(),
      profiles: () => this.agentProfiles(),
      review: () => this.library(false),
      health: () => h("div", {}, this.coreHealth(), this.library(true)),
      topics: () => {
        const host = h("div", { class: "topics" });
        void this.paintTopics(host);
        return host;
      },
      methods: () => {
        const profile = h("div"), packs = h("div", { class: "lens-packs" });
        void this.paintProfile(profile);
        void this.paintPacks(packs);
        return h("div", {}, profile, h("h3", {}, "Lens packs"), packs);
      }
    };
    clear(this.body, h("h2", {}, this.links.get(this.page)?.textContent ?? "Settings"), pages[this.page]());
    if (this.page === "context" || this.page === "topics") this.body.append(h("button", { class: "ghost", onclick: () => {
      this.drafts.delete(this.page);
      this.dirty = false;
      this.render();
    } }, "Discard unsaved edits"));
    this.syncState();
    this.body.scrollTop = 0;
  }
  modelsPage() {
    const catalogues = h("div", { class: "model-catalogs" });
    const more = h("details", { class: "settings-more" }, h("summary", {}, "Model catalogues and qualification"));
    more.addEventListener("toggle", () => {
      if (more.open && more.childElementCount === 1) {
        more.append(catalogues, this.releaseLeadSetup());
        void this.paintModelCatalogs(catalogues);
      }
    });
    return h(
      "div",
      {},
      h("p", { class: "settings-intro" }, "Choose the models that perform each kind of work."),
      h(
        "p",
        { class: "settings-scope" },
        "Chat-model changes also update defaults used by libraries without their own choices.",
        h("small", {}, "Service assignments remain specific to this library. Effort changes also update the shared default.")
      ),
      h("h3", {}, "Chat roles"),
      CHAT_ROLES.map(([label, job], i) => {
        return h(
          "div",
          { class: "settings-role" },
          h("div", {}, h("strong", {}, label), h("small", {}, job)),
          h("span", { class: "settings-assignment" }),
          h("button", {
            class: "ghost",
            "aria-label": `Choose ${label} model`,
            onclick: () => {
              this.dialog.close();
              this.chooseModel?.("chat", label, this.state().tiers?.[i], i);
            }
          }, "Choose"),
          h("button", { class: "ghost clear-role", onclick: async (e) => {
            const button = e.currentTarget;
            const tiers = this.state().tiers ?? [];
            const names = CHAT_ROLES.slice(i, tiers.length).map(([name]) => name).join(", ");
            if (!window.confirm("Clear these assignments: " + names + "? " + (i ? "Later roles will use the preceding model." : "No chat model will be selected.") + " Shared defaults will also change.")) return;
            button.disabled = true;
            try {
              await this.api.post("/api/tiers", { tiers: tiers.slice(0, i) });
              await this.refresh();
              this.render();
            } catch (err) {
              button.after(h("span", { role: "alert" }, err.message));
              button.disabled = false;
            }
          } }, "Clear from this role")
        );
      }),
      h("h3", {}, "Supporting services"),
      h("p", { class: "settings-help" }, "Expand a service to choose its model or check its configuration."),
      this.serviceModels(),
      more,
      researchSetups(this.api, this.state, this.refresh)
    );
  }
  // -- page 1 --------------------------------------------------------------
  connections() {
    const keys = this.state().keys ?? [];
    if (this.manageKeys) {
      return h(
        "div",
        {},
        h("p", {}, "Keys are kept in Obsidian's secret storage, never in the vault or the plugin's data."),
        keys.filter((k) => k.needed).map((k) => h(
          "div",
          { class: "srv" },
          h("span", { class: `dot ${k.saved ? "" : "nokey"}` }),
          `${PROVIDERS[k.provider] ?? k.provider}: `,
          k.saved ? `\u2022\u2022\u2022\u2022 ${k.last4}` : "no key"
        )),
        h("div", { class: "row2" }, h(
          "button",
          { class: "primary", onclick: () => {
            this.dialog.close();
            this.manageKeys?.();
          } },
          "Choose keys in the plugin's settings"
        )),
        h("p", { class: "note" }, "After changing a key, the plugin restarts the core so it takes effect."),
        this.hostRegistry()
      );
    }
    const LABELS = {
      ...PROVIDERS,
      tavily: "Tavily (web search)",
      brave: "Brave Search (web search)",
      github: "GitHub (repository intake)"
    };
    const select = h(
      "select",
      { id: this.fieldId("lib-provider") },
      Object.entries(LABELS).map(([id, label]) => h("option", { value: id }, label))
    );
    const input = h("input", { type: "password", id: this.fieldId("lib-key"), autocomplete: "off", placeholder: "Paste a key" });
    const status = h("span", { class: "note inline", role: "status" });
    const confirmBox = h("div");
    const save = h("button", { class: "primary" }, "Save key");
    const remove = h("button", { class: "ghost" }, "Remove key");
    const usageBox = h("div", { class: "usage" });
    const checkUsage = h("button", { class: "ghost", onclick: async () => {
      clear(usageBox, h("p", { class: "dim" }, "Checking\u2026"));
      let out;
      try {
        out = await this.api.get(`/api/usage?provider=${select.value}`);
      } catch (e) {
        out = { ok: false, error: e.message };
      }
      const link2 = out.dashboard ? h(
        "a",
        { href: out.dashboard, target: "_blank", rel: "noreferrer noopener" },
        out.ok && out.balance !== void 0 ? "Full billing details \u2197" : "View on the provider's site \u2197"
      ) : null;
      if (out.ok && out.balance !== void 0) {
        clear(
          usageBox,
          h(
            "p",
            {},
            `Balance: $${out.balance}${out.currency ? ` ${out.currency}` : ""}`,
            out.suspended ? h("strong", {}, " \xB7 account suspended") : null,
            out.billing_type ? h("span", { class: "dim" }, ` \xB7 ${out.billing_type}`) : null
          ),
          h("p", { class: "note" }, "Unofficial: read from an undocumented endpoint, not DeepInfra's published API. ", link2)
        );
      } else {
        clear(usageBox, h("p", { class: "dim" }, out.error || "Usage isn't available here for this provider."), link2);
      }
    } }, "Check usage");
    const show = () => {
      const k = keys.find((x) => x.provider === select.value) ?? {};
      clear(confirmBox);
      clear(usageBox);
      if (!k.needed) {
        input.disabled = true;
        save.hidden = true;
        remove.hidden = true;
        checkUsage.hidden = true;
        status.textContent = "No key needed. The local server must be running.";
        return;
      }
      input.disabled = false;
      save.hidden = false;
      checkUsage.hidden = ["tavily", "brave", "github"].includes(select.value);
      remove.hidden = !k.saved;
      save.textContent = k.saved ? "Overwrite key" : "Save key";
      input.placeholder = k.saved ? `\u2022\u2022\u2022\u2022 ${k.last4} \xB7 ${k.source === "host" ? "from Obsidian" : "saved"}` : "Paste a key";
      status.textContent = "";
    };
    const submit = async (overwrite) => {
      status.textContent = "Saving and testing\u2026";
      try {
        const out = await this.api.post("/api/keys", { provider: select.value, key: input.value, overwrite });
        input.value = "";
        status.textContent = out.check?.ok ? out.check.status : `Saved, but the provider said: ${out.check?.error ?? "no answer"}`;
        status.className = cls(`note inline ${out.check?.ok ? "ok" : "err"}`);
        await this.refresh();
        keys.splice(0, keys.length, ...this.state().keys ?? []);
        const msg = status.textContent;
        show();
        status.textContent = msg;
      } catch (e) {
        if (e instanceof ApiError && e.status === 409 && e.body.confirm) {
          clear(confirmBox, h(
            "div",
            { class: "confirm" },
            String(e.body.confirm),
            h(
              "div",
              { class: "row2" },
              h("button", { class: "ghost", onclick: () => clear(confirmBox) }, "Cancel"),
              h("button", { class: "primary", onclick: () => submit(true) }, "Overwrite")
            )
          ));
          status.textContent = "";
        } else {
          status.textContent = e.message;
          status.className = cls("note inline err");
        }
      }
    };
    save.onclick = () => submit(false);
    remove.onclick = () => clear(confirmBox, h(
      "div",
      { class: "confirm" },
      `Remove the saved ${LABELS[select.value]} key? It can't be recovered from here.`,
      h(
        "div",
        { class: "row2" },
        h("button", { class: "ghost", onclick: () => clear(confirmBox) }, "Cancel"),
        h("button", { class: "primary", onclick: async () => {
          await this.api.post("/api/keys/remove", { provider: select.value, confirm: true });
          await this.refresh();
          keys.splice(0, keys.length, ...this.state().keys ?? []);
          show();
        } }, "Remove")
      )
    ));
    select.onchange = show;
    input.onkeydown = (e) => {
      if (e.key === "Enter") submit(false);
    };
    const keyMigration = h("div");
    if (this.state().key_backend === "config file" || this.state().key_migration_pending) {
      const migrationStatus = h("span", { class: "note inline", role: "status" });
      const migrate = h("button", { class: "ghost", onclick: () => clear(
        keyMigration,
        h(
          "div",
          { class: "confirm" },
          "Move the saved fallback-file credentials into this computer's operating-system keychain? No key value is displayed or sent back to this page.",
          h(
            "div",
            { class: "row2" },
            h("button", { class: "ghost", onclick: () => {
              this.render();
            } }, "Cancel"),
            h("button", { class: "primary", onclick: async () => {
              migrationStatus.textContent = "Migrating\u2026";
              try {
                const out = await this.api.post("/api/keys/migrate", { confirm: true });
                await this.refresh();
                if (out.available === false) {
                  migrationStatus.textContent = String(out.detail ?? "No operating-system keychain is available yet.");
                  migrationStatus.className = cls("note inline err");
                } else if (out.fallback_retained) {
                  migrationStatus.textContent = String(out.detail ?? "Migrated, but the old fallback file remains.");
                  migrationStatus.className = cls("note inline err");
                } else {
                  migrationStatus.textContent = out.already_secure ? "Keys are already in the operating-system keychain." : "Saved keys moved to the operating-system keychain.";
                  migrationStatus.className = cls("note inline ok");
                }
              } catch (e) {
                migrationStatus.textContent = e.message;
                migrationStatus.className = cls("note inline err");
              }
            } }, "Migrate")
          )
        )
      ) }, "Move fallback keys to keychain");
      clear(
        keyMigration,
        h(
          "p",
          { class: "note" },
          this.state().key_migration_pending ? "A protected fallback key file from an earlier installation still needs explicit migration into this computer's keychain." : "This installation is using the protected file fallback. Once the operating-system keychain is available, move saved keys explicitly."
        ),
        h("div", { class: "row2" }, migrate, migrationStatus)
      );
    }
    const page = h(
      "div",
      {},
      h("label", { class: "f", for: this.fieldId("lib-provider") }, "Provider"),
      select,
      h("label", { class: "f", for: this.fieldId("lib-key") }, "Connect API key"),
      input,
      h("div", { class: "row2" }, save, remove, status),
      confirmBox,
      h(
        "p",
        { class: "note" },
        `Keys are kept by the core (${this.state().key_backend ?? "securely"}), never in the vault. `,
        "They never come back to this page: only whether one is saved, and its last four characters."
      ),
      keyMigration,
      h("label", { class: "f" }, "Usage & billing"),
      h("div", { class: "row2" }, checkUsage),
      usageBox,
      this.hostRegistry()
    );
    show();
    return page;
  }
  /** The chosen profile narrows an agent; it cannot expand a person's tools
   * or silently change its route.  Keeping the selector beside hosts makes
   * the connection between a model choice and its policy visible. */
  agentProfiles() {
    const root = h("section", { class: "agent-profiles" }, h("p", { class: "dim" }, "Loading agent profiles\u2026"));
    const reload = async () => {
      try {
        const out = await this.api.get("/api/profiles");
        const profiles = out.profiles ?? [];
        const selected = String(out.selected ?? this.state().agent_profile ?? "lead");
        const status = h("span", { class: "note inline", role: "status" });
        const select = h("select", { "aria-label": "Agent profile" }, profiles.map((profile) => h(
          "option",
          { value: String(profile.id), selected: String(profile.id) === selected },
          `${profile.id} r${profile.revision ?? 1} \xB7 ${profile.role} \xB7 ${profile.permission_ceiling}`
        )));
        select.onchange = async () => {
          status.textContent = "Applying profile\u2026";
          try {
            await this.api.post("/api/agent-profile", { id: select.value });
            await this.refresh();
            status.textContent = "Applied to subsequent agent turns.";
            status.className = cls("note inline ok");
          } catch (e) {
            select.value = selected;
            status.textContent = e.message;
            status.className = cls("note inline err");
          }
        };
        const active = out.active ?? {};
        const editor = h("div", { class: "profile-editor" });
        const split = (value) => value.split(",").map((part) => part.trim()).filter(Boolean);
        const showEditor = (base, creating = false) => {
          const route = base.route_policy ?? {};
          const rates = route.rate_card ?? {};
          const id = h("input", {
            type: "text",
            value: creating ? "" : String(base.id ?? ""),
            placeholder: "profile id",
            "aria-label": "Profile id"
          });
          const role = h("input", {
            type: "text",
            value: String(base.role ?? "lead"),
            "aria-label": "Profile role"
          });
          const routeSlots = ["lead", "scribe", "clerk", "research_helper"];
          const bindingRole = h(
            "select",
            { "aria-label": "Model route slot" },
            routeSlots.map((value) => h(
              "option",
              {
                value,
                selected: value === String(route.binding_role ?? (routeSlots.includes(base.role) ? base.role : "lead"))
              },
              value.replace(/_/g, " ")
            ))
          );
          const ceiling = h(
            "select",
            { "aria-label": "Permission ceiling" },
            ["consult", "contribute", "curate"].map((value) => h("option", {
              value,
              selected: value === String(base.permission_ceiling ?? "contribute")
            }, value))
          );
          const qualification = h(
            "select",
            { "aria-label": "Required qualification" },
            ["experimental", "screened", "verified_local", "verified_release"].map((value) => h("option", {
              value,
              selected: value === String(base.required_qualification ?? "screened")
            }, value))
          );
          const bundles = h("input", {
            type: "text",
            value: (base.allowed_bundles ?? []).join(", "),
            placeholder: "session, research",
            "aria-label": "Allowed tool bundles"
          });
          const hosts = h("input", {
            type: "text",
            value: (route.host_ids ?? []).join(", "),
            placeholder: "optional host ids",
            "aria-label": "Allowed host ids"
          });
          const providers = h("input", {
            type: "text",
            value: (route.providers ?? []).join(", "),
            placeholder: "optional legacy providers",
            "aria-label": "Allowed legacy providers"
          });
          const models = h("input", {
            type: "text",
            value: (route.model_ids ?? []).join(", "),
            placeholder: "optional model ids",
            "aria-label": "Allowed model ids"
          });
          const validation = h("input", {
            type: "text",
            value: (base.validation_rules ?? []).join(", "),
            placeholder: "grounded, cite evidence",
            "aria-label": "Validation focus rules"
          });
          const token2 = h("input", {
            type: "number",
            min: 0,
            value: String(base.token_budget ?? 0),
            "aria-label": "Token budget per agent turn"
          });
          const output = h("input", {
            type: "number",
            min: 1,
            value: String(base.output_budget ?? 4096),
            "aria-label": "Maximum output tokens"
          });
          const cost = h("input", {
            type: "number",
            min: 0,
            step: "0.01",
            value: String(base.cost_budget_usd ?? 0),
            "aria-label": "Cost budget USD per agent turn"
          });
          const seconds = h("input", {
            type: "number",
            min: 0,
            value: String(base.time_budget_seconds ?? 0),
            "aria-label": "Time budget seconds"
          });
          const concurrent = h("input", {
            type: "number",
            min: 1,
            max: 32,
            value: String(base.concurrency_limit ?? 1),
            "aria-label": "Concurrent runs"
          });
          const inputRate = h("input", {
            type: "number",
            min: 0,
            step: "0.001",
            value: String(rates.input_per_1m ?? rates.price_input_per_1m ?? ""),
            placeholder: "input $/1M",
            "aria-label": "Input USD per million tokens"
          });
          const outputRate = h("input", {
            type: "number",
            min: 0,
            step: "0.001",
            value: String(rates.output_per_1m ?? rates.price_output_per_1m ?? ""),
            placeholder: "output $/1M",
            "aria-label": "Output USD per million tokens"
          });
          const retry = h("select", { "aria-label": "Retry policy" }, ["bounded", "none"].map((value) => h("option", { value, selected: value === String(base.retry_policy ?? "bounded") }, value)));
          const failover = h("select", { "aria-label": "Failover policy" }, ["ask", "never"].map((value) => h("option", { value, selected: value === String(base.failover_policy ?? "ask") }, value)));
          const editorStatus = h("span", { class: "note inline", role: "status" });
          const save = async () => {
            const rateCard = {};
            if (inputRate.value.trim() || outputRate.value.trim()) {
              rateCard.input_per_1m = Number(inputRate.value || 0);
              rateCard.output_per_1m = Number(outputRate.value || 0);
            }
            const profile = {
              ...base,
              id: id.value.trim(),
              role: role.value.trim(),
              permission_ceiling: ceiling.value,
              required_qualification: qualification.value,
              allowed_bundles: split(bundles.value),
              token_budget: Number(token2.value || 0),
              output_budget: Number(output.value || 4096),
              cost_budget_usd: Number(cost.value || 0),
              time_budget_seconds: Number(seconds.value || 0),
              concurrency_limit: Number(concurrent.value || 1),
              retry_policy: retry.value,
              failover_policy: failover.value,
              validation_rules: split(validation.value),
              route_policy: {
                ...route,
                host_ids: split(hosts.value),
                model_ids: split(models.value),
                binding_role: bindingRole.value,
                providers: split(providers.value),
                ...Object.keys(rateCard).length ? { rate_card: rateCard } : {}
              }
            };
            editorStatus.textContent = "Saving profile\u2026";
            try {
              await this.api.post("/api/profiles", { profile });
              editorStatus.textContent = "Saved as a new profile revision.";
              editorStatus.className = cls("note inline ok");
              await reload();
            } catch (e) {
              editorStatus.textContent = e.message;
              editorStatus.className = cls("note inline err");
            }
          };
          clear(
            editor,
            h(
              "div",
              { class: "confirm" },
              h("strong", {}, creating ? "New agent profile" : `Edit ${base.id}`),
              h("div", { class: "row2 tight" }, id, role, ceiling, qualification),
              h("label", { class: "f" }, "Use the model assigned to this route slot"),
              bindingRole,
              h("label", { class: "f" }, "Tool bundles (comma-separated)"),
              bundles,
              h("label", { class: "f" }, "Route allow-lists (blank means unrestricted)"),
              h("div", { class: "row2 tight" }, hosts, providers, models),
              h("label", { class: "f" }, "Validation focus (comma-separated, guidance only; platform gates still apply)"),
              validation,
              h("label", { class: "f" }, "Turn budgets"),
              h("div", { class: "row2 tight" }, token2, output, cost, seconds, concurrent),
              h("p", { class: "note" }, "A non-zero cost cap needs both rate fields; otherwise Core refuses before a paid provider call."),
              h("div", { class: "row2 tight" }, inputRate, outputRate, retry, failover),
              h(
                "div",
                { class: "row2" },
                h("button", { class: "ghost", onclick: () => clear(editor) }, "Cancel"),
                h("button", { class: "primary", onclick: () => void save() }, "Save profile"),
                editorStatus
              )
            )
          );
        };
        const chosen = profiles.find((profile) => String(profile.id) === selected) ?? profiles[0] ?? {};
        const history = h("div", { class: "profile-history" });
        const showHistory = async () => {
          try {
            const out2 = await this.api.get(`/api/profiles/history?id=${encodeURIComponent(String(chosen.id ?? ""))}`);
            const rows = out2.history ?? [];
            clear(history, rows.length ? h(
              "div",
              { class: "confirm" },
              h("strong", {}, "Saved profile revisions"),
              rows.slice(0, 12).map((row) => h(
                "p",
                { class: "note" },
                `r${row.revision ?? row.profile?.revision ?? "?"} \xB7 ${String(row.at ?? "").replace("T", " ").slice(0, 19)} \xB7 ${row.profile?.role ?? ""}, ${row.profile?.permission_ceiling ?? ""}, output ${row.profile?.output_budget ?? ""}`
              )),
              h("button", { class: "ghost", onclick: () => clear(history) }, "Hide history")
            ) : h("p", { class: "note" }, "No vault-specific revisions yet. Editing a shipped default creates revision 2."));
          } catch (e) {
            clear(history, h("p", { class: "error" }, e.message));
          }
        };
        clear(
          root,
          h("label", { class: "f" }, "Agent profile"),
          h(
            "div",
            { class: "row2 tight" },
            select,
            h("button", { class: "ghost", onclick: () => showEditor(chosen) }, "Edit\u2026"),
            h("button", { class: "ghost", onclick: () => showEditor({
              id: "",
              role: "research_helper",
              permission_ceiling: "consult",
              required_qualification: "screened",
              allowed_bundles: ["read"],
              route_policy: {},
              output_budget: 1024,
              retry_policy: "bounded",
              failover_policy: "ask",
              concurrency_limit: 1
            }, true) }, "New\u2026"),
            h("button", { class: "ghost", onclick: () => void showHistory() }, "History\u2026"),
            status
          ),
          h("p", { class: "note" }, "Profiles set tool bundles, permission ceilings, route allow-lists, budgets and concurrency. They narrow the selected agent only; they never grant it a new host or bypass a checkpoint."),
          Object.keys(active).length ? h("p", { class: "note" }, `Active profile runs: ${Object.entries(active).map(([id, n]) => `${id} (${n})`).join(", ")}.`) : null,
          editor,
          history
        );
      } catch (e) {
        clear(root, h("p", { class: "error" }, e.message));
      }
    };
    void reload();
    return root;
  }
  /** Research Pipeline §6.1: project access - off by default, folders a person chooses, each
   *  with its librarian-app/ sidecar. The core refuses project tools while it is off; this
   *  page is where a person turns it on, never the model. */
  projectsPage() {
    const host = h("div", {}, h("p", { class: "dim" }, "Loading\u2026"));
    const status = h("span", { class: "note inline", role: "status" });
    const paint = (data) => {
      const toggle = h("input", {
        type: "checkbox",
        id: this.fieldId("lib-projects-on"),
        checked: !!data.enabled,
        onchange: async (e) => {
          await changePermission(e, "/api/projects/enable", { enabled: e.target.checked }, !!data.enabled);
        }
      });
      const changePermission = async (event, url, body, previous, done = "") => {
        const box = event.currentTarget;
        box.disabled = true;
        try {
          paint(await this.api.post(url, body));
          status.textContent = done;
        } catch (err) {
          box.checked = previous;
          try {
            paint(await this.api.get("/api/projects"));
            status.textContent = "Change failed. Showing current permissions. " + err.message;
          } catch {
            status.textContent = "Could not verify permissions. Showing last confirmed value.";
          }
        } finally {
          box.disabled = false;
        }
      };
      const path2 = h("input", {
        type: "text",
        class: "f",
        id: this.fieldId("lib-project-path"),
        placeholder: "Full path to the project folder, e.g. D:\\code\\my-app"
      });
      const project = h("input", {
        type: "text",
        "aria-label": "Project note",
        placeholder: "Its Project note's name (optional)"
      });
      const act = (url, body, done = "") => async () => {
        status.textContent = "";
        try {
          const out = await this.api.post(url, body);
          paint(out);
          if (done) status.textContent = done;
        } catch (err) {
          status.textContent = err.message;
        }
      };
      clear(
        host,
        h("label", { class: "opt" }, toggle, h(
          "span",
          {},
          h("strong", {}, "Enable project access"),
          h("small", {}, "Off by default. While off, no project folder is read and the librarian's project tools are unavailable - checked by the core, not only this page.")
        )),
        h("label", { class: "f" }, "Project folders"),
        (data.roots ?? []).length ? data.roots.map((r) => h(
          "div",
          { class: "srv project-root" },
          h("span", { class: `dot ${r.exists ? "" : "off"}` }),
          h(
            "span",
            {},
            h("code", {}, r.path),
            h("span", { class: "dim" }, [
              r.project ? ` \xB7 ${r.project}` : " \xB7 no Project note linked",
              ` \xB7 librarian-app/ ${r.scaffold?.state ?? "?"}`,
              r.last_scan ? ` \xB7 scanned ${String(r.last_scan.at).slice(0, 10)} at ${String(r.last_scan.revision).slice(0, 10)} (${r.last_scan.components} components)` : " \xB7 not scanned",
              r.exists ? "" : " \xB7 moved or gone: add it again"
            ].join(""))
          ),
          data.enabled && r.exists ? h("button", { class: "ghost", onclick: act("/api/projects/scan", { id: r.id }, "Scanned.") }, "Scan") : null,
          h(
            "label",
            { class: "inline project-writes", title: "Separate from reading: the librarian may then propose one change at a time (a snippet replaced or a new file), shown as a diff; you approve each one, and each is logged with a backup in librarian-app/logs/." },
            h("input", {
              type: "checkbox",
              checked: !!r.writes,
              "aria-label": `Allow edits in ${r.path}`,
              onchange: (e) => changePermission(
                e,
                "/api/projects/writes",
                { id: r.id, allowed: e.target.checked },
                !!r.writes,
                e.target.checked ? "Edits allowed: each one is still asked." : "Edits withdrawn."
              )
            }),
            " Allow edits"
          ),
          h("button", { class: "ghost", onclick: act("/api/projects/remove", { id: r.id }) }, "Remove this project")
        )) : h("p", { class: "dim" }, "No project folders yet."),
        h("label", { class: "f", for: this.fieldId("lib-project-path") }, "Add a project folder"),
        path2,
        h(
          "div",
          { class: "row2 tight" },
          project,
          h("button", { class: "primary", onclick: () => act(
            "/api/projects/add",
            { path: path2.value.trim(), project: project.value.trim() },
            "Added: its librarian-app/ is ready."
          )() }, "Add"),
          status
        ),
        h("p", { class: "note" }, "Adding a folder creates librarian-app/ inside it (manifest, README, data, information, sessions, applications, index, logs), never overwriting a file already there, and never touching the project's own .gitignore. The librarian reads the project. It changes a project file only in a folder where you ticked Allow edits, and asks you before every change, whatever the permission mode; each change is logged with a backup in librarian-app/logs/ so it can be undone.")
      );
    };
    this.api.get("/api/projects").then(paint).catch((e) => clear(host, h("p", { class: "error" }, e.message)));
    return host;
  }
  /** Slot 6 (R17, SM-8): what embedding the library takes before anything is sent, a
   *  person's own start, the lexical-vs-hybrid measurement, and the intents a person turns
   *  vectors on for after reading it. */
  embeddingsBlock(s, reload) {
    const status = h("span", { class: "note inline", role: "status" });
    const confirm2 = h("div");
    const est = s.estimate ?? {};
    const local = h("button", {
      class: "ghost",
      title: "A small static model on this machine: no key, no cost",
      onclick: async () => {
        await this.api.post("/api/services", { slot: "embeddings", provider: "model2vec", model: "minishlab/potion-base-8M" });
        reload();
      }
    }, "Use a local model");
    const embedAll = h("button", { class: "primary", onclick: () => clear(confirm2, h(
      "div",
      { class: "confirm" },
      `This embeds ${est.chunks} text chunks (about ${est.tokens_est} tokens) with ${s.spec}` + (s.hosted ? est.cost_est_usd !== void 0 ? `, about $${est.cost_est_usd}.` : ". Its price is unknown here: see the provider's page." : ", on this machine."),
      h(
        "div",
        { class: "row2" },
        h("button", { class: "ghost", onclick: () => clear(confirm2) }, "Cancel"),
        h("button", { class: "primary", onclick: async () => {
          clear(confirm2);
          status.textContent = "Embedding\u2026";
          try {
            const out = await this.api.tool("embed_index", {});
            if (out.error) throw new Error(String(out.detail ?? out.error));
            reload();
          } catch (e) {
            status.textContent = e.message;
          }
        } }, "Embed")
      )
    )) }, "Embed the library");
    const measure = h("button", { class: "ghost", onclick: async () => {
      status.textContent = "Measuring lexical against hybrid on this library's questions\u2026";
      try {
        const out = await this.api.tool("evaluate", { compare_vectors: true });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        reload();
      } catch (e) {
        status.textContent = e.message;
      }
    } }, "Measure (lexical vs hybrid)");
    const using = new Set(s.vector_intents ?? []);
    const rows = Object.entries(s.comparison?.by_intent ?? {});
    const table2 = rows.length ? h(
      "table",
      { class: "compare" },
      h("tr", {}, ["intent", "questions", "lexical hit", "hybrid hit", "\u0394", "use vectors"].map((t) => h("th", {}, t))),
      rows.map(([intent, r]) => h(
        "tr",
        {},
        h("td", {}, intent),
        h("td", {}, String(r.n)),
        h("td", {}, String(r.lexical_hit)),
        h("td", {}, String(r.hybrid_hit)),
        h("td", { class: r.delta_hit > 0 ? "ok" : r.delta_hit < 0 ? "err" : "" }, String(r.delta_hit)),
        h("td", {}, h("input", {
          type: "checkbox",
          checked: using.has(intent),
          "aria-label": `use vectors for ${intent}`,
          onchange: (e) => {
            if (e.target.checked) using.add(intent);
            else using.delete(intent);
          }
        }))
      ))
    ) : null;
    const save = rows.length ? h("button", { class: "ghost", onclick: async () => {
      await this.api.post("/api/services/vector_intents", { intents: [...using] });
      reload();
    } }, "Save intents") : null;
    return h(
      "div",
      { class: "embeddings" },
      s.model ? h("p", { class: "dim" }, `${s.embedded ?? 0} of ${s.chunks ?? 0} text chunks embedded` + (s.vector_intents?.length ? ` \xB7 vectors used for: ${s.vector_intents.join(", ")}` : " \xB7 vectors used for no intent yet")) : null,
      s.representation_stale ? h("p", { class: "note locked" }, "Embedding representation changed; existing vectors are not used. Choose Embed all to build the reviewed representation.") : null,
      h("div", { class: "row2 tight" }, local, s.model && est.chunks ? embedAll : null, s.model ? measure : null, status),
      confirm2,
      table2,
      save,
      s.comparison ? h("p", { class: "note" }, `Measured ${String(s.comparison.at ?? "").slice(0, 10)} on ${s.comparison.questions} questions; vectors joined ${s.comparison.vectors_contributed} answers. Turn them on only where they help.`) : null
    );
  }
  /** Requirements Addendum R17: service models, slots 4-7 - each one kind of job with its
   *  own request format, chosen with the same tile as the chat models and kept with this
   *  library. Test makes one small real call. */
  serviceModels() {
    const host = h("div", { class: "services" }, h("p", { class: "dim" }, "Loading\u2026"));
    void (async () => {
      let out;
      try {
        out = await this.api.get("/api/services");
      } catch (e) {
        clear(host, h("p", { class: "error" }, e.message));
        return;
      }
      clear(
        host,
        (out.slots ?? []).sort((a, b) => Object.keys(SERVICE_NAMES).indexOf(a.slot) - Object.keys(SERVICE_NAMES).indexOf(b.slot)).map((s) => {
          const status = h("span", { class: "note inline", role: "status" });
          const current = s.model ? `${s.model} \xB7 ${PROVIDERS[s.provider] ?? s.provider}${s.default ? " (default)" : ""}` : s.built ? "none chosen" : "planned";
          const contract = s.adapter && typeof s.adapter === "object" ? s.adapter : {};
          const contractLabel = !s.model ? "" : contract.adapter?.id ? ` \xB7 ${String(contract.adapter.id).replace(/_/g, " ")} \xB7 ${contract.status ?? "unreviewed"}` : " \xB7 no reviewed service contract";
          const clearService = async () => {
            try {
              await this.api.post("/api/services", { slot: s.slot, provider: "", model: "" });
              this.render();
            } catch (err) {
              status.textContent = err.message;
            }
          };
          const test = async (event) => {
            const button = event.currentTarget;
            if (button.disabled) return;
            button.disabled = true;
            status.className = cls("note inline");
            status.textContent = "Testing: one small call\u2026";
            try {
              const t = await this.api.post("/api/services/test", { slot: s.slot });
              status.textContent = t.summary ?? (t.ok ? `Works: it read \u201C${t.read}\u201D.` : `Not working: ${t.error ?? `it read \u201C${t.read}\u201D`}`);
              if (t.ok && t.audio) void new Audio(t.audio).play().catch(() => void 0);
              status.className = cls(`note inline ${t.ok ? "ok" : "err"}`);
            } catch (e) {
              status.textContent = e.message;
            } finally {
              button.disabled = false;
            }
          };
          return h(
            "details",
            {
              class: `settings-service slot-${s.slot}`,
              open: this.expandedServices.has(s.slot),
              ontoggle: (e) => {
                const row = e.currentTarget;
                if (row.isConnected) {
                  if (row.open) this.expandedServices.add(s.slot);
                  else this.expandedServices.delete(s.slot);
                }
              },
              title: s.built && s.model ? "Right-click to empty this slot" : "",
              oncontextmenu: async (e) => {
                if (!s.built || !s.model) return;
                e.preventDefault();
                try {
                  await this.api.post("/api/services", { slot: s.slot, provider: "", model: "" });
                  this.render();
                } catch (err) {
                  status.textContent = err.message;
                }
              }
            },
            h("summary", {}, h("strong", {}, SERVICE_NAMES[s.slot] ?? s.label), h("small", {}, s.job)),
            h(
              "div",
              { class: "settings-service-body" },
              h(
                "span",
                {},
                h("strong", {}, s.label),
                ` \xB7 ${current}`,
                h("span", { class: "dim" }, ` \xB7 ${s.job}`),
                contractLabel ? h("span", { class: "dim" }, contractLabel) : null,
                s.route_status === "unavailable" ? h("span", { class: "note err" }, ` \xB7 ${s.route_error ?? "route unavailable"}`) : null,
                s.cap_usd !== void 0 ? h("span", { class: "dim" }, ` \xB7 spent or held $${Number(s.spent_usd ?? 0).toFixed(2)} of its $${Number(s.cap_usd).toFixed(2)} cap`) : null
              ),
              s.built && this.chooseModel ? h("button", { class: "ghost", onclick: () => {
                this.dialog.close();
                this.chooseModel(s.slot, s.label, { provider: s.provider, model: s.model });
              } }, "Choose\u2026") : null,
              s.built && s.model ? h("button", { class: "ghost", onclick: test }, "Test model (one call)") : null,
              s.built && s.model ? h("button", { class: "ghost", onclick: clearService }, "Clear service model") : null,
              status,
              s.slot === "embeddings" ? this.embeddingsBlock(s, () => this.render()) : null
            )
          );
        }),
        h("p", { class: "note" }, "Each does one kind of job with its own request format, and is kept with this library. An empty slot is never filled by a chat model.")
      );
      if (this.focusService && host.isConnected) {
        host.querySelector(".lib-slot-" + this.focusService + " summary")?.focus();
        this.focusService = "";
      }
    })();
    return host;
  }
  /** Personal endpoints are configuration, not vault data.  This deliberately
   * keeps endpoint/key binding, discovery, health probes and local limits in
   * the same visible place rather than making a model infer policy from a URL. */
  hostRegistry() {
    const root = h("section", { class: "host-registry" }, h("p", { class: "dim" }, "Loading personal hosts\u2026"));
    const reload = async () => {
      try {
        const data = await this.api.get("/api/hosts");
        const hosts = data.hosts ?? [];
        clear(
          root,
          h("label", { class: "f" }, "Personal model hosts"),
          h("p", { class: "note" }, "Hosts contain endpoints and rate limits, never credentials. A custom endpoint is OpenAI-compatible in V2; test it before assigning it to an agent profile."),
          hosts.map((row) => h("details", { class: "host-details" }, h("summary", {}, row.display_name || row.id, " \xB7 ", row.enabled ? "enabled" : "disabled"), this.hostCard(row, reload))),
          this.newHostCard(reload)
        );
      } catch (e) {
        clear(root, h("p", { class: "error" }, e.message));
      }
    };
    void reload();
    return root;
  }
  hostCard(row, reload) {
    const title = h("strong", {}, String(row.display_name ?? row.id));
    const status = h("span", { class: "note inline", role: "status" });
    const detail = row.health?.detail ? ` \xB7 ${row.health.detail}` : "";
    const health = h(
      "span",
      { class: `note inline ${row.health?.status === "ready" ? "ok" : row.health?.status === "error" ? "err" : ""}` },
      row.health?.status ? `${row.health.status}${detail}` : "not tested"
    );
    const model = h("input", { type: "text", placeholder: "Model id for test or lead selection", "aria-label": `Model on ${row.display_name ?? row.id}` });
    const probeRole = String(this.state().agent_profile_role || this.state().agent_profile || "lead");
    const discovered = h("div", { class: "row2 tight" });
    const enabled = h("input", { type: "checkbox", checked: !!row.enabled, "aria-label": `Enable ${row.display_name ?? row.id}` });
    const name = h("input", { type: "text", value: String(row.display_name ?? ""), "aria-label": "Host display name" });
    const protocol = h(
      "select",
      { "aria-label": "Host protocol", disabled: !!row.seeded },
      h("option", { value: "openai", selected: row.protocol === "openai" }, "OpenAI-compatible"),
      h("option", { value: "anthropic", selected: row.protocol === "anthropic" }, "Anthropic")
    );
    const base = h("input", { type: "text", value: String(row.base_url ?? ""), "aria-label": "Base URL", disabled: !!row.seeded });
    const authRef = h("input", { type: "text", value: String(row.auth_ref ?? ""), "aria-label": "Credential reference", disabled: !!row.seeded });
    const timeout = h("input", { type: "number", value: String(row.timeout ?? 120), min: 1, max: 3600, "aria-label": "Timeout seconds" });
    const concurrency = h("input", { type: "number", value: String(row.concurrency_limit ?? 1), min: 1, max: 32, "aria-label": "Concurrent calls" });
    const rate = h("input", { type: "number", value: String(row.rate_limit ?? 0), min: 0, "aria-label": "Calls per minute" });
    const key = h("input", {
      type: "password",
      autocomplete: "off",
      placeholder: row.needs_key ? "Paste key for this host" : "No key configured",
      disabled: !row.needs_key,
      "aria-label": `Key for ${row.display_name ?? row.id}`
    });
    const confirm2 = h("div");
    const save = async () => {
      status.textContent = "Saving host\u2026";
      try {
        await this.api.post("/api/hosts", { host: {
          id: row.id,
          display_name: name.value.trim(),
          protocol: protocol.value,
          base_url: base.value.trim(),
          auth_ref: authRef.value.trim(),
          enabled: enabled.checked,
          timeout: Number(timeout.value || 120),
          concurrency_limit: Number(concurrency.value || 1),
          rate_limit: Number(rate.value || 0)
        } });
        status.textContent = "Saved.";
        await reload();
      } catch (e) {
        status.textContent = e.message;
        status.className = cls("note inline err");
      }
    };
    const setKey = async (overwrite = false) => {
      try {
        const out = await this.api.post("/api/hosts/key", { host_id: row.id, key: key.value, overwrite });
        key.value = "";
        status.textContent = out.saved ? "Key saved." : "Key status updated.";
        clear(confirm2);
      } catch (e) {
        const body = e.body ?? {};
        if (body.confirm) {
          clear(confirm2, h("div", { class: "confirm" }, String(body.confirm), h(
            "div",
            { class: "row2" },
            h("button", { class: "ghost", onclick: () => clear(confirm2) }, "Cancel"),
            h("button", { class: "primary", onclick: () => void setKey(true) }, "Replace key")
          )));
        } else status.textContent = e.message;
      }
    };
    const discover2 = async () => {
      status.textContent = "Discovering models\u2026";
      try {
        const out = await this.api.get(`/api/models?provider=${encodeURIComponent(String(row.id))}`);
        const models = out.models ?? [];
        clear(discovered, models.length ? models.slice(0, 40).map((entry) => h("button", { class: "ghost", onclick: () => {
          model.value = String(entry.id);
        } }, String(entry.id))) : h("span", { class: "note inline" }, out.error ?? "No models returned."));
        status.textContent = models.length ? `${models.length} models discovered.` : "No models returned.";
      } catch (e) {
        status.textContent = e.message;
        status.className = cls("note inline err");
      }
    };
    const test = async () => {
      status.textContent = "Testing host\u2026";
      try {
        const out = await this.api.post("/api/hosts/test", { host_id: row.id, model: model.value.trim() });
        const check = out.check ?? {};
        const category = String(check.failure_category ?? "");
        status.textContent = check.ok ? "Connection and model listing work." : category === "local_environment" ? "Local network policy blocked the Core \u2014 this is not a model result." : String(check.error ?? "Host test failed.");
        status.className = cls(`note inline ${check.ok ? "ok" : "err"}`);
        await reload();
      } catch (e) {
        status.textContent = e.message;
        status.className = cls("note inline err");
      }
    };
    const probe = async (checkpointId = "") => {
      if (!model.value.trim()) {
        status.textContent = "Enter or discover a model id first.";
        return;
      }
      status.textContent = "Preparing a one-call tool probe\u2026";
      try {
        const out = await this.api.post("/api/qualification/run", {
          host_id: row.id,
          model: model.value.trim(),
          role: probeRole,
          level: "L1",
          checkpoint_id: checkpointId
        });
        const run = out.run ?? {};
        status.textContent = run.outcome === "pass" ? `L1 tool-call probe passed for ${probeRole} (Screened).` : `L1 probe: ${run.detail ?? run.outcome ?? "did not pass"}`;
        status.className = cls(`note inline ${run.outcome === "pass" ? "ok" : "err"}`);
        clear(confirm2);
        await reload();
      } catch (e) {
        const body = e.body ?? {};
        const checkpoint = body.checkpoint_record;
        if (checkpoint?.id) {
          status.textContent = "Approve this small paid account probe to run it.";
          clear(confirm2, h(
            "div",
            { class: "confirm" },
            "This L1 probe makes one real tool-call request to this host.",
            h(
              "div",
              { class: "row2" },
              h("button", { class: "ghost", onclick: () => clear(confirm2) }, "Cancel"),
              h("button", { class: "primary", onclick: async () => {
                await this.api.post("/api/checkpoints/resolve", { id: checkpoint.id, choice: "approve" });
                await probe(checkpoint.id);
              } }, "Approve probe")
            )
          ));
        } else {
          status.textContent = e.message;
          status.className = cls("note inline err");
        }
      }
    };
    const chooseLead = async (checkpointId = "", override = "") => {
      if (!model.value.trim()) {
        status.textContent = "Enter or discover a model id first.";
        return;
      }
      try {
        await this.api.post("/api/lead", {
          route: { host_id: row.id, model: model.value.trim() },
          ...checkpointId ? { checkpoint_id: checkpointId } : {},
          ...override ? { override } : {}
        });
        status.textContent = `${model.value} is the selected lead route.`;
        clear(confirm2);
        await this.refresh();
      } catch (e) {
        const body = e.body ?? {};
        const checkpoint = body.checkpoint_record;
        if (checkpoint?.id) {
          clear(confirm2, h(
            "div",
            { class: "confirm" },
            e.message,
            h("p", { class: "note" }, "This route remains experimental. Approving records your route choice; it does not mark the model verified."),
            h(
              "div",
              { class: "row2" },
              h("button", { class: "ghost", onclick: () => clear(confirm2) }, "Cancel"),
              h("button", { class: "primary", onclick: async () => {
                await this.api.post("/api/checkpoints/resolve", { id: checkpoint.id, choice: "approve" });
                await chooseLead(checkpoint.id);
              } }, "Use experimental lead")
            )
          ));
        } else if (body.needs_override) {
          const reason = h("input", { type: "text", value: "chosen by the person for this host", "aria-label": "Why use this unqualified lead" });
          clear(confirm2, h(
            "div",
            { class: "confirm" },
            e.message,
            h("p", { class: "note" }, "This records an explicit experimental-route choice; it does not mark the model verified."),
            reason,
            h(
              "div",
              { class: "row2" },
              h("button", { class: "ghost", onclick: () => clear(confirm2) }, "Cancel"),
              h("button", { class: "primary", onclick: () => void chooseLead("", reason.value.trim() || "chosen by the person") }, "Use experimental lead")
            )
          ));
        } else status.textContent = e.message;
      }
    };
    const remove = async () => {
      try {
        await this.api.post("/api/hosts/remove", { host_id: row.id });
        await reload();
      } catch (e) {
        status.textContent = e.message;
      }
    };
    const serviceSlot = h(
      "select",
      { "aria-label": `Service slot on ${row.display_name ?? row.id}` },
      h("option", { value: "ocr" }, "OCR"),
      h("option", { value: "embeddings" }, "Embeddings")
    );
    const chooseService = async () => {
      if (!model.value.trim()) {
        status.textContent = "Enter or discover a model id first.";
        return;
      }
      try {
        await this.api.post("/api/services", {
          slot: serviceSlot.value,
          host_id: row.id,
          model: model.value.trim()
        });
        await this.refresh();
        this.render();
      } catch (e) {
        status.textContent = e.message;
      }
    };
    return h(
      "div",
      { class: "host-card" },
      h(
        "div",
        { class: "row2 tight" },
        h("span", { class: `dot ${row.enabled ? "" : "off"}` }),
        title,
        h("code", {}, String(row.id)),
        row.seeded ? h("span", { class: "dim" }, "preset") : null,
        health
      ),
      h(
        "div",
        { class: "host-grid" },
        h("label", { class: "f" }, "Display name", name),
        h("label", { class: "f" }, "Protocol", protocol),
        h("label", { class: "f" }, "Base URL", base),
        h("label", { class: "f" }, "Credential reference", authRef),
        h("label", { class: "f" }, "Timeout (s)", timeout),
        h("label", { class: "f" }, "Concurrent calls", concurrency),
        h("label", { class: "f" }, "Calls/minute (0 = no local cap)", rate)
      ),
      h("label", { class: "opt" }, enabled, h("span", {}, "Enable this host")),
      h(
        "div",
        { class: "row2" },
        h("button", { class: "ghost", onclick: () => void save() }, "Save host"),
        !row.seeded ? h("button", { class: "ghost", onclick: () => void remove() }, "Remove") : null,
        status
      ),
      row.needs_key ? h("div", { class: "row2" }, key, h("button", { class: "ghost", onclick: () => void setKey() }, "Save key")) : null,
      confirm2,
      h(
        "div",
        { class: "row2" },
        model,
        h("button", { class: "ghost", onclick: () => void discover2() }, "Discover models"),
        h("button", { class: "ghost", onclick: () => void test() }, "Test"),
        h("button", { class: "ghost", onclick: () => void probe() }, `L1 probe (${probeRole})`),
        h("button", { class: "primary", onclick: () => void chooseLead() }, "Use as lead")
      ),
      discovered,
      row.protocol === "openai" ? h(
        "div",
        { class: "row2" },
        serviceSlot,
        h("button", { class: "ghost", onclick: () => void chooseService() }, "Use for service"),
        h("span", { class: "note inline" }, "OCR and embeddings use this exact host. Native speech remains DeepInfra-only; selection is not qualification.")
      ) : null
    );
  }
  newHostCard(reload) {
    const id = h("input", { type: "text", placeholder: "e.g. studio-lan", "aria-label": "New host id" });
    const label = h("input", { type: "text", placeholder: "Display name", "aria-label": "New host display name" });
    const base = h("input", { type: "text", placeholder: "http://127.0.0.1:1234/v1", "aria-label": "New host base URL" });
    const auth = h("input", { type: "text", placeholder: "Optional env/key reference", "aria-label": "New host credential reference" });
    const status = h("span", { class: "note inline", role: "status" });
    const add = async () => {
      try {
        await this.api.post("/api/hosts", { host: {
          id: id.value.trim(),
          display_name: label.value.trim(),
          protocol: "openai",
          base_url: base.value.trim(),
          auth_ref: auth.value.trim(),
          enabled: true,
          timeout: 120,
          concurrency_limit: 1,
          rate_limit: 0
        } });
        await reload();
      } catch (e) {
        status.textContent = e.message;
        status.className = cls("note inline err");
      }
    };
    return h(
      "div",
      { class: "host-card new-host" },
      h("strong", {}, "Add OpenAI-compatible host"),
      h(
        "div",
        { class: "host-grid" },
        h("label", { class: "f" }, "Id", id),
        h("label", { class: "f" }, "Name", label),
        h("label", { class: "f" }, "Base URL", base),
        h("label", { class: "f" }, "Credential reference", auth)
      ),
      h("div", { class: "row2" }, h("button", { class: "primary", onclick: () => void add() }, "Add host"), status)
    );
  }
  /** A stable release can ship two L3-qualified candidates, but an account
   * tool probe and its spend decision still belong to the person. */
  releaseLeadSetup() {
    const root = h("section", { class: "release-leads" });
    void this.api.get("/api/release-leads").then((data) => {
      const choices = data.choices ?? [];
      if (!choices.length) {
        clear(root);
        return;
      }
      clear(
        root,
        h("label", { class: "f" }, "First-run verified leads"),
        choices.map((choice) => {
          const key = h("input", {
            type: "password",
            autocomplete: "off",
            placeholder: choice.key?.saved ? "Key already available" : "Provider key",
            disabled: !choice.available || !!choice.key?.saved,
            "aria-label": `Key for ${choice.model}`
          });
          const status = h("span", { class: "note inline", role: "status" });
          let keySaved = !!choice.key?.saved;
          const pick = async (checkpointId = "") => {
            try {
              const out = await this.api.post("/api/release-leads/select", {
                id: choice.id,
                key: keySaved ? "" : key.value,
                checkpoint_id: checkpointId
              });
              keySaved = true;
              status.textContent = out.selected ? `${choice.model} is ready as lead.` : String(out.reason ?? "Probe did not pass.");
              if (out.selected) await this.refresh();
            } catch (e) {
              const body = e.body ?? {};
              const checkpoint = body.checkpoint_record;
              if (checkpoint?.id) {
                status.textContent = "Approve the small account probe to continue.";
                clear(actions, h("button", { class: "primary", onclick: async () => {
                  await this.api.post("/api/checkpoints/resolve", { id: checkpoint.id, choice: "approve" });
                  await pick(checkpoint.id);
                } }, "Approve account probe"));
              } else status.textContent = e.message;
            }
          };
          const actions = h("div", { class: "row2" });
          const label = choice.available ? "Connect and probe" : "Awaiting release qualification";
          clear(actions, choice.available ? h("button", { class: "primary", onclick: () => void pick() }, label) : null);
          return h(
            "div",
            { class: "host-card release-lead" },
            h("strong", {}, `${choice.provider} \xB7 ${choice.model}`),
            h("p", { class: "note" }, choice.available ? choice.reason ?? "" : `Unavailable: ${choice.reason ?? choice.qualification}`),
            choice.available && !keySaved ? key : null,
            actions,
            status
          );
        })
      );
    }).catch((e) => clear(root, h("p", { class: "error" }, e.message)));
    return root;
  }
  // -- page 2 --------------------------------------------------------------
  context() {
    const s = this.state();
    const text = h("textarea", { class: "f", id: this.fieldId("lib-sys"), placeholder: "What will you be working on?" });
    text.value = s.working_context ?? "";
    let length = s.reply_length ?? "long";
    const custom = h("input", {
      type: "text",
      placeholder: "custom",
      "aria-label": "Custom reply length",
      value: ["long", "short"].includes(length) ? "" : length
    });
    const seg = h("div", { class: "seg", role: "group", "aria-label": "In-chat responses" });
    let customMode = !["long", "short"].includes(length);
    custom.hidden = !customMode;
    const paint = () => clear(seg, ["long", "short", "custom"].map((v) => h("button", {
      "aria-pressed": String(customMode ? v === "custom" : length === v),
      onclick: () => {
        this.dirty = true;
        customMode = v === "custom";
        custom.hidden = !customMode;
        length = v;
        paint();
        if (customMode) custom.focus();
      }
    }, v[0].toUpperCase() + v.slice(1))));
    paint();
    let stance = s.stance ?? "answer";
    const stanceSeg = h("div", { class: "seg", role: "group", "aria-label": "Stance" });
    const paintStance = () => clear(stanceSeg, ["answer", "coach"].map((v) => h("button", {
      "aria-pressed": String(stance === v),
      onclick: () => {
        this.dirty = true;
        stance = v;
        paintStance();
      }
    }, v[0].toUpperCase() + v.slice(1))));
    paintStance();
    const status = h("span", { class: "note inline", role: "status" });
    const thread = s.session;
    const active = h(
      "details",
      {},
      h("summary", {}, "View active context"),
      h("p", {}, "Library chat instructions: " + (s.working_context || "none saved")),
      h("p", {}, "Active session: " + (thread?.session || "none"))
    );
    if (thread?.session) active.addEventListener("toggle", async () => {
      if (!active.open || active.childElementCount > 3) return;
      const lenses = h("p", {}, "Reading session lenses\u2026");
      active.append(lenses);
      try {
        const view = await this.api.tool("session_status", {}, thread.session);
        if (view.error) throw Error(String(view.detail ?? view.error));
        lenses.textContent = "Lenses adopted in this session: " + ((view.lenses ?? []).join(", ") || "none");
      } catch (err) {
        lenses.textContent = "Could not read session lenses: " + err.message;
      }
    });
    return h(
      "div",
      {},
      h("label", { class: "f" }, "Send shortcut on this device", h(
        "select",
        { onchange: (e) => remember("send", e.target.value) },
        h("option", { value: "enter", selected: preference("send") !== "modified" }, "Enter"),
        h("option", { value: "modified", selected: preference("send") === "modified" }, "Ctrl / Cmd + Enter")
      )),
      h("label", { class: "f", for: this.fieldId("lib-sys") }, "Context for chat replies"),
      text,
      h("label", { class: "f" }, "In-chat responses"),
      h("div", { class: "row2 tight" }, seg, custom),
      h("label", { class: "f" }, "Stance"),
      h("div", { class: "row2 tight" }, stanceSeg),
      h("p", { class: "note" }, "Answer replies directly. Coach asks before telling and gives a hint before an answer - a `learn` session always uses Coach, whatever this is set to."),
      h("div", { class: "row2" }, h("button", { class: "primary", onclick: async () => {
        try {
          if (customMode && !custom.value.trim()) {
            status.textContent = "Enter a custom reply length.";
            custom.focus();
            return;
          }
          const submitted = { working_context: text.value, reply_length: customMode ? custom.value.trim() : length, stance };
          await this.api.post("/api/context", submitted);
          await this.refresh();
          if (submitted.working_context !== text.value || submitted.reply_length !== (customMode ? custom.value.trim() : length) || submitted.stance !== stance) {
            status.textContent = "Previous changes saved. New edits are still unsaved.";
            return;
          }
          this.drafts.delete("context");
          if (this.page === "context" && text.isConnected) this.dirty = false;
          active.querySelector("p").textContent = "Library chat instructions: " + (submitted.working_context || "none saved");
          status.textContent = "Saved.";
        } catch (e) {
          status.textContent = e.message;
        }
      } }, "Save"), status),
      active,
      h("p", { class: "note" }, "This shapes chat replies only. Notes, concepts and offerings are written by the tier 2 model without it, so how you like replies never changes how the catalogue is written.")
    );
  }
  // -- page 3 --------------------------------------------------------------
  // A skills registry: curated servers toggle on in one step (install +
  // accept), plus a hand-add form for anything else, status per server, and
  // per-tool Allow/Ask/Deny. Outside tools stay outside the rules - their
  // results are marked untrusted, and none can write to the vault - so this
  // page only ever asks "which server, which tool", never "trust it fully".
  mcp() {
    const host = h("div", {}, h("p", { class: "dim" }, "Loading\u2026"));
    const load = () => this.api.get("/api/mcp").then((data) => clear(host, this.mcpBody(data, load))).catch((e) => clear(host, h("p", { class: "error" }, e.message)));
    load();
    return host;
  }
  mcpBody(data, reload) {
    const servers = data.servers ?? {};
    const toolSettings = data.tool_settings ?? {};
    const status = h("span", { class: "note inline", role: "status" });
    const busy = (label) => {
      status.textContent = label;
      status.className = cls("note inline");
    };
    const fail = (e) => {
      status.textContent = e.message;
      status.className = cls("note inline err");
    };
    const curatedCard = (skill) => {
      const installed = servers[skill.id];
      const on = !!installed?.enabled && installed?.library_enabled !== false;
      const toggle = h("button", { class: on ? "ghost" : "primary", onclick: async () => {
        busy(on ? "Disabling in this library\u2026" : installed ? "Enabling in this library\u2026" : "Installing and enabling\u2026");
        try {
          if (installed) {
            if (!on && !installed.enabled) await this.api.post("/api/mcp/enable", { name: skill.id, enabled: true });
            await this.api.post("/api/mcp/library", { name: skill.id, enabled: !on });
          } else {
            await this.api.post("/api/mcp/server", {
              name: skill.id,
              server: { command: skill.command, args: skill.args, env: skill.env ?? {}, enabled: true }
            });
          }
          status.textContent = "";
          reload();
        } catch (e) {
          fail(e);
        }
      } }, on ? "Disable here" : installed ? "Enable here" : "Install");
      return h(
        "div",
        { class: "srv" },
        h("span", { class: `dot ${on ? "" : "off"}` }),
        h("span", {}, h("strong", {}, skill.name), h("span", { class: "dim" }, ` \xB7 ${skill.description}`)),
        toggle
      );
    };
    const nameInput = h("input", { type: "text", placeholder: "server name" });
    const cmdInput = h("input", { type: "text", placeholder: "command, e.g. npx" });
    const argsInput = h("input", { type: "text", placeholder: "args, space-separated" });
    const envInput = h("input", { type: "text", placeholder: "env as KEY=value, comma-separated (optional)" });
    const searchInput = h("input", {
      type: "search",
      placeholder: "search the MCP registry, e.g. calendar"
    });
    const browseResults = h("div", { class: "browse-results" });
    const fillHandAdd = (name, server) => {
      nameInput.value = name;
      cmdInput.value = server.command;
      argsInput.value = server.args.join(" ");
      envInput.value = Object.entries(server.env).map(([k, v]) => `${k}=${v}`).join(", ");
      nameInput.scrollIntoView({ block: "center" });
      nameInput.focus();
    };
    const runSearch = async () => {
      clear(browseResults, h("p", { class: "dim" }, "Searching\u2026"));
      let out;
      try {
        out = await this.api.get(`/api/mcp/registry?q=${encodeURIComponent(searchInput.value.trim())}`);
      } catch (e) {
        clear(browseResults, h("p", { class: "error" }, e.message));
        return;
      }
      if (out.error) {
        clear(browseResults, h("p", { class: "note err" }, out.error));
        return;
      }
      const entries = out.servers ?? [];
      if (!entries.length) {
        clear(browseResults, h("p", { class: "dim" }, "No results."));
        return;
      }
      clear(browseResults, entries.map((entry) => h(
        "div",
        { class: "srv" },
        h("span", { class: `dot ${entry.resolvable ? "" : "nokey"}` }),
        h(
          "span",
          {},
          h("strong", {}, entry.title || entry.name),
          h("span", { class: "dim" }, ` \xB7 ${entry.description}`),
          entry.repository ? h("a", { href: entry.repository, target: "_blank", rel: "noreferrer noopener" }, " repo \u2197") : null,
          !entry.resolvable ? h("div", { class: "note" }, entry.reason) : null
        ),
        entry.resolvable ? h(
          "button",
          {
            class: "ghost",
            onclick: () => fillHandAdd(String(entry.name).split("/").pop() || entry.name, entry.server)
          },
          "Fill in below"
        ) : null
      )));
    };
    searchInput.onkeydown = (e) => {
      if (e.key === "Enter") runSearch();
    };
    const addServer = async () => {
      const name = nameInput.value.trim();
      if (!name || !cmdInput.value.trim()) {
        fail(new Error("name and command are required"));
        return;
      }
      const env = {};
      for (const pair of envInput.value.split(",").map((s) => s.trim()).filter(Boolean)) {
        const [key, ...rest] = pair.split("=");
        if (key) env[key.trim()] = rest.join("=").trim();
      }
      busy("Adding and accepting\u2026");
      try {
        await this.api.post("/api/mcp/server", { name, server: {
          command: cmdInput.value.trim(),
          args: argsInput.value.split(/\s+/).filter(Boolean),
          env,
          enabled: true
        } });
        nameInput.value = cmdInput.value = argsInput.value = envInput.value = "";
        status.textContent = "";
        reload();
      } catch (e) {
        fail(e);
      }
    };
    const toolRow = (tool) => {
      let setting = toolSettings[tool] ?? "ask";
      const seg = h("div", { class: "seg", role: "group", "aria-label": `${tool} permission` });
      const paint = () => clear(seg, ["allow", "ask", "deny"].map((v) => h("button", {
        "aria-pressed": String(setting === v),
        onclick: async () => {
          try {
            await this.api.post("/api/tool-setting", { tool, setting: v });
            setting = v;
            toolSettings[tool] = v;
            paint();
          } catch (e) {
            fail(e);
          }
        }
      }, v[0].toUpperCase() + v.slice(1))));
      paint();
      return h("div", { class: "row2 tight" }, h("span", { class: "dim" }, tool.replace(/^mcp__/, "")), seg);
    };
    const serverRows = Object.entries(servers).map(([name, s]) => h(
      "div",
      { class: "srv-block" },
      h(
        "div",
        { class: "srv" },
        h("span", { class: `dot ${s.connected ? "" : s.error ? "off" : "nokey"}` }),
        h(
          "span",
          {},
          h("strong", {}, name),
          h("span", { class: "dim" }, ` \xB7 ${s.command}${(s.args ?? []).length ? " " + s.args.join(" ") : ""}`),
          (s.env ?? []).length ? h("span", { class: "dim" }, ` \xB7 env: ${s.env.join(", ")}`) : null,
          h("span", { class: "dim" }, ` \xB7 ${s.tools ?? 0} tool${s.tools === 1 ? "" : "s"}`)
        ),
        s.library_enabled === void 0 ? null : h("button", {
          class: s.library_enabled ? "ghost" : "primary",
          title: "Whether this library uses it; every library decides for itself",
          onclick: async () => {
            busy(s.library_enabled ? "Disabling in this library\u2026" : "Enabling in this library\u2026");
            try {
              await this.api.post("/api/mcp/library", { name, enabled: !s.library_enabled });
              status.textContent = "";
              reload();
            } catch (e) {
              fail(e);
            }
          }
        }, s.library_enabled ? "Disable here" : "Enable here"),
        h("button", { class: "ghost", title: "Installed for you: pausing stops it in every library", onclick: async () => {
          busy(s.enabled ? "Pausing everywhere\u2026" : "Resuming\u2026");
          try {
            await this.api.post("/api/mcp/enable", { name, enabled: !s.enabled });
            status.textContent = "";
            reload();
          } catch (e) {
            fail(e);
          }
        } }, s.enabled ? "Pause all" : "Resume all"),
        h("button", { class: "ghost", onclick: async () => {
          busy("Removing\u2026");
          try {
            await this.api.post("/api/mcp/remove", { name });
            status.textContent = "";
            reload();
          } catch (e) {
            fail(e);
          }
        } }, "Remove")
      ),
      s.error ? h("p", { class: "note err" }, s.error) : null,
      s.unpinned ? h("p", { class: "note err" }, `Not pinned: ${s.unpinned}`) : null,
      s.changed_since_enabled ? h("p", { class: "note" }, "Its definition changed after this library turned it on - still on here; worth a look.") : null,
      (s.tool_names ?? []).length ? h("details", { class: "tool-perms" }, h("summary", {}, `Permissions for ${name} (${s.tool_names.length} tools)`), s.tool_names.map(toolRow)) : null
    ));
    return h(
      "div",
      {},
      h("h3", {}, "Sandbox output"),
      h("p", {}, "Keep files a sandbox or Workbench run writes. Disk usage is uncapped during execution; files are checked afterwards. Permission to run a script is separate. Ask applies in Auto mode too."),
      toolRow("sandbox_output"),
      h("label", { class: "f" }, "Skills registry"),
      h("p", { class: "note" }, "Installed once for you, then enabled per library, off until you turn it on: a history library and a software library each choose their own tools."),
      CURATED_SKILLS.map(curatedCard),
      h("label", { class: "f" }, "Browse the MCP Registry"),
      h(
        "div",
        { class: "row2 tight" },
        searchInput,
        h("button", { class: "ghost", onclick: runSearch }, "Search")
      ),
      browseResults,
      h("label", { class: "f" }, "Add a server by hand"),
      h("div", { class: "row2 tight" }, nameInput, cmdInput),
      h("div", { class: "row2 tight" }, argsInput, envInput),
      h("div", { class: "row2" }, h("button", { class: "primary", onclick: addServer }, "Add and accept"), status),
      h("label", { class: "f" }, "Servers"),
      serverRows.length ? serverRows : h("p", { class: "dim" }, "None configured yet."),
      h(
        "p",
        { class: "note" },
        "Outside tools stay outside the rules: their results are marked untrusted, clerk tasks ",
        "never call them, and none can write to the vault. Each tool defaults to Ask until set otherwise. Meanwhile, ",
        "the librarian itself is an MCP server: `resource-librarian mcp` (see the Cowork plugin)."
      )
    );
  }
  // -- page 4 --------------------------------------------------------------
  library(health) {
    const host = h("div", {}, h("p", { class: "dim" }, "Loading\u2026"));
    this.api.get("/api/library").then((lib) => {
      const promo = h(
        "select",
        { id: this.fieldId("lib-promo") },
        [["person", "person (default): a person accepts every promotion"], ["agent", "agent: the librarian may promote, except sensitive material"]].map(([v, label]) => h("option", { value: v, selected: lib.promotion?.mode === v }, label))
      );
      const status = h("span", { class: "note inline", role: "status" });
      let confirmed = promo.value;
      promo.onchange = async () => {
        promo.disabled = true;
        try {
          await this.api.post("/api/library", { promotion_mode: promo.value });
          confirmed = promo.value;
          status.textContent = "Saved to the vault's config.";
        } catch (error) {
          try {
            confirmed = (await this.api.get("/api/library")).promotion.mode;
            status.textContent = `Change failed: ${error.message}. Current promotion policy: ${confirmed}.`;
          } catch {
            status.textContent = "Could not confirm the current policy. Showing the last confirmed value.";
          }
          promo.value = confirmed;
        } finally {
          promo.disabled = false;
        }
      };
      const keyBox = h("div", { class: "key-entry" });
      let opened = null;
      const keyEntry = (c, row) => {
        opened?.setAttribute("aria-expanded", "false");
        if (opened === row) {
          opened = null;
          clear(keyBox);
          return;
        }
        opened = row;
        row.setAttribute("aria-expanded", "true");
        const label = String(c.name).replace(/^key: /, "");
        const input = h("input", {
          type: "password",
          autocomplete: "off",
          "aria-label": `${label} key`,
          placeholder: c.ok ? `Replace the key (${c.detail})` : `Paste the ${label} key`
        });
        const said = h("span", { class: "note inline", role: "status" });
        const save = async () => {
          if (!input.value.trim()) return;
          said.textContent = "Saving\u2026";
          try {
            const out = await this.api.post("/api/keys", { provider: c.key, key: input.value.trim(), overwrite: true });
            input.value = "";
            said.textContent = out.check?.ok ? out.check.status : `Saved, but the provider said: ${out.check?.error ?? "no answer"}`;
            said.className = cls(`note inline ${out.check?.ok ? "ok" : "err"}`);
            await this.refresh();
            const line = row.closest(sel(".srv"));
            line?.querySelector(sel(".dot"))?.setAttribute("class", cls("dot"));
            const detail = line?.querySelector(sel(".key-detail"));
            if (detail) detail.textContent = " \xB7 saved in this computer's key store";
          } catch (e) {
            said.textContent = e.message;
            said.className = cls("note inline err");
          }
        };
        input.onkeydown = (e) => {
          if (e.key === "Enter") void save();
        };
        clear(keyBox, h(
          "div",
          { class: "confirm" },
          h("label", { class: "f" }, `${label} key`),
          h(
            "div",
            { class: "row2 tight" },
            input,
            h("button", { class: "primary", onclick: () => void save() }, "Save key"),
            h("button", { class: "ghost", onclick: () => keyEntry(c, row) }, "Cancel")
          ),
          said,
          h("small", { class: "dim" }, "Kept in this computer's key store, never in a library. Settings \u2192 Providers & keys lists every key.")
        ));
        input.focus();
      };
      const reviewStatus = h("span", { class: "note inline", role: "status" });
      const reviewBox = (key, label, hint) => {
        const box = h("input", { type: "checkbox", id: this.fieldId(`lib-${key}`) });
        box.checked = !!lib.clerk?.[key];
        box.onchange = async () => {
          try {
            await this.api.post("/api/library", { review: { [key]: box.checked } });
            reviewStatus.textContent = "Saved to the library's config.";
          } catch (e) {
            box.checked = !box.checked;
            reviewStatus.textContent = e.message;
          }
        };
        return h("div", { class: "srv" }, box, h("label", { for: this.fieldId(`lib-${key}`) }, h("strong", {}, label), h("span", { class: "dim" }, ` \xB7 ${hint}`)));
      };
      if (!health) {
        const access = h("div", {}, h("p", {}, "Reading current permissions\u2026"));
        void Promise.allSettled([this.api.get("/api/projects"), this.api.get("/api/mcp")]).then(([projects, mcp]) => {
          const folders = projects.status === "fulfilled" ? projects.value : null;
          const tools = mcp.status === "fulfilled" ? mcp.value : null;
          const enabled = tools ? Object.entries(tools.servers ?? {}).filter(([, s]) => s.enabled && s.library_enabled !== false) : [];
          clear(
            access,
            h("h3", {}, "What can the librarian do here?"),
            h("p", {}, folders ? folders.enabled ? "Project access enabled. Folders allowing edit proposals: " + ((folders.roots ?? []).filter((r) => r.writes).map((r) => r.path).join(", ") || "none") + ". Each change requires approval." : "Project access is off." : "Project access could not be verified."),
            h("button", { class: "ghost", onclick: () => this.open("projects") }, "Manage folder permissions"),
            h("p", {}, tools ? "Enabled external servers: " + (enabled.map(([name, s]) => name + (s.connected ? " (connected)" : " (disconnected)")).join(", ") || "none") + ". Each tool uses its Allow, Ask or Deny rule." : "External tool access could not be verified."),
            h("button", { class: "ghost", onclick: () => this.open("mcp") }, "Manage external tools")
          );
        });
        clear(
          host,
          access,
          h("label", { class: "f", for: this.fieldId("lib-promo") }, "Promotion"),
          h("div", { class: "row2 tight" }, promo, status),
          h("label", { class: "f" }, "Review"),
          reviewBox(
            "review_replies",
            "Check replies",
            "the claims a reply makes about the notes it links are checked against those notes; the verdict shows under the reply"
          ),
          reviewBox(
            "review_offerings",
            "Check drafted offerings",
            "each claim is checked before the draft is staged; a challenged claim kept by the librarian needs you to promote it"
          ),
          h("p", { class: "note" }, "Run by the small-tasks model (tier 3), or `route_review` under [clerk]. A high effort setting also turns these on for its turns. ", reviewStatus),
          h("label", { class: "f" }, "Distribution posture"),
          h("p", {}, String(lib.usage?.distribution_posture ?? "private"), h("span", { class: "dim" }, " \xB7 set in the vault's config")),
          h("label", { class: "f" }, "Clerk route"),
          h("p", {}, lib.clerk?.provider ? `configured: ${lib.clerk.provider}` : "tier 3 model, else queued")
        );
        return;
      }
      clear(
        host,
        h("label", { class: "f" }, "Capabilities on this install"),
        (lib.doctor ?? []).map((c) => h(
          "div",
          { class: "srv" },
          h("span", { class: `dot ${c.ok ? "" : c.required ? "off" : "nokey"}` }),
          h("span", {}, c.key ? h(
            "button",
            {
              class: "link",
              title: `${c.ok ? "Replace" : "Add"} this key`,
              "aria-expanded": "false",
              onclick: (e) => keyEntry(c, e.currentTarget)
            },
            h("strong", {}, c.name)
          ) : h("strong", {}, c.name), h("span", { class: "key-detail" }, ` \xB7 ${c.detail ?? ""}`))
        )),
        keyBox
      );
    }).catch((e) => clear(host, h("p", { class: "error" }, e.message)));
    return host;
  }
  /** The closed topic list (About/Topics.md) and the topics proposed for it (R8): only
   *  here does a proposal join the list - accepted as proposed, renamed, or rejected. */
  async paintTopics(host) {
    clear(host, h("p", { class: "dim" }, "Loading topics\u2026"));
    const status = h("span", { class: "note inline", role: "status" });
    const reload = () => {
      this.drafts.delete("topics");
      if (host.isConnected) this.dirty = false;
      void this.paintTopics(host);
    };
    let out;
    try {
      out = await this.api.tool("topics_list", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
    } catch (e) {
      clear(host, h("p", { class: "error" }, e.message));
      return;
    }
    const propose = h("button", { class: "ghost", onclick: async () => {
      status.textContent = "Asking the clerk to group the sources\u2026";
      try {
        const r = await this.api.tool("topic_propose", { only_unfiled: false });
        if (r.error) throw new Error(String(r.detail ?? r.error));
        status.textContent = r.detail ? String(r.detail) : `${(r.proposed ?? []).length} proposed.`;
        reload();
      } catch (e) {
        status.textContent = e.message;
      }
    } }, "Propose topics");
    const refresh = h("button", {
      class: "ghost",
      title: "Rewrite the topic indexes and the Master Index from the notes",
      onclick: async () => {
        try {
          const result = await this.api.tool("views_refresh", {});
          if (result.error || result.refused) throw new Error(String(result.detail ?? result.error ?? result.refused));
          status.textContent = "Indexes rewritten.";
        } catch (e) {
          status.textContent = e.message;
        }
      }
    }, "Rewrite indexes");
    const proposal = (p) => {
      const name = h("input", { type: "text", value: p.name, "aria-label": "Topic name" });
      const file = h("input", { type: "checkbox", checked: p.acceptance_progress?.refile ?? true });
      const accept = h("button", { class: "primary", onclick: async () => {
        try {
          const r = await this.api.tool("staging_decide", {
            item_ids: [p.id],
            decision: "accept",
            ...p.staged_revision ? { staged_revision: p.staged_revision } : {},
            fields: { name: name.value, refile: file.checked }
          });
          const one = (r.results ?? [])[0] ?? r;
          if (r.error || one.error || one.refused) throw new Error(String(one.detail ?? one.error ?? r.detail ?? r.error));
          status.textContent = `${one.topic} accepted; ${(one.refiled ?? []).filter((x) => x.topic && !x.unchanged).length} source(s) filed under it.`;
          reload();
        } catch (e) {
          status.textContent = e.message;
        }
      } }, p.acceptance_progress ? "Finish acceptance" : "Accept");
      return h(
        "div",
        { class: "srv" },
        name,
        h("label", { class: "note inline" }, file, ` file its ${p.sources} source${p.sources === 1 ? "" : "s"} under it`),
        p.duplicate_of ? h("span", { class: "warn" }, `close to ${p.duplicate_of}`) : null,
        p.acceptance_progress ? h(
          "span",
          { class: "warn" },
          `Partly applied; review before finishing. Completed: ${(p.acceptance_progress.completed_paths ?? []).join(", ")}`
        ) : null,
        accept
      );
    };
    clear(
      host,
      h("p", {}, (out.topics ?? []).map((t) => `${t.topic} (${t.sources})`).join(" \xB7 ")),
      out.unfiled ? h("p", { class: "note" }, `${out.unfiled} source${out.unfiled === 1 ? "" : "s"} Unfiled.`) : null,
      (out.not_accepted ?? []).length ? h("p", { class: "warn" }, `Filed under topics not in the list: ${out.not_accepted.join(", ")}.`) : null,
      (out.proposed ?? []).length ? h("p", { class: "note" }, "Proposed from the library's own sources (details in Staging \u2192 Topics):") : null,
      (out.proposed ?? []).map(proposal),
      h(
        "div",
        { class: "row2 tight" },
        propose,
        refresh,
        h("button", { class: "ghost", onclick: reload }, "Reload topics (discards edits)"),
        status
      )
    );
  }
  /** The domain profile this library was created with (profiles.py): what it
   *  suggests and where each item stands. Suggestions only - each is taken up
   *  through its own gate (a pack's Accept below, a server's Enable here on
   *  the MCP servers page). */
  async paintProfile(host) {
    try {
      const out = await this.api.tool("library_profile", {});
      if (!out.profile) {
        clear(host);
        return;
      }
      const done = (state) => state === "accepted" || state === "enabled here" || state === "available";
      const item = (kind, name, state) => h(
        "div",
        { class: "srv" },
        h("span", { class: `dot ${done(state) ? "" : "nokey"}` }),
        h("span", {}, h("strong", {}, name), h("span", { class: "dim" }, ` \xB7 ${kind} \xB7 ${state}`))
      );
      clear(
        host,
        h("label", { class: "f" }, `Set up for its domain: the ${out.profile} profile`),
        (out.content_model_added ?? []).length ? h("p", { class: "note" }, `Added at creation: ${out.content_model_added.join("; ")}.`) : null,
        (out.lens_packs ?? []).map((p) => item("lens pack - accept it below", p.name, p.state)),
        (out.mcp_servers ?? []).map((m) => item("outside server - MCP servers page", m.name, m.state)),
        (out.workflows ?? []).map((w) => item("workflow", w.name, w.state)),
        h("p", { class: "note" }, "Suggestions only: nothing here is accepted, installed or turned on until you do it.")
      );
    } catch {
      clear(host);
    }
  }
  /** Lens packs (lens_packs.py): a plugin's or domain pack's hand-written
   *  lenses. Nothing is installed until a person accepts a pack's exact text;
   *  a pack whose file changed since shows as changed and needs accepting again. */
  async paintPacks(host, message = "") {
    try {
      const out = await this.api.tool("lens_packs", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const packs = out.packs ?? [];
      const status = h("span", { class: "note inline", role: "status" }, message);
      clear(
        host,
        h("p", { class: "note" }, "A pack's lenses are instructions someone else wrote for the model. Read them before accepting; nothing is used until a person adopts a lens in a thread."),
        packs.length ? packs.map((p) => h(
          "div",
          { class: "srv" },
          h("span", { class: `dot ${p.state === "accepted" ? "" : p.state === "invalid" ? "off" : "nokey"}` }),
          h(
            "span",
            {},
            h("strong", {}, p.name),
            ` \xB7 ${p.origin} \xB7 ${p.state} \xB7 ${p.lenses.length} lens${p.lenses.length === 1 ? "" : "es"}`,
            p.description ? h("small", { class: "dim" }, ` \u2014 ${p.description}`) : null,
            h("details", {}, h("summary", {}, "Lenses"), h("ul", {}, p.lenses.map((n) => h("li", {}, n)))),
            p.problems.length ? h("p", { class: "note err" }, p.problems.slice(0, 5).join("; ")) : null
          ),
          p.state === "not accepted" || p.state === "changed" ? h("button", { class: "ghost", onclick: async () => {
            try {
              const r = await this.api.tool("lens_pack_accept", { name: p.name });
              if (r.error) throw new Error(String(r.detail ?? r.error));
              void this.paintPacks(host, `${p.name}: ${r.lenses.length} lens(es) installed${r.replaced ? `, ${r.replaced} replaced` : ""}.`);
            } catch (e) {
              status.textContent = e.message;
            }
          } }, p.state === "changed" ? "Accept the new version" : "Accept") : null
        )) : h("p", { class: "dim" }, "No lens packs. A plugin or domain pack adds one to .librarian/lens_packs/."),
        status
      );
    } catch (e) {
      clear(host, h("p", { class: "error" }, e.message));
    }
  }
  /** Standard model catalogues (model_catalog.py): a provider's models,
   *  already profiled once and shipped with the package. Adopting one writes
   *  its Source notes straight in - each was reviewed once already, so this
   *  is reusing that review, not asking the vault to trust a fresh draft. */
  async paintModelCatalogs(host, message = "") {
    try {
      const out = await this.api.tool("model_catalog_status", {});
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const catalogs = out.catalogues ?? [];
      const status = h("span", { class: "note inline", role: "status" }, message);
      clear(
        host,
        h("p", { class: "note" }, "Each model here was already profiled once from its provider's own listing page - adopting a catalogue reuses that, instead of profiling every model again in this vault."),
        catalogs.length ? catalogs.map((c) => h(
          "div",
          { class: "srv" },
          h("span", { class: `dot ${c.held === c.models ? "" : "nokey"}` }),
          h(
            "span",
            {},
            h("strong", {}, c.provider),
            ` \xB7 ${c.held}/${c.models} models held`,
            c.needs_attention?.length ? h(
              "p",
              { class: "warn" },
              `Review incomplete/unfindable Source notes: ${c.needs_attention.slice(0, 5).join(", ")}. Existing notes are not overwritten by re-adoption.`
            ) : null
          ),
          c.held < c.models ? h("button", { class: "ghost", onclick: async (e) => {
            const button = e.currentTarget;
            button.disabled = true;
            try {
              const r = await this.api.tool("model_catalog_adopt", { provider: c.provider });
              if (r.error) throw new Error(String(r.detail ?? r.error));
              await this.paintModelCatalogs(host, `${c.provider}: ${r.written} model(s) added${r.already_held ? `, ${r.already_held} already held` : ""}${r.failed.length ? `, ${r.failed.length} failed` : ""}${r.not_findable?.length ? `, ${r.not_findable.length} need findability review` : ""}.` + (r.failed.length ? ` Review before retrying: ${r.failed.slice(0, 3).map((f) => `${f.name}: ${f.error}`).join("; ")}` : ""));
            } catch (e2) {
              status.textContent = e2.message;
            } finally {
              if (button.isConnected) button.disabled = false;
            }
          } }, c.held ? "Adopt the rest" : "Adopt") : null
        )) : h("p", { class: "dim" }, "No standard model catalogues are bundled with this install."),
        status
      );
    } catch (e) {
      clear(host, h("p", { class: "error" }, e.message));
    }
  }
};

// ../ui/src/pane.ts
var RECENT = 8;
var DocPane = class {
  /** `onMoved`: a note was renamed, so links to it elsewhere (the chat) can follow.
   *  `currentProject`: the open session's pursuit, if any - drives the ⋮ menu's Desk
   *  section and which pursuit a note opened here is touched against. */
  constructor(api, plan, vaultName, onClose, onMoved = () => void 0, currentProject = () => "", currentSession = () => "") {
    this.api = api;
    this.plan = plan;
    this.vaultName = vaultName;
    this.onClose = onClose;
    this.onMoved = onMoved;
    this.currentProject = currentProject;
    this.currentSession = currentSession;
    this.el = h("aside", { class: "lib-pane", "aria-label": "Document" });
    this.crumbs = h("div", { class: "pane-crumbs" });
    this.menuButton = h("button", {
      class: "icon-btn",
      title: "Note actions",
      "aria-label": "Note actions",
      "aria-haspopup": "true",
      "aria-expanded": "false"
    }, "\u22EE");
    this.menu = h("div", { class: "pane-menu", hidden: true, role: "menu" });
    // Text to speech, mode B: read the open document aloud (slot 5).
    // A person's run (EXECUTION_SANDBOX_ONLY): only for a script file (.py, .sh) - never a
    // note or text - in the air-gapped sandbox; what it wrote lands on its own pad.
    this.runButton = h("button", {
      class: "icon-btn run",
      hidden: true,
      title: "Run this script in the sandbox (no network; it can write only to its landing pad)",
      "aria-label": "Run this script",
      onclick: () => void this.runScript()
    }, runIcon());
    this.runOutput = h("div", { class: "run-output" });
    this.speakButton = h("button", {
      class: "icon-btn speak",
      hidden: true,
      title: "Read this document",
      "aria-label": "Read this document",
      onclick: () => {
        if (this.current.kind === "doc") void reader.toggle({ path: this.current.path }, this.speakButton);
      }
    }, speakerIcon());
    this.body = h("div", { class: "pane-body" });
    this.recent = [];
    this.version = 0;
    this.switcher = h("div", { class: "pane-views", role: "group", "aria-label": "Pane view" });
    this.compact = h("select", { "aria-label": "Pane view" });
    this.current = { kind: "plan" };
    this.browsing = "";
    this.onDocumentClick = (e) => {
      if (!this.menu.hidden && !e.composedPath().includes(this.menu) && !e.composedPath().includes(this.menuButton)) {
        this.showMenu(false);
      }
    };
    /** Escape closes the open menu and is consumed; otherwise it passes by. */
    this.onDocumentKey = (e) => {
      if (e.key !== "Escape" || this.menu.hidden) return;
      this.showMenu(false);
      this.menuButton.focus();
      e.preventDefault();
      e.stopPropagation();
    };
    this.menuButton.onclick = () => this.toggleMenu();
    const change = (view) => {
      this.showMenu(false);
      if (view === "Note" && this.recent.length) void this.open(this.recent[0].path);
      else if (view === "Plan") this.showPlan();
      else if (view === "This week") void this.showAgenda();
      else void this.showBrowse();
    };
    for (const view of ["Note", "Browse", "Plan", "This week"]) {
      this.switcher.append(h("button", { class: "ghost", onclick: () => change(view) }, view));
      this.compact.append(h("option", { value: view }, view));
    }
    this.compact.onchange = () => change(this.compact.value);
    this.el.append(
      this.switcher,
      h("label", { class: "pane-view-select" }, "View ", this.compact),
      h(
        "div",
        { class: "pane-head" },
        this.crumbs,
        h(
          "div",
          { class: "pane-actions" },
          this.runButton,
          this.speakButton,
          this.menuButton,
          h("button", {
            class: "icon-btn",
            title: "Close the pane",
            "aria-label": "Close the pane",
            onclick: () => this.onClose()
          }, "\u2715")
        ),
        this.menu
      ),
      this.body
    );
    document.addEventListener("click", this.onDocumentClick);
    document.addEventListener("keydown", this.onDocumentKey);
    this.showPlan();
  }
  dispose() {
    document.removeEventListener("click", this.onDocumentClick);
    document.removeEventListener("keydown", this.onDocumentKey);
  }
  get showingPlan() {
    return this.current.kind === "plan";
  }
  mark(view) {
    this.version++;
    this.compact.value = view;
    this.compact.options[0].disabled = !this.recent.length && view !== "Note";
    this.switcher.querySelectorAll("button").forEach((b) => {
      b.disabled = b.textContent === "Note" && this.compact.options[0].disabled;
      b.setAttribute("aria-pressed", String(b.textContent === view));
    });
    this.menuButton.hidden = view !== "Note";
    this.showMenu(false);
  }
  showPlan() {
    this.mark("Plan");
    this.current = { kind: "plan" };
    this.speakButton.hidden = true;
    this.runButton.hidden = true;
    clear(
      this.crumbs,
      h("span", { class: "crumb-here" }, "Plan"),
      h("span", { class: "dim" }, " \xB7 the session this chat is working in")
    );
    clear(this.body, this.plan);
    this.body.scrollTop = 0;
  }
  /** "This week": every open, dated task across the vault, computed fresh -
   *  no daemon, nothing kept in sync (Co-work Roadmap 2C). */
  async showAgenda() {
    this.mark("This week");
    const version = this.version;
    this.current = { kind: "agenda" };
    this.speakButton.hidden = true;
    this.runButton.hidden = true;
    clear(
      this.crumbs,
      h("span", { class: "crumb-here" }, "This week"),
      h("span", { class: "dim" }, " \xB7 open, dated tasks across the vault")
    );
    clear(this.body, h("p", { class: "dim pad" }, "Loading\u2026"));
    try {
      const out = await this.api.tool("agenda", {});
      if (version !== this.version) return;
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const groups = [
        ["overdue", "Overdue"],
        ["today", "Today"],
        ["this_week", "This week"],
        ["later", "Later"],
        ["undated", "No date"]
      ];
      const rows = (tasks) => h("ul", {}, tasks.map((t) => h(
        "li",
        {},
        h("a", { class: "wl", href: "#", onclick: (e) => {
          e.preventDefault();
          void this.open(t.path);
        } }, t.note),
        ": ",
        t.text,
        t.due ? h("small", {}, ` \u{1F4C5} ${t.due}`) : null
      )));
      const sections = groups.map(([key, label]) => {
        const tasks = out[key] ?? [];
        return tasks.length ? h("section", {}, h("h4", {}, `${label} (${tasks.length})`), rows(tasks)) : null;
      });
      const empty = groups.every(([key]) => !(out[key] ?? []).length);
      clear(this.body, h(
        "div",
        { class: "pad agenda" },
        empty ? h("p", { class: "dim" }, "Nothing open with a checkbox anywhere in the vault.") : sections
      ));
    } catch (e) {
      if (version === this.version) clear(this.body, h("div", { class: "pad" }, h("p", { class: "error" }, e.message)));
    }
    this.body.scrollTop = 0;
  }
  /** A vault path (with or without .md) or a bare note name. */
  async open(target) {
    const version = ++this.version;
    this.menuButton.hidden = this.speakButton.hidden = this.runButton.hidden = true;
    clear(this.body, h("p", { class: "dim pad" }, `Opening ${target}\u2026`));
    let doc;
    try {
      doc = await this.api.get(`/api/file?path=${encodeURIComponent(target)}`);
    } catch (e) {
      if (version !== this.version) return;
      clear(this.crumbs, h("span", { class: "crumb-here" }, target));
      clear(this.body, h(
        "div",
        { class: "pad" },
        h("p", { class: "error" }, e.message),
        h("p", { class: "dim" }, "Names are exact. Choose Browse, or ask the librarian for the path.")
      ));
      return;
    }
    if (version !== this.version) return;
    this.mark("Note");
    this.current = { kind: "doc", path: doc.path, name: doc.name };
    this.speakButton.hidden = Boolean(doc.script);
    this.runButton.hidden = !doc.script;
    this.browsing = doc.path.split("/").slice(0, -1).join("/");
    this.recent = [{ path: doc.path, name: doc.name }, ...this.recent.filter((r) => r.path !== doc.path)].slice(0, RECENT);
    const project = this.currentProject();
    if (project) this.api.tool("desk_touch", { project, note: doc.name }).catch(() => void 0);
    this.paintCrumbs(doc.path);
    if (doc.script) {
      clear(this.runOutput);
      clear(this.body, h(
        "article",
        { class: "doc" },
        h("h1", { class: "doc-title" }, doc.name),
        h("pre", { class: "code" }, h("code", {}, doc.text)),
        this.runOutput
      ));
      this.body.scrollTop = 0;
      return;
    }
    const rendered = render(doc.text, (t) => void this.open(t), { frontmatter: true });
    const own2 = Array.from(rendered.children).find((el) => !el.matches(sel("table.props")));
    const titled = own2?.tagName === "H2" && own2.textContent?.trim().toLowerCase() === String(doc.name).toLowerCase();
    if (titled) own2.remove();
    clear(this.body, h("article", { class: "doc" }, h("h1", { class: "doc-title" }, doc.name), rendered));
    this.body.scrollTop = 0;
  }
  /** Run the open script in the sandbox, as the person's own action, and show what came
   *  back: exit code, output, and what landed on its pad. */
  async runScript() {
    if (this.current.kind !== "doc") return;
    const path2 = this.current.path;
    this.runButton.disabled = true;
    clear(this.runOutput, h("p", { class: "dim" }, "Running in the sandbox (no network)\u2026"));
    try {
      const r = await this.api.post("/api/sandbox/run_file", { path: path2 });
      if (r.error) {
        clear(this.runOutput, h("p", { class: "error" }, String(r.detail ?? r.error)));
      } else {
        const files = r.files ?? [];
        clear(
          this.runOutput,
          h("h4", {}, `Run ${r.run}: exit ${r.exit_code}${r.timed_out ? " (stopped: too long)" : ""}`),
          r.stdout ? h("pre", { class: "code" }, h("code", {}, r.stdout)) : null,
          r.stderr ? h("pre", { class: "code err" }, h("code", {}, r.stderr)) : null,
          h("p", { class: "dim" }, r.output?.kept === false ? "Output was not kept. See the run notes below." : files.length ? `Landed in ${r.landing}: ${files.map((f) => `${f.name} (${f.bytes} bytes)`).join(", ")}. Nothing there is run or imported.` : "Nothing landed."),
          ...(r.notes ?? []).map((n) => h("p", { class: "dim" }, n))
        );
      }
    } catch (e) {
      clear(this.runOutput, h("p", { class: "error" }, e.message));
    }
    this.runButton.disabled = false;
  }
  paintCrumbs(path2) {
    const parts = path2.split("/");
    const out = [];
    parts.forEach((part, i) => {
      out.push(h("span", { class: "sep" }, "/"));
      if (i === parts.length - 1) {
        out.push(h("span", { class: "crumb-here" }, part));
      } else {
        const dir = parts.slice(0, i + 1).join("/");
        out.push(h("button", {
          class: "crumb-dir",
          title: `Browse ${dir}`,
          onclick: () => {
            this.browsing = dir;
            void this.showBrowse();
          }
        }, part));
      }
    });
    clear(this.crumbs, out);
  }
  // -- the ⋮ menu ------------------------------------------------------------
  toggleMenu() {
    if (this.menu.hidden && this.current.kind === "doc") {
      this.browsing = this.current.path.split("/").slice(0, -1).join("/");
    }
    this.showMenu(this.menu.hidden !== false);
  }
  showMenu(on) {
    this.menu.hidden = !on;
    this.menuButton.setAttribute("aria-expanded", String(on));
    if (on) void this.paintMenu();
  }
  async paintMenu() {
    const item = (label, small, action, cls2 = "") => h("button", {
      class: `menuitem ${cls2}`,
      role: "menuitem",
      onclick: action
    }, label, small ? h("small", {}, small) : null);
    const vault = this.vaultName();
    const obsidian = this.current.kind === "doc" && vault ? `obsidian://open?vault=${encodeURIComponent(vault)}&file=${encodeURIComponent(this.current.path)}` : "";
    const doc = this.current.kind === "doc" ? this.current : null;
    if (!doc) return;
    clear(
      this.menu,
      obsidian ? h("a", { class: "menuitem", href: obsidian, role: "menuitem" }, "Open this note in Obsidian") : null,
      item("Rename or move\u2026", "Links follow the note", () => this.paintMove(doc), "move"),
      item("Copy path", doc.path, async () => {
        try {
          await navigator.clipboard.writeText(doc.path);
          this.showMenu(false);
          this.menuButton.focus();
        } catch {
          this.menu.append(h("p", { role: "status" }, doc.path));
        }
      })
    );
    this.menu.querySelector("a,button")?.focus();
  }
  async showBrowse() {
    const doc = this.recent[0] ?? null;
    this.current = { kind: "browse" };
    this.mark("Browse");
    this.runButton.hidden = this.speakButton.hidden = true;
    clear(this.crumbs, "Browse");
    const browser = h("div", { class: "pane-browser pad" });
    clear(this.body, browser);
    const item = (label, small, action, cls2 = "") => h("button", { class: "menuitem " + cls2, onclick: action }, label, small ? h("small", {}, small) : null);
    const folder = h("div", { class: "pane-folder" }), desk = h("div", { class: "pane-desk" }), lenses = h("div", { class: "pane-lenses" });
    const project = this.currentProject(), session = this.currentSession();
    clear(
      browser,
      project ? h("h4", {}, `Desk \u2014 ${project}`) : null,
      project ? desk : null,
      session ? h("h4", {}, "Lenses \u2014 this thread") : null,
      session ? lenses : null,
      this.recent.length ? h("h4", {}, "Recent") : null,
      this.recent.map((r) => item(r.name, r.path, () => {
        this.showMenu(false);
        void this.open(r.path);
      })),
      h("h4", {}, "Browse"),
      folder
    );
    try {
      const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(this.browsing)}`);
      const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
      clear(
        folder,
        h("div", { class: "folder-path" }, `/${listing.dir}`),
        up !== null ? item(`\u2191 ${up ? up.split("/").pop() : "the vault"}`, "", () => {
          this.browsing = up;
          void this.showBrowse();
        }, "dir up") : null,
        listing.entries.map((e) => e.kind === "dir" ? item(`${e.name}/`, "", () => {
          this.browsing = e.path;
          void this.showBrowse();
        }, "dir") : item(e.name, "", () => {
          this.showMenu(false);
          void this.open(e.path);
        }, "file")),
        listing.entries.length ? null : h("p", { class: "dim" }, "No notes here.")
      );
    } catch (e) {
      this.browsing = "";
      clear(folder, h("p", { class: "error" }, e.message));
    }
    if (project) void this.paintDesk(desk, project, item, doc);
    if (session) void this.paintLenses(lenses, session);
  }
  /** Accepted lenses for this thread: the adopted ones (each an instruction
   *  in the model's prompt until dropped), then the rest with what each
   *  catches and when not to use it. Adopting is the person's choice - this
   *  pane calls as the person - and a thread holds at most three. */
  async paintLenses(host, session) {
    try {
      const [status, out] = await Promise.all([
        this.api.tool("session_status", {}, session),
        this.api.tool("lens_suggest", { limit: 12 }, session)
      ]);
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const adopted = new Set(status.lenses ?? []);
      const all = out.lenses ?? [];
      const toggle = (id) => async () => {
        try {
          const r = await this.api.tool(adopted.has(id) ? "lens_drop" : "lens_adopt", { lens_id: id }, session);
          if (r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? r.error));
        } catch (e) {
          clear(host, h("p", { class: "error" }, e.message));
          return;
        }
        void this.paintLenses(host, session);
      };
      clear(host, all.length ? all.sort((a, b) => Number(adopted.has(b.id)) - Number(adopted.has(a.id))).map((l) => h(
        "div",
        { class: "menuitem desk-row", title: [l.catches && `Catches: ${l.catches}`, l.not_when && `Not when: ${l.not_when}`].filter(Boolean).join("\n") },
        h("span", { class: "lens-name" }, l.name, h(
          "small",
          { title: l.source },
          ` \xB7 ${l.source.length > 36 ? `${l.source.slice(0, 35)}\u2026` : l.source}`
        )),
        h(
          "button",
          {
            class: "icon-btn pin-toggle",
            title: adopted.has(l.id) ? "Drop from this thread" : "Adopt for this thread",
            "aria-label": adopted.has(l.id) ? `Drop ${l.name}` : `Adopt ${l.name}`,
            onclick: () => void toggle(l.id)()
          },
          adopted.has(l.id) ? "\u2713" : "+"
        )
      )) : h("p", { class: "dim" }, "No accepted lenses yet - accept one in Staging, or a lens pack in Settings \u2192 Library."));
    } catch (e) {
      clear(host, h("p", { class: "error" }, e.message));
    }
  }
  async paintDesk(desk, project, item, doc) {
    try {
      const out = await this.api.tool("desk_show", { project });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const working = out.working_set ?? [];
      const pinned = new Set(working.filter((r) => r.pinned).map((r) => r.note));
      const togglePin = (name) => async () => {
        try {
          await this.api.tool(pinned.has(name) ? "desk_unpin" : "desk_pin", { project, note: name });
        } catch {
        }
        void this.paintDesk(desk, project, item, doc);
      };
      clear(
        desk,
        doc ? item(
          pinned.has(doc.name) ? `\u{1F4CC} Unpin "${doc.name}"` : `\u{1F4CC} Pin "${doc.name}" to the desk`,
          "",
          () => void togglePin(doc.name)(),
          "pin"
        ) : null,
        working.length ? working.map((r) => h(
          "div",
          { class: "menuitem desk-row" },
          h("button", { class: "wl", onclick: () => {
            this.showMenu(false);
            void this.open(r.note);
          } }, r.note),
          h("small", {}, r.why),
          h(
            "button",
            {
              class: "icon-btn pin-toggle",
              title: r.pinned ? "Unpin" : "Pin",
              "aria-label": r.pinned ? `Unpin ${r.note}` : `Pin ${r.note}`,
              onclick: () => void togglePin(r.note)()
            },
            r.pinned ? "\u{1F4CC}" : "\u{1F4CD}"
          )
        )) : h("p", { class: "dim" }, "Nothing on the desk yet - open or pin a note.")
      );
    } catch (e) {
      clear(desk, h("p", { class: "error" }, e.message));
    }
  }
  // -- rename or move ----------------------------------------------------------
  paintMove(doc) {
    const here = doc.path.split("/").slice(0, -1).join("/");
    const name = h("input", {
      type: "text",
      id: "lib-mv-name",
      value: doc.name,
      "aria-label": "New name"
    });
    const folder = h("input", {
      type: "text",
      id: "lib-mv-folder",
      value: here,
      "aria-label": "Folder",
      placeholder: "the vault's top level"
    });
    const picker = h("div", { class: "picker" });
    const status = h("div", { role: "status" });
    let picking = here;
    const paintPicker = async () => {
      clear(picker, h("p", { class: "dim" }, "Loading\u2026"));
      try {
        const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(picking)}`);
        const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
        const go = (dir) => () => {
          picking = dir;
          folder.value = dir;
          void paintPicker();
        };
        clear(
          picker,
          h("div", { class: "folder-path" }, `/${listing.dir}`),
          up !== null ? h(
            "button",
            { class: "menuitem dir up", type: "button", onclick: go(up) },
            `\u2191 ${up ? up.split("/").pop() : "the vault"}`
          ) : null,
          listing.entries.filter((e) => e.kind === "dir").map((e) => h("button", { class: "menuitem dir", type: "button", onclick: go(e.path) }, `${e.name}/`))
        );
      } catch (e) {
        clear(picker, h("p", { class: "error" }, e.message));
      }
    };
    const submit = async () => {
      const newName = name.value.trim();
      const newFolder = folder.value.trim().replace(/^\/+|\/+$/g, "");
      const args = { name: doc.name };
      if (newName && newName !== doc.name) args.new_name = newName;
      if (newFolder !== here) args.new_folder = newFolder;
      if (!args.new_name && args.new_folder === void 0) {
        clear(status, h("p", { class: "error" }, "Nothing changed: give a new name or a different folder."));
        return;
      }
      clear(status, h("p", { class: "dim" }, "Moving\u2026"));
      try {
        const out = await this.api.tool("note_move", args);
        if (out.error) throw new Error(String(out.detail ?? out.error));
        const moved = String(out.path);
        const movedName = moved.split("/").pop().replace(/\.md$/, "");
        const updated = out.updated_links ?? [];
        this.recent = this.recent.filter((r) => r.path !== doc.path);
        this.showMenu(false);
        if (movedName !== doc.name) this.onMoved(doc.name, movedName);
        await this.open(moved);
        this.body.querySelector(sel("article.doc"))?.prepend(h(
          "div",
          { class: "note moved", role: "status" },
          `Moved from ${doc.path}. `,
          updated.length ? h(
            "details",
            {},
            h(
              "summary",
              {},
              `Updated links in ${updated.length} note${updated.length === 1 ? "" : "s"}.`
            ),
            h("ul", {}, updated.map((p) => h("li", {}, p)))
          ) : "No other note linked to it."
        ));
      } catch (e) {
        clear(status, h("p", { class: "error" }, e.message));
      }
    };
    const onEnter = (e) => {
      if (e.key === "Enter") void submit();
    };
    name.addEventListener("keydown", onEnter);
    folder.addEventListener("keydown", onEnter);
    clear(this.menu, h(
      "div",
      { class: "move-form" },
      h("h4", {}, "Rename or move"),
      h("label", { class: "f", for: "lib-mv-name" }, "Name"),
      name,
      h("label", { class: "f", for: "lib-mv-folder" }, "Folder"),
      folder,
      picker,
      h(
        "div",
        { class: "row2" },
        h("button", { class: "primary", type: "button", onclick: () => void submit() }, "Move"),
        h("button", { class: "ghost", type: "button", onclick: () => void this.paintMenu() }, "Cancel")
      ),
      status,
      h("p", { class: "note" }, "Every [[link]] to this note by its name is updated to match.")
    ));
    name.focus();
    name.select();
    void paintPicker();
  }
};

// ../ui/src/views.ts
var BEST_FOR_TAGS = [
  "Talking_Fast",
  "Long_Conversations",
  "Small_Coding_Tasks",
  "Large_Coding_Tasks",
  "Long_Horizon_Tasks"
];
var TIERS = ["Tier_1", "Tier_2", "Tier_3"];
var untag = (s) => s.replace(/_/g, " ");
var APPROVABLE = ["staged", "deferred", "failed", "partial"];
var DEFERRABLE = ["staged", "approved", "enriched", "partial"];
var Staging = class {
  // an offering to open once the list loads
  constructor(api, openNote, currentSession = () => "", onSessionUpdate = () => {
  }, openModels = () => {
  }, onBatch = () => {
  }, routeHint = () => "", libraryKey = () => "") {
    this.api = api;
    this.openNote = openNote;
    this.currentSession = currentSession;
    this.onSessionUpdate = onSessionUpdate;
    this.openModels = openModels;
    this.onBatch = onBatch;
    this.routeHint = routeHint;
    this.libraryKey = libraryKey;
    this.el = h("div", { class: "view staging" });
    this.list = h("div", { class: "items", role: "listbox", "aria-label": "Staged items" });
    this.detail = h("div", { class: "detail" });
    this.kind = "source";
    this.status = "staged";
    // sources only: which part of their lifecycle
    this.selected = "";
    // Research Pipeline §4.2: shown on every kind while approved sources wait, and while a
    // batch runs; polled only while one runs.
    this.banner = h("div", { class: "batch-banner", role: "status" });
    this.poll = 0;
    this.wasRunning = false;
    // True right after a decision's outcome message is shown, until the person
    // opens something else or explicitly refreshes: an automatic reload (the
    // SSE echo of this same decision, or someone else's) must not wipe it.
    this.detailLocked = false;
    this.restoredLibrary = "";
    this.resumeScroll = null;
    // Several sources decided at once: the person ticks the ones they mean, never an
    // "approve all", and never opening each in turn. Each ticked item is sent on its
    // own with the revision its row showed, so one that changed since is refused and
    // left untouched while the rest go through (owner, 2026-11-05).
    this.picked = /* @__PURE__ */ new Set();
    this.rows = /* @__PURE__ */ new Map();
    this.bulkCount = h("span", { class: "dim" });
    this.bulkReason = h("input", {
      type: "text",
      placeholder: "Reason, to defer",
      "aria-label": "Reason for deferring the ticked items"
    });
    this.bulkApprove = h("button", { type: "button", class: "primary", onclick: () => void this.decideTicked("approve") });
    this.bulkDefer = h("button", { type: "button", class: "ghost", onclick: () => void this.decideTicked("defer") });
    this.bulkClear = h("button", { type: "button", class: "ghost", onclick: () => {
      this.picked.clear();
      this.list.querySelectorAll("input[type=checkbox]").forEach((box) => {
        box.checked = false;
      });
      this.paintBulk();
    } }, "Clear");
    this.bulkStatus = h("span", { role: "status" });
    this.bulk = h(
      "div",
      { class: "bulk-bar", role: "group", "aria-label": "Decide the ticked sources" },
      this.bulkCount,
      this.bulkApprove,
      this.bulkReason,
      this.bulkDefer,
      this.bulkClear,
      this.bulkStatus
    );
    this.bulkStatusFilter = "";
    this.listRequest = 0;
    this.paintKinds = () => {
    };
    this.evidenceMode = h("select", { "aria-label": "Review evidence layout" }, h("option", { value: "beside" }, "Evidence beside draft"), h("option", { value: "demand" }, "Evidence on demand"));
    this.stopped = false;
    this.pending = "";
    const kinds = h("div", { class: "seg", role: "group", "aria-label": "Kind" });
    const statuses = h("select", { "aria-label": "Which sources", onchange: () => {
      this.status = statuses.value;
      this.selected = "";
      this.savePosition();
      void this.load(true);
    } }, [
      ["staged", "Captured, to review"],
      ["approved", "Approved, awaiting ingestion"],
      ["enriched", "Ingested, ready to accept"],
      ["partial", "Ingested with gaps"],
      ["queued", "Queued for capture"],
      ["failed", "Failed"],
      ["deferred", "Deferred"]
    ].map(([v, label]) => h("option", { value: v }, label)));
    this.statuses = statuses;
    this.el.addEventListener("scroll", () => this.savePosition(), { passive: true });
    const paint = () => {
      const focusedKind = kinds.contains(document.activeElement) ? document.activeElement.dataset.kind : "";
      clear(kinds, [["source", "Sources"], ["lens", "Lenses"], ["concept", "Concepts"], ["topic", "Topics"], ["offering", "Offerings"], ["import", "From V1"]].map(([v, label]) => h("button", { "data-kind": v, "aria-pressed": String(this.kind === v), onclick: () => {
        this.selected = "";
        this.kind = v;
        this.savePosition();
        paint();
        void this.load(true);
      } }, label, h("span", { class: "queue-count", title: v === "source" ? "Sources in selected filter" : "Waiting for review" }, String(v === "offering" ? this.waitingOfferings ?? "\u2026" : this.counts ? this.counts[v]?.[v === "source" ? this.status : "staged"] ?? 0 : "\u2026")))));
      if (focusedKind) kinds.querySelector(`[data-kind="${focusedKind}"]`)?.focus({ preventScroll: true });
      scan.style.display = this.kind === "concept" ? "" : "none";
      propose.style.display = this.kind === "topic" ? "" : "none";
      statuses.style.display = this.kind === "source" ? "" : "none";
    };
    const propose = h("button", {
      class: "ghost",
      title: "Group the library's sources into topics, staged here for you to accept",
      onclick: async () => {
        clear(this.list, h("p", { class: "dim" }, "Asking the clerk to group the sources\u2026"));
        try {
          const out = await this.api.tool("topic_propose", {});
          if (out.error) throw new Error(String(out.detail ?? out.error));
          await this.load(true);
          const n = (out.proposed ?? []).length;
          this.list.prepend(h("p", { class: "note" }, out.detail ? String(out.detail) : `${n} topic${n === 1 ? "" : "s"} proposed from ${out.considered} sources.` + ((out.refile ?? []).length ? ` ${out.refile.length} source(s) fit a topic you already have.` : "")));
        } catch (e) {
          clear(this.list, h("p", { class: "error" }, e.message));
        }
      }
    }, "Propose topics");
    const scan = h("button", {
      class: "ghost",
      title: "Scan recorded term usages for a term seen across several sources",
      onclick: async () => {
        clear(this.list, h("p", { class: "dim" }, "Scanning term usages\u2026"));
        try {
          const out = await this.api.tool("concept_candidates", {});
          await this.load(true);
          const n = (out.staged ?? []).length;
          this.list.prepend(h("p", { class: "note" }, n ? `${n} new concept${n === 1 ? "" : "s"} staged.` : "Nothing new to stage."));
        } catch (e) {
          clear(this.list, h("p", { class: "error" }, e.message));
        }
      }
    }, "Scan for concepts");
    paint();
    this.paintKinds = paint;
    this.evidenceMode.value = preference("evidence", "beside");
    const layout = () => this.el.classList.toggle("lib-evidence-demand", this.evidenceMode.value === "demand");
    layout();
    this.evidenceMode.onchange = () => {
      remember("evidence", this.evidenceMode.value);
      layout();
      const evidence = this.detail.querySelector("details.lib-review-evidence");
      if (evidence) evidence.open = this.evidenceMode.value === "beside";
    };
    this.el.append(
      h("div", { class: "view-head" }, h("strong", {}, "Staging review"), kinds),
      h("p", { class: "note" }, "Review captured material before adding it to this library."),
      h(
        "div",
        { class: "view-head review-toolbar" },
        statuses,
        this.evidenceMode,
        h("button", { class: "ghost", onclick: () => void this.load(true) }, "Refresh"),
        scan,
        propose
      ),
      this.banner,
      this.bulk,
      h("div", { class: "split" }, this.list, this.detail)
    );
    this.bulk.hidden = true;
  }
  savePosition() {
    if (!this.restoredLibrary || this.resumeScroll !== null) return;
    try {
      sessionStorage.setItem("librarian.queue." + this.restoredLibrary, JSON.stringify({
        kind: this.kind,
        status: this.status,
        selected: this.selected,
        scroll: this.el.scrollTop
      }));
    } catch {
    }
  }
  restorePosition() {
    const key = this.libraryKey();
    if (!key || key === this.restoredLibrary) return;
    this.restoredLibrary = key;
    if (this.pending) return;
    try {
      const saved = JSON.parse(sessionStorage.getItem("librarian.queue." + key) ?? "null");
      if (!saved || !["source", "lens", "concept", "topic", "offering", "import"].includes(saved.kind) || !Array.from(this.statuses.options).some((option) => option.value === saved.status)) return;
      this.kind = saved.kind;
      this.statuses.value = this.status = saved.status;
      this.selected = String(saved.selected ?? "");
      this.resumeScroll = Number(saved.scroll) || 0;
      this.paintKinds();
    } catch {
    }
  }
  async finishRestore(ids) {
    if (this.resumeScroll === null) return;
    const scroll = this.resumeScroll;
    if (this.selected && ids.includes(this.selected)) {
      if (this.kind === "offering") await this.showOffering(this.selected);
      else await this.show(this.selected);
    } else this.selected = "";
    this.resumeScroll = null;
    this.el.scrollTop = scroll;
  }
  dispose() {
    this.stopped = true;
    window.clearTimeout(this.poll);
  }
  /** The bar over the list: how many are ticked, and what can be done with them. */
  paintBulk() {
    const status = this.bulkStatusFilter;
    const on = this.kind === "source" && (APPROVABLE.includes(status) || DEFERRABLE.includes(status));
    this.bulk.hidden = !on;
    if (!on) return;
    const n = this.picked.size;
    this.bulkCount.textContent = n ? `${n} ticked` : "Tick sources to decide several at once";
    this.bulkApprove.textContent = `Approve ${n || ""} ticked`.replace("  ", " ");
    this.bulkDefer.textContent = `Defer ${n || ""} ticked`.replace("  ", " ");
    this.bulkApprove.hidden = !APPROVABLE.includes(status);
    this.bulkDefer.hidden = this.bulkReason.hidden = !DEFERRABLE.includes(status);
    for (const button of [this.bulkApprove, this.bulkDefer, this.bulkClear]) button.disabled = n === 0;
  }
  /** Send each ticked source on its own, with the revision its row showed; report each. */
  async decideTicked(decision) {
    const ids = [...this.picked].filter((id) => this.rows.has(id));
    if (!ids.length) return;
    const reason = this.bulkReason.value.trim();
    if (decision === "defer" && !reason) {
      this.bulkStatus.textContent = "A deferral needs its reason.";
      this.bulkReason.focus();
      return;
    }
    for (const button of [this.bulkApprove, this.bulkDefer, this.bulkClear]) button.disabled = true;
    this.bulkStatus.textContent = `Sending ${ids.length}\u2026`;
    const done = [], changed = [], refused = [];
    for (const id of ids) {
      const row = this.rows.get(id) ?? {};
      const name = String(row.name || id);
      try {
        const out = await this.api.tool("staging_decide", {
          item_ids: [id],
          decision,
          ...decision === "defer" ? { reason } : {},
          ...row.staged_revision ? { staged_revision: row.staged_revision } : {}
        });
        const r = (out.results ?? [])[0] ?? out;
        if (out.refused === "DOCUMENT_ACTIVE") changed.push(name);
        else if (out.error || r.error || r.refused) {
          refused.push(`${name}: ${String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error)}`);
        } else done.push(name);
      } catch (e) {
        refused.push(`${name}: ${e.message}`);
      }
      this.picked.delete(id);
    }
    this.bulkStatus.textContent = "";
    if (decision === "defer" && !changed.length && !refused.length) this.bulkReason.value = "";
    await this.load();
    this.detailLocked = true;
    const verb = decision === "approve" ? "Approved" : "Deferred";
    clear(this.detail, h(
      "div",
      { class: "bulk-outcome", role: "status" },
      h("p", { class: done.length ? "ok" : "dim" }, `${verb} ${done.length} of ${ids.length}.` + (decision === "approve" && done.length ? " They wait for the batch above: nothing is in the library yet." : "")),
      done.length ? h("ul", {}, done.map((name) => h("li", {}, name))) : null,
      changed.length ? h("p", { class: "warn" }, `Changed since this list was shown, so left untouched: ${changed.join(", ")}. Open each to see what changed before deciding it.`) : null,
      refused.length ? h("p", { class: "error" }, "Not decided:") : null,
      refused.length ? h("ul", {}, refused.map((text) => h("li", {}, text))) : null
    ));
  }
  /** `reset`: an explicit visit (opening the view, Refresh, switching kind) —
   * always shows the placeholder when nothing is selected. Left false, an
   * automatic reload (another surface's decision arriving over the event
   * stream) refreshes the list without wiping a just-shown outcome message. */
  async load(reset = false) {
    this.restorePosition();
    const request = ++this.listRequest;
    if (reset) this.detailLocked = false;
    clear(this.list, h("p", { class: "dim" }, "Loading\u2026"));
    this.bulkStatusFilter = this.kind === "source" ? this.status : "";
    this.paintBulk();
    if (this.kind === "offering") return this.loadOfferings(request);
    try {
      const status = this.kind === "source" ? this.status : "staged";
      const out = await this.api.tool("staging_list", { kind: this.kind, status, limit: 50 });
      if (request !== this.listRequest || this.stopped) return;
      if (out.error) throw new Error(String(out.detail ?? out.error));
      this.counts = out.counts;
      this.paintKinds();
      if (this.waitingOfferings === void 0 || reset) {
        void this.api.get("/api/offerings/staged").then((data) => {
          if (request !== this.listRequest || this.stopped || !Array.isArray(data.offerings)) return;
          this.waitingOfferings = data.offerings.filter((row2) => row2.status !== "declined").length;
          this.paintKinds();
        }).catch(() => {
        });
      }
      const items = out.items ?? [];
      this.rows = new Map(items.map((item) => [String(item.id), item]));
      this.bulkStatusFilter = status;
      for (const id of [...this.picked]) if (!this.rows.has(id)) this.picked.delete(id);
      const ticking = this.kind === "source" && (APPROVABLE.includes(status) || DEFERRABLE.includes(status));
      this.list.setAttribute("role", ticking ? "list" : "listbox");
      const row = (item, button) => ticking ? h(
        "div",
        { class: "item-row", role: "listitem" },
        h("input", {
          type: "checkbox",
          "data-tick": item.id,
          checked: this.picked.has(String(item.id)),
          "aria-label": `Tick ${item.name || item.id}`,
          onchange: (event) => {
            const box = event.target;
            if (box.checked) this.picked.add(String(item.id));
            else this.picked.delete(String(item.id));
            this.bulkStatus.textContent = "";
            this.paintBulk();
          }
        }),
        button
      ) : button;
      this.paintBulk();
      clear(
        this.list,
        h("p", { class: "dim" }, `${out.total ?? items.length} ${status === "staged" ? "waiting" : status}`),
        items.length ? items.map((item) => row(item, h(
          "button",
          {
            "data-item": item.id,
            class: `item${item.id === this.selected ? " sel" : ""}`,
            ...ticking ? { "aria-current": item.id === this.selected ? "true" : void 0 } : { role: "option", "aria-selected": String(item.id === this.selected) },
            onclick: () => this.show(item.id)
          },
          item.sensitivity === "review" ? h("span", { class: "flag", title: "sensitive: a person decides" }, "\u2691 ") : null,
          item.name || item.id,
          h("small", {}, (item.kind === "lens" ? [item.source ? `from ${item.source}` : "", item.locator] : item.kind === "concept" ? [`${item.sources ?? 0} source${item.sources === 1 ? "" : "s"}`, `${item.usages ?? 0} usage${item.usages === 1 ? "" : "s"}`] : item.kind === "topic" ? [`${item.coverage?.sources ?? 0} of ${item.coverage?.of ?? 0} sources`, item.duplicate_of ? `close to ${item.duplicate_of}` : ""] : item.ref ? [item.failure ? `failed: ${item.failure.stage}` : "not yet fetched", item.note] : item.status === "enriched" || item.status === "partial" ? [item.topic, `coverage ${item.processing?.coverage ?? "?"}`] : item.status === "failed" ? [`failed at ${item.failure?.stage ?? "?"}`] : [
            item.topic,
            item.drafted ? "drafted" : item.reviewed ? "draft queued" : "no draft yet",
            item.deep_read ? `read ${item.deep_read}` : "",
            item.fit
          ]).filter(Boolean).join(" \xB7 "))
        ))) : h("p", { class: "dim" }, "Nothing here.")
      );
      await this.finishRestore(items.map((item) => item.id));
      if (!this.selected && !this.detailLocked) {
        clear(this.detail, h("p", { class: "dim" }, "Choose an item to see its draft beside its evidence."));
      }
    } catch (e) {
      clear(this.list, h("p", { class: "error" }, e.message));
    }
    void this.paintBanner();
  }
  /** Open one staged offering here (the chat's "Read the draft" on a promotion question). */
  focusOffering(id) {
    this.kind = "offering";
    this.selected = id;
    this.pending = id;
    this.paintKinds();
  }
  /** Offering drafts wait in staging/offerings/ until promoted: listed here so a person
   * reads one before answering "promote it?" (Test Report A2 b). Not staging items -
   * each belongs to the session that drafted it, and its decision is recorded there. */
  async loadOfferings(request) {
    try {
      const out = await this.api.get("/api/offerings/staged");
      if (request !== this.listRequest || this.stopped) return;
      const rows = out.offerings ?? [];
      const waiting = rows.filter((r) => r.status !== "declined").length;
      this.waitingOfferings = waiting;
      this.paintKinds();
      clear(
        this.list,
        h("p", { class: "dim" }, `${waiting} waiting${rows.length > waiting ? ` \xB7 ${rows.length - waiting} declined` : ""}`),
        rows.length ? rows.map((r) => h(
          "button",
          {
            "data-item": r.offering,
            class: `item${r.offering === this.selected ? " sel" : ""}`,
            role: "option",
            "aria-selected": String(r.offering === this.selected),
            onclick: () => void this.showOffering(r.offering)
          },
          r.challenged ? h("span", { class: "flag", title: "a claim the review challenged was kept: yours to weigh" }, "\u2691 ") : null,
          r.title,
          h("small", {}, [
            r.project || "Insights",
            `${r.claims} claim${r.claims === 1 ? "" : "s"}`,
            r.question ? "asked: promote?" : r.status === "declined" ? "declined" : "",
            r.session_status === "closed" ? "session closed" : ""
          ].filter(Boolean).join(" \xB7 "))
        )) : h("p", { class: "dim" }, "No offering waits to be promoted.")
      );
      await this.finishRestore(rows.map((row) => row.offering));
      if (this.pending) {
        const id = this.pending;
        this.pending = "";
        return this.showOffering(id);
      }
      if (!this.selected && !this.detailLocked) {
        clear(this.detail, h("p", { class: "dim" }, "Choose an offering to read it before deciding."));
      }
    } catch (e) {
      clear(this.list, h("p", { class: "error" }, e.message));
    }
    void this.paintBanner();
  }
  async showOffering(id) {
    this.selected = id;
    this.savePosition();
    this.detailLocked = false;
    this.list.querySelectorAll(sel(".item")).forEach((button) => {
      const selected = button.dataset.item === id;
      button.classList.toggle(cls("sel"), selected);
      if (button.getAttribute("role") === "option") button.setAttribute("aria-selected", String(selected));
      else if (selected) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    });
    clear(this.detail, h("p", { class: "dim" }, "Loading\u2026"));
    let r;
    try {
      r = await this.api.get(`/api/offerings/staged?id=${encodeURIComponent(id)}`);
    } catch (e) {
      clear(this.detail, h("p", { class: "error" }, e.message));
      return;
    }
    if (this.selected !== id || this.stopped) return;
    const status = h("div", { role: "status" });
    const decide = (d) => async () => {
      try {
        const out = await this.api.post("/api/offerings/decide", { id, decision: d });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h(
          "p",
          { class: "ok", role: "status" },
          out.resumed ? `${r.title}: answered - the session carries on and ${d === "promote" ? "promotes" : "declines"} it.` : out.promoted ? [`${r.title}: promoted to `, h("a", { href: "#", onclick: (e) => {
            e.preventDefault();
            this.openNote(String(out.promoted));
          } }, String(out.promoted)), out.findable === false ? " (not yet found by search)" : "", "."] : `${r.title}: declined. It stays here, and can still be promoted.`
        ));
      } catch (e) {
        clear(status, h("p", { class: "error" }, e.message));
      }
    };
    const review = r.review ?? {};
    const reviewed = ["holds", "unchecked", "queued"].filter((k) => review[k]).map((k) => `${review[k]} ${k}`);
    clear(
      this.detail,
      h("div", { class: "view-head" }, h("strong", {}, r.title)),
      h("p", { class: "dim" }, [
        r.kind.replace(/_/g, " "),
        r.created,
        `for ${r.project || "Insights"}`,
        `${r.claims} claim${r.claims === 1 ? "" : "s"}, each quote found in its source`,
        reviewed.length ? `review: ${reviewed.join(", ")}${review.by ? ` (${review.by})` : ""}` : "",
        `session ${r.session} (${r.session_status})`
      ].filter(Boolean).join(" \xB7 ")),
      r.challenged ? h("p", { class: "warn" }, `\u2691 ${r.challenged} claim${r.challenged === 1 ? "" : "s"} the review challenged ${r.challenged === 1 ? "was" : "were"} kept by the agent, with its reason - read ${r.challenged === 1 ? "it" : "them"} before promoting.`) : null,
      h("p", { class: "note" }, r.question ? "The session has asked you to promote this. Your choice here answers it." : r.status === "declined" ? "You declined this. It stays in staging; promoting it now still moves it into the library." : "The session has not asked yet. Promoting moves it into the library now."),
      h("div", { class: "offering-body" }, render(String(r.text ?? ""), this.openNote, { frontmatter: true })),
      h(
        "div",
        { class: "row2 tight" },
        h("button", { class: "primary", onclick: decide("promote") }, "Promote into the library"),
        r.status === "declined" ? null : h("button", { class: "ghost", onclick: decide("decline") }, "Decline")
      ),
      status
    );
  }
  /** Approving a source only queues it: a person begins the batch here, and nothing
   * else starts it (Research Pipeline §4.2). The count is the approved set not yet
   * started; while a batch runs, later approvals are counted apart, for the next run. */
  async focusBatch(id) {
    await this.paintBanner();
    const button = this.banner.querySelector(`[data-command="${id}"]`);
    if (button) {
      button.focus();
      return;
    }
    this.banner.append(h("p", { class: "note" }, "This batch action is unavailable for the current queue."));
  }
  async paintBanner() {
    let b;
    try {
      b = await this.api.tool("batch_status", {});
    } catch {
      clear(this.banner);
      return;
    }
    if (this.stopped) return;
    const waiting = Number(b.waiting ?? 0);
    const running = b.status === "running";
    const start2 = (id, label, args, cls2 = "primary") => h("button", { class: cls2, "data-command": id, onclick: async (e) => {
      const button = e.currentTarget;
      button.disabled = true;
      try {
        const out = await this.api.tool("process_approved", { ...args, background: true });
        if (out.error || out.refused) throw new Error(String(out.detail ?? out.refused ?? out.error));
      } catch (err) {
        this.banner.append(h("p", { class: "error" }, err.message));
        button.disabled = false;
        return;
      }
      this.onBatch("start");
      void this.paintBanner();
    } }, label);
    const rows = [];
    if (running) {
      const cur = b.current ?? {};
      rows.push(h(
        "div",
        { class: "row2 tight" },
        h(
          "span",
          {},
          h("strong", {}, `Processing ${b.processed ?? 0} of ${b.total ?? 0}`),
          cur.item ? ` \xB7 ${cur.item}: ${cur.stage}${cur.detail ? ` - ${cur.detail}` : ""}` : ""
        ),
        h("button", { class: "ghost", "data-command": "stop", onclick: async (e) => {
          const button = e.currentTarget;
          button.disabled = true;
          try {
            const result = await this.api.tool("batch_cancel", {});
            if (result.error || result.refused) throw Error(String(result.detail ?? result.error ?? result.refused));
            await this.paintBanner();
          } catch (err) {
            button.disabled = false;
            this.banner.append(h("p", { class: "error" }, err.message));
          }
        } }, "Stop after this stage")
      ));
      if (waiting) rows.push(h("p", { class: "note inline" }, `${waiting} more approved, waiting for the next run.`));
    } else {
      const unfinished = (b.items ?? []).some((i) => i.status === "processing");
      if (b.status === "failed") {
        rows.push(h(
          "p",
          { class: "error" },
          `Batch processing stopped: ${b.detail ?? "review the unfinished source before resuming"}.`
        ));
      }
      if (unfinished && ["interrupted", "cancelled", "failed"].includes(b.status)) {
        rows.push(h(
          "div",
          { class: "row2 tight" },
          h("span", {}, `The last batch stopped${b.detail ? ` (${b.detail})` : ""} with sources unfinished.`),
          start2("resume", "Resume it", { resume: b.run }, "ghost")
        ));
      }
      if (waiting) {
        rows.push(h(
          "div",
          { class: "row2 tight" },
          h("strong", {}, waiting === 1 ? "1 source approved and awaiting ingestion." : `${waiting} sources approved and awaiting ingestion.`),
          start2("approved", "Process approved sources", {})
        ));
      }
      const onModel = Number(b.waiting_on_model ?? 0);
      if (onModel) {
        rows.push(h(
          "div",
          { class: "row2 tight" },
          h("span", {}, `${onModel} source${onModel === 1 ? " has" : "s have"} reading steps that waited for a model. With models chosen (Choose models), run just those steps:`),
          start2("retry", "Run the waiting steps", { retry_waiting: true }, "ghost")
        ));
      }
    }
    if (rows.length && !running) rows.push(h("small", { class: "note" }, this.routeHint() + " Estimated cost and total content sent are unknown before the run."));
    if (this.wasRunning && !running && b.status === "finished") this.onBatch("finish");
    clear(this.banner, rows.length ? h("div", { class: "warn" }, rows) : null);
    window.clearTimeout(this.poll);
    if (running) this.poll = window.setTimeout(() => void this.paintBanner(), 2e3);
    else if (this.wasRunning && this.kind === "source") void this.load();
    this.wasRunning = running;
  }
  decisionError(status, id, error) {
    clear(
      status,
      h("p", { class: "error" }, error.message),
      h(
        "button",
        { class: "ghost", onclick: () => this.show(id) },
        "Reload item (discards form edits)"
      )
    );
  }
  async show(id) {
    this.selected = id;
    this.savePosition();
    this.detailLocked = false;
    this.list.querySelectorAll(sel(".item")).forEach((button) => {
      const selected = button.dataset.item === id;
      button.classList.toggle(cls("sel"), selected);
      if (button.getAttribute("role") === "option") button.setAttribute("aria-selected", String(selected));
      else if (selected) button.setAttribute("aria-current", "true");
      else button.removeAttribute("aria-current");
    });
    clear(this.detail, h("p", { class: "dim" }, "Loading\u2026"));
    let item;
    try {
      item = await this.api.tool("staging_show", { item_id: id });
      if (item.error) throw new Error(String(item.detail ?? item.error));
    } catch (e) {
      clear(this.detail, h("p", { class: "error" }, e.message));
      return;
    }
    if (this.stopped || this.selected !== id) return;
    if (item.kind === "lens") return this.showLens(item);
    if (item.kind === "concept") return this.showConcept(item);
    if (item.kind === "topic") return this.showTopic(item);
    if (item.kind === "import") return this.showImport(item);
    if (item.ref && (item.status === "queued" || item.status === "failed")) return this.showQueued(item);
    const draft = item.review?.draft ?? {};
    const bottom = h("textarea", { class: "f", id: "lib-bl", placeholder: "One or two sentences: what this is, from the evidence." });
    bottom.value = draft.bottom_line ?? "";
    const solves = h("textarea", { class: "f short", id: "lib-solves", placeholder: "What problem it solves, for whom." });
    solves.value = draft.what_it_solves ?? "";
    const reason = h("input", { type: "text", placeholder: "Reason (for a rejection or deferral)", "aria-label": "Reason" });
    const status = h("div", { role: "status" });
    const isModel = item.source_kind === "model";
    const bestFor = new Set(item.fields?.best_for ?? []);
    let suggestedTier = item.fields?.suggested_tier ?? "";
    const bestForButtons = BEST_FOR_TAGS.map((tag) => {
      const btn2 = h("button", {
        type: "button",
        "aria-pressed": String(bestFor.has(tag)),
        onclick: () => {
          if (bestFor.has(tag)) bestFor.delete(tag);
          else bestFor.add(tag);
          btn2.setAttribute("aria-pressed", String(bestFor.has(tag)));
        }
      }, untag(tag));
      return btn2;
    });
    const tierButtons = TIERS.map((t) => h("button", {
      type: "button",
      "aria-pressed": String(suggestedTier === t),
      onclick: () => {
        suggestedTier = t;
        tierButtons.forEach((b, i) => b.setAttribute("aria-pressed", String(TIERS[i] === t)));
      }
    }, untag(t)));
    const decide = (decision) => async () => {
      try {
        const out = await this.api.tool("staging_decide", {
          item_ids: [id],
          decision,
          reason: reason.value,
          ...item.revision ? { revision: item.revision } : {},
          ...item.staged_revision ? { staged_revision: item.staged_revision } : {},
          bottom_line: bottom.value,
          what_it_solves: solves.value,
          ...isModel ? { fields: {
            ...!item.promotion_progress || item.fields?.best_for !== void 0 || bestFor.size ? { best_for: Array.from(bestFor) } : {},
            ...suggestedTier ? { suggested_tier: suggestedTier } : {}
          } } : {}
        });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        const outcome = decision === "accept" ? (r.merged_into ? `Merged ${(r.sections ?? []).join(", ") || "its sections"} into ${r.merged_into}; the previous text is kept on this item.` : r.promotion && !r.promotion.catalogued ? `Accepted: ${r.promotion.status}.` : `Accepted into the library and catalogued (coverage: ${r.coverage ?? "unknown"}).`) + (r.handoff ? " It joins your session as an undecided candidate." : "") + (r.originals_retained?.length ? " Attachments were copied; originals remain in place." : "") + (r.handoff_warning ? " Session handoff was not recorded; the library decision remains saved. Review the original session." : "") : decision === "approve" ? "Approved for ingestion: it waits for the batch above. Nothing is in the library yet." : decision === "reject" ? "Rejected." : "Deferred.";
        this.selected = "";
        if (r.session && r.session.session === this.currentSession()) this.onSessionUpdate(r.session);
        await this.load();
        this.detailLocked = true;
        clear(
          this.detail,
          h("p", { class: "ok", role: "status" }, `${item.name}: ${outcome}`),
          (r.embedding_warnings ?? []).map((w) => h("p", { class: "warn" }, `Derived embeddings \xB7 ${w.stage}: ${w.error}. ${w.next}`))
        );
      } catch (e) {
        this.decisionError(status, id, e);
      }
    };
    const draftIt = async () => {
      clear(status, h("p", { class: "dim" }, "Asking the clerk for an unframed draft\u2026"));
      try {
        const out = await this.api.tool("staging_review", { item_id: id });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        if (out.draft?.status === "queued") clear(status, h("p", { class: "dim" }, "Queued: no clerk model is available. Choose a tier 3 model, or run the clerk agent."));
        else await this.show(id);
      } catch (e) {
        clear(status, h("p", { class: "error" }, e.message));
      }
    };
    const readIt = async () => {
      clear(status, h("p", { class: "dim" }, "Reading the whole text, part by part\u2026"));
      try {
        const out = await this.api.tool("deep_read", { item_id: id });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        await this.show(id);
        const lensNote = out.lenses_staged?.length ? ` ${out.lenses_staged.length} lens${out.lenses_staged.length === 1 ? "" : "es"} staged for review under Lenses.` : "";
        const waitNote = out.waiting_on_clerk ? ` ${out.waiting_on_clerk} part${out.waiting_on_clerk === 1 ? "" : "s"} waiting on a clerk model.` : "";
        this.detail.querySelector("[role=status]")?.replaceChildren(h(
          "p",
          { class: "ok" },
          `Read ${out.read} of ${out.chunks} parts.${lensNote}${waitNote}`
        ));
        void this.load();
      } catch (e) {
        clear(status, h("p", { class: "error" }, e.message));
      }
    };
    const dr = item.deep_read;
    const readCount = dr ? Object.keys(dr.read ?? {}).length : 0;
    const readLine = !dr ? "Only the opening of this source has been read." : dr.version !== 2 ? "Deep read: earlier progress recorded only how many parts were read, not which text, so it is stale. Deep read again to read the text as it is now." : `Deep read: ${readCount} of ${dr.chunks} parts read${dr.lenses?.length ? `, ${dr.lenses.length} lens${dr.lenses.length === 1 ? "" : "es"} staged` : ""}.`;
    const sections = Object.entries(item.sections ?? {}).filter(([, t]) => t);
    const queued = item.review?.queued ?? [];
    const missing = item.readiness ?? [];
    const st = String(item.status ?? "staged");
    const btn = (label, d, cls2 = "ghost", title = "") => h("button", { class: cls2, onclick: decide(d), ...title ? { title } : {} }, label);
    const proc = item.processing ?? {};
    const interrupted = item.promotion_progress && !item.promotion_progress.completed_at;
    const buttons = interrupted ? [btn("Finish acceptance", "accept", "primary"), btn("Reject", "reject"), btn("Defer", "defer")] : item.revision_of ? [btn("Accept", "accept", "primary"), btn("Reject", "reject"), btn("Defer", "defer")] : st === "enriched" ? [btn("Accept into library", "accept", "primary"), btn("Reject", "reject"), btn("Defer", "defer")] : st === "partial" ? [
      btn("Approve for ingestion again", "approve", "primary", "Runs only the unfinished stages; finished ones are kept"),
      btn("Accept with partial coverage", "accept", "ghost", "The note records its coverage and what was not examined"),
      btn("Reject", "reject"),
      btn("Defer", "defer")
    ] : st === "approved" ? [btn("Reject", "reject"), btn("Defer", "defer", "ghost", "Take it out of the waiting batch")] : st === "processing" ? [] : st === "failed" ? [btn("Approve for ingestion again", "approve", "primary"), btn("Reject", "reject")] : [
      btn("Approve for ingestion", "approve", "primary", "Read it in full and review it in the next batch, then accept it"),
      btn("Reject", "reject"),
      btn("Defer", "defer"),
      btn("Accept as captured", "accept", "ghost", "Catalogue it now from what capture read, without ingesting it; the note records coverage: captured")
    ];
    const stage = st === "approved" ? h("p", { class: "note" }, "Approved for ingestion: it waits for the batch (the banner above). Nothing is in the library yet.") : st === "processing" ? h("p", { class: "note" }, `Being ingested in ${item.batch ?? "a batch"}.`) : st === "enriched" || st === "partial" ? h(
      "div",
      {},
      h("p", { class: "note" }, st === "enriched" ? `Ingested in ${proc.run ?? "a batch"}: every stage complete, coverage ${proc.coverage ?? "unknown"}.` : `Ingested in ${proc.run ?? "a batch"} with gaps: coverage ${proc.coverage ?? "unknown"}. Approve it again to run only what is unfinished, or accept it as it is - its note will say what was not examined.`),
      (proc.not_examined ?? []).length ? h("p", { class: "warn" }, `Not examined: ${proc.not_examined.join("; ")}.`) : null
    ) : st === "staged" || st === "deferred" ? h("p", { class: "note" }, "Captured: only what intake fetched has been read.") : st === "failed" && item.failure ? h("p", { class: "warn" }, `Ingestion failed at ${item.failure.stage}: ${item.failure.reason}`) : null;
    const intakeInfo = item.intake ?? {};
    const q = intakeInfo.quality ?? {};
    const ledger = (stages) => Object.entries(stages ?? {}).map(([k, v]) => `${k}: ${v}`).join(" \xB7 ");
    const capture = h(
      "div",
      {},
      Object.keys(intakeInfo.stages ?? {}).length ? h("p", { class: "dim" }, `Capture \u2014 ${ledger(intakeInfo.stages)}`) : null,
      Object.keys(proc.stages ?? {}).length ? h("p", { class: "dim" }, `Batch \u2014 ${ledger(proc.stages)}`) : null,
      q.verdict && q.verdict !== "usable" ? h("p", { class: "warn" }, `${q.reason}. Next: ${q.next}.`) : null,
      item.possible_duplicate_of ? h("p", { class: "warn" }, `Possibly the same work as ${item.possible_duplicate_of}.`) : null,
      item.fit_screen ? h(
        "p",
        { class: "note" },
        `Screened against ${item.found_for?.brief ?? "its brief"}: `,
        h("strong", {}, String(item.fit_screen.verdict ?? item.fit_screen.status ?? "")),
        item.fit_screen.reason ? ` \u2014 ${item.fit_screen.reason}` : "",
        " (a fit judgement, kept apart from the description)"
      ) : null
    );
    clear(
      this.detail,
      h(
        "div",
        { class: "view-head" },
        h("strong", {}, item.name),
        item.canonical_url ? h("a", { href: item.canonical_url, target: "_blank", rel: "noreferrer noopener" }, "source \u2197") : null
      ),
      item.sensitivity === "review" ? h("p", { class: "warn" }, "\u2691 Marked sensitive: only a person accepts it, and only a person clears the mark.") : null,
      stage,
      st === "staged" && !item.revision_of ? h("p", { class: "note" }, "Approve for ingestion queues a full read. Accept as captured publishes the current material with its limited coverage.") : null,
      interrupted ? h(
        "div",
        { class: "warn", role: "note" },
        h("p", {}, "Acceptance was interrupted. Review the completed work before finishing with the same approved content. Changed content needs a source revision, not an overwrite."),
        h("p", {}, `Completed paths: ${(item.promotion_progress.completed_paths ?? []).join(", ") || "inspect the operation log"}.`),
        item.promotion_progress.source?.path ? h("a", { class: "wl", href: "#", onclick: (e) => {
          e.preventDefault();
          this.openNote(item.promotion_progress.source.path);
        } }, item.promotion_progress.source.path) : null,
        h("p", {}, "Original attachments remain in place. Rejecting or deferring does not undo completed copies or notes.")
      ) : null,
      !item.revision_of && (item.file || item.clean_file) ? h(
        "p",
        { class: "note" },
        "Accepting this source copies attachments to managed Sources files; original project files stay in place."
      ) : null,
      capture,
      item.revision_of ? h(
        "p",
        { class: "note" },
        "A revision of an accepted note, ",
        h("a", { class: "wl", href: "#", onclick: (e) => {
          e.preventDefault();
          this.openNote(item.revision_of);
        } }, item.revision_of),
        item.revision_kind === "dik" ? `: its Data and Information records rebuilt. Accepting adds ${Object.keys(item.sections ?? {}).join(", ")} to that note, each labelled with where its claims come from; the note's own prose is untouched (the previous text is kept on this item). Rejecting leaves the note as it is.` : ": its whole text read. Accepting merges its Claims and Evidence & Limits into that note (the previous text is kept on this item); rejecting leaves the note as it is."
      ) : null,
      queued.length ? h(
        "p",
        { class: "warn" },
        `\u23F3 Waiting on a clerk model for: ${queued.join(", ")}. Choose a tier 3 model under Model, `,
        h("button", { class: "ghost", onclick: this.openModels }, "Configure reviewer model")
      ) : null,
      (item.intake_notes ?? []).length ? h("p", { class: "note" }, `Intake could not read everything: ${item.intake_notes.join("; ")}.`) : null,
      missing.length ? h("p", { class: "warn" }, `Still missing before this is catalogued fully: ${missing.join(", ")}.`) : null,
      h(
        "div",
        { class: "columns" },
        h(
          "div",
          {},
          h("label", { class: "f", for: "lib-bl" }, interrupted ? "Bottom Line (previously approved; review it)" : draft.bottom_line ? `Bottom Line (drafted by ${draft.model || "the clerk"}; edit it)` : "Bottom Line"),
          bottom,
          h("label", { class: "f", for: "lib-solves" }, "What it solves"),
          solves,
          isModel ? h(
            "div",
            {},
            h("label", { class: "f" }, "Best for (a clerk's first guess; confirm or correct it)"),
            h("div", { class: "seg", role: "group", "aria-label": "Best for" }, bestForButtons),
            h("label", { class: "f" }, "Suggested tier (a first guess)"),
            h("div", { class: "seg", role: "group", "aria-label": "Suggested tier" }, tierButtons)
          ) : null,
          (draft.dropped ?? []).length ? h("p", { class: "note" }, `Dropped from the draft as ungrounded: ${draft.dropped.join("; ")}`) : null,
          reason,
          h(
            "div",
            { class: "row2" },
            buttons,
            st === "processing" || interrupted ? null : h("button", { class: "ghost push", onclick: draftIt }, draft.bottom_line ? "Redraft" : "Draft with the clerk")
          ),
          h(
            "div",
            { class: "row2" },
            h("span", { class: "note inline" }, readLine),
            st !== "processing" && !interrupted && (!dr || readCount < dr.chunks) ? h(
              "button",
              { class: "ghost", onclick: readIt, title: "Claims and limits from every part, with pages; terms; and any reasoning stance the text teaches, staged as a lens" },
              dr ? "Continue deep read" : "Deep read"
            ) : null
          ),
          status
        ),
        h(
          "details",
          { class: "review-evidence", open: this.evidenceMode.value === "beside" },
          h("summary", {}, "View source evidence"),
          sections.length ? h("label", { class: "f" }, "What was read") : null,
          sections.length ? h("div", { class: "sections" }, sections.map(([heading, body]) => h("section", {}, h("h4", {}, heading), render(body, this.openNote)))) : null,
          h("label", { class: "f" }, "Evidence"),
          h("pre", { class: "evidence" }, String(item.evidence_text ?? ""))
        )
      )
    );
  }
  showLens(item) {
    const p = { ...item.proposal ?? {}, ...item };
    const origin = p.provenance ?? {};
    const ORIGIN_LABEL = {
      source: "from the source",
      model: "drafted by the model",
      pack: "written by the pack's author",
      person: "edited by you",
      "model+source": "drafted by the model, each with a source quote",
      "pack+source": "written by the pack's author, each with a source quote"
    };
    const head = (label, field) => h(
      "h4",
      {},
      label,
      origin[field] ? h("span", { class: `origin origin-${origin[field].replace("+", "-")}` }, ORIGIN_LABEL[origin[field]] ?? origin[field]) : null
    );
    const list2 = (label, items, field = "") => items?.length ? h("div", {}, head(label, field), h("ul", {}, items.map((t) => h("li", {}, t)))) : null;
    const groundedList = (label, items, field = "") => items?.length ? h("div", {}, head(label, field), h("ul", {}, items.map((it) => h(
      "li",
      {},
      it.what ?? it.question ?? "",
      it.because ? h("blockquote", { class: "lens-quote small" }, it.because) : null,
      it.confirmed_by ? h(
        "p",
        { class: "note" },
        "Answered elsewhere in the text: ",
        it.confirmed_by.claim,
        it.confirmed_by.locator ? ` (${it.confirmed_by.locator})` : ""
      ) : null
    )))) : null;
    const quotes = p.quotes?.length ? p.quotes : p.source_quote ? [{ quote: p.source_quote, locator: p.locator }] : [];
    const inContext = (q) => h(
      "blockquote",
      { class: "lens-quote" },
      q.before ? h("span", { class: "quote-context" }, `\u2026${q.before}`) : null,
      h("mark", {}, q.quote),
      q.after ? h("span", { class: "quote-context" }, `${q.after}\u2026`) : null,
      q.locator ? h("cite", {}, ` \u2014 ${q.locator}`) : null
    );
    const trace = Object.entries(p.trace ?? {});
    const reason = h("input", {
      type: "text",
      placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason"
    });
    const status = h("div", { role: "status" });
    const editable = [
      ["name", "Name", false],
      ["catches", "The failure it catches", true],
      ["applies_when", "Applies when", true],
      ["not_when", "Not when", true],
      ["prompt_fragment", "The instruction a model would adopt", true],
      ["materials", "Material tags (comma-separated: paper, repository\u2026)", false],
      ["tasks", "Task tags (comma-separated: assess, design, debug\u2026)", false]
    ];
    const initial = (key) => Array.isArray(p[key]) ? p[key].join(", ") : String(p[key] ?? "");
    const inputs = editable.map(([key, label, long]) => {
      const el = long ? h("textarea", { class: "f", rows: key === "prompt_fragment" ? 4 : 2 }) : h("input", { type: "text", class: "f" });
      el.value = initial(key);
      el.id = `lens-edit-${key}`;
      return { key, el, row: h("div", {}, h("label", { class: "f", for: el.id }, label), el) };
    });
    const edits = () => Object.fromEntries(inputs.filter((i) => i.el.value.trim() !== initial(i.key).trim()).map((i) => [i.key, i.el.value.trim()]));
    const decide = (d) => async () => {
      try {
        const changed = d === "accept" ? edits() : {};
        const out = await this.api.tool("staging_decide", {
          item_ids: [item.id],
          decision: d,
          reason: reason.value,
          ...item.staged_revision ? { staged_revision: item.staged_revision } : {},
          ...Object.keys(changed).length ? { fields: changed } : {}
        });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h(
          "p",
          { class: "ok", role: "status" },
          `${p.name}: ${d === "accept" ? "accepted into the lens store" : d === "reject" ? "rejected" : "deferred"}.`
        ));
      } catch (e) {
        this.decisionError(status, item.id, e);
      }
    };
    const source = p.source ? h("a", { class: "wl", href: "#", onclick: (e) => {
      e.preventDefault();
      this.openNote(p.source);
    } }, p.source) : "an unknown source";
    clear(
      this.detail,
      h("div", { class: "view-head" }, h("strong", {}, p.name ?? item.id)),
      h(
        "p",
        {},
        "A reasoning stance drawn from ",
        source,
        quotes.length > 1 ? ` (${quotes.length} passages)` : p.locator ? ` (${p.locator})` : "",
        "."
      ),
      p.level === "document" ? h(
        "div",
        { class: "note" },
        h("p", {}, "Drawn from the whole text, not one passage: it rests on these claims from different parts."),
        h("ul", {}, (p.rests_on ?? []).map((r) => h("li", {}, r)))
      ) : null,
      origin.quotes ? h(
        "p",
        { class: "dim small" },
        "The passage(s) - ",
        h("span", { class: "origin origin-source" }, "from the source"),
        "; highlighted within the text around them."
      ) : null,
      ...quotes.map(inContext),
      p.topic_warning ? h("p", { class: "note err" }, "No situation outside the source's own subject survived as a transfer: this may be a topic rather than a reusable stance.") : null,
      p.challenge?.verdict ? h("p", { class: "note" }, `Challenge: ${p.challenge.verdict}${p.challenge.reason ? ` \u2014 ${p.challenge.reason}` : ""}`) : null,
      p.resembles ? h("p", { class: "note" }, `Resembles a lens you already accepted: ${p.resembles.name}. Reject this one if it adds nothing.`) : null,
      p.perspective ? h("div", {}, head("The stance", "perspective"), h("p", {}, p.perspective)) : null,
      groundedList("Weighs", p.attends_to, "attends_to"),
      list2("Lets fade", p.deprioritizes, "deprioritizes"),
      p.role_purpose ? h("div", {}, head("As a role", "role_purpose"), h("p", {}, p.role_purpose)) : null,
      list2("Brings", p.role_capabilities, "role_capabilities"),
      list2("Expected of it", p.role_expectations, "role_expectations"),
      list2("Also fits", p.transfers_to, "transfers_to"),
      groundedList("Ask this of a similar artifact", p.probes, "probes"),
      p.catches ? h("div", {}, head("The failure this catches", "catches"), h("p", {}, p.catches)) : null,
      p.applies_when || p.not_when ? h(
        "div",
        {},
        head("When to reach for it", p.applies_when ? "applies_when" : "not_when"),
        p.applies_when ? h("p", {}, "Applies when: ", p.applies_when) : null,
        p.not_when ? h("p", {}, "Not when: ", p.not_when) : null
      ) : null,
      p.prompt_fragment ? h(
        "div",
        {},
        head("The instruction a model would adopt", "prompt_fragment"),
        h("blockquote", { class: "lens-instruction" }, p.prompt_fragment)
      ) : null,
      trace.length ? h(
        "details",
        {},
        h("summary", {}, "How this was drafted"),
        h("ul", {}, trace.map(([step, model]) => h("li", {}, `${step}: `, h("code", {}, model || "unknown model"))))
      ) : null,
      h("p", { class: "note" }, "Check the stance is really in the quoted passage(s) before accepting it."),
      h("details", {}, h("summary", {}, "Edit before accepting"), inputs.map((i) => i.row)),
      reason,
      h(
        "div",
        { class: "row2" },
        h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer")
      ),
      status,
      h(
        "details",
        {},
        h("summary", {}, "The raw proposal"),
        h("pre", { class: "evidence" }, JSON.stringify(item.proposal ?? item, null, 1))
      )
    );
  }
  showConcept(item) {
    const usages = item.usages ?? [];
    const sources = item.sources ?? [];
    const definition = h("textarea", {
      class: "f",
      id: "lib-def",
      placeholder: "In your own words: what this term or pattern means. Never drafted for you."
    });
    const kindSel = h(
      "select",
      { "aria-label": "Concept kind" },
      h("option", { value: "term" }, "term"),
      h("option", { value: "pattern" }, "pattern")
    );
    const imported = item.imported;
    const aliases = h("input", {
      type: "text",
      placeholder: "Aliases, comma-separated (optional)",
      "aria-label": "Aliases"
    });
    const related = h("input", {
      type: "text",
      placeholder: "Related concepts, comma-separated (optional)",
      "aria-label": "Related"
    });
    const reason = h("input", {
      type: "text",
      placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason"
    });
    const status = h("div", { role: "status" });
    const split = (v) => v.split(",").map((s) => s.trim()).filter(Boolean);
    if (imported) {
      definition.value = imported.definition ?? "";
      kindSel.value = imported.concept_kind ?? "term";
      aliases.value = (imported.aliases ?? []).join(", ");
      related.value = (imported.related ?? []).join(", ");
    }
    const decide = (d) => async () => {
      if (d === "accept" && !definition.value.trim()) {
        clear(status, h("p", { class: "error" }, "A Definition, in your own words, is needed to accept a concept."));
        return;
      }
      try {
        const out = await this.api.tool("staging_decide", {
          item_ids: [item.id],
          decision: d,
          reason: reason.value,
          ...item.staged_revision ? { staged_revision: item.staged_revision } : {},
          ...d === "accept" ? { fields: {
            definition: definition.value,
            concept_kind: kindSel.value,
            aliases: split(aliases.value),
            related: split(related.value)
          } } : {}
        });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h(
          "p",
          { class: "ok", role: "status" },
          `${item.name}: ${d === "accept" ? "accepted as a Concept note" : d === "reject" ? "rejected" : "deferred"}.`
        ));
      } catch (e) {
        this.decisionError(status, item.id, e);
      }
    };
    clear(
      this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name ?? item.id)),
      h(
        "p",
        {},
        `Seen across ${sources.length} source${sources.length === 1 ? "" : "s"}: `,
        sources.flatMap((s, i) => [i ? ", " : "", h("a", {
          class: "wl",
          href: "#",
          onclick: (e) => {
            e.preventDefault();
            this.openNote(s);
          }
        }, s)])
      ),
      h("h4", {}, "Usages"),
      h("ul", {}, usages.map((u) => h(
        "li",
        {},
        h("blockquote", { class: "lens-quote small" }, u.sentence),
        h("cite", {}, ` \u2014 ${u.source}`)
      ))),
      h("p", { class: "note" }, "Nothing above is drafted: the Definition below is your own words, the one part of a concept note this catalogue never writes for you."),
      h("label", { class: "f", for: "lib-def" }, "Definition"),
      definition,
      h("label", { class: "f" }, "Kind"),
      kindSel,
      aliases,
      related,
      reason,
      h(
        "div",
        { class: "row2" },
        h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer")
      ),
      status
    );
  }
  /** A proposed topic, as the library's own sources suggest it (R8). It is reviewed here;
   * accepting, renaming or merging it into the taxonomy is done in Settings → Library. */
  /** V1's Applications and branch offerings: the note as V1 wrote it, into its V2 folder. */
  showImport(item) {
    const reason = h("input", {
      type: "text",
      placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason"
    });
    const status = h("div", { role: "status" });
    const decide = (d) => async () => {
      try {
        const out = await this.api.tool("staging_decide", {
          item_ids: [item.id],
          decision: d,
          reason: reason.value,
          ...item.staged_revision ? { staged_revision: item.staged_revision } : {}
        });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h(
          "p",
          { class: "ok", role: "status" },
          `${item.name}: ${d === "accept" ? `written to ${item.target}` : d === "reject" ? "rejected" : "deferred"}.`
        ));
      } catch (e) {
        this.decisionError(status, item.id, e);
      }
    };
    clear(
      this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name ?? item.id)),
      h("p", { class: "dim" }, `From V1 ${item.imported_from?.path ?? ""} - accepting writes it to ${item.target}, as V1 wrote it. V1's whole note is also kept as evidence.`),
      h("pre", { class: "import-body" }, String(item.body ?? "").slice(0, 4e3)),
      reason,
      h(
        "div",
        { class: "row2 tight" },
        h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer"),
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject")
      ),
      status
    );
  }
  showTopic(item) {
    const reason = h("input", {
      type: "text",
      placeholder: "Reason (for a rejection or deferral)",
      "aria-label": "Reason"
    });
    const status = h("div", { role: "status" });
    const decide = (d) => async () => {
      try {
        const out = await this.api.tool("staging_decide", { item_ids: [item.id], decision: d, reason: reason.value });
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.error ?? out.detail ?? out.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" }, `${item.name}: ${d === "reject" ? "rejected" : "deferred"}.`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, e.message));
      }
    };
    const members = item.members ?? [];
    clear(
      this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.name)),
      h("p", {}, item.what_belongs ?? ""),
      item.acceptance_progress ? h(
        "p",
        { class: "warn" },
        `Partly applied. Completed: ${(item.acceptance_progress.completed_paths ?? []).join(", ")}. Finish acceptance in Settings \u2192 Library after review. Rejecting or deferring does not undo those writes.`
      ) : null,
      item.duplicate_of ? h("p", { class: "warn" }, `Close to a topic you already have: ${item.duplicate_of}. Merge rather than add?`) : null,
      h("p", { class: "dim" }, `${item.coverage?.sources ?? members.length} of the ${item.coverage?.of ?? "?"} sources considered \xB7 proposed by ${item.proposed_by ?? "the clerk"}`),
      (item.aliases ?? []).length ? h("p", {}, h("strong", {}, "Also called: "), item.aliases.join(", ")) : null,
      h("h4", {}, "Sources it would hold"),
      h("p", {}, members.flatMap((s, i) => [i ? ", " : "", h("a", {
        class: "wl",
        href: "#",
        onclick: (e) => {
          e.preventDefault();
          this.openNote(s);
        }
      }, s)])),
      h("p", { class: "note" }, "A proposal only: the topic list changes when you accept, rename or merge it in Settings \u2192 Library."),
      reason,
      h(
        "div",
        { class: "row2" },
        h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
        h("button", { class: "ghost", onclick: decide("defer") }, "Defer")
      ),
      status
    );
  }
  /** A reference in the intake queue, not yet fetched, or whose capture failed (R7). */
  showQueued(item) {
    const reason = h("input", { type: "text", placeholder: "Why remove it", "aria-label": "Reason" });
    const status = h("div", { role: "status" });
    const act = (tool, args, done) => async () => {
      try {
        const out = await this.api.tool(tool, args);
        const r = (out.results ?? [])[0] ?? out;
        if (out.error || r.error) throw new Error(String(r.error ?? out.detail ?? out.error));
        this.selected = "";
        await this.load();
        this.detailLocked = true;
        clear(this.detail, h("p", { class: "ok", role: "status" }, `${item.ref}: ${done}`));
      } catch (e) {
        clear(status, h("p", { class: "error" }, e.message));
      }
    };
    const remove = () => reason.value.trim() ? act("queue_remove", { item_ids: [item.id], reason: reason.value }, "removed; kept in quarantine with your reason.")() : clear(status, h("p", { class: "error" }, "Say why it is removed."));
    const f = item.found_for ?? {};
    clear(
      this.detail,
      h("div", { class: "view-head" }, h("strong", {}, item.ref)),
      h("p", {}, item.status === "failed" ? "Its capture failed: nothing was fetched." : "Queued for capture: not yet fetched."),
      item.failure ? h("p", { class: "warn" }, `${item.failure.stage}: ${item.failure.reason}`) : null,
      item.note ? h("p", {}, h("strong", {}, "Why: "), item.note) : null,
      h("p", { class: "dim" }, [
        item.requested_by ? `asked by ${item.requested_by}` : "",
        f.session ? `for ${f.session}${f.brief ? ` / ${f.brief}` : ""}` : "",
        item.queued_at ? `queued ${String(item.queued_at).slice(0, 10)}` : ""
      ].filter(Boolean).join(" \xB7 ")),
      reason,
      h(
        "div",
        { class: "row2" },
        item.status === "failed" ? h("button", { class: "primary", onclick: act("queue_retry", { item_ids: [item.id] }, "queued again.") }, "Retry capture") : null,
        h("button", { class: "ghost", onclick: remove }, "Remove from queue")
      ),
      status
    );
  }
};
var INTENTS = [
  ["all", "everything, grouped"],
  ["donor", "something to reuse"],
  ["orient", "where the catalogue holds a topic"],
  ["pattern", "a design pattern"],
  ["technique", "a technique"],
  ["data", "a dataset"],
  ["precedent", "prior work"],
  ["made", "what this library made"],
  ["in_text", "text inside documents"]
];
var FILTERED = /* @__PURE__ */ new Set(["all", "donor", "orient", "data"]);
var GROUP_LABEL = {
  orient: "Sources",
  pattern: "Patterns",
  made: "What this library made"
};
var Search = class {
  constructor(api, openNote) {
    this.api = api;
    this.openNote = openNote;
    this.el = h("div", { class: "view search" });
    this.facets = h("div", { class: "facets", "aria-label": "Filters" });
    this.results = h("div", { class: "results", "aria-live": "polite" });
    this.chosen = {};
    this.last = { query: "", intent: "all", age: 0 };
    // The library, or the library's work: staging, the threads, what was used and written
    this.scope = "library";
    const query = h("input", { type: "search", placeholder: "What are you looking for?", "aria-label": "Search query" });
    const intent = h(
      "select",
      { "aria-label": "Intent" },
      INTENTS.map(([v, label]) => h("option", { value: v }, `${v} \xB7 ${label}`))
    );
    const age = h(
      "select",
      { "aria-label": "Source date" },
      [["0", "any date"], ["365", "within a year"], ["1095", "within 3 years"]].map(([v, label]) => h("option", { value: v }, label))
    );
    const scope = h("select", { "aria-label": "Search in", onchange: () => {
      this.scope = scope.value;
      intent.style.display = age.style.display = this.scope === "library" ? "" : "none";
    } }, [
      ["library", "the library"],
      ["staging", "staging"],
      ["sessions", "sessions"],
      ["activity", "activity"]
    ].map(([v, label]) => h("option", { value: v }, label)));
    const run = () => this.scope === "library" ? this.run(query.value, intent.value, Number(age.value)) : this.runWork(query.value);
    query.onkeydown = (e) => {
      if (e.key === "Enter") run();
    };
    this.el.append(
      h("div", { class: "view-head" }, h("strong", {}, "Search")),
      h("div", { class: "row2 tight search-bar" }, query, h("button", { class: "primary", onclick: run }, "Search")),
      h("div", { class: "search-filters", role: "group", "aria-label": "Search filters" }, scope, intent, age),
      h("div", { class: "split" }, this.facets, this.results)
    );
  }
  activity() {
    const scope = this.el.querySelector('select[aria-label="Search in"]');
    scope.value = "activity";
    scope.dispatchEvent(new Event("change"));
    this.focus();
  }
  focus() {
    this.el.querySelector("input")?.focus();
  }
  /** Staging, sessions or activity (search_work): where was that seen? */
  async runWork(query) {
    if (!query.trim()) return;
    clear(this.facets);
    clear(this.results, h("p", { class: "dim" }, "Searching\u2026"));
    try {
      const out = await this.api.tool("search_work", { query, scope: this.scope });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      const rows = out.results ?? [];
      const when2 = (w) => String(w ?? "").slice(0, 10);
      const row = (r) => this.scope === "staging" ? h(
        "div",
        { class: "tile" },
        h("strong", {}, r.name || r.id),
        h("span", { class: "dim" }, ` \xB7 ${r.kind} \xB7 ${r.status} \xB7 ${when2(r.when)}`)
      ) : this.scope === "sessions" ? h(
        "div",
        { class: "tile" },
        h("strong", {}, r.question || r.session),
        h("span", { class: "dim" }, ` \xB7 ${r.purpose} \xB7 ${r.status} in ${r.phase} \xB7 ${when2(r.when)} \xB7 ${r.session}`)
      ) : h(
        "div",
        { class: "tile" },
        `${r.what} `,
        h("a", { class: "wl", href: "#", onclick: (e) => {
          e.preventDefault();
          this.openNote(r.target);
        } }, r.target),
        h("span", { class: "dim" }, `${r.detail && r.detail !== r.target ? ` \xB7 ${r.detail}` : ""} \xB7 ${when2(r.when)} \xB7 ${r.session}`)
      );
      clear(this.results, rows.length ? rows.map(row) : h("p", { class: "dim" }, `Nothing in ${this.scope} matches.`));
    } catch (e) {
      clear(this.results, h("p", { class: "error" }, e.message));
    }
  }
  async run(query, intent, age = this.last.age) {
    if (!query.trim()) return;
    if (query !== this.last.query || intent !== this.last.intent) this.chosen = {};
    this.last = { query, intent, age };
    clear(this.results, h("p", { class: "dim" }, "Searching\u2026"));
    const constraints = FILTERED.has(intent) ? this.chosen : {};
    try {
      const out = await this.api.tool("search", {
        query,
        intent,
        limit: 20,
        constraints,
        ...age ? { max_age_days: age } : {}
      });
      if (out.error) throw new Error(String(out.detail ?? out.error));
      this.paintFacets(out, intent);
      this.paintResults(out, query, intent);
    } catch (e) {
      clear(this.results, h("p", { class: "error" }, e.message));
    }
  }
  paintFacets(out, intent) {
    const axes = Object.entries(out.facets ?? {});
    const picked = Object.values(this.chosen).reduce((n, v) => n + v.length, 0);
    const toggle = (axis, value) => () => {
      const now = new Set(this.chosen[axis] ?? []);
      if (now.has(value)) now.delete(value);
      else now.add(value);
      this.chosen = { ...this.chosen, [axis]: [...now] };
      if (!now.size) delete this.chosen[axis];
      void this.run(this.last.query, this.last.intent);
    };
    clear(
      this.facets,
      !FILTERED.has(intent) ? h("p", { class: "dim" }, "Filters apply to sources: choose everything, donor, orient or data.") : axes.length || picked ? null : h("p", { class: "dim" }, "Filters appear here from what the search returns."),
      picked ? h(
        "button",
        { class: "ghost", onclick: () => {
          this.chosen = {};
          void this.run(this.last.query, this.last.intent);
        } },
        `Clear filters (${picked})`
      ) : null,
      // A chosen value stays listed even when it now matches nothing, so it can be cleared.
      Object.entries(this.chosen).filter(([axis]) => !axes.some(([a]) => a === axis)).map(([axis, values]) => h(
        "div",
        { class: "facet" },
        h("h4", {}, axis.replace(/_/g, " ")),
        values.map((v) => h("button", { class: "chip", "aria-pressed": "true", onclick: toggle(axis, v) }, `${v} \u2715`))
      )),
      axes.map(([axis, values]) => h(
        "div",
        { class: "facet" },
        h("h4", {}, axis.replace(/_/g, " ")),
        values.slice(0, 12).map((v) => h("button", {
          class: "chip",
          "aria-pressed": String((this.chosen[axis] ?? []).includes(v.value)),
          onclick: toggle(axis, v.value)
        }, `${v.value} `, h("span", { class: "dim" }, String(v.count))))
      ))
    );
  }
  paintResults(out, query, intent) {
    const rows = out.results ?? [];
    const feedback = (r, verdict, rank) => this.api.tool("search_feedback", { query, note: r.name, verdict, intent: r.fields?.intent ?? intent, rank }).catch(() => void 0);
    const tile = (r, rank) => {
      const f = r.fields ?? {};
      const card = h(
        "div",
        { class: "tile" },
        h(
          "div",
          { class: "tile-head" },
          h("a", { class: "wl", href: "#", onclick: (e) => {
            e.preventDefault();
            void feedback(r, "opened", rank);
            this.openNote(f.path ?? f.note ?? r.name);
          } }, r.name),
          h("span", { class: "dim" }, [r.kind, f.kind && f.kind !== r.kind ? f.kind : "", f.topic].filter(Boolean).join(" \xB7 ")),
          f.read_depth ? h("span", {
            class: `depth ${String(f.read_depth).split(" ")[0]}`,
            title: (f.not_examined ?? []).join("; ") || "how much of the source was read"
          }, `read: ${f.read_depth}`) : null
        ),
        f.bottom_line ? h("p", {}, f.bottom_line) : f.excerpt ? h("p", {}, f.excerpt) : null,
        h("small", { class: "dim" }, r.why ?? ""),
        // The grains beneath a source (SM-2/3/4): where inside it, how to reach it, what
        // it relates to - shown beside the result, never folded into its rank.
        (f.components ?? []).length ? h(
          "p",
          { class: "inside" },
          "Inside: ",
          f.components.map((c, i) => h(
            "span",
            {},
            i ? " \xB7 " : "",
            h("code", {}, c.address),
            h("span", { class: "dim" }, ` (${(c.matched ?? []).join(", ")})`)
          ))
        ) : null,
        (f.access_points ?? []).length ? h(
          "div",
          { class: "access" },
          f.access_points.map((p) => h("div", {}, h("code", {}, p.url), h(
            "span",
            { class: "dim" },
            p.checked_at === "never" ? " \xB7 not checked" : ` \xB7 ${p.reachable ? "answered" : "did not answer"} (${p.status}) \xB7 checked ${String(p.checked_at).slice(0, 10)}`
          ))),
          h("button", { class: "ghost", onclick: async () => {
            await this.api.tool("verify_access", { source: r.name });
            void this.run(this.last.query, this.last.intent);
          } }, "Check access")
        ) : null,
        (f.examples ?? []).length || (f.neighbours ?? []).length ? h(
          "p",
          { class: "dim" },
          (f.examples ?? []).length ? "Used by: " : "",
          (f.examples ?? []).flatMap((n, i) => [i ? ", " : "", h("a", { class: "wl", href: "#", onclick: (e) => {
            e.preventDefault();
            this.openNote(n);
          } }, n)]),
          (f.neighbours ?? []).length ? `${(f.examples ?? []).length ? " \xB7 " : ""}Near: ${f.neighbours.join(", ")}` : ""
        ) : null,
        h(
          "div",
          { class: "row2 tight" },
          h("button", { class: "ghost", title: "Logged only: it never changes ranking", onclick: () => {
            void feedback(r, "dismissed", rank);
            card.classList.add(cls("dismissed"));
          } }, "Not relevant")
        )
      );
      return card;
    };
    const groups = intent === "all" ? (out.ran ?? []).map((i) => [i, rows.filter((r) => r.fields?.intent === i)]) : [["", rows]];
    const removed = out.removed_by_filters ?? [];
    clear(
      this.results,
      h("p", { class: "verdict" }, String(out.coverage?.sentence ?? out.verdict ?? "")),
      removed.length ? h("p", { class: "warn" }, `Your filters removed these top candidates: ${removed.join(", ")}.`) : null,
      out.ran ? h("p", { class: "dim" }, `Ran: ${out.ran.join(", ")} \u2014 each answers in its own shape.`) : null,
      rows.length ? groups.map(([i, rs]) => h(
        "section",
        { class: "group" },
        i ? h("h3", {}, `${GROUP_LABEL[i] ?? i} \xB7 ${rs.length}`) : null,
        rs.length ? rs.map((r, n) => tile(r, n + 1)) : h("p", { class: "dim" }, "Nothing here.")
      )) : h("p", { class: "dim" }, "Nothing held matches."),
      out.next_step ? h("p", { class: "note" }, String(out.next_step)) : null
    );
  }
};

// ../ui/src/main.ts
function relinkChat(log, oldName, newName, open) {
  log.querySelectorAll(sel("a.wl")).forEach((a) => {
    const target = a.title;
    const parts = target.split("/");
    if (parts[parts.length - 1].replace(/\.md$/i, "").toLowerCase() !== oldName.toLowerCase()) return;
    parts[parts.length - 1] = newName;
    const label = a.textContent === oldName ? newName : a.textContent ?? newName;
    a.replaceWith(link(parts.join("/"), label, open));
  });
}
var App = class {
  constructor(root, opts) {
    this.root = root;
    this.ids = claimInstance();
    this.state = {};
    // Bumped whenever this tab learns newer tiers than a fetch in flight could
    // hold (its own pick, or a `tiers_changed` event): a `/api/state` answer
    // requested before that must not put the older tiers back.
    this.tiersEpoch = 0;
    this.effects = /* @__PURE__ */ new Map();
    this.pipelines = [];
    this.session = null;
    this.view = "chat";
    this.libraryButton = h("button", { class: "ghost lib-switch", title: "Switch library" }, "Library \u25BE");
    this.checkpointButton = h("button", { class: "ghost", title: "Decisions waiting for you" }, "Checkpoints \u25BE");
    this.title = h("span", { class: "title" }, "Librarian");
    this.crumb = h("span", { class: "crumb" });
    this.live = h("span", { class: "live", role: "status", title: "Connection to the core" });
    this.chips = h("div", { class: "chips", "aria-label": "Queued actions" });
    this.input = h("textarea", {
      id: this.ids.id("lib-msg"),
      class: "composer-text",
      "aria-label": "Message",
      placeholder: "Ask the librarian. Enter sends, Shift+Enter adds a line."
    });
    this.attachments = [];
    this.sending = false;
    // a chat POST is in flight (MF-005)
    this.cancelling = /* @__PURE__ */ new Set();
    // workflow runs with a cancel requested (MF-006)
    this.savedPaneWidth = 0;
    // the person's split preference, px (MF-008)
    this.bodyObserver = null;
    this.stopping = false;
    // Stop was pressed; waiting for the Core's outcome
    this.attachRow = h("div", { class: "attach-row", hidden: true });
    this.msgBox = h("div", { class: "msg-box" });
    this.modeButton = h("button", { class: "tb" });
    this.modelButton = h("button", { class: "tb" });
    // The effort slider (owner, 2026-10-01): how much work the person expects - helpers,
    // steps and time per reply, call budgets, how much is reviewed (effort.py).
    this.effortValue = h("span", { class: "effort-value" }, "4");
    this.effortInput = h("input", {
      type: "range",
      min: "1",
      max: "10",
      step: "1",
      value: "4",
      "aria-label": "Effort"
    });
    this.effortControl = h("label", { class: "effort tb" }, "Effort ", this.effortInput, this.effortValue);
    this.batchNotice = h("div", { class: "notice", role: "status", hidden: true });
    this.notice = h("div", { class: "notice", role: "alert", hidden: true });
    this.paneOpen = true;
    this.stopEvents = null;
    this.onDocumentKey = (e) => {
      if (this.opts.host === "website" && e.altKey && e.shiftKey && !e.ctrlKey && !e.metaKey && !e.repeat && !e.isComposing && !e.defaultPrevented && !this.settings.dialog.open && e.target instanceof Element && (this.root.contains(e.target) || e.target === document.body && document.querySelectorAll(".librarian-root").length === 1) && !e.target.closest("input, textarea, select, [contenteditable], [role=textbox], dialog, [role=dialog]")) {
        const key = e.code.replace(/^(Key|Digit)/, "");
        const id = key && Object.keys(COMMANDS).find((id2) => preference("key." + id2) === key);
        if (id) {
          e.preventDefault();
          this.command(id);
          return;
        }
      }
      if (e.key !== "Escape") return;
      const open = this.popovers().filter((p) => p.open);
      if (!open.length) return;
      open.forEach((p) => {
        if (p !== this.models || !this.tile.cancelSlot()) p.show(false);
      });
      e.preventDefault();
      e.stopPropagation();
    };
    this.onDocumentClick = (e) => {
      const path2 = e.composedPath();
      for (const p of [this.modes, this.models, this.sessions, this.libraries, this.checkpoints, this.attachPop]) {
        if (p.open && !path2.includes(p.el) && !path2.includes(p.button)) {
          if (p !== this.models || !this.tile.cancelSlot()) p.show(false);
        }
      }
    };
    this.api = new Api(opts);
    const openNote = (target) => void this.openDoc(target);
    reader.init(this.api, (message) => this.warn(message));
    this.chat = new Chat(this.api, {
      openNote,
      effectOf: (tool) => this.effects.get(tool) ?? "write",
      onSession: (s) => this.setSession(s),
      resend: (text) => void this.sendText(text),
      newThread: () => void this.reset(),
      continueSession: () => void this.sendText("Continue the current research session from its next step. Read session_status first, complete the open work, and report any information you cannot verify as a gap. Do not claim the session or requested work is complete while session_status still shows open items."),
      openModelPicker: () => {
        this.toggle(this.models);
        if (this.models.open) void this.tile.refresh();
      },
      rewind: (index) => void this.rewindMessage(index),
      branch: (index) => void this.branchMessage(index),
      openOffering: (id) => {
        this.staging.focusOffering(id);
        this.show("staging");
      }
    });
    this.staging = new Staging(
      this.api,
      openNote,
      () => this.session?.session ?? "",
      (session) => this.setSession(session),
      () => this.settings.open("models"),
      (event) => {
        if (event === "start" && preference("job-start") === "activity") {
          this.show("search");
          this.search.activity();
        }
        if (event === "finish" && preference("batch-notice") === "on") {
          this.batchNotice.hidden = false;
          clear(
            this.batchNotice,
            this.libraryName() + ": ingestion batch finished. ",
            h("button", { class: "ghost", onclick: () => {
              this.batchNotice.hidden = true;
              this.show("staging");
            } }, "View batch"),
            h("button", { class: "ghost", onclick: () => {
              this.batchNotice.hidden = true;
            } }, "Dismiss")
          );
        }
      },
      () => {
        const tiers = this.state.tiers ?? [], route = tiers[2] ?? tiers[1] ?? tiers[0];
        return "Library: " + this.libraryName() + ". " + (route ? "Chat small-task selection: " + route.provider + " / " + route.model + ". Individual steps can use other routes." : "No chat model selected.");
      },
      () => String(this.state.vault_path || this.state.vault || "")
    );
    this.search = new Search(this.api, openNote);
    this.pane = new DocPane(
      this.api,
      this.chat.plan,
      () => String(this.state.vault ?? ""),
      () => this.showPane(false),
      (oldName, newName) => relinkChat(this.chat.log, oldName, newName, openNote),
      () => this.session?.project ?? "",
      () => this.session?.session ?? ""
    );
    this.opts = opts;
    this.settings = new Settings(
      this.api,
      () => this.state,
      () => this.refresh(),
      opts.manageKeys,
      (slot, label, current, role) => void this.chooseService(slot, label, current, role),
      opts.host === "obsidian",
      (id) => this.command(id),
      (base) => this.ids.id(base)
    );
    const settingsButton = h("button", {
      class: "ghost",
      title: "Settings",
      "aria-label": "Settings",
      onclick: () => this.settings.open()
    }, "Settings");
    this.modes = new Popover(this.ids.id("lib-modes"), "Modes", this.modeButton, "lib-modes");
    this.models = new Popover(this.ids.id("lib-models"), "Model", this.modelButton, "lib-models");
    const sessionsButton = h("button", { class: "ghost" }, "Sessions \u25BE");
    this.sessions = new Popover(this.ids.id("lib-sessions"), "Sessions", sessionsButton, "lib-sessions");
    this.libraries = new Popover(this.ids.id("lib-libraries"), "Libraries", this.libraryButton, "lib-libraries");
    this.checkpoints = new Popover(this.ids.id("lib-checkpoints"), "Checkpoints", this.checkpointButton, "lib-checkpoints");
    this.libraryButton.onclick = () => {
      this.toggle(this.libraries);
      if (this.libraries.open) void renderLibraries(this.libraries, this.api, this.libraryName());
    };
    this.tile = new ModelTile(
      this.models,
      this.api,
      () => this.state.tiers ?? [],
      () => Object.fromEntries((this.state.keys ?? []).map((k) => [k.provider, !!k.saved])),
      (tiers) => {
        this.state.tiers = tiers;
        this.tiersEpoch++;
      }
    );
    const attachButton = h("button", {
      class: "tb icon",
      title: "Attach a file, or link a note or folder",
      "aria-label": "Attach"
    }, "\u{1F4CE}");
    this.attachPop = new Popover(this.ids.id("lib-attach"), "Attach", attachButton, "lib-attach");
    this.attachPanel = new AttachPanel(
      this.attachPop,
      this.api,
      (text) => this.insertIntoComposer(text),
      (file, raw) => this.addAttachment(file.name, raw)
    );
    attachButton.onclick = () => {
      this.toggle(this.attachPop);
      if (this.attachPop.open) this.attachPanel.render();
    };
    this.modeButton.onclick = () => this.toggle(this.modes);
    this.modelButton.onclick = async () => {
      this.tile.endSlot();
      this.toggle(this.models);
      if (this.models.open) {
        await this.refresh();
        await this.tile.refresh();
      }
    };
    sessionsButton.onclick = () => {
      this.toggle(this.sessions);
      if (this.sessions.open) void renderSessions(
        this.sessions,
        this.api,
        (id) => this.attach(id),
        () => this.reset(),
        this.libraryName(),
        String(this.state.vault_path ?? "")
      );
    };
    this.checkpointButton.onclick = () => {
      this.toggle(this.checkpoints);
      if (this.checkpoints.open) void this.refreshCheckpoints();
    };
    const elsewhere = h("button", {
      class: "tb",
      title: opts.host === "obsidian" ? "Continue in the website" : "Open this vault in Obsidian",
      onclick: opts.openElsewhere ?? (() => {
        window.location.href = `obsidian://open?vault=${encodeURIComponent(String(this.state.vault ?? ""))}`;
      })
    }, opts.host === "obsidian" ? "\u2197 Open in browser" : "\u2197 Open in Obsidian");
    this.sendButton = h("button", { class: "send", onclick: () => this.state.busy ? this.stop() : this.send() }, "Send");
    this.effortInput.oninput = () => {
      this.effortValue.textContent = this.effortInput.value;
    };
    this.effortInput.onchange = async () => {
      try {
        const chosen = await this.api.post("/api/effort", { level: Number(this.effortInput.value) });
        this.state.effort = chosen;
        this.paintEffort();
      } catch (e) {
        this.paintEffort();
        this.warn(`Effort not changed: ${e.message}`);
      }
    };
    this.input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.altKey && !e.isComposing && (e.ctrlKey || e.metaKey) === (preference("send") === "modified")) {
        e.preventDefault();
        if (!this.state.busy) void this.send();
      }
    });
    const chatView = h("main", { class: "chatview" }, this.chat.log, this.attachPop.el);
    this.views = { chat: chatView, staging: this.staging.el, search: this.search.el };
    const navButton = (v, label) => h("button", {
      role: "tab",
      onkeydown: (event) => {
        const e = event;
        const names = Object.keys(this.nav), index = names.indexOf(v);
        const next = e.key === "Home" ? 0 : e.key === "End" ? names.length - 1 : e.key === "ArrowRight" ? (index + 1) % names.length : e.key === "ArrowLeft" ? (index + names.length - 1) % names.length : -1;
        if (next >= 0) {
          e.preventDefault();
          this.show(names[next]);
          this.nav[names[next]].focus();
        }
      },
      onclick: () => this.show(v)
    }, label);
    this.nav = {
      chat: navButton("chat", "Chat"),
      staging: navButton("staging", "Staging"),
      search: navButton("search", "Search")
    };
    clear(this.msgBox, this.attachRow, this.input);
    const composer = h(
      "div",
      { class: "composer" },
      this.chips,
      this.msgBox,
      h("div", { class: "toolbar" }, attachButton, this.modeButton, this.modelButton, this.effortControl, elsewhere, this.sendButton),
      this.modes.el,
      this.models.el
    );
    this.paneButton = h("button", {
      class: "icon-btn",
      title: "Plan and notes beside the chat",
      "aria-label": "Show the document pane",
      onclick: () => this.showPane(!this.paneOpen)
    }, paneIcon());
    const resizer = h("div", {
      class: "lib-resizer",
      role: "separator",
      "aria-orientation": "vertical",
      tabindex: "0",
      "aria-label": "Document pane width",
      title: "Drag or use arrow keys to resize"
    });
    resizer.addEventListener("keydown", (e) => {
      const room = this.body.clientWidth - resizer.offsetWidth;
      const now = this.pane.el.getBoundingClientRect().width;
      const widths = { Home: 300, End: room - 360, ArrowLeft: now + 24, ArrowRight: now - 24 };
      if (!(e.key in widths)) return;
      e.preventDefault();
      this.savedPaneWidth = widths[e.key];
      this.savedPaneWidth = this.applyPaneWidth();
      remember2("pane-w", String(this.savedPaneWidth) + "px");
    });
    resizer.addEventListener("pointerdown", (e) => this.resize(e, resizer));
    this.body = h(
      "div",
      { class: "lib-body" },
      h("div", { class: "lib-main" }, this.notice, this.batchNotice, chatView, this.staging.el, this.search.el, composer),
      resizer,
      this.pane.el
    );
    clear(
      root,
      h(
        "div",
        { class: `lib-app host-${opts.host}` },
        h(
          "header",
          {},
          h("div", { class: "anchor" }, this.libraryButton, this.libraries.el),
          h("div", { class: "anchor" }, sessionsButton, this.sessions.el),
          h("div", { class: "anchor" }, this.checkpointButton, this.checkpoints.el),
          this.title,
          this.crumb,
          h("nav", { role: "tablist", "aria-label": "Views" }, Object.values(this.nav)),
          settingsButton,
          h("button", { class: "ghost", onclick: () => this.settings.open("models") }, "Models"),
          this.live,
          this.paneButton
        ),
        this.body
      ),
      this.settings.dialog
    );
    this.composer = composer;
    document.addEventListener("keydown", this.onDocumentKey);
    document.addEventListener("click", this.onDocumentClick);
    this.show("chat");
    this.savedPaneWidth = parseInt(recall("pane-w"), 10) || 0;
    this.applyPaneWidth();
    if (typeof ResizeObserver !== "undefined") {
      this.bodyObserver = new ResizeObserver(() => this.applyPaneWidth());
      this.bodyObserver.observe(this.body);
    }
    const saved = recall("pane");
    this.showPane(saved === "open");
  }
  popovers() {
    return [this.modes, this.models, this.sessions, this.libraries, this.checkpoints, this.attachPop];
  }
  // -- the document pane -------------------------------------------------------
  /** A [[link]]: in Obsidian the real note opens; elsewhere it opens beside the chat. */
  async openDoc(target) {
    if (this.opts.openNote) {
      try {
        const doc = await this.api.get(`/api/file?path=${encodeURIComponent(target)}`);
        this.opts.openNote(doc.name, doc.path);
        return;
      } catch {
      }
    }
    this.showPane(true);
    await this.pane.open(target);
  }
  showPane(on) {
    this.paneOpen = on;
    this.body.classList.toggle(cls("pane-open"), on);
    this.body.classList.toggle(cls("pane-closed"), !on);
    this.paneButton.setAttribute("aria-pressed", String(on));
    remember2("pane", on ? "open" : "closed");
  }
  /** Apply the saved split clamped to the current room; returns the width
   *  applied (0 when none is saved and the stylesheet's default applies). */
  applyPaneWidth() {
    const separator = this.body.querySelector(".lib-resizer");
    separator?.setAttribute("aria-valuemin", "300");
    separator?.setAttribute("aria-valuemax", String(Math.max(300, this.body.clientWidth - (separator.offsetWidth || 5) - 360)));
    if (!this.savedPaneWidth) {
      separator?.setAttribute("aria-valuenow", String(Math.round(this.pane.el.getBoundingClientRect().width)));
      return 0;
    }
    const handle = this.body.querySelector(".lib-resizer")?.offsetWidth ?? 0;
    const room = this.body.clientWidth - handle;
    const width = room > 0 ? Math.max(300, Math.min(this.savedPaneWidth, room - 360)) : this.savedPaneWidth;
    this.body.style.setProperty("--pane-w", `${Math.round(width)}px`);
    separator?.setAttribute("aria-valuenow", String(Math.round(width)));
    return Math.round(width);
  }
  resize(start2, handle) {
    start2.preventDefault();
    handle.setPointerCapture(start2.pointerId);
    const rect = this.body.getBoundingClientRect();
    const move = (e) => {
      this.savedPaneWidth = Math.round(rect.right - e.clientX);
      this.applyPaneWidth();
    };
    const up = () => {
      handle.removeEventListener("pointermove", move);
      this.savedPaneWidth = this.applyPaneWidth();
      remember2("pane-w", `${this.savedPaneWidth}px`);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up, { once: true });
  }
  async start() {
    try {
      const tools = await this.api.get("/api/tools");
      for (const t of tools.tools ?? []) this.effects.set(t.name, t.effect);
      const listed = await this.api.tool("list_workflows").catch(() => ({ definitions: [] }));
      this.pipelines = (listed.definitions ?? []).filter((d) => d.kind === "pipeline").map((d) => d.name);
      await this.refresh();
    } catch (e) {
      this.warn(`The core did not answer: ${e.message}. Is \`resource-librarian app\` running?`);
      return;
    }
    this.stopEvents = this.api.events(this.state.event_stream, (event) => this.onEvent(event), (live) => {
      this.live.className = cls(`live ${live ? "on" : "off"}`);
      this.live.setAttribute("aria-label", live ? "Event stream connected" : "Event stream reconnecting");
      this.live.title = live ? "Event stream connected" : "Event stream reconnecting";
      this.live.textContent = live ? "\u25CF" : "\u25CB reconnecting";
      if (live) void this.refresh();
    });
    this.input.focus();
  }
  async refresh() {
    const epoch = this.tiersEpoch;
    const fresh = await this.api.get("/api/state");
    if (this.tiersEpoch !== epoch) fresh.tiers = this.state.tiers;
    this.state = fresh;
    if (this.settings.dialog.open) this.settings.syncState();
    this.paintSendButton();
    this.libraryButton.textContent = `${this.libraryName()} \u25BE`;
    this.libraryButton.title = `Switch library - this is ${this.libraryName()} (${String(this.state.vault_path ?? "")})`;
    document.title = `${this.libraryName()} - Librarian`;
    this.setSession(this.state.session ?? null);
    this.paintToolbar();
    this.paintChips();
    if (this.state.busy) this.chat.setWorking(true);
    for (const request of this.state.pending ?? []) this.chat.handle({ seq: 0, type: "permission_request", ...request });
  }
  onEvent(event) {
    if (event.type === "resync_required") {
      void this.refresh().catch((error) => this.warn(error.message));
      return;
    }
    this.chat.handle(event);
    switch (event.type) {
      case "mode_changed":
        this.state.mode = event.to;
        this.paintToolbar();
        break;
      case "tiers_changed":
        this.state.tiers = event.tiers;
        if (this.settings.dialog.open) this.settings.syncState();
        this.tiersEpoch++;
        this.paintToolbar();
        if (this.models.open) this.tile.render();
        break;
      case "turn_done":
      case "error":
        this.state.busy = false;
        this.stopping = false;
        this.paintSendButton();
        break;
      case "action_started":
      case "action_progress":
      case "action_done": {
        const actions = this.state.actions ?? [];
        const at = actions.findIndex((a) => a.id === event.id);
        const row = { id: event.id, name: event.name, status: event.status, steps: event.steps, reason: event.reason };
        if (at >= 0) actions[at] = row;
        else actions.push(row);
        this.state.actions = actions;
        this.paintChips();
        if (event.type === "action_done" && this.view === "staging") void this.staging.load();
        break;
      }
      case "person_acted":
        if (event.session) this.setSession(event.session);
        if (this.view === "staging") void this.staging.load();
        break;
      case "checkpoint_created":
      case "checkpoint_resolved":
        void this.refreshCheckpoints();
        break;
      case "route_health_changed":
      case "workflow_preflight":
        if (this.models.open) void this.tile.refresh();
        break;
      case "library_switched":
        window.location.reload();
        break;
    }
  }
  // -- painting ------------------------------------------------------------
  paintEffort() {
    const e = this.state.effort;
    if (!e) return;
    this.effortInput.value = String(e.level);
    this.effortValue.textContent = String(e.level);
    this.effortControl.title = `Effort up to ${e.level} of 10 - the most work you allow. The librarian chooses less for a small request (one link, one file, a quick answer). At ${e.level}: Helpers at once: ${e.lead_agents} on the lead model, ${e.tier2_agents} on the notes model; small-task calls at once: ${e.tier3_agents}. Up to ${e.turn_steps} steps and ${Math.round(e.turn_seconds / 60)} min per reply; call budgets x${e.budget_scale}. Review: ${e.review_replies ? `offerings and up to ${e.review_claims} claims per reply` : e.review_offerings ? "offerings' claims" : "nothing automatic"}.`;
  }
  paintToolbar() {
    this.paintEffort();
    const mode = MODES.find(([v]) => v === this.state.mode);
    clear(this.modeButton, "Modes: ", h("strong", {}, mode ? mode[1].split(" ")[0] : "?"), " \u25BE");
    const tier = (this.state.tiers ?? [])[0];
    clear(this.modelButton, tier ? [h("span", { class: "badge" }, "1"), ` ${tier.model} \xB7 ${PROVIDERS[tier.provider] ?? tier.provider}`] : "Choose models", " \u25BE");
    renderModes(
      this.modes,
      this.api,
      this.state.mode,
      this.state.queued_actions ?? [],
      this.pipelines,
      (msg) => this.warn(msg),
      this.state.queued_inputs ?? {},
      this.ids.id("librarian-mode"),
      this.libraryName() + " \xB7 " + (this.session?.session ?? "no active conversation")
    );
    const pending = (this.state.pending_checkpoints ?? []).length;
    this.checkpointButton.textContent = pending ? `Checkpoints (${pending}) \u25BE` : "Checkpoints \u25BE";
    if (this.checkpoints.open) this.renderCheckpoints();
  }
  /** Policy choices live here, not in a prose prompt.  A blocked operation
   * leaves its evidence and available, explicit choices in this small panel;
   * resolving one does not silently unblock unrelated work. */
  async refreshCheckpoints() {
    try {
      const out = await this.api.get("/api/checkpoints?pending=1");
      this.state.pending_checkpoints = out.checkpoints ?? [];
      this.renderCheckpoints();
      this.paintToolbar();
    } catch (e) {
      this.warn(e.message);
    }
  }
  renderCheckpoints() {
    const rows = this.state.pending_checkpoints ?? [];
    const card = (row) => {
      const evidence = row.evidence && Object.keys(row.evidence).length ? h("pre", { class: "checkpoint-evidence" }, JSON.stringify(row.evidence, null, 2)) : null;
      const writeConflictHelp = row.type === "write_conflict" ? h(
        "p",
        { class: "checkpoint-help" },
        "Review the named note in its editor. Resolving this card records your decision only; it does not retry the blocked write. Repeat the original action after the editor is quiet."
      ) : null;
      const buttons = [];
      const resolve2 = async (choice) => {
        if (buttons.some((b) => b.disabled)) return;
        buttons.forEach((b) => {
          b.disabled = true;
        });
        try {
          await this.api.post("/api/checkpoints/resolve", { id: row.id, choice });
        } catch (e) {
          buttons.forEach((b) => {
            b.disabled = false;
          });
          this.warn(`Decision not recorded: ${e.message}`);
          return;
        }
        if (choice === "retry_after_review") this.warn(
          "Review recorded. The blocked write was not retried; repeat the original action after the editor is quiet."
        );
        await this.refreshCheckpoints();
      };
      return h(
        "section",
        { class: "checkpoint" },
        h("strong", {}, String(row.type ?? "Decision").replace(/_/g, " ")),
        h("p", {}, String(row.scope ?? "")),
        evidence,
        writeConflictHelp,
        h("div", { class: "row2" }, ...(Array.isArray(row.choices) ? row.choices : []).map((choice) => (
          // The Core declares the safe default.  Array order is presentation
          // history, not an instruction to make an approval action primary.
          buttons[buttons.push(h(
            "button",
            {
              class: choice === row.default ? "primary" : "ghost",
              onclick: () => void resolve2(choice)
            },
            choice === "retry_after_review" ? "Mark reviewed; retry manually" : choice.replace(/_/g, " ")
          )) - 1]
        )))
      );
    };
    clear(
      this.checkpoints.el,
      h("h4", {}, "Decisions waiting for you"),
      rows.length ? rows.map(card) : h("p", { class: "dim" }, "No decisions are waiting. Agents can continue work on other notes.")
    );
  }
  paintChips() {
    const running = (this.state.actions ?? []).filter((a) => a.status === "running" || a.status === "paused");
    for (const id of [...this.cancelling]) {
      if (!running.some((a) => a.id === id && a.status === "running")) this.cancelling.delete(id);
    }
    clear(this.chips, running.map((a) => h(
      "span",
      { class: "chip" },
      `${a.name} \xB7 ${a.status === "paused" ? `paused${a.reason ? `: ${a.reason}` : ""}` : `${a.steps} steps`}`,
      a.status !== "running" ? null : this.cancelling.has(a.id) ? h("button", { "aria-label": `Cancelling ${a.name}`, "aria-busy": "true", disabled: true }, "Cancelling\u2026") : h("button", { "aria-label": `Cancel ${a.name}`, onclick: async () => {
        this.cancelling.add(a.id);
        this.paintChips();
        try {
          await this.api.post(`/api/actions/${a.id}/cancel`);
        } catch (e) {
          this.cancelling.delete(a.id);
          this.paintChips();
          this.warn(`${a.name} was not cancelled: ${e.message}`);
        }
      } }, "\u2715")
    )));
  }
  setSession(session) {
    if (session && this.session && session.session === this.session.session)
      session = { ...this.session, ...session };
    this.session = session;
    this.chat.renderPlan(session);
    if (!session) {
      this.title.textContent = "";
      this.crumb.textContent = "no thread";
      return;
    }
    this.title.textContent = session.project || session.question || "";
    this.crumb.textContent = `${session.purpose ?? ""} \xB7 phase: ${session.phase ?? ""}${session.status && session.status !== "open" ? ` \xB7 ${session.status}` : ""}`;
  }
  /** The open library by its own name: two libraries made by new-vault.ps1 share the
   *  folder name `.librarian-app`, so the folder cannot say which one this is. */
  libraryName() {
    return String(this.state.vault_name ?? this.state.vault ?? "Librarian");
  }
  command(id) {
    if (!(id in COMMANDS)) return;
    if (id === "settings") {
      this.settings.open();
      return;
    }
    this.settings.dialog.close();
    if (id === "search") {
      this.show("search");
      return;
    }
    if (id === "sessions" || id === "checkpoints") {
      const pop = id === "sessions" ? this.sessions : this.checkpoints;
      if (!pop.open) pop.button.click();
      return;
    }
    if (["staging", "approved", "resume", "retry", "stop"].includes(id)) {
      this.show("staging");
      if (id === "staging") this.staging.el.querySelector("button")?.focus();
      else void this.staging.focusBatch(id);
      return;
    }
    this.show("chat");
    if (id === "intake") {
      this.attachPop.button.click();
      this.warn("Attach a source file for this library, then ask the librarian to capture it for review in Staging.");
      return;
    }
    if (!this.modes.open) this.toggle(this.modes);
    const button = this.modes.el.querySelector(`[data-command="${id}"]`);
    if (button) {
      button.focus();
      button.scrollIntoView({ block: "nearest" });
    } else this.warn("This workflow is unavailable in " + this.libraryName() + ".");
  }
  show(view, refresh = true) {
    this.view = view;
    for (const [v, el] of Object.entries(this.views)) el.hidden = v !== view;
    for (const [v, b] of Object.entries(this.nav)) {
      b.setAttribute("aria-selected", String(v === view));
      b.tabIndex = v === view ? 0 : -1;
    }
    this.composer.hidden = view !== "chat";
    if (view === "staging" && refresh) void this.staging.load(true);
    if (view === "search") this.search.focus();
  }
  /** R17: Settings' "Choose…" for a service slot opens the model tile to pick one model
   *  for it; picking (or Cancel) returns to Settings. */
  async chooseService(slot, label, current, role) {
    await new Promise((resolve2) => window.setTimeout(resolve2, 0));
    const origin = this.view;
    this.show("chat");
    this.tile.startSlot(slot, label, () => {
      if (this.models.open) this.toggle(this.models);
      this.show(origin, false);
      this.settings.open("models");
    }, current?.model ? current : void 0, role);
    if (!this.models.open) this.toggle(this.models);
    await this.refresh();
    await this.tile.refresh();
  }
  toggle(pop) {
    const open = !pop.open;
    [this.modes, this.models, this.sessions, this.libraries, this.checkpoints, this.attachPop].forEach((p) => p.show(false));
    pop.show(open);
  }
  /** A file just attached: a chip above the composer, its icon standing for
   *  it, splitting the box in two - the reference itself already sits in the
   *  message text (`insertIntoComposer` put it there); removing the chip
   *  takes that same text back out. */
  addAttachment(label, raw) {
    this.attachments.push({ label, raw });
    this.renderAttachments();
  }
  removeAttachment(i) {
    const [gone] = this.attachments.splice(i, 1);
    if (gone) this.input.value = this.input.value.replace(`${gone.raw} `, "").replace(gone.raw, "");
    this.renderAttachments();
  }
  renderAttachments() {
    const has = this.attachments.length > 0;
    this.attachRow.hidden = !has;
    this.msgBox.classList.toggle(cls("has-attachments"), has);
    clear(this.attachRow, this.attachments.map((a, i) => h(
      "span",
      { class: "attach-chip" },
      fileIcon(),
      h("span", { class: "attach-name" }, a.label),
      h("button", {
        class: "attach-remove",
        "aria-label": `Remove ${a.label}`,
        onclick: () => this.removeAttachment(i)
      }, "\xD7")
    )));
  }
  insertIntoComposer(text) {
    const el = this.input;
    const start2 = el.selectionStart ?? el.value.length;
    const end = el.selectionEnd ?? el.value.length;
    const before = el.value.slice(0, start2);
    const insertion = `${before && !/\s$/.test(before) ? " " : ""}${text} `;
    el.value = before + insertion + el.value.slice(end);
    const caret = start2 + insertion.length;
    el.focus();
    el.setSelectionRange(caret, caret);
  }
  warn(message) {
    this.notice.hidden = false;
    clear(this.notice, message, h("button", {
      class: "ghost push",
      "aria-label": "Dismiss",
      onclick: () => {
        this.notice.hidden = true;
      }
    }, "\u2715"));
  }
  // -- actions ---------------------------------------------------------------
  /** Send the composer's text. The draft stays until the server accepts it:
   *  a refusal or a lost connection keeps text and attachments. Success
   *  clears only what was sent, so anything typed while it was pending
   *  survives (MF-005, G01). */
  async send() {
    if (this.state.busy || this.sending) return;
    const raw = this.input.value;
    const text = raw.trim();
    if (!text) return;
    const sent = [...this.attachments];
    if (!await this.sendText(text)) return;
    if (this.input.value === raw) this.input.value = "";
    this.attachments = this.attachments.filter((a) => !sent.includes(a));
    this.renderAttachments();
  }
  /** The send path itself, shared by the composer and a message's Retry
   *  button - which resends the same text without touching the composer.
   *  One request at a time: a second press while one is pending sends
   *  nothing. True when the server accepted it. */
  async sendText(text) {
    if (!text || this.sending) return false;
    this.sending = true;
    this.paintSendButton();
    try {
      await this.api.post("/api/chat", { text });
      this.state.busy = true;
      return true;
    } catch (e) {
      const message = e.message;
      this.warn(message.includes("tier 1") ? "Choose a chat model first: click Model, then a model (it becomes tier 1)." : message);
      return false;
    } finally {
      this.sending = false;
      this.paintSendButton();
    }
  }
  /** Stop the current reply. Only this button stops one; the reply is
   *  stopped when the Core says so (turn_done or error), not when the
   *  request is sent. */
  async stop() {
    if (!this.state.busy || this.stopping) return;
    this.stopping = true;
    this.paintSendButton();
    try {
      await this.api.post("/api/chat/cancel", {});
    } catch (e) {
      this.stopping = false;
      this.paintSendButton();
      this.warn(e.message);
    }
  }
  paintSendButton() {
    const busy = !!this.state.busy;
    this.sendButton.disabled = this.sending || this.stopping;
    this.sendButton.setAttribute("aria-busy", String(this.sending || this.stopping));
    this.sendButton.textContent = this.stopping ? "Stopping\u2026" : busy ? "Stop" : "Send";
    this.sendButton.setAttribute("aria-label", this.stopping ? "Stopping reply" : busy ? "Stop reply" : "Send message");
    this.sendButton.title = this.stopping ? "Stopping the current reply" : busy ? "Stop the current reply" : "Send message";
  }
  async attach(id) {
    try {
      await this.api.post("/api/chat/attach", { session_id: id });
      this.show("chat");
    } catch (e) {
      this.warn(e.message);
    }
  }
  async rewindMessage(index) {
    const sessionId = this.session?.session;
    if (!sessionId) return;
    try {
      const out = await this.api.tool("rewind_session", { to_index: index }, sessionId);
      if (out.error) {
        this.warn(String(out.detail ?? out.error));
        return;
      }
      this.chat.applyRewind(out.messages ?? [], Number(out.min_rewind_index ?? 0));
    } catch (e) {
      this.warn(e.message);
    }
  }
  /** Branching switches to the new thread straight away, the same way
   *  picking a thread from Sessions does - there is nothing else to show
   *  until it's the one open. */
  async branchMessage(index) {
    const sessionId = this.session?.session;
    if (!sessionId) return;
    try {
      const out = await this.api.tool("branch_session", { to_index: index }, sessionId);
      if (out.error) {
        this.warn(String(out.detail ?? out.error));
        return;
      }
      await this.attach(String(out.branched));
    } catch (e) {
      this.warn(e.message);
    }
  }
  /** Put text into the message box (Obsidian: "Ask about this note"). */
  insert(text) {
    this.show("chat");
    const gap = this.input.value && !this.input.value.endsWith(" ") ? " " : "";
    this.input.value += gap + text;
    this.input.focus();
  }
  dispose() {
    this.stopEvents?.();
    this.stopEvents = null;
    this.bodyObserver?.disconnect();
    this.bodyObserver = null;
    this.settings.stopHealth();
    this.staging.dispose();
    this.pane.dispose();
    this.attachPanel.dispose();
    this.tile.dispose();
    this.popovers().forEach((p) => p.dispose());
    this.ids.release();
    document.removeEventListener("keydown", this.onDocumentKey);
    document.removeEventListener("click", this.onDocumentClick);
  }
  async reset() {
    try {
      await this.api.post("/api/chat/reset");
    } catch (e) {
      this.warn(e.message);
    }
  }
};
function paneIcon() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of [
    ["rect", { x: "1.5", y: "2.5", width: "13", height: "11", rx: "2" }],
    ["line", { x1: "9", y1: "2.5", x2: "9", y2: "13.5" }]
  ]) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", "currentColor");
    el.setAttribute("stroke-width", "1.3");
    svg.append(el);
  }
  return svg;
}
function fileIcon() {
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "13");
  svg.setAttribute("height", "13");
  svg.setAttribute("aria-hidden", "true");
  for (const [tag, attrs] of [
    ["path", { d: "M3.5 1.8h6l3 3v8.7a.7.7 0 0 1-.7.7h-8.3a.7.7 0 0 1-.7-.7V2.5a.7.7 0 0 1 .7-.7Z" }],
    ["path", { d: "M9.5 1.8v2.6a.7.7 0 0 0 .7.7h2.3" }]
  ]) {
    const el = document.createElementNS(ns, tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    el.setAttribute("fill", "none");
    el.setAttribute("stroke", "currentColor");
    el.setAttribute("stroke-width", "1.2");
    el.setAttribute("stroke-linejoin", "round");
    svg.append(el);
  }
  return svg;
}
function remember2(key, value) {
  try {
    localStorage.setItem(`librarian:${key}`, value);
  } catch {
  }
}
function recall(key) {
  try {
    return localStorage.getItem(`librarian:${key}`) ?? "";
  } catch {
    return "";
  }
}
function mount(root, opts) {
  root.classList.add(cls("librarian-root"), cls(`host-${opts.host}`));
  const app = new App(root, opts);
  void app.start();
  return { command: (id) => app.command(id), insert: (text) => app.insert(text), dispose: () => app.dispose() };
}
var auto = typeof document !== "undefined" ? document.getElementById("librarian-root") : null;
if (auto) {
  const token2 = $(document, "meta[name=librarian-token]")?.content ?? "";
  mount(auto, { base: "", token: token2, host: "website" });
}

// src/core.ts
var import_node_child_process = require("node:child_process");
var import_node_crypto = require("node:crypto");
var import_promises = require("node:fs/promises");
var os = __toESM(require("node:os"));
var path = __toESM(require("node:path"));
var KEY_ENV = {
  deepinfra: "DEEPINFRA_API_KEY",
  openai: "OPENAI_API_KEY",
  anthropic: "ANTHROPIC_API_KEY"
};
var STOP_EXIT_MS = 25e3;
var CoreNotFound = class extends Error {
};
var StaleCoreLease = class extends Error {
};
function loopbackUrl(value) {
  try {
    const parsed = new URL(value);
    const host = parsed.hostname.toLowerCase();
    if (parsed.protocol !== "http:" || !["127.0.0.1", "localhost", "::1", "[::1]"].includes(host)) return null;
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}
function discoveryPath(vaultPath) {
  let canonical = path.resolve(vaultPath);
  if (process.platform === "win32") canonical = canonical.toLowerCase();
  const key = (0, import_node_crypto.createHash)("sha256").update(canonical, "utf8").digest("hex").slice(0, 24);
  const explicit = process.env.LIBRARIAN_CONFIG_DIR;
  const base = explicit || path.join(
    process.env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config"),
    "resource-librarian"
  );
  return path.join(base, "cores", `${key}.json`);
}
function samePath(left, right) {
  let a = path.resolve(left);
  let b = path.resolve(right);
  if (process.platform === "win32") {
    a = a.toLowerCase();
    b = b.toLowerCase();
  }
  return a === b;
}
async function exactCoreIsRunning(corePath, vaultPath, expected, expectedUrl) {
  const [exe, prefix] = command(corePath);
  return new Promise((resolve2) => {
    let child;
    try {
      child = (0, import_node_child_process.spawn)(
        exe,
        [...prefix, "host", "status", "--vault", vaultPath],
        { env: process.env, stdio: ["ignore", "pipe", "pipe"], windowsHide: true }
      );
    } catch {
      resolve2(false);
      return;
    }
    let out = "";
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve2(value);
    };
    const timer = setTimeout(() => {
      child.kill();
      finish(false);
    }, 5e3);
    child.on("error", () => finish(false));
    child.stdout?.on("data", (data) => {
      out += String(data);
      if (out.length > 1e6) {
        child.kill();
        finish(false);
      }
    });
    child.on("close", (code) => {
      if (code !== 0) {
        finish(false);
        return;
      }
      try {
        const status = JSON.parse(out);
        const matched = Array.isArray(status.cores) && status.cores.some((row) => Number(row.pid) === expected.pid && row.process_start === expected.process_start && typeof row.vault === "string" && samePath(row.vault, vaultPath) && typeof row.url === "string" && loopbackUrl(row.url) === expectedUrl);
        finish(Boolean(matched));
      } catch {
        finish(false);
      }
    });
  });
}
async function discover(vaultPath, corePath = "") {
  try {
    const row = JSON.parse(await (0, import_promises.readFile)(discoveryPath(vaultPath), "utf8"));
    if (!row || typeof row.url !== "string" || typeof row.token !== "string" || typeof row.pid !== "number" || typeof row.process_start !== "string" || !row.process_start || String(row.protocol_version) !== "2") return null;
    if (!samePath(String(row.vault || ""), vaultPath)) return null;
    const url = loopbackUrl(row.url);
    if (!url) return null;
    if (!await exactCoreIsRunning(corePath, vaultPath, row, url)) return null;
    return { url, token: row.token, owned: false };
  } catch {
    return null;
  }
}
function command(corePath) {
  const exe = corePath.trim() || "resource-librarian";
  return /^python[\d.]*(\.exe)?$/i.test(path.basename(exe)) ? [exe, ["-m", "resource_librarian"]] : [exe, []];
}
async function start(corePath, vaultPath, keys, options = {}) {
  const timeoutMs = options.timeoutMs ?? 2e4;
  const active = await discover(vaultPath, corePath);
  if (active) return active;
  const token2 = (0, import_node_crypto.randomBytes)(24).toString("base64url");
  const [exe, prefix] = command(corePath);
  const env = {
    ...process.env,
    LIBRARIAN_TOKEN: token2,
    LIBRARIAN_SECRET_SOURCE: "obsidian",
    // This grants the child exactly one authenticated
    // graceful-stop endpoint for an explicit key rotation.
    // It never ties Core lifetime to this view or its stdio.
    LIBRARIAN_HOST_MANAGED: "1"
  };
  for (const name of Object.values(KEY_ENV)) delete env[name];
  for (const [provider, name] of Object.entries(KEY_ENV)) {
    if (keys[provider]) env[name] = keys[provider];
  }
  return new Promise((resolve2, reject) => {
    let child;
    try {
      const args = [...prefix, "--vault", vaultPath, "app", "--port", "0"];
      if (options.takeover) args.push("--takeover");
      child = (0, import_node_child_process.spawn)(
        exe,
        args,
        { env, stdio: ["pipe", "pipe", "pipe"], windowsHide: true }
      );
    } catch (e) {
      reject(new CoreNotFound(String(e)));
      return;
    }
    let out = "";
    let err = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`the core did not start within ${timeoutMs / 1e3}s. ${err.slice(-400)}`));
    }, timeoutMs);
    child.on("error", (e) => {
      clearTimeout(timer);
      reject(e.code === "ENOENT" ? new CoreNotFound(`${exe} was not found`) : e);
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      for (const line of `${out}
${err}`.split(/\r?\n/).reverse()) {
        try {
          const row = JSON.parse(line);
          if (row?.error === "stale_vault_lease") {
            reject(new StaleCoreLease(String(row.detail || "a stopped Core left stale lease metadata")));
            return;
          }
        } catch {
        }
      }
      reject(new Error(`the core exited (${code}). ${err.slice(-400) || out.slice(-400)}`));
    });
    child.stderr?.on("data", (d) => {
      err += String(d);
    });
    child.stdout?.on("data", (d) => {
      out += String(d);
      const line = out.split("\n").find((l) => l.includes('"listening"'));
      if (!line) return;
      clearTimeout(timer);
      try {
        const url = loopbackUrl(String(JSON.parse(line).listening));
        if (!url) throw new Error("the Core reported a non-loopback listening URL");
        resolve2({ url, token: token2, process: child, owned: true });
      } catch (e) {
        reject(e);
      }
    });
  });
}

// src/main.ts
var VIEW = "librarian-view";
var PROVIDER_LABEL = { deepinfra: "DeepInfra", openai: "OpenAI", anthropic: "Anthropic" };
var DEFAULTS = { corePath: "", secrets: {} };
var LibrarianPlugin = class extends import_obsidian.Plugin {
  constructor() {
    super(...arguments);
    this.settings = { ...DEFAULTS };
    this.core = null;
    this.starting = null;
    this.lastMarkdownPath = "";
    this.dirtyAt = /* @__PURE__ */ new Map();
  }
  async onload() {
    this.settings = { ...DEFAULTS, ...await this.loadData() };
    this.registerView(VIEW, (leaf) => new LibrarianView(leaf, this));
    this.addRibbonIcon("library", "Open the librarian", () => this.activate());
    for (const [id, name] of Object.entries(COMMANDS)) {
      this.addCommand({ id: "command-" + id, name, checkCallback: (checking) => {
        if (document.activeElement?.closest("textarea, input, select, [contenteditable=true], .cm-content")) return false;
        if (!checking) void this.activate().then((view) => view?.command(id));
        return true;
      } });
    }
    this.addCommand({ id: "open", name: "Open the librarian", callback: () => this.activate() });
    this.addCommand({
      id: "ask-about-note",
      name: "Ask about this note",
      checkCallback: (checking) => {
        const file = this.app.workspace.getActiveFile();
        if (!file || file.extension !== "md") return false;
        if (!checking) void this.askAbout(file);
        return true;
      }
    });
    this.registerEvent(this.app.vault.on("modify", (file) => {
      if (file instanceof import_obsidian.TFile && file.extension === "md") {
        this.lastMarkdownPath = file.path;
        this.dirtyAt.set(file.path, Date.now());
      }
    }));
    this.registerEvent(this.app.workspace.on("active-leaf-change", () => {
      const file = this.app.workspace.getActiveFile();
      if (file?.extension === "md") this.lastMarkdownPath = file.path;
    }));
    this.app.workspace.onLayoutReady(() => {
      const leaves = this.app.workspace.getLeavesOfType(VIEW);
      if (leaves.length && !leaves.some((leaf) => leaf.getRoot() === this.app.workspace.rootSplit)) {
        void this.activate();
      }
    });
    this.addSettingTab(new LibrarianSettings(this.app, this));
  }
  onunload() {
    this.core = null;
  }
  vaultPath() {
    const adapter = this.app.vault.adapter;
    if (!(adapter instanceof import_obsidian.FileSystemAdapter)) throw new Error("the librarian needs a vault on disk");
    return adapter.getBasePath();
  }
  keys() {
    const out = {};
    for (const provider of Object.keys(KEY_ENV)) {
      const id = this.settings.secrets[provider];
      const value = id ? this.app.secretStorage.getSecret(id) : null;
      if (value) out[provider] = value;
    }
    return out;
  }
  ensureCore(takeover = false) {
    if (this.core) return Promise.resolve(this.core);
    if (!this.starting) {
      this.starting = start(this.settings.corePath, this.vaultPath(), this.keys(), { takeover }).then((running) => {
        this.core = running;
        running.process?.on("exit", () => {
          if (this.core === running) this.core = null;
        });
        return running;
      }).finally(() => {
        this.starting = null;
      });
    }
    return this.starting;
  }
  async stopCore() {
    const core = this.core;
    if (!core?.process) {
      this.core = null;
      return;
    }
    const child = core.process;
    let detail = {};
    try {
      const response = await fetch(`${core.url}/api/host/stop`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Librarian-Token": core.token,
          "Origin": "app://obsidian.md"
        },
        body: JSON.stringify({ force: false })
      });
      try {
        detail = await response.json();
      } catch {
        detail = {};
      }
      if (!response.ok) {
        const active = detail.active ? " Resolve or explicitly close the active work in Librarian first." : "";
        throw new Error(`${String(detail.error || "the Core refused to stop cleanly")}.${active}`);
      }
    } catch (e) {
      throw new Error(`Librarian Core was not restarted: ${e.message}`);
    }
    await new Promise((resolve2, reject) => {
      if (child.exitCode !== null) {
        resolve2();
        return;
      }
      const timer = window.setTimeout(() => reject(new Error("the Core is still draining work")), STOP_EXIT_MS);
      child.once("exit", () => {
        window.clearTimeout(timer);
        resolve2();
      });
      child.once("error", (e) => {
        window.clearTimeout(timer);
        reject(e);
      });
    });
    if (this.core === core) this.core = null;
  }
  forgetCore(core) {
    if (!core || this.core === core) this.core = null;
  }
  /** Keys reach the core only when it starts, so a changed key restarts it. */
  async restartCore() {
    if (this.core && !this.core.owned) {
      throw new Error("Librarian is attached to an existing Host Core. Restart it from the Librarian Host before changing Obsidian-managed keys.");
    }
    await this.stopCore();
    for (const leaf of this.app.workspace.getLeavesOfType(VIEW)) {
      const view = leaf.view;
      if (view instanceof LibrarianView) await view.render();
    }
  }
  async activate() {
    const existing = this.app.workspace.getLeavesOfType(VIEW);
    let leaf = existing.find((candidate) => candidate.getRoot() === this.app.workspace.rootSplit);
    if (!leaf) {
      leaf = this.app.workspace.getLeaf("tab");
      await leaf.setViewState({ type: VIEW, active: true });
      for (const old of existing) old.detach();
    }
    await this.app.workspace.revealLeaf(leaf);
    return leaf.view instanceof LibrarianView ? leaf.view : null;
  }
  activeMarkdownPath() {
    const active = this.app.workspace.getActiveViewOfType(import_obsidian.MarkdownView)?.file ?? this.app.workspace.getActiveFile();
    if (active?.extension === "md") this.lastMarkdownPath = active.path;
    return this.lastMarkdownPath;
  }
  documentIsDirty(path2) {
    const touched = this.dirtyAt.get(path2) ?? 0;
    if (Date.now() - touched > 1e4) {
      this.dirtyAt.delete(path2);
      return false;
    }
    return true;
  }
  async askAbout(file) {
    const view = await this.activate();
    view?.insert(`[[${file.basename}]] `);
  }
};
var LibrarianView = class extends import_obsidian.ItemView {
  constructor(leaf, plugin) {
    super(leaf);
    this.plugin = plugin;
    this.mounted = null;
    this.heartbeatTimer = null;
    this.heartbeatPath = "";
  }
  getViewType() {
    return VIEW;
  }
  getDisplayText() {
    return "Librarian";
  }
  getIcon() {
    return "library";
  }
  async onOpen() {
    await this.render();
  }
  async render(takeover = false) {
    this.mounted?.dispose();
    this.mounted = null;
    this.stopHeartbeat(this.plugin.core ?? void 0);
    const root = this.contentEl;
    root.empty();
    root.addClass("librarian-view");
    root.createEl("p", { text: "Starting the librarian\u2026" });
    let core;
    try {
      core = await this.plugin.ensureCore(takeover);
    } catch (e) {
      root.empty();
      const box = root.createDiv({ cls: "librarian-missing" });
      if (e instanceof CoreNotFound) {
        box.createEl("p", { text: "The Librarian core is not installed, or Obsidian can't find it." });
        box.createEl("p", { text: "Install it with: pip install 'resource-librarian[mcp]' \u2014 then set its path in this plugin's settings if Obsidian doesn't find it on its own (apps started from the dock often don't see your shell's PATH)." });
      } else {
        box.createEl("p", { text: `The core did not start: ${e.message}` });
      }
      const staleLease = e instanceof StaleCoreLease;
      if (staleLease) box.createEl("p", { text: "The previous Core is no longer running. Recovery will verify the OS lock again and replace only its stale lease metadata." });
      new import_obsidian.Setting(box).addButton((b) => b.setButtonText(staleLease ? "Recover and try again" : "Try again").onClick(() => this.render(staleLease)));
      return;
    }
    try {
      const response = await fetch(`${core.url}/api/meta`, {
        headers: { "X-Librarian-Token": core.token }
      });
      const meta = await response.json();
      if (!response.ok || String(meta.protocol_version) !== "2") {
        throw new Error(`Core protocol ${String(meta.protocol_version ?? "unknown")} is not compatible with this adapter.`);
      }
    } catch (e) {
      this.plugin.forgetCore(core);
      root.empty();
      const box = root.createDiv({ cls: "librarian-missing" });
      box.createEl("p", { text: `The Librarian Core cannot mount safely: ${e.message}` });
      new import_obsidian.Setting(box).addButton((b) => b.setButtonText("Try again").onClick(() => this.render(false)));
      return;
    }
    root.empty();
    const host = root.createDiv({ cls: "librarian-host" });
    this.mounted = mount(host, {
      base: core.url,
      token: core.token,
      host: "obsidian",
      openNote: (_name, notePath) => {
        void this.app.workspace.openLinkText(notePath, "", false);
      },
      openElsewhere: () => {
        window.open(`${core.url}/`);
      },
      manageKeys: () => {
        const setting = this.app.setting;
        setting?.open?.();
        setting?.openTabById?.(this.plugin.manifest.id);
      }
    });
    this.startHeartbeat(core);
  }
  command(id) {
    this.mounted?.command(id);
  }
  insert(text) {
    this.mounted?.insert(text);
  }
  async onClose() {
    this.mounted?.dispose();
    this.mounted = null;
    this.stopHeartbeat(this.plugin.core ?? void 0);
  }
  startHeartbeat(core) {
    const send = async () => {
      const path2 = this.plugin.activeMarkdownPath();
      if (this.heartbeatPath && this.heartbeatPath !== path2) {
        await fetch(`${core.url}/api/documents/release`, {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token },
          body: JSON.stringify({ path: this.heartbeatPath, editor: "Obsidian" })
        }).catch(() => void 0);
      }
      this.heartbeatPath = path2;
      if (!path2 || !this.plugin.documentIsDirty(path2)) return;
      await fetch(`${core.url}/api/documents/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token },
        body: JSON.stringify({ path: path2, editor: "Obsidian", dirty: true })
      }).catch(() => void 0);
    };
    void send();
    this.heartbeatTimer = window.setInterval(() => {
      void send();
    }, 2e3);
  }
  stopHeartbeat(core) {
    if (this.heartbeatTimer !== null) window.clearInterval(this.heartbeatTimer);
    this.heartbeatTimer = null;
    const path2 = this.heartbeatPath;
    this.heartbeatPath = "";
    if (path2 && core) {
      void fetch(`${core.url}/api/documents/release`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Librarian-Token": core.token },
        body: JSON.stringify({ path: path2, editor: "Obsidian" })
      }).catch(() => void 0);
    }
  }
};
var LibrarianSettings = class extends import_obsidian.PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }
  display() {
    const { containerEl } = this;
    containerEl.empty();
    new import_obsidian.Setting(containerEl).setName("Core").setDesc("The installed core: `resource-librarian`, or a Python that has the package. Leave empty to find it on the path.").addText((t) => t.setPlaceholder("resource-librarian").setValue(this.plugin.settings.corePath).onChange(async (value) => {
      this.plugin.settings.corePath = value;
      await this.plugin.saveData(this.plugin.settings);
    }));
    new import_obsidian.Setting(containerEl).setHeading().setName("Keys");
    containerEl.createEl("p", {
      cls: "setting-item-description",
      text: "Choose a secret from Obsidian's secret storage for each provider. The key stays there; the core receives it in memory when it starts, and it never reaches a note, a log or the page."
    });
    for (const [provider, label] of Object.entries(PROVIDER_LABEL)) {
      new import_obsidian.Setting(containerEl).setName(label).addComponent((el) => new import_obsidian.SecretComponent(this.app, el).setValue(this.plugin.settings.secrets[provider] ?? "").onChange(async (id) => {
        this.plugin.settings.secrets[provider] = id;
        await this.plugin.saveData(this.plugin.settings);
        try {
          await this.plugin.restartCore();
          new import_obsidian.Notice(`Librarian: ${label} key updated; the core restarted.`);
        } catch (e) {
          new import_obsidian.Notice(e.message);
        }
      }));
    }
    new import_obsidian.Setting(containerEl).setName("Restart the core").setDesc(this.plugin.core ? `Running at ${this.plugin.core.url}` : "Not running.").addButton((b) => b.setButtonText("Restart").onClick(async () => {
      try {
        await this.plugin.restartCore();
      } catch (e) {
        new import_obsidian.Notice(e.message);
      }
      this.display();
    }));
  }
};
