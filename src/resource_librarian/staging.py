"""Staging: the airlock between what a machine produced and the vault.

Three kinds of item wait here (offering drafts wait in `staging/offerings/`
and are promoted from their session):

- `source`: a described source, not yet a note. Accepted, it goes through the
  six-step promotion job and becomes a Source note.
- `lens`: a reasoning stance drawn from a passage. Accepted, it goes to the
  agent-side lens store, not into the notes.
- `concept`: a term or pattern seen across several sources (`concepts.py`),
  its usages quoted from evidence. Accepted, it becomes a Concept note - but
  never with a machine-drafted Definition: that section is a person's own
  words, given at accept time (`fields["definition"]`), the one part of a
  concept note this catalogue's evidence-first discipline cannot itself
  supply. `promote.py`'s own linking step (M4b's other half) then finds it by
  name or alias for future sources.

**Assisted review** runs two clerk tasks, kept apart on purpose:
- a *framed* fit judgement (does the evidence show it doing what the need
  describes?), run only when the item was found against a need, with the
  verified quote shown beside the evidence it came from;
- an *unframed* Bottom Line draft, from the evidence alone, so the sentence a
  reader acts on is never written toward the project that found it.

**Who accepts** (`INTERPRETATION_IS_NOT_MACHINE_WORK`, `PERSON_CONFIRMS`):
under `promotion.mode = "person"` only a person (the curate tier) accepts; under
`"agent"` an agent may, using the unframed draft. A sensitive item is accepted
by a person only, whatever the setting (`SENSITIVITY_REVIEW`). A rejection is
never deleted: it moves to quarantine with its reason.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from . import clerk, notes
from .lenses import LensStore
from .promote import Draft, promote
from .rules import Refusal
from .search import Engine
from .vault import Vault, now_iso

KINDS = ("source", "lens", "concept", "topic", "import")
# One lifecycle for a source (Requirements - Research Pipeline §4.1, Addendum R7/R14):
# queued (a reference, not yet fetched) -> staged (captured and described) -> approved
# (a person approved spending processing on it) -> processing (in a batch a person
# started) -> enriched (every stage complete) or partial (the batch finished, but a stage
# is unfinished: text it could not read, a clerk that did not answer) -> accepted (a
# library note). rejected, deferred and failed keep their reason. Approving is not
# accepting: nothing is published until the separate accept, and every accepted note
# records how much of the source was read (`coverage_of`).
STATUSES = ("queued", "staged", "approved", "processing", "enriched", "partial",
            "accepted", "rejected", "deferred", "failed")
DECIDABLE = {"accept": ("staged", "deferred", "approved", "enriched", "partial"),
             # partial or failed: run the batch again; finished stages are not repeated
             "approve": ("staged", "deferred", "failed", "partial"),
             "reject": ("staged", "deferred", "approved", "enriched", "partial", "failed"),
             "defer": ("staged", "approved", "enriched", "partial")}
CAPTURED = ("accepted as captured: only what intake fetched was read (a page's text, a "
            "file's opening, a repository's README and tree), not the whole source")


def coverage_of(item: dict[str, Any]) -> tuple[str, list[str]]:
    """How much of a source was read when it is accepted, and what was not examined - kept
    on its note (Research Pipeline §7): `full`, `partial n/m`, or `captured` for a source
    accepted without being ingested ("Accept as captured")."""
    proc = item.get("processing") or {}
    by_ocr = " (text by OCR)" if item.get("ocr") else ""
    if item.get("status") in ("enriched", "partial") and proc:
        return str(proc.get("coverage") or "partial") + by_ocr, \
            list(proc.get("not_examined") or [])
    q = (item.get("intake") or {}).get("quality") or {}
    flagged = [f"capture: {q['reason']}"] if q.get("verdict") in (
        "needs_ocr", "js_shell", "partial", "no_access_point") else []
    read = item.get("deep_read") or {}
    chunks, done = int(read.get("chunks") or 0), len(read.get("read") or {})
    if chunks and done >= chunks:
        return "full", ["not reviewed in a batch: the Bottom Line is from capture or a person"
                        ] + flagged
    if chunks:
        return f"partial {done}/{chunks}", [f"read: {chunks - done} of {chunks} parts not "
                                            f"read"] + flagged
    return "captured", [CAPTURED] + flagged


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:60] or "item"


@dataclass
class StagingStore:
    vault: Vault

    @property
    def root(self) -> Path:
        return self.vault.work("staging")

    def folder(self, kind: str) -> Path:
        if kind not in KINDS:
            raise TypeError(f"staging kind {kind!r} is not one of {KINDS}")
        return self.root / kind

    def path(self, item_id: str) -> Path:
        for kind in KINDS:
            candidate = self.folder(kind) / f"{item_id}.json"
            if candidate.exists():
                return candidate
        raise TypeError(f"no staged item {item_id!r}")

    def load(self, item_id: str) -> dict[str, Any]:
        return json.loads(self.path(item_id).read_text(encoding="utf-8"))

    def save(self, item: dict[str, Any]) -> None:
        folder = self.folder(item["kind"])
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{item['id']}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=1), encoding="utf-8")

    def add(self, item: dict[str, Any]) -> dict[str, Any]:
        item.setdefault("status", "staged")
        item.setdefault("created_at", now_iso())
        item.setdefault("sensitivity", "normal")
        item.setdefault("history", [])
        self.save(item)
        return item

    def items(self, kind: str = "", status: str = "") -> Iterable[dict[str, Any]]:
        for k in ([kind] if kind else KINDS):
            folder = self.folder(k)
            if not folder.is_dir():
                continue
            for path in sorted(folder.glob("*.json")):
                item = json.loads(path.read_text(encoding="utf-8"))
                if not status or item.get("status") == status:
                    yield item

    def counts(self) -> dict[str, dict[str, int]]:
        out: dict[str, dict[str, int]] = {}
        for item in self.items():
            bucket = out.setdefault(item["kind"], {})
            bucket[item["status"]] = bucket.get(item["status"], 0) + 1
            if item.get("sensitivity") != "normal" and item["status"] == "staged":
                bucket["sensitive_waiting"] = bucket.get("sensitive_waiting", 0) + 1
        return out

    def quarantine(self, item: dict[str, Any], reason: str) -> None:
        folder = self.vault.work("quarantine") / "staging"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{item['id']}.json").write_text(
            json.dumps({**item, "quarantined_at": now_iso(), "reason": reason},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        self.path(item["id"]).unlink()


# ---------------------------------------------------------------- reviewing

def evidence_text(item: dict[str, Any]) -> str:
    if item.get("evidence_text"):
        return item["evidence_text"]
    parts = [f"{h}:\n{t}" for h, t in (item.get("sections") or {}).items() if t]
    return "\n\n".join(parts)


def review(store: StagingStore, item_id: str, endpoint: clerk.Endpoint | None,
           need: str = "", disqualifiers: list[str] | None = None) -> dict[str, Any]:
    """The assisted review: the unframed draft always, the framed fit judgement
    only when there is a need to judge against. Stored on the item."""
    item = store.load(item_id)
    if item["kind"] == "lens":
        return {"id": item_id, "kind": item["kind"], "note": "lenses are reviewed by reading "
                "the proposal and its source_quote; there is nothing to draft"}
    if item["kind"] == "concept":
        return {"id": item_id, "kind": item["kind"], "note": "a concept is reviewed by reading "
                "its usages; its Definition is a person's own words, given at accept "
                "(fields={'definition': ...}), never drafted here"}
    text = evidence_text(item)
    tasks = [clerk.bottom_line(text), clerk.sensitivity(text)]
    if need:
        tasks.append(clerk.fit(text, need, disqualifiers or []))
    results = clerk.run(tasks, endpoint, store.vault.work("queue") / "clerk")
    draft, sensitive = results[0], results[1]
    out: dict[str, Any] = {"reviewed_at": now_iso(),
                           "draft": {"status": draft.status, **draft.value,
                                     "dropped": draft.dropped, "model": draft.model}}
    if sensitive.ok and sensitive.value.get("sensitivity") == "review_required":
        item["sensitivity"] = "review"
        out["sensitivity"] = sensitive.value.get("reason", "")
    if need:
        fit_result = results[2]
        quote = fit_result.value.get("evidence_quote", "")
        out["fit"] = {"status": fit_result.status, **fit_result.value,
                      "need": need, "quote_context": _context(text, quote)}
    item["review"] = out
    store.save(item)
    return {"id": item_id, **out}


def _context(text: str, quote: str, width: int = 160) -> str:
    """The quote shown beside the evidence around it, so a reader can check it."""
    if not quote:
        return ""
    at = clerk.normal(text).find(clerk.normal(quote))
    flat = " ".join(text.split())
    if at < 0:
        return ""
    start = max(0, at - width)
    return ("..." if start else "") + flat[start:at + len(quote) + width] + "..."


# ---------------------------------------------------------------- deciding

def decide(store: StagingStore, engine: Engine, item_ids: list[str], decision: str,
           reason: str = "", bottom_line: str = "", what_it_solves: str = "",
           decided_by: str = "person", session: str = "",
           fields: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Accept, reject or defer, one item or a batch. Each item's outcome is
    reported on its own; one refusal does not stop the batch.

    `fields` corrects or fills in what the item was staged with - a person's
    own read of `best_for` and `suggested_tier` on a model, say, after the
    clerk's first guess, the same way `bottom_line` corrects its draft. Every
    key must already be a field of that item's kind, and a closed one must be
    one of its permitted values: it is checked here, before the note exists,
    not left for the findability check to notice afterwards."""
    if decision not in DECIDABLE:
        raise TypeError("decision is accept, approve, reject or defer")
    if decision in ("reject", "defer") and not reason.strip():
        raise TypeError(f"a {decision} needs its reason")
    if fields and len(item_ids) > 1:
        raise TypeError("a batch accept cannot share one set of field corrections; accept "
                        "items one at a time with their own")
    mode = str(store.vault.setting("promotion", "mode") or "person")
    out = []
    for item_id in item_ids:
        try:
            out.append(_decide_one(store, engine, item_id, decision, reason, bottom_line,
                                   what_it_solves, decided_by, session, mode,
                                   batch=len(item_ids) > 1, fields=fields or {}))
        except Refusal as refusal:
            out.append({"id": item_id, "refused": refusal.code, "detail": refusal.detail})
        except TypeError as exc:
            out.append({"id": item_id, "error": str(exc)})
    return out


