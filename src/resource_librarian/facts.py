"""Facts that are read, never guessed: licence class and the derivable axes.

Ported from V1 (`scout/rank.py` for licences, `librarian/derive.py` for the
axes) with their measured rules and the reasons for them intact. No model is
involved (`EVIDENCE_REQUIRED`): what the evidence does not support is left
empty for a person or a clerk task, because a plausible value nobody can tell
is wrong is worse than an empty one.

`ecosystem` is the main programming language; a language with no entry below is
left empty for a person rather than forced into a category. `derive_axes`
filters every value against the vault's own content model, so a vault with
different axes simply receives fewer derived values rather than foreign ones.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

PERMISSIVE = {"mit", "mit-0", "apache-2.0", "bsd", "bsd-2-clause", "bsd-3-clause",
              "isc", "unlicense", "0bsd", "zlib", "cc0-1.0", "postgresql", "python-2.0",
              # PSF is the Python standard library's licence, met wherever a
              # project vendors stdlib code. CC-BY-4.0 is a content licence and
              # the right answer for a specification repository, which is what
              # `syntax-tree/mdast` turned out to be.
              "psf-2.0", "cc-by-4.0"}
WEAK_COPYLEFT = {"lgpl", "lgpl-2.1", "lgpl-3.0", "mpl-2.0", "epl-2.0", "cddl-1.0"}
COPYLEFT = {"gpl", "gpl-2.0", "gpl-3.0", "gpl-3.0-or-later", "agpl", "agpl-3.0",
            "cc-by-sa-4.0", "osl-3.0"}
# Source-available licences let you read the code but restrict use, and are not
# OSI open source. GitHub reports most of them as NOASSERTION, so they arrive
# looking like "unknown" when they are in fact a known and restrictive answer.
SOURCE_AVAILABLE = {"busl-1.1", "bsl-1.1", "fsl-1.1", "fsl-1.1-apache-2.0",
                    "elastic-2.0", "sspl-1.0", "hippocratic-2.1", "commons-clause"}


UNRESOLVED_SPDX = {"", "unknown", "noassertion", "other", "none", "null"}

# How much each class restricts reuse. Used only to pick the answer for a
# LICENSE that names several licences: the most restrictive one present is the
# one that governs what a reuser may actually do, so it is the safe reading.
# Unknown sits at the top because "we could not tell" must never be quieter
# than "we could tell, and it was fine".
RESTRICTIVENESS = {"Permissive": 0, "Weak_Copyleft": 1, "Copyleft": 2,
                   "Source_Available": 3, "Unknown": 4}


def spdx_is_unresolved(spdx: str | None) -> bool:
    """True when the API has told us nothing usable and the text must be read."""
    return (spdx or "").strip().lower() in UNRESOLVED_SPDX


def license_class(spdx: str | None) -> str:
    low = (spdx or "").strip().lower()
    if spdx_is_unresolved(low):
        return "Unknown"
    if low in PERMISSIVE:
        return "Permissive"
    if low in WEAK_COPYLEFT:
        return "Weak_Copyleft"
    if low in COPYLEFT:
        return "Copyleft"
    if low in SOURCE_AVAILABLE:
        return "Source_Available"
    return "Unknown"


# ------------------------------------------------------- licence from text

# The GPL family is the hard case and the reason this is not simple substring
# matching. Every one of these texts names its siblings: LGPL-2.1 refers to the
# GPL throughout, and GPL-3.0 names both the AGPL and the LGPL in its closing
# sections. A naive match reports three licences for a file that grants one.
#
# The discriminator is position. A licence document opens with its own title,
# and refers to its relatives later, so within this family the marker that
# appears *earliest* is the licence that actually governs.
GPL_FAMILY = (
    ("AGPL", "gnu affero general public license"),
    ("LGPL", "gnu lesser general public license"),
    ("GPL", "gnu general public license"),
)
GPL_SPDX = {("AGPL", "3"): "AGPL-3.0", ("AGPL", ""): "AGPL-3.0",
            ("LGPL", "2.1"): "LGPL-2.1", ("LGPL", "3"): "LGPL-3.0",
            ("LGPL", ""): "LGPL-2.1",
            ("GPL", "2"): "GPL-2.0", ("GPL", "3"): "GPL-3.0", ("GPL", ""): "GPL-3.0"}
VERSION_NEAR = re.compile(r"version\s+(3|2\.1|2)\b")

# Distinctive strings from each licence's own body. Matching the body is strong
# evidence: the licence is here, not merely referred to.
LICENCE_BODY = (
    ("MPL-2.0", "mozilla public license version 2.0"),
    ("Apache-2.0", "apache license, version 2.0"),
    ("Apache-2.0", "licensed under the apache license"),
    ("Apache-2.0", "apache license version 2.0, january 2004"),
    ("MIT", "permission is hereby granted, free of charge"),
    ("ISC", "permission to use, copy, modify, and/or distribute this software"),
    ("BSD-3-Clause", "neither the name of"),
    ("BSD-2-Clause", "redistribution and use in source and binary forms"),
    ("Unlicense", "this is free and unencumbered software released into the public domain"),
    ("CC0-1.0", "creative commons legal code"),
    ("CC-BY-SA-4.0", "attribution-sharealike 4.0"),
    ("CC-BY-4.0", "attribution 4.0 international"),
    ("BUSL-1.1", "business source license 1.1"),
    ("Elastic-2.0", "elastic license 2.0"),
    ("SSPL-1.0", "server side public license"),
    ("PSF-2.0", "python software foundation license"),
)

# Licences named in prose rather than reproduced. Weaker evidence, and the
# reason a composite is flagged rather than resolved: a LICENSE saying "some
# files are PSF licensed" is telling you the file you care about may not be
# under the licence whose text follows it.
LICENCE_MENTION = (
    ("PSF-2.0", "psf licensed"),
    ("PSF-2.0", "python software foundation"),
    ("Apache-2.0", "apache licensed"),
    ("Apache-2.0", "apache 2.0"),
    ("Apache-2.0", "apache-2.0"),
    ("MIT", "mit licensed"),
    ("MIT", "mit license"),
    ("MPL-2.0", "mozilla public license"),
    ("CC-BY-4.0", "creative commons attribution 4.0"),
    ("CC-BY-SA-4.0", "creative commons attribution-sharealike"),
)


@dataclass(frozen=True)
class LicenceReading:
    """What the licence text actually said, and whether we are sure of it."""
    names: tuple[str, ...]        # every SPDX id the text supports
    license_class: str            # the most restrictive class present
    composite: bool               # more than one distinct licence named
    review_required: bool         # a person must confirm before this is trusted
    evidence: str                 # why, in one line

    joiner: str = " AND "

    @property
    def spdx(self) -> str:
        """One identifier when there is one, else all of them joined. Never a
        guess: a composite reports everything it found rather than picking."""
        return self.joiner.join(self.names) if self.names else "Unknown"


def _gpl_member(low: str) -> str | None:
    """Which GPL-family licence a text grants, by earliest title occurrence."""
    seen: list[tuple[int, str]] = []
    for family, marker in GPL_FAMILY:
        at = low.find(marker)
        if at >= 0:
            seen.append((at, family))
    if not seen:
        return None
    at, family = min(seen)
    window = low[at:at + 200]
    match = VERSION_NEAR.search(window)
    return GPL_SPDX.get((family, match.group(1) if match else ""))


def license_from_text(text: str, readme: str = "") -> LicenceReading:
    """Classify a LICENSE file deterministically. No model, no guessing.

    A text naming several licences returns all of them, the most restrictive
    class among them, and `review_required=True` - because the correct answer
    for a composite is a person reading it, and a confident single answer would
    be exactly the plausible guess `EVIDENCE_REQUIRED` forbids.

    `readme` is the fallback for repositories that state their licence in prose
    and ship no LICENSE file. It is always weaker evidence, so a reading that
    rests on it always requires review.
    """
    low = " ".join((text or "").lower().split())
    source = "LICENSE"
    if not low and readme:
        low = " ".join(_license_section(readme).lower().split())
        source = "readme"
    if not low:
        return LicenceReading((), "Unknown", False, True, "no licence text found")

    # The authoritative answer, when the file bothers to state one.
    expression = spdx_expression(low)
    if expression:
        names, choice = expression
        classes = [license_class(n) for n in names]
        picked = (min if choice else max)(classes,
                                          key=lambda c: RESTRICTIVENESS[c])
        joiner = " OR " if choice else " AND "
        return LicenceReading(
            names, picked, len(names) > 1,
            len(names) > 1 or picked == "Unknown" or source == "readme",
            f"{source} declares SPDX-License-Identifier: " + joiner.join(names),
            joiner=joiner)

    found: list[str] = []
    gpl = _gpl_member(low)
    if gpl:
        found.append(gpl)
    for spdx, marker in LICENCE_BODY:
        if marker in low and spdx not in found:
            found.append(spdx)
    if "BSD-3-Clause" in found and "BSD-2-Clause" in found:
        found.remove("BSD-2-Clause")     # 3-clause is 2-clause plus a clause

    body_count = len(found)
    for spdx, marker in LICENCE_MENTION:
        if marker in low and spdx not in found:
            found.append(spdx)
    for spdx, pattern in SPDX_TOKEN:
        if spdx not in found and pattern.search(low):
            found.append(spdx)

    if not found:
        return LicenceReading((), "Unknown", False, True,
                              f"{source} present but matched no known licence")

    names = tuple(sorted(found))
    composite = len(names) > 1
    # A composite read from prose is always a conjunction: this file is MIT,
    # that vendored one is PSF, and the most restrictive licence present
    # governs what a reuser may do.
    #
    # A *choice* between licences is only ever inferred from an explicit SPDX
    # `OR` expression, handled above. It was briefly inferred from wording too,
    # and that was wrong in a way worth recording: "either version 3 of the
    # License, or (at your option) any later version" is GPL and AGPL
    # boilerplate present in every copy of those licences, and it describes a
    # choice between *versions of one licence*, not between licences. Reading
    # it as a choice took the least restrictive name in the list and reported
    # ckan (AGPL-3.0) and wazuh (GPL-2.0) as Permissive - the exact direction
    # of error that puts a copyleft project into a permissive-only answer.
    worst = max((license_class(n) for n in names),
                key=lambda c: RESTRICTIVENESS[c])
    referred = len(names) - body_count
    detail = (f"{body_count} reproduced in full, {referred} referred to"
              if composite else
              "reproduced in full" if body_count else "referred to only")
    return LicenceReading(
        names, worst, composite,
        composite or worst == "Unknown" or source == "readme",
        f"{source} names " + ", ".join(names) + f" ({detail})")


# SPDX identifiers written as bare tokens, which is how a readme states a
# licence rather than reproducing it. `[CC-BY-4.0][license] (c) Titus Wormer`
# is the entire licence declaration in `syntax-tree/mdast`, and no prose
# marker reaches it. Applied last, so a reproduced licence body always wins.
SPDX_TOKEN = tuple((spdx, re.compile(pattern, re.I))
                   for spdx, pattern in (
    ("CC-BY-SA-4.0", r"\bcc[\s-]?by[\s-]?sa[\s-]?4\.0\b"),
    ("CC-BY-4.0", r"\bcc[\s-]?by[\s-]?4\.0\b"),
    ("CC0-1.0", r"\bcc0[\s-]?1\.0\b"),
    ("Apache-2.0", r"\bapache[\s-]?2\.0\b"),
    ("AGPL-3.0", r"\bagpl[\s-]?v?3(?:\.0)?\b"),
    ("LGPL-2.1", r"\blgpl[\s-]?v?2\.1\b"),
    ("LGPL-3.0", r"\blgpl[\s-]?v?3(?:\.0)?\b"),
    ("GPL-3.0", r"\bgpl[\s-]?v?3(?:\.0)?\b"),
    ("GPL-2.0", r"\bgpl[\s-]?v?2(?:\.0)?\b"),
    ("MPL-2.0", r"\bmpl[\s-]?2\.0\b"),
    ("BSD-3-Clause", r"\bbsd[\s-]?3[\s-]?clause\b"),
    ("BSD-2-Clause", r"\bbsd[\s-]?2[\s-]?clause\b"),
    ("MIT", r"\bmit\b"),
    ("ISC", r"\bisc\b"),
    ("Unlicense", r"\bunlicense\b"),
))


# An explicit SPDX expression is the authoritative answer and outranks every
# heuristic below it. `Apache-2.0 OR GPL-2.0-only` is a choice offered to the
# reuser; `MIT AND PSF-2.0` is a combination binding all of it.
SPDX_EXPRESSION = re.compile(
    r"spdx-license-identifier\s*:\s*([a-z0-9.\-+ ()]+?)(?:\s*$|[\n`\"'])", re.I)
SPDX_NORMALISE = {"gpl-2.0-only": "GPL-2.0", "gpl-3.0-only": "GPL-3.0",
                  "gpl-2.0-or-later": "GPL-2.0", "gpl-3.0-or-later": "GPL-3.0",
                  "lgpl-2.1-only": "LGPL-2.1", "lgpl-3.0-only": "LGPL-3.0",
                  "agpl-3.0-only": "AGPL-3.0", "agpl-3.0-or-later": "AGPL-3.0",
                  "bsd-3-clause": "BSD-3-Clause", "bsd-2-clause": "BSD-2-Clause",
                  "apache-2.0": "Apache-2.0", "mit": "MIT", "isc": "ISC",
                  "mpl-2.0": "MPL-2.0", "psf-2.0": "PSF-2.0",
                  "cc-by-4.0": "CC-BY-4.0", "cc-by-sa-4.0": "CC-BY-SA-4.0",
                  "cc0-1.0": "CC0-1.0", "unlicense": "Unlicense",
                  "busl-1.1": "BUSL-1.1", "elastic-2.0": "Elastic-2.0"}


def spdx_expression(text: str) -> tuple[tuple[str, ...], bool] | None:
    """Licences named by an SPDX expression, and whether they are a choice.

    Returns None when the text states no expression, so callers fall through
    to reading the licence body.
    """
    match = SPDX_EXPRESSION.search(text or "")
    if not match:
        return None
    raw = match.group(1).strip().strip("`\"'").replace("(", " ").replace(")", " ")
    parts = [p for p in re.split(r"\s+", raw) if p]
    choice = any(p.upper() == "OR" for p in parts)
    names: list[str] = []
    for part in parts:
        if part.upper() in {"AND", "OR", "WITH"}:
            continue
        spdx = SPDX_NORMALISE.get(part.lower(), part)
        if spdx not in names:
            names.append(spdx)
    return (tuple(sorted(names)), choice) if names else None


LICENSE_HEADING = re.compile(r"^#{1,6}\s*licen[cs]e\b.*$", re.M | re.I)


def _license_section(readme: str) -> str:
    """The `## License` section of a readme, or nothing.

    Deliberately narrow. A repository that states its licence only in prose is
    a repository whose licence needs a person to confirm, and this exists to
    stop that case being silently recorded as Unknown when the answer was
    written down - which is what `syntax-tree/mdast` did.
    """
    match = LICENSE_HEADING.search(readme or "")
    if not match:
        return ""
    rest = readme[match.end():]
    nxt = re.search(r"^#{1,6}\s+", rest, re.M)
    return rest[:nxt.start()] if nxt else rest[:1000]




# A language name to the `ecosystem` value: the main programming language.
# Deliberately incomplete: an unmapped language returns nothing and the axis is
# left for a person, which is more honest than forcing it into `Mixed`.
LANGUAGE_ECOSYSTEM = {
    "c": "C", "python": "Python", "go": "Go", "rust": "Rust",
    "typescript": "TypeScript", "javascript": "JavaScript", "java": "Java",
    "c#": "CSharp", "csharp": "CSharp", "c++": "CPlusPlus", "cpp": "CPlusPlus",
    "shell": "Shell", "powershell": "Shell", "batchfile": "Shell",
    "markdown": "Markdown", "mdx": "Markdown", "text": "Markdown",
    "ruby": "Ruby", "php": "PHP", "kotlin": "Kotlin", "swift": "Swift",
    "haskell": "Haskell", "r": "R", "julia": "Julia", "scala": "Scala", "lua": "Lua",
}

EXTENSION_ECOSYSTEM = {
    ".c": "C", ".h": "C", ".py": "Python", ".go": "Go", ".rs": "Rust",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript",
    ".java": "Java", ".cs": "CSharp",
    ".cpp": "CPlusPlus", ".cc": "CPlusPlus", ".cxx": "CPlusPlus", ".hpp": "CPlusPlus",
    ".sh": "Shell", ".ps1": "Shell", ".md": "Markdown",
    ".rb": "Ruby", ".php": "PHP", ".kt": "Kotlin", ".swift": "Swift", ".hs": "Haskell",
    ".r": "R", ".jl": "Julia", ".scala": "Scala", ".lua": "Lua",
}

# Mentioned anywhere in the evidence, these mean the project expects a GPU.
GPU = re.compile(r"\b(cuda|gpu|vram|nvidia|rocm|tensorrt|bitsandbytes|"
                 r"torch\.cuda|accelerat\w*\s+gpu)\b", re.I)

STALE_DAYS = 730          # two years without a push, and it is not Active
ABANDONED_MARKERS = re.compile(
    r"\b(no longer maintained|unmaintained|deprecated|archived|"
    r"this project is dead|not actively developed|read.only)\b", re.I)


EXT_COUNT = re.compile(r"^\s*(\.[A-Za-z0-9_+-]+)\s*\((\d+)\)\s*$")


def extension_counts(survey: dict[str, Any]) -> dict[str, int]:
    """Extension counts, whatever shape the survey stored them in.

    `scout.survey.shape` writes `[".py (150)", ".md (30)"]`; a hand-built
    fixture writes `{".py": 150}`. Both callers below tested for a mapping and
    silently did nothing on the real form, so neither the ecosystem fallback
    nor the prose rule ever fired against a live survey.
    """
    raw = survey.get("extensions")
    if isinstance(raw, dict):
        return {str(k).lower(): _int(v) for k, v in raw.items()}
    out: dict[str, int] = {}
    for item in raw or ():
        match = EXT_COUNT.match(str(item))
        if match:
            out[match.group(1).lower()] = int(match.group(2))
        elif str(item).startswith("."):
            out[str(item).lower()] = 1
    return out


def _ecosystem(meta: dict[str, Any], survey: dict[str, Any]) -> str:
    language = str(meta.get("language") or meta.get("github_language") or "").lower()
    if language in LANGUAGE_ECOSYSTEM:
        return LANGUAGE_ECOSYSTEM[language]

    extensions = extension_counts(survey)
    if extensions:
        ranked = sorted(extensions.items(), key=lambda kv: -kv[1])
        # Only the dominant extension counts. Walking down the list until
        # something maps reported `Markdown` for a repository that is 250 `.ts`
        # files and 30 `.md` ones - `.ts` has no value in this enumeration, so
        # the loop fell through to the readme files. An unmapped leader means
        # the taxonomy has no home for this language, and saying nothing is the
        # honest answer.
        top_name, top_count = ranked[0]
        mapped = EXTENSION_ECOSYSTEM.get(str(top_name).lower())
        if mapped:
            return mapped
    # A language with no home in the enumeration - Ruby, Kotlin, Swift - is
    # left for a person rather than forced into `Mixed`, which would say
    # something false about a single-language repository.
    return ""


def _maturity(meta: dict[str, Any], evidence_text: str) -> str:
    if meta.get("archived") or ABANDONED_MARKERS.search(evidence_text or ""):
        return "Abandoned"
    pushed = str(meta.get("pushed_at") or meta.get("github_pushed_at") or "")
    age = _age_days(pushed)
    if age is None:
        return ""
    if age > STALE_DAYS:
        return "Abandoned"
    # `Production_Ready` and `Reference` are judgements about what a repository
    # *is*, which metadata cannot settle. Recency only rules out abandonment.
    return "Active"


def _footprint(evidence_text: str) -> str:
    """Only the negative case is safe to derive.

    Text mentioning CUDA might still run on a CPU; text mentioning nothing of
    the sort is not a GPU project. So absence gives `CPU_Only` and presence
    gives nothing, leaving the harder call to a reader.
    """
    if not evidence_text:
        return ""
    return "" if GPU.search(evidence_text) else "CPU_Only"


# The enumeration is two values and one of them is the default. `Uncertified`
# does not mean "we checked and it failed" - it means no certification is
# claimed, which is true of essentially everything here. So the only question
# worth asking is whether this is security material at all, and that is a
# keyword question rather than a judgement about how secure anything is.
SECURITY = re.compile(
    r"\b(exploit\w*|payload|penetration test\w*|pentest\w*|red team|malware|"
    r"vulnerabilit\w+|CVE-\d|shellcode|backdoor|c2 framework|"
    r"command and control|antivirus evasion|reverse shell|"
    r"privilege escalation|siem|intrusion detection|firewall|forensic\w*|"
    r"cryptograph\w+|authentication|authorisation|authorization|"
    r"secrets? management|threat (?:model|intel)\w*)\b", re.I)


def _security(evidence_text: str) -> str:
    """Security material, or not. Never a claim about how secure something is."""
    return ("Security_Adjacent" if SECURITY.search(evidence_text or "")
            else "Uncertified")


def _age_days(timestamp: str) -> int | None:
    if not timestamp:
        return None
    text = timestamp.strip().replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).days


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------- grounding

SKILL_DIR = re.compile(
    r"(?:^|/)(?:\.claude|\.agents|\.opencode|\.cursor|\.gemini)?/?skills/"
    r"[^/]+/(?:SKILL\.md|skill\.md)", re.I)

INSTRUCTION_FILE = re.compile(
    r"(?:^|/)(?:AGENTS?\.md|CLAUDE\.md|GEMINI\.md|CONVENTIONS\.md|"
    r"\.cursorrules|copilot-instructions\.md)$", re.I)

INSTRUCTION_DIR = re.compile(
    r"(?:^|/)\.(?:claude|cursor|agents|opencode|gemini|aider)/", re.I)

# An MCP server is the usual way a repository *is* an agent-invocable
# interface. A manifest or a package directory is strong; a passing mention in
# a workflow file or a test fixture is not, which is why this does not simply
# match "mcp" anywhere in a path.
MCP_STRONG = re.compile(
    r"(?:^|/)(?:\.mcp\.json|mcp\.json|mcp_config\.json|"
    r"\.well-known/mcp\.json)$|"
    r"(?:^|/)(?:_mcp|mcp_server|mcpb)(?:/|$)|"
    r"(?:^|/)mcp/(?:__init__\.py|server\.py|index\.ts|main\.py)$", re.I)


def agent_surface(paths: Iterable[str], *, repo_key: str = "",
                  description: str = "", topics: Iterable[str] = ()) -> str:
    """The highest rung the evidence reaches. `None` when it reaches none.

    Deliberately returns `None` rather than "" for an absent surface: `None`
    is a permitted value on this axis and means *we looked and there is no
    agent surface*, which is a finding. An empty string would mean *nobody
    looked*, and 78% of the corpus genuinely has no surface.
    """
    listing = [str(p) for p in (paths or ()) if p]

    declared = f"{description} {' '.join(str(t) for t in topics or ())}"
    # A repository *named* mcp is one, and the name is evidence. `semgrep/mcp`
    # was charted `Callable` and derived `None`, because its MCP-ness is in the
    # name rather than in any of the ten sampled paths.
    named = bool(re.search(r"(?:^|[/_-])mcp(?:[/_-]|$)", repo_key or "", re.I))
    if (named
            or any(MCP_STRONG.search(p) for p in listing)
            or re.search(r"\bmcp\b.{0,40}\bserver\b"
                         r"|\bserver\b.{0,40}\bmcp\b"
                         r"|model context protocol", declared, re.I)):
        return "Callable"
    if any(SKILL_DIR.search(p) for p in listing):
        return "Procedural"
    if any(INSTRUCTION_FILE.search(p) or INSTRUCTION_DIR.search(p)
           for p in listing):
        return "Documented"
    return "None"



def _ecosystem(meta: dict[str, Any], survey: dict[str, Any]) -> str:
    language = str(meta.get("language") or meta.get("github_language") or "").lower()
    if language in LANGUAGE_ECOSYSTEM:
        return LANGUAGE_ECOSYSTEM[language]

    extensions = extension_counts(survey)
    if extensions:
        ranked = sorted(extensions.items(), key=lambda kv: -kv[1])
        # Only the dominant extension counts. Walking down the list until
        # something maps reported `Markdown` for a repository that is 250 `.ts`
        # files and 30 `.md` ones - `.ts` has no value in this enumeration, so
        # the loop fell through to the readme files. An unmapped leader means
        # the taxonomy has no home for this language, and saying nothing is the
        # honest answer.
        top_name, top_count = ranked[0]
        mapped = EXTENSION_ECOSYSTEM.get(str(top_name).lower())
        if mapped:
            return mapped
    # A language with no home in the enumeration - Ruby, Kotlin, Swift - is
    # left for a person rather than forced into `Mixed`, which would say
    # something false about a single-language repository.
    return ""


def _maturity(meta: dict[str, Any], evidence_text: str) -> str:
    if meta.get("archived") or ABANDONED_MARKERS.search(evidence_text or ""):
        return "Abandoned"
    pushed = str(meta.get("pushed_at") or meta.get("github_pushed_at") or "")
    age = _age_days(pushed)
    if age is None:
        return ""
    if age > STALE_DAYS:
        return "Abandoned"
    # `Production_Ready` and `Reference` are judgements about what a repository
    # *is*, which metadata cannot settle. Recency only rules out abandonment.
    return "Active"


def _footprint(evidence_text: str) -> str:
    """Only the negative case is safe to derive.

    Text mentioning CUDA might still run on a CPU; text mentioning nothing of
    the sort is not a GPU project. So absence gives `CPU_Only` and presence
    gives nothing, leaving the harder call to a reader.
    """
    if not evidence_text:
        return ""
    return "" if GPU.search(evidence_text) else "CPU_Only"


# The enumeration is two values and one of them is the default. `Uncertified`
# does not mean "we checked and it failed" - it means no certification is
# claimed, which is true of essentially everything here. So the only question
# worth asking is whether this is security material at all, and that is a
# keyword question rather than a judgement about how secure anything is.
SECURITY = re.compile(
    r"\b(exploit\w*|payload|penetration test\w*|pentest\w*|red team|malware|"
    r"vulnerabilit\w+|CVE-\d|shellcode|backdoor|c2 framework|"
    r"command and control|antivirus evasion|reverse shell|"
    r"privilege escalation|siem|intrusion detection|firewall|forensic\w*|"
    r"cryptograph\w+|authentication|authorisation|authorization|"
    r"secrets? management|threat (?:model|intel)\w*)\b", re.I)


def _security(evidence_text: str) -> str:
    """Security material, or not. Never a claim about how secure something is."""
    return ("Security_Adjacent" if SECURITY.search(evidence_text or "")
            else "Uncertified")


def _age_days(timestamp: str) -> int | None:
    if not timestamp:
        return None
    text = timestamp.strip().replace("Z", "+00:00")
    try:
        when = datetime.fromisoformat(text)
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - when).days


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ------------------------------------------------------------- grounding

WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.+-]{2,}")
COMMON = frozenset("""
the and for with that this from into your you are was were has have had not
but can will would should could may might must all any some each other than
then them they their there these those when where which while who whom whose
its it's use uses used using run runs running make makes made take takes
produce produces output outputs input inputs data file files code project
library tool support supports requires required work works
""".split())


def grounded(bullets: list[str], source: str, *,
             min_hits: int = 1) -> tuple[list[str], list[str]]:
    """Drop bullets whose distinctive words do not appear in the evidence.

    The live run produced *"Uses tree-sitter for parsing"* for a repository
    whose documentation never mentions tree-sitter. That is the failure this
    whole design is arranged against, and it landed in a section a machine is
    allowed to write — so allowing it requires checking it.

    Crude on purpose: it asks only whether the bullet's uncommon words occur in
    the text the model was given. It cannot catch a wrong claim built from
    right words, and it reliably catches an invented name, which is the shape
    the hallucinations actually take.
    """
    haystack = (source or "").lower()
    kept, dropped = [], []
    for bullet in bullets or []:
        text = str(bullet).strip()
        if not text:
            continue
        distinctive = [w.lower() for w in WORD.findall(text)
                       if w.lower() not in COMMON]
        if not distinctive:
            kept.append(text)
            continue
        hits = sum(1 for w in distinctive if w in haystack)
        (kept if hits >= min(min_hits, len(distinctive)) and
         hits >= len(distinctive) * 0.5 else dropped).append(text)
    return kept, dropped


# ===========================================================================
# agent_surface — a ladder of paths, not a judgement
# ===========================================================================
#
# [[Note Content Model]] defines this axis explicitly: `None`; `Documented`
# (an `AGENTS.md`, `CLAUDE.md`, `.cursor/` or equivalent); `Procedural`
# (executable skills under `.claude/skills/`, `.agents/skills/`,
# `.opencode/skills/`); `Callable` (the source *is* an agent-invocable
# interface, usually an MCP server). *A source is recorded at the highest rung
# it reaches.*
#
# That is a file listing question. Putting it to a model was the same error as
# putting the licence to one - the answer is in evidence we already hold, and
# asking converts it into a guess. Measured against the 130 hand-charted
# sources, mere presence of an `agent_instructions` path predicts


def license_class_of(meta: dict[str, Any], licence_text: str = "",
                     readme: str = "") -> tuple[str, bool, str]:
    """(class, needs review, why): the SPDX field first, then the LICENSE
    text, then the readme's licence section. Composites and prose-only
    readings always need a person."""
    spdx = str(meta.get("license_spdx") or meta.get("spdx") or "")
    if spdx and not spdx_is_unresolved(spdx):
        return license_class(spdx), False, f"SPDX {spdx}"
    if not licence_text and not readme:
        return "", False, "no licence evidence"
    reading = license_from_text(licence_text, readme if not licence_text else "")
    return reading.license_class, reading.review_required, reading.evidence


def derive_axes(meta: dict[str, Any], survey: dict[str, Any], evidence_text: str = "", *,
                licence_text: str = "", paths: Iterable[str] = (), repo_key: str = "",
                permitted: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Everything that can be read rather than guessed, filtered to the
    vault's permitted values. A missing axis stays missing."""
    out: dict[str, Any] = {}
    licence, review, why = license_class_of(meta, licence_text, evidence_text)
    if licence:
        out["license_class"] = licence
        if review:
            out["license_needs_review"] = why
    ecosystem = _ecosystem(meta, survey)
    if ecosystem:
        out["ecosystem"] = ecosystem
    maturity = _maturity(meta, evidence_text)
    if maturity:
        out["maturity_stage"] = maturity
    footprint = _footprint(evidence_text)
    if footprint:
        out["hardware_footprint"] = footprint
    out["security_compliance"] = _security(evidence_text)
    listing = list(paths or survey.get("paths") or ())
    if listing:
        out["agent_surface"] = agent_surface(
            listing, repo_key=repo_key or str(meta.get("full_name") or ""),
            description=str(meta.get("description") or ""), topics=meta.get("topics") or ())
    if permitted:
        out = {k: v for k, v in out.items()
               if k not in permitted or not permitted[k] or v in permitted[k]
               or k == "license_needs_review"}
    return out
