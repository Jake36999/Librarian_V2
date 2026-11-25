"""Prototype renderer for an activity diagram spec (docs/proposals/diagram-workflows.md, P0).

    python render_spec.py ingestion.spec.yaml

From one spec it validates the activity rules, unfolds the decisions into a tree of paths, and writes:
  <name>.views.md   Mermaid activity diagram with swimlanes, the written use case (MSS + extensions,
                    generated), the decision tree, the test table and the cross-view check
  <name>.canvas     an Obsidian canvas: one column per lane, rows in flow order
No model is called. This is an example, not the product: P0 builds the real thing.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

import yaml

OUTCOMES = "Outcomes"
KINDS = {"start", "end", "activity", "decision", "merge", "fork", "join", "note", "ref"}
# Where a path may branch: a decision, or a reference to another use case (UML's call-behaviour action),
# whose ways out are that use case's outcomes.
BRANCHING = {"decision", "ref"}
SUCCESS = {"success", "resolved", "learned"}
# Ends that are neither the success path nor a failure: an existing definition reused, or one used once.
NEUTRAL = {"reused", "used once"}


def outcome(node: dict) -> str:
    """An end node's outcome: declared, or success for the main end of an older spec."""
    return node.get("outcome") or ("success" if node["id"] == "e1" else "failure")


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- validate

def validate(spec: dict) -> list[str]:
    nodes = {n["id"]: n for n in spec["nodes"]}
    out_edges = defaultdict(list)
    problems = []
    for n in spec["nodes"]:
        if n["kind"] not in KINDS:
            problems.append(f"{n['id']}: unknown node kind {n['kind']!r}")
        if n["kind"] not in ("start", "end") and n.get("lane") not in spec["lanes"]:
            problems.append(f"{n['id']}: lane {n.get('lane')!r} is not declared")
    for e in spec["edges"]:
        for end in ("from", "to"):
            if e[end] not in nodes:
                problems.append(f"edge {e['from']}->{e['to']}: no node {e[end]!r}")
        out_edges[e["from"]].append(e)
    starts = [n for n in nodes.values() if n["kind"] == "start"]
    if len(starts) != 1:
        problems.append(f"exactly one start node is required, found {len(starts)}")
    if not any(n["kind"] == "end" for n in nodes.values()):
        problems.append("at least one end node is required")
    for nid, n in nodes.items():
        outs = out_edges[nid]
        if n["kind"] == "decision":
            if len(outs) < 2:
                problems.append(f"{nid} ({n['label']}): a decision needs at least two ways out")
            if any(not e.get("guard") for e in outs):
                problems.append(f"{nid} ({n['label']}): every way out of a decision needs a guard")
        elif n["kind"] == "ref":
            if not n.get("use_case"):
                problems.append(f"{nid}: a reference names the use case it calls (use_case:)")
            if len(outs) > 1 and any(not e.get("guard") for e in outs):
                problems.append(f"{nid}: a reference with several ways out labels each with an outcome")
        elif n["kind"] == "end" and outs:
            problems.append(f"{nid}: an end node has no way out")
        elif n["kind"] not in ("end",) and not outs:
            problems.append(f"{nid} ({n.get('label', '')}): no way out, and not an end")
        if n["kind"] == "activity" and len(outs) > 1 and any(e.get("guard") for e in outs):
            problems.append(f"{nid}: guarded branches belong on a decision node, not an activity")
    forks = sum(n["kind"] == "fork" for n in nodes.values())
    joins = sum(n["kind"] == "join" for n in nodes.values())
    if forks != joins:
        problems.append(f"{forks} fork(s) but {joins} join(s)")
    if starts:
        seen, todo = set(), deque([starts[0]["id"]])
        while todo:
            cur = todo.popleft()
            if cur in seen:
                continue
            seen.add(cur)
            todo.extend(e["to"] for e in out_edges[cur])
        for nid in nodes:
            if nid not in seen:
                problems.append(f"{nid}: unreachable from the start")
    return problems


# ----------------------------------------------------------------------------- tree logic

