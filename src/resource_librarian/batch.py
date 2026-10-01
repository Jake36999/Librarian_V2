"""The approved batch: processing a person started (Requirements - Research Pipeline §4.2-4.3,
Addendum R14).

A person approves sources in Staging; that only queues them (`approved`). Nothing reads
them until a person begins the batch - `process_approved`, a curate-tier tool, so no model
call, approval, refresh or restart can start one. The batch takes exactly the approved set
at that moment; anything approved while it runs waits for the next one.

Each item goes through the stages below, every stage logged against (item, stage) in the
run log (`.librarian/runs/batch-*.jsonl`, the workflow run store), so a crash or a cancel
resumes where it stopped and never repeats a completed stage. One item failing never
undoes another's work. At the end an item is `enriched` when every stage completed, or
`partial` when one did not (text it could not read, a clerk that did not answer, a read
stopped early) - never enriched with a stage outstanding. A partial item can be approved
again: its finished stages are carried over and only the rest run. Either waits for the
separate "Accept into library", which records the coverage on the note.

The stages call registered tools through the registry, as any other action does (§7).
Project context (the brief, the need) never reaches them: the fit judgement was made at
capture, apart from the reading (§4.4).
"""
from __future__ import annotations

import secrets
import threading
from typing import Any, Callable

from . import deep_read as reading
from .registry import REGISTRY, Context
from .staging import StagingStore
from .vault import Vault, now_iso
from .workflows import RunStore

NAME = "process-approved"
MAX_READ_CALLS = 40                  # deep_read is chunked; enough calls for a long book

_LIVE: dict[str, tuple[str, threading.Thread | None, threading.Event]] = {}
_GUARD = threading.RLock()


# ------------------------------------------------------------------ stages
# Each takes (ctx, item) and returns {"status": complete|partial|queued|skipped|failed, ...}.

