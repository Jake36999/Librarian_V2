"""1a: per-commit table, line survival at HEAD, and a line-level rework graph.

Outputs: data/commits.csv, data/rework_edges.csv, data/git_summary.json
Rework edge (i -> j): commit j removed or replaced lines that commit i introduced,
found with `git blame` on j's parent. Bookkeeping files (plan, docs, reports) are
excluded from rework attribution; they are counted as bookkeeping instead.
Provenance fields come from commit-message text, so they are tier R, not M.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPO, git, parse_ts, write_csv, write_json  # noqa: E402

PLAN = "docs/unified-implementation-plan.md"
HDR = re.compile(r"^([0-9a-f]{40}) \d+ (\d+)(?: \d+)?$")
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
TASK_ID = re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,3}[A-Z]?)\b")
MODEL = re.compile(r"(DeepSeek-V4(?:\.1)?-(?:Pro|Flash)(?:-\d+)?|GLM-5\.3(?:-Flash)?|Qwen3\.5-397B|Qwen3-Coder|MiMo-V2\.6-(?:Pro|Flash))")
FINDINGS = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:\w+\s+){0,2}findings?\b", re.I)
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
FIX_SUBJECT = re.compile(r"\b(fix|fixes|repair|correct|regress|hotfix|revert|follow[- ]?up|close the .* gaps?)\b", re.I)
TEXT_EXT = {".py", ".md", ".ts", ".js", ".ps1", ".json", ".toml", ".html", ".css", ".bat", ".yml", ".yaml", ".xml", ".txt", ".in", ".cfg"}


def file_class(path: str) -> str:
    if path == PLAN:
        return "plan"
    if path.startswith("src/"):
        return "src"
    if path.startswith("tests/"):
        return "tests"
    if path.startswith("scripts/"):
        return "scripts"
    if path.startswith("docs/"):
        return "docs"
    if path.startswith("reports/"):
        return "reports"
    if path.startswith(("plugin/", "obsidian/", "ui/")):
        return "client"
    return "other"


def blame_map(rev: str, path: str) -> dict[int, str]:
    run = subprocess.run(["git", "-C", str(REPO), "blame", "--line-porcelain", "-w", rev, "--", path],
                         capture_output=True, encoding="utf-8", errors="replace")
    if run.returncode != 0:
        return {}
    result, cur = {}, None
    for line in run.stdout.splitlines():
        if line.startswith("\t"):
            if cur:
                result[cur[1]] = cur[0]
        else:
            m = HDR.match(line)
            if m:
                cur = (m.group(1), int(m.group(2)))
    return result


def commit_hunks(commit: str) -> dict[str, list[tuple[int, int]]]:
    text = git("diff", "-U0", "--no-color", f"{commit}^", commit)
    hunks: dict[str, list[tuple[int, int]]] = defaultdict(list)
    path = None
    for line in text.splitlines():
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
        else:
            m = HUNK.match(line)
            if m and path:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) is not None else 1
                if count > 0:
                    hunks[path].append((start, start + count - 1))
    return hunks


def main() -> int:
    skip_blame = "--skip-blame" in sys.argv
    master = set(git("rev-list", "master").split())
    raw = git("log", "--reverse", "--all", "--format=%H%x1f%aI%x1f%cI%x1f%P%x1f%s%x1f%b%x1e")
    commits = []
    for chunk in raw.split("\x1e"):
        chunk = chunk.strip("\n")
        if not chunk.strip():
            continue
        h, ai, ci, parents, subject, body = chunk.split("\x1f", 5)
        commits.append({"hash": h.strip(), "author_time": ai, "commit_time": ci, "parents": parents.split(), "subject": subject, "body": body})

    numstat: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    cur = None
    for line in git("log", "--all", "--format=@@@%H", "--numstat", "--no-renames").splitlines():
        if line.startswith("@@@"):
            cur = line[3:].strip()
        elif line.strip() and cur:
            a, d, p = line.split("\t", 2)
            numstat[cur].append((p, int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0))

    # survival at HEAD
    survive: Counter = Counter()
    if not skip_blame:
        files = [f for f in git("ls-files").splitlines() if os.path.splitext(f)[1].lower() in TEXT_EXT]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for m in pool.map(lambda f: blame_map("HEAD", f), files):
                survive.update(m.values())

    # rework graph
    edges = []
    if not skip_blame:
        def edges_for(c):
            if len(c["parents"]) != 1 or c["hash"] not in master:
                return []
            out = []
            hunks = commit_hunks(c["hash"])
            for path, ranges in hunks.items():
                if file_class(path) not in ("src", "tests", "scripts", "client", "other"):
                    continue
                bm = blame_map(c["hash"] + "^", path)
                if not bm:
                    continue
                per: Counter = Counter()
                for a, b in ranges:
                    for ln in range(a, b + 1):
                        sha = bm.get(ln)
                        if sha and sha != c["hash"]:
                            per[sha] += 1
                for sha, n in per.items():
                    out.append({"orig_commit": sha, "later_commit": c["hash"], "file": path, "lines": n})
            return out
        with ThreadPoolExecutor(max_workers=6) as pool:
            for res in pool.map(edges_for, commits):
                edges.extend(res)
    ctime = {c["hash"]: parse_ts(c["commit_time"]) for c in commits}
    for e in edges:
        e["hours_after"] = round((ctime[e["later_commit"]] - ctime[e["orig_commit"]]).total_seconds() / 3600, 2) if e["orig_commit"] in ctime else ""
    by_orig: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        by_orig[e["orig_commit"]].append(e)

    rows = []
    for c in commits:
        files = numstat.get(c["hash"], [])
        classes = sorted({file_class(p) for p, _, _ in files})
        ins = sum(a for _, a, _ in files)
        dele = sum(d for _, _, d in files)
        body = c["body"]
        low = body.lower()
        norm = " ".join(low.split())  # a phrase such as "Drafted by X" can break across lines in commit text
        trailer = ""
        if "Co-Authored-By: Claude Opus 5.5" in body:
            trailer = "claude-opus-5-5"
        elif "Co-Authored-By: Claude Sonnet 4.6" in body:
            trailer = "claude-sonnet-4-6"
        elif "Co-Authored-By:" in body:
            trailer = "other"
        code_classes = {"src", "tests", "scripts", "client", "other"}
        bookkeeping = bool(classes) and set(classes) <= {"plan", "docs", "reports"}
        n_find = ""
        m = FINDINGS.search(body)
        if m:
            tok = m.group(1).lower()
            n_find = int(tok) if tok.isdigit() else WORDS.get(tok, "")
        ins_text = sum(a for p, a, _ in files if os.path.splitext(p)[1].lower() in TEXT_EXT)
        surv = survive.get(c["hash"], 0)
        mine = by_orig.get(c["hash"], [])
        t0 = ctime[c["hash"]]
        def within(h):
            return sum(e["lines"] for e in mine if e["hours_after"] != "" and e["hours_after"] <= h)
        rows.append({
            "hash": c["hash"], "short": c["hash"][:7], "on_master": c["hash"] in master, "n_parents": len(c["parents"]),
            "author_time": c["author_time"], "commit_time": c["commit_time"], "subject": c["subject"],
            "agent_trailer": trailer, "files_n": len(files), "insertions": ins, "deletions": dele,
            "classes": ";".join(classes),
            "touches_src": "src" in classes, "touches_tests": "tests" in classes, "touches_scripts": "scripts" in classes,
            "touches_plan": "plan" in classes, "touches_docs": "docs" in classes, "touches_reports": "reports" in classes,
            "bookkeeping_only": bookkeeping, "plan_only": bool(files) and all(p == PLAN for p, _, _ in files),
            "code_commit": bool(set(classes) & code_classes),
            "task_ids": ";".join(sorted(set(TASK_ID.findall(c["subject"] + " " + body)))),
            "models_named": ";".join(sorted(set(MODEL.findall(body)))),
            "drafted_by": bool(re.search(r"drafted (by|with)", norm)), "reviewed_by": bool(re.search(r"reviewed (by|with)|delegate reviews?", norm)),
            "findings_n_text": n_find, "rejected_text": ("rejected" in low), "fixed_in_review": ("fixed in review" in low),
            "is_revert": c["subject"].lower().startswith("revert"), "fix_like_subject": bool(FIX_SUBJECT.search(c["subject"])),
            "insertions_text_files": ins_text, "surviving_lines_at_head": surv,
            "survival_ratio": round(min(1.0, surv / ins_text), 3) if ins_text else "",
            "rewritten_lines_24h": within(24), "rewritten_lines_72h": within(72), "rewritten_lines_any": within(10**9),
            "first_rework_hours": min((e["hours_after"] for e in mine if e["hours_after"] != ""), default=""),
        })
    write_csv(DATA / "commits.csv", rows)
    edges.sort(key=lambda e: (e["orig_commit"], e["later_commit"], e["file"]))
    write_csv(DATA / "rework_edges.csv", edges)
    m_rows = [r for r in rows if r["on_master"]]
    write_json(DATA / "git_summary.json", {
        "commits_all_branches": len(rows), "commits_on_master": len(m_rows),
        "code_commits": sum(1 for r in m_rows if r["code_commit"]),
        "bookkeeping_only": sum(1 for r in m_rows if r["bookkeeping_only"]),
        "plan_only": sum(1 for r in m_rows if r["plan_only"]),
        "trailers": dict(Counter(r["agent_trailer"] or "none" for r in m_rows)),
        "with_drafted_by": sum(1 for r in m_rows if r["drafted_by"]),
        "with_reviewed_by": sum(1 for r in m_rows if r["reviewed_by"]),
        "rework_edges": len(edges), "head": git("rev-parse", "HEAD").strip(), "skip_blame": skip_blame,
    })
    print("commits", len(rows), "master", len(m_rows), "edges", len(edges))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
