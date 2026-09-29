"""Accepted lenses: an agent-side store, not notes.

A lens is a reasoning stance drawn from a passage of a source (a book, usually)
and phrased as an instruction a model can adopt. It is configuration for
agents rather than information about the source, so an accepted lens lives in
`.librarian/lenses.sqlite` (tracked: an accepted lens is a person's decision
and cannot be rebuilt), where agents and the app read it. The owner decided
this on 2026-09-25; the app gives it its own view.

Proposals wait in staging like any other machine-produced item, and only a
person's acceptance moves one here. A lens can also arrive in a *lens pack*
(`lens_packs.py`) - a plugin's or domain pack's set of hand-written lenses -
but only through a person accepting that pack's exact text.

Accepted lenses are *used*: `suggest()` ranks them for a material and a task,
and a person may adopt one into a session, which puts its instruction into
that thread's system prompt (`loop.py`). Nothing adopts a lens automatically:
its instruction was manufactured from source text, and it becomes an
instruction only by a person's choice, twice - once at acceptance, once at
adoption.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from .vault import Vault, now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS lens (
  id                 TEXT PRIMARY KEY,
  name               TEXT NOT NULL,
  source             TEXT NOT NULL,
  source_quote       TEXT NOT NULL,
  quotes             TEXT NOT NULL DEFAULT '[]',
  perspective        TEXT NOT NULL DEFAULT '',
  attends_to         TEXT NOT NULL DEFAULT '[]',
  deprioritizes      TEXT NOT NULL DEFAULT '[]',
  role_purpose       TEXT NOT NULL DEFAULT '',
  role_capabilities  TEXT NOT NULL DEFAULT '[]',
  role_expectations  TEXT NOT NULL DEFAULT '[]',
  transfers_to       TEXT NOT NULL DEFAULT '[]',
  probes             TEXT NOT NULL DEFAULT '[]',
  catches            TEXT NOT NULL DEFAULT '',
  applies_when       TEXT NOT NULL DEFAULT '',
  not_when           TEXT NOT NULL DEFAULT '',
  prompt_fragment    TEXT NOT NULL DEFAULT '',
  trace              TEXT NOT NULL DEFAULT '{}',
  legacy             TEXT NOT NULL DEFAULT '{}',
  materials          TEXT NOT NULL DEFAULT '[]',
  tasks              TEXT NOT NULL DEFAULT '[]',
  origin             TEXT NOT NULL DEFAULT '',
  edited             TEXT NOT NULL DEFAULT '{}',
  promoted_from      TEXT NOT NULL,
  accepted_at        TEXT NOT NULL,
  accepted_by        TEXT NOT NULL
);
"""
FTS_COLUMNS = ("name", "perspective", "role_purpose", "attends_to", "catches", "applies_when",
               "probes", "source")
FTS = (f"CREATE VIRTUAL TABLE IF NOT EXISTS lens_fts USING fts5(id UNINDEXED, "
       f"{', '.join(FTS_COLUMNS)}, tokenize='porter unicode61');")
ADDED = {"materials": "'[]'", "tasks": "'[]'", "origin": "''", "edited": "'{}'"}
LISTS = ("quotes", "attends_to", "deprioritizes", "role_capabilities", "role_expectations",
        "transfers_to", "probes", "materials", "tasks")
TEXTS = ("perspective", "role_purpose", "catches", "applies_when", "not_when", "prompt_fragment")
DICTS = ("trace", "edited")
# What a person may change at acceptance: the stance's wording and when it
# applies, never its evidence - the quotes stay what the source said.
EDITABLE = ("name", "perspective", "catches", "applies_when", "not_when", "prompt_fragment",
            "materials", "tasks")
# More than half of a library's drawn lenses from one source is worth saying
# (the thematic paper's "2% of domains" concern, at library scale), once there
# are enough lenses for a share to mean anything.
CONCENTRATED = 0.5
CONCENTRATION_MIN = 6


def tags(values: Any) -> list[str]:
    """Material/task tags: lower-case words, free-form so any project's own
    vocabulary works ("paper", "repository", "assess", "choose-tool")."""
    if isinstance(values, str):
        values = values.split(",")
    return sorted({re.sub(r"[^a-z0-9-]+", "-", str(v).strip().lower()).strip("-")
                   for v in values or [] if str(v).strip()} - {""})


# Where each part of a lens came from (roadmap §4 B1; thematic paper p.38:
# provenance is "multidimensional"). A verified quote is the source's own
# words; everything else was *drafted* - by the extraction chain's model, or
# by a lens pack's author - and a person may have reworded it at acceptance.
# The review shows each field's origin, so a drafted probe is never mistaken
# for something the source said.
DRAFTED = ("name", "perspective", "deprioritizes", "role_purpose", "role_capabilities",
           "role_expectations", "transfers_to", "catches", "applies_when", "not_when",
           "prompt_fragment")
