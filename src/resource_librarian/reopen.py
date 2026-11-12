"""Opening a library that may already be open.

Closing the browser tab leaves a library's Core running, by design. Launching
the app again for that library must open the running Core, never build a
second one (which the vault lease refuses). A Core that died leaves a stale
lease instead; clearing it is a person's decision, so the app serves a small
page that says what held the library and asks.
"""
from __future__ import annotations

import html
import json
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import connection, process_identity

PROBE_TIMEOUT = 3.0
DECISION_TIMEOUT = 30 * 60          # an unanswered takeover page stops after this


class CoreUnreachable(RuntimeError):
    """A live process holds the library's record but its address does not answer."""


def _loopback(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "::1", "localhost")


def running_core(vault_root: str | Path) -> str | None:
    """The URL of this library's running Core, or None when none is running.

    Raises CoreUnreachable when the recorded process is alive but its address
    does not answer the authenticated handshake: that is never a reason to
    start a second Core.
    """
    record = connection.load(vault_root)
    if record is None:
        return None
    pid = int(record.get("pid") or 0)
    if not process_identity.is_alive(pid, record.get("process_start")):
        return None
    url = str(record.get("url") or "").rstrip("/")
    who = f"Librarian process {pid}"
    if not _loopback(url):
        raise CoreUnreachable(f"{who} holds this library, but its recorded address is not "
                              "on this computer; refusing to open a second Core")
    request = urllib.request.Request(url + "/api/meta", headers={
        "X-Librarian-Token": str(record.get("token") or ""), "Origin": url})
    try:
        with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT) as response:
            json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        reason = getattr(exc, "reason", None) or exc
        raise CoreUnreachable(f"{who} holds this library but does not answer at {url} "
                              f"({reason}); close that process, then open the library "
                              "again") from None
    return url + "/"


# -- the takeover page ----------------------------------------------------------

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Library needs a decision</title>
<style>
  :root { --bg: #f7f6f2; --fg: #1f2328; --muted: #5d6470; --accent: #2f5d8a; --line: #d8d5cc; }
  @media (prefers-color-scheme: dark) {
    :root { --bg: #1b1d21; --fg: #e8e6e1; --muted: #a3a8b0; --accent: #7fb0e0; --line: #3a3d44; }
  }
  body { background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif;
         margin: 0; padding: 32px 16px; }
  main { max-width: 560px; margin: 0 auto; }
  h1 { font-size: 1.3rem; margin: 0 0 12px; }
  p { margin: 0 0 12px; }
  .detail { color: var(--muted); font-size: .9rem; border-left: 3px solid var(--line);
            padding-left: 10px; overflow-wrap: anywhere; }
  .buttons { display: flex; gap: 12px; flex-wrap: wrap; margin-top: 20px; }
  button { font: inherit; padding: 8px 16px; border-radius: 6px; cursor: pointer;
           border: 1px solid var(--line); background: transparent; color: var(--fg); }
  button.primary { background: var(--accent); border-color: var(--accent); color: var(--bg); }
  #status { margin-top: 16px; color: var(--muted); }
</style></head><body><main>
<h1>__NAME__ was not closed properly</h1>
<p>An earlier Librarian session for this library stopped without releasing it.</p>
<p class="detail">__DETAIL__</p>
<p>Take it over only if that earlier Librarian is no longer running anywhere,
including on another computer that shares this folder.</p>
<div class="buttons">
  <button class="primary" id="take">Take over and open</button>
  <button id="leave">Leave it closed</button>
</div>
<p id="status" role="status"></p>
</main><script>
var token = "__TOKEN__";
function decide(choice) {
  document.getElementById('take').disabled = true;
  document.getElementById('leave').disabled = true;
  var st = document.getElementById('status');
  fetch('/decide', {method: 'POST', headers: {'Content-Type': 'application/json',
        'X-Takeover-Token': token}, body: JSON.stringify({choice: choice})})
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.error) { st.textContent = d.error; return; }
      if (choice !== 'takeover') { st.textContent = 'Left closed. You can close this tab.'; return; }
      st.textContent = 'Opening the library…';
      var tries = 0;
      (function wait() {
        fetch('/', {cache: 'no-store'}).then(function (r) { return r.text(); }).then(function (t) {
          if (t.indexOf('id="take"') === -1) { window.location.reload(); }
          else if (++tries < 60) { setTimeout(wait, 500); }
        }).catch(function () { if (++tries < 60) { setTimeout(wait, 500); } });
      })();
    })
    .catch(function (e) { st.textContent = e.message; });
}
document.getElementById('take').onclick = function () { decide('takeover'); };
document.getElementById('leave').onclick = function () { decide('leave'); };
</script></body></html>
"""


class _TakeoverHandler(BaseHTTPRequestHandler):
    server: "TakeoverPage"

    def log_message(self, *_: Any) -> None:
        pass

    def do_GET(self) -> None:                                         # noqa: N802
        if urllib.parse.urlparse(self.path).path != "/":
            return self._send(404, b'{"error": "not found"}', "application/json")
        page = (_PAGE.replace("__NAME__", html.escape(self.server.name))
                .replace("__DETAIL__", html.escape(self.server.detail))
                .replace("__TOKEN__", self.server.token))
        self._send(200, page.encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self) -> None:                                        # noqa: N802
        if urllib.parse.urlparse(self.path).path != "/decide":
            return self._send(404, b'{"error": "not found"}', "application/json")
        origin = self.headers.get("Origin")
        if (origin and origin != self.server.origin) or not secrets.compare_digest(
                self.headers.get("X-Takeover-Token", ""), self.server.token):
            return self._send(403, b'{"error": "not allowed"}', "application/json")
        try:
            length = min(int(self.headers.get("Content-Length") or 0), 4096)
            body = json.loads(self.rfile.read(length) or b"{}")
            choice = str(body.get("choice") or "") if isinstance(body, dict) else ""
        except ValueError:
            choice = ""
        if choice not in ("takeover", "leave"):
            return self._send(400, b'{"error": "choose takeover or leave"}', "application/json")
        self._send(200, json.dumps({"choice": choice}).encode(), "application/json")
        self.server.decide(choice)

    def _send(self, status: int, body: bytes, kind: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)


class TakeoverPage(ThreadingHTTPServer):
    """A one-question page on loopback: take over the stale lease, or leave it."""

    daemon_threads = True

    def __init__(self, port: int, *, name: str, detail: str):
        super().__init__(("127.0.0.1", port), _TakeoverHandler)
        self.name, self.detail = name, detail
        self.token = secrets.token_urlsafe(24)
        self.origin = f"http://127.0.0.1:{self.server_address[1]}"
        self.choice = ""
        self._decided = threading.Event()

    @property
    def url(self) -> str:
        return self.origin + "/"

    def decide(self, choice: str) -> None:
        if not self._decided.is_set():
            self.choice = choice
            self._decided.set()

    def wait(self, timeout: float = DECISION_TIMEOUT) -> str:
        """Serve until the person answers; "" when nobody does in time.

        The port is released on return, so the app can bind the same port and
        the page's reload lands on the library itself.
        """
        worker = threading.Thread(target=self.serve_forever, daemon=True)
        worker.start()
        try:
            self._decided.wait(timeout)
        finally:
            self.shutdown()
            self.server_close()
            worker.join(5)
        return self.choice
