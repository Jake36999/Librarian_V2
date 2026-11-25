"""S3: split the two oversized as-is specs into parents and children (PLAN.md 2.3).

    python tools/s3_split_as_is.py        # run once, on the S1 copies

Labels, lanes and edges are kept; only the grouping, the step numbers and the extension numbers change.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import extract, load, renumber, save  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / "librarian/as-is"
NOTE = "Split from the S1 copy by tools/s3_split_as_is.py (S3, 2026-11-25); labels unchanged."


def split_activation() -> None:
    spec = load(PACK / "activation.spec.yaml")
    children = []
    spec, child = extract(
        spec, "activation-external-project",
        ["c2_call", "dc2_gate", "c2_helpers", "dc2_outcome", "c2_record_app", "c2_deliver_reuse",
         "c2_queue_only", "c2_deliver_partial", "c2_refusal"],
        {"capture_source": "success", "user_reused": "reused", "user_partial": "partial", "user_paused": "paused"},
        title="Work for an external project through MCP (Context 2), as it runs today", use_case="UC0.2",
        ref_label="works for an external project through MCP", ref_lane="Overseer (tier 0)",
        end_labels={"success": "a source is captured for intake", "reused": "the result reuses an Applications/ note",
                    "partial": "a workaround or gap notice, with queued leads", "paused": "refused or timed out"})
    children.append(child)
    spec, child = extract(
        spec, "folder-review",
        ["ui_folder_survey", "folder_stage_cards", "dfolder_action", "folder_draft_check", "folder_clerk_draft",
         "folder_draft_hold", "folder_batch_approve", "dfolder_batch_go", "folder_accept_prep", "dfolder_prep",
         "geo_folder_apply", "dfolder_post", "ui_folder_done", "folder_queue_sources"],
        {"dqueue_drain": "success", "start_batch": "approved for processing", "user_reused": "reused",
         "ui_hold_notice": "paused", "ui_fail_notice": "escalated"},
        title="Review a folder and apply its groups, as it runs today", use_case="UC1.1",
        ref_label="reviews the folder in the Folders tab", ref_lane="Web UI",
        end_labels={"success": "the folder's documents are queued for intake",
                    "approved for processing": "approved folder cards go into the batch",
                    "reused": "a non-Source folder is indexed whole, or excluded",
                    "paused": "held: draft disabled, stale, policy, or waiting",
                    "escalated": "the Geo-Grapher application failed"})
    children.append(child)
    spec, child = extract(
        spec, "workflow-run",
        ["ui_wf_start", "dwf_route", "wf_deep_read", "dwf_outcome", "ui_drop_result", "dwf_followup",
         "wf_paused_chip", "wf_refused"],
        {"dgate1_auth": "success", "ui_partial_notice": "partial", "user_paused": "paused",
         "ui_fail_notice": "escalated"},
        title="Run a saved workflow from the Web UI, as it runs today", use_case="UC8.1",
        ref_label="runs a saved workflow (paperclip)", ref_lane="Web UI",
        end_labels={"success": "the person decides the still-staged items",
                    "partial": "finished, but the result is unseen", "paused": "paused, with no way to resume it",
                    "escalated": "refused or failed"})
    children.append(child)
    spec, child = extract(
        spec, "source-intake",
        ["capture_source", "dcap_curr", "quar_curr", "clerk_draft", "stage_source"],
        {"dgate1_auth": "success", "reuse_curr": "reused", "ui_hold_notice": "paused"},
        title="Capture, describe and stage a source, as it runs today", use_case="UC1.2",
        ref_label="captures, describes and stages the source",
        end_labels={"success": "the source is staged", "reused": "already held, or screened out",
                    "paused": "quarantined for a retry"})
    children.append(child)
    spec, child = extract(
        spec, "acceptance",
        ["gate2_ui", "dgate2_curr", "promote_curr", "dfind_curr", "ui_done"],
        {"user_done": "success", "ui_hold_notice": "paused", "ui_partial_notice": "partial",
         "ui_fail_notice": "escalated"},
        title="Accept an enriched source into the library, as it runs today", use_case="UC1.3",
        ref_label="accepts the enriched source (Gate 2)", ref_lane="Owner",
        end_labels={"success": "the Source note is catalogued and findable",
                    "paused": "deferred, rejected, or a stale-revision conflict",
                    "partial": "written but not findable, or embedding warnings",
                    "escalated": "a write or index failure"})
    children.append(child)
    save(renumber(spec), PACK / "activation.spec.yaml", NOTE)
    for child in children:
        save(renumber(child), PACK / f"{child['diagram']}.spec.yaml", NOTE)


def split_source_enrichment() -> None:
    spec = load(PACK / "source-enrichment.spec.yaml")
    children = []
    spec, child = extract(
        spec, "source-parse",
        ["validate", "dvalidate", "parse", "dparse", "convert", "conversioncheck", "dconversion", "fallback",
         "parsegap", "dprojection", "preproject", "dpreproject", "parsefinal"],
        {"read": "success", "itemfailed": "failed"},
        title="Validate and parse one source (stages 1–2), as it runs today", use_case="UC1c.1",
        ref_label="validates and parses the source",
        end_labels={"success": "text is ready for reading, complete or with its gaps recorded",
                    "failed": "a stage failed; the item stops"})
    children.append(child)
    spec, child = extract(
        spec, "source-reading",
        ["read", "host", "readcheck", "dread", "lenses", "dlenses", "data", "ddata", "relate", "relatestatic",
         "drelate", "metadata", "dmetadata", "review", "reviewcheck", "dreview"],
        {"pubcheck": "success", "itemfailed": "failed"},
        title="Read one source (stages 3–8), as it runs today", use_case="UC1c.2",
        ref_label="reads the source: points, lenses, Data, relations, metadata, review",
        end_labels={"success": "read, with each stage's status recorded", "failed": "a stage failed; the item stops"})
    children.append(child)
    spec, child = extract(
        spec, "paper-publication",
        ["pubcheck", "dpublication", "publish", "publishstorage", "dpubresult"],
        {"reduce": "success", "pubna": "not applicable", "pubgap": "gap", "itemfailed": "failed"},
        title="Publish a read paper to Geo-Grapher (stage 9), as it runs today", use_case="UC1c.3",
        ref_label="publishes the paper to the paper graph",
        end_labels={"success": "published; the active catalogue points at the new generation",
                    "not applicable": "not a PDF, or no full-conversion artifact",
                    "gap": "reading incomplete, Geo-Grapher disabled, folder not accepted, or refused",
                    "failed": "an uncaught failure"})
    children.append(child)
    save(renumber(spec), PACK / "source-enrichment.spec.yaml", NOTE)
    for child in children:
        save(renumber(child), PACK / f"{child['diagram']}.spec.yaml", NOTE)


if __name__ == "__main__":
    split_activation()
    split_source_enrichment()
