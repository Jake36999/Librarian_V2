"""Handoff review (26 November): bounded retries, reachable paths, complete handoffs, rechecks and contracts.

    python tools/s6_handoff_fixes.py          # idempotent

Each fix is recorded in ADVERSARIAL-REVIEW.md, section "Handoff review".
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, renumber, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Handoff review by tools/s6_handoff_fixes.py (2026-11-26)."
L, G = "librarian/to-be/", "geo-grapher/to-be/"


def edit(stem: str, fn) -> None:
    path = HERE / f"{stem}.spec.yaml"
    spec = load(path)
    if fn(spec) is not False:
        save(renumber(spec), path, NOTE)


def has(spec, nid):
    return any(n["id"] == nid for n in spec["nodes"])


def add_node(spec, after, node):
    at = next(i for i, n in enumerate(spec["nodes"]) if n["id"] == after)
    spec["nodes"].insert(at + 1, node)


def node(spec, nid):
    return next(n for n in spec["nodes"] if n["id"] == nid)


def edges(spec, a=None, b=None):
    return [e for e in spec["edges"] if (a is None or e["from"] == a) and (b is None or e["to"] == b)]


# 1. Retries and loops: explicit limits and terminal outcomes ------------------------------------------

def paper_import_retry(spec):
    if has(spec, "dretry"):
        return False
    add_node(spec, "retry", {"id": "dretry", "kind": "decision", "lane": "Geo-Grapher store",
                             "label": "did the retry match the current row?"})
    for e in edges(spec, "retry", "content"):
        e["to"] = "dretry"
    spec["edges"] += [{"from": "dretry", "to": "content", "guard": "yes"},
                      {"from": "dretry", "to": "refuse", "guard": "no: refused, nothing written"}]


def reading_retry(spec):
    if edges(spec, "dpoison", "read"):
        return False
    node(spec, "dpoison")["label"] = "what is left after the bounded retries (at most two per part; the number is a decision)?"
    for e in edges(spec, "dpoison", "e_failed"):
        e["guard"] = "the retries are spent, and the text is still ungrounded or poison"
    spec["edges"].append({"from": "dpoison", "to": "read", "guard": "retries left: re-read only the failed parts"})


def research_bounds(spec):
    if has(spec, "dredraft"):
        return False
    add_node(spec, "ref_verify", {"id": "dredraft", "kind": "decision", "lane": "Lead (tier 1)",
                                  "label": "within two redrafts of this claim?"})
    add_node(spec, "dredraft", {"id": "dropclaim", "kind": "activity", "lane": "Lead (tier 1)",
                                "label": "drops the claim from the report as a stated gap, with its ticket, and goes on with the rest"})
    for e in edges(spec, "ref_verify"):
        if e.get("guard") in ("challenged", "refused"):
            e["to"] = "dredraft"
        if e.get("guard") == "held":
            e["to"] = "dropclaim"
    spec["edges"] += [{"from": "dredraft", "to": "draft", "guard": "yes"},
                      {"from": "dredraft", "to": "dropclaim", "guard": "no"},
                      {"from": "dropclaim", "to": "ref_oracle"}]
    node(spec, "e_paused")["label"] = "stopped by the Owner, or paused by the Oracle"


# 2. Unreachable or contradictory paths -----------------------------------------------------------------

def publication_without_folder(spec):
    for e in edges(spec, "dpub"):
        if e["to"] == "publish":
            e["guard"] = "fully converted: into its folder's group, or the library's own papers group when it has none"
        if e["to"] == "e_gap":
            e["guard"] = "Geo-Grapher disabled for this library"
    node(spec, "e_gap")["label"] = "Geo-Grapher disabled, a refusal, or an empty paper graph"


def compose_context(spec):
    d = node(spec, "dctx")
    if d["label"].startswith("routes by"):
        return False
    d["label"] = "routes by the specification's recorded owner (set at the first decision; a run never switches context)"
    guards = {"ctx1": "the owner is tier 0, working for the Owner", "ctx2": "the owner is an external project",
              "ctx3": "the owner is the person, in the Web UI"}
    for e in edges(spec, "dctx"):
        e["guard"] = guards[e["to"]]


def catalogue_limit(spec):
    moved = False
    for e in edges(spec, "x2", "a4"):
        e["to"], moved = "d3", True
    return None if moved else False


# 3. Incomplete results and handoffs -------------------------------------------------------------------

def ingestion_handoffs(spec):
    if has(spec, "codeledger"):
        return False
    add_node(spec, "dinput", {"id": "codeledger", "kind": "activity", "lane": "Core",
                              "label": "records the ledger for code-only folders: the applied groups and their receipts, no Source notes expected"})
    for e in edges(spec, "dinput", "oraclefinal"):
        e["to"] = "codeledger"
    spec["edges"].append({"from": "codeledger", "to": "oraclefinal"})
    node(spec, "oraclefinal")["label"] = ("verifies against the ledger, on a route distinct from the workers': the committed notes' "
                                          "findability and neutrality, or for code-only folders the applied groups' receipts")
    add_node(spec, "holdunmet", {"id": "dclean", "kind": "decision", "lane": "Core", "label": "are any items clean?"})
    for e in edges(spec, "holdunmet", "ref_acceptance"):
        e["to"] = "dclean"
    spec["edges"] += [{"from": "dclean", "to": "ref_acceptance", "guard": "yes"},
                      {"from": "dclean", "to": "recordpartial", "guard": "no: nothing to accept; the held items' tickets are returned"}]
    add_node(spec, "queueagenda", {"id": "heldfolders", "kind": "activity", "lane": "Core",
                                   "label": "puts the held folders on the agenda, each with its owner, and goes on with the other folders"})
    for e in edges(spec, "ref_folder_review"):
        if e.get("guard") == "held for the Owner":
            e["to"] = "heldfolders"
    spec["edges"].append({"from": "heldfolders", "to": "dinput"})


# 4. Missing rechecks ------------------------------------------------------------------------------------

def web_ui_rechecks(spec):
    if has(spec, "dkind"):
        return False
    for e in edges(spec, "batchchild", "duicrit"):
        e["to"] = "uiesc"                # the batch's own Doctor has already tried; an escalation is shown at once
    spec["edges"] = [e for e in spec["edges"] if e["from"] != "duicrit"]
    spec["nodes"] = [n for n in spec["nodes"] if n["id"] != "duicrit"]
    node(spec, "uidoctor")["label"] = "repairs the findability ticket (for example, re-indexing)"
    node(spec, "uireentry")["label"] = "confirms the repaired ticket and refreshes Search, for the Oracle's recheck"
    node(spec, "uiesc")["label"] = "shows the critical or unresolved error at once, with the ticket, flags, evidence and the compensation shown"
    for e in edges(spec, "uireentry", "reviewgate2"):
        e["to"] = "oracleverify"
    for e in edges(spec, "promotepartial", "uipartial"):
        e["to"] = "oracleverify"
    add_node(spec, "dindex", {"id": "dkind", "kind": "decision", "lane": "Web UI",
                              "label": "was the note accepted with full or partial coverage?"})
    for e in edges(spec, "dindex", "uinotify"):
        e["to"] = "dkind"
    spec["edges"] += [{"from": "dkind", "to": "uinotify", "guard": "full"},
                      {"from": "dkind", "to": "uipartial", "guard": "partial"}]
    node(spec, "oracleverify")["label"] = ("verifies the summary's integrity and the note's findability, full or partial, on a "
                                           "route distinct from the workers'")


def citation_repair(spec):
    if has(spec, "ref_doctor"):
        return False
    add_node(spec, "ticket", {"id": "ref_doctor", "kind": "ref", "lane": "Core", "use_case": "doctor",
                              "label": "re-links the paper from its publication receipt"})
    for e in edges(spec, "ticket", "e_unavailable"):
        e["to"] = "ref_doctor"
    spec["edges"] += [{"from": "ref_doctor", "to": "resolve", "guard": "resolved"},
                      {"from": "ref_doctor", "to": "e_unavailable", "guard": "declined"},
                      {"from": "ref_doctor", "to": "e_unavailable", "guard": "escalated"}]


# 5. Ownership and integration contracts -----------------------------------------------------------------

def learn_owner(spec):
    for n in spec["nodes"]:
        if n.get("lane") == "Overseer (tier 0)":
            n["lane"] = "Lead (tier 1)"
    spec["lanes"] = ["Lead (tier 1)" if lane == "Overseer (tier 0)" else lane for lane in spec["lanes"]]
    node(spec, "a1")["label"] = "owns an unmapped case resolved without a catalogued remedy (tier 0 only when it needed a code change)"
    node(spec, "a2")["label"] = "puts the Doctor's drafted remedy to the Owner: symptom shape, remedy workflow, scope, rejoin"


def doctor_draft(spec):
    node(spec, "draftprop")["label"] = "drafts a remedy for the unmapped case on the Lead's ticket; it never installs or runs it"


def folder_staleness(spec):
    if has(spec, "markstale"):
        return False
    add_node(spec, "m_success", {"id": "markstale", "kind": "activity", "lane": "Core",
                                 "label": "records the receipt, and marks the notes and claims that cite a changed entity as stale, for the Oracle's recheck"})
    for e in edges(spec, "m_success", "e_success"):
        e["to"] = "markstale"
    spec["edges"].append({"from": "markstale", "to": "e_success"})


def geo_receipt(spec):
    node(spec, "receipt")["label"] = ("returns the group's receipt: snapshot id, parser version, parse coverage with each unparsed "
                                      "file's cause, counts, and the changed entity ids (added, changed, deleted)")


def federation_decision(spec):
    if has(spec, "ddecide"):
        return False
    add_node(spec, "decide", {"id": "ddecide", "kind": "decision", "lane": "Owner", "label": "accepted?"})
    for e in edges(spec, "decide", "compare"):
        e["to"] = "ddecide"
    spec["edges"] += [{"from": "ddecide", "to": "compare", "guard": "accepted: related through the new bridges"},
                      {"from": "ddecide", "to": "compare", "guard": "rejected: compared without them, the rejection recorded"}]
    node(spec, "decide")["label"] = "decides the checked candidates: the Owner, or a standing policy for a kind the Owner has accepted"


def main() -> None:
    edit(G + "paper-import", paper_import_retry)
    edit(L + "source-reading", reading_retry)
    edit(L + "research", research_bounds)
    edit(L + "paper-publication", publication_without_folder)
    edit(L + "compose", compose_context)
    edit(L + "catalogue", catalogue_limit)
    edit(L + "ingestion", ingestion_handoffs)
    edit(L + "activation-web-ui", web_ui_rechecks)
    edit(L + "cite-graph", citation_repair)
    edit(L + "learn", learn_owner)
    edit(L + "doctor", doctor_draft)
    edit(L + "folder-review", folder_staleness)
    edit(G + "graph-building", geo_receipt)
    edit(G + "federated-search", federation_decision)


if __name__ == "__main__":
    main()
