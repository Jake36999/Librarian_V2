"""ADAPT-06: background service calls yield to interactive turns on a local host."""

import threading
import time

import pytest

from resource_librarian.hosts import Host, HostLimiter
from resource_librarian.providers import ProviderError


def host(base_url: str, timeout: int = 120) -> Host:
    return Host(id="h", display_name="H", protocol="openai",
                base_url=base_url, timeout=timeout, concurrency_limit=2)


@pytest.mark.parametrize("base_url,expected", [
    ("http://localhost:1234/v1", True),
    ("http://127.0.0.1:1234/v1", True),
    ("http://[::1]:1234/v1", True),
    ("http://lmstudio.local:1234/v1", True),
    ("http://api.deepinfra.com/v1", False),
])
def test_local_detection(base_url: str, expected: bool) -> None:
    assert host(base_url).local is expected


def test_background_yields_to_interactive_on_local_host() -> None:
    limiter = HostLimiter()
    h = host("http://localhost:1234/v1", timeout=2)
    interactive_started = threading.Event()
    interactive_done = threading.Event()
    background_ran = threading.Event()

    def interactive() -> str:
        interactive_started.set()
        interactive_done.wait(5)
        return "lead"

    def background() -> str:
        background_ran.set()
        return "embeddings"

    lead = threading.Thread(target=limiter.run, args=(h, interactive))
    lead.start()
    assert interactive_started.wait(5)
    sync = threading.Thread(target=limiter.run, args=(h, background), kwargs={"background": True})
    sync.start()
    # The embedding sync stays parked while the Lead's turn is in flight.
    assert not background_ran.wait(0.3)
    interactive_done.set()
    lead.join(5)
    sync.join(5)
    assert background_ran.is_set()
    assert not sync.is_alive()


def test_background_does_not_wait_on_remote_host() -> None:
    limiter = HostLimiter()
    h = host("http://api.deepinfra.com/v1", timeout=2)
    interactive_started = threading.Event()
    interactive_done = threading.Event()
    background_ran = threading.Event()

    def interactive() -> str:
        interactive_started.set()
        interactive_done.wait(5)
        return "lead"

    def background() -> str:
        background_ran.set()
        return "embeddings"

    lead = threading.Thread(target=limiter.run, args=(h, interactive))
    lead.start()
    assert interactive_started.wait(5)
    sync = threading.Thread(target=limiter.run, args=(h, background), kwargs={"background": True})
    sync.start()
    # A remote provider does not share this machine, so nothing yields.
    assert background_ran.wait(5)
    interactive_done.set()
    lead.join(5)
    sync.join(5)


def test_background_times_out_while_interactive_turn_holds_a_local_host() -> None:
    limiter = HostLimiter()
    h = host("http://localhost:1234/v1", timeout=1)
    interactive_started = threading.Event()
    release = threading.Event()
    failures: list[ProviderError] = []

    def interactive() -> str:
        interactive_started.set()
        release.wait(5)
        return "lead"

    def background() -> str:
        assert False, "the background call must not run while the turn holds the host"

    lead = threading.Thread(target=limiter.run, args=(h, interactive))
    lead.start()
    assert interactive_started.wait(5)
    sync = threading.Thread(target=lambda: failures.append(catch(limiter, h, background)))
    sync.start()
    sync.join(5)
    release.set()
    lead.join(5)
    assert len(failures) == 1
    assert "is busy with an interactive turn" in str(failures[0])


def catch(limiter: HostLimiter, h: Host, call) -> Exception:
    try:
        limiter.run(h, call, background=True)
    except ProviderError as exc:
        return exc
    raise AssertionError("the background call should have yielded with a ProviderError")
