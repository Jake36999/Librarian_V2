#!/usr/bin/env python
"""phase_walk: find phase deadlocks before a model does.

A session walks phases (explore: frame, map, need, search, judge, synthesise, check_out).
Each phase has an exit gate (`Session.missing`) that tells the model what to do, and a compact
tool bundle (`agent_runtime.BUNDLES`) that is the ONLY thing the live loop offers and enforces.
If a gate asks for a tool its own bundle does not offer, no model can ever leave that phase
(seen 2026-11-18: Map asks for update_plan; the bundle omits it; a model refused `advance` 15 times).

The existing scripted walks (tests/walks.py) call the registry without bundle enforcement, so
they cannot see this. This tool calls the registry the way the live loop does (same
`Loop.tools()` surface, same enforcement) and never calls a model, so it costs nothing.

Three checks, all deterministic:

  1. GATES   Every tool each phase's gate text names, versus the tool bundle that phase offers.
             Source-derived, so it covers states a single run never reaches.
  2. PROBE   Force a session into each phase (appending a `phase` event: the "skip" hack), then
             call each gate tool through the enforced registry with empty arguments and classify
             the refusal. TOOL_BUNDLE_REFUSED = deadlock; PHASE_GATE = the write is gated out of
             this phase; an argument error = reachable (the call got past the gates).
  3. WALK    A scripted agent walks explore / add_project / suggest end to end using only the
             offered tools. When a step is blocked it records the block, performs the step
             unenforced, and carries on, so one run lists every blocked phase instead of
             stopping at the first.

    python scripts/phase_walk.py                      # all three checks, text report
    python scripts/phase_walk.py --json out.json      # also write machine-readable results
    python scripts/phase_walk.py --check gates        # one check only (gates|probe|walk)
    python scripts/phase_walk.py --purpose explore    # restrict purposes
    python scripts/phase_walk.py --tier contribute    # the tier the lead runs at

Exit status is 1 when anything is blocked, so it can guard a build.
"""
from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
for key in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)                       # no live search, no paid model, ever
os.environ.setdefault("LIBRARIAN_CONFIG_DIR", tempfile.mkdtemp(prefix="phase-walk-config-"))

from resource_librarian import tools  # noqa: E402,F401  (registers every tool)
from resource_librarian.agent_runtime import required_bundle_actions  # noqa: E402
from resource_librarian.init import init  # noqa: E402
from resource_librarian.loop import Loop  # noqa: E402
from resource_librarian.registry import REGISTRY, Context  # noqa: E402
from resource_librarian.session import PURPOSES, Session, SessionStore  # noqa: E402
from resource_librarian.vault import Vault  # noqa: E402

TEXT_PURPOSES_FOR_WALK = ("explore", "add_project", "suggest")
# Judge's gate says "N undecided candidate(s)" without naming the tool that decides one.
IMPLICIT_GATE_TOOLS = {"judge": ("decide",)}
# A gate branch that only applies to some purposes. (phase, tool) -> the purposes it applies to.
ONLY_FOR = {
    ("map", "read_project"): {"suggest"},
    ("check_out", "update_plan"): {"apply"},
    ("check_out", "record_application"): {"apply"},
    ("check_out", "close_brief"): {"explore", "add_project", "suggest", "add_capability"},
}
# Gate text that offers a choice: the tool is one of two ways out, so being absent is by design,
# not a deadlock. (purpose, phase) -> tools.
ALTERNATIVES = {
    ("explore", "frame"): {"create_project"},   # or update_plan(fields={'project': ''})
    ("suggest", "map"): {"read_project"},       # only when the library's project access is on
    ("apply", "check_out"): {"close_brief"},    # that branch of the gate is for other purposes
}


# ----------------------------------------------------------------------------- a stub model

class _NoModel:
    """The loop wants a provider to exist; nothing here ever calls it."""

    def chat(self, *args, **kwargs):  # pragma: no cover
        raise RuntimeError("phase_walk never calls a model")


def seeded_vault(root: Path) -> Vault:
    from conftest import add_source          # tests' own fixture writer, so notes look real
    init(root, name="Phase Walk")
    add_source(root, "osquery", "Exposes the operating system as a relational database you "
               "query with SQL.", "Query operating system state such as processes and sockets.")
    add_source(root, "duckdb", "An in-process analytical SQL database for a laptop.",
               "Analytical queries over local files.")
    add_source(root, "painter", "Draws pictures of cats.", "Illustration.")
    return Vault(root)


# ----------------------------------------------------------------------------- the walker

