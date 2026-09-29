"""The vault's schema, read from `About/Note Content Model.md`.

The schema is a note, not code, so a Python package never becomes the authority
over the vault it describes (`NO_SCHEMA_DRIFT`). This module only reads it and
checks notes against it; it has no opinion about what the schema should say.

Headings the parser understands:

    ## Shapes                          Shape | Folder | type
    ## Source Kinds                    Kind | Folder | What it is
    ## Frontmatter — <scope>           Field | Requirement
    ## Sections — <scope>              Order | Section | Requirement
    ## Axis Values — <scope>           Axis | Permitted values
    ## Claim Sections And Caveat Sections
                                       **Claim**: a, b.  **Caveat**: c.
                                       **Not indexed as text**: d.

`<scope>` is a shape (`source`), a shape and kind (`source/repository`), or
`all`. Rules for `source` apply to every kind; rules for `source/repository`
add to them. Section rules are the exception: a kind's own section table
replaces the shape's, because a paper and a repository are organised
differently rather than one extending the other.

A vault with no content model has no checks and says so. A model that exists
and will not parse is an error, and the checks stand down rather than report
every note as malformed.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import notes

MODEL_PATH = Path("About") / "Note Content Model.md"
DASH = r"\s*[—–-]\s*"


@dataclass(frozen=True)
class Violation:
    check: str
    note: str
    detail: str
    severity: str = "error"


@dataclass
class ContentModel:
    shapes: dict[str, dict[str, str]] = field(default_factory=dict)     # shape -> {folder, type}
    kinds: dict[str, str] = field(default_factory=dict)                 # kind -> folder
    frontmatter: dict[str, dict[str, str]] = field(default_factory=dict)  # scope -> field -> req
    sections: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # scope -> [(sec, req)]
    axes: dict[str, dict[str, list[str]]] = field(default_factory=dict)   # scope -> axis -> values
    claim_sections: frozenset[str] = frozenset()      # lower-case headings
    caveat_sections: frozenset[str] = frozenset()
    unindexed_sections: frozenset[str] = frozenset()
    found: bool = False
    error: str = ""

    # -- identity -------------------------------------------------------------
    def shape_of(self, note: notes.Note, vault_root: Path | None = None) -> str:
        declared = note.type
        for shape, spec in self.shapes.items():
            if declared and declared == spec.get("type"):
                return shape
        if vault_root is not None:
            try:
                top = note.path.relative_to(vault_root).parts[0]
            except (ValueError, IndexError):
                top = ""
            for shape, spec in self.shapes.items():
                if spec.get("folder") == top:
                    return shape
        return ""

    def scopes(self, shape: str, kind: str = "") -> list[str]:
        out = ["all", shape]
        if kind:
            out.append(f"{shape}/{kind}")
        return out

    # -- sections -------------------------------------------------------------
    def section_role(self, heading: str) -> str:
        """`claim`, `caveat` or `skip`. A heading on no list is a claim."""
        key = heading.strip().lower()
        if key in self.unindexed_sections:
            return "skip"
        if key in self.caveat_sections:
            return "caveat"
        return "claim"

    # -- lookups --------------------------------------------------------------
    def fields_for(self, shape: str, kind: str = "") -> dict[str, str]:
        merged: dict[str, str] = {}
        for scope in self.scopes(shape, kind):
            merged.update(self.frontmatter.get(scope, {}))
        return merged

    def sections_for(self, shape: str, kind: str = "") -> list[tuple[str, str]]:
        if kind and f"{shape}/{kind}" in self.sections:
            return self.sections[f"{shape}/{kind}"]
        return self.sections.get(shape, [])

    def axes_for(self, shape: str, kind: str = "") -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}
        for scope in self.scopes(shape, kind):
            merged.update(self.axes.get(scope, {}))
        return merged

    # -- checks ---------------------------------------------------------------
    def check(self, note: notes.Note, vault_root: Path | None = None) -> list[Violation]:
        if not self.found or self.error:
            return []
        if note.parse_error:
            return [Violation("frontmatter_parses", note.name, note.parse_error)]
        shape = self.shape_of(note, vault_root)
        if not shape:
            return []
        kind = str(note.frontmatter.get("kind") or "") if shape == "source" else ""
        out: list[Violation] = []
        if shape == "source" and kind and kind not in self.kinds:
            out.append(Violation("kind_known", note.name,
                                 f"kind {kind!r} is not one of {sorted(self.kinds)}"))
        for name, requirement in self.fields_for(shape, kind).items():
            if requirement == "required" and _empty(note.frontmatter.get(name)):
                out.append(Violation("required_fields", note.name,
                                     f"{shape}{'/' + kind if kind else ''} requires `{name}`"))
        present = note.sections()
        for section, requirement in self.sections_for(shape, kind):
            if requirement == "required" and not present.get(section, "").strip():
                out.append(Violation("required_sections", note.name,
                                     f"missing or empty section `## {section}`"))
        for axis, values in self.axes_for(shape, kind).items():
            value = note.frontmatter.get(axis)
            if _empty(value):
                continue
            for item in value if isinstance(value, list) else [value]:
                if not values:
                    out.append(Violation("axis_values", note.name,
                                         f"`{axis}` has no accepted values yet; `{item}` needs "
                                         f"accepting into the content model first"))
                elif str(item) not in values:
                    out.append(Violation("axis_values", note.name,
                                         f"`{axis}: {item}` is not a permitted value "
                                         f"({', '.join(values)})"))
        return out


def _empty(value: object) -> bool:
    return value is None or value == "" or value == []


def _cells(line: str) -> list[str]:
    return [c.strip().strip("`") for c in line.strip().strip("|").split("|")]


def _tables(body: str) -> dict[str, list[list[str]]]:
    """Heading -> table rows (header and separator removed)."""
    out: dict[str, list[list[str]]] = {}
    for heading, text in notes.split_sections(body).items():
        rows = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
        if len(rows) >= 2:
            out[heading] = [_cells(r) for r in rows[2:]]
    return out


def parse(text: str) -> ContentModel:
    frontmatter, body, error = notes.parse(text)
    model = ContentModel(found=True)
    if error:
        model.error = error
        return model
    for heading, rows in _tables(body).items():
        scope_match = re.match(rf"^(Frontmatter|Sections|Axis Values){DASH}(.+)$", heading)
        if heading == "Shapes":
            model.shapes = {r[0]: {"folder": r[1], "type": r[2]} for r in rows if len(r) >= 3}
        elif heading == "Source Kinds":
            model.kinds = {r[0]: r[1] for r in rows if len(r) >= 2}
        elif scope_match:
            what, scope = scope_match.group(1), scope_match.group(2).strip()
            if what == "Frontmatter":
                model.frontmatter[scope] = {r[0]: r[1] for r in rows if len(r) >= 2}
            elif what == "Sections":
                model.sections[scope] = [(r[1], r[2]) for r in rows if len(r) >= 3]
            else:
                model.axes[scope] = {r[0]: [v.strip() for v in r[1].split(",") if v.strip()]
                                     for r in rows if len(r) >= 2}
    sections = notes.split_sections(body)
    roles = sections.get("Claim Sections And Caveat Sections", "")
    flat = " ".join(roles.split())
    for label, attr in (("Claim", "claim_sections"), ("Caveat", "caveat_sections"),
                        ("Not indexed as text", "unindexed_sections")):
        found = re.search(rf"\*\*{label}\*\*:\s*([^.]+)\.", flat)
        if found:
            setattr(model, attr, frozenset(x.strip().lower() for x in found.group(1).split(",")
                                           if x.strip()))
    if not model.shapes:
        model.error = "the content model has no `## Shapes` table"
    return model


def load(vault_root: Path) -> ContentModel:
    path = vault_root / MODEL_PATH
    if not path.exists():
        return ContentModel(found=False)
    return parse(path.read_text(encoding="utf-8"))
