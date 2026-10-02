"""The derived index: notes -> SQLite rows, FTS5 chunks, facets and links.

Everything here is rebuildable (`MARKDOWN_IS_TRUTH`): it lives in
`.librarian/derived/index.sqlite`, and deleting it costs only the seconds a
rebuild takes.

**The cost of a write is the note, not the vault.** V1 refreshed the whole
index after every promotion (2.2 s at 600 notes, so filling a vault cost
O(n²)). Here `upsert(path)` replaces one note's rows and FTS entries and
touches nothing else, and `refresh()` reads only the files whose size or
modification time changed. A full rebuild happens when it is asked for, or
when the content model changed, because section roles and filterable axes
come from it and every note's rows depend on them.

**What is indexed as what** comes from the content model, not from code:
- a note's sections are chunked, and each chunk carries the section's role:
  `claim` (evidence the source does the thing), `caveat` (evidence *about* it),
  or skipped (link and record lists, which match words without meaning them);
- a note's filterable values (`facet`) are the axes the content model declares
  for its shape and kind, plus its kind and topics;
- document text (PDF pages) is chunked under its Source note with the role
  `document`, and is searched only when asked for, so a long PDF cannot
  outvote the notes (V1's lesson: counting sections rewards verbose notes).
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import notes, schema
from .vault import Vault, now_iso

SCHEMA_VERSION = 2          # 2: repository components (P5.3)
TARGET_CHARS = 1200
MIN_CHARS = 80

SCHEMA = """
CREATE TABLE IF NOT EXISTS note (
  path         TEXT PRIMARY KEY,
  name         TEXT NOT NULL,
  name_lower   TEXT NOT NULL,
  shape        TEXT NOT NULL,
  kind         TEXT NOT NULL,
  title        TEXT NOT NULL,
  aliases      TEXT NOT NULL,          -- lower-case, one per line
  topic        TEXT NOT NULL,
  bottom_line  TEXT NOT NULL,
  frontmatter  TEXT NOT NULL,          -- JSON
  hash         TEXT NOT NULL,
  mtime        REAL NOT NULL,
  size         INTEGER NOT NULL,
  parse_error  TEXT NOT NULL,
  indexed_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_note_name ON note(name);
CREATE INDEX IF NOT EXISTS idx_note_shape ON note(shape, kind);

CREATE TABLE IF NOT EXISTS chunk (
  id       INTEGER PRIMARY KEY,
  path     TEXT NOT NULL,
  note     TEXT NOT NULL,
  ordinal  INTEGER NOT NULL,
  heading  TEXT NOT NULL,
  role     TEXT NOT NULL,              -- claim | caveat | document
  text     TEXT NOT NULL,
  hash     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chunk_path ON chunk(path);
CREATE INDEX IF NOT EXISTS idx_chunk_hash ON chunk(hash);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
  heading, text, tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS facet (
  path   TEXT NOT NULL,
  note   TEXT NOT NULL,
  axis   TEXT NOT NULL,
  value  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facet_axis ON facet(axis, value);
CREATE INDEX IF NOT EXISTS idx_facet_path ON facet(path);

CREATE TABLE IF NOT EXISTS component (
  path     TEXT NOT NULL,              -- the repository note's own path
  note     TEXT NOT NULL,
  address  TEXT NOT NULL,              -- a surveyed file, directory, module or entry point
  revision TEXT NOT NULL,              -- the tree or push it was read at
  evidence TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_component_note ON component(note);
CREATE INDEX IF NOT EXISTS idx_component_path ON component(path);

CREATE TABLE IF NOT EXISTS link (
  path  TEXT NOT NULL,
  src   TEXT NOT NULL,
  dst   TEXT NOT NULL                  -- lower-case note name
);
CREATE INDEX IF NOT EXISTS idx_link_dst ON link(dst);
CREATE INDEX IF NOT EXISTS idx_link_path ON link(path);

-- Keyed by the chunk's content hash, so a re-embed happens only for text
-- that is new, and a note moved or renamed keeps its vectors.
CREATE TABLE IF NOT EXISTS embedding (
  hash    TEXT NOT NULL,
  model   TEXT NOT NULL,
  dim     INTEGER NOT NULL,
  vector  BLOB NOT NULL,
  PRIMARY KEY (hash, model)
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


@dataclass
class Chunk:
    heading: str
    role: str
    text: str

    @property
    def hash(self) -> str:
        return hashlib.sha256(f"{self.heading}\n{self.text}".encode("utf-8")).hexdigest()[:24]


@dataclass
class RefreshReport:
    upserted: list[str] = field(default_factory=list)
    unchanged: int = 0
    removed: list[str] = field(default_factory=list)
    rebuilt: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"upserted": len(self.upserted), "unchanged": self.unchanged,
                "removed": len(self.removed), "rebuilt": self.rebuilt, "reason": self.reason,
                "sample": self.upserted[:10]}


# ------------------------------------------------------------------ chunking

def split_text(text: str, target: int = TARGET_CHARS) -> list[str]:
    """Paragraph-bounded pieces of about `target` characters."""
    text = text.strip()
    if len(text) <= target:
        return [text] if text else []
    pieces, current, size = [], [], 0
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if size + len(para) > target and current:
            pieces.append("\n\n".join(current))
            current, size = [], 0
        while len(para) > target * 2:             # one enormous paragraph
            pieces.append(para[:target])
            para = para[target:]
        current.append(para)
        size += len(para)
    if current:
        pieces.append("\n\n".join(current))
    return pieces


def chunk_note(note: notes.Note, model: schema.ContentModel) -> list[Chunk]:
    """One chunk per section, split on paragraphs when long. The text before
    the first heading (usually the `# Title`) is a claim: it names the note."""
    out: list[Chunk] = []
    for heading, text in note.sections().items():
        role = model.section_role(heading) if heading else "claim"
        if role == "skip":
            continue
        for piece in split_text(text):
            if len(piece) < MIN_CHARS and out and out[-1].heading == heading:
                continue
            out.append(Chunk(heading, role, piece))
    if not out and note.body.strip():
        out.append(Chunk("", "claim", note.body.strip()[:TARGET_CHARS]))
    return out


def _title(note: notes.Note) -> str:
    if note.frontmatter.get("title"):
        return str(note.frontmatter["title"])
    match = re.search(r"^# +(.+)$", note.body, re.M)
    return match.group(1).strip() if match else note.name


def fold(text: Any) -> str:
    """Lower case without accents - "Zürich" -> "zurich", "café" -> "cafe" - the way the
    FTS index's own tokenizer (unicode61, remove_diacritics) already reads text, so the
    Python-side checks and name lookups agree with it (Search Methods SM-9)."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _as_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    return [str(v) for v in value] if isinstance(value, list) else [str(value)]


# --------------------------------------------------------------------- index

class Index:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.path = vault.derived / "index.sqlite"
        self._model: schema.ContentModel | None = None
        # One connection per thread: a surface may call from several, and a
        # SQLite connection must stay on the thread that made it. WAL mode
        # lets the readers run beside a writer.
        self._local = threading.local()
        self._all: list[sqlite3.Connection] = []

    # -- connection -----------------------------------------------------------
    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self.path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.create_function("fold", 1, fold, deterministic=True)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(SCHEMA)
            self._local.conn = conn
            self._all.append(conn)
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None
            if conn in self._all:
                self._all.remove(conn)

    def __enter__(self) -> "Index":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @property
    def model(self) -> schema.ContentModel:
        if self._model is None:
            self._model = schema.load(self.vault.root)
        return self._model

    def _meta(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def _set_meta(self, key: str, value: str) -> None:
        self.conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))

    def _model_hash(self) -> str:
        path = self.vault.root / schema.MODEL_PATH
        data = path.read_bytes() if path.exists() else b""
        return hashlib.sha256(data + str(SCHEMA_VERSION).encode()).hexdigest()[:16]

    def stale_reason(self) -> str:
        """Why the whole index must be rebuilt, or empty if it need not be."""
        if not self._meta("model_hash"):
            return "the index has never been built"
        if self._meta("model_hash") != self._model_hash():
            return "the content model or the index format changed"
        return ""

    # -- writes: one note -----------------------------------------------------
    def upsert(self, path: Path, *, commit: bool = True, force: bool = False) -> bool:
        """Index one note. Returns False when its content was already indexed."""
        path = Path(path)
        rel = path.relative_to(self.vault.root).as_posix()
        stat = path.stat()
        text = path.read_text(encoding="utf-8", errors="replace")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
        row = self.conn.execute("SELECT hash FROM note WHERE path = ?", (rel,)).fetchone()
        if row and row["hash"] == digest and not force:
            self.conn.execute("UPDATE note SET mtime = ?, size = ? WHERE path = ?",
                              (stat.st_mtime, stat.st_size, rel))
            if commit:
                self.conn.commit()
            return False
        self._delete_rows(rel)
        fm, body, error = notes.parse(text)
        note = notes.Note(name=path.stem, path=path, frontmatter=fm, body=body,
                          parse_error=error)
        model = self.model
        shape = model.shape_of(note, self.vault.root) if model.found else ""
        kind = str(fm.get("kind") or "") if shape == "source" else \
            str(fm.get("concept_kind") or fm.get("offering_kind") or "")
        topics = _as_list(fm.get("primary_topic")) + _as_list(fm.get("secondary_topics"))
        aliases = [a.lower() for a in _as_list(fm.get("aliases"))]
        self.conn.execute(
            "INSERT INTO note(path, name, name_lower, shape, kind, title, aliases, topic, "
            "bottom_line, frontmatter, hash, mtime, size, parse_error, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rel, note.name, note.name.lower(), shape, kind, _title(note), "\n".join(aliases),
             topics[0] if topics else "", note.sections().get("Bottom Line", "")[:400],
             json.dumps(fm, default=str, ensure_ascii=False), digest, stat.st_mtime,
             stat.st_size, error, now_iso()))
        chunks = chunk_note(note, model) if not error else []
        self._insert_chunks(rel, note.name, chunks)
        facets: list[tuple[str, str]] = [("kind", kind)] if kind else []
        facets += [("topic", t) for t in topics]
        for axis in (model.axes_for(shape, kind) if shape else {}):
            facets += [(axis, v) for v in _as_list(fm.get(axis))]
        self.conn.executemany("INSERT INTO facet(path, note, axis, value) VALUES (?, ?, ?, ?)",
                              [(rel, note.name, a, v) for a, v in facets])
        targets = set(notes.wikilinks(body))
        for value in fm.values():
            for item in _as_list(value) if not isinstance(value, dict) else []:
                targets.update(notes.wikilinks(item))
        self.conn.executemany("INSERT INTO link(path, src, dst) VALUES (?, ?, ?)",
                              [(rel, note.name, t.lower()) for t in sorted(targets)])
        if shape == "source" and kind == "repository" and not error:
            from .components import addresses
            self.conn.executemany(
                "INSERT INTO component(path, note, address, revision, evidence) "
                "VALUES (?, ?, ?, ?, ?)",
                [(rel, note.name, a, r, e) for a, r, e in addresses(self.vault, fm)])
        if commit:
            self.conn.commit()
        return True

    def add_document_text(self, note_name: str, pages: list[str], *,
                          commit: bool = True) -> int:
        """Chunk a document's pages under its Source note, replacing any
        earlier text for that note. Returns the number of chunks."""
        row = self.conn.execute("SELECT path FROM note WHERE name = ? AND shape = 'source'",
                                (note_name,)).fetchone()
        if not row:
            raise LookupError(f"no source note named {note_name!r} in the index")
        ids = [r["id"] for r in self.conn.execute(
            "SELECT id FROM chunk WHERE path = ? AND role = 'document'", (row["path"],))]
        self._delete_chunk_ids(ids)
        chunks = [Chunk(f"p. {number}", "document", piece)
                  for number, page in enumerate(pages, 1) for piece in split_text(page)
                  if len(piece.strip()) >= 20]
        self._insert_chunks(row["path"], note_name, chunks, start=10_000)
        if commit:
            self.conn.commit()
        return len(chunks)

    def remove(self, rel: str, *, commit: bool = True) -> None:
        self._delete_rows(rel)
        if commit:
            self.conn.commit()

    def _insert_chunks(self, rel: str, name: str, chunks: list[Chunk], start: int = 0) -> None:
        for ordinal, chunk in enumerate(chunks, start):
            cursor = self.conn.execute(
                "INSERT INTO chunk(path, note, ordinal, heading, role, text, hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rel, name, ordinal, chunk.heading, chunk.role, chunk.text, chunk.hash))
            self.conn.execute("INSERT INTO chunk_fts(rowid, heading, text) VALUES (?, ?, ?)",
                              (cursor.lastrowid, chunk.heading, chunk.text))

    def _delete_chunk_ids(self, ids: list[int]) -> None:
        for chunk_id in ids:
            self.conn.execute("DELETE FROM chunk_fts WHERE rowid = ?", (chunk_id,))
            self.conn.execute("DELETE FROM chunk WHERE id = ?", (chunk_id,))

    def _delete_rows(self, rel: str, *, keep_documents: bool = True) -> None:
        role_clause = " AND role != 'document'" if keep_documents else ""
        ids = [r["id"] for r in self.conn.execute(
            f"SELECT id FROM chunk WHERE path = ?{role_clause}", (rel,))]
        self._delete_chunk_ids(ids)
        for table in ("note", "facet", "link", "component"):
            self.conn.execute(f"DELETE FROM {table} WHERE path = ?", (rel,))

    # -- writes: many notes ---------------------------------------------------
    def refresh(self) -> RefreshReport:
        """Bring the index up to date, reading only files that changed. Falls
        back to a full rebuild when the content model changed."""
        reason = self.stale_reason()
        if reason:
            report = self.rebuild()
            report.reason = reason
            return report
        report = RefreshReport()
        known = {r["path"]: (r["mtime"], r["size"]) for r in
                 self.conn.execute("SELECT path, mtime, size FROM note")}
        seen: set[str] = set()
        for path in notes.iter_paths(self.vault.root):
            rel = path.relative_to(self.vault.root).as_posix()
            seen.add(rel)
            stat = path.stat()
            if known.get(rel) == (stat.st_mtime, stat.st_size):
                report.unchanged += 1
                continue
            if self.upsert(path, commit=False):
                report.upserted.append(rel)
            else:
                report.unchanged += 1
        for rel in sorted(set(known) - seen):
            self._delete_rows(rel, keep_documents=False)
            report.removed.append(rel)
        self.conn.commit()
        return report

    def rebuild(self) -> RefreshReport:
        """Everything from the notes. Document text and embeddings survive,
        because both are keyed to content that a rebuild does not change."""
        documents = [dict(r) for r in self.conn.execute(
            "SELECT note, heading, text, ordinal FROM chunk WHERE role = 'document' "
            "ORDER BY note, ordinal")]
        for table in ("note", "chunk", "facet", "link"):
            self.conn.execute(f"DELETE FROM {table}")
        self.conn.execute("DELETE FROM chunk_fts")
        self._model = None
        report = RefreshReport(rebuilt=True)
        for path in notes.iter_paths(self.vault.root):
            self.upsert(path, commit=False, force=True)
            report.upserted.append(path.relative_to(self.vault.root).as_posix())
        by_note: dict[str, list[dict]] = {}
        for doc in documents:
            by_note.setdefault(doc["note"], []).append(doc)
        for name, rows in by_note.items():
            row = self.conn.execute("SELECT path FROM note WHERE name = ?", (name,)).fetchone()
            if row:
                self._insert_chunks(row["path"], name,
                                    [Chunk(r["heading"], "document", r["text"]) for r in rows],
                                    start=10_000)
        self._set_meta("model_hash", self._model_hash())
        self._set_meta("built_at", now_iso())
        self.conn.commit()
        return report

    # -- reads ----------------------------------------------------------------
    def stats(self) -> dict[str, Any]:
        def count(sql: str) -> int:
            return self.conn.execute(sql).fetchone()[0]
        shapes = {r["shape"] or "other": r["n"] for r in self.conn.execute(
            "SELECT shape, COUNT(*) AS n FROM note GROUP BY shape")}
        return {"notes": count("SELECT COUNT(*) FROM note"), "by_shape": shapes,
                "chunks": count("SELECT COUNT(*) FROM chunk WHERE role != 'document'"),
                "document_chunks": count("SELECT COUNT(*) FROM chunk WHERE role = 'document'"),
                "embeddings": count("SELECT COUNT(*) FROM embedding"),
                "unparsed": count("SELECT COUNT(*) FROM note WHERE parse_error != ''"),
                "duplicate_names": self.duplicate_names(),
                "built_at": self._meta("built_at"), "stale": self.stale_reason() or False}

    def duplicate_names(self) -> list[str]:
        return [r["name"] for r in self.conn.execute(
            "SELECT name FROM note GROUP BY name HAVING COUNT(*) > 1 ORDER BY name")]

    def note_row(self, name: str, shape: str = "") -> sqlite3.Row | None:
        """The note by name. `shape` prefers that shape when two notes share a name (seen
        2026-10-02: a plain note `Notes/X` beside the Project `Projects/X` hid the project
        from the desk)."""
        if shape:
            row = self.conn.execute("SELECT * FROM note WHERE name_lower = ? AND shape = ?",
                                    (name.lower(), shape)).fetchone()
            if row is not None:
                return row
        row = self.conn.execute("SELECT * FROM note WHERE name = ?", (name,)).fetchone()
        if row is None:
            row = self.conn.execute("SELECT * FROM note WHERE name_lower = ?",
                                    (name.lower(),)).fetchone()
        return row

    def linked_from(self, name: str) -> list[str]:
        return [r["src"] for r in self.conn.execute(
            "SELECT DISTINCT src FROM link WHERE dst = ? ORDER BY src", (name.lower(),))]


def open_index(vault: Vault, refresh: bool = True) -> tuple[Index, RefreshReport | None]:
    index = Index(vault)
    return index, (index.refresh() if refresh else None)


def paths_changed(index: Index, paths: Iterable[Path]) -> list[str]:
    """Upsert exactly these notes: the per-write path."""
    changed = [p.relative_to(index.vault.root).as_posix() for p in paths
               if index.upsert(p, commit=False)]
    index.conn.commit()
    return changed
