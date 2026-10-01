"""The library picker: the page the desktop shortcut opens first, before any library
(Test Directive 2026-09-28, "After the report"; like Obsidian's vault picker).

It lists the libraries this person has opened, and:
- opens one;
- creates a new one, with a domain profile if wanted (`profiles.py`);
- opens any folder as a library, making it one first when the person agrees
  (`init` only adds what is missing, so nothing already in the folder changes);
- forgets one from the list (the folder itself is never touched).

Opening a library starts the full app at it, on a port of its own, and sends the
browser there. The picker is also what starts when no library can be found.

Bound to 127.0.0.1, and every request that reads or does anything carries this run's
token in a header. A web page open in the same browser can neither read the token nor
send that header to another origin, so it cannot drive the picker - creating folders
on this machine included.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

# A library's folder name: Windows refuses these characters and names.
BAD_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]|[. ]$|^\s*$')
RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
            *(f"lpt{i}" for i in range(1, 10))}
BROWSE_TIMEOUT = 600           # seconds a native folder dialog may stay open

_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="picker-token" content="__TOKEN__">
<title>Librarian</title>
<style>
  :root {
    --bg: #1e1e2e; --surface: #27273a; --border: #3a3a52;
    --text: #cdd6f4; --muted: #8c8cac; --accent: #7c3aed;
    --danger: #f38ba8; --ok: #a6e3a1; --warn-bg: #3a3320; --warn-line: #6b5a2a;
  }
  @media (prefers-color-scheme: light) {
    :root { --bg: #f6f5f9; --surface: #ffffff; --border: #dcd9e6; --text: #1c1a24;
            --muted: #6b6680; --danger: #b4233c; --ok: #1d7a3a;
            --warn-bg: #fff6dd; --warn-line: #e3c56b; }
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font: 14px/1.5 "Inter", system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    min-height: 100vh; gap: 20px; padding: 40px 16px;
  }
  .logo { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
  .logo span { color: var(--accent); }
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 22px; width: 520px; max-width: 100%;
  }
  h2 { font-size: 12px; font-weight: 600; color: var(--muted);
       text-transform: uppercase; letter-spacing: .08em; margin-bottom: 12px; }
  .library-list { display: flex; flex-direction: column; gap: 8px; }
  .lib {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; border-radius: 7px;
    border: 1px solid var(--border); background: var(--bg);
  }
  .lib:hover { border-color: var(--accent); }
  .lib-info { flex: 1; min-width: 0; }
  .lib-name { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lib-path, .lib-date { font-size: 11px; color: var(--muted); white-space: nowrap;
                         overflow: hidden; text-overflow: ellipsis; }
  .lib-missing { color: var(--danger); font-size: 11px; }
  button {
    font: inherit; font-size: 13px; border-radius: 6px; cursor: pointer;
    padding: 6px 14px; border: 1px solid var(--border); background: transparent; color: var(--text);
    white-space: nowrap;
  }
  button:hover { border-color: var(--accent); }
  button.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
  button.forget { padding: 4px 8px; color: var(--muted); }
  button:disabled { opacity: .45; cursor: not-allowed; }
  .empty { color: var(--muted); font-size: 13px; padding: 4px 0; }
  .divider { height: 1px; background: var(--border); margin: 18px 0; }
  .row { display: flex; gap: 8px; margin-top: 8px; flex-wrap: wrap; }
  label { display: block; font-size: 12px; color: var(--muted); margin-top: 10px; }
  input, select {
    flex: 1; min-width: 0; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); padding: 7px 10px; font: inherit; font-size: 13px;
  }
  input:focus, select:focus { outline: 2px solid var(--accent); border-color: transparent; }
  .hint { font-size: 12px; color: var(--muted); margin-top: 6px; overflow-wrap: anywhere; }
  .confirm { background: var(--warn-bg); border: 1px solid var(--warn-line); border-radius: 7px;
             padding: 10px 12px; margin-top: 10px; font-size: 13px; }
  #status { font-size: 13px; margin-top: 14px; min-height: 18px; overflow-wrap: anywhere; }
  #status.error { color: var(--danger); }
  .spin { display: inline-block; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="logo">Librar<span>ian</span></div>
<div class="card">
  <h2>Open a library</h2>
  <div class="library-list" id="list"><div class="empty">Loading…</div></div>

  <div class="divider"></div>
  <h2>Create a new library</h2>
  <label for="new-name">Name</label>
  <div class="row"><input id="new-name" placeholder="e.g. Software, History, Databases Course"></div>
  <label for="new-parent">In the folder</label>
  <div class="row">
    <input id="new-parent">
    <button onclick="browse('new-parent')">Browse…</button>
  </div>
  <label for="new-profile">Domain profile</label>
  <div class="row"><select id="new-profile"></select></div>
  <div class="hint" id="new-hint"></div>
  <div class="row"><button class="primary" onclick="createNew()">Create and open</button></div>

  <div class="divider"></div>
  <h2>Open a folder as a library</h2>
  <div class="row">
    <input id="folder" placeholder="A library's folder, or any folder to make one">
    <button onclick="browse('folder')">Browse…</button>
    <button onclick="openFolder()">Open</button>
  </div>
  <div id="adopt"></div>
  <div id="status" role="status"></div>
</div>
<script>
var TOKEN = document.querySelector('meta[name=picker-token]').content;
var PROFILES = [];

function call(path, body) {
  return fetch(path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'X-Picker-Token': TOKEN, 'Content-Type': 'application/json'},
    body: body === undefined ? undefined : JSON.stringify(body)
  }).then(function (r) {
    return r.json().then(function (d) {
      if (!r.ok || d.error) throw new Error(d.error || r.statusText);
      return d;
    });
  });
}
function el(tag, cls, text) {
  var e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
function status(text, isError, busy) {
  var st = document.getElementById('status');
  st.className = isError ? 'error' : '';
  st.textContent = '';
  if (busy) { st.appendChild(el('span', 'spin', '\\u27f3')); st.appendChild(document.createTextNode(' ')); }
  st.appendChild(document.createTextNode(text || ''));
}
function opened(d) {
  status('Opening ' + (d.name || 'the library') + '…', false, true);
  window.location.href = d.url;
}
function profileSelect(sel) {
  sel.textContent = '';
  var none = el('option', '', 'None - the starter content model');
  none.value = '';
  sel.appendChild(none);
  PROFILES.forEach(function (p) {
    var o = el('option', '', p.name + (p.description ? ' - ' + p.description : ''));
    o.value = p.name;
    sel.appendChild(o);
  });
}
function render(libraries) {
  var list = document.getElementById('list');
  list.textContent = '';
  if (!libraries.length) {
    list.appendChild(el('div', 'empty', 'No libraries yet: create one, or open a folder below.'));
    return;
  }
  libraries.forEach(function (lib) {
    var row = el('div', 'lib');
    var info = el('div', 'lib-info');
    info.appendChild(el('div', 'lib-name', lib.name || lib.path));
    info.appendChild(el('div', 'lib-path', lib.path));
    if (lib.missing) info.appendChild(el('div', 'lib-missing', 'Missing: the folder is not there'));
    else if (lib.last_opened) info.appendChild(el('div', 'lib-date', 'Last opened ' + lib.last_opened.slice(0, 10)));
    row.appendChild(info);
    var open = el('button', 'primary', 'Open');
    open.disabled = !!lib.missing;
    open.onclick = function () { openPath(lib.path); };
    var forget = el('button', 'forget', '\\u00d7');
    forget.title = 'Forget it here (the folder is not touched)';
    forget.setAttribute('aria-label', 'Forget ' + (lib.name || lib.path));
    forget.onclick = function () {
      call('/api/forget', {path: lib.path}).then(load).catch(function (e) { status(e.message, true); });
    };
    row.appendChild(open);
    row.appendChild(forget);
    list.appendChild(row);
  });
}
function load() {
  return call('/api/state').then(function (d) {
    PROFILES = d.profiles || [];
    profileSelect(document.getElementById('new-profile'));
    var parent = document.getElementById('new-parent');
    if (!parent.value) parent.value = d.default_parent || '';
    render(d.libraries || []);
    hint();
  }).catch(function (e) { status(e.message, true); });
}
function hint() {
  var name = document.getElementById('new-name').value.trim();
  var parent = document.getElementById('new-parent').value.trim();
  document.getElementById('new-hint').textContent = name && parent
    ? 'It will be made at ' + parent.replace(/[\\\\/]+$/, '') + (parent.indexOf('/') >= 0 && parent.indexOf('\\\\') < 0 ? '/' : '\\\\') + name
    : '';
}
document.getElementById('new-name').addEventListener('input', hint);
document.getElementById('new-parent').addEventListener('input', hint);
function browse(id) {
  status('Choose a folder in the window that opened…', false, true);
  call('/api/browse', {start: document.getElementById(id).value.trim()}).then(function (d) {
    status('');
    if (d.path) { document.getElementById(id).value = d.path; hint(); }
  }).catch(function (e) { status(e.message, true); });
}
function openPath(path) {
  status('Starting…', false, true);
  call('/api/open', {path: path}).then(opened).catch(function (e) { status(e.message, true); });
}
function createNew() {
  var body = {name: document.getElementById('new-name').value.trim(),
              parent: document.getElementById('new-parent').value.trim(),
              profile: document.getElementById('new-profile').value};
  status('Creating…', false, true);
  call('/api/create', body).then(opened).catch(function (e) { status(e.message, true); });
}
function openFolder() {
  var path = document.getElementById('folder').value.trim();
  var box = document.getElementById('adopt');
  box.textContent = '';
  if (!path) return;
  status('Looking…', false, true);
  call('/api/inspect', {path: path}).then(function (d) {
    if (d.library) return openPath(d.library);
    status('');
    if (!d.exists) { status('There is no folder at ' + path + '.', true); return; }
    var c = el('div', 'confirm');
    c.appendChild(el('div', '', path + ' is not a library yet. Make it one? This adds the ' +
      'library\\'s own folders (.librarian, .evidence, About, Indexes, Sources and the note ' +
      'folders), and a README.md and .gitignore only where there are none. Nothing already ' +
      'in the folder is changed' + (d.entries ? ' (it holds ' + d.entries + ' item' + (d.entries === 1 ? '' : 's') + ').' : '.')));
    var sel = el('select');
    profileSelect(sel);
    var row = el('div', 'row');
    row.appendChild(sel);
    c.appendChild(row);
    var buttons = el('div', 'row');
    var yes = el('button', 'primary', 'Make it a library and open it');
    yes.onclick = function () {
      status('Making it a library…', false, true);
      call('/api/create', {folder: d.path, adopt: true, profile: sel.value})
        .then(opened).catch(function (e) { status(e.message, true); });
    };
    var no = el('button', '', 'Cancel');
    no.onclick = function () { box.textContent = ''; };
    buttons.appendChild(yes);
    buttons.appendChild(no);
    c.appendChild(buttons);
    box.appendChild(c);
  }).catch(function (e) { status(e.message, true); });
}
document.getElementById('folder').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') openFolder();
});
load();
</script>
</body>
</html>
"""


