"""S4: split the two oversized to-be specs into parents and children (PLAN.md 2.3).

    python tools/s4_split_to_be.py        # run once, on the S1 copies

The children take the same ids as their as-is counterparts (folder-review, source-intake, acceptance,
source-parse, source-reading, paper-publication), so each pairs with the as-is version by name.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import extract, load, renumber, save  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / "librarian/to-be"
NOTE = "Split from the S1 copy by tools/s4_split_to_be.py (S4, 2026-11-25); labels unchanged."


def split_ingestion() -> None:
    spec = load(PACK / "ingestion.spec.yaml")
    children = []
    spec, child = extract(
        spec, "folder-review",
        ["rootinv", "droot", "doctorroot", "reentryroot", "folderscreen", "dfolderauth", "leadfolder", "dheldcaller",
         "ownerfolder", "excl", "folderapply", "geoapply", "dgeo", "doctorgeo", "reentrygeo", "oraclecov"],
        {"dinput": "success", "queueagenda": "held for the Owner", "pauseout": "paused", "escout": "escalated"},
        title="Review a folder and apply its group (proposed)", use_case="UC1.1",
        ref_label="surveys, screens and applies the folder's own group",
        end_labels={"success": "the folder's group is applied, its inputs known",
                    "held for the Owner": "a reserved folder decision is on the Owner's agenda",
                    "paused": "held or declined", "escalated": "a critical security or data fault"})
    children.append(child)
    spec, child = extract(
        spec, "source-intake",
        ["capture", "dcap", "describe", "stage"],
        {"dgate1": "success", "reuseout": "reused", "pauseout": "paused"},
        title="Capture, title and stage each source (proposed)", use_case="UC1.2",
        ref_label="captures, titles and stages each source",
        end_labels={"success": "the sources are staged with proposed titles", "reused": "duplicates only",
                    "paused": "every target quarantined"})
    children.append(child)
    spec, child = extract(
        spec, "acceptance",
        ["dgate2", "leadaccept", "dgate2caller", "ownergate2", "promote"],
        {"oraclefinal": "success", "queueagenda": "held for the Owner", "pauseout": "paused"},
        title="Accept the screened sources (proposed)", use_case="UC1.3",
        ref_label="accepts the screened sources within the mandate, or asks the Owner once",
        ref_lane="Lead (tier 1)",
        end_labels={"success": "the accepted sources are committed", "held for the Owner": "the choice is on the Owner's agenda",
                    "paused": "held or deferred"})
    children.append(child)
    save(renumber(spec), PACK / "ingestion.spec.yaml", NOTE)
    for child in children:
        save(renumber(child), PACK / f"{child['diagram']}.spec.yaml", NOTE)


def split_source_enrichment() -> None:
    spec = load(PACK / "source-enrichment.spec.yaml")
    children = []
    spec, child = extract(
        spec, "source-parse",
        ["validate", "dvalidate", "parse", "dparse", "convplan", "convert", "convrev", "convchk", "dconv", "fallback",
         "dprov", "preproj", "parsegap"],
        {"readplan": "success", "quarantine": "failed"},
        title="Validate and parse one source (proposed)", use_case="UC1c.1",
        ref_label="validates and parses the source",
        end_labels={"success": "text is ready for reading, with its gaps recorded",
                    "failed": "unrecoverable: the item is quarantined"})
    children.append(child)
    spec, child = extract(
        spec, "source-reading",
        ["readplan", "read", "host", "readchk", "readproof", "dread", "dpoison", "partialread", "lenses", "data",
         "drelate", "relateskip", "relate", "metapropose", "metadata", "review", "reviewchk"],
        {"dpub": "success", "quarantine": "failed"},
        title="Read one source (proposed)", use_case="UC1c.2",
        ref_label="plans, reads and checks the source",
        end_labels={"success": "read, each part checked", "failed": "poison or ungrounded text after bounded retries"})
    children.append(child)
    spec, child = extract(
        spec, "paper-publication",
        ["dpub", "publish", "pubreceipt", "dpubok"],
        {"oracle": "success", "pubna": "not applicable", "pubgap": "gap"},
        title="Publish a read paper to Geo-Grapher (proposed)", use_case="UC1c.3",
        ref_label="publishes the paper to the paper graph",
        end_labels={"success": "published, with a non-empty claim receipt", "not applicable": "not a PDF, or no full conversion",
                    "gap": "missing folder, refusal, or an empty paper graph"})
    children.append(child)
    save(renumber(spec), PACK / "source-enrichment.spec.yaml", NOTE)
    for child in children:
        save(renumber(child), PACK / f"{child['diagram']}.spec.yaml", NOTE)


if __name__ == "__main__":
    split_ingestion()
    split_source_enrichment()
