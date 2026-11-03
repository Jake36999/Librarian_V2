# ACCEPT-02 Windows acceptance pass

Date: 2026-10-31; refreshed 2026-11-03

Repository revision: original packet at `716ac10`; current-candidate refresh at
`bdfd834` (`REMED-07: qualify model view and reachability`)

Status: **in progress — local artifact, live-Docker, real Obsidian UI, dirty-document and SecretStorage boundaries passed; real Claude/Cowork mixed traffic and external-application handles remain**

The original 2026-10-31 packet records a fresh Windows pass on a
repository-built candidate. At that time real Obsidian with SecretStorage, the
real Claude/Cowork host interface and real external application handles were
unavailable. Dated refreshes below supersede the original gaps for live Docker,
real Obsidian UI, dirty-document coordination and SecretStorage. ACCEPT-02
remains open only for the still-unchecked hands-on items below.

## Environment (original 2026-10-31 packet)

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

## 2026-11-02 current-candidate refresh

The local artifact boundary was repeated after REMED-07 at exact revision
`bdfd8344ad1408a4c5eef4e4bf55984f147b1e23`. This refresh supersedes the
candidate hashes above, but does not replace or waive any unchecked real-host
item below.

The complete Python suite at this revision passed with **1,935 passed, 2
skipped and 5 deselected**. A fresh focused Windows packet passed **106 tests
with 1 deselected**. The release build reran the shared UI and Obsidian builds,
then produced this unsigned, deliberately non-installable development
candidate:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `core/resource_librarian-2.1.0.dev0-py3-none-any.whl` | 1,054,355 | `cb7b6ca692e1a172e5c0d5c6a9a0d623b2e53337d97ecf8d6f32320686f27c5d` |
| `obsidian/librarian-obsidian.zip` | 84,957 | `559f8a4fca28a0f89671aaa8032034c2e5e33d4492ea5715b0cfc2e8345f46e4` |
| `cowork/librarian-cowork.zip` | 9,462 | `068c2cf2337bb5c4c03e7c080bbaf4e537a5785af70e331ab8542c9d2a030291` |
| `release-manifest.json` | 2,038 | `0c56cd98b76de1fc1549437a32a0f69666df5c9463afa51d4bd08a1bdcc0ae09` |

The manifest identifies UI build `2.1.0.dev0-bdfd8344ad14`, status
`development_template`, and signing status `not_signed`.

The clean installed-wheel smoke passed with version `2.1.0.dev0`, 148 MCP
tools, authenticated packaged UI/API access and a clean Host shutdown. The
packaged-adapter smoke also passed with one real browser, the command from the
Cowork bundle, 148 tools, one shared Core and a clean stop. These remain
protocol/package checks rather than claims about execution inside the real
Claude/Cowork desktop UI.

The rollback rehearsal was repeated in a fresh external venv and disposable
vault. Candidate Doctor and rollback Doctor each had zero failed required
checks. The installed `resource_librarian.app` hash changed from
`1224c9cdecde9543b4ef5b5f7bc4281992646719277cc2478f3ddb61d604e95f`
to `cbe2eea212e690b68de6ae68e28d4a7637dcba829cb1f252717b1f2b1da2ddeb`,
proving that different package bytes were active. Hashing every vault file
outside `.librarian/runtime/**` after Doctor on each version found zero added,
removed or changed durable files.

At the time of the artifact refresh, Docker client 29.8.1 was present but its
Desktop daemon was unavailable, and no Obsidian executable was found. The
subsequent section supersedes that statement for Docker only; no
SecretStorage, dirty-note or real three-client evidence is inferred.

## 2026-11-02 live-Docker refresh

Docker Desktop was started after the candidate refresh. Against current pushed
revision `7029c68db49f9f3b643249cc0b7eb202b4177c5e` (documentation-only changes
after artifact candidate `bdfd8344ad1408a4c5eef4e4bf55984f147b1e23`), the
live Workbench check used:

- Docker Desktop 4.93.0 (240920), client and engine 29.8.1, API 1.56;
- Linux engine on amd64, kernel `6.18.54.1-microsoft-standard-WSL2`;
- WSL 3.0.3.0 and WSL kernel 6.18.54.1-1; and
- freshly pulled and digest-pinned image
  `python@sha256:db20d8506e2f15b6db39b40b6015ca46bae855dec6dd326d462cfe79ae972893`.

The exact metadata and raw results are retained in
`reports/2026-11-02-accept02-live-docker.json` (3,685 bytes, SHA-256
`537411d8765c4254bf36d298ad2cd1cdbce34dd00f82e539bd03e3e982c86c76`).

