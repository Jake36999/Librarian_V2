"""Relabel stored readings of texts without pages (Markdown, plain text, web pages), 2026-11-17.

Before Librarian 6125370 every part of such a text was cited "p. 1", so its sections said "(p. 1)"
and its DIK record had a single chapter. This rewrites those records with the current rules:

  * each part's locator becomes "part N" (the readings themselves are reused: they are keyed by
    the part's exact text, so nothing is read again and no model is called);
  * the Claims / Evidence & Limits sections are rebuilt (spread across every part);
  * the DIK document record is rebuilt with chapters by part.

An item is touched only if every part is read and every stored reading still matches its text;
anything else is reported and left for a real reading.

usage: relabel_md.py LIBRARY (--dry-run | --apply) [--limit N]
--apply needs the library's Core stopped: the script holds the vault lease while it writes, and
copies every file it changes to .librarian/migrations/relabel-unpaged-2026-11-17/ first.
"""
import argparse, json, re, shutil, sys, time
from pathlib import Path

from resource_librarian import PROTOCOL_VERSION, deep_read, dik, schema
from resource_librarian.coordination import VaultCoordinator
from resource_librarian.staging import StagingStore
from resource_librarian.vault import Vault

PAGED = deep_read.PAGED_SUFFIXES


def plan(vault, item):
    """(chunks, read) for an item this migration may rewrite, else (None, reason)."""
    record = item.get("deep_read") or {}
    if item.get("kind") != "source" or record.get("version") != deep_read.RECORD_VERSION:
        return None, "no current reading record"
    rel = str(item.get("file") or "")
    if not rel or rel.lower().endswith(PAGED) or item.get("clean_file"):
        return None, "paged or converted: not affected"
    stored = record.get("read") or {}
    if not stored or not any(re.match(r"pp?\. ", str(e.get("locator", ""))) for e in stored.values()):
        return None, "already labelled by part"
    representation, units = deep_read.source(vault, item)
    if not units or any(n for n, _ in units):
        return None, "the text now has pages, or is unreadable"
    chunks = deep_read.chunk(units)
    keys = deep_read.part_keys(deep_read.identity(representation), chunks)
    by_key = {e.get("key"): e for e in stored.values() if isinstance(e, dict) and e.get("key")}
    if len(chunks) != int(record.get("chunks") or 0) or not all(k in by_key for k in keys):
        return None, "a part is unread or its text changed: needs a real reading"
    # Each part keeps its own reading when its key still matches (a passage repeated word for word
    # shares a key, and its two readings may differ); otherwise the reading of that same text.
    def own(c, k):
        mine = stored.get(str(c.index))
        return mine if isinstance(mine, dict) and mine.get("key") == k else by_key[k]
    return chunks, {str(c.index): {**own(c, k), "locator": c.locator} for c, k in zip(chunks, keys)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("library"); ap.add_argument("--limit", type=int, default=10 ** 9)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true"); mode.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    vault = Vault(a.library)
    store = StagingStore(vault)
    model = schema.load(vault.root)
    backup = vault.librarian / "migrations" / "relabel-unpaged-2026-11-17"
    lease = None
    if a.apply:
        lease = VaultCoordinator(vault, protocol_version=PROTOCOL_VERSION)
        lease.acquire()                                   # refuses while a Core holds the library
    counts, chapters_now, done = {}, {"one": 0, "several": 0}, 0
    try:
        for item in list(store.items("source")):
            if done >= a.limit:
                break
            chunks, read = plan(vault, item)
            if chunks is None:
                counts[read] = counts.get(read, 0) + 1
                continue
            sections_of = dict(model.sections_for("source", item.get("source_kind", "")))
            changed = json.loads(json.dumps(item))
            changed["deep_read"]["read"] = read
            deep_read._rebuild_sections(changed, chunks, sections_of)
            record = dik.document(vault, changed["name"], [c.text for c in chunks], read,
                                  [(c.index + 1, c.index + 1) for c in chunks],
                                  str(changed.get("captured_at") or ""), unit="part")
            parts = sum(1 for d in record["data"] if d.get("kind") == "chapter")
            chapters_now["several" if parts > 1 else "one"] += 1
            counts["relabelled"] = counts.get("relabelled", 0) + 1
            if a.apply:
                item_path = store.path(item["id"]); dik_path = dik.path_for(vault, changed["name"])
                for path in (item_path, dik_path):
                    if path.is_file():
                        target = backup / path.relative_to(vault.librarian)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        if not target.exists():
                            shutil.copy2(path, target)
                changed.setdefault("history", []).append(dict(
                    at=time.strftime("%Y-%m-%dT%H:%M:%S"), event="relabelled",
                    detail="part locators and chapters by part (Librarian 6125370); readings reused, no model call",
                    by="relabel-unpaged-2026-11-17"))
                store.save(changed)
                dik.save(vault, record)
            done += 1
    finally:
        if lease is not None:
            lease.release()
    print(json.dumps({"library": vault.root.name, "mode": "apply" if a.apply else "dry-run",
                      "items": counts, "chapters_after": chapters_now}, indent=1))


if __name__ == "__main__":
    main()
