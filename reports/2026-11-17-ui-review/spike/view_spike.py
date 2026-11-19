"""SPIKE (throwaway): is a lean graph load enough for viewport frames, and what does it save?

mode full: today's SnapshotStore.graph.  mode lean: entities + relationships + incidences + the `text:`
analyses only (no evidence, no fingerprints, no bulk analysis results).
Run per mode in a fresh process so RSS is comparable. Catalog is a copy; stores are opened read-only
by the same code the server uses.   Usage: view_spike.py <catalog> <graph_id> <full|lean> [frames]
"""
import logging; logging.basicConfig(level=logging.ERROR)
import copy, ctypes, ctypes.wintypes as wt, hashlib, json, statistics, sys, time

cat_path, gid, mode = sys.argv[1], sys.argv[2], sys.argv[3]
with_frames = len(sys.argv) > 4


class PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t)]


_k32 = ctypes.WinDLL("kernel32"); _ps = ctypes.WinDLL("psapi")
_k32.GetCurrentProcess.restype = wt.HANDLE
_ps.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PMC), wt.DWORD]


def rss():
    c = PMC(); c.cb = ctypes.sizeof(c)
    _ps.GetProcessMemoryInfo(_k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 1e6


from geographer.model import Graph, Entity, Relationship
from geographer.store import SnapshotStore
from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter
from geographer.graph_composition import DEFAULT_FILTER


def lean_graph(self, sid, published_only=True):
    if published_only:
        self.require_complete(sid)
    g = Graph()
    for table, cls, collection in (("entities", Entity, g.entities), ("relationships", Relationship, g.relationships)):
        key = {"entities": "entity_id", "relationships": "relationship_id"}[table]
        for raw in self.connection.execute(f"SELECT * FROM {table} WHERE snapshot_id=? ORDER BY {key}", (sid,)):
            record = dict(raw); record.pop("snapshot_id")
            collection[record[key]] = cls(**record)
    g.incidences = [{k: v for k, v in dict(r).items() if k != "snapshot_id"} for r in self.connection.execute(
        "SELECT * FROM documentary_incidences WHERE snapshot_id=? ORDER BY incidence_id,entity_id", (sid,))]
    g.fingerprints = {}
    for r in self.connection.execute(
            "SELECT * FROM analysis_results WHERE snapshot_id=? AND analysis_id LIKE 'text:%'", (sid,)):
        g.analyses[r["analysis_id"]] = {"algorithm_version": r["algorithm_version"], "scope": json.loads(r["scope_json"]),
                                        "result": json.loads(r["result_json"])}
    return g


def compact_graph(self, sid, published_only=True):
    """lean + only the entity columns a frame reads, shared id strings, shared repeated values."""
    import sys as _sys
    if published_only:
        self.require_complete(sid)
    g = Graph()
    intern = _sys.intern
    cols = "entity_id,repo_id,kind,qualified_name,parent_id,sort,language,rel_path,start_line,end_line,depth,is_test,is_generated,is_vendor,is_external"
    for r in self.connection.execute(f"SELECT {cols} FROM entities WHERE snapshot_id=? ORDER BY entity_id", (sid,)):
        eid = r[0]
        g.entities[eid] = Entity(entity_id=eid, repo_id=intern(r[1]), kind=intern(r[2]), qualified_name=r[3], parent_id=r[4],
                                 sort=intern(r[5]), language=intern(r[6]) if r[6] else r[6], rel_path=intern(r[7]) if r[7] else r[7],
                                 start_line=r[8], end_line=r[9], depth=r[10], is_test=r[11], is_generated=r[12],
                                 is_vendor=r[13], is_external=r[14])
    ids = {eid: eid for eid in g.entities}                       # one string object per id, shared everywhere
    for e in g.entities.values():
        if e.parent_id is not None:
            e.parent_id = ids.get(e.parent_id, e.parent_id)
    for raw in self.connection.execute("SELECT * FROM relationships WHERE snapshot_id=? ORDER BY relationship_id", (sid,)):
        rec = dict(raw); rec.pop("snapshot_id")
        for k in ("source_id", "target_id", "source_subject_id", "target_subject_id"):
            rec[k] = ids.get(rec[k], rec[k])
        for k in ("subtype", "resolution_status", "family", "direction", "weight_unit"):
            rec[k] = intern(rec[k])
        g.relationships[rec["relationship_id"]] = Relationship(**rec)
    g.incidences = [{k: v for k, v in dict(r).items() if k != "snapshot_id"} for r in self.connection.execute(
        "SELECT * FROM documentary_incidences WHERE snapshot_id=? ORDER BY incidence_id,entity_id", (sid,))]
    g.fingerprints = {}
    import os as _os
    keep = set(_os.environ.get("SPIKE_KEEP", "").split(","))
    where = "analysis_id LIKE 'text:%'" + (" OR analysis_id LIKE 'declaration:%'" if "decl" in keep else "")
    for r in self.connection.execute(f"SELECT * FROM analysis_results WHERE snapshot_id=? AND ({where})", (sid,)):
        g.analyses[r["analysis_id"]] = {"algorithm_version": r["algorithm_version"], "scope": json.loads(r["scope_json"]),
                                        "result": json.loads(r["result_json"])}
    if "evid" in keep:      # evidence without its details text
        from geographer.model import Evidence
        for raw in self.connection.execute("SELECT evidence_id,relationship_id,category,repo_id,revision,rel_path,start_line,end_line,extractor_version,confidence,trace_ref,window_start,window_end FROM evidence WHERE snapshot_id=? ORDER BY evidence_id", (sid,)):
            r = tuple(raw)
            g.evidence[r[0]] = Evidence(evidence_id=r[0], relationship_id=ids.get(r[1], r[1]), category=intern(r[2]), repo_id=intern(r[3]),
                                        revision=intern(r[4]), rel_path=r[5], start_line=r[6], end_line=r[7], details_json="",
                                        extractor_version=intern(r[8]), confidence=r[9], trace_ref=r[10], window_start=r[11], window_end=r[12])
    return g


if mode in ("lean", "compact"):
    SnapshotStore.graph = lean_graph if mode == "lean" else compact_graph
if mode == "compact":
    from geographer import analysis as _an
    _orig_init = _an.TreeIndex.__init__

    def _init(self, graph):                                       # same tree, without the binary-lifting table
        import json as _j
        saved = {eid: e.ancestors_binary_lifting_json for eid, e in graph.entities.items()}   # '[]' defaults
        _orig_init_patched(self, graph)

    def _orig_init_patched(self, graph):
        self.graph = graph
        self.children = {eid: [] for eid in graph.entities}
        self.parents = {eid: e.parent_id for eid, e in graph.entities.items()}
        roots = []
        for eid, parent in self.parents.items():
            if parent is None:
                roots.append(eid)
            else:
                self.children[parent].append(eid)
        if len(roots) != 1:
            raise ValueError("Tree requires one root")
        self.root = roots[0]
        for cs in self.children.values():
            cs.sort()
        self.leaf_order = []; self.intervals = {}
        stack = [(self.root, False)]; starts = {}
        while stack:
            eid, leaving = stack.pop()
            if leaving:
                self.intervals[eid] = (starts[eid], len(self.leaf_order)); continue
            starts[eid] = len(self.leaf_order)
            stack.append((eid, True))
            if self.children[eid]:
                stack.extend((c, False) for c in reversed(self.children[eid]))
            else:
                self.leaf_order.append(eid)

    def _lca(self, x, y):                                         # parent walk: at most tree depth steps
        e = self.graph.entities
        while e[x].depth > e[y].depth:
            x = self.parents[x]
        while e[y].depth > e[x].depth:
            y = self.parents[y]
        while x != y:
            x = self.parents[x]; y = self.parents[y]
        return x

    _an.TreeIndex.__init__ = _orig_init_patched
    _an.TreeIndex.lca = _lca

cat = GraphCatalog(cat_path); row = cat.graph(gid); router = GraphRouter(cat)
key, service = router.acquire(gid); sid = row["snapshot_id"]
r0 = rss(); t = time.time()
ctx = service._context(sid)
load = time.time() - t
g, tree = ctx["g"], ctx["tree"]
out = dict(label=row["label"].split("-", 1)[1], mode=mode, entities=len(g.entities), relationships=len(g.relationships),
           evidence=len(g.evidence), analyses=len(g.analyses), load_s=round(load, 1), rss_mb=round(rss() - r0))


def request(focus, radius=1, grouping=False):
    d = dict(schema_version="1.0", request_id="spike", snapshot_id=sid,
             budget=dict(limit_tokens=32768, tokenizer="o200k_base", allow_byte_fallback=False),
             focus_id=focus, revealed_ids=[], pins=[], context_radius=radius, filter=copy.deepcopy(DEFAULT_FILTER),
             layout_version="sphere-pack-v1", seed="view-v1", beta=.8,
             edge_lens=dict(enabled=False, center=[0, 0, 0], radius=5., strength=.8), node_budget=120, curve_budget=200,
             viewport=dict(width_px=1440, height_px=900, device_pixel_ratio=1),
             camera=dict(eye=[0, 0, 100], target=[0, 0, 0], up=[0, 1, 0], fov_y_degrees=45, near=.01, far=10000))
    if grouping:
        d.update(schema_version="1.1", layout_version="sphere-affinity-v1", identity_mode="canonical_map",
                 grouping=dict(mode="atomic"))
    return d


if with_frames:
    roots = sorted(e.entity_id for e in g.entities.values() if e.kind == "repository")
    focus0 = roots[0] if len(roots) == 1 else tree.root
    kids = [k for k in tree.children.get(focus0, [])][:3]
    cases = [("root r1", focus0, 1, False), ("root r2", focus0, 2, False)] + \
            [(f"child{i} r2", k, 2, False) for i, k in enumerate(kids)] + [("root atomic", focus0, 1, True)]
    digests, times = {}, []
    for name, focus, radius, grouping in cases:
        service.query("viewport_frame", request(focus, radius, grouping))          # warm
        ts = []
        for _ in range(3):
            t = time.perf_counter()
            with service.lock:
                res = service.query("viewport_frame", request(focus, radius, grouping))
            ts.append((time.perf_counter() - t) * 1000)
        times.append(statistics.median(ts))
        ok = "error" not in res
        body = json.dumps(res, sort_keys=True, default=str)
        digests[name] = (hashlib.sha256(body.encode()).hexdigest()[:12] if ok else "ERR:" + str(res.get("error", {}).get("message", ""))[:60])
    out["frame_ms_median"] = round(statistics.median(times), 1)
    out["digests"] = digests
print(json.dumps(out))
