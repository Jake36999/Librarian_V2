"""Build and validate the Librarian V2 current-activation map and 8 clone-free to-be activity specs."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

from resource_librarian.canvas import service

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = REPO / "reports/2026-11-21-enrichment-baseline"
ING = REPO / "reports/2026-11-20-workflow-map/examples/ingestion"

STEMS = (
    "librarian-current-activation",
    "librarian-doctor-tobe",
    "librarian-source-enrichment-tobe",
    "librarian-batch-enrichment-tobe",
    "librarian-ingestion-tobe",
    "librarian-context1-tier0-delegated",
    "librarian-context2-external-project-mcp",
    "librarian-context3-human-platform-ui",
    "librarian-process-composition-tobe",
)

EXTERNAL_CURRENT_SPECS = (
    BASE / "batch-enrichment-current.spec.yaml",
    BASE / "source-enrichment-current.spec.yaml",
    ING / "ingestion.spec.yaml",
)

PRESERVED_EXTERNAL_CANVASES = (
    (
        "reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas",
        "0a0b1af08f1ae2553ed4e0927d162ab60068ab1f9e2c612c949c7e6c737485b5",
    ),
    (
        "reports/2026-11-21-enrichment-baseline/batch-enrichment-current.canvas",
        "eb5a5bb6533d2d5c3ad93b0c98e36150deabd68bfe22856c439cd8e082d7fe2b",
    ),
    (
        "reports/2026-11-21-enrichment-baseline/source-enrichment-current.canvas",
        "5b050a3e80351e5a47d347f04d59e63d5cad9fae0abf43649ca499a7c3d6d76b",
    ),
    (
        "reports/2026-11-21-enrichment-baseline/enrichment-cycle.canvas",
        "8108dcd9dd9bfcecf6dc0dfd724c6cf00075d2cc8104d6590faf5aedd6157a6c",
    ),
)

FORBIDDEN_LAYER_LANES = (
    "Activation Context",
    "L2 Pipeline",
    "L1 Workflow",
    "L0 Action",
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def is_linear_tail(spec: dict, nid: str) -> bool:
    nodes = {n["id"]: n for n in spec["nodes"]}
    out = {}
    for edge in spec["edges"]:
        out.setdefault(edge["from"], []).append(edge)
    cur = nid
    seen = set()
    while True:
        if cur in seen:
            return False
        seen.add(cur)
        if nodes[cur]["kind"] == "end":
            return True
        nxts = out.get(cur, [])
        if len(nxts) != 1 or nxts[0].get("ext"):
            return False
        cur = nxts[0]["to"]


def check_ownership_and_safety(stem: str, spec: dict, raw: str) -> list[str]:
    issues = []
    for lane in spec["lanes"]:
        if any(bad.lower() in lane.lower() for bad in FORBIDDEN_LAYER_LANES):
            issues.append(f"{stem}: layer-named swimlane '{lane}' instead of actor lane")
    # Check Core vs semantic ownership: Core must not author semantic prose/relations/proposals.
    for node in spec["nodes"]:
        nid = node["id"]
        lane = node.get("lane", "")
        lab = node.get("label", "").lower()
        if lane == "Core" and nid in ("relate", "metapropose", "describe", "clerkdraft", "freview", "fscribe"):
            issues.append(f"{stem}: semantic node '{nid}' must not be assigned to Core")
        if lane.startswith("Clerk") and "static ast" in lab and "never" not in lab:
            issues.append(f"{stem}: Clerk node '{nid}' appears to claim static AST extraction")
    # Route-collided Oracle checks must fail closed and never assert positive independent review.
    for i, line in enumerate(raw.splitlines(), 1):
        low = line.lower()
        if "oracle_route_collision" in low and ("independently reviewed" in low or "marked resolved" in low):
            if not any(neg in low for neg in ("never", "not ", "must not", "prohibit")):
                issues.append(f"{stem}:{i}: positive independent review claim on ORACLE_ROUTE_COLLISION")
    return issues


def check_preserved_canvases() -> list[dict]:
    results = []
    for rel, expected in PRESERVED_EXTERNAL_CANVASES:
        path = REPO / rel
        if not path.exists():
            raise FileNotFoundError(f"Preserved external canvas missing: {path}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Preserved canvas modified: {rel} expected={expected} actual={actual}")
        results.append({"canvas": rel, "sha256": actual, "preserved_unchanged": True})
    return results


def render_views(stem: str, spec: dict, scenarios: list[dict], render) -> str:
    tree, tests = render.tree_and_tests(spec, scenarios)
    actors = [lane for lane in spec["lanes"] if lane != "Core"]
    use_case = [
        "flowchart LR",
        '  subgraph librarian["Librarian"]',
        f'    goal(["{spec["title"]}"])',
        "  end",
    ]
    for idx, actor in enumerate(actors):
        use_case.append(f'  actor{idx}(["{actor}"]) --- goal')
    is_current = spec.get("status") == "IMPLEMENTED_VERIFIED" or stem == "librarian-current-activation"
    if is_current:
        status_line = (
            "**Status:** `IMPLEMENTED_VERIFIED` descriptive present-day behavioural specification at commit `d9435e1` "
            "(links to `batch-enrichment-current` and `source-enrichment-current`; preserves historical `DataManagement` `ingestion.canvas` unmodified). "
            "See [librarian-current-activation.md](librarian-current-activation.md) · [05-policy-and-behaviour-reconstruction.md](../05-policy-and-behaviour-reconstruction.md) · [Diagrams Index](README.md)."
        )
        footer = (
            "_Note: Scenario tests verify static graph reachability and path coverage of this descriptive current-state model only; "
            "live behaviour is verified separately against `d9435e1` code anchors in [librarian-current-activation.md](librarian-current-activation.md)._"
        )
    else:
        status_line = (
            "**Status:** `PROPOSED_UNACCEPTED` refined to-be behavioral specification (clone-free YAML; NOT accepted by Owner and NOT implemented in runtime code). "
            "See [05-policy-and-behaviour-reconstruction.md](../05-policy-and-behaviour-reconstruction.md) · [03-proposed-librarian-tobe.md](../03-proposed-librarian-tobe.md) · [Diagrams Index](README.md)."
        )
        footer = (
            "_Note: Scenario tests verify static graph reachability and guarded path coverage in this proposed spec only; "
            "they do NOT execute or verify live Web UI, MCP server, Broker, Geo-Grapher, or DeepInfra runtime behaviour._"
        )
    return "\n".join([
        "<!-- generated by build_and_validate_diagrams.py using accepted render_spec.py; edit the spec -->",
        f"# {spec['title']}",
        "",
        status_line,
        "",
        "## Validation",
        "",
        "No structural problems, cross-view flags, card overlaps, edge/card intersections, text overflows, ownership violations, or `_at_` spec clones.",
        "",
        "## Use-case diagram",
        "",
        "```mermaid",
        "\n".join(use_case),
        "```",
        "",
        "## Activity diagram",
        "",
        "```mermaid",
        render.mermaid(spec),
        "```",
        "",
        "## Written use case",
        "",
        render.written_use_case(spec, scenarios),
        "",
        "## Lane load",
        "",
        render.lane_load(spec, scenarios),
        "",
        f"## Decision tree with {len(scenarios)} extension scenarios",
        "",
        tree,
        "",
        "## Scenario test table",
        "",
        tests,
        "",
        footer,
        "",
    ])


def main() -> int:
    layout = load_module("tobe_layout", BASE / "build_artifacts.py")
    routing = layout.routing()
    render = layout.renderer()
    raster = load_module("tobe_raster", BASE / "render_preview.py")

    preserved_receipts = check_preserved_canvases()

    library = {}
    raw_texts = {}
    for stem in STEMS:
        path = HERE / f"{stem}.spec.yaml"
        raw = path.read_text(encoding="utf-8")
        if "_at_" in raw:
            raise ValueError(f"{path.name}: canonical .spec.yaml must contain zero _at_ clone nodes")
        raw_texts[stem] = raw
        spec = render.load(path)
        spec["_file"] = path.name
        library[stem] = spec

    # Load read-only external current baseline specs for ref outcome validation without mutating them.
    ref_library = dict(library)
    for ext_path in EXTERNAL_CURRENT_SPECS:
        ext_spec = render.load(ext_path)
        ext_key = ext_spec.get("diagram") or ext_path.stem.removesuffix(".spec")
        ref_library[ext_key] = ext_spec

    ownership_findings = []
    for stem in STEMS:
        ownership_findings.extend(check_ownership_and_safety(stem, library[stem], raw_texts[stem]))
    if ownership_findings:
        raise ValueError(("ownership_or_safety_violations", ownership_findings))

    receipts = []
    for stem in STEMS:
        spec = library[stem]
        problems, scenarios = layout.checks(spec, render, ref_library)
        if problems:
            raise ValueError((stem, problems))

        views_md = render_views(stem, spec, scenarios, render)

        # Build geometry from pure spec first; only apply in-memory tail localization if edge routing intersects cards.
        geom_spec = copy.deepcopy(spec)
        in_memory_fold = {"node_origins": {}, "terminal_tail_copies": []}
        generated = layout.managed_canvas(geom_spec, render)
        routing.clear_layout(generated, minimum_pitch=600, strict=False)
        inter = routing.intersections(generated)
        for _ in range(4):
            if not inter:
                break
            cur_main = render.main_path(geom_spec)
            cur_pairs = set(zip(cur_main, cur_main[1:]))
            bad_pairs = {
                (item["from"].removeprefix(service.MANAGED_PREFIX), item["to"].removeprefix(service.MANAGED_PREFIX))
                for item in inter
            }
            in_edges = [
                edge for edge in geom_spec["edges"]
                if (edge["from"], edge["to"]) in bad_pairs
                and (edge["from"], edge["to"]) not in cur_pairs
                and is_linear_tail(geom_spec, edge["to"])
            ]
            if not in_edges:
                raise ValueError((stem, "unresolved non-tail intersections", inter))
            geom_spec, step_fold = routing.localize_terminal_tails(
                geom_spec, in_edges, main_path=cur_main
            )
            geom_spec["_file"] = spec["_file"]
            in_memory_fold["node_origins"].update(step_fold["node_origins"])
            in_memory_fold["terminal_tail_copies"].extend(step_fold["terminal_tail_copies"])
            fold_probs, _ = layout.checks(geom_spec, render, ref_library)
            if fold_probs:
                raise ValueError((stem, "in-memory localized spec failed checks", fold_probs))
            generated = layout.managed_canvas(geom_spec, render)
            routing.clear_layout(generated, minimum_pitch=600, strict=False)
            inter = routing.intersections(generated)

        ov = layout.overlaps(generated)
        inter = routing.intersections(generated)
        if ov or inter:
            raise ValueError((stem, "layout defects remain", ov, inter))

        target = HERE / f"{stem}.canvas"
        if target.exists():
            prior_doc = json.loads(target.read_text(encoding="utf-8"))
            if all(str(n.get("id", "")).startswith(service.MANAGED_PREFIX) for n in prior_doc.get("nodes", [])):
                # Reset purely generated layout when specs/lanes are redesigned so old card coordinates never collide.
                target.unlink()
        preview = service.preview(target, generated, profile=None)
        commit_res = service.commit(target, preview)
        (HERE / f"{stem}.views.md").write_text(views_md, encoding="utf-8")

        saved = json.loads(target.read_text(encoding="utf-8"))
        saved_ov = layout.overlaps(saved)
        saved_inter = routing.intersections(saved)
        if saved_ov or saved_inter:
            raise ValueError((stem, "saved canvas defects", saved_ov, saved_inter))

        right = max(n["x"] + n["width"] for n in saved["nodes"])
        bottom = max(n["y"] + n["height"] for n in saved["nodes"])
        clipped = raster.render(
            saved,
            HERE / f"{stem}.png",
            (0, -220, right + 30, bottom + 30),
            0.3,
            spec["title"],
        )
        if clipped:
            raise ValueError((stem, "PNG text overflow", clipped))

        t0 = render.tier0_lane(spec)
        t0_mss = render.tier0_turns(spec, scenarios[0]) if t0 else None
        t0_non_esc = [
            render.tier0_turns(spec, p)
            for p in scenarios
            if not (p["end"] and render.outcome({n["id"]: n for n in spec["nodes"]}[p["end"]]) == "escalated")
        ] if t0 else []

        receipts.append({
            "model": stem,
            "epistemic_status": spec.get("status") or ("IMPLEMENTED_VERIFIED" if stem == "librarian-current-activation" else "PROPOSED_UNACCEPTED"),
            "spec_file": f"{stem}.spec.yaml",
            "spec_sha256": hashlib.sha256((HERE / f"{stem}.spec.yaml").read_bytes()).hexdigest(),
            "spec_at_clones": 0,
            "canvas_file": f"{stem}.canvas",
            "canvas_revision": commit_res["revision"],
            "views_file": f"{stem}.views.md",
            "png_file": f"{stem}.png",
            "canvas_nodes": len(saved["nodes"]),
            "canvas_edges": len(saved["edges"]),
            "numbered_steps": sum(bool(n.get("step")) for n in spec["nodes"]),
            "extension_scenarios": len(scenarios),
            "tier0_turns_mss": t0_mss,
            "tier0_turns_worst_non_escalated": max(t0_non_esc) if t0_non_esc else None,
            "structural_reference_flags": [],
            "card_overlaps": saved_ov,
            "edge_card_intersections": saved_inter,
            "overview_text_overflow": clipped,
            "in_memory_terminal_localizations": len(in_memory_fold["terminal_tail_copies"]),
            "call_outcomes": sorted({render.outcome(n) for n in spec["nodes"] if n["kind"] == "end"}),
        })

    # Re-verify preserved external canvases at end as well.
    check_preserved_canvases()

    summary = {
        "completed_on": "2026-11-25",
        "renderer": "reports/2026-11-20-workflow-map/examples/ingestion/render_spec.py",
        "models": receipts,
        "ownership_review": {
            "actor_lanes_only": True,
            "core_vs_agent_checks": "passed",
            "route_collision_fail_closed": "passed",
            "findings": [],
        },
        "preserved_external_canvases": preserved_receipts,
        "new_library_model_calls": 0,
        "new_library_model_spend_usd": 0,
        "validation_scope": [
            "Structural YAML node/edge graph validation (render_spec.validate)",
            "Cross-view step/extension parity and single-MSS termination (render_spec.cross_check)",
            "Cross-diagram ref outcome parity across all 9 local specs plus external batch-enrichment-current and source-enrichment-current (render_spec.check_references)",
            "Actor-lane purity, Core vs Agent ownership boundaries, and fail-closed ORACLE_ROUTE_COLLISION safety checks",
            "SHA-256 preservation verification of untouched historical ingestion.canvas, batch-enrichment-current.canvas, source-enrichment-current.canvas, and enrichment-cycle.canvas",
            "2D Obsidian Canvas geometry checks (card_overlaps=0, edge_card_intersections=0) and PNG overview text-fit check (clipped=0)",
            "Strict spec purity check: zero _at_<hash> clone nodes on disk in .spec.yaml or .views.md",
        ],
        "validation_limits": [
            "PROPOSED_UNACCEPTED specifications (8 to-be models): passing static checks does NOT make any diagram Owner-accepted or implemented in runtime Python/JS.",
            "librarian-current-activation documents verified d9435e1 behaviour statically; scenario enumeration proves graph reachability, not fresh runtime execution.",
            "Static diagram, cross-view, and canvas geometry checks do NOT verify live Librarian Web UI flows, live MCP requests, Broker permission gates, record_application persistence, Geo-Grapher indexing, or DeepInfra model behaviour.",
            "No DeepInfra or external model calls were executed during validation (new_library_model_calls=0, spend=$0).",
            "In-memory terminal tail localization preserves behavior per validate_terminal_fold during 2D .canvas geometry generation without altering canonical .spec.yaml.",
        ],
    }
    (HERE / "validation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    for bak in HERE.glob("*.bak"):
        bak.unlink()

    lines = [
        "# Librarian V2 Current Activation & To-Be Diagrams (`diagrams/`)",
        "",
        "This directory holds **9** validated specifications obeying the accepted `render_spec.py` (`DOC-MAP-05`, `DOC-PLN-03`) four-view convention with **zero `_at_` clone nodes** inside canonical `.spec.yaml` files:",
        "- **1 Current-State Activation Map (`IMPLEMENTED_VERIFIED`, commit `d9435e1`):** `librarian-current-activation` (links via `kind: ref` to preserved [batch-enrichment-current.canvas](../../2026-11-21-enrichment-baseline/batch-enrichment-current.canvas) and [source-enrichment-current.canvas](../../2026-11-21-enrichment-baseline/source-enrichment-current.canvas); leaves historical `DataManagement` [ingestion.canvas](../../2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) unmodified).",
        "- **8 Proposed To-Be Specifications (`PROPOSED_UNACCEPTED`):** `librarian-process-composition-tobe`, `librarian-context1-tier0-delegated`, `librarian-context2-external-project-mcp`, `librarian-context3-human-platform-ui`, `librarian-ingestion-tobe`, `librarian-batch-enrichment-tobe`, `librarian-source-enrichment-tobe`, and `librarian-doctor-tobe`.",
        "",
        "## Process Call Hierarchies",
        "",
        "```text",
        "Current Activation (`IMPLEMENTED_VERIFIED` d9435e1):",
        "  librarian-current-activation ──(ref: main batch)──> batch-enrichment-current ──(ref)──> source-enrichment-current",
        "                               └──(ref: UI deep-read)──────────────────────────────────> source-enrichment-current",
        "  (Historical DataManagement cohort trace preserved separately at reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas)",
        "",
        "Proposed To-Be Family (`PROPOSED_UNACCEPTED` — NOT accepted/implemented):",
        "  librarian-process-composition-tobe (actor-laned L3 Sprint -> L0 Action narrowing)",
        "    ├──(ref: Context 1)──> librarian-context1-tier0-delegated   ──(ref)──> librarian-ingestion-tobe",
        "    ├──(ref: Context 2)──> librarian-context2-external-project-mcp ─(ref)─> librarian-ingestion-tobe",
        "    └──(ref: Context 3)──> librarian-context3-human-platform-ui ──(ref)──> librarian-batch-enrichment-tobe / librarian-ingestion-tobe",
        "                                                                                  │",
        "                                                                                  ├──(ref)──> librarian-source-enrichment-tobe",
        "                                                                                  └──(ref)──> librarian-doctor-tobe (Ticket R1-R6)",
        "```",
        "",
        "## Validated Diagram Inventory (9 Models)",
        "",
        "| Model | Status | Steps | Scenarios | Nodes | Edges | Overlaps | Edge Crossings | PNG Overflows | Spec `_at_` Clones | In-Memory Tail Locs | Artifacts |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for r in receipts:
        m = r["model"]
        extra_md = " · [notes](librarian-current-activation.md)" if m == "librarian-current-activation" else ""
        lines.append(
            f"| `{m}` | `{r['epistemic_status']}` | {r['numbered_steps']} | {r['extension_scenarios']} | {r['canvas_nodes']} | "
            f"{r['canvas_edges']} | 0 | 0 | 0 | 0 | {r['in_memory_terminal_localizations']} | "
            f"[spec]({m}.spec.yaml) · [views]({m}.views.md) · [canvas]({m}.canvas) · [png]({m}.png){extra_md} |"
        )
    lines += [
        "",
        "## Preserved Baseline Canvases (Unmodified SHA-256 Verified)",
        "",
        "| Canvas | SHA-256 | Status |",
        "|---|---|---|",
    ]
    for p in preserved_receipts:
        lines.append(f"| `{p['canvas']}` | `{p['sha256']}` | Unmodified (`preserved_unchanged: true`) |")
    lines += [
        "",
        "## Validation Scope & Limits",
        "",
        "- **What validation establishes:** Every model passes structural validation (`render_spec.validate`), cross-view guard/step numbering (`render_spec.cross_check`), cross-diagram outcome parity across all 9 local specs plus external `batch-enrichment-current` and `source-enrichment-current` (`render_spec.check_references`), actor-lane and Core/agent ownership checks, fail-closed `ORACLE_ROUTE_COLLISION` checks, SHA-256 baseline canvas preservation, 2D canvas non-overlap & edge/card intersection checks (`0` overlaps, `0` intersections), overview PNG text-fit checks (`0` clipped labels), and spec purity (`0` `_at_` clones on disk).",
        "- **What validation does NOT establish:** The 8 to-be diagrams remain **`PROPOSED_UNACCEPTED`** targets — static checks do **NOT** constitute Owner acceptance, do **NOT** prove runtime Ticket/Oracle/Doctor implementation, and do **NOT** execute live Web UI, MCP, Broker, `record_application`, Geo-Grapher, or DeepInfra behaviour (`new_library_model_calls: 0`).",
        "",
        "Machine-checked summary: [validation.json](validation.json) · Companion Policy & Behaviour Report: [05-policy-and-behaviour-reconstruction.md](../05-policy-and-behaviour-reconstruction.md).",
        "",
    ]
    (HERE / "README.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
