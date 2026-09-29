"""Intake: one pipeline from a reference to a staged, described source.

    capture ─► fetch ─► record evidence ─► read facts ─► describe ─► stage

- **Capture** takes what a person or agent has: a GitHub URL or `owner/repo`,
  an arXiv id, a DOI, a web page, or a file in `Inbox/`.
- **Fetch** goes through one `Fetcher`, so every network call is polite, can be
  replayed in tests, and arXiv is paced globally (one request every three
  seconds, whatever else is running).
- **Record evidence**: what came back, as it came back, content-addressed.
- **Read facts**: licence, language, dates, identifiers. Code, never a model.
- **Describe**: clerk tasks over the evidence, each unframed. Term usages
  found by the `terms` task are recorded as evidence too.
- **Stage**: a staging item with the described sections, the unframed Bottom
  Line draft, the sensitivity check and what is still missing.

Screening against a need is framed, so it happens only when the caller passes
a need, and its verdict is returned to the caller (the session records it on
the Candidate); a screen rejection is not staged, and nothing about the need is
written into evidence or the staged item.

A failure is quarantined with the stage that failed and why. Nothing is
dropped silently.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from . import clerk, facts, notes, structure, text
from .evidence import EvidenceStore
from .search import Engine
from .staging import StagingStore
from .vault import Vault, now_iso

GITHUB = re.compile(r"^(?:https?://github\.com/)?([A-Za-z0-9][\w.-]*)/([\w.-]+?)(?:\.git)?/?$")
ARXIV = re.compile(r"(?:arxiv\.org/(?:abs|pdf|html)/|arxiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I)
DOI = re.compile(r"\b(10\.\d{4,9}/[-._;()/:a-z0-9]+)\b", re.I)
USER_AGENT = "resource-librarian/2 (+https://github.com; research catalogue)"
ARXIV_INTERVAL = 3.0
README_CHARS = 20_000
TREE_PATHS = 4000

NOT_ASKED = frozenset({"status", "attested_by"})     # a note's lifecycle, never the clerk's
UNFILED = "Unfiled"
AXIS_QUESTIONS = {
    "domain_primary": "What subject area is this project about?",
    "deployment_target": "Where does this run? 'Local_Only' means on one machine, 'Server' "
                         "means it is hosted for others, 'Browser' means in a web page, "
                         "'Desktop' means an installed application.",
    "interface_protocol": "How does a person or program mainly interact with it?",
    "data_locality": "Where does its data live? 'Local_First' means on the machine that "
                     "runs it, 'Distributed' means across nodes or services, 'Stateless' "
                     "means it keeps none.",
}


# -------------------------------------------------------------------- capture

@dataclass(frozen=True)
class Reference:
    kind: str          # github | arxiv | doi | page | file
    key: str           # owner/repo, arXiv id, DOI, URL or vault-relative path
    original: str


def capture(ref: str, vault: Vault | None = None) -> Reference:
    raw = ref.strip()
    if vault is not None and not raw.startswith(("http://", "https://")):
        candidate = (vault.root / raw).resolve()
        if candidate.is_file() and vault.root in candidate.parents:
            return Reference("file", candidate.relative_to(vault.root).as_posix(), raw)
    if (m := ARXIV.search(raw)) and ("arxiv" in raw.lower() or re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", raw)):
        return Reference("arxiv", m.group(1), raw)
    if (m := DOI.search(raw)) and ("doi" in raw.lower() or raw.startswith("10.")):
        return Reference("doi", m.group(1).rstrip("."), raw)
    if raw.lower().startswith("model:"):
        return Reference("model", raw[len("model:"):].strip(), raw)
    if (m := GITHUB.match(raw)) and ("github.com" in raw or not raw.startswith("http")):
        return Reference("github", f"{m.group(1)}/{m.group(2)}", raw)
    if raw.startswith(("http://", "https://")):
        return Reference("page", raw, raw)
    raise ValueError(f"cannot tell what {ref!r} is: give a URL, owner/repo, an arXiv id, a "
                     f"DOI, or a file in Inbox/")


# -------------------------------------------------------------------- fetching

class FetchError(RuntimeError):
    pass


class Fetcher:
    """Every network read intake makes. Replace `get` in tests."""

    _arxiv_lock = threading.Lock()
    _arxiv_last = 0.0

    def get(self, url: str, accept: str = "") -> bytes:
        if "export.arxiv.org" in url:
            with Fetcher._arxiv_lock:
                wait = ARXIV_INTERVAL - (time.monotonic() - Fetcher._arxiv_last)
                if wait > 0:
                    time.sleep(wait)
                Fetcher._arxiv_last = time.monotonic()
        headers = {"User-Agent": USER_AGENT}
        if accept:
            headers["Accept"] = accept
        if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise FetchError(f"{url}: HTTP {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise FetchError(f"{url}: {exc}") from exc

    @contextmanager
    def checkout(self, key: str):
        """A shallow clone of a GitHub repository, removed afterwards. Nothing
        in it is run (`structure`)."""
        try:
            with structure.shallow_clone(f"https://github.com/{key}.git") as root:
                yield root
        except structure.CloneError as exc:
            raise FetchError(f"clone {key}: {exc}") from exc


class Replay(Fetcher):
    """Recorded responses by URL, for tests and offline runs."""

    def __init__(self, responses: dict[str, bytes | str | dict | Exception]):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, accept: str = "") -> bytes:
        self.calls.append(url)
        for key, value in self.responses.items():
            if url == key or (key.endswith("*") and url.startswith(key[:-1])):
                if isinstance(value, Exception):
                    raise value
                if isinstance(value, dict):
                    return json.dumps(value).encode()
                return value.encode() if isinstance(value, str) else value
        raise FetchError(f"{url}: HTTP 404")

    @contextmanager
    def checkout(self, key: str):
        """A recorded checkout is a local directory under `clone:<owner/repo>`;
        without one, the repository is not cloned."""
        self.calls.append(f"clone:{key}")
        root = self.responses.get(f"clone:{key}")
        if root is None:
            raise FetchError(f"clone {key}: none recorded")
        yield Path(root)


# ---------------------------------------------------------------- fetched

@dataclass
class Fetched:
    """What a fetch produced, before description."""
    kind: str                          # source kind: repository, paper, page, document
    name: str
    title: str
    canonical_url: str
    fields: dict[str, Any] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)       # documentation, abstract, listing
    evidence: list[dict[str, Any]] = field(default_factory=list)
    file: str = ""
    notes: list[str] = field(default_factory=list)     # what could not be read, and why


def _record(store: EvidenceStore, fetched: Fetched, kind: str, source: str,
            payload: dict[str, Any]) -> None:
    record = store.put(kind, source, payload)
    fetched.evidence.append({"id": record.id, "kind": kind, "source": source,
                             "fetched_at": record.fetched_at})


def fetch_github(key: str, fetcher: Fetcher, store: EvidenceStore) -> Fetched:
    api = f"https://api.github.com/repos/{key}"
    meta = json.loads(fetcher.get(api))
    owner, repo = meta.get("full_name", key).split("/", 1)
    fetched = Fetched("repository", f"{owner} - {repo}", f"{owner} - {repo}",
                      meta.get("html_url") or f"https://github.com/{key}")
    keep = ("full_name", "description", "language", "stargazers_count", "forks_count",
            "pushed_at", "created_at", "archived", "fork", "topics", "homepage",
            "default_branch", "open_issues_count")
    facts_meta = {k: meta.get(k) for k in keep}
    facts_meta["license_spdx"] = (meta.get("license") or {}).get("spdx_id") or ""
    _record(store, fetched, "metadata", api, facts_meta)
    readme = ""
    try:
        readme = fetcher.get(f"{api}/readme", "application/vnd.github.raw").decode(
            "utf-8", "replace")[:README_CHARS]
        _record(store, fetched, "readme", f"{api}/readme", {"text": readme})
    except FetchError:
        pass
    licence_text = ""
    try:
        licence_text = fetcher.get(f"{api}/license", "application/vnd.github.raw").decode(
            "utf-8", "replace")[:20_000]
    except FetchError:
        pass
    paths: list[str] = []
    try:
        tree = json.loads(fetcher.get(f"{api}/git/trees/{meta.get('default_branch') or 'HEAD'}"
                                      f"?recursive=1"))
        paths = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"][:TREE_PATHS]
        survey = survey_of(paths, truncated=bool(tree.get("truncated")))
        _record(store, fetched, "survey", f"{api}/git/trees", survey)
    except FetchError:
        survey = {}
    code: dict[str, Any] = {}
    if (meta.get("size") or 0) > structure.MAX_REPO_KB:
        fetched.notes.append(f"not cloned: {meta['size'] // 1000} MB is over the "
                             f"{structure.MAX_REPO_KB // 1000} MB limit")
    else:
        try:
            with fetcher.checkout(meta.get("full_name", key)) as root:
                code = structure.survey(root)
        except FetchError as exc:
            fetched.notes.append(f"not cloned: {exc}")
    if code:
        _record(store, fetched, "code_structure", f"{fetched.canonical_url} (shallow clone)",
                {k: code[k] for k in ("files", "source_files_read", "languages",
                                      "test_files", "modules", "limited")})
        _record(store, fetched, "access_point", f"{fetched.canonical_url} (shallow clone)",
                {k: code[k] for k in ("entry_points", "routes", "environment",
                                      "mcp_server_files")})
    fetched.fields = {"repo_key": meta.get("full_name", key),
                      "stars": meta.get("stargazers_count"), "pushed_at": meta.get("pushed_at"),
                      "language": meta.get("language") or ""}
    fetched.texts = {"documentation": f"{meta.get('description') or ''}\n\n{readme}".strip(),
                     "listing": survey_text(survey), "licence": licence_text,
                     "structure": structure.structure_text(code),
                     "access_points": structure.access_points_section(code),
                     "description": meta.get("description") or ""}
    fetched.fields["_derive"] = {"meta": {**facts_meta, "pushed_at": meta.get("pushed_at")},
                                 "survey": survey, "paths": paths, "licence": licence_text}
    return fetched


def survey_of(paths: list[str], truncated: bool = False) -> dict[str, Any]:
    """A repository's shape from its file listing: extensions, top directories,
    counts. Data, unframed."""
    ext = Counter(PurePosixPath(p).suffix.lower() for p in paths if PurePosixPath(p).suffix)
    dirs = Counter(p.split("/")[0] for p in paths if "/" in p)
    return {"files": len(paths), "truncated": truncated,
            "extensions": [f"{e} ({n})" for e, n in ext.most_common(15)],
            "top_directories": [f"{d}/ ({n})" for d, n in dirs.most_common(15)],
            "root_files": sorted(p for p in paths if "/" not in p)[:30],
            "paths": paths[:200]}


def survey_text(survey: dict[str, Any]) -> str:
    if not survey:
        return ""
    return "\n".join([f"files: {survey['files']}" + (" (listing truncated)"
                                                      if survey.get("truncated") else ""),
                      "extensions:", *[f"  {e}" for e in survey["extensions"]],
                      "top directories:", *[f"  {d}" for d in survey["top_directories"]],
                      "root files:", *[f"  {f}" for f in survey["root_files"]]])


ATOM = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def fetch_arxiv(identifier: str, fetcher: Fetcher, store: EvidenceStore) -> Fetched:
    url = f"https://export.arxiv.org/api/query?id_list={identifier}"
    root = ET.fromstring(fetcher.get(url))
    entry = root.find("a:entry", ATOM)
    if entry is None or entry.find("a:title", ATOM) is None:
        raise FetchError(f"arXiv has no paper {identifier}")
    title = " ".join((entry.findtext("a:title", "", ATOM)).split())
    abstract = " ".join((entry.findtext("a:summary", "", ATOM)).split())
    authors = [a.findtext("a:name", "", ATOM) for a in entry.findall("a:author", ATOM)]
    year = (entry.findtext("a:published", "", ATOM) or "")[:4]
    fetched = Fetched("paper", _paper_name(authors, year, title), title,
                      f"https://arxiv.org/abs/{identifier}")
    _record(store, fetched, "metadata", url, {"title": title, "authors": authors,
                                              "published": year, "identifier": identifier})
    _record(store, fetched, "abstract", url, {"text": abstract})
    fetched.fields = {"identifier_kind": "arxiv", "identifier": identifier,
                      "authors": authors, "year": int(year) if year.isdigit() else year,
                      "paper_kind": "preprint"}
    fetched.texts = {"abstract": abstract, "documentation": f"{title}\n\n{abstract}"}
    return fetched


def fetch_doi(identifier: str, fetcher: Fetcher, store: EvidenceStore) -> Fetched:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(identifier)}"
    message = json.loads(fetcher.get(url)).get("message") or {}
    title = " ".join((message.get("title") or [""])[0].split())
    if not title:
        raise FetchError(f"Crossref has no title for {identifier}")
    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip()
               for a in message.get("author") or []]
    year = str(((message.get("issued") or {}).get("date-parts") or [[""]])[0][0])
    abstract = re.sub(r"<[^>]+>", " ", message.get("abstract") or "")
    abstract = " ".join(html.unescape(abstract).split())
    fetched = Fetched("paper", _paper_name(authors, year, title), title,
                      f"https://doi.org/{identifier}")
    _record(store, fetched, "metadata", url, {
        "title": title, "authors": authors, "published": year, "identifier": identifier,
        "venue": (message.get("container-title") or [""])[0], "type": message.get("type", "")})
    if abstract:
        _record(store, fetched, "abstract", url, {"text": abstract})
    fetched.fields = {"identifier_kind": "doi", "identifier": identifier, "authors": authors,
                      "year": int(year) if year.isdigit() else year,
                      "venue": (message.get("container-title") or [""])[0],
                      "paper_kind": "published"}
    fetched.texts = {"abstract": abstract, "documentation": f"{title}\n\n{abstract}"}
    return fetched


def _paper_name(authors: list[str], year: str, title: str) -> str:
    surname = (authors[0].split()[-1] if authors and authors[0].split() else "Unknown")
    return notes.safe_name(f"{surname}, {year} - {title}")[:120]


TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)


# Public per-model listing pages, by provider. A provider absent here has no
# known page to fetch, so `fetch_model` refuses loudly rather than guessing a URL.
MODEL_PAGES: dict[str, str] = {"deepinfra": "https://deepinfra.com/{model_id}"}


def fetch_model(key: str, fetcher: Fetcher, store: EvidenceStore) -> Fetched:
    """`key` is `<provider>:<model_id>` (a `model:` reference's own key). The
    model's specs are read from its provider's public listing page by a clerk
    task in `describe`, exactly as a repository's mechanics are read from its
    README - never assumed from what the model's name suggests."""
    provider, _, model_id = key.partition(":")
    provider, model_id = provider.strip().lower(), model_id.strip()
    if not provider or not model_id:
        raise FetchError(f"a model reference is 'model:<provider>:<model_id>', not {key!r}")
    if provider not in MODEL_PAGES:
        raise FetchError(f"no public listing page is known for provider {provider!r}; "
                         f"known: {sorted(MODEL_PAGES)}")
    url = MODEL_PAGES[provider].format(model_id=model_id)
    raw = fetcher.get(url, "text/html").decode("utf-8", "replace")
    body = " ".join(html.unescape(TAG.sub(" ", raw)).split())[:README_CHARS]
    name = notes.safe_name(f"{model_id.split('/')[-1]} - {provider}")[:120]
    fetched = Fetched("model", name, model_id, url,
                      fields={"provider": provider, "model_id": model_id})
    _record(store, fetched, "model_listing", url, {"provider": provider, "model_id": model_id,
                                                    "text": body})
    fetched.texts = {"documentation": body}
    return fetched


def fetch_page(url: str, fetcher: Fetcher, store: EvidenceStore) -> Fetched:
    raw = fetcher.get(url, "text/html").decode("utf-8", "replace")
    title = html.unescape(re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I).group(1)
                          if re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
                          else url).strip()
    body = " ".join(html.unescape(TAG.sub(" ", raw)).split())[:README_CHARS]
    fetched = Fetched("page", notes.safe_name(title)[:120] or notes.safe_name(url)[:120],
                      title, url)
    _record(store, fetched, "page", url, {"title": title, "text": body})
    fetched.texts = {"documentation": body}
    return fetched


