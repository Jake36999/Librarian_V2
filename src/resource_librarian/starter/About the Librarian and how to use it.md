---
type: "about"
status: "active"
authority: "the orientation for this library: what the Librarian is, the pages you use, and where the formal notes are"
---

# About the Librarian and how to use it

**{name}** is a library of sources someone has actually read. The Librarian is the keeper: it finds
and reads material with help from models, drafts what it learned, and **nothing enters the library
until you accept it**. Agents can work in here too (Claude Code, Codex and others call the same
tools), and they follow the same rules.

This note opens beside the chat the first time you visit. Follow its links the way you would in
Obsidian (they are the same wikilinks): each one opens that note here. The formal notes at the end
are the reference.

## The pages

| Page | What it is for |
| --- | --- |
| **Chat** | Ask the librarian anything. A question that needs more than one search opens a *thread* (a session), and the **Plan** beside the chat shows where the thread is. |
| **Staging** | Everything waiting for your review: captured sources, folders, lenses, concepts, topics and offerings. Accept, reject or defer each one. |
| **Search** | Search the library, staging, past threads or recorded activity. |
| **Settings** | Models and services, permissions, review and promotion, shortcuts, health. **Models** (beside it) opens the same page at the model choices. |

The buttons across the top: the library menu (switch library), **Sessions** (resume or start a
thread), **Checkpoints** (decisions an agent is waiting for you to make), **Geo-Grapher** (the
graphs built from this library), and the power button (close Geo-Grapher or this library).

## How a source becomes part of the library

1. **Queued**: a reference or file is waiting to be fetched.
2. **Captured, to review**: it was fetched and a short description drafted. You can accept it as it is, or approve it for a full read.
3. **Approved, awaiting ingestion** then **Ingested, ready to accept**: the whole text was read, with claims and limits and the pages they came from.
4. **Accepted**: it becomes a note under `Sources/`, filed under a topic. Only you (or an agent you trust, see Permissions below) do this step.

Anything can be **deferred** (come back to it) or **rejected** (with a reason). Rejecting never
deletes the original file.

## Workflows you can start

Open **Modes** under the message box and choose **Queue an action**. Each workflow has a hint
(hover it) and says what it will leave behind. The same workflows can be given keyboard shortcuts
in Settings, under *Commands & shortcuts*, where each one is explained.

## Permissions

The **Modes** menu also sets how much the librarian may write on its own:

- **Plan**: reads and searches only; it proposes instead of writing.
- **Ask permission**: every write pauses for your answer (allow once, allow for this session, or deny).
- **Auto**: writes inside the phase it is in and the library's settings. Sensitive material still waits for you.

Review and promotion (Settings) decide whether promotions need a person or may be made by the
librarian itself.

## Where things live

| Folder | Holds |
| --- | --- |
| `Sources/` | accepted sources, one note each |
| `Concepts/` | concepts and the sources that use them |
| `Projects/` | pursuits: what you are working towards |
| `Offerings/` | drafted guides you promoted |
| `Indexes/` | the master index and one page per topic |
| `About/` | the formal notes below, and this library's rules |
| `.librarian/` | settings, session logs and staging. Hidden in Obsidian; safe to leave alone |

## The formal notes

- [[Rules]]: every rule the Librarian enforces, with its code. Generated, so it cannot drift.
- [[Tool Reference]]: every tool an agent or this page can call, by tier. Generated from the code.
- [[Note Content Model]]: what each kind of note must contain.
- [[Source Documentation Standard]]: how a source is described.
- [[Topics]]: the closed list sources are filed under.
- [[Domain Register]] and [[Domain Packs]]: how a library is specialised for a field.
- [[Recommended MCP Servers]] and [[Recommended Plugins]]: outside tools worth adding.

Platform and API documentation ships with the Librarian itself, in its `docs/` folder
(for example the operator guide, the agent guide and the product contract); the notes above are
the part every library carries with it.
