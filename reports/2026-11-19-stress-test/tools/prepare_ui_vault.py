#!/usr/bin/env python
"""Prepare a rich scratch vault for live UI + real-model stress testing (with $0.50 budget cap)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\Librarian_V2")
sys.path.insert(0, str(ROOT / "src"))
VAULT_DIR = Path(
    r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\ui-live-vault"
)
if VAULT_DIR.exists():
    shutil.rmtree(VAULT_DIR, ignore_errors=True)

# 1. Use scripts/phase_walk.py --prepare to create a vault with guide + seeded notes + parked sessions
subprocess.run(
    [
        str(ROOT / ".venv/Scripts/python.exe"),
        str(ROOT / "scripts/phase_walk.py"),
        "--prepare", str(VAULT_DIR),
        "--phase", "map",
        "--phase", "need",
        "--phase", "search",
        "--phase", "judge",
        "--phase", "synthesise",
        "--phase", "check_out",
    ],
    check=True,
)

# 2. Enforce $0.50 spend cap BEFORE any model call!
cfg_path = VAULT_DIR / ".librarian" / "config.toml"
cfg = cfg_path.read_text(encoding="utf-8")
if "[budget]" not in cfg:
    cfg += "\n[budget]\nceiling_usd = 0.5\n"
else:
    cfg = cfg.replace("[budget]", "[budget]\nceiling_usd = 0.5")
cfg_path.write_text(cfg, encoding="utf-8")

# 3. Add special-char notes for Pick Mode testing (Windows-legal chars: ]], #, `, unicode)
notes_dir = VAULT_DIR / "Notes"
notes_dir.mkdir(exist_ok=True)
(notes_dir / "café_日本語.md").write_text("---\ntype: note\n---\n# café_日本語\nUnicode note for pick-mode testing.\n", encoding="utf-8")
(notes_dir / "edge]]hash#tick`note.md").write_text("---\ntype: note\n---\n# Special chars\nNote with ]], #, and backtick.\n", encoding="utf-8")
# Duplicate filename in two folders to test [[wikilink]] ambiguity in Pick Mode
(notes_dir / "SubA").mkdir(exist_ok=True)
(notes_dir / "SubB").mkdir(exist_ok=True)
(notes_dir / "SubA" / "SharedName.md").write_text("# Shared A\nIn SubA.\n", encoding="utf-8")
(notes_dir / "SubB" / "SharedName.md").write_text("# Shared B\nIn SubB.\n", encoding="utf-8")

# 4. Seed 55 staged sources (to test "Showing 50 of 55" / "Show 50 more") + 1 enriched source with
#    capture quality=metadata_only (to test the updated "At capture... The batch has since run." banner)
from resource_librarian.staging import StagingStore
from resource_librarian.vault import Vault
from resource_librarian.session import SessionStore
from resource_librarian import tools  # noqa: F401
from resource_librarian.registry import REGISTRY, Context

v = Vault(VAULT_DIR)
store = StagingStore(v)
for i in range(55):
    store.add({
        "id": f"pager-src-{i:03d}",
        "kind": "source",
        "name": f"Pager Fixture Source {i + 1:03d}",
        "status": "staged",
        "source_kind": "document",
        "evidence_text": f"Evidence body for pager fixture {i + 1}.",
        "intake": {"stages": {"capture": "complete", "fetch": "complete"}},
    })

store.add({
    "id": "enriched-quality-check",
    "kind": "source",
    "name": "Enriched Quality Banner Check",
    "status": "enriched",
    "source_kind": "document",
    "evidence_text": "Full cleaned text of the paper after batch processing.",
    "intake": {
        "stages": {"capture": "complete", "fetch": "complete", "quality": "metadata_only"},
        "quality": {
            "verdict": "metadata_only",
            "reason": "only the abstract and metadata were read",
            "next": "the approved batch fetches the full PDF",
        },
    },
    "processing": {
        "run": "batch-test-001",
        "coverage": "full",
        "stages": {"validate": "complete", "parse": "complete", "read": "complete", "review": "complete"},
    },
    "review": {
        "draft": {
            "bottom_line": "Test note verifying capture banner updates after batch completes.",
            "what_it_solves": "Confirms stale Next advice is replaced.",
        }
    },
})

# 5. Create a parked session with an unanswered ask_user question so we can test auto-continue on reopened thread
ctx_cur = Context(tier="curate", vault=v, extras={})
opened = REGISTRY.call("open_session", {"purpose": "explore", "question": "Reopened question auto-continue check"}, ctx_cur)
q_sid = opened["opened"]
q_ctx = Context(tier="contribute", vault=v, session=q_sid, extras={})
q_out = REGISTRY.call("ask_user", {
    "question": "Should we focus on osquery or duckdb first?",
    "options": ["Focus on osquery", "Focus on duckdb"],
}, q_ctx)
SessionStore(v).append(q_sid, {"type": "status", "status": "parked", "note": "waiting on person"})

# 6. Index the vault so search & browse see all seeded notes immediately
REGISTRY.call("index", {}, ctx_cur)

print(json.dumps({
    "vault": str(VAULT_DIR),
    "budget_config": cfg_path.read_text(encoding="utf-8")[-80:],
    "question_session": q_sid,
    "question_id": q_out.get("question_id"),
    "sessions_count": len(SessionStore(v).list()),
}, indent=2))
