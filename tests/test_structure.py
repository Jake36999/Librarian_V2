"""Roadmap §4 D5 (2026-09-28): a repository's code structure and access points,
read from a shallow clone by code, nothing in it run, recorded as evidence and
written into the note."""
import json
import shutil
import subprocess

import pytest

from resource_librarian import intake, notes, structure
from resource_librarian.registry import REGISTRY

from test_intake import RESPONSES, accept, ctx, library  # noqa: F401  (fixture)


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def checkout(tmp_path):
    root = tmp_path / "rowstream"
    write(root, "pyproject.toml", '[project]\nname = "rowstream"\n'
                                  '[project.scripts]\nrowstream = "rowstream.cli:main"\n')
    write(root, "rowstream/__init__.py", "")
    write(root, "rowstream/wal.py", "import os\n\nclass WalReader:\n    pass\n\n"
                                    "def read_slot(name):\n    return os.environ['PG_DSN']\n\n"
                                    "def _private():\n    pass\n")
    write(root, "rowstream/api.py", "from flask import Flask\nimport os\napp = Flask(__name__)\n"
                                    "TOKEN = os.getenv('ROWSTREAM_API_TOKEN')\n\n"
                                    "@app.route('/health', methods=['GET'])\ndef health():\n"
                                    "    return 'ok'\n\n@app.post('/replay')\ndef replay():\n"
                                    "    pass\n\nif __name__ == '__main__':\n    app.run()\n")
    write(root, "rowstream/broken.py", "def (:\n")                  # never fatal
    write(root, "web/server.js", "const port = process.env.PORT;\n"
                                 "app.get('/status', (req, res) => res.send('ok'));\n"
                                 "export function start() {}\n")
    write(root, "cmd/tail/main.go", "package main\n\nfunc main() {}\n\nfunc Tail() {}\n")
    write(root, "Dockerfile", 'FROM python:3.12\nCMD ["rowstream", "serve"]\n')
    write(root, ".env.example", "KAFKA_BROKERS=localhost:9092\n")
    write(root, "lib/router.js", "exports.route = function () {};\n"
                                 "proto.handle = function handle() {};\n")
    write(root, "examples/demo.py", "import os\nKEY = os.environ['DEMO_API_KEY']\n"
                                    "@app.get('/demo')\ndef demo():\n    pass\n\n"
                                    "if __name__ == '__main__':\n    demo()\n")
    write(root, "tests/test_wal.py", "def test_it():\n    assert True\n")
    write(root, "node_modules/left-pad/index.js", "export function leftPad() {}\n")
    return root


def test_the_survey_reads_structure_and_access_points(checkout):
    s = structure.survey(checkout)
    assert s["test_files"] == 1 and s["languages"]["python"] == 6
    modules = {m["file"]: m["symbols"] for m in s["modules"]}
    assert modules["rowstream/wal.py"] == ["class WalReader", "def read_slot"]
    assert "start" in modules["web/server.js"] and "Tail" in modules["cmd/tail/main.go"]
    assert modules["lib/router.js"] == ["route", "handle"]
    assert not any(f.startswith(("node_modules", "tests")) for f in modules)
    assert list(modules)[-1] == "examples/demo.py"             # read after its own code
    kinds = {(e["kind"], e["name"]) for e in s["entry_points"]}
    assert ("console script", "rowstream") in kinds
    assert ("__main__ block", "rowstream/api.py") in kinds
    assert ("go main", "cmd/tail/main.go") in kinds
    assert any(k == "container cmd" for k, _ in kinds)
    routes = {(r["method"], r["path"]) for r in s["routes"]}
    assert routes == {("GET", "/health"), ("-", "/replay"), ("GET", "/status")}
    assert s["example_routes"] == 1 and "examples/demo.py" not in {n for _, n in kinds}
    env = {e["name"]: e for e in s["environment"]}
    assert "DEMO_API_KEY" not in env
    assert env["ROWSTREAM_API_TOKEN"]["credential"] and not env["PG_DSN"]["credential"]
    assert env["KAFKA_BROKERS"]["file"] == ".env.example" and "PORT" in env
    section = structure.access_points_section(s)
    assert "`rowstream` → `rowstream.cli:main` (pyproject.toml)" in section
    assert "**Credentials it reads**: `ROWSTREAM_API_TOKEN`" in section
    assert "nothing run" in section


def test_intake_records_it_as_evidence_and_writes_access_points(library, checkout):
    c = ctx(library)
    c.extras["fetcher"] = intake.Replay({**RESPONSES, "clone:acme/rowstream": str(checkout)})
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    item = json.loads((library.work("staging") / "source" / f"{staged['item']}.json").read_text())
    kinds = sorted(e["kind"] for e in item["evidence"])
    assert kinds == ["access_point", "code_structure", "metadata", "readme", "survey"]
    assert "ROWSTREAM_API_TOKEN" in item["sections"]["Access Points"]
    assert "intake_notes" not in item
    result = accept(c, staged["item"])
    note = notes.load(library.root / result["promotion"]["path"])
    assert "`rowstream`" in note.sections()["Access Points"]


def test_a_repository_that_cannot_be_cloned_is_still_staged_with_the_reason(library):
    c = ctx(library)                                     # no checkout recorded
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    item = json.loads((library.work("staging") / "source" / f"{staged['item']}.json").read_text())
    assert item["intake_notes"] == ["not cloned: clone acme/rowstream: none recorded"]
    assert "Access Points" not in item["sections"]


def test_a_repository_over_the_size_limit_is_not_cloned(library, checkout):
    c = ctx(library)
    big = {**RESPONSES["https://api.github.com/repos/acme/rowstream"], "size": 900_000}
    fetcher = intake.Replay({**RESPONSES, "https://api.github.com/repos/acme/rowstream": big,
                             "clone:acme/rowstream": str(checkout)})
    c.extras["fetcher"] = fetcher
    staged = REGISTRY.call("ingest", {"ref": "acme/rowstream"}, c)
    item = json.loads((library.work("staging") / "source" / f"{staged['item']}.json").read_text())
    assert "clone:acme/rowstream" not in fetcher.calls
    assert item["intake_notes"][0].startswith("not cloned: 900 MB")


def test_doctor_says_when_an_older_model_has_no_access_points_section(vault):
    from resource_librarian import doctor
    assert not any(c.name == "content model: access points" for c in doctor.checks(vault))
    model = vault.root / "About" / "Note Content Model.md"
    model.write_text(model.read_text(encoding="utf-8").replace(
        "| 5 | Access Points | optional |\n", ""), encoding="utf-8")
    check = next(c for c in doctor.checks(vault) if c.name == "content model: access points")
    assert not check.ok and "What Is Inside" in check.detail


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_the_clone_refuses_local_paths(tmp_path, checkout):
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    with pytest.raises(structure.CloneError):
        with structure.shallow_clone(checkout.as_uri()):
            pass
