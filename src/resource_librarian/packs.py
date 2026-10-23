"""First-party pack boundary for Librarian V2.

Packs keep optional derived/research features out of the Core kernel without
turning V2 into a third-party plugin marketplace.  They are shipped code,
versioned with the Core, and expose only registered tools plus a disposable
derived-data schema.  There is deliberately no executable pack loader here.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import PROTOCOL_VERSION


@dataclass(frozen=True)
class InternalPack:
    id: str
    version: str
    core_protocol_range: str
    settings_schema: dict[str, Any] = field(default_factory=dict)
    registry_tools: tuple[str, ...] = ()
    derived_schema_version: int = 1
    health_checks: tuple[str, ...] = ()
    migrations: tuple[str, ...] = ()

    def public(self) -> dict[str, Any]:
        return asdict(self)


PACKS: dict[str, InternalPack] = {
    "graph": InternalPack(
        "graph", "1.0.0", ">=2,<3", registry_tools=("community_rebuild", "community_reports",
                                                        "community_disagreements"),
        derived_schema_version=1, health_checks=("communities.json is advisory",)),
    "extract": InternalPack(
        "extract", "1.0.0", ">=2,<3", registry_tools=("extract_plan", "extract_materialize"),
        derived_schema_version=1, health_checks=("revision-pinned source required",)),
    "learning": InternalPack(
        "learning", "1.0.0", ">=2,<3", registry_tools=("ranking_status", "ranking_benchmark",
                                                          "ranking_select", "ranking_restore"),
        derived_schema_version=1, health_checks=("manual ranking selection only",)),
    "workbench": InternalPack(
        "workbench", "1.0.0", ">=2,<3", registry_tools=("engagement_plan", "engagement_propose",
                                                            "engagement_start", "engagement_close", "engagement_list"),
        derived_schema_version=1, health_checks=("Docker is the only isolated tier",)),
}


def all_packs() -> list[dict[str, Any]]:
    return [PACKS[key].public() for key in sorted(PACKS)]


def compatible(pack: InternalPack) -> bool:
    # V2 has one supported major protocol.  Keep this simple and explicit
    # until a future protocol range parser is actually needed.
    return PROTOCOL_VERSION == "2" and pack.core_protocol_range == ">=2,<3"

