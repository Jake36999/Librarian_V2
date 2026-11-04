# Framework and application plan

Proposed development requirements, 2026-11-03. These recommendations supplement the [assessment](ASSESSMENT.md); they are not adopted requirements or a compliance attestation.

## A small set of complementary frameworks

| Document | Role | Application to Librarian |
|---|---|---|
| [NIST SP 800-218, SSDF 1.1](https://csrc.nist.gov/pubs/sp/800/218/final) | Lifecycle framework: prepare, protect software, produce well-secured software, respond to vulnerabilities | Use as the umbrella for ownership, development environments, verification, release integrity and vulnerability response. Tailor controls to this desktop/agent application. |
| [OpenSSF OSPS Baseline 2026.08.28](https://baseline.openssf.org/versions/2026-08-28) | Concrete repository and delivery controls, organized by maturity | Start with applicable Level 1 controls, then select higher-level controls justified by release and execution risk. Record applicable, implemented, demonstrated and exception states separately. |
| [SLSA 1.2 build requirements](https://slsa.dev/spec/v1.2/build-requirements) | Artifact provenance and build-platform assurance | First produce and verify provenance; then assess an L2 target with hosted authentic provenance. L3 requires additional platform guarantees. A CMS signature alone establishes no SLSA level. |
| [DORA continuous integration](https://dora.dev/capabilities/continuous-integration/) | Research-backed development feedback practices | Restore a green mainline, integrate small changes, measure feedback and repair time. Use operational trends, not certification claims. |

SSDF is the lifecycle spine; OSPS makes selected controls checkable; SLSA addresses artifact origin; DORA helps assess whether the workflow remains effective. Avoid maintaining four independent checklists. Keep one control/evidence register with cross-references. NIST's separate generative-AI profile concerns model development; using external models does not justify imposing an entire model-training lifecycle on Librarian.

Selected OSPS anchors are AC-03.01 (primary-branch changes), QA-06.01 (tests before acceptance), BR-05.01 (dependency tooling), BR-06.01 (signed releases), BR-07.01 (credential protection), and VM-05 (dependency-analysis policy). These are selected mappings, not a claim that all belong to one maturity level or that this report audits the complete baseline.

## Implementation sequence and acceptance contracts

Owners below are proposed responsibilities, not assignments to named people. One maintainer may hold several roles, but record when independent review is unavailable.

| Package | Proposed owner | Concrete work | Completion evidence |
|---|---|---|---|
| DT-01: restore acceptance | Core maintainer | Diagnose Windows credential ACL assertion and Python 3.12/3.13 failures. Configure protected mainline with required Core/wheel/adapter checks and controlled bypass. | Green checks at the exact integration revision; a failing change cannot merge through normal workflow; exported rules/settings and documented emergency bypass. |
| DT-02: reproducible setup | Build maintainer | Lock Python development and build dependencies by supported environment; choose explicit Node/npm and Python patch versions; use lock-respecting JS setup; record runner image. | A clean Windows setup reproduces the recorded dependency graph without changing locks; all three Python lanes pass. |
| DT-03: trustworthy CI | Build/security maintainer | Pin reviewed action SHAs; minimal explicit permissions; bound job durations; validate release path inputs; retain JUnit, environment manifest and failure diagnostics. | An intentionally failing fixture makes the workflow fail and retains evidence; malformed input is rejected without executing injected shell text. |
| DT-04: dependency and source assurance | Security maintainer | Add vulnerability/secret checks, dependency update cadence, security reporting policy, and incremental Python static checks. Define expiring exceptions and remediation ownership. | A synthetic policy violation blocks acceptance; exceptions identify rationale, owner and expiry. No real credential used for tests. |
| DT-05: release evidence | Release maintainer | Produce SBOM and provenance for shipped components; verify builder/source identity and digest; promote immutable payloads or verify explicit rebuild derivation; validate protected release environment. | Wrong digest/source/builder fails verification; two clean unsigned-payload builds compare; stable installation and rollback evidence links to actual artifact digests. |
| DT-06: execution assurance | Workbench maintainer | Implement and test existing DEV-01–14 incrementally; align image identity across Workbench/snippet paths; run real Windows/Docker containment tests. | Denied network/host access, bounded resources, cancellation/descendant cleanup, export confinement and rejected unauthorized integration demonstrated on declared backend versions. |
| DT-07: operating discipline | Project maintainer | Add concise contribution/security/ownership guidance, support matrix, failure triage and periodic control review. Decide licensing explicitly if distribution is intended. | A new contributor can reproduce a failure from retained evidence; release exceptions and support commitments have an owner and review date. |

DT-01 is first: adding scanners to a workflow whose failures do not block acceptance provides limited assurance. DT-02/03 then stabilize diagnosis and enforcement. Complete DT-04/05 before claiming a reliable stable release process, alongside the existing release queue. DT-06 is a prerequisite for expanding autonomous coding authority; it need not delay unrelated read-only research features. Never advertise the proposed DEV profile as implemented merely because its document exists.

## Tool choices that fit the existing system

**Dependency resolution:** extend the existing pip-tools direction rather than introduce a second resolver immediately. Its [official documentation](https://pip-tools.pypa.io/en/stable/) describes hash generation and environment-specific compilation. Keep runtime package compatibility ranges, but generate reviewed development/build locks. Include the isolated build backend and tools, not only installed application dependencies. Continue `npm ci` with existing lockfiles. A future uv migration should demonstrate faster clean setup and equivalent graph/packaging behavior before adoption.

**Security checks:** [pip-audit](https://github.com/pypa/pip-audit) is a suitable Python dependency vulnerability checker. Audit the resolved release and development sets separately; supplement with JavaScript dependency checks and a maintained secret scanner. Known-vulnerability scanning cannot certify arbitrary packages as safe. Establish a severity/exploitability policy, explicit exception expiry and scheduled rescans because advisories change without code changes. Start Python lint/type checking on security boundaries and new changes rather than blocking all work on an untriaged historical backlog; TypeScript checking already exists.

**Artifact evidence:** use a [CycloneDX SBOM](https://cyclonedx.org/specification/overview/) to inventory shipped components, versions and relationships. Include Python wheelhouse, distributed adapters and bundled JavaScript, distinguish development-only components, and bind the BOM to release digests. The existing marketplace SBOM proposal addresses a different inventory. [GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations) fit the current CI provider, including an offline-verification path. Prototype verifier policy against the current CMS/offline installer flow; do not replace working offline verification with a mandatory online dependency.

**Environment records:** add a small machine-readable manifest to every verification run: source/base and candidate digest, dirty-input manifest if allowed, lock hashes, tool versions, OS/runner and container digest, exact command, exit status, test report hashes and artifact identities. Do not store credentials or full ambient environment dumps. The manifest lets a person or another agent reproduce evidence rather than trust a summary.

## Tests and metrics that demonstrate improvement

1. **Mainline reliability:** required-check success rate, duration of red-mainline episodes and time to restore green. Report failing supported versions separately; do not average them away.
2. **Feedback:** median and upper-percentile time to useful failure evidence, clean setup time, and rerun-without-change outcome differences. Investigate nondeterminism before calling a test flaky.
3. **Reproducibility:** lock drift after clean setup and equality of defined unsigned payload hashes across independent builds. Compare signatures separately.
4. **Release recoverability:** installation and rollback success on the supported host matrix, tied to artifact digests and retained logs. Include restoration of service with user data intact.
5. **Agent execution:** boundary violations, residual processes, unauthorized integration attempts rejected, reproducible candidate checks and evidence loss after interruption. Test setup and export as well as the command itself.
6. **Maintenance:** time to triage dependency findings, age of accepted exceptions, and percentage of shipped components inventoried. Set targets after collecting a baseline; no arbitrary coverage percentage substitutes for boundary tests.

For long-horizon and multiagent work, persist the environment/check manifest alongside Session and Workbench records. Invalidate prior checks when their source, locks, environment, requirements or integration base change. Reuse evidence only when its declared applicability remains valid. Archive superseded records for explanation; never allow an old successful summary to make a new candidate appear verified. Core should decide integration from runner evidence and policy, not model confidence.

## Where these requirements belong

- Extend `docs/development-agent-harness.md` with DT-06 acceptance cases and evidence bindings; preserve its proposed status until implementation.
- Extend `docs/regression-manifest.md` with required-check identities, retained report locations and freshness rules.
- Extend `docs/release-implementation-queue.md` with DT-05 and actual environment-protection evidence; retain existing real-host prerequisites.
- Add `docs/development-environment.md` for the supported toolchain, lock regeneration and clean setup/diagnosis commands.
- Add `docs/development-assurance.md` as the single SSDF/OSPS/SLSA control register: requirement, applicability, implementation, verification, owner and expiring exception.
- Add concise root contribution/security guidance and explicit ownership. Licensing is a maintainer decision, not something an automated audit should invent.

The design specification should require observable outcomes and evidence identity. Keep tool versions, concrete commands and operational procedures in these maintained companion documents so routine tooling updates do not force architectural rewrites.
