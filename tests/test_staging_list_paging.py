"""staging_list counts from cached summaries and reads only the page in full (2026-11-18)."""
from resource_librarian import staging, tools  # noqa: F401
from resource_librarian.init import init
from resource_librarian.registry import REGISTRY, Context
from resource_librarian.vault import Vault


def test_a_page_reads_only_its_own_items(tmp_path, monkeypatch):
    init(tmp_path / "lib"); vault = Vault(tmp_path / "lib")
    store = staging.StagingStore(vault)
    for n in range(30):
        store.add({"id": f"src-{n:02d}", "kind": "source", "name": f"Source {n}", "evidence": []})
    loads = []
    real = staging.StagingStore.load
    monkeypatch.setattr(staging.StagingStore, "load", lambda self, i: loads.append(i) or real(self, i))
    out = REGISTRY.call("staging_list", {"kind": "source", "status": "staged", "limit": 5, "offset": 10},
                        Context(tier="consult", vault=vault))
    assert out["total"] == 30 and [i["id"] for i in out["items"]] == [f"src-{n:02d}" for n in range(10, 15)]
    assert len(set(loads)) <= 5                       # only the page's items were read in full
