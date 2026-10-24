# Verification of six suggested architectural blind spots

**Date:** 2026-10-24
**Input:** six points raised by a third reviewer after reading the
[harness and adapter-plan review](2026-10-24-harness-and-adapter-plan-review.md)
and the [ChatGPT transcript review](2026-10-24-chatgpt-transcript-review.md).
**Method:** each claim was checked against the code, by running it, or against
the validation JSON. Measurements use the `o200k_base` tokenizer on a fresh
temporary vault. No product code was changed.

## Summary

| # | Point | Verdict | Severity |
| --- | --- | --- | --- |
| 1 | Cross-process split-brain: MCP and CLI | **MCP confirmed** (a contract violation). The **CLI already proxies** to the active Core. | **P0** for MCP |
| 2 | Out-of-band Obsidian edits and store skew | **Partly.** The watcher, leases, refresh-on-read, and atomic writes already exist. The real gaps are elsewhere (below). | P1 |
| 3 | Closure defined at the level of individual DIK grains | **Confirmed and valuable.** The verifiers already exist. The "80%" figure is unsupported. | Design, high value |
| 4 | Synchronous walks vs background jobs | **Mostly already done.** Three narrower gaps remain. | P1 (shutdown gap) |
| 5 | Prompt bloat from schemas and tool outputs | **Partly.** Schemas are about 1,240 tokens, not about 2,000. Tool results have been bounded since M0. | P2 |
| 6 | Local compute contention | **Partly.** STT and TTS are cloud-only. OCR and local embeddings bypass the host limiter. | P2 |

## 1. Cross-process split-brain

**MCP: confirmed.**

- `mcp_server.serve` opens `Vault.find(...)` in the stdio process
  (`mcp_server.py:217-231`). It builds `Context` with no `index_service`, no
  `vault_writer`, no document leases, and no vault lease.
- With no writer, `Registry.call` falls through to a direct `invoke()`
  (`registry.py:360-366`). Tools then open SQLite through
  `engine_for(ctx)` → `Index(...)`.
- The Cowork and Claude Code plugin launches exactly this process
  (`plugin/.mcp.json`: `resource-librarian mcp --tier contribute`).
- That breaks the contract twice:
  - [`adapter-contract.md`](../docs/adapter-contract.md): "Cowork/MCP … must
    not open vault SQLite files directly or bypass the writer queue."
  - [`product-contract.md`](../docs/product-contract.md) §Authority: one Core
    holds the vault lease.

It is worse than the reviewer stated. The MCP process also bypasses
`DocumentLeases`, so an MCP write can overwrite a note a person is typing in
Obsidian with no write-conflict checkpoint. The Core's watcher and the
Obsidian heartbeat protect only writes made by the Core.

**CLI: already handled.** `cli._call_active_core` (`cli.py:39-91`) reads the
protected per-user connection record and posts to the Core's
`/api/tool/<name>` with a loopback check and the token. It also refuses to
fall back to a direct write when a recorded Core cannot be reached. Its
liveness test is the same `os.kill(pid, 0)` defect, so fixing that helper
benefits this path too.

*Recommendation (P0, alongside the Host-stop fix).* The MCP server should do
exactly one of these:

- proxy every tool call through the active Core, reusing
  `_call_active_core`; or
- when no Core is live, start as a coordinated Core, holding the vault lease
  with the writer and IndexService.

It should never do neither. A session opened over MCP then becomes an
ordinary Core session.

## 2. Out-of-band edits and store skew

**Already present** (the reviewer missed these):

- **A filesystem watcher.** `VaultWatcher` (`coordination.py:402-460`) polls
  `(mtime_ns, size)` of all visible Markdown every 0.35 s, and treats
  deletions as edits. It feeds `DocumentLeases.observe_change`, which ignores
  the Core's own atomic replacements and blocks Core writes to a note during
  its quiet window.
- **The Obsidian heartbeat** marks the note being edited
  (`obsidian/src/main.ts:44`; adapter contract).
