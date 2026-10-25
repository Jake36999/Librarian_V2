"""Topics from what the library holds (Requirements Addendum R8; Research Pipeline §3.4).

The topic list in `About/Topics.md` is closed: a source is filed under an accepted topic
or under Unfiled, and nothing grows the list on its own. This is how it grows:

1. `propose` - the clerk reads the library's own sources (name and Bottom Line, no project
   or need) and groups them. Every member it names is checked against the real source
   names; a topic with fewer than two real members is dropped. A new topic is staged as a
   `topic` item with its examples, coverage and alias suggestions, and a possible duplicate
   of an accepted topic is marked. Sources it files under an already accepted topic come
   back as refile suggestions. Re-running refreshes what is staged and never restages a
   decided topic.
2. A person accepts (or renames, or rejects) a staged topic. Accepting writes its row into
   `About/Topics.md` and, by default, files its members under it.
3. `refile` moves a source to an accepted topic; `refresh_views` rewrites the generated
   topic indexes and the Master Index from the notes. Both only ever use accepted topics.
"""
from __future__ import annotations

import json
import re
from typing import Any, Callable

from . import clerk, notes
from .coordination import (MISSING, PreconditionChangedError, atomic_write_text,
                           fingerprint, fingerprint_bytes)
from .promote import UNFILED, master_index_text, topic_index_path, topic_index_text
from .rules import Refusal
from .search import Engine
from .staging import StagingStore
from .vault import Vault, now_iso, topics_in

MAX_SOURCES = 200
LINE_CHARS = 160


def _key(name: str) -> str:
    """Compare topic names loosely: case, punctuation and a plural 's' aside."""
    k = re.sub(r"[^a-z0-9]+", " ", name.casefold()).strip()
    return " ".join(w[:-1] if len(w) > 3 and w.endswith("s") else w for w in k.split())


def sources(engine: Engine, only_unfiled: bool = False) -> list[dict[str, Any]]:
    rows = engine.index.conn.execute(
        "SELECT name, path FROM note WHERE shape = 'source' ORDER BY name").fetchall()
    out = []
    for row in rows:
        note = notes.load(engine.index.vault.root / row["path"])
        topic = str(note.frontmatter.get("primary_topic") or UNFILED)
        if only_unfiled and topic != UNFILED:
            continue
        line = " ".join((note.sections().get("Bottom Line") or "").split())[:LINE_CHARS]
        out.append({"name": row["name"], "path": row["path"], "topic": topic,
                    "kind": str(note.frontmatter.get("kind") or ""), "line": line})
    return out


