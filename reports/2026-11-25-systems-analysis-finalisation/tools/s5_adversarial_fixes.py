"""Correction round: apply the adversarial findings accepted in ADVERSARIAL-REVIEW.md.

    python tools/s5_adversarial_fixes.py

Labels change in place; tables gain rows; nothing structural changes, so every check still holds.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Correction round by tools/s5_adversarial_fixes.py (2026-11-26)."

LABELS = {
    "librarian/to-be/activation-overseer": {
        "policy_note": ("Proposed: within the commission tier 0 holds every permission and is never prompted for one. Reserved by policy, "
                        "and asked as agenda decisions that do not block the run: sensitivity reviews, rebuttals of challenged claims, "
                        "spend beyond the budget, a wider mandate, promotion-mode changes and lead overrides (see the authority table)."),
    },
    "librarian/to-be/oracle": {
        "droute": "is an Oracle route available that is distinct from every worker's in this run?",
        "collision": ("records the review as unverified and opens a ticket for the Owner to assign or restore a distinct route; "
                      "the output is held, never passed"),
        "tiera": ("runs the Tier A checks on this level's own obligations and on changed evidence only: counts reconcile, quotes "
                  "verbatim, findability, schemas, links; an unchanged child is checked by its receipt's hash, and a mismatch "
                  "re-checks that child in full"),
    },
    "librarian/to-be/verify-claims": {
        "hold": "holds the claim, unstaged, and opens a ticket for the Lead: rewrite it, drop it, or re-review it when a route returns",
    },
    "librarian/to-be/research": {
        "e_escalated": "the graph is unavailable, or the Oracle escalates: tier 0 and the Owner are told",
    },
    "librarian/to-be/activation-external-project": {
        "queueasync": "queues the unresolved sources on the library's agenda for the Lead, without holding up the external work",
    },
    "librarian/to-be/compose": {
        "compile_manifest": ("stores the sprint's specification in the Core, checks the order action, workflow, pipeline, sprint "
                             "(a cycle is refused before anything runs), and compiles the manifest and the permission envelope"),
    },
}

ROUTING_ROWS = [
    ["A held claim: no review completed on two routes", "`verify-claims:hold`", "Lead (tier 1)", "the Lead's queue",
     "the claim is rewritten, dropped, or re-reviewed when a route returns", "`verify-claims:hold`"],
    ["A published paper with no stored link", "`cite-graph:ticket`", "Doctor (re-link from the publication receipt)",
     "the ticket service", "the citation is retried", "`cite-graph:ticket`"],
]
ROUTING_NOTE = "A failure inside the Doctor's own steps (computing the blast radius, running a remedy) is a critical ticket for tier 0."
COLLISION_CLASS = ("No Oracle route distinct from the workers'", "The Oracle is unavailable, or has no route distinct from the workers'")

SAFETY_ROWS = [
    ["Other groups refer to what changed", "references across groups are links resolved when read, never copies; the receipt lists the changed entity ids so their dependants can be re-checked", "`graph-building:receipt`", "change an entity another group links to; the link resolves to the new version and the dependant is listed"],
    ["The retention numbers are not yet decided", "nothing is pruned until they are: a safe default that costs disk, not history", "`graph-building:prune`", "with no policy set, apply twice; both snapshots remain"],
]


def update_labels() -> None:
    for stem, labels in LABELS.items():
        path = HERE / f"{stem}.spec.yaml"
        spec = load(path)
        nodes = {n["id"]: n for n in spec["nodes"]}
        for nid, label in labels.items():
            nodes[nid]["label"] = label
        save(spec, path, NOTE)


def update_table(path: Path, heading: str, rows: list[list[str]], note: str | None = None,
                 rename: tuple[str, str] | None = None) -> None:
    table = yaml.safe_load(path.read_text(encoding="utf-8"))
    section = next(s for s in table["sections"] if s["heading"] == heading)
    if rename:
        for row in section["rows"]:
            if row[0] == rename[0]:
                row[0] = rename[1]
    for row in rows:
        if row[0] not in {r[0] for r in section["rows"]}:
            section["rows"].append(row)
    if note:
        notes = next(s for s in table["sections"] if s["heading"] == "Rules").setdefault("notes", [])
        if note not in notes:
            notes.append(note)
    path.write_text(yaml.safe_dump(table, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


if __name__ == "__main__":
    update_labels()
    update_table(HERE / "librarian/to-be/ticket-routing.table.yaml", "Ticket classes", ROUTING_ROWS, ROUTING_NOTE, COLLISION_CLASS)
    update_table(HERE / "geo-grapher/to-be/incremental-safety.table.yaml", "Cases", SAFETY_ROWS)
