"""A new library opens with a guide: what the Librarian is, how to use it, and links (the same
[[wikilinks]] Obsidian follows) to the formal notes that sit beside it."""
import re

from resource_librarian import notes, tools  # noqa: F401  (registers the tools)
from resource_librarian.init import init
from resource_librarian.registry import REGISTRY

GUIDE = "About the Librarian and how to use it"


def test_a_new_library_has_the_guide_at_its_root(tmp_path):
    report = init(tmp_path / "lib", name="Guide Test")
    assert f"{GUIDE}.md" in report.created
    loaded = notes.load(tmp_path / "lib" / f"{GUIDE}.md")
    assert loaded.frontmatter["type"] == "about"
    assert "Guide Test" in loaded.body                              # the library's own name


def test_every_link_in_the_guide_leads_to_a_note_in_the_library(tmp_path):
    init(tmp_path / "lib", name="Guide Test")
    root = tmp_path / "lib"
    body = (root / f"{GUIDE}.md").read_text(encoding="utf-8")
    targets = {t.split("|")[0].split("#")[0].strip() for t in re.findall(r"\[\[([^\]]+)\]\]", body)}
    assert len(targets) >= 6, targets                               # it really does lead somewhere
    present = {p.stem for p in root.rglob("*.md") if ".librarian" not in p.parts}
    assert sorted(targets - present) == []


def test_the_tool_reference_is_generated_from_the_registry(tmp_path):
    init(tmp_path / "lib", name="Guide Test")
    text = (tmp_path / "lib" / "About" / "Tool Reference.md").read_text(encoding="utf-8")
    assert 'type: "about"' in text
    for name in ("open_session", "advance", "staging_decide", "intake_run"):
        assert f"`{name}`" in text
    assert all(f"`{n}`" in text for n in REGISTRY.names())          # nothing left out
