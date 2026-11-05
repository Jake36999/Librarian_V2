"""The sandbox: code run in a container of its own, air-gapped, writing only to a landing pad
(owner, 2026-10-01; rule EXECUTION_SANDBOX_ONLY).

Who runs what:
- **The agent** runs code it wrote (`sandbox_run`): a Python or shell script, with any
  library files it names copied in read-only. It goes through the permission broker like
  any write (asked in Ask mode, refused in Plan mode).
- **A person** runs a script file from the document pane ("Run this script", shown only for
  a script - `.py`, `.sh` - never for a note or text), and a claim's failing input
  (`claim_run.py`).

Every run, whoever starts it, gets a fresh container of its own: no network, no
capabilities, an unprivileged user, a read-only root, its code and inputs mounted read-only,
a small `/tmp`, memory, CPU, process and time limits, and nothing from this machine's
environment (no keys). Containers share nothing: each run has its own folders.

**Its life** (MF-016; see `containers.py`). The container is created, started attached and
supervised here, never with `--rm`:
- What it prints is counted and held to a bounded tail.
- Its deadline, a cancelled turn, or output past its limit requests one stop.
- It is inspected and shown stopped (killed if it has to be) before anything leaves it.
- Then it is removed.
A run whose container cannot be shown stopped and removed ends `cleanup_unknown`. That run
is never `completed`, and nothing it wrote is kept.

**The landing pad.** The only place a run can write outside its small `/tmp` is its own
`/landing`, an anonymous volume removed with the container. After the run stops, `/landing`
streams out as a tar into a private quarantine (`.librarian/quarantine/sandbox/<run>`) and
each member is checked before it is written:
- regular files and folders only, with names safe on this machine;
- at most LANDING_MAX_FILES entries and LANDING_MAX_BYTES in all.
Only if all of it passes is it moved to `.librarian/sandbox/landing/<run>/`, and every
file is listed with its size and digest. Otherwise nothing is kept, and what arrived stays
in quarantine for a person (the newest few are kept). Nothing on the pad is ever executed,
imported, indexed or moved by the app. The model may read a text file from it
(`sandbox_read`); moving anything out is a person's act.

**Output is its own permission** (owner, 2026-11-05; MF-015). Those limits hold for what is
kept, not for what the run writes while it runs:
- Docker Desktop on WSL2 ignores `--storage-opt size`: measured 2026-11-05, 60 MiB was
  written under a 20 MB cap.
- A volume has no cap of its own.
So a run gets a writable `/landing` only when `sandbox_output` is allowed. That is a write
of its own:
- asked about in every mode (`broker.ALWAYS_ASK`) and refused in Plan mode;
- allowing the run, or any earlier write, never grants it.
While it runs, its disk writes are sampled, and past IO_LIMIT_BYTES a stop is requested.
That is a monitor, not a quota. Refused or unanswered, the run still goes ahead with no
writable pad: it keeps what it prints, but no file it writes is kept. A Workbench
engagement's output volume is gated the same way.

The image is `librarian-sandbox:2`, built once from `sandbox/Dockerfile`: python:3.11-slim,
an unprivileged user, and a `/landing` that user owns. Without a running Docker there is no
run, and no fallback to this machine.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import secrets
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from . import containers
from .rules import Refusal
from .vault import Vault, now_iso

IMAGE = "librarian-sandbox:2"
BASE_IMAGE = "python:3.11-slim"
DOCKERFILE = f"""FROM {BASE_IMAGE}
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin runner && mkdir -p /landing && chown 10001:10001 /landing
USER runner
WORKDIR /work
"""
TIMEOUT = 120
MEMORY = "1g"
CPUS = "1"
LANDING_MAX_BYTES = 50 * 1024 * 1024
LANDING_MAX_FILES = 200
# Writes past this are stopped: more than twice what could be kept is not output.
IO_LIMIT_BYTES = 2 * LANDING_MAX_BYTES
READ_MAX_BYTES = 200_000
CODE_MAX_CHARS = 100_000
SCRIPTS = {".py": "python", ".sh": "shell"}
INTERPRETER = {"python": ["python", "-I"], "shell": ["sh"]}
OUTPUT_CHARS = 8000

Runner = Callable[[list[str], float], Any]


CAPTURE_BYTES = 64 * 1024


def drain(process: subprocess.Popen, timeout: float, on_timeout: Callable[[], Any],
          keep: int = CAPTURE_BYTES) -> tuple[str, str, bool, dict[str, int]]:
    """Read a process's stdout and stderr to the end, holding only the last `keep`
    bytes of each in memory (REMED-04: a run that prints gigabytes must not
    exhaust this machine). Returns both tails, whether it timed out, and how
    many bytes each stream really produced."""
    import threading
    tails: dict[str, bytes] = {}
    totals: dict[str, int] = {}

    def pump(name: str, pipe: Any) -> None:
        held, total = bytearray(), 0
        try:
            for block in iter(lambda: pipe.read1(64 * 1024), b""):
                total += len(block)
                held += block
                if len(held) > keep:
                    del held[:-keep]
        except (OSError, ValueError):
            pass
        tails[name], totals[name] = bytes(held), total

    pumps = [threading.Thread(target=pump, args=(name, pipe), daemon=True)
             for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr))
             if pipe is not None]
    for thread in pumps:
        thread.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        on_timeout()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=30)
    for thread in pumps:
        thread.join(timeout=10)
    text = {name: tails.get(name, b"").decode("utf-8", "replace") for name in ("stdout", "stderr")}
    return text["stdout"], text["stderr"], timed_out, {name: totals.get(name, 0)
                                                        for name in ("stdout", "stderr")}


def run_bounded(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    """`subprocess.run` with bounded capture: what a command prints is held to its
    last CAPTURE_BYTES per stream. A timeout kills it and raises, as `run` does."""
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    stdout, stderr, timed_out, produced = drain(process, timeout, process.kill)
    if timed_out:
        raise subprocess.TimeoutExpired(args, timeout, stdout, stderr)
    done = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
    done.produced = produced                                   # type: ignore[attr-defined]
    return done


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return run_bounded(args, timeout)


_run.supervised = True                  # type: ignore[attr-defined]  # the real Docker


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


OUTPUT_PERMISSION = "sandbox_output"
UNCAPPED = ("nothing limits what the run writes while it runs: Docker cannot cap a folder "
            "shared with this machine")


def output_permission(ctx: Any, where: str, after_run: str) -> tuple[bool, str]:
    """Whether a run may write files with no disk cap while it runs, and how that was decided.

    Asked through the permission broker as its own write, `sandbox_output`, in every mode
    and whatever was allowed before. With no broker (a direct, CLI or test call, where the
    registry has none either), it is allowed, as every write is there.
    """
    from .registry import Card, ToolSpec
    broker = getattr(ctx, "extras", {}).get("broker") if ctx is not None else None
    if broker is None:
        return True, "no broker"
    spec = ToolSpec(OUTPUT_PERMISSION, fn=lambda *args, **kwargs: None, tier="contribute",
                    effect="write",
                    card=Card("Let a container run write files to its output folder",
                              "a sandbox run or a Workbench engagement is about to start",
                              "No disk cap applies while it runs; the output is checked "
                              "after it"))
    try:
        return True, broker.check(spec, {"writes_to": where, "while_running": UNCAPPED,
                                         "after_the_run": after_run}, ctx)
    except Refusal as refusal:
        return False, f"{refusal.code}: {refusal.detail}"


def quarantine_root(vault: Vault) -> Path:
    return vault.librarian / "quarantine" / "sandbox"


def container_flags(job: Path, landing: bool, inputs: Path | None, language: str) -> list[str]:
    """The container's controls, built here in code; every flag is one.

    With `landing` (its output permitted) `/landing` is an anonymous volume of its own,
    removed with the container: nothing the run writes reaches this machine except
    through the checked export. Without it nothing writable is mounted: the code runs in
    its small `/tmp`, and what it writes there goes with the container.
    """
    args = ["--network", "none",                       # air-gapped
            "--memory", MEMORY, "--cpus", CPUS, "--pids-limit", "128",
            "--read-only", "--tmpfs", "/tmp:rw,size=64m",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--user", "10001:10001",
            "-e", "HOME=/tmp", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={job},target=/job,readonly"]
    if landing:
        args += ["--mount", "type=volume,target=/landing"]
    if inputs is not None:
        args += ["--mount", f"type=bind,source={inputs},target=/inputs,readonly"]
    return args + ["--workdir", "/landing" if landing else "/tmp"]


def _log(vault: Vault, row: dict[str, Any]) -> None:
    log = vault.librarian / "sandbox" / "runs.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


STOPPED = {"deadline": "stopped after {timeout}s",
           "cancelled": "stopped: the turn was cancelled",
           "output_limit": "stopped: it printed more than {limit} MB",
           "io_limit": "stopped: it wrote more than {io} MB to disk"}


def run(vault: Vault, code: str, language: str, by: str, inputs: list[str] | None = None,
        timeout: int = TIMEOUT, runner: Runner | None = None, label: str = "",
        ctx: Any = None) -> dict[str, Any]:
    """One run in a fresh container. `inputs` are library files, copied in read-only.

    `ctx` carries the permission broker that decides `sandbox_output` for this run, and
    the turn's cancel event, if it has one."""
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
    keep, permission = output_permission(
        ctx, f".librarian/sandbox/landing/{run_id}",
        f"exported only once the run is stopped, and only if all of it passes: no links, "
        f"no unsafe names, at most {LANDING_MAX_FILES} entries and "
        f"{LANDING_MAX_BYTES // (1024 * 1024)} MB")
    job = base / "job"
    job.mkdir(parents=True)
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
    producer = containers.Producer(name, runner, kind="sandbox")
    _log(vault, {"run": run_id, "state": "reserved", "container": name, "at": now_iso()})
    extras = getattr(ctx, "extras", None) or {}
    files: list[dict[str, Any]] = []
    notes: list[str] = []
    report: dict[str, Any] | None = None
    quarantined = ""
    landing = landing_root(vault) / run_id
    try:
        capture = producer.execute(
            container_flags(job, keep, staged_inputs, language), IMAGE,
            [*INTERPRETER[language], f"/job/{entry}"], deadline=min(int(timeout), 900) + 5,
            cancel=extras.get("cancel"), io_limit=IO_LIMIT_BYTES if keep else None)
        if keep:
            quarantine = quarantine_root(vault) / run_id
            report = producer.export_to("/landing", quarantine, max_bytes=LANDING_MAX_BYTES,
                                        max_entries=LANDING_MAX_FILES)
        producer.dispose()
        if keep and report is not None:
            if report["accepted"] and producer.state == "disposed":
                containers.promote(quarantine, landing)
                files = [{"name": f["name"], "bytes": f["bytes"], "sha256": f["sha256"][:16]}
                         for f in report["files"]]
            else:
                why = report["stopped"] or "; ".join(report["rejected"][:5])
                if producer.state == "cleanup_unknown":
                    why = "the container could not be shown stopped and removed"
                notes.append(f"nothing this run wrote was kept: {why}")
                if quarantine.is_dir():
                    quarantined = quarantine.relative_to(vault.root).as_posix()
                    notes.append(f"what arrived is held for a person in {quarantined} (the "
                                 f"newest {containers.QUARANTINE_KEEP} are kept)")
                containers.prune(quarantine_root(vault))
    except BaseException:
        # Whatever went wrong here, the container is not left running.
        with contextlib.suppress(Exception):
            if producer.state not in ("disposed", "cleanup_unknown"):
                producer.stop("error")
                producer.settle()
                producer.dispose()
        raise
    finally:
        shutil.rmtree(job, ignore_errors=True)
    if not keep:
        notes.append("no file this run wrote was kept: writing its output was not "
                     f"permitted ({permission})")
    stderr = capture.stderr
    if producer.stop_reason in STOPPED:
        said = STOPPED[producer.stop_reason].format(
            timeout=timeout, limit=containers.STREAM_LIMIT_BYTES // (1024 * 1024),
            io=IO_LIMIT_BYTES // (1024 * 1024))
        notes.append(said)
        stderr = (stderr + "\n" + said).lstrip("\n")
    if producer.state == "cleanup_unknown":
        notes.append("this run is not a success: its container could not be shown stopped "
                     f"and removed ({name}); `docker rm -f {name}` removes it")
    kept = bool(files) or (report is not None and report["accepted"] and landing.is_dir())
    record = {"run": run_id, "by": by, "label": label, "language": language,
              "exit_code": capture.exit_code if capture.exit_code is not None else -1,
              "timed_out": producer.stop_reason == "deadline",
              "stopped": producer.stop_reason,
              # Complete only if it ended by itself, was shown stopped and removed, and
              # what it wrote (if that was allowed) was kept whole.
              "completed": producer.succeeded and not producer.stop_reason and
              capture.exit_code == 0 and (not keep or kept),
              "network": "none", "inputs": inputs or [],
              "landing": f".librarian/sandbox/landing/{run_id}" if kept else "",
              "output": {"allowed": keep, "kept": kept, "permission": permission,
                         **({"export": {k: report[k] for k in
                                        ("accepted", "entries", "bytes", "stopped")} |
                             {"refused": report["rejected"][:20]}} if report else {}),
                         "quarantine": quarantined},
              "files": files, "notes": notes, "execution": producer.record(), "at": now_iso()}
    _log(vault, {**record, "state": producer.state,
                 "code_sha256": hashlib.sha256(code.encode()).hexdigest()[:16]})
    return {**record, "stdout": capture.stdout[-OUTPUT_CHARS:], "stderr": stderr[-OUTPUT_CHARS:]}


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
