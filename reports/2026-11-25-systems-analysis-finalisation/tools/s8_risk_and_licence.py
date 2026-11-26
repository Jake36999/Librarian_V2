"""Two Owner directions of 26 November, and ChatGPT's review of 8b9cac2.

1. High-risk decisions stay with the person when no tier 0 oversees the run, and tier 0 spends as few
   tokens and turns as possible: it is never asked to relay a reserved decision, and the Core alerts the
   Owner and tier 0 at once on a critical fault instead of tier 0 relaying the alert.
2. Licence status alone is never a reason to hold a folder (folder-review:dfolderauth).

    python tools/s8_risk_and_licence.py          # idempotent
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Risk routing and the licence hold, by tools/s8_risk_and_licence.py (2026-11-26)."
L = "librarian/to-be/"
T0 = "Overseer (tier 0)"

LABELS = {
    L + "catalogue": {
        "x3": ("puts the wider radius on the Owner's agenda as one reserved decision, with the manifest and its evidence; "
               "tier 0, when it oversees the run, is told in its handover and never asked to relay it"),
        "xe": ("hands the draft and its two revisions to the specification's owner: tier 0 when it oversees the run, "
               "otherwise the Owner, on the agenda"),
        "xp": "records the paused composition and the Owner's reason; the specification's owner is told in its handover",
        "e4": "escalated to the specification's owner: a failure of this use case",
    },
    L + "activation-overseer": {
        "escrec": ("alerts the Owner and tier 0 at once with the critical ticket, its flags, evidence hashes, spend and state, "
                   "and the compensation shown; tier 0 does not relay it"),
        "useresc": "receives the urgent alert and the ticket's link, at the same moment as tier 0",
    },
    L + "oracle": {
        "e_escalated": "the repair failed or a critical fault: the Owner is told, and tier 0 when it oversees the run",
    },
    L + "research": {
        "e_escalated": ("the graph is unavailable, or the Oracle escalates: the Owner is told, and tier 0 when it oversees "
                        "the run"),
    },
    L + "doctor": {
        "haltescalate": ("routes the critical ticket at once to the Owner, and to tier 0 when it oversees the run, with its "
                         "flags, hashes and the compensation shown"),
    },
    L + "learn": {
        "a1": ("owns an unmapped case resolved without a catalogued remedy; a code change goes to tier 0 when it oversees "
               "the run, otherwise to the Owner's agenda"),
    },
}

LANES = {L + "catalogue": {"xe": "Lead (tier 1)", "xp": "Core"}}

GUARDS = {
    # (spec, from, to): guard
    (L + "folder-review", "dfolderauth", "dheldcaller"): (
        "outside it: the person in the Web UI, an external project's out-of-scope folder, linked content reaching outside "
        "the roots, or a reserved decision such as a sensitivity flag (licence status alone is never a reason)"),
}


def drop_node(spec: dict, nid: str, *, bridge_to: str) -> None:
    """Remove a pass-through node: edges into it go to `bridge_to`, its own way out is dropped."""
    if not any(n["id"] == nid for n in spec["nodes"]):
        return
    spec["nodes"] = [n for n in spec["nodes"] if n["id"] != nid]
    edges = []
    for e in spec["edges"]:
        if e["from"] == nid:
            continue
        if e["to"] == nid:
            e = dict(e, to=bridge_to)
        edges.append(e)
    spec["edges"] = edges


def main() -> None:
    specs = {stem: load(HERE / f"{stem}.spec.yaml") for stem in set(LABELS) | set(LANES) | {g[0] for g in GUARDS}}

    cat = specs[L + "catalogue"]
    drop_node(cat, "x4", bridge_to="x5")                    # tier 0 no longer relays the wider radius
    ovr = specs[L + "activation-overseer"]
    drop_node(ovr, "failnotify", bridge_to="useresc")       # the Core alerts both at once

    for stem, labels in LABELS.items():
        nodes = {n["id"]: n for n in specs[stem]["nodes"]}
        for nid, label in labels.items():
            nodes[nid]["label"] = label
    for stem, lanes in LANES.items():
        nodes = {n["id"]: n for n in specs[stem]["nodes"]}
        for nid, lane in lanes.items():
            nodes[nid]["lane"] = lane
    for (stem, a, b), guard in GUARDS.items():
        edge = next(e for e in specs[stem]["edges"] if e["from"] == a and e["to"] == b)
        edge["guard"] = guard

    # a lane with no node left is dropped (the catalogue no longer spends a tier-0 turn)
    for spec in specs.values():
        used = {n.get("lane") for n in spec["nodes"]}
        spec["lanes"] = [ln for ln in spec["lanes"] if ln in used or ln != T0]

    for stem, spec in specs.items():
        save(spec, HERE / f"{stem}.spec.yaml", NOTE)


if __name__ == "__main__":
    main()
