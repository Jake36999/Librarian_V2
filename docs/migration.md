# Guided Resource Library V1 migration

V1 is read-only history.  Librarian V2 imports a selected subset through
`v1_import_plan`, `v1_import_stage`, and `v1_import_status`; it never edits the
V1 root.

1. Create or open the target V2 vault.
2. Call `v1_import_plan` with exactly one existing V1 root.
3. Review the source fingerprint, included categories, exclusions, duplicates,
   sensitive material, drafts, and proposed collisions.
4. Confirm the selected records and call `v1_import_stage`.  Pass its optional
   `paths` list to stage only reviewed plan rows; omit it only to accept the
   already-reviewed safe filter set as a whole.
5. Review the staged records through the normal staging workflow before any
   promotion.

The default inclusion set is catalogued active/published sources, concepts,
applications, and offerings.  Drafts, canvases, generated hubs/queues/indexes,
workflows, untyped notes, and derived caches are excluded by default.

The V2 vault records an append-only import manifest with the V1 fingerprint,
source hashes, selected filters, staged IDs, collision mappings, skip reasons,
and promotion state.  Whole V1 notes are preserved as evidence, so a later
reader can inspect the original rather than relying on a generated summary.
Once staging begins, the vault is bound to that one V1 root; a different root
can still be previewed but cannot be mixed into the same migration manifest.

