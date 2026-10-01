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

import re
from typing import Any

from . import clerk, notes
from .promote import UNFILED, write_master_index, write_topic_index
from .rules import Refusal
from .search import Engine
from .staging import StagingStore
from .vault import Vault, now_iso

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


def propose(vault: Vault, engine: Engine, endpoint: clerk.Endpoint | None,
            only_unfiled: bool = True) -> dict[str, Any]:
    pool = sources(engine, only_unfiled)[:MAX_SOURCES]
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
        if prior is not None and prior["status"] not in ("staged", "deferred"):
            continue                               # decided: never restaged
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


def add_topic(vault: Vault, name: str, what_belongs: str, aliases: list[str]) -> str:
    """Append one row to About/Topics.md's table."""
    name = " ".join(name.split())
    if not name or "|" in name or name.casefold() == UNFILED.casefold():
        raise TypeError(f"{name!r} cannot be a topic name")
    if any(_key(name) == _key(t) for t in vault.topics()):
        raise TypeError(f"{name!r} is already a topic (or too close to one): "
                        f"{[t for t in vault.topics() if _key(t) == _key(name)]}")
    path = vault.root / "About" / "Topics.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else (
        "# Topics\n\n| Topic | What belongs here |\n| --- | --- |\n"
        f"| {UNFILED} | sources waiting for a topic |\n")
    also = f" (also: {', '.join(aliases)})" if aliases else ""
    row = f"| {name} | {' '.join(what_belongs.split()).replace('|', '/')}{also} |"
    lines = text.rstrip("\n").split("\n")
    last = max((i for i, line in enumerate(lines) if line.strip().startswith("|")),
               default=len(lines) - 1)
    lines.insert(last + 1, row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return name


def accept(vault: Vault, engine: Engine, item: dict[str, Any], decided_by: str,
           edits: dict[str, Any]) -> dict[str, Any]:
    if decided_by != "person":
        raise Refusal("PERSON_CONFIRMS", "a topic changes this vault's taxonomy: a person "
                                         "accepts it")
    name = add_topic(vault, str(edits.get("name") or item["name"]),
                     str(edits.get("what_belongs") or item.get("what_belongs", "")),
                     list(edits.get("aliases") or item.get("aliases") or []))
    filed = refile(vault, engine, item.get("members", []), name) \
        if edits.get("refile", True) else []
    return {"topic": name, "refiled": filed}


def refile(vault: Vault, engine: Engine, names: list[str], topic: str) -> list[dict[str, Any]]:
    if topic not in vault.topics():
        raise TypeError(f"{topic!r} is not an accepted topic: {vault.topics()}")
    out, touched = [], {topic}
    for name in names:
        row = engine.index.note_row(name)
        if row is None or row["shape"] != "source":
            out.append({"source": name, "error": "not a catalogued source"})
            continue
        path = vault.root / row["path"]
        note = notes.load(path)
        before = str(note.frontmatter.get("primary_topic") or UNFILED)
        if before == topic:
            out.append({"source": name, "topic": topic, "unchanged": True})
            continue
        fm = dict(note.frontmatter, primary_topic=topic)
        path.write_text(notes.render(fm, note.body), encoding="utf-8")
        engine.index.upsert(path)
        touched.add(before)
        out.append({"source": name, "from": before, "topic": topic})
    for t in touched:
        write_topic_index(engine.index, t)
    write_master_index(engine.index)
    return out


def refresh_views(vault: Vault, engine: Engine) -> dict[str, Any]:
    """Rewrite every topic index and the Master Index from the notes as they are."""
    filed = {s["topic"] for s in sources(engine)}
    written = [write_topic_index(engine.index, t).relative_to(vault.root).as_posix()
               for t in sorted(filed | set(vault.topics()))]
    master = write_master_index(engine.index).relative_to(vault.root).as_posix()
    return {"written": written + [master],
            "not_accepted": sorted(filed - set(vault.topics()))}
