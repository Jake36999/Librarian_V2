"""Data, Information, Knowledge (Requirements Addendum R16; Research Pipeline §3; plan P6).

**Data** records what a source contains, one component at a time, before any conclusion:
a repository's files, modules, entry points, endpoints, settings, languages and
dependencies; a long document's chapters or sections. Every record carries a stable id, the
source, a locator, the revision or capture it was read at, the method that produced it, its
origin (`observed`, `source-stated`, `model-produced`) and its status. What was not read is
`not examined`, never guessed.

**Information** relates Data records with typed edges, each citing the records it joins and
saying its basis: `static structure` (an import, a route in a file - never runtime
behaviour), `document order`, or a model's reading (marked `inferred`). Document-level
claims need document-level coverage: a chapter not read has no relations drawn to it.

**Knowledge** is the source note itself. `sections()` renders the Data and Information as
note sections (Components, How It Fits Together, Chapters), each line labelled with its
claim origin. Project application never appears here: that is an Offering or Application.

Records are rebuildable from the evidence and the read, and kept per source under
`.librarian/derived/dik/<source>.json`.
"""
from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path
from typing import Any

from . import clerk
from .evidence import EvidenceStore
from .vault import Vault, now_iso

ORIGINS = {"observed": "structurally observed", "source-stated": "source-stated",
           "derived": "derived relation", "potential": "potential use",
           "model-produced": "model-produced"}
CHAPTER = re.compile(r"^\s*(?:#{1,2}\s+(?P<md>.{3,120})|(?P<word>chapter|part|section|appendix)"
                     r"\s+(?P<num>[0-9ivxlc]+)\b[.:]?\s*(?P<title>.{0,100}))\s*$",
                     re.I | re.M)
PAGE = re.compile(r"^\[page (\d+)\]\s*$", re.M)
EXTERNAL_HINT = re.compile(r"^(?!\.)[@\w][\w.@/-]*$")


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "source"


def path_for(vault: Vault, source: str) -> Path:
    return vault.derived / "dik" / f"{slug(source)}.json"


