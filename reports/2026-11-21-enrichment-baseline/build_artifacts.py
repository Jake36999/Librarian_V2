"""Render this analysis model through the accepted renderer and existing safe canvas service.

This script authors report artifacts only. It implements no Librarian process or runtime schema.
Run from any directory with the repository's Python environment.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict, deque
from functools import lru_cache
from pathlib import Path

from resource_librarian.canvas import service
from resource_librarian.canvas.document import (content_revision, load_document, proposal_hash,
                                               validate_document)


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
REFERENCE = REPO / "reports/2026-11-20-workflow-map/examples/ingestion"
# Actor assignments in the first saved baseline, before the Owner's responsibility correction.
# Saved actor_lane metadata takes precedence after the first deliberate reassignment.
INITIAL_ACTORS = {name: "Core" for name in (
    "a23", "a25", "a33", "revisionapprove", "dprosebound", "paused", "escalation")}
# Authoring hints for new cards only: (existing anchor id, vertical offset). They never move
# existing cards or become fields in the behavioral specification.
NEW_CARD_HINTS = {
    "capturedescribe": ("a10", 0),
    "dagentingestion": ("dsourceapprove", 0),
    "drevisionintent": ("revisionapprove", 200),
    "dacceptintent": ("a33", 0),
    "conversionplan": ("dp", 400),
    "conversionwork": ("a19", 400),
    "conversionreview": ("dp", 1000),
    "conversioncheck": ("a23", 0),
    "dconversion": ("a24", 0),
    "conversiongap": ("a25", 0),
}
# This one correction was explicitly scoped: the reassigned card would otherwise cover a18.
REASSIGNMENT_Y_OFFSETS = {"revisionapprove": -200}


def renderer():
    location = REFERENCE / "render_spec.py"
    definition = importlib.util.spec_from_file_location("accepted_activity_renderer", location)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def routing():
    definition = importlib.util.spec_from_file_location("report_edge_routing", HERE / "edge_routing.py")
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


def attach_sides(edge, first, last, *, on_main=False):
    """Initialize native sides; complete-field obstacle selection follows placement."""
    first_side, last_side = routing().preferred_sides(first, last)
    edge.update(fromSide=first_side, toSide=last_side)


def checks(spec: dict, render, reference_library=None) -> tuple[list[str], list[dict]]:
    problems = render.validate(spec)
    ids = [node["id"] for node in spec["nodes"]]
    problems += [f"duplicate node id: {name}" for name, count in Counter(ids).items() if count != 1]
    extension_ids = [edge["ext"] for edge in spec["edges"] if edge.get("ext")]
    problems += [f"duplicate extension: {name}" for name, count in Counter(extension_ids).items() if count != 1]
    numbered = [node["step"] for node in spec["nodes"] if node.get("step")]
    if sorted(numbered) != list(range(1, len(numbered) + 1)):
        problems.append("main scenario steps must be consecutive and unique")
    main = render.main_path(spec)
    for node in spec["nodes"]:
        if node.get("step") and node["id"] not in main:
            problems.append(f"numbered scenario step outside main path: {node['id']}")
    if problems:
        return problems, []
    scenarios = render.paths(spec)
    problems += render.cross_check(spec, scenarios)
    problems += render.check_references(spec, reference_library or {spec["diagram"]: spec})
    return problems, scenarios


def managed_canvas(spec: dict, render) -> dict:
    generated = render.canvas(spec)
    by_id = {node["id"]: node for node in generated["nodes"]}
    # Reserve a complete vertical band for each departure before placing the next
    # main-flow card. Main-first packing hid early conversion/recovery cards among
    # later stages in the same actor column, even though it avoided overlaps.
    main = render.main_path(spec)
    on_main = set(main)
    main_index = {name: index for index, name in enumerate(main)}
    side = [node["id"] for node in spec["nodes"] if node["id"] not in on_main]
    incoming = Counter({name: 0 for name in side})
    children = defaultdict(list)
    predecessors = defaultdict(list)
    entries = defaultdict(set)
    for edge in spec["edges"]:
        source, target = edge["from"], edge["to"]
        if target in on_main:
            continue  # a main continuation or explicit rejoin, not a side-band dependency
        predecessors[target].append(source)
        if source in on_main:
            entries[target].add(main_index[source])
        else:
            children[source].append(target)
            incoming[target] += 1
    ready = deque(name for name in side if incoming[name] == 0)
    order = []
    while ready:
        name = ready.popleft()
        order.append(name)
        for child in children[name]:
            entries[child].update(entries[name])
            incoming[child] -= 1
            if incoming[child] == 0:
                ready.append(child)
    if len(order) != len(side):
        raise ValueError("off-main layout cycle: express its bound and authorized rejoin")
    # A many-to-one sink belongs to the latest band that can enter it. Thus shared
    # failed-item/ticket blocks remain shared near final accounting instead of
    # dragging every local predecessor into that late block. A single-entry local
    # chain (conversion, raw fallback, cancellation) stays at its own departure.
    anchors = {}
    bands = defaultdict(list)
    for name in order:
        if not entries[name]:
            raise ValueError(f"off-main card has no main-flow departure: {name}")
        anchors[name] = max(entries[name])
        bands[anchors[name]].append(name)
    occupied = defaultdict(list)
    cursor = 140
    for index, node_id in enumerate(main):
        card = by_id[node_id]
        card["y"] = cursor
        occupied[card["x"]].append((cursor, cursor + card["height"]))
        next_cursor = cursor + 200
        for name in bands[index]:
            branch = by_id[name]
            # Parents in earlier bands are already above this one; all parents in
            # the same band precede the card in its topological order.
            position = max([cursor + 200]
                           + [by_id[parent]["y"] + 200 for parent in predecessors[name]])
            while any(position < end + 20 and position + branch["height"] + 20 > start
                      for start, end in occupied[branch["x"]]):
                position += 200
            branch["y"] = position
            occupied[branch["x"]].append((position, position + branch["height"]))
            next_cursor = max(next_cursor, position + 200)
        cursor = next_cursor
    if any(by_id[last]["y"] <= by_id[first]["y"] for first, last in zip(main, main[1:])):
        raise ValueError("main-flow cards must advance through their stage bands")
    if any(by_id[child]["y"] <= by_id[parent]["y"]
           for child in side for parent in predecessors[child]):
        raise ValueError("a side-band dependency moved upwards")
    bottom = max(node["y"] + node["height"] for node in generated["nodes"] if node["type"] == "text") + 100
    for node in generated["nodes"]:
        if node["type"] == "group":
            node["height"] = bottom - node["y"]
    for edge in generated["edges"]:
        first, last = by_id[edge["fromNode"]], by_id[edge["toNode"]]
        # Match the accepted canvas's explicit attachment sides. Preserve downward same-lane
        # flow and cross-lane hand-offs, including upward rejoin edges.
        attach_sides(edge, first, last, on_main=(edge["fromNode"], edge["toNode"]) in set(zip(main, main[1:])))
        edge["id"] = service.MANAGED_PREFIX + edge["id"]
        edge["fromNode"] = service.MANAGED_PREFIX + edge["fromNode"]
        edge["toNode"] = service.MANAGED_PREFIX + edge["toNode"]
    for node in generated["nodes"]:
        node["id"] = service.MANAGED_PREFIX + node["id"]
    routing().reroute(generated, strict=False)
    return generated


def overlaps(canvas: dict) -> list[list[str]]:
    cards = [node for node in canvas["nodes"] if node["type"] == "text"]
    collisions = []
    for index, first in enumerate(cards):
        for last in cards[index + 1:]:
            if (max(first["x"], last["x"]) < min(first["x"] + first["width"], last["x"] + last["width"])
                    and max(first["y"], last["y"]) < min(first["y"] + first["height"], last["y"] + last["height"])):
                collisions.append([first["id"], last["id"]])
    return collisions


def actor_preview(target, generated, model, placement_hints=None, *, reflow_generated=False,
                  reroute_generated=False, validation_path=None):
    """Preview declared actor changes without relaying out the Owner's saved canvas."""
    original_revision = content_revision(target)
    previous = load_document(target)
    if (reflow_generated or reroute_generated) and previous["nodes"]:
        receipt_path = validation_path or target.parent / "validation.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if proposal_hash(previous) != receipt.get("canvas_revision"):
            raise service.CanvasConflict("saved canvas differs from its last validated generation; preserve Owner edits before geometry/routing changes")
    prior_nodes = {node["id"]: node for node in previous["nodes"]}
    prior_groups = {node["label"]: node for node in previous["nodes"] if node["type"] == "group"}
    prior_edges = defaultdict(list)
    for edge in previous["edges"]:
        if edge["id"].startswith(service.MANAGED_PREFIX):
            prior_edges[(edge["fromNode"], edge["toNode"])].append(edge)

    generated = copy.deepcopy(generated)
    generated_groups = {node["label"]: node for node in generated["nodes"] if node["type"] == "group"}
    roles = {service.MANAGED_PREFIX + node["id"]: node["lane"]
             for node in model["nodes"] if node.get("lane")}
    for node in generated["nodes"]:
        if node["id"] not in roles:
            continue
        metadata = (prior_nodes.get(node["id"]) or {}).get("librarian", {})
        proposed_metadata = node.get("librarian", {})
        if not isinstance(metadata, dict) or not isinstance(proposed_metadata, dict):
            raise service.CanvasConflict(f"{node['id']} has unknown authoring metadata; preserve it for review")
        node["librarian"] = {**metadata, **proposed_metadata, "actor_lane": roles[node["id"]]}

    preview = service.preview(target, generated, profile=None)
    if preview["base_revision"] != original_revision:
        raise service.CanvasConflict("the canvas changed while its actor assignments were read; preview again")
    candidate = preview["proposal"]
    nodes = {node["id"]: node for node in candidate["nodes"]}
    groups = {node["label"]: node for node in candidate["nodes"] if node["type"] == "group"}
    added = set(preview["changes"]["added"])
    moved = set()
    changes = []

    def intersects(first, last, gap=0):
        return (max(first["x"], last["x"]) < min(first["x"] + first["width"], last["x"] + last["width"])
                and max(first["y"], last["y"]) < min(first["y"] + first["height"] + gap,
                                                           last["y"] + last["height"] + gap))

    for node_id, destination in roles.items():
        before = prior_nodes.get(node_id)
        if before is None:
            continue
        metadata = before.get("librarian", {})
        previous_role = metadata.get("actor_lane") or INITIAL_ACTORS.get(
            node_id.removeprefix(service.MANAGED_PREFIX), destination)
        if previous_role == destination:
            continue
        source_group = prior_groups.get(previous_role)
        target_group = groups.get(destination)
        if source_group is None or target_group is None:
            raise service.CanvasConflict(f"{node_id} names an unknown old or new actor lane; preserve it for review")
        card = nodes[node_id]
        center = card["x"] + card["width"] / 2
        if source_group["x"] <= center <= source_group["x"] + source_group["width"]:
            card["x"] += target_group["x"] - source_group["x"]
        elif not target_group["x"] <= center <= target_group["x"] + target_group["width"]:
            raise service.CanvasConflict(f"{node_id} is outside its old and new lanes; preserve its position for review")
        others = [node for node in candidate["nodes"] if node["type"] == "text"
                  and node["id"] != node_id and node["id"] not in added]
        if any(intersects(card, other) for other in others):
            offset = REASSIGNMENT_Y_OFFSETS.get(node_id.removeprefix(service.MANAGED_PREFIX))
            if offset is None:
                raise service.CanvasConflict(f"{node_id} would overlap an existing card after reassignment; inspect it")
            card["y"] += offset
            if any(intersects(card, other) for other in others):
                raise service.CanvasConflict(f"{node_id}'s explicit row adjustment still overlaps an existing card")
        moved.add(node_id)
        changes.append({"node": node_id, "from": previous_role, "to": destination,
                        "old_x": before["x"], "new_x": card["x"],
                        "old_y": before["y"], "new_y": card["y"],
                        "y_preserved": card["y"] == before["y"],
                        "intentional_y_adjustment": card["y"] - before["y"]})

    relayout = []
    if reflow_generated:
        # The preceding receipt check proves there are no unreviewed Owner edits. Only
        # generated geometry changes; the service merge still retains custom fields.
        fresh_nodes = {node["id"]: node for node in generated["nodes"]}
        for node_id, fresh in fresh_nodes.items():
            card = nodes[node_id]
            before = {key: card[key] for key in ("x", "y", "width", "height")}
            for key in before:
                card[key] = fresh[key]
            after = {key: card[key] for key in before}
            if before != after:
                relayout.append({"node": node_id, "before": before, "after": after})
                moved.add(node_id)
    hints = {**NEW_CARD_HINTS, **(placement_hints or {})}
    parents = defaultdict(list)
    for edge in generated["edges"]:
        parents[edge["toNode"]].append(edge["fromNode"])
    # A newly created canvas already has the renderer's checked geometry. On subsequent
    # renders, place only added cards relative to the saved anchors, never the fresh layout.
    pending = [node["id"] for node in candidate["nodes"]
               if prior_nodes and not reflow_generated and node["id"] in added and node["type"] == "text"]
    while pending:
        progress = False
        for node_id in list(pending):
            card = nodes[node_id]
            name = node_id.removeprefix(service.MANAGED_PREFIX)
            hint = hints.get(name)
            if hint:
                anchor, offset = hint
                anchor_id = anchor if anchor.startswith(service.MANAGED_PREFIX) else service.MANAGED_PREFIX + anchor
                if anchor_id not in nodes:
                    raise service.CanvasConflict(f"{node_id}'s placement anchor {anchor_id} is missing")
                if anchor_id in pending:
                    continue
                card["y"] = nodes[anchor_id]["y"] + offset
            else:
                incoming = parents.get(node_id, [])
                if any(parent in pending for parent in incoming):
                    continue
                if incoming:
                    card["y"] = max(nodes[parent]["y"] + 200 for parent in incoming)
            if node_id in roles:
                destination = roles[node_id]
                card["x"] += groups[destination]["x"] - generated_groups[destination]["x"]
            others = [node for node in candidate["nodes"] if node["type"] == "text"
                      and node["id"] != node_id and node["id"] not in pending]
            while any(intersects(card, other, gap=20) for other in others):
                card["y"] += 200
            pending.remove(node_id)
            progress = True
        if not progress:
            raise service.CanvasConflict("new cards have cyclic placement dependencies; supply explicit anchor hints")

    group_extensions = []
    for node_id in added:
        if node_id not in roles or nodes[node_id]["type"] != "text":
            continue
        group = groups[roles[node_id]]
        needed_height = nodes[node_id]["y"] + nodes[node_id]["height"] + 100 - group["y"]
        if needed_height > group["height"]:
            group_extensions.append({"group": group["id"], "old_height": group["height"],
                                     "new_height": needed_height})
            group["height"] = needed_height

    touched = moved | added | ({node["id"] for node in generated["nodes"]} if reflow_generated else set())
    main = renderer().main_path(model)
    main_pairs = {(service.MANAGED_PREFIX + a, service.MANAGED_PREFIX + b) for a, b in zip(main, main[1:])}
    for edge in candidate["edges"]:
        if not edge["id"].startswith(service.MANAGED_PREFIX):
            continue
        previous_matches = prior_edges.get((edge["fromNode"], edge["toNode"]), [])
        exact = [old for old in previous_matches if old.get("label") == edge.get("label")]
        old = exact[0] if len(exact) == 1 else previous_matches[0] if len(previous_matches) == 1 else None
        if old:
            for key, value in old.items():
                if key not in {"id", "fromNode", "toNode", "label", "color"}:
                    edge[key] = copy.deepcopy(value)
        if edge["fromNode"] not in touched and edge["toNode"] not in touched:
            continue
        first, last = nodes[edge["fromNode"]], nodes[edge["toNode"]]
        attach_sides(edge, first, last, on_main=(edge["fromNode"], edge["toNode"]) in main_pairs)
    routing_changes = {}
    if reroute_generated:
        try:
            routing_changes = routing().clear_layout(
                candidate, node_ids={node["id"] for node in generated["nodes"]},
                edge_ids={edge["id"] for edge in generated["edges"]})
        except ValueError as exc:
            raise service.CanvasConflict(str(exc)) from exc
    elif touched:
        routing_changes = routing().reroute(
            candidate, edge_ids={edge["id"] for edge in candidate["edges"]
                                 if edge["id"].startswith(service.MANAGED_PREFIX)
                                 and (edge["fromNode"] in touched or edge["toNode"] in touched)},
            strict=False)
    diagnostics = [item for item in validate_document(candidate) if item.get("severity") != "warning"]
    if diagnostics or overlaps(candidate):
        raise service.CanvasConflict(f"inspect the canvas before writing: document={diagnostics}, overlaps={overlaps(candidate)}")
    preview["changes"]["actor_reassignments"] = changes
    preview["changes"]["group_extensions"] = group_extensions
    preview["changes"]["generated_relayout"] = relayout
    preview["changes"]["generated_routing"] = routing_changes
    # This final authoring preview covers only explicit lane edits/new cards. Commit still
    # checks the originally read base revision and the hash of this complete proposal.
    preview["proposal_hash"] = proposal_hash(candidate)
    return preview


