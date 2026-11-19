#!/usr/bin/env python
"""Area C stress test: Checkpoints & macro approval reuse in run_macro.
Tests:
1. Original no-id loop (request -> approve -> re-call without checkpoint_id -> runs!).
2. Same scope twice after completion (does completed approval block legitimate re-run forever?).
3. Expired approval (expires_at in the past -> must NOT reuse!).
4. Changed inputs (different scope digest -> must NOT reuse!).
5. Two cards for one scope: Card 1 approved earlier, Card 2 explicitly cancelled later!
6. Two approved cards for one scope (Card 1 completed, Card 2 approved & unused -> which wins?).
7. Cross-session / cross-requester approval reuse: Session A gets approval, Session B calls without id!
8. Concurrent calls for the same macro scope!
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(ROOT / "src"))
for key in ("TAVILY_API_KEY", "BRAVE_API_KEY", "APIFY_TOKEN", "DEEPINFRA_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
    os.environ.pop(key, None)

SCRATCH = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\area_c")
if SCRATCH.exists():
    shutil.rmtree(SCRATCH, ignore_errors=True)
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ["LIBRARIAN_CONFIG_DIR"] = str(SCRATCH / "config")

from resource_librarian import tools  # noqa: F401
from resource_librarian.agent_runtime import MACROS, Macro, MacroStep, ProfileStore, _checkpoint_scope, run_macro
from resource_librarian.checkpoints import CheckpointStore
from resource_librarian.init import init
from resource_librarian.registry import Context
from resource_librarian.vault import Vault


# Register a deterministic local write-capable macro (identical to tests/test_macro_permissions.py)
# plus test real intake_to_stage (using its real input key: `ref`)
MACROS["_stress_write"] = Macro(
    "_stress_write", 1, "Write one note for checkpoint stress testing", (
        MacroStep("write_note", {"folder": "Notes", "name": "$name", "body": "$body"}),
    ), True)


def make_vault(name: str) -> tuple[Vault, CheckpointStore, Path]:
    root = SCRATCH / name
    init(root, name=name)
    v = Vault(root)
    doc = root / "Inbox" / "sample.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("# Sample Note\nSome factual content for testing macros.\n", encoding="utf-8")
    return v, CheckpointStore(v), doc


def ctx_for(v: Vault, cp: CheckpointStore, session: str | None = None, caller: str = "agent-A") -> Context:
    return Context(tier="contribute", vault=v, session=session, extras={
        "checkpoints": cp, "caller": caller, "profile_store": ProfileStore(v), "agent_profile": "lead",
    })


def open_real_session(v: Vault, question: str) -> str:
    from resource_librarian.registry import REGISTRY
    out = REGISTRY.call("open_session", {"purpose": "explore", "question": question},
                        Context(tier="curate", vault=v, extras={}))
    return out["opened"]


def main():
    report: dict[str, Any] = {}
    macro_id = "_stress_write"
    report["intake_to_stage_signature"] = {
        "steps": [(s.tool, s.arguments) for s in MACROS["intake_to_stage"].steps],
        "write_capable": MACROS["intake_to_stage"].write_capable,
    }

    # 1. Original no-id loop + 2. Same scope twice after completion
    v1, cp1, doc1 = make_vault("c1_loop_and_rerun")
    s1 = open_real_session(v1, "q1")
    inp1 = {"name": "Sample Note", "body": "Body v1"}
    r1 = run_macro(ctx_for(v1, cp1, s1), macro_id, inp1)
    cid1 = r1["checkpoint"]["id"]
    cp1.resolve(cid1, "approve")
    r2 = run_macro(ctx_for(v1, cp1, s1), macro_id, inp1)  # NO checkpoint_id
    r3 = run_macro(ctx_for(v1, cp1, s1), macro_id, inp1)  # Second time after completion!
    report["1_original_loop_fixed"] = {
        "first_status": r1.get("status"), "checkpoint_id": cid1,
        "after_approve_no_id_status": r2.get("status"), "reused_flag_on_first_run": r2.get("reused"),
        "total_checkpoints": len(cp1.all()),
        "note_exists": (v1.root / "Notes" / "Sample Note.md").exists(),
    }
    report["2_same_scope_after_completion"] = {
        "third_call_status": r3.get("status"), "reused": r3.get("reused"),
        "detail": r3.get("detail"),
        "blocked_from_fresh_rerun": r3.get("reused") is True and len(cp1.all()) == 1,
    }

    # 3. Expired approval must NOT be reused
    v3, cp3, doc3 = make_vault("c3_expired")
    inp3 = {"name": "Sample Exp", "body": "Body"}
    scope3 = _checkpoint_scope(MACROS[macro_id], inp3)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    exp_card = cp3.create("macro_expansion", scope3, evidence={"macro": macro_id},
                          choices=["approve", "cancel"], default="cancel", expires_at=past)
    data = json.loads(cp3.path.read_text(encoding="utf-8"))
    data["checkpoints"][0]["resolution"] = "approve"
    cp3.path.write_text(json.dumps(data), encoding="utf-8")
    r_exp = run_macro(ctx_for(v3, cp3), macro_id, inp3)
    report["3_expired_approval"] = {
        "status": r_exp.get("status"),
        "reused_expired": r_exp.get("status") != "awaiting_checkpoint",
        "new_checkpoint_id": (r_exp.get("checkpoint") or {}).get("id"),
    }

    # 4. Changed inputs must NOT reuse approval
    v4, cp4, doc4 = make_vault("c4_changed_inputs")
    r4a = run_macro(ctx_for(v4, cp4), macro_id, {"name": "NoteA", "body": "A"})
    cp4.resolve(r4a["checkpoint"]["id"], "approve")
    r4b = run_macro(ctx_for(v4, cp4), macro_id, {"name": "NoteB", "body": "B"})
    report["4_changed_inputs"] = {
        "status": r4b.get("status"),
        "asked_again": r4b.get("status") == "awaiting_checkpoint",
        "new_id_differs": (r4b.get("checkpoint") or {}).get("id") != r4a["checkpoint"]["id"],
    }

    # 5. Two cards for same scope: Card 1 approved earlier, Card 2 explicitly cancelled later!
    v5, cp5, doc5 = make_vault("c5_approve_then_cancel")
    inp5 = {"name": "Cancel Test", "body": "Body"}
    scope5 = _checkpoint_scope(MACROS[macro_id], inp5)
    c_app = cp5.create("macro_expansion", scope5, evidence={"macro": macro_id}, choices=["approve", "cancel"], default="cancel")
    cp5.resolve(c_app["id"], "approve")
    c_can = cp5.create("macro_expansion", scope5, evidence={"macro": macro_id}, choices=["approve", "cancel"], default="cancel")
    cp5.resolve(c_can["id"], "cancel")
    r5 = run_macro(ctx_for(v5, cp5), macro_id, inp5)
    report["5_approve_then_later_cancel"] = {
        "approved_id": c_app["id"], "later_cancelled_id": c_can["id"],
        "run_status": r5.get("status"),
        "bypassed_later_cancel": r5.get("status") != "awaiting_checkpoint",
        "note_written_despite_later_cancel": (v5.root / "Notes" / "Cancel Test.md").exists(),
    }

    # 6. Two approved cards for one scope: Card 1 completed, Card 2 newly approved -> which wins?
    v6, cp6, doc6 = make_vault("c6_two_approved")
    inp6 = {"name": "Two Approved", "body": "Body"}
    scope6 = _checkpoint_scope(MACROS[macro_id], inp6)
    c6_1 = cp6.create("macro_expansion", scope6, evidence={"macro": macro_id}, choices=["approve", "cancel"], default="cancel")
    cp6.resolve(c6_1["id"], "approve")
    run_macro(ctx_for(v6, cp6), macro_id, {**inp6, "checkpoint_id": c6_1["id"]})  # completes c6_1
    c6_2 = cp6.create("macro_expansion", scope6, evidence={"macro": macro_id}, choices=["approve", "cancel"], default="cancel")
    cp6.resolve(c6_2["id"], "approve")
    r6 = run_macro(ctx_for(v6, cp6), macro_id, inp6)  # calls without id; reversed() picks c6_2!
    report["6_two_approved_cards"] = {
        "card1_completed": c6_1["id"], "card2_fresh_approved": c6_2["id"],
        "run_status": r6.get("status"), "reused_old_completed": r6.get("reused") is True,
    }

    # 7. Cross-session & cross-caller approval hijack: Session A asks & gets approved, Session B runs without id!
    v7, cp7, doc7 = make_vault("c7_cross_session")
    s7a = open_real_session(v7, "session A")
    s7b = open_real_session(v7, "session B")
    inp7 = {"name": "Cross Session", "body": "Body"}
    r7a = run_macro(ctx_for(v7, cp7, session=s7a, caller="agent-A"), macro_id, inp7)
    cp7.resolve(r7a["checkpoint"]["id"], "approve")
    r7b = run_macro(ctx_for(v7, cp7, session=s7b, caller="untrusted-mcp-B"), macro_id, inp7)
    report["7_cross_session_approval_reuse"] = {
        "session_A": s7a, "session_B": s7b,
        "session_A_checkpoint": r7a["checkpoint"]["id"],
        "session_A_scope": r7a["checkpoint"]["scope"],
        "session_B_status": r7b.get("status"),
        "session_B_reused_session_A_approval": r7b.get("status") != "awaiting_checkpoint",
        "note_written_by_session_B": (v7.root / "Notes" / "Cross Session.md").exists(),
    }

    # 8. Concurrent calls for the same macro scope (two threads racing after one approval)
    v8, cp8, doc8 = make_vault("c8_concurrent")
    s8a = open_real_session(v8, "conc A")
    s8b = open_real_session(v8, "conc B")
    inp8 = {"name": "Concurrent", "body": "Body"}
    r8_init = run_macro(ctx_for(v8, cp8, session=s8a), macro_id, inp8)
    cp8.resolve(r8_init["checkpoint"]["id"], "approve")
    barrier = threading.Barrier(2)
    conc_out = [None, None]
    sessions8 = [s8a, s8b]
    def worker(idx):
        barrier.wait()
        conc_out[idx] = run_macro(ctx_for(v8, cp8, session=sessions8[idx]), macro_id, inp8)
    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))
    t1.start(); t2.start(); t1.join(); t2.join()
    report["8_concurrent_same_approval"] = {
        "t0_status": (conc_out[0] or {}).get("status"), "t0_reused": (conc_out[0] or {}).get("reused"),
        "t1_status": (conc_out[1] or {}).get("status"), "t1_reused": (conc_out[1] or {}).get("reused"),
        "both_ran_not_reused": (conc_out[0] or {}).get("reused") is not True and (conc_out[1] or {}).get("reused") is not True,
        "journal_events": len(list((v8.librarian / "runs").glob("macro-*.jsonl"))),
    }

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
