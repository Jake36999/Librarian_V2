"""W2 (owner, 2026-11-20): the Librarian reads and writes Obsidian canvases without ever losing
a person's work, and a workflow can be drawn on a canvas and compiled back."""
import copy
import json

import pytest

from resource_librarian import tools, workflows  # noqa: F401
from resource_librarian.canvas import service
from resource_librarian.canvas.document import CanvasValidationError, load_document
from resource_librarian.canvas.workflows import compile_canvas, draw_workflow, fingerprint
from resource_librarian.registry import REGISTRY

from test_workflows import GOOD, person


def text_node(node_id, text, x=0, y=0):
    return {"id": node_id, "type": "text", "text": text, "x": x, "y": y, "width": 300, "height": 120}


def generated(*ids):
    return {"nodes": [text_node(f"librarian-{i}", i) for i in ids],
            "edges": [{"id": f"librarian-{a}-{b}", "fromNode": f"librarian-{a}",
                       "toNode": f"librarian-{b}"} for a, b in zip(ids, ids[1:])]}


# ----------------------------------------------------------------------------- the document

def test_a_malformed_canvas_is_reported_and_never_replaced(tmp_path):
    path = tmp_path / "broken.canvas"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CanvasValidationError):
        service.preview(path, generated("a"))
    assert path.read_text(encoding="utf-8") == "{not json"


def test_unknown_fields_survive_a_write(tmp_path):
    path = tmp_path / "x.canvas"
    service.write(path, generated("a"))
    data = json.loads(path.read_text(encoding="utf-8"))
    data["plugin_extension"] = {"keep": True}
    data["nodes"][0]["colour_scheme"] = "mine"
    path.write_text(json.dumps(data), encoding="utf-8")
    service.write(path, generated("a", "b"))
    after = load_document(path)
    assert after["plugin_extension"] == {"keep": True}
    assert next(n for n in after["nodes"] if n["id"] == "librarian-a")["colour_scheme"] == "mine"


# ----------------------------------------------------------------------------- preview and commit

def test_a_preview_writes_nothing_and_a_commit_writes_with_a_backup(tmp_path):
    path = tmp_path / "x.canvas"
    service.write(path, generated("a"))
    before = path.read_bytes()
    previewed = service.preview(path, generated("a", "b"))
    assert path.read_bytes() == before
    assert previewed["changes"]["added"] == ["librarian-b"]
    written = service.commit(path, previewed)
    assert written["backup"].endswith(".bak") and (tmp_path / written["backup"]).exists()
    assert {n["id"] for n in load_document(path)["nodes"]} == {"librarian-a", "librarian-b"}


def test_a_commit_is_refused_if_the_canvas_changed_or_the_proposal_was_altered(tmp_path):
    path = tmp_path / "x.canvas"
    service.write(path, generated("a"))
    previewed = service.preview(path, generated("a", "b"))
    tampered = copy.deepcopy(previewed)
    tampered["proposal"]["nodes"].append(text_node("librarian-evil", "x"))
    with pytest.raises(service.CanvasConflict, match="not the one previewed"):
        service.commit(path, tampered)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["nodes"].append(text_node("mine", "a person's card", 900, 900))
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(service.CanvasConflict, match="changed since it was previewed"):
        service.commit(path, previewed)


