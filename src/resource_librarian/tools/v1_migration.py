"""Person-controlled one-way migration from the original Resource Library."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from .. import v1_export
from ..registry import Card, Context, REGISTRY
from ..rules import Refusal


def _root(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise TypeError("v1_root is an existing Resource Library folder")
    return path


@REGISTRY.tool("v1_import_plan", tier="consult", effect="read", sessionless=True,
               card=Card("Preview a one-way V1 migration without writing either library.",
                         "you are deciding whether to bring catalogued Resource Library records into V2"),
               returns=("from", "to", "counts", "rows"))
def v1_import_plan(ctx: Context, v1_root: str, with_drafts: bool = False) -> dict:
    """V1 is read only; the preview explains every staged, held and excluded note."""
    return v1_export.plan(_root(v1_root), ctx.vault, with_drafts)


@REGISTRY.tool("v1_import_stage", tier="curate", effect="vault_write", scope="library",
               sessionless=True, idempotent=False,
               card=Card("Stage selected safe V1 categories for ordinary V2 review.",
                         "a person reviewed a V1 import plan and wants an explicit batch staged"),
               returns=("staged", "items", "manifest"))
def v1_import_stage(ctx: Context, v1_root: str, shapes: list[str] | None = None,
                    limit: int = 0, with_drafts: bool = False,
                    paths: list[str] | None = None) -> dict:
    """Never modifies V1 and never promotes staged material automatically."""
    if ctx.extras.get("caller_kind") != "person":
        raise Refusal("PERSON_CONFIRMS", "staging a V1 import needs an explicit person action in the browser or CLI")
    return v1_export.stage(_root(v1_root), ctx.vault, limit, with_drafts, shapes, paths)


@REGISTRY.tool("v1_import_status", tier="consult", effect="read", sessionless=True,
               card=Card("Show the source fingerprint, staged records and recent V1 migration history.",
                         "resuming or auditing a guided V1 import"), returns=("manifest", "staged"))
def v1_import_status(ctx: Context) -> dict:
    return v1_export.import_status(ctx.vault)
