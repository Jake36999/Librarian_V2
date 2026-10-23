# V1 to Librarian capability matrix

This is the product-facing status matrix for the V2 migration.  “Internal
pack” means a first-party module behind the `InternalPack` boundary, not a
third-party plugin marketplace.

| Capability | Status | V2 treatment |
| --- | --- | --- |
| Markdown source catalogue, evidence and concepts | ported | Native vault formats and evidence-first source notes are retained. |
| Search, source intake and local index | ported | The Core-owned `IndexService` is the only SQLite owner; clients call Core APIs. |
| Sessions, staged writing and approval gates | ported | Existing phase and approval semantics remain the control plane. |
| Browser chat and local HTTP API | changed | Served by a per-vault Core with a protocol handshake and dynamic ports. |
| Obsidian two-way Markdown use | changed | Human edits stay direct; Core writes use document leases, debounce, and conflict checkpoints. |
| MCP/Cowork access | changed | Uses the same registry and Core safety rules, with legacy tiers mapped to profiles. |
| Model tiers | changed | Versioned vault-scoped profiles, host records, compact tool bundles, and qualifications replace positional routing as the primary model. |
| Common research walks | changed | Audited `inspect_map_source`, `search_and_judge`, `intake_to_stage`, `evidence_to_claim_check`, and `review_staged_candidate` macros make their expanded plan and stops visible. |
| V1 source continuity | changed | Guided, one-way import previews and stages selected records; it never edits V1 or auto-promotes content. |
| Community/graph advice | internal pack | Deterministic, disposable-index reports use wikilinks and declared topic/concept links; they never rewrite Markdown or ranking. |
| Repository capability extraction | internal pack | A revision-pinned, bounded extract plan/materialization path supports Python and TypeScript/JavaScript without executing code. |
| Ranking learning | internal pack | Offline candidates and a manual Current/Candidate/Compare selector replace percentage traffic canaries. |
| Source-bound workbench | changed | Engagements require catalogued sources and pinned revisions; Docker is the only mode called isolated. |
| Public plugin marketplace / arbitrary executable plugins | deferred | Deferred to V3.  V2 does not ship publisher PKI, a marketplace, third-party UI runtime, or arbitrary plugin execution. |
| Automatic live ranking rollout | retired | A person selects or restores a ranking version. |
| Direct concurrent adapter SQLite access | retired | All adapter reads and writes go through the active Core. |

## How to interpret the matrix

“Ported” preserves the user-visible research capability.  “Changed” retains
the outcome while deliberately replacing an unsafe or impractical mechanism.
“Internal pack” is intentionally narrower than an extension ecosystem: packs
are first-party, versioned against the Core protocol, and registered through
the normal tools and health checks.

