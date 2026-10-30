# Release queue: externally gated work only

**Status:** Release-only queue. The authoritative implementation sequence and
delivery status are in the [unified implementation plan](unified-implementation-plan.md).
**Last reconciled:** 2026-10-30 (RELEASE-01).

This document covers the release-owner work that remains *after* applicable
implementation gates are green. It distinguishes work needing real provider
evidence, protected release credentials, or physical Windows environments. It
is deliberately not an authorization to use a provider account, publish an
artifact, or create a release record.

## Current state

Every gate from G0 to G5 is green (2026-10-30). R0 may begin once the release
owner decides to freeze a revision **and** that revision passes the entry
gates below. V2 is still not a release: the evidence for real host
applications (ACCEPT-02) and for a signed build (RELEASE-03) comes after R0.

| Gate | State on 2026-10-30 | Source |
| --- | --- | --- |
| G0 baseline attributable and honest | green | Unified plan, BASE rows. |
| G1 Core lifecycle and single-Core access | green (2026-10-28) | The plan's INDEX-05 and G1 closure. |
| G2 canonical routes; UI truth matches runtime | green (2026-10-30) | The plan's G2 and G4 closure. |
| G3 safe adoption of existing documentation roots | green (2026-10-30) | The plan's G3 closure; local evidence from DEPLOY-01 to -04. Real host applications are ACCEPT-02. |
| G4 trusted request shaping; durable route evidence | green (2026-10-30) | The plan's G2 and G4 closure. |
| G5 Session-backed long-horizon state and Tier A | green (2026-10-30) | The plan's G5 closure: 16 real audited sessions, a Tier A share of 0.432 (95% 0.326–0.546) over seven of ten verifiers, zero false closures. |

A passing local suite is necessary evidence for an implemented packet. It is
not evidence that V2 or a release is complete. The unified plan's progress log
is the source for every gate change; this table is copied from it and must be
updated when a gate changes there.

The checked-in `release-manifest.json` and
`src/resource_librarian/standard/release_leads.json` are intentionally
development templates. They must remain non-installable and
`pending_release_ci` until the evidence-backed release process below is
complete. No model, signature, dependency lock, or release artifact may be
represented as production-ready before then.

## Queue rules

- **Ready** means the repository implementation exists and the next owner can
  begin after accepting the stated input or authority.
- **Blocked externally** means it cannot be completed safely from this source
  checkout: it needs a release-owner decision, provider credentials/budget,
  protected signing material, or a real target environment.
- Completion evidence belongs with the release record or its protected CI
  artifacts. Do not replace it with an assertion in a Markdown file.
- The two lead providers remain an OpenAI route and an Anthropic route, but
  the exact snapshots must be selected and verified at release time. A
  candidate in the source tree is not an endorsement or a frozen release
  choice.

## Release critical path

```text
G0–G5 green in the unified plan, plus the SI and LC entry gates
    │
    ▼
R0 release freeze
    ├── R1 dependency lock and offline wheelhouse
    └── R2 provider qualification and release-lead evidence
              │
              ▼
       R3 protected stable build, signing, and verification
              │
              ▼
       R4 Windows/adapter acceptance and rollback rehearsal
              │
              ▼
       R5 manual publication and post-release watch
```

R0 begins only when **every** gate from G0 to G5 is green in the unified plan,
and the frozen revision passes the source-identity and lifecycle entry gates
below. "Applicable" gates are not enough: a release is a whole-product claim.
R1 and R2 may run in parallel after R0. R3 cannot start until both
have passed. R4 should exercise the final signed bundle, and R5 is an explicit
release-owner decision rather than an automated publication step.

## Entry gates for every release step

Each step from R0 to R5 starts only when its inputs pass both gates again. A
pass recorded for an earlier step does not carry over to a changed input.

**Source identity (SI)**, so that the evidence describes the source that
ships:
1. **SI-1.** The frozen revision is one commit. Its worktree is clean:
   `git status --short` is empty, or every untracked file has been reviewed
   and excluded from the build inputs. Builds and tests read that commit only.
2. **SI-2.** Tests run through the repository virtual environment. Every
   path must import the checkout under test, not a stale sibling install:
   - `tests/test_source_identity.py` passes;
   - the `doctor` source-identity check (`resource-librarian host doctor`)
     reports the frozen checkout or the built wheel.
3. **SI-3.** `python scripts/check_release_versions.py --root .` passes, so the version
   files and the adapter metadata agree.
4. **SI-4.** Every later artifact (the lock, the wheelhouse, the release-lead
   evidence, the signed bundle and the acceptance records) names the frozen
   commit. An artifact made from any other revision is not evidence for this
   release. The release verifier must confirm this in R3.

