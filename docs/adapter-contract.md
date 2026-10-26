# Browser, Obsidian, and Cowork adapter contract

**Status:** Normative client/Core boundary. Its implementation is partial and
must be read with the [unified implementation plan](unified-implementation-plan.md),
which is the delivery-status authority. Terms follow
[Librarian terminology](terminology.md).

Adapters are clients of the active Core, not alternate vault owners.  Before
mounting UI they call `/api/meta` and compare their supported protocol range to
the Core's `protocol_version` and `compatible_adapter_range`.  Incompatibility
must offer a visible upgrade/downgrade path instead of mounting an uncertain
surface.

The shared UI mount shape is:

```ts
mount(...) -> { insert, dispose }
```

An adapter calls `dispose()` before rerender and on close.  In particular,
Obsidian disposes stale EventSource streams before a view is recreated.

Obsidian first discovers a compatible active Core for its vault.  If it starts
one, it registers through `VaultCoordinator` rather than bypassing the lease.
For the focused dirty Markdown note it sends a heartbeat containing its path,
baseline hash, editor identity, and activity.  The Core debounces filesystem
notifications for one second and expires a document lease ten seconds after
the last heartbeat.  An agent may read such a note, but an operation that
writes it pauses at a write-conflict checkpoint; unrelated notes remain
available.

Cowork/MCP uses the same registry, profile/bundle checks, session gates,
budgets, and Core API.  It must not open vault SQLite files directly or bypass
the writer queue.

