from pathlib import Path
import re, json, hashlib, shutil, sqlite3

ROOT = Path('D:/Librarian_V2')
OUT = ROOT / 'reports/2026-11-04-master-finalization'
QA = Path('C:/Users/jakem/Documents/Codex/2026-11-04/help-me-set-up-web-app/outputs')
PLAN = 'docs/unified-implementation-plan.md'
MEM = 'reports/2026-11-03-memory-context-review/'
NAT = 'reports/2026-11-04-native-subsystem-review/'
UI = 'reports/2026-11-04-ui-framework-review/'
NAMES = ['01-MASTER-SYSTEM-REPORT.md','02-UNIFIED-REQUIREMENTS-AND-SPECIFICATIONS.md','03-MASTER-FINALIZATION-PLAN.md','04-PLAN-INTEGRATION-SUMMARY.md']

def read(p):
    p = Path(p)
    return (p if p.is_absolute() else ROOT/p).read_text(encoding='utf-8-sig')

def link(p, line=None, label=None):
    p = Path(p)
    if not p.is_absolute(): p = ROOT/p
    target = '/' + p.as_posix()
    if line: target += ':' + str(line)
    return f'[{label or p.name + (":"+str(line) if line else "") }](<{target}>)'

def anchor(p, needle, label=None):
    ls=read(p).splitlines()
    n=next(i for i,l in enumerate(ls,1) if needle in l)
    return link(p,n,label)

def nav():
    return ' · '.join(link(OUT/n,label=n.split('-')[0]+' '+['Report','Specification','Plan','Integration'][i]) for i,n in enumerate(NAMES))+'\n\n'

def table(headers, rows):
    return '| '+' | '.join(headers)+' |\n|'+'|'.join('---' for _ in headers)+'|\n'+''.join('| '+' | '.join(str(c).replace('\n','<br>').replace('|',' / ') for c in row)+' |\n' for row in rows)+'\n'

def source_links(text, source):
    def fix(m):
        label,target=m.groups()
        if target.startswith(('http','/D:','/C:','#')): return m.group(0)
        mt=re.match(r'(.*?)(:\d+)?$',target)
        path=(ROOT/source).parent/mt[1]
        return link(path.resolve(),int(mt[2][1:]) if mt[2] else None,label)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)',fix,text)

# One execution row per accepted synthesis unit. Requirement IDs MC-* and original MEM-* packet IDs remain distinct.
tasks=[]
def task(id,wave,aliases,title,lane,files,deps,done,tests,extra=''):
    tasks.append(dict(id=id,wave=wave,aliases=aliases,title=title,lane=lane,files=files.split(),deps=deps.split(),done=done,tests=tests.split(),extra=extra))

task('MF-001','0','ACCEPT-02','Close original mixed-client acceptance','HOST','reports/2026-10-31-accept02-windows-acceptance.md', '', 'Real Browser, Obsidian 1.12.7 or newly recorded version, and real Claude/Cowork MCP concurrently use one compatible Core in a disposable vault; one lease, ordered writes, valid JSONL, no SQLITE_BUSY, preserved dirty note, close/reconnect a client without replay; record exact candidate hashes and versions. Protocol smoke alone cannot close it.', 'test_mcp.py test_core_mixed_acceptance.py test_obsidian_adapter_contract.py','Installed/real-host gate H; repeat on final artifacts in MF-045.')
task('MF-002','0','REMED-06/08','Reconcile measurement record and uncertain liabilities','DOC','reports/2026-10-30-g5-measurement.md', '', 'Preserve completed pilot and approved task-local timeout policy. Owner reconciles all three uncertain IDs from provider evidence or records still uncertain at full reservation; no automatic refund, rerun or reopening of the completed pilot.', 'test_paid_dispatch.py test_remed08_measures.py','Ledger is read-only for drafting; settlement requires owner evidence/decision, outside this pass.')
task('MF-003','0','BASE-03/04/05; NAT-17','Adopt status/crosswalk and terminology refresh','DOC','docs/unified-implementation-plan.md docs/regression-manifest.md docs/terminology.md docs/handoff-2026-10-31-codex.md', '', 'After master-plan approval, current rows match latest progress entries; old rows explicitly historical; new packets/tests labeled planned; aliases and current release gates reconciled. No completed implementation is requeued.', 'test_source_identity.py','Documentation only; current pass supplies proposed edits in document 04.')
task('MF-004','0','DT-01','Establish current CI acceptance evidence','BUILD','.github/workflows/ci.yml tests/test_keys.py', '', 'Recheck current hosted failures and identify exact failing tests before allocating edits; restore supported Python lanes and retain reports. Export actual branch-rule evidence or record external block; historical red CI is not asserted as current.', 'test_source_identity.py','Exact failing selectors must come from fresh CI, not guessed from review. Provisional file ownership; confirm workflow paths at packet admission.')
task('MF-005','1A','UI-01; G01/G02','Preserve composer and separate Stop','UI','ui/src/main.ts', '', '409 and transport ambiguity retain submitted text/attachments; pending prevents duplicate POST; success clears only its snapshot; Enter while busy never cancels; explicit Stop waits for canonical outcome.', '', 'B: admission/attachment/late-edit/cancel assertions.')
task('MF-006','1A','UI-02; G19','Make mutation feedback truthful','UI','ui/src/main.ts ui/src/panels.ts obsidian/src/main.ts', 'MF-005', 'Failed mode/effort/Forget/clear restores confirmed state and visible error; pending cancellation explicit; checkpoint resolution never retries effects; mount/meta failure offers ordinary retry without takeover.', 'test_obsidian_adapter_contract.py','B; typed stale-lease recovery is the sole takeover path.')
task('MF-007','1A','UI-03; G04/G05','Isolate all owned CSS and DOM tokens','UI','ui/src/style.css ui/src/main.ts ui/src/panels.ts ui/src/chat.ts ui/src/views.ts ui/src/settings.ts ui/src/pane.ts ui/src/markdown.ts ui/src/speech.ts ui/src/attach.ts', '', 'Both CSS directions checked against appendix inventory; every dialog branch rooted; high-collision owned classes and modifiers namespaced across emitters/selectors; foreign dialog unchanged; old model-card fix retained.', 'test_obsidian_adapter_contract.py','B plus generated asset parity; exclusive UI-wide rename lease before other UI changes land.')
task('MF-008','1A','UI-04; UI-05 prerequisite slice; G03','Use root containers and minimum overlay lifecycle','UI','ui/src/style.css ui/src/main.ts ui/src/panels.ts ui/src/pane.ts', 'MF-007', 'Named @container adapts at 320/420/760/1100 widths in a wide window; split is clamped; resize preserves drafts; overlay focus/instance IDs/listener disposal needed by session dialogs exists now. Remaining UI-05 ergonomics stays MF-025.', '', 'B; 420px query >=280px; main >=360px when split fits; short-root height.')
task('MF-009','1A','UI-07; G11/G12','Expose legacy/stale lifecycle','UI','ui/src/chat.ts ui/src/panels.ts', 'MF-008', 'Empty and nonempty legacy histories show read-only banner despite invalid empty string; new audited session is separate; historical results and changed files visible without invented path-to-predicate causality.', 'test_predicate_inspector.py test_closure_lifecycle.py','B uses real disposable Session fixtures, not just mocked business state.')
task('MF-010','1A','UI-08; G13/G14; D3 bridge','Show durable stop reasons and safe revision forms','SESSION','src/resource_librarian/audit_projection.py src/resource_librarian/session.py src/resource_librarian/tools/sessions.py ui/src/chat.ts ui/src/api.ts', 'MF-009', 'reason/source survive projection and session_status restart; text-only revision retains exact predicates/verifier parameters; refusal details and skeleton on demand; fits=false disables admission; no invented CAS for set_requirement.', 'test_audit_projection.py test_admission_usability.py test_predicate_inspector.py','B; shared UI edits integrate under UI lease; bridge uses existing events, not a second log.')
task('MF-011','1B','MEM-01/02; MC-01/02/16','Measure and bound complete provider requests','CONTEXT','src/resource_librarian/loop.py src/resource_librarian/model_invocation.py src/resource_librarian/audit_projection.py', '', 'Post-render system/schema/continuation/history/evidence plus output reserve fit supported route bounds at 50/200 rounds or dispatch parks; protected constraints and tool pairs survive; counters record method/error margin without prompt leakage.', 'test_prompt_size.py test_loop.py test_audit_projection.py test_prompt_layout.py test_openai_chat_adapter.py test_anthropic_messages_adapter.py')
task('MF-012','1B','MEM-03; MEM-12 foundation; MC-03/06/07/14','Make durable references cross restart and worker boundaries','CONTEXT','src/resource_librarian/result_handles.py src/resource_librarian/evidence.py src/resource_librarian/tools/context.py', 'MF-011', 'Durable reference resolves exact bytes after worker exit/Core restart through current authorization; legacy ephemeral handles stay isolated; changed/missing/expired/forbidden/withdrawn are distinct; no handle opens arbitrary files.', 'test_result_handles.py test_evidence.py','New durable cases extend existing target; cross-scope metadata must not leak.')
task('MF-013','1B','NAT-01','Fingerprint deep-read chunks','INGEST','src/resource_librarian/deep_read.py src/resource_librarian/lens_gold.py', '', 'Equal-count edits/reorders invalidate old extraction; text/chunker/representation identity governs reuse; count-only legacy progress is explicitly stale.', 'test_deep_read.py test_lens_gold.py')
task('MF-014','1B','NAT-02','Preserve document chunks through rename','INDEX','src/resource_librarian/index.py src/resource_librarian/document_identity.py', '', 'One transaction reconciles identity/chunks before orphan deletion; unique move preserves IDs/FTS/vectors; edited attachments and ambiguous copies do not cross-attach; unsettled orphan chunks remain non-searchable and recoverable.', 'test_document_identity.py test_core_index_service.py test_embed.py')
task('MF-015','1B','NAT-04; DT-06 quota slice; G18','Qualify disk-backed Docker quotas and admission','EXEC','src/resource_librarian/sandbox.py src/resource_librarian/workbench.py', '', 'Actual Windows/WSL2 backend has verified disk-backed byte/inode enforcement for contained profile, setup/log/export/global caps, digest identity and preflight; unsupported backend refuses. Live rapid-write/tiny-file/concurrent floods meet limits. Polling alone is not a hard quota.', 'test_sandbox.py test_workbench_boundaries.py test_accept_workbench.py','H Docker; no RAM-backed artifact tmpfs, no supervisor daemon. Backend remains a qualification gate, not assumed Docker Desktop capability.')
task('MF-016','1B','NAT-05; DT-06 teardown slice; G18','Stop producers before bounded quarantine export','EXEC','src/resource_librarian/sandbox.py src/resource_librarian/workbench.py src/resource_librarian/claim_run.py', 'MF-015', 'No --rm; idempotent stop/kill plus verified stopped inspect precedes docker cp tar stream into private quarantine; links/escapes/truncation/size/count/depth rejected; cleanup_unknown blocks success; remove only after export disposition.', 'test_sandbox.py test_claim_run.py test_workbench_boundaries.py','H Docker; stdout/stderr and I/O circuit-breakers retain bounded tails and declared overshoot.')
task('MF-017','1B','NAT-06','Pin recursive workflow definition closure','RECIPE','src/resource_librarian/workflows.py', '', 'At start retain all reachable child definitions and route target digests; resume uses pinned bytes or refuses drift; cycle/unknown action rejected; no current-name child substitution.', 'test_workflows.py')
task('MF-018','1B','NAT-07','Reconcile workflow and macro step effects','RECIPE','src/resource_librarian/workflows.py src/resource_librarian/tools/macros.py', 'MF-017', 'Durable intent before dispatch and result after; crashes before/after effects resolve reusable/safe retry/outcome_unknown; mutating default never blindly repeats; Registry/Broker checks and expanded macro approval retained.', 'test_workflows.py test_macro_permissions.py test_operation_recovery.py')
task('MF-019','1B','NAT-11; MC-10 service portion','Serialize service reservations including global TTS','SERVICE','src/resource_librarian/service_routes.py src/resource_librarian/tts.py src/resource_librarian/stt.py', '', 'Two vault Cores share a process-safe personal cap; reserve before send; retries and repairs charged; timeout/late result retains liability; cache/replay settles once; cancellation and error taxonomy retained.', 'test_tts.py test_stt.py test_service_routes.py test_service_adapters.py')
task('MF-020','1B','NAT-13','Bind migration and batch reuse to one byte snapshot','INGEST','src/resource_librarian/v1_export.py src/resource_librarian/batch.py', '', 'Parse and evidence use same immutable read; content/stage/recipe/route identity enters batch key; mutations during waits cannot settle stale output; older completion cannot satisfy changed input.', 'test_v1_export.py test_core_batch.py test_core_source_batch.py')
task('MF-021','2','MEM-04/07; MC-06/07/08/09/10','Structured worker handoff, merge and aggregate budget','CONTEXT','src/resource_librarian/tools/delegate.py src/resource_librarian/loop.py src/resource_librarian/session.py', 'MF-010 MF-011 MF-012 MF-019', 'Bounded typed request/result retains late caveats and evidence; parent reserves before parallel dispatch; current epoch/access/evidence checked at serialized merge; duplicate receipt accepted once; crash/uncertain charge stays unresolved.', 'test_shared_models.py test_effort.py test_session_events.py test_result_handles.py','Add planned tests/test_worker_continuity.py; no writable worker authority.')
task('MF-022','2','NAT-03','Harden existing encoder recovery and counters','INDEX','src/resource_librarian/embed.py src/resource_librarian/promote.py src/resource_librarian/tools/staging.py', 'MF-014', 'Blocked encoder leaves both owners available; operation/source/representation CAS rejects stale completion; crash leaves pending recovery; actual inserted/skipped counts; no direct active-Core fallback.', 'test_core_source_batch.py test_core_index_service.py test_embed.py')
task('MF-023','2','NAT-08; EK-06','Pin claim recipes and qualify environment receipts','EXEC','src/resource_librarian/claim_run.py src/resource_librarian/workflows.py', 'MF-016 MF-017 MF-018', 'Exact commit/tree/image mismatch refuses; latest means new-version test; outputs/input/verifier/environment digests retained; missing prerequisites could-not-run; evidence replay runs nothing.', 'test_claim_run.py test_workbench_boundaries.py')
task('MF-024','2','NAT-09; MC-10 role portion','Correlate Clerk/Scribe/Scout work and receipts','SERVICE','src/resource_librarian/clerk.py src/resource_librarian/scribe.py src/resource_librarian/scout.py src/resource_librarian/tools/staging.py src/resource_librarian/app.py src/resource_librarian/tools/pace.py', 'MF-019 MF-021 MF-022', 'Browser/MCP fallback/batch/worker attribution equivalent; cancellation prevents new inner dispatch; durable effort-log failure explicit; tasks cannot mutate each other limits; Clerk/Scribe prompts remain source-neutral.', 'test_clerk.py test_clerk_routes.py test_effort.py test_e2_effort.py test_role_route_bindings.py')
task('MF-025','2','UI-05/06; G06/G21','Complete focus, keys, tabs, splitter and touch','UI','ui/src/main.ts ui/src/panels.ts ui/src/pane.ts ui/src/settings.ts ui/src/style.css', 'MF-008 MF-010', 'Async overlays focus after load; Escape owned and restores trigger; native modal trap; unique mounts; no leaked listeners; arrow/Home/End tabs and keyboard splitter; touchcancel/drag suppresses clearing; reduced motion respected.', '', 'B and real Obsidian capture-hotkey evidence H. Minimal prerequisite portion already MF-008.')
task('MF-026','2','UI-09; G07/G08/G09/G10','Project operations and derived failures','UI','ui/src/main.ts ui/src/views.ts ui/src/settings.ts ui/src/api.ts', 'MF-006 MF-025', 'SSE separated from writer/index/watcher/leases; accepted Markdown survives visible embedding failure; snapshots never fake progress; failed updates retain last-reported time; polling bounded/nonoverlapping/disposed; offline G5 is not runtime spend.', 'test_app.py','B; general jobs/quarantine-history API remains deferred, not fabricated.')
task('MF-027','2','NAT-10 + UI-10; G15/G16/G17','Bind review evidence and composed staging previews','REVIEW','src/resource_librarian/reply_review.py src/resource_librarian/app.py src/resource_librarian/tools/staging.py src/resource_librarian/promote.py src/resource_librarian/loop.py ui/src/chat.ts ui/src/views.ts ui/src/api.ts', 'MF-012 MF-016 MF-023 MF-024 MF-026', 'reply_id/turn_id, exact path/revision, checked spans and bounded advisory lifecycle exposed; ambiguous basename unchecked; late review stays on original reply. staging_show composes exact preview with original CAS tokens; edits invalidate preview. Docker preflight disables unavailable Claim Run; receipts rendered only when real.', 'test_reply_review.py test_prompt_size.py test_audit_projection.py test_staging_safety.py test_core_source_promotion.py','B; planned tests/test_staging_preview.py; taxonomy preview stays explicitly semantic unless exact prepared bytes are exposed.')
task('MF-028','2','NAT-12','Use common envelopes for PDF/OCR/search','SERVICE','src/resource_librarian/pdf_markdown.py src/resource_librarian/ocr.py src/resource_librarian/websearch.py', 'MF-019 MF-024', 'Raw/cleaned identities distinct, partial page coverage retained; cancel stops new pages; dispatched uncertainty keeps reservation; backend/route identity and error category explicit.', 'test_pdf_markdown.py test_ocr.py test_websearch.py test_core_batch.py')
task('MF-029','2','NAT-14','Reconcile V1 identities, edges, attachments and history','INGEST','src/resource_librarian/v1_export.py', 'MF-020', 'Every fixture edge/attachment is preserved, excluded, transformed or unresolved with reason; aliases/renames/missing targets explicit; partial batches accumulate mappings; V1 unchanged; imported histories never become approvals.', 'test_v1_export.py test_source_identity.py','Add planned tests/test_v1_fidelity.py.')
task('MF-030','2','MC-03/06/09 continuity across MCP','Qualify MCP restart, library switch and handoff boundaries','CONTEXT','src/resource_librarian/mcp_client.py src/resource_librarian/mcp_server.py', 'MF-021 MF-024', 'Core-required constrained RPC retained; revoked access, child restart, server disconnect and library switch cannot leak old handles/results or duplicate accepted effects; outbound tools remain Broker-controlled.', 'test_mcp.py test_mcp_client.py test_mcp_library.py','Owner Windows full suite and H; not a second implementation of CORE-04A.')
task('MF-031','2','UI-11; Settings step 3 model portion','Make model selection role-explicit','UI','ui/src/panels.ts ui/src/settings.ts', 'MF-006 MF-025', 'Lead/Notes/Small tasks selection preserves untouched slots and current override gate; visible clearing truthful about prefix/fallback; service clear never posts tiers; shared-default effects labeled.', 'test_role_route_bindings.py test_app.py','B; no new route authority.')
task('MF-032','2','UI-12; Settings steps 1/2','Build Settings workspace and redistribute controls','UI','ui/src/settings.ts ui/src/main.ts ui/src/style.css', 'MF-025 MF-031', '1120x820 maximum, 224px left rail, ten specified pages and scope labels; root-bound sizing, narrow selector, page-local Save/Cancel and retained edits; Settings and Choose models persist across Chat/Staging/Search.', '', 'B; 420px leaf, short height, two mounts, dirty-close and library-switch cases.')
task('MF-033','2','UI-12; Settings step 3 remainder','Simplify providers, tools and project access','UI','ui/src/settings.ts', 'MF-032', 'Provider summary/detail, separate save key/connection, no automatic paid probe; integration summaries and explicit library permissions; project read/write hierarchy; chat context label and custom length; warnings remain actionable.', '', 'B; existing requests/settings semantics preserved.')
task('MF-034','2','UI-12; Settings step 4; visual Staging/Search','Connect navigation, triage and research surfaces','UI','ui/src/main.ts ui/src/pane.ts ui/src/views.ts ui/src/settings.ts ui/src/style.css', 'MF-027 MF-032 MF-033', 'Note/Browse/Plan/This week view switch separated from note actions and audio; queue/form/evidence readable; empty Plan collapses; bulk defer and approve-for-processing return per-item outcomes, never bulk publish; query full first row, filters second; task/edits/return position retained.', '', 'B; no new bulk endpoint required—bounded existing per-item decisions with current revisions.')
task('MF-035','2','UI-13; Settings verification','Qualify installed shared UI and adapter runtime','HOST','tests/test_obsidian_adapter_contract.py tests/fixtures/obsidian_ui_runtime.mjs ui/packaged-smoke.mjs', 'MF-005 MF-006 MF-007 MF-008 MF-009 MF-010 MF-025 MF-026 MF-027 MF-031 MF-032 MF-033 MF-034', 'Actual bundled adapter runtime drives retry/takeover/dispose assertions; installed CSS/JS containment passes; artifact hashes and protocol recorded; unmocked Search after faults passes; mocked rendering never counts as real-host success.', 'test_obsidian_adapter_contract.py','B + H; planned runtime fixture must derive observations, not return expected constants.')
task('MF-036','3','NAT-15; MEM-05/06/12; MC-04/05/13/14','Integrate temporal revisions and versioned lessons','KNOWLEDGE','src/resource_librarian/dik.py src/resource_librarian/facts.py src/resource_librarian/evidence.py src/resource_librarian/schema.py src/resource_librarian/index.py src/resource_librarian/session.py', 'MF-012 MF-013 MF-014 MF-020 MF-021 MF-029', 'Human YAML + immutable source snapshots + DIK sidecar lineage rebuild temporal SQL; valid-time/known-time and external edits honest; episode pointers scoped; lessons staged/qualified/versioned; withdrawal survives cache rebuild and invalidates in-flight use.', 'test_schema.py test_revisions.py test_session_events.py test_dik.py test_evidence.py','Add planned tests/test_knowledge_temporal.py and tests/test_memory_withdrawal.py. No independent belief authority.')
task('MF-037','3','NAT-16; MEM-10; HARNESS-09 conditional','Add scoped support eligibility and measured selective invalidation','KNOWLEDGE','src/resource_librarian/dik.py src/resource_librarian/closure.py src/resource_librarian/closure_audit.py src/resource_librarian/audit_events.py src/resource_librarian/agenda.py', 'MF-036 MF-023', 'AND/OR sets preserve independent support; cycle/unknown/overflow stay unknown; closure named verifier unchanged; scope/lens pivot never rewrites source facts; agenda derives review tasks. Compare coarse epoch baseline before any selective closure optimization.', 'test_closure.py test_closure_lifecycle.py test_agenda.py test_lens_use.py','Add planned tests/test_knowledge_support.py. Full HARNESS-09 activation remains separately gated; advisory scoped support can be tested first.')
task('MF-038','3','MEM-08; MC-11/15','Evaluate bounded parent/section retrieval','RETRIEVAL','src/resource_librarian/search.py src/resource_librarian/ranking.py', 'MF-011 MF-012 MF-036', 'Exact hit spans plus bounded parents disclose scope/coverage; negation/caveats/duplicates tested; lexical/hybrid/structural arms matched; retain baseline if no demonstrated benefit.', 'test_search.py test_accept_ranking.py','New tests/test_memory_retrieval.py for eligibility/coverage cases.')
task('MF-039','3','MEM-09; NAT-16 discovery follow-on','Pilot V1 community orientation recovery','RETRIEVAL','src/resource_librarian/communities.py src/resource_librarian/search.py src/resource_librarian/ranking.py', 'MF-038', 'Snapshot/corpus/lens digests and stale status precede optional orient lane; factual summaries advisory; no model on ordinary reads; hubs cannot dominate; measured cross-topic benefit required.', 'test_communities.py test_search.py test_accept_ranking.py')
task('MF-040','3','MEM-11; DEPLOY-05 adjacent, not activation','Pilot DIK capability-sized code digest','KNOWLEDGE','src/resource_librarian/dik.py', 'MF-036 MF-037', 'Seed/import closure bounded with SCC handling, unresolved imports explicit and permitted roots enforced; compare file-reading baseline; static coverage not runtime semantics; do not activate broad structural indexing by implication.', 'test_dik.py','Add planned tests/test_capability_digest.py; optional experiment may terminate with retain-baseline decision.')
task('MF-041','3','MC-12; EK-01..08; EKP-01..10','Run deterministic evolving-knowledge benchmark and design held-out study','EVAL','tests/test_evolving_knowledge.py scripts/evolving_knowledge_benchmark.py', 'MF-021 MF-023 MF-030 MF-036 MF-037 MF-038 MF-039 MF-040', 'All ten seeds translated into real interfaces, restart/scope/correction invariants pass; rubrics hidden; A/B/C/D cloned state and cost denominators frozen. E/F only after simpler arms. Behavioral paid results explicitly pending until budgeted runs; no learning claim from fixtures alone.', '', 'Both files planned. Exact future target: .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider tests/test_evolving_knowledge.py.')
task('MF-042','1-3','NAT-17; BASE sync','Reconcile docs and Cowork contracts after each slice','DOC','docs/regression-manifest.md docs/unified-implementation-plan.md plugin/skills', 'MF-003', 'Actual tool/schema names, current tests, artifact provenance, partial/unknown limits and historical supersession updated for each delivered MF row; no quotas/learning/exactly-once claims without evidence.', 'test_mcp.py','Continuous checkpoint, not a blocking dependency cycle; docs owner is sole canonical-plan editor.')
task('MF-043','0-4','DT-02/03/04/05/07','Harden reproducible build and release evidence','BUILD','.github/workflows pyproject.toml requirements-dev.txt scripts', 'MF-004', 'Split into bounded build packets with exact files at admission: clean locks/toolchains, pinned CI permissions/input guards, retained test evidence, dependency/secret policy, SBOM/provenance verification, ownership/support/license decision. No certification claim from checklist.', 'test_release_versions.py test_release_leads.py','Release prerequisite; broad directories are planning ownership, never a worker write allowlist. DT-06 contained execution handled MF-015/016/023; autonomous DEV profile stays deferred.')
task('MF-044','4','ACCEPT-01/03; RELEASE-01 refresh','Refresh acceptance matrix and truthful capabilities','HOST','tests/test_acceptance_matrix.py docs/capability-matrix.md docs/release-implementation-queue.md', 'MF-035 MF-041 MF-042 MF-043', 'Existing eight-workflow matrix retained and extended for new accepted scope; success/refusal/recovery/no-mutation cells cite real tests; capability/release docs reflect implemented and experimentally rejected features.', 'test_acceptance_matrix.py test_accept_failures.py test_accept_ranking.py test_accept_workbench.py','Completed original packets are refreshed, not declared previously missing.')
task('MF-045','4','ACCEPT-02 final requalification','Repeat real-host acceptance on final candidate','HOST','reports/2026-10-31-accept02-windows-acceptance.md', 'MF-001 MF-044', 'Freeze candidate hashes then repeat touched lifecycle/SecretStorage/CSS/dirty-note/three-client/Docker/rollback boundaries; full suite and explicit slow cases; earlier overlays cannot qualify new bytes.', 'test_host_lifecycle.py test_shutdown.py test_mcp.py test_obsidian_adapter_contract.py','H; retain actual host versions and failure evidence.')
task('MF-046','4','RELEASE-02','R0 freeze, R1 locks, R2 qualified routes','RELEASE','docs/release-implementation-queue.md release-manifest.json', 'MF-044 MF-045', 'Owner R0 decision, clean exact source and SI/LC gates; locked wheelhouse, current L0-L3 exact-route evidence with expiry/budget. Candidate templates remain non-installable until gates pass.', 'test_release_versions.py test_release_leads.py','Externally blocked pending release owner, credentials and route budget; no paid action authorized by this plan.')
task('MF-047','4','RELEASE-03','R3 signing, R4 acceptance, R5 publication','RELEASE','release-manifest.json', 'MF-046', 'Protected signed payloads and verification/provenance pass; final signed Windows/adapter/rollback acceptance and supported hosted matrix pass; owner explicitly publishes and records rollback/watch procedure.', 'test_release_versions.py test_release_leads.py','Externally blocked; publication/signing are not performed in this synthesis.')
task('MF-048','decision','HARNESS-08','Optional Tier B experiment','EVAL','docs/experiments', 'MF-041', 'Owner predeclares held-out human labels, negative controls, false-completion/correction gain, cost/latency margin and cap; state-only/Tier A/Tier B compared; Tier B stays advisory and non-default without positive decision.', 'test_closure.py','No proposed automatic adoption; exact experiment file declared at admission.')
task('MF-049','decision','DELEG-06','Retain stop decision for small refactors','DOC','docs/unified-implementation-plan.md', 'MF-003', 'Record built pilot and E2-prime A0 lead-effort ratio 2.5; no autonomous controller expansion for small refactors. Further use needs a measured workload-specific go/narrow/stop case.', '', 'Ordinary bounded drafting/review in budget plan does not revive autonomous controller.')
task('MF-050','decision','HARNESS-09 / DEPLOY-05 / CORE-04B / DEV-01..14','Preserve deferred scope decisions','DOC','docs/unified-implementation-plan.md', 'MF-003', 'Record whether each remains deferred or receives a new bounded approved packet. HARNESS-09 prerequisites remain explicit; CORE-04B means managed bootstrap through the same Core, never direct vault ownership; structural index and writable developer profile not smuggled into pilots.', '', 'Current plan defaults to deferred. These decisions do not block release when excluded from shipped scope.')

