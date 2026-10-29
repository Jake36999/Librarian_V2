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

    writable = set(admission["write_targets"])
    for target in admission["protected_targets"]:
        if target["path"] in writable:
            errors.append(f"protected target is also a write target: {target['path']}")

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
    args = parser.parse_args(argv)
    try:
        package = json.loads(args.package.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"cannot read work package: {exc}") from exc
    errors = check(package, verify_hashes=args.verify_hashes)
    for error in errors:
        print(error)
    if not errors:
        print("ok")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
