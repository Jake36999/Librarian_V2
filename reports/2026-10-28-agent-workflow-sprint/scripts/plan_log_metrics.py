"""1e: growth of the unified plan and the size of a cold-start read at each commit.

Outputs: data/plan_growth.csv, data/handoff_artifacts.csv
Tokens use tiktoken o200k_base when available (the earlier blind-spot report used the
same tokenizer); otherwise chars/4.4, the ratio measured on DeepInfra receipts.
"""
from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPO, git, write_csv  # noqa: E402

PLAN = "docs/unified-implementation-plan.md"

try:
    import tiktoken
    ENC = tiktoken.get_encoding("o200k_base")
    def tokens(text: str) -> int:
        return len(ENC.encode(text, disallowed_special=()))
    TOKENIZER = "tiktoken o200k_base"
except Exception:  # noqa: BLE001 - fall back when the encoding cannot be loaded
    def tokens(text: str) -> int:
        return round(len(text) / 4.4)
    TOKENIZER = "chars/4.4 estimate"


def main() -> int:
    rows = []
    log = git("log", "--reverse", "--format=%H %cI %s", "master", "--", PLAN).splitlines()
    for line in log:
        h, when, subject = line.split(" ", 2)
        text = git("show", f"{h}:{PLAN}")
        lines = text.splitlines()
        start = next((i for i, l in enumerate(lines) if re.match(r"^## 19\.", l)), None)
        s19 = "\n".join(lines[start:]) if start is not None else ""
        entries = [l for l in lines[start:] if l.startswith("### ")] if start is not None else []
        rows.append({
            "commit": h[:7], "commit_time": when, "subject": subject[:90], "bytes": len(text.encode("utf-8")), "lines": len(lines),
            "tokens": tokens(text), "s19_start_line": (start + 1) if start is not None else "", "s19_bytes": len(s19.encode("utf-8")),
            "s19_tokens": tokens(s19) if s19 else 0, "s19_entries": len(entries),
        })
    write_csv(DATA / "plan_growth.csv", rows)
    artifacts = []
    for rel in ("reports/2026-10-24-handoff-to-chatgpt.md", "reports/2026-10-24-chatgpt-transcript-review.md",
                "reports/2026-10-24-harness-and-adapter-plan-review.md", "docs/audited-engagement-harness.md",
                "docs/model-invocation-architecture.md", "docs/staging-write-safety.md", "docs/regression-manifest.md",
                "docs/release-implementation-queue.md", "docs/qualification.md", PLAN):
        text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
        artifacts.append({"path": rel, "bytes": len(text.encode("utf-8")), "tokens": tokens(text)})
    write_csv(DATA / "handoff_artifacts.csv", artifacts)
    print(f"plan versions={len(rows)} tokenizer={TOKENIZER} first={rows[0]['tokens']} last={rows[-1]['tokens']} s19_last={rows[-1]['s19_tokens']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
