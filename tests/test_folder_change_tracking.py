"""A re-survey tells a move from a content change (owner, 2026-11-17: "only requiring review if
the content changes, but only putting up a yellow flag when a file moves")."""
import json
import os

import pytest

from resource_librarian.vault import Vault


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "library"; root.mkdir()
    source = tmp_path / "source"
    for name in ("main.py", "docs/a.pdf", "docs/b.pdf", "vendor/x.c"):
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic {name}\n")
    return Vault(root), source


def planner(found):
    def part(key, subtrees, purpose):
        return dict(key=key, subtrees=subtrees, file_counts={".x": 1}, bytes=10,
                    suggestion=dict(purpose=purpose, reasons=["synthetic"]))
    return dict(plan_version="workspace-init-v1", shared_survey_fingerprint=found.fingerprint,
                partitions=[part("residual", [], "own-current"), part("docs", ["docs"], "own-docs"),
                            part("vendor", ["vendor"], "third-party")])


def review_of(vault):
    from resource_librarian.folder_review import FolderReview
    return FolderReview(vault, planner=planner, applier=lambda _: {})


def cards(review):
    return {c["path"]: c for c in review.list()}


def accept(review, path, purpose, graph):
    card = cards(review)[path]
    review.accept(card["id"], card["folder_fingerprint"], purpose=purpose, graph=graph, person=True)


@pytest.fixture
def decided(project):
    vault, source = project
    review = review_of(vault)
    review.survey(source)
    accept(review, ".", "own-current", "project")
    accept(review, "docs", "own-docs", "project-docs")
    return vault, source, review


def move(source, a, b):
    target = source / b; target.parent.mkdir(parents=True, exist_ok=True)
    os.rename(source / a, target)                       # a same-drive move keeps size and time


def test_a_moved_file_keeps_the_decision_and_raises_a_yellow_flag(decided):
    vault, source, review = decided
    move(source, "docs/a.pdf", "docs/datasheets/a.pdf")
    review.survey(source)
    after = cards(review)
    docs = after["docs"]
    assert docs["status"] == "accepted" and docs["decision"]["purpose"] == "own-docs"
    assert docs["change"]["kind"] == "moved" and docs["change"]["flag"] == "yellow"
    assert docs["change"]["moved"] == [["docs/a.pdf", "docs/datasheets/a.pdf"]]
    root = after["."]
    assert root["status"] == "accepted" and "change" not in root   # a decided child tracks itself
    card = after["docs"]                                             # the kept card is current again
    review.accept(card["id"], card["folder_fingerprint"], purpose="own-docs", graph="project-docs", person=True)


def test_removed_files_are_tracked_but_new_or_edited_content_asks_again(decided):
    vault, source, review = decided
    (source / "docs" / "b.pdf").unlink()
    review.survey(source)
    docs = cards(review)["docs"]
    assert docs["status"] == "accepted" and docs["change"]["kind"] == "removed"
    (source / "docs" / "c.md").write_text("new material\n")
    review.survey(source)
    docs = cards(review)["docs"]
    assert docs["status"] == "staged" and docs["previous_decision"]["purpose"] == "own-docs"
    assert docs["change"]["kind"] == "content" and docs["change"]["flag"] == "review"
    assert docs["change"]["added"] == ["docs/c.md"]


def test_a_hold_survives_a_resurvey_and_changed_content_never_lifts_it(project):
    vault, source = project
    review = review_of(vault)
    review.survey(source)
    vendor = cards(review)["vendor"]
    vendor["sensitivity"] = dict(sensitivity="review_required", reason="dual-use tooling")
    review.store.save(vendor)
    review.survey(source)
    assert cards(review)["vendor"]["sensitivity"]["sensitivity"] == "review_required"
    (source / "vendor" / "y.c").write_text("more vendor code\n")
    review.survey(source)
    vendor = cards(review)["vendor"]
    assert vendor["sensitivity"]["sensitivity"] == "review_required"
    assert "a person decides" in vendor["sensitivity"]["reason"]


def test_staged_sources_and_the_ledger_follow_a_moved_file(decided):
    from resource_librarian.staging import StagingStore
    vault, source, review = decided
    old = (source / "docs" / "a.pdf").resolve().as_posix()
    StagingStore(vault).add(dict(id="paper-a", kind="source", file=old, fields={"file": old}))
    ledger = vault.librarian / "folder-sources.json"
    ledger.write_text(json.dumps({old: "queued"}), encoding="utf-8")
    move(source, "docs/a.pdf", "docs/datasheets/a.pdf")
    out = review.survey(source)
    new = (source / "docs" / "datasheets" / "a.pdf").resolve().as_posix()
    item = StagingStore(vault).load("paper-a")
    assert out["followed_sources"] == 1 and item["file"] == new and item["fields"]["file"] == new
    assert item["change"]["flag"] == "yellow" and item["history"][-1]["moved_from"] == old
    assert json.loads(ledger.read_text(encoding="utf-8")) == {new: "queued"}


def test_classify_change_pairs_moves_by_size_and_time():
    from resource_librarian.folder_review import classify_change
    old = [("d/", 0, 0), ("d/a.pdf", 10, 111), ("d/b.pdf", 20, 222), ("d/c.md", 5, 333)]
    new = [("d/", 0, 0), ("d/sub/a.pdf", 10, 111), ("d/b2.pdf", 20, 222), ("d/c.md", 6, 444)]
    change = classify_change(old, new, rel="d")
    assert change["moved"] == [["d/b.pdf", "d/b2.pdf"], ["d/a.pdf", "d/sub/a.pdf"]]
    assert change["edited"] == ["d/c.md"] and change["kind"] == "content"
    assert classify_change(None, new)["kind"] == "content"           # nothing to compare: ask
