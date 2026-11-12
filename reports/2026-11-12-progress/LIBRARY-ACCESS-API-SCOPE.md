# Scope: one local service any agent session can reach the user's libraries through

**Asked by the owner (2026-11-12):**
- Let any Claude or ChatGPT/Codex session use the user's libraries, from any
  folder, without the person launching the app.
- Fix reopening a library whose earlier session is still alive.

Everything here is a proposal: no code has changed. It builds on what exists:
- the per-user Host (`host.py`);
- the Core's private connection record (`connection.py`);
- the MCP thin client (`mcp_server.py`);
- the library registry (`libraries.py`).

It replaces none of them.

## 1. The problems, as they are in the code

1. **A session must name its library before it starts.** The MCP server reads
   one library from `--vault`, `LIBRARIAN_VAULT` or the working directory
   (`mcp_server.py:232`), and keeps it for its whole life. A session started
   elsewhere has none (`CORE_REQUIRED: no vault`). Switching means editing the
   client config and restarting.
2. **A library is usable only while its Core runs,** and only the app, Obsidian
   or `host start` starts one. The MCP server never opens a library itself
   (correctly: one writer per library).
3. **Reopening breaks.** Closing the tab leaves the Core running, by design
   (`host.py`: no tab reference counting). Launching the app again builds a
   second `App`. That fails on the live lease, and `serve` prints `vault_in_use`
   and exits (`app.py:4641`). It never looks for the running Core's connection
   record, which it could simply reopen. `host start` already does this check
   (`host.py:172-187`); the app launch path does not.
4. **A Core that died leaves a stale lease.** Reopening then needs `--takeover`,
   which the window never offers. This is `StaleLeaseError`, distinct from (3),
   where the Core is alive.

## 2. The fix for reopening (small, do first)

**In `app.serve`,** before building an `App`:
- **Core alive:** if `connection.load(vault.root)` names a live process
  (`process_identity.is_alive`) and its URL answers `/api/meta` on loopback,
  open that URL. Print `{"attached": url, "vault": …}` and exit 0. No second Core
  is built.
- **Lease stale:** serve a small takeover page (as the library picker does)
  that says which process held the library and when it started. Its button calls
  the existing takeover path. A person decides; an agent never does.
- **The library picker** gets the same check when a person opens a library from
  it (`library_picker.py`).

**Tests:**
- start a Core, then call `serve` for the same library: it attaches and opens
  the existing URL, and no second lease is attempted;
- a dead recorded PID: the takeover page, not a crash;
- a live PID but an unreachable URL: a refusal that names the running process,
  never a second Core.

**Size:** small (`app.py`, `library_picker.py` and one test file). It closes the
owner's reported defect independently of everything below.

## 3. The service: a library router in the existing Host

**Recommendation.** Extend the per-user **Host** into a small loopback **router**.
Don't build a new daemon. The Host already starts, finds and stops one Core per
library, and refuses to start a second (`host.py:172`).

What the router adds:
- **A stable address and a token for clients.** It listens on loopback, and
  publishes `router.json` (URL, token, PID, process start) in the user's config
  directory, owner-only, like the Core connection records.
- **Library listing and opening.** It lists known libraries from
  `libraries.json`. Opening one starts its Core headless (`CREATE_NO_WINDOW`,
  as the Host does) or reuses it.
- **Forwarding calls.** A tool call goes to the right Core's existing
  `/api/mcp/call`, so every rule, phase gate and permission is enforced where it
  already is.

### REST surface (`/v1`, loopback only, bearer token)

| Method and path | Does | Notes |
|---|---|---|
| `GET /v1/libraries` | lists known libraries: `id`, `name`, `path`, `profile`, `state` (`running`, `stopped`, `stale`, `missing`) | `id` is a stable digest of the canonical path; paths are shown, contents never |
| `POST /v1/libraries/{id}/open` | ensures a Core: reuses a running one, or starts one headless | `stale` is refused with `STALE_LEASE`, which only the person resolves (section 2) |
| `GET /v1/libraries/{id}/status` | the Core's health, active work, its own lease, and its qualified routes | the qualified routes are why helpers may be refused |
| `GET /v1/libraries/{id}/tools` | the tool list at this client's tier | the registry's own specs |
| `POST /v1/libraries/{id}/tools/{name}` | one tool call: `{arguments, session}`, returning the Core's result unchanged | forwarded to `/api/mcp/call` with the client's tier |
| `POST /v1/libraries/{id}/close` | stops a Core **this router started**, only when it has no admitted work | never stops a Core the person opened, and never forces |

There is no endpoint that opens or creates a library at an arbitrary path.
Adding a library stays a person's act in the app, so an agent cannot point the
router at a repository and write `.librarian/` into it, as happened with
Geo-Grapher on 2026-11-11.

