"""Search: filters, then names, text and coverage (and vectors when enabled),
fused by Reciprocal Rank Fusion, returned in one envelope.

This is V1's `consult` engine carried over with its measured lessons intact and
its catalogue-specific parts removed: the filterable axes, the claim and caveat
sections and the answerable shapes all come from the vault's content model, so
a stranger's vault with different axes searches the same way.

The rules it keeps (each one was a V1 bug before it was a rule):

- **Constraints eliminate** (`CONSTRAINTS_ELIMINATE`). A filter removes
  candidates before ranking; a value outside the axis is refused, not matched
  against nothing; a source with no value for a filtered axis is removed,
  because "unknown" does not answer "runs on a laptop".
- **Every result says why** (`EVERY_RESULT_SAYS_WHY`), assembled from what
  matched and which filters passed, never generated.
- **No generative model on the read path** (`READS_NEVER_CALL_A_GENERATIVE_MODEL`).
- **Selectivity is measured, over what can be an answer.** A query term in
  half or more of the answerable notes discriminates nothing and earns no
  coverage credit. The denominator is the answerable notes, not the vault.
- **A name hit must qualify.** One incidental query word inside a long note
  name is a coincidence, not evidence.
- **One entry per note per ranking.** Summing a note's chunks rewards verbose
  notes.
- **Caveats are searchable but earn no coverage credit.** A term matched in
  `Reading Notes` is often the sentence refuting it.
- **Rank is a position; the verdict is the confidence.** Both arrive together.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .index import Index

INTENTS = ("orient", "donor", "pattern", "technique", "data", "precedent", "in_text")

STOPWORDS = frozenset("""
a an and are as at be but by can could do does for from get give has have how i
if in into is it its me my need not of on or should so than that the their then
there these they this to use used using want was what when where which who why
will with without would you your our we us e.g eg i.e ie etc also any some such
""".split())

TOKEN = re.compile(r'"[^"]+"|[A-Za-z0-9_.+#-]{2,}')

NAME_SHORT_QUERY = 2
NAME_MIN_QUERY_COVERAGE = 0.5
NAME_MIN_NAME_COVERAGE = 0.5

COVERED, THIN, UNCOVERED = "covered", "thin", "uncovered"


class ConstraintError(TypeError):
    """A constraint that cannot be applied. A `TypeError` so the registry
    reports it as invalid arguments, with the permitted values."""


# ---------------------------------------------------------------- envelope

@dataclass(frozen=True)
class Result:
    kind: str                 # source | concept | topic | application | offering | section | page
    name: str
    why: str
    rank: float               # a position, 1.0 for the best in this response; not a quality
    fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "name": self.name, "why": self.why,
                "rank": round(self.rank, 4), "fields": self.fields}


@dataclass
class Response:
    intent: str
    results: list[Result] = field(default_factory=list)
    verdict: str = ""
    coverage: dict[str, Any] = field(default_factory=dict)
    facets: dict[str, list[dict]] = field(default_factory=dict)
    considered: int = 0
    matched: int = 0
    filtered_out: int = 0
    constraints: dict[str, list[str]] = field(default_factory=dict)
    advisories: list[str] = field(default_factory=list)
    tier_reached: int = 1          # 1 names, 2 metadata, 3 text
    next_step: str = ""
    partial: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"intent": self.intent, "verdict": self.verdict, "coverage": self.coverage,
                "results": [r.to_dict() for r in self.results], "facets": self.facets,
                "considered": self.considered, "matched": self.matched,
                "filtered_out": self.filtered_out, "constraints": self.constraints,
                "advisories": self.advisories, "tier_reached": self.tier_reached,
                "next_step": self.next_step, "partial": self.partial, "notes": self.notes}


@dataclass(frozen=True)
class Hit:
    note: str
    heading: str
    role: str
    excerpt: str
    matched: tuple[str, ...]
    rank: int


# ------------------------------------------------------------------- terms

def terms_from(text: str) -> list[str]:
    """Query text to terms. A quoted phrase stays one term."""
    out: list[str] = []
    seen: set[str] = set()
    for match in TOKEN.findall(text or ""):
        token = match.strip('"').strip().strip(".")
        low = token.lower()
        if len(token) < 2 or low in seen or (low in STOPWORDS and " " not in token):
            continue
        seen.add(low)
        out.append(token)
    return out


def _fts_query(terms: Sequence[str]) -> str:
    return " OR ".join('"' + t.replace('"', "") + '"' for t in terms if t.strip())


def _matched(text: str, terms: Sequence[str]) -> tuple[str, ...]:
    low = text.lower()
    return tuple(t for t in terms if t.lower() in low)


def _matched_bounded(text: str, terms: Sequence[str]) -> tuple[str, ...]:
    """Whole-token matches only: names are short, so a substring inside an
    unrelated word is a large share of the evidence rather than noise."""
    low = text.lower()
    return tuple(t for t in terms
                 if re.search(rf"(?<![a-z0-9]){re.escape(t.lower())}(?![a-z0-9])", low))


def _excerpt(text: str, terms: Sequence[str], width: int = 220) -> str:
    flat = " ".join((text or "").split())
    low = flat.lower()
    for term in terms:
        at = low.find(term.lower())
        if at >= 0:
            start = max(0, at - width // 3)
            return ("..." if start else "") + flat[start:start + width].strip() + \
                ("..." if start + width < len(flat) else "")
    return flat[:width]


def rrf(rankings: Sequence[Sequence[str]], weights: Sequence[float], k: int) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking, weight in zip(rankings, weights):
        for position, name in enumerate(ranking, 1):
            scores[name] = scores.get(name, 0.0) + weight / (k + position)
    return scores


def _first_per_note(hits: Iterable[Hit]) -> list[str]:
    seen: set[str] = set()
    return [h.note for h in hits if not (h.note in seen or seen.add(h.note))]


# -------------------------------------------------------------- constraints

@dataclass
class Constraints:
    values: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @classmethod
    def of(cls, raw: dict[str, Any] | None, permitted: dict[str, list[str]]) -> "Constraints":
        out: dict[str, tuple[str, ...]] = {}
        for axis, value in (raw or {}).items():
            if value in (None, "", []):
                continue
            if axis not in permitted:
                raise ConstraintError(
                    f"{axis!r} is not a filterable axis. Filterable: {sorted(permitted)}")
            values = (value,) if isinstance(value, str) else tuple(str(v) for v in value)
            allowed = permitted[axis]
            unknown = [v for v in values if allowed and v not in allowed]
            if unknown:
                raise ConstraintError(
                    f"{axis}={unknown[0]!r} is not a value of that axis. Permitted: "
                    f"{allowed}. Values are case-sensitive.")
            out[axis] = values
        return cls(out)

    def describe(self) -> str:
        return ", ".join(f"{a}={'|'.join(v)}" for a, v in self.values.items())


# ------------------------------------------------------------------ engine

class Engine:
    def __init__(self, index: Index, heuristics: dict[str, Any] | None = None,
                 vectors: Any = None):
        self.index = index
        self.h = {**_DEFAULTS, **(heuristics or {})}
        self.vectors = vectors            # an `embed.VectorSearch`, or None
        self._df: dict[tuple[str, str], float] = {}

    @property
    def conn(self):
        """The index's connection for the calling thread."""
        return self.index.conn

    def forget(self) -> None:
        """Drop per-corpus caches after the index changed."""
        self._df.clear()

    # -- vocabulary -----------------------------------------------------------
    def permitted_axes(self, shape: str = "source") -> dict[str, list[str]]:
        """Every axis a search may filter on, with its permitted values, from
        the content model; plus `kind` and `topic`, which every source has."""
        model = self.index.model
        out: dict[str, list[str]] = {"kind": sorted(model.kinds) if shape == "source" else [],
                                     "topic": []}
        kinds = sorted(model.kinds) if shape == "source" else [""]
        for kind in kinds:
            for axis, values in model.axes_for(shape, kind).items():
                if axis in ("status", "attested_by"):
                    continue
                out.setdefault(axis, [])
                out[axis] = sorted(set(out[axis]) | set(values))
        return out

    def _answerable_count(self, shapes: Sequence[str]) -> int:
        marks = ",".join("?" for _ in shapes)
        return self.conn.execute(f"SELECT COUNT(*) FROM note WHERE shape IN ({marks})",
                                 tuple(shapes)).fetchone()[0] or 1

    def document_frequency(self, term: str, shapes: Sequence[str] = ("source",)) -> float:
        key = (term.lower(), ",".join(shapes))
        if key not in self._df:
            marks = ",".join("?" for _ in shapes)
            try:
                n = self.conn.execute(
                    "SELECT COUNT(DISTINCT c.path) FROM chunk_fts "
                    "JOIN chunk c ON c.id = chunk_fts.rowid JOIN note n ON n.path = c.path "
                    f"WHERE chunk_fts MATCH ? AND c.role != 'document' AND n.shape IN ({marks})",
                    (_fts_query([term]), *shapes)).fetchone()[0]
            except sqlite3.OperationalError:
                n = 0
            self._df[key] = n / self._answerable_count(shapes)
        return self._df[key]

    def selective(self, terms: Sequence[str], shapes: Sequence[str] = ("source",)) -> frozenset[str]:
        """Terms in fewer than `selectivity_ceiling` of the answerable notes.

        Below `selectivity_min_corpus` answerable notes every term counts: in a
        vault of four sources one note is a quarter of the corpus, and a
        document frequency cannot tell a rare word from a common one. A new
        vault lives here for its first sources.
        """
        if self._answerable_count(shapes) < int(self.h["selectivity_min_corpus"]):
            return frozenset(t.lower() for t in terms)
        ceiling = float(self.h["selectivity_ceiling"])
        return frozenset(t.lower() for t in terms
                         if self.document_frequency(t, shapes) < ceiling)

    # -- the three lexical rankings -------------------------------------------
    def by_name(self, terms: Sequence[str], shapes: Sequence[str],
                selective: frozenset[str], limit: int = 30) -> list[Hit]:
        if not terms:
            return []
        clauses, params = [], []
        for term in terms:
            clauses.append("(name_lower LIKE ? OR aliases LIKE ? OR LOWER(title) LIKE ?)")
            params += [f"%{term.lower()}%"] * 3
        marks = ",".join("?" for _ in shapes)
        rows = self.conn.execute(
            f"SELECT name, title, aliases, bottom_line FROM note WHERE ({' OR '.join(clauses)}) "
            f"AND shape IN ({marks}) LIMIT 400", (*params, *shapes)).fetchall()
        candidates = []
        for row in rows:
            in_name = tuple(t for t in _matched_bounded(f"{row['name']} {row['title']}", terms)
                            if t.lower() in selective)
            where = "name"
            matched = in_name
            if not matched:
                matched = tuple(t for t in terms if t.lower() in selective
                                and t.lower() in row["aliases"].split("\n"))
                where = "alias"
            if not matched or not _name_qualifies(matched, terms, row["name"] if in_name else ""):
                continue
            candidates.append((row, matched, where))
        candidates.sort(key=lambda c: (-len(c[1]), c[2] != "name", len(c[0]["name"]),
                                       c[0]["name"]))
        return [Hit(row["name"], where, "claim", row["bottom_line"][:220], matched, i)
                for i, (row, matched, where) in enumerate(candidates[:limit], 1)]

    def lexical(self, terms: Sequence[str], shapes: Sequence[str],
                roles: Sequence[str] = ("claim", "caveat"), limit: int = 80,
                within: Sequence[str] | None = None) -> list[Hit]:
        query = _fts_query(terms)
        if not query:
            return []
        marks_s = ",".join("?" for _ in shapes)
        marks_r = ",".join("?" for _ in roles)
        sql = ("SELECT c.note AS note, c.heading AS heading, c.role AS role, c.text AS text, "
               "bm25(chunk_fts) AS score FROM chunk_fts JOIN chunk c ON c.id = chunk_fts.rowid "
               "JOIN note n ON n.path = c.path WHERE chunk_fts MATCH ? "
               f"AND n.shape IN ({marks_s}) AND c.role IN ({marks_r})")
        params: list[Any] = [query, *shapes, *roles]
        if within:
            sql += f" AND c.note IN ({','.join('?' for _ in within)})"
            params += list(within)
        sql += " ORDER BY score LIMIT ?"
        params.append(limit)
        try:
            rows = self.conn.execute(sql, params).fetchall()
        except sqlite3.OperationalError:
            return []
        return [Hit(r["note"], r["heading"], r["role"], _excerpt(r["text"], terms),
                    _matched(f"{r['heading']} {r['text']}", terms), i)
                for i, r in enumerate(rows, 1)]

    # -- fusion -------------------------------------------------------------
    def rank(self, query: str, shapes: Sequence[str] = ("source",), pool: int = 80
             ) -> tuple[dict[str, float], dict[str, Hit], frozenset[str], int, list[str]]:
        """Returns (scores, best hit per note, selective terms, tier, degraded)."""
        terms = terms_from(query)
        selective = self.selective(terms, shapes)

        def counted(hits: list[Hit]) -> list[Hit]:
            return [Hit(h.note, h.heading, h.role, h.excerpt,
                        tuple(t for t in h.matched if t.lower() in selective), h.rank)
                    for h in hits]

        name_hits = counted(self.by_name(terms, shapes, selective))
        text_hits = counted(self.lexical(terms, shapes, limit=pool))
        best: dict[str, Hit] = {}
        by_note: dict[str, Hit] = {}
        for hit in name_hits + text_hits:
            # The evidence shown for a note: a claim over a caveat, then the
            # most distinctive terms, then the better position.
            key = (hit.role == "claim", len(hit.matched), -hit.rank)
            current_best = best.get(hit.note)
            if current_best is None or key > (current_best.role == "claim",
                                              len(current_best.matched), -current_best.rank):
                best[hit.note] = hit
            if hit.role == "claim":
                current = by_note.get(hit.note)
                if current is None or len(hit.matched) > len(current.matched):
                    by_note[hit.note] = hit
        coverage = self._coverage(name_hits + text_hits, by_note)
        rankings = [_first_per_note(name_hits), _first_per_note(text_hits), coverage]
        weights = [float(self.h["name_weight"]), 1.0, float(self.h["coverage_weight"])]
        degraded: list[str] = []
        tier = 3 if text_hits else 1
        if self.vectors is not None:
            ordered, reason = self.vectors.search(query, shapes=shapes, limit=pool)
            if reason:
                degraded.append(reason)
            elif ordered:
                rankings.append(ordered)
                weights.append(float(self.h["vector_weight"]))
                for position, name in enumerate(ordered, 1):
                    best.setdefault(name, Hit(name, "", "claim", "", (), position))
                tier = 3
        scores = rrf(rankings, weights, int(self.h["rrf_k"]))
        top = max(scores.values(), default=1.0) or 1.0
        return {n: s / top for n, s in scores.items()}, best, selective, tier, degraded

    def _coverage(self, hits: list[Hit], by_note: dict[str, Hit]) -> list[str]:
        """How much of the query each note accounts for, in its claim sections.

        `bm25` (V1's measured default): each note's single chunk with the most
        distinctive terms, ordered by that chunk's text rank. `union`: the
        distinct distinctive terms a note matches across all its claim
        sections, most first, ties by best rank; a note whose description
        spreads the query over two sections is not penalised for it. Chosen by
        `coverage_order` and measured with `evaluate`, not assumed.
        """
        minimum = int(self.h["coverage_min_terms"])
        if self.h.get("coverage_order", "bm25") == "union":
            union: dict[str, set[str]] = {}
            first: dict[str, int] = {}
            for hit in hits:
                if hit.role != "claim":
                    continue
                union.setdefault(hit.note, set()).update(t.lower() for t in hit.matched)
                first[hit.note] = min(first.get(hit.note, hit.rank), hit.rank)
            ordered = sorted(union, key=lambda n: (-len(union[n]), first[n]))
            return [n for n in ordered if len(union[n]) >= minimum]
        covered = sorted(by_note.values(), key=lambda h: (h.rank, -len(h.matched)))
        return [h.note for h in covered if len(h.matched) >= minimum]

    # -- filters ------------------------------------------------------------
    def eligible(self, bounds: Constraints, shapes: Sequence[str] = ("source",),
                 any_of: Sequence[str] | None = None) -> tuple[set[str], int]:
        """Survivors of the constraints, and how many they removed. `any_of`
        (axis=value pairs) narrows the pool first, as the `data` intent does."""
        marks = ",".join("?" for _ in shapes)
        pool = {r["name"] for r in self.conn.execute(
            f"SELECT name FROM note WHERE shape IN ({marks})", tuple(shapes))}
        if any_of:
            shaped: set[str] = set()
            for pair in any_of:
                axis, _, value = str(pair).partition("=")
                shaped |= {r["note"] for r in self.conn.execute(
                    "SELECT DISTINCT note FROM facet WHERE axis = ? AND value = ?",
                    (axis.strip(), value.strip()))}
            pool &= shaped
        survivors = set(pool)
        for axis, values in bounds.values.items():
            rows = self.conn.execute(
                f"SELECT DISTINCT note FROM facet WHERE axis = ? AND value IN "
                f"({','.join('?' for _ in values)})", (axis, *values))
            survivors &= {r["note"] for r in rows}
        return survivors, len(pool) - len(survivors)

    def facet_counts(self, names: Iterable[str]) -> dict[str, list[dict]]:
        """Per-axis counts over the matched set. An axis with one value narrows
        nothing and is left out."""
        names = list(names)
        out: dict[str, list[dict]] = {}
        for start in range(0, len(names), 500):
            batch = names[start:start + 500]
            for row in self.conn.execute(
                    f"SELECT axis, value, COUNT(DISTINCT note) AS n FROM facet WHERE note IN "
                    f"({','.join('?' for _ in batch)}) GROUP BY axis, value", batch):
                out.setdefault(row["axis"], []).append({"value": row["value"], "count": row["n"]})
        return {axis: sorted(values, key=lambda v: (-v["count"], v["value"]))
                for axis, values in sorted(out.items()) if len(values) > 1}

    # -- verdict ------------------------------------------------------------
    def verdict(self, selective: frozenset[str], results: list[Result]) -> dict[str, Any]:
        """Absolute, where rank is relative: how much of the query the best
        answer accounts for in a claim section, and how many sources agree."""
        per = [tuple(t for t in r.fields.get("matched", []) if t.lower() in selective)
               if r.fields.get("matched_role") == "claim" else () for r in results]
        best = max(per, key=len, default=())
        account = len({t.lower() for t in best}) / len(selective) if selective else 0.0
        consensus = sum(1 for m in per if len(m) >= 2)
        strong, thin = float(self.h["strong_account"]), float(self.h["thin_account"])
        agree = int(self.h["consensus_matches"])
        if not results:
            level, reason = UNCOVERED, "no source matched at all"
        elif account >= strong and consensus >= agree:
            level = COVERED
            reason = (f"the best answer accounts for {len(best)} of {len(selective)} "
                      f"distinctive terms, and {consensus} sources agree")
        elif account >= strong or (account >= thin and consensus >= agree):
            level = THIN
            reason = (f"the best answer accounts for {len(best)} of {len(selective)} "
                      f"distinctive terms, with {consensus} corroborating source(s)")
        else:
            level = UNCOVERED
            reason = (f"the best answer accounts for {len(best)} of {len(selective)} "
                      f"distinctive terms in a claim section")
        sentence = {COVERED: f"covered - {reason}",
                    THIN: f"thin coverage - {reason}; treat these as leads, not answers",
                    UNCOVERED: f"nothing here covers this - {reason}"}[level]
        return {"level": level, "account": round(account, 3), "consensus": consensus,
                "distinctive_terms": sorted(selective), "best_matched": list(best),
                "sentence": sentence}


