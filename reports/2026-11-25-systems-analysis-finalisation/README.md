# Systems analysis of the Librarian and Geo-Grapher

25 November 2026. The approach is to map each system as it is, find where it goes wrong, and then design a preferred version that handles every use case, edge case and failure mode. Each graph comes from a spec, is checked, and records its weaknesses (as-is) or what it handles (to-be). There are no swim-lane canvases (D1).

| Pack | Use cases | Weaknesses | Status |
|---|---|---|---|
| [Librarian, as-is](librarian/as-is/INDEX.md) | 18 | 54, in ten root causes ([findings](librarian/AS-IS-FINDINGS.md)) | `IMPLEMENTED_VERIFIED` / `_OBSERVED`, code at `d9435e1` |
| [Librarian, to-be](librarian/to-be/INDEX.md) | 22 (7 more mapped, not drawn) | 51 handled; 3 open with reasons ([handles](librarian/to-be/handles.yaml)) | `PROPOSED_UNACCEPTED` |
| [Geo-Grapher, as-is](geo-grapher/as-is/INDEX.md) | 3 (3 deferred) | 17, in six root causes ([register](geo-grapher/as-is/weaknesses.yaml)) | `IMPLEMENTED_VERIFIED`, code at `e71967a` |
| [Geo-Grapher, to-be](geo-grapher/to-be/INDEX.md) | 4 | all 17 handled ([handles](geo-grapher/to-be/handles.yaml)) | `PROPOSED_UNACCEPTED` |