### MCP router mode (how Claude Code, Codex and ChatGPT desktop use it)

`resource-librarian mcp --router` starts with **no fixed library**:
- If the router isn't running, it starts it (once).
- It offers `list_libraries`, `use_library(id)` and `library_status`. After
  `use_library`, it serves that library's tools exactly as today, forwarded
  through the router.
- `use_library` can be called again to switch, without restarting the client.

One client entry then works for every library and every folder:

```json
"librarian": {"command": "D:/Librarian_V2/.venv/Scripts/python.exe",
              "args": ["-m", "resource_librarian", "mcp", "--router", "--tier", "contribute"]}
```

The existing `--vault` mode stays unchanged, for pinned set-ups and the Cowork
plugin.

**Why both REST and MCP.** MCP is how Claude Code, Codex and ChatGPT desktop
already call tools, so router mode is what most sessions use. REST serves
scripts, other local tools and clients without MCP. Both go through the same
router code, so they cannot drift.

**ChatGPT on the web is out of scope.** Custom GPT actions need a public HTTPS
endpoint. Exposing a library to the internet is a different, much larger
security decision. This scope stays loopback-only.

### Security

| Rule | Why |
|---|---|
| **Loopback only;** the token is required on every request; Origin is checked | the same posture as the Core |
| **The token is in an owner-only file,** never in a URL, never in logs | as with Core connection records |
| **Tier ceiling:** `consult` by default; `contribute` granted per library by the person in Settings; `curate` never through the router | `curate` is a person's own authority |
| **A per-client library allow-list,** optional | so a Geo-Grapher session sees only the libraries it should |
| **Every call is attributed** (`caller=router:<client>`) in the Core's existing activity and audit trail | provenance |
| **No path-based opening;** no takeover; no force-stop | these are person decisions |
| **Paid model routes keep their existing spend checkpoints;** qualification is never run through the router | the person confirms spend |

### Sessions

The Core already binds a research session to a connection (`open_session` and
the envelope). Through the router:
- A client gets the `session` id from `open_session` and sends it with each
  call.
- The router keeps nothing per session beyond that pass-through. Two agent
  sessions on one library get two Librarian sessions, as two MCP clients do
  today.

### Lifecycle (one owner decision)

The Host deliberately has no idle reaper. Cores started by the router headless
need an answer:
- **(a) Keep running** until the person stops them (Host Quit), as today.
- **(b) Recommended:** stop a router-started Core after N minutes (for example
  30) with no admitted work and no attached window. The Core already counts
  admitted work, which is how shutdown refuses while work is running.

A Core the person opened is never stopped by the router.

## 4. Work packages

| # | Package | Files | Size | Depends on |
|---|---|---|---|---|
| A1 | Reopen the running Core instead of refusing; the stale-lease page | `app.py`, `library_picker.py`, `tests/test_app_reopen.py` | S | — |
| A2 | Router in the Host: `router.json`, the token, library listing, `open`, `status` and `close` | `host.py`, new `router.py`, `libraries.py` (stable ids), `tests/test_router.py` | M | A1 |
| A3 | Tool forwarding with tier ceiling and per-client allow-list; attribution | `router.py`, `app.py` (`/api/mcp/call` accepts the router as caller), Settings for the per-library grant | M | A2 |
| A4 | `mcp --router` mode: `list_libraries`, `use_library`, switching | `mcp_server.py`, `tests/test_mcp_router.py` | M | A3 |
| A5 | Idle stop for router-started Cores, if the owner picks (b) | `host.py`, `router.py` | S | A2 and the decision |
| A6 | Docs and Cowork contract: `docs/agent-guide.md`, `docs/operator-guide.md`, `plugin/skills` | docs | S | A4 |

A1 can ship alone. A2–A4 are the planned packet **MF-030** ("qualify MCP
restart, library switch and handoff boundaries", `mcp_client.py` and
`mcp_server.py`). Do it there, with MF-030's restart and library-switch
acceptance tests, not as a parallel track.

## 5. Acceptance (what "done" means)

- **Any folder, no app open.** A Claude Code session started in an unrelated
  folder with the router entry can list libraries, open one, and run `search`.
  The Core starts headless, and the call is attributed to the router client.
- **One Core per library.** Two sessions open the same library concurrently and
  get one Core, never two.
- **Reopening works.** Closing the browser tab, then launching the app again,
  opens the running Core.
- **A stale lease is never taken over by the router.** It answers
  `STALE_LEASE`; the person's takeover page clears it.
- **The tier ceiling holds.** A `consult` client calling a write tool is refused
  by the Core's existing tier check. `curate` can't be granted through the
  router.
- **No library is created or opened by path through either interface.**
- **The existing `--vault` MCP mode and the Cowork plugin pass their current
  tests unchanged.**
