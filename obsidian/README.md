# Librarian: the Obsidian plugin

A desktop-only plugin that opens the Librarian inside your vault. It holds no research logic:
it starts the local core for this vault and mounts the same interface the website serves.

## Install

1. Install the core, so `librarian` (or the compatibility alias
   `resource-librarian`) exists: `pip install -e '.[mcp]'` from the
   `Librarian_V2` checkout, or install a signed Librarian release bundle.
2. Copy `dist/main.js`, `dist/manifest.json` and `dist/styles.css` into
   `<vault>/.obsidian/plugins/librarian/`, then enable **Librarian** under Community plugins.
3. If the view says the core can't be found, set its full path under the plugin's settings.
   Apps started from the dock often don't see your shell's `PATH`. The path can be
   `resource-librarian` itself, or a Python interpreter that has the package.
4. Under the plugin's settings, choose a secret for each provider you use. Obsidian keeps it in
   its secret storage (Obsidian 1.11.4 or later).

## How it runs

- The plugin discovers a compatible Core for this vault before starting
  `librarian --vault <this vault> app --port 0` with a fresh page token.
  - Keys are passed in the child's environment: in memory, never written to `data.json`, a note
    or a log.
  - A Core managed by the Librarian Host remains alive until an explicit Stop or Quit.  A
    plugin-owned child is restarted cleanly when its Obsidian-managed secrets rotate.
- The view talks to the core over loopback. Only Obsidian's own origin (`app://obsidian.md`) is
  allowed to read across origins, and every request carries the token.
- **In the view:**
  - `[[links]]` open the real note.
  - **Ask about this note** (command palette) puts the note into the message box.
  - **Open in browser** continues in the website.
- Changing a key restarts the core, because keys reach it only when it starts.

## Build

`npm install && npm run build` builds `dist/` from `src/` and the interface in `../ui/src`.

## To confirm on your machine (M0 spike f)

- the plugin starts the core, and the view mounts;
- a key chosen from secret storage reaches the core (Settings → Connections in the view shows
  `•••• last4`);
- the plugin disposes its mounted UI and document heartbeats when the view closes.
