# For Codex: what landed after 7a7bcb6 (2026-11-06)

Your status and qualification are from `7a7bcb6`. Since then, `master` has three
commits from Claude. Pull before starting the next UI item, so nothing below is
built twice.

## Your two Core asks are done, front end included (`3b3de57`)

**1. Bulk approve and defer: done, with the UI.**
- **Core.** Approve and defer now check the item's own record inside the write
  boundary, against `staged_revision`. A record that changed since is refused
  (`DOCUMENT_ACTIVE`, with a write-conflict checkpoint) and left untouched.
- **List rows.** Every `staging_list` row carries its own `staged_revision`.
- **UI** (`ui/src/views.ts`, Staging, Sources):
  - a checkbox beside each source wherever approve or defer applies;
  - a bar with "Approve N ticked", a reason box with "Defer N ticked", and "Clear";
  - no approve-all; the owner asked for multi-select only.
- **Behaviour.**
  - Each ticked source is its own call, with its row's revision.
  - Each result is reported: decided, changed since listed (named, left alone), or
    refused with its reason.
  - Everything sent is unticked afterwards.
- **Tests.** `tests/test_staging_triage.py`, and the `ui/smoke.mjs` step
  "several sources decided by ticking".

**2. Durable macro recovery: done, with the chat card.**
- **The handle.** An `outcome_unknown` macro result carries
  `recovery: {checkpoint_id, step, tool, macro, options}`.
- **New tools.**
  - `macro_status(checkpoint_id)` (read) reports `completed`, `paused`,
    `outcome_unknown` (with step and options), `running_or_interrupted` or
    `not_started`.
  - `macro_resolve(checkpoint_id, step, choice)` (person only) resumes with the
    inputs the run's log recorded. If the run has moved on, it answers
    `{"status": "changed"}` and does nothing.
- **Chat card.** `ui/src/chat.ts` `uncertainMacro()` re-checks `macro_status`,
  then calls `macro_resolve`, and locks once answered. The workflow-run card's
  buttons got the ghost style too: they were unreadable.
- **Background chip.** Your remaining item, inspecting a paused step from the
  background activity indicator, can use the same two tools. The chip only needs
  the checkpoint id.
- **Tests.** `tests/test_macro_permissions.py`, and the smoke step "answered by
  its recovery handle".
- **Demo Core.** It now seeds a paused two-note macro: a chat message containing
  "macro" shows the card. It also exits by itself after `LIBRARIAN_DEMO_SECONDS`
  when set.

## Build rules that now apply to you (`40eaf7d`, `9dbf575`; MF-043)

`tests/test_ci_workflows.py` makes these binding:
- **No `${{ }}` inside any workflow `run:` script.** Pass values through `env:`.
- **Actions** are pinned to a commit, with `# vN` beside each.
- **Exact versions:** the runner is `windows-2025`; Python is 3.11.9, 3.12.10 or
  3.13.17; the adapters job uses Node 22.23.4.
- **Python installs** only from `requirements-dev.txt` or `requirements-build.txt`,
  with `--require-hashes`. After adding or changing a dependency in
  `pyproject.toml`, regenerate both:

  ```
  pip-compile --extra dev --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url --output-file requirements-dev.txt pyproject.toml requirements-build.in
  pip-compile --generate-hashes --allow-unsafe --strip-extras --no-emit-index-url --constraint requirements-dev.txt --output-file requirements-build.txt requirements-build.in
  ```
- **npm** is unchanged: `npm ci` from the lockfiles.

## What remains on the Core side for your list

None of MF-027's three Core dependencies remains open; see the update below. The
before/after preview display in Staging is yours.

## Update: MF-027's Core side has landed (same day)

- **Exact staging preview** (`staging_show` → `preview`):
  - Fields: `kind`, `path`, `current_markdown`, `composed_markdown`, `sections`,
    `source_revision`, `staged_revision`, `dependency_digest`, `preview_digest`,
    `set_on_accept`, `status` and `authorizes: false`.
  - Show before and after from these two strings, not an approximation.
  - After an edit to Bottom Line, what it solves or fields, call
    `staging_preview(item_id, bottom_line, what_it_solves, fields)` for the new
    composition and a fresh `staged_revision`.
  - For any `status` other than `exact` (`needs_person`, `conflict`,
    `needs_input`, `semantic`), show `detail` and do not offer Accept from the
    preview.
- **Reply review binding:**
  - The final `text` event and `turn_done` carry `reply_id` and `turn_id`.
  - `reply_reviewed` carries the same `reply_id` and `carried_to_next_prompt`, plus
    `late`, `ambiguous` and `partly_checked` when they apply.
  - Already wired in `ui/src/chat.ts`. The verdict is also kept in the session log
    as a `reply_reviewed` event, ready for a replay view.
- **Claim Run preflight.** `GET /api/claims/preflight` (`?fresh=1` to re-ask
  Docker) returns `{available, detail, checked_at}`. Already wired into the chat's
  Run button.
