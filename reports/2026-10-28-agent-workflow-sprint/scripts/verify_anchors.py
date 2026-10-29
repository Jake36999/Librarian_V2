"""WS4: check every model-produced anchor mechanically before a human reads the item.

Run with the repository venv (it imports resource_librarian.clerk for `quoted`/`locate`, which already
handle typographic quotes, Markdown emphasis and PDF line-break hyphens).
  D:\\Librarian_V2\\.venv\\Scripts\\python.exe verify_anchors.py [--only id-prefix,...]
A quote must be at least 8 normalised characters. An item is
  verified        quote found within the +-2 lines (or +-1 pages) of the cited anchor
  quote_elsewhere quote exists in the same source but not at the cited anchor (anchor wrong, evidence real)
  unverified      quote not found in the source at all
Outputs: tmp/sprint/out/verified/<call id>.jsonl, data/anchor_verification.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(REPO / "src"))
from resource_librarian.clerk import locate, quoted  # noqa: E402

TMP = REPO / "tmp" / "sprint"
OUT = TMP / "out" / "verified"
DATA = REPO / "reports" / "2026-10-28-agent-workflow-sprint" / "data"
LINE = re.compile(r"^L(\d{5})\| ?(.*)$")
ARRAY_KEYS = ("events", "claims", "papers", "method_cards", "facts", "capability_checks", "requirements",
              "methods", "costs", "negative_results", "limitations", "reproducibility")


def read_numbered(path: Path) -> dict[int, str]:
    out = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(raw)
        if m:
            out[int(m.group(1))] = m.group(2)
    return out


def split_pages(path: Path) -> dict[int, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    parts = re.split(r"\[\[PAGE (\d+)\]\]\n", text)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def repair_braces(s: str) -> str:
    """Close an object left open before the next array item (`, {`) or before `]`; strings are skipped."""
    out, stack, in_str, esc = [], [], False, False
    for i, ch in enumerate(s):
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch == "}":
            if stack and stack[-1] == "{":
                stack.pop()
        elif ch == "]":
            while stack and stack[-1] == "{":
                out.append("}")
                stack.pop()
            if stack and stack[-1] == "[":
                stack.pop()
        elif ch == ",":
            j = i + 1
            while j < len(s) and s[j].isspace():
                j += 1
            if j < len(s) and s[j] == "{" and stack and stack[-1] == "{":
                out.append("}")
                stack.pop()
        out.append(ch)
    return "".join(out)


def parse_output(text: str) -> tuple[dict | None, str]:
    t = re.sub(r"^```(?:json)?\s*", "", text.strip())
    t = re.sub(r"\s*```$", "", t)
    start = t.find("{")
    if start < 0:
        return None, "no_json"
    body = t[start:]
    try:
        return json.loads(body), "ok"
    except ValueError:
        pass
    # Revision 2: a complete object followed only by stray closing brackets (a model closed one level too many) is the whole answer.
    try:
        obj, end = json.JSONDecoder().raw_decode(body)
        if isinstance(obj, dict) and not body[end:].strip(" \n\r\t}]`"):
            return obj, "repaired"
    except ValueError:
        pass
    # Models sometimes leave one nested object unclosed per item; repair with a bracket stack.
    try:
        return json.loads(repair_braces(body)), "repaired"
    except ValueError:
        pass
    dec = json.JSONDecoder()
    found: dict = {}
    for key in ARRAY_KEYS:
        m = re.search(r'"' + key + r'"\s*:\s*\[', body)
        if not m:
            continue
        pos, items = m.end(), []
        while True:
            while pos < len(body) and body[pos] in " \n\r\t,":
                pos += 1
            if pos >= len(body) or body[pos] != "{":
                break
            try:
                obj, pos = dec.raw_decode(body, pos)
            except ValueError:
                break
            items.append(obj)
        found[key] = items
    m = re.search(r'"reading_record"\s*:\s*', body)  # lane L2: the record object comes first and is usually intact in a truncated answer
    if m:
        try:
            found["reading_record"], _ = dec.raw_decode(body, m.end())
        except ValueError:
            pass
    return (found or None), ("salvaged" if found else "unparseable")


def window_text(lines: dict[int, str], n: int, span: int) -> str:
    return "\n".join(lines.get(i, "") for i in range(n - span, n + span + 1))


def check_line(item: dict, lines: dict[int, str], line_key: str = "line", quote_key: str = "quote", span: int = 2) -> tuple[str, int | None]:
    quote = str(item.get(quote_key) or "")
    try:
        n = int(item.get(line_key))
    except (TypeError, ValueError):
        n = None
    if len(quote.strip()) < 8:
        return "unverified", None
    if n is not None and quoted(quote, window_text(lines, n, span)):
        return "verified", n
    full = "\n".join(lines[i] for i in sorted(lines))
    if quoted(quote, full):
        at = locate(quote, full)
        count = full[:at].count("\n") + 1 if at >= 0 else 0
        keys = sorted(lines)
        return "quote_elsewhere", keys[count - 1] if 0 < count <= len(keys) else None
    return "unverified", None


def check_page(item: dict, pages: dict[int, str], page_key: str = "page", quote_key: str = "quote") -> tuple[str, int | None]:
    quote = str(item.get(quote_key) or "")
    try:
        p = int(item.get(page_key))
    except (TypeError, ValueError):
        p = None
    if len(quote.strip()) < 8:
        return "unverified", None
    if p is not None and quoted(quote, "\n".join(pages.get(i, "") for i in (p - 1, p, p + 1))):
        return "verified", p
    for num, text in pages.items():
        if quoted(quote, text):
            return "quote_elsewhere", num
    return "unverified", None


def check_page_strict(item: dict, pages: dict[int, str], page_key: str = "page", quote_key: str = "quote") -> tuple[str, int | None]:
    """Exact-page check (revision 2): `verified` only when the quote is on the cited page (or starts there and runs onto the next);
    `adjacent_page` when it is on the page before or after; `quote_elsewhere` when it is elsewhere in the paper."""
    quote = str(item.get(quote_key) or "")
    try:
        p = int(item.get(page_key))
    except (TypeError, ValueError):
        p = None
    if len(quote.strip()) < 8:
        return "unverified", None
    if p is not None:
        here, after = pages.get(p, ""), pages.get(p + 1, "")
        if quoted(quote, here):
            return "verified", p
        if quoted(quote, here + "\n" + after) and not quoted(quote, after):
            return "verified", p
        if quoted(quote, pages.get(p - 1, "")) or quoted(quote, after):
            return "adjacent_page", p
    for num, text in pages.items():
        if quoted(quote, text):
            return "quote_elsewhere", num
    return "unverified", None


def numbered_section(path: Path, slug: str) -> dict[int, str]:
    """Lines of one `=== NOTE slug ===` section of a vault-note packet."""
    text = path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"=== NOTE " + re.escape(slug) + r" ===\n(.*?)(?=\n=== NOTE |\Z)", text, re.S)
    out = {}
    for raw in (m.group(1).splitlines() if m else []):
        mm = LINE.match(raw)
        if mm:
            out[int(mm.group(1))] = mm.group(2)
    return out


def verify_call(call: dict, result: dict) -> tuple[list[dict], dict]:
    text = Path(result["output"]).read_text(encoding="utf-8", errors="replace") if result.get("output") and Path(result["output"]).exists() else ""
    data, parse = parse_output(text)
    lane = call["lane"]
    rows: list[dict] = []
    if data is None:
        return rows, {"parse": parse}
    if lane in ("T", "G"):
        lines = read_numbered(REPO / call["files"][0])
        for e in data.get("events" if lane == "T" else "claims", []):
            status, at = check_line(e, lines)
            rows.append({**e, "verified": status, "anchor_line": at})
    elif lane in ("A", "R"):
        cache: dict[str, dict[int, str]] = {}
        for key in ("facts", "requirements", "capability_checks"):
            for e in data.get(key, []):
                target = e if key != "capability_checks" else (e.get("where") or {})
                if key == "capability_checks" and not target:
                    rows.append({**e, "kind": key, "verified": "no_claim" if e.get("status") == "absent" else "unverified", "anchor_line": None})
                    continue
                f = str(target.get("file") or "")
                if f not in cache:
                    p = REPO / f
                    cache[f] = read_numbered(p) if f and p.exists() else {}
                status, at = check_line(target, cache[f]) if cache[f] else ("unverified", None)
                rows.append({**e, "kind": key, "verified": status, "anchor_line": at})
    elif lane == "P1":
        for e in data.get("papers", []):
            ev = e.get("evidence") or {}
            if str(ev.get("category", "none")) == "none" or not ev.get("quote"):
                rows.append({**e, "verified": "no_claim", "anchor_line": None})
                continue
            pages = split_pages(TMP / "src" / "papers" / f"{e.get('slug')}.txt") if (TMP / "src" / "papers" / f"{e.get('slug')}.txt").exists() else {}
            status, at = check_page(ev, pages) if pages else ("unverified", None)
            rows.append({**e, "verified": status, "anchor_line": at})
    elif lane == "P1V":
        packet = REPO / call["files"][0]
        for e in data.get("papers", []):
            ev = e.get("evidence") or {}
            if str(ev.get("category", "none")) == "none" or not ev.get("quote"):
                rows.append({**e, "verified": "no_claim", "anchor_line": None})
                continue
            status, at = check_line({"line": ev.get("page"), "quote": ev.get("quote")}, numbered_section(packet, str(e.get("slug"))), span=3)
            rows.append({**e, "verified": status, "anchor_line": at})
    elif lane == "C":
        cache: dict[str, dict[int, str]] = {}
        def lines_of(f):
            if f not in cache:
                cache[f] = read_numbered(REPO / f) if f and (REPO / f).exists() else {}
            return cache[f]
        for e in data.get("findings", []):
            rep, evd = e.get("report") or {}, e.get("evidence")
            s1, a1 = check_line(rep, lines_of(str(rep.get("file") or ""))) if lines_of(str(rep.get("file") or "")) else ("unverified", None)
            if evd:
                s2, _ = check_line(evd, lines_of(str(evd.get("file") or ""))) if lines_of(str(evd.get("file") or "")) else ("unverified", None)
            else:
                s2 = "no_claim"
            status = "verified" if s1 == "verified" and s2 in ("verified", "no_claim") else ("quote_elsewhere" if "quote_elsewhere" in (s1, s2) else "unverified")
            rows.append({**e, "verified": status, "report_anchor": s1, "evidence_anchor": s2, "anchor_line": a1})
    elif lane == "P2":
        slug = str(data.get("paper") or call.get("slug") or "")
        pages = split_pages(REPO / call["files"][0])
        for e in data.get("method_cards", []):
            status, at = check_page(e, pages)
            rows.append({**e, "paper": slug, "verified": status, "anchor_line": at})
    elif lane == "L2":
        slug = call.get("slug") or str(data.get("paper") or "")
        pages = split_pages(REPO / call["files"][0])
        rec = data.get("reading_record") or {}
        items = [(k, rec[k]) for k in ("problem", "sample_and_unit", "source_availability") if isinstance(rec.get(k), dict)]
        for field, seq in (("comparators", rec.get("comparators")), ("methods", data.get("methods")), ("costs", data.get("costs")),
                           ("negative_results", data.get("negative_results")), ("limitations", data.get("limitations")), ("reproducibility", data.get("reproducibility"))):
            items += [(field, e) for e in (seq or []) if isinstance(e, dict)]
        for field, e in items:
            if not str(e.get("quote") or "").strip() or str(e.get("text") or "").strip().lower() == "not_reported":
                rows.append({**e, "field": field, "paper": slug, "verified": "no_claim", "anchor_line": None})
                continue
            status, at = check_page_strict(e, pages)
            rows.append({**e, "field": field, "paper": slug, "verified": status, "anchor_line": at})
        rows.append({"field": "record", "paper": slug, "verified": "no_claim", "anchor_line": None, "evidence_type": rec.get("evidence_type"),
                     "applicability_level": rec.get("applicability_level"), "applicability_reason": rec.get("applicability_reason")})
    return rows, {"parse": parse}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = [s for s in args.only.split(",") if s]
    calls = {c["id"]: c for c in json.loads((TMP / "lanes" / "calls.json").read_text(encoding="utf-8"))}
    for extra in ("calls_p2.json", "calls_critic.json", "calls_l2.json", "calls_critic_final.json"):
        p2 = TMP / "lanes" / extra
        if p2.exists():
            calls.update({c["id"]: c for c in json.loads(p2.read_text(encoding="utf-8"))})
    results = {}
    for line in (TMP / "lanes" / "results.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("status") == "completed":
            results[r["id"]] = r
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for cid, res in sorted(results.items()):
        if only and not any(cid.startswith(p) for p in only):
            continue
        call = calls.get(cid)
        if not call:
            continue
        rows, info = verify_call(call, res)
        (OUT / f"{cid}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + ("\n" if rows else ""), encoding="utf-8", newline="\n")
        c = Counter(r["verified"] for r in rows)
        claimed = sum(v for k, v in c.items() if k != "no_claim")
        summary.append({"call": cid, "lane": call["lane"], "model": call["model"], "parse": info["parse"], "items": len(rows), "claimed": claimed,
                        "verified": c["verified"], "adjacent_page": c["adjacent_page"], "quote_elsewhere": c["quote_elsewhere"], "unverified": c["unverified"],
                        "pass_rate": round(c["verified"] / claimed, 3) if claimed else "", "truncated": res.get("truncated"),
                        "finish_reason": res.get("finish_reason"), "input_tokens": res.get("input_tokens"), "output_tokens": res.get("output_tokens"),
                        "live_cost": res.get("live_cost"), "latency_s": res.get("latency_s")})
    table = DATA / "anchor_verification.csv"
    merged = {}
    if table.exists():
        merged = {r["call"]: r for r in csv.DictReader(table.open(encoding="utf-8"))}
    merged.update({r["call"]: r for r in summary})  # a partial run (--only) updates its own rows and keeps the rest
    fields = list(summary[0].keys()) if summary else (list(next(iter(merged.values())).keys()) if merged else [])
    with table.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows([merged[k] for k in sorted(merged)])
    for s in summary:
        print(f"{s['call']:36} {s['model'][-16:]:16} parse={s['parse']:9} items={s['items']:3} claimed={s['claimed']:3} ok={s['verified']:3} elsewhere={s['quote_elsewhere']:2} bad={s['unverified']:2} rate={s['pass_rate']} trunc={s['truncated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
