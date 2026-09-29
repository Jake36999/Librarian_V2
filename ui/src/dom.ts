// Small helpers: building elements, and a safe, small Markdown for replies.

type Attrs = Record<string, string | boolean | number | EventListener | undefined>;
type Child = Node | string | null | undefined | false;

export function h(tag: string, attrs: Attrs = {}, ...children: (Child | Child[])[]): HTMLElement {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === false) continue;
    if (key.startsWith("on") && typeof value === "function") {
      el.addEventListener(key.slice(2), value as EventListener);
    } else if (key === "class") {
      el.className = String(value);
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
