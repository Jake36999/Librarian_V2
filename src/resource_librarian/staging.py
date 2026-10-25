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
import hashlib
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from . import clerk, notes
from .coordination import atomic_write_text
from .lenses import LensStore
from .promote import Draft, PromotionInterruptedError, promote
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

    @staticmethod
    def _item_id(item_id: str) -> str:
        if not isinstance(item_id, str) or not item_id or len(item_id) > 200 or \
                item_id.startswith(".") or item_id.endswith((".", " ")) or \
                any(char in item_id for char in "/\\:\x00"):
            raise TypeError("a staged item id is a plain filename, not a path")
        return item_id

    def path(self, item_id: str) -> Path:
        item_id = self._item_id(item_id)
        for kind in KINDS:
            candidate = self.folder(kind) / f"{item_id}.json"
            if candidate.exists():
                return candidate
        raise TypeError(f"no staged item {item_id!r}")

    def load(self, item_id: str) -> dict[str, Any]:
        path = self.path(item_id)
        item = json.loads(path.read_text(encoding="utf-8"))
        self.validate_item(item, item_id, path.parent.name)
        return item

    @staticmethod
    def validate_item(item: Any, item_id: str, kind: str) -> None:
        if not isinstance(item, dict) or item.get("id") != item_id or item.get("kind") != kind:
            raise TypeError("staged item identity does not match its file")

    def save(self, item: dict[str, Any]) -> None:
        self._item_id(item["id"])
        folder = self.folder(item["kind"])
        folder.mkdir(parents=True, exist_ok=True)
        atomic_write_text(folder / f"{item['id']}.json",
                          json.dumps(item, ensure_ascii=False, indent=1))

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
        atomic_write_text(folder / f"{item['id']}.json",
                          json.dumps({**item, "quarantined_at": now_iso(), "reason": reason},
                                     ensure_ascii=False, indent=1))
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
    if item.get("promotion_progress"):
        raise TypeError("finish or reconcile interrupted acceptance before requesting another draft")
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

def decide(store: StagingStore, engine: Engine | None, item_ids: list[str], decision: str,
           reason: str = "", bottom_line: str = "", what_it_solves: str = "",
           decided_by: str = "person", session: str = "",
           fields: dict[str, Any] | None = None, *,
           index_call: Callable | None = None, topic_plan: dict | None = None, source_plan: dict | None = None,
           source_batch: dict | None = None, document_leases=None) -> list[dict[str, Any]]:
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
    if index_call is not None:
        index_call(lambda current: None)  # Fail before mutations if Core closed.
    elif engine is None:
        raise TypeError("decide requires an Engine or callback-only index access")
    mode = str(store.vault.setting("promotion", "mode") or "person")
    out = []
    batch_guard = None
    if source_batch is not None:
        from .promote import PromotionGuard
        batch_guard = PromotionGuard(store.vault, source_batch, document_leases)
    for item_id in item_ids:
        try:
            out.append(_decide_one(store, engine, item_id, decision, reason, bottom_line,
                                   what_it_solves, decided_by, session, mode,
                                   batch=len(item_ids) > 1, fields=fields or {}, index_call=index_call,
                                   topic_plan=topic_plan,
                                   source_plan=(source_batch["plans"].get(item_id) if source_batch is not None else source_plan),
                                   source_guard=batch_guard, document_leases=document_leases))
        except Refusal as refusal:
            if (topic_plan is not None or source_plan is not None or source_batch is not None) and refusal.code == "DOCUMENT_ACTIVE":
                if batch_guard is not None:
                    refusal.extra.update(completed_paths=list(dict.fromkeys(batch_guard.completed)),
                                         completed_results=out,
                                         next_action="Review completed writes and any unrecorded session handoffs before accepting remaining items.")
                raise  # Surface a Core checkpoint, not a hidden per-item conflict.
            out.append({"id": item_id, "refused": refusal.code, "detail": refusal.detail,
                        **({"completed_paths": refusal.extra["completed_paths"]}
                           if refusal.extra.get("completed_paths") else {})})
        except TypeError as exc:
            out.append({"id": item_id, "error": str(exc)})
        except PromotionInterruptedError as exc:
            out.append({"id": item_id, "error": str(exc), "completed_paths": exc.completed_paths,
                        "next_action": "Reload the staged item, inspect completed work, then explicitly finish or reconcile it."})
        except Exception as exc:
            if source_batch is None:
                raise
            # A stopped Core/service or failed admission must not hide earlier
            # committed decisions, attempt later items, or leak provider text.
            out.append({"id": item_id, "error": f"source batch interrupted ({type(exc).__name__})",
                        "completed_paths": list(dict.fromkeys(batch_guard.completed))})
            for remaining in item_ids[len(out):]:
                out.append({"id": remaining, "error": "not run: source batch interrupted; review before trying again"})
            break
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
    if item.get("revision_of"):
        target = store.vault.safe_relative(str(item["revision_of"]))
        if not target.is_file():
            problems.append("the accepted source note no longer exists")
        elif notes.load(target).frontmatter.get("type") != "source":
            problems.append("a staged source revision must target a source note")
        return {"id": item_id, "would": "merge", "ok": not problems, "problems": problems,
                "path": str(item["revision_of"]),
                "sections": [heading for heading in REVISED_SECTIONS if (item.get("sections") or {}).get(heading)]}
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