def propose(vault: Vault, engine: Engine | None, endpoint: clerk.Endpoint | None,
            only_unfiled: bool = True, *,
            index_call: Callable[[Callable[[Engine], Any]], Any] | None = None) -> dict[str, Any]:
    """Stage taxonomy proposals without holding the SQLite worker for Clerk I/O."""
    if index_call is not None:
        pool = index_call(lambda active: sources(active, only_unfiled))[:MAX_SOURCES]
    elif engine is not None:
        pool = sources(engine, only_unfiled)[:MAX_SOURCES]
    else:
        raise TypeError("propose needs an Engine or callback-only index access")
    accepted = [t for t in vault.topics() if t != UNFILED]
    if len(pool) < 2:
        return {"proposed": [], "refile": [], "considered": len(pool),
                "detail": "fewer than two sources to group"}
    corpus = "\n".join(f"{s['name']} ({s['kind']}): {s['line'] or 'no Bottom Line'}"
                       for s in pool)
    result = clerk.run([clerk.topics(corpus, accepted)], endpoint,
                       vault.work("queue") / "clerk")[0]
    if not result.ok:
        return {"proposed": [], "refile": [], "considered": len(pool),
                "detail": f"the clerk did not answer ({result.status}); nothing proposed"}
    names = {s["name"].casefold(): s for s in pool}
    by_key = {_key(t): t for t in accepted}
    store = StagingStore(vault)
    proposed, refile, dropped = [], [], 0
    for topic in result.value.get("topics", []):
        members = []
        for m in topic.get("members", []):
            hit = names.get(str(m).strip().casefold())
            if hit is None:
                dropped += 1                       # not a source the library holds
            elif hit["name"] not in members:
                members.append(hit["name"])
        name = " ".join(str(topic.get("name", "")).split())
        existing = by_key.get(_key(name))
        if existing:
            refile += [{"source": m, "topic": existing} for m in members
                       if names[m.casefold()]["topic"] != existing]
            continue
        if len(members) < 2 or not name or name.casefold() == UNFILED.casefold():
            continue
        item_id = f"topic-{re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')[:50]}"
        try:
            prior = store.load(item_id)
        except TypeError:
            prior = None
        if prior is not None and (prior["status"] not in ("staged", "deferred") or prior.get("acceptance_progress")):
            continue                               # decided/partly applied: never replace the person's work
        aliases = [a for a in dict.fromkeys(" ".join(str(a).split())
                                            for a in topic.get("aliases", [])) if a]
        near = next((t for t in accepted for a in [name, *aliases] if _key(a) == _key(t)), "")
        item = {**(prior or {}), "id": item_id, "kind": "topic", "name": name,
                "what_belongs": " ".join(str(topic.get("what_belongs", "")).split()),
                "members": members, "aliases": aliases,
                "coverage": {"sources": len(members), "of": len(pool)},
                "proposed_by": result.model or "clerk", "proposed_at": now_iso(),
                **({"duplicate_of": near} if near else {})}
        if prior is None:
            store.add(item)
        else:
            store.save(item)
        proposed.append({"id": item_id, "name": name, "sources": len(members)})
    return {"proposed": proposed, "refile": refile, "considered": len(pool),
            "dropped_members": dropped}


def _topic_addition(text: str, name: str, what_belongs: str, aliases: list[str]) -> tuple[str, str, str]:
    """Plan a table addition from the same text whose fingerprint is captured."""
    name = " ".join(name.split())
    if not name or "|" in name or name.casefold() == UNFILED.casefold():
        raise TypeError(f"{name!r} cannot be a topic name")
    accepted = topics_in(text)
    if any(_key(name) == _key(t) for t in accepted):
        raise TypeError(f"{name!r} is already a topic (or too close to one): "
                        f"{[t for t in accepted if _key(t) == _key(name)]}")
    text = text or (
        "# Topics\n\n| Topic | What belongs here |\n| --- | --- |\n"
        f"| {UNFILED} | sources waiting for a topic |\n")
    aliases = _aliases(aliases)
    also = f" (also: {', '.join(aliases)})" if aliases else ""
    row = f"| {name} | {' '.join(what_belongs.split()).replace('|', '/')}{also} |"
    lines = text.rstrip("\n").split("\n")
    last = max((i for i, line in enumerate(lines) if line.strip().startswith("|")),
               default=len(lines) - 1)
    lines.insert(last + 1, row)
    return name, "\n".join(lines) + "\n", row


def add_topic(vault: Vault, name: str, what_belongs: str, aliases: list[str]) -> str:
    """Explicit offline compatibility helper; Core acceptance uses a plan."""
    rel, _, text = _snapshot(vault, "About/Topics.md")
    name, rendered, _ = _topic_addition(text, name, what_belongs, aliases)
    atomic_write_text(vault.safe_relative(rel), rendered)
    return name