_DEFAULTS: dict[str, Any] = {
    "selectivity_ceiling": 0.5, "selectivity_min_corpus": 20, "rrf_k": 60, "name_weight": 1.2, "coverage_weight": 1.0,
    "vector_weight": 1.0, "coverage_min_terms": 2, "strong_account": 0.34,
    "thin_account": 0.10, "consensus_matches": 2, "coverage_order": "union",
}


def _name_qualifies(matched: Sequence[str], terms: Sequence[str], name: str) -> bool:
    if not matched or not terms:
        return False
    if len(terms) <= NAME_SHORT_QUERY or len(matched) >= 2:
        return True
    if len(matched) / len(terms) >= NAME_MIN_QUERY_COVERAGE:
        return True
    flat = "".join(ch for ch in name.lower() if ch.isalnum())
    return bool(flat) and any(
        len("".join(ch for ch in t.lower() if ch.isalnum())) / len(flat) >= NAME_MIN_NAME_COVERAGE
        for t in matched)


def _why(hit: Hit | None, described: str, extra: str = "") -> str:
    parts = []
    if hit and hit.matched:
        where = {"name": "its name", "alias": "an alias"}.get(hit.heading) or \
            (f"`{hit.heading}`" if hit.heading else "its text")
        terms = ", ".join(f"'{t}'" for t in hit.matched)
        parts.append(f"matched {terms} in {where}" +
                     (" (a caveat, not a claim)" if hit.role == "caveat" else ""))
    elif hit and hit.heading == "" and not hit.matched:
        parts.append("close in meaning (vector match; no query word appears)")
    if described:
        parts.append(f"passes {described}")
    if extra:
        parts.append(extra)
    return "; ".join(parts) or "listed without a term match"


