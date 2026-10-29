"""DELEG-06 pilot oracle: check_work_package.py --json reports errors and conformance."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path


REPOSITORY = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_work_package", REPOSITORY / "scripts" / "check_work_package.py")
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

EXAMPLE = REPOSITORY / "docs" / "examples" / "work-package-ADAPT-05.json"


def test_json_reports_a_valid_package_with_its_conformance(capsys):
    package = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert checker.main([str(EXAMPLE), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"ok": True, "errors": [], "conformance": checker.conformance(package)}


def test_json_reports_rule_errors(tmp_path, capsys):
    package = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    broken = copy.deepcopy(package)
    broken["admission"]["roles"]["reviewer_model"] = broken["admission"]["roles"]["drafter_model"]
    path = tmp_path / "broken.json"
    path.write_text(json.dumps(broken), encoding="utf-8")
    assert checker.main([str(path), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert any("same model family" in e for e in report["errors"])
    assert report["conformance"] == checker.conformance(broken)


def test_json_has_no_conformance_for_a_malformed_package(tmp_path, capsys):
    path = tmp_path / "malformed.json"
    path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")
    assert checker.main([str(path), "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False and report["errors"]
    assert report["conformance"] is None


def test_plain_output_is_unchanged(capsys):
    assert checker.main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().out.strip() == "ok"