def fetch_file(rel: str, vault: Vault, store: EvidenceStore) -> Fetched:
    path = vault.root / rel
    result = text.extract(path, vault.derived / "text")
    if result.error:
        raise FetchError(f"{rel}: {result.error}")
    body = "\n\n".join(result.pages)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    fetched = Fetched("document", notes.safe_name(path.stem)[:120], path.stem,
                      f"file:{digest}", file=rel)
    _record(store, fetched, "pdf_text" if path.suffix.lower() == ".pdf" else "page",
            f"file:{path.name}#{digest}",
            {"file": path.name, "pages": len(result.pages), "empty_pages": result.empty_pages,
             "text": body[:README_CHARS]})
    fetched.texts = {"documentation": body[:README_CHARS]}
    if result.empty_pages:
        fetched.fields["pages_without_text"] = result.empty_pages
    return fetched


FETCHERS: dict[str, Callable[..., Fetched]] = {"github": fetch_github, "arxiv": fetch_arxiv,
                                               "doi": fetch_doi, "page": fetch_page,
                                               "model": fetch_model}


# --------------------------------------------------------------- the pipeline

@dataclass
class IntakeResult:
    ref: str
    status: str                  # staged | already_held | screened_out | quarantined | error
    item: str = ""
    name: str = ""
    detail: Any = ""
    screen: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in ("", {}, None)}