**Lifecycle (LC)**, so that the Core starts, stops and recovers as the
product claims:
1. **LC-1.** On the frozen revision, the Host and Core lifecycle suites
   pass:
   - `tests/test_host_lifecycle.py`
   - `tests/test_shutdown.py`
   - `tests/test_process_identity.py`
   - `tests/test_operation_recovery.py`
   - `tests/test_event_resync.py`
   - `tests/test_watcher_recovery.py`
2. **LC-2.** The end-to-end acceptance matrix (`tests/test_acceptance_matrix.py`
   with the tests it cites, ACCEPT-01) passes on the frozen revision.
3. **LC-3.** On the real targets, R4 repeats the lifecycle against the signed
   bundle (step 1 below): start, explicit stop, restart, a forced stop and
   recovery, and rollback.

## Relation to the unified plan

| Plan task | Release steps | Note |
| --- | --- | --- |
| RELEASE-01 | this document | Gates R0 to R5 on G0 to G5 and adds the entry gates above. |
| RELEASE-02 | R0, R1, R2 | Needs G5 and approved credentials and budgets. |
| ACCEPT-02 | before R4 | A fresh Windows pass on the repository artifact: real Browser, Obsidian and Cowork under mixed traffic, the real Claude/Cowork interface, Obsidian SecretStorage, and external file handles. |
| RELEASE-03 | R3, R4, R5 | Includes the hosted Python 3.12/3.13 matrix and signed stable bundles, moved here from INDEX-05. |

## R0 — Freeze a releasable source revision

**State:** Ready — the gates are green (2026-10-30). The release-owner decision is
required, and the frozen revision must pass the entry gates.

**Entry:** G0 to G5 green in the unified plan; SI-1 to SI-3 and LC-1 to LC-2
pass.

1. Select the intended SemVer release version and freeze the source revision.
2. Update `VERSION`, `pyproject.toml`, `resource_librarian.__version__`, and
   release-facing adapter metadata together; the build script rejects a
   mismatch.
3. Review the compatibility contract: Core protocol, tool/prompt contract,
   supported Python 3.11–3.13 matrix, and adapter range.
4. Run the normal deterministic suite and UI/Obsidian builds on the frozen
   revision. Record the commit and build inputs in the release checklist.

**Completion evidence:**
- the reviewed revision identifier;
- consistent version files;
- a passing deterministic build and test record, including the SI and LC
  gate results;
- the approved release scope;
- the gate table above, as it stood at the freeze.

## R1 — Produce a Windows hash lock and offline wheelhouse

**State:** Blocked externally — controlled build environment and dependency
approval required.

1. Generate `release-inputs/requirements.release.lock` from the reviewed
   release dependency input with `pip-compile --generate-hashes`.
2. Build a matching `release-inputs/wheelhouse` from exactly that lock for the
   supported Windows/Python matrix. Do not silently let pip consult a network
   index during bootstrap.
3. Verify that every locked artifact has a hash, that the wheelhouse contains
   the required distributions, and that the bootstrapper installs from it on
   clean Python 3.11, 3.12, and 3.13 environments.
4. Retain the generated lock, wheelhouse manifest, tool versions, and hashes
   as controlled release inputs. They are not ordinary developer artifacts.

**Completion evidence:** reviewed hash-locked file, complete offline
wheelhouse, clean-install evidence for the supported matrix, and the
`requirements_lock_sha256` captured by the stable manifest.

## R2 — Qualify and freeze the two release leads

**State:** Blocked externally — provider accounts, keys, budget approval, and
current provider endpoint/model confirmation required.

1. Confirm each provider's current API contract and select one exact,
   version-pinned OpenAI route and one exact, version-pinned Anthropic route.
   Record the non-secret endpoint and endpoint fingerprint; do not infer a
   replacement model when a provider retires a candidate.
2. Run L0 on the frozen source contract. Run L1 through the intended host,
   then L2 (three role-specific micro-walks per route) and L3 (five full golden
   runs per role/scenario) through the protected evaluation process.
3. Preserve the run artifacts, dates, cost/budget record, model and endpoint
   fingerprints, expiry, Core/protocol/tool/prompt fingerprints, and failures
   as well as passes.
4. Generate the reviewed stable
   `release-inputs/release-leads.json` with exactly one `verified_release`
   OpenAI lead and one `verified_release` Anthropic lead. Its integrity and
   signing envelope must validate under the release verifier.
5. Test first-run behavior with a user-owned key: a fresh successful L1 probe
   is still required before the chosen release lead is usable. A failed probe
   must downgrade rather than silently reroute.

