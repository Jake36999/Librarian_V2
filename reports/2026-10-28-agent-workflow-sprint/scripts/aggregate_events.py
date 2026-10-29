"""WS5: aggregate the anchor-verified transcript events (lane T) and measure reader agreement.

Outputs: data/transcript_events.csv (verified events, de-duplicated), data/transcript_event_summary.json
Agreement: for the four chunks read by both MiMo and GLM-5.3-Flash, events are matched by kind and a line distance <= 3.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv, write_json  # noqa: E402


def load():
    events = []
    for f in sorted(glob.glob(str(TMP / "out" / "verified" / "T-*.jsonl"))):
        cid = os.path.basename(f)[:-6]
        m = re.match(r"T-(.+)-(\d\d)-(mimo|glmflash)$", cid)
        source, chunk, reader = m.group(1), m.group(2), m.group(3)
        for line in open(f, encoding="utf-8"):
            if line.strip():
                e = json.loads(line)
                e.update({"source": source, "chunk": chunk, "reader": reader})
                events.append(e)
    return events


def main() -> int:
    ev = load()
    ok = [e for e in ev if e.get("verified") == "verified"]
    primary = [e for e in ok if e["reader"] == "mimo"]
    seen, dedup = set(), []
    for e in sorted(primary, key=lambda e: (e["source"], int(e["line"]))):
        key = (e["source"], e["kind"], int(e["line"]))
        if key not in seen:
            seen.add(key)
            dedup.append(e)
    rows = [{"source": e["source"], "chunk": e["chunk"], "line": e["line"], "kind": e["kind"], "actor": e["actor"], "evidence": e.get("evidence"),
             "tokens": (e.get("numbers") or {}).get("tokens"), "usd": (e.get("numbers") or {}).get("usd"), "minutes": (e.get("numbers") or {}).get("minutes"),
             "count": (e.get("numbers") or {}).get("count"), "note": e.get("note", ""), "quote": e.get("quote", "")} for e in dedup]
    write_csv(DATA / "transcript_events.csv", rows)
    by_kind = defaultdict(Counter)
    for r in rows:
        by_kind[r["source"]][r["kind"]] += 1
    # agreement on the sampled chunks
    agree = []
    for (src, chunk) in sorted({(e["source"], e["chunk"]) for e in ok if e["reader"] == "glmflash"}):
        a = [e for e in ok if e["source"] == src and e["chunk"] == chunk and e["reader"] == "mimo"]
        b = [e for e in ok if e["source"] == src and e["chunk"] == chunk and e["reader"] == "glmflash"]
        used, hits = set(), 0
        for x in a:
            for j, y in enumerate(b):
                if j not in used and x["kind"] == y["kind"] and abs(int(x["line"]) - int(y["line"])) <= 3:
                    used.add(j); hits += 1
                    break
        agree.append({"chunk": f"{src}-{chunk}", "mimo_events": len(a), "glm_flash_events": len(b), "matched": hits,
                      "recall_of_mimo": round(hits / len(a), 2) if a else None, "precision_of_flash_vs_mimo": round(hits / len(b), 2) if b else None})
    # kind-level view of disagreement
    kinds_mimo = Counter(e["kind"] for e in ok if e["reader"] == "mimo" and (e["source"], e["chunk"]) in {(a["chunk"].rsplit("-", 1)[0], a["chunk"].rsplit("-", 1)[1]) for a in agree})
    kinds_flash = Counter(e["kind"] for e in ok if e["reader"] == "glmflash")
    protocol = [r for r in rows if r["kind"] == "protocol_step" and r["source"] == "qball"]
    dispositions = Counter()
    for r in rows:
        if r["kind"] == "finding_disposition":
            n = r["note"].lower()
            dispositions[("upheld" if "upheld" in n or "accept" in n else "rejected" if "reject" in n or "false" in n else "partial" if "partial" in n else "other", r["source"])] += 1
    summary = {"events_total_verified_primary": len(rows), "by_source_and_kind": {k: dict(v) for k, v in by_kind.items()}, "agreement_sample": agree,
               "kinds_mimo_on_sample": dict(kinds_mimo), "kinds_flash_on_sample": dict(kinds_flash),
               "finding_disposition_by_note": {f"{a}:{b}": n for (a, b), n in dispositions.items()},
               "protocol_steps_qball": [{"line": r["line"], "actor": r["actor"], "note": r["note"]} for r in protocol]}
    write_json(DATA / "transcript_event_summary.json", summary)
    print("verified primary events", len(rows))
    for src, c in by_kind.items():
        print(f"{src:11}", dict(c.most_common()))
    print("agreement:", agree)
    print("dispositions:", summary["finding_disposition_by_note"])
    print("qball protocol steps:", len(protocol))
    for p in protocol:
        print("  L" + str(p["line"]), p["actor"], p["note"].encode("ascii", "replace").decode()[:110])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
