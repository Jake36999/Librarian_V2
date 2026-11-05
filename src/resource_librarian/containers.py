"""One container's life, from creation to disposal (MF-016; specification N-05).

Every container the app starts goes through `Producer`. That covers a sandbox run, a
claim's failing input, and a Workbench engagement and its helpers:

    preflight -> reserved -> created -> running -> stop_requested
     -> stopped_verified -> export_quarantine -> validated -> disposed
                               |                    |
                               +-> rejected --------+
    stop or inspect uncertainty -> cleanup_unknown (never a success, nothing promoted)

- **No `--rm`.** A container is created, then started attached. It is still there after
  it stops, so it can be inspected and its files exported from it. Docker keeps no copy
  of what it prints (`--log-driver none`); by default Docker writes that to a log file
  with no size limit. The attached stream read here is the only copy.
- **One stop.** Three things request a stop, once:
  - the run's deadline;
  - a cancelled turn;
  - output past its limit.
  The stop is `docker stop`, which gives STOP_GRACE seconds and then has Docker kill it.
  A run past an output or disk limit gets no grace: it is killed at once.
  Before anything is exported, the container is inspected. If it still runs, it is
  killed, waited on and inspected again. If it still cannot be shown stopped, the run
  ends `cleanup_unknown`.
- **What it prints is counted here.**
  - Each stream's received bytes are counted apart from the tail kept (CAPTURE_BYTES).
  - Past STREAM_LIMIT_BYTES a stop is requested.
  - Past the limit plus STREAM_TOLERANCE_BYTES this machine stops reading that stream and
    ends the attached client. A client that only stopped reading would hold up the
    container's stop. What it receives is held to limit + tolerance + one 64 KiB read,
    and the record says which streams were cut.
- **Disk writes are sampled, not contained.**
  - When an I/O limit is given, `docker stats` streams the container's block writes,
    about one reading a second (measured 2026-11-05).
  - Past the limit a stop is requested.
  - Writes still in the page cache are counted only when the kernel writes them back.
    The run's memory limit bounds that cache.
  - So the overshoot is measured and recorded, never promised. It is a best-effort
    monitor, not a quota (MF-015).
- **Export.**
  - Only a container verified stopped is exported. `docker cp <container>:<path> -`
    streams a tar into a private quarantine under `.librarian/quarantine/`.
  - Each member is checked before it is written. Accepted: regular files and folders
    only. Rejected:
    - absolute, drive, UNC or escaping paths;
    - names Windows would read differently: `:`, reserved characters, a trailing dot
      or space, device names;
    - links, devices, pipes and sparse files;
    - duplicate or case-colliding names;
    - depth, name or path length past their limits.
  - Directories count as entries. The byte and entry budget is checked before each
    write. Hashing happens while streaming, and a short stream is truncation.
  - Nothing is accepted unless the whole stream passes.
- **Removal follows the export's disposition.** `docker rm -v` comes after the export
  is validated or rejected. A validated export is moved to its destination only once
  the container is removed. A failed removal is reported as `cleanup_unknown`, never
  hidden behind a success.
- **Retention.** A rejected export stays in quarantine for a person to look at. Only
  the newest QUARANTINE_KEEP are kept, and the run's own record says where.
"""
from __future__ import annotations

import contextlib
import hashlib
import re
import shutil
import subprocess
import tarfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from typing import Any, Callable

from .vault import now_iso

Runner = Callable[[list[str], float], Any]

CAPTURE_BYTES = 64 * 1024
STREAM_LIMIT_BYTES = 8 * 1024 * 1024
STREAM_TOLERANCE_BYTES = 1024 * 1024
READ_BLOCK = 64 * 1024
STOP_GRACE = 2
EXIT_WAIT = 30
AFTER_STOP = 3            # seconds the attached client may take to leave after a stop
TICK = 0.1
IO_POLL_SECONDS = 2.0      # a poll that calls `docker stats --no-stream` itself
IO_READ_SECONDS = 0.25     # how often the streamed reading is looked at
EXPORT_SECONDS = 300
MAX_DEPTH = 16
MAX_NAME_BYTES = 255
MAX_PATH_CHARS = 400
QUARANTINE_KEEP = 20
LOG_FLAGS = ["--log-driver", "none"]
LIMIT_STOPS = ("output_limit", "io_limit")
REMOVE_SECONDS = 300       # removing a volume of several GB took 34 s (measured)
STATES = ("preflight", "reserved", "created", "running", "stop_requested",
          "stopped_verified", "export_quarantine", "validated", "rejected", "disposed",
          "cleanup_unknown")


