"""Agents must be able to read an attached project's ordinary files (owner, 2026-11-16).

Routing preferences (catalogue first, then graph, then source) are never a permission gate.
Hardcoded blocks found on the live Nonlinear Field Lab Core: every dot-segment was refused even
inside an attached project (.github CI config, .gitignore, root dotfiles), and plain-text files
with a suffix outside a whitelist (pytest.ini, setup.cfg, Makefile, LICENSE) were unreadable.
"""
import pytest

from resource_librarian import content_roots
import resource_librarian.tools  # noqa: F401  registers every tool
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault


@pytest.fixture
def project(tmp_path):
    vault = Vault(tmp_path / "library"); vault.root.mkdir()
    (vault.root / ".librarian").mkdir()
    (vault.root / ".librarian" / "app.json").write_text("{}")
    src = tmp_path / "proj"
    files = {".github/workflows/ci.yml": "name: ci\n", ".gitignore": "build/\n", "pytest.ini": "[pytest]\naddopts = -q\n",
             "setup.cfg": "[metadata]\nname = demo\n", "Makefile": "all:\n\techo hi\n", "LICENSE": "MIT\n",
             "Dockerfile": "FROM python:3\n", "src/app.py": "print('hi')\n", ".env": "KEY=secret\n",
             ".env.example": "KEY=\n", ".git/config": "[remote]\nurl = https://u:p@example.com/x\n",
             ".librarian/state.json": "{}", "image.bin": None}
    for rel, text in files.items():
        p = src / rel; p.parent.mkdir(parents=True, exist_ok=True)
        if text is None:
            p.write_bytes(b"\x00\x01\x02\xff" * 64)
        else:
            p.write_text(text)
    manifest = dict(version=1, mode="create", excludes=[], roots=[
        dict(path=".", access="read_write"),
        dict(path=str(src), access="read_only", attached=True, purpose="own-current", authorship="owner_created")])
    content_roots._write_json(content_roots.manifest_path(vault.root), manifest)
    return vault, src


def _read(vault, path):
    out = REGISTRY.call("read_file", {"path": str(path)}, Context(tier="consult", vault=vault))
    assert out.get("refused") != "CLOSED_ACTION_REGISTRY", "tools were not registered in this test"
    out["_failed"] = out.get("error") or out.get("error_detail")      # read_file reports unreadable formats as error_detail
    return out


@pytest.mark.parametrize("rel", [".github/workflows/ci.yml", ".gitignore", "pytest.ini", "setup.cfg", "Makefile",
                                 "LICENSE", "Dockerfile", "src/app.py"])
def test_ordinary_project_files_are_readable_whatever_their_name_or_suffix(project, rel):
    vault, src = project
    out = _read(vault, src / rel)
    assert not out["_failed"], out
    assert out["text"].strip()


@pytest.mark.parametrize("rel", [".env", ".env.example", ".git/config", ".librarian/state.json", "image.bin"])
def test_credentials_vcs_state_other_libraries_and_binaries_stay_unreadable(project, rel):
    vault, src = project
    assert _read(vault, src / rel)["_failed"]       # .env.example stays refused: Wave L's secrets policy


def test_the_vaults_own_private_state_stays_unreadable_by_agents(project):
    vault, _ = project
    assert _read(vault, ".librarian/app.json")["_failed"]
    assert _read(vault, ".hidden/x.md")["_failed"]
