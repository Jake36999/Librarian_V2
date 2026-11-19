"""The registry page's entries are copied from plugin/; they must not drift from it."""
import re
from pathlib import Path

import pytest

from resource_librarian import skill_registry

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


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
                   "`https://example.org/docs`", "[[Tool Reference]]"):
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


def test_a_servers_name_and_docs_cannot_change_the_page():
    """Stress F-08: values from a server's definition are data. A pipe, a backtick, a newline or
    link syntax in them must not split the row, add columns, start a heading or make a link."""
    hostile_docs = "https://ok.example> [CLICK ME](https://phish.example) | [[About/Rules]]\n\n## Injected"
    page = skill_registry.render_markdown([
        {"name": "evil` | on | 99 | <img src=x>", "enabled": False, "tool_names": [], "docs": hostile_docs},
        {"name": "fine", "enabled": True, "tool_names": ["a"], "docs": "javascript:alert(1)"}])
    lines = page.split("\n")
    server_rows = [r for r in lines if r.startswith("| `") and ("evil" in r or "`fine`" in r)]
    assert len(server_rows) == 2
    for row in server_rows:
        assert len(UNESCAPED_PIPE.split(row.strip().strip("|"))) == 4        # four columns, however it is written
    assert "## Injected" not in page and "](https://phish.example)" not in page
    assert "[[About/Rules]]" not in page
    assert "see the server itself" in page                                  # neither address was a plain URL
    # the commands table keeps its three columns: "[source | lens]" is one cell
    review = next(line for line in lines if line.startswith("| `/review-staging`"))
    assert len(UNESCAPED_PIPE.split(review.strip().strip("|"))) == 3


class _Manager:
    """Two servers installed for the person: one turned on in this library, one not."""
    def status(self):
        return {"on-here": {"enabled": True, "accepted": True, "library_enabled": True,
                            "connected": True, "tools": 1},
                "off-here": {"enabled": True, "accepted": True, "library_enabled": False,
                             "connected": False, "tools": 0}}

    def servers(self):
        return {"on-here": {"command": "x"}, "off-here": {"command": "y"}}

    def tool_names(self, name):
        return ["t"] if name == "on-here" else []

    def __getattr__(self, name):                  # anything else the status view reads
        return lambda *a, **k: {}

    def stop(self):
        pass


@pytest.mark.skipif(not PLUGIN.is_dir(), reason="no plugin folder beside the package")
def test_a_server_not_enabled_in_this_library_is_not_shown_on(vault, monkeypatch):
    """2026-11-19 workflow review: the registry said "on" for a server Health and Settings
    said was not enabled in this library."""
    from resource_librarian.app import App
    from resource_librarian.keys import KeyStore
    seen = {}
    monkeypatch.setattr(skill_registry, "render_markdown",
                        lambda servers: seen.update(servers=servers) or "")
    app = App(vault, coordinate=True, keys=KeyStore(use_keyring=False))
    try:
        saved, app.mcp = app.mcp, _Manager()
        app.mcp_status()                       # raises here, not swallowed by the page
        app.skill_registry()
    finally:
        app.mcp = saved
        app.close_runtime()
    on = {s["name"]: s["enabled"] for s in seen["servers"]}
    assert on == {"off-here": False, "on-here": True}
