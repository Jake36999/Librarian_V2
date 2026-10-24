# Model expectations registry

## Purpose

Librarian should make model configuration more reliable without turning
provider discovery into an endless, expensive trial-and-error loop.

The Model Expectations Registry is the proposed evidence layer between a
provider's model listing and a live agent run. It records what a particular
route is documented and reviewed to expect: its protocol, exact model
identity, tool-call contract, chat/template requirements, reasoning controls,
generation constraints, and source provenance.

It does **not** replace live qualification. It makes qualification targeted:
the card-derived expectation says what to configure and test; L0–L3 evidence
says whether the route actually works in Librarian.

This document is a design and operating contract. It does not enable a
provider parameter or modify an active prompt by itself.

The companion [Model Invocation Architecture](model-invocation-architecture.md)
specifies how an expectation record is resolved with task, role,
collaboration, and route policy into a provider call and model walk.
The corresponding evidence and implementation requirements are in
[Model protocol-adapter requirements](model-adapter-requirements.md).

## Why the registry is needed

The current catalog is a useful discovery and display layer. Its profile
mostly contains modality, best use, licence class, suggested tier, context
length, prices, tool-calling, and reasoning flags. That is insufficient to
tell an adapter how to invoke a model safely.

In particular, an arbitrary OpenAI-compatible endpoint does not guarantee:

- that it uses the upstream checkpoint's chat template;
- that it accepts the upstream model's tool grammar;
- that it supports a thought/thinking parameter;
- that a field called effort has the same semantics as another provider; or
- that the returned model version remains the one that was profiled.

The differences are material rather than cosmetic:

