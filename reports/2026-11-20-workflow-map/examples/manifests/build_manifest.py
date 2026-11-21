"""Prototype: compile a process into a manifest, and check it against a parent process's mandate.

    python build_manifest.py clear-enrichment-backlog
    python build_manifest.py clear-enrichment-backlog --mandate mandate.json

A process (action, workflow, pipeline, sprint) is written as YAML by a person or an agent. Its manifest is
compiled from it and from the registry, never written by hand:
  - the component tree (which processes it is made of, at which layer);
  - every action it can take, in order, with each action's declared properties;
  - a roll-up of those properties, so a parent process can be checked against the manifest alone.
A model integrating a process into a parent reads the manifest, not every action file. No model is called.
This is an example (docs/proposals/diagram-workflows.md, section 11.7), not the product.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))

from resource_librarian import tools  # noqa: E402,F401  (registers every tool)
from resource_librarian import workflows  # noqa: E402
from resource_librarian.registry import REGISTRY, TIERS  # noqa: E402

LAYER = {"action": 0, "workflow": 1, "pipeline": 2, "sprint": 3}
ACCESS = {row["tool"]: row for row in json.loads(
    (ROOT / "docs" / "tool-access-declarations.json").read_text(encoding="utf-8"))["tools"]}


def action_facts(name: str) -> dict:
    """What the registry and the access review declare about one action."""
    if name not in REGISTRY:
        return {"action": name, "declared": False}
    spec = REGISTRY.get(name)
    row = ACCESS.get(name, {})
    return {"action": name, "declared": True, "tier": spec.tier, "effect": spec.effect,
            "open_world": spec.open_world, "idempotent": spec.idempotent,
            "returns_content": row.get("returns_content"),
            "access_fingerprint": (row.get("fingerprint") or {}).get("source_sha256", "")[:12]}


def compile_process(name: str, library: workflows.Library) -> dict:
    d = library.get(name)
    workflows.closure(d, library)                    # refuses an unknown name or a cycle, as at run time
    ordered: list[dict] = []

    def walk(node: workflows.Definition, path: str, branch: str) -> list[dict]:
        tree = []
        for step in node.data.get("steps") or []:
            if not isinstance(step, dict):
                continue
            here = f"{path}/{step.get('id', '?')}"
            if "action" in step:
                ordered.append({"order": len(ordered) + 1, "at": here, "branch": branch,
                                "each": bool(step.get("each")), **action_facts(str(step["action"]))})
                tree.append({"step": step.get("id"), "kind": "action", "name": step["action"], "layer": 0})
            elif "workflow" in step:
                child = library.get(str(step["workflow"]))
                tree.append({"step": step.get("id"), "kind": child.kind, "name": child.name,
                             "layer": LAYER[child.kind], "components": walk(child, here, branch)})
            elif "route" in step:
                opts = []
                for opt, spec in (step["route"].get("options") or {}).items():
                    if isinstance(spec, dict) and "workflow" in spec:
                        child = library.get(str(spec["workflow"]))
                        opts.append({"option": opt, "kind": child.kind, "name": child.name,
                                     "layer": LAYER[child.kind],
                                     "components": walk(child, f"{here}.{opt}", f"{branch}{step.get('id')}={opt};")})
                    else:
                        opts.append({"option": opt, "kind": "end"})
                tree.append({"step": step.get("id"), "kind": "route",
                             "decided_by": step["route"].get("decide"), "options": opts})
        return tree

    tree = walk(d, d.name, "")
    declared = [a for a in ordered if a.get("declared")]
    rank = {t: i for i, t in enumerate(TIERS)}
    return {
        "manifest": 1,
        "process": d.name, "kind": d.kind, "layer": LAYER[d.kind], "origin": d.origin,
        "digest": d.digest,                         # the same digest a run pins (MF-017)
        "purpose": d.data.get("purpose", ""),
        "inputs": d.data.get("inputs") or {}, "outputs": sorted((d.data.get("outputs") or {}).keys()),
        "components": tree,
        "actions": ordered,
        "rollup": {
            "actions": len(ordered), "distinct_actions": sorted({a["action"] for a in ordered}),
            "highest_tier": max((a["tier"] for a in declared), key=lambda t: rank[t], default=None),
            "effects": sorted({a["effect"] for a in declared}),
            "open_world": any(a["open_world"] for a in declared),
            "not_idempotent": sorted({a["action"] for a in declared if not a["idempotent"]}),
            "returns_content": sorted({a["action"] for a in declared if a["returns_content"]}),
            "undeclared": sorted({a["action"] for a in ordered if not a.get("declared")}),
            "model_routed_steps": sum(1 for c in _routes(tree) if c),
        },
    }


def _routes(tree: list[dict]):
    for node in tree:
        if node.get("kind") == "route":
            yield node.get("decided_by") == "reason"
        for child in node.get("components") or []:
            yield from _routes([child])
        for opt in node.get("options") or []:
            yield from _routes(opt.get("components") or [])


def check(manifest: dict, mandate: dict) -> list[str]:
    """Which of a process's actions a parent process may not take, from the manifest alone."""
    rank = {t: i for i, t in enumerate(TIERS)}
    out = []
    for a in manifest["actions"]:
        if not a.get("declared"):
            out.append(f"{a['at']}: {a['action']} is not a registered action")
            continue
        if rank[a["tier"]] > rank[mandate.get("max_tier", "curate")]:
            out.append(f"{a['at']}: {a['action']} needs tier {a['tier']}, above the parent's {mandate['max_tier']}")
        if a["effect"] not in mandate.get("effects", ["read", "write"]):
            out.append(f"{a['at']}: {a['action']} has effect {a['effect']}, which the parent does not allow")
        if a["open_world"] and not mandate.get("open_world", True):
            out.append(f"{a['at']}: {a['action']} reaches outside the library, which the parent does not allow")
        if a["action"] in mandate.get("deny", []):
            out.append(f"{a['at']}: {a['action']} is on the parent's deny list")
    if manifest["layer"] >= mandate.get("parent_layer", 99):
        out.append(f"layer rule: a {manifest['kind']} (L{manifest['layer']}) cannot be a component of a "
                   f"parent at L{mandate['parent_layer']}")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("process")
    ap.add_argument("--mandate", type=Path)
    args = ap.parse_args(argv)
    library = workflows.Library(None)
    manifest = compile_process(args.process, library)
    out = Path(__file__).with_name(f"{args.process}.manifest.json")
    out.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    r = manifest["rollup"]
    print(f"{args.process}: L{manifest['layer']} {manifest['kind']}, {r['actions']} action steps "
          f"({len(r['distinct_actions'])} distinct), highest tier {r['highest_tier']}, effects {r['effects']}, "
          f"open world {r['open_world']} -> {out.name}")
    if args.mandate:
        problems = check(manifest, json.loads(args.mandate.read_text(encoding="utf-8")))
        print(f"against {args.mandate.name}: " + ("suitable" if not problems else f"{len(problems)} unsuitable"))
        for p in problems:
            print("  -", p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
