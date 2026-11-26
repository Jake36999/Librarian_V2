# Process composition: librarian/to-be

Which process calls which (`kind: ref`). Roots: `agenda`, `compose`, `delegate`, `learn`, `research`.

```mermaid
flowchart TD
  acceptance["acceptance<br/>UC1.3"]
  activation_external_project["activation-external-project<br/>UC0"]
  activation_overseer["activation-overseer<br/>UC0"]
  activation_web_ui["activation-web-ui<br/>UC0"]
  agenda["agenda<br/>UC9"]
  batch_enrichment["batch-enrichment<br/>UC1b"]
  catalogue["catalogue<br/>UC8.2"]
  cite_graph["cite-graph<br/>UC4"]
  compose["compose<br/>UC8"]
  delegate["delegate<br/>UC0.4"]
  doctor["doctor<br/>UC-D"]
  folder_review["folder-review<br/>UC1.1"]
  ingestion["ingestion<br/>UC1"]
  learn["learn<br/>UC-L"]
  oracle["oracle<br/>UC-O"]
  paper_publication["paper-publication<br/>UC1c.3"]
  research["research<br/>UC2"]
  source_enrichment["source-enrichment<br/>UC1c"]
  source_intake["source-intake<br/>UC1.2"]
  source_parse["source-parse<br/>UC1c.1"]
  source_reading["source-reading<br/>UC1c.2"]
  verify_claims["verify-claims<br/>UC3"]
  activation_external_project --> doctor
  activation_external_project --> ingestion
  activation_overseer --> doctor
  activation_overseer --> ingestion
  activation_web_ui --> batch_enrichment
  activation_web_ui --> doctor
  activation_web_ui --> ingestion
  agenda --> doctor
  batch_enrichment --> doctor
  batch_enrichment --> source_enrichment
  cite_graph --> doctor
  geo_grapher_to_be_query_graph["geo-grapher/to-be/query-graph (the other system)"]
  cite_graph --> geo_grapher_to_be_query_graph
  compose --> activation_external_project
  compose --> activation_overseer
  compose --> activation_web_ui
  compose --> catalogue
  delegate --> geo_grapher_to_be_query_graph
  delegate --> oracle
  folder_review --> doctor
  geo_grapher_to_be_graph_building["geo-grapher/to-be/graph-building (the other system)"]
  folder_review --> geo_grapher_to_be_graph_building
  ingestion --> acceptance
  ingestion --> batch_enrichment
  ingestion --> doctor
  ingestion --> folder_review
  ingestion --> source_intake
  oracle --> doctor
  geo_grapher_to_be_paper_import["geo-grapher/to-be/paper-import (the other system)"]
  paper_publication --> geo_grapher_to_be_paper_import
  research --> cite_graph
  geo_grapher_to_be_federated_search["geo-grapher/to-be/federated-search (the other system)"]
  research --> geo_grapher_to_be_federated_search
  research --> geo_grapher_to_be_query_graph
  research --> oracle
  research --> verify_claims
  source_enrichment --> doctor
  source_enrichment --> paper_publication
  source_enrichment --> source_parse
  source_enrichment --> source_reading
```