- Hugging Face describes model cards as Markdown plus metadata. They are useful
  for intended use, limitations, lineage, licensing, and evaluation context,
  but are not a universal machine-readable invocation contract.
  [Model-card documentation](https://huggingface.co/docs/hub/main/en/model-cards)
- Hugging Face explicitly warns that special tokens and tool formatting must
  match the format a model saw in training.
  [Tool chat-template documentation](https://huggingface.co/docs/transformers/chat_templating_writing)
- Qwen 3 documents a real enable_thinking template control and different
  suggested settings for thinking versus non-thinking operation.
  [Qwen 3 model card](https://huggingface.co/Qwen/Qwen3-8B)
- DeepSeek V3.1 documents a distinct non-thinking tool-call template and
  grammar. [DeepSeek V3.1 model card](https://huggingface.co/deepseek-ai/DeepSeek-V3.1)
- Native effort is not provider-wide. OpenAI documents model-specific
  reasoning_effort availability, and Anthropic documents model-generation
  specific thinking/effort behaviour.
  [OpenAI API reference](https://platform.openai.com/docs/api-reference/chat/object?lang=ruby)
  and [Anthropic guidance](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables)

Therefore, Librarian must not infer invocation behaviour from a family name,
a catalog tag, or a provider's marketing tile.

## Terms and ownership

| Layer | What it answers | Authority |
| --- | --- | --- |
| Provider discovery | “What model IDs did this endpoint list today?” | Provider response; useful but unreviewed. |
| Model catalog | “What can the picker display and compare?” | Curated descriptive metadata. |
| Model expectation | “What input/output contract should this exact route be expected to use?” | Reviewed, versioned source evidence. |
| Adapter conformance | “Can this Core build and parse that contract?” | Deterministic tests and a low-cost probe. |
| Qualification evidence | “Has this route behaved reliably in Librarian scenarios?” | L0–L3 run artifacts. |
| Active assignment | “Which exact route is this role/session allowed to run?” | Person-selected profile/slot configuration. |

Credentials and host connections remain personal and outside vaults. Role
assignments remain vault-scoped. A curated expectation record can ship with
the Core; a personal endpoint mapping or local-host override belongs in the
personal configuration area and must not contain a secret.

## Registry record

Each record is versioned and pinned to a route identity. This is illustrative
schema, not an instruction to put arbitrary card text into an agent prompt:

~~~
ModelExpectation
  schema_version
  id
  status: draft | reviewed | deprecated

  identity
    provider_model_id
    host_id_or_family
    endpoint_fingerprint
    upstream_repository
    upstream_revision
    aliases

  provenance
    source_kind: official_card | tokenizer_template | provider_docs | manual
    source_url
    source_revision
    source_sha256
    fetched_at
    reviewer
    confidence

  capabilities
    modalities
    context_window
    tool_use: true | false | unknown
    parallel_tool_calls: true | false | unknown
    structured_output: true | false | unknown
    system_message_support: true | false | unknown

  prompt_contract
    runtime_target: hosted_openai | anthropic | transformers | vllm | sglang
    chat_template_id
    chat_template_revision
    tool_format: provider_native | named_template | unknown
    tool_turn_policy
    tool_result_requirements
    response_parser

  reasoning_contract
    control: none | boolean | numeric | enum | provider_native | unknown
    parameter
    allowed_values
    default
    tool_turn_policy
    adapter_mapping_status: untested | declared | adapter_tested

  generation_defaults
    temperature
    top_p
    top_k
    min_p
    output_guidance

  evidence
    declared_claims
    adapter_contract_tests
    live_evaluations
    compatibility_fingerprint
    behaviour_fingerprint
~~~

The registry must use tri-state capabilities. Unknown is a valid honest state;
it is not false. Only an explicit, evidenced false should block a model from a
tool-dependent lead role. Unknown models remain available as experimental
routes and offer a clear path to collect an expectation and run L1.

The record's identity is not its friendly display name. It is the combination
of exact provider model ID, host/endpoint compatibility, and any mapped
upstream revision. This prevents renamed catalog records from duplicating the
same route and prevents an upstream model-card change from silently modifying
a hosted route.

## Source ingestion rules

### Sources to prefer

Use sources in this order:

1. official provider API documentation for the endpoint actually called;
2. official upstream repository card and tokenizer/template at an immutable
   revision;
3. official vendor deployment/runtime documentation for vLLM, SGLang, or a
   local backend;
4. a short internal reviewer statement when the first three sources do not
   resolve a hosted-provider behaviour.

Pin Hugging Face sources to a commit hash and hash the exact fetched bytes.
The Hub supports revision-specific resolution and caching, which makes the
source artifact reproducible.
[Hugging Face revision cache guidance](https://huggingface.co/docs/huggingface_hub/guides/manage-cache)

### What an import may and may not do

A card-research job may:

- collect URLs, immutable revisions, short claims, declared defaults, and
  template references;
- propose a mapping from a provider model ID to an upstream checkpoint;
- open a review item with cited evidence and a proposed L0 suite.

It may not:

- copy unrestricted card prose, Jinja, or prompt text into a system prompt;
- change a host assignment, profile, permission, or model route;
- enable a parameter because its name sounds plausible;
- execute a downloaded repository or template;
- infer that a reseller uses the upstream template; or
- convert a model-card claim into a qualification result.

All prompt fragments are Librarian-owned, small, reviewed configuration
assets with their own version and tests. A source card may justify a fragment,
but does not directly supply executable prompt instructions. This is both a
safety measure and a way to avoid stale, overbroad provider advice.

## Configuration and runtime policy

### Separate work budget from reasoning control

The existing 1–10 effort slider is a universal Librarian work-budget control.
It governs allowed agents, steps, time, output/cost budget, and review work.
It currently does not send a native OpenAI, Anthropic, Qwen, or DeepInfra
reasoning setting.

The UI should make two controls explicit:

| User-facing control | Scope | Meaning |
| --- | --- | --- |
| **Work budget** | Every route | How much Librarian may attempt/spend: steps, helpers, time, output, review, and cost. |
| **Model behaviour** | Only routes with a reviewed mapping | The exact native effort/thinking/template setting and its observed state. |

For a selected route, Model behaviour has one of four visible states:

| State | Meaning |
| --- | --- |
| Unsupported | Work budget changes Librarian only; no native configuration is sent. |
| Declared | A source documents a setting, but the adapter has not proven its request/response handling. |
| Adapter-tested | Deterministic contract tests and a route probe prove the adapter mapping. |
| Qualified | Relevant L2/L3 evidence includes the selected behaviour. |

The effective request configuration should be visible after selection:
host, exact model, adapter protocol, model-behaviour mode, source/revision,
and qualification state. It must never reveal credentials or hidden chain of
thought.

### No generic thinking-off prompt

“Turn thinking off” is not a generic model instruction. For example, a local
Qwen deployment may need a reviewed enable_thinking control through its
template, while a hosted OpenAI-compatible endpoint may not expose that
control at all. DeepSeek V3.1 documents a particular non-thinking tool-call
format, but that does not prove every hosted DeepSeek route uses it.

For generic OpenAI-compatible hosts, let the server own its template unless
the host and the expectation record explicitly document an adapter mapping.
If the mapping is unknown, do not inject keywords such as /no_think and do
not claim a reasoning mode was changed.

### Selection flow

The existing model tile and popup are good places to build this without adding
another configuration page:

1. Choose a role/slot, not just positional tier 1–3.
2. Choose a host and exact model.
3. Show catalog facts separately from expectation and qualification facts.
4. If an expectation exists, show its route-specific Model behaviour choices,
   their source, and their testing state.
5. If no expectation exists, offer “Use experimentally” and “Research this
   model,” with no automatic configuration recommendation.
6. Require the normal visible checkpoint for an experimental route or a
   cross-model change.
7. Record the effective non-secret configuration in the session trace.

The role/slot must be canonical. Legacy tiers can remain a compatibility view,
but a lead, scribe, clerk, helper, TTS, STT, OCR, and embedding assignment
should not overwrite unrelated slots.

## Runtime measurement contract

Model selection should make its recommendations auditable after the fact. The
normal non-secret trace should retain:

~~~
route and role/slot identity
requested and provider-observed model identity
expectation-record and effective-configuration hashes
queue time, provider round-trip time, retry count, and failure class
usage availability and redacted prompt/completion totals when the provider sends them
tool-call/parser outcome and checkpoint outcome
~~~

This is deliberately narrower than raw provider capture. Do not persist
credentials, full provider payloads, hidden reasoning content, or arbitrary
model-card text. The trace is enough to distinguish an endpoint regression,
adapter mismatch, budget stop, model behaviour failure, and ordinary task
failure without exposing private content.

## Validation hierarchy

Cards reduce blind testing; they do not remove it. Each expectation record
creates the smallest test plan needed to verify its declared contract.

| Level | Cost | Required proof |
| --- | --- | --- |
| L0 | No provider cost | Payload construction, permitted fields, tool-schema serialization, parser shape, template selection, tool-result continuation, and forbidden-parameter tests. |
| L1 | Low | Exact model returned, basic connectivity, one strict tool call with exact arguments, and expected response/parser state. |
| L2 | Moderate | Three short role-specific micro-walks that exercise relevant bundles, IDs, checkpoints, grounding, recovery, and the selected reasoning/tool mode. |
| L3 | High | Repeated full golden walks per role/scenario; the only route to verified_local or verified_release evidence. |

An expectation-specific L1 should report two separate outcomes:

1. **Conformance:** did the endpoint honour the expected model, control, tool
   shape, and parser path?
2. **Reliability:** did the model complete the Librarian task successfully?

The first can pass while the second fails, and vice versa. Keeping them
separate prevents a provider or Core regression from being incorrectly
described as a model-quality result.

The 2026-10-22 post-fix DeepInfra artifact is an example of focused evidence:
both MiMo V2.6 Flash and DeepSeek V4.1 Flash passed one strict L1 and three
focused walks. It is not enough to label either route verified. See
[the validation artifact](../reports/2026-10-23-deepinfra-post-fix-validation.json).

## Freshness and invalidation

The record needs two change classes, aligned with qualification evidence:

| Change | Treatment |
| --- | --- |
| Exact model/version, endpoint fingerprint, protocol, tool grammar/template, response parser, native reasoning parameter, or security policy | Hard compatibility change: invalidate verified evidence, run L0, and queue paid requalification behind the usual spend control. |
| Descriptive card prose, pricing, display labels, non-semantic recommendations, or an unapproved candidate mapping | Advisory review: do not silently change runtime configuration or lock a route. |

A source fetch that changes hash must create a review task. It must not
overwrite the active record automatically. Prompt wording and macro changes
remain soft behaviour changes unless deterministic tests or a safety threshold
show that they altered the contract.

## Rollout

Do not attempt to profile 200+ models in one migration. Use a measured
high-value rollout:

1. **Foundation:** add the schema, provenance store, tri-state capability
   fields, and read-only UI display. No runtime adapter changes.
2. **Canonical assignment:** make role/slot-to-route binding authoritative,
   retain tier migration adapters, and repair per-role readiness rendering.
3. **First cohort:** curate the current DeepInfra candidates plus the most
   used 8–15 hosted/local routes. Each gets an exact source record and L0
   contract fixture.
4. **Controlled mappings:** enable native controls only after L0 and L1 prove
   the correct adapter/request/parser behaviour for that route.
5. **Evidence loop:** correlate L2/L3 outcomes with expectation versions,
   endpoint fingerprints, latency, cost, and failure class.
6. **Expansion:** add opt-in research queue proposals, reviewer workflow,
   expiry/deprecation, and curated coverage reporting.

Success is not the number of cards collected. Success is that a user can see
why a model is recommended, what Librarian will actually send, what has been
observed, and what remains experimental.

## Acceptance criteria

- Every visible recommendation has a cited expectation record or is labelled
  unprofiled/experimental.
- Unknown capability stays unknown; the selector does not convert absence of
  evidence into a negative capability.
- No card content becomes system-prompt text without a reviewed,
  versioned Librarian configuration asset.
- An exact model/endpoint/template/reasoning mismatch cannot retain a verified
  label.
- A provider-native setting is never sent unless its adapter mapping has L0
  coverage and an explicit record.
- Work budget remains usable for every host without pretending to control
  native reasoning.
- Live probes remain bounded, budgeted, resumable, and traceable.
- A model-card refresh cannot silently change a running route, a user
  selection, or a vault's control-plane policy.