def main_path(spec: dict) -> list[str]:
    """The happy path: from the start, always the way out that is not an extension; at a fork,
    its first branch (the others run beside it and meet it at the join)."""
    outs = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
    cur = next(n["id"] for n in spec["nodes"] if n["kind"] == "start")
    trail = [cur]
    while outs[cur]:
        nxt = next((e for e in outs[cur] if not e.get("ext")), outs[cur][0])["to"]
        if nxt in trail:
            break
        trail.append(nxt)
        cur = nxt
    return trail


def paths(spec: dict) -> list[dict]:
    """Tree logic, one scenario per path, as a written use case counts them:
    - the main success scenario, once;
    - each extension, from the step it leaves to where it ends or rejoins the main path;
    - each side branch of a fork, as concurrent work that ends at its join, or ends the use case."""
    nodes = {n["id"]: n for n in spec["nodes"]}
    outs = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
    happy = main_path(spec)
    on_main = set(happy)
    main_edges = [next(e for e in outs[a] if e["to"] == b) for a, b in zip(happy, happy[1:])]
    found = [{"nodes": happy, "edges": main_edges, "end": happy[-1], "rejoin": None, "kind": "MSS"}]

    def follow(first_edge, prefix_edges, kind):
        """Walk from an edge that leaves the main path until an end, the main path, or a join."""
        taken, cur = prefix_edges + [first_edge], first_edge["to"]
        seen = set()
        while True:
            n = nodes[cur]
            if n["kind"] == "end":
                return {"edges": taken, "end": cur, "rejoin": None, "kind": kind}
            if cur in on_main or cur in seen:
                return {"edges": taken, "end": None, "rejoin": cur, "kind": kind}
            seen.add(cur)
            branch = [e for e in outs[cur]]
            if nodes[cur]["kind"] in BRANCHING and len(branch) > 1:
                # a decision inside a side branch: each way out is its own scenario
                for e in branch[1:]:
                    found.append(follow(e, taken, kind))
            taken = taken + [branch[0]]
            cur = branch[0]["to"]

    for i, nid in enumerate(happy):
        for e in outs[nid]:
            if e in main_edges:
                continue
            kind = "concurrent" if nodes[nid]["kind"] == "fork" else "extension"
            found.append(follow(e, main_edges[:i], kind))
    return found


def step_of(spec, nid):
    n = {x["id"]: x for x in spec["nodes"]}[nid]
    return n.get("step")


def first_step_after(spec, path_nodes, idx):
    for nid in path_nodes[idx:]:
        s = step_of(spec, nid)
        if s:
            return s
    return None


# ----------------------------------------------------------------------------- views

def mermaid(spec: dict) -> str:
    nodes = spec["nodes"]
    lines = ["flowchart TD"]
    shape = {"start": ('(("', '"))'), "end": ('((("', '")))'), "decision": ('{"', '"}'), "ref": ('[["', '"]]'),
             "fork": ('[/"', '"\\]'), "join": ('[\\"', '"/]'), "activity": ('["', '"]'), "note": ('>"', '"]'),
             "merge": ('{{"', '"}}')}

    def text(n):
        if n["kind"] == "start":
            return "start"
        lab = n.get("label", n["kind"])
        lab = lab.replace('"', "'")
        if n["kind"] == "ref":
            lab = f"{n['use_case']}: {lab}"
        return (f"{n['step']}. " if n.get("step") else "") + lab

    free = [n for n in nodes if not n.get("lane")]
    for lane in spec["lanes"]:
        lid = re.sub(r"\W+", "_", lane)
        lines.append(f'  subgraph {lid}["{lane}"]')
        for n in nodes:
            if n.get("lane") == lane:
                o, c = shape[n["kind"]]
                lines.append(f"    {n['id']}{o}{text(n)}{c}")
        lines.append("  end")
    for n in free:
        o, c = shape[n["kind"]]
        lines.append(f"  {n['id']}{o}{text(n)}{c}")
    for e in spec["edges"]:
        g = e.get("guard")
        lab = f"|\"[{g}]{' ' + e['ext'] if e.get('ext') else ''}\"|" if g else ""
        lines.append(f"  {e['from']} -->{lab} {e['to']}")
    lines.append("  classDef ext stroke:#d9534f,stroke-width:2px")
    return "\n".join(lines)


