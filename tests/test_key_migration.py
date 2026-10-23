"""Fallback credential migration stays explicit, atomic, and secret-free."""
from __future__ import annotations

from resource_librarian import keys
from resource_librarian.keys import KeyStore, SERVICE


class MemoryKeyring:
    def __init__(self, fail_on: str = "") -> None:
        self.values: dict[str, str] = {}
        self.fail_on = fail_on

    def get_password(self, _service: str, name: str) -> str | None:
        assert _service == SERVICE
        return self.values.get(name)

    def set_password(self, _service: str, name: str, value: str) -> None:
        assert _service == SERVICE
        if name == self.fail_on:
            raise RuntimeError("backend write failed")
        self.values[name] = value

    def delete_password(self, _service: str, name: str) -> None:
        assert _service == SERVICE
        self.values.pop(name, None)


def test_explicit_fallback_key_migration_moves_values_then_removes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(keys, "config_dir", lambda: tmp_path)
    store = KeyStore(use_keyring=False)
    store._saved = {"OPENAI_API_KEY": "test-openai-secret", "ANTHROPIC_API_KEY": "test-anthropic-secret"}
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("fallback values are not returned by migration\n", encoding="utf-8")
    backend = MemoryKeyring()
    monkeypatch.setattr(keys, "_keyring", lambda: backend)

    result = store.migrate_to_keychain()

    assert result == {"migrated": 2, "backend": "keychain", "already_secure": False,
                      "fallback_retained": False, "detail": ""}
    assert backend.values == store._saved
    assert not store.path.exists()
    assert store.backend == "keychain"
    assert "test-openai-secret" not in str(result)


def test_failed_keychain_migration_keeps_fallback_and_rolls_back_new_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(keys, "config_dir", lambda: tmp_path)
    store = KeyStore(use_keyring=False)
    store._saved = {"OPENAI_API_KEY": "test-openai-secret", "ANTHROPIC_API_KEY": "test-anthropic-secret"}
    store.path.parent.mkdir(parents=True, exist_ok=True)
    store.path.write_text("still the durable fallback\n", encoding="utf-8")
    backend = MemoryKeyring(fail_on="ANTHROPIC_API_KEY")
    monkeypatch.setattr(keys, "_keyring", lambda: backend)

    try:
        store.migrate_to_keychain()
    except OSError as exc:
        assert "could not write all saved credentials" in str(exc)
    else:  # pragma: no cover - assertion clarity if the fake changes
        raise AssertionError("a failing keychain must not claim migration success")

    assert store.path.exists()
    assert backend.values == {}
    assert store.backend == "config file"


def test_keyring_installed_after_fallback_detects_and_migrates_the_old_file(tmp_path, monkeypatch):
    """An upgrade cannot mistake a newly available backend for already-migrated keys."""
    monkeypatch.setattr(keys, "config_dir", lambda: tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=old-fallback-secret\n", encoding="utf-8")
    backend = MemoryKeyring()
    monkeypatch.setattr(keys, "_keyring", lambda: backend)

    store = KeyStore()

    assert store.backend == "keychain"
    assert store.migration_pending is True
    assert store.status("openai")["source"] == "fallback_pending_migration"
    assert store.migrate_to_keychain()["migrated"] == 1
    assert backend.values["OPENAI_API_KEY"] == "old-fallback-secret"
    assert store.migration_pending is False
    assert not store.path.exists()


def test_migration_never_overwrites_a_current_keychain_value_with_a_stale_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(keys, "config_dir", lambda: tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / ".env").write_text("OPENAI_API_KEY=stale-fallback-secret\n", encoding="utf-8")
    backend = MemoryKeyring()
    backend.values["OPENAI_API_KEY"] = "current-keychain-secret"
    monkeypatch.setattr(keys, "_keyring", lambda: backend)

    store = KeyStore()

    assert store.migration_pending is True
    result = store.migrate_to_keychain()
    assert result["migrated"] == 0
    assert backend.values["OPENAI_API_KEY"] == "current-keychain-secret"
    assert not store.path.exists()
