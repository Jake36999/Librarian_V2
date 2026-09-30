"use strict";
var Librarian = (() => {
  var __defProp = Object.defineProperty;
  var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
  var __getOwnPropNames = Object.getOwnPropertyNames;
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
  var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

  // src/main.ts
  var main_exports = {};
  __export(main_exports, {
    mount: () => mount
  });

  // src/api.ts
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
    async request(method, path, body) {
      const response = await fetch(this.opts.base + path, {
        method,
        headers: { "Content-Type": "application/json", "X-Librarian-Token": this.opts.token },
        body: body === void 0 ? void 0 : JSON.stringify(body)
      });
      const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
      if (!response.ok) throw new ApiError(response.status, data);
      return data;
    }
    get(path) {
      return this.request("GET", path);
    }
    post(path, body = {}) {
      return this.request("POST", path, body);
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
    /** The event stream. Reconnects from the last sequence number seen. */
    events(onEvent, onStatus) {
      let last = 0;
      let source = null;
      let closed = false;
      const open = () => {
        const url = `${this.opts.base}/api/events?token=${encodeURIComponent(this.opts.token)}&since=${last}`;
        source = new EventSource(url);
        source.onopen = () => onStatus(true);
        source.onmessage = () => void 0;
        source.onerror = () => {
          onStatus(false);
          source?.close();
          if (!closed) setTimeout(open, 1500);
        };
        const handle = (message) => {
          const event = JSON.parse(message.data);
          if (event.seq <= last) return;
          last = event.seq;
          onEvent(event);
        };
        for (const type of EVENT_TYPES) source.addEventListener(type, handle);
      };
      open();
      return () => {
        closed = true;
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
    "reply_reviewed"
  ];

  // src/dom.ts
  function h(tag, attrs = {}, ...children) {
    const el = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === void 0 || value === false) continue;
      if (key.startsWith("on") && typeof value === "function") {
        el.addEventListener(key.slice(2), value);
      } else if (key === "class") {
        el.className = String(value);
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
  var $ = (root, sel) => root.querySelector(sel);
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

  // src/attach.ts
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

  // src/markdown.ts
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

  // src/chat.ts
  function icon(paths) {
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
  var copyIcon = () => icon([
    ["rect", { x: "3", y: "4.5", width: "8", height: "9.5", rx: "1.3" }],
    ["path", { d: "M6 4.5V3a1.3 1.3 0 0 1 1.3-1.3H12A1.3 1.3 0 0 1 13.3 3v8A1.3 1.3 0 0 1 12 12.3h-1" }]
  ]);
  var retryIcon = () => icon([
    ["path", { d: "M3 8a5 5 0 1 1 1.7 3.75" }],
    ["path", { d: "M3 11.8V8.1h3.7" }]
  ]);
  var rewindIcon = () => icon([
    ["path", { d: "M8.5 3 3.3 8l5.2 5" }],
    ["path", { d: "M13 3v10" }]
  ]);
  var branchIcon = () => icon([
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
    handle(event) {
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
          if (result.error) line.classList.add("refused");
          if (!line.isConnected) this.append(line);
          if (result.session) this.hooks.onSession(result.session);
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
            if (row) clear(row, h("em", {}, sentence(String(event.reason ?? event.outcome))));
          }
          break;
        }
        case "reply_reviewed": {
          const challenged = event.challenged ?? [];
          const held = Number(event.held ?? 0), unchecked = Number(event.unchecked ?? 0);
          if (!held && !challenged.length && !unchecked && !event.status) break;
          this.append(h(
            "div",
            { class: "note reviewed" },
            event.status ? `The review could not run (${event.status}).` : `Checked against the notes it cites: ${held} held${unchecked ? `, ${unchecked} unchecked` : ""}${challenged.length ? `, ${challenged.length} challenged` : ""}.`,
            challenged.length ? h("ul", {}, challenged.map((c) => h(
              "li",
              {},
              `\u2691 \u201C${c.claim}\u201D \u2014 `,
              h("span", { class: "dim" }, c.counter_quote ? `${c.reason} [[${c.note}]] says: \u201C${c.counter_quote}\u201D` : `not found in [[${c.note}]]. ${c.reason}`)
            ))) : null,
            challenged.length ? h("div", { class: "dim small" }, "The librarian sees these challenges in its next reply.") : null
          ));
          break;
        }
        case "turn_done":
          this.setWorking(false);
          if (event.stopped === "max_steps") {
            this.append(h(
              "div",
              { class: "error" },
              "Stopped after the step limit for one turn. ",
              "Say \u201Ccontinue\u201D to carry on, or ask for a summary of where it got to."
            ));
          } else if (event.stopped === "provider_error") {
            this.append(h(
              "div",
              { class: "error" },
              `The model could not answer: ${event.error}. `,
              "Check the key and the model under + \u2192 Connections, then retry.",
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
              )
            ));
          }
          this.sessionOutcome(event.session ?? null);
          this.hooks.onSession(event.session ?? null);
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
          if (card && !card.classList.contains("done")) {
            card.classList.add("done");
            const row = card.querySelector(".row");
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
    sessionOutcome(session) {
      if (!session) return;
      this.outcomeCard?.remove();
      if (session.status === "closed") {
        this.outcomeCard = h(
          "div",
          { class: "session-outcome closed", role: "status" },
          h("strong", {}, "Thread closed"),
          session.summary ? h("div", {}, String(session.summary)) : null,
          session.gaps ? h("div", { class: "dim" }, `Gaps: ${session.gaps}`) : null
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
        parked ? h("p", { class: "dim" }, "Reopen this thread from Sessions to continue.") : h("button", { class: "ghost", onclick: () => this.hooks.continueSession() }, "Continue from next step")
      );
      this.append(this.outcomeCard);
    }
    permission(event) {
      const args = event.arguments ?? {};
      const detail = Object.entries(args).slice(0, 3).map(([k, v]) => `${k}: ${v}`).join(" \xB7 ");
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
        detail ? h("div", { class: "dim" }, detail) : null,
        h(
          "div",
          { class: "row" },
          h("button", { onclick: answer("allow_once") }, "Allow once"),
          h("button", { onclick: answer("allow_session") }, "Allow for this session"),
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
          card.classList.add("done");
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
        questions.length ? h("h3", {}, "Waiting for you") : null,
        questions.map((q) => this.question(session, q)),
        h("h3", {}, "Next"),
        h("p", {}, String(session.next ?? "")),
        (session.open_items ?? []).length ? h("h3", {}, "Open") : null,
        (session.open_items ?? []).length ? h("ul", {}, session.open_items.map((t) => h("li", {}, t))) : null,
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
      if ((q.options ?? []).length) {
        box.append(h("div", { class: "row" }, q.options.map((o) => h("button", { onclick: () => send(o) }, o))));
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
  function pathName(path) {
    return path.split("/").pop().replace(/\.md$/, "");
  }
  function sentence(text) {
    const t = text.trim();
    return t ? t[0].toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? "" : ".") : "";
  }
  function summarise(tool, r, openNote) {
    if (r.error === "refused") return h("span", {}, `refused (${r.refused}): ${r.detail ?? ""}`);
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

  // src/panels.ts
  var MODES = [
    ["plan", "Plan", "Reads and searches. Writes are refused: the librarian proposes instead."],
    ["ask", "Ask permission", "Every write pauses for you, with Allow once, Allow for this session, or Deny."],
    ["auto", "Auto", "Writes within the phase gate and the vault's settings. Sensitive material still waits for you."]
  ];
  var ACTIONS = {
    "clear-enrichment-backlog": ["Clear enrichment backlog", "Fetch, describe and stage everything queued. Background, cancellable."],
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
    const parts = [];
    if (p.suggested_tier) parts.push(String(p.suggested_tier).replace(/_/g, " "));
    const bestFor = p.best_for ?? [];
    if (bestFor.length) parts.push(bestFor.map((t) => String(t).replace(/_/g, " ")).join(", "));
    if (p.context_length) parts.push(`${Math.round(p.context_length / 1e3)}k ctx`);
    if (p.price_input_per_1m || p.price_output_per_1m) {
      parts.push(`$${p.price_input_per_1m ?? 0} / $${p.price_output_per_1m ?? 0} per 1M`);
    }
    parts.push(p.tool_calling ? "tool calling" : "no tool calling");
    return parts.filter(Boolean).join(" \xB7 ");
  }
  var Popover = class {
    constructor(id, label, button) {
      this.button = button;
      this.el = h("div", { class: "popover", id, hidden: true, role: "dialog", "aria-label": label });
      button.setAttribute("aria-haspopup", "true");
      button.setAttribute("aria-expanded", "false");
    }
    get open() {
      return !this.el.hidden;
    }
    show(on) {
      this.el.hidden = !on;
      this.button.setAttribute("aria-expanded", String(on));
      if (on) this.el.querySelector("input, button")?.focus();
    }
  };
  function renderModes(pop, api, mode, queued, pipelines, report, needs = {}) {
    const group = h(
      "div",
      { role: "radiogroup", "aria-label": "Permission mode" },
      MODES.map(([value, label, help]) => h(
        "label",
        { class: "opt" },
        h("input", {
          type: "radio",
          name: "librarian-mode",
          value,
          checked: value === mode,
          onchange: async () => {
            try {
              await api.post("/api/mode", { mode: value });
            } catch (e) {
              report(e.message);
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
    const start = (name) => async () => {
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
        el.id = `queue-${name}-${key}`;
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
          h("button", { class: "ghost", onclick: () => renderModes(pop, api, mode, queued, pipelines, report, needs) }, "Back")
        )
      );
    };
    clear(
      pop.el,
      h("h4", {}, "Permission mode"),
      group,
      h("h4", { class: "gap" }, "Queue an action"),
      queued.map((name) => h(
        "button",
        { class: "menuitem", onclick: start(name) },
        (ACTIONS[name] ?? [name])[0],
        h("small", {}, (ACTIONS[name] ?? ["", "A pipeline."])[1])
      )),
      extra.length ? h("h4", { class: "gap" }, "This vault's pipelines") : null,
      extra.map((name) => h("button", { class: "menuitem", onclick: start(name) }, name))
    );
  }
  var ModelTile = class {
    constructor(pop, api, tiers, keysSaved, setTiers = () => {
    }) {
      this.pop = pop;
      this.api = api;
      this.tiers = tiers;
      this.keysSaved = keysSaved;
      this.setTiers = setTiers;
      this.listings = /* @__PURE__ */ new Map();
      this.filter = "";
      this.toast = "";
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
    }
    async save(tiers) {
      try {
        await this.api.post("/api/tiers", { tiers });
        this.setTiers(tiers);
      } catch (e) {
        this.toast = e.message;
      }
    }
    async clearAll() {
      this.toast = "Selection cleared. Click models in order again.";
      await this.save([]);
      this.render();
    }
    async pick(provider, model) {
      const tiers = this.tiers();
      const at = tiers.findIndex((t) => t.provider === provider && t.model === model);
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
          { class: "slot" },
          h("span", { class: "badge" }, String(i + 1)),
          t ? `${t.model} \xB7 ${PROVIDERS[t.provider] ?? t.provider}` : h("span", { class: "dim" }, fallback),
          h("span", { class: "dim" }, ` \xB7 ${ROLES[i]}`)
        );
      });
      const filter = h("input", {
        type: "search",
        placeholder: "Filter models",
        "aria-label": "Filter models",
        value: this.filter,
        oninput: (e) => {
          this.filter = e.target.value;
          this.renderGrids(grids);
        }
      });
      const grids = h("div", {});
      clear(
        this.pop.el,
        h(
          "div",
          { class: "tierbar" },
          h("strong", {}, "Chat models"),
          h("span", { class: "dim" }, "Click in order: 1 leads, 2 writes notes, 3 does small tasks. Right-click a chosen model to clear all.")
        ),
        h(
          "div",
          { class: "tierbar" },
          slots,
          tiers.length ? h("button", { class: "ghost", onclick: () => this.clearAll() }, "Clear selection") : null
        ),
        this.toast ? h("div", { class: "toast", role: "status" }, this.toast) : null,
        filter,
        grids,
        h("h4", {}, "Embeddings \xB7 Speech to text \xB7 Text to speech"),
        h("p", { class: "note locked" }, "\u{1F512} These need their own single-choice pickers (with the re-embedding cost shown first for Embeddings). They arrive with catalogue upkeep (M4b)."),
        h("p", { class: "note" }, "Models come from each provider's live listing. A profiled model (a Source of kind model) shows its suggested tier and best-for tags (a first guess to confirm or correct), plus context, price and tool calling; an unprofiled one can be profiled, which stages it for your review like any other source.")
      );
      this.renderGrids(grids);
    }
    renderGrids(host) {
      const tiers = this.tiers();
      const needle = this.filter.toLowerCase();
      clear(host, Object.entries(PROVIDERS).map(([p, label]) => {
        const listing = this.listings.get(p) ?? { status: "\u2026", models: [] };
        const models = listing.models.filter((m) => !needle || String(m.id).toLowerCase().includes(needle));
        const status = listing.status === "ready" ? `${listing.models.length} model${listing.models.length === 1 ? "" : "s"}` : listing.status === "no key" ? "no key saved (+ \u2192 Connections)" : listing.status === "offline" ? "offline: the local server is not running" : listing.error ? `error: ${listing.error}` : listing.status;
        return h(
          "section",
          { class: "provider" },
          h("h4", {}, h("span", { class: `dot ${listing.status === "ready" ? "" : listing.status === "no key" ? "nokey" : "off"}` }), `${label} \xB7 ${status}`),
          models.length ? h("div", { class: "grid" }, models.slice(0, 60).map((m) => {
            const at = tiers.findIndex((t) => t.provider === p && t.model === m.id);
            const card = h(
              "button",
              {
                class: `card${at >= 0 ? " sel" : ""}`,
                "aria-pressed": at >= 0 ? "true" : "false",
                title: m.profile && m.profile.tool_calling === false ? "Profiled as not supporting tool calling: can still lead as tier 2 or 3" : "",
                onclick: () => this.pick(p, m.id),
                oncontextmenu: (e) => {
                  if (at >= 0) {
                    e.preventDefault();
                    this.clearAll();
                  }
                },
                onkeydown: (e) => {
                  if (at >= 0 && e.key === "Delete") this.clearAll();
                },
                ontouchstart: () => {
                  if (at >= 0) this.press = window.setTimeout(() => this.clearAll(), 600);
                },
                ontouchend: () => window.clearTimeout(this.press)
              },
              at >= 0 ? h("span", { class: "badge" }, String(at + 1)) : null,
              h("div", { class: "name" }, m.id),
              h("div", { class: "meta" }, profileMeta(m))
            );
            return h(
              "div",
              { class: "card-wrap" },
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
    const go = async (path, force = false) => {
      clear(status, `Opening ${path}\u2026`);
      try {
        await api.post("/api/library/switch", { path, force });
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
            h("button", { class: "ghost", onclick: () => void go(path, true) }, "Switch anyway - let it finish in the background"),
            h("small", {}, " Unanswered questions time out and park their thread, so it can be resumed later.")
          );
        } else {
          clear(status, h("span", { class: "error" }, err.message));
        }
      }
    };
    try {
      const out = await api.get("/api/libraries");
      const rows = out.libraries ?? [];
      const path = h("input", {
        type: "text",
        class: "f",
        placeholder: "A library's folder, e.g. D:\\Libraries\\History",
        "aria-label": "Library folder path"
      });
      path.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && path.value.trim()) void go(path.value.trim());
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
            onclick: async () => {
              await api.post("/api/libraries/forget", { path: l.path }).catch(() => void 0);
              void renderLibraries(pop, api, current);
            }
          }, "\u2715")
        )) : h("p", { class: "dim" }, "Only this library so far."),
        h("h4", { class: "gap" }, "Open another library"),
        h(
          "div",
          { class: "row2 tight" },
          path,
          h("button", { class: "ghost", onclick: () => path.value.trim() && void go(path.value.trim()) }, "Open")
        ),
        h("small", { class: "dim" }, "One library per domain; projects live inside it as pursuits."),
        status
      );
    } catch (e) {
      clear(pop.el, h("p", { class: "error" }, `Could not list libraries: ${e.message}`));
    }
  }
  async function renderSessions(pop, api, attach, reset) {
    clear(pop.el, h("p", { class: "dim" }, "Loading threads\u2026"));
    try {
      const out = await api.tool("list_sessions");
      const rows = out.sessions ?? [];
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
        h("h4", { class: "gap" }, "Threads"),
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
          h("small", {}, `${s.purpose} \xB7 ${s.status} \xB7 ${s.phase} \xB7 ${when(s.opened_at)}`)
        )) : h("p", { class: "dim" }, "No threads yet.")
      );
    } catch (e) {
      clear(pop.el, h("p", { class: "error" }, `Could not list threads: ${e.message}`));
    }
  }

  // src/settings.ts
  var PAGES = [
    ["connections", "Connections"],
    ["context", "Working context"],
    ["mcp", "MCP servers"],
    ["library", "Library"]
  ];
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
    constructor(api, state, refresh, manageKeys) {
      this.api = api;
      this.state = state;
      this.refresh = refresh;
      this.manageKeys = manageKeys;
      this.dialog = h("dialog", { class: "settings", "aria-label": "Settings" });
      this.page = "connections";
      this.body = h("section", { class: "page" });
      this.tabs = h("div", { class: "tabs", role: "tablist" });
      this.dialog.append(
        h(
          "div",
          { class: "dlg-head" },
          h("strong", {}, "Settings"),
          h("button", { class: "ghost push", onclick: () => this.dialog.close() }, "Close")
        ),
        this.tabs,
        this.body
      );
    }
    open(page = this.page) {
      this.page = page;
      this.render();
      if (!this.dialog.open) this.dialog.showModal();
    }
    render() {
      clear(this.tabs, PAGES.map(([id, label]) => h("button", {
        role: "tab",
        "aria-selected": String(id === this.page),
        onclick: () => {
          this.page = id;
          this.render();
        }
      }, label)));
      const page = {
        connections: () => this.connections(),
        context: () => this.context(),
        mcp: () => this.mcp(),
        library: () => this.library()
      }[this.page];
      clear(this.body, page ? page() : null);
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
          h("p", { class: "note" }, "After changing a key, the plugin restarts the core so it takes effect.")
        );
      }
      const select = h(
        "select",
        { id: "lib-provider" },
        Object.entries(PROVIDERS).map(([id, label]) => h("option", { value: id }, label))
      );
      const input = h("input", { type: "password", id: "lib-key", autocomplete: "off", placeholder: "Paste a key" });
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
        checkUsage.hidden = false;
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
          status.className = `note inline ${out.check?.ok ? "ok" : "err"}`;
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
            status.className = "note inline err";
          }
        }
      };
      save.onclick = () => submit(false);
      remove.onclick = () => clear(confirmBox, h(
        "div",
        { class: "confirm" },
        `Remove the saved ${PROVIDERS[select.value]} key? It can't be recovered from here.`,
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
      const page = h(
        "div",
        {},
        h("label", { class: "f", for: "lib-provider" }, "Provider"),
        select,
        h("label", { class: "f", for: "lib-key" }, "Connect API key"),
        input,
        h("div", { class: "row2" }, save, remove, status),
        confirmBox,
        h(
          "p",
          { class: "note" },
          `Keys are kept by the core (${this.state().key_backend ?? "securely"}), never in the vault. `,
          "They never come back to this page: only whether one is saved, and its last four characters."
        ),
        h("label", { class: "f" }, "Usage & billing"),
        h("div", { class: "row2" }, checkUsage),
        usageBox
      );
      show();
      return page;
    }
    // -- page 2 --------------------------------------------------------------
    context() {
      const s = this.state();
      const text = h("textarea", { class: "f", id: "lib-sys", placeholder: "What will you be working on?" });
      text.value = s.working_context ?? "";
      let length = s.reply_length ?? "long";
      const custom = h("input", {
        type: "text",
        placeholder: "custom",
        "aria-label": "Custom reply length",
        value: ["long", "short"].includes(length) ? "" : length
      });
      const seg = h("div", { class: "seg", role: "group", "aria-label": "In-chat responses" });
      const paint = () => clear(seg, ["long", "short"].map((v) => h("button", {
        "aria-pressed": String(length === v),
        onclick: () => {
          length = v;
          custom.value = "";
          paint();
        }
      }, v[0].toUpperCase() + v.slice(1))));
      paint();
      let stance = s.stance ?? "answer";
      const stanceSeg = h("div", { class: "seg", role: "group", "aria-label": "Stance" });
      const paintStance = () => clear(stanceSeg, ["answer", "coach"].map((v) => h("button", {
        "aria-pressed": String(stance === v),
        onclick: () => {
          stance = v;
          paintStance();
        }
      }, v[0].toUpperCase() + v.slice(1))));
      paintStance();
      const status = h("span", { class: "note inline", role: "status" });
      return h(
        "div",
        {},
        h("label", { class: "f", for: "lib-sys" }, "System prompt"),
        text,
        h("label", { class: "f" }, "In-chat responses"),
        h("div", { class: "row2 tight" }, seg, custom),
        h("label", { class: "f" }, "Stance"),
        h("div", { class: "row2 tight" }, stanceSeg),
        h("p", { class: "note" }, "Answer replies directly. Coach asks before telling and gives a hint before an answer - a `learn` session always uses Coach, whatever this is set to."),
        h("div", { class: "row2" }, h("button", { class: "primary", onclick: async () => {
          try {
            await this.api.post("/api/context", {
              working_context: text.value,
              reply_length: custom.value.trim() || length,
              stance
            });
            await this.refresh();
            status.textContent = "Saved.";
          } catch (e) {
            status.textContent = e.message;
          }
        } }, "Save"), status),
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
        status.className = "note inline";
      };
      const fail = (e) => {
        status.textContent = e.message;
        status.className = "note inline err";
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
        (s.tool_names ?? []).length ? h("div", { class: "tool-perms" }, s.tool_names.map(toolRow)) : null
      ));
      return h(
        "div",
        {},
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
    library() {
      const host = h("div", {}, h("p", { class: "dim" }, "Loading\u2026"));
      const packs = h("div", { class: "lens-packs" }, h("p", { class: "dim" }, "Loading\u2026"));
      const catalogs = h("div", { class: "model-catalogs" }, h("p", { class: "dim" }, "Loading\u2026"));
      const profile = h("div", { class: "library-profile" });
      this.api.get("/api/library").then((lib) => {
        const promo = h(
          "select",
          { id: "lib-promo" },
          [["person", "person (default): a person accepts every promotion"], ["agent", "agent: the librarian may promote, except sensitive material"]].map(([v, label]) => h("option", { value: v, selected: lib.promotion?.mode === v }, label))
        );
        const status = h("span", { class: "note inline", role: "status" });
        promo.onchange = async () => {
          try {
            await this.api.post("/api/library", { promotion_mode: promo.value });
            status.textContent = "Saved to the vault's config.";
          } catch (e) {
            status.textContent = e.message;
          }
        };
        clear(
          host,
          h("label", { class: "f", for: "lib-promo" }, "Promotion"),
          h("div", { class: "row2 tight" }, promo, status),
          h("label", { class: "f" }, "Distribution posture"),
          h("p", {}, String(lib.usage?.distribution_posture ?? "private"), h("span", { class: "dim" }, " \xB7 set in the vault's config")),
          h("label", { class: "f" }, "Clerk route"),
          h("p", {}, lib.clerk?.provider ? `configured: ${lib.clerk.provider}` : "tier 3 model, else queued"),
          h("label", { class: "f" }, "Capabilities on this install"),
          (lib.doctor ?? []).map((c) => h(
            "div",
            { class: "srv" },
            h("span", { class: `dot ${c.ok ? "" : c.required ? "off" : "nokey"}` }),
            h("span", {}, h("strong", {}, c.name), ` \xB7 ${c.detail ?? ""}`)
          )),
          profile,
          h("label", { class: "f" }, "Lens packs"),
          packs,
          h("label", { class: "f" }, "Model catalogues"),
          catalogs
        );
        void this.paintPacks(packs);
        void this.paintModelCatalogs(catalogs);
        void this.paintProfile(profile);
      }).catch((e) => clear(host, h("p", { class: "error" }, e.message)));
      return host;
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
            h("span", {}, h("strong", {}, c.provider), ` \xB7 ${c.held}/${c.models} models held`),
            c.held < c.models ? h("button", { class: "ghost", onclick: async () => {
              try {
                const r = await this.api.tool("model_catalog_adopt", { provider: c.provider });
                if (r.error) throw new Error(String(r.detail ?? r.error));
                void this.paintModelCatalogs(host, `${c.provider}: ${r.written} model(s) added${r.already_held ? `, ${r.already_held} already held` : ""}${r.failed.length ? `, ${r.failed.length} failed` : ""}.`);
              } catch (e) {
                status.textContent = e.message;
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

  // src/pane.ts
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
        title: "Plan, recent notes and folders",
        "aria-label": "Documents menu",
        "aria-haspopup": "true",
        "aria-expanded": "false"
      }, "\u22EE");
      this.menu = h("div", { class: "pane-menu", hidden: true, role: "menu" });
      this.body = h("div", { class: "pane-body" });
      this.recent = [];
      this.current = { kind: "plan" };
      this.browsing = "";
      this.menuButton.onclick = () => this.toggleMenu();
      this.el.append(
        h(
          "div",
          { class: "pane-head" },
          this.crumbs,
          h(
            "div",
            { class: "pane-actions" },
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
      document.addEventListener("click", (e) => {
        if (!this.menu.hidden && !e.composedPath().includes(this.menu) && !e.composedPath().includes(this.menuButton)) {
          this.showMenu(false);
        }
      });
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") this.showMenu(false);
      });
      this.showPlan();
    }
    get showingPlan() {
      return this.current.kind === "plan";
    }
    showPlan() {
      this.current = { kind: "plan" };
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
      this.current = { kind: "agenda" };
      clear(
        this.crumbs,
        h("span", { class: "crumb-here" }, "This week"),
        h("span", { class: "dim" }, " \xB7 open, dated tasks across the vault")
      );
      clear(this.body, h("p", { class: "dim pad" }, "Loading\u2026"));
      try {
        const out = await this.api.tool("agenda", {});
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
        clear(this.body, h("div", { class: "pad" }, h("p", { class: "error" }, e.message)));
      }
      this.body.scrollTop = 0;
    }
    /** A vault path (with or without .md) or a bare note name. */
    async open(target) {
      clear(this.body, h("p", { class: "dim pad" }, `Opening ${target}\u2026`));
      let doc;
      try {
        doc = await this.api.get(`/api/file?path=${encodeURIComponent(target)}`);
      } catch (e) {
        clear(this.crumbs, h("span", { class: "crumb-here" }, target));
        clear(this.body, h(
          "div",
          { class: "pad" },
          h("p", { class: "error" }, e.message),
          h("p", { class: "dim" }, "Names are exact. Browse with \u22EE, or ask the librarian for the path.")
        ));
        return;
      }
      this.current = { kind: "doc", path: doc.path, name: doc.name };
      this.recent = [{ path: doc.path, name: doc.name }, ...this.recent.filter((r) => r.path !== doc.path)].slice(0, RECENT);
      const project = this.currentProject();
      if (project) this.api.tool("desk_touch", { project, note: doc.name }).catch(() => void 0);
      this.paintCrumbs(doc.path);
      const rendered = render(doc.text, (t) => void this.open(t), { frontmatter: true });
      const own = Array.from(rendered.children).find((el) => !el.matches("table.props"));
      const titled = own?.tagName === "H2" && own.textContent?.trim().toLowerCase() === String(doc.name).toLowerCase();
      if (titled) own.remove();
      clear(this.body, h("article", { class: "doc" }, h("h1", { class: "doc-title" }, doc.name), rendered));
      this.body.scrollTop = 0;
    }
    paintCrumbs(path) {
      const parts = path.split("/");
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
              this.showMenu(true);
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
      const item = (label, small, action, cls = "") => h("button", {
        class: `menuitem ${cls}`,
        role: "menuitem",
        onclick: action
      }, label, small ? h("small", {}, small) : null);
      const folder = h("div", { class: "pane-folder" }, h("p", { class: "dim" }, "Loading\u2026"));
      const vault = this.vaultName();
      const obsidian = this.current.kind === "doc" && vault ? `obsidian://open?vault=${encodeURIComponent(vault)}&file=${encodeURIComponent(this.current.path)}` : "";
      const doc = this.current.kind === "doc" ? this.current : null;
      const project = this.currentProject();
      const desk = h("div", { class: "pane-desk" }, h("p", { class: "dim" }, "Loading\u2026"));
      const session = this.currentSession();
      const lenses = h("div", { class: "pane-lenses" }, h("p", { class: "dim" }, "Loading\u2026"));
      clear(
        this.menu,
        item("Plan", "the session this chat is working in", () => {
          this.showMenu(false);
          this.showPlan();
        }),
        item("This week", "open, dated tasks across the vault", () => {
          this.showMenu(false);
          void this.showAgenda();
        }),
        obsidian ? h("a", { class: "menuitem", href: obsidian, role: "menuitem" }, "Open this note in Obsidian") : null,
        doc ? item("Rename or move\u2026", "links to it across the vault follow", () => this.paintMove(doc), "move") : null,
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
      this.menu.querySelector("button")?.focus();
      try {
        const listing = await this.api.get(`/api/files?dir=${encodeURIComponent(this.browsing)}`);
        const up = listing.dir ? listing.dir.split("/").slice(0, -1).join("/") : null;
        clear(
          folder,
          h("div", { class: "folder-path" }, `/${listing.dir}`),
          up !== null ? item(`\u2191 ${up ? up.split("/").pop() : "the vault"}`, "", () => {
            this.browsing = up;
            void this.paintMenu();
          }, "dir up") : null,
          listing.entries.map((e) => e.kind === "dir" ? item(`${e.name}/`, "", () => {
            this.browsing = e.path;
            void this.paintMenu();
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
          this.body.querySelector("article.doc")?.prepend(h(
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

  // src/views.ts
  var BEST_FOR_TAGS = [
    "Talking_Fast",
    "Long_Conversations",
    "Small_Coding_Tasks",
    "Large_Coding_Tasks",
    "Long_Horizon_Tasks"
  ];
  var TIERS = ["Tier_1", "Tier_2", "Tier_3"];
  var untag = (s) => s.replace(/_/g, " ");
  var Staging = class {
    constructor(api, openNote, currentSession = () => "", onSessionUpdate = () => {
    }) {
      this.api = api;
      this.openNote = openNote;
      this.currentSession = currentSession;
      this.onSessionUpdate = onSessionUpdate;
      this.el = h("div", { class: "view staging" });
      this.list = h("div", { class: "items", role: "listbox", "aria-label": "Staged items" });
      this.detail = h("div", { class: "detail" });
      this.kind = "source";
      this.selected = "";
      // True right after a decision's outcome message is shown, until the person
      // opens something else or explicitly refreshes: an automatic reload (the
      // SSE echo of this same decision, or someone else's) must not wipe it.
      this.detailLocked = false;
      const kinds = h("div", { class: "seg", role: "group", "aria-label": "Kind" });
      const paint = () => {
        clear(kinds, [["source", "Sources"], ["lens", "Lenses"], ["concept", "Concepts"]].map(([v, label]) => h("button", { "aria-pressed": String(this.kind === v), onclick: () => {
          this.kind = v;
          paint();
          void this.load(true);
        } }, label)));
        scan.style.display = this.kind === "concept" ? "" : "none";
      };
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
      this.el.append(
        h(
          "div",
          { class: "view-head" },
          h("strong", {}, "Staging review"),
          kinds,
          h("button", { class: "ghost", onclick: () => void this.load(true) }, "Refresh"),
          scan
        ),
        h("div", { class: "split" }, this.list, this.detail)
      );
    }
    /** `reset`: an explicit visit (opening the view, Refresh, switching kind) —
     * always shows the placeholder when nothing is selected. Left false, an
     * automatic reload (another surface's decision arriving over the event
     * stream) refreshes the list without wiping a just-shown outcome message. */
    async load(reset = false) {
      if (reset) this.detailLocked = false;
      clear(this.list, h("p", { class: "dim" }, "Loading\u2026"));
      try {
        const out = await this.api.tool("staging_list", { kind: this.kind, status: "staged", limit: 50 });
        const items = out.items ?? [];
        clear(
          this.list,
          h("p", { class: "dim" }, `${out.total ?? items.length} waiting`),
          items.length ? items.map((item) => h(
            "button",
            {
              class: `item${item.id === this.selected ? " sel" : ""}`,
              role: "option",
              "aria-selected": String(item.id === this.selected),
              onclick: () => this.show(item.id)
            },
            item.sensitivity === "review" ? h("span", { class: "flag", title: "sensitive: a person decides" }, "\u2691 ") : null,
            item.name || item.id,
            h("small", {}, (item.kind === "lens" ? [item.source ? `from ${item.source}` : "", item.locator] : item.kind === "concept" ? [`${item.sources ?? 0} source${item.sources === 1 ? "" : "s"}`, `${item.usages ?? 0} usage${item.usages === 1 ? "" : "s"}`] : [
              item.topic,
              item.drafted ? "drafted" : item.reviewed ? "draft queued" : "no draft yet",
              item.deep_read ? `read ${item.deep_read}` : "",
              item.fit
            ]).filter(Boolean).join(" \xB7 "))
          )) : h("p", { class: "dim" }, "Nothing waiting.")
        );
        if (!this.selected && !this.detailLocked) {
          clear(this.detail, h("p", { class: "dim" }, "Choose an item to see its draft beside its evidence."));
        }
      } catch (e) {
        clear(this.list, h("p", { class: "error" }, e.message));
      }
    }
    async show(id) {
      this.selected = id;
      this.detailLocked = false;
      this.list.querySelectorAll(".item").forEach((b) => b.classList.remove("sel"));
      clear(this.detail, h("p", { class: "dim" }, "Loading\u2026"));
      let item;
      try {
        item = await this.api.tool("staging_show", { item_id: id });
        if (item.error) throw new Error(String(item.detail ?? item.error));
      } catch (e) {
        clear(this.detail, h("p", { class: "error" }, e.message));
        return;
      }
      if (item.kind === "lens") return this.showLens(item);
      if (item.kind === "concept") return this.showConcept(item);
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
        const btn = h("button", {
          type: "button",
          "aria-pressed": String(bestFor.has(tag)),
          onclick: () => {
            if (bestFor.has(tag)) bestFor.delete(tag);
            else bestFor.add(tag);
            btn.setAttribute("aria-pressed", String(bestFor.has(tag)));
          }
        }, untag(tag));
        return btn;
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
            bottom_line: bottom.value,
            what_it_solves: solves.value,
            ...isModel ? { fields: { best_for: Array.from(bestFor), ...suggestedTier ? { suggested_tier: suggestedTier } : {} } } : {}
          });
          const r = (out.results ?? [])[0] ?? out;
          if (out.error || r.error || r.refused) throw new Error(String(r.detail ?? r.refused ?? out.detail ?? out.error ?? r.error));
          const outcome = decision === "accept" ? r.promotion && !r.promotion.catalogued ? `Accepted: ${r.promotion.status}.` : "Accepted and catalogued." : decision === "reject" ? "Rejected." : "Deferred.";
          this.selected = "";
          if (r.session && r.session.session === this.currentSession()) this.onSessionUpdate(r.session);
          await this.load();
          this.detailLocked = true;
          clear(this.detail, h("p", { class: "ok", role: "status" }, `${item.name}: ${outcome}`));
        } catch (e) {
          clear(status, h("p", { class: "error" }, e.message));
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
      const readLine = dr ? `Deep read: ${readCount} of ${dr.chunks} parts read${dr.lenses?.length ? `, ${dr.lenses.length} lens${dr.lenses.length === 1 ? "" : "es"} staged` : ""}.` : "Only the opening of this source has been read.";
      const sections = Object.entries(item.sections ?? {}).filter(([, t]) => t);
      const queued = item.review?.queued ?? [];
      const missing = item.readiness ?? [];
      clear(
        this.detail,
        h(
          "div",
          { class: "view-head" },
          h("strong", {}, item.name),
          item.canonical_url ? h("a", { href: item.canonical_url, target: "_blank", rel: "noreferrer noopener" }, "source \u2197") : null
        ),
        item.sensitivity === "review" ? h("p", { class: "warn" }, "\u2691 Marked sensitive: only a person accepts it, and only a person clears the mark.") : null,
        item.revision_of ? h(
          "p",
          { class: "note" },
          "A revision of an accepted note, ",
          h("a", { class: "wl", href: "#", onclick: (e) => {
            e.preventDefault();
            this.openNote(item.revision_of);
          } }, item.revision_of),
          ": its whole text read. Accepting merges its Claims and Evidence & Limits into that note (the previous text is kept on this item); rejecting leaves the note as it is."
        ) : null,
        queued.length ? h(
          "p",
          { class: "warn" },
          `\u23F3 Waiting on a clerk model for: ${queued.join(", ")}. Choose a tier 3 model under Model, `,
          "set [clerk] in the vault's config, or run the clerk agent, then \u201CRedraft\u201D below."
        ) : null,
        (item.intake_notes ?? []).length ? h("p", { class: "note" }, `Intake could not read everything: ${item.intake_notes.join("; ")}.`) : null,
        missing.length ? h("p", { class: "warn" }, `Still missing before this is catalogued fully: ${missing.join(", ")}.`) : null,
        h(
          "div",
          { class: "columns" },
          h(
            "div",
            {},
            h("label", { class: "f", for: "lib-bl" }, draft.bottom_line ? `Bottom Line (drafted by ${draft.model || "the clerk"}; edit it)` : "Bottom Line"),
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
              h("button", { class: "primary", onclick: decide("accept") }, "Accept"),
              h("button", { class: "ghost", onclick: decide("reject") }, "Reject"),
              h("button", { class: "ghost", onclick: decide("defer") }, "Defer"),
              h("button", { class: "ghost push", onclick: draftIt }, draft.bottom_line ? "Redraft" : "Draft with the clerk")
            ),
            h(
              "div",
              { class: "row2" },
              h("span", { class: "note inline" }, readLine),
              !dr || readCount < dr.chunks ? h(
                "button",
                { class: "ghost", onclick: readIt, title: "Claims and limits from every part, with pages; terms; and any reasoning stance the text teaches, staged as a lens" },
                dr ? "Continue deep read" : "Deep read"
              ) : null
            ),
            status
          ),
          h(
            "div",
            {},
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
          clear(status, h("p", { class: "error" }, e.message));
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
          clear(status, h("p", { class: "error" }, e.message));
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
  };
  var INTENTS = [
    ["donor", "something to reuse"],
    ["orient", "where the catalogue holds a topic"],
    ["pattern", "a design pattern"],
    ["technique", "a technique"],
    ["data", "a dataset"],
    ["precedent", "prior work"],
    ["in_text", "text inside documents"]
  ];
  var Search = class {
    constructor(api, openNote) {
      this.api = api;
      this.openNote = openNote;
      this.el = h("div", { class: "view search" });
      this.results = h("div", { class: "results", "aria-live": "polite" });
      const query = h("input", { type: "search", placeholder: "What are you looking for?", "aria-label": "Search query" });
      const intent = h(
        "select",
        { "aria-label": "Intent" },
        INTENTS.map(([v, label]) => h("option", { value: v }, `${v} \xB7 ${label}`))
      );
      const run = () => this.run(query.value, intent.value);
      query.onkeydown = (e) => {
        if (e.key === "Enter") run();
      };
      this.el.append(
        h("div", { class: "view-head" }, h("strong", {}, "Search")),
        h("div", { class: "row2 tight" }, query, intent, h("button", { class: "primary", onclick: run }, "Search")),
        this.results
      );
    }
    focus() {
      this.el.querySelector("input")?.focus();
    }
    async run(query, intent) {
      if (!query.trim()) return;
      clear(this.results, h("p", { class: "dim" }, "Searching\u2026"));
      try {
        const out = await this.api.tool("search", { query, intent, limit: 20 });
        if (out.error) throw new Error(String(out.detail ?? out.error));
        const rows = out.results ?? [];
        clear(
          this.results,
          h("p", { class: "verdict" }, String(out.coverage?.sentence ?? out.verdict ?? "")),
          rows.length ? rows.map((r) => h(
            "div",
            { class: "result" },
            h("a", { class: "wl", href: "#", onclick: (e) => {
              e.preventDefault();
              this.openNote(r.fields?.path ?? r.name);
            } }, r.name),
            h("span", { class: "dim" }, ` \xB7 ${r.fields?.kind ?? r.kind} \xB7 ${r.fields?.topic ?? ""}`),
            r.fields?.bottom_line ? h("p", {}, r.fields.bottom_line) : null,
            h("small", { class: "dim" }, r.why ?? "")
          )) : h("p", { class: "dim" }, "Nothing held matches."),
          out.next_step ? h("p", { class: "note" }, String(out.next_step)) : null
        );
      } catch (e) {
        clear(this.results, h("p", { class: "error" }, e.message));
      }
    }
  };

  // src/main.ts
  function relinkChat(log, oldName, newName, open) {
    log.querySelectorAll("a.wl").forEach((a) => {
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
      this.title = h("span", { class: "title" }, "Librarian");
      this.crumb = h("span", { class: "crumb" });
      this.live = h("span", { class: "live", role: "status", title: "Connection to the core" });
      this.chips = h("div", { class: "chips", "aria-label": "Queued actions" });
      this.input = h("textarea", {
        id: "lib-msg",
        "aria-label": "Message",
        placeholder: "Ask the librarian. Enter sends, Shift+Enter adds a line."
      });
      this.attachments = [];
      this.attachRow = h("div", { class: "attach-row", hidden: true });
      this.msgBox = h("div", { class: "msg-box" });
      this.modeButton = h("button", { class: "tb" });
      this.modelButton = h("button", { class: "tb" });
      this.notice = h("div", { class: "notice", role: "alert", hidden: true });
      this.paneOpen = true;
      this.api = new Api(opts);
      const openNote = (target) => void this.openDoc(target);
      this.chat = new Chat(this.api, {
        openNote,
        effectOf: (tool) => this.effects.get(tool) ?? "write",
        onSession: (s) => this.setSession(s),
        resend: (text) => void this.sendText(text),
        continueSession: () => void this.sendText("Continue the current research session from its next step. Read session_status first, complete the open work, and report any information you cannot verify as a gap. Do not claim the session or requested work is complete while session_status still shows open items."),
        rewind: (index) => void this.rewindMessage(index),
        branch: (index) => void this.branchMessage(index)
      });
      this.staging = new Staging(
        this.api,
        openNote,
        () => this.session?.session ?? "",
        (session) => this.setSession(session)
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
      this.settings = new Settings(this.api, () => this.state, () => this.refresh(), opts.manageKeys);
      const plus = h("button", {
        class: "tb icon",
        title: "Settings",
        "aria-label": "Settings",
        onclick: () => this.settings.open()
      }, "+");
      this.modes = new Popover("lib-modes", "Modes", this.modeButton);
      this.models = new Popover("lib-models", "Model", this.modelButton);
      const sessionsButton = h("button", { class: "ghost" }, "Sessions \u25BE");
      this.sessions = new Popover("lib-sessions", "Sessions", sessionsButton);
      this.libraries = new Popover("lib-libraries", "Libraries", this.libraryButton);
      this.libraryButton.onclick = () => {
        this.toggle(this.libraries);
        if (this.libraries.open) void renderLibraries(this.libraries, this.api, String(this.state.vault ?? "this library"));
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
      this.attachPop = new Popover("lib-attach", "Attach", attachButton);
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
        this.toggle(this.models);
        if (this.models.open) {
          await this.refresh();
          await this.tile.refresh();
        }
      };
      sessionsButton.onclick = () => {
        this.toggle(this.sessions);
        if (this.sessions.open) void renderSessions(this.sessions, this.api, (id) => this.attach(id), () => this.reset());
      };
      const elsewhere = h("button", {
        class: "tb",
        title: opts.host === "obsidian" ? "Continue in the website" : "Open this vault in Obsidian",
        onclick: opts.openElsewhere ?? (() => {
          window.location.href = `obsidian://open?vault=${encodeURIComponent(String(this.state.vault ?? ""))}`;
        })
      }, opts.host === "obsidian" ? "\u2197 Open in browser" : "\u2197 Open in Obsidian");
      const send = h("button", { class: "send", onclick: () => this.send() }, "Send");
      this.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
          e.preventDefault();
          void this.send();
        }
      });
      const chatView = h("main", { class: "chatview" }, this.chat.log);
      this.views = { chat: chatView, staging: this.staging.el, search: this.search.el };
      const navButton = (v, label) => h("button", {
        role: "tab",
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
        h("div", { class: "toolbar" }, plus, attachButton, this.modeButton, this.modelButton, elsewhere, send),
        this.modes.el,
        this.models.el,
        this.attachPop.el
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
        title: "Drag to resize"
      });
      resizer.addEventListener("pointerdown", (e) => this.resize(e, resizer));
      this.body = h(
        "div",
        { class: "lib-body" },
        h("div", { class: "lib-main" }, this.notice, chatView, this.staging.el, this.search.el, composer),
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
            this.title,
            this.crumb,
            h("nav", { role: "tablist", "aria-label": "Views" }, Object.values(this.nav)),
            this.live,
            this.paneButton
          ),
          this.body
        ),
        this.settings.dialog
      );
      this.composer = composer;
      document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") [this.modes, this.models, this.sessions, this.libraries, this.attachPop].forEach((p) => p.show(false));
      });
      document.addEventListener("click", (e) => {
        const path = e.composedPath();
        for (const p of [this.modes, this.models, this.sessions, this.libraries, this.attachPop]) {
          if (p.open && !path.includes(p.el) && !path.includes(p.button)) p.show(false);
        }
      });
      this.show("chat");
      const width = recall("pane-w");
      if (width) this.body.style.setProperty("--pane-w", width);
      const saved = recall("pane");
      this.showPane(saved ? saved === "open" : (root.clientWidth || window.innerWidth) >= 1e3);
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
      this.body.classList.toggle("pane-open", on);
      this.body.classList.toggle("pane-closed", !on);
      this.paneButton.setAttribute("aria-pressed", String(on));
      remember("pane", on ? "open" : "closed");
    }
    resize(start, handle) {
      start.preventDefault();
      handle.setPointerCapture(start.pointerId);
      const rect = this.body.getBoundingClientRect();
      const move = (e) => {
        const width = Math.min(Math.max(rect.right - e.clientX, 300), rect.width - 360);
        this.body.style.setProperty("--pane-w", `${Math.round(width)}px`);
      };
      const up = () => {
        handle.removeEventListener("pointermove", move);
        remember("pane-w", this.body.style.getPropertyValue("--pane-w"));
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
      this.api.events((event) => this.onEvent(event), (live) => {
        this.live.className = `live ${live ? "on" : "off"}`;
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
      this.libraryButton.textContent = `${String(this.state.vault ?? "Library")} \u25BE`;
      this.libraryButton.title = `Switch library - this is ${String(this.state.vault_path ?? this.state.vault ?? "")}`;
      this.setSession(this.state.session ?? null);
      this.paintToolbar();
      this.paintChips();
      if (this.state.busy) this.chat.setWorking(true);
      for (const request of this.state.pending ?? []) this.chat.handle({ seq: 0, type: "permission_request", ...request });
    }
    onEvent(event) {
      this.chat.handle(event);
      switch (event.type) {
        case "mode_changed":
          this.state.mode = event.to;
          this.paintToolbar();
          break;
        case "tiers_changed":
          this.state.tiers = event.tiers;
          this.tiersEpoch++;
          this.paintToolbar();
          if (this.models.open) this.tile.render();
          break;
        case "turn_done":
        case "error":
          this.state.busy = false;
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
        case "library_switched":
          window.location.reload();
          break;
      }
    }
    // -- painting ------------------------------------------------------------
    paintToolbar() {
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
        this.state.queued_inputs ?? {}
      );
    }
    paintChips() {
      const running = (this.state.actions ?? []).filter((a) => a.status === "running" || a.status === "paused");
      clear(this.chips, running.map((a) => h(
        "span",
        { class: "chip" },
        `${a.name} \xB7 ${a.status === "paused" ? `paused${a.reason ? `: ${a.reason}` : ""}` : `${a.steps} steps`}`,
        a.status === "running" ? h("button", { "aria-label": `Cancel ${a.name}`, onclick: async () => {
          try {
            await this.api.post(`/api/actions/${a.id}/cancel`);
          } catch (e) {
            this.warn(e.message);
          }
        } }, "\u2715") : null
      )));
    }
    setSession(session) {
      if (session && this.session && session.session === this.session.session)
        session = { ...this.session, ...session };
      this.session = session;
      this.chat.renderPlan(session);
      if (!session) {
        this.title.textContent = String(this.state.vault ?? "Librarian");
        this.crumb.textContent = "no thread";
        return;
      }
      this.title.textContent = session.project || session.question || String(this.state.vault ?? "Librarian");
      this.crumb.textContent = `${session.purpose ?? ""} \xB7 phase: ${session.phase ?? ""}${session.status && session.status !== "open" ? ` \xB7 ${session.status}` : ""}`;
    }
    show(view) {
      this.view = view;
      for (const [v, el] of Object.entries(this.views)) el.hidden = v !== view;
      for (const [v, b] of Object.entries(this.nav)) b.setAttribute("aria-selected", String(v === view));
      this.composer.hidden = view !== "chat";
      if (view === "staging") void this.staging.load(true);
      if (view === "search") this.search.focus();
    }
    toggle(pop) {
      const open = !pop.open;
      [this.modes, this.models, this.sessions, this.attachPop].forEach((p) => p.show(false));
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
      this.msgBox.classList.toggle("has-attachments", has);
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
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const before = el.value.slice(0, start);
      const insertion = `${before && !/\s$/.test(before) ? " " : ""}${text} `;
      el.value = before + insertion + el.value.slice(end);
      const caret = start + insertion.length;
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
    async send() {
      const text = this.input.value.trim();
      if (!text) return;
      this.input.value = "";
      this.attachments = [];
      this.renderAttachments();
      await this.sendText(text);
    }
    /** The send path itself, shared by the composer and a message's Retry
     *  button - which resends the same text without touching the composer. */
    async sendText(text) {
      if (!text) return;
      try {
        await this.api.post("/api/chat", { text });
        this.state.busy = true;
      } catch (e) {
        const message = e.message;
        this.warn(message.includes("tier 1") ? "Choose a chat model first: click Model, then a model (it becomes tier 1)." : message);
      }
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
  function remember(key, value) {
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
    root.classList.add("librarian-root", `host-${opts.host}`);
    const app = new App(root, opts);
    void app.start();
    return { insert: (text) => app.insert(text) };
  }
  var auto = typeof document !== "undefined" ? document.getElementById("librarian-root") : null;
  if (auto) {
    const token2 = $(document, "meta[name=librarian-token]")?.content ?? "";
    mount(auto, { base: "", token: token2, host: "website" });
  }
  return __toCommonJS(main_exports);
})();
