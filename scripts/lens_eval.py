"""E10, run for real: how the lens chain behaves on actual sources, by model.

Not a pytest (it calls live models and costs a little); run it by hand:

    python scripts/lens_eval.py --models local:qwen/qwen3-4b-2507,deepinfra:openai/gpt-oss-20b
    python scripts/lens_eval.py --stages challenge --models deepinfra:deepseek-ai/DeepSeek-V4-Flash

What it measures (review 2026-09-27, plan P1-L1/L5):

- **perspective recall** on the three gold-set sources whose hand-built lens a
  single passage can teach (Crisan & Hoque; LLift; Eugene). A chunk is a *gold
  chunk* if it contains the phrases that state the gold stance (`GOLD`);
  recall is gold chunks flagged `has_perspective`, precision-proxy is flagged
  chunks that are gold chunks. Error direction, stated rather than hidden:
  the phrase rule under-counts gold chunks (a stance can be taught without
  its keywords), and the precision proxy *under*-states precision (a flagged
  non-gold chunk may hold a genuine stance the gold set never named) - so
  read recall as an upper bound's denominator and precision as a floor.
  Prompt variants: `shipped` (whatever `clerk.lens_perspective` asks now),
  `v2` (its wording before 2026-09-28), and `scan`, a reconstruction of V1's permissive LENS_SCAN question (the one
  that originally found "evaluative lenses").
- **challenge discrimination** (E11): the true gold stance, a decoy (another
  source's stance) and a topic restatement, each challenged N times on a gold
  chunk, reported as verdict counts. A useful challenge says `holds` for the
  first and `fails` for the other two.
- **stability**: the same stance drafted from a passage and its paraphrase,
  judged the way the deep read reconciles drafts (`deep_read._same_stance`:
  similar names, or what each catches and explains overlapping), within
  repeats and across the two; the names are listed too.
- **invalid outputs**, per stage: answers still off-shape after repair, errors,
  and answers that needed a repair to pass.

A full run on a local model takes over an hour (about 50 s per call for a 4B):
start it deliberately, in the background - the librarian itself keeps local-model
work to calls under ten minutes (`deep_read.LOCAL_MAX_CHUNKS`).

Nothing here writes to a vault. Keys: DEEPINFRA_API_KEY from the environment,
else `.utility/.env` (read in-process, never echoed).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".v2" / "src"))
from resource_librarian import clerk, deep_read  # noqa: E402

GOLD_DIR = ROOT / "06-Papers" / "PDF's" / "systems design and dev"
GOLD = {
    "crisan": {
        "file": "Towards a Holistic Evaluation of LLM Generated Code for Exploratory Visual Analysis.md",
        "phrases": r"evaluative lens",
        "stance": ("Evaluative lenses",
                   "judge generated analysis code separately on functional, semantic, contextual "
                   "and preferential grounds, since passing one says nothing about the others")},
    "llift": {
        "file": "hitchhikers guide to programme analysis.md",
        "phrases": r"progressive prompt|self-validat|task decomposition",
        "stance": ("Decompose, disclose progressively, self-validate",
                   "split an LLM analysis into staged sub-tasks, give the model context only as "
                   "it needs it, and have it check its own answer against stated criteria")},
    "eugene": {
        "file": "A User-Guided Approach to Program Analysis.md",
        "phrases": r"soft (rule|constraint)|hard (rule|constraint)",
        "stance": ("Hard rules plus tunable soft rules",
                   "treat an analysis as non-negotiable hard constraints plus weighted soft "
                   "preferences whose weights are tuned from a user's feedback")},
}

SCAN_QUESTION = (
    "Does the passage below name, describe or demonstrate a reusable reasoning lens - a way of "
    "looking at, evaluating or approaching a problem that someone could apply again to other "
    "material (for example a named evaluation framework, a principle for structuring work, or "
    "a method for checking results)?\n\n"
    "If yes, set `has_perspective` true and give `name` (the lens itself, not the paper's "
    "topic), `explanation` (what the lens makes you do differently) and `source_quote` (the "
    "exact sentence(s) below it comes from, word for word - this is checked). If not, set "
    "`has_perspective` false and leave the rest empty.")

V2_QUESTION = (
    "A doctor and an engineer examining the same broken machine reason about it "
        "differently - not because they know different facts, but because each has adopted a "
        "stance that makes certain things salient and others invisible. Read the passage "
        "below with that in mind.\n\n"
        "Does it require or teach a specific reasoning stance like that - a way of approaching "
        "a problem that a reader could adopt again elsewhere? Most passages do not: a plain "
        "fact, a definition, an API reference entry, or a chapter's own introduction ('In "
        "this chapter we will discuss...') is not a stance, even when it mentions a named "
        "concept.\n\n"
        "If yes, set `has_perspective` true and give:\n"
        "- `name`: short, naming the stance itself (not the topic it's applied to)\n"
        "- `explanation`: what makes THIS framing necessary for THIS material specifically - "
        "not a generic restatement of the subject\n"
        "- `source_quote`: the exact sentence(s) below that this stance is drawn from, word "
        "for word. This is checked; an unverifiable quote discards the whole answer.\n\n"
        "If nothing here requires a specific stance, set `has_perspective` false and leave "
        "the rest empty - that is the normal, correct answer for most passages.")

V3_QUESTION = (
    "Does the passage below teach, name or demonstrate a reusable way of reasoning - a way of "
    "looking at, evaluating or approaching a problem that someone could apply again to other "
    "material (for example an evaluation framework, a principle for structuring work, or a method "
    "for checking results)? A plain fact, a definition, a citation list or a chapter's own "
    "introduction is not one, even when it mentions a named concept.\n\n"
    "If yes, set `has_perspective` true and give:\n"
    "- `name`: short, naming the way of reasoning itself - not the paper, the tool or the topic "
    "it is applied to\n"
    "- `explanation`: what it makes someone do differently\n"
    "- `source_quote`: the exact sentence(s) below it comes from, word for word. This is "
    "checked.\n\n"
    "If not, set `has_perspective` false and leave the rest empty.")

POSITIVE = ("A surgeon and a claims adjuster examining the same accident scene reach different "
            "conclusions - not from different facts, but because each has adopted a stance that "
            "makes certain injuries salient and others invisible. Read every injury by asking "
            "which structure failed first, not which one is most visible.")
PARAPHRASE = ("Two professionals - say a trauma doctor and an insurance assessor - can look at "
              "one crash and disagree, although they see the same evidence, because each "
              "approaches it from a position that highlights some injuries and hides others. When "
              "reading the damage, start from whichever structure gave way earliest rather than "
              "whichever is most eye-catching.")


def _key() -> str:
    if os.environ.get("DEEPINFRA_API_KEY"):
        return os.environ["DEEPINFRA_API_KEY"]
    for line in (ROOT / ".utility" / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DEEPINFRA_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').split()[0]
    raise SystemExit("no DEEPINFRA_API_KEY")


def endpoint(spec: str) -> clerk.Endpoint:
    where, model = spec.split(":", 1)
    if where == "local":
        return clerk.OpenAICompatible("http://127.0.0.1:1234/v1", model, timeout=600,
                                      min_tokens=6000 if "qwen3-8b" in model else 0)
    os.environ.setdefault("DEEPINFRA_API_KEY", _key())
    return clerk.OpenAICompatible("https://api.deepinfra.com/v1/openai", model,
                                  key_env="DEEPINFRA_API_KEY", concurrency=4, timeout=300,
                                  min_tokens=1800)


def run(task: clerk.Task, ep: clerk.Endpoint) -> dict:
    try:
        r = clerk.run_one(task, ep)
    except clerk.ClerkUnavailable as exc:
        return {"status": "unavailable", "value": {}, "dropped": [], "problems": str(exc),
                "attempts": 0}
    return {"status": r.status, "value": r.value, "dropped": r.dropped, "problems": r.problems,
            "attempts": r.attempts}


def outcome(r: dict) -> dict:
    """What every stage row carries for the invalid-output count (C3)."""
    return {"status": r["status"], "repaired": r.get("attempts", 0) > 1}


def chunks() -> list[tuple[str, int, str, bool]]:
    out = []
    for key, gold in GOLD.items():
        text = (GOLD_DIR / gold["file"]).read_text(encoding="utf-8")
        for c in deep_read.chunk([(0, text)]):
            out.append((key, c.index, c.text, bool(re.search(gold["phrases"], c.text, re.I))))
    return out


VARIANTS = ("shipped", "v2", "scan")


def perspective_stage(ep: clerk.Endpoint, workers: int) -> list[dict]:
    rows = []
    jobs = [(src, i, text, gold, variant) for src, i, text, gold in chunks()
            for variant in VARIANTS]

    def one(job):
        src, i, text, gold, variant = job
        question = {"v2": V2_QUESTION, "scan": SCAN_QUESTION, "v3": V3_QUESTION}.get(variant)
        task = clerk.lens_perspective(text) if variant == "shipped" else \
            clerk.Task(clerk.KINDS["lens_perspective"], text, question)
        r = run(task, ep)
        v = r["value"]
        return {"source": src, "chunk": i, "gold": gold, "variant": variant,
                **outcome(r), "flagged": bool(v.get("has_perspective")),
                "name": v.get("name", ""), "explanation": v.get("explanation", ""),
                "quote_dropped": bool(r["dropped"]), "problems": r["problems"][:200]}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(one, jobs))
    return rows


def challenge_stage(ep: clerk.Endpoint, n: int, workers: int) -> list[dict]:
    keys = list(GOLD)
    jobs = []
    for i, key in enumerate(keys):
        gold_chunk = next(text for src, _, text, gold in chunks() if src == key and gold)
        window = gold_chunk
        m = re.search(GOLD[key]["phrases"], gold_chunk, re.I)
        if m:
            window = gold_chunk[max(0, m.start() - 1500): m.end() + 1500]
        decoy = GOLD[keys[(i + 1) % len(keys)]]["stance"]
        topic = (f"{key} paper summary", "a general description of what this paper is about")
        for label, (name, expl) in (("true", GOLD[key]["stance"]), ("decoy", decoy),
                                     ("topic", topic)):
            jobs += [(key, label, window, name, expl)] * n

    def one(job):
        key, label, window, name, expl = job
        r = run(clerk.lens_challenge(window, name, expl), ep)
        return {"source": key, "case": label, **outcome(r),
                "verdict": r["value"].get("verdict", ""),
                "counter_is_source_phrase": bool(r["value"].get("counter_quote")),
                "reason": str(r["value"].get("reason", ""))[:200]}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, jobs))


def blind_stage(ep: clerk.Endpoint, n: int, workers: int) -> list[dict]:
    """The rebuilt E11, as deep_read runs it (`deep_read._candidates` +
    `clerk.discrimination`): proposing the true gold stance should come back
    `holds`; proposing another source's stance on the same passage, `fails`."""
    keys = list(GOLD)
    jobs = []
    for i, key in enumerate(keys):
        gold_chunk = next(text for src, _, text, gold in chunks() if src == key and gold)
        m = re.search(GOLD[key]["phrases"], gold_chunk, re.I)
        window = gold_chunk[max(0, m.start() - 1500): m.end() + 1500] if m else gold_chunk
        wrong = GOLD[keys[(i + 1) % len(keys)]]["stance"]
        for label, (name, expl) in (("true", GOLD[key]["stance"]), ("wrong", wrong)):
            for k in range(n):
                jobs.append((key, label, window, name, expl, k))

    def one(job):
        key, label, window, name, expl, k = job
        s = {"name": name, "explanation": expl}
        candidates, proposed = deep_read._candidates(deep_read.Chunk(k, window), s, {k: s}, [],
                                                     [])
        r = run(clerk.lens_discriminate(window, candidates), ep)
        verdict = clerk.discrimination(r["value"], proposed, len(candidates))[0] \
            if r["status"] == "ok" else r["status"]
        return {"source": key, "case": label, "verdict": verdict, **outcome(r)}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, jobs))


