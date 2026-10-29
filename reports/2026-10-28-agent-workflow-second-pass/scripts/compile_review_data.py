"""Render explicit reviewer dispositions and verify new short source anchors."""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ORIGINAL = ROOT.parent / '2026-10-28-agent-workflow-sprint'
sys.path.insert(0, str(REPO/'src'))
from resource_librarian.clerk import quoted

def read(name):
    with (ORIGINAL/'data'/name).open(encoding='utf-8') as f:
        return list(csv.DictReader(f))
def write_csv(name, values):
    with (ROOT/'data'/name).open('w', encoding='utf-8', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(values[0])); w.writeheader(); w.writerows(values)

# Original rank -> review priority, depth, reason. Adjacent methods are not direct validations.
DECISIONS = {
1: ('core_with_cautions','methods, results, limitations, rendered formula','Retain drift concept; add token/conservatism costs, heuristic estimates and formal-definition issues.'),
2: ('core_with_cautions','architecture, metrics, tables, references; rendered p16','Retain task tree; code URL placeholder, bibliography defects and uncertain reproducibility.'),
3: ('core','methods, case study, limitations','Extract non-monotonic context utility, knowledge lifecycle and amortization assumptions.'),
4: ('orientation','abstract and original card audit','Survey routing/annotation concepts; cited savings need original experimental sources.'),
5: ('core','communication and navigation methods, results','Keep RL message-size result distinct from LLM inference costs.'),
6: ('core_with_cautions','implementation, results, limitations','Agreement improves; approval differences nonsignificant; fixed feedback and groupthink cautions.'),
7: ('core','planning, evaluation, costs, parallelism; rendered p8','Promote: omitted verifier-cost and measured parallel-acceleration evidence.'),
8: ('core','benchmark, routing, controls, cost/frontier sections','Add false-refusal tradeoff, negative self-reflection control and serving-cost assumptions.'),
9: ('core_with_cautions','hierarchy, adaptive depth, limitations, appendix assumptions','Offline reward-model architecture; cost and label-error floor; no guarantee for our validators.'),
10: ('orientation','abstract and original card audit','Taxonomy and memory framing; not new evidence of orchestration savings.'),
11: ('core','domain/effects, state/action encoding, evaluation, limitations','Promote metrics and explicit effects; resolve metadata through publisher.'),
12: ('core_with_cautions','metrics, results, ablation, publication header','Same ReflectiChain lineage; treat as related, not independent replication.'),
13: ('orientation','abstract and original card audit','Conceptual architecture taxonomy; no measured software-delegation economics.'),
14: ('core','schema, decomposition, critic tests, perturbation results','Promote matched-rule and adaptive-controller baselines; numerical agents.'),
15: ('adjacent','abstract and original card audit','Intent/resource role separation; specialized telecom training assumptions.'),
16: ('orientation','abstract and original card audit; existing harness references','Agent lifecycle framing; do not count a survey as new experiment.'),
17: ('defer','head-scoring method and evaluation','Requires internal KV/head access; agent credit assignment is an expensive analogy.'),
18: ('orientation','abstract and original card audit','Industrial monitoring/ensemble analogy; no delegated-code validation.'),
19: ('adjacent_promote','study framing and selected collaboration/verification/context sections','Human review and coordination work belong in economics; qualitative evidence only.'),
20: ('adjacent_promote','abstract, retrieval/compatibility mechanism and result table','Candidate tool sets and compatibility are useful; recommendation is not authorization.'),
21: ('orientation','abstract','Broad cyber application survey; no new priority over existing safety/closure design.'),
22: ('exclude_from_this_synthesis','abstract','Physical UAV tracking/reward learning; no specific current implementation transfer.'),
23: ('defer','abstract','Shared learned state is a distant analogy; do not transfer RL convergence speedup.'),
24: ('defer','abstract','Local control reducing network communication; training/power-system assumptions differ.'),
25: ('adjacent_promote','abstract, workflow and verification sections','Directly useful synthesis/repair and semantic-vs-executable distinction; survey evidence.'),
26: ('adjacent_promote','formal composition/trace sections','Formal trace contracts for async services; not a reason to build a replacement bus.'),
27: ('exclude_from_this_synthesis','abstract','Visual abductive task; weaker transfer than directly grounded evidence methods.'),
28: ('adjacent_promote','abstract, program models and query sections','Structural/static checking can replace repeated manual verification.'),
29: ('exclude_from_this_synthesis','opening problem/method framing','Job-shop search branching is too remote from current agent changes.'),
30: ('adjacent_design_only','abstract','Human agency and consequential questioning; no quantitative orchestration result.'),
31: ('exclude_from_this_synthesis','abstract','Few-shot graph node generation; not current task orchestration.'),
32: ('adjacent','abstract, modeling/validation workflow sections','Declarative resource/capability compatibility and constraints; no need to adopt ontology stack.'),
33: ('adjacent_promote','abstract, structural/semantic framing','Dependency/document skeleton useful for state assembly; no validated handoff savings.'),
34: ('exclude_from_this_synthesis','abstract','Diffusion backdoor semantic drift differs from runtime plan/constraint drift.'),
35: ('exclude_from_this_synthesis','abstract','Manufacturing/AGV optimizer; not a current orchestration contribution.'),
36: ('adjacent_design_only','opening framing','Library usability goal decomposition; potential UX work, not delegation-cost evidence.'),
37: ('exclude_from_this_synthesis','abstract','Graph representation training; no immediate transfer to these proposals.'),
38: ('exclude_from_this_synthesis','abstract','Graph continual-learning fine-tuning; not runtime conversational forgetting.'),
39: ('adjacent_design_only','abstract','Goal context helps interpretation; no evidence for our runtime metric thresholds.'),
40: ('exclude_from_this_synthesis','abstract','Physical ship control; no concrete current transfer.'),
41: ('exclude_from_this_synthesis','abstract','Trajectory-prediction model; not agent planning drift.'),
42: ('adjacent_promote','grounding/faithfulness methods; rendered distinction table','Quote presence and decision relevance differ; counterfactual support probes useful.'),
43: ('adjacent_promote','abstract, staged framework and bounded token selector','Budgeted structural context already recognized by harness design.'),
44: ('exclude_from_this_synthesis','abstract','VGAE representation drift is different from agent plan drift.'),
45: ('adjacent_promote','introductory formalization and invariant-pattern mechanism','Reusable temporal properties/invariants support deterministic verification catalogue.'),
46: ('exclude_from_this_synthesis','abstract','Class-incremental representation compensation is not agent context continuity.'),
47: ('defer','abstract','Cloud scheduling has workload/cost analogies; no justification for new RL scheduler now.'),
48: ('defer','abstract','Visual evidence/self-reflection framework; narrower than direct evidence-faithfulness methods.'),
49: ('adjacent_design_only','abstract','Agency/accountability theory; support user control requirements without numeric savings.'),
50: ('exclude_from_this_synthesis','abstract','Climate-verification editorial; no current orchestration method.'),
}

