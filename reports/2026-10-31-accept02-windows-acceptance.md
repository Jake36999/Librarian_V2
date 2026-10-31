# ACCEPT-02 Windows acceptance pass

Date: 2026-10-31

Repository revision: `716ac10` (`UX-01: add per-predicate audit inspector`)

Status: **in progress — local artifact boundary passed; real Obsidian, real Claude/Cowork UI and live Docker remain**

This packet records a fresh Windows pass on a repository-built candidate. It
does not close ACCEPT-02: the plan explicitly requires real Obsidian with
SecretStorage, the real Claude/Cowork host interface, real external application
handles and a fresh live-Docker pass. Those environments were not available in
this session and are listed as hands-on checks below.

## Environment

| Component | Observed identity |
| --- | --- |
| OS | Microsoft Windows 11 Home 25H2, build 26200.9711 |
| Python | CPython 3.11.3 |
| Node / npm | Node v24.13.0 / npm 11.21.0 |
| Git | 2.52.0.windows.1 |
| Browser | Chrome 156.0.8078.76; Edge 156.0.4314.50 |
| Docker | client 29.8.1; Desktop daemon not running |
| WSL | WSL2; default distribution Ubuntu |
| Obsidian | executable not found in the standard per-user or Program Files install roots |

Docker was not started automatically. The pass therefore records Docker as
unavailable and verifies the explicitly labelled non-isolated fallback; it
does not reuse the 2026-10-30 live-Docker result as if it were fresh evidence.

## Candidate artifact

Built with:

```powershell
& .\scripts\build-release.ps1 `
  -Python .\.venv\Scripts\python.exe `
  -OutDir .\tmp\accept02-716ac10-candidate `
  -SkipTests
```

The full suite had already passed at the same revision before the artifact
build: 1,923 passed, 2 skipped, 5 deselected. The build reran both shared UI
and Obsidian TypeScript checks and produced a deliberately non-installable
development candidate.

| Artifact | SHA-256 |
| --- | --- |
| `core/resource_librarian-2.1.0.dev0-py3-none-any.whl` | `b341e1cf07219c9e76be926af959119da07bee48ceee3f9e1881bf2d650b570c` |
| `obsidian/librarian-obsidian.zip` | `559f8a4fca28a0f89671aaa8032034c2e5e33d4492ea5715b0cfc2e8345f46e4` |
| `cowork/librarian-cowork.zip` | `068c2cf2337bb5c4c03e7c080bbaf4e537a5785af70e331ab8542c9d2a030291` |

## Results run here

### Focused Windows contracts

```powershell
& .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider `
  -W error::pytest.PytestUnhandledThreadExceptionWarning `
  -o faulthandler_timeout=90 `
  tests\test_host_lifecycle.py `
  tests\test_obsidian_adapter_contract.py `
  tests\test_core_mixed_acceptance.py `
  tests\test_core_concurrency.py `
  tests\test_index_external_sqlite_handle.py `
  tests\test_adoption.py `
  tests\test_workspace_documents.py `
  tests\test_accept_workbench.py `
  tests\test_workbench_boundaries.py `
  tests\test_packaged_adapter_smoke.py `
  tests\test_installed_wheel_smoke.py
```

Result: **106 passed, 1 deselected in 58.67 seconds**.

This covers the source-level Host lifecycle, dirty-document and writer
coordination contracts, Windows external SQLite handle characterization,
adopted/attached roots, workspace documents, explicit non-isolated execution
labelling and packaged-smoke contracts. It is not evidence that the real
Obsidian or Claude processes obey those contracts.

### Installed-wheel lifecycle

`scripts/smoke-installed-wheel.ps1` installed the exact wheel with its MCP
extra into a fresh external venv, initialized a fresh vault, started one Core
on a dynamic loopback port, fetched the packaged UI and authenticated metadata,
listed and called tools over the installed MCP process, then stopped cleanly.

Result: **passed; version 2.1.0.dev0; 148 MCP tools; no residual Core lease or discovery record**.

### Simultaneous packaged Browser and Cowork protocol

`scripts/smoke-packaged-adapters.ps1` installed the same wheel, safely
extracted the exact Cowork ZIP and kept a real packaged browser connected while
the command declared by the Cowork bundle listed tools and called the shared
Core. The browser then rechecked the authenticated API before shutdown.

Result: **passed; one Browser, one packaged Cowork command, one Core, 148 tools, clean stop**.

This proves the packaged protocol adapter, not execution inside the Claude
desktop/Cowork UI.

### Rollback rehearsal

The installed-wheel venv was first force-reinstalled from the current
candidate, then force-reinstalled from the retained 2026-10-27 candidate. The
common `resource_librarian.app` module changed from SHA-256
`17a1d1f14d19bf8b0654b49b1fa4e21d1e6a061dae9df0b1e612a39475542249`
to `cbe2eea212e690b68de6ae68e28d4a7637dcba829cb1f252717b1f2b1da2ddeb`,
proving different package bytes were active. The rolled-back `doctor` command
passed every required check.

All vault files outside `.librarian/runtime/**` were hashed before and after;
the sets and hashes were identical. Runtime operation telemetry was excluded
because running the lifecycle check is itself expected to append telemetry.

Result: **rollback succeeded; required health green; user content and durable non-runtime vault state unchanged**.

## Honest gaps and owner hands-on checklist

Run these against the candidate above (or a later frozen replacement) and add
versions, screenshots/log paths and pass/fail notes to this report.

- [ ] Record the exact Obsidian version and install the candidate Obsidian ZIP
  into a disposable copy of a real vault.
- [ ] Set a provider key through Obsidian SecretStorage; confirm the Core marks
  it `obsidian_managed`, the browser cannot overwrite it, no value appears in
  loopback responses or vault files, and rotating it restarts the Core.
- [ ] With a note dirty in Obsidian, attempt a Core write to that same note.
  Confirm the document-specific checkpoint appears, the unsaved editor text is
  retained, and a different note can still be written.
- [ ] Keep Browser, Obsidian and the real Claude/Cowork UI attached to the same
  Core. Under mixed read/write traffic, confirm one vault lease, ordered writer
  completion, no `SQLITE_BUSY`, no lost JSONL events and clean reconnect after
  one client closes.
- [ ] Hold a Markdown file and the index database open from real external
  applications. Confirm the documented refusal/retry behaviour and that no
  process reports success after a failed write.
- [ ] Start Docker Desktop manually. Record Docker Desktop, engine and WSL2
  versions, then run `scripts/workbench_live_check.py` with a freshly resolved,
  pinned `python:3.11-slim@sha256:...` image. Retain its JSON output.
- [x] With Docker unavailable, confirm only `non_isolated_host_exec` is
  offered as executable fallback, requires both confirmations and makes no
  network-isolation claim. Covered by the focused tests above.
- [x] Rehearse rollback between retained candidate wheels and confirm the vault
  content hash is unchanged. Covered above.

ACCEPT-02 closes only when every unchecked real-host item passes and the exact
Obsidian/Docker versions and retained evidence are added. RELEASE-03 still
requires the separate frozen, signed-bundle pass.