# Resolve existing integration seams and enumerate future tests without pretending they exist.
by_id={t['id']:t for t in tasks}
by_id['MF-004']['files']=['.github/workflows/ci.yml','tests/test_app.py']
by_id['MF-004']['tests']+=['test_app.py']
by_id['MF-012']['files']=['src/resource_librarian/result_handles.py','src/resource_librarian/evidence.py','src/resource_librarian/tools/results.py']
for ident,names in {
    'MF-021':['test_worker_continuity.py'],
    'MF-027':['test_staging_preview.py'],
    'MF-029':['test_v1_fidelity.py'],
    'MF-036':['test_knowledge_temporal.py','test_memory_withdrawal.py'],
    'MF-037':['test_knowledge_support.py'],
    'MF-038':['test_memory_retrieval.py'],
    'MF-040':['test_capability_digest.py'],
    'MF-041':['test_evolving_knowledge.py'],
}.items(): by_id[ident]['tests']+=names

# --- Corrections adopted 2026-11-04 (Codex's review of this set, re-checked by Claude) ---
# 1. A release is gated by a frozen selected-scope record (MF-051), not by every
#    proposed capability: before this, 45 of 50 packets gated MF-047, because
#    MF-044 depended on the MF-041 benchmark experiment.
task('MF-051','3-4','Codex review 2026-11-04','Freeze the selected release scope','RELEASE','docs/unified-implementation-plan.md docs/capability-matrix.md', 'MF-002 MF-003 MF-004', 'One dated owner record lists every P1 packet (MF-011–020, MF-027) as fixed with its evidence, or disabled and stated as a limitation in the capability matrix; every optional track (MF-021–026, MF-028–034) as in or out of the release; experiments MF-036–041 and decisions MF-048–050 as outside the release. A packet recorded as in becomes a prerequisite of MF-035 and MF-044 through this record.', 'test_acceptance_matrix.py','Owner decision; replaces the old transitive release graph.')
by_id['MF-051']=tasks[-1]
by_id['MF-035']['deps']=['MF-005','MF-006','MF-007','MF-008','MF-009','MF-010','MF-051']
by_id['MF-044']['deps']=['MF-035','MF-042','MF-043','MF-051']

# 2. Oversized rows become sub-packets, each dispatched and merged on its own.
#    The parent stays as the umbrella that is done when its slices are.
SPLITS={
 'MF-021':[('a','Structured worker envelopes and handoff receipts',''),('b','Aggregate budget reservation across workers','a'),('c','Restart-safe parent merge','a')],
 'MF-027':[('a','Reply-review identity: full path, whole body, capped challenges',''),('b','Exact composed staging preview',''),('c','Docker preflight before review execution','')],
 'MF-034':[('a','Navigation',''),('b','Staging redesign',''),('c','Search redesign','')],
 'MF-036':[('a','Temporal revision event schema',''),('b','Manifests','a'),('c','SQLite projection','a'),('d','Migration of existing records','c'),('e','Lifecycle and withdrawal','c')],
 'MF-041':[('a','Deterministic fixtures',''),('b','Benchmark adapter','a'),('c','Held-out study design','b'),('d','Paid trial, only with its own owner approval and cap','c')],
 'MF-043':[('a','CI and toolchain',''),('b','Dependency locking','a'),('c','Workflow security','a'),('d','Evidence retention','a'),('e','Provenance and SBOM','b'),('f','Operating governance','')],
}
for parent,parts in SPLITS.items():
    base=by_id[parent]; subs=[]
    for suffix,title,after in parts:
        ident=parent+suffix
        tasks.append(dict(id=ident,wave=base['wave'],aliases=parent,title=title,lane=base['lane'],files=list(base['files']),
                          deps=list(base['deps'])+[parent+a for a in after.split()],
                          done=f'This slice of {parent} ({title.lower()}) meets its share of the parent condition, with its own focused test passing before it merges.',
                          tests=list(base['tests']),extra=f'Sub-packet of {parent}.'))
        by_id[ident]=tasks[-1]; subs.append(ident)
    base['deps']=list(base['deps'])+subs
    base['extra']=(base['extra']+' ' if base['extra'] else '')+'Umbrella: done when '+', '.join(subs)+' are done and the condition holds end to end.'

# Notes from the 2026-11-04 re-check.
by_id['MF-011']['extra']+=' REMED-07 measured 27,470 bytes (OpenAI-compatible) and 28,529 bytes (Anthropic) at 50 rounds: this is a missing guarantee, not an observed overflow.'
by_id['MF-010']['extra']+=' REMED-08: three of eight MiMo sessions were parked whole, because the proposal named every requirement; the stop reason must say when a park left no independent work.'
by_id['MF-004']['extra']+=' Observed 2026-11-04 via the Actions API: Core CI fails its L0/Core suite step on Python 3.11, 3.12 and 3.13 at 40ec923 and on every push since 2026-10-29, while wheel smoke and adapters pass and the local suite passes (1,939 passed). Job logs need repository authentication.'

# 3. Each packet says whether and when it blocks a release, and what stands in for it.
ROLE={}
for n in [1,2,3,4,5,6,7,8,9,10,35,42,43,44,45,46,47,51]: ROLE[f'MF-{n:03}']='required'
for n in list(range(11,21))+[27]: ROLE[f'MF-{n:03}']='fix-or-disable'
for n in list(range(21,27))+list(range(28,35)): ROLE[f'MF-{n:03}']='if-selected'
for n in list(range(36,42))+[48,49,50]: ROLE[f'MF-{n:03}']='outside release'
STAGE={}
for ids,stage in [([1,2,3,4],'1'),(list(range(5,15)),'2'),(list(range(15,21))+[27,51],'3'),([35,42,43,44,45],'4'),([46,47],'5'),(list(range(21,27))+list(range(28,35)),'6'),(list(range(36,42))+[48,49,50],'7')]:
    for n in ids: STAGE[f'MF-{n:03}']=stage
BLOCKS={'required':'always','fix-or-disable':'the capability ships enabled with the defect unfixed','if-selected':'MF-051 selects it for the release','outside release':'never; it runs on its own approval'}
FALLBACK={'required':'none','fix-or-disable':'disable it, or mark it unsupported in the capability matrix with the limitation in the release notes','if-selected':'leave it out of the release scope','outside release':'defer, keep or reject by its own decision'}
RECHECKED={'MF-005','MF-007','MF-011','MF-012','MF-013','MF-014','MF-015','MF-016','MF-017','MF-018','MF-019','MF-020','MF-027'}
PROCESS={'MF-001','MF-002','MF-003','MF-035','MF-042','MF-043','MF-044','MF-045','MF-046','MF-047','MF-049','MF-050','MF-051'}
for t in tasks:
    key=t['id'][:6]
    t['release']=ROLE[key]; t['milestone']=STAGE[key]
    t['blocking_if']=BLOCKS[t['release']]; t['fallback']=FALLBACK[t['release']]
    t['evidence']=('observed 2026-11-04' if key=='MF-004' else 'source-supported, re-checked 2026-11-04' if key in RECHECKED
                   else 'process, no defect claim' if key in PROCESS else 'proposal' if t['release']=='outside release'
                   else 'source-supported (review), not re-checked')

def header(title):
    return '# '+title+'\n\n'+nav()+'Prepared 4 November 2026 against `40ec923f5d7cb5612939b9fc456963b88e0af4a3` on `master`. **Proposed synthesis for approval; not runtime implementation or release certification.** The current user request governs; transcript instructions are historical evidence.\n\n'

def write(name,text): (OUT/name).write_text(text,encoding='utf-8')

