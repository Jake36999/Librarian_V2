"""DELEG-11: the work-package contract, its schema and its cross-item rules."""
from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_work_package", REPOSITORY / "scripts" / "check_work_package.py")
assert SPEC is not None and SPEC.loader is not None
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

EXAMPLE = REPOSITORY / "docs" / "examples" / "work-package-ADAPT-05.json"
CONTRACT = REPOSITORY / "docs" / "delegation-work-package.md"
PLAN = REPOSITORY / "docs" / "unified-implementation-plan.md"


@pytest.fixture
def package():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def test_adapt05_example_is_a_valid_accepted_package(package):
    assert checker.check(package) == []


def test_adapt05_protected_fixtures_hold_their_hashes_in_the_landed_commit(package):
    if checker.committed_sha256(package["completion"]["artifact"]["ref"], "pyproject.toml") is None:
        pytest.skip("the ADAPT-05 commit is not in this checkout's history")
    assert checker.hash_errors(package) == []
    package["admission"]["protected_targets"][0]["sha256"] = "0" * 64
    assert checker.hash_errors(package)


def test_every_plan_packet_field_maps_to_a_contract_field():
    plan = PLAN.read_text(encoding="utf-8")
    section = plan[plan.index("### 3.3 Work-packet contract"):]
    block = re.search(r"~~~text\n(.*?)~~~", section, re.S).group(1)
    fields = [line.strip() for line in block.splitlines() if line.strip()]
    mapped = {m.group(1).strip() for m in re.finditer(
        r"^\| ([^|`]+?) \| `", CONTRACT.read_text(encoding="utf-8"), re.M)}
    assert len(fields) == 9
    assert [f for f in fields if f not in mapped] == []


def test_implementation_needs_protected_fixtures_and_an_oracle(package):
    package["admission"]["protected_targets"] = []
    assert any("protected_targets" in e for e in checker.check(package))


def test_a_generic_suite_is_not_admission_evidence(package):
    for check in package["admission"]["checks"]:
        if check["kind"] == "oracle":
            check["kind"] = "suite"
    assert any(e.startswith("schema: admission/checks") for e in checker.check(package))


def test_the_oracle_must_cover_a_behaviour_predicate(package):
    for check in package["admission"]["checks"]:
        if check["kind"] == "oracle":
            check["covers"] = ["P2-runs"]
    assert any("behaviour predicate" in e for e in checker.check(package))


def test_exploratory_work_may_be_admitted_without_an_oracle(package):
    admission = package["admission"]
    admission["class"] = "exploratory"
    admission["protected_targets"] = []
    admission["checks"] = [{"id": "suite", "command": "pytest -q", "kind": "suite",
                            "expected_before": "pass", "covers": ["P3-integrates"]}]
    admission["acceptance_predicates"] = [
        p for p in admission["acceptance_predicates"] if p["id"] == "P3-integrates"]
    del package["completion"]
    assert checker.check(package) == []


def test_repair_rounds_are_capped_at_two(package):
    package["admission"]["budget"]["max_repair_rounds"] = 3
    assert checker.check(package)


def test_unknown_or_duplicate_ids_are_refused(package):
    broken = copy.deepcopy(package)
    broken["admission"]["checks"][0]["covers"].append("P9-missing")
    assert any("unknown predicate" in e for e in checker.check(broken))
    broken = copy.deepcopy(package)
    broken["admission"]["checks"].append(copy.deepcopy(broken["admission"]["checks"][0]))
    assert any("duplicate check id" in e for e in checker.check(broken))


def test_a_protected_fixture_cannot_also_be_writable(package):
    protected = package["admission"]["protected_targets"][0]["path"]
    package["admission"]["write_targets"].append(protected)
    assert any("also a write target" in e for e in checker.check(package))


def test_a_worker_claim_never_satisfies_behaviour(package):
    for result in package["completion"]["check_results"]:
        result["ran_by"] = "worker_claim"
    assert any("without a passing check" in e for e in checker.check(package))


def test_acceptance_needs_intact_fixtures_and_matching_base(package):
    broken = copy.deepcopy(package)
    broken["completion"]["protected_targets_intact"] = False
    assert any("protected target changed" in e for e in checker.check(broken))
    broken = copy.deepcopy(package)
    broken["completion"]["base_revision"] = "0" * 40
    assert any("base_revision differs" in e for e in checker.check(broken))
    broken = copy.deepcopy(package)
    broken["completion"]["predicates"]["P1-behaviour"] = "not_checked"
    assert any("P1-behaviour is not_checked" in e for e in checker.check(broken))


def test_escalation_reasons_are_closed(package):
    package["escalation"] = {"reason": "felt_like_it", "detail": "x"}
    assert checker.check(package)
    package["escalation"] = {"reason": "uncertain_call", "detail": "run left uncertain"}
    assert checker.check(package) == []


def test_command_line_reports_ok(capsys):
    assert checker.main([str(EXAMPLE)]) == 0
    assert capsys.readouterr().out.strip() == "ok"
