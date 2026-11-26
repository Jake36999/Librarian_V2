# Use case diagram: Librarian (as-is)

Actors outside the boundary; dashed arrows are «include» and «extend».

```mermaid
flowchart LR
  owner(["Owner"])
  overseer(["Overseer (tier 0)"])
  lead(["Lead (tier 1)"])
  clerk(["Clerk (tier 3)"])
  model(["Model worker and model host"])
  geo(["Geo-Grapher"])
  external(["External project"])
  subgraph system["Librarian (as-is)"]
    UC0(["UC0 Start work in the library"])
    UC0_2(["UC0.2 Work for an external project through MCP"])
    UC1(["UC1 Make a folder of documents into Source notes"])
    UC1_1(["UC1.1 Review a folder and apply its groups"])
    UC1_2(["UC1.2 Capture, describe and stage a source"])
    UC1b(["UC1b Run the approved batch"])
    UC1c(["UC1c Enrich one source"])
    UC1c_1(["UC1c.1 Validate and parse a source"])
    UC1c_2(["UC1c.2 Read a source"])
    UC1c_3(["UC1c.3 Publish a paper to the paper graph"])
    UC1_3(["UC1.3 Accept a source into the library"])
    UC2(["UC2 Research a brief across a corpus"])
    UC3(["UC3 Verify a report's claims"])
    UC4(["UC4 Read and cite a paper from the graph"])
    UC8(["UC8 Compose work from actions"])
    UC8_1(["UC8.1 Run a saved workflow from the Web UI"])
    UC_D(["UC-D Repair a failed step"])
    UC_O(["UC-O Judge work against its requirements"])
    UC5(["UC5 Trust a relation (deferred)"])
    UC6(["UC6 Reorganise a folder into groups (deferred)"])
    UC7(["UC7 See the data in another model (deferred)"])
  end
  owner --- UC0
  overseer --- UC0
  UC0 -. "«include»" .-> UC0_2
  UC0 -. "«include»" .-> UC1_1
  UC0 -. "«include»" .-> UC1_2
  UC0 -. "«include»" .-> UC8_1
  UC0 -. "«include»" .-> UC1b
  UC0 -. "«include»" .-> UC1_3
  overseer --- UC0_2
  external --- UC0_2
  owner --- UC1
  overseer --- UC1
  geo --- UC1
  model --- UC1
  UC1 -. "«include»" .-> UC1_1
  UC1 -. "«include»" .-> UC1_2
  UC1 -. "«include»" .-> UC1b
  UC1 -. "«include»" .-> UC1_3
  owner --- UC1_1
  geo --- UC1_1
  model --- UC1_2
  owner --- UC1b
  UC1b -. "«include»" .-> UC1c
  model --- UC1c
  geo --- UC1c
  UC1c -. "«include»" .-> UC1c_1
  UC1c -. "«include»" .-> UC1c_2
  UC1c -. "«include»" .-> UC1c_3
  model --- UC1c_1
  model --- UC1c_2
  geo --- UC1c_3
  owner --- UC1_3
  owner --- UC2
  lead --- UC2
  UC2 -. "«include»" .-> UC3
  UC2 -. "«include»" .-> UC4
  lead --- UC3
  clerk --- UC3
  lead --- UC4
  geo --- UC4
  owner --- UC8
  overseer --- UC8
  UC8 -. "«include»" .-> UC8_1
  owner --- UC8_1
  overseer --- UC_D
  owner --- UC_D
  owner --- UC_O
  lead --- UC_O
  owner --- UC5
  owner --- UC6
  owner --- UC7
```

| Use case | Actors | Spec | Status |
|---|---|---|---|
| UC0 Start work in the library | Owner, Overseer (tier 0) | [activation](views/activation.views.md) | IMPLEMENTED_VERIFIED |
| UC0.2 Work for an external project through MCP | Overseer (tier 0), External project | [activation-external-project](views/activation-external-project.views.md) | IMPLEMENTED_VERIFIED |
| UC1 Make a folder of documents into Source notes | Owner, Overseer (tier 0), Geo-Grapher, Model worker and model host | [ingestion](views/ingestion.views.md) | IMPLEMENTED_VERIFIED |
| UC1.1 Review a folder and apply its groups | Owner, Geo-Grapher | [folder-review](views/folder-review.views.md) | IMPLEMENTED_VERIFIED |
| UC1.2 Capture, describe and stage a source | Model worker and model host | [source-intake](views/source-intake.views.md) | IMPLEMENTED_VERIFIED |
| UC1b Run the approved batch | Owner | [batch-enrichment](views/batch-enrichment.views.md) | IMPLEMENTED_VERIFIED |
| UC1c Enrich one source | Model worker and model host, Geo-Grapher | [source-enrichment](views/source-enrichment.views.md) | IMPLEMENTED_VERIFIED |
| UC1c.1 Validate and parse a source | Model worker and model host | [source-parse](views/source-parse.views.md) | IMPLEMENTED_VERIFIED |
| UC1c.2 Read a source | Model worker and model host | [source-reading](views/source-reading.views.md) | IMPLEMENTED_VERIFIED |
| UC1c.3 Publish a paper to the paper graph | Geo-Grapher | [paper-publication](views/paper-publication.views.md) | IMPLEMENTED_VERIFIED |
| UC1.3 Accept a source into the library | Owner | [acceptance](views/acceptance.views.md) | IMPLEMENTED_VERIFIED |
| UC2 Research a brief across a corpus | Owner, Lead (tier 1) | [research](views/research.views.md) | IMPLEMENTED_OBSERVED |
| UC3 Verify a report's claims | Lead (tier 1), Clerk (tier 3) | [verify-claims](views/verify-claims.views.md) | IMPLEMENTED_OBSERVED |
| UC4 Read and cite a paper from the graph | Lead (tier 1), Geo-Grapher | [cite-graph](views/cite-graph.views.md) | IMPLEMENTED_OBSERVED |
| UC8 Compose work from actions | Owner, Overseer (tier 0) | [compose](views/compose.views.md) | IMPLEMENTED_VERIFIED |
| UC8.1 Run a saved workflow from the Web UI | Owner | [workflow-run](views/workflow-run.views.md) | IMPLEMENTED_VERIFIED |
| UC-D Repair a failed step | Overseer (tier 0), Owner | [doctor](views/doctor.views.md) | IMPLEMENTED_OBSERVED |
| UC-O Judge work against its requirements | Owner, Lead (tier 1) | [oracle](views/oracle.views.md) | IMPLEMENTED_VERIFIED |
| UC5 Trust a relation | Owner | — | deferred: to-be only; there is no as-is (USE-CASES.md UC5) |
| UC6 Reorganise a folder into groups | Owner | — | deferred: PLAN.md 2.2 |
| UC7 See the data in another model | Owner | — | deferred: PLAN.md 2.2 |
