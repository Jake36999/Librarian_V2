"""Label the lens gold set by hand (A2A-5): which passages teach which stance.

The set lives in `docs/lens-gold/gold.json`; `scripts/lens_eval.py` measures against it.
Labels are per chunk, as the deep read chunks the text, and each keeps a digest of that
chunk, so a changed chunker or text shows up as a stale label (see `lens_gold.py` in the
package). Nothing here calls a model or writes to a library.

    python scripts/lens_gold.py list
    python scripts/lens_gold.py add crisan --name "Evaluative lenses" --explanation "..." \\
        --file "06-Papers/PDF's/systems design and dev/Towards ... Analysis.md"
    python scripts/lens_gold.py add my-book --name "..." --explanation "..." \\
        --vault D:/Libraries/Software --note "Some Book"
    python scripts/lens_gold.py label crisan            # go through every chunk
    python scripts/lens_gold.py label crisan --grep "lens|framework" --unlabelled
    python scripts/lens_gold.py mark crisan --gold 3,4 --none 0,1,2
    python scripts/lens_gold.py propose --vault D:/Libraries/Software [--adopt]

In `label`, each chunk is shown with its current label; answer
  g  gold - this passage teaches the stance
  n  none - it teaches no stance
  s  skip (and clear any label)        m  show the whole chunk
  b  back one chunk                    q  quit (every answer is already saved)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".v2" / "src"))
from resource_librarian import lens_gold  # noqa: E402
from resource_librarian.vault import Vault  # noqa: E402

GOLD_PATH = ROOT / ".v2" / "docs" / "lens-gold" / "gold.json"
SHOW = 1500


def _ints(text: str) -> list[int]:
    return [int(x) for x in re.split(r"[,\s]+", text or "") if x.strip()]


def cmd_list(args, data) -> None:
    rows = lens_gold.status(data, ROOT)
    if not rows:
        print("The gold set is empty: add a source with `add`.")
    for r in rows:
        if "error" in r:
            print(f"{r['key']}: {r['stance']} - cannot read its text: {r['error']}")
            continue
        stale = f", STALE labels on chunks {r['stale']}" if r["stale"] else ""
        proposed = f", {r['proposed']} proposed (not yet confirmed by you)" if r["proposed"] else ""
        print(f"{r['key']}: {r['stance']} - {r['chunks']} chunks, judged by {r['rule']}: "
              f"{r['gold']} gold, {r['none']} none{stale}{proposed}")


def cmd_add(args, data) -> None:
    entry = lens_gold.add_source(data, args.key, args.name, args.explanation, file=args.file,
                                 vault=args.vault, note=args.note, phrases=args.phrases)
    n = len(lens_gold.chunks(entry, ROOT))
    lens_gold.save(GOLD_PATH, data)
    print(f"{args.key}: {n} chunks to label - `python scripts/lens_gold.py label {args.key}`")


def cmd_mark(args, data) -> None:
    entry = data["sources"][args.key]
    cl = lens_gold.chunks(entry, ROOT)
    for label, picked in (("gold", args.gold), ("none", args.none), ("skip", args.clear)):
        for i in _ints(picked):
            lens_gold.mark(data, args.key, i, label, cl)
    lens_gold.save(GOLD_PATH, data)
    cmd_list(args, {"sources": {args.key: entry}})


def cmd_label(args, data) -> None:
    entry = data["sources"][args.key]
    cl = lens_gold.chunks(entry, ROOT)
    rule = re.compile(args.grep, re.I) if args.grep else None
    order = [c for c in cl if c.index >= args.start and (not rule or rule.search(c.text))
             and not (args.unlabelled and str(c.index) in entry["labels"]
                      and entry["labels"][str(c.index)].get("by") == "owner")]
    print(f"{args.key}: {entry['stance']['name']}\n  {entry['stance']['explanation']}\n"
          f"{len(order)} of {len(cl)} chunks to go through.\n")
    pos = 0
    while 0 <= pos < len(order):
        c = order[pos]
        current = entry["labels"].get(str(c.index))
        fresh = current and current["digest"] == lens_gold.digest(c.text)
        state = (f"{current['label']} ({current['by']})" if fresh else "STALE") if current \
            else "unlabelled"
        print(f"--- chunk {c.index} ({c.locator}) - {state} - {pos + 1}/{len(order)}")
        print(c.text[:SHOW] + (f"\n[... {len(c.text) - SHOW} more characters: m]"
                               if len(c.text) > SHOW else ""))
        answer = input("g/n/s/m/b/q > ").strip().lower()[:1]
        if answer == "q":
            break
        if answer == "m":
            print(c.text)
            continue
        if answer == "b":
            pos = max(0, pos - 1)
            continue
        if answer in ("g", "n", "s"):
            lens_gold.mark(data, args.key, c.index,
                           {"g": "gold", "n": "none", "s": "skip"}[answer], cl)
            lens_gold.save(GOLD_PATH, data)                 # saved after every answer
            pos += 1
            continue
        print("answer g, n, s, m, b or q")
    cmd_list(args, {"sources": {args.key: entry}})


def cmd_propose(args, data) -> None:
    vault = Vault(Path(args.vault))
    proposals = lens_gold.propose(vault, data)
    if not proposals:
        print("No accepted lens to propose from (pack lenses and ones already in the set "
              "are left out).")
    for p in proposals:
        if "problem" in p:
            print(f"- {p['name']} ({p['source']}): not proposed - {p['problem']}")
            continue
        key = re.sub(r"[^a-z0-9]+", "-", p["name"].lower()).strip("-")[:40] or p["lens"]
        print(f"- {p['name']} ({p['source']}): gold chunks {p['chunks']} -> key {key}")
        if args.adopt:
            lens_gold.adopt(data, p, vault, key)
    if args.adopt:
        lens_gold.save(GOLD_PATH, data)
        print("Adopted as `accepted-lens` labels: confirm each with `label <key>`.")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    a = sub.add_parser("add")
    a.add_argument("key")
    a.add_argument("--name", required=True)
    a.add_argument("--explanation", required=True)
    a.add_argument("--file", default="")
    a.add_argument("--vault", default="")
    a.add_argument("--note", default="")
    a.add_argument("--phrases", default="")
    m = sub.add_parser("mark")
    m.add_argument("key")
    m.add_argument("--gold", default="")
    m.add_argument("--none", default="")
    m.add_argument("--clear", default="")
    lab = sub.add_parser("label")
    lab.add_argument("key")
    lab.add_argument("--grep", default="")
    lab.add_argument("--start", type=int, default=0)
    lab.add_argument("--unlabelled", action="store_true",
                     help="skip chunks you already labelled yourself")
    p = sub.add_parser("propose")
    p.add_argument("--vault", required=True)
    p.add_argument("--adopt", action="store_true")
    args = ap.parse_args()
    data = lens_gold.load(GOLD_PATH)
    {"list": cmd_list, "add": cmd_add, "mark": cmd_mark, "label": cmd_label,
     "propose": cmd_propose}[args.command](args, data)


if __name__ == "__main__":
    main()