All three hostile cases exited successfully while enforcing the boundary: 9
MB stdout was measured but only 8,000 characters retained; the byte-limited
export stopped before a 3 MB file crossed its 1 MB limit; the count-limited
export stopped after ten files; and the type-only run refused its FIFO and
symbolic link while retaining the hard-linked names and nested file. The
benign case exported one three-byte `hi\n` result. Post-run inspection found no
residual live-check containers or volumes. Docker's builtin seccomp profile is
relied upon, not independently proved.

Result: **fresh live-Docker acceptance passed.** This closes only the Docker
check, not the real Obsidian, Claude/Cowork, mixed-client or external-handle
requirements.

## 2026-11-03 real-Obsidian and dirty-document refresh

The supplied `D:\Testing Folder` was a genuine Obsidian vault containing 163
files, including 42 Markdown files and mixed PDF, image, Office, Canvas and
HTML content. Its inherited D-drive ACL allowed directory creation but not
writes inside newly created directories, so fingerprinted adoption stopped
without retaining `.librarian` state or changing an existing file.

A byte-verified working copy was made at
`C:\Users\jakem\Librarian ACCEPT-02 Vault`. All 163 copied files matched their
source SHA-256 values. The copy was adopted under survey fingerprint
`a7154dfe13eb9bb312fb9609ea19b855`; every pre-existing file remained
byte-identical.

The exact `bdfd834` candidate wheel was installed in a fresh external venv and
the exact candidate Obsidian ZIP was installed beside the existing Excalidraw
and Tasks plugins. All required Doctor checks passed. The launcher executable
at `D:\obsidian\Obsidian.exe` reports file version 1.12.7.0; a running window
title reported runtime 1.15.0. The exact in-app About version still needs to be
retained before the version checklist item closes.

The person opened the copied vault in real Obsidian and confirmed that the
Librarian plugin loaded, every button behaved as expected, and the Chat,
Staging, Search, Sessions and Checkpoints pages rendered. The plugin-owned Core
reported version 2.1.0.dev0, protocol 2, compatible adapter range `>=2,<3`, one
held vault lease, ready writer and index, 44 watched Markdown files, and
`secret_source: obsidian_managed`. No provider secret had yet been selected.

### Real dirty-document boundary

The first asynchronous attempt depended on the ten-second heartbeat surviving
a chat round trip. It had expired before the write arrived, so the Core
correctly treated the note as inactive and accepted the update. That attempt
temporarily replaced the person's Summary sentence. The generated diff
retained the exact prior sentence; it was restored immediately. Its restored
SHA-256
`af0ba28cfef6eb1a137758050be8adbf7277b8bd30e159836454be21806729c6`
and 675-byte size matched the pre-attempt values exactly. This was a flawed
acceptance procedure, not evidence that an active lease was bypassed.

The repeat used a watcher that performed no write until the real Obsidian
lease appeared. It observed path `Projects/ACCEPT-02 Dirty Target.md`, editor
`Obsidian`, `dirty: true`, 9.9 seconds remaining and baseline prefix
`e44d84f677644d6df1dd`.

During that lease, the conflicting `update_project` call was refused as
`DOCUMENT_ACTIVE`. Checkpoint `c38bf833180dc49a` had type `write_conflict`,
default `wait`, and only `wait`, `retry_after_review` and `cancel` choices; the
person confirmed those choices in the real UI. The dirty note remained exactly
SHA-256
`e44d84f677644d6df1dde3991e06b456f4604f2e413e3a22d31a3f83484ec410`
and 677 bytes before and after. In the same lease, the unrelated project write
succeeded and changed from SHA-256
`fd9f76e732c36c46e2537fb8bc1e411251b0f2848aa73bb389278786c263f279`
to
`cc286710b237857854fcff397b56bdcba90d81f84e05af5e9300e1eff2c67725`.

Result: **the real Obsidian dirty-document boundary passed.** A live edit was
retained byte-for-byte, a document-specific person checkpoint appeared, and an
unrelated note remained writable. Sanitized raw evidence is retained in
`reports/2026-11-03-accept02-obsidian-dirty.json`.

### SecretStorage and defects found in the real host

After the initial exact-`bdfd834` dirty-document walk exposed host-integration
defects, the repaired working-tree Obsidian bundle was copied over the candidate
plugin in the disposable vault. The stale-recovery and SecretStorage checks
below therefore qualify that remediation overlay on top of the `bdfd834` base
Core; they are not claimed as tests of the unchanged old plugin ZIP. Final diff
review then hardened the same typed diagnostic by parsing it after child stdio
closed instead of at process exit; that race correction passed the focused
contracts but was not separately repeated in the real host.

