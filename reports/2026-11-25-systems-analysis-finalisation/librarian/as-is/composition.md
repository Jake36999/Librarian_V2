# Process composition: librarian/as-is

Which process calls which (`kind: ref`). Roots: `activation`, `add-capability`, `add-project`, `compose`, `doctor`, `ingestion`, `oracle`, `research`, `scheduled-pipeline`, `search-and-read`, `start-pursuit`, `study-topic`, `suggest`.

```mermaid
flowchart TD
  acceptance["acceptance<br/>UC1.3"]
  activation_external_project["activation-external-project<br/>UC0.2"]
  activation["activation<br/>UC0"]
  add_capability["add-capability<br/>UC15"]
  add_project["add-project<br/>UC11"]
  batch_enrichment["batch-enrichment<br/>UC1b"]
  cite_graph["cite-graph<br/>UC4"]
  compose["compose<br/>UC8"]
  doctor["doctor<br/>UC-D"]
  folder_review["folder-review<br/>UC1.1"]
  ingestion["ingestion<br/>UC1"]
  oracle["oracle<br/>UC-O"]
  paper_publication["paper-publication<br/>UC1c.3"]
  research["research<br/>UC2"]
  scheduled_pipeline["scheduled-pipeline<br/>UC16"]
  search_and_read["search-and-read<br/>UC10"]
  source_enrichment["source-enrichment<br/>UC1c"]
  source_intake["source-intake<br/>UC1.2"]
  source_parse["source-parse<br/>UC1c.1"]
  source_reading["source-reading<br/>UC1c.2"]
  start_pursuit["start-pursuit<br/>UC13"]
  study_topic["study-topic<br/>UC14"]
  suggest["suggest<br/>UC12"]
  verify_claims["verify-claims<br/>UC3"]
  workflow_run["workflow-run<br/>UC8.1"]
  activation --> acceptance
  activation --> activation_external_project
  activation --> batch_enrichment
  activation --> folder_review
  activation --> source_intake
  activation --> workflow_run
  add_capability --> source_intake
  batch_enrichment --> source_enrichment
  ingestion --> acceptance
  ingestion --> batch_enrichment
  ingestion --> folder_review
  ingestion --> source_intake
  research --> cite_graph
  research --> verify_claims
  source_enrichment --> paper_publication
  source_enrichment --> source_parse
  source_enrichment --> source_reading
```
