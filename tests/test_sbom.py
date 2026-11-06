"""MF-043e: the software bill of materials says what ships apart from what built it, and
claims no version it was not given."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("make_sbom", ROOT / "scripts" / "make_sbom.py")
make_sbom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(make_sbom)

H1, H2 = "a" * 64, "b" * 64


def wheel(tmp_path: Path) -> Path:
    path = tmp_path / "demo_pkg-1.2.3-py3-none-any.whl"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("demo_pkg-1.2.3.dist-info/METADATA", "\n".join([
            "Metadata-Version: 2.1", "Name: demo-pkg", "Version: 1.2.3",
            "Requires-Dist: PyYAML>=6", "Requires-Dist: keyring<27,>=25",
            'Requires-Dist: numpy>=1.26; extra == "search"', ""]))
    return path


def lock(tmp_path: Path, name: str, lines: list[str]) -> Path:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_a_candidate_lists_runtime_requirements_unresolved_and_the_build_tools_as_excluded(tmp_path):
    build_lock = lock(tmp_path, "build.txt", [f"build==1.6.1 \\", f"    --hash=sha256:{H1}"])
    npm_lock = tmp_path / "package-lock.json"
    npm_lock.write_text(json.dumps({"packages": {"": {"name": "ui"}, "node_modules/esbuild": {
        "version": "0.28.2", "integrity": "sha512-" + "QUJD" * 22}}}), encoding="utf-8")
    bom = make_sbom.build(wheel(tmp_path), None, build_lock, [npm_lock])
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.5"
    main = bom["metadata"]["component"]
    assert main["purl"] == "pkg:pypi/demo-pkg@1.2.3"
    assert main["hashes"][0]["content"] == hashlib.sha256(wheel(tmp_path).read_bytes()).hexdigest()
    by_name = {c["name"]: c for c in bom["components"]}
    assert set(by_name) == {"PyYAML", "keyring", "build", "esbuild"}        # no optional extra
    assert by_name["PyYAML"]["scope"] == "required" and "version" not in by_name["PyYAML"]
    assert {"name": "librarian:resolution", "value": "unresolved: no lock"} in \
        by_name["keyring"]["properties"]
    assert by_name["build"]["scope"] == "excluded" and by_name["build"]["hashes"][0]["content"] == H1
    assert by_name["esbuild"]["scope"] == "excluded" and by_name["esbuild"]["hashes"][0]["alg"] == "SHA-512"
    assert bom["dependencies"] == [{"ref": main["bom-ref"],
                                    "dependsOn": ["pkg:pypi/keyring", "pkg:pypi/pyyaml"]}]


def test_a_stable_lock_pins_every_shipped_package_with_its_hashes(tmp_path):
    release = lock(tmp_path, "release.lock", [
        "pyyaml==6.0.3 \\", f"    --hash=sha256:{H1} \\", f"    --hash=sha256:{H2}",
        "keyring==25.7.0 \\", f"    --hash=sha256:{H2}",
        "jaraco-classes==3.4.0 \\", f"    --hash=sha256:{H1}"])
    bom = make_sbom.build(wheel(tmp_path), release, None, [])
    by_name = {c["name"]: c for c in bom["components"]}
    assert by_name["pyyaml"]["version"] == "6.0.3"
    assert [h["content"] for h in by_name["pyyaml"]["hashes"]] == [H1, H2]
    assert by_name["jaraco-classes"]["scope"] == "required"          # transitive, from the lock
    assert bom["dependencies"][0]["dependsOn"] == ["pkg:pypi/keyring@25.7.0", "pkg:pypi/pyyaml@6.0.3"]


def test_a_lock_that_misses_a_requirement_is_refused(tmp_path):
    partial = lock(tmp_path, "release.lock", ["pyyaml==6.0.3 \\", f"    --hash=sha256:{H1}"])
    with pytest.raises(SystemExit, match="keyring"):
        make_sbom.build(wheel(tmp_path), partial, None, [])


def test_the_same_inputs_give_the_same_bill(tmp_path, monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1800000000")
    first = make_sbom.build(wheel(tmp_path), None, None, [])
    second = make_sbom.build(wheel(tmp_path), None, None, [])
    assert first == second and first["metadata"]["timestamp"] == "2027-01-15T08:00:00Z"