GROUNDED = ("attends_to", "probes")      # drafted wording, each item with a source quote


def provenance(lens: dict[str, Any]) -> dict[str, str]:
    """Field -> "source" | "model" | "model+source" | "pack" | "person"."""
    drafter = "pack" if str(lens.get("origin") or "").startswith("pack:") else "model"
    out: dict[str, str] = {}
    if lens.get("quotes") or lens.get("source_quote"):
        out["quotes"] = "source"
    for key in DRAFTED:
        if lens.get(key):
            out[key] = drafter
    for key in GROUNDED:
        items = lens.get(key) or []
        if items:
            quoted = any(isinstance(i, dict) and i.get("because") for i in items)
            out[key] = f"{drafter}+source" if quoted else drafter
    for key in (lens.get("edited") or {}):
        out[key] = "person"
    return out


def _row_digest(row: dict[str, Any], keys: list[str]) -> str:
    body = json.dumps({k: row.get(k) for k in keys}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:24]


def _fts_text(lens: dict[str, Any]) -> tuple[str, ...]:
    def words(items: Any, key: str) -> str:
        return " ".join((i.get(key, "") if isinstance(i, dict) else str(i)) for i in items or [])
    return (lens.get("name", ""), lens.get("perspective", ""), lens.get("role_purpose", ""),
            words(lens.get("attends_to"), "what"), lens.get("catches", ""),
            lens.get("applies_when", ""), words(lens.get("probes"), "question"),
            lens.get("source", ""))


