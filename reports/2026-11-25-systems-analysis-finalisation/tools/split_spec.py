"""Split an oversized spec into a parent and a child joined by a reference (PLAN.md 2.3, size rule).

    from tools.split_spec import load, save, extract, renumber

`extract` moves a set of nodes into a new child spec. The set must have exactly one entry node.
Every edge leaving the set becomes an end of the child, with the outcome given for its target. In the
parent, one `ref` node takes the set's place, with one way out per outcome. `renumber` then numbers the
main path's activities and references 1..n, and each extension by the step it belongs to, the way
render_spec.cross_check reads them. Labels and lanes are not changed.
"""
from __future__ import annotations

import copy
import re
import string
from collections import defaultdict
from pathlib import Path

import yaml

HEAD_KEYS = ("diagram", "use_case", "status", "supersedes", "kind", "title")
NUMBERED = ("activity", "ref")


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def save(spec: dict, path: Path, comment: str = "") -> None:
    ordered = {k: spec[k] for k in HEAD_KEYS if k in spec} | {k: v for k, v in spec.items() if k not in HEAD_KEYS}
    text = yaml.safe_dump(ordered, sort_keys=False, allow_unicode=True, width=120)
    path.write_text((f"# {comment}\n" if comment else "") + text, encoding="utf-8")


def main_path(spec: dict) -> list[str]:
    outs = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
    cur = next(n["id"] for n in spec["nodes"] if n["kind"] == "start")
    trail = [cur]
    while outs[cur]:
        nxt = next((e for e in outs[cur] if not e.get("ext")), outs[cur][0])["to"]
        if nxt in trail:
            break
        trail.append(nxt)
        cur = nxt
    return trail


def extract(spec: dict, child_id: str, members: list[str], outcomes: dict[str, str], *, title: str,
            use_case: str, ref_label: str, ref_lane: str = "Core", end_labels: dict[str, str] | None = None,
            success: str = "success") -> tuple[dict, dict]:
    """Return (parent, child). `outcomes` maps each exit target (a parent node id) to an outcome name."""
    parent = copy.deepcopy(spec)
    inside = set(members)
    nodes = {n["id"]: n for n in parent["nodes"]}
    entering = [e for e in parent["edges"] if e["to"] in inside and e["from"] not in inside]
    entries = {e["to"] for e in entering}
    if len(entries) != 1:
        raise ValueError(f"{child_id}: the set needs exactly one entry node, found {sorted(entries)}")
    entry = entries.pop()
    leaving = [e for e in parent["edges"] if e["from"] in inside and e["to"] not in inside]
    targets = {e["to"] for e in leaving}
    if set(outcomes) != targets:
        raise ValueError(f"{child_id}: outcomes must name exactly the exit targets {sorted(targets)}; "
                         f"got {sorted(outcomes)}")
    if len(set(outcomes.values())) != len(outcomes):
        raise ValueError(f"{child_id}: two exit targets share an outcome; the parent could not tell them apart")
    if success not in outcomes.values():
        raise ValueError(f"{child_id}: one exit must be the {success!r} outcome")
    end_labels = end_labels or {}

    child_nodes = [{"id": "s", "kind": "start", "label": "start"}]
    child_nodes += [copy.deepcopy(nodes[m]) for m in members]
    end_of = {}
    for target, result in outcomes.items():
        eid = "e_" + re.sub(r"\W+", "_", result)
        end_of[target] = eid
        child_nodes.append({"id": eid, "kind": "end", "outcome": result,
                            "label": end_labels.get(result, f"{result}: back to the caller")})
    child_edges = [{"from": "s", "to": entry}]
    for e in parent["edges"]:
        if e["from"] in inside:
            new = copy.deepcopy(e)
            if e["to"] not in inside:
                new["to"] = end_of[e["to"]]
            child_edges.append(new)
    # Several ways into the success end would each count as a success path; meet them first.
    success_end = end_of[next(t for t, r in outcomes.items() if r == success)]
    to_success = [e for e in child_edges if e["to"] == success_end]
    if len(to_success) > 1:
        merge = {"id": "m_" + success, "kind": "merge", "lane": nodes[to_success[0]["from"]]["lane"],
                 "label": "the ways to " + end_labels.get(success, success) + " meet"}
        child_nodes.insert(-len(outcomes), merge)
        for e in to_success:
            e["to"] = merge["id"]
        child_edges.append({"from": merge["id"], "to": success_end})
    lanes = [lane for lane in parent["lanes"] if any(n.get("lane") == lane for n in child_nodes)]
    child = {"diagram": child_id, "use_case": use_case, "status": parent.get("status"), "kind": "activity",
             "title": title, "lanes": lanes, "nodes": child_nodes, "edges": child_edges}

    ref_id = "ref_" + re.sub(r"\W+", "_", child_id)
    ref = {"id": ref_id, "kind": "ref", "lane": ref_lane, "use_case": child_id, "label": ref_label}
    kept = [n for n in parent["nodes"] if n["id"] not in inside]
    at = next(i for i, n in enumerate(parent["nodes"]) if n["id"] == entry)
    before = [n for n in parent["nodes"][:at] if n["id"] not in inside]
    parent["nodes"] = before + [ref] + [n for n in kept if n not in before]
    edges = []
    for e in parent["edges"]:
        if e["from"] in inside and e["to"] in inside:
            continue
        if e["from"] in inside:
            continue                                    # replaced by the ref's ways out
        new = copy.deepcopy(e)
        if new["to"] in inside:
            new["to"] = ref_id
        edges.append(new)
    ordered = sorted(outcomes.items(), key=lambda kv: kv[1] != success)
    for target, result in ordered:
        edges.append({"from": ref_id, "to": target, "guard": result,
                      **({} if result == success else {"ext": "?"})})
    parent["edges"] = edges
    parent["lanes"] = [lane for lane in parent["lanes"] if any(n.get("lane") == lane for n in parent["nodes"])]
    return parent, child


