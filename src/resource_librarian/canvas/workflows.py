"""A workflow drawn as a canvas, and a canvas compiled into a workflow (W2, 2026-11-20).

The design is the owner's MARK XLVIII canvas planner (docs/proposals/plan-forward-2026-11.md,
Appendix A), compiled onto this Librarian's own YAML workflows rather than its runtime:

- Every node is at once a step and its own description. Its leading `key: value` lines are
  directives; the first line that is not one starts free text, which the compiler ignores.
- `role: workflow` is the one anchor: `workflow: <name>`, `input <name>: <type>[ = default]`,
  `output <name>: <reference>`, and its prose is the purpose.
- `role: step` (or any node with `action:`) is an action step: `id`, `action`, `arg <name>:`,
  `each`, `when`, `on_error`, `side_effects`, `accept`, `compensation`.
- Any other node, or one with no role, is a note: it does nothing (the least it could do) and
  is reported, so a drawing can never mint a step by accident. A step with no action is refused.
- An edge labelled `needs` is a dependency (`depends_on`); any other edge only orders the steps.
  Order is decided by the edges, then by step id - never by where a node sits - so moving nodes
  on the canvas never changes the workflow, and never re-opens its approval.

The compiled YAML goes through `workflows.validate` (closed action registry, each action's own
arguments) and `save_workflow` / `accept_workflow`, so a drawn workflow is approved and pinned
exactly like a written one.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any

import yaml

from .service import MANAGED_PREFIX

DIRECTIVE = re.compile(r"^(?P<key>[a-z_]+(?: [A-Za-z0-9_\-]+)?):\s?(?P<value>.*)$")
REFERENCE = re.compile(r"^(inputs|steps|item)(\.[A-Za-z0-9_\-]+)+$")
ROLE_ALIASES = {"workflow": "workflow", "start": "workflow", "anchor": "workflow",
                "step": "step", "action": "step", "note": "note", "end": "note"}
NEEDS = {"needs", "depends on", "depends_on"}


# ----------------------------------------------------------------------------- reading a node

def directives(text: str) -> tuple[dict[str, str], str]:
    """A node's leading `key: value` lines, and the free text after them."""
    found: dict[str, str] = {}
    lines = (text or "").splitlines()
    for i, line in enumerate(lines):
        match = DIRECTIVE.match(line.strip())
        if not line.strip() or not match:
            return found, "\n".join(lines[i:]).strip()
        found[match["key"]] = match["value"].strip()
    return found, ""


def _value(raw: str) -> Any:
    raw = raw.strip()
    if REFERENCE.match(raw):
        return {"from": raw}
    try:
        return yaml.safe_load(raw) if raw else ""
    except yaml.YAMLError:
        return raw


def _shown(value: Any) -> str:
    if isinstance(value, dict) and set(value) == {"from"}:
        return str(value["from"])
    if isinstance(value, str) and value and not REFERENCE.match(value):
        try:
            plain = yaml.safe_load(value) == value       # "yes" would read back as True
        except yaml.YAMLError:
            plain = False
        if plain and value.strip() == value and "\n" not in value:
            return value
    return json.dumps(value, ensure_ascii=False)


# ----------------------------------------------------------------------------- canvas -> workflow

