# REMED-07 model-view and reachability qualification

**Date:** 2026-11-02. **Scope:** offline, deterministic qualification of the
real request renderer, effective capability context, audited tool surfaces,
and existing retry/cancellation path. No paid call or external network call
was made.

## Result

REMED-07's exit conditions are met:

- exact serialized request size is recorded for long audited histories on
  both first-party chat protocols;
- the Manager manifest is derived from the effective selected profile,
  resolved role routes, passive qualification state and content roots;
- registered, offered and admitted are kept distinct for every audited phase;
- retry and cancel faults are injected with virtual time; and
- existing real transport cancellation is confirmed rather than replaced.

## Complete model-request size

The bounded Manager projection does not replace `Loop.view()` or the chat
history. The fixture restores a real audited `SessionStore` history, makes one
request through the real OpenAI or Anthropic adapter and local HTTP transport,
and captures `sent_bytes` at `providers._request`'s dispatch gate. The gate's
size equals both `len(json.dumps(body).encode("utf-8"))` and the local server's
received bytes.

| Profile | Route/protocol | Historical rounds | Wire messages | Exact bytes |
| --- | --- | ---: | ---: | ---: |
| Lead | OpenAI-compatible | 1 | 4 | 13,015 |
| Lead | OpenAI-compatible | 10 | 22 | 15,670 |
| Lead | OpenAI-compatible | 50 | 102 | 27,470 |
| Lead | Anthropic Messages | 1 | 3 | 12,702 |
| Lead | Anthropic Messages | 10 | 21 | 15,609 |
| Lead | Anthropic Messages | 50 | 101 | 28,529 |

The first historical marker, the last historical marker and the current
request all remain in every long rendered body. Request size therefore grows
with history even though old tool results are compacted and the Manager
projection is bounded. This is a measured qualification, not a claim of
constant context size.

The capture retains only protocol, endpoint suffix, message count, byte count
and SHA-256. Neither prompts nor the measurement-local body digest appear in
the redacted invocation trace. Scribe, Clerk and research-helper profiles do
not receive an audited Lead transcript, so long audited-history request size
is not applicable to them rather than inferred.

## Effective capability context

`audit_projection` now receives non-secret context derived from the same App
paths used at dispatch:

- the selected `AgentProfile` and its permission/bundle/qualification policy;
- canonical role bindings, enabled host and endpoint identity;
- the profile's route allow-list and passive qualification/explicit override;
- adopted and attached roots, including read/write versus attached read-only
  access.

No model discovery, qualification job or probe occurs while building the
manifest. A deleted profile, unreadable route store, changed/disabled host,
route-policy mismatch, insufficient qualification, unreadable roots or a
failed context callback is shown as unavailable. It never falls back to a
broader profile, an invented route or the whole vault.

One shared `bundle_selection` function now feeds both `Loop.tools()` and the
manifest, including the Lead profile's `research` phase wildcard and a
restrictive profile's read-only fallback. The general bundle list remains
compact so the essential projection stays bounded.

## Audited reachability matrix

`registered` is the phase bundle's declared tool names that exist in the
closed Registry. `offered` is the exact default-Lead surface after tier and
profile selection, including the bounded result reader and the two controlled
macro entry points. `admitted` is deliberately not precomputed: the real
`REGISTRY.call` boundary still applies active bundle, profile tier, phase,
contract, arguments, roots and epoch to each call.

| Phase | Registered | Offered | Required actions admitted in the scripted full round |
| --- | ---: | ---: | --- |
| manage | 7 | 10 | `audit_projection`, `update_plan`, `advance` |
| preflight | 4 | 7 | `admit_contract`, `advance` |
| execute | 7 | 10 | `stage_artifact`, `advance` |
| audit | 5 | 8 | `verify_grain`, `audit_targets`, `advance` |
| reduce | 3 | 6 | `reduce_round` |

The full scripted Lead round used only the tools offered on each step and
finished with a clean contract and Tier A closure. Person-only controls
(`set_requirement`, `accept_artifact`, `reject_artifact`,
`request_evidence`) remain in no model bundle. A restrictive research-helper
profile sees the same registered phase definitions but receives the actual
read fallback; it does not borrow Lead reachability. Helper, Clerk and
workflow registration likewise does not make those actions reachable from an
audited Lead phase.

## Retry and cancellation fault matrix

The scripted route uses the production `LimitedProvider` and `HostLimiter`.
An Event-compatible virtual clock records the configured backoff without a
timer or sleep.

| Effective profile policy | Injected fault | Provider calls | Virtual waits | Outcome |
| --- | --- | ---: | --- | --- |
| `bounded` | transient, then success | 2 | `[0.25]` | completed; limiter reset |
| `none` | transient | 1 | `[]` | typed `provider_transient`; no slot leak |
| `bounded` | cancel during retry backoff | 1 | `[0.25]` | typed `cancelled`; non-retrying; no slot leak |
| `bounded` | already cancelled | 0 | `[]` | typed `cancelled`; nothing dispatched |

The existing local slow-response fixtures for both OpenAI and Anthropic also
pass: cancelling an in-flight socket returns a typed cancellation within the
declared one-second test bound. Invocation evidence records cancellation as
non-retryable, the Loop stops without an error, and Core shutdown propagates
the same cancellation event.

`retry_policy="none"` disables the host-facade retry. A first-party HTTP
adapter still owns its existing transport-level transient retries. Session
telemetry currently reports inner attempt count as unavailable, so this report
uses fixture-observed call counts and does not infer retries from a Session
log.

## Verification

Focused new and adjacent qualification command:

```text
python -m pytest -q -p no:cacheprovider \
  tests/test_capability_context.py tests/test_remed07_faults.py \
  tests/test_remed07_request_size.py tests/test_audit_projection.py \
  tests/test_g5_readiness.py tests/test_provider_cancellation.py \
  tests/test_agent_runtime_profiles.py tests/test_role_route_bindings.py
```

Result: **80 passed in 42.02 seconds.** The request-size-only command with
`-s` prints the six-row deterministic measurement table. Full suite:
**1,935 passed, 2 skipped, 5 deselected in 629.83 seconds.**

## Limits

- The byte figures are deterministic fixtures for 1/10/50 rounds, not a
  universal maximum or a production traffic distribution.
- Route readiness is informational in the manifest. It does not admit an
  action or replace dispatch-time checks.
- The fault route is scripted. The separate local HTTP fixtures establish the
  real first-party socket-abort boundary without contacting a vendor.
