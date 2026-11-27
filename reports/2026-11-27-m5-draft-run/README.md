# M5 folder-draft run: the fixed test folder, drafts approved (27 November)

The `ingest-folder` pipeline ran on the fixed test folder with its new draft step and the real Clerk. The folder is `E:\DataManagement\03-Retrieval-Routing-and-Graph-Query-Systems`: 8 PDFs, which survey into 3 folder cards. The Owner asked for this run on 27 November ("Real-folder draft run").

**Result:**
- **Drafts:** all 3 non-excluded cards were described, which is 100% against M5's 90% floor. Each had its sensitivity checked and found normal, with no silent failure.
- **Decisions:** all 3 were then decided by policy acceptance, with nothing held and no tickets.
- **Capture:** the 8 documents were queued and captured, and the ledger reconciles.
- **Cost:** $0.0071 in 102 seconds. Drafting itself was 6 calls, under $0.001.

## How it was run

- **Library:** a new one at `G:\Librarian-work\m5-draft-run\library` (title "M5 Draft Run").
  - The Owner's settings for this throwaway library: promotion mode `agent`, and `[folders] production_drafting = true`, which is the approval of the real Clerk route for drafts.
  - Budget ceiling: $1.
- **Geo-Grapher:** the 0dcfb9a wheel in its separate runtime, as in the M5 acceptance run.
- **Models:** DeepInfra `google/gemma-4-26B-A4B-it` as Clerk and Scribe, through the Core's per-route profile gate. The key was loaded into the run's process only.
- **Calls:** one `run_pipeline ingest-folder` with `approve_folder_drafts: true`, through `App.person_call`, with the vault writer live. The batch was not started.
- **Script:** `G:\Librarian-work\m5-draft-run\run.py`. Its summary is in [data/summary.json](data/summary.json): counts, paths and the Clerk's descriptions, with no source content.

## What it showed

| Card | Suggested (Geo-Grapher) | Clerk's description | Sensitivity | Decided |
|---|---|---|---|---|
| `.` | own-current | "The inventory contains 8 files, all of which are .pdf files, with a total size of 15,254,667 bytes." | normal | policy, own-current |
| `baseline` | research-docs | "The inventory contains a folder named 'baseline' with 3 files, all of which are .pdf files, totaling 5,575,174 bytes." | normal | policy, research-docs |
| `external` | third-party | "The inventory contains 5 files located in the external path, all of which are .pdf files, totaling 9,679,493 bytes." | normal | policy, third-party |

- **Accurate descriptions:** each states only what the inventory holds, and each passed the provenance check against the card's own counts. The Clerk is sent folder metadata only.
- **The ledger:** 3 surveyed, 3 accepted, 8 documents queued, and 8 sources staged with none unaccounted. Its next step: "8 staged source(s) wait for approval into the batch" (the person's).
- **Model calls:** 46 Clerk calls in all, $0.0071.

| Task | Calls | Cost |
|---|---|---|
| Folder drafts (`folder_brief`) | 3 | $0.00008 |
| Sensitivity checks (3 folders and 8 documents) | 11 | $0.00103 |
| Capture's description tasks (`points`, `limits`, `bottom_line`, `terms`) | 32 | $0.0060 |

## For the Owner

**The root card was accepted as `own-current`, the owner's own current work.**
- Geo-Grapher suggested `own-current` for the root `.` of a folder of third-party papers, and policy acceptance accepts a suggestion as it stands: "nothing is changed from its suggestion", by the Owner's rule of 15 November.
- Every file sits in `baseline/` or `external/`, which have their own decisions, so no document is labelled owner-created here.
- In the M5 acceptance run, the person decided the same card as third-party.

**Decided by the Owner, 27 November:** keep it, "as long as no conflicts arise from any changes to the content of the folder".

A check then found that a conflict could arise:
- a file added directly to the root re-staged the root card, and policy acceptance re-accepted it as `own-current`, so the new file was taken as the owner's own work, silently;
- the same path replaced a person's decision after its folder's content changed.

Both are now held for the person, with a ticket: a decision that rested on its decided subfolders alone does not extend to new files in the root, and a person's decision is never replaced. A paper added to a policy-decided reference folder is still accepted by policy, as before. The fix is in `folder_review.accept_by_policy` and `tests/test_m5_planted.py`; the rule is in `docs/policy/agent-roles-and-authority.md`.

## Not covered

- The batch, which is the person's to start and was covered by the M5 acceptance run.
- A folder the Clerk finds sensitive, and a failed draft, on real data. Both are covered by the planted cases with a scripted Clerk.
- A larger folder. The floor's denominator here is 3 cards.
