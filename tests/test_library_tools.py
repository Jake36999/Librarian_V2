"""tools/library.py's own tools, through the registry: `note_move` in
particular - there was no way at all, for a person or the model, to rename or
move a note before this."""
from resource_librarian import tools  # noqa: F401  (registers tools)
from resource_librarian.registry import REGISTRY, Context

from conftest import add_source


def test_note_move_renames_updates_links_and_reindexes(vault):
    add_source(vault.root, "Alpha", "Alpha parses SQL into lineage graphs.")
    add_source(vault.root, "Beta", "Beta stores the graphs Alpha produces.",
               related="See [[Alpha]] and [[Alpha#Claims|its claims]].")
    ctx = Context(tier="contribute", vault=vault)

    out = REGISTRY.call("note_move", {"name": "Alpha", "new_name": "Alpha Two"}, ctx)
    assert "error" not in out, out
    assert out["path"] == "Sources/repository/Alpha Two.md"
    assert out["updated_links"] == ["Sources/repository/Beta.md"]

    assert not (vault.root / "Sources/repository/Alpha.md").exists()
    assert (vault.root / "Sources/repository/Alpha Two.md").is_file()
    beta_text = (vault.root / "Sources/repository/Beta.md").read_text()
    assert "[[Alpha Two]]" in beta_text and "[[Alpha Two#Claims|its claims]]" in beta_text
    assert "[[Alpha]]" not in beta_text

    from resource_librarian.tools.library import engine_for
    index = engine_for(ctx).index
    assert index.note_row("Alpha") is None
    moved = index.note_row("Alpha Two")
    assert moved is not None and moved["path"] == "Sources/repository/Alpha Two.md"
    assert index.linked_from("Alpha Two") == ["Beta"]


def test_note_move_between_folders_without_renaming(vault):
    add_source(vault.root, "Alpha", "Alpha parses SQL into lineage graphs.")
    ctx = Context(tier="contribute", vault=vault)
    out = REGISTRY.call("note_move", {"name": "Alpha", "new_folder": "Sources/document"}, ctx)
    assert "error" not in out, out
    assert out["path"] == "Sources/document/Alpha.md"
    assert out["updated_links"] == []                      # the name never changed
    assert (vault.root / "Sources/document/Alpha.md").is_file()
    assert not (vault.root / "Sources/repository/Alpha.md").exists()


def test_note_move_refuses_a_collision_and_no_target(vault):
    add_source(vault.root, "Alpha", "one")
    add_source(vault.root, "Beta", "two")
    ctx = Context(tier="contribute", vault=vault)

    collide = REGISTRY.call("note_move", {"name": "Alpha", "new_name": "Beta"}, ctx)
    assert collide["error"] == "invalid_arguments" and "already exists" in collide["detail"]

    nothing = REGISTRY.call("note_move", {"name": "Alpha"}, ctx)
    assert nothing["error"] == "invalid_arguments" and "new_name" in nothing["detail"]

    unknown = REGISTRY.call("note_move", {"name": "Nope", "new_name": "X"}, ctx)
    assert unknown["error"] == "invalid_arguments" and "no note named" in unknown["detail"]
