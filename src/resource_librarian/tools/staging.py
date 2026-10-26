"""Staging review: the airlock, and the lens store the app reads."""
from __future__ import annotations

import json
import re
from pathlib import PurePosixPath
from typing import Literal

from .. import clerk, concepts, notes, revisions, staging
from ..coordination import fingerprint, fingerprint_bytes
from ..revisions import WriteIntent
from ..rules import Refusal
from .. import deep_read as reading
from ..lenses import LensStore
from ..registry import Card, Context, tool
from ..session import SessionStore
from ..vault import now_iso
from .library import IndexGateway, with_engine


def _store(ctx: Context) -> staging.StagingStore:
    return staging.StagingStore(ctx.vault)


def _snapshot(ctx: Context, item_id: str) -> tuple[dict, str, str]:
    store = _store(ctx)
    path = store.path(item_id)
    raw = path.read_bytes()
    item = json.loads(raw.decode("utf-8"))
    store.validate_item(item, item_id, path.parent.name)
    return item, path.relative_to(ctx.vault.root).as_posix(), fingerprint_bytes(raw)


def _profile_endpoint(ctx: Context, role: str, endpoint: clerk.Endpoint | None,
                      tier: int) -> clerk.Endpoint | None:
    """Apply the Core's role profile to a background endpoint when available.

    Standalone CLI/test contexts deliberately retain the established endpoint
    contract.  An active Core supplies the factory, which makes Clerk/Scribe
    calls use the same vault-scoped profile constraints as chat and helpers.
    """
    factory = ctx.extras.get("background_profile_endpoint")
    if endpoint is not None and callable(factory):
        return factory(role, endpoint, tier)
    return endpoint


def clerk_endpoint(ctx: Context) -> clerk.Endpoint | None:
    """The surface's endpoint, else the vault's configured one, else the
    surface's fallback (MCP sampling), else None and the tasks queue."""
    from .. import effort
    endpoint = ctx.extras.get("clerk")
    if endpoint is None:
        endpoint = clerk.from_config(ctx.vault.config().get("clerk") or {})
    if endpoint is None:
        endpoint = ctx.extras.get("clerk_fallback")
    if "effort" in ctx.extras:                 # the person's effort: the clerk's parallel calls
        effort.apply_concurrency(endpoint, effort.of(ctx)["tier3_agents"])
    return _profile_endpoint(ctx, "clerk", endpoint, 3)


def scribe_endpoint(ctx: Context) -> clerk.Endpoint | None:
    """Tier 2: the surface's scribe, else `[scribe]` in config, else the
    surface's fallback (the loop's own model in a fresh call, or MCP sampling)."""
    endpoint = ctx.extras.get("scribe")
    if endpoint is None:
        try:
            endpoint = clerk.from_config(ctx.vault.config().get("scribe") or {})
        except clerk.ClerkUnavailable:
            endpoint = None
    if endpoint is None:
        endpoint = ctx.extras.get("scribe_fallback") or ctx.extras.get("clerk_fallback")
    if "effort" in ctx.extras:
        from .. import effort
        effort.apply_concurrency(endpoint, effort.of(ctx)["tier2_agents"])
    return _profile_endpoint(ctx, "scribe", endpoint, 2)


@tool("staging_list", tier="consult", effect="read",
      returns=("counts", "total", "items"),
      card=Card("What waits in staging: counts, and a page of items",
                "reviewing the airlock", "Sensitive items are marked"))
def staging_list(ctx: Context, kind: Literal["", "source", "lens", "concept", "topic",
                                             "import", "model_expectation"] = "",
                 status: Literal["", "queued", "staged", "approved", "processing", "enriched",
                                 "partial", "deferred", "accepted", "failed"] = "staged",
                 limit: int = 25, offset: int = 0) -> dict:
    store = _store(ctx)
    rows = [staging.summary(i) for i in store.items(kind, status)]
    return {"counts": store.counts(), "total": len(rows),
            "items": rows[offset:offset + limit]}


@tool("staging_show", tier="consult", effect="read",
      card=Card("One staged item in full, with its evidence and any review",
                "deciding an item"))
