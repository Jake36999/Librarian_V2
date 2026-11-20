"""Obsidian canvases the Librarian reads and writes (W2, 2026-11-20).

- `document`: parse, validate and hash JSON Canvas 1.0 without losing unknown fields.
- `layout`: deterministic, rectangle-aware layouts that never move a pinned or person-moved node.
- `service`: preview a change, then commit it only if the file is still the one previewed.
- `workflows`: a workflow drawn as a canvas, and a canvas compiled into a workflow.
"""
