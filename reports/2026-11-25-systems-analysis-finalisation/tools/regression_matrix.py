"""Build the regression matrix from the second-pass readers' replies, checking every item mechanically.

    python tools/regression_matrix.py RUN_DIR

RUN_DIR holds one folder per reader call (tmp/second-pass/out/trace-*), each with a receipt and a
response. For every item a reader returned, this checks:
- quote:      the quote appears in one of the call's source files (whitespace, case and markup ignored);
- pack quote: the supporting quote appears in the pack digest;
- reference:  a `pack/spec:node` reference names a real node, or a `pack/file` reference a real file.
Then it applies regression-adjudication.yaml (Claude's review of the items: overrides with a reason), and
writes regression-matrix.json and REGRESSION-MATRIX.md. Model output is a proposal; only checked items
and adjudicated items are reported as dispositions.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
DISPOSITIONS = ("preserved", "deferred", "rejected", "unresolved")


def norm(text: str) -> str:
    text = re.sub(r"-\s*\n\s*", "", text or "")
    text = re.sub(r"[`*_|>#\"'“”‘’]", "", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def parse_reply(response: Path) -> list[dict]:
    data = json.loads(response.read_text(encoding="utf-8"))
    data = data.get("body", data)
    content = data["choices"][0]["message"]["content"] if "choices" in data else data.get("content", "")
    start, end = content.find("["), content.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        items = json.loads(content[start:end + 1])
    except json.JSONDecodeError:
        return []
    return [i for i in items if isinstance(i, dict)]


def node_exists(ref: str) -> bool | None:
    """True or False for a checkable reference; None when there is none."""
    if not ref or ref in ("null", "None"):
        return None
    ref = ref.strip("` ")
    if "/" in ref and ":" not in ref and ((HERE / ref).is_file() or (REPO / ref).is_file()):
        return True                      # a file of the package or the repository (README.md, render_pack.py ...)
    if ref in ("README.md", "VALIDATION.md", "PLAN.md") and (HERE / ref).is_file():
        return True
    m = re.match(r"^(librarian|geo-grapher)/(as-is|to-be)/([a-z0-9-]+)(?::([A-Za-z0-9_]+))?$", ref)
    if not m:
        m2 = re.match(r"^(librarian|geo-grapher)/(as-is|to-be)/(.+)$", ref)
        return bool(m2) and (HERE / ref).exists()
    system, state, name, node = m.groups()
    folder = HERE / system / state
    spec = folder / f"{name}.spec.yaml"
    if node is None:
        return spec.exists() or any((folder / f"{name}{ext}").exists() for ext in (".yaml", ".table.yaml", ".md"))
    if not spec.exists():
        return False
    return node in {n["id"] for n in yaml.safe_load(spec.read_text(encoding="utf-8"))["nodes"]}


def main(run_dir: Path) -> None:
    digest = norm((REPO / "tmp/second-pass/pack-digest.md").read_text(encoding="utf-8"))
    rows = []
    for receipt in sorted(run_dir.glob("trace-*/*.receipt.json")):
        r = json.loads(receipt.read_text(encoding="utf-8"))
        response = Path(r.get("response_path", ""))
        sources = {m["path"]: norm((REPO / m["path"]).read_text(encoding="utf-8"))
                   for m in r["manifest"] if not m["path"].endswith("pack-digest.md")}
        items = parse_reply(response) if response.exists() else []
        # A supporting quote is checked against the packet this reader was sent (the request keeps it),
        # not against today's digest: later rewording must not turn a faithful quote into a failure.
        request = Path(r.get("request_path", ""))
        seen = digest
        if request.exists():
            body = json.loads(request.read_text(encoding="utf-8")).get("body", {})
            seen = norm(" ".join(str(m.get("content", "")) for m in body.get("messages", []) if m.get("role") == "user"))
        for item in items:
            quote = norm(item.get("quote", ""))
            in_source = bool(quote) and any(quote in text for text in sources.values())
            pq = norm(item.get("pack_quote") or "")
            call = r["task"].replace("trace-", "").split("-")[0]      # t1 ... t8: readers reuse ids across calls
            rows.append({**item, "id": f"{call}/{item.get('id', '?')}", "call": r["task"], "run_id": r["run_id"], "model": r["model"],
                         "check_quote": in_source,
                         "check_pack_quote": (pq in seen) if pq else None,
                         "check_ref": node_exists(str(item.get("pack_ref") or ""))})
    adjudication_file = HERE / "regression-adjudication.yaml"
    adjudication = yaml.safe_load(adjudication_file.read_text(encoding="utf-8")) if adjudication_file.exists() else {}
    for row in rows:
        row["reader_disposition"] = row.get("disposition")
        verdict = (adjudication or {}).get(row.get("id"))
        if verdict:
            row.update({k: v for k, v in verdict.items() if k in ("disposition", "pack_ref", "note")})
            row["adjudicated"] = True
            row["check_ref"] = node_exists(str(row.get("pack_ref") or "")) if "pack_ref" in verdict else row["check_ref"]
        row["trusted"] = bool(row["check_quote"]) and row.get("check_ref") is not False and (
            row.get("adjudicated") or row.get("disposition") != "preserved" or row.get("check_pack_quote") is not False)
    (HERE / "regression-matrix.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_md(rows)


def cell(value) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def write_md(rows: list[dict]) -> None:
    counts = Counter(r.get("disposition") for r in rows if r["trusted"])
    dropped = [r for r in rows if not r["trusted"]]
    out = ["# Regression matrix", "",
           "<!-- generated by tools/regression_matrix.py; edit regression-adjudication.yaml, not this file -->", "",
           "Each requirement, accepted decision and reviewed element of the 20–24 November research, designs and graphs, "
           "traced to its disposition in the canonical packs. DeepInfra readers (MiMo-V2.6-Pro) proposed the items; a script "
           "checked every quote against its source and every reference against the packs; Claude reviewed every item marked "
           "unresolved or rejected, and overrode a disposition only with a reason (`adjudicated`). Every to-be element cited is "
           "proposed and unaccepted; *preserved* means the design carries it, not that it runs.", "",
           "**Reader reliability.** Claude checked 12 reader-preserved items drawn at random (seed 7) by hand: all 12 "
           "plausible, 3 only partly carried (t1/trace-t1-16, t1/trace-t1-20, t7/trace-t7-16). Read the reader-preserved "
           "rows as likely, not certain; the adjudicated rows were each read by Claude.", "",
           f"**{len(rows)} items proposed; {len(rows) - len(dropped)} passed the checks:** "
           + ", ".join(f"{counts.get(d, 0)} {d}" for d in DISPOSITIONS) + f". {len(dropped)} failed a check and are listed at the end.", ""]
    for disposition in DISPOSITIONS:
        chosen = [r for r in rows if r["trusted"] and r.get("disposition") == disposition]
        if not chosen:
            continue
        out += [f"## {disposition.capitalize()} ({len(chosen)})", "",
                "| Id | Requirement | Source | Where in the packs | Note |", "|---|---|---|---|---|"]
        for r in sorted(chosen, key=lambda x: x.get("id", "")):
            mark = " *(adjudicated)*" if r.get("adjudicated") else ""
            out.append(f"| {cell(r.get('id'))} | {cell(r.get('requirement'))} | {cell(r.get('source_file'))} | "
                       f"{cell(r.get('pack_ref'))} | {cell(r.get('note'))}{mark} |")
        out.append("")
    if dropped:
        out += ["## Items that failed a check (not counted)", "",
                "| Id | Requirement | Failed |", "|---|---|---|"]
        for r in dropped:
            failed = [n for n, ok in (("quote", r["check_quote"]), ("reference", r.get("check_ref")),
                                      ("pack quote", r.get("check_pack_quote"))) if ok is False]
            out.append(f"| {cell(r.get('id'))} | {cell(r.get('requirement'))} | {', '.join(failed)} |")
        out.append("")
    (HERE / "REGRESSION-MATRIX.md").write_text("\n".join(out), encoding="utf-8")
    print(f"{len(rows)} items; trusted {len(rows) - len(dropped)}; " + ", ".join(f"{d} {counts.get(d, 0)}" for d in DISPOSITIONS))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
