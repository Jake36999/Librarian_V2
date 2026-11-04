# Librarian Settings: layout and navigation plan

4 November 2026. Initial visual assessment of the supplied Settings screenshots, cross-checked against `D:/Librarian_V2/ui/src/settings.ts` and relevant persistence code. Design proposal only; no application changes. [Illustrative layout](settings-layout-concept.png).

## What the screenshots reveal

The current five-tab dialog is about 680px wide, but Connections contains credentials, billing, service assignments, embedding evaluation, release leads, agent profiles and editable host definitions. Library combines promotion/review policy, technical health, domain configuration, taxonomy, lens packs and model catalogues. These headings no longer predict a short, coherent page. More width helps, but grouping is the main intervention.

The screenshot sequence exposes several specific problems:

- Provider credentials and a one-time key migration warning occupy the beginning of Connections, while the model/service settings needed for daily work extend well below the initial viewport.
- Each provider is expanded into a long form. Operational controls (choose a model), configuration (URL/concurrency), diagnosis (test/probe) and authority (use as lead) appear together.
- Fourteen Semantic Scholar tool permission rows repeat a long server prefix and three buttons. Server installation and per-library permission are adjacent but have different scope.
- Library includes a session-record integrity warning among package/version checks and topic/lens content. The warning should remain visible, but its explanation belongs in diagnostics rather than interrupting unrelated configuration.
- Working context is comparatively coherent, but “System prompt” overstates a field that shapes chat replies rather than all agent/source-writing behavior. Custom length is shown next to Long/Short even when its role is unclear.
- Projects explains several filesystem effects in one paragraph. The enable switch, folder access and per-folder write approval need separate visual levels.
- Many items are actions or reports, not settings: Propose topics, Rewrite indexes, measure retrieval, migrate keys, test a connection, and inspect record integrity. They should be visibly distinguished from editable preferences.

## Proposed shell

Move the entry point from the composer '+' to a persistent Settings icon and label in the app header, reachable from Chat, Review/Staging and Search. Preserve existing entry points as aliases during transition if necessary; no new navigation/state library.

On a spacious desktop, use a dialog up to **1120px wide and 820px high**, bounded by the actual mounted app region and viewport with 24px exterior clearance. These are design starting values, not research-derived thresholds. Use a **224px left navigation rail** and a flexible content area with 28–32px padding. Limit text-heavy forms to roughly 760px of readable content width rather than stretching every field across a large monitor.

Header: Settings, current library name/path disclosure, Close. The navigation rail is stable; main content has one vertical scroller. A long sidebar may scroll independently if essential, but do not create separate scroll boxes inside every card. The page title, one-sentence purpose and scope appear at the top of each page. Forms with pending edits get a page-local sticky Save/Cancel footer, not a misleading global Save button.

For a narrow mounted leaf, collapse the rail into an accessible labelled category selector or drawer. Below approximately 840px of available root width, avoid maintaining 224px navigation beside an unreadable form. At phone widths, use the available root as the Settings surface with a clear Back/Close action. Measure the mounted root, not only the window: an Obsidian main split can be narrow inside a wide desktop window.

## Navigation and grouping

Use the three section headings below. A category can contain settings of more than one scope, but scope must be labelled on its actual controls. Do not create a global/library switch that the backend cannot honor.

