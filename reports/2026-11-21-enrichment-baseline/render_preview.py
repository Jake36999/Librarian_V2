"""Draw review PNGs from the saved canvas geometry, without changing the canvas."""
from __future__ import annotations

import json
import importlib.util
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = Path("C:/Windows/Fonts/segoeui.ttf")
COLORS = {"1": ("#fff0f0", "#c84949"), "2": ("#fff2df", "#b77922"),
          "3": ("#fff6d6", "#ad9022"), "4": ("#e8f4ec", "#428259"),
          "5": ("#eeeafa", "#8267aa"), "6": ("#e6f1fa", "#4a7a9b")}
_routing_definition = importlib.util.spec_from_file_location("report_preview_routing", HERE / "edge_routing.py")
_routing = importlib.util.module_from_spec(_routing_definition)
_routing_definition.loader.exec_module(_routing)


def anchor(card, side):
    x, y, w, h = (card[key] for key in ("x", "y", "width", "height"))
    return {"left": (x, y + h / 2), "right": (x + w, y + h / 2),
            "top": (x + w / 2, y), "bottom": (x + w / 2, y + h)}[side]


def render(doc, destination, bounds, scale, title):
    x0, y0, x1, y1 = bounds
    image = Image.new("RGB", (int((x1 - x0) * scale), int((y1 - y0) * scale) + 58), "#fafafa")
    draw = ImageDraw.Draw(image)
    # Keep text proportional to the saved card geometry. A minimum 9px font at
    # .35 scale enlarged text relative to cards and clipped otherwise fitting labels.
    font = ImageFont.truetype(str(FONT), max(3, round(17 * scale)))
    label_font = ImageFont.truetype(str(FONT), max(3, round(19 * scale)))

    def point(p):
        return ((p[0] - x0) * scale, (p[1] - y0) * scale + 58)

    by_id = {node["id"]: node for node in doc["nodes"]}
    for node in doc["nodes"]:
        if node["type"] != "group":
            continue
        draw.rectangle([point((node["x"], max(node["y"], y0))),
                        point((node["x"] + node["width"], min(node["y"] + node["height"], y1)))],
                       outline="#c8cdd2", width=1)
        draw.text(point((node["x"] + 8, max(node["y"] + 4, y0 + 4))), node["label"], fill="#43505e", font=label_font)

    for edge in doc["edges"]:
        curve = [point(coordinate) for coordinate in _routing.curve_points(edge, by_id)]
        color = "#c84949" if edge.get("color") == "1" else "#a5adb7"
        draw.line(curve, fill=color, width=max(1, int(1.6 * scale)))

    clipped = []
    for node in doc["nodes"]:
        if node["type"] != "text" or node["y"] > y1 or node["y"] + node["height"] < y0:
            continue
        left, top = point((node["x"], node["y"]))
        right, bottom = point((node["x"] + node["width"], node["y"] + node["height"]))
        fill, stroke = COLORS.get(node.get("color"), ("#ffffff", "#9ca7b3"))
        draw.rounded_rectangle((left, top, right, bottom), radius=max(2, int(7 * scale)), fill=fill, outline=stroke, width=1)
        raw = re.sub(r"[*`]+", "", node.get("text", ""))
        lines = []
        line = ""
        max_width = max(8, right - left - 16 * scale)
        for word in raw.split():
            candidate = (line + " " + word).strip()
            if line and draw.textlength(candidate, font=font) > max_width:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        text_y = top + max(1, 7 * scale)
        line_height = max(4, round(21 * scale))
        for line in lines:
            if text_y + line_height > bottom - max(1, 3 * scale):
                clipped.append(node["id"])
                break
            draw.text((left + max(1, 8 * scale), text_y), line, fill="#253140", font=font)
            text_y += line_height
    draw.rectangle((0, 0, image.width, 57), fill="#fafafa")
    draw.text((12, 8), title, fill="#253140", font=ImageFont.truetype(str(FONT), 20))
    draw.text((12, 34), "Saved canvas geometry; review preview. Open the .canvas to inspect text, guards and connections at full size.", fill="#596674", font=ImageFont.truetype(str(FONT), 13))
    image.save(destination)
    return sorted(set(clipped))


def main():
    doc = json.loads((HERE / "enrichment-cycle.canvas").read_text(encoding="utf-8"))
    nodes = {node["id"].removeprefix("librarian-"): node for node in doc["nodes"]}
    bottom = max(node["y"] + node["height"] for node in doc["nodes"])
    # The overview deliberately emphasizes the shape; the stage detail remains readable.
    render(doc, HERE / "overview.png", (0, -220, 4640, bottom + 30), .28, "Complete enrichment cycle")
    start, end = nodes["a16"]["y"] - 70, nodes["a29"]["y"] + 220
    clipped = render(doc, HERE / "source-stages.png", (2100, start, 4230, end), .80, "Source enrichment stages within the complete cycle")
    (HERE / "preview-validation.json").write_text(json.dumps({
        "source_stage_text_overflow": clipped,
        "preview": "deterministic raster of saved canvas positions; not an Obsidian application screenshot",
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"source_stage_text_overflow": clipped, "overview": "overview.png", "detail": "source-stages.png"}))


if __name__ == "__main__":
    main()
