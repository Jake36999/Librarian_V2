import json

from resource_librarian import cli
from resource_librarian.registry import REGISTRY


def run(capsys, *argv):
    code = cli.main(list(argv))
    return code, json.loads(capsys.readouterr().out)


def test_every_tool_has_a_subcommand():
    parser = cli.build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert set(REGISTRY.names()) <= set(sub.choices)


def test_init_then_status(tmp_path, capsys):
    code, out = run(capsys, "init", str(tmp_path / "v"), "--name", "V")
    assert code == 0 and ".librarian/config.toml" in out["created"]
    code, out = run(capsys, "--vault", str(tmp_path / "v"), "vault_status")
    assert code == 0 and out["content_model"] == "found" and out["unparsed"] == 0
    code, out = run(capsys, "--vault", str(tmp_path / "v"), "check_notes")
    assert code == 0 and out["ok"], out


def test_refusals_exit_two(tmp_path, capsys):
    run(capsys, "init", str(tmp_path / "v"))
    code, out = run(capsys, "init", str(tmp_path / "v"))
    assert code == 2 and out["refused"] == "VAULT_EXISTS"
    code, out = run(capsys, "--vault", str(tmp_path / "nowhere"), "vault_status")
    assert code == 2 and out["refused"] == "VAULT_REQUIRED"


def test_rules_and_capabilities(capsys):
    code, out = run(capsys, "rules", "--code", "TIER_REFUSED")
    assert code == 0 and out["found"]
    code, out = run(capsys, "--tier", "consult", "capabilities")
    names = {t["name"] for t in out["tools"]}
    # A Reader (consult) searches and records its own use, and nothing else.
    assert {"search", "log_use", "record_application", "open_session"} <= names
    assert not names & {"index", "create_project", "draft_offering", "promote_offering",
                        "answer"}


def test_doctor_never_shows_key_values(capsys, monkeypatch):
    monkeypatch.setenv("DEEPINFRA_API_KEY", "sk-secret-value")
    code, out = run(capsys, "doctor")
    text = json.dumps(out)
    assert "sk-secret-value" not in text
    assert any(c["name"] == "key: DeepInfra" and c["ok"] for c in out["checks"])


def test_search_tools(tmp_path, capsys):
    from conftest import add_source
    run(capsys, "init", str(tmp_path / "v"))
    add_source(tmp_path / "v", "osquery", "Query operating system state with SQL.")
    v = ["--vault", str(tmp_path / "v")]
    code, out = run(capsys, *v, "search", "--query", "operating system SQL")
    assert code == 0 and out["results"][0]["name"] == "osquery" and out["verdict"]
    code, out = run(capsys, *v, "search", "--query", "x", "--constraints",
                    '{"license_class": "nope"}')
    assert code == 1 and out["error"] == "invalid_arguments" and "Permitted" in out["detail"]
    code, out = run(capsys, *v, "get_note", "--name", "osquery")
    assert out["found"] and "Bottom Line" in out["sections"]
    code, out = run(capsys, *v, "index", "--rebuild")
    assert out["rebuilt"] and out["stats"]["notes"] >= 1
    code, out = run(capsys, *v, "filters")
    assert "license_class" in out["axes"]
    code, out = run(capsys, *v, "evaluate")
    assert out["questions"]["total"] == 0


def test_search_is_refused_below_its_tier_only_for_writes(tmp_path, capsys):
    run(capsys, "init", str(tmp_path / "v"))
    code, out = run(capsys, "--vault", str(tmp_path / "v"), "--tier", "consult", "index")
    assert code == 2 and out["refused"] == "TIER_REFUSED"