def written_use_case(spec: dict, all_paths: list[dict]) -> str:
    nodes = {n["id"]: n for n in spec["nodes"]}
    main = sorted((n for n in spec["nodes"] if n.get("step")), key=lambda n: n["step"])
    out = ["**Main success scenario** (generated: the guard-true path, in step order)", ""]
    out += [f"{n['step']}. The {n['lane']} {n['label']}." for n in main]
    out += ["", "**Extensions** (generated: one per non-happy guard; numbered by the step it leaves)", ""]
    exts = [e for e in spec["edges"] if e.get("ext")]
    for e in exts:
        src = nodes[e["from"]]
        lines = [f"`{e['ext']}1` {e['guard'][0].upper() + e['guard'][1:]}."]
        cur, k, seen = e["to"], 2, set()
        while cur and cur not in seen:
            seen.add(cur)
            n = nodes[cur]
            if n["kind"] == "end":
                lines.append(f"`{e['ext']}{k}` The use case ends: {n['label']}.")
                break
            if n.get("step"):
                lines.append(f"`{e['ext']}{k}` Rejoin at {n['step']}.")
                break
            if n["kind"] in ("join", "merge"):
                lines.append(f"`{e['ext']}{k}` Rejoin at '{n['label']}'.")
                break
            nxt = [x for x in spec["edges"] if x["from"] == cur]
            if n["kind"] == "activity":
                lines.append(f"`{e['ext']}{k}` The {n['lane']} {n['label']}.")
                k += 1
            elif n["kind"] in BRANCHING:
                if n["kind"] == "ref":
                    lines.append(f"`{e['ext']}{k}` The {n['lane']} {n['label']} (continues in {n['use_case']}).")
                else:
                    lines.append(f"`{e['ext']}{k}` The {n['lane']} decides: {n['label']}")
                for alt in nxt[1:]:
                    tgt = nodes[alt["to"]]
                    then = (f"the use case ends: {tgt['label']}" if tgt["kind"] == "end"
                            else f"rejoin at {tgt['step']}" if tgt.get("step") else tgt.get("label", ""))
                    lines.append(f"`{e['ext']}{k}a` If {alt['guard']}: {then}.")
                k += 1
                if nxt and nxt[0].get("guard"):
                    lines.append(f"`{e['ext']}{k}` If {nxt[0]['guard']}:")
                    k += 1
            cur = nxt[0]["to"] if nxt else None
        tag = f" *observed: {e['observed']}*" if e.get("observed") else " *anticipated*"
        out.append(f"- **{e['ext']}** (from: {src.get('label')}){tag}")
        out += [f"  - {line}" for line in lines]
    return "\n".join(out)


# Owner's scale for how often a run comes back to tier 0 (2026-11-20). A *turn* is one return of
# control to tier 0: consecutive tier-0 steps on a path are one turn, since the agent is invoked once.
TIER0_GRADES = ((2, "ideal"), (3, "expected"), (4, "rusty"), (10, "bad"))


def tier0_lane(spec: dict) -> str | None:
    # "Tier 0 agent" in the older specs; "Overseer (tier 0)" in the packs (docs/terminology.md).
    return next((lane for lane in spec["lanes"] if "tier 0" in lane.lower()), None)


def full_sequence(spec: dict, p: dict) -> list[str]:
    """Every node a run on this path visits, to its end: a path that rejoins continues along the main path."""
    start = next(n["id"] for n in spec["nodes"] if n["kind"] == "start")
    seq = [start] + [e["to"] for e in p["edges"]]
    if p.get("rejoin"):
        happy = main_path(spec)
        seq += happy[happy.index(p["rejoin"]) + 1:]
    return seq


def tier0_turns(spec: dict, p: dict) -> int:
    lane = tier0_lane(spec)
    if lane is None:
        return 0
    nodes = {n["id"]: n for n in spec["nodes"]}
    turns, inside = 0, False
    for nid in full_sequence(spec, p):
        n = nodes[nid]
        if n["kind"] in ("fork", "join"):
            continue                                   # transparent: they hand nothing to anyone
        here = n.get("lane") == lane
        if here and not inside:
            turns += 1
        inside = here
    return turns


def grade(turns: int) -> str:
    for limit, name in TIER0_GRADES:
        if turns <= limit:
            return name
    return "bad" if turns <= 10 else "might as well have done it themselves"


