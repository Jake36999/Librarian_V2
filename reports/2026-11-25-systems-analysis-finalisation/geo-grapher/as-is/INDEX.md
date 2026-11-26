# Geo-Grapher — as-is pack

How Geo-Grapher builds, publishes and serves the library's graphs today, and how agents query them. weaknesses.yaml records what goes wrong; where a weakness is the Geo-Grapher side of a Librarian one, it names the Librarian id.

[Use case diagram](use-case-diagram.md) · [Composition](composition.md) · [States](states.md) · [Canvas](index.canvas)

## Use cases

| Id | Use case | Status | Nodes | Steps | Paths | Tier-0 turns (main / worst) | Weaknesses | Handles | Errors | Warnings |
|---|---|---|---|---|---|---|---|---|---|---|
| UC-G4 | [federated-search](views/federated-search.views.md) | `IMPLEMENTED_VERIFIED` | 17 | 7 | 4 | — | 2 | 0 | 0 | 0 |
| UC1d | [graph-building](views/graph-building.views.md) | `IMPLEMENTED_VERIFIED` | 36 | 18 | 11 | — | 12 | 0 | 0 | 0 |
| UC-G3 | [query-graph](views/query-graph.views.md) | `IMPLEMENTED_VERIFIED` | 15 | 6 | 4 | — | 2 | 0 | 0 | 0 |

Not drawn yet: UC-G5 Compare (deferred: diff-graphs, clone-report, drift-report, merge, copy-graph, delete-graph: not on the Librarian's path); UC-G6 Explore a graph in the 3D workspace (deferred: the person's UI; not on the Librarian's path); UC-G7 Build graphs of the Owner's own projects (deferred: ingest-graphs, ingest-workspace, init-workspace: outside folder review).

## Root causes

| Theme | What goes wrong | Weaknesses | Handled |
|---|---|---|---|
| **GT1 Rebuild instead of change** | A change copies or rebuilds everything near it, and nothing old is ever removed. | G-BLD-01, G-BLD-03, G-BLD-06, G-BLD-07, G-BLD-12, G-GEN-01 | 6 of 6 |
| **GT2 Status says more than was done** | Complete is recorded over parse failures, empty papers and half-committed loops. | G-BLD-02, G-BLD-05, G-BLD-08 | 3 of 3 |
| **GT3 Two stores, no stored link** | The paper graph and the library cannot point at each other, so they drift apart. | G-BLD-09, G-BLD-10, G-BLD-11 | 3 of 3 |
| **GT4 Durability** | Writes are not checkpointed. | G-BLD-04 | 1 of 1 |
| **GT5 Graphs stay islands** | Nothing connects one graph to another except a person's hand. | G-FED-01, G-FED-02 | 2 of 2 |
| **GT6 The agent interface answers too much or nothing** | Listing returns everything; a large item returns nothing. | G-QRY-01, G-QRY-02 | 2 of 2 |

## Weakness register

Every weakness found in the as-is, and the to-be element that handles it.

| Id | Kind | In | Weakness | Handled by |
|---|---|---|---|---|
| G-BLD-01 | cost | `graph-building` | Every folder accept loops serially over every reviewed group in the library, under a 14,400-second timeout. | `graph-building` |
| G-BLD-02 | fault | `graph-building` | Parse failures (a missing tree-sitter grammar, bad UTF-8, TypeScript) are logged, and the snapshot still publishes status complete. | `graph-building` |
| G-BLD-03 | cost | `graph-building` | Each build appends a full, unpruned snapshot: 30 graphs use 77.2 GB, up to 19.5 GB for one documentation graph. | `graph-building` |
| G-BLD-04 | risk | `graph-building` | The code stores and the catalogue are written without a WAL checkpoint. | `graph-building` |
| G-BLD-05 | fault | `graph-building` | A failed build ends in an opaque GEOGRAPHER_CALL_FAILED, while the groups earlier in the loop may already be committed. | `graph-building` |
| G-BLD-06 | cost | `graph-building` | Each paper publication copies the whole previous paper database into a new generation and deletes nothing: 96 copies take 873 MB for one 16 MB database. | `paper-import` |
| G-BLD-07 | cost | `graph-building` | Each PDF is published by a cold-start CLI subprocess. | `paper-import` |
| G-BLD-08 | gap | `graph-building` | Publication is recorded complete with no check of claims or concepts: 12 unread papers have 0 claims, and 72 have 0 concepts. | `paper-import` |
| G-BLD-09 | drift | `graph-building` | 48 published papers have no accepted Source note: the graph and the library disagree about what is in the library. | `paper-import` |
| G-BLD-10 | gap | `graph-building` | A paper is published only into an active reviewed folder group whose reviewed roots hold the original, so a source added without folder review is never published. | `paper-import` |
| G-BLD-11 | gap | `graph-building` | The import receipt returns a document count, not the new document's id, so neither side can store a link between the paper and its source. | `paper-import` |
| G-BLD-12 | risk | `graph-building` | The disk reserve grows with twice the previous paper database, so as generations pile up, publication will be refused (DISK_RESERVE). | `paper-import` |
| G-FED-01 | gap | `federated-search` | No bridges exist: bridges are only declared by hand, and the bridge candidates Geo-Grapher computes are read-only. | `federated-search` |
| G-FED-02 | risk | `federated-search` | With no global rank, relating one graph's results to another's is left to the agent. | `federated-search` |
| G-GEN-01 | cost | `state:paper-generation` | A superseded or failed generation is retained forever; nothing ever deletes one. | `state:paper-store` |
| G-QRY-01 | cost | `query-graph` | list_graphs answers with every graph and its snapshot; an agent that needs only the labels gets them from the Librarian, not from Geo-Grapher. | `query-graph` |
| G-QRY-02 | gap | `query-graph` | An item larger than the connection's limit is refused outright, with no pointer to a smaller part of it. | `query-graph` |

17 weaknesses: 17 handled by the to-be, 0 open with a reason, 0 not yet answered.

## Checks

Errors (0):

Warnings (0):
