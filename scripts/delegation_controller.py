#!/usr/bin/env python
"""Local controller for DELEG-06: run one delegated work package end to end.

Admits the package, creates an isolated git worktree, asks a hosted worker
model for complete replacement files, applies them, guards the scope, runs the
declared checks, feeds failures back for at most max_repair_rounds, and writes
the evidence-bearing completion record.  The hosted model executes nothing.
"""
from __future__ import annotations

import json
import math
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import check_work_package  # noqa: E402
from check_diff_scope import parse_diff, scope_findings, worktree_diff_text  # noqa: E402
from delegate_deepinfra import (  # noqa: E402
    MAX_OUTPUT_TOKENS,
    SECRET_PATTERNS,
    atomic_json,
    atomic_text,
    sha256,
)

# ---------------------------------------------------------------------------
# Public API types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WorkerResult:
    run_id: str
    text: str
    exit_code: int
    error: str


Worker = Callable[[str, list[str], Path, str, int], WorkerResult]


@dataclass(frozen=True)
class CheckRun:
    id: str
    exit_code: int
    log_ref: str
    seconds: float


FILE_BLOCK = re.compile(
    r"^<<<FILE (?P<path>[^\n>]+)>>>\n(?P<body>.*?)\n<<<END FILE>>>$",
    re.M | re.S,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_files(reply: str) -> dict[str, str]:
    """Extract every FILE block from *reply*.

    Returns {path (stripped, forward slashes): body}.  Bodies end with exactly
    one ``"\\n"`` added.  A path given twice raises ``ValueError``.  No blocks
    -> ``{}``.
    """
    result: dict[str, str] = {}
    for m in FILE_BLOCK.finditer(reply):
        path = m.group("path").strip()
        # Workers echo the packet's <file path="..."> style; that is format, not scope.
        if path.startswith("path="):
            path = path[len("path="):]
        path = path.strip("\"'").replace("\\", "/")
        if path in result:
            raise ValueError(f"duplicate FILE block for {path}")
        result[path] = m.group("body") + "\n"
    return result


def venv_command(command: str, venv_python: Path) -> list[str]:
    """Split *command* and replace a leading venv python with *venv_python*."""
    # Normalise backslashes in the leading token so shlex works on Windows.
    normalised = command.replace("\\", "/")
    tokens = shlex.split(normalised, posix=True)
    if not tokens:
        raise ValueError("empty check command")
    first = tokens[0]
    if first in (".venv/Scripts/python.exe", ".venv/Scripts/python", ".venv/bin/python"):
        tokens[0] = str(venv_python)
    else:
        raise ValueError("check does not run with the repository venv")
    return tokens


def _committed_sha256(repository: Path, revision: str, path: str) -> str | None:
    """sha256 of a file's committed bytes at *revision*, or None if absent."""
    result = subprocess.run(
        ["git", "-C", str(repository), "show", f"{revision}:{path}"],
        capture_output=True, check=False,
    )
    if result.returncode != 0:
        return None
    return sha256(result.stdout)


def environment_identity(repository: Path, venv_python: Path, revision: str) -> dict[str, Any]:
    """Return the environment identity dict for admission comparison."""
    py_ver = subprocess.run(
        [str(venv_python), "-c", "import platform; print(platform.python_version())"],
        capture_output=True, text=True, check=False,
    )
    python_version = py_ver.stdout.strip()
    dep_sha = _committed_sha256(repository, revision, "pyproject.toml")
    return {
        "python": python_version,
        "venv": ".venv",
        "dependency_sha256": dep_sha or "",
    }


def run_check(
    check: dict[str, Any],
    worktree: Path,
    venv_python: Path,
    log_path: Path,
    timeout_s: float,
) -> CheckRun:
    """Execute one check, writing combined stdout+stderr to *log_path*."""
    cmd = venv_command(check["command"], venv_python)
    env = os.environ.copy()
    pythonpath = str(worktree / "src")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = pythonpath + (os.pathsep + existing if existing else "")
    env["PYTHONIOENCODING"] = "utf-8"
    # Checks must not leave untracked bytecode or caches for the scope guard to see.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_ADDOPTS"] = (env.get("PYTEST_ADDOPTS", "") + " -p no:cacheprovider").strip()

    started = time.monotonic()
    try:
        with log_path.open("wb") as log_fh:
            proc = subprocess.Popen(
                cmd, cwd=str(worktree), env=env,
                stdout=log_fh, stderr=subprocess.STDOUT,
            )
            proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        with log_path.open("ab") as log_fh:
            log_fh.write(f"TIMEOUT after {timeout_s:.0f} s\n".encode())
        exit_code = 124
    else:
        exit_code = proc.returncode
    elapsed = time.monotonic() - started
    return CheckRun(
        id=check["id"],
        exit_code=exit_code,
        log_ref=str(log_path),
        seconds=elapsed,
    )


def log_tail(path: Path, lines: int = 120) -> str:
    """Last *lines* lines of *path*, with secret patterns redacted."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    tail = text.splitlines()[-lines:]
    out: list[str] = []
    for line in tail:
        if any(p.search(line) for p in SECRET_PATTERNS):
            out.append("[line withheld: possible secret]")
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Worker factory
# ---------------------------------------------------------------------------

def runner_worker(
    *,
    model: str,
    pool: str,
    budget_usd: float,
    agent: str,
    package_path: Path,
    out_dir: Path,
    max_output_tokens: int,
    timeout_s: float,
    venv_python: Path,
    runner_path: Path,
) -> Worker:
    """Return a Worker that calls the runner as a subprocess."""
    package = json.loads(package_path.read_text(encoding="utf-8"))
    package_id = package["admission"]["package_id"]

    def worker(
        instruction_text: str,
        files: list[str],
        worktree: Path,
        parent_run_id: str,
        round_no: int,
    ) -> WorkerResult:
        brief_dir = out_dir / "briefs"
        brief_dir.mkdir(parents=True, exist_ok=True)
        brief_path = brief_dir / f"round-{round_no}.txt"
        atomic_text(brief_path, instruction_text)

        cmd = [
            str(venv_python),
            str(runner_path),
            "--task", f"{package_id}-r{round_no}",
            "--work-package", str(package_path),
            "--pool", pool,
            "--total-budget-usd", str(budget_usd),
            "--agent", agent,
            "--model", model,
            "--role", "drafter" if round_no == 0 else "builder",
            "--instruction-file", str(brief_path),
            "--export-root", str(worktree),
            "--max-output-tokens", str(max_output_tokens),
            "--timeout", str(timeout_s),
        ]
        if parent_run_id:
            cmd += ["--parent-run", parent_run_id]
        for f in files:
            cmd += ["--file", f]

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        proc = subprocess.run(
            cmd, capture_output=True, text=True, env=env, check=False,
        )
        stderr_tail = proc.stderr[-2000:] if proc.stderr else ""

        # Parse the last stdout line as JSON.
        run_id = ""
        output_text = ""
        if proc.stdout:
            last_line = proc.stdout.strip().splitlines()[-1]
            try:
                info = json.loads(last_line)
                run_id = info.get("run_id", "")
                output_path = info.get("output", "")
                if output_path:
                    output_text = Path(output_path).read_text(encoding="utf-8")
            except (json.JSONDecodeError, OSError):
                pass

        if proc.returncode not in (0, 3):
            return WorkerResult(run_id, "", proc.returncode, stderr_tail)
        return WorkerResult(run_id, output_text, proc.returncode, stderr_tail)

    return worker


# ---------------------------------------------------------------------------
# Main package runner
# ---------------------------------------------------------------------------

def run_package(
    package_path: Path,
    brief_path: Path,
    *,
    worker: Worker,
    repository: Path,
    venv_python: Path,
    out_dir: Path,
    clock: Callable[[], float] = time.monotonic,
    max_reply_tokens: int = MAX_OUTPUT_TOKENS,
) -> dict[str, Any]:
    """Run one delegated work package end to end.

    Returns the completed package record (also written to
    ``out_dir/"package.json"``). `max_reply_tokens` is the worker's output
    limit; a write target too large to come back whole within it is refused
    at admission, before any worktree or paid call.
    """
    # Checks run with cwd set to the worktree, so every path must be absolute:
    # a relative one would put the wrong src first on PYTHONPATH.
    repository, venv_python, out_dir = (p.resolve() for p in (repository, venv_python, out_dir))
    package_path, brief_path = package_path.resolve(), brief_path.resolve()

    # 1. Load and validate the package.
    package = json.loads(package_path.read_text(encoding="utf-8"))
    errors = check_work_package.check(package)
    if errors:
        raise SystemExit("package refused:\n  " + "\n  ".join(errors))

    admission = package["admission"]
    if admission["class"] != "implementation":
        raise SystemExit("only implementation packages are supported")
    if admission["owner_host_gate"]:
        raise SystemExit("owner-host packages stay lead-led in the pilot")
    if package.get("completion"):
        raise SystemExit("package already has a completion record")

    base = admission["base_revision"]
    budget = admission["budget"]
    max_rounds = budget["max_repair_rounds"]
    wall_clock_s = float(budget["wall_clock_s"])
    start_time = clock()

    # 2. Verify protected targets at base.
    for target in admission["protected_targets"]:
        actual = _committed_sha256(repository, base, target["path"])
        if actual != target["sha256"]:
            raise SystemExit(
                f"protected target {target['path']} sha256 mismatch at {base}; "
                "fixtures must be committed in base_revision before delegation"
            )

    # 3. Environment identity.
    identity = environment_identity(repository, venv_python, base)
    env_admission = admission["environment"]
    if (identity["python"] != env_admission["python"]
            or identity["dependency_sha256"] != env_admission["dependency_sha256"]):
        return _finish(
            package, out_dir, base, [], [], [],
            proposed_disposition="escalate",
            escalation_reason="environment_mismatch",
            escalation_detail="python or dependency_sha256 differs from admission",
            execution={"controller": "controller", "repair_rounds": 0, "worktree": ""},
        )

    # 3b. Whole-file replies must fit the worker's output limit. In E2' A0
    # hosts.py (74 KB) and app.py (245 KB) could not, and both runs escalated
    # only after the lead had written the package.
    too_large = _oversized_targets(repository, base, admission["write_targets"],
                                   max_reply_tokens)
    if too_large:
        return _finish(
            package, out_dir, base, [], [], [],
            proposed_disposition="escalate",
            escalation_reason="scope_change",
            escalation_detail=(
                "a whole-file reply cannot fit the worker's output limit of "
                f"{max_reply_tokens} tokens: " + "; ".join(too_large)
                + ". Do the change directly or split the module first."),
            execution={"controller": "controller", "repair_rounds": 0, "worktree": ""},
        )

    # 4. Create worktree.
    worktree = out_dir / "worktree"
    subprocess.run(
        ["git", "-C", str(repository), "worktree", "add", "--detach", str(worktree), base],
        check=True, capture_output=True,
    )
    execution: dict[str, Any] = {
        "controller": "controller",
        "repair_rounds": 0,
        "worktree": str(worktree),
    }

    # 5. Before-state checks (oracle + regression, not suite).
    logs_dir = out_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    before_results: list[dict[str, Any]] = []
    for check in admission["checks"]:
        if check["kind"] == "suite":
            continue
        log_path = logs_dir / f"before-{check['id']}.log"
        cr = run_check(check, worktree, venv_python, log_path, wall_clock_s)
        # A before-state "fail" must be a failing or uncollectable test (pytest
        # exit 1 or 2; an import of not-yet-written code fails at collection).
        # Usage errors (4, which the checkout guard raises), no tests (5),
        # internal errors and timeouts mean the check could not run.
        state = {0: "pass", 1: "fail", 2: "fail"}.get(cr.exit_code, "could not run")
        if state != check["expected_before"]:
            return _finish(
                package, out_dir, base, [], [], [],
                proposed_disposition="escalate",
                escalation_reason="ambiguity",
                escalation_detail=(
                    f"check {check['id']} was admitted to {check['expected_before']} before "
                    f"the change but it gave '{state}' (exit {cr.exit_code}); see {log_path}"
                ),
                execution=execution,
            )

    # 6. Rounds.
    run_ids: list[str] = []
    check_results: list[dict[str, Any]] = []
    brief_text = brief_path.read_text(encoding="utf-8")

    write_targets = admission["write_targets"]
    read_targets = admission["read_targets"]
    all_targets = sorted(set(read_targets + write_targets))

    failure = ""  # why the previous round failed; fed back as the REPAIR section
    unresolved_runs: list[str] = []
    for round_no in range(max_rounds + 1):
        if round_no > 0:
            execution["repair_rounds"] = round_no
        # a. Wall-clock budget.
        if clock() - start_time > wall_clock_s:
            return _finish(
                package, out_dir, base, run_ids, check_results, [],
                proposed_disposition="escalate",
                escalation_reason="budget_exhausted",
                escalation_detail="wall clock exhausted before round",
                execution=execution,
            )

        # b. Build instruction.
        instruction = brief_text + "\n\n"
        instruction += (
            "FORMAT: return each changed file in full inside "
            "<<<FILE path>>> ... <<<END FILE>>> blocks (path relative to the "
            "repository root, one block per file, no diffs, no other files); "
            "only these paths may be written: "
            + ", ".join(write_targets)
            + "; do not edit tests or fixtures you were not given as write targets.\n"
            + "Example, exactly this shape (the bare path, no quotes or path=):\n"
            + f"<<<FILE {write_targets[0]}>>>\n...the whole file...\n<<<END FILE>>>\n"
        )
        if round_no > 0:
            instruction += "\nREPAIR: the previous attempt failed. " + failure + "\n"

        # Files that exist in the worktree.
        existing = [
            f for f in all_targets
            if (worktree / f).is_file()
        ]

        parent_run = run_ids[-1] if run_ids else ""

        # c. Call worker.
        result = worker(instruction, existing, worktree, parent_run, round_no)
        if result.run_id:
            run_ids.append(result.run_id)

        if result.exit_code not in (0, 3):
            if result.run_id:
                unresolved_runs.append(result.run_id)
            reason, detail = _worker_failure_reason(result)
            return _finish(
                package, out_dir, base, run_ids, check_results, [],
                proposed_disposition="escalate",
                escalation_reason=reason,
                escalation_detail=detail,
                execution=execution, worktree=worktree, unresolved_runs=unresolved_runs,
            )

        # d. Parse files. A truncated or unusable reply costs a round.
        try:
            files = parse_files(result.text) if result.exit_code == 0 else {}
        except ValueError as exc:
            files, failure = {}, f"The reply could not be used: {exc}."
        else:
            if result.exit_code == 3:
                failure = ("The reply was truncated at the output limit. Return only the "
                           "changed files, complete, and nothing else.")
            elif not files:
                failure = "The reply contained no <<<FILE path>>> blocks."
        if not files:
            if round_no == max_rounds:
                return _exhausted(package, out_dir, base, run_ids, check_results,
                                  execution, worktree, unresolved_runs, failure)
            continue

        # Scope: every path must match write_targets.
        out_of_scope = [
            p for p in files
            if not check_work_package.matches(p, write_targets)
        ]
        if out_of_scope:
            return _finish(
                package, out_dir, base, run_ids, check_results,
                [f"out_of_scope {p} not in write_targets" for p in out_of_scope],
                proposed_disposition="reject",
                execution=execution, worktree=worktree,
            )

        # Write files.
        for path, body in files.items():
            dest = worktree / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(body, encoding="utf-8", newline="\n")

        # e. Diff-scope guard.
        diff_text = worktree_diff_text(base, worktree)
        changes = parse_diff(diff_text)
        findings = scope_findings(package, changes)
        if findings:
            finding_lines = [f"{f.kind} {f.path} {f.detail}" for f in findings]
            return _finish(
                package, out_dir, base, run_ids, check_results, finding_lines,
                proposed_disposition="reject",
                execution=execution, worktree=worktree,
            )

        # f. Run all checks.
        round_passed = True
        for check in admission["checks"]:
            remaining = wall_clock_s - (clock() - start_time)
            timeout = max(1.0, remaining)
            log_path = logs_dir / f"r{round_no}-{check['id']}.log"
            cr = run_check(check, worktree, venv_python, log_path, timeout)
            check_results.append({
                "id": cr.id,
                "exit_code": cr.exit_code,
                "log_ref": str(log_path),
                "ran_by": "controller",
            })
            if cr.exit_code != 0:
                round_passed = False
                failure = (f"Check {check['id']} ({check['command']}) failed with exit "
                           f"{cr.exit_code}. Its output ends:\n{log_tail(log_path)}")
                break

        if round_passed:
            return _success(package, out_dir, base, worktree, run_ids, check_results, execution)

        # g. Failed round.
        if round_no == max_rounds:
            return _exhausted(package, out_dir, base, run_ids, check_results,
                              execution, worktree, unresolved_runs, failure)
    raise AssertionError("unreachable: the last round always returns")


def _exhausted(package: dict[str, Any], out_dir: Path, base: str, run_ids: list[str],
               check_results: list[dict[str, Any]], execution: dict[str, Any],
               worktree: Path, unresolved_runs: list[str], failure: str) -> dict[str, Any]:
    rounds = package["admission"]["budget"]["max_repair_rounds"] + 1
    return _finish(
        package, out_dir, base, run_ids, check_results, [],
        proposed_disposition="escalate",
        escalation_reason="repeated_failure",
        escalation_detail=f"all {rounds} rounds failed; last: {failure[:300]}",
        execution=execution, worktree=worktree, unresolved_runs=unresolved_runs,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _oversized_targets(repository: Path, base: str, write_targets: list[str],
                       max_reply_tokens: int) -> list[str]:
    """Write targets whose whole text, estimated as the runner does, exceeds the limit."""
    found = []
    for path in write_targets:
        if path.endswith("/"):
            continue  # a directory target: new files are written whole and are small
        result = subprocess.run(["git", "-C", str(repository), "show", f"{base}:{path}"],
                                capture_output=True, check=False)
        if result.returncode != 0:
            continue  # the worker creates this file
        estimate = math.ceil(len(result.stdout) / 3.5)
        if estimate > max_reply_tokens:
            found.append(f"{path} is about {estimate} tokens")
    return found


def _worker_failure_reason(result: WorkerResult) -> tuple[str, str]:
    """Map a non-0/3 worker exit to an escalation reason."""
    err = result.error.lower()
    if "budget" in err or "limit" in err:
        return "budget_exhausted", result.error
    if "reconcile" in err or "uncertain" in err:
        return "uncertain_call", result.error
    return "repeated_failure", result.error


def _predicate_states(
    admission: dict[str, Any],
    check_results: list[dict[str, Any]],
    failing_check_id: str | None,
) -> dict[str, str]:
    """Compute predicate states from check results."""
    checks = {c["id"]: c for c in admission["checks"]}
    predicates: dict[str, str] = {}
    for pred in admission["acceptance_predicates"]:
        pid = pred["id"]
        predicates[pid] = "not_checked"
    for cr in check_results:
        if cr["id"] not in checks:
            continue
        covers = checks[cr["id"]]["covers"]
        if cr["exit_code"] == 0:
            for c in covers:
                predicates[c] = "met"
        elif cr["id"] == failing_check_id:
            for c in covers:
                predicates[c] = "unmet"
    return predicates


def _success(
    package: dict[str, Any],
    out_dir: Path,
    base: str,
    worktree: Path,
    run_ids: list[str],
    check_results: list[dict[str, Any]],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Commit the worktree and build an accept completion."""
    admission = package["admission"]
    package_id = admission["package_id"]

    # Commit.
    subprocess.run(["git", "-C", str(worktree), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(worktree),
         "-c", "user.name=delegation-controller",
         "-c", "user.email=controller@localhost",
         "commit", "-q", "-m",
         f"{package_id}: candidate from the delegation controller"],
        check=True,
    )
    full_sha = subprocess.run(
        ["git", "-C", str(worktree), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    # Changed files.
    changed_raw = subprocess.run(
        ["git", "-C", str(worktree), "diff", "--name-only", base, "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    changed_files = []
    for path in changed_raw:
        path = path.strip()
        if not path:
            continue
        changed_files.append({
            "path": path,
            "sha256": _committed_sha256(worktree, "HEAD", path) or "",
        })

    # Protected targets intact?
    intact = True
    for target in admission["protected_targets"]:
        rc = subprocess.run(
            ["git", "-C", str(worktree), "diff", "--quiet", base, "HEAD", "--", target["path"]],
            check=False,
        )
        if rc.returncode != 0:
            intact = False
            break

    predicates = _predicate_states(admission, check_results, None)

    completion: dict[str, Any] = {
        "artifact": {"kind": "commit", "ref": full_sha},
        "base_revision": base,
        "changed_files": changed_files,
        "protected_targets_intact": intact,
        "check_results": check_results,
        "predicates": predicates,
        "run_ids": run_ids,
        "cost_usd": 0.0,
        "repair_rounds": execution["repair_rounds"],
        "unresolved_findings": [],
        "declared_gaps": [
            "cost_usd is 0.0; the lead fills it from the ledger",
        ],
        "proposed_disposition": "accept",
        "recorded_by": "delegation-controller",
    }
    return _write_and_return(package, out_dir, completion, execution)


def _finish(
    package: dict[str, Any],
    out_dir: Path,
    base: str,
    run_ids: list[str],
    check_results: list[dict[str, Any]],
    unresolved_findings: list[str],
    *,
    proposed_disposition: str,
    escalation_reason: str = "",
    escalation_detail: str = "",
    execution: dict[str, Any],
    worktree: Path | None = None,
    unresolved_runs: list[str] | None = None,
) -> dict[str, Any]:
    """Build a reject/escalate completion and write it."""
    admission = package["admission"]
    failing_id = check_results[-1]["id"] if check_results else None
    predicates = _predicate_states(admission, check_results, failing_id)

    completion: dict[str, Any] = {
        "artifact": {"kind": "patch", "ref": ""},
        "base_revision": base,
        "changed_files": [],
        "protected_targets_intact": _protected_intact(admission, worktree, base),
        "check_results": check_results,
        "predicates": predicates,
        "run_ids": run_ids,
        "cost_usd": 0.0,
        "repair_rounds": execution["repair_rounds"],
        "unresolved_findings": unresolved_findings,
        "declared_gaps": [
            "cost_usd is 0.0; the lead fills it from the ledger",
        ],
        "proposed_disposition": proposed_disposition,
        "recorded_by": "delegation-controller",
    }
    if proposed_disposition == "escalate":
        package["escalation"] = {"reason": escalation_reason, "detail": escalation_detail}
        package["resume"] = {
            "last_good_artifact": base,
            # Only calls that ended without a usable answer may need reconciling.
            "open_run_ids": list(unresolved_runs or []),
            "next_action": (
                f"Escalated ({escalation_reason}): read the logs in {out_dir}, reconcile any "
                "open runs, then retry with a revised brief, re-scope, or do it directly."
            ),
        }
    return _write_and_return(package, out_dir, completion, execution)


def _protected_intact(admission: dict[str, Any], worktree: Path | None, base: str) -> bool:
    """True when no protected target differs from base in the worktree (or none exists)."""
    if worktree is None or not worktree.exists():
        return True
    for target in admission["protected_targets"]:
        rc = subprocess.run(["git", "-C", str(worktree), "diff", "--quiet", base, "--",
                             target["path"]], check=False, capture_output=True)
        if rc.returncode != 0:
            return False
    return True


def _write_and_return(
    package: dict[str, Any],
    out_dir: Path,
    completion: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    """Validate, write and return the finished package record."""
    package["execution"] = execution
    package["completion"] = completion

    # Validate.
    gaps = list(completion.get("declared_gaps", []))
    for err in check_work_package.schema_errors(package):
        gaps.append(f"record check: schema: {err}")
    for err in check_work_package.rule_errors(package):
        gaps.append(f"record check: rule: {err}")
    completion["declared_gaps"] = gaps

    out_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(out_dir / "package.json", package)
    return package


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="work package JSON")
    parser.add_argument("brief", type=Path, help="brief text file")
    parser.add_argument("--model", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--total-budget-usd", type=float, required=True)
    parser.add_argument("--agent", default="controller")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--max-output-tokens", type=int, default=12000)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args(argv)
    # Refuse here, not after the lead has prepared a run: the runner would
    # refuse every call and the controller would report "repeated_failure".
    if not 1 <= args.max_output_tokens <= MAX_OUTPUT_TOKENS:
        raise SystemExit(f"--max-output-tokens must be between 1 and {MAX_OUTPUT_TOKENS}")

    repository = _SCRIPTS.parent
    if (repository / ".venv" / "Scripts" / "python.exe").exists():
        venv_python = repository / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = repository / ".venv" / "bin" / "python"

    package = json.loads(args.package.read_text(encoding="utf-8"))
    package_id = package["admission"]["package_id"]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_dir = args.out_dir or (repository / "tmp" / "delegation-runs" / f"{package_id}-{ts}")

    worker = runner_worker(
        model=args.model,
        pool=args.pool,
        budget_usd=args.total_budget_usd,
        agent=args.agent,
        package_path=args.package,
        out_dir=out_dir,
        max_output_tokens=args.max_output_tokens,
        timeout_s=args.timeout,
        venv_python=venv_python,
        runner_path=_SCRIPTS / "delegate_deepinfra.py",
    )

    record = run_package(
        args.package,
        args.brief,
        worker=worker,
        repository=repository,
        venv_python=venv_python,
        out_dir=out_dir,
        max_reply_tokens=args.max_output_tokens,
    )

    completion = record["completion"]
    disposition = completion["proposed_disposition"]
    rounds = completion["repair_rounds"]
    run_ids = completion.get("run_ids", [])
    escalation = completion.get("escalation", {})

    print(f"disposition: {disposition}")
    print(f"rounds: {rounds}")
    print(f"run ids: {', '.join(run_ids) if run_ids else '(none)'}")
    if escalation:
        print(f"escalation: {escalation.get('reason', '')}")
    print(f"out dir: {out_dir}")

    if disposition == "accept":
        return 0
    elif disposition == "escalate":
        return 2
    else:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
