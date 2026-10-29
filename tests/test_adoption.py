"""DEPLOY-02: compare-and-apply Adopt and Attach, the content-roots manifest, and a
watcher scoped to the approved roots that backs off on large trees."""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import pytest

from resource_librarian import content_roots
from resource_librarian.cli import main
from resource_librarian.coordination import DocumentLeases, VaultWatcher
from resource_librarian.deploy_survey import survey
from resource_librarian.init import init
from resource_librarian.rules import Refusal
from resource_librarian.vault import Vault


def hashes(root: Path, skip: str = ".librarian") -> dict[str, str]:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if os.path.relpath(dirpath, root).split(os.sep)[0] == skip:
            continue
        for name in filenames:
            path = os.path.join(dirpath, name)
            with open(path, "rb") as handle:
                out[os.path.relpath(path, root)] = hashlib.sha256(handle.read()).hexdigest()
    return out


@pytest.fixture
def docs(tmp_path):
    root = tmp_path / "Docs"
    for rel, text in {"README.md": "# Readme\n", "guide/install.md": "# Install\n",
                      "guide/use.md": "# Use\n", "notes/diagram.png": "png",
                      "node_modules/pkg/README.md": "# dep\n", ".git/HEAD": "ref\n",
                      ".obsidian/app.json": "{}", ".github/CONTRIBUTING.md": "# hi\n"}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


# --- Adopt ---------------------------------------------------------------------------

def test_the_plan_changes_nothing(docs):
    before = hashes(docs)
    plan = content_roots.plan_adopt(docs)
    assert plan["survey_fingerprint"] == survey(docs).fingerprint
    assert "node_modules" in plan["excludes"]
    assert hashes(docs) == before and not (docs / ".librarian").exists()


def test_adopting_writes_operational_state_only_and_keeps_every_document(docs):
    before = hashes(docs)
    plan = content_roots.plan_adopt(docs, name="Team docs")
    applied = content_roots.apply_adopt(docs, plan["survey_fingerprint"], name="Team docs")
    assert applied["applied"] is True
    assert hashes(docs) == before                           # byte-identical documents
    state = sorted(p.relative_to(docs / ".librarian").as_posix()
                   for p in (docs / ".librarian").rglob("*"))
    assert state == sorted(["config.toml", "content-roots.json", ".gitignore", "derived",
                            "sessions", "queue", "staging", "quarantine", "eval"])
    assert not any(p.suffix == ".md" for p in (docs / ".librarian").rglob("*"))
    vault = Vault.find(docs)
    assert vault.exists() and vault.config()["vault"]["name"] == "Team docs"
    manifest = content_roots.load(docs)
    assert manifest["mode"] == "adopt" and manifest["survey_fingerprint"] == plan[
        "survey_fingerprint"]
    assert manifest["roots"] == [{"path": ".", "access": "read_write"}]
    assert not (docs / ".gitignore").exists() and not (docs / "About").exists()


def test_a_changed_tree_invalidates_the_plan_and_nothing_is_written(docs):
    plan = content_roots.plan_adopt(docs)
    (docs / "guide" / "new.md").write_text("# New\n", encoding="utf-8")
    with pytest.raises(Refusal, match="ADOPTION_PLAN_STALE"):
        content_roots.apply_adopt(docs, plan["survey_fingerprint"])
    assert not (docs / ".librarian").exists()


def test_an_unrelated_librarian_folder_halts_adoption(docs):
    (docs / ".librarian").mkdir()
    (docs / ".librarian" / "notes.txt").write_text("not ours", encoding="utf-8")
    with pytest.raises(Refusal, match="ADOPTION_STOPPED.*never reused"):
        content_roots.plan_adopt(docs)
    assert [p.name for p in (docs / ".librarian").iterdir()] == ["notes.txt"]


def test_an_adopted_folder_is_not_adopted_twice(docs):
    content_roots.apply_adopt(docs, content_roots.plan_adopt(docs)["survey_fingerprint"])
    with pytest.raises(Refusal, match="already a Librarian vault"):
        content_roots.plan_adopt(docs)