def supervised(runner: Any) -> bool:
    """Whether `runner` is the real Docker command line, which can be attached to and
    streamed from. A stand-in (a test's) answers each command by itself."""
    return bool(getattr(runner, "supervised", False))


# ------------------------------------------------------------------ capture

@dataclass
class Capture:
    """What a container printed, as received here, and why it stopped."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    produced: dict[str, int] = field(default_factory=dict)
    retained: dict[str, int] = field(default_factory=dict)
    cut: list[str] = field(default_factory=list)
    stop: str = ""
    io: dict[str, Any] = field(default_factory=dict)
    limit: int = STREAM_LIMIT_BYTES
    tolerance: int = STREAM_TOLERANCE_BYTES

    def public(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "produced": self.produced, "retained": self.retained, "limit": self.limit,
            "tolerance": self.tolerance, "cut": self.cut,
            "overshoot": max([0, *(n - self.limit for n in self.produced.values())])}
        if self.io:
            out["io"] = self.io
        return out


def supervise(process: subprocess.Popen, *, deadline: float,
              request_stop: Callable[[str], Any], keep: int = CAPTURE_BYTES,
              limit: int = STREAM_LIMIT_BYTES, tolerance: int = STREAM_TOLERANCE_BYTES,
              cancel: Any = None, written: Callable[[], int | None] | None = None,
              io_limit: int | None = None, every: float = IO_POLL_SECONDS) -> Capture:
    """Read an attached process's two streams to the end, and request one stop.

    The stop is requested on the first of four things:
    - `deadline` seconds passing;
    - `cancel` being set;
    - a stream passing `limit`;
    - `written()` passing `io_limit`.
    `request_stop` runs on its own thread, so the streams keep being read while the
    container stops. The attached client is killed if it has not left AFTER_STOP seconds
    after the stop returned, or STOP_GRACE + EXIT_WAIT after the stop began.
    """
    reasons: list[str] = []
    lock = threading.Lock()
    finished = threading.Event()
    tails: dict[str, bytes] = {}
    totals: dict[str, int] = {}
    cut: list[str] = []

    def flag(reason: str) -> None:
        with lock:
            if not reasons:
                reasons.append(reason)

    def pump(name: str, pipe: Any) -> None:
        held, total = bytearray(), 0
        try:
            for block in iter(lambda: pipe.read1(READ_BLOCK), b""):
                total += len(block)
                held += block
                if len(held) > keep:
                    del held[:-keep]
                if total > limit:
                    flag("output_limit")
                if total >= limit + tolerance:
                    # Intake stops here. The attached client is ended too: a client that
                    # stops reading holds the container's stop until its own timeout
                    # (measured: 34 s against a 2 s grace).
                    cut.append(name)
                    with contextlib.suppress(OSError):
                        process.kill()
                    break
        except (OSError, ValueError):
            pass
        tails[name], totals[name] = bytes(held), total

    io: dict[str, Any] = {}
    if written is not None:
        io.update(limit=io_limit, every=every, samples=0, failed=0, written=0,
                  method="docker stats block I/O, sampled about once a second; not a quota")

    def poll() -> None:
        while not finished.wait(every):
            try:
                value = written()               # type: ignore[misc]
            except Exception:                   # noqa: BLE001
                value = None
            if value is None:
                io["failed"] += 1
                continue
            io["samples"] += 1
            io["written"] = max(io["written"], value)
            if io_limit is not None and value > io_limit:
                flag("io_limit")

    threads = [threading.Thread(target=pump, args=(name, pipe), daemon=True)
               for name, pipe in (("stdout", process.stdout), ("stderr", process.stderr))
               if pipe is not None]
    if written is not None:
        threads.append(threading.Thread(target=poll, daemon=True))
    for thread in threads:
        thread.start()
    started = time.monotonic()
    stopper: threading.Thread | None = None
    stop_began = stop_done = 0.0
    while process.poll() is None:
        now = time.monotonic()
        if not reasons:
            if now - started >= deadline:
                flag("deadline")
            elif cancel is not None and cancel.is_set():
                flag("cancelled")
        if reasons and stopper is None:
            stop_began = now
            stopper = threading.Thread(target=request_stop, args=(reasons[0],), daemon=True)
            stopper.start()
        if stopper is not None:
            if not stopper.is_alive() and not stop_done:
                stop_done = now
            if (stop_done and now - stop_done > AFTER_STOP) or \
                    now - stop_began > STOP_GRACE + EXIT_WAIT:
                process.kill()                  # the attached client; the container is
                break                           # inspected apart
        time.sleep(TICK)
    if reasons and stopper is None:
        # The client ended first (a cut stream ends it): the container still stops.
        stopper = threading.Thread(target=request_stop, args=(reasons[0],), daemon=True)
        stopper.start()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=EXIT_WAIT)
    finished.set()
    for thread in threads:
        thread.join(timeout=10)
    for pipe in (process.stdout, process.stderr):
        if pipe is not None:
            with contextlib.suppress(OSError):
                pipe.close()
    if stopper is not None:
        stopper.join(timeout=STOP_GRACE + EXIT_WAIT)
    if io and io_limit is not None:
        io["overshoot_at_least"] = max(0, io["written"] - io_limit)
    names = ("stdout", "stderr")
    return Capture(
        stdout=tails.get("stdout", b"").decode("utf-8", "replace"),
        stderr=tails.get("stderr", b"").decode("utf-8", "replace"),
        exit_code=process.returncode, stop=reasons[0] if reasons else "",
        produced={n: totals.get(n, 0) for n in names},
        retained={n: len(tails.get(n, b"")) for n in names},
        cut=sorted(cut), io=io, limit=limit, tolerance=tolerance)


WRITTEN = re.compile(r"/\s*([\d.]+)\s*([A-Za-z]+)")
UNITS = {"b": 1, "kb": 1000, "mb": 1000 ** 2, "gb": 1000 ** 3, "tb": 1000 ** 4,
         "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3, "tib": 1024 ** 4}


def written_in(text: str) -> int | None:
    """The bytes written, from `docker stats` BlockIO ("1.2kB / 41.9MB": read / written,
    three significant figures)."""
    match = WRITTEN.search(text)
    if not match or match.group(2).lower() not in UNITS:
        return None
    return int(float(match.group(1)) * UNITS[match.group(2).lower()])


def block_written(runner: Runner, name: str) -> int | None:
    """One `docker stats --no-stream` reading (about two seconds a call)."""
    done = runner(["docker", "stats", "--no-stream", "--format", "{{.BlockIO}}", name], 20)
    if getattr(done, "returncode", 1) != 0:
        return None
    return written_in(str(getattr(done, "stdout", "")))


class StatsWatch:
    """`docker stats` left running for one container: it prints a reading about once a
    second (measured 2026-11-05), so the latest is read here without a call of its own."""

    def __init__(self, name: str, command: list[str] | None = None) -> None:
        self.latest: int | None = None
        self.readings = 0
        self.process = subprocess.Popen(
            command or ["docker", "stats", "--format", "{{.BlockIO}}", name],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.thread = threading.Thread(target=self._read, daemon=True)
        self.thread.start()

    def _read(self) -> None:
        pipe = self.process.stdout
        try:
            for line in iter(lambda: pipe.readline(4096), b""):   # type: ignore[union-attr]
                value = written_in(line.decode("utf-8", "replace"))
                if value is not None:
                    self.latest, self.readings = value, self.readings + 1
        except (OSError, ValueError):
            pass

    def __call__(self) -> int | None:
        return self.latest

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self.process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            self.process.wait(timeout=10)
        self.thread.join(timeout=5)
        if self.process.stdout is not None:
            with contextlib.suppress(OSError):
                self.process.stdout.close()


# ------------------------------------------------------------------ export stream

class Piped:
    """A command's stdout, read as it is produced, and how the command ended."""

    def __init__(self, pipe: Any) -> None:
        self._pipe = pipe
        self.exit_code: int | None = None

    def read(self, size: int = -1) -> bytes:
        return self._pipe.read(size)


