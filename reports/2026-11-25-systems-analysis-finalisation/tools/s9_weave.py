"""Weave Geo-Grapher's processes into the Librarian's (26 November).

Each place a Librarian flow called Geo-Grapher through a plain activity becomes a reference to the
Geo-Grapher to-be process it runs, named `geo-grapher/to-be/<spec>`. render_pack then checks that the
Librarian handles every outcome that process can end with, as it does for its own references.

- folder-review:geoapply        -> graph-building   (UC-G1)
- paper-publication:publish     -> paper-import     (UC-G2)
- cite-graph:search + outline   -> query-graph      (UC-G3); the connection check it made redundant goes
- research:place                -> query-graph      (UC-G3), the code graph
- research: a brief comparing projects -> federated-search (UC-G4)

    python tools/s9_weave.py          # idempotent
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, renumber, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Geo-Grapher woven in by tools/s9_weave.py (2026-11-26)."
L = HERE / "librarian/to-be"
G = "geo-grapher/to-be/"


def nodes_of(spec: dict) -> dict:
    return {n["id"]: n for n in spec["nodes"]}


def out_edges(spec: dict, nid: str) -> list:
    return [e for e in spec["edges"] if e["from"] == nid]


def set_outs(spec: dict, nid: str, outs: list[tuple[str, str]]) -> None:
    """Replace a node's ways out with (target, guard) pairs, in order; the first is the main way."""
    spec["edges"] = [e for e in spec["edges"] if e["from"] != nid]
    spec["edges"] += [{"from": nid, "to": t, **({"guard": g} if g else {})} for t, g in outs]


def as_ref(node: dict, use_case: str, label: str) -> None:
    node.update(kind="ref", use_case=use_case, label=label)


def drop(spec: dict, nid: str) -> None:
    spec["nodes"] = [n for n in spec["nodes"] if n["id"] != nid]
    spec["edges"] = [e for e in spec["edges"] if nid not in (e["from"], e["to"])]


def add_node(spec: dict, node: dict, before: str | None = None) -> None:
    if node["id"] in nodes_of(spec):
        return
    ids = [n["id"] for n in spec["nodes"]]
    at = ids.index(before) if before in ids else len(ids)
    spec["nodes"].insert(at, node)


def folder_review() -> None:
    path = L / "folder-review.spec.yaml"
    spec = load(path)
    n = nodes_of(spec)
    as_ref(n["geoapply"], G + "graph-building",
           "applies the one decided group in Geo-Grapher as a delta, and returns its receipt (UC-G1)")
    set_outs(spec, "geoapply", [("dgeo", "success"), ("oraclecov", "partial"), ("doctorgeo", "refused")])
    n["dgeo"]["label"] = "does the receipt match the one decided group: its fingerprint, coverage and changed entities?"
    set_outs(spec, "dgeo", [("m_success", "it matches"),
                            ("doctorgeo", "the folder changed since the decision, or a mapped Geo-Grapher fault"),
                            ("e_escalated", "critical Geo DB or security violation")])
    save(renumber(spec), path, NOTE)


def paper_publication() -> None:
    path = L / "paper-publication.spec.yaml"
    spec = load(path)
    n = nodes_of(spec)
    as_ref(n["publish"], G + "paper-import",
           "publishes the converted paper in Geo-Grapher as one checked insert, and returns its receipt and stored link "
           "(UC-G2)")
    set_outs(spec, "publish", [("pubreceipt", "success"), ("e_gap", "partial"), ("e_gap", "refused")])
    n["e_gap"]["label"] = ("Geo-Grapher disabled, a refusal, a partial publication (its Geo-Grapher ticket kept), "
                           "or an empty paper graph")
    save(renumber(spec), path, NOTE)


def cite_graph() -> None:
    path = L / "cite-graph.spec.yaml"
    spec = load(path)
    if "query" not in nodes_of(spec):
        add_node(spec, {"id": "query", "kind": "ref", "lane": "Geo-Grapher", "use_case": G + "query-graph",
                        "label": ("searches the library's paper graph and returns the paper's outline, labels in the "
                                  "Lead's context (UC-G3)")}, before="search")
        for e in spec["edges"]:
            if e["to"] == "search":
                e["to"] = "query"
        drop(spec, "search")
        drop(spec, "outline")
        set_outs(spec, "query", [("sections", "success"), ("e_unavailable", "refused")])
        # the query's own refusal now says whether the graph is there; the later connection check never fires
        set_outs(spec, "put", [("resolve", "")])
        drop(spec, "dconnected")
    save(renumber(spec), path, NOTE)


def research() -> None:
    path = L / "research.spec.yaml"
    spec = load(path)
    n = nodes_of(spec)
    as_ref(n["place"], G + "query-graph",
           "places each finding in our code: a code-graph query finds the entity it cites (UC-G3)")
    add_node(spec, {"id": "noplace", "kind": "activity", "lane": "Lead (tier 1)",
                    "label": "states the finding as unplaced, a gap in the report, when no code graph is readable"},
             before="draft")
    set_outs(spec, "place", [("draft", "success"), ("noplace", "refused")])
    set_outs(spec, "noplace", [("draft", "")])
    # a brief that compares projects searches across their graphs before the papers are read
    add_node(spec, {"id": "dcompare", "kind": "decision", "lane": "Core",
                    "label": "does the brief compare projects?"}, before="ref_cite")
    add_node(spec, {"id": "ref_fed", "kind": "ref", "lane": "Lead (tier 1)", "use_case": G + "federated-search",
                    "label": ("searches the projects' graphs side by side, related only through accepted bridges "
                              "(UC-G4)")}, before="ref_cite")
    for e in spec["edges"]:
        if e["to"] == "ref_cite" and e["from"] not in ("dcompare", "ref_fed"):
            e["to"] = "dcompare"
    set_outs(spec, "dcompare", [("ref_cite", "no"), ("ref_fed", "yes: two or more projects' graphs")])
    add_node(spec, {"id": "nocompare", "kind": "activity", "lane": "Lead (tier 1)",
                    "label": "states the comparison as a gap (the graphs were out of bounds) and reads the papers without it"},
             before="ref_cite")
    set_outs(spec, "ref_fed", [("ref_cite", "success"), ("nocompare", "refused")])
    set_outs(spec, "nocompare", [("ref_cite", "")])
    save(renumber(spec), path, NOTE)


def main() -> None:
    folder_review()
    paper_publication()
    cite_graph()
    research()


if __name__ == "__main__":
    main()
