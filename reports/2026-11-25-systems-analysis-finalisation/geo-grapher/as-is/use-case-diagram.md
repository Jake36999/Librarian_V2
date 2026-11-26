# Use case diagram: Geo-Grapher (as-is)

Actors outside the boundary; dashed arrows are «include» and «extend».

```mermaid
flowchart LR
  owner(["Owner"])
  lead(["Lead (tier 1)"])
  core(["Librarian Core"])
  model(["Model worker"])
  subgraph system["Geo-Grapher (as-is)"]
    UC_G1(["UC-G1 Build the library's graphs from reviewed folders, and publish its papers"])
    UC_G3(["UC-G3 Query a graph through MCP"])
    UC_G4(["UC-G4 Search across graphs and their bridges"])
    UC_G5(["UC-G5 Compare, merge and copy graphs (deferred)"])
    UC_G6(["UC-G6 Explore a graph in the 3D workspace (deferred)"])
    UC_G7(["UC-G7 Build graphs of the Owner's own projects (deferred)"])
  end
  owner --- UC_G1
  core --- UC_G1
  model --- UC_G1
  lead --- UC_G3
  lead --- UC_G4
  owner --- UC_G4
  owner --- UC_G5
  owner --- UC_G6
  owner --- UC_G7
```

| Use case | Actors | Spec | Status |
|---|---|---|---|
| UC-G1 Build the library's graphs from reviewed folders, and publish its papers | Owner, Librarian Core, Model worker | [graph-building](views/graph-building.views.md) | IMPLEMENTED_VERIFIED |
| UC-G3 Query a graph through MCP | Lead (tier 1) | [query-graph](views/query-graph.views.md) | IMPLEMENTED_VERIFIED |
| UC-G4 Search across graphs and their bridges | Lead (tier 1), Owner | [federated-search](views/federated-search.views.md) | IMPLEMENTED_VERIFIED |
| UC-G5 Compare, merge and copy graphs | Owner | — | deferred: diff-graphs, clone-report, drift-report, merge, copy-graph, delete-graph: not on the Librarian's path |
| UC-G6 Explore a graph in the 3D workspace | Owner | — | deferred: the person's UI; not on the Librarian's path |
| UC-G7 Build graphs of the Owner's own projects | Owner | — | deferred: ingest-graphs, ingest-workspace, init-workspace: outside folder review |