def _source_draft(store, item, bottom_line, what_it_solves, decided_by, session,
                  fields, batch, index_call):
    """Resolve the approved prose/metadata without moving attachments."""
    from . import dik
    review = ((item.get("promotion_progress") or {}).get("review") or
              (item.get("review") or {}).get("draft") or {})
    merged = dict(item.get("fields") or {})
    def validate(engine):
        kind = item.get("source_kind", "repository")
        if kind not in engine.index.model.kinds or not re.fullmatch(r"[a-z0-9_-]+", kind):
            raise TypeError("source kind is not in the vault content model")
        for key, value in (fields or {}).items():
            _check_field_override(engine.index.model, kind, key, value, store.vault.topics())
    index_call(validate)
    merged.update(fields or {})
    if batch and (bottom_line or what_it_solves):
        raise TypeError("a batch accept cannot share one Bottom Line; accept items one at a time")
    if not bottom_line:
        if review.get("status") != "ok":
            raise TypeError(f"{item['id']} has no reviewed draft: run staging_review, or give bottom_line and what_it_solves")
        bottom_line, what_it_solves = review.get("bottom_line", ""), review.get("what_it_solves", "")
        if not item.get("promotion_progress"):
            merged["drafted_by"] = review.get("model") or "clerk"
    coverage, not_examined = coverage_of(item)
    merged.setdefault("coverage", coverage)
    record = dik.load(store.vault, item["name"])
    sections = {**(item.get("sections") or {}), **dik.sections(record)} if record else dict(item.get("sections") or {})
    if record:
        merged.setdefault("dik", dik.path_for(store.vault, item["name"]).relative_to(store.vault.root).as_posix())
    if item.get("ocr"):
        o = item["ocr"]
        merged.setdefault("text_origin", f"OCR by {o.get('model')}: {o.get('read')} of {o.get('needed')} image-only pages")
    if not_examined:
        merged.setdefault("not_examined", not_examined)
    return Draft(name=item["name"], kind=item.get("source_kind", "repository"),
        title=item.get("title", item["name"]), canonical_url=item.get("canonical_url", ""),
        bottom_line=bottom_line, what_it_solves=what_it_solves or bottom_line,
        fields=merged, sections=sections, evidence=item.get("evidence") or [],
        topic=item.get("topic") or "Unfiled", attested_by=decided_by, session=session,
        captured_at=item.get("captured_at") or str(item.get("created_at") or "")[:10]), coverage


