"""The registry page's entries are copied from plugin/; they must not drift from it."""
import re
from pathlib import Path

import pytest

from resource_librarian import skill_registry

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"


def front_matter(path):
    text = path.read_text(encoding="utf-8")
    block = text.split("---")[1]
    return dict(re.findall(r"^([a-z-]+):\s*(.+)$", block, flags=re.M))


@pytest.mark.skipif(not PLUGIN.is_dir(), reason="no plugin folder beside the package")
def test_the_commands_match_the_plugin_files():
    found = {}
    for path in sorted((PLUGIN / "commands").glob("*.md")):
        meta = front_matter(path)
        found["/" + path.stem] = (meta.get("argument-hint", "").strip('"'), meta["description"])
    assert {n: (t, d) for n, t, d in skill_registry.COMMANDS} == found


@pytest.mark.skipif(not PLUGIN.is_dir(), reason="no plugin folder beside the package")
def test_the_skills_and_agents_match_the_plugin_files():
    skills = {front_matter(p)["name"] for p in (PLUGIN / "skills").glob("*/SKILL.md")}
    assert {n for n, _ in skill_registry.SKILLS} == skills
    agents = {front_matter(p)["name"] for p in (PLUGIN / "agents").glob("*.md")}
    assert {n for n, _ in skill_registry.AGENTS} == agents


def test_the_page_lists_commands_skills_and_installed_servers():
    page = skill_registry.render_markdown([
        {"name": "semantic-scholar", "enabled": True, "tool_names": ["a", "b"],
         "docs": "https://example.org/docs"}])
    for needle in ("`/research`", "`research-session`", "`clerk`", "semantic-scholar",
                   "<https://example.org/docs>", "[[Tool Reference]]"):
        assert needle in page
    assert "None installed yet" in skill_registry.render_markdown([])


def test_the_core_serves_the_page(vault):
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        out = app.skill_registry()
    finally:
        app.close_runtime()
    assert out["title"] == "Skill registry" and "`/research`" in out["markdown"]
