"""The librarian's own notes (Requirements Addendum R1, 2026-09-30).

Until now the librarian could write only typed library artifacts - Sources, Concepts,
Offerings, Applications, Project notes - and a person who asked for a study plan or a
reading list got a promise of a file that was never written. These tools write the
librarian's *own* notes, in two places only:

- `Notes/` (and folders under it): notes for the person - a study plan, a reading list,
  meeting notes;
- `Projects/<project>/` (and folders under it): working notes of a pursuit that exists.

Never Sources, Concepts, Indexes, About, Applications or Offerings (those have their own
reviewed writers), never a dot-folder. Every write goes through the permission broker like
any vault write, returns the path and a diff, and is re-indexed so it can be found at once.
A note the librarian wrote carries a digest of its body; if a person has edited it since,
it is never replaced or rewritten wholesale.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from pathlib import Path
from typing import Any, Literal

from .. import notes
from ..registry import Card, Context, tool
from ..rules import Refusal
from ..vault import now_iso
from .library import engine_for

RESERVED = re.compile(r"^(con|prn|aux|nul|com\d|lpt\d)$", re.I)
TYPED_SHAPES = frozenset({"source", "concept", "offering", "application", "project", "about"})
PROTECTED_FIELDS = frozenset({"type", "written_by", "librarian_digest", "archived_from"})


def _digest(body: str) -> str:
    return hashlib.sha256(body.strip().encode("utf-8")).hexdigest()[:16]


def _folder(ctx: Context, folder: str) -> Path:
    """`Notes[/...]` or `Projects/<existing project>[/...]`, confined to the vault."""
    parts = [p for p in folder.replace("\\", "/").strip("/").split("/") if p]
    if not parts or any(p in (".", "..") or p.startswith(".") for p in parts):
        raise TypeError(f"folder {folder!r}: use 'Notes' (or a folder inside it) or "
                        f"'Projects/<project>'")
    head = parts[0].casefold()
    if head == "notes":
        parts[0] = "Notes"
    elif head == "projects" and len(parts) >= 2:
        parts[0] = "Projects"
        if not ctx.vault.project_note(parts[1]).exists():
            raise TypeError(f"no project {parts[1]!r}: create_project first, or write under "
                            f"'Notes'")
    else:
        raise TypeError(f"folder {folder!r} is not one the librarian writes its own notes in: "
                        f"use 'Notes' (or a folder inside it) or 'Projects/<project>'. Sources, "
                        f"Concepts, Offerings and Applications have their own tools")
    path = (ctx.vault.root.joinpath(*parts)).resolve()
    root = ctx.vault.root.resolve()
    if root not in path.parents and path != root:
        raise TypeError(f"folder {folder!r} resolves outside the vault")
    return path


def _note_name(name: str) -> str:
    base = name.strip().removesuffix(".md").strip()
    safe = notes.safe_name(base)
    if not safe or RESERVED.match(safe):
        raise TypeError(f"{name!r} cannot be a note name")
    return safe


def _existing(ctx: Context, name: str) -> list[Path]:
    return [p for p in notes.iter_paths(ctx.vault.root) if p.stem.casefold() == name.casefold()]


def _record(ctx: Context, tool_name: str, rel: str) -> None:
    if ctx.session:
        from .sessions import _event
        _event(ctx, {"type": "write", "tool": tool_name, "path": rel})


def _diff(before: str, after: str, rel: str) -> str:
    lines = difflib.unified_diff(before.splitlines(), after.splitlines(), f"a/{rel}", f"b/{rel}",
                                 lineterm="", n=1)
    text = "\n".join(lines)
    return text if len(text) <= 4000 else text[:4000] + "\n... (diff clipped)"


def _writable(ctx: Context, path: Path) -> None:
    """The edit tools' own confinement: only inside Notes/ or Projects/."""
    rel = path.relative_to(ctx.vault.root).parts
    if not rel or rel[0] not in ("Notes", "Projects"):
        raise TypeError(f"{path.relative_to(ctx.vault.root).as_posix()!r} is not one of the "
                        f"librarian's own notes (Notes/ or Projects/)")


@tool("write_note", tier="contribute", effect="vault_write", scope="session",
      returns=("written", "path", "created", "diff", "findable"),
      card=Card("Write one of your own notes for the person - a study plan, a reading list, "
                "a guide to what you found - in Notes/ or Projects/<project>/",
                "the person asks for a note, plan, list or guide to be saved in the library",
                "folder is 'Notes', or 'Projects/<project>' for a project that already exists "
                "(create_project first). Returns the path: only say a note exists once this "
                "returns it. A research guide whose claims cite sources is an Offering "
                "(draft_offering), not this. mode=replace rewrites only a note you wrote that "
                "nobody has edited since - the way to rewrite a whole note"))
