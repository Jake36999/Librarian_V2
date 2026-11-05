"""The sandbox (owner, 2026-10-01): a fresh air-gapped container per run, writing only to its
own landing pad; the agent runs code it wrote, a person runs a script file."""
from types import SimpleNamespace

import pytest

from resource_librarian import sandbox
from resource_librarian.broker import Broker
from resource_librarian.registry import REGISTRY, Context

from conftest import write_note
from docker_fake import Docker as FakeDocker
from test_app import served  # noqa: F401  (fixture)


def test_each_run_is_air_gapped_and_writes_only_to_its_pad(vault):
    write_note(vault.root, "Notes/data.md", "type: note", "1,2,3")
    docker = FakeDocker(writes={"out.txt": b"6\n"})
    out = sandbox.run(vault, "print(sum([1, 2, 3]))", "python", by="agent",
                      inputs=["Notes/data.md"], runner=docker)
    run = docker.create_args()
    for flag in (["--network", "none"], ["--read-only"], ["--cap-drop", "ALL"],
                 ["--user", "10001:10001"], ["--log-driver", "none"]):
        assert any(run[i:i + len(flag)] == flag for i in range(len(run))), flag
    assert "--rm" not in run                                  # MF-016: kept to be inspected
    binds = [a for a in run if a.startswith("type=bind")]
    assert all(m.endswith(",readonly") for m in binds)        # nothing here is writable
    assert "type=volume,target=/landing" in run               # the pad: its own volume
    assert any("target=/inputs,readonly" in m for m in binds)
    assert not [a for a in run if "KEY" in a or "TOKEN" in a]                 # no credentials
    assert run[-4:] == [sandbox.IMAGE, "python", "-I", "/job/main.py"]
    assert out["stdout"] == "hello\n" and out["files"][0]["name"] == "out.txt"
    assert (vault.root / out["landing"] / "out.txt").read_bytes() == b"6\n"
    assert sandbox.read_landed(vault, out["run"], "out.txt")["text"] == "6\n"
    assert out["completed"] is True and out["execution"]["state"] == "disposed"


def test_the_pad_is_kept_whole_or_not_at_all(vault, monkeypatch):
    monkeypatch.setattr(sandbox, "LANDING_MAX_BYTES", 10)
    out = sandbox.run(vault, "x", "python", by="agent",
                      runner=FakeDocker(writes={"a.txt": b"12345", "b.bin": b"x" * 50}))
    # MF-016: what passes is not kept apart from what does not (N-05: nothing is
    # accepted until all of it passes).
    assert out["files"] == [] and out["landing"] == "" and out["output"]["kept"] is False
    assert not (sandbox.landing_root(vault) / out["run"]).exists()
    assert "b.bin would take it past 10 bytes" in out["notes"][0]
    held = vault.root / out["output"]["quarantine"]
    assert (held / "a.txt").read_bytes() == b"12345" and not (held / "b.bin").exists()


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
    # MF-015: keeping a run's files is its own permission, asked even in Auto; set to
    # Allow here, as a person can set it.
    auto = Context(tier="contribute", vault=vault, extras={
        "broker": Broker("auto", tool_settings={"sandbox_output": "allow"})})
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


# -- MF-015 (owner, 2026-11-05): keeping a run's files is a write of its own --------

def gated(monkeypatch, docker):
    monkeypatch.setattr(sandbox, "_run", docker)
    monkeypatch.setattr(sandbox, "docker_status", lambda runner=None: (True, "fake"))
    monkeypatch.setattr(sandbox, "ensure_image", lambda v, runner=None: sandbox.IMAGE)


def answering(broker, **answers):
    """A person answering by tool name; records every request and its always_ask flag."""
    asked = []

    def listen(event):
        if event.get("type") == "permission_request":
            asked.append((event["tool"], bool(event.get("always_ask"))))
            broker.answer(event["id"], answers.get(event["tool"], "deny"))

    broker.subscribe(listen)
    return asked


def writable(args):
    return [a for a in args if a.startswith("type=volume") or
            (a.startswith("type=bind") and not a.endswith(",readonly"))]