def staging_show(ctx: Context, item_id: str) -> dict:
    item, state, observed = _snapshot(ctx, item_id)
    out = staging.show(item)
    if item.get("promotion_progress", {}).get("review"):
        out["review"] = {**(out.get("review") or {}), "draft": item["promotion_progress"]["review"]}
    out["staged_revision"] = revisions.issue(ctx, state, observed)
    destination = item.get("revision_of") or ((item.get("promotion_progress") or {}).get("source") or {}).get("path")
    if destination and ctx.vault.safe_relative(str(destination)).is_file():
        path = ctx.vault.safe_relative(str(destination))
        rel = path.relative_to(ctx.vault.root).as_posix()
        out["revision"] = revisions.issue_current(ctx, rel)
    return out


@tool("staging_review", tier="contribute", effect="write", scope="session", open_world=True,
      returns=("id", "draft", "reviewed_at"),
      card=Card("Assisted review: an unframed Bottom Line draft from the evidence alone, "
                "a sensitivity check, and (given a need) a framed fit judgement with its "
                "quote shown in context", "before deciding a source",
                "Runs on the clerk channel; with no clerk configured the tasks are queued"))
def staging_review(ctx: Context, item_id: str, need: str = "",
                   disqualifiers: list[str] | None = None) -> dict:
    return staging.review(_store(ctx), item_id, clerk_endpoint(ctx), need, disqualifiers)


@tool("deep_read", tier="contribute", effect="write", scope="session", open_world=True,
      returns=("chunks", "read", "remaining", "lenses_staged"),
      card=Card("Read a staged source's whole text chunk by chunk: its claims and limits with "
                "the pages they came from, its terms, and any reasoning stance it teaches "
                "(staged as a lens)",
                "a staged document, paper or page is worth more than its opening window; "
                "before accepting it",
                "Bounded by max_chunks per call and resumable: call again to carry on. Runs on "
                "the clerk channel; with no clerk configured the tasks are queued"))
def deep_read_tool(ctx: Context, item_id: str, max_chunks: int = reading.MAX_CHUNKS,
                   lenses: bool = True) -> dict:
    kind = _store(ctx).load(item_id).get("source_kind", "")
    sections = IndexGateway(ctx).run(lambda engine: dict(engine.index.model.sections_for("source", kind)))
    return reading.deep_read(ctx.vault, item_id, clerk_endpoint(ctx), max_chunks=max_chunks,
                             lenses=lenses, sections_of=sections)


@tool("deep_read_note", tier="contribute", effect="write", scope="session", open_world=True,
      resolve={"note": "note"},
      returns=("revision", "chunks", "read", "remaining", "lenses_staged"),
      card=Card("Deep-read a source that is already accepted: its whole text, staged as a "
                "revision of its note",
                "an accepted source was only skimmed at intake, or its text is worth reading "
                "in full now",
                "Never rewrites the note: the claims and limits it finds, with pages, wait in "
                "Staging as a revision a person merges; lenses are staged as usual. Resumable"))
def deep_read_note(ctx: Context, note: str, max_chunks: int = reading.MAX_CHUNKS,
                   lenses: bool = True) -> dict:
    gateway = IndexGateway(ctx)
    row = gateway.run(lambda engine: engine.index.note_row(note))
    if row is None or row["shape"] != "source":
        raise TypeError(f"no accepted source named {note!r}; names are exact")
    loaded = notes.load(ctx.vault.root / row["path"])
    fm = loaded.frontmatter
    store = _store(ctx)
    open_revision = next((i for i in store.items(kind="source")
                          if i.get("revision_of") == row["path"]
                          and i.get("status") in ("staged", "deferred")), None)
    if open_revision is None:
        slug = re.sub(r"[^a-z0-9]+", "-", row["name"].lower()).strip("-")[:50] or "source"
        open_revision = store.add({
            "id": f"revision-{slug}-{now_iso()[:10]}", "kind": "source",
            "name": row["name"], "title": fm.get("title", row["name"]),
            "source_kind": fm.get("kind", "document"), "revision_of": row["path"],
            "canonical_url": fm.get("canonical_url", ""),
            **({"file": fm["file"]} if fm.get("file") else {}),
            "evidence": [{"id": e} for e in fm.get("evidence") or [] if isinstance(e, str)],
            "sensitivity": str(fm.get("sensitivity") or "normal"), "sections": {}})
    kind = open_revision.get("source_kind", "")
    sections = gateway.run(lambda engine: dict(engine.index.model.sections_for("source", kind)))
    out = reading.deep_read(ctx.vault, open_revision["id"], clerk_endpoint(ctx),
                            max_chunks=max_chunks, lenses=lenses, sections_of=sections)
    return {"revision": open_revision["id"], "of": row["path"], **out}