def accept(vault: Vault, engine: Engine | None, item: dict[str, Any], decided_by: str,
           edits: dict[str, Any], *, index_call: Callable | None = None,
           prepared: dict | None = None, leases=None) -> dict[str, Any]:
    if decided_by != "person":
        raise Refusal("PERSON_CONFIRMS", "a topic changes this vault's taxonomy: a person "
                                         "accepts it")
    plan = prepared if prepared is not None else prepare_accept(vault, engine, item, edits, index_call=index_call)
    if (plan.get("operation") != "topic" or plan.get("item_id") != item["id"]
            or plan.get("request") != _topic_request(item, edits)):
        raise TypeError("topic acceptance requires its own prepared write plan")
    return _apply_plan(vault, engine, plan, index_call, leases)[1]


def _index_run(engine: Engine | None, index_call: Callable | None, operation: Callable):
    if index_call is not None:
        return index_call(operation)
    if engine is None:
        raise TypeError("taxonomy requires an Engine or callback-only index access")
    return operation(engine)


def _snapshot(vault: Vault, rel: str) -> tuple[str, str, str]:
    path = vault.safe_relative(rel)
    canonical = path.relative_to(vault.root).as_posix()
    if not path.exists():
        return canonical, MISSING, ""
    raw = path.read_bytes()
    return canonical, fingerprint_bytes(raw), raw.decode("utf-8")


def _view_paths(vault: Vault, topics: list[str]) -> list[str]:
    paths = [topic_index_path(vault, topic).relative_to(vault.root).as_posix() for topic in topics]
    # Filename normalisation is not an identity rule for taxonomy names.
    if len({path.casefold() for path in paths}) != len(paths):
        raise TypeError("topic names collide as index filenames; rename the conflicting topics before refreshing")
    return [*paths, "Indexes/Master Index.md"]


def _finish_plan(vault: Vault, operation: str, topics: list[str], observed: dict[str, str],
                 writes: list[dict], result: Any, taxonomy_path: str, render_views: bool = True) -> dict:
    view_paths = _view_paths(vault, topics) if render_views else []
    targets = [*[write["path"] for write in writes], *view_paths]
    for path in view_paths:
        canonical, stamp, _ = _snapshot(vault, path)
        if canonical != path:
            raise TypeError("generated index paths must not redirect through symlinks")
        observed[path] = stamp
    if len(observed) > 200 or len(targets) > 200:
        raise TypeError("this taxonomy operation exceeds the 200-file recovery bound; split the refiling batch "
                        "or accept the topic without filing its sources first")
    return {"operation": operation, "topics": topics, "targets": targets,
            "observed": list(observed.items()), "writes": writes, "result": result,
            "taxonomy_path": taxonomy_path, "render_views": render_views}


def prepare_refile(vault: Vault, engine: Engine | None, names: list[str], topic: str, *,
                   index_call: Callable | None = None, taxonomy_update: dict | None = None) -> dict:
    """Read-only preparation before approval: exact note bytes, not a second engine."""
    if taxonomy_update is None:
        about, stamp, text = _snapshot(vault, "About/Topics.md")
    else:
        about, stamp, text = taxonomy_update["path"], taxonomy_update["before"], taxonomy_update["text"]
    accepted = topics_in(text)
    if topic not in accepted:
        raise TypeError(f"{topic!r} is not an accepted topic: {accepted}")
    def read(active):
        return [dict(row) if (row := active.index.note_row(name)) is not None else None
                for name in names]
    rows = _index_run(engine, index_call, read)
    out, touched, writes, observed = [], {topic}, [], {about: stamp}
    planned = set()
    for name, row in zip(names, rows):
        if row is None or row["shape"] != "source":
            out.append({"source": name, "error": "not a catalogued source"})
            continue
        path, stamp, text = _snapshot(vault, row["path"])
        fm, body, error = notes.parse(text)
        if error or fm.get("type") != "source":
            raise TypeError(f"{path} is no longer a valid source note (invalid frontmatter or type changed)")
        observed[path] = stamp
        before = str(fm.get("primary_topic") or UNFILED)
        if before == topic or path in planned:
            out.append({"source": name, "topic": topic, "unchanged": True})
            continue
        writes.append({"path": path, "text": notes.render(dict(fm, primary_topic=topic), body)})
        planned.add(path)
        touched.add(before)
        out.append({"source": name, "from": before, "topic": topic})
    plan = _finish_plan(vault, "refile", sorted(touched), observed, writes, out, about)
    plan["request"] = {"names": list(names), "topic": topic}
    return plan


