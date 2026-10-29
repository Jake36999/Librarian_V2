"""WS2: bibliographic metadata fetched deterministically (vault rule: never recalled by a model).

DOIs go to the public Crossref REST API, arXiv ids to the public arXiv API. Only the identifier
is sent; no mailto and no other data. Output: data/papers_metadata.json
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, to_iso, write_json  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

UA = {"User-Agent": "librarian-sprint-metadata/1"}


def get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return r.read().decode("utf-8", errors="replace")


def crossref(doi: str) -> dict:
    try:
        msg = json.loads(get("https://api.crossref.org/works/" + urllib.parse.quote(doi)))["message"]
    except (urllib.error.URLError, ValueError, KeyError, TimeoutError) as exc:
        return {"status": "error", "error": type(exc).__name__}
    issued = (msg.get("issued") or {}).get("date-parts") or [[None]]
    return {"status": "ok", "title": (msg.get("title") or [""])[0], "authors": [(" ".join(x for x in (a.get("given", ""), a.get("family", a.get("name", ""))) if x)) for a in msg.get("author", [])][:12],
            "n_authors": len(msg.get("author", [])), "year": issued[0][0], "venue": (msg.get("container-title") or [""])[0], "type": msg.get("type"),
            "publisher": msg.get("publisher"), "url": msg.get("URL")}


def arxiv(aid: str) -> dict:
    try:
        xml = get("http://export.arxiv.org/api/query?id_list=" + aid)
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"status": "error", "error": type(exc).__name__}
    entry = re.search(r"<entry>(.*?)</entry>", xml, re.S)
    if not entry:
        return {"status": "not_found"}
    body = entry.group(1)
    title = re.sub(r"\s+", " ", (re.search(r"<title>(.*?)</title>", body, re.S) or [None, ""])[1]).strip()
    return {"status": "ok", "title": title, "authors": re.findall(r"<name>(.*?)</name>", body)[:8], "year": int((re.search(r"<published>(\d{4})", body) or [None, 0])[1] or 0),
            "venue": "arXiv", "type": "preprint", "url": "https://arxiv.org/abs/" + aid}


def main() -> int:
    rows = list(csv.DictReader((DATA / "papers_inventory.csv").open(encoding="utf-8")))
    out = {"retrieved_at": to_iso(datetime.now(timezone.utc)), "papers": {}}
    for r in rows:
        if r.get("duplicate_of"):
            continue
        meta = {}
        page1 = ""
        src = TMP / "src" / "papers" / f"{r['slug']}.txt"
        if src.exists():
            text = src.read_text(encoding="utf-8", errors="replace")
            page1 = text.split("[[PAGE 2]]")[0].lower()
        if r.get("arxiv_id"):
            meta = {"source": "arxiv", "id": r["arxiv_id"], **arxiv(r["arxiv_id"])}
            time.sleep(3)
        elif r.get("doi"):
            meta = {"source": "crossref", "id": r["doi"], **crossref(r["doi"])}
            time.sleep(0.4)
        else:
            meta = {"source": "none", "status": "no_identifier"}
        if meta.get("status") == "ok":
            # The fetched title must appear in the paper's own first page, or the id was a citation.
            toks = {t for t in re.findall(r"[a-z0-9]{4,}", (meta.get("title") or "").lower())}
            overlap = len([t for t in toks if t in page1]) / max(1, len(toks))
            meta["title_overlap"] = round(overlap, 2)
            if overlap < 0.7:
                meta["status"] = "title_mismatch"
        out["papers"][r["slug"]] = {"file": r["file"], **meta}
    write_json(DATA / "papers_metadata.json", out)
    ok = sum(1 for v in out["papers"].values() if v.get("status") == "ok")
    print(f"papers={len(out['papers'])} metadata_ok={ok} no_identifier={sum(1 for v in out['papers'].values() if v.get('status') == 'no_identifier')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
