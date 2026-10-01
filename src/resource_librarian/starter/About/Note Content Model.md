---
type: "about"
status: "active"
authority: "the schema of this vault. The librarian reads these tables and enforces them; changing a shape, a field or an axis value means editing this note (NO_SCHEMA_DRIFT)"
---

# Note Content Model

## How This Note Is Used

This note is the vault's schema, written as tables so a person can read it and the librarian can
parse it. The librarian never adds a field, a shape or an axis value on its own: it proposes, and
a person edits this note. A vault without this note has no shape checks and says so.

Three layers, and each note belongs to one:

| Layer | May assert | Notes |
| --- | --- | --- |
| Data | this was present, this was said, on this date | evidence in `.evidence/`, never edited |
| Information | what the data points mean once related | Sources, Concepts |
| Knowledge | what it is for, realised against a need, and what it did | Projects, Offerings, Applications |

Information notes are written without framing: they describe what a source does, never what one
project hopes it does. Framing belongs in Projects, Offerings and Applications.

## Shapes

| Shape | Folder | type |
| --- | --- | --- |
| source | Sources | source |
| concept | Concepts | concept |
| project | Projects | project |
| offering | Offerings | offering |
| application | Applications | application |
| note | Notes | note |

## Source Kinds

| Kind | Folder | What it is |
| --- | --- | --- |
| repository | Sources/repository | a code repository |
| paper | Sources/paper | a paper, preprint or book chapter with a bibliographic identifier |
| dataset | Sources/dataset | a dataset or data service |
| document | Sources/document | a document without an identifier: a report, a manual, a book |
| page | Sources/page | a web page |
| standard | Sources/standard | a specification or standard |
| model | Sources/model | a hosted or local inference model |

## Frontmatter — source

| Field | Requirement |
| --- | --- |
| type | required |
| kind | required |
| title | required |
| canonical_url | required |
| status | required |
| primary_topic | required |
| captured_at | required |
| evidence | optional |
| aliases | optional |
| secondary_topics | optional |
| concepts | optional |
| sensitivity | optional |
| attested_by | optional |
| session | optional |
| catalogued_at | optional |
| file | optional |
| coverage | optional |
| not_examined | optional |

## Frontmatter — source/repository

| Field | Requirement |
| --- | --- |
| repo_key | required |
| license_class | required |
| ecosystem | required |
| domain_primary | optional |
| maturity_stage | required |
| deployment_target | required |
| interface_protocol | required |
| data_locality | required |
| hardware_footprint | required |
| security_compliance | required |
| agent_surface | required |
| category | optional |
| stars | optional |
| pushed_at | optional |
| container | optional |
| expansion_status | optional |

## Frontmatter — source/paper

| Field | Requirement |
| --- | --- |
| identifier_kind | required |
| identifier | required |
| authors | required |
| year | required |
| paper_kind | required |
| venue | optional |

## Frontmatter — source/model

| Field | Requirement |
| --- | --- |
| provider | required |
| model_id | required |
| modality | required |
| license_class | required |
| context_length | optional |
| price_input_per_1m | optional |
| price_output_per_1m | optional |
| tool_calling | optional |
| reasoning | optional |
| best_for | optional |
| suggested_tier | optional |
| json_schema | optional |

## Frontmatter — concept

| Field | Requirement |
| --- | --- |
| type | required |
| concept_kind | required |
| status | required |
| aliases | optional |
| senses | optional |
| related | optional |

## Frontmatter — project

A project is a pursuit: a course, a job, a project or a research or learning
line, distinguished by `pursuit_kind`. `started` and `horizon` are free text
(a date, or a phrase like "end of semester") - not every pursuit has a clean
end date.

| Field | Requirement |
| --- | --- |
| type | required |
| status | required |
| stage | required |
| pursuit_kind | required |
| aliases | optional |
| constraints | optional |
| disqualifiers | optional |
| repository | optional |
| started | optional |
| horizon | optional |

## Frontmatter — offering

| Field | Requirement |
| --- | --- |
| type | required |
| offering_kind | required |
| status | required |
| created | required |
| sources | required |
| project | optional |
| attested_by | optional |
| session | optional |

## Frontmatter — application

| Field | Requirement |
| --- | --- |
| type | required |
| project | required |
| stage | required |
| outcome | required |
| sources_used | required |
| unresolved_sources | optional |
| attested_by | optional |
| session | optional |
| date_range | optional |

## Sections — source/repository

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Bottom Line | required |
| 2 | What It Solves | required |
| 3 | Architecture & Mechanics | optional |
| 4 | What Is Inside | optional |
| 5 | Access Points | optional |
| 6 | Transferable Capability | optional |
| 7 | Integration & Use Cases | optional |
| 8 | Evidence & Limits | optional |
| 9 | Reading Notes | optional |
| 10 | Evidence | required |

## Sections — source/paper

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Bottom Line | required |
| 2 | Claim | required |
| 3 | Method | optional |
| 4 | Evidence & Limits | optional |
| 5 | Transferable Capability | optional |
| 6 | Reading Notes | optional |
| 7 | Evidence | required |

## Sections — source/model

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Bottom Line | required |
| 2 | What It's For | required |
| 3 | Specs | required |
| 4 | Reading Notes | optional |
| 5 | Evidence | required |

## Sections — source

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Bottom Line | required |
| 2 | What It Solves | optional |
| 3 | Claims | optional |
| 4 | What Is Inside | optional |
| 5 | Evidence & Limits | optional |
| 6 | Transferable Capability | optional |
| 7 | Reading Notes | optional |
| 8 | Evidence | required |

