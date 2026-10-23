"""Safe, schema-derived fixtures for local and live validation runs.

Validation evidence is only useful when a failed case can be attributed to the
route or workflow under test.  These helpers deliberately derive the Markdown
path from the V2 vault's source-kind contract and optionally prove that the
Core-owned :class:`IndexService` can see the note *before* a live model call is
made.

They are intentionally small and are not a source-ingestion path.  Production
sources still enter through the regular capture/staging flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import notes
from .coordination import atomic_write_text
from .index import IndexService
from .vault import SOURCE_KINDS, Vault


class FixturePreflightError(ValueError):
    """A local validation fixture does not match the current vault contract."""


@dataclass(frozen=True)
class SourceFixture:
    """A minimal, disposable source note whose location is contract-derived."""

    path: Path
    kind: str
    name: str
    marker: str


def write_validation_source_fixture(
        vault: Vault, *, kind: str = "page", name: str = "Validation Evidence",
        marker: str = "ORCHID-47") -> SourceFixture:
    """Create one local-only source fixture at the authoritative V2 location.

    ``Vault.source_folder`` is deliberately the first operation.  A stale
    fixture kind therefore fails before a directory or a provider request is
    created, instead of silently recreating a retired layout such as
    ``Sources/article``.
    """
    kind = str(kind or "").strip()
    try:
        folder = vault.source_folder(kind)
    except ValueError as exc:
        raise FixturePreflightError(str(exc)) from exc
    safe_name = notes.safe_name(str(name or "")).strip()
    if not safe_name:
        raise FixturePreflightError("fixture name is required")
    marker = str(marker or "").strip()
    if not marker:
        raise FixturePreflightError("fixture marker is required")

    path = folder / f"{safe_name}.md"
    frontmatter = {
        "type": "source",
        "kind": kind,
        "status": "active",
        "title": str(name).strip(),
    }
    body = notes.compose(str(name).strip(), [
        ("Bottom Line", f"The unique validation marker is {marker}."),
        ("Evidence", "This local fixture exists solely to check grounded retrieval "
                     "in a disposable vault."),
    ])
    atomic_write_text(path, notes.render(frontmatter, body))
    fixture = SourceFixture(path=path, kind=kind, name=safe_name, marker=marker)
    validate_validation_source_fixture(vault, fixture)
    return fixture


def validate_validation_source_fixture(vault: Vault, fixture: SourceFixture) -> dict[str, Any]:
    """Check path, frontmatter, and parseability without opening SQLite."""
    if fixture.kind not in SOURCE_KINDS:
        raise FixturePreflightError(
            f"fixture kind {fixture.kind!r} is not one of {SOURCE_KINDS}")
    expected_folder = vault.source_folder(fixture.kind).resolve()
    path = fixture.path.resolve()
    if path.parent != expected_folder or path.suffix.lower() != ".md":
        raise FixturePreflightError(
            f"fixture path must be under {expected_folder}, not {path}")
    if not path.is_file():
        raise FixturePreflightError(f"fixture note is missing: {path}")
    loaded = notes.load(path)
    if loaded.parse_error:
        raise FixturePreflightError(f"fixture frontmatter is invalid: {loaded.parse_error}")
    if loaded.type != "source":
        raise FixturePreflightError("fixture type must be 'source'")
    if str(loaded.frontmatter.get("kind") or "") != fixture.kind:
        raise FixturePreflightError(
            f"fixture kind is {loaded.frontmatter.get('kind')!r}, expected {fixture.kind!r}")
    if not str(loaded.frontmatter.get("title") or "").strip():
        raise FixturePreflightError("fixture source needs a title")
    if fixture.marker not in loaded.body:
        raise FixturePreflightError("fixture marker is absent from the note body")
    return {"status": "ready", "path": path.relative_to(vault.root).as_posix(),
            "kind": fixture.kind, "name": loaded.name}


def preflight_validation_source_fixture(
        vault: Vault, fixture: SourceFixture, index_service: IndexService) -> dict[str, Any]:
    """Prove the Core-owned index can discover a validated fixture.

    This deliberately receives an ``IndexService`` rather than an ``Index`` or
    a database path.  Validation code consequently follows the same SQLite
    ownership boundary as Browser, Obsidian, Cowork, and agent calls.
    """
    result = validate_validation_source_fixture(vault, fixture)
    index_service.refresh()
    row = index_service.run(lambda index: index.note_row(fixture.name, "source"))
    expected = result["path"]
    if row is None or str(row["path"] or "") != expected:
        raise FixturePreflightError(
            "fixture is not discoverable through the Core-owned index service")
    result["index_discoverable"] = True
    return result
