# Adversarial review

26 November 2026. Two DeepInfra reviewers from different model families attacked the corrected packs:
- `Qwen/Qwen3.5-397B-A17B`;
- `XiaomiMiMo/MiMo-V2.6-Pro`, run with thinking off after its first attempt spent its whole reply on reasoning.

Each was given the pack digest, the README and the as-is findings, and asked for gaps, unhandled edge cases, authority leaks, contradictions and unsupported claims, each with a verbatim quote. A script checked every quote, and Claude triaged every finding. The receipts are under `tmp/second-pass/out/` (git-ignored); the instruction is `tmp/second-pass/adversarial-instruction.md`.

**Outcome:** 60 findings. 4 were discarded for quotes that are not verbatim. Of the other 56, 39 were accepted and 17 were rejected, each with a reason. Many accepted findings repeat each other (both reviewers found the route-collision and held-claim gaps); together they led to the 23 changes below. MiMo rated all 30 of its findings "high", so severities are not compared.

## Changes made

| Finding | What changed |
|---|---|
| Qwen A4, A13, A22; MiMo A9, A10, A20, A30: a route collision or an unavailable Oracle had no owner or re-run | `oracle:collision` opens a ticket for the Owner to assign or restore a distinct route, and the output is held. `oracle:droute` now asks whether a route is available. The ticket-routing row names the Owner and the re-run. |
| Qwen A5; MiMo A5, A6, A22: a held claim had no owner | `verify-claims:hold` opens a ticket for the Lead (rewrite, drop, or re-review); a routing row was added |
| Qwen A11: a published paper with no stored link had no owner | Routing row: the Doctor re-links it from the publication receipt |
| Qwen A12; MiMo A16: queued external leads and staged external sources had no decider | `activation-external-project:queueasync` goes to the Lead's agenda; `queuepause` names the Owner, or tier 0 under its own commission |
| Qwen A15: other groups' references to what changed | Incremental-safety row: links are resolved when read, and the receipt lists changed entities for their dependants |
| Qwen A18: a cycle in the sprint's manifest | `compose:compile_manifest`: a cycle is refused before anything runs |
| Qwen A20: a child receipt whose hash does not match | `oracle:tiera`: a mismatch re-checks that child in full |
| Qwen A25: the to-be has no workflow-run counterpart | UC8.1 is recorded in the to-be `pack.yaml`, mapped to the `activation-web-ui` steps that carry it |
| Qwen A28: pruning before retention is decided | Incremental-safety row: nothing is pruned until the numbers are decided |
| Qwen A2; MiMo A11, A25: "never prompted" read as covering reserved decisions | `policy_note`: never prompted *for a permission*; reserved decisions are agenda items |
| Qwen A7: a failure inside the Doctor's own steps | Routing rule: it is a critical ticket for tier 0 |
| Qwen A10: research's escalation had no recipient | `research:e_escalated`: tier 0 and the Owner are told |
| MiMo A1, A19: the Lead deciding a folder whose sensitivity its Clerk judged | `folder-review:leadfolder` decides only folders screened as not sensitive; a sensitivity flag goes to the Owner |
| MiMo A2: an agent accepting a flagged item | `acceptance:leadaccept`: a sensitivity flag or a low-confidence draft goes to the Owner |
| MiMo A12: agent acceptance needs promotion mode agent | `leadaccept` requires the Owner to have set it; the authority row says only the Owner sets it |
| MiMo A4, A21: one unmet output paused the whole ingestion | New `ingestion:holdunmet`: only the unmet items are held, each with its ticket, and the clean items go on to acceptance |
| MiMo A13: the topic question asked inside the envelope | `source-intake:stage` queues a topic proposal on the agenda instead |
| MiMo A23: keeping a challenged claim was not drawn | `verify-claims:challenge`: the Lead rewrites the claim, or proposes keeping it with a rebuttal that only the Owner can accept |
| MiMo A24: the Owner's unanswered budget question | `research:askonce`: the session parks at its resume point until it is answered |
| MiMo A8, A18, A26: a declined ticket had no owner | `doctor:haltdecline`: assigned to the Owner, with a review date |
| MiMo A14, A15: retained partials and unmet tasks had no owner | `source-enrichment:retpartial` puts each on the agenda with its owner; routing row added |
| MiMo A28: a quarantined sibling whose remedy cannot run | Routing row: a ticket whose remedy is unavailable goes to the Owner, or to the Lead when no reserved decision is needed |
| Several: no deadlines anywhere | Routing rule and ticket state: every open ticket and agenda decision has an owner and a review date; past it, the item is raised to the next owner. The dates are a decision. |

## Rejected, with the reason

