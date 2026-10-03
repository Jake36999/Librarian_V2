"""The approved batch, as tools (see `batch.py`). Beginning and cancelling it are a
person's: curate tier, so no model call can start processing (Research Pipeline §4.2)."""
from __future__ import annotations

from .. import batch
from ..registry import Card, Context, tool


@tool("process_approved", tier="curate", effect="write", scope="library", open_world=True,
      returns=("started", "run", "status"),
      card=Card("Begin the approved batch: read and review every source approved for "
                "ingestion, then return each for acceptance",
                "a person clicks 'Click here to begin' in Staging",
                "Takes exactly the sources approved at this moment. While a batch runs, "
                "another start reports it and does nothing; `resume` continues an "
                "interrupted or cancelled run without repeating a finished stage"))
def process_approved(ctx: Context, resume: str = "", background: bool = False,
                     retry_waiting: bool = False) -> dict:
    return batch.start(ctx, requested_by=ctx.tier, resume=resume, background=background,
                       retry_waiting=retry_waiting)


@tool("batch_status", tier="consult", effect="read",
      returns=("waiting", "running", "run", "status", "items"),
      card=Card("The approved batch: how many sources wait for the next run, and what the "
                "current or last run did to each, stage by stage",
                "checking on processing, or before telling the person what is ready"))
def batch_status(ctx: Context, run: str = "") -> dict:
    return batch.status(ctx.vault, run)


@tool("batch_cancel", tier="curate", effect="write", scope="library",
      returns=("cancelling",),
      card=Card("Stop the running batch after its current stage",
                "a person wants processing to stop",
                "Nothing is rolled back; the run can be resumed later"))
def batch_cancel(ctx: Context) -> dict:
    return batch.cancel(ctx.vault)
