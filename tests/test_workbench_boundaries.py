"""REMED-04, Workbench output and helper boundaries (Codex review W1): outputs are
held to size, count and type before they reach this machine, what a process
prints is held in memory to a bounded tail, and every helper container carries
the documented isolation policy."""
from __future__ import annotations

import contextlib
import io
import sys
import tarfile
from types import SimpleNamespace

import pytest

from resource_librarian import sandbox, workbench
from resource_librarian.workbench import CONTAINED, Engagement

from docker_fake import Docker

IMAGE = "example/image@sha256:" + "a" * 64


def tar_stream(*members: tuple[tarfile.TarInfo, bytes | None]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w|") as bundle:
        for info, data in members:
            bundle.addfile(info, io.BytesIO(data) if data is not None else None)
    return buffer.getvalue()


def entry(name: str, data: bytes = b"", kind: bytes = tarfile.REGTYPE,
          link: str = "") -> tuple[tarfile.TarInfo, bytes | None]:
    info = tarfile.TarInfo(name)
    info.type = kind
    info.linkname = link
    if kind == tarfile.REGTYPE:
        info.size = len(data)
        return info, data
    return info, None


@pytest.fixture
def export(vault, monkeypatch):
    """Export a given tar stream from a stopped execution container (MF-016), recording
    every Docker call."""
    docker = Docker()

    def go(stream: bytes, **script):
        for key, value in script.items():
            setattr(docker, key, value)

        @contextlib.contextmanager
        def fake(args, timeout):
            docker.calls.append(args)
            yield io.BytesIO(stream)

        monkeypatch.setattr(workbench, "_stream", fake)
        engagement = Engagement(id="eng-bounds", source="s", pinned_revision="abc")
        producer = workbench._helper(engagement, "engage", docker)
        producer.execute([], IMAGE, ["true"], deadline=60)
        out = workbench._archive_outputs(vault, engagement, producer)
        out["producer"] = producer
        return out, vault.derived / "engagements" / "eng-bounds" / "output"

    go.docker = docker
    return go


def test_benign_outputs_are_exported_with_their_records(export, vault):
    out, folder = export(tar_stream(entry("output/", kind=tarfile.DIRTYPE),
                                    entry("output/result.json", b'{"ok": true}'),
                                    entry("output/plots/", kind=tarfile.DIRTYPE),
                                    entry("output/plots/a.csv", b"x,y\n1,2\n")))
    assert out["export"]["complete"] and out["export"]["refused"] == []
    assert (folder / "result.json").read_bytes() == b'{"ok": true}'
    assert (folder / "plots" / "a.csv").is_file()
    assert [a["bytes"] for a in out["artifacts"]] == [12, 8]
    assert out["export"]["files"] == 2 and out["export"]["bytes"] == 20
    assert out["export"]["entries"] == 3                     # folders count as entries
    assert out["export"]["quarantine"] == ""                 # moved out, not held
    assert not any((vault.librarian / "quarantine" / "engagements").iterdir())


def test_an_oversized_output_refuses_the_export_before_it_is_written(export, monkeypatch,
                                                                    vault):
    monkeypatch.setattr(workbench, "MAX_OUTPUT_BYTES", 100)
    # The second file declares ten gigabytes; none of it is read or written.
    small, data = entry("output/small.txt", b"a" * 40)
    huge = tarfile.TarInfo("output/huge.bin")
    huge.size = 10 * 1024 ** 3
    stream = (small.tobuf(tarfile.GNU_FORMAT) + data.ljust(512, b"\0") +
              huge.tobuf(tarfile.GNU_FORMAT) + b"y" * 4096)
    out, folder = export(stream)
    assert not out["export"]["complete"] and "huge.bin" in out["export"]["stopped"]
    # MF-016: nothing is kept unless all of it passes; what arrived is held apart.
    assert not folder.exists() and out["artifacts"] == []
    held = vault.root / out["export"]["quarantine"]
    assert (held / "small.txt").is_file() and not (held / "huge.bin").exists()


def test_too_many_entries_refuses_the_export(export, monkeypatch):
    monkeypatch.setattr(workbench, "MAX_OUTPUT_FILES", 3)
    out, folder = export(tar_stream(*(entry(f"output/f{i}.txt", b"x") for i in range(10))))
    assert not out["export"]["complete"] and "more than 3 entries" in out["export"]["stopped"]
    assert not folder.exists()


def test_folders_count_against_the_entry_limit(export, monkeypatch):
    monkeypatch.setattr(workbench, "MAX_OUTPUT_FILES", 3)
    out, _ = export(tar_stream(*(entry(f"output/d{i}/", kind=tarfile.DIRTYPE)
                                 for i in range(5))))
    assert not out["export"]["complete"] and "more than 3 entries" in out["export"]["stopped"]


def test_links_devices_and_escaping_paths_are_refused_and_named(export, vault):
    out, folder = export(tar_stream(
        entry("output/keep.txt", b"kept"),
        entry("output/link", kind=tarfile.SYMTYPE, link="/etc/passwd"),
        entry("output/hard", kind=tarfile.LNKTYPE, link="output/keep.txt"),
        entry("output/orphan", kind=tarfile.LNKTYPE, link="/etc/shadow"),
        entry("output/fifo", kind=tarfile.FIFOTYPE),
        entry("output/device", kind=tarfile.CHRTYPE),
        entry("output/../../escaped.txt", b"out"),
        entry("/absolute.txt", b"out")))
    refused = " ".join(out["export"]["refused"])
    # MF-016: a hard link is refused too (N-05), and one refusal refuses the export.
    for name in ("link", "hard:", "orphan", "fifo", "device", "escaped.txt", "absolute.txt"):
        assert name in refused
    assert not out["export"]["complete"] and out["artifacts"] == [] and not folder.exists()
    assert not list(vault.derived.parent.rglob("escaped.txt"))
    assert not list(vault.root.rglob("absolute.txt"))


@pytest.mark.parametrize("name, why", [
    ("output/a:b.txt", "cannot keep in a name"),
    ("output/CON.txt", "reserves for a device"),
    ("output/trailing.", "ending in a dot"),
    ("output/" + "n" * 300, "over 255 bytes"),
    ("output/" + "/".join(["d"] * 20) + "/deep.txt", "deeper than 16"),
])
def test_names_this_machine_would_read_differently_are_refused(export, name, why):
    out, folder = export(tar_stream(entry(name, b"x")))
    assert not out["export"]["complete"] and why in " ".join(out["export"]["refused"])
    assert not folder.exists()


def test_names_differing_only_in_case_are_refused(export):
    out, folder = export(tar_stream(entry("output/Report.txt", b"a"),
                                    entry("output/report.TXT", b"b")))
    assert not out["export"]["complete"] and "only in case" in out["export"]["refused"][0]
    assert not folder.exists()


def test_a_truncated_or_broken_stream_is_refused_not_silently_short(export):
    info, data = entry("output/a.bin", b"z" * 2000)
    out, folder = export(info.tobuf(tarfile.GNU_FORMAT) + data[:700])
    assert not out["export"]["complete"] and out["export"]["stopped"]
    assert not folder.exists()
    out, _ = export(b"this is not a tar stream" * 40)
    assert not out["export"]["complete"] and "stream failed" in out["export"]["stopped"]
    assert out["artifacts"] == []


def test_the_export_folder_mirrors_the_volume_not_earlier_leftovers(export):
    _, folder = export(tar_stream(entry("output/old.txt", b"old")))
    out, folder = export(tar_stream(entry("output/new.txt", b"new")))
    assert [p.name for p in folder.iterdir()] == ["new.txt"]


def test_the_export_comes_from_the_stopped_container_which_is_then_removed(export):
    out, _ = export(tar_stream(entry("output/a.txt", b"a")))
    docker, producer = export.docker, out["producer"]
    verbs = [v for v in docker.verbs() if v in ("create", "start", "inspect", "cp", "rm")]
    assert verbs == ["create", "start", "inspect", "cp", "rm"]   # no separate export helper
    assert ["docker", "cp", f"{producer.name}:/workspace/output", "-"] in docker.calls
    assert producer.state == "disposed" and not docker.status


def test_a_container_not_shown_stopped_exports_nothing(export):
    out, folder = export(tar_stream(entry("output/a.txt", b"a")), inspect_fails=True)
    assert not out["export"]["complete"] and "cleanup_unknown" in out["export"]["stopped"]
    assert "cp" not in export.docker.verbs() and not folder.exists()


def test_a_failed_removal_keeps_the_validated_export_out_of_the_folder(export):
    out, folder = export(tar_stream(entry("output/a.txt", b"a")), rm_fails=True)
    assert not out["export"]["complete"] and out["producer"].state == "cleanup_unknown"
    assert not folder.exists() and out["export"]["quarantine"]


# --------------------------------------------------------------- helpers staging

def test_every_staging_helper_carries_the_isolation_policy(tmp_path, monkeypatch):
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.txt").write_text("a", encoding="utf-8")
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="repo-abc")
    monkeypatch.setattr(workbench, "_download_archive", lambda *_: (archive, "hash"))
    docker = Docker()

    engagement = Engagement(id="eng-stage", source="s", pinned_revision="abc")
    workbench._docker_stage(engagement, "example/test", IMAGE, docker)
    containers = [c for c in docker.calls if c[:2] in (["docker", "run"], ["docker", "create"])]
    assert len(containers) == 2 and not any(c[:2] == ["docker", "run"] for c in docker.calls)
    for args in containers:
        assert all(flag in args for flag in CONTAINED), args
        assert "--memory" in args and "--pids-limit" in args and "--rm" not in args
    provision, stage = containers
    assert provision[provision.index("--cap-add") + 1] == "FOWNER"
    assert "--read-only" in provision
    assert "--cap-add" not in stage and "-lc" not in stage
    assert "tar -xzof" in stage[-1]
    # The archive goes in after create and before start; both helpers are removed.
    verbs = [v for v in docker.verbs() if v in ("create", "cp", "start", "rm")]
    assert verbs == ["create", "start", "rm", "create", "cp", "start", "rm"]
    assert not docker.status