| Sidebar group / page | Contents and purpose | Existing source / operation |
|---|---|---|
| Environment / Providers & keys | Saved providers/hosts, credentials, connection setup, usage link/check. Expand only the selected provider. Advanced host URL, credential reference, timeouts and concurrency behind Edit connection. | settings.ts connections/hostRegistry/hostCard; `/api/keys`, `/api/hosts`, `/api/usage` |
| Environment / Tools & integrations | Installed server summaries, explicit enable-for-this-library control, add/browse integration flow. Tool permissions disclosed per server. | mcp/mcpBody; `/api/mcp`, registry, server, library, enable, remove and `/api/tool-setting` |
| Current library / Models & services | Explicit Lead, Notes and Small tasks roles; separate OCR, read-aloud, speech recognition and embedding service cards. Model catalogues in a secondary disclosure. | existing tier/service selection, serviceModels, embeddingsBlock, paintModelCatalogs; `/api/state`, `/api/tiers`, `/api/services` |
| Current library / Chat behaviour | Working context, answer/coach preference and response length. Plain explanation that these shape chat, not neutral source descriptions. | context; `/api/context` |
| Current library / Review & promotion | Who may promote, advisory reply/offerings checks, read-only distribution posture and a link to the reviewer model role. | library policy controls; `/api/library` |
| Current library / Project access | Master access switch, connected folders, read/edit permission per folder, add-folder workflow and explanation of files created. | projectsPage; `/api/projects` and current mutations |
| Current library / Methods & lenses | Domain profile summary, lens-pack catalogue, pack inspection/acceptance and explanation that pack acceptance differs from adopting a lens into a thread. | paintProfile/paintPacks; library_profile, lens_packs, lens_pack_accept |
| Current library / Topics & organisation | Current topics, unfiled count, pending proposals, refile choices; explicit links back to Review. Maintenance commands separated from configuration. | paintTopics; topics_list, topic_propose, staging_decide, views_refresh |
| Advanced / Agent profiles | Selected profile, permission ceiling, bundle/route restrictions, editor and version history. Keep authority constraints explicit. | agentProfiles; `/api/profiles`, `/api/agent-profile`, history |
| Advanced / Health & diagnostics | Installation capabilities, record integrity, route readiness and qualification details. Non-secret support information and one-time migration actions. | `/api/library.doctor`, `/api/meta`, route readiness and qualification APIs |

Do not introduce empty pages for nonexistent appearance, notification or backup preferences. Add Settings search only over controls/categories that actually exist; it is a local navigation index, not a second configuration store.

## Scope must be truthful

The screenshots say that some tools are installed for the user but enabled per library. Keep these distinctions explicit:

- **This computer/account:** provider host definitions and key storage. HostRegistry uses the user config directory; keys are not stored in library notes. Obsidian-managed keys must still route users to Obsidian SecretStorage controls.
- **This library:** service assignments, working context, review/promotion policy, project roots, lens-pack acceptance and agent-profile definitions. ProfileStore lives under the vault's `.librarian/agents/profiles.json`.
- **Shared defaults side effect:** app Settings.SHARED includes tiers, lead_overrides and effort (`app.py:206–265`). Changes are saved to the current library and copied into defaults used by libraries without their own choices. Say this visibly on the affected controls; do not claim every existing library changes immediately. Exact inheritance badges need an exposed payload; do not infer them merely from identical values.
- **This thread:** adopting a lens is distinct from accepting a pack into the library. Keep adoption in the session surface, with an explanatory link here.

For integrations, show both “Installed for this user” and “Enabled in Timeline-mapping”. Replace ambiguous “Disable here” with the full library scope. Put Pause in all libraries and Remove installation inside an explicit installation menu with impact confirmation. Existing tool-policy semantics remain unchanged; this layout must not silently turn Ask into Allow.

## Individual page specifications

### Providers & keys

Show provider summaries with name, endpoint identity, credential saved/not saved and the last reported connection result as distinct states. A green dot should not imply the model is qualified. Select a provider to edit details rather than expanding every host at once.

Keep Save connection and Save key separate because their persistence/security differ. Show missing-key migration as an actionable notice with its affected scope. Move raw IDs/protocol names/credential references and rate/concurrency limits behind Advanced connection settings. Retain exact values for experienced users.

Label Test connection and Check model capability separately. An L1 probe can make a real paid request; do not run it on page load or hide its confirmation. Qualification and release-template diagnostics belong in an expanded technical section, not between ordinary service choices.

### Models & services

Use a role grid: Role | Current model/provider | Reported readiness | Change. Replace visible slots 1–7 with names, retaining the existing backend slot identifiers. Explain shared-default effects here. Changing Notes must not clear Lead as an incidental UI operation; preserve server qualification/fallback rules.

