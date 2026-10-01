"""The lens gold set: a person's labels of which passages teach which stance (A2A-5, A2A-7).

`scripts/lens_eval.py` measures the lens chain against it, and `scripts/lens_gold.py` is
where the owner labels it. A gold source names its text and the stance it teaches; its
labels are per chunk, exactly as the deep read chunks that text:

- `gold`: this passage teaches the stance;
- `none`: this passage teaches no stance (a true negative, so precision is measured on
  labelled passages instead of only bounded).

Each label keeps a digest of the chunk's text. A change to the chunker or to the text
marks the label **stale** - reported, never silently moved to whatever chunk now has that
number. A source with no chunk labels falls back to its phrase rule (`phrases`, the first
three sources' original rule), and the report says which rule each source used.

A source's text is either a file (`file`, relative to the repository root, read whole as
lens_eval always read it) or a library's Source note (`vault` + `note`), read the way the
deep read reads it (`deep_read.source_units`: the cleaned copy, else the attached file).

Proposals come from lenses a person already accepted (`.librarian/lenses.sqlite`): the
chunk holding the accepted lens's quote is proposed as gold for that stance, labelled
`by: accepted-lens` until the owner confirms it. Nothing here calls a model.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import clerk, deep_read
from .vault import Vault, now_iso

GOLD_VERSION = 1
LABELS = ("gold", "none")


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def load(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"version": GOLD_VERSION, "chunk_chars": deep_read.CHUNK_CHARS, "sources": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("sources", {})
    return data


def save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)                                   # a label is never half-written


def _note_path(vault: Vault, name: str) -> Path | None:
    for path in sorted((vault.root / "Sources").rglob(f"{name}.md")):
        if "files" not in path.relative_to(vault.root).parts:   # an attached copy, not the note
            return path
    return None


def units(entry: dict[str, Any], root: Path) -> list[tuple[int, str]]:
    """The source's text as (page, prose) units - what the chunker is given."""
    if entry.get("file"):
        path = Path(entry["file"])
        path = path if path.is_absolute() else root / path
        return [(0, path.read_text(encoding="utf-8"))]
    vault = Vault(Path(entry["vault"]))
    from . import notes
    note = _note_path(vault, entry["note"])
    if note is None:
        raise FileNotFoundError(f"no Source note {entry['note']!r} in {vault.root}")
    fm = notes.load(note).frontmatter
    item = {"file": fm.get("file") or "",
            **({"clean_file": fm["file_markdown"]} if fm.get("file_markdown") else {})}
    found = deep_read.source_units(vault, item)
    if not found:
        raise FileNotFoundError(f"{entry['note']!r} has no attached text to label")
    return found


def chunks(entry: dict[str, Any], root: Path) -> list[deep_read.Chunk]:
    return deep_read.chunk(units(entry, root))


def add_source(data: dict[str, Any], key: str, name: str, explanation: str, *,
               file: str = "", vault: str = "", note: str = "", phrases: str = "",
               by: str = "owner") -> dict[str, Any]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,40}", key):
        raise ValueError("a key is lowercase letters, digits and hyphens")
    if bool(file) == bool(vault and note):
        raise ValueError("give the text as a file, or as a library (vault) and its Source note")
    entry = data["sources"].get(key, {"labels": {}})
    entry.update({"stance": {"name": name.strip(), "explanation": explanation.strip()},
                  "by": entry.get("by", by), "updated_at": now_iso()})
    if file:
        entry["file"] = file
        entry.pop("vault", None), entry.pop("note", None)
    else:
        entry.update(vault=vault, note=note)
        entry.pop("file", None)
    if phrases:
        entry["phrases"] = phrases
    data["sources"][key] = entry
    return entry


def mark(data: dict[str, Any], key: str, index: int, label: str, chunk_list: list[Any],
         by: str = "owner") -> dict[str, Any]:
    """Label one chunk; `skip` removes a label."""
    entry = data["sources"][key]
    if not 0 <= index < len(chunk_list):
        raise ValueError(f"{key} has chunks 0-{len(chunk_list) - 1}")
    if label == "skip":
        entry["labels"].pop(str(index), None)
    elif label in LABELS:
        entry["labels"][str(index)] = {"label": label, "digest": digest(chunk_list[index].text),
                                       "by": by, "at": now_iso()}
    else:
        raise ValueError(f"a label is one of {LABELS} or skip")
    entry["updated_at"] = now_iso()
    return entry