def test_keeping_a_runs_files_is_asked_separately_even_in_auto(vault, monkeypatch):
    docker = FakeDocker(writes={"out.txt": b"6\n"})
    gated(monkeypatch, docker)
    broker = Broker("auto", timeout=5)
    asked = answering(broker, sandbox_output="allow_once")
    ctx = Context(tier="contribute", vault=vault, extras={"broker": broker})

    out = REGISTRY.call("sandbox_run", {"code": "print(6)"}, ctx)

    assert asked == [("sandbox_output", True)]       # the run itself was Auto's to allow
    assert out["output"]["kept"] is True and out["files"][0]["name"] == "out.txt"
    assert len(writable(docker.create_args())) == 1


def test_a_refused_output_still_runs_but_keeps_no_files(vault, monkeypatch):
    docker = FakeDocker(writes={"out.txt": b"6\n"})
    gated(monkeypatch, docker)
    broker = Broker("auto", timeout=5)
    answering(broker, sandbox_output="deny")
    ctx = Context(tier="contribute", vault=vault, extras={"broker": broker})

    out = REGISTRY.call("sandbox_run", {"code": "print(6)"}, ctx)

    run = docker.create_args()
    assert out["exit_code"] == 0 and out["stdout"] == "hello\n"     # it still ran
    assert writable(run) == [] and run[run.index("--workdir") + 1] == "/tmp"
    assert out["output"]["kept"] is False and out["files"] == [] and out["landing"] == ""
    assert "not permitted" in out["notes"][-1]
    assert not any(sandbox.landing_root(vault).glob("*"))


def test_allowing_the_run_for_the_session_does_not_allow_its_output(vault, monkeypatch):
    gated(monkeypatch, FakeDocker())
    broker = Broker("ask", timeout=5)
    asked = answering(broker, sandbox_run="allow_session", sandbox_output="allow_session")
    ctx = Context(tier="contribute", vault=vault, extras={"broker": broker})
    REGISTRY.call("open_session", {"purpose": "explore", "question": "q"}, ctx)

    REGISTRY.call("sandbox_run", {"code": "print(1)"}, ctx)
    REGISTRY.call("sandbox_run", {"code": "print(2)"}, ctx)

    assert [tool for tool, _ in asked] == ["sandbox_run", "sandbox_output", "sandbox_output"]

    planning = Context(tier="contribute", vault=vault, extras={"broker": Broker("plan")})
    plan_asked = answering(planning.extras["broker"])
    assert REGISTRY.call("sandbox_run", {"code": "print(1)"}, planning)["refused"] == \
        "PERMISSION_DENIED"
    assert plan_asked == []                           # never got as far as the output


# -- MF-016: stop the producer, show it stopped, export checked, then remove it ------

def order(docker):
    """The lifecycle verbs, in the order the app asked them."""
    return [v for v in docker.verbs() if v in ("create", "start", "stop", "kill", "wait",
                                               "inspect", "cp", "rm")]