**Completion evidence:** protected L0–L3 artifacts, valid signed
release-leads manifest, expiry/freshness record, and first-run L1 success and
failure-path evidence for both providers.

## R3 — Build, sign, and verify the stable bundle

**State:** Blocked externally — protected CI environment and signing
certificate required.

1. Configure the protected `stable-release` environment and make the
   certificate material available only as the documented release secrets.
2. Dispatch the stable release workflow with the frozen version, reviewed
   `release-inputs/release-leads.json`, lock, and wheelhouse. Never point the
   stable job at the checked-in development candidates.
3. Let `scripts/build-release.ps1 -Stable` construct the bundle, then use
   `scripts/sign-release.ps1` and `scripts/verify-release.ps1`. The verifier
   must reject missing hashes, development lead state, incomplete evidence,
   or an invalid detached signature.
4. Preserve the signed Core wheel, Obsidian ZIP, Cowork ZIP, Host companion,
   bootstrapper, verifier, manifest, detached signature, and CI provenance as
   one immutable release set.

**Completion evidence:** a signed bundle whose self-contained verifier passes
from a clean location, a stable release manifest with artifact hashes, and
protected CI logs/provenance.

## R4 — Exercise the final bundle on real Windows targets

**State:** Blocked externally — representative Windows/Obsidian/Docker
environments required.

Perform this against the signed R3 bundle, not an editable checkout:

1. Fresh install, launch, `/api/meta`, Host status/doctor, explicit stop,
   restart, and uninstall/rollback checks on supported Windows/Python targets.
2. Credential Manager, unsupported-keychain fallback, and explicit fallback
   migration checks. Confirm that environment keys remain read-only.
3. Obsidian SecretStorage injection, key rotation restart, adapter protocol
   mismatch, and `dispose()` behavior. Verify that no key moves over loopback
   HTTP or into a vault.
4. Two-client and active-typing simulations: Core lease contention, stale
   lease takeover confirmation, writer queue recovery, JSONL/SQLite access,
   dirty-document heartbeat/debounce, document-specific conflict checkpoints,
   and simultaneous writes to different notes.
5. Docker Desktop/WSL2 health, named-volume staging, no-NTFS-bind-mount
   execution, and output archival. On a no-Docker target, verify the only
   executable fallback is clearly labelled `non_isolated_host_exec`, requires
   the extra confirmation, and makes no unverified network-isolation claim.
6. Browser, Obsidian, and Cowork protocol compatibility, shared UI lifecycle,
   agent profile/tool bundle/macro/checkpoint recovery, V1 import, ranking
   comparison, graph/extract, and engagement close paths.

**Completion evidence:** retained test matrix with target versions, logs and
screenshots where helpful, resolved defects, and a successful rollback
rehearsal that leaves the vault unchanged.

## R5 — Publish deliberately and establish the operating cadence

**State:** Blocked externally — release owner approval required.

1. Publish only the R3 signed artifact set after R4 acceptance. Keep the
   previous signed bundle available for the documented manual rollback path.
2. Publish the operator, migration, qualification, update/rollback, Docker,
   and non-isolated-execution documentation alongside the artifacts.
3. Record the two release leads' expiry dates and assign an owner to review
   provider deprecations, endpoint/model fingerprints, hard compatibility
   changes, and security-policy changes.
4. On a hard change, invalidate qualification immediately and queue L0 plus
   the budget-gated L1–L3 work. On a soft change, retain selectable evidence
   as `advisory_stale` while queueing L0/L2 and refreshing release evidence
   before the next stable release.
5. Review real single-user feedback through the manual ranking
   Current/Candidate/Compare workflow; never convert this into a percentage
   traffic canary or automatic adoption.

**Completion evidence:** release-owner approval, published signed artifacts
and documentation, retained rollback artifact, and a dated qualification
freshness review schedule.

## Explicitly not in the V2 queue

- Third-party plugin marketplace, publisher PKI, SBOM catalogue review,
  third-party UI runtime, and arbitrary executable plugins remain V3 work.
- Client reference counting, automatic idle shutdown, and an autonomous
  service-style daemon remain intentionally excluded from the Host design.
- Percentage traffic canaries and automatic live ranking rollout remain
  retired; personal ranking is manual and reversible.
- A non-Docker host process must not be relabelled as isolated without a
  separately tested and explicit firewall policy.

## Reference material

- [Product contract](product-contract.md)
- [Qualification and release-lead policy](qualification.md)
- [Operator guide](operator-guide.md)
- [Adapter contract](adapter-contract.md)
- [Source-bound workbench policy](workbench.md)
- [Capability matrix](capability-matrix.md)
