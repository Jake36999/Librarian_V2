"""Storage and speed quick wins (2026-11-17 pilot measurements).

- counts() reads cached summaries, so a staging_list no longer parses every folder card;
- a folder a survey proposed on its own stays out of its parent's whole indexing until decided;
- the index's write-ahead log is capped and emptied after a refresh and on close.
"""
import json
import os

import pytest

from resource_librarian.vault import Vault


@pytest.fixture
def attached(tmp_path):
    root = tmp_path / "library"; root.mkdir()
    source = tmp_path / "source"; source.mkdir()
    (source / "own.py").write_text("print('own code')\n")
    (source / "held_repo").mkdir()
    (source / "held_repo" / "driver.c").write_text("int main(void) { return 0; }\n")
    return Vault(root), source


def planner(found):
    return dict(plan_version="workspace-init-v1", shared_survey_fingerprint=found.fingerprint,
                partitions=[dict(key="residual", subtrees=[], file_counts={".py": 1}, bytes=18,
                                 suggestion=dict(purpose="own-current", reasons=["synthetic"])),
                            dict(key="held_repo", subtrees=["held_repo"], file_counts={".c": 1}, bytes=30,
                                 suggestion=dict(purpose="third-party", reasons=["synthetic vendor repo"]))])


def survey(vault, source):
    from resource_librarian.folder_review import FolderReview
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    cards = {c["path"]: c for c in review.survey(source)["cards"]}
    return review, cards


def test_counts_parse_only_changed_cards_and_follow_edits_and_deletions(attached, monkeypatch):
    from resource_librarian import staging
    from resource_librarian.staging import StagingStore
    vault, source = attached
    review, cards = survey(vault, source)
    store = StagingStore(vault)
    before = store.counts()["folder"]
    parsed = []
    real = staging.json.loads
    monkeypatch.setattr(staging.json, "loads", lambda text, *a, **k: parsed.append(1) or real(text, *a, **k))
    assert store.counts()["folder"] == before and not parsed          # nothing changed, nothing parsed
    held = review.store.load(cards["held_repo"]["id"])
    held["sensitivity"] = dict(sensitivity="review_required", reason="dual-use")
    review.store.save(held)
    parsed.clear()                                                     # load() above parsed it too
    after = store.counts()["folder"]
    assert len(parsed) == 1 and after.get("sensitive_waiting") == 1   # only the edited card was read
    (store.folder("folder") / f"{held['id']}.json").unlink()
    assert store.counts()["folder"].get("sensitive_waiting", 0) == 0  # a deleted card leaves the counts


def test_an_undecided_folder_stays_out_of_its_parents_whole_indexing_until_decided(attached):
    from resource_librarian.workspace_documents import index_paths
    vault, source = attached
    review, cards = survey(vault, source)
    root = cards["."]
    review.accept(root["id"], root["folder_fingerprint"], purpose="own-current", graph="project", person=True)
    paths = {p.resolve() for p in index_paths(vault)}
    assert (source / "own.py").resolve() in paths
    assert (source / "held_repo" / "driver.c").resolve() not in paths  # held, nobody decided it
    held = {c["path"]: c for c in review.list()}["held_repo"]
    review.accept(held["id"], held["folder_fingerprint"], purpose="own-current", graph="project", person=True)
    assert (source / "held_repo" / "driver.c").resolve() in {p.resolve() for p in index_paths(vault)}


def test_the_index_log_is_capped_and_emptied_after_a_refresh_and_on_close(tmp_path):
    from resource_librarian.index import IndexService, WAL_SIZE_LIMIT
    from resource_librarian.init import init
    init(tmp_path / "library")
    vault = Vault(tmp_path / "library")
    for n in range(30):
        (vault.root / "Inbox" / f"note {n}.md").write_text(f"# Note {n}\n\n" + "words " * 400, encoding="utf-8")
    service = IndexService(vault)
    try:
        service.refresh()
        wal = service.run(lambda index: index.path).with_name("index.sqlite-wal")
        assert not wal.exists() or wal.stat().st_size == 0
        assert service.run(lambda index: index.conn.execute("PRAGMA journal_size_limit").fetchone()[0]) == WAL_SIZE_LIMIT
        (vault.root / "Inbox" / "late.md").write_text("# Late\n\nmore words\n", encoding="utf-8")
        service.run(lambda index: index.refresh())                      # a pass outside refresh() leaves frames
    finally:
        service.close()
    assert not wal.exists() or wal.stat().st_size == 0                  # a clean close empties the log