SUITE=ROOT/'reports/2026-11-04-evidence/suite-40ec923-clean.json'
suite=json.loads(SUITE.read_text(encoding='utf-8'))
DELEG=ROOT/'tmp/deepinfra-delegation/ledger.json'
deleg=json.loads(DELEG.read_text(encoding='utf-8'))
shared=[c for c in deleg['calls'] if c.get('pool')=='shared']
shared_committed=round(sum(float(c.get('charged_usd',0)) for c in shared),8)
report=header('Master system report: delivered baseline and remaining finalization')
report+='''## Executive assessment

The original implementation program has delivered its Core ownership, routing, adapter, adoption and audited-session foundations. The new reviews identify boundary defects and missing continuity/visibility contracts; they do not justify rebuilding those foundations. Proceed with operational closure, P1 corrections and truthful UI, then qualify evolving knowledge on the repaired substrate.

At this exact commit the full suite was rerun, in a clean clone with CI's install step, on '''+suite['started_utc'][:10]+''': **'''+suite['summary']+'''**, exit code '''+str(suite['exit_code'])+''' (CPython '''+suite['python']+''', '''+suite['platform']+''', no tracked changes: '''+('yes' if not suite['tracked_changes'] else 'no')+'''). The command, environment, exit code and complete output are retained in '''+link('reports/2026-11-04-evidence/suite-40ec923-clean.json')+''' and '''+link('reports/2026-11-04-evidence/suite-40ec923-clean.log')+'''. The earlier reported post-recovery baseline was 1,938 passed; the final layout commit additionally has both builds, hostile-CSS smoke, six adapter contracts and person-confirmed Obsidian layout evidence. Hosted Core CI at the same commit fails its suite step on Python 3.11, 3.12 and 3.13, so a green local run is not hosted assurance. This synthesis did not launch Docker, call providers, change runtime code, settle charges, or perform release actions.

The checkout matches the requested commit. Existing untracked transcript/proposal/review material remains outside the committed baseline; preserve it. The four documents are the proposed consolidated design authority **after approval**; until then the existing unified plan remains sequencing authority. Historical findings retain their evidence class: inspected code, scripted fixture, synthetic browser probe, real host, or unexecuted proposal.

## Evidence precedence and corrections

Use current user guardrails, then directly retained artifacts/current local records, then the unified plan's latest §19 entries, then older handoffs and transcript summaries. Where a record conflicts, retain the history and state the superseding evidence. Reviews supply hypotheses and tests, not completion claims.

'''
corrections=[
('Original handoff leaves REMED-08/MiMo decision pending','Task-local stopping was approved and implemented at 8b3844c; pilot complete; REMED-06 exit met. Only uncertain billing reconciliation remains.',anchor(PLAN,'### REMED-08 measurement')),
('Two uncertain entries / ~$5.45 remaining','Three entries remain uncertain. Local ledger cap $8, committed $5.57622764, available $2.42377236. The ~$5.45 handoff figure was committed spend.',anchor('reports/2026-10-30-g5-measurement.md','The shared G5 ledger stands')),
('INDEX-02/03 partial; INDEX-05 still needs encoder release','INDEX-02/03 closed by zero serving-path debt; INDEX-05 closed locally and external evidence moved to ACCEPT-02/RELEASE-03. Encoder release already delivered; NAT-03 hardens recovery/counts.',anchor(PLAN,'| INDEX-02, INDEX-03 |')+'; '+link(PLAN,759)),
('DEPLOY/HARNESS all planned; RELEASE-01 planned in manifest','DEPLOY-01..04, HARNESS-01..07, ACCEPT-01/03 and RELEASE-01 are implemented. Manifest aggregate/history rows lag §19.',link('docs/regression-manifest.md',66)+'; '+link(PLAN,3149)),
('G3/G5 blocked in early release log','Current release queue records G0..G5 green; later G5 fixed-code and REMED-08 results supersede initial run. Recheck gates on final changed source; no stable-release approval follows automatically.',link('docs/release-implementation-queue.md',15)),
('Native Docker tmpfs/supervisor proposal','Superseded: disk-backed qualified quotas, no --rm, stop/kill entire container, verify stopped, bounded docker cp tar export into quarantine, then remove.',link(NAT+'DESIGNS.md',118)),
('Verbose epistemic YAML as separate belief system','Superseded: ergonomic claim YAML, DIK/facts integration, unframed EvidenceStore snapshots, framed lineage sidecars, existing closure/audit and agenda semantics.',link(NAT+'DESIGNS.md',52)),
('UI-only missing-field disclaimers and 680px settings','Superseded by reason/source, reply identity/coverage and composed-preview bridges; named CSS container queries and 1120×820 left-sidebar Settings. Genuine unsupported job/history data stays unknown.',link(UI+'UI-DESIGNS.md',95)+'; '+link(QA/'settings-redesign-plan.md',19)),
('Research tooling alternatives imply dependencies','External orchestration/database/frontend adoption is rejected for this plan. Transfer temporal/support/provenance concepts into existing native modules; use current Python tests for benchmarks.',link(MEM+'formal-solutions/TOOL-DECISIONS.md',1)),
('Mobile Plan always defaults open; clearing requires right-click','Corrections: takeover depends on saved/open pane state; visible clear, Delete and long-press already exist. Improve role clarity and persistence without claiming those controls are absent.',link(QA/'librarian-research-assessment.md',69)),
]
report+=table(['Superseded reading','Canonical reconciliation','Evidence'],corrections)
report+='## Current baseline and evidence limits\n\n'
baseline=[
('Core: CORE-01/02A/02B/03/04A/05A/05B/06/07','Implemented','Platform process identity and venv redirector lifecycle; park/drain; Core-owned hash-chained Session append; constrained MCP RPC; bound revision tokens/CAS; start-only-operation checkpoints; epoch SSE resync.',link(PLAN,714)+'; '+link(PLAN,722)+'; '+link(PLAN,728)),
('INDEX-01..05','Implemented original scope','AST guard and zero serving debt; callback-only IndexService; Windows contention/WAL/snapshot/force-stop/scale/installed fixtures; encoder releases both owners. Rename chunk loss and operation counters are new NAT corrections, not reopening all INDEX work.',link(PLAN,757)+'; '+link(PLAN,2112)),
('ROUTE-01..05; ADAPT-01..11 incl. 04B','Implemented','Canonical role routes/readiness; trusted OpenAI/Anthropic render/parse; metadata and reasoning continuation; cancellation; service routing/HostLimiter; declarative packs; stable prompt layout; reviewed authoring; bounded tool surface and ephemeral handles. Route-specific live qualification remains evidence-bound.',link(PLAN,2116)+'; '+link('docs/regression-manifest.md',58)),
('DEPLOY-01..04','Implemented','Survey/create/adopt/attach, managed content-root scope, workspace documents and stable identity/dedupe explanations. Does not mean complete V1 history migration or automatic merges.',link(PLAN,2649)+'; '+link(PLAN,2858)),
('HARNESS-01..07','Implemented, measured within declared sample','Session reuse, typed events/replay/epochs, audited phases, bounded projection, closure authority and per-call gates, research grains/Tier A, protected-target verification. Complete request bounding and durable worker continuity remain new work.',link(PLAN,2148)+'; '+link(PLAN,2568)+'; '+link('docs/release-implementation-queue.md',27)),
('REMED-01/02','Implemented','Adopted-library schema validation and grouped search corrected.',link(PLAN,3579)+'; '+link(PLAN,3618)),
('REMED-03/04/05','Implemented original scopes','Closure drift/person-named verifiers/legacy handling; bounded captured/exported outputs and live Docker checks; per-dispatch paid reservations. NAT disk-exhaustion/teardown fixes strengthen these guarantees.',link(PLAN,3648)+'; '+link(PLAN,3725)+'; '+link(PLAN,3807)),
('REMED-06/07/08','Implemented; pilot exit met','Predicate IDs/skeleton/refusals/stall parking; actual-wire context/capability/retry qualification; bounded paid comparison. DeepSeek 28/37 and MiMo 10/37 candidate Tier A; 16 valid histories, 38 held closures, 14 reached restart points reproduced. Not causal isolation of REMED-06.',anchor(PLAN,'### REMED-08 measurement')+'; '+anchor(PLAN,'### REMED-07 model-view')),
('UX-01','Implemented, refinements open','Predicate inspector differentiates authority, person acceptance and stale historical evidence. G11..G14 describe concrete rendering/oversight gaps, not absence of inspector.',link(PLAN,3966)),
('ACCEPT-01/03; RELEASE-01','Implemented, refresh at Wave 4','Eight-workflow acceptance matrix and capability parity/release-gate docs delivered. Future changes require extension/requalification.',link(PLAN,3011)+'; '+link(PLAN,3093)+'; '+link(PLAN,3149)),
('ACCEPT-02','Partial: one original live check remains','Installed-wheel/packaged protocol, rollback, real Docker, real Obsidian dirty/SecretStorage/layout and independent Windows handle evidence retained. Only real three-client mixed traffic unchecked.',link('reports/2026-10-31-accept02-windows-acceptance.md',351)),
]
report+=table(['Track','Status at takeover','Delivered / boundary','Evidence'],baseline)
report+='''### Acceptance provenance matters

The initial acceptance package and 2 November refresh have different hashes. Real dirty-note evidence uses the `bdfd834` candidate; SecretStorage/recovery uses a remediation overlay, with a later exit-to-stdio-close race fix tested separately. The 40ec923 layout confirmation is another identified step. These are valid bounded observations, not one immutable final signed bundle pass. Obsidian **1.12.7** is the retained About version; 1.15.0 in earlier title fields is not authoritative version evidence.

The first dirty-note attempt missed the ten-second heartbeat and wrote; its bytes were restored, and it is explicitly excluded from the boundary pass. The synchronized repeat refused `DOCUMENT_ACTIVE` and preserved bytes while an unrelated write succeeded. Independent external holders demonstrated WinError 5 refusal/retry and SQLite snapshot/WAL integrity; they were scripted processes, not GUI-application tests. Public checkpoint counters were not observed.

'''
report+='Evidence: '+', '.join(link('reports/'+f) for f in ['2026-11-03-accept02-obsidian-dirty.json','2026-11-03-accept02-obsidian-secretstorage.json','2026-11-03-accept02-external-handles.json'])+'.\n\n'
report+='### Remaining original-plan disposition\n\n'
report+=table(['Item','Exact remaining action','Master owner'],[
('ACCEPT-02','One original Browser + Obsidian + real Claude/Cowork mixed-traffic check; final changed artifact requalification later.','MF-001 → MF-045'),
('REMED-06/08','No timeout-policy decision remains; reconcile three liabilities without weakening reservations.','MF-002'),
('BASE-03..05','Already implemented; refresh stale manifest/status language after approval.','MF-003 / MF-042'),
('HARNESS-08','Experimental Tier B; predeclared fixtures, labels, budget and go/no-go required; remains advisory.','MF-048'),
('DELEG-06','Pilot built; A0 stop for small refactors (2.5× lead effort), further use conditional.','MF-049'),
('HARNESS-09','Deferred full targeted invalidation/trust-zone scope; Wave 3 prototypes support eligibility, preserves coarse fallback and old HARNESS-08 dependency unless explicitly amended.','MF-037 / MF-050'),
('DEPLOY-05','Deferred structural index; bounded DIK digest pilot is not blanket adoption.','MF-040 / MF-050'),
('CORE-04B','Deferred managed bootstrap into existing Core; never a direct no-Core database path.','MF-050'),
('RELEASE-01..03','01 delivered documentation; 02/03 externally blocked on freeze/credentials/signing/real artifact evidence and owner publication.','MF-044 / MF-046 / MF-047'),
])
report+='## Unified gap matrix\n\nEach row is one remediation boundary. Original finding IDs are aliases, not duplicate tasks. P1 = correctness/resource/authority or broken critical interaction; P2 = material continuity/observability; P3 = ergonomics/documentation. Scheduling UI-07/08 in Wave 1A does not relabel every P2 source finding P1. Anchors are one-based at the inspected checkout; source-report anchors preserve the evidence argument.\n\n'
gaps=[]
def gap(ids,p,issue,owner,refs): gaps.append((ids,p,issue,owner,refs))
gap('MEM-01/02; MC-01/02/16','P1','Complete dispatched history grows despite bounded projection; no proven final token ceiling.','MF-011',link('src/resource_librarian/loop.py',812)+'; '+link('src/resource_librarian/loop.py',932))
gap('MEM-03/12; MC-03/06/07/14','P1','Loop-local handles cannot satisfy restart/parent evidence continuity; withdrawal and scope must survive durable reuse.','MF-012',link('src/resource_librarian/result_handles.py',1)+'; '+link('src/resource_librarian/loop.py',886))
gap('MEM-04/07; MC-08/09/10; MCP','P1','Clipped worker caveats, no typed parent snapshot/merge receipt or proven shared reservation; cross-client restart needs tests.','MF-021/030',link('src/resource_librarian/tools/delegate.py',37)+'; '+link('src/resource_librarian/mcp_server.py',1)+'; '+link('src/resource_librarian/mcp_client.py',1))
gap('MEM-05/06/12; NAT-15; MC-04/05/13/14; EK-01..04','P2','Missing scoped episode→qualified lesson→correction/withdrawal lifecycle and temporal current-use view.','MF-036',link('src/resource_librarian/dik.py',15)+'; '+link('src/resource_librarian/facts.py',697)+'; '+link(MEM+'REVIEW.md',71))
gap('MEM-10; NAT-16; MC-15; EK-05/07','P2','Support alternatives, coverage and applicability not a qualified selective revalidation system; distinguish human learning from probes.','MF-037/041',link('src/resource_librarian/closure.py',156)+'; '+link('src/resource_librarian/closure_audit.py',150)+'; '+link('src/resource_librarian/agenda.py',76))
gap('MEM-08; MC-11/12','P2','Exact hit/parent/negation coverage and downstream use need matched evaluation; absence of top-k hit is not factual absence.','MF-038/041',link('src/resource_librarian/search.py',1)+'; '+link('src/resource_librarian/ranking.py',151))
gap('MEM-09/11; MC-15','P2','V1 orientation and code digest partly lost; graph snapshots/coverage needed before selective recovery.','MF-039/040',link('src/resource_librarian/communities.py',20)+'; '+link('src/resource_librarian/dik.py',141))
native_map={11:('NAT-01','MF-013'),12:('NAT-15/16; epistemic distinctions','MF-036/037'),13:('NAT-02','MF-014'),14:('NAT-03','MF-022'),15:('NAT-16; MEM-09','MF-037/039'),16:('NAT-09','MF-024'),17:('NAT-10; G16','MF-027'),18:('NAT-09/10; MC-01','MF-024/027'),19:('NAT-06','MF-017'),20:('NAT-07','MF-018'),21:('NAT-15/16','MF-036/037'),22:('NAT-04; G18','MF-015'),23:('NAT-05; G18','MF-016'),24:('NAT-08','MF-023'),25:('NAT-12','MF-028'),26:('NAT-11','MF-019'),27:('NAT-13/14','MF-020/029'),28:('NAT-13; MC-06','MF-020/030')}
for n,l in enumerate(read(NAT+'REVIEW.md').splitlines(),1):
    if n not in native_map: continue
    cells=l.strip('|').split('|'); ids,owner=native_map[n]
    gap(ids,'P1' if 'P1' in cells[2] else 'P2',cells[1].strip(),owner,source_links(cells[3].strip(),NAT+'REVIEW.md'))
ui_owner={'G01':'MF-005','G02':'MF-005','G03':'MF-008','G04':'MF-007','G05':'MF-007','G06':'MF-025','G07':'MF-026','G08':'MF-026','G09':'MF-026','G10':'MF-026','G11':'MF-009','G12':'MF-009','G13':'MF-010','G14':'MF-010','G15':'MF-027','G16':'MF-027','G17':'MF-027','G18':'MF-015/016/027','G19':'MF-006','G20':'MF-032/034','G21':'MF-025/034'}
for l in read(UI+'UI-REVIEW.md').splitlines():
    if not re.match(r'^\| G\d\d \|',l): continue
    c=l.strip('|').split('|'); gid=c[0].strip()
    if gid in ('G16','G18'): continue # native rows above already own these findings
    gap(gid, re.search(r'P[123]',c[2])[0],c[3].strip(),ui_owner[gid],source_links(c[4].strip(),UI+'UI-REVIEW.md'))
