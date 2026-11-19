"""Stop one library's Core, run the relabel migration, start the Core again on core-693448d.
Library paths are passed whole, never built in a shell (2026-11-17: a quoting slip started a
stray Core twice)."""
import os, subprocess, sys

LIB = sys.argv[1]
assert os.path.isdir(os.path.join(LIB, ".librarian")), f"not a library: {LIB!r}"
SCRATCH = r"C:\Users\jakem\AppData\Local\Temp\claude\4770644ade8fbf0e\6a1b88d3-d1d5-4c02-b521-b86d3b97fd1c\scratchpad"
PY = r"D:\Librarian_V2\.venv\Scripts\python.exe"
SRC = os.path.join(SCRATCH, "core-693448d", "src")
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
frozen = dict(env, PYTHONPATH=SRC)


def run(args, e, timeout):
    out = subprocess.run(args, env=e, capture_output=True, text=True, timeout=timeout, cwd=r"D:\Librarian_V2")
    return (out.stdout + out.stderr).strip()


print("stop:", run([PY, "-m", "resource_librarian", "host", "stop", "--vault", LIB], env, 300)[-300:].replace("\n", " "), flush=True)
print(run([PY, os.path.join(SCRATCH, "relabel_md.py"), LIB, "--apply"], frozen, 3000), flush=True)
print("start:", run([PY, "-m", "resource_librarian", "host", "start", "--vault", LIB], frozen, 300)[-300:].replace("\n", " "), flush=True)
