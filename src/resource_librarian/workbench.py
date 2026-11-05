"""Source-bound workbench engagements.

An engagement makes executable work explicit: which catalogued repository and
pinned revision it concerns, why it is needed, the isolation tier, outputs,
and its close-out outcome.  It is intentionally a first-party Core feature,
not an arbitrary plugin runtime.

Isolation policy (REMED-04).  Every container a Docker engagement starts is
built from `CONTAINED`: no network, every capability dropped, no privilege
gain.  Each phase then adds only what it needs, and says why:

Every one of those containers lives as `containers.Producer` (MF-016):
- created and started attached, never `--rm`;
- its output held to a bounded tail;
- one stop on its deadline, a cancelled turn, or too much output;
- shown stopped before anything is taken from it, then removed.

- **provision** (`_docker_stage`, output volume): read-only root, runs as root
  with FOWNER alone, to make the root-owned output volume writable by the
  unprivileged runner.
- **stage** (`_docker_stage`, source volume): the archive is checked on this
  machine first (no links, no paths outside, size held) and only then copied
  in.  Runs as root without capabilities, so the copy lands in a root-owned
  volume yet tar cannot restore ownership; its writable layer is where
  `docker cp` places the archive.
- **execute** (`_docker_execute`): read-only root, a small /tmp, the
  unprivileged runner uid, the source read-only, memory, CPU and process limits.
  The output volume is mounted only when `sandbox_output` is allowed: nothing
  caps it while the run writes (MF-015, owner 2026-11-05; see `sandbox.py`).
  Without it the run keeps what it prints, and nothing is exported.
- **export** (`_archive_outputs`): from the execution container itself, once it
  is shown stopped; the stopped filesystem is never restarted.
  - The output volume streams out as a tar into a private quarantine.
  - Each member is checked before anything is written: regular files and
    folders only, with names safe here, and at most MAX_OUTPUT_FILES entries
    and MAX_OUTPUT_BYTES in all.
  - Only if every member passes, and the container is then removed, does it
    replace the engagement's folder. Otherwise nothing is kept, and the reason
    is named.

Docker's default seccomp profile applies; it is relied on, not asserted.
What any process prints is held to its last `sandbox.CAPTURE_BYTES` per
stream, host execution included.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import venv
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

from .coordination import atomic_write_text
from .rules import Refusal
from .vault import Vault, jsonl_lines, now_iso

Runner = Callable[[list[str], float], Any]
MAX_ARCHIVE_BYTES = 250 * 1024 * 1024
MAX_OUTPUT_BYTES = 100 * 1024 * 1024
MAX_OUTPUT_FILES = 1000
HOST_EXECUTION_SECONDS = 300
EXPORT_SECONDS = 300
# The flags every Workbench container carries (see the isolation policy above).
CONTAINED = ["--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
HELPER_LIMITS = ["--memory", "512m", "--cpus", "1", "--pids-limit", "64"]
HOST_EXECUTION_MEMORY = 1024 * 1024 * 1024
HOST_EXECUTION_PROCESSES = 8


@dataclass
class Engagement:
    id: str
    source: str
    pinned_revision: str
    project: str = ""
    session: str = ""
    purpose: str = ""
    isolation_tier: str = "inspect_only"
    workspace: str = ""
    run_ids: list[str] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    application: str = ""
    outcome: str = ""
    state: str = "proposed"
    close_reason: str = ""
    audit_trace: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def public(self) -> dict[str, Any]:
        return asdict(self)


class EngagementStore:
    def __init__(self, vault: Vault) -> None:
        self.vault = vault
        self.path = vault.librarian / "engagements.jsonl"

    def _events(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        out = []
        for line in jsonl_lines(self.path.read_text(encoding="utf-8")):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                out.append(row)
        return out

    def _append(self, event: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
            handle.flush()
            with contextlib.suppress(OSError):
                os.fsync(handle.fileno())

    def _states(self) -> dict[str, Engagement]:
        current: dict[str, Engagement] = {}
        for event in self._events():
            data = event.get("engagement")
            if not isinstance(data, dict):
                continue
            try:
                current[str(data["id"])] = Engagement(**data)
            except TypeError:
                continue
        return current

    def get(self, engagement_id: str) -> Engagement:
        try:
            return self._states()[engagement_id]
        except KeyError as exc:
            raise KeyError(f"no engagement {engagement_id!r}") from exc

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        rows = sorted(self._states().values(), key=lambda item: item.updated_at, reverse=True)
        return [item.public() for item in rows[:max(1, min(limit, 500))]]

    def put(self, engagement: Engagement, event: str) -> Engagement:
        engagement.updated_at = now_iso()
        self._append({"at": engagement.updated_at, "event": event, "engagement": engagement.public()})
        return engagement


def _repository(vault: Vault, source: str) -> dict[str, Any]:
    from .claim_run import repository_of
    repo = repository_of(vault, source)
    if not repo.get("surveyed_tree"):
        raise Refusal("PINNED_REVISION_REQUIRED", "the catalogued repository has no surveyed tree revision")
    return repo


def plan(vault: Vault, source: str, purpose: str = "", project: str = "", session: str = "") -> dict[str, Any]:
    repo = _repository(vault, source)
    from . import sandbox
    docker_ok, docker_detail = sandbox.docker_status()
    return {"source": source, "pinned_revision": repo["surveyed_tree"], "repository": repo["repo_key"],
            "purpose": purpose[:500], "project": project, "session": session,
            "docker": {"available": docker_ok, "detail": docker_detail,
                       "strategy": "managed named source/output volumes; no NTFS bind mount"},
            "choices": (["inspect_only", "retry_docker", "docker_isolated"] if docker_ok else
                        ["inspect_only", "retry_docker", "non_isolated_host_exec"]),
            "requires_person": True,
            "note": "Agents may inspect/propose this plan. A person must explicitly start any execution."}


def propose(vault: Vault, source: str, purpose: str = "", project: str = "", session: str = "") -> dict[str, Any]:
    prepared = plan(vault, source, purpose, project, session)
    engagement = Engagement(id=f"eng-{now_iso()[:10].replace('-', '')}-{secrets.token_hex(4)}", source=source,
                            pinned_revision=prepared["pinned_revision"], project=project, session=session,
                            purpose=purpose[:500], workspace="managed on start", created_at=now_iso(),
                            updated_at=now_iso(), audit_trace=[{"at": now_iso(), "event": "proposed",
                                                               "detail": "source and revision pinned"}])
    EngagementStore(vault).put(engagement, "proposed")
    return {"engagement": engagement.public(), "plan": prepared}


def _run(args: list[str], timeout: float) -> subprocess.CompletedProcess:
    from .sandbox import run_bounded
    return run_bounded(args, timeout)


_run.supervised = True                  # type: ignore[attr-defined]  # the real Docker


def _stream(args: list[str], timeout: float):
    """A command's stdout as a binary stream, never held whole (`containers.stream`)."""
    from .containers import stream
    return stream(args, timeout)