# Every quote is checked against freshly extracted PDF text, not an old model card.
SUPPLEMENTS = [
(1,20,'8.2 Computational Cost of Reflection','Cost of reflection','+68% tokens relative to ReAct'),
(1,22,'10 Conclusions and Future Work','Heuristic drift estimates','Drift α estimates are derived from heuristic trajectory data'),
(1,18,'7.10 Cross-domain benchmark results, Table 9','Negative code-domain transfer','CodeSim (Code)'),
(2,16,'Code availability','Reproducibility limit','repository URL to be added upon acceptance'),
(3,8,'IV.C Results and analysis','Context amount and composition confounded','varies knowledge amount and composition jointly'),
(3,8,'IV.C Results and analysis','Non-monotonic knowledge utility','redundancy and reconciliation'),
(5,10,'V Simulation results','Attribute byte savings to MAPPO-BDP','60% reduction in communication overhead'),
(6,7,'5.1 Results','Approval is not agreement','We did not observe a statistically significant change in approval rates'),
(7,8,'IV.E Analysis of failure, module accuracy and efficiency','Verifier cost dominates','overhead is dominated by the Judge module'),
(7,8,'IV.F Parallel Acceleration','Actual parallel rollout measurement','reduces the simulation time of Task 5 from 55 s to 26 s'),
(8,5,'III.D Cost-weighted safety metric','False refusal and false execution','false-refusal rate'),
(8,11,'VI.G comparison control','Self-reflection control','0 label flips in 1,000 reflections'),
(9,20,'9 Limitations','Offline deployment and cost','offline reward-labeling and batch-RLHF method'),
(11,4,'4 Formal Framework','Check task effects','checks the current world state against the defined task effects'),
(11,8,'6.3 Evaluation Metrics','Task difficulty before comparison','planning time, number of planning'),
(14,17,'4.6 Decomposition','Matched fixed-rule control','not statistically robust'),
(14,22,'4.14.2 Structural shock','Refreshing targets confounds model contribution','frozen target list'),
(19,31,'4.4 Remixing meeting outputs','Human verification effort','reviewed and edited as necessary'),
(25,7,'3.2.3 CO model verification','Execution versus semantic acceptance','executability checking'),
(28,6,'3.3 Detailed Program Design Model','Structural dependency checking','Which program statements affect'),
(26,10,'5 Conclusion','Separate communication and computation','separates the communication behavior from the computation behavior'),
(42,9,'4 method discussion','Presence does not establish faithfulness','Extractiveness by itself does not establish'),
(42,13,'4.5.4 Faithfulness constraints','Evidence sufficiency and removal tests','sufficiency and comprehensiveness'),
(43,7,'3.2.2 Structure-aware learning','Bounded structural context','under a fixed budget'),
(45,2,'Introduction','Requirement plus supporting invariant','an extra invariant that contains structural information'),
]