def main(*, reflow_generated=False) -> int:
    render = renderer()
    source = HERE / "enrichment-cycle.spec.yaml"
    spec = render.load(source)
    spec["_file"] = source.name
    problems, scenarios = checks(spec, render)
    if problems:
        print(json.dumps({"problems": problems}, indent=2))
        return 1

    tree, tests = render.tree_and_tests(spec, scenarios)
    actors = [lane for lane in spec["lanes"] if lane != "Core"]
    use_case = ["flowchart LR", '  subgraph librarian["Librarian"]',
                '    goal(["Enrich sources and account for the required outcomes"])', "  end"]
    for index, actor in enumerate(actors):
        use_case += [f'  actor{index}(["{actor}"]) --- goal']
    text = "\n".join([
        "<!-- generated by build_artifacts.py using the accepted render_spec.py; edit the spec -->",
        "# Enrichment cycle views",
        "",
        "**Status:** behavioural analysis for review. Existing operations and planned coordination are distinguished in [model notes](model-notes.md) and the [requirements baseline](requirements-evidence.md).",
        "",
        "These are extension scenarios from the accepted prototype's tree logic: the main success scenario plus departures and rejoins. They are not a Cartesian enumeration of repeated items, all combined failures, or an executable proof of the process. Rejoins remain conditional on the recorded item state and authority. The coverage table and source tests retain those conditions.",
        "",
        "## Validation", "", "No structural problems or cross-view flags.", "",
        "## Use case diagram", "", "```mermaid", "\n".join(use_case), "```", "",
        "## Activity diagram", "", "```mermaid", render.mermaid(spec), "```", "",
        "## Written use case", "", "The [nine-field use-case description](model-notes.md#use-case-description) defines the actors, entry conditions, guarantee and open implementation questions.", "",
        render.written_use_case(spec, scenarios), "",
        "## Lane load", "", render.lane_load(spec, scenarios), "",
        f"## Decision tree with {len(scenarios)} extension scenarios", "", tree, "",
        "## Scenario test table", "", tests, "",
        "## Cross view check", "", "No flags.", "",
    ])
    canvas = managed_canvas(spec, render)
    collisions = overlaps(canvas)
    if collisions:
        raise ValueError(f"overlapping cards: {collisions}")
    target = HERE / "enrichment-cycle.canvas"
    previewed = actor_preview(target, canvas, spec, reflow_generated=reflow_generated)
    result = service.commit(target, previewed)
    (HERE / "enrichment-cycle.views.md").write_text(text, encoding="utf-8")
    result_canvas = json.loads(target.read_text(encoding="utf-8"))
    # Round-trip inspection after the safe commit, including generated ownership and edge geometry.
    assert not overlaps(result_canvas)
    assert all(node["id"].startswith(service.MANAGED_PREFIX) for node in canvas["nodes"])
    assert all("fromSide" in edge and "toSide" in edge for edge in result_canvas["edges"]
               if edge["id"].startswith(service.MANAGED_PREFIX))
    receipt = {
        "source": source.name,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "renderer": str(REFERENCE.relative_to(REPO) / "render_spec.py"),
        "renderer_sha256": hashlib.sha256((REFERENCE / "render_spec.py").read_bytes()).hexdigest(),
        "structural_problems": [],
        "cross_view_flags": [],
        "numbered_main_steps": len([node for node in spec["nodes"] if node.get("step")]),
        "extension_scenarios": len(scenarios),
        "nodes": len(result_canvas["nodes"]),
        "edges": len(result_canvas["edges"]),
        "overlapping_cards": [],
        "actor_reassignments": previewed["changes"]["actor_reassignments"],
        "group_extensions": previewed["changes"]["group_extensions"],
        "generated_relayout": previewed["changes"]["generated_relayout"],
        "ownership_rule": "agents own interpretation, proposals and semantic judgement; Core performs declared scripts and mechanical checks/storage/dispatch",
        "layout": "accepted actor columns and card dimensions; main flow downward, branches beside the flow, explicit edge attachment sides",
        "canvas_revision": result["revision"],
        "canvas_service": "preview then revision/hash-checked commit, profile=None",
        "scope": "analysis artifact checks; not live pipeline, model qualification or runtime readiness evidence",
    }
    (HERE / "validation.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reflow-generated", action="store_true",
                        help="reflow modeled geometry only when the saved canvas matches its last validation receipt")
    raise SystemExit(main(reflow_generated=parser.parse_args().reflow_generated))
