# Use case diagram: Librarian (to-be)

Actors outside the boundary; dashed arrows are «include» and «extend».

```mermaid
flowchart LR
  owner(["Owner"])
  overseer(["Overseer (tier 0)"])
  lead(["Lead (tier 1)"])
  clerk(["Clerk (tier 2)"])
  scribe(["Scribe (tier 3)"])
  oracle(["Oracle"])
  doctor(["Doctor"])
  geo(["Geo-Grapher"])
  external(["External project"])
  subgraph system["Librarian (to-be)"]
    UC8(["UC8 Compose and start a sprint"])
    UC8_2(["UC8.2 Compose a process and promote it into the repertoire"])
    UC0_1(["UC0.1 Work for the Owner as tier 0 (Context 1)"])
    UC0_2(["UC0.2 Work for an external project through MCP (Context 2)"])
    UC0_3(["UC0.3 Work directly in the Web UI (Context 3)"])
    UC0_4(["UC0.4 Delegate a task to the library's workers, as tier 0"])
    UC1(["UC1 Make a folder of documents into Source notes"])
    UC1_1(["UC1.1 Review a folder and apply its group"])
    UC1_2(["UC1.2 Capture, title and stage each source"])
    UC1b(["UC1b Run the approved batch"])
    UC1c(["UC1c Enrich one source"])
    UC1c_1(["UC1c.1 Validate and parse a source"])
    UC1c_2(["UC1c.2 Read a source"])
    UC1c_3(["UC1c.3 Publish a paper to the paper graph"])
    UC1_3(["UC1.3 Accept the screened sources"])
    UC2(["UC2 Research a brief across a corpus"])
    UC3(["UC3 Verify a report's claims"])
    UC4(["UC4 Read and cite a paper from the graph"])
    UC_O(["UC-O Judge a process's output"])
    UC_D(["UC-D Repair a failure through a ticket"])
    UC_L(["UC-L Learn a remedy"])
    UC9(["UC9 Decide the agenda and resume held work"])
    UC8_1(["UC8.1 Run a saved workflow from the Web UI (deferred)"])
    UC5(["UC5 Trust a relation (deferred)"])
    UC6(["UC6 Reorganise a folder into groups (deferred)"])
    UC7(["UC7 See the data in another model (deferred)"])
    UC10(["UC10 Search and read the library (deferred)"])
    UC11(["UC11 Add a project and map what the library holds for it (deferred)"])
    UC12(["UC12 Suggest work for the vault (deferred)"])
    UC13(["UC13 Start a pursuit (a course, a role or a project) (deferred)"])
    UC14(["UC14 Study a topic with the library (deferred)"])
    UC15(["UC15 Add a capability (an MCP server) (deferred)"])
    UC16(["UC16 Run a scheduled pipeline (deferred)"])
  end
  owner --- UC8
  overseer --- UC8
  UC8 -. "«include»" .-> UC0_1
  UC8 -. "«include»" .-> UC0_2
  UC8 -. "«include»" .-> UC0_3
  UC8 -. "«include»" .-> UC8_2
  UC8 -. "«include»" .-> UC_O
  lead --- UC8_2
  owner --- UC8_2
  oracle --- UC8_2
  owner --- UC0_1
  overseer --- UC0_1
  UC0_1 -. "«include»" .-> UC1
  UC0_1 -. "«include»" .-> UC_D
  overseer --- UC0_2
  external --- UC0_2
  owner --- UC0_3
  overseer --- UC0_4
  geo --- UC0_4
  UC0_4 -. "«include»" .-> UC_O
  UC0_4 -. "«include»" .-> UC_G3
  owner --- UC1
  overseer --- UC1
  geo --- UC1
  UC1 -. "«include»" .-> UC1_1
  UC1 -. "«include»" .-> UC1_2
  UC1 -. "«include»" .-> UC1b
  UC1 -. "«include»" .-> UC1_3
  UC1 -. "«include»" .-> UC_D
  owner --- UC1_1
  geo --- UC1_1
  UC1b -. "«include»" .-> UC1c
  UC1b -. "«include»" .-> UC_D
  UC1c -. "«include»" .-> UC1c_1
  UC1c -. "«include»" .-> UC1c_2
  UC1c -. "«include»" .-> UC1c_3
  UC1c -. "«include»" .-> UC_D
  geo --- UC1c_3
  owner --- UC1_3
  owner --- UC2
  lead --- UC2
  UC2 -. "«include»" .-> UC3
  UC2 -. "«include»" .-> UC4
  UC2 -. "«include»" .-> UC_O
  lead --- UC3
  clerk --- UC3
  lead --- UC4
  geo --- UC4
  oracle --- UC_O
  doctor --- UC_D
  owner --- UC_D
  owner --- UC_L
  owner --- UC9
  overseer --- UC9
  UC9 -. "«include»" .-> UC_D
  owner --- UC8_1
  owner --- UC5
  owner --- UC6
  owner --- UC7
  owner --- UC10
  overseer --- UC11
  overseer --- UC12
  overseer --- UC13
  owner --- UC13
  overseer --- UC14
  owner --- UC14
  overseer --- UC15
  owner --- UC15
  owner --- UC16
```