gap('Settings visual; L01/L04/L05/L11; UI-11/12','P2','Five-tab dialog mixes environment/library/advanced scope; roles and shared default fallback unclear; persistent entry points absent.','MF-031/032/033',link('ui/src/settings.ts',58)+'; '+link('src/resource_librarian/app.py',206)+'; '+link(QA/'settings-redesign-plan.md',35))
gap('Staging visual; L06/L07/L08/L09; UI-12','P2','Queue/form/evidence compete while empty Plan consumes width; counts and process-vs-publish consequences unclear.','MF-034',link('ui/src/views.ts',405)+'; '+link('ui/src/views.ts',474)+'; '+link(next((ROOT/'docs/Development transcripts').glob('*-7.md')),645))
gap('Search visual; L02; UI-04/12','P1','Readable query/filter values lost at narrow widths even without page overflow; two-row controls required.','MF-008/034',link('ui/src/views.ts',851)+'; '+link(QA/'librarian-research-assessment.md',61))
gap('L03/L10/L12; navigation/outcomes','P3','Pane navigation hidden among note actions; empty states and actual human task outcomes unqualified.','MF-034/035/044',link('ui/src/pane.ts',210)+'; '+link(QA/'librarian-research-assessment.md',99))
gap('DT-01..07','P1','Hosted Core CI is red: its L0/Core suite step fails on Python 3.11, 3.12 and 3.13 at 40ec923 and on every push since 2026-10-29 (observed 2026-11-04), while the local suite passes. Reproducibility and release provenance gaps remain; the local suite is not hosted matrix or signed release assurance.','MF-004/043',link('reports/2026-11-03-development-tooling-review/ASSESSMENT.md',19))
gap('NAT-17; BASE-03/04/05','P3','Historical partial/planned rows and handoff figures can misdirect new work unless explicitly superseded; Cowork contracts must follow delivered behavior.','MF-003/042',link('docs/regression-manifest.md',66)+'; '+link(NAT+'PACKETS.md',23))
report+=table(['Aliases','Severity','Gap / consequence','Single execution owner','Exact evidence anchors'],gaps)
report+='''## Research synthesis and disposition

The strongest common idea is to preserve evidence/history while revising eligibility for current use. Source truth, editorial acceptance, extraction coverage, quote presence, arithmetic agreement, replication under one environment, and person acceptance must stay separate. Relevance, freshness, applicability, lifecycle, epistemic status and authority are independent dimensions. A goal pivot retires advice without falsifying the old measurement.

V1 contributes lexical/hybrid retrieval and useful community orientation/import-digest patterns; V2 contributes stronger Session authority, staging and Core ownership. Mark contributes lifecycle tiers, localized consolidation proposals and snapshot discipline. Neither old caches nor Mark's artifact-completeness tests prove migration fidelity or later-task learning. Do not copy destructive prompt-memory trimming, similarity-as-truth, automatic global preference inference or unscoped fallback.

The formal solutions motivate native bitemporal projection, AND/OR support sets, revision-bound worker acceptance, reservations and reproducible recipes. Their reference models establish properties of small abstractions only. External platform surveys are background, not procurement or installation instructions. Existing workflow execution, DIK lineage, EvidenceStore and closure verifiers are the integration points.

The memory literature supports testing recall separately from downstream use, harmful transfer, correction uptake and abstention. R1..R8 research objectives become: durable references (MF-012/036), bounded context/handoffs (MF-011/021), qualified lessons (MF-036/041), measured invalidation (MF-037), recipes (MF-017/018/023), actor-separated probes (MF-041), chronological evaluation (MF-041), and selective retrieval (MF-038..040). Proposed benefit remains unmeasured until those experiments run.

The QA corpus screened ten papers; five received focused extraction. R2 supplies a heuristic development/validation method; R1 supplies task-context instrumentation; R5 motivates cautious claim/evidence proximity; R6 separates usefulness, ease and adoption; R9 motivates task decomposition and varied input/users. R3/R10 are indirect screened sources; R4/R7/R8 do not support UI criteria. None establishes numerical layout thresholds, demographic personalization, accessibility certification or a measured Librarian UX improvement. Preserve all twelve L01..L12 criteria through the validation mapping in document 02.

Historical tests are separate evidence sets: memory review 84 V2 tests; evolving review 59 V2 and 28 Mark tests; native review 99 tests; UI review TypeScript and six adapter tests plus synthetic probes. Do not add these counts into a fresh full-suite or benchmark claim. EKP-01..10 are scenario seeds, not yet executable API tests.

## Source inventory and provenance

The following inventory preserves all required artifacts and the additional formal/theory/development-tooling outputs found in the analysis transcript. The transcripts were read as chronological discussion and targeted evidence, with large embedded tool/data blocks treated as supporting material rather than instructions. Runtime reads in this pass were limited to schema/ownership integration seams and test/anchor existence, not a new codebase audit. Source hashes are retained in `validation.json`; external QA Markdown is copied under `sources/qa/` for portability along with its referenced screenshots. The original concept image is preserved byte-for-byte at the report root.

'''
sources=[PLAN,'docs/handoff-2026-10-31-codex.md','docs/regression-manifest.md','docs/release-implementation-queue.md','reports/2026-10-31-accept02-windows-acceptance.md','reports/2026-11-03-accept02-obsidian-dirty.json','reports/2026-11-03-accept02-obsidian-secretstorage.json','reports/2026-11-03-accept02-external-handles.json','reports/2026-10-30-g5-measurement.md','docs/proposals/memory-context-design-addendum.md']
sources += [str(p.relative_to(ROOT)).replace('\\','/') for folder in [MEM,NAT,UI,'reports/2026-11-03-development-tooling-review/'] for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ('.md','.json')]
sources += [str(p) for p in (ROOT/'docs/Development transcripts').glob('*.md')]
sources += ['reports/2026-11-04-review-assessment.md','reports/2026-11-04-evidence/suite-40ec923-clean.json','reports/2026-11-04-evidence/suite-40ec923-clean.log']
sources += [str(QA/f) for f in ['research-synthesis.md','librarian-research-assessment.md','settings-redesign-plan.md','settings-layout-concept.png']]
report+=table(['Source','Use / evidence class'],[(link(p),'Chronological discussion; not active instructions' if 'transcript' in str(p) else 'Supplied review/specification or retained evidence; limits described above') for p in sources])
report+='\n'+link(OUT/'settings-layout-concept.png',label='Preserved Settings concept')+' — illustrative design, not an implemented screenshot.\n'
write(NAMES[0],report)

