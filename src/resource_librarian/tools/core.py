"""The tools every surface has from the start: status, capabilities, rules and
a note by name. Search, sessions and intake register their own tools in their
own modules."""
from __future__ import annotations

from .. import doctor, notes, rules, schema
from ..registry import REGISTRY, Card, Context, tool


@tool("capabilities", tier="consult", effect="read", needs_vault=False,
      card=Card("Every tool this caller may use, as short cards",
                "you are deciding what to do next"))
def capabilities(ctx: Context) -> dict:
    """Cards only; the exact parameters come from the surface's own schema."""
    return {"tier": ctx.tier, "tools": [
        {"name": t.name, "purpose": t.card.purpose, "use_when": t.card.use_when,
         "effect": t.effect, "open_world": t.open_world,
         **({"scope": t.scope} if t.scope else {}),
         **({"phases": sorted(t.phases)} if t.phases else {})}
        for t in sorted(REGISTRY.for_tier(ctx.tier), key=lambda t: t.name)]}


@tool("doctor", tier="consult", effect="read", needs_vault=False,
      card=Card("What this install can and cannot do right now",
                "before relying on an optional capability"))
def doctor_tool(ctx: Context) -> dict:
    """Keys are reported present or absent, never shown."""
    results = doctor.checks(ctx.vault, ctx.extras.get("mcp"))
    return {"ok": all(c.ok for c in results if c.required),
            "checks": [c.to_dict() for c in results]}


@tool("rules", tier="consult", effect="read", needs_vault=False,
      card=Card("The rules this system enforces, with their codes",
                "a refusal named a rule you want to understand"))
def rules_tool(ctx: Context, code: str = "") -> dict:
    """One rule by code, or all of them."""
    if code:
        rule = rules.RULES.get(code)
        return {"code": code, "found": bool(rule),
                "statement": rule.statement if rule else ""}
    return {"rules": [{"code": r.code, "group": r.group, "statement": r.statement}
                      for r in rules.RULES.values()]}


@tool("vault_status", tier="consult", effect="read",
      card=Card("What this vault holds, by shape and source kind",
                "you do not yet know what the library covers"))
def vault_status(ctx: Context) -> dict:
    """Counts from the notes themselves, not from a derived index."""
    model = schema.load(ctx.vault.root)
    counts: dict[str, int] = {}
    kinds: dict[str, int] = {}
    unparsed = 0
    for path in notes.iter_paths(ctx.vault.root):
        note = notes.load(path)
        if note.parse_error:
            unparsed += 1
            continue
        shape = model.shape_of(note, ctx.vault.root) or "other"
        counts[shape] = counts.get(shape, 0) + 1
        if shape == "source":
            kind = str(note.frontmatter.get("kind") or "unknown")
            kinds[kind] = kinds.get(kind, 0) + 1
    return {"vault": str(ctx.vault.root), "notes": counts, "source_kinds": kinds,
            "unparsed": unparsed, "content_model": "found" if model.found else "missing"}


@tool("check_notes", tier="consult", effect="read",
      card=Card("Check every note against the vault's content model",
                "after writing or editing notes"))
def check_notes(ctx: Context, limit: int = 50) -> dict:
    """Violations first, with the note and the rule each breaks."""
    model = schema.load(ctx.vault.root)
    if model.error:
        return {"ok": False, "error": f"the content model will not parse: {model.error}"}
    violations = []
    names: dict[str, str] = {}
    links: dict[str, list[str]] = {}
    for path in notes.iter_paths(ctx.vault.root):
        note = notes.load(path)
        rel = path.relative_to(ctx.vault.root).as_posix()
        if note.name in names:
            violations.append({"check": "unique_note_names", "note": note.name,
                               "detail": f"also at {names[note.name]}", "severity": "error"})
        names[note.name] = rel
        violations += [v.__dict__ for v in model.check(note, ctx.vault.root)]
        links[note.name] = [t.replace("\\", "/").rsplit("/", 1)[-1].removesuffix(".md")
                            for t in notes.wikilinks(note.body)]
    # V1's integrity checks, carried over (2026-09-30): a link that names no note, and a
    # Source or Concept nothing links to (a stale index, or a note filed out of reach).
    known = {n.casefold() for n in names}
    files = {p.name.casefold() for p in ctx.vault.root.rglob("*") if p.is_file()}
    inbound: set[str] = set()
    for name, targets in links.items():
        for target in targets:
            if not target:
                continue
            key = target.casefold()
            inbound.add(key)
            if key not in known and key not in files:
                violations.append({"check": "wikilinks_resolve", "note": name,
                                   "detail": f"[[{target}]] names no note", "severity": "warn"})
    for name, rel in names.items():
        if rel.split("/", 1)[0] in ("Sources", "Concepts") and name.casefold() not in inbound:
            violations.append({"check": "orphan_notes", "note": name,
                               "detail": f"{rel}: nothing links to it (is the index current?)",
                               "severity": "info"})
    # V1's distinct_resource_prose and topic_keys_known (P7): two sources whose Bottom Line
    # or What It Solves is word for word the same, and a source filed under a topic the
    # vault has not accepted (About/Topics.md).
    accepted = set(ctx.vault.topics())
    seen: dict[tuple[str, str], str] = {}
    for path in notes.iter_paths(ctx.vault.root):
        if path.relative_to(ctx.vault.root).parts[0] != "Sources":
            continue
        note = notes.load(path)
        for heading in ("Bottom Line", "What It Solves"):
            text = " ".join((note.sections().get(heading) or "").split()).lower()
            if len(text) >= 40:
                other = seen.setdefault((heading, text), note.name)
                if other != note.name:
                    violations.append({"check": "distinct_resource_prose", "note": note.name,
                                       "detail": f"its {heading} is word for word {other}'s",
                                       "severity": "warn"})
        topic = str(note.frontmatter.get("primary_topic") or "")
        if topic and topic not in accepted:
            violations.append({"check": "topic_keys_known", "note": note.name,
                               "detail": f"filed under {topic!r}, which About/Topics.md does "
                                         f"not list", "severity": "warn"})
    return {"ok": not [v for v in violations if v.get("severity") != "info"],
            "total": len(violations), "violations": violations[:limit],
            "model_found": model.found}
