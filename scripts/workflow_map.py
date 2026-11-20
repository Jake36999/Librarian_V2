#!/usr/bin/env python
"""workflow_map: draw the Librarian's workflows from its own code (owner, 2026-11-20).

The Librarian turned on itself: nothing here is written by hand or by a model. It reads

- the session purposes and their phases (`session.PURPOSES`), and for each phase the exit gate a
  model actually sees (a session forced into the phase, its `missing()` text) and the tools the
  live loop offers there (`phase_walk.Walker`, the same enforced surface);
- the YAML workflows and pipelines shipped in `standard/`;
- the agent macros (`agent_runtime.MACROS`);
- the source batch stages and folder stages (`batch.STAGES`, `batch.FOLDER_STAGES`);

and writes them as Mermaid (in one Markdown file, which Obsidian renders and draw.io imports via
Arrange > Insert > Advanced > Mermaid) and as an Obsidian canvas.

    python scripts/workflow_map.py --out reports/2026-11-20-workflow-map
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import phase_walk  # noqa: E402  (sets up the offline environment and registers every tool)
import yaml  # noqa: E402

from resource_librarian import batch  # noqa: E402
from resource_librarian.agent_runtime import MACROS  # noqa: E402
from resource_librarian.session import PURPOSES  # noqa: E402
from resource_librarian.phases import DECLARATION, TAIL as DECLARED_TAIL  # noqa: E402

STANDARD = ROOT / "src" / "resource_librarian" / "standard"
# Tools every phase offers (the tail); listing them on every node is noise.
TAIL = set(DECLARED_TAIL) | {"ask_user", "advance"}


def label(text: str, n: int = 160) -> str:
    """Text safe inside a Mermaid ["..."] label."""
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = text.replace('"', "'").replace("[", "(").replace("]", ")").replace("{", "(") \
        .replace("}", ")").replace("|", "/").replace("<", "‹").replace(">", "›").replace("#", "")
    return text if len(text) <= n else text[: n - 1] + "…"


# ----------------------------------------------------------------------------- gather

def gather_phases() -> dict[str, list[dict]]:
    """purpose -> [{phase, gate, offered}] from a seeded throwaway vault, no model."""
    out: dict[str, list[dict]] = {}
    tmp = Path(tempfile.mkdtemp(prefix="workflow-map-"))
    try:
        vault = phase_walk.seeded_vault(tmp / "v")
        for purpose, phases in PURPOSES.items():
            w = phase_walk.Walker(vault, "consult" if purpose == "apply" else "contribute")
            opened = w.open(purpose, project="P" if purpose != "explore" else "", question="q")
            if "error" in opened:
                out[purpose] = [{"phase": "*", "gate": f"could not open: {opened.get('detail', '')}",
                                 "offered": []}]
                continue
            rows = []
            for phase in phases:
                w.force_phase(phase)
                try:
                    gate = w.missing()
                except Exception as exc:  # noqa: BLE001 - a map shows what it cannot read
                    gate = [f"(gate not readable: {type(exc).__name__})"]
                declared = DECLARATION.phases[phase]
                rows.append({"phase": phase, "gate": gate,
                             "offered": sorted(set(w.offered()) - TAIL),
                             # W1: what phases.yaml declares, read directly
                             "ask": declared.ask, "budget": declared.budget,
                             "assumptions": declared.assumptions,
                             "checks": [g.check for g in declared.gate],
                             "remedies": sorted({r.tool for r in declared.remedies(purpose)})})
            out[purpose] = rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def gather_yaml(kind: str) -> list[dict]:
    rows = []
    for path in sorted((STANDARD / kind).glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        steps = [{"id": s.get("id", ""), "does": s.get("action") or s.get("workflow") or
                  ("route" if s.get("route") else "?"), "each": bool(s.get("each")),
                  "kind": "workflow" if s.get("workflow") else "route" if s.get("route") else "action"}
                 for s in data.get("steps") or []]
        # W1 part 3: what each step can touch, from the validator (derived from its action).
        from resource_librarian import workflows as wf
        library = wf.Library(None)
        report = wf.validate(wf.parse(path.read_text(encoding="utf-8")), library)
        for row in steps:
            row["side_effects"] = report.get("side_effects", {}).get(row["id"], "")
            row["depends_on"] = next((list(s.get("depends_on") or []) for s in data.get("steps") or []
                                      if s.get("id") == row["id"]), [])
        rows.append({"name": data.get(kind[:-1]) or path.stem, "purpose": data.get("purpose", ""),
                     "steps": steps, "side_effects_max": report.get("side_effects_max", "")})
    return rows


def gather_macros() -> list[dict]:
    return [{"name": m.id, "purpose": m.purpose if hasattr(m, "purpose") else "",
             "steps": [s.tool for s in m.steps], "writes": getattr(m, "write_capable", False)}
            for m in MACROS.values()]


# ----------------------------------------------------------------------------- render

def mermaid_purpose(purpose: str, rows: list[dict]) -> str:
    lines = ["flowchart TD"]
    for i, r in enumerate(rows):
        gate = "; ".join(r["gate"]) if r["gate"] else "nothing: advance"
        tools = ", ".join(r["offered"][:10]) + (" …" if len(r["offered"]) > 10 else "")
        remedies = ", ".join(r.get("remedies") or [])
        lines.append(f'  p{i}["<b>{label(r["phase"], 40)}</b><br/>{label(r.get("ask", ""), 120)}'
                     f'<br/>to leave: {label(gate)}<br/>gate uses: {label(remedies, 120)}'
                     f'<br/><i>tools: {label(tools, 200)}</i>"]')
        if i:
            lines.append(f"  p{i - 1} --> p{i}")
    return "\n".join(lines)


def mermaid_steps(name: str, steps: list[dict]) -> str:
    lines = ["flowchart LR", f'  s["{label(name, 60)}"]']
    prev = "s"
    for i, s in enumerate(steps):
        shape = ('[["' if s["kind"] == "workflow" else '{"' if s["kind"] == "route" else '["')
        close = {'[["': '"]]', '{"': '"}', '["': '"]'}[shape]
        text = f'{s["id"]}: {s["does"]}' + (" (each)" if s.get("each") else "") +             (f' [{s["side_effects"]}]' if s.get("side_effects") else "")
        lines.append(f"  n{i}{shape}{label(text, 60)}{close}")
        lines.append(f"  {prev} --> n{i}")
        prev = f"n{i}"
    return "\n".join(lines)


def lifecycle() -> str:
    stages = " --> ".join(f'b{i}["{name}"]' for i, (name, _) in enumerate(batch.STAGES))
    folder = " --> ".join(f'f{i}["{name}"]' for i, (name, _) in enumerate(batch.FOLDER_STAGES))
    return "\n".join([
        "flowchart LR",
        '  survey["folder survey"] --> decide{"folder decision<br/>(person or policy)"}',
        '  decide --> queue["queue documents (deferred, no model)"]',
        '  queue --> intake["intake: capture, fetch, quality, screen, describe"]',
        '  intake --> staged["staged item"] --> approve{"approve (person or agent policy)"}',
        f"  approve --> {stages}",
        f'  b{len(batch.STAGES) - 1} --> enriched["enriched / partial"] --> accept{{"accept"}}',
        '  accept --> note["Source note (indexed, findable)"]',
        '  note --> sessions["research sessions (purposes below)"] --> offering["staged Offering"]',
        '  offering --> promote{"promote (person or agent policy)"}',
        f'  b{len(batch.STAGES) - 1} -.-> geo["paper graph (Geo-Grapher)"]',
        f'  decide -.-> {folder}',
    ])


def canvas(phases: dict[str, list[dict]]) -> dict:
    """An Obsidian canvas: one group per purpose, one card per phase, arrows in order."""
    nodes, edges = [], []
    x = 0
    for purpose, rows in phases.items():
        y = 80
        cards = []
        for i, r in enumerate(rows):
            gate = "\n".join(f"- {g}" for g in r["gate"]) or "- nothing: advance"
            text = (f"### {r['phase']}\n_{r.get('ask', '')}_\n\n**To leave:**\n{gate}\n\n"
                    "**Gate uses:** " + ", ".join(f"`{t}`" for t in r.get("remedies") or [])
                    + "\n\n**Tools:** " + ", ".join(f"`{t}`" for t in r["offered"]))
            nid = f"librarian-map-{purpose}-{i}"
            nodes.append({"id": nid, "type": "text", "x": x + 20, "y": y, "width": 400,
                          "height": 260, "text": text})
            if cards:
                edges.append({"id": f"{nid}-after", "fromNode": cards[-1], "fromSide": "bottom",
                              "toNode": nid, "toSide": "top"})
            cards.append(nid)
            y += 300
        nodes.append({"id": f"librarian-map-{purpose}", "type": "group", "x": x, "y": 0, "width": 440,
                      "height": y, "label": f"{purpose} session"})
        x += 500
    return {"nodes": nodes, "edges": edges}


def render(phases, workflows, pipelines, macros) -> str:
    out = ["# Librarian workflow map", "",
           "Generated by `scripts/workflow_map.py` from `standard/phases.yaml` and the code; "
           "regenerate rather than "
           "edit. Each phase card shows the exit gate the model is shown in that phase "
           "(`Session.missing`) and the tools the live loop offers there (tail tools such as "
           "`advance`, `ask_user`, `park_session` and `request_budget` are left out).", "",
           "## 1. A source's life, end to end", "", "```mermaid", lifecycle(), "```", "",
           "## 2. Research sessions, by purpose", ""]
    for purpose, rows in phases.items():
        out += [f"### {purpose}", "", "```mermaid", mermaid_purpose(purpose, rows), "```", ""]
    out += ["## 3. YAML workflows (`standard/workflows`)", "",
            "Each is a closed sequence of registered actions; `[[...]]` is a nested workflow, "
            "`{...}` a routing step.", ""]
    for w in workflows:
        out += [f"### {w['name']}", "", f"_{w['purpose']}_", "", "```mermaid",
                mermaid_steps(w["name"], w["steps"]), "```", ""]
    out += ["## 4. YAML pipelines (`standard/pipelines`)", ""]
    for p in pipelines:
        out += [f"### {p['name']}", "", f"_{p['purpose']}_", "", "```mermaid",
                mermaid_steps(p["name"], p["steps"]), "```", ""]
    out += ["## 5. Agent macros", "",
            "Workflows above with a `macro:` block. The Lead runs them in a session with "
            "`macro_run`; one that can write waits for a person's approval of its exact "
            "expanded plan.", "",
            "| Macro | Steps | Writes |", "|---|---|---|"]
    out += [f"| `{m['name']}` | {' → '.join(f'`{s}`' for s in m['steps'])} | "
            f"{'yes' if m['writes'] else 'no'} |" for m in macros]
    return "\n".join(out) + "\n"


def write_canvas(folder: Path, generated: dict) -> Path:
    """Write the map's canvas through the safe canvas service (W2, 2026-11-20).

    Only nodes with the `librarian-map-` prefix are the map's; every other node on the canvas is a
    person's and is kept, and a map node someone moved stays where they put it. A canvas this
    service never wrote (no `librarian-` node: a person's own drawing, or a map from before W2) is
    never merged into; the map is written beside it, to the next free name, instead."""
    from resource_librarian.canvas import service
    target = folder / "workflow-map.canvas"
    n = 0
    while True:
        try:
            service.write(target, generated, profile=None)
            return target
        except service.CanvasConflict:
            n += 1
            target = folder / f"workflow-map.generated{'' if n == 1 else '-' + str(n)}.canvas"
            if n > 9:
                raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    phases = gather_phases()
    workflows, pipelines, macros = gather_yaml("workflows"), gather_yaml("pipelines"), gather_macros()
    (args.out / "WORKFLOW-MAP.md").write_text(render(phases, workflows, pipelines, macros),
                                              encoding="utf-8")
    target = write_canvas(args.out, canvas(phases))
    (args.out / "workflow-map.json").write_text(json.dumps(
        {"phases": phases, "workflows": workflows, "pipelines": pipelines, "macros": macros},
        indent=1), encoding="utf-8")
    print(f"wrote {args.out}: {sum(len(r) for r in phases.values())} phases, "
          f"{len(workflows)} workflows, {len(pipelines)} pipelines, {len(macros)} macros")
    if target.name != "workflow-map.canvas":
        print(f"workflow-map.canvas holds nodes the Librarian did not write (a person's canvas), so it was "
              f"left alone; the new map is in {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
