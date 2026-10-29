# Development-security review: proposed development-agent profile

**Scope note:** I inspected only the supplied excerpts. I did not run code, tests, or exploits. "Fact" = visible in the supplied code. "Hypothesis" = inference requiring verification.

## 1. DEV-02/DEV-11: no capability object exists; the only authority is a boolean plus a digest scope

**Fact.** `tools/workbench.py::_require_person` gates on `ctx.extras.get("caller_kind") == "person"`. `_checkpoint` binds approval to `type`, `scope` (a 16-hex-char SHA-256 prefix of `{id, choice, command, image, non_isolated}`), and `resolution == "approve"`. `workbench.start` accepts `person_confirmed: bool` and `choice`; there is no engagement-scoped, expiring, revocable capability token, no operation set, no environment/destination/budget fields, and no revocation path. `Engagement` has no capability, expiry, or budget fields.

**Gap vs DEV-02.** The profile requires "an unforgeable execution capability scoped to engagement, workspace, operations, environment, destinations, resource budget and expiry/revocation." Nothing in the code models this. The checkpoint scope is a *digest*, not a capability: it does not carry the engagement's authorized paths, environment identity, or budget, and `_checkpoint` returns `None` (approval accepted) on any matching `type`+`scope`+`approve`+`not expired` row — the `expired` flag is read from the store, not enforced by `workbench.start`.

**Hypothesis (verify).** A caller that can write `ctx.extras["checkpoints"]` or `caller_kind` bypasses both gates; the docstring asserts agents "cannot manufacture that bit" but the code does not show where `extras` is populated or sealed. This is the single highest-value thing to confirm before advertising DEV-02.

## 2. DEV-08: validation evidence is not bound to candidate tree or environment

**Fact.** `workbench.start` records `run_id`, `choice`, and a filtered `result` (stdout/stderr dropped) into `audit_trace`, then sets `state = "completed" if exit_code == 0`. There is no candidate-tree hash, no environment/image identity beyond `archive_sha256` (source only), no command/verifier version, no baseline-failure record, no test-collection counts, and no staleness check. `_docker_execute` returns `archive_sha256` (source archive) but not the image digest actually used beyond `_require_image`'s `@sha256:` presence check.

**Gap vs DEV-08.** "Bind each check to the exact candidate tree, environment, command/verifier version, timing and trusted runner result" and "Candidate edited after tests → prior evidence is stale" are not represented. `exit_code == 0` is the only acceptance signal, which the profile itself says is insufficient ("command exit zero only describes that command"). A model-written test that exits 0 is indistinguishable from a real pass in the stored record.

## 3. DEV-03/DEV-06: `_docker_stage` helper commands lack the execution container's restrictions; output export is post-hoc

**Fact.** `_docker_execute`'s main `docker run` applies `--network none --read-only --cap-drop ALL --security-opt no-new-privileges --user 10001:10001 --pids-limit 128 --memory 2g --cpus 2`. `_docker_stage` runs three separate `docker run`/`docker create`/`docker start` invocations (`output_init`, source staging `sh -lc "mkdir -p /source && tar -xzf ..."`) with **no** `--cap-drop`, `--user`, `--pids-limit`, `--memory`, `--cpus`, or `--security-opt`; only `output_init` has `--network none`. The staging container runs `tar` as the image's default user against a host-copied archive.

**Fact.** `_archive_outputs` runs `docker cp` of the whole output volume into `vault.derived/.../output` **before** the size loop; the loop then `unlink`s files exceeding `MAX_OUTPUT_BYTES` but does not remove already-materialized directories, symlinks are skipped only after `docker cp` has materialized them, and there is no path-traversal/device/reparse validation on the copied tree.

**Gap vs DEV-03/DEV-06/DEV-09.** The profile requires containment "to setup, execution, diagnostics, cleanup and export helpers" and "Validate and bound exports before host materialization." The staging helpers and the `docker cp` export are exactly the pre/post-main-command paths the profile calls out, and they are weaker than the main run. The research doc already flags this ("`_docker_stage` helper commands do not visibly carry the same complete restrictions. `_archive_outputs` copies output before checking its aggregate size") — the profile does not add a requirement that closes it, only DEV-03/DEV-09 prose.

