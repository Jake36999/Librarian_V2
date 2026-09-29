"""M0 spike (b): lexical vs model2vec vs fastembed on V1's own tests.

Run on your machine, against your V1 vault (HuggingFace is blocked where V2 is
being built, so no embedding model can be downloaded there):

    pip install model2vec fastembed numpy pyyaml
    python embeddings_spike.py --vault "C:/path/to/Resource Library" --out embeddings.md

It reads V1's `eval_questions.json` and `scenarios.json` from the vault's
`.utility/librarian/`, builds each retriever over the vault's notes, and prints
one table: hit@k, recall@k and MRR on the eval set, strong and any-answer hit@k
on the scenarios, plus build time and query latency. Each retriever is scored
alone and fused with the lexical one by Reciprocal Rank Fusion, which is how V2
will use it. Nothing in the vault is written.

The retrievers deliberately share nothing with V1's `consult`: V1's own score
is already known (`librarian eval`), and this spike asks which *vector* side
V2 should ship, not whether V1's tuning can be reproduced.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

SKIP_DIRS = {"PDF's", "PDFs", "node_modules", "internal docs", "05-Canvases"}
STOPWORDS = set("""a an and are as at be but by can do does for from has have how i if in
into is it its of on or our so that the their them then there these they this to use used
using want we what when where which while who why will with without would you your e g eg
already also any some such than more most other only just like need needs about over""".split())
TOKEN = re.compile(r"[a-z0-9][a-z0-9_\-]{1,}")
FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)
HEADING = re.compile(r"^## +(.+?)\s*$", re.M)
TEXT_FIELDS = ("title", "summary", "description", "aliases", "primary_topic", "category")


@dataclass
class Doc:
    name: str
    text: str
    sections: list[str] = field(default_factory=list)


def load_docs(vault: Path, max_chars: int) -> list[Doc]:
    docs = []
    for path in sorted(vault.rglob("*.md")):
        rel = path.relative_to(vault).parts
        if any(p.startswith(".") for p in rel) or SKIP_DIRS & set(rel[:-1]):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        fm, body = {}, raw
        m = FM.match(raw)
        if m:
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                fm = {}
            body = raw[m.end():]
        head = " ".join(str(fm.get(k, "")) for k in TEXT_FIELDS if fm.get(k)) \
            if isinstance(fm, dict) else ""
        text = f"{path.stem}. {head}\n{body}"[:max_chars]
        parts = HEADING.split(body)
        sections = [f"{path.stem}. {parts[0][:max_chars]}"]
        sections += [f"{path.stem}. {parts[i]}. {parts[i + 1][:max_chars]}"
                     for i in range(1, len(parts) - 1, 2)]
        docs.append(Doc(path.stem, text, [s for s in sections if len(s) > len(path.stem) + 5]))
    return docs


# ------------------------------------------------------------------ retrievers

class Lexical:
    name = "lexical (FTS5 BM25)"

    def __init__(self, docs: list[Doc]):
        self.docs = docs
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE VIRTUAL TABLE t USING fts5(name, body, tokenize='porter')")
        self.db.executemany("INSERT INTO t(rowid, name, body) VALUES (?, ?, ?)",
                            [(i, d.name, d.text) for i, d in enumerate(docs)])

    def search(self, query: str, k: int) -> list[str]:
        terms = [t for t in TOKEN.findall(query.lower()) if t not in STOPWORDS]
        if not terms:
            return []
        match = " OR ".join('"' + t.replace('"', "") + '"' for t in dict.fromkeys(terms))
        rows = self.db.execute("SELECT rowid FROM t WHERE t MATCH ? ORDER BY bm25(t, 5.0, 1.0) "
                               "LIMIT ?", (match, k)).fetchall()
        return [self.docs[r[0]].name for r in rows]


class Vector:
    """Cosine over note text, or max over a note's sections (`--granularity section`)."""

    def __init__(self, label: str, encode, docs: list[Doc], granularity: str):
        import numpy as np
        self.np, self.encode, self.docs = np, encode, docs
        self.name = f"{label} [{granularity}]"
        if granularity == "section":
            texts, self.owner = [], []
            for i, d in enumerate(docs):
                for s in d.sections or [d.text]:
                    texts.append(s)
                    self.owner.append(i)
        else:
            texts, self.owner = [d.text for d in docs], list(range(len(docs)))
        self.owner = np.array(self.owner)
        self.chunks = len(texts)
        self.matrix = self._norm(np.asarray(encode(texts), dtype="float32"))

    def _norm(self, m):
        return m / (self.np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)

    def search(self, query: str, k: int) -> list[str]:
        np = self.np
        q = self._norm(np.asarray(self.encode([query]), dtype="float32"))[0]
        sims = self.matrix @ q
        best = np.full(len(self.docs), -1.0, dtype="float32")
        np.maximum.at(best, self.owner, sims)
        return [self.docs[i].name for i in np.argsort(-best)[:k]]


class Fused:
    def __init__(self, a, b, rrf_k: int = 60, depth: int = 50):
        self.a, self.b, self.rrf_k, self.depth = a, b, rrf_k, depth
        self.name = f"RRF({a.name} + {b.name})"

    def search(self, query: str, k: int) -> list[str]:
        score: dict[str, float] = {}
        for r in (self.a, self.b):
            for rank, name in enumerate(r.search(query, self.depth), 1):
                score[name] = score.get(name, 0.0) + 1.0 / (self.rrf_k + rank)
        return sorted(score, key=score.get, reverse=True)[:k]