- **The index is derived and self-healing.** `Index.refresh()` compares
  `(mtime, size)` on every routed read (`index.py:395-420`). A crash between a
  file write and an index commit is therefore corrected on the next read.
  Embeddings are keyed by chunk hash and recomputed when missing.
- **Writes are atomic** (`os.replace` + `fsync`, `coordination.py:255-277`).
  The writer appends an operation record *before* mutating and a second record
  after (`coordination.py:536-603`). That is already the write-ahead intent log
  the reviewer proposes.

**Real gaps:**

1. **The compare-and-swap precondition is never used.**
   `VaultWriter.submit(..., preconditions=...)` enforces a CAS
   (`coordination.py:582-594`), but no caller in `src/` passes one. Once a
   note's quiet window lapses, or when it was edited without the plugin, an
   agent's read-modify-write silently overwrites the person's change.
   *Fix:* carry the fingerprint recorded at read time (`get_note`,
   `read_source_file`) into the write tools (`edit_note`, `write_note`,
   `update_project`) as a precondition.
2. **Interrupted operations are never reconciled.** An operation with a start
   record and no finish record is diagnosable, but nothing checks for it at
   startup. That matters for multi-target operations such as promotion's
   six steps, which can be left half-applied. *Fix:* a startup scan that
   surfaces those operations as a checkpoint.
3. **Sessions never learn of external edits.** Nothing appends an event to the
   session log when a note the session read changes. This is the input that
   the harness's `state_epoch` invalidation needs.
4. **The watcher will not scale (new).** `rglob("*.md")` over the whole vault
   every 0.35 s is fine for a Librarian vault. It will be costly on a large
   adopted docs tree such as `F:\quantule_mapper\docs`. Scope it to approved
   document roots and back off on large trees, as part of the adoption work.

## 3. Closure at the DIK-grain level

**Confirmed, and it improves on companion §4.2.6.** These deterministic
verifiers already exist for individual pieces of research evidence:

| Grain | Verifier in the codebase | What it can establish |
| --- | --- | --- |
| Captured source | `EvidenceStore.verify()` (content addressing); `quality.py` per-kind verdicts | The record is intact; capture is `usable`, `partial`, or `needs_ocr` |
| Coverage | `dik.py` origin and status, with "not examined" explicit | What was and was not read |
| Quote | `clerk.quoted()` / `locate()` (`clerk.py:950-963`): normalised span match of at least 8 characters, with its offset into the original | The quoted text occurs in the cited chunk |
| Note sentences | `facts.grounded()`: lexical overlap of distinctive words | Catches invented names. By its own docstring it "cannot catch a wrong claim built from right words" |
| Arithmetic | `provenance.py` | Stated counts match the survey evidence |
| Executable claim | `claim_run.py` | The failing input reproduces |
| Promotion | `promote.py` step 5 findability | The note is retrievable by title, bottom line, and concept |

*Recommendation for the spec.* Define closure per grain, with the predicate
worded exactly: "the quote is present in evidence `<id>` at offset N", not "the
claim is true". Intake, coverage, quote, arithmetic, executable-claim, and
findability grains can be `authoritative` with Tier A only. Synthesis and
interpretation stay `human_judgment`, through staging and promotion. Drop the
"80%" figure; measure the share on real sessions instead.

## 4. Walk execution model

**Already done** (the reviewer missed these):

- `POST /api/chat` starts the turn on a background thread and returns at once
  (`app.py:1798-1835`).
- Events are sequence-stamped in `EventHub` and streamed over SSE with
  `id:` lines and `?since=` replay (`app.py:97-130`, `2971`, `3305-3340`).
- The browser client reconnects from the last sequence number it saw
  (`ui/src/api.ts:54-80`).
- `/api/chat/cancel` sets a cooperative cancel event that `Loop.send` checks
  before each step and each tool call (`loop.py:815`, `855`, `870`).
- Obsidian disposes mounted views (`obsidian/src/main.ts:201`, `257`).

**Real gaps:**

1. **Core shutdown does not cancel the active turn.** `close_runtime`
   (`app.py:384-400`) stops the watcher and flushes the writer, but never sets
   `_turn_cancel`. The daemon turn thread dies with the process: no
   `stopped: cancelled` event, no checkpoint. This belongs with the Host-stop
   P0.