def stability_stage(ep: clerk.Endpoint, n: int) -> list[dict]:
    out = []
    for label, text in (("original", POSITIVE), ("paraphrase", PARAPHRASE)):
        for _ in range(n):
            r = run(clerk.lens_perspective(text), ep)
            v = r["value"]
            out.append({"variant": label, "flagged": bool(v.get("has_perspective")),
                        "name": v.get("name", ""), "explanation": v.get("explanation", ""),
                        "catches": v.get("catches", ""), **outcome(r)})
    return out


def stability_pairs(rows: list[dict]) -> dict[str, tuple[int, int]]:
    """How often two flagged drafts are the same stance, judged the way the
    deep read reconciles them (`deep_read._same_stance`), not by exact name:
    within repeats of the passage, within repeats of its paraphrase, and
    across the two. Each is (same, pairs)."""
    flagged = [r for r in rows if r["flagged"]]
    groups = {label: [r for r in flagged if r["variant"] == label]
              for label in ("original", "paraphrase")}
    out = {}
    for label, rs in groups.items():
        pairs = [(a, b) for i, a in enumerate(rs) for b in rs[i + 1:]]
        out[label] = (sum(deep_read._same_stance(a, b) for a, b in pairs), len(pairs))
    cross = [(a, b) for a in groups["original"] for b in groups["paraphrase"]]
    out["across"] = (sum(deep_read._same_stance(a, b) for a, b in cross), len(cross))
    return out


