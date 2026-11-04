# Librarian development tooling and environment assessment

Assessment date: 2026-11-03. Source revision: `40ec923f5d7cb5612939b9fc456963b88e0af4a3`. Read together with [the application plan](FRAMEWORK-AND-APPLICATION-PLAN.md) and [machine-readable evidence](evidence.json).

## Verdict

Librarian has substantial engineering foundations, but its current delivery process does **not yet demonstrate a dependable industrial baseline**. The decisive issues are failing required-platform tests and unenforced mainline acceptance, followed by incomplete environment reproducibility and release assurance. This is an engineering assessment, not certification against a universal definition of “industrial standards.”

Keep the existing Windows-first architecture, Python version matrix, packaged smoke tests, release verification, and documented execution boundaries. Strengthen their enforcement and evidence before adding another platform or orchestrator. A devcontainer, Kubernetes deployment, or larger tool catalogue would not resolve the observed blockers.

## Evidence and limits

Reviewed repository workflows, Python/JavaScript dependency declarations, setup/build/signing/verification scripts, test configuration, sandbox and Workbench implementations, and development/release documentation. Checked public GitHub Actions runs and branch metadata at the current revision. Earlier research documents are background evidence, not authority to implement their proposals.

The latest [Core CI run](https://github.com/Jake36999/Librarian_V2/actions/runs/41567602480) finished on 2026-11-03:

| Lane | Observed result | Meaning |
|---|---|---|
| Python 3.11 Core | 1 failed; 1,937 passed; 3 skipped; 5 deselected | Owner-only credential-file permission assertion failed. |
| Python 3.12 Core | 262 failed; 1,671 passed; 5 errors; 3 skipped; 5 deselected | Broad compatibility/integration failure. |
| Python 3.13 Core | 262 failed; 1,671 passed; 5 errors; 3 skipped; 5 deselected | Broad compatibility/integration failure. |
| Installed wheel, all three Python versions | Passed | Clean installed-wheel smoke coverage exists and ran. |
| Adapters | Passed | TypeScript builds and packaged Browser/Cowork smoke ran successfully. |

The 3.12/3.13 logs include repeated `FileChangedError` and missing index-derived results. These are observed failure patterns, **not a diagnosed root cause**. The credential assertion likewise requires investigation of actual ACL enforcement and verification; it does not alone prove credential exposure. Do not suppress these tests merely to obtain green CI.

All 13 Core CI runs in the returned 16-run history failed; the other three successful runs were dependency graph updates. That bounded history supports a process concern, not a claim about every historical run. Public [branch metadata](https://api.github.com/repos/Jake36999/Librarian_V2/branches/master) reported `protected: false`, and [repository rulesets](https://api.github.com/repos/Jake36999/Librarian_V2/rulesets) returned an empty collection. Actual release-environment reviewers and default token permissions could not be inspected through the available connector; their state remains unknown.

Local targeted verification passed: 40 tests covering release versions/leads, smoke-script contracts, Workbench boundaries, and sandbox behavior. The local interpreter was Python 3.11.3; `pip check` reported no broken dependencies. Several tests use fake runners or inspect script contracts. These results neither override the remote failures nor prove real Docker containment, successful signing, or absence of vulnerable dependencies. No full suite, penetration test, production release, or real-host acceptance exercise was performed in this audit.

## Findings

| Area | Existing strengths | Gap and consequence | Priority |
|---|---|---|---|
| Mainline acceptance | Push/PR CI, three Python versions, substantial tests | Current Core matrix is red; master is unprotected. Checks can report failure without preventing acceptance. | Immediate |
| Development environment | Checkout-specific virtualenv, interpreter selection, source-import identity checks, isolated test config | Python dev/build dependencies float; local setup uses `npm install` while CI uses `npm ci`; Node is not explicitly selected in CI. Reproducing a failure depends on incidental environment state. | High |
| Test evidence | Real installed-wheel and packaged Browser/Cowork checks; TypeScript checks | No retained JUnit/coverage reports in reviewed workflows; slow tests deselected by default with no scheduled slow lane visible. Real Obsidian/Windows/Docker acceptance remains pending in project documents. | High |
| Workflow security | Candidate/stable separation and explicit stable dispatch | Actions use mutable major tags, workflow token permissions are not explicit, and release path inputs are interpolated directly into shell text. | High |
| Dependency management | JavaScript lockfiles; stable release accepts hash lock and offline wheelhouse | No tracked Python development lock or automated vulnerability-scanning/update workflow found. `--no-audit` makes npm install output unsuitable as security evidence. | High |
| Release integrity | Artifact hashes, detached CMS signatures, verification, stable lead checks, deterministic ZIP construction | Manifest signature is not build provenance; candidate and stable are separately rebuilt with floating tools. Actual protected signing/release acceptance is not demonstrated by source code alone. | High |
| Agent execution | Workbench image digest requirement, no-network contained profile, resource limits; detailed DEV requirements | Separate snippet sandbox uses mutable image/base tags. Fake-runner tests do not establish real-host guarantees. Writable autonomous coding remains proposed. | High before expanding authority |
| Maintainability and governance | Extensive regression, operator and release documentation | No tracked CONTRIBUTING, SECURITY, CODEOWNERS or LICENSE file found; no configured Python lint/type gates in reviewed configuration. Ownership and response expectations need a concise operational home. | Medium |

### Environment reproducibility

[pyproject.toml](../../pyproject.toml) declares compatible dependency ranges; these are useful package metadata but do not freeze the development environment. [requirements.release.in](../../requirements.release.in) and stable release lock inputs address a different purpose. Record a tested Windows toolchain and reproducible development/build dependency resolution, including build isolation dependencies. Preserve the supported Python matrix rather than assuming one environment lock works identically across all minors.

Use native Windows as the acceptance environment because ACLs, process management, installation and integrations are material product behavior. A container may help selected tools or untrusted execution; it cannot substitute for Windows host evidence. Record the runner image/version alongside Python, Node, npm, PowerShell, browser, dependency locks and source revision. Treat environment updates as reviewed changes with repeatable checks.

### Delivery and release assurance

[ci.yml](../../.github/workflows/ci.yml) already provides a useful separation of Core, wheel and adapter checks. Make those successful checks an acceptance condition. Preserve logs and machine-readable results on failure so agent summaries can link to actual evidence.

[release.yml](../../.github/workflows/release.yml) declares a `stable-release` environment; the declaration cannot prove that GitHub reviewers or branch restrictions are configured. Verify and retain configuration evidence. Pin reviewed action revisions, declare least privilege per job, validate dispatch paths, and pass inputs through environment variables rather than embedding expressions into PowerShell source. This recommendation follows [GitHub's secure workflow guidance](https://docs.github.com/en/actions/reference/security/secure-use); this audit did not establish an exploitable injection path.

[build-release.ps1](../../scripts/build-release.ps1), [sign-release.ps1](../../scripts/sign-release.ps1) and [verify-release.ps1](../../scripts/verify-release.ps1) provide valuable integrity controls. Retain them. Add evidence tying the exact distributed payload to source, toolchain, workflow and checks. Prefer promotion of tested immutable payloads; if stable packaging changes them, require stable-artifact checks and explicit derivation. Do not label a separately rebuilt artifact as the identical tested candidate without digest evidence.

Deterministic ZIP ordering/timestamps and `SOURCE_DATE_EPOCH` are useful mechanisms, not a demonstrated reproducible build. Define the unsigned payloads to compare, then build twice in independent clean environments. Timestamped signatures require a separate comparison policy. This matches the [Reproducible Builds definition](https://reproducible-builds.org/docs/definition/).

The checked-in release manifest explicitly describes a non-installable development template. Pending signatures and lead approvals there are not evidence of a broken published release. Existing [release implementation queue](../../docs/release-implementation-queue.md) and [regression manifest](../../docs/regression-manifest.md) correctly retain real-host and release prerequisites; close them with artifacts rather than rewriting them as complete.

### Execution environments for development agents

Distinguish human development/CI, person-started Workbench execution, and agent-written snippet execution. Their controls differ. [workbench.py](../../src/resource_librarian/workbench.py) requires digest-qualified images; [sandbox.py](../../src/resource_librarian/sandbox.py) uses `librarian-sandbox:1` built from `python:3.11-slim`. Harmonize image identity recording and update policy across both paths. Digest pinning improves identity; it does not prove the image or container is secure.

[development-agent-harness.md](../../docs/development-agent-harness.md) is already a strong proposed design: bounded capabilities, isolated candidate trees, setup/runtime/export containment, trusted checks, controlled integration, durable task state and incidents. The missing step is implementation and adversarial acceptance evidence, not another competing harness specification. [workbench.md](../../docs/workbench.md) also distinguishes contained execution from explicitly confirmed host execution; retain that distinction in user-visible status and results.

For multiagent development, separate candidate workspaces and execution capabilities, bind each result to its base revision and environment, and centralize integration through Core. A helper's successful test report cannot authorize a merge. Recheck on the final integrated revision because independently passing branches can conflict. These are proposed applications of existing DEV contracts, not claims that the runtime delivers them today.

## What to preserve and what to add

Preserve existing release scripts, packaged tests, Windows coverage and harness architecture. Add enforced acceptance, controlled environment resolution, retained evidence, dependency/security response and verified provenance. Extend the existing design and release documents with named owners and observable acceptance tests. The accompanying plan supplies the framework mapping and sequence; none of its proposed controls were applied to repository settings or product code during this review.
