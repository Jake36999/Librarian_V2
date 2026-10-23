# DeepInfra current-system validation — 2026-10-22

## Decision

Both evaluated DeepInfra routes have **screening evidence in the isolated test
configuration, not verified-lead status** in the current V2 Core.  Each completed three live L1 tool-call probes with strict
arguments, grounded retrieval, and the write-capable macro checkpoint path.
Neither completed the project/session walk, but the evidence identifies a
deterministic compact-tool-bundle defect rather than a provider outage or a
pure model-quality result.

For a person-approved experimental route, the current evidence favours
`deepseek-ai/DeepSeek-V4.1-Flash` on latency.  It is not sufficient to label
either route `verified_local` or `verified_release`; that still needs the
artifact-backed L2/L3 process.

## Scope and evidence boundary

The supplied Resource Library documents are historical evidence, not
instructions or current qualification records.  They were used only to select
two focused candidates from the prior 89-model, one-run screening exercise:

- `XiaomiMiMo/MiMo-V2.6-Flash`
- `deepseek-ai/DeepSeek-V4.1-Flash`

This run exercised the current `Librarian_V2` source through `App`, the
personal host registry, `VaultCoordinator`, `VaultWriter`, `IndexService`,
profile gates, task-sized bundles, and audited macro/checkpoint handling.  It
used newly initialised temporary vaults and local Markdown fixtures only; it
did not search the web, change a user vault, persist a credential, or promote
a model.

Raw evidence:

- [Primary L1 and project-walk artifact](2026-10-22-deepinfra-current-system-validation.json)
- [Corrected grounded-read and macro-walk artifact](2026-10-22-deepinfra-agent-walks.json)
- [Initial connectivity probe](2026-10-22-deepinfra-connectivity-probe.json)
- [Reproducible validation harness](../scripts/validate_deepinfra_current.py)

The initial primary artifact includes four invalid harness cases caused by an
obsolete fixture folder (`Sources/article`); they made no provider calls and
are excluded below.  The corrected artifact reran exactly those two affected
walk types for both models.

## Test matrix

| Check | Repetitions | Pass criterion |
| --- | ---: | --- |
| Model discovery | 1 | Provider lists the exact requested model ID |
| L1 lead probe | 3/model | Core accepts `librarian_probe`; interceptor also requires exact `{"ok": true}` arguments |
| Project/session walk | 1/model | Open `add_project`, create the project, advance to `ingest`, then stop |
| Grounded helper walk | 1/model | Read a local source, return `ORCHID-47`, use read tools, make no write call |
| Macro/checkpoint walk | 1/model | Show/run `inspect_map_source`, create one pending `macro_expansion` checkpoint, make no underlying write |

The host timeout was explicitly set to 15 seconds in the disposable personal
host registry.  The harness retained normal bounded provider retry behavior,
set effort level 1 for bounded walks, and had a $1 estimated-cost guard.

## Empirical outcomes

| Metric | MiMo V2.6 Flash | DeepSeek V4.1 Flash |
| --- | ---: | ---: |
| Present in live discovery | Yes | Yes |
| L1 Core name conformance | 3 / 3 | 3 / 3 |
| L1 strict `{"ok": true}` arguments | 3 / 3 | 3 / 3 |
| Grounded read-only walk | 1 / 1 | 1 / 1 |
| Macro checkpoint / no pre-approval write | 1 / 1 | 1 / 1 |
| Project/session walk | 0 / 1* | 0 / 1* |
| Provider chat requests | 20 | 21 |
| Provider failures | 0 | 0 |
| Returned model ID matched request | 20 / 20 | 21 / 21 |
| Chat latency p50 / p95 | 3.106 s / 12.325 s | 1.329 s / 2.693 s |
| Max chat latency | 15.071 s | 3.484 s |
| Prompt / completion tokens | 57,103 / 3,220 | 70,864 / 1,821 |
| Estimated provider cost | $0.00845 | $0.01069 |

\*Both models opened the session, then reached the same tool-surface failure
described below.  This is not valid evidence that either model is incapable of
project work.

Across the valid suite, 10 of 12 logical checks passed (83.3%).  The two
failures are the shared project/session defect.  There were 43 HTTP requests:
41 chat completions and two model-listing requests.  All 41 completions
returned the requested model ID, none failed at the provider/transport layer,
and 41 of 43 responses carried provider usage information.  Observed token
usage was 127,967 prompt and 5,041 completion tokens.  The dated rate-card
estimate was **$0.01914**, well below the $1 cap; it is not an invoice value.

