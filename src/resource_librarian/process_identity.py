"""Platform-aware process identity for liveness checks.

``os.kill(pid, 0)`` is not an existence test on Windows: CPython opens a
handle to the process, and a process that has exited while any handle to it
is still open (a parent's ``Popen`` object, an attached pipe, a debugger)
still reports as alive, so a Host draining on stop waits its full window for
a Core that is already gone.  A non-zero signal argument is worse there: it
terminates the process instead of probing it.  This module is the one place
that asks the operating system instead, and pairs the answer with the exact
process start identity persisted in connection and lease records, so a
recycled PID is never mistaken for the original Core.

The identity is opaque and compared for equality, never within a tolerance:
the raw creation FILETIME on Windows (100 ns), and the boot id with the
start-time clock ticks on Linux (/proc's wall-clock ``btime`` can shift by a
second, which is why a converted timestamp could not be compared exactly).
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any

_ERROR_ACCESS_DENIED = 5
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259


class _FILETIME(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


_kernel32: Any = None


def _windows_library() -> Any:
    """kernel32 bound once, with handle-sized prototypes.

    The declarations matter: a default ``c_int`` restype truncates a 64-bit
    HANDLE, and a truncated handle can name a *different* process's object.
    """
    global _kernel32
    if _kernel32 is None:
        library = ctypes.WinDLL("kernel32", use_last_error=True)
        library.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
        library.OpenProcess.restype = ctypes.c_void_p
        library.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
        library.GetExitCodeProcess.restype = ctypes.c_int
        library.GetProcessTimes.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(_FILETIME)] * 4
        library.GetProcessTimes.restype = ctypes.c_int
        library.CloseHandle.argtypes = [ctypes.c_void_p]
        library.CloseHandle.restype = ctypes.c_int
        _kernel32 = library
    return _kernel32


def _windows_start(pid: int) -> str | None:
    try:
        library = _windows_library()
        handle = library.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            creation, exit_time, kernel, user = (_FILETIME() for _ in range(4))
            if not library.GetProcessTimes(handle, ctypes.byref(creation), ctypes.byref(exit_time),
                                           ctypes.byref(kernel), ctypes.byref(user)):
                return None
            return f"win:{(creation.high << 32) | creation.low}"
        finally:
            library.CloseHandle(handle)
    except Exception:
        return None


def _linux_start(pid: int) -> str | None:
    """The boot this process started in, and its start time in clock ticks."""
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        # comm (field 2) is parenthesised and may itself contain spaces or
        # parentheses, so the remaining fields start after the *last* ")".
        ticks = int(stat[stat.rfind(")") + 1:].split()[19])  # starttime, field 22
        boot = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
        return f"linux:{boot}:{ticks}" if boot else None
    except (OSError, ValueError, IndexError):
        return None


def process_start(pid: int) -> str | None:
    """The process's exact start identity, or None when it cannot be
    determined (an unsupported platform, a dead PID, or any failure)."""
    if pid <= 0:
        return None
    try:
        if os.name == "nt":
            return _windows_start(pid)
        if Path("/proc/self/stat").is_file():
            return _linux_start(pid)
        return None
    except Exception:
        return None


def _windows_alive(pid: int) -> bool:
    library = _windows_library()
    handle = library.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # ERROR_ACCESS_DENIED: the process exists but cannot be queried.
        # Claiming it stopped would authorise an unsafe takeover.
        return ctypes.get_last_error() == _ERROR_ACCESS_DENIED
    try:
        code = ctypes.c_uint32()
        if not library.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True  # cannot prove it stopped
        return code.value == _STILL_ACTIVE
    finally:
        library.CloseHandle(handle)


def _posix_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)  # signal 0 is a real existence test on POSIX
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def is_alive(pid: int, start: str | None = None) -> bool:
    """Liveness, optionally pinned to the process that wrote a record.

    ``start`` is the start identity the record's author persisted.  When it
    is available and this PID's identity differs at all, the PID was reused
    by another process and the record's owner is gone.
    """
    if pid <= 0:
        return False
    # Our own PID is alive, but a record carrying it may have been written by
    # an earlier process whose PID was recycled to us: the identity below
    # still decides whether the record's author is the running process.
    if pid != os.getpid():
        if os.name == "nt":
            if not _windows_alive(pid):
                return False
        elif not _posix_alive(pid):
            return False
    # A record from an older Core has no identity, and a malformed one is
    # treated the same way: absent, never as proof the process is gone.
    if isinstance(start, str) and start:
        actual = process_start(pid)
        if actual is not None and actual != start:
            return False
    return True


def current_identity() -> dict[str, Any]:
    """The current process's identity for records that must survive PID reuse."""
    return {"pid": os.getpid(), "process_start": process_start(os.getpid())}
