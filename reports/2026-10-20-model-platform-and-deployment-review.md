# Librarian V2 model, co-work and deployment review

## Executive conclusion

V2's deterministic research machinery is considerably more mature than its model platform. The application can constrain an agent safely, but it cannot yet demonstrate that a selected provider/model/host can operate those constraints reliably. Its customization mechanisms exist mostly in code or manual configuration rather than as a coherent user experience, and its deployment path is still a developer workflow.

## 1. Model reliability: current state versus product claim

### What the evidence supports

- The Tier-1 qualification gate is implemented. `standard/eligible_leads.json` contains an empty `eligible` array and the app requires a recorded override for a lead model.
- The original M0 test record concludes that completed runs were insufficient to rank leads; it intentionally left the eligibility list empty. The earlier DeepInfra screening used single runs and is useful lead-generation evidence, not stable reliability evidence.
- The bundled catalogue contains 102 DeepInfra profiles. They are provider metadata and public-listing-derived profiling, not cross-provider observed performance. OpenAI, Anthropic and local hosts have no equivalent bundled evidence record.

### Resulting product position

There is no empirically qualified default lead. The UI should never imply otherwise. Use four distinct states:

| State | Meaning | Default action |
|---|---|---|
| Verified | Repeated, versioned Librarian-role evaluation passes defined thresholds | Eligible for the role |
| Screened | Basic capability/protocol checks passed, evidence insufficient for reliability | Permitted with visible caution |
| Experimental | User-added, stale or incomplete evidence | Explicit override required |
| Unavailable | Connection or capability probe failed | Cannot be assigned |

Provider description, context-window marketing and a “suggested tier” must be shown as **declared capability**, separately from **observed capability**. Every displayed result should carry the provider endpoint, model/version, test date, sample size, scenarios, prompt/tool-schema version, cost/latency and a link to the trace/artifacts.

### A credible qualification harness

Run role-specific, artifact-scored tests against a fixed vault/corpus and versioned fixtures. A lead needs complete research walks, valid tool arguments, phase compliance, grounded synthesis, proper approval behaviour, recovery after a transient failure, structured output and cancellation/resume. A scribe, clerk and media model need their own smaller tasks. Score actual session/project/evidence/staging state—not a model's assertion that it performed an action.

For each exact provider/model/endpoint/version, repeat each scenario enough times to see variation (for example 5–10 runs before provisional eligibility), retain failure samples and separate connector availability from cognitive/tool reliability. Re-run automatically when the provider, model, tool schema, prompt bundle or core version changes. A live-web suite can supplement this; a fixed corpus is essential for comparability.

## 2. Why model walks still fail or stall

The walk has valuable safeguards: append-only event history, phase-gated writes, budgets, explicit next steps, brokered permissions, staging and resumability. Historical prompt fixes are present. The remaining problem is cognitive surface and recovery, not lack of gates.

During an active contribute session the model receives about 59–66 tool cards, depending on phase. Narrowing principally hides phase-gated writes and upkeep tools, leaving a large reading/session surface and schemas. Historical M0 evidence records argument-form errors, budget refusals and incomplete Tier-1 walks. Prompt compaction lowered earlier oversized prompts but does not make the available affordance set task-sized.

### Recommended walk design

1. Preserve the central registry and hard policy gates.
2. Add a navigation controller/task bundle that offers only 5–12 tools appropriate to the current objective and phase.
3. Generate a structured next action from durable state; supply canonical IDs and deterministic identifier validation/repair before a provider call.
4. Offer small, audited macros for frequent paths (e.g. inspect → map → search → judge → stage) rather than expecting a model to compose every tool sequence.
5. Make context/output budgets model-aware in tokens, not just character trimming; reject or warn on unproven tool-capability server-side.
6. Move known human choices and escalation points into UI controls, leaving the prompt to reason about research rather than interpret policy prose.

### Recovery policy is needed

Current fallback selects a lower tier only if one is absent, not when a chosen model fails. A provider failure ends the turn; clerk routes intentionally do not fall back; 429/5xx handling is weak. Define a per-role recovery policy: bounded exponential retry, health/circuit-breaker state, resumable continuation from the last durable event, optional alternate route and a clear user confirmation before cross-model failover.

## 3. Custom co-work should become a product model

