---
type: "about"
status: "active"
authority: "how to opt a discipline-specific extension into this vault's Content Model. Nothing here is enabled until its rows are copied into About/Note Content Model.md"
---

# Domain Packs

The Content Model is the whole schema: every kind, field, section and axis the librarian
checks a note against comes from `About/Note Content Model.md`, read fresh every time - never
from a fixed list inside the program. A domain pack is nothing more than a few extra rows in
that one file: a new `## Source Kinds` row, an optional `## Frontmatter — source/<kind>` table
for fields specific to it, and an optional `## Sections — source/<kind>` table if it wants its
own section layout instead of the generic one. Nothing is enabled per vault until you paste a
pack's rows in yourself - "opt-in" means the file you already own, not a setting to flip.

To add a pack: open `About/Note Content Model.md`, add the pack's kind row to the existing
`## Source Kinds` table, and paste its `## Frontmatter — source/<kind>` table in below the
existing per-kind ones (`source/repository`, `source/paper`, `source/model`). The next source
promoted with that kind is checked against it immediately - no restart, no code.

## History
Primary and secondary sources need to say where they came from and whose eyes wrote them.

Add to `## Source Kinds`:
```
| history | Sources/history | a primary or secondary historical source |
```

`## Frontmatter — source/history`

| Field | Requirement |
| --- | --- |
| provenance | required |
| perspective | optional |
| date | optional |

## Literature
A literary or textual work needs the edition and the passage, not just a URL.

Add to `## Source Kinds`:
```
| literature | Sources/literature | a literary or textual primary work |
```

`## Frontmatter — source/literature`

| Field | Requirement |
| --- | --- |
| author | required |
| edition | optional |
| passage_ref | optional |

## Science
A scientific claim is only as strong as its method and whether it replicated.

Add to `## Source Kinds`:
```
| study | Sources/study | a scientific study or experimental report |
```

`## Frontmatter — source/study`

| Field | Requirement |
| --- | --- |
| method | required |
| evidence_strength | optional |
| replicated | optional |

## IT
Mostly exists already: `repository` and `model` kinds already carry `license_class`,
`ecosystem`, and version-shaped fields (`About/Note Content Model.md`'s existing
`## Frontmatter — source/repository` and `## Frontmatter — source/model` tables). No pack
needed here unless a vault wants a field neither already has.

## Verifying a pack took
`doctor` reports the content model's shape and kind count (`content model` check); a promoted
source's frontmatter is only ever checked against what `About/Note Content Model.md` says at
the moment it promotes, so editing the file and then re-promoting (or checking an existing note
against the updated model) is the only verification that matters - there is nothing else to
restart or rebuild.

## Lens packs: how a discipline brings its own ways of reasoning
A domain pack says what a note *holds*. A **lens pack** says how the model should *reason* about a
kind of material: a handful of named stances, each with the questions it makes you ask, the
failure it catches, and when it does and doesn't apply. A pack is one YAML file, `lens_pack:
<name>` plus a list of `lenses:`, in the vault's `.librarian/lens_packs/` folder. The standard
packs shipped with the librarian (`tool-choice`, `source-assessment`) show the shape.

Nothing in a pack is used until a person accepts it (Settings → Library → Lens packs, or
`lens_pack_accept`). Acceptance is tied to the file's exact text, so a pack that changes afterwards
shows as *changed* and keeps its old lenses until it is accepted again. Every text field is screened
for embedded instructions and links, and one bad lens refuses the whole pack. Even an accepted lens
reaches the model only when a person adopts it for a thread (the ⋮ menu's *Lenses* section, at most
three at a time). The model may suggest a lens with `lens_suggest`, but it never adopts one.

Material and task tags (`materials: [document]`, `tasks: [assess]`) are free-form, so a history
pack can say `materials: [primary-source]` and a course pack `tasks: [revise]`.

## Domain profiles: all of this in one step, at creation
A **domain profile** bundles a domain pack's rows with the lens packs, outside servers and workflows
that suit it, and applies them once when a library is created:
`new-vault.ps1 -Domain History -Profile history`, or `resource-librarian init <folder> --profile
history`. The standard profiles are `software-systems`, `course` and `history`, and a profile can
also be a file of your own.

Choosing a profile at creation writes its Content Model rows into the new library, the same as
pasting them in yourself. Everything else it names is only *suggested*: Settings → Library shows a
checklist, and each lens pack, server or workflow is still accepted, installed or enabled by you
through its usual gate.