def test_a_persons_canvas_is_never_merged_into(tmp_path):
    path = tmp_path / "mine.canvas"
    path.write_text(json.dumps({"nodes": [text_node("idea", "my drawing")], "edges": []}),
                    encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(service.CanvasConflict, match="a person's canvas"):
        service.write(path, generated("a"))
    assert path.read_bytes() == before
    service.write(path, generated("a"), adopt=True)           # only when the caller says so
    assert {n["id"] for n in load_document(path)["nodes"]} == {"idea", "librarian-a"}


def test_a_persons_nodes_and_moves_are_kept_when_the_view_is_regenerated(tmp_path):
    path = tmp_path / "x.canvas"
    service.write(path, generated("a", "b"))
    data = json.loads(path.read_text(encoding="utf-8"))
    moved = next(n for n in data["nodes"] if n["id"] == "librarian-b")
    moved["x"], moved["y"] = 5000, 5000                       # a person moved it
    data["nodes"].append(text_node("note", "my annotation", -800, 0))
    data["edges"].append({"id": "mine-1", "fromNode": "note", "toNode": "librarian-a"})
    path.write_text(json.dumps(data), encoding="utf-8")
    service.write(path, generated("a", "b", "c"))
    after = {n["id"]: n for n in load_document(path)["nodes"]}
    assert (after["librarian-b"]["x"], after["librarian-b"]["y"]) == (5000, 5000)
    assert after["note"]["text"] == "my annotation" and (after["note"]["x"], after["note"]["y"]) == (-800, 0)
    assert any(e["id"] == "mine-1" for e in load_document(path)["edges"])
    assert "librarian-c" in after


def test_a_generated_node_must_carry_the_managed_prefix(tmp_path):
    with pytest.raises(ValueError, match="managed prefix"):
        service.preview(tmp_path / "x.canvas", {"nodes": [text_node("plain", "x")], "edges": []})


# ----------------------------------------------------------------------------- canvas <-> workflow

def test_every_shipped_workflow_survives_a_round_trip_through_a_canvas():
    library = workflows.Library(None)
    keys = ("id", "action", "args", "each", "when", "on_error", "depends_on")
    for d in library._standard():
        if d.kind != "workflow" or any("action" not in s for s in d.data["steps"]):
            continue
        out = compile_canvas(draw_workflow(d.data))
        assert not out["errors"], (d.name, out["errors"])
        back = out["definition"]
        assert [{k: s[k] for k in keys if k in s} for s in back["steps"]] == \
            [{k: s[k] for k in keys if k in s} for s in d.data["steps"]], d.name
        for field in ("inputs", "outputs", "macro", "tier"):
            assert back.get(field) == d.data.get(field), (d.name, field)
        assert workflows.validate(workflows.parse(out["yaml"]), library)["valid"], d.name


DRAWN = {
    "nodes": [
        text_node("w", "role: workflow\nworkflow: drawn-review\ninput query: string\n"
                       "output verdict: steps.found.verdict\n\n"
                       "search for something and review the first staged item", 0, 0),
        text_node("s1", "role: step\nid: found\naction: search\narg query: inputs.query\n"
                        "arg limit: 3\n\nlook it up", 0, 300),
        text_node("s2", "role: step\nid: waiting\naction: staging_list\narg kind: source", 0, 600),
        text_node("n", "a note to myself about this drawing", 600, 300),
    ],
    "edges": [{"id": "e1", "fromNode": "w", "toNode": "s1"},
              {"id": "e2", "fromNode": "s1", "toNode": "s2", "label": "then"}],
}


def test_a_drawn_workflow_compiles_and_a_note_does_nothing():
    out = compile_canvas(DRAWN)
    assert out["errors"] == []
    assert [s["id"] for s in out["definition"]["steps"]] == ["found", "waiting"]
    assert out["definition"]["steps"][0]["args"] == {"query": {"from": "inputs.query"}, "limit": 3}
    assert any("note" in n and "'n'" in n for n in out["notes"])


def test_moving_nodes_changes_neither_the_workflow_nor_its_fingerprint():
    moved = copy.deepcopy(DRAWN)
    for node in moved["nodes"]:
        node["x"], node["y"] = node["y"], -node["x"] - 1000
    assert compile_canvas(moved)["yaml"] == compile_canvas(DRAWN)["yaml"]
    assert fingerprint(moved) == fingerprint(DRAWN)
    edited = copy.deepcopy(DRAWN)
    edited["nodes"][1]["text"] = edited["nodes"][1]["text"].replace("limit: 3", "limit: 4")
    assert fingerprint(edited) != fingerprint(DRAWN)


@pytest.mark.parametrize("change, why", [
    (lambda c: c["nodes"][1].update(text="role: step\nid: found"), "names no action"),
    (lambda c: c["nodes"].pop(0), "no `role: workflow` node"),
    (lambda c: c["edges"].append({"id": "back", "fromNode": "s2", "toNode": "s1"}), "cycle"),
    (lambda c: c["nodes"][2].update(text="role: step\nid: found\naction: staging_list"), "share an id"),
    (lambda c: c["nodes"][2].update(text="role: step\nid: w2\naction: staging_list\nmagic: on"),
     "unknown directive"),
])
def test_a_drawing_that_cannot_mean_one_workflow_is_refused(change, why):
    drawing = copy.deepcopy(DRAWN)
    change(drawing)
    errors = compile_canvas(drawing)["errors"]
    assert any(why in e for e in errors), errors


def test_a_needs_edge_is_a_dependency_and_a_then_edge_only_orders():
    drawing = copy.deepcopy(DRAWN)
    drawing["edges"][1]["label"] = "needs"
    steps = compile_canvas(drawing)["definition"]["steps"]
    assert steps[1]["depends_on"] == ["found"]
    assert "depends_on" not in compile_canvas(DRAWN)["definition"]["steps"][1]


# ----------------------------------------------------------------------------- the tools, end to end

def test_drawn_compiled_saved_and_run_it_matches_the_written_workflow(vault):
    """W2's done-when: a workflow drawn by hand, compiled, accepted and run gives what the
    same workflow written as YAML gives."""
    (vault.root / "Drawn.canvas").write_text(json.dumps(DRAWN), encoding="utf-8")
    compiled = REGISTRY.call("canvas_compile", {"path": "Drawn.canvas"}, person(vault))
    assert compiled["compiled"], compiled
    saved = REGISTRY.call("save_workflow", {"yaml_text": compiled["yaml"]}, person(vault))
    assert "error" not in saved, saved
    REGISTRY.call("save_workflow", {"yaml_text": GOOD}, person(vault))
    drawn = REGISTRY.call("run_workflow", {"name": "drawn-review", "inputs": {"query": "x"}},
                          person(vault))
    written = REGISTRY.call("run_workflow", {"name": "find-and-review", "inputs": {"query": "x"}},
                            person(vault))
    assert drawn["status"] == written["status"] == "finished"
    assert drawn["outputs"] == written["outputs"]
    assert drawn["steps"].keys() == written["steps"].keys()


def test_drawing_a_workflow_previews_then_commits_and_spares_a_persons_canvas(vault):
    args = {"name": "deep-read-staged", "path": "Maps/deep-read.canvas"}
    previewed = REGISTRY.call("canvas_draw_workflow", args, person(vault))
    assert not (vault.root / "Maps/deep-read.canvas").exists()
    stale = REGISTRY.call("canvas_draw_workflow", {**args, "commit": True, "base_revision": "x",
                                                   "proposal_hash": previewed["proposal_hash"]},
                          person(vault))
    assert stale.get("refused") == "CANVAS_CONFLICT"
    written = REGISTRY.call("canvas_draw_workflow", {
        **args, "commit": True, "base_revision": previewed["base_revision"],
        "proposal_hash": previewed["proposal_hash"]}, person(vault))
    assert written["written"] == "Maps/deep-read.canvas"
    compiled = REGISTRY.call("canvas_compile", {"path": "Maps/deep-read.canvas"}, person(vault))
    assert compiled["compiled"] and "deep_read" in compiled["yaml"]
    (vault.root / "Mine.canvas").write_text(json.dumps({"nodes": [text_node("idea", "x")]}),
                                            encoding="utf-8")
    refused = REGISTRY.call("canvas_draw_workflow", {"name": "deep-read-staged",
                                                     "path": "Mine.canvas"}, person(vault))
    assert refused.get("refused") == "CANVAS_CONFLICT"


@pytest.mark.parametrize("arg, expected", [
    ("arg query: the owner said: do it", "the owner said: do it"),      # a sentence stays one
    ("arg query: Doctor (Lead, tier 1)", "Doctor (Lead, tier 1)"),
    ("arg limit: 3", 3),
])
def test_a_plain_value_stays_what_it_says(arg, expected):
    drawing = copy.deepcopy(DRAWN)
    drawing["nodes"][1]["text"] = f"role: step\nid: found\naction: search\n{arg}"
    out = compile_canvas(drawing)
    assert out["errors"] == []
    name = arg.split(":", 1)[0].split(" ", 1)[1]
    assert out["definition"]["steps"][0]["args"][name] == expected


def test_a_comma_that_splits_a_written_mapping_is_refused():
    """Found by the diagram-workflows session: {lane: Doctor (Lead, tier 1)} silently became
    {'lane': 'Doctor (Lead', 'tier 1)': None}."""
    drawing = copy.deepcopy(DRAWN)
    drawing["nodes"][2]["text"] = ("role: step\nid: waiting\naction: staging_list\n"
                                   "when: {from: steps.found.verdict, is: Doctor (Lead, tier 1)}")
    errors = compile_canvas(drawing)["errors"]
    assert any("split" in e and "quote" in e for e in errors), errors
    drawing["nodes"][2]["text"] = ("role: step\nid: waiting\naction: staging_list\n"
                                   'when: {from: steps.found.verdict, is: "Doctor (Lead, tier 1)"}')
    out = compile_canvas(drawing)
    assert out["errors"] == []
    assert out["definition"]["steps"][1]["when"]["is"] == "Doctor (Lead, tier 1)"
