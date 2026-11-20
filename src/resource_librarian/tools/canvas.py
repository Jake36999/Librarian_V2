"""Workflows on an Obsidian canvas, as tools (W2, 2026-11-20).

`canvas_compile` reads a drawn canvas and returns the workflow it describes, validated; the
person (or an agent, then the person) saves and accepts it with save_workflow / accept_workflow,
so a drawn workflow is pinned and approved exactly like a written one. `canvas_draw_workflow`
draws a workflow onto a canvas through the safe service: it previews by default, and writes only
with the revision and hash of that preview, never touching a node a person drew or moved.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .. import workflows
from ..canvas import service
from ..canvas.document import CanvasValidationError, load_document
from ..canvas.workflows import compile_canvas, draw_workflow
from ..registry import Card, Context, tool
from ..rules import Refusal


def _canvas_path(ctx: Context, path: str) -> Path:
    target = ctx.vault.safe_relative(path)          # inside the vault, no dot-folders
    if target.suffix.lower() != ".canvas":
        raise TypeError(f"{path!r} is not a .canvas file")
    return target


@tool("canvas_compile", tier="consult", effect="read", scope="library",
      card=Card("Compile a workflow drawn on an Obsidian canvas into its YAML, and validate it",
                "a person drew a workflow (a `role: workflow` node and `role: step` nodes) and "
                "wants it checked or saved",
                "Nothing is saved: pass the yaml to save_workflow, then a person accepts it"))
def canvas_compile(ctx: Context, path: str) -> dict:
    target = _canvas_path(ctx, path)
    if not target.is_file():
        raise TypeError(f"no canvas at {path!r}")
    try:
        payload = load_document(target)
    except CanvasValidationError as exc:
        return {"compiled": False, "errors": [d.get("message") for d in exc.diagnostics]}
    out = compile_canvas(payload)
    if out["errors"]:
        return {"compiled": False, "errors": out["errors"], "notes": out["notes"]}
    library = workflows.Library(ctx.vault)
    report = workflows.validate(workflows.parse(out["yaml"]), library)
    return {"compiled": report["valid"], "yaml": out["yaml"], "fingerprint": out["fingerprint"],
            "errors": report["errors"], "warnings": report["warnings"], "notes": out["notes"],
            "side_effects": report.get("side_effects", {}), "tier": report.get("tier"),
            "next": "save_workflow(yaml_text=...) to keep it; a person accepts it before it runs"
            if report["valid"] else "fix the drawing and compile again"}


@tool("canvas_draw_workflow", tier="contribute", effect="write", scope="library",
      card=Card("Draw a saved workflow onto an Obsidian canvas",
                "a person wants to see or edit a workflow as a canvas",
                "Previews unless commit is true with that preview's base_revision and "
                "proposal_hash; a canvas a person drew is never merged into"))
def canvas_draw_workflow(ctx: Context, name: str, path: str, commit: bool = False,
                         base_revision: str = "", proposal_hash: str = "") -> dict:
    target = _canvas_path(ctx, path)
    library = workflows.Library(ctx.vault)
    d = library.get(name)
    report = workflows.validate(d, library)
    generated = draw_workflow(d.data, side_effects=report.get("side_effects"))
    try:
        previewed = service.preview(target, generated, profile="dependency")
    except service.CanvasConflict as exc:
        raise Refusal("CANVAS_CONFLICT", str(exc)) from exc
    except CanvasValidationError as exc:
        raise Refusal("CANVAS_CONFLICT", f"{path} is not a valid canvas, so it is left as it "
                                         f"is: {exc}") from exc
    rel = target.relative_to(ctx.vault.root).as_posix()
    if not commit:
        return {"preview": rel, "base_revision": previewed["base_revision"],
                "proposal_hash": previewed["proposal_hash"], "changes": previewed["changes"],
                "next": "canvas_draw_workflow(..., commit=true, base_revision, proposal_hash)"}
    if base_revision != previewed["base_revision"] or proposal_hash != previewed["proposal_hash"]:
        raise Refusal("CANVAS_CONFLICT", "the canvas or the drawing changed since that preview: "
                                         "preview again")
    try:
        written = service.commit(target, previewed)
    except service.CanvasConflict as exc:
        raise Refusal("CANVAS_CONFLICT", str(exc)) from exc
    return {"written": rel, "revision": written["revision"], "changes": written["changes"],
            "backup": Path(written["backup"]).name if written["backup"] else ""}
