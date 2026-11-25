# Process composition: geo-grapher/to-be

Which process calls which (`kind: ref`). Roots: `federated-search`, `graph-building`, `paper-import`, `query-graph`.

```mermaid
flowchart TD
  federated_search["federated-search<br/>UC-G4"]
  graph_building["graph-building<br/>UC-G1"]
  paper_import["paper-import<br/>UC-G2"]
  query_graph["query-graph<br/>UC-G3"]
```
