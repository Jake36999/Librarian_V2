"""Reference resolution for tool arguments (Requirements Addendum R2).

Models name things the way people do: `[[osquery]]`, `Sources/page/osquery.md`, `b1`,
`Synthesise`. A tool wants the exact note name, brief ID or phase. These resolvers read
the first as the second when exactly one thing fits, and say so (the call's
`adjusted_arguments`).

Two rules keep this safe:
- **Never guess between candidates.** A value that fits more than one thing is refused
  with the candidates, so the model chooses.
- **Never invent.** A value that fits nothing passes through unchanged, and the tool's
  own error (with its own suggestions) answers it.
"""
from __future__ import annotations

import re

from .. import notes
from ..registry import RESOLVERS, Context


def _clean_note(value: str) -> str:
    """`[[Sources/page/Name|alias]]`, `Sources/page/Name.md`, `Name#Heading` -> `Name`."""
    text = value.strip()
    if text.startswith("[[") and text.endswith("]]"):
        text = text[2:-2]
    text = text.split("|", 1)[0].split("#", 1)[0].strip()
    text = text.replace("\\", "/").rsplit("/", 1)[-1]
    return text[:-3] if text.lower().endswith(".md") else text


def _key(text: str) -> str:
    return " ".join(text.casefold().split())


def note(ctx: Context, value: str) -> str:
    if ctx.vault is None:
        return value
    name = _clean_note(value)
    stems: dict[str, list[str]] = {}
    for path in notes.iter_paths(ctx.vault.root):
        stems.setdefault(_key(path.stem), []).append(path.stem)
    if name in stems.get(_key(name), []):
        return name                                         # exact, after cleaning
    matches = sorted(set(stems.get(_key(name), [])))
    if len(matches) > 1:
        raise TypeError(f"{value!r} could be any of {matches}: give the exact note name")
    return matches[0] if matches else name


def _session(ctx: Context):
    if not ctx.session or ctx.vault is None:
        return None
    from ..session import SessionStore
    return SessionStore(ctx.vault).load(ctx.session)


def brief(ctx: Context, value: str) -> str:
    session = _session(ctx)
    if session is None:
        return value
    briefs = session.briefs
    if value in briefs:
        return value
    compact = re.sub(r"[^a-z0-9]", "", value.casefold()).removeprefix("brief")
    for bid in briefs:
        if compact == bid.casefold():
            return bid                                      # b1, B-1, "brief B1"
    by_need = [bid for bid, b in briefs.items() if _key(b.need) == _key(value)]
    if len(by_need) == 1:
        return by_need[0]                                   # the need's own text
    listed = "; ".join(f"{bid}: {b.need[:60]}" for bid, b in sorted(briefs.items())) or "none"
    if not briefs:
        raise TypeError(f"brief {value!r}: this session has no briefs yet - open_brief(need, "
                        f"disqualifiers) first, or call without a brief")
    raise TypeError(f"brief {value!r} is not a brief ID; this session's briefs are: {listed}. "
                    f"Pass the ID (e.g. {sorted(briefs)[0]!r})")


def phase(ctx: Context, value: str) -> str:
    session = _session(ctx)
    if session is None:
        return value
    wanted = re.sub(r"[^a-z]", "", value.casefold())
    matches = [p for p in session.phases if re.sub(r"[^a-z]", "", p) == wanted]
    return matches[0] if len(matches) == 1 else value


def candidate(ctx: Context, value: str) -> str:
    """A session candidate by name: the same cleaning as a note, matched against the
    thread's own candidates first."""
    session = _session(ctx)
    name = _clean_note(value)
    if session is None:
        return name
    if name in session.candidates:
        return name
    matches = sorted(c for c in session.candidates if _key(c) == _key(name))
    if len(matches) > 1:
        raise TypeError(f"{value!r} could be any of {matches}: give the exact candidate")
    return matches[0] if matches else note(ctx, value)


RESOLVERS.update({"note": note, "brief": brief, "phase": phase, "candidate": candidate})