class Walker:
    """One session driven the way the live loop drives a model."""

    def __init__(self, vault: Vault, tier: str = "contribute"):
        self.vault = vault
        from resource_librarian.agent_runtime import ProfileStore
        # The Core always supplies a profile store; without one the registry fails closed to
        # `consult`, which would make every write look tier-refused.
        self.loop = Loop(vault, _NoModel(), tier=tier, scribe=None, extras={
            "use_tool_bundles": True, "agent_profile": "lead", "caller": "phase_walk",
            "profile_store": ProfileStore(vault)})
        self.ctx = self.loop.ctx
        self.store = SessionStore(vault)

    # -- the surface -----------------------------------------------------------
    def offered(self) -> list[str]:
        """Exactly what the loop would send the model now; also arms enforcement."""
        return sorted(t.name for t in self.loop.tools())

    def session(self) -> Session:
        return self.store.load(self.ctx.session)

    def phase(self) -> str:
        return self.session().phase

    def missing(self) -> list[str]:
        return self.session().missing(self.vault)

    # -- calls -----------------------------------------------------------------
    def call(self, tool: str, **arguments) -> dict:
        """An enforced call: refused if the live loop would not have offered the tool."""
        self.offered()
        return REGISTRY.call(tool, arguments, self.ctx)

    def forced(self, tool: str, **arguments) -> dict:
        """The hack: the same call with bundle enforcement off (what a god-mode agent could do)."""
        self.offered()
        self.ctx.extras.pop("enforce_active_bundle", None)
        try:
            return REGISTRY.call(tool, arguments, self.ctx)
        finally:
            self.ctx.extras["enforce_active_bundle"] = True

    def person(self, tool: str, **arguments) -> dict:
        who = Context(tier="curate", vault=self.vault, session=self.ctx.session)
        return REGISTRY.call(tool, arguments, who)

    def force_phase(self, phase: str) -> None:
        """Skip to a phase without satisfying anything before it."""
        self.store.append(self.ctx.session, {"type": "phase", "to": phase, "skipped": "phase_walk"})

    def open(self, purpose: str, **arguments) -> dict:
        return REGISTRY.call("open_session", {"purpose": purpose, **arguments}, self.ctx)


def refusal_code(result: dict) -> str:
    """Short classification of a registry result."""
    if not isinstance(result, dict) or "error" not in result:
        return "ok"
    if result.get("error") == "refused":
        return str(result.get("refused") or "refused")      # the rule's code, e.g. TOOL_BUNDLE_REFUSED
    return "error"                                           # an ordinary failure (bad arguments etc.)


def short(value, n: int = 140) -> str:
    return re.sub(r"\s+", " ", json.dumps(value, default=str) if not isinstance(value, str) else value)[:n]


# ----------------------------------------------------------------------------- 1. gates

def _branches(source: str) -> dict[str, str]:
    """Split a gate function's source into the text of each `p == "phase"` branch."""
    marks = list(re.finditer(r'\b(?:el)?if p == "([a-z_]+)"', source))
    out: dict[str, str] = {}
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(source)
        out[mark.group(1)] = out.get(mark.group(1), "") + source[mark.start():end]
    return out


def gate_tools() -> dict[str, set[str]]:
    """phase -> registered tools its gate text asks the model to use."""
    # A person's own tools (tier curate) are never the model's to call, so a gate that waits for
    # one is not a bundle gap.
    names = {n for n in REGISTRY.names() if getattr(REGISTRY.get(n), "tier", "") != "curate"}
    # The assumptions tail applies to ASSUMPTION_PHASES whichever branch ran: handled below, so
    # keep it out of the last `p == ...` branch it textually follows.
    body = inspect.getsource(Session.missing).split("if p in ASSUMPTION_PHASES")[0]
    texts = _branches(body)
    for phase, text in _branches(inspect.getsource(Session._audited_missing)).items():
        texts[phase] = texts.get(phase, "") + text
    # the assumptions tail in `missing` applies to these phases whatever branch they took
    from resource_librarian.session import ASSUMPTION_PHASES
    for phase in ASSUMPTION_PHASES:
        texts[phase] = texts.get(phase, "") + ' "record_assumptions"'
    # Gates whose text does not name the tool the model needs. Found by the WALK, kept here so
    # the cheap static check stays honest about them.
    for phase, implied in IMPLICIT_GATE_TOOLS.items():
        texts[phase] = texts.get(phase, "") + "".join(f' "{name}"' for name in implied)
    found: dict[str, set[str]] = {}
    for phase, text in texts.items():
        # drop each branch's own `p == "phase"` condition line: its literals are phase names and
        # plan keys (the "ingest" phase would otherwise look like it names the ingest tool)
        text = "\n".join(line for line in text.split("\n")
                         if not re.search(r"\b(?:el)?if p == \"", line) or "out.append" in line)
        strings = " ".join(re.findall(r'"((?:[^"\\]|\\.)*)"', text))
        tokens = set(re.findall(r"[a-z][a-z_]+", strings))
        found[phase] = {t for t in tokens if t in names and t not in ("search",)} | (
            {"search"} if re.search(r"\bsearch with intent\b|\bsearch\(", strings) else set())
    return found


