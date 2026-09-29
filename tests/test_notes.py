from pathlib import Path

from resource_librarian import notes


def test_parse_round_trip():
    fm, body, err = notes.parse("---\ntype: source\ntags: [a, b]\n---\n\n# T\n\n## One\nx\n")
    assert err == "" and fm == {"type": "source", "tags": ["a", "b"]}
    again = notes.parse(notes.render(fm, body))
    assert again[0] == fm


def test_render_never_collapses_a_scalar_only_frontmatter_to_flow_style():
    """PyYAML's default_flow_style=None puts a mapping of only scalars on one
    `{...}` line; the pane's own frontmatter table is a plain one-`key:
    value`-per-line scan and reads none of a note rendered that way."""
    fm = {"type": "source", "kind": "repository", "title": "x", "status": "active"}
    head = notes.render(fm, "body").splitlines()[1]
    assert not head.startswith("{")
    assert head == "type: source"


def test_render_keeps_list_fields_parseable_after_a_scalar_field():
    fm = {"type": "project", "status": "active", "aliases": ["Alpha", "Beta"]}
    rendered = notes.render(fm, "body")
    assert "aliases:" in rendered and "- Alpha" in rendered
    assert notes.parse(rendered)[0] == fm


def test_bad_yaml_is_reported_not_raised():
    fm, body, err = notes.parse("---\nkey: [unclosed\n---\nbody")
    assert fm == {} and "not valid YAML" in err and "body" in body


def test_non_mapping_frontmatter():
    assert notes.parse("---\n- a\n- b\n---\n")[2] == "frontmatter is not a mapping"


def test_no_frontmatter():
    assert notes.parse("# Just text") == ({}, "# Just text", "")


def test_sections():
    body = notes.compose("T", [("Bottom Line", "short"), ("Evidence", "- a")])
    s = notes.split_sections(body)
    assert s["Bottom Line"] == "short" and s["Evidence"] == "- a" and s[""] == "# T"


def test_iter_paths_skips_dot_directories(tmp_path: Path):
    (tmp_path / "Sources").mkdir()
    (tmp_path / ".librarian").mkdir()
    (tmp_path / "Sources" / "a.md").write_text("x")
    (tmp_path / ".librarian" / "b.md").write_text("x")
    assert [p.name for p in notes.iter_paths(tmp_path)] == ["a.md"]


def test_wikilinks_and_safe_name():
    assert notes.wikilinks("see [[A]] and [[B#h|alias]]") == ["A", "B"]
    assert notes.safe_name('a/b:c*?"<>|d. ') == "abcd"


def test_rewrite_wikilinks_by_bare_name_only():
    text = ("See [[Old Name]], [[Old Name#Claims|the claims]], and "
            "[[Sources/repository/Old Name]]. Not [[Other Note]].")
    out, changed = notes.rewrite_wikilinks(text, "Old Name", "New Name")
    assert changed
    assert out == ("See [[New Name]], [[New Name#Claims|the claims]], and "
                   "[[Sources/repository/New Name]]. Not [[Other Note]].")
    same, changed_again = notes.rewrite_wikilinks("Nothing here links to it.",
                                                   "Old Name", "New Name")
    assert not changed_again and same == "Nothing here links to it."
