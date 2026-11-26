"""Process manifests and mandates (implementation plan M1b; W1b items 1-3; policy composition.md).

A process (workflow or pipeline, later a sprint) is compiled into a manifest from its YAML and the
registry, never written by hand:
- the component tree: which processes it is made of, at which layer;
- every action it can take, in order, with each action's declared properties, the kinds of state it
  can change among them;
- a roll-up of those properties, so a parent process is checked against the manifest alone.

The manifest's digest covers the definition's text and, for every action, a fingerprint of its
implementation and declaration. A manifest whose digest no longer matches is stale, so a changed
action is never authorised by an old manifest. Built from the prototype in
reports/2026-11-20-workflow-map/examples/manifests/build_manifest.py.
"""
from __future__ import annotations

import hashlib
import inspect
import json
from functools import lru_cache
from importlib import resources
from typing import Any

import yaml

from .registry import REGISTRY, TIERS

LAYER = {"action": 0, "workflow": 1, "pipeline": 2, "sprint": 3}
# The kinds of state an action can change (plan-forward W1b item 1). Blast radius (M6) reads these.
STATE_CLASSES = ("notes", "staging", "sessions", "indexes", "graphs", "outside")


@lru_cache(maxsize=1)
def _declared_changes() -> dict[str, tuple[str, ...]]:
    text = (resources.files("resource_librarian") / "standard" / "actions.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    out: dict[str, tuple[str, ...]] = {}
    for name, classes in (data.get("changes") or {}).items():
        bad = set(classes or []) - set(STATE_CLASSES)
        if bad:
            raise ValueError(f"actions.yaml: {name}: unknown state classes {sorted(bad)}")
        out[str(name)] = tuple(classes or [])
    return out


def changes_of(name: str) -> tuple[tuple[str, ...], str]:
    """The state classes an action can change, and whether that is `declared` (standard/actions.yaml)
    or `derived` from its registry effect, scope and open-world flag."""
    declared = _declared_changes()
    if name in declared:
        return declared[name], "declared"
    spec = REGISTRY.get(name)
    found: list[str] = []
    if spec.effect == "vault_write":
        found.append("notes")
    elif spec.effect == "write":
        if name.startswith("mcp__geo-grapher__"):
            found.append("graphs")
        elif spec.scope in ("session", "phase") or spec.sessionless:
            found.append("sessions")
        else:
            found.append("staging")
    if spec.open_world:
        found.append("outside")
    return tuple(found), "derived"


def fingerprint(name: str) -> str:
    """An action's implementation and declaration, hashed: what a manifest's digest pins."""
    spec = REGISTRY.get(name)
    try:
        source = inspect.getsource(spec.fn).replace("\r\n", "\n")
    except (OSError, TypeError):
        source = ""
    declared = json.dumps({"schema": spec.json_schema(), "tier": spec.tier, "effect": spec.effect,
                           "open_world": spec.open_world, "scope": spec.scope,
                           "changes": list(changes_of(name)[0])}, sort_keys=True, default=str)
    return hashlib.sha256((source + "\n" + declared).encode("utf-8")).hexdigest()[:16]


def action_facts(name: str) -> dict[str, Any]:
    if name not in REGISTRY:
        return {"action": name, "declared": False}
    spec = REGISTRY.get(name)
    changes, how = changes_of(name)
    return {"action": name, "declared": True, "tier": spec.tier, "effect": spec.effect,
            "open_world": spec.open_world, "idempotent": spec.idempotent,
            "changes": list(changes), "changes_from": how, "fingerprint": fingerprint(name)}


def compile_process(name: str, library: Any) -> dict[str, Any]:
    from . import workflows
    d = library.get(name)
    workflows.closure(d, library)                  # refuses an unknown name or a cycle, as a run does
    ordered: list[dict[str, Any]] = []

    def walk(node: Any, path: str, branch: str) -> list[dict[str, Any]]:
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
                             "layer": LAYER[child.kind], "digest": child.digest,
                             "components": walk(child, here, branch)})
            elif "route" in step:
                options = []
                for option, spec in (step["route"].get("options") or {}).items():
                    if isinstance(spec, dict) and "workflow" in spec:
                        child = library.get(str(spec["workflow"]))
                        options.append({"option": option, "kind": child.kind, "name": child.name,
                                        "layer": LAYER[child.kind], "digest": child.digest,
                                        "components": walk(child, f"{here}.{option}",
                                                           f"{branch}{step.get('id')}={option};")})
                    else:
                        options.append({"option": option, "kind": "end"})
                tree.append({"step": step.get("id"), "kind": "route",
                             "decided_by": step["route"].get("decide"), "options": options})
        return tree

    tree = walk(d, d.name, "")
    declared = [a for a in ordered if a.get("declared")]
    rank = {t: i for i, t in enumerate(TIERS)}
    manifest = {
        "manifest": 1, "process": d.name, "kind": d.kind, "layer": LAYER[d.kind], "origin": d.origin,
        "definition_digest": d.digest, "purpose": d.data.get("purpose", ""),
        "inputs": d.data.get("inputs") or {}, "outputs": sorted((d.data.get("outputs") or {}).keys()),
        "components": tree, "actions": ordered,
        "rollup": {
            "actions": len(ordered), "distinct_actions": sorted({a["action"] for a in ordered}),
            "highest_tier": max((a["tier"] for a in declared), key=lambda t: rank[t], default=None),
            "effects": sorted({a["effect"] for a in declared}),
            "changes": sorted({c for a in declared for c in a["changes"]}),
            "open_world": any(a["open_world"] for a in declared),
            "not_idempotent": sorted({a["action"] for a in declared if not a["idempotent"]}),
            "undeclared": sorted({a["action"] for a in ordered if not a.get("declared")}),
        },
    }
    manifest["digest"] = digest_of(manifest)
    return manifest


