"""Document text: a Source note's file, extracted once and chunked under it.

A Source may name its document in `file:` (a path inside the vault, usually
under `Sources/<kind>/files/` or `Inbox/`). Its text is extracted with pypdf
(BSD; V1 used PyMuPDF, which is AGPL and cannot ship in this package), cached
in `.librarian/derived/text/` by the file's content hash, and indexed as
`document` chunks under the note. Ordinary searches leave document chunks out,
so one long PDF cannot outvote the notes; `search` with `intent: in_text`
reads them.

Extraction runs when a note names a file that has not been extracted, or
whose size or modification time changed. A scanned page with no text layer
is counted and reported (OCR is not in the default install), never silently
indexed as empty.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .index import Index

SUPPORTED = (".pdf", ".txt", ".md", ".docx", ".pptx", ".odt", ".odp", ".html", ".htm")

# Office files are zip archives of XML: read with the standard library, so a
# lab sheet or a lecture deck needs no extra install. A Word document is one
# "page" (it has no fixed pages); each slide of a deck is its own page, so a
# deep read cites "p. 4" for slide 4.
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_TEXT_NS = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"


def _office_pages(path: Path, suffix: str) -> list[str]:
    with zipfile.ZipFile(path) as archive:
        if suffix == ".docx":
            root = ET.fromstring(archive.read("word/document.xml"))
            paragraphs = ["".join(t.text or "" for t in p.iter(f"{_W}t")) for p in root.iter(f"{_W}p")]
            return ["\n".join(p for p in paragraphs if p.strip())]
        if suffix == ".pptx":
            slides = sorted((n for n in archive.namelist()
                             if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                            key=lambda n: int(re.search(r"\d+", n.rsplit("/", 1)[1]).group()))
            pages = []
            for name in slides:
                root = ET.fromstring(archive.read(name))
                lines = ["".join(t.text or "" for t in p.iter(f"{_A}t")) for p in root.iter(f"{_A}p")]
                pages.append("\n".join(line for line in lines if line.strip()))
            return pages
        root = ET.fromstring(archive.read("content.xml"))          # .odt / .odp
        return ["\n".join("".join(el.itertext()) for el in root.iter()
                          if el.tag in (f"{_TEXT_NS}p", f"{_TEXT_NS}h"))]


def _html_text(markup: str) -> str:
    markup = re.sub(r"(?is)<(script|style|nav|header|footer)\b.*?</\1>", " ", markup)
    markup = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr)>", "\n", markup)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


@dataclass
class Extraction:
    pages: list[str] = field(default_factory=list)
    empty_pages: int = 0
    error: str = ""
    cached: bool = False


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()[:32]


def extract(path: Path, cache_dir: Path) -> Extraction:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        return Extraction(error=f"{suffix} files are not supported ({', '.join(SUPPORTED)})")
    key = _file_hash(path)
    cached = cache_dir / f"{key}.json"
    if cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        return Extraction(data["pages"], data["empty_pages"], "", cached=True)
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError:
            return Extraction(error="pypdf is not installed: `pip install resource-librarian[pdf]`")
        try:
            pages = [(page.extract_text() or "") for page in PdfReader(str(path)).pages]
        except Exception as exc:                            # noqa: BLE001
            return Extraction(error=f"{type(exc).__name__}: {exc}"[:300])
    elif suffix in (".docx", ".pptx", ".odt", ".odp"):
        try:
            pages = _office_pages(path, suffix)
        except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
            return Extraction(error=f"not a readable {suffix} file: {exc}"[:300])
    elif suffix in (".html", ".htm"):
        pages = [_html_text(path.read_text(encoding="utf-8", errors="replace"))]
    else:
        pages = [path.read_text(encoding="utf-8", errors="replace")]
    empty = sum(1 for p in pages if len(p.strip()) < 20)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"file": path.name, "pages": pages, "empty_pages": empty},
                                 ensure_ascii=False), encoding="utf-8")
    return Extraction(pages, empty)


def sync_documents(index: Index) -> dict[str, Any]:
    """Index the text of every Source's `file` that is new or changed."""
    vault = index.vault
    cache_dir = vault.derived / "text"
    report: dict[str, Any] = {"indexed": [], "unchanged": 0, "problems": []}
    rows = index.conn.execute(
        "SELECT name, frontmatter FROM note WHERE shape = 'source' AND frontmatter LIKE ?",
        ('%"file"%',)).fetchall()
    for row in rows:
        rel = str(json.loads(row["frontmatter"]).get("file") or "").strip()
        if not rel:
            continue
        path = (vault.root / rel).resolve()
        if vault.root not in path.parents or not path.is_file():
            report["problems"].append({"note": row["name"], "file": rel,
                                       "problem": "not a file inside this vault"})
            continue
        stat = path.stat()
        stamp = f"{rel}|{stat.st_size}|{stat.st_mtime}"
        key = f"doc:{row['name']}"
        has_chunks = index.conn.execute(
            "SELECT 1 FROM chunk WHERE note = ? AND role = 'document' LIMIT 1",
            (row["name"],)).fetchone()
        if index._meta(key) == stamp and has_chunks:
            report["unchanged"] += 1
            continue
        result = extract(path, cache_dir)
        if result.error:
            report["problems"].append({"note": row["name"], "file": rel,
                                       "problem": result.error})
            continue
        chunks = index.add_document_text(row["name"], result.pages, commit=False)
        index._set_meta(key, stamp)
        entry = {"note": row["name"], "pages": len(result.pages), "chunks": chunks}
        if result.empty_pages:
            entry["pages_without_text"] = result.empty_pages
            entry["note_on_empty_pages"] = "scanned pages need OCR, which is not installed"
        report["indexed"].append(entry)
    index.conn.commit()
    return report