Service cards show job name, selected provider/model, last reported result and Choose/Test actions. Expand details only for the selected service. Put semantic-search retrieval evaluation inside Embeddings → Retrieval quality, distinct from vector coverage: “984 chunks embedded” and “vectors improve answers” are different facts. “Measured on 0 questions” means no usable evaluation sample; it should not imply validated benefit.

### Tools & integrations

Initial view: server name, human description, connection state, library enable state and number of tools. Expanding Semantic Scholar reveals tool permissions. Show short labels such as Search papers; preserve exact technical identifier in details. If no trustworthy display name exists, format the identifier rather than inventing capabilities.

Use aligned tool-name and Allow/Ask/Deny columns, a local tool filter and a collapsed advanced add-server form. Keep current effective policies visible; do not assume all tools use Ask. Do not add a broad “Allow all” shortcut merely to reduce visual density.

### Chat behaviour, review and project access

Rename the working-context field “Context for chat replies”; provide a short explanation of what it does not affect. Length choices are Short, Long or Custom; show custom input only when selected. Label Answer/Coach as response style and retain the learn-session override explanation.

Review & promotion separates authority (who can publish) from advisory checking (whether claims are reviewed). Neither switch guarantees factual truth. Show a direct Configure reviewer model link to Small tasks on Models & services.

Project access uses a short top explanation, then folder cards with separate read/write state. Adding a folder explains creation of librarian-app metadata before submission. Keep “edits require approval” visible next to write permission; place the full file/log/backup explanation in details. Never simplify by weakening current defaults.

## Visual and interaction rules

- Retain the parchment/brown identity. Make the sidebar a slightly stronger warm-neutral surface, with a clear selected background and accent marker; keep form fields white.
- Use 16px body copy where space permits, 20–24px page headings and 14px secondary descriptions as starting sizes. Avoid rendering essential explanations as tiny low-contrast footnotes.
- Use short purpose text followed by labelled sections. Advanced technical records are collapsed; actionable failures stay visible and linked to their page.
- Show icons with words for navigation. Avoid dot-only status: Connected, Not tested and Needs attention need distinct text.
- Separate preferences from actions. Save writes configuration; Test, Measure, Propose topics and Rewrite indexes initiate work and require their own result/pending feedback.
- No global Save all. Preserve explicit-save forms, immediate toggles and command buttons, but label each pattern. Immediate changes show Saving/Saved/failure and restore confirmed state after rejection. Warn before abandoning dirty forms; never silently save a different category.
- Keep current category, scroll and unsaved edits while moving between Settings pages. Save/Discard/Stay handles closing with edits. Library switching must never submit an old form into the new library.
- Use native dialog modal behavior and scoped `dialog.lib-dialog` CSS under the Librarian root. Sidebar category navigation uses appropriate links/buttons and current-page semantics; keyboard focus returns to the opening Settings button on close.

## Delivery plan

1. **Build the larger shell and left navigation.** Move the entry point into the persistent header; add root-aware sizing, active category, native dialog focus, and lazy page rendering. Preserve all existing endpoints.
2. **Split the overloaded pages.** Extract the current rendering methods into the categories above. Preserve forms/requests and scope wording; no backend/store migration. Establish local pending-form state before adding more navigation.
3. **Simplify common tasks.** Provider summary/detail, role-labelled models, collapsed per-server tool permissions, explicit project-access hierarchy and honest saved/tested/readiness states.
4. **Connect related workflows.** Review warning → correct model role; missing tool key → provider credential editor; diagnostics warning → affected service. Preserve the referring task and return position.
5. **Verify behavior and usability.** Test a 420px mounted leaf in a wide window, a normal desktop and a short-height surface; keyboard operation, Escape/return focus, scroll and retained edits. Test existing mutation failures and prove that no model/provider call occurs on opening Settings.

Acceptance tasks: a new user can connect a provider, change only the reviewer model, find read-aloud configuration, disable an integration in one library without pausing it everywhere, change chat style, explain promotion permission and inspect a record-integrity issue without searching the full Library page. Compare success, wrong turns and help requests; do not claim user-test improvements from the mockup alone.

The accompanying image is an illustrative layout with placeholder model selections. It is not an app screenshot, functioning prototype, or evidence of configured models.
