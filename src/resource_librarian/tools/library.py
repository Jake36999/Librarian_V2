"""Index, search, notes and measurement: the read side of the library."""
from __future__ import annotations

import json
import re
from typing import Literal

from .. import agenda, desk, evaluation, notes, text
from ..index import Index
from ..registry import Card, Context, tool
from ..search import INTENTS, Engine, search
from ..vault import now_iso

Intent = Literal["orient", "donor", "pattern", "technique", "data", "precedent", "in_text"]
assert set(Intent.__args__) == set(INTENTS)                  # type: ignore[attr-defined]


def engine_for(ctx: Context, refresh: bool = True) -> Engine:
    """One engine per call context, over an index brought up to date first:
    answering from a stale index is a silent failure (`FAILURE_MUST_BE_LOUD`)."""
    cached = ctx.extras.get("engine")
    if cached is None:
        cached = _build_engine(ctx)
        ctx.extras["engine"] = cached
    if refresh:
        # Every call that asks for a current index gets one, cached engine or
        # not; refresh reads only what changed, so this is cheap.
        report = cached.index.refresh()
        documents = text.sync_documents(cached.index)
        if report.upserted or report.removed or report.rebuilt or documents["indexed"]:
            cached.forget()
    return cached


def _build_engine(ctx: Context) -> Engine:
    index = Index(ctx.vault)
    vectors = None
    spec = str(ctx.vault.setting("search", "vectors") or "")
    if spec:
        from ..embed import VectorSearch
        vectors = VectorSearch.from_spec(index, spec)
    config = ctx.vault.config()
    heuristics = {**config.get("heuristics", {}),
                  "data_shaped": config.get("search", {}).get("data_shaped")}
    return Engine(index, heuristics, vectors)


@tool("index", tier="contribute", effect="write",
      returns=("upserted", "unchanged", "removed", "rebuilt", "stats"),
      card=Card("Bring the search index up to date with the notes",
                "notes were edited outside the librarian, or search says the index is stale",
                "Reads only changed files; rebuilds everything only when the content model "
                "changed or `rebuild` is set"))
def index_tool(ctx: Context, rebuild: bool = False) -> dict:
    """The index is derived and disposable; this never touches a note."""
    with Index(ctx.vault) as index:
        report = index.rebuild() if rebuild else index.refresh()
        documents = text.sync_documents(index)
        out = {**report.to_dict(), "documents": documents}
        spec = str(ctx.vault.setting("search", "vectors") or "")
        if spec:
            from ..embed import VectorSearch
            vectors = VectorSearch.from_spec(index, spec)
            out["vectors"] = ({"model": vectors.model, "embedded": vectors.sync()}
                              if not vectors.unavailable else {"error": vectors.unavailable})
        return {**out, "stats": index.stats()}


@tool("index_status", tier="consult", effect="read",
      card=Card("How big the index is and whether it is current",
                "before trusting a search about coverage"))
def index_status(ctx: Context) -> dict:
    with Index(ctx.vault) as index:
        return index.stats()


@tool("search", tier="consult", effect="read",
      returns=("intent", "verdict", "results", "coverage", "advisories"),
      card=Card("Find sources, concepts, applications or passages, with the reason each "
                "came back and a coverage verdict",
                "you need to know what the library holds on something",
                "Intents: orient (where does this sit), donor (what could I take), pattern "
                "(has this shape of problem been named), technique (how is it done, inside "
                "sources), data (datasets), precedent (has it been used before), in_text "
                "(inside document text). Constraints eliminate; read `verdict` beside `rank`"))
def search_tool(ctx: Context, query: str, intent: Intent = "donor",
                constraints: dict | None = None, limit: int = 10, source: str = "") -> dict:
    """`rank` is a position within this answer; `verdict` says whether to trust it."""
    return search(engine_for(ctx), query, intent, constraints, limit, source).to_dict()


@tool("filters", tier="consult", effect="read",
      card=Card("The axes a search can filter on and their permitted values",
                "before passing `constraints` to search"))
def filters_tool(ctx: Context) -> dict:
    return {"axes": engine_for(ctx, refresh=False).permitted_axes("source")}


@tool("get_note", tier="consult", effect="read",
      card=Card("One note by name: its fields, sections and what links to it",
                "a search result is worth reading in full"))
def get_note(ctx: Context, name: str, sections: list[str] | None = None) -> dict:
    """Section text is returned whole; ask for specific sections to keep it short."""
    engine = engine_for(ctx)
    row = engine.index.note_row(name)
    if row is None:
        return {"found": False, "name": name,
                "next_step": "search for it; names are exact, including owner prefixes"}
    note = notes.load(ctx.vault.root / row["path"])
    body = note.sections()
    wanted = {s.lower() for s in sections or []}
    return {"found": True, "name": row["name"], "path": row["path"], "shape": row["shape"],
            "kind": row["kind"], "frontmatter": json.loads(row["frontmatter"]),
            "sections": {h or "opening": t for h, t in body.items()
                         if not wanted or h.lower() in wanted},
            "linked_from": engine.index.linked_from(row["name"])[:50]}


@tool("note_move", tier="contribute", effect="vault_write",
      returns=("path", "updated_links"),
      card=Card("Rename a note, move it to a different folder, or both - updating every "
                "[[link]] to it across the vault so nothing breaks",
                "a note's name no longer fits, or it belongs in a different folder",
                "Refuses a name collision at the destination; only links by the note's bare "
                "name are updated, not one already written as a full path"))