@contextlib.contextmanager
def stream(args: list[str], timeout: float):
    """A command's stdout as a binary stream, never held whole. The command is killed on
    leaving or after `timeout`; `exit_code` is set once it has ended."""
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    timer = threading.Timer(timeout, process.kill)
    timer.start()
    piped = Piped(process.stdout)
    try:
        yield piped
    finally:
        timer.cancel()
        if process.poll() is None:
            # Left before the end: whatever was not read is not an export.
            process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=EXIT_WAIT)
        piped.exit_code = process.returncode
        if process.stdout is not None:
            process.stdout.close()


# ------------------------------------------------------------------ the checked export

RESERVED = re.compile(r"^(con|prn|aux|nul|conin\$|conout\$|com[0-9¹²³]|"
                      r"lpt[0-9¹²³])(\..*)?$", re.IGNORECASE)
UNSAFE_CHARS = frozenset('<>:"|?*\\') | frozenset(chr(code) for code in range(32))


def _unsafe_part(part: str) -> str:
    if any(ch in UNSAFE_CHARS for ch in part):
        return "a character this machine cannot keep in a name (: \\ < > \" | ? * or control)"
    if part.endswith((".", " ")):
        return "a name ending in a dot or a space"
    if RESERVED.match(part):
        return "a name Windows reserves for a device"
    if len(part.encode("utf-8")) > MAX_NAME_BYTES:
        return f"a name over {MAX_NAME_BYTES} bytes"
    return ""