**Correction round, 26 November** (after ChatGPT's review):
- **The process catalogue is restored** as [`catalogue`](librarian/to-be/views/catalogue.views.md) (UC8.2). It covers reuse, the layer rule as accepted, the manifest against the mandate, the Oracle's dry run, the duplicate check, the Owner's acceptance into the repertoire, and storage in the Core with the digest pinned.
- **New checked tables:**
  - the [data contract](librarian/to-be/data-contract.md) (Medallion and DIK, kept distinct from Geo-Grapher's trust tiers);
  - [authority](librarian/to-be/authority.md) (permissions against reserved decisions, reconciling tier 0's authority with the policy, and the risk levels that say who holds a decision when no tier 0 oversees the run);
  - [ticket routing](librarian/to-be/ticket-routing.md);
  - performance baselines for the [Librarian](librarian/to-be/performance.md) and [Geo-Grapher](geo-grapher/to-be/performance.md);
  - Geo-Grapher's [incremental safety cases](geo-grapher/to-be/incremental-safety.md).
- **Two open gaps closed:** a ticket for each quarantined sibling, and the person's draft kept through a stale revision.
- **Other changes:** the Oracle now checks unchanged children by their receipts' hashes, and pack specs no longer point to themselves.
- **All four packs pass with no warnings.** [VALIDATION.md](VALIDATION.md) says what that does and does not prove.
- **Handoff review** (same day): fifteen fixes for bounded retries, reachable paths, complete handoffs, rechecks, a single owner for drafting remedies, and Geo-Grapher's receipt contract. They are listed at the end of the [adversarial review](ADVERSARIAL-REVIEW.md).
- **Second pass** (DeepInfra readers and reviewers, 19 calls, $0.83 of the $5 allowed):
  - The [regression matrix](REGRESSION-MATRIX.md) traces 224 checked requirements from the 20–24 November research, designs and graphs: 210 preserved, 12 deferred on the record, 2 rejected with evidence, none unresolved.
  - The [adversarial review](ADVERSARIAL-REVIEW.md): 56 findings with verbatim quotes, 39 accepted (23 changes), 17 rejected with reasons.

**Coverage and the weave, 26 November** (the Owner asked for improvements, the human and tier-0 use cases, Geo-Grapher woven in, and CI/CD pathways):
- **Improvements found and made:**
  - an unquoted comma had split Geo-Grapher's UC-G5 name into a stray key in both packs. The renderer now refuses unknown use-case keys, and it caught a second one while this round was being written;
  - cite-graph checked whether Geo-Grapher was connected after its search had already succeeded, a branch that could never fire. It is gone;
  - folder-review read a degraded parse from inside a success receipt; Geo-Grapher's own partial outcome now carries it.
- **Two missing use cases, now drawn:**
  - [UC9 Decide the agenda](librarian/to-be/views/agenda.views.md): where every held decision lands under the risk rule. Each is decided once, recorded as the person's, re-screened if its inputs changed, and its run resumes at its recorded point. It costs no tier-0 turn from the Web UI and one through chat;
  - [UC0.4 Delegate a task](librarian/to-be/views/delegate.views.md): tier 0's own read-only work through `delegate` and `dispatch_plan`. The Core plans waves within the effort cap instead of refusing a long list, and tier 0 spends two turns.
- **[Who starts each use case](librarian/to-be/initiators.md):** the person, tier 0 for the Owner, tier 0 for an external project, a schedule, or a parent process. It maps the eight MCP session purposes; five run today with no to-be flow and are listed as UC11 to UC15 (add_project, suggest, start_pursuit, tutoring, add_capability), with search-and-read (UC10) and scheduled pipelines (UC16).
- **[Geo-Grapher woven in](librarian/to-be/weave.md):** every Librarian call to Geo-Grapher is now a reference to the Geo-Grapher to-be process it runs. The renderer checks that the Librarian handles each of that process's outcomes:
  - folder review to graph-building;
  - publication to paper-import;
  - citing and placing findings to query-graph;
  - comparing projects to federated search;
  - delegation's packets to query-graph.
- **[Stage contracts and CI/CD pathways](librarian/to-be/stages.md):** MCP sessions already declare each phase's tools and exit gate; the batch's nine stages share one flat tool grant. The table proposes one stage contract (tools, entry, exit gate, receipt, recipe, risk) and eight CI and CD checks. These include a pack check (none runs in CI today), a reports-only path, tool-to-stage coverage, a Geo-Grapher receipt schema tested in both repositories, and hosted CI for Geo-Grapher, which has none.

**Each pack holds:**
- **G1** a use case diagram;
- **G2** the composition of processes;
- **G3** for each use case, the four views: Mermaid activity diagram, written use case, decision tree, and test cases with boundary values;
- **G4** state diagrams;
- an index and an index canvas.

Weaknesses link to their evidence, and as-is and to-be use cases pair by id.

## Reading order

1. [The Librarian's findings](librarian/AS-IS-FINDINGS.md): ten root causes, each with the rule the to-be must meet.
2. The two Librarian indexes, side by side. The as-is index's root-cause table counts how much of each cause the to-be handles.
3. Geo-Grapher's root causes:
   - **GT1 rebuild instead of change**: full snapshots, a full database copy per paper, nothing ever pruned; 77.2 GB for 30 graphs;
   - **GT2 status says more than was done**: complete over parse failures and empty papers;
   - **GT3 two stores, no stored link**: 48 published papers have no Source note;
   - **GT4 durability**: no WAL checkpoint;
   - **GT5 graphs stay islands**: no bridges;
   - **GT6 an agent interface that answers too much or nothing**.

## What is open

- **Owner decisions** (Librarian):
  - may a person's own surface skip the Broker (`W-ACT-05`);
  - correct the attester on the 96 notes of 20 November (`W-ACC-04`).
- **Owner decision, from the authority table:** whether to delegate any reserved decision (such as sensitivity review in the test vault) to tier 0. That would change the policy.
- **Not drawn yet, from the initiators table:** UC10 to UC16 (search and read, the five session purposes with no to-be flow, and scheduled pipelines).
- **Proposed, not built:** the stage contracts and the eight CI and CD pathways in the [stages table](librarian/to-be/stages.md). Each is a code or CI change that needs its own task.
- **Closed 26 November, from the catalogue:** same-layer components. Composition rule 1 (policy) allows a process "of its own kind without a cycle" at every layer, and policy outranks the accepted layer table.
- **Decisions the performance tables leave open:** retention numbers, the concurrency cap (the rule that reading is capped within a stage is settled; the number is not), the target rate for folder descriptions.
- **Decided 26 November:** an unlicensed repository is treated the same as any external source. Its licence status is a label, never a gate: licence status alone no longer holds a folder (`folder-review:dfolderauth`), while scope, linked content, sensitivity and reserved decisions still can. Work that uses an external source cites it; that is a provenance rule applied when the work is written, not a block on ingestion. The [ingest sequence by source kind](librarian/to-be/source-kinds.md) shows how a repository and a document differ: their units, their relations, the graph each feeds. A repository's functions and classes are symbols on its module records (at most 25 each, in `dik.py`); records of their own are marked as a proposed expansion.
- **Decided 26 November: high risk stays with the person when no tier 0 oversees the run.** The [authority table](librarian/to-be/authority.md) now gives each gate a risk level and says who holds it when no tier 0 oversees: a high-risk decision (gates 1 and 2, starting a batch, a code change, an uncovered bridge) is held on the Owner's agenda, never passed down to a Lead, unless a standing policy the Owner set covers it. To cut tier 0's tokens and turns, routine and bounded items are counted in the handover rather than asked, a reserved decision goes straight to the Owner's agenda (the catalogue's wider radius no longer costs tier 0 two relay turns), and the Core alerts the Owner and tier 0 at once on a critical fault.

**Decided 26 November, after the implementation plan's review:**
- **The packs map the current system,** and what makes its processes unreliable; the build hardens the existing code. The to-be [builds-on table](librarian/to-be/builds-on.md) names, for each to-be mechanism, the module it extends. It flattens duplicates, such as the to-be's agenda and the existing `agenda` tool.
- **The tier order is Lead 1, Scribe 2, Clerk 3,** as the code has it; the names imply the hierarchy. The packs had it reversed since 25 November.
  - Every lane is renamed by its tier: the tier-2 lanes are the Scribe's, the tier-3 lanes the Clerk's.
  - Four tier-2 lanes do what the code's Clerk does today, so they move to the Clerk (tier 3): claim verdicts, folder screening, and two title drafts.
- **A connected folder is the person's decision:** it is open to that library's agents, and no classification revokes it (policy, agent-roles-and-authority).
- **The 24 November activation map is a superseded record.** Its canonical copy, `librarian/as-is/activation`, already holds the folder path, the folder-to-Source bridge and the paperclip workflow. Edits belong there.

## Out of scope of these packs (deferred, on the record)

The [regression matrix](REGRESSION-MATRIX.md) found requirements that these process packs do not draw. They are deferred here explicitly, each with where it belongs:
- **The diagram-workflow tooling itself:** lens-pack acceptance and lens provenance, problem statements as a required field, and canvas approval and adoption. These are the diagram-workflows proposal's phases P0–P5. The canvas rules are already enforced by the W2 canvas service, which writes the index canvases.
- **Repository boundaries:** no dependency on the retiring MARK XLVIII harness. This is a constraint on the codebase, not a process.
- **Implementation defects reported on 24 November, not drawn as processes:**
  - Geo-Grapher's dependency relations for Python functions;
  - graph search when repository ids are omitted;
  - conversions persisting a source graph;
  - code repositories attached read-only, never opened as libraries.

  Each needs its own check against the code before it is drawn, or fixed.
- **Decisions D2–D4** in [PLAN.md](PLAN.md):
  - archiving superseded specs;
  - the size limit, applied here at 40;
  - sequence diagrams, none drawn yet.
- **Wording: done.** The 14 to-be specs inherited from 24 November were reworded in plain language: 325 titles, problem statements, labels and guards, with structure, ids and reference outcomes unchanged ([`tools/s4_plain_language.py`](tools/s4_plain_language.py) holds the old-code-to-meaning key).
  - Model names were taken out of the labels. The Oracle and Doctor were assigned GLM-5.3 on 24 November; that assignment is revisable and is not part of the design.
- **S6, your review** of the four packs.

## How to regenerate

```powershell
.venv\Scripts\python.exe reports\2026-11-25-systems-analysis-finalisation\render_pack.py --all
```

`--check` writes nothing, and fails if any view is older than its spec. [CANONICAL.md](CANONICAL.md) records which spec replaced which. `tools/` holds the one-off scripts that did S1 and the splits.
