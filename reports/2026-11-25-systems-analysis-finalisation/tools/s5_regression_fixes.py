"""Correction round: the fixes the regression matrix and MiMo's adversarial review called for
(see REGRESSION-MATRIX.md and ADVERSARIAL-REVIEW.md).

    python tools/s5_regression_fixes.py          # idempotent
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, renumber, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Correction round by tools/s5_regression_fixes.py (2026-11-26)."
T = "librarian/to-be/"

LABELS = {
    T + "folder-review": {"leadfolder": "decides the in-scope folders the Clerk screened as not sensitive, under the commission or standing policy, and applies the exclusions; a sensitivity flag goes to the Owner"},
    T + "acceptance": {
        "leadaccept": "accepts the in-scope sources and folder cards when the Owner has set promotion mode to agent, recorded as accepted by an agent; an item with a sensitivity flag or a low-confidence draft goes to the Owner",
        "promote": "commits the accepted sources through the guarded writer (compare-and-set over the files it writes), indexes them, and hands any undecided candidates on",
    },
    T + "source-intake": {
        "capture": "captures immutable evidence and literal header or DOI metadata, quarantining failed siblings and restoring a queued reference's framing",
        "stage": "validates and stages the title, the record and its unknowns; if the library has only Unfiled, queues a topic proposal on the agenda",
    },
    T + "source-enrichment": {
        "bind": "binds the source and its workflow's mandate (never wider than the parent), and reuses work already done when its key matches: the source's hash, the stage, the recipe version and the model route",
        "pubgap": "records an empty paper graph or a refusal without closing the requirement; it never triggers a reread",
        "retpartial": "returns the non-critical partial source, with its unmet tasks and any quarantine stated, each on the agenda with its owner",
    },
    T + "activation-external-project": {
        "recordapp": "validates the citations, stores the append-only Applications/ note with its locators, external constraints, when it may be reused, the verification used and its evaluation status, and queues the unresolved sources",
        "queuepause": "keeps the staged sources on the library's agenda for the Owner, or tier 0 under its own commission, to accept; returns how to resume",
    },
    T + "oracle": {
        "handin": "hands the Oracle, in a context shared with no worker, the output, the specification, the run's receipts and its children's receipts, each linked by hash",
        "verdict": "records its verdict as a claim, with its evidence; it never directs the workers",
    },
    T + "research": {
        "decide": "decides the candidates, each decision with its source and reason, or it is refused as incomplete",
        "askonce": "answers one consolidated question on the agenda: extend, narrow or stop; until then the session is parked at its resume point",
    },
    T + "source-reading": {"host": "answers the task requests on the qualified route, never another model in its place, and settles the reserved cost against the actual"},
    T + "ingestion": {
        "ledger": "reconciles one paged ledger for the folder from each item's current state, never from what was queued, and separates the folder, source, lens, topic and bridge lists",
        "doctorphase": "repairs findability, or another mapped shortfall, through a ticket; a repair re-indexes only, and never invents concepts or enables vectors to pass the check",
        "startrun": "checks the Lead's approval against the grant and the run's checkpoint, freezes the mixed batch, and returns the active run instead of starting a duplicate",
    },
    T + "activation-overseer": {"t0deliver": "writes the final handover without redoing the workers' tasks: evidence, spend, coverage, deferred work, review status and tickets"},
    T + "compose": {"worker_roles": "carries out the assigned interpretation, review and bounded reading and writing over the Core's scripted actions, seeing only the repertoire mounted for its role"},
    T + "catalogue": {"a4": "validates the draft: schema, references, arguments and outputs, and that no step declares less than its action's registered effects"},
    T + "verify-claims": {"challenge": "returns the challenge to the Lead, who rewrites the claim or proposes keeping it with a rebuttal, which only the Owner can accept"},
    T + "doctor": {"haltdecline": "keeps the ticket open, declined or deferred, assigned to the Owner on the agenda with its evidence, the compensation and a review date"},
    "geo-grapher/to-be/paper-import": {"empty": "marks the paper partial, with the reason; an empty count is not taken as unread, and no claims are invented"},
}


def labels() -> None:
    for stem, change in LABELS.items():
        path = HERE / f"{stem}.spec.yaml"
        spec = load(path)
        nodes = {n["id"]: n for n in spec["nodes"]}
        for nid, label in change.items():
            nodes[nid]["label"] = label
        save(spec, path, NOTE)


def bound_research_revision() -> None:
    """t8-22: one bounded revision after the Oracle's shortfall, then escalation."""
    path = HERE / T / "research.spec.yaml"
    spec = load(path)
    if any(n["id"] == "dshort" for n in spec["nodes"]):
        return
    at = next(i for i, n in enumerate(spec["nodes"]) if n["id"] == "ref_oracle")
    spec["nodes"].insert(at + 1, {"id": "dshort", "kind": "decision", "lane": "Lead (tier 1)",
                                  "label": "is this the brief's first shortfall?"})
    for e in spec["edges"]:
        if e["from"] == "ref_oracle" and e.get("guard") == "shortfall":
            e["to"] = "dshort"
    spec["edges"] += [{"from": "dshort", "to": "rounds", "guard": "first: one bounded revision"},
                      {"from": "dshort", "to": "e_escalated", "guard": "again: escalate"}]
    save(renumber(spec), path, NOTE)