def preview(store: StagingStore, engine: Engine, item_id: str, decided_by: str,
            bottom_line: str = "", what_it_solves: str = "",
            fields: dict[str, Any] | None = None) -> dict[str, Any]:
    """An accept, rehearsed (V1's promote --dry-run): every check the real accept makes, and
    what it would write - path, coverage, sections - with nothing written or moved."""
    from . import dik
    item = store.load(item_id)
    problems: list[str] = []
    mode = str(store.vault.setting("promotion", "mode") or "person")
    if item["status"] not in DECIDABLE["accept"]:
        problems.append(f"it is {item['status']}: not acceptable from there")
    if item.get("sensitivity") != "normal" and decided_by != "person":
        problems.append("marked sensitive: only a person accepts it")
    if mode != "agent" and decided_by != "person":
        problems.append(f"promotion.mode is {mode!r}: a person accepts")
    if item["kind"] != "source":
        return {"id": item_id, "kind": item["kind"], "would": "accept", "problems": problems}
    draft = (item.get("review") or {}).get("draft") or {}
    if not bottom_line and draft.get("status") != "ok":
        problems.append("no reviewed draft and no bottom_line given")
    for name, value in (fields or {}).items():
        try:
            _check_field_override(engine.index.model, item.get("source_kind", ""), name, value,
                                  store.vault.topics())
        except TypeError as exc:
            problems.append(str(exc))
    name = notes.safe_name(item["name"])
    kind = item.get("source_kind", "repository")
    if engine.index.note_row(name) is not None:
        problems.append(f"a note named {name!r} already exists (UNIQUE_NOTE_NAMES)")
    if kind not in engine.index.model.kinds:
        problems.append(f"source kind {kind!r} is not in the content model")
    coverage, not_examined = coverage_of(item)
    record = dik.load(store.vault, item["name"])
    sections = sorted({*(item.get("sections") or {}), *dik.sections(record)})
    return {"id": item_id, "would": "accept", "ok": not problems, "problems": problems,
            "path": f"Sources/{kind}/{name}.md", "coverage": coverage,
            "not_examined": not_examined, "sections": sections,
            **({"file": f"Sources/{kind}/files/{Path(item['file']).name}"}
               if item.get("file") else {})}


