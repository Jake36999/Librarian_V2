"""MF-016 (specification N-05): one container's life, from creation to disposal.

- A supervised, attached run is counted here, and requests one stop on whichever comes
  first: its deadline, a cancelled turn, output past its limit, or sampled disk writes
  past theirs.
- A checked export accepts nothing unless every member passes.
- Quarantine is held to its newest few.
These run real processes on this machine, never Docker; `test_sandbox.py`,
`test_claim_run.py` and `test_workbench_boundaries.py` cover each caller's lifecycle.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import threading
import time

import pytest

from resource_librarian import containers, providers
from resource_librarian.containers import Producer, block_written, check_tar, prune, supervise
from resource_librarian.loop import Loop
from resource_librarian.providers import Reply

from docker_fake import Docker, answer

FLOOD = [sys.executable, "-c",
         "import sys\nwhile True: sys.stdout.buffer.write(b'x' * 65536); sys.stdout.flush()"]
SLEEP = [sys.executable, "-c", "import time; time.sleep(60)"]


def attached(args):
    return subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)


class Stopper:
    """Stands in for `docker stop`: records each request, and ends the process."""

    def __init__(self, process, kill=True):
        self.process, self.kill, self.reasons = process, kill, []

    def __call__(self, reason):
        self.reasons.append(reason)
        if self.kill:
            self.process.kill()


# ------------------------------------------------------------------ supervise

def test_a_flood_is_stopped_once_and_what_is_received_is_bounded():
    process = attached(FLOOD)
    stop = Stopper(process)
    limit, tolerance = 256 * 1024, 64 * 1024
    capture = supervise(process, deadline=60, request_stop=stop, keep=4096, limit=limit,
                        tolerance=tolerance)
    assert stop.reasons == ["output_limit"] and capture.stop == "output_limit"
    received = capture.produced["stdout"]
    assert limit < received <= limit + tolerance + containers.READ_BLOCK
    assert capture.retained["stdout"] <= 4096 and len(capture.stdout) <= 4096
    assert capture.cut == ["stdout"]
    record = capture.public()
    assert record["overshoot"] == received - limit and record["limit"] == limit


def test_the_deadline_requests_one_stop():
    process = attached(SLEEP)
    stop = Stopper(process)
    started = time.monotonic()
    capture = supervise(process, deadline=0.5, request_stop=stop)
    assert stop.reasons == ["deadline"] and capture.stop == "deadline"
    assert time.monotonic() - started < 15


def test_a_cancelled_turn_requests_the_stop():
    process = attached(SLEEP)
    stop = Stopper(process)
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    capture = supervise(process, deadline=60, request_stop=stop, cancel=cancel)
    assert stop.reasons == ["cancelled"] and capture.stop == "cancelled"


def test_sampled_disk_writes_past_their_limit_request_the_stop_and_say_so():
    process = attached(SLEEP)
    stop = Stopper(process)
    seen = iter([10, 500, 2_000, 9_000, 9_000, 9_000])
    capture = supervise(process, deadline=60, request_stop=stop,
                        written=lambda: next(seen, 9_000), io_limit=1_000, every=0.05)
    assert stop.reasons == ["io_limit"]
    io_record = capture.public()["io"]
    assert io_record["samples"] >= 3 and io_record["written"] >= 2_000
    assert io_record["overshoot_at_least"] >= 1_000 and "not a quota" in io_record["method"]


def test_an_attached_client_that_will_not_leave_after_the_stop_is_ended(monkeypatch):
    monkeypatch.setattr(containers, "AFTER_STOP", 0.3)
    process = attached(SLEEP)
    stop = Stopper(process, kill=False)          # the container "stopped"; the client did not
    started = time.monotonic()
    supervise(process, deadline=0.2, request_stop=stop)
    assert stop.reasons == ["deadline"] and process.poll() is not None
    assert time.monotonic() - started < 15


def test_what_a_quiet_run_prints_is_kept_whole():
    process = attached([sys.executable, "-c",
                        "import sys; print('out'); sys.stderr.write('err')"])
    capture = supervise(process, deadline=60, request_stop=Stopper(process))
    assert capture.stop == "" and capture.exit_code == 0
    assert capture.stdout.strip() == "out" and capture.stderr == "err"
    assert capture.cut == [] and capture.public()["overshoot"] == 0


@pytest.mark.parametrize("said, written", [
    ("49.2kB / 41.9MB\n", 41_900_000), ("0B / 0B", 0), ("1.1GB / 2.5GB", 2_500_000_000),
    ("3MiB / 7KiB", 7 * 1024), ("--", None)])
def test_docker_stats_block_io_is_read_as_bytes_written(said, written):
    assert block_written(lambda args, timeout: answer(said), "c") == written


def test_a_cut_stream_ends_the_attached_client_and_the_stop_still_happens():
    process = attached(FLOOD)
    stop = Stopper(process, kill=False)          # as if `docker stop` left the client alone
    started = time.monotonic()
    capture = supervise(process, deadline=60, request_stop=stop, limit=128 * 1024,
                        tolerance=64 * 1024)
    assert capture.cut == ["stdout"] and process.poll() is not None
    assert stop.reasons == ["output_limit"] and time.monotonic() - started < 15


def test_streamed_docker_stats_readings_are_watched_without_a_call_each():
    lines = "import time\nfor v in ['0B / 0B', '1kB / 5MB', '1kB / 9MB']:\n" \
            "    print(v, flush=True); time.sleep(0.05)\ntime.sleep(30)\n"
    watch = containers.StatsWatch("c", command=[sys.executable, "-c", lines])
    try:
        for _ in range(100):
            if watch.readings == 3:
                break
            time.sleep(0.05)
        assert watch() == 9_000_000 and watch.readings == 3
    finally:
        watch.close()
    assert watch.process.poll() is not None


def test_no_answer_from_docker_stats_is_no_sample():
    assert block_written(lambda args, timeout: answer(code=1, stderr="x"), "c") is None


# ------------------------------------------------------------------ the producer

def test_a_stop_is_requested_once_however_often_it_is_asked():
    docker = Docker()
    producer = Producer("c1", docker, kind="test")
    docker.status["c1"] = "running"
    producer.stop("deadline")
    producer.stop("output_limit")
    assert docker.count("stop") == 1 and producer.stop_reason == "deadline"


def test_a_create_refused_for_a_name_in_use_removes_nothing():
    docker = Docker(create_fails='Conflict. The container name "/c1" is already in use')
    producer = Producer("c1", docker, kind="test")
    capture = producer.execute([], "image", ["true"], deadline=5)
    assert docker.count("rm") == 0 and producer.state == "disposed"
    assert not producer.succeeded and capture.exit_code == 125
    assert producer.dispose() is True and docker.count("rm") == 0   # asked once, never again


def test_a_container_that_never_started_has_no_exit_code():
    docker = Docker()
    producer = Producer("c1", docker, kind="test")
    capture = producer.execute([], "image", ["true"], deadline=5,
                               before_start=lambda: "the archive could not be copied in")
    assert capture.exit_code is None and "start" not in docker.verbs()
    assert "could not be copied in" in capture.stderr
    producer.dispose()
    assert producer.state == "disposed"


# ------------------------------------------------------------------ check_tar

def tarred(*members):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w|", format=tarfile.GNU_FORMAT) as bundle:
        for name, kind, data in members:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(data or b"")
            bundle.addfile(info, io.BytesIO(data) if data else None)
    return io.BytesIO(buffer.getvalue())


def check(stream, tmp_path, **limits):
    return check_tar(stream, tmp_path / "q", root="out", max_bytes=limits.get("bytes", 10_000),
                     max_entries=limits.get("entries", 100))


def test_folders_given_only_by_their_files_are_made_and_counted(tmp_path):
    report = check(tarred(("out", tarfile.DIRTYPE, None),
                          ("out/a/b/c.txt", tarfile.REGTYPE, b"abc"),
                          ("out/a/", tarfile.DIRTYPE, None)), tmp_path)
    assert report["accepted"] and report["dirs"] == 2 and report["entries"] == 3
    assert (tmp_path / "q" / "a" / "b" / "c.txt").read_bytes() == b"abc"
    assert len(report["files"][0]["sha256"]) == 64


@pytest.mark.parametrize("members, why", [
    ([("out/f", tarfile.REGTYPE, b"x"), ("out/f/g", tarfile.REGTYPE, b"y")],
     "inside something that is a file"),
    ([("out/f", tarfile.REGTYPE, b"x"), ("out/f", tarfile.REGTYPE, b"y")], "second entry"),
    ([("elsewhere/f", tarfile.REGTYPE, b"x")], "outside the exported folder"),
    ([("out/s", tarfile.GNUTYPE_SPARSE, b"")], "sparse"),
    ([("out/c", tarfile.CONTTYPE, b"x")], "not a regular file"),
    ([("out/AUX", tarfile.REGTYPE, b"x")], "reserves for a device"),
    ([("out/sp ", tarfile.REGTYPE, b"x")], "ending in a dot or a space"),
    ([("out/" + "a" * 120 + "/" + "b" * 120 + "/" + "c" * 120 + "/" + "d" * 60,
       tarfile.REGTYPE, b"x")], "a path over 400 characters"),
])
def test_one_unsafe_member_refuses_the_export(tmp_path, members, why):
    report = check(tarred(("out", tarfile.DIRTYPE, None), *members), tmp_path)
    assert not report["accepted"] and why in " ".join(report["rejected"])


def test_the_byte_budget_is_checked_before_a_file_is_written(tmp_path):
    report = check(tarred(("out/a", tarfile.REGTYPE, b"x" * 60),
                          ("out/b", tarfile.REGTYPE, b"y" * 60)), tmp_path, bytes=100)
    assert not report["accepted"] and "out/b" not in report["stopped"]
    assert "b would take it past 100 bytes" in report["stopped"]
    assert not (tmp_path / "q" / "b").exists()


def test_nothing_more_is_written_once_a_member_is_refused(tmp_path):
    report = check(tarred(("out/link", tarfile.SYMTYPE, None),
                          ("out/after.txt", tarfile.REGTYPE, b"later")), tmp_path)
    assert not report["accepted"] and not (tmp_path / "q" / "after.txt").exists()


def test_quarantine_keeps_only_the_newest(tmp_path):
    for i in range(5):
        folder = tmp_path / f"run-{i}"
        folder.mkdir()
        os.utime(folder, (1_000_000 + i, 1_000_000 + i))
    removed = prune(tmp_path, keep=2)
    assert sorted(removed) == ["run-0", "run-1", "run-2"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["run-3", "run-4"]


# ------------------------------------------------------------------ a turn's cancel

def test_a_turns_cancel_is_in_its_tools_context_only_while_it_runs(vault):
    seen = []

    def model(system, messages, tools):
        seen.append(loop.ctx.extras.get("cancel"))
        return Reply(text="done", model="lead-model-x")

    loop = Loop(vault, providers.Scripted(model, name="lead-model-x"))
    cancel = threading.Event()
    loop.send("go", cancel=cancel)
    assert seen and seen[0] is cancel
    assert "cancel" not in loop.ctx.extras
    loop.send("again")
    assert seen[-1] is None