def write_note(ctx: Context, folder: str, name: str, body: str,
               frontmatter: dict | None = None,
               mode: Literal["create", "replace"] = "create") -> dict:
    target = _folder(ctx, folder)
    safe = _note_name(name)
    path = target / f"{safe}.md"
    rel = path.relative_to(ctx.vault.root).as_posix()
    elsewhere = [p for p in _existing(ctx, safe) if p.resolve() != path.resolve()]
    if elsewhere:
        # Note names are unique across the vault (UNIQUE_NOTE_NAMES).
        raise TypeError(f"a note named {safe!r} already exists at "
                        f"{elsewhere[0].relative_to(ctx.vault.root).as_posix()}: choose "
                        f"another name, or edit_note that one")
    fields = {k: v for k, v in (frontmatter or {}).items() if k not in PROTECTED_FIELDS}
    before = ""
    if path.exists():
        if mode != "replace":
            raise TypeError(f"{rel} already exists: mode='replace' rewrites a note you wrote, "
                            f"or use edit_note to change part of it")
        current = notes.load(path)
        fm = current.frontmatter
        if fm.get("written_by") != "librarian" or \
                fm.get("librarian_digest") != _digest(current.body):
            raise Refusal("PERSON_CONFIRMS", f"{rel} has been edited by a person since the "
                                             f"librarian wrote it (or was never the "
                                             f"librarian's): it is not replaced. Use edit_note "
                                             f"to add to it, or ask the person")
        before = path.read_text(encoding="utf-8")
        fields = {**{k: v for k, v in fm.items() if k not in PROTECTED_FIELDS}, **fields}
    text_body = body if body.lstrip().startswith("# ") else f"# {safe}\n\n{body.strip()}\n"
    fm = {"type": "note", **fields, "written_by": "librarian",
          "created": fields.get("created") or now_iso()[:10],
          "librarian_digest": _digest(text_body)}
    if ctx.session:
        fm.setdefault("session", ctx.session)
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = notes.render(fm, text_body)
    path.write_text(rendered, encoding="utf-8")
    engine = engine_for(ctx, refresh=False)
    engine.index.upsert(path)
    _record(ctx, "write_note", rel)
    row = engine.index.note_row(safe)
    out = {"written": rel, "path": rel, "created": not before,
           "diff": _diff(before, rendered, rel),
           # findable by search, not merely indexed: a note with no shape is in no intent
           "findable": row is not None and bool(row["shape"])}
    if row is not None and not row["shape"]:
        out["warning"] = ("written, but this library's content model has no `note` shape, so "
                          "search cannot return it (the `made` intent): a person copies the "
                          "`note` row from the starter Note Content Model's `## Shapes` table "
                          "into About/Note Content Model.md (doctor says the same)")
    return out


@tool("edit_note", tier="contribute", effect="vault_write", scope="session",
      resolve={"note": "note"}, returns=("edited", "path", "diff"),
      card=Card("Add to or replace one section of a note in Notes/ or Projects/, or set its "
                "frontmatter fields (aliases, related, status...)",
                "a note of yours, or a project's working note, needs a section added or "
                "changed",
                "Always name the `section` (its heading) and give `text`: append adds to the "
                "end of it (creating it if missing), replace swaps its text. To rewrite a whole "
                "note you wrote, use write_note(mode='replace'). Sources, Concepts, Offerings "
                "and Applications have their own tools"))
def edit_note(ctx: Context, note: str, section: str = "", text: str = "",
              mode: Literal["append", "replace"] = "append", fields: dict | None = None) -> dict:
    matches = _existing(ctx, notes.safe_name(note) or note)
    if len(matches) != 1:
        raise TypeError(f"no single note named {note!r}" if not matches else
                        f"{note!r} could be any of "
                        f"{[p.relative_to(ctx.vault.root).as_posix() for p in matches]}")
    path = matches[0]
    _writable(ctx, path)
    current = notes.load(path)
    if str(current.frontmatter.get("type", "")) in TYPED_SHAPES - {"project"}:
        raise TypeError(f"{note!r} is a {current.frontmatter['type']} note: it has its own tools")
    if not section and not fields:
        raise TypeError("give a section and text to add or replace, or fields to set")
    before = path.read_text(encoding="utf-8")
    body = current.body
    if section:
        body = (notes.append_to_section(body, section, text) if mode == "append"
                else notes.with_section(body, section, text))
    fm = dict(current.frontmatter)
    blocked = sorted(set(fields or {}) & PROTECTED_FIELDS)
    if blocked:
        raise TypeError(f"fields {blocked} are set by the librarian itself, not edited")
    fm.update(fields or {})
    # Only a note still exactly as the librarian left it keeps a live digest: a person's
    # edit, once made, keeps it protected from replacement.
    if fm.get("written_by") == "librarian" and \
            fm.get("librarian_digest") == _digest(current.body):
        fm["librarian_digest"] = _digest(body)
    rendered = notes.render(fm, body)
    path.write_text(rendered, encoding="utf-8")
    engine_for(ctx, refresh=False).index.upsert(path)
    rel = path.relative_to(ctx.vault.root).as_posix()
    _record(ctx, "edit_note", rel)
    return {"edited": rel, "path": rel, "diff": _diff(before, rendered, rel)}


