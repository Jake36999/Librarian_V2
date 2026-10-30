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
    """Run the export against a given tar stream, recording every helper call."""
    calls: list[list[str]] = []

    def runner(args, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def go(stream: bytes):
        @contextlib.contextmanager
        def fake(args, timeout):
            calls.append(args)
            yield io.BytesIO(stream)

        monkeypatch.setattr(workbench, "_stream", fake)
        engagement = Engagement(id="eng-bounds", source="s", pinned_revision="abc")
        out = workbench._archive_outputs(vault, engagement, IMAGE, runner)
        return out, vault.derived / "engagements" / "eng-bounds" / "output"

    go.calls = calls
    return go


def test_benign_outputs_are_exported_with_their_records(export):
    out, folder = export(tar_stream(entry("output/", kind=tarfile.DIRTYPE),
                                    entry("output/result.json", b'{"ok": true}'),
                                    entry("output/plots/", kind=tarfile.DIRTYPE),
                                    entry("output/plots/a.csv", b"x,y\n1,2\n")))
    assert out["export"]["complete"] and out["export"]["refused"] == []
    assert (folder / "result.json").read_bytes() == b'{"ok": true}'
    assert (folder / "plots" / "a.csv").is_file()
    assert [a["bytes"] for a in out["artifacts"]] == [12, 8]
    assert out["export"]["files"] == 2 and out["export"]["bytes"] == 20


def test_an_oversized_output_stops_the_export_before_it_is_written(export, monkeypatch):
    monkeypatch.setattr(workbench, "MAX_OUTPUT_BYTES", 100)
    # The second file declares ten gigabytes; none of it is read or written.
    small, data = entry("output/small.txt", b"a" * 40)
    huge = tarfile.TarInfo("output/huge.bin")
    huge.size = 10 * 1024 ** 3
    stream = (small.tobuf(tarfile.GNU_FORMAT) + data.ljust(512, b"\0") +
              huge.tobuf(tarfile.GNU_FORMAT) + b"y" * 4096)
    out, folder = export(stream)
    assert not out["export"]["complete"] and "huge.bin" in out["export"]["stopped"]
    assert (folder / "small.txt").is_file() and not (folder / "huge.bin").exists()
    assert out["export"]["bytes"] == 40


def test_too_many_files_stops_the_export(export, monkeypatch):
    monkeypatch.setattr(workbench, "MAX_OUTPUT_FILES", 3)
    out, folder = export(tar_stream(*(entry(f"output/f{i}.txt", b"x") for i in range(10))))
    assert not out["export"]["complete"] and "more than 3 files" in out["export"]["stopped"]
    assert sorted(p.name for p in folder.iterdir()) == ["f0.txt", "f1.txt", "f2.txt"]


def test_hard_link_copies_count_against_the_size_limit(export, monkeypatch):
    monkeypatch.setattr(workbench, "MAX_OUTPUT_BYTES", 60)
    out, folder = export(tar_stream(entry("output/a.bin", b"a" * 40),
                                    entry("output/b.bin", kind=tarfile.LNKTYPE,
                                          link="output/a.bin")))
    assert not out["export"]["complete"] and "60 bytes" in out["export"]["stopped"]
    assert [p.name for p in folder.iterdir()] == ["a.bin"]


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
    for name in ("link", "orphan", "fifo", "device", "escaped.txt", "absolute.txt"):
        assert name in refused
    # A hard link to an exported file is a second name for it: copied, and counted.
    assert "hard:" not in refused and (folder / "hard").read_bytes() == b"kept"
    assert out["export"]["complete"] and out["export"]["bytes"] == 8
    assert sorted(p.name for p in folder.iterdir()) == ["hard", "keep.txt"]
    assert not list(vault.derived.parent.rglob("escaped.txt"))
    assert not list(vault.root.rglob("absolute.txt"))


def test_a_broken_stream_is_reported_not_silently_empty(export):
    out, _ = export(b"this is not a tar stream" * 40)
    assert not out["export"]["complete"] and "stream failed" in out["export"]["stopped"]
    assert out["artifacts"] == []


def test_the_export_folder_mirrors_the_volume_not_earlier_leftovers(export):
    _, folder = export(tar_stream(entry("output/old.txt", b"old")))
    out, folder = export(tar_stream(entry("output/new.txt", b"new")))
    assert [p.name for p in folder.iterdir()] == ["new.txt"]


def test_the_export_helper_is_contained_read_only_and_never_started(export):
    export(tar_stream(entry("output/a.txt", b"a")))
    create = next(c for c in export.calls if c[:2] == ["docker", "create"])
    assert all(flag in create for flag in CONTAINED) and "--read-only" in create
    assert not any(c[:2] in (["docker", "start"], ["docker", "run"]) for c in export.calls)
    # The volume leaves as a stream to be checked, never as a copy into a folder.
    assert ["docker", "cp", "librarian-output-g-bounds:/output", "-"] in export.calls


# --------------------------------------------------------------- helpers staging

def test_every_staging_helper_carries_the_isolation_policy(tmp_path, monkeypatch):
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.txt").write_text("a", encoding="utf-8")
    archive = tmp_path / "a.tar.gz"
    with tarfile.open(archive, "w:gz") as bundle:
        bundle.add(source, arcname="repo-abc")
    monkeypatch.setattr(workbench, "_download_archive", lambda *_: (archive, "hash"))
    calls: list[list[str]] = []

    def runner(args, timeout):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    engagement = Engagement(id="eng-stage", source="s", pinned_revision="abc")
    workbench._docker_stage(engagement, "example/test", IMAGE, runner)
    containers = [c for c in calls if c[:2] in (["docker", "run"], ["docker", "create"])]
    assert len(containers) == 2
    for args in containers:
        assert all(flag in args for flag in CONTAINED), args
        assert "--memory" in args and "--pids-limit" in args
    provision, stage = containers
    assert provision[provision.index("--cap-add") + 1] == "FOWNER"
    assert "--read-only" in provision
    assert "--cap-add" not in stage and "-lc" not in stage
    assert "tar -xzof" in stage[-1]


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
