# Librarian V2 review — executive report

**Review date:** 20 October 2026  
**Scope:** read-only architecture, documentation, implementation, parity, model-workflow, deployment, and focused-test review of `D:\Librarian_V2` and the original `D:\Resource-Library`.  
**Code reviewed:** standalone V2 Git `34ca7648b57d59414416b74dc1631259dee88001`; its `VERSION` file names `4c65375`, a revision from the Resource-Library lineage rather than this clone's visible history.

## Bottom line

Librarian V2 is a credible, unusually well-considered **research kernel**. It preserves the original project's strongest ideas—Markdown as the durable user-owned representation, evidence provenance, controlled promotion, constraint-led retrieval, and safe research sessions—and improves the consistency of the command, browser, MCP, and Obsidian surfaces.

It is not yet a dependable all-in-one agentic co-work product. The layer above the research kernel is unfinished in three material ways: no model is presently empirically qualified as a Tier-1 lead; the promised arbitrary-host configuration is not exposed end-to-end; and delivery remains a collection of development installations rather than one versioned, tested release. These are product-readiness gaps, not reasons to discard the architecture.

| Area | Assessment | Why |
|---|---|---|
| Research capability migration | Strong, with selected gaps | Most core V1 flows survive and several are stronger; graph/extract and operational use-learning do not yet have equivalents. |
| Obsidian compatibility | Strong foundation | The shared Markdown vault is genuinely two-way rather than a fragile synchronisation copy. The adapter's packaging/lifecycle needs work. |
| Model reliability | Not ready to claim | The eligibility registry is empty, while catalogue recommendations are metadata rather than observed performance. |
| Agentic co-work | Promising but constrained | Sessions, delegation, policy, workflows and routing exist; roles, bundles, recovery and user-facing configuration are still rigid. |
| Deployment | Development-ready, not release-ready | Install/build/release paths, adapters, keys, documentation and versioning are not yet cohesive. |

## What is already working well

- `src/resource_librarian` is a sensible authoritative core: vault persistence, intake, evidence, search, staging, sessions, policy, providers, workflows and MCP share one implementation.
- The central registry is an important design success. It declares 64 consult, 59 contribute and 16 curate tools; tiers receive the cumulative 64 / 123 / 139 tool surfaces. This prevents the separate CLI/MCP/chat action lists that caused drift in the original project.
- The policy model is appropriate for research: Plan/Ask/Auto modes, explicit gates, append-only session trace, durable staging and person-controlled promotion protect the user-owned library from a model's mistakes.
- The browser local-control plane has a thoughtful security baseline: loopback binding, per-process page token, origin checks, CSP and secret separation. Obsidian's SecretStorage-to-process-memory design is particularly sound in principle.
- V2 has real, not merely aspirational, model-aware features: lead/scribe/clerk roles, fixed-permission helper delegation, tier configuration, a model catalogue, task routing for clerks, profiles, lens packs, workflow definitions and MCP configuration.

## Highest-priority findings

### P0 — Do not present any model as a reliable lead yet

`standard/eligible_leads.json` ships with an empty `eligible` list. `app.py` correctly requires a recorded override for every Tier-1 selection, but this means there is no qualified default lead. The M0 evidence found in the original repository also concludes that the runs were insufficient to rank or qualify leads; the broader September benchmark was single-run screening, not reliability proof.

The user experience currently risks conflating provider-described “best for”/suggested tier with observed performance. The bundled catalogue has 102 DeepInfra profiles, and its profiling is derived from provider-listing text. That is useful discovery data, not evidence that a model can safely complete Librarian's research walk.

**Decision:** retain the override gate and describe all leads as **screened**, **experimental**, or **unavailable** until a repeatable empirical qualification process produces a versioned eligibility record.

### P0 — Provider onboarding can fail on Windows managed/service identities

The file-backed key path derives the ACL grantee from `%USERNAME%`, hardens `.env.tmp`, then reopens it. In this review environment `%USERNAME%` and the actual process identity differed, producing `PermissionError`; the key API returned HTTP 500. Focused app tests exposed three key-save failures.

This may not affect every interactive desktop account, but it is a real portability failure for managed, elevated, or service-like contexts—exactly the kinds of environments likely to host local model endpoints. Use the effective Windows principal/SID (or a supported keyring backend), retain an intentional recovery path, and return a recoverable user-facing error rather than a 500.

### P0 — Host choice is promised but not a finished product flow

The README says a user can set any OpenAI-compatible local base URL in Settings. Runtime code contains `base_urls`, but the review found no browser settings control or API that writes it. Tier selection accepts fixed preset providers only. Fine-grained clerk routes exist in manual configuration, not as a first-class product feature.

Build a host registry rather than a one-off text field: host URL/protocol/auth method, model discovery, connection test, tool-capability probe, rate/concurrency limits, health state and explicit user consent to use a route. This is the shortest path from “model chooser” to genuinely user-selectable infrastructure.

