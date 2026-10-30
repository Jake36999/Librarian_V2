"""Document identity and explainable duplicates (DEPLOY-04).

Each indexed document has a stable id in the index's `document` table. Four
layers decide when two paths are one document, or two documents look alike:

| Layer | Key | Used for |
| --- | --- | --- |
| 1. canonical path / file identity | the path; the file's device and file id | a move or rename keeps the id: a same-volume rename (Obsidian's) keeps the file id |
| 2. byte hash | SHA-256 of the exact bytes | a move that rewrote the file (another volume, a copy then delete) keeps the id when exactly one vanished and one new document share it; exact duplicates |
| 3. normalised text hash | the text after line endings, Unicode form and whitespace are normalised | duplicates that differ only in formatting |
| 4. logical external identity | the canonical URL, repository key or DOI a note declares | different documents about the same outside thing |

A refresh reconciles identities after it has seen the whole tree: a
document that vanished from one path and appeared at another keeps its id
only on an unambiguous layer-1 or layer-2 match. Otherwise the new path is a
new document. Duplicates are reported with the layer that matched and why.
Nothing is ever merged, moved or deleted.
"""
from __future__ import annotations

import hashlib
import secrets
import unicodedata
from typing import Any
from urllib.parse import urlsplit

from .vault import now_iso

TABLE = """
CREATE TABLE IF NOT EXISTS document (
  doc_id      TEXT PRIMARY KEY,
  path        TEXT NOT NULL UNIQUE,
  file_key    TEXT NOT NULL,
  byte_hash   TEXT NOT NULL,
  text_hash   TEXT NOT NULL,
  external    TEXT NOT NULL,
  first_seen  TEXT NOT NULL,
  moved_from  TEXT NOT NULL DEFAULT '',
  moved_by    TEXT NOT NULL DEFAULT '',
  provisional INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_document_file ON document(file_key);
CREATE INDEX IF NOT EXISTS idx_document_bytes ON document(byte_hash);
"""


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:24]


def normalised_text(text: str) -> str:
    """The text with its formatting taken out: a byte-order mark, line endings,
    Unicode composition, runs of spaces and tabs, trailing space, blank lines."""
    text = unicodedata.normalize("NFC", text.lstrip("﻿"))
    lines = (" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n")
             .split("\n"))
    return "\n".join(line for line in lines if line)


def _url(value: str) -> str:
    parts = urlsplit(value.strip())
    if not parts.scheme or not parts.netloc:
        return ""
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/").removesuffix(".git")
    return f"{host}{path}" + (f"?{parts.query}" if parts.query else "")


def external_identity(frontmatter: dict[str, Any]) -> str:
    """The outside thing a note says it is about, normalised; empty if none."""
    if frontmatter.get("repo_key"):
        return f"repository:{str(frontmatter['repo_key']).strip().lower()}"
    if str(frontmatter.get("identifier_kind", "")).lower() == "doi" and \
            frontmatter.get("identifier"):
        return f"doi:{str(frontmatter['identifier']).strip().lower()}"
    if frontmatter.get("doi"):
        return f"doi:{str(frontmatter['doi']).strip().lower()}"
    for key in ("canonical_url", "url", "source_url"):
        value = frontmatter.get(key)
        if isinstance(value, str) and _url(value):
            return f"url:{_url(value)}"
    return ""


def remember(conn: Any, rel: str, data: bytes, text: str, frontmatter: dict[str, Any],
             device: int, inode: int) -> None:
    """Record what one path holds now. A path seen for the first time gets a
    provisional id, settled when the refresh reconciles."""
    file_key = f"{device}:{inode}" if inode else ""
    row = (file_key, _hash(data), _hash(normalised_text(text).encode("utf-8")),
           external_identity(frontmatter))
    updated = conn.execute(
        "UPDATE document SET file_key = ?, byte_hash = ?, text_hash = ?, external = ? "
        "WHERE path = ?", (*row, rel)).rowcount
    if not updated:
        conn.execute(
            "INSERT INTO document(doc_id, path, file_key, byte_hash, text_hash, external, "
            "first_seen, provisional) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            (f"doc-{secrets.token_hex(8)}", rel, *row, now_iso()))


def reconcile(conn: Any) -> list[dict[str, str]]:
    """Carry ids across moves, drop vanished documents, settle new ones.
    Returns the moves found."""
    live = {r["path"] for r in conn.execute("SELECT path FROM note")}
    rows = [dict(r) for r in conn.execute("SELECT * FROM document")]
    orphans = [r for r in rows if r["path"] not in live]
    fresh = [r for r in rows if r["provisional"] and r["path"] in live]
    moves = []
    for layer, key in (("file identity", "file_key"), ("byte hash", "byte_hash")):
        for new in list(fresh):
            if not new[key]:
                continue
            gone = [o for o in orphans if o[key] == new[key]]
            rivals = [f for f in fresh if f[key] == new[key]]
            if len(gone) != 1 or len(rivals) != 1:
                continue                     # ambiguous: never guess an identity
            old = gone[0]
            conn.execute("DELETE FROM document WHERE path = ?", (old["path"],))
            conn.execute("UPDATE document SET doc_id = ?, first_seen = ?, moved_from = ?, "
                         "moved_by = ? WHERE path = ?",
                         (old["doc_id"], old["first_seen"], old["path"], layer, new["path"]))
            moves.append({"doc_id": old["doc_id"], "from": old["path"], "to": new["path"],
                          "matched_by": layer})
            orphans.remove(old)
            fresh.remove(new)
    for old in orphans:
        conn.execute("DELETE FROM document WHERE path = ?", (old["path"],))
    conn.execute("UPDATE document SET provisional = 0 WHERE provisional = 1")
    return moves


def duplicates(conn: Any, limit: int = 50) -> dict[str, Any]:
    """Groups of live documents that match on a layer, each with why."""
    live = {r["path"] for r in conn.execute("SELECT path FROM note")}
    rows = [dict(r) for r in conn.execute("SELECT * FROM document ORDER BY path")
            if r["path"] in live]

    def grouped(key: str) -> list[list[dict]]:
        groups: dict[str, list[dict]] = {}
        for r in rows:
            if r[key]:
                groups.setdefault(r[key], []).append(r)
        return [g for g in groups.values() if len(g) > 1]

    def members(group: list[dict]) -> list[dict[str, str]]:
        return [{"doc_id": r["doc_id"], "path": r["path"]} for r in group]

    out: list[dict[str, Any]] = []
    for group in grouped("file_key"):
        out.append({"layer": "file identity", "documents": members(group),
                    "why": "one file reached through several paths (a hard link)"})
    for group in grouped("byte_hash"):
        if len({r["file_key"] for r in group}) > 1 or not group[0]["file_key"]:
            out.append({"layer": "byte hash", "documents": members(group),
                        "why": "separate files with byte-identical content"})
    for group in grouped("text_hash"):
        if len({r["byte_hash"] for r in group}) > 1:
            out.append({"layer": "normalised text", "documents": members(group),
                        "why": "the same text, differing only in line endings, whitespace, "
                               "blank lines or Unicode form"})
    for group in grouped("external"):
        same = len({r["text_hash"] for r in group}) == 1
        out.append({"layer": "external identity", "documents": members(group),
                    "why": f"each declares {group[0]['external']}"
                           + ("" if same else "; their texts differ")})
    return {"documents": len(rows), "groups": out[:limit], "more": max(0, len(out) - limit),
            "note": "an explanation for a person: nothing was merged, moved or deleted"}