def renumber(spec: dict) -> dict:
    """Number the main path's activities and references; number each extension by its step."""
    spec = copy.deepcopy(spec)
    nodes = {n["id"]: n for n in spec["nodes"]}
    for n in spec["nodes"]:
        n.pop("step", None)
    happy = main_path(spec)
    step = 0
    for nid in happy:
        if nodes[nid]["kind"] in NUMBERED:
            step += 1
            nodes[nid]["step"] = step
    preds = defaultdict(list)
    for e in spec["edges"]:
        preds[e["to"]].append(e["from"])
    on_main = set(happy)
    outs = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
    for nid in happy:
        if nodes[nid]["kind"] not in ("decision", "ref") or not outs[nid]:
            continue
        followed = next((e for e in outs[nid] if not e.get("ext")), outs[nid][0])
        for e in outs[nid]:
            if e is not followed and not e.get("ext"):
                e["ext"] = "?"                    # every other way out of a main-path decision is an extension
    for e in spec["edges"]:
        if e["from"] not in on_main and e.get("ext") and not str(e["ext"]).startswith("*") \
                and not any(nodes[p].get("step") for p in preds[e["from"]]):
            del e["ext"]                          # inside an extension: part of that extension's text
    used = defaultdict(set)
    for e in spec["edges"]:
        if e.get("ext") and not str(e["ext"]).startswith("*"):
            d = e["from"]
            if d in happy:
                i = happy.index(d)
                after = next((nodes[n].get("step") for n in happy[i:] if nodes[n].get("step")), None)
                before = next((nodes[n].get("step") for n in reversed(happy[:i]) if nodes[n].get("step")), None)
                number = after or before or 1
            else:
                number = nodes[preds[d][0]].get("step") or 1
            letter = next(c for c in string.ascii_lowercase if c not in used[number])
            used[number].add(letter)
            e["ext"] = f"{number}{letter}"
    return spec