def _decision_intent(ctx: Context, kwargs: dict) -> WriteIntent | None:
    """Selected staging writes: explicit paths, checked before any approval.

    Single new-source acceptance includes managed attachment copies and views.
    All batches share a bounded guard; mixed batches replan derived text only
    within their approved file footprint.
    """
    decision = kwargs.get("decision")
    if kwargs.get("dry_run") or decision not in ("accept", "reject"):
        return None
    # The registry's existing 100-item list bound fits recovery's 200
    # fingerprints: at most one staged record and one destination per item.
    items, snapshots = [], {}
    for item_id in kwargs.get("item_ids") or []:
        try:
            item, state, observed = _snapshot(ctx, item_id)
            items.append(item)
            snapshots[item["id"]] = (state, observed)
        except TypeError:
            continue  # Preserve the domain's per-item invalid-ID result.
    if decision == "reject":
        targets, absent, observed, plans = [], [], [], {}
        store = _store(ctx)
        for item in items:
            state, stamp = snapshots[item["id"]]
            quarantine = store.quarantine_path(item["id"])
            quarantine_rel = quarantine.relative_to(ctx.vault.root).as_posix()
            targets.extend((state, quarantine_rel))
            absent.append(quarantine_rel)
            observed.append((state, stamp))
            attachments = []
            for key in ("file", "clean_file"):
                if not item.get(key):
                    continue
                path = staging._attachment_path(ctx.vault, str(item[key]))
                rel = path.relative_to(ctx.vault.root).as_posix()
                observed.append((rel, fingerprint(path)))
                attachments.append(rel)
            plans[item["id"]] = {"item_id": item["id"], "state": state,
                                  "quarantine": quarantine_rel, "attachments": attachments}
        if len(dict(observed)) + len(dict.fromkeys(absent)) > 200:
            raise TypeError("rejection exceeds the 200-file recovery bound; reject it in smaller groups")
        return WriteIntent(tuple(dict.fromkeys(targets)), absent=tuple(dict.fromkeys(absent)),
                           observed=tuple(dict(observed).items()),
                           prepared={"operation": "stage_reject", "rejections": plans})
    supported = [i for i in items if i.get("revision_of") or i.get("kind") in ("concept", "import", "lens")]
    if len(items) > 1 and any(i.get("kind") == "model_expectation" for i in items):
        raise TypeError("review and decide model expectations one at a time")
    replacements = [i for i in items if i.get("revision_of")]
    if replacements and len(items) > 1 and ctx.extras.get("caller_kind") != "person":
        raise Refusal("REVISION_REQUIRED", "accept one staged revision at a time with the revision from staging_show")
    if len(items) > 1 and (kwargs.get("revision") or kwargs.get("staged_revision")):
        raise Refusal("REVISION_REQUIRED", "a revision token applies to one staged revision; accept it separately")
    targets, absent, observed = [], [], []
    for item in items:
        state, stamp = snapshots[item["id"]]
        if len(items) == 1 and kwargs.get("staged_revision"):
            stamp = revisions.redeem(ctx, str(kwargs["staged_revision"]), state)
        observed.append((state, stamp))
    for item in supported:
        if item.get("revision_of"):
            target = str(item["revision_of"])
        elif item["kind"] == "concept":
            target = f"Concepts/{notes.safe_name(item['name'])}.md"
        elif item["kind"] == "import":
            target = str(item["target"])
        else:
            continue  # LensStore is serialized but is not a Markdown target.
        path = ctx.vault.safe_relative(target)
        target = path.relative_to(ctx.vault.root).as_posix()
        targets.append(target)
        observed.append((target, fingerprint(path)))
        if not item.get("revision_of") and not path.exists():
            absent.append(target)
    replacing = targets[0] if len(items) == 1 and replacements else ""
    prepared = None
    multiple = len(kwargs.get("item_ids") or []) > 1
    source_batch = multiple and items and all(
        i["kind"] == "source" and not i.get("revision_of") for i in items)
    if source_batch:
        if kwargs.get("fields") or kwargs.get("bottom_line") or kwargs.get("what_it_solves"):
            raise TypeError("a batch accept cannot share prose or field corrections; accept items individually")
        batch = staging.prepare_source_batch(_store(ctx), items,
            "person" if ctx.tier == "curate" else "agent", ctx.session or "",
            IndexGateway(ctx, include_vectors=False).run)
        # Initial staged snapshots include invalid/preflight-failed items too.
        initial = dict(observed)
        for path, stamp in batch["observed"]:
            if path in initial and initial[path] != stamp:
                raise Refusal("DOCUMENT_ACTIVE", "a staged source changed during batch preparation")
        batch["observed"] = list(dict([*observed, *batch["observed"]]).items())
        if len(batch["observed"]) > 200:
            raise TypeError("source batch exceeds the 200-file recovery bound; accept it in smaller groups")
        targets.extend(batch["targets"])
        observed = batch["observed"]
        prepared = {"operation": "stage_sources", "source_batch": batch}
    elif multiple and items:
        if kwargs.get("fields") or kwargs.get("bottom_line") or kwargs.get("what_it_solves"):
            raise TypeError("a batch accept cannot share prose or field corrections; accept items individually")
        batch = staging.prepare_mixed_batch(_store(ctx), items,
            "person" if ctx.tier == "curate" else "agent", ctx.session or "",
            IndexGateway(ctx, include_vectors=False).run)
        initial = dict(observed)
        if any(path in initial and initial[path] != stamp for path, stamp in batch["observed"]):
            raise Refusal("DOCUMENT_ACTIVE", "a staged item changed during mixed-batch preparation")
        batch["observed"] = list(dict([*observed, *batch["observed"]]).items())
        if len(batch["observed"]) > 200:
            raise TypeError("mixed acceptance exceeds the 200-file recovery bound; accept smaller groups")
        targets.extend(batch["targets"])
        observed = batch["observed"]
        prepared = {"operation": "stage_mixed", "mixed_batch": batch}
    elif len(items) == 1 and items[0]["kind"] == "source" and not items[0].get("revision_of"):
        item = items[0]
        origin = str((item.get("found_for") or {}).get("session") or ctx.session or "")
        try:
            source_plan = staging.prepare_source(_store(ctx), item, kwargs.get("bottom_line") or "",
                kwargs.get("what_it_solves") or "", "person" if ctx.tier == "curate" else "agent",
                origin, kwargs.get("fields") or {}, IndexGateway(ctx, include_vectors=False).run)
        except (Refusal, TypeError) as exc:
            # Preserve the existing per-item error contract without falling
            # through to an unplanned mutation after a failed preparation.
            source_plan = {"item_id": item["id"], "error": exc.detail if isinstance(exc, Refusal) else str(exc),
                           **({"refused": exc.code} if isinstance(exc, Refusal) else {})}
        if "error" not in source_plan:
            targets.extend(source_plan["targets"])
            observed.extend(source_plan["observed"])
            if source_plan.get("resuming"):
                replacing = source_plan["path"]
        prepared = {"operation": "stage_source", "source_plan": source_plan}
    if not multiple and len(items) == 1 and items[0]["kind"] == "topic":
        from .. import taxonomy
        topic_plan = taxonomy.prepare_accept(ctx.vault, None, items[0], kwargs.get("fields") or {},
                                              index_call=IndexGateway(ctx).run)
        targets.extend(topic_plan["targets"])
        observed.extend(topic_plan["observed"])
        if len(dict(observed)) > 200:
            raise TypeError("topic acceptance exceeds the 200-file recovery bound; accept without filing "
                            "its sources, then refile them in smaller batches")
        prepared = {"operation": "stage_topic", "topic_plan": topic_plan}
    return WriteIntent(tuple(dict.fromkeys(targets)), replaces=replacing,
                       absent=tuple(absent), observed=tuple(observed), prepared=prepared)