def _source_fields(engine: Engine, name: str, hit: Hit | None) -> dict[str, Any]:
    row = engine.index.note_row(name)
    fields: dict[str, Any] = {"matched": list(hit.matched) if hit else [],
                              "matched_in": hit.heading if hit else "",
                              "matched_role": hit.role if hit else ""}
    if row is None:
        return fields
    fm = json.loads(row["frontmatter"])
    fields.update({"kind": row["kind"], "title": row["title"], "topic": row["topic"],
                   "bottom_line": row["bottom_line"][:300], "path": row["path"]})
    for key in ("canonical_url", "license_class", "status"):
        if fm.get(key):
            fields[key] = fm[key]
    return fields


# ----------------------------------------------------------------- intents

def search(engine: Engine, query: str, intent: str = "donor",
           constraints: dict[str, Any] | None = None, limit: int = 10,
           source: str = "") -> Response:
    if intent not in INTENTS:
        raise ConstraintError(f"intent {intent!r} is not one of {INTENTS}")
    if intent == "in_text":
        return _in_text(engine, query, limit, source)
    if intent == "technique":
        return _technique(engine, query, limit, source)
    shapes = {"donor": ("source",), "data": ("source",), "orient": ("source",),
              "pattern": ("concept",), "precedent": ("application",)}[intent]
    data_shaped = list(engine.h.get("data_shaped") or ["kind=dataset"]) \
        if intent == "data" else None
    bounds = Constraints.of(constraints, engine.permitted_axes(shapes[0])) \
        if shapes == ("source",) else Constraints()
    scores, best, selective, tier, degraded = engine.rank(query, shapes)
    survivors, eliminated = engine.eligible(bounds, shapes, data_shaped)
    kept = {n: s for n, s in scores.items() if n in survivors}
    removed_best = [n for n, _ in sorted(scores.items(), key=lambda kv: -kv[1])[:3]
                    if n not in survivors]
    described = bounds.describe()
    filters_only = not kept and bool(bounds.values) and bool(survivors)
    if filters_only:
        kept = {n: 0.5 for n in sorted(survivors)}
    kind_label = {"source": "source", "concept": "concept", "application": "application"}[shapes[0]]
    ordered = sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))
    results = [Result(kind_label, name,
                      _why(best.get(name), described,
                           "no term matched; listed because it passes the constraints"
                           if filters_only else ""),
                      score, _source_fields(engine, name, best.get(name)))
               for name, score in ordered[:limit]]
    response = Response(intent=intent, results=results, considered=len(survivors) + eliminated,
                        matched=len(kept), filtered_out=eliminated,
                        constraints={a: list(v) for a, v in bounds.values.items()},
                        tier_reached=2 if filters_only or not results else tier,
                        partial=bool(degraded), notes=degraded)
    if shapes == ("source",):
        response.facets = engine.facet_counts(kept)
    verdict = engine.verdict(selective, results)
    response.verdict, response.coverage = verdict["level"], verdict
    if removed_best and bounds.values:
        response.advisories.append(
            f"{len(removed_best)} of the highest-ranked candidates were removed by your "
            f"constraints ({described}): {', '.join(removed_best)}. If nothing below fits, the "
            f"honest answer may be that nothing here fits under those constraints.")
    if intent == "data" and not survivors:
        response.advisories.append(
            f"no source here is data-shaped by this vault's setting "
            f"(search.data_shaped = {data_shaped})")
    response.advisories.append(verdict["sentence"])
    stale = engine.index.stale_reason()
    if stale:
        response.advisories.append(f"the index needs rebuilding ({stale}); run `index`")
    if intent == "orient":
        _add_orientation(engine, response, query, selective)
    response.next_step = _next_step(response, described, eliminated)
    return response