def compile_canvas(payload: dict[str, Any]) -> dict[str, Any]:
    """`{yaml, definition, fingerprint, errors, notes}` for a drawn workflow. Errors refuse it."""
    errors: list[str] = []
    notes: list[str] = []
    anchor: dict[str, Any] | None = None
    steps: dict[str, dict[str, Any]] = {}                  # node id -> step
    for node in payload.get("nodes", []):
        if not isinstance(node, dict) or node.get("type") != "text":
            continue
        found, prose = directives(str(node.get("text") or ""))
        role = ROLE_ALIASES.get(found.get("role", "").casefold(),
                                "step" if "action" in found else "")
        where = f"node {node.get('id')!r}"
        if role == "workflow":
            if anchor is not None:
                errors.append(f"{where}: a second `role: workflow` node; a drawing has one")
                continue
            anchor = {"found": found, "prose": prose, "where": where}
        elif role == "step":
            if not found.get("action"):
                errors.append(f"{where}: a step names no action (refused, never guessed)")
                continue
            sid = found.get("id") or ""
            if not sid:
                errors.append(f"{where}: a step needs an `id:`")
                continue
            step: dict[str, Any] = {"id": sid, "action": found["action"]}
            args = {k.split(" ", 1)[1]: _value(v) for k, v in found.items() if k.startswith("arg ")}
            if args:
                step["args"] = args
            for key in ("each", "when", "on_error", "side_effects"):
                if key in found:
                    step[key] = _value(found[key])
            if "accept" in found:
                accept = _value(found["accept"])
                step["acceptance_criteria"] = accept if isinstance(accept, list) else [accept]
            if "compensation" in found:
                step["compensation"] = _value(found["compensation"])
            unknown = sorted(k for k in found if k not in {
                "role", "id", "action", "each", "when", "on_error", "side_effects", "accept",
                "compensation"} and not k.startswith("arg "))
            if unknown:
                errors.append(f"{where}: unknown directive(s) {unknown}")
            steps[str(node.get("id"))] = step
        else:
            notes.append(f"{where} is a note (role {found.get('role') or 'none'}): it does nothing")
    if anchor is None:
        errors.append("no `role: workflow` node: a drawing needs exactly one, naming the workflow")
        return {"errors": errors, "notes": notes}
    # Edges between steps: `needs` is a dependency, anything else only orders.
    after: dict[str, set[str]] = defaultdict(set)
    needs: dict[str, list[str]] = defaultdict(list)
    for edge in payload.get("edges", []):
        src, dst = str(edge.get("fromNode") or ""), str(edge.get("toNode") or "")
        if src in steps and dst in steps:
            after[dst].add(src)
            if str(edge.get("label") or "").strip().casefold() in NEEDS:
                needs[dst].append(steps[src]["id"])
    order: list[str] = []
    ready = sorted((n for n in steps if not after[n]), key=lambda n: steps[n]["id"])
    waiting = {n: set(after[n]) for n in steps}
    while ready:
        node = ready.pop(0)
        order.append(node)
        for other in steps:
            if node in waiting[other]:
                waiting[other].discard(node)
                if not waiting[other] and other not in order and other not in ready:
                    ready.append(other)
                    ready.sort(key=lambda n: steps[n]["id"])
    if len(order) != len(steps):
        errors.append("the steps' edges form a cycle: " +
                      ", ".join(sorted(steps[n]["id"] for n in steps if n not in order)))
    ids = [steps[n]["id"] for n in order]
    if len(set(ids)) != len(ids):
        errors.append(f"two steps share an id: {sorted({i for i in ids if ids.count(i) > 1})}")
    found = anchor["found"]
    name = found.get("workflow") or ""
    definition: dict[str, Any] = {"workflow": name,
                                  "purpose": anchor["prose"] or found.get("purpose", "")}
    inputs: dict[str, Any] = {}
    outputs: dict[str, Any] = {}
    for key, value in found.items():
        if key.startswith("input "):
            kind, _, default = value.partition("=")
            spec: dict[str, Any] = {"type": kind.strip()}
            if _:
                spec["default"] = _value(default)
            inputs[key.split(" ", 1)[1]] = spec
        elif key.startswith("output "):
            outputs[key.split(" ", 1)[1]] = _value(value)
    for key in ("tier", "macro"):
        if key in found:
            definition[key] = _value(found[key])
    if inputs:
        definition["inputs"] = inputs
    out_steps = []
    for node in order:
        step = dict(steps[node])
        if needs.get(node):
            step["depends_on"] = list(dict.fromkeys(needs[node]))
        out_steps.append(step)
    definition["steps"] = out_steps
    if outputs:
        definition["outputs"] = outputs
    text = yaml.safe_dump(definition, sort_keys=False, allow_unicode=True, width=100)
    return {"yaml": text, "definition": definition, "fingerprint": fingerprint(payload),
            "errors": errors, "notes": notes}


