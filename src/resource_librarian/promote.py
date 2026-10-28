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
import hashlib
import os
import re
import secrets
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from . import notes, schema
from .coordination import (MISSING, PreconditionChangedError, atomic_write_text,
                           fingerprint, fingerprint_bytes, operation_path)
from .index import Index
from .rules import Refusal
from .search import Engine, search
from .vault import Vault, now_iso

UNFILED = "Unfiled"
EVIDENCE_HEADING = "Evidence"
EMBEDDING_PENDING = "embedding pending after writer release; retry derived embedding if it remains"


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
    # Internal hand-off state. Neither field is part of the public promotion
    # report; serving callers use it to finish derived vectors after releasing
    # the sole vault writer.
    embedding_pending: bool = False
    embedding_attention_pending: bool = False
    publication_fingerprint: str = ""

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
    ordered = [(h, f"*Origin: {SECTION_ORIGIN[h]}.*\n\n{t}" if h in SECTION_ORIGIN
                and not t.lstrip().startswith("*Origin:") else t) for h, t in ordered]
    return notes.compose(draft.title or draft.name, ordered)


# Research Pipeline §3.3 / Addendum R16: the note labels where each kind of claim comes from.
# Project application never appears in a source note (an Offering or Application holds it).
SECTION_ORIGIN = {
    "Claims": "source-stated - what the text itself says, part by part",
    "Reading Notes": "source-stated - what the text says, from reading it in full",
    "Specs": "source-stated - the provider's own listing, not a measurement",
    "Architecture & Mechanics": "source-stated - how the source describes its own workings",
    "Evidence & Limits": "source-stated - the limits the source itself states",
    "What Is Inside": "structurally observed - read from the source's files or pages",
    "Components": "structurally observed - one record per component, with its locator",
    "Access Points": "structurally observed - declared in the source",
    "How It Fits Together": "derived relation - from the components' static structure, "
                            "never observed running",
    "Chapters": "structurally observed divisions, with the claims read from each",
    "How The Chapters Relate": "derived relation - a model's reading of fully read chapters",
    "Integration & Use Cases": "potential use - what the source could serve, not a recorded use",
    "Transferable Capability": "potential use - stated apart from the source's own domain",
}


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


def topic_index_text(index: Index, topic: str) -> str:
    """Render only; Core callers copy this text back to their file writer."""
    rows = index.conn.execute(
        "SELECT n.name, n.kind, n.bottom_line FROM facet f JOIN note n ON n.path = f.path "
        "WHERE f.axis = 'topic' AND f.value = ? AND n.shape = 'source' ORDER BY n.name",
        (topic,)).fetchall()
    lines = [f"- [[{r['name']}]] ({r['kind']}): "
             f"{' '.join(r['bottom_line'].split())[:160] or 'no Bottom Line yet'}"
             for r in rows]
    body = notes.compose(f"Topic - {topic}", [
        ("About This Index", "Generated by the librarian from the notes filed under this "
                             "topic. Edits here are overwritten."),
        ("Sources", "\n".join(lines) or "None yet.")])
    return notes.render({"type": "index", "status": "active", "generated": True, "topic": topic}, body)


def write_topic_index(index: Index, topic: str) -> Path:
    """Offline/legacy promotion wrapper; Core taxonomy separates render/write."""
    path = topic_index_path(index.vault, topic)
    atomic_write_text(path, topic_index_text(index, topic))
    index.upsert(path)
    return path


CONCEPT_SOURCES = "Sources Using This"


def concept_sources_text(index: Index, concept: str, original: str) -> str:
    """Render the generated section over a caller's exact note snapshot."""
    front, body, error = notes.parse(original)
    if error or front.get("type") not in (None, "", "concept"):
        raise TypeError("concept backlink target is no longer a valid concept note")
    note = notes.Note(concept, Path(concept), front, body)
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
    return notes.render(note.frontmatter, body)


