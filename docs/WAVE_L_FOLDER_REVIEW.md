# Folder review with Geo-Grapher (Wave L)

This feature is opt-in per library. It does not choose a lead, launch enrichment, qualify a model, accept an MCP server or ingest a real library automatically.

## Operator configuration

Install the reviewed Geo-Grapher wheel into a dedicated environment on the library's data drive. Verify the wheel SHA256 against the Wave L gate report. The build retains version `0.2.0`; the recorded SHA256 identifies this feature candidate rather than the earlier 0.2.0 build.

In that library's `.librarian/geographer.json`, configure its installed-wheel command:

```json
{
  "enabled": true,
  "wheel_version": "0.2.0",
  "command": ["G:/Libraries/<library>/.tools/geographer/Scripts/python.exe", "-I", "-m", "geographer"]
}
```

`<library>` is an example placeholder. Do not point this at a source checkout. With the file absent or `enabled: false`, ordinary native ingestion remains available. Credential refusal applies regardless of this switch.

The native attach flow uses one metadata survey for native compare-and-apply and the Geo partition plan. The CLI receives `folder-inventory-v1` on stdin, including the same survey fingerprint; it does not walk the folder again to plan it. Incomplete surveys and stale accepted group members are refused before graph application.

## Person review

Open **Staging → Folders**. Survey a content root to stage cards. Cards show paths, counts by file kind, bytes, suggestion reasons, a graph label, and a description draft. Purposes are `own-current`, `own-legacy`, `own-docs`, `research-docs`, `third-party`, `data`, `logs/transcripts`, and `exclude`.

The optional description button requires explicit spending approval and the existing qualified Clerk route. It submits bounded inventory metadata, never source bodies or third-party graph contents. The draft remains unaccepted. QA screenshots use a visibly labelled scripted draft and make no paid-model claim.

Accepting is a separate person action. It compares the card's folder fingerprint and checks every accepted group member that would be re-ingested. Same graph labels produce a real shared graph with separate repository namespaces. An existing owned project graph can be chosen by its unique label; its original source and identity are retained. Registered external stores cannot be expanded. Incompatible strata require separate graphs.

An accepted child overrides an internal parent's purpose for indexing, watching and writes. Attached source projects remain read-only even when classified as own content. In enabled libraries their maps and logs live under `.librarian/project-sidecars/`, leaving the source tree untouched.

Re-surveys preserve unchanged decisions and restage changed folders. Excluding the last member hides its reviewed graph and retains immutable snapshots; nothing is deleted. A failed graph application keeps the read barrier and a visible failed staging item for retry.

PDF assignments retain paper modality. This static graph application indexes supported code/text; PDF extraction and paid enrichment continue through the existing paper/native workflows under their own approval gates. A paper assignment alone is not evidence that PDF text was extracted.

## Research boundary

Third-party graphs use bronze trust and content modality. Tier-3 `dispatch_plan` tasks are rejected as `PLAN_SCOPE`, naming the task, before packet compilation or model calls. The server independently rejects third-party reads through Clerk/Scribe principals and tier-3 profiles.

Generate proposed MCP entries using the installed wheel's `review-mcp-config --catalog ... --command-json ...`. This prints configuration only: review and accept it through the normal native MCP flow. The own-packet entry has an explicit own-graph allow-list and Clerk principal; third-party entries use lead/research-helper principals. No automatic acceptance or qualification bypass is performed.

Agent hits, packets and federated results label external provenance and graph-qualified citations. Structured packet contracts flag external claims presented as current-system facts. The free-prose checker flags explicit current-system framing around delivered third-party handles and adds a visible source-scope warning, without a model retry. It is a deterministic detector, not proof against every possible paraphrase.

Own-to-third-party bridges can only be `reference`, with an explicit owner decision. Automatic equivalence proposals are suppressed. The existing W3-5 scoring firewall is unchanged.

Credential-like filenames and roots are refused before survey content counting, text extraction or ingestion. Refusal reports contain names only. Refused directories are not traversed, so the count is refused paths, including directory boundaries, rather than a count of all private files below them.