def ingest(vault: Vault, engine: Engine, ref: str, *, endpoint: clerk.Endpoint | None,
           fetcher: Fetcher | None = None, need: str = "",
           disqualifiers: list[str] | None = None, found_by: dict[str, Any] | None = None
           ) -> IntakeResult:
    """One reference, through to staging. `found_by` (a session and brief id)
    is kept on the staged item for provenance and never reaches a clerk."""
    fetcher = fetcher or Fetcher()
    store = EvidenceStore(vault)
    staging = StagingStore(vault)
    try:
        reference = capture(ref, vault)
    except ValueError as exc:
        return _quarantine(vault, ref, "capture", str(exc))
    try:
        if reference.kind == "file":
            fetched = fetch_file(reference.key, vault, store)
        else:
            fetched = FETCHERS[reference.kind](reference.key, fetcher, store)
    except (FetchError, ET.ParseError, ValueError, KeyError) as exc:
        return _quarantine(vault, ref, "fetch", str(exc))

    held = engine.index.note_row(fetched.name)
    # A Markdown file dropped into Inbox/ (a converted PDF, say) is indexed as
    # a note under its own name: that is the file being ingested, not a copy
    # already held.
    if held is not None and not (reference.kind == "file" and held["path"] == reference.key):
        return IntakeResult(ref, "already_held", name=fetched.name, detail=held["path"])
    for item in staging.items("source"):
        if item.get("canonical_url") == fetched.canonical_url and item["status"] in (
                "staged", "deferred"):
            return IntakeResult(ref, "already_held", item["id"], fetched.name,
                                "already waiting in staging")

    documentation = fetched.texts.get("documentation", "")
    screen: dict[str, Any] = {}
    if need:
        result = clerk.run([clerk.screen(documentation, need, disqualifiers or [])],
                           endpoint, vault.work("queue") / "clerk")[0]
        screen = {"status": result.status, **result.value}
        if result.ok and result.value.get("verdict") == "reject":
            return IntakeResult(ref, "screened_out", name=fetched.name, screen=screen,
                                detail="the screen found a stated contradiction")
        # A paper can share a need's vocabulary without engaging with its
        # substance (V1's PAPER_RELEVANCE); worth a cheap check before the
        # larger `describe()` pass runs on something off-topic.
        abstract = fetched.texts.get("abstract", "")
        if fetched.kind == "paper" and abstract:
            relevance = clerk.run([clerk.relevance(abstract, need)], endpoint,
                                  vault.work("queue") / "clerk")[0]
            screen["relevance"] = {"status": relevance.status, **relevance.value}
            if relevance.ok and relevance.value.get("verdict") == "reject":
                return IntakeResult(ref, "screened_out", name=fetched.name, screen=screen,
                                    detail="the abstract does not engage with the stated need")

    fields, sections, review, sensitivity = describe(vault, fetched, endpoint, store)
    item_id = f"{re.sub(r'[^a-z0-9]+', '-', fetched.name.lower()).strip('-')[:50]}-" \
              f"{hashlib.sha256(fetched.canonical_url.encode()).hexdigest()[:6]}"
    staging.add({"id": item_id, "kind": "source", "source_kind": fetched.kind,
                 "name": fetched.name, "title": fetched.title,
                 "canonical_url": fetched.canonical_url,
                 "topic": fields.get("primary_topic") or UNFILED,
                 "fields": fields, "sections": sections, "evidence": fetched.evidence,
                 "evidence_text": _evidence_text(fetched, sections),
                 "captured_at": now_iso()[:10], "file": fetched.file,
                 "found_for": found_by or {}, "proposed_by": "intake",
                 "sensitivity": sensitivity, "review": review,
                 **({"intake_notes": fetched.notes} if fetched.notes else {}),
                 "readiness": readiness(engine, fetched.kind, fields)})
    return IntakeResult(ref, "staged", item_id, fetched.name, screen=screen,
                        detail={"sensitivity": sensitivity,
                                "draft": review["draft"].get("status")})


