"""Scouting: finding candidates nobody named, and ordering them honestly.

V1's `scout/` method, kept; its separate pipeline, dropped. Discovery and
ranking are the first stage of the one intake pipeline.

- **Domain register** (`About/Domain Register.md`): the closed list of domains
  with their seed queries. The scout may report a candidate `unmatched`; it
  may never invent a domain (`NO_SCHEMA_DRIFT`).
- **Discovery**, deterministic and model-free: GitHub search on seed queries,
  and **container expansion**, reading the curated lists already catalogued
  (their own annotations become the candidate's description; the curator
  wrote them, and they are better evidence than anything invented).
- **Ranking**: six weighted signals, every component stored, so any position
  can be explained. It reorders work; it never selects it.
- **The adjudication audit** (`LOCATE_DO_NOT_ADJUDICATE`): vitality, adoption
  and reusability are scaled by `usage.catalogue_role` and
  `usage.distribution_posture`. An archived, unstarred or unlicensed source is
  lowered at most, never removed.
- **Cohorts**: a batch frozen and written to a visible note before deep work.
- **Gates for an unattended sweep**: retrieval must have passed its own eval,
  and a person must have read the previous cohort.

Candidates live in `.librarian/scout/candidates.jsonl` (tracked working state).
"""
from __future__ import annotations

import json
import math
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import notes
from .facts import license_class
from .intake import ATOM, Fetcher, FetchError
from .rules import Refusal
from .vault import Vault, now_iso

GITHUB_URL = re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)")
MD_LINK = re.compile(r"\[([^\]]{1,120})\]\((https?://[^\s)]+)\)")
DEFAULT_WEIGHTS = {"gap_fit": 30.0, "corroboration": 20.0, "vitality": 15.0,
                   "reusability": 15.0, "adoption": 10.0, "depth": 10.0}
GAP_TARGET = 10


# ------------------------------------------------------------ the register

@dataclass(frozen=True)
class Domain:
    name: str
    seeds: tuple[str, ...]
    boundary: str = ""
    sensitive: bool = False


def domains(vault: Vault) -> list[Domain]:
    path = vault.root / "About" / "Domain Register.md"
    if not path.exists():
        return []
    body = notes.load(path).body
    out = []
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2 or not line.strip().startswith("|") or cells[0] in ("Domain", "") \
                or set(cells[0]) <= set("-: "):
            continue
        seeds = tuple(q.strip().strip("`") for q in re.split(r"[;,]", cells[1]) if q.strip())
        out.append(Domain(cells[0], seeds, cells[2] if len(cells) > 2 else "",
                          len(cells) > 3 and cells[3].lower() in ("yes", "y", "true")))
    return out


# ---------------------------------------------------------------- signals

# V1's integration floors were 0.0 for archived and unstarred, and the
# distributed scale 0.0 for an unknown licence. Together they zeroed a
# candidate, which the plan's audit forbids: a signal may lower a source, never
# remove it (LOCATE_DO_NOT_ADJUDICATE). The floors below are the smallest
# non-zero values; everything else is V1's, as measured.
FLOOR = 0.05
VITALITY_FLOORS = {
    "integration": {"archived": FLOOR, "unknown": 0.2, "stale": 0.1, "ageing": 0.3},
    "reference": {"archived": 0.55, "unknown": 0.45, "stale": 0.4, "ageing": 0.55},
}
REUSABILITY_SCALES = {
    "distributed": {"Permissive": 1.0, "Weak_Copyleft": 0.67, "Copyleft": 0.33,
                    "Source_Available": 0.1, "Unknown": FLOOR},
    "private": {"Permissive": 1.0, "Weak_Copyleft": 0.95, "Copyleft": 0.90,
                "Source_Available": 0.80, "Unknown": 0.85},
}
ADOPTION_FLOORS = {"integration": FLOOR, "reference": 0.35}


def gap_fit(held: int, target: int = GAP_TARGET) -> float:
    """Highest where the vault is thinnest; stops attracting work once full."""
    return 0.0 if held >= target else round(1.0 - max(0, held) / target, 4)


