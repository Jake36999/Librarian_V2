"""Native Canvas port selection and obstacle checks for report reading previews.

Only the native fromSide/toSide fields are edited. The tested polyline is exactly
the one drawn by render_preview.py; native hosts may use a different curve shape.
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math

SIDES = ("top", "bottom", "left", "right")
VECTORS = {"left": (-1, 0), "right": (1, 0), "top": (0, -1), "bottom": (0, 1)}


def anchor(card, side):
    x, y, width, height = (card[key] for key in ("x", "y", "width", "height"))
    return {"left": (x, y + height / 2), "right": (x + width, y + height / 2),
            "top": (x + width / 2, y), "bottom": (x + width / 2, y + height)}[side]


def curve_points(edge, nodes, *, subdivisions=30):
    first, last = nodes[edge["fromNode"]], nodes[edge["toNode"]]
    start, end = anchor(first, edge["fromSide"]), anchor(last, edge["toSide"])
    distance = min(220, max(70, math.dist(start, end) / 3))
    one, two = VECTORS[edge["fromSide"]], VECTORS[edge["toSide"]]
    c1 = tuple(start[index] + one[index] * distance for index in (0, 1))
    c2 = tuple(end[index] + two[index] * distance for index in (0, 1))
    points = []
    for index in range(subdivisions + 1):
        t, u = index / subdivisions, 1 - index / subdivisions
        points.append(tuple(u**3 * start[axis] + 3 * u * u * t * c1[axis]
                            + 3 * u * t * t * c2[axis] + t**3 * end[axis]
                            for axis in (0, 1)))
    return points


def segment_intersects_card(first, last, card, *, inset=.1):
    """Intersect a line segment with a strict card interior, ignoring edge touches."""
    lower, upper = 0., 1.
    for axis, position, extent in ((0, "x", "width"), (1, "y", "height")):
        lo = card[position] + inset
        hi = card[position] + card[extent] - inset
        delta = last[axis] - first[axis]
        if abs(delta) < 1e-10:
            if not lo < first[axis] < hi:
                return False
        else:
            one, two = sorted(((lo - first[axis]) / delta, (hi - first[axis]) / delta))
            lower, upper = max(lower, one), min(upper, two)
            if lower > upper:
                return False
    return lower <= upper


def intersected_cards(edge, nodes, *, include_endpoints=True):
    points = curve_points(edge, nodes)
    xmin, xmax = min(point[0] for point in points), max(point[0] for point in points)
    ymin, ymax = min(point[1] for point in points), max(point[1] for point in points)
    result = []
    for card in nodes.values():
        if card["type"] != "text":
            continue
        if not include_endpoints and card["id"] in (edge["fromNode"], edge["toNode"]):
            continue
        if xmax < card["x"] or xmin > card["x"] + card["width"]:
            continue
        if ymax < card["y"] or ymin > card["y"] + card["height"]:
            continue
        if any(segment_intersects_card(first, last, card) for first, last in zip(points, points[1:])):
            result.append(card["id"])
    return result


def intersections(document, *, edge_ids=None):
    nodes = {node["id"]: node for node in document["nodes"]}
    result = []
    for edge in document["edges"]:
        if edge_ids is not None and edge["id"] not in edge_ids:
            continue
        cards = intersected_cards(edge, nodes)
        if cards:
            result.append({"edge": edge["id"], "from": edge["fromNode"],
                           "to": edge["toNode"], "cards": cards})
    return result


def preferred_sides(first, last):
    if first["x"] == last["x"]:
        down = last["y"] > first["y"]
        return ("bottom", "top") if down else ("top", "bottom")
    right = last["x"] > first["x"]
    return ("right", "left") if right else ("left", "right")


def choose_sides(edge, nodes):
    """Find a clear native side pair, or return None without faking clearance."""
    existing = (edge.get("fromSide"), edge.get("toSide"))
    natural = preferred_sides(nodes[edge["fromNode"]], nodes[edge["toNode"]])
    candidates = [existing, natural, ("right", "right"), ("left", "left")]
    candidates.extend(itertools.product(SIDES, repeat=2))
    seen = set()
    for sides in candidates:
        if sides in seen or any(side not in SIDES for side in sides):
            continue
        seen.add(sides)
        proposal = {**edge, "fromSide": sides[0], "toSide": sides[1]}
        if not intersected_cards(proposal, nodes):
            return sides
    return None


def reroute(document, *, edge_ids=None, strict=True):
    """Edit permitted edge ports in place; preserve cards, labels and unknown fields."""
    nodes = {node["id"]: node for node in document["nodes"]}
    changes, unresolved = [], []
    for edge in document["edges"]:
        if edge_ids is not None and edge["id"] not in edge_ids:
            continue
        before = {key: edge.get(key) for key in ("fromSide", "toSide")}
        sides = choose_sides(edge, nodes)
        if sides is None:
            unresolved.append({"edge": edge["id"], "from": edge["fromNode"],
                               "to": edge["toNode"], "cards": intersected_cards(edge, nodes)})
            continue
        edge.update(fromSide=sides[0], toSide=sides[1])
        after = {key: edge[key] for key in before}
        if before != after:
            changes.append({"edge": edge["id"], "before": before, "after": after})
    if strict and unresolved:
        raise ValueError({"unrouteable_with_native_ports": unresolved})
    return {"edge_port_changes": changes, "edge_card_intersections": unresolved,
            "curve_scope": "deterministic report preview; native Canvas attachment sides only"}


def spread_columns(document, *, minimum_pitch=600, node_ids=None):
    """Expand only gutters; retain actor order, lane/card sizes and within-lane offsets."""
    groups = sorted((node for node in document["nodes"] if node["type"] == "group"
                     and (node_ids is None or node["id"] in node_ids)),
                    key=lambda node: node["x"])
    old_positions = [node["x"] for node in groups]
    if not old_positions:
        return []
    new_positions = [old_positions[0]]
    for index in range(1, len(groups)):
        new_positions.append(max(old_positions[index], new_positions[-1] + minimum_pitch))
    changes = []
    for node in document["nodes"]:
        if node_ids is not None and node["id"] not in node_ids:
            continue
        if node["type"] == "text" and node["width"] > 400:
            # The generated title spans the whole field, rather than belonging to a lane.
            node["width"] += new_positions[-1] - old_positions[-1]
            continue
        index = max((index for index, position in enumerate(old_positions)
                     if position <= node["x"]), default=0)
        offset = new_positions[index] - old_positions[index]
        if offset:
            changes.append({"node": node["id"], "old_x": node["x"], "new_x": node["x"] + offset})
            node["x"] += offset
    return changes


def clear_layout(document, *, edge_ids=None, node_ids=None, minimum_pitch=600, strict=True):
    """Open native gutters then select clear ports, preserving row order and semantics."""
    columns = spread_columns(document, minimum_pitch=minimum_pitch, node_ids=node_ids)
    result = reroute(document, edge_ids=edge_ids, strict=strict)
    return {"column_spacing_changes": columns, **result}


def localize_terminal_tails(specification, incoming_edges, *, main_path=()):
    """Copy real linear report/end tails for selected departures, never routing nodes.

    This pure authoring transform returns a new specification and an explicit fold
    mapping. It refuses main-path departures and branching/cyclic terminal tails.
    Copies retain the original actor, label and outcome. Callers still validate the
    model, geometry and caller contracts before accepting the transformed analysis.
    """
    result = copy.deepcopy(specification)
    nodes = {node["id"]: node for node in result["nodes"]}
    outgoing = {}
    for edge in result["edges"]:
        outgoing.setdefault(edge["from"], []).append(edge)
    selected = {json.dumps([edge["from"], edge["to"], edge.get("guard"), edge.get("ext")],
                           ensure_ascii=False) for edge in incoming_edges}
    main_pairs = set(zip(main_path, main_path[1:]))
    mapping, copies = {}, []
    for edge in list(result["edges"]):
        identity = json.dumps([edge["from"], edge["to"], edge.get("guard"), edge.get("ext")], ensure_ascii=False)
        if identity not in selected:
            continue
        if (edge["from"], edge["to"]) in main_pairs:
            raise ValueError("terminal localization must preserve the numbered main path")
        chain, visited = [], set()
        current = edge["to"]
        while True:
            if current in visited:
                raise ValueError("terminal report tail contains a cycle")
            visited.add(current)
            chain.append(current)
            if nodes[current]["kind"] == "end":
                break
            next_edges = outgoing.get(current, [])
            if len(next_edges) != 1 or next_edges[0].get("ext"):
                raise ValueError(f"{edge['to']} is not a linear terminal report tail")
            current = next_edges[0]["to"]
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
        copied = {name: f"{name}_at_{suffix}" for name in chain}
        for name in chain:
            node = copy.deepcopy(nodes[name])
            node["id"] = copied[name]
            node.pop("step", None)
            result["nodes"].append(node)
            mapping[node["id"]] = name
        for name in chain[:-1]:
            cloned_edge = copy.deepcopy(outgoing[name][0])
            cloned_edge["from"] = copied[cloned_edge["from"]]
            cloned_edge["to"] = copied[cloned_edge["to"]]
            result["edges"].append(cloned_edge)
        edge["to"] = copied[chain[0]]
        copies.append({"departure": identity, "original_tail": chain,
                       "local_tail": [copied[name] for name in chain]})
    validate_terminal_fold(specification, result, mapping)
    return result, {"node_origins": mapping, "terminal_tail_copies": copies}


def validate_terminal_fold(original, transformed, origins):
    """Prove local copies implement exactly the original labelled linear tails."""
    original_nodes = {node["id"]: node for node in original["nodes"]}
    transformed_nodes = {node["id"]: node for node in transformed["nodes"]}
    for copied, origin in origins.items():
        expected = copy.deepcopy(original_nodes[origin])
        actual = copy.deepcopy(transformed_nodes[copied])
        expected.pop("step", None)
        actual["id"] = origin
        assert actual == expected, (copied, "terminal copy changed behavior")

    def signature(edge, fold):
        return json.dumps({**edge, "from": fold.get(edge["from"], edge["from"]),
                           "to": fold.get(edge["to"], edge["to"])}, sort_keys=True)

    assert {signature(edge, {}) for edge in original["edges"]} == {
        signature(edge, origins) for edge in transformed["edges"]}, "folded edge contract changed"
    for copied, origin in origins.items():
        expected = {signature(edge, {}) for edge in original["edges"] if edge["from"] == origin}
        actual = {signature(edge, origins) for edge in transformed["edges"] if edge["from"] == copied}
        assert actual == expected, (copied, "terminal copy changed outgoing choices")