2. **Cancellation cannot interrupt a provider call.** Checks happen only
   between steps. A blocking provider request can hold a turn for up to the
   host timeout (default 120 s). The reviewer's "<500 ms" stop needs an
   abortable transport (streaming, or a short socket timeout with retry), not
   only more check points.
3. **Replay is limited to memory.** `EventHub(keep=500)` holds the last 500
   events and loses them on restart. The durable session JSONL is not used for
   replay, so a reconnect after a long walk or a Core restart misses events.

## 5. Where prompt tokens go

The telemetry figures are accurate: 106 tokens for the 1-tool L1 probe, 2,738
on the first 10-tool walk step, 2,865 → 6,202 over 11 steps on 10-22. The
attribution is not.

**Measured first App-style turn** (bundles on, as the App sets them in
`app.py:1720`):

| Component | Tokens |
| --- | ---: |
| System prompt | 1,358 |
| Tool schemas (10 tools) | 1,241 |
| — of which descriptions | 402 |
| User message | 19 |

So the jump is about half system prompt and half schemas, not "~1,800–2,200
tokens of schemas".

**Tool results have been bounded since M0.** `loop.py:115-122` and `216-240`:

- The current result is capped at 16,000 characters.
- The last 6 results go whole.
- Older results are cut to 700 characters, and long arguments to 300.

The comment there records why: prompts had averaged 42,000 tokens. A large
read is therefore re-sent for at most 5 more steps, capped at about 4k tokens,
not "re-billed on steps 4–10". Observed growth is about 300–550 tokens per
step.

**Still worth doing:**

- About 2,600 fixed tokens per turn makes a cache-stable prompt order
  worthwhile (companion §5.3).
- The worst-case recent window is 6 × 16,000 characters, about 24k tokens.
  Returning an evidence handle for oversized `read_source_file` and `get_note`
  results, as the reviewer suggests, is a reasonable refinement.
- **Guard the default.** A `Loop` built without `use_tool_bundles` offers all
  130 tools: 16,921 schema tokens. No product path reaches that today; the App
  sets bundles and the helper sets `only = HELPER_TOOLS`. But it is an unsafe
  default for any new caller. Make bundles the default.

## 6. Local compute contention

- **STT and TTS have no local path.** Both are DeepInfra-only (`stt.py:50`,
  `tts.py:37-48`).
- **Local chat is limited per host** by `HostLimiter`, default concurrency 1
  (`hosts.py:383-411`).
- **OCR and embeddings bypass that limiter.** OCR (`ocr.py:59-61`) and
  `api:local` embeddings (`embed.py:101-137`) use their own `urllib`
  transports. A local OpenAI-compatible server can therefore receive chat,
  embedding, and vision requests at the same time, which can mean model swaps
  and VRAM pressure. `model2vec` and `fastembed` run in-process on the CPU.

*Recommendation.* Do not add a new semaphore abstraction. Route the service
transports through the same per-host limiter as part of consolidating
transports (companion defect 6), and let a host be marked `local` so a
background `embed.sync()` yields to an interactive turn. This is low priority
unless local-first deployment is a release target.

## Amendments to the merged order of work (companion §7)

1. **Release blockers:**
   - Also make MCP proxy-or-lease (point 1).
   - Also cancel the active turn and checkpoint it in `close_runtime`
     (point 4.1).
2. **Adapter steps 1–3:**
   - Also wire read fingerprints into writer preconditions (point 2.1).
   - Also send service transports through `HostLimiter` (point 6).
3. **Adoption:**
   - Also scope the watcher to document roots (point 2.4).
   - Also add a startup scan for interrupted operations (point 2.2).
4. **Prompt work (adapter steps 5–7):**
   - Make tool bundles the `Loop` default.
   - Add evidence handles for oversized results (point 5).
5. **Harness as a session purpose:**
   - Define closure per DIK grain (point 3).
   - Record external edits as session events (point 2.3).
   - Add durable replay from the session log, and an abortable provider
     transport (points 4.2–4.3).
