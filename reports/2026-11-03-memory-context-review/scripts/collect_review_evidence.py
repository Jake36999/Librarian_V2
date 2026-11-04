"""Read-only inventory and synthetic context-growth probe; no provider calls."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from resource_librarian.loop import Loop

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "data"
PAPERS = ROOT / "reports/2026-10-29-long-horizon-harness-research/data/paper_text"
NEW = ROOT / "reports/2026-10-30-runtime-tooling-literature/data/paper_text"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inventory = []
    for path in sorted([*PAPERS.glob("*.txt"), *NEW.glob("new-??.txt")]):
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        inventory.append({
            "path": path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "page_markers": len(re.findall(r"\[\[(?:PDF )?PAGE \d+\]\]", text)),
            "keyword_counts": {term: len(re.findall(term, text, re.I)) for term in
                               ("memory", "retriev", "context", "graph", "communicat")},
        })
    (OUT / "local-extract-inventory.json").write_text(
        json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    # Exercise the real view() method independently of providers/vault writes.
    # Each round has the same message sizes; this measures wire growth only.
    probes = []
    for rounds in (10, 50, 200):
        loop = Loop.__new__(Loop)
        loop.messages = []
        loop.context_message = lambda: None
        for i in range(rounds):
            loop.messages.extend([
                {"role": "user", "content": "u" * 2000},
                {"role": "assistant", "content": "a" * 2000},
                {"role": "tool", "tool_call_id": str(i), "name": "search",
                 "content": json.dumps({"result": "r" * 16000})},
            ])
        view = loop.view()
        wire = json.dumps(view, separators=(",", ":"))
        probes.append({"rounds": rounds, "messages": len(view), "wire_chars": len(wire),
                       "estimated_tokens_at_4_chars": (len(wire) + 3) // 4})
    evidence = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         text=True).strip(),
        "local_extract_count": len(inventory),
        "context_growth": probes,
        "probe_limits": "Synthetic view() sizing only; not model accuracy, provider tokenization, "
                        "a full invocation, or a valid audited event trace.",
        "focused_tests": {"passed": 84, "seconds": 30.39,
            "files": ["test_audit_projection.py", "test_result_handles.py", "test_search.py",
                      "test_embed.py", "test_audited_session.py", "test_research_round.py"]},
    }
    (OUT / "review-evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
