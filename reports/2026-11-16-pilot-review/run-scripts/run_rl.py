"""Resource-Library ingestion (owner 2026-11-16: the rest of the $30, boundaries kept).

Order: resume anything interrupted; own docs (the main architecture and internal docs) newest
first; then research papers newest first; then re-run partial sources (publication and failed
chunks; finished stages carry over). PDFs byte-identical to Nonlinear Field Lab's research are
marked skipped in this library's folder-sources ledger before queuing: they belong to that
library and are read there. The ceiling is held by budget_supervisor.py.
"""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent)); sys.path.insert(0, r"D:\Librarian_V2\src")
from run_ingest import round_, note, wait_batch          # noqa: E402
from core import tool                                    # noqa: E402
from resource_librarian.vault import Vault               # noqa: E402

V = r"G:\Libraries\Resource-Library"
vault = Vault(V)
NFL_RESEARCH = [r"F:\quantule_mapper\external research", r"F:\quantule_mapper\tools\external_validation",
                r"F:\quantule_mapper\docs\external_validation"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def skip_duplicates_of_nfl(folder):
    nfl = {sha(p) for root in NFL_RESEARCH for p in Path(root).rglob("*.pdf")}
    ledger = vault.librarian / "folder-sources.json"
    done = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
    marked = []
    for p in Path(folder).rglob("*.pdf"):
        key = p.resolve().as_posix()
        if key not in done and sha(p) in nfl:
            done[key] = "skipped: byte-identical to a Nonlinear Field Lab research PDF"
            marked.append(p.name)
    ledger.write_text(json.dumps(done, indent=1), encoding="utf-8")
    note(phase="RL", step="skip-duplicates", folder=folder, marked=len(marked), examples=marked[:5])


def roots(purposes):
    rs = json.loads((vault.librarian / "content-roots.json").read_text(encoding="utf-8"))["roots"]
    return [r["path"] for r in rs if r.get("attached") and r.get("purpose") in purposes]


def run_folders(name, folders, scope, limit=20):
    for folder in folders:
        while True:
            state = round_(V, folder, limit, scope, name)
            if state == "ceiling":
                note(phase=name, step="ceiling"); return "ceiling"
            if state in ("done", "error"):
                note(phase=name, step="folder_" + state, folder=folder); break
    return "done"


def resume_unfinished():
    s = tool(V, "batch_status")
    if s.get("run") and s.get("status") != "running" and (s.get("processed") or 0) < (s.get("total") or 0):
        r = tool(V, "process_approved", {"resume": s["run"], "background": True})
        final = wait_batch(V) if r.get("started") else s
        note(phase="RL-resume", run=s["run"], batch_status=final.get("status"))


def rerun_partials():
    ids, offset = [], 0
    while True:
        page = tool(V, "staging_list", {"kind": "source", "status": "partial", "limit": 200, "offset": offset}).get("items") or []
        ids += [r["id"] for r in page if r.get("sensitivity", "normal") == "normal"]
        if len(page) < 200:
            break
        offset += 200
    for start in range(0, len(ids), 50):
        tool(V, "staging_decide", {"item_ids": ids[start:start + 50], "decision": "approve",
                                   "reason": "retry partials: owner instruction in chat 2026-11-16, applied by agent Claude"})
        r = tool(V, "process_approved", {"background": True})
        final = wait_batch(V) if r.get("started") else {}
        note(phase="RL-retry-partials", approved=len(ids[start:start + 50]), batch_status=final.get("status"))


if __name__ == "__main__":
    resume_unfinished()
    docs = sorted(roots({"own-docs"}))
    papers = sorted(roots({"research-docs"}))
    note(phase="RL", step="plan", own_docs=docs, research=papers)
    for folder in papers:
        skip_duplicates_of_nfl(folder)
    if run_folders("RL-own-docs", docs, [".pdf", ".md"]) != "ceiling":
        run_folders("RL-research", papers, [".pdf"])
    rerun_partials()
    note(phase="RL", step="finished")