def needed_for(needed: dict[str, set[str]], purpose: str, phase: str) -> set[str]:
    """The phase's gate tools that apply to this purpose (a branch is often purpose-specific)."""
    return {t for t in needed.get(phase, set())
            if purpose in ONLY_FOR.get((phase, t), {purpose})}


def check_gates(purposes: list[str], tier: str) -> list[dict]:
    needed = gate_tools()
    rows = []
    tmp = Path(tempfile.mkdtemp(prefix="phase-walk-gates-"))
    try:
        vault = seeded_vault(tmp / "v")
        for purpose in purposes:
            w = Walker(vault, "consult" if purpose == "apply" else tier)
            opened = w.open(purpose, project="P" if purpose != "explore" else "", question="q")
            if "error" in opened:
                rows.append({"purpose": purpose, "phase": "*", "status": "could_not_open",
                             "detail": short(opened)})
                continue
            for phase in PURPOSES[purpose]:
                w.force_phase(phase)
                offered = set(w.offered())
                named = needed_for(needed, purpose, phase)
                # A session ends with close_session, which no gate names: the last phase of every
                # purpose has to offer it (the audited purpose lacked it until 2026-11-19).
                if phase == PURPOSES[purpose][-1]:
                    named = named | {"close_session"}
                absent = sorted(named - offered - ALTERNATIVES.get((purpose, phase), set()))
                guarded = set(required_bundle_actions(phase, purpose=purpose, project="P",
                                                      project_exists=False))
                rows.append({"purpose": purpose, "phase": phase, "gate_tools": sorted(named),
                             "offered": sorted(offered), "not_offered": absent,
                             "preflight_guarded": sorted(guarded & set(absent)),
                             "advance_offered": "advance" in offered,
                             "status": "BLOCKED" if absent else "ok"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


# ----------------------------------------------------------------------------- 2. probe

def check_probe(purposes: list[str], tier: str) -> list[dict]:
    needed = gate_tools()
    rows = []
    tmp = Path(tempfile.mkdtemp(prefix="phase-walk-probe-"))
    try:
        for purpose in purposes:
            for phase in PURPOSES[purpose]:
                vault = seeded_vault(tmp / f"{purpose}-{phase}")
                w = Walker(vault, "consult" if purpose == "apply" else tier)
                opened = w.open(purpose, project="P" if purpose != "explore" else "", question="q")
                if "error" in opened:
                    rows.append({"purpose": purpose, "phase": phase, "tool": "*",
                                 "result": "could_not_open", "detail": short(opened)})
                    break
                w.force_phase(phase)
                last = phase == PURPOSES[purpose][-1]
                if not last:
                    # `advance` is judged by the offered list: calling it would really advance.
                    present = "advance" in w.offered()
                    rows.append({"purpose": purpose, "phase": phase, "tool": "advance",
                                 "result": "ok" if present else "TOOL_BUNDLE_REFUSED",
                                 "reachable": present, "detail": "offered" if present
                                 else "a model cannot ask to leave this phase"})
                for tool in sorted(needed_for(needed, purpose, phase)):
                    w.force_phase(phase)                    # earlier probes must not move us
                    out = w.call(tool)                       # empty arguments on purpose
                    code = refusal_code(out)
                    reachable = code not in ("TOOL_BUNDLE_REFUSED", "PHASE_GATE", "TIER_REFUSED")
                    reachable = reachable or tool in ALTERNATIVES.get((purpose, phase), set())
                    rows.append({"purpose": purpose, "phase": phase, "tool": tool,
                                 "result": code, "reachable": reachable,
                                 "detail": short(out.get("detail") or out.get("error") or out, 110)})
                # the literal call syntax the gate hint teaches, versus the tool's schema
                if "update_plan" in needed_for(needed, purpose, phase):
                    for key in _hint_plan_keys(phase):
                        literal = w.forced("update_plan", **{key: "x"})
                        wrapped = w.forced("update_plan", fields={key: "x"})
                        rows.append({"purpose": purpose, "phase": phase,
                                     "tool": f"update_plan({key}=...)", "result":
                                     "hint_syntax_ok" if refusal_code(literal) == "ok"
                                     else "hint_syntax_rejected",
                                     "reachable": True, "detail":
                                     f"literal={refusal_code(literal)} wrapped={refusal_code(wrapped)}"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows


def _hint_plan_keys(phase: str) -> list[str]:
    """The `update_plan(key=...)` keys a phase's gate text teaches."""
    text = _branches(inspect.getsource(Session.missing)).get(phase, "")
    return sorted(set(re.findall(r"update_plan\(([a-z_]+)=", text)))


# ----------------------------------------------------------------------------- 3. walk

def _step(report: list[dict], w: Walker, phase: str, label: str, tool: str, **arguments) -> dict:
    """Try a step the enforced way; if blocked, record it and do it unenforced to continue."""
    out = w.call(tool, **arguments)
    code = refusal_code(out)
    entry = {"phase": phase, "step": label, "tool": tool}
    if code == "ok":
        entry["status"] = "ok"
        report.append(entry)
        return out
    if code in ("TOOL_BUNDLE_REFUSED", "PHASE_GATE", "TIER_REFUSED"):
        entry.update(status="BLOCKED", code=code, detail=short(out.get("detail") or out, 160))
        forced = w.forced(tool, **arguments)
        entry["continued_unenforced"] = refusal_code(forced) == "ok"
        if not entry["continued_unenforced"]:
            entry["unenforced_error"] = short(forced, 160)
        report.append(entry)
        return forced
    entry.update(status="FAIL", code=code, detail=short(out.get("detail") or out, 160))
    report.append(entry)
    return out


def _advance(report: list[dict], w: Walker, phase: str) -> None:
    out = w.call("advance")
    code = refusal_code(out)
    entry = {"phase": phase, "step": "advance", "tool": "advance"}
    if code == "ok" and out.get("moved"):
        entry["status"] = "ok"
        entry["to"] = out["moved"]
    elif code == "ok":
        entry.update(status="STUCK", detail="missing: " + short(out.get("missing"), 200))
        # keep walking: skip the phase the way a person's override would
        nxt = PURPOSES[w.session().purpose]
        i = nxt.index(phase)
        if i + 1 < len(nxt):
            w.force_phase(nxt[i + 1])
            entry["forced_to"] = nxt[i + 1]
    else:
        entry.update(status="BLOCKED", code=code, detail=short(out, 160))
    report.append(entry)


def walk_text_purpose(purpose: str, tier: str, *, vault: Vault | None = None,
                      stop_at: str = "", question: str = "How do we query host state?") -> list[dict]:
    """Walk one purpose. With `stop_at`, build the state up to that phase and park the session
    there (used by --prepare); `vault` is then the caller's and is kept."""
    tmp = Path(tempfile.mkdtemp(prefix="phase-walk-walk-"))
    report: list[dict] = []
    try:
        vault = vault or seeded_vault(tmp / "v")
        w = Walker(vault, tier)
        opened = w.open(purpose, **({"project": "Host Watch"} if purpose != "explore" else
                                    {"question": question}))
        if "error" in opened:
            return [{"phase": "open", "step": "open_session", "status": "FAIL",
                     "detail": short(opened)}]
        for phase in PURPOSES[purpose]:
            if phase == stop_at:
                w.store.append(w.ctx.session, {"type": "status", "status": "parked",
                                               "note": "prepared by phase_walk"})
                report.append({"phase": phase, "step": "parked", "tool": "-", "status": "ok",
                               "session": w.ctx.session})
                break
            if w.phase() != phase:
                w.force_phase(phase)
                report.append({"phase": phase, "step": "enter", "tool": "-",
                               "status": "FORCED", "detail": "previous phase did not advance"})
            if phase == "frame":
                if purpose == "explore":
                    _step(report, w, phase, "set the question", "update_plan",
                          fields={"question": "How do we query host state?"})
                else:
                    _step(report, w, phase, "create the project", "create_project",
                          name="Host Watch", stage="planning", summary="Watch our hosts.",
                          constraints={"license_class": "Permissive"}, disqualifiers=["needs a GPU"])
            elif phase == "ingest":
                _step(report, w, phase, "record what exists", "update_plan",
                      fields={"ingested": "none"})
            elif phase == "map":
                _step(report, w, phase, "orient search", "search",
                      query="operating system state", intent="orient")
                _step(report, w, phase, "record the map", "update_plan",
                      fields={"map": "host tooling is held under Unfiled"})
                if purpose == "suggest":        # no Need phase: the brief is opened here
                    _step(report, w, phase, "open a brief", "open_brief",
                          need="query operating system state as a database",
                          disqualifiers=["requires a GPU"])
            elif phase == "need":
                _step(report, w, phase, "open a brief", "open_brief",
                      need="query operating system state as a database",
                      disqualifiers=["requires a GPU"])
            elif phase == "search":
                for round_no in range(3):
                    _step(report, w, phase, f"research round {round_no + 1}", "research_round",
                          queries=["operating system state database", "process sockets"], brief="B1")
                    out = _step(report, w, phase, f"checkpoint {round_no + 1}", "checkpoint",
                                learned="the field says 'host instrumentation'",
                                subthreads=["host tables", "event streams"], next_targets=["osquery tables"])
                    if isinstance(out, dict) and out.get("stop"):
                        break
            elif phase == "judge":
                for c in w.session().candidates.values():
                    if c.disposition == "undecided":
                        keep = c.source == "osquery"
                        _step(report, w, phase, f"decide {c.source}", "decide", source=c.source,
                              disposition="keep" if keep else "reject",
                              **({"role": "exposes host state to queries"} if keep
                                 else {"reason": "does not do the job"}))
                _step(report, w, phase, "record assumptions", "record_assumptions", assumptions=[
                    {"assumption": "hosts run a local agent", "settled_by": "unverifiable"}])
            elif phase == "synthesise":
                _step(report, w, phase, "synthesis", "record_synthesis", outcome="offering",
                      together="osquery alone covers the need", unknowns="fleet scale",
                      open_first="osquery")
                staged = _step(report, w, phase, "draft offering", "draft_offering",
                               title="Host Watch Starter", summary="Start with osquery.",
                               claims=[{"text": "osquery turns host state into SQL tables",
                                        "source": "osquery",
                                        "quote": "exposes the operating system as a relational database you query with sql."}])
                if isinstance(staged, dict) and staged.get("offering"):
                    asked = _step(report, w, phase, "promote (ask)", "promote_offering",
                                  offering=staged["offering"])
                    if isinstance(asked, dict) and asked.get("question_id"):
                        w.person("answer", question_id=asked["question_id"], answer="yes")
                        _step(report, w, phase, "promote (after yes)", "promote_offering",
                              offering=staged["offering"])
            elif phase == "check_out":
                _step(report, w, phase, "close the brief", "close_brief", brief="B1",
                      coverage="covered", note="answered by osquery")
                _step(report, w, phase, "close the session", "close_session",
                      summary="Walked.", gaps="nothing on fleet-scale performance")
                break
            _advance(report, w, phase)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return report


def check_walk(purposes: list[str], tier: str) -> dict[str, list[dict]]:
    return {p: walk_text_purpose(p, tier) for p in purposes if p in TEXT_PURPOSES_FOR_WALK}


# ----------------------------------------------------------------------------- report

def summarise(results: dict) -> dict[str, dict[str, list[str]]]:
    """purpose -> phase -> tools a model needs there but is not offered, from every check."""
    out: dict[str, dict[str, set[str]]] = {}

    def add(purpose: str, phase: str, tool: str) -> None:
        if tool in ALTERNATIVES.get((purpose, phase), set()) or "(" in tool or tool in ("*", "-"):
            return
        out.setdefault(purpose, {}).setdefault(phase, set()).add(tool)

    for r in results.get("gates", []):
        for tool in r.get("not_offered", []):
            add(r["purpose"], r["phase"], tool)
    for r in results.get("probe", []):
        if r.get("reachable") is False:
            add(r["purpose"], r["phase"], r["tool"])
    for purpose, steps in results.get("walk", {}).items():
        for s in steps:
            if s["status"] == "BLOCKED":
                add(purpose, s["phase"], s["tool"])
    return {p: {ph: sorted(t) for ph, t in phases.items()} for p, phases in out.items()}


def render(results: dict) -> str:
    lines: list[str] = []
    if "gates" in results:
        lines += ["", "1. GATES  tools each phase's gate names vs the tools the phase offers",
                  "   (BLOCKED = a model can be told to call a tool it is not offered)", ""]
        lines.append(f"   {'purpose':15} {'phase':11} {'status':8} not offered")
        for r in results["gates"]:
            lines.append(f"   {r['purpose']:15} {r['phase']:11} {r['status']:8} "
                         f"{', '.join(r.get('not_offered', [])) or '-'}"
                         + ("   [preflight guard covers it]" if r.get("preflight_guarded") else ""))
    if "probe" in results:
        bad = [r for r in results["probe"] if r.get("reachable") is False]
        syn = [r for r in results["probe"] if r["result"] == "hint_syntax_rejected"]
        lines += ["", "2. PROBE  each gate tool called through the enforced registry (empty arguments)",
                  f"   {len(results['probe'])} probes, {len(bad)} unreachable, "
                  f"{len(syn)} hint-syntax mismatches", ""]
        for r in bad:
            lines.append(f"   UNREACHABLE  {r['purpose']}/{r['phase']}: {r['tool']}  -> {r['result']}")
        for r in syn:
            lines.append(f"   HINT SYNTAX  {r['purpose']}/{r['phase']}: {r['tool']} {r['detail']}")
    if "walk" in results:
        lines += ["", "3. WALK   scripted agent, enforced surface; blocked steps are noted then forced", ""]
        for purpose, steps in results["walk"].items():
            lines.append(f"   {purpose}")
            for s in steps:
                if s["status"] == "ok":
                    continue
                lines.append(f"     {s['phase']:11} {s['status']:8} {s['step']:22} {s.get('tool', '')}"
                             f"  {s.get('code', '')} {s.get('detail', '')[:110]}")
            ok = sum(1 for s in steps if s["status"] == "ok")
            lines.append(f"     ({ok} of {len(steps)} steps passed enforced)")
    summary = summarise(results)
    lines += ["", "SUMMARY   phases where a model needs a tool it is not offered (all checks combined)", ""]
    for purpose in PURPOSES:
        if purpose not in summary and purpose in results.get("walk", {}):
            lines.append(f"   {purpose:15} no blocked phase")
        for phase in PURPOSES[purpose]:
            tools = summary.get(purpose, {}).get(phase)
            if tools:
                lines.append(f"   {purpose:15} {phase:11} needs {', '.join(tools)}")
    dead = sorted(p for p in summary)
    lines += ["", f"   purposes with at least one blocked phase: {len(dead)} of "
                  f"{len(results.get('gates') and {r['purpose'] for r in results['gates']} or PURPOSES)}"]
    return "\n".join(lines)


def blocked(results: dict) -> bool:
    return bool(summarise(results)) or any(
        r["result"] == "hint_syntax_rejected" for r in results.get("probe", []))


def prepare(target: Path, tier: str, phases: list[str]) -> dict[str, str]:
    """Build a vault at `target` whose Sessions list holds one parked explore thread per phase,
    each forced into that phase with the state the earlier phases would have left, so a real model
    can be resumed (Sessions menu -> type a message) straight into a late phase.

        python scripts/phase_walk.py --prepare C:/path/vault --phase need --phase judge
        resource-librarian --vault C:/path/vault app --port 0
    """
    vault = seeded_vault(target)
    made: dict[str, str] = {}
    for phase in phases:
        steps = walk_text_purpose("explore", tier, vault=vault, stop_at=phase,
                                  question=f"phase_walk live check: resume in {phase}")
        made[phase] = next((s["session"] for s in steps if s.get("session")), "")
    return made


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--prepare", metavar="DIR", help="build a vault with parked sessions per --phase")
    ap.add_argument("--phase", action="append", help="with --prepare: explore phases to park in")
    ap.add_argument("--check", choices=("gates", "probe", "walk"), action="append")
    ap.add_argument("--purpose", action="append", choices=sorted(PURPOSES))
    ap.add_argument("--tier", default="contribute", choices=("consult", "contribute", "curate"))
    ap.add_argument("--json", help="write results here")
    args = ap.parse_args(argv)
    if args.prepare:
        made = prepare(Path(args.prepare), args.tier, args.phase or list(PURPOSES["explore"]))
        print(json.dumps(made, indent=1))
        return 0
    purposes = args.purpose or list(PURPOSES)
    checks = args.check or ["gates", "probe", "walk"]
    results: dict = {}
    if "gates" in checks:
        results["gates"] = check_gates(purposes, args.tier)
    if "probe" in checks:
        results["probe"] = check_probe(purposes, args.tier)
    if "walk" in checks:
        results["walk"] = check_walk(purposes, args.tier)
    print(render(results))
    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    return 1 if blocked(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
