"""The source-copy setup selects only the release-supported Python range."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "setup-python.ps1"
SETUP = ROOT / "scripts" / "setup.ps1"


def _powershell() -> str:
    executable = shutil.which("pwsh") or shutil.which("powershell")
    if executable is None:
        pytest.skip("PowerShell is required to exercise the Windows setup probe")
    return executable


def _probe(executable: Path) -> str:
    helper = str(HELPER).replace("'", "''")
    environment = {**os.environ, "LIBRARIAN_TEST_PYTHON": str(executable)}
    command = (f". '{helper}'; "
               "$value = Get-LibrarianPythonVersion -Exe $env:LIBRARIAN_TEST_PYTHON; "
               "if ($null -eq $value) { 'UNSUPPORTED' } else { $value }")
    result = subprocess.run(
        [_powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=True, capture_output=True, text=True, env=environment, timeout=15)
    return result.stdout.strip()


def _find_requested(executable: Path) -> str:
    helper = str(HELPER).replace("'", "''")
    environment = {**os.environ, "LIBRARIAN_TEST_PYTHON": str(executable)}
    command = (f". '{helper}'; "
               "$value = Find-LibrarianPython -Requested $env:LIBRARIAN_TEST_PYTHON; "
               "if ($null -eq $value) { 'NONE' } else { $value.Version }")
    result = subprocess.run(
        [_powershell(), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        check=True, capture_output=True, text=True, env=environment, timeout=15)
    return result.stdout.strip()


def test_setup_accepts_the_current_supported_interpreter() -> None:
    expected = f"{sys.version_info.major}.{sys.version_info.minor}"
    if expected not in {"3.11", "3.12", "3.13"}:
        pytest.skip("the test runner itself is outside the supported release matrix")
    assert _probe(Path(sys.executable)) == expected


@pytest.mark.parametrize("version,expected", [
    ("3.10", "UNSUPPORTED"),
    ("3.11", "3.11"),
    ("3.13", "3.13"),
    ("3.14", "UNSUPPORTED"),
    ("4.0", "UNSUPPORTED"),
])
def test_setup_probe_enforces_both_version_bounds(
        tmp_path: Path, version: str, expected: str) -> None:
    if os.name != "nt":
        pytest.skip("the source-copy setup is a Windows PowerShell entry point")
    fake = tmp_path / "python.cmd"
    fake.write_text(f"@echo off\r\necho {version}\r\nexit /b 0\r\n", encoding="ascii")
    assert _probe(fake) == expected


def test_setup_validates_an_existing_environment_and_never_requests_314() -> None:
    helper = HELPER.read_text(encoding="utf-8")
    setup = SETUP.read_text(encoding="utf-8")
    assert "$script:LibrarianSupportedPythonMinors = @(13, 12, 11)" in helper
    assert 'Get-LibrarianPythonVersion -Exe $VenvPython' in setup
    assert "An explicit interpreter is a contract" in helper
    assert "Remove $Venv and run setup again" in setup
    assert '"3.14"' not in helper
    assert "3.11 or later" not in setup


@pytest.mark.skipif(os.name != "nt", reason="the source-copy setup is Windows PowerShell")
def test_an_explicit_unsupported_interpreter_never_falls_back(tmp_path: Path) -> None:
    unsupported = tmp_path / "python314.cmd"
    unsupported.write_text("@echo off\r\necho 3.14\r\nexit /b 0\r\n", encoding="ascii")
    supported = tmp_path / "python312.cmd"
    supported.write_text("@echo off\r\necho 3.12\r\nexit /b 0\r\n", encoding="ascii")

    assert _find_requested(unsupported) == "NONE"
    assert _find_requested(supported) == "3.12"
