#!/usr/bin/env python
"""Area A stress test: enforced phase walks for ALL 8 purposes (especially apply/consult,
start_pursuit, learn, add_capability, audited), backwards advance, revisit budget halving,
parking/resuming, rewind/branch, restricted allowed_bundles, 16-tool cap clipping,
narrowed/upkeep discrepancies, gate hint argument validation, and no-progress guard FP/FN.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
for key in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)

SCRATCH = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\area_a")
if SCRATCH.exists():
    shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["LIBRARIAN_CONFIG_DIR"] = str(SCRATCH / "config")

from resource_librarian import tools  # noqa: F401
from resource_librarian.agent_runtime import (
    AgentProfile, BUNDLES, MAX_BUNDLE_TOOLS, ProfileStore, bundle_selection, required_bundle_actions,
)
from resource_librarian.init import init
from resource_librarian.loop import Loop, NO_PROGRESS_REPEATS, UPKEEP_TOOLS, _no_progress_signature, narrowed
from resource_librarian.providers import Reply, ToolCall
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.session import PURPOSES, Session, SessionStore
from resource_librarian.vault import Vault


class ScriptedProvider:
    def __init__(self, turns: list[Reply]):
        self.turns = list(turns)
        self.calls = 0

    def chat(self, system, messages, tools=None, **kwargs):
        self.calls += 1
        if self.turns:
            return self.turns.pop(0)
        return Reply(text="done", tool_calls=[])


def make_vault(name: str) -> Vault:
    from conftest import add_source
    root = SCRATCH / name
    init(root, name=name)
    add_source(root, "osquery", "OS as SQL tables.", "Query host state.")
    add_source(root, "duckdb", "In-process analytical SQL.", "Local analytics.")
    return Vault(root)


def make_walker(vault: Vault, tier: str = "contribute", profile: str = "lead",
                profile_store: ProfileStore | None = None):
    ps = profile_store or ProfileStore(vault)
    loop = Loop(vault, ScriptedProvider([]), tier=tier, scribe=None, extras={
        "use_tool_bundles": True, "agent_profile": profile, "caller": "stress_a",
        "profile_store": ps,
    })
    return loop, loop.ctx


def call_enforced(loop: Loop, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    offered = [t.name for t in loop.tools()]
    out = REGISTRY.call(name, args, loop.ctx)
    return out, offered


def test_walk_apply_consult():
    """Walk apply end-to-end at tier=consult (documented Reader tier) AND tier=contribute."""
    results = {}
    for tier in ("consult", "contribute"):
        v = make_vault(f"walk_apply_{tier}")
        loop, ctx = make_walker(v, tier=tier)
        steps = []

        def step(label: str, tool: str, args: dict[str, Any]):
            out, offered = call_enforced(loop, tool, args)
            refused = out.get("refused") if isinstance(out, dict) else None
            err = out.get("error") if isinstance(out, dict) else None
            steps.append({
                "label": label, "tool": tool, "offered": tool in offered,
                "refused": refused, "error": err, "detail": str(out.get("detail", ""))[:180] if isinstance(out, dict) else "",
                "moved": out.get("moved") if isinstance(out, dict) else None,
                "phase": out.get("session", {}).get("phase") if isinstance(out, dict) and isinstance(out.get("session"), dict) else None,
            })
            return out

        o = step("open_session", "open_session", {"purpose": "apply", "question": "Query local sockets"})
        if isinstance(o, dict) and o.get("session"):
            ctx.session = o["session"]["session"]
            step("check_in:update_plan", "update_plan", {"fields": {"question": "Query local sockets"}})
            step("advance->find", "advance", {})
            step("find:search", "search", {"query": "osquery", "intent": "orient"})
            step("find:log_use", "log_use", {"source": "osquery", "used_for": "host socket audit"})
            step("advance->check_out", "advance", {})
            step("check_out:record_application", "record_application", {
                "title": "Host Socket Audit", "stage": "building", "outcome": "worked",
                "sources_used": ["osquery"], "needed": "Query host sockets",
                "found_and_taken": "Used osquery listening_ports",
                "replaced": "netstat", "should_learn": "Works on Windows",
            })
            # If record_application refused, try update_plan(no_application)
            if steps[-1]["refused"]:
                step("check_out:update_plan(no_application)", "update_plan",
                     {"fields": {"no_application": "consult tier cannot write application"}})
            step("close_session", "close_session", {"summary": "Applied osquery", "gaps": []})
        results[tier] = steps
    return results


def test_walk_start_pursuit():
    v = make_vault("walk_start_pursuit")
    loop, ctx = make_walker(v, tier="contribute")
    steps = []

    def step(label, tool, args):
        out, offered = call_enforced(loop, tool, args)
        steps.append({
            "label": label, "tool": tool, "offered": tool in offered,
            "refused": out.get("refused"), "error": out.get("error"),
            "detail": str(out.get("detail", ""))[:180],
            "moved": out.get("moved"),
            "missing": out.get("missing"),
            "phase": (out.get("session") or {}).get("phase") if isinstance(out.get("session"), dict) else None,
        })
        return out

    o = step("open_session", "open_session", {"purpose": "start_pursuit", "question": "BSc CS"})
    ctx.session = o["session"]["session"]
    step("frame:create_project", "create_project", {
        "name": "BSc CS", "stage": "active", "summary": "Finish CS degree",
        "pursuit_kind": "course", "goal": "Finish CS degree",
    })
    step("advance->inventory", "advance", {})
    step("inventory:search", "search", {"query": "osquery", "intent": "orient"})
    step("inventory:update_plan", "update_plan", {"fields": {"inventory": {"modules": ["OS"]}}})
    step("inventory:record_assumptions", "record_assumptions", {"assumptions": [
        {"assumption": "OS notes exist", "settled_by": "search", "how": "checked orient"}
    ]})
    step("advance->plan", "advance", {})
    step("plan:task_add", "task_add", {
        "note": "BSc CS", "text": "Finish Lab 1", "due": "2026-12-01",
    })
    step("advance->seed", "advance", {})
    step("seed:update_plan", "update_plan", {"fields": {"ingested": "none"}})
    step("advance->check_out", "advance", {})
    step("close_session", "close_session", {"summary": "Pursuit started", "gaps": []})
    return steps


def test_walk_learn():
    v = make_vault("walk_learn")
    # Seed a concept note so understanding_record can verify exact concept name
    cdir = v.root / "Concepts"
    cdir.mkdir(exist_ok=True)
    (cdir / "SQL joins.md").write_text("---\ntype: concept\nname: SQL joins\n---\n# SQL joins\nCombining rows across tables.\n", encoding="utf-8")
    loop, ctx = make_walker(v, tier="contribute")
    steps = []

    def step(label, tool, args):
        out, offered = call_enforced(loop, tool, args)
        steps.append({
            "label": label, "tool": tool, "offered": tool in offered,
            "refused": out.get("refused"), "error": out.get("error"),
            "detail": str(out.get("detail", ""))[:180],
            "moved": out.get("moved"),
            "missing": out.get("missing"),
            "phase": (out.get("session") or {}).get("phase") if isinstance(out.get("session"), dict) else None,
        })
        return out

    o = step("open_session", "open_session", {"purpose": "learn", "question": "Learn SQL"})
    ctx.session = o["session"]["session"]
    step("goal:update_plan", "update_plan", {"fields": {"goal": "Write joins", "deadline": "2026-12-01"}})
    step("advance->baseline", "advance", {})
    step("baseline:update_plan", "update_plan", {"fields": {"baseline": "Knows SELECT"}})
    step("advance->focus", "advance", {})
    step("focus:search", "search", {"query": "duckdb", "intent": "orient"})
    step("focus:update_plan", "update_plan", {"fields": {"focus": ["SQL joins"]}})
    step("advance->practice", "advance", {})
    step("practice:understanding_record", "understanding_record", {
        "concept": "SQL joins", "own_words": "INNER keeps matches; LEFT keeps all left rows",
        "confidence": "ok",
    })
    step("advance->consolidate", "advance", {})
    step("consolidate:understanding_record", "understanding_record", {
        "concept": "SQL joins", "own_words": "Verified INNER vs LEFT JOIN semantics against duckdb",
        "confidence": "solid",
    })
    step("consolidate:update_plan", "update_plan", {"fields": {"consolidated": True}})
    step("advance->next", "advance", {})
    step("next:task_add_per_hint_fails", "task_add", {"text": "Review: SQL joins", "due": "2026-12-01", "heading": "Understanding"})
    step("next:task_add_with_note", "task_add", {"note": "SQL joins", "text": "Review: SQL joins", "due": "2026-12-01", "heading": "Understanding"})
    step("next:update_plan(scheduled)", "update_plan", {"fields": {"scheduled": "spaced repetition"}})
    step("next:close_session", "close_session", {"summary": "Learned SQL joins", "gaps": []})
    return steps


def test_walk_add_capability():
    v = make_vault("walk_add_capability")
    loop, ctx = make_walker(v, tier="contribute")
    steps = []

    def step(label, tool, args):
        out, offered = call_enforced(loop, tool, args)
        steps.append({
            "label": label, "tool": tool, "offered": tool in offered,
            "refused": out.get("refused"), "error": out.get("error"),
            "detail": str(out.get("detail", ""))[:180],
            "moved": out.get("moved"),
            "missing": out.get("missing"),
            "phase": (out.get("session") or {}).get("phase") if isinstance(out.get("session"), dict) else None,
        })
        return out

    o = step("open_session", "open_session", {"purpose": "add_capability", "question": "Add calendar"})
    ctx.session = o["session"]["session"]
    step("candidate:capability_candidates", "capability_candidates", {})
    step("candidate:update_plan", "update_plan", {"fields": {"candidate": "semantic-scholar"}})
    step("advance->assess", "advance", {})
    local_doc = v.root / "Inbox" / "cap_readme.md"
    local_doc.parent.mkdir(exist_ok=True)
    local_doc.write_text("# Semantic Scholar MCP\nLicense: MIT. Read-only academic search.\n", encoding="utf-8")
    step("assess:ingest", "ingest", {"ref": "Inbox/cap_readme.md", "note": "Semantic Scholar MCP"})
    step("assess:update_plan", "update_plan", {"fields": {"assessment": "MIT, read-only"}})
    step("assess:record_assumptions", "record_assumptions", {"assumptions": [
        {"assumption": "Read-only API", "settled_by": "ingest", "how": "checked README"}
    ]})
    step("advance->propose", "advance", {})
    step("propose:capability_propose", "capability_propose", {
        "name": "sem-test", "command": "uvx", "args": ["s2-mcp-server==1.7.4"],
        "why": "Academic search (MIT, read-only)",
    })
    step("advance->install", "advance", {})
    step("install:capability_install", "capability_install", {"name": "sem-test"})
    # Person answers the install confirmation question (decline is a finished outcome)
    SessionStore(v).append(ctx.session, {"type": "answer", "id": "q1", "answer": "no, decline for test"})
    step("install:capability_install_after_answer", "capability_install", {"name": "sem-test"})
    step("advance->check_out", "advance", {})
    step("check_out:close_session", "close_session", {"summary": "Capability assessed", "gaps": []})
    return steps


def test_walk_audited():
    v = make_vault("walk_audited")
    loop, ctx = make_walker(v, tier="contribute")
    steps = []

    def step(label, tool, args):
        out, offered = call_enforced(loop, tool, args)
        steps.append({
            "label": label, "tool": tool, "offered": tool in offered,
            "refused": out.get("refused"), "error": out.get("error"),
            "detail": str(out.get("detail", ""))[:180],
            "moved": out.get("moved"),
            "missing": out.get("missing"),
            "phase": (out.get("session") or {}).get("phase") if isinstance(out.get("session"), dict) else None,
            "next": (out.get("session") or {}).get("next") if isinstance(out.get("session"), dict) else None,
        })
        return out

    o = step("open_session", "open_session", {"purpose": "audited", "question": "Audit host query"})
    ctx.session = o["session"]["session"]
    curate_ctx = Context(tier="curate", vault=v, session=ctx.session)
    req_out = REGISTRY.call("set_requirement", {
        "requirement_id": "R1", "text": "Verify osquery note exists",
        "closure": "human_judgment",
    }, curate_ctx)
    steps.append({"label": "curate:set_requirement", "refused": req_out.get("refused"), "error": req_out.get("error")})
    step("manage:audit_projection", "audit_projection", {})
    step("manage:update_plan", "update_plan", {
        "fields": {"proposal": {"requirements": ["R1"], "step": "Inspect osquery note"}}
    })
    step("advance->preflight", "advance", {})
    step("preflight:admit_contract", "admit_contract", {
        "contract_id": "C1", "requirements": ["R1"],
        "read": ["Sources/repository/osquery.md"],
        "write": [f".librarian/staging/audited/{ctx.session}/osquery-check.md"],
    })
    step("advance->execute", "advance", {})
    step("execute:get_note", "get_note", {"name": "osquery"})
    step("execute:stage_artifact", "stage_artifact", {
        "name": "osquery-check", "text": "Osquery note says OS as SQL tables.",
    })
    step("advance->audit", "advance", {})
    step("audit:audit_targets", "audit_targets", {})
    step("advance->reduce", "advance", {})
    step("reduce:reduce_round", "reduce_round", {})
    # Check close_session RIGHT HERE in reduce (where session.next tells the model to call close_session!)
    step("reduce:close_session_deadlock_check", "close_session", {"summary": "Audit complete", "gaps": ["R1 awaiting person"]})
    step("advance->manage", "advance", {})
    step("manage:close_session_deadlock_check", "close_session", {"summary": "Audit complete", "gaps": ["R1 awaiting person"]})
    return steps


def test_backwards_revisit_park_rewind_branch():
    v = make_vault("walk_backwards")
    loop, ctx = make_walker(v, tier="contribute")
    report: dict[str, Any] = {}

    o = call_enforced(loop, "open_session", {"purpose": "explore", "question": "Test transitions"})[0]
    sid = o["session"]["session"]
    ctx.session = sid
    call_enforced(loop, "advance", {})  # frame -> map
    call_enforced(loop, "search", {"query": "osquery", "intent": "orient"})
    call_enforced(loop, "update_plan", {"fields": {"map": "osquery exists"}})
    call_enforced(loop, "advance", {})  # map -> need

    # Revisit map (go backwards) and check budget halving
    s_before = SessionStore(v).load(sid)
    back = call_enforced(loop, "advance", {"target": "map"})
    s_after = SessionStore(v).load(sid)
    report["revisit_map"] = {
        "moved": back[0].get("moved"), "phase": s_after.phase,
        "budget_before": s_before.budget_left(), "budget_after": s_after.budget_left(),
        "visits": dict(s_after.visits),
    }

    # Check going backwards from check_out and learn/next!
    store = SessionStore(v)
    store.append(sid, {"type": "phase", "to": "check_out"})
    out_co, offered_co = call_enforced(loop, "advance", {"target": "synthesise"})
    report["back_from_check_out"] = {
        "advance_offered_in_check_out": "advance" in offered_co,
        "refused": out_co.get("refused"), "detail": out_co.get("detail"),
    }

    # Check going backwards from learn/next!
    v2 = make_vault("walk_learn_back")
    loop2, ctx2 = make_walker(v2, tier="contribute")
    o2 = call_enforced(loop2, "open_session", {"purpose": "learn", "question": "Test learn back"})[0]
    sid2 = o2["session"]["session"]
    ctx2.session = sid2
    SessionStore(v2).append(sid2, {"type": "phase", "to": "next"})
    out_next, offered_next = call_enforced(loop2, "advance", {"target": "practice"})
    report["back_from_learn_next"] = {
        "advance_offered_in_next": "advance" in offered_next,
        "refused": out_next.get("refused"), "detail": out_next.get("detail"),
    }

    # Park and resume from inside an active session + rewind & branch
    v3 = make_vault("walk_park_resume")
    loop3, ctx3 = make_walker(v3, tier="contribute")
    o3 = call_enforced(loop3, "open_session", {"purpose": "explore", "question": "Test park"})[0]
    sid3 = o3["session"]["session"]
    ctx3.session = sid3
    call_enforced(loop3, "advance", {})  # frame -> map
    park_out, offered_map = call_enforced(loop3, "park_session", {"note": "pausing"})
    # Park as curate, resume, rewind, branch
    c3 = Context(tier="curate", vault=v3, session=sid3)
    cur_park = REGISTRY.call("park_session", {"note": "curate pause"}, c3)
    cur_res = REGISTRY.call("resume_session", {"session_id": sid3}, c3)
    cur_branch = REGISTRY.call("branch_session", {"to_index": 0}, c3)
    cur_rewind = REGISTRY.call("rewind_session", {"to_index": 0}, c3)
    report["park_rewind_branch"] = {
        "park_session_offered_in_map": "park_session" in offered_map,
        "park_in_map_refused": park_out.get("refused"), "park_in_map_detail": park_out.get("detail"),
        "curate_park_status": cur_park.get("status"),
        "curate_resume_phase": (cur_res.get("session") or {}).get("phase") if isinstance(cur_res.get("session"), dict) else cur_res.get("phase"),
        "curate_branch_ok": not cur_branch.get("refused") and not cur_branch.get("error"),
        "curate_branch_id": cur_branch.get("branched") or cur_branch.get("session"),
        "curate_rewind_ok": not cur_rewind.get("refused") and not cur_rewind.get("error"),
        "curate_rewind_phase": (cur_rewind.get("session") or {}).get("phase") if isinstance(cur_rewind.get("session"), dict) else cur_rewind.get("phase"),
    }

    # Restricted allowed_bundles profile
    v4 = make_vault("walk_restricted_profile")
    ps = ProfileStore(v4)
    # Create a custom profile restricting allowed_bundles to ["read"] only
    from dataclasses import replace as _replace
    ps.save(_replace(ps.get("lead"), id="lead_restricted", allowed_bundles=["read"]))
    loop4, ctx4 = make_walker(v4, tier="contribute", profile="lead_restricted", profile_store=ps)
    offered_r = [t.name for t in loop4.tools()]
    try_open = REGISTRY.call("open_session", {"purpose": "explore", "question": "x"}, ctx4)
    report["restricted_profile"] = {
        "offered": offered_r,
        "open_session_refused": try_open.get("refused"),
        "detail": try_open.get("detail"),
    }

    # Bundle clipping & narrowed/upkeep audit across EVERY purpose/phase
    clipping = []
    hidden_in_bundle = []
    for purpose, phases in PURPOSES.items():
        for phase in phases:
            for project_exists in (True, False):
                req = required_bundle_actions(phase, purpose=purpose, project="P", project_exists=project_exists)
                sel = bundle_selection("contribute", phase, projects_on=True, working=True,
                                       purpose=purpose, project="P", project_exists=project_exists)
                raw_bundle = BUNDLES.get(sel.bundle_id)
                raw_tools = list(raw_bundle.names) if raw_bundle else []
                expected_all = list(dict.fromkeys(raw_tools + list(req) + ["read_result", "macro_run", "macro_plan"]))
                offered_names = [s.name for s in sel.offered]
                dropped_by_cap = [t for t in expected_all if t not in offered_names and t in {s.name for s in narrowed("contribute", phase=phase, projects_on=True, working=True)}]
                if dropped_by_cap:
                    clipping.append({
                        "purpose": purpose, "phase": phase, "project_exists": project_exists,
                        "total_needed": len(expected_all), "cap": MAX_BUNDLE_TOOLS,
                        "dropped": dropped_by_cap,
                    })
                shown = {s.name for s in narrowed("contribute", phase=phase, projects_on=True, working=True)}
                hidden = [t for t in raw_tools if t not in shown and t in REGISTRY]
                if hidden and project_exists:
                    hidden_in_bundle.append({"purpose": purpose, "phase": phase, "bundle": sel.bundle_id, "hidden": hidden})
    report["clipping_by_cap"] = clipping
    report["declared_in_bundle_but_hidden_by_narrowed"] = hidden_in_bundle
    return report


def test_no_progress_guard():
    """Test false positives and false negatives in Loop's no-progress guard."""
    report = {}

    # 1. Alternating refusals (A -> B -> A -> B -> A -> B -> A -> B): does it evade NO_PROGRESS_REPEATS?
    v1 = make_vault("np_alternating")
    ps1 = ProfileStore(v1)
    # In map phase, alternate advance (moved=False) and an unoffered tool refusal (e.g. open_brief)
    calls = []
    for i in range(6):
        calls.append(Reply(text="", tool_calls=[ToolCall(f"a{i}", "advance", {})]))
        calls.append(Reply(text="", tool_calls=[ToolCall(f"b{i}", "open_brief", {"need": "x"})]))
    calls.append(Reply(text="escaped", tool_calls=[]))
    prov1 = ScriptedProvider(calls)
    loop1 = Loop(v1, prov1, tier="contribute", scribe=None, max_steps=16, extras={
        "use_tool_bundles": True, "agent_profile": "lead", "caller": "np1", "profile_store": ps1,
    })
    o1 = REGISTRY.call("open_session", {"purpose": "explore", "question": "alt"}, loop1.ctx)
    loop1.ctx.session = o1["session"]["session"]
    REGISTRY.call("advance", {}, loop1.ctx)  # frame -> map
    turn1 = loop1.send("go")
    report["fn_alternating_refusals"] = {
        "stopped": turn1.stopped, "error": turn1.error, "provider_calls": prov1.calls,
        "evaded_guard": turn1.stopped != "no_progress" and prov1.calls > NO_PROGRESS_REPEATS + 1,
    }

    # 2. Repeated ordinary errors (not refusals, e.g. macro_plan('update_plan') -> ValueError / error dict)
    v2 = make_vault("np_errors")
    ps2 = ProfileStore(v2)
    calls2 = [Reply(text="", tool_calls=[ToolCall(f"e{i}", "macro_plan", {"macro_id": "update_plan"})])
              for i in range(8)]
    calls2.append(Reply(text="done", tool_calls=[]))
    prov2 = ScriptedProvider(calls2)
    loop2 = Loop(v2, prov2, tier="contribute", scribe=None, max_steps=12, extras={
        "use_tool_bundles": True, "agent_profile": "lead", "caller": "np2", "profile_store": ps2,
    })
    turn2 = loop2.send("go")
    report["fn_repeated_ordinary_errors"] = {
        "stopped": turn2.stopped, "error": turn2.error, "provider_calls": prov2.calls,
        "evaded_guard": turn2.stopped != "no_progress" and prov2.calls > NO_PROGRESS_REPEATS + 1,
    }

    # 3. Repeated bad arguments (TypeError / invalid_arguments, e.g. record_assumptions bad shape)
    v3 = make_vault("np_bad_args")
    ps3 = ProfileStore(v3)
    calls3 = [Reply(text="", tool_calls=[ToolCall(f"t{i}", "update_plan", {"map": "wrong_kwarg"})])
              for i in range(8)]
    calls3.append(Reply(text="done", tool_calls=[]))
    prov3 = ScriptedProvider(calls3)
    loop3 = Loop(v3, prov3, tier="contribute", scribe=None, max_steps=12, extras={
        "use_tool_bundles": True, "agent_profile": "lead", "caller": "np3", "profile_store": ps3,
    })
    o3 = REGISTRY.call("open_session", {"purpose": "explore", "question": "badargs"}, loop3.ctx)
    loop3.ctx.session = o3["session"]["session"]
    REGISTRY.call("advance", {}, loop3.ctx)  # map
    turn3 = loop3.send("go")
    report["fn_repeated_bad_args"] = {
        "stopped": turn3.stopped, "error": turn3.error, "provider_calls": prov3.calls,
        "evaded_guard": turn3.stopped != "no_progress" and prov3.calls > NO_PROGRESS_REPEATS + 1,
    }

    # 4. False positive check: 4 distinct calls whose refusal detail shares the first 160 chars
    sig_a = _no_progress_signature("get_note", {"refused": "R", "detail": "X" * 165 + "_item_1"})
    sig_b = _no_progress_signature("get_note", {"refused": "R", "detail": "X" * 165 + "_item_2"})
    report["fp_160_char_truncation_collision"] = {
        "sig_a": sig_a[:60] + "...", "equal_despite_diff_after_160": sig_a == sig_b,
    }

    # 5. Control check: 4 identical advance refusals DO trigger no_progress
    v5 = make_vault("np_control")
    ps5 = ProfileStore(v5)
    calls5 = [Reply(text="", tool_calls=[ToolCall(f"c{i}", "advance", {})]) for i in range(6)]
    prov5 = ScriptedProvider(calls5)
    loop5 = Loop(v5, prov5, tier="contribute", scribe=None, max_steps=12, extras={
        "use_tool_bundles": True, "agent_profile": "lead", "caller": "np5", "profile_store": ps5,
    })
    o5 = REGISTRY.call("open_session", {"purpose": "explore", "question": "ctrl"}, loop5.ctx)
    loop5.ctx.session = o5["session"]["session"]
    REGISTRY.call("advance", {}, loop5.ctx)
    turn5 = loop5.send("go")
    report["control_identical_advance"] = {
        "stopped": turn5.stopped, "provider_calls": prov5.calls, "error": turn5.error,
    }
    return report


def main():
    out = {
        "apply": test_walk_apply_consult(),
        "start_pursuit": test_walk_start_pursuit(),
        "learn": test_walk_learn(),
        "add_capability": test_walk_add_capability(),
        "audited": test_walk_audited(),
        "transitions_and_bundles": test_backwards_revisit_park_rewind_branch(),
        "no_progress_guard": test_no_progress_guard(),
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
