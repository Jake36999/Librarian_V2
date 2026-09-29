"""The Desk: a persisted, per-pursuit working set (Co-work Roadmap 2B).

Pinning is a person's decision and cannot be rebuilt, so it lives in its own
small store, `.librarian/desk.sqlite` (tracked, mirroring `lenses.py`'s
LensStore) rather than under `derived/`. The automatic half of the working
set is never copied in: `working_set()` reads a project's own sessions for
their `use`/`write` events (already logged - `log_use`, and the tools that
write a note) live, every time, and blends them with this store's own
`touch()` records (opening a note in the pane, say) by recency. Nothing here
duplicates the session log; it only ranks what is already there.

A pin never decays. An unpinned note's standing in the working set decays
with time (`_score`, a half-life, not a hard cutoff) and grows with how
often it was touched (logarithmically), so the desk favours what is live and
returned to over what was merely touched once.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .session import SessionStore
from .vault import Vault, now_iso

HALF_LIFE_DAYS = 7.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS desk (
  project      TEXT NOT NULL,
  note         TEXT NOT NULL,
  pinned       INTEGER NOT NULL DEFAULT 0,
  touches      INTEGER NOT NULL DEFAULT 0,
  last_touched TEXT NOT NULL,
  PRIMARY KEY (project, note)
);
"""


def _age_days(timestamp: str) -> float:
    text = timestamp.strip().replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return 999.0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - when).total_seconds() / 86400)


def _score(timestamp: str, half_life_days: float = HALF_LIFE_DAYS) -> float:
    return 0.5 ** (_age_days(timestamp) / half_life_days)


def _bump(signals: dict[str, dict[str, Any]], note: str, t: str, why: str) -> None:
    entry = signals.get(note)
    if entry is None:
        signals[note] = {"note": note, "pinned": False, "last": t, "touches": 1, "why": why}
        return
    entry["touches"] += 1
    if t >= entry["last"]:
        entry["last"], entry["why"] = t, why


class DeskStore:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.path = vault.librarian / "desk.sqlite"

    def _conn(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.executescript(SCHEMA)
        return conn

    def pin(self, project: str, note: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO desk (project, note, pinned, touches, last_touched) "
                "VALUES (?, ?, 1, 0, ?) "
                "ON CONFLICT(project, note) DO UPDATE SET pinned = 1",
                (project, note, now_iso()))

    def unpin(self, project: str, note: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE desk SET pinned = 0 WHERE project = ? AND note = ? AND pinned = 1",
                (project, note))
            return cur.rowcount > 0

    def touch(self, project: str, note: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO desk (project, note, pinned, touches, last_touched) "
                "VALUES (?, ?, 0, 1, ?) "
                "ON CONFLICT(project, note) DO UPDATE SET "
                "touches = touches + 1, last_touched = excluded.last_touched",
                (project, note, now_iso()))

    def _rows(self, project: str) -> list[sqlite3.Row]:
        with self._conn() as conn:
            return conn.execute("SELECT * FROM desk WHERE project = ?", (project,)).fetchall()

    def working_set(self, project: str, limit: int = 20) -> list[dict[str, Any]]:
        signals: dict[str, dict[str, Any]] = {}
        for row in self._rows(project):
            signals[row["note"]] = {"note": row["note"], "pinned": bool(row["pinned"]),
                                    "last": row["last_touched"], "touches": row["touches"],
                                    "why": "pinned" if row["pinned"] else "opened"}
        for session in _sessions_for(self.vault, project):
            for use in session.uses:
                name = str(use.get("source") or "").strip()
                if name:
                    _bump(signals, name, use["t"], "used")
            for write in session.writes:
                name = Path(str(write.get("path") or "")).stem
                if name:
                    _bump(signals, name, write["t"], "written")
        ranked = [{**entry, "score": round(_score(entry["last"]) *
                                            (1 + math.log(max(1, entry["touches"]))), 4)}
                 for entry in signals.values()]
        ranked.sort(key=lambda e: (not e["pinned"], -e["score"]))
        return ranked[:limit]


def pursuit_notes(vault: Vault, project: str) -> set[str]:
    """The notes that belong to a pursuit: its own project note, and its desk -
    what a person pinned or opened for it, and what its sessions used or wrote.
    What `agenda(project=...)` and a pursuit's weekly review are scoped to."""
    return {project} | {row["note"] for row in DeskStore(vault).working_set(project, 500)}


def _sessions_for(vault: Vault, project: str) -> list[Any]:
    store = SessionStore(vault)
    out = []
    for path in sorted(store.folder.glob("*.jsonl")):
        session = store.load(path.stem)
        if session.project == project:
            out.append(session)
    return out
