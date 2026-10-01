"""Repository components and dataset access points: two grains beneath a source note
(Search Methods SM-2, SM-3; plan P5.3).

**Components.** A query can ask not only "which source?" but "where inside it?". Each
repository's surveyed paths (its file tree, module and entry-point addresses, from intake's
evidence) are kept in the index's `component` table, bound to the revision they were read at,
rebuilt whenever the note is. A search returns at most three address-level hits under each
parent source that survived the constraints - never on their own, so paths do not swamp
sources. Matching is whole-segment (a directory or file name, or a part of one split on
`-`, `_`, `.`), terms under three letters are ignored, and a segment found in a quarter or
more of the surveyed repositories, and in at least three (`src`, `test`, `docs`), says
nothing and is skipped.

**Access points.** A dataset's recorded endpoints and files, with when each was last checked
and whether it answered - kept apart from relevance: a good search hit is not proof that a
URL still works (V1's `data` answer). Checks are evidence records (`access_check`).
"""
from __future__ import annotations

import re
import urllib.error
import urllib.request
from typing import Any, Sequence

from .evidence import EvidenceStore
from .index import fold
from .vault import Vault, now_iso

MIN_TERM = 3
PER_SOURCE = 3
PER_ANSWER = 6
COMMON_SHARE = 0.25


def segments(address: str) -> set[str]:
    out: set[str] = set()
    for part in fold(address).strip("/").split("/"):
        stem = part.rsplit(".", 1)[0] if "." in part[1:] else part
        out.add(stem)
        out.update(p for p in re.split(r"[-_.]", stem) if p)
    return {s for s in out if s}


def addresses(vault: Vault, fm: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(address, revision, evidence id) for a repository note, from its evidence."""
    store = EvidenceStore(vault)
    out: list[tuple[str, str, str]] = []
    for ref in fm.get("evidence") or []:
        record = store.get(str(ref))
        if record is None:
            continue
        revision = str(record.payload.get("tree_sha") or fm.get("pushed_at") or
                       record.fetched_at)[:40]
        if record.kind == "survey":
            out += [(str(p), revision, record.id) for p in record.payload.get("paths") or []]
        elif record.kind == "code_structure":
            out += [(str(m), revision, record.id) for m in record.payload.get("modules") or []
                    if isinstance(m, str)]
        elif record.kind == "access_point":
            for key in ("entry_points", "routes", "mcp_server_files"):
                out += [(str(a), revision, record.id) for a in record.payload.get(key) or []
                        if isinstance(a, str)]
    seen: set[str] = set()
    return [a for a in out if not (a[0] in seen or seen.add(a[0]))][:2000]


def find(conn, terms: Sequence[str], parents: Sequence[str]) -> dict[str, list[dict]]:
    """Address-level hits under the given parent sources, capped."""
    wanted = [fold(t) for t in terms if len(t) >= MIN_TERM]
    if not wanted or not parents:
        return {}
    repos = conn.execute("SELECT COUNT(DISTINCT note) FROM component").fetchone()[0] or 0
    common: set[str] = set()
    if repos >= 4:
        where: dict[str, set[str]] = {}
        for row in conn.execute("SELECT note, address FROM component"):
            for seg in segments(row["address"]):
                if seg in wanted:
                    where.setdefault(seg, set()).add(row["note"])
        # a quarter of them, and never fewer than three: in a small library two repositories
        # sharing a word is not what makes a word uninformative
        common = {seg for seg, notes in where.items()
                  if len(notes) >= max(3, repos * COMMON_SHARE)}
    useful = [t for t in wanted if t not in common]
    if not useful:
        return {}
    rows = conn.execute(f"SELECT note, address, revision FROM component WHERE note IN "
                        f"({','.join('?' for _ in parents)})", list(parents)).fetchall()
    hits: dict[str, list[dict]] = {}
    for row in rows:
        matched = [t for t in useful if t in segments(row["address"])]
        if matched:
            hits.setdefault(row["note"], []).append(
                {"address": row["address"], "matched": matched, "revision": row["revision"]})
    out: dict[str, list[dict]] = {}
    total = 0
    for note in parents:
        ranked = sorted(hits.get(note, []), key=lambda h: (-len(h["matched"]), len(h["address"])))
        take = ranked[:min(PER_SOURCE, PER_ANSWER - total)]
        if take:
            out[note] = take
            total += len(take)
        if total >= PER_ANSWER:
            break
    return out


# ------------------------------------------------------------------ access points

def checks(vault: Vault) -> dict[str, dict[str, Any]]:
    """The latest check of each access point URL."""
    latest: dict[str, dict[str, Any]] = {}
    for record in EvidenceStore(vault).iter("access_check"):
        url = str(record.payload.get("url", ""))
        if url and (url not in latest or record.fetched_at > latest[url]["checked_at"]):
            latest[url] = {**record.payload, "checked_at": record.fetched_at}
    return latest


def with_status(vault: Vault, urls: Sequence[str], known: dict | None = None) -> list[dict]:
    known = checks(vault) if known is None else known
    return [{"url": u, **({"reachable": known[u].get("reachable"),
                           "status": known[u].get("status"),
                           "checked_at": known[u]["checked_at"]}
                          if u in known else {"checked_at": "never"})} for u in urls]


def check(vault: Vault, url: str, fetcher: Any = None, timeout: float = 20) -> dict[str, Any]:
    """Does the endpoint answer? A HEAD request (a data file is not downloaded), recorded."""
    try:
        if fetcher is not None:
            fetcher.get(url)
            status = "200"
        else:
            request = urllib.request.Request(url, method="HEAD",
                                             headers={"User-Agent": "resource-librarian/2"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status = str(response.status)
        reachable = True
    except urllib.error.HTTPError as exc:
        reachable, status = exc.code in (401, 403, 405), str(exc.code)   # there, but guarded
    except Exception as exc:                                  # noqa: BLE001 - any failure
        reachable, status = False, f"{type(exc).__name__}: {str(exc)[:120]}"
    record = EvidenceStore(vault).put("access_check", url, {"url": url, "reachable": reachable,
                                                            "status": status},
                                      fetched_at=now_iso())
    return {"url": url, "reachable": reachable, "status": status,
            "checked_at": record.fetched_at}
