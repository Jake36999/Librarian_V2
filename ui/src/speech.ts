// Text to speech (service slot 5; owner, 2026-10-01). One reader for the whole app, so only
// one thing plays at a time: mode A reads a reply (the speaker under it), mode B reads the
// open document (the speaker beside the pane's ⋮). The server cuts the text into chunks and
// speaks each only when it is about to play - the next is fetched while the current plays -
// so stopping spends nothing more, and its $2 cap is checked before every chunk.

import type { Api } from "./api";

const NS = "http://www.w3.org/2000/svg";

/** A small line icon, drawn rather than emoji so it matches the theme. */
export function icon(paths: readonly (readonly [string, Record<string, string>])[],
                     size = 13): SVGElement {
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

export const speakerIcon = (size = 13): SVGElement => icon([
  ["path", { d: "M2.5 6h2.3L8 3.2v9.6L4.8 10H2.5z" }],
  ["path", { d: "M10.4 5.6a3.2 3.2 0 0 1 0 4.8" }], ["path", { d: "M12.2 3.8a5.8 5.8 0 0 1 0 8.4" }]], size);
export const stopIcon = (size = 13): SVGElement => icon([
  ["rect", { x: "4", y: "4", width: "8", height: "8", rx: "1" }]], size);
export const runIcon = (size = 13): SVGElement => icon([["path", { d: "M5 3.2v9.6L12.6 8z" }]], size);

type Source = { text: string } | { path: string };

class Reader {
  private api: Api | null = null;
  private warn: (message: string) => void = () => undefined;
  private audio: HTMLAudioElement | null = null;
  private button: HTMLElement | null = null;
  private title = "";
  private run = 0;

  init(api: Api, warn: (message: string) => void): void {
    this.api = api;
    this.warn = warn;
  }

  /** Start reading `source` with `button` showing it; the same button again stops it. */
  async toggle(source: Source, button: HTMLElement, size = 13): Promise<void> {
    if (this.button === button) {
      this.stop();
      return;
    }
    this.stop();
    const run = ++this.run;
    this.button = button;
    this.title = button.title;
    button.classList.add("speaking");
    button.replaceChildren(stopIcon(size));
    try {
      const plan = await this.api!.post("/api/tts/plan", source);
      let next = this.api!.post("/api/tts/chunk", { plan: plan.plan, index: 0 });
      for (let i = 0; i < plan.count && run === this.run; i++) {
        const got = await next;
        if (run !== this.run) break;
        if (i + 1 < plan.count) next = this.api!.post("/api/tts/chunk", { plan: plan.plan, index: i + 1 });
        button.title = `Reading part ${i + 1} of ${plan.count} - click to stop`;
        await this.play(got.audio, run);
      }
    } catch (e) {
      if (run === this.run) this.warn(`Read aloud: ${(e as Error).message}`);
    }
    if (run === this.run) this.reset(size);
  }

  private play(src: string, run: number): Promise<void> {
    return new Promise((resolve) => {
      if (run !== this.run) { resolve(); return; }
      const audio = new Audio(src);
      this.audio = audio;
      audio.onended = () => resolve();
      audio.onerror = () => resolve();
      audio.play().catch(() => resolve());
    });
  }

  stop(): void {
    this.run++;
    this.audio?.pause();
    this.audio = null;
    this.reset();
  }

  private reset(size = 13): void {
    if (this.button) {
      this.button.classList.remove("speaking");
      this.button.replaceChildren(speakerIcon(size));
      this.button.title = this.title;
    }
    this.button = null;
  }
}

export const reader = new Reader();
