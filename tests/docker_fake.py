"""A scripted Docker for container-lifecycle tests (MF-016).

It answers each command the way the Docker command line would: create, start (attached),
stop, kill, wait, inspect, cp (in, and out as a tar stream), rm, stats, volume, info,
image inspect and build. A container's status moves as the real one's does, so a test can
check the order the app asks in, and script a container that will not stop, an inspection
that fails, or a removal that fails.
"""
from __future__ import annotations

import io
import subprocess
import tarfile
from contextlib import contextmanager
from types import SimpleNamespace


def answer(stdout: str = "", code: int = 0, stderr: str = "") -> SimpleNamespace:
    return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def tar_of(root: str, files: dict[str, bytes]) -> bytes:
    """A `docker cp <container>:/<root> -` stream: the folder, then its files."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w|") as bundle:
        top = tarfile.TarInfo(root)
        top.type = tarfile.DIRTYPE
        bundle.addfile(top)
        made = {root}
        for name, data in files.items():
            parts = name.split("/")
            for i in range(1, len(parts)):
                folder = "/".join([root, *parts[:i]])
                if folder not in made:
                    info = tarfile.TarInfo(folder)
                    info.type = tarfile.DIRTYPE
                    bundle.addfile(info)
                    made.add(folder)
            info = tarfile.TarInfo(f"{root}/{name}")
            info.size = len(data)
            bundle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


class Docker:
    """Docker answering by script.

    - `writes`: the files the run leaves in its exported folder;
    - `export`: raw tar bytes to stream instead;
    - `hang`: the attached start outlives its timeout;
    - `stubborn`: how many `docker stop`s it ignores;
    - `unkillable`: `docker kill` does not stop it either;
    - `inspect_fails`: every inspection errors;
    - `rm_fails`: every removal errors.
    """

    def __init__(self, *, running: bool = True, image: bool = True, stdout: str = "hello\n",
                 stderr: str = "", exit_code: int = 0, writes: dict[str, bytes] | None = None,
                 export: bytes | None = None, hang: bool = False, stubborn: int = 0,
                 unkillable: bool = False, inspect_fails: bool = False, rm_fails: bool = False,
                 create_fails: str = "", cp_in_fails: bool = False) -> None:
        self.calls: list[list[str]] = []
        self.running, self.image = running, image
        self.stdout, self.stderr, self.exit_code = stdout, stderr, exit_code
        self.writes, self.export = writes or {}, export
        self.hang, self.stubborn, self.unkillable = hang, stubborn, unkillable
        self.inspect_fails, self.rm_fails = inspect_fails, rm_fails
        self.create_fails, self.cp_in_fails = create_fails, cp_in_fails
        self.status: dict[str, str] = {}
        self.created: dict[str, list[str]] = {}

    # -- what was asked
    def verbs(self) -> list[str]:
        return [c[1] if c[1] != "image" else "image " + c[2] for c in self.calls if len(c) > 1]

    def create_args(self, index: int = -1) -> list[str]:
        return [c for c in self.calls if c[:2] == ["docker", "create"]][index]

    def count(self, verb: str) -> int:
        return sum(1 for c in self.calls if c[1:2] == [verb])

    # -- the command line
    def __call__(self, args: list[str], timeout: float) -> SimpleNamespace:
        self.calls.append(list(args))
        verb = args[1] if len(args) > 1 else ""
        if args[:2] == ["docker", "info"]:
            return answer("29.8.1", 0 if self.running else 1)
        if args[:3] == ["docker", "image", "inspect"]:
            return answer("sha256:x", 0 if self.image else 1)
        if verb == "build":
            self.image = True
            return answer()
        if verb == "create":
            name = args[args.index("--name") + 1]
            if self.create_fails:
                return answer(code=125, stderr=self.create_fails)
            self.created[name], self.status[name] = list(args), "created"
            return answer(name + "\n")
        name = args[-1]
        if verb == "start":
            self.status[name] = "running"
            if self.hang:
                raise subprocess.TimeoutExpired(args, timeout)
            self.status[name] = "exited"
            return answer(self.stdout, self.exit_code, self.stderr)
        if verb == "stop":
            if name not in self.status:
                return answer(code=1, stderr=f"Error response from daemon: No such container: {name}")
            if self.stubborn > 0:
                self.stubborn -= 1
            elif self.status[name] == "running":
                self.status[name] = "exited"
            return answer(name + "\n")
        if verb == "kill":
            if not self.unkillable and self.status.get(name) == "running":
                self.status[name] = "exited"
            return answer(name + "\n")
        if verb == "wait":
            return answer("137\n")
        if verb == "inspect":
            if self.inspect_fails:
                return answer(code=1, stderr="error during connect: the daemon did not answer")
            if name not in self.status:
                return answer(code=1, stderr=f"Error: No such container: {name}")
            status = self.status[name]
            code = self.exit_code if status == "exited" else 0
            return answer(f"{'true' if status == 'running' else 'false'} {status} {code} false\n")
        if verb == "rm":
            if self.rm_fails:
                return answer(code=1, stderr="Error response from daemon: removal is stuck")
            if name not in self.status:
                return answer(code=1, stderr=f"Error response from daemon: No such container: {name}")
            del self.status[name]
            return answer(name + "\n")
        if verb == "cp":                             # into a container (out is `stream`)
            return answer(code=1 if self.cp_in_fails else 0,
                          stderr="no space" if self.cp_in_fails else "")
        if verb == "stats":
            return answer("0B / 1.5MB\n")
        return answer()

    @contextmanager
    def stream(self, args: list[str], timeout: float):
        """`docker cp <container>:<path> -`, as the export reads it."""
        self.calls.append(list(args))
        root = args[2].rsplit("/", 1)[-1]
        yield io.BytesIO(self.export if self.export is not None else tar_of(root, self.writes))
