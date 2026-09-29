"""Promotion: a source is catalogued only when it is findable.

One job, six steps, each costing in proportion to the change, not the vault:

1. **Write** the Source note (sections in the content model's order).
2. **Index** that note: its rows, chunks and FTS entries, and vectors for new
   text when vectors are on.
3. **Concepts**: link the source to Concepts whose name or alias its text uses.
   (The concept lifecycle, candidates and thresholds, is M4b; this step only
   links to what exists.)
4. **Index notes**: rewrite the source's topic index and the Master Index's
   counts. A topic index is proportional to its topic, the Master Index to the
   number of topics.
5. **Findability check**: search for the source by its title, by its Bottom
   Line and by one of its concepts; each must return it in the top
   `findability_top_k`. At least one index note must link to it.
6. **Record**: the session's write log, when there is a session.

If step 5 fails, promotion reports "written but not findable", names which
search missed, and flags the note (`needs_attention`) for maintenance
(`FAILURE_MUST_BE_LOUD`).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import notes, schema
from .index import Index
from .rules import Refusal
from .search import Engine, search
from .vault import Vault, now_iso

UNFILED = "Unfiled"
EVIDENCE_HEADING = "Evidence"


@dataclass
class Draft:
    """Everything a Source note is written from. Built by intake or by
    staging review; the job does not care which."""
    name: str
    kind: str
    title: str
    canonical_url: str
    bottom_line: str
    what_it_solves: str
    fields: dict[str, Any] = field(default_factory=dict)     # axes and facts
    sections: dict[str, str] = field(default_factory=dict)   # described sections
    evidence: list[dict[str, Any]] = field(default_factory=list)  # {id, kind, source, fetched_at}
    topic: str = UNFILED
    captured_at: str = ""
    attested_by: str = "person"
    session: str = ""


@dataclass
class Report:
    note: str
    path: str = ""
    steps: dict[str, dict[str, Any]] = field(default_factory=dict)
    catalogued: bool = False

    def step(self, name: str, ok: bool, detail: Any = "") -> None:
        self.steps[name] = {"ok": ok, "detail": detail}

    def to_dict(self) -> dict[str, Any]:
        return {"note": self.note, "path": self.path, "catalogued": self.catalogued,
                "status": "catalogued" if self.catalogued else
                "written but not findable" if self.path else "not written",
                "steps": self.steps}


def _body(draft: Draft, model: schema.ContentModel) -> str:
    order = [s for s, _ in model.sections_for("source", draft.kind)] or \
        ["Bottom Line", "What It Solves", "Evidence"]
    # "What It Solves" and "What It's For" are the same prose slot (the problem a
    # source addresses), worded for software or for a model; a kind whose
    # Content Model uses neither (a paper's own "Claim" instead) gets neither,
    # rather than the text landing under a heading nobody declared.
    sections = {"Bottom Line": draft.bottom_line.strip()}
    for heading in ("What It Solves", "What It's For"):
        if heading in order:
            sections[heading] = draft.what_it_solves.strip()
    sections.update({k: v for k, v in draft.sections.items() if v and v.strip()})
    lines = [f"- `{e['id']}` {e.get('kind', '')} from {e.get('source', '')}"
             f"{', fetched ' + str(e['fetched_at'])[:10] if e.get('fetched_at') else ''}"
             for e in draft.evidence]
    sections[EVIDENCE_HEADING] = "\n".join(lines) or "No fetched evidence is recorded."
    ordered = [(h, sections[h]) for h in order if sections.get(h)]
    ordered += [(h, t) for h, t in sections.items() if h not in order and t]
    return notes.compose(draft.title or draft.name, ordered)


def _concepts(engine: Engine, text: str) -> list[str]:
    """Concepts whose name or alias the note's prose uses, whole-word.

    Headings are left out (`## Architecture & Mechanics` is structure, not a
    use of the concept *Architecture*), and so are concepts named by a word
    that most sources use: a link that holds for half the vault says nothing
    about this source, and could never be searched by."""
    prose = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))
    low = f" {prose.lower()} "
    found = []
    for row in engine.index.conn.execute(
            "SELECT name, aliases FROM note WHERE shape = 'concept'"):
        names = [row["name"]] + [a for a in row["aliases"].split("\n") if a]
        for candidate in names:
            bare = re.sub(r"^(glossary|pattern)\s*-\s*", "", candidate, flags=re.I).strip()
            if len(bare) >= 4 and re.search(rf"(?<![a-z0-9]){re.escape(bare.lower())}"
                                            rf"(?![a-z0-9])", low) and \
                    bare.lower() in engine.selective([bare]):
                found.append(row["name"])
                break
    return sorted(set(found))[:12]


# ------------------------------------------------------------- index notes

def topic_index_path(vault: Vault, topic: str) -> Path:
    return vault.root / "Indexes" / f"Topic - {notes.safe_name(topic)}.md"


def write_topic_index(index: Index, topic: str) -> Path:
    """One topic's index note, from the index: proportional to the topic."""
    rows = index.conn.execute(
        "SELECT n.name, n.kind, n.bottom_line FROM facet f JOIN note n ON n.path = f.path "
        "WHERE f.axis = 'topic' AND f.value = ? AND n.shape = 'source' ORDER BY n.name",
        (topic,)).fetchall()
    path = topic_index_path(index.vault, topic)
    lines = [f"- [[{r['name']}]] ({r['kind']}): "
             f"{' '.join(r['bottom_line'].split())[:160] or 'no Bottom Line yet'}"
             for r in rows]
    body = notes.compose(f"Topic - {topic}", [
        ("About This Index", "Generated by the librarian from the notes filed under this "
                             "topic. Edits here are overwritten."),
        ("Sources", "\n".join(lines) or "None yet.")])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.render({"type": "index", "status": "active", "generated": True,
                                  "topic": topic}, body), encoding="utf-8")
    index.upsert(path)
    return path