| Use case | Actors | Spec | Status |
|---|---|---|---|
| UC8 Compose and start a sprint | Owner, Overseer (tier 0) | [compose](views/compose.views.md) | PROPOSED_UNACCEPTED |
| UC8.2 Compose a process and promote it into the repertoire | Lead (tier 1), Owner, Oracle | [catalogue](views/catalogue.views.md) | PROPOSED_UNACCEPTED |
| UC0.1 Work for the Owner as tier 0 (Context 1) | Owner, Overseer (tier 0) | [activation-overseer](views/activation-overseer.views.md) | PROPOSED_UNACCEPTED |
| UC0.2 Work for an external project through MCP (Context 2) | Overseer (tier 0), External project | [activation-external-project](views/activation-external-project.views.md) | PROPOSED_UNACCEPTED |
| UC0.3 Work directly in the Web UI (Context 3) | Owner | [activation-web-ui](views/activation-web-ui.views.md) | PROPOSED_UNACCEPTED |
| UC0.4 Delegate a task to the library's workers, as tier 0 | Overseer (tier 0), Geo-Grapher | [delegate](views/delegate.views.md) | PROPOSED_UNACCEPTED |
| UC1 Make a folder of documents into Source notes | Owner, Overseer (tier 0), Geo-Grapher | [ingestion](views/ingestion.views.md) | PROPOSED_UNACCEPTED |
| UC1.1 Review a folder and apply its group | Owner, Geo-Grapher | [folder-review](views/folder-review.views.md) | PROPOSED_UNACCEPTED |
| UC1.2 Capture, title and stage each source |  | [source-intake](views/source-intake.views.md) | PROPOSED_UNACCEPTED |
| UC1b Run the approved batch |  | [batch-enrichment](views/batch-enrichment.views.md) | PROPOSED_UNACCEPTED |
| UC1c Enrich one source |  | [source-enrichment](views/source-enrichment.views.md) | PROPOSED_UNACCEPTED |
| UC1c.1 Validate and parse a source |  | [source-parse](views/source-parse.views.md) | PROPOSED_UNACCEPTED |
| UC1c.2 Read a source |  | [source-reading](views/source-reading.views.md) | PROPOSED_UNACCEPTED |
| UC1c.3 Publish a paper to the paper graph | Geo-Grapher | [paper-publication](views/paper-publication.views.md) | PROPOSED_UNACCEPTED |
| UC1.3 Accept the screened sources | Owner | [acceptance](views/acceptance.views.md) | PROPOSED_UNACCEPTED |
| UC2 Research a brief across a corpus | Owner, Lead (tier 1) | [research](views/research.views.md) | PROPOSED_UNACCEPTED |
| UC3 Verify a report's claims | Lead (tier 1), Clerk (tier 2) | [verify-claims](views/verify-claims.views.md) | PROPOSED_UNACCEPTED |
| UC4 Read and cite a paper from the graph | Lead (tier 1), Geo-Grapher | [cite-graph](views/cite-graph.views.md) | PROPOSED_UNACCEPTED |
| UC-O Judge a process's output | Oracle | [oracle](views/oracle.views.md) | PROPOSED_UNACCEPTED |
| UC-D Repair a failure through a ticket | Doctor, Owner | [doctor](views/doctor.views.md) | PROPOSED_UNACCEPTED |
| UC-L Learn a remedy | Owner | [learn](views/learn.views.md) | PROPOSED_UNACCEPTED |
| UC9 Decide the agenda and resume held work | Owner, Overseer (tier 0) | [agenda](views/agenda.views.md) | PROPOSED_UNACCEPTED |
| UC8.1 Run a saved workflow from the Web UI | Owner | — | deferred: no separate to-be spec: its steps are wgrant, uinotify and uiagenda in activation-web-ui, under compose (as-is W-WFR-01 to 03 are handled there) |
| UC5 Trust a relation | Owner | — | deferred: USE-CASES.md UC5; not yet drawn |
| UC6 Reorganise a folder into groups | Owner | — | deferred: PLAN.md 2.2 |
| UC7 See the data in another model | Owner | — | deferred: PLAN.md 2.2 |
| UC10 Search and read the library | Owner | — | deferred: the Web UI's Search and note view, and the search and get_note tools; it only reads |
| UC11 Add a project and map what the library holds for it | Overseer (tier 0) | — | deferred: the add_project session purpose; its sources go through UC1 |
| UC12 Suggest work for the vault | Overseer (tier 0) | — | deferred: the suggest session purpose |
| UC13 Start a pursuit (a course, a role or a project) | Overseer (tier 0), Owner | — | deferred: the start_pursuit session purpose |
| UC14 Study a topic with the library | Overseer (tier 0), Owner | — | deferred: the learn session purpose (tutoring); not UC-L, which learns a remedy |
| UC15 Add a capability (an MCP server) | Overseer (tier 0), Owner | — | deferred: the add_capability session purpose; the person decides the install |
| UC16 Run a scheduled pipeline | Owner | — | deferred: weekly-review and clear-enrichment-backlog; not overseen, so a high-risk decision holds for the Owner |
