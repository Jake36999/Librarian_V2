# Librarian V2 system attention, deployment, and runtime review

**Review date:** 2026-10-23  
**Scope:** source review, focused local regression tests, and the preceding
bounded DeepInfra validation artifact. This is a documentation-only review:
no product behaviour was changed.

## Executive assessment

Librarian has a strong safety direction: its vault lease, writer, document
leases, profile gates, checkpoints, and qualification vocabulary are all
substantial improvements over a loosely coupled research assistant. The
highest remaining risks are integration gaps, not missing aspirations.

The immediate priorities are:

1. make adoption of an existing documentation tree explicit and
   non-destructive;
2. restore the promised single-owner SQLite boundary;
3. make profile-to-route assignment, readiness evidence, and the model picker
   describe the route that will actually run;
4. fix the reproducible Host graceful-stop failure before calling the desktop
   lifecycle release-ready; and
5. separate Librarian work budgets from provider/model reasoning controls.

The existing hidden .librarian directory should remain an operational state
directory. It should **not** become a place where user documentation lives.
The source currently leaves visible Markdown visible to Obsidian, but it does
not yet give an existing arbitrary documentation tree a first-class adoption
or search contract. That distinction explains the apparent contradiction in
the current experience.

## Evidence and limits

### Focused regression results

The following source-tree tests were run with
PYTHONPATH set to D:\Librarian_V2\src:

| Area | Result | Interpretation |
| --- | ---: | --- |
| Library picker, index, search, search contract | 35 passed | Existing covered adoption and normal search behaviours remain green. |
| Effort, qualification jobs, Host lifecycle, V2 remediation | 25 passed, 1 failed | The Host starts a Core but does not report a clean stop within its 15-second grace window. |
| Core index service, profiles, provider failures, validation fixtures, release leads | 33 passed | The targeted contracts work, but do not prove every tool follows them. |
| Host lifecycle test rerun alone | failed again | The failure is reproducible rather than a suite-order flake. |

The failing test is
tests/test_host_lifecycle.py::test_host_managed_core_starts_and_stops_cleanly.
The authenticated /api/host/stop request returns {"stopping": true}, but
HostManager.stop() subsequently returns stopped: false because the child is
still alive after the 15-second drain window. A separate manual diagnostic
reproduced the same result. The process eventually exited, so the evidence
points to a shutdown/drain sequencing or observability issue, not a refusal
to accept the stop request. It is nevertheless a release-blocking desktop UX
bug: a person pressing Stop sees a failure despite having done the correct
thing.

### Current live runtime evidence

The post-fix bounded validation artifact exercised two DeepInfra routes with
temporary vaults and no user-vault writes:
[raw artifact](2026-10-23-deepinfra-post-fix-validation.json).

| Metric | MiMo V2.6 Flash | DeepSeek V4.1 Flash | Combined |
| --- | ---: | ---: | ---: |
| Logical cases passed | 4 / 4 | 4 / 4 | 8 / 8 |
| Strict L1 probe | 1 / 1 | 1 / 1 | 2 / 2 |
| Focused walks | project, grounded read, macro checkpoint | project, grounded read, macro checkpoint | 6 / 6 |
| Provider/transport failures | 0 | 0 | 0 |
| Returned model matched request | all 15 requests | all 12 requests | all 27 chat requests |
| Chat latency p50 / p95 | 2.117 s / 4.414 s | 1.297 s / 2.843 s | 1.812 s / 3.772 s |
| Prompt / completion tokens | 39,659 / 1,009 | 32,114 / 1,011 | 71,773 / 2,020 |
| Estimated provider cost | $0.005543 | $0.004921 | $0.010464 |

This confirms that the earlier serial project-walk tool-bundle regression was
fixed for these two routes. It is useful performance evidence, not a
qualification shortcut: each route has one L1 and one run of each focused
walk, not the repeated role/scenario evidence required for L2 or L3.
Provider pricing and usage remain estimates rather than invoices. This sample
does not measure UI latency, time-to-first-token, queueing, concurrent
sessions, retry/circuit-breaker behaviour, full-vault scale, or provider
billing reconciliation.

