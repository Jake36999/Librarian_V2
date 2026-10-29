"""WS7: capability matrix from the architecture lane (A1-A6), two independent readers per component.

For every (component, capability): each reader's status (present/partial/absent) and whether its quote is
anchor-verified. Reader pairs: MiMo-V2.6-Pro with GLM-5.3 (A2, A3, A5, A6) or DeepSeek-V4-Pro (A1, A4).
Outputs: data/capability_matrix.csv, data/architecture_facts.csv, and a printed grid.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, TMP, write_csv  # noqa: E402

CAPS = {
    "C1": "typed/schema-checked delegate output", "C2": "receipts with join keys", "C3": "executable acceptance gate", "C4": "resume/handoff capsule",
    "C5": "quota/limit-aware dispatch", "C6": "fan-out dispatcher", "C7": "lease/heartbeat watchdog", "C8": "parked question queue",
    "C9": "pre-dispatch cost estimator", "C10": "call trace/telemetry", "C11": "lane isolation + scope guard", "C12": "drafter != reviewer enforced",
}
ABBR = {"present": "P", "partial": "p", "absent": "-", None: "?"}


def readers(component: str):
    out = {}
    for f in glob.glob(str(TMP / "out" / "verified" / f"{component}-*.jsonl")):
        reader = re.sub(r"^.*" + re.escape(component) + r"-", "", os.path.basename(f)[:-6])
        out[reader] = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    return out


def main() -> int:
    comps = ["A1-mcp-boundary", "A2-core-writer", "A3-invocation-runtime", "A4-qualification-expectations", "A5-delegation-and-parallelism", "A6-session-and-harness"]
    matrix, facts = [], []
    grid = defaultdict(dict)
    for comp in comps:
        rd = readers(comp)
        usable = {k: v for k, v in rd.items() if any(r.get("kind") == "capability_checks" for r in v)}
        for reader, rows in rd.items():
            for r in rows:
                if r.get("kind") == "facts":
                    facts.append({"component": comp, "reader": reader, "claim": r.get("claim"), "file": r.get("file"), "line": r.get("line"), "quote": r.get("quote"), "anchor": r.get("verified")})
        for cid in CAPS:
            st = {}
            for reader, rows in usable.items():
                hit = next((r for r in rows if r.get("kind") == "capability_checks" and r.get("id") == cid), None)
                if hit:
                    st[reader] = (hit.get("status"), hit.get("verified"), (hit.get("where") or {}).get("file"), (hit.get("where") or {}).get("line"), (hit.get("where") or {}).get("quote"), hit.get("gap"))
            names = sorted(st)
            row = {"component": comp.split("-")[0], "capability": cid, "meaning": CAPS[cid]}
            for n in names:
                row[f"{n}_status"], row[f"{n}_anchor"], row[f"{n}_file"], row[f"{n}_line"], row[f"{n}_quote"], row[f"{n}_gap"] = st[n]
            statuses = [st[n][0] for n in names]
            row["readers"] = len(names)
            row["agree"] = (len(set(statuses)) == 1) if len(statuses) > 1 else ""
            matrix.append(row)
            def sym(n):
                status, anchor = st[n][0], st[n][1]
                if status in ("present", "partial") and anchor != "verified":
                    return "u"  # claimed without a verified quote: unsupported
                return ABBR.get(status, "?")
            grid[cid][comp.split("-")[0]] = "/".join(sym(n) for n in names) if names else "n/a"
            row["supported_status"] = "/".join(sym(n) for n in names)
    write_csv(DATA / "capability_matrix.csv", matrix)
    write_csv(DATA / "architecture_facts.csv", facts)
    print("cap  meaning                               " + "  ".join(c.split("-")[0].ljust(5) for c in comps))
    for cid, meaning in CAPS.items():
        print(f"{cid:4} {meaning[:36]:36} " + "  ".join(grid[cid].get(c.split('-')[0], 'n/a').ljust(5) for c in comps))
    pairs = [r for r in matrix if r["agree"] != ""]
    print("reader pairs:", len(pairs), "| raw status agreement:", sum(1 for r in pairs if r["agree"]), "/", len(pairs))
    # Cohen's kappa over the pairs (3 categories), using each reader's raw status
    labels = ["present", "partial", "absent"]
    xs, ys = [], []
    for r in pairs:
        ks = sorted(k[:-7] for k in r if k.endswith("_status") and k != "supported_status")
        if len(ks) == 2 and r[ks[0] + "_status"] in labels and r[ks[1] + "_status"] in labels:
            xs.append(r[ks[0] + "_status"]); ys.append(r[ks[1] + "_status"])
    n = len(xs)
    po = sum(1 for a, b in zip(xs, ys) if a == b) / n if n else 0
    pe = sum((xs.count(l) / n) * (ys.count(l) / n) for l in labels) if n else 0
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    print(f"Cohen kappa on {n} pairs: {kappa:.2f} (po={po:.2f}, pe={pe:.2f})")
    from common import write_json
    write_json(DATA / "capability_matrix_summary.json", {"reader_pairs": len(pairs), "pairs_with_both_labels": n, "observed_agreement": round(po, 3), "chance_agreement": round(pe, 3),
                                                         "cohen_kappa": round(kappa, 3), "raw_status_agreement": [sum(1 for r in pairs if r["agree"]), len(pairs)]})
    print("facts:", len(facts), "| anchor verified:", sum(1 for f in facts if f["anchor"] == "verified"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
