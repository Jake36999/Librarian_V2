"""Revision 2: parse the judge's applicability opinion (call AP-01-glm) into data/applicability_second_opinion.csv."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402


def main() -> int:
    res = None
    for line in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["id"] == "AP-02-qwen" and r.get("status") == "completed":
            res = r
    if not res:
        print("AP-02-qwen has not completed")
        return 1
    text = Path(res["output"]).read_text(encoding="utf-8", errors="replace")
    t = re.sub(r"^```(?:json)?\s*", "", text.strip())
    t = re.sub(r"\s*```$", "", t)
    papers = []
    try:
        papers = json.loads(t[t.find("{"):]).get("papers", [])
    except ValueError:
        dec = json.JSONDecoder()
        pos = t.find('"papers"')
        pos = t.find("[", pos) + 1
        while True:
            j = t.find("{", pos)
            if j < 0:
                break
            try:
                obj, pos = dec.raw_decode(t, j)
                papers.append(obj)
            except ValueError:
                pos = j + 1
    rows = [{"rank": int(p["rank"]), "level": p.get("level", ""), "mechanism": p.get("mechanism", ""), "reason": p.get("reason", "")} for p in papers if "rank" in p]
    write_csv(DATA / "applicability_second_opinion.csv", rows)
    print("opinions:", len(rows), {k: sum(1 for r in rows if r["level"] == k) for k in ("direct_candidate", "bounded_analogy", "out_of_scope")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
