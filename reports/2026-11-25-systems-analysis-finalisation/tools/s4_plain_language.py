"""S4: plain-language pass over the to-be specs inherited from 24 November (Owner, 25 November).

    python tools/s4_plain_language.py

Only wording changes: titles, problem statements, node labels and decision guards. Node ids, steps,
edges, extension numbers and reference outcomes are untouched, so handles.yaml and every check still
hold. Codes are replaced by what they mean:
  Rule 8   a compensation is shown with the ticket, never run automatically
  Rule 9, 16   a sub-run is never wider than its parent; reserved decisions are the Owner's
  Rule 12  the run's receipt
  Rule 15  the permission envelope, approved once
  Rule 17  the Oracle judges an ungranted call against the specification before anyone is asked
  MC-10    the budget reserved before each dispatch
  NAT-13   the receipts of work already done, reused
  OD-05    the open Owner decision on sensitivity and challenged-claim exceptions
  F-01 / F-02 / F-03   the staging pager / the run's checkpoint / the 150 s and 600 s permission waits
  L0-L3    action, workflow, pipeline, sprint;  Context 1/2/3   tier 0 / an external project / the Web UI
  W3, W5, W8   blast radius, bridges, titles and topics;  E4/E5   the grounding checks
  Bronze / Silver   captured evidence / staged records;  DIK   the structured Data records
Model names (GLM-5.3) are dropped from labels: an assignment is revisable and not part of the design.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from split_spec import load, save  # noqa: E402

PACK = Path(__file__).resolve().parents[1] / "librarian/to-be"
NOTE = "Plain-language pass by tools/s4_plain_language.py (S4, 2026-11-25); structure unchanged."

COLLISION = "no Oracle route distinct from the workers' (never marked as independently reviewed)"

REWORD = {
    "acceptance": {
        "nodes": {
            "leadaccept": "accepts the in-scope sources and folder cards, recorded as accepted by an agent with their flags kept; defers the reserved ones",
            "promote": "commits the accepted sources through the guarded writer, indexes them, and hands any undecided candidates on",
        },
        "guards": {
            ("dgate2", "leadaccept"): "within tier 0's commission, or a standing agent policy",
            ("dgate2", "dgate2caller"): "outside it: an external project may not accept, the Web UI person reviews, a taxonomy change, or a reserved decision",
            ("dgate2caller", "e_held_for_the_Owner"): "no person present (an external project or a scheduled run)",
        },
    },
    "activation-external-project": {
        "title": "Work for an external project through MCP (proposed)",
        "problem": {
            "symptom": "As-is: delegation refused at the external project's tier, permission asks timing out, acceptance authority confused with the other contexts, and Applications/ notes that record no authorship or locators.",
            "root": "An external project gets a scoped grant: a reading budget, checked third-party access, intake that only queues or stages, no acceptance, and Applications/ notes written by the agent and stored by the Core.",
        },
        "nodes": {
            "mcpenv": "records the external project as the specification's owner, and enforces its helper budget, third-party checks and stage-only intake (no acceptance)",
            "mcpblocked": "returns a structured ticket at once (unanswered, tier or scope), not a 150-second wait",
            "notifyblocked": "tells the external project's user exactly what authority or route is missing, and how to resume",
            "userpause": "receives the pause, its ticket and the agenda link to resume it",
            "reusedapp": "confirms the catalogued sources are unchanged and a matching Applications/ note exists, at no new spend",
            "parallelhelpers": "runs the delegated reading within the helper budget: the Lead sets a narrower sub-task, Clerks and Scribes do it",
            "queueasync": "queues the unresolved sources for the library's staging, without holding up the external work",
            "ingestchild": "stages the missing sources through a stage-only intake the Lead runs, narrower than the grant and with no acceptance",
            "applypartial": "applies the partial evidence it holds in the external project, and records the unresolved leads and spend",
            "queuepause": "keeps the staged sources on the library's agenda for a person, or tier 0, to accept; returns how to resume",
            "doctorex": "attempts a bounded repair of the MCP or intake ticket",
            "escticket": "routes the critical ticket at once, with its flags, evidence and the compensation shown",
            "notifyesc": "alerts the external project's user at once, with the ticket and the evidence kept",
            "useresc": "receives the urgent failure notice and the ticket's link",
            "recordapp": "validates the citations, stores the append-only Applications/ note with its locators, and queues the unresolved sources",
            "eescalated": "a critical MCP or intake ticket escalated; the user is told",
        },
        "guards": {
            ("dmissing", "queueasync"): "missing sources: queue them for later (the default for an external project)",
            ("dmissing", "ingestchild"): "missing sources, and the grant allows staging them",
        },
    },
    "activation-overseer": {
        "title": "Work for the Owner as tier 0 (proposed)",
        "problem": {
            "symptom": "As-is: tier 0 is refused the curate tier, stalls on hidden 150- and 600-second permission asks, is asked to approve twice, and has to watch low-value steps.",
            "root": "The Owner's instruction and scope are the commission: tier 0 approves the permission envelope once on the Owner's behalf, delegates the work to the Lead and the shared pipeline, and hands back one receipt.",
        },
        "nodes": {
            "commission": "writes the sprint's specification on the Owner's behalf and approves its permission envelope once, with no second ask",
            "t0cancel": "reports the rejected commission and what needs clarifying, with nothing spent",
            "storeenv": "stores the specification and its mandate (commissioned by the person, decided by the agent) and grants the delegated in-scope permissions",
            "policy_note": "Proposed: full in-scope delegation to tier 0. Sensitivity and challenged-claim exceptions stay flagged for the Owner (an open Owner decision).",
            "leaddispatch": "owns the delegated pipeline run, never wider than its parent, and routes work to Clerks and Scribes",
            "callingest": "runs the shared ingestion pipeline, its batch and each source's workflow, under the commission",
            "partbranch": "weighs the permitted partial coverage and spend against the sprint's acceptance criteria",
            "partnotify": "tells the Owner the coverage, spend, what was not examined, the deferred decisions and the open tickets",
            "reusehand": "packages the reused receipts and the unchanged source list, at no spend",
            "t0notifyreuse": "tells the Owner nothing changed, with the evidence hashes and no duplicate spend",
            "t0ticket": "records a paused ticket (its id, flags, spend and resume point): out of scope, budget, a library-wide change, or a reserved decision",
            "t0surface": "puts one structured question to the Owner (a boundary, a reserved decision or a route collision) with where to resume",
            "collisionrec": "records the review as unverified, with a ticket: " + COLLISION,
            "doctortriage": "attempts a bounded repair of the sprint's ticket",
            "reentrydoc": "checks the repair's progress and prepares the Oracle's independent recheck",
            "declinerec": "keeps the declined ticket, its attempts and the compensation shown on the agenda",
            "t0decline": "reports the open ticket, the declined remedy, the spend and the compensation shown",
            "escrec": "routes the critical ticket at once, with its flags, evidence hashes and the compensation shown",
            "failnotify": "alerts the Owner at once with the critical ticket, evidence, spend and state",
            "useresc": "receives the urgent failure alert and the ticket's link",
            "oraclesprint": "audits the sprint's obligations on a route distinct from the workers'",
            "dverdict": "are the sprint's obligations met?",
            "packagereceipt": "commits the delivery receipt: accepted notes, spend, coverage, deferred decisions, tickets and agenda",
            "t0deliver": "writes the final handover: evidence, spend, coverage, deferred work, review status and tickets",
            "userpartial": "receives the permitted partial report, what was not examined and the open tickets",
            "userdecline": "receives the open ticket, the declined remedy and the compensation plan",
            "e1": "the sprint is done; the Owner has the Oracle-verified evidence and the agenda",
            "epartial": "done with permitted partials; the Owner has what was not examined and the tickets",
            "epaused": "paused on a boundary, a hazard, a route collision or a declined commission; the Owner is told",
            "eescalated": "a critical ticket escalated with its evidence; the Owner is alerted at once",
        },
        "guards": {
            ("dcrit", "doctortriage"): "a mapped, non-critical shortfall",
            ("dverdict", "collisionrec"): COLLISION,
        },
    },
    "activation-web-ui": {
        "title": "Work directly in the Web UI (proposed)",
        "problem": {
            "symptom": "As-is: staging filters hide accepted and processing items, a background reload wipes the person's edits, a workflow's result is dropped (app.js:8472), and unfindable notes and queued Clerk work are invisible.",
            "root": "The Web UI starts the same parent processes with no tier 0; each decision (source, summary, folder, lens, topic, index) is separate and explicit, and every result is shown from the Core's record.",
        },
        "nodes": {
            "leaddeleg": "delegates a multi-folder Chat request, never wider than the person's own authority, with no tier 0",
            "wgrant": "grants the person's workflow, with the read access its steps need",
            "uicapture": "captures the evidence and records the staging and folder items, at the person's curate tier",
            "leadcoord": "oversees the queued work started from the UI, within the person's authority, and shows queued Clerk work",
            "clerkdraft": "proposes a readable title, a neutral Bottom Line, what the source solves, its fields (Unknown where unsupported), topics and sensitivity",
            "reviewgate1": "reviews the staged sources with their evidence beside them, and ticks or edits the Gate 1 items",
            "uidispose": "defers the item, or quarantines a rejected one, with the reason and the originals kept",
            "startbatch": "clicks Process approved; the selected batch is frozen",
            "batchchild": "runs the mixed batch under the person's start",
            "uidoctor": "attempts a bounded repair of the UI or batch ticket (for example, re-indexing)",
            "uireentry": "confirms the repaired ticket and refreshes Staging and Search",
            "reviewgate2": "makes the Gate 2 choices: the summary (Bottom Line, redraft, unknowns), then folders, lenses, topics and offerings",
            "promotepartial": "writes the Source note with partial coverage and what was not examined, and updates the indexes",
            "promoteindex": "checks the staged revision, writes the Source note through the guarded writer and indexes it",
            "oracleverify": "verifies the summary's integrity and the note's findability, on a route distinct from the workers'",
            "uinotify": "shows the result banner and a drawer with the run's result, spend and coverage, and the agenda",
            "uireused": "shows that nothing new was needed, with the unchanged catalogue links and no spend",
            "uiagenda": "updates the agenda and staging filters, and shows the workflow or ticket notice with its resume path",
            "userpaused": "receives the paused ticket, any unverified-review flag, the spend and where to resume",
            "uiesc": "shows the critical error at once, with the ticket, flags, evidence and the compensation shown",
            "useresc": "receives the urgent failure alert, the ticket and the compensation plan",
            "eescalated": "a critical UI or index ticket shown to the person with its evidence",
        },
        "guards": {
            ("dgate2choice", "promotepartial"): "accept with partial coverage (what was not examined is recorded)",
            ("dindex", "uidoctor"): "not findable, or embedding warnings",
            ("dindex", "uiagenda"): COLLISION,
        },
    },
    "batch-enrichment": {
        "title": "Run the approved batch (proposed)",
        "problem": {
            "symptom": "As-is: batches ran outside a session, checked the budget only before each item, drafted folders twice, and were repaired without an Oracle's check.",
            "root": "Record what started the batch, reuse the receipts of work already done, reserve the budget before each dispatch, gate the result with the Oracle, and let the Doctor repair once.",
        },
        "nodes": {
            "activate": "records the batch's mandate (narrower than its parent), who owns it, the run's checkpoint and who commissioned and decided it",
            "useradmit": "takes the person's own Process approved selection",
            "t0admit": "validates tier 0's commission (or a scoped stage-only grant), recorded as decided by an agent",
            "bind": "owns the delegated batch run, never wider than its parent",
            "admit": "validates the session's checkpoint, the frozen selection and the role routes",
            "controls": "checks cancellation and the writer lease, and reserves the item's budget before dispatching it",
            "source": "runs one source's enrichment under the shared commission and its budget",
            "fval": "validates the folder card: the survey digest, access and sensitivity flags",
            "froute": "checks the folder drafting grant, reuses the intake receipt, and reserves the budget",
            "fdata": "checks the folder's provenance arithmetic by script and writes its Data record",
            "account": "updates the batch ledger with coverage, spend and the worklists",
            "oracle": "verifies the batch ledger and its spend on a route distinct from the workers', and opens tickets on faults",
            "reentry": "checks the Doctor's single repair receipt",
            "pausehandoff": "returns the pause (cancelled, budget reached, or " + COLLISION + ") as a ticket, with its state kept",
            "epaused": "paused: cancelled, a reserved grant, the budget reached, or no distinct Oracle route",
        },
        "guards": {
            ("dtrigger", "t0admit"): "tier 0, under a commission or a scoped stage-only grant",
            ("dcontrols", "dkind"): "the controls allow it and the budget is reserved",
            ("dcontrols", "pausehandoff"): "cancelled, or the budget is reached",
            ("dfroute", "fdata"): "scripted, or an intake receipt reused",
            ("dverdict", "pausehandoff"): COLLISION,
        },
    },
    "compose": {
        "title": "Compose and start a sprint (proposed)",
        "problem": {
            "symptom": "The earlier model used the composition layers as swim lanes, and left out who owns each specification, the Oracle's scope judgment and the handovers to the person.",
            "root": "Compose strictly action, workflow, pipeline, sprint across the real actors; name each specification's owner; keep every sub-run within its parent; let the Oracle judge scope; hand over to the person.",
        },
        "nodes": {
            "init": "starts work as tier 0's instruction, an external project over MCP, or directly in the Web UI",
            "dspec_owner": "who owns the sprint's specification?",
            "t0_spec": "writes the sprint's specification on the Owner's behalf and approves its permission envelope",
            "c2_spec": "sets the external project's specification within its bounded read-and-apply grant",
            "c3_spec": "sets the specification of the person's own Web UI work, with no tier 0",
            "compile_manifest": "checks the order action, workflow, pipeline, sprint has no cycle, and compiles the manifest and the permission envelope",
            "dnarrow": "does the sub-run's manifest stay within its parent's mandate, reserved decisions included?",
            "lead_subspec": "writes the delegated pipeline and workflow specifications, only within the parent's mandate",
            "oracle_scope": "judges an ungranted call against the sprint's specification before anyone is asked",
            "log_allowance": "records the allowance and its evidence for the end-of-run report",
            "dctx": "which context runs the sprint?",
            "ctx1": "tier 0's sprint: the Lead runs the ingestion",
            "ctx2": "the external project's sprint: delegated reading and applying, optionally staging",
            "ctx3": "the person's Web UI sprint: curation, then the batch or the ingestion, with no tier 0",
            "oracle_rollup": "verifies the rolled-up obligations of every layer and the allowances made, on a route distinct from the workers'",
            "dor_comp": "are the composed obligations met?",
            "rollreceipt": "stores the run's receipt: provenance at every layer, spend, coverage, deferrals, tickets and agenda",
            "outpartial": "stores the partial outputs, spend, coverage gaps and open tickets",
            "userpartial": "receives the permitted partial report, what was not examined, the spend and the open tickets",
            "outpause": "stores the pause as a ticket with where to resume: a reserved decision, the budget, or no distinct Oracle route",
            "userpaused": "receives the paused ticket, the spend and state so far, and where to resume",
            "outesc": "routes the critical ticket at once, with its full trace and the compensation shown",
            "useresc": "receives the critical failure alert, the ticket and the compensation plan",
            "e1": "the composition is done, every sub-run within its parent, and the person is told",
            "epartial": "done with permitted partials; the open tickets are reported",
            "ereused": "nothing new needed at any layer, with no duplicate spend",
            "epaused": "paused cleanly on a reserved decision, the budget or a route collision",
            "eescalated": "a critical or unresolved ticket escalated at once to the person and the specification's owner",
        },
        "guards": {
            ("dspec_owner", "t0_spec"): "tier 0, working for the Owner",
            ("dspec_owner", "c2_spec"): "tier 0, working for an external project",
            ("dspec_owner", "c3_spec"): "the person, in the Web UI",
            ("dnarrow", "oracle_scope"): "an ungranted call: the Oracle judges its scope",
            ("dscope", "outpause"): "it would widen the parent's mandate, or needs a reserved decision",
            ("dctx", "ctx1"): "tier 0's commission",
            ("dctx", "ctx2"): "an external project",
            ("dctx", "ctx3"): "the Web UI",
            ("dor_comp", "outpause"): COLLISION,
            ("dor_comp", "outesc"): "a critical integrity finding at any layer",
        },
    },
    "doctor": {
        "title": "Repair a failure through a ticket (proposed)",
        "problem": {
            "symptom": "The earlier doctor rolled compensation back automatically, used a helper role, had no activation or ticket routing, and blocked unattended runs on the Owner.",
            "root": "A structured ticket (extension, flags, owner, repair history), only accepted remedies within a computed blast radius and the Doctor's limits, routing that never blocks the caller, compensation shown not run, and the Oracle's recheck.",
        },
        "nodes": {
            "intake": "records the ticket: the extension, tiered flags, evidence hash, accountable actor, repair history, the Oracle it needs, and the mandate",
            "dtrigger": "who raised the ticket?",
            "userdoc": "takes the Owner's own repair request from the Web UI",
            "t0doc": "takes tier 0's commission or an external project's scoped grant; in-scope remedies run, and nothing widens it",
            "scout": "scouts the unmapped defect read-only and attaches its findings to the ticket",
            "draftprop": "drafts a new remedy on the ticket; it never installs or runs it",
            "blast": "computes the blast radius against the parent's mandate: at most 3 recovery steps and 2 paid calls",
            "dgrant": "within the parent's mandate and the Doctor's limits?",
            "askowner": "asks the Owner for the reserved scope, with the exact blast radius",
            "runremedy": "runs the accepted remedy in an isolated context",
            "checkrepair": "reruns the deterministic checks, records the changed hashes on the ticket, and checks the repair ran apart from the workers",
            "showcomp": "attaches the compensation plan and the failed attempt to the ticket; it is shown, never run automatically",
            "oracle": "confirms the cleared ticket on a route distinct from the workers', switching reviewer on a collision",
            "closeresolved": "marks the ticket resolved, with its repair history, the Oracle's pass and the notice to the caller",
            "haltdecline": "keeps the ticket open (declined or deferred) with its evidence, the compensation and an agenda notice",
            "haltescalate": "routes the critical ticket at once, with its flags, hashes and the compensation shown",
        },
        "guards": {
            ("dgrant", "runremedy"): "within the blast radius and the Doctor's limits",
            ("dgrant", "haltescalate"): "a critical security, data-loss or boundary violation (at once)",
            ("doracle", "showcomp"): "the recheck failed, or no distinct Oracle route (never marked resolved)",
        },
    },
    "folder-review": {
        "nodes": {
            "rootinv": "surveys the roots, fingerprints, licences and exclusions at no cost, reusing the folder receipts already held",
            "doctorroot": "attempts a scoped repair of a stale root or a lost route, once",
            "reentryroot": "checks the single repair's progress",
            "dfolderauth": "is the folder decision within tier 0's commission or a standing policy?",
            "leadfolder": "decides the in-scope folders under the commission or standing policy, and applies the exclusions",
            "doctorgeo": "repairs the group or the service through a ticket, without rebuilding the library",
        },
        "guards": {
            ("dfolderauth", "leadfolder"): "within the commission, or a standing policy for non-sensitive folders",
            ("dfolderauth", "dheldcaller"): "outside it: the person in the Web UI, an external project's out-of-scope folder, unlicensed or linked content, or a reserved decision",
            ("dheldcaller", "e_held_for_the_Owner"): "no person present (tier 0 over MCP, an external project, a scheduled run): put it on the agenda without blocking",
            ("dgeo", "doctorgeo"): "the folder is stale, or a mapped Geo-Grapher fault",
            ("dgeo", "oraclecov"): "parse coverage is degraded (some files skipped)",
        },
    },
    "ingestion": {
        "title": "Make a folder of documents into Source notes (proposed)",
        "problem": {
            "symptom": "The earlier draft hid three different callers behind one trigger, gave the Owner seven main-path steps and three serial acceptance prompts, could block an external tier 0 at curate, and skipped the final Oracle check on code-only folders.",
            "root": "Take a mandate from any caller that never widens its parent; delegate routine screening and acceptance to the Lead, the Oracle and the Doctor; consolidate acceptance into one decision; end with one of five outcomes and its tickets.",
        },
        "nodes": {
            "admit_mandate": "admits the ingestion's mandate, its owner, budget and who commissioned it; it never widens its parent",
            "leadbind": "owns the ingestion run and its permission envelope, never wider than the parent",
            "queueagenda": "puts the reserved decision, or the external project's hold, on the agenda as a ticket without blocking the caller",
            "startrun": "the Lead approves within the grant; the Core checks the run's checkpoint and freezes the mixed batch",
            "ledger": "reconciles one paged ledger for the folder, and separates the folder, source, lens, topic and bridge lists",
            "oraclebatch": "screens the batch's outputs, partial gaps and Geo-Grapher receipts on a route distinct from the workers'",
            "doctorbatch": "repairs the partial or unpublished items through a ticket, on the affected subset only",
            "reentrybatch": "merges the checked repair into the ledger (one attempt)",
            "oraclefinal": "verifies findability, neutrality and the ledger on a route distinct from the workers'",
            "doctorphase": "repairs findability, or another mapped shortfall, through a ticket",
            "deliver": "packages the Oracle's verdict, evidence hashes, spend, coverage, deferred decisions and tickets",
            "recorddelivery": "stores the final receipt: spend, coverage, deferrals and the handover",
            "recordpartial": "stores the partial coverage, spend, deferred items and open tickets",
            "notifypartial": "receives the partial result, what was not examined, the spend and the tickets to resume",
            "reuseout": "reconciles the reused and excluded inputs, with no batch dispatched and nothing spent",
            "pauseout": "returns the held gate, a route-collision ticket or a refusal, with the spend and where to resume",
            "escout": "routes the critical or unresolved ticket at once, with its flags, hashes and the compensation shown",
            "epartial": "a permitted partial, or a deferred worklist, returned with its gaps and tickets",
            "epaused": "paused: a reserved decision, stage-only scope, the budget, or no distinct Oracle route",
            "eescalated": "an unresolved critical integrity ticket escalated",
        },
        "guards": {
            ("dgate1", "startrun"): "within tier 0's commission, or the person's own start",
            ("dgate1", "dgate1caller"): "an external project's stage-only scope, or waiting for the person's start",
            ("dgate1caller", "queueagenda"): "no person present (an external project or a scheduled run)",
            ("dbatchscreen", "pauseout", "ORACLE_ROUTE_COLLISION"): COLLISION,
            ("dbatchscreen", "escout"): "a critical security, data-loss or integrity violation",
            ("doracle", "pauseout", "ORACLE_ROUTE_COLLISION"): COLLISION,
        },
    },
    "paper-publication": {
        "nodes": {"pubreceipt": "requires claims for a multi-page PDF, and checks for bridges to propose"},
        "guards": {("dpubok", "e_gap"): "an empty paper graph, or a late refusal"},
    },
    "source-enrichment": {
        "title": "Enrich one source (proposed)",
        "problem": {
            "symptom": "As-is: part counts hid failed whole-source passes, budget checks only before each item let inner calls leak, and papers with no claims passed silently.",
            "root": "Record what started the work, reuse what is already done, reserve the budget before each dispatch, check the whole-source derivations, quarantine poison text, require claims from Geo-Grapher, and never block mid-loop on the Owner.",
        },
        "nodes": {
            "bind": "binds the source and its workflow's mandate (never wider than the parent), and the receipts of work already done",
            "dwork": "what admitted this source's workflow?",
            "userread": "admits the person's reread from the Web UI, under their workflow grant",
            "t0read": "verifies the commission's envelope for this source (tier 0, or an external project)",
            "controls": "checks cancellation and the lease, and reserves the budget before dispatching",
            "pubgap": "records an empty paper graph or a refusal, without closing the requirement",
            "oracle": "audits the raw receipts, the spend and the fidelity of what was read, on a route distinct from the workers'",
            "doctor": "runs the accepted remedy for the ticket",
            "reentry": "checks the single repair and re-admits the source",
            "retpause": "returns the pause: the budget ceiling, cancellation, or " + COLLISION,
            "e1": "the source meets its reading and publication obligations",
            "enowork": "nothing new admitted; the existing receipts are reused",
            "epaused": "paused: cancelled, the budget reached, or no distinct Oracle route",
        },
        "guards": {
            ("dcontrols", "ref_source_parse"): "the controls allow it and the budget is reserved",
            ("dcontrols", "retpause"): "paused, or the budget is reached",
            ("dverdict", "retpause"): COLLISION,
        },
    },
    "source-intake": {
        "nodes": {
            "capture": "captures immutable evidence and literal header or DOI metadata, quarantining failed siblings",
            "describe": "proposes a readable title when the header is a slug or file name, a neutral description, its fields (Unknown where unsupported) and topics",
            "stage": "validates and stages the title, the record and its unknowns; asks for topics if it would be Unfiled",
        },
    },
    "source-parse": {
        "nodes": {
            "validate": "verifies the evidence hash, the route and recipe, and that publication state is current",
            "convplan": "assigns a bounded OCR or cleanup task to a qualified role, within the reserved budget",
            "convchk": "stores the conversion with its authorship, and reconciles the spend",
            "preproj": "marks the provisional paper projection as provisional; it is never counted as published",
        },
    },
    "source-reading": {
        "nodes": {
            "read": "carries out bounded reading and synthesis tasks within the reserved budget",
            "readchk": "verifies each part's schema and quotes, and keeps part reading apart from the whole-source pass",
            "readproof": "reconciles the whole-source pass and the chapter relations",
            "partialread": "keeps the item partial, with its unread parts or missing whole-source pass stated",
            "lenses": "stores the grounded lens candidates, read blind; accepting them is a separate decision",
            "data": "extracts the structural Data records and the static code relations by script, at no cost",
            "metadata": "derives the deterministic facts, validates the proposed fields against the schema, and stores them with the unknowns",
            "review": "drafts a neutral Bottom Line and the sensitivity check, flagging low confidence",
            "reviewchk": "checks the Bottom Line's form, its quotes and the reading counters; a good draft never overrides incomplete reading",
        },
        "guards": {("dread", "lenses"): "every part and the whole-source pass are complete"},
    },
}


# Second pass: labels the first pass left, which read badly as "The <actor> <label>" in the generated
# written use case, or used shorthand (&, +, ->, a/b).
CRITICAL = "a critical security, data-loss or boundary breach, rather than a mapped shortfall?"
MORE = {
    "acceptance": {
        "nodes": {"ownergate2": "the Owner's one consolidated decision: which folders, sources, lenses and topics?"},
        "guards": {("dgate2caller", "ownergate2"): "the Owner is present, in the Web UI"},
    },
    "activation-external-project": {
        "nodes": {
            "checkcatalog": "returns the verified catalogue citations with their handles and the spend, and checks the unresolved leads",
            "dcrit_ex": CRITICAL,
            "reuseingest": "reconciles the reused Source note and links the candidate to the open apply session",
            "userpartial": "receives the external deliverable, its coverage gaps, the spend and the leads queued in the library",
            "extapply": "applies the verified findings in the external project and proposes the Applications/ note it wrote",
            "userhandover": "receives the external deliverable with its locators, the spend, the Applications/ link and the queued leads",
            "userreuse": "receives the library's reused precedent and the unchanged Applications/ link",
            "e1": "the external task is done, with a repeatable Applications/ precedent and any queued leads",
            "epartial": "the external task is done with partial evidence; the leads are queued in the library and the user told",
            "epaused": "the library's grant or gate paused cleanly on the agenda; the external user is told",
        },
        "guards": {
            ("dmode", "parallelhelpers"): "a session authorised to read, delegate and apply",
            ("dmode", "reusedapp"): "the sources are unchanged and an Applications/ precedent exists",
        },
    },
    "activation-overseer": {
        "nodes": {
            "request": "instructs tier 0 with the task, scope, exclusions and budget: the instruction and its scope are the commission",
            "denv": "are the commissioned specification and scope well formed?",
            "dcrit": CRITICAL,
            "userchoice": "decides the boundary, hazard or route exception, and gets the exact place on the agenda to resume",
            "usercancel": "receives the rejected commission and what needs clarifying; the library is unchanged",
            "userack": "receives the completion notice in the chat or IDE session, and the receipt on the agenda",
        },
    },
    "activation-web-ui": {
        "nodes": {
            "ui_entry": "starts in the Web UI: Add source or Folders in Staging, Chat with an attachment, or Run a workflow",
            "duicrit": CRITICAL,
            "dindex": "is the Source note findable, and do its checks pass?",
            "userdone": "receives the accepted Source note, the spend, the index confirmation and the deferred decisions, with no tier 0",
            "uipartial": "shows the partial coverage, the spend, what was not examined and the remaining agenda and staging counts",
            "userpartial": "receives the accepted partial note with its coverage caveats, the spend and the deferred decisions",
            "userreuse": "receives confirmation that the catalogue is unchanged, with its links",
            "e1": "the source is findable in Search and the catalogue; the person is told, with no tier 0",
            "epaused": "the staged, deferred or paused item stays visible in Staging and on the agenda; the person is told",
        },
        "guards": {
            ("dentry", "uicapture"): "Add source in Staging, or Chat with an attachment",
            ("dgate1choice", "startbatch"): "approve for ingestion, then click Process approved",
            ("dgate2choice", "promoteindex"): "accept into the library",
            ("dindex", "uinotify"): "findable, and the checks pass on a distinct Oracle route",
        },
    },
    "batch-enrichment": {
        "nodes": {
            "dfroute": "is folder drafting needed, and permitted?",
            "freview": "reviews the folder summary's organisation and sensitivity",
            "fullhandoff": "hands the verified batch and its separate pending worklists to the parent",
            "partialhandoff": "returns the completed items beside the unmet tickets and partial items",
        },
    },
    "compose": {
        "nodes": {
            "dscope": "is it within the specification and the parent's mandate?",
            "worker_roles": "carries out the assigned interpretation, review and bounded reading and writing over the Core's scripted actions",
            "ctx2": "runs the external project's sprint: delegated reading and applying, optionally staging",
            "ctx3": "runs the person's Web UI sprint: curation, then the batch or the ingestion, with no tier 0",
            "usernotify": "receives the handover: the result's evidence, spend, coverage and deferred work",
            "outreused": "stores the reuse receipt and the links to the existing precedent, with no work redone",
        },
        "guards": {
            ("dscope", "log_allowance"): "within the parent's mandate and the specification",
            ("dscope", "outesc"): "a critical security or data-loss breach",
        },
    },
    "doctor": {"guards": {("drepaired", "showcomp"): "the checks failed, or the step or call limit was reached"}},
    "folder-review": {
        "nodes": {
            "droot": "are the roots current, and the folder route qualified?",
            "folderscreen": "screens only the new or ambiguous folders for purpose, unlicensed third-party risk and sensitivity, without reading documents",
            "folderapply": "submits only the changed or selected group",
            "geoapply": "indexes the changed group incrementally and returns its parse and coverage receipt",
        },
        "guards": {
            ("droot", "folderscreen"): "current, and the route is ready",
            ("droot", "doctorroot"): "a stale root, or the route's qualification lost",
            ("dheldcaller", "ownerfolder"): "the Owner is present, in the Web UI",
        },
    },
    "ingestion": {
        "nodes": {
            "dgate1": "are approving and starting the batch within the mandate?",
            "ownergate1": "approve and start the batch?",
            "startrun": "checks the Lead's approval against the grant and the run's checkpoint, and freezes the mixed batch",
            "batch": "runs the mixed batch of sources and folder cards against the frozen ledger",
            "doracle": "are the parent's obligations and findability met?",
            "notifyowner": "receives the verified result: the catalogued notes, the spend and the deferred work",
            "ereused": "the existing and excluded inputs reconciled cleanly",
        },
        "guards": {
            ("dinput", "oraclefinal"): "code or graph folders only (no Source notes)",
            ("dgate1caller", "ownergate1"): "the Owner is present, in the Web UI",
            ("ownergate1", "startrun"): "approve and start",
            ("doracle", "doctorphase"): "a findability miss, or another mapped shortfall",
            ("dfinalkind", "recorddelivery"): "everything required and optional is clean",
        },
    },
    "paper-publication": {
        "nodes": {"publish": "imports the fully converted paper and returns its claim, concept and error counts"},
        "guards": {("dpubok", "e_success"): "valid, with claims, and bridges checked"},
    },
    "source-enrichment": {
        "nodes": {
            "quarantine": "quarantines the poison item and drops its provisional cache",
            "pubna": "records publication as not applicable: not a PDF, or no full conversion",
            "handback": "returns the verified source, its costs, coverage and the separate worklists to the batch",
            "retpartial": "returns the non-critical partial source, with its unmet tasks and any quarantine stated",
        },
        "guards": {("dwork", "userread"): "the person asked for it (a reread or a revision)"},
    },
    "source-intake": {
        "nodes": {"dcap": "do the capture and the queue reconcile?"},
        "guards": {("dcap", "e_paused"): "every target quarantined or unreachable"},
    },
    "source-parse": {
        "nodes": {
            "parse": "fetches and extracts the text by script (code syntax trees, PDF text) with its page map, keeping the originals",
            "dparse": "what does the parse need: nothing more, a conversion, or does it stop early?",
            "convert": "converts the pages with page anchors, marking what is unread or failed",
        },
        "guards": {("dprov", "preproj"): "a PDF or a paper"},
    },
    "source-reading": {
        "nodes": {
            "host": "answers the task requests on a qualified route, and settles the reserved cost against the actual",
            "dread": "are the part readings and the whole-source derivations complete?",
            "dpoison": "are the bounded retries spent on poison or ungrounded text?",
            "relateskip": "keeps the Core's static code relations, or records chapter relations as not applicable",
        },
        "guards": {("dpoison", "e_failed"): "the retries are spent on ungrounded or poison text"},
    },
}
for _name, _change in MORE.items():
    _into = REWORD.setdefault(_name, {})
    for _part in ("nodes", "guards"):
        _into.setdefault(_part, {}).update(_change.get(_part, {}))


def apply(name: str, change: dict) -> int:
    path = PACK / f"{name}.spec.yaml"
    spec = load(path)
    count = 0
    if "title" in change:
        spec["title"], count = change["title"], count + 1
    if "problem" in change:
        spec["problem"] = {**(spec.get("problem") or {}), **change["problem"]}
        count += 1
    ids = {n["id"]: n for n in spec["nodes"]}
    for nid, label in change.get("nodes", {}).items():
        if nid not in ids:
            raise KeyError(f"{name}: no node {nid}")
        ids[nid]["label"], count = label, count + 1
    for key, guard in change.get("guards", {}).items():
        a, b, needle = (key + (None,))[:3]      # a third item picks one of several edges by its old guard
        edges = [e for e in spec["edges"] if e["from"] == a and e["to"] == b
                 and (needle is None or needle in str(e.get("guard", "")) or e.get("guard") == guard)]
        if len(edges) != 1:
            raise KeyError(f"{name}: expected one edge {a}->{b}, found {len(edges)}")
        if ids[a]["kind"] == "ref":
            raise ValueError(f"{name}: {a}->{b} is a reference's outcome; it must not be reworded")
        edges[0]["guard"], count = guard, count + 1
    save(spec, path, NOTE)
    return count


if __name__ == "__main__":
    total = sum(apply(name, change) for name, change in REWORD.items())
    print(f"reworded {total} titles, problems, labels and guards in {len(REWORD)} specs")
