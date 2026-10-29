"""Final-report number check: is every meaningful number in 10-final-report.md present in a source file?

A number is 'meaningful' when it has a decimal point, a dollar sign or percent sign, or at least three digits (years are skipped).
It is 'grounded' when the same digits appear as a stand-alone number in the report corpus (this sprint's reports and data, the second-pass
review and the overseer review, excluding the private transcripts). Ungrounded numbers are either derived (arithmetic in the report) or
errors; `data/final_number_check.json` lists them with their lines, and DERIVED below records why each derived number is allowed.
Output: data/final_number_check.json
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPORT  # noqa: E402

ROOT = REPORT.parent
EXTRA = [ROOT / "2026-10-28-agent-workflow-second-pass", ROOT / "2026-10-28-deepinfra-overseer-workflow"]
SKIP_DIRS = {"sources", "revision-1", "__pycache__", "calls"}
SKIP_PREFIX = ("claude_", "codex_")
MAX_BYTES = 400_000

# number (digits only, no separators) -> why the report may state it without a source
DERIVED = {
    "0.027882": "55,768 x 0.43/M + 4,485 x 0.87/M, recomputed in section 3",
    "0.635": "t(0.975, 11) / sqrt(12), standard t table",
    "1.05": "t(0.975, 5) / sqrt(6), standard t table",
    "0.64": "0.635 rounded",
    "0.25": "a stated guess for sigma",
    "0.95": "interval level",
    "0.8": "arithmetic of the identity or a proposed threshold",
    "0.2": "arithmetic of the identity or a proposed threshold",
    "0.5": "proposed threshold",
    "0.9": "arithmetic of the identity",
    "0.1": "arithmetic of the identity",
    "0.3": "illustrative value",
    "80": "minutes, derived: 8.4 / 0.1 rounded down in the text",
    "97.7": "(1,626 + 104) / 1,771, data/hyphen_recheck.json",
    "98.1": "(1,225 + 72) / 1,322, data/hyphen_recheck.csv",
    "98.3": "(211 + 21) / 236, data/hyphen_recheck.csv",
    "94.4": "(190 + 11) / 213, data/hyphen_recheck.csv",
    "1.115": "sum of 56 completed development calls with a cost, recomputed from delegate_events.csv",
    "1.7": "median call cost in cents, recomputed from delegate_events.csv",
    "7.8": "maximum call cost in cents, recomputed from delegate_events.csv",
    "1771": "1,802 items less 31 with no claim, data/hyphen_recheck.json",
    "1730": "1,626 + 104",
    "145": "132 + 5 + 8 non-verified claim-bearing items, data/hyphen_recheck.json",
    "0.00589": "INDEX-05 evidence report in the repository states $0.00589009 for the interrupted mapper's reserve, rounded",
    "15.6": "MAST page fetched 2026-10-29 (appendix A row 5); fetch-tool extract",
    "0.373": "scaling paper v3 abstract fetched 2026-10-29 (appendix A row 6); fetch-tool extract",
    "0.0679": "claude-ledger.json (tmp/deepinfra-delegation) charge for CF-final-mimo",
    "0.0746": "claude-ledger.json charge for CF-final-qwen",
    "0.0221": "claude-ledger.json charge for the timed-out CF-final-glm call (its reserve)",
}


def corpus_files() -> list[Path]:
    files = []
    bases = [REPORT / "data", REPORT, *EXTRA]
    for base in bases:
        for p in base.rglob("*") if base != REPORT else base.glob("*.md"):
            if not p.is_file() or p.suffix.lower() not in (".md", ".json", ".csv", ".txt", ".jsonl"):
                continue
            if any(part in SKIP_DIRS for part in p.parts) or p.name.startswith(SKIP_PREFIX):
                continue
            if p.name in ("10-final-report.md", "final_number_check.json") or p.stat().st_size > MAX_BYTES:
                continue
            files.append(p)
    return files


def norm_numbers(text: str) -> set[str]:
    out = set()
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
        s = m.group(0).rstrip(",").replace(",", "")
        out.add(s)
        if "." in s:
            out.add(s.rstrip("0").rstrip("."))
    return out


def main() -> int:
    corpus: set[str] = set()
    n_files = 0
    for p in corpus_files():
        try:
            corpus |= norm_numbers(p.read_text(encoding="utf-8", errors="replace"))
            n_files += 1
        except OSError:
            continue
    report = (REPORT / "10-final-report.md").read_text(encoding="utf-8")
    ungrounded: dict[str, list[int]] = {}
    checked = 0
    for ln, line in enumerate(report.splitlines(), 1):
        if line.startswith("_Critic pass"):
            continue
        for m in re.finditer(r"(\$?)(\d[\d,]*(?:\.\d+)?)(%?)", line):
            raw = m.group(2).rstrip(",")
            digits = raw.replace(",", "")
            meaningful = bool(m.group(1) or m.group(3) or "." in digits or len(digits) >= 3)
            if not meaningful:
                continue
            if re.fullmatch(r"20(2[4-9]|3\d)", digits):
                continue  # a year
            before = line[max(0, m.start() - 1):m.start()]
            after = line[m.end():m.end() + 1]
            if before == "-" or after == "-":  # part of a date or a range such as 2026-10-29
                if re.search(r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}", line[max(0, m.start() - 5):m.end() + 5]):
                    continue
            checked += 1
            if digits in corpus or digits.rstrip("0").rstrip(".") in corpus:
                continue
            ungrounded.setdefault(digits, []).append(ln)
    derived = {k: v for k, v in ungrounded.items() if k in DERIVED}
    unexplained = {k: v for k, v in ungrounded.items() if k not in DERIVED}
    result = {"corpus_files": n_files, "numbers_checked": checked, "ungrounded_distinct": len(ungrounded),
              "derived_allowed": {k: {"lines": v, "why": DERIVED[k]} for k, v in derived.items()}, "unexplained": unexplained}
    (DATA / "final_number_check.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("corpus_files", "numbers_checked", "ungrounded_distinct")}))
    print("derived allowed:", sorted(derived))
    print("UNEXPLAINED:", json.dumps(unexplained))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
