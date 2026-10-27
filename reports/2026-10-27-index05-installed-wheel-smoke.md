# INDEX-05 clean installed-wheel smoke

Date: 2026-10-27
Implementation: `6fb2389`
Status: partial; Python 3.11 installed-wheel runtime accepted locally, INDEX-05/G1 open

## Delivered boundary

This packet turns the previously inspected candidate wheel into an executable
artifact check. `scripts/smoke-installed-wheel.ps1` creates a fresh virtual
environment outside the source checkout, removes inherited `PYTHONPATH` and
`PYTHONHOME` from every child, installs the exact wheel with its MCP extra and
proves that the imported package lives under that isolated environment.

The smoke verifies both installed console scripts, distribution/package
version agreement, the packaged UI and both expectation-resource families. It
initialises a new vault, starts the installed Host Core on a dynamic loopback
port, fetches `/`, `/app.js`, `/app.css` and authenticated `/api/meta`, then
launches the installed `resource-librarian` MCP server. The real MCP client
lists tools and calls the read-only `vault_status` tool through the live Core.
Finally, the installed Host performs an authenticated graceful stop and the
smoke requires the lease and discovery records to be gone.

CI now defines an independent Windows wheel-smoke matrix for CPython
3.11--3.13. Candidate release construction runs the same artifact check before
upload, while stable construction runs it before signing and resolves
dependencies only from the reviewed offline wheelhouse. These workflow paths
are configured and syntax-checked; they have not run in a hosted CI job in
this evidence packet.

## Verification

Fast contract verification:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_installed_wheel_smoke.py -p no:cacheprovider
```

Result: **6 passed in 0.13s**. The PowerShell parser accepted the smoke script,
and both changed workflow YAML files parsed successfully.

Focused source regression on the normal host:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_installed_wheel_smoke.py tests\test_release_versions.py tests\test_host_lifecycle.py tests\test_source_identity.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **19 passed in 4.59s**. The first in-sandbox invocation passed 15 and
failed four Host cases because the redirected Windows sandbox denied atomic
`os.replace`; the identical normal-host rerun above replaces that
environment-only result.

Independent artifact replay used the candidate wheel built by the preceding
prerequisite packet and a fresh external work root:

```powershell
& .\scripts\smoke-installed-wheel.ps1 `
  -Python .\.venv\Scripts\python.exe `
  -Wheel tmp\release-prereq-check-host-20261027\core\resource_librarian-2.1.0.dev0-py3-none-any.whl `
  -WorkRoot C:\Users\jakem\AppData\Local\Temp\librarian-wheel-smoke-root-review-01
```

Result: **passed**. The clean environment installed version `2.1.0.dev0`,
listed **140 MCP tools**, called `vault_status` against the live installed Core,
served the packaged UI/API and stopped without residual lease or discovery
metadata.

Frozen-source full default-suite verification against `6fb2389`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,459 passed, 2 skipped, 3 deselected in 518.59s (8m38s)**.

## Limits and remaining boundary

Only CPython 3.11 was available for the local artifact replay. The configured
3.12/3.13 jobs have not yet supplied results, and no signed stable bundle was
created. Fetching packaged Browser resources is not real browser automation;
the smoke drives the Cowork-compatible MCP protocol but not the real
Claude/Cowork host UI. Real Obsidian execution remains externally blocked by
the missing Obsidian/SecretStorage environment.

INDEX-05/G1 therefore remains open for hosted 3.11--3.13 matrix evidence,
simultaneous packaged Browser/Cowork runtime evidence, externally provided
real-Obsidian evidence, a signed stable bundle, unsupported long-lived
external handles, large attachments and encoder writer occupancy.