def test_an_archive_that_cannot_be_copied_in_is_never_started(tmp_path, monkeypatch):
    source = tmp_path / "src"
    source.mkdir()
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="repo-abc")
    monkeypatch.setattr(workbench, "_download_archive", lambda *_: (archive, "hash"))
    docker = Docker(cp_in_fails=True)
    with pytest.raises(RuntimeError, match="could not copy archive"):
        workbench._docker_stage(Engagement(id="eng-cp", source="s", pinned_revision="abc"),
                                "example/test", IMAGE, docker)
    assert sum(1 for c in docker.calls if c[1] == "start") == 1      # the provision only
    assert not docker.status


@pytest.mark.parametrize("hostile", ["link", "escape"])
def test_a_hostile_archive_is_refused_before_any_helper_sees_it(tmp_path, monkeypatch, hostile):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        if hostile == "link":
            info = tarfile.TarInfo("repo-abc/link")
            info.type, info.linkname = tarfile.SYMTYPE, "/etc/passwd"
            bundle.addfile(info)
        else:
            info = tarfile.TarInfo("repo-abc/../../escape.txt")
            info.size = 1
            bundle.addfile(info, io.BytesIO(b"x"))
    monkeypatch.setattr(workbench, "_download_archive", lambda *_: (archive, "hash"))
    calls: list[list[str]] = []

    def runner(args, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with pytest.raises(TypeError, match="revision archive"):
        workbench._docker_stage(Engagement(id="eng-bad", source="s", pinned_revision="abc"),
                                "example/test", IMAGE, runner)
    assert not any(c[:2] in (["docker", "create"], ["docker", "cp"], ["docker", "start"])
                   for c in calls)


# ------------------------------------------------------------ bounded capture

LOUD = [sys.executable, "-c",
        "import sys\nfor _ in range(80): sys.stdout.write('x' * 65536)\nsys.stdout.write('END')\n"
        "sys.stderr.write('e' * 200000)"]


def test_a_loud_process_is_held_to_a_bounded_tail(monkeypatch):
    done = sandbox.run_bounded(LOUD, 60)
    assert done.returncode == 0
    assert len(done.stdout) <= sandbox.CAPTURE_BYTES and done.stdout.endswith("END")
    assert len(done.stderr) <= sandbox.CAPTURE_BYTES
    assert done.produced == {"stdout": 80 * 65536 + 3, "stderr": 200000}


def test_a_bounded_run_that_overruns_is_killed_and_raises():
    with pytest.raises(sandbox.subprocess.TimeoutExpired):
        sandbox.run_bounded([sys.executable, "-c", "import time; time.sleep(30)"], 1)


def test_host_execution_output_is_bounded_and_measured(vault, tmp_path, monkeypatch):
    source = tmp_path / "src"
    source.mkdir()
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="repo-abc")
    monkeypatch.setattr(workbench, "_repository", lambda *_: {"repo_key": "example/test",
                                                               "surveyed_tree": "abc"})
    monkeypatch.setattr(workbench, "_download_archive", lambda *_: (archive, "hash"))
    engagement = Engagement(id="eng-loud", source="s", pinned_revision="abc")
    out = workbench._host_execute(vault, engagement, ["python", *LOUD[1:]])
    assert out["exit_code"] == 0, out["stderr"]
    assert out["stdout"].endswith("END") and len(out["stdout"]) <= 8000
    assert out["output_bytes"]["stdout"] == 80 * 65536 + 3