def describe(vault: Vault, fetched: Fetched, endpoint: clerk.Endpoint | None,
             store: EvidenceStore) -> tuple[dict, dict, dict, str]:
    """Facts by code, then descriptions by the clerk, each task unframed."""
    model = vault_model(vault)
    permitted = model.axes_for("source", fetched.kind)
    fields = {k: v for k, v in fetched.fields.items() if not k.startswith("_")}
    derive = fetched.fields.get("_derive")
    documentation = fetched.texts.get("documentation", "")
    if derive:
        fields.update(facts.derive_axes(derive["meta"], derive["survey"], documentation,
                                        licence_text=derive["licence"], paths=derive["paths"],
                                        repo_key=fields.get("repo_key", ""),
                                        permitted=permitted))
    sections_of = dict(model.sections_for("source", fetched.kind))
    limits_to = "Evidence & Limits" if "Evidence & Limits" in sections_of else "Reading Notes"
    tasks: list[tuple[str, clerk.Task]] = []
    sections: dict[str, str] = {}
    if fetched.kind == "repository":
        if fetched.texts.get("listing"):
            listing = fetched.texts["listing"]
            if fetched.texts.get("structure"):
                listing += ("\n\nmodules and the names they define:\n"
                            + fetched.texts["structure"])
            tasks.append(("What Is Inside", clerk.inside(listing)))
        if fetched.texts.get("access_points"):          # by code, not a clerk
            sections["Access Points" if "Access Points" in sections_of
                     else "What Is Inside"] = fetched.texts["access_points"]
        tasks += [("Architecture & Mechanics", clerk.mechanics(documentation)),
                  ("Integration & Use Cases", clerk.uses(documentation)),
                  (limits_to, clerk.limits(documentation))]
    elif fetched.kind == "paper" and fetched.texts.get("abstract"):
        tasks += [("Claim", clerk.claims(fetched.texts["abstract"])),
                  (limits_to, clerk.limits(fetched.texts["abstract"]))]
    elif fetched.kind != "model" and documentation:
        # A document's own claims earn search credit in Claims; Reading Notes
        # is a caveat section, only the fallback for a vault without Claims.
        points_to = "Claims" if "Claims" in sections_of else "Reading Notes"
        tasks += [(points_to, clerk.points(documentation)),
                  (limits_to, clerk.limits(documentation))]
    if fetched.kind != "model":
        for name, values in permitted.items():
            if values and name not in fields and name not in NOT_ASKED:  # never an empty choice
                tasks.append((f"axis:{name}", clerk.axis(name, values, documentation,
                                                         AXIS_QUESTIONS.get(name, ""))))
        topics = vault.topics()
        if len(topics) > 1:                                 # more than Unfiled to choose from
            tasks.append(("topic", clerk.topic(_draft_evidence(fetched), topics)))
    if fetched.kind == "model":
        tasks.append(("model_specs", clerk.model_specs(
            documentation, permitted.get("modality", []), permitted.get("license_class", []),
            permitted.get("best_for", []), permitted.get("suggested_tier", []),
            fields.get("model_id", fetched.title))))
    tasks += [("terms", clerk.terms(documentation)),
              ("sensitivity", clerk.sensitivity(documentation)),
              ("draft", clerk.bottom_line(_draft_evidence(fetched)))]
    results = clerk.run([t for _, t in tasks], endpoint, vault.work("queue") / "clerk")
    review: dict[str, Any] = {"reviewed_at": now_iso(), "draft": {"status": "queued"}}
    sensitivity = "normal"
    for (label, _task), result in zip(tasks, results):
        if label.startswith("axis:"):
            if result.ok and result.value.get("value"):
                fields[label[5:]] = result.value["value"]
        elif label == "topic":
            if result.ok and result.value.get("topic") and result.value["topic"] != UNFILED:
                fields["primary_topic"] = result.value["topic"]
        elif label == "terms":
            for term in result.value.get("terms", []) if result.ok else []:
                store.put("term_usage", fetched.canonical_url,
                          {"term": term["term"], "sentence": term["sentence"]})
        elif label == "model_specs":
            if result.ok:
                v = result.value
                for name in ("modality", "license_class"):
                    if v.get(name):
                        fields[name] = v[name]
                for name in ("context_length", "price_input_per_1m", "price_output_per_1m"):
                    if v.get(name):
                        fields[name] = v[name]
                fields["tool_calling"] = bool(v.get("tool_calling"))
                fields["reasoning"] = bool(v.get("reasoning"))
                if v.get("best_for"):
                    fields["best_for"] = v["best_for"]
                if v.get("suggested_tier"):
                    fields["suggested_tier"] = v["suggested_tier"]
                sections["Specs"] = _model_specs_section(fields)
        elif label == "sensitivity":
            if result.ok and result.value.get("sensitivity") == "review_required":
                sensitivity = "review"
                review["sensitivity"] = result.value.get("reason", "")
        elif label == "draft":
            review["draft"] = {"status": result.status, **result.value,
                               "dropped": result.dropped, "model": result.model}
        elif result.ok and result.value.get("bullets"):
            bullets = "\n".join(f"- {b}" for b in result.value["bullets"])
            sections[label] = f"{sections[label]}\n{bullets}" if sections.get(label) else bullets
    queued = [label for (label, _t), r in zip(tasks, results) if r.status == "queued"]
    if queued:
        review["queued"] = queued
    if fetched.file:
        fields["file"] = fetched.file
    return fields, sections, review, sensitivity