def _volume_name(engagement: Engagement, kind: str) -> str:
    return f"librarian-{engagement.id}-{kind}".lower().replace("_", "-")[:63]


def _require_image(image: str) -> str:
    image = image.strip()
    if "@sha256:" not in image:
        raise TypeError("Docker execution requires a pinned image digest (image@sha256:...)")
    return image


def _archive_url(repo_key: str, revision: str) -> str:
    # The GitHub tree SHA is both a revision pin and safe path component.
    if not repo_key or "/" not in repo_key or any(part in repo_key for part in ("..", "\\")):
        raise TypeError("the catalogued repository has no safe GitHub repo key")
    return f"https://codeload.github.com/{repo_key}/tar.gz/{revision}"


def _download_archive(repo_key: str, revision: str) -> tuple[Path, str]:
    fd, name = tempfile.mkstemp(prefix="librarian-revision-", suffix=".tar.gz")
    path = Path(name)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(fd, "wb") as out, urlopen(_archive_url(repo_key, revision), timeout=90) as response:
            while True:
                block = response.read(64 * 1024)
                if not block:
                    break
                total += len(block)
                if total > MAX_ARCHIVE_BYTES:
                    raise TypeError("revision archive exceeds the workbench size limit")
                digest.update(block)
                out.write(block)
        return path, digest.hexdigest()
    except Exception:
        with contextlib.suppress(OSError):
            path.unlink()
        raise