def _kind(member: tarfile.TarInfo) -> str:
    if member.issym():
        return "a symbolic link"
    if member.islnk():
        return "a hard link"
    if member.ischr() or member.isblk():
        return "a device"
    if member.isfifo():
        return "a pipe"
    if member.issparse():
        return "a sparse file"
    return f"not a regular file or folder (tar type {member.type!r})"


def check_tar(pipe: Any, quarantine: Path, *, root: str, max_bytes: int, max_entries: int,
              max_depth: int = MAX_DEPTH, max_path: int = MAX_PATH_CHARS) -> dict[str, Any]:
    """Unpack a `docker cp ... -` tar of the folder `root` into `quarantine`, checking each
    member before anything is written. Accepted only if every member passes."""
    quarantine.mkdir(parents=True, exist_ok=False)
    files: list[dict[str, Any]] = []
    rejected: list[str] = []
    seen: dict[str, str] = {}                # casefolded path -> "dir" or "file"
    total = entries = dirs = 0
    stopped = ""

    def refuse(rel: str, why: str) -> None:
        if len(rejected) < 50:
            rejected.append(f"{rel}: {why}")
        elif len(rejected) == 50:
            rejected.append("... more refused")

    try:
        with tarfile.open(fileobj=pipe, mode="r|") as bundle:
            for member in bundle:
                raw = member.name
                parts = [part for part in raw.split("/") if part not in ("", ".")]
                if raw.startswith("/") or parts[:1] != [root]:
                    refuse(raw, "a path outside the exported folder")
                    continue
                parts = parts[1:]
                if not parts:                   # the folder itself
                    if not member.isdir():
                        refuse(raw, "the exported folder is not a folder")
                    continue
                rel = "/".join(parts)
                if ".." in parts:
                    why = "a path outside the exported folder"
                elif len(parts) > max_depth:
                    why = f"deeper than {max_depth} folders"
                elif len(rel) > max_path:
                    why = f"a path over {max_path} characters"
                else:
                    why = next((w for w in map(_unsafe_part, parts) if w), "")
                kind = ""
                if not why:
                    if member.type == tarfile.DIRTYPE:
                        kind = "dir"
                    elif member.type in (tarfile.REGTYPE, tarfile.AREGTYPE) and \
                            not member.issparse():
                        kind = "file"
                    else:
                        why = _kind(member)
                key = rel.casefold()
                prefixes = ["/".join(parts[:i]).casefold() for i in range(1, len(parts))]
                if not why:
                    if key in seen and not (kind == "dir" and seen[key] == "dir"):
                        why = "a second entry with this name, or one differing only in case"
                    elif any(seen.get(prefix) == "file" for prefix in prefixes):
                        why = "inside something that is a file"
                if why:
                    refuse(rel, why)
                    continue
                if kind == "dir" and key in seen:
                    continue                    # a folder already made for its contents
                implicit = [prefix for prefix in prefixes if prefix not in seen]
                if entries + 1 + len(implicit) > max_entries:
                    stopped = f"more than {max_entries} entries (files and folders)"
                    break
                if kind == "file" and total + max(0, member.size) > max_bytes:
                    stopped = f"{rel} would take it past {max_bytes:,} bytes"
                    break
                for prefix in implicit:
                    seen[prefix] = "dir"
                dirs += len(implicit) + (kind == "dir")
                entries += len(implicit) + 1
                seen[key] = kind
                target = quarantine.joinpath(*parts)
                if kind == "dir":
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                total += max(0, member.size)
                if rejected:
                    continue                    # refused already: nothing more is written
                target.parent.mkdir(parents=True, exist_ok=True)
                source = bundle.extractfile(member)
                digest, got = hashlib.sha256(), 0
                with target.open("xb") as out:
                    while source is not None and got < member.size:
                        block = source.read(min(READ_BLOCK, member.size - got))
                        if not block:
                            break
                        out.write(block)
                        digest.update(block)
                        got += len(block)
                if got != member.size:
                    stopped = f"{rel}: the stream ended {member.size - got} bytes early"
                    break
                files.append({"name": rel, "bytes": got, "sha256": digest.hexdigest()})
    except (tarfile.TarError, OSError, EOFError) as exc:
        stopped = f"the export stream failed: {type(exc).__name__}: {exc}"
    return {"accepted": not rejected and not stopped, "files": files, "dirs": dirs,
            "entries": entries, "bytes": total, "rejected": rejected, "stopped": stopped}


