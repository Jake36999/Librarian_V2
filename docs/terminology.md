# Librarian terminology

**Status:** Normative vocabulary for V2 documentation and implementation.
The [unified implementation plan](unified-implementation-plan.md) remains the
delivery-status authority.

## Authority and execution

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Core | The single mutable authority for one vault: coordinator, writer, index service, leases, session append path, and policy boundary. | A browser, Obsidian adapter, Cowork/MCP process, or CLI client. |
| Registry tier | `consult`, `contribute`, or `curate`: the maximum tool authority of a caller. | A model-picker position, model quality level, or work budget. |
| Role slot | A semantic assignment: `lead`, `scribe`, `clerk`, `research_helper`, `ocr`, `tts`, `stt`, or `embeddings`. | A legacy positional tier. |
| Legacy position | The existing three-picker compatibility projection: Lead, Scribe, Clerk. | The canonical vault-scoped role-to-route binding. |
| Route | One host plus exact provider model, protocol adapter, expectation record, and qualification evidence. | A provider family or catalogue tile. |

## Model evidence and controls

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Capability state | `supported`, `unsupported`, or `unknown`. `unknown` means unassessed and may be experimental; it is not `unsupported`. | Qualification. |
| Qualification | `unavailable`, `experimental`, `screened`, `verified_local`, or `verified_release`, based on route- and role-specific evidence. | Evidence freshness. |
| Evidence freshness | `current`, `advisory_stale`, or `hard_invalid`. A hard compatibility dependency invalidates qualification; a soft change produces advisory stale evidence until rechecked. | A route's qualification level. |
| Work budget | Librarian's universal ceiling for time, turns, tools, delegation, output, and spend. | A provider's hidden reasoning or thinking setting. |
| Native behaviour | A route-specific provider control permitted only by a reviewed expectation record and matching qualification evidence. | A generic effort slider or an instruction embedded in a pack. |
| Invocation plan | The immutable, non-secret resolved contract a trusted adapter may render and validate. | Authority to choose a route, invoke a tool, or alter policy. |

## Durable work state

| Term | Meaning | Must not be confused with |
| --- | --- | --- |
| Session state | `open`, `parked`, or `closed`. A parked session has durable partial work and may be resumed; it is not complete. | A provider chat thread or an SSE connection. |
| Execution outcome | A bounded result such as completed, refused, failed, cancelled, interrupted, or needs-person. It describes an attempt. | Audit integrity or semantic closure. |
| Audit integrity | `clean`, `suspect`, or `violation`, determined by a deterministic or approved audit. | Whether a research conclusion is true. |
| Closure state | `open`, `partial`, `verified`, or `human_judgment`. Only exact/bounded deterministic evidence may produce `verified`; synthesis remains human judgment. | Session closure. |
| Checkpoint | A structured, visible decision or conflict record that blocks only its affected operation until resolved or expired. | Silent model policy prose. |

## Delivery status

| Status | Meaning |
| --- | --- |
| implemented | Source code and focused deterministic tests exist; system or release evidence may still be required. |
| partial | Some code exists, but an invariant, integration path, or acceptance test remains missing. |
| planned | A requirement exists but no accepted implementation is claimed. |
| blocked externally | Completion requires a protected credential, signing material, provider budget, or target environment. |
| retired | Explicitly excluded from V2. |

Do not use `ready`, `qualified`, `verified`, or `complete` as substitutes for a
delivery status.