@tool("staging_decide", tier="contribute", effect="vault_write", phases=("judge", "ingest", "seed", "assess"),
      intent=_decision_intent,
      returns=("results", "accepted", "not_findable", "refused"),
      card=Card("Accept, approve, reject or defer staged items, one or a batch",
                "an item has been reviewed",
                "Accepting a source runs the six-step promotion and reports whether it is "
                "findable. Approving a source puts it in the batch a person begins from "
                "Staging (read in full, reviewed, then back for acceptance) - it does not "
                "publish it. Under promotion.mode 'person', and for anything sensitive, only "
                "a person accepts or approves. Rejections go to quarantine with their reason"))
def staging_decide(ctx: Context, item_ids: list[str],
                   decision: Literal["accept", "approve", "reject", "defer"], reason: str = "",
                   bottom_line: str = "", what_it_solves: str = "",
                   fields: dict | None = None, dry_run: bool = False, revision: str = "",
                   staged_revision: str = "") -> dict:
    store = _store(ctx)
    if dry_run:
        # an accept rehearsed: every check, what would be written, nothing changed
        if decision != "accept":
            raise TypeError("dry_run rehearses an accept")
        decided_by = "person" if ctx.tier == "curate" else "agent"
        if len(item_ids) > 1:
            items = []
            for item_id in item_ids:
                try:
                    items.append(store.load(item_id))
                except TypeError:
                    pass
            if items and all(i["kind"] == "source" and not i.get("revision_of") for i in items):
                if fields or bottom_line or what_it_solves:
                    raise TypeError("a batch accept cannot share prose or field corrections; accept items individually")
                batch = staging.prepare_source_batch(store, items, decided_by, ctx.session or "",
                    IndexGateway(ctx, include_vectors=False).run)
                results, seen = [], set()
                for item_id in item_ids:
                    plan = batch["plans"].get(item_id, {"error": "no staged item with this ID"})
                    if item_id in seen:
                        plan = {"error": "duplicate staged item ID; only the first decision can accept it"}
                    seen.add(item_id)
                    results.append({"id": item_id, "would": "accept", "ok": "error" not in plan,
                        **({"problems": [plan["error"]]} if "error" in plan else {
                            "path": plan["path"], "coverage": plan["coverage"], "copies": plan["copies"],
                            "sections": sorted(plan["draft"]["sections"]), "problems": [],
                            "not_examined": plan["draft"]["fields"].get("not_examined", []),
                            **({"file": plan["copies"][0]["destination"]} if plan["copies"] else {}),
                            "originals_retained": [c["source"] for c in plan["copies"]]})})
                return {"dry_run": True, "results": results,
                        "would_accept": sum(int(r["ok"]) for r in results)}
            if items:
                if fields or bottom_line or what_it_solves:
                    raise TypeError("a batch accept cannot share prose or field corrections; accept items individually")
                batch = staging.prepare_mixed_batch(store, items, decided_by, ctx.session or "",
                    IndexGateway(ctx, include_vectors=False).run)
                results, seen = [], set()
                for item_id in item_ids:
                    plan = batch["plans"].get(item_id, {"error": "no staged item with this ID"})
                    if item_id in seen:
                        plan = {"error": "duplicate staged item ID"}
                    seen.add(item_id)
                    result = {"id": item_id, "ok": "error" not in plan, "would": "accept",
                              "problems": [plan["error"]] if "error" in plan else []}
                    if not plan.get("error"):
                        result.update(targets=plan.get("targets", []), path=plan.get("path", ""))
                        if plan.get("operation") == "new_source":
                            result.update(coverage=plan["coverage"], copies=plan["copies"],
                                sections=sorted(plan["draft"]["sections"]),
                                not_examined=plan["draft"]["fields"].get("not_examined", []),
                                originals_retained=[c["source"] for c in plan["copies"]])
                            if plan["copies"]:
                                result["file"] = plan["copies"][0]["destination"]
                        elif plan.get("operation") == "revision":
                            item = next(i for i in items if i["id"] == item_id)
                            result.update(would="merge", sections=[heading for heading in staging.REVISED_SECTIONS
                                if (item.get("sections") or {}).get(heading)])
                    results.append(result)
                return {"dry_run": True, "ordered_replanning": True, "targets": batch["targets"],
                        "results": results, "would_accept": sum(int(r["ok"]) for r in results)}
        if len(item_ids) == 1:
            item = store.load(item_ids[0])
            if item["kind"] == "source" and not item.get("revision_of"):
                try:
                    plan = staging.prepare_source(store, item, bottom_line, what_it_solves, decided_by,
                        str((item.get("found_for") or {}).get("session") or ctx.session or ""),
                        fields or {}, IndexGateway(ctx, include_vectors=False).run)
                    result = {"id": item["id"], "ok": True, "would": "accept", "path": plan["path"],
                        "coverage": plan["coverage"], "copies": plan["copies"],
                        "sections": sorted(plan["draft"]["sections"]),
                        "not_examined": plan["draft"]["fields"].get("not_examined", []),
                        "originals_retained": [c["source"] for c in plan["copies"]], "problems": [],
                        **({"file": plan["copies"][0]["destination"]} if plan["copies"] else {})}
                except (Refusal, TypeError) as exc:
                    result = {"id": item["id"], "ok": False, "would": "accept", "problems": [str(exc)]}
                return {"dry_run": True, "results": [result], "would_accept": int(result["ok"])}
        results = with_engine(ctx, lambda engine: [staging.preview(store, engine, i, decided_by, bottom_line,
                                   what_it_solves, fields) for i in item_ids])
        return {"dry_run": True, "results": results,
                "would_accept": sum(1 for r in results if r.get("ok"))}
    before = {}
    for item_id in item_ids:
        try:
            before[item_id] = store.load(item_id)
        except TypeError:
            pass
    expectation_items = [item for item in before.values()
                         if item.get("kind") == "model_expectation"]
    prepared = ctx.extras.get("_prepared_write") or {}
    if expectation_items:
        if len(before) != 1 or len(item_ids) != 1:
            raise TypeError("review and decide model expectations one at a time")
        if not staged_revision:
            raise TypeError("read staging_show and provide its staged_revision")
        if ctx.extras.get("caller_kind") != "person":
            raise TypeError("only a person can decide a model expectation")
        _item, state, observed = _snapshot(ctx, item_ids[0])
        if revisions.redeem(ctx, staged_revision, state) != observed:
            raise TypeError("the staged expectation changed; review it again")
        from .. import model_expectation_authoring
        from ..model_invocation import ExpectationRegistry
        quarantine_target = None
        if decision == "reject":
            plan = prepared.get("rejections", {}).get(item_ids[0]) \
                if prepared.get("operation") == "stage_reject" else None
            if plan is None or plan.get("item_id") != item_ids[0]:
                raise TypeError("a model-expectation rejection requires its prepared quarantine plan")
            from ..coordination import operation_path
            quarantine_target = operation_path(ctx.vault, plan["quarantine"])
        result = model_expectation_authoring.decide(
            store, item_ids[0], decision, reason, decided_by="person",
            quarantine_target=quarantine_target)
        runtime = ctx.extras.get("invocation_runtime")
        if runtime is not None and decision == "accept":
            runtime.expectations = ExpectationRegistry.active()
        return {"results": [result], "accepted": int(result.get("status") == "accepted"),
                "not_findable": [], "refused": 0}
    origins = {str((item.get("found_for") or {}).get("session") or "")
               for item in before.values() if (item.get("found_for") or {}).get("session")}
    promotion_session = next(iter(origins)) if len(origins) == 1 else (ctx.session or "")
    results = staging.decide(store, None, item_ids, decision, reason,
                             bottom_line, what_it_solves,
                             decided_by="person" if ctx.tier == "curate" else "agent",
                             session=promotion_session, fields=fields,
                             index_call=IndexGateway(ctx,
                                 include_vectors=prepared.get("operation") not in ("stage_source", "stage_sources", "stage_mixed")).run,
                             topic_plan=prepared.get("topic_plan") if prepared.get("operation") == "stage_topic" else None,
                             source_plan=prepared.get("source_plan") if prepared.get("operation") == "stage_source" else None,
                             source_batch=prepared.get("source_batch") if prepared.get("operation") == "stage_sources" else None,
                             mixed_batch=prepared.get("mixed_batch") if prepared.get("operation") == "stage_mixed" else None,
                             rejection_plan=prepared.get("rejections") if prepared.get("operation") == "stage_reject" else None,
                             document_leases=ctx.extras.get("document_leases"))
    for result in results:
        if result.get("status") not in ("accepted", "approved", "rejected", "deferred"):
            continue
        item_id = str(result.get("id") or "")
        item = before.get(item_id, {})
        session_id = str((item.get("found_for") or {}).get("session") or ctx.session or "")
        if not session_id or not item:
            continue
        path = ""
        if result["status"] == "accepted":
            try:
                path = store.load(item_id).get("accepted_to", "")
            except TypeError:
                pass
        brief = (item.get("found_for") or {}).get("brief", "")
        try:
            session_store = SessionStore(ctx.vault)
            # Do not create a library-item-only log when its original session
            # has disappeared. Promotion is already durable; report the missing
            # handoff without losing the acceptance result or inventing a thread.
            session_store.load(session_id)
            session_store.append(session_id, {"type": "library_item", "id": item_id,
                "source": item["name"], "status": result["status"], "path": path,
                "brief": brief})
            # Deeper Audit DA-3: accepting a source into the library is not deciding it
            # answers this session's need. It joins the session as an undecided candidate
            # under its catalogued name - never kept automatically - with the exact next
            # step, so "accepted, but nothing was kept" is no longer a dead end.
            if path:
                note = PurePosixPath(path).stem
                session = session_store.load(session_id)
                if session.status != "closed" and not {note, item["name"]} & set(
                        session.candidates):
                    session_store.append(session_id, {"type": "candidate", "source": note,
                                                      "brief": brief, "via": "accepted"})
                result["handoff"] = {"note": note, "path": path, "candidate": "undecided",
                                     "next": f"in judge: decide(source={note!r}, "
                                             f"disposition=keep|reject, role=...)"}
            result["session"] = session_store.load(session_id).envelope(ctx.vault)
        except (Refusal, TypeError, OSError) as exc:
            result["handoff_warning"] = {"status": "not_recorded",
                "error": exc.code if isinstance(exc, Refusal) else type(exc).__name__,
                "next": "The library decision remains durable; inspect the original session before recording its handoff."}
    return {"results": results,
            "accepted": sum(1 for r in results if r.get("status") == "accepted"),
            "not_findable": [r["id"] for r in results if r.get("promotion")
                             and not r["promotion"]["catalogued"]],
            "refused": sum(1 for r in results if "refused" in r or "error" in r)}