## Sections — concept

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Definition | required |
| 2 | Usages | optional |
| 3 | Sense Notes | optional |
| 4 | Related | optional |
| 5 | Understanding | optional |

Understanding is written by `understanding_record` (a `learn` session's practice or
consolidate phase, Co-work Roadmap §2 W2): dated entries, in the person's own words, with a
confidence (shaky / ok / solid). Never written by anything else - a model's own paraphrase does
not belong here.

## Sections — project

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Summary | required |
| 2 | Goal | optional |
| 3 | Milestones | optional |
| 4 | Current Focus | optional |
| 5 | Fixed Constraints | optional |
| 6 | Standing Disqualifiers | optional |
| 7 | Open Needs | optional |
| 8 | Decisions | optional |
| 9 | Reflections | optional |

## Sections — offering

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | Summary | required |
| 2 | Sources | required |

## Sections — application

| Order | Section | Requirement |
| --- | --- | --- |
| 1 | What Was Needed | required |
| 2 | What Was Found And Taken | required |
| 3 | What It Replaced | required |
| 4 | What The Catalogue Should Learn | required |
| 5 | Not Yet In The Library | optional |
| 6 | Project Files | optional |
| 7 | Changes | optional |

## Claim Sections And Caveat Sections

**Claim**: Bottom Line, What It Solves, Architecture & Mechanics, What Is Inside, Access Points,
Transferable Capability, Integration & Use Cases, Claim, Claims, Method, What It's For, Specs, Definition. A
search match here is evidence the source does the thing.

**Caveat**: Reading Notes, Evidence, Evidence & Limits, Usages, Sense Notes. A match here is
evidence *about* the source (or, on a concept, about how sources use the word), often the opposite
of a claim, and earns no ranking credit.

**Not indexed as text**: Evidence, Related, Sources, Sources Using This. These hold links and record ids, not prose; a
search term matching them says nothing about the note.

A heading on neither list counts as a claim: a new section is more likely to describe a source
than to caveat it.

`Transferable Capability` states what a source does without its own field's vocabulary, and what
it would replace. It is never written toward any project, including the one that found it.

## Axis Values — source/repository


`ecosystem` is the main programming language (`Markdown` for a repository that is mostly prose,
`Mixed` when no language dominates). `domain_primary` starts with no values: a vault's subject
areas come from what it actually holds, so they are added here (by a person, or by accepting a
taxonomy proposal) once there are sources to name them from. Until a value is accepted, the field
stays empty.

| Axis | Permitted values |
| --- | --- |
| license_class | Copyleft, Permissive, Source_Available, Unknown, Weak_Copyleft |
| ecosystem | C, CPlusPlus, CSharp, Go, Haskell, Java, JavaScript, Julia, Kotlin, Lua, Markdown, Mixed, PHP, Python, R, Ruby, Rust, Scala, Shell, Swift, TypeScript |
| domain_primary | |
| maturity_stage | Abandoned, Active, Production_Ready, Reference |
| deployment_target | Browser, Desktop, Local_Only, Server |
| interface_protocol | CLI, GUI, Markdown, Python_SDK, REST, Web_UI |
| data_locality | Distributed, Local_First, Stateless |
| hardware_footprint | Browser_Only, CPU_Only, High_Memory, Low_VRAM |
| security_compliance | Security_Adjacent, Uncertified |
| agent_surface | Callable, Documented, None, Procedural |

## Axis Values — source/paper

| Axis | Permitted values |
| --- | --- |
| identifier_kind | arxiv, doi |
| paper_kind | preprint, published |

## Axis Values — source/model

| Axis | Permitted values |
| --- | --- |
| provider | Anthropic, DeepInfra, Google, LMStudio_Local, OpenAI, OpenRouter |
| modality | Embeddings, Image_To_Text, Speech_To_Text, Text_Generation, Text_To_Speech |
| license_class | Copyleft, Permissive, Source_Available, Unknown, Weak_Copyleft |
| best_for | Talking_Fast, Long_Conversations, Small_Coding_Tasks, Large_Coding_Tasks, Long_Horizon_Tasks |
| suggested_tier | Tier_1, Tier_2, Tier_3 |

`best_for` takes more than one value: what the model has actually shown it is good at. A
clerk's first pass at it, from the model's own listing page, is a starting guess for the person
to confirm or correct - only a person's own use, or a real comparison like
`10-Models/`'s Reading Notes once held in V1, is evidence enough to trust it.

`suggested_tier`, one value, is the model tile's own three roles, not a judgement of the model in
the abstract:
- **Tier_1**: a large model capable of long-horizon work and of overseeing other agents.
- **Tier_2**: capable of complex tasks, short of Tier_1.
- **Tier_3**: a lightweight, quick-thinking model suited to sub-agent work.

## Axis Values — concept

| Axis | Permitted values |
| --- | --- |
| concept_kind | term, pattern |

## Axis Values — project

| Axis | Permitted values |
| --- | --- |
| pursuit_kind | course, job, project, research, learning |
| stage | idea, planning, active, paused, done, dropped |

## Axis Values — offering

| Axis | Permitted values |
| --- | --- |
| offering_kind | branch_offering, insight_report, suggestion, external_report |

## Axis Values — all

| Axis | Permitted values |
| --- | --- |
| status | draft, active, published, archived |
| attested_by | person, agent |