def tree_and_tests(spec: dict, all_paths: list[dict]) -> tuple[str, str]:
    nodes = {n["id"]: n for n in spec["nodes"]}
    tree = ["```text", f"start: {spec['title']}"]
    t0 = tier0_lane(spec)
    rows = (["| Test | Path (guards taken) | Extension | Expected outcome | Tier-0 turns |",
             "|---|---|---|---|---|"] if t0 else
            ["| Test | Path (guards taken) | Extension | Expected outcome |", "|---|---|---|---|"])
    for i, p in enumerate(all_paths, 1):
        guards = [f"{nodes[e['from']]['label']} → {e['guard']}" for e in p["edges"] if e.get("guard")]
        exts = [e["ext"] for e in p["edges"] if e.get("ext")]
        if p["end"]:
            result = nodes[p["end"]]["label"]
        else:
            happy = main_path(spec)
            s = first_step_after(spec, happy, happy.index(p["rejoin"]))
            joined = "joins the main flow at" if p.get("kind") == "concurrent" else "rejoins at"
            r = nodes[p["rejoin"]]
            result = (f"{joined} step {r['step']}" if r.get("step")
                       else f"{joined} '{r['label']}' (before step {s})")
        depth = len(guards)
        tree.append("  " * depth + f"└─ T{i}: " + (" / ".join(g.split(" → ")[1] for g in guards) or "(no decision)")
                    + f"  ⇒ {result}")
        label = ", ".join(exts) or ("concurrent branch" if p.get("kind") == "concurrent" else "MSS")
        escalated = bool(p["end"]) and outcome(nodes[p["end"]]) == "escalated"
        extra = (f" {tier0_turns(spec, p)} (escalated: a failure) |" if escalated
                 else f" {tier0_turns(spec, p)} ({grade(tier0_turns(spec, p))}) |") if t0 else ""
        rows.append(f"| T{i} | {'; '.join(guards) or '—'} | {label} | {result} |{extra}")
    tree.append("```")
    return "\n".join(tree), "\n".join(rows)


def cross_check(spec: dict, all_paths: list[dict]) -> list[str]:
    nodes = {n["id"]: n for n in spec["nodes"]}
    flags = []
    ext_edges = [e for e in spec["edges"] if e.get("ext")]
    covered = {e["ext"] for p in all_paths for e in p["edges"] if e.get("ext")}
    for e in ext_edges:
        if e["ext"] not in covered:
            flags.append(f"extension {e['ext']} has no path through the diagram")
    on_main = set(main_path(spec))
    # Only a decision on the main path numbers its other ways out; one inside an extension is part of
    # that extension's text ("3a3 If declined: ...").
    for d in (n for n in spec["nodes"] if n["kind"] == "decision" and n["id"] in on_main):
        outs = [e for e in spec["edges"] if e["from"] == d["id"]]
        unhappy = [e for e in outs if not e.get("ext")]
        if len(unhappy) > 1:
            flags.append(f"decision '{d['label']}' has {len(unhappy)} unnumbered ways out; one is the happy path, "
                         f"the rest need extension numbers")
    for e in spec["edges"]:
        if e.get("guard") and nodes[e["from"]]["kind"] != "decision" and not e.get("ext"):
            pass
    # An extension is numbered by the step it belongs to: the numbered step just before its decision
    # on the flow, or the one just after it (a check made before a step is part of that step).
    happy = main_path(spec)
    preds = defaultdict(list)
    for x in spec["edges"]:
        preds[x["to"]].append(x["from"])
    for e in ext_edges:
        d = e["from"]
        before = after = None
        if d in happy:
            i = happy.index(d)
            before = next((step_of(spec, n) for n in reversed(happy[:i]) if step_of(spec, n)), None)
            after = first_step_after(spec, happy, i)
        else:                                 # inside a fork's side branch
            p0 = preds[d][0]
            before = step_of(spec, p0)
        number = int(re.match(r"\d+", e["ext"]).group())
        if number not in {before, after}:
            flags.append(f"extension {e['ext']} leaves '{nodes[d]['label']}', which sits between steps "
                         f"{before} and {after}: number it {after}x (the step it belongs to) or {before}x")
    ended = sum(1 for p in all_paths if p["end"] and outcome(nodes[p["end"]]) in SUCCESS)
    if ended != 1:
        flags.append(f"{ended} paths reach the success end; exactly one (the MSS) was expected")
    return flags


