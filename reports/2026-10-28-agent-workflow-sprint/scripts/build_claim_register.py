"""WS4 (revision 2): the claim register for the Gemini review.

Input: tmp/sprint/out/verified/G-*.jsonl (claims extracted by a model, each with a verbatim quote checked against the review text)
       and data/claim_dispositions.csv (hand-written, one row per examined claim).
Output: data/claim_register.csv

The first pass assigned tags with regular expressions over claim fragments. That mis-scoped claims (for example it called a
claim about the Lean phase 'contradicted' by a different document). Tags are now written row by row, each with its source,
retrieval date and who checked it. Tags: verified = supported as stated by a primary source read in this sprint (or observed
directly); plausible = partly supported, or consistent with secondary reports or local data; unverified = no supporting source read.
`qualifier` records scope corrections, partial support, design hypotheses and local-session assertions.
Claim ids are stable: they come from the same ordered, de-duplicated extraction as the first pass.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402

OUTSIDE = {"outside_company", "outside_tool", "model_capability", "pricing"}


def main() -> int:
    claims = []
    for f in sorted(glob.glob(str(TMP / "out" / "verified" / "G-*.jsonl"))):
        for line in open(f, encoding="utf-8"):
            c = json.loads(line)
            if c.get("verified") in ("verified", "quote_elsewhere"):
                claims.append(c)
    disp = {r["id"]: r for r in csv.DictReader((DATA / "claim_dispositions.csv").open(encoding="utf-8"))}
    seen, rows = set(), []
    for c in sorted(claims, key=lambda c: int(c["line"])):
        key = re.sub(r"\W+", "", c["quote"].lower())[:70]
        if key in seen:
            continue
        seen.add(key)
        cid = f"CL-{len(rows) + 1:03d}"
        d = disp.get(cid)
        if d:
            row = {"group": d["group"], "tag": d["tag"], "qualifier": d["qualifier"], "source": d["source"], "retrieved": d["retrieved"], "checked_by": d["checked_by"], "note": d["note"]}
        elif c["class"] == "opinion_or_score":
            row = {"group": "other", "tag": "n/a", "qualifier": "opinion", "source": "", "retrieved": "", "checked_by": "", "note": "opinion or rating"}
        elif c["class"] in OUTSIDE:
            row = {"group": "outside", "tag": "unverified", "qualifier": "", "source": "", "retrieved": "", "checked_by": "", "note": "no source read; not used by any design"}
        else:
            row = {"group": "other", "tag": "n/a", "qualifier": "not_examined", "source": "", "retrieved": "", "checked_by": "", "note": "claim about the project's own data or practice that this sprint did not test"}
        rows.append({"id": cid, "line": c["line"], "class": c["class"], "quote": c["quote"].replace("\n", " "), **row})
    missing = sorted(set(disp) - {r["id"] for r in rows})
    write_csv(DATA / "claim_register.csv", rows)
    from collections import Counter
    out = [r for r in rows if r["group"] == "outside"]
    print("claims", len(rows), "| outside", len(out), dict(Counter(r["tag"] for r in out)), "| local", sum(1 for r in rows if r["group"] == "local"),
          "| other", sum(1 for r in rows if r["group"] == "other"), "| dispositions without a claim:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