def _attachment_path(vault: Vault, rel: str) -> Path:
    from .coordination import operation_path
    normalized = str(rel).replace("\\", "/")
    if normalized.startswith(".librarian/staging/files/"):
        path = operation_path(vault, normalized)
        if not path.is_relative_to(vault.work("staging") / "files"):
            raise TypeError("hidden attachments must remain inside staging/files")
        return path
    path = vault.safe_relative(normalized)
    if any(part.startswith(".") for part in path.relative_to(vault.root).parts):
        raise TypeError("visible attachments cannot resolve into hidden vault state")
    return path


def prepare_source(store, item, bottom_line, what_it_solves, decided_by, session,
                   fields, index_call, *, reserved_destinations=()) -> dict:
    """Single-source pre-approval preparation; originals are never relocated."""
    from . import dik, promote as promotion
    from .coordination import MISSING, fingerprint, fingerprint_bytes, operation_path
    if item["status"] not in DECIDABLE["accept"] or item.get("revision_of"):
        raise TypeError("this is not a new source awaiting acceptance")
    if item.get("sensitivity") != "normal" and decided_by != "person":
        raise Refusal("SENSITIVITY_REVIEW", "only a person accepts a sensitive source")
    mode = str(store.vault.setting("promotion", "mode") or "person")
    if mode != "agent" and decided_by != "person":
        raise Refusal("PERSON_CONFIRMS", f"promotion.mode is {mode!r}: a person accepts this staged source")
    progress = item.get("promotion_progress") or {}
    if not isinstance(progress, dict) or (progress and (
            not isinstance(progress.get("source"), dict) or
            not isinstance(progress.get("copies"), list) or
            any(not isinstance(c, dict) or not all(isinstance(c.get(k), str)
                for k in ("key", "source", "destination", "fingerprint"))
                for c in progress["copies"]))):
        raise TypeError("invalid interrupted promotion record; inspect it before continuing")
    if progress and decided_by != "person":
        raise Refusal("PERSON_CONFIRMS", "a person reviews interrupted source promotion before continuing")
    state_path = store.path(item["id"])
    raw = state_path.read_bytes()
    if json.loads(raw) != item:
        raise Refusal("DOCUMENT_ACTIVE", "the staged source changed during preparation")
    state = state_path.relative_to(store.vault.root).as_posix()
    data_path = dik.path_for(store.vault, item["name"])
    data_stamp = fingerprint(data_path)
    draft, coverage = _source_draft(store, item, bottom_line, what_it_solves, decided_by,
                                     progress.get("session", session),
                                     fields, False, index_call)
    copies, reserved = [], set(reserved_destinations)
    for key in ("file", "clean_file"):
        if not item.get(key):
            continue
        source = _attachment_path(store.vault, item[key])
        rel = source.relative_to(store.vault.root).as_posix()
        if not source.is_file():
            raise TypeError(f"attachment is missing: {rel}")
        stamp = fingerprint(source)
        prior = next((c for c in progress.get("copies", []) if c.get("key") == key), None)
        if prior:
            target = store.vault.safe_relative(prior["destination"])
            folder = store.vault.root / "Sources" / draft.kind / "files"
            if target.parent != folder:
                raise TypeError("retained attachment copies must remain in the source kind's files folder")
            if (prior.get("source") != rel or prior.get("fingerprint") != stamp
                    or (target.exists() and fingerprint(target) != stamp)):
                raise Refusal("DOCUMENT_ACTIVE", "an interrupted attachment or retained copy changed; inspect before continuing")
        else:
            folder = store.vault.root / "Sources" / draft.kind / "files"
            base = source.name if key == "file" or not copies else Path(copies[0]["destination"]).stem + " (clean text).md"
            target = folder / base
            n = 2
            while target.exists() or target.as_posix().casefold() in reserved:
                target = folder / f"{Path(base).stem} ({n}){Path(base).suffix}"
                n += 1
        dest = target.relative_to(store.vault.root).as_posix()
        # Reject redirects before either a source or an attachment is written.
        if operation_path(store.vault, dest) != target:
            raise TypeError("attachment destination redirects through a link")
        if target.as_posix().casefold() in reserved:
            raise TypeError("attachment targets collide")
        reserved.add(target.as_posix().casefold())
        copies.append({"key": key, "source": rel, "destination": dest, "fingerprint": stamp,
                       "before": fingerprint(target)})
        draft.fields["file" if key == "file" else "file_markdown"] = dest
    requested = asdict(draft)
    requested.pop("attested_by")  # Explicit human resumption may attest prior agent work.
    request_hash = hashlib.sha256(json.dumps(requested, sort_keys=True, default=str).encode()).hexdigest()
    if progress and (progress.get("version") != 1 or progress.get("request_hash") != request_hash):
        raise Refusal("DOCUMENT_ACTIVE", "approved source content changed since interruption; use source revision review rather than replacing it")
    resume = progress.get("source") if progress.get("source", {}).get("fingerprint") not in (None, MISSING) else None
    plan = promotion.prepare(store.vault, draft, index_call, resume=resume)
    plan.update(item_id=item["id"], coverage=coverage, request_hash=request_hash, copies=copies,
                state_path=state)
    plan["targets"].extend([state, *[c["destination"] for c in copies]])
    plan["observed"].extend([(state, fingerprint_bytes(raw)),
        (data_path.relative_to(store.vault.root).as_posix(), data_stamp)])
    for copy in copies:
        plan["observed"].extend([(copy["source"], copy["fingerprint"]), (copy["destination"], copy["before"])])
    if len(dict(plan["observed"])) > 200:
        raise TypeError("source acceptance exceeds the 200-file recovery bound")
    return plan


