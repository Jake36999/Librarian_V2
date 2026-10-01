"""The Desk: a persisted, per-pursuit working set - pinned notes, then
automatically-ranked recent ones, decaying with time (Co-work Roadmap 2B)."""
from __future__ import annotations

from .. import desk
from ..registry import Card, Context, tool
from .library import engine_for


def _project_row(ctx: Context, project: str) -> dict:
    row = engine_for(ctx).index.note_row(project)
    if row is None or row["shape"] != "project":
        raise TypeError(f"no pursuit named {project!r}; create_project first")
    return row


def _note_row(ctx: Context, note: str) -> dict:
    row = engine_for(ctx).index.note_row(note)
    if row is None:
        raise TypeError(f"no note named {note!r}; names are exact, including owner prefixes")
    return row


@tool("desk_show", tier="consult", effect="read",
      returns=("project", "working_set"),
      card=Card("A pursuit's working set: pinned notes, then automatically-ranked recent "
                "ones, decaying with time",
                "picking this pursuit back up, or before deciding what to read next",
                "Ranked from the pursuit's own sessions (what was used or written) and "
                "notes touched on the desk directly; nothing is copied between the two - "
                "each call reads them fresh"))
def desk_show(ctx: Context, project: str, limit: int = 20) -> dict:
    _project_row(ctx, project)
    return {"project": project,
            "working_set": desk.DeskStore(ctx.vault).working_set(project, limit)}


@tool("desk_pin", tier="contribute", effect="write", scope="session",
      resolve={"note": "note"},
      returns=("project", "note"),
      card=Card("Pin a note to a pursuit's desk - a pin never decays out of the working set",
                "a note is central to this pursuit and should always be there"))
def desk_pin(ctx: Context, project: str, note: str) -> dict:
    _project_row(ctx, project)
    row = _note_row(ctx, note)
    desk.DeskStore(ctx.vault).pin(project, row["name"])
    return {"project": project, "note": row["name"]}


@tool("desk_unpin", tier="contribute", effect="write", scope="session",
      resolve={"note": "note"},
      returns=("project", "note", "unpinned"),
      card=Card("Unpin a note from a pursuit's desk - it still shows while it decays",
                "a note is no longer central to this pursuit"))
def desk_unpin(ctx: Context, project: str, note: str) -> dict:
    _project_row(ctx, project)
    unpinned = desk.DeskStore(ctx.vault).unpin(project, note)
    return {"project": project, "note": note, "unpinned": unpinned}


@tool("desk_touch", tier="consult", effect="write", scope="session",
      returns=("project", "note"),
      card=Card("Record that a note was just used on this pursuit's desk - opened in the "
                "pane, or attached in a message - so it joins the automatically-recent ones",
                "the person just opened or attached a note while working on this pursuit"))
def desk_touch(ctx: Context, project: str, note: str) -> dict:
    _project_row(ctx, project)
    row = _note_row(ctx, note)
    desk.DeskStore(ctx.vault).touch(project, row["name"])
    return {"project": project, "note": row["name"]}
