# Handoff to ChatGPT: Librarian V2 unified plan, continuing from CORE-05

**Date:** 2026-10-24.
**From:** Claude (Opus 5.5).
**For:** ChatGPT, resuming the work.
**Branch:** `v2-unified-plan`. It has not been pushed, and nothing on it is merged to `master`.

The owner will review your completed work later. Leave it in a state that
review can check task by task. §8 of this document explains how.

---

## 1. The source of truth

- **The plan:** [`docs/unified-implementation-plan.md`](../docs/unified-implementation-plan.md).
  - §18 is the start order.
  - §19 is the progress log, with one row per task, its commit and its evidence.
  - Read §19 first. It also holds the CORE-05 write inventory, the owner's
    confirmed behaviour changes, and open follow-ups.
- **Earlier reports**, all in `reports/` and dated 2026-10-24: the harness and
  adapter review, your transcript review, the blind-spot verification, and the
  baseline manifest.

## 2. What is done since your last session

Every commit below is on `v2-unified-plan`. The full suite passes under the
repository venv: **959 passed, 2 skipped, 1 deselected**, in about 4 minutes.

| Commit | Task |
| --- | --- |
| `ad02715`, `f213fc6`, `1fd49c3` | BASE-01: the baseline, in groups |
| `a467710` | BASE-02: source-identity preflight |
| `77315cc` | ROUTE-01: Lead selection patches only the Lead slot |
| `f014b2f` | CORE-01: Windows-safe process identity |
| `1a8adf6`, `4cfc6eb` | CORE-02A: shutdown phases |
| `4873894` | CORE-03: session events go through the Core writer |
| `7a48f0c` | ROUTE-02: tri-state tool support and alias display |
| `3015bc2` | CORE-02B: interrupted threads are parked and resumable |
| `557126c` | INDEX-01: SQLite-ownership AST guard |
| `8ccce9b` | INDEX-02 batch 1: **partial**, 39 call sites still to migrate |
| `d177d55` | CORE-04A: MCP reaches the vault only through its running Core |
| `8a34cc7` | Fixes for the four P1 findings in your review of this branch (below) |
| `119ded6` | CORE-05A/B: revision tokens and write preconditions |
| `020e3ad` | Plan progress log |

### Your review's four P1 findings

All four were reproduced in the code before they were fixed, in `8a34cc7`.

1. **Session writes bypassed the Core.** Without an attached writer, a
   session write is now direct only offline: when this process holds the
   vault lease, or no live Core holds it. It is refused with `CORE_REQUIRED`
   in two cases: after a Core in this process has stopped (a sentinel), or
   while another process's live lease row exists.
2. **Writer linearity.** `serve_until` is gone, and nothing waits for a
   person inside a writer operation.
   - `_ask` registers its waiter, then records the question.
   - On the writer thread it returns a `PERSON_WAIT` marker.
   - `Registry.call` finishes the wait after `writer.submit` returns.
   - An ask nested in a macro abandons the wait, so its question stays open.
3. **Late work during shutdown.**
   - `person_call` and `mcp_call` are admitted and counted under the
     admission lock (`App._counted_call`). `close_runtime` drains them within
     its grace period.
   - `Waiters.release_all()` and `Broker.close()` are terminal: later answers
     wake nothing, and later permission checks expire at once.
   - An answer delivered just before the stop is kept.
4. **PID reuse.** `process_start` is an exact opaque string: `win:<FILETIME>`,
   or `linux:<boot_id>:<ticks>`. Every liveness check compares it for
   equality, including the Host start path that used to check the PID alone.

### CORE-05

- New module: `src/resource_librarian/revisions.py`.
- **Write intents.** A tool may declare
  `intent=` (`WriteIntent(targets, replaces, note, absent)`). The registry
  resolves it and canonicalises its paths before the broker asks.
- **Revision tokens** are opaque, HMAC-signed, and kept per process. Each is
  bound to the vault, the canonical path, the session, the caller kind and the
  fingerprint.
  - `get_note` issues one for the exact bytes it read.
  - Every write returns the next one, minted inside the writer operation.
- **Who must bring one.** An agent or MCP client replacing an existing note
  must pass `revision`, or the call is refused with `REVISION_REQUIRED`. A
  token issued for anything else is refused with `REVISION_REFUSED`. A
  person's own action needs no token.
- **Coverage:**
  - Checked by compare-and-swap: `edit_note`, `write_note(mode="replace")`
    and `update_project`. A stale revision raises `PreconditionChangedError`,
    which becomes a `write_conflict` checkpoint.
  - Targets declared, no token: `archive_note` and `promote_offering`.
  - **Not covered:** `staging_decide` (see §4).

## 3. Invariants you must keep

These are the guarantees the work above bought. Breaking one silently undoes it.

- **One owner.** One Core per vault holds the lease, the `VaultWriter`, the
  `IndexService` and the document leases. MCP holds no vault state; it
  forwards each call to `POST /api/mcp/call` (`caller_kind="mcp"`, tier capped
  at `contribute`, broker kept).
- **No waiting inside the writer.** Never block for a person inside a writer
  operation. `Waiters.wait` raises if you try. Use the `PERSON_WAIT` path.
