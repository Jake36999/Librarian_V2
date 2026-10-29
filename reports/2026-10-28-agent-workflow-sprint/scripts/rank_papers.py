"""WS6: deterministic relevance ranking from the triage lane (P1) and the vault-note triage (P1V).

score = 2*max(A,B,C,D) + (A+B+C+D) + domain bonus (yes +2, partial +0.5, no -3) - 2 if keyword trap
        + 1 if the evidence quote is anchor-verified, -1 if it is not
Ties: method / empirical > survey > theory > position > application > other.
Outputs: data/reading_list_ranked.csv, data/vault_notes_ranked.csv, tmp/sprint/lanes/p2_shortlist.json
"""
from __future__ import annotations

import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402

KIND_ORDER = {"method": 0, "empirical": 0, "survey": 1, "theory": 2, "position": 3, "application": 4, "other": 5}
DOMAIN = {"yes": 2.0, "partial": 0.5, "no": -3.0}


def load(prefix: str) -> list[dict]:
    items = []
    for f in sorted(glob.glob(str(TMP / "out" / "verified" / f"{prefix}-*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            if line.strip():
                items.append(json.loads(line))
    return items


def to_row(it: dict) -> dict:
    rel = it.get("relevance") or {}
    ev = it.get("evidence") or {}
    a, b, c, d = (int(rel.get(k) or 0) for k in "ABCD")
    verified = it.get("verified")
    score = 2 * max(a, b, c, d) + (a + b + c + d) + DOMAIN.get(str(it.get("domain_match")), 0) - (2 if it.get("keyword_trap") else 0)
    if verified == "verified":
        score += 1
    elif verified in ("unverified", "quote_elsewhere"):
        score -= 1
    reason = it.get("reason") or ev.get("reason") or ""
    return {"slug": it.get("slug"), "title": (it.get("title_as_printed") or "")[:120], "kind": it.get("paper_kind"), "domain_match": it.get("domain_match"),
            "keyword_trap": bool(it.get("keyword_trap")), "A": a, "B": b, "C": c, "D": d, "best_category": ev.get("category", ""), "evidence_page": ev.get("page"),
            "evidence_anchor": verified, "evidence_quote": (ev.get("quote") or "")[:160], "score": round(score, 1), "reason": reason[:200]}


def main() -> int:
    inv = {r["slug"]: r for r in csv.DictReader((DATA / "papers_inventory.csv").open(encoding="utf-8"))}
    rows = [to_row(it) for it in load("P1") if it.get("slug") in inv]
    for r in rows:
        r["file"] = inv[r["slug"]]["file"]
        r["pages"] = inv[r["slug"]]["pages"]
        r["duplicate_of"] = inv[r["slug"]].get("duplicate_of", "")
    rows = [r for r in rows if not r["duplicate_of"]]
    rows.sort(key=lambda r: (-r["score"], KIND_ORDER.get(r["kind"], 5), r["slug"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    write_csv(DATA / "reading_list_ranked.csv", rows)
    vrows = [to_row(it) for it in load("P1V")]
    vrows.sort(key=lambda r: (-r["score"], r["slug"]))
    for i, r in enumerate(vrows, 1):
        r["rank"] = i
    write_csv(DATA / "vault_notes_ranked.csv", vrows)
    short = [r for r in rows if r["domain_match"] in ("yes", "partial") and max(r["A"], r["B"], r["C"], r["D"]) >= 2 and int(r["pages"]) <= 70][:18]
    (TMP / "lanes" / "p2_shortlist.json").write_text(json.dumps([{"slug": r["slug"], "file": r["file"], "pages": r["pages"], "rank": r["rank"]} for r in short], indent=1), encoding="utf-8")
    print(f"ranked papers={len(rows)} vault notes={len(vrows)} shortlist={len(short)}")
    for r in rows[:30]:
        print(f"{r['rank']:2} {r['score']:5} A{r['A']}B{r['B']}C{r['C']}D{r['D']} {str(r['domain_match'])[:4]:4} {str(r['kind'])[:6]:6} {r['title'][:70]}".encode("ascii", "replace").decode())
    zero = [r for r in rows if max(r["A"], r["B"], r["C"], r["D"]) == 0]
    print("papers scoring zero in all categories:", len(zero), "| keyword traps:", sum(1 for r in rows if r["keyword_trap"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