OPENAI='https://openai.com/index/navier-stokes-solution/'
CLAIMS={
'001':('unverified','Exact page count/proof-content evaluation not checked; subjective recommendation is separate.',''),
'002':('unverified','A zero-content claim requires full proof inspection; not established.',''),
'003':('unverified','No specific staff disclosure was identified and fetched.',''),
'004':('partly_supported','Discovery/consolidation/formalisation are described; distinct automated phases are interpretation.',OPENAI),
'005':('partly_supported','Grouped internal-model agents are described; retain only stated isolation details.',OPENAI),
'006':('verified','Different groups received different problem variants.',OPENAI),
'007':('verified','Separate groups received proof and disproof variants.',OPENAI),
'008':('verified','Approximate concurrency stated for relevant group.',OPENAI),
'009':('verified','Run-specific time and message figures are stated.',OPENAI),
'010':('scope_correction','Larger totals refer to all attempted problems.',OPENAI),
'011':('partly_supported','Codex consolidation supported; periodic pauses/sampling not established.',OPENAI),
'012':('partly_supported','Consolidation of useful insights supported; exact raw ingestion mechanism unspecified.',OPENAI),
'013':('partly_supported','Internal-model discovery supported; page count not checked here.',OPENAI),
'014':('verified','Additional formalisation/verification phase is explicitly stated.',OPENAI),
'015':('plausible','General specification-translation risk; no specific demonstrated drift audited here.',''),
'016':('unverified','Public absence of UI/code cannot be inferred from one announcement.',''),
'017':('unverified','Specific controller architecture is not disclosed by retrieved source.',''),
'018':('unverified','Monitoring/isolation does not establish strict network-isolated sandbox topology.',''),
'019':('partly_supported','Codex consolidation supported; precise automated control-plane node unspecified.',OPENAI),
'020':('verified','Lean formalisation/verification is described.',OPENAI),
'021':('unverified','Exact proof contents not reviewed.',''),
'022':('scope_correction','Mixes group/run and all-problem totals.',OPENAI),
'023':('partly_supported','Named formaliser is supported; exact artifact-level attribution not audited.',OPENAI),
'024':('unverified','Specific critical teardown not identified and evaluated.',''),
'025':('plausible','Need initial-release version; current README and history are different snapshots.','https://github.com/openai/math/blob/main/history.md'),
'026':('partly_supported','Consolidation supported; periodic bottleneck characterization not established.',OPENAI),
'027':('plausible','Possible semantic mismatch does not prove intentional model behavior.',''),
'028':('unverified','Message contents and schema were not inspected.',''),
'029':('partly_supported','vLLM schema/grammar constrained outputs documented; Outlines not checked.','https://docs.vllm.ai/en/latest/features/structured_outputs/'),
'039':('local_measured_proxy','Cache/input aggregates support context reuse; universal every-turn mechanism not established.','../2026-10-28-agent-workflow-sprint/data/baseline_metrics.json'),
'054':('unverified','Shared platform-pool causal explanation is not demonstrated by local error counts.',''),
'078':('design_hypothesis','Workload selection heuristic, not a measured universal deployment fact.',''),
'079':('design_hypothesis','Attempt-bounded compute heuristic requires task-specific benchmarking.',''),
'085':('local_partly_supported','Recorded rent-to-runner timing does not isolate image/weight provisioning.','../2026-10-28-agent-workflow-sprint/data/vast_summary.json'),
'089':('unverified','Savings and dollar cap require paired task measurement; current follow-up metric flawed.',''),
'090':('unverified','Illustrative rental price/stack needs actual hardware, image and utilization.',''),
'093':('unverified','Zero-model-token runtime and GPU-hours depend on the exact workload/controller.',''),
'094':('design_hypothesis','Illustrative CLI command is not evidence that it exists.',''),
'095':('partly_supported','Captured listing supports availability, not autonomous coding/debugging capability.','../2026-10-28-agent-workflow-sprint/data/deepinfra_live_check.json'),
'096':('partly_supported','Local controller/API prior art exists; exact image contents not established.','../2026-10-28-agent-workflow-sprint/data/vast_summary.json'),
'098':('local_reported_unverified','Behavioral generalization from historical local sessions; not a vendor fact.',''),
'099':('local_reported_unverified','Every-session universal claim is unsupported by a sampled transcript.',''),
'105':('local_reported','Historical local tooling assertion; quote is not independent execution proof.',''),
'106':('local_reported_unverified','Historical exact-model/packet claim; model suffix not established.',''),
'108':('local_reported_unverified','Historical overlap timing claim requires task timestamps.',''),
'109':('local_reported','Evidence-handling policy statement; do not classify as model capability.',''),
'110':('local_reported','Interpretation of historical review behavior; not a general model property.',''),
'123':('local_reported_unverified','Historical experiment/budget claim; complete per-task reconciliation not supplied.',''),
'132':('local_reported_unverified','Specific prior page-error anecdote not independently adjudicated here.',''),
'133':('local_reported_unverified','Specific prior author-error anecdote not independently adjudicated here.',''),
'139':('unverified','Budget estimate and deterministic completion claim lack a defined reproducible workload.',''),
'142':('local_reported','Historical code-review finding must be bound to its revision, not current source.',''),
'144':('local_supported','Repository plan records launch-path measurement; this review did not repeat lifecycle probe.','../../docs/unified-implementation-plan.md'),
'145':('local_supported','Repository fix/test provenance documents behavior in that Windows setup.','../../docs/unified-implementation-plan.md'),
'147':('local_reported_unverified','Exact earlier route walk failures not rerun; do not generalize from model names.',''),
'152':('local_reported_unverified','Historical reflog recovery assertion not independently replayed.',''),
'153':('local_reported_unverified','Specific historical approval refusal is not a universal platform policy.',''),
'155':('local_supported','Structured limit events support repeated hits; exact mid-suite attribution not checked.','../2026-10-28-agent-workflow-sprint/data/m5_limits.csv'),
}

