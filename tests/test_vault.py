import pytest

from resource_librarian.init import init
from resource_librarian.rules import Refusal
from resource_librarian.vault import SOURCE_KINDS, WORK_FOLDERS, Vault, render_config
from resource_librarian import notes


def test_init_creates_layout(vault):
    root = vault.root
    assert vault.exists()
    for kind in SOURCE_KINDS:
        assert (root / "Sources" / kind).is_dir()
    for work in WORK_FOLDERS:
        assert (root / ".librarian" / work).is_dir()
    assert (root / ".librarian" / "derived").is_dir() and (root / ".evidence").is_dir()
    assert (root / "About" / "Rules.md").is_file()
    assert ".librarian/derived/" in (root / ".gitignore").read_text()
    assert not (root / "gitignore.txt").exists()


def test_only_derived_is_ignored(vault):
    ignored = [ln.strip() for ln in (vault.root / ".gitignore").read_text().splitlines()
               if ln.strip() and not ln.startswith("#")]
    assert not any(ln.startswith(".librarian") and "derived" not in ln for ln in ignored)
    assert not any(ln.startswith(".evidence") for ln in ignored)


def test_starter_notes_all_parse(vault):
    for path in notes.iter_paths(vault.root):
        assert not notes.load(path).parse_error, path


def test_placeholders_filled(vault):
    readme = (vault.root / "README.md").read_text()
    assert "{name}" not in readme and "{created}" not in readme


def test_config_defaults_and_name(vault):
    assert vault.setting("vault", "name") == "Test Vault"
    assert vault.setting("promotion", "mode") == "person"
    assert vault.setting("heuristics", "rrf_k") == 60


def test_second_init_refused(vault):
    with pytest.raises(Refusal) as exc:
        init(vault.root)
    assert exc.value.code == "VAULT_EXISTS"


def test_init_keeps_existing_files(tmp_path):
    (tmp_path / "About").mkdir()
    (tmp_path / "About" / "Topics.md").write_text("mine")
    report = init(tmp_path)
    assert "About/Topics.md" in report.kept
    assert (tmp_path / "About" / "Topics.md").read_text() == "mine"


def test_find_walks_up_and_refuses_outside(vault, tmp_path):
    assert Vault.find(vault.root / "Sources" / "paper").root == vault.root
    with pytest.raises(Refusal) as exc:
        Vault.find(tmp_path)
    assert exc.value.code == "VAULT_REQUIRED"


def test_layout_guards(vault):
    with pytest.raises(ValueError):
        vault.source_folder("podcast")
    with pytest.raises(ValueError):
        vault.work("derived")


def test_safe_relative_resolves_and_refuses_escape(vault):
    assert vault.safe_relative("Sources/repository") == vault.root / "Sources" / "repository"
    assert vault.safe_relative("") == vault.root
    for bad in ("../outside", ".librarian/config.toml", "a/../../b", ".git"):
        with pytest.raises(Refusal) as exc:
            vault.safe_relative(bad)
        assert exc.value.code == "VAULT_REQUIRED"


def test_render_config_round_trips(tmp_path):
    import tomllib
    data = {"a": {"s": 'q"uote\\', "n": 1, "f": 0.5, "b": True, "l": [1, "x"]}}
    assert tomllib.loads(render_config(data)) == data