def _check_field_override(model, kind: str, name: str, value: Any,
                          topics: list[str] | None = None) -> None:
    known = model.fields_for("source", kind)
    if name not in known:
        raise TypeError(f"{name!r} is not a field of source/{kind}; known: {sorted(known)}")
    if name == "primary_topic" and topics is not None and value not in topics:
        raise TypeError(f"primary_topic={value!r} is not an accepted topic {topics}; a person "
                        f"accepts a topic by adding its row to About/Topics.md")
    permitted = model.axes_for("source", kind).get(name)
    if permitted:
        for item in value if isinstance(value, list) else [value]:
            if item not in permitted:
                raise TypeError(f"{name}={item!r} is not one of {permitted}")


def _decide_one(store, engine, item_id, decision, reason, bottom_line, what_it_solves,
                decided_by, session, mode, batch, fields: dict[str, Any] | None = None
                ) -> dict[str, Any]:
    item = store.load(item_id)
    if item["status"] == "queued":
        raise TypeError(f"{item_id} is queued for capture, not yet fetched: intake_run "
                        f"captures it, queue_remove drops it")
    if item["status"] == "processing":
        raise TypeError(f"{item_id} is in batch {item.get('batch', '?')}: decide it once the "
                        f"batch has enriched it")
    if item["status"] == "failed" and item.get("ref") and decision != "reject":
        raise TypeError(f"{item_id} is a capture that failed ({item.get('failure', {})}): "
                        f"queue_retry it, or reject it")
    if item["status"] not in DECIDABLE[decision]:
        raise TypeError(f"{item_id} is already {item['status']}")
    entry = {"decision": decision, "by": decided_by, "at": now_iso(), "reason": reason}
    if item.get("revision_of"):
        if decision == "approve":
            raise TypeError(f"{item_id} is a revision of an accepted note: accept or reject it")
        return _decide_revision(store, engine, item, decision, entry, decided_by, mode)
    if decision == "reject":
        item["status"] = "rejected"
        item["history"].append(entry)
        if item.get("file"):
            _move_file(store.vault, item, store.vault.work("quarantine") / "files")
        store.quarantine(item, reason)
        return {"id": item_id, "status": "rejected", "quarantined": True}
    if decision == "defer":
        item["status"] = "deferred"
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "deferred"}

    # approve or accept: the same people may do either
    if item.get("sensitivity") != "normal" and decided_by != "person":
        raise Refusal("SENSITIVITY_REVIEW", f"{item_id} is marked sensitive; a person "
                                            f"accepts it, whatever the promotion setting")
    if mode != "agent" and decided_by != "person":
        raise Refusal("PERSON_CONFIRMS", f"this vault's promotion.mode is {mode!r}: a "
                                         f"person accepts staged items")
    if decision == "approve":
        if item["kind"] != "source":
            raise TypeError(f"{item_id} is a {item['kind']}: only a source is approved for "
                            f"ingestion; accept or reject it")
        item.update(status="approved", approved={"by": decided_by, "at": entry["at"]})
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "approved",
                "next": "waiting for a person to begin the approved batch (Staging)"}
    if item["kind"] == "topic":
        # A person may rename it or say what belongs (`fields`); `refile: false` accepts
        # the topic without filing the proposed members under it.
        from . import taxonomy
        done = taxonomy.accept(store.vault, engine, item, decided_by, fields or {})
        item.update(status="accepted", accepted_to=f"About/Topics.md#{done['topic']}")
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "accepted", **done}
    if item["kind"] == "lens":
        # A person may reword the stance or say when it applies before
        # accepting (`lenses.EDITABLE`); the quotes are never editable.
        lens_id = LensStore(store.vault).accept(item, decided_by, origin=f"staging:{item_id}",
                                                edits=fields)
        item.update(status="accepted", accepted_to=f"lenses.sqlite#{lens_id}")
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "accepted", "lens": lens_id}

    if item["kind"] == "import":
        target = store.vault.safe_relative(item["target"])
        if target.exists():
            raise TypeError(f"{item['target']} already exists: reject this import, or move "
                            f"that note first")
        target.parent.mkdir(parents=True, exist_ok=True)
        front = {**item.get("frontmatter", {}), "evidence": [e["id"] for e in item["evidence"]],
                 "accepted_by": decided_by}
        target.write_text(notes.render(front, item.get("body", "")), encoding="utf-8")
        engine.index.upsert(target)
        item.update(status="accepted", accepted_to=item["target"])
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "accepted", "path": item["target"]}

    if item["kind"] == "concept":
        given = fields or {}
        definition = str(given.get("definition", "")).strip()
        if not definition:
            raise TypeError("a concept needs fields={'definition': ...}: a person's own "
                            "words - nothing here drafts one")
        concept_kind = str(given.get("concept_kind") or "term")
        if concept_kind not in ("term", "pattern"):
            raise TypeError("concept_kind is 'term' or 'pattern'")
        path = _write_concept(store.vault, engine, item, concept_kind, definition,
                              given.get("aliases") or [], given.get("related") or [])
        item.update(status="accepted", accepted_to=path)
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "accepted", "path": path}

    draft = (item.get("review") or {}).get("draft") or {}
    item_fields = dict(item.get("fields") or {})
    for name, value in (fields or {}).items():
        _check_field_override(engine.index.model, item.get("source_kind", ""), name, value,
                              store.vault.topics())
        item_fields[name] = value
    fields = item_fields
    if batch and (bottom_line or what_it_solves):
        raise TypeError("a batch accept cannot share one Bottom Line; accept items one at "
                        "a time with their own sentences, or rely on each item's draft")
    if not bottom_line and decided_by == "person" and draft.get("status") == "ok":
        bottom_line, what_it_solves = draft.get("bottom_line", ""), draft.get("what_it_solves", "")
        attested = "person"          # a person accepted the draft they were shown
        fields["drafted_by"] = draft.get("model") or "clerk"
    elif not bottom_line:
        if draft.get("status") != "ok":
            raise TypeError(f"{item_id} has no reviewed draft: run staging_review, or give "
                            f"bottom_line and what_it_solves")
        bottom_line, what_it_solves = draft["bottom_line"], draft["what_it_solves"]
        attested = "agent"
        fields["drafted_by"] = draft.get("model") or "clerk"
    else:
        attested = decided_by
    coverage, not_examined = coverage_of(item)
    fields.setdefault("coverage", coverage)
    from . import dik                                    # R16: Data and Information, as prose
    record = dik.load(store.vault, item["name"])
    if record:
        item["sections"] = {**(item.get("sections") or {}), **dik.sections(record)}
        fields.setdefault("dik", dik.path_for(store.vault, item["name"])
                          .relative_to(store.vault.root).as_posix())
    if item.get("ocr"):
        o = item["ocr"]
        fields.setdefault("text_origin", f"OCR by {o.get('model')}: {o.get('read')} of "
                                         f"{o.get('needed')} image-only pages")
    if not_examined:
        fields.setdefault("not_examined", not_examined)
    if item.get("file"):
        kind = item.get("source_kind", "document")
        fields["file"] = _move_file(store.vault, item,
                                    store.vault.root / "Sources" / kind / "files")
        if item.get("clean_file"):
            fields["file_markdown"] = item["clean_file"]
    report = promote(store.vault, engine, Draft(
        name=item["name"], kind=item.get("source_kind", "repository"),
        title=item.get("title", item["name"]), canonical_url=item.get("canonical_url", ""),
        bottom_line=bottom_line, what_it_solves=what_it_solves or bottom_line,
        fields=fields, sections=item.get("sections") or {},
        evidence=item.get("evidence") or [], topic=item.get("topic") or "Unfiled",
        captured_at=item.get("captured_at", ""), attested_by=attested, session=session))
    item.update(status="accepted", accepted_to=report.path, promotion=report.to_dict())
    item["history"].append(entry)
    store.save(item)
    return {"id": item_id, "status": "accepted", "coverage": coverage,
            "promotion": report.to_dict()}


