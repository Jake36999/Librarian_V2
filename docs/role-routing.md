# Role routing and service selection

Status: implemented routing boundary; adapter transport extraction and live
qualification remain separate tasks in the unified implementation plan.

## Authority and compatibility

`<vault>/.librarian/agents/routes.json` is authoritative after migration for
Lead, Scribe, Clerk, research_helper, OCR, TTS, STT and embeddings. Chat tiers
in `app.json` and service strings in `config.toml` are compatibility
projections. Startup repairs these projections; editing a projection does not
silently change a selected route. Use the existing picker or Core APIs.

The one-time service migration preserves a legacy `[search] vectors` setting.
Afterwards, explicitly clearing the embedding slot disables it; the legacy
setting cannot silently re-enable it. A malformed binding store fails closed.

Profiles select a model slot without changing their task role or authority.
An analyst using the Scribe slot needs analyst qualification, not Scribe or
Lead evidence. Inherited model selection does not inherit qualification.

## Passive readiness

`GET /api/routes/readiness` returns the active chat bindings and each route's
`qualification_by_role`, `bound_roles`, `binding_errors`, and `host_enabled`.
The existing `qualification` field describes the selected profile's task role;
`active_task` identifies the route that profile would execute. No discovery,
probe, evidence invalidation, or paid evaluation is triggered by this read.

The three-position picker labels evidence for the selected/next slot. It also
shows a distinct active-task label when that profile's role differs. Expired
or incompatible evidence and unusable bindings are shown explicitly. Service
tiles never borrow chat qualification: their adapter line is a service
contract declaration, not a tested reliability claim.

## Service APIs and custom hosts

`POST /api/services` keeps the existing `slot`, `provider`, `model` interface.
It also accepts an explicit `host_id` for OCR and hosted embeddings. Explicit
IDs are never reinterpreted as preset aliases, even if named `deepinfra` or
`hash`. Connections offers manual/discovered custom-host assignment alongside
the existing preset tile. Empty `model` clears only the selected service slot.

`GET /api/services` exposes `binding`, `route_status` and, where relevant,
`route_error`. Missing/disabled/changed hosts stay visible for repair rather
than falling back to an unrelated endpoint. Service calls use the bound
endpoint and personal credential reference; no key value enters the vault.

- OCR and hosted embeddings support explicit OpenAI-compatible endpoints.
- TTS/STT require the reviewed native DeepInfra endpoint and supported service
  contracts. An arbitrary chat-compatible host does not imply speech support.
- Local embedding engines remain explicit local selections.
- Custom embedding namespaces include the endpoint fingerprint to prevent
  mixing vectors from different hosts that advertise the same model name.
- A familiar provider name on a custom host confers no provider-specific
  contract or qualification evidence.

The Core's existing HostLimiter is shared by chat and hosted service calls.
Service IO rechecks its binding after waiting for admission and after its
response. Shutdown counts outstanding service calls and rejects late results
before downstream cache/vector processing. This is not yet abortable HTTP:
ADAPT-04B/06 still own cancellable transport, transport unification, and local
compute prioritization. This packet does not claim to close all direct
SQLite or service-cache write paths.