CONCEPT_SOURCES = "Sources Using This"


def write_concept_sources(index: Index, concept: str) -> Path | None:
    """The generated list of sources that link a Concept, inside the Concept
    note, in its own section. Only that section is rewritten; the rest of the
    note is the person's. Proportional to the concept's sources."""
    row = index.note_row(concept)
    if row is None or row["shape"] != "concept":
        return None
    path = index.vault.root / row["path"]
    note = notes.load(path)
    sources = index.conn.execute(
        "SELECT DISTINCT n.name FROM link l JOIN note n ON n.path = l.path "
        "WHERE l.dst = ? AND n.shape = 'source' ORDER BY n.name",
        (concept.lower(),)).fetchall()
    listing = "\n".join(f"- [[{r['name']}]]" for r in sources) or "None yet."
    marker = "*Generated by the librarian from the sources that link this concept.*"
    sections = [(h, t) for h, t in note.sections().items() if h and h != CONCEPT_SOURCES]
    preamble = note.sections().get("", "")
    body = (preamble + "\n\n" if preamble else "") + "\n".join(
        f"## {h}\n{t}\n" for h, t in sections) + f"\n## {CONCEPT_SOURCES}\n{marker}\n\n{listing}\n"
    path.write_text(notes.render(note.frontmatter, body), encoding="utf-8")
    index.upsert(path)
    return path


def write_master_index(index: Index) -> Path:
    """Counts per topic and per kind: proportional to the number of topics."""
    topics = index.conn.execute(
        "SELECT f.value AS topic, COUNT(DISTINCT f.note) AS n FROM facet f JOIN note x "
        "ON x.path = f.path WHERE f.axis = 'topic' AND x.shape = 'source' "
        "GROUP BY f.value ORDER BY f.value").fetchall()
    kinds = index.conn.execute(
        "SELECT kind, COUNT(*) AS n FROM note WHERE shape = 'source' GROUP BY kind "
        "ORDER BY kind").fetchall()
    path = index.vault.root / "Indexes" / "Master Index.md"
    body = notes.compose("Master Index", [
        ("About This Index", "Generated by the librarian. Edits here are overwritten."),
        ("Topics", "\n".join(f"- [[Topic - {notes.safe_name(r['topic'])}|{r['topic']}]] "
                             f"({r['n']})" for r in topics) or "- Unfiled (0)"),
        ("Sources By Kind", "\n".join(f"- {r['kind']}: {r['n']}" for r in kinds) or
         "No sources yet.")])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.render({"type": "index", "status": "active", "generated": True},
                                 body), encoding="utf-8")
    index.upsert(path)
    return path


# ------------------------------------------------------------------- the job

