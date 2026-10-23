# Model hosts and qualification

## Personal host records

Host records contain only non-secret configuration:

```text
id, display_name, protocol, base_url, auth_ref, enabled,
timeout, concurrency_limit, rate_limit, discovery_at,
endpoint_fingerprint, health
```

OpenAI, Anthropic, DeepInfra, and local presets are seeded.  V2 accepts
arbitrary OpenAI-compatible endpoints; other protocols require a curated
adapter rather than a guessed compatibility mode.  Keys live in the personal
key source named by `auth_ref`, never in a vault.

## Evidence levels

| Level | Work | Result |
| --- | --- | --- |
| L0 | Deterministic contract/replay tests with mocked turns | Contract failure blocks compatibility. |
| L1 | Low-cost real connectivity and tool-call probe | `screened`. |
| L2 | Three short role-specific micro-walks | Validates bundles, IDs, checkpoints, recovery, and grounding. |
| L3 | Five repeated full golden walks per role/scenario | `verified_local` or release evidence. |

L0 belongs in normal CI.  L1–L3 are budgeted, resumable work: the Core shows
an estimate and requires a visible spend checkpoint before a provider-facing
probe or evaluator starts.  Dependency invalidation may create an inert plan,
but it never spends credentials in the background.  A user can safely use a
screened or experimental custom route when they explicitly accept its
qualification state.

### Resumable L2/L3 jobs

`POST /api/qualification/run` with `level: "L2"` or `"L3"` first requires
`confirm_spend: true`.  It creates a durable personal evaluation job; it does
not silently issue a provider request or turn a plan into evidence.  Jobs can
be listed at `GET /api/qualification/jobs`, paused, resumed, or cancelled.

A local evaluation harness or release CI advances an unfinished job through
`POST /api/qualification/jobs/result`.  Each pass or fail must include a
durable artifact reference.  The Core records the observed run and only its
normal evidence derivation can make the route locally verified after the
required L3 results.  A hard protocol/schema/endpoint/model/security change
marks unfinished jobs stale; a soft prompt/profile/macro change is advisory.

## Release leads and cold start

Stable releases must bundle two exact, version-pinned release leads—one OpenAI
and one Anthropic route—with actual L3 artifact references.  First-run setup
still performs L1 using the user's own provider key; no key is bundled.

`release_leads.json` is not a provider catalogue.  A stable record is accepted
only when its canonical `integrity` digest matches, its envelope has
`schema_version: 2`, `release_status: stable`, and a release-pipeline signing
verification record, and its shared contract names the Core/protocol/tool and
prompt versions.  Each lead must name an exact `model` and `model_version`, a
derived `model_fingerprint`, the exact endpoint including its non-secret
`auth_ref`, a matching endpoint fingerprint, evidence date and future expiry,
at least five L3 runs, and SHA-256-addressed qualification artifacts.  The
installer/release pipeline verifies the actual package signature; the Core
uses the recorded verification reference plus the embedded digest to fail
closed if the bundled evidence is damaged or incomplete.

At first run, release L3 evidence is still not enough to start a Lead.  The
selected route must have a fresh successful L1 record for the same host,
requested model, current hard-compatibility fingerprint, and provider-returned
model version.  A failed, expired, stale, or differently routed probe returns
the choice to `release_probe_required`; it never silently falls back to the
other provider.

The current source manifest intentionally marks both proposed leads as
`pending_release_ci`.  That is an honest development state: they are visible
as candidates but are not selectable as verified release leads.  Release CI
must replace this data only after its recorded qualification succeeds.  A
provider deprecation, endpoint fingerprint change, or failed probe downgrades
the route and offers the other qualified lead or an explicitly experimental
custom route.

The stable bootstrapper copies its manifest-hashed `release-leads.json` beside
the installed Core and into the installed package's evidence location, then
starts Librarian with its absolute path and SHA-256 in the environment.  The
Core accepts that override only when both values are present and the file bytes
match; a damaged or incomplete override fails closed instead of falling back
to a development candidate.  Replacing the packaged candidate also keeps
direct Host and adapter launches on the same evidence record.

## Invalidation without churn

Hard compatibility fingerprints are Core protocol, tool schemas, structured
response contract, endpoint fingerprint, exact model/version, and security
policy.  A hard change immediately invalidates verified evidence, runs L0, and
creates dormant L2/L3 plans plus an explicit L1 requirement.  The plan is not
a provider call: its next paid action remains behind the spend checkpoint.

Soft behavior fingerprints are prompt wording, macro content, profile tuning,
tool-bundle composition, and non-breaking UI guidance.  A soft change marks
evidence `advisory_stale`: the route remains selectable, L0/L2 work is queued,
and release evidence must be refreshed before the next stable release.  It
becomes hard only when L0 fails, a safety regression occurs, or L2 crosses its
declared failure threshold.  Time expiry is separate freshness information.

Profile runtime budgets are enforced before every provider request.  The Core
reserves the prompt plus requested output maximum against a token budget; a
cost budget needs an explicit `route_policy.rate_card` with input/output USD
per million tokens and otherwise fails closed before a paid request.  This is
conservative because the provider-neutral protocol has no universal usage
field.  Profile concurrency is Core-local and route allow-lists (`host_ids`,
`providers`, and `model_ids`) are checked before a chat turn starts.
Profiles are vault-scoped revisioned records: each save appends a snapshot in
`agents/profiles.json`, and `/api/profiles/history?id=<profile>` exposes that
non-secret audit trail.

The selected profile's qualification floor is enforced at the Core boundary.
Lead profiles retain the stricter release/M0 eligibility rule; a different
role (for example `research_helper` or `scribe`) needs its own fresh
role-specific L1/L2/L3 evidence. A recorded 2.x experimental-lead override is
possible only through a route-scoped `host_model_override` checkpoint and is
never reported as qualification evidence. Profile validation-focus rules are
compact guidance for the model; they cannot grant tools, bypass a registry
gate, change a route, or replace a UI checkpoint.

Task-sized tool bundles are enforced as well as displayed. A permissive
OpenAI-compatible endpoint cannot replay or invent a hidden tool call outside
the schema issued for the current turn. `macro_run` is the deliberately
audited exception: its fixed registered steps are traced and pass their normal
registry, broker, phase, budget, and document-lease gates.

Delegated helpers always resolve the vault's `research_helper` profile rather
than inheriting a Lead's authority. They retain their fixed read-only tool
allow-list, use the Core-owned index service, and apply that profile's route,
qualification, concurrency, output, token, cost, and time constraints to the
actual helper route (including a tier-2-to-tier-1 fallback).

Clerk and Scribe single-shot calls are governed by their own fixed role
profiles too. Their configured route is checked per task, their output is
capped, and their token/cost/time/concurrency budgets reserve work before the
provider sees it. A route-policy or qualification failure queues the task; it
never falls through to another model. An existing 2.x `[clerk]` or `[scribe]`
entry remains supported: known preset URLs are matched to the seeded Host
Registry record, while a custom URL needs one non-secret Host Registry record
before a Screened or Verified profile can use it. When a current host assignment
exists for the role, it is the explicit assignment and takes precedence over
the legacy block.

