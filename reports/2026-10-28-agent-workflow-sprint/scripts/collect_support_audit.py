"""Revision 2, M8d: join the judge's verdicts to the sampled items. Output: data/support_audit_results.csv, data/support_audit_summary.json"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402


def parse_verdicts(text: str) -> list[dict]:
    t = re.sub(r"^```(?:json)?\s*", "", text.strip())
    t = re.sub(r"\s*```$", "", t)
    i = t.find("{")
    if i < 0:
        return []
    try:
        return json.loads(t[i:]).get("verdicts", [])
    except ValueError:
        pass
    dec, out = json.JSONDecoder(), []
    m = re.search(r'"verdicts"\s*:\s*\[', t)
    pos = m.end() if m else i
    while pos < len(t):
        j = t.find("{", pos)
        if j < 0:
            break
        try:
            obj, pos = dec.raw_decode(t, j)
            if isinstance(obj, dict) and "item" in obj:
                out.append(obj)
        except ValueError:
            pos = j + 1
    return out


def main() -> int:
    sample = list(csv.DictReader((DATA / "support_audit_sample.csv").open(encoding="utf-8")))
    results = {}
    for line in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["id"].startswith("S2b-") and r.get("status") == "completed":
            results[r["id"]] = r
    verdicts = {}
    for cid, r in results.items():
        p = Path(r["output"])
        if p.exists():
            for v in parse_verdicts(p.read_text(encoding="utf-8", errors="replace")):
                verdicts[(cid, int(v.get("item", 0)))] = v
    rows = []
    for s in sample:
        v = verdicts.get((s["call"], int(s["item"])), {})
        rows.append({**s, "judge": s["call"].rsplit("-", 1)[1], "verdict": v.get("verdict", "no_verdict"), "judge_reason": v.get("reason", ""), "quote_relevant": v.get("quote_relevant", "")})
    write_csv(DATA / "support_audit_results.csv", rows)
    summary = {"items": len(rows), "verdicts": dict(Counter(r["verdict"] for r in rows)),
               "by_field": {f: dict(Counter(r["verdict"] for r in rows if r["field"] == f)) for f in sorted({r["field"] for r in rows})},
               "by_reader": {f: dict(Counter(r["verdict"] for r in rows if r["reader"] == f)) for f in sorted({r["reader"] for r in rows})},
               "calls_completed": len(results)}
    (DATA / "support_audit_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
