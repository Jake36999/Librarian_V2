"""Fetch each outside source the memory review cites, as plain text, for claim checking.

Reads claims.json, writes text/<slug>.txt and fetched.json (url -> status, bytes, title).
Reading only: nothing fetched is executed.
"""
import html
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEXT = HERE / "text"
TEXT.mkdir(exist_ok=True)
UA = "Mozilla/5.0 (compatible; citation-check/1.0)"


class _Text(HTMLParser):
    SKIP = {"script", "style", "nav", "header", "footer", "noscript", "svg"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip, self.title, self._in_title = [], 0, "", False

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "table"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if not self.skip:
            self.parts.append(data)


def slug(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", url.split("://", 1)[1])[:120]


def fetch(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(30_000_000)
            kind = response.headers.get("Content-Type", "")
            final = response.geturl()
    except urllib.error.HTTPError as exc:
        return {"status": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"status": f"{type(exc).__name__}: {str(exc)[:120]}"}
    title = ""
    if "pdf" in kind or data[:5] == b"%PDF-":
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data))
            pages = [f"\n[page {i}]\n" + (p.extract_text() or "") for i, p in enumerate(reader.pages, 1)]
            text = "".join(pages)
        except Exception as exc:  # noqa: BLE001
            return {"status": f"pdf unreadable: {exc}"}
    else:
        parser = _Text()
        parser.feed(data.decode("utf-8", "replace"))
        text = html.unescape(re.sub(r"\n\s*\n+", "\n\n", "".join(parser.parts)))
        title = " ".join(parser.title.split())
    path = TEXT / f"{slug(url)}.txt"
    path.write_text(text, encoding="utf-8")
    return {"status": "ok", "final_url": final, "bytes": len(text), "title": title[:200],
            "file": path.name}


def main() -> None:
    claims = json.loads((HERE / "claims.json").read_text(encoding="utf-8"))
    urls = sorted({c["source"] for c in claims if c["kind"] == "web"})
    out_path = HERE / "fetched.json"
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    for url in urls:
        if done.get(url, {}).get("status") == "ok":
            continue
        done[url] = fetch(url)
        print(done[url].get("status"), done[url].get("bytes", ""), url, flush=True)
        out_path.write_text(json.dumps(done, indent=1), encoding="utf-8")
        time.sleep(1.0)
    ok = sum(1 for v in done.values() if v.get("status") == "ok")
    print(f"{ok}/{len(urls)} fetched")


if __name__ == "__main__":
    sys.exit(main())