## P0 — fix or prove before a stable desktop release

| Finding | Evidence | Why it matters | Required verification |
| --- | --- | --- | --- |
| Host graceful stop is not dependable | The real-child lifecycle test fails reproducibly after the stop endpoint accepts the request. | A tray Stop/Restart experience that says “still draining” after an idle Core undermines user trust and can leave stale lease diagnostics. | Add phase-level shutdown telemetry; test idle, writer-busy, active-turn, active-checkpoint, and forced stop paths. Assert both process exit and lease/connection-record cleanup. |
| Core-only SQLite ownership is incomplete | The product contract says Core-owned IndexService is the sole SQLite owner, while tools can still call engine_for(ctx), which constructs a direct Index. | Direct connections can defeat the serial IndexService and recreate Windows WAL/SQLITE_BUSY risk under multi-client activity. | Statically forbid direct Index/engine_for use in Core-serving tool paths; run concurrent browser/Obsidian/Cowork/agent read-write/checkpoint stress tests. |
| Existing-doc adoption is unsafe by default | init() creates standard visible folders and starter notes without a structural survey; it can reuse an unrelated .librarian directory. | Pointing Librarian at F:\quantule_mapper\docs can preserve files but still alter an established structure or assign unintended Librarian meaning to existing folders. | Add a read-only plan/confirm/apply flow and test an existing .librarian, Sources/Projects collisions, Git/Obsidian trees, junctions, and plan-to-commit changes. |
| Agent profiles do not yet choose their routes | AgentProfile.route_policy is an allow-list; the main loop still selects legacy tier 1 and helpers/Clerk select tier positions. | The interface and documentation imply role-based configuration, but the chosen role can be constrained without becoming the route that runs. | Add a canonical profile/slot route binding and prove lead, scribe, clerk, and helper each execute the configured route. Preserve tiers only as migration adapters. |
| Readiness can show evidence for the wrong role | route_readiness() selects one active profile role and applies it across every tier; the model tile requests it without a slot/profile. | A tier-2 or tier-3 card can look qualified using lead evidence even though execution correctly requires scribe/clerk evidence. | Return readiness per route **and role/slot**. Add a divergent-evidence fixture that proves no card inherits lead qualification. |
| Migrated preset-host routes are not a safe UI round trip | Legacy migration changes the DeepInfra provider identity to preset-deepinfra, while the tile still filters and compares against deepinfra. | A previously selected route can disappear as selected, and a subsequent selection can mix legacy provider and canonical host identities. | Make the picker data-driven from Host Registry IDs; add a migrate-open-select-save-reopen fixture for every seeded host. |

## P1 — high-value correctness and UX work

### Existing documentation is scanned, but not adopted as a usable corpus

notes.iter_paths() recursively scans visible Markdown and intentionally skips
dot-directories. Therefore documentation at F:\quantule_mapper\docs is not
required to sit inside .librarian, and it remains visible in Obsidian.
However, arbitrary files without Librarian frontmatter or known top-level
folders receive an empty shape. Normal research-search paths primarily operate
over recognised shapes, so those documents are not reliably discoverable to
agents as project documentation.

This is a feature drop in practice:

- the user sees existing files in Obsidian;
- the index may know the files exist;
- the agent's ordinary source-search workflow cannot reliably find or
  distinguish them as a deliberate document corpus.

The solution is not to rewrite project documentation or hide copies under
.librarian. It is to give adopted roots a virtual, read-only
workspace_document identity with provenance and a dedicated search scope.

### Model-picker and host-registry mismatch