| Finding | Why rejected |
|---|---|
| Qwen A1 | Misread: tier 0 under a commission *starts* the batch; the "no" is the external-project column |
| Qwen A3 | The performance row already calls the 2-turn figure a model figure until a run shows it |
| Qwen A6 | Conflates code-only folders (checked by `oraclefinal`) with publication's folder prerequisite (W-PUB-02) |
| Qwen A8 | `folder-review:doctorroot` is a reference whose declined and escalated outcomes are both handled |
| Qwen A9 | Each quarantined sibling now has a ticket (`source-intake:qticket`) |
| Qwen A14, A16 | The parent handles the gap and the failure (`source-enrichment:pubgap`, `retpartial`) |
| Qwen A17 | A kept draft blocks nothing, so it needs no timeout |
| Qwen A19 | The routing table says what the Lead does with an unmapped failure |
| Qwen A21 | A brief that cannot compile its manifest does not start (`research:dbrief`) |
| Qwen A27 | Misread: the folder row covers only folders that are not sensitive |
| Qwen A29 | A refused import is recorded by the Librarian's `pubgap` without closing the requirement |
| MiMo A3, A27 | "Hold or defer all" is the Owner's own choice; a held reserved decision goes to `queueagenda` without blocking |
| MiMo A7 | The Doctor asks only when the Owner is present; otherwise the ticket goes to the agenda (`downeravail`) |
| MiMo A17 | `acceptance:dgate2` routes an external project away from acceptance |
| MiMo A29 | `batch-enrichment:activate` records who commissioned and decided the batch |

## Discarded (quote not verbatim)

Qwen A23, A24, A26 and A30.

## Handoff review (26 November)

A focused subset from ChatGPT and Gemini, checked against the specs and the policy before the hand-back to the main workflow. Every item was confirmed in the specs and fixed by [`tools/s6_handoff_fixes.py`](tools/s6_handoff_fixes.py); the packs still pass with no warnings.

| Finding | Fix |
|---|---|
| `paper-import` retried a compare-and-set conflict without checking the second result | `dretry`: a second mismatch is refused, with nothing written |
| `source-reading` had no retry edge for the parts that failed | `dpoison` re-reads only the failed parts, at most twice (the number is a decision); after that the part is partial or the item fails. Boundary values added. |
| `research` could loop on challenged or refused claims | `dredraft`: at most two redrafts per claim, then `dropclaim` drops it as a stated gap with its ticket, and the report goes on. A held claim now does the same instead of pausing the brief. |
| The Librarian's publication refused a missing folder before Geo-Grapher's own-papers-group fallback could run | `paper-publication:dpub` publishes into the folder's group or the library's own papers group; only a disabled Geo-Grapher stops it. W-PUB-02 is now handled in the Librarian's own to-be. |
| `compose` chose the specification's owner, then the context, separately | `dctx` routes by the specification's recorded owner and never switches context; its guards are conditions on that record, not a second choice |
| `catalogue`'s layer-rule repair bypassed its revision limit | `x2` now goes through `d3`, the two-revision limit |
| `ingestion` sent a code-only folder to a final check that expects a ledger | `codeledger` records the code-only ledger first; `oraclefinal` checks either notes or applied groups against it |
| `ingestion` could send an empty set to acceptance when every item was held | `dclean`: with nothing clean, it goes to the partial record with the held items' tickets |
| A held folder decision paused the whole ingestion | `heldfolders` puts the held folders on the agenda and goes on with the others. A held acceptance, or a stage-only scope, still ends the run held, because nothing else is left to do. |
| The Web UI's repair rejoined at the review gate, and the partial promotion skipped the Oracle | The Web UI's Doctor now serves only findability and rejoins at `oracleverify`; the partial promotion goes through `oracleverify` too, and `dkind` branches after it. A batch escalation is shown at once, because the batch's own Doctor has already tried. |
| The citation's missing-link ticket had no repair | `cite-graph:ref_doctor` re-links from the publication receipt and rejoins at `resolve` |
| The drafting of a remedy for an unmapped failure was assigned three ways | One owner, as the policy says: the Lead owns the ticket, the Clerk scouts, the Doctor drafts (`doctor:draftprop`) and never installs, and the Lead puts the draft to the Owner (`learn:a2`). Tier 0 gets only code changes. The routing table and UC-L agree. |
| Geo-Grapher's receipt needed `changed_entity_ids` for the Librarian to propagate staleness | `graph-building:receipt` carries them, with the parser version. `folder-review:markstale` consumes them. The new [receipt contract](geo-grapher/to-be/receipt-contract.md) names each field's consumer. |
| Federation decisions had no outcome | `federated-search:ddecide`: accepted or rejected, the rejection recorded; the authority table adds accepting a bridge as reserved, unless a standing policy covers its kind |
| The data contract's "Oracle checks" included a Core check | Each check is now labelled Core (deterministic) or Oracle |

The table check now also resolves references across systems (`librarian/to-be/...` from a Geo-Grapher table), and fails on one that does not exist.
