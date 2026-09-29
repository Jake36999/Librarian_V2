"""Export a vault's accepted `model` sources into a standard catalog bundle
(`standard/model_catalog/<provider>.json`) any vault can adopt without
re-profiling: rewind, don't re-run.

Usage:
    python scripts/export_model_catalog.py --vault D:\\path\\to\\vault --provider deepinfra

Reads every `Sources/model/*.md` note whose `provider` frontmatter field
matches, pulls its cited evidence record in full, and writes one JSON array:
[{name, title, canonical_url, fields, bottom_line, what_it_solves, sections,
  evidence: {id, kind, source, fetched_at, payload}}, ...]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from resource_librarian.vault import Vault  # noqa: E402

FM = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)
HEADING = re.compile(r"^## (.+)$", re.M)


def _parse(text: str) -> tuple[dict, str]:
    import yaml
    m = FM.match(text)
    if not m:
        raise ValueError("no frontmatter block")
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def _sections(body: str) -> dict[str, str]:
    headings = list(HEADING.finditer(body))
    out: dict[str, str] = {}
    for i, h in enumerate(headings):
        start = h.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(body)
        out[h.group(1).strip()] = body[start:end].strip()
    return out


def export(vault: Vault, provider: str) -> list[dict]:
    folder = vault.root / "Sources" / "model"
    out = []
    for path in sorted(folder.glob("*.md")):
        fm, body = _parse(path.read_text(encoding="utf-8"))
        if fm.get("provider") != provider:
            continue
        sections = _sections(body)
        bottom_line = sections.pop("Bottom Line", "")
        what_it_solves = sections.pop("What It's For", "")
        sections.pop("Evidence", None)          # regenerated on adopt, not carried
        evidence_ids = fm.get("evidence") or []
        if not evidence_ids:
            print(f"skip {path.name}: no evidence cited", file=sys.stderr)
            continue
        record_path = vault.evidence / "model_listing" / f"{evidence_ids[0]}.json"
        if not record_path.is_file():
            print(f"skip {path.name}: evidence {evidence_ids[0]} missing on disk",
                  file=sys.stderr)
            continue
        evidence = json.loads(record_path.read_text(encoding="utf-8"))
        fields = {k: v for k, v in fm.items()
                  if k not in ("type", "kind", "title", "canonical_url", "status",
                               "primary_topic", "captured_at", "evidence", "attested_by",
                               "catalogued_at")}
        out.append({
            "name": path.stem, "title": fm.get("title", path.stem),
            "canonical_url": fm.get("canonical_url", ""), "fields": fields,
            "bottom_line": bottom_line, "what_it_solves": what_it_solves,
            "sections": sections, "captured_at": fm.get("captured_at", ""),
            "evidence": {"id": evidence["id"], "kind": evidence["kind"],
                        "source": evidence["source"], "fetched_at": evidence["fetched_at"],
                        "payload": evidence["payload"]},
        })
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--vault", required=True)
    p.add_argument("--provider", required=True)
    args = p.parse_args()
    vault = Vault(Path(args.vault))
    entries = export(vault, args.provider)
    out_path = ROOT / "src" / "resource_librarian" / "standard" / "model_catalog" / \
        f"{args.provider}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {len(entries)} entries to {out_path}")


if __name__ == "__main__":
    main()