def _validated_members(bundle: tarfile.TarFile) -> tuple[str, list[tarfile.TarInfo]]:
    """One top-level folder of regular files and folders, no path outside it,
    held to MAX_ARCHIVE_BYTES expanded; anything else refuses the archive."""
    total = 0
    root = ""
    safe: list[tarfile.TarInfo] = []
    for member in bundle.getmembers():
        raw = member.name.replace("\\", "/")
        parts = [part for part in raw.split("/") if part not in ("", ".")]
        if not parts or any(part == ".." for part in parts) or raw.startswith("/") or ":" in parts[0]:
            raise TypeError("revision archive contains an unsafe path")
        if not root:
            root = parts[0]
        if parts[0] != root:
            raise TypeError("revision archive has more than one top-level directory")
        if member.issym() or member.islnk() or member.isdev() or not (member.isdir() or member.isfile()):
            raise TypeError("revision archive contains a link or unsupported member")
        total += max(0, int(member.size))
        if total > MAX_ARCHIVE_BYTES:
            raise TypeError("revision archive expands beyond the workbench size limit")
        safe.append(member)
    if not root:
        raise TypeError("revision archive is empty")
    return root, safe


def _check_archive(archive: Path) -> None:
    """Refuse an archive here, before any helper container sees it (REMED-04)."""
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            _validated_members(bundle)
    except tarfile.TarError as exc:
        raise TypeError(f"revision archive is not a readable tar.gz: {exc}") from exc


def _extract_pinned_archive(archive: Path, destination: Path) -> Path:
    """Extract one GitHub revision archive without accepting tar path tricks.

    Host execution is not isolated, but its source still has to be the exact
    reviewed revision.  Keeping extraction here rather than using a host
    shell command makes the archive path, byte cap and link handling
    auditable before an explicitly chosen command can run.
    """
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as bundle:
        root, safe = _validated_members(bundle)
        # Members were validated above.  Do not preserve source ownership or
        # permissions from an untrusted archive on the host filesystem.
        bundle.extractall(destination, members=safe, numeric_owner=False)
    source = destination / root
    if not source.is_dir():
        raise TypeError("revision archive did not contain a source directory")
    return source


def _restricted_workspace(path: Path) -> tuple[bool, str]:
    """Apply the strongest cheap per-user workspace protection available."""
    try:
        if os.name == "nt":
            from .keys import _owner_only
            return (_owner_only(path), "Windows owner-only ACL")
        path.chmod(0o700)
        return (True, "POSIX mode 0700")
    except OSError as exc:
        return (False, f"could not restrict workspace permissions: {exc}")


