# Geo Grapher Phase 6–7 integration preparation

This guide belongs to the `geo-grapher-wave4` feature branch. It is not a notice of merge or release. The Geo Grapher repository contains the companion guides under `docs/phase67/` and the full gate report under `reports/PHASE67_WAVE4_GATE.md`.

## Runtime behavior at the tool-step limit

The loop keeps its configured ordinary step budget. At exhaustion it may make one final, guarded model invocation with tools disabled, asking for an answer from the evidence already gathered and an explicit account of missing information. Cancellation, time, route-context and profile cost/token guards still apply. It does not execute another tool or silently change the model route.

A nonblank answer carries `completed_at_step_limit: true` in the turn metadata. The `max_steps` stop provenance can coexist with a useful reply: consumers should not discard text merely because that stop reason is present. Read the flag with a false default for older/ordinary turns. It is a completion marker, not proof that citations or requirements are valid; existing checks still apply. A failed or blank synthesis is not marked completed.

## MCP setup and diagnostics

Use the reviewed Geo Grapher wheel through the curated stdio entry, selecting the intended catalog, graph allow-list and one of the six-tool presets. `lead` offers discovery, code search/content/context, cross-graph analysis and packet compilation. Connection scoping remains an access boundary; a label is preferred for calls, while connection configuration should use returned canonical graph IDs.

Flat calls carry plain arguments. Copy `entity_id` and `cite_as` exactly from results. Unknown-ID errors can return real scoped choices and an executable example; recovery does not search another graph. Whole-result caps scale with the declared route window and remain enforced by both sides; oversized JSON is not silently cut into a different answer.

Search/content delivery metadata is bounded to IDs, line ranges, truncation flags and SHA256. Source hashes cover actual returned UTF-8 text; search hashes describe metadata with null source ranges. The benchmark now saves those fields per call rather than full tool text. Code final-answer scores and delivery diagnostics remain separate.

## Helper and Clerk readiness

The Resource-Library research-helper and Clerk routes require their own screened/fresh qualification and a running Core. Lead qualification does not cover them. Use gate §10 for the exact owner-operated commands. If a route times out, retain the failure; do not substitute a model or take over a live/stale library lease on an agent's initiative.

The six-task pilot remains four tier-3 block contracts, one tier-2 synthesis and one tier-1 review on ToolSet, followed by the non-gating production-lead question. Packets are fetched and verified by the Core/runtime; a model's unsupported assertion does not close a requirement. The closed final wave-4 code cycle is not a replacement for that pilot.

## Release boundary

The original dirty Librarian master and its mixed-owner files have not been staged or reverted by this branch's work. Survey integration, wave-4 integration, both full suites, merged-wheel cross-repo checks and every merge/push still need the agreed owner-controlled F1/F2 process. The Geo Grapher 0.2.0 notes and stable-v1.1 freeze are drafts until that process and owner acceptance finish.