The host registry accepts arbitrary OpenAI-compatible hosts, while the chat
model tile is still organised around DeepInfra, OpenAI, Anthropic, and local
providers. Legacy migration also converts the DeepInfra identity to the
canonical preset-deepinfra host ID while the tile continues to compare against
deepinfra; a migrated selection can therefore render as unselected. Settings
can make a custom host the selected lead, but its current “Use as lead” action
sends a one-item legacy tier list and silently removes the other two
assignments. Service-slot selection is also uneven: OCR and embeddings reject
custom host IDs on the server side, while UI filtering relies heavily on
model-name patterns. STT/transcription is not currently implemented as a
service slot even though user expectations and the settings concept imply
TTS/STT/OCR configuration.

The model configuration surface needs one canonical assignment model:

~~~
role/slot -> host -> exact model -> capability configuration -> qualification
~~~

The current tier list should be a visible compatibility projection, not a
second competing source of truth. TTS, STT, OCR, embeddings, lead, scribe,
clerk, and helper must all declare whether custom OpenAI-compatible hosting is
supported, unsupported, or requires a curated adapter.

### Catalog truth and deduplication drift

The current DeepInfra catalog has 102 shipped profiles, while the latest
discovery artifact saw 176 provider models. That is acceptable only if the UI
clearly distinguishes “discovered but unprofiled” from “profiled and known
unsupported.” At present, App.models() coerces nullable tool_calling with
bool(...); 10 catalog records with unknown/null capability consequently become
false. The tier-1 picker then blocks them as if support were explicitly known
to be absent.

Use a three-state capability:

~~~
true       documented/observed supported
false      documented/observed unsupported
unknown    not yet assessed
~~~

Only explicit false should block a lead placement. Unknown should remain
selectable as experimental, with an L1/expectation-conformance action.

Catalog documentation says canonical URLs avoid duplicates, but the current
promotion/catalog check is name-based. A renamed catalog item can therefore
represent the same canonical URL twice. The catalog needs the same
identity-first dedupe policy proposed below.

### Effort means two different things today

The existing effort control governs Librarian workload: agent count, turn
steps, time, budget scale, and review work. It does **not** currently send
OpenAI reasoning_effort, Anthropic thinking/effort configuration, or a
reviewed DeepInfra model-specific control. Calling it “effort” without this
qualification leads people to believe the provider received a native reasoning
request when it did not. It also does not dynamically select more distinct
models: a higher setting permits more work on the routes already configured.

The UX should present:

1. **Work budget** — universal, controls what Librarian is allowed to spend
   and attempt.
2. **Model behaviour** — route-specific, shown only when a reviewed
   expectation record says the adapter can safely send a native reasoning or
   template control.

The formal proposed contract is in
[Model expectations registry](../docs/model-expectations-registry.md).

### Runtime observability stops at the validation harness

The validation harness can record redacted HTTP-boundary usage and latency, but
the normal provider Reply path does not retain enough request/usage/reasoning
metadata to make these metrics durable qualification evidence. Extend the
non-secret trace with a request ID, effective-configuration hash, requested
and observed model, queue time, retries/failure class, provider latency,
usage availability, and outcome. Keep raw provider payloads and reasoning
content out of the vault trace.

### Personal defaults leak into a new vault

Hosts and credentials should remain personal. Agent profiles should remain
vault-scoped. The current Settings shared set deliberately shares tiers,
lead-overrides, and effort across libraries, so a newly adopted vault can
inherit a model selection and effort value from another library. That is a
reasonable onboarding default, but it must be shown as an explicit choice:
“Apply my personal defaults” or “Start with empty vault assignments.” It
cannot be treated as a silent per-vault configuration.

## Recommended deployment model for existing documentation

### The product choices

Do not make a populated directory follow the same path as a blank library.
The picker should make the difference explicit before touching disk:

| Choice | Intended use | Files created by default | Document handling |
| --- | --- | --- | --- |
| **Create a Librarian library** | A new/empty research vault | Standard layout, starter notes, operational state | Librarian owns the layout. |
| **Adopt this documentation directory** | Existing project docs such as F:\quantule_mapper\docs | Only minimal state after confirmation | Existing files stay in place, are never rewritten, and become one or more explicit content roots. |
| **Attach documentation without modifying its root** | Strict repository/no-touch requirements | State in a user-selected companion location | The docs root is read-only to Librarian; a visible output workspace is selected separately. |

