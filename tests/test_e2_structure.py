"""E2': the generated structure oracle accepts a real split and refuses the shortcuts."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "e2_structure.py"
SPEC = importlib.util.spec_from_file_location("e2_structure", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
generator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generator)

BODY = "".join(f"    total += {i}\n" for i in range(30))
BASE = f"""LIMIT = 3


def helper(x):
    return x


def target(values: list[int], *, scale: int = 1) -> int:
    total = 0
{BODY}    return total * scale
"""
SPLIT = f"""LIMIT = 3


def helper(x):
    return x


def _first(total):
{"".join(f"    total += {i}{chr(10)}" for i in range(15))}    return total


def _second(total):
{"".join(f"    total += {i}{chr(10)}" for i in range(15, 30))}    return total


def target(values: list[int], *, scale: int = 1) -> int:
    return _second(_first(0)) * scale
"""
MOVED = f"""LIMIT = 3


def helper(x):
    return x


def _impl(scale):
    total = 0
{BODY}    return total * scale


def target(values: list[int], *, scale: int = 1) -> int:
    return _impl(scale)
"""
TASK = {"id": "E2-T99", "module": "pkg/mod.py", "target": "target",
        "oracle": {"max_target_lines": 20}}


def oracle_failures(tmp_path: Path, source: str) -> list[str]:
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True, exist_ok=True)
    (root / "pkg" / "mod.py").write_text(BASE, encoding="utf-8")
    test = root / "tests" / "e2" / "test_T99_structure.py"
    test.parent.mkdir(parents=True, exist_ok=True)
    test.write_text(generator.render(TASK, root), encoding="utf-8")
    (root / "pkg" / "mod.py").write_text(source, encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", str(test), "-q", "-p", "no:cacheprovider",
                             "--rootdir", str(root)], capture_output=True, text=True, cwd=root)
    return sorted({line.split("::")[1].split()[0] for line in result.stdout.splitlines()
                   if line.startswith("FAILED")})


def test_the_base_fails_only_on_length(tmp_path):
    assert oracle_failures(tmp_path, BASE) == ["test_the_body_is_split_not_moved",
                                               "test_the_target_is_short"]


def test_a_real_split_passes(tmp_path):
    assert oracle_failures(tmp_path, SPLIT) == []


def test_moving_the_body_into_one_helper_fails(tmp_path):
    assert oracle_failures(tmp_path, MOVED) == ["test_the_body_is_split_not_moved"]


@pytest.mark.parametrize("change,failure", [
    (lambda s: s.replace("def _first", "def first").replace("_first(0)", "first(0)"),
     "test_no_public_name_is_added_or_removed"),
    (lambda s: s.replace("*, scale: int = 1) -> int", "*, scale: int = 2) -> int"),
     "test_the_signature_is_unchanged"),
])
def test_surface_changes_fail(tmp_path, change, failure):
    assert oracle_failures(tmp_path, change(SPLIT)) == [failure]
