---
type: "about"
status: "active"
authority: "the closed list of community plugins the librarian pairs its own features with. Confirmed against Obsidian's own community-plugins.json on 2026-09-27; re-check before adopting"
---

# Recommended Plugins

> Third-party plugins are not part of the librarian, are not reviewed or maintained by it, and
> run with full access to your vault. Install them at your own risk; the librarian works without
> any of them.

The librarian writes plain Obsidian-Tasks-format checkboxes, standard frontmatter and Markdown
tables - nothing proprietary - so any of these can read what the librarian writes, and the
librarian never needs any of them to be installed. `doctor` reports which of these are present
in this vault (`.obsidian/community-plugins.json`); it never installs, configures or runs any
plugin code.

| Plugin | What it's for | Pairs with | Repository |
| --- | --- | --- | --- |
| Tasks | Due dates, recurring tasks, a query-driven task view | `task_add`/`task_done`, the `agenda` tool | `obsidian-tasks-group/obsidian-tasks` |
| Calendar | A month view of daily notes | Dated Milestones and tasks (W1, 2A) | `liamcain/obsidian-calendar-plugin` |
| Periodic Notes | Daily/weekly/monthly notes on a schedule | The `weekly-review` pipeline (W3) | `liamcain/obsidian-periodic-notes` |
| Reminder | Desktop notifications for dated Markdown tasks | The same checkboxes `task_add` writes | `uphy/obsidian-reminder` |
| Kanban | Markdown-backed boards | Project Milestones as a board, not just a list | `obsidian-community/obsidian-kanban` (formerly `mgmeyers/obsidian-kanban`; now maintained under the Obsidian Community Archive) |
| Dataview | Query the vault's own frontmatter into tables/lists | Any of the librarian's schema-driven fields | `blacksmithgu/obsidian-dataview` |
| Spaced Repetition | Flashcard-style scheduled review | `learn`'s Understanding section (W2) - if present, it owns review scheduling and `review-due` (W4) is not needed | `st3v3nmw/obsidian-spaced-repetition` |
| Zotero Integration | Insert citations, notes and PDF annotations from Zotero | The librarian's existing DOI/arXiv ingest, and any Source note | `obsidian-community/obsidian-zotero-integration` (formerly `mgmeyers/obsidian-zotero-integration`; now maintained under the Obsidian Community Archive) |

Vetting before a plugin is listed here: open-source licence, listed in Obsidian's own community
directory (`community-plugins.json`), no network access beyond its stated purpose. A plugin
moved under the Obsidian Community Archive keeps its listing here as long as it still ships a
working `manifest.json` at its current repository; it is flagged rather than dropped, since a
vault that already depends on it should not be told to stop.

Excluded on principle, whatever a search turns up: filesystem or shell plugins with broad script
execution, and anything advertising itself as a second "memory" or "second brain" layer over the
vault - the vault already is that layer.
