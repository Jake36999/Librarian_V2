# Librarian V2 Current Activation & To-Be Diagrams (`diagrams/`)

This directory holds **9** validated specifications obeying the accepted `render_spec.py` (`DOC-MAP-05`, `DOC-PLN-03`) four-view convention with **zero `_at_` clone nodes** inside canonical `.spec.yaml` files:
- **1 Current-State Activation Map (`IMPLEMENTED_VERIFIED`, commit `d9435e1`):** `librarian-current-activation` (links via `kind: ref` to preserved [batch-enrichment-current.canvas](../../2026-11-21-enrichment-baseline/batch-enrichment-current.canvas) and [source-enrichment-current.canvas](../../2026-11-21-enrichment-baseline/source-enrichment-current.canvas); leaves historical `DataManagement` [ingestion.canvas](../../2026-11-20-workflow-map/examples/ingestion/ingestion.canvas) unmodified).
- **8 Proposed To-Be Specifications (`PROPOSED_UNACCEPTED`):** `librarian-process-composition-tobe`, `librarian-context1-tier0-delegated`, `librarian-context2-external-project-mcp`, `librarian-context3-human-platform-ui`, `librarian-ingestion-tobe`, `librarian-batch-enrichment-tobe`, `librarian-source-enrichment-tobe`, and `librarian-doctor-tobe`.

## Process Call Hierarchies

```text
Current Activation (`IMPLEMENTED_VERIFIED` d9435e1):
  librarian-current-activation ──(ref: main batch)──> batch-enrichment-current ──(ref)──> source-enrichment-current
                               └──(ref: UI deep-read)──────────────────────────────────> source-enrichment-current
  (Historical DataManagement cohort trace preserved separately at reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas)

Proposed To-Be Family (`PROPOSED_UNACCEPTED` — NOT accepted/implemented):
  librarian-process-composition-tobe (actor-laned L3 Sprint -> L0 Action narrowing)
    ├──(ref: Context 1)──> librarian-context1-tier0-delegated   ──(ref)──> librarian-ingestion-tobe
    ├──(ref: Context 2)──> librarian-context2-external-project-mcp ─(ref)─> librarian-ingestion-tobe
    └──(ref: Context 3)──> librarian-context3-human-platform-ui ──(ref)──> librarian-batch-enrichment-tobe / librarian-ingestion-tobe
                                                                                  │
                                                                                  ├──(ref)──> librarian-source-enrichment-tobe
                                                                                  └──(ref)──> librarian-doctor-tobe (Ticket R1-R6)
```

## Validated Diagram Inventory (9 Models)