def _add_orientation(engine: Engine, response: Response, query: str,
                     selective: frozenset[str]) -> None:
    """Topics and concepts beside the sources: where the query sits in the vault."""
    topics = {}
    for result in response.results:
        topic = result.fields.get("topic")
        if topic:
            topics[topic] = topics.get(topic, 0) + 1
    concept_scores, concept_best, *_ = engine.rank(query, ("concept",), pool=30)
    extra = [Result("topic", t, f"{n} of the sources above are filed here", 0.0,
                    {"count": n}) for t, n in sorted(topics.items(), key=lambda kv: -kv[1])[:5]]
    extra += [Result("concept", n, _why(concept_best.get(n), ""), s,
                     {"matched": list(concept_best[n].matched) if n in concept_best else []})
              for n, s in sorted(concept_scores.items(), key=lambda kv: -kv[1])[:5]]
    response.results += extra


def _technique(engine: Engine, query: str, limit: int, source: str) -> Response:
    """Sections, not sources: *how* something is done, inside one source or across all."""
    terms = terms_from(query)
    selective = engine.selective(terms)
    within = [source] if source else None
    if source and engine.index.note_row(source) is None:
        raise ConstraintError(f"no note named {source!r}")
    hits = engine.lexical(terms, ("source", "concept"), roles=("claim",), limit=limit * 3,
                          within=within)
    results = []
    for hit in hits[:limit]:
        counted = tuple(t for t in hit.matched if t.lower() in selective)
        results.append(Result("section", f"{hit.note} § {hit.heading or 'opening'}",
                              _why(Hit(hit.note, hit.heading, hit.role, "", counted, hit.rank), ""),
                              1.0 / hit.rank, {"note": hit.note, "heading": hit.heading,
                                               "excerpt": hit.excerpt, "matched": list(counted),
                                               "matched_role": "claim"}))
    response = Response(intent="technique", results=results, matched=len(hits), tier_reached=3)
    verdict = engine.verdict(selective, results)
    response.verdict, response.coverage = verdict["level"], verdict
    response.advisories.append(verdict["sentence"])
    response.next_step = ("open the section's note and read around the excerpt" if results
                          else "nothing matched; try the vocabulary the source itself uses")
    return response