class _WindowsJob:
    """Best-effort Job Object resource limits for explicitly non-isolated work.

    A Job Object does *not* fence a process's network, which is why callers
    receive ``non_isolated_host_exec`` regardless of whether this succeeds.
    It does give Windows a reliable process-tree kill boundary and bounded
    CPU time/memory/process count when available.
    """

    def __init__(self) -> None:
        self.handle: Any = None
        self.detail = "not applicable outside Windows"
        self.cpu_limited = False
        if os.name != "nt":
            return
        try:
            import ctypes
            from ctypes import wintypes

            size_t = ctypes.c_size_t
            ulong_ptr = ctypes.c_size_t

            class _LargeInteger(ctypes.Structure):
                _fields_ = [("QuadPart", ctypes.c_longlong)]

            class _IoCounters(ctypes.Structure):
                _fields_ = [("ReadOperationCount", ctypes.c_ulonglong),
                           ("WriteOperationCount", ctypes.c_ulonglong),
                           ("OtherOperationCount", ctypes.c_ulonglong),
                           ("ReadTransferCount", ctypes.c_ulonglong),
                           ("WriteTransferCount", ctypes.c_ulonglong),
                           ("OtherTransferCount", ctypes.c_ulonglong)]

            class _BasicLimits(ctypes.Structure):
                _fields_ = [("PerProcessUserTimeLimit", _LargeInteger),
                           ("PerJobUserTimeLimit", _LargeInteger),
                           ("LimitFlags", wintypes.DWORD),
                           ("MinimumWorkingSetSize", size_t),
                           ("MaximumWorkingSetSize", size_t),
                           ("ActiveProcessLimit", wintypes.DWORD),
                           ("Affinity", ulong_ptr),
                           ("PriorityClass", wintypes.DWORD),
                           ("SchedulingClass", wintypes.DWORD)]

            class _ExtendedLimits(ctypes.Structure):
                _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", _IoCounters),
                           ("ProcessMemoryLimit", size_t), ("JobMemoryLimit", size_t),
                           ("PeakProcessMemoryUsed", size_t), ("PeakJobMemoryUsed", size_t)]

            self._ctypes = ctypes
            self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
            self._kernel32.SetInformationJobObject.restype = wintypes.BOOL
            self._kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
            self._kernel32.CloseHandle.restype = wintypes.BOOL
            handle = self._kernel32.CreateJobObjectW(None, None)
            if not handle:
                raise OSError(ctypes.get_last_error(), "CreateJobObjectW failed")
            self.handle = handle
            limits = _ExtendedLimits()
            # KILL_ON_JOB_CLOSE gives timeouts and parent failure a process
            # tree boundary; the remaining limits are deliberately modest.
            limits.BasicLimitInformation.LimitFlags = (0x00002000 |  # KILL_ON_JOB_CLOSE
                                                        0x00000008 |  # ACTIVE_PROCESS
                                                        0x00000100 |  # PROCESS_MEMORY
                                                        0x00000002)   # PROCESS_TIME
            limits.BasicLimitInformation.ActiveProcessLimit = HOST_EXECUTION_PROCESSES
            limits.BasicLimitInformation.PerProcessUserTimeLimit.QuadPart = HOST_EXECUTION_SECONDS * 10_000_000
            limits.ProcessMemoryLimit = HOST_EXECUTION_MEMORY
            if not self._kernel32.SetInformationJobObject(handle, 9, ctypes.byref(limits),
                                                           ctypes.sizeof(limits)):
                error = ctypes.get_last_error()
                self.close()
                raise OSError(error, "SetInformationJobObject limits failed")
            # CPU rate controls are unavailable in a few older Windows
            # configurations; retain the other limits and say so in audit.
            class _CpuRate(ctypes.Structure):
                _fields_ = [("ControlFlags", wintypes.DWORD), ("CpuRate", wintypes.DWORD)]
            cpu = _CpuRate(0x1 | 0x4, 2_000)  # enable hard-cap, 20% of one CPU
            self.cpu_limited = bool(self._kernel32.SetInformationJobObject(
                handle, 15, ctypes.byref(cpu), ctypes.sizeof(cpu)))
            self.detail = "Windows Job Object limits applied" + (" (CPU hard-cap)" if self.cpu_limited else "")
        except Exception as exc:  # a failed control changes no safety label
            self.close()
            self.detail = f"Windows Job Object limits unavailable: {type(exc).__name__}: {exc}"

    def attach(self, process: subprocess.Popen[str]) -> bool:
        if self.handle is None:
            return False
        try:
            handle = getattr(process, "_handle", None)
            if handle is None or not self._kernel32.AssignProcessToJobObject(self.handle, handle):
                self.detail = "Windows Job Object could not attach to the process"
                return False
            return True
        except Exception as exc:  # noqa: BLE001
            self.detail = f"Windows Job Object attach failed: {type(exc).__name__}: {exc}"
            return False

    def close(self) -> None:
        if self.handle is not None:
            try:
                self._kernel32.CloseHandle(self.handle)
            except Exception:  # noqa: BLE001
                pass
            self.handle = None


def _helper(engagement: Engagement, kind: str, runner: Runner) -> Any:
    from .containers import Producer
    return Producer(f"librarian-{kind}-{engagement.id[-8:]}-{secrets.token_hex(3)}", runner,
                    kind=f"workbench-{kind}")