def invalid_counts(result: dict) -> list[str]:
    """Per stage: calls, outputs still invalid after repair (`refused`), errors
    or an unavailable endpoint, and outputs that needed a repair to pass."""
    lines = ["| stage | calls | invalid | error / unavailable | repaired |",
             "| --- | --- | --- | --- | --- |"]
    for stage in ("perspective", "challenge", "blind", "stability"):
        rows = result.get(stage) or []
        if rows:
            s = Counter(r.get("status", "") for r in rows)
            lines.append(f"| {stage} | {len(rows)} | {s['refused']} | "
                         f"{s['error'] + s['unavailable']} | "
                         f"{sum(bool(r.get('repaired')) for r in rows)} |")
    return lines + [""] if len(lines) > 2 else []


def summarise(model: str, result: dict) -> str:
    lines = [f"### {model}", ""]
    rows = result.get("perspective") or []
    if rows:
        lines += ["| variant | gold chunks flagged (recall) | flagged that are gold (precision floor) "
                  "| flagged total | quote dropped | errors |", "| --- | --- | --- | --- | --- | --- |"]
        for variant in sorted({r["variant"] for r in rows}):
            vr = [r for r in rows if r["variant"] == variant]
            gold = [r for r in vr if r["gold"]]
            flagged = [r for r in vr if r["flagged"]]
            lines.append(
                f"| {variant} | {sum(r['flagged'] for r in gold)}/{len(gold)} | "
                f"{sum(r['gold'] for r in flagged)}/{len(flagged)} | {len(flagged)}/{len(vr)} | "
                f"{sum(r['quote_dropped'] for r in vr)} | "
                f"{sum(r['status'] not in ('ok', 'not_confident') for r in vr)} |")
        lines.append("")
        # Per source: did any flagged stance *recover the gold stance*? Judged by
        # name with deep_read's own stemmed matcher - automatic, so it can both
        # miss a recovery under a very different name (under-counts) and credit
        # a name that shares a key word (over-counts); the names are listed
        # below for a person to check.
        for variant in sorted({r["variant"] for r in rows}):
            found = sorted({r["source"] for r in rows if r["variant"] == variant and r["flagged"]
                            and deep_read._similar_names(r["name"], GOLD[r["source"]]["stance"][0])})
            lines.append(f"- `{variant}` recovered the gold stance in {len(found)}/{len(GOLD)} "
                         f"sources: {', '.join(found) or 'none'}")
        for variant in sorted({r["variant"] for r in rows}):
            names = [f"{r['source']}#{r['chunk']}{'*' if r['gold'] else ''}: {r['name']}"
                     for r in rows if r["variant"] == variant and r["flagged"]]
            lines.append(f"- `{variant}` flagged: " + ("; ".join(names) or "nothing"))
        lines.append("")
    ch = result.get("challenge") or []
    if ch:
        lines += ["| challenge case | holds | weak | fails | other |", "| --- | --- | --- | --- | --- |"]
        for case in ("true", "decoy", "topic"):
            c = Counter(r["verdict"] or r["status"] for r in ch if r["case"] == case)
            lines.append(f"| {case} | {c['holds']} | {c['weak']} | {c['fails']} | "
                         f"{sum(v for k, v in c.items() if k not in ('holds', 'weak', 'fails'))} |")
        lines.append("")
    bl = result.get("blind") or []
    if bl:
        lines += ["| blind challenge, proposed | holds | undiscriminating | fails | other |",
                  "| --- | --- | --- | --- | --- |"]
        for case in ("true", "wrong"):
            c = Counter(r["verdict"] for r in bl if r["case"] == case)
            lines.append(f"| {case} stance | {c['holds']} | {c['undiscriminating']} | {c['fails']} | "
                         f"{sum(v for k, v in c.items() if k not in ('holds', 'undiscriminating', 'fails'))} |")
        lines.append("")
    st = result.get("stability") or []
    if st:
        for label in ("original", "paraphrase"):
            names = Counter(r["name"] for r in st if r["variant"] == label)
            lines.append(f"- stability, {label}: " + ", ".join(f"{k!r} x{v}" for k, v in names.items()))
        lines.append("- same stance (`_same_stance`), pairs: " + ", ".join(
            f"{label} {same}/{n}" for label, (same, n) in stability_pairs(st).items()))
        lines.append("")
    lines += invalid_counts(result)
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True, help="comma list of local:<id> / deepinfra:<id>")
    ap.add_argument("--stages", default="perspective,challenge,blind,stability")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--out", default="lens_eval_results")
    args = ap.parse_args()
    stages = set(args.stages.split(","))
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = [f"# Lens chain evaluation - {time.strftime('%Y-%m-%d %H:%M')}", ""]
    for spec in args.models.split(","):
        ep = endpoint(spec)
        workers = 1 if spec.startswith("local:") else 6
        t0 = time.time()
        result: dict = {"model": spec}
        if "perspective" in stages:
            result["perspective"] = perspective_stage(ep, workers)
        if "challenge" in stages:
            result["challenge"] = challenge_stage(ep, args.n, workers)
        if "blind" in stages:
            result["blind"] = blind_stage(ep, args.n, workers)
        if "stability" in stages:
            result["stability"] = stability_stage(ep, args.n)
        result["seconds"] = round(time.time() - t0)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", spec)
        (out_dir / f"{safe}.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
        report.append(summarise(spec, result))
        print(summarise(spec, result), flush=True)
    (out_dir / "report.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
