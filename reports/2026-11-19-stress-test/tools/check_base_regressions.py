#!/usr/bin/env python
"""Verify regression status of every finding against baseline da7bf8a snapshot."""
from __future__ import annotations

from pathlib import Path

BASE = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\scratch\librarian-stress-20261119\base")


def rd(rel: str) -> str:
    p = BASE / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


checks = {
    "F01_base_has_show_50_more": "Show 50 more" in rd("ui/src/views.ts"),
    "F02_base_has_checkpoint_reuse": "previous = next(" in rd("src/resource_librarian/agent_runtime.py"),
    "F03_base_has_workflow_grant": "workflow_grant" in rd("src/resource_librarian/broker.py"),
    "F04_base_cancel_turn_releases_waiters": "waiters" in rd("src/resource_librarian/app.py").split("def cancel_turn")[1][:300],
    "F05_base_chat_cards_clears_in_replay": "this.cards.clear" in rd("ui/src/chat.ts"),
    "F06_base_audited_reduce_has_close_session": '"close_session"' in rd("src/resource_librarian/agent_runtime.py").split('"reduce":')[1][:200],
    "F07_base_smoke_line142_guide_auto_open": "guide-seen" in rd("ui/src/main.ts"),
    "F08_base_has_skill_registry": (BASE / "src/resource_librarian/skill_registry.py").exists(),
    "F09_base_read_file_has_rglob": 'rglob("*.md")' in rd("src/resource_librarian/app.py"),
    "F10_base_safe_name_checks_con": "CON" in rd("src/resource_librarian/notes.py").split("def safe_name")[1][:200],
    "F11_base_has_no_progress": "_no_progress_signature" in rd("src/resource_librarian/loop.py"),
    "F12_base_learn_next_hint_has_note": "task_add(note=" in rd("src/resource_librarian/session.py"),
    "F13_base_modes_has_max_height": "max-height" in rd("ui/src/style.css").split(".lib-modes")[1][:150],
    "F14_base_has_pickFile": "pickFile" in rd("ui/src/pane.ts"),
    "F15_base_has_NOT_CHAT_NAME": "NOT_CHAT_NAME" in rd("ui/src/panels.ts"),
    "F16_base_has_guide_seen": "guide-seen" in rd("ui/src/main.ts"),
}
for k, v in checks.items():
    print(f"{k}: {v}")