def _aliases(values: list[str]) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise TypeError("topic aliases must be a list of strings")
    return [" ".join(value.split()).replace("|", "/") for value in values]


def _topic_request(item: dict, edits: dict) -> dict:
    return {"name": " ".join(str(edits.get("name") or item["name"]).split()),
            "what_belongs": " ".join(str(edits.get("what_belongs") or item.get("what_belongs", "")).split()),
            "aliases": _aliases(edits.get("aliases") or item.get("aliases") or []),
            "refile": bool(edits.get("refile", True))}


def prepare_accept(vault: Vault, engine: Engine | None, item: dict, edits: dict, *,
                   index_call: Callable | None = None) -> dict:
    about, stamp, text = _snapshot(vault, "About/Topics.md")
    request = _topic_request(item, edits)
    progress = item.get("acceptance_progress") or {}
    if progress:
        name, row = str(progress.get("topic") or ""), str(progress.get("row") or "")
        if (progress.get("version") != 1 or progress.get("request") != request
                or not row or text.splitlines().count(row) != 1
                or sum(_key(topic) == _key(name) for topic in topics_in(text)) != 1):
            raise Refusal("DOCUMENT_ACTIVE", "partial topic acceptance or its approved taxonomy row changed; "
                          "review the recorded changes before continuing")
        rendered = text  # Do not append the already-committed row a second time.
    else:
        name, rendered, row = _topic_addition(text, request["name"], request["what_belongs"], request["aliases"])
    update = {"path": about, "text": rendered, "before": stamp}
    if request["refile"]:
        plan = prepare_refile(vault, engine, item.get("members", []), name,
                              index_call=index_call, taxonomy_update=update)
        if not progress:
            plan["writes"].insert(0, {"path": about, "text": rendered})
            plan["targets"].insert(0, about)
        plan["result"] = {"topic": name, "refiled": plan["result"]}
    else:
        plan = _finish_plan(vault, "topic", [], {about: stamp}, [] if progress else [{"path": about, "text": rendered}],
                            {"topic": name, "refiled": []}, about, render_views=False)
    plan.update(operation="topic", item_id=item["id"], request=request, topic_row=row)
    return plan


def _filed_topics(active: Engine) -> list[str]:
    return [str(json.loads(row["frontmatter"]).get("primary_topic") or UNFILED)
            for row in active.conn.execute("SELECT frontmatter FROM note WHERE shape = 'source'")]


def prepare_views(vault: Vault, engine: Engine | None, *, index_call: Callable | None = None) -> dict:
    about, stamp, text = _snapshot(vault, "About/Topics.md")
    accepted = set(topics_in(text))
    filed = set(_index_run(engine, index_call, _filed_topics))
    return _finish_plan(vault, "views", sorted(filed | accepted), {about: stamp}, [],
                        {"not_accepted": sorted(filed - accepted)}, about)


class TaxonomyInterruptedError(RuntimeError):
    def __init__(self, cause: Exception, completed: list[str]):
        self.completed_paths = list(completed)
        super().__init__(f"{cause}; completed Markdown writes: {completed}; review before retrying")


