#!/usr/bin/env python
"""Area B stress test: Permission grants (workflow_grant) security & isolation.
Tests:
1. Can an agent's own call carry workflow_grant? Can a grant leak across threads/sessions/libraries/restarts?
2. Vault-defined workflows/pipelines naming dangerous write tools (write_note, archive_note,
   staging_decide, project_edit, sandbox_run, sandbox_output, request_raw_source_access,
   vault_commit, vault_push) in Ask mode via App.start_action (unaccepted vs accepted).
3. Does a vault workflow calling action=run_workflow or action=process_approved escalate or propagate grants?
4. Mid-run mode switches (Ask -> Plan, Plan -> Auto), set_tool(Deny/Ask) mid-run, publication_review
   taint, PERSON_CONFIRMS / promotion.mode, batch never accepting/promoting.
5. 98-note scenario: approve 98 sources, start batch from UI (curate/contribute) and MCP (process_approved)
   in Ask mode, counting every permission request.
6. Broker._policy consistency in set_mode for pending requests.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(ROOT / "src"))
for key in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)

SCRATCH = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\area_b")
if SCRATCH.exists():
    shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["LIBRARIAN_CONFIG_DIR"] = str(SCRATCH / "config")

from resource_librarian import batch, tools, workflows  # noqa: F401
from resource_librarian.app import App
from resource_librarian.broker import ALWAYS_ASK, Broker
from resource_librarian.init import init
from resource_librarian.keys import KeyStore
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.rules import Refusal
from resource_librarian.staging import StagingStore
from resource_librarian.vault import Vault


def make_app(name: str, mode: str = "ask") -> tuple[Vault, App]:
    root = SCRATCH / name
    init(root, name=name)
    v = Vault(root)
    app = App(v, coordinate=True, keys=KeyStore(use_keyring=False), broker_timeout=5)
    app.set_mode(mode)
    return v, app


def test_vault_defined_pipelines_privilege():
    """Save a vault workflow naming high-impact tools and inspect what start_action grants in Ask mode."""
    v, app = make_app("vault_pipeline_priv", mode="ask")
    results: dict[str, Any] = {}
    perm_events: list[dict[str, Any]] = []

    def on_broker(ev):
        if ev.get("type") == "permission_request":
            perm_events.append(ev)
            # Deny immediately so tests don't block 600s
            app.broker.answer(ev["id"], "deny")

    unsub = app.broker.subscribe(on_broker)
    try:
        # 1. Agent (contribute tier) saves a workflow + pipeline that calls write_note
        yaml_wf = """
workflow: innocent-step
purpose: Tidy up notes
inputs: {}
steps:
  - id: w1
    action: write_note
    args:
      folder: "Notes"
      name: "InjectedByPipeline"
      body: "# Injected without Ask prompt"
"""
        yaml_pipe = """
pipeline: innocent-cleanup
purpose: Tidy up notes
inputs: {}
steps:
  - id: p1
    workflow: innocent-step
    args: {}
