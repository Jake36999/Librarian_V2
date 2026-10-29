"""DEPLOY-01: the read-only Create / Adopt / Attach survey."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from resource_librarian.cli import main
from resource_librarian.deploy_survey import survey
from resource_librarian.init import init


def state_of(root: Path) -> dict[str, tuple]:
    """Every entry under root with its bytes' hash, size and modification time."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames:
            out[os.path.relpath(os.path.join(dirpath, name), root)] = ("dir",)
        for name in filenames:
            path = os.path.join(dirpath, name)
            info = os.stat(path)
            with open(path, "rb") as handle:
                out[os.path.relpath(path, root)] = (hashlib.sha256(handle.read()).hexdigest(),
                                                    info.st_size, info.st_mtime_ns)
    return out


@pytest.fixture
def docs(tmp_path):
    """A Git + Obsidian documentation tree with build clutter."""
    root = tmp_path / "Docs"
    for rel, text in {"README.md": "# Readme\n", "guide/install.md": "# Install\n",
                      "guide/use.md": "# Use\n", "notes/idea.markdown": "idea\n",
                      "notes/diagram.png": "png", "node_modules/pkg/README.md": "# dep\n",
                      ".git/HEAD": "ref: refs/heads/main\n",
                      ".obsidian/app.json": "{}"}.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def test_the_survey_writes_nothing(docs):
    before = state_of(docs)
    survey(docs)
    assert state_of(docs) == before
    assert not (docs / ".librarian").exists()


def test_it_reports_what_an_adoption_plan_needs(docs):
    found = survey(docs)
    assert found.exists and found.canonical_root == str(docs.resolve())
    assert found.root_identity["file_id"] == os.stat(docs).st_ino
    assert found.git and found.obsidian
    assert found.librarian == {"state": "absent"}
    assert found.markdown_files == 4                 # node_modules' README is not counted
    assert found.content_candidates == [{"path": ".", "markdown_files": 1},
                                        {"path": "guide", "markdown_files": 2},
                                        {"path": "notes", "markdown_files": 1}]
    excluded = {e["path"]: e["why"] for e in found.exclusion_candidates}
    assert excluded == {".git": "hidden folder", ".obsidian": "hidden folder",
                        "node_modules": "build, cache or dependency folder"}
    assert found.watcher["markdown_files"] == 4
    assert found.modes["adopt"]["possible"] and found.modes["attach"]["possible"]
    assert not found.modes["create"]["possible"]
    assert found.stops == []


def test_an_unrelated_librarian_folder_is_a_hard_stop(docs):
    (docs / ".librarian").mkdir()
    (docs / ".librarian" / "cache.db").write_text("someone else's", encoding="utf-8")
    found = survey(docs)
    assert found.librarian["state"] == "unrelated"
    assert "never reused or replaced" in found.stops[0]
    assert not any(m["possible"] for m in found.modes.values())


def test_a_config_from_another_tool_is_unrelated_too(docs):
    (docs / ".librarian").mkdir()
    (docs / ".librarian" / "config.toml").write_text('[tool]\nname = "other"\n',
                                                     encoding="utf-8")
    assert survey(docs).librarian["state"] == "unrelated"


def test_an_existing_vault_is_recognised_and_not_offered_for_create_or_adopt(tmp_path):
    init(tmp_path / "Lib", name="Mine")
    found = survey(tmp_path / "Lib")
    assert found.librarian["state"] == "librarian_vault" and found.librarian["name"] == "Mine"
    assert not found.modes["create"]["possible"] and not found.modes["adopt"]["possible"]
    assert "already a Librarian vault" in found.modes["adopt"]["why"]
    assert found.stops == []


def test_a_missing_or_empty_folder_can_be_created(tmp_path):
    missing = survey(tmp_path / "new")
    assert not missing.exists and missing.modes["create"]["possible"]
    assert not (tmp_path / "new").exists()
    (tmp_path / "empty").mkdir()
    assert survey(tmp_path / "empty").modes["create"]["possible"]


def test_a_file_is_not_a_root(tmp_path):
    (tmp_path / "f.md").write_text("x", encoding="utf-8")
    assert "is not a folder" in survey(tmp_path / "f.md").stops[0]


def test_the_fingerprint_changes_with_the_tree_and_only_then(docs):
    first = survey(docs).fingerprint
    assert survey(docs).fingerprint == first
    (docs / "guide" / "new.md").write_text("# New\n", encoding="utf-8")
    second = survey(docs).fingerprint
    assert second != first
    (docs / "guide" / "new.md").write_text("# New, longer\n", encoding="utf-8")
    assert survey(docs).fingerprint != second


def test_changes_inside_an_excluded_folder_do_not_move_the_fingerprint(docs):
    first = survey(docs).fingerprint
    (docs / "node_modules" / "pkg" / "index.js").write_text("x", encoding="utf-8")
    assert survey(docs).fingerprint == first


def test_links_and_junctions_are_reported_and_never_followed(docs, tmp_path):
    outside = tmp_path / "Elsewhere"
    outside.mkdir()
    (outside / "secret.md").write_text("# not ours\n", encoding="utf-8")
    link = docs / "linked"
    if sys.platform == "win32":
        made = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                              capture_output=True)
        if made.returncode:
            pytest.skip("could not make a junction here")
    else:
        os.symlink(outside, link, target_is_directory=True)
    found = survey(docs)
    assert [entry["path"] for entry in found.links] == ["linked"]
    assert found.markdown_files == 4                 # secret.md was not counted


def test_case_rule_and_collisions(docs):
    found = survey(docs)
    if sys.platform == "win32":
        assert found.case_insensitive is True
    assert found.case_collisions == []


def test_the_cli_prints_the_survey(docs, capsys):
    assert main(["survey", str(docs)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["fingerprint"] == survey(docs).fingerprint
    assert printed["modes"]["adopt"]["possible"] is True
