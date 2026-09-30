"""A minimal vault-picker served when no vault can be found at startup.

Opens in the browser and lets the person choose (or add) a library from the
ones they have opened before. Selecting one relaunches the full app at that
vault and redirects the browser there.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

_HTML = """\
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Librarian</title>
<style>
  :root {
    --bg: #1e1e2e; --surface: #27273a; --border: #3a3a52;
    --text: #cdd6f4; --muted: #7c7c9c; --accent: #7c3aed;
    --danger: #f38ba8; --ok: #a6e3a1;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg); color: var(--text);
    font: 14px/1.5 "Inter", system-ui, sans-serif;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; min-height: 100vh; gap: 24px;
  }
  .logo { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
  .logo span { color: var(--accent); }
  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 24px; width: 420px; max-width: 96vw;
  }
  h2 { font-size: 13px; font-weight: 600; color: var(--muted);
       text-transform: uppercase; letter-spacing: .08em; margin-bottom: 14px; }
  .library-list { display: flex; flex-direction: column; gap: 8px; }
  .lib {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 12px; border-radius: 7px;
    border: 1px solid var(--border); background: var(--bg);
    cursor: pointer; transition: border-color .15s;
  }
  .lib:hover { border-color: var(--accent); }
  .lib-info { flex: 1; min-width: 0; }
  .lib-name { font-weight: 600; font-size: 14px; white-space: nowrap;
              overflow: hidden; text-overflow: ellipsis; }
  .lib-path { font-size: 11px; color: var(--muted); white-space: nowrap;
              overflow: hidden; text-overflow: ellipsis; }
  .lib-date { font-size: 11px; color: var(--muted); white-space: nowrap; }
  .lib-missing { color: var(--danger); font-size: 11px; }
  .open-btn {
    flex-shrink: 0; padding: 5px 14px; border-radius: 5px;
    background: var(--accent); color: #fff; border: none;
    font-size: 12px; font-weight: 600; cursor: pointer;
  }
  .open-btn:disabled { opacity: .4; cursor: not-allowed; }
  .empty { color: var(--muted); font-size: 13px; padding: 8px 0; }
  .divider { height: 1px; background: var(--border); margin: 16px 0; }
  .add-row { display: flex; gap: 8px; margin-top: 4px; }
  .add-input {
    flex: 1; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); padding: 7px 10px;
    font-size: 13px;
  }
  .add-input:focus { outline: 2px solid var(--accent); border-color: transparent; }
  .add-btn {
    padding: 7px 14px; border-radius: 6px; background: transparent;
    border: 1px solid var(--border); color: var(--text); font-size: 13px;
    cursor: pointer; white-space: nowrap;
  }
  .add-btn:hover { border-color: var(--accent); }
  #status { font-size: 12px; color: var(--muted); margin-top: 6px; min-height: 16px; }
  .spin { display: inline-block; animation: spin .8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="logo">Librar<span>ian</span></div>
<div class="card">
  <h2>Open Library</h2>
  <div class="library-list" id="list">__LIST__</div>
  <div class="divider"></div>
  <h2>Add Library</h2>
  <div class="add-row">
    <input class="add-input" id="path-input" placeholder="Path to vault folder…" type="text">
    <button class="add-btn" onclick="openPath()">Open</button>
  </div>
  <div id="status"></div>
</div>
<script>
function openVault(path) {
  var st = document.getElementById('status');
  st.innerHTML = '<span class="spin">⟳</span> Starting…';
  fetch('/open?path=' + encodeURIComponent(path))
    .then(r => r.json())
    .then(d => { if (d.url) { window.location.href = d.url; }
                 else { st.textContent = d.error || 'Could not open'; } })
    .catch(() => { st.textContent = 'Could not reach the picker.'; });
}
function openPath() {
  var p = document.getElementById('path-input').value.trim();
  if (p) openVault(p);
}
document.getElementById('path-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') openPath();
});
</script>
</body>
</html>
"""

_LIB_ROW = """\
<div class="lib">
  <div class="lib-info">
    <div class="lib-name">{name}</div>
    <div class="lib-path">{path}</div>
    {extra}
  </div>
  <button class="open-btn" {disabled} onclick="openVault('{epath}')">Open</button>
</div>"""


def _render_list(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return '<div class="empty">No libraries remembered yet — add one below.</div>'
    rows = []
    for e in entries:
        missing = e.get("missing", False)
        last = e.get("last_opened", "")[:10]
        extra = (f'<div class="lib-missing">Missing — folder not found</div>' if missing
                 else f'<div class="lib-date">{last}</div>' if last else "")
        epath = e["path"].replace("\\", "\\\\").replace("'", "\\'")
        rows.append(_LIB_ROW.format(
            name=e.get("name") or Path(e["path"]).name,
            path=e["path"],
            extra=extra,
            disabled='disabled title="Folder not found"' if missing else "",
            epath=epath,
        ))
    return "\n".join(rows)


class _PickerHandler(BaseHTTPRequestHandler):
    server: "_PickerServer"

    def log_message(self, *_: Any) -> None:
        pass

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._serve_page()
        elif parsed.path == "/open":
            qs = urllib.parse.parse_qs(parsed.query)
            path = (qs.get("path") or [""])[0].strip()
            self._open_vault(path)
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_page(self) -> None:
        from . import libraries
        entries = libraries.known()
        html = _HTML.replace("__LIST__", _render_list(entries)).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _open_vault(self, path: str) -> None:
        if not path:
            self._json({"error": "no path given"})
            return
        # --vault is a top-level CLI option, so argparse requires it before
        # the `app` subcommand. The picker is still bound to its own port
        # while this child starts, so ask the OS for a distinct free port.
        cmd = [sys.executable, "-m", "resource_librarian", "--vault", path,
               "app", "--port", "0"]
        proc: subprocess.Popen[str] | None = None
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                    text=True)
            assert proc.stdout
            line = proc.stdout.readline()
            if not line:
                return_code = proc.poll()
                self._json({
                    "error": "The library app exited before reporting its address"
                             + (f" (exit code {return_code})" if return_code is not None else ".")
                })
                return
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                if proc.poll() is None:
                    proc.terminate()
                self._json({"error": "The library app returned an invalid startup response"})
                return
            if not isinstance(data, dict):
                if proc.poll() is None:
                    proc.terminate()
                self._json({"error": "The library app returned an invalid startup response"})
                return
            url = data.get("listening", "")
            if url:
                self._json({"url": url})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                proc.terminate()
                self._json({"error": "app did not report its URL"})
        except Exception as exc:
            if proc is not None and proc.poll() is None:
                proc.terminate()
            self._json({"error": str(exc)})

    def _json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _PickerServer(ThreadingHTTPServer):
    pass


def serve_picker(port: int = 8324, open_browser: bool = True) -> int:
    """Serve the vault-selection page when no vault is found at startup."""
    server = _PickerServer(("127.0.0.1", port), _PickerHandler)
    actual_port = server.server_address[1]
    url = f"http://127.0.0.1:{actual_port}/"
    print(json.dumps({"listening": url, "picker": True}), flush=True)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0