### P1 — The research walk is safe but cognitively oversized for many models

The state machine has good guardrails—phase gating, stable identifiers, required next steps and explicit promotion—but an active contribute session still exposes roughly 59–66 tool cards depending on phase. The current narrowing hides gated writes and upkeep tools, rather than giving the model a small task-local affordance set. Historical M0 results show argument-form errors, budget refusals and incomplete Tier-1 work even after prompt compaction.

Keep the policy/registry; change the interaction shape. Introduce task bundles or a navigation controller that offers about 5–12 appropriate tools, structured next-action guidance, deterministic identifier repair and a few well-tested macros for common research paths. Put known human checkpoints in the UI, not in a long model prompt.

### P1 — Release engineering must become a product capability

V2 is currently installed as editable source with broad dependencies, `pip` upgrades and `npm install`. It has no visible immutable lock files, release pipeline, wheel/installer, changelog, rollback/update mechanism or compatibility contract between core and adapters. Browser use is nearest to turnkey; Obsidian and Cowork remain separate manual installations. The expected Obsidian `dist` artefacts are absent, and both adapter READMEs still direct a standalone V2 checkout to the obsolete `.v2[mcp]` path.

The report recommends one signed/versioned Core release, CI-built browser/Obsidian assets, adapter compatibility handshakes, deterministic dependencies and a real `doctor`/startup smoke check.

## V1-to-V2 conclusion

V2 is a successor architecture rather than a one-to-one rewrite. It meaningfully advances intake, source typing, content-addressed evidence, search, staging, resumable sessions, application records, unified policies and Obsidian use. It leaves several original capabilities incomplete or hidden:

- A well-designed read-only `v1_export.py` exists but is not in the CLI, MCP, UI or documentation. Its planner identifies 500 stageable legacy records and 204 intentional exclusions, so migration needs a deliberate product decision.
- Whole-library graph/community analysis and capability-digest/import-graph extraction have no registered V2 counterpart.
- Feedback/application data is safely logged but does not yet produce a transparent use-learning/readiness loop.
- The original source-engagement workbench lifecycle is only partly replaced by generic sandbox/claim-run features.

The detailed ledger is in `2026-10-20-v1-v2-capability-parity.md`.

## Product boundary to decide explicitly

The historical V2 plan describes a focused research harness and explicitly warns against turning it into an undifferentiated agent platform. The requested all-in-one co-work direction is viable, but needs a stable boundary:

```text
Research kernel
  vault schema · evidence · intake · search · staging · sessions · policy
        ↓
Optional co-work extensions
  hosts · models · agent profiles · workflows · sandbox · TTS · MCP · project controls
```

This keeps research trust and portability stable while allowing a user to add hosts, model routes, role definitions and domain-specific tools without making every vault install or trust every extension.

## Recommended sequence

1. **Truthful onboarding and safety:** label all leads accurately; fix Windows credential storage; ship a visible host/connection configuration flow; correct obsolete installation instructions.
2. **Qualify the agent loop:** establish role-specific golden walks, repeat runs against a fixed corpus, artifact-based scoring, provider-health separation, and a versioned eligibility registry. Only then choose a default lead.
3. **Make walks smaller and recoverable:** task-local tool bundles, token-aware budgets, bounded retry/circuit-breaking, explicit cross-model failover policy and resumable continuation from durable session events.
4. **Make co-work configurable:** replace hard-coded positional tiers with reusable agent profiles containing route policy, permitted tools, permission ceiling, validation, budget and fallback rules.
5. **Release one product:** lock dependencies, build browser and Obsidian assets in CI, ship adapters as release artefacts, add compatibility/health checks, standardise dynamic ports and define version/update/rollback support.
6. **Close deliberate parity decisions:** publish a ported/changed/deferred/removed V1 capability matrix, decide whether to expose the legacy importer, then restore the highest-value research gaps as optional modules.

## Validation and limits

This was a static and focused-runtime review; no application code, product configuration, dependencies or user data were changed. The following checks were run:

- 43 focused loop, research-loop, model-catalogue, clerk-routing, prompt-compaction and JSONL tests passed.
- 26 focused V1 export/search/upkeep/DIK parity tests passed.
- Additional focused model/loop/clerk tests passed and the browser UI TypeScript check passed.
- `tests/test_app.py` passed 26 tests and exposed 3 key-save failures described above.
- 765 tests were collected. A complete green-suite claim is intentionally not made: the credential failure is real and a longer full run encountered external-install/time constraints.

Primary local evidence included the original V2 plan, co-work roadmap, M0/model-test records, V1 implementation/docs, V2 README and code, registry/tool definitions, deployment scripts, adapters and tests. Some R&D documents referenced by V2 code are present in `D:\Resource-Library` but not in the deployable V2 repository; that documentation split is itself a finding.
