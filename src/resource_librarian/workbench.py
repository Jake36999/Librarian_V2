"""Source-bound workbench engagements.

An engagement makes executable work explicit: which catalogued repository and
pinned revision it concerns, why it is needed, the isolation tier, outputs,
and its close-out outcome.  It is intentionally a first-party Core feature,
not an arbitrary plugin runtime.
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
HOST_EXECUTION_SECONDS = 300
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
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


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


def _extract_pinned_archive(archive: Path, destination: Path) -> Path:
    """Extract one GitHub revision archive without accepting tar path tricks.

    Host execution is not isolated, but its source still has to be the exact
    reviewed revision.  Keeping extraction here rather than using a host
    shell command makes the archive path, byte cap and link handling
    auditable before an explicitly chosen command can run.
    """
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    root = ""
    with tarfile.open(archive, "r:gz") as bundle:
        members = bundle.getmembers()
        safe: list[tarfile.TarInfo] = []
        for member in members:
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


def _docker_stage(engagement: Engagement, repo_key: str, image: str, runner: Runner) -> tuple[str, str]:
    """Copy source bytes into a named Linux volume without bind-mounting NTFS."""
    source_volume, output_volume = _volume_name(engagement, "source"), _volume_name(engagement, "output")
    for volume in (source_volume, output_volume):
        made = runner(["docker", "volume", "create", volume], 60)
        if getattr(made, "returncode", 1) != 0:
            raise RuntimeError(f"could not create Docker volume {volume}: {str(getattr(made, 'stderr', ''))[-300:]}")
    # Named volumes are root-owned when Docker creates them.  Initialise only
    # the disposable output volume before dropping the execution container to
    # its unprivileged uid; otherwise a correctly unprivileged run cannot
    # write any declared result at all.
    output_init = runner(["docker", "run", "--rm", "--network", "none",
                          "--mount", f"type=volume,src={output_volume},dst=/output",
                          image, "sh", "-lc", "mkdir -p /output && chmod 1777 /output"], 90)
    if getattr(output_init, "returncode", 1) != 0:
        raise RuntimeError("could not initialise controlled Docker output volume: " +
                           str(getattr(output_init, "stderr", ""))[-300:])
    archive, archive_hash = _download_archive(repo_key, engagement.pinned_revision)
    container = f"librarian-stage-{engagement.id[-8:]}"
    try:
        made = runner(["docker", "create", "--name", container,
                       "--mount", f"type=volume,src={source_volume},dst=/source",
                       image, "sh", "-lc",
                       "mkdir -p /source && tar -xzf /tmp/source.tar.gz -C /source --strip-components=1"], 90)
        if getattr(made, "returncode", 1) != 0:
            raise RuntimeError(f"could not create source staging helper: {str(getattr(made, 'stderr', ''))[-300:]}")
        copied = runner(["docker", "cp", str(archive), f"{container}:/tmp/source.tar.gz"], 90)
        if getattr(copied, "returncode", 1) != 0:
            raise RuntimeError(f"could not copy archive into Linux volume: {str(getattr(copied, 'stderr', ''))[-300:]}")
        unpacked = runner(["docker", "start", "-a", container], 300)
        if getattr(unpacked, "returncode", 1) != 0:
            raise RuntimeError(f"could not unpack pinned archive: {str(getattr(unpacked, 'stderr', ''))[-300:]}")
        return source_volume, archive_hash
    finally:
        runner(["docker", "rm", "-f", container], 30)
        with contextlib.suppress(OSError):
            archive.unlink()


def _archive_outputs(vault: Vault, engagement: Engagement, image: str, runner: Runner) -> list[dict[str, Any]]:
    """Export a managed output volume back into a validated engagement record."""
    output_volume = _volume_name(engagement, "output")
    destination = vault.derived / "engagements" / engagement.id / "output"
    destination.mkdir(parents=True, exist_ok=True)
    container = f"librarian-output-{engagement.id[-8:]}"
    try:
        made = runner(["docker", "create", "--name", container,
                       "--mount", f"type=volume,src={output_volume},dst=/output,readonly", image,
                       "sh", "-lc", "true"], 60)
        if getattr(made, "returncode", 1) != 0:
            return []
        copied = runner(["docker", "cp", f"{container}:/output/.", str(destination)], 120)
        if getattr(copied, "returncode", 1) != 0:
            return []
    finally:
        runner(["docker", "rm", "-f", container], 30)
    records = []
    total = 0
    for path in sorted(destination.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        size = path.stat().st_size
        if total + size > MAX_OUTPUT_BYTES:
            path.unlink()
            continue
        total += size
        records.append({"path": path.relative_to(vault.root).as_posix(), "bytes": size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:20]})
    return records


def _docker_execute(vault: Vault, engagement: Engagement, command: list[str], image: str,
                    runner: Runner) -> dict[str, Any]:
    repo = _repository(vault, engagement.source)
    source_volume, archive_hash = _docker_stage(engagement, repo["repo_key"], image, runner)
    output_volume = _volume_name(engagement, "output")
    name = f"librarian-engage-{engagement.id[-8:]}"
    args = ["docker", "run", "--rm", "--name", name, "--network", "none", "--read-only",
            "--tmpfs", "/tmp:rw,size=128m", "--memory", "2g", "--cpus", "2", "--pids-limit", "128",
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--user", "10001:10001",
            "--mount", f"type=volume,src={source_volume},dst=/workspace/source,readonly",
            "--mount", f"type=volume,src={output_volume},dst=/workspace/output",
            "--workdir", "/workspace", image, *command]
    try:
        done = runner(args, 930)
        result = {"exit_code": int(getattr(done, "returncode", -1)),
                  "stdout": str(getattr(done, "stdout", ""))[-8000:],
                  "stderr": str(getattr(done, "stderr", ""))[-8000:], "archive_sha256": archive_hash,
                  "source_volume": source_volume, "output_volume": output_volume,
                  "isolation_tier": "docker_isolated"}
    except subprocess.TimeoutExpired:
        runner(["docker", "kill", name], 30)
        result = {"exit_code": -1, "stdout": "", "stderr": "stopped after 900s", "archive_sha256": archive_hash,
                  "source_volume": source_volume, "output_volume": output_volume,
                  "isolation_tier": "docker_isolated"}
    result["artifacts"] = _archive_outputs(vault, engagement, image, runner)
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
        process = subprocess.Popen(actual_command, cwd=source, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                   close_fds=True, creationflags=flags)
        job = _WindowsJob()
        attached = job.attach(process)
        controls["job_object"] = {"attached": attached, "detail": job.detail,
                                  "cpu_limited": job.cpu_limited}
        try:
            stdout, stderr = process.communicate(timeout=HOST_EXECUTION_SECONDS)
            code = process.returncode
        except subprocess.TimeoutExpired:
            # Closing a successfully attached job kills the entire tree.
            if attached:
                job.close()
            else:
                process.kill()
            stdout, stderr = process.communicate()
            code = -1
            stderr = (stderr or "") + f"\nstopped after {HOST_EXECUTION_SECONDS}s"
        return {"exit_code": code, "stdout": (stdout or "")[-8000:], "stderr": (stderr or "")[-8000:],
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
          runner: Runner | None = None) -> dict[str, Any]:
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
        engagement.state, engagement.isolation_tier = "running", "docker_isolated"
        store.put(engagement, "started")
        result = _docker_execute(vault, engagement, command, image, runner or _run)
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
    engagement.state = "completed" if result.get("exit_code") == 0 else "paused"
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

