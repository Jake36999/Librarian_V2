---
name: add-a-project
description: Frame a new project in the Librarian vault and supply it from the catalogue — constraints, disqualifiers, briefs, candidates and an offering. Use when the person describes something they want to build or start.
---

# Adding a project

Open with `open_session(purpose="add_project")`, then walk the phases the envelope names.

1. **frame**: `create_project` with the stage, a summary in the person's words, hard
   constraints (for example a licence class) and **disqualifiers**: what would rule a source
   out. Ask for disqualifiers if the person gives none (`ask_user`); a need with no
   disqualifiers makes every judgement softer.
2. **ingest**: sources the person already holds (`ingest` with a URL or reference). Record
   `ingested: none` in the plan if there are none.
3. **map**: `search` with `intent: orient` to see where the catalogue already holds material;
   record the map with `update_plan`.
4. **need**: one `open_brief` per distinct need, phrased as a job to be done, not a product.
5. **search**: `research_round` per brief, then `checkpoint` with what you learned, two to four
   open sub-threads and next targets. The stopping rule fires when rounds stop adding sources
   or vocabulary; stop when it does.
6. **judge**: `decide` on every candidate: keep (with its role) or reject (with the reason).
   A rejection is a finding and is recorded as carefully as a keep.
7. **synthesise**: `record_synthesis`, then use the `write-an-offering` skill.
8. **check_out**: close every brief (`close_brief`), then `close_session` with a summary and
   the gaps you could not fill.

The session log is the record. Do not write project notes yourself.