def test_the_container_is_shown_stopped_before_export_and_removed_after(vault):
    docker = FakeDocker(writes={"out.txt": b"6\n"})
    out = sandbox.run(vault, "print(6)", "python", by="agent", runner=docker)
    assert order(docker) == ["create", "start", "inspect", "cp", "rm"]
    rm = next(c for c in docker.calls if c[1] == "rm")
    assert rm[:3] == ["docker", "rm", "-v"]                 # its anonymous pad goes with it
    assert out["execution"]["states"] == [
        "reserved", "created", "running", "stopped_verified", "export_quarantine",
        "validated", "disposed"]
    assert not docker.status                                # nothing left behind
    log = (vault.librarian / "sandbox" / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert '"state": "reserved"' in log[0] and '"state": "disposed"' in log[-1]


def test_a_run_past_its_deadline_is_stopped_once_then_shown_stopped(vault):
    docker = FakeDocker(hang=True, writes={"out.txt": b"partial"})
    out = sandbox.run(vault, "while True: pass", "python", by="agent", runner=docker,
                      timeout=5)
    assert out["timed_out"] is True and out["stopped"] == "deadline"
    assert out["completed"] is False and "stopped after 5s" in out["stderr"]
    assert order(docker) == ["create", "start", "stop", "inspect", "cp", "rm"]
    assert docker.count("stop") == 1


def test_a_container_that_ignores_its_stop_is_killed_and_looked_at_again(vault):
    docker = FakeDocker(hang=True, stubborn=1)
    out = sandbox.run(vault, "x", "python", by="agent", runner=docker)
    # One stop (it is idempotent), then kill and wait, then a verified stop.
    assert order(docker) == ["create", "start", "stop", "inspect", "inspect", "kill", "wait",
                             "inspect", "cp", "rm"]
    assert out["execution"]["state"] == "disposed" and docker.count("stop") == 1


@pytest.mark.parametrize("trouble", [dict(stubborn=99, unkillable=True), dict(inspect_fails=True)])
def test_a_container_not_shown_stopped_is_never_a_success_and_keeps_nothing(vault, trouble):
    docker = FakeDocker(hang=True, writes={"out.txt": b"6\n"}, **trouble)
    out = sandbox.run(vault, "x", "python", by="agent", runner=docker)
    assert out["execution"]["state"] == "cleanup_unknown" and out["completed"] is False
    assert "cp" not in order(docker)                         # nothing taken from it
    assert next(c for c in docker.calls if c[1] == "rm")[:4] == ["docker", "rm", "-v", "-f"]
    assert out["files"] == [] and out["landing"] == ""
    assert any("not a success" in note for note in out["notes"])


def test_a_failed_removal_is_said_and_nothing_is_promoted(vault):
    docker = FakeDocker(writes={"out.txt": b"6\n"}, rm_fails=True)
    out = sandbox.run(vault, "x", "python", by="agent", runner=docker)
    assert out["execution"]["state"] == "cleanup_unknown"
    assert out["execution"]["teardown"]["removed"] is False
    assert out["completed"] is False and out["files"] == [] and out["landing"] == ""
    held = vault.root / out["output"]["quarantine"]
    assert (held / "out.txt").read_bytes() == b"6\n"         # validated, held, not kept


@pytest.mark.parametrize("member", ["link", "hard", "device", "colon", "upper"])
def test_one_unsafe_member_refuses_the_whole_export(vault, member):
    import io
    import tarfile
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w|") as bundle:
        top = tarfile.TarInfo("landing")
        top.type = tarfile.DIRTYPE
        bundle.addfile(top)
        good = tarfile.TarInfo("landing/good.txt")
        good.size = 2
        bundle.addfile(good, io.BytesIO(b"ok"))
        bad = tarfile.TarInfo({"colon": "landing/a:stream", "upper": "landing/GOOD.txt"}.get(
            member, "landing/bad"))
        bad.type = {"link": tarfile.SYMTYPE, "hard": tarfile.LNKTYPE,
                    "device": tarfile.CHRTYPE}.get(member, tarfile.REGTYPE)
        bad.linkname = "landing/good.txt" if member in ("link", "hard") else ""
        bad.size = 1 if bad.type == tarfile.REGTYPE else 0
        bundle.addfile(bad, io.BytesIO(b"x") if bad.type == tarfile.REGTYPE else None)
    out = sandbox.run(vault, "x", "python", by="agent",
                      runner=FakeDocker(export=buffer.getvalue()))
    assert out["files"] == [] and out["output"]["kept"] is False
    assert out["output"]["export"]["accepted"] is False and out["output"]["export"]["refused"]
    assert out["completed"] is False                   # what it wrote was not kept whole


def test_a_cancelled_turn_stops_the_run(vault):
    import threading
    cancel = threading.Event()
    cancel.set()
    docker = FakeDocker()
    out = sandbox.run(vault, "x", "python", by="agent", runner=docker,
                      ctx=Context(tier="contribute", vault=vault, extras={"cancel": cancel}))
    assert out["stopped"] == "cancelled" and out["completed"] is False
    assert "start" not in order(docker) and "rm" in order(docker)