spec=header('Unified requirements and specifications')
spec+='''## 1. Scope, authority and requirement naming

This is a proposed canonical addendum, consolidating MC-01..16, the native designs, UI D1..D6 and Settings/Staging/Search corrections. “Must” defines the proposed acceptance contract, not current implementation. Existing Core security/closure policy remains controlling. All new runtime work is planned unless document 01 explicitly says delivered.

**Architecture invariant A-01.** Python single-owner Core; SQLite through IndexService; durable vault mutations through VaultWriter; existing Session/run JSONL and recovery records; Markdown as note truth, immutable EvidenceStore for captured inputs and `.librarian/` sidecars for manifests/derived views; vanilla TypeScript/CSS for both hosts. No Temporal, XTDB, LangGraph, CWL runner, GraphRAG, Anki, Inspect AI, React, Vue or Tailwind. No new independent scheduler, belief database, task ledger or browser authority. Acceptance: ownership/transport guards pass and no active-Core fallback constructs private vault state.

**A-02.** Preserve Broker/person permissions, current access checks, staging review, exact revision-CAS tokens and existing verifier authority. Data, including retained transcript instructions and worker paraphrases, cannot elevate permissions or become person requirements through repetition. Acceptance: revoked-access and source-instruction fixtures fail closed at retrieval, handoff and merge; LLM consensus never closes an authoritative predicate.

IDs **MC-01..16 are requirement clauses**, whereas **MEM-01..12 are the review's implementation packets**. The user's shorthand “MC-02 durable handles / MC-03 handoffs” maps operationally to MF-012/MF-021, but canonical clauses remain MC-03 for durable evidence and MC-08/09 for handoff/merge. MF-* is the unique execution namespace.

## 2. Complete memory/context contract

'''
mc_rows=[
('MC-01','Final route input, protocol/schema overhead and reserved output fit the effective supported allowance. Count after trusted rendering; identify tokenizer/estimate and uncertainty. Essential overflow splits or parks before dispatch.','50/200 rounds, Unicode/code/schemas and continuation blocks: every dispatch within bound or explicit refusal; no orphan tool result.','MF-011'),
('MC-02','Derived context preserves typed goal, constraints/exceptions, corrections, unresolved decisions, uncertain effects and required evidence identities. Record source event boundary, revision and omitted categories.','Repeated compaction/restart retains exact constraints; summaries cannot replace authority; distinguish presence from successful model use.','MF-011/041'),
('MC-03','Promised durable evidence resolves beyond originating Loop with version, locator and representation; current access checked; ephemeral lifetime explicit.','Parent after child exit/Core restart opens exact version or gets changed/missing/expired/forbidden outcome, never silent new bytes.','MF-012/030'),
('MC-04 (conditional)','Procedure reuse carries assumptions/scope/version, outcomes, limitations and applicability checks; old failure is conditional.','Environment fix permits requalification; obsolete workaround rejected; unknown fit remains tentative.','MF-023/036/041'),
('MC-05 (conditional)','Recording and validity times distinct; authorized correction/supersession explicit; independent conflicts unresolved unless adjudicated.','Current/as-of answers differ correctly; corrections affect dependent use; unknown dates not backfilled.','MF-036/037'),
('MC-06','Library/project/session/role scope checked at read, rehydrate and merge. Private worker context is not automatically shared.','Similar forbidden project leaks no excerpt, count or neighbor; revocation between read/merge prevents dependent use.','MF-012/021/030'),
('MC-07','Origin and lineage survive retrieval, paraphrase, consolidation and graph projection; duplicate source derivations are not corroboration.','Hostile source instructions remain data; lost lineage stays advisory; duplicated summaries count as one source.','MF-012/021/036'),
('MC-08','Worker packet includes parent work/revisions, question, snapshot, constraints, scope, allowance and result obligations; result includes evidence/caveats/conflicts/stops/usage.','Late caveat past preview retained structurally or explicit overflow with durable reference; missing prerequisite may be reported without answer.','MF-021'),
('MC-09','Core merge checks current requirements/contract/evidence/access against stable child identity; receipt and acceptance distinct, deduplicated durably.','Concurrent stale results cannot close revised work; replay accepts once; crash before merge leaves pending, not presumed accepted.','MF-021/030'),
('MC-10','Shared controlling allowance reserved atomically before parallel/inner/retry/repair/review calls; attribution avoids double count; unknown charges retain reserves.','N workers cannot each spend remaining cap; two vault TTS requests serialize personal cap; totals reconcile exactly.','MF-019/021/024/028'),
('MC-11','No eligible match, incomplete search, forbidden/access failure, stale, partial and contradictory evidence distinct; bounded follow-up may abstain.','Two of three required sources yields explicit coverage gap, not complete answer; top-k miss never proves absence.','MF-027/028/038'),
('MC-12','Evaluate later decisions with optional memory absent/relevant/noisy/outdated; measure benefit and harm, supported decisions, recovery and all costs.','Held-out chained and preservation slices, denominators and stream-level uncertainty; no recall-only pass.','MF-041'),
('MC-13 (conditional)','Consolidation is reversible versioned proposal/view with evidence/status; promotion required for durable accepted knowledge; originals remain usable.','Faulty lesson withdrawal/rebuild loses no original episodes; inferred preference never becomes global instruction; enrichment failure falls back.','MF-036'),
('MC-14 (conditional)','Withdrawal propagates to search/vectors/summaries/caches/worker acceptance/graph views; retrieval suppression distinct from audit retention/byte deletion.','Withdraw, restart, rebuild: no current retrieval; in-flight dependent result refused; retained audit reference accurately disclosed.','MF-012/036'),
('MC-15 (conditional)','Edges distinguish structure/source claims/inference and retain direction/negation/qualifiers/version/scope; graph paths/community are advisory.','Inhibits never becomes promotes; two-hop similarity not causal verification; stale community visible; original lexical evidence fallback.','MF-037/038/039/040'),
('MC-16','Retrieval/fan-out/rehydration/consolidation/index maintenance have resource ceilings and observable exhaustion; caches cannot evict canonical constraints.','Fan-out, irrelevant recall loop and cache exhaustion stop boundedly; source-loss vs cache-unavailable explicit; no unbounded paid maintenance.','MF-011/012/015/021/041'),
]
spec+=table(['Requirement','Normative contract','Acceptance','Execution owner'],mc_rows)
spec+='Source clauses and rationale: '+link('docs/proposals/memory-context-design-addendum.md',9)+'; '+link(MEM+'REQUIREMENTS-RESEARCH.md',19)+'.\n\n'
spec+='''### 2.1 Context assembly and durable handle shapes

Compute `input_allowance = route_context_limit - output_reserve - protocol_safety_margin`. The route manifest identifies whether the limit is total-context or input-only; use its actual semantics. Count the complete rendered request with the route tokenizer when available; an estimated method needs a qualified conservative upper bound, not the current characters/4 assumption. If no safe allowance can be established, refuse the context-sensitive profile with an explicit configuration outcome. Provider-reported usage calibrates later calls; it cannot retroactively make an oversized dispatch safe.

Include current essential Session projection on each audited dispatch, then bounded dialogue and evidence selected within remaining allowance. Preserve tool-call/result groups and provider continuation as indivisible units. Keep required corrections/uncertain outcomes outside optional summary eviction. Never persist hidden reasoning blocks in diagnostics or durable handles; existing ephemeral provider continuation semantics remain intact. Log redacted component counts/digests, method and margin, not prompts.

Proposed v1 reference envelope (ordinary values, never a SQLite connection or capability to arbitrary paths):

```json
{"v":1,"ref_id":"ref-17","lifetime":"durable","library_id":"lib-A","source":{"kind":"evidence","id":"existing-evidence-id","revision_sha256":"<64 hex>","locator":{"kind":"text_span","start":420,"end":690,"unit":"unicode_codepoint"},"representation":"utf8-text-v1"},"scope_ref":"session-event-ref","manifest_ref":".librarian/results/ref-17.json","state":"available"}
```

The Core validates ref IDs and resolves its own allowlisted sidecar; `manifest_ref` is descriptive, not caller-supplied file authority. Persist exact large-result payloads as immutable private sidecar blobs or unframed evidence only when the content fits EvidenceStore's data contract. Search-result sets containing project context must **not** be forced into EvidenceStore, whose structural framing prohibition remains. Sidecar identifies payload digest/length, origin, source versions, access requirements and withdrawal state. Quota/retention policy is explicit per library. Required resumable references are pinned by Session usage; TTL eviction applies only to expendable previews/caches. A missing durable payload returns unavailable, never a recreated newer payload under the same identity.

Existing Loop handles remain private ephemeral previews. Promotion to a parent-readable durable reference is explicit through the Core and current access checks; it does not expose child-private context. Locator interpretation is tied to the stored representation; byte offsets and codepoint offsets never mix. Outcomes: `available`, `changed`, `missing`, `expired`, `forbidden`, `withdrawn`, `integrity_failed`; filtered callers receive only permitted diagnostics.

Default scope/retention policy for this addendum: a durable reference inherits the originating library and intersection of source access with admitted parent work; cross-project sharing is opt-in through existing authorized promotion/configuration, never inferred by similarity. Worker-private results remain child-only until an explicit allowed result packet shares them. Active Session-required references are pinned until the Session's explicit archival/withdrawal policy releases them; derived caches may be evicted without deleting snapshots or canonical constraints. No automatic age-based deletion of evidence/history is introduced. Withdrawal appends an eligibility change through existing Session/manifest ownership and disables current retrieval/merge across derivatives; it is not physical erasure. Physical deletion remains a distinct explicit source operation, leaving only permitted audit metadata and an unavailable outcome for deleted bytes. Historical retrieval rechecks access and never promises to reopen bytes deliberately removed. Numeric storage ceilings must be configured and tested before durable-reference admission; exhausting a ceiling refuses new durable retention rather than evicting active required evidence.

### 2.2 Worker and service envelopes

```json
{"type":"worker_requested","v":1,"operation_id":"op-1","child_id":"w-1","parent_session":"s-1","library_id":"lib-A","input_snapshot":{"epoch":4,"contract_revision":2,"requirements":{"R1":3},"evidence_refs":["ref-17"]},"question":"bounded question","constraint_refs":["s-1:event-12"],"scope":{"project_id":"P","role":"research_helper","roots":["Sources"]},"allowance":{"reservation_id":"res-1","max_calls":3,"max_tokens":8000},"result_contract":"worker-result-v1"}
{"type":"worker_result_received","v":1,"operation_id":"op-1","child_id":"w-1","input_snapshot_digest":"<64 hex>","result_ref":"ref-18","findings":[{"text":"advisory finding","evidence_refs":["ref-17"],"origin":"inferred"}],"caveats":["limited span"],"conflicts":[],"unresolved":[],"stop":"completed","coverage":"partial","overflow_ref":null,"usage":{"receipt_refs":["receipt-1"],"state":"known"}}
{"type":"worker_merge_decided","v":1,"operation_id":"op-1","child_id":"w-1","result_digest":"<64 hex>","decision":"stale","checked_parent_epoch":5,"reason":"requirement changed"}
```

These payloads extend existing Session JSONL, not an additional worker log. Stable merge key is `(library_id,parent_session,child_id,operation_id,result_digest)`; same child/operation with a different digest is a conflict to resolve, not a fresh accepted effect. Core serializes current-state check and durable decision append through existing writer authority. A received result is a proposal; merge acceptance does not itself run a verifier, publish a note, or close a predicate. Replayed receipt settlement is idempotent independently of editorial acceptance.

Common service metadata is carried outside Clerk/Scribe neutral prompts: `operation_id`, `attempt_id`, `parent_session`, `child_id`, `library_id`, `input_sha256`, route/adapter/configuration digests, reservation/receipt IDs, deadline, cancellation generation, output evidence IDs and coverage. Error taxonomy: configuration, authentication, quota, transient_transport, invalid_output, cancelled, stale_assignment, outcome_unknown, with safe original codes retained. Capture, OCR, cleanup, search, TTS and STT charge actual usage if known, conservative reserve otherwise; cache hits link original receipts without billing twice. TTS's personal cap uses a short process-safe file lock plus durable reservation records beside its current user-level ledger, across vault Cores. Expiry is not automatic refund.

If a provider reports actual cost above the reserved bound, record the full actual liability and halt further discretionary dispatch; never hide the overrun to preserve a cap claim. Qualification must establish defensible upper-bound reservations and output limits. Where a true upper bound is unavailable, label estimated monetary enforcement explicitly and do not claim a hard financial guarantee.

## 3. Native ingestion, workflow and migration contracts

'''
native_specs=[
('N-01 / NAT-01','Deep-read reuse key = source full-byte revision + chunker/version + ordered chunk digest + extraction route/recipe identity. Reuse unchanged chunks by digest; legacy count-only records become stale.','Same-count edit and reorder cannot inherit extracted claims; unchanged chunks demonstrably reuse.','MF-013'),
('N-02 / NAT-02','Within one IndexService transaction, remove vanished non-document rows, reconcile stable document IDs, transfer document chunks only for unambiguous matching attachment manifests, then purge settled orphans. Live-note joins exclude unresolved orphan chunks.','Move keeps chunk IDs/text/FTS/vector identity; ambiguous copy and changed attachment never cross-attach; injected crash rolls back whole movement.','MF-014'),
('N-03 / NAT-03','Preserve publish → release owners → compute → derived CAS commit → writer CAS settlement. Pending marker/staged record remains recovery authority; bind operation/source/representation/chunk manifest. No vector-job database.','Blocked encoder leaves unrelated work live; source/route change rejects settlement; inserted/skipped counters reflect actual rows; active Core never enters offline fallback.','MF-022'),
('N-06 / NAT-06','Snapshot recursive workflow closure and route targets at start into existing evidence; resume only pinned definitions or explicit drift refusal.','Nested child edit cannot execute unseen; unknown action/code/cycle refused; unchanged closure resumes.','MF-017'),
('N-07 / NAT-07','Validated replay enum never/read_only/reconcile; mutation default never. Shared RunStore helper for intent/result and existing operation recovery; macro expanded plan approval retained.','Death before dispatch, after effect, before result produces provable reuse/retry or outcome_unknown; no blind external send/push retry.','MF-018'),
('N-08 / NAT-08','Recipe binds exact commit/tree/image/input/environment/argv/dependency/verifier digests, allowed effects, outputs and replay mode. Latest is a new-version run.','Mismatch refuses; missing input/tool could-not-run; stored replay has no side effects; changed environment gets new run derived_from old.','MF-023'),
('N-09 / NAT-09','All inner Clerk/Scribe/Scout work has operation/parent/reservation/deadline identity without project framing in source-description prompts. Effort log failure is observable before claiming persisted change.','Browser/MCP/batch/worker receipts agree; repairs charged; cancelled task starts no new inner calls; concurrent limits isolated.','MF-024'),
('N-12 / NAT-12','PDF/OCR/search use common envelopes, raw/derived manifests and page/span coverage; stop between pages/chunks and retain already-dispatched liabilities.','Partial coverage survives; cleanup not mislabeled original; cancelled chunks not sent; backend/route changes invalidate incompatible cache.','MF-028'),
('N-13 / NAT-13','Read V1 note once, parse those bytes, retain full digest. Batch reuse key `(library_id,item_id,input_revision,stage,stage_version,route_or_recipe_digest)`; earliest affected dependent stage reruns.','Concurrent source change yields one consistent snapshot or refusal; old completion cannot cover new content; post-wait stale output cannot commit.','MF-020'),
('N-14 / NAT-14','Import manifest accumulates stable source_root_id/source revision/target mapping, attachment hashes and every edge disposition across batches. Histories are inert evidence.','Alias/rename/missing endpoint/attachment fixture accounts for every item; no guessed edge; repeated batches retain mappings; V1 bytes unchanged.','MF-029'),
('N-17 / NAT-17','Docs/Cowork prompts describe only actual tool contracts and recovery semantics. Do not equate replay with exactly-once, capture bounds with disk quota, or extraction with truth.','Current source/tool-name and test-target checks plus per-packet result links; historical records explicitly superseded.','MF-042'),
]
spec+=table(['Requirement','Contract','Acceptance','Owner'],native_specs)
spec+='Native detailed derivation: '+link(NAT+'DESIGNS.md',5)+'; '+link(NAT+'PACKETS.md',7)+'.\n\n'
spec+='''### 3.1 Run JSONL and recovery

```json
{"type":"run.started","v":2,"run_id":"run-1","recipe_manifest":"evidence-ref","input_manifest":"<64 hex>","scope_ref":"session-event-ref","environment_manifest":"sidecar-ref","parent_session":"s-1","replay_mode":"execute"}
{"type":"step_intent","v":1,"step_key":"run-1/step-2","attempt_id":"a-1","operation_id":"op-2","input_digest":"<64 hex>","definition_digest":"<64 hex>","expected_revisions":{"Sources/A.md":"opaque-revision-token"},"replay":"reconcile"}
{"type":"step_result","v":1,"step_key":"run-1/step-2","attempt_id":"a-1","operation_id":"op-2","result_handle":"ref-19","result_digest":"<64 hex>","receipt_refs":["receipt-2"],"verifier_result":{"state":"pass","verifier":"declared-version"}}
```

Extend current RunStore envelope, preserving old replay readers through explicit version handling. Intent precedes effect; the gap between effect and result is reconciled against existing durable target/operation receipts. A cursor cannot prove an external effect occurred exactly once. `resume` continues interrupted work, `replay` reads retained evidence without execution, `rerun` creates a new linked run on newly declared inputs. A changed goal/lens invalidates dependent reuse, not unrelated history.

## 4. Windows/WSL2 Docker resource and teardown contract

**N-04 (MF-015).** Artifact outputs are disk-backed, never charged to RAM-backed tmpfs. No custom in-container supervisor daemon. Preflight records Docker Desktop/engine/WSL/storage-driver identity, digest-pinned image, available backing storage, intended byte/inode ceiling, setup/log/export amplification, global concurrent reservations and quota enforcement capability. A Docker flag accepted syntactically is not qualification. A global WSL VHD cap alone does not prove per-run quota or protect unrelated data. Named volumes or overlay writable layers are not assumed to have usable per-run quotas on Windows.

Qualify a supported native disk-backed quota configuration with rapid-write and tiny-file floods. If the active backend cannot enforce the required byte/inode bound, the contained execution profile is unavailable with a precise preflight reason. A best-effort I/O monitor is additional protection, not a substitute for the hard bound. This is an explicit remaining implementation/host qualification gate. Do not promise a universally working Docker Desktop storage-opt recipe without evidence.

**N-05 (MF-016).** Create/start containers **without `--rm`**. Sources/inputs are read-only and network/CPU/memory/process limits remain existing policy. Native host-side capture owns shared counters for total stdout/stderr and I/O monitoring; overflow/deadline/cancel requests one idempotent stop. Count produced bytes separately from retained tail bytes. Document sampling/buffer overshoot and keep it within predeclared tolerances; never label polling exact containment.

State machine:

```text
preflight -> reserved -> created -> running -> stop_requested
 -> stopped_verified -> export_quarantine -> validated -> disposed
                           |                    |
                           +-> rejected --------+
stop/inspect uncertainty -> cleanup_unknown (no success/promotion)
```

Call docker stop, escalate docker kill as required, wait and inspect that the entire producer container is stopped before export. The stopped filesystem is inert; do not restart it to retrieve artifacts. Use bounded `docker cp <container>:<output> -` tar stream into a private host quarantine. Reject absolute/drive/UNC paths, traversal, alternate streams/reparse hazards, symlinks/hardlinks, devices/FIFOs, duplicate or case-colliding destinations, excessive depth/name length/member count and truncated/sparse-overflow payloads. Count directories and metadata as well as regular files. Check remaining byte/count budget before allocating each destination/write; hash while streaming. No accepted/indexed/executable artifact until the entire manifest passes policy. `docker rm` follows export disposition; failed disposal is reported explicitly, not hidden behind success. Quarantine retention is bounded and visible in the existing run record, not a new job database.

```json
{"execution_v":2,"state":"quarantined","stop_reason":"output_quota","container_id":"nonsecret-id","limits":{"artifact_bytes":52428800,"artifact_entries":200,"stdout_bytes":1048576,"stderr_bytes":1048576},"quota":{"backend":"qualified-disk-backend-id","verified":true,"evidence_ref":"quota-check-ref"},"observed":{"artifact_bytes":8192,"artifact_entries":2,"stdout_bytes":1048577},"cleanup":"verified","export":{"complete":false,"manifest_ref":null},"environment":{"image_digest":"sha256:...","source_commit":"...","source_tree":"...","runtime_version":"...","platform":"windows-wsl2","input_manifest":"sha256:...","argv_digest":"sha256:...","dependency_manifest":"sha256:...","network":"none"}}
```

Numbers above are provisional test-policy examples, not measured optimal defaults. Teardown verification, export completeness, validation and disposal are separate facts. A stopped container can have an incomplete export; `cleanup_unknown` prohibits a safe-completion label. Claim Run stays Docker-only. Person-confirmed `non_isolated_host_exec` remains a distinct Workbench choice with no network-isolation promise, never automatic fallback.

Acceptance: real declared backend tests byte/tiny-file floods, stdout/stderr floods, cancellation, failed kill/inspect, child processes, malformed tar, setup/export concurrency and benign exact hashes. Fake-runner tests supplement but cannot close NAT-04/05.

## 5. Evolving knowledge integrated with DIK and closure

### 5.1 Module responsibilities and authority

'''
spec+=table(['Existing module','Extension / invariant','Acceptance'],[
(link('src/resource_librarian/facts.py',697),'Keep deterministic catalogue derivation; bind observed facts to source snapshot/version. Do not turn it into a free-form conversational belief writer.','Same snapshot yields same facts; application scope never alters neutral source description.'),
(link('src/resource_librarian/dik.py',65),'Reuse stable datum/edge IDs, origins and typed relationships. Derived DIK JSON gains links to temporal/support manifests; accepted Markdown and evidence remain reconstruction inputs.','Observed/static/source-stated/inferred stay distinct after rebuild; relations retain direction/negation/qualifiers.'),
(link('src/resource_librarian/evidence.py',77),'Immutable unframed captures; add narrowly validated note_snapshot evidence kind if needed. Store bytes/digests/locators here, scope/approval in Session/sidecars.','Snapshot intact after overwrite; FRAMING_KEYS guard unchanged; project/session metadata cannot enter raw evidence.'),
(link('src/resource_librarian/closure.py',156),'Current applicability/coverage can block reuse; only existing person-named exact/bounded verifier and contract may establish authoritative closure.','Accepted claim, lesson or support graph cannot close a predicate by itself; stale checks refused.'),
(link('src/resource_librarian/closure_audit.py',150),'Recheck current retained evidence and verifier receipts; reference temporal/support state for explanatory invalidation.','Independent check and rerun explicitly distinguished; no hidden relaxation of closure strength.'),
(link('src/resource_librarian/agenda.py',76),'Derive recheck/review work through existing Markdown task/session mechanisms; no second scheduler or authority to auto-edit goals.','Source change yields bounded review proposal; completion of a reminder does not imply verification.'),
])
spec+='''### 5.2 Frontmatter, sidecars and immutable history

Content-model change is explicitly reviewed through `About/Note Content Model.md`; `schema.py` validates it and leaves legacy notes valid. Prefer an optional nested `knowledge` block to avoid colliding with existing top-level lifecycle status:

```yaml
knowledge:
  claim_id: claim-42
  status: accepted
  valid_from: 2026-10-01T00:00:00Z
  valid_until: null
  supersedes: [claim-42-r1]
```

`accepted` means editorial acceptance, not general truth. `valid_from: null` means unspecified start, not a known infinite past; absent metadata means temporally unspecified. `valid_until: null` means no stated end, not proof of permanent validity. Multi-claim notes use `knowledge.claims` entries with unique claim_id and stable section anchor, validated as a separate schema variant. Human authors never maintain long premise/evidence/locator SHA-256 lists in YAML.

The immutable proposed `.librarian/knowledge/revisions/<revision_id>.json` manifest binds full note bytes and DIK lineage. This is Core-written metadata for existing note/evidence authority, not a separately editable belief store:

```json
{"v":1,"library_id":"lib-A","claim_id":"claim-42","revision_id":"claim-42-r2","operation_id":"op-42","library_revision_seq":12,"note_path":"Notes/Claim.md","section_anchor":null,"note_sha256":"<64 hex>","snapshot_id":"unframed-note-snapshot-id","scope":{"project_id":"P","goal_epoch":3,"lens_digest":"<64 hex>"},"origin":"inferred","epistemic_status":"source-stated","lifecycle":"reusable","applicability":"unknown","dependency_coverage":"complete_declared","recorded_event":{"session_id":"s-1","position":18,"hash":"existing-chain-hash"},"support_sets":[{"id":"S1","coverage":"complete_declared","premises":[{"id":"datum:source-9:page4","revision":"rev-9","evidence_id":"ev-9","evidence_sha256":"<64 hex>","locator":{"kind":"page","page":4},"locator_sha256":"<64 hex>"}]}],"conflicts_with":[],"lesson":{"episode_refs":["s-1:10-17"],"assumptions":["tool T available"],"failure_conditions":["missing T"],"qualification_refs":[],"counterexamples":[]}}
```

Full SHA-256 fields supplement existing shortened EvidenceStore IDs and Session chain hashes; they do not reinterpret those existing IDs as full hashes. Raw note snapshot payload contains only path/content/encoding/digest, not project or reasons. Framed scope/lesson/approval belongs in the manifest and owning Session.

Proposed Session payload (store adds the existing `t` and `h`; do not change hash algorithm):

```json
{"type":"knowledge_revision","v":1,"operation_id":"op-42","claim_id":"claim-42","revision_id":"claim-42-r2","prior_revision":"claim-42-r1","manifest_ref":".librarian/knowledge/revisions/claim-42-r2.json","manifest_sha256":"<64 hex>","decision":"accept","reason":"authorized correction","library_revision_seq":12}
```

The existing envelope is flat JSONL with Core timestamp `t` and chained `h`, not a fabricated new `payload/seq/prev_hash` wrapper. Event position is the Session line order. For cross-session temporal ordering, Core reserves a monotonically increasing **library revision sequence** through its existing writer operation-intent/recovery seam and persists that sequence in immutable manifests/events; reconstruct the next value from retained committed records, never solely from SQLite. A crashed reservation may leave a gap, never reuse a committed number. A revision becomes eligible only when the existing operation disposition confirms all required note/snapshot/manifest/event writes; incomplete operations yield recovery checkpoints and unknown state, not speculative acceptance. This does not claim a filesystem/JSONL atomic transaction.

Event validation: `knowledge_revision.decision` is `accept`, `dispute`, `withdraw` or `correct`; `observed_external_revision` never implies any of those authorizations. Each carries operation/revision/manifest identity, recorded sequence and safe reason; withdrawal identifies the affected revision/scope and invalidates current derived eligibility. `worker_requested`, `worker_result_received` and `worker_merge_decided` retain their separate phases; merge decision is `accepted`, `stale`, `duplicate`, `conflict`, `forbidden` or `partial`. Unknown new envelope versions cannot execute effects. New public tool callers cannot supply trusted Core recording time, chain hash or sequence; importer-observed historical timestamps stay data fields. Snapshot/manifest integrity and replay compatibility tests cover every event kind.

Retain old full bytes before approved overwrite. Manual external edits generate `observed_external_revision` at observation time with current snapshot and unknown approval; never backdate when Core knew it or resurrect an accepted state from arbitrary YAML. New accepted revision must match the reviewed source fingerprint/CAS; later edits immediately make that projection stale. Historical access remains subject to current permissions.

### 5.3 Exact proposed SQLite migration

These are **new derived tables**, owned by the current IndexService connection and schema migration machinery. Reserve the next schema version at implementation time (baseline is schema 5); do not mutate this checkout. Foreign keys refer only to locally projected revision identities; evidence/premise resolution is validated by Core, with missing references explicit. UTC timestamps are canonical fixed-format strings validated before insertion; SQL checks are a second guard, not a timestamp parser.

'''
SQL='''CREATE TABLE claim_revision (
  library_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  revision_id TEXT NOT NULL,
  scope_key TEXT NOT NULL,
  note_path TEXT NOT NULL,
  section_anchor TEXT,
  snapshot_id TEXT NOT NULL,
  note_sha256 TEXT NOT NULL CHECK(length(note_sha256)=64),
  manifest_sha256 TEXT NOT NULL CHECK(length(manifest_sha256)=64),
  valid_from TEXT,
  valid_until TEXT,
  validity_known INTEGER NOT NULL CHECK(validity_known IN (0,1)),
  recorded_at TEXT NOT NULL,
  recorded_event TEXT NOT NULL,
  recorded_position INTEGER NOT NULL CHECK(recorded_position>=1),
  library_revision_seq INTEGER NOT NULL CHECK(library_revision_seq>=1),
  operation_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('accepted','disputed','withdrawn','unknown')),
  origin TEXT NOT NULL CHECK(origin IN ('person','observed','source-stated','derived','model-produced','inferred')),
  epistemic_status TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('working','reusable','archived','withdrawn')),
  dependency_coverage TEXT NOT NULL CHECK(dependency_coverage IN ('complete_declared','partial','unknown')),
  PRIMARY KEY(library_id,revision_id),
  UNIQUE(library_id,operation_id,claim_id),
  UNIQUE(library_id,library_revision_seq,claim_id),
  CHECK(valid_from IS NULL OR valid_until IS NULL OR valid_from<valid_until)
);
CREATE INDEX claim_revision_lookup ON claim_revision(library_id,scope_key,claim_id,library_revision_seq);
CREATE TABLE claim_supersedes (
  library_id TEXT NOT NULL, newer_revision TEXT NOT NULL, older_revision TEXT NOT NULL,
  PRIMARY KEY(library_id,newer_revision,older_revision),
  CHECK(newer_revision<>older_revision),
  FOREIGN KEY(library_id,newer_revision) REFERENCES claim_revision(library_id,revision_id)
);
CREATE TABLE claim_support_set (
  library_id TEXT NOT NULL, conclusion_revision TEXT NOT NULL, support_set TEXT NOT NULL,
  coverage TEXT NOT NULL CHECK(coverage IN ('complete_declared','partial','unknown')),
  PRIMARY KEY(library_id,conclusion_revision,support_set),
  FOREIGN KEY(library_id,conclusion_revision) REFERENCES claim_revision(library_id,revision_id)
);
CREATE TABLE claim_support (
  library_id TEXT NOT NULL, conclusion_revision TEXT NOT NULL, support_set TEXT NOT NULL,
  premise_id TEXT NOT NULL, premise_revision TEXT NOT NULL,
  evidence_id TEXT NOT NULL, evidence_sha256 TEXT NOT NULL CHECK(length(evidence_sha256)=64),
  locator_json TEXT NOT NULL, locator_sha256 TEXT NOT NULL CHECK(length(locator_sha256)=64),
  relation TEXT NOT NULL CHECK(relation IN ('supports','requires')),
  PRIMARY KEY(library_id,conclusion_revision,support_set,premise_id,premise_revision,evidence_id,locator_sha256),
  FOREIGN KEY(library_id,conclusion_revision,support_set)
    REFERENCES claim_support_set(library_id,conclusion_revision,support_set)
);
CREATE INDEX claim_support_reverse ON claim_support(library_id,premise_id,premise_revision);
CREATE TABLE claim_conflict (
  library_id TEXT NOT NULL, revision_id TEXT NOT NULL, other_revision TEXT NOT NULL,
  basis_manifest TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('proposed','unresolved','resolved')),
  PRIMARY KEY(library_id,revision_id,other_revision),
  FOREIGN KEY(library_id,revision_id) REFERENCES claim_revision(library_id,revision_id)
);
CREATE TABLE knowledge_episode (
  library_id TEXT NOT NULL, episode_id TEXT NOT NULL, scope_key TEXT NOT NULL,
  session_id TEXT NOT NULL, first_position INTEGER NOT NULL, last_position INTEGER NOT NULL,
  boundary_hash TEXT NOT NULL, source_revision TEXT NOT NULL, kind TEXT NOT NULL,
  lifecycle TEXT NOT NULL CHECK(lifecycle IN ('working','reusable','archived','withdrawn')),
  summary_ref TEXT, PRIMARY KEY(library_id,episode_id),
  CHECK(first_position>=1 AND last_position>=first_position)
);
CREATE INDEX knowledge_episode_scope ON knowledge_episode(library_id,scope_key,kind,lifecycle);
'''
spec+='```sql\n'+SQL+'```\n\n'
spec+='''A missing superseded revision is retained as an unresolved reference, which is why `older_revision` has no foreign key. Do not infer permission or validity from a successful SQL join. Scope keys are canonical versioned JSON encodings of library/project/session/goal/lens dimensions, not fuzzy text. All retrieval lanes authorize before exposing rows/counts/derived summaries. `knowledge_episode` is an approved-scope event-range lookup; it neither copies full transcripts into privileged prompts nor constitutes a new authority. Model summaries remain optional derived references.

Migration acceptance: empty and populated legacy indexes upgrade; invalid manifests are quarantined/skipped with explicit diagnostics; SQLite deletion/rebuild from Markdown/evidence/committed manifests/events reproduces identical eligible answers; orphan/missing references yield unknown; migration failure leaves original notes unchanged; rollback rebuilds the previous projection or declares unsupported reader rather than corrupting truth. All SQL runs in short IndexService transactions, never across network/encoder work.

### 5.4 Temporal and support semantics

Query modes are current, historical `(valid_at, known_at)`, compare and hypothetical. `known_at` may be a Core recorded-time cutoff or an exact library revision sequence. Select only committed observations known by that cutoff; evaluate half-open `[valid_from,valid_until)` when known. Unknown applicability time remains unknown. Supersession is scoped and interval-aware: a correction covering October does not globally hide an otherwise applicable September assertion. Newer timestamps alone do not settle disagreement between independent sources. Same known-time ordering must be deterministic across Sessions using the persisted library sequence, not comparison of unrelated Session positions.

Within a complete nonempty support set premises are AND; alternative complete sets are OR. Each premise must resolve to the required version, authorized scope and declared verification/applicability. Multiple summaries of one source remain one underlying support origin. Invalidate/re-evaluate reverse dependents to a bounded fixed point. A surviving independently sufficient set preserves supported eligibility. A cycle with no grounded external support contributes no support; partial/unknown coverage, cap overflow or unavailable evidence is unknown. Maintain conservative Session epoch invalidation for closure until the explicitly gated HARNESS-09 comparison proves a scoped optimization safe and worthwhile.

Conflicts are staged with reasons; person approval or the existing authorized workflow adopts revisions. Do not claim complete AGM postulates or a natural-language contradiction oracle. Goal/lens changes alter scoped applicability and query perspective, never hard permissions or neutral source facts. Preserve `{goal_epoch,content_model_hash,profile_digest,selected_lenses:[id,digest]}` in existing Session/run evidence. Hypothetical branches do not adopt goals.

A direct refutation or unresolved conflict is a separate epistemic state: surviving positive support does not erase it. The support evaluator reports support and conflict independently and cannot silently promote a disputed conclusion to verified closure.

Acceptance N-15/N-16: retroactive correction/current-vs-historical fixtures; partial interval supersession; unknown times; duplicate operation replay; independent vs conjunctive support; ungrounded cycles; incomplete dependencies; bounded overflow; scope isolation; manual note edits; withdrawn records surviving restart/rebuild; unchanged closure strength. Lessons retain episode/assumptions/outcome/failure/counterexample/check references and are qualified on unseen variants. Agent probe pass cannot satisfy a person's own-words understanding record or an execution predicate.

## 6. Backend payload bridges for honest UI

**U-B1 — durable stall/block reason (MF-010).** Add `reason` and `source` to `audit_projection._EVENT_KEYS`; fold latest blocked/stall disposition per requirement from existing durable events into `session_status`. Proposed additive `audit.blocked_reasons[rid] = {reason,source,event_ref,requirement_revision,epoch}`; validate actual event fields, preserve missing/legacy as unknown. UI correlates selected session/revision and shows real reason after restart. Counters are actual projected counters, never a hardcoded eight. Acceptance: stall, restart, reopen and explicit revision clear/update reason consistently; bounded event projection does not drop current blocked requirement explanation.

**U-B2 — bound reply review (MF-027, NAT-10).** Add `reply_id`, `turn_id`, exact canonical `note_path`, `source_revision`, evidence reference and `coverage:{checked_spans,unit,total_length,complete,truncated}` to review event/result shape. Reuse existing reply IDs if present; otherwise allocate stable IDs when transcript reply is appended. Root-relative paths, not basename guesses, identify citations; ambiguous link remains unchecked. Targeted spans beyond old 5,000-character prefix may be checked under budget; unexamined spans cannot be labeled contradicted. Count and token caps include missing-link challenges. Persist association through existing transcript/Session evidence, not a UI-owned challenge store. Late async results update only the original matching reply/revision; stale ones remain historical or are discarded with explicit status. Advice is not a veto or verification. Acceptance: duplicate filenames, late evidence, rapid new turn, source edits, challenge floods, resume and unknown legacy events.

**U-B3 — composed staging preview (MF-027).** Extend `staging_show` with `preview:{kind,current_markdown,composed_markdown,sections,source_revision,staged_revision,dependency_digest,preview_digest}` generated by the same server composition/preparation logic used for source promotion, with **no writes**. Obtain current bytes/tokens from one reviewed snapshot. Keep existing opaque review/revision-CAS tokens authoritative; preview_digest is not authorization. Any edited proposal field or changed source/dependency invalidates local preview and requires a refreshed preview/token check. Acceptance refuses stale tokens exactly as today. Before/after UI displays these composed bytes, not a browser approximation. If composition cannot be determined, return typed conflict/needs-input with no actionable accept, rather than a permanent missing-payload banner. Taxonomy membership review stays semantic unless its exact multi-file prepared writes are also exposed under a separately bounded extension.

Bridge code anchors: '''+link('src/resource_librarian/audit_projection.py',36)+'; '+link('src/resource_librarian/session.py',1143)+'; '+link('src/resource_librarian/reply_review.py',38)+'; '+link('src/resource_librarian/tools/staging.py',1)+'.\n\n'
spec+='''## 7. UI contracts: D1..D6 reconciled

### 7.1 Projection, actions and oversight

D1 stays a view over existing authenticated Api/Core operations plus U-B1..3. Transient pending flags prevent duplicate clicks; they do not create authoritative workflow state. Health uses `Promise.allSettled`, individual unavailable results, bounded nonoverlapping refresh while visible, disposal cancellation and manual refresh. SSE connectivity is separate from lease/writer/index/watcher/shutdown health. Index counts are snapshots, never invented percentages or ETA. Accepted notes and derived embedding failure remain separately visible. General embedding-job/quarantine-history APIs are not created by implication; immediate NAT receipts are rendered when available. Offline G5 ledger is not live runtime task spend.

D2 requires truthful action transitions: draft/attachments retained through admission; success clears only submitted snapshot; ambiguous transport causes inspection, not automatic resend. Busy Enter preserves next draft; explicit Stop shows pending until canonical stop. Failed mode/effort/model/service/Forget mutation restores last confirmed state and visible error. “Mark reviewed; retry manually” only records its checkpoint choice. Approved execution checkpoint still requires a separate person start with matching ID. Library force-switch describes leaving work running with possible failure/wait, not guaranteed completion. Remove-reference never deletes uploaded Inbox bytes.

D3 renders legacy/invalid banner before empty inspector return, uses actual nonempty legacy/invalid values, blocks history mutations and offers a new audited session. File edits and stale requirements are listed separately until real dependency evidence supports a causal link. Requirement text edits preserve full predicates/verifier parameter objects and closure. Existing set_requirement has no revision-CAS parameter: reread detects known changes but is not atomic CAS; do not claim otherwise. U-B1 supplies resumed stop reasons. Refusal details, predicate detail and skeleton are progressive disclosures, retaining focus/open state by stable identity. Skeleton is proposed, not admitted; fits=false cannot lead to admission.

D4 uses server-composed staging preview, bound advisory reply review and visible Docker preflight. Keep accepted/captured/full-depth/source-stated/quote-located/arithmetic/replicated/person-accepted meanings separate. Claim Run never falls back to host execution. Workbench host mode explicitly says network isolation is not enforced and requires current person/checkpoint confirmations. Failed teardown or incomplete export cannot show safely quarantined/replicated success.

'''
spec+=table(['Requirement / aliases','Acceptance contract','Owner'],[
('U-01 / UI-01','409, network loss, duplicate Enter, later edits and attached references survive correctly; explicit cancel distinct.','MF-005'),
('U-02 / UI-02','Every rejected mutation visibly rolls back confirmed state; checkpoint action makes zero effect replay; normal mount retry never takes over.','MF-006'),
('U-07 / UI-07','Empty legacy and invalid histories visibly read-only; new session separate; stale evidence not green.','MF-009'),
('U-08 / UI-08','Restart preserves reason/source; revision request retains predicate/verifier objects; skeleton/refusal detail available without flooding chat.','MF-010'),
('U-09 / UI-09','Connected stream with failed writer still warns in all tabs; dirty paths visible; stale health labeled last reported; no polling after dispose.','MF-026'),
('U-10 / UI-10','Bound late reviews never attach to latest reply by arrival; exact source spans open; composed preview matches preparation; stale CAS refuses; unavailable Docker sends no execution request.','MF-027'),
])
spec+='''### 7.2 D5: DOM/CSS containment and root-width layout

Canonical DOM skeleton:

```html
<div class="librarian-root" data-lib-instance="unique">
  <div class="lib-app">
    <header class="lib-header"><!-- Settings and Choose models remain reachable --></header>
    <section class="lib-operations" aria-label="Operations"></section>
    <div class="lib-body"><main class="lib-main"></main><aside class="lib-pane"></aside></div>
  </div>
  <dialog class="lib-dialog lib-settings" aria-labelledby="unique-settings-title"></dialog>
</div>
```

```css
.librarian-root {
  container-type: inline-size;
  container-name: librarian;
  min-inline-size: 0;
}
.librarian-root .lib-app { min-inline-size: 0; }
.librarian-root dialog.lib-dialog {
  box-sizing: border-box;
  max-inline-size: min(1120px, var(--lib-dialog-max-width));
  max-block-size: min(820px, var(--lib-dialog-max-height));
}
.librarian-root dialog.lib-dialog::backdrop { background: rgb(0 0 0 / 25%); }
.librarian-root dialog.lib-dialog .lib-page { min-inline-size: 0; }
@container librarian (max-width: 999px) {
  .librarian-root .lib-body { display: block; }
}
@container librarian (max-width: 839px) {
  .librarian-root .lib-settings-rail { display: none; }
  .librarian-root .lib-settings-category { display: block; }
}
@container librarian (max-width: 599px) {
  .librarian-root .lib-search-controls { grid-template-columns: minmax(0, 1fr); }
}
```

CSS queries descendants of the named root, not the container itself. Queries are the primary responsive mechanism; ResizeObserver measures available root width/height and clamps persisted split widths, top-layer dialog dimensions/position and popovers. Top-layer dialog geometry must be tested in both hosts because viewport-centred native placement is not root containment: compute root bounds on open/resize, set owned coordinates and available max dimensions, and keep the dialog's DOM ancestry rooted. No body-portal framework. Use viewport intersection to cap root geometry, preserving 12px each side (24px total) where space permits. Dispose observer/listeners/timers and reject delayed results from previous mount/library/session generations.

Wide roots >=1000px use main >=360px and pane >=300px if those minima fit. Compact roots 600–999px use explicit document overlay with return action. Narrow roots stack queue/detail/evidence, preserve draft and selected note, and offer Back to items/chat. Separate saved desktop split preference from transient narrow overlay state. Settings uses 1120×820 maximum rather than the superseded generic 680px cap; ordinary small dialogs may stay narrower. Sidebar becomes labelled selector/drawer below ~840px. Breakpoints are proposed design constants to validate, not research-derived universal thresholds.

Every outgoing dialog selector, including comma branches and backdrop/descendants, starts `.librarian-root dialog.lib-dialog`. Namespace high-collision generic owned tokens (`row`, `row2`, `item`, `list`, `title`, `body`, `header`, `badge`, `tabs`, `page`, `slot`, `primary`, `ghost`, `opt`, `active`, `error`, etc.) in every emitter, CSS, event selector and test. Preserve host-owned integration classes only at adapter boundaries. Local custom properties use `--lib-*`. No global dialog/button/input/select/textarea/*/:root reset. Use surgical owned control baselines (height:auto, min-height:0, wrapping, line-height, margin, box-sizing); no broad all:initial. Retain the proven model-card/popover/grid fix. Namespacing does not promise immunity to arbitrary hostile !important rules targeting new names.

Acceptance U-03/U-04: inventory all 309 CSS rule headers and 113 main/panels declarations from source appendices plus other emitters; foreign dialog computed styles unchanged; hostile old generic selectors do not collapse owned controls; 320/420/760/1100 root widths within 1440 window and short-height leaf; 420px Search input >=280px; saved oversize split clamped; dialog/popover stays within visible root; generated assets match source builds.

### 7.3 D6: focus, touch and navigation

U-05: focus first usable popover control after async content arrives; nonmodal Tab may leave and closes predictably; native dialog owns modal focus trap. Escape closes innermost owned surface and consumes only handled events originating there; outside leaves keep their keys. Restore focus only when appropriate. IDs/radio groups are mount-unique; disposal removes all listeners. Real Obsidian capture hotkeys require real-host evidence beyond synthetic bubble tests.

U-06: tabs use roving tabindex, Arrow/Home/End and panel relations; splitter supports bounded keyboard adjustments and aria min/max/current; touch long-press cancels on movement/touchcancel and suppresses following click; visible actions supplement hover. Reduced-motion disables action fades. Acceptance includes two mounts, dispose/remount, async focus, keyboard-only complete journeys, touch cancellation and screen-reader-oriented labels. No formal accessibility compliance claim is inferred.

U-11: role-first selection for Lead, Notes and Small tasks; preserve existing ordered-tier/backend binding semantics, qualification and explicit override. Clearing a middle slot cannot silently shift later roles; if current API only supports a prefix, disclose its consequence or use honest clear-all. Service clear remains a service mutation. State/readiness/tested/qualified are distinct.

## 8. Settings, staging and search workspace

### 8.1 Left-sidebar Settings contract (U-12A)

Persistent header controls **Settings** and **Choose models** are available in Chat, Staging and Search. Settings is a native root-contained dialog, max 1120×820, 224px stable left rail, flexible content with 28–32px padding and approximately 760px readable form width. One main content scroller; header/Close/navigation available while scrolling. Long rail may scroll when necessary, but cards do not become independent scroll traps. Narrow root uses labelled category selector/drawer and clear Close/Back.

'''
settings_rows=[
('Environment','Providers & keys','Provider/host/key summary; selected-provider detail; Edit connection advanced URL/timeouts/concurrency; Save connection separate from Save key; last connection test separate from qualification.','/api/keys, /api/hosts, /api/usage'),
('Environment','Tools & integrations','Installed-for-user and enabled-for-library states; server summary then per-tool Allow/Ask/Deny; filter; advanced installation actions explicitly scoped. No new Allow all.','Existing /api/mcp family; /api/tool-setting'),
('Current library','Models & services','Named chat roles; separate OCR/read-aloud/STT/embedding cards; model catalogue/qualification details secondary; embedding coverage distinct from retrieval quality.','/api/state, /api/tiers, /api/services'),
('Current library','Chat behaviour','Context for chat replies; Short/Long/Custom with conditional custom input; Answer/Coach and learn-session override explanation.','/api/context'),
('Current library','Review & promotion','Publish authority distinct from advisory checks; direct reviewer-role link; distribution posture.','/api/library'),
('Current library','Project access','Master access, folder read/edit state, explicit write approvals; explain metadata creation before adding folder.','Existing /api/projects operations'),
('Current library','Methods & lenses','Domain initialization profile, available packs, inspected/accepted methods; pack acceptance distinct from session lens adoption.','library_profile, lens_packs, lens_pack_accept'),
('Current library','Topics & organisation','Topics/unfiled/proposals/refile; links back to staging; separate maintenance commands from preferences.','topics_list, topic_propose, staging_decide, views_refresh'),
('Advanced','Agent profiles','Permission ceilings, tool bundles, route restrictions, explicit profile editing/history.','/api/profiles, /api/agent-profile and existing history'),
('Advanced','Health & diagnostics','Actionable warning summary, installation capabilities, integrity and route/qualification detail; safe support metadata and key-migration actions.','/api/library doctor payload; /api/meta'),
]
spec+=table(['Group','Page','Presentation','Existing contract'],settings_rows)
spec+='''Control-level scope labels govern, not category headings alone. Host/key definitions are computer/account scoped; Obsidian-managed credentials lead to SecretStorage. Services, context, review policy, roots, accepted packs and profile definitions are library scoped. **Chat tiers, lead overrides and effort also update shared defaults used by libraries without their own choices.** Explain this next to affected controls; do not claim every existing library changes immediately or infer inheritance from equal values. Session lens adoption remains thread scoped.

Forms retain explicit Save/Cancel; immediate toggles show Saving/Saved/error and revert on failure. No global Save all. Preserve category, scroll and unsaved edits; closing offers Save/Discard/Stay for applicable forms; switching libraries must never submit old-library data into the new one. Navigation warns before discarding edits, not silently saves them. Commands such as Test, Measure, Propose and Rewrite have separate pending/result feedback. No paid probe on page load. Actionable warnings stay visible and deep-link to the relevant category; technical records stay expandable. Retain warm neutral palette, white edit fields, stronger selected navigation and readable evidence; numerical typography/colour effects require actual validation.

Acceptance: all ten categories reachable by keyboard at desktop/420px/short root; provider setup does not require opening Agent profiles; changing Notes preserves Lead; SecretStorage ownership preserved; shared-default side effect visible; failed Save stays dirty with error; close/reopen and cross-workflow return retains state; stale library callback discarded.

### 8.2 Right pane and Staging (U-12B)

Visible view switching **Note / Browse / Plan / This week** is separate from current-note **⋮** actions and **🔊 Read aloud** with explicit playback state. Narrow pane may use labelled View selector. Keep Desk/pins and recent notes reachable without confusing them with settings. Empty Plan does not consume half the review surface; explicit user-opened content remains recoverable after resize.

Staging hierarchy is queue → selected state/next action → form and evidence → decision. Compact queue has obvious selection; scoped counts explain current filter versus library totals. Evidence is a readable proportional-text surface, with monospace only for code/raw extraction. Wide layout gives draft and evidence useful width; narrow layout stacks with Back to items and retained edits. Selecting evidence must not silently overwrite an unrelated open document.

Distinguish **Approve for processing** (read/prepare for later review) from **Keep captured version** (publish limited available capture under existing rules), **Accept reviewed draft**, **Defer** and **Reject**. Hide secondary reason fields until applicable without bypassing required person judgments or coverage checks. Bulk actions in scope are **defer** and **approve-for-processing only**. Snapshot selected IDs, library and current revision tokens; apply bounded existing per-item person decisions; report each success/refusal/stale item, retain unresolved selection, stop on library change/cancel. No bulk publish, fabricated evidence review or implicit payment authority. Retrying uncertain outcome requires current-state inspection.

Acceptance: six-item mixed-state bulk fixture changes only eligible selected items, preserves rejected/stale items and reports partial results; never calls publication acceptance; queued work uses existing budgets/permissions. Settings roundtrip and source preview refresh preserve edits or explicitly request discard. Evidence/claim/revision can be located and explained.

### 8.3 Search (U-12C)

First row: labelled full-width query with usable Submit. Second row: readable scope/intent/date/source filters wrapping or disclosed at narrow widths. Never shrink selected values into fragments. Preserve query/filter selection across results and pane changes. Search depth/score/coverage/advisories are not truth ratings. Empty states offer a few real actions (find source, review captured item, resume session), not decorative pseudo-features.

Acceptance: 390px viewport and 420px leaf within wide window keep readable active filters and query; text zoom and short height retain actions; open result then return keeps query/context. Actual human usefulness and findability measured separately from automated selectors.

### 8.4 Four implementation steps and evaluation criteria

Reconcile the four-step summary with the detailed source's five numbered entries by keeping verification as an exit condition of every step: (1) larger shell/header/left navigation MF-032; (2) redistribute controls and preserve pending forms MF-032; (3) simplify providers/models/tools MF-031/033; (4) connect related workflows, pane/Staging/Search and return state MF-034. MF-035 verifies the integrated result. This does not create a duplicate fifth implementation program.

'''
spec+=table(['QA criterion','Acceptance observation / owner'],[
('L01','New user locates Settings/provider setup without hints; MF-032/035.'),('L02','Readable query/scope at tested widths; MF-008/034.'),('L03','Resize/open/close pane preserves task and draft; MF-008/025/034.'),('L04','Replace Notes only and explain result; MF-031.'),('L05','User distinguishes selected/connection-tested/qualified; MF-031/033.'),('L06','Locate cited evidence and explain limitation before review; MF-027/034.'),('L07','Explain captured/queued/processed/accepted and bulk consequences; MF-034.'),('L08','Recover interrupted/stale review without lost edits or duplicated effect; MF-006/027/035.'),('L09','Explain write scope before approval and retain Ask/Deny; MF-006/033.'),('L10','Complete a first meaningful task from empty screen; MF-034/035.'),('L11','Find ordinary provider/service setup without unrelated advanced controls; MF-032/033.'),('L12','Record success/errors/human interaction time separately from provider wait and ease/usefulness judgments; MF-035/044. Independent evaluator/user validation remains open.'),
])
spec+='''Evaluation uses consented minimal task/context observations, not source text, credentials, inferred demographics or silent telemetry. Automated Playwright proves scripted behavior, not novice comprehension or standards conformance. Human study outcomes remain unverified until collected; no paper's demographic or visual effect becomes an app design constant.

## 9. Benchmark and knowledge acceptance

EK-01..08 are refinements of the contracts above: distinct status dimensions; conditioned lessons; localized reversible updates; exploration vs adoption; independent support preservation; version-qualified recipes; separate human/agent/training identities; chronological held-out transfer and harm measurement. Training pipelines are out of scope.

'''
scenarios=json.loads(read(MEM+'data/evolving-knowledge-scenarios.json'))['scenarios']
spec+=table(['Scenario','Required assertion','Primary owners'],[(s['id']+' — '+s['name'],'; '.join(s['expected']),{'EKP-01':'MF-036','EKP-02':'MF-037','EKP-03':'MF-037','EKP-04':'MF-036/037','EKP-05':'MF-023/036','EKP-06':'MF-012/030/038','EKP-07':'MF-023','EKP-08':'MF-037/041','EKP-09':'MF-021/030','EKP-10':'MF-012/036'}[s['id']]+'; MF-041') for s in scenarios])
spec+='''Implement a deterministic adapter to real Session/evidence/workflow interfaces; seeds are not API calls. Include late caveat, source-instruction laundering, recipe cycle, false paraphrase conflict and forbidden-similar-source variants. Fixed input manifests and hidden rubrics remain inaccessible to the evaluated agent. Freeze source/tool/route versions, clone initial state per arm, use chronological/disjoint project splits, and repeat streams independently.

Start A no optional prior experience, B scoped original episodes, C B plus lifecycle tiers, D B plus qualified versioned lessons. Every arm retains operative requirements/current evidence/access. E recipes and F event-driven probes follow only after A–D are sound. Compare equal total budget and separately matched-quality cost. Report task predicates, partials, transfer, tasks helped/harmed, preserved valid knowledge, stale-use rate, correct/over-invalidation, adaptation lag, historical rationale, applicability errors, replication failures/unavailable, retrieval coverage, latency/human corrections, storage and all roles' tokens/known/unknown cost. Zero accepted outcomes retain total cost with no finite cost-per-success.

Deterministic integrity gates require zero dropped mandatory constraints, stale authoritative merges, duplicate accepted effects and scope leaks in authored fixtures. Behavioral improvement thresholds/pilot size must be preregistered against actual available budget; do not claim statistical benefit from ten seeds or pool correlated questions as independent samples. Layer 0 completion does not establish Layer 1–3 learning. This pass specifies the suite; execution belongs MF-041.

## 10. Verification ownership and scope limits

Every requirement above has a done-only-when check and one MF owner; document 03 supplies exact existing test paths plus explicitly planned new targets. No new target is represented as already passing. Before each implementation merge, use repo-venv source identity, focused tests and the required full regression; UI slices also check/build both distributions and run Playwright. Real Windows/Obsidian/Docker/provider evidence remains distinct. Optional features may be rejected after measurement without blocking release when explicitly excluded from shipped scope. No universal correctness, exact-once external execution, scientific replication or human-learning claim follows from finite fixtures.

'''
write(NAMES[1],spec)