| Model | Status | Steps | Scenarios | Nodes | Edges | Overlaps | Edge Crossings | PNG Overflows | Spec `_at_` Clones | In-Memory Tail Locs | Artifacts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `librarian-current-activation` | `IMPLEMENTED_VERIFIED` | 11 | 30 | 61 | 77 | 0 | 0 | 0 | 0 | 1 | [spec](librarian-current-activation.spec.yaml) · [views](librarian-current-activation.views.md) · [canvas](librarian-current-activation.canvas) · [png](librarian-current-activation.png) · [notes](librarian-current-activation.md) |
| `librarian-doctor-tobe` | `PROPOSED_UNACCEPTED` | 6 | 13 | 38 | 36 | 0 | 0 | 0 | 0 | 2 | [spec](librarian-doctor-tobe.spec.yaml) · [views](librarian-doctor-tobe.views.md) · [canvas](librarian-doctor-tobe.canvas) · [png](librarian-doctor-tobe.png) |
| `librarian-source-enrichment-tobe` | `PROPOSED_UNACCEPTED` | 21 | 23 | 73 | 77 | 0 | 0 | 0 | 0 | 3 | [spec](librarian-source-enrichment-tobe.spec.yaml) · [views](librarian-source-enrichment-tobe.views.md) · [canvas](librarian-source-enrichment-tobe.canvas) · [png](librarian-source-enrichment-tobe.png) |
| `librarian-batch-enrichment-tobe` | `PROPOSED_UNACCEPTED` | 10 | 21 | 51 | 55 | 0 | 0 | 0 | 0 | 3 | [spec](librarian-batch-enrichment-tobe.spec.yaml) · [views](librarian-batch-enrichment-tobe.views.md) · [canvas](librarian-batch-enrichment-tobe.canvas) · [png](librarian-batch-enrichment-tobe.png) |
| `librarian-ingestion-tobe` | `PROPOSED_UNACCEPTED` | 20 | 43 | 73 | 97 | 0 | 0 | 0 | 0 | 3 | [spec](librarian-ingestion-tobe.spec.yaml) · [views](librarian-ingestion-tobe.views.md) · [canvas](librarian-ingestion-tobe.canvas) · [png](librarian-ingestion-tobe.png) |
| `librarian-context1-tier0-delegated` | `PROPOSED_UNACCEPTED` | 9 | 16 | 49 | 49 | 0 | 0 | 0 | 0 | 0 | [spec](librarian-context1-tier0-delegated.spec.yaml) · [views](librarian-context1-tier0-delegated.views.md) · [canvas](librarian-context1-tier0-delegated.canvas) · [png](librarian-context1-tier0-delegated.png) |
| `librarian-context2-external-project-mcp` | `PROPOSED_UNACCEPTED` | 8 | 12 | 41 | 40 | 0 | 0 | 0 | 0 | 0 | [spec](librarian-context2-external-project-mcp.spec.yaml) · [views](librarian-context2-external-project-mcp.views.md) · [canvas](librarian-context2-external-project-mcp.canvas) · [png](librarian-context2-external-project-mcp.png) |
| `librarian-context3-human-platform-ui` | `PROPOSED_UNACCEPTED` | 12 | 23 | 46 | 52 | 0 | 0 | 0 | 0 | 0 | [spec](librarian-context3-human-platform-ui.spec.yaml) · [views](librarian-context3-human-platform-ui.views.md) · [canvas](librarian-context3-human-platform-ui.canvas) · [png](librarian-context3-human-platform-ui.png) |
| `librarian-process-composition-tobe` | `PROPOSED_UNACCEPTED` | 9 | 22 | 42 | 50 | 0 | 0 | 0 | 0 | 0 | [spec](librarian-process-composition-tobe.spec.yaml) · [views](librarian-process-composition-tobe.views.md) · [canvas](librarian-process-composition-tobe.canvas) · [png](librarian-process-composition-tobe.png) |

## Preserved Baseline Canvases (Unmodified SHA-256 Verified)

| Canvas | SHA-256 | Status |
|---|---|---|
| `reports/2026-11-20-workflow-map/examples/ingestion/ingestion.canvas` | `0a0b1af08f1ae2553ed4e0927d162ab60068ab1f9e2c612c949c7e6c737485b5` | Unmodified (`preserved_unchanged: true`) |
| `reports/2026-11-21-enrichment-baseline/batch-enrichment-current.canvas` | `eb5a5bb6533d2d5c3ad93b0c98e36150deabd68bfe22856c439cd8e082d7fe2b` | Unmodified (`preserved_unchanged: true`) |
| `reports/2026-11-21-enrichment-baseline/source-enrichment-current.canvas` | `5b050a3e80351e5a47d347f04d59e63d5cad9fae0abf43649ca499a7c3d6d76b` | Unmodified (`preserved_unchanged: true`) |
| `reports/2026-11-21-enrichment-baseline/enrichment-cycle.canvas` | `8108dcd9dd9bfcecf6dc0dfd724c6cf00075d2cc8104d6590faf5aedd6157a6c` | Unmodified (`preserved_unchanged: true`) |

## Validation Scope & Limits

- **What validation establishes:** Every model passes structural validation (`render_spec.validate`), cross-view guard/step numbering (`render_spec.cross_check`), cross-diagram outcome parity across all 9 local specs plus external `batch-enrichment-current` and `source-enrichment-current` (`render_spec.check_references`), actor-lane and Core/agent ownership checks, fail-closed `ORACLE_ROUTE_COLLISION` checks, SHA-256 baseline canvas preservation, 2D canvas non-overlap & edge/card intersection checks (`0` overlaps, `0` intersections), overview PNG text-fit checks (`0` clipped labels), and spec purity (`0` `_at_` clones on disk).
- **What validation does NOT establish:** The 8 to-be diagrams remain **`PROPOSED_UNACCEPTED`** targets — static checks do **NOT** constitute Owner acceptance, do **NOT** prove runtime Ticket/Oracle/Doctor implementation, and do **NOT** execute live Web UI, MCP, Broker, `record_application`, Geo-Grapher, or DeepInfra behaviour (`new_library_model_calls: 0`).

Machine-checked summary: [validation.json](validation.json) · Companion Policy & Behaviour Report: [05-policy-and-behaviour-reconstruction.md](../05-policy-and-behaviour-reconstruction.md).