def _finished(producer: Any, capture: Any, what: str) -> None:
    """A helper's run, removed, and shown to have done its job; otherwise why not."""
    producer.dispose()
    if capture.exit_code != 0 or not producer.succeeded:
        why = capture.stderr.strip()[-300:] or producer.stop_reason or producer.state
        raise RuntimeError(f"{what}: {why}")


def _docker_stage(engagement: Engagement, repo_key: str, image: str, runner: Runner) -> tuple[str, str]:
    """Copy source bytes into a named Linux volume without bind-mounting NTFS."""
    source_volume, output_volume = _volume_name(engagement, "source"), _volume_name(engagement, "output")
    for volume in (source_volume, output_volume):
        made = runner(["docker", "volume", "create", volume], 60)
        if getattr(made, "returncode", 1) != 0:
            raise RuntimeError(f"could not create Docker volume {volume}: {str(getattr(made, 'stderr', ''))[-300:]}")
    archive, archive_hash = _download_archive(repo_key, engagement.pinned_revision)
    try:
        # The archive is checked before any container exists.
        _check_archive(archive)
        # Named volumes are root-owned when Docker creates them.  Initialise only
        # the disposable output volume before dropping the execution container to
        # its unprivileged uid; otherwise a correctly unprivileged run cannot
        # write any declared result at all.
        # provision: root with FOWNER alone, so chmod works on the volume root.
        provision = _helper(engagement, "provision", runner)
        done = provision.execute([*CONTAINED, "--cap-add", "FOWNER", *HELPER_LIMITS,
                                  "--read-only", "--user", "0:0",
                                  "--mount", f"type=volume,src={output_volume},dst=/output"],
                                 image, ["sh", "-c", "chmod 1777 /output"], deadline=90)
        _finished(provision, done, "could not initialise controlled Docker output volume")
        stage = _helper(engagement, "stage", runner)

        def copy_in() -> str:
            copied = runner(["docker", "cp", str(archive), f"{stage.name}:/tmp/source.tar.gz"], 90)
            if getattr(copied, "returncode", 1) != 0:
                return ("could not copy archive into Linux volume: " +
                        str(getattr(copied, "stderr", ""))[-300:])
            return ""

        # stage: root without capabilities; -o keeps tar from restoring owners.
        done = stage.execute([*CONTAINED, *HELPER_LIMITS, "--user", "0:0",
                              "--mount", f"type=volume,src={source_volume},dst=/source"],
                             image, ["sh", "-c",
                                     "tar -xzof /tmp/source.tar.gz -C /source --strip-components=1"],
                             deadline=300, before_start=copy_in)
        _finished(stage, done, "could not unpack pinned archive")
        return source_volume, archive_hash
    finally:
        with contextlib.suppress(OSError):
            archive.unlink()


def _archive_outputs(vault: Vault, engagement: Engagement, producer: Any) -> dict[str, Any]:
    """Export the output volume from the stopped execution container, checked before any
    of it is kept (REMED-04; MF-016).

    `docker cp <container>:/workspace/output -` streams a tar into a private quarantine,
    checked member by member before a byte is written (`containers.check_tar`). Only if
    every member passes, and the container is then removed, does it replace the
    engagement's folder. Otherwise nothing is kept: a link, device, unsafe name or a
    limit names why, and what arrived stays in quarantine for a person."""
    from . import containers
    destination = vault.derived / "engagements" / engagement.id / "output"
    held = vault.librarian / "quarantine" / "engagements"
    quarantine = held / f"{engagement.id}-{secrets.token_hex(3)}"
    report = producer.export_to("/workspace/output", quarantine, max_bytes=MAX_OUTPUT_BYTES,
                                max_entries=MAX_OUTPUT_FILES, stream_with=_stream)
    producer.dispose()
    accepted = report["accepted"] and producer.state == "disposed"
    records: list[dict[str, Any]] = []
    kept_in = ""
    if accepted:
        # The volume is the record of every run's outputs; this folder mirrors it.
        containers.promote(quarantine, destination)
        records = [{"path": (destination / f["name"]).relative_to(vault.root).as_posix(),
                    "bytes": f["bytes"], "sha256": f["sha256"][:20]} for f in report["files"]]
    else:
        if quarantine.is_dir():
            kept_in = quarantine.relative_to(vault.root).as_posix()
        containers.prune(held)
    stopped = report["stopped"]
    if not accepted and not stopped:
        stopped = ("refused: " + "; ".join(report["rejected"][:3]) if report["rejected"] else
                   f"the container is {producer.state}")
    return {"artifacts": records, "export": {
        "complete": accepted, "files": len(report["files"]), "bytes": report["bytes"],
        "entries": report["entries"], "refused": report["rejected"][:50], "stopped": stopped,
        "quarantine": kept_in}}


