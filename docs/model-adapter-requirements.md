# Model protocol-adapter requirements

**Status:** Partial. The compatibility/observability foundation, including
ADAPT-01 reply metadata and ephemeral reasoning continuation, is implemented.
Trusted protocol render/parse shaping, cancellation, route evidence, and
ADAPT-02–11 remain planned in the
[unified implementation plan](unified-implementation-plan.md).
**Terms:** [Librarian terminology](terminology.md).

This is the research record and acceptance boundary for Librarian's model
adapter layer. It supplements the broader
[Model Invocation Architecture](model-invocation-architecture.md) with the
provider facts that constrain an implementation. It does not replace live
qualification: an expectation is a documented configuration claim, whereas
L0–L3 evidence is proof that the exact deployed route works in Librarian.

## Evidence that shapes the contract

| Source | Requirement for Librarian |
| --- | --- |
| [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) | A model tool call is a proposal, not execution. Preserve the provider call ID, validate arguments in Core, run the approved tool, and return its result with the exact matching ID. OpenAI also recommends a small initial tool surface and combining operations that are always sequential; that supports Librarian's task-sized bundles and audited macros. |
| [Anthropic client-tool loop](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works) | The Core drives the loop while `stop_reason` is `tool_use`; full assistant/tool-result turn shape must be preserved. A model never receives authority to execute a tool directly. |
| [Anthropic tool-use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview) | Tool schemas and tool-result content add input tokens. This reinforces an explicit tool-budget/selection policy rather than exposing an entire registry on every turn. |
| [Hugging Face chat-template guidance](https://huggingface.co/docs/transformers/chat_templating_writing) | Formatting, whitespace, and special tokens are model-specific. A local model card can inform an expectation record, but its template cannot be copied into a generic OpenAI-compatible route. |
| [vLLM tool-calling documentation](https://docs.vllm.ai/en/latest/features/tool_calling/) | An OpenAI-shaped endpoint alone does not prove tool-call reliability; server version, parser, tokenizer/template and deployed configuration are part of the route fingerprint. |

The design implication is important: protocol compatibility is not model
qualification. An adapter may know how to render OpenAI Chat Completions, but
only an exact model/endpoint expectation plus L0/L1 evidence may enable a
non-default native control such as strict tools, streaming, or thinking.

## Normative requirements

### Boundaries and authority

1. A protocol adapter translates an already resolved plan. It receives no
   vault path, SQLite connection, writer, registry executor, approval broker,
   credential value, or model-routing authority.
2. Core owns policy, capability selection, budget, tool validation, tool
   execution, retry/failover decisions, checkpoints, and durable audit events.
3. Credentials are resolved by the existing secret source immediately before
   transport. Plans, expectation packs, diagnostics, and traces contain no
   key, header, request body, prompt, raw response, or hidden reasoning.
4. A provider-returned model identifier is recorded separately from the
   requested model. A mismatch is visible evidence, never a quiet success.
5. Existing `Provider.chat(system, messages, tools, max_tokens, temperature)`
   remains the compatibility ABI through V2. The new layer does not add
   free-form native provider parameters to it.

### Invocation plan and result

The runtime resolves:

```text
TaskContract + role/workflow scope + exact route + model expectation
    + trusted adapter descriptor + offered-tool schema
    -> immutable InvocationPlan
    -> ProtocolAdapter
    -> Reply + normalized InvocationResult
```

An `InvocationPlan` includes the adapter ID/version/ABI, endpoint fingerprint,
exact requested model, role, task type, interaction type, bounded output
budget, behaviour intent, expectation fingerprint, and hash of the offered
tool schema. It excludes mutable user text and secrets. Its configuration hash
excludes the plan ID and session ID, making same-configuration comparisons
deterministic across turns.

An `InvocationResult` records safe metadata only: completed/tool-call/failed
outcome, requested and observed model, stop reason, elapsed time, safe tool
call summaries (with a call-ID fingerprint rather than a raw provider field),
and a typed/redacted provider failure. The legacy bridge
explicitly reports usage, request ID, and inner retry count as unavailable
until the transport layer can expose them reliably.

### Expectations

Expectation packs are data, never executable code. They must declare:

```text
exact model identity or wildcard scope
host family and optional endpoint fingerprint
protocol adapter ID and ABI
tri-state capability claims: true | false | unknown
reviewed native behaviour modes
source URL, immutable revision/date, and pack fingerprint
```

Unknown is not false. An unknown capability may remain selectable as
experimental under existing qualification policy, but cannot unlock a
provider-native control. An explicit false or a missing reviewed behaviour
mode fails before a provider request is made.

The initial bundled pack contains only protocol baseline records. It makes no
claim that a specific hosted reseller or local model supports a feature. Exact
model cards and local-runtime records should be added in reviewed batches,
starting with routes already selected as reliable.

## Implemented V2 foundation

The following components now exist in
[`src/resource_librarian/model_invocation.py`](../src/resource_librarian/model_invocation.py):

- immutable `TaskContract`, `InvocationScope`, `ExactRoute`,
  `InvocationPlan`, `InvocationBinding`, and `InvocationPayload` contracts;
- `ModelExpectation` and read-only `ExpectationRegistry` with a shipped
  baseline pack at
  [`src/resource_librarian/standard/model_expectations/core.json`](../src/resource_librarian/standard/model_expectations/core.json);
- trusted `AdapterRegistry` descriptors for legacy OpenAI Chat Completions,
  Anthropic Messages, and test/custom Provider routes;
- `LegacyProviderAdapter`, which invokes the current provider ABI exactly and
  performs no retry, model swap, or tool execution;
- `InvocationRuntime`, which holds a bounded, redacted in-memory trace; and
- `AdapterBackedProvider` for external legacy integrations that explicitly
  replace their wrapped provider after a route change.

The Core supplies the runtime to interactive `Loop` walks, one-shot
`ProviderEndpoint` work, and L1 qualification. A walk pins its route/adapter/
expectation binding at turn start, so a settings refresh cannot silently move a
tool continuation to another model. The existing SSE sequence and research
vault artefacts remain unchanged; model diagnostics are not persisted yet.

## Deliberately not enabled yet

The following require separate protocol adapters, reviewed expectation
records, fixture suites, and live probes. They must not be approximated by a
generic OpenAI-compatible flag:

- OpenAI Responses continuation, opaque reasoning items, and `call_id`;
- Anthropic thinking blocks/signatures and model-specific effort controls;
- streaming tool-call fragments and cancellation guarantees;
- native JSON-schema/strict-tool mode;
- direct Transformers chat-template execution;
- vLLM/SGLang parser- and template-specific tool use; and
- token usage, request IDs, and per-attempt transport telemetry.

The existing effort slider remains a Librarian work budget. It does not send a
native reasoning/thinking knob until a reviewed expectation plus adapter
fixture explicitly allows that mapping.

## L0 acceptance suite and next increments

The deterministic foundation suite is
[`tests/test_model_invocation.py`](../tests/test_model_invocation.py). It
proves plan hashing/redaction, legacy-call compatibility, typed failure
redaction, unknown versus explicit-false capability handling, native-behaviour
fail-closed policy, explicit provider replacement, and a normal Loop walk
without changing public event ordering.

Before enabling a new protocol/model behaviour, add all of the following:

1. Request-render and response-parser fixtures for the exact protocol;
2. tool-result continuation fixtures preserving provider call IDs;
3. malformed JSON/schema/refusal/truncation cases that prove no invalid call
   reaches the registry;
4. an expectation record pinned to official source material and local runtime
   configuration where relevant;
5. an L1 no-effect live probe against the exact endpoint/model fingerprint;
6. qualification dependencies for adapter ABI/parser/expectation changes;
   and
7. a compact model-tile explanation of what is known, unknown, or requires a
   probe—without changing the current three-position selection UX.

Direct PDF cleanup's fixed DeepInfra helper remains outside this agent-route
adapter slice. It should be migrated under a dedicated service-adapter
contract rather than silently inheriting interactive tool-loop policy.
