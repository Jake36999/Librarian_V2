"""Extract Phase 1-3 transcripts for accurate citation in final review deliverables."""
from __future__ import annotations
import json
import re
from pathlib import Path

EVID = Path(r"D:\Librarian_V2\reports\2026-11-19-agent-review\evidence")

def redact(s: str) -> str:
    return re.sub(r"(geo_token|token)=[A-Za-z0-9._-]+", r"\1=<REDACTED_TOKEN>", s)

p9 = Path(r"C:\Users\jakem\.gemini\antigravity\brain\9fa50400-0770-4909-9357-ecae5785e2b9\.system_generated\logs\transcript_full.jsonl")
if not p9.exists():
    p9 = Path(r"C:\Users\jakem\.gemini\antigravity\brain\9fa50400-0770-4909-9357-ecae5785e2b9\.system_generated\logs\transcript.jsonl")

rows = [json.loads(l) for l in p9.read_text(encoding="utf-8").splitlines() if l.strip()]
for row in reversed(rows):
    c = row.get("content", "")
    if isinstance(c, str) and ("84" in c or "A2" in c or "Librarian" in c) and len(c) > 800:
        (EVID / "phase2_subagent_report.md").write_text(redact(c), encoding="utf-8")
        print("Extracted 9fa50400 report chars:", len(c))
        break

pt = Path(r"C:\Users\jakem\.gemini\antigravity\brain\3960e172-6f69-4375-a20c-32da8ab417ab\.system_generated\logs\transcript_full.jsonl")
if pt.exists():
    out = []
    for i, line in enumerate(pt.read_text(encoding="utf-8").splitlines(), 1):
        if any(k in line for k in ("9fa50400", "42a4474", "d1a08bb", "inspect_accept_geo", "env_check", "catalog_check")):
            obj = json.loads(line)
            c = str(obj.get("content", ""))
            if obj.get("source") == "SYSTEM" or obj.get("type") in ("USER_INPUT", "PLANNER_RESPONSE", "TOOL_RESULT"):
                out.append(f"=== line {i} {obj.get('type')} {obj.get('source')} ===\n{redact(c[:3500])}")
    (EVID / "phase1_3_extract.txt").write_text("\n\n".join(out[-25:]), encoding="utf-8")
    print("Extracted phase1_3 entries:", len(out))
