// The only way the interface reaches the core: JSON over loopback with the
// page token, and one event stream. Nothing here holds a key.

export interface Options {
  base: string;            // "" in the website (same origin), "http://127.0.0.1:port" in Obsidian
  token: string;
  host: "website" | "obsidian";
  openNote?: (name: string, path: string) => void;   // Obsidian opens the real note
  openElsewhere?: () => void;                        // "Open in browser" / "Open in Obsidian"
  manageKeys?: () => void;                           // Obsidian: keys live in its secret storage
}

export class ApiError extends Error {
  constructor(public status: number, public body: Record<string, unknown>) {
    super(String(body.error ?? `HTTP ${status}`));
  }
}

export type Event = { seq: number; type: string; [key: string]: unknown };

export class Api {
  constructor(private opts: Options) {}

  private async request(method: string, path: string, body?: unknown): Promise<any> {
    const response = await fetch(this.opts.base + path, {
      method,
      headers: { "Content-Type": "application/json", "X-Librarian-Token": this.opts.token },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }

  get(path: string): Promise<any> { return this.request("GET", path); }
  post(path: string, body: unknown = {}): Promise<any> { return this.request("POST", path, body); }

  /** The composer's paperclip: raw bytes, not JSON - too large and the wrong shape. */
  async attach(file: File, dir = "Inbox"): Promise<{ path: string; name: string }> {
    const qs = `dir=${encodeURIComponent(dir)}&name=${encodeURIComponent(file.name)}`;
    const response = await fetch(`${this.opts.base}/api/attach?${qs}`, {
      method: "POST", headers: { "X-Librarian-Token": this.opts.token }, body: file,
    });
    const data = await response.json().catch(() => ({ error: `HTTP ${response.status}` }));
    if (!response.ok) throw new ApiError(response.status, data);
    return data;
  }

  /** A person's own tool call, at their tier, through the core's registry. */
  tool(name: string, args: Record<string, unknown> = {}, session = ""): Promise<any> {
    return this.post(`/api/tool/${encodeURIComponent(name)}`, { arguments: args, session });
  }

  /** The event stream. Reconnects from the last sequence number seen. */
  events(onEvent: (e: Event) => void, onStatus: (live: boolean) => void): () => void {
    let last = 0;
    let source: EventSource | null = null;
    let closed = false;
    const open = () => {
      const url = `${this.opts.base}/api/events?token=${encodeURIComponent(this.opts.token)}&since=${last}`;
      source = new EventSource(url);
      source.onopen = () => onStatus(true);
      source.onmessage = () => undefined;
      source.onerror = () => {
        onStatus(false);
        source?.close();
        if (!closed) setTimeout(open, 1500);
      };
      const handle = (message: MessageEvent) => {
        const event = JSON.parse(message.data) as Event;
        if (event.seq <= last) return;
        last = event.seq;
        onEvent(event);
      };
      for (const type of EVENT_TYPES) source.addEventListener(type, handle as EventListener);
    };
    open();
    return () => { closed = true; source?.close(); };
  }
}

export const EVENT_TYPES = [
  "user", "text", "tool_call", "tool_result", "turn_done", "error", "stopped",
  "permission_request", "permission_decided", "mode_changed", "tiers_changed",
  "session_attached", "conversation_reset", "person_acted",
  "question_asked", "question_answered",
  "action_started", "action_progress", "action_done", "library_switched", "reply_reviewed",
];