execution=header('Master finalization plan: one deduplicated execution queue')
execution+='''## Execution policy and wave gates

This plan requests approval of sequencing and specifications, not authorization to spend, reconcile billing without evidence, change repository rules, freeze/sign or publish. All MF implementation rows start **planned**; external/experimental conditions are explicit below. Original IDs are retained as aliases. MF-001/002/003 are closure/reconciliation of existing work; MF-044 refreshes already delivered ACCEPT-01/03 and RELEASE-01.

Wave 0 closes the original live acceptance gap, billing/document reconciliation and current CI evidence. A real-host wait need not idle independent deterministic Wave 1 work, but prevents an acceptance-complete claim. Wave 1A and 1B may proceed concurrently only with disjoint file leases. Wave 2 needs its specific foundation dependencies; Wave 3 measures evolving knowledge on repaired continuity/resource boundaries. Wave 4 qualifies final selected scope and release artifacts.

| Wave | Scope | Exit gate |
|---|---|---|
| 0 | MF-001..004; start build assurance | Original mixed-client result retained or explicit external block; three liabilities accounted for; status/docs adoption ready; current CI failures triaged. |
| 1A | MF-005..010 | Composer/action truth, CSS/container integrity, legacy/stale oversight and durable blocked reasons tested. |
| 1B | MF-011..020 | Complete context bound, durable references, ingestion identity, quota/teardown, workflow reconciliation, service cap and V1 snapshot tests pass; live quota evidence still required. |
| 2 | MF-021..035 | Workers/MCP continuity, correlated role/services, reply/preview bridges, pinned recipes/migration and redesigned UI qualified in source and installed artifacts. |
| 3 | MF-036..041 | Native temporal/support/lesson contracts pass integrity tests; selective retrieval/graph/digest experiments have adopt/defer/reject outcomes; all ten EKP fixtures executable. Behavioral evidence reported separately. |
| 4 | MF-044..047 | Refreshed acceptance/capability/release gates, final real-host pass, owner freeze, current routes, signing and explicit publication. |
| Continuous | MF-042/043 | Per-packet docs and reproducible delivery evidence; no stale “complete” claims. |
| Decision register | MF-048..050 | Experimental/deferred work remains excluded unless separately accepted with its gates. |

**Dependency correction:** original UI-07 depends on UI-05, but the requested ordering puts UI-07 in Wave 1A and UI-05 in Wave 2. MF-008 pulls only the necessary instance/focus/disposal scaffold into Wave 1A; MF-025 completes UI-05/06 later. This removes the backwards dependency without hiding it. MF-037 does not silently remove HARNESS-09's original HARNESS-08/evidence prerequisites: scoped support can be evaluated as advisory, with conservative closure invalidation retained until a separate activation decision.

## File ownership and collision prevention

Lane labels denote future implementation owners, not agents spawned in this synthesis. Each admitted packet gets an exact file allowlist and a clean base. One write lease per file/directory; overlapping leases cannot run concurrently even across different lanes. Files listed below are planning boundaries, not blanket worker permissions. Broad DT/skills directories must be split into exact files before admission.

| Lane | Primary ownership | Scheduling restriction |
|---|---|---|
| UI | ui/src and browser fixtures | MF-007 namespacing lands first under exclusive UI-wide lease. Then MF-005/006/008/009/025/026/031..034 serialize wherever files overlap. No separate CSS/settings/pane workers editing the same files. |
| CONTEXT / SESSION | loop, projections, Session, handles, delegate, MCP | MF-010 and MF-011 share audit_projection; serialize that seam. MF-021 follows both. Core integrator owns Session/app/Registry/protocol changes; workers return suggestions for those files. |
| INDEX / INGEST | index/document identity, embed, batch/deep-read/V1 | MF-014 before later index schema work; MF-022 and MF-024 serialize staging. Batch and V1 changes explicitly split if separately drafted. |
| EXEC / RECIPE | sandbox/workbench/claim_run/workflows/macros | MF-015 → 016 → 023; MF-017 → 018 before MF-023 workflow edits. No parallel claim_run edits. |
| SERVICE / REVIEW | service_routes/TTS/STT, Clerk/Scribe/Scout, reply_review | MF-019 → 024 → 028; MF-027 integrates shared app/loop/staging after MF-021/022/024. UI portions enter UI lease, not a parallel review worker. |
| KNOWLEDGE / RETRIEVAL / EVAL | DIK/facts/closure/agenda, search/communities/ranking, benchmarks | MF-036 → 037 → 040 for DIK ownership; MF-038 → 039 for search/ranking. New test modules can be drafted independently but landed against their owning implementation. |
| DOC / BUILD / HOST / RELEASE | canonical docs, build workflows, evidence | One docs owner updates plan/manifest. One integration owner builds generated UI artifacts after source changes; workers never edit shipped JS/CSS. Real-host runner works only on declared disposable fixtures. |

At dispatch the coordinator compares allowlists, including tests, generated files and nested directories. Conflict means wait or split, never “different functions in one file” as parallel ownership. `tests/ui_demo_core.py`, `ui/smoke.mjs`, `ui/packaged-smoke.mjs`, `tests/conftest.py`, `app.py`, `session.py`, `index.py`, `loop.py` and `audit_events.py` are shared integration seams. Their final edits and merges are serialized locally. Protect unrelated existing user files and forbid scope expansion, mass formatting and test weakening.

## Single master table

P targets in the final column mean the exact pytest command in the command register below; B is the shared Playwright/build gate; H is a real-host/installed artifact gate. Each row's own done-only-when condition is mandatory even if baseline tests already pass. New targets must first be authored and collected; their absence is not a skip-worthy success.

'''
def file_list(files):
    return '<br>'.join(link(p) if (ROOT/p).exists() else '`'+p+'` (planned; confirm at admission)' for p in files)
