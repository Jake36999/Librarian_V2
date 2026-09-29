"""M0 spike (c): is pypdf's text good enough to search?

V1 extracted PDFs with PyMuPDF, which is AGPL and cannot ship in a package
other people download. V2 defaults to pypdf (BSD). This measures what that
costs on your own PDFs. Run on your machine:

    pip install pypdf pyyaml
    python pdf_spike.py --pdfs "C:/path/to/PDFs" --v1-text "C:/path/to/vault/06-Papers/PDF's" \\
        --limit 10 --out pdf.md

For each PDF: pages, seconds, characters per page, the share of pages with no
text (a scanned page needs OCR, which is not in the default install), the share
of tokens that look like words (ligature and encoding damage shows up here),
and, when V1 already holds an extraction with the same file stem, the word
overlap with it. Nothing is written except the report.
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

WORD = re.compile(r"^[A-Za-z][a-z]{1,19}$|^[A-Z]{2,10}$|^\d+([.,]\d+)?$")
TOKEN = re.compile(r"\S+")


def extract(path: Path) -> tuple[list[str], float, str]:
    from pypdf import PdfReader
    t = time.perf_counter()
    try:
        reader = PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return pages, time.perf_counter() - t, ""
    except Exception as exc:                                # noqa: BLE001
        return [], time.perf_counter() - t, f"{type(exc).__name__}: {exc}"[:120]


def wordlike(text: str) -> float:
    tokens = [t.strip(".,;:()[]\"'!?") for t in TOKEN.findall(text)]
    tokens = [t for t in tokens if t]
    return sum(bool(WORD.match(t)) for t in tokens) / len(tokens) if tokens else 0.0


def overlap(a: str, b: str) -> float:
    wa = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", a)}
    wb = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", b)}
    return len(wa & wb) / len(wa | wb) if wa | wb else 0.0


def v1_text(folder: Path | None, stem: str) -> str | None:
    if not folder:
        return None
    for candidate in (folder / f"{stem}.md", folder / f"{stem}.txt"):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8", errors="replace")
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pdfs", required=True, help="a folder of PDFs")
    ap.add_argument("--v1-text", help="V1's extraction folder, to compare against")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    folder = Path(args.pdfs).expanduser()
    v1 = Path(args.v1_text).expanduser() if args.v1_text else None
    pdfs = sorted(folder.rglob("*.pdf"), key=lambda p: p.stat().st_size)
    if args.limit and len(pdfs) > args.limit:
        step = len(pdfs) / args.limit          # spread across sizes, not the ten smallest
        pdfs = [pdfs[int(i * step)] for i in range(args.limit)]

    lines = ["# PDF Text Spike", "", f"{len(pdfs)} PDFs from `{folder}`, extracted with pypdf.", "",
             "| PDF | pages | s | chars/page | empty pages | word-like | overlap with V1 | error |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    totals = {"pages": 0, "seconds": 0.0, "empty": 0}
    for path in pdfs:
        pages, seconds, error = extract(path)
        text = "\n".join(pages)
        empty = sum(1 for p in pages if len(p.strip()) < 20)
        old = v1_text(v1, path.stem)
        totals["pages"] += len(pages)
        totals["seconds"] += seconds
        totals["empty"] += empty
        lines.append(
            f"| {path.name[:60]} | {len(pages)} | {seconds:.2f} | "
            f"{len(text) // max(len(pages), 1)} | {empty} | {wordlike(text):.2f} | "
            f"{overlap(text, old):.2f} |" if old is not None else
            f"| {path.name[:60]} | {len(pages)} | {seconds:.2f} | "
            f"{len(text) // max(len(pages), 1)} | {empty} | {wordlike(text):.2f} | — |")
        lines[-1] += f" {error} |"
    lines += ["", f"Total: {totals['pages']} pages in {totals['seconds']:.1f}s "
                  f"({totals['seconds'] / max(totals['pages'], 1) * 1000:.0f} ms/page); "
                  f"{totals['empty']} pages with no text layer.", "",
              "Reading it: word-like below about 0.75 means damaged text (ligatures, "
              "encodings, maths); empty pages mean a scan, which needs OCR; overlap "
              "below about 0.6 with V1 means pypdf and PyMuPDF disagree enough to check "
              "by eye."]
    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).write_text(report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
