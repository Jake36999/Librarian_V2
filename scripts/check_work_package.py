#!/usr/bin/env python
"""Check a delegation work package (DELEG-11) against its schema and rules.

The JSON Schema covers shapes and enums. The rules here cross array items and
the repository, which a schema cannot express: an oracle must cover a
behaviour predicate, completion evidence must come from someone other than the
worker, and protected fixtures must still have their admitted hashes.
Usage: check_work_package.py PACKAGE.json [--verify-hashes]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import jsonschema


REPOSITORY = Path(__file__).resolve().parents[1]
SCHEMA = REPOSITORY / "docs" / "schemas" / "delegation-work-package.schema.json"
# Plan §3.2: changes to these are accepted only after the owner's Windows full suite.
OWNER_HOST_FILES = tuple(f"src/resource_librarian/{name}.py" for name in
                         ("host", "coordination", "connection", "cli", "mcp_server"))
VENV_PYTHON = (".venv/Scripts/python", ".venv\\Scripts\\python", ".venv/bin/python")


def matches(path: str, targets: list[str]) -> bool:
    """A target ending in "/" covers its directory; any other target is one file."""
    path = path.replace("\\", "/")
    return any(path.startswith(t) if t.endswith("/") else path == t
               for t in (t.replace("\\", "/") for t in targets))


def model_family(model: str) -> str:
    """The organisation part of a model ID: zai-org/GLM-5.3 and GLM-5.3-Flash share one."""
    return model.split("/", 1)[0].strip().casefold()


def schema_errors(package: Any) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"schema: {'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
            for e in validator.iter_errors(package)]


def _duplicates(ids: list[str]) -> set[str]:
    return {i for i in ids if ids.count(i) > 1}


def rule_errors(package: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    admission = package["admission"]
    checks = {c["id"]: c for c in admission["checks"]}
    predicates = {p["id"]: p for p in admission["acceptance_predicates"]}

    for name, ids in (("check", [c["id"] for c in admission["checks"]]),
                      ("predicate", [p["id"] for p in admission["acceptance_predicates"]])):
        for duplicate in sorted(_duplicates(ids)):
            errors.append(f"duplicate {name} id: {duplicate}")
    for check in admission["checks"]:
        for covered in check["covers"]:
            if covered not in predicates:
                errors.append(f"check {check['id']} covers unknown predicate {covered}")

    if admission["class"] == "implementation":
        behaviour = {i for i, p in predicates.items() if p["kind"] == "behaviour"}
        if not any(c["kind"] == "oracle" and behaviour & set(c["covers"])
                   for c in admission["checks"]):
            errors.append("an implementation package needs an oracle check that covers "
                          "a behaviour predicate; a generic suite is not admission evidence")

    for target in admission["protected_targets"]:
        if matches(target["path"], admission["write_targets"]):
            errors.append(f"protected target is also a write target: {target['path']}")

    roles = admission["roles"]
    if model_family(roles["drafter_model"]) == model_family(roles["reviewer_model"]):
        errors.append("drafter and reviewer come from the same model family; "
                      "the reviewer must be independent (plan §3.2)")
    for check in admission["checks"]:
        if not any(venv in check["command"] for venv in VENV_PYTHON):
            errors.append(f"check {check['id']} does not run with the repository venv")
    gated = [f for f in OWNER_HOST_FILES if matches(f, admission["write_targets"])]
    if gated and not admission["owner_host_gate"]:
        errors.append(f"owner_host_gate must be true when {gated[0]} is writable (plan §3.2)")
    if admission["class"] == "implementation":
        if not admission["write_targets"]:
            errors.append("an implementation package names no write targets")
        if not admission["documentation_consequence"].strip():
            errors.append("documentation_consequence is empty; say 'none' explicitly")

    execution = package.get("execution")
    if execution and execution["repair_rounds"] > admission["budget"]["max_repair_rounds"]:
        errors.append("execution used more repair rounds than admission allows")

    completion = package.get("completion")
    if completion:
        errors += _completion_errors(admission, checks, predicates, completion)
    return errors


def _completion_errors(admission: dict[str, Any], checks: dict[str, Any],
                       predicates: dict[str, Any], completion: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if completion["base_revision"] != admission["base_revision"]:
        errors.append("completion base_revision differs from admission")
    if completion["repair_rounds"] > admission["budget"]["max_repair_rounds"]:
        errors.append("completion used more repair rounds than admission allows")
    if completion["proposed_disposition"] != "accept":
        return errors

    if not completion["protected_targets_intact"]:
        errors.append("cannot accept: a protected target changed")
    passed_by_non_worker = {
        r["id"] for r in completion["check_results"]
        if r["exit_code"] == 0 and r["ran_by"] != "worker_claim"
    }
    for result in completion["check_results"]:
        if result["id"] not in checks:
            errors.append(f"result for an undeclared check: {result['id']}")
    for predicate_id, predicate in predicates.items():
        state = completion["predicates"].get(predicate_id, "not_checked")
        if state != "met":
            errors.append(f"cannot accept: predicate {predicate_id} is {state}")
            continue
        if predicate["kind"] == "behaviour" and not any(
                predicate_id in checks[c]["covers"] for c in passed_by_non_worker if c in checks):
            errors.append(f"predicate {predicate_id} is marked met without a passing "
                          "check run by the controller or lead")
    return errors


def conformance(package: dict[str, Any]) -> dict[str, Any]:
    """Which plan §3.3 packet fields the admission fills (metric M9)."""
    a = package["admission"]
    covered = {c for check in a["checks"] for c in check["covers"]}
    fields = {
        "task_and_objective": bool(a["task_id"].strip() and a["objective"].strip()),
        "allowed_and_forbidden_files": bool(a["write_targets"] or a["read_targets"]),
        "behaviour_to_preserve": bool(a["preserve"] or a["protected_targets"]),
        "venv_test_command": any(v in c["command"] for c in a["checks"] for v in VENV_PYTHON),
        "expected_failure_before": any(c["expected_before"] == "fail" for c in a["checks"]),
        "acceptance_tests": bool(a["acceptance_predicates"]) and all(
            p["id"] in covered for p in a["acceptance_predicates"]),
        "documentation_consequence": bool(a["documentation_consequence"].strip()),
        "models_and_merge_owner": model_family(a["roles"]["drafter_model"])
            != model_family(a["roles"]["reviewer_model"]),
        "budget": a["budget"]["task_usd"] > 0,
    }
    return {"fields": fields, "present": sum(fields.values()), "total": len(fields)}


def committed_sha256(revision: str, path: str) -> str | None:
    """sha256 of a file's committed bytes at a revision, or None if absent."""
    result = subprocess.run(["git", "-C", str(REPOSITORY), "show", f"{revision}:{path}"],
                            capture_output=True, check=False)
    return hashlib.sha256(result.stdout).hexdigest() if result.returncode == 0 else None


