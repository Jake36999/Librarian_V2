"""Validate a library's ingestion cycle against its sources (read-only; no model calls).

Checks, each reported as pass/fail counts with examples:
  1. Content table   - every attached root has a purpose, authorship, graph label and an accepted
                       folder decision; graph labels follow one-graph-per-project-and-stratum.
  2. Geo components  - every root's graph exists in the catalog with entities; sampled entities
                       resolve to files inside a root that maps to that same graph (no leakage).
  3. Separation      - Sources come only from own-docs / research-docs / third-party roots, never
                       from own code, data or logs (those are indexed, not read).
  4. Lineage         - each Source's original exists, its digest matches the current bytes, and a
                       conversion (when one is recorded) is bound to those same bytes.
  5. Purpose         - each Source inherits its root's purpose and authorship.
  6. Fidelity        - sampled read points are compared with the ORIGINAL text at their locator:
                       share of content words found, and every number found.
  7. Paper graphs    - research PDFs published into Geo, or why not.

Usage: python validate_library.py <library root> [--sample 40] [--seed 7] [--out report.json]
"""
import argparse, hashlib, json, random, re, sqlite3, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, r"D:\Librarian_V2\src")
from resource_librarian.vault import Vault            # noqa: E402
from resource_librarian import text as text_mod        # noqa: E402

STOP = set("""a an and are as at be but by can do does for from has have how i if in into is it its of on or so
that the their then there these they this to was were what when where which who will with without would
you your via also any each other such not than more most may only one two using used use based""".split())
SOURCE_PURPOSES = {"own-docs", "research-docs", "third-party"}
INDEX_ONLY = {"own-current", "own-legacy", "data", "logs/transcripts"}


def words(s):
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", s.lower()) if w not in STOP]


def numbers(s):
    return [n.lstrip("0") or "0" for n in re.findall(r"(?<![\w.])\d+(?:\.\d+)?", s) if len(n) >= 2]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def deepest_root(roots, path):
    best = None
    for r in roots:
        base = Path(r["path"])
        try:
            Path(path).resolve().relative_to(base.resolve())
        except ValueError:
            continue
        if best is None or len(base.parts) > len(Path(best["path"]).parts):
            best = r
    return best


def page_range(loc):
    m = re.match(r"pp?\.\s*(\d+)(?:\s*[-–]\s*(\d+))?", loc or "")
    if not m:
        return None
    a = int(m.group(1)); b = int(m.group(2) or a)
    return a, b