def gating(ident):
    seen,stack=set(),[ident]
    while stack:
        x=stack.pop()
        if x not in seen: seen.add(x); stack.extend(by_id[x]['deps'])
    return seen
release_set=gating('MF-047')
execution+=f'''### Release graph (corrected 2026-11-04)

The queue has {len(tasks)} rows. {len(SPLITS)} are umbrella rows ({', '.join(SPLITS)}) whose {sum(len(v) for v in SPLITS.values())} slices do the work, so it holds {len(tasks)-len(SPLITS)} dispatchable packets, several of them documentation, process or owner decisions rather than code changes. Do not estimate it as {len(tasks)} independent coding changes.

Publication (MF-047) is gated by {len(release_set)} of {len(tasks)} rows, the release-critical path: {', '.join(sorted(release_set))}. P1 packets marked fix-or-disable reach the release only through the MF-051 scope record, as fixed or disabled; optional tracks only if MF-051 selects them; experiments and decisions never. Before this correction 45 of 50 packets gated MF-047, because MF-044 depended on the MF-041 benchmark experiment.

Roadmap stages: 1 close the baseline; 2 stabilise exposed capabilities; 3 feature safety gate and scope freeze; 4 release engineering; 5 owner-controlled release; 6 vNext continuity and UI; 7 evolving-knowledge experiments. Evidence states which findings were re-checked against source on 2026-11-04 and which rest on the source reviews alone.

'''
execution+=table(['ID / wave','Source aliases / objective','Owner and files','Dependencies','Done only when','Release role / evidence','Verification / limit'],[(t['id']+' / '+t['wave'],t['aliases']+' — '+t['title'],t['lane']+'<br>'+file_list(t['files']),', '.join(t['deps']) or 'None beyond admission',t['done'],t['release']+' · stage '+t['milestone']+'<br>blocks release if: '+t['blocking_if']+'<br>fallback: '+t['fallback']+'<br>evidence: '+t['evidence'],'P-'+t['id'][3:]+'; '+t['extra']) for t in tasks])
execution+='''## Exact verification command register

Run from `D:/Librarian_V2`. `tests/conftest.py` guards package source identity. Before first packet record executable, imported package path, git HEAD, worktree inputs and environment/lock hashes. All commands below are **future verification commands**, not results of this synthesis. Retain before-failure, after-result, exit code and relevant fixture hashes. Extend existing files with adversarial acceptance cases, not tests that merely mirror implementation.

```powershell
& .\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests/test_source_identity.py
& .\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider
```

The second command is the required full regression before a code packet's accepted merge. Do not repeat it for report-only edits. Record skips/deselections with reasons; the default suite does not substitute for explicitly required slow/live cases. Core lifecycle/coordination/CLI/MCP/writer changes need owner Windows real-child execution as prescribed in the original plan.

'''
cmdrows=[]
planned_tests=[]
for t in tasks:
    existing=[]; future=[]
    for n in t['tests']:
        if (ROOT/'tests'/n).exists(): existing.append('tests/'+n)
        else: future.append('tests/'+n); planned_tests.append('tests/'+n)
    cmd='`& .\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider '+' '.join(existing)+'`' if existing else 'No existing Python target required; use stated B/H/document gate or planned new target.'
    if future: cmd+=' After authoring planned tests, exact required combined command: `& .\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider '+' '.join(existing+future)+'`. Planned files: '+', '.join('`'+x+'`' for x in future)+'.'
    cmdrows.append(('P-'+t['id'][3:],cmd))
