# ADAPT-11 tool-surface and result-size measurement

**Date:** 2026-10-26. **Status:** implemented on the route-neutral Core path;
no provider-specific behavior or paid call was enabled.

ADAPT-11 makes task-sized tool bundles the default for every bare `Loop`.
Callers can still request the legacy full registry explicitly with
`use_tool_bundles=False`, and helper `only` allowlists remain narrower than
either mode. The default bundle includes `read_result`, which retrieves exact
chunks from oversized read results stored only in the originating loop.

## Surface measurement

The deterministic schema measurement serialises the same tool definitions the
model receives and uses the existing conservative four-characters-per-token
estimate.

| Measurement | Legacy full surface | Default bundle | Change |
| --- | ---: | ---: | ---: |
| Offered tools | 133 | 11 | -91.7% |
| Serialised schema characters | 63,251 | 4,962 | -92.2% |
| Estimated schema tokens | 15,813 | 1,241 | -92.2% |

The bundle cap remains 12 tools. A caller which omits the bundle flag therefore
cannot expose the full registry accidentally.

## Oversized-result measurement

`search`, `get_note`, and `read_source_file` results larger than 6,000
serialised characters now return a projection of at most 4,800 characters,
rather than entering recent history at the previous 16,000-character cap. The
projection carries a loop-local `sha256:` handle. `read_result` returns chunks
of at most 3,000 characters; concatenating those chunks reconstructs the exact
deterministic JSON representation whose SHA-256 names the handle.

The deterministic 50,000-character fixture proves:

- the projection stays within 4,800 serialised characters;
- the full result is recoverable exactly, including its end marker;
- individual retrieval chunks stay within 3,000 characters; and
- a handle cannot be used from another loop.

This is a prompt/history bound and an authority-preserving retrieval seam, not
a persistent result archive. Handles expire with their loop and do not grant a
new vault or tool permission.

## Verification

The combined adapter-focused command was:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_provider_cancellation.py tests/test_model_invocation.py tests/test_model_session_evidence.py tests/test_loop.py tests/test_shutdown.py tests/test_host_local_yield.py tests/test_model_expectation_authoring.py tests/test_model_dialect.py tests/test_staging.py tests/test_arguments.py tests/test_result_handles.py tests/test_prompt_size.py tests/test_effort.py tests/test_shared_models.py -p no:cacheprovider
```

Result: **184 passed in 30.80 seconds**.

The frozen implementation commit is `6960d84`. The final repository-wide
command was:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -o faulthandler_timeout=60
```

Result: **1,417 passed, 2 skipped, 1 deselected in 472.12 seconds**. No live
provider call, route requalification, push, or release-gate closure is implied.