Today there are three positional tiers, fixed read-only delegated helpers and powerful manual clerk-route configuration. There are not reusable user-facing profiles for a role's prompt, tool policy, model route, verification, permission ceiling, budget and recovery behaviour.

Introduce a versioned **agent profile** with at least:

- name and intended role;
- primary/alternate route and host health requirements;
- allowed tool bundle and permission ceiling;
- input/output/context and cost/latency budgets;
- validation/grounding and person-approval gates;
- retry/failover policy and required qualification state;
- versioned evaluation evidence.

Workflows should reference profiles rather than hard-coded Tier 1/2/3 positions. Store profile configuration in a reviewable vault/config location and allow import/export, but validate it against an extension/permission manifest before it can run. This enables customization without weakening the evidence and approval model.

### Host configuration gap

The README promises Settings support for arbitrary OpenAI-compatible base URLs. Runtime code knows about `base_urls`, but no UI/API write path was found; the UI limits chat providers to presets and the local URL is fixed. A host registry must expose endpoint/auth/model discovery/connectivity/tool probe/health/rates to fulfill this promise. It should also distinguish “connector reachable” from “model fit for this role.”

### Obsidian operational note

The Markdown-vault approach is the right two-way compatibility design. One lifecycle concern remains: the UI returns an EventSource cleanup function but the mounted interface does not expose disposal; the Obsidian adapter re-renders/clears without invoking it. Reopening/restarting can leave stale reconnecting streams. Treat a mount/unmount/dispose contract as a reliability requirement for the adapter.

## 4. Deployment assessment

### Strengths

- `Setup.bat`, `scripts/setup.ps1`, a per-copy virtual environment and a browser launcher create a straightforward developer on-ramp.
- The browser interface can use prebuilt assets without a Node build.
- Host adapters use the same core instead of reimplementing policy and storage.

### Release blockers

| Finding | Impact |
|---|---|
| `pyproject.toml` is `2.0.0.dev0`; product/package name is undecided; `VERSION` does not resolve in the standalone Git history | Users cannot identify a supportable release. |
| No visible release CI, lock/hashes, wheel/installer, changelog, update or rollback path | Installations are hard to reproduce and support. |
| Setup uses editable source, newest available Python, `pip` upgrade and `npm install` | Results vary over time and across machines. |
| Setup validates import/help, not a bound port, API/UI serving or asset compatibility | “Installed” can still be unusable. |
| Obsidian `dist` artefacts are absent; adapter docs use stale `.v2[mcp]` command | Obsidian/Cowork are manual, non-portable branches. |
| Browser launcher chooses a free port but `new-vault.ps1` defaults to 8323; a minimized batch must stay alive | Launch and lifetime management are fragile. |
| Key-save ACL failure under identity mismatch | Hosted provider onboarding can fail in managed deployments. |
| Roadmap/M0 documents live in Resource-Library rather than deployable V2 | Operators do not receive the evidence behind product gates. |

### Release direction

1. Select a canonical product name; retain `resource-librarian` only as a documented package/CLI compatibility alias.
2. Produce immutable, signed/versioned Core artefacts (wheel/pipx or native installer) with locked dependencies and a tested OS/Python matrix.
3. Build browser assets and the Obsidian plugin in the same CI release; ship a plugin ZIP and an explicit Core/adapter API compatibility handshake.
4. Implement `librarian doctor`: version/provenance, UI asset hash, adapter compatibility, extras, writable vault/config paths, key backend, port selection, connector health and model probe.
5. Standardise dynamic ports and use a managed local process/tray lifecycle instead of a hidden console's lifetime.
6. Bundle or immutably link operator architecture, M0 and migration docs; correct `.v2[mcp]` references immediately.

## Validation performed

- Browser UI TypeScript check passed.
- Focused loop, research-loop, model catalogue, prompt compaction, clerk-routing and JSONL tests passed (43 tests in one focused run; additional focused model/clerk coverage also passed).
- V1 parity-focused tests passed (26 tests).
- App tests exposed the three reproducible Windows key-save failures; 26 app tests passed.
- Obsidian type-check could not run from this clean checkout because its local Node dependencies were absent. That does not establish a source defect, but it confirms the additional deployment prerequisite.

No product code, configuration, dependencies, credentials or user data were altered during this review.
