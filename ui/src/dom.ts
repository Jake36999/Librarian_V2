// Small helpers: building elements, and a safe, small Markdown for replies.

type Attrs = Record<string, string | boolean | number | EventListener | undefined>;
type Child = Node | string | null | undefined | false;

// MF-007: every class the app owns is namespaced in the DOM, so a host's
// generic rules (Obsidian's or another plugin's `.title`, `.badge`, `.tabs`)
// cannot match it. Source writes local names (`class: "title"`); `cls()` turns
// them into `lib-title`, and style.css selects `.lib-title`. Names already
// namespaced (`lib-*`, `librarian-*`) pass through unchanged.
const OWNED_PREFIX = "lib-";

function own(token: string): string {
  return token.startsWith(OWNED_PREFIX) || token.startsWith("librarian-") ? token : OWNED_PREFIX + token;
}

/** Namespace a space-separated list of owned class names. */
export function cls(value: string): string {
  return value.split(/\s+/).filter(Boolean).map(own).join(" ");
}

/** Namespace the class names in a CSS selector (`"a.wl"` → `"a.lib-wl"`). */
export function sel(selector: string): string {
  return selector.replace(/\.(-?[A-Za-z_][\w-]*)/g, (_m, name: string) => `.${own(name)}`);
}

export function h(tag: string, attrs: Attrs = {}, ...children: (Child | Child[])[]): HTMLElement {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2), value as EventListener);
    } else if (key === "class") {
      el.className = cls(String(value));
    } else {
      el.setAttribute(key, value === true ? "" : String(value));
    }
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return el;
}

export const $ = <T extends HTMLElement = HTMLElement>(root: ParentNode, sel: string): T =>
  root.querySelector(sel) as T;

export function clear(el: HTMLElement, ...children: (Child | Child[])[]): HTMLElement {
  el.replaceChildren();
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return el;
}

export function when(iso: unknown): string {
  const text = String(iso ?? "");
  return text.slice(0, 16).replace("T", " ");
}