class PickerError(Exception):
    """Said to the person as it is."""


def default_parent() -> str:
    """Where a new library goes unless the person says otherwise - the same place
    `new-vault.ps1 -Domain` puts domain libraries."""
    return os.environ.get("LIBRARIAN_LIBRARIES") or str(Path.home() / "Libraries")


def state() -> dict[str, Any]:
    from . import libraries, profiles
    try:
        standard = [{"name": p.name, "description": p.description}
                    for p in profiles.standard().values()]
    except Exception:                                     # noqa: BLE001 - never blocks the page
        standard = []
    return {"libraries": libraries.known(), "profiles": standard,
            "default_parent": default_parent()}


def inspect(path: str) -> dict[str, Any]:
    """What a folder is: a library, inside one, or a plain folder (and how full)."""
    from .rules import Refusal
    from .vault import Vault
    raw = str(path or "").strip().strip('"')
    if not raw:
        raise PickerError("give a folder")
    folder = Path(raw).expanduser()
    if not folder.is_absolute():
        raise PickerError("give the folder's full path, e.g. D:\\Libraries\\Software")
    folder = folder.resolve()
    if not folder.is_dir():
        return {"path": str(folder), "exists": False, "library": "", "entries": 0}
    try:
        library = str(Vault.find(folder).root)
    except Refusal:
        library = ""
    try:
        entries = sum(1 for _ in folder.iterdir())
    except OSError:
        entries = 0
    return {"path": str(folder), "exists": True, "library": library, "entries": entries}