def fingerprint(payload: dict[str, Any]) -> str:
    """What a person authored: every text node's text and every edge, never positions."""
    nodes = sorted((str(n.get("id")), str(n.get("text") or "")) for n in payload.get("nodes", [])
                   if isinstance(n, dict) and n.get("type") == "text")
    edges = sorted((str(e.get("fromNode")), str(e.get("toNode")), str(e.get("label") or ""))
                   for e in payload.get("edges", []) if isinstance(e, dict))
    return hashlib.sha256(json.dumps([nodes, edges]).encode("utf-8")).hexdigest()[:16]


# ----------------------------------------------------------------------------- workflow -> canvas

def draw_workflow(definition: dict[str, Any], *, side_effects: dict[str, str] | None = None,
                  prefix: str = MANAGED_PREFIX) -> dict[str, Any]:
    """A canvas of one workflow: its anchor, a node per step, and its order and dependencies.
    Node ids carry the managed prefix, so the safe service never mistakes a person's nodes for
    these, and a redraw replaces only these."""
    name = str(definition.get("workflow") or "")
    base = f"{prefix}wf-{name}"
    lines = ["role: workflow", f"workflow: {name}"]
    for input_name, spec in (definition.get("inputs") or {}).items():
        default = f" = {_shown(spec['default'])}" if isinstance(spec, dict) and "default" in spec else ""
        lines.append(f"input {input_name}: {spec.get('type', 'string')}{default}")
    for out, ref in (definition.get("outputs") or {}).items():
        lines.append(f"output {out}: {_shown(ref)}")
    for key in ("tier", "macro"):
        if key in definition:
            lines.append(f"{key}: {_shown(definition[key])}")
    nodes = [{"id": base, "type": "text", "x": 0, "y": 0, "width": 420, "height": 220,
              "text": "\n".join(lines) + "\n\n" + str(definition.get("purpose") or "")}]
    edges = []
    previous = ""
    for step in definition.get("steps") or []:
        if "action" not in step:
            continue                             # a nested workflow or route is drawn elsewhere
        sid = str(step["id"])
        body = ["role: step", f"id: {sid}", f"action: {step['action']}"]
        for arg, value in (step.get("args") or {}).items():
            body.append(f"arg {arg}: {_shown(value)}")
        for key in ("each", "when", "on_error"):
            if key in step:
                body.append(f"{key}: {_shown(step[key])}")
        effect = step.get("side_effects") or (side_effects or {}).get(sid)
        if step.get("side_effects"):
            body.append(f"side_effects: {step['side_effects']}")
        if step.get("acceptance_criteria"):
            body.append(f"accept: {_shown(step['acceptance_criteria'])}")
        if step.get("compensation"):
            body.append(f"compensation: {_shown(step['compensation'])}")
        note = f"\n\nTouches: {effect}." if effect and not step.get("side_effects") else ""
        node_id = f"{base}-{sid}"
        nodes.append({"id": node_id, "type": "text", "x": 0, "y": 0, "width": 420,
                      "height": 200 + 20 * len(body), "text": "\n".join(body) + note})
        for dep in step.get("depends_on") or []:
            edges.append({"id": f"{node_id}-needs-{dep}", "fromNode": f"{base}-{dep}",
                          "toNode": node_id, "fromSide": "bottom", "toSide": "top",
                          "label": "needs"})
        if previous:                              # keeps the declared order exactly
            edges.append({"id": f"{node_id}-after", "fromNode": previous, "toNode": node_id,
                          "fromSide": "bottom", "toSide": "top", "label": "then"})
        previous = node_id
    if len(nodes) > 1:
        edges.insert(0, {"id": f"{base}-start", "fromNode": base, "toNode": nodes[1]["id"],
                         "fromSide": "bottom", "toSide": "top"})
    return {"nodes": nodes, "edges": edges}
