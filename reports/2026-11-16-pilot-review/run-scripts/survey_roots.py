"""Re-survey a library's roots through its Core (person route), one at a time, and log a summary.

usage: survey_roots.py LIBRARY ROOT [ROOT ...]
"""
import collections, json, sys, time
sys.path.insert(0, r"D:\Librarian_V2\src")
import core
from resource_librarian.vault import Vault
from resource_librarian.folder_review import FolderReview

library, roots = sys.argv[1], sys.argv[2:]
for root in roots:
    t = time.time()
    try:
        out = core.call(library, "POST", "/api/folders/survey", {"path": root}, timeout=14400)
        cards = out.get("cards") or []
        print(json.dumps({"root": root, "secs": round(time.time() - t), "cards": len(cards)}), flush=True)
    except Exception as exc:                                 # noqa: BLE001
        print(json.dumps({"root": root, "secs": round(time.time() - t), "error": str(exc)[:400]}), flush=True)
fr = FolderReview(Vault(library))
counts = collections.Counter()
for c in fr.list(include_provenance=False):
    if c["kind"] == "folder" and c["source_root"] in roots:
        counts[(c["source_root"], c["status"], bool(c.get("inherited")))] += 1
for k, n in sorted(counts.items()):
    print(n, k, flush=True)