def model2vec_encoder(model_id: str):
    from model2vec import StaticModel
    model = StaticModel.from_pretrained(model_id)
    return lambda texts: model.encode(list(texts))


def fastembed_encoder(model_id: str):
    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=model_id)
    return lambda texts: list(model.embed(list(texts)))


# ------------------------------------------------------------------- scoring

def score(retriever, questions, scenarios, k: int) -> dict:
    hits = recall = rr = 0.0
    latencies = []
    for q in questions:
        t = time.perf_counter()
        got = retriever.search(q["question"], k)
        latencies.append(time.perf_counter() - t)
        expects = set(q["expects"])
        found = [n for n in got if n in expects]
        hits += bool(found)
        recall += len(found) / len(expects) if expects else 0
        rr += next((1 / (i + 1) for i, n in enumerate(got) if n in expects), 0)
    strong = anyhit = answerable = 0
    for s in scenarios:
        query = f"{s.get('component', '')}. {s['description']}"
        t = time.perf_counter()
        got = set(retriever.search(query, k))
        latencies.append(time.perf_counter() - t)
        wanted_strong = set(s["expects"].get("strong", []))
        wanted_any = wanted_strong | set(s["expects"].get("acceptable", []))
        if "expected to fail" in str(s.get("note", "")).lower():
            continue
        answerable += 1
        strong += bool(got & wanted_strong)
        anyhit += bool(got & wanted_any)
    n = max(len(questions), 1)
    latencies.sort()
    return {"hit": hits / n, "recall": recall / n, "mrr": rr / n,
            "sc_strong": strong / max(answerable, 1), "sc_any": anyhit / max(answerable, 1),
            "answerable": answerable,
            "p50_ms": 1000 * latencies[len(latencies) // 2] if latencies else 0,
            "p95_ms": 1000 * latencies[int(len(latencies) * 0.95) - 1] if latencies else 0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--vault", required=True)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--max-chars", type=int, default=4000)
    ap.add_argument("--granularity", choices=("note", "section", "both"), default="both")
    ap.add_argument("--model2vec", nargs="*", default=["minishlab/potion-base-8M",
                                                      "minishlab/potion-retrieval-32M"])
    ap.add_argument("--fastembed", nargs="*", default=["BAAI/bge-small-en-v1.5"])
    ap.add_argument("--out", help="also write the Markdown table here")
    args = ap.parse_args(argv)

    vault = Path(args.vault).expanduser()
    lib = vault / ".utility" / "librarian"
    questions = json.loads((lib / "eval_questions.json").read_text(encoding="utf-8"))["questions"]
    scenarios = json.loads((lib / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]
    docs = load_docs(vault, args.max_chars)
    names = {d.name for d in docs}
    missing = sorted({n for q in questions for n in q["expects"]} - names)
    print(f"{len(docs)} notes, {len(questions)} questions, {len(scenarios)} scenarios; "
          f"{len(missing)} expected answers not found as notes", file=sys.stderr)

    rows, notes_out = [], []
    t = time.perf_counter()
    lexical = Lexical(docs)
    rows.append((lexical.name, time.perf_counter() - t, len(docs),
                 score(lexical, questions, scenarios, args.k)))

    grains = ("note", "section") if args.granularity == "both" else (args.granularity,)
    encoders = [(f"model2vec {m}", model2vec_encoder, m) for m in args.model2vec]
    encoders += [(f"fastembed {m}", fastembed_encoder, m) for m in args.fastembed]
    for label, factory, model_id in encoders:
        try:
            t = time.perf_counter()
            encode = factory(model_id)
            load_s = time.perf_counter() - t
        except Exception as exc:                            # noqa: BLE001
            notes_out.append(f"- {label}: not run ({type(exc).__name__}: {exc})")
            continue
        notes_out.append(f"- {label}: loaded in {load_s:.1f}s")
        for grain in grains:
            t = time.perf_counter()
            vec = Vector(label, encode, docs, grain)
            build = time.perf_counter() - t
            rows.append((vec.name, build, vec.chunks, score(vec, questions, scenarios, args.k)))
            fused = Fused(lexical, vec)
            rows.append((fused.name, build, vec.chunks,
                         score(fused, questions, scenarios, args.k)))

    k = args.k
    answerable = rows[0][3]["answerable"]
    lines = ["# Embeddings Spike", "",
             f"{len(docs)} notes; {len(questions)} eval questions; {answerable} answerable "
             f"scenarios (those marked expected-to-fail are excluded); k = {k}.", "",
             f"| Retriever | hit@{k} | recall@{k} | MRR | scenario strong@{k} | "
             f"scenario any@{k} | build s | chunks | p50 ms | p95 ms |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for name, build, chunks, r in rows:
        lines.append(f"| {name} | {r['hit']:.2f} | {r['recall']:.2f} | {r['mrr']:.2f} | "
                     f"{r['sc_strong']:.2f} | {r['sc_any']:.2f} | {build:.1f} | {chunks} | "
                     f"{r['p50_ms']:.1f} | {r['p95_ms']:.1f} |")
    lines += ["", "## Notes", ""] + (notes_out or ["- no vector models requested"])
    if missing:
        lines += ["", "Expected answers with no note of that name (these questions cannot "
                      "score): " + ", ".join(missing)]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