def _model_specs_section(fields: dict[str, Any]) -> str:
    lines = [f"- **Provider**: {fields.get('provider', '')} (`{fields.get('model_id', '')}`)"]
    if fields.get("context_length"):
        lines.append(f"- **Context length**: {int(fields['context_length']):,} tokens")
    price_in, price_out = fields.get("price_input_per_1m"), fields.get("price_output_per_1m")
    if price_in or price_out:
        lines.append(f"- **Price**: ${price_in or 0:g} / ${price_out or 0:g} per 1M tokens")
    if fields.get("modality"):
        lines.append(f"- **Modality**: {str(fields['modality']).replace('_', ' ')}")
    if fields.get("tool_calling"):
        lines.append("- Supports tool/function calling.")
    if fields.get("reasoning"):
        lines.append("- A reasoning model: chain-of-thought is returned separately from "
                     "the answer.")
    if fields.get("best_for"):
        tags = ", ".join(str(t).replace("_", " ") for t in fields["best_for"])
        lines.append(f"- **Best for** (a first guess; confirm or correct it): {tags}")
    if fields.get("suggested_tier"):
        lines.append(f"- **Suggested tier** (a first guess): "
                     f"{str(fields['suggested_tier']).replace('_', ' ')}")
    return "\n".join(lines)