def corroboration(times_seen: int) -> float:
    return {0: 0.0, 1: 0.0, 2: 0.6, 3: 0.85}.get(times_seen, 1.0)


def vitality(pushed_at: str, archived: bool, role: str, now: datetime | None = None) -> float:
    floors = VITALITY_FLOORS[role]
    if archived:
        return floors["archived"]
    try:
        stamp = datetime.fromisoformat(str(pushed_at).replace("Z", "+00:00"))
    except ValueError:
        return floors["unknown"]
    days = ((now or datetime.now(timezone.utc)) - stamp).days
    for limit, score in ((30, 1.0), (90, 0.85), (365, 0.6)):
        if days <= limit:
            return score
    return floors["ageing"] if days <= 730 else floors["stale"]


def reusability(spdx: str, posture: str) -> float:
    return REUSABILITY_SCALES[posture][license_class(spdx)]


def adoption(stars: int, role: str) -> float:
    floor = ADOPTION_FLOORS[role]
    n = max(0, int(stars or 0))
    return floor if n <= 0 else round(max(floor, min(1.0, math.log10(n + 1) / 5.0)), 4)


def depth(description: str, topics: list[str], size_kb: int) -> float:
    """What discovery can see without fetching: a described, topic-tagged,
    non-trivial repository is likelier to repay a read."""
    score = 0.35 if len(description or "") >= 40 else 0.1 if description else 0.0
    score += 0.25 if topics else 0.0
    score += 0.4 if size_kb >= 500 else 0.2 if size_kb >= 50 else 0.0
    return round(min(1.0, score), 4)


def score(candidate: dict[str, Any], held: int, role: str, posture: str,
          weights: dict[str, float] | None = None) -> tuple[float, list[dict[str, Any]]]:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    gh = candidate.get("github") or {}
    signals = [
        ("gap_fit", gap_fit(held), f"{held} already held in {candidate.get('domain') or 'unmatched'}"),
        ("corroboration", corroboration(int(candidate.get("times_seen") or 1)),
         f"seen {candidate.get('times_seen') or 1}x"),
        ("vitality", vitality(gh.get("pushed_at", ""), bool(gh.get("archived")), role),
         f"pushed {gh.get('pushed_at') or 'unknown'}" + (", archived" if gh.get("archived") else "")),
        ("reusability", reusability(gh.get("license_spdx", ""), posture),
         f"licence {gh.get('license_spdx') or 'unknown'} under a {posture} posture"),
        ("adoption", adoption(gh.get("stars", 0), role), f"{gh.get('stars') or 0} stars"),
        ("depth", depth(candidate.get("description", ""), gh.get("topics") or [],
                        int(gh.get("size_kb") or 0)), f"{gh.get('size_kb') or 0} KB"),
    ]
    rows = [{"signal": n, "value": v, "weight": w[n], "points": round(v * w[n], 3),
             "detail": d} for n, v, d in signals]
    return round(sum(r["points"] for r in rows), 3), rows


def audit(role: str, posture: str) -> dict[str, float]:
    """The adjudication audit, as numbers: what an archived, unstarred,
    unlicensed candidate scores under this vault's role and posture. Never 0."""
    worst = {"github": {"archived": True, "stars": 0, "license_spdx": "", "pushed_at": ""},
             "times_seen": 1, "description": ""}
    total, rows = score(worst, GAP_TARGET, role, posture)
    adjudicated = {r["signal"]: r["value"] for r in rows
                   if r["signal"] in ("vitality", "reusability", "adoption")}
    return {"total": total, **adjudicated}


# ------------------------------------------------------------- the store