class LensStore:
    def __init__(self, vault: Vault):
        self.path = vault.librarian / "lenses.sqlite"

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        conn.execute(FTS)
        self._migrate(conn)
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """A store from before these columns keeps its rows: columns are added,
        and the search index is rebuilt once if it lacks the newer fields."""
        have = {r["name"] for r in conn.execute("PRAGMA table_info(lens)")}
        for column, default in ADDED.items():
            if column not in have:
                conn.execute(f"ALTER TABLE lens ADD COLUMN {column} TEXT NOT NULL "
                             f"DEFAULT {default}")
        fts = {r["name"] for r in conn.execute("PRAGMA table_info(lens_fts)")}
        if fts and set(FTS_COLUMNS) <= fts:
            return
        conn.execute("DROP TABLE IF EXISTS lens_fts")
        conn.execute(FTS)
        for row in conn.execute("SELECT * FROM lens").fetchall():
            self._index(conn, self._decode(row))
        conn.commit()

    @staticmethod
    def _index(conn: sqlite3.Connection, lens: dict[str, Any]) -> None:
        conn.execute("DELETE FROM lens_fts WHERE id = ?", (lens["id"],))
        conn.execute(f"INSERT INTO lens_fts(id, {', '.join(FTS_COLUMNS)}) VALUES "
                     f"(?, {', '.join('?' for _ in FTS_COLUMNS)})",
                     (lens["id"], *_fts_text(lens)))

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        out = dict(row)
        for key in LISTS + DICTS:
            out[key] = json.loads(out.get(key) or ("{}" if key in DICTS else "[]"))
        out["legacy"] = json.loads(out.get("legacy") or "{}")
        return out

    def accept(self, proposal: dict[str, Any], accepted_by: str, origin: str = "",
               edits: dict[str, Any] | None = None) -> str:
        """Store an accepted lens. `edits` are a person's own changes to the
        editable fields (`EDITABLE`), applied over the proposal with the
        original values kept in `edited`. A lens from a pack (`origin`
        "pack:...") may cite its source by name alone; any other lens is
        accepted only with the passage it was drawn from."""
        edits = {k: v for k, v in (edits or {}).items() if k in EDITABLE}
        original = {k: proposal.get(k) for k in edits}
        proposal = {**proposal, **edits}
        from_pack = origin.startswith("pack:")
        if not str(proposal.get("source_quote") or "").strip() and \
                not (from_pack and str(proposal.get("source") or "").strip()):
            raise TypeError("a lens is accepted only with the passage it was drawn from")
        if not str(proposal.get("name") or "").strip():
            raise TypeError("a lens needs a name")
        base = re.sub(r"[^a-z0-9]+", "-", str(proposal["name"]).lower()).strip("-")[:60]
        # A proposal from before E6 has no `quotes` list of its own; fall back
        # to the single quote every lens has always carried.
        quotes = proposal.get("quotes") or ([{"quote": proposal["source_quote"],
                                               "locator": proposal.get("locator", "")}]
                                             if proposal.get("source_quote") else [])
        conn = self._conn()
        try:
            lens_id, n = base, 2
            while conn.execute("SELECT 1 FROM lens WHERE id = ?", (lens_id,)).fetchone():
                lens_id, n = f"{base}-{n}", n + 1
            legacy = {k: proposal[k] for k in ("purpose", "activation_triggers",
                                                "known_blind_spots") if proposal.get(k)}
            proposal = {**proposal, "materials": tags(proposal.get("materials")),
                        "tasks": tags(proposal.get("tasks"))}
            row = {"id": lens_id, "name": str(proposal["name"]).strip(),
                   "source": proposal.get("source", ""),
                   "source_quote": str(proposal.get("source_quote") or ""),
                   **{k: str(proposal.get(k) or "") for k in TEXTS},
                   **{k: json.dumps(proposal.get(k) or [], ensure_ascii=False) for k in LISTS
                      if k != "quotes"},
                   "quotes": json.dumps(quotes, ensure_ascii=False),
                   "trace": json.dumps(proposal.get("trace") or {}, ensure_ascii=False),
                   "edited": json.dumps(original, ensure_ascii=False, default=str),
                   "legacy": json.dumps(legacy, ensure_ascii=False),
                   "origin": origin,
                   "promoted_from": proposal.get("id") or proposal.get("proposal_id", ""),
                   "accepted_at": now_iso(), "accepted_by": accepted_by}
            conn.execute(f"INSERT INTO lens({', '.join(row)}) VALUES "
                         f"({', '.join('?' for _ in row)})", tuple(row.values()))
            self._index(conn, {**proposal, "id": lens_id, "name": row["name"]})
            conn.commit()
            self._log({"op": "accept", "id": lens_id, "by": accepted_by,
                       "keys": sorted(row), "digest": _row_digest(row, sorted(row))})
            return lens_id
        finally:
            conn.close()

    def list(self, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        conn = self._conn()
        try:
            if query.strip():
                terms = " OR ".join('"' + t.replace('"', "") + '"'
                                    for t in re.findall(r"\w{3,}", query))
                rows = conn.execute(
                    "SELECT l.* FROM lens_fts JOIN lens l ON l.id = lens_fts.id "
                    "WHERE lens_fts MATCH ? ORDER BY bm25(lens_fts) LIMIT ?",
                    (terms or '""', limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM lens ORDER BY name LIMIT ?",
                                    (limit,)).fetchall()
            return [{"id": r["id"], "name": r["name"], "source": r["source"],
                     "role_purpose": r["role_purpose"][:200]} for r in rows]
        finally:
            conn.close()

    def get(self, lens_id: str) -> dict[str, Any] | None:
        conn = self._conn()
        try:
            row = conn.execute("SELECT * FROM lens WHERE id = ?", (lens_id,)).fetchone()
            if row is None:
                return None
            lens = self._decode(row)
            return {**lens, "provenance": provenance(lens)}
        finally:
            conn.close()

    def remove_origin(self, origin: str) -> int:
        """Every lens a pack installed, removed - so re-accepting a changed
        pack replaces its lenses rather than duplicating them."""
        conn = self._conn()
        try:
            ids = [r["id"] for r in conn.execute("SELECT id FROM lens WHERE origin = ?",
                                                 (origin,))]
            for lens_id in ids:
                conn.execute("DELETE FROM lens WHERE id = ?", (lens_id,))
                conn.execute("DELETE FROM lens_fts WHERE id = ?", (lens_id,))
            conn.commit()
            for lens_id in ids:
                self._log({"op": "remove", "id": lens_id, "origin": origin})
            return len(ids)
        finally:
            conn.close()

    # -- the record (roadmap §4 B4) -------------------------------------------
    @property
    def log_path(self) -> Path:
        return self.path.with_name("lens_log.jsonl")

    def _log(self, entry: dict[str, Any]) -> None:
        """An append-only, hash-chained record of every acceptance and removal,
        beside the store: the store can be rebuilt or edited, the record says
        what a person actually accepted."""
        from .session import _append_lock, _last_hash, chain_hash
        path = self.log_path
        with _append_lock(path):
            record = {"t": now_iso(), **entry}
            record["h"] = chain_hash(_last_hash(path), record)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def verify(self) -> dict[str, Any]:
        """Whether the record's chain holds, and whether every lens in the store
        is exactly what its acceptance recorded. Lenses accepted before the
        record existed are counted, not failed."""
        from .session import verify_chain
        lines = self.log_path.read_text(encoding="utf-8").splitlines() \
            if self.log_path.exists() else []
        broken = verify_chain(lines)
        accepted: dict[str, dict[str, Any]] = {}
        for line in lines:
            if line.strip():
                entry = json.loads(line)
                if entry.get("op") == "accept":
                    accepted[entry["id"]] = entry
                elif entry.get("op") == "remove":
                    accepted.pop(entry.get("id"), None)
        changed, unrecorded = [], 0
        if Path(self.path).exists():
            conn = self._conn()
            try:
                for r in conn.execute("SELECT * FROM lens"):
                    entry = accepted.get(r["id"])
                    if entry is None:
                        unrecorded += 1
                    elif _row_digest(dict(r), entry["keys"]) != entry["digest"]:
                        changed.append(r["id"])
            finally:
                conn.close()
        return {"chain": broken, "changed": changed, "unrecorded": unrecorded}

    def concentration(self) -> dict[str, Any]:
        """How many accepted lenses each source gave (roadmap §4 B3). A library
        whose stances mostly come from one or two sources sees problems the
        way those sources do; the count makes that visible. Lenses from a pack
        were chosen as a set, so they are counted apart."""
        conn = self._conn()
        try:
            rows = conn.execute("SELECT source, origin FROM lens").fetchall()
        finally:
            conn.close()
        own = [r["source"].strip() or "(no source)" for r in rows
               if not r["origin"].startswith("pack:")]
        counts: dict[str, int] = {}
        for source in own:
            counts[source] = counts.get(source, 0) + 1
        ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        top_share = ranked[0][1] / len(own) if own else 0.0
        return {"drawn": len(own), "from_packs": len(rows) - len(own),
                "sources": len(counts), "top_share": round(top_share, 2),
                "concentrated": len(own) >= CONCENTRATION_MIN and top_share > CONCENTRATED,
                "by_source": [{"source": s, "lenses": n} for s, n in ranked[:10]]}

    def origins(self) -> dict[str, int]:
        conn = self._conn()
        try:
            return {r["origin"]: r["n"] for r in conn.execute(
                "SELECT origin, COUNT(*) AS n FROM lens GROUP BY origin")}
        finally:
            conn.close()

    def suggest(self, material: str = "", task: str = "", query: str = "",
                limit: int = 5) -> list[dict[str, Any]]:
        """Accepted lenses worth considering for this material and task, each
        with *why*. A lens with no material (or task) tags fits any; one with
        tags must share one. `query` ranks by the lens's own words - name,
        stance, what it catches, when it applies, its probes. Nothing here
        judges `not_when`: it is returned for the person (or model) to read."""
        want_m, want_t = set(tags(material)), set(tags(task))
        terms = re.findall(r"\w{3,}", query or "")
        conn = self._conn()
        try:
            rows = [self._decode(r) for r in conn.execute("SELECT * FROM lens")]
            ranks: dict[str, float] = {}
            if terms:
                match = " OR ".join('"' + t.replace('"', "") + '"' for t in terms)
                for i, r in enumerate(conn.execute(
                        "SELECT id FROM lens_fts WHERE lens_fts MATCH ? "
                        "ORDER BY bm25(lens_fts)", (match,))):
                    ranks[r["id"]] = 1.0 / (1 + i)
        finally:
            conn.close()
        out = []
        for lens in rows:
            have_m, have_t = set(lens["materials"]), set(lens["tasks"])
            if want_m and have_m and not want_m & have_m:
                continue
            if want_t and have_t and not want_t & have_t:
                continue
            if terms and lens["id"] not in ranks:
                continue
            why = []
            if want_m:
                why.append(f"material: {', '.join(sorted(want_m & have_m))}" if have_m
                           else "fits any material")
            if want_t:
                why.append(f"task: {', '.join(sorted(want_t & have_t))}" if have_t
                           else "fits any task")
            if lens["id"] in ranks:
                why.append("its own words match the query")
            score = ranks.get(lens["id"], 0.0) + 0.5 * bool(want_m & have_m) + \
                0.5 * bool(want_t & have_t)
            out.append({"id": lens["id"], "name": lens["name"], "source": lens["source"],
                        "why": why or ["no filter given"], "score": round(score, 3),
                        "catches": lens["catches"], "applies_when": lens["applies_when"],
                        "not_when": lens["not_when"],
                        "probes": [p.get("question", "") if isinstance(p, dict) else str(p)
                                   for p in lens["probes"]][:3],
                        "origin": lens["origin"]})
        out.sort(key=lambda e: (-e["score"], e["name"]))
        return out[:max(1, limit)]

    def count(self) -> int:
        if not Path(self.path).exists():
            return 0
        conn = self._conn()
        try:
            return conn.execute("SELECT COUNT(*) FROM lens").fetchone()[0]
        finally:
            conn.close()
