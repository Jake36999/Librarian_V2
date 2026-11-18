"""The skill registry page: the skills, "/" commands and agent the Librarian's plugin gives an
agent host, and where to read about the plugins and servers a person installs.

It is built on request (never stored), so it is right for libraries made before it existed and
cannot go stale. The plugin's files live outside the installed package, so the entries below are
copied from `plugin/` and `tests/test_skill_registry.py` fails if the two drift apart."""
from __future__ import annotations

from typing import Any

# (command, what it takes, what it does) - plugin/commands/*.md
COMMANDS: tuple[tuple[str, str, str], ...] = (
    ("/research", "[the question]", "Explore a field or question in the library"),
    ("/new-project", "[what you want to build]", "Frame a new project and supply it from the library"),
    ("/resume", "[session id, or blank to choose]", "Pick a research thread back up"),
    ("/review-staging", "[source | lens]", "Review what waits in staging, a page at a time"),
    ("/check-out", "", "Close the current research thread properly"),
)

# (skill, when it is used) - plugin/skills/*/SKILL.md, trimmed to the first sentence
SKILLS: tuple[tuple[str, str], ...] = (
    ("add-a-project", "Frame a new project in the Librarian vault and supply it from the catalogue"),
    ("apply-and-check-out", "For an agent working on another project that wants to borrow from the "
                            "Librarian catalogue: check in, find what applies, log what you used, check out"),
    ("explore-a-field", "Explore a field or question in the Librarian vault without a project"),
    ("research-session", "How to run any research session in the Librarian vault: the phased walk, "
                         "the session envelope, and what a refusal means"),
    ("write-an-offering", "Write an offering: a short, evidenced recommendation built from kept "
                          "candidates, every claim quoted from its source"),
)

AGENTS: tuple[tuple[str, str], ...] = (
    ("clerk", "Answers the Librarian's waiting clerk tasks, one closed description question about "
              "one text at a time, in its own context"),
)


def render_markdown(servers: list[dict[str, Any]] | None = None) -> str:
    # No title line: the pane shows the page's title above it.
    lines = [
        "What an agent host (Claude, Codex and others) can do with this library, and where to read "
        "about each thing. Skills and commands come from the Librarian plugin; servers are the "
        "outside tools this library has added.", "",
        "Skills and abilities that are not a fixed workflow (searching, recall, graphs, "
        "inspection, writing files) always run under the library's permission mode. A "
        "fixed workflow you start from the paperclip menu is the permission for its own steps.", "",
        "## Commands you can type", "",
        "Typed in the agent host's chat, starting with `/`.", "",
        "| Command | Takes | What it does |", "| --- | --- | --- |"]
    lines += [f"| `{name}` | {takes and f'`{takes}`'} | {does} |" for name, takes, does in COMMANDS]
    lines += ["", "## Skills", "",
              "An agent reads a skill when the situation matches; you do not type these.", "",
              "| Skill | Used for |", "| --- | --- |"]
    lines += [f"| `{name}` | {does} |" for name, does in SKILLS]
    lines += ["", "## Agents", "", "| Agent | What it does |", "| --- | --- |"]
    lines += [f"| `{name}` | {does} |" for name, does in AGENTS]
    lines += ["", "## Installed servers and plugins", ""]
    if servers:
        lines += ["| Name | In this library | Tools | Documentation |", "| --- | --- | --- | --- |"]
        for s in servers:
            docs = s.get("docs") or s.get("homepage") or ""
            lines.append(f"| `{s['name']}` | {'on' if s.get('enabled') else 'off'} | "
                         f"{len(s.get('tool_names') or [])} | {f'<{docs}>' if docs else 'see the server itself'} |")
    else:
        lines.append("None installed yet. Add one from Settings → Tools & integrations.")
    lines += ["", "## Read more", "",
              "- [[About the Librarian and how to use it]]: the pages, workflows and permissions.",
              "- [[Tool Reference]]: every tool, by tier.",
              "- [[Rules]]: every rule the Librarian enforces.",
              "- [[Recommended Plugins]] and [[Recommended MCP Servers]]: outside tools worth adding.", ""]
    return "\n".join(lines)
