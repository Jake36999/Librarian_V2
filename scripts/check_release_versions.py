"""Validate the one release version contract before artifacts are built."""
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path


class VersionContractError(ValueError):
    """Source-controlled release metadata disagrees about its version."""


def adapter_version(core_version: str) -> str:
    """Map the supported Core stable/dev version forms to adapter SemVer."""
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(\.dev\d+)?", core_version)
    if match is None:
        raise VersionContractError(
            f"unsupported Core version form {core_version!r}; use X.Y.Z or X.Y.Z.devN")
    return match.group(1) + ("-dev" if match.group(2) else "")


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VersionContractError(f"cannot read release metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise VersionContractError(f"release metadata {path} is not an object")
    return value


def _require(path: Path, observed: object, expected: str) -> None:
    if observed != expected:
        raise VersionContractError(
            f"{path} version is {observed!r}; expected {expected!r}")


def validate(root: Path) -> dict[str, str]:
    root = root.resolve()
    try:
        core = (root / "VERSION").read_text(encoding="utf-8").strip()
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
        init_text = (root / "src/resource_librarian/__init__.py").read_text(encoding="utf-8")
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise VersionContractError(f"cannot read Core release metadata: {exc}") from exc
    init_match = re.search(r'^__version__\s*=\s*"([^"]+)"', init_text, re.MULTILINE)
    init_version = init_match.group(1) if init_match else None
    _require(root / "pyproject.toml", project.get("project", {}).get("version"), core)
    _require(root / "src/resource_librarian/__init__.py", init_version, core)
    _require(root / "release-manifest.json", _json(root / "release-manifest.json").get("version"), core)

    adapter = adapter_version(core)
    obsidian_files = [
        root / "obsidian/manifest.json",
        root / "obsidian/package.json",
        root / "obsidian/dist/manifest.json",
    ]
    for path in obsidian_files:
        _require(path, _json(path).get("version"), adapter)

    lock_path = root / "obsidian/package-lock.json"
    lock = _json(lock_path)
    _require(lock_path, lock.get("version"), adapter)
    _require(lock_path, (lock.get("packages") or {}).get("", {}).get("version"), adapter)

    cowork_path = root / "plugin/.claude-plugin/plugin.json"
    _require(cowork_path, _json(cowork_path).get("version"), adapter)
    return {"core": core, "adapter": adapter}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        versions = validate(args.root)
    except VersionContractError as exc:
        print(f"release version check failed: {exc}", file=sys.stderr)
        return 2
    print(f"release versions agree: Core {versions['core']}, adapters {versions['adapter']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
