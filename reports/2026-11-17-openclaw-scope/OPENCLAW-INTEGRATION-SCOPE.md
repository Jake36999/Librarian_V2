# OpenClaw as a foundation for coding sub-agents: integration scope

2026-11-17, agent Claude. Owner: "open claw was used in the past to act as a foundation for
deploying coding sub-agents. If it's still useful scope the integration, but I wouldn't ingest it
into any libraries."

Evidence tags: **seen** (read on this machine), **docs** (OpenClaw's own installed docs),
**inferred**.

## What is on this machine

- **OpenClaw 2026.5.20, installed globally** (`F:\npm-global\node_modules\openclaw`), with its home at `~\.openclaw`. **seen**
  - Gateway mode `local`; config last touched 2026-07-21.
  - Two agents. `main` uses `lmstudio/qwen/qwen3.5-9b` (24K context). `jarvis-worker` uses `lmstudio/qwen/qwen3-4b-2507` (4K context, 512 output tokens), with a system prompt for "bounded JARVIS development continuity" work in `F:\Mark-XLVIII-main\...\openclaw-worker`. 360 s timeout.
- **The repository in Parallax, `openclaw-ruview-presence-main`, is not OpenClaw.** It is an 11-file OpenClaw plugin that makes agents presence-aware through RuView Wi-Fi sensing: it queues messages while you are away and delivers a digest when you return. A second copy sits at `Automated Deployment & Infrastructure\offline_payload\git\openclaw-ruview-presence`. **seen**
- **Our own research mentions OpenClaw:** `research\immediate_security_control_sprint\implementation_phase_3\03_openclaw_bridge_policy.md` and `wazuh_openclaw_policy_gap.md`. They are our work, so they stay in Parallax's internal research. **seen**

## What OpenClaw offers a sub-agent setup (docs)

- **ACP agents:** OpenClaw can launch Codex, Claude Code or Gemini as an ACP "harness" session (`/acp spawn`, through `acpx`). This is the sub-agent route.
- **`openclaw acp`:** an ACP bridge that an IDE or client can talk to, which forwards into Gateway sessions.
- **`openclaw mcp`:**
  - a registry of outbound MCP servers that its runtimes can use;
  - `mcp serve`, which exposes OpenClaw channel conversations to an MCP client.
- **Skills and plugins:** `SKILL.md` folders and TypeScript plugins, with a heartbeat. The presence plugin is one of these.

## Is it still useful? Three options

| Option | What it gives | Effort | Recommendation |
|---|---|---|---|
| **A. Register the Librarian's MCP server in OpenClaw** (`openclaw mcp set librarian …`) | OpenClaw agents, and the Codex or Claude sessions they spawn, can search and read the libraries through the Librarian's own access rules | Small: a config entry plus a check that the Librarian's MCP server runs under OpenClaw | **Yes, if OpenClaw stays in use.** It reuses what exists and adds no new trust path |
| **B. OpenClaw as a runner for delegation work packages (DELEG)** | The Librarian's delegation controller hands a work package to an OpenClaw ACP session (Codex or Claude Code), then collects its evidence for the completion record | Medium: a runner adapter (package → spawn → diff and checks → receipt), behind the existing package checker and diff-scope guard | **Only if** you want OpenClaw, rather than the current DeepInfra and agent-session routes, to host sub-agents. Scope it as a DELEG runner, not a new authority |
| **C. OpenClaw's local LM Studio agents as coding workers** | Free local work | Small to wire | **No** for coding: 4K and 24K context windows are too small for the work packages DELEG produces. **inferred** from the context sizes |

The presence plugin itself has no role in the Librarian.

## Library boundary (owner)

- **`openclaw-ruview-presence-main` and its `offline_payload` copy:** excluded from Parallax, so no reading, no graph and no index.
  - Both are currently accepted third-party folders, and the Parallax runner already skips the first.
  - Their decisions change to `exclude` in the next Parallax graph build. That build re-extracts all of Parallax's graphs, so it waits for the benchmark.
- **Our research notes about OpenClaw** stay ingested as internal research.

## If you choose A or B

- **A:**
  - Run the Librarian MCP server as OpenClaw would launch it (stdio), against a scratch library.
  - Register it with `openclaw mcp set`.
  - Confirm an OpenClaw agent can search the library but cannot write.
- **B:** a work package for the runner adapter, under the DELEG-11 contract:
  - protected fixtures;
  - a check that drafter and reviewer come from different model families;
  - a completion record the worker does not write.