## 4. DEV-01/DEV-07: no writable candidate tree, no transactional edit, no conflict detection

**Fact.** `Engagement.workspace` is a string set to `"managed on start"`; `_docker_execute` mounts source `readonly` and output as a separate volume. There is no candidate tree, no base-revision-vs-dirty manifest, no expected-content check, no diff preview, and no concurrent-edit detection. `_host_execute` extracts into a fresh `tempfile.mkdtemp` and `shutil.rmtree`s it in `finally` — no persistence across iterations.

**Gap vs DEV-01/DEV-07/DEV-12.** The profile's core premise — "repeated bounded iterations" with "transactional edits checked against prior content identity" and "Persist ... patch identity ... through compaction/restart" — has no implementation surface in the supplied code. `Engagement` has no `candidate`, `base_revision`, `authorized_paths`, or `patch_id` fields. This is the largest *capability* gap, not just a security one: without a persistent writable candidate, the agent cannot do multi-iteration development at all, so the profile's "practical autonomous coding capability" claim is unsupported.

## 5. DEV-04/DEV-10: network and external-effect authority are not separated from local execution

**Fact.** `_docker_execute` hardcodes `--network none`; there is no broker for scoped fetch/service access, no destination allowlist, no DNS/redirect/IPv6/loopback/metadata handling. `_host_execute` explicitly sets `"network_containment": False` and warns "loopback and network access may be possible." `_download_archive` uses `urlopen` on a host-constructed `codeload.github.com` URL — a host-side network call outside any candidate boundary, with no redirect policy shown. There is no push/merge/release/deploy operation anywhere; `close` only records `application`/`outcome`.

**Gap vs DEV-04/DEV-10.** The profile requires "Broker narrowly scoped fetch/service access separately from arbitrary process networking" and "Use a separate publishing broker" with "Reconcile unknown remote outcomes before retries." Neither exists. The `non_isolated_host_exec` tier is correctly labeled, but the profile's DEV-04 default-no-network requirement is only met for the Docker main command, not for staging, export, or host fallback.

## Demonstrated facts vs hypotheses

- **Facts:** the code anchors above (function names, flags, fields, ordering of `docker cp` vs size check, missing flags on `_docker_stage`).
- **Hypotheses to verify:** (a) whether `ctx.extras` is sealed against agent writes; (b) whether `checkpoints` store enforces `expired` independently; (c) whether `docker cp` of a symlink/device in the output volume can materialize on the host before the `is_symlink()` skip; (d) whether `_download_archive`'s `urlopen` follows redirects to non-GitHub hosts.

## Deterministic tests the integrator should run

1. **Authority bypass:** call `engagement_start` with `caller_kind` absent/`"agent"` and a pre-seeded approved checkpoint; assert `Refusal("PERSON_CONFIRMS")`. Then with `caller_kind="person"` but a checkpoint whose `scope` digest differs by one argv byte; assert a new checkpoint is required.
2. **Staleness:** start a Docker run, mutate the source volume, re-run `_archive_outputs`; assert no record claims the prior `archive_sha256` still validates the new tree (currently it would).
3. **Staging parity:** inspect the argv passed to `runner` in `_docker_stage`; assert `--cap-drop ALL`, `--user`, `--pids-limit`, `--memory`, `--cpus`, `--security-opt no-new-privileges` are present, or that the profile explicitly exempts staging (it does not).
4. **Export ordering:** place a file larger than `MAX_OUTPUT_BYTES` plus a symlink in the output volume; assert nothing is materialized under `vault.derived` before the bound check, and that symlinks/devices are rejected pre-copy.
5. **Host fallback labeling:** run `_host_execute` with a command that opens a loopback socket; assert `isolation_tier == "non_isolated_host_exec"` and `controls["network_containment"] is False` are surfaced to the user view (DEV-13), not just stored.

**Assumption:** the profile is intended to be enforced by the same `workbench.py`/`tools/workbench.py` surface; if a separate development-capability API is planned, items 1–2 and 5 still apply to the current surface until it lands.