def test_the_cli_plans_then_applies(docs, capsys):
    assert main(["adopt", str(docs)]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert not (docs / ".librarian").exists()
    assert main(["adopt", str(docs), "--fingerprint", plan["survey_fingerprint"]]) == 0
    assert json.loads(capsys.readouterr().out)["applied"] is True


# --- Attach --------------------------------------------------------------------------

def test_attaching_records_a_read_only_root_and_writes_nothing_into_it(docs, tmp_path):
    init(tmp_path / "Lib", name="Lib")
    vault = Vault(tmp_path / "Lib")
    before = hashes(docs, skip="")
    plan = content_roots.plan_attach(vault, docs)
    content_roots.apply_attach(vault, docs, plan["survey_fingerprint"])
    assert hashes(docs, skip="") == before and not (docs / ".librarian").exists()
    roots = content_roots.load(vault.root)["roots"]
    assert roots[-1]["path"] == str(docs.resolve()) and roots[-1]["access"] == "read_only"
    assert content_roots.watch_scope(vault.root) == (["."], set())   # never watched here


def test_attaching_a_folder_that_overlaps_the_library_is_refused(tmp_path):
    init(tmp_path / "Lib", name="Lib")
    vault = Vault(tmp_path / "Lib")
    with pytest.raises(Refusal, match="overlaps the library"):
        content_roots.plan_attach(vault, vault.root / "Sources")


def test_a_stale_attach_plan_is_refused(docs, tmp_path):
    init(tmp_path / "Lib", name="Lib")
    vault = Vault(tmp_path / "Lib")
    plan = content_roots.plan_attach(vault, docs)
    (docs / "README.md").write_text("# Changed, longer\n", encoding="utf-8")
    with pytest.raises(Refusal, match="ADOPTION_PLAN_STALE"):
        content_roots.apply_attach(vault, docs, plan["survey_fingerprint"])
    assert content_roots.load(vault.root) is None


# --- the scoped watcher --------------------------------------------------------------

def adopted(docs):
    content_roots.apply_adopt(docs, content_roots.plan_adopt(docs)["survey_fingerprint"])
    vault = Vault(docs)
    return vault, DocumentLeases(vault)


def test_the_watcher_skips_excluded_and_hidden_folders(docs):
    vault, leases = adopted(docs)
    watcher = VaultWatcher(vault, leases)
    known = watcher._snapshot()
    assert sorted(known) == ["README.md", "guide/install.md", "guide/use.md"]
    assert watcher.health()["scope"]["excludes"][:1] == [".git"]


def test_the_watcher_still_sees_edits_and_deletions_in_its_roots(docs):
    vault, leases = adopted(docs)
    watcher = VaultWatcher(vault, leases)
    watcher._known = watcher._snapshot()
    (docs / "guide" / "use.md").write_text("# Use, edited\n", encoding="utf-8")
    (docs / "guide" / "install.md").unlink()
    (docs / "node_modules" / "pkg" / "README.md").write_text("# ignored\n", encoding="utf-8")
    watcher.scan_once()
    assert {"guide/use.md", "guide/install.md"} <= set(leases._changed)
    assert "node_modules/pkg/README.md" not in leases._changed


def big_tree(root: Path, files: int) -> None:
    for n in range(files):
        folder = root / f"section-{n // 500:03d}"
        if n % 500 == 0:
            folder.mkdir(parents=True, exist_ok=True)
        (folder / f"doc-{n:05d}.md").write_text(f"# Doc {n}\n", encoding="utf-8")


def watcher_budget(tmp_path: Path, files: int, seconds: float) -> dict:
    """Run the real watcher thread over a large adopted tree; measure CPU and latency."""
    root = tmp_path / "Big"
    big_tree(root, files)
    content_roots.apply_adopt(root, content_roots.plan_adopt(root)["survey_fingerprint"])
    vault = Vault(root)
    leases = DocumentLeases(vault)
    watcher = VaultWatcher(vault, leases)
    watcher.start()
    try:
        cpu, wall = time.process_time(), time.perf_counter()
        time.sleep(seconds)
        share = (time.process_time() - cpu) / (time.perf_counter() - wall)
        health = watcher.health()["scope"]
        edited, deleted = "section-001/doc-00600.md", "section-002/doc-01100.md"
        (root / edited).write_text("# edited\n", encoding="utf-8")
        (root / deleted).unlink()
        started = time.perf_counter()
        while not {edited, deleted} <= set(leases._changed):
            assert time.perf_counter() - started < 60, "edit or deletion not detected"
            time.sleep(0.05)
        latency = time.perf_counter() - started
    finally:
        watcher.close()
    return {"files": files, "cpu_share": round(share, 3), "detect_seconds": round(latency, 2),
            "scan_seconds": health["scan_seconds"], "interval": health["interval"],
            "watched": health["watched"]}


# The recorded budget: polling may use at most a fifth of one core on average,
# and an edit or deletion must still be seen.
CPU_BUDGET = 0.20


def test_the_watcher_stays_within_its_cpu_budget_on_2000_files(tmp_path):
    measured = watcher_budget(tmp_path, 2_000, 3.0)
    assert measured["watched"] == 2_000
    assert measured["cpu_share"] <= CPU_BUDGET, measured


@pytest.mark.slow
def test_the_watcher_stays_within_its_cpu_budget_on_20000_files(tmp_path):
    measured = watcher_budget(tmp_path, 20_000, 10.0)
    print(measured)
    assert measured["watched"] == 20_000
    assert measured["cpu_share"] <= CPU_BUDGET, measured
