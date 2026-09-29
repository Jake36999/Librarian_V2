"""The scribe: composes a note's prose from what to say, with its own fixed
instructions.

The person's working context (page 2 of the settings: "what will you be working
on?", long or short replies) shapes chat replies only. It must never reach a
note: a preference for short replies must not make offerings short. So the
session model does not write note prose. It passes the scribe *what* to write
(its points, the verified claims and their quotes) and the scribe decides *how*,
in a call whose prompt is built here, from those parts and nothing else. No
constructor accepts a working context, a session or a conversation, so none can
reach it; a test holds the payload to `PAYLOAD_KEYS`.

What comes back is checked, not trusted:
- the shape must match, with one claim sentence per claim (one repair);
- every sentence must be grounded in the points and quotes it was given (the
  clerk's grounding test); a section that is not keeps the model's own text,
  and the report says so;
- quotes are never the scribe's to write: code sets each one under its claim,
  verbatim, from the verified evidence.

With no scribe model, the model's own text is used as given, and the result
says so (`composed_by: "as given"`).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Sequence

from . import clerk

PAYLOAD_KEYS = clerk.PAYLOAD_KEYS
PROSE = ("summary", "together", "unknowns", "open_first")

INSTRUCTIONS = """\
You compose the prose of one note in a research library, from the points and quotes you are
given. You decide how it is written, never what it says.

- Write for a reader who has never heard of these sources.
- Say everything the points say. Do not shorten into a summary style, and do not add anything:
  every statement must come from the points or the quotes.
- Keep the source names exactly as given.
- Plain declarative prose. No headings, no lists, no quotation of your own.

Sections of an offering:
- summary: what the offering recommends, and for which need, in two to four sentences.
- claims: one sentence per claim, in the order given, restating the claim so it reads on its
  own. Its quote is set beneath it separately; do not repeat it.
- together: how the sources fit together.
- unknowns: what is not established, and what would establish it.
- open_first: which source to open first, and why.

Reply with one JSON object matching this schema:
"""


@dataclass(frozen=True)
class Brief:
    """What to write, entire. Built only by the constructors below."""
    kind: str
    title: str
    points: dict[str, str]
    claims: tuple[dict[str, str], ...]

    def schema(self) -> dict[str, Any]:
        props: dict[str, Any] = {name: {"type": "string", "maxLength": 1600}
                                 for name in self.points}
        props["claims"] = {"type": "array", "items": {"type": "string", "maxLength": 400},
                           "minItems": len(self.claims), "maxItems": len(self.claims)}
        return {"type": "object", "required": sorted(props), "properties": props}

    def payload(self) -> dict[str, Any]:
        """Exactly what leaves the core."""
        points = "\n".join(f"{name}: {text}" for name, text in self.points.items())
        claims = "\n".join(f"{i}. {c['text']} [source: {c['source']}]\n   quote: {c['quote']}"
                           for i, c in enumerate(self.claims, 1))
        return {"task": f"scribe:{self.kind}",
                "system": INSTRUCTIONS + json.dumps(self.schema()),
                "user": f"Title: {self.title}\n\nPoints:\n{points}\n\nClaims:\n{claims}",
                "schema": self.schema(), "temperature": 0.2, "max_tokens": 2000}

    def material(self) -> str:
        return "\n".join([self.title, *self.points.values(),
                          *(f"{c['text']} {c['quote']} {c['source']}" for c in self.claims)])


def offering(title: str, summary: str, claims: Sequence[dict[str, str]],
             synthesis: dict[str, Any]) -> Brief:
    points = {"summary": summary, "together": str(synthesis.get("together") or ""),
              "unknowns": str(synthesis.get("unknowns") or ""),
              "open_first": str(synthesis.get("open_first") or "")}
    return Brief("offering", title, {k: v for k, v in points.items() if v.strip()},
                 tuple({"text": c["text"], "source": c["source"], "quote": c["quote"]}
                       for c in claims))


SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _grounded(text: str, material: str) -> bool:
    return all(clerk.grounded(s, material) for s in SENTENCE.split(text.strip()) if s.strip())


def compose(brief: Brief, endpoint: clerk.Endpoint | None) -> dict[str, Any]:
    """`{"sections": {...}, "claims": [...], "composed_by": ..., "kept_as_given": [...]}`."""
    given = {"sections": dict(brief.points), "claims": [c["text"] for c in brief.claims],
             "composed_by": "as given", "kept_as_given": []}
    if endpoint is None:
        return given
    payload = brief.payload()
    problems, model, value = "", "", {}
    try:
        for _attempt in range(clerk.REPAIR_ATTEMPTS + 1):
            raw, model = endpoint.complete(payload, problems)
            value, problems = clerk.parse(raw, payload["schema"])
            if not problems:
                break
    except Exception as exc:                                # noqa: BLE001
        return {**given, "scribe_error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    if problems:
        return {**given, "scribe_error": f"the reply did not match the shape ({problems})"}
    material = brief.material()
    out = {"sections": {}, "claims": [], "composed_by": model or "scribe", "kept_as_given": []}
    for name, text in brief.points.items():
        written = str(value.get(name) or "").strip()
        if written and _grounded(written, material):
            out["sections"][name] = written
        else:
            out["sections"][name] = text
            out["kept_as_given"].append(name)
    for i, (claim, written) in enumerate(zip(brief.claims, value.get("claims") or []), 1):
        written = str(written).strip()
        if written and _grounded(written, f"{claim['text']} {claim['quote']} {claim['source']}"):
            out["claims"].append(written)
        else:
            out["claims"].append(claim["text"])
            out["kept_as_given"].append(f"claim {i}")
    return out
