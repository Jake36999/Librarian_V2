"""Release builds refuse drift between Core and packaged adapter metadata."""
from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_versions.py"
SPEC = importlib.util.spec_from_file_location("check_release_versions", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
versions = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(versions)

METADATA = (
    "VERSION",
    "pyproject.toml",
    "release-manifest.json",
    "src/resource_librarian/__init__.py",
    "obsidian/manifest.json",
    "obsidian/package.json",
    "obsidian/package-lock.json",
    "obsidian/dist/manifest.json",
    "plugin/.claude-plugin/plugin.json",
)


def _copy_metadata(target: Path) -> None:
    for rel in METADATA:
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, destination)


def test_release_metadata_versions_match_the_core() -> None:
    assert versions.validate(ROOT) == {"core": "2.1.0.dev0", "adapter": "2.1.0-dev"}
    assert versions.adapter_version("2.1.0") == "2.1.0"
    with pytest.raises(versions.VersionContractError, match="unsupported Core version form"):
        versions.adapter_version("2.1")


def test_cowork_version_drift_fails_the_release_check(tmp_path: Path) -> None:
    _copy_metadata(tmp_path)
    path = tmp_path / "plugin/.claude-plugin/plugin.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = "2.0.0-dev"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(versions.VersionContractError, match=r"plugin.*2\.0\.0-dev.*2\.1\.0-dev"):
        versions.validate(tmp_path)


def test_a_missing_built_adapter_manifest_fails_the_release_check(tmp_path: Path) -> None:
    _copy_metadata(tmp_path)
    (tmp_path / "obsidian/dist/manifest.json").unlink()

    with pytest.raises(versions.VersionContractError, match=r"cannot read release metadata.*dist"):
        versions.validate(tmp_path)


def test_release_builder_runs_the_shared_version_check() -> None:
    script = (ROOT / "scripts/build-release.ps1").read_text(encoding="utf-8")
    assert 'scripts\\check_release_versions.py' in script
    assert 'Invoke-Native "Release metadata version check"' in script
