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
    assert routes == {("GET", "/health"), ("POST", "/replay"), ("GET", "/status")}
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


# Test Directive A3 (2026-10-01): what the reader missed in four real repositories, in
# miniature - Go routes on any receiver and in `_examples/`, Java and Spring, NestJS's
# decorators. FastAPI's and Flask's decorators were already read; held here too.
def test_go_routes_on_any_receiver_and_its_underscored_examples(tmp_path):
    root = tmp_path / "chi"
    write(root, "middleware/profiler.go", 'package middleware\n\nfunc Profiler() {\n'
          '\tr.HandleFunc("/pprof/*", pprof.Index)\n\tr.Get("/vars", expVars)\n}\n')
    write(root, "gin.go", 'package web\n\nfunc Mount() { e.POST("/login", login) }\n')
    write(root, "route_headers.go", 'package middleware\n\n// Usage:\n//   r.Get("/long", h)\n'
          '/*\n *   r.Get("/doc", h)\n */\nfunc RouteHeaders() {}\n')
    write(root, "_examples/hello/main.go", 'package main\n\nfunc main() {\n'
          '\tr := chi.NewRouter()\n\tr.Get("/", hello)\n\thttp.Get("https://x.example/")\n}\n')
    s = structure.survey(root)
    assert {(r["method"], r["path"]) for r in s["routes"]} == {
        ("-", "/pprof/*"), ("GET", "/vars"), ("POST", "/login")}
    assert s["example_routes"] == 1
    assert not any(e["kind"] == "go main" for e in s["entry_points"])    # an example's main


def test_java_and_spring(tmp_path):
    root = tmp_path / "gs-rest-service"
    base = "complete/src/main/java/com/example/restservice"
    write(root, f"{base}/RestServiceApplication.java",
          "package com.example.restservice;\n\n@SpringBootApplication\n"
          "public class RestServiceApplication {\n"
          "    public static void main(String[] args) {\n"
          "        SpringApplication.run(RestServiceApplication.class, args);\n    }\n}\n")
    write(root, f"{base}/GreetingController.java",
          "package com.example.restservice;\n\n@RestController\n@RequestMapping(\"/api\")\n"
          "public class GreetingController {\n"
          "    private final String token = System.getenv(\"GREETING_API_TOKEN\");\n"
          "    @GetMapping(\"/greeting\")\n    public Greeting greeting() { return null; }\n"
          "    @PostMapping\n    public void make() {}\n"
          "    @RequestMapping(value = \"/old\", method = RequestMethod.PUT)\n"
          "    public void old() {}\n}\n")
    write(root, f"{base}/Tool.java", "public class Tool {\n"
          "    public static void main(final String... args) {}\n}\n")
    write(root, "complete/src/main/resources/application.properties",
          "server.port=8080\nspring.datasource.password=${DB_PASSWORD}\n")
    write(root, "complete/src/main/resources/application.yml",
          "greeting:\n  template: 'Hello, %s!'\n")
    write(root, "complete/src/test/resources/application.properties", "test.only=1\n")
    write(root, "samples/src/main/java/demo/Demo.java", "public class Demo {\n"
          "    public static void main(String[] args) {}\n}\n")     # still an example
    s = structure.survey(root)
    kinds = {(e["kind"], e["name"]) for e in s["entry_points"]}
    assert ("Spring Boot application", f"{base}/RestServiceApplication.java") in kinds
    assert ("java main", f"{base}/Tool.java") in kinds
    assert {(r["method"], r["path"]) for r in s["routes"]} == {
        ("GET", "/api/greeting"), ("POST", "/api"), ("PUT", "/api/old")}
    env = {e["name"]: e for e in s["environment"]}
    assert env["GREETING_API_TOKEN"]["credential"]
    assert env["spring.datasource.password"]["credential"] and env["DB_PASSWORD"]["credential"]
    assert not env["server.port"]["credential"] and "greeting.template" in env
    assert "test.only" not in env
    assert "8080" not in json.dumps(s) and "Hello" not in json.dumps(s)   # keys, never values
    section = structure.access_points_section(s)
    assert "**Spring Boot application**" in section
    assert "**Runnable files** (1): `" in section and "Tool.java" in section


def test_nestjs_decorators_under_their_controller(tmp_path):
    root = tmp_path / "typescript-starter"
    write(root, "src/app.controller.ts", "@Controller()\nexport class AppController {\n"
          "  @Get()\n  getHello(): string { return 'hi'; }\n}\n")
    write(root, "src/cats/cats.controller.ts", "@Controller('cats')\n"
          "export class CatsController {\n  @Get(':id')\n  findOne() {}\n"
          "  @Post()\n  create() {}\n}\n")
    s = structure.survey(root)
    assert {(r["method"], r["path"]) for r in s["routes"]} == {
        ("GET", "/"), ("GET", "/cats/:id"), ("POST", "/cats")}


def test_fastapi_and_flask_decorators_keep_their_verbs(tmp_path):
    root = tmp_path / "svc"
    write(root, "svc/api.py", "router = APIRouter()\n\n@router.get('/items/{item_id}')\n"
          "def item(item_id: int):\n    pass\n\n@bp.route('/ping', methods=['GET', 'HEAD'])\n"
          "def ping():\n    pass\n")
    s = structure.survey(root)
    assert {(r["method"], r["path"]) for r in s["routes"]} == {
        ("GET", "/items/{item_id}"), ("GET,HEAD", "/ping")}