def note_move(ctx: Context, name: str, new_name: str = "", new_folder: str = "") -> dict:
    if not new_name and not new_folder:
        raise TypeError("give a new_name, a new_folder, or both")
    engine = engine_for(ctx)
    row = engine.index.note_row(name)
    if row is None:
        raise TypeError(f"no note named {name!r}; names are exact, including owner prefixes")
    source = ctx.vault.root / row["path"]
    if not source.is_file():
        raise TypeError(f"the index says {name!r} is at {row['path']!r} but that file is "
                        f"gone; run index_tool to refresh")
    folder = ctx.vault.safe_relative(new_folder) if new_folder else source.parent
    target_name = notes.safe_name(new_name) if new_name else source.stem
    if not target_name:
        raise TypeError(f"{new_name!r} is not a usable name")
    target = folder / f"{target_name}.md"
    if target == source:
        raise TypeError("that is already this note's name and folder")
    if target.exists():
        raise TypeError(f"{target.relative_to(ctx.vault.root).as_posix()} already exists")
    folder.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    old_name = row["name"]
    updated: list[str] = []
    if old_name.lower() != target_name.lower():
        for note_path in notes.iter_paths(ctx.vault.root):
            if note_path == target:
                continue
            text = note_path.read_text(encoding="utf-8", errors="replace")
            rewritten, changed = notes.rewrite_wikilinks(text, old_name, target_name)
            if changed:
                note_path.write_text(rewritten, encoding="utf-8")
                updated.append(note_path.relative_to(ctx.vault.root).as_posix())
    engine.index.remove(row["path"])
    engine.index.upsert(target)
    for rel in updated:
        engine.index.upsert(ctx.vault.root / rel, force=True)
    return {"path": target.relative_to(ctx.vault.root).as_posix(), "updated_links": updated}


DUE_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@tool("task_add", tier="contribute", effect="vault_write",
      returns=("note", "task"),
      card=Card("Add a dated task (a Markdown checkbox) to a note's section - Milestones "
                "by default",
                "a pursuit needs a plan, or a next step needs a date",
                "Obsidian Tasks-compatible (`- [ ] … 📅 YYYY-MM-DD`), so the vault stays "
                "usable without the librarian"))
def task_add(ctx: Context, note: str, text: str, due: str = "", heading: str = "Milestones"
            ) -> dict:
    text = notes.one_line(text, "a task")
    if not text:
        raise TypeError("a task needs its text")
    if any(s in text for s in agenda.SIGNIFIERS):
        raise TypeError("a task's text carries no Tasks signifiers (📅 and the like): the date "
                        "goes in `due`")
    if due and not DUE_DATE.match(due):
        raise TypeError("due is a date, YYYY-MM-DD")
    engine = engine_for(ctx)
    row = engine.index.note_row(note)
    if row is None:
        raise TypeError(f"no note named {note!r}; names are exact, including owner prefixes")
    path = ctx.vault.root / row["path"]
    loaded = notes.load(path)
    line = f"- [ ] {text}" + (f" 📅 {due}" if due else "")
    body = notes.append_to_section(loaded.body, heading, line)
    path.write_text(notes.render(loaded.frontmatter, body), encoding="utf-8")
    engine.index.upsert(path)
    return {"note": row["name"], "task": line}


@tool("task_done", tier="contribute", effect="vault_write",
      returns=("note", "done"),
      card=Card("Check off an open task on a note, matched by its text",
                "a milestone or task is finished"))
def task_done(ctx: Context, note: str, text: str) -> dict:
    engine = engine_for(ctx)
    row = engine.index.note_row(note)
    if row is None:
        raise TypeError(f"no note named {note!r}; names are exact, including owner prefixes")
    path = ctx.vault.root / row["path"]
    loaded = notes.load(path)
    task = agenda.find_open(loaded.body, text)
    if task is None:
        raise TypeError(f"no open task {text!r} on {note!r}")
    body = loaded.body[:task.mark_at] + "x" + loaded.body[task.mark_at + 1:]
    path.write_text(notes.render(loaded.frontmatter, body), encoding="utf-8")
    engine.index.upsert(path)
    return {"note": row["name"], "done": text.strip()}


@tool("agenda", tier="consult", effect="read",
      returns=("overdue", "today", "this_week", "later", "undated"),
      card=Card("Every open, dated task across the vault - or one pursuit's - bucketed by "
                "when it falls",
                "picking up where things left off, or a weekly review",
                "Computed fresh from every note's own checkboxes - no daemon, and a task "
                "typed straight into Obsidian counts the same as one added with task_add. "
                "`project` narrows it to that pursuit's note and its desk"))
def agenda_tool(ctx: Context, project: str = "") -> dict:
    if not project:
        return agenda.scan(ctx.vault)
    if not ctx.vault.project_note(project).exists():
        raise TypeError(f"no pursuit named {project!r}; create_project first")
    return agenda.scan(ctx.vault, only=desk.pursuit_notes(ctx.vault, project))


@tool("evaluate", tier="consult", effect="read",
      returns=("questions", "scenarios"),
      card=Card("Score retrieval on this vault's own questions and scenarios",
                "after changing heuristics, adding many sources, or before a sweep",
                "Reads .librarian/eval/questions.json and scenarios.json; reported per slice"))
def evaluate(ctx: Context, k: int = 5) -> dict:
    engine = engine_for(ctx)
    folder = ctx.vault.work("eval")
    out = {"questions": evaluation.run_questions(engine, folder / "questions.json", k),
           "scenarios": evaluation.run_scenarios(engine, folder / "scenarios.json", k)}
    # The sweep gate reads this: retrieval before volume.
    q = out["questions"]
    (folder / "last.json").write_text(json.dumps(
        {"at": now_iso(), "k": k, "total": q["total"], "hit": q.get("hit", 0.0),
         "mrr": q.get("mrr", 0.0), "scenarios_useful": out["scenarios"].get("useful", 0.0)}),
        encoding="utf-8")
    return out
