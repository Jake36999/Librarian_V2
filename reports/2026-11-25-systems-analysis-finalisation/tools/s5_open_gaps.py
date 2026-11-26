"""Correction round: give the two open to-be gaps an element (W-INT-02, W-ACC-01).

    python tools/s5_open_gaps.py          # run once
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, renumber, save  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / "librarian/to-be"
NOTE = "Correction round by tools/s5_open_gaps.py (2026-11-26)."


def insert_after(spec: dict, after: str, node: dict) -> None:
    at = next(i for i, n in enumerate(spec["nodes"]) if n["id"] == after)
    spec["nodes"].insert(at + 1, node)


def quarantine_tickets() -> None:
    path = PACK / "source-intake.spec.yaml"
    spec = load(path)
    if any(n["id"] == "qticket" for n in spec["nodes"]):
        return
    insert_after(spec, "capture", {"id": "qticket", "kind": "activity", "lane": "Core",
                                   "label": "opens a ticket for each quarantined sibling, routed to the Doctor's re-capture remedy, and carries on with the rest"})
    for e in spec["edges"]:
        if e["from"] == "capture" and e["to"] == "dcap":
            e["from"] = "qticket"
    spec["edges"].append({"from": "capture", "to": "qticket"})
    save(renumber(spec), path, NOTE)


def keep_draft() -> None:
    path = PACK / "activation-web-ui.spec.yaml"
    spec = load(path)
    if any(n["id"] == "dstale" for n in spec["nodes"]):
        return
    insert_after(spec, "reviewgate2", {"id": "dstale", "kind": "decision", "lane": "Web UI",
                                       "label": "has the staged revision changed while the person was editing?"})
    insert_after(spec, "dstale", {"id": "keepdraft", "kind": "activity", "lane": "Web UI",
                                  "label": "keeps the person's draft beside the new revision, shows the difference, and lets them carry their edits over"})
    for e in spec["edges"]:
        if e["from"] == "reviewgate2" and e["to"] == "dgate2choice":
            e["to"] = "dstale"
    spec["edges"] += [{"from": "dstale", "to": "dgate2choice", "guard": "unchanged"},
                      {"from": "dstale", "to": "keepdraft", "guard": "changed", "ext": "?"},
                      {"from": "keepdraft", "to": "reviewgate2"}]
    save(renumber(spec), path, NOTE)


if __name__ == "__main__":
    quarantine_tickets()
    keep_draft()
