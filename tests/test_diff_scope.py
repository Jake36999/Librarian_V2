"""DELEG-03: the pre-landing diff-scope guard refuses changes outside a package."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPOSITORY = Path(__file__).parents[1]
SCRIPTS = REPOSITORY / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("check_diff_scope", SCRIPTS / "check_diff_scope.py")
assert SPEC is not None and SPEC.loader is not None
guard = importlib.util.module_from_spec(SPEC)
sys.modules["check_diff_scope"] = guard  # dataclasses look their module up by name
SPEC.loader.exec_module(guard)

EXAMPLE = json.loads((REPOSITORY / "docs" / "examples" / "work-package-ADAPT-05.json")
                     .read_text(encoding="utf-8"))
ORACLE = "def test_golden():\n    assert render() == 1\n    assert parse() == 2\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "-c", "core.autocrlf=false",
                           "-c", "user.email=t@example.invalid", "-c", "user.name=t", *args],
                          capture_output=True, check=True, text=True).stdout


def write(repo: Path, path: str, text: str | bytes) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        target.write_bytes(text)
    else:
        target.write_text(text, encoding="utf-8", newline="\n")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    write(root, "src/adapter.py", "def render():\n    return 1\n")
    write(root, "src/other.py", "x = 1\n")
    write(root, "tests/fixtures/golden.json", '{"body": 1}\n')
    write(root, "tests/test_golden.py", ORACLE)
    write(root, "tests/test_extra.py", "def test_one():\n    assert True\n\ndef test_two():\n    assert 1\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    return root


def package(repo: Path) -> dict:
    wp = copy.deepcopy(EXAMPLE)
    a = wp["admission"]
    a["base_revision"] = git(repo, "rev-parse", "HEAD").strip()
    a["write_targets"] = ["src/adapter.py", "tests/test_extra.py", "tests/new/"]
    a["forbidden_targets"] = ["tests/fixtures/"]
    a["protected_targets"] = [
        {"path": p, "sha256": hashlib.sha256((repo / p).read_bytes()).hexdigest()}
        for p in ("tests/fixtures/golden.json", "tests/test_golden.py")]
    del wp["completion"]
    return wp


def findings(repo: Path) -> list[tuple[str, str]]:
    text = guard.worktree_diff_text("HEAD", repo)
    return [(f.kind, f.path) for f in guard.scope_findings(package(repo), guard.parse_diff(text))]


def test_an_in_scope_change_and_a_new_worker_test_pass(repo):
    write(repo, "src/adapter.py", "def render():\n    return 2\n")
    write(repo, "tests/new/test_more.py", "def test_more():\n    assert 2\n")
    assert findings(repo) == []


def test_a_file_outside_the_write_targets_is_refused(repo):
    write(repo, "src/other.py", "x = 2\n")
    write(repo, "src/brand_new.py", "y = 1\n")
    assert findings(repo) == [("out_of_scope", "src/brand_new.py"), ("out_of_scope", "src/other.py")]


def test_a_worker_edit_to_a_protected_fixture_is_refused(repo):
    write(repo, "tests/fixtures/golden.json", '{"body": 2}\n')
    assert findings(repo) == [("out_of_scope", "tests/fixtures/golden.json"),
                              ("forbidden", "tests/fixtures/golden.json"),
                              ("protected", "tests/fixtures/golden.json")]


def test_a_deleted_test_is_refused_with_each_lost_test(repo):
    (repo / "tests" / "test_extra.py").unlink()
    assert findings(repo) == [("deleted", "tests/test_extra.py"),
                              ("test_removed", "tests/test_extra.py"),
                              ("test_removed", "tests/test_extra.py"),
                              ("assertions_reduced", "tests/test_extra.py")]


def test_a_renamed_file_is_refused(repo):
    git(repo, "mv", "src/adapter.py", "src/adapter_v2.py")
    kinds = findings(repo)
    assert ("renamed", "src/adapter_v2.py") in kinds
    assert ("out_of_scope", "src/adapter_v2.py") in kinds


def test_a_weakened_assertion_is_refused(repo):
    write(repo, "tests/test_extra.py", "def test_one():\n    pass\n\ndef test_two():\n    assert 1\n")
    assert findings(repo) == [("assertions_reduced", "tests/test_extra.py")]


def test_a_removed_test_function_is_refused_even_with_assertions_kept(repo):
    write(repo, "tests/test_extra.py", "def test_one():\n    assert True\n    assert 1\n")
    assert findings(repo) == [("test_removed", "tests/test_extra.py")]


def test_an_added_skip_is_refused(repo):
    write(repo, "tests/test_extra.py",
          "import pytest\n\n@pytest.mark.skip\ndef test_one():\n    assert True\n\n"
          "def test_two():\n    assert 1\n")
    assert findings(repo) == [("skip_added", "tests/test_extra.py")]


def test_a_binary_file_is_refused(repo):
    write(repo, "tests/new/blob.bin", b"\x00\x01\x02binary")
    assert findings(repo) == [("binary", "tests/new/blob.bin")]


def test_a_committed_range_is_checked_too(repo):
    write(repo, "src/other.py", "x = 3\n")
    git(repo, "commit", "-qam", "worker")
    text = guard.diff_text_from_git("HEAD~1..HEAD", repo)
    found = guard.scope_findings(package(repo), guard.parse_diff(text))
    assert [(f.kind, f.path) for f in found] == [("out_of_scope", "src/other.py")]


def test_command_line_exit_codes(repo, tmp_path, capsys):
    path = tmp_path / "wp.json"
    path.write_text(json.dumps(package(repo)), encoding="utf-8")
    assert guard.main([str(path), "--worktree", "HEAD", "--repository", str(repo)]) == 0
    assert capsys.readouterr().out.strip() == "ok"
    write(repo, "src/other.py", "x = 2\n")
    assert guard.main([str(path), "--worktree", "HEAD", "--repository", str(repo), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["kind"] == "out_of_scope"


# --- parser details -----------------------------------------------------------------

def test_a_removed_line_that_looks_like_a_header_is_content():
    text = ("diff --git a/tests/test_x.py b/tests/test_x.py\n"
            "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n"
            "@@ -1,2 +1,1 @@\n--- assert sentinel\n keep\n")
    (change,) = guard.parse_diff(text)
    assert change.removed == ("-- assert sentinel",) and change.added == ()


def test_quoted_utf8_paths_and_copies_are_parsed():
    text = ('diff --git "a/src/\\303\\251.py" "b/src/\\303\\251.py"\nnew file mode 100644\n'
            '--- /dev/null\n+++ "b/src/\\303\\251.py"\n@@ -0,0 +1 @@\n+x = 1\n'
            "diff --git a/src/a.py b/src/b.py\nsimilarity index 90%\n"
            "copy from src/a.py\ncopy to src/b.py\n")
    added, copied = guard.parse_diff(text)
    assert (added.status, added.old_path, added.new_path) == ("added", None, "src/é.py")
    assert (copied.status, copied.old_path, copied.new_path) == ("copied", "src/a.py", "src/b.py")
    wp = copy.deepcopy(EXAMPLE)
    wp["admission"]["write_targets"] = ["src/b.py"]
    assert guard.scope_findings(wp, [copied]) == []  # the copy's source is unchanged


def test_paths_with_spaces_come_from_the_rename_lines():
    text = ("diff --git a/a b.py b/c d.py\nsimilarity index 100%\n"
            "rename from a b.py\nrename to c d.py\n")
    (change,) = guard.parse_diff(text)
    assert (change.status, change.old_path, change.new_path) == ("renamed", "a b.py", "c d.py")