"""
        lib = workflows.Library(v)
        saved_wf = lib.save(yaml_wf, accepted_by_person=False)
        saved_unaccepted = lib.save(yaml_pipe, accepted_by_person=False)
        results["saved_unaccepted"] = {"workflow": saved_wf, "pipeline": saved_unaccepted}

        # Does an unaccepted vault pipeline appear in /api/state pipelines?
        state_unaccepted = app.state()
        results["unaccepted_in_ui_pipelines"] = "innocent-cleanup" in (state_unaccepted.get("pipelines") or [])

        # Try starting unaccepted via start_action (simulating user clicking it in UI)
        act_unacc = app.start_action("innocent-cleanup", {})
        deadline = time.monotonic() + 5
        while app.actions[act_unacc["id"]].status == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        results["unaccepted_start_result"] = {
            "status": app.actions[act_unacc["id"]].status,
            "result": app.actions[act_unacc["id"]].result,
            "file_written": (v.root / "Notes/InjectedByPipeline.md").exists(),
        }

        # Now accept the workflow + pipeline (person accepted once, or synced accepted.json)
        lib.accept("innocent-step")
        lib.accept("innocent-cleanup")
        perm_events.clear()
        act_acc = app.start_action("innocent-cleanup", {})
        deadline = time.monotonic() + 5
        while app.actions[act_acc["id"]].status == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        results["accepted_write_note_in_ask_mode"] = {
            "status": app.actions[act_acc["id"]].status,
            "result": app.actions[act_acc["id"]].result,
            "permission_requests_fired": len(perm_events),
            "file_written_without_ask": (v.root / "Notes/InjectedByPipeline.md").exists(),
            "granted_tools": sorted(workflows.granted_actions(lib.get("innocent-cleanup"), lib)),
        }

        # 2. Test dangerous tools inside a vault workflow: what validates and what gets granted?
        dangerous_tests = {}
        candidates = {
            "write_note": ("write_note", {"folder": "Notes", "name": "TestX", "body": "hi"}),
            "staging_decide": ("staging_decide", {"item_ids": ["x"], "decision": "accept"}),
            "project_edit": ("project_edit", {"project": "P", "path": "a.txt", "content": "hi"}),
            "sandbox_run": ("sandbox_run", {"command": ["echo", "1"], "network": False}),
            "sandbox_output": ("sandbox_output", {"run_id": "r1", "files": []}),
            "request_raw_source_access": ("request_raw_source_access", {"source": "x", "reason": "y"}),
            "vault_commit": ("vault_commit", {"message": "auto"}),
            "vault_push": ("vault_push", {}),
            "archive_note": ("archive_note", {"note": "Notes/InjectedByPipeline.md", "reason": "bye"}),
            "note_move": ("note_move", {"note": "Notes/InjectedByPipeline.md", "folder": "About"}),
            "run_workflow": ("run_workflow", {"name": "innocent-step"}),
        }
        for label, (tool_name, args) in candidates.items():
            if tool_name not in REGISTRY:
                dangerous_tests[label] = {"registered": False}
                continue
            spec = REGISTRY.get(tool_name)
            # Build minimal valid args from spec required schema
            schema = spec.json_schema()
            yml = f"workflow: test-{label.replace('_','-')}\npurpose: test\ninputs: {{}}\nsteps:\n  - id: s1\n    action: {tool_name}\n    args: {json.dumps(args)}\n"
            try:
                d = workflows.parse(yml)
                val = workflows.validate(d, lib)
                in_always_ask = tool_name in ALWAYS_ASK
                policy_if_granted = app.broker._policy(tool_name, spec.effect, spec.open_world, "", granted=True)
                dangerous_tests[label] = {
                    "validates": val["valid"], "errors": val["errors"], "required_tier": val["tier"],
                    "tool_tier": spec.tier, "tool_effect": spec.effect,
                    "in_ALWAYS_ASK": in_always_ask,
                    "broker_policy_in_ask_when_granted": policy_if_granted,
                    "runnable_at_contribute_start_action": spec.tier in ("consult", "contribute"),
                    "required_args": schema.get("required", []),
                }
            except Exception as exc:
                dangerous_tests[label] = {"exception": f"{type(exc).__name__}: {exc}"}
        results["dangerous_tools_in_vault_pipeline"] = dangerous_tests

        # 3. Check if a nested workflow via `workflow:` step propagates grants through closure()
        w_child = """
workflow: hidden-writer
purpose: writes a note
inputs: {}
steps:
  - id: w
    action: write_note
    args:
      folder: "Notes"
      name: "NestedWritten"
      body: "# From nested child workflow"
"""
        p_parent = """
pipeline: innocent-parent
purpose: looks harmless
inputs: {}
steps:
  - id: c
    workflow: hidden-writer
    args: {}