execution+=table(['Target','Exact command / explicit prerequisite'],cmdrows)
execution+='''### B — TypeScript, builds and Playwright

```powershell
npm.cmd --prefix ui run check
npm.cmd --prefix ui run build
npm.cmd --prefix obsidian run build
npm.cmd --prefix ui run smoke
```

`ui/run-smoke.mjs` drives `ui/smoke.mjs` through the isolated source-identity-checked scripted Core. Use existing `playwright-core` assertions; do not invent `npx playwright test` selectors for a nonexistent test runner. Add the UI-01..13 assertions at the source packet locations linked below, updating U-B1..3 expectations to real bridge fields. In particular replace old assertions for “reason not exposed”, “final preview unavailable” and unbound review when exercising new payloads; legacy input can remain explicitly unknown. Restore mocked routes after each fault and end with unmocked Search.

'''
execution+=table(['Packet assertion source','Execution'],[(link(UI+'UI-PACKETS.md',n,label=title),'Source smoke B; duplicate applicable read-only/containment cases in installed packaged smoke; real mutation in disposable fixture only') for title,n in [('UI-01 admission',45),('UI-02 action feedback',65),('UI-03 isolation',84),('UI-04 root widths',122),('UI-05 focus',140),('UI-06 semantics/touch',159),('UI-07 legacy/stale',173),('UI-08 revision/reasons',188),('UI-09 operations',206),('UI-10 preview/review/execution',220),('UI-11 role fidelity',234),('UI-12 navigation/edits',248),('UI-13 adapter runtime',263)]])
execution+='''Settings/Staging/Search additions to B: ten categories; 1120×820 max/root clamp; 224px rail and 420px selector; failed Save/dirty close/library switch; persistent Settings/Choose models; Notes-only replacement; Note/Browse/Plan/This week navigation separate from note actions/audio; mixed-state bulk defer/processing without publish; two-row Search at 390/420 widths; evidence and draft remain readable; resize/return preserves selected item and edits. At least one integrated fixture uses actual staging/revision operations rather than only mocked response JSON.

### H — Installed artifacts and real hosts

Use the existing scripts with actual resolved values for all mandatory parameters; placeholders below are variables populated from the retained candidate manifest, not literal paths to invent:

```powershell
& .\\scripts\\smoke-installed-wheel.ps1 -Python $AcceptancePython -Wheel $CandidateWheel -WorkRoot $InstalledFixtureRoot
& .\\scripts\\smoke-packaged-adapters.ps1 -Python $AcceptancePython -Wheel $CandidateWheel -CoworkZip $CandidateCoworkZip -WorkRoot $PackagedFixtureRoot
```

Confirm exact script parameter contracts at admission; retain wheel/ZIP/UI hashes and loaded protocol/version. The packaged script exercises a real installed browser plus Cowork protocol client, **not the real Claude/Cowork UI**. MF-001 must additionally use the real UI connected to the same Core as Browser and Obsidian, with sanitized request/event ordering evidence and post-close reconnect. No fabricated unattended substitute closes that criterion. MF-045/R4 repeats affected checks on final candidate/signed bytes, including SecretStorage/dirty leases and rollback.

NAT-04/05 real Docker checks extend `scripts/workbench_live_check.py` after inspecting its CLI; retain OS/Desktop/engine/WSL/storage-driver/image identity, preflight quota evidence, measured maxima/overshoot, cleanup and quarantine manifests. Current script's old export limits do not prove new live disk containment. Provider L1–L3 and behavioral EKP trials run only with their declared caps and exact route evidence; this plan initiates none.

## DeepInfra delegation and budget plan

**Verified local accounting:** G5 cap $8.00, committed $5.57622764, remaining **$2.42377236**. Three uncertain entries retain full reservations: `g5-6f67e1617aea` ($0.01247330), `g5-6cc14337750d` ($0.00690690), `g5-889befbf09d1` ($0.00677628), total $0.02615648. These liabilities are already included in committed spend; do not subtract them twice or refund automatically. Ledger snapshot/hash is recorded in validation.json, with no mutation.

**Development delegation is a separate pool, already approved.** The owner approved a $10 ceiling with about $2 spillover, and permission to send files under `D:\\Librarian_V2` to DeepInfra for review ('''+link('docs/Development transcripts/# Review Librarian V2 - chatgpt transcript -5.md',2121,label='transcript -5:2121')+' and '+link('docs/Development transcripts/# Review Librarian V2 - chatgpt transcript -5.md',2171,label='2171')+'''). The shared delegation ledger `tmp/deepinfra-delegation/ledger.json` records it as pool `shared`: budget $12.00, committed $0.1551861 over 11 calls, all on 2026-10-28, remaining **$11.8448139**, with one uncertain entry `20261028T140820-4f1c3480` ($0.00589) awaiting reconciliation. No delegated call has been recorded since 2026-10-28. The two pools are not interchangeable: development drafting and review draw on `shared`; the G5 pool stays for measurement, including any approved MF-041d trial. The following is a reviewable allocation proposal, not a paid dispatch approval or price quote. Rates/route availability must be checked through existing runner/ledger policy at dispatch; historical model prices are not assumed current.

'''
execution+=table(['Wave / bounded candidate','Worker contribution','Draft + independent review maximum','Local-only integration'],[
('1: MF-013 NAT-01','Draft chunk identity regression and narrow implementation on approved file list','$0.35 + $0.20 = $0.55','Lead verifies source/chunker invalidation and runs full checks.'),
('1: MF-020 NAT-13 snapshot slice','Review byte-snapshot/batch reuse cases; draft isolated fixture/patch','$0.30 + $0.15 = $0.45','Lead owns writer/batch/CAS integration; no live V1 corpus mutation.'),
('2: MF-031/033 UI role/scope copy','Draft role-selection and Settings failure/label cases; no simultaneous settings edits','$0.25 + $0.15 = $0.40','UI owner integrates and runs both builds/Playwright/real-host gate.'),
('2: MF-029 migration fidelity','Draft aliases/edges/attachments fixture and reviewer checklist','$0.25 + $0.15 = $0.40','Lead checks every disposition and V1 byte preservation.'),
('3: MF-041 EKP adapter fixtures','Draft deterministic expected cases from all seeds; review leakage/denominators','$0.20 + $0.15 = $0.35','Lead authors/validates actual adapter semantics and hidden scoring.'),
('Unallocated in pool shared','No automatic consumption; repair or uncertainty only with cap check','$9.6948139','Scheduled $2.15 of $11.8448139 remaining in pool shared; G5 untouched.'),
])
execution+='''Allocate these from pool `shared`, never from `g5`. Beyond the $2.15 first slice, allow at most $2.00 for held-out fixture/review expansion and $1.00 for bounded repairs; the rest stays unallocated until a packet names it. Every call runs through `scripts/delegate_deepinfra.py --pool shared`, so the ledger, not an agent's summary, is the evidence that delegation happened. The approved ceiling adds no automatic spending entitlement. Extra money does not justify broader worker authority or revive DELEG-06 automation.

Use existing `scripts/delegate_deepinfra.py`, `scripts/delegate_ledger.py` and the work-package schema/linter/scope guard. Each package names base commit, exact allowed/forbidden files, preserved behavior, expected failure, deterministic checks, budget/call limit, distinct model-family drafter/reviewer and local merge owner. Select candidates from currently qualified routes at dispatch; the original GLM/Qwen/DeepSeek lane names are historical candidates, not guaranteed current availability. If a max-token reservation exceeds the row cap, reduce/split scope or execute locally rather than dispatch under an optimistic average-cost estimate.

Never delegate final Core/IndexService/VaultWriter authority, token-accounting guarantees, budget settlement, Docker quota/teardown containment, migration acceptance, epistemic closure integration, signed-release decisions or credential access. Workers may propose adversarial tests/review those boundaries, but the lead checks them locally and on required real hosts. All retries/repairs/reviewer calls reserve from the same task/pool; unknown completion retains full reservation and stops the affected task. Artifacts pass protected diff-scope checks and deterministic tests before acceptance. No paid calls or worker agents were launched by this synthesis.

## Completion record for every packet

Record MF and source aliases; exact source/base/candidate and dirty-input hashes; permitted files and reviewer identity; before-failure and focused/full/B/H commands; result counts and skipped/deselected reasons; actual versus simulated/provider/OS coverage; receipt/reservation IDs; remaining limitations; documentation changes; accept/reject disposition. Do not infer delivery from a written design or successful baseline test. Release owner gates remain the existing SI/LC/R0–R5 process. Where an optional experiment has no benefit, record rejection/defer and retain the simpler baseline rather than silently shipping it.

'''
execution+='References: '+link('docs/delegation-work-package.md')+'; '+link('scripts/delegate_deepinfra.py')+'; '+link('scripts/delegate_ledger.py')+'; '+link('docs/release-implementation-queue.md',82)+'.\n'
write(NAMES[2],execution)

integration=header('Plan integration summary: proposed edits after approval')
integration+='''The canonical unified plan, regression manifest and runtime code were **not modified** in this pass. Approving this report set adopts the reconciled specifications and queue; it does not retrospectively mark any new MF packet implemented or authorize paid calls, repository settings, signing or publication.

## Unified plan crosswalk

'''
integration+=table(['Current location','Proposed exact integration','Status effect'],[
(link(PLAN,20),'Add dated pointer to this report set; preserve G0–G7 and original sequencing history; state MF queue is the approved finalization extension, with user corrections taking precedence over older review proposals.','No delivery changes from approval alone.'),
(link(PLAN,96),'Use implemented/partial/planned/blocked externally/retired consistently; experimental/deferred are qualifiers with an explicit decision.','Separate implemented code, qualification evidence and release readiness.'),
(link(PLAN,189),'Preserve DELEG-01/03/11. Update DELEG-06 note to retain small-refactor stop and link MF-049; add corrected budget snapshot and bounded draft/review plan.','No autonomous controller rollout or spend authorization.'),
(link(PLAN,250),'Record BASE-03/04/05 as delivered; add follow-up MF-003/042 for current status/vocabulary/manifest sync.','Do not reimplement old BASE tasks.'),
(link(PLAN,264),'Keep CORE-04A delivered and CORE-04B deferred managed bootstrap; explicitly prohibit direct/no-Core state ownership.','New MCP continuity tests MF-030 extend, not replace, delivered RPC.'),
(link(PLAN,279),'Link latest INDEX-02/03 closure and INDEX-05 closure; retain external acceptance transfer. Add NAT-02 rename fix and NAT-03 recovery/counters as new MF-014/022.','No reopening encoder writer release as absent.'),
(link(PLAN,394),'Keep HARNESS-01..07 delivered; add MC-01..16 requirements and MEM→MF mapping. Preserve HARNESS-08 and HARNESS-09 gates.','Scoped support prototype is not automatic activation of full targeted closure invalidation.'),
(anchor(PLAN,'### REMED-08 measurement'),'Keep completed REMED-08, met REMED-06 exit and task-local timeout approval. Add MF-002 three-entry liability reconciliation; cite current ledger/report.','Older two-entry/pending-MiMo handoff superseded.'),
(anchor(PLAN,'### ACCEPT-02 real-Obsidian refresh'),'Record only three-client mixed traffic as original remaining ACCEPT-02 item; preserve artifact/overlay distinctions; add final changed-artifact rerun MF-045.','Partial until real evidence; protocol smoke insufficient.'),
(link(PLAN,421),'Keep ACCEPT-01/03 and RELEASE-01 implemented; add MF-044 refresh, MF-046/047 external gates and DT release evidence prerequisites.','No R0 freeze or stable certification now.'),
(link(PLAN,515),'Retain exclusions/deferrals: full HARNESS-09, DEPLOY-05, CORE-04B, DEV profile; mark graph/digest/lesson experiments conditional with explicit keep/defer/reject outcomes.','No hidden dependency adoption.'),
(anchor(PLAN,'## 19.'),'Append dated master-synthesis adoption entry only after approval, with all MF rows planned and full links. Subsequent implementation entries cite exact commits/tests, not this report as proof.','Historical progress entries remain intact.'),
])
integration+='''## Regression manifest corrections

Retain historical partial rows as dated evidence, but add a clearly labeled current-status table and supersession pointers so they cannot be mistaken for today's backlog. Apply these changes under MF-003/042:

'''
integration+=table(['Manifest row / anchor','Current replacement or clarification','Evidence authority'],[
(link('docs/regression-manifest.md',44),'INDEX-05 → implemented original scope; remaining host/release checks tracked ACCEPT-02/RELEASE-03. NAT findings new rows.','Unified plan INDEX-05 closure and later acceptance record.'),
(link('docs/regression-manifest.md',46),'Remove encoder-occupies-writer from current limitation; retain as historical snapshot and point to 33fb3b5.','Unified plan line 759; NAT-03 preserves delivered separation.'),
(link('docs/regression-manifest.md',35),'Earlier CORE-05/INDEX batch partial rows (35–55) explicitly historical; current zero serving debt closure linked.','Unified plan latest reconciliation, not an inferred code audit.'),
(link('docs/regression-manifest.md',66),'Split DEPLOY-01..04 implemented from DEPLOY-05 deferred.','§19 DEPLOY records and deferred decision.'),
(link('docs/regression-manifest.md',67),'Split HARNESS-01..07 implemented, HARNESS-08 experimental, HARNESS-09 deferred. Attach later real-session measurement caveats.','§19 and corrected G5/REMED-08 report.'),
(link('docs/regression-manifest.md',69),'ACCEPT-02 partial: one original real three-client check; listed Obsidian/Docker/handles already evidenced, final artifact rerun later.','Acceptance checklist and three JSON artifacts.'),
(link('docs/regression-manifest.md',71),'RELEASE-01 implemented docs; RELEASE-02/03 remain externally blocked.','§19 RELEASE-01 and current release queue.'),
('New rows','One MF row per execution packet from document 03 with aliases, exact command, source identity, fixture class, expected invariant, new-target marker and real-host gate.','Do not paste planned assertions into evidence/pass column.'),
])
integration+='''Proposed new row schema:

```text
MF ID | original aliases | delivery status | source revision / dirty manifest
focused command | full regression result | UI/installed/real-host gate
fixture class (L0/scripted/real OS/live provider) | invariant / failure injected
artifact / receipt / report paths | reviewer | remaining limitation
```

Exact focused commands and Playwright/host conventions are maintained in document 03; duplicate neither a second implementation queue nor a contradictory status authority. New test filenames remain planned until authored/collected. Source-only smoke, installed protocol smoke and real Claude/Obsidian observations need separate cells. Benchmark seeds/reference models are not runtime pass evidence.

## Alias crosswalk without duplicate execution

'''
integration+=table(['Source set','Canonical execution mapping'],[
('MEM-01 / 02 / 03 / 04','MF-011 / MF-011 / MF-012 / MF-021'),
('MEM-05 / 06 / 07 / 08','MF-036 / MF-036 / MF-021 (with MF-019/024) / MF-038'),
('MEM-09 / 10 / 11 / 12','MF-039 / MF-037 conditional / MF-040 conditional / MF-012+036'),
('NAT-01..08','MF-013,014,022,015,016,017,018,023'),
('NAT-09..17','MF-024,027,019,028,020,029,036,037,042'),
('UI-01..04','MF-005,006,007,008'),
('UI-05..08','MF-008 prerequisite + MF-025 completion; MF-025; MF-009; MF-010'),
('UI-09..13','MF-026,027,031,032–034,035'),
('Settings four steps','MF-032 shell; MF-032 redistribution; MF-031/033 simplification; MF-034 workflow connection; MF-035 verification across all steps'),
('EK-01..08 / EKP-01..10','MF-036/037 temporal/lesson/support, MF-023 recipes, MF-021/030 continuity; MF-041 integrates all ten benchmark cases.'),
('DT-01..07','MF-004 current CI; MF-043 reproducibility/CI/dependency/provenance/operating discipline; DT-06 contained execution slice MF-015/016/023. Full DEV scope deferred.'),
])
integration+='''## Review corrections applied (2026-11-04)

Codex reviewed this set and found two material errors, which Claude re-checked by script and corrected in the generator:

- **Release coupling.** 45 of the original 50 packets gated publication, because MF-044 depended on the MF-041 benchmark experiment. MF-044 now depends on a frozen selected-scope record, MF-051. The release-critical path is the packets marked `required`; P1 packets reach the release as fixed or disabled through MF-051, optional tracks only if it selects them, and experiments never.
- **Delegation budget.** Development delegation is a separate, approved pool (`shared`, $12, $11.84 remaining), not the G5 measurement pool. Draft allocations now come from `shared`, and G5 stays for measurement. The cited approvals are transcript -5 lines 2121 and 2171; the earlier citation to line 1929 was wrong.

Also applied:
- MF-021, MF-027, MF-034, MF-036, MF-041 and MF-043 are split into sub-packets, each dispatched and merged on its own; the parent is the umbrella.
- Every packet now records its release role, roadmap stage, the condition under which it blocks a release, its fallback, and its evidence state, including which findings were re-checked against source on 2026-11-04.
- MF-004 records hosted CI as observed red.

The adopted set still needs owner approval before MF-003 updates the canonical plan.

'''
integration+='''## Approval and remaining decisions

The concrete approval object is these four documents, including corrected scope and budget, with optional experiments explicitly conditional. After approval, MF-003 can update canonical documents and admit bounded implementation packets. No further architecture survey is required to start independent Wave 1 fixes.

Remaining decisions belong to their actual gates: three uncertain receipts need provider evidence or retained liability; the development delegation pool is approved (pool `shared`, $12) but each dispatch still names its packet and cap; disk quota support needs host qualification before contained execution; selective HARNESS-09 activation and optional Tier B/digest/community/lesson behavioral experiments need measured go/no-go; release needs owner freeze/sign/publish decisions. These are not reasons to block the completed documentation synthesis or request confirmation for routine local editing.

## Validation record

The generator's validation.json records link/line-anchor checks, exact source/report/image hashes, planned test targets, unique MF IDs and dependency checks, and SQL-DDL syntax validation against an in-memory SQLite database. All linked local paths and numeric anchors in the four generated documents must exist and fall within file length. Anchors intentionally refer to this source snapshot and should be refreshed after code changes. A valid line number alone is not a future-source semantic guarantee; important code/report anchors were checked against the cited source content during synthesis.

The concept image and external QA source snapshots are preserved under this folder. No full regression is claimed for this report-only pass; runtime/source tests remain the retained historical evidence and the planned commands. Neither docs/unified-implementation-plan.md nor docs/regression-manifest.md is changed. Existing user work remains untouched.

'''
write(NAMES[3],integration)

# Preserve external source materials byte-for-byte. Their internal relative screenshot links remain usable.
qa_copy=OUT/'sources/qa'
qa_copy.mkdir(parents=True,exist_ok=True)
for p in QA.iterdir():
    if p.is_file() and p.suffix in ('.md','.png'): shutil.copy2(p,qa_copy/p.name)
shutil.copy2(QA/'settings-layout-concept.png',OUT/'settings-layout-concept.png')

# Self-contained machine-readable provenance and validation, not application tests.
errors=[]; link_count=0; anchor_count=0
for name in NAMES:
    text=(OUT/name).read_text(encoding='utf-8')
    for match in re.finditer(r'\[[^\]]*\]\((<[^>]+>|[^)]+)\)',text):
        target=match[1].strip('<>')
        if target.startswith(('http:','https:','mailto:','#')): continue
        target=target[1:] if re.match(r'^/[A-Za-z]:/',target) else target
        m=re.fullmatch(r'(.*?)(?::(\d+))?',target)
        p=Path(m[1]); p=p if p.is_absolute() else OUT/p
        link_count+=1
        if not p.exists(): errors.append(f'{name}: missing {target}'); continue
        if m[2]:
            anchor_count+=1; n=int(m[2])
            if p.is_dir() or not 1<=n<=len(p.read_text(encoding='utf-8-sig').splitlines()): errors.append(f'{name}: invalid anchor {target}')
ids={t['id'] for t in tasks}
if len(ids)!=len(tasks): errors.append('Duplicate MF ID')
for t in tasks:
    for dep in t['deps']:
        if dep not in ids: errors.append('Unknown dependency '+dep)
def visit(id,stack,done):
    if id in stack: errors.append('Dependency cycle '+str(stack+[id])); return
    if id in done: return
    for dep in next(t for t in tasks if t['id']==id)['deps']: visit(dep,stack+[id],done)
    done.add(id)
done=set()
for id in ids: visit(id,[],done)
db=sqlite3.connect(':memory:')
db.execute('PRAGMA foreign_keys=ON')
try: db.executescript(SQL)
except Exception as e: errors.append('DDL '+str(e))
db.close()
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
source_hashes={str(p if Path(p).is_absolute() else ROOT/p):digest(p if Path(p).is_absolute() else ROOT/p) for p in sources}
ledger=ROOT/'tmp/g5/ledger.json'
data=json.loads(ledger.read_text(encoding='utf-8'))
validation={'date':'2026-11-04','source_commit':'40ec923f5d7cb5612939b9fc456963b88e0af4a3','local_links_checked':link_count,'line_anchors_checked':anchor_count,'unique_master_packets':len(ids),'dependency_graph_acyclic':not any('cycle' in e for e in errors),'sql_ddl_syntax':'passed' if not any(e.startswith('DDL') for e in errors) else 'failed','errors':errors,'report_hashes':{n:digest(OUT/n) for n in NAMES},'source_hashes':source_hashes,'concept_copy_sha256':digest(OUT/'settings-layout-concept.png'),'concept_copy_matches_source':digest(OUT/'settings-layout-concept.png')==digest(QA/'settings-layout-concept.png'),'ledger_snapshot':{'sha256':digest(ledger),'pools':data['pools'],'uncertain_ids':[c['run_id'] for c in data['calls'] if c.get('status')=='uncertain']},'delegation_ledger_snapshot':{'path':'tmp/deepinfra-delegation/ledger.json','sha256':digest(DELEG),'pool':'shared','budget_usd':deleg['pools']['shared']['budget_usd'],'committed_usd':shared_committed,'remaining_usd':round(deleg['pools']['shared']['budget_usd']-shared_committed,8),'calls':len(shared),'uncertain_ids':[c['run_id'] for c in shared if c.get('status') in ('uncertain','started')]},'suite_run':{k:suite[k] for k in ('command','exit_code','summary','head','python','platform','log_sha256')},'not_run':['Playwright','Docker','paid provider calls','EKP benchmark','release'],'planned_nonexistent_test_targets':sorted(set(planned_tests))}
(OUT/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'execution-queue.json').write_text(json.dumps(tasks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in validation.items() if k not in ('source_hashes','report_hashes')},indent=2))
if errors: raise SystemExit(1)

