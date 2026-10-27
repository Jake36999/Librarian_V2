# INDEX-05 packaged Browser and Cowork adapters

Date: 2026-10-27
Implementation: `788540e`
Status: partial; packaged Browser/Cowork runtime accepted locally, INDEX-05/G1 open

## Delivered boundary

This packet executes the shipped Browser surface and Cowork protocol adapter
simultaneously against one Core installed from the candidate wheel. The
acceptance harness creates a fresh environment outside the checkout, removes
inherited Python source paths, installs the exact wheel with its MCP extra and
safely extracts the actual `librarian-cowork.zip`.

The extracted root `.mcp.json` must contain exactly the shipped Librarian
server declaration. Its bare `resource-librarian` command must resolve inside
the isolated environment; the harness then passes that manifest command and
arguments unchanged to the real MCP client.

Meanwhile an installed Edge browser renders the UI served from the installed
wheel. It completes the UI startup APIs and a read-only Search, signals ready
atomically and remains connected while the packaged Cowork command lists tools
and calls `vault_status`. Only after that call completes is the page released;
the same page then rechecks authenticated `/api/meta`. The harness requires
exactly one shared Core and a clean authenticated stop with no residual lease
or discovery record.

The page token is passed to the Node driver only through environment state,
never as a command argument. The driver captures it and deletes the variable
before Playwright launches the browser child.

CI extends the existing Windows adapter job with the Python 3.13 packaged
smoke. Candidate and stable release workflows also gate their packaged
adapters, and the stable path resolves dependencies from its reviewed offline
wheelhouse. These paths are configured and syntax-checked; hosted execution is
not claimed in this report.

## Verification

Syntax and fast contracts:

```powershell
node --check ui\packaged-smoke.mjs
& .\.venv\Scripts\python.exe -m pytest -q tests\test_packaged_adapter_smoke.py tests\test_installed_wheel_smoke.py -p no:cacheprovider
```

The Node check passed. PowerShell AST and both changed workflow YAML files also
parsed. The combined contracts passed **11 tests in 0.21s**.

Focused normal-host regression:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests\test_packaged_adapter_smoke.py tests\test_installed_wheel_smoke.py tests\test_release_versions.py tests\test_host_lifecycle.py tests\test_mcp.py tests\test_source_identity.py -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **44 passed in 27.06s**. A prior restricted-sandbox combined attempt
could not create an asyncio socket; the normal-host result above replaces that
environment-only attempt.

Independent packaged-adapter replay:

```powershell
& .\scripts\smoke-packaged-adapters.ps1 `
  -Python .\.venv\Scripts\python.exe `
  -Wheel tmp\release-prereq-check-host-20261027\core\resource_librarian-2.1.0.dev0-py3-none-any.whl `
  -CoworkZip tmp\release-prereq-check-host-20261027\cowork\librarian-cowork.zip `
  -WorkRoot C:\Users\jakem\AppData\Local\Temp\librarian-packaged-adapters-root-review-02
```

Result: **passed**. The actual packaged command resolved inside the fresh venv,
the installed browser and Cowork process overlapped against exactly one Core,
**140 MCP tools** were listed, `vault_status` reached that Core, the same page
completed its post-MCP API check, and shutdown left no lease or discovery
record.

Frozen-source full default-suite verification against `788540e`:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider -W error::pytest.PytestUnhandledThreadExceptionWarning -o faulthandler_timeout=90
```

Result: **1,464 passed, 2 skipped, 3 deselected in 500.98s (8m20s)**.

## Limits and remaining boundary

This proves the packaged Cowork manifest and MCP protocol, not execution inside
the real Claude/Cowork host UI. It uses an installed browser but does not prove
the Obsidian application or SecretStorage integration. The configured hosted
jobs have not run, local installed-wheel evidence remains CPython 3.11 only,
and no signed stable bundle was created.

INDEX-05/G1 therefore remains open for hosted matrix evidence, Python
3.12/3.13 runtime evidence, external real-host evidence, a signed stable
bundle, unsupported long-lived external handles, large attachments and encoder
writer occupancy.
