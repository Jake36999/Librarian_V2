"""E2': lead effort is read from session logs, each API response counted once."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "e2_effort.py"
SPEC = importlib.util.spec_from_file_location("e2_effort", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
meter = importlib.util.module_from_spec(SPEC)
sys.modules["e2_effort"] = meter
SPEC.loader.exec_module(meter)


def assistant(message_id, minute, usage, model="claude-opus-5-5"):
    return {"type": "assistant", "timestamp": f"2026-10-29T10:{minute:02d}:00Z",
            "message": {"id": message_id, "model": model, "usage": usage}}


def user(minute):
    return {"type": "user", "timestamp": f"2026-10-29T10:{minute:02d}:00Z"}


def write_log(path: Path, records) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n{truncated", encoding="utf-8")


USAGE = {"input_tokens": 10, "cache_creation_input_tokens": 1000,
         "cache_read_input_tokens": 5000, "output_tokens": 200}


@pytest.fixture
def projects(tmp_path):
    root = tmp_path / "projects"
    # One response logged over two lines must count once.
    write_log(root / "D--repo" / "s1.jsonl", [
        user(0), assistant("m1", 1, USAGE), assistant("m1", 1, USAGE),
        user(3), assistant("m2", 4, USAGE),
        user(30), assistant("m3", 31, USAGE),  # after a 26-minute pause
        assistant("syn", 31, {"input_tokens": 0, "output_tokens": 0}, model="<synthetic>"),
    ])
    write_log(root / "D--repo" / "s1" / "subagents" / "a.jsonl", [
        user(5), assistant("m4", 6, USAGE, model="claude-haiku-5-5")])
    write_log(root / "D--repo-wt" / "s2.jsonl", [user(0), assistant("m5", 2, USAGE)])
    return root


def test_requests_are_counted_once_and_subagents_included(projects):
    result = meter.measure(meter.session_files("s1", projects))
    assert result["requests"] == 4
    assert result["tokens"] == {"input_tokens": 40, "cache_creation_input_tokens": 4000,
                                "cache_read_input_tokens": 20000, "output_tokens": 800}
    weighted = 40 + 4000 * 1.60 + 20000 * 0.04 + 800 * 3.94
    assert result["weighted_index"] == round(weighted)
    assert result["models"] == ["claude-haiku-5-5", "claude-opus-5-5"]


def test_active_time_excludes_long_pauses(projects):
    result = meter.measure(meter.session_files("s1", projects), gap_minutes=5)
    # Gaps of 1, 2, 1, 1, 1 (subagent at 5-6), 24 (excluded) and 1 minute.
    assert result["active_minutes"] == 7.0
    assert result["wall_minutes"] == 31.0


def test_an_arm_may_span_sessions_in_different_project_folders(projects, capsys):
    assert meter.main(["--session", "s1", "--session", "s2", "--projects", str(projects),
                       "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["requests"] == 5 and result["files"] == 3


def test_delegate_spend_is_joined_by_task_id(projects, tmp_path, capsys):
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"schema": 2, "pools": {}, "calls": [
        {"run_id": "a", "task_id": "E2-T01-C", "charged_usd": 0.02, "status": "completed"},
        {"run_id": "b", "task_id": "E2-T01-C", "charged_usd": 0.01, "status": "uncertain"},
        {"run_id": "c", "task_id": "E2-T02-C", "charged_usd": 0.5, "status": "completed"}]}),
        encoding="utf-8")
    meter.main(["--session", "s2", "--projects", str(projects), "--ledger", str(ledger),
                "--task-id", "E2-T01-C", "--json"])
    delegate = json.loads(capsys.readouterr().out)["delegate"]
    assert delegate == {"calls": 2, "usd": 0.03, "open_runs": ["b"]}


def test_an_unknown_session_is_refused(projects):
    with pytest.raises(SystemExit, match="no logs found"):
        meter.session_files("nope", projects)