def prepare_source_batch(store, items: list[dict], decided_by: str, session: str,
                         index_call) -> dict:
    """One bounded source-only acceptance inventory, prepared before approval.

    A shared guard advances only hashes of our own durable writes, never a
    fresh fingerprint of arbitrary content after a prior item. Source plans
    still render current generated backlinks/views on the Core SQL worker.
    """
    targets, observed, plans, reserved, names = [], {}, {}, set(), set()
    for item in items:
        item_id = item["id"]
        if item_id in plans:
            continue  # The second decision still reports "already accepted".
        try:
            if item.get("promotion_progress"):
                raise TypeError("review and finish interrupted source acceptance one item at a time")
            plan = prepare_source(store, item, "", "", decided_by,
                str((item.get("found_for") or {}).get("session") or session or ""), {}, index_call,
                reserved_destinations=reserved)
            if plan["name"].casefold() in names:
                raise Refusal("UNIQUE_NOTE_NAMES", "another source in this batch has the same destination; accept it separately")
        except (Refusal, TypeError) as exc:
            plans[item_id] = {"item_id": item_id,
                "error": exc.detail if isinstance(exc, Refusal) else str(exc),
                **({"refused": exc.code} if isinstance(exc, Refusal) else {})}
            continue
        for path, stamp in plan["observed"]:
            if path in observed and observed[path] != stamp:
                raise Refusal("DOCUMENT_ACTIVE", "a shared source-batch dependency changed during preparation")
            observed[path] = stamp
        names.add(plan["name"].casefold())
        reserved.update((store.vault.root / c["destination"]).as_posix().casefold() for c in plan["copies"])
        targets.extend(plan["targets"])
        plans[item_id] = plan
    if len(observed) > 200:
        raise TypeError("source batch exceeds the 200-file recovery bound; accept it in smaller groups")
    return {"operation": "new_sources", "plans": plans,
            "targets": list(dict.fromkeys(targets)), "observed": list(observed.items())}


