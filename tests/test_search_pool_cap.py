"""One note may place only a few passages in a lexical pool (2026-11-18: a 92,000-passage data
file filled all 80 slots before results were reduced to one per note)."""
from resource_librarian.index import Index
from resource_librarian.init import init
from resource_librarian.search import PER_NOTE_POOL, Engine
from resource_librarian.vault import Vault


def test_a_giant_note_cannot_fill_the_pool(tmp_path):
    init(tmp_path / "lib"); vault = Vault(tmp_path / "lib")
    inbox = vault.root / "Inbox"; inbox.mkdir(exist_ok=True)
    (inbox / "Giant log.md").write_text("# Log\n\n" + "\n\n".join(
        f"## Entry {i}\n\nThe mtls relay handshake retried at step {i}." for i in range(200)), encoding="utf-8")
    (inbox / "Relay design.md").write_text("# Relay design\n\nThe mtls relay terminates client handshakes.\n", encoding="utf-8")
    with Index(vault) as index:
        index.refresh()
        engine = Engine(index, vault.config()["heuristics"])
        shapes = [r[0] for r in index.conn.execute("SELECT DISTINCT shape FROM note")]
        roles = [r[0] for r in index.conn.execute("SELECT DISTINCT role FROM chunk")]
        hits = engine.lexical(["mtls", "relay"], shapes, roles=roles, limit=10)
        notes = [h.note for h in hits]
        assert notes.count("Giant log") <= PER_NOTE_POOL
        assert "Relay design" in notes
