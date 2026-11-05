# Settings controls implementation and handoff · 5 November 2026

The standalone and Obsidian bundles share this implementation. Open Settings in the header from Chat, Staging or Search. The previous SETTINGS-QA.md and browser-observations.json record the pre-fix behavior.

| User task | Delivered behavior |
|---|---|
| Verify who can act in a library | Review & promotion shows the promotion policy, advisory checks, project access and folders permitting edit proposals, and enabled external servers with connection state. Manage links open the underlying controls. A refused promotion, project access or per-folder write change reloads the Core value. A failed reconciliation identifies the last confirmed value. |
| Find a control | Find a setting matches section names, commands and task words including TTS, OCR, Clerk and folder permissions. Service results open the service disclosure. Settings remains reachable from Search and Staging. |
| Keep research edits | Chat preferences and topic proposal forms retain unsaved edits while moving between Settings sections or closing and reopening the panel in the same mount. Discard is explicit. Topic decisions retain their reviewed revision. These temporary drafts last until the app is reloaded or the library changes. |
| Start the right task | Commands & shortcuts exposes 15 destinations and actions. Batch availability reads the active library’s batch status. The due-review count reads due tasks; existing learning sessions may reduce the number created. Workflow commands focus the contextual action, batch commands focus the corresponding Staging control, and the user explicitly starts the operation. Source setup opens the attachment flow. |
| Assign shortcuts | Standalone users select Alt+Shift chords or Unassigned. Conflicts are rejected; repeat events and editor inputs are ignored. Obsidian registers 15 native commands without default shortcuts. In Chat behaviour, choose Enter or Ctrl/Cmd+Enter for sending. |
| Inspect evidence and background work | Staging offers evidence beside the draft or on demand without replacing the open note. The batch banner shows scope and available route information before starting. Observed batch completions can generate a separate in-app notice. On batch start the user can stay in place or open Activity search. Checkpoints and permission requests keep their existing handling. |
| Choose and reuse research settings | Role/service pickers offer a quick list of previously assigned, currently listed models and a detailed comparison view. A service test specifies one call and locks during submission. Named presets on Models & services contain saved chat instructions, length, stance and roles. Preview the destination and differences; apply chat preferences and model roles separately through their normal Core gates. |
| Understand session scope | Chat behaviour has a read-only active-context disclosure for saved instructions and adopted session lenses. Sessions offers newest-created and parked-first sorting using the fields the listing supplies. |

Browser preferences live in local storage scoped to the current origin. Libraries opened at the same browser address share them; a different loopback port, browser profile or Obsidian environment has separate storage. Presets are saved explicitly and may include the user's chat instructions. Permission changes, keys and project access go through their existing controls.

## Verification

The repository UI smoke exercises the existing research flows plus refusal reconciliation, context preservation, TTS search and shortcut conflicts/editor exclusion. The Obsidian adapter contract suite passes its ten checks. Additional isolated Edge checks exercised a one-request double-click, reload persistence, quick model selection and Escape back to Search, applying a saved preset, multiline Enter, the effective-permissions summary and topic draft retention. Commands content fit a 390-pixel browser without horizontal overflow. Real-vault Obsidian hotkey assignment remains a native-host acceptance item.

## Remaining boundaries

Exact passages supplied to a particular turn, active model context capacity, priced job forecasts, enforceable spending limits, tracked image downsampling and high-resolution retries need authoritative runtime data. The current UI reports available scope and selections. Last-active timestamps, an attention classification, persistent custom titles and reversible session archiving require session support. The source setup command covers file attachment and capture; whole-folder discovery, a zero-click whole-library ingest and replaying earlier paid actions remain outside this change.