def _docker_execute(vault: Vault, engagement: Engagement, command: list[str], image: str,
                    runner: Runner, keep_output: bool = True,
                    permission: str = "", cancel: Any = None) -> dict[str, Any]:
    """Run the command. Without `keep_output` (MF-015: `sandbox_output` not allowed) no
    output volume is mounted and nothing is exported: the run keeps what it prints."""
    repo = _repository(vault, engagement.source)
    source_volume, archive_hash = _docker_stage(engagement, repo["repo_key"], image, runner)
    output_volume = _volume_name(engagement, "output")
    producer = _helper(engagement, "engage", runner)
    output = ["--mount", f"type=volume,src={output_volume},dst=/workspace/output"] \
        if keep_output else []
    flags = [*CONTAINED, "--read-only", "--tmpfs", "/tmp:rw,size=128m", "--memory", "2g",
             "--cpus", "2", "--pids-limit", "128", "--user", "10001:10001",
             "--mount", f"type=volume,src={source_volume},dst=/workspace/source,readonly",
             *output, "--workdir", "/workspace"]
    try:
        capture = producer.execute(flags, image, command, deadline=900, cancel=cancel,
                                   io_limit=2 * MAX_OUTPUT_BYTES if keep_output else None)
        stderr = capture.stderr
        if producer.stop_reason == "deadline":
            stderr = (stderr + "\nstopped after 900s").lstrip("\n")
        elif producer.stop_reason:
            stderr = (stderr + f"\nstopped: {producer.stop_reason}").lstrip("\n")
        result = {"exit_code": capture.exit_code if capture.exit_code is not None else -1,
                  "stdout": capture.stdout[-8000:], "stderr": stderr[-8000:],
                  "archive_sha256": archive_hash, "source_volume": source_volume,
                  "output_volume": output_volume, "isolation_tier": "docker_isolated",
                  "output_bytes": capture.produced, "stopped": producer.stop_reason}
        if not keep_output:
            producer.dispose()
            result.update(artifacts=[], export={
                "complete": False, "files": 0, "bytes": 0, "refused": [],
                "stopped": f"no output was kept: writing it was not permitted ({permission})"})
        else:
            result.update(_archive_outputs(vault, engagement, producer))
    except BaseException:
        with contextlib.suppress(Exception):
            if producer.state not in ("disposed", "cleanup_unknown"):
                producer.stop("error")
                producer.settle()
                producer.dispose()
        raise
    result["execution"] = producer.record()
    result["succeeded"] = producer.succeeded and (not keep_output or result["export"]["complete"])
    return result


def _host_environment(workspace: Path, venv_path: Path) -> dict[str, str]:
    """A minimal environment with no inherited provider tokens or handles."""
    temporary = workspace / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    system_root = os.environ.get("SystemRoot") or os.environ.get("WINDIR") or ""
    system32 = str(Path(system_root) / "System32") if system_root else ""
    scripts = venv_path / ("Scripts" if os.name == "nt" else "bin")
    path_parts = [str(scripts), system32, system_root]
    return {"PATH": os.pathsep.join(part for part in path_parts if part),
            "SystemRoot": system_root, "WINDIR": system_root,
            "ComSpec": os.environ.get("ComSpec", ""),
            "TEMP": str(temporary), "TMP": str(temporary),
            "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONSAFEPATH": "1"}


