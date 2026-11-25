"""S1, second part: give the pack copies the actor names of docs/terminology.md.

    python tools/s1_actor_names.py

Only lane names change. A lane that held two actors is split by node, as listed in BY_NODE.
"""
from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]

LANES = {
    "Tier 0 agent": "Overseer (tier 0)", "Tier 0 agent (MCP / CLI-API)": "Overseer (tier 0)",
    "Tier 0 agent (external project)": "Overseer (tier 0)", "Tier 0 / Ext caller": "Overseer (tier 0)",
    "Human user": "Owner", "Human user (UI)": "Owner", "Human user (ext project)": "Owner",
    "Specification owner": "Owner",
    "Librarian Web UI": "Web UI", "Librarian UI": "Web UI",
    "Model worker (legacy transport)": "Model worker", "Clerk & Model Host": "Model worker",
    "Lead / Clerk / Scribe (tier 1-3)": "Clerk (tier 2)", "Clerk / Scribe (tier 2-3)": "Clerk (tier 2)",
    "Librarian Core": "Core", "Geo-Grapher Store": "Geo-Grapher store", "Geo-Grapher Service": "Geo-Grapher service",
}
# The as-is activation's "In-app Lead / Model worker" lane held the in-app chat Lead and the Core's model calls.
BY_NODE = {"chat_lead": "Lead (tier 1)"}
SPLIT_DEFAULT = {"In-app Lead / Model worker": "Model worker"}


def main() -> None:
    for path in sorted(HERE.glob("*/*/*.spec.yaml")):
        text = path.read_text(encoding="utf-8")
        head = "".join(line + "\n" for line in text.splitlines() if line.startswith("#"))
        spec = yaml.safe_load(text)
        changed = False
        for node in spec["nodes"]:
            lane = node.get("lane")
            new = BY_NODE.get(node["id"]) if lane in SPLIT_DEFAULT else None
            new = new or SPLIT_DEFAULT.get(lane) or LANES.get(lane)
            if new and new != lane:
                node["lane"], changed = new, True
        lanes = []
        for lane in spec["lanes"]:
            for new in ([LANES.get(lane, lane)] if lane not in SPLIT_DEFAULT else ["Lead (tier 1)", "Model worker"]):
                if new not in lanes:
                    lanes.append(new)
        used = {n.get("lane") for n in spec["nodes"]}
        lanes = [lane for lane in lanes if lane in used]
        if lanes != spec["lanes"]:
            spec["lanes"], changed = lanes, True
        if changed:
            path.write_text(head + yaml.safe_dump(spec, sort_keys=False, allow_unicode=True, width=120),
                            encoding="utf-8")
            print("renamed lanes in", path.relative_to(HERE).as_posix())


if __name__ == "__main__":
    main()
