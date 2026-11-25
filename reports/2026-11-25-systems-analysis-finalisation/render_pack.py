"""Render and check the systems-analysis packs (PLAN.md section 2; step S2).

    python render_pack.py --all                  # render every pack
    python render_pack.py librarian/as-is        # render one pack
    python render_pack.py --check --all          # write nothing; fail if a view is older than its spec

A pack is a folder holding `pack.yaml` (actors and use cases), one `.spec.yaml` per drawn use case,
and optionally `states.yaml`. From them it writes, into the pack:
  views/<id>.views.md   G3: activity diagram, written use case, lane load, decision tree, test table,
                        boundary values, and the weaknesses (as-is) or the failures handled (to-be)
  use-case-diagram.md   G1
  composition.md        G2: which process calls which, from the specs' references
  states.md             G4, when the pack has states.yaml
  INDEX.md              the pack's contents, its weakness register and every check's result
  index.canvas          G6: one card per graph
  validation.json       a receipt per spec, with its hash
No model is called. The tree logic is render_spec.py's (the accepted P0 renderer); the checks that the
nine wrapper scripts added one by one are folded in here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
RENDER_SPEC = REPO / "reports/2026-11-20-workflow-map/examples/ingestion/render_spec.py"
PACKS = ("librarian/as-is", "librarian/to-be", "geo-grapher/as-is", "geo-grapher/to-be")

STATUSES = {"as-is": {"IMPLEMENTED_VERIFIED", "IMPLEMENTED_OBSERVED"},
            "to-be": {"PROPOSED_UNACCEPTED", "PROPOSED_ACCEPTED"}}
# Lane names: exactly the actors of docs/terminology.md and USE-CASES.md. Qualifiers go in the labels.
ACTORS = ("Owner", "Overseer (tier 0)", "Lead (tier 1)", "Clerk (tier 2)", "Scribe (tier 3)", "Oracle", "Doctor",
          "Core", "Web UI", "Model worker", "Model host", "Geo-Grapher", "Geo-Grapher CLI", "Geo-Grapher service",
          "Geo-Grapher store", "External project")
NODE_KEYS = {"id", "kind", "lane", "label", "step", "outcome", "use_case"}
EDGE_KEYS = {"from", "to", "guard", "ext", "observed"}
SIZE_LIMIT = 40                      # nodes per activity diagram, notes excluded (PLAN.md 2.3, D3)
WEAKNESS_KINDS = ("gap", "fault", "risk", "unverified", "drift", "cost")
FIELDS = (("name", "Use case name"), ("brief", "Brief description"), ("primary_actor", "Primary actor"),
          ("supporting_actors", "Supporting actors"), ("preconditions", "Preconditions"), ("trigger", "Trigger"),
          ("success_guarantee", "Success guarantee"), ("minimal_guarantee", "Minimal guarantee"),
          ("open_questions", "Open questions"))
NUMERIC_GUARD = re.compile(r"[<>≤≥]|\b\d+\s*(s|seconds?|minutes?|min|calls?|items?|cards?|files?|pages?|chunks?|%)\b"
                           r"|\b(budget|limit|ceiling|at least|at most|more than|fewer than|within|timeout|time out)\b",
                           re.I)


def load_render():
    spec = importlib.util.spec_from_file_location("render_spec", RENDER_SPEC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


R = load_render()


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


# ----------------------------------------------------------------------------- loading

class Pack:
    def __init__(self, path: Path):
        self.path = path
        self.name = rel(path).split("2026-11-25-systems-analysis-finalisation/")[-1]
        meta_file = path / "pack.yaml"
        self.meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}
        self.state = self.meta.get("state") or path.name
        self.files = {p: R.load(p) for p in sorted(path.glob("*.spec.yaml"))}
        self.specs = {s["diagram"]: s for s in self.files.values()}
        self.file_of = {s["diagram"]: p for p, s in self.files.items()}
        states = path / "states.yaml"
        self.states = yaml.safe_load(states.read_text(encoding="utf-8")) if states.exists() else None
        self.load_errors: list[str] = []
        # pack.yaml carries each use case's written fields and boundary values; specs carry the flow.
        for uc in self.meta.get("use_cases", []):
            spec = self.specs.get(uc.get("spec"))
            if spec is None:
                continue
            fields = dict(uc.get("fields") or spec.get("use_case_fields") or {})
            fields.setdefault("name", uc.get("name"))
            spec["use_case_fields"] = fields
            if uc.get("boundaries"):
                spec.setdefault("boundaries", uc["boundaries"])
        # weaknesses.yaml is the as-is pack's register; each entry names its spec, or `state:<entity>`.
        # handles.yaml is the to-be pack's answer to the register: where each weakness is handled, or
        # why it is still open.
        self.open: dict[str, str] = {}
        answers = path / "handles.yaml"
        if answers.exists():
            entities = {e["id"]: e for e in (self.states or {}).get("entities", [])}
            data = yaml.safe_load(answers.read_text(encoding="utf-8"))
            for h in data.get("handles", []):
                where = str(h.get("spec", ""))
                if where in self.specs:
                    self.specs[where].setdefault("handles", []).append(h)
                elif where.startswith("state:") and where[6:] in entities:
                    entities[where[6:]].setdefault("handles", []).append(h)
                else:
                    self.load_errors.append(f"handles {h.get('weakness')} in {where!r}, which is no spec or state here")
            self.open = {o["weakness"]: o["reason"] for o in data.get("open", [])}
        register = path / "weaknesses.yaml"
        self.themes: list[dict] = []
        if register.exists():
            entities = {e["id"]: e for e in (self.states or {}).get("entities", [])}
            data = yaml.safe_load(register.read_text(encoding="utf-8"))
            self.themes = data.get("themes", [])
            for w in data.get("weaknesses", []):
                where = str(w.get("spec", ""))
                if where in self.specs:
                    self.specs[where].setdefault("weaknesses", []).append(w)
                elif where.startswith("state:") and where[6:] in entities:
                    entities[where[6:]].setdefault("weaknesses", []).append(w)
                else:
                    self.load_errors.append(f"weakness {w.get('id')} names {where!r}, which is no spec or state here")

    def counterpart(self) -> "Pack | None":
        other = self.path.parent / ("to-be" if self.state == "as-is" else "as-is")
        return Pack(other) if other.exists() else None

    def weaknesses(self) -> dict[str, tuple[str, dict]]:
        found = {}
        for sid, spec in self.specs.items():
            for w in spec.get("weaknesses", []) or []:
                found[w["id"]] = (sid, w)
        for entity in (self.states or {}).get("entities", []):
            for w in entity.get("weaknesses", []) or []:
                found[w["id"]] = (f"state:{entity['id']}", w)
        return found

    def handles(self) -> dict[str, list[tuple[str, dict]]]:
        found = defaultdict(list)
        for sid, spec in self.specs.items():
            for h in spec.get("handles", []) or []:
                found[h["weakness"]].append((sid, h))
        for entity in (self.states or {}).get("entities", []):
            for h in entity.get("handles", []) or []:
                found[h["weakness"]].append((f"state:{entity['id']}", h))
        return found


# ----------------------------------------------------------------------------- checks

def check_spec(pack: Pack, sid: str, spec: dict) -> tuple[list[str], list[str], list[dict]]:
    """Errors fail the run; warnings are listed in the index. Returns (errors, warnings, scenarios)."""
    bad = [e for e in spec["edges"] if "guard" in e and not isinstance(e["guard"], str)]
    if bad:     # YAML reads an unquoted yes, no, on or off as a boolean
        return [f"guard {e['guard']!r} on {e['from']}->{e['to']} is not text: quote it" for e in bad], [], []
    # In a flow mapping an unquoted comma ends the value, and the rest becomes a key of its own.
    stray = [f"{x.get('id') or x.get('from')}: unknown key {k!r} (an unquoted comma?)"
             for group, allowed in (("nodes", NODE_KEYS), ("edges", EDGE_KEYS))
             for x in spec[group] for k in x if k not in allowed]
    if stray:
        return stray, [], []
    errors, warnings = list(R.validate(spec)), []
    ids = [n["id"] for n in spec["nodes"]]
    errors += [f"duplicate node id: {i}" for i, c in Counter(ids).items() if c > 1]
    exts = [e["ext"] for e in spec["edges"] if e.get("ext")]
    errors += [f"duplicate extension: {x}" for x, c in Counter(exts).items() if c > 1]
    steps = [n["step"] for n in spec["nodes"] if n.get("step")]
    if sorted(steps) != list(range(1, len(steps) + 1)):
        errors.append("main scenario steps must be consecutive and unique")
    if errors:
        return errors, warnings, []
    main = R.main_path(spec)
    errors += [f"step {n['step']} ({n['id']}) is not on the main path" for n in spec["nodes"]
               if n.get("step") and n["id"] not in main]
    scenarios = R.paths(spec)
    errors += R.cross_check(spec, scenarios)
    errors += R.check_references(spec, pack.specs)

    status = spec.get("status")
    if status not in STATUSES[pack.state]:
        errors.append(f"status {status!r} does not belong in an {pack.state} pack ({sorted(STATUSES[pack.state])})")
    for lane in spec["lanes"]:
        if lane not in ACTORS:
            errors.append(f"lane {lane!r} is not an actor of docs/terminology.md ({', '.join(ACTORS)})")
    size = sum(n["kind"] != "note" for n in spec["nodes"])
    if size > SIZE_LIMIT and not spec.get("size_exception"):
        errors.append(f"{size} nodes: over the limit of {SIZE_LIMIT}; split it into a parent and children by reference")
    for old in spec.get("supersedes", []) or []:
        if not (REPO / old).exists():
            errors.append(f"supersedes {old}, which does not exist")

    fields = spec.get("use_case_fields") or {}
    missing = [label for key, label in FIELDS if not fields.get(key)]
    if missing:
        warnings.append("written use case lacks: " + ", ".join(missing))

    places = set(ids) | set(exts) | {"*"}
    if pack.state == "as-is":
        for w in spec.get("weaknesses", []) or []:
            if w.get("kind") not in WEAKNESS_KINDS:
                errors.append(f"weakness {w.get('id')}: kind {w.get('kind')!r} is not one of {WEAKNESS_KINDS}")
            for at in _list(w.get("at")):
                if at not in places:
                    errors.append(f"weakness {w['id']} is at {at!r}, which is no node or extension here")
            if not w.get("evidence"):
                warnings.append(f"weakness {w['id']} cites no evidence")
        if spec.get("handles"):
            errors.append("an as-is spec records weaknesses; `handles` belongs in the to-be pack")
    else:
        for h in spec.get("handles", []) or []:
            for at in _list(h.get("at")):
                if at not in places:
                    errors.append(f"handles {h['weakness']} at {at!r}, which is no node or extension here")
        if spec.get("weaknesses"):
            warnings.append("a to-be spec names its own risks under `risks`, not `weaknesses`")
    declared = {b["at"] for b in spec.get("boundaries", []) or []}
    for b in spec.get("boundaries", []) or []:
        if b["at"] not in ids:
            errors.append(f"boundary values at {b['at']!r}, which is no node here")
    nodes = {n["id"]: n for n in spec["nodes"]}
    for d in (n for n in spec["nodes"] if n["kind"] == "decision" and n["id"] not in declared):
        guards = " ".join(e.get("guard", "") for e in spec["edges"] if e["from"] == d["id"]) + " " + d.get("label", "")
        if NUMERIC_GUARD.search(guards):
            warnings.append(f"decision {d['id']} ('{nodes[d['id']]['label']}') tests a quantity but declares no boundary values")
    return errors, warnings, scenarios


OPEN: dict[str, str] = {}      # the to-be pack's open weaknesses and their reasons, set by render()


def answered(wid: str, handled: dict) -> str:
    """Where the to-be handles a weakness, or why it is still open."""
    if handled.get(wid):
        return ", ".join(f"`{sid}`" for sid, _ in handled[wid])
    if wid in OPEN:
        return "open: " + md_cell(OPEN[wid])
    return "**not yet**"


def _list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# ----------------------------------------------------------------------------- views

def md_cell(text) -> str:
    if isinstance(text, list):
        text = "; ".join(str(t) for t in text)
    return str(text or "—").replace("|", "\\|").replace("\n", " ")


def fields_table(spec: dict) -> str:
    fields = dict(spec.get("use_case_fields") or {})
    fields.setdefault("name", spec["title"])
    rows = ["| Field | Content |", "|---|---|"]
    rows += [f"| **{label}** | {md_cell(fields.get(key))} |" for key, label in FIELDS]
    return "\n".join(rows)


def boundary_table(spec: dict) -> str:
    items = spec.get("boundaries") or []
    if not items:
        return "_None declared._"
    nodes = {n["id"]: n for n in spec["nodes"]}
    rows = ["| Decision | Values to test | Expected |", "|---|---|---|"]
    for b in items:
        rows.append(f"| {md_cell(nodes[b['at']]['label'])} | {md_cell(b.get('values'))} | {md_cell(b.get('expect'))} |")
    return "\n".join(rows)


def weakness_table(pack: Pack, spec: dict, handled: dict) -> str:
    items = spec.get("weaknesses") or []
    if not items:
        return "_None recorded._"
    rows = ["| Id | Kind | Where | Weakness | Evidence | Handled in the to-be by |", "|---|---|---|---|---|---|"]
    for w in items:
        by = answered(w["id"], handled)
        rows.append(f"| {w['id']} | {w['kind']} | {md_cell(_list(w.get('at')))} | {md_cell(w['says'])} | "
                    f"{md_cell(w.get('evidence'))} | {by} |")
    return "\n".join(rows)


def handles_table(spec: dict, known: dict) -> str:
    items = spec.get("handles") or []
    if not items:
        return "_None recorded._"
    rows = ["| As-is weakness | Where here | How it is handled |", "|---|---|---|"]
    for h in items:
        origin = known.get(h["weakness"])
        name = f"{h['weakness']} ({origin[0]}): {origin[1]['says']}" if origin else f"{h['weakness']} (**unknown**)"
        rows.append(f"| {md_cell(name)} | {md_cell(_list(h.get('at')))} | {md_cell(h.get('how'))} |")
    return "\n".join(rows)


def views(pack: Pack, sid: str, spec: dict, scenarios: list[dict], errors: list[str], warnings: list[str],
          weakness_index: dict, handled: dict) -> str:
    path = pack.file_of[sid]
    tree, tests = R.tree_and_tests(spec, scenarios)
    problem = spec.get("problem") or {}
    out = [f"<!-- generated by render_pack.py from {path.name} sha256={sha(path)}; edit the spec, not this file -->",
           f"# {spec['title']}", "",
           f"**{spec.get('use_case', '')} · {pack.state} · `{spec.get('status')}`** · spec [{path.name}](../{path.name})"]
    if spec.get("supersedes"):
        out.append("Supersedes: " + ", ".join(f"`{s}`" for s in spec["supersedes"]))
    if problem:
        out += ["", "| Problem | |", "|---|---|"] + [f"| {k} | {md_cell(v)} |" for k, v in problem.items()]
    out += ["", "## Written use case", "", fields_table(spec), "", R.written_use_case(spec, scenarios), "",
            "## Activity diagram", "", "```mermaid", R.mermaid(spec), "```", "",
            "## Lane load", "", R.lane_load(spec, scenarios), "",
            "## Decision tree", "", tree, "",
            "## Test cases", "", "One test per path: the main success scenario, then each extension.", "", tests, "",
            "### Boundary values", "", boundary_table(spec), ""]
    if pack.state == "as-is":
        out += ["## Weaknesses and gaps", "", weakness_table(pack, spec, handled), ""]
    else:
        out += ["## As-is weaknesses this handles", "", handles_table(spec, weakness_index), ""]
        if spec.get("risks"):
            out += ["### New risks", ""] + [f"- {md_cell(r)}" for r in spec["risks"]] + [""]
        if spec.get("delta"):
            out += ["## Delta from the as-is", "", "| As-is | To-be | Answers |", "|---|---|---|"]
            out += [f"| {md_cell(d.get('from'))} | {md_cell(d.get('to'))} | {md_cell(d.get('answers'))} |"
                    for d in spec["delta"]] + [""]
    if spec.get("evidence"):
        ev = spec["evidence"]
        out += ["## Evidence", ""] + [f"- {md_cell(e)}" for e in (ev if isinstance(ev, list) else [ev])] + [""]
    out += ["## Checks", "", "Errors: " + ("none" if not errors else ""), *[f"- {e}" for e in errors],
            "", "Warnings: " + ("none" if not warnings else ""), *[f"- {w}" for w in warnings], ""]
    return "\n".join(out)


def mermaid_id(text: str) -> str:
    return re.sub(r"\W+", "_", text)


def use_case_diagram(pack: Pack) -> str:
    meta = pack.meta
    lines = ["flowchart LR"]
    actors = meta.get("actors", [])
    for a in actors:
        lines.append(f'  {mermaid_id(a["id"])}(["{a["name"]}"])')
    lines.append(f'  subgraph system["{meta.get("system", "System")} ({pack.state})"]')
    for uc in meta.get("use_cases", []):
        mark = " (not drawn)" if not uc.get("spec") else ""
        mark = " (deferred)" if uc.get("deferred") else mark
        lines.append(f'    {mermaid_id(uc["id"])}(["{uc["id"]} {uc["name"]}{mark}"])')
    lines.append("  end")
    for uc in meta.get("use_cases", []):
        for a in uc.get("actors", []):
            lines.append(f"  {mermaid_id(a)} --- {mermaid_id(uc['id'])}")
        for inc in uc.get("includes", []):
            lines.append(f'  {mermaid_id(uc["id"])} -. "«include»" .-> {mermaid_id(inc)}')
        for ext in uc.get("extends", []):
            lines.append(f'  {mermaid_id(uc["id"])} -. "«extend»" .-> {mermaid_id(ext)}')
    rows = ["| Use case | Actors | Spec | Status |", "|---|---|---|---|"]
    names = {a["id"]: a["name"] for a in actors}
    for uc in meta.get("use_cases", []):
        spec_id = uc.get("spec")
        link = f"[{spec_id}](views/{spec_id}.views.md)" if spec_id in pack.specs else (spec_id or "—")
        state = ("deferred: " + uc["deferred"]) if uc.get("deferred") else (
            pack.specs[spec_id].get("status") if spec_id in pack.specs else "**not drawn yet**")
        rows.append(f"| {uc['id']} {uc['name']} | {', '.join(names.get(a, a) for a in uc.get('actors', []))} | "
                    f"{link} | {state} |")
    return "\n".join([f"# Use case diagram: {meta.get('system', '')} ({pack.state})", "",
                      "Actors outside the boundary; dashed arrows are «include» and «extend».", "",
                      "```mermaid", *lines, "```", "", *rows, ""])


def composition(pack: Pack) -> str:
    calls = {sid: sorted({n["use_case"] for n in s["nodes"] if n["kind"] == "ref"}) for sid, s in pack.specs.items()}
    called = {c for cs in calls.values() for c in cs}
    roots = sorted(sid for sid in pack.specs if sid not in called)
    lines = ["flowchart TD"]
    for sid, spec in pack.specs.items():
        lines.append(f'  {mermaid_id(sid)}["{sid}<br/>{spec.get("use_case", "")}"]')
    for sid, cs in calls.items():
        for c in cs:
            target = mermaid_id(c)
            if c not in pack.specs:
                lines.append(f'  {target}["{c} (no spec)"]')
            lines.append(f"  {mermaid_id(sid)} --> {target}")
    text = ["# Process composition: " + pack.name, "",
            "Which process calls which (`kind: ref`). Roots: " + ", ".join(f"`{r}`" for r in roots) + ".", "",
            "```mermaid", *lines, "```", ""]
    if pack.meta.get("composition_note"):
        text += [pack.meta["composition_note"], ""]
    return "\n".join(text)


def states_md(pack: Pack, handled: dict, weakness_index: dict) -> str:
    out = [f"# State diagrams: {pack.name}", ""]
    for ent in pack.states.get("entities", []):
        lines = ["stateDiagram-v2"]
        if ent.get("initial"):
            lines.append(f"  [*] --> {mermaid_id(ent['initial'])}")
        for t in ent.get("transitions", []):
            label = t.get("on", "")
            lines.append(f"  {mermaid_id(t['from'])} --> {mermaid_id(t['to'])}" + (f": {label}" if label else ""))
        for f in ent.get("final", []) or []:
            lines.append(f"  {mermaid_id(f)} --> [*]")
        out += [f"## {ent['name']}", "", md_cell(ent.get("about", "")), "", "```mermaid", *lines, "```", ""]
        rows = ["| From | To | On | By | Guard |", "|---|---|---|---|---|"]
        rows += [f"| {t['from']} | {t['to']} | {md_cell(t.get('on'))} | {md_cell(t.get('by'))} | {md_cell(t.get('guard'))} |"
                 for t in ent.get("transitions", [])]
        out += rows + [""]
        if ent.get("evidence"):
            out += ["Evidence: " + md_cell(ent["evidence"]), ""]
        if pack.state == "as-is" and ent.get("weaknesses"):
            out += ["Weaknesses:", ""]
            for w in ent["weaknesses"]:
                by = answered(w["id"], handled)
                out.append(f"- **{w['id']}** ({w['kind']}): {md_cell(w['says'])} Evidence: {md_cell(w.get('evidence'))}. "
                           f"Handled by: {by}.")
            out.append("")
        if pack.state != "as-is" and ent.get("handles"):
            out += ["Handles:", ""] + [f"- **{h['weakness']}**: {md_cell(h.get('how'))}" for h in ent["handles"]] + [""]
    return "\n".join(out)


def index_canvas(pack: Pack) -> dict:
    nodes, edges, x = [], [], 0
    groups = [("G1 Use case diagram", ["use-case-diagram.md"]), ("G2 Composition", ["composition.md"]),
              ("G3 Use cases", [f"views/{sid}.views.md" for sid in pack.specs]),
              ("G4 States", ["states.md"] if pack.states else []), ("Index", ["INDEX.md"])]
    base = rel(pack.path)
    for gi, (title, files) in enumerate(groups):
        if not files:
            continue
        height = 60 + 420 * len(files)
        nodes.append({"id": f"librarian-group-{gi}", "type": "group", "label": title, "x": x, "y": 0,
                      "width": 520, "height": height})
        for fi, f in enumerate(files):
            nodes.append({"id": f"librarian-card-{gi}-{fi}", "type": "file", "file": f"{base}/{f}",
                          "x": x + 20, "y": 40 + 420 * fi, "width": 480, "height": 400})
        x += 580
    return {"nodes": nodes, "edges": edges}


# ----------------------------------------------------------------------------- the pack

def render(pack: Pack, write: bool = True) -> tuple[list[str], list[str]]:
    other = pack.counterpart()
    own_weaknesses = pack.weaknesses()
    if pack.state == "as-is":
        weakness_index, handled = own_weaknesses, (other.handles() if other else {})
    else:
        weakness_index, handled = (other.weaknesses() if other else {}), pack.handles()
    all_errors, all_warnings, receipts, rows = list(pack.load_errors), [], [], []
    seen_w = Counter(w["id"] for s in pack.specs.values() for w in (s.get("weaknesses") or []))
    seen_w.update(w["id"] for e in (pack.states or {}).get("entities", []) for w in (e.get("weaknesses") or []))
    all_errors += [f"weakness id {w} is used {c} times in this pack" for w, c in seen_w.items() if c > 1]
    if pack.themes:
        placed = Counter(w for t in pack.themes for w in t["weaknesses"])
        all_errors += [f"weakness {w} is in no theme" for w in own_weaknesses if w not in placed]
        all_errors += [f"weakness {w} is in {c} themes" for w, c in placed.items() if c > 1]
        all_errors += [f"a theme names {w}, which is not in the register" for w in placed if w not in own_weaknesses]
    if pack.state != "as-is":
        for wid in list(handled) + list(pack.open):
            if wid not in weakness_index:
                all_errors.append(f"`{wid}` in handles.yaml names no weakness of the as-is pack")
        both = sorted(set(handled) & set(pack.open))
        all_errors += [f"{w} is both handled and open" for w in both]
        unanswered = sorted(w for w in weakness_index if w not in handled and w not in pack.open)
        if unanswered:
            all_warnings.append(f"{len(unanswered)} as-is weaknesses are neither handled nor open: " + ", ".join(unanswered))
    global OPEN
    OPEN = pack.open if pack.state != "as-is" else (other.open if other else {})
    (pack.path / "views").mkdir(exist_ok=True) if write else None
    for sid, spec in pack.specs.items():
        errors, warnings, scenarios = check_spec(pack, sid, spec)
        all_errors += [f"{sid}: {e}" for e in errors]
        all_warnings += [f"{sid}: {w}" for w in warnings]
        path = pack.file_of[sid]
        view = pack.path / "views" / f"{sid}.views.md"
        if not write:
            recorded = view.read_text(encoding="utf-8").split("sha256=")[1].split(";")[0] if view.exists() else None
            if recorded != sha(path):
                all_errors.append(f"{sid}: views are older than the spec (re-render)")
            continue
        if scenarios:
            view.write_text(views(pack, sid, spec, scenarios, errors, warnings, weakness_index, handled),
                            encoding="utf-8")
        nodes = {n["id"]: n for n in spec["nodes"]}
        t0 = R.tier0_lane(spec)
        graded = [R.tier0_turns(spec, p) for p in scenarios
                  if not (p["end"] and R.outcome(nodes[p["end"]]) == "escalated")] if (t0 and scenarios) else []
        receipt = {"spec": path.name, "sha256": sha(path), "status": spec.get("status"),
                   "nodes": sum(n["kind"] != "note" for n in spec["nodes"]),
                   "steps": sum(bool(n.get("step")) for n in spec["nodes"]), "scenarios": len(scenarios),
                   "tier0_turns_mss": graded[0] if graded else None, "tier0_turns_worst": max(graded) if graded else None,
                   "weaknesses": len(spec.get("weaknesses") or []), "handles": len(spec.get("handles") or []),
                   "errors": errors, "warnings": warnings}
        receipts.append(receipt)
        rows.append(receipt | {"id": sid, "use_case": spec.get("use_case", "")})
    if not write:
        return all_errors, all_warnings
    (pack.path / "use-case-diagram.md").write_text(use_case_diagram(pack), encoding="utf-8")
    (pack.path / "composition.md").write_text(composition(pack), encoding="utf-8")
    if pack.states:
        (pack.path / "states.md").write_text(states_md(pack, handled, weakness_index), encoding="utf-8")
    (pack.path / "INDEX.md").write_text(index_md(pack, rows, all_errors, all_warnings, weakness_index, handled),
                                        encoding="utf-8")
    (pack.path / "validation.json").write_text(json.dumps({"pack": pack.name, "receipts": receipts,
                                                           "errors": all_errors, "warnings": all_warnings},
                                                          indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_canvas(pack)
    return all_errors, all_warnings


def write_canvas(pack: Pack) -> None:
    sys.path.insert(0, str(REPO / "src"))
    from resource_librarian.canvas import service
    target = pack.path / "index.canvas"
    if target.exists():
        target.unlink()                     # wholly generated: rebuilt each time
    service.write(target, index_canvas(pack), profile=None)


def index_md(pack: Pack, rows, errors, warnings, weakness_index, handled) -> str:
    out = [f"# {pack.meta.get('system', '')} — {pack.state} pack", "",
           pack.meta.get("about", ""), "",
           "[Use case diagram](use-case-diagram.md) · [Composition](composition.md)"
           + (" · [States](states.md)" if pack.states else "") + " · [Canvas](index.canvas)", "",
           "## Use cases", "",
           "| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        t0 = f"{r['tier0_turns_mss']} / {r['tier0_turns_worst']}" if r["tier0_turns_mss"] is not None else "—"
        out.append(f"| {r['use_case']} | [{r['id']}](views/{r['id']}.views.md) | `{r['status']}` | {r['nodes']} | "
                   f"{r['steps']} | {r['scenarios']} | {t0} | {r['weaknesses']} | {r['handles']} | "
                   f"{len(r['errors'])} | {len(r['warnings'])} |")
    undrawn = [uc for uc in pack.meta.get("use_cases", []) if uc.get("spec") not in pack.specs]
    if undrawn:
        out += ["", "Not drawn yet: " + "; ".join(
            f"{uc['id']} {uc['name']}" + (f" (deferred: {uc['deferred']})" if uc.get("deferred") else "")
            for uc in undrawn) + "."]
    if pack.state == "as-is" and pack.themes:
        out += ["", "## Root causes", "", "| Theme | What goes wrong | Weaknesses | Handled |", "|---|---|---|---|"]
        for t in pack.themes:
            done = sum(1 for w in t["weaknesses"] if handled.get(w))
            out.append(f"| **{t['id']} {t['name']}** | {md_cell(t['says'])} | {', '.join(t['weaknesses'])} | "
                       f"{done} of {len(t['weaknesses'])} |")
    if pack.state == "as-is":
        out += ["", "## Weakness register", "",
                "Every weakness found in the as-is, and the to-be element that handles it.", "",
                "| Id | Kind | In | Weakness | Handled by |", "|---|---|---|---|---|"]
        for wid, (where, w) in sorted(weakness_index.items()):
            by = answered(wid, handled)
            out.append(f"| {wid} | {w['kind']} | `{where}` | {md_cell(w['says'])} | {by} |")
        done = sum(1 for wid in weakness_index if handled.get(wid))
        still_open = sum(1 for wid in weakness_index if not handled.get(wid) and wid in OPEN)
        out += ["", f"{len(weakness_index)} weaknesses: {done} handled by the to-be, {still_open} open with a reason, "
                    f"{len(weakness_index) - done - still_open} not yet answered."]
    out += ["", "## Checks", "", f"Errors ({len(errors)}):", *[f"- {e}" for e in errors],
            "", f"Warnings ({len(warnings)}):", *[f"- {w}" for w in warnings], ""]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packs", nargs="*")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--check", action="store_true", help="write nothing; fail on errors or stale views")
    args = parser.parse_args()
    names = [p for p in PACKS if (HERE / p).exists()] if args.all else args.packs
    failed = False
    for name in names:
        pack = Pack(HERE / name)
        errors, warnings = render(pack, write=not args.check)
        print(f"{name}: {len(pack.specs)} specs, {len(errors)} errors, {len(warnings)} warnings")
        for e in errors:
            print("  ERROR", e)
        failed |= bool(errors)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
