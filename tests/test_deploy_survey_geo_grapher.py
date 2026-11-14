"""Optional Geo-Grapher partition preview in the deploy survey (Geo-Grapher Phase 6-7 wave 2 Task 4).

The hook is read-only: it only runs `init-workspace --plan-out -` (never --apply/--yes),
and it never writes into the surveyed folder.
"""
import json
import os
import sys
from pathlib import Path

from resource_librarian.deploy_survey import survey

PLAN = {"plan_version": "workspace-init-v1", "partitions": [{"key": "residual"}], "plan_id": "x" * 64}


def listing(root: Path):
    return sorted((str(p.relative_to(root)), p.stat().st_size, p.read_bytes() if p.is_file() else b"")
                  for p in root.rglob("*"))


def fake_command(tmp_path: Path, body: str) -> str:
    script = tmp_path / "fake_geographer.py"
    script.write_text(body, encoding="utf-8")
    return f'"{sys.executable}" "{script}"'


def folder(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "notes.md").write_text("# n\n", encoding="utf-8")
    return root


def test_unset_env_adds_no_geo_grapher_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GEOGRAPHER_INIT", raising=False)
    assert "geo_grapher" not in survey(folder(tmp_path)).to_dict()


def test_fake_command_plan_is_attached_and_folder_untouched(tmp_path, monkeypatch):
    root = folder(tmp_path)
    args_file = tmp_path / "args.json"
    cmd = fake_command(tmp_path, "import json,sys\n"
                       f"json.dump(sys.argv[1:], open(r'{args_file}', 'w'))\n"
                       f"print(json.dumps({PLAN!r}))\n")
    monkeypatch.setenv("GEOGRAPHER_INIT", cmd)
    before = listing(root)
    out = survey(root).to_dict()
    assert out["geo_grapher"]["plan"]["plan_version"] == "workspace-init-v1"
    assert out["geo_grapher"]["command"] == cmd
    args = json.loads(args_file.read_text(encoding="utf-8"))
    assert args[0] == "init-workspace" and "--plan-out" in args and args[args.index("--plan-out") + 1] == "-"
    assert "--apply" not in args and "--yes" not in args
    catalog = Path(args[args.index("--catalog") + 1])
    assert not catalog.is_relative_to(root) and not catalog.parent.exists()  # temp catalog deleted afterwards
    assert listing(root) == before


def test_failing_command_is_an_error_entry_and_survey_is_otherwise_unchanged(tmp_path, monkeypatch):
    root = folder(tmp_path)
    monkeypatch.delenv("GEOGRAPHER_INIT", raising=False)
    baseline = survey(root).to_dict()
    monkeypatch.setenv("GEOGRAPHER_INIT", fake_command(tmp_path, "import sys\nsys.stderr.write('boom ' * 200)\nsys.exit(3)\n"))
    out = survey(root).to_dict()
    entry = out.pop("geo_grapher")
    assert entry["error"] == "GEOGRAPHER_INIT_FAILED" and len(entry["detail"]) <= 300
    assert out == baseline


def test_unparseable_output_and_missing_executable_are_errors(tmp_path, monkeypatch):
    root = folder(tmp_path)
    monkeypatch.setenv("GEOGRAPHER_INIT", fake_command(tmp_path, "print('not json')\n"))
    assert survey(root).to_dict()["geo_grapher"]["error"] == "GEOGRAPHER_INIT_BAD_OUTPUT"
    monkeypatch.setenv("GEOGRAPHER_INIT", str(tmp_path / "does-not-exist.exe"))
    assert survey(root).to_dict()["geo_grapher"]["error"] == "GEOGRAPHER_INIT_UNAVAILABLE"
