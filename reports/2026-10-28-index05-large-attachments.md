# INDEX-05 large managed attachments

Date: 2026-10-28
Implementation: `901ec65`
Status: partial; large-attachment work shape characterized, amplification open

## Delivered boundary

This packet adds a deliberate slow characterization of real single-source
acceptance with **80 MiB** of managed attachment input: a 64 MiB raw PDF and a
16 MiB cleaned Markdown attachment. Both are created and hashed incrementally,
then promoted through the coordinated `App` and `VaultWriter` path.

The fixture proves that every instrumented attachment read supplies an
explicit positive size no larger than **1 MiB**. It retains and re-hashes both
originals, verifies byte-exact destination sizes and SHA-256 digests, requires
the accepted source and staging state to agree, checks the index row and SQLite
integrity, finds no attachment temporary file, drains both queues and verifies
clean writer/index-worker teardown.

The first attachment read is paused deliberately. During that pause, a Browser
`get_note` call and a Cowork/MCP `vault_status` call complete against the same
Core in **0.047s**. This is bounded scheduling evidence for unrelated reads,
not a general response-time target.

## Verification

Independent slow characterization:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_index_large_attachments.py -m slow -rP -s -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=120
```

Result: **1 passed in 7.18s**. The acceptance portion reported 2.859s on this
host. Its work-shape metrics were:

- logical attachment bytes: **83,886,080**;
- attachment bytes read: **2,332,033,024**;
- scan amplification: **27.8x**;
- attachment read calls: **2,279**; and
- maximum read block: **1,048,576 bytes**.

Focused default-marker companion:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_core_source_promotion.py tests\test_index_large_attachments.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **41 passed, 1 deselected in 25.86s**. The deselected case is the
explicit slow characterization above.

Frozen-source full default-suite verification against `901ec65`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,466 passed, 2 skipped, 4 deselected in 497.98s (8m17s)**.

## Limits and remaining boundary

This is a work-shape characterization, not a latency, RSS, throughput or
capacity benchmark. It proves streaming and exactness but deliberately records
rather than hides the current repeated-fingerprint cost: promotion reads 27.8
times the logical attachment footprint in this fixture.

INDEX-05/G1 remains open for reducing that scan amplification and releasing
the writer during encoder work. Hosted Python-matrix/signing evidence and the
external real host applications also remain outside this local packet.
