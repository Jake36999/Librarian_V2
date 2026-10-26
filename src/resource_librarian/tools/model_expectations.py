"""Human-reviewed model expectation authoring through staging."""
from __future__ import annotations

from .. import model_expectation_authoring as authoring
from ..registry import Card, Context, tool
from ..staging import StagingStore


@tool("model_expectation_propose", tier="contribute", effect="write", scope="session",
      returns=("item", "status", "record_id", "source_item_id", "source_evidence_id"),
      card=Card("Propose a strict declarative expectation from an evidenced staged model card",
                "a model source has been captured and its route contract is ready for human review",
                "Creates staging only. Raw card prose, templates and executable fields are refused."))
def model_expectation_propose(ctx: Context, source_item_id: str, record: dict) -> dict:
    return authoring.propose(StagingStore(ctx.vault), source_item_id, record)