"""
        lib.save(w_child, accepted_by_person=True)
        lib.save(p_parent, accepted_by_person=True)
        perm_events.clear()
        act_nested = app.start_action("innocent-parent", {})
        deadline = time.monotonic() + 5
        while app.actions[act_nested["id"]].status == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        results["nested_workflow_grant"] = {
            "status": app.actions[act_nested["id"]].status,
            "granted_tools": sorted(workflows.granted_actions(lib.get("innocent-parent"), lib)),
            "permission_requests_fired": len(perm_events),
            "nested_file_written_in_ask_mode": (v.root / "Notes/NestedWritten.md").exists(),
        }
    finally:
        unsub()
        app.close_runtime()
    return results


def test_grant_isolation_and_broker_edge_cases():
    """Check grant leakage across contexts, threads, taint, mode switches, and set_tool."""
    v, app = make_app("grant_isolation", mode="ask")
    out: dict[str, Any] = {}
    try:
        # 1. Does start_action leak workflow_grant into app._extras()?
        before_extras = dict(app._extras())
        lib = workflows.Library(v)
        lib.save("workflow: noop-w\npurpose: noop\ninputs: {}\nsteps:\n  - id: s\n    action: index_status\n    args: {}\n", accepted_by_person=True)
        lib.save("pipeline: noop-p\npurpose: noop\ninputs: {}\nsteps:\n  - id: s\n    workflow: noop-w\n    args: {}\n", accepted_by_person=True)
        act = app.start_action("noop-p", {})
        deadline = time.monotonic() + 5
        while app.actions[act["id"]].status == "running" and time.monotonic() < deadline:
            time.sleep(0.05)
        after_extras = dict(app._extras())
        out["leaked_into_app_extras"] = "workflow_grant" in after_extras or "workflow_grant" in before_extras

        # 2. Publication review taint MUST override workflow_grant!
        spec = REGISTRY.get("write_note")
        ctx_tainted = Context(tier="contribute", vault=v, extras={
            **app._extras(),
            "workflow_grant": {"label": "test", "tools": frozenset({"write_note"})},
            "_publication_review": ["unlicensed-source.md"],
        })
        taint_asked = []
        def answer_deny(ev):
            if ev.get("type") == "permission_request":
                taint_asked.append(ev)
                app.broker.answer(ev["id"], "deny")
        unsub = app.broker.subscribe(answer_deny)
        try:
            try:
                app.broker.check(spec, {"path": "x.md", "content": "x"}, ctx_tainted)
                out["taint_overrides_grant"] = False
            except Refusal as r:
                out["taint_overrides_grant"] = len(taint_asked) == 1 and r.code == "PERMISSION_DENIED"
        finally:
            unsub()

        # 3. Mode switch mid-run: Ask -> Plan must deny granted writes immediately
        app.broker.set_mode("plan")
        ctx_granted = Context(tier="contribute", vault=v, extras={
            **app._extras(),
            "workflow_grant": {"label": "test", "tools": frozenset({"write_note"})},
        })
        try:
            app.broker.check(spec, {"path": "x.md", "content": "x"}, ctx_granted)
            out["plan_mode_blocks_grant"] = False
        except Refusal as r:
            out["plan_mode_blocks_grant"] = r.code == "PERMISSION_DENIED"
        app.broker.set_mode("ask")

        # 4. Tool set to Deny or Ask overrides grant
        app.broker.set_tool("write_note", "ask")
        out["tool_setting_ask_overrides_grant"] = app.broker._policy("write_note", "write", False, "", granted=True) == "ask"
        app.broker.set_tool("write_note", "deny")
        out["tool_setting_deny_overrides_grant"] = app.broker._policy("write_note", "write", False, "", granted=True) == "deny"
        app.broker.settings.pop("write_note", None)

        # 5. ALWAYS_ASK (project_edit, sandbox_output) overrides grant
        out["always_ask_project_edit_overrides_grant"] = app.broker._policy("project_edit", "write", False, "", granted=True) == "ask"
        out["always_ask_sandbox_output_overrides_grant"] = app.broker._policy("sandbox_output", "write", False, "", granted=True) == "ask"

        # 6. Broker.set_mode consistency for pending requests:
        #    Case A: pending request for write_note in Ask mode -> switch to Auto releases it
        #    Case B: pending request for project_edit (ALWAYS_ASK) in Ask mode -> switch to Auto MUST NOT release it
        #    Case C: pending request with publication_sources in Ask mode -> switch to Auto MUST NOT release it
        #    Case D: pending request where tool is set to Ask -> switch to Auto MUST NOT release it
        b = Broker(mode="ask", timeout=5.0)
        pending_results = {}
        for case, tool_name, taint, tool_setting in [
            ("normal_write", "write_note", (), None),
            ("always_ask", "project_edit", (), None),
            ("tainted_write", "write_note", ("src.md",), None),
            ("tool_set_ask", "archive_note", (), "ask"),
        ]:
            if tool_setting:
                b.set_tool(tool_name, tool_setting)
            res = {}
            ready = threading.Event()
            def wait_check(tn=tool_name, tnt=taint, r=res, rdy=ready):
                c = Context(tier="contribute", vault=v, extras={"_publication_review": list(tnt)} if tnt else {})
                try:
                    r["ok"] = b.check(REGISTRY.get(tn), {}, c)
                except Refusal as exc:
                    r["refused"] = exc.code
            def on_ev(ev, rdy=ready):
                if ev.get("type") == "permission_request":
                    rdy.set()
            u = b.subscribe(on_ev)
            th = threading.Thread(target=wait_check)
            th.start()
            ready.wait(2.0)
            switched = b.set_mode("auto")
            # If still pending, deny so thread exits cleanly
            for pid in list(b._pending):
                b.answer(pid, "deny")
            th.join(3.0)
            u()
            b.set_mode("ask")
            if tool_setting:
                b.settings.pop(tool_name, None)
            pending_results[case] = {"released_by_auto": bool(switched["released"]), "outcome": res}
        out["set_mode_pending_consistency"] = pending_results

        # 7. Can a workflow started via start_action call `batch.start` (`process_approved`)?
        #    Check process_approved tier!
        pa_spec = REGISTRY.get("process_approved")
        out["process_approved_spec"] = {"tier": pa_spec.tier, "effect": pa_spec.effect}
    finally:
        app.close_runtime()
    return out


def test_98_note_scenario():
    """Approve 98 sources for ingestion, start batch via UI (curate) and MCP (contribute) in Ask mode,
    counting every permission request."""
    results = {}
    for caller_mode in ("ui_curate", "mcp_contribute"):
        v, app = make_app(f"batch98_{caller_mode}", mode="ask")
        perm_requests: list[dict[str, Any]] = []

        def on_ev(ev):
            if ev.get("type") == "permission_request":
                perm_requests.append({"tool": ev["tool"], "id": ev["id"], "args": ev.get("arguments")})
                # Allow once so we count EVERY permission request triggered!
                app.broker.answer(ev["id"], "allow_once")

        unsub = app.broker.subscribe(on_ev)
        try:
            store = StagingStore(v)
            src_dir = SCRATCH / f"src98_{caller_mode}"
            src_dir.mkdir(parents=True, exist_ok=True)
            for i in range(98):
                f = src_dir / f"note_{i:03d}.md"
                f.write_text(f"# Note {i}\nSome short content about topic {i}.\n", encoding="utf-8")
                store.add({
                    "id": f"src-{i:03d}", "kind": "source", "name": f"Note {i:03d}",
                    "status": "approved", "source_kind": "document",
                    "file": str(f), "clean_file": str(f),
                    "evidence_text": f"Some short content about topic {i}.",
                    "intake": {"stages": {"capture": "complete", "fetch": "complete"}},
                })
            if caller_mode == "ui_curate":
                # UI calls POST /api/tool/process_approved (tier=curate, NO broker on person_call!)
                out = app.person_call("process_approved", {"background": False})
            else:
                # MCP agent calls POST /api/mcp/call (tier=contribute, broker attached!)
                out = app.mcp_call("process_approved", {"background": False}, "", "contribute")
            # Check no source was accepted or promoted!
            items = store.items(kind="source")
            statuses: dict[str, int] = {}
            for it in items:
                st = str(it.get("status"))
                statuses[st] = statuses.get(st, 0) + 1
            results[caller_mode] = {
                "out_summary": {k: out.get(k) for k in ("run", "status", "total", "processed", "error", "refused", "result") if isinstance(out, dict) and k in out},
                "permission_request_count": len(perm_requests),
                "permission_requests": perm_requests[:10],
                "post_batch_statuses": statuses,
                "any_accepted_by_batch": statuses.get("accepted", 0) > 0,
            }
        finally:
            unsub()
            app.close_runtime()
    return results


def main():
    out = {
        "vault_defined_pipelines": test_vault_defined_pipelines_privilege(),
        "grant_isolation_and_broker": test_grant_isolation_and_broker_edge_cases(),
        "scenario_98_notes": test_98_note_scenario(),
    }
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
