"""The sandbox: code run in a container of its own, air-gapped, writing only to a landing pad
(owner, 2026-10-01; rule EXECUTION_SANDBOX_ONLY).

Who runs what:
- **The agent** runs code it wrote (`sandbox_run`): a Python or shell script, with any
  library files it names copied in read-only. It goes through the permission broker like
  any write (asked in Ask mode, refused in Plan mode).
- **A person** runs a script file from the document pane ("Run this script", shown only for
  a script - `.py`, `.sh` - never for a note or text), and a claim's failing input
  (`claim_run.py`).

Every run, whoever starts it, gets a fresh container that is removed when it stops: no
network, no capabilities, an unprivileged user, a read-only root, its code and inputs
mounted read-only, a small `/tmp`, memory, CPU, process and time limits, and nothing from
this machine's environment (no keys). Containers share nothing: each run has its own
folders.

**The landing pad.** The only place a run can write outside its container is its own
`/landing`, which is `.librarian/sandbox/landing/<run>/` here. After the run, that folder is
checked: symbolic links are removed, the total is held to LANDING_MAX_BYTES and the file
count to LANDING_MAX_FILES (what is over is deleted and said), and every file is listed
with its size and digest. Nothing on the pad is ever executed, imported, indexed or moved
by the app: the model may read a text file from it (`sandbox_read`), and moving anything
out is a person's act.

The image is `librarian-sandbox:1`, built once from `sandbox/Dockerfile` (python:3.11-slim
and an unprivileged user); without a running Docker there is no run, and no fallback to
this machine.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from .rules import Refusal
from .vault import Vault, now_iso

IMAGE = "librarian-sandbox:1"
BASE_IMAGE = "python:3.11-slim"
DOCKERFILE = f"""FROM {BASE_IMAGE}
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin runner
USER runner
WORKDIR /work
"""
TIMEOUT = 120
MEMORY = "1g"
CPUS = "1"
LANDING_MAX_BYTES = 50 * 1024 * 1024
LANDING_MAX_FILES = 200
READ_MAX_BYTES = 200_000
CODE_MAX_CHARS = 100_000
SCRIPTS = {".py": "python", ".sh": "shell"}
INTERPRETER = {"python": ["python", "-I"], "shell": ["sh"]}
OUTPUT_CHARS = 8000

Runner = Callable[[list[str], float], Any]


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def docker_status(runner: Runner | None = None) -> tuple[bool, str]:
    if runner is None and shutil.which("docker") is None:
        return False, "Docker is not installed"
    runner = runner or _run
    try:
        done = runner(["docker", "info", "--format", "{{.ServerVersion}}"], 30)
    except Exception as exc:                                # noqa: BLE001
        return False, f"Docker did not answer: {exc}"
    if getattr(done, "returncode", 1) != 0:
        return False, "Docker is installed but not running: start Docker Desktop"
    return True, f"Docker {str(done.stdout).strip()}"


def ensure_image(vault: Vault, runner: Runner | None = None) -> str:
    """The sandbox image, built once (pulling its base image the first time)."""
    runner = runner or _run
    have = runner(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"], 60)
    if getattr(have, "returncode", 1) == 0:
        return str(have.stdout).strip()
    context = vault.librarian / "sandbox" / "image"
    context.mkdir(parents=True, exist_ok=True)
    (context / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8")
    built = runner(["docker", "build", "--tag", IMAGE, str(context)], 900)
    if getattr(built, "returncode", 1) != 0:
        raise Refusal("EXECUTION_SANDBOX_ONLY", "the sandbox image could not be built: " +
                      str(getattr(built, "stderr", "")).strip()[-300:])
    return IMAGE


def landing_root(vault: Vault) -> Path:
    return vault.librarian / "sandbox" / "landing"


def command(name: str, job: Path, landing: Path, inputs: Path | None, language: str,
            entry: str) -> list[str]:
    """The container, built here in code; every flag is a control."""
    args = ["docker", "run", "--rm", "--name", name,
            "--network", "none",                       # air-gapped
            "--memory", MEMORY, "--cpus", CPUS, "--pids-limit", "128",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001",
            "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={job},target=/job,readonly",
            "--mount", f"type=bind,source={landing},target=/landing"]
    if inputs is not None:
        args += ["--mount", f"type=bind,source={inputs},target=/inputs,readonly"]
    return args + ["--workdir", "/landing", IMAGE, *INTERPRETER[language], f"/job/{entry}"]


def _check_landing(landing: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """The pad after a run: links removed, size and count held, every file listed."""
    notes: list[str] = []
    files: list[dict[str, Any]] = []
    total = 0
    for path in sorted(landing.rglob("*")):
        if path.is_symlink():
            path.unlink()
            notes.append(f"removed a link: {path.relative_to(landing).as_posix()}")
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        rel = path.relative_to(landing).as_posix()
        if total + size > LANDING_MAX_BYTES or len(files) >= LANDING_MAX_FILES:
            path.unlink()
            notes.append(f"removed {rel}: over the pad's limit ({LANDING_MAX_FILES} files, "
                         f"{LANDING_MAX_BYTES // (1024 * 1024)} MB)")
            continue
        total += size
        files.append({"name": rel, "bytes": size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16]})
    return files, notes


def run(vault: Vault, code: str, language: str, by: str, inputs: list[str] | None = None,
        timeout: int = TIMEOUT, runner: Runner | None = None, label: str = "") -> dict[str, Any]:
    """One run in a fresh container. `inputs` are library files, copied in read-only."""
    runner = runner or _run          # looked up when called, so a test can stand in for it
    if language not in INTERPRETER:
        raise TypeError(f"language is one of {sorted(INTERPRETER)}")
    if not code.strip() or len(code) > CODE_MAX_CHARS:
        raise TypeError(f"give the code to run (up to {CODE_MAX_CHARS} characters)")
    ok, why = docker_status(runner)
    if not ok:
        raise Refusal("EXECUTION_SANDBOX_ONLY", why)
    ensure_image(vault, runner)
    run_id = f"{now_iso()[:19].replace(':', '').replace('-', '')}-{secrets.token_hex(3)}"
    base = vault.librarian / "sandbox" / "runs" / run_id
    job, landing = base / "job", landing_root(vault) / run_id
    job.mkdir(parents=True)
    landing.mkdir(parents=True)
    entry = "main.py" if language == "python" else "main.sh"
    (job / entry).write_text(code, encoding="utf-8")
    staged_inputs = None
    if inputs:
        staged_inputs = base / "inputs"
        staged_inputs.mkdir()
        for rel in inputs:
            source = vault.safe_relative(rel)
            if not source.is_file():
                raise TypeError(f"no library file {rel!r} to copy in")
            shutil.copy2(source, staged_inputs / source.name)
    name = f"librarian-sandbox-{run_id}"
    timed_out = False
    try:
        done = runner(command(name, job, landing, staged_inputs, language, entry),
                      min(int(timeout), 900) + 30)
        code_out, stdout, stderr = (getattr(done, "returncode", -1),
                                    str(getattr(done, "stdout", "")),
                                    str(getattr(done, "stderr", "")))
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            runner(["docker", "kill", name], 30)
        except Exception:                                   # noqa: BLE001
            pass
        code_out, stdout, stderr = -1, "", f"stopped after {timeout}s"
    finally:
        shutil.rmtree(job, ignore_errors=True)
    files, notes = _check_landing(landing)
    record = {"run": run_id, "by": by, "label": label, "language": language,
              "exit_code": code_out, "timed_out": timed_out, "network": "none",
              "inputs": inputs or [], "landing": f".librarian/sandbox/landing/{run_id}",
              "files": files, "notes": notes, "at": now_iso()}
    log = vault.librarian / "sandbox" / "runs.jsonl"
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({**record, "code_sha256":
                                 hashlib.sha256(code.encode()).hexdigest()[:16]}) + "\n")
    return {**record, "stdout": stdout[-OUTPUT_CHARS:], "stderr": stderr[-OUTPUT_CHARS:]}


def read_landed(vault: Vault, run_id: str, name: str) -> dict[str, Any]:
    """A text file from a run's landing pad - read, never executed or imported."""
    pad = (landing_root(vault) / run_id).resolve()
    target = (pad / name).resolve()
    if pad not in target.parents or not target.is_file():
        raise TypeError(f"no file {name!r} on run {run_id}'s landing pad")
    data = target.read_bytes()
    if len(data) > READ_MAX_BYTES or b"\x00" in data[:4096]:
        raise TypeError(f"{name!r} is binary or larger than {READ_MAX_BYTES} bytes: a person "
                        f"opens it from the pad")
    return {"run": run_id, "name": name, "text": data.decode("utf-8", "replace")}
