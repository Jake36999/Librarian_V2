"""Correction round, gap 1: the process catalogue (repertoire) lifecycle, restored to the to-be pack.

    python tools/s5_catalogue.py          # run once

The 20 November UC-C spec drew the lifecycle: search the repertoire, draft, validate, check the layer
rule, compile the manifest, check it against the parent's mandate, dry-run with the Oracle, run, propose
promotion, check for duplicates, the Owner accepts, the Core pins the digest. Canonicalisation (S1) kept
only the sprint-level compose and dropped it. This rebuilds it as the child `catalogue` (UC8.2), with:
- the accepted layer table of docs/proposals/diagram-workflows.md section 11.1;
- storage in the Core (docs/policy/agent-roles-and-authority.md: specifications belong within the Core);
and has the to-be compose call it where sub-processes are written.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, renumber, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
OLD = REPO / "reports/2026-11-20-workflow-map/examples/ingestion/compose.spec.yaml"
PACK = HERE / "librarian/to-be"

LANES = {"Tier 0 agent": "Overseer (tier 0)", "Helper (tier 2)": "Clerk (tier 2)"}
RULE = ("validates the layer rule: an action has no components; a workflow holds actions and, without a cycle, "
        "workflows; a pipeline holds workflows and actions; a sprint holds pipelines, workflows and actions")
LABELS = {
    "a2": "searches the repertoire, the Core's store of accepted processes, for one that covers it, lowest layer first",
    "a3": "drafts a process at the layer the task needs, from accepted processes as its components",
    "a4": "validates the draft: schema, references, arguments and outputs",
    "a5": RULE,
    "a6": "compiles the manifest: the component tree, the actions in order, their declared effects, tier and outside access, and the blast radius",
    "d5": "does the manifest fit the parent's mandate: tier, effects, outside access and deny list?",
    "x4": "puts the wider radius to the Owner as one reserved decision",
    "a7": "dry-runs the draft against its specification: Tier A checks, then a Tier B review",
    "a8": "runs the process for the task, pinned to its digest",
    "a10": "checks the proposal against the repertoire for duplicates, and puts it on the Owner's agenda",
    "a12": "stores the specification in the Core, pins its digest, and records its manifest and provenance",
    "e1": "the process is in the repertoire, available as a component of any later parent process",
}
GUARDS = {("d4", "x2"): "it breaks the rule: a later layer, a same-layer component outside workflows, or a cycle"}


def build_catalogue() -> None:
    spec = load(OLD)
    for key in ("superseded_by", "status"):
        spec.pop(key, None)
    spec["lanes"] = [LANES.get(lane, lane) for lane in spec["lanes"]]
    for node in spec["nodes"]:
        node["lane"] = LANES.get(node.get("lane"), node.get("lane"))
        if node.get("lane") is None:
            node.pop("lane")
        if node["id"] in LABELS:
            node["label"] = LABELS[node["id"]]
        if node["id"] == "d5":
            node["lane"] = "Core"              # a deterministic comparison of manifest and mandate (section 11.7)
    for edge in spec["edges"]:
        if (edge["from"], edge["to"]) in GUARDS:
            edge["guard"] = GUARDS[(edge["from"], edge["to"])]
    spec["lanes"] = [lane for lane in spec["lanes"] if any(n.get("lane") == lane for n in spec["nodes"])]
    head = {"diagram": "catalogue", "use_case": "UC8.2", "status": "PROPOSED_UNACCEPTED",
            "supersedes": ["reports/2026-11-20-workflow-map/examples/ingestion/compose.spec.yaml"],
            "kind": "activity", "title": "Compose a process and promote it into the repertoire (proposed)",
            "problem": {
                "symptom": "Canonicalisation kept the sprint-level compose and dropped the repertoire's lifecycle: duplicates, the Owner's acceptance, the pinned digest.",
                "root": "A process is reused if one is accepted, composed under the layer rule if not, and kept only through the Owner's acceptance, stored in the Core."},
            "evidence": ["docs/proposals/diagram-workflows.md sections 11.1 (layer table), 11.3 (UC-C), 11.7 (manifests).",
                         "docs/policy/agent-roles-and-authority.md: specifications belong within the Librarian Core."]}
    body = {k: v for k, v in spec.items() if k not in ("diagram", "use_case", "kind", "title", "problem", "evidence")}
    save({**head, **body}, PACK / "catalogue.spec.yaml",
         "Rebuilt from the 20 November UC-C by tools/s5_catalogue.py (correction round, 2026-11-26).")


def wire_compose() -> None:
    path = PACK / "compose.spec.yaml"
    spec = load(path)
    if any(n["id"] == "ref_catalogue" for n in spec["nodes"]):
        return
    at = next(i for i, n in enumerate(spec["nodes"]) if n["id"] == "lead_subspec")
    spec["nodes"].insert(at + 1, {"id": "ref_catalogue", "kind": "ref", "lane": "Lead (tier 1)", "use_case": "catalogue",
                                  "label": "reuses an accepted process for each part, or composes one and proposes it"})
    for node in spec["nodes"]:
        if node["id"] == "compile_manifest":
            node["label"] = ("stores the sprint's specification in the Core, checks the order action, workflow, pipeline, "
                             "sprint has no cycle, and compiles the manifest and the permission envelope")
    edges = []
    for edge in spec["edges"]:
        if edge["from"] == "lead_subspec" and edge["to"] == "dnarrow":
            edges.append({"from": "lead_subspec", "to": "ref_catalogue"})
            continue
        edges.append(edge)
    edges += [{"from": "ref_catalogue", "to": "dnarrow", "guard": "success"},
              {"from": "ref_catalogue", "to": "dnarrow", "guard": "reused", "ext": "?"},
              {"from": "ref_catalogue", "to": "dnarrow", "guard": "used once", "ext": "?"},
              {"from": "ref_catalogue", "to": "outpause", "guard": "paused", "ext": "?"},
              {"from": "ref_catalogue", "to": "outesc", "guard": "escalated", "ext": "?"}]
    spec["edges"] = edges
    save(renumber(spec), path, "Wired to the catalogue by tools/s5_catalogue.py (correction round, 2026-11-26).")


if __name__ == "__main__":
    build_catalogue()
    wire_compose()
