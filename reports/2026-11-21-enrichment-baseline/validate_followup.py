"""Check the saved current-code follow-up artifacts; never commit a live canvas."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path
from urllib.parse import unquote

from PIL import Image, ImageDraw, ImageFont

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
ING = ROOT / "reports/2026-11-20-workflow-map/examples/ingestion"
FOCUSED = ROOT / "reports/2026-11-22-proposed-tobe-enrichment"


def module(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(result)
    return result


def text_overflow(document, scale):
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", max(3, round(17 * scale)))
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    clipped = []
    for node in document["nodes"]:
        if node["type"] != "text":
            continue
        lines, line = [], ""
        for word in re.sub(r"[*`]+", "", node.get("text", "")).split():
            candidate = (line + " " + word).strip()
            if line and draw.textlength(candidate, font=font) > max(8, (node["width"] - 16) * scale):
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
        required = max(1, 7 * scale) + len(lines) * max(4, round(21 * scale))
        if required > node["height"] * scale - max(1, 3 * scale):
            clipped.append(node["id"])
    return clipped


def main():
    layout = module("followup_layout", BASE / "build_artifacts.py")
    author = module("followup_ingestion", ING / "render_corrected.py")
    render = layout.renderer()
    from resource_librarian.canvas import service
    from resource_librarian.canvas.document import proposal_hash, validate_document

    library, locations = author.spec_library(render)
    configurations = [
        ("ingestion", ING, "ingestion.canvas", "ingestion.correction-validation.json", .35),
        ("ingestion-tobe", ING, "accepted-ingestion-tobe.canvas", "ingestion-tobe.correction-validation.json", .35),
        ("source-enrichment-current", BASE, "source-enrichment-current.canvas", "source-enrichment-current.validation.json", .36),
        ("batch-enrichment-current", BASE, "batch-enrichment-current.canvas", "batch-enrichment-current.validation.json", .36),
        ("proposed-tobe-enrichment", FOCUSED, "proposed-tobe-enrichment.canvas", "validation.json", .28),
    ]
    results, specs, documents = [], {}, {}
    for stem, directory, canvas_name, receipt_name, scale in configurations:
        path, source = directory / canvas_name, directory / f"{stem}.spec.yaml"
        original = path.read_bytes()
        spec = render.load(source)
        spec["_file"] = source.name
        problems, scenarios = layout.checks(spec, render, library)
        assert not problems, (stem, problems)
        saved = json.loads(original)
        assert not [x for x in validate_document(saved) if x.get("severity") != "warning"]
        assert not layout.overlaps(saved), stem
        generated = layout.managed_canvas(spec, render)
        nodes = {n["id"]: n for n in saved["nodes"]}
        groups = {n["label"]: n for n in saved["nodes"] if n["type"] == "group"}
        for expected in generated["nodes"]:
            actual = nodes[expected["id"]]
            if actual["type"] == "text":
                assert actual["text"] == expected["text"], (stem, actual["id"], "text")
                if actual["id"] != "librarian-title":
                    assert (actual["width"], actual["height"]) == (expected["width"], expected["height"])
        for node in spec["nodes"]:
            if not node.get("lane"):
                continue
            card, group = nodes["librarian-" + node["id"]], groups[node["lane"]]
            assert group["x"] <= card["x"] and card["x"] + card["width"] <= group["x"] + group["width"]
            assert group["y"] <= card["y"] and card["y"] + card["height"] <= group["y"] + group["height"]
        main_path = render.main_path(spec)
        assert all(nodes["librarian-" + b]["y"] > nodes["librarian-" + a]["y"] for a, b in zip(main_path, main_path[1:]))
        assert all(e.get("fromSide") in ("top", "bottom", "left", "right") and e.get("toSide") in ("top", "bottom", "left", "right") for e in saved["edges"])
        assert not layout.routing().intersections(saved), (stem, "edge/card intersection")
        assert not text_overflow(saved, 1), (stem, "native text")
        assert not text_overflow(saved, scale), (stem, "overview text")
        assert not text_overflow(saved, .8), (stem, "detail text")
        if directory == ING:
            _, preview, _, _ = author.prepare(stem, render, layout, library, locations)
        else:
            preview = layout.actor_preview(path, generated, spec, validation_path=directory / receipt_name)
        assert preview["proposal"] == saved, (stem, "repeat preview")
        receipt = json.loads((directory / receipt_name).read_text(encoding="utf-8"))
        assert proposal_hash(saved) == receipt.get("canvas_revision", receipt.get("proposal_hash"))
        source_hash = next(receipt[k] for k in ("spec_sha256", "source_sha256", "model_sha256") if k in receipt)
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
        assert path.read_bytes() == original
        results.append(dict(model=stem, canvas=path.relative_to(ROOT).as_posix(), nodes=len(saved["nodes"]),
                            edges=len(saved["edges"]), steps=sum(bool(n.get("step")) for n in spec["nodes"]),
                            scenarios=len(scenarios), structural_reference_flags=[], card_overlaps=[],
                            edge_card_intersections=[],
                            physical_lanes_and_labels="verified", main_flow="forward", repeat_preview="identical",
                            native_text_overflow=[], overview_text_overflow=[], detail_text_overflow=[],
                            canvas_sha256=proposal_hash(saved)))
        specs[stem], documents[stem] = spec, saved

    def nodes(stem):
        return {n["id"]: n for n in specs[stem]["nodes"]}

    def pairs(stem):
        return {(e["from"], e["to"]) for e in specs[stem]["edges"]}

    for stem in ("ingestion", "ingestion-tobe"):
        assert {("a7", "applygroups"), ("applygroups", "applicationreceipt"), ("applicationreceipt", "dfolder")} <= pairs(stem)
        assert "wholeindex" not in nodes(stem)
    assert not {"indexcheck", "dindex", "indexfault"} & nodes("ingestion").keys()
    assert nodes("ingestion")["enrich"]["use_case"] == "batch-enrichment-current"
    assert "Model worker (legacy transport)" in specs["ingestion"]["lanes"]
    assert "proposed" in nodes("ingestion-tobe")["indexcheck"]["label"]
    assert nodes("batch-enrichment-current")["source"]["use_case"] == "source-enrichment-current"
    assert nodes("batch-enrichment-current")["folderdescribe"]["lane"] == "Model worker (legacy transport)"
    for name in ("foldervalidate", "foldercheck", "folderdata", "foldercoverage"):
        assert nodes("batch-enrichment-current")[name]["lane"] == "Core"
    outcomes = {"success", "partial", "paused", "reused", "escalated"}
    for stem in ("source-enrichment-current", "batch-enrichment-current"):
        assert {render.outcome(n) for n in specs[stem]["nodes"] if n["kind"] == "end"} == outcomes
    for parent, call in (("ingestion", "enrich"), ("batch-enrichment-current", "source")):
        assert {e.get("guard") for e in specs[parent]["edges"] if e["from"] == call} == outcomes
    cards = {n["id"].removeprefix("librarian-"): n for n in documents["source-enrichment-current"]["nodes"]}
    assert all(cards[n]["y"] < cards["read"]["y"] for n in ("conversioncheck", "dconversion", "fallback", "parsegap", "preproject"))
    assert cards["stopped"]["y"] < cards["validate"]["y"]
    assert cards["relatestatic"]["y"] < cards["drelate"]["y"]
    assert max(cards[n]["y"] for n in ("pubna", "pubgap")) < cards["reduce"]["y"]
    assert [(e["from"], e["to"]) for e in specs["source-enrichment-current"]["edges"] if cards[e["to"]]["y"] < cards[e["from"]]["y"]] == [("dmore", "controls")]

    broad_path = BASE / "enrichment-cycle.canvas"
    broad_raw = broad_path.read_bytes()
    broad_hash = proposal_hash(json.loads(broad_raw))
    assert broad_hash == "5a2f45feb02259201c867caf5fd55d7102911aa5330341173c9dc2b7f6b5bf0b"
    broad_model = render.load(BASE / "enrichment-cycle.spec.yaml")
    try:
        layout.actor_preview(broad_path, layout.managed_canvas(broad_model, render), broad_model, reflow_generated=True)
    except service.CanvasConflict:
        pass
    else:
        raise AssertionError("Owner-edited comprehensive canvas reflow allowed")
    assert broad_path.read_bytes() == broad_raw

    with tempfile.TemporaryDirectory(prefix="graph-followup-", dir=BASE) as scratch:
        assert Path(scratch).resolve().is_relative_to(BASE.resolve())
        target = Path(scratch) / "current.canvas"
        original = copy.deepcopy(documents["source-enrichment-current"])
        manual = copy.deepcopy(original)
        manual["owner_note"] = {"keep": ["manual", "metadata"]}
        moved = next(n for n in manual["nodes"] if n["id"] == "librarian-parse")
        moved["y"] += 10
        moved["librarian"]["owner_note"] = {"keep": True}
        manual["nodes"].append(dict(id="owner-note", type="text", text="Owner annotation", x=5000, y=140, width=360, height=150))
        manual["edges"].append(dict(id="owner-edge", fromNode="librarian-parse", toNode="owner-note", fromSide="right", toSide="left", owner_note=True))
        target.write_text(json.dumps(manual), encoding="utf-8")
        (Path(scratch) / "validation.json").write_text(json.dumps({"canvas_revision": proposal_hash(original)}), encoding="utf-8")
        spec = specs["source-enrichment-current"]
        generated = layout.managed_canvas(spec, render)
        preview = layout.actor_preview(target, generated, spec)
        candidate = preview["proposal"]
        assert candidate["owner_note"] == manual["owner_note"]
        for collection in ("nodes", "edges"):
            assert {n["id"]: n for n in candidate[collection]} == {n["id"]: n for n in manual[collection]}
        try:
            layout.actor_preview(target, generated, spec, reflow_generated=True)
        except service.CanvasConflict:
            pass
        else:
            raise AssertionError("manual edit reflow allowed")
        try:
            layout.actor_preview(target, generated, spec, reroute_generated=True)
        except service.CanvasConflict:
            pass
        else:
            raise AssertionError("manual edit reroute allowed")
        manual["concurrent_edit"] = True
        target.write_text(json.dumps(manual), encoding="utf-8")
        try:
            service.commit(target, preview)
        except service.CanvasConflict:
            pass
        else:
            raise AssertionError("concurrent edit commit allowed")

    requirement_text = (BASE / "requirements-evidence.md").read_text(encoding="utf-8")
    rows = [line for line in requirement_text.splitlines() if re.match(r"^\| [EPC]\d\d\b", line)]
    requirement_ids = {re.match(r"^\| ([EPC]\d\d)", line)[1] for line in rows}
    assert len(requirement_ids) == 34
    node_ids = {n["id"] for n in broad_model["nodes"]}
    extension_ids = {str(e["ext"]) for e in broad_model["edges"] if e.get("ext")}
    mapping_rows = [line for line in rows if len(line.split("|")) == 5]
    assert len(mapping_rows) == 34
    for line in mapping_rows:
        for identifier in re.findall(r"`([^`]+)`", line.split("|")[2]):
            assert identifier in node_ids or identifier in extension_ids, ("requirement mapping", identifier)

    files = list(BASE.glob("*.md")) + list(FOCUSED.glob("*.md")) + [
        ING / name for name in ("INGESTION-EXAMPLE.md", "INGESTION-TOBE.md", "ingestion.views.md", "ingestion-tobe.views.md")]
    files += [ROOT / "reports" / name for name in (
        "2026-11-20-workflow-map/USE-CASES.md", "2026-11-22-ingestion-enrichment-graph-review.md", "2026-11-23-current-graph-followup.md")]
    links = 0
    for source in files:
        for destination in re.findall(r"\]\(([^\n]+?)\)", source.read_text(encoding="utf-8")):
            value = destination.strip().strip("<>")
            if re.match(r"^[a-zA-Z][\w+.-]*:", value) or value.startswith("#"):
                continue
            value = unquote(value.split("#", 1)[0])
            if value:
                assert (source.parent / value).exists(), (str(source), value)
                links += 1

    output = ROOT / "reports/2026-11-23-ingestion-enrichment-validation.json"
    archive = output.with_name(output.stem + ".before-current-followup.json")
    if not archive.exists():
        archive.write_bytes(output.read_bytes())
    routing_archive = output.with_name(output.stem + ".before-native-routing.json")
    if not routing_archive.exists():
        routing_archive.write_bytes(output.read_bytes())
    receipt = dict(
        completed_on="2026-11-23", scope="current-code follow-up and native routing correction: report artifacts; no runtime or library processing",
        previous_validation=routing_archive.relative_to(ROOT).as_posix(), models=results,
        preserved_owner_edited_canvas=dict(canvas=broad_path.relative_to(ROOT).as_posix(), canvas_sha256=broad_hash,
            status="saved Owner edits preserved; reflow correctly refused; previous layout receipt does not certify current manual geometry"),
        semantic_boundaries="passed", manual_preservation_and_reflow_refusal="passed on fresh scratch copy and preserved comprehensive canvas",
        concurrent_edit_commit_refusal="passed on fresh scratch copy", requirement_mappings=len(requirement_ids),
        local_links_checked=links, new_paid_model_calls=0, new_model_spend_usd=0)
    receipt["curve_check_scope"] = "actual deterministic preview polyline including endpoint cards; native attachment fields only"
    output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(models=[{k: m[k] for k in ("model", "nodes", "edges", "steps", "scenarios")} for m in results],
                         requirement_mappings=len(requirement_ids), local_links_checked=links,
                         owner_edits_preserved=True, guards="passed", validation=str(output)), indent=2))


if __name__ == "__main__":
    main()
