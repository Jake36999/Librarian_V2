"""`[search] refresh_seconds` lets searches skip the folder walk after a recent refresh; the
default keeps refreshing before every search (2026-11-18: 12 s of walking before a 1 s search)."""
from resource_librarian import tools  # noqa: F401
from resource_librarian.index import Index
from resource_librarian.init import init
from resource_librarian.registry import Context
from resource_librarian.tools.library import _prepared_engine
from resource_librarian.vault import Vault


def test_refresh_is_skipped_only_inside_the_configured_window(tmp_path, monkeypatch):
    init(tmp_path / "lib"); vault = Vault(tmp_path / "lib")
    ctx = Context(tier="consult", vault=vault)
    calls = []
    with Index(vault) as index:
        real = index.refresh
        monkeypatch.setattr(index, "refresh", lambda: calls.append(1) or real())

        def refreshed():
            before = len(calls); _prepared_engine(ctx, index, True); return len(calls) > before
        assert refreshed() and refreshed()                      # default: every search refreshes
        vault.set_setting("search", "refresh_seconds", 30)
        assert not refreshed()                                  # within 30 s of the last refresh
        index._refreshed_at -= 31
        assert refreshed()                                      # the window passed