def _prepare_host_venv(workspace: Path) -> tuple[Path, str]:
    path = workspace / "venv"
    try:
        venv.EnvBuilder(with_pip=False, clear=True, symlinks=False).create(str(path))
        return path, "ephemeral stdlib venv"
    except Exception as exc:  # an interpreter can still be explicitly selected below
        return path, f"venv unavailable: {type(exc).__name__}: {exc}"


def _isolated_python_command(command: list[str], venv_path: Path) -> tuple[list[str], bool]:
    """Use the ephemeral interpreter and -I when the requested command is Python."""
    if not command:
        return command, False
    first = str(command[0])
    python_names = {"python", "python.exe", Path(sys.executable).name.casefold(),
                    str(Path(sys.executable)).casefold()}
    if first.casefold() not in python_names:
        return list(command), False
    executable = venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not executable.is_file():
        executable = Path(sys.executable)
    args = [str(executable), *command[1:]]
    if "-I" not in args[1:] and "-i" not in args[1:]:
        args.insert(1, "-I")
    return args, True


def _host_execute(vault: Vault, engagement: Engagement, command: list[str]) -> dict[str, Any]:
    """Run an explicit pinned revision with deliberately non-isolated semantics.

    The controls here limit lifetime, process tree, memory, inherited secrets
    and workspace exposure.  They are useful damage reduction, not a network
    sandbox: the returned tier and warning always say that plainly.
    """
    workspace = Path(tempfile.mkdtemp(prefix="librarian-host-exec-"))
    archive: Path | None = None
    job: _WindowsJob | None = None
    started = time.monotonic()
    controls: dict[str, Any] = {"network_containment": False,
                                "process_timeout_seconds": HOST_EXECUTION_SECONDS,
                                "process_memory_bytes": HOST_EXECUTION_MEMORY,
                                "process_limit": HOST_EXECUTION_PROCESSES}
    try:
        acl_ok, acl_detail = _restricted_workspace(workspace)
        controls["workspace_acl"] = {"applied": acl_ok, "detail": acl_detail}
        repo = _repository(vault, engagement.source)
        archive, archive_hash = _download_archive(repo["repo_key"], engagement.pinned_revision)
        source = _extract_pinned_archive(archive, workspace / "source-archive")
        venv_path, venv_detail = _prepare_host_venv(workspace)
        controls["venv"] = venv_detail
        actual_command, isolated_python = _isolated_python_command(command, venv_path)
        controls["isolated_python"] = isolated_python
        env = _host_environment(workspace, venv_path)
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0
        process = subprocess.Popen(actual_command, cwd=source, env=env, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   close_fds=True, creationflags=flags)
        job = _WindowsJob()
        attached = job.attach(process)
        controls["job_object"] = {"attached": attached, "detail": job.detail,
                                  "cpu_limited": job.cpu_limited}
        from .sandbox import drain
        # Closing a successfully attached job kills the entire tree.
        stdout, stderr, timed_out, produced = drain(
            process, HOST_EXECUTION_SECONDS, job.close if attached else process.kill)
        code = -1 if timed_out else process.returncode
        if timed_out:
            stderr += f"\nstopped after {HOST_EXECUTION_SECONDS}s"
        return {"exit_code": code, "stdout": stdout[-8000:], "stderr": stderr[-8000:],
                "output_bytes": produced,
                "isolation_tier": "non_isolated_host_exec", "source_archive_sha256": archive_hash,
                "command": actual_command, "controls": controls,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "warning": "No network containment is claimed; loopback and network access may be possible."}
    except Exception as exc:  # preserve the audit/labelling even for setup failure
        return {"exit_code": -1, "stdout": "", "stderr": f"host execution setup failed: {type(exc).__name__}: {exc}",
                "isolation_tier": "non_isolated_host_exec", "controls": controls,
                "duration_ms": round((time.monotonic() - started) * 1000),
                "warning": "No network containment is claimed; loopback and network access may be possible."}
    finally:
        if job is not None:
            job.close()
        if archive is not None:
            with contextlib.suppress(OSError):
                archive.unlink()
        shutil.rmtree(workspace, ignore_errors=True)


