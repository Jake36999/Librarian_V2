"""Safely regenerate corrected report canvases; product code is unchanged.

Default: preview both corrected ingestion canvases without writing anything.
Use ``--commit`` only after the corrected specifications are ready. Optional ``--png``
adds deterministic reading aids. The unmodified accepted render_spec.py supplies views.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
BASELINE = REPO / "reports/2026-11-21-enrichment-baseline"
FOCUSED = REPO / "reports/2026-11-22-proposed-tobe-enrichment"
sys.path.insert(0, str(REPO / "src"))
from resource_librarian.canvas import service
from resource_librarian.canvas.document import content_revision, load_document, proposal_hash, validate_document

PREFIX = service.MANAGED_PREFIX
AUTHORING = "report_ingestion_corrections"
ORIGINAL_CANVAS_CHECKSUMS = {"ingestion":"7c1e4977f57d05e3fde0f7d085c8ecfec335e2cfe92f78907f0e8268d9d16870","ingestion-tobe":"371e2fae23c4f4f2cfbf27eb34007ebc48b706f39b1e3d3c2fbb84ec6fce926f"}


def module_at(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


def lane_name(name, stem):
    aliases = {"Helper (tier 2)": "Clerk (tier 2)",
               "Clerk (tier 3)": "Model worker (legacy transport)" if stem == "ingestion" else "Scribe (tier 3)"}
    if stem == "ingestion":
        aliases["Clerk (tier 2)"] = "Model worker (legacy transport)"
    return aliases.get(name, name)


def lane_id(name):
    return PREFIX + "lane-" + re.sub(r"\W+", "-", name)


def intersects(first, last, gap=0):
    return (max(first["x"], last["x"]) < min(first["x"] + first["width"], last["x"] + last["width"])
            and max(first["y"], last["y"]) < min(first["y"] + first["height"] + gap,
                                                       last["y"] + last["height"] + gap))


def edge_sides(edge, nodes, main_pairs=()):
    first, last = nodes[edge["fromNode"]], nodes[edge["toNode"]]
    if first["x"] == last["x"]:
        down = last["y"] > first["y"]
        edge.update(fromSide="bottom" if down else "top", toSide="top" if down else "bottom")
    else:
        right = last["x"] > first["x"]
        edge.update(fromSide="right" if right else "left", toSide="left" if right else "right")


def forward_graph(model, render):
    """Return layout dependencies, excluding explicit returns to the main flow."""
    main = render.main_path(model)
    positions = {name: index for index, name in enumerate(main)}
    parents, children = defaultdict(list), defaultdict(list)
    incoming = Counter({node["id"]: 0 for node in model["nodes"]})
    for edge in model["edges"]:
        source, target = edge["from"], edge["to"]
        if target in positions and (source not in positions or positions[target] <= positions[source]):
            continue
        parents[target].append(source)
        children[source].append(target)
        incoming[target] += 1
    pending = deque(name for name, degree in incoming.items() if not degree)
    order = []
    while pending:
        name = pending.popleft()
        order.append(name)
        for target in children[name]:
            incoming[target] -= 1
            if not incoming[target]:
                pending.append(target)
    if len(order) != len(model["nodes"]):
        raise ValueError("off-main cycle needs an explicit bounded rejoin before layout")
    return main, parents, children, order


def verify_reflow_base(previous, target, stem):
    """Permit reflow only from the original or latest validated saved generation."""
    if not previous.get(AUTHORING):
        checksum = hashlib.sha256(json.dumps(previous, sort_keys=True, ensure_ascii=False,
                                              separators=(",", ":")).encode("utf-8")).hexdigest()
        if checksum != ORIGINAL_CANVAS_CHECKSUMS[stem]:
            raise service.CanvasConflict("initial generated-card reflow requires the verified original canvas; "
                                         "unreviewed Owner changes are preserved for review")
        return {"mode": "initial_prototype", "checksum": checksum}
    receipt_path = Path(target).parent / f"{stem}.correction-validation.json"
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise service.CanvasConflict("generated-card reflow requires the latest saved validation receipt") from exc
    recorded_revision = receipt.get("commit", {}).get("revision")
    recorded_proposal = receipt.get("proposal_hash")
    if recorded_revision and recorded_proposal and recorded_revision != recorded_proposal:
        raise service.CanvasConflict("latest validation receipt has inconsistent committed/proposal revisions")
    expected = recorded_revision or recorded_proposal
    observed = proposal_hash(previous)
    if not expected or observed != expected:
        raise service.CanvasConflict("canvas differs from its latest validated generation; "
                                     "unreviewed Owner changes are preserved for review")
    return {"mode": "validated_generation", "revision": observed, "receipt": str(receipt_path)}


def correction_preview(target, generated, model, render, layout, snapshot, stem, placement_hints=None,
                       reflow_generated=False, reroute_generated=False):
    """Adopt known old generated IDs while preserving everything else in the live file.

    service.preview supplies the real file revision guard. Its generic merge cannot
    identify this older renderer's unprefixed IDs, so this report-local final proposal
    uses the captured provenance set. No temporary rename or destructive regeneration
    of the Owner's file is involved.
    """
    original_revision = content_revision(target)
    previous = load_document(target)
    preview = service.preview(target, generated, adopt=True, profile=None)
    if preview["base_revision"] != original_revision:
        raise service.CanvasConflict("canvas changed while reading its authoring state")
    saved = previous.get(AUTHORING, {})
    if not isinstance(saved, dict):
        raise service.CanvasConflict(f"unknown {AUTHORING} metadata; preserve it for review")
    reflow_base = verify_reflow_base(previous, target, stem) if reflow_generated or reroute_generated else None
    prior = {node["id"]: node for node in previous["nodes"]}
    prior_groups = {node.get("label"): node for node in previous["nodes"] if node["type"] == "group"}
    roles = {node["id"]: node.get("lane") for node in model["nodes"]}
    old_roles = {**snapshot["roles"], **saved.get("roles", {})}
    known_nodes = set(saved.get("managed_nodes", []))
    known_edges = set(saved.get("managed_edges", []))
    id_map = {}
    for name in snapshot["nodes"] + ["title"]:
        if name in prior:
            known_nodes.add(name)
            id_map[name] = PREFIX + name
    for name, lane in snapshot["groups"].items():
        if name in prior:
            known_nodes.add(name)
            id_map[name] = lane_id(lane_name(lane, stem))
    for name in known_nodes:
        id_map.setdefault(name, name)
    # An already-adopted historical lane can be clarified without appending a new
    # column or discarding its saved geometry and custom fields.
    for name in known_nodes:
        old = prior.get(name, {})
        if old.get("type") == "group":
            renamed = lane_name(old.get("label"), stem)
            if renamed in model["lanes"] and renamed != old.get("label"):
                id_map[name] = lane_id(renamed)
    generated = copy.deepcopy(generated)
    generated_ids = {node["id"] for node in generated["nodes"]}
    # An unknown managed-looking ID is still Owner material. Never let a prefix
    # alone authorize deleting or replacing it.
    collisions = (set(prior) - known_nodes) & generated_ids
    if collisions:
        raise service.CanvasConflict(f"new generated IDs collide with unknown nodes: {sorted(collisions)}")
    for edge in previous["edges"]:
        pair = [edge["fromNode"], edge["toNode"]]
        if snapshot["edges"].get(edge["id"]) == pair:
            known_edges.add(edge["id"])
    manual_edges = [copy.deepcopy(edge) for edge in previous["edges"] if edge["id"] not in known_edges]
    retired = {name for name in known_nodes if id_map[name] not in generated_ids}
    # Owner edges to a retired card need an anchor. Preserve that card as manual
    # material rather than deleting the edge or producing a dangling reference.
    retained_anchors = {edge[end] for edge in manual_edges for end in ("fromNode", "toNode")
                        if edge[end] in retired}
    for name in retained_anchors:
        id_map[name] = name
    old_by_new = {id_map[name]: node for name, node in prior.items() if name in known_nodes and name not in retired}
    new_groups = {node["label"]: node for node in generated["nodes"] if node["type"] == "group"}
    right = max((node["x"] + node["width"] for node in prior_groups.values()), default=0)
    group_changes = []
    for label, group in new_groups.items():
        before = old_by_new.get(group["id"])
        if before is not None:
            for field in ("x", "y", "width", "height"):
                group[field] = before[field]
        elif prior:
            group["x"] = right + 20
            right = group["x"] + group["width"]
            group_changes.append({"group": group["id"], "reason": "new lane beside preserved columns", "x": group["x"]})
    final = copy.deepcopy(previous)
    final["nodes"] = [copy.deepcopy(node) for node in previous["nodes"]
                      if node["id"] not in known_nodes or node["id"] in retained_anchors]
    changes, added, reassigned, reflowed = [], set(), set(), set()
    for fresh in generated["nodes"]:
        before = old_by_new.get(fresh["id"])
        card = {**copy.deepcopy(before or {}), **fresh}
        if before:
            for field in ("x", "y", "width", "height"):
                card[field] = before[field]
            if fresh["type"] == "group":
                for field in ("x", "y", "width", "height"):
                    card[field] = fresh[field]
        else:
            added.add(card["id"])
        name = card["id"].removeprefix(PREFIX)
        if name in roles:
            if reflow_generated:
                card["y"] = fresh["y"]
                if before and card["y"] != before["y"]:
                    reflowed.add(card["id"])
                    provenance = ("original prototype geometry verified unchanged" if not saved
                                  else "latest validated saved generation verified unchanged")
                    changes.append({"node": card["id"], "reason": "restructured main/extension flow; " + provenance,
                                    "old_x": before["x"], "new_x": card["x"],
                                    "old_y": before["y"], "new_y": card["y"]})
            destination = roles[name] or ("Outcomes" if next(n for n in model["nodes"] if n["id"] == name)["kind"] == "end" else model["lanes"][0])
            metadata = card.get("librarian", {})
            if not isinstance(metadata, dict):
                raise service.CanvasConflict(f"unknown node metadata on {card['id']}")
            source = ((before or {}).get("librarian") or {}).get("actor_lane") or old_roles.get(name)
            if source is None:
                source = "Outcomes" if name != "s" else model["lanes"][0]
            target_group = new_groups[destination]
            if before:
                source_group = prior_groups.get(source) or prior_groups.get(lane_name(source, stem))
                if source_group is None:
                    raise service.CanvasConflict(f"missing previous actor column for {name}: {source}")
                normalized = lane_name(source, stem)
                if normalized != destination or source_group["x"] != target_group["x"]:
                    center = before["x"] + before["width"] / 2
                    if source_group["x"] <= center <= source_group["x"] + source_group["width"]:
                        card["x"] += target_group["x"] - source_group["x"]
                    elif not target_group["x"] <= center <= target_group["x"] + target_group["width"]:
                        raise service.CanvasConflict(f"{name} is outside old and new actor columns")
                    reassigned.add(card["id"])
                    changes.append({"node": card["id"], "reason": "actor reassignment", "from": source,
                                    "to": destination, "old_x": before["x"], "new_x": card["x"],
                                    "old_y": before["y"], "new_y": card["y"]})
            else:
                card["x"] = target_group["x"] + 20
            card["librarian"] = {**metadata, "actor_lane": destination}
        final["nodes"].append(card)
    nodes = {node["id"]: node for node in final["nodes"]}
    for change in changes:
        if change["reason"].startswith("restructured main/extension"):
            change["new_x"] = nodes[change["node"]]["x"]
    main, parents, children, order = forward_graph(model, render)

    def bounds(name, placed):
        lower = max([140] + [nodes[PREFIX + parent]["y"] + 200 for parent in parents[name]
                              if PREFIX + parent in placed])
        upper = float("inf")
        pending = deque((child, 1) for child in children[name])
        seen = {}
        while pending:
            child, distance = pending.popleft()
            if seen.get(child, 0) >= distance:
                continue
            seen[child] = distance
            if PREFIX + child in placed:
                upper = min(upper, nodes[PREFIX + child]["y"] - distance * 200)
            else:
                pending.extend((other, distance + 1) for other in children[child])
        return lower, upper

    # Every existing card is fixed except an explicitly reassigned card's minimal
    # collision correction. Apply all x translations before looking for collisions.
    fixed = set(nodes) - added
    for node_id in sorted(reassigned if not reflow_generated else []):
        card = nodes[node_id]
        others = [n for n in final["nodes"] if n["type"] != "group" and n["id"] != node_id and n["id"] not in added]
        if not any(intersects(card, other, 20) for other in others):
            continue
        name = node_id.removeprefix(PREFIX)
        low, high = bounds(name, fixed - {node_id})
        initial = card["y"]
        found = False
        for distance in range(1, 101):
            for offset in (-200 * distance, 200 * distance):
                candidate = initial + offset
                if candidate < low or candidate > high:
                    continue
                card["y"] = candidate
                if not any(intersects(card, other, 20) for other in others):
                    changes.append({"node": node_id, "reason": "scoped actor-lane collision correction",
                                    "old_y": initial, "new_y": candidate})
                    found = True
                    break
            if found:
                break
        if not found:
            raise service.CanvasConflict(f"{name}: reassignment has no clear row between preserved anchors {low}..{high}")
    placed = set(nodes) - added
    for name in (order if not reflow_generated else []):
        node_id = PREFIX + name
        if node_id not in added:
            continue
        card = nodes[node_id]
        low, high = bounds(name, placed)
        hint = (placement_hints or {}).get(name)
        if hint:
            anchor, offset = hint
            start = nodes[PREFIX + anchor]["y"] + offset
            if not low <= start <= high:
                raise service.CanvasConflict(f"{name}: authoring hint is outside preserved flow bounds {low}..{high}")
        else:
            start = low
        card["y"] = start
        others = [n for n in final["nodes"] if n["type"] != "group" and n["id"] in placed]
        while any(intersects(card, other, 20) for other in others):
            card["y"] += 200
        if card["y"] > high:
            raise service.CanvasConflict(f"{name}: new card has no clear row between preserved anchors {low}..{high}")
        placed.add(node_id)
        changes.append({"node": node_id, "reason": "new card beside preserved flow", "x": card["x"], "y": card["y"]})
    if reflow_generated:
        changes += [{"node": node_id, "reason": "new card in accepted downward-flow layout",
                     "x": nodes[node_id]["x"], "y": nodes[node_id]["y"]}
                    for node_id in sorted(added) if nodes[node_id]["type"] == "text"]
    # Keep old edge extension fields and sides when their hand-off has not moved.
    old_edges = defaultdict(list)
    for edge in previous["edges"]:
        if edge["id"] in known_edges:
            old_edges[(id_map.get(edge["fromNode"], edge["fromNode"]),
                       id_map.get(edge["toNode"], edge["toNode"]))].append(edge)
    final["edges"] = list(manual_edges)
    for edge in manual_edges:
        for end in ("fromNode", "toNode"):
            edge[end] = id_map.get(edge[end], edge[end])
    touched = added | reassigned | reflowed
    if reflow_generated:
        touched.update(node["id"] for node in generated["nodes"])
    main_pairs = {(PREFIX + a, PREFIX + b) for a, b in zip(main, main[1:])}
    managed_edges = []
    for index, edge in enumerate(generated["edges"]):
        source = model["edges"][index]
        identity = json.dumps([source["from"], source["to"], source.get("guard"), source.get("ext")], ensure_ascii=False)
        edge_id = PREFIX + "edge-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
        if any(e["id"] == edge_id for e in manual_edges):
            raise service.CanvasConflict(f"new edge ID collides with an Owner edge: {edge_id}")
        matches = old_edges[(edge["fromNode"], edge["toNode"])]
        old = matches.pop(0) if matches else None
        result = {**copy.deepcopy(old or {}), **edge, "id": edge_id}
        for field in ("label", "color"):
            if field not in edge:
                result.pop(field, None)
        if old and not ({edge["fromNode"], edge["toNode"]} & touched):
            for side in ("fromSide", "toSide"):
                if side in old:
                    result[side] = old[side]
        else:
            edge_sides(result, nodes, main_pairs)
        if not result.get("fromSide") or not result.get("toSide"):
            edge_sides(result, nodes, main_pairs)
        final["edges"].append(result)
        managed_edges.append(edge_id)
    routing_changes = {}
    if reroute_generated:
        try:
            routing_changes = layout.routing().clear_layout(
                final, node_ids=generated_ids, edge_ids=set(managed_edges))
        except ValueError as exc:
            raise service.CanvasConflict(str(exc)) from exc
    elif touched:
        routing_changes = layout.routing().reroute(
            final, edge_ids={edge["id"] for edge in final["edges"]
                             if edge["id"] in managed_edges and
                             (edge["fromNode"] in touched or edge["toNode"] in touched)},
            strict=False)
    # Extend only lane backgrounds whose existing extent cannot cover added cards.
    bottom = max(node["y"] + node["height"] for node in final["nodes"] if node["type"] != "group") + 100
    for node in final["nodes"]:
        if node["id"] in generated_ids and node["type"] == "group" and node["y"] + node["height"] < bottom:
            old_height = node["height"]
            node["height"] = bottom - node["y"]
            group_changes.append({"group": node["id"], "reason": "background extent for new cards",
                                  "old_height": old_height, "new_height": node["height"]})
    backwards = [[a, b] for a, b in zip(main, main[1:]) if nodes[PREFIX + b]["y"] <= nodes[PREFIX + a]["y"]]
    old_pairs = {frozenset(id_map.get(name, name) for name in pair) for pair in layout.overlaps(previous)}
    overlap_pairs = layout.overlaps(final)
    introduced_overlaps = [pair for pair in overlap_pairs if frozenset(pair) not in old_pairs]
    diagnostics = [item for item in validate_document(final) if item.get("severity") != "warning"]
    if backwards or introduced_overlaps or diagnostics:
        raise service.CanvasConflict(json.dumps({"backward_main_edges": backwards,
                                                "introduced_overlaps": introduced_overlaps, "document": diagnostics}))
    final[AUTHORING] = {**saved, "generator": "render_corrected.py", "spec": model.get("_file"),
                        "roles": roles, "managed_nodes": sorted(generated_ids), "managed_edges": managed_edges,
                        "initial_spec_sha256": snapshot["spec_sha256"]}
    preview["proposal"] = final
    preview["proposal_hash"] = proposal_hash(final)
    preview["changes"] = {"migrated_ids": {a: b for a, b in id_map.items() if a != b and a not in retired},
                           "retired_nodes_removed": sorted(retired - retained_anchors),
                           "retired_anchors_retained_for_owner_edges": sorted(retained_anchors),
                           "owner_nodes_preserved": len(previous["nodes"]) - len(known_nodes) + len(retained_anchors),
                           "owner_edges_preserved": len(manual_edges), "geometry_changes": changes,
                           "generated_reflow": reflow_generated,
                           "initial_generated_reflow": reflow_generated and not bool(saved),
                           "initial_semantic_checksum_verified": ORIGINAL_CANVAS_CHECKSUMS[stem] if reflow_generated and not saved else None,
                           "reflow_validation": reflow_base,
                           "generated_routing": routing_changes,
                           "group_changes": group_changes, "preexisting_overlaps_preserved": overlap_pairs}
    return preview
def spec_library(render):
    library, locations = {}, {}
    for directory in (HERE, BASELINE, FOCUSED):
        for path in sorted(directory.glob("*.spec.yaml")):
            model = render.load(path)
            key = model["diagram"]
            if key in library:
                raise ValueError(f"duplicate use-case identifier {key}: {locations[key]} and {path}")
            library[key], locations[key] = model, path
    return library, locations


def validate_model(model, render, library):
    problems = render.validate(model)
    for kind, values in (("node", [node["id"] for node in model["nodes"]]),
                         ("extension", [edge["ext"] for edge in model["edges"] if edge.get("ext")])):
        problems += [f"duplicate {kind}: {name}" for name, number in Counter(values).items() if number != 1]
    steps = [node["step"] for node in model["nodes"] if node.get("step")]
    if sorted(steps) != list(range(1, len(steps) + 1)):
        problems.append("numbered main steps must be consecutive and unique")
    if problems:
        raise ValueError(problems)
    main = render.main_path(model)
    problems += [f"numbered step outside main flow: {node['id']}"
                 for node in model["nodes"] if node.get("step") and node["id"] not in main]
    scenarios = render.paths(model)
    problems += render.cross_check(model, scenarios) + render.check_references(model, library)
    if problems:
        raise ValueError(problems)
    return scenarios


def views_for(model, render, scenarios, stem, locations):
    import os
    tree, tests = render.tree_and_tests(model, scenarios)
    if stem == "ingestion":
        status = ("Corrected current-state parent for the DataManagement ingestion example. "
                  "The child use case supplies the implemented per-item enrichment detail; "
                  "failure branches distinguish this cohort from wider-library evidence.")
    else:
        status = ("Corrected accepted to-be parent model. Planned Oracle, Doctor and tiered "
                  "orchestration remains proposed runtime behavior; the enrichment child is called explicitly.")
    references = []
    for key in sorted({node["use_case"] for node in model["nodes"] if node.get("use_case")}):
        path = locations[key]
        view_path = path.with_name(path.name.replace(".spec.yaml", ".views.md"))
        destination = Path(os.path.relpath(view_path, HERE)).as_posix()
        references.append(f"- [{key}: {library_title(path, render)}]({destination})")
    # This is the Librarian boundary. Core is an implementation participant;
    # it is never substituted for the full system in the goal diagram.
    diagram = ['flowchart LR', '  subgraph system["Librarian"]',
               '    goal(["' + model["title"].replace('"', "'") + '"])', '  end',
               '  owner(["Owner"]) --- goal', '  overseer(["Overseer / tier 0"]) --- goal']
    return "\n".join([
        f"<!-- generated by render_corrected.py from {model['_file']}; edit the spec -->",
        f"# {model['title']}", "", status, "",
        "These generated paths cover main and extension/rejoin scenarios, not every combination of repeated items or faults.", "",
        "## Validation", "", "No structural or cross-view/reference flags.", "",
        "## Use case diagram", "", "```mermaid", "\n".join(diagram), "```", "",
        "## Called use cases", "", *(references or ["None."]), "",
        "## Activity diagram", "", "```mermaid", render.mermaid(model), "```", "",
        "## Written use case", "", render.written_use_case(model, scenarios), "",
        "## Lane load", "", render.lane_load(model, scenarios), "",
        f"## Decision tree: {len(scenarios)} extension scenarios", "", tree, "",
        "## Scenario test table", "", tests, "",
        "## Cross-view check", "", "No flags.", "",
    ])


def library_title(path, render):
    return render.load(path)["title"]


def prepare(stem, render, layout, library, locations, hints=None, reflow_generated=False,
            reroute_generated=False):
    path = HERE / f"{stem}.spec.yaml"
    model = render.load(path)
    model["_file"] = path.name
    scenarios = validate_model(model, render, library)
    target = HERE / ("ingestion.canvas" if stem == "ingestion" else "accepted-ingestion-tobe.canvas")
    generated = layout.managed_canvas(model, render)
    preview = correction_preview(target, generated, model, render, layout, OLD_SNAPSHOTS[stem], stem, hints,
                                 reflow_generated=reflow_generated, reroute_generated=reroute_generated)
    receipt = {"status": "report model validation; not execution, runtime rollout or new Owner acceptance",
               "spec": str(path), "spec_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "canvas": str(target), "base_revision": preview["base_revision"],
               "proposal_hash": preview["proposal_hash"], "scenarios": len(scenarios),
               "structural_problems": [], "cross_view_reference_flags": [],
               "changes": preview["changes"], "write": "service.preview(profile=None, adopt=True), final provenance-aware proposal, guarded service.commit",
               "accepted_renderer_sha256": hashlib.sha256((HERE / "render_spec.py").read_bytes()).hexdigest()}
    return target, preview, views_for(model, render, scenarios, stem, locations), receipt


def reading_aids(canvas, stem, destination_dir=None):
    """Draw the reduced overview and readable detail without editing the canvas."""
    directory = Path(destination_dir) if destination_dir is not None else HERE
    raster = module_at("corrected_canvas_reading_aid", BASELINE / "render_preview.py")
    canvas = copy.deepcopy(canvas)
    nodes = {node["id"]: node for node in canvas["nodes"]}
    for edge in canvas["edges"]:
        if not edge.get("fromSide") or not edge.get("toSide"):
            edge_sides(edge, nodes)  # reading aid only; Owner edge remains unchanged
    bounds = (min(n["x"] for n in canvas["nodes"]) - 20,
              min(n["y"] for n in canvas["nodes"]) - 20,
              max(n["x"] + n["width"] for n in canvas["nodes"]) + 20,
              max(n["y"] + n["height"] for n in canvas["nodes"]) + 20)
    overview = directory / f"{stem}.corrected-overview.png"
    detail = directory / f"{stem}.corrected-readable.png"
    overview_clipped = raster.render(canvas, overview, bounds, .35, stem + " — overview")
    detail_clipped = raster.render(canvas, detail, bounds, .8, stem + " — readable detail")
    return {"reading_aid": str(overview), "overview_scale": .35,
            "overview_text_overflow": overview_clipped,
            "overview_purpose": "reduced orientation image; text scales with saved card geometry",
            "detail_reading_aid": str(detail), "detail_scale": .8,
            "detail_text_overflow": detail_clipped,
            "preview": "deterministic raster of saved canvas positions; not an Obsidian application screenshot"}


def persist_receipt(path, receipt):
    """Archive the exact preceding receipt before replacing the current receipt."""
    if path.exists():
        previous_bytes = path.read_bytes()
        previous = json.loads(previous_bytes.decode("utf-8"))
        checksum = hashlib.sha256(previous_bytes).hexdigest()
        history = path.parent / "correction-history"
        history.mkdir(exist_ok=True)
        archived = history / f"{path.stem}.{checksum[:16]}.json"
        if archived.exists() and archived.read_bytes() != previous_bytes:
            raise service.CanvasConflict("previous validation receipt archive has conflicting content")
        if not archived.exists():
            archived.write_bytes(previous_bytes)
        reference = {"path": str(archived), "sha256": checksum}
        receipt["previous_validation"] = reference
        if previous.get("changes", {}).get("initial_generated_reflow"):
            receipt["initial_migration_validation"] = reference
        elif previous.get("initial_migration_validation"):
            receipt["initial_migration_validation"] = previous["initial_migration_validation"]
    path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def compact_receipt(receipt):
    changes = receipt["changes"]
    return {"spec": Path(receipt["spec"]).name, "canvas": Path(receipt["canvas"]).name,
            "committed": "commit" in receipt, "scenarios": receipt["scenarios"],
            "structural_problems": receipt["structural_problems"],
            "reference_flags": receipt["cross_view_reference_flags"],
            "card_overlaps": changes["preexisting_overlaps_preserved"],
            "owner_nodes_preserved": changes["owner_nodes_preserved"],
            "owner_edges_preserved": changes["owner_edges_preserved"],
            "geometry_change_records": len(changes["geometry_changes"]),
            "generated_reflow": changes["generated_reflow"],
            "initial_generated_reflow": changes["initial_generated_reflow"],
            "proposal_hash": receipt["proposal_hash"],
            **({"overview_text_overflow_count": len(receipt["overview_text_overflow"]),
                "detail_text_overflow": receipt["detail_text_overflow"]}
               if "overview_text_overflow" in receipt else {})}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true", help="commit only after corrected specs are ready")
    parser.add_argument("--stem", choices=["ingestion", "ingestion-tobe"], action="append")
    parser.add_argument("--hints", type=Path, help="report-local JSON: stem -> new node -> [existing anchor, y offset]")
    parser.add_argument("--png", action="store_true", help="render reading aids after committing")
    parser.add_argument("--reflow-generated", action="store_true",
                        help="reflow generated cards from the verified original or latest validated saved generation")
    parser.add_argument("--reroute-generated", action="store_true",
                        help="open native gutters and reroute generated edges from the last validated saved generation")
    parser.add_argument("--verbose-receipts", action="store_true", help="print complete receipts instead of compact summaries")
    options = parser.parse_args(argv)
    render = module_at("accepted_ingestion_renderer", HERE / "render_spec.py")
    layout = module_at("accepted_report_layout", BASELINE / "build_artifacts.py")
    library, locations = spec_library(render)
    hints = json.loads(options.hints.read_text(encoding="utf-8")) if options.hints else {}
    stems = options.stem or ["ingestion", "ingestion-tobe"]
    # Prepare every selected result before committing either target.
    prepared = [(stem, prepare(stem, render, layout, library, locations, hints.get(stem),
                              reflow_generated=options.reflow_generated,
                              reroute_generated=options.reroute_generated)) for stem in stems]
    receipts = []
    for stem, (target, preview, views, receipt) in prepared:
        if options.commit:
            receipt["commit"] = service.commit(target, preview)
            (HERE / f"{stem}.views.md").write_text(views, encoding="utf-8")
            if options.png:
                receipt.update(reading_aids(preview["proposal"], stem))
            persist_receipt(HERE / f"{stem}.correction-validation.json", receipt)
        else:
            receipt["committed"] = False
        receipts.append(receipt)
    print(json.dumps(receipts if options.verbose_receipts else [compact_receipt(r) for r in receipts], indent=2))
    return 0


# Captured before the 22 November corrections. This identifies generated material;
# it is not a layout snapshot and never overwrites live Owner geometry.
OLD_SNAPSHOTS = json.loads(r'''{"ingestion":{"spec_sha256":"6fae9b2d8e887321c7881f286586c3d97164d522113798fa125066faf21dbbfd","roles":{"s":null,"a1":"Owner","a2":"Tier 0 agent","a3":"Core","d1":"Core","x1":"Tier 0 agent","a4":"Owner","a5":"Tier 0 agent","d2":"Core","x2":"Tier 0 agent","a6":"Clerk (tier 3)","d3":"Clerk (tier 3)","x3":"Owner","a7":"Core","a8":"Tier 0 agent","d4":"Tier 0 agent","a9":"Core","a10":"Tier 0 agent","f1":"Core","a11":"Core","a12":"Clerk (tier 3)","m1":"Model host","dm":"Model host","a14":"Tier 0 agent","dc":"Tier 0 agent","j1":"Core","d5":"Core","x5":"Tier 0 agent","a13":"Geo-Grapher","d6":"Tier 0 agent","a15":"Tier 0 agent","a16":"Core","d7":"Core","a17":"Tier 0 agent","e1":null,"e2":null,"e3":null,"e4":null},"nodes":["s","a1","a2","a3","d1","x1","a4","a5","d2","x2","a6","d3","x3","a7","a8","d4","a9","a10","f1","a11","a12","m1","dm","a14","dc","j1","d5","x5","a13","d6","a15","a16","d7","a17","e1","e2","e3","e4"],"groups":{"lane-Owner":"Owner","lane-Tier-0-agent":"Tier 0 agent","lane-Core":"Core","lane-Clerk-tier-3-":"Clerk (tier 3)","lane-Model-host":"Model host","lane-Geo-Grapher":"Geo-Grapher","lane-Outcomes":"Outcomes"},"edges":{"e0":["s","a1"],"e1":["a1","a2"],"e2":["a2","a3"],"e3":["a3","d1"],"e4":["d1","a4"],"e5":["d1","x1"],"e6":["x1","a3"],"e7":["a4","a5"],"e8":["a5","d2"],"e9":["d2","a6"],"e10":["d2","x2"],"e11":["x2","a6"],"e12":["a6","d3"],"e13":["d3","a7"],"e14":["d3","x3"],"e15":["x3","a7"],"e16":["a7","a8"],"e17":["a8","d4"],"e18":["d4","a9"],"e19":["d4","a8"],"e20":["a9","a10"],"e21":["a10","f1"],"e22":["f1","a11"],"e23":["f1","a14"],"e24":["a11","a12"],"e25":["a12","m1"],"e26":["m1","dm"],"e27":["dm","j1"],"e28":["dm","j1"],"e29":["a14","dc"],"e30":["dc","j1"],"e31":["dc","e4"],"e32":["j1","d5"],"e33":["d5","a13"],"e34":["d5","x5"],"e35":["x5","f1"],"e36":["a13","d6"],"e37":["d6","a15"],"e38":["d6","e2"],"e39":["a15","a16"],"e40":["a16","d7"],"e41":["d7","a17"],"e42":["d7","e3"],"e43":["a17","e1"]}},"ingestion-tobe":{"spec_sha256":"9a27d04cbd24c6ecc2952cbcd7c16d424b2539f815aa0bf0361c158b3d0ddc39","roles":{"s":null,"a1":"Owner","a2":"Tier 0 agent","a3":"Lead (tier 1)","a4":"Core","d1":"Core","r1":"Doctor","a5":"Lead (tier 1)","d2":"Core","r2":"Doctor","a6":"Clerk (tier 3)","d3":"Clerk (tier 3)","x1":"Lead (tier 1)","x2":"Tier 0 agent","x3":"Owner","a7":"Core","a8":"Core","a9":"Helper (tier 2)","d4":"Helper (tier 2)","r3":"Doctor","a10":"Core","a11":"Core","f1":"Core","a12":"Core","a13":"Clerk (tier 3)","m1":"Model host","dm":"Model host","a14":"Core","dc":"Core","x4":"Lead (tier 1)","x5":"Tier 0 agent","j1":"Core","d5":"Core","r4":"Doctor","a15":"Geo-Grapher","d6":"Core","x6":"Core","x7":"Owner","a16":"Core","a17":"Core","d7":"Core","r5":"Doctor","a18":"Oracle","d8":"Oracle","r6":"Doctor","x8":"Helper (tier 2)","x9":"Lead (tier 1)","a19":"Lead (tier 1)","a20":"Tier 0 agent","d9":"Tier 0 agent","x10":"Tier 0 agent","x11":"Oracle","x12":"Lead (tier 1)","x13":"Oracle","x14":"Tier 0 agent","a21":"Tier 0 agent","xe":"Tier 0 agent","xp":"Tier 0 agent","e1":null,"e2":null,"e3":null},"nodes":["s","a1","a2","a3","a4","d1","r1","a5","d2","r2","a6","d3","x1","x2","x3","a7","a8","a9","d4","r3","a10","a11","f1","a12","a13","m1","dm","a14","dc","x4","x5","j1","d5","r4","a15","d6","x6","x7","a16","a17","d7","r5","a18","d8","r6","x8","x9","a19","a20","d9","x10","x11","x12","x13","x14","a21","xe","xp","e1","e2","e3"],"groups":{"lane-Owner":"Owner","lane-Tier-0-agent":"Tier 0 agent","lane-Oracle":"Oracle","lane-Lead-tier-1-":"Lead (tier 1)","lane-Doctor":"Doctor","lane-Helper-tier-2-":"Helper (tier 2)","lane-Clerk-tier-3-":"Clerk (tier 3)","lane-Core":"Core","lane-Model-host":"Model host","lane-Geo-Grapher":"Geo-Grapher","lane-Outcomes":"Outcomes"},"edges":{"e0":["s","a1"],"e1":["a1","a2"],"e2":["a2","a3"],"e3":["a3","a4"],"e4":["a4","d1"],"e5":["d1","a5"],"e6":["d1","r1"],"e7":["r1","a4"],"e8":["r1","xe"],"e9":["r1","xp"],"e10":["a5","d2"],"e11":["d2","a6"],"e12":["d2","r2"],"e13":["r2","a6"],"e14":["r2","xe"],"e15":["r2","xp"],"e16":["a6","d3"],"e17":["d3","a7"],"e18":["d3","x1"],"e19":["x1","x2"],"e20":["x2","x3"],"e21":["x3","a7"],"e22":["a7","a8"],"e23":["a8","a9"],"e24":["a9","d4"],"e25":["d4","a10"],"e26":["d4","r3"],"e27":["r3","a8"],"e28":["r3","xe"],"e29":["r3","xp"],"e30":["a10","a11"],"e31":["a11","f1"],"e32":["f1","a12"],"e33":["f1","a14"],"e34":["a12","a13"],"e35":["a13","m1"],"e36":["m1","dm"],"e37":["dm","j1"],"e38":["dm","j1"],"e39":["a14","dc"],"e40":["dc","j1"],"e41":["dc","x4"],"e42":["x4","x5"],"e43":["x5","xp"],"e44":["j1","d5"],"e45":["d5","a15"],"e46":["d5","r4"],"e47":["r4","a15"],"e48":["r4","xe"],"e49":["r4","xp"],"e50":["a15","d6"],"e51":["d6","a16"],"e52":["d6","x6"],"e53":["x6","x7"],"e54":["x7","a17"],"e55":["a16","a17"],"e56":["a17","d7"],"e57":["d7","a18"],"e58":["d7","r5"],"e59":["r5","a18"],"e60":["r5","xe"],"e61":["r5","xp"],"e62":["a18","d8"],"e63":["d8","a19"],"e64":["d8","r6"],"e65":["d8","x8"],"e66":["r6","a18"],"e67":["r6","xe"],"e68":["r6","xp"],"e69":["x8","x9"],"e70":["x9","a18"],"e71":["a19","a20"],"e72":["a20","d9"],"e73":["d9","a21"],"e74":["d9","x10"],"e75":["x10","x11"],"e76":["x11","x12"],"e77":["x12","x13"],"e78":["x13","x14"],"e79":["x14","a21"],"e80":["a21","e1"],"e81":["xe","e2"],"e82":["xp","e3"]}}}''')


if __name__ == "__main__":
    raise SystemExit(main())