def _accept_prepared_source(store, item, plan, index_call, leases, entry, guard=None):
    from . import promote as promotion
    from .coordination import fingerprint, operation_path
    if plan.get("error"):
        if plan.get("refused"):
            raise Refusal(plan["refused"], plan["error"])
        raise TypeError(plan["error"])
    if plan.get("item_id") != item["id"]:
        raise TypeError("source acceptance requires its own prepared plan")
    index_call(lambda current: None)  # Each item checks Core admission before copying.
    guard = guard or promotion.PromotionGuard(store.vault, plan, leases)
    start = len(guard.completed)
    try:
        for copy in plan["copies"]:
            guard.copy(copy["source"], copy["destination"])
        report = promotion.apply(store.vault, Draft(**plan["draft"]), plan, index_call, leases=leases, guard=guard)
        guard.check()
        item.update(status="accepted", accepted_to=report.path, promotion=report.to_dict(),
                    sections=plan["draft"]["sections"],
                    attachment_copies=[{k: c[k] for k in ("key", "source", "destination", "fingerprint")} for c in plan["copies"]])
        for copy in plan["copies"]:
            item[copy["key"]] = copy["destination"]
        if item.get("promotion_progress"):
            item["promotion_progress"]["completed_at"] = now_iso()
        item["history"].append(entry)
        guard.write(plan["state_path"], json.dumps(item, ensure_ascii=False, indent=1))
        return {"id": item["id"], "status": "accepted", "coverage": plan["coverage"], "promotion": report.to_dict(),
                "originals_retained": [c["source"] for c in plan["copies"]]}
    except Exception as exc:
        completed = list(dict.fromkeys(guard.completed[start:]))
        state = plan["state_path"]
        if completed and fingerprint(operation_path(store.vault, state)) == guard.expected[state]:
            fresh = store.load(item["id"])
            fresh["promotion_progress"] = {"version": 1, "request_hash": plan["request_hash"],
                "source": {"path": plan["path"], "fingerprint": guard.expected[plan["path"]], "linked": plan["linked"]},
                "copies": [{k: c[k] for k in ("key", "source", "destination", "fingerprint")} for c in plan["copies"]],
                "completed_paths": completed, "at": now_iso(), "session": plan["draft"]["session"],
                "review": {"status": "ok", "bottom_line": plan["draft"]["bottom_line"],
                           "model": plan["draft"]["fields"].get("drafted_by", ""),
                           "what_it_solves": plan["draft"]["what_it_solves"]}}
            fresh["fields"], fresh["sections"] = plan["draft"]["fields"], plan["draft"]["sections"]
            fresh.setdefault("history", []).append({**entry, "decision": "partial_accept", "completed_paths": completed})
            try:
                # Recording progress must not overwrite an outside staged edit.
                # Other conflicted documents need not be rewritten or rebased.
                text = json.dumps(fresh, ensure_ascii=False, indent=1)
                atomic_write_text(operation_path(store.vault, state), text)
                from .coordination import fingerprint_bytes
                guard.expected[state] = fingerprint_bytes(text.encode("utf-8"))
                guard.completed.append(state)
            except OSError:
                pass  # Existing durable operation recovery covers ambiguous persistence.
        if isinstance(exc, Refusal):
            exc.extra["completed_paths"] = completed
            raise
        if isinstance(exc, promotion.PromotionInterruptedError):
            raise promotion.PromotionInterruptedError(exc, completed) from exc
        raise promotion.PromotionInterruptedError(exc, completed) from exc


