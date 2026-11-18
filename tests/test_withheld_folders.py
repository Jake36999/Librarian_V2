"""Folders withheld for a decision (undecided, or held for a person's review) never reach a graph
build, an index or a folder-source walk; an `exclude` decision also narrows reading (Gemini audit
R3, verified 2026-11-17)."""
import json

import pytest

from resource_librarian.vault import Vault


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "library"; root.mkdir()
    source = tmp_path / "source"
    for name in ("own.md", "vendor/notes.md", "vendor/paper.pdf", "excluded/x.md"):
        path = source / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic {name}\n")
    return Vault(root), source


def planner(found):
    def part(key, subtrees, purpose):
        return dict(key=key, subtrees=subtrees, file_counts={".md": 1}, bytes=10,
                    suggestion=dict(purpose=purpose, reasons=["synthetic"]))
    return dict(plan_version="workspace-init-v1", shared_survey_fingerprint=found.fingerprint,
                partitions=[part("residual", [], "own-docs"), part("vendor", ["vendor"], "third-party"),
                            part("excluded", ["excluded"], "exclude")])


def test_the_graph_build_is_told_which_folders_are_withheld(project):
    from resource_librarian.folder_review import FolderReview
    vault, source = project
    requests = []
    review = FolderReview(vault, planner=planner, applier=lambda request: requests.append(request) or {})
    cards = {c["path"]: c for c in review.survey(source)["cards"]}
    held = review.store.load(cards["vendor"]["id"])
    held["sensitivity"] = dict(sensitivity="review_required", reason="dual-use")
    review.store.save(held)
    root = cards["."]
    review.accept(root["id"], root["folder_fingerprint"], purpose="own-docs", graph="docs", person=True)
    assert str((source / "vendor").resolve()) in requests[-1]["withheld"]


def test_folder_sources_skip_withheld_and_excluded_folders_and_reads_honour_excludes(project):
    from resource_librarian.content_roots import resolve_read_path
    from resource_librarian.folder_review import FolderReview
    from resource_librarian.folder_sources import documents
    vault, source = project
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    cards = {c["path"]: c for c in review.survey(source)["cards"]}
    root = cards["."]
    review.accept(root["id"], root["folder_fingerprint"], purpose="own-docs", graph="docs", person=True)
    excluded = {c["path"]: c for c in review.list()}["excluded"]
    review.accept(excluded["id"], excluded["folder_fingerprint"], purpose="exclude", graph="", person=True)
    found = {p.relative_to(source.resolve()).as_posix() for p in documents(vault, str(source), [".md", ".pdf"])}
    assert found == {"own.md"}                                   # vendor is undecided, excluded is excluded
    manifest = json.loads((vault.librarian / "content-roots.json").read_text(encoding="utf-8"))
    assert str(source / "excluded") in manifest["excludes"]
    with pytest.raises(TypeError, match="excluded"):
        resolve_read_path(vault, str(source / "excluded" / "x.md"))
    assert resolve_read_path(vault, str(source / "own.md")) == (source / "own.md").resolve()


def test_a_later_normal_check_never_lifts_a_hold(project, monkeypatch):
    from types import SimpleNamespace
    from resource_librarian import clerk
    from resource_librarian.folder_review import FolderReview
    vault, source = project
    review = FolderReview(vault, planner=planner)
    card = {c["path"]: c for c in review.survey(source)["cards"]}["vendor"]
    card = review.store.load(card["id"]); card["sensitivity"] = dict(sensitivity="review_required", reason="dual-use")
    review.store.save(card)
    monkeypatch.setattr(clerk, "run", lambda tasks, endpoint: [
        SimpleNamespace(ok=True, value={"description": "A synthetic folder inventory."}),
        SimpleNamespace(ok=True, value={"sensitivity": "normal", "reason": "looks ordinary"})])
    out = review.draft(card["id"], clerk.Scripted(lambda _: {}), approved=True)
    assert out["sensitivity"]["sensitivity"] == "review_required"
    assert out["sensitivity"]["later_check"]["sensitivity"] == "normal"


def test_policy_writes_go_through_commit_and_a_failed_build_restores_the_manifest(project):
    from resource_librarian.folder_review import FolderReview
    vault, source = project
    vault.set_setting("promotion", "mode", "agent")
    FolderReview(vault, planner=planner).survey(source)
    review = FolderReview(vault, planner=planner)
    for card in review.list():
        card["sensitivity"] = dict(sensitivity="normal", reason="checked"); review.store.save(card)
    manifest = vault.librarian / "content-roots.json"
    before = manifest.read_bytes() if manifest.is_file() else None
    commits = []

    def fail(_request):
        raise ValueError("DISK_RESERVE: synthetic")
    failing = FolderReview(vault, planner=planner, applier=fail, commit=lambda write: commits.append(1) or write())
    with pytest.raises(ValueError, match="DISK_RESERVE"):
        failing.accept_by_policy(source)
    assert commits and (manifest.read_bytes() if manifest.is_file() else None) == before
    assert not [c for c in failing.list() if c["status"] == "accepted"]


def test_read_scope_is_resolved_once_per_manifest_and_follows_a_change(project, monkeypatch):
    """The resolved roots and exclusions are cached per manifest content (2026-11-18: resolving
    1,779 exclusions on every read made one index refresh take 95 s); an exclusion written
    after a read must still narrow the next one."""
    from pathlib import Path
    from resource_librarian import content_roots
    from resource_librarian.content_roots import resolve_read_path
    from resource_librarian.folder_review import FolderReview
    vault, source = project
    review = FolderReview(vault, planner=planner, applier=lambda _: {})
    cards = {c["path"]: c for c in review.survey(source)["cards"]}
    root = cards["."]
    review.accept(root["id"], root["folder_fingerprint"], purpose="own-docs", graph="docs", person=True)
    target = source / "excluded" / "x.md"
    assert resolve_read_path(vault, str(target)) == target.resolve()
    calls = []
    real = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, *a, **k: calls.append(self) or real(self, *a, **k))
    for _ in range(5):
        resolve_read_path(vault, str(source / "own.md"))
    assert len(calls) <= 5                      # only each read's own path, not the scope again
    monkeypatch.setattr(Path, "resolve", real)
    excluded = {c["path"]: c for c in review.list()}["excluded"]
    review.accept(excluded["id"], excluded["folder_fingerprint"], purpose="exclude", graph="", person=True)
    with pytest.raises(TypeError, match="excluded"):
        resolve_read_path(vault, str(target))
    assert content_roots._RESOLVED_SCOPES