class _WriteGuard:
    """Per-write checks complement admission CAS; no OS lock or rollback claim."""
    def __init__(self, vault: Vault, plan: dict, leases=None):
        self.vault, self.leases = vault, leases
        self.expected, self.targets = dict(plan["observed"]), set(plan["targets"])
        self.taxonomy_path = plan["taxonomy_path"]
        self.completed: list[str] = []
        for path, wanted in self.expected.items():
            if fingerprint(vault.safe_relative(path)) != wanted:
                raise PreconditionChangedError(path)
        if leases is not None:
            leases.assert_writable(plan["targets"])

    def write(self, rel: str, text: str) -> None:
        path = self.vault.safe_relative(rel)
        if path.relative_to(self.vault.root).as_posix() != rel or rel not in self.targets:
            raise Refusal("DOCUMENT_ACTIVE", "the taxonomy write plan changed; review and run it again")
        # Taxonomy edits made mid-round invalidate even a later generated view.
        for dependency in dict.fromkeys([self.taxonomy_path, rel]):
            if fingerprint(self.vault.safe_relative(dependency)) != self.expected[dependency]:
                raise PreconditionChangedError(dependency)
        if self.leases is not None:
            self.leases.assert_writable([rel])
        atomic_write_text(path, text)
        self.expected[rel] = fingerprint_bytes(text.encode("utf-8"))
        self.completed.append(rel)
        if self.leases is not None:
            self.leases.note_core_write([rel])


def _apply_plan(vault: Vault, engine: Engine | None, plan: dict, index_call: Callable | None,
                leases=None) -> tuple[list[str], Any]:
    _index_run(engine, index_call, lambda active: None)  # Admission before any file write.
    guard = _WriteGuard(vault, plan, leases)
    try:
        for write in plan["writes"]:
            guard.write(write["path"], write["text"])
            _index_run(engine, index_call, lambda active: active.index.upsert(vault.safe_relative(write["path"])))
        # Render only on the SQLite owner, then write and upsert separately.
        rendered = _index_run(engine, index_call, lambda active: [
            {"path": topic_index_path(vault, topic).relative_to(vault.root).as_posix(),
             "text": topic_index_text(active.index, topic)} for topic in plan["topics"]] + [
            {"path": "Indexes/Master Index.md", "text": master_index_text(active.index)}]) if plan["render_views"] else []
        for write in rendered:
            guard.write(write["path"], write["text"])
            _index_run(engine, index_call, lambda active: active.index.upsert(vault.safe_relative(write["path"])))
    except Refusal as exc:
        exc.extra.update(completed_paths=list(guard.completed),
                         next_action="Review the conflict and completed paths; rerun refiling/views after review.")
        if guard.completed:
            exc.detail = f"Earlier writes remain at {guard.completed}; review them before retrying. {exc.detail}"
            exc.args = (f"{exc.code}: {exc.detail}",)
        raise
    except Exception as exc:
        raise TaxonomyInterruptedError(exc, guard.completed) from exc
    return [write["path"] for write in rendered], plan["result"]


def refile(vault: Vault, engine: Engine | None, names: list[str], topic: str, *,
           index_call: Callable | None = None, prepared: dict | None = None, leases=None) -> list[dict[str, Any]]:
    plan = prepared if prepared is not None else prepare_refile(vault, engine, names, topic, index_call=index_call)
    if plan.get("operation") != "refile" or plan.get("request") != {"names": list(names), "topic": topic}:
        raise TypeError("refiling requires its own prepared write plan")
    return _apply_plan(vault, engine, plan, index_call, leases)[1]


def refresh_views(vault: Vault, engine: Engine | None, *, index_call: Callable | None = None,
                  prepared: dict | None = None, leases=None) -> dict[str, Any]:
    """Rewrite every topic index and the Master Index from the notes as they are."""
    plan = prepared if prepared is not None else prepare_views(vault, engine, index_call=index_call)
    if plan.get("operation") != "views":
        raise TypeError("view refresh requires its own prepared write plan")
    if prepared is not None:
        current = sorted(set(_index_run(engine, index_call, _filed_topics)) | set(vault.topics()))
        if current != plan["topics"]:
            raise Refusal("DOCUMENT_ACTIVE", "source topics changed while approval waited; review and refresh again")
    written, result = _apply_plan(vault, engine, plan, index_call, leases)
    return {"written": written, **result}
