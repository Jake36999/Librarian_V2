"""Recording an external research process: a trace, read for its pattern.

A report from another tool (a Deep Research run, a colleague's review) is
evidence of a *process*, not a source of facts (Convention - Recording an
External Research Process). This module reads the process note:

- **rounds**: each a group of checkpoints (a short heading and the tool's own
  paragraph about what it is doing next) followed by the batch of sources it
  read;
- **cited links**: every URL, recorded as `external_link` evidence (what was
  cited, by which tool) with no topic attached, because why it was cited is
  framing and belongs to a session;
- a **replayable trace** in `.librarian/eval/traces/`, for the session-replay
  eval: does V2's round structure reach what the tool reached, within as many
  rounds?

The parser reads the export format Gemini's "thinking" panel produces (headed
paragraphs, then favicon-linked source cards). Another tool's format needs its
own reader; the trace shape it produces is the same.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .evidence import EvidenceStore
from .vault import Vault

SOURCE_CARD = re.compile(
    r"\n\n(?P<domain>[a-z0-9][a-z0-9.-]*\.[a-z]{2,})\n\n(?P<title>[^\n]{3,200})\n\n"
    r"(?:Opens in a new window)?\]\((?P<url>https?://[^\s)]+)\)", re.I)
URL = re.compile(r"\]\((https?://[^\s)]+)\)")
HEADING = re.compile(r"^(?P<h>[A-Z][^\n.!?:\[\]()]{3,80})\n\n(?P<p>[^\n!\[\]]{120,})$", re.M)
ARXIV = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5})", re.I)


@dataclass
class Round:
    n: int
    checkpoints: list[dict[str, str]] = field(default_factory=list)
    sources: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"n": self.n, "checkpoints": self.checkpoints, "sources": self.sources}


def parse(text: str) -> list[Round]:
    """Rounds in order: a run of checkpoints opens a round; the source cards
    after it, until the next checkpoint, are what that round read."""
    events: list[tuple[int, str, dict[str, str]]] = []
    for m in HEADING.finditer(text):
        events.append((m.start(), "checkpoint", {"heading": m.group("h").strip(),
                                                 "text": m.group("p").strip()}))
    first_checkpoint = events[0][0] if events else len(text)
    for m in SOURCE_CARD.finditer(text):
        if m.start() > first_checkpoint:
            events.append((m.start(), "source", {"domain": m.group("domain"),
                                                 "title": m.group("title").strip(),
                                                 "url": m.group("url")}))
    events.sort(key=lambda e: e[0])
    rounds: list[Round] = []
    for _pos, kind, value in events:
        if kind == "checkpoint":
            if not rounds or rounds[-1].sources:
                rounds.append(Round(len(rounds) + 1))
            rounds[-1].checkpoints.append(value)
        elif rounds:
            if value["url"] not in {s["url"] for s in rounds[-1].sources}:
                rounds[-1].sources.append(value)
    return [r for r in rounds if r.checkpoints]


def cited_urls(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for url in URL.findall(text):
        if "gstatic.com" not in url and url not in seen:
            seen[url] = None
    return list(seen)


def record(vault: Vault, path: Path, tool: str) -> dict[str, Any]:
    """Evidence for every cited link, and the replayable trace."""
    text = path.read_text(encoding="utf-8")
    rounds = parse(text)
    store = EvidenceStore(vault)
    ids = []
    refs = []
    from .intake import DOI
    for url in cited_urls(text):
        arxiv = ARXIV.search(url)
        doi = None if arxiv else DOI.search(url)        # doi.org/..., publisher DOI links
        kind = "arxiv" if arxiv else "doi" if doi else ""
        identifier = arxiv.group(1) if arxiv else doi.group(1).rstrip(".") if doi else ""
        payload = {"url": url, "cited_by": tool, "identifier_kind": kind,
                   "identifier": identifier}
        ids.append(store.put("external_link", url, payload).id)
        refs.append({"url": url, "identifier_kind": kind, "identifier": identifier,
                     "ref": f"arXiv:{identifier}" if arxiv else f"doi:{identifier}" if doi
                     else url})
    traces = vault.work("eval") / "traces"
    traces.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    out = traces / f"{name}.json"
    out.write_text(json.dumps({"tool": tool, "from": path.name,
                               "rounds": [r.to_dict() for r in rounds]},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    return {"rounds": len(rounds), "checkpoints": sum(len(r.checkpoints) for r in rounds),
            "sources_in_rounds": sum(len(r.sources) for r in rounds),
            "cited_links": len(ids), "trace": out.relative_to(vault.root).as_posix(),
            "refs": refs}