REVISED_SECTIONS = ("Claims", "Evidence & Limits", "Reading Notes",
                    # a D/I/K rebuild of an accepted note (dik_rebuild, 2026-10-01)
                    "Components", "How It Fits Together", "Chapters", "How The Chapters Relate")


def _decide_revision(store, engine, item: dict[str, Any], decision: str, entry: dict[str, Any],
                     decided_by: str, mode: str) -> dict[str, Any]:
    """A deep read of an *accepted* source (roadmap §4 C2) is staged as a
    revision, never written straight into the person's note. Accepting it
    merges the sections the deep read rebuilt (what the text claims, and its
    stated limits, each with pages) into the accepted note, keeping each
    section's previous text on this item so the merge can be undone by hand.
    Rejecting or deferring only closes it: the file belongs to the accepted
    note, so nothing is moved to quarantine."""
    if decision in ("reject", "defer"):
        item["status"] = "rejected" if decision == "reject" else "deferred"
        item["history"].append(entry)
        store.save(item)
        return {"id": item["id"], "status": item["status"]}
    if mode != "agent" and decided_by != "person":
        raise Refusal("PERSON_CONFIRMS", "a revision rewrites sections of an accepted note: a "
                                         "person accepts it")
    path = store.vault.root / item["revision_of"]
    if not path.is_file():
        raise TypeError(f"{item['revision_of']} no longer exists")
    note = notes.load(path)
    body = note.body
    previous: dict[str, str] = {}
    merged = []
    from .promote import SECTION_ORIGIN
    for heading in REVISED_SECTIONS:
        text = (item.get("sections") or {}).get(heading)
        if not text:
            continue
        previous[heading] = note.sections().get(heading, "")
        if heading in SECTION_ORIGIN and not text.lstrip().startswith("*Origin:"):
            text = f"*Origin: {SECTION_ORIGIN[heading]}.*\n\n{text}"
        body = notes.with_section(body, heading, text)
        merged.append(heading)
    if item.get("revision_kind") == "dik":
        note.frontmatter["dik"] = item.get("dik", "")
    else:
        note.frontmatter["deep_read"] = now_iso()[:10]
    path.write_text(notes.render(note.frontmatter, body), encoding="utf-8")
    engine.index.upsert(path)
    item.update(status="accepted", accepted_to=item["revision_of"], merged=merged,
                previous_sections=previous)
    item["history"].append(entry)
    store.save(item)
    return {"id": item["id"], "status": "accepted", "merged_into": item["revision_of"],
            "sections": merged}