def lane_load(spec: dict, all_paths: list[dict]) -> str:
    """How busy each lane is: on the happy path, and anywhere. The aim is quiet Owner and tier-0 lanes."""
    nodes = {n["id"]: n for n in spec["nodes"]}
    happy = set(main_path(spec))
    rows = ["| Lane | On the main success scenario | Anywhere in the diagram |", "|---|---|---|"]
    for lane in spec["lanes"]:
        mine = [n for n in spec["nodes"] if n.get("lane") == lane and n["kind"] in ("activity", "ref", "decision")]
        rows.append(f"| {lane} | {sum(n['id'] in happy for n in mine)} | {len(mine)} |")
    ends = defaultdict(int)
    for p in all_paths:
        if p["end"]:
            ends[outcome(nodes[p["end"]])] += 1
    if tier0_lane(spec):
        counts = [(tier0_turns(spec, p), i) for i, p in enumerate(all_paths, 1)
                  if not (p["end"] and outcome(nodes[p["end"]]) == "escalated")]
        escalations = len(all_paths) - len(counts)
        mss = counts[0][0]
        worst = max(counts)
        by_grade = defaultdict(int)
        for t, _ in counts:
            by_grade[grade(t)] += 1
        rows += ["", f"**Tier-0 turns** (each return of control to tier 0; owner's scale: 2 ideal, 3 expected, "
                     f"4 rusty, 5–10 bad, more: might as well have done it themselves). Main success scenario: "
                     f"**{mss} ({grade(mss)})**. Worst path: T{worst[1]}, **{worst[0]} ({grade(worst[0])})**. "
                     "Paths by grade: " + ", ".join(f"{k} {v}" for k, v in by_grade.items())
                 + (f"; escalated {escalations} (failures, not graded)" if escalations else "") + "."]
    rows += ["", "Paths by how they end: " + ", ".join(f"**{k}** {v}" for k, v in sorted(ends.items()))
             + (". Every *escalated* path is a failure of this use case: the work went back to tier 0."
                if ends.get("escalated") else ".")]
    return "\n".join(rows)


def check_references(spec: dict, library: dict) -> list[str]:
    """A reference must call a use case that exists, and handle exactly the outcomes it can end with."""
    flags = []
    outs = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
    for n in (x for x in spec["nodes"] if x["kind"] == "ref"):
        called = library.get(n["use_case"])
        if called is None:
            flags.append(f"{n['id']} calls {n['use_case']}, which has no spec here: its outcomes cannot be checked")
            continue
        theirs = {outcome(x) for x in called["nodes"] if x["kind"] == "end"}
        mine = {e.get("guard") for e in outs[n["id"]]}
        for missing in sorted(theirs - mine):
            flags.append(f"{n['id']} calls {n['use_case']} but does not handle its outcome '{missing}'")
        for extra in sorted(mine - theirs - {None}):
            flags.append(f"{n['id']} handles '{extra}', which {n['use_case']} never ends with")
    return flags