class CandidateStore:
    def __init__(self, vault: Vault):
        self.vault = vault
        self.folder = vault.librarian / "scout"
        self.path = self.folder / "candidates.jsonl"

    def all(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    out[row["key"]] = {**out.get(row["key"], {}), **row}
        return out

    def write(self, row: dict[str, Any]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    def add(self, key: str, url: str, description: str, found_via: str, domain: str = "",
            github: dict[str, Any] | None = None) -> bool:
        """True when new; a repeat sighting raises corroboration instead."""
        current = self.all().get(key)
        if current:
            vias = set(current.get("found_via") or [])
            if found_via in vias:
                return False
            self.write({"key": key, "times_seen": int(current.get("times_seen") or 1) + 1,
                        "found_via": sorted(vias | {found_via})})
            return False
        self.write({"key": key, "url": url, "description": description,
                    "found_via": [found_via], "domain": domain, "times_seen": 1,
                    "github": github or {}, "status": "new", "at": now_iso()})
        return True


def _github_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {"full_name": item.get("full_name", ""), "description": item.get("description") or "",
            "language": item.get("language") or "",
            "license_spdx": (item.get("license") or {}).get("spdx_id") or "",
            "topics": item.get("topics") or [], "archived": bool(item.get("archived")),
            "stars": int(item.get("stargazers_count") or 0),
            "pushed_at": item.get("pushed_at") or "", "size_kb": int(item.get("size") or 0)}


def search_github(query: str, fetcher: Fetcher, per_page: int = 15) -> list[dict[str, Any]]:
    url = (f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}"
           f"&sort=stars&order=desc&per_page={per_page}")
    return list(json.loads(fetcher.get(url)).get("items") or [])


def search_arxiv(query: str, fetcher: Fetcher, limit: int = 10) -> list[dict[str, Any]]:
    url = (f"https://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}"
           f"&max_results={limit}")
    root = ET.fromstring(fetcher.get(url))
    out = []
    for entry in root.findall("a:entry", ATOM):
        ident = (entry.findtext("a:id", "", ATOM) or "").rsplit("/", 1)[-1].split("v")[0]
        out.append({"ref": f"arXiv:{ident}", "title": " ".join(
            entry.findtext("a:title", "", ATOM).split()),
            "description": " ".join(entry.findtext("a:summary", "", ATOM).split())[:300]})
    return out


def discover(vault: Vault, fetcher: Fetcher, domain: str = "", per_query: int = 15
             ) -> dict[str, Any]:
    """Run the register's seed queries (one domain, or all) into candidates."""
    store = CandidateStore(vault)
    held = _held_keys(vault)
    report: dict[str, Any] = {"added": 0, "corroborated": 0, "already_held": 0, "errors": []}
    chosen = [d for d in domains(vault) if not domain or d.name == domain]
    if not chosen:
        raise TypeError(f"no domain {domain!r} in About/Domain Register.md" if domain else
                        "the domain register is empty: add a domain with seed queries")
    for d in chosen:
        for query in d.seeds:
            try:
                items = search_github(query, fetcher, per_query)
            except (FetchError, ValueError) as exc:
                report["errors"].append(f"{query}: {exc}")
                continue
            for item in items:
                key = item.get("full_name", "")
                if not key:
                    continue
                if key.lower() in held:
                    report["already_held"] += 1
                    continue
                if store.add(key, item.get("html_url", ""), item.get("description") or "",
                             f"search:{query}", d.name, _github_payload(item)):
                    report["added"] += 1
                else:
                    report["corroborated"] += 1
    return report


def expand_containers(vault: Vault, fetcher: Fetcher) -> dict[str, Any]:
    """Read every catalogued curated list (`container: true`) not yet
    expanded, from its recorded readme when there is one."""
    from .evidence import EvidenceStore
    store = CandidateStore(vault)
    held = _held_keys(vault)
    report: dict[str, Any] = {"containers": 0, "added": 0, "corroborated": 0}
    records = {}
    for record in EvidenceStore(vault).iter("readme"):
        records[record.source] = record.payload.get("text", "")
    for path in sorted((vault.root / "Sources").rglob("*.md")):
        note = notes.load(path)
        fm = note.frontmatter
        if not fm.get("container") or fm.get("expansion_status") == "complete":
            continue
        repo = str(fm.get("repo_key") or "")
        readme = records.get(f"https://api.github.com/repos/{repo}/readme", "")
        if not readme and repo:
            try:
                readme = fetcher.get(f"https://api.github.com/repos/{repo}/readme",
                                     "application/vnd.github.raw").decode("utf-8", "replace")
            except FetchError:
                continue
        report["containers"] += 1
        for label, url in MD_LINK.findall(readme):
            match = GITHUB_URL.match(url)
            if not match:
                continue
            key = f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
            if key.lower() == repo.lower() or key.lower() in held:
                continue
            if store.add(key, f"https://github.com/{key}", label.strip(),
                         f"container:{note.name}"):
                report["added"] += 1
            else:
                report["corroborated"] += 1
    return report


def _held_keys(vault: Vault) -> set[str]:
    keys = set()
    for path in (vault.root / "Sources").rglob("*.md"):
        repo = notes.load(path).frontmatter.get("repo_key")
        if repo:
            keys.add(str(repo).lower())
    return keys


def _held_by_domain(vault: Vault) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in (vault.root / "Sources").rglob("*.md"):
        topic = str(notes.load(path).frontmatter.get("primary_topic") or "")
        counts[topic] = counts.get(topic, 0) + 1
    return counts


def rank(vault: Vault) -> list[dict[str, Any]]:
    """Score every new candidate; store the signals; return best first."""
    store = CandidateStore(vault)
    usage = vault.config().get("usage", {})
    role = str(usage.get("catalogue_role") or "reference")
    posture = str(usage.get("distribution_posture") or "private")
    weights = vault.config().get("scout", {})
    held = _held_by_domain(vault)
    ranked = []
    for key, candidate in store.all().items():
        if candidate.get("status") != "new":
            continue
        total, signals = score(candidate, held.get(candidate.get("domain", ""), 0), role,
                               posture, {k: float(v) for k, v in weights.items()
                                         if k in DEFAULT_WEIGHTS})
        ranked.append({"key": key, "score": total, "signals": signals,
                       "description": candidate.get("description", ""),
                       "domain": candidate.get("domain", ""),
                       "found_via": candidate.get("found_via", [])})
    ranked.sort(key=lambda r: (-r["score"], r["key"]))
    return ranked


# ---------------------------------------------------------------- cohorts

def cohort_folder(vault: Vault) -> Path:
    return vault.librarian / "scout" / "cohorts"


def cohorts(vault: Vault) -> list[dict[str, Any]]:
    folder = cohort_folder(vault)
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))] \
        if folder.is_dir() else []


