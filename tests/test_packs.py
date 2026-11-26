"""The systems-analysis packs stay checked (implementation plan M0; CI pathway 1).

The packs are the map of the current system and its to-be. Each view records the hash of the spec it
was rendered from, so a spec edited without re-rendering, or a broken cross-pack reference, fails here
rather than passing unnoticed (the 26 November UC-G5 defect passed CI because nothing ran the check).
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ANALYSIS = Path(__file__).resolve().parents[1] / "reports" / "2026-11-25-systems-analysis-finalisation"
RENDER_PACK = ANALYSIS / "render_pack.py"

pytestmark = pytest.mark.skipif(not RENDER_PACK.exists(), reason="systems-analysis packs not present")


def _render_pack():
    spec = importlib.util.spec_from_file_location("render_pack_under_test", RENDER_PACK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_pack_checks_clean():
    run = subprocess.run([sys.executable, str(RENDER_PACK), "--check", "--all"],
                         capture_output=True, text=True, timeout=120)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "0 errors" in run.stdout


def test_a_stale_view_fails_the_check(monkeypatch):
    rp = _render_pack()
    pack = rp.Pack(ANALYSIS / "librarian" / "to-be")
    planted = pack.file_of["agenda"]
    real_sha = rp.sha
    monkeypatch.setattr(rp, "sha", lambda path: "0" * 64 if path == planted else real_sha(path))
    errors, _ = rp.render(pack, write=False)
    assert "agenda: views are older than the spec (re-render)" in errors
    assert not any(e.startswith("acceptance:") for e in errors)


def test_line_endings_do_not_change_a_specs_hash(tmp_path):
    rp = _render_pack()
    lf, crlf = tmp_path / "lf.yaml", tmp_path / "crlf.yaml"
    lf.write_bytes(b"a: 1\nb: 2\n")
    crlf.write_bytes(b"a: 1\r\nb: 2\r\n")
    assert rp.sha(lf) == rp.sha(crlf)