For the normal adoption choice, .librarian is appropriate only for state:
leases, index, manifests, sessions, staging, and settings. It stays hidden in
Obsidian by design. Existing project documentation remains outside it and
visible. A visible Librarian workspace must be optional, created only after
the user chooses a location for Librarian-authored notes; it is never an
automatic copy of the existing documentation.

### Read-only adoption plan

Before initialization, show an adopt_plan produced by a read-only survey:

~~~
root identity and filesystem case rules
existing Librarian state / unrelated .librarian conflict
Markdown, attachment, and generated-file counts
candidate content roots and proposed excludes
Obsidian, Git, workspace, build/cache, and symlink/junction detection
known Librarian-layout name collisions
frontmatter / recognised-shape coverage
exact and near-duplicate candidate groups
estimated first-index time and storage
survey fingerprint
~~~

The user selects roots, exclusions, read-only/read-write status, and an
optional generated workspace. adopt_apply must require the survey fingerprint;
a changed file tree causes a refresh rather than silently applying an obsolete
plan.

An unrelated existing .librarian must be a hard stop, not a directory to
reuse. The UI should offer: select another state location, inspect the
conflict, or explicitly migrate a recognised old Librarian state. It must
never merge opaque state based solely on folder name.

### A content-root contract

Persist a versioned, vault-scoped deployment manifest conceptually like:

~~~
DocumentRoot = id, canonical_path, mode, include, exclude,
               fingerprint, purpose, added_at, last_scan_at
~~~

Each indexed document retains document_root_id, canonical relative path,
content fingerprint, and an origin type. Existing project documents should
enter as workspace_document, not be assigned a research source shape because
they happen to live in a folder called Sources. Agents then receive a compact
workspace search/read capability when their task includes adopted project
documentation. This preserves current research evidence semantics while
making the existing corpus usable.

### Dedupe policy for deployment and subsequent scans

Dedupe should be a layered, reviewable identity process:

| Level | Key | Outcome |
| --- | --- | --- |
| Physical-path equivalence | Canonical Windows path, case-folding, resolved junction/symlink and, where available, volume/file identity | Scan once; do not follow loops. |
| Exact bytes | SHA-256 of original bytes | Report one content identity with multiple locations. |
| Normalised text | Versioned Markdown/text normalisation hash | Find equivalent documents differing only in line endings or harmless formatting. |
| Canonical external identity | DOI, canonical URL, repository remote + pinned revision, explicit frontmatter ID | Join representations of the same source. |
| Near duplicate | Bounded shingle/MinHash or equivalent lexical candidate score | Suggest a review group only; never merge automatically. |

The baseline stores paths, identity keys, hashes, scanner/version metadata, and
the person's resolution. It does not delete, rename, rewrite frontmatter, or
move files. A move with the same byte hash becomes a renamed location rather
than a newly ingested document. Ambiguous groups receive actions such as
“keep separate,” “mark same logical document,” and “choose canonical
presentation”; all choices are reversible and auditable.

## Documentation assessment

The core documents are unusually clear about the target safety model:
[product contract](../docs/product-contract.md),
[qualification](../docs/qualification.md), and the
[capability matrix](../docs/capability-matrix.md) correctly describe the
one-Core, checkpoint, qualification, and V1 continuity intent.

They need a release-readiness pass in four areas:

1. **State the implemented boundary separately from the intended boundary.**
   The product contract currently says the Core alone owns SQLite. The direct
   engine_for() paths mean that statement is not yet universally true.
2. **Add an “existing documentation adoption” guide.** It should explain
   Create, Adopt, and Attach, what .librarian contains, why it is hidden, and
   why project docs are never moved there.
3. **Make role assignment legible.** Documentation presently describes
   profiles as replacing positional tiers while execution still depends on
   tiers. Until route binding is implemented, say that profiles constrain
   legacy tier routes rather than select them.
