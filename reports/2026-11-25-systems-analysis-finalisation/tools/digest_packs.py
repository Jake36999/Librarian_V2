"""Write compact digests for the second-pass readers (regression matrix, adversarial review).

    python tools/digest_packs.py OUT_DIR

pack-digest.md     every canonical spec (id, status, title, each node's id and label), the weakness
                   registers, handles, open items, deferred use cases and the checked tables
superseded.md      the 22 superseded or copied originals of 20-24 November, compactly, for tracing what
                   canonicalisation kept and dropped
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
PACKS = ("librarian/as-is", "librarian/to-be", "geo-grapher/as-is", "geo-grapher/to-be")


def spec_lines(spec: dict, where: str) -> list[str]:
    out = [f"### {where}/{spec['diagram']} ({spec.get('use_case', '')}, {spec.get('status', '')}): {spec['title']}"]
    for k, v in (spec.get("problem") or {}).items():
        out.append(f"problem.{k}: {v if isinstance(v, str) else ' '.join(v)}")
    for n in spec["nodes"]:
        if n["kind"] == "start":
            continue
        tag = n["kind"] + (f" {n['outcome']}" if n.get("outcome") else "") + (f" -> {n['use_case']}" if n.get("use_case") else "")
        out.append(f"- {n['id']} [{tag}; {n.get('lane', '')}]: {n.get('label', '')}")
    for e in spec["edges"]:
        if e.get("guard"):
            out.append(f"  edge {e['from']}->{e['to']}: {e['guard']}" + (f" ({e['ext']})" if e.get("ext") else ""))
    return out


def pack_digest() -> str:
    out = ["# Canonical systems-analysis packs (digest)", ""]
    for name in PACKS:
        path = HERE / name
        out += [f"## Pack {name}", ""]
        meta = yaml.safe_load((path / "pack.yaml").read_text(encoding="utf-8"))
        for uc in meta.get("use_cases", []):
            if uc.get("deferred"):
                out.append(f"DEFERRED use case {uc['id']} {uc['name']}: {uc['deferred']}")
            elif uc.get("fields", {}).get("open_questions"):
                out.append(f"OPEN QUESTION {uc['id']} {uc['name']}: {uc['fields']['open_questions']}")
        for p in sorted(path.glob("*.spec.yaml")):
            out += spec_lines(yaml.safe_load(p.read_text(encoding="utf-8")), name) + [""]
        for extra in ("weaknesses.yaml", "handles.yaml", "states.yaml"):
            if (path / extra).exists():
                out += [f"#### {name}/{extra}", (path / extra).read_text(encoding="utf-8"), ""]
        for p in sorted(path.glob("*.table.yaml")):
            out += [f"#### {name}/{p.name}", p.read_text(encoding="utf-8"), ""]
    return "\n".join(out)


def superseded() -> str:
    out = ["# The 20-24 November specs that canonicalisation copied or superseded", ""]
    for p in sorted(REPO.glob("reports/2026-11-2[0-4]*/**/*.spec.yaml")):
        if "isolated" in p.as_posix():
            continue
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not spec.get("superseded_by"):
            continue
        out += spec_lines(spec, p.relative_to(REPO).parent.as_posix()) + [f"superseded_by: {spec['superseded_by']}", ""]
    return "\n".join(out)


if __name__ == "__main__":
    target = Path(sys.argv[1])
    target.mkdir(parents=True, exist_ok=True)
    (target / "pack-digest.md").write_text(pack_digest(), encoding="utf-8")
    (target / "superseded.md").write_text(superseded(), encoding="utf-8")
    for f in ("pack-digest.md", "superseded.md"):
        print(f, (target / f).stat().st_size)