def freeze_cohort(vault: Vault, size: int = 20) -> dict[str, Any]:
    """The top `size` new candidates, frozen, written to a visible note."""
    ranked = rank(vault)[:size]
    if not ranked:
        raise TypeError("no new candidates to freeze: run discovery first")
    number = len(cohorts(vault)) + 1
    cohort = {"id": f"cohort-{number:03d}", "frozen_at": now_iso(), "reviewed_by": "",
              "members": [{"key": r["key"], "score": r["score"], "domain": r["domain"],
                           "description": r["description"], "signals": r["signals"],
                           "outcome": ""} for r in ranked]}
    folder = cohort_folder(vault)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{cohort['id']}.json").write_text(json.dumps(cohort, indent=1,
                                                            ensure_ascii=False), encoding="utf-8")
    store = CandidateStore(vault)
    for r in ranked:
        store.write({"key": r["key"], "status": cohort["id"]})
    rows = "\n".join(f"| {i} | [{m['key']}](https://github.com/{m['key']}) | {m['score']:.1f} | "
                     f"{m['domain'] or 'unmatched'} | "
                     f"{' '.join(str(m['description']).split())[:90].replace('|', '/')} |"
                     for i, m in enumerate(cohort["members"], 1))
    note = vault.root / "Indexes" / "Cohorts" / f"{cohort['id']}.md"
    note.parent.mkdir(parents=True, exist_ok=True)
    note.write_text(notes.render(
        {"type": "index", "status": "active", "generated": True, "cohort": cohort["id"]},
        notes.compose(f"Cohort {number:03d}", [
            ("About This Cohort", "Frozen before any deep work, so the batch that was chosen "
                                  "is the batch that is reviewed. Scores are arithmetic over "
                                  "stored signals; they order the work and select nothing. "
                                  "A person reads this cohort before the next one runs."),
            ("Members", "| # | Candidate | Score | Domain | Its own description |\n"
                        "| --- | --- | --- | --- | --- |\n" + rows)])), encoding="utf-8")
    return {"cohort": cohort["id"], "members": len(ranked),
            "note": note.relative_to(vault.root).as_posix()}