def promote(vault: Vault, engine: Engine, draft: Draft) -> Report:
    index = engine.index
    report = Report(draft.name)
    name = notes.safe_name(draft.name)
    if not name:
        raise TypeError("a source needs a name")
    if not draft.bottom_line.strip() or not draft.what_it_solves.strip():
        raise TypeError("a Source is promoted with its Bottom Line and What It Solves")
    existing = index.note_row(name)
    if existing is not None:
        raise Refusal("UNIQUE_NOTE_NAMES", f"{name!r} already exists at {existing['path']}")
    # The kind must be one the vault's own Content Model declares - never
    # "anything, when the model lists none": the kind becomes a folder name,
    # so an unchecked one could also walk out of Sources/ (review §4 A1).
    if not index.model.kinds:
        raise TypeError("the vault's Content Model declares no source kinds "
                        "(About/Note Content Model.md, ## Source Kinds); doctor explains")
    if draft.kind not in index.model.kinds or not re.fullmatch(r"[a-z0-9_\-]+", draft.kind):
        raise TypeError(f"source kind {draft.kind!r} is not in the content model: "
                        f"{sorted(index.model.kinds)}")
    folder = vault.root / "Sources" / draft.kind
    path = folder / f"{name}.md"

    # 1. write
    fm: dict[str, Any] = {"type": "source", "kind": draft.kind,
                          "title": draft.title or name,
                          "canonical_url": draft.canonical_url or "unknown",
                          "status": "active",
                          # A person's correction (a `primary_topic` field) wins over
                          # the topic the item was staged under.
                          "primary_topic": (draft.fields.get("primary_topic") or draft.topic
                                            or UNFILED),
                          "captured_at": draft.captured_at or now_iso()[:10]}
    fm.update({k: v for k, v in draft.fields.items() if v not in (None, "", [])
               and k not in fm})
    fm["evidence"] = [e["id"] for e in draft.evidence]
    fm["attested_by"] = draft.attested_by
    if draft.session:
        fm["session"] = draft.session
    fm["catalogued_at"] = now_iso()
    body = _body(draft, index.model)
    linked = _concepts(engine, body)                                  # 3, before writing
    if linked:
        fm["concepts"] = [f"[[{c}]]" for c in linked]
    folder.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.render(fm, body), encoding="utf-8")
    rel = path.relative_to(vault.root).as_posix()
    report.path = rel
    violations = index.model.check(notes.load(path), vault.root)
    report.step("write", True, {"path": rel, "schema_violations":
                                [v.detail for v in violations]})

    # 2. index
    index.upsert(path)
    engine.forget()
    vectors = ""
    if engine.vectors is not None:
        embedded = engine.vectors.sync()
        vectors = engine.vectors.unavailable or f"{embedded} chunk(s) embedded"
    report.step("index", True, {"vectors": vectors or "off"})
    report.step("concepts", True, {"linked": linked})

    # 4. index notes
    topic_path = write_topic_index(index, fm["primary_topic"])
    write_master_index(index)
    for concept in linked:
        write_concept_sources(index, concept)
    report.step("index_notes", True, {"topic_index": topic_path.relative_to(vault.root)
                                      .as_posix()})

    # 5. findability
    missed = findability(engine, name)
    if missed:
        note = notes.load(path)
        note.frontmatter["needs_attention"] = f"not findable: {'; '.join(missed)}"
        path.write_text(notes.render(note.frontmatter, note.body), encoding="utf-8")
        index.upsert(path)
    report.step("findability", not missed, {"missed": missed})
    report.catalogued = not missed
    return report


def findability(engine: Engine, name: str) -> list[str]:
    """Which of the three searches (and the index-note link) fail to find it."""
    index = engine.index
    row = index.note_row(name)
    if row is None:
        return ["the note is not in the index"]
    k = int(engine.h.get("findability_top_k", 5))
    fm = json.loads(row["frontmatter"])
    probes = [("title", row["title"])]
    if row["bottom_line"].strip():
        probes.append(("Bottom Line", row["bottom_line"]))
    concepts = [c.strip("[]") for c in fm.get("concepts") or []]
    if concepts:
        concept = index.note_row(concepts[0])
        probes.append((f"concept {concepts[0]}", concept["title"] if concept else concepts[0]))
    missed = []
    for label, query in probes:
        if label.startswith("concept "):
            concept_links = {r["dst"] for r in index.conn.execute(
                "SELECT l.dst FROM link l JOIN note n ON n.path = l.path "
                "WHERE n.name = ?", (concepts[0],))}
            if name.lower() in concept_links:
                continue                     # the concept page lists it
        names = [r.name for r in search(engine, query, "donor", limit=k).results]
        if name not in names[:k]:
            missed.append(f"not in the top {k} for its {label}")
    if not any(src.startswith("Topic - ") or src == "Master Index"
               for src in index.linked_from(name)):
        missed.append("no index note links to it")
    if engine.vectors is not None and not engine.vectors.unavailable:
        has = index.conn.execute(
            "SELECT 1 FROM chunk c JOIN embedding e ON e.hash = c.hash AND e.model = ? "
            "WHERE c.note = ? LIMIT 1", (engine.vectors.model, name)).fetchone()
        if not has:
            missed.append("it has no vectors")
    return missed
