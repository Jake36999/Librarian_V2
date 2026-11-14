# Content access model

Normative owner contract, approved at OWNER STOP C0 on 2026-11-14. Its vocabulary and settled decisions supersede the earlier scope report's `own` shorthand and undecided D1/D3/D5/D6 proposals. The C0 inventory records current divergences; this contract is not a claim that S1–S6b and R have shipped.

## Authorship and access

| Material | Person | LLM agent |
|---|---|---|
| `owner_created` — internal documents, code and tools | Full access; ingested completely | Full access; completely ingested into the Librarian index and the appropriate Geo graph |
| `third_party` — other people's work | Free access to the original. The catalogue gives a brief summary, relevance, prior use and expandable chapter summaries. A generated conversion is never presented as an original source. | Default entry is the catalogue, then the graph of the full conversion, then the relevant section, then a bounded check against the original pages. Verification uses two tier-2 tasks or one tier-1 task. No whole-document default read, repeated OCR or page scouting. Explicit tier-1/2 grants are described below. |
| `generated` — drafts, conversions, summaries and use logs | Hidden under `.librarian/` until accepted. Acceptance makes a note visible; it does not turn a conversion into an original source. | Readable as labelled library work, never cited as the primary source |

The closed vocabulary is **`owner_created | generated | third_party`**. `own` in older plans means `owner_created`, never a fourth value.

- **owner_created:** the owner's own documents, code and tools. Examples: an internal architecture plan, original project code, the owner's first-hand model test notes.
- **generated:** Librarian or agent output. Examples: an unaccepted folder description, a PDF conversion, a synthesis, a use-log rollup. It stays distinguishable from the material it describes.
- **third_party**, also called **unlicensed** in the owner's policy: other people's work that the library studies and cites. The library is not its licence distributor. It must not be copied into an own repository/product or represented as own work, regardless of its repository licence. This is the owner's ingestion/attribution rule, not a replacement licence classification.

Mixed records retain authorship at the relevant field/span: distributor quotations in an owner-curated model card remain third_party; the owner's observations remain owner_created. Accepting a draft does not silently change the authorship of quoted source material.

## Domains, objects and classification

`internal` covers owner_created and generated. `external` covers third_party. Trust tiers are ranking weights and read/write access is permission; neither substitutes for authorship or domain.

An unsupported or unclassifiable video, image set or other format is listed as catalogue kind `object` and is not graphed. Object is not a fourth authorship value. A graph without a domain is a flagged defect for owner classification; never silently default it to internal or external. Existing defects remain visible until classified. B2 adds the domain gates after owner approval at S6.

Accepted folder purposes determine authorship:

| Purpose | Authorship |
|---|---|
| own-current, own-legacy, own-docs | owner_created |
| research-docs, third-party | third_party |
| data, logs/transcripts | Explicit person choice; no default |
| exclude | None; excluded from both systems |

An accepted child override changes purpose and authorship together. Attached source projects stay read-only, including owner_created projects. An unchanged accepted decision is retained; changed evidence reopens review. A source/folder not read is `not examined`.

## Model roles and route budgets

Model tiers 1/2/3 are not native registry consult/contribute/curate authority tiers. Profiles, Core leases, permissions, checkpoints and task bundles continue to apply. No role choice promotes an agent to person authority.

All token budgets are clamped to the active route's **declared** window:

`effective tokens = max(0, min(owner cap, declared window − actual prompt tokens − visible output reserve − reasoning reserve))`.

For a comparison, both source allocations must fit that one remainder; a per-source cap is not a separate window. Do not advertise 200k + 200k token reads on a 262,144-token route. Preserve the existing per-call result cap `min(160,000 characters, 12% of the route context setting)`. Tokens and characters are distinct units; a character approximation is not a token-count proof.

| Role | Reading policy |
|---|---|
| Tier 1, lead | Third-party reads, including explicit one-off raw grants, within the active route and existing result cap. Default research still locates through catalogue/graph. The owner's catalogue lists about 1M-token lead routes; the bound route's declaration wins. |
| Tier 2, research helper | Prompt to locate relevant sections first. Intent: about 200k tokens for one source, or a balanced comparison, clamped to the window and reserves. The owner-provided current Gemma/Qwen window is 262,144 tokens, so a 400k-token comparison cannot fit. Report actual allocations when S4 implements them. One-off raw grants are permitted. |
| Tier 3, Clerk | No free reading or raw-access grant. Search/graph location must produce explicitly bounded targets before extraction/viewing. Existing Wave L PLAN_SCOPE refusal for direct third-party graph anchoring remains; S4 adds a controlled target route rather than free graph access. The owner's 200k–500k intent has unresolved units. Current Clerk declaration: 262,144-token window, 1,800 visible output tokens and 1,024 reasoning-reserve tokens. Clamp to the declared window regardless of the unit decision. |

**DECIDED C0-1 (2026-11-14): tokens.** The Clerk's intended 200k–500k input allocation is always clamped to the actual bound route's declared window minus measured prompt, visible output and reasoning reserve. S4 must also size each tier-3 task to its visible output capacity, not just its input capacity: the current Clerk's 1,800-token visible output was the binding pilot constraint. Split tasks or bound deliverables to fit; report effective input allocations and output allowances per actual route. No new route allocation has been measured or enabled at this documentation step.

**Existing cap unit mix (A5):** the `12%` calculation takes a context setting expressed in tokens, then uses that number as a character limit, capped at 160,000 characters. It is not a 12%-of-window token allowance. There is no explicit characters-per-token conversion basis in that formula. Keep runtime behavior unchanged until S4 states an explicit basis and tests the resulting budgets.

