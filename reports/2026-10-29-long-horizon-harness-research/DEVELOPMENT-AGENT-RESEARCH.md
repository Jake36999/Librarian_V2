# Development-agent requirements research

Reviewed 2026-10-29. This extends the completed 51-file local corpus review with coding-specific primary sources and direct implementation inspection. The resulting [development profile](../../docs/development-agent-harness.md) is a proposed contract, not evidence that the current product is hardened.

## Findings

The long-horizon foundation supplies intent continuity, bounded rounds and evidence freshness. Coding adds an executable adversarial environment: reading a repository, preparing dependencies, running tests and importing outputs can all cross trust boundaries. A capable coding harness therefore needs both an iterative candidate workspace and an independently enforced execution/integration boundary.

### Current implementation

- [Workbench contract](../../docs/workbench.md): pinned source, person-started execution, isolated Docker mode, explicitly non-isolated host fallback. This does not yet specify a standing agent development authorization or persistent writable candidate lifecycle.
- [Workbench tool entry points](../../src/resource_librarian/tools/workbench.py): `_require_person` and `_checkpoint` enforce caller and approval scope. Preserve them until an explicit development-capability API exists; do not make the model claim person identity.
- [Workbench implementation](../../src/resource_librarian/workbench.py): `_docker_execute` applies network, privilege and resource restrictions. `_docker_stage` helper commands do not visibly carry the same complete restrictions. `_archive_outputs` copies output before checking its aggregate size. These warrant lifecycle containment and streaming-export work; this review did not execute exploits or prove exploitability.
- [Generic sandbox tools](../../src/resource_librarian/tools/sandbox.py) and [sandbox implementation](../../src/resource_librarian/sandbox.py) provide another execution path. Development qualification must demonstrate consistent authority across paths rather than assuming Workbench alone controls execution.
- [E2′ Stage A0](../2026-10-29-e2-prime-a0/README.md) supports measuring handoff overhead. Its three small refactors do not qualify security, large repository work or a persistent coding runtime.

## External evidence register

Primary sources accessed 2026-10-29. Source findings below are deliberately bounded; DEV mappings are our engineering synthesis. Guidance documents are not experimental demonstrations. Academic results retain their original threat models and task domains.

| Source | Relevant finding and limitation | Design use |
|---|---|---|
| [SWE-agent, arXiv 2405.15793v3](https://arxiv.org/html/2405.15793v3), especially agent-computer interface sections | Repository navigation, editing and execution interfaces affect agent effectiveness. Coding benchmark success does not establish containment. | DEV-07: compact navigation, checked edits and usable diagnostics; evaluate capability as well as restrictions. |
| [CaMeL: Defeating Prompt Injections by Design, 2503.18813v2](https://arxiv.org/html/2503.18813v2), threat model, capability/interpreter design and limitations | Separates trusted control from untrusted data and enforces capability-based flows. Its guarantees depend on its interpreter and threat model; they do not transfer automatically to arbitrary shell execution. | DEV-02/04/11: deterministic authority and data-access boundaries. Do not mandate a full dual-model interpreter or claim general prompt-injection immunity. |
| [AgentDojo, 2406.13352v3](https://arxiv.org/html/2406.13352v3), benchmark and evaluation | Tests tool agents against prompt injection while measuring task usefulness. Its task environments are not a development sandbox qualification suite. | Adapt methodology to malicious repositories, tools and dependencies; measure legitimate-task utility and attacker effects separately. |
| [OWASP Secure Coding with AI](https://cheatsheetseries.owasp.org/cheatsheets/Secure_Coding_with_AI_Cheat_Sheet.html) | Covers coding-agent risks involving instructions, dependencies, execution privileges and review. Prescriptive guidance, not proof that a checklist prevents attacks. | DEV-03/05/08: protect execution, inspect dependency changes and preserve review integrity. Do not treat package popularity or age as trust guarantees. |
| [MCP Security Best Practices, 2026-07-28 documentation](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices) | Identifies confused-deputy, token-passthrough, SSRF, state-handle and local-server threats. Protocol compliance alone does not sandbox an executable server. | DEV-04/11: scoped credentials, destination checks and local-server containment. |
| [GitHub Actions secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use) | Untrusted checkout in privileged workflows and excessive token permissions can compromise CI; masking does not guarantee secret removal. | DEV-10/13: separate untrusted validation from publication authority; minimize secrets and protect logs. |
| [NIST SP 800-218, SSDF v1.1](https://csrc.nist.gov/pubs/sp/800/218/final), February 2022 | Secure development practices belong across the lifecycle, including prevention and vulnerability response. This is process guidance, not an agent certification. | DEV-08/14: explicit software assurance and incident response, beyond passing functional tests. |
| [SLSA v1.2 supply-chain threats](https://slsa.dev/spec/v1.2/threats-overview) | Distinguishes source and build integrity; provenance does not directly solve a malicious producer. | DEV-05/09: bind accepted source, environment and exported artifacts; retain dependency-risk review. |
| [gVisor security model](https://gvisor.dev/docs/architecture_guide/security/) | Isolation has defined attack surfaces and residual risks, including hardware side channels. A sandbox cannot undo permissions intentionally granted to a workload. | DEV-03/04: qualify actual backend exposure. This is not a recommendation to require gVisor on Windows/WSL. |

## Local research carried forward

The [remaining-corpus review](REMAINING-CORPUS-REVIEW.md) and [research report](RESEARCH-REPORT.md) retain the original paper identities and page anchors. Semantic-execution drift motivates stable user constraints and revision-aware preflight. Goal-tree work motivates persistent bounded task structure. Formal temporal-verification work motivates explicit event invariants and failure scenarios, without claiming formal verification of this product. Structured-proposal research motivates deterministic admission, without copying permissive simulation fallbacks. Confidence estimates and model critiques remain advisory; neither may authorize code execution or substitute for runner evidence.

The development profile adds 14 requirement groups, supporting helpers and user-visible monitoring, 18 qualification scenarios and four delivery gates. Low-level schemas, backend selection, prompts, UI layout and tuning remain open. The existing unified task count and completion states remain unchanged: implementing the profile requires separately scoped development work.

## DeepInfra review disposition

A complete, non-truncated DeepSeek review (`20261029T181624-fefc9304`, 13,604 input / 2,218 output tokens) compared the draft with Workbench source. The preserved response and receipt are under `data/development_deepinfra/`. Its five findings mostly restate acknowledged implementation gaps: authority capabilities, candidate-bound evidence, lifecycle containment/export, persistent editing and scoped network/publication.

Accepted additions: explicitly qualify trusted caller-field provenance, dispatch/commit-time revocation, and host-side archive-fetch redirect/size policy. Existing DEV requirements already cover the other gaps. Rejected interpretation: missing implementation does not contradict a document explicitly labeled proposed; the critic's suggestion that prose requirements fail to specify closure confuses specification with implementation. Its claim that exit zero is the only acceptance signal must be narrowed to the Workbench run state; engagement closure and overall task acceptance have separate semantics. Caller-field forgery and archive exploitation remain hypotheses, not demonstrated vulnerabilities. Its proposed source-volume mutation test requires a deliberately privileged test fixture and must not be described as an available agent capability.

This call cost an estimated $0.0040516. Cumulative sprint commitments are $0.35037415 of the $8 cap, including the pre-existing unresolved $0.0135514 reserve. These are local accounting estimates, not a provider invoice. Validation checked 28 local document links; no runtime security tests were performed.