@tool("staging_flag", tier="contribute", effect="write", scope="session",
      returns=("id", "sensitivity"),
      card=Card("Mark a staged item sensitive (or clear the mark, as a person)",
                "an item is dual-use: offensive security, surveillance"))
def staging_flag(ctx: Context, item_id: str, sensitive: bool = True, reason: str = "") -> dict:
    store = _store(ctx)
    item = store.load(item_id)
    if not sensitive and ctx.tier != "curate":
        raise TypeError("only a person clears a sensitivity mark")
    item["sensitivity"] = "review" if sensitive else "normal"
    item.setdefault("history", []).append({"flag": item["sensitivity"], "reason": reason,
                                           "by": ctx.tier})
    store.save(item)
    return {"id": item_id, "sensitivity": item["sensitivity"]}


@tool("lens_list", tier="consult", effect="read",
      card=Card("Accepted lenses: reasoning stances drawn from sources",
                "you want a way of looking at a problem that a source teaches"))
def lens_list(ctx: Context, query: str = "", limit: int = 25) -> dict:
    store = LensStore(ctx.vault)
    return {"total": store.count(), "lenses": store.list(query, limit),
            "concentration": store.concentration()}


@tool("lens_show", tier="consult", effect="read",
      card=Card("One accepted lens in full, with the passage it was drawn from",
                "adopting a lens"))