def prune(folder: Path, keep: int = QUARANTINE_KEEP) -> list[str]:
    """Hold a quarantine folder to its newest `keep` exports; returns those removed."""
    if not folder.is_dir():
        return []
    held = sorted((p for p in folder.iterdir() if p.is_dir()),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    removed = []
    for old in held[keep:]:
        shutil.rmtree(old, ignore_errors=True)
        removed.append(old.name)
    return removed


# ------------------------------------------------------------------ the producer

class Producer:
    """One container, from `reserved` to `disposed` (or `cleanup_unknown`)."""

    def __init__(self, name: str, runner: Runner, *, kind: str) -> None:
        self.name, self.runner, self.kind = name, runner, kind
        self.live = supervised(runner)
        self.states: list[dict[str, Any]] = []
        self.stop_reason = ""
        self.exit_code: int | None = None
        self.oom_killed = False
        self.capture: Capture | None = None
        self.export: dict[str, Any] | None = None
        self.teardown: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._t0 = time.monotonic()
        self._set("reserved")

    # -- record
    @property
    def state(self) -> str:
        return self.states[-1]["state"]

    def _set(self, state: str, detail: str = "") -> None:
        self.states.append({"state": state, "at": now_iso(),
                            "t": round(time.monotonic() - self._t0, 2),
                            **({"detail": detail[-300:]} if detail else {})})

    def _call(self, args: list[str], timeout: float) -> Any:
        try:
            return self.runner(args, timeout)
        except Exception as exc:                # noqa: BLE001
            return SimpleNamespace(returncode=-1, stdout="", stderr=f"{type(exc).__name__}: {exc}")

    @property
    def verified(self) -> bool:
        return any(s["state"] == "stopped_verified" for s in self.states)

    @property
    def succeeded(self) -> bool:
        """Stopped, verified, and removed: the only ending a success label may follow."""
        return self.state == "disposed" and self.verified

    def record(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "execution_v": 2, "container": self.name, "state": self.state,
            "states": [s["state"] for s in self.states],
            "timeline": [[s["state"], s["t"]] for s in self.states], "stop": self.stop_reason,
            "exit_code": self.exit_code, "oom_killed": self.oom_killed,
            "teardown": self.teardown}
        detail = [s["detail"] for s in self.states if s.get("detail")]
        if detail:
            out["detail"] = detail[-3:]
        if self.capture is not None:
            out["capture"] = self.capture.public()
        return out

    # -- life
    def execute(self, flags: list[str], image: str, command: list[str], *, deadline: float,
                cancel: Any = None, io_limit: int | None = None, keep: int = CAPTURE_BYTES,
                limit: int = STREAM_LIMIT_BYTES, tolerance: int = STREAM_TOLERANCE_BYTES,
                before_start: Callable[[], str] | None = None) -> Capture:
        """Create, start attached, supervise, and verify the stop. Never raises for
        Docker's answers: they are in the capture and the record.

        `before_start` runs between create and start (a `docker cp` in, say); what it
        returns, if anything, is why the container is not started."""
        made = self._call(["docker", "create", "--name", self.name, *LOG_FLAGS,
                           "--label", f"librarian.producer={self.kind}", *flags, image,
                           *command], 120)
        if getattr(made, "returncode", 1) != 0:
            why = "could not create the container: " + str(getattr(made, "stderr", "")).strip()
            self.capture = Capture(stderr=str(getattr(made, "stderr", ""))[-keep:],
                                   exit_code=getattr(made, "returncode", -1))
            if "already in use" in why:
                # The name belongs to another container, which is not this run's to remove.
                self.teardown = {"removed": True, "detail": "never created: the name is in use"}
                self._set("disposed", why)
                return self.capture
            # A failed create may still have left one (a timeout): make sure there is none.
            gone = self._call(["docker", "rm", "-f", "-v", self.name], 60)
            err = str(getattr(gone, "stderr", "")).strip()
            removed = getattr(gone, "returncode", 1) == 0 or "no such container" in err.lower()
            self.teardown = {"removed": removed, **({"detail": err[-300:]} if not removed else {})}
            self._set("disposed" if removed else "cleanup_unknown", why)
            return self.capture
        self._set("created")
        refused = before_start() if before_start is not None else ""
        if refused:
            capture = Capture(stderr=refused[-keep:])
        elif cancel is not None and cancel.is_set():
            self.stop("cancelled")
            capture = Capture(stop="cancelled")
        else:
            self._set("running")
            capture = self._attach(deadline, keep=keep, limit=limit, tolerance=tolerance,
                                   cancel=cancel, io_limit=io_limit)
        self.capture = capture
        self.settle()
        capture.stop = self.stop_reason
        if self.exit_code is not None:
            capture.exit_code = self.exit_code
        return capture

    def _attach(self, deadline: float, **limits: Any) -> Capture:
        args = ["docker", "start", "-a", self.name]
        if self.live:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            io_limit = limits.pop("io_limit")
            watch = StatsWatch(self.name) if io_limit is not None else None
            try:
                capture = supervise(process, deadline=deadline, request_stop=self.stop,
                                    written=watch, io_limit=io_limit, every=IO_READ_SECONDS,
                                    **limits)
            finally:
                if watch is not None:
                    watch.close()
            if watch is not None:
                capture.io["docker_readings"] = watch.readings
            return capture
        keep = limits["keep"]
        try:
            done = self.runner(args, deadline + EXIT_WAIT)
        except subprocess.TimeoutExpired:
            self.stop("deadline")
            return Capture(stop="deadline")
        out, err = str(getattr(done, "stdout", "")), str(getattr(done, "stderr", ""))
        produced = getattr(done, "produced", None) or {"stdout": len(out.encode()),
                                                       "stderr": len(err.encode())}
        return Capture(stdout=out[-keep:], stderr=err[-keep:],
                       exit_code=getattr(done, "returncode", -1), produced=dict(produced),
                       retained={"stdout": len(out[-keep:].encode()),
                                 "stderr": len(err[-keep:].encode())},
                       limit=limits["limit"], tolerance=limits["tolerance"])

    def stop(self, reason: str) -> None:
        """Request the container's stop, once; later requests do nothing."""
        with self._lock:
            if self.stop_reason:
                return
            self.stop_reason = reason
        self._set("stop_requested", reason)
        # A run past an output or disk limit gets no grace: each second of one is more
        # of what the limit was for (measured: about 0.3-1.4 GB a second to disk here).
        grace = 0 if reason in LIMIT_STOPS else STOP_GRACE
        self._call(["docker", "stop", "-t", str(grace), self.name], grace + EXIT_WAIT)

    def inspect(self) -> tuple[str, str]:
        """("stopped" | "running" | "gone" | "unknown", detail)."""
        done = self._call(["docker", "inspect", "--type", "container", "--format",
                           "{{.State.Running}} {{.State.Status}} {{.State.ExitCode}} "
                           "{{.State.OOMKilled}}", self.name], 30)
        if getattr(done, "returncode", 1) != 0:
            err = str(getattr(done, "stderr", "")).strip()
            return ("gone" if "no such" in err.lower() else "unknown"), err
        parts = str(getattr(done, "stdout", "")).split()
        if len(parts) < 3 or parts[0] not in ("true", "false"):
            return "unknown", f"an unreadable inspection: {' '.join(parts)[:80]!r}"
        if parts[0] == "false" and parts[1] in ("exited", "created", "dead"):
            if parts[1] != "created":           # never started: it has no exit code
                with contextlib.suppress(ValueError):
                    self.exit_code = int(parts[2])
            self.oom_killed = parts[3:4] == ["true"]
            return "stopped", parts[1]
        return "running", parts[1]

    def settle(self) -> bool:
        """Show the whole container stopped before anything is taken from it: look, then
        stop, then kill and wait, looking again after each."""
        detail = ""
        for escalate in ("", "stop", "kill"):
            if escalate == "stop":
                self.stop(self.stop_reason or "still running after its output closed")
            elif escalate == "kill":
                self._call(["docker", "kill", self.name], 30)
                self._call(["docker", "wait", self.name], 30)
            seen, detail = self.inspect()
            if seen == "stopped":
                self._set("stopped_verified")
                return True
            if seen == "gone":
                detail = "the container was gone before it could be shown stopped"
                break
        self._set("cleanup_unknown", detail or "the container could not be shown stopped")
        return False

    def export_to(self, path: str, quarantine: Path, *, max_bytes: int, max_entries: int,
                  stream_with: Callable[..., Any] | None = None) -> dict[str, Any]:
        """Stream `path` out of the stopped container into `quarantine`, checked."""
        if self.state != "stopped_verified":
            self.export = {"accepted": False, "files": [], "dirs": 0, "entries": 0,
                           "bytes": 0, "rejected": [],
                           "stopped": f"not exported: the container is {self.state}"}
            return self.export
        opener = stream_with or (stream if self.live else getattr(self.runner, "stream", None))
        self._set("export_quarantine")
        root = PurePosixPath(path).name
        if opener is None:
            report = {"accepted": False, "files": [], "dirs": 0, "entries": 0, "bytes": 0,
                      "rejected": [], "stopped": "no way to stream the export"}
        else:
            with opener(["docker", "cp", f"{self.name}:{path}", "-"], EXPORT_SECONDS) as pipe:
                report = check_tar(pipe, quarantine, root=root, max_bytes=max_bytes,
                                   max_entries=max_entries)
            code = getattr(pipe, "exit_code", 0)
            if report["accepted"] and code not in (0, None):
                report["accepted"] = False
                report["stopped"] = (f"the export ended with code {code}: what arrived may "
                                     f"not be all of it")
        self._set("validated" if report["accepted"] else "rejected",
                  "" if report["accepted"] else (report["stopped"] or
                                                 "; ".join(report["rejected"][:3])))
        self.export = report
        return report

    def dispose(self) -> bool:
        """Remove the container (and its anonymous volumes). After an uncertain stop the
        removal is forced, and the run stays `cleanup_unknown` whatever it says. Once
        removed, it stays removed: a second call asks nothing."""
        if self.state == "disposed":
            return True
        uncertain = self.state == "cleanup_unknown"
        done = self._call(["docker", "rm", "-v", *(["-f"] if uncertain else []), self.name],
                          REMOVE_SECONDS)
        err = str(getattr(done, "stderr", "")).strip()
        removed = getattr(done, "returncode", 1) == 0 or "no such container" in err.lower()
        if not removed and self.inspect()[0] == "gone":
            removed = True                      # the answer was lost, not the removal
        self.teardown = {"removed": removed, **({"detail": err[-300:]} if not removed else {})}
        if uncertain:
            return False
        if removed:
            self._set("disposed")
        else:
            self._set("cleanup_unknown", f"the stopped container could not be removed: {err}")
        return removed


def promote(quarantine: Path, destination: Path) -> None:
    """Move a validated export from quarantine to where it is kept."""
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(quarantine), str(destination))
