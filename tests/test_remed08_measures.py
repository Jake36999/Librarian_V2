"""REMED-08 evidence aggregation across provider-interrupted run folders."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("remed08_measures", SCRIPTS / "remed08_measures.py")
measures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(measures)


def _results(path: Path, rows: list[dict]) -> Path:
    path.mkdir()
    (path / "results.json").write_text(json.dumps({"rows": rows}), encoding="utf-8")
    return path


def test_split_runs_count_only_real_sessions_and_reject_duplicates(tmp_path):
    first = _results(tmp_path / "first", [
        {"task": "t1", "session": "s1", "grains": {"grains": 2, "tier_a": 1},
         "spend": {"calls": 3}, "refusals": {"CONTRACT_SCOPE": 2}},
        {"task": "t2", "stopped": "budget_exhausted"},
    ])
    second = _results(tmp_path / "second", [
        {"task": "t2", "session": "s2", "grains": {"grains": 3, "tier_a": 2},
         "spend": {"calls": 4}, "refusals": {}},
    ])

    result = measures.measures([first, second])

    assert result["sessions"] == 2
    assert result["grains"] == 5 and result["tier_a"] == 3
    assert result["model_calls"] == 7 and result["refused_total"] == 2

    duplicate = _results(tmp_path / "duplicate", [
        {"task": "t2", "session": "again", "grains": {"grains": 1, "tier_a": 0}},
    ])
    try:
        measures.measures([second, duplicate])
    except ValueError as exc:
        assert "duplicate measured task" in str(exc)
    else:
        raise AssertionError("duplicate task was accepted")
