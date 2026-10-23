# Librarian product contract

Librarian is a Windows-local, single-user research and co-work product.  The
Python distribution and compatibility command remain `resource-librarian`
through the 2.x line; user-facing UI, documentation, shortcuts, and release
artifacts use **Librarian**.

`Librarian_V2` is the only V2 source tree.  Resource Library is V1/R&D
history, not a runtime dependency or a sibling checkout that a deployed Core
expects to find.

## Authority and state

For a vault which may mutate, exactly one Core holds the vault lease.  The Core
owns the writer queue and the SQLite index.  Browser UI, Obsidian, Cowork,
CLI, agents, helpers, packs, and adapters ask that Core to read or write; they
do not open the index or write durable vault state beside it.

Markdown remains human-editable.  An Obsidian dirty-document heartbeat creates
a short, document-scoped lease.  A Core write that targets that note becomes a
visible conflict checkpoint rather than overwriting active human work.  It
does not lock unrelated notes or the whole vault.

Known human decisions are structured checkpoints rather than long policy prose
in a model prompt. A checkpoint is bound to an exact operation scope and may
carry an expiry; an expired approval is never reused. Experimental host/model
selection, evaluation spend, macro expansion, active-document conflicts,
Docker/host execution, and forced engagement close are visible decisions with
their evidence and consequences.

The contract is deliberately conservative:

- no content is promoted without the existing staging/approval path;
- a macro cannot bypass a registry, session, budget, or checkpoint gate;
- an agent can invoke only the task-sized tool bundle sent for that turn; an
  audited macro is the sole traced expansion path;
- a model route never changes silently;
- code never runs merely because an agent proposes it;
- learning can change only retrieval-ranking candidates, never permissions,
  hosts, routing, profiles, or promotion;
- credentials are personal and outside a vault.

## Version and adapter policy

Librarian uses SemVer for the Core package.  The current development line is
`2.1.0.dev0`; releases in the 2.x line retain the legacy tier/Clerk-route
configuration as adapters to versioned agent profiles.

The Core protocol is independently versioned.  `/api/meta` is the adapter
handshake and returns at least:

```text
core_version, protocol_version, ui_build_id,
compatible_adapter_range, enabled_features, non_secret_health
```

An adapter must compare its supported protocol range before mounting.  A
protocol-major incompatibility is a stop-and-upgrade/downgrade condition, not
a best-effort mount.  Browser and Obsidian UI mounts expose `dispose()` and
must call it before rerendering or closing so event streams do not survive the
view that created them.

Supported Python versions are 3.11, 3.12, and 3.13.  Python 3.14 is not part
of the release contract until it has passed the release matrix.

## Release record

Each release carries a `release-manifest.json` with Core/protocol versions,
adapter range, supported Python matrix, artifact digests, build IDs, and lead
qualification state.  Its self-contained bundle includes a hashed Core wheel,
Obsidian ZIP, Cowork ZIP, offline wheelhouse, and adjacent bootstrapper and
verifier scripts.  The checked-in manifest is a development template, not a
signed release assertion.  A stable release must replace its placeholder
artifact hashes and pending lead evidence with artifacts produced by CI.  The
ordered external-input and release-execution work is tracked in the
[remaining implementation and release queue](release-implementation-queue.md).

`src/resource_librarian/standard/release_leads.json` also starts as a
candidate list.  A candidate becomes a bundled verified release lead only
after the release job records exact model, endpoint and contract fingerprints,
L3 evidence, expiry, and a successful L1 probe against the user's own key at
first run.  No provider key or fictional qualification result is shipped.

## Compatibility commitments through 2.x

- Markdown, evidence, staging, project, session, and approval semantics stay
  intact.
- Existing positional tiers and `[clerk] route_*` settings continue to work as
  default profile adapters. A custom legacy endpoint is registered once in the
  non-secret Host Registry before a Screened or Verified Clerk/Scribe profile
  may use it; preset URLs are matched automatically. On first Core startup,
  persisted provider/base-URL tiers are upgraded to seeded or deterministic
  custom Host Registry IDs without changing their model or endpoint.
- Vault-scoped non-secret settings, profiles, migration manifests, ranking
  choices, and engagements remain versioned and auditable.
- `resource-librarian` remains a CLI/package alias while `librarian` is the
  preferred command.