def judged(entry: dict[str, Any], chunk_list: list[Any]) -> dict[int, bool]:
    """Chunk index -> is it gold, for the chunks this source can judge: its fresh labels, or
    (with no labels at all) its phrase rule over every chunk. Stale labels judge nothing."""
    labels = entry.get("labels") or {}
    if labels:
        out = {}
        for idx, lab in labels.items():
            i = int(idx)
            if i < len(chunk_list) and digest(chunk_list[i].text) == lab["digest"]:
                out[i] = lab["label"] == "gold"
        return out
    if entry.get("phrases"):
        rule = re.compile(entry["phrases"], re.I)
        return {c.index: bool(rule.search(c.text)) for c in chunk_list}
    return {}


def rule_of(entry: dict[str, Any]) -> str:
    return "labels" if entry.get("labels") else ("phrases" if entry.get("phrases") else "none")


def status(data: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    out = []
    for key, entry in data["sources"].items():
        row: dict[str, Any] = {"key": key, "stance": entry["stance"]["name"],
                               "rule": rule_of(entry)}
        try:
            cl = chunks(entry, root)
        except (OSError, ValueError) as exc:
            out.append({**row, "error": str(exc)})
            continue
        labels = entry.get("labels") or {}
        fresh = judged(entry, cl)
        row.update(chunks=len(cl), gold=sum(fresh.values()),
                   none=sum(not v for v in fresh.values()),
                   stale=sorted(int(i) for i in labels if int(i) not in fresh),
                   proposed=sum(1 for lab in labels.values() if lab.get("by") != "owner"))
        out.append(row)
    return out


def propose(vault: Vault, data: dict[str, Any]) -> list[dict[str, Any]]:
    """Gold proposals from lenses a person accepted: the chunk holding each accepted lens's
    quote. Pack lenses (hand-written, no passage) and lenses already in the set are left
    out; a lens whose source has no attached text, or whose quote is not found, says so."""
    from .lenses import LensStore
    store = LensStore(vault)
    known = {(e.get("note"), e["stance"]["name"]) for e in data["sources"].values()}
    out = []
    for row in store.list(limit=10_000):
        lens = store.get(row["id"]) or {}
        if str(lens.get("origin", "")).startswith("pack") or not lens.get("source"):
            continue
        if (lens["source"], lens["name"]) in known:
            continue
        entry = {"vault": str(vault.root), "note": lens["source"],
                 "stance": {"name": lens["name"], "explanation": lens.get("perspective", "")},
                 "labels": {}}
        quotes = [q.get("quote", "") for q in lens.get("quotes") or []] or \
            [lens.get("source_quote", "")]
        proposal = {"lens": lens["id"], "name": lens["name"], "source": lens["source"],
                    "explanation": lens.get("perspective", "")}
        try:
            cl = chunks(entry, vault.root)
        except (OSError, ValueError) as exc:
            out.append({**proposal, "problem": str(exc)})
            continue
        hits = sorted({c.index for c in cl for q in quotes
                       if q.strip() and clerk.locate(q, c.text) != -1})
        out.append({**proposal, "chunks": hits} if hits else
                   {**proposal, "problem": "its quote is not in the source's text as read now"})
    return out


def adopt(data: dict[str, Any], proposal: dict[str, Any], vault: Vault, key: str) -> dict:
    """Add a proposal to the set, its chunks labelled gold `by: accepted-lens` - the owner
    confirms them by labelling them again."""
    entry = add_source(data, key, proposal["name"], proposal["explanation"],
                       vault=str(vault.root), note=proposal["source"], by="accepted-lens")
    cl = chunks(entry, vault.root)
    for i in proposal.get("chunks") or []:
        mark(data, key, i, "gold", cl, by="accepted-lens")
    return entry