def _move_file(vault: Vault, item: dict[str, Any], folder: Path) -> str:
    """Move an item's file (from Inbox/) and return its new vault path."""
    source = vault.root / item["file"]
    if not source.is_file():
        return item["file"]
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / source.name
    n = 2
    while target.exists():
        target = folder / f"{source.stem} ({n}){source.suffix}"
        n += 1
    source.replace(target)
    item["file"] = target.relative_to(vault.root).as_posix()
    clean = vault.root / item["clean_file"] if item.get("clean_file") else None
    if clean is not None and clean.is_file():             # its cleaned copy goes with it
        moved = target.with_name(f"{target.stem} (clean text).md")
        if not moved.exists():
            clean.replace(moved)
            item["clean_file"] = moved.relative_to(vault.root).as_posix()
    return item["file"]


def _write_concept(vault: Vault, engine: Engine, item: dict[str, Any], concept_kind: str,
                   definition: str, aliases: list[str], related: list[str]) -> str:
    """The Concept note itself: Usages is what the candidate already had
    (quoted, from evidence); Definition is the person's own words, just
    given at accept - the one section this module never drafts."""
    safe = notes.safe_name(item["name"])
    path = vault.root / "Concepts" / f"{safe}.md"
    if path.exists():
        raise TypeError(f"a concept note already exists at "
                        f"{path.relative_to(vault.root)}; accept as an alias there instead")
    fm: dict[str, Any] = {"type": "concept", "concept_kind": concept_kind, "status": "active"}
    if aliases:
        fm["aliases"] = list(aliases)
    if related:
        fm["related"] = list(related)
    usages = "\n".join(f"- {u['sentence']} ({u['source']})" for u in item.get("usages") or [])
    extra = list(((item.get("imported") or {}).get("sections") or {}).items())
    body = notes.compose(safe, [
        ("Definition", definition),
        ("Usages", usages or "None recorded."),
        ("Related", "\n".join(f"- [[{r}]]" for r in related) or ""), *extra])
    if item.get("imported_from"):
        fm.update(imported_from="V1", v1_path=item["imported_from"].get("path", ""),
                  evidence=[e["id"] for e in item.get("evidence") or []])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(notes.render(fm, body), encoding="utf-8")
    engine.index.upsert(path)
    return f"Concepts/{safe}.md"