def load(vault: Vault, source: str) -> dict[str, Any]:
    path = path_for(vault, source)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save(vault: Vault, record: dict[str, Any]) -> Path:
    path = path_for(vault, record["source"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def _datum(source: str, kind: str, locator: str, name: str, *, revision: str, method: str,
           evidence: str = "", origin: str = "observed", status: str = "observed",
           **extra: Any) -> dict[str, Any]:
    return {"id": f"{kind}:{locator}", "source": source, "kind": kind, "name": name,
            "locator": locator, "revision": revision, "method": method, "origin": origin,
            "status": status, **({"evidence": evidence} if evidence else {}), **extra}


def _edge(kind: str, a: str, b: str, basis: str, status: str = "observed",
          **extra: Any) -> dict[str, Any]:
    return {"type": kind, "from": a, "to": b, "basis": basis, "status": status,
            "cites": [a, b], **extra}


# ------------------------------------------------------------------ repositories

def repository(vault: Vault, source: str, evidence_ids: list[str],
               revision_hint: str = "") -> dict[str, Any]:
    """Data and Information for a repository, from its intake evidence alone."""
    store = EvidenceStore(vault)
    data: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    files: list[str] = []
    imports: list[dict[str, Any]] = []
    records = [r for r in (store.get(str(ref)) for ref in evidence_ids) if r is not None]
    # one revision for the whole repository: the tree it was surveyed at, else the push
    revision = next((str(r.payload["tree_sha"]) for r in records
                     if r.kind == "survey" and r.payload.get("tree_sha")), revision_hint)
    for record in records:
        p = record.payload
        rev = str(revision or record.fetched_at)[:40]
        if record.kind == "survey":
            files = [str(x) for x in p.get("paths") or []]
            for f in files:
                data.setdefault(f"file:{f}", _datum(source, "file", f, posixpath.basename(f),
                                                    revision=rev, evidence=record.id,
                                                    method="file listing (host API)"))
        elif record.kind == "code_structure":
            method = "static structure (shallow clone survey)"
            for lang, count in (p.get("languages") or {}).items():
                data[f"language:{lang}"] = _datum(source, "language", lang, lang, revision=rev,
                                                  method=method, evidence=record.id, files=count)
            for m in p.get("modules") or []:
                if isinstance(m, dict) and m.get("file"):
                    data[f"module:{m['file']}"] = _datum(
                        source, "module", m["file"], posixpath.basename(m["file"]),
                        revision=rev, method=method, evidence=record.id,
                        symbols=list(m.get("symbols") or [])[:25])
            imports = [i for i in p.get("imports") or [] if isinstance(i, dict)]
        elif record.kind == "access_point":
            method = "static structure (shallow clone survey)"
            for e in p.get("entry_points") or []:
                if isinstance(e, dict):
                    loc = str(e.get("file") or e.get("target") or e.get("name"))
                    data[f"entry_point:{e.get('name')}"] = _datum(
                        source, "entry_point", loc, str(e.get("name")), revision=rev,
                        method=method, evidence=record.id, how=str(e.get("kind", "")))
            for r in p.get("routes") or []:
                if isinstance(r, dict):
                    key = f"{r.get('method', '-')} {r.get('path')}"
                    data[f"endpoint:{key}"] = _datum(
                        source, "endpoint", str(r.get("file", "")), key, revision=rev,
                        method=method, evidence=record.id)
            for env in p.get("environment") or []:
                if isinstance(env, dict):
                    data[f"setting:{env.get('name')}"] = _datum(
                        source, "setting", str(env.get("file", "")), str(env.get("name")),
                        revision=rev, method=method, evidence=record.id,
                        credential=bool(env.get("credential")))
    edges = _relations(source, data, imports, files, revision)
    return {"source": source, "kind": "repository", "revision": revision, "built_at": now_iso(),
            "coverage": "partial (a bounded survey)" if len(files) >= 200 else "surveyed",
            "data": list(data.values()), "information": _dedupe(edges)}



def _relations(source: str, data: dict[str, dict[str, Any]], imports: list[dict[str, Any]],
               files: list[str], revision: str) -> list[dict[str, Any]]:
    """Information for a codebase from its Data: what imports what, what exposes and reads
    what - static text only - and which test file names which module (inferred)."""
    edges: list[dict[str, Any]] = []
    known = {k.split(":", 1)[1] for k in data if k.startswith(("module:", "file:"))}
    for entry in imports:
        here = str(entry.get("file", ""))
        for target in entry.get("imports") or []:
            inside = _resolve(here, str(target), known)
            if inside:
                edges.append(_edge("imports", f"module:{here}", f"module:{inside}",
                                   "static structure (an import statement)"))
            elif EXTERNAL_HINT.match(str(target)):
                package = _package(str(target))
                data.setdefault(f"dependency:{package}", _datum(
                    source, "dependency", package, package, revision=revision,
                    method="import statements", origin="observed"))
                edges.append(_edge("depends_on", f"module:{here}", f"dependency:{package}",
                                   "static structure (an import statement)"))
    for key, d in list(data.items()):
        if d["kind"] in ("endpoint", "setting") and d["locator"]:
            edges.append(_edge("exposes" if d["kind"] == "endpoint" else "reads",
                               f"module:{d['locator']}", key,
                               "static structure (declared in that file)"))
    tests = [f for f in files if re.search(r"(^|/)(tests?|spec)(/|_)|_test\.|\.test\.", f)]
    for t in tests:
        stem = re.sub(r"^test_|_test$|\.test$|\.spec$", "", posixpath.splitext(
            posixpath.basename(t))[0])
        for key in [k for k in data if k.startswith("module:")]:
            if posixpath.splitext(posixpath.basename(key[7:]))[0] == stem and key[7:] != t:
                edges.append(_edge("tests", f"file:{t}", key, "file names", status="inferred"))
    return edges


def from_survey(source: str, survey: dict[str, Any], revision: str, method: str,
                files: list[str] | None = None) -> dict[str, Any]:
    """Data and Information straight from a structure survey (a project scan), with no
    evidence records in between."""
    data: dict[str, dict[str, Any]] = {}
    for f in files or []:
        data[f"file:{f}"] = _datum(source, "file", f, posixpath.basename(f), revision=revision,
                                   method=method)
    for lang, count in (survey.get("languages") or {}).items():
        data[f"language:{lang}"] = _datum(source, "language", lang, lang, revision=revision,
                                          method=method, files=count)
    for m in survey.get("modules") or []:
        data[f"module:{m['file']}"] = _datum(
            source, "module", m["file"], posixpath.basename(m["file"]), revision=revision,
            method=method, symbols=list(m.get("symbols") or [])[:25])
    for e in survey.get("entry_points") or []:
        loc = str(e.get("file") or e.get("target") or e.get("name"))
        data[f"entry_point:{e.get('name')}"] = _datum(source, "entry_point", loc,
                                                      str(e.get("name")), revision=revision,
                                                      method=method, how=str(e.get("kind", "")))
    for r in survey.get("routes") or []:
        key = f"{r.get('method', '-')} {r.get('path')}"
        data[f"endpoint:{key}"] = _datum(source, "endpoint", str(r.get("file", "")), key,
                                         revision=revision, method=method)
    for env in survey.get("environment") or []:
        data[f"setting:{env.get('name')}"] = _datum(source, "setting", str(env.get("file", "")),
                                                    str(env.get("name")), revision=revision,
                                                    method=method,
                                                    credential=bool(env.get("credential")))
    edges = _relations(source, data, list(survey.get("imports") or []), files or [], revision)
    return {"source": source, "kind": "repository", "revision": revision, "built_at": now_iso(),
            "coverage": "partial (a bounded survey)" if survey.get("limited") else "surveyed",
            "data": list(data.values()), "information": _dedupe(edges)}

def _resolve(here: str, target: str, known: set[str]) -> str:
    """The repository file an import names, or "" when it is outside the repository."""
    base = posixpath.dirname(here)
    candidates: list[str] = []
    if target.startswith("."):
        if "/" in target or target.startswith(("./", "../")):        # JS/TS relative path
            joined = posixpath.normpath(posixpath.join(base, target))
            candidates = [joined + ext for ext in ("", ".js", ".ts", ".tsx", ".jsx", ".mjs")] + \
                [posixpath.join(joined, "index" + ext) for ext in (".js", ".ts", ".tsx")]
        else:                                                         # Python relative import
            dots = len(target) - len(target.lstrip("."))
            up = base
            for _ in range(dots - 1):
                up = posixpath.dirname(up)
            rest = target.lstrip(".").replace(".", "/")
            joined = posixpath.join(up, rest) if rest else up
            candidates = [joined + ".py", posixpath.join(joined, "__init__.py")]
    else:
        dotted = re.sub(r"^crate::", "", target).replace("::", "/").replace(".", "/")
        candidates = [dotted + ext for ext in (".py", ".rs", ".java", ".kt", ".go", ".cs")] + \
            [posixpath.join(dotted, "__init__.py"), posixpath.join(dotted, "mod.rs")]
        candidates += [f"src/{c}" for c in candidates]
    for c in candidates:
        if c in known:
            return c
    return ""


def _package(target: str) -> str:
    if target.startswith("@"):
        return "/".join(target.split("/")[:2])
    return re.split(r"[/.:]", target, maxsplit=1)[0]


def _dedupe(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen, out = set(), []
    for e in edges:
        key = (e["type"], e["from"], e["to"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


# ------------------------------------------------------------------ models and datasets

MODEL_FACTS = (("provider", "provider"), ("model_id", "identifier"),
               ("modality", "modality"), ("context_length", "context window"),
               ("price_input_per_1m", "input price per 1M tokens"),
               ("price_output_per_1m", "output price per 1M tokens"),
               ("tool_calling", "tool calling"), ("reasoning", "reasoning"))


def model(source: str, fields: dict[str, Any], revision: str) -> dict[str, Any]:
    """A hosted model's components: what the provider's own listing states - its identity,
    modality, limits, prices and capabilities. Source-stated, never measured here (the
    benchmark and M0 measure); a fact the listing omits is `unknown`."""
    data = []
    for key, label in MODEL_FACTS:
        value = fields.get(key)
        data.append(_datum(source, "listing_fact", key, label, revision=revision,
                           method="the provider's model listing", origin="source-stated",
                           status="observed" if value not in (None, "") else "unknown",
                           value=value))
    for tag in fields.get("best_for") or []:
        data.append(_datum(source, "suggested_use", str(tag), str(tag), revision=revision,
                           method="a clerk's first guess from the listing",
                           origin="model-produced", status="proposed"))
    return {"source": source, "kind": "model", "revision": revision, "built_at": now_iso(),
            "coverage": "listing read", "data": data, "information": []}


def dataset(vault: Vault, source: str, fields: dict[str, Any], revision: str) -> dict[str, Any]:
    """A dataset's components: its access points (files and APIs it declares), each with
    whether it answered when last checked - and how they relate to the dataset's page."""
    from .components import with_status
    points = [str(p) for p in fields.get("access_points") or []]
    data = [_datum(source, "landing_page", str(fields.get("canonical_url") or source),
                   "landing page", revision=revision, method="the dataset's page",
                   origin="source-stated")]
    edges = []
    for p in with_status(vault, points):
        fmt = (re.search(r"\.(\w{2,8})(?:[?#]|$)", p["url"]) or [None, "api"])[1]
        data.append(_datum(source, "access_point", p["url"], fmt, revision=revision,
                           method="a link on the dataset's page", origin="source-stated",
                           status="observed" if p.get("reachable") else
                           ("unknown" if p.get("checked_at") == "never" else "unreachable"),
                           checked_at=p.get("checked_at")))
        edges.append(_edge("offers", data[0]["id"], f"access_point:{p['url']}",
                           "declared on the dataset's page"))
    return {"source": source, "kind": "dataset", "revision": revision, "built_at": now_iso(),
            "coverage": f"{len(points)} access point(s) recorded", "data": data,
            "information": edges}


# ------------------------------------------------------------------ long documents

def chapters(pages: list[str]) -> list[dict[str, Any]]:
    """The document's own divisions - headings a chapter, part or section starts with - each
    with its page range; without any, the pages in fixed runs, labelled as such."""
    marks: list[tuple[int, str]] = []
    for number, page in enumerate(pages, 1):
        for m in CHAPTER.finditer(page[:600]):                    # a heading opens a page
            title = (m.group("md") or f"{m.group('word').title()} {m.group('num')}"
                     f"{(': ' + m.group('title').strip()) if m.group('title') else ''}").strip()
            marks.append((number, " ".join(title.split())[:120]))
            break
    out = []
    if len(marks) >= 2:
        for i, (start, title) in enumerate(marks):
            end = (marks[i + 1][0] - 1) if i + 1 < len(marks) else len(pages)
            out.append({"title": title, "first_page": start, "last_page": max(start, end),
                        "method": "headings in the text"})
        if marks[0][0] > 1:
            out.insert(0, {"title": "Front matter", "first_page": 1,
                           "last_page": marks[0][0] - 1, "method": "headings in the text"})
        return out
    run = 10
    for start in range(1, len(pages) + 1, run):
        end = min(len(pages), start + run - 1)
        out.append({"title": f"pp. {start}-{end}", "first_page": start, "last_page": end,
                    "method": "fixed page runs (no headings found)"})
    return out


def document(vault: Vault, source: str, pages: list[str], read: dict[str, Any] | None,
             chunk_pages: list[tuple[int, int]], revision: str) -> dict[str, Any]:
    """Data for a long document: its chapters, each with coverage and the claims read from it;
    Information: their order, and nothing drawn to a chapter not read."""
    read = read or {}
    parts = chapters(pages)
    data = []
    for position, part in enumerate(parts, 1):
        span = range(part["first_page"], part["last_page"] + 1)
        mine = [i for i, (a, b) in enumerate(chunk_pages) if a in span or b in span]
        done = [i for i in mine if str(i) in read]
        coverage = ("not opened" if not done else "full" if len(done) == len(mine)
                    else f"partial {len(done)}/{len(mine)}")
        claims = [p for i in done for p in (read[str(i)].get("points") or [])][:8]
        locator = f"pp. {part['first_page']}-{part['last_page']}"
        data.append(_datum(source, "chapter", locator, part["title"], revision=revision,
                           method=part["method"], position=position, coverage=coverage,
                           status="observed" if done else "not examined",
                           claims=claims, claims_origin="source-stated (read part by part)"))
    edges = [_edge("precedes", f"chapter:{a['locator']}", f"chapter:{b['locator']}",
                   "document order") for a, b in zip(data, data[1:])]
    full = all(d["coverage"] == "full" for d in data) and bool(data)
    return {"source": source, "kind": "document", "revision": revision, "built_at": now_iso(),
            "coverage": "full" if full else _coverage_line(data),
            "data": data, "information": edges}


def _coverage_line(data: list[dict[str, Any]]) -> str:
    read = sum(1 for d in data if d["coverage"] != "not opened")
    return f"partial: {read} of {len(data)} chapters opened"


def relate_chapters(record: dict[str, Any], endpoint: clerk.Endpoint | None,
                    queue: Path) -> dict[str, Any]:
    """How fully read chapters relate (continues, contrasts, depends on, prepares) - a model's
    reading, marked `inferred`, citing both chapters. A chapter not fully read is left out,
    and a document-level synthesis is drawn only when every chapter was read."""
    read = [d for d in record.get("data", []) if d.get("kind") == "chapter"
            and d.get("coverage") == "full" and d.get("claims")]
    if len(read) < 2:
        return {"added": 0, "reason": "fewer than two fully read chapters"}
    listing = "\n".join(f"{d['id']} | {d['name']}: " + "; ".join(d["claims"][:4]) for d in read)
    result = clerk.run([clerk.chapter_relations(listing)], endpoint, queue)[0]
    if not result.ok:
        return {"added": 0, "reason": f"the clerk did not answer ({result.status})"}
    ids = {d["id"] for d in read}
    added = 0
    for rel in result.value.get("relations", []):
        a, b, kind = str(rel.get("from")), str(rel.get("to")), str(rel.get("type"))
        if a in ids and b in ids and a != b:
            record["information"].append(_edge(kind, a, b, f"model reading ({result.model})",
                                               status="inferred",
                                               why=str(rel.get("why", ""))[:200]))
            added += 1
    record["information"] = _dedupe(record["information"])
    return {"added": added}


# ------------------------------------------------------------------ accepted notes

def rebuild(vault: Vault, conn, source: str = "", limit: int = 20) -> dict[str, Any]:
    """Records for notes accepted before P6 (owner-approved 2026-10-01): rebuilt from each
    note's own evidence, files and - for a document - the read its staged item kept. The
    records are written (derived, rebuildable); the note sections they support are staged as
    a revision a person merges, never written into the accepted note."""
    from . import deep_read as reading, text as doc_text
    from .staging import StagingStore
    store = StagingStore(vault)
    staged = {i.get("accepted_to"): i for i in store.items("source", "accepted")
              if i.get("accepted_to") and not i.get("revision_of")}
    rows = conn.execute("SELECT name, path, kind, frontmatter FROM note WHERE shape = 'source'"
                        + (" AND name = ?" if source else "") + " ORDER BY name",
                        (source,) if source else ()).fetchall()
    out = []
    for row in rows[:max(1, limit)]:
        fm = json.loads(row["frontmatter"])
        kind, name = row["kind"], row["name"]
        revision = str(fm.get("pushed_at") or fm.get("captured_at") or "")
        if kind == "repository":
            record = repository(vault, name, [str(e) for e in fm.get("evidence") or []],
                                str(fm.get("pushed_at") or ""))
        elif kind == "model":
            record = model(name, fm, revision)
        elif kind == "dataset":
            record = dataset(vault, name, fm, revision)
        elif fm.get("file") and (vault.root / str(fm["file"])).is_file():
            item = staged.get(row["path"]) or {"file": fm["file"]}
            item = {**item, "file": fm["file"],
                    **({"clean_file": fm["file_markdown"]} if fm.get("file_markdown") else {})}
            units = reading.source_units(vault, item)
            pages = [t for _, t in units] or doc_text.extract(
                vault.root / fm["file"], vault.derived / "text").pages
            chunks = reading.chunk(units)
            record = document(vault, name, pages, (item.get("deep_read") or {}).get("read"),
                              [(c.first_page, c.last_page) for c in chunks], revision)
        else:
            out.append({"source": name, "status": "skipped",
                        "reason": f"no component model for a {kind or 'source'} without a file"})
            continue
        if not record["data"]:
            out.append({"source": name, "status": "skipped",
                        "reason": "its evidence holds no components (captured before surveys "
                                  "kept them)"})
            continue
        path = save(vault, record)
        rel = path.relative_to(vault.root).as_posix()
        sections = sections_of(record)
        staged_id = _stage_revision(store, name, row["path"], kind, sections, rel) \
            if sections else ""
        out.append({"source": name, "status": "rebuilt", "records": len(record["data"]),
                    "relations": len(record["information"]), "coverage": record["coverage"],
                    **({"revision": staged_id} if staged_id else {})})
    return {"rebuilt": sum(1 for r in out if r["status"] == "rebuilt"),
            "revisions_staged": sum(1 for r in out if r.get("revision")), "results": out}


def _stage_revision(store, name: str, rel: str, kind: str, sections: dict[str, str],
                    record_path: str) -> str:
    """One open revision per note: an earlier, undecided one is brought up to date."""
    open_ = next((i for i in store.items("source") if i.get("revision_of") == rel
                  and i.get("revision_kind") == "dik" and i["status"] in ("staged", "deferred")),
                 None)
    item = {**(open_ or {}), "id": (open_ or {}).get("id") or f"dik-{slug(name)[:50]}",
            "kind": "source", "status": "staged", "name": name, "source_kind": kind,
            "revision_of": rel, "revision_kind": "dik", "sections": sections,
            "dik": record_path, "proposed_by": "dik_rebuild", "evidence": []}
    if open_:
        store.save(item)
    else:
        store.add(item)
    return item["id"]


# ------------------------------------------------------------------ knowledge

def sections_of(record: dict[str, Any]) -> dict[str, str]:
    return sections(record)


def sections(record: dict[str, Any]) -> dict[str, str]:
    """The note sections the records support, each line labelled with its claim origin."""
    data = record.get("data") or []
    edges = record.get("information") or []
    out: dict[str, str] = {}
    if record.get("kind") == "repository":
        lines = []
        for kind, label in (("entry_point", "Entry point"), ("endpoint", "Endpoint"),
                            ("module", "Module"), ("dependency", "Dependency")):
            rows = [d for d in data if d["kind"] == kind][:8]
            for d in rows:
                extra = f" - {', '.join(d.get('symbols', [])[:4])}" if d.get("symbols") else ""
                lines.append(f"- {label} `{d['locator'] if kind != 'endpoint' else d['name']}`"
                             f"{extra} *(structurally observed)*")
        if lines:
            out["Components"] = "\n".join(lines + [
                f"\nRead at `{record.get('revision', '')}`; {record.get('coverage', '')}."])
        rel = [e for e in edges if e["type"] in ("imports", "exposes", "reads", "tests")][:12]
        if rel:
            def label(e: dict[str, Any]) -> str:
                return "derived relation" if e["status"] == "observed" else "inferred"
            out["How It Fits Together"] = "\n".join(
                f"- `{e['from'].split(':', 1)[1]}` {e['type'].replace('_', ' ')} "
                f"`{e['to'].split(':', 1)[1]}` *({label(e)}: {e['basis']})*"
                for e in rel) + "\n\nStatic structure only: nothing here was observed running."
    elif record.get("kind") == "document":
        lines = [f"- {d['name']} ({d['locator']}) - {d['coverage']}"
                 + (f": {d['claims'][0]} *(source-stated)*" if d.get("claims") else "")
                 for d in data]
        if lines:
            out["Chapters"] = "\n".join(lines + [f"\nCoverage: {record.get('coverage')}."])
        rel = [e for e in edges if e["type"] != "precedes"][:10]
        if rel:
            out["How The Chapters Relate"] = "\n".join(
                f"- {e['from'].split(':', 1)[1]} {e['type'].replace('_', ' ')} "
                f"{e['to'].split(':', 1)[1]} *(inferred: {e['basis']})*" for e in rel)
    return out