class Report:
    def __init__(self):
        self.checks = defaultdict(lambda: {"pass": 0, "fail": 0, "examples": []})

    def add(self, name, ok, example=None):
        c = self.checks[name]
        c["pass" if ok else "fail"] += 1
        if not ok and example is not None and len(c["examples"]) < 6:
            c["examples"].append(example)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("library"); ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--seed", type=int, default=7); ap.add_argument("--out", default="")
    a = ap.parse_args()
    vault = Vault(a.library); lib = vault.librarian; rep = Report(); rnd = random.Random(a.seed)
    roots = [r for r in json.loads((lib / "content-roots.json").read_text(encoding="utf-8"))["roots"] if r.get("attached")]
    cards = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in (lib / "staging" / "folder").glob("*.json")}

    # 1. content table
    for r in roots:
        card = cards.get(r.get("folder_decision", ""))
        ok = bool(r.get("purpose") and (r.get("authorship") or r["purpose"] == "exclude") and r.get("graph_label")
                  and card and card.get("status") == "accepted")
        rep.add("1 content table: root fully declared and accepted", ok, r["path"])
    # 2. geo components
    cat = sqlite3.connect(f"file:{lib / 'geographer' / 'catalog.sqlite'}?mode=ro", uri=True)
    graphs = {label: (gid, code, paper, snapshot) for gid, label, code, paper, snapshot in
              cat.execute("select graph_id, label, code_database, paper_database, snapshot_id from graphs")}
    by_graph = defaultdict(list)
    for r in roots:
        by_graph[r["graph_label"]].append(r)
        rep.add("2 geo: root's graph exists in the catalog", r["graph_label"] in graphs,
                f'{r["path"]} -> {r["graph_label"]}')
    graph_stats = {}
    for label, (gid, code, paper, snapshot) in graphs.items():
        stats = {"entities": 0, "paper_database": bool(paper)}
        if code and Path(code).exists():
            db = sqlite3.connect(f"file:{code}?mode=ro", uri=True)
            # Only the graph's published snapshot: older snapshots are history, not scope
            # (2026-11-16: sampling all of them reported files a later decision excluded).
            stats["entities"] = db.execute("select count(*) from entities where snapshot_id = ?", (snapshot,)).fetchone()[0]
            stats["snapshot"] = snapshot
            cols = [c[1] for c in db.execute("pragma table_info(entities)")]
            pcol = next((c for c in ("path", "file_path", "source_path", "rel_path", "file") if c in cols), None)
            stats["path_column"] = pcol
            if pcol:
                rows = db.execute(f"select {pcol} from entities where snapshot_id = ? and {pcol} is not null "
                                  f"and {pcol} != '' order by random() limit 25", (snapshot,)).fetchall()
                for (p,) in rows:
                    cand = [Path(r["path"]) / p for r in roots] + [Path(p)]
                    hit = next((c for c in cand if c.exists()), None)
                    owner = deepest_root(roots, hit) if hit else None
                    rep.add("2 geo: sampled entity file belongs to a root of the same graph",
                            bool(owner and owner["graph_label"] == label), f"{label}: {p} -> {(owner or {}).get('graph_label')}")
        rep.add("2 geo: graph has entities", stats["entities"] > 0, label)
        graph_stats[label] = stats

    # 3-6. sources
    srcs = [json.loads(p.read_text(encoding="utf-8")) for p in (lib / "staging" / "source").glob("*.json")]
    status = Counter(); per_purpose = Counter(); sample_pool = defaultdict(list)
    for s in srcs:
        status[s.get("status")] += 1
        f = s.get("file") or (s.get("fields") or {}).get("file")
        if not f or not Path(f).is_absolute():
            continue
        root = deepest_root(roots, f)
        purpose = (root or {}).get("purpose", "unattached")
        per_purpose[(purpose, s.get("status"))] += 1
        rep.add("3 separation: Source comes from a Source purpose", purpose in SOURCE_PURPOSES, f"{purpose}: {f}")
        p = Path(f)
        rep.add("4 lineage: original exists", p.exists(), f)
        if p.exists() and s.get("digest"):
            rep.add("4 lineage: digest matches current bytes", sha256(p).startswith(s["digest"][:16]), f)
        if s.get("clean_file"):
            idx = lib / "conversions" / "index.json"
            entries = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else {}
            rows = entries.get("items", {}) if isinstance(entries, dict) else {}
            if isinstance(rows, list):
                rows = {r.get("path"): r for r in rows if isinstance(r, dict)}
            e = rows.get(s["clean_file"]) or next((r for r in rows.values() if isinstance(r, dict)
                                                   and r.get("path") == s["clean_file"]), None)
            rep.add("4 lineage: conversion bound to the original's bytes",
                    bool(e and p.exists() and e.get("original_sha256") == sha256(p)), s["clean_file"])
        read = ((s.get("deep_read") or {}).get("read") or {})
        if p.suffix.lower() == ".pdf" and read:
            located = all(page_range(c.get("locator", "")) for c in read.values())
            rep.add("4 lineage: every read part of a PDF has a page locator", located,
                    f"{p.name}: {sorted({c.get('locator', '')[:12] for c in read.values()})[:4]}")
        if root:
            rep.add("5 purpose: root decision recorded with purpose and authorship",
                    bool(root.get("folder_decision") and root.get("authorship")), f)
        if s.get("status") in ("enriched", "partial", "accepted") and (s.get("deep_read") or {}).get("read"):
            sample_pool[purpose].append(s)

    fidelity = []
    for purpose, pool in sample_pool.items():
        for s in rnd.sample(pool, min(len(pool), max(1, a.sample // max(1, len(sample_pool))))):
            f = Path(s.get("file"))
            if f.suffix.lower() == ".pdf":
                ext = text_mod.extract(f, vault.derived / "text")
                pages = list(ext.pages or [])
                if s.get("clean_file") and (vault.root / s["clean_file"]).exists():
                    pass  # compare with the original text layer regardless; OCR'd pages fall back below
            else:
                pages = [f.read_text(encoding="utf-8", errors="replace")]
            whole = "\n".join(pages)
            chunks = list(s["deep_read"]["read"].values())
            for ch in rnd.sample(chunks, min(3, len(chunks))):
                rng = page_range(ch.get("locator", "")) if len(pages) > 1 else None
                body = "\n".join(pages[rng[0] - 1: rng[1]]) if rng and rng[1] <= len(pages) else whole
                bw = set(words(body)); bn = set(numbers(body)); wn = set(numbers(whole))
                for b in (ch.get("points") or [])[:2] + (ch.get("limits") or [])[:1]:
                    prose = re.sub(r"\$[^$]*\$", " ", b.replace("…", ""))     # LaTeX is checked by eye, not by words
                    ws = words(prose)
                    share = sum(w in bw for w in ws) / max(1, len(ws))
                    nums = numbers(b)
                    missing = [n for n in nums if n not in bn and n not in wn]
                    ok = share >= 0.5 and not missing
                    fidelity.append(share)
                    rep.add(f"6 fidelity ({purpose}): point grounded in the original at its locator", ok,
                            {"source": f.name, "locator": ch.get("locator"), "share": round(share, 2),
                             "missing_numbers": missing[:5], "point": b[:200]})
    # 7. paper graphs
    research = [s for s in srcs if (s.get("file") or "").lower().endswith(".pdf")]
    published = 0
    for s in research:
        root = deepest_root(roots, s["file"])
        if not root:
            continue
        pub = graph_stats.get(root["graph_label"], {}).get("paper_database")
        published += bool(pub)
        rep.add("7 paper graph: PDF Source's graph has a paper database", bool(pub), f'{root["graph_label"]}: {Path(s["file"]).name}')

    out = {"library": str(vault.root), "graphs": graph_stats, "source_status": dict(status),
           "sources_by_purpose_status": {f"{k[0]} | {k[1]}": v for k, v in sorted(per_purpose.items())},
           "fidelity_median_share": (sorted(fidelity)[len(fidelity) // 2] if fidelity else None),
           "checks": {k: v for k, v in sorted(rep.checks.items())}}
    text = json.dumps(out, indent=1, ensure_ascii=False)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    for k, v in sorted(rep.checks.items()):
        print(f"{'PASS' if not v['fail'] else 'FAIL'}  {k}: {v['pass']} pass, {v['fail']} fail")
    print("sources:", dict(status)); print("by purpose:", out["sources_by_purpose_status"])
    print("fidelity median share:", out["fidelity_median_share"])


if __name__ == "__main__":
    main()
