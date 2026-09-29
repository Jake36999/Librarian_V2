// Markdown for notes and replies, rendered as DOM nodes: nothing in a note is
// ever parsed as HTML. It covers what vault notes use: YAML frontmatter (shown
// as properties), headings, paragraphs, nested and task lists, tables,
// blockquotes and callouts, fenced code, rules, and inline code, bold, italic,
// strike, [[wiki links]] and [links](target).

import { h } from "./dom";

export type OpenLink = (target: string) => void;

/** `[[Offerings/Host Watch/Starter#Claims|label]]` → target and what to show. */
export function wikiTarget(inner: string): { target: string; label: string } {
  const [ref, alias] = inner.split("|");
  const target = ref.split("#")[0].trim();
  const label = (alias ?? target.split("/").pop() ?? target).trim();
  return { target, label: label || target };
}

export function link(target: string, label: string, open: OpenLink): HTMLElement {
  return h("a", {
    class: "wl", href: "#", title: target,
    onclick: ((e: Event) => { e.preventDefault(); open(target); }) as EventListener,
  }, label);
}

// -- inline ------------------------------------------------------------------

const INLINE = /(`[^`]+`|!?\[\[[^\]]+\]\]|!?\[[^\]]*\]\([^)\s]+\)|\*\*[^*]+\*\*|__[^_]+__|~~[^~]+~~|\*[^*\s][^*]*\*|(?<![\w])_[^_\s][^_]*_(?![\w])|https?:\/\/[^\s<>)\]]+)/g;

export function inline(text: string, open: OpenLink): DocumentFragment {
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

function token(t: string, open: OpenLink): Node {
  if (t.startsWith("`")) return h("code", {}, t.slice(1, -1));
  if (t.startsWith("![[") || t.startsWith("[[")) {
    const { target, label } = wikiTarget(t.replace(/^!/, "").slice(2, -2));
    return link(target, label, open);
  }
  if (t.startsWith("![")) {                           // images: their alt text, not a fetch
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
    if (/^[a-z][a-z0-9+.-]*:/i.test(target)) return document.createTextNode(label);   // no other schemes
    return link(decodeURIComponent(target).replace(/\.md$/i, ""), label || target, open);
  }
  if (t.startsWith("**") || t.startsWith("__")) return h("strong", {}, inline(t.slice(2, -2), open));
  if (t.startsWith("~~")) return h("s", {}, inline(t.slice(2, -2), open));
  if (t.startsWith("*") || t.startsWith("_")) return h("em", {}, inline(t.slice(1, -1), open));
  if (/^https?:\/\//i.test(t)) return h("a", { href: t, target: "_blank", rel: "noreferrer noopener" }, t);
  return document.createTextNode(t);
}

// -- frontmatter ---------------------------------------------------------------

