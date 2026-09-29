"""The agenda: where an open, dated task stands in time - overdue, today,
this week, later, or with no date at all - read from every note's own
checkboxes (Co-work Roadmap 2C).

Not a calendar, and it keeps no store of its own: a checkbox written by
`task_add` (`- [ ] text` optionally followed by `📅 YYYY-MM-DD`, Obsidian
Tasks-compatible) or typed by hand in Obsidian counts exactly the same,
because both are just Markdown a person can read without the librarian.
`scan()` re-reads every note fresh each call - no daemon, nothing to keep in
sync, nothing that can drift from what the vault actually says.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from . import notes
from .vault import Vault

# One reading of a task line, shared by the agenda, `task_done`, `task_route`
# and W1's dated-task check, so anything the agenda lists can also be checked
# off or rescheduled. Obsidian Tasks' own shape: any list bullet, indented or
# not; a status character; the description; then signifiers in any order -
# the due date among them, not necessarily last (`📅 2026-10-01 ⏫ 🔁 every
# week` is one dated task, not an undated one).
TASK_LINE = re.compile(r"^(?P<lead>[ \t]*[-*+] \[)(?P<mark>.)(?P<rest>\][ \t]+(?P<body>.*?))"
                       r"[ \t]*$")
SIGNIFIERS = "📅⏳🛫➕✅❌🔁⏫🔼🔽⏬🔺🆔⛔🏁"
DUE = re.compile(r"📅\s*(\d{4}-\d{2}-\d{2})")
CLOSED_MARKS = "xX-"                           # done, cancelled; every other status is open
THIS_WEEK_DAYS = 6                             # today, plus the next six days
BUCKETS = ("overdue", "today", "this_week", "later", "undated")


@dataclass(frozen=True)
class Task:
    start: int                 # offsets of the whole line in the text it came from
    end: int
    mark_at: int               # offset of the status character
    open: bool
    text: str                  # the description, before any signifier
    due: str                   # as written after 📅 (maybe not a real date), or ""
    line: str


def tasks(text: str) -> list[Task]:
    """Every checkbox task in `text`, outside fenced code blocks."""
    out: list[Task] = []
    fence, pos = "", 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        opened = notes.FENCE.match(line)
        if opened:
            fence = notes.toggle_fence(fence, opened.group(1))
        elif not fence:
            m = TASK_LINE.match(line)
            if m:
                body = m.group("body")
                cut = min((body.find(s) for s in SIGNIFIERS if s in body), default=len(body))
                due = DUE.search(body)
                out.append(Task(pos, pos + len(line), pos + m.start("mark"),
                                m.group("mark") not in CLOSED_MARKS, body[:cut].strip(),
                                due.group(1) if due else "", line))
        pos += len(raw)
    return out


def find_open(text: str, description: str) -> Task | None:
    """The first open task whose description is exactly `description`."""
    wanted = " ".join(description.split())
    return next((t for t in tasks(text) if t.open and " ".join(t.text.split()) == wanted), None)


def scan(vault: Vault, today: date | None = None, only: set[str] | None = None
         ) -> dict[str, list[dict[str, Any]]]:
    """Every open (unchecked) task across the vault - or, with `only`, on just
    those notes (by name) - bucketed by its due date relative to `today` (the
    caller's clock, else the real one)."""
    today = today or date.today()
    buckets: dict[str, list[dict[str, Any]]] = {b: [] for b in BUCKETS}
    for path in notes.iter_paths(vault.root):
        if only is not None and path.stem not in only:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        entry_base = {"note": path.stem, "path": path.relative_to(vault.root).as_posix()}
        for task in tasks(text):
            if not task.open:
                continue                                    # done: not on the agenda
            due = task.due
            entry = {**entry_base, "text": task.text, "due": due or None}
            when = _parse(due)
            if when is None:
                buckets["undated"].append(entry)
            elif when < today:
                buckets["overdue"].append(entry)
            elif when == today:
                buckets["today"].append(entry)
            elif when <= today + timedelta(days=THIS_WEEK_DAYS):
                buckets["this_week"].append(entry)
            else:
                buckets["later"].append(entry)
    for bucket in ("overdue", "today", "this_week", "later"):
        buckets[bucket].sort(key=lambda e: e["due"])
    return buckets


def _parse(due: str) -> date | None:
    if not due:
        return None
    try:
        return date.fromisoformat(due)
    except ValueError:
        return None