Two dummy OpenAI entries were selected in turn through real Obsidian
SecretStorage. The first selection restarted the plugin-owned Core, which
reported `saved: true`, `source: obsidian_managed` and the expected last-four
indicator. A browser attempt to replace it through `/api/keys` was refused with
HTTP 409 and `managed_by: obsidian`; the selected value remained in force.
Selecting the second entry restarted the Core again and changed the reported
last-four indicator. Plugin data retained only the selected SecretStorage ID,
not either value. Neither full dummy value appeared in serialized API responses
or any vault file.

The person then selected the blank option and removed both dummy entries.
Another clean Core restart followed; the Core reported `saved: false`, and the
plugin's stored OpenAI secret ID was blank. No provider request or key check was
made. Sanitized evidence, deliberately excluding the dummy values, is retained
in `reports/2026-11-03-accept02-obsidian-secretstorage.json`.

The real-host walk also exposed three usability defects, which were repaired:

- Obsidian's host `.popover` rule could turn the model selector into a wide,
  clipped flex row. Librarian now uses the namespaced `.lib-popover` class and
  a hostile-host-CSS browser regression exercises its geometry.
- `retry_after_review` resolves a checkpoint but does not itself retry the
  write or open a separate review page. The UI now says **Mark reviewed; retry
  manually** and explains that behavior before resolution.
- After disabling and re-enabling the plugin, an exited Core could leave a
  stale vault lease. The error is now typed, and **Recover and try again** makes
  exactly one explicit takeover attempt. The person exercised that recovery in
  real Obsidian: the old Core was dead, one replacement Core started, and the
  plugin returned to the normal UI.

The shared UI smoke passes with the hostile host rule, both TypeScript bundles
build, and five focused adapter contract tests pin the namespace, checkpoint
wording and one-shot stale recovery. The complete repository suite passed
**1,938 tests, 2 skipped, 5 deselected** after the repairs. A final visual
confirmation of the repaired model selector in real Obsidian remains desirable;
the stale-recovery flow is already confirmed in the real host.

## Honest gaps and owner hands-on checklist

Run these against the candidate above (or a later frozen replacement) and add
versions, screenshots/log paths and pass/fail notes to this report.

- [x] Install the exact candidate Obsidian ZIP into a disposable copy of a real
  vault and exercise the real plugin and shared UI. Covered by the 2026-11-03
  refresh.
- [ ] Retain the exact in-app Obsidian About version. The launcher file and a
  runtime window title reported different versions.
- [x] Set a provider key through Obsidian SecretStorage; confirm the Core marks
  it `obsidian_managed`, the browser cannot overwrite it, no value appears in
  loopback responses or vault files, and rotating it restarts the Core. Passed
  with two dummy entries, followed by verified cleanup; no provider call was
  made.
- [x] With a note dirty in Obsidian, attempt a Core write to that same note.
  Confirm the document-specific checkpoint appears, the unsaved editor text is
  retained, and a different note can still be written. Passed in the
  synchronized 2026-11-03 repeat; the expired-heartbeat procedure failure and
  exact restoration are disclosed above.
- [ ] Keep Browser, Obsidian and the real Claude/Cowork UI attached to the same
  Core. Under mixed read/write traffic, confirm one vault lease, ordered writer
  completion, no `SQLITE_BUSY`, no lost JSONL events and clean reconnect after
  one client closes.
- [ ] Hold a Markdown file and the index database open from real external
  applications. Confirm the documented refusal/retry behaviour and that no
  process reports success after a failed write.
- [x] Start Docker Desktop manually. Record Docker Desktop, engine and WSL2
  versions, then run `scripts/workbench_live_check.py` with a freshly resolved,
  pinned `python:3.11-slim@sha256:...` image. Passed in the 2026-11-02 refresh;
  the exact JSON and its hash are retained above.
- [x] With Docker unavailable, confirm only `non_isolated_host_exec` is
  offered as executable fallback, requires both confirmations and makes no
  network-isolation claim. Covered by the focused tests above.
- [x] Rehearse rollback between retained candidate wheels and confirm the vault
  content hash is unchanged. Covered above.

ACCEPT-02 closes only when every unchecked real-host item passes and the exact
Obsidian/Docker versions and retained evidence are added. RELEASE-03 still
requires the separate frozen, signed-bundle pass.
