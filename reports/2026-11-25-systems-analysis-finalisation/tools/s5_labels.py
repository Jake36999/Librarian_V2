"""Correction round: wording changes that carry the reconciled authority, the Oracle's use of child receipts
and Geo-Grapher's incremental safety cases into the to-be specs.

    python tools/s5_labels.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Correction round by tools/s5_labels.py (2026-11-26)."

CHANGES = {
    "librarian/to-be/activation-overseer": {
        "policy_note": ("Proposed: within the commission tier 0 holds every permission and is never prompted. Reserved by policy, "
                        "and asked as agenda decisions that do not block the run: sensitivity reviews, rebuttals of challenged claims, "
                        "spend beyond the budget, a wider mandate, promotion-mode changes and lead overrides (see the authority table)."),
    },
    "librarian/to-be/oracle": {
        "handin": "hands the Oracle the output, the specification, the run's receipts and its children's receipts, each linked by hash",
        "tiera": ("runs the Tier A checks on this level's own obligations and on changed evidence only: counts reconcile, quotes "
                  "verbatim, findability, schemas, links; an unchanged child receipt is checked by its hash, not re-read"),
    },
    "geo-grapher/to-be/graph-building": {
        "check": "checks this group's stratum and store ownership, that no other application holds the group, and the disk reserve for this delta",
        "delta": ("computes what changed since the group's last snapshot: added, changed and deleted files, and every file again "
                  "when the parser version changed"),
        "write": ("writes the delta in one transaction, deletions as tombstones, and checkpoints the WAL; an interrupted "
                  "transaction rolls back to the last snapshot"),
        "prune": "prunes snapshots beyond the retention policy, never a pinned one or the one a rollback still needs",
    },
}


def main() -> None:
    for stem, labels in CHANGES.items():
        path = HERE / f"{stem}.spec.yaml"
        spec = load(path)
        nodes = {n["id"]: n for n in spec["nodes"]}
        for nid, label in labels.items():
            if nid not in nodes:
                raise KeyError(f"{stem}: no node {nid}")
            nodes[nid]["label"] = label
        save(spec, path, NOTE)


if __name__ == "__main__":
    main()
