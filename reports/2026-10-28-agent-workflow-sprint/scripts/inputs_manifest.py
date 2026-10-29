"""WS0: hash every static input so the sprint is reproducible; live logs get size and mtime only.

Output: data/inputs.manifest.json
"""
from __future__ import annotations

import glob
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CLAUDE_PROJECTS, CODEX_SESSIONS, DATA, REPO, git, sha256_file, to_iso, write_json  # noqa: E402

TRANSCRIPTS = [
    r"C:\Users\jakem\Downloads\workflow discussion and review - gemini.md",
    r"E:\# Review Librarian V2 - chatgpt transcript.txt",
    r"E:\# Review Librarian V2 - chatgpt transcript -2.txt",
    r"E:\# Review Librarian V2 - claud transcript.txt",
    r"E:\Librarian setup and Q-ball research-claud transcript.md",
]


def entry(path: Path, hash_it: bool = True) -> dict:
    st = path.stat()
    out = {"path": str(path), "bytes": st.st_size, "mtime": to_iso(datetime.fromtimestamp(st.st_mtime, tz=timezone.utc))}
    if hash_it:
        out["sha256"] = sha256_file(path)
    return out


def main() -> int:
    manifest = {"created": to_iso(datetime.now(timezone.utc)), "repo_head": git("rev-parse", "HEAD").strip(), "groups": {}}
    g = manifest["groups"]
    g["transcripts"] = [entry(Path(p)) for p in TRANSCRIPTS]
    g["papers"] = [entry(p) for p in sorted(Path(r"E:\Librarian research").glob("*.pdf"))]
    g["delegation_receipts"] = [entry(p) for p in sorted((REPO / "tmp" / "deepinfra-delegation").rglob("*")) if p.is_file() and p.suffix in (".json", ".md", ".txt")]
    g["repo_docs"] = [entry(REPO / "docs" / "unified-implementation-plan.md")] + [entry(p) for p in sorted((REPO / "reports").glob("2026-10-2*.md"))]
    g["live_logs_size_only"] = (
        [entry(p, hash_it=False) for p in sorted((CLAUDE_PROJECTS / "D--Librarian-V2").glob("*.jsonl"))]
        + [entry(Path(p), hash_it=False) for p in sorted(glob.glob(str(CODEX_SESSIONS / "2026" / "10" / "*" / "rollout-*.jsonl")))[:3]]
    )
    g["live_logs_size_only"].append({"note": "Codex rollouts: 328 files under ~/.codex/sessions/2026/{09,10}; counts and sizes recorded by codex_threads.csv"})
    # revision 2 inputs: the second-pass review, the Claude scratchpad runners' records (outside the repository), and the primary pages read
    second = REPO / "reports" / "2026-10-28-agent-workflow-second-pass"
    g["second_pass_review"] = [entry(p) for p in sorted(second.glob("*.md"))] + [entry(p) for p in sorted((second / "data").glob("*.json")) + sorted((second / "data").glob("claim_review.csv"))]
    scratch = Path(os.path.expanduser("~")) / "AppData" / "Local" / "Temp" / "claude" / "D--Librarian-V2"
    g["claude_scratchpad_runner_records"] = [entry(p) for p in sorted(scratch.glob("2ca0af49*/scratchpad/reader/*")) if p.is_file()] + [entry(p) for p in sorted(scratch.glob("2ca0af49*/scratchpad/reader/out/*.log"))]
    g["primary_pages_read_2026_10_28"] = [{"url": u, "note": "read with the built-in browser or the fetch tool; not saved as files"} for u in (
        "https://openai.com/index/navier-stokes-solution/", "https://github.com/openai/math", "https://github.com/openai/math/blob/main/history.md",
        "https://docs.vllm.ai/en/latest/features/structured_outputs/", "https://docs.deepinfra.com/account/data-privacy", "https://ojs.aaai.org/index.php/ICAPS/article/view/36143")]
    write_json(DATA / "inputs.manifest.json", manifest)
    print({k: len(v) for k, v in g.items()}, "head", manifest["repo_head"][:7])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