D3 is settled: a person may grant tiers 1/2 one-off raw access through a scoped checkpoint. The earlier "disabled until D3 is decided" text is superseded by that approval; the grant mechanism is still unimplemented and is not silently enabled at C0. Tier 3 requests bounded targets only. A person's original-file access is unchanged.

## Untrusted content and publication

A third-party/unknown-external result marks the session untrusted for canonical publication. **Reading stays available.** Canonical publication requires staging/person review or a fresh, source-showing per-call broker approval. This is not a blanket reading ban. S1's initial ordinary/audited tests exposed the old gap; the owner reviewed it and approved the central remedy on 2026-11-14. First failures remain in the closure-stop report.

The owner-approved T1–T4 rules are implemented centrally in the S1 candidate:

- Block every `effect=vault_write`, `_PROMOTE`/`_PUBLISH` operation and `project_edit` after taint. Reads, staging and `effect=write` work-state operations remain available, subject to their independent phase/scope/permission gates. `record_application` is explicitly exempt: a generated use log with attached taint sources, not a content-read conformance claim.
- Persist a set of source handles in session events, surviving turns, park/resume and branching. New sessions start clear. A legal rewind before the tainting event clears that history; existing rewind barriers are preserved. A person may clear the exact source set through a scoped, non-reusable checkpoint. Legacy untrusted/open-world call histories conservatively retain opaque handles on replay; person calls remain unaffected.
- Refuse with `COMPOSITION_REFUSED`, naming source handles and the staging route, or require a fresh broker ask that shows the source set. Auto mode, previous Allow/session grants and mode switches cannot substitute for that review. Tainted `project_edit` asks include: **derived from third-party (unlicensed) material: do not copy it into this repository**. A changed source set invalidates an in-flight approval. `caller_kind=person` neither adds taint nor inherits an agent's publication restriction.
- Unknown external MCP remains untrusted/open-world. Only an operator-accepted Geo connector, with its authority included in the acceptance digest, may project Geo's own source provenance. Server self-assertions grant nothing. Owner_created/generated graphs are read; third_party and explicitly unclassified graph results taint publication. Unknown internal source authorship is flagged, not fabricated as owner-created. Sessionless helpers attach source handles to the publication session without receiving its conversation/tools.

Geo's canonical v1.x response bodies remain unchanged: MCP `_meta.access` carries transport provenance. Scoped flat projections retain their graph-qualified source metadata; the native adapter preserves trusted transport metadata without changing the existing content cap. Generated UI bundles are excluded before source reads/indexing, while TypeScript inputs remain selected.

Source content and model output are data, never instructions. Generated material can assist research, but cannot impersonate an original source. Packets, citations and answers carry source provenance. Existing Wave L free-prose warnings catch explicit current-system framing; they are not semantic proof against every paraphrase.

Own/external bridges remain owner-decided `reference` links; no automatic concept equivalence crosses that boundary. Keep the existing W3-5 firewall and all L4/L5 checks.

## Ingestion, originals and stored work

Use the native capture → evidence → facts → describe → stage pipeline, DIK, provenance checks, document identity, sensitivity review and approved-batch continuation. Geo remains a pinned installed wheel. The shared inventory/fingerprint is retained, with evidence/DIK identity added by R; no parallel folder pipeline is the final design.

Conversions belong at `.librarian/conversions/<evidence-id>.md`, content-addressed, outside rebuildable `derived/`. Their page anchors and original paths feed the agent's graph. Third-party native indexing is catalogue-level only; owner_created attachments are indexed fully. Each use/application is recorded and rolled into catalogue/search results. These are S1–S6b/R requirements, not C0 changes.

The owner will provide the `06-Papers` original PDFs later. Do not block internal documents/plans on that delivery. Until an original exists, the paper is `catalogue_only` and cannot claim verified original pages. Keep current summaries distinct from full conversions.

Graphify is retired and the old rule against persistent source graphs is void. Keep the graphify application/modifications in ToolSet; exclude graphify-out and graphify's generated outputs in both surveys. Delete nothing: output cleanup belongs to the owner/lead session.

The library setup's research folder is E:/Librarian research. Do not re-ask settled decisions or bind a lead. Production card drafting, paid enrichment and qualification still require approval with an estimate; preserve the $2 reserve.

## C0 review boundary

See `access-conformance-sweep.md` and the machine-readable `tool-access-declarations.json`. A declaration-coverage pass proves that tools were reviewed, not that the full S4 policy is implemented. The owner answered the S1 closure stop and authorised the T1–T4 fix and continuation through S6 on 2026-11-14. The S1 candidate is implemented with RED-first evidence; full verification is recorded separately before proceeding. Wave L stays unmerged; combined Wave L+B0 merges require separate repository approvals at STOP S6. Never push or tag without instruction.

## S1 implementation amendments

- Resolve authorship and mark closure centrally at `Registry.call` / the result envelope, and at Geo's existing provenance projection. Do not repeat policy across 98 tools; per-tool changes are for refusal/bounding only.
- Class A returns potentially third-party text to models: authorship must conform at S1, full access behavior by S4. Class B is references/labels/metadata: authorship must conform at S1. Class C is person-only/control and n/a. Report n/N per class at each stop.
- Unknown external MCP servers default to untrusted/open-world. Geo uses returned provenance to distinguish owner_created/generated reads from third_party untrusted content; server identity is not an authorship proof.
- Generated UI bundles (`src/resource_librarian/ui/*.js` and analogous build products) are excluded from graphs/indexes as generated hygiene; graph `ui/src/*.ts` instead. The approved live refresh resolved app.js's extraction failure by exclusion, not a parser fix. Its new source settings.ts parse limitation is separately recorded.