def hash_errors(package: dict[str, Any]) -> list[str]:
    """Protected targets must hold their admitted hashes in the completed artifact."""
    completion = package.get("completion")
    if not completion or completion["artifact"]["kind"] != "commit":
        return ["--verify-hashes needs a completion whose artifact is a commit"]
    revision = completion["artifact"]["ref"]
    errors = []
    for target in package["admission"]["protected_targets"]:
        actual = committed_sha256(revision, target["path"])
        if actual != target["sha256"]:
            errors.append(f"protected target changed or missing at {revision[:12]}: "
                          f"{target['path']}")
    return errors


def check(package: Any, *, verify_hashes: bool = False) -> list[str]:
    errors = schema_errors(package)
    if errors:
        return errors  # the rules assume a well-formed package
    errors = rule_errors(package)
    if verify_hashes:
        errors += hash_errors(package)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("package", type=Path)
    parser.add_argument("--verify-hashes", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        package = json.loads(args.package.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read work package: {exc}") from exc
    errors = check(package, verify_hashes=args.verify_hashes)
    if args.json:
        schema_ok = not schema_errors(package)
        report = {
            "ok": len(errors) == 0,
            "errors": errors,
            "conformance": conformance(package) if schema_ok else None,
        }
        json.dump(report, sys.stdout)
        sys.stdout.write("\n")
    else:
        for error in errors:
            print(error)
        if not errors:
            print("ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
