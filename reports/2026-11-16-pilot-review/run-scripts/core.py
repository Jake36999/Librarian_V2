"""Tiny client for a running Librarian Core, using the Host's connection record. Never prints the token."""
import json, sys, urllib.request
sys.path.insert(0, r"D:\Librarian_V2\src")
from resource_librarian import connection

def call(vault, method, path, body=None, timeout=600):
    rec = connection.load(vault)
    if not rec:
        raise SystemExit(f"no connection record for {vault}")
    url = rec["url"].rstrip("/") + path
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"X-Librarian-Token": str(rec["token"]), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:2000]}

def tool(vault, name, args=None, timeout=600):
    return call(vault, "POST", f"/api/tool/{name}", {"arguments": args or {}}, timeout)

if __name__ == "__main__":
    vault, method, path = sys.argv[1:4]
    body = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    print(json.dumps(call(vault, method, path, body), indent=1)[:20000])