export function splitFrontmatter(text: string): { props: [string, string][]; body: string } {
  const normal = text.replace(/\r/g, "");
  if (!normal.startsWith("---\n")) return { props: [], body: normal };
  const end = normal.indexOf("\n---", 4);
  if (end < 0) return { props: [], body: normal };
  const props: [string, string][] = [];
  for (const line of normal.slice(4, end).split("\n")) {
    // PyYAML's block sequences are "indentless" by default: `aliases:\n- a\n- b`,
    // the dash flush with its key, not indented under it.
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

function unquote(v: string): string {
  const t = v.trim();
  return /^(["']).*\1$/.test(t) ? t.slice(1, -1) : t;
}

// -- blocks ----------------------------------------------------------------------

/** `frontmatter`: show YAML properties as a table (notes). `breaks`: a single
 *  newline is a line break (chat replies); otherwise wrapped lines join into
 *  one paragraph, as in any Markdown reader. */
export function render(text: string, open: OpenLink,
                       opts: { frontmatter?: boolean; breaks?: boolean } = {}): DocumentFragment {
  const out = document.createDocumentFragment();
  let body = text.replace(/\r/g, "");
  if (opts.frontmatter) {
    const split = splitFrontmatter(body);
    body = split.body;
    if (split.props.length) {
      out.append(h("table", { class: "props" }, h("tbody", {}, split.props.map(([k, v]) =>
        h("tr", {}, h("th", {}, k), h("td", {}, inline(v, open)))))));
    }
  }
  const lines = body.split("\n");
  let i = 0;
  let para: string[] = [];
  const flush = () => {
    if (!para.length) return;
    const p = h("p");
    if (opts.breaks) {
      para.forEach((line, n) => { if (n) p.append(h("br")); p.append(inline(line, open)); });
    } else {
      p.append(inline(para.join(" "), open));
    }
    out.append(p);
    para = [];
  };
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { flush(); i++; continue; }
    const fence = /^\s*(```|~~~)/.exec(line);
    if (fence) {
      flush();
      const code: string[] = [];
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
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { flush(); out.append(h("hr")); i++; continue; }
    if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      flush();
      const rows: string[] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) rows.push(lines[i++]);
      out.append(table(rows, open));
      continue;
    }
    if (/^\s*>/.test(line)) {
      flush();
      const quoted: string[] = [];
      while (i < lines.length && /^\s*>/.test(lines[i])) quoted.push(lines[i++].replace(/^\s*>\s?/, ""));
      const callout = /^\[!(\w+)\][+-]?\s*(.*)$/.exec(quoted[0] ?? "");
      if (callout) {
        out.append(h("div", { class: `callout callout-${callout[1].toLowerCase()}` },
          h("div", { class: "callout-title" }, inline(callout[2] || callout[1], open)),
          render(quoted.slice(1).join("\n"), open, { breaks: opts.breaks })));
      } else {
        out.append(h("blockquote", {}, render(quoted.join("\n"), open, { breaks: opts.breaks })));
      }
      continue;
    }
    if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
      flush();
      const items: string[] = [];
      while (i < lines.length && (/^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) ||
             (lines[i].trim() && /^\s{2,}\S/.test(lines[i]) && items.length))) items.push(lines[i++]);
      out.append(list(items, open));
      continue;
    }
    para.push(line.trim());
    i++;
  }
  flush();
  return out;
}

function cells(row: string): string[] {
  return row.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((c) => c.trim().replace(/\\\|/g, "|"));
}

function table(rows: string[], open: OpenLink): HTMLElement {
  const [head, , ...body] = rows;
  return h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, cells(head).map((c) => h("th", {}, inline(c, open))))),
    h("tbody", {}, body.map((r) => h("tr", {}, cells(r).map((c) => h("td", {}, inline(c, open))))))));
}

/** Nested lists by indentation; `- [ ]` and `- [x]` are tasks. */
function list(lines: string[], open: OpenLink): HTMLElement {
  type Level = { indent: number; el: HTMLElement; last: HTMLElement | null };
  const make = (ordered: boolean) => h(ordered ? "ol" : "ul");
  const first = /^(\s*)([-*+]|\d+[.)])/.exec(lines[0])!;
  const stack: Level[] = [{ indent: first[1].length, el: make(/\d/.test(first[2])), last: null }];
  for (const line of lines) {
    const m = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/.exec(line);
    if (!m) {                                        // a continuation of the last item
      stack[stack.length - 1].last?.append(" ", inline(line.trim(), open));
      continue;
    }
    const indent = m[1].replace(/\t/g, "    ").length;
    while (stack.length > 1 && indent < stack[stack.length - 1].indent) stack.pop();
    let top = stack[stack.length - 1];
    if (indent > top.indent && top.last) {
      const nested: Level = { indent, el: make(/\d/.test(m[2])), last: null };
      top.last.append(nested.el);
      stack.push(nested);
      top = nested;
    }
    const task = /^\[([ xX])\]\s+(.*)$/.exec(m[3]);
    const li = task
      ? h("li", { class: "task" }, h("input", { type: "checkbox", disabled: true, checked: task[1] !== " " }), " ", inline(task[2], open))
      : h("li", {}, inline(m[3], open));
    top.el.append(li);
    top.last = li;
  }
  return stack[0].el;
}