def mark_reviewed(vault: Vault, cohort_id: str, by: str) -> dict[str, Any]:
    path = cohort_folder(vault) / f"{cohort_id}.json"
    if not path.exists():
        raise TypeError(f"no cohort {cohort_id!r}")
    cohort = json.loads(path.read_text(encoding="utf-8"))
    cohort["reviewed_by"], cohort["reviewed_at"] = by, now_iso()
    path.write_text(json.dumps(cohort, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"cohort": cohort_id, "reviewed_by": by}


def sweep_gate(vault: Vault) -> None:
    """Refuse an unattended sweep until retrieval has passed its eval and a
    person has read the last cohort."""
    minimum = float((vault.config().get("scout") or {}).get("sweep_min_hit", 0.8))
    last = vault.work("eval") / "last.json"
    if not last.exists():
        raise Refusal("SWEEP_GATED", "retrieval has not been evaluated on this vault: write "
                                     "questions in .librarian/eval/ and run `evaluate` first")
    result = json.loads(last.read_text(encoding="utf-8"))
    hit = float(result.get("hit") or 0.0)
    if result.get("total", 0) < 5 or hit < minimum:
        raise Refusal("SWEEP_GATED", f"retrieval eval hit@5 is {hit:.2f} over "
                                     f"{result.get('total', 0)} question(s); a sweep needs at "
                                     f"least {minimum:.2f} over five or more")
    unread = [c["id"] for c in cohorts(vault) if not c.get("reviewed_by")]
    if unread:
        raise Refusal("SWEEP_GATED", f"cohort {unread[0]} has not been read by a person "
                                     f"(cohort_reviewed marks it)")


def sweep(vault: Vault, engine: Any, endpoint: Any, fetcher: Fetcher,
          limit: int = 10) -> dict[str, Any]:
    """Ingest the next members of the latest reviewed-or-current cohort, up to
    `limit`. Stages only; promotion stays with review. Stops early after
    `sweep_stop_after` consecutive members that bring nothing new (already
    held, or failed), a diminishing-returns rule in asreview's spirit."""
    from .intake import ingest
    sweep_gate(vault)
    stop_after = int((vault.config().get("scout") or {}).get("sweep_stop_after", 10))
    current = next((c for c in reversed(cohorts(vault))
                    if any(not m["outcome"] for m in c["members"])), None)
    if current is None:
        raise TypeError("every frozen cohort has been swept: freeze the next one")
    report: dict[str, Any] = {"cohort": current["id"], "results": [], "stopped": ""}
    barren = 0
    for member in [m for m in current["members"] if not m["outcome"]][:limit]:
        result = ingest(vault, engine, member["key"], endpoint=endpoint, fetcher=fetcher)
        member["outcome"] = result.status
        report["results"].append(result.to_dict())
        barren = barren + 1 if result.status in ("already_held", "quarantined") else 0
        if barren >= stop_after:
            report["stopped"] = (f"{barren} consecutive candidates brought nothing new: this "
                                 f"vein looks exhausted")
            break
    (cohort_folder(vault) / f"{current['id']}.json").write_text(
        json.dumps(current, indent=1, ensure_ascii=False), encoding="utf-8")
    report["staged"] = sum(1 for r in report["results"] if r["status"] == "staged")
    return report