def write_concept_sources(index: Index, concept: str) -> Path | None:
    """The generated list of sources that link a Concept, inside the Concept
    note, in its own section. Only that section is rewritten; the rest of the
    note is the person's. Proportional to the concept's sources."""
    row = index.note_row(concept)
    if row is None or row["shape"] != "concept":
        return None
    path = index.vault.root / row["path"]
    atomic_write_text(path, concept_sources_text(index, concept, path.read_text(encoding="utf-8")))
    index.upsert(path)
    return path


def master_index_text(index: Index) -> str:
    """Render counts per topic/kind without writing any Markdown."""
    topics = index.conn.execute(
        "SELECT f.value AS topic, COUNT(DISTINCT f.note) AS n FROM facet f JOIN note x "
        "ON x.path = f.path WHERE f.axis = 'topic' AND x.shape = 'source' "
        "GROUP BY f.value ORDER BY f.value").fetchall()
    kinds = index.conn.execute(
        "SELECT kind, COUNT(*) AS n FROM note WHERE shape = 'source' GROUP BY kind "
        "ORDER BY kind").fetchall()
    body = notes.compose("Master Index", [
        ("About This Index", "Generated by the librarian. Edits here are overwritten."),
        ("Topics", "\n".join(f"- [[Topic - {notes.safe_name(r['topic'])}|{r['topic']}]] "
                             f"({r['n']})" for r in topics) or "- Unfiled (0)"),
        ("Sources By Kind", "\n".join(f"- {r['kind']}: {r['n']}" for r in kinds) or
         "No sources yet.")])
    return notes.render({"type": "index", "status": "active", "generated": True}, body)


def write_master_index(index: Index) -> Path:
    """Offline/legacy promotion wrapper; never call on the Core index worker."""
    path = index.vault.root / "Indexes" / "Master Index.md"
    atomic_write_text(path, master_index_text(index))
    index.upsert(path)
    return path


# ------------------------------------------------------------------- the job

def _source_material(vault: Vault, engine: Engine, draft: Draft, existing_path: str = "") -> dict:
    index = engine.index
    name = notes.safe_name(draft.name)
    if not name:
        raise TypeError("a source needs a name")
    if not draft.bottom_line.strip() or not draft.what_it_solves.strip():
        raise TypeError("a Source is promoted with its Bottom Line and What It Solves")
    existing = index.note_row(name)
    if existing is not None and not (existing_path and existing["path"] == existing_path
                                    and existing["shape"] == "source" and existing["kind"] == draft.kind):
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
    return {"name": name, "path": path.relative_to(vault.root).as_posix(),
            "topic": str(fm["primary_topic"]), "text": notes.render(fm, body), "linked": linked,
            "concept_rows": [dict(index.note_row(c)) for c in linked]}


