"""Advisory whole-library communities derived from the disposable index."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .coordination import atomic_write_text
from .index import Index
from .vault import now_iso

ALGORITHM = "deterministic-label-propagation-v1"


def _path(vault: Any) -> Path:
    return vault.derived / "communities.json"


def rebuild(vault: Any, iterations: int = 20, *, index_service: Any = None) -> dict[str, Any]:
    """Build a deterministic, advisory graph report without touching notes."""
    def collect(index: Index) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        index.refresh()
        rows = [dict(row) for row in index.conn.execute(
            "SELECT name, name_lower, shape, kind, path, frontmatter FROM note WHERE parse_error = ''")]
        links = [dict(row) for row in index.conn.execute("SELECT src, dst FROM link")]
        return rows, links
    if index_service is not None:
        rows, links = index_service.run(collect)
    else:
        with Index(vault) as index:
            rows, links = collect(index)
    names = {str(r["name_lower"]): str(r["name"]) for r in rows
             if str(r["shape"]) in ("source", "concept", "offering", "application")}
    graph: dict[str, set[str]] = {key: set() for key in names}
    excluded = 0
    for link in links:
        src, dst = str(link["src"]).lower(), str(link["dst"]).lower()
        if src not in graph or dst not in graph or src == dst:
            excluded += 1
            continue
        graph[src].add(dst)
        graph[dst].add(src)
    # Explicit concept/topic relations are an additional declared edge type,
    # not an inference from word overlap.  Structural routers and templates
    # were already excluded from ``names`` above, so they cannot acquire
    # centrality merely by linking everything.
    explicit_edges = 0
    for row in rows:
        src = str(row["name_lower"])
        if src not in graph:
            continue
        try:
            fm = json.loads(row["frontmatter"] or "{}")
        except (TypeError, ValueError):
            fm = {}
        declared = []
        for field in ("concepts", "related_terms", "glossary_terms", "related", "related_topics"):
            value = fm.get(field, []) if isinstance(fm, dict) else []
            declared.extend(value if isinstance(value, list) else [value])
        for target in declared:
            dst = str(target).replace("[[", "").replace("]]", "").strip().casefold()
            if dst in graph and dst != src and dst not in graph[src]:
                graph[src].add(dst)
                graph[dst].add(src)
                explicit_edges += 1
    labels = {node: node for node in graph}
    for _ in range(max(1, min(iterations, 100))):
        changed = False
        next_labels = dict(labels)
        for node in sorted(graph):
            neighbours = graph[node]
            if not neighbours:
                continue
            counts: dict[str, int] = defaultdict(int)
            for neighbour in sorted(neighbours):
                counts[labels[neighbour]] += 1
            chosen = min(((-count, label) for label, count in counts.items()))[1]
            if chosen != labels[node]:
                next_labels[node] = chosen
                changed = True
        labels = next_labels
        if not changed:
            break
    groups: dict[str, list[str]] = defaultdict(list)
    for node, label in labels.items():
        groups[label].append(node)
    communities = []
    for label, nodes in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0])):
        ranked = sorted(nodes, key=lambda n: (-len(graph[n]), names[n].lower()))
        communities.append({"id": label, "label": names.get(label, label), "size": len(nodes),
                            "members": [names[n] for n in ranked],
                            "central": [{"note": names[n], "degree": len(graph[n])}
                                        for n in ranked[:10]]})
    out = {"algorithm": ALGORITHM, "at": now_iso(), "nodes": len(graph),
           "edges": sum(len(v) for v in graph.values()) // 2,
           "explicit_edges": explicit_edges, "excluded_links": excluded,
           "exclusions": ["templates", "structural routers", "generated index nodes"],
           "communities": communities,
           "advisory": True}
    target = _path(vault)
    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    return out


def report(vault: Any) -> dict[str, Any]:
    try:
        data = json.loads(_path(vault).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"status": "not_built", "advisory": True, "communities": []}
    return data if isinstance(data, dict) else {"status": "invalid", "communities": []}


def disagreements(vault: Any, limit: int = 20) -> dict[str, Any]:
    data = report(vault)
    groups = data.get("communities", []) if isinstance(data, dict) else []
    # A bridge is an advisory ambiguity: a highly linked node in a small or
    # weakly connected community deserves a person's inspection, not mutation.
    rows = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        for central in group.get("central", []):
            if isinstance(central, dict) and central.get("degree", 0) >= 2:
                rows.append({"community": group.get("label", ""), **central})
    return {"algorithm": data.get("algorithm", ""), "advisory": True,
            "candidates": sorted(rows, key=lambda r: (-int(r.get("degree", 0)),
                                                       str(r.get("note", ""))))[:max(1, limit)]}