def digest_of(manifest: dict[str, Any]) -> str:
    """The definition texts it reaches and every action's fingerprint, hashed."""
    parts: list[str] = [manifest["definition_digest"]]

    def child_digests(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            if node.get("digest"):
                parts.append(f"{node['name']}:{node['digest']}")
            child_digests(node.get("components") or [])
            for option in node.get("options") or []:
                if option.get("digest"):
                    parts.append(f"{option['name']}:{option['digest']}")
                child_digests(option.get("components") or [])

    child_digests(manifest["components"])
    parts += [f"{a['action']}:{a.get('fingerprint', 'undeclared')}" for a in manifest["actions"]]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:16]


def is_fresh(manifest: dict[str, Any], library: Any) -> bool:
    """A stored manifest still describes the process and the actions it would run."""
    try:
        return compile_process(manifest["process"], library)["digest"] == manifest.get("digest")
    except Exception:                                # noqa: BLE001 - a process that no longer compiles is stale
        return False


REQUIRED = {"manifest": int, "process": str, "kind": str, "layer": int, "origin": str,
            "definition_digest": str, "digest": str, "components": list, "actions": list, "rollup": dict}


def problems_in(manifest: Any) -> list[str]:
    """A structural check of a manifest, as standard/manifest.schema.json states it (the Core does not
    depend on jsonschema; the tests check the schema file itself)."""
    if not isinstance(manifest, dict):
        return ["a manifest is a mapping"]
    out = [f"{key}: {kind.__name__}" for key, kind in REQUIRED.items() if not isinstance(manifest.get(key), kind)]
    if manifest.get("kind") not in ("workflow", "pipeline", "sprint"):
        out.append("kind: workflow, pipeline or sprint")
    for n, action in enumerate(manifest.get("actions") or []):
        if not isinstance(action, dict) or not isinstance(action.get("action"), str):
            out.append(f"actions[{n}]: a mapping with `action`")
        elif action.get("declared") and not set(action.get("changes") or []) <= set(STATE_CLASSES):
            out.append(f"actions[{n}].changes: one of {STATE_CLASSES}")
    return out


def check(manifest: dict[str, Any], mandate: dict[str, Any]) -> list[str]:
    """Which of a process's actions a parent process may not take, from the manifest alone."""
    rank = {t: i for i, t in enumerate(TIERS)}
    out = []
    for a in manifest["actions"]:
        if not a.get("declared"):
            out.append(f"{a['at']}: {a['action']} is not a registered action")
            continue
        if rank[a["tier"]] > rank[mandate.get("max_tier", "curate")]:
            out.append(f"{a['at']}: {a['action']} needs tier {a['tier']}, above the parent's {mandate['max_tier']}")
        if a["effect"] not in mandate.get("effects", ["read", "write", "vault_write"]):
            out.append(f"{a['at']}: {a['action']} has effect {a['effect']}, which the parent does not allow")
        if "changes" in mandate and not set(a["changes"]) <= set(mandate["changes"]):
            out.append(f"{a['at']}: {a['action']} changes {sorted(set(a['changes']) - set(mandate['changes']))}, "
                       f"which the parent does not allow")
        if a["open_world"] and not mandate.get("open_world", True):
            out.append(f"{a['at']}: {a['action']} reaches outside the library, which the parent does not allow")
        if a["action"] in mandate.get("deny", []):
            out.append(f"{a['at']}: {a['action']} is on the parent's deny list")
    # Composition rule 1: a process is built from earlier kinds, or its own kind without a cycle
    # (closure() refuses the cycle); never from a later kind.
    if manifest["layer"] > mandate.get("parent_layer", 99):
        out.append(f"layer rule: a {manifest['kind']} (L{manifest['layer']}) cannot be a component of a "
                   f"parent at L{mandate['parent_layer']}")
    return out
