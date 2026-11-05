"""MF-016 qualification on a real Docker: the sandbox's container lifecycle, end to end.

Run from the repository root with the project's venv:

    .venv/Scripts/python.exe -I reports/2026-11-05-evidence/mf016_docker_qualification.py OUT.json

Each case runs `sandbox.run` with the real Docker command line, in a throwaway vault, and
records what the run returned and what Docker shows afterwards. Cases:
- a benign run, whose exported files are compared with hashes computed here;
- a print flood;
- a deadline;
- a process that ignores SIGTERM;
- a disk flood, written with and without fsync;
- a hostile export (a symbolic link).
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from resource_librarian import containers, sandbox  # noqa: E402
from resource_librarian.init import init  # noqa: E402
from resource_librarian.vault import Vault  # noqa: E402

BENIGN = {"a.txt": b"alpha\n", "d/b.bin": bytes(range(256)) * 40, "d/e/c.csv": b"x,y\n1,2\n"}
CASES = {
    "benign": ("import os\n"
               "os.makedirs('/landing/d/e', exist_ok=True)\n"
               "open('/landing/a.txt','wb').write(b'alpha\\n')\n"
               "open('/landing/d/b.bin','wb').write(bytes(range(256)) * 40)\n"
               "open('/landing/d/e/c.csv','wb').write(b'x,y\\n1,2\\n')\n"
               "print('benign done')\n", 60),
    "print_flood": ("import sys\nblock = b'x' * 65536\n"
                    "while True:\n    sys.stdout.buffer.write(block)\n", 120),
    "deadline": ("import time\nprint('sleeping', flush=True)\ntime.sleep(600)\n", 5),
    "ignores_sigterm": ("import signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
                        "print('ignoring SIGTERM', flush=True)\ntime.sleep(600)\n", 5),
    "disk_flood_fsync": ("import os\nblock = b'z' * (1 << 20)\n"
                         "f = open('/landing/flood.bin', 'wb')\n"
                         "while True:\n    f.write(block); f.flush(); os.fsync(f.fileno())\n",
                         120),
    "disk_flood_cached": ("block = b'z' * (1 << 20)\nf = open('/landing/flood.bin', 'wb')\n"
                          "while True:\n    f.write(block)\n", 120),
    "hostile_link": ("import os\nopen('/landing/ok.txt','w').write('ok')\n"
                     "os.symlink('/etc/passwd', '/landing/passwd')\n", 60),
}


def docker(*args: str) -> str:
    done = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=120)
    return done.stdout.strip()


def main(out_path: str) -> int:
    results: dict[str, object] = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "python": sys.version.split()[0],
        "platform": platform.platform(),
        "docker": docker("version", "--format", "{{.Server.Version}} {{.Server.Os}}"),
        "storage_driver": docker("info", "--format", "{{.Driver}}"),
        "head": subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                               capture_output=True, text=True).stdout.strip(),
        "limits": {"stream_limit": containers.STREAM_LIMIT_BYTES,
                   "stream_tolerance": containers.STREAM_TOLERANCE_BYTES,
                   "read_block": containers.READ_BLOCK, "io_limit": sandbox.IO_LIMIT_BYTES,
                   "io_poll_seconds": containers.IO_POLL_SECONDS,
                   "stop_grace": containers.STOP_GRACE,
                   "landing_max_bytes": sandbox.LANDING_MAX_BYTES},
        "cases": {}}
    dangling_before = set(docker("volume", "ls", "-qf", "dangling=true").split())
    with tempfile.TemporaryDirectory(prefix="mf016-") as tmp:
        init(Path(tmp) / "vault", name="MF-016 qualification")
        vault = Vault(Path(tmp) / "vault")
        sandbox.ensure_image(vault)
        results["image"] = docker("image", "inspect", sandbox.IMAGE, "--format", "{{.Id}}")
        for case, (code, timeout) in CASES.items():
            started = time.monotonic()
            out = sandbox.run(vault, code, "python", by="person", timeout=timeout,
                              label=f"mf016-{case}")
            took = round(time.monotonic() - started, 2)
            left = docker("ps", "-a", "--filter", f"name={out['execution']['container']}",
                          "--format", "{{.Names}} {{.Status}}")
            row = {key: out[key] for key in ("exit_code", "timed_out", "stopped", "completed",
                                             "landing", "files", "notes")}
            row.update(seconds=took, execution=out["execution"], output=out["output"],
                       stdout_chars=len(out["stdout"]), stderr_tail=out["stderr"][-200:],
                       container_left=left)
            if case == "benign":
                landing = vault.root / out["landing"]
                row["hashes_match"] = all(
                    hashlib.sha256((landing / name).read_bytes()).hexdigest()[:16] ==
                    hashlib.sha256(data).hexdigest()[:16] for name, data in BENIGN.items())
                row["files_match"] = sorted(f["name"] for f in out["files"]) == sorted(BENIGN)
            results["cases"][case] = row
            print(f"{case:18} {took:7.2f}s stopped={out['stopped'] or '-':12} "
                  f"state={out['execution']['state']:16} completed={out['completed']} "
                  f"left={left or '-'}", flush=True)
    results["leftover_containers"] = docker("ps", "-a", "--filter", "label=librarian.producer",
                                            "--format", "{{.Names}}").split()
    results["new_dangling_volumes"] = sorted(
        set(docker("volume", "ls", "-qf", "dangling=true").split()) - dangling_before)
    Path(out_path).write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