def start(vault: Vault, engagement_id: str, *, choice: str, command: list[str] | None = None,
          image: str = "", confirm_non_isolated: bool = False, person_confirmed: bool = False,
          runner: Runner | None = None, ctx: Any = None) -> dict[str, Any]:
    store = EngagementStore(vault)
    engagement = store.get(engagement_id)
    if engagement.state not in ("proposed", "paused"):
        raise TypeError(f"engagement {engagement_id} is {engagement.state}, not startable")
    if choice == "inspect_only":
        engagement.state, engagement.isolation_tier = "inspected", "inspect_only"
        engagement.audit_trace.append({"at": now_iso(), "event": "inspect_only"})
        store.put(engagement, "inspect_only")
        return engagement.public()
    if not person_confirmed:
        raise Refusal("PERSON_CONFIRMS", "starting an execution engagement needs an explicit person confirmation")
    if not isinstance(command, list) or not command or not all(isinstance(part, str) and part for part in command):
        raise TypeError("execution needs a non-empty argv command list")
    if choice == "docker_isolated":
        from . import sandbox
        ok, detail = sandbox.docker_status(runner)
        if not ok:
            raise Refusal("EXECUTION_SANDBOX_ONLY", detail + "; choose inspect-only, retry Docker, or explicitly use non-isolated host execution")
        image = _require_image(image)
        # MF-015: the output volume has no disk cap while the run writes to it.
        keep, permission = sandbox.output_permission(
            ctx, f"the engagement's Docker output volume ({_volume_name(engagement, 'output')})",
            f"exported only after checks, at most {MAX_OUTPUT_FILES} files and "
            f"{MAX_OUTPUT_BYTES // (1024 * 1024)} MB")
        engagement.state, engagement.isolation_tier = "running", "docker_isolated"
        store.put(engagement, "started")
        result = _docker_execute(vault, engagement, command, image, runner or _run,
                                 keep_output=keep, permission=permission,
                                 cancel=(getattr(ctx, "extras", None) or {}).get("cancel"))
    elif choice == "non_isolated_host_exec":
        if not confirm_non_isolated:
            raise Refusal("EXECUTION_SANDBOX_ONLY", "host execution is non_isolated_host_exec; explicitly confirm its weaker guarantee")
        engagement.state, engagement.isolation_tier = "running", "non_isolated_host_exec"
        store.put(engagement, "started")
        result = _host_execute(vault, engagement, command)
    else:
        raise TypeError("choice is inspect_only, docker_isolated, or non_isolated_host_exec")
    run_id = f"run-{secrets.token_hex(6)}"
    engagement.run_ids.append(run_id)
    engagement.artifacts.extend(result.pop("artifacts", []))
    # MF-016: a Docker run is complete only once its container was shown stopped and
    # removed, and its output (if kept) passed the export whole.
    engagement.state = ("completed" if result.get("exit_code") == 0 and
                        result.pop("succeeded", True) else "paused")
    engagement.audit_trace.append({"at": now_iso(), "event": "run", "run_id": run_id,
                                   "choice": choice, "result": {k: v for k, v in result.items()
                                                                     if k not in ("stdout", "stderr")}})
    store.put(engagement, "run_finished")
    return {"engagement": engagement.public(), "run": run_id, **result}


def close(vault: Vault, engagement_id: str, *, application: str = "", outcome: str = "",
          force_reason: str = "") -> dict[str, Any]:
    store = EngagementStore(vault)
    engagement = store.get(engagement_id)
    if not force_reason and (not application.strip() or not outcome.strip()):
        raise Refusal("EXECUTION_SANDBOX_ONLY", "normal engagement close requires documented application and outcome; force close records a reason")
    engagement.application, engagement.outcome = application[:2000], outcome[:2000]
    engagement.close_reason = force_reason[:1000]
    engagement.state = "closed"
    engagement.audit_trace.append({"at": now_iso(), "event": "force_closed" if force_reason else "closed",
                                   "reason": force_reason[:1000]})
    store.put(engagement, "closed")
    return engagement.public()