def _draft_evidence(fetched: Fetched) -> str:
    return "\n\n".join(t for t in (fetched.texts.get("description", ""),
                                   fetched.texts.get("abstract", ""),
                                   fetched.texts.get("documentation", "")[:4000]) if t)


def _evidence_text(fetched: Fetched, sections: dict[str, str]) -> str:
    parts = [f"title: {fetched.title}"]
    if fetched.texts.get("description"):
        parts.append(f"description: {fetched.texts['description']}")
    if fetched.texts.get("abstract"):
        parts.append(f"abstract: {fetched.texts['abstract']}")
    parts += [f"{h}:\n{t}" for h, t in sections.items()]
    if not fetched.texts.get("abstract") and not fetched.texts.get("description"):
        parts.append(fetched.texts.get("documentation", "")[:3000])
    return "\n\n".join(parts)


def vault_model(vault: Vault):
    from . import schema
    return schema.load(vault.root)


def readiness(engine: Engine, kind: str, fields: dict[str, Any]) -> list[str]:
    """Required fields the note would still be missing (Bottom Line and What It
    Solves are decided at review)."""
    required = [f for f, r in engine.index.model.fields_for("source", kind).items()
                if r == "required"]
    automatic = {"type", "kind", "title", "canonical_url", "status", "primary_topic",
                 "captured_at"}
    return [f for f in required if f not in automatic and fields.get(f) in (None, "", [])]


