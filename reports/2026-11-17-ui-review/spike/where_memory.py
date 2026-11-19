"""Where does a lean graph's memory go? tracemalloc by source line on one real graph (throwaway)."""
import sys, tracemalloc, collections
cat_path, gid = sys.argv[1], sys.argv[2]
sys.argv = [sys.argv[0], cat_path, gid, "lean"]
# reuse the spike's lean loader without running its frame code
src = open(__file__.replace("where_memory.py", "view_spike.py"), encoding="utf-8").read().split("cat = GraphCatalog(cat_path)")[0]
exec(compile(src, "spike_head", "exec"))
cat = GraphCatalog(cat_path); row = cat.graph(gid); router = GraphRouter(cat)
key, service = router.acquire(gid)
tracemalloc.start(1)
g = service.store.graph(row["snapshot_id"])
snap = tracemalloc.take_snapshot()
total = sum(s.size for s in snap.statistics("filename"))
print(f"lean graph: {len(g.entities)} entities, {len(g.relationships)} relationships, traced {total/1e6:.0f} MB")
for s in snap.statistics("lineno")[:8]:
    f = s.traceback[0]
    print(f"  {s.size/1e6:7.1f} MB  {s.count:8d} blocks  {f.filename.split('site-packages')[-1].split(chr(92))[-1]}:{f.lineno}")
# sizes of one entity and one relationship, and what its fields hold
import sys as _s
e = next(iter(g.entities.values())); r = next(iter(g.relationships.values()))
print("entity fields:", [f for f in e.__dict__.keys()] if hasattr(e, "__dict__") else "slots")
print("entity __dict__ bytes:", _s.getsizeof(e.__dict__) if hasattr(e, "__dict__") else 0,
      "| str payload:", sum(_s.getsizeof(v) for v in e.__dict__.values() if isinstance(v, str)))
print("relationship fields:", list(r.__dict__.keys()) if hasattr(r, "__dict__") else "slots")
longest = max((len(str(v)) for ent in list(g.entities.values())[:5000] for v in ent.__dict__.values()), default=0)
print("longest field value among 5000 entities:", longest, "chars")