def _decide_one(store, engine, item_id, decision, reason, bottom_line, what_it_solves,
                decided_by, session, mode, batch, fields: dict[str, Any] | None = None,
                index_call: Callable | None = None, topic_plan: dict | None = None, source_plan: dict | None = None,
                source_guard=None,
                document_leases=None
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
        if decision == "accept" and item.get("sensitivity") != "normal" and decided_by != "person":
            raise Refusal("SENSITIVITY_REVIEW", "only a person accepts a sensitive source revision")
        return _decide_revision(store, engine, item, decision, entry, decided_by, mode, index_call=index_call)
    if decision == "reject":
        item["status"] = "rejected"
        item["history"].append(entry)
        if item.get("file") and not item.get("promotion_progress"):
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
        if item.get("promotion_progress"):
            raise TypeError("review and finish interrupted acceptance, or defer/reject it; do not re-ingest partial writes")
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
        try:
            done = taxonomy.accept(store.vault, engine, item, decided_by, fields or {},
                                   index_call=index_call, prepared=topic_plan, leases=document_leases)
        except (Refusal, taxonomy.TaxonomyInterruptedError) as exc:
            completed = exc.extra.get("completed_paths", []) if isinstance(exc, Refusal) else exc.completed_paths
            if topic_plan is not None and (topic_plan["taxonomy_path"] in completed or item.get("acceptance_progress")):
                request = topic_plan["request"]
                prior = item.get("acceptance_progress") or {}
                item["acceptance_progress"] = {"version": 1, "topic": topic_plan["result"]["topic"],
                    "row": topic_plan["topic_row"], "request": request, "at": now_iso(),
                    "completed_paths": list(dict.fromkeys([*prior.get("completed_paths", []), *completed]))}
                # Retain the person's approved wording for the next explicit review.
                item.update(name=request["name"], what_belongs=request["what_belongs"], aliases=request["aliases"])
                item["history"].append({**entry, "decision": "partial_accept", "completed_paths": completed})
                store.save(item)
            raise
        item.update(status="accepted", accepted_to=f"About/Topics.md#{done['topic']}")
        if item.get("acceptance_progress"):
            item["acceptance_progress"]["completed_at"] = now_iso()
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
        atomic_write_text(target, notes.render(front, item.get("body", "")))
        _upsert(engine, target, index_call)
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
                              given.get("aliases") or [], given.get("related") or [], index_call=index_call)
        item.update(status="accepted", accepted_to=path)
        item["history"].append(entry)
        store.save(item)
        return {"id": item_id, "status": "accepted", "path": path}

    if source_plan is not None:
        return _accept_prepared_source(store, item, source_plan, index_call, document_leases, entry, source_guard)
    if item.get("promotion_progress"):
        raise TypeError("review and finish interrupted source acceptance one item at a time")
    draft, coverage = _source_draft(store, item, bottom_line, what_it_solves, decided_by, session,
                                    fields, batch, lambda fn: fn(engine))
    item["sections"] = draft.sections
    if item.get("file"):
        kind = item.get("source_kind", "document")
        draft.fields["file"] = _move_file(store.vault, item,
                                    store.vault.root / "Sources" / kind / "files")
        if item.get("clean_file"):
            draft.fields["file_markdown"] = item["clean_file"]
    report = promote(store.vault, engine, draft)
    item.update(status="accepted", accepted_to=report.path, promotion=report.to_dict())
    item["history"].append(entry)
    store.save(item)
    return {"id": item_id, "status": "accepted", "coverage": coverage,
            "promotion": report.to_dict()}


REVISED_SECTIONS = ("Claims", "Evidence & Limits", "Reading Notes",
                    # a D/I/K rebuild of an accepted note (dik_rebuild, 2026-10-01)
                    "Components", "How It Fits Together", "Chapters", "How The Chapters Relate")


def _decide_revision(store, engine, item: dict[str, Any], decision: str, entry: dict[str, Any],
                     decided_by: str, mode: str, *, index_call: Callable | None = None) -> dict[str, Any]:
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
    path = store.vault.safe_relative(str(item["revision_of"]))
    if not path.is_file():
        raise TypeError(f"{item['revision_of']} no longer exists")
    note = notes.load(path)
    if note.frontmatter.get("type") != "source":
        raise TypeError("a staged source revision must target a source note")
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
    atomic_write_text(path, notes.render(note.frontmatter, body))
    _upsert(engine, path, index_call)
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


def _upsert(engine: Engine | None, path: Path, index_call: Callable | None) -> None:
    if index_call is not None:
        index_call(lambda current: current.index.upsert(path))
    else:
        engine.index.upsert(path)


def _write_concept(vault: Vault, engine: Engine | None, item: dict[str, Any], concept_kind: str,
                   definition: str, aliases: list[str], related: list[str], *,
                   index_call: Callable | None = None) -> str:
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
    atomic_write_text(path, notes.render(fm, body))
    _upsert(engine, path, index_call)
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
