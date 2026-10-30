"""Replay every stored audited-session history under the current rules (REMED-03).

Prints each history that does not replay cleanly, then a count of outcomes per
run folder. Read-only: no log is changed.

Usage: python scripts/audit_census.py <folder holding vaults, e.g. tmp/g5>
"""
import collections
import json
import sys
from pathlib import Path

from resource_librarian import audit_events
from resource_librarian.vault import jsonl_lines

root = Path(sys.argv[1])
counts = collections.Counter()
for path in sorted(root.rglob(".librarian/sessions/*.jsonl")):
    state = audit_events.AuditState()
    for line in jsonl_lines(path.read_text(encoding="utf-8")):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") in audit_events.AUDIT_EVENTS:
            audit_events.replay(state, event)
    if not state.used:
        continue
    run = path.relative_to(root).parts[0]
    outcome = audit_events.session_outcome(state)
    counts[(run, outcome)] += 1
    if state.halted:
        print(run, path.parts[-5], "|", outcome, "|", state.halted[:220])
for key, n in sorted(counts.items()):
    print(key, n)
