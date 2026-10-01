"""Running a claim's failing input (Co-work Roadmap G3; owner's decisions, 2026-10-01).

A review that challenges a claim about what a catalogued repository's code does may give a
*failing input*: one call to one function, and what that call does instead. A person can run
it; running it settles what a judge could only argue about.

The owner's four decisions, enforced here:

- **Functions, as data.** A failing input is `call` (`package.module:function`, or
  `module:Class.method`), JSON `args` and `kwargs`, and `expect`: `raises` with an exception's
  class name, or `returns` with a JSON value. Code builds the runner (`RUNNER`, fixed text);
  no code a model wrote is ever run, and no command is built from model output
  (`NO_ARBITRARY_SHELL`).
- **A person's action.** `run_claim_input` is a `curate` tool: never offered to the model,
  never run by a sweep or a batch.
- **No network.** The container has none, so only the standard library and the repository's
  own code import; a missing dependency is "could not run", never a verdict.
- **Docker only.** Without a running Docker there is no run (`EXECUTION_SANDBOX_ONLY`); there
  is no fallback to this machine.

The container: the repository's shallow clone mounted read-only, the runner's folder read-only,
a 64 MB `/tmp`, no network, no capabilities, an unprivileged user, memory, CPU and process
limits, no environment from this machine (so no keys), removed when it stops; a run that
outlives its timeout is killed. The clone is the default branch at depth 1; its tree is
compared with the tree the library surveyed, and the result says which version ran.

Every outcome is kept: the run's record in `.librarian/claims/runnable.jsonl` and an
`execution` evidence record (what ran, at which commit, in which image, and what happened).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .rules import Refusal
from .vault import Vault, jsonl_lines, now_iso

IMAGE = "python:3.11-slim"
TIMEOUT = 60
MEMORY = "1g"
CPUS = "1"
MAX_INPUT_CHARS = 4000
MARK = "\x1eLIBRARIAN-RESULT "
CALL = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*:[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$")
EXCEPTION = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)*$")
IDENT = re.compile(r"^[A-Za-z_]\w*$")

# The whole runner. It reads its job from /job/spec.json, imports one module from the
# repository, calls one function with JSON arguments, and prints one marked JSON line.
RUNNER = '''import importlib, json, sys, traceback
spec = json.load(open("/job/spec.json", encoding="utf-8"))
for path in reversed(spec["paths"]):
    sys.path.insert(0, path)
MARK = "\\x1eLIBRARIAN-RESULT "
module_name, _, attribute = spec["call"].partition(":")
out = {}
try:
    target = importlib.import_module(module_name)
except BaseException as exc:
    out = {"stage": "import", "error": type(exc).__name__, "message": str(exc)[:500]}
else:
    try:
        for part in attribute.split("."):
            target = getattr(target, part)
    except AttributeError as exc:
        out = {"stage": "lookup", "error": "AttributeError", "message": str(exc)[:500]}
    else:
        try:
            value = target(*spec["args"], **spec["kwargs"])
        except BaseException as exc:
            kind = type(exc)
            out = {"stage": "call", "raised": kind.__name__,
                   "qualified": kind.__module__ + "." + kind.__qualname__,
                   "message": str(exc)[:500], "trace": traceback.format_exc()[-1500:]}
        else:
            try:
                out = {"stage": "call", "returned": json.loads(json.dumps(value)), "json": True}
            except (TypeError, ValueError):
                out = {"stage": "call", "returned_repr": repr(value)[:1000], "json": False}
sys.stdout.write("\\n" + MARK + json.dumps(out) + "\\n")
'''


# ------------------------------------------------------------------ the input

def validate(failing_input: Any) -> dict[str, Any]:
    """The closed shape of a failing input, or a TypeError saying what is wrong."""
    if not isinstance(failing_input, dict):
        raise TypeError("a failing input is an object: call, args, kwargs, expect, value")
    call = str(failing_input.get("call") or "").strip()
    if not CALL.match(call):
        raise TypeError(f"call {call!r} is not 'package.module:function' (or "
                        f"'module:Class.method')")
    args = failing_input.get("args", [])
    kwargs = failing_input.get("kwargs", {})
    if not isinstance(args, list) or not isinstance(kwargs, dict):
        raise TypeError("args is a JSON list and kwargs a JSON object")
    if any(not IDENT.match(str(k)) for k in kwargs):
        raise TypeError("every kwargs key is a parameter name")
    try:
        encoded = json.dumps([args, kwargs], ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"arguments must be plain JSON: {exc}") from None
    if len(encoded) > MAX_INPUT_CHARS:
        raise TypeError(f"arguments are limited to {MAX_INPUT_CHARS} characters of JSON")
    expect = str(failing_input.get("expect") or "")
    value = failing_input.get("value")
    if expect == "raises":
        if not EXCEPTION.match(str(value or "")):
            raise TypeError("expect 'raises' names the exception's class in value")
        value = str(value)
    elif expect == "returns":
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError):
            raise TypeError("expect 'returns' gives the JSON value in value") from None
    else:
        raise TypeError("expect is 'raises' or 'returns'")
    return {"call": call, "args": args, "kwargs": kwargs, "expect": expect, "value": value}


def shown(fi: dict[str, Any]) -> str:
    """`module:function(1, 'a', key=2)` - said to raise X / return Y."""
    parts = [json.dumps(a, ensure_ascii=False) for a in fi["args"]] + \
        [f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in fi["kwargs"].items()]
    then = (f"raises {fi['value']}" if fi["expect"] == "raises"
            else f"returns {json.dumps(fi['value'], ensure_ascii=False)}")
    return f"{fi['call']}({', '.join(parts)}) {then}"


# ------------------------------------------------------------------ the store

class RunnableStore:
    """Challenges with a failing input, and every run of one: append-only JSON Lines."""

    def __init__(self, vault: Vault):
        self.vault = vault
        self.path = vault.librarian / "claims" / "runnable.jsonl"

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        return [json.loads(line) for line in jsonl_lines(self.path.read_text(encoding="utf-8"))
                if line.strip()]

    def _append(self, row: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def add(self, claim: str, source: str, failing_input: dict[str, Any], origin: str,
            session: str = "", reason: str = "") -> str:
        fi = validate(failing_input)
        run_id = hashlib.sha256(json.dumps([source, fi], sort_keys=True).encode()
                                ).hexdigest()[:12]
        if not any(r.get("id") == run_id for r in self._rows()):
            self._append({"type": "runnable", "id": run_id, "at": now_iso(),
                          "claim": claim[:500], "source": source, "failing_input": fi,
                          "origin": origin, "session": session, "reason": reason[:300]})
        return run_id

    def get(self, run_id: str) -> dict[str, Any] | None:
        rows = self._rows()
        item = next((r for r in rows if r["type"] == "runnable" and r["id"] == run_id), None)
        if item is None:
            return None
        runs = [r for r in rows if r["type"] == "run" and r["id"] == run_id]
        return {**item, "runs": runs, "verdict": runs[-1]["verdict"] if runs else "not run"}

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._rows()
        items = [r for r in rows if r["type"] == "runnable"][-limit:]
        out = []
        for item in reversed(items):
            runs = [r for r in rows if r["type"] == "run" and r["id"] == item["id"]]
            out.append({**item, "shown": shown(item["failing_input"]),
                        "verdict": runs[-1]["verdict"] if runs else "not run",
                        "runs": len(runs)})
        return out

    def record(self, run_id: str, result: dict[str, Any]) -> None:
        self._append({"type": "run", "id": run_id, "at": now_iso(), **result})


# ------------------------------------------------------------------ the sandbox

def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def docker_status(runner: Callable[..., Any] | None = None) -> tuple[bool, str]:
    if shutil.which("docker") is None and runner is None:
        return False, "Docker is not installed"
    runner = runner or _run              # looked up when called, so a test can stand in for it
    try:
        done = runner(["docker", "info", "--format", "{{.ServerVersion}}"], 30)
    except Exception as exc:                                # noqa: BLE001
        return False, f"Docker did not answer: {exc}"
    if getattr(done, "returncode", 1) != 0:
        return False, ("Docker is installed but not running: start Docker Desktop, then run "
                       "it again")
    return True, f"Docker {str(done.stdout).strip()}"


def repository_of(vault: Vault, source: str) -> dict[str, Any]:
    """The catalogued repository a claim cites: its clone URL and the tree it was surveyed at."""
    from . import notes
    from .evidence import EvidenceStore
    path = next((p for p in sorted((vault.root / "Sources").rglob(f"{source}.md"))
                 if "files" not in p.relative_to(vault.root).parts), None)
    if path is None:
        raise TypeError(f"no Source note {source!r}")
    fm = notes.load(path).frontmatter
    key = str(fm.get("repo_key") or "")
    if fm.get("kind") != "repository" or not key:
        raise TypeError(f"{source!r} is not a catalogued repository: only a repository's own "
                        f"code is run")
    url = str(fm.get("canonical_url") or f"https://github.com/{key}")
    tree = next((str(r.payload["tree_sha"]) for r in
                 (EvidenceStore(vault).get(str(e)) for e in fm.get("evidence") or [])
                 if r is not None and r.kind == "survey" and r.payload.get("tree_sha")), "")
    return {"url": url, "repo_key": key, "surveyed_tree": tree}


def command(name: str, checkout: Path, job: Path) -> list[str]:
    """The container, built here in code; every flag is a control."""
    return ["docker", "run", "--rm", "--name", name,
            "--network", "none",                       # no egress, no dependency fetching
            "--memory", MEMORY, "--cpus", CPUS, "--pids-limit", "128",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "65534:65534",                   # nobody
            "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={checkout},target=/src,readonly",
            "--mount", f"type=bind,source={job},target=/job,readonly",
            "--workdir", "/src", IMAGE, "python", "-I", "/job/runner.py"]


def judge(fi: dict[str, Any], outcome: dict[str, Any]) -> tuple[str, str]:
    """confirmed / not_confirmed / could_not_run, and why."""
    stage = outcome.get("stage")
    if stage in ("import", "lookup") or outcome.get("error") == "timeout":
        why = f"{outcome.get('error')}: {outcome.get('message', '')}".strip()
        if outcome.get("error") == "ModuleNotFoundError":
            why += " (the sandbox has no network, so only the standard library and the " \
                   "repository's own code import)"
        return "could_not_run", why
    if stage != "call":
        return "could_not_run", str(outcome.get("message") or "the runner reported nothing")
    if fi["expect"] == "raises":
        if "raised" in outcome:
            name = str(fi["value"])
            hit = outcome["raised"] == name.rsplit(".", 1)[-1] and (
                "." not in name or outcome.get("qualified", "").endswith(name))
            return ("confirmed" if hit else "not_confirmed",
                    f"raised {outcome['qualified']}: {outcome.get('message', '')}")
        return "not_confirmed", ("returned " + json.dumps(outcome.get("returned"))
                                 if outcome.get("json") else
                                 f"returned {outcome.get('returned_repr')}")
    if "raised" in outcome:
        return "not_confirmed", f"raised {outcome['qualified']}: {outcome.get('message', '')}"
    if outcome.get("json") and outcome.get("returned") == fi["value"]:
        return "confirmed", "returned " + json.dumps(outcome["returned"])
    return "not_confirmed", ("returned " + json.dumps(outcome.get("returned"))
                             if outcome.get("json") else
                             f"returned {outcome.get('returned_repr')}")


def parse(stdout: str) -> dict[str, Any]:
    marked = [line for line in str(stdout).split("\n") if line.startswith(MARK)]
    if not marked:
        return {"stage": "none", "message": "the runner printed no result"}
    try:
        return json.loads(marked[-1][len(MARK):])
    except ValueError:
        return {"stage": "none", "message": "the runner's result was not readable"}


def run(vault: Vault, run_id: str, *, runner: Callable[..., Any] | None = None,
        cloner: Callable[[str], Any] | None = None) -> dict[str, Any]:
    """One person-initiated run of one stored failing input."""
    runner = runner or _run
    from .evidence import EvidenceStore
    from .structure import shallow_clone
    store = RunnableStore(vault)
    item = store.get(run_id)
    if item is None:
        raise TypeError(f"no runnable claim {run_id!r}: list_claim_runs shows them")
    fi = item["failing_input"]
    repo = repository_of(vault, item["source"])
    ok, why = docker_status(runner)
    if not ok:
        raise Refusal("EXECUTION_SANDBOX_ONLY", why)
    cloner = cloner or shallow_clone
    with cloner(repo["url"]) as checkout:
        checkout = Path(checkout)
        tree = _git(checkout, "rev-parse", "HEAD^{tree}")
        commit = _git(checkout, "rev-parse", "HEAD")
        version = ("the surveyed version" if tree and tree == repo["surveyed_tree"] else
                   f"a newer version than surveyed (tree {tree[:12] or '?'}, surveyed "
                   f"{repo['surveyed_tree'][:12] or 'not recorded'})")
        job = Path(tempfile.mkdtemp(prefix="librarian-job-"))
        try:
            paths = ["/src"] + (["/src/src"] if (checkout / "src").is_dir() else [])
            (job / "spec.json").write_text(json.dumps(
                {"call": fi["call"], "args": fi["args"], "kwargs": fi["kwargs"],
                 "paths": paths}), encoding="utf-8")
            (job / "runner.py").write_text(RUNNER, encoding="utf-8")
            name = f"librarian-run-{run_id}-{now_iso()[11:19].replace(':', '')}"
            try:
                done = runner(command(name, checkout, job), TIMEOUT + 30)
                outcome = parse(getattr(done, "stdout", ""))
                if outcome.get("stage") == "none" and getattr(done, "returncode", 0):
                    outcome["message"] = (str(getattr(done, "stderr", "")).strip()[-400:]
                                          or outcome["message"])
            except subprocess.TimeoutExpired:
                try:
                    runner(["docker", "kill", name], 30)
                except Exception:                           # noqa: BLE001
                    pass
                outcome = {"stage": "none", "error": "timeout",
                           "message": f"still running after {TIMEOUT + 30}s; stopped"}
        finally:
            shutil.rmtree(job, ignore_errors=True)
    verdict, detail = judge(fi, outcome)
    evidence = EvidenceStore(vault).put("execution", f"{repo['url']}@{commit or 'unknown'}", {
        "call": fi["call"], "args": fi["args"], "kwargs": fi["kwargs"],
        "expected": {"expect": fi["expect"], "value": fi["value"]},
        "image": IMAGE, "network": "none", "commit": commit, "tree": tree,
        "surveyed_tree": repo["surveyed_tree"], "outcome": outcome, "verdict": verdict})
    result = {"verdict": verdict, "detail": detail[:600], "version": version,
              "commit": commit, "evidence": evidence.id, "by": "person"}
    store.record(run_id, result)
    return {"run": run_id, "claim": item["claim"], "input": shown(fi), **result}


def _git(checkout: Path, *args: str) -> str:
    try:
        done = subprocess.run(["git", "-C", str(checkout), *args], capture_output=True,
                              text=True, timeout=30)
        return done.stdout.strip() if done.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""