def _check_name(name: str) -> str:
    name = str(name or "").strip()
    if BAD_NAME.search(name) or name.split(".")[0].casefold() in RESERVED:
        raise PickerError(f"{name!r} can't be a folder name: leave out < > : \" / \\ | ? * "
                          f"and a trailing dot or space")
    return name


def create(name: str = "", parent: str = "", folder: str = "", profile: str = "",
           adopt: bool = False) -> Path:
    """A new library at `parent/name`, or (`adopt`) the existing `folder` made one.

    A new library's folder must not exist yet, or be empty; a folder with things in
    it becomes a library only when the person said so (`adopt`), and `init` then only
    adds what is missing. A folder that already is a library is never re-made."""
    from . import init as _init
    from .rules import Refusal
    from .vault import Vault
    if adopt:
        target = Path(str(folder or "").strip().strip('"')).expanduser()
        if not target.is_absolute() or not target.is_dir():
            raise PickerError(f"there is no folder at {folder}")
        try:                                  # never a library inside another one
            inside = Vault.find(target.resolve()).root
        except Refusal:
            inside = None
        if inside is not None and inside != target.resolve():
            raise PickerError(f"{target} is inside the library at {inside}: open that one")
        title = name.strip() or target.resolve().name
    else:
        title = _check_name(name)
        base = Path(str(parent or "").strip().strip('"') or default_parent()).expanduser()
        if not base.is_absolute():
            raise PickerError("give the parent folder's full path")
        target = base / title
        if target.is_file():
            raise PickerError(f"{target} is a file")
        if target.is_dir() and any(target.iterdir()):
            if Vault(target.resolve()).exists():
                raise PickerError(f"{target} is already a library: open it from the list, "
                                  f"or under \"Open a folder as a library\"")
            raise PickerError(f"{target} already has things in it: open it under \"Open a "
                              f"folder as a library\" to make it one")
    target = target.resolve()
    if Vault(target).exists():
        raise PickerError(f"{target} is already a library; nothing was changed")
    try:
        _init.init(target, title, profile)
    except Refusal as refusal:
        raise PickerError(refusal.detail) from None
    except ValueError as exc:                             # a profile that won't load
        raise PickerError(str(exc)) from None
    except OSError as exc:
        raise PickerError(f"could not make {target}: {exc.strerror or exc}") from None
    return target


