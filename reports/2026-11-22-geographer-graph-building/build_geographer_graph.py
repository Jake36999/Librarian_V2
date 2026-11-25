"""Validate and render geographer-graph-building.spec.yaml into views, Obsidian canvas, and PNG preview."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from resource_librarian.canvas import service
from resource_librarian.canvas.document import content_revision, validate_document

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RENDER_SPEC_PATH = REPO / "reports/2026-11-20-workflow-map/examples/ingestion/render_spec.py"
SPEC_PATH = HERE / "geographer-graph-building.spec.yaml"
VIEWS_PATH = HERE / "geographer-graph-building.views.md"
CANVAS_PATH = HERE / "geographer-graph-building.canvas"
PREVIEW_PATH = HERE / "overview.png"
VALIDATION_PATH = HERE / "validation.json"


def load_renderer():
    spec = importlib.util.spec_from_file_location("accepted_activity_renderer", RENDER_SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build_clean_canvas(spec: dict, render) -> dict:
    """Actor-column Obsidian canvas with strict downward main spine, non-interleaved side cards,
    explicit edge attachment sides, and librarian- generated IDs."""
    generated = render.canvas(spec)
    by_id = {n["id"]: n for n in generated["nodes"]}
    main = render.main_path(spec)
    on_main = set(main)
    outs = defaultdict(list)
    preds = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
        preds[e["to"]].append(e["from"])

    # Assign strict sequential rows to main path so every step advances cleanly downward
    # and extension cards sit on the same row as (or just below) their decision in an adjacent lane.
    row_y = {}
    row_step = 210
    cur_row = 0
    lane_occupied = defaultdict(list)  # x -> list of (y_start, y_end)

    def place(nid: str, preferred_y: int) -> int:
        card = by_id[nid]
        h = card["height"]
        y = preferred_y
        x = card["x"]
        while any(y < end + 24 and y + h + 24 > start for start, end in lane_occupied[x]):
            y += row_step
        card["y"] = y
        lane_occupied[x].append((y, y + h))
        row_y[nid] = y
        return y

    # 1. Place main path strictly downward; when a main decision spawns side nodes, place those
    # immediately beside/below it so the eye follows the branch cleanly without interleaving.
    last_main_y = 140
    placed = set()
    for nid in main:
        y = place(nid, last_main_y if nid == main[0] else last_main_y + row_step)
        placed.add(nid)
        last_main_y = y
        # Place direct extension chains branching off this main node (excluding rejoins/main)
        for e in outs[nid]:
            if e["to"] in on_main:
                continue
            cur = e["to"]
            chain_y = y
            while cur and cur not in on_main and cur not in placed:
                # If side node shares same column as parent, step down; otherwise align horizontally
                if by_id[cur]["x"] == by_id[nid]["x"]:
                    chain_y = max(chain_y + row_step, y + row_step)
                cy = place(cur, chain_y)
                placed.add(cur)
                # Follow single outgoing edge in side chain
                nxts = [ne["to"] for ne in outs[cur] if ne["to"] not in on_main and ne["to"] not in placed]
                if nxts:
                    nxt = nxts[0]
                    chain_y = cy if by_id[nxt]["x"] != by_id[cur]["x"] else cy + row_step
                    cur = nxt
                else:
                    cur = None

    # Place any remaining unplaced nodes (if any)
    for n in spec["nodes"]:
        if n["id"] not in placed:
            p_ys = [row_y[p] for p in preds[n["id"]] if p in row_y]
            place(n["id"], max(p_ys) if p_ys else last_main_y + row_step)
            placed.add(n["id"])

    # Resize lane groups to fit all cards cleanly
    max_bottom = max(c["y"] + c["height"] for c in generated["nodes"] if c["type"] == "text" and c["id"] != "title")
    for n in generated["nodes"]:
        if n["type"] == "group":
            n["y"] = 60
            n["height"] = max_bottom + 80 - 60

    # Add explicit edge attachment sides based on relative geometry
    for edge in generated["edges"]:
        a = by_id[edge["fromNode"]]
        b = by_id[edge["toNode"]]
        if a["x"] == b["x"]:
            if b["y"] >= a["y"]:
                edge["fromSide"], edge["toSide"] = "bottom", "top"
            else:
                edge["fromSide"], edge["toSide"] = "top", "bottom"
        elif b["x"] > a["x"]:
            edge["fromSide"], edge["toSide"] = "right", "left"
        else:
            edge["fromSide"], edge["toSide"] = "left", "right"

    # Prefix generated node and edge IDs with librarian- per canvas service contract
    id_map = {}
    for n in generated["nodes"]:
        old = n["id"]
        new = f"librarian-{old}"
        id_map[old] = new
        n["id"] = new
    for e in generated["edges"]:
        e["id"] = f"librarian-{e['id']}"
        e["fromNode"] = id_map[e["fromNode"]]
        e["toNode"] = id_map[e["toNode"]]
    return generated


def check_overlaps(doc: dict) -> list[tuple[str, str]]:
    cards = [n for n in doc["nodes"] if n.get("type") == "text"]
    overlaps = []
    for i, a in enumerate(cards):
        for b in cards[i + 1:]:
            if (a["x"] < b["x"] + b["width"] and a["x"] + a["width"] > b["x"]
                    and a["y"] < b["y"] + b["height"] and a["y"] + a["height"] > b["y"]):
                overlaps.append((a["id"], b["id"]))
    return overlaps


def render_png_preview(doc: dict, out_path: Path) -> dict:
    """Deterministic raster preview of the saved canvas for visual inspection."""
    scale = 0.75
    pad = 40
    min_x = min(n["x"] for n in doc["nodes"]) - pad
    min_y = min(n["y"] for n in doc["nodes"]) - pad
    max_x = max(n["x"] + n["width"] for n in doc["nodes"]) + pad
    max_y = max(n["y"] + n["height"] for n in doc["nodes"]) + pad
    W = int((max_x - min_x) * scale)
    H = int((max_y - min_y) * scale)

    img = Image.new("RGB", (W, H), "#f8f9fb")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 12)
        font_bold = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 13)
        font_title = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 15)
    except Exception:
        font = font_bold = font_title = ImageFont.load_default()

    palette = {
        "1": ("#fdecea", "#c93b3b"),
        "2": ("#fff3e0", "#d97706"),
        "3": ("#fef9e7", "#b7791f"),
        "4": ("#eaf7ee", "#2e7d32"),
        "5": ("#eef0ff", "#5c6bc0"),
        "6": ("#f3e8ff", "#7e22ce"),
        None: ("#ffffff", "#64748b"),
    }

    def sx(v): return int((v - min_x) * scale)
    def sy(v): return int((v - min_y) * scale)

    # 1. Draw groups (lanes)
    for n in doc["nodes"]:
        if n.get("type") == "group":
            x1, y1 = sx(n["x"]), sy(n["y"])
            x2, y2 = sx(n["x"] + n["width"]), sy(n["y"] + n["height"])
            draw.rectangle([x1, y1, x2, y2], fill="#f1f5f9", outline="#cbd5e1", width=1)
            draw.text((x1 + 8, y1 + 6), n.get("label", ""), fill="#334155", font=font_bold)

    # 2. Draw edges
    by_id = {n["id"]: n for n in doc["nodes"]}
    def anchor(n, side):
        x, y, w, h = n["x"], n["y"], n["width"], n["height"]
        if side == "top": return (sx(x + w / 2), sy(y))
        if side == "bottom": return (sx(x + w / 2), sy(y + h))
        if side == "left": return (sx(x), sy(y + h / 2))
        if side == "right": return (sx(x + w), sy(y + h / 2))
        return (sx(x + w / 2), sy(y + h / 2))

    for e in doc["edges"]:
        p1 = anchor(by_id[e["fromNode"]], e.get("fromSide", "bottom"))
        p2 = anchor(by_id[e["toNode"]], e.get("toSide", "top"))
        col = "#dc2626" if e.get("color") == "1" else "#475569"
        draw.line([p1, p2], fill=col, width=2 if e.get("color") == "1" else 1)
        # Arrowhead dot at target
        draw.ellipse([p2[0] - 3, p2[1] - 3, p2[0] + 3, p2[1] + 3], fill=col)

    # 3. Draw cards & wrap text
    overflows = []
    def wrap(txt, max_w, fnt):
        lines = []
        for para in txt.splitlines():
            words = para.split()
            if not words:
                lines.append("")
                continue
            cur = words[0]
            for w in words[1:]:
                cand = f"{cur} {w}"
                if draw.textlength(cand, font=fnt) <= max_w:
                    cur = cand
                else:
                    lines.append(cur)
                    cur = w
            lines.append(cur)
        return lines

    for n in doc["nodes"]:
        if n.get("type") != "text":
            continue
        x1, y1 = sx(n["x"]), sy(n["y"])
        x2, y2 = sx(n["x"] + n["width"]), sy(n["y"] + n["height"])
        fill, border = palette.get(n.get("color"), palette[None])
        draw.rounded_rectangle([x1, y1, x2, y2], radius=5, fill=fill, outline=border, width=2)
        fnt = font_title if n["id"] == "librarian-title" else font
        txt = re.sub(r"\*\*|\*|#", "", n.get("text", "")).strip()
        lines = wrap(txt, (x2 - x1) - 12, fnt)
        ty = y1 + 6
        lh = 14 if n["id"] != "librarian-title" else 18
        for ln in lines:
            if ty + lh > y2 - 2:
                overflows.append(n["id"])
                break
            draw.text((x1 + 6, ty), ln, fill="#0f172a", font=fnt)
            ty += lh

    img.save(out_path)
    return {"width": W, "height": H, "text_overflow_cards": sorted(set(overflows))}


def main() -> int:
    render = load_renderer()
    spec = render.load(SPEC_PATH)
    spec["_file"] = SPEC_PATH.name

    problems = render.validate(spec)
    all_paths = render.paths(spec)
    flags = render.cross_check(spec, all_paths) + render.check_references(spec, {spec["diagram"]: spec})
    tree, tests = render.tree_and_tests(spec, all_paths)

    views = "\n".join([
        f"<!-- generated by build_geographer_graph.py via render_spec.py from {SPEC_PATH.name}; regenerate, do not edit -->",
        "## Validation", "",
        ("No problems: the spec passes the activity rules." if not problems else "\n".join(f"- {x}" for x in problems)), "",
        "## Activity diagram (swimlanes)", "", "```mermaid", render.mermaid(spec), "```", "",
        "## Written use case (generated)", "", render.written_use_case(spec, all_paths), "",
        "## Lane load", "", render.lane_load(spec, all_paths), "",
        f"## Decision tree: {len(all_paths)} paths", "", tree, "",
        "## Test table: one test per path", "", tests, "",
        "## Cross-view check", "", ("No flags." if not flags else "\n".join(f"- {x}" for x in flags)), "",
    ])
    VIEWS_PATH.write_text(views, encoding="utf-8")

    canvas_doc = build_clean_canvas(spec, render)
    validate_document(canvas_doc)
    overlaps = check_overlaps(canvas_doc)

    # Use existing safe canvas preview -> commit service with profile=None
    previewed = service.preview(CANVAS_PATH, canvas_doc, profile=None)
    service.commit(CANVAS_PATH, previewed)
    saved_doc = json.loads(CANVAS_PATH.read_text(encoding="utf-8"))
    preview_meta = render_png_preview(saved_doc, PREVIEW_PATH)

    summary = {
        "source": SPEC_PATH.name,
        "source_sha256": hashlib.sha256(SPEC_PATH.read_bytes()).hexdigest(),
        "renderer": str(RENDER_SPEC_PATH.relative_to(REPO)),
        "structural_problems": problems,
        "cross_view_flags": flags,
        "numbered_main_steps": sum(1 for n in spec["nodes"] if n.get("step")),
        "paths": len(all_paths),
        "nodes": len(saved_doc["nodes"]),
        "edges": len(saved_doc["edges"]),
        "overlapping_cards": overlaps,
        "canvas_revision": content_revision(CANVAS_PATH),
        "preview": preview_meta,
    }
    VALIDATION_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if (problems or flags or overlaps) else 0


if __name__ == "__main__":
    raise SystemExit(main())