def _in_text(engine: Engine, query: str, limit: int, source: str) -> Response:
    """Inside document text (PDF pages), which ordinary searches leave out."""
    terms = terms_from(query)
    within = [source] if source else None
    hits = engine.lexical(terms, ("source",), roles=("document",), limit=limit, within=within)
    results = [Result("page", f"{h.note} {h.heading}",
                      _why(h, ""), 1.0 / h.rank,
                      {"note": h.note, "page": h.heading, "excerpt": h.excerpt,
                       "matched": list(h.matched)}) for h in hits]
    total = engine.conn.execute("SELECT COUNT(*) FROM chunk WHERE role = 'document'").fetchone()[0]
    response = Response(intent="in_text", results=results, matched=len(hits), tier_reached=3)
    if not total:
        response.advisories.append("no document text is indexed in this vault yet")
    response.next_step = ("open the page in the source's document" if results else
                          "nothing in the indexed document text matched")
    return response


def _next_step(response: Response, described: str, eliminated: int) -> str:
    if response.results and response.verdict == UNCOVERED:
        return ("nothing here covers this. Treat the results as the nearest material, not "
                "answers, and record the gap.")
    if response.results:
        return (f"read the Bottom Line of the top {min(3, len(response.results))}; the "
                f"catalogue locates, you decide")
    if eliminated and described:
        return (f"every candidate failed a constraint ({described}); relax one or record "
                f"the gap. {eliminated} were eliminated")
    return "nothing matched; try the vocabulary the domain itself uses"