def summary(item: dict[str, Any]) -> dict[str, Any]:
    """A row for a review list: enough to choose what to open."""
    row = {"id": item["id"], "kind": item["kind"], "status": item["status"],
           "sensitivity": item.get("sensitivity", "normal"),
           **({"from_v1": item["imported_from"]["path"]} if item.get("imported_from") else {})}
    if item["kind"] == "source":
        row.update(name=item["name"], topic=item.get("topic", ""),
                   reviewed=bool(item.get("review")),
                   drafted=((item.get("review") or {}).get("draft") or {}).get("status") == "ok",
                   fit=((item.get("review") or {}).get("fit") or {}).get("recommendation", ""))
        read = item.get("deep_read")
        if read:
            row["deep_read"] = f"{len(read.get('read') or {})}/{read.get('chunks', 0)}"
        for key in ("ref", "note", "requested_by", "failure", "batch", "processing"):
            if item.get(key):
                row[key] = item[key]
    elif item["kind"] == "concept":
        row.update(name=item.get("name", ""), sources=len(item.get("sources") or []),
                   usages=len(item.get("usages") or []))
    elif item["kind"] == "import":                 # V1's Applications and branch offerings
        row.update(name=item.get("name", ""), target=item.get("target", ""))
    elif item["kind"] == "topic":
        row.update(name=item.get("name", ""), what_belongs=item.get("what_belongs", ""),
                   examples=(item.get("members") or [])[:5],
                   coverage=item.get("coverage", {}), aliases=item.get("aliases", []),
                   **({"duplicate_of": item["duplicate_of"]} if item.get("duplicate_of") else {}))
    else:
        row.update(name=item.get("name", ""), source=item.get("source", ""),
                   locator=item.get("locator", ""),
                   quotes=len(item.get("quotes") or []) or (1 if item.get("source_quote") else 0))
    return row


def show(item: dict[str, Any]) -> dict[str, Any]:
    out = dict(item)
    if item["kind"] == "source":
        out["evidence_text"] = evidence_text(item)[:6000]
    return out


def note_exists(engine: Engine, name: str) -> bool:
    return engine.index.note_row(notes.safe_name(name)) is not None