- **Synchronous calls are counted.** Any new synchronous entry point into the
  Core is admitted through `App._counted_call`, so that a stop drains it.
- **Session log writes** go through `SessionStore._through_core`. Never write
  a session log directly.
- **Liveness** uses `process_identity.is_alive(pid, record["process_start"])`,
  never `os.kill(pid, 0)`, and never the PID alone.
- **New write tools.** A tool that replaces an existing note declares an
  `intent` with `replaces=`. A tool that creates a note declares
  `absent=(path,)`.
- **SQLite.** Never write `with_engine(ctx, lambda e: e)`, which takes the
  engine out of the index worker. INDEX-03 needs an engine proxy first.

## 4. What to do next, in order

1. **BASE-05:** the task-level regression manifest. ADAPT-01 depends on it,
   and it isn't done. BASE-03 and BASE-04 are also still open.
2. **ADAPT-01:** reply metadata, usage, reasoning continuation, and a typed
   output-budget failure, for empty content with `finish_reason=length`.
3. **CORE-06:** reconcile interrupted operations from the writer's operation
   log, with an idempotent recovery checkpoint. **CORE-07:** epoch-aware
   resynchronisation of the event stream (`resync_required`).
4. **INDEX-03:** first the engine proxy, then the next batch of call sites.
   Before expanding batch 1, add real-Core context tests for its migrations.
5. **ROUTE-03 → ROUTE-05:** canonical role and route bindings. This includes
   server-side canonical aliases, which ROUTE-02 only fixed in the tile.

**Open follow-ups, recorded in §19:**

- **CORE-05 for `staging_decide`.** Resolve its targets per item kind. The
  `topic` kind rewrites `About/Topics.md`, so it needs a revision check.
- **Macro steps in Ask mode.** A macro step's permission check still waits
  inside the macro's writer operation. Let the approved macro checkpoint stand
  in for its steps' permissions.
- **G1 stays open** until CORE-06 and INDEX-04 land with passing acceptance
  tests.

**Owner decisions needed. Do not adopt these on your own:**

- An `approval_pending` result with a resume token for Ask-mode MCP writes.
  Today an MCP write in Ask mode waits for a person in the Librarian window.
- Either CORE-04C (a sampling callback) or a visible "MCP sampling
  unavailable" state in the plugin.
- A one-click "open or start Librarian for this vault" recovery path for
  `CORE_REQUIRED`.

The owner has confirmed that the current MCP behaviour is acceptable as it is.

## 5. How to work in this repository

- **Tests:** run `.venv/Scripts/python.exe -m pytest -q`.
  - `tests/conftest.py` exits if `resource_librarian` is imported from
    anywhere but this checkout's `src`.
  - Run the full suite in the background; it takes about 4 minutes.
- **Line endings.** The repository stores LF (`eol=lf`). On Windows, Python's
  `write_text` writes CRLF, so edit files as bytes, or normalise them before
  you commit.
- **Commits** have a sentence-style subject, one task per commit where the
  code allows, and a body that names the reviewer and what the review found.
- **Hunk splitting.** Avoid splitting hunks across commits. It once produced
  an inconsistent `host.py`. If you must split, verify the commit in a
  temporary `git worktree`.
- **Do not push**, and do not merge to `master`. Do not stop processes you did
  not start; the owner runs other Python services.
- **Windows facts that bit us:**
  - `.venv\Scripts\python.exe` is a redirector, so a `Popen` PID is not the
    interpreter's PID. Spawn `sys._base_executable` when a test needs the real
    child.
  - A script run outside pytest can load the owner's saved API keys and call
    live services. Keep such checks inside pytest.

## 6. Delegation, optional

The owner allowed cheap DeepInfra models as drafters and reviewers.

- **Budget:** $8, of which about $0.25 has been spent.
- **Models:** DeepSeek-V4-Pro, GLM-5.3 and Qwen3.5-397B-A17B.
- The API key lives in `D:\Resource-Library\.utility\.env`. Never print it.
- **What worked:** send a diff with targeted questions, then verify every
  finding in the code before acting on it.
- **Track record:**
  - About half the findings were real.
  - Long reviews hit the output-token limit; ask for a capped length.
  - GLM truncated a code draft.
  - DeepSeek's INDEX-02 draft took the engine out of the index worker.

## 7. Pitfalls already found and fixed

Don't reintroduce these.

- An App that created an MCP manager never stopped it, so pytest hung at exit.
  Fixed by an ownership-based stop in `close_runtime`.
- `LibrarianServer` turned a `Path` into its drive root via
  `getattr(vault, "root", vault)`.
- A question asked inside a writer operation deadlocked against its own
  answer. That came from a pre-existing bug on master, and it led to the
  `PERSON_WAIT` design.
- `git stash` with an untracked pathspec lost staged hunks.

## 8. What the owner's review will look for

For each task you complete:

1. A row in §19, with the commit, the status (implemented, partial, planned,
   blocked externally, or retired) and the evidence.
2. Tests that prove the task's "done when" column, named in the commit or
   the row.
3. A full-suite count under the repository venv, recorded after the task.
4. Behaviour changes listed separately for the owner to confirm, as §19 does
   for CORE-04A and CORE-05.
5. For delegated work: which model drafted or reviewed it, which findings
   were fixed, and which were rejected and why.
