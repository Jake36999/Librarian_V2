"""Final synthesis: collect the critic findings for 10-final-report.md and check both quotes of each finding.

For every completed CF-final-* call: parse the JSON (verify_anchors.parse_output; if that fails, repair the one known defect, a closing
square bracket where an object should close, and say so), check the report quote and the evidence quote against the line-numbered packet
copies the critic was given, and write data/final_critic_findings.csv. Dispositions are written by hand in data/final_critic_adjudication.csv.
Run with the repository venv.
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_anchors import DATA, REPO, TMP, check_line, parse_output, read_numbered  # noqa: E402


def load(call_id: str, output: str) -> tuple[list[dict], str]:
    text = Path(output).read_text(encoding="utf-8", errors="replace")
    data, how = parse_output(text)
    if data is not None:
        return data.get("findings", []), how
    fixed = re.sub(r'""\]\s*,\s*"explanation"', '""},"explanation"', text)
    try:
        return json.loads(fixed).get("findings", []), "repaired: a closing bracket where an object should close"
    except json.JSONDecodeError as exc:
        return [], f"unparseable: {exc}"


def main() -> int:
    results = {}
    for line in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["id"].startswith("CF-final-") and r.get("status") == "completed":
            results[r["id"]] = r
    cache: dict[str, dict[int, str]] = {}

    def lines_of(f: str) -> dict[int, str]:
        if f not in cache:
            cache[f] = read_numbered(REPO / f) if f and (REPO / f).exists() else {}
        return cache[f]

    rows = []
    for cid, res in sorted(results.items()):
        findings, how = load(cid, res["output"])
        print(cid, "parse:", how, "findings:", len(findings), "finish:", res.get("finish_reason"), "cost:", res.get("live_cost"))
        for f in findings:
            rep, evd = f.get("report") or {}, f.get("evidence")
            s1, _ = check_line(rep, lines_of(str(rep.get("file") or ""))) if lines_of(str(rep.get("file") or "")) else ("unverified", None)
            if evd:
                s2, _ = check_line(evd, lines_of(str(evd.get("file") or ""))) if lines_of(str(evd.get("file") or "")) else ("unverified", None)
            else:
                s2 = "none"
            rows.append({"critic": cid, "finding": f.get("id"), "kind": f.get("kind"), "severity": f.get("severity"), "report_quote_at_line": s1,
                         "evidence_quote_at_line": s2, "report_line": rep.get("line"), "report_quote": rep.get("quote"),
                         "evidence_file": (evd or {}).get("file", ""), "evidence_line": (evd or {}).get("line", ""),
                         "evidence_quote": (evd or {}).get("quote", ""), "explanation": f.get("explanation"), "parse": how})
    if rows:
        with (DATA / "final_critic_findings.csv").open("w", encoding="utf-8", newline="") as handle:
            w = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    for r in rows:
        print(f"{r['critic']:15} {r['finding']:4} {r['kind']:22} {r['severity']:6} report={r['report_quote_at_line']:15} evidence={r['evidence_quote_at_line']:15} line {r['report_line']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