def _validate(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    from .tools.library import engine_for
    held = engine_for(ctx, refresh=False).index.note_row(item["name"])
    if held is not None:
        return {"status": "failed", "reason": f"already in the library: {held['path']}"}
    if not (item.get("evidence") or item.get("file")):
        return {"status": "failed", "reason": "no evidence was captured"}
    return {"status": "complete", "captured_at": item.get("captured_at", ""),
            "canonical_url": item.get("canonical_url", "")}


def _parse(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    """The per-kind branch on what capture found (quality.py): a paper's open-access PDF is
    fetched, a mechanically extracted PDF is cleaned into markdown, and what cannot be read
    here (a scan, a script-built page) is said, not guessed around."""
    q = (item.get("intake") or {}).get("quality") or {}
    verdict, done = q.get("verdict", "usable"), {}
    if verdict == "metadata_only" and q.get("full_text_url") and not item.get("file"):
        done = _fetch_full_text(ctx, item, q["full_text_url"])
        if done.get("status") == "partial":
            return done
        item = StagingStore(ctx.vault).load(item["id"])
    elif verdict == "needs_ocr" and str(item.get("file", "")).lower().endswith(".pdf") \
            and not item.get("clean_file"):
        done = _ocr(ctx, item)
        if done.get("status") == "partial":
            return done
        item = StagingStore(ctx.vault).load(item["id"])
        verdict = "usable" if done.get("ocr_complete") else verdict
    elif verdict == "cleanup" and item.get("file") and not item.get("clean_file"):
        out = REGISTRY.call("pdf_to_markdown", {"file": item["file"],
                                                "staged_item": item["id"]}, ctx)
        if "error" in out:
            done = {"cleanup": f"not run: {out.get('detail') or out['error']}"}
        else:
            store = StagingStore(ctx.vault)
            fresh = store.load(item["id"])
            fresh["clean_file"] = out["path"]
            store.save(fresh)
            item, done = fresh, {"cleanup": f"cleaned into {out['path']}"}
    chunks = reading.chunk(reading.source_units(ctx.vault, item))
    if not chunks:
        return {"status": "partial", "chunks": 0, **done,
                "reason": q.get("reason") if verdict in ("needs_ocr", "js_shell") else
                "no readable text: a scanned file needs OCR, a script-built page needs a "
                "rendered read"}
    if verdict in ("needs_ocr", "js_shell"):
        return {"status": "partial", "chunks": len(chunks), **done,
                "reason": done.get("ocr_gap") or q.get("reason", "")}
    if str(done.get("cleanup", "")).startswith("not run"):
        return {"status": "partial", "chunks": len(chunks), **done,
                "reason": f"read from the raw extraction: cleanup {done['cleanup']}"}
    return {"status": "complete", "chunks": len(chunks), **done}


def _ocr(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    """Slot 4 (R17): the image-only pages read by the library's OCR model, through the
    registered tool; with no model chosen, the scan stays a stated gap."""
    from . import ocr
    try:
        chosen = ocr.endpoint(ctx.vault, ctx.extras)
    except ocr.OcrError as exc:
        return {"status": "partial", "reason": f"the pages have no text layer, and OCR was "
                                               f"not run: {exc}"}
    if chosen is None:
        return {"status": "partial", "reason": "the pages have no text layer, and no OCR "
                "model is chosen (Settings -> Connections, slot 4)"}
    out = REGISTRY.call("ocr_pdf", {"file": item["file"], "staged_item": item["id"]}, ctx)
    if "error" in out:
        return {"status": "partial", "reason": f"the pages have no text layer, and OCR was "
                                               f"not run: {out.get('detail') or out['error']}"}
    if not out.get("read"):
        why = (out.get("errors") or [{}])[0].get("error", "no page came back")
        return {"status": "partial", "reason": f"the pages have no text layer, and OCR read "
                                               f"none of them: {why}"}
    store = StagingStore(ctx.vault)
    fresh = store.load(item["id"])
    fresh["clean_file"] = out["path"]
    fresh["ocr"] = {k: out[k] for k in ("model", "pages", "needed", "read")}
    store.save(fresh)
    complete = out["read"] >= out["needed"] and not out.get("errors")
    return {"ocr": f"{out['read']} of {out['needed']} image-only pages read by {out['model']}",
            "ocr_complete": complete,
            **({} if complete else {"ocr_gap": f"OCR read {out['read']} of {out['needed']} "
                                               f"image-only pages"})}


def _fetch_full_text(ctx: Context, item: dict[str, Any], url: str) -> dict[str, Any]:
    """A paper's open-access PDF, kept with the item (moved beside its note on accept)."""
    from . import intake, text
    fetcher = ctx.extras.get("fetcher") or intake.Fetcher()
    try:
        raw = fetcher.get(url, "application/pdf")
    except intake.FetchError as exc:
        return {"status": "partial", "reason": f"open-access PDF not fetched: {exc}"}
    if raw[:5] != b"%PDF-":
        return {"status": "partial", "reason": f"{url} did not return a PDF"}
    folder = ctx.vault.work("staging") / "files"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{item['id']}.pdf"
    path.write_bytes(raw)
    got = text.extract(path, ctx.vault.derived / "text")
    store = StagingStore(ctx.vault)
    fresh = store.load(item["id"])
    fresh["file"] = path.relative_to(ctx.vault.root).as_posix()
    fresh["full_text"] = {"url": url, "pages": len(got.pages), "empty_pages": got.empty_pages}
    store.save(fresh)
    return {"full_text": f"{len(got.pages)} pages from {url}"}


def _read(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for _ in range(MAX_READ_CALLS):
        out = REGISTRY.call("deep_read", {"item_id": item["id"]}, ctx)
        if "error" in out:
            if "no text to read" in str(out.get("detail", "")):
                return {"status": "skipped", "reason": "no text to read"}
            return {"status": "failed", "reason": str(out.get("detail") or out["error"])}
        if not out.get("remaining") or not out.get("this_call"):
            break
    coverage = f"{out.get('read', 0)}/{out.get('chunks', 0)}"
    if not out.get("remaining"):
        return {"status": "complete", "coverage": coverage,
                "lenses_staged": out.get("lenses_staged", [])}
    return {"status": "queued" if not out.get("this_call") else "partial",
            "coverage": coverage, "reason": "waiting for the clerk model"
            if not out.get("this_call") else "stopped before the end"}


def _review(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    out = REGISTRY.call("staging_review", {"item_id": item["id"]}, ctx)   # unframed: no need
    if "error" in out:
        return {"status": "failed", "reason": str(out.get("detail") or out["error"])}
    draft = (out.get("draft") or {}).get("status", "")
    if draft == "ok":
        return {"status": "complete", "draft": draft}
    return {"status": "queued", "draft": draft,
            "reason": "waiting for the clerk model to draft the Bottom Line"}


def _lenses(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    """Lens extraction happens as the text is read; this stage says what it staged, so it is
    never a hidden side effect - each lens waits in Staging -> Lenses for its own review."""
    staged = list(((item.get("deep_read") or {}).get("lenses")) or [])
    if not (item.get("deep_read") or {}).get("read"):
        return {"status": "not_applicable", "reason": "nothing was read, so nothing to draw "
                                                      "lenses from"}
    return {"status": "complete", "staged": len(staged),
            **({"lenses": staged[:10]} if staged else {})}


def _data(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    """Data records (R16): a repository's components from its evidence; a document's
    chapters from its text, each with coverage and the claims read from it."""
    from . import dik
    kind = item.get("source_kind", "")
    if kind == "repository":
        record = dik.repository(ctx.vault, item["name"],
                                [e.get("id") for e in item.get("evidence") or []],
                                str((item.get("fields") or {}).get("pushed_at") or ""))
    elif kind in ("document", "paper", "standard") and (item.get("clean_file") or item.get("file")):
        units = reading.source_units(ctx.vault, item)
        pages = [t for _, t in units]
        chunks = reading.chunk(units)
        record = dik.document(ctx.vault, item["name"], pages,
                              (item.get("deep_read") or {}).get("read"),
                              [(c.first_page, c.last_page) for c in chunks],
                              str(item.get("captured_at") or ""))
    elif kind == "model":
        record = dik.model(item["name"], item.get("fields") or {},
                           str(item.get("captured_at") or ""))
    elif kind == "dataset":
        record = dik.dataset(ctx.vault, item["name"], {**(item.get("fields") or {}),
                                                       "canonical_url": item.get("canonical_url")},
                             str(item.get("captured_at") or ""))
    else:
        return {"status": "not_applicable", "reason": f"no component model for a "
                                                      f"{kind or 'source'} yet; its note rests "
                                                      f"on the description"}
    if not record["data"]:
        return {"status": "partial", "reason": "no components were found in what was captured"}
    dik.save(ctx.vault, record)
    partial = str(record.get("coverage", "")).startswith("partial")
    return {"status": "partial" if partial else "complete", "records": len(record["data"]),
            "relations": len(record["information"]), "coverage": record["coverage"],
            **({"reason": record["coverage"]} if partial else {})}


def _relate(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    """Information (R16): a repository's static relations are drawn with its Data; a
    document's chapters are related by a model reading only the fully read ones."""
    from . import dik
    from .tools.staging import clerk_endpoint
    record = dik.load(ctx.vault, item["name"])
    if not record:
        return {"status": "not_applicable", "reason": "no Data records to relate"}
    if record["kind"] != "document":
        return {"status": "complete", "relations": len(record["information"])}
    if sum(1 for d in record["data"] if d.get("kind") == "chapter") < 2:
        return {"status": "not_applicable", "reason": "a single part: nothing to relate"}
    out = dik.relate_chapters(record, clerk_endpoint(ctx), ctx.vault.work("queue") / "clerk")
    dik.save(ctx.vault, record)
    if "the clerk did not answer" in str(out.get("reason", "")):
        return {"status": "queued", "reason": "waiting for the clerk model to relate chapters"}
    if out.get("reason"):
        return {"status": "partial", "reason": out["reason"]}
    return {"status": "complete", "relations": out["added"]}


def _metadata(ctx: Context, item: dict[str, Any]) -> dict[str, Any]:
    """Metadata proposals (R16): fields the content model requires that are still unknown,
    and values the Data can supply - proposals on the item, confirmed at acceptance."""
    from . import dik
    from .intake import readiness
    from .tools.library import engine_for
    fields = dict(item.get("fields") or {})
    record = dik.load(ctx.vault, item["name"])
    proposed = {}
    languages = [d["name"] for d in record.get("data", []) if d.get("kind") == "language"]
    if languages and not fields.get("language"):
        proposed["language"] = languages[0]
    if proposed:
        store = StagingStore(ctx.vault)
        fresh = store.load(item["id"])
        fresh["fields"] = {**fresh.get("fields", {}), **proposed}
        fresh["metadata_proposals"] = {k: "from the Data records" for k in proposed}
        store.save(fresh)
        fields.update(proposed)
    missing = readiness(engine_for(ctx, refresh=False), item.get("source_kind", ""), fields)
    # fields still unknown are listed for the person, not counted against how much was read
    return {"status": "complete", **({"unknown": missing} if missing else {}),
            **({"proposed": proposed} if proposed else {})}


STAGES: list[tuple[str, Callable[[Context, dict[str, Any]], dict[str, Any]]]] = [
    ("validate", _validate), ("parse", _parse), ("read", _read), ("lenses", _lenses),
    ("data", _data), ("relate", _relate), ("metadata", _metadata), ("review", _review)]


# ------------------------------------------------------------------ the run

def waiting(vault: Vault) -> list[str]:
    return [i["id"] for i in StagingStore(vault).items("source", "approved")]


def live(vault: Vault) -> str:
    """The batch running in this process for this vault, or ""."""
    with _GUARD:
        entry = _LIVE.get(str(vault.root))
    if entry and (entry[1] is None or entry[1].is_alive()):
        return entry[0]
    return ""


def latest(vault: Vault) -> str:
    runs = RunStore(vault)
    if not runs.folder.exists():
        return ""
    paths = sorted(runs.folder.glob("batch-*.jsonl"), key=lambda p: p.stat().st_mtime)
    return paths[-1].stem if paths else ""


def status(vault: Vault, run_id: str = "") -> dict[str, Any]:
    """The banner's view: what runs, where it is, and what waits for the next run."""
    run_id = run_id or latest(vault)
    out: dict[str, Any] = {"waiting": len(waiting(vault)), "running": live(vault)}
    if not run_id:
        return out
    events = RunStore(vault).events(run_id)
    items = events[0].get("items", [])
    done = {(e["item"], e["stage"]): e for e in events if e["type"] == "done"}
    finished = {e["item"]: e for e in events if e["type"] == "item"}
    last = events[-1]
    state = last["type"] if last["type"] in ("finished", "cancelled") else (
        "running" if run_id == out["running"] else "interrupted")
    current = next(({"item": e["item"], "stage": e["stage"],
                     **({"detail": e["detail"]} if e["type"] == "progress" else {})}
                    for e in reversed(events) if e["type"] in ("done", "stage", "progress")), {})
    out.update(run=run_id, status=state, total=len(items), processed=len(finished),
               current=current if state == "running" else {},
               items=[{"id": i, **({"status": finished[i]["status"],
                                     "coverage": finished[i].get("coverage", "")}
                                    if i in finished else {"status": "processing"}),
                       "stages": {s: done[(i, s)]["status"] for s, _ in STAGES
                                  if (i, s) in done}} for i in items])
    if last["type"] == "cancelled":
        out["detail"] = last.get("detail", "")
    return out


def start(ctx: Context, requested_by: str, resume: str = "",
          background: bool = False) -> dict[str, Any]:
    """Begin the approved batch, or resume an interrupted one. Idempotent: while one runs,
    another start reports it and does nothing."""
    vault = ctx.vault
    runs = RunStore(vault)
    with _GUARD:
        running = live(vault)
        if running:
            return {"started": False, "already_running": running, **status(vault, running)}
        if resume:
            events = runs.events(resume)
            if events[-1]["type"] in ("finished", "cancelled") and not _unfinished(vault, resume):
                return {"started": False, "detail": f"{resume} has nothing left to do"}
            run_id, items = resume, events[0].get("items", [])
            runs.append(run_id, {"type": "resumed", "by": requested_by})
        else:
            items = waiting(vault)
            if not items:
                return {"started": False, "waiting": 0, "detail": "nothing is approved"}
            run_id = f"batch-{now_iso()[:10]}-{secrets.token_hex(3)}"
            runs.append(run_id, {"type": "started", "name": NAME, "kind": "batch",
                                 "items": items, "requested_by": requested_by})
            store = StagingStore(vault)
            for item_id in items:
                item = store.load(item_id)
                item.update(status="processing", batch=run_id)
                store.save(item)
        cancel = ctx.extras.get("cancel") or threading.Event()
        _LIVE[str(vault.root)] = (run_id, None, cancel)
    worker_ctx = Context(tier=ctx.tier, vault=vault, extras={**ctx.extras, "cancel": cancel})
    if background:
        thread = threading.Thread(target=_run, args=(worker_ctx, run_id, items, cancel),
                                  daemon=True, name=f"batch-{run_id}")
        with _GUARD:
            _LIVE[str(vault.root)] = (run_id, thread, cancel)
        thread.start()
        return {"started": True, "run": run_id, "items": items, "status": "running"}
    try:
        _run(worker_ctx, run_id, items, cancel)
    finally:
        with _GUARD:
            _LIVE.pop(str(vault.root), None)
    return {"started": True, **status(vault, run_id)}


def cancel(vault: Vault) -> dict[str, Any]:
    with _GUARD:
        entry = _LIVE.get(str(vault.root))
    if not entry:
        return {"cancelling": "", "detail": "no batch is running"}
    entry[2].set()
    return {"cancelling": entry[0]}


def _unfinished(vault: Vault, run_id: str) -> list[str]:
    events = RunStore(vault).events(run_id)
    finished = {e["item"] for e in events if e["type"] == "item"}
    return [i for i in events[0].get("items", []) if i not in finished]


def _run(ctx: Context, run_id: str, items: list[str], cancel: threading.Event) -> None:
    runs, store = RunStore(ctx.vault), StagingStore(ctx.vault)
    try:
        done = {(e["item"], e["stage"]): e for e in runs.events(run_id) if e["type"] == "done"}
        finished = {e["item"] for e in runs.events(run_id) if e["type"] == "item"}
        last = ""
        for item_id in items:
            if item_id in finished:
                continue
            results: dict[str, dict[str, Any]] = {}
            prior = (store.load(item_id).get("processing") or {})
            for stage, fn in STAGES:
                if (item_id, stage) in done:                  # resumed: never done twice
                    results[stage] = done[(item_id, stage)]
                    continue
                if (prior.get("stages") or {}).get(stage) == "complete":   # an earlier run's
                    results[stage] = {"status": "complete", "carried": prior.get("run", ""),
                                      **({"coverage": prior["read_coverage"]}
                                         if stage == "read" and prior.get("read_coverage")
                                         else {})}
                    continue
                if cancel.is_set():
                    runs.append(run_id, {"type": "cancelled",
                                         "detail": f"cancelled after {last or 'the start'}"})
                    return
                runs.append(run_id, {"type": "stage", "item": item_id, "stage": stage})
                # A long step says how far it has got (the PDF clean-up's parts), so the
                # banner never sits on one stage for minutes with nothing to show.
                ctx.extras["progress"] = (lambda detail, i=item_id, s=stage: runs.append(
                    run_id, {"type": "progress", "item": i, "stage": s, "detail": detail}))
                try:
                    result = fn(ctx, store.load(item_id))
                except Exception as exc:                      # noqa: BLE001 - one item
                    result = {"status": "failed", "reason": f"{type(exc).__name__}: {exc}"}
                runs.append(run_id, {"type": "done", "item": item_id, "stage": stage,
                                     **result})
                results[stage] = result
                last = f"{item_id}: {stage}"
                if result["status"] == "failed":
                    break
            _finish_item(store, runs, run_id, item_id, results)
        runs.append(run_id, {"type": "finished"})
    finally:
        with _GUARD:
            entry = _LIVE.get(str(ctx.vault.root))
            if entry and entry[0] == run_id and entry[1] is not None:
                _LIVE.pop(str(ctx.vault.root), None)


def _finish_item(store: StagingStore, runs: RunStore, run_id: str, item_id: str,
                 results: dict[str, dict[str, Any]]) -> None:
    item = store.load(item_id)
    failed = next((s for s, r in results.items() if r.get("status") == "failed"), "")
    incomplete = [f"{s}: {r.get('reason') or r['status']}" for s, r in results.items()
                  if r.get("status") in ("partial", "queued", "skipped")]
    coverage = (results.get("read") or {}).get("coverage", "")
    item["processing"] = {"run": run_id, "at": now_iso(),
                          "stages": {s: r.get("status") for s, r in results.items()},
                          "coverage": "full" if not incomplete and not failed else
                          (f"partial {coverage}" if coverage else "partial"),
                          **({"read_coverage": coverage} if coverage else {}),
                          **({"not_examined": incomplete} if incomplete else {})}
    if failed:
        item.update(status="failed", failure={"stage": failed, "reason": results[failed].get(
            "reason", ""), "at": now_iso()})
    else:
        item["status"] = "partial" if incomplete else "enriched"
    item.setdefault("history", []).append({"decision": item["status"], "at": now_iso(),
                                           "batch": run_id})
    store.save(item)
    runs.append(run_id, {"type": "item", "item": item_id, "status": item["status"],
                         "coverage": item["processing"]["coverage"]})