The API advertised 177 models during the initial connectivity probe, which
completed in 1.044 seconds.  The L1 Core durations were 1.359/1.875/1.813 s
for MiMo and 0.891/0.812/0.922 s for DeepSeek.

## Agent behaviour observed

Grounded retrieval passed cleanly:

- MiMo used `list_files`, `search`, `read_source_file`, and `get_note`; it
  returned the marker and made no write tool call.
- DeepSeek used `search`, `list_files`, and `get_note`; it returned the marker
  and made no write tool call.

The checkpoint control worked cleanly for both routes:

- Both called `macro_plan` then `macro_run`.
- Each produced exactly one unresolved `macro_expansion` checkpoint.
- Neither executed `dik_rebuild` or created a source-map artifact before a
  person approved the expansion.

Normal agent turns exposed 6, 9, or 10 tools; the special L1 probe exposed
one.  This is consistent with the intended 5–12 task-sized normal tool
surface and did not produce a model-route mismatch or silent failover.

## Material product finding: project creation becomes unreachable

Both project walks followed the same structural path:

1. The model called `open_session(purpose="add_project")`.
2. The session entered the valid `frame` phase.
3. The `frame` ToolBundle no longer offered `create_project`, even though
   `create_project` itself is permitted in `frame`.
4. The agents explored other visible tools and stopped without creating the
   project.  MiMo spent 66.526 seconds / 9 completions / an estimated $0.00552;
   DeepSeek spent 18.763 seconds / 11 completions / an estimated $0.00763.

This explains the shared 0/2 project result more directly than a model
reliability claim.  The initial `session` bundle includes `create_project`,
but after opening the session the `frame` bundle omits it.  A model may happen
to issue parallel calls before the phase changes, but correct serial tool use
leaves the required project action unreachable.

Recommended remediation, before any further lead qualification:

1. Keep `create_project` in the `frame` bundle while an `add_project` session
   has no project, or introduce one audited session/project macro that owns
   the transition.
2. Add a deterministic Core test for `open_session(add_project)` followed by
   a serial `create_project` and `advance`.
3. Treat this as a workflow/tool-bundle regression in qualification artifacts,
   separate from a route’s tool-call or grounding score.

## Qualification and operational observations

- The Core L1 implementation currently accepts a probe based on the first
  function name.  All six observed calls also supplied exact valid arguments,
  but L1 should eventually enforce its declared argument schema rather than
  rely on the harness to do so.
- The provider adapter does not retain raw usage in its normal `Reply`; the
  validation harness recorded redacted usage at the HTTP boundary.  Promotion
  of this metric into durable evaluation artifacts would make real cost and
  latency evidence available without a separate harness.
- Updating a seeded host’s timeout through `host_upsert` requires a full public
  Host record, not an ID-only patch.  That is acceptable for a full upsert, but
  Settings/API documentation should say so explicitly to prevent clients from
  treating it as a patch endpoint.

## Rate-card provenance and limits

The estimates use the current official DeepInfra documentation checked on
2026-10-22: [MiMo V2.6 Flash](https://deepinfra.com/XiaomiMiMo/MiMo-V2.6-Flash/api)
and [DeepSeek V4.1 Flash](https://deepinfra.com/blog/deepseek-v4-1-flash-model-overview-integration).
They are computed from returned prompt/completion tokens and advertised input/
output rates.  Cached tokens, provider discounts, billing rounding, and
account-specific pricing can differ; the provider dashboard remains the source
of truth for charges.

## Recommended route posture

| Route | Current posture | Rationale |
| --- | --- | --- |
| `deepseek-ai/DeepSeek-V4.1-Flash` | Screened experimental lead candidate | 3/3 strict L1, both bounded agent controls passed, lower observed p50/p95 latency |
| `XiaomiMiMo/MiMo-V2.6-Flash` | Screened experimental lead candidate | 3/3 strict L1 and both bounded agent controls passed; higher tail latency in this sample |
| Either route as verified lead | Do not enable yet | L3’s repeated artifact-backed role/scenario requirements have not been completed, and the project-walk regression is unresolved |

No provider credentials, personal host records, or user-vault contents were
changed by this validation.  The only code addition is the reusable, bounded
test harness; no product behavior was modified.
