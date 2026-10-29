"""WS2: turn the sprint inputs into packets the delegation runner can read.

- papers: PDF -> text with [[PAGE n]] markers, inventory, duplicate detection, triage excerpts
- transcripts: secret-redacted (line count preserved), line-numbered chunks `L00123| text`
- code/doc packets: line-numbered copies so a cited file:line can be checked mechanically
Everything is written under tmp/sprint (untracked). Outputs in data/: papers_inventory.csv,
redaction_report.json, packet_manifest.json
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import DATA, REPO, TMP, write_csv, write_json  # noqa: E402

import fitz  # PyMuPDF

PDF_DIR = Path(r"E:\Librarian research")
VAULT = Path(r"D:\Resource-Library")
PAPERS = TMP / "src" / "papers"
PACKETS = TMP / "packets"
DOI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>\]\)\|,;]+)")
ARXIV = re.compile(r"arXiv:\s*(\d{4}\.\d{4,5})", re.I)
HEADING = re.compile(r"^\s*(?:\d{1,2}(?:\.\d{1,2}){0,3}\.?|[IVX]{1,5}\.)\s+[A-Z][A-Za-z0-9 ,:;&()\-/']{3,90}$")
SECRETS = {
    "private_key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "sk_token": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "named_secret": re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|secret[_-]?key|password)\b\s*[:=]\s*['\"][^'\"\r\n]{12,}['\"]"),
    "instance_api_key": re.compile(r"(?i)instance_api_key['\"]?\s*[:=]\s*['\"]?[0-9a-f]{24,}"),
    "bearer": re.compile(r"Bearer\s+[A-Za-z0-9._\-]{20,}"),
    "provider_token": re.compile(r"\b(?:ghp_|hf_|AKIA)[A-Za-z0-9]{16,}"),
    "env_assign": re.compile(r"(?i)\bDEEPINFRA_API_KEY\s*=\s*\S+"),
}
TRANSCRIPTS = {
    "chat1": r"E:\# Review Librarian V2 - chatgpt transcript.txt",
    "chat2": r"E:\# Review Librarian V2 - chatgpt transcript -2.txt",
    "claude_dev": r"E:\# Review Librarian V2 - claud transcript.txt",
    "qball": r"E:\Librarian setup and Q-ball research-claud transcript.md",
    "gemini": r"C:\Users\jakem\Downloads\workflow discussion and review - gemini.md",
}
CHUNK_BYTES = 100_000  # hidden reasoning in the reader models costs about 2.4x the visible JSON; smaller chunks avoid truncation
CHUNK_BYTES_BY_KEY = {"gemini": 160_000}  # the Gemini file stays one packet; extra halves are sliced below
CODE_REDACTIONS: Counter = Counter()


def slug(name: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-")[:60]
    return f"{stem}-{hashlib.sha1(name.encode()).hexdigest()[:4]}"


def shingles(text: str, n: int = 5) -> set:
    words = re.findall(r"[a-z0-9]+", text.lower())[:600]
    return {" ".join(words[i:i + n]) for i in range(max(0, len(words) - n))}


def prep_papers() -> list[dict]:
    PAPERS.mkdir(parents=True, exist_ok=True)
    PACKETS.mkdir(parents=True, exist_ok=True)
    rows, sigs, excerpts = [], {}, {}
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        row = {"file": pdf.name, "slug": slug(pdf.name), "bytes": pdf.stat().st_size}
        try:
            doc = fitz.open(pdf)
            pages = [p.get_text("text").replace("\x00", "") for p in doc]
            meta_title = (doc.metadata or {}).get("title") or ""
        except Exception as exc:  # noqa: BLE001 - a broken PDF is recorded, not fatal
            row.update({"error": type(exc).__name__, "pages": 0})
            rows.append(row)
            continue
        text = "".join(f"[[PAGE {i}]]\n{t}\n" for i, t in enumerate(pages, 1))
        (PAPERS / f"{row['slug']}.txt").write_text(text, encoding="utf-8", newline="\n")
        chars = sum(len(t) for t in pages)
        # Identifiers come from the first page only: later pages hold reference lists whose DOIs and
        # arXiv ids belong to cited papers (the first version of this script fetched those by mistake).
        front = (pages[0] if pages else "") + "\n" + (pages[1][:1500] if len(pages) > 1 else "")
        dois = Counter(m.rstrip(".,;)") for m in DOI.findall(front))
        arx = Counter(ARXIV.findall(pages[0] if pages else ""))
        first_lines = [l.strip() for l in (pages[0] if pages else "").splitlines() if len(l.strip()) > 12][:2]
        abstract = ""
        m = re.search(r"(?is)\babstract\b[\s:.\-—]*(.{200,1500}?)(?:\n\s*\n|keywords|index terms|1\.\s+introduction)", "\n".join(pages[:2]))
        if m:
            abstract = re.sub(r"\s+", " ", m.group(1)).strip()
        years = re.findall(r"\b(20[12]\d)\b", "\n".join(pages[:1]))
        row.update({
            "pages": len(pages), "chars": chars, "chars_per_page": round(chars / max(1, len(pages))), "likely_scanned": chars / max(1, len(pages)) < 300,
            "meta_title": meta_title[:140], "first_lines": " / ".join(first_lines)[:200],
            "doi": dois.most_common(1)[0][0] if dois else "", "arxiv_id": arx.most_common(1)[0][0] if arx else "",
            "year_guess": Counter(years).most_common(1)[0][0] if years else "", "abstract_chars": len(abstract),
        })
        # triage excerpt: first two pages, last page, and a heading list with page numbers
        heads = []
        for i, t in enumerate(pages, 1):
            for line in t.splitlines():
                if HEADING.match(line) and len(heads) < 60:
                    heads.append(f"p{i}: {line.strip()}")
        body = "[[PAGE 1]]\n" + pages[0][:9000] + ("\n[[PAGE 2]]\n" + pages[1][:6000] if len(pages) > 1 else "")
        if len(pages) > 3:
            body += f"\n[[PAGE {len(pages)}]]\n" + pages[-1][:4500]
        excerpts[row["slug"]] = f"=== PAPER {row['slug']} (file: {pdf.name}; pages: {len(pages)}) ===\nHEADINGS:\n" + "\n".join(heads) + "\nEXCERPT:\n" + body
        sigs[row["slug"]] = shingles(pages[0] + (pages[1] if len(pages) > 1 else ""))
        row["sha256"] = hashlib.sha256(pdf.read_bytes()).hexdigest()
        rows.append(row)
    by_sha: dict[str, str] = {}
    for r in rows:
        r["duplicate_of"] = ""
        r["near_duplicate_of"] = ""
        r["near_duplicate_jaccard"] = ""
        if r.get("sha256"):
            if r["sha256"] in by_sha:
                r["duplicate_of"] = by_sha[r["sha256"]]
            else:
                by_sha[r["sha256"]] = r["file"]
    slugs = [r["slug"] for r in rows if r["slug"] in sigs]
    for i, a in enumerate(slugs):
        for b in slugs[i + 1:]:
            inter = len(sigs[a] & sigs[b])
            union = len(sigs[a] | sigs[b]) or 1
            if inter / union >= 0.6:
                ra = next(r for r in rows if r["slug"] == a)
                rb = next(r for r in rows if r["slug"] == b)
                rb["near_duplicate_of"] = ra["file"]
                rb["near_duplicate_jaccard"] = round(inter / union, 2)
    # triage batches of 5 papers
    ordered = [r["slug"] for r in rows if r["slug"] in excerpts]
    batches = []
    for k in range(0, len(ordered), 5):
        name = f"P1-batch-{k // 5 + 1:02d}.txt"
        (PACKETS / name).write_text("\n\n".join(excerpts[s] for s in ordered[k:k + 5]), encoding="utf-8", newline="\n")
        batches.append({"packet": name, "slugs": ordered[k:k + 5]})
    write_csv(DATA / "papers_inventory.csv", rows)
    write_json(TMP / "lanes" / "p1_batches.json", batches)
    return rows


def redact(line: str, counts: Counter) -> str:
    for name, pat in SECRETS.items():
        line, n = pat.subn("[REDACTED]", line)
        if n:
            counts[name] += n
    return line


def chunk_file(key: str, path: str, counts: Counter, manifest: list) -> None:
    raw = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    limit = CHUNK_BYTES_BY_KEY.get(key, CHUNK_BYTES)
    out, start, size, k = [], 1, 0, 1

    def flush(end: int) -> None:
        nonlocal out, start, size, k
        if not out:
            return
        name = f"T-{key}-{k:02d}.txt"
        header = f"### CHUNK {name} source={Path(path).name} lines {start}-{end} (each line below is prefixed `L<number>| `)\n"
        (PACKETS / name).write_text(header + "\n".join(out) + "\n", encoding="utf-8", newline="\n")
        manifest.append({"packet": name, "source": path, "first_line": start, "last_line": end, "bytes": size})
        out, start, size, k = [], end + 1, 0, k + 1

    for n, line in enumerate(raw, 1):
        text = redact(line, counts)
        entry = f"L{n:05d}| {text}"
        out.append(entry)
        size += len(entry.encode("utf-8")) + 1
        if (size >= limit and not text.strip()) or size >= int(limit * 1.25):
            flush(n)
    flush(len(raw))


def slice_packet(source_name: str, first: int, last: int | None, new_name: str, manifest: list) -> None:
    """A line range of an existing numbered packet, keeping the original L-numbers."""
    keep = []
    for row in (PACKETS / source_name).read_text(encoding="utf-8").splitlines():
        m = re.match(r"^L(\d{5})\| ", row)
        if m and int(m.group(1)) >= first and (last is None or int(m.group(1)) <= last):
            keep.append(row)
    header = f"### CHUNK {new_name} (slice of {source_name}; lines {first}-{last or 'end'}; each line below is prefixed `L<number>| `)\n"
    (PACKETS / new_name).write_text(header + "\n".join(keep) + "\n", encoding="utf-8", newline="\n")
    manifest.append({"packet": new_name, "source": source_name, "first_line": first, "last_line": last, "bytes": len(keep)})


def numbered_copy(src: Path, dest_rel: str, manifest: list, lines: tuple[int, int] | None = None, anchor: str | None = None) -> str:
    text = src.read_text(encoding="utf-8", errors="replace").splitlines()
    a, b = lines if lines else (1, len(text))
    body = "\n".join(f"L{n:05d}| {redact(text[n - 1], CODE_REDACTIONS)}" for n in range(a, min(b, len(text)) + 1))
    dest = PACKETS / "code" / dest_rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(body + "\n", encoding="utf-8", newline="\n")
    rel = dest.relative_to(REPO).as_posix()
    manifest.append({"packet": rel, "source": anchor or str(src), "first_line": a, "last_line": min(b, len(text)), "bytes": dest.stat().st_size})
    return rel


COMPONENTS = {
    "A1-mcp-boundary": [
        "src/resource_librarian/mcp_server.py", "src/resource_librarian/cli.py", "src/resource_librarian/host.py",
        "src/resource_librarian/connection.py", "src/resource_librarian/mcp_client.py", "plugin/.mcp.json",
        "docs/adapter-contract.md", "docs/product-contract.md", "reports/2026-10-24-architecture-blindspot-verification.md"],
    "A2-core-writer": [
        "src/resource_librarian/coordination.py", "src/resource_librarian/registry.py", "src/resource_librarian/index.py",
        "src/resource_librarian/promote.py", "src/resource_librarian/staging.py", "src/resource_librarian/tools/staging.py",
        "docs/index-ownership.md", "docs/staging-write-safety.md"],
    "A3-invocation-runtime": [
        "src/resource_librarian/model_invocation.py", "src/resource_librarian/providers.py", "src/resource_librarian/service_adapters.py",
        "src/resource_librarian/service_routes.py", "src/resource_librarian/role_routes.py", "src/resource_librarian/adapters/openai_chat.py",
        "src/resource_librarian/adapters/anthropic_messages.py", "docs/model-invocation-architecture.md", "docs/model-adapter-requirements.md", "docs/role-routing.md"],
    "A4-qualification-expectations": [
        "docs/qualification.md", "docs/model-expectations-registry.md", "docs/model-adapter-cohort-2026-10-23.md", "docs/capability-matrix.md",
        "src/resource_librarian/model_expectation_authoring.py", "src/resource_librarian/evaluation.py", "src/resource_librarian/validation_fixtures.py",
        "src/resource_librarian/tools/model_expectations.py", "tests/test_qualification_jobs.py", "scripts/validate_deepinfra_current.py",
        "reports/2026-10-26-adapt07-continuation-probe.md", "reports/2026-10-26-adapt09-prompt-layout.md", "reports/2026-10-26-adapt11-tool-surface.md"],
    "A5-delegation-and-parallelism": [
        "scripts/delegate_deepinfra.py", "tests/test_deepinfra_delegation.py", "src/resource_librarian/tools/delegate.py", "src/resource_librarian/tools/sandbox.py",
        "src/resource_librarian/tools/batch.py", "src/resource_librarian/tools/pace.py", "src/resource_librarian/tools/scout.py", "src/resource_librarian/tools/workbench.py",
        "src/resource_librarian/batch.py", "src/resource_librarian/sandbox.py", "src/resource_librarian/effort.py", "src/resource_librarian/scout.py",
        "src/resource_librarian/workbench.py", "src/resource_librarian/trace.py", "src/resource_librarian/checkpoints.py", "src/resource_librarian/broker.py",
        "src/resource_librarian/agenda.py", "src/resource_librarian/agent_runtime.py"],
    "A6-session-and-harness": [
        "src/resource_librarian/session.py", "src/resource_librarian/loop.py", "docs/audited-engagement-harness.md", "docs/release-implementation-queue.md",
        "reports/2026-10-24-harness-and-adapter-plan-review.md"],
}
PLAN_RANGES = [(68, 131), (132, 215), (309, 436)]
PRIOR_REVIEWS = [
    "reports/2026-10-20-executive-review.md", "reports/2026-10-20-model-platform-and-deployment-review.md",
    "reports/2026-10-23-system-attention-deployment-and-runtime-review.md", "reports/2026-10-24-chatgpt-transcript-review.md",
    "reports/2026-10-24-architecture-blindspot-verification.md", "reports/2026-10-24-handoff-to-chatgpt.md",
]
VAULT_REVIEWS = [
    ("internal docs/chatgpt-review/Requirements - V2 Research Pipeline and Project Access 2026-09-30.md", "vault-requirements.md"),
    ("internal docs/chatgpt-review/Librarian Uni session performance - 2026-09-30.md", "vault-session-performance.md"),
    ("08-Workflows/Opening Prompt - Dedicated Research Agent.md", "vault-opening-prompt.md"),
    ("08-Workflows/Workflow - Contribution By Outside Agents.md", "vault-contribution-workflow.md"),
]


def main() -> int:
    manifest: list[dict] = []
    papers = prep_papers()
    counts: Counter = Counter()
    redactions = {}
    for key, path in TRANSCRIPTS.items():
        before = Counter(counts)
        chunk_file(key, path, counts, manifest)
        redactions[key] = {k: counts[k] - before[k] for k in counts if counts[k] - before[k]}
    slice_packet("T-gemini-01.txt", 290, 420, "T-gemini-02.txt", manifest)
    slice_packet("T-gemini-01.txt", 421, None, "T-gemini-03.txt", manifest)
    for lane, files in COMPONENTS.items():
        for rel in files:
            numbered_copy(REPO / rel, rel.replace("/", "__") + ".txt", manifest)
    plan_parts = []
    for a, b in PLAN_RANGES:
        plan_parts.append(numbered_copy(REPO / "docs/unified-implementation-plan.md", f"docs__unified-implementation-plan.md.L{a}-{b}.txt", manifest, (a, b)))
    for rel in PRIOR_REVIEWS:
        numbered_copy(REPO / rel, rel.replace("/", "__") + ".txt", manifest)
    for rel, name in VAULT_REVIEWS:
        numbered_copy(VAULT / rel, f"ext__{name}.txt", manifest, anchor=str(VAULT / rel))
    write_json(DATA / "redaction_report.json", {"patterns_matched_per_source": redactions, "code_and_doc_packets": dict(CODE_REDACTIONS),
                                                "note": "counts only; line numbers preserved"})
    write_json(TMP / "lanes" / "packet_manifest.json", manifest)
    write_json(DATA / "packet_manifest.json", [{k: v for k, v in m.items() if k != "source" or not str(v).startswith("C:")} for m in manifest])
    print(f"papers={len(papers)} scanned={sum(1 for p in papers if p.get('likely_scanned'))} with_doi={sum(1 for p in papers if p.get('doi'))} "
          f"packets={len(manifest)} redactions={dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
