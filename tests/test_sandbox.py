"""The sandbox (owner, 2026-10-01): a fresh air-gapped container per run, writing only to its
own landing pad; the agent runs code it wrote, a person runs a script file."""
from types import SimpleNamespace

import pytest

from resource_librarian import sandbox
from resource_librarian.broker import Broker
from resource_librarian.registry import REGISTRY, Context

from conftest import write_note
from test_app import served  # noqa: F401  (fixture)


class FakeDocker:
    """Docker answering by script: `writes` is what the run leaves on its pad."""

    def __init__(self, running=True, image=True, writes=None, stdout="hello\n"):
        self.calls, self.running, self.image = [], running, image
        self.writes, self.stdout = writes or {}, stdout

    def __call__(self, args, timeout):
        self.calls.append(args)
        if args[:2] == ["docker", "info"]:
            return SimpleNamespace(returncode=0 if self.running else 1, stdout="29.4.3", stderr="")
        if args[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(returncode=0 if self.image else 1, stdout="sha256:x", stderr="")
        if args[:2] == ["docker", "build"]:
            self.image = True
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        landing = next(a for a in args if a.endswith("target=/landing")).split(",")[1][7:]
        from pathlib import Path
        for name, data in self.writes.items():
            (Path(landing) / name).write_bytes(data)
        return SimpleNamespace(returncode=0, stdout=self.stdout, stderr="")


def test_each_run_is_air_gapped_and_writes_only_to_its_pad(vault):
    write_note(vault.root, "Notes/data.md", "type: note", "1,2,3")
    docker = FakeDocker(writes={"out.txt": b"6\n"})
    out = sandbox.run(vault, "print(sum([1, 2, 3]))", "python", by="agent",
                      inputs=["Notes/data.md"], runner=docker)
    run = docker.calls[-1]
    for flag in (["--network", "none"], ["--read-only"], ["--cap-drop", "ALL"],
                 ["--user", "10001:10001"], ["--rm"]):
        assert any(run[i:i + len(flag)] == flag for i in range(len(run))), flag
    mounts = [a for a in run if a.startswith("type=bind")]
    assert sum(1 for m in mounts if not m.endswith(",readonly")) == 1          # the pad only
    assert any(m.endswith("target=/landing") for m in mounts)
    assert any("target=/inputs,readonly" in m for m in mounts)
    assert not [a for a in run if "KEY" in a or "TOKEN" in a]                 # no credentials
    assert run[-4:] == [sandbox.IMAGE, "python", "-I", "/job/main.py"]
    assert out["stdout"] == "hello\n" and out["files"][0]["name"] == "out.txt"
    assert (vault.root / out["landing"] / "out.txt").read_bytes() == b"6\n"
    assert sandbox.read_landed(vault, out["run"], "out.txt")["text"] == "6\n"


def test_the_pad_is_held_to_its_limits(vault, monkeypatch):
    monkeypatch.setattr(sandbox, "LANDING_MAX_BYTES", 10)
    out = sandbox.run(vault, "x", "python", by="agent",
                      runner=FakeDocker(writes={"a.txt": b"12345", "b.bin": b"x" * 50}))
    assert [f["name"] for f in out["files"]] == ["a.txt"]
    assert any("b.bin" in n and "limit" in n for n in out["notes"])


def test_nothing_on_the_pad_is_read_as_anything_but_text(vault):
    out = sandbox.run(vault, "x", "python", by="agent",
                      runner=FakeDocker(writes={"blob": b"\x00\x01binary"}))
    with pytest.raises(TypeError, match="binary"):
        sandbox.read_landed(vault, out["run"], "blob")
    with pytest.raises(TypeError):
        sandbox.read_landed(vault, out["run"], "../../config.toml")


def test_no_docker_no_run_and_the_image_is_built_once(vault):
    with pytest.raises(Exception) as caught:
        sandbox.run(vault, "x", "python", by="agent", runner=FakeDocker(running=False))
    assert getattr(caught.value, "code", "") == "EXECUTION_SANDBOX_ONLY"
    docker = FakeDocker(image=False)
    sandbox.run(vault, "x", "python", by="agent", runner=docker)
    sandbox.run(vault, "y", "python", by="agent", runner=docker)
    assert sum(1 for c in docker.calls if c[:2] == ["docker", "build"]) == 1
    assert "useradd" in (vault.librarian / "sandbox" / "image" / "Dockerfile").read_text()


def test_the_agent_is_asked_and_plan_mode_never_runs(vault, monkeypatch):
    monkeypatch.setattr(sandbox, "_run", FakeDocker())
    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (True, "fake"))
    monkeypatch.setattr(sandbox, "ensure_image", lambda v, runner=None: sandbox.IMAGE)
    planning = Context(tier="contribute", vault=vault, extras={"broker": Broker("plan")})
    out = REGISTRY.call("sandbox_run", {"code": "print(1)"}, planning)
    assert out["refused"] == "PERMISSION_DENIED"
    auto = Context(tier="contribute", vault=vault, extras={"broker": Broker("auto")})
    assert REGISTRY.call("sandbox_run", {"code": "print(1)"}, auto)["exit_code"] == 0
    # a person's run of a script file: only a script, and only a person
    write_note(vault.root, "Notes/plan.md", "type: note", "not a script")
    (vault.root / "Notes" / "go.py").write_text("print('go')", encoding="utf-8")
    assert REGISTRY.call("sandbox_run_file", {"path": "Notes/go.py"}, auto)["refused"] == \
        "TIER_REFUSED"
    person = Context(tier="curate", vault=vault)
    assert REGISTRY.call("sandbox_run_file", {"path": "Notes/plan.md"}, person)["error"] == \
        "invalid_arguments"
    assert REGISTRY.call("sandbox_run_file", {"path": "Notes/go.py"}, person)["exit_code"] == 0


def test_the_pane_lists_and_shows_scripts_as_code(served):
    app, client, _ = served
    (app.vault.root / "Notes").mkdir(exist_ok=True)
    (app.vault.root / "Notes" / "tally.py").write_text("print(2 + 2)\n", encoding="utf-8")
    listing = client.get("/api/files?dir=Notes")[1]
    script = next(e for e in listing["entries"] if e["name"] == "tally.py")
    assert script["script"] is True
    shown = client.get("/api/file?path=Notes/tally.py")[1]
    assert shown["script"] == "python" and shown["text"] == "print(2 + 2)\n"
