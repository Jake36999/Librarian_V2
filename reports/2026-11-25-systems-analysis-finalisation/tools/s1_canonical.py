"""S1 of PLAN.md: mark one canonical spec per process, and copy the canonical ones into the packs.

    python tools/s1_canonical.py          # from the finalisation folder; run once

What it does, and nothing else:
- every active original spec gains `status` (when it has none) and `superseded_by`, inserted as text
  after its `diagram:` line, so the rest of the file is untouched;
- each canonical original is copied into its pack under the pack's id, with `status`, `use_case`
  and `supersedes`, and its references renamed to the pack's ids.
Lanes, sizes and content are not changed here: that is S3 and S4, checked by render_pack.py.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
REPORTS = HERE.parent
REPO = REPORTS.parent

ING = "2026-11-20-workflow-map/examples/ingestion"
BASE = "2026-11-21-enrichment-baseline"
REC = "2026-11-24-librarian-reconstruction-and-offering/diagrams"
FAM = "2026-11-23-proposed-process-family"

# pack path -> (pack id, use case, status, canonical original, older generations it also supersedes)
CANONICAL = {
    "librarian/as-is": [
        ("activation", "UC0", "IMPLEMENTED_VERIFIED", f"{REC}/librarian-current-activation", []),
        ("batch-enrichment", "UC1b", "IMPLEMENTED_VERIFIED", f"{BASE}/batch-enrichment-current", []),
        ("source-enrichment", "UC1c", "IMPLEMENTED_VERIFIED", f"{BASE}/source-enrichment-current", []),
    ],
    "librarian/to-be": [
        ("activation-overseer", "UC0", "PROPOSED_UNACCEPTED", f"{REC}/librarian-context1-tier0-delegated", []),
        ("activation-external-project", "UC0", "PROPOSED_UNACCEPTED", f"{REC}/librarian-context2-external-project-mcp", []),
        ("activation-web-ui", "UC0", "PROPOSED_UNACCEPTED", f"{REC}/librarian-context3-human-platform-ui", []),
        ("compose", "UC8", "PROPOSED_UNACCEPTED", f"{REC}/librarian-process-composition-tobe", [f"{ING}/compose"]),
        ("ingestion", "UC1", "PROPOSED_UNACCEPTED", f"{REC}/librarian-ingestion-tobe",
         [f"{ING}/ingestion-tobe", f"{FAM}/proposed-ingestion"]),
        ("batch-enrichment", "UC1b", "PROPOSED_UNACCEPTED", f"{REC}/librarian-batch-enrichment-tobe",
         [f"{FAM}/proposed-batch-enrichment"]),
        ("source-enrichment", "UC1c", "PROPOSED_UNACCEPTED", f"{REC}/librarian-source-enrichment-tobe",
         [f"{BASE}/enrichment-cycle", "2026-11-22-proposed-tobe-enrichment/proposed-tobe-enrichment",
          f"{FAM}/proposed-source-enrichment"]),
        ("doctor", "UC-D", "PROPOSED_UNACCEPTED", f"{REC}/librarian-doctor-tobe", [f"{ING}/doctor"]),
        ("learn", "UC-L", "PROPOSED_UNACCEPTED", f"{ING}/learn", []),
    ],
    "geo-grapher/as-is": [
        ("graph-building", "UC1d", "IMPLEMENTED_VERIFIED",
         "2026-11-22-geographer-graph-building/geographer-graph-building", []),
    ],
}
# Not copied: the observed trace of one run, kept as evidence for the general as-is ingestion (S3).
TRACES = {f"{ING}/ingestion": ("librarian/as-is/ingestion", "IMPLEMENTED_OBSERVED")}
STATUS_OF_OLD = {f"{BASE}/enrichment-cycle": "MIXED_AS_IS_AND_TO_BE"}

# References renamed inside each pack: old diagram id -> pack id.
RENAME = {
    "librarian/as-is": {"librarian-current-activation": "activation", "batch-enrichment-current": "batch-enrichment",
                        "source-enrichment-current": "source-enrichment"},
    "librarian/to-be": {"librarian-context1-tier0-delegated": "activation-overseer",
                        "librarian-context2-external-project-mcp": "activation-external-project",
                        "librarian-context3-human-platform-ui": "activation-web-ui",
                        "librarian-process-composition-tobe": "compose", "librarian-ingestion-tobe": "ingestion",
                        "librarian-batch-enrichment-tobe": "batch-enrichment",
                        "librarian-source-enrichment-tobe": "source-enrichment",
                        "librarian-doctor-tobe": "doctor", "UC-D": "doctor", "UC-L": "learn"},
    "geo-grapher/as-is": {},
}


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def mark_original(stem: str, superseded_by: str, status: str) -> None:
    path = REPORTS / f"{stem}.spec.yaml"
    text = path.read_text(encoding="utf-8")
    if "\nsuperseded_by:" in text or text.startswith("superseded_by:"):
        return
    has_status = re.search(r"^status:", text, re.M) is not None
    insert = ("" if has_status else f"status: {status}\n") + f"superseded_by: {superseded_by}\n"
    text = re.sub(r"^(diagram: .*\n)", lambda m: m.group(1) + insert, text, count=1, flags=re.M)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    for pack, rows in CANONICAL.items():
        out_dir = HERE / pack
        out_dir.mkdir(parents=True, exist_ok=True)
        for pid, use_case, status, original, older in rows:
            src = REPORTS / f"{original}.spec.yaml"
            spec = yaml.safe_load(src.read_text(encoding="utf-8"))
            target = out_dir / f"{pid}.spec.yaml"
            spec.pop("status", None)
            head = {"diagram": pid, "use_case": use_case, "status": status,
                    "supersedes": [rel(REPORTS / f"{s}.spec.yaml") for s in [original, *older]]}
            for node in spec.get("nodes", []):
                if node.get("use_case") in RENAME[pack]:
                    node["use_case"] = RENAME[pack][node["use_case"]]
            spec.pop("diagram")
            body = yaml.safe_dump({**head, **spec}, sort_keys=False, allow_unicode=True, width=120)
            target.write_text(f"# Copied from {rel(src)} by tools/s1_canonical.py (S1, 2026-11-25).\n" + body,
                              encoding="utf-8")
            for stem in [original, *older]:
                old_status = STATUS_OF_OLD.get(stem, "PROPOSED_UNACCEPTED" if "to-be" in pack else status)
                mark_original(stem, rel(target), old_status)
    for stem, (pack_spec, status) in TRACES.items():
        mark_original(stem, f"reports/2026-11-25-systems-analysis-finalisation/{pack_spec}.spec.yaml", status)


if __name__ == "__main__":
    main()