def hold_only_unmet() -> None:
    """MiMo A4/A21: an unmet required output holds only those items; the clean subset goes on."""
    path = HERE / T / "ingestion.spec.yaml"
    spec = load(path)
    if any(n["id"] == "holdunmet" for n in spec["nodes"]):
        return
    edge = next(e for e in spec["edges"] if e["from"] == "dbatchscreen" and e["to"] == "pauseout"
                and "COLLISION" not in str(e.get("guard", "")) and "distinct" not in str(e.get("guard", "")))
    at = next(i for i, n in enumerate(spec["nodes"]) if n["id"] == "dbatchscreen")
    spec["nodes"].insert(at + 1, {"id": "holdunmet", "kind": "activity", "lane": "Core",
                                  "label": "holds only the unmet items on the agenda, each with its ticket and owner; the clean items go on to acceptance"})
    edge["to"] = "holdunmet"
    spec["edges"].append({"from": "holdunmet", "to": "ref_acceptance"})
    save(renumber(spec), path, NOTE)


def states() -> None:
    path = HERE / T / "states.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = {e["id"] for e in data["entities"]}
    if "accepted-note" not in ids:
        data["entities"].append({
            "id": "accepted-note", "name": "An accepted Source note and its revisions",
            "about": "A later reading never overwrites an accepted note: it stages a revision, which is accepted into the same note or rejected.",
            "evidence": "staging.py revision_of and merged (as-is accept of a revision, line 1152); 2026-11-21 baseline requirement of accepted-note revisions",
            "initial": "accepted", "final": ["accepted"],
            "transitions": [
                {"from": "accepted", "to": "revision-staged", "on": "a later reading stages a revision; the note is untouched", "by": "Core"},
                {"from": "revision-staged", "to": "accepted", "on": "the revision is accepted and merged into the same note, never a second note", "by": "Lead (tier 1)"},
                {"from": "revision-staged", "to": "accepted", "on": "the revision is rejected; the note stays as it was", "by": "Owner"},
            ],
            "notes": "A partial revision gives no acceptance authority and no credit for full reading."})
    for e in data["entities"]:
        if e["id"] == "ticket":
            extra = {"from": "assigned", "to": "assigned", "on": "past its review date: raised to the next owner (the Lead, then tier 0, then the Owner)", "by": "Core"}
            if extra not in e["transitions"]:
                e["transitions"].append(extra)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


def tables() -> None:
    path = HERE / T / "ticket-routing.table.yaml"
    table = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = table["sections"][0]["rows"]
    for row in (["A permitted partial, or unmet tasks", "`source-enrichment:retpartial`", "Lead (tier 1), for the parent",
                 "the agenda, with a review date", "re-run, accepted as partial, or dropped", "`source-enrichment:retpartial`"],
                ["A ticket whose remedy is unavailable or declined", "`doctor:haltdecline`", "Owner (assigned), or the Lead when no reserved decision is needed",
                 "the agenda, with a review date", "the Owner decides, or the Lead hands it to tier 0", "`doctor:haltdecline`"]):
        if row[0] not in {r[0] for r in rows}:
            rows.append(row)
    notes = next(s for s in table["sections"] if s["heading"] == "Rules")["notes"]
    for note in ("Every open ticket and agenda decision has an owner and a review date; past its date it is raised to the next owner: the Lead, then tier 0, then the Owner. The dates are a decision.",
                 "A remedy never writes an attached original: originals are read-only to every agent.",
                 "A findability repair re-indexes only: it never invents concepts or enables vectors to pass a check."):
        if note not in notes:
            notes.append(note)
    path.write_text(yaml.safe_dump(table, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")

    path = HERE / T / "authority.table.yaml"
    table = yaml.safe_load(path.read_text(encoding="utf-8"))
    for row in table["sections"][0]["rows"]:
        if row[0].startswith("Gate 2: accept sources"):
            row[0] = "Gate 2: accept sources, under promotion mode agent (which only the Owner sets)"
        if row[0] == "A sensitivity review":
            row[0] = "A sensitivity review, a sensitivity flag, or a low-confidence draft"
            row[6] = "`acceptance:leadaccept`"
    path.write_text(yaml.safe_dump(table, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")

    path = HERE / "geo-grapher/to-be/performance.table.yaml"
    table = yaml.safe_load(path.read_text(encoding="utf-8"))
    rows = table["sections"][0]["rows"]
    row = ["Import papers in a batch session", "C: one subprocess per paper", "seconds per paper across a batch",
           "decision needed: whether a batch session is worth it once the service is running", "`paper-import:send`"]
    if row[0] not in {r[0] for r in rows}:
        rows.append(row)
    path.write_text(yaml.safe_dump(table, sort_keys=False, allow_unicode=True, width=120), encoding="utf-8")


if __name__ == "__main__":
    labels()
    bound_research_revision()
    hold_only_unmet()
    states()
    tables()