def main():
    ranked=read('reading_list_ranked.csv')
    inv={r['slug']:r for r in read('papers_inventory.csv')}
    coverage=[]
    for r in ranked:
        priority,depth,why=DECISIONS[int(r['rank'])]
        coverage.append({'original_rank':r['rank'],'file':r['file'],'title':inv[r['slug']].get('meta_title') or r['title'],
            'review_priority':priority,'inspection_depth':depth,'decision_reason':why,'sha256':inv[r['slug']]['sha256']})
    write_csv('literature_coverage.csv',coverage)
    supplements=[]
    for rank,page,section,method,quote in SUPPLEMENTS:
        ss=re.split(r'\[\[PAGE \d+\]\]\n',(ROOT/'data/paper_text'/f'rank-{rank:02d}.txt').read_text(encoding='utf-8'))[1:]
        ok=quoted(quote,ss[page-1])
        supplements.append({'rank':rank,'file':ranked[rank-1]['file'],'page':page,'section':section,'method':method,'quote':quote,'exact_page_verified':ok})
    (ROOT/'data/supplement_methods.json').write_text(json.dumps(supplements,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    failed=[r for r in supplements if not r['exact_page_verified']]
    outside=[r for r in read('claim_register.csv') if r['class'] in {'outside_company','outside_tool','model_capability','pricing'} and r['tag']!='local']
    missing={r['id'][3:] for r in outside}-CLAIMS.keys()
    assert not missing,missing
    claim_rows=[]
    for r in outside:
        verdict,reason,source=CLAIMS[r['id'][3:]]
        claim_rows.append({'id':r['id'],'original_class':r['class'],'original_status':r['tag'],
            'claim':r['quote'],'second_pass_status':verdict,'reason':reason,'source':source,'checked_date':'2026-10-28'})
    write_csv('claim_review.csv',claim_rows)
    print(json.dumps({'coverage_rows':len(coverage),'claim_dispositions':len(claim_rows),'supplement_anchors':len(supplements),'anchor_failures':failed},indent=2,ensure_ascii=False))
    if failed:
        raise SystemExit(1)

if __name__=='__main__':
    main()