def _quarantine(vault: Vault, ref: str, stage: str, reason: str) -> IntakeResult:
    folder = vault.work("quarantine") / "intake"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{hashlib.sha256(ref.encode()).hexdigest()[:12]}.json"
    (folder / name).write_text(json.dumps({"ref": ref, "stage": stage, "reason": reason,
                                           "at": now_iso()}, ensure_ascii=False, indent=1),
                               encoding="utf-8")
    return IntakeResult(ref, "quarantined", detail=f"{stage}: {reason}")


# ------------------------------------------------------------------ the queue

def queue_path(vault: Vault) -> Path:
    return vault.work("queue") / "sources.jsonl"


def enqueue(vault: Vault, ref: str, note: str = "", logged_by: str = "") -> dict[str, Any]:
    entry = {"ref": ref.strip(), "note": note, "logged_by": logged_by, "at": now_iso()}
    path = queue_path(vault)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def pending(vault: Vault) -> list[dict[str, Any]]:
    path = queue_path(vault)
    if not path.exists():
        return []
    entries = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
               if line.strip()]
    done = {e["ref"] for e in entries if e.get("done")}
    seen: set[str] = set()
    out = []
    for e in entries:
        if not e.get("done") and e["ref"] not in done and e["ref"] not in seen:
            seen.add(e["ref"])
            out.append(e)
    return out


def mark_done(vault: Vault, ref: str, outcome: str) -> None:
    with queue_path(vault).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ref": ref, "done": True, "outcome": outcome,
                                 "at": now_iso()}) + "\n")