def lens_show(ctx: Context, lens_id: str) -> dict:
    lens = LensStore(ctx.vault).get(lens_id)
    return lens or {"found": False, "lens_id": lens_id}


@tool("concept_candidates", tier="contribute", effect="write", scope="session",
      returns=("scanned", "staged"),
      card=Card("Scan recorded term usages and stage a concept candidate for each term "
                "seen across several sources",
                "building the glossary; re-running never restages a decided term",
                "Nothing is drafted from thin air: only the term's own quoted usages are "
                "staged. A person's own words become the Definition on accept"))
def concept_candidates(ctx: Context, min_sources: int = concepts.MIN_SOURCES) -> dict:
    return concepts.candidates(ctx.vault, min_sources)


# -- the clerk agent route -----------------------------------------------------

@tool("clerk_next", tier="contribute", effect="read", sessionless=True,
      returns=("waiting",),
      card=Card("The next waiting clerk task: one question, one text, one answer shape",
                "you are the clerk agent, and only then",
                "Never call this from a research conversation: a clerk answer must not "
                "see the thread's framing. It runs outside any session"))
def clerk_next(ctx: Context) -> dict:
    task = clerk.next_task(ctx.vault.work("queue") / "clerk")
    return task or {"waiting": 0}


@tool("clerk_submit", tier="contribute", effect="write", sessionless=True,
      returns=("accepted",),
      card=Card("Submit the clerk agent's answer to one waiting task",
                "you are the clerk agent and have answered the task from its text alone",
                "The answer is checked for shape now, and for grounding when the owning "
                "review next runs"))
def clerk_submit(ctx: Context, key: str, answer: dict) -> dict:
    return clerk.submit(ctx.vault.work("queue") / "clerk", key, answer, by="clerk-agent")