@tool("update_project", tier="contribute", effect="vault_write", scope="session",
      resolve={"name": "note"}, returns=("updated", "path", "diff"),
      card=Card("Change a Project note after it was created: its stage, goal, summary, "
                "horizon, disqualifiers or fixed constraints",
                "a pursuit's stage or goal has changed, or it was created with too little",
                "Values are checked against the vault's content model"))
def update_project(ctx: Context, name: str, stage: str = "", goal: str = "", summary: str = "",
                   horizon: str = "", disqualifiers: list[str] | None = None,
                   constraints: dict | None = None) -> dict:
    from ..search import Constraints
    from .sessions import _axis_value
    path = ctx.vault.project_note(name)
    if not path.exists():
        raise TypeError(f"no Project note {name!r}: create_project first")
    current = notes.load(path)
    before = path.read_text(encoding="utf-8")
    fm, body = dict(current.frontmatter), current.body
    engine = engine_for(ctx, refresh=False)
    if stage:
        fm["stage"] = _axis_value(engine.index.model, "project", "stage", stage)
    if horizon:
        fm["horizon"] = horizon
    if disqualifiers is not None:
        fm["disqualifiers"] = [d for d in disqualifiers if str(d).strip()]
        body = notes.with_section(body, "Standing Disqualifiers",
                                  "\n".join(f"- {d}" for d in fm["disqualifiers"]) or
                                  "None stated.")
    if constraints is not None:
        bounds = Constraints.of(constraints, engine.permitted_axes("source"))
        fm["constraints"] = {a: list(v) for a, v in bounds.values.items()}
        body = notes.with_section(body, "Fixed Constraints", "\n".join(
            f"- {a}: {', '.join(v)}" for a, v in bounds.values.items()) or "None stated.")
    if goal:
        body = notes.with_section(body, "Goal", goal.strip())
    if summary:
        body = notes.with_section(body, "Summary", summary.strip())
    rendered = notes.render(fm, body)
    if rendered == before:
        return {"updated": path.relative_to(ctx.vault.root).as_posix(), "diff": ""}
    path.write_text(rendered, encoding="utf-8")
    engine.index.upsert(path)
    rel = path.relative_to(ctx.vault.root).as_posix()
    _record(ctx, "update_project", rel)
    return {"updated": rel, "path": rel, "diff": _diff(before, rendered, rel)}


@tool("archive_note", tier="contribute", effect="vault_write", scope="session",
      resolve={"note": "note"}, returns=("archived", "path", "from"),
      card=Card("Move a note out of the way into Archive/, keeping it (nothing is deleted)",
                "a note of yours is obsolete or was written in error",
                "Only your own notes (Notes/, a project's working notes) - never a Source, "
                "Concept, Offering or Application: a duplicate source still in staging is "
                "rejected there (staging_decide), an accepted one is the person's to archive. "
                "Links by name keep resolving"))
def archive_note(ctx: Context, note: str, reason: str) -> dict:
    matches = _existing(ctx, notes.safe_name(note) or note)
    if len(matches) != 1:
        raise TypeError(f"no single note named {note!r}")
    path = matches[0]
    rel = path.relative_to(ctx.vault.root)
    if rel.parts[0] == "Archive":
        raise TypeError(f"{rel.as_posix()} is already archived")
    if ctx.tier != "curate":
        _writable(ctx, path)
        if rel.parts[0] == "Projects" and len(rel.parts) == 2:
            raise TypeError("a Project note itself is archived by the person, not the librarian")
    if not reason.strip():
        raise TypeError("say why it is archived")
    current = notes.load(path)
    fm = {**current.frontmatter, "archived_from": rel.as_posix(), "archived_at": now_iso()[:10],
          "archived_reason": reason.strip()}
    dest = ctx.vault.root / "Archive" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(notes.render(fm, current.body), encoding="utf-8")
    path.unlink()
    engine = engine_for(ctx, refresh=False)
    engine.index.remove(rel.as_posix())
    engine.index.upsert(dest)
    archived = dest.relative_to(ctx.vault.root).as_posix()
    _record(ctx, "archive_note", archived)
    return {"archived": archived, "path": archived, "from": rel.as_posix()}