def promote(vault: Vault, engine: Engine, draft: Draft) -> Report:
    """Explicit legacy/offline path; Core callers use prepare/apply below."""
    index = engine.index
    material = _source_material(vault, engine, draft)
    name, linked = material["name"], material["linked"]
    report = Report(draft.name)
    path = vault.safe_relative(material["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, material["text"])
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
    topic_path = write_topic_index(index, material["topic"])
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
        atomic_write_text(path, notes.render(note.frontmatter, note.body))
        index.upsert(path)
    report.step("findability", not missed, {"missed": missed})
    report.catalogued = not missed
    return report


class PromotionInterruptedError(RuntimeError):
    """Durable work exists; never suggest an automatic retry or rollback."""
    def __init__(self, cause: Exception, completed: list[str]):
        self.completed_paths = list(dict.fromkeys(completed))
        # Exception text may contain a provider payload. Persist type + paths,
        # not arbitrary messages or source text.
        super().__init__(f"promotion interrupted ({type(cause).__name__}); completed writes: "
                         f"{self.completed_paths}; review before retrying")


def prepare(vault: Vault, draft: Draft, index_call: Callable, *, resume: dict | None = None) -> dict:
    """Read-only, invocation-local plan for a *new* source (no attachments)."""
    observed, snapshots = {}, {}
    def snapshot(rel):
        path = operation_path(vault, rel)
        if path.relative_to(vault.root).as_posix() != rel:
            raise TypeError("promotion targets cannot redirect through symlinks")
        raw = path.read_bytes() if path.exists() else None
        observed[rel] = fingerprint_bytes(raw) if raw is not None else MISSING
        snapshots[rel] = raw.decode("utf-8") if raw is not None else ""
    for rel in (schema.MODEL_PATH.as_posix(), "About/Topics.md", ".librarian/config.toml",
                ".librarian/agents/routes.json"):
        snapshot(rel)
    material = index_call(lambda engine: _source_material(vault, engine, draft, (resume or {}).get("path", "")))
    rel = material["path"]
    snapshot(rel)
    if resume:
        if (resume.get("path") != rel or resume.get("fingerprint") != observed[rel]
                or resume.get("linked") != material["linked"]):
            raise Refusal("DOCUMENT_ACTIVE", "the interrupted source or its concept context changed; review before continuing")
    elif observed[rel] != MISSING:
        raise Refusal("UNIQUE_NOTE_NAMES", f"{rel} already exists; promotion never replaces an unindexed file")
    topic_path = topic_index_path(vault, material["topic"]).relative_to(vault.root).as_posix()
    targets = [rel, topic_path, "Indexes/Master Index.md"]
    concepts = []
    for row in material.pop("concept_rows"):
        target = row["path"]
        snapshot(target)
        if observed[target] == MISSING:
            raise PreconditionChangedError(target)
        concepts.append({"name": row["name"], "path": target, "text": snapshots[target]})
        targets.append(target)
    if len(set(path.casefold() for path in targets)) != len(targets):
        raise TypeError("promotion targets collide; resolve names before accepting")
    for target in (topic_path, "Indexes/Master Index.md"):
        snapshot(target)
    # The index filename is a projection, not a topic identity. Never replace
    # a different accepted topic whose Windows-safe filename happens to match.
    if any(t != material["topic"] and topic_index_path(vault, t).name.casefold() ==
           Path(topic_path).name.casefold() for t in vault.topics()):
        raise TypeError("source topic collides with another topic's generated filename")
    return {"operation": "new_source", "draft": asdict(draft), "resuming": bool(resume), **material,
            "topic_path": topic_path, "concepts": concepts, "targets": targets,
            "observed": list(observed.items())}


class PromotionGuard:
    """Per-step CAS/lease checks; not an OS lock or cross-file transaction."""
    def __init__(self, vault: Vault, plan: dict, leases=None):
        self.vault, self.leases = vault, leases
        self.expected, self.targets = dict(plan["observed"]), set(plan["targets"])
        # Only a single-source plan owns this top-level copy inventory. Batch
        # plans intentionally have no ``copies`` key and retain the older
        # full-footprint check before every write.
        copies = plan.get("copies") if plan.get("operation") == "new_source" else None
        self.copy_pairs = {
            (str(copy["source"]), str(copy["destination"]))
            for copy in copies or []
            if isinstance(copy, dict) and copy.get("source") and copy.get("destination")
        }
        if copies and len(self.copy_pairs) != len(copies):
            raise TypeError("promotion copy inventory is invalid or duplicated")
        self.attachment_paths = {path for pair in self.copy_pairs for path in pair}
        if any(source not in self.expected or destination not in self.expected
               or destination not in self.targets for source, destination in self.copy_pairs):
            raise TypeError("promotion copy inventory is outside the prepared footprint")
        self.validated_copies: set[tuple[str, str]] = set()
        self.completed: list[str] = []
        # The writer's admission check already fingerprinted every observed
        # path. Each declared copy below independently validates its source
        # and destination immediately before publication, so rehash only the
        # non-attachment dependencies here. Direct/batch guards remain full.
        self.check(include_attachments=not self.copy_pairs)
        if leases is not None:
            leases.assert_writable([p for p in self.targets if not p.startswith(".")])

    def check(self, *, include_attachments: bool = True):
        for rel, wanted in self.expected.items():
            if not include_attachments and rel in self.attachment_paths:
                continue
            if fingerprint(operation_path(self.vault, rel)) != wanted:
                raise PreconditionChangedError(rel)

    def write(self, rel: str, text: str, *, include_attachments: bool | None = None):
        if rel not in self.targets:
            raise TypeError("promotion attempted an undeclared write")
        if self.copy_pairs and self.validated_copies != self.copy_pairs:
            raise TypeError("promotion attachments must be validated before text writes")
        self.check(include_attachments=(not self.copy_pairs if include_attachments is None
                                        else include_attachments))
        path = operation_path(self.vault, rel)
        if self.leases is not None and not rel.startswith("."):
            self.leases.assert_writable([rel])
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, text)
        self.expected[rel] = fingerprint_bytes(text.encode("utf-8"))
        self.completed.append(rel)
        if self.leases is not None and not rel.startswith("."):
            self.leases.note_core_write([rel])

    def copy(self, source: str, destination: str):
        """Stream a verified managed copy; never remove the original input."""
        if destination not in self.targets or source not in self.expected:
            raise TypeError("attachment copy is not in the prepared plan")
        pair = (source, destination)
        declared = pair in self.copy_pairs
        if self.copy_pairs and not declared:
            raise TypeError("attachment copy is not in the declared single-source inventory")
        self.check(include_attachments=not declared)
        target = self.vault.safe_relative(destination)
        if self.leases is not None:
            self.leases.assert_writable([destination])
        if self.expected[destination] != MISSING:
            if self.expected[destination] != self.expected[source]:
                raise PreconditionChangedError(destination)
            if declared:
                if fingerprint(operation_path(self.vault, source)) != self.expected[source]:
                    raise PreconditionChangedError(source)
                if fingerprint(target) != self.expected[destination]:
                    raise PreconditionChangedError(destination)
                self.validated_copies.add(pair)
            return  # Only an explicitly retained, byte-identical prior copy.
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_name(f".{target.name}.{secrets.token_hex(6)}.tmp")
        try:
            digest = hashlib.sha256()
            with operation_path(self.vault, source).open("rb") as origin, temp.open("xb") as output:
                for block in iter(lambda: origin.read(1 << 20), b""):
                    digest.update(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest()[:20] != self.expected[source]:
                raise PreconditionChangedError(source)
            if declared:
                # The streamed digest catches a mutation during the read; a
                # second fingerprint catches a change just after EOF. Text
                # dependencies and the absent destination are checked as
                # close to publication as the cross-file contract permits.
                if fingerprint(operation_path(self.vault, source)) != self.expected[source]:
                    raise PreconditionChangedError(source)
                self.check(include_attachments=False)
                if fingerprint(target) != self.expected[destination]:
                    raise PreconditionChangedError(destination)
            else:
                self.check()
            if self.leases is not None:
                self.leases.assert_writable([destination])
            os.replace(temp, target)
            self.expected[destination] = self.expected[source]
            self.completed.append(destination)
            if declared:
                self.validated_copies.add(pair)
            if self.leases is not None:
                # The streamed digest is the exact fingerprint of the bytes
                # atomically published above. Reuse it for watcher suppression
                # instead of immediately rereading a potentially large copy.
                self.leases.note_core_write(
                    [destination], fingerprints={destination: self.expected[source]})
        finally:
            if temp.exists():
                temp.unlink()

    def record_progress(self, rel: str, text: str):
        """Record caught partial work even if a different document conflicts.

        Only the declared staging record can use this narrower CAS; no note,
        policy file or arbitrary state can bypass the ordinary guard.
        """
        if rel not in self.targets or not rel.startswith(".librarian/staging/") or not rel.endswith(".json"):
            raise TypeError("partial progress requires a declared staging record")
        path = operation_path(self.vault, rel)
        if fingerprint(path) != self.expected[rel]:
            raise PreconditionChangedError(rel)
        atomic_write_text(path, text)
        self.expected[rel] = fingerprint_bytes(text.encode("utf-8"))
        self.completed.append(rel)


def apply(vault: Vault, draft: Draft, plan: dict, index_call: Callable, *,
          leases=None, guard: PromotionGuard | None = None,
          defer_embedding: bool = False) -> Report:
    """SQL/rendering on Core; file mutations on the caller's writer actor."""
    if plan.get("operation") != "new_source" or plan.get("draft") != asdict(draft):
        raise TypeError("source promotion requires its own prepared plan")
    # Admission and uniqueness precede even evidence/Markdown mutations.
    def admission(engine):
        held = engine.index.note_row(plan["name"])
        if held is not None and not (plan.get("resuming") and held["path"] == plan["path"]
                                     and held["shape"] == "source" and held["kind"] == draft.kind):
            raise Refusal("UNIQUE_NOTE_NAMES", f"{plan['name']!r} is already catalogued")
    index_call(admission)
    guard = guard or PromotionGuard(vault, plan, leases)
    report = Report(draft.name)
    def write(rel, text):
        guard.write(rel, text)
        return index_call(lambda engine: engine.index.upsert(vault.safe_relative(rel)))
    try:
        front, body, _ = notes.parse(plan["text"])
        # A crash or caught mid-promotion conflict must not leave an apparently
        # complete accepted note. Clear this marker only after final checks.
        front["needs_attention"] = "promotion incomplete; review evidence, backlinks and indexes before retrying"
        write(plan["path"], notes.render(front, body))
        report.path = plan["path"]
        violations = index_call(lambda engine: [v.detail for v in engine.index.model.check(
            notes.load(vault.safe_relative(plan["path"])), vault.root)])
        report.step("write", True, {"path": report.path, "schema_violations": violations})
        report.step("concepts", True, {"linked": plan["linked"]})
        rendered = index_call(lambda engine: [
            (plan["topic_path"], topic_index_text(engine.index, plan["topic"])),
            ("Indexes/Master Index.md", master_index_text(engine.index)),
            *[(c["path"], concept_sources_text(engine.index, c["name"], c["text"]))
              for c in plan["concepts"]]])
        for rel, text in rendered:
            write(rel, text)
        report.step("index_notes", True, {"topic_index": plan["topic_path"]})
        # The mechanical searches must never invoke an embedding endpoint on
        # the index worker. Vector sync has an explicit copied-data boundary.
        missed = index_call(lambda engine: findability(Engine(engine.index, engine.h), plan["name"]))
        if defer_embedding:
            # Reading the assignment is cheap and local. Avoid manufacturing a
            # continuation (and a second state write) when vectors are off.
            from .embed import spec_for
            if spec_for(vault):
                vectors = "pending writer release"
                report.embedding_pending = True
            else:
                vectors = "off"
        else:
            from .embed import sync_source_via
            try:
                vectors = sync_source_via(vault, plan["name"], index_call)
            except Exception as exc:
                vectors = f"embedding update failed ({type(exc).__name__}); retry explicitly"
                missed.append("its embedding update failed")
        report.step("index", True, {"vectors": vectors})
        # Embedding never reads managed attachments. Their streamed copies
        # were validated at publication and staging performs one final full
        # source/destination check immediately before accepting its state.
        # Keep this intermediate check on mutable text/config dependencies so
        # large attachments are not rehashed during encoder work.
        guard.check(include_attachments=False)
        if missed:
            front, body, _ = notes.parse(plan["text"])
            front["needs_attention"] = f"not findable: {'; '.join(missed)}"
            write(plan["path"], notes.render(front, body))
        elif report.embedding_pending:
            # A process can die after the writer releases but before vectors
            # finish. Keep that window visible on the authoritative note, not
            # only in an accepted hidden staging record.
            front, body, _ = notes.parse(plan["text"])
            front["needs_attention"] = EMBEDDING_PENDING
            write(plan["path"], notes.render(front, body))
            report.embedding_attention_pending = True
        else:
            write(plan["path"], plan["text"])
        report.step("findability", not missed, {"missed": missed})
        report.catalogued = not missed
        report.publication_fingerprint = guard.expected[plan["path"]]
        return report
    except Refusal as exc:
        exc.extra.update(completed_paths=list(dict.fromkeys(guard.completed)),
                         next_action="Review the completed source/evidence/views; do not retry blindly.")
        if guard.completed:
            exc.detail = f"Earlier writes remain at {list(dict.fromkeys(guard.completed))}. {exc.detail}"
            exc.args = (f"{exc.code}: {exc.detail}",)
        raise
    except Exception as exc:
        raise PromotionInterruptedError(exc, guard.completed) from exc


def complete_embedding_report(report: Report, vectors: str,
                              failure: Exception | None = None) -> None:
    """Reconcile a deferred vector result without changing publication facts."""
    report.steps["index"]["detail"]["vectors"] = vectors
    if failure is not None:
        missed = report.steps["findability"]["detail"].setdefault("missed", [])
        if "its embedding update failed" not in missed:
            missed.append("its embedding update failed")
        report.steps["findability"]["ok"] = False
        report.catalogued = False
    report.embedding_pending = False


def complete_embedding_dict(report: dict[str, Any], vectors: str,
                            failure: Exception | None = None) -> None:
    """Dictionary counterpart used by a post-writer staging continuation."""
    report["steps"]["index"]["detail"]["vectors"] = vectors
    if failure is not None:
        missed = report["steps"]["findability"]["detail"].setdefault("missed", [])
        if "its embedding update failed" not in missed:
            missed.append("its embedding update failed")
        report["steps"]["findability"]["ok"] = False
        report["catalogued"] = False
        report["status"] = "written but not findable"


def stale_embedding_report(report: Report) -> None:
    """A newer source revision makes a just-computed vector result provisional."""
    missed = report.steps["findability"]["detail"].setdefault("missed", [])
    if "the source changed during its embedding update" not in missed:
        missed.append("the source changed during its embedding update")
    report.steps["findability"]["ok"] = False
    report.catalogued = False


def stale_embedding_dict(report: dict[str, Any]) -> None:
    missed = report["steps"]["findability"]["detail"].setdefault("missed", [])
    if "the source changed during its embedding update" not in missed:
        missed.append("the source changed during its embedding update")
    report["steps"]["findability"]["ok"] = False
    report["catalogued"] = False
    report["status"] = "written but not findable"


def embedding_success(vault: Vault, path: str, expected: str,
                      index_call: Callable) -> None:
    """Clear the durable pending marker after vectors finish, with exact CAS."""
    target = operation_path(vault, path)
    if fingerprint(target) != expected:
        raise PreconditionChangedError(path)
    note = notes.load(target)
    if note.frontmatter.get("needs_attention") != EMBEDDING_PENDING:
        raise PreconditionChangedError(path)
    note.frontmatter.pop("needs_attention", None)
    if fingerprint(target) != expected:
        raise PreconditionChangedError(path)
    atomic_write_text(target, notes.render(note.frontmatter, note.body))
    index_call(lambda engine: engine.index.upsert(target))


def embedding_failure(vault: Vault, path: str, expected: str,
                      index_call: Callable) -> None:
    """Flag a published source after derived-vector failure, with exact CAS.

    The encoder ran without the writer. A human or another Core operation may
    therefore have changed the note meanwhile; that newer revision wins.
    """
    target = operation_path(vault, path)
    if fingerprint(target) != expected:
        raise PreconditionChangedError(path)
    note = notes.load(target)
    current = str(note.frontmatter.get("needs_attention") or "").strip()
    if current == EMBEDDING_PENDING:
        current = ""
    missing = "its embedding update failed"
    note.frontmatter["needs_attention"] = current + ("; " if current else "not findable: ") + missing
    if fingerprint(target) != expected:
        raise PreconditionChangedError(path)
    atomic_write_text(target, notes.render(note.frontmatter, note.body))
    index_call(lambda engine: engine.index.upsert(target))


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
