# Librarian operator guide

## Install paths

For development from this source tree, run `Setup.bat` or install the project
in editable mode.  Editable installation is intentionally developer-only: it
runs the working tree and does not make a release provenance claim.

A production Windows release is installed with the bundle's adjacent
`installer/bootstrapper.ps1`, not a script copied from a source checkout. The
bootstrapper verifies the manifest's SHA-256 digests before installation, uses
only the supplied wheelhouse, and does not fall back to a network package
index.  It also copies the verified Obsidian and Cowork bundles into
`<install root>\adapters`. A release bundle is not valid until its manifest has
real artifact hashes and its detached CMS signature verifies. Obtain the
bootstrapper from the signed release channel; its own distribution should be
Authenticode-signed before execution.

Release engineering has two deliberately separate paths.  A normal
`build-release.ps1` invocation produces a non-installable candidate.  The
controlled stable job invokes `build-release.ps1 -Stable` with a generated
release-lead manifest, `pip-compile --generate-hashes` lock, and matching
offline wheelhouse; it then signs the resulting manifest and runs the
self-contained verifier.  A missing artifact, evidence record, hash lock, or
signing certificate is a release failure, not an implicit downgrade to a
candidate.  Build into a fresh, empty output directory; the script refuses to
reuse one so an older wheel can never be mistaken for the current candidate.

## One Core per mutable vault

Start a Core through the explicit Host lifecycle commands:

```powershell
librarian host start --vault D:\Research --open
librarian host status
librarian host doctor
librarian host restart --vault D:\Research
librarian host stop
```

`resource-librarian` is equivalent during 2.x.  Host is intentionally
user-controlled: it has no browser-tab reference count and no idle reaper.
Closing a browser tab never stops a Core.  Stop or Quit is explicit, and the
Core flushes its writer work before a normal shutdown.

### Windows tray companion

Stable Windows bundles also install `LibrarianHost.cmd`.  It opens a small
per-user notification-area companion with **Open**, **Status**, **Doctor**,
**Restart**, **Stop**, and **Quit**.  It is a UI over the same Host commands,
not a service: its 15-second status refresh never starts, stops, or reaps a
Core.  Open starts a selected vault on demand; browser and Obsidian windows
can close without changing Core lifetime.

Stop and Quit show an explicit confirmation.  If the Core has a session,
evaluation, queued Clerk task, or engagement in progress, the Core returns
the active-work warning; the companion presents a separate, explicit
force-quit choice.  A Core using Obsidian SecretStorage remains restartable
only from the Obsidian settings, rather than allowing the tray to lose the
adapter-managed secret injection.

A write-capable CLI does not write beside an active Core.  It either obtains
the vault lease or returns a clear `vault_in_use` response.  Use the active
Core/API or stop it before a direct mutation.  A diagnostic stale lease is not
silently stolen; use `app --takeover` only after verifying the former Core is
gone.

## Health and recovery

`librarian --vault D:\Research doctor` reports vault health.  `librarian host
doctor` additionally reports Host state.  The Core health endpoint is
`/api/meta`; it is the source of truth for Core version, protocol compatibility,
non-secret health, dynamic-port state, lease state, and enabled features.

When a provider is unavailable, durable session state stays in the vault.  The
recovery policy retries bounded transient failures, opens circuit breakers,
and pauses/requeues Clerk work.  It does not silently select another model:
cross-model failover is a checkpoint for a person.

## Secrets

Desktop and browser mode use the Windows OS keychain by default.  Environment
secrets are discovered as read-only sources.  The encrypted-file fallback is
only for environments without a supported keychain; it resolves the effective
Windows principal/SID, writes atomically, and surfaces structured errors
rather than HTTP 500s.

The production dependency set includes `keyring`, which selects Windows
Credential Manager on supported Windows systems.  A fallback is therefore a
visible unsupported-backend condition rather than the ordinary install path.
When a fallback file already exists, Settings → Connections exposes an
explicit **Move fallback keys to keychain** action.  It copies every saved
credential into the effective user's keychain first, keeps the fallback on any
failure, and never returns credential values to the browser.

Obsidian has a separate contract.  The plugin selects secrets from Obsidian
SecretStorage and injects them only into the Core child process's memory at
start.  The Core marks these keys `obsidian_managed`, never persists them, and
does not accept `/api/keys` writes for them.  The browser view attached to that
Core delegates key changes to Obsidian settings.  Rotating a key restarts the
Core; tokens do not traverse loopback HTTP.

## Updates and rollback

The first stable line uses manual, reversible updates:

1. Stop the relevant Core through Host.
2. Keep the former release bundle and manifest.
3. Install the new verified bundle with the bootstrapper.
4. Start it and inspect `/api/meta` and `doctor`.
5. If compatibility or health fails, stop it and reinstall the former bundle.

Vault data is not an installer payload.  Do not use an update process that
replaces or deletes vault Markdown, evidence, sessions, staging, or migration
manifests.

