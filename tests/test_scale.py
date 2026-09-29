"""The per-write cost follows the change, not the vault (plan: Scale targets)."""
import time

import pytest

from resource_librarian.index import Index
from resource_librarian.init import init
from resource_librarian.vault import Vault

from conftest import add_source

WORDS = ("parser stream graph cache queue schema lineage tensor mesh solver sensor "
         "packet ledger kernel shader vector index crawler").split()


def _vault(tmp_path, n):
    init(tmp_path / f"v{n}")
    vault = Vault(tmp_path / f"v{n}")
    for i in range(n):
        a, b, c = WORDS[i % 18], WORDS[(i * 7) % 18], WORDS[(i * 13) % 18]
        add_source(vault.root, f"source {i:05d}",
                   f"A {a} tool that handles {b} and {c} for case {i}.",
                   f"It solves {a} {b} problems at scale number {i}.",
                   reading=f"Checked on {i % 28 + 1} September.")
    return vault


def _one_write(vault):
    with Index(vault) as ix:
        started = time.perf_counter()
        ix.refresh()
        build = time.perf_counter() - started
        path = vault.root / "Sources" / "repository" / "source 00007.md"
        path.write_text(path.read_text().replace("case 7.", "case seven, revised."))
        started = time.perf_counter()
        assert ix.upsert(path)
        return build, time.perf_counter() - started


@pytest.mark.slow
def test_one_note_write_is_flat_from_1000_to_5000(tmp_path):
    build_1k, write_1k = _one_write(_vault(tmp_path, 1000))
    build_5k, write_5k = _one_write(_vault(tmp_path, 5000))
    assert write_1k < 1.0 and write_5k < 1.0
    # "not measurably slower": within noise, bounded generously for shared CI.
    assert write_5k < max(0.05, write_1k * 5), (write_1k, write_5k)
    assert build_1k < 60
    print(f"\nbuild 1k {build_1k:.1f}s 5k {build_5k:.1f}s; "
          f"one write 1k {write_1k * 1000:.1f}ms 5k {write_5k * 1000:.1f}ms")
