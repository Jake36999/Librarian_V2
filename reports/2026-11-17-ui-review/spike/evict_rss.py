"""Does evicting a graph return its memory? Real NFL graphs, throwaway process, catalog copy."""
import ctypes, ctypes.wintypes as wt, gc, sys, time


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


from geographer.graph_catalog import GraphCatalog
from geographer.graph_router import GraphRouter

cat = GraphCatalog(sys.argv[1])
router = GraphRouter(cat)                       # default cap
by_label = {r["label"].split("-", 1)[1]: r for r in cat.graphs()}
order = ["quantule_mapper-docs", "quantule_mapper", "quantule_mapper-data", "third-party", "quantule_mapper-docs"]
# the largest first, so the drop when it is evicted is visible
print(f"cap={router.max_loaded} start rss {rss():.0f} MB")
for name in order:
    row = by_label[name]
    t = time.time()
    with router.lease(row["graph_id"]) as service:
        ctx = service._context(row["snapshot_id"])
        n = len(ctx["g"].entities)
    del ctx
    gc.collect()
    resident = sorted(by_label_key for by_label_key in
                      (next(l for l, r in by_label.items() if r["graph_id"] == k[0]) for k in router.services))
    print(f"open {name:24s} entities={n:7d} {time.time()-t:5.1f}s  rss {rss():7.0f} MB  resident={len(resident)}: {resident}")
