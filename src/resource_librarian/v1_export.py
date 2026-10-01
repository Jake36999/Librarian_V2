"""Exporting V1's catalogue into a V2 library, staged (owner, 2026-10-01).

V1 (`D:\\Resource-Library`) stays as it is and keeps working: this only reads it. What V1
ingested becomes staged items in the chosen V2 library, for a person to accept - nothing is
written into the library's own notes until then - and anything V1 did not ingest is left out.

| V1 folder | V2 staged as |
|---|---|
| 01-Resources | a source, kind repository |
| 04-Reviews | a source, kind repository, marked sensitive (a person reviews it) |
| 06-Papers | a source, kind paper |
| 10-Models | a source, kind model |
| 02-Glossary | a concept, a term (its V1 definition offered for the person to keep or reword) |
| 03-Patterns | a concept, a pattern |
| 09-Applications | an import into Applications/ |
| branch offerings | an import into Offerings/ |

Left out, with the reason said: 00-Indexes (generated), 05-Canvases (drawings), 08-Workflows
(V1's own process notes); a note with no `type` (not catalogued - e.g. the PDF text
extractions under 06-Papers/PDF's, which no catalogue note points to); a hub, index, queue
or manifest note (generated or process); a note V1 had not ingested - status `draft` or
`review_pending` (`with_drafts=True` stages drafts too, marked as such); and a source with no
address (no canonical_url, repo_key or identifier) unless it is a paper, which is named by
its title.

**Nothing is lost.** Every staged item carries V1's whole note - frontmatter and text - as a
`v1_note` evidence record, whatever maps onto V2's fields and sections and whatever does not;
a source keeps every V1 section (promotion writes headings V2 does not know after its own),
every V1 frontmatter field (V1's `type` as `v1_type`), and its V1 path and uuid. A concept
keeps its V1 sections beyond the definition, and its V1 note title as an alias, so links by
that title still find it.

**Run again, nothing doubles.** An item already in the library (same name or address) or
already staged from V1 is listed, not staged again. Each staging is logged in
`.librarian/v1_export.jsonl`.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import notes
from .evidence import EvidenceStore
from .staging import StagingStore
from .vault import Vault, jsonl_lines, now_iso

FOLDERS: dict[str, tuple[str, str]] = {
    "01-Resources": ("source", "repository"),
    "04-Reviews": ("source", "repository"),
    "06-Papers": ("source", "paper"),
    "10-Models": ("source", "model"),
    "02-Glossary": ("concept", "term"),
    "03-Patterns": ("concept", "pattern"),
    "09-Applications": ("import", "application"),
    "branch offerings": ("import", "offering"),
}
LEFT_OUT = {"00-Indexes": "generated indexes", "05-Canvases": "drawings, not notes",
            "08-Workflows": "V1's own process notes"}
SENSITIVE = {"04-Reviews"}
INGESTED = {"active", "published"}                 # V1's statuses for a catalogued note
GENERATED_TYPES = ("_index", "_hub", "_queue")     # hubs, indexes, queues: made, not ingested
KIND_BY_TYPE = {"dataset": "dataset", "ai_model": "model", "ml_model": "model"}
# V2 writes these itself on promotion; V1's values are kept under v1_<name>.
RESERVED = {"type", "kind", "evidence", "attested_by", "catalogued_at", "status", "concepts",
            "session", "sensitivity"}
DRAFTED = ("Bottom Line", "What It Solves")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def _address(fm: dict[str, Any]) -> str:
    for key in ("canonical_url", "repo_key", "identifier", "doi", "model_id"):
        if fm.get(key):
            return str(fm[key])
    return ""


def _held(vault: Vault) -> tuple[set[str], set[str]]:
    """Names and addresses already in the library or its staging."""
    names: set[str] = set()
    addresses: set[str] = set()
    for path in vault.root.rglob("*.md"):
        rel = path.relative_to(vault.root)
        if any(p.startswith(".") for p in rel.parts):
            continue
        names.add(path.stem.casefold())
        try:
            fm = notes.load(path).frontmatter
        except Exception:                                   # noqa: BLE001
            continue
        for key in ("canonical_url", "repo_key", "doi"):
            if fm.get(key):
                addresses.add(str(fm[key]).casefold())
    for item in StagingStore(vault).items():
        names.add(str(item.get("name", "")).casefold())
        if item.get("canonical_url"):
            addresses.add(str(item["canonical_url"]).casefold())
    return names, addresses


def _exported(vault: Vault) -> set[str]:
    log = vault.librarian / "v1_export.jsonl"
    if not log.is_file():
        return set()
    return {json.loads(line)["v1_path"] for line in jsonl_lines(log.read_text(encoding="utf-8"))
            if line.strip()}


def candidates(v1_root: Path, with_drafts: bool = False) -> list[dict[str, Any]]:
    """Every V1 note, with what it would become - or why it is left out."""
    out: list[dict[str, Any]] = []
    for folder in sorted(p for p in v1_root.iterdir() if p.is_dir()):
        if folder.name in LEFT_OUT:
            out.append({"v1_path": folder.name + "/", "action": "left out",
                        "why": LEFT_OUT[folder.name]})
            continue
        if folder.name not in FOLDERS:
            continue
        shape, kind = FOLDERS[folder.name]
        for path in sorted(folder.rglob("*.md")):
            rel = path.relative_to(v1_root).as_posix()
            try:
                note = notes.load(path)
            except Exception as exc:                        # noqa: BLE001
                out.append({"v1_path": rel, "action": "left out", "why": f"unreadable: {exc}"})
                continue
            fm = note.frontmatter
            v1_type = str(fm.get("type") or "")
            if not v1_type:
                out.append({"v1_path": rel, "action": "left out", "why": "no type: not catalogued"})
            elif v1_type.endswith(GENERATED_TYPES) or v1_type == "manifest_hub" or \
                    path.name.startswith("_Template"):
                out.append({"v1_path": rel, "action": "left out",
                            "why": "a hub, index, queue, manifest or template: not ingested"})
            elif str(fm.get("status") or "active") not in INGESTED and not (
                    with_drafts and fm.get("status") == "draft"):
                out.append({"v1_path": rel, "action": "left out",
                            "why": f"V1 status {fm.get('status')!r}: not ingested"})
            elif shape == "source" and not _address(fm) and kind != "paper":
                out.append({"v1_path": rel, "action": "left out",
                            "why": "a source with no address (canonical_url, repo_key, id)"})
            else:
                row_kind = KIND_BY_TYPE.get(v1_type, kind) if shape == "source" else kind
                out.append({"v1_path": rel, "action": "stage", "shape": shape, "kind": row_kind,
                            "draft": fm.get("status") == "draft",
                            "name": path.stem, "v1_type": v1_type,
                            "sensitive": folder.name in SENSITIVE})
    return out


def plan(v1_root: Path, vault: Vault, with_drafts: bool = False) -> dict[str, Any]:
    """What an export would do now: staged, already there, or left out - with counts."""
    names, addresses = _held(vault)
    done = _exported(vault)
    rows = []
    for row in candidates(v1_root, with_drafts):
        if row["action"] == "stage":
            fm = notes.load(v1_root / row["v1_path"]).frontmatter
            if row["v1_path"] in done:
                row = {**row, "action": "already staged"}
            elif _target_name(row, fm).casefold() in names or \
                    (_address(fm) and str(fm.get("canonical_url") or "").casefold() in addresses):
                row = {**row, "action": "already held"}
        rows.append(row)
    counts: dict[str, int] = {}
    for row in rows:
        key = row["action"] if row["action"] != "stage" else f"stage {row['shape']}/{row['kind']}"
        counts[key] = counts.get(key, 0) + 1
    return {"from": str(v1_root), "to": str(vault.root), "counts": counts, "rows": rows}


def _target_name(row: dict[str, Any], fm: dict[str, Any]) -> str:
    if row["shape"] == "concept":
        return str(fm.get("canonical_word") or re.sub(r"^(Glossary|Pattern) - ", "", row["name"]))
    return row["name"]


def stage(v1_root: Path, vault: Vault, limit: int = 0,
          with_drafts: bool = False) -> dict[str, Any]:
    """Stage what `plan` says to stage (up to `limit`; 0 is all)."""
    planned = plan(v1_root, vault, with_drafts)
    store = StagingStore(vault)
    evidence = EvidenceStore(vault)
    log = vault.librarian / "v1_export.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for row in planned["rows"]:
        if row["action"] != "stage" or (limit and len(staged) >= limit):
            continue
        path = v1_root / row["v1_path"]
        raw = path.read_text(encoding="utf-8")
        note = notes.load(path)
        record = evidence.put("v1_note", f"v1:{row['v1_path']}", {
            "path": row["v1_path"], "uuid": str(note.frontmatter.get("uuid") or ""),
            "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(), "text": raw})
        item = _item(row, note, record.id)
        store.add(item)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"t": now_iso(), "v1_path": row["v1_path"],
                                     "item": item["id"], "shape": row["shape"]}) + "\n")
        staged.append(item["id"])
    return {**{k: planned[k] for k in ("from", "to")}, "counts": planned["counts"],
            "staged": len(staged), "items": staged[:50]}


def _item(row: dict[str, Any], note: notes.Note, evidence_id: str) -> dict[str, Any]:
    fm = dict(note.frontmatter)
    sections = {h: t.strip() for h, t in note.sections().items() if h and t.strip()}
    base = {"id": f"v1-{_slug(row['name'])}-{hashlib.sha1(row['v1_path'].encode()).hexdigest()[:6]}",
            "status": "staged", "evidence": [{"id": evidence_id, "kind": "v1_note"}],
            "imported_from": {"system": "V1", "path": row["v1_path"],
                              "uuid": str(fm.get("uuid") or ""), "type": row["v1_type"]},
            "sensitivity": "review_required" if row.get("sensitive") else "normal",
            "history": [{"decision": "imported", "by": "v1_export", "at": now_iso(),
                         "reason": f"from V1 {row['v1_path']}" +
                                   (" (a draft in V1)" if row.get("draft") else "")}]}
    if row["shape"] == "source":
        fields = {(f"v1_{k}" if k in RESERVED else k): v for k, v in fm.items()
                  if v not in (None, "", [])}
        fields.update(v1_path=row["v1_path"], imported_from="V1")
        bottom, solves = sections.pop("Bottom Line", ""), sections.pop("What It Solves", "")
        if "Evidence" in sections:          # V2 writes its own Evidence; V1's stays beside it
            sections["V1 Evidence"] = sections.pop("Evidence")
        return {**base, "kind": "source", "source_kind": row["kind"], "name": row["name"],
                "title": str(fm.get("title") or row["name"]),
                "canonical_url": str(fm.get("canonical_url") or ""),
                "captured_at": str(fm.get("metadata_captured_at") or fm.get("captured_at") or ""),
                "topic": "Unfiled", "fields": fields, "sections": sections,
                "review": {"draft": {"status": "ok" if bottom else "missing",
                                     "bottom_line": bottom, "what_it_solves": solves or bottom,
                                     "model": "V1 note"}} if bottom else {}}
    if row["shape"] == "concept":
        name = _target_name(row, fm)
        definition = sections.pop("Definition", "")
        related = [str(r) for r in fm.get("related_terms") or fm.get("glossary_terms") or []]
        aliases = [str(a) for a in fm.get("aliases") or []] + [row["name"]]
        for heading in ("Aliases", "Related Terms"):
            sections.pop(heading, None)
        return {**base, "kind": "concept", "name": name, "sources": [], "usages": [],
                "imported": {"definition": definition, "concept_kind": row["kind"],
                             "aliases": aliases, "related": related, "sections": sections}}
    # an Application or a branch offering: the note as V1 wrote it, into its V2 folder
    folder = "Applications" if row["kind"] == "application" else "Offerings"
    front = {(f"v1_{k}" if k in ("type", "status") else k): v for k, v in fm.items()}
    front.update(type=row["kind"], status="imported", imported_from="V1",
                 v1_path=row["v1_path"], **({"offering_kind": "branch_offering"}
                                             if row["kind"] == "offering" else {}))
    return {**base, "kind": "import", "name": row["name"],
            "target": f"{folder}/{notes.safe_name(row['name'])}.md",
            "frontmatter": front, "body": note.body}