def launch(path: str) -> dict[str, Any]:
    """Start the full app at the library containing `path`, on a free port of its own;
    its address once it is listening. Replaced in tests."""
    # --vault is a top-level option, so it goes before the `app` subcommand. The
    # picker still holds its own port while the child starts, hence port 0.
    cmd = [sys.executable, "-m", "resource_librarian", "--vault", path, "app", "--port", "0"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    assert proc.stdout
    line = proc.stdout.readline()
    if not line:
        code = proc.poll()
        raise PickerError("the library app stopped before it was ready"
                          + (f" (exit code {code})" if code is not None else ""))
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or not data.get("listening"):
        if proc.poll() is None:
            proc.terminate()
        detail = data.get("detail") if isinstance(data, dict) else ""
        raise PickerError(f"the library could not be opened{': ' + detail if detail else ''}")
    return {"url": data["listening"], "path": data.get("vault", path)}


def ask_folder(start: str = "") -> str:
    """A native folder dialog, in a process of its own (Tk wants its own main thread).
    "" when the person cancels. Replaced in tests."""
    code = ("import sys, tkinter\nfrom tkinter import filedialog\n"
            "root = tkinter.Tk(); root.withdraw(); root.attributes('-topmost', True)\n"
            "print(filedialog.askdirectory(initialdir=sys.argv[1] or None, mustexist=False,"
            " title='Choose a folder for the library') or '')\n")
    try:
        out = subprocess.run([sys.executable, "-c", code, start], capture_output=True,
                             text=True, timeout=BROWSE_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise PickerError("the folder dialog was left open too long") from None
    if out.returncode != 0:
        raise PickerError("no folder dialog here (tkinter is missing): type the path instead")
    chosen = out.stdout.strip()
    return str(Path(chosen)) if chosen else ""


class _PickerHandler(BaseHTTPRequestHandler):
    server: "_PickerServer"

    def log_message(self, *_: Any) -> None:
        pass

    # -- the boundary ---------------------------------------------------------
    def _allowed(self) -> bool:
        origin = self.headers.get("Origin")
        if origin and origin != self.server.origin:
            return False
        return secrets.compare_digest(self.headers.get("X-Picker-Token", ""), self.server.token)

    def do_GET(self) -> None:                                         # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if path == "/":
            html = _HTML.replace("__TOKEN__", self.server.token).encode()
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/api/state":
            if not self._allowed():
                return self._json({"error": "not allowed"}, 403)
            self._json(state())
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self) -> None:                                        # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not self._allowed():
            return self._json({"error": "not allowed"}, 403)
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 65536)
            body = json.loads(self.rfile.read(length) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._json({"error": "a JSON object is expected"}, 400)
        try:
            if path == "/api/open":
                return self._opened(str(body.get("path") or ""))
            if path == "/api/create":
                made = create(name=str(body.get("name") or ""),
                              parent=str(body.get("parent") or ""),
                              folder=str(body.get("folder") or ""),
                              profile=str(body.get("profile") or ""),
                              adopt=bool(body.get("adopt")))
                return self._opened(str(made), created=True)
            if path == "/api/inspect":
                return self._json(inspect(str(body.get("path") or "")))
            if path == "/api/browse":
                return self._json({"path": ask_folder(str(body.get("start") or ""))})
            if path == "/api/forget":
                from . import libraries
                return self._json({"forgotten": libraries.forget(str(body.get("path") or ""))})
        except PickerError as exc:
            return self._json({"error": str(exc)})
        except Exception as exc:                                      # noqa: BLE001
            return self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        self._json({"error": "not found"}, 404)

    def _opened(self, path: str, created: bool = False) -> None:
        from . import libraries
        if not path.strip():
            raise PickerError("give a library's folder")
        found = inspect(path)
        if not found["library"]:
            raise PickerError(f"{found['path']} is not a library" if found["exists"]
                              else f"there is no folder at {found['path']}")
        out = launch(found["library"])
        name = Path(found["library"]).name
        for entry in libraries.known():
            if Path(entry["path"]) == Path(found["library"]):
                name = entry.get("name") or name
        self._json({**out, "name": name, **({"created": found["library"]} if created else {})})
        if self.server.close_after_open:
            # The library's own app runs on; this page's work is done.
            threading.Thread(target=self.server.shutdown, daemon=True).start()

    # -- replies ----------------------------------------------------------------
    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, payload: dict[str, Any], status: int = 200) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")


class _PickerServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], close_after_open: bool = True):
        super().__init__(address, _PickerHandler)
        self.token = secrets.token_urlsafe(24)
        self.origin = f"http://127.0.0.1:{self.server_address[1]}"
        self.close_after_open = close_after_open


def serve_picker(port: int = 8324, open_browser: bool = True) -> int:
    """Serve the library picker: the desktop shortcut's first page (`app --pick`), and
    what starts when no library can be found."""
    server = _PickerServer(("127.0.0.1", port))
    url = f"{server.origin}/"
    print(json.dumps({"listening": url, "picker": True}), flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
