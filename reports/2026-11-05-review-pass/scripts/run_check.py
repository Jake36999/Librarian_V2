"""Check the memory review's literature claims, one reader call per source.

Inputs: claims.json and fetched.json from the scratchpad (see fetch_sources.py).
Steps: build packets under tmp/lit-check/, call scripts/delegate_deepinfra.py
(MiMo-V2.6-Pro, claude pool), parse each JSON verdict list, and check every quote
against the source text, strictly and leniently (letters and digits only).
Outputs: tmp/lit-check/results.json.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
LIT = Path(sys.argv[1])                       # the scratchpad lit folder
SOURCES, PACKETS = HERE / "sources", HERE / "packets"
LOCAL_DIRS = [REPO / "reports/2026-10-29-long-horizon-harness-research/data/paper_text",
              REPO / "reports/2026-10-30-runtime-tooling-literature/data/paper_text"]
MAX_SOURCE_CHARS = 380_000
MODEL = "XiaomiMiMo/MiMo-V2.6-Pro"


def slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text.split("://", 1)[-1])[:90]


def lenient(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.casefold())


def source_text(source: str, kind: str, fetched: dict) -> str | None:
    if kind == "web":
        info = fetched.get(source) or {}
        if info.get("status") != "ok":
            return None
        return (LIT / "text" / info["file"]).read_text(encoding="utf-8")
    for folder in LOCAL_DIRS:
        path = folder / source
        if path.is_file():
            return path.read_text(encoding="utf-8", errors="replace")
    return None


def build() -> list[dict]:
    claims = json.loads((LIT / "claims.json").read_text(encoding="utf-8"))
    fetched = json.loads((LIT / "fetched.json").read_text(encoding="utf-8"))
    groups: dict[str, dict] = {}
    for c in claims:
        g = groups.setdefault(c["source"], {"source": c["source"], "kind": c["kind"], "claims": []})
        key = " ".join(c["text"].split())
        for existing in g["claims"]:
            if existing["text"] == key:
                existing["where"].append(f"{c['doc']}:{c['line']}")
                break
        else:
            g["claims"].append({"id": f"c{len(g['claims']) + 1}", "text": key,
                                "where": [f"{c['doc']}:{c['line']}"]})
    SOURCES.mkdir(exist_ok=True)
    PACKETS.mkdir(exist_ok=True)
    jobs = []
    for n, g in enumerate(sorted(groups.values(), key=lambda g: g["source"]), 1):
        text = source_text(g["source"], g["kind"], fetched)
        if text is None:
            g["missing"] = True
            jobs.append(g)
            continue
        name = f"{n:02d}-{slug(g['source'])}"
        src = SOURCES / f"{name}.txt"
        src.write_text(text[:MAX_SOURCE_CHARS], encoding="utf-8")
        pkt = PACKETS / f"{name}.claims.md"
        pkt.write_text("CLAIMS about the source " + g["source"] + "\n\n" + "\n\n".join(
            f"[{c['id']}] {c['text']}" for c in g["claims"]), encoding="utf-8")
        g.update(name=name, src=str(src), pkt=str(pkt), truncated=len(text) > MAX_SOURCE_CHARS)
        jobs.append(g)
    return jobs


def call(g: dict) -> dict:
    if g.get("missing"):
        return {**g, "error": "source text unavailable"}
    out_dir = HERE / "responses"
    out_dir.mkdir(exist_ok=True)
    args = [sys.executable, str(REPO / "scripts/delegate_deepinfra.py"),
            "--task", f"lit-{g['name'][:40]}", "--model", MODEL,
            "--instruction-file", str(HERE / "instruction.md"),
            "--file", g["src"], "--file", g["pkt"],
            "--max-output-tokens", "12000", "--timeout", "600",
            "--pool", "claude", "--total-budget-usd", "8",
            "--task-id", "lit-check-2026-11-05", "--task-budget-usd", "1.5",
            "--role", "reader", "--agent", "claude", "--call-cap-usd", "0.25",
            "--output-dir", str(out_dir)]
    done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", cwd=REPO)
    line = (done.stdout.strip().splitlines() or [""])[-1]
    try:
        meta = json.loads(line)
    except json.JSONDecodeError:
        return {**g, "error": f"runner exit {done.returncode}: {done.stderr[-400:] or done.stdout[-400:]}"}
    reply = Path(meta["output"]).read_text(encoding="utf-8") if meta.get("output") else ""
    return {**g, "meta": {k: meta.get(k) for k in ("run_id", "charged_usd", "usage", "truncated")},
            "reply": reply}


def parse(reply: str) -> list[dict]:
    match = re.search(r"\[\s*\{.*\}\s*\]", reply, re.S)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return []


def check(results: list[dict]) -> None:
    for g in results:
        if "reply" not in g:
            continue
        source = Path(g["src"]).read_text(encoding="utf-8")
        flat, loose = " ".join(source.split()), lenient(source)
        verdicts = {v.get("id"): v for v in parse(g["reply"])}
        g["parsed"] = bool(verdicts)
        for c in g["claims"]:
            v = verdicts.get(c["id"], {})
            c["verdict"] = v.get("verdict", "no_answer")
            c["location"], c["note"] = v.get("location", ""), v.get("note", "")
            c["quotes"] = []
            for q in v.get("quotes") or []:
                q = str(q)
                strict = " ".join(q.split()) in flat
                ok = strict or (len(lenient(q)) >= 12 and lenient(q) in loose)
                c["quotes"].append({"quote": q, "strict": strict, "found": ok})


def main() -> None:
    jobs = build()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(call, jobs))
    check(results)
    (HERE / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False),
                                       encoding="utf-8")
    spent = sum(float((g.get("meta") or {}).get("charged_usd") or 0) for g in results)
    print(f"{len(results)} sources, charged ${spent:.3f}")
    for g in results:
        status = g.get("error") or ("parsed" if g.get("parsed") else "UNPARSED")
        print(f"{status[:60]:60} {g['source'][:80]}")


if __name__ == "__main__":
    main()