4. **Rename/explain effort.** User-facing copy needs the distinction between
   a universal Librarian work budget and a route-specific native reasoning
   setting. It should never promise that changing the slider sends a
   provider-native parameter.

The checked-in release manifest and release-lead data are honestly described
as development candidates. Keep that wording until signed artifacts and
actual L3 evidence exist; do not soften it into an out-of-the-box verified
lead claim.

## Regression matrix to add

### Adoption and Obsidian

- populated tree remains byte-identical after planning and after minimal
  adoption, apart from explicitly approved state files;
- existing arbitrary Markdown is searchable through the workspace_document
  scope without frontmatter rewrites;
- .obsidian, .git, build caches, dot-directories, and configured excludes
  are not ingested;
- unrelated .librarian causes a conflict, not a mutation;
- standard folder-name collisions do not assign a schema accidentally;
- symlink/junction loops and paths outside an approved root are rejected;
- changes between plan and apply invalidate the plan;
- a human editing an adopted document gets document-scoped conflict handling,
  not a vault-wide lock.

### Concurrency and lifecycle

- a static test rejects direct SQLite construction in serving paths outside
  IndexService;
- concurrent agent reads, Obsidian reads, index refreshes, WAL checkpoints,
  and writer operations run without SQLITE_BUSY/cross-thread connection
  errors;
- Host stop records request accepted, writer drained, index closed, lease
  released, and process exited, with a bounded timeout per phase;
- force-stop and crash recovery leave no false-live connection record.

### Models and UX

- every role/slot renders readiness for its own route and qualification role;
- a custom OpenAI-compatible host can be assigned without clearing unrelated
  slots;
- the custom-host “Use as lead” action patches only the lead binding and
  preserves scribe/clerk bindings;
- a migrated seeded-host selection renders, saves, and reopens under one
  canonical Host Registry identity;
- unknown tool support is not rendered as false;
- explicit unsupported service-host combinations are explained before save;
- catalog canonical URL/model/endpoint identity prevents renamed duplicates;
- a profile route binding controls the actual provider selected by lead,
  scribe, clerk, and helper paths;
- test fixtures cover native reasoning settings only where a reviewed
  expectation record permits them.

## Recommended order of work

1. Repair and instrument Host stop; restore a green real-child lifecycle
   test.
2. Complete the IndexService ownership audit and add the static/concurrency
   regression guard.
3. Design and implement the read-only adoption planner and content-root
   manifest before exposing populated-directory deployment more broadly.
4. Make profile route bindings canonical, then make picker/readiness/service
   controls consume that same source of truth.
5. Introduce the expectations registry and use it first for the most-used
   routes, not for all 200+ provider models at once.
6. Update user documentation and release checks to describe only the
   behaviour that the preceding tests prove.

## External research used for the model recommendation

Model cards are valuable provenance and expectation sources, but not a
universal runtime contract. Hugging Face describes them as Markdown plus
metadata and encourages them to document use, limitations, and evaluation
context; its chat-template guidance explicitly says tool formatting and
special tokens must match what the model was trained on.
[Hugging Face model cards](https://huggingface.co/docs/hub/main/en/model-cards)
and [tool chat-template guidance](https://huggingface.co/docs/transformers/chat_templating_writing)
support the registry approach rather than generic prompt injection.

The model-specific differences are concrete. Qwen documents an
enable_thinking template control with separate suggested settings for thinking
and non-thinking operation; DeepSeek V3.1 documents tool calling in a
specific non-thinking template.
[Qwen 3 model card](https://huggingface.co/Qwen/Qwen3-8B)
and [DeepSeek V3.1 model card](https://huggingface.co/deepseek-ai/DeepSeek-V3.1)
show why family-name inference is not sufficient. OpenAI likewise documents
different reasoning_effort availability by model, and Anthropic documents
model-generation-specific thinking/effort behaviour.
[OpenAI API reference](https://platform.openai.com/docs/api-reference/chat/object?lang=ruby)
and [Anthropic prompting guidance](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/prompt-templates-and-variables)
support keeping native controls route-specific.
