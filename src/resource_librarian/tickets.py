"""Tickets for failures and misalignments (implementation plan M3; policy: the fault register).

A ticket is a record, not a code in a call's result (as-is W-DOC-02): its class, owner, scope, evidence,
repair history and review date. Classes and owners are declared in `standard/tickets.yaml`, from the
to-be ticket-routing table. The store lives beside the checkpoints (`.librarian/tickets.json`) and is
written the same way, under a lock, so two parallel runs never lose a row.

Escalation is computed, not scheduled: a ticket past its review date is shown under the next owner on
the escalation path, one step per review period, with no daemon. Opening is idempotent per (class,
scope) while a ticket is open, so a retry or a re-run does not open a second ticket for one failure.
A worker never closes its own ticket.
"""
from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from .coordination import atomic_write_text
from .vault import now_iso

OWNERS = ("doctor", "lead", "overseer", "owner")
QUEUES = ("agenda", "lead", "tickets", "alert")
_LOCKS: dict[str, threading.RLock] = {}
_GUARD = threading.Lock()


def lock_for(path: Any) -> threading.RLock:
    """One lock per store file, shared by every instance in the process."""
    key = str(path)
    with _GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


@lru_cache(maxsize=1)
def routing() -> dict[str, Any]:
    text = (resources.files("resource_librarian") / "standard" / "tickets.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    escalation = list(data.get("escalation") or [])
    if not set(escalation) <= set(OWNERS):
        raise ValueError(f"tickets.yaml: escalation names only {OWNERS}")
    classes = {}
    for name, spec in (data.get("classes") or {}).items():
        if spec.get("owner") not in OWNERS or spec.get("queue") not in QUEUES:
            raise ValueError(f"tickets.yaml: {name}: owner one of {OWNERS}, queue one of {QUEUES}")
        days = spec.get("review_days")
        if days is not None and (not isinstance(days, int) or days < 0):
            raise ValueError(f"tickets.yaml: {name}: review_days is a whole number of days")
        classes[str(name)] = dict(spec)
    return {"escalation": escalation, "classes": classes}


def _parse(value: str) -> datetime | None:
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def effective_owner(ticket: dict[str, Any], now: datetime | None = None) -> tuple[str, bool]:
    """Who owns an open ticket now, and whether it is past its review date. Past it, the ticket
    moves one step along the escalation path per review period (computed, never scheduled)."""
    days = (routing()["classes"].get(ticket["class"]) or {}).get("review_days")
    review_by = _parse(ticket.get("review_by") or "")
    if ticket.get("status") != "open" or days is None or review_by is None:
        return ticket["owner"], False
    now = now or datetime.now(timezone.utc)
    if now <= review_by:
        return ticket["owner"], False
    path = routing()["escalation"]
    steps = 1 if days == 0 else 1 + int((now - review_by) / timedelta(days=days))
    start = path.index(ticket["owner"]) if ticket["owner"] in path else len(path) - 1
    return path[min(len(path) - 1, start + steps)], True


class TicketStore:
    def __init__(self, vault: Any) -> None:
        self.vault = vault
        self.path = vault.librarian / "tickets.json"

    # -- reading ----------------------------------------------------------------
    def all(self, open_only: bool = False, now: datetime | None = None) -> list[dict[str, Any]]:
        rows = self._load()
        if open_only:
            rows = [r for r in rows if r["status"] == "open"]
        out = []
        for row in rows:
            owner, overdue = effective_owner(row, now)
            out.append({**row, "current_owner": owner, "overdue": overdue})
        return out

    def get(self, ticket_id: str) -> dict[str, Any]:
        for row in self._load():
            if row["id"] == ticket_id:
                return row
        raise KeyError(f"no ticket {ticket_id!r}")

    # -- writing ----------------------------------------------------------------
    def ensure(self, cls: str, scope: str, *, summary: str = "", evidence: dict[str, Any] | None = None,
               opened_by: str = "core", owner: str = "") -> dict[str, Any]:
        """The open ticket for this failure, or a new one: one ticket per (class, scope) while open."""
        spec = routing()["classes"].get(cls)
        if spec is None:
            raise ValueError(f"ticket class is one of {sorted(routing()['classes'])}")
        scope = str(scope).strip()[:300]
        if not scope:
            raise ValueError("a ticket needs a scope")
        owner = owner or spec["owner"]
        if owner not in OWNERS:
            raise ValueError(f"owner is one of {OWNERS}")
        with lock_for(self.path):
            rows = self._load()
            for row in rows:
                if row["class"] == cls and row["scope"] == scope and row["status"] == "open":
                    return row
            opened = now_iso()
            days = spec.get("review_days")
            review_by = ((_parse(opened) or datetime.now(timezone.utc)) + timedelta(days=days)
                         ).isoformat(timespec="seconds") if days is not None else ""
            row = {"id": secrets.token_hex(6), "class": cls, "title": spec.get("title", cls),
                   "scope": scope, "summary": str(summary)[:500], "evidence": dict(evidence or {}),
                   "owner": owner, "queue": spec["queue"], "opened_by": str(opened_by)[:80],
                   "opened_at": opened, "review_by": review_by, "status": "open",
                   "history": [{"at": opened, "event": "opened", "by": str(opened_by)[:80], "owner": owner}]}
            rows.append(row)
            self._save(rows)
            return row

    def note(self, ticket_id: str, by: str, text: str, *, handover_to: str = "") -> dict[str, Any]:
        """Record a repair attempt or a finding; with `handover_to`, name the next owner."""
        if handover_to and handover_to not in OWNERS:
            raise ValueError(f"handover_to is one of {OWNERS}")
        with lock_for(self.path):
            rows = self._load()
            row = next((r for r in rows if r["id"] == ticket_id), None)
            if row is None:
                raise KeyError(f"no ticket {ticket_id!r}")
            if row["status"] != "open":
                raise ValueError(f"ticket {ticket_id} is {row['status']}")
            entry = {"at": now_iso(), "event": "handover" if handover_to else "note",
                     "by": str(by)[:80], "text": str(text)[:1000]}
            if handover_to:
                entry["owner"] = row["owner"] = handover_to
            row["history"].append(entry)
            self._save(rows)
            return row

    def close(self, ticket_id: str, by: str, resolution: str) -> dict[str, Any]:
        """Close a ticket with its resolution. A worker never closes its own ticket: the closer is
        the person, the Oracle's recheck, or the Core's own recheck."""
        if by not in ("person", "oracle", "core-recheck"):
            raise ValueError("a ticket is closed by the person or a recheck, never by the worker")
        with lock_for(self.path):
            rows = self._load()
            row = next((r for r in rows if r["id"] == ticket_id), None)
            if row is None:
                raise KeyError(f"no ticket {ticket_id!r}")
            if row["status"] == "open":
                row.update(status="closed", closed_at=now_iso(), resolution=str(resolution)[:500])
                row["history"].append({"at": row["closed_at"], "event": "closed", "by": by,
                                       "text": row["resolution"]})
                self._save(rows)
            return row

    # -- the file ---------------------------------------------------------------
    def _load(self) -> list[dict[str, Any]]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        rows = data.get("tickets", []) if isinstance(data, dict) else []
        return [r for r in rows if isinstance(r, dict) and {"id", "class", "scope", "owner", "status"} <= set(r)]

    def _save(self, rows: list[dict[str, Any]]) -> None:
        atomic_write_text(self.path, json.dumps({"schema_version": 1, "tickets": rows}, indent=2,
                                                ensure_ascii=False) + "\n")