def canvas(spec: dict) -> dict:
    """One column per lane; rows by first visit in flow order. Ends sit under their source."""
    colour = {"start": "4", "end": "6", "decision": "5", "fork": "3", "join": "3", "activity": None}
    nodes = {n["id"]: n for n in spec["nodes"]}
    outs = defaultdict(list)
    for e in spec["edges"]:
        outs[e["from"]].append(e)
    start = next(n["id"] for n in spec["nodes"] if n["kind"] == "start")
    order, seen, todo = {}, set(), deque([(start, 0)])
    while todo:                                       # breadth-first rank = row
        cur, rank = todo.popleft()
        if cur in seen:
            continue
        seen.add(cur)
        order[cur] = rank
        for e in outs[cur]:
            todo.append((e["to"], rank + 1))
    colw, rowh, w, h = 420, 200, 360, 150
    lanes = list(spec["lanes"]) + [OUTCOMES]
    lane_x = {lane: 40 + i * colw for i, lane in enumerate(lanes)}
    used = defaultdict(int)
    out_nodes, out_edges = [], []
    for nid, rank in sorted(order.items(), key=lambda kv: kv[1]):
        n = nodes[nid]
        lane = n.get("lane")
        if n["kind"] == "end":                 # every end in its own column: the ways it can finish
            lane = OUTCOMES
        elif not lane:                         # the start: above the first lane
            lane = spec["lanes"][0]
        x = lane_x[lane]
        # A lane stacks downwards: a card sits at its flow row, or below the lane's last card if that
        # row is taken, so two cards in one lane never overlap.
        y = max(140 + rank * rowh, used[lane])
        used[lane] = y + h + 20
        label = n.get("label", n["kind"])
        text = (f"**{n['step']}.** " if n.get("step") else "") + (
            f"◇ {label}" if n["kind"] == "decision"
            else f"⇉ **{n.get('use_case')}**: {label}" if n["kind"] == "ref"
            else f"▬ {label}" if n["kind"] in ("fork", "join")
            else "● start" if n["kind"] == "start" else f"◉ {label}" if n["kind"] == "end" else label)
        card = {"id": nid, "type": "text", "x": x, "y": y, "width": w,
                "height": h if n["kind"] != "start" else 70, "text": text}
        if colour.get(n["kind"]):
            card["color"] = colour[n["kind"]]
        if n["kind"] == "ref":
            card["color"] = "2"
        if n["kind"] == "end" and outcome(n) not in SUCCESS | NEUTRAL:
            card["color"] = "1"
        if n["kind"] == "end":
            card["text"] += f"\n*outcome: {outcome(n)}*"
        out_nodes.append(card)
    top = max(max(used.values()) - 40, 140 + (max(order.values()) + 1) * rowh)
    for lane, x in lane_x.items():
        out_nodes.append({"id": "lane-" + re.sub(r"\W+", "-", lane), "type": "group", "x": x - 20, "y": 60,
                          "width": colw - 20, "height": top, "label": lane})
    for i, e in enumerate(spec["edges"]):
        edge = {"id": f"e{i}", "fromNode": e["from"], "toNode": e["to"]}
        if e.get("guard"):
            edge["label"] = f"[{e['guard']}]" + (f" {e['ext']}" if e.get("ext") else "")
            if e.get("ext"):
                edge["color"] = "1"
        out_edges.append(edge)
    title = {"id": "title", "type": "text", "x": 20, "y": -200, "width": colw * len(lane_x) - 40, "height": 220,
             "text": f"# {spec['title']}\n**Symptom:** {spec['problem']['symptom']}\n**Root cause:** "
                     f"{spec['problem']['root']}\nLanes are actors; red arrows are extensions (numbered); "
                     f"red ends are ways the use case ends without success; orange cards call another use case. "
                     f"Generated from `{spec.get('_file', 'the spec')}`."}
    return {"nodes": [title] + out_nodes, "edges": out_edges}


def main(path: str) -> int:
    p = Path(path)
    spec = load(p)
    spec["_file"] = p.name
    library = {}
    for other in p.parent.glob("*.spec.yaml"):           # use cases this one may call
        o = load(other)
        library[o["diagram"]] = o
    problems = validate(spec)
    all_paths = paths(spec)
    tree, tests = tree_and_tests(spec, all_paths)
    flags = cross_check(spec, all_paths) + check_references(spec, library)
    stem = p.name.replace(".spec.yaml", "")
    views = "\n".join([
        f"<!-- generated by render_spec.py from {p.name}; regenerate, do not edit -->",
        "## Validation", "", ("No problems: the spec passes the activity rules." if not problems
                              else "\n".join(f"- {x}" for x in problems)), "",
        "## Activity diagram (swimlanes)", "", "```mermaid", mermaid(spec), "```", "",
        "## Written use case (generated)", "", written_use_case(spec, all_paths), "",
        "## Lane load", "", lane_load(spec, all_paths), "",
        f"## Decision tree: {len(all_paths)} paths", "", tree, "",
        "## Test table: one test per path", "", tests, "",
        "## Cross-view check", "", ("No flags." if not flags else "\n".join(f"- {x}" for x in flags)), ""])
    (p.parent / f"{stem}.views.md").write_text(views, encoding="utf-8")
    (p.parent / f"{stem}.canvas").write_text(json.dumps(canvas(spec), indent=1), encoding="utf-8")
    print(f"{stem}: {len(problems)} problems, {len(all_paths)} paths, {len(flags)} flags")
    for x in problems + flags:
        print("  -", x)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
