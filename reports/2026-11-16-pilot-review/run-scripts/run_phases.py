"""Owner 2026-11-16: $20 internal docs, then $10 research, newest first, until the funds are spent.

Phase A: every own-docs root of the library, newest first, ceiling $20 of library spend.
Phase B: the research folder, ceiling = spend after phase A + $10.
Ceilings are the library's own [budget] ceiling_usd, which the Core enforces between items.
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, r"D:\Librarian_V2\src")
from run_ingest import round_, note, wait_batch
from core import tool
from resource_librarian.vault import Vault
from resource_librarian import usage_log

V = r"G:\Libraries\Nonlinear Field Lab"
vault = Vault(V)
roots = json.loads((vault.librarian / "content-roots.json").read_text(encoding="utf-8"))["roots"]
own_docs = [r["path"] for r in roots if r.get("purpose") == "own-docs"]
own_docs.sort(key=lambda p: (p.rstrip("\\") != r"F:\quantule_mapper\docs", p))   # the main docs folder first
RESEARCH = [r"F:\quantule_mapper\external research", r"F:\quantule_mapper\tools\external_validation"]


def phase(name, folders, ceiling, scope, limit=25, adopt_first=False):
    vault.set_setting("budget", "ceiling_usd", round(ceiling, 4))
    note(phase=name, step="begin", ceiling=ceiling, spent=round(usage_log.spent_usd(vault), 4), folders=folders)
    adopt = adopt_first
    for folder in folders:
        while True:
            state = round_(V, folder, limit, scope, name, adopt=adopt)
            adopt = False
            if state == "ceiling":
                note(phase=name, step="ceiling", spent=round(usage_log.spent_usd(vault), 4)); return "ceiling"
            if state in ("done", "error"):
                note(phase=name, step="folder_" + state, folder=folder); break
    return "done"


def resume_unfinished():
    s = tool(V, "batch_status")
    if s.get("run") and s.get("status") != "running" and (s.get("processed") or 0) < (s.get("total") or 0):
        r = tool(V, "process_approved", {"resume": s["run"], "background": True})
        final = wait_batch(V) if r.get("started") else s
        items = final.get("items") or []
        note(phase="resume", run=s["run"], started=r.get("started"), detail=str(r.get("detail", ""))[:300],
             batch_status=final.get("status"), item_status={k: sum(1 for i in items if i.get("status") == k)
                                                           for k in {i.get("status") for i in items}})


def rerun(statuses, pdf_only, label):
    """Approve already-processed sources again: finished stages carry over, so only stages
    added since (publish) or left unfinished (a failed chunk) run."""
    rows, offset = [], 0
    while True:
        page = []
        for st in statuses:
            page += tool(V, "staging_list", {"kind": "source", "status": st, "limit": 200, "offset": offset}).get("items") or []
        rows += page
        if len(page) < 200 * len(statuses):
            break
        offset += 200
    import json as _j
    ids = []
    for r in rows:
        if r.get("sensitivity", "normal") != "normal":
            continue
        rec = _j.loads((vault.librarian / "staging" / "source" / (r["id"] + ".json")).read_text(encoding="utf-8"))
        if pdf_only and not str(rec.get("file", "")).lower().endswith(".pdf"):
            continue
        if pdf_only and ((rec.get("processing") or {}).get("stages") or {}).get("publish") in ("complete", "not_applicable"):
            continue                       # already published (or legitimately catalogue-only): no new generation
        ids.append(r["id"])
    for start in range(0, len(ids), 50):
        chunk = ids[start:start + 50]
        tool(V, "staging_decide", {"item_ids": chunk, "decision": "approve",
                                   "reason": f"{label}: owner instruction in chat 2026-11-16, applied by agent Claude"})
        r = tool(V, "process_approved", {"background": True})
        final = wait_batch(V) if r.get("started") else {}
        items = final.get("items") or []
        note(phase=label, approved=len(chunk), run=final.get("run", ""), batch_status=final.get("status"),
             item_status={k: sum(1 for i in items if i.get("status") == k) for k in {i.get("status") for i in items}})


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    resume_unfinished()
    if which in ("both", "A"):
        rerun(["enriched"], True, "backfill-paper-graphs")
    if which in ("both", "A"):
        phase("A-internal-docs", own_docs, 20.0, [".pdf", ".md"], adopt_first=True)
    if which in ("both", "B"):
        spent = usage_log.spent_usd(vault)
        phase("B-research", RESEARCH, spent + 10.0, [".pdf"])
    rerun(["partial"], False, "retry-partials")
    note(phase="all", step="finished", spent=round(usage_log.spent_usd(vault), 4))
