"""The Owner's decision on unlicensed repositories (26 November), and the two requirements the regression
matrix left unresolved: models given only closed choices, and bounded concurrency within a stage.

    python tools/s7_owner_decisions.py          # idempotent
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, save  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
NOTE = "Owner decision and closing fixes by tools/s7_owner_decisions.py (2026-11-26)."
L = "librarian/to-be/"

LABELS = {
    L + "folder-review": {
        "folderscreen": ("screens only the new or ambiguous folders for purpose, authorship and sensitivity, without reading "
                         "documents; an unlicensed repository is an external source, labelled and never withheld"),
    },
    L + "verify-claims": {
        "review": ("reviews each claim against the passage around its quote, choosing one of the Core's closed verdicts: "
                   "supported, goes beyond the passage, or not a readable sentence; review is always on"),
    },
    L + "oracle": {
        "tierb": ("reviews what Tier A cannot decide (claims against passages, neutrality, whether the question is answered), "
                  "choosing among closed verdicts the Core offers, each with its evidence"),
    },
    L + "source-reading": {
        "read": ("carries out bounded reading and synthesis tasks, at most a set number at a time within the stage, "
                 "within the reserved budget"),
    },
}


def main() -> None:
    for stem, labels in LABELS.items():
        path = HERE / f"{stem}.spec.yaml"
        spec = load(path)
        nodes = {n["id"]: n for n in spec["nodes"]}
        for nid, label in labels.items():
            nodes[nid]["label"] = label
        save(spec, path, NOTE)


if __name__ == "__main__":
    main()